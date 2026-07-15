"""Annotation layer storage and mesh assignment operations."""

import colorsys
import json
import random
from collections import Counter, OrderedDict

import bmesh
import bpy

from .constants import EDGE, ELEMENT_TYPES, FACE, VERTEX, element_spec


_ELEMENT_LAYERS_CACHE = OrderedDict()
_ELEMENT_LAYERS_CACHE_LIMIT = 96
_ELEMENT_LAYERS_VALUE_LIMIT = 300_000
_BMESH_SYNC_SIGNATURES = OrderedDict()
_BMESH_SYNC_CACHE_LIMIT = 96


def _settings_cache_pointer(settings) -> int:
    try:
        return int(settings.as_pointer())
    except (AttributeError, ReferenceError, TypeError):
        return id(settings)


def _element_layers_cache_key(settings, element_type: str):
    return _settings_cache_pointer(settings), element_type


def _cache_element_layers(settings, element_type: str, data_str: str, mapping):
    key = _element_layers_cache_key(settings, element_type)
    _ELEMENT_LAYERS_CACHE[key] = {
        "data": data_str,
        "mapping": mapping,
        "counts": None,
        "value_count": len(mapping) + sum(len(layers) for layers in mapping.values()),
    }
    _ELEMENT_LAYERS_CACHE.move_to_end(key)
    while (
        len(_ELEMENT_LAYERS_CACHE) > _ELEMENT_LAYERS_CACHE_LIMIT
        or len(_ELEMENT_LAYERS_CACHE) > 1
        and sum(
            entry["value_count"] for entry in _ELEMENT_LAYERS_CACHE.values()
        )
        > _ELEMENT_LAYERS_VALUE_LIMIT
    ):
        _ELEMENT_LAYERS_CACHE.popitem(last=False)
    return mapping


def invalidate_element_layers_cache(settings=None, element_type=None):
    """Discard decoded annotation data without touching Blender-owned properties."""
    if settings is None:
        _ELEMENT_LAYERS_CACHE.clear()
        _BMESH_SYNC_SIGNATURES.clear()
        return
    settings_pointer = _settings_cache_pointer(settings)
    for key in list(_ELEMENT_LAYERS_CACHE):
        if key[0] != settings_pointer:
            continue
        if element_type is None or key[1] == element_type:
            _ELEMENT_LAYERS_CACHE.pop(key, None)


def debug_log(settings, *message):
    if settings and getattr(settings, "debug_output", False):
        print("[MeshAnnotation]", *message)


def get_layer_collection(settings, element_type: str):
    return getattr(settings, element_spec(element_type).collection)


def layer_order_map(settings, element_type: str):
    if not settings:
        return {}
    collection = get_layer_collection(settings, element_type)
    return {layer.layer_id: index for index, layer in enumerate(collection)}


def normalize_layer_ids(layers, order_lookup=None):
    unique = []
    seen = set()
    for lid in layers:
        lid = int(lid)
        if lid in seen:
            continue
        seen.add(lid)
        unique.append(lid)
    if order_lookup:
        unique.sort(key=lambda value: order_lookup.get(value, float("inf")))
    return unique


def apply_layer_order_to_mapping(obj: bpy.types.Object, element_type: str) -> bool:
    settings = getattr(obj, "mesh_annotations", None)
    if settings is None:
        return False
    mapping = load_element_layers(settings, element_type)
    if not mapping:
        return False
    order_lookup = layer_order_map(settings, element_type)
    changed = False
    changed_indices = set()
    for key, layers in list(mapping.items()):
        normalized = normalize_layer_ids(layers, order_lookup)
        if normalized != layers:
            mapping[key] = normalized
            changed = True
            changed_indices.add(int(key))
    if not changed:
        return False
    mesh = obj.data
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
        ensure_lookup_tables(bm, element_type)
        sync_mapping_to_bmesh(
            bm,
            int_layer,
            stack_layer,
            mapping,
            element_type,
            changed_indices,
        )
        mark_bmesh_mapping_synchronized(mesh, bm, element_type)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    else:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
        ensure_lookup_tables(bm, element_type)
        sync_mapping_to_bmesh(
            bm,
            int_layer,
            stack_layer,
            mapping,
            element_type,
            changed_indices,
        )
        mark_bmesh_mapping_synchronized(mesh, bm, element_type)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()
    save_element_layers(settings, element_type, mapping)
    return True


