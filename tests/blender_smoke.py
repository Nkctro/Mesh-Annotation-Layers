"""Run with: blender --background --factory-startup --python tests/blender_smoke.py"""

import os
import sys
import time
from pathlib import Path

import bmesh
import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
GRID_SEGMENTS = int(os.environ.get("MAL_GRID_SEGMENTS", "28"))

import mesh_annotation_layers as addon
from mesh_annotation_layers import evaluated_geometry, model, overlay
from mesh_annotation_layers.constants import EDGE, FACE, VERTEX


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


def main():
    addon.register()
    try:
        obj, geometry, elapsed_ms = test_assignments_and_evaluated_geometry()
        test_cache_reuse(obj)
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
