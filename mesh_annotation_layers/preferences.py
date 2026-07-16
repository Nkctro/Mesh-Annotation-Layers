"""Add-on preferences."""

import bpy

from .i18n import (
    ADDON_PACKAGE,
    blender_locale,
    language_from_locale,
    language_items,
    redraw_ui,
    tr,
)


class MeshAnnotationPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_PACKAGE

    language_display: bpy.props.EnumProperty(
        name="Language",
        description=(
            "Choose automatic Blender-language detection or a manual add-on language"
        ),
        items=language_items,
        update=lambda _self, context: redraw_ui(context),
    )

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "language_display", text=tr("Language"))
        if self.language_display == "AUTO":
            automatic_key = (
                "Chinese"
                if language_from_locale(blender_locale()) == "ZH"
                else "English"
            )
            layout.label(
                text=tr("Automatic language: {language}", language=tr(automatic_key))
            )


CLASSES = (MeshAnnotationPreferences,)
