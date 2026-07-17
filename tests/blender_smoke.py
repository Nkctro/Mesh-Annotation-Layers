"""Run with: blender --background --factory-startup --python tests/blender_smoke.py"""

import importlib
import importlib.util
import json
import os
import sys
import time
import types
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import bmesh
import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
GRID_SEGMENTS = int(os.environ.get("MAL_GRID_SEGMENTS", "28"))

import mesh_annotation_layers as addon
from mesh_annotation_layers import evaluated_geometry, i18n, model, operators, overlay, ui
from mesh_annotation_layers.constants import EDGE, FACE, VERTEX, element_spec


class UILayoutProbe:
    """Minimal UILayout stand-in that executes menu and panel draw code."""

    def __init__(self):
        self.entries = []
        self.enabled = True

    def row(self, **_kwargs):
        return self

    def column(self, **_kwargs):
        return self

    def box(self):
        return self

    def operator(self, operator_id, **kwargs):
        properties = SimpleNamespace()
        self.entries.append(("operator", operator_id, kwargs, properties))
        return properties

    def menu(self, menu_id, **kwargs):
        self.entries.append(("menu", menu_id, kwargs, None))

    def label(self, **kwargs):
        self.entries.append(("label", None, kwargs, None))

    def separator(self, **_kwargs):
        self.entries.append(("separator", None, {}, None))

    def prop(self, *_args, **_kwargs):
        return None

    def template_list(self, *_args, **_kwargs):
        return None


@contextmanager
def overlay_gpu_stub():
    """Keep geometry tests runnable when Blender has no background GPU context."""
    original_shader_builder = overlay.gpu.shader.from_builtin
    original_batch_builder = overlay.batch_for_shader
    try:
        overlay.gpu.shader.from_builtin = lambda _name: object()
        overlay.batch_for_shader = lambda *_args, **_kwargs: object()
        yield
    finally:
        overlay.gpu.shader.from_builtin = original_shader_builder
        overlay.batch_for_shader = original_batch_builder


def test_extension_namespace_package_name():
    package_name = "bl_ext.user_default.mesh_annotation_layers"
    for namespace in ("bl_ext", "bl_ext.user_default"):
        if namespace not in sys.modules:
            module = types.ModuleType(namespace)
            module.__path__ = []
            sys.modules[namespace] = module

    spec = importlib.util.spec_from_file_location(
        package_name,
        ROOT / "mesh_annotation_layers" / "__init__.py",
        submodule_search_locations=[str(ROOT / "mesh_annotation_layers")],
    )
    namespaced_addon = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = namespaced_addon
    try:
        spec.loader.exec_module(namespaced_addon)
        assert namespaced_addon.preferences.ADDON_PACKAGE == package_name
        assert (
            namespaced_addon.preferences.MeshAnnotationPreferences.bl_idname
            == package_name
        )
        namespaced_addon.register()
        assert hasattr(bpy.types.Object, "mesh_annotations")
        namespaced_addon.unregister()
        assert not hasattr(bpy.types.Object, "mesh_annotations")
    finally:
        for module_name in list(sys.modules):
            if module_name == package_name or module_name.startswith(
                f"{package_name}."
            ):
                del sys.modules[module_name]


def test_entry_point_reloads_all_submodules():
    def owned_symbols(module):
        return {
            name: value
            for name, value in vars(module).items()
            if callable(value) and getattr(value, "__module__", None) == module.__name__
        }

    symbols = {
        name: owned_symbols(getattr(addon, name))
        for name in addon._SUBMODULE_NAMES
    }
    assert all(symbols.values())
    importlib.reload(addon)
    for module_name, previous in symbols.items():
        current = owned_symbols(getattr(addon, module_name))
        common_names = previous.keys() & current.keys()
        assert common_names
        assert all(previous[name] is not current[name] for name in common_names)


def create_grid_object():
    mesh = bpy.data.meshes.new("AnnotationSmokeMesh")
    source = bmesh.new()
    bmesh.ops.create_grid(
        source,
        x_segments=GRID_SEGMENTS,
        y_segments=GRID_SEGMENTS,
        size=2.0,
    )
    source.to_mesh(mesh)
    source.free()

    obj = bpy.data.objects.new("AnnotationSmokeObject", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def create_two_triangle_object(name="TwoTriangleAnnotation"):
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)),
        (),
        ((0, 1, 2), (0, 2, 3)),
    )
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


def create_disconnected_triangle_object(name="DisconnectedTriangles"):
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (3.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (3.0, 1.0, 0.0),
        ),
        (),
        ((0, 1, 2), (3, 4, 5)),
    )
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


def remove_object_and_orphaned_mesh(obj):
    mesh = obj.data
    object_name = obj.name
    if bpy.data.objects.get(object_name) is obj:
        bpy.data.objects.remove(obj, do_unlink=True)
    if mesh.users == 0 and bpy.data.meshes.get(mesh.name) is mesh:
        bpy.data.meshes.remove(mesh)


