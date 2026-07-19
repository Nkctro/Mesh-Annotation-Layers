"""Annotation layer storage and mesh assignment operations."""

import colorsys
import hashlib
import json
import random
import struct
import time
import zlib
from collections import Counter, OrderedDict
from typing import NamedTuple

import bmesh
import bpy

from .constants import EDGE, ELEMENT_TYPES, FACE, VERTEX, element_spec


_ELEMENT_LAYERS_CACHE = OrderedDict()
_ELEMENT_LAYERS_CACHE_LIMIT = 96
_ELEMENT_LAYERS_VALUE_LIMIT = 300_000
_BMESH_SYNC_STATES = OrderedDict()
_BMESH_SYNC_CACHE_LIMIT = 96
_BMESH_SYNC_DIRTY_AT = {}
_BMESH_SYNC_QUIET_SECONDS = 0.15

_STACK_MAGIC = b"\x00MAL"
_STACK_VERSION = 1
_STACK_MAX_BYTES = 255
_LAYER_ID_MAX = 0x7FFFFFFF


class SharedMeshAnnotationError(RuntimeError):
    """Raised when object-local annotations would write shared mesh data."""


class StaleSharedAnnotationError(RuntimeError):
    """Raised when a shared Mesh no longer matches an Object-local mapping."""


class StackEncodingError(ValueError):
    """Raised when annotation ownership cannot be stored losslessly."""


class StackCapacityError(StackEncodingError):
    """Raised before a BMesh string layer could truncate annotation data."""


class StackMergeResult(NamedTuple):
    changed: bool
    complete: bool
    inspected: bool


def _settings_cache_pointer(settings) -> int:
    try:
        return int(settings.as_pointer())
    except (AttributeError, ReferenceError, TypeError):
        return id(settings)


def _element_layers_cache_key(settings, element_type: str):
    return _settings_cache_pointer(settings), element_type


def _cache_element_layers(
    settings, element_type: str, data_str: str, mapping, *, valid=True
):
    key = _element_layers_cache_key(settings, element_type)
    _ELEMENT_LAYERS_CACHE[key] = {
        "data": data_str,
        "mapping": mapping,
        "valid": bool(valid),
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
        _BMESH_SYNC_STATES.clear()
        _BMESH_SYNC_DIRTY_AT.clear()
        return
    settings_pointer = _settings_cache_pointer(settings)
    for key in list(_ELEMENT_LAYERS_CACHE):
        if key[0] != settings_pointer:
            continue
        if element_type is None or key[1] == element_type:
            _ELEMENT_LAYERS_CACHE.pop(key, None)


def debug_log(settings, *message):
    if settings and settings.debug_output:
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


def _object_bmesh(obj):
    mesh = obj.data
    if obj.mode == "EDIT":
        return mesh, bmesh.from_edit_mesh(mesh), True
    bm = bmesh.new()
    bm.from_mesh(mesh)
    return mesh, bm, False


def apply_layer_order_to_mapping(obj: bpy.types.Object, element_type: str) -> bool:
    ensure_annotation_mesh_editable(obj)
    settings = getattr(obj, "mesh_annotations", None)
    if settings is None:
        return False
    mapping = copy_element_layers(load_element_layers(settings, element_type))
    mesh, bm, source_is_edit = _object_bmesh(obj)
    try:
        ensure_lookup_tables(bm, element_type)
        container = element_container(bm, element_type)
        storage_changed = prune_mapping_to_index_count(mapping, len(container))
        stack_layer = container.layers.string.get(
            element_spec(element_type).stack_layer
        )
        mapping, merge_result = _reconcile_existing_stack(
            mapping, mesh, bm, stack_layer, element_type
        )
        storage_changed |= merge_result.changed

        order_lookup = layer_order_map(settings, element_type)
        changed_indices = set()
        for key, layers in list(mapping.items()):
            normalized = normalize_layer_ids(layers, order_lookup)
            if normalized != layers:
                mapping[key] = normalized
                changed_indices.add(int(key))
        if stack_layer is None and mapping:
            changed_indices.update(int(key) for key in mapping)
        prepared_mapping, data_str = prepare_element_layers(mapping)
        mapping = prepared_mapping
        if changed_indices:
            stack_layer, stack_created = ensure_annotation_stack(
                bm, element_type, mapping
            )
            commit_mapping_transaction(
                settings,
                element_type,
                mesh,
                bm,
                stack_layer,
                stack_created,
                mapping,
                data_str,
                changed_indices,
                source_is_edit=source_is_edit,
                complete_state=stack_created or merge_result.complete,
            )
        else:
            _finalize_reconciled_mapping(
                settings,
                element_type,
                mesh,
                bm,
                mapping,
                data_str,
                merge_result,
                storage_changed,
            )
        return bool(changed_indices)
    finally:
        if not source_is_edit:
            bm.free()


def get_active_index(settings, element_type: str) -> int:
    return getattr(settings, element_spec(element_type).active_index)


def set_active_index(settings, element_type: str, value: int):
    setattr(settings, element_spec(element_type).active_index, value)


def get_next_layer_id(settings, element_type: str) -> int:
    return getattr(settings, element_spec(element_type).next_id)


def _data_property_name(element_type: str) -> str:
    return element_spec(element_type).data_property


def ensure_lookup_tables(bm: bmesh.types.BMesh, element_type: str):
    if element_type == FACE:
        bm.faces.ensure_lookup_table()
    elif element_type == EDGE:
        bm.edges.ensure_lookup_table()
    elif element_type == VERTEX:
        bm.verts.ensure_lookup_table()
    else:
        raise ValueError(f"Unsupported mesh element type: {element_type!r}")


def element_container(bm: bmesh.types.BMesh, element_type: str):
    if element_type == FACE:
        return bm.faces
    if element_type == EDGE:
        return bm.edges
    if element_type == VERTEX:
        return bm.verts
    raise ValueError(f"Unsupported mesh element type: {element_type!r}")


def _stored_layer_id(raw_value) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, str)):
        raise ValueError("Layer IDs must be integers")
    layer_id = int(raw_value)
    if not (0 < layer_id <= _LAYER_ID_MAX):
        raise ValueError("Layer ID is out of range")
    return layer_id


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
        return _cache_element_layers(
            settings, element_type, data_str, {}, valid=False
        )
    if not isinstance(raw, dict):
        debug_log(settings, f"Ignored non-object {element_type} annotation data")
        return _cache_element_layers(
            settings, element_type, data_str, {}, valid=False
        )

    mapping = {}
    valid = True
    for raw_index, raw_layers in raw.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            valid = False
            continue
        if (
            index < 0
            or str(raw_index) != str(index)
            or not isinstance(raw_layers, list)
            or not raw_layers
        ):
            valid = False
            continue
        if len(raw_layers) == 1:
            try:
                layer_id = _stored_layer_id(raw_layers[0])
            except (TypeError, ValueError):
                valid = False
                continue
            mapping[str(index)] = [layer_id]
            continue
        layer_ids = []
        seen_layer_ids = set()
        for raw_layer_id in raw_layers:
            try:
                layer_id = _stored_layer_id(raw_layer_id)
            except (TypeError, ValueError):
                valid = False
                continue
            if layer_id in seen_layer_ids:
                valid = False
                continue
            seen_layer_ids.add(layer_id)
            layer_ids.append(layer_id)
        if layer_ids:
            mapping[str(index)] = layer_ids
        else:
            valid = False
    return _cache_element_layers(
        settings, element_type, data_str, mapping, valid=valid
    )


