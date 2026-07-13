"""GPU overlay batching, caching, drawing, and lifecycle."""

import time
from collections import defaultdict

import bmesh
import bpy
import gpu
from bpy.app.handlers import persistent
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from .constants import EDGE, ELEMENT_TYPES, FACE, VERTEX, element_spec
from .evaluated_geometry import (
    evaluated_overlay_geometry,
    ordered_edge_chains,
    trim_edge_chain,
)
from .model import (
    active_layer,
    debug_log,
    element_container,
    ensure_annotation_layers,
    ensure_lookup_tables,
    get_layer_collection,
    layer_order_map,
    load_element_layers,
    merge_stack_layer_into_mapping,
    normalize_layer_ids,
    save_element_layers,
)


_draw_handle = None
_overlay_batch_cache = {}
_overlay_topology_counts = {}
_overlay_refresh_timer_pending = False


def invalidate_overlay_cache():
    _overlay_batch_cache.clear()


def mark_overlay_cache_dirty(obj=None):
    if obj is not None:
        cached = _overlay_batch_cache.get(obj.as_pointer())
        if cached is not None:
            cached["dirty"] = True
        return
    for cached in _overlay_batch_cache.values():
        cached["dirty"] = True


def _overlay_refresh_timer():
    global _overlay_refresh_timer_pending
    _overlay_refresh_timer_pending = False
    tag_view3d_redraw(invalidate_cache=False)
    return None


def _schedule_overlay_refresh(delay):
    global _overlay_refresh_timer_pending
    if _overlay_refresh_timer_pending:
        return
    _overlay_refresh_timer_pending = True
    bpy.app.timers.register(_overlay_refresh_timer, first_interval=max(0.01, float(delay)))


def tag_view3d_redraw(context=None, invalidate_cache=True):
    if invalidate_cache:
        invalidate_overlay_cache()
    context = context or bpy.context
    wm = context.window_manager if context else None
    if wm is None:
        return
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _modifier_state_signature(obj: bpy.types.Object):
    signature = []
    supported_types = {"BOOLEAN", "INT", "FLOAT", "ENUM", "STRING", "POINTER"}
    for modifier in obj.modifiers:
        values = []
        for prop in modifier.bl_rna.properties:
            if (
                prop.identifier == "rna_type"
                or prop.is_readonly
                or prop.type not in supported_types
            ):
                continue
            try:
                value = getattr(modifier, prop.identifier)
                if prop.is_array:
                    value = tuple(round(float(item), 9) for item in value)
                elif prop.type == "POINTER":
                    value = value.as_pointer() if value is not None else 0
                elif prop.type == "FLOAT":
                    value = round(float(value), 9)
                elif prop.type in {"BOOLEAN", "INT"}:
                    value = int(value)
                else:
                    value = str(value)
                values.append((prop.identifier, value))
            except (AttributeError, TypeError, ValueError, RuntimeError):
                continue
        signature.append((modifier.type, tuple(values)))
    return tuple(signature)


def _paint_cache_can_ignore_data_updates(obj: bpy.types.Object) -> bool:
    if obj.mode == "WEIGHT_PAINT":
        paint_is_geometry_neutral = not _weight_paint_can_deform_overlay(obj)
    elif obj.mode == "VERTEX_PAINT":
        paint_is_geometry_neutral = not any(
            modifier.show_viewport and modifier.type == "NODES"
            for modifier in obj.modifiers
        )
    elif obj.mode == "TEXTURE_PAINT":
        paint_is_geometry_neutral = True
    else:
        return False
    if not paint_is_geometry_neutral:
        return False
    cached = _overlay_batch_cache.get(obj.as_pointer())
    if cached is None:
        return False
    return cached["modifier_signature"] == _modifier_state_signature(obj)


@persistent
def annotation_depsgraph_update_post(_scene, depsgraph):
    active_obj = getattr(bpy.context, "object", None)
    preserve_paint_cache = bool(
        active_obj
        and active_obj.type == "MESH"
        and _paint_cache_can_ignore_data_updates(active_obj)
    )
    for update in depsgraph.updates:
        if not (update.is_updated_geometry or update.is_updated_transform):
            continue
        update_id = getattr(update.id, "original", update.id)
        if preserve_paint_cache:
            if update_id == active_obj.data:
                # Paint data updates mark Mesh transform/geometry even though
                # neither topology nor positions changed.
                continue
            if update_id == active_obj and not update.is_updated_transform:
                continue
        mark_overlay_cache_dirty(active_obj if active_obj and active_obj.type == "MESH" else None)
        return


def _weight_paint_can_deform_overlay(obj: bpy.types.Object) -> bool:
    weight_driven_types = {"ARMATURE", "HOOK", "LATTICE", "MESH_DEFORM", "SURFACE_DEFORM"}
    for modifier in obj.modifiers:
        if not modifier.show_viewport:
            continue
        if modifier.type in weight_driven_types:
            return True
        if getattr(modifier, "vertex_group", ""):
            return True
    return False