def get_active_index(settings, element_type: str) -> int:
    return getattr(settings, element_spec(element_type).active_index)


def set_active_index(settings, element_type: str, value: int):
    setattr(settings, element_spec(element_type).active_index, value)


def get_next_layer_id(settings, element_type: str) -> int:
    return getattr(settings, element_spec(element_type).next_id)


def increment_next_layer_id(settings, element_type: str):
    attr = element_spec(element_type).next_id
    setattr(settings, attr, getattr(settings, attr) + 1)


def _data_property_name(element_type: str) -> str:
    return element_spec(element_type).data_property


def _color_seed_name(element_type: str) -> str:
    return element_spec(element_type).color_seed


def ensure_lookup_tables(bm: bmesh.types.BMesh, element_type: str):
    if element_type == FACE:
        bm.faces.ensure_lookup_table()
    elif element_type == EDGE:
        bm.edges.ensure_lookup_table()
    else:
        bm.verts.ensure_lookup_table()


def element_container(bm: bmesh.types.BMesh, element_type: str):
    if element_type == FACE:
        return bm.faces
    if element_type == EDGE:
        return bm.edges
    return bm.verts


def load_element_layers(settings, element_type: str):
    if settings is None:
        return {}
    data_str = getattr(settings, _data_property_name(element_type), "")
    if not data_str:
        return _cache_element_layers(settings, element_type, data_str, {})
    cache_key = _element_layers_cache_key(settings, element_type)
    cached = _ELEMENT_LAYERS_CACHE.get(cache_key)
    if cached is not None and cached["data"] == data_str:
        _ELEMENT_LAYERS_CACHE.move_to_end(cache_key)
        return cached["mapping"]
    try:
        raw = json.loads(data_str)
    except (json.JSONDecodeError, TypeError):
        debug_log(settings, f"Ignored invalid {element_type} annotation JSON")
        return _cache_element_layers(settings, element_type, data_str, {})
    if not isinstance(raw, dict):
        debug_log(settings, f"Ignored non-object {element_type} annotation data")
        return _cache_element_layers(settings, element_type, data_str, {})

    mapping = {}
    for raw_index, raw_layers in raw.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if index < 0 or not isinstance(raw_layers, (list, tuple)):
            continue
        if len(raw_layers) == 1:
            try:
                layer_id = int(raw_layers[0])
            except (TypeError, ValueError):
                continue
            if layer_id > 0:
                mapping[str(index)] = [layer_id]
            continue
        layer_ids = []
        seen_layer_ids = set()
        for raw_layer_id in raw_layers:
            try:
                layer_id = int(raw_layer_id)
            except (TypeError, ValueError):
                continue
            if layer_id > 0 and layer_id not in seen_layer_ids:
                seen_layer_ids.add(layer_id)
                layer_ids.append(layer_id)
        if layer_ids:
            mapping[str(index)] = layer_ids
    return _cache_element_layers(settings, element_type, data_str, mapping)


def save_element_layers(settings, element_type: str, mapping):
    if settings is None:
        return
    cleaned = {str(k): [int(v) for v in values] for k, values in mapping.items() if values}
    data_str = json.dumps(cleaned, separators=(",", ":"))
    setattr(settings, _data_property_name(element_type), data_str)
    _cache_element_layers(settings, element_type, data_str, cleaned)