def element_layers_data_is_valid(settings, element_type: str) -> bool:
    """Return whether durable JSON was decoded without dropping any content."""

    if settings is None:
        return True
    data_str = getattr(settings, _data_property_name(element_type), "")
    cache_key = _element_layers_cache_key(settings, element_type)
    cached = _ELEMENT_LAYERS_CACHE.get(cache_key)
    if cached is None or cached["data"] != data_str:
        load_element_layers(settings, element_type)
        cached = _ELEMENT_LAYERS_CACHE.get(cache_key)
    return bool(cached is not None and cached["valid"])


def copy_element_layers(mapping):
    """Return a private mapping that can be reconciled transactionally."""

    return {str(key): list(layers) for key, layers in mapping.items()}


def prepare_element_layers(mapping):
    """Validate and serialize a complete mapping without changing Blender data."""

    cleaned = {}
    for raw_index, values in mapping.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise StackEncodingError("Invalid annotation element index") from exc
        if index < 0:
            raise StackEncodingError("Annotation element indices must be non-negative")
        normalized = normalize_layer_ids(values)
        if normalized:
            encode_layers(normalized)
            cleaned[str(index)] = normalized
    data_str = json.dumps(cleaned, separators=(",", ":"))
    return cleaned, data_str


def commit_prepared_element_layers(
    settings, element_type: str, cleaned, data_str: str
):
    """Commit data returned by :func:`prepare_element_layers`."""

    owner = getattr(settings, "id_data", None)
    if isinstance(owner, bpy.types.Object) and owner.type == "MESH":
        ensure_annotation_mesh_editable(owner)
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


def _encode_uvarint(value: int) -> bytes:
    if not (0 <= value <= _LAYER_ID_MAX):
        raise StackEncodingError(f"Invalid annotation layer id: {value!r}")
    encoded = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        encoded.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(encoded)


def _decode_uvarint(data: bytes, offset: int, limit: int):
    value = 0
    shift = 0
    while offset < limit and shift <= 28:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            if value > _LAYER_ID_MAX:
                raise StackEncodingError("Annotation layer id is out of range")
            return value, offset
        shift += 7
    raise StackEncodingError("Truncated annotation stack integer")


def encode_layers(layers):
    """Encode every layer id or fail before Blender's 255-byte truncation."""

    normalized = []
    seen = set()
    for raw_layer_id in layers:
        layer_id = int(raw_layer_id)
        if layer_id <= 0:
            raise StackEncodingError("Annotation layer ids must be positive")
        if layer_id not in seen:
            seen.add(layer_id)
            normalized.append(layer_id)
    if not normalized:
        return b""
    payload = bytearray(_STACK_MAGIC)
    payload.append(_STACK_VERSION)
    payload.extend(_encode_uvarint(len(normalized)))
    for layer_id in normalized:
        payload.extend(_encode_uvarint(layer_id))
    payload.extend(zlib.crc32(payload).to_bytes(4, "little"))
    if len(payload) > _STACK_MAX_BYTES:
        raise StackCapacityError(
            "Too many overlapping annotation layers for one mesh element"
        )
    return bytes(payload)