def get_viewport_size():
    context = bpy.context
    region = getattr(context, "region", None)
    if region and region.type == "WINDOW":
        return float(region.width), float(region.height)
    wm = context.window_manager if context else None
    if wm:
        for window in wm.windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for reg in area.regions:
                    if reg.type == "WINDOW":
                        return float(reg.width), float(reg.height)
    return 1920.0, 1080.0


def build_overlay_batches(obj: bpy.types.Object, settings):
    mesh = obj.data
    source_is_edit = obj.mode == "EDIT"
    if source_is_edit:
        bm = bmesh.from_edit_mesh(mesh)
    else:
        bm = bmesh.new()
        bm.from_mesh(mesh)
    try:
        for element_type in ELEMENT_TYPES:
            ensure_lookup_tables(bm, element_type)
        bm.normal_update()
        cache_key = obj.as_pointer()
        topology_counts = (len(bm.verts), len(bm.edges), len(bm.faces))
        sync_stack_mapping = _overlay_topology_counts.get(cache_key) != topology_counts
        _overlay_topology_counts[cache_key] = topology_counts
        results = {etype: [] for etype in ELEMENT_TYPES}
        layer_states = {}
        source_filters = {}
        for element_type in ELEMENT_TYPES:
            collection = get_layer_collection(settings, element_type)
            if not collection:
                continue
            container = element_container(bm, element_type)
            meta = element_spec(element_type)
            if source_is_edit:
                int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
            else:
                int_layer = container.layers.int.get(meta.integer_layer)
                stack_layer = container.layers.string.get(meta.stack_layer)
            mapping = load_element_layers(settings, element_type)
            if stack_layer is not None and sync_stack_mapping:
                mapping_changed = merge_stack_layer_into_mapping(
                    mapping, bm, stack_layer, element_type
                )
                if mapping_changed and settings is not None:
                    save_element_layers(settings, element_type, mapping)
            visible_layers = {layer.layer_id: layer for layer in collection if layer.is_visible}
            if not visible_layers:
                continue
            if getattr(settings, "solo_active", False):
                current = active_layer(settings, element_type)
                if current and current.layer_id in visible_layers:
                    visible_layers = {current.layer_id: current}
                elif current:
                    debug_log(
                        settings,
                        f"Solo active requested but layer {current.layer_id} "
                        f"hidden for {element_type}",
                    )
                    visible_layers = {}
            if not visible_layers:
                continue
            order_lookup = layer_order_map(settings, element_type)
            top_layers = {}
            for index_key, mapped_layers in mapping.items():
                try:
                    element_index = int(index_key)
                except (TypeError, ValueError):
                    continue
                if not (0 <= element_index < len(container)):
                    continue
                layers = normalize_layer_ids(mapped_layers, order_lookup)
                if (
                    not layers
                    and int_layer is not None
                    and container[element_index][int_layer] >= 0
                ):
                    layers = normalize_layer_ids(
                        [container[element_index][int_layer]], order_lookup
                    )
                target = [layer_id for layer_id in layers if layer_id in visible_layers]
                if target:
                    top_layers[element_index] = max(
                        target,
                        key=lambda layer_id: order_lookup.get(layer_id, -1),
                    )
            if top_layers:
                layer_states[element_type] = (container, visible_layers, top_layers)
                source_filters[element_type] = set(top_layers)

        if not layer_states:
            return results

        geometry = evaluated_overlay_geometry(obj, bm, settings, source_filters)
        matrix = obj.matrix_world
        try:
            normal_matrix = matrix.to_3x3().inverted().transposed()
        except ValueError:
            normal_matrix = matrix.to_3x3()
        edge_trim = float(getattr(settings, "overlay_edge_trim", 0.0))
        face_offset = float(getattr(settings, "overlay_face_offset", 0.0001))
        edge_offset = float(getattr(settings, "overlay_edge_offset", 0.0001))
        vertex_offset = float(getattr(settings, "overlay_vertex_offset", 0.0001))
        for element_type, (container, visible_layers, top_layers) in layer_states.items():
            buckets = defaultdict(list)
            if element_type == FACE:
                for source_index, triangles_local, normal_local in geometry[element_type]:
                    if not (0 <= source_index < len(container)):
                        continue
                    source_face = container[source_index]
                    top_layer = top_layers.get(source_index)
                    if top_layer is None:
                        continue
                    normal = (
                        (normal_matrix @ normal_local).normalized()
                        if normal_local.length
                        else Vector((0.0, 0.0, 1.0))
                    )
                    offset = normal * face_offset
                    triangles = [
                        tuple(matrix @ coordinate + offset for coordinate in triangle)
                        for triangle in triangles_local
                    ]
                    bucket_key = (top_layer, source_is_edit and bool(source_face.select))
                    buckets[bucket_key].extend(triangles)
                shader = gpu.shader.from_builtin("UNIFORM_COLOR")
                for (layer_id, selected_flag), triangles in buckets.items():
                    if not triangles:
                        continue
                    flat = [coordinate for triangle in triangles for coordinate in triangle]
                    batch = batch_for_shader(shader, "TRIS", {"pos": flat})
                    results[element_type].append(
                        {
                            "kind": "triangles",
                            "batch": batch,
                            "shader": shader,
                            "color": tuple(visible_layers[layer_id].color),
                            "selected": selected_flag,
                        }
                    )
            elif element_type == EDGE:
                edge_groups = defaultdict(list)
                for (
                    source_index,
                    p0_local,
                    p1_local,
                    normal0_local,
                    normal1_local,
                ) in geometry[element_type]:
                    if not (0 <= source_index < len(container)):
                        continue
                    top_layer = top_layers.get(source_index)
                    if top_layer is None:
                        continue
                    edge_groups[source_index].append(
                        (p0_local, p1_local, normal0_local, normal1_local)
                    )

                for source_index, records in edge_groups.items():
                    source_edge = container[source_index]
                    top_layer = top_layers[source_index]
                    bucket_key = (top_layer, source_is_edit and bool(source_edge.select))
                    for chain in ordered_edge_chains(records):
                        segments = []
                        for p0_local, p1_local, normal0_local, normal1_local in chain:
                            normal0_world = normal_matrix @ normal0_local
                            normal1_world = normal_matrix @ normal1_local
                            if normal0_world.length == 0:
                                normal0_world = Vector((0.0, 0.0, 1.0))
                            if normal1_world.length == 0:
                                normal1_world = Vector((0.0, 0.0, 1.0))
                            normal0_world.normalize()
                            normal1_world.normalize()
                            segments.append(
                                (
                                    matrix @ p0_local + normal0_world * edge_offset,
                                    matrix @ p1_local + normal1_world * edge_offset,
                                )
                            )
                        if edge_trim < 0.0:
                            segments = trim_edge_chain(segments, -edge_trim)
                        buckets[bucket_key].extend(segments)
                shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
                for (layer_id, selected_flag), segments in buckets.items():
                    if not segments:
                        continue
                    flat = [coordinate for segment in segments for coordinate in segment]
                    batch = batch_for_shader(shader, "LINES", {"pos": flat})
                    results[element_type].append(
                        {
                            "kind": "edge_segments",
                            "batch": batch,
                            "shader": shader,
                            "segment_count": len(segments),
                            "color": tuple(visible_layers[layer_id].color),
                            "selected": selected_flag,
                        }
                    )
            else:
                for source_index, coordinate_local, normal_local in geometry[element_type]:
                    if not (0 <= source_index < len(container)):
                        continue
                    source_vertex = container[source_index]
                    top_layer = top_layers.get(source_index)
                    if top_layer is None:
                        continue
                    normal = (
                        (normal_matrix @ normal_local).normalized()
                        if normal_local.length
                        else Vector((0.0, 0.0, 1.0))
                    )
                    coordinate = matrix @ coordinate_local + normal * vertex_offset
                    bucket_key = (top_layer, source_is_edit and bool(source_vertex.select))
                    buckets[bucket_key].append(coordinate)
                shader = gpu.shader.from_builtin("POINT_UNIFORM_COLOR")
                for (layer_id, selected_flag), coordinates in buckets.items():
                    if not coordinates:
                        continue
                    batch = batch_for_shader(shader, "POINTS", {"pos": coordinates})
                    results[element_type].append(
                        {
                            "kind": "points",
                            "batch": batch,
                            "shader": shader,
                            "color": tuple(visible_layers[layer_id].color),
                            "selected": selected_flag,
                        }
                    )
        return results
    finally:
        if not source_is_edit:
            bm.free()