def element_layer_counts(settings, element_type: str):
    """Return cached per-layer usage counts for one annotation element kind."""
    if settings is None:
        return Counter()
    data_str = getattr(settings, _data_property_name(element_type), "")
    cache_key = _element_layers_cache_key(settings, element_type)
    cached = _ELEMENT_LAYERS_CACHE.get(cache_key)
    if cached is None or cached["data"] != data_str:
        load_element_layers(settings, element_type)
        cached = _ELEMENT_LAYERS_CACHE.get(cache_key)
    if cached is None:
        return Counter()
    _ELEMENT_LAYERS_CACHE.move_to_end(cache_key)
    if cached["counts"] is None:
        counts = Counter()
        for layers in cached["mapping"].values():
            counts.update(layers)
        cached["counts"] = counts
    return cached["counts"]


def get_layers_for_index(mapping, element_index: int):
    return list(mapping.get(str(element_index), []))


def set_layers_for_index(mapping, element_index: int, layers):
    key = str(element_index)
    if layers:
        mapping[key] = [int(v) for v in layers]
    elif key in mapping:
        del mapping[key]


def prune_mapping_to_indices(mapping, valid_indices):
    removed = False
    valid = set(valid_indices)
    for key in list(mapping.keys()):
        if int(key) not in valid:
            del mapping[key]
            removed = True
    return removed


def prune_mapping_to_index_count(mapping, element_count: int):
    """Fast path for Blender element sequences whose indices are contiguous."""
    removed = False
    for key in list(mapping):
        try:
            index = int(key)
        except (TypeError, ValueError):
            index = -1
        if not (0 <= index < element_count):
            del mapping[key]
            removed = True
    return removed


def ensure_annotation_layers(bm: bmesh.types.BMesh, element_type: str):
    container = element_container(bm, element_type)
    meta = element_spec(element_type)
    layer_name = meta.integer_layer
    stack_name = meta.stack_layer
    int_layer = container.layers.int.get(layer_name)
    if int_layer is None:
        int_layer = container.layers.int.new(layer_name)
        for elem in container:
            elem[int_layer] = -1
    stack_layer = container.layers.string.get(stack_name)
    if stack_layer is None:
        stack_layer = container.layers.string.new(stack_name)
        for elem in container:
            elem[stack_layer] = b""
    return int_layer, stack_layer


def decode_layer_bytes(data):
    if isinstance(data, bytes):
        data = data.decode("utf-8", "ignore")
    if not data:
        return []
    return [int(v) for v in data.split(",") if v.strip().isdigit()]


def encode_layers(layers):
    if not layers:
        return b""
    parts = [str(v) for v in layers]
    if not parts:
        return b""
    accepted = []
    size = 0
    for part in parts:
        token = ("," if accepted else "") + part
        token_bytes = token.encode("utf-8")
        if size + len(token_bytes) > 255:
            break
        accepted.append(part)
        size += len(token_bytes)
    if not accepted:
        return b""
    return ",".join(accepted).encode("utf-8")


def merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type: str):
    container = element_container(bm, element_type)
    changed = False
    for elem in container:
        data = elem[stack_layer]
        key = str(elem.index)
        layers = decode_layer_bytes(data)
        if layers:
            if mapping.get(key) != layers:
                mapping[key] = layers
                changed = True
        elif key in mapping:
            del mapping[key]
            changed = True
    return changed


def _bmesh_sync_key(mesh, element_type: str):
    return mesh.as_pointer(), element_type


def _bmesh_topology_signature(bm):
    return len(bm.verts), len(bm.edges), len(bm.faces)


def mark_bmesh_mapping_synchronized(mesh, bm, element_type: str):
    key = _bmesh_sync_key(mesh, element_type)
    _BMESH_SYNC_SIGNATURES[key] = _bmesh_topology_signature(bm)
    _BMESH_SYNC_SIGNATURES.move_to_end(key)
    while len(_BMESH_SYNC_SIGNATURES) > _BMESH_SYNC_CACHE_LIMIT:
        _BMESH_SYNC_SIGNATURES.popitem(last=False)