def rotate_two_triangle_diagonal(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    diagonal = next(edge for edge in bm.edges if len(edge.link_faces) == 2)
    result = bmesh.ops.rotate_edges(bm, edges=[diagonal], use_ccw=False)
    assert result.get("edges")
    bm.faces.ensure_lookup_table()
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def bmesh_stack_payloads(mesh, element_type):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    try:
        model.ensure_lookup_tables(bm, element_type)
        container = model.element_container(bm, element_type)
        stack_layer = container.layers.string.get(
            element_spec(element_type).stack_layer
        )
        if stack_layer is None:
            return None
        return tuple(bytes(elem[stack_layer]) for elem in container)
    finally:
        bm.free()


def test_binary_stack_contract():
    boundary_ids = [1, 127, 128, 16_384, 2_147_483_647]
    payload = model.encode_layers(boundary_ids)
    assert model.decode_layer_bytes(payload) == boundary_ids
    assert len(payload) <= 255
    for damaged in (payload[:-1], payload[:-5] + b"xxxxx"):
        try:
            model.decode_layer_bytes(damaged)
        except model.StackEncodingError:
            pass
        else:
            raise AssertionError("damaged stack was accepted")

    dense_ids = [*range(1, 185), 16_384]
    dense_payload = model.encode_layers(dense_ids)
    assert len(dense_payload) == 255
    mesh = bpy.data.meshes.new("BinaryStackRoundTrip")
    bm = bmesh.new()
    bm.verts.new((0.0, 0.0, 0.0))
    bm.verts.ensure_lookup_table()
    stack_layer = bm.verts.layers.string.new("binary_stack")
    bm.verts[0][stack_layer] = dense_payload
    bm.to_mesh(mesh)
    bm.free()
    roundtrip = bmesh.new()
    try:
        roundtrip.from_mesh(mesh)
        roundtrip.verts.ensure_lookup_table()
        restored_layer = roundtrip.verts.layers.string.get("binary_stack")
        restored = bytes(roundtrip.verts[0][restored_layer])
        assert len(restored) == len(dense_payload)
        assert model.decode_layer_bytes(restored) == dense_ids
    finally:
        roundtrip.free()
        bpy.data.meshes.remove(mesh)

    oversized = list(range(1, 220))
    bm = bmesh.new()
    try:
        bm.verts.new((0.0, 0.0, 0.0))
        bm.verts.ensure_lookup_table()
        try:
            model.ensure_annotation_stack(
                bm,
                VERTEX,
                {"0": oversized},
            )
        except model.StackCapacityError:
            pass
        else:
            raise AssertionError("over-capacity stack was accepted")
        meta = element_spec(VERTEX)
        assert bm.verts.layers.string.get(meta.stack_layer) is None
    finally:
        bm.free()

    bm = bmesh.new()
    try:
        bm.verts.new((0.0, 0.0, 0.0))
        bm.verts.index_update()
        bm.verts.ensure_lookup_table()
        legacy_layer = bm.verts.layers.string.new("legacy_stack")
        known_ids = list(range(1, 151))
        legacy_prefix = model._legacy_prefix(known_ids)
        legacy_bytes = ",".join(
            str(layer_id) for layer_id in legacy_prefix
        ).encode("ascii")
        bm.verts[0][legacy_layer] = legacy_bytes
        mapping = {"0": known_ids.copy()}
        changed, complete = model.merge_stack_layer_into_mapping(
            mapping,
            bm,
            legacy_layer,
            VERTEX,
        )
        assert complete and not changed
        assert mapping == {"0": known_ids}

        bm.verts[0][legacy_layer] = legacy_bytes.ljust(255, b",")
        ambiguous_mapping = {"0": [9]}
        changed, complete = model.merge_stack_layer_into_mapping(
            ambiguous_mapping,
            bm,
            legacy_layer,
            VERTEX,
        )
        assert not complete and not changed
        assert ambiguous_mapping == {"0": [9]}

        bm.verts[0][legacy_layer] = b"1,broken"
        damaged_mapping = {"0": [9]}
        changed, complete = model.merge_stack_layer_into_mapping(
            damaged_mapping,
            bm,
            legacy_layer,
            VERTEX,
        )
        assert not complete and not changed
        assert damaged_mapping == {"0": [9]}
    finally:
        bm.free()


def test_sparse_stack_initialization_and_rebuild():
    bm = bmesh.new()
    try:
        for index in range(1000):
            bm.verts.new((float(index), 0.0, 0.0))
        bm.verts.ensure_lookup_table()
        mapping = {"10": [1]}
        stack_layer, created = model.ensure_annotation_stack(
            bm, VERTEX, mapping
        )
        assert created
        assert model.decode_layer_bytes(bytes(bm.verts[10][stack_layer])) == [1]
        assert all(
            not bytes(vert[stack_layer])
            for vert in bm.verts
            if vert.index != 10
        )

        bm.verts[20][stack_layer] = model.encode_layers([2])
        rebuilt_layer, created = model.ensure_annotation_stack(
            bm, VERTEX, mapping, rebuild=True
        )
        assert not created
        stack_layer = rebuilt_layer
        assert model.decode_layer_bytes(bytes(bm.verts[10][stack_layer])) == [1]
        assert not bytes(bm.verts[20][stack_layer])
    finally:
        bm.free()


def test_capacity_failure_is_atomic():
    obj = create_grid_object()
    obj.name = "AtomicCapacity"
    settings = obj.mesh_annotations
    for layer_id in range(1, 221):
        layer = settings.vertex_layers.add()
        layer.layer_id = layer_id
        layer.element_type = VERTEX
        layer.name = f"Vertex Layer {layer_id}"
    settings.active_vertex_layer_index = 219
    settings.next_vertex_layer_id = 221
    original_mapping = {"0": list(range(1, 220))}
    settings.vertex_layers_data = json.dumps(original_mapping, separators=(",", ":"))
    model.invalidate_element_layers_cache()
    before_json = settings.vertex_layers_data
    before_stack = bmesh_stack_payloads(obj.data, VERTEX)
    try:
        model.assign_elements_to_layer(obj, VERTEX, 220, [0])
    except model.StackCapacityError:
        pass
    else:
        raise AssertionError("over-capacity assignment was accepted")
    assert settings.vertex_layers_data == before_json
    assert model.load_element_layers(settings, VERTEX) == original_mapping
    assert bmesh_stack_payloads(obj.data, VERTEX) == before_stack

    # A failure caused by an untouched legacy element must not partially clear
    # a different target element in BMesh.
    original_mapping = {"0": list(range(1, 220)), "1": [1]}
    settings.vertex_layers_data = json.dumps(original_mapping, separators=(",", ":"))
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    stack_layer = bm.verts.layers.string.get(element_spec(VERTEX).stack_layer)
    if stack_layer is None:
        stack_layer = bm.verts.layers.string.new(element_spec(VERTEX).stack_layer)
    legacy = ",".join(
        str(layer_id) for layer_id in model._legacy_prefix(original_mapping["0"])
    ).encode("ascii")
    bm.verts[0][stack_layer] = legacy
    bm.verts[1][stack_layer] = model.encode_layers([1])
    for vert in bm.verts:
        vert.select = vert.index == 1
    bm.to_mesh(obj.data)
    bm.free()
    model.invalidate_element_layers_cache()
    before_json = settings.vertex_layers_data
    before_stack = bmesh_stack_payloads(obj.data, VERTEX)
    try:
        model.clear_elements_from_layer(
            obj, VERTEX, 1, only_selected=True, mode="ALL"
        )
    except model.StackCapacityError:
        pass
    else:
        raise AssertionError("cross-element capacity failure was accepted")
    assert settings.vertex_layers_data == before_json
    assert model.load_element_layers(settings, VERTEX) == original_mapping
    assert bmesh_stack_payloads(obj.data, VERTEX) == before_stack

    # An incomplete merge that cannot be saved must not poison the decoded
    # JSON cache or be mistaken for a synchronized state on the next force read.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    stack_layer = bm.verts.layers.string.get(element_spec(VERTEX).stack_layer)
    bm.verts[1][stack_layer] = model.encode_layers([2])
    bm.to_mesh(obj.data)
    bm.free()
    model.invalidate_element_layers_cache()
    for _attempt in range(2):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        try:
            model.ensure_lookup_tables(bm, VERTEX)
            model.reconciled_mapping_for_explicit_read(obj, VERTEX, bm)
        except model.StackCapacityError:
            pass
        else:
            raise AssertionError("incomplete unsavable merge was accepted")
        finally:
            bm.free()
        assert settings.vertex_layers_data == before_json
        assert model.load_element_layers(settings, VERTEX) == original_mapping
    bpy.data.objects.remove(obj, do_unlink=True)


def test_object_mode_rna_failure_never_flushes_mesh():
    obj = create_two_triangle_object("ObjectModeTransaction")
    settings = obj.mesh_annotations
    first = model.create_layer(settings, FACE)
    assert model.assign_elements_to_layer(obj, FACE, first.layer_id, [0])
    second = model.create_layer(settings, FACE)
    before_json = settings.face_layers_data
    before_stack = bmesh_stack_payloads(obj.data, FACE)

    original_commit = model.commit_prepared_element_layers
    original_flush = model._flush_bmesh
    flush_calls = []

    def failing_commit(*_args, **_kwargs):
        raise RuntimeError("simulated RNA failure")

    def observed_flush(*args, **kwargs):
        flush_calls.append(1)
        return original_flush(*args, **kwargs)

    model.commit_prepared_element_layers = failing_commit
    model._flush_bmesh = observed_flush
    try:
        try:
            model.assign_elements_to_layer(obj, FACE, second.layer_id, [1])
        except RuntimeError as exc:
            assert "simulated RNA failure" in str(exc)
        else:
            raise AssertionError("simulated RNA failure was hidden")
    finally:
        model.commit_prepared_element_layers = original_commit
        model._flush_bmesh = original_flush
    assert flush_calls == []
    assert settings.face_layers_data == before_json
    assert bmesh_stack_payloads(obj.data, FACE) == before_stack
    bpy.data.objects.remove(obj, do_unlink=True)


def annotation_settings_snapshot(settings):
    return (
        settings.face_layers_data,
        settings.edge_layers_data,
        settings.vertex_layers_data,
        settings.active_face_layer_index,
        settings.active_edge_layer_index,
        settings.active_vertex_layer_index,
        settings.next_face_layer_id,
        settings.next_edge_layer_id,
        settings.next_vertex_layer_id,
        tuple(
            (
                layer.layer_id,
                layer.element_type,
                layer.name,
                tuple(layer.color),
                layer.is_visible,
            )
            for collection in (
                settings.face_layers,
                settings.edge_layers,
                settings.vertex_layers,
            )
            for layer in collection
        ),
    )


def test_shared_mesh_isolation_and_recovery():
    base = create_grid_object()
    base.name = "SharedAnnotationBase"
    base_layer = model.create_layer(base.mesh_annotations, FACE)
    assert model.assign_elements_to_layer(base, FACE, base_layer.layer_id, [10])

    linked = bpy.data.objects.new("SharedAnnotationLinked", base.data)
    bpy.context.collection.objects.link(linked)
    linked_settings = linked.mesh_annotations
    for layer_id in (1, 2):
        layer = linked_settings.face_layers.add()
        layer.layer_id = layer_id
        layer.element_type = FACE
        layer.name = f"Linked Face {layer_id}"
        layer.color = (0.2 * layer_id, 0.4, 0.8, 0.45)
    linked_settings.active_face_layer_index = 0
    linked_settings.next_face_layer_id = 3
    linked_settings.face_layers_data = json.dumps({"11": [1]})
    model.invalidate_element_layers_cache()

    bpy.ops.object.select_all(action="DESELECT")
    linked.select_set(True)
    bpy.context.view_layer.objects.active = linked
    with overlay_gpu_stub():
        batches = overlay.build_overlay_batches(linked, linked_settings)
    assert not batches[FACE]
    assert model.load_element_layers(linked_settings, FACE) == {"11": [1]}
    assert model.load_element_layers(base.mesh_annotations, FACE) == {"10": [1]}

    before_settings = annotation_settings_snapshot(linked_settings)
    before_stack = {
        element_type: bmesh_stack_payloads(linked.data, element_type)
        for element_type in (FACE, EDGE, VERTEX)
    }
    before_seams = tuple(edge.use_seam for edge in linked.data.edges)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bm = bmesh.from_edit_mesh(linked.data)
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
            face.select = False
        bm.faces[12].select = True
        bmesh.update_edit_mesh(linked.data, loop_triangles=False, destructive=False)

        refused_calls = (
            lambda: bpy.ops.mesh.annotation_layer_add(element_type=FACE),
            lambda: bpy.ops.mesh.annotation_layer_remove(element_type=FACE),
            lambda: bpy.ops.mesh.annotation_layer_move(
                element_type=FACE, direction="DOWN"
            ),
            lambda: bpy.ops.mesh.annotation_assign_active(element_type=FACE),
            lambda: bpy.ops.mesh.annotation_assign_loop(element_type=FACE),
            lambda: bpy.ops.mesh.annotation_assign_new_layer(
                element_type=FACE, use_loop=False
            ),
            lambda: bpy.ops.mesh.annotation_assign_layer(
                element_type=FACE, layer_id=2, make_active=True
            ),
            lambda: bpy.ops.mesh.annotation_assign_valence(valence=4),
            lambda: bpy.ops.mesh.annotation_assign_valence_new_layer(valence=4),
            lambda: bpy.ops.mesh.annotation_mark_seam_active_face_layer(),
            lambda: bpy.ops.mesh.annotation_mark_seam_all_face_layers(),
            lambda: bpy.ops.mesh.annotation_clear_selected(
                element_type=FACE, mode="ALL"
            ),
        )
        for call in refused_calls:
            try:
                result = call()
            except RuntimeError as exc:
                assert "single-user" in str(exc)
            else:
                assert result == {"CANCELLED"}

        assert annotation_settings_snapshot(linked_settings) == before_settings
        assert {
            element_type: bmesh_stack_payloads(linked.data, element_type)
            for element_type in (FACE, EDGE, VERTEX)
        } == before_stack
        assert tuple(edge.use_seam for edge in linked.data.edges) == before_seams

        original_mesh = linked.data
        try:
            result = bpy.ops.mesh.annotation_make_single_user(
                recovery_mode="VERIFIED"
            )
        except RuntimeError as exc:
            assert "topology" in str(exc).lower()
        else:
            assert result == {"CANCELLED"}
        assert linked.data == original_mesh
        assert bpy.ops.mesh.annotation_make_single_user(
            recovery_mode="OBJECT"
        ) == {"FINISHED"}
        assert linked.data != original_mesh
        assert linked.data.users == 1
        assert bpy.context.mode == "EDIT_MESH"
        assert model.load_element_layers(linked_settings, FACE) == {"11": [1]}
        rebuilt = bmesh_stack_payloads(linked.data, FACE)
        assert model.decode_layer_bytes(rebuilt[11]) == [1]
        assert model.decode_layer_bytes(rebuilt[10]) == []
        assert bpy.ops.mesh.annotation_assign_active(element_type=FACE) == {"FINISHED"}
        assert model.load_element_layers(linked_settings, FACE)["12"] == [1]
        assert model.load_element_layers(base.mesh_annotations, FACE) == {"10": [1]}
    finally:
        if linked.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(linked, do_unlink=True)
        bpy.data.objects.remove(base, do_unlink=True)


def test_shared_topology_change_is_quarantined():
    base = create_two_triangle_object("SharedTopologyBase")
    layer = model.create_layer(base.mesh_annotations, FACE)
    assert model.assign_elements_to_layer(base, FACE, layer.layer_id, [0])
    original_json = base.mesh_annotations.face_layers_data
    linked = bpy.data.objects.new("SharedTopologyLinked", base.data)
    bpy.context.collection.objects.link(linked)

    bpy.context.view_layer.objects.active = base
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        rotate_two_triangle_diagonal(base)
        bm = bmesh.from_edit_mesh(base.data)
        bm.faces.ensure_lookup_table()
        stack_layer = bm.faces.layers.string.get(element_spec(FACE).stack_layer)
        assert stack_layer is not None
        assert all(not bytes(face[stack_layer]) for face in bm.faces)

        try:
            model.select_elements_for_layer(base, FACE, layer.layer_id)
        except model.StaleSharedAnnotationError:
            pass
        else:
            raise AssertionError("stale shared annotations were selectable")
        assert base.mesh_annotations.face_layers_data == original_json

        with overlay_gpu_stub():
            batches = overlay.build_overlay_batches(base, base.mesh_annotations)
        assert not batches[FACE]

        shared_mesh = base.data
        try:
            result = bpy.ops.mesh.annotation_make_single_user(
                recovery_mode="VERIFIED"
            )
        except RuntimeError as exc:
            assert "topology" in str(exc).lower()
        else:
            assert result == {"CANCELLED"}
        assert base.data == shared_mesh
        assert base.mesh_annotations.face_layers_data == original_json

        assert bpy.ops.mesh.annotation_make_single_user(
            recovery_mode="DISCARD"
        ) == {"FINISHED"}
        assert base.data != shared_mesh
        assert model.load_element_layers(base.mesh_annotations, FACE) == {}
        assert bpy.context.mode == "EDIT_MESH"
    finally:
        if base.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(linked, do_unlink=True)
        bpy.data.objects.remove(base, do_unlink=True)


def test_discard_recovery_only_clears_unverified_element_types():
    base = create_two_triangle_object("MixedRecoveryBase")
    face_layer = model.create_layer(base.mesh_annotations, FACE)
    edge_layer = model.create_layer(base.mesh_annotations, EDGE)
    assert model.assign_elements_to_layer(base, FACE, face_layer.layer_id, [0])
    assert model.assign_elements_to_layer(base, EDGE, edge_layer.layer_id, [1])

    linked = bpy.data.objects.new("MixedRecoveryLinked", base.data)
    bpy.context.collection.objects.link(linked)
    bpy.context.view_layer.objects.active = base
    base.select_set(True)
    try:
        base.mesh_annotations.face_annotation_state = ""
        statuses = model.shared_annotation_mapping_statuses(base)
        assert not statuses[FACE]
        assert statuses[EDGE]

        shared_mesh = base.data
        assert bpy.ops.mesh.annotation_make_single_user(
            recovery_mode="DISCARD"
        ) == {"FINISHED"}
        assert base.data != shared_mesh
        assert model.load_element_layers(base.mesh_annotations, FACE) == {}
        assert model.load_element_layers(base.mesh_annotations, EDGE) == {
            "1": [edge_layer.layer_id]
        }
        edge_payloads = bmesh_stack_payloads(base.data, EDGE)
        assert model.decode_layer_bytes(edge_payloads[1]) == [edge_layer.layer_id]
    finally:
        bpy.data.objects.remove(linked, do_unlink=True)
        bpy.data.objects.remove(base, do_unlink=True)


def test_retention_users_do_not_masquerade_as_real_mesh_users():
    for retention_flag in ("use_fake_user", "use_extra_user"):
        obj = create_two_triangle_object(f"RetentionUser_{retention_flag}")
        mesh = obj.data
        setattr(mesh, retention_flag, True)
        try:
            expected_retention_users = 2 if retention_flag == "use_fake_user" else 1
            assert mesh.users == expected_retention_users
            assert not model.annotation_mesh_is_shared(obj)
            first = model.create_layer(obj.mesh_annotations, FACE)
            assert model.assign_elements_to_layer(obj, FACE, first.layer_id, [0])
            second = model.create_layer(obj.mesh_annotations, FACE)
            bpy.ops.object.mode_set(mode="EDIT")
            try:
                rotate_two_triangle_diagonal(obj)
                assert model.assign_elements_to_layer(
                    obj, FACE, second.layer_id, [0]
                )
                assert model.load_element_layers(obj.mesh_annotations, FACE) == {
                    "0": [second.layer_id]
                }
            finally:
                bpy.ops.object.mode_set(mode="OBJECT")

            linked = bpy.data.objects.new(
                f"RetentionLinked_{retention_flag}", mesh
            )
            bpy.context.collection.objects.link(linked)
            try:
                expected_shared_users = (
                    3 if retention_flag == "use_fake_user" else 2
                )
                assert mesh.users == expected_shared_users
                assert model.annotation_mesh_is_shared(obj)
                try:
                    model.ensure_annotation_mesh_editable(obj)
                except model.SharedMeshAnnotationError:
                    pass
                else:
                    raise AssertionError(
                        "two Object users plus a retention user were not locked"
                    )
            finally:
                bpy.data.objects.remove(linked, do_unlink=True)
        finally:
            bpy.data.objects.remove(obj, do_unlink=True)
            setattr(mesh, retention_flag, False)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)


