"""Map source annotations onto Blender's evaluated mesh."""

from collections import Counter, defaultdict

import bmesh
import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

from .constants import EDGE, FACE, VERTEX
from .model import debug_log


# These modifier families retain the source element ordering. Unknown and
# topology-generating modifiers must use provenance matching even when their
# evaluated vertex/edge/face counts happen to equal the source counts.
_INDEX_PRESERVING_MODIFIER_TYPES = frozenset(
    {
        "ARMATURE",
        "CAST",
        "CORRECTIVE_SMOOTH",
        "CURVE",
        "DATA_TRANSFER",
        "DISPLACE",
        "HOOK",
        "LAPLACIANDEFORM",
        "LAPLACIANSMOOTH",
        "LATTICE",
        "MESH_CACHE",
        "MESH_DEFORM",
        "NORMAL_EDIT",
        "SHRINKWRAP",
        "SIMPLE_DEFORM",
        "SMOOTH",
        "SURFACE_DEFORM",
        "UV_PROJECT",
        "UV_WARP",
        "VERTEX_WEIGHT_EDIT",
        "VERTEX_WEIGHT_MIX",
        "VERTEX_WEIGHT_PROXIMITY",
        "WARP",
        "WAVE",
        "WEIGHTED_NORMAL",
    }
)
_SUPPORTED_EVALUATED_MODIFIER_TYPES = _INDEX_PRESERVING_MODIFIER_TYPES | {"SUBSURF"}


def _modifier_visible_for_overlay(obj: bpy.types.Object, modifier) -> bool:
    if not modifier.show_viewport:
        return False
    return obj.mode != "EDIT" or modifier.show_in_editmode


def _visible_modifiers(obj: bpy.types.Object):
    return tuple(
        modifier
        for modifier in obj.modifiers
        if _modifier_visible_for_overlay(obj, modifier)
    )


def _modifier_preserves_indices(modifier) -> bool:
    return modifier.type in _INDEX_PRESERVING_MODIFIER_TYPES or (
        modifier.type == "SUBSURF" and int(modifier.levels) == 0
    )


def _modifier_stack_preserves_indices(obj: bpy.types.Object) -> bool:
    return all(
        _modifier_preserves_indices(modifier)
        for modifier in _visible_modifiers(obj)
    )


def _modifier_stack_supports_evaluated_mapping(obj: bpy.types.Object) -> bool:
    return all(
        modifier.type in _SUPPORTED_EVALUATED_MODIFIER_TYPES
        for modifier in _visible_modifiers(obj)
    )


def _overlay_subdivision_levels(obj: bpy.types.Object) -> int:
    """Return exact-map subdivision steps, or zero for an unsafe mixed stack."""

    modifiers = _visible_modifiers(obj)
    if any(
        modifier.type not in _INDEX_PRESERVING_MODIFIER_TYPES | {"SUBSURF"}
        for modifier in modifiers
    ):
        return 0
    levels = 0
    for modifier in modifiers:
        if modifier.type != "SUBSURF":
            continue
        levels += max(0, int(modifier.levels))
    return levels


def _topology_vertex_sources(
    bm: bmesh.types.BMesh,
    mesh: bpy.types.Mesh,
    edge_sources,
    source_vertex_filter=None,
):
    """Map source vertices from intersections of their evaluated edge descendants."""
    sources = [None] * len(mesh.vertices)
    if not bm.verts or not mesh.vertices:
        return sources

    source_edge_vertices = defaultdict(set)
    source_edge_degrees = defaultdict(Counter)
    for edge in mesh.edges:
        source_index = edge_sources[edge.index] if edge.index < len(edge_sources) else None
        if source_index is None:
            continue
        vertex0, vertex1 = edge.vertices
        source_edge_vertices[source_index].update((vertex0, vertex1))
        source_edge_degrees[source_index][vertex0] += 1
        source_edge_degrees[source_index][vertex1] += 1

    if source_vertex_filter is None:
        source_vertices = bm.verts
    else:
        source_vertices = (
            bm.verts[index]
            for index in sorted(source_vertex_filter)
            if 0 <= index < len(bm.verts)
        )
    for source_vertex in source_vertices:
        incident_edges = [
            (edge.index, source_edge_vertices[edge.index])
            for edge in source_vertex.link_edges
            if source_edge_vertices.get(edge.index)
        ]
        incident_sets = [vertices for _edge_index, vertices in incident_edges]
        candidates = set()
        if len(incident_sets) >= 2:
            candidates = set.intersection(*incident_sets)
        elif len(incident_sets) == 1:
            source_edge_index = incident_edges[0][0]
            degrees = source_edge_degrees.get(source_edge_index, {})
            candidates = {index for index, degree in degrees.items() if degree == 1}

        if source_vertex.index in candidates:
            evaluated_index = source_vertex.index
        elif len(candidates) == 1:
            evaluated_index = next(iter(candidates))
        elif not incident_sets and source_vertex.index < len(mesh.vertices):
            # Subdivision retains loose source vertices at their source index.
            evaluated_index = source_vertex.index
        else:
            # Ambiguous provenance is safer to omit than to assign by distance.
            continue
        if sources[evaluated_index] is None:
            sources[evaluated_index] = source_vertex.index
    return sources