def merge_stack_layer_if_needed(mapping, mesh, bm, stack_layer, element_type: str):
    """Reconcile durable JSON only after load, history, or topology-size changes."""
    key = _bmesh_sync_key(mesh, element_type)
    signature = _bmesh_topology_signature(bm)
    if _BMESH_SYNC_SIGNATURES.get(key) == signature:
        _BMESH_SYNC_SIGNATURES.move_to_end(key)
        return False
    changed = merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type)
    mark_bmesh_mapping_synchronized(mesh, bm, element_type)
    return changed


def sync_mapping_to_bmesh(
    bm, int_layer, stack_layer, mapping, element_type: str, element_indices=None
):
    container = element_container(bm, element_type)
    if element_indices is None:
        elements = container
    else:
        elements = (
            container[index]
            for index in element_indices
            if 0 <= index < len(container)
        )
    for elem in elements:
        layers = mapping.get(str(elem.index), [])
        elem[int_layer] = layers[-1] if layers else -1
        elem[stack_layer] = encode_layers(layers)


def auto_generate_color(settings, element_type: str, existing_colors=None):
    seed_attr = _color_seed_name(element_type)
    setattr(settings, seed_attr, random.random())
    if existing_colors is None:
        collection = get_layer_collection(settings, element_type) if settings else []
        existing_colors = [tuple(layer.color[:3]) for layer in collection]
    best_color = None
    best_score = -1.0
    for _ in range(16):
        hue = random.random()
        saturation = 0.65
        value = 1.0
        candidate = colorsys.hsv_to_rgb(hue, saturation, value)
        if not existing_colors:
            best_color = candidate
            break
        score = min(
            (
                (candidate[0] - col[0]) ** 2
                + (candidate[1] - col[1]) ** 2
                + (candidate[2] - col[2]) ** 2
            )
            ** 0.5
            for col in existing_colors
        )
        if score > best_score:
            best_score = score
            best_color = candidate
    if best_color is None:
        best_color = colorsys.hsv_to_rgb(random.random(), 0.65, 1.0)
    r, g, b = best_color
    alpha = 0.45 if element_type == FACE else 1.0
    return (r, g, b, alpha)


def get_mesh_sequence(obj, element_type: str):
    if element_type == FACE:
        return obj.data.polygons
    if element_type == EDGE:
        return obj.data.edges
    return obj.data.vertices


def assign_elements_to_layer(
    obj: bpy.types.Object, element_type: str, layer_id: int, element_indices=None
):
    mesh = obj.data
    settings = getattr(obj, "mesh_annotations", None)
    mapping = load_element_layers(settings, element_type)
    debug_log(
        settings,
        f"Assign elements start: type={element_type}, "
        f"layer_id={layer_id}, indices={element_indices}",
    )
    order_lookup = layer_order_map(settings, element_type)
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
        ensure_lookup_tables(bm, element_type)
        container = element_container(bm, element_type)
        if prune_mapping_to_index_count(mapping, len(container)):
            save_element_layers(settings, element_type, mapping)
        merge_stack_layer_if_needed(mapping, mesh, bm, stack_layer, element_type)
        if element_indices is None:
            targets = [elem for elem in container if elem.select]
        else:
            targets = [container[i] for i in element_indices if 0 <= i < len(container)]
        if not targets:
            debug_log(settings, "Assign aborted: no selection in edit mode")
            return False
        for elem in targets:
            idx = elem.index
            layers = normalize_layer_ids(get_layers_for_index(mapping, idx), order_lookup)
            if layer_id in layers:
                layers.remove(layer_id)
            layers.append(layer_id)
            layers = normalize_layer_ids(layers, order_lookup)
            set_layers_for_index(mapping, idx, layers)
        sync_mapping_to_bmesh(
            bm,
            int_layer,
            stack_layer,
            mapping,
            element_type,
            {elem.index for elem in targets},
        )
        mark_bmesh_mapping_synchronized(mesh, bm, element_type)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        save_element_layers(settings, element_type, mapping)
        debug_log(settings, f"Assign edit success: {len(targets)} elements")
        return True
    bm = bmesh.new()
    bm.from_mesh(mesh)
    int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    element_count = len(container)
    if prune_mapping_to_index_count(mapping, element_count):
        save_element_layers(settings, element_type, mapping)
    merge_stack_layer_if_needed(mapping, mesh, bm, stack_layer, element_type)
    if element_indices is None:
        element_indices = range(element_count)
    element_indices = [idx for idx in element_indices if 0 <= idx < element_count]
    if not element_indices:
        bm.free()
        debug_log(settings, "Assign aborted: no indices in object mode")
        return False
    for idx in element_indices:
        layers = normalize_layer_ids(get_layers_for_index(mapping, idx), order_lookup)
        if layer_id in layers:
            layers.remove(layer_id)
        layers.append(layer_id)
        layers = normalize_layer_ids(layers, order_lookup)
        set_layers_for_index(mapping, idx, layers)
    sync_mapping_to_bmesh(
        bm,
        int_layer,
        stack_layer,
        mapping,
        element_type,
        element_indices,
    )
    mark_bmesh_mapping_synchronized(mesh, bm, element_type)
    bm.to_mesh(mesh)
    mesh.update()
    save_element_layers(settings, element_type, mapping)
    bm.free()
    debug_log(settings, f"Assign object success: {len(element_indices)} elements")
    return True


