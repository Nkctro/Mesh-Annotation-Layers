"""Mesh Annotation Layers extension entry point."""
_needs_reload = "bpy" in locals()
_restore_registration = bool(
    _needs_reload and globals().get("_runtime_registered", False)
)
if _restore_registration:
    unregister()

import importlib
import sys

import bpy

_SUBMODULE_NAMES = (
    "constants",
    "i18n",
    "model",
    "evaluated_geometry",
    "loops",
    "overlay",
    "properties",
    "operators",
    "preferences",
    "ui",
)


def _load_submodules():
    """Import once, then reload only after the prior runtime is unregistered."""
    loaded = {}
    for name in _SUBMODULE_NAMES:
        qualified_name = f"{__package__}.{name}"
        module = sys.modules.get(qualified_name)
        if module is None:
            module = importlib.import_module(f".{name}", __package__)
        elif _needs_reload:
            module = importlib.reload(module)
        loaded[name] = module
    return loaded


_submodules = _load_submodules()
globals().update(_submodules)

MeshAnnotationSettings = properties.MeshAnnotationSettings
CLASSES = preferences.CLASSES + properties.CLASSES + operators.CLASSES + ui.CLASSES
_registered_classes = []
_runtime_registered = False
_property_registered = False


def _annotation_property_is_ours():
    if not hasattr(bpy.types.Object, "mesh_annotations"):
        return False
    try:
        prop = bpy.types.Object.bl_rna.properties["mesh_annotations"]
        return bool(
            prop.type == "POINTER"
            and prop.fixed_type == MeshAnnotationSettings.bl_rna
        )
    except (AttributeError, KeyError, ReferenceError, RuntimeError):
        return False


def register():
    global _property_registered, _runtime_registered
    if _runtime_registered:
        return
    if hasattr(bpy.types.Object, "mesh_annotations"):
        raise RuntimeError("Object.mesh_annotations is already registered")
    try:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
            _registered_classes.append(cls)
        bpy.types.Object.mesh_annotations = bpy.props.PointerProperty(
            type=MeshAnnotationSettings
        )
        _property_registered = True
        overlay.register()
        ui.register()
    except Exception:
        unregister()
        raise
    _runtime_registered = True


def unregister():
    global _property_registered, _runtime_registered
    _runtime_registered = False
    ui.unregister()
    overlay.unregister()
    if _property_registered:
        if _annotation_property_is_ours():
            del bpy.types.Object.mesh_annotations
        _property_registered = False
    for cls in reversed(tuple(_registered_classes)):
        bpy.utils.unregister_class(cls)
    _registered_classes.clear()


if _restore_registration:
    register()
