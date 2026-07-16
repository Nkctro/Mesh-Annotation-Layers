"""User actions for creating, assigning, selecting, and clearing layers."""

import bmesh
import bpy

from .constants import EDGE, ELEMENT_TYPES, FACE, VERTEX, element_spec
from .i18n import LocalizedDescription, tr
from .loops import (
    collect_edge_loop_edges,
    collect_face_loop_faces,
    collect_vertex_loop_vertices,
)
from .model import (
    active_layer,
    apply_layer_order_to_mapping,
    assign_elements_to_layer,
    auto_generate_color,
    clear_elements_from_layer,
    collect_layer_usage_from_selection,
    create_layer,
    ensure_lookup_tables,
    get_active_index,
    get_layer_by_id,
    get_layer_collection,
    get_next_layer_id,
    mark_face_layer_edges_as_seam,
    remove_layer,
    select_elements_for_layer,
    set_active_index,
)
from .overlay import tag_view3d_redraw


class MESH_OT_annotation_toggle_overlay(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_toggle_overlay"
    bl_label = "Toggle Annotation Overlay"
    bl_options = {"INTERNAL"}
    tooltip_key = "Show or hide annotation overlays in the viewport."

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        settings = context.object.mesh_annotations
        settings.enable_overlay = not settings.enable_overlay
        return {"FINISHED"}


class MESH_OT_annotation_toggle_solo(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_toggle_solo"
    bl_label = "Toggle Solo Annotation Layer"
    bl_options = {"INTERNAL"}
    tooltip_key = "Show only the active annotation layer for each element type."

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        settings = context.object.mesh_annotations
        settings.solo_active = not settings.solo_active
        return {"FINISHED"}


class MESH_OT_annotation_toggle_layer_visibility(
    LocalizedDescription, bpy.types.Operator
):
    bl_idname = "mesh.annotation_toggle_layer_visibility"
    bl_label = "Toggle Annotation Layer Visibility"
    bl_options = {"INTERNAL"}
    tooltip_key = "Show or hide this annotation layer."

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )
    layer_id: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        settings = context.object.mesh_annotations
        layer = get_layer_by_id(settings, self.element_type, self.layer_id)
        if layer is None:
            self.report({"WARNING"}, tr("Layer not found"))
            return {"CANCELLED"}
        layer.is_visible = not layer.is_visible
        return {"FINISHED"}


class MESH_OT_annotation_layer_add(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_layer_add"
    bl_label = tr('Add Annotation Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Create a new annotation layer for the current element type."

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, tr('Select a mesh object'))
            return {"CANCELLED"}
        settings = obj.mesh_annotations
        create_layer(settings, self.element_type)
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_layer_remove(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_layer_remove"
    bl_label = tr('Remove Annotation Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Delete the active annotation layer and remove its assignments."

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        index = get_active_index(settings, self.element_type)
        if index < 0:
            self.report({"WARNING"}, tr('No active layer selected'))
            return {"CANCELLED"}
        remove_layer(settings, obj, self.element_type, index)
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_layer_move(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_layer_move"
    bl_label = tr('Reorder Annotation Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Move the active layer up or down in the overlay order."

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )
    direction: bpy.props.EnumProperty(
        name="Direction",
        items=(
            ("UP", "Up", "Move the layer up"),
            ("DOWN", "Down", "Move the layer down"),
        ),
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != "MESH":
            return False
        settings = getattr(obj, "mesh_annotations", None)
        if not settings:
            return False
        for etype in ELEMENT_TYPES:
            if len(get_layer_collection(settings, etype)) > 1:
                return True
        return False

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        collection = get_layer_collection(settings, self.element_type)
        idx = get_active_index(settings, self.element_type)
        if not (0 <= idx < len(collection)):
            return {"CANCELLED"}
        offset = -1 if self.direction == "UP" else 1
        new_idx = idx + offset
        if new_idx < 0 or new_idx >= len(collection):
            return {"CANCELLED"}
        collection.move(idx, new_idx)
        set_active_index(settings, self.element_type, new_idx)
        apply_layer_order_to_mapping(obj, self.element_type)
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_active(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_assign_active"
    bl_label = tr('Assign Selection to Active Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Add the selected elements to the active annotation layer."

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = active_layer(settings, self.element_type)
        if layer is None:
            self.report({"WARNING"}, tr('No active layer selected'))
            return {"CANCELLED"}
        if not assign_elements_to_layer(obj, self.element_type, layer.layer_id):
            self.report({"WARNING"}, tr('Select at least one element'))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_select_layer(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_select_layer"
    bl_label = tr('Select Elements in Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Select every mesh element assigned to this layer."

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )
    layer_id: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        count = select_elements_for_layer(obj, self.element_type, self.layer_id)
        if count == 0:
            self.report({"INFO"}, tr('Layer is empty'))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_activate_from_selection(
    LocalizedDescription, bpy.types.Operator
):
    bl_idname = "mesh.annotation_activate_from_selection"
    bl_label = tr('Pick Active Layer From Selection')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Make the layer used most by the current selection active."

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        usage = collect_layer_usage_from_selection(obj, self.element_type)
        if not usage:
            self.report({"WARNING"}, tr('Selected elements do not belong to any layer'))
            return {"CANCELLED"}
        layer_id, _count = usage.most_common(1)[0]
        collection = get_layer_collection(settings, self.element_type)
        for idx, layer in enumerate(collection):
            if layer.layer_id == layer_id:
                set_active_index(settings, self.element_type, idx)
                tag_view3d_redraw(context)
                return {"FINISHED"}
        self.report({"WARNING"}, tr('Layer not found'))
        return {"CANCELLED"}


class MESH_OT_annotation_assign_loop(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_assign_loop"
    bl_label = tr('Assign Loop to Active Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Derive a complete loop or path from the selection and add it to the active layer."
    )

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = active_layer(settings, self.element_type)
        if layer is None:
            self.report({"WARNING"}, tr('No active layer selected'))
            return {"CANCELLED"}
        bm = bmesh.from_edit_mesh(obj.data)
        if self.element_type == FACE:
            loop_elems, message = collect_face_loop_faces(context, obj, bm, settings)
            indices = [face.index for face in loop_elems]
        elif self.element_type == EDGE:
            loop_elems, message = collect_edge_loop_edges(context, obj, bm, settings)
            indices = [edge.index for edge in loop_elems]
        else:
            loop_elems, message = collect_vertex_loop_vertices(context, obj, bm, settings)
            indices = [vert.index for vert in loop_elems]
        if message:
            self.report({"INFO"}, message)
            return {"CANCELLED"}
        if not assign_elements_to_layer(
            obj, self.element_type, layer.layer_id, element_indices=indices
        ):
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_valence(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_assign_valence"
    bl_label = tr('Annotate Vertices by Valence')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Add every vertex with the chosen valence to the active vertex layer."
    )

    valence: bpy.props.IntProperty(
        name="Valence",
        description="Number of connected edges",
        min=0,
        max=128,
        default=4,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = active_layer(settings, VERTEX)
        if layer is None:
            self.report({"WARNING"}, tr('No active vertex layer selected'))
            return {"CANCELLED"}
        bm = bmesh.from_edit_mesh(obj.data)
        ensure_lookup_tables(bm, VERTEX)
        target_indices = [vert.index for vert in bm.verts if len(vert.link_edges) == self.valence]
        if not target_indices:
            self.report({"INFO"}, tr('No vertices found with that valence'))
            return {"CANCELLED"}
        if not assign_elements_to_layer(
            obj, VERTEX, layer.layer_id, element_indices=target_indices
        ):
            self.report({"WARNING"}, tr('Failed to assign vertices'))
            return {"CANCELLED"}
        self.report({"INFO"}, tr("Annotated {count} vertices", count=len(target_indices)))
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_valence_new_layer(
    LocalizedDescription, bpy.types.Operator
):
    bl_idname = "mesh.annotation_assign_valence_new_layer"
    bl_label = tr('Annotate Valence to New Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Create a vertex layer and add every vertex with the chosen valence."
    )

    valence: bpy.props.IntProperty(
        name="Valence",
        description="Number of connected edges",
        min=0,
        max=128,
        default=4,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        bm = bmesh.from_edit_mesh(obj.data)
        ensure_lookup_tables(bm, VERTEX)
        target_indices = [vert.index for vert in bm.verts if len(vert.link_edges) == self.valence]
        if not target_indices:
            self.report({"INFO"}, tr('No vertices found with that valence'))
            return {"CANCELLED"}
        next_id_attr = element_spec(VERTEX).next_id
        previous_next_id = getattr(settings, next_id_attr)
        layer = create_layer(settings, VERTEX)
        if not assign_elements_to_layer(
            obj, VERTEX, layer.layer_id, element_indices=target_indices
        ):
            collection = get_layer_collection(settings, VERTEX)
            collection.remove(len(collection) - 1)
            setattr(settings, next_id_attr, previous_next_id)
            self.report({"WARNING"}, tr('Nothing assigned; new layer cancelled'))
            return {"CANCELLED"}
        self.report({"INFO"}, tr("Annotated {count} vertices", count=len(target_indices)))
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_new_layer(
    LocalizedDescription, bpy.types.Operator
):
    bl_idname = "mesh.annotation_assign_new_layer"
    bl_label = tr('Assign Selection to New Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Create a new layer and add the selection or derived loop to it."
    )

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )
    use_loop: bpy.props.BoolProperty(default=False)
    skip_dialog: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    layer_name: bpy.props.StringProperty(name="Layer Name")
    color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype="COLOR_GAMMA",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.9, 0.6, 0.2, 0.4),
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def invoke(self, context, event):
        settings = context.object.mesh_annotations
        default_name = (
            f"{element_spec(self.element_type).default_name} "
            f"{get_next_layer_id(settings, self.element_type)}"
        )
        self.layer_name = default_name
        self.color = auto_generate_color(settings, self.element_type)
        if self.skip_dialog:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "layer_name", text=tr('Layer Name'))
        layout.prop(self, "color", text=tr('Color'))

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        indices = None
        if self.use_loop:
            bm = bmesh.from_edit_mesh(obj.data)
            if self.element_type == FACE:
                loop_elems, message = collect_face_loop_faces(context, obj, bm, settings)
                indices = [face.index for face in loop_elems]
            elif self.element_type == EDGE:
                loop_elems, message = collect_edge_loop_edges(context, obj, bm, settings)
                indices = [edge.index for edge in loop_elems]
            else:
                loop_elems, message = collect_vertex_loop_vertices(context, obj, bm, settings)
                indices = [vert.index for vert in loop_elems]
            if message:
                self.report({"INFO"}, message)
                return {"CANCELLED"}
        next_id_attr = element_spec(self.element_type).next_id
        previous_next_id = getattr(settings, next_id_attr)
        layer = create_layer(
            settings,
            self.element_type,
            name=self.layer_name.strip() or None,
            color=self.color,
        )
        if not assign_elements_to_layer(
            obj, self.element_type, layer.layer_id, element_indices=indices
        ):
            collection = get_layer_collection(settings, self.element_type)
            collection.remove(len(collection) - 1)
            setattr(settings, next_id_attr, previous_next_id)
            self.report({"WARNING"}, tr('Nothing assigned; new layer cancelled'))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_layer(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_assign_layer"
    bl_label = tr('Assign Selection to Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Add the selection or derived loop to this existing layer."

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )
    layer_id: bpy.props.IntProperty()
    use_loop: bpy.props.BoolProperty(default=False)
    make_active: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = get_layer_by_id(settings, self.element_type, self.layer_id)
        if layer is None:
            self.report({"WARNING"}, tr('Layer not found'))
            return {"CANCELLED"}
        indices = None
        if self.use_loop:
            bm = bmesh.from_edit_mesh(obj.data)
            if self.element_type == FACE:
                loop_elems, message = collect_face_loop_faces(context, obj, bm, settings)
                indices = [face.index for face in loop_elems]
            elif self.element_type == EDGE:
                loop_elems, message = collect_edge_loop_edges(context, obj, bm, settings)
                indices = [edge.index for edge in loop_elems]
            else:
                loop_elems, message = collect_vertex_loop_vertices(context, obj, bm, settings)
                indices = [vert.index for vert in loop_elems]
            if message:
                self.report({"INFO"}, message)
                return {"CANCELLED"}
        if not assign_elements_to_layer(
            obj, self.element_type, layer.layer_id, element_indices=indices
        ):
            self.report({"WARNING"}, tr('Select at least one element'))
            return {"CANCELLED"}
        if self.make_active:
            collection = get_layer_collection(settings, self.element_type)
            for index, candidate in enumerate(collection):
                if candidate.layer_id == layer.layer_id:
                    set_active_index(settings, self.element_type, index)
                    break
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_mark_seam_active(
    LocalizedDescription, bpy.types.Operator
):
    bl_idname = "mesh.annotation_mark_seam_active_face_layer"
    bl_label = tr('Mark Active Layer Seams')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Mark the boundary edges of the active face layer as UV seams."

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != "MESH" or context.mode != "EDIT_MESH":
            return False
        settings = getattr(obj, "mesh_annotations", None)
        if not settings:
            return False
        layer = active_layer(settings, FACE)
        return layer is not None

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = active_layer(settings, FACE)
        count = mark_face_layer_edges_as_seam(obj, [layer.layer_id])
        if count == 0:
            self.report({"INFO"}, tr('No seams updated'))
        else:
            self.report({"INFO"}, tr("Marked {count} edges", count=count))
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_mark_seam_all(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_mark_seam_all_face_layers"
    bl_label = tr('Mark All Layer Seams')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Mark the boundary edges of every face layer as UV seams."

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != "MESH" or context.mode != "EDIT_MESH":
            return False
        settings = getattr(obj, "mesh_annotations", None)
        if not settings:
            return False
        return len(settings.face_layers) > 0

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer_ids = [layer.layer_id for layer in settings.face_layers]
        count = mark_face_layer_edges_as_seam(obj, layer_ids)
        if count == 0:
            self.report({"INFO"}, tr('No seams updated'))
        else:
            self.report({"INFO"}, tr("Marked {count} edges", count=count))
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_clear_selected(LocalizedDescription, bpy.types.Operator):
    bl_idname = "mesh.annotation_clear_selected"
    bl_label = tr('Clear Annotation From Selected')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Remove the active, topmost, or all annotation assignments from selected elements."
    )

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
    )
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            (
                "ACTIVE",
                "Active Layer",
                "Remove only the active annotation layer from the selection",
            ),
            ("ALL", "All Layers", "Remove all annotations from the selection"),
            (
                "TOP",
                "Top Layer Only",
                "Remove only the highest annotation in layer order",
            ),
        ),
        default="ACTIVE",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        layer_id = -1
        if self.mode == "ACTIVE":
            layer = active_layer(obj.mesh_annotations, self.element_type)
            if layer is None:
                self.report({"WARNING"}, tr('No active layer selected'))
                return {"CANCELLED"}
            layer_id = layer.layer_id
        clear_elements_from_layer(
            obj,
            self.element_type,
            layer_id,
            only_selected=True,
            mode=self.mode,
        )
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_set_element_type(
    LocalizedDescription, bpy.types.Operator
):
    bl_idname = "mesh.annotation_set_element_type"
    bl_label = tr('Switch Annotation Type')
    bl_options = {"INTERNAL"}
    tooltip_key = "Switch the annotation workspace and mesh selection mode."

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layers"),
            (EDGE, "Edge", "Edge layers"),
            (VERTEX, "Vertex", "Vertex layers"),
        ),
        default=FACE,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        settings = context.object.mesh_annotations
        settings.ui_element_type = self.element_type
        if context.mode == "EDIT_MESH":
            target_mode = [False, False, False]
            target_mode[element_spec(self.element_type).select_mode_index] = True
            context.tool_settings.mesh_select_mode = tuple(target_mode)
        tag_view3d_redraw(context, invalidate_cache=False)
        return {"FINISHED"}


class MESH_OT_annotation_enter_edit_mode(
    LocalizedDescription, bpy.types.Operator
):
    bl_idname = "mesh.annotation_enter_edit_mode"
    bl_label = tr('Edit Annotations')
    tooltip_key = "Switch to Edit Mode to change annotation assignments"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode != "EDIT_MESH"

    def execute(self, context):
        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


CLASSES = (
    MESH_OT_annotation_toggle_overlay,
    MESH_OT_annotation_toggle_solo,
    MESH_OT_annotation_toggle_layer_visibility,
    MESH_OT_annotation_layer_add,
    MESH_OT_annotation_layer_remove,
    MESH_OT_annotation_layer_move,
    MESH_OT_annotation_assign_active,
    MESH_OT_annotation_select_layer,
    MESH_OT_annotation_activate_from_selection,
    MESH_OT_annotation_assign_loop,
    MESH_OT_annotation_assign_valence,
    MESH_OT_annotation_assign_valence_new_layer,
    MESH_OT_annotation_assign_new_layer,
    MESH_OT_annotation_assign_layer,
    MESH_OT_annotation_mark_seam_active,
    MESH_OT_annotation_mark_seam_all,
    MESH_OT_annotation_clear_selected,
    MESH_OT_annotation_set_element_type,
    MESH_OT_annotation_enter_edit_mode,
)