def clear_elements_from_layer(
    obj: bpy.types.Object,
    element_type: str,
    layer_id: int,
    only_selected: bool,
    mode: str = "ALL",
):
    mesh = obj.data
    settings = getattr(obj, "mesh_annotations", None)
    mapping = load_element_layers(settings, element_type)
    order_lookup = layer_order_map(settings, element_type)
    debug_log(
        settings,
        f"Clear elements: type={element_type}, layer_id={layer_id}, "
        f"only_selected={only_selected}, mode={mode}",
    )
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
        ensure_lookup_tables(bm, element_type)
        container = element_container(bm, element_type)
        if prune_mapping_to_index_count(mapping, len(container)):
            save_element_layers(settings, element_type, mapping)
        mapping_changed = merge_stack_layer_if_needed(
            mapping, mesh, bm, stack_layer, element_type
        )
        targets = container if not only_selected else [elem for elem in container if elem.select]
        assignment_changed = False
        changed_indices = set()
        for elem in targets:
            idx = elem.index
            layers = normalize_layer_ids(get_layers_for_index(mapping, idx), order_lookup)
            original_layers = tuple(layers)
            if layer_id == -1:
                if mode == "TOP":
                    if layers:
                        layers = layers[:-1]
                        assignment_changed = True
                else:
                    if layers:
                        layers = []
                        assignment_changed = True
            elif layer_id in layers:
                new_layers = [l for l in layers if l != layer_id]
                if new_layers != layers:
                    layers = new_layers
                    assignment_changed = True
            if mode == "TOP" and layer_id != -1:
                # remove first occurrence matching layer_id only once
                if layer_id in layers:
                    layers.remove(layer_id)
                    assignment_changed = True
            layers = normalize_layer_ids(layers, order_lookup)
            set_layers_for_index(mapping, idx, layers)
            if tuple(layers) != original_layers:
                changed_indices.add(idx)
        if assignment_changed:
            sync_mapping_to_bmesh(
                bm,
                int_layer,
                stack_layer,
                mapping,
                element_type,
                changed_indices,
            )
            mark_bmesh_mapping_synchronized(mesh, bm, element_type)
        if mapping_changed or assignment_changed:
            save_element_layers(settings, element_type, mapping)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        debug_log(
            settings,
            f"Clear edit processed {len(targets)} elements "
            f"(changed={assignment_changed or mapping_changed})",
        )
        return
    bm = bmesh.new()
    bm.from_mesh(mesh)
    int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    if prune_mapping_to_index_count(mapping, len(container)):
        save_element_layers(settings, element_type, mapping)
    mapping_changed = merge_stack_layer_if_needed(
        mapping, mesh, bm, stack_layer, element_type
    )
    assignment_changed = False
    changed_indices = set()
    for elem in container:
        idx = elem.index
        layers = normalize_layer_ids(get_layers_for_index(mapping, idx), order_lookup)
        original_layers = tuple(layers)
        if layer_id == -1:
            if mode == "TOP":
                if layers:
                    layers = layers[:-1]
                    assignment_changed = True
            else:
                if layers:
                    layers = []
                    assignment_changed = True
        elif layer_id in layers:
            new_layers = [l for l in layers if l != layer_id]
            if new_layers != layers:
                layers = new_layers
                assignment_changed = True
        if mode == "TOP" and layer_id != -1 and layer_id in layers:
            layers.remove(layer_id)
            assignment_changed = True
        layers = normalize_layer_ids(layers, order_lookup)
        set_layers_for_index(mapping, idx, layers)
        if tuple(layers) != original_layers:
            changed_indices.add(idx)
    if assignment_changed:
        sync_mapping_to_bmesh(
            bm,
            int_layer,
            stack_layer,
            mapping,
            element_type,
            changed_indices,
        )
        mark_bmesh_mapping_synchronized(mesh, bm, element_type)
        bm.to_mesh(mesh)
        mesh.update()
    if mapping_changed or assignment_changed:
        save_element_layers(settings, element_type, mapping)
    bm.free()
    debug_log(
        settings,
        f"Clear object complete for layer {layer_id} "
        f"(changed={assignment_changed or mapping_changed})",
    )