def _evaluated_source_maps(
    obj: bpy.types.Object,
    bm: bmesh.types.BMesh,
    mesh: bpy.types.Mesh,
    required_types=None,
    source_filters=None,
):
    """Map evaluated elements back to the edit-cage elements that own annotations."""
    required_types = set(required_types or (FACE, EDGE, VERTEX))
    needs_vertex_sources = VERTEX in required_types
    needs_edge_sources = EDGE in required_types or needs_vertex_sources
    needs_face_sources = FACE in required_types or needs_edge_sources
    source_filters = source_filters or {}
    vertex_filter = source_filters.get(VERTEX)
    required_source_edges = (
        source_filters.get(EDGE) if EDGE in required_types else None
    )
    if needs_vertex_sources and vertex_filter:
        required_source_edges = set(required_source_edges or ())
        required_source_edges.update(
            edge.index
            for vertex_index in vertex_filter
            if 0 <= vertex_index < len(bm.verts)
            for edge in bm.verts[vertex_index].link_edges
        )

    source_counts = (len(bm.verts), len(bm.edges), len(bm.faces))
    evaluated_counts = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))
    if source_counts == evaluated_counts and _modifier_stack_preserves_indices(obj):
        return (
            list(range(source_counts[2])) if needs_face_sources else None,
            list(range(source_counts[1])) if needs_edge_sources else None,
            list(range(source_counts[0])) if needs_vertex_sources else None,
            "DIRECT",
        )

    subdivision_levels = _overlay_subdivision_levels(obj)
    if subdivision_levels > 0:
        face_multiplier = 4 ** (subdivision_levels - 1)
        face_sources = []
        for face in bm.faces:
            child_count = len(face.verts) * face_multiplier
            face_sources.extend([face.index] * child_count)
        if len(face_sources) == len(mesh.polygons):
            if not needs_edge_sources:
                return face_sources, None, None, "SUBDIVISION"
            edge_child_count = 2 ** subdivision_levels
            edge_sources = []
            for edge in bm.edges:
                source_index = (
                    edge.index
                    if required_source_edges is None or edge.index in required_source_edges
                    else None
                )
                edge_sources.extend([source_index] * edge_child_count)
            if len(edge_sources) <= len(mesh.edges) and len(bm.verts) <= len(mesh.vertices):
                edge_sources.extend([None] * (len(mesh.edges) - len(edge_sources)))
                vertex_sources = (
                    _topology_vertex_sources(
                        bm,
                        mesh,
                        edge_sources,
                        source_vertex_filter=vertex_filter,
                    )
                    if needs_vertex_sources
                    else None
                )
                return (
                    face_sources if needs_face_sources else None,
                    edge_sources if needs_edge_sources else None,
                    vertex_sources,
                    "SUBDIVISION",
                )
    return None