def test_shared_compatibility_rejects_untracked_inherited_stack_payloads():
    base = create_disconnected_triangle_object("CompleteStackCompatibilityBase")
    layer = model.create_layer(base.mesh_annotations, FACE)
    assert model.assign_elements_to_layer(base, FACE, layer.layer_id, [0])
    original_token = base.mesh_annotations.face_annotation_state
    linked = bpy.data.objects.new("CompleteStackCompatibilityLinked", base.data)
    bpy.context.collection.objects.link(linked)

    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bm = bmesh.from_edit_mesh(base.data)
        bm.faces.ensure_lookup_table()
        annotated = bm.faces[0]
        removed_vertices = list(bm.faces[1].verts)
        duplicated_geometry = [
            annotated,
            *annotated.edges,
            *annotated.verts,
        ]
        bmesh.ops.duplicate(bm, geom=duplicated_geometry)
        bmesh.ops.delete(bm, geom=removed_vertices, context="VERTS")
        for container in (bm.verts, bm.edges, bm.faces):
            container.index_update()
            container.ensure_lookup_table()
        bmesh.update_edit_mesh(base.data, loop_triangles=False, destructive=False)

        assert (len(bm.verts), len(bm.edges), len(bm.faces)) == (6, 6, 2)
        stack_layer = bm.faces.layers.string.get(element_spec(FACE).stack_layer)
        assert [model.decode_layer_bytes(bytes(face[stack_layer])) for face in bm.faces] == [
            [layer.layer_id],
            [layer.layer_id],
        ]
        mapping = model.load_element_layers(base.mesh_annotations, FACE)
        assert mapping == {"0": [layer.layer_id]}
        assert base.mesh_annotations.face_annotation_state == original_token
        assert not model.shared_annotation_mapping_is_current(
            base, FACE, bm, mapping
        )
        try:
            result = bpy.ops.mesh.annotation_make_single_user(
                recovery_mode="VERIFIED"
            )
        except RuntimeError as exc:
            assert "topology" in str(exc).lower()
        else:
            assert result == {"CANCELLED"}
    finally:
        if base.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(linked, do_unlink=True)
        bpy.data.objects.remove(base, do_unlink=True)


