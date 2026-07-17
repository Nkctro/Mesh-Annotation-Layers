"""User actions for creating, assigning, selecting, and clearing layers."""

from functools import wraps

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
    annotation_mesh_is_shared,
    apply_layer_order_to_mapping,
    assign_elements_to_layer,
    clear_elements_from_layer,
    commit_prepared_element_layers,
    collect_layer_usage_from_selection,
    create_layer,
    ensure_annotation_mesh_editable,
    ensure_lookup_tables,
    get_active_index,
    get_layer_by_id,
    get_layer_collection,
    invalidate_element_layers_cache,
    load_element_layers,
    mark_face_layer_edges_as_seam,
    prepare_element_layers,
    rebuild_annotation_stacks,
    remove_layer,
    select_elements_for_layer,
    shared_annotation_mapping_statuses,
    shared_annotation_mappings_are_current,
    set_active_index,
    SharedMeshAnnotationError,
    StaleSharedAnnotationError,
    StackCapacityError,
    StackEncodingError,
)
from .overlay import tag_view3d_redraw


_ELEMENT_TYPE_ITEMS = (
    (FACE, "Face", "Face layer"),
    (EDGE, "Edge", "Edge layer"),
    (VERTEX, "Vertex", "Vertex layer"),
)


def _element_type_property():
    return bpy.props.EnumProperty(
        name="Element", items=_ELEMENT_TYPE_ITEMS, default=FACE
    )


def _valence_property():
    return bpy.props.IntProperty(
        name="Valence",
        description="Number of connected edges",
        min=0,
        max=128,
        default=4,
    )


class _MeshPoll:
    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"


class _EditMeshPoll(_MeshPoll):
    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.mode == "EDIT_MESH"


def annotation_write(method):
    """Make every annotation mutation fail atomically on unsafe mesh data."""

    @wraps(method)
    def guarded(self, context):
        try:
            ensure_annotation_mesh_editable(getattr(context, "object", None))
            return method(self, context)
        except SharedMeshAnnotationError:
            self.report(
                {"ERROR"},
                tr("Make the active object's mesh data single-user before editing annotations."),
            )
        except StackCapacityError:
            self.report(
                {"ERROR"},
                tr("Too many overlapping layers on one mesh element"),
            )
        except StackEncodingError:
            self.report(
                {"ERROR"},
                tr("Annotation storage is invalid; no changes were made"),
            )
        return {"CANCELLED"}

    return guarded


def _collect_loop_indices(context, obj, element_type: str):
    settings = obj.mesh_annotations
    bm = bmesh.from_edit_mesh(obj.data)
    collector = {
        FACE: collect_face_loop_faces,
        EDGE: collect_edge_loop_edges,
        VERTEX: collect_vertex_loop_vertices,
    }[element_type]
    elements, message = collector(context, obj, bm, settings)
    return [element.index for element in elements], message


def _vertex_indices_with_valence(obj, valence: int):
    bm = bmesh.from_edit_mesh(obj.data)
    ensure_lookup_tables(bm, VERTEX)
    return [vert.index for vert in bm.verts if len(vert.link_edges) == valence]


def _create_assigned_layer(obj, element_type: str, element_indices):
    settings = obj.mesh_annotations
    meta = element_spec(element_type)
    previous_next_id = getattr(settings, meta.next_id)
    previous_active_index = get_active_index(settings, element_type)
    layer = create_layer(settings, element_type)
    assigned = False
    try:
        assigned = assign_elements_to_layer(
            obj, element_type, layer.layer_id, element_indices=element_indices
        )
        return layer if assigned else None
    finally:
        if not assigned:
            collection = get_layer_collection(settings, element_type)
            collection.remove(len(collection) - 1)
            setattr(settings, meta.next_id, previous_next_id)
            set_active_index(settings, element_type, previous_active_index)