def _polygon_triangles(mesh: bpy.types.Mesh, polygon):
    coordinates = [mesh.vertices[index].co.copy() for index in polygon.vertices]
    orientation = 0
    for index, coordinate in enumerate(coordinates):
        next_coordinate = coordinates[(index + 1) % len(coordinates)]
        after_next = coordinates[(index + 2) % len(coordinates)]
        turn = (next_coordinate - coordinate).cross(
            after_next - next_coordinate
        ).dot(polygon.normal)
        if turn == 0.0:
            continue
        current_orientation = 1 if turn > 0.0 else -1
        if orientation and current_orientation != orientation:
            break
        orientation = current_orientation
    else:
        if len(coordinates) < 3:
            return []
        root = coordinates[0]
        return [
            (root.copy(), coordinates[index].copy(), coordinates[index + 1].copy())
            for index in range(1, len(coordinates) - 1)
        ]

    origin = coordinates[0]
    scale = max((coordinate - origin).length for coordinate in coordinates)
    if scale == 0.0:
        return []
    normalized = [(coordinate - origin) / scale for coordinate in coordinates]
    triangles = []
    for triangle in tessellate_polygon([normalized]):
        if triangle and isinstance(triangle[0], int):
            triangles.append(tuple(coordinates[index].copy() for index in triangle))
        else:
            triangles.append(
                tuple(origin + coordinate * scale for coordinate in triangle)
            )
    return triangles


def _edge_geometry(source_index: int, vertex0, vertex1):
    p0 = vertex0.co.copy()
    p1 = vertex1.co.copy()
    normal0 = vertex0.normal.copy()
    normal1 = vertex1.normal.copy()
    fallback = (p0 - p1).cross(Vector((0.0, 0.0, 1.0)))
    if normal0.length == 0:
        normal0 = fallback.copy()
    if normal1.length == 0:
        normal1 = fallback.copy()
    return source_index, p0, p1, normal0, normal1


def _evaluated_edge_geometry(mesh, edge_index: int, source_index: int):
    edge = mesh.edges[edge_index]
    return _edge_geometry(
        source_index,
        mesh.vertices[edge.vertices[0]],
        mesh.vertices[edge.vertices[1]],
    )


def _sparse_exact_overlay_geometry(obj, bm, mesh, source_filters):
    """Read only annotated evaluated elements when modifier ordering is deterministic."""
    face_filter = source_filters.get(FACE, set())
    edge_filter = source_filters.get(EDGE, set())
    vertex_filter = source_filters.get(VERTEX, set())
    source_counts = (len(bm.verts), len(bm.edges), len(bm.faces))
    evaluated_counts = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))

    if source_counts == evaluated_counts and _modifier_stack_preserves_indices(obj):
        faces = []
        for source_index in sorted(face_filter):
            if 0 <= source_index < len(mesh.polygons):
                polygon = mesh.polygons[source_index]
                triangles = _polygon_triangles(mesh, polygon)
                if triangles:
                    faces.append((source_index, triangles, polygon.normal.copy()))
        edges = [
            _evaluated_edge_geometry(mesh, source_index, source_index)
            for source_index in sorted(edge_filter)
            if 0 <= source_index < len(mesh.edges)
        ]
        vertices = [
            (
                source_index,
                mesh.vertices[source_index].co.copy(),
                mesh.vertices[source_index].normal.copy(),
            )
            for source_index in sorted(vertex_filter)
            if 0 <= source_index < len(mesh.vertices)
        ]
        return {FACE: faces, EDGE: edges, VERTEX: vertices}, "DIRECT_SPARSE"

    subdivision_levels = _overlay_subdivision_levels(obj)
    if subdivision_levels == 0:
        return None
    if vertex_filter:
        # Subdivision vertex descendants are identified topologically below;
        # source-space proximity fails after later deformers and on loose data.
        return None

    face_multiplier = 4 ** (subdivision_levels - 1)
    face_ranges = {}
    one_copy_face_count = 0
    for face in bm.faces:
        child_count = len(face.verts) * face_multiplier
        face_ranges[face.index] = (one_copy_face_count, child_count)
        one_copy_face_count += child_count
    if one_copy_face_count != len(mesh.polygons):
        return None

    # A supported Subdivision Surface stack keeps each source face's children
    # in a deterministic contiguous range.
    faces = []
    for source_index in sorted(face_filter):
        face_range = face_ranges.get(source_index)
        if face_range is None:
            continue
        range_start, child_count = face_range
        for polygon_index in range(range_start, range_start + child_count):
            polygon = mesh.polygons[polygon_index]
            triangles = _polygon_triangles(mesh, polygon)
            if triangles:
                faces.append((source_index, triangles, polygon.normal.copy()))

    edge_child_count = 2 ** subdivision_levels
    edges = []
    for source_index in sorted(edge_filter):
        start = source_index * edge_child_count
        end = start + edge_child_count
        if source_index < 0 or end > len(mesh.edges):
            continue
        edges.extend(
            _evaluated_edge_geometry(mesh, edge_index, source_index)
            for edge_index in range(start, end)
        )
    return {FACE: faces, EDGE: edges, VERTEX: []}, "SUBDIVISION_SPARSE"