def cached_overlay_batches(obj: bpy.types.Object, settings):
    cache_key = obj.as_pointer()
    mesh_pointer = obj.data.as_pointer()
    source_mode = obj.mode
    modifier_signature = _modifier_state_signature(obj)
    cached = _overlay_batch_cache.get(cache_key)
    cache_matches = bool(
        cached
        and cached["mesh_pointer"] == mesh_pointer
        and cached["source_mode"] == source_mode
        and cached["modifier_signature"] == modifier_signature
    )
    if cache_matches:
        if not cached["dirty"]:
            return cached["batches"]
        interactive_modes = {"EDIT", "SCULPT", "WEIGHT_PAINT", "VERTEX_PAINT"}
        if source_mode in interactive_modes:
            refresh_interval = max(1.0 / 30.0, min(0.2, cached["build_duration"] * 2.0))
            elapsed = time.perf_counter() - cached["built_at"]
            if elapsed < refresh_interval:
                _schedule_overlay_refresh(refresh_interval - elapsed)
                return cached["batches"]
    build_started = time.perf_counter()
    batches = build_overlay_batches(obj, settings)
    build_duration = time.perf_counter() - build_started
    _overlay_batch_cache[cache_key] = {
        "mesh_pointer": mesh_pointer,
        "source_mode": source_mode,
        "modifier_signature": modifier_signature,
        "batches": batches,
        "built_at": time.perf_counter(),
        "build_duration": build_duration,
        "dirty": False,
    }
    return batches