class MESH_OT_annotation_make_single_user(
    LocalizedDescription, _MeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_make_single_user"
    bl_label = tr("Make Mesh Single User")
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Make the active object's mesh data single-user before editing annotations."
    )

    recovery_mode: bpy.props.EnumProperty(
        name=tr("Recovery"),
        items=(
            (
                "VERIFIED",
                tr("Verified Only"),
                tr(
                    "Keep assignments only when the stored mapping and current Mesh agree"
                ),
            ),
            (
                "OBJECT",
                tr("Keep Object Assignments"),
                tr("Explicitly trust the Object's current element indices"),
            ),
            (
                "DISCARD",
                tr("Discard Assignments"),
                tr(
                    "Keep layer definitions but clear every stale element assignment"
                ),
            ),
        ),
        default="VERIFIED",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(super().poll(context) and annotation_mesh_is_shared(obj))

    def invoke(self, context, _event):
        if shared_annotation_mappings_are_current(context.object):
            return self.execute(context)
        self.recovery_mode = "DISCARD"
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, _context):
        layout = self.layout
        layout.label(
            text=tr("Shared topology changed or cannot be verified"),
            icon="ERROR",
        )
        layout.label(
            text=tr("Choose how to resolve the Object-local assignments."),
        )
        layout.prop(self, "recovery_mode", expand=True)

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        mappings = {}
        try:
            mapping_statuses = (
                {element_type: True for element_type in ELEMENT_TYPES}
                if self.recovery_mode == "OBJECT"
                else shared_annotation_mapping_statuses(obj)
            )
            for element_type in ELEMENT_TYPES:
                source = (
                    {}
                    if (
                        self.recovery_mode == "DISCARD"
                        and not mapping_statuses[element_type]
                    )
                    else load_element_layers(settings, element_type)
                )
                mappings[element_type], _data_str = prepare_element_layers(source)
        except StackCapacityError:
            self.report(
                {"ERROR"},
                tr("Too many overlapping layers on one mesh element"),
            )
            return {"CANCELLED"}
        except StackEncodingError:
            self.report(
                {"ERROR"},
                tr("Annotation storage is invalid; no changes were made"),
            )
            return {"CANCELLED"}

        if (
            self.recovery_mode == "VERIFIED"
            and not all(mapping_statuses.values())
        ):
            self.report(
                {"ERROR"},
                tr(
                    "Shared topology changed; choose a recovery mode before detaching"
                ),
            )
            return {"CANCELLED"}

        was_edit_mode = context.mode == "EDIT_MESH"
        original_mesh = obj.data
        detached_mesh = None
        previous_properties = {}
        for element_type in ELEMENT_TYPES:
            meta = element_spec(element_type)
            previous_properties[meta.data_property] = getattr(
                settings, meta.data_property
            )
            previous_properties[meta.state_property] = getattr(
                settings, meta.state_property
            )
        try:
            if was_edit_mode:
                bpy.ops.object.mode_set(mode="OBJECT")
            if annotation_mesh_is_shared(obj):
                detached_mesh = original_mesh.copy()
                obj.data = detached_mesh
            prepared, data_strings, state_tokens = rebuild_annotation_stacks(
                obj, mappings
            )
            for element_type in ELEMENT_TYPES:
                commit_prepared_element_layers(
                    settings,
                    element_type,
                    prepared[element_type],
                    data_strings[element_type],
                )
                setattr(
                    settings,
                    element_spec(element_type).state_property,
                    state_tokens[element_type],
                )
        except Exception as exc:
            for property_name, value in previous_properties.items():
                setattr(settings, property_name, value)
            invalidate_element_layers_cache(settings)
            if detached_mesh is not None:
                obj.data = original_mesh
                bpy.data.meshes.remove(detached_mesh)
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            if was_edit_mode and obj.mode != "EDIT":
                try:
                    bpy.ops.object.mode_set(mode="EDIT")
                except RuntimeError:
                    self.report(
                        {"WARNING"},
                        tr("Mesh was detached, but Edit Mode could not be restored"),
                    )
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_toggle_overlay(
    LocalizedDescription, _MeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_toggle_overlay"
    bl_label = "Toggle Annotation Overlay"
    bl_options = {"INTERNAL"}
    tooltip_key = "Show or hide annotation overlays in the viewport."

    def execute(self, context):
        settings = context.object.mesh_annotations
        settings.enable_overlay = not settings.enable_overlay
        return {"FINISHED"}


class MESH_OT_annotation_toggle_solo(
    LocalizedDescription, _MeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_toggle_solo"
    bl_label = "Toggle Solo Annotation Layer"
    bl_options = {"INTERNAL"}
    tooltip_key = "Show only the active annotation layer for each element type."

    def execute(self, context):
        settings = context.object.mesh_annotations
        settings.solo_active = not settings.solo_active
        return {"FINISHED"}


class MESH_OT_annotation_toggle_layer_visibility(
    LocalizedDescription, _MeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_toggle_layer_visibility"
    bl_label = "Toggle Annotation Layer Visibility"
    bl_options = {"INTERNAL"}
    tooltip_key = "Show or hide this annotation layer."

    element_type: _element_type_property()
    layer_id: bpy.props.IntProperty()

    def execute(self, context):
        settings = context.object.mesh_annotations
        layer = get_layer_by_id(settings, self.element_type, self.layer_id)
        if layer is None:
            self.report({"WARNING"}, tr("Layer not found"))
            return {"CANCELLED"}
        layer.is_visible = not layer.is_visible
        return {"FINISHED"}


class MESH_OT_annotation_layer_add(
    LocalizedDescription, _MeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_layer_add"
    bl_label = tr('Add Annotation Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Create a new annotation layer for the current element type."

    element_type: _element_type_property()

    @annotation_write
    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        create_layer(settings, self.element_type)
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_layer_remove(
    LocalizedDescription, _MeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_layer_remove"
    bl_label = tr('Remove Annotation Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Delete the active annotation layer and remove its assignments."

    element_type: _element_type_property()

    @annotation_write
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


class MESH_OT_annotation_layer_move(
    LocalizedDescription, _MeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_layer_move"
    bl_label = tr('Reorder Annotation Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Move the active layer up or down in the overlay order."

    element_type: _element_type_property()
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
        if not super().poll(context):
            return False
        settings = getattr(obj, "mesh_annotations", None)
        if not settings:
            return False
        for etype in ELEMENT_TYPES:
            if len(get_layer_collection(settings, etype)) > 1:
                return True
        return False

    @annotation_write
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
        try:
            apply_layer_order_to_mapping(obj, self.element_type)
        except Exception:
            collection.move(new_idx, idx)
            set_active_index(settings, self.element_type, idx)
            raise
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_active(
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_assign_active"
    bl_label = tr('Assign Selection to Active Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Add the selected elements to the active annotation layer."

    element_type: _element_type_property()

    @annotation_write
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


class MESH_OT_annotation_select_layer(
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_select_layer"
    bl_label = tr('Select Elements in Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Select every mesh element assigned to this layer."

    element_type: _element_type_property()
    layer_id: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.object
        try:
            count = select_elements_for_layer(
                obj, self.element_type, self.layer_id
            )
        except StaleSharedAnnotationError:
            self.report(
                {"ERROR"},
                tr("Shared topology changed; detach or resolve stale assignments"),
            )
            return {"CANCELLED"}
        except StackEncodingError:
            self.report(
                {"ERROR"},
                tr("Annotation storage is invalid; no changes were made"),
            )
            return {"CANCELLED"}
        if count == 0:
            self.report({"INFO"}, tr('Layer is empty'))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_activate_from_selection(
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_activate_from_selection"
    bl_label = tr('Pick Active Layer From Selection')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Make the layer used most by the current selection active."

    element_type: _element_type_property()

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        try:
            usage = collect_layer_usage_from_selection(obj, self.element_type)
        except StaleSharedAnnotationError:
            self.report(
                {"ERROR"},
                tr("Shared topology changed; detach or resolve stale assignments"),
            )
            return {"CANCELLED"}
        except StackEncodingError:
            self.report(
                {"ERROR"},
                tr("Annotation storage is invalid; no changes were made"),
            )
            return {"CANCELLED"}
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


class MESH_OT_annotation_assign_loop(
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_assign_loop"
    bl_label = tr('Assign Loop to Active Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Derive a complete loop or path from the selection and add it to the active layer."
    )

    element_type: _element_type_property()

    @annotation_write
    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = active_layer(settings, self.element_type)
        if layer is None:
            self.report({"WARNING"}, tr('No active layer selected'))
            return {"CANCELLED"}
        indices, message = _collect_loop_indices(
            context, obj, self.element_type
        )
        if message:
            self.report({"INFO"}, message)
            return {"CANCELLED"}
        if not assign_elements_to_layer(
            obj, self.element_type, layer.layer_id, element_indices=indices
        ):
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_valence(
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_assign_valence"
    bl_label = tr('Annotate Vertices by Valence')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Add every vertex with the chosen valence to the active vertex layer."
    )

    valence: _valence_property()

    @annotation_write
    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = active_layer(settings, VERTEX)
        if layer is None:
            self.report({"WARNING"}, tr('No active vertex layer selected'))
            return {"CANCELLED"}
        target_indices = _vertex_indices_with_valence(obj, self.valence)
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
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_assign_valence_new_layer"
    bl_label = tr('Annotate Valence to New Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Create a vertex layer and add every vertex with the chosen valence."
    )

    valence: _valence_property()

    @annotation_write
    def execute(self, context):
        obj = context.object
        target_indices = _vertex_indices_with_valence(obj, self.valence)
        if not target_indices:
            self.report({"INFO"}, tr('No vertices found with that valence'))
            return {"CANCELLED"}
        if _create_assigned_layer(obj, VERTEX, target_indices) is None:
            self.report({"WARNING"}, tr('Nothing assigned; new layer cancelled'))
            return {"CANCELLED"}
        self.report({"INFO"}, tr("Annotated {count} vertices", count=len(target_indices)))
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_new_layer(
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_assign_new_layer"
    bl_label = tr('Assign Selection to New Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Create a new layer and add the selection or derived loop to it."
    )

    element_type: _element_type_property()
    use_loop: bpy.props.BoolProperty(default=False)

    @annotation_write
    def execute(self, context):
        obj = context.object
        indices = None
        if self.use_loop:
            indices, message = _collect_loop_indices(
                context, obj, self.element_type
            )
            if message:
                self.report({"INFO"}, message)
                return {"CANCELLED"}
        if _create_assigned_layer(obj, self.element_type, indices) is None:
            self.report({"WARNING"}, tr('Nothing assigned; new layer cancelled'))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_layer(
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_assign_layer"
    bl_label = tr('Assign Selection to Layer')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Add the selection or derived loop to this existing layer."

    element_type: _element_type_property()
    layer_id: bpy.props.IntProperty()
    use_loop: bpy.props.BoolProperty(default=False)
    make_active: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    @annotation_write
    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = get_layer_by_id(settings, self.element_type, self.layer_id)
        if layer is None:
            self.report({"WARNING"}, tr('Layer not found'))
            return {"CANCELLED"}
        indices = None
        if self.use_loop:
            indices, message = _collect_loop_indices(
                context, obj, self.element_type
            )
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
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_mark_seam_active_face_layer"
    bl_label = tr('Mark Active Layer Seams')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Mark the boundary edges of the active face layer as UV seams."

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not super().poll(context):
            return False
        settings = getattr(obj, "mesh_annotations", None)
        if not settings:
            return False
        layer = active_layer(settings, FACE)
        return layer is not None

    @annotation_write
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


class MESH_OT_annotation_mark_seam_all(
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_mark_seam_all_face_layers"
    bl_label = tr('Mark All Layer Seams')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = "Mark the boundary edges of every face layer as UV seams."

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not super().poll(context):
            return False
        settings = getattr(obj, "mesh_annotations", None)
        if not settings:
            return False
        return len(settings.face_layers) > 0

    @annotation_write
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


class MESH_OT_annotation_clear_selected(
    LocalizedDescription, _EditMeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_clear_selected"
    bl_label = tr('Clear Annotation From Selected')
    bl_options = {"REGISTER", "UNDO"}
    tooltip_key = (
        "Remove the active, topmost, or all annotation assignments from selected elements."
    )

    element_type: _element_type_property()
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

    @annotation_write
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
    LocalizedDescription, _MeshPoll, bpy.types.Operator
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
    LocalizedDescription, _MeshPoll, bpy.types.Operator
):
    bl_idname = "mesh.annotation_enter_edit_mode"
    bl_label = tr('Edit Annotations')
    tooltip_key = "Switch to Edit Mode to change annotation assignments"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.mode != "EDIT_MESH"

    def execute(self, context):
        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


CLASSES = (
    MESH_OT_annotation_make_single_user,
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