def _decode_stack_payload(data):
    if not data:
        return [], "EMPTY"
    if not isinstance(data, bytes):
        data = bytes(data)
    if not data.startswith(_STACK_MAGIC):
        try:
            text = data.decode("ascii")
            values = [int(token.strip()) for token in text.split(",") if token.strip()]
        except (UnicodeDecodeError, ValueError) as exc:
            raise StackEncodingError("Invalid legacy annotation stack") from exc
        if any(value <= 0 for value in values) or len(values) != len(set(values)):
            raise StackEncodingError("Invalid legacy annotation layer ids")
        return values, "LEGACY"
    minimum_size = len(_STACK_MAGIC) + 1 + 1 + 4
    if len(data) < minimum_size:
        raise StackEncodingError("Truncated annotation stack header")
    version_offset = len(_STACK_MAGIC)
    if data[version_offset] != _STACK_VERSION:
        raise StackEncodingError("Unsupported annotation stack version")
    checksum_offset = len(data) - 4
    expected_checksum = int.from_bytes(data[checksum_offset:], "little")
    if zlib.crc32(data[:checksum_offset]) != expected_checksum:
        raise StackEncodingError("Annotation stack checksum mismatch")
    offset = version_offset + 1
    count, offset = _decode_uvarint(data, offset, checksum_offset)
    values = []
    for _index in range(count):
        value, offset = _decode_uvarint(data, offset, checksum_offset)
        if value <= 0 or value in values:
            raise StackEncodingError("Invalid annotation layer id sequence")
        values.append(value)
    if offset != checksum_offset:
        raise StackEncodingError("Unexpected bytes in annotation stack")
    return values, "BINARY"


def decode_layer_bytes(data):
    """Decode a complete stack; malformed or truncated data is never partial."""

    return _decode_stack_payload(data)[0]


def _legacy_prefix(layers):
    accepted = []
    size = 0
    for layer_id in layers:
        token = ("," if accepted else "") + str(int(layer_id))
        token_size = len(token.encode("ascii"))
        if size + token_size > _STACK_MAX_BYTES:
            break
        accepted.append(int(layer_id))
        size += token_size
    return accepted


def ensure_annotation_stack(
    bm: bmesh.types.BMesh,
    element_type: str,
    initial_mapping=None,
    *,
    rebuild=False,
):
    """Create storage without ever replacing durable JSON with an empty stack."""

    if rebuild and initial_mapping is None:
        raise ValueError("Rebuilding annotation storage requires durable JSON")
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    container.index_update()
    meta = element_spec(element_type)
    stack_layer = container.layers.string.get(meta.stack_layer)
    stack_created = stack_layer is None

    stack_values = []
    if rebuild and not stack_created:
        for elem in container:
            layers = list(initial_mapping.get(str(elem.index), ()))
            stack_values.append((elem.index, encode_layers(layers)))
    elif stack_created and initial_mapping:
        for raw_index, layers in initial_mapping.items():
            index = int(raw_index)
            if 0 <= index < len(container):
                payload = encode_layers(layers)
                if payload:
                    stack_values.append((index, payload))

    # BMesh layer creation itself is a mutation, so it happens only after all
    # string payloads have passed the fixed-capacity preflight above.
    if stack_created:
        stack_layer = container.layers.string.new(meta.stack_layer)
    try:
        for index, payload in stack_values:
            container[index][stack_layer] = payload
    except Exception:
        if stack_created:
            try:
                container.layers.string.remove(stack_layer)
            except (ReferenceError, RuntimeError, ValueError):
                pass
        raise
    return stack_layer, stack_created


def merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type: str):
    """Reconcile a complete valid BMesh stack, preserving damaged legacy data."""

    container = element_container(bm, element_type)
    mapped_keys = {int(key): key for key in mapping}
    changed = False
    complete = True
    for elem in container:
        data = elem[stack_layer]
        key = mapped_keys.get(elem.index)
        if not data:
            if key is not None:
                del mapping[key]
                changed = True
            continue
        if key is None:
            key = str(elem.index)
        try:
            layers, encoding = _decode_stack_payload(data)
        except StackEncodingError:
            complete = False
            continue

        current = list(mapping.get(key, ()))
        if encoding == "LEGACY":
            legacy_was_truncated = (
                len(current) > len(layers)
                and layers == _legacy_prefix(current)
            )
            if legacy_was_truncated:
                layers = current
            elif len(data) >= _STACK_MAX_BYTES and current != layers:
                # A legacy value at Blender's hard limit may end in a valid but
                # partial token. Without a checksum it cannot outrank JSON.
                complete = False
                continue
            try:
                encode_layers(layers)
            except StackCapacityError:
                complete = False
                continue

        if layers:
            if current != layers:
                mapping[key] = layers
                changed = True
        elif key in mapping:
            del mapping[key]
            changed = True
    return changed, complete


def _digest_integer(digest, value):
    digest.update(struct.pack("<q", int(value)))


def _canonical_face_vertices(face):
    indices = tuple(vert.index for vert in face.verts)
    if len(indices) < 2:
        return indices
    pivot = indices.index(min(indices))
    forward = indices[pivot:] + indices[:pivot]
    reverse_indices = tuple(reversed(indices))
    reverse_pivot = reverse_indices.index(min(reverse_indices))
    reverse = reverse_indices[reverse_pivot:] + reverse_indices[:reverse_pivot]
    return min(forward, reverse)


