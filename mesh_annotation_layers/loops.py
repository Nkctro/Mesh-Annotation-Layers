"""Face loops, edge loops, and vertex path derivation."""

import bmesh
import bpy

from .constants import EDGE, FACE, VERTEX
from .i18n import tr
from .model import debug_log, ensure_lookup_tables


def collect_face_loop_faces(context, obj, bm, settings):
    ensure_lookup_tables(bm, FACE)
    bm.edges.ensure_lookup_table()
    selected_faces = [face for face in bm.faces if face.select]
    if len(selected_faces) < 2:
        msg = tr('Select at least two faces to define the loop')
        return set(), msg
    required_indices = {face.index for face in selected_faces}
    loop_candidates = []
    processed_edges = set()

    def gather_loop(face, other, edge):
        loop = set()
        loop |= _walk_face_loop(face, other, edge)
        loop |= _walk_face_loop(other, face, edge)
        loop.add(face)
        loop.add(other)
        return loop

    # Every valid result must pass through the first selected face. Seeding from
    # every selected face repeats the same full loop walks on large selections.
    for face in selected_faces[:1]:
        if len(face.verts) != 4:
            continue
        for edge in face.edges:
            if len(edge.link_faces) != 2:
                continue
            linked = [f for f in edge.link_faces if f is not face]
            if not linked:
                continue
            other = linked[0]
            edge_key = (edge.index, tuple(sorted((face.index, other.index))))
            if edge_key in processed_edges:
                continue
            processed_edges.add(edge_key)
            loop = gather_loop(face, other, edge)
            if loop:
                loop_candidates.append(loop)

    if not loop_candidates:
        msg = tr('Unable to derive a face loop from the selection')
        return set(), msg

    unique_candidates = []
    seen_signatures = set()
    for loop in loop_candidates:
        signature = frozenset(face.index for face in loop)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique_candidates.append(loop)
    matching_loops = []
    for loop in unique_candidates:
        loop_indices = {face.index for face in loop}
        if required_indices.issubset(loop_indices):
            matching_loops.append(loop)
    if not matching_loops:
        msg = tr('No face loop passes through every selected face')
        return set(), msg
    if len(matching_loops) > 1:
        msg = tr('Multiple face loops detected; refine your selection')
        return set(), msg
    final_loop = matching_loops[0]
    for face in bm.faces:
        face.select = face in final_loop

    debug_log(settings, f"collect_face_loop_faces gathered {len(final_loop)} faces")
    return final_loop, None


def _walk_face_loop(start_face, previous_face, shared_edge):
    loop = set()
    current_face = start_face
    prev_face = previous_face
    incoming_edge = shared_edge
    while current_face not in loop:
        loop.add(current_face)
        opposite_edge = _find_opposite_edge(current_face, incoming_edge)
        if opposite_edge is None:
            break
        linked_faces = [f for f in opposite_edge.link_faces if f is not current_face]
        if not linked_faces:
            break
        next_face = linked_faces[0]
        if next_face is prev_face:
            break
        prev_face = current_face
        incoming_edge = opposite_edge
        current_face = next_face
    return loop


def _find_opposite_edge(face: bmesh.types.BMFace, incoming_edge: bmesh.types.BMEdge):
    incoming_vertices = {v.index for v in incoming_edge.verts}
    for edge in face.edges:
        if edge is incoming_edge:
            continue
        if incoming_vertices.isdisjoint({v.index for v in edge.verts}):
            return edge
    return None


def _select_loop_via_builtin(context, obj, element_type: str):
    mesh = obj.data
    tool_settings = context.tool_settings
    original_mode = tuple(tool_settings.mesh_select_mode)
    target_mode = {
        VERTEX: (True, False, False),
        EDGE: (False, True, False),
        FACE: (False, False, True),
    }[element_type]
    try:
        if original_mode != target_mode:
            tool_settings.mesh_select_mode = target_mode
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        window = context.window
        if window is None:
            return False, tr('No active 3D View found')
        screen = window.screen
        last_error = None
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is None:
                continue
            override_kwargs = {
                "window": window,
                "screen": screen,
                "area": area,
                "region": region,
                "mode": "EDIT_MESH",
                "object": obj,
                "active_object": obj,
            }
            try:
                with context.temp_override(**override_kwargs):
                    result = bpy.ops.mesh.loop_multi_select(ring=False)
            except (RuntimeError, ValueError) as exc:
                last_error = str(exc)
                continue
            if "FINISHED" in result:
                bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
                return True, None
        message = last_error or tr('Unable to resolve a loop from the current selection')
        return False, message
    except Exception as exc:
        return False, str(exc)
    finally:
        if tool_settings.mesh_select_mode != original_mode:
            tool_settings.mesh_select_mode = original_mode
