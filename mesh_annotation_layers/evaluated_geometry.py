"""Map source annotations onto Blender's evaluated mesh."""

from collections import Counter, defaultdict

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from .constants import EDGE, FACE, VERTEX
from .model import debug_log


def _modifier_visible_for_overlay(obj: bpy.types.Object, modifier) -> bool:
    if not modifier.show_viewport:
        return False
    return obj.mode != "EDIT" or modifier.show_in_editmode


def _overlay_subdivision_levels(obj: bpy.types.Object) -> int:
    """Return visible subdivision steps for the object's current interaction mode."""
    levels = 0
    for modifier in obj.modifiers:
        if modifier.type != "SUBSURF":
            continue
        if not _modifier_visible_for_overlay(obj, modifier):
            continue
        levels += max(0, int(modifier.levels))
    return levels


def _overlay_mirror_copies(obj: bpy.types.Object) -> int:
    """Return the theoretical face-copy count for visible Mirror modifiers."""
    copies = 1
    for modifier in obj.modifiers:
        if modifier.type != "MIRROR":
            continue
        if not _modifier_visible_for_overlay(obj, modifier):
            continue
        axis_count = sum(1 for enabled in modifier.use_axis if enabled)
        copies *= 2 ** axis_count
    return copies


def _evaluated_edge_faces(mesh: bpy.types.Mesh):
    edge_faces = [[] for _edge in mesh.edges]
    for polygon in mesh.polygons:
        loop_end = polygon.loop_start + polygon.loop_total
        for loop_index in range(polygon.loop_start, loop_end):
            edge_index = mesh.loops[loop_index].edge_index
            edge_faces[edge_index].append(polygon.index)
    return edge_faces


def _overlay_mirror_transforms(obj: bpy.types.Object):
    transforms = []
    for modifier in obj.modifiers:
        if modifier.type != "MIRROR":
            continue
        if not _modifier_visible_for_overlay(obj, modifier):
            continue
        axes = [index for index, enabled in enumerate(modifier.use_axis) if enabled]
        if not axes:
            continue
        mirror_object = modifier.mirror_object
        if mirror_object is None:
            to_mirror_space = None
            from_mirror_space = None
        else:
            try:
                to_mirror_space = mirror_object.matrix_world.inverted() @ obj.matrix_world
                from_mirror_space = obj.matrix_world.inverted() @ mirror_object.matrix_world
            except ValueError:
                to_mirror_space = None
                from_mirror_space = None
        transforms.append((axes, to_mirror_space, from_mirror_space))
    return transforms


def _mirror_point_variants(coordinate: Vector, mirror_transforms):
    variants = [coordinate.copy()]
    for axes, to_mirror_space, from_mirror_space in mirror_transforms:
        expanded = []
        for variant in variants:
            mirror_coordinate = to_mirror_space @ variant if to_mirror_space else variant.copy()
            for mask in range(1 << len(axes)):
                reflected = mirror_coordinate.copy()
                for bit, axis in enumerate(axes):
                    if mask & (1 << bit):
                        reflected[axis] *= -1.0
                expanded.append(from_mirror_space @ reflected if from_mirror_space else reflected)
        unique = {}
        for variant in expanded:
            key = tuple(round(value, 7) for value in variant)
            unique[key] = variant
        variants = list(unique.values())
    return variants


def _nearest_face_sources(bm: bmesh.types.BMesh, mesh: bpy.types.Mesh):
    if not bm.faces:
        return [None] * len(mesh.polygons)
    tree = BVHTree.FromBMesh(bm)
    sources = []
    for polygon in mesh.polygons:
        nearest = tree.find_nearest(polygon.center)
        sources.append(nearest[2] if nearest and nearest[2] is not None else None)
    return sources


def _nearest_edge_sources(
    obj,
    bm: bmesh.types.BMesh,
    mesh: bpy.types.Mesh,
    face_sources,
    edge_faces,
    source_edge_filter=None,
):
    source_candidates = defaultdict(list)
    source_midpoints = {}
    mirror_transforms = _overlay_mirror_transforms(obj)
    for edge in bm.edges:
        if source_edge_filter is not None and edge.index not in source_edge_filter:
            continue
        signature = tuple(sorted(face.index for face in edge.link_faces))
        source_candidates[signature].append(edge.index)
        midpoint = (edge.verts[0].co + edge.verts[1].co) * 0.5
        source_midpoints[edge.index] = _mirror_point_variants(midpoint, mirror_transforms)

    sources = []
    for edge in mesh.edges:
        linked_faces = edge_faces[edge.index]
        mapped_faces = [
            face_sources[index]
            for index in linked_faces
            if face_sources[index] is not None
        ]
        unique_faces = tuple(sorted(set(mapped_faces)))

        # Two evaluated faces mapped to one source face meet on an edge created
        # inside that face. It is not a descendant of a source edge.
        if len(linked_faces) >= 2 and len(unique_faces) <= 1:
            sources.append(None)
            continue

        candidates = source_candidates.get(unique_faces, ())
        if not candidates:
            sources.append(None)
            continue
        midpoint = (mesh.vertices[edge.vertices[0]].co + mesh.vertices[edge.vertices[1]].co) * 0.5
        source_index = min(
            candidates,
            key=lambda index: min(
                (midpoint - source_midpoint).length_squared
                for source_midpoint in source_midpoints[index]
            ),
        )
        sources.append(source_index)
    return sources