def _cage_overlay_geometry(bm: bmesh.types.BMesh, source_filters=None):
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    source_filters = source_filters or {}
    face_filter = source_filters.get(FACE)
    edge_filter = source_filters.get(EDGE)
    vertex_filter = source_filters.get(VERTEX)
    face_triangles = defaultdict(list)
    for loops in bm.calc_loop_triangles():
        face_index = loops[0].face.index
        if face_filter is None or face_index in face_filter:
            face_triangles[face_index].append(tuple(loop.vert.co.copy() for loop in loops))

    faces = []
    face_indices = range(len(bm.faces)) if face_filter is None else sorted(face_filter)
    for face_index in face_indices:
        if not (0 <= face_index < len(bm.faces)):
            continue
        face = bm.faces[face_index]
        triangles = face_triangles.get(face.index)
        if triangles:
            faces.append((face.index, triangles, face.normal.copy()))

    edges = []
    edge_indices = range(len(bm.edges)) if edge_filter is None else sorted(edge_filter)
    for edge_index in edge_indices:
        if not (0 <= edge_index < len(bm.edges)):
            continue
        edge = bm.edges[edge_index]
        edges.append(_edge_geometry(edge.index, *edge.verts))

    vertex_indices = range(len(bm.verts)) if vertex_filter is None else sorted(vertex_filter)
    vertices = [
        (index, bm.verts[index].co.copy(), bm.verts[index].normal.copy())
        for index in vertex_indices
        if 0 <= index < len(bm.verts)
    ]
    return {FACE: faces, EDGE: edges, VERTEX: vertices}, "CAGE"


def evaluated_overlay_geometry(
    obj: bpy.types.Object, bm: bmesh.types.BMesh, settings, source_filters=None
):
    """Copy drawable geometry from the modifier-evaluated surface into stable records."""
    try:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_object = obj.evaluated_get(depsgraph)
        mesh = evaluated_object.data
        if not isinstance(mesh, bpy.types.Mesh) or not mesh.vertices:
            raise RuntimeError("evaluated mesh is empty")
        if not _modifier_stack_supports_evaluated_mapping(obj):
            raise RuntimeError("modifier stack has no reliable annotation provenance")

        if source_filters is None:
            required_types = {FACE, EDGE, VERTEX}
        else:
            required_types = {
                element_type
                for element_type in (FACE, EDGE, VERTEX)
                if source_filters.get(element_type)
            }
        if not required_types:
            return {FACE: [], EDGE: [], VERTEX: []}

        if source_filters is not None:
            sparse_result = _sparse_exact_overlay_geometry(obj, bm, mesh, source_filters)
            if sparse_result is not None:
                geometry, mapping_mode = sparse_result
                debug_log(
                    settings,
                    f"Overlay uses evaluated mesh ({mapping_mode} mapping): "
                    f"{len(mesh.vertices)} verts, {len(mesh.edges)} edges, "
                    f"{len(mesh.polygons)} faces",
                )
                return geometry

        source_maps = _evaluated_source_maps(
            obj,
            bm,
            mesh,
            required_types=required_types,
            source_filters=source_filters,
        )
        if source_maps is None:
            raise RuntimeError("evaluated topology does not match a supported mapping")
        face_sources, edge_sources, vertex_sources, mapping_mode = source_maps
        if source_filters is None:
            face_filter = edge_filter = vertex_filter = None
        else:
            face_filter = source_filters.get(FACE, set())
            edge_filter = source_filters.get(EDGE, set())
            vertex_filter = source_filters.get(VERTEX, set())

        faces = []
        if FACE in required_types:
            for polygon in mesh.polygons:
                source_index = face_sources[polygon.index]
                if (
                    source_index is not None
                    and (face_filter is None or source_index in face_filter)
                ):
                    triangles = _polygon_triangles(mesh, polygon)
                    if triangles:
                        faces.append((source_index, triangles, polygon.normal.copy()))

        edges = []
        if EDGE in required_types:
            for edge in mesh.edges:
                source_index = edge_sources[edge.index]
                if source_index is None or (
                    edge_filter is not None and source_index not in edge_filter
                ):
                    continue
                edges.append(
                    _evaluated_edge_geometry(mesh, edge.index, source_index)
                )

        vertices = []
        if VERTEX in required_types:
            for vertex in mesh.vertices:
                source_index = vertex_sources[vertex.index]
                if source_index is not None and (
                    vertex_filter is None or source_index in vertex_filter
                ):
                    vertices.append((source_index, vertex.co.copy(), vertex.normal.copy()))

        debug_log(
            settings,
            f"Overlay uses evaluated mesh ({mapping_mode} mapping): "
            f"{len(mesh.vertices)} verts, {len(mesh.edges)} edges, {len(mesh.polygons)} faces",
        )
        return {FACE: faces, EDGE: edges, VERTEX: vertices}
    except Exception as exc:
        debug_log(settings, f"Evaluated overlay unavailable; using edit cage: {exc}")
        return _cage_overlay_geometry(bm, source_filters=source_filters)[0]