def test_shared_compatibility_rejects_invalid_or_lossy_json():
    base = create_two_triangle_object("InvalidSharedJsonBase")
    linked = bpy.data.objects.new("InvalidSharedJsonLinked", base.data)
    bpy.context.collection.objects.link(linked)
    settings = base.mesh_annotations
    bm = bmesh.new()
    bm.from_mesh(base.data)
    try:
        for invalid_data in ("{", "[]", '{"bad":[1]}', '{"0":[]}'):
            settings.face_layers_data = invalid_data
            mapping = model.load_element_layers(settings, FACE)
            assert mapping == {}
            assert not model.element_layers_data_is_valid(settings, FACE)
            assert not model.shared_annotation_mapping_is_current(
                base, FACE, bm, mapping
            )

        settings.face_layers_data = "{}"
        assert model.element_layers_data_is_valid(settings, FACE)
        assert model.shared_annotation_mapping_is_current(base, FACE, bm, {})
    finally:
        bm.free()
        bpy.data.objects.remove(linked, do_unlink=True)
        bpy.data.objects.remove(base, do_unlink=True)


def test_immediate_equal_count_write_forces_reconciliation():
    obj = create_two_triangle_object("ImmediateTopologyWrite")
    first = model.create_layer(obj.mesh_annotations, FACE)
    assert model.assign_elements_to_layer(obj, FACE, first.layer_id, [0])
    second = model.create_layer(obj.mesh_annotations, FACE)

    bpy.ops.object.mode_set(mode="EDIT")
    try:
        rotate_two_triangle_diagonal(obj)
        assert model.assign_elements_to_layer(obj, FACE, second.layer_id, [0])
        mapping = model.load_element_layers(obj.mesh_annotations, FACE)
        assert mapping == {"0": [second.layer_id]}
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        stack_layer = bm.faces.layers.string.get(element_spec(FACE).stack_layer)
        assert model.decode_layer_bytes(bytes(bm.faces[0][stack_layer])) == [
            second.layer_id
        ]
        assert not bytes(bm.faces[1][stack_layer])
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(obj, do_unlink=True)


def test_new_layer_cancellation_restores_all_cursors():
    obj = create_grid_object()
    settings = obj.mesh_annotations
    model.create_layer(settings, FACE)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bm = bmesh.from_edit_mesh(obj.data)
        for face in bm.faces:
            face.select = False
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        before = (
            len(settings.face_layers),
            settings.active_face_layer_index,
            settings.next_face_layer_id,
        )
        assert bpy.ops.mesh.annotation_assign_new_layer(
            element_type=FACE, use_loop=False
        ) == {"CANCELLED"}
        assert (
            len(settings.face_layers),
            settings.active_face_layer_index,
            settings.next_face_layer_id,
        ) == before

        original_assign = operators.assign_elements_to_layer
        operators.assign_elements_to_layer = lambda *_args, **_kwargs: False
        try:
            vertex_before = (
                len(settings.vertex_layers),
                settings.active_vertex_layer_index,
                settings.next_vertex_layer_id,
            )
            assert bpy.ops.mesh.annotation_assign_valence_new_layer(
                valence=4
            ) == {"CANCELLED"}
            assert (
                len(settings.vertex_layers),
                settings.active_vertex_layer_index,
                settings.next_vertex_layer_id,
            ) == vertex_before
        finally:
            operators.assign_elements_to_layer = original_assign
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(obj, do_unlink=True)


def create_annotated_grid_object():
    obj = create_grid_object()
    settings = obj.mesh_annotations
    source_filters = {FACE: {10}, EDGE: {20}, VERTEX: {30}}
    for element_type, source_indices in source_filters.items():
        layer = model.create_layer(settings, element_type)
        assigned = model.assign_elements_to_layer(
            obj, element_type, layer.layer_id, list(source_indices)
        )
        assert assigned
        mapping = model.load_element_layers(settings, element_type)
        source_index = next(iter(source_indices))
        assert mapping[str(source_index)] == [layer.layer_id]
    return obj


