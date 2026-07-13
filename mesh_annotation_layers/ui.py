"""Viewport menus, layer list, and sidebar panels."""

import bpy

from .constants import EDGE, ELEMENT_TYPES, FACE, VERTEX, element_spec
from .i18n import addon_preferences, tr
from .loops import element_labels
from .model import (
    active_layer,
    count_elements_for_layer,
    get_layer_collection,
    infer_element_type_from_mode,
)


def draw_existing_layer_menu(layout, obj, element_type: str, use_loop: bool):
    settings = getattr(obj, "mesh_annotations", None)
    if not settings:
        layout.label(text=tr('No layers'))
        return
    collection = get_layer_collection(settings, element_type)
    if not collection:
        layout.label(text=tr('No layers'))
        return
    for layer in collection:
        count = count_elements_for_layer(obj, element_type, layer.layer_id)
        text = f"{layer.name} ({count})" if count else layer.name
        operator = layout.operator("mesh.annotation_assign_layer", text=text, icon="BRUSH_DATA")
        operator.layer_id = layer.layer_id
        operator.element_type = element_type
        operator.use_loop = use_loop


def context_menu_use_type_choice():
    prefs = addon_preferences()
    return bool(prefs and getattr(prefs, "context_menu_split_types", True))


def context_menu_default_type(context):
    return infer_element_type_from_mode(context)


TYPE_MENU_ACTIONS = {
    "assign_selected_active": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_active",
        "props": {},
        "label": "Choose Element Type",
    },
    "assign_selected_new": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_new_layer",
        "props": {"use_loop": False, "skip_dialog": True},
        "label": "Choose Element Type",
    },
    "assign_selected_existing": {
        "kind": "existing",
        "use_loop": False,
        "label": "Choose Element Type",
    },
    "assign_loop_active": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_loop",
        "props": {},
        "label": "Choose Element Type",
    },
    "assign_loop_new": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_new_layer",
        "props": {"use_loop": True, "skip_dialog": True},
        "label": "Choose Element Type",
    },
    "assign_loop_existing": {
        "kind": "existing",
        "use_loop": True,
        "label": "Choose Element Type",
    },
    "clear_selected_all": {
        "kind": "clear",
        "mode": "ALL",
        "label": "Choose Element Type",
    },
    "clear_selected_top": {
        "kind": "clear",
        "mode": "TOP",
        "label": "Choose Element Type",
    },
    "clear_selected_active": {
        "kind": "clear",
        "mode": "ACTIVE",
        "label": "Choose Element Type",
    },
}


class MeshAnnotationTypeMenuBase(bpy.types.Menu):
    bl_label = tr('Choose Element Type')
    action_key = ""

    def draw(self, context):
        layout = self.layout
        action = TYPE_MENU_ACTIONS.get(self.action_key)
        if not action:
            layout.label(text=tr('No action configured'))
            return
        layout.label(text=tr(action.get("label", "Choose Element Type")))
        obj = context.object
        for element_type in ELEMENT_TYPES:
            meta = element_spec(element_type)
            text = tr(meta.label)
            icon = meta.icon
            kind = action["kind"]
            if kind == "operator":
                op = layout.operator(action["operator"], text=text, icon=icon)
                op.element_type = element_type
                for attr, value in action.get("props", {}).items():
                    setattr(op, attr, value)
            elif kind == "existing":
                col = layout.column()
                col.label(text=text, icon=icon)
                draw_existing_layer_menu(
                    col,
                    obj,
                    element_type,
                    use_loop=action.get("use_loop", False),
                )
            elif kind == "clear":
                op = layout.operator("mesh.annotation_clear_selected", text=text, icon=icon)
                op.element_type = element_type
                op.mode = action["mode"]
            else:
                layout.label(text=tr('Unsupported action'), icon="ERROR")


