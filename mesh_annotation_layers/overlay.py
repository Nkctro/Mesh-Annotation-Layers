"""GPU overlay batching, caching, drawing, and lifecycle."""

import time
from collections import OrderedDict, defaultdict

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
    invalidate_element_layers_cache,
    layer_order_map,
    load_element_layers,
    mark_bmesh_mapping_synchronized,
    merge_stack_layer_into_mapping,
    normalize_layer_ids,
    save_element_layers,
)


_draw_handle = None
_overlay_batch_cache = OrderedDict()
_overlay_geometry_cache = OrderedDict()
_overlay_source_signatures = {}
_overlay_refresh_timer_pending = False
_surface_shader = None
_surface_shader_failed = False
_OVERLAY_CACHE_LIMIT = 8
_OVERLAY_GEOMETRY_VECTOR_LIMIT = 500_000
_OVERLAY_BATCH_VERTEX_LIMIT = 500_000


def _get_surface_shader():
    """Return a local-space surface shader, falling back on unsupported GPUs."""
    global _surface_shader, _surface_shader_failed
    if _surface_shader is not None:
        return _surface_shader
    if _surface_shader_failed:
        return None
    try:
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant("MAT4", "modelViewProjectionMatrix")
        info.push_constant("FLOAT", "surfaceOffset")
        info.push_constant("VEC4", "color")
        info.vertex_in(0, "VEC3", "pos")
        info.vertex_in(1, "VEC3", "offsetDirection")
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(
            """
            void main()
            {
                vec3 offsetPosition = pos + offsetDirection * surfaceOffset;
                gl_Position = modelViewProjectionMatrix * vec4(offsetPosition, 1.0);
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
                FragColor = color;
            }
            """
        )
        _surface_shader = gpu.shader.create_from_info(info)
    except Exception:
        _surface_shader_failed = True
        _surface_shader = None
    return _surface_shader


def invalidate_overlay_cache(obj=None, invalidate_geometry=True):
    if obj is None:
        _overlay_batch_cache.clear()
        if invalidate_geometry:
            _overlay_geometry_cache.clear()
        return
    cache_key = obj.as_pointer()
    _overlay_batch_cache.pop(cache_key, None)
    if invalidate_geometry:
        _overlay_geometry_cache.pop(cache_key, None)


def invalidate_overlay_state():
    """Discard every derived value that may outlive Blender mesh history."""
    invalidate_overlay_cache()
    _overlay_source_signatures.clear()
    invalidate_element_layers_cache()


def mark_overlay_cache_dirty(obj=None, invalidate_geometry=True):
    if obj is not None:
        cache_key = obj.as_pointer()
        cached = _overlay_batch_cache.get(cache_key)
        if cached is not None:
            cached["dirty"] = True
            _overlay_batch_cache.move_to_end(cache_key)
        if invalidate_geometry:
            _overlay_geometry_cache.pop(cache_key, None)
        return
    for cached in _overlay_batch_cache.values():
        cached["dirty"] = True
    if invalidate_geometry:
        _overlay_geometry_cache.clear()


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


def tag_view3d_redraw(
    context=None,
    invalidate_cache=True,
    invalidate_geometry=False,
):
    context = context or bpy.context
    if invalidate_cache:
        context_object = getattr(context, "object", None) if context else None
        invalidate_overlay_cache(
            context_object if context_object and context_object.type == "MESH" else None,
            invalidate_geometry=invalidate_geometry,
        )
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


def tag_surface_offset_redraw(context=None):
    """Update shader uniforms, rebuilding only when the GPU fallback is active."""
    tag_view3d_redraw(
        context,
        invalidate_cache=_surface_shader is None,
        invalidate_geometry=False,
    )


@persistent
def annotation_history_pre(*_args):
    """Never let a batch from the abandoned history state reach the viewport."""
    invalidate_overlay_state()


@persistent
def annotation_history_post(*_args):
    """Force annotation ownership to be read from the restored BMesh layers."""
    invalidate_overlay_state()
    tag_view3d_redraw(invalidate_cache=False)


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