def _mapped_topology_identity(bm, element_type: str, elem):
    if element_type == VERTEX:
        neighbours = [edge.other_vert(elem).index for edge in elem.link_edges]
        if any(index < 0 for index in neighbours):
            bm.verts.index_update()
            neighbours = [edge.other_vert(elem).index for edge in elem.link_edges]
        return tuple(sorted(neighbours))
    vertices = [vert.index for vert in elem.verts]
    if any(index < 0 for index in vertices):
        bm.verts.index_update()
    if element_type == EDGE:
        return tuple(sorted(vert.index for vert in elem.verts))
    return _canonical_face_vertices(elem)


def annotation_state_fingerprint(
    bm, element_type: str, mapping, data_str: str | None = None
) -> str:
    """Bind sparse Object assignments to their current local Mesh identities."""

    if data_str is None:
        cleaned, data_str = prepare_element_layers(mapping)
    else:
        cleaned = mapping
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    stack_layer = container.layers.string.get(element_spec(element_type).stack_layer)
    digest = hashlib.blake2b(digest_size=20, person=b"MAL-state-v2")
    digest.update(element_type.encode("ascii"))
    for count in (len(bm.verts), len(bm.edges), len(bm.faces)):
        _digest_integer(digest, count)
    digest.update(b"\x01" if stack_layer is not None else b"\x00")
    for raw_index in sorted(cleaned, key=int):
        element_index = int(raw_index)
        _digest_integer(digest, element_index)
        if not (0 <= element_index < len(container)):
            digest.update(b"\xff")
            continue
        elem = container[element_index]
        identity = _mapped_topology_identity(bm, element_type, elem)
        _digest_integer(digest, len(identity))
        for identity_index in identity:
            _digest_integer(digest, identity_index)
        payload = bytes(elem[stack_layer]) if stack_layer is not None else b""
        _digest_integer(digest, len(payload))
        digest.update(payload)
    digest.update(data_str.encode("utf-8"))
    return digest.hexdigest()


def _complete_stack_matches_mapping(bm, element_type: str, mapping) -> bool:
    """Compare durable JSON with every non-empty custom-data payload."""

    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    stack_layer = container.layers.string.get(element_spec(element_type).stack_layer)
    if stack_layer is None:
        return False
    container.index_update()
    working_mapping = copy_element_layers(mapping)
    if prune_mapping_to_index_count(working_mapping, len(container)):
        return False
    changed, complete = merge_stack_layer_into_mapping(
        working_mapping, bm, stack_layer, element_type
    )
    return bool(complete and not changed)


def record_annotation_state(
    settings, element_type: str, bm, mapping, data_str: str | None = None
):
    """Persist proof that JSON, topology, and BMesh ownership agree."""

    property_name = element_spec(element_type).state_property
    value = annotation_state_fingerprint(
        bm, element_type, mapping, data_str=data_str
    )
    if getattr(settings, property_name, "") != value:
        setattr(settings, property_name, value)


def clear_annotation_state(settings, element_type: str):
    property_name = element_spec(element_type).state_property
    if getattr(settings, property_name, ""):
        setattr(settings, property_name, "")


def _finish_stack_inspection(
    settings, element_type: str, mesh, bm, mapping, data_str, merge_result
):
    if not merge_result.inspected:
        return
    if merge_result.complete:
        record_annotation_state(settings, element_type, bm, mapping, data_str)
        mark_bmesh_mapping_synchronized(mesh, bm, element_type)
    else:
        clear_annotation_state(settings, element_type)
        mark_bmesh_mapping_quarantined(mesh, bm, element_type)


def shared_annotation_mapping_is_current(
    obj: bpy.types.Object,
    element_type: str,
    bm,
    mapping=None,
) -> bool:
    """Return whether a shared Mesh mapping is safe to consume by index."""

    if not annotation_mesh_is_shared(obj):
        return True
    settings = getattr(obj, "mesh_annotations", None)
    if settings is None:
        return True
    mapping = load_element_layers(settings, element_type) if mapping is None else mapping
    if not element_layers_data_is_valid(settings, element_type):
        return False
    if not mapping:
        return True
    try:
        if not _complete_stack_matches_mapping(bm, element_type, mapping):
            return False
        current = annotation_state_fingerprint(bm, element_type, mapping)
    except (StackEncodingError, TypeError, ValueError):
        return False
    stored = getattr(settings, element_spec(element_type).state_property, "")
    return bool(stored and stored == current)


def ensure_shared_annotation_current(obj, element_type: str, bm, mapping=None):
    if not shared_annotation_mapping_is_current(obj, element_type, bm, mapping):
        raise StaleSharedAnnotationError(
            "Shared mesh topology no longer matches this object's annotations"
        )


def shared_annotation_mapping_statuses(obj: bpy.types.Object) -> dict[str, bool]:
    """Validate each Object mapping against the same shared Mesh snapshot."""

    statuses = {element_type: True for element_type in ELEMENT_TYPES}
    if not annotation_mesh_is_shared(obj):
        return statuses
    _mesh, bm, source_is_edit = _object_bmesh(obj)
    try:
        for element_type in ELEMENT_TYPES:
            ensure_lookup_tables(bm, element_type)
            mapping = load_element_layers(obj.mesh_annotations, element_type)
            statuses[element_type] = shared_annotation_mapping_is_current(
                obj, element_type, bm, mapping
            )
        return statuses
    finally:
        if not source_is_edit:
            bm.free()