class VIEW3D_MT_mesh_annotation_type_assign_selected_active(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_selected_active"
    action_key = "assign_selected_active"


class VIEW3D_MT_mesh_annotation_type_assign_selected_new(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_selected_new"
    action_key = "assign_selected_new"


class VIEW3D_MT_mesh_annotation_type_assign_selected_existing(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_selected_existing"
    action_key = "assign_selected_existing"


class VIEW3D_MT_mesh_annotation_type_assign_loop_active(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_loop_active"
    action_key = "assign_loop_active"


class VIEW3D_MT_mesh_annotation_type_assign_loop_new(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_loop_new"
    action_key = "assign_loop_new"


class VIEW3D_MT_mesh_annotation_type_assign_loop_existing(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_loop_existing"
    action_key = "assign_loop_existing"


class VIEW3D_MT_mesh_annotation_type_clear_selected_all(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_clear_selected_all"
    action_key = "clear_selected_all"


class VIEW3D_MT_mesh_annotation_type_clear_selected_top(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_clear_selected_top"
    action_key = "clear_selected_top"


class VIEW3D_MT_mesh_annotation_type_clear_selected_active(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_clear_selected_active"
    action_key = "clear_selected_active"


def add_assign_selected_active_entry(layout, context):
    text = tr('Assign Selected to Active Layer')
    if context_menu_use_type_choice():
        layout.menu(
            "VIEW3D_MT_mesh_annotation_type_assign_selected_active",
            text=text,
            icon="BRUSH_DATA",
        )
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_assign_active", text=text, icon="BRUSH_DATA")
        op.element_type = element_type


def add_assign_selected_new_entry(layout, context):
    text = tr('Assign Selected to New Layer')
    if context_menu_use_type_choice():
        layout.menu("VIEW3D_MT_mesh_annotation_type_assign_selected_new", text=text, icon="ADD")
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_assign_new_layer", text=text, icon="ADD")
        op.element_type = element_type
        op.use_loop = False
        op.skip_dialog = True


def add_assign_selected_existing_entry(layout, context):
    text = tr('Assign Selected to Existing Layer')
    if context_menu_use_type_choice():
        layout.menu(
            "VIEW3D_MT_mesh_annotation_type_assign_selected_existing",
            text=text,
            icon="GROUP_VCOL",
        )
    else:
        layout.label(text=text, icon="GROUP_VCOL")
        element_type = context_menu_default_type(context)
        draw_existing_layer_menu(layout, context.object, element_type, use_loop=False)


def add_assign_loop_active_entry(layout, context):
    text = tr('Assign Loop to Active Layer')
    if context_menu_use_type_choice():
        layout.menu(
            "VIEW3D_MT_mesh_annotation_type_assign_loop_active",
            text=text,
            icon="BRUSH_DATA",
        )
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_assign_loop", text=text, icon="BRUSH_DATA")
        op.element_type = element_type


def add_assign_loop_new_entry(layout, context):
    text = tr('Assign Loop to New Layer')
    if context_menu_use_type_choice():
        layout.menu("VIEW3D_MT_mesh_annotation_type_assign_loop_new", text=text, icon="ADD")
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_assign_new_layer", text=text, icon="ADD")
        op.element_type = element_type
        op.use_loop = True
        op.skip_dialog = True


def add_assign_loop_existing_entry(layout, context):
    text = tr('Assign Loop to Existing Layer')
    if context_menu_use_type_choice():
        layout.menu(
            "VIEW3D_MT_mesh_annotation_type_assign_loop_existing",
            text=text,
            icon="GROUP_VCOL",
        )
    else:
        layout.label(text=text, icon="GROUP_VCOL")
        element_type = context_menu_default_type(context)
        draw_existing_layer_menu(layout, context.object, element_type, use_loop=True)


def add_clear_selected_entry(layout, context, mode: str):
    if mode == "ACTIVE":
        text = tr('Clear Selected (Active Layer)')
        icon = "REMOVE"
    elif mode == "ALL":
        text = tr('Clear Selected (All Layers)')
        icon = "X"
    else:
        text = tr('Clear Selected (Top Layer)')
        icon = "REMOVE"
    if context_menu_use_type_choice():
        menu_ids = {
            "ACTIVE": "VIEW3D_MT_mesh_annotation_type_clear_selected_active",
            "ALL": "VIEW3D_MT_mesh_annotation_type_clear_selected_all",
            "TOP": "VIEW3D_MT_mesh_annotation_type_clear_selected_top",
        }
        menu_id = menu_ids[mode]
        layout.menu(menu_id, text=text, icon=icon)
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_clear_selected", text=text, icon=icon)
        op.element_type = element_type
        op.mode = mode


class VIEW3D_MT_mesh_annotation_add(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_add"
    bl_label = tr('Add')

    def draw(self, context):
        layout = self.layout
        layout.menu(
            "VIEW3D_MT_mesh_annotation_add_selected",
            text=tr('Selected Elements'),
            icon="FACESEL",
        )
        layout.menu(
            "VIEW3D_MT_mesh_annotation_add_loop",
            text=tr('Loops / Paths'),
            icon="EDGESEL",
        )


class VIEW3D_MT_mesh_annotation_add_selected(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_add_selected"
    bl_label = tr('Selected Elements')

    def draw(self, context):
        layout = self.layout
        add_assign_selected_active_entry(layout, context)
        add_assign_selected_new_entry(layout, context)
        add_assign_selected_existing_entry(layout, context)


class VIEW3D_MT_mesh_annotation_add_loop(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_add_loop"
    bl_label = tr('Loops / Paths')

    def draw(self, context):
        layout = self.layout
        add_assign_loop_active_entry(layout, context)
        add_assign_loop_new_entry(layout, context)
        add_assign_loop_existing_entry(layout, context)


class VIEW3D_MT_mesh_annotation_remove(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_remove"
    bl_label = tr('Remove')

    def draw(self, context):
        layout = self.layout
        layout.menu(
            "VIEW3D_MT_mesh_annotation_remove_selected",
            text=tr('Selected Elements'),
            icon="TRASH",
        )


class VIEW3D_MT_mesh_annotation_remove_selected(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_remove_selected"
    bl_label = tr('Remove Selected')

    def draw(self, context):
        layout = self.layout
        add_clear_selected_entry(layout, context, mode="ACTIVE")
        add_clear_selected_entry(layout, context, mode="TOP")
        add_clear_selected_entry(layout, context, mode="ALL")


class MESH_UL_annotation_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layer = item
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            icon_id = "HIDE_OFF" if layer.is_visible else "HIDE_ON"
            visibility = row.operator(
                "mesh.annotation_toggle_layer_visibility",
                text="",
                emboss=False,
                icon=icon_id,
            )
            visibility.element_type = layer.element_type
            visibility.layer_id = layer.layer_id
            row.prop(layer, "color", text="")
            row.prop(layer, "name", text="", emboss=False)
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=layer.name)


class VIEW3D_MT_mesh_annotation_context(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_context"
    bl_label = tr('Mesh Annotation')

    def draw(self, context):
        layout = self.layout
        obj = context.object
        if not obj or obj.type != "MESH" or context.mode != "EDIT_MESH":
            layout.label(text=tr('Switch to Edit Mode to use annotations'), icon="INFO")
            return
        layout.menu("VIEW3D_MT_mesh_annotation_add", text=tr('Add'), icon="ADD")
        layout.menu("VIEW3D_MT_mesh_annotation_remove", text=tr('Remove'), icon="TRASH")


class VIEW3D_PT_mesh_annotation(bpy.types.Panel):
    bl_label = tr('Mesh Annotation')
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = tr('Mesh Annotation')

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        obj = context.object
        settings = obj.mesh_annotations

        toolbar = layout.row(align=True)
        toolbar.operator(
            "mesh.annotation_toggle_overlay",
            text=tr('Overlay'),
            icon="HIDE_OFF" if settings.enable_overlay else "HIDE_ON",
            depress=settings.enable_overlay,
        )
        solo_column = toolbar.row(align=True)
        solo_column.enabled = settings.enable_overlay
        solo_column.operator(
            "mesh.annotation_toggle_solo",
            text=tr('Solo'),
            depress=settings.solo_active,
        )

        if context.mode == "EDIT_MESH":
            active_element_type = infer_element_type_from_mode(context)
        else:
            active_element_type = settings.ui_element_type

        type_tabs = layout.row(align=True)
        type_tabs.scale_y = 1.15
        tab_labels = {FACE: "Faces", EDGE: "Edges", VERTEX: "Vertices"}
        for element_type in ELEMENT_TYPES:
            tab = type_tabs.operator(
                "mesh.annotation_set_element_type",
                text=tr(tab_labels[element_type]),
                icon=element_spec(element_type).icon,
                depress=active_element_type == element_type,
            )
            tab.element_type = element_type

        if context.mode != "EDIT_MESH":
            mode_labels = {
                "OBJECT": "Object Mode",
                "PAINT_WEIGHT": "Weight Paint",
                "PAINT_VERTEX": "Vertex Paint",
                "SCULPT": "Sculpt Mode",
                "PAINT_TEXTURE": "Texture Paint",
            }
            mode_key = mode_labels.get(context.mode, context.mode.replace("_", " ").title())
            status = layout.box()
            status.label(
                text=tr("Visible in {mode}; assignments are read-only", mode=tr(mode_key)),
                icon="INFO",
            )
            status.operator(
                "mesh.annotation_enter_edit_mode",
                text=tr('Switch to Edit Mode to Edit'),
            )

        self.draw_layer_workspace(layout, context, obj, settings, active_element_type)

    def draw_layer_workspace(self, parent_layout, context, obj, settings, element_type):
        selection_label = tr(element_labels(element_type)[0])
        box = parent_layout.box()
        row = box.row()
        row.template_list(
            "MESH_UL_annotation_layers",
            element_type,
            settings,
            element_spec(element_type).collection,
            settings,
            element_spec(element_type).active_index,
            rows=4,
        )
        col = row.column(align=True)
        op_add = col.operator("mesh.annotation_layer_add", icon="ADD", text="")
        op_add.element_type = element_type
        op_remove = col.operator("mesh.annotation_layer_remove", icon="REMOVE", text="")
        op_remove.element_type = element_type
        move_up = col.operator("mesh.annotation_layer_move", icon="TRIA_UP", text="")
        move_up.element_type = element_type
        move_up.direction = "UP"
        move_down = col.operator("mesh.annotation_layer_move", icon="TRIA_DOWN", text="")
        move_down.element_type = element_type
        move_down.direction = "DOWN"

        collection = get_layer_collection(settings, element_type)
        layer = active_layer(settings, element_type)
        if layer:
            count = count_elements_for_layer(obj, element_type, layer.layer_id)
            summary = box.row(align=True)
            summary.label(
                text=tr(
                    "Active · {name} · {count} {selection}",
                    name=layer.name,
                    count=count,
                    selection=selection_label,
                )
            )
        elif not collection:
            box.label(text=tr("No layers yet — use + to create one"), icon="INFO")

        if context.mode == "EDIT_MESH":
            if collection:
                row_info = box.row(align=True)
                row_info.enabled = layer is not None
                op = row_info.operator(
                    "mesh.annotation_select_layer",
                    text=tr('Select Layer'),
                )
                if layer:
                    op.layer_id = layer.layer_id
                op.element_type = element_type
                picker = row_info.operator(
                    "mesh.annotation_activate_from_selection",
                    text=tr('Pick Layer'),
                    icon="EYEDROPPER",
                )
                picker.element_type = element_type

            box.separator(factor=0.5)
            row_assign = box.row(align=True)
            row_assign.enabled = layer is not None
            assign_active = row_assign.operator(
                "mesh.annotation_assign_active",
                text=tr('Add Selected'),
            )
            assign_active.element_type = element_type
            assign_loop = row_assign.operator(
                "mesh.annotation_assign_loop",
                text=tr('Add Loop'),
            )
            assign_loop.element_type = element_type
            row_new = box.row(align=True)
            new_layer = row_new.operator(
                "mesh.annotation_assign_new_layer",
                text=tr("Selected → New Layer"),
                icon="ADD",
            )
            new_layer.element_type = element_type
            new_layer.use_loop = False
            new_layer.skip_dialog = True
            new_loop = row_new.operator(
                "mesh.annotation_assign_new_layer",
                text=tr("Loop → New Layer"),
                icon="ADD",
            )
            new_loop.element_type = element_type
            new_loop.use_loop = True
            new_loop.skip_dialog = True
            if element_type == VERTEX:
                valence_row = box.row(align=True)
                valence_row.prop(settings, "auto_valence_n", text=tr('Valence'))
                valence_op = valence_row.operator(
                    "mesh.annotation_assign_valence",
                    text=tr('Annotate'),
                )
                valence_op.valence = settings.auto_valence_n
                valence_new_row = box.row(align=True)
                valence_new = valence_new_row.operator(
                    "mesh.annotation_assign_valence_new_layer",
                    text=tr("Valence → New Layer"),
                    icon="ADD",
                )
                valence_new.valence = settings.auto_valence_n
            if element_type == FACE:
                seam_row = box.row(align=True)
                seam_row.operator(
                    "mesh.annotation_mark_seam_active_face_layer",
                    text=tr('Mark Seams (Layer)'),
                    icon="MOD_UVPROJECT",
                )
                seam_row.operator(
                    "mesh.annotation_mark_seam_all_face_layers",
                    text=tr('Mark Seams (All)'),
                    icon="MOD_UVPROJECT",
                )
            box.separator(factor=0.5)
            clear_op = box.operator(
                "mesh.annotation_clear_selected",
                text=tr('Remove Selected From Active Layer'),
                icon="REMOVE",
            )
            clear_op.element_type = element_type
            clear_op.mode = "ACTIVE"


class VIEW3D_PT_mesh_annotation_display(bpy.types.Panel):
    bl_label = tr('Display')
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = tr('Mesh Annotation')
    bl_parent_id = "VIEW3D_PT_mesh_annotation"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.object.mesh_annotations
        content = layout.column()
        content.enabled = settings.enable_overlay
        content.prop(settings, "overlay_alpha_multiplier", text=tr('Opacity'))
        content.prop(settings, "overlay_show_backfaces", text=tr('Show Through Mesh'))

        content.separator()
        content.label(text=tr('Faces'), icon="FACESEL")
        content.prop(settings, "overlay_face_offset", text=tr('Surface Offset'))

        content.separator()
        content.label(text=tr('Edges'), icon="EDGESEL")
        content.prop(settings, "overlay_edge_offset", text=tr('Surface Offset'))
        content.prop(settings, "overlay_line_width", text=tr('Thickness'))
        content.prop(settings, "overlay_edge_trim", text=tr('Shortening'))

        content.separator()
        content.label(text=tr('Vertices'), icon="VERTEXSEL")
        content.prop(settings, "overlay_vertex_offset", text=tr('Surface Offset'))
        content.prop(settings, "overlay_point_size", text=tr('Point Size'))

        layout.separator()
        layout.prop(settings, "debug_output", text=tr('Debug Output'))


def draw_context_menu(self, context):
    obj = context.object
    if not obj or obj.type != "MESH" or context.mode != "EDIT_MESH":
        return
    layout = self.layout
    layout.separator()
    layout.menu(
        "VIEW3D_MT_mesh_annotation_context",
        text=tr('Mesh Annotation'),
        icon="GROUP_VCOL",
    )


CLASSES = (
    MESH_UL_annotation_layers,
    VIEW3D_MT_mesh_annotation_type_assign_selected_active,
    VIEW3D_MT_mesh_annotation_type_assign_selected_new,
    VIEW3D_MT_mesh_annotation_type_assign_selected_existing,
    VIEW3D_MT_mesh_annotation_type_assign_loop_active,
    VIEW3D_MT_mesh_annotation_type_assign_loop_new,
    VIEW3D_MT_mesh_annotation_type_assign_loop_existing,
    VIEW3D_MT_mesh_annotation_type_clear_selected_all,
    VIEW3D_MT_mesh_annotation_type_clear_selected_top,
    VIEW3D_MT_mesh_annotation_type_clear_selected_active,
    VIEW3D_MT_mesh_annotation_add,
    VIEW3D_MT_mesh_annotation_add_selected,
    VIEW3D_MT_mesh_annotation_add_loop,
    VIEW3D_MT_mesh_annotation_remove,
    VIEW3D_MT_mesh_annotation_remove_selected,
    VIEW3D_MT_mesh_annotation_context,
    VIEW3D_PT_mesh_annotation,
    VIEW3D_PT_mesh_annotation_display,
)



def register():
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.append(draw_context_menu)


def unregister():
    try:
        bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(draw_context_menu)
    except (RuntimeError, ValueError):
        pass