def _dependency_pointers(obj: bpy.types.Object):
    """Collect Blender IDs whose updates may change this object's evaluated surface."""
    pointers = {obj.as_pointer(), obj.data.as_pointer()}
    for modifier in obj.modifiers:
        for prop in modifier.bl_rna.properties:
            if prop.identifier == "rna_type" or prop.type != "POINTER":
                continue
            try:
                value = getattr(modifier, prop.identifier)
            except (AttributeError, ReferenceError, RuntimeError):
                continue
            if value is None or not isinstance(value, bpy.types.ID):
                continue
            try:
                pointers.add(value.as_pointer())
                value_data = getattr(value, "data", None)
                if value_data is not None and hasattr(value_data, "as_pointer"):
                    pointers.add(value_data.as_pointer())
            except (ReferenceError, RuntimeError):
                continue
    return frozenset(pointers)


def _updated_id_pointer(update):
    update_id = getattr(update.id, "original", update.id)
    try:
        return update_id, update_id.as_pointer()
    except (AttributeError, ReferenceError, RuntimeError):
        return update_id, None


def _linear_metric_signature(matrix):
    linear = matrix.to_3x3()
    metric = linear.transposed() @ linear
    return tuple(round(float(value), 9) for row in metric for value in row)


def _paint_mode_is_geometry_neutral(obj: bpy.types.Object) -> bool:
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
    return paint_is_geometry_neutral


def _paint_cache_can_ignore_data_updates(obj: bpy.types.Object) -> bool:
    if not _paint_mode_is_geometry_neutral(obj):
        return False
    cached = _overlay_batch_cache.get(obj.as_pointer())
    if cached is None:
        return False
    return cached["modifier_signature"] == _modifier_state_signature(obj)


@persistent
def annotation_depsgraph_update_post(_scene, depsgraph):
    active_obj = getattr(bpy.context, "object", None)
    active_cache = (
        _overlay_batch_cache.get(active_obj.as_pointer())
        if active_obj and active_obj.type == "MESH"
        else None
    )
    preserve_paint_cache = bool(
        active_obj
        and active_obj.type == "MESH"
        and active_cache is not None
        and _paint_mode_is_geometry_neutral(active_obj)
    )
    modifier_state_matches = None
    relevant_updates = []
    for update in depsgraph.updates:
        if not (update.is_updated_geometry or update.is_updated_transform):
            continue
        update_id, update_pointer = _updated_id_pointer(update)
        if preserve_paint_cache:
            if update_id == active_obj.data:
                # Paint data updates mark Mesh transform/geometry even though
                # neither topology nor positions changed.
                continue
            if update_id == active_obj and not update.is_updated_transform:
                if modifier_state_matches is None:
                    modifier_state_matches = (
                        active_cache["modifier_signature"]
                        == _modifier_state_signature(active_obj)
                    )
                if modifier_state_matches:
                    continue
        if update_pointer is not None:
            relevant_updates.append(
                (
                    update_pointer,
                    bool(update.is_updated_geometry),
                    bool(update.is_updated_transform),
                )
            )
    if not relevant_updates:
        return
    for cache_key, cached in _overlay_batch_cache.items():
        matched_updates = [
            update
            for update in relevant_updates
            if update[0] in cached["dependency_pointers"]
        ]
        if not matched_updates:
            continue
        local_transform_only = (
            len(cached["dependency_pointers"]) <= 2
            and all(
                pointer == cache_key and is_transform and not is_geometry
                for pointer, is_geometry, is_transform in matched_updates
            )
        )
        if local_transform_only and not cached["has_world_space_batches"]:
            continue
        cached["dirty"] = True
        if not local_transform_only:
            _overlay_geometry_cache.pop(cache_key, None)


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


def _source_filters_signature(source_filters):
    return tuple(
        (element_type, tuple(sorted(indices)))
        for element_type, indices in sorted(source_filters.items())
    )