def shared_annotation_mappings_are_current(obj: bpy.types.Object) -> bool:
    """Return whether every Object mapping is proven by one Mesh snapshot."""

    return all(shared_annotation_mapping_statuses(obj).values())


def _bmesh_sync_key(mesh, element_type: str):
    return int(mesh.session_uid), element_type


def _bmesh_topology_signature(bm):
    return len(bm.verts), len(bm.edges), len(bm.faces)


def real_mesh_user_count(mesh) -> int:
    """Exclude Blender retention users while retaining every real data owner."""

    users = int(mesh.users)
    users -= int(bool(getattr(mesh, "use_fake_user", False)))
    # Extra User only raises an otherwise orphaned ID to one user. A Mesh
    # attached to an Object already has a real user, so there is no additive
    # count to subtract (doing so would hide a real second Object owner).
    return max(0, users)


def mark_bmesh_mapping_synchronized(mesh, bm, element_type: str):
    _remember_bmesh_sync_state(mesh, bm, element_type, complete=True)


def mark_bmesh_mapping_quarantined(mesh, bm, element_type: str):
    """Remember an inspected corrupt stack without calling it synchronized."""

    _remember_bmesh_sync_state(mesh, bm, element_type, complete=False)


def _remember_bmesh_sync_state(mesh, bm, element_type: str, *, complete: bool):
    key = _bmesh_sync_key(mesh, element_type)
    _BMESH_SYNC_STATES[key] = (_bmesh_topology_signature(bm), complete)
    _BMESH_SYNC_STATES.move_to_end(key)
    _BMESH_SYNC_DIRTY_AT.pop(key, None)
    while len(_BMESH_SYNC_STATES) > _BMESH_SYNC_CACHE_LIMIT:
        _BMESH_SYNC_STATES.popitem(last=False)


def mark_bmesh_mapping_dirty(mesh):
    """Coalesce indistinguishable selection, deformation, and topology updates."""

    mesh_uid = int(mesh.session_uid)
    dirty_at = time.perf_counter()
    for element_type in ELEMENT_TYPES:
        _BMESH_SYNC_DIRTY_AT[(mesh_uid, element_type)] = dirty_at
    while len(_BMESH_SYNC_DIRTY_AT) > _BMESH_SYNC_CACHE_LIMIT * len(ELEMENT_TYPES):
        oldest_key = min(_BMESH_SYNC_DIRTY_AT, key=_BMESH_SYNC_DIRTY_AT.get)
        _BMESH_SYNC_DIRTY_AT.pop(oldest_key, None)


def pending_bmesh_sync_delay() -> float:
    if not _BMESH_SYNC_DIRTY_AT:
        return 0.0
    newest_update = max(_BMESH_SYNC_DIRTY_AT.values())
    return max(0.0, _BMESH_SYNC_QUIET_SECONDS - (time.perf_counter() - newest_update))


def merge_stack_layer_if_needed(
    mapping,
    mesh,
    bm,
    stack_layer,
    element_type: str,
    *,
    defer=False,
    force=False,
):
    """Inspect into a private mapping; callers commit and mark synchronization."""

    if stack_layer is None or real_mesh_user_count(mesh) > 1:
        return mapping, StackMergeResult(False, False, False)
    key = _bmesh_sync_key(mesh, element_type)
    signature = _bmesh_topology_signature(bm)
    dirty_at = _BMESH_SYNC_DIRTY_AT.get(key)
    if (
        not force
        and defer
        and dirty_at is not None
        and time.perf_counter() - dirty_at < _BMESH_SYNC_QUIET_SECONDS
    ):
        return mapping, StackMergeResult(False, False, False)
    if not force and dirty_at is None:
        cached_state = _BMESH_SYNC_STATES.get(key)
        if cached_state is not None and cached_state[0] == signature:
            _BMESH_SYNC_STATES.move_to_end(key)
            return mapping, StackMergeResult(False, cached_state[1], False)
    working_mapping = copy_element_layers(mapping)
    changed, complete = merge_stack_layer_into_mapping(
        working_mapping, bm, stack_layer, element_type
    )
    if not complete:
        mark_bmesh_mapping_quarantined(mesh, bm, element_type)
    return working_mapping, StackMergeResult(changed, complete, True)


def _reconcile_existing_stack(mapping, mesh, bm, stack_layer, element_type: str):
    if stack_layer is None:
        return mapping, StackMergeResult(False, True, False)
    return merge_stack_layer_if_needed(
        mapping, mesh, bm, stack_layer, element_type, force=True
    )