def _coordinate_key(coordinate):
    return tuple(round(value, 7) for value in coordinate)


def ordered_edge_chains(records):
    """Split evaluated descendants into connected, consistently oriented chains."""
    if not records:
        return []
    if len(records) == 1:
        return [records]
    endpoint_keys = []
    adjacency = defaultdict(list)
    for index, (p0, p1, _normal0, _normal1) in enumerate(records):
        keys = (_coordinate_key(p0), _coordinate_key(p1))
        endpoint_keys.append(keys)
        adjacency[keys[0]].append(index)
        adjacency[keys[1]].append(index)

    unused = set(range(len(records)))
    chains = []
    while unused:
        start_key = None
        for index in unused:
            for key in endpoint_keys[index]:
                if sum(1 for candidate in adjacency[key] if candidate in unused) == 1:
                    start_key = key
                    break
            if start_key is not None:
                break
        if start_key is None:
            first = next(iter(unused))
            start_key = endpoint_keys[first][0]

        chain = []
        current_key = start_key
        while True:
            candidates = [index for index in adjacency[current_key] if index in unused]
            if not candidates:
                break
            index = candidates[0]
            unused.remove(index)
            p0, p1, normal0, normal1 = records[index]
            key0, key1 = endpoint_keys[index]
            if key0 == current_key:
                chain.append((p0, p1, normal0, normal1))
                current_key = key1
            else:
                chain.append((p1, p0, normal1, normal0))
                current_key = key0
        if chain:
            chains.append(chain)
    return chains


def _consume_chain_start(segments, distance):
    remaining = max(0.0, distance)
    trimmed = []
    for p0, p1 in segments:
        direction = p1 - p0
        length = direction.length
        if length <= 1e-9:
            continue
        if remaining >= length:
            remaining -= length
            continue
        if remaining > 0.0:
            p0 = p0 + direction * (remaining / length)
            remaining = 0.0
        trimmed.append((p0, p1))
    return trimmed


def trim_edge_chain(segments, trim_fraction):
    """Trim the two ends of a complete evaluated edge chain without internal gaps."""
    total_length = sum((p1 - p0).length for p0, p1 in segments)
    if total_length <= 1e-9 or trim_fraction <= 0.0:
        return segments
    trim_distance = min(total_length * trim_fraction, total_length * 0.499)
    trimmed = _consume_chain_start(segments, trim_distance)
    reversed_segments = [(p1, p0) for p0, p1 in reversed(trimmed)]
    reversed_segments = _consume_chain_start(reversed_segments, trim_distance)
    return [(p1, p0) for p0, p1 in reversed(reversed_segments)]