def collect_edge_loop_edges(context, obj, bm, settings):
    ensure_lookup_tables(bm, EDGE)
    bm.edges.ensure_lookup_table()
    selected_edges = [edge for edge in bm.edges if edge.select]
    if not selected_edges:
        msg = tr('Select at least one edge to derive a loop')
        return set(), msg
    mesh = obj.data
    original_selection = {edge.index for edge in bm.edges if edge.select}
    active_index = selected_edges[0].index
    for edge in bm.edges:
        edge.select = False
    bm.select_history.clear()
    bm.edges[active_index].select = True
    bm.select_history.add(bm.edges[active_index])
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    ok, message = _select_loop_via_builtin(context, obj, EDGE)
    if not ok:
        bm_restore = bmesh.from_edit_mesh(mesh)
        ensure_lookup_tables(bm_restore, EDGE)
        for edge in bm_restore.edges:
            edge.select = edge.index in original_selection
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        return set(), message
    bm_after = bmesh.from_edit_mesh(mesh)
    ensure_lookup_tables(bm_after, EDGE)
    loop_edges = {edge for edge in bm_after.edges if edge.select}
    loop_indices = {edge.index for edge in loop_edges}
    if not loop_edges:
        for edge in bm_after.edges:
            edge.select = edge.index in original_selection
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        msg = tr('Unable to resolve an edge loop')
        return set(), msg
    if not original_selection.issubset(loop_indices):
        for edge in bm_after.edges:
            edge.select = edge.index in original_selection
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        msg = tr('Selected edges are not on the same loop')
        return set(), msg
    debug_log(settings, f"collect_edge_loop_edges gathered {len(loop_edges)} edges")
    return loop_edges, None


def _gather_vertex_path_components(bm, vertex_indices):
    components = []
    visited = set()
    for index in vertex_indices:
        if index in visited:
            continue
        component = set()
        stack = [index]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            vert = bm.verts[current]
            for edge in vert.link_edges:
                for other in edge.verts:
                    other_index = other.index
                    if other_index == current or other_index not in vertex_indices:
                        continue
                    stack.append(other_index)
        if component:
            components.append(component)
    return components


def _component_is_vertex_path(bm, component):
    if not component:
        return False
    if len(component) == 1:
        return True
    endpoints = 0
    for index in component:
        vert = bm.verts[index]
        neighbours = {
            other.index
            for edge in vert.link_edges
            for other in edge.verts
            if other.index != index and other.index in component
        }
        degree = len(neighbours)
        if degree > 2:
            return False
        if degree == 1:
            endpoints += 1
        elif degree == 0:
            return False
    return endpoints in {0, 2}


def collect_vertex_loop_vertices(context, obj, bm, settings):
    ensure_lookup_tables(bm, VERTEX)
    bm.edges.ensure_lookup_table()
    selected_vertices = [vert for vert in bm.verts if vert.select]
    if len(selected_vertices) < 2:
        msg = tr('Select at least two vertices to derive a loop')
        return set(), msg
    mesh = obj.data
    target_indices = [vert.index for vert in selected_vertices]
    required = set(target_indices)
    original_selection = {vert.index for vert in bm.verts if vert.select}
    chosen_loop = None
    last_message = None
    for candidate_index in target_indices:
        bm_candidate = bmesh.from_edit_mesh(mesh)
        ensure_lookup_tables(bm_candidate, VERTEX)
        for vert in bm_candidate.verts:
            vert.select = False
        bm_candidate.select_history.clear()
        candidate = bm_candidate.verts[candidate_index]
        candidate.select = True
        bm_candidate.select_history.add(candidate)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        ok, message = _select_loop_via_builtin(context, obj, VERTEX)
        if not ok:
            last_message = message
            continue
        bm_after = bmesh.from_edit_mesh(mesh)
        ensure_lookup_tables(bm_after, VERTEX)
        loop_indices = {vert.index for vert in bm_after.verts if vert.select}
        components = _gather_vertex_path_components(bm_after, loop_indices)
        valid_components = [
            component
            for component in components
            if _component_is_vertex_path(bm_after, component)
        ]
        containing = [comp for comp in valid_components if required.issubset(comp)]
        if not containing:
            last_message = tr('No vertex loop passes through every selected vertex')
            continue
        if len(containing) > 1:
            last_message = tr('Multiple vertex loops detected; refine your selection')
            continue
        chosen_loop = set(containing[0])
        break
    if chosen_loop is None:
        bm_restore = bmesh.from_edit_mesh(mesh)
        ensure_lookup_tables(bm_restore, VERTEX)
        for vert in bm_restore.verts:
            vert.select = vert.index in original_selection
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        return set(), last_message or tr('No vertex loop passes through every selected vertex')
    bm_final = bmesh.from_edit_mesh(mesh)
    ensure_lookup_tables(bm_final, VERTEX)
    loop_vertices = {bm_final.verts[index] for index in chosen_loop}
    for vert in bm_final.verts:
        vert.select = vert.index in chosen_loop
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    debug_log(settings, f"collect_vertex_loop_vertices gathered {len(loop_vertices)} vertices")
    return loop_vertices, None