def sync_mapping_to_bmesh(
    bm, stack_layer, mapping, element_type: str, element_indices=None
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
    prepared = [
        (
            elem.index,
            encode_layers(mapping.get(str(elem.index), ())),
        )
        for elem in elements
    ]
    for index, payload in prepared:
        elem = container[index]
        elem[stack_layer] = payload


def _flush_bmesh(mesh, bm, source_is_edit: bool):
    if source_is_edit:
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    else:
        bm.to_mesh(mesh)
        mesh.update()


def commit_mapping_transaction(
    settings,
    element_type: str,
    mesh,
    bm,
    stack_layer,
    stack_created: bool,
    mapping,
    data_str: str,
    element_indices,
    *,
    source_is_edit: bool,
    complete_state: bool,
):
    """Commit BMesh + JSON + proof token, restoring all of them on failure."""

    container = element_container(bm, element_type)
    if element_indices is None:
        target_indices = list(range(len(container)))
    else:
        target_indices = sorted(
            {
                index
                for index in map(int, element_indices)
                if 0 <= index < len(container)
            }
        )
    previous_payloads = (
        {}
        if stack_created
        else {index: bytes(container[index][stack_layer]) for index in target_indices}
    )
    data_property = _data_property_name(element_type)
    state_property = element_spec(element_type).state_property
    previous_data = getattr(settings, data_property)
    previous_state = getattr(settings, state_property, "")
    mesh_flush_attempted = False
    try:
        sync_mapping_to_bmesh(
            bm, stack_layer, mapping, element_type, target_indices
        )
        # Object Mode uses a detached BMesh. Commit fallible RNA first so a
        # property failure cannot require a second Mesh write to roll back.
        if source_is_edit:
            mesh_flush_attempted = True
            _flush_bmesh(mesh, bm, True)
        commit_prepared_element_layers(settings, element_type, mapping, data_str)
        if complete_state:
            record_annotation_state(
                settings, element_type, bm, mapping, data_str
            )
        else:
            clear_annotation_state(settings, element_type)
        if not source_is_edit:
            mesh_flush_attempted = True
            _flush_bmesh(mesh, bm, False)
        if complete_state:
            mark_bmesh_mapping_synchronized(mesh, bm, element_type)
        else:
            mark_bmesh_mapping_quarantined(mesh, bm, element_type)
    except Exception:
        bmesh_restored = False
        try:
            if stack_created:
                container.layers.string.remove(stack_layer)
            else:
                for index, payload in previous_payloads.items():
                    container[index][stack_layer] = payload
            if source_is_edit or mesh_flush_attempted:
                _flush_bmesh(mesh, bm, source_is_edit)
            bmesh_restored = True
        finally:
            try:
                setattr(settings, data_property, previous_data)
                setattr(settings, state_property, previous_state)
            finally:
                invalidate_element_layers_cache(settings, element_type)
                if bmesh_restored:
                    mark_bmesh_mapping_dirty(mesh)
                else:
                    mark_bmesh_mapping_quarantined(mesh, bm, element_type)
        raise


def _finalize_reconciled_mapping(
    settings,
    element_type: str,
    mesh,
    bm,
    mapping,
    data_str: str,
    merge_result: StackMergeResult,
    mapping_changed: bool,
):
    """Commit changed JSON, then record the result of a stack inspection."""

    if not mapping_changed:
        _finish_stack_inspection(
            settings, element_type, mesh, bm, mapping, data_str, merge_result
        )
        return

    data_property = _data_property_name(element_type)
    state_property = element_spec(element_type).state_property
    previous_data = getattr(settings, data_property)
    previous_state = getattr(settings, state_property, "")
    try:
        commit_prepared_element_layers(settings, element_type, mapping, data_str)
        _finish_stack_inspection(
            settings, element_type, mesh, bm, mapping, data_str, merge_result
        )
    except Exception:
        setattr(settings, data_property, previous_data)
        setattr(settings, state_property, previous_state)
        invalidate_element_layers_cache(settings, element_type)
        mark_bmesh_mapping_dirty(mesh)
        raise


def annotation_mesh_is_shared(obj: bpy.types.Object) -> bool:
    if not obj or obj.type != "MESH":
        return False
    mesh = obj.data
    return bool(
        real_mesh_user_count(mesh) > 1
        or not getattr(mesh, "is_editable", True)
    )


def rebuild_annotation_stacks(obj: bpy.types.Object, mappings=None):
    """Rebuild detached Mesh storage and return prepared JSON/state snapshots."""

    if annotation_mesh_is_shared(obj):
        raise SharedMeshAnnotationError(
            "Make the mesh data single-user before editing annotations"
        )
    settings = getattr(obj, "mesh_annotations", None)
    if settings is None:
        return
    source_mappings = mappings if mappings is not None else {
        element_type: load_element_layers(settings, element_type)
        for element_type in ELEMENT_TYPES
    }
    prepared_mappings = {}
    data_strings = {}
    for element_type in ELEMENT_TYPES:
        prepared, data_str = prepare_element_layers(source_mappings[element_type])
        prepared_mappings[element_type] = prepared
        data_strings[element_type] = data_str

    mesh, bm, source_is_edit = _object_bmesh(obj)
    try:
        state_tokens = {}
        for element_type, mapping in prepared_mappings.items():
            ensure_lookup_tables(bm, element_type)
            ensure_annotation_stack(bm, element_type, mapping, rebuild=True)
            state_tokens[element_type] = annotation_state_fingerprint(
                bm, element_type, mapping, data_strings[element_type]
            )
        _flush_bmesh(mesh, bm, source_is_edit)
        return prepared_mappings, data_strings, state_tokens
    finally:
        if not source_is_edit:
            bm.free()


def ensure_annotation_mesh_editable(obj: bpy.types.Object):
    if annotation_mesh_is_shared(obj):
        raise SharedMeshAnnotationError(
            "Make the mesh data single-user before editing annotations"
        )


def auto_generate_color(settings, element_type: str, existing_colors=None):
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


def assign_elements_to_layer(
    obj: bpy.types.Object, element_type: str, layer_id: int, element_indices=None
):
    ensure_annotation_mesh_editable(obj)
    settings = getattr(obj, "mesh_annotations", None)
    if settings is None or get_layer_by_id(settings, element_type, layer_id) is None:
        return False
    mapping = copy_element_layers(load_element_layers(settings, element_type))
    debug_log(
        settings,
        f"Assign elements start: type={element_type}, "
        f"layer_id={layer_id}, indices={element_indices}",
    )
    order_lookup = layer_order_map(settings, element_type)
    mesh, bm, source_is_edit = _object_bmesh(obj)
    try:
        ensure_lookup_tables(bm, element_type)
        container = element_container(bm, element_type)
        storage_changed = prune_mapping_to_index_count(mapping, len(container))
        meta = element_spec(element_type)
        stack_layer = container.layers.string.get(meta.stack_layer)
        mapping, merge_result = _reconcile_existing_stack(
            mapping, mesh, bm, stack_layer, element_type
        )
        storage_changed |= merge_result.changed
        if element_indices is None:
            target_indices = (
                [elem.index for elem in container if elem.select]
                if source_is_edit
                else list(range(len(container)))
            )
        else:
            target_indices = [
                index
                for index in map(int, element_indices)
                if 0 <= index < len(container)
            ]
        target_indices = list(dict.fromkeys(target_indices))
        if not target_indices:
            prepared_mapping, data_str = prepare_element_layers(mapping)
            mapping = prepared_mapping
            _finalize_reconciled_mapping(
                settings,
                element_type,
                mesh,
                bm,
                mapping,
                data_str,
                merge_result,
                storage_changed,
            )
            debug_log(settings, "Assign aborted: no target elements")
            return False

        for index in target_indices:
            layers = get_layers_for_index(mapping, index)
            if layer_id in layers:
                layers.remove(layer_id)
            layers.append(layer_id)
            set_layers_for_index(
                mapping, index, normalize_layer_ids(layers, order_lookup)
            )

        # Validate the complete final mapping before creating a custom layer or
        # changing even one BMesh element.
        prepared_mapping, data_str = prepare_element_layers(mapping)
        mapping = prepared_mapping

        stack_layer, stack_created = ensure_annotation_stack(
            bm, element_type, mapping
        )
        commit_mapping_transaction(
            settings,
            element_type,
            mesh,
            bm,
            stack_layer,
            stack_created,
            mapping,
            data_str,
            target_indices,
            source_is_edit=source_is_edit,
            complete_state=stack_created or merge_result.complete,
        )
        debug_log(settings, f"Assign success: {len(target_indices)} elements")
        return True
    finally:
        if not source_is_edit:
            bm.free()


def clear_elements_from_layer(
    obj: bpy.types.Object,
    element_type: str,
    layer_id: int,
    only_selected: bool,
    mode: str = "ALL",
):
    if mode not in {"ACTIVE", "TOP", "ALL"}:
        raise ValueError(f"Unsupported annotation clear mode: {mode!r}")
    ensure_annotation_mesh_editable(obj)
    settings = getattr(obj, "mesh_annotations", None)
    mapping = copy_element_layers(load_element_layers(settings, element_type))
    order_lookup = layer_order_map(settings, element_type)
    debug_log(
        settings,
        f"Clear elements: type={element_type}, layer_id={layer_id}, "
        f"only_selected={only_selected}, mode={mode}",
    )
    mesh, bm, source_is_edit = _object_bmesh(obj)
    try:
        ensure_lookup_tables(bm, element_type)
        container = element_container(bm, element_type)
        mapping_changed = prune_mapping_to_index_count(mapping, len(container))
        stack_layer = container.layers.string.get(
            element_spec(element_type).stack_layer
        )
        mapping, merge_result = _reconcile_existing_stack(
            mapping, mesh, bm, stack_layer, element_type
        )
        mapping_changed |= merge_result.changed
        targets = [
            elem
            for elem in container
            if not only_selected or elem.select
        ]
        changed_indices = set()
        for elem in targets:
            layers = normalize_layer_ids(
                get_layers_for_index(mapping, elem.index), order_lookup
            )
            original_layers = tuple(layers)
            if layer_id == -1:
                layers = layers[:-1] if mode == "TOP" else []
            elif layer_id in layers:
                layers = [candidate for candidate in layers if candidate != layer_id]
            layers = normalize_layer_ids(layers, order_lookup)
            set_layers_for_index(mapping, elem.index, layers)
            if tuple(layers) != original_layers:
                changed_indices.add(elem.index)
        prepared_mapping, data_str = prepare_element_layers(mapping)
        mapping = prepared_mapping
        if changed_indices:
            stack_layer, stack_created = ensure_annotation_stack(
                bm, element_type, mapping
            )
            commit_mapping_transaction(
                settings,
                element_type,
                mesh,
                bm,
                stack_layer,
                stack_created,
                mapping,
                data_str,
                changed_indices,
                source_is_edit=source_is_edit,
                complete_state=stack_created or merge_result.complete,
            )
        else:
            _finalize_reconciled_mapping(
                settings,
                element_type,
                mesh,
                bm,
                mapping,
                data_str,
                merge_result,
                mapping_changed,
            )
        debug_log(
            settings,
            f"Clear processed {len(targets)} elements "
            f"(changed={bool(changed_indices) or mapping_changed})",
        )
        return bool(changed_indices)
    finally:
        if not source_is_edit:
            bm.free()


def count_elements_for_layer(obj: bpy.types.Object, element_type: str, layer_id: int) -> int:
    if layer_id is None:
        return 0
    settings = getattr(obj, "mesh_annotations", None)
    return int(element_layer_counts(settings, element_type).get(layer_id, 0))


def reconciled_mapping_for_explicit_read(obj, element_type: str, bm):
    """Return a proven snapshot; explicit actions may durably reconcile JSON."""

    mesh = obj.data
    settings = obj.mesh_annotations
    mapping = load_element_layers(settings, element_type)
    if annotation_mesh_is_shared(obj):
        ensure_shared_annotation_current(obj, element_type, bm, mapping)
        return mapping
    container = element_container(bm, element_type)
    stack_layer = container.layers.string.get(element_spec(element_type).stack_layer)
    if stack_layer is None:
        working_mapping = copy_element_layers(mapping)
        prune_mapping_to_index_count(working_mapping, len(container))
        prepared_mapping, data_str = prepare_element_layers(working_mapping)
        if prepared_mapping or mapping:
            stack_layer, stack_created = ensure_annotation_stack(
                bm, element_type, prepared_mapping
            )
            commit_mapping_transaction(
                settings,
                element_type,
                mesh,
                bm,
                stack_layer,
                stack_created,
                prepared_mapping,
                data_str,
                (),
                source_is_edit=obj.mode == "EDIT",
                complete_state=True,
            )
        else:
            mark_bmesh_mapping_synchronized(mesh, bm, element_type)
        return prepared_mapping
    mapping, merge_result = _reconcile_existing_stack(
        mapping, mesh, bm, stack_layer, element_type
    )
    mapping_changed = merge_result.changed
    mapping_changed |= prune_mapping_to_index_count(mapping, len(container))
    prepared_mapping, data_str = prepare_element_layers(mapping)
    mapping = prepared_mapping
    _finalize_reconciled_mapping(
        settings,
        element_type,
        mesh,
        bm,
        mapping,
        data_str,
        merge_result,
        mapping_changed,
    )
    return mapping


def synchronize_edit_mesh_annotations(obj, *, dirty_only=False):
    """Commit topology-following ownership outside the viewport draw callback."""

    if not obj or obj.type != "MESH" or obj.mode != "EDIT":
        return
    if annotation_mesh_is_shared(obj):
        mesh_uid = int(obj.data.session_uid)
        for element_type in ELEMENT_TYPES:
            _BMESH_SYNC_DIRTY_AT.pop((mesh_uid, element_type), None)
        return
    bm = bmesh.from_edit_mesh(obj.data)
    for element_type in ELEMENT_TYPES:
        if (
            dirty_only
            and _bmesh_sync_key(obj.data, element_type) not in _BMESH_SYNC_DIRTY_AT
        ):
            continue
        ensure_lookup_tables(bm, element_type)
        reconciled_mapping_for_explicit_read(obj, element_type, bm)


def select_elements_for_layer(obj: bpy.types.Object, element_type: str, layer_id: int) -> int:
    if obj.mode != "EDIT":
        return 0
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    settings = obj.mesh_annotations
    mapping = reconciled_mapping_for_explicit_read(obj, element_type, bm)
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
    ensure_annotation_mesh_editable(obj)
    mesh = obj.data
    settings = getattr(obj, "mesh_annotations", None)
    if settings is None:
        return 0
    target_layers = {int(lid) for lid in layer_ids if lid is not None}
    if not target_layers:
        return 0
    bm = bmesh.from_edit_mesh(mesh)
    ensure_lookup_tables(bm, FACE)
    ensure_lookup_tables(bm, EDGE)
    mapping = reconciled_mapping_for_explicit_read(obj, FACE, bm)
    layer_faces_map = {layer_id: set() for layer_id in target_layers}
    for raw_index, layers in mapping.items():
        face_index = int(raw_index)
        if not (0 <= face_index < len(bm.faces)):
            continue
        for layer_id in target_layers.intersection(layers):
            layer_faces_map[layer_id].add(face_index)
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
    owner = getattr(settings, "id_data", None)
    if isinstance(owner, bpy.types.Object) and owner.type == "MESH":
        ensure_annotation_mesh_editable(owner)
    collection = get_layer_collection(settings, element_type)
    meta = element_spec(element_type)
    used_ids = {int(candidate.layer_id) for candidate in collection}
    layer_id = max(1, get_next_layer_id(settings, element_type))
    while layer_id in used_ids:
        layer_id += 1
    if layer_id > _LAYER_ID_MAX:
        raise StackEncodingError("Annotation layer id space is exhausted")
    existing_colors = [tuple(layer.color[:3]) for layer in collection]
    generated_color = color or auto_generate_color(
        settings, element_type, existing_colors=existing_colors
    )
    layer = collection.add()
    layer.element_type = element_type
    next_id_attr = element_spec(element_type).next_id
    layer.layer_id = layer_id
    setattr(settings, next_id_attr, min(_LAYER_ID_MAX, layer_id + 1))
    layer.name = name or f"{meta.default_name} {layer.layer_id}"
    layer.color = generated_color
    set_active_index(settings, element_type, len(collection) - 1)
    return layer


def remove_layer(settings, obj, element_type: str, index: int):
    ensure_annotation_mesh_editable(obj)
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
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    mapping = reconciled_mapping_for_explicit_read(obj, element_type, bm)
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
