"""Mesh Annotation Layers add-on entry point."""

bl_info = {
    "name": "Mesh Annotation Layers",
    "author": "Nkctro",
    "version": (1, 2, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar > Mesh Annotation",
    "description": "Annotate mesh elements with evaluated-surface color layers",
    "category": "3D View",
    "doc_url": "https://github.com/Nkctro/Mesh-Annotation-Layers",
    "tracker_url": "https://github.com/Nkctro/Mesh-Annotation-Layers/issues",
}

import bpy

from . import operators, overlay, preferences, properties, ui
from .properties import MeshAnnotationSettings


CLASSES = preferences.CLASSES + properties.CLASSES + operators.CLASSES + ui.CLASSES
_registered_classes = []


def register():
    if _registered_classes:
        return
    try:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
            _registered_classes.append(cls)
        bpy.types.Object.mesh_annotations = bpy.props.PointerProperty(
            type=MeshAnnotationSettings
        )
        overlay.register()
        ui.register()
    except Exception:
        unregister()
        raise


def unregister():
    ui.unregister()
    overlay.unregister()
    if hasattr(bpy.types.Object, "mesh_annotations"):
        del bpy.types.Object.mesh_annotations
    while _registered_classes:
        cls = _registered_classes.pop()
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