def _local_overlay_geometry(obj, bm, settings, source_filters):
    cache_key = obj.as_pointer()
    signature = (
        obj.data.as_pointer(),
        obj.mode,
        _source_filters_signature(source_filters),
    )
    cached = _overlay_geometry_cache.get(cache_key)
    if cached is not None and cached["signature"] == signature:
        _overlay_geometry_cache.move_to_end(cache_key)
        return cached["geometry"]
    geometry = evaluated_overlay_geometry(obj, bm, settings, source_filters)
    vector_weight = (
        sum(
            1 + sum(len(triangle) for triangle in triangles)
            for _source_index, triangles, _normal in geometry[FACE]
        )
        + len(geometry[EDGE]) * 4
        + len(geometry[VERTEX]) * 2
    )
    if vector_weight > _OVERLAY_GEOMETRY_VECTOR_LIMIT:
        _overlay_geometry_cache.pop(cache_key, None)
        return geometry
    _overlay_geometry_cache[cache_key] = {
        "signature": signature,
        "geometry": geometry,
        "vector_weight": vector_weight,
    }
    _overlay_geometry_cache.move_to_end(cache_key)
    while (
        len(_overlay_geometry_cache) > _OVERLAY_CACHE_LIMIT
        or sum(
            entry["vector_weight"] for entry in _overlay_geometry_cache.values()
        )
        > _OVERLAY_GEOMETRY_VECTOR_LIMIT
    ):
        _overlay_geometry_cache.popitem(last=False)
    return geometry