def draw_overlay():
    context = bpy.context
    obj = context.object
    if not obj or obj.type != "MESH":
        return
    settings = getattr(obj, "mesh_annotations", None)
    if not settings or not settings.enable_overlay:
        return
    line_width = max(1.0, float(getattr(settings, "overlay_line_width", 7.0)))
    point_size = max(1.0, float(getattr(settings, "overlay_point_size", 10.0)))
    alpha_mult = max(0.0, min(1.0, float(getattr(settings, "overlay_alpha_multiplier", 0.5))))
    show_backfaces = bool(getattr(settings, "overlay_show_backfaces", False))
    batches = cached_overlay_batches(obj, settings)
    if not any(batches[etype] for etype in ELEMENT_TYPES):
        debug_log(settings, "Draw overlay: nothing to draw")
        return
    depth_mode = "ALWAYS" if show_backfaces else "LESS_EQUAL"
    gpu.state.blend_set("ALPHA")
    current_blend = "ALPHA"
    gpu.state.depth_mask_set(False)
    gpu.state.depth_test_set(depth_mode)
    try:
        viewport_size = get_viewport_size()
        for element_type in ELEMENT_TYPES:
            entries = batches[element_type]
            if not entries:
                continue
            for entry in entries:
                kind = entry.get("kind")
                base_color = entry.get("color", (1.0, 1.0, 1.0, 1.0))
                if len(base_color) < 4:
                    base_color = (*base_color[:3], 1.0)
                color = (
                    base_color[0],
                    base_color[1],
                    base_color[2],
                    base_color[3] * alpha_mult,
                )
                selected_flag = bool(entry.get("selected"))
                if selected_flag:
                    boost = 0.2
                    color = (
                        min(1.0, color[0] + boost),
                        min(1.0, color[1] + boost),
                        min(1.0, color[2] + boost),
                        min(1.0, max(color[3], alpha_mult * 0.85)),
                    )
                    target_blend = "ADDITIVE"
                else:
                    target_blend = "ALPHA"
                if target_blend != current_blend:
                    gpu.state.blend_set(target_blend)
                    current_blend = target_blend
                if kind == "triangles":
                    shader = entry["shader"]
                    batch = entry["batch"]
                    shader.bind()
                    shader.uniform_float("color", color)
                    batch.draw(shader)
                elif kind == "points":
                    shader = entry["shader"]
                    batch = entry["batch"]
                    gpu.state.point_size_set(point_size)
                    shader.bind()
                    shader.uniform_float("color", color)
                    batch.draw(shader)
                    gpu.state.point_size_set(1.0)
                elif kind == "edge_segments":
                    polyline_shader = entry["shader"]
                    polyline_shader.bind()
                    polyline_shader.uniform_float("viewportSize", viewport_size)
                    polyline_shader.uniform_float("lineWidth", line_width)
                    polyline_shader.uniform_float("color", color)
                    entry["batch"].draw(polyline_shader)
    finally:
        if current_blend != "ALPHA":
            gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set("NONE")


def register_draw_handler():
    global _draw_handle
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
            draw_overlay, (), "WINDOW", "POST_VIEW"
        )


def unregister_draw_handler():
    global _draw_handle
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        _draw_handle = None


def register():
    global _overlay_refresh_timer_pending
    invalidate_overlay_cache()
    _overlay_topology_counts.clear()
    if bpy.app.timers.is_registered(_overlay_refresh_timer):
        bpy.app.timers.unregister(_overlay_refresh_timer)
    _overlay_refresh_timer_pending = False
    if annotation_depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(annotation_depsgraph_update_post)
    register_draw_handler()


def unregister():
    global _overlay_refresh_timer_pending
    unregister_draw_handler()
    if annotation_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(annotation_depsgraph_update_post)
    invalidate_overlay_cache()
    _overlay_topology_counts.clear()
    if bpy.app.timers.is_registered(_overlay_refresh_timer):
        bpy.app.timers.unregister(_overlay_refresh_timer)
    _overlay_refresh_timer_pending = False