def count_elements_for_layer(obj: bpy.types.Object, element_type: str, layer_id: int) -> int:
    if layer_id is None:
        return 0
    settings = getattr(obj, "mesh_annotations", None)
    return int(element_layer_counts(settings, element_type).get(layer_id, 0))


def collect_element_indices_for_layer(obj: bpy.types.Object, element_type: str, layer_id: int):
    settings = getattr(obj, "mesh_annotations", None)
    mapping = load_element_layers(settings, element_type)
    sequence = get_mesh_sequence(obj, element_type)
    element_count = len(sequence)
    return [
        int(idx)
        for idx, layers in mapping.items()
        if 0 <= int(idx) < element_count and layer_id in layers
    ]


def select_elements_for_layer(obj: bpy.types.Object, element_type: str, layer_id: int) -> int:
    if obj.mode != "EDIT":
        return 0
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    settings = obj.mesh_annotations
    mapping = load_element_layers(settings, element_type)
    mapping_changed = merge_stack_layer_if_needed(
        mapping, mesh, bm, stack_layer, element_type
    )
    if mapping_changed and settings is not None:
        save_element_layers(settings, element_type, mapping)
    target_indices = {int(idx) for idx, layers in mapping.items() if layer_id in layers}
    selected = 0
    for elem in container:
        is_in_layer = elem.index in target_indices
        elem.select = is_in_layer
        if is_in_layer:
            selected += 1
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    debug_log(settings, f"Select elements: type={element_type}, count={selected}")
    return selected


