"""Viewport menus, layer list, and sidebar panels."""

import bpy

from .constants import EDGE, ELEMENT_TYPES, FACE, VERTEX, element_spec
from .i18n import tr
from .model import (
    active_layer,
    annotation_mesh_is_shared,
    count_elements_for_layer,
    get_layer_collection,
    infer_element_type_from_mode,
)


def draw_existing_layer_menu(layout, obj, element_type: str, use_loop: bool):
    settings = obj.mesh_annotations
    collection = get_layer_collection(settings, element_type)
    if not collection:
        layout.label(text=tr('No layers'))
        return
    current = active_layer(settings, element_type)
    current_id = current.layer_id if current else -1
    for layer in collection:
        icon = "RADIOBUT_ON" if layer.layer_id == current_id else "RADIOBUT_OFF"
        operator = layout.operator(
            "mesh.annotation_assign_layer",
            text=layer.name,
            icon=icon,
        )
        operator.layer_id = layer.layer_id
        operator.element_type = element_type
        operator.use_loop = use_loop
        operator.make_active = True


class VIEW3D_MT_mesh_annotation_assign_selected_existing(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_assign_selected_existing"
    bl_label = tr('Choose Target Layer')

    def draw(self, context):
        draw_existing_layer_menu(
            self.layout,
            context.object,
            infer_element_type_from_mode(context),
            use_loop=False,
        )


class VIEW3D_MT_mesh_annotation_assign_loop_existing(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_assign_loop_existing"
    bl_label = tr('Choose Target Layer')

    def draw(self, context):
        draw_existing_layer_menu(
            self.layout,
            context.object,
            infer_element_type_from_mode(context),
            use_loop=True,
        )


def draw_active_assignment(layout, element_type: str, layer, *, use_loop: bool):
    row = layout.row()
    row.enabled = layer is not None
    layer_name = layer.name if layer else tr('No Active Layer')
    if use_loop:
        text = tr('Add Loop to {name}', name=layer_name)
        operator = row.operator(
            "mesh.annotation_assign_loop",
            text=text,
            icon="EDGESEL",
        )
    else:
        text = tr('Add Selected to {name}', name=layer_name)
        operator = row.operator(
            "mesh.annotation_assign_active",
            text=text,
            icon="BRUSH_DATA",
        )
    operator.element_type = element_type


def draw_new_layer_assignment(layout, element_type: str, *, use_loop: bool):
    text = tr('New Layer from Loop') if use_loop else tr('New Layer from Selected')
    operator = layout.operator(
        "mesh.annotation_assign_new_layer",
        text=text,
        icon="ADD",
    )
    operator.element_type = element_type
    operator.use_loop = use_loop


def draw_clear_assignment(layout, element_type: str, layer, mode: str):
    row = layout.row()
    if mode == "ACTIVE":
        row.enabled = layer is not None
        layer_name = layer.name if layer else tr('No Active Layer')
        text = tr('Remove Selected from {name}', name=layer_name)
        icon = "REMOVE"
    elif mode == "TOP":
        text = tr('Remove Top Annotation from Selected')
        icon = "REMOVE"
    else:
        text = tr('Remove All Annotations from Selected')
        icon = "TRASH"
    operator = row.operator(
        "mesh.annotation_clear_selected",
        text=text,
        icon=icon,
    )
    operator.element_type = element_type
    operator.mode = mode


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
            editor = row.row(align=True)
            editor.enabled = not annotation_mesh_is_shared(context.object)
            editor.prop(layer, "color", text="")
            editor.prop(layer, "name", text="", emboss=False)
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
        if annotation_mesh_is_shared(obj):
            layout.label(
                text=tr("Shared or linked mesh data is read-only for annotations"),
                icon="LOCKED",
            )
            layout.operator(
                "mesh.annotation_make_single_user",
                text=tr("Make Mesh Single User"),
                icon="DUPLICATE",
            )
            return
        element_type = infer_element_type_from_mode(context)
        meta = element_spec(element_type)
        layer = active_layer(obj.mesh_annotations, element_type)
        layer_name = layer.name if layer else tr('No Active Layer')

        layout.label(
            text=tr(
                '{type} · Active: {name}',
                type=tr(meta.label),
                name=layer_name,
            ),
            icon=meta.icon,
        )
        layout.separator()

        draw_active_assignment(layout, element_type, layer, use_loop=False)
        draw_new_layer_assignment(layout, element_type, use_loop=False)
        layout.menu(
            "VIEW3D_MT_mesh_annotation_assign_selected_existing",
            text=tr('Add Selected to Another Layer'),
            icon="GROUP_VCOL",
        )

        layout.separator()
        draw_active_assignment(layout, element_type, layer, use_loop=True)
        draw_new_layer_assignment(layout, element_type, use_loop=True)
        layout.menu(
            "VIEW3D_MT_mesh_annotation_assign_loop_existing",
            text=tr('Add Loop to Another Layer'),
            icon="GROUP_VCOL",
        )

        layout.separator()
        draw_clear_assignment(layout, element_type, layer, mode="ACTIVE")
        draw_clear_assignment(layout, element_type, layer, mode="TOP")
        draw_clear_assignment(layout, element_type, layer, mode="ALL")


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
        mesh_is_shared = annotation_mesh_is_shared(obj)

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

        if mesh_is_shared:
            linked = layout.box()
            linked.label(
                text=tr("Shared or linked mesh data is read-only for annotations"),
                icon="LOCKED",
            )
            linked.operator(
                "mesh.annotation_make_single_user",
                text=tr("Make Mesh Single User"),
                icon="DUPLICATE",
            )

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

        self.draw_layer_workspace(
            layout,
            context,
            obj,
            settings,
            active_element_type,
            editable=not mesh_is_shared,
        )

    def draw_layer_workspace(
        self,
        parent_layout,
        context,
        obj,
        settings,
        element_type,
        *,
        editable=True,
    ):
        selection_label = tr(element_spec(element_type).selection_label)
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
        col.enabled = editable
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

            actions = box.column()
            actions.enabled = editable
            actions.separator(factor=0.5)
            row_assign = actions.row(align=True)
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
            row_new = actions.row(align=True)
            new_layer = row_new.operator(
                "mesh.annotation_assign_new_layer",
                text=tr("Selected → New Layer"),
                icon="ADD",
            )
            new_layer.element_type = element_type
            new_layer.use_loop = False
            new_loop = row_new.operator(
                "mesh.annotation_assign_new_layer",
                text=tr("Loop → New Layer"),
                icon="ADD",
            )
            new_loop.element_type = element_type
            new_loop.use_loop = True
            if element_type == VERTEX:
                valence_row = actions.row(align=True)
                valence_row.prop(settings, "auto_valence_n", text=tr('Valence'))
                valence_op = valence_row.operator(
                    "mesh.annotation_assign_valence",
                    text=tr('Annotate'),
                )
                valence_op.valence = settings.auto_valence_n
                valence_new_row = actions.row(align=True)
                valence_new = valence_new_row.operator(
                    "mesh.annotation_assign_valence_new_layer",
                    text=tr("Valence → New Layer"),
                    icon="ADD",
                )
                valence_new.valence = settings.auto_valence_n
            if element_type == FACE:
                seam_row = actions.row(align=True)
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
            actions.separator(factor=0.5)
            clear_op = actions.operator(
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
    VIEW3D_MT_mesh_annotation_assign_selected_existing,
    VIEW3D_MT_mesh_annotation_assign_loop_existing,
    VIEW3D_MT_mesh_annotation_context,
    VIEW3D_PT_mesh_annotation,
    VIEW3D_PT_mesh_annotation_display,
)


def register():
    _remove_context_menu_callbacks()
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.append(draw_context_menu)


def unregister():
    _remove_context_menu_callbacks()


def _remove_context_menu_callbacks():
    menu = bpy.types.VIEW3D_MT_edit_mesh_context_menu
    identity = draw_context_menu.__module__, draw_context_menu.__name__
    callbacks = tuple(getattr(getattr(menu, "draw", None), "_draw_funcs", ()))
    for callback in callbacks:
        if callback is draw_context_menu or (
            getattr(callback, "__module__", None),
            getattr(callback, "__name__", None),
        ) == identity:
            try:
                menu.remove(callback)
            except (RuntimeError, ValueError):
                pass
