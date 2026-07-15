"""Run with: blender --background --factory-startup --python tests/blender_smoke.py"""

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
from mesh_annotation_layers import evaluated_geometry, i18n, model, operators, overlay
from mesh_annotation_layers.constants import EDGE, FACE, VERTEX


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
    finally:
        for module_name in list(sys.modules):
            if module_name == package_name or module_name.startswith(
                f"{package_name}."
            ):
                del sys.modules[module_name]


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


def test_assignments_and_evaluated_geometry():
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


def test_face_only_generic_mapping_is_demand_driven():
    obj = create_grid_object()
    obj.name = "DemandDrivenMapping"
    obj.modifiers.new("Triangulate", "TRIANGULATE")
    bpy.context.view_layer.objects.active = obj
    source_mesh = bmesh.new()
    source_mesh.from_mesh(obj.data)
    original_edges = evaluated_geometry._nearest_edge_sources
    original_vertices = evaluated_geometry._topology_vertex_sources
    try:
        evaluated_geometry._nearest_edge_sources = lambda *_args, **_kwargs: (
            (_ for _ in ()).throw(AssertionError("face-only mapping computed edges"))
        )
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
        evaluated_geometry._nearest_edge_sources = original_edges
        evaluated_geometry._topology_vertex_sources = original_vertices
        source_mesh.free()
        bpy.data.objects.remove(obj, do_unlink=True)


def test_depsgraph_invalidation_is_scoped(obj):
    bpy.context.view_layer.objects.active = obj
    overlay.invalidate_overlay_state()
    with overlay_gpu_stub():
        overlay.cached_overlay_batches(obj, obj.mesh_annotations)
    cache_key = obj.as_pointer()
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


def test_local_surface_batches_survive_style_and_transform_updates():
    obj = create_grid_object()
    obj.name = "LocalSurfaceCache"
    bpy.context.view_layer.objects.active = obj
    settings = obj.mesh_annotations
    layer = model.create_layer(settings, FACE)
    model.save_element_layers(settings, FACE, {"10": [layer.layer_id]})
    overlay.invalidate_overlay_state()
    with overlay_gpu_stub():
        batches = overlay.cached_overlay_batches(obj, settings)
    face_entries = batches[FACE]
    assert face_entries
    uses_local_coordinates = all(
        entry.get("coordinate_space") == "LOCAL" for entry in face_entries
    )
    cache_key = obj.as_pointer()
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
            int_layer, stack_layer = model.ensure_annotation_layers(bm, FACE)
            bm.faces[10][int_layer] = -1
            bm.faces[10][stack_layer] = b""
            bm.faces[11][int_layer] = layer_id
            bm.faces[11][stack_layer] = model.encode_layers([layer_id])
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

            # Undo restores BMesh custom data independently of Python's derived
            # caches. The history handler must make that BMesh data authoritative.
            overlay.annotation_history_post()
            overlay.build_overlay_batches(obj, settings)
        mapping = model.load_element_layers(settings, FACE)
        assert "10" not in mapping
        assert mapping["11"] == [layer_id]
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def test_history_handlers_registered():
    for handlers in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        assert overlay.annotation_history_pre in handlers
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        assert overlay.annotation_history_post in handlers


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


def main():
    test_extension_namespace_package_name()
    addon.register()
    try:
        test_history_handlers_registered()
        test_localization_modes_and_tooltips()
        obj, geometry, elapsed_ms = test_assignments_and_evaluated_geometry()
        test_multi_layer_assignment_and_active_removal(obj)
        test_button_operators(obj)
        test_cache_reuse(obj)
        test_clean_cache_skips_modifier_signature(obj)
        test_layer_counts_parse_once(obj)
        test_face_only_generic_mapping_is_demand_driven()
        test_depsgraph_invalidation_is_scoped(obj)
        test_local_surface_batches_survive_style_and_transform_updates()
        test_overlay_color_is_selection_independent(obj)
        test_history_resyncs_bmesh_ownership(obj)
        counts = {kind: len(records) for kind, records in geometry.items()}
        base_counts = (
            len(obj.data.vertices),
            len(obj.data.edges),
            len(obj.data.polygons),
        )
        print("BLENDER_SMOKE_OK", base_counts, round(elapsed_ms, 2), counts)
    finally:
        addon.unregister()


if __name__ == "__main__":
    main()