def mark_face_layer_edges_as_seam(obj: bpy.types.Object, layer_ids) -> int:
    if obj.mode != "EDIT":
        return 0
    mesh = obj.data
    settings = getattr(obj, "mesh_annotations", None)
    if settings is None:
        return 0
    target_layers = {int(lid) for lid in layer_ids if lid is not None}
    if not target_layers:
        return 0
    bm = bmesh.from_edit_mesh(mesh)
    int_layer, stack_layer = ensure_annotation_layers(bm, FACE)
    ensure_lookup_tables(bm, FACE)
    ensure_lookup_tables(bm, EDGE)
    mapping = load_element_layers(settings, FACE)
    mapping_changed = merge_stack_layer_if_needed(mapping, mesh, bm, stack_layer, FACE)
    if mapping_changed:
        save_element_layers(settings, FACE, mapping)
    layer_faces_map = {layer_id: set() for layer_id in target_layers}
    for raw_index, layers in mapping.items():
        face_index = int(raw_index)
        if not (0 <= face_index < len(bm.faces)):
            continue
        for layer_id in target_layers.intersection(layers):
            layer_faces_map[layer_id].add(face_index)
    missing_legacy_layers = {
        layer_id
        for layer_id, face_indices in layer_faces_map.items()
        if not face_indices
    }
    if missing_legacy_layers:
        for face in bm.faces:
            layer_id = face[int_layer]
            if layer_id in missing_legacy_layers:
                layer_faces_map[layer_id].add(face.index)
    edges_to_mark = set()
    for layer_faces in layer_faces_map.values():
        if not layer_faces:
            continue
        for face_index in layer_faces:
            face = bm.faces[face_index]
            for edge in face.edges:
                adjacent = {link_face.index for link_face in edge.link_faces}
                if len(adjacent) < 2:
                    edges_to_mark.add(edge)
                    continue
                if any(idx not in layer_faces for idx in adjacent):
                    edges_to_mark.add(edge)
    changed = 0
    for edge in edges_to_mark:
        if not edge.seam:
            edge.seam = True
            changed += 1
    if changed:
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    return changed


def get_layer_by_id(settings, element_type: str, layer_id: int):
    collection = get_layer_collection(settings, element_type)
    for layer in collection:
        if layer.layer_id == layer_id:
            return layer
    return None


def active_layer(settings, element_type: str):
    collection = get_layer_collection(settings, element_type)
    idx = get_active_index(settings, element_type)
    if 0 <= idx < len(collection):
        return collection[idx]
    return None


def create_layer(settings, element_type: str, name=None, color=None):
    collection = get_layer_collection(settings, element_type)
    meta = element_spec(element_type)
    existing_colors = [tuple(layer.color[:3]) for layer in collection]
    generated_color = color or auto_generate_color(
        settings, element_type, existing_colors=existing_colors
    )
    layer = collection.add()
    layer.element_type = element_type
    layer.layer_id = get_next_layer_id(settings, element_type)
    increment_next_layer_id(settings, element_type)
    layer.name = name or f"{meta.default_name} {layer.layer_id}"
    layer.color = generated_color
    set_active_index(settings, element_type, len(collection) - 1)
    return layer


def remove_layer(settings, obj, element_type: str, index: int):
    collection = get_layer_collection(settings, element_type)
    if not (0 <= index < len(collection)):
        return
    layer = collection[index]
    clear_elements_from_layer(obj, element_type, layer.layer_id, only_selected=False, mode="ALL")
    collection.remove(index)
    new_index = min(index, len(collection) - 1)
    set_active_index(settings, element_type, new_index)


def collect_layer_usage_from_selection(obj, element_type: str):
    if obj.mode != "EDIT":
        return Counter()
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    settings = obj.mesh_annotations
    _int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
    ensure_lookup_tables(bm, element_type)
    mapping = load_element_layers(settings, element_type)
    mapping_changed = merge_stack_layer_if_needed(
        mapping, mesh, bm, stack_layer, element_type
    )
    if mapping_changed and settings is not None:
        save_element_layers(settings, element_type, mapping)
    container = element_container(bm, element_type)
    usage = Counter()
    order_lookup = layer_order_map(settings, element_type)
    for elem in container:
        if elem.select:
            for lid in normalize_layer_ids(get_layers_for_index(mapping, elem.index), order_lookup):
                usage[lid] += 1
    return usage


def infer_element_type_from_mode(context) -> str:
    try:
        mode = context.tool_settings.mesh_select_mode
    except AttributeError:
        mode = (False, False, False)
    for element_type, index in sorted(
        ((etype, element_spec(etype).select_mode_index) for etype in ELEMENT_TYPES),
        key=lambda item: item[1],
        reverse=True,
    ):
        if index < len(mode) and mode[index]:
            return element_type
    return FACE