def test_assignments_and_evaluated_geometry():
    obj = create_annotated_grid_object()
    settings = obj.mesh_annotations
    source_filters = {FACE: {10}, EDGE: {20}, VERTEX: {30}}

    original_face_data = settings.face_layers_data
    settings.face_layers_data = '{"bad": ["x"], "0": [1, "bad"], "-1": [2]}'
    assert model.load_element_layers(settings, FACE) == {"0": [1]}
    settings.face_layers_data = original_face_data

    subdivision = obj.modifiers.new("Subdivision", "SUBSURF")
    subdivision.levels = 2
    source_mesh = bmesh.new()
    source_mesh.from_mesh(obj.data)
    started = time.perf_counter()
    geometry = evaluated_geometry.evaluated_overlay_geometry(
        obj, source_mesh, settings, source_filters
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    source_mesh.free()

    for element_type, source_indices in source_filters.items():
        assert geometry[element_type]
        evaluated_sources = {record[0] for record in geometry[element_type]}
        assert source_indices <= evaluated_sources
    return obj, geometry, elapsed_ms


def test_multi_layer_assignment_and_active_removal(obj):
    settings = obj.mesh_annotations
    first_layer = settings.face_layers[0]
    second_layer = model.create_layer(settings, FACE)
    target_index = 12

    assert model.assign_elements_to_layer(
        obj, FACE, first_layer.layer_id, [target_index]
    )
    assert model.assign_elements_to_layer(
        obj, FACE, second_layer.layer_id, [target_index]
    )
    assert model.load_element_layers(settings, FACE)[str(target_index)] == [
        first_layer.layer_id,
        second_layer.layer_id,
    ]

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
            face.select = False
        bm.faces[target_index].select = True
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        assert bpy.ops.mesh.annotation_clear_selected(
            element_type=FACE,
            mode="ACTIVE",
        ) == {"FINISHED"}
        assert model.load_element_layers(settings, FACE)[str(target_index)] == [
            first_layer.layer_id
        ]
        assert bpy.ops.mesh.annotation_assign_layer(
            element_type=FACE,
            layer_id=first_layer.layer_id,
            make_active=True,
        ) == {"FINISHED"}
        assert model.active_layer(settings, FACE).layer_id == first_layer.layer_id
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def test_flat_context_menu_and_sidebar_draw(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        context_layout = UILayoutProbe()
        fake_menu = SimpleNamespace(layout=context_layout)
        ui.VIEW3D_MT_mesh_annotation_context.draw(fake_menu, bpy.context)

        operator_ids = {
            entry[1] for entry in context_layout.entries if entry[0] == "operator"
        }
        menu_ids = {
            entry[1] for entry in context_layout.entries if entry[0] == "menu"
        }
        assert {
            "mesh.annotation_assign_active",
            "mesh.annotation_assign_new_layer",
            "mesh.annotation_assign_loop",
            "mesh.annotation_clear_selected",
        } <= operator_ids
        assert menu_ids == {
            "VIEW3D_MT_mesh_annotation_assign_selected_existing",
            "VIEW3D_MT_mesh_annotation_assign_loop_existing",
        }

        target_layout = UILayoutProbe()
        fake_target_menu = SimpleNamespace(layout=target_layout)
        ui.VIEW3D_MT_mesh_annotation_assign_selected_existing.draw(
            fake_target_menu,
            bpy.context,
        )
        target_operators = [
            entry[3] for entry in target_layout.entries if entry[0] == "operator"
        ]
        assert target_operators
        assert all(operator.make_active for operator in target_operators)

        panel_layout = UILayoutProbe()
        fake_panel = SimpleNamespace(layout=panel_layout)
        fake_panel.draw_layer_workspace = types.MethodType(
            ui.VIEW3D_PT_mesh_annotation.draw_layer_workspace,
            fake_panel,
        )
        ui.VIEW3D_PT_mesh_annotation.draw(fake_panel, bpy.context)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def test_cache_reuse(obj):
    original_builder = overlay.build_overlay_batches
    calls = []
    try:
        overlay.build_overlay_batches = (
            lambda _obj, _settings: calls.append(object()) or calls[-1]
        )
        overlay.invalidate_overlay_cache()
        first = overlay.cached_overlay_batches(obj, obj.mesh_annotations)
        second = overlay.cached_overlay_batches(obj, obj.mesh_annotations)
        assert first is second
        assert len(calls) == 1
    finally:
        overlay.build_overlay_batches = original_builder


def test_clean_cache_skips_modifier_signature(obj):
    overlay.invalidate_overlay_state()
    with overlay_gpu_stub():
        first = overlay.cached_overlay_batches(obj, obj.mesh_annotations)
    original_signature = overlay._modifier_state_signature
    try:
        overlay._modifier_state_signature = lambda _obj: (_ for _ in ()).throw(
            AssertionError("clean cache should not inspect modifier RNA")
        )
        second = overlay.cached_overlay_batches(obj, obj.mesh_annotations)
        assert second is first
    finally:
        overlay._modifier_state_signature = original_signature


def test_layer_counts_parse_once(obj):
    settings = obj.mesh_annotations
    original_data = settings.face_layers_data
    original_loads = model.json.loads
    calls = []
    try:
        settings.face_layers_data = json.dumps(
            {"0": [1], "1": [1, 2], "2": [2]}
        )
        model.invalidate_element_layers_cache()
        model.json.loads = lambda value: calls.append(value) or original_loads(value)
        assert model.count_elements_for_layer(obj, FACE, 1) == 2
        assert model.count_elements_for_layer(obj, FACE, 2) == 2
        assert len(calls) == 1
    finally:
        model.json.loads = original_loads
        settings.face_layers_data = original_data
        model.invalidate_element_layers_cache()


def test_face_only_subdivision_mapping_is_demand_driven():
    obj = create_grid_object()
    obj.name = "DemandDrivenMapping"
    obj.modifiers.new("Subdivision", "SUBSURF").levels = 1
    bpy.context.view_layer.objects.active = obj
    source_mesh = bmesh.new()
    source_mesh.from_mesh(obj.data)
    original_vertices = evaluated_geometry._topology_vertex_sources
    try:
        evaluated_geometry._topology_vertex_sources = lambda *_args, **_kwargs: (
            (_ for _ in ()).throw(AssertionError("face-only mapping computed vertices"))
        )
        geometry = evaluated_geometry.evaluated_overlay_geometry(
            obj,
            source_mesh,
            obj.mesh_annotations,
            {FACE: {10}, EDGE: set(), VERTEX: set()},
        )
        assert geometry[FACE]
        assert not geometry[EDGE]
        assert not geometry[VERTEX]
    finally:
        evaluated_geometry._topology_vertex_sources = original_vertices
        source_mesh.free()
        remove_object_and_orphaned_mesh(obj)


def test_unknown_modifier_falls_back_to_cage_mapping():
    obj = create_grid_object()
    obj.name = "SameCountModifierMapping"
    obj.modifiers.new("UnknownProvenance", "NODES")
    bpy.context.view_layer.objects.active = obj
    source_mesh = bmesh.new()
    source_mesh.from_mesh(obj.data)
    original_cage = evaluated_geometry._cage_overlay_geometry
    calls = []
    try:

        def observed_cage(*args, **kwargs):
            calls.append(True)
            return original_cage(*args, **kwargs)

        evaluated_geometry._cage_overlay_geometry = observed_cage
        geometry = evaluated_geometry.evaluated_overlay_geometry(
            obj,
            source_mesh,
            obj.mesh_annotations,
            {FACE: {10}, EDGE: set(), VERTEX: set()},
        )
        assert geometry[FACE]
        assert calls
    finally:
        evaluated_geometry._cage_overlay_geometry = original_cage
        source_mesh.free()
        remove_object_and_orphaned_mesh(obj)


def test_mirror_falls_back_to_cage_mapping():
    obj = create_disconnected_triangle_object("MirrorCageFallback")
    obj.modifiers.new("Mirror", "MIRROR")
    source_mesh = bmesh.new()
    source_mesh.from_mesh(obj.data)
    original_cage = evaluated_geometry._cage_overlay_geometry
    calls = []
    try:

        def observed_cage(*args, **kwargs):
            calls.append(True)
            return original_cage(*args, **kwargs)

        evaluated_geometry._cage_overlay_geometry = observed_cage
        geometry = evaluated_geometry.evaluated_overlay_geometry(
            obj,
            source_mesh,
            obj.mesh_annotations,
            {FACE: {1}, EDGE: set(), VERTEX: set()},
        )
        assert calls
        assert [record[0] for record in geometry[FACE]] == [1]
    finally:
        evaluated_geometry._cage_overlay_geometry = original_cage
        source_mesh.free()
        remove_object_and_orphaned_mesh(obj)


def test_concave_ngon_uses_valid_tessellation():
    coordinates = (
        (0.0, 0.0, 0.0),
        (3.0, 0.0, 0.0),
        (3.0, 1.0, 0.0),
        (1.0, 1.0, 0.0),
        (1.0, 2.0, 0.0),
        (3.0, 2.0, 0.0),
        (3.0, 3.0, 0.0),
        (0.0, 3.0, 0.0),
    )
    for scale in (1e-5, 1.0, 1e5):
        mesh = bpy.data.meshes.new(f"ConcaveOverlayMesh{scale}")
        mesh.from_pydata(
            tuple(tuple(value * scale for value in point) for point in coordinates),
            (),
            ((0, 1, 2, 3, 4, 5, 6, 7),),
        )
        mesh.update()
        try:
            triangles = evaluated_geometry._polygon_triangles(
                mesh, mesh.polygons[0]
            )
            triangle_area = sum(
                (vertex1 - vertex0).cross(vertex2 - vertex0).length * 0.5
                for vertex0, vertex1, vertex2 in triangles
            )
            expected_area = 7.0 * scale * scale
            assert abs(triangle_area - expected_area) <= expected_area * 1e-5
        finally:
            bpy.data.meshes.remove(mesh)


def test_subdivision_vertex_mapping_survives_later_deformer():
    obj = create_two_triangle_object("DeformedSubdivisionVertex")
    obj.modifiers.new("Subdivision", "SUBSURF").levels = 1
    displace = obj.modifiers.new("LargeXDisplace", "DISPLACE")
    displace.direction = "X"
    displace.mid_level = 0.0
    displace.strength = 100.0
    source_mesh = bmesh.new()
    source_mesh.from_mesh(obj.data)
    try:
        geometry = evaluated_geometry.evaluated_overlay_geometry(
            obj,
            source_mesh,
            obj.mesh_annotations,
            {FACE: set(), EDGE: set(), VERTEX: {1}},
        )
        evaluated_mesh = obj.evaluated_get(
            bpy.context.evaluated_depsgraph_get()
        ).data
        assert len(geometry[VERTEX]) == 1
        source_index, coordinate, _normal = geometry[VERTEX][0]
        assert source_index == 1
        assert (coordinate - evaluated_mesh.vertices[1].co).length < 1e-6
    finally:
        source_mesh.free()
        remove_object_and_orphaned_mesh(obj)


def test_subdivision_keeps_loose_vertex_annotations():
    mesh = bpy.data.meshes.new("LooseSubdivisionVertexMesh")
    mesh.from_pydata(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
            (10.0, 0.0, 0.0),
        ),
        (),
        ((0, 1, 2, 3),),
    )
    mesh.update()
    obj = bpy.data.objects.new("LooseSubdivisionVertex", mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    obj.modifiers.new("Subdivision", "SUBSURF").levels = 1
    source_mesh = bmesh.new()
    source_mesh.from_mesh(obj.data)
    try:
        geometry = evaluated_geometry.evaluated_overlay_geometry(
            obj,
            source_mesh,
            obj.mesh_annotations,
            {FACE: set(), EDGE: set(), VERTEX: {4}},
        )
        assert len(geometry[VERTEX]) == 1
        assert geometry[VERTEX][0][0] == 4
    finally:
        source_mesh.free()
        remove_object_and_orphaned_mesh(obj)


def test_zero_level_subdivision_preserves_later_deformation():
    obj = create_two_triangle_object("ZeroLevelSubdivision")
    obj.modifiers.new("ZeroSubdivision", "SUBSURF").levels = 0
    displace = obj.modifiers.new("LaterDisplace", "DISPLACE")
    displace.direction = "Z"
    displace.mid_level = 0.0
    displace.strength = 3.0
    source_mesh = bmesh.new()
    source_mesh.from_mesh(obj.data)
    try:
        geometry = evaluated_geometry.evaluated_overlay_geometry(
            obj,
            source_mesh,
            obj.mesh_annotations,
            {FACE: {0}, EDGE: set(), VERTEX: set()},
        )
        z_values = [
            coordinate.z
            for _source_index, triangles, _normal in geometry[FACE]
            for triangle in triangles
            for coordinate in triangle
        ]
        assert z_values
        assert min(z_values) > 2.9
    finally:
        source_mesh.free()
        remove_object_and_orphaned_mesh(obj)


def test_depsgraph_invalidation_is_scoped(obj):
    bpy.context.view_layer.objects.active = obj
    overlay.invalidate_overlay_state()
    with overlay_gpu_stub():
        overlay.cached_overlay_batches(obj, obj.mesh_annotations)
    cache_key = obj.session_uid
    cached = overlay._overlay_batch_cache[cache_key]
    unrelated_mesh = bpy.data.meshes.new("UnrelatedMesh")
    try:
        unrelated_update = SimpleNamespace(
            is_updated_geometry=True,
            is_updated_transform=False,
            id=unrelated_mesh,
        )
        overlay.annotation_depsgraph_update_post(
            None, SimpleNamespace(updates=[unrelated_update])
        )
        assert not cached["dirty"]

        related_update = SimpleNamespace(
            is_updated_geometry=True,
            is_updated_transform=False,
            id=obj.data,
        )
        overlay.annotation_depsgraph_update_post(
            None, SimpleNamespace(updates=[related_update])
        )
        assert cached["dirty"]
    finally:
        bpy.data.meshes.remove(unrelated_mesh)


def test_geometry_only_cache_tracks_dependencies():
    obj = create_grid_object()
    obj.name = "GeometryOnlyCache"
    other = create_grid_object()
    other.name = "GeometryOnlyCacheActive"
    settings = obj.mesh_annotations
    layer = model.create_layer(settings, FACE)
    assert model.assign_elements_to_layer(obj, FACE, layer.layer_id, [10])
    bpy.context.view_layer.objects.active = obj
    overlay.invalidate_overlay_state()
    with overlay_gpu_stub():
        overlay.cached_overlay_batches(obj, settings)
    cache_key = obj.session_uid
    assert cache_key in overlay._overlay_geometry_cache
    overlay.invalidate_overlay_cache(obj, invalidate_geometry=False)
    assert cache_key not in overlay._overlay_batch_cache
    assert cache_key in overlay._overlay_geometry_cache

    bpy.context.view_layer.objects.active = other
    related_update = SimpleNamespace(
        is_updated_geometry=True,
        is_updated_transform=False,
        id=obj.data,
    )
    overlay.annotation_depsgraph_update_post(
        None, SimpleNamespace(updates=[related_update])
    )
    assert cache_key not in overlay._overlay_geometry_cache
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.objects.remove(other, do_unlink=True)


def test_texture_paint_displace_invalidates_geometry_cache():
    obj = create_grid_object()
    obj.name = "TexturePaintDisplace"
    settings = obj.mesh_annotations
    layer = model.create_layer(settings, FACE)
    assert model.assign_elements_to_layer(obj, FACE, layer.layer_id, [10])
    image = bpy.data.images.new("TexturePaintDisplaceImage", width=2, height=2)
    texture = bpy.data.textures.new("TexturePaintDisplaceTexture", type="IMAGE")
    texture.image = image
    displace = obj.modifiers.new("ImageDisplace", "DISPLACE")
    displace.texture = texture
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
    try:
        assert not overlay._paint_mode_is_geometry_neutral(obj)
        overlay.invalidate_overlay_state()
        with overlay_gpu_stub():
            overlay.cached_overlay_batches(obj, settings)
        cache_key = obj.session_uid
        assert cache_key in overlay._overlay_geometry_cache

        overlay.annotation_depsgraph_update_post(
            None,
            SimpleNamespace(
                updates=[
                    SimpleNamespace(
                        is_updated_geometry=True,
                        is_updated_transform=False,
                        id=obj,
                    ),
                    SimpleNamespace(
                        is_updated_geometry=True,
                        is_updated_transform=False,
                        id=image,
                    ),
                ]
            ),
        )
        assert cache_key not in overlay._overlay_geometry_cache
        assert overlay._overlay_batch_cache[cache_key]["dirty"]
    finally:
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        overlay.invalidate_overlay_state()
        remove_object_and_orphaned_mesh(obj)
        bpy.data.textures.remove(texture)
        bpy.data.images.remove(image)


def test_weight_paint_nodes_preserves_cage_geometry():
    obj = create_grid_object()
    obj.name = "WeightPaintNodes"
    obj.modifiers.new("WeightDrivenNodes", "NODES")
    assert not evaluated_geometry._modifier_stack_supports_evaluated_mapping(obj)
    assert not overlay._weight_paint_can_deform_overlay(obj)
    remove_object_and_orphaned_mesh(obj)


def test_weight_paint_shape_key_invalidates_geometry_cache():
    obj = create_two_triangle_object("WeightPaintShapeKey")
    obj.shape_key_add(name="Basis")
    raised = obj.shape_key_add(name="Raised")
    raised.data[2].co.z = 2.0
    raised.value = 0.0
    settings = obj.mesh_annotations
    layer = model.create_layer(settings, FACE)
    assert model.assign_elements_to_layer(obj, FACE, layer.layer_id, [0])
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    try:
        assert overlay._weight_paint_can_deform_overlay(obj)
        overlay.invalidate_overlay_state()
        with overlay_gpu_stub():
            overlay.cached_overlay_batches(obj, settings)
        cache_key = obj.session_uid
        assert cache_key in overlay._overlay_geometry_cache
        cached_z = max(
            coordinate.z
            for _source_index, triangles, _normal in
            overlay._overlay_geometry_cache[cache_key]["geometry"][FACE]
            for triangle in triangles
            for coordinate in triangle
        )
        assert abs(cached_z) < 1e-6
        assert obj.data.shape_keys.session_uid in overlay._overlay_batch_cache[
            cache_key
        ]["dependency_keys"]

        raised.value = 1.0
        bpy.context.view_layer.update()
        assert cache_key not in overlay._overlay_geometry_cache
        source_mesh = bmesh.new()
        source_mesh.from_mesh(obj.data)
        try:
            fresh_geometry = evaluated_geometry.evaluated_overlay_geometry(
                obj,
                source_mesh,
                settings,
                {FACE: {0}, EDGE: set(), VERTEX: set()},
            )
        finally:
            source_mesh.free()
        fresh_z = max(
            coordinate.z
            for _source_index, triangles, _normal in fresh_geometry[FACE]
            for triangle in triangles
            for coordinate in triangle
        )
        assert fresh_z > 1.9
    finally:
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        overlay.invalidate_overlay_state()
        remove_object_and_orphaned_mesh(obj)


def test_solo_active_layer_change_invalidates_batches():
    obj = create_two_triangle_object("SoloActiveCache")
    settings = obj.mesh_annotations
    layer1 = model.create_layer(settings, FACE)
    layer2 = model.create_layer(settings, FACE)
    assert model.assign_elements_to_layer(obj, FACE, layer1.layer_id, [0])
    assert model.assign_elements_to_layer(obj, FACE, layer2.layer_id, [1])
    settings.solo_active = True
    settings.active_face_layer_index = 0
    overlay.invalidate_overlay_state()
    try:
        with overlay_gpu_stub():
            first = overlay.cached_overlay_batches(obj, settings)
        assert {entry["layer_id"] for entry in first[FACE]} == {layer1.layer_id}
        cache_key = obj.session_uid
        assert cache_key in overlay._overlay_batch_cache

        settings.active_face_layer_index = 1
        assert cache_key not in overlay._overlay_batch_cache
        with overlay_gpu_stub():
            second = overlay.cached_overlay_batches(obj, settings)
        assert second is not first
        assert {entry["layer_id"] for entry in second[FACE]} == {layer2.layer_id}
    finally:
        overlay.invalidate_overlay_state()
        remove_object_and_orphaned_mesh(obj)


def test_non_active_solo_change_invalidates_owner_batches():
    obj_a = create_two_triangle_object("SoloCacheOwnerA")
    obj_b = create_two_triangle_object("SoloCacheOwnerB")

    def configure(obj):
        settings = obj.mesh_annotations
        layer1 = model.create_layer(settings, FACE)
        layer2 = model.create_layer(settings, FACE)
        assert model.assign_elements_to_layer(obj, FACE, layer1.layer_id, [0])
        assert model.assign_elements_to_layer(obj, FACE, layer2.layer_id, [1])
        settings.solo_active = True
        settings.active_face_layer_index = 0
        return settings, layer1, layer2

    settings_a, layer_a1, layer_a2 = configure(obj_a)
    settings_b, _layer_b1, _layer_b2 = configure(obj_b)
    overlay.invalidate_overlay_state()
    try:
        bpy.context.view_layer.objects.active = obj_a
        with overlay_gpu_stub():
            first_a = overlay.cached_overlay_batches(obj_a, settings_a)
        assert {entry["layer_id"] for entry in first_a[FACE]} == {
            layer_a1.layer_id
        }

        bpy.context.view_layer.objects.active = obj_b
        with overlay_gpu_stub():
            overlay.cached_overlay_batches(obj_b, settings_b)
        cache_key_a = obj_a.session_uid
        cache_key_b = obj_b.session_uid
        assert cache_key_a in overlay._overlay_batch_cache
        assert cache_key_b in overlay._overlay_batch_cache

        settings_a.active_face_layer_index = 1
        assert cache_key_a not in overlay._overlay_batch_cache
        assert cache_key_b in overlay._overlay_batch_cache
        with overlay_gpu_stub():
            second_a = overlay.cached_overlay_batches(obj_a, settings_a)
        assert {entry["layer_id"] for entry in second_a[FACE]} == {
            layer_a2.layer_id
        }
    finally:
        overlay.invalidate_overlay_state()
        remove_object_and_orphaned_mesh(obj_a)
        remove_object_and_orphaned_mesh(obj_b)


def test_local_surface_batches_survive_style_and_transform_updates():
    obj = create_grid_object()
    obj.name = "LocalSurfaceCache"
    bpy.context.view_layer.objects.active = obj
    settings = obj.mesh_annotations
    layer = model.create_layer(settings, FACE)
    assert model.assign_elements_to_layer(obj, FACE, layer.layer_id, [10])
    overlay.invalidate_overlay_state()
    with overlay_gpu_stub():
        batches = overlay.cached_overlay_batches(obj, settings)
    face_entries = batches[FACE]
    assert face_entries
    uses_local_coordinates = all(
        entry.get("coordinate_space") == "LOCAL" for entry in face_entries
    )
    cache_key = obj.session_uid
    cached = overlay._overlay_batch_cache[cache_key]

    layer.color = (0.2, 0.4, 0.8, 1.0)
    assert overlay._overlay_batch_cache.get(cache_key) is cached
    assert not cached["dirty"]

    transform_update = SimpleNamespace(
        is_updated_geometry=False,
        is_updated_transform=True,
        id=obj,
    )
    overlay.annotation_depsgraph_update_post(
        None, SimpleNamespace(updates=[transform_update])
    )
    assert cached["dirty"] is not uses_local_coordinates
    bpy.data.objects.remove(obj, do_unlink=True)


def test_overlay_color_is_selection_independent(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
            face.select = False
        bm.faces[10].select = True
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        overlay.invalidate_overlay_state()
        with overlay_gpu_stub():
            batches = overlay.build_overlay_batches(obj, obj.mesh_annotations)
        entries = [
            entry
            for element_type in (FACE, EDGE, VERTEX)
            for entry in batches[element_type]
        ]
        assert entries
        assert all("selected" not in entry for entry in entries)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def test_history_resyncs_bmesh_ownership(obj):
    settings = obj.mesh_annotations
    layer_id = settings.face_layers[0].layer_id
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        with overlay_gpu_stub():
            overlay.invalidate_overlay_state()
            overlay.build_overlay_batches(obj, settings)

            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            stack_layer, _created = model.ensure_annotation_stack(
                bm, FACE
            )
            bm.faces[10][stack_layer] = b""
            bm.faces[11][stack_layer] = model.encode_layers([layer_id])
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

            before_draw_json = settings.face_layers_data
            overlay.invalidate_overlay_state()
            overlay.build_overlay_batches(obj, settings)
            assert settings.face_layers_data == before_draw_json

            # Undo restores BMesh custom data independently of Python's derived
            # caches. The history handler must make that BMesh data authoritative.
            overlay.annotation_history_post()
            for key in tuple(model._BMESH_SYNC_DIRTY_AT):
                model._BMESH_SYNC_DIRTY_AT[key] = time.perf_counter() - 1.0
            assert overlay._topology_sync_timer() is None
            overlay.build_overlay_batches(obj, settings)
        mapping = model.load_element_layers(settings, FACE)
        assert "10" not in mapping
        assert mapping["11"] == [layer_id]
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def test_equal_count_topology_reconciles_after_quiet_period():
    obj = create_grid_object()
    obj.name = "EqualCountTopology"
    settings = obj.mesh_annotations
    layer = model.create_layer(settings, FACE)
    assert model.assign_elements_to_layer(obj, FACE, layer.layer_id, [10])
    original_counts = (
        len(obj.data.vertices),
        len(obj.data.edges),
        len(obj.data.polygons),
    )
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        removed = bm.faces[10]
        replacement_vertices = tuple(removed.verts)
        bmesh.ops.delete(bm, geom=[removed], context="FACES_ONLY")
        bm.faces.new(replacement_vertices)
        bm.faces.index_update()
        bm.faces.ensure_lookup_table()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=True)
        assert (
            len(bm.verts),
            len(bm.edges),
            len(bm.faces),
        ) == original_counts

        update = SimpleNamespace(
            is_updated_geometry=True,
            is_updated_transform=False,
            id=obj.data,
        )
        overlay.annotation_depsgraph_update_post(
            None,
            SimpleNamespace(updates=[update]),
        )
        for key in tuple(model._BMESH_SYNC_DIRTY_AT):
            model._BMESH_SYNC_DIRTY_AT[key] = time.perf_counter() - 1.0
        assert overlay._topology_sync_timer() is None
        with overlay_gpu_stub():
            overlay.build_overlay_batches(obj, settings)
        assert model.load_element_layers(settings, FACE) == {}
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(obj, do_unlink=True)


def test_load_pre_clears_identity_keyed_state(obj):
    bpy.context.view_layer.objects.active = obj
    model.load_element_layers(obj.mesh_annotations, FACE)
    model.mark_bmesh_mapping_dirty(obj.data)
    with overlay_gpu_stub():
        overlay.cached_overlay_batches(obj, obj.mesh_annotations)
    assert model._ELEMENT_LAYERS_CACHE
    assert model._BMESH_SYNC_DIRTY_AT or model._BMESH_SYNC_STATES
    assert overlay._overlay_batch_cache
    overlay.annotation_load_pre()
    assert not model._ELEMENT_LAYERS_CACHE
    assert not model._BMESH_SYNC_DIRTY_AT
    assert not model._BMESH_SYNC_STATES
    assert not overlay._overlay_batch_cache
    assert not overlay._overlay_geometry_cache


def test_history_handlers_registered():
    for handlers in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        assert overlay.annotation_history_pre in handlers
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        assert overlay.annotation_history_post in handlers


def assert_runtime_callbacks_are_singletons():
    assert (
        bpy.app.handlers.depsgraph_update_post.count(
            addon.overlay.annotation_depsgraph_update_post
        )
        == 1
    )
    assert bpy.app.handlers.load_pre.count(addon.overlay.annotation_load_pre) == 1
    for handlers in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        assert handlers.count(addon.overlay.annotation_history_pre) == 1
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        assert handlers.count(addon.overlay.annotation_history_post) == 1
    menu_callbacks = tuple(
        getattr(
            bpy.types.VIEW3D_MT_edit_mesh_context_menu.draw,
            "_draw_funcs",
            (),
        )
    )
    identity = (
        addon.ui.draw_context_menu.__module__,
        addon.ui.draw_context_menu.__name__,
    )
    assert sum(
        (
            getattr(callback, "__module__", None),
            getattr(callback, "__name__", None),
        )
        == identity
        for callback in menu_callbacks
    ) == 1


def test_external_draw_handle_removal_does_not_break_teardown():
    handle = addon.overlay._draw_handle
    assert handle is not None
    bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
    addon.unregister()
    assert not hasattr(bpy.types.Object, "mesh_annotations")
    assert not addon._registered_classes
    addon.register()
    assert_runtime_callbacks_are_singletons()


def test_register_rejects_and_preserves_a_foreign_same_name_property():
    addon.unregister()
    bpy.types.Object.mesh_annotations = bpy.props.IntProperty(default=37)
    assert not addon._annotation_property_is_ours()
    try:
        addon.register()
    except RuntimeError as exc:
        assert "already registered" in str(exc).lower()
    else:
        raise AssertionError("foreign Object.mesh_annotations was accepted")
    assert hasattr(bpy.types.Object, "mesh_annotations")
    probe_mesh = bpy.data.meshes.new("ForeignPropertyProbeMesh")
    probe = bpy.data.objects.new("ForeignPropertyProbe", probe_mesh)
    try:
        assert probe.mesh_annotations == 37
    finally:
        bpy.data.objects.remove(probe)
        bpy.data.meshes.remove(probe_mesh)

    del bpy.types.Object.mesh_annotations
    addon.register()
    assert addon._annotation_property_is_ours()
    assert_runtime_callbacks_are_singletons()


def test_registration_failure_rolls_back_completed_steps():
    addon.unregister()
    original_register = bpy.utils.register_class
    failing_class = addon.CLASSES[2]

    def fail_once(cls):
        if cls is failing_class:
            raise RuntimeError("simulated class registration conflict")
        return original_register(cls)

    bpy.utils.register_class = fail_once
    try:
        try:
            addon.register()
        except RuntimeError as exc:
            assert "registration conflict" in str(exc)
        else:
            raise AssertionError("class registration failure was hidden")
    finally:
        bpy.utils.register_class = original_register
    assert not addon._registered_classes
    assert not hasattr(bpy.types.Object, "mesh_annotations")
    addon.register()
    assert_runtime_callbacks_are_singletons()


def test_registered_manual_reload_cycle():
    old_classes = tuple(addon.CLASSES)
    reloaded = importlib.reload(addon)
    assert reloaded is addon
    assert addon._runtime_registered
    assert hasattr(bpy.types.Object, "mesh_annotations")
    assert all(
        old_class is not new_class
        for old_class, new_class in zip(old_classes, addon.CLASSES, strict=True)
    )
    assert_runtime_callbacks_are_singletons()


def test_button_operators(obj):
    settings = obj.mesh_annotations
    overlay_state = settings.enable_overlay
    assert bpy.ops.mesh.annotation_toggle_overlay() == {"FINISHED"}
    assert settings.enable_overlay is not overlay_state
    assert bpy.ops.mesh.annotation_toggle_overlay() == {"FINISHED"}
    assert settings.enable_overlay is overlay_state

    assert bpy.ops.mesh.annotation_toggle_solo() == {"FINISHED"}
    assert settings.solo_active
    assert bpy.ops.mesh.annotation_toggle_solo() == {"FINISHED"}
    assert not settings.solo_active

    layer = settings.face_layers[0]
    visible = layer.is_visible
    result = bpy.ops.mesh.annotation_toggle_layer_visibility(
        element_type=FACE,
        layer_id=layer.layer_id,
    )
    assert result == {"FINISHED"}
    assert layer.is_visible is not visible


def test_localization_modes_and_tooltips():
    original_preferences = i18n.addon_preferences
    original_locale = i18n.blender_locale
    try:
        i18n.addon_preferences = lambda: SimpleNamespace(language_display="ZH")
        assert i18n.tr("Add Annotation Layer") == "新增标注图层"
        assert (
            operators.MESH_OT_annotation_layer_add.description(None, None)
            == "为当前元素类型创建新的标注图层。"
        )

        i18n.addon_preferences = lambda: SimpleNamespace(language_display="EN")
        assert i18n.tr("Add Annotation Layer") == "Add Annotation Layer"

        i18n.addon_preferences = lambda: SimpleNamespace(language_display="AUTO")
        i18n.blender_locale = lambda: "ja_JP"
        assert i18n.language_mode() == "EN"
        i18n.blender_locale = lambda: "zh_HANS"
        assert i18n.language_mode() == "ZH"

        items = i18n.language_items(None, None)
        assert [item[0] for item in items] == ["AUTO", "EN", "ZH"]
        assert i18n.ADDON_PACKAGE == addon.__package__
    finally:
        i18n.addon_preferences = original_preferences
        i18n.blender_locale = original_locale


def test_registered_reload_cycle():
    old_classes = tuple(addon.CLASSES)
    addon.unregister()
    importlib.reload(addon)
    assert all(
        old_class is not new_class
        for old_class, new_class in zip(old_classes, addon.CLASSES, strict=True)
    )

    addon.register()
    assert hasattr(bpy.types.Object, "mesh_annotations")
    assert_runtime_callbacks_are_singletons()


def run_with_fresh_annotations(test):
    obj = create_annotated_grid_object()
    subdivision = obj.modifiers.new("Subdivision", "SUBSURF")
    subdivision.levels = 2
    bpy.context.view_layer.objects.active = obj
    try:
        test(obj)
    finally:
        overlay.invalidate_overlay_state()
        if obj.name in bpy.data.objects:
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            remove_object_and_orphaned_mesh(obj)


def main():
    initial_meshes = set(bpy.data.meshes)
    test_extension_namespace_package_name()
    test_entry_point_reloads_all_submodules()
    addon.register()
    try:
        test_history_handlers_registered()
        test_localization_modes_and_tooltips()
        test_binary_stack_contract()
        test_sparse_stack_initialization_and_rebuild()
        test_capacity_failure_is_atomic()
        test_object_mode_rna_failure_never_flushes_mesh()
        test_shared_mesh_isolation_and_recovery()
        test_shared_topology_change_is_quarantined()
        test_discard_recovery_only_clears_unverified_element_types()
        test_retention_users_do_not_masquerade_as_real_mesh_users()
        test_shared_compatibility_rejects_untracked_inherited_stack_payloads()
        test_shared_compatibility_rejects_invalid_or_lossy_json()
        test_immediate_equal_count_write_forces_reconciliation()
        test_new_layer_cancellation_restores_all_cursors()
        obj, geometry, elapsed_ms = test_assignments_and_evaluated_geometry()
        counts = {kind: len(records) for kind, records in geometry.items()}
        base_counts = (
            len(obj.data.vertices),
            len(obj.data.edges),
            len(obj.data.polygons),
        )
        remove_object_and_orphaned_mesh(obj)
        for isolated_test in (
            test_multi_layer_assignment_and_active_removal,
            test_flat_context_menu_and_sidebar_draw,
            test_button_operators,
            test_cache_reuse,
            test_clean_cache_skips_modifier_signature,
            test_layer_counts_parse_once,
            test_depsgraph_invalidation_is_scoped,
            test_overlay_color_is_selection_independent,
            test_history_resyncs_bmesh_ownership,
            test_load_pre_clears_identity_keyed_state,
        ):
            run_with_fresh_annotations(isolated_test)
        test_face_only_subdivision_mapping_is_demand_driven()
        test_unknown_modifier_falls_back_to_cage_mapping()
        test_mirror_falls_back_to_cage_mapping()
        test_concave_ngon_uses_valid_tessellation()
        test_subdivision_vertex_mapping_survives_later_deformer()
        test_subdivision_keeps_loose_vertex_annotations()
        test_zero_level_subdivision_preserves_later_deformation()
        test_geometry_only_cache_tracks_dependencies()
        test_texture_paint_displace_invalidates_geometry_cache()
        test_weight_paint_nodes_preserves_cage_geometry()
        test_weight_paint_shape_key_invalidates_geometry_cache()
        test_solo_active_layer_change_invalidates_batches()
        test_non_active_solo_change_invalidates_owner_batches()
        test_local_surface_batches_survive_style_and_transform_updates()
        test_equal_count_topology_reconciles_after_quiet_period()
        test_registration_failure_rolls_back_completed_steps()
        test_register_rejects_and_preserves_a_foreign_same_name_property()
        test_external_draw_handle_removal_does_not_break_teardown()
        test_registered_manual_reload_cycle()
        test_registered_reload_cycle()
        print("BLENDER_SMOKE_OK", base_counts, round(elapsed_ms, 2), counts)
    finally:
        addon.unregister()
        for mesh in tuple(bpy.data.meshes):
            if mesh not in initial_meshes and mesh.users == 0:
                bpy.data.meshes.remove(mesh)


if __name__ == "__main__":
    main()