def _local_offset_direction(normal_local, normal_matrix, inverse_linear):
    if normal_local.length:
        world_normal = normal_matrix @ normal_local
    else:
        world_normal = Vector((0.0, 0.0, 1.0))
    if world_normal.length:
        world_normal.normalize()
    else:
        world_normal = Vector((0.0, 0.0, 1.0))
    if inverse_linear is None:
        return normal_local.normalized() if normal_local.length else world_normal
    return inverse_linear @ world_normal


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
        source_signature = (mesh.as_pointer(), topology_counts)
        sync_stack_mapping = (
            _overlay_source_signatures.get(cache_key) != source_signature
        )
        _overlay_source_signatures[cache_key] = source_signature
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
                mark_bmesh_mapping_synchronized(mesh, bm, element_type)
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
                layers = mapped_layers
                if (
                    not layers
                    and int_layer is not None
                    and container[element_index][int_layer] >= 0
                ):
                    layers = normalize_layer_ids(
                        [container[element_index][int_layer]], order_lookup
                    )
                if len(layers) == 1:
                    candidate = layers[0]
                    top_layer = candidate if candidate in visible_layers else None
                else:
                    target = (
                        layer_id
                        for layer_id in layers
                        if layer_id in visible_layers
                    )
                    top_layer = max(
                        target,
                        key=lambda layer_id: order_lookup.get(layer_id, -1),
                        default=None,
                    )
                if top_layer is not None:
                    top_layers[element_index] = top_layer
            if top_layers:
                layer_states[element_type] = (container, visible_layers, top_layers)
                source_filters[element_type] = set(top_layers)

        if not layer_states:
            return results

        geometry = _local_overlay_geometry(obj, bm, settings, source_filters)
        matrix = obj.matrix_world
        try:
            inverse_linear = matrix.to_3x3().inverted()
            normal_matrix = inverse_linear.transposed()
        except ValueError:
            inverse_linear = None
            normal_matrix = matrix.to_3x3()
        edge_trim = float(getattr(settings, "overlay_edge_trim", 0.0))
        face_offset = float(getattr(settings, "overlay_face_offset", 0.0001))
        edge_offset = float(getattr(settings, "overlay_edge_offset", 0.0001))
        vertex_offset = float(getattr(settings, "overlay_vertex_offset", 0.0001))
        for element_type, (container, visible_layers, top_layers) in layer_states.items():
            buckets = defaultdict(list)
            if element_type == FACE:
                surface_shader = _get_surface_shader()
                direction_buckets = defaultdict(list)
                for source_index, triangles_local, normal_local in geometry[element_type]:
                    if not (0 <= source_index < len(container)):
                        continue
                    top_layer = top_layers.get(source_index)
                    if top_layer is None:
                        continue
                    if surface_shader is not None:
                        offset_direction = _local_offset_direction(
                            normal_local,
                            normal_matrix,
                            inverse_linear,
                        )
                        for triangle in triangles_local:
                            buckets[top_layer].extend(triangle)
                            direction_buckets[top_layer].extend((offset_direction,) * 3)
                    else:
                        normal = (
                            (normal_matrix @ normal_local).normalized()
                            if normal_local.length
                            else Vector((0.0, 0.0, 1.0))
                        )
                        offset = normal * face_offset
                        for triangle in triangles_local:
                            buckets[top_layer].extend(
                                matrix @ coordinate + offset
                                for coordinate in triangle
                            )
                shader = surface_shader or gpu.shader.from_builtin("UNIFORM_COLOR")
                for layer_id, coordinates in buckets.items():
                    if not coordinates:
                        continue
                    attributes = {"pos": coordinates}
                    if surface_shader is not None:
                        attributes["offsetDirection"] = direction_buckets[layer_id]
                    batch = batch_for_shader(shader, "TRIS", attributes)
                    results[element_type].append(
                        {
                            "kind": (
                                "surface_triangles"
                                if surface_shader is not None
                                else "triangles"
                            ),
                            "batch": batch,
                            "shader": shader,
                            "layer_id": layer_id,
                            "vertex_count": len(coordinates),
                            "coordinate_space": (
                                "LOCAL" if surface_shader is not None else "WORLD"
                            ),
                        }
                    )
            elif element_type == EDGE:
                if edge_trim >= 0.0:
                    # The common path does not care about descendant ordering.
                    # Append directly instead of building one tiny graph per edge.
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
                        if edge_offset:
                            offset0 = _local_offset_direction(
                                normal0_local,
                                normal_matrix,
                                inverse_linear,
                            ) * edge_offset
                            offset1 = _local_offset_direction(
                                normal1_local,
                                normal_matrix,
                                inverse_linear,
                            ) * edge_offset
                        else:
                            offset0 = offset1 = Vector((0.0, 0.0, 0.0))
                        buckets[top_layer].extend(
                            (
                                p0_local + offset0,
                                p1_local + offset1,
                            )
                        )
                else:
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
                        if source_index not in top_layers:
                            continue
                        edge_groups[source_index].append(
                            (p0_local, p1_local, normal0_local, normal1_local)
                        )

                    for source_index, records in edge_groups.items():
                        top_layer = top_layers[source_index]
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
                            segments = trim_edge_chain(segments, -edge_trim)
                            buckets[top_layer].extend(
                                coordinate
                                for segment in segments
                                for coordinate in segment
                            )
                shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
                for layer_id, coordinates in buckets.items():
                    if not coordinates:
                        continue
                    batch = batch_for_shader(shader, "LINES", {"pos": coordinates})
                    results[element_type].append(
                        {
                            "kind": "edge_segments",
                            "batch": batch,
                            "shader": shader,
                            "segment_count": len(coordinates) // 2,
                            "layer_id": layer_id,
                            "vertex_count": len(coordinates),
                            "coordinate_space": (
                                "LOCAL" if edge_trim >= 0.0 else "WORLD"
                            ),
                        }
                    )
            else:
                surface_shader = _get_surface_shader()
                direction_buckets = defaultdict(list)
                for source_index, coordinate_local, normal_local in geometry[element_type]:
                    if not (0 <= source_index < len(container)):
                        continue
                    top_layer = top_layers.get(source_index)
                    if top_layer is None:
                        continue
                    if surface_shader is not None:
                        buckets[top_layer].append(coordinate_local)
                        direction_buckets[top_layer].append(
                            _local_offset_direction(
                                normal_local,
                                normal_matrix,
                                inverse_linear,
                            )
                        )
                    else:
                        normal = (
                            (normal_matrix @ normal_local).normalized()
                            if normal_local.length
                            else Vector((0.0, 0.0, 1.0))
                        )
                        coordinate = matrix @ coordinate_local + normal * vertex_offset
                        buckets[top_layer].append(coordinate)
                shader = surface_shader or gpu.shader.from_builtin("POINT_UNIFORM_COLOR")
                for layer_id, coordinates in buckets.items():
                    if not coordinates:
                        continue
                    attributes = {"pos": coordinates}
                    if surface_shader is not None:
                        attributes["offsetDirection"] = direction_buckets[layer_id]
                    batch = batch_for_shader(shader, "POINTS", attributes)
                    results[element_type].append(
                        {
                            "kind": (
                                "surface_points"
                                if surface_shader is not None
                                else "points"
                            ),
                            "batch": batch,
                            "shader": shader,
                            "layer_id": layer_id,
                            "vertex_count": len(coordinates),
                            "coordinate_space": (
                                "LOCAL" if surface_shader is not None else "WORLD"
                            ),
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
    cached = _overlay_batch_cache.get(cache_key)
    cache_matches = bool(
        cached
        and cached["mesh_pointer"] == mesh_pointer
        and cached["source_mode"] == source_mode
    )
    if cache_matches:
        if (
            cached.get("has_local_batches", False)
            and cached.get("linear_metric_signature")
            != _linear_metric_signature(obj.matrix_world)
        ):
            cached["dirty"] = True
        _overlay_batch_cache.move_to_end(cache_key)
        if not cached["dirty"]:
            return cached["batches"]
        interactive_modes = {"EDIT", "SCULPT", "WEIGHT_PAINT", "VERTEX_PAINT"}
        if source_mode in interactive_modes:
            refresh_interval = max(
                1.0 / 30.0,
                min(1.0, cached["build_duration"] * 4.0),
            )
            elapsed = time.perf_counter() - cached["built_at"]
            if elapsed < refresh_interval:
                _schedule_overlay_refresh(refresh_interval - elapsed)
                return cached["batches"]
    modifier_signature = _modifier_state_signature(obj)
    build_started = time.perf_counter()
    batches = build_overlay_batches(obj, settings)
    build_duration = time.perf_counter() - build_started
    batch_vertex_count = (
        sum(
            int(entry.get("vertex_count", 0))
            for entries in batches.values()
            for entry in entries
        )
        if isinstance(batches, dict)
        else 0
    )
    has_world_space_batches = (
        any(
            entry.get("coordinate_space", "WORLD") == "WORLD"
            for entries in batches.values()
            for entry in entries
        )
        if isinstance(batches, dict)
        else True
    )
    has_local_batches = (
        any(
            entry.get("coordinate_space") == "LOCAL"
            for entries in batches.values()
            for entry in entries
        )
        if isinstance(batches, dict)
        else False
    )
    _overlay_batch_cache[cache_key] = {
        "mesh_pointer": mesh_pointer,
        "source_mode": source_mode,
        "modifier_signature": modifier_signature,
        "dependency_pointers": _dependency_pointers(obj),
        "batches": batches,
        "built_at": time.perf_counter(),
        "build_duration": build_duration,
        "batch_vertex_count": batch_vertex_count,
        "has_world_space_batches": has_world_space_batches,
        "has_local_batches": has_local_batches,
        "linear_metric_signature": _linear_metric_signature(obj.matrix_world),
        "dirty": False,
    }
    _overlay_batch_cache.move_to_end(cache_key)
    while (
        len(_overlay_batch_cache) > _OVERLAY_CACHE_LIMIT
        or len(_overlay_batch_cache) > 1
        and sum(
            entry["batch_vertex_count"]
            for entry in _overlay_batch_cache.values()
        )
        > _OVERLAY_BATCH_VERTEX_LIMIT
    ):
        evicted_key, _evicted = _overlay_batch_cache.popitem(last=False)
        _overlay_source_signatures.pop(evicted_key, None)
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
    face_offset = float(getattr(settings, "overlay_face_offset", 0.0001))
    vertex_offset = float(getattr(settings, "overlay_vertex_offset", 0.0001))
    show_backfaces = bool(getattr(settings, "overlay_show_backfaces", False))
    batches = cached_overlay_batches(obj, settings)
    if not any(batches[etype] for etype in ELEMENT_TYPES):
        debug_log(settings, "Draw overlay: nothing to draw")
        return
    depth_mode = "ALWAYS" if show_backfaces else "LESS_EQUAL"
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_mask_set(False)
    gpu.state.depth_test_set(depth_mode)
    try:
        viewport_size = get_viewport_size()
        region_data = getattr(context, "region_data", None)
        view_projection_matrix = (
            region_data.perspective_matrix if region_data is not None else None
        )
        object_matrix = obj.matrix_world
        model_view_projection_matrix = (
            view_projection_matrix @ object_matrix
            if view_projection_matrix is not None
            else None
        )
        for element_type in ELEMENT_TYPES:
            entries = batches[element_type]
            if not entries:
                continue
            layer_colors = {
                layer.layer_id: tuple(layer.color)
                for layer in get_layer_collection(settings, element_type)
            }
            for entry in entries:
                kind = entry.get("kind")
                base_color = layer_colors.get(
                    entry.get("layer_id"),
                    (1.0, 1.0, 1.0, 1.0),
                )
                if len(base_color) < 4:
                    base_color = (*base_color[:3], 1.0)
                color = (
                    base_color[0],
                    base_color[1],
                    base_color[2],
                    base_color[3] * alpha_mult,
                )
                if kind in {"surface_triangles", "surface_points"}:
                    if view_projection_matrix is None:
                        continue
                    shader = entry["shader"]
                    shader.bind()
                    shader.uniform_float(
                        "modelViewProjectionMatrix",
                        model_view_projection_matrix,
                    )
                    shader.uniform_float(
                        "surfaceOffset",
                        face_offset
                        if kind == "surface_triangles"
                        else vertex_offset,
                    )
                    shader.uniform_float("color", color)
                    if kind == "surface_points":
                        gpu.state.point_size_set(point_size)
                    entry["batch"].draw(shader)
                    if kind == "surface_points":
                        gpu.state.point_size_set(1.0)
                elif kind == "triangles":
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
                    uses_local_coordinates = entry.get("coordinate_space") == "LOCAL"
                    if uses_local_coordinates:
                        gpu.matrix.push()
                        gpu.matrix.multiply_matrix(object_matrix)
                    try:
                        polyline_shader.bind()
                        polyline_shader.uniform_float("viewportSize", viewport_size)
                        polyline_shader.uniform_float("lineWidth", line_width)
                        polyline_shader.uniform_float("color", color)
                        entry["batch"].draw(polyline_shader)
                    finally:
                        if uses_local_coordinates:
                            gpu.matrix.pop()
    finally:
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
    global _overlay_refresh_timer_pending, _surface_shader, _surface_shader_failed
    invalidate_overlay_state()
    _surface_shader = None
    _surface_shader_failed = False
    if bpy.app.timers.is_registered(_overlay_refresh_timer):
        bpy.app.timers.unregister(_overlay_refresh_timer)
    _overlay_refresh_timer_pending = False
    if annotation_depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(annotation_depsgraph_update_post)
    for handlers in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        if annotation_history_pre not in handlers:
            handlers.append(annotation_history_pre)
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if annotation_history_post not in handlers:
            handlers.append(annotation_history_post)
    register_draw_handler()


def unregister():
    global _overlay_refresh_timer_pending, _surface_shader, _surface_shader_failed
    unregister_draw_handler()
    if annotation_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(annotation_depsgraph_update_post)
    for handlers in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        if annotation_history_pre in handlers:
            handlers.remove(annotation_history_pre)
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if annotation_history_post in handlers:
            handlers.remove(annotation_history_post)
    invalidate_overlay_state()
    if bpy.app.timers.is_registered(_overlay_refresh_timer):
        bpy.app.timers.unregister(_overlay_refresh_timer)
    _overlay_refresh_timer_pending = False
    _surface_shader = None
    _surface_shader_failed = False
