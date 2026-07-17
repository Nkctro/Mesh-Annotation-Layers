"""Blender property groups owned by the add-on."""

import bpy

from .constants import EDGE, FACE, VERTEX
from .overlay import tag_surface_offset_redraw, tag_view3d_redraw


def _tag_owner_batch_redraw(self, context):
    tag_view3d_redraw(
        context,
        invalidate_geometry=False,
        cache_owner=self.id_data,
    )


def _tag_owner_surface_offset_redraw(self, context):
    tag_surface_offset_redraw(context, cache_owner=self.id_data)


class MeshAnnotationLayer(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="Layer")
    color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype="COLOR_GAMMA",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.8, 0.3, 0.3, 1.0),
        update=lambda self, context: tag_view3d_redraw(context, invalidate_cache=False),
    )
    layer_id: bpy.props.IntProperty()
    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (FACE, "Face", "Face layer"),
            (EDGE, "Edge", "Edge layer"),
            (VERTEX, "Vertex", "Vertex layer"),
        ),
        default=FACE,
        options={'HIDDEN'},
    )
    is_visible: bpy.props.BoolProperty(
        name="Visible",
        default=True,
        update=_tag_owner_batch_redraw,
    )


class MeshAnnotationSettings(bpy.types.PropertyGroup):
    enable_overlay: bpy.props.BoolProperty(
        name="Show Overlay",
        default=True,
        update=lambda self, context: tag_view3d_redraw(context, invalidate_cache=False),
    )
    solo_active: bpy.props.BoolProperty(
        name="Solo Active Layer",
        default=False,
        update=_tag_owner_batch_redraw,
    )
    debug_output: bpy.props.BoolProperty(name="Debug Output", default=False)
    ui_element_type: bpy.props.EnumProperty(
        name="Annotation Type",
        items=(
            (FACE, "Faces", "Manage face annotation layers", "FACESEL", 0),
            (EDGE, "Edges", "Manage edge annotation layers", "EDGESEL", 1),
            (VERTEX, "Vertices", "Manage vertex annotation layers", "VERTEXSEL", 2),
        ),
        default=FACE,
    )
    auto_valence_n: bpy.props.IntProperty(
        name="Valence",
        description="Annotate vertices with this edge count",
        min=0,
        max=128,
        default=4,
    )
    overlay_line_width: bpy.props.FloatProperty(
        name="Edge Thickness",
        min=1.0,
        max=10.0,
        default=7.0,
        update=lambda self, context: tag_view3d_redraw(context, invalidate_cache=False),
    )
    overlay_point_size: bpy.props.FloatProperty(
        name="Vertex Size",
        min=1.0,
        max=20.0,
        default=10.0,
        update=lambda self, context: tag_view3d_redraw(context, invalidate_cache=False),
    )
    overlay_edge_trim: bpy.props.FloatProperty(
        name="Edge Shortening",
        description=(
            "Trim the two ends of the complete source edge while keeping "
            "subdivision segments connected"
        ),
        min=-0.45,
        max=0.0,
        default=0.0,
        step=0.01,
        precision=3,
        update=_tag_owner_batch_redraw,
    )
    overlay_face_offset: bpy.props.FloatProperty(
        name="Face Offset",
        description="Offset face overlays along the surface normal to avoid z-fighting",
        min=0.0,
        max=0.01,
        default=0.0001,
        step=0.0001,
        precision=4,
        update=_tag_owner_surface_offset_redraw,
    )
    overlay_edge_offset: bpy.props.FloatProperty(
        name="Edge Offset",
        description="Offset edge overlays along the evaluated surface normal",
        min=0.0,
        max=0.01,
        default=0.0001,
        step=0.0001,
        precision=4,
        update=_tag_owner_batch_redraw,
    )
    overlay_vertex_offset: bpy.props.FloatProperty(
        name="Vertex Offset",
        description="Offset vertex markers along the evaluated surface normal",
        min=0.0,
        max=0.01,
        default=0.0001,
        step=0.0001,
        precision=4,
        update=_tag_owner_surface_offset_redraw,
    )

    overlay_alpha_multiplier: bpy.props.FloatProperty(
        name="Overlay Opacity",
        description="Global multiplier applied to each layer's own alpha value",
        min=0.0,
        max=1.0,
        default=0.5,
        update=lambda self, context: tag_view3d_redraw(context, invalidate_cache=False),
    )

    overlay_show_backfaces: bpy.props.BoolProperty(
        name="Show Through Mesh",
        default=False,
        update=lambda self, context: tag_view3d_redraw(context, invalidate_cache=False),
    )

    face_layers: bpy.props.CollectionProperty(type=MeshAnnotationLayer)
    edge_layers: bpy.props.CollectionProperty(type=MeshAnnotationLayer)
    vertex_layers: bpy.props.CollectionProperty(type=MeshAnnotationLayer)

    active_face_layer_index: bpy.props.IntProperty(
        default=-1,
        update=_tag_owner_batch_redraw,
    )
    active_edge_layer_index: bpy.props.IntProperty(
        default=-1,
        update=_tag_owner_batch_redraw,
    )
    active_vertex_layer_index: bpy.props.IntProperty(
        default=-1,
        update=_tag_owner_batch_redraw,
    )

    next_face_layer_id: bpy.props.IntProperty(default=1)
    next_edge_layer_id: bpy.props.IntProperty(default=1)
    next_vertex_layer_id: bpy.props.IntProperty(default=1)

    face_layers_data: bpy.props.StringProperty(default="{}")
    edge_layers_data: bpy.props.StringProperty(default="{}")
    vertex_layers_data: bpy.props.StringProperty(default="{}")

    # A token for the last agreeing JSON/BMesh/topology state. It prevents an
    # Object-local index mapping from being trusted after its Mesh is shared
    # and changed by Blender's native topology tools.
    face_annotation_state: bpy.props.StringProperty(default="", options={'HIDDEN'})
    edge_annotation_state: bpy.props.StringProperty(default="", options={'HIDDEN'})
    vertex_annotation_state: bpy.props.StringProperty(default="", options={'HIDDEN'})


CLASSES = (MeshAnnotationLayer, MeshAnnotationSettings)