def _topology_vertex_sources(
    obj,
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

    mirror_transforms = _overlay_mirror_transforms(obj)
    chosen = {}
    fallback_tree = None
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
        targets = _mirror_point_variants(source_vertex.co, mirror_transforms)
        candidates = set()
        if len(incident_sets) >= 2:
            candidates = set.intersection(*incident_sets)
        elif len(incident_sets) == 1:
            source_edge_index = incident_edges[0][0]
            degrees = source_edge_degrees.get(source_edge_index, {})
            candidates = {index for index, degree in degrees.items() if degree == 1}

        if candidates:
            if len(incident_sets) >= 2:
                evaluated_indices = candidates
            else:
                evaluated_indices = {
                    min(
                        candidates,
                        key=lambda index: (mesh.vertices[index].co - target).length_squared,
                    )
                    for target in targets
                }
            for evaluated_index in evaluated_indices:
                distance = min(
                    (mesh.vertices[evaluated_index].co - target).length_squared
                    for target in targets
                )
                previous = chosen.get(evaluated_index)
                if previous is None or distance < previous[0]:
                    chosen[evaluated_index] = (distance, source_vertex.index)
            continue

        if fallback_tree is None:
            fallback_tree = KDTree(len(mesh.vertices))
            for vertex in mesh.vertices:
                fallback_tree.insert(vertex.co, vertex.index)
            fallback_tree.balance()
        for target in targets:
            _co, evaluated_index, distance = fallback_tree.find(target)
            previous = chosen.get(evaluated_index)
            if previous is None or distance < previous[0]:
                chosen[evaluated_index] = (distance, source_vertex.index)

    for evaluated_index, (_distance, source_index) in chosen.items():
        sources[evaluated_index] = source_index
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
    if needs_vertex_sources and vertex_filter:
        required_source_edges = {
            edge.index
            for vertex_index in vertex_filter
            if 0 <= vertex_index < len(bm.verts)
            for edge in bm.verts[vertex_index].link_edges
        }
    else:
        required_source_edges = source_filters.get(EDGE) if EDGE in required_types else None

    source_counts = (len(bm.verts), len(bm.edges), len(bm.faces))
    evaluated_counts = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))
    if source_counts == evaluated_counts:
        return (
            list(range(source_counts[2])) if needs_face_sources else None,
            list(range(source_counts[1])) if needs_edge_sources else None,
            list(range(source_counts[0])) if needs_vertex_sources else None,
            "DIRECT",
        )

    subdivision_levels = _overlay_subdivision_levels(obj)
    mirror_copies = _overlay_mirror_copies(obj)
    mapping_mode = None
    if subdivision_levels > 0 or mirror_copies > 1:
        face_multiplier = 1 if subdivision_levels == 0 else 4 ** (subdivision_levels - 1)
        one_copy_face_sources = []
        for face in bm.faces:
            child_count = 1 if subdivision_levels == 0 else len(face.verts) * face_multiplier
            one_copy_face_sources.extend([face.index] * child_count)
        face_sources = one_copy_face_sources * mirror_copies
        if len(face_sources) == len(mesh.polygons):
            if mirror_copies == 1:
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
                            obj,
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

            mapping_mode = (
                "MIRROR_SUBDIVISION" if subdivision_levels > 0 else "MIRROR"
            )

    if mapping_mode is None:
        face_sources = _nearest_face_sources(bm, mesh) if needs_face_sources else None
        mapping_mode = "NEAREST"
    edge_sources = None
    vertex_sources = None
    if needs_edge_sources:
        edge_faces = _evaluated_edge_faces(mesh)
        edge_sources = _nearest_edge_sources(
            obj,
            bm,
            mesh,
            face_sources,
            edge_faces,
            source_edge_filter=required_source_edges,
        )
    if needs_vertex_sources:
        vertex_sources = _topology_vertex_sources(
            obj,
            bm,
            mesh,
            edge_sources,
            source_vertex_filter=vertex_filter,
        )
    return face_sources, edge_sources, vertex_sources, mapping_mode


def _polygon_triangles(mesh: bpy.types.Mesh, polygon):
    coordinates = [mesh.vertices[index].co.copy() for index in polygon.vertices]
    if len(coordinates) < 3:
        return []
    root = coordinates[0]
    return [
        (root, coordinates[index], coordinates[index + 1])
        for index in range(1, len(coordinates) - 1)
    ]


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


