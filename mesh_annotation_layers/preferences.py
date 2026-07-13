"""Add-on preferences."""

import bpy

from .i18n import tr


ADDON_PACKAGE = (__package__ or "").partition(".")[0]


def addon_preferences():
    try:
        prefs = bpy.context.preferences
    except AttributeError:
        return None
    if not prefs:
        return None
    addon = prefs.addons.get(ADDON_PACKAGE)
    if addon:
        return addon.preferences
    return None


class MeshAnnotationPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_PACKAGE

    language_display: bpy.props.EnumProperty(
        name="Language",
        items=(
            ("AUTO", "Auto", "Follow Blender interface language"),
            ("EN", "English", "Always show English labels"),
            ("ZH", "中文", "始终显示中文"),
            ("BOTH", "Both", "Show both English and Chinese text"),
        ),
        default="AUTO",
    )

    context_menu_split_types: bpy.props.BoolProperty(
        name="Type Selection Submenu",
        description=(
            "Enable to show an extra submenu for choosing Faces/Edges/Vertices. "
            "Disable for quicker access with direct actions."
        ),
        default=True,
    )

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "language_display", text=tr('Language'))
        layout.label(text=tr("Auto follows Blender's interface language."))
        layout.prop(self, "context_menu_split_types", text=tr('Type Selection Submenu'))


CLASSES = (MeshAnnotationPreferences,)