def _subdivision_vertex_geometry(
    obj,
    bm,
    mesh,
    vertex_filter,
    face_ranges,
    one_copy_face_count,
    mirror_copies,
):
    """Locate source-vertex descendants by intersecting adjacent face patches."""
    geometry = []
    mirror_transforms = _overlay_mirror_transforms(obj)
    bm.verts.ensure_lookup_table()
    for source_index in sorted(vertex_filter):
        if not (0 <= source_index < len(bm.verts)):
            continue
        source_vertex = bm.verts[source_index]
        linked_faces = [face.index for face in source_vertex.link_faces]
        targets = _mirror_point_variants(source_vertex.co, mirror_transforms)
        used_vertices = set()
        for copy_index in range(mirror_copies):
            patch_sets = []
            for face_index in linked_faces:
                face_range = face_ranges.get(face_index)
                if face_range is None:
                    continue
                range_start, child_count = face_range
                copy_start = copy_index * one_copy_face_count + range_start
                patch_vertices = set()
                for polygon_index in range(copy_start, copy_start + child_count):
                    patch_vertices.update(mesh.polygons[polygon_index].vertices)
                if patch_vertices:
                    patch_sets.append(patch_vertices)
            if not patch_sets:
                continue
            candidates = set.intersection(*patch_sets)
            if not candidates:
                continue
            evaluated_index = min(
                candidates,
                key=lambda index: min(
                    (mesh.vertices[index].co - target).length_squared
                    for target in targets
                ),
            )
            if evaluated_index in used_vertices:
                continue
            used_vertices.add(evaluated_index)
            vertex = mesh.vertices[evaluated_index]
            geometry.append((source_index, vertex.co.copy(), vertex.normal.copy()))
    return geometry


def _sparse_exact_overlay_geometry(obj, bm, mesh, source_filters):
    """Read only annotated evaluated elements when modifier ordering is deterministic."""
    face_filter = source_filters.get(FACE, set())
    edge_filter = source_filters.get(EDGE, set())
    vertex_filter = source_filters.get(VERTEX, set())
    source_counts = (len(bm.verts), len(bm.edges), len(bm.faces))
    evaluated_counts = (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))

    if source_counts == evaluated_counts:
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
    mirror_copies = _overlay_mirror_copies(obj)
    if subdivision_levels == 0 and mirror_copies == 1:
        return None

    face_multiplier = 1 if subdivision_levels == 0 else 4 ** (subdivision_levels - 1)
    face_ranges = {}
    one_copy_face_count = 0
    for face in bm.faces:
        child_count = 1 if subdivision_levels == 0 else len(face.verts) * face_multiplier
        face_ranges[face.index] = (one_copy_face_count, child_count)
        one_copy_face_count += child_count
    if one_copy_face_count * mirror_copies != len(mesh.polygons):
        return None

    # Face ordering is stable through Mirror and Subdivision Surface, so an
    # annotated cage face can jump directly to its evaluated child range.
    faces = []
    for source_index in sorted(face_filter):
        face_range = face_ranges.get(source_index)
        if face_range is None:
            continue
        range_start, child_count = face_range
        for copy_index in range(mirror_copies):
            copy_start = copy_index * one_copy_face_count + range_start
            for polygon_index in range(copy_start, copy_start + child_count):
                polygon = mesh.polygons[polygon_index]
                triangles = _polygon_triangles(mesh, polygon)
                if triangles:
                    faces.append((source_index, triangles, polygon.normal.copy()))

    # Mirrored edge descendants still need the generic topology matcher.
    if mirror_copies > 1 and edge_filter:
        return None

    edge_child_count = 1 if subdivision_levels == 0 else 2 ** subdivision_levels
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
    vertices = _subdivision_vertex_geometry(
        obj,
        bm,
        mesh,
        vertex_filter,
        face_ranges,
        one_copy_face_count,
        mirror_copies,
    )
    mode = "MIRROR_SUBDIVISION_SPARSE" if mirror_copies > 1 else "SUBDIVISION_SPARSE"
    return {FACE: faces, EDGE: edges, VERTEX: vertices}, mode


def _cage_overlay_geometry(bm: bmesh.types.BMesh, source_filters=None):
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
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_object = obj.evaluated_get(depsgraph)
        mesh = evaluated_object.data
        if not isinstance(mesh, bpy.types.Mesh) or not mesh.vertices:
            raise RuntimeError("evaluated mesh is empty")

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

        face_sources, edge_sources, vertex_sources, mapping_mode = (
            _evaluated_source_maps(
                obj,
                bm,
                mesh,
                required_types=required_types,
                source_filters=source_filters,
            )
        )
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
