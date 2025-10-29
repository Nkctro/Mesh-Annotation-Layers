# Mesh Annotation Layers - Blender Addon
# 用于在编辑模式下为网格添加彩色标注层的插件

bl_info = {
    "name": "Mesh Annotation Layers",
    "author": "Mesh Annotation Layers Team",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "3D View > Sidebar > Annotation Layers",
    "description": "在编辑模式下为网格对象的面、边、顶点添加多个彩色叠加层",
    "category": "Mesh",
}

import bpy
from bpy.props import (
    StringProperty,
    FloatVectorProperty,
    BoolProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import (
    PropertyGroup,
    UIList,
    Panel,
    Operator,
)


# ============================================================================
# Data Structures
# ============================================================================

class AnnotationLayerElement(PropertyGroup):
    """Stores individual element (vertex/edge/face) in a layer"""
    index: IntProperty(
        name="Element Index",
        description="Index of the mesh element",
        default=-1
    )


class AnnotationLayer(PropertyGroup):
    """Annotation layer properties"""
    name: StringProperty(
        name="Layer Name",
        description="Name of the annotation layer",
        default="Layer"
    )
    
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        default=(1.0, 0.0, 0.0, 1.0),
        size=4,
        min=0.0,
        max=1.0,
        description="Color of the annotation layer overlay"
    )
    
    visible: BoolProperty(
        name="Visible",
        description="Show/hide this layer",
        default=True
    )
    
    element_type: StringProperty(
        name="Element Type",
        description="Type of elements stored (VERT, EDGE, FACE)",
        default="FACE"
    )
    
    # Store element indices as a collection
    vertices: CollectionProperty(type=AnnotationLayerElement)
    edges: CollectionProperty(type=AnnotationLayerElement)
    faces: CollectionProperty(type=AnnotationLayerElement)


class AnnotationLayerSettings(PropertyGroup):
    """Global settings for annotation layers"""
    layers: CollectionProperty(type=AnnotationLayer)
    active_layer_index: IntProperty(
        name="Active Layer",
        description="Index of the active annotation layer",
        default=0
    )
    
    overlay_opacity: FloatProperty(
        name="Overlay Opacity",
        description="Opacity of the overlay display",
        default=0.5,
        min=0.0,
        max=1.0
    )


# ============================================================================
# Operators
# ============================================================================

class MESH_OT_add_annotation_layer(Operator):
    """Add a new annotation layer"""
    bl_idname = "mesh.add_annotation_layer"
    bl_label = "Add Annotation Layer"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH'
    
    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotation_settings
        
        layer = settings.layers.add()
        layer.name = f"Layer {len(settings.layers)}"
        
        # Set random color for visual distinction
        import random
        layer.color = (
            random.random(),
            random.random(),
            random.random(),
            1.0
        )
        
        settings.active_layer_index = len(settings.layers) - 1
        
        self.report({'INFO'}, f"Added layer: {layer.name}")
        return {'FINISHED'}


class MESH_OT_remove_annotation_layer(Operator):
    """Remove the active annotation layer"""
    bl_idname = "mesh.remove_annotation_layer"
    bl_label = "Remove Annotation Layer"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.object or context.object.type != 'MESH':
            return False
        settings = context.object.mesh_annotation_settings
        return len(settings.layers) > 0
    
    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotation_settings
        
        if settings.active_layer_index < len(settings.layers):
            settings.layers.remove(settings.active_layer_index)
            settings.active_layer_index = max(0, settings.active_layer_index - 1)
            
        self.report({'INFO'}, "Removed annotation layer")
        return {'FINISHED'}


class MESH_OT_assign_to_layer(Operator):
    """Assign selected elements to the active annotation layer"""
    bl_idname = "mesh.assign_to_annotation_layer"
    bl_label = "Assign to Layer"
    bl_options = {'REGISTER', 'UNDO'}
    
    element_type: StringProperty(default="FACE")
    
    @classmethod
    def poll(cls, context):
        if not context.object or context.object.type != 'MESH':
            return False
        if context.mode != 'EDIT_MESH':
            return False
        settings = context.object.mesh_annotation_settings
        return len(settings.layers) > 0
    
    def execute(self, context):
        import bmesh
        
        obj = context.object
        settings = obj.mesh_annotation_settings
        
        if settings.active_layer_index >= len(settings.layers):
            self.report({'ERROR'}, "No active layer")
            return {'CANCELLED'}
        
        layer = settings.layers[settings.active_layer_index]
        
        # Get the mesh data
        bm = bmesh.from_edit_mesh(obj.data)
        
        # Clear existing elements for this type
        if self.element_type == "VERT":
            layer.vertices.clear()
            selected = [v.index for v in bm.verts if v.select]
            for idx in selected:
                elem = layer.vertices.add()
                elem.index = idx
        elif self.element_type == "EDGE":
            layer.edges.clear()
            selected = [e.index for e in bm.edges if e.select]
            for idx in selected:
                elem = layer.edges.add()
                elem.index = idx
        elif self.element_type == "FACE":
            layer.faces.clear()
            selected = [f.index for f in bm.faces if f.select]
            for idx in selected:
                elem = layer.faces.add()
                elem.index = idx
        
        layer.element_type = self.element_type
        
        count = len(selected)
        self.report({'INFO'}, f"Assigned {count} {self.element_type.lower()}(s) to {layer.name}")
        
        # Force viewport update
        context.area.tag_redraw()
        
        return {'FINISHED'}


class MESH_OT_remove_from_layer(Operator):
    """Remove selected elements from the active annotation layer"""
    bl_idname = "mesh.remove_from_annotation_layer"
    bl_label = "Remove from Layer"
    bl_options = {'REGISTER', 'UNDO'}
    
    element_type: StringProperty(default="FACE")
    
    @classmethod
    def poll(cls, context):
        if not context.object or context.object.type != 'MESH':
            return False
        if context.mode != 'EDIT_MESH':
            return False
        settings = context.object.mesh_annotation_settings
        return len(settings.layers) > 0
    
    def execute(self, context):
        import bmesh
        
        obj = context.object
        settings = obj.mesh_annotation_settings
        
        if settings.active_layer_index >= len(settings.layers):
            self.report({'ERROR'}, "No active layer")
            return {'CANCELLED'}
        
        layer = settings.layers[settings.active_layer_index]
        
        # Get the mesh data
        bm = bmesh.from_edit_mesh(obj.data)
        
        # Get selected indices
        if self.element_type == "VERT":
            selected_set = {v.index for v in bm.verts if v.select}
            # Remove from layer
            to_remove = [i for i, elem in enumerate(layer.vertices) if elem.index in selected_set]
            for i in reversed(to_remove):
                layer.vertices.remove(i)
        elif self.element_type == "EDGE":
            selected_set = {e.index for e in bm.edges if e.select}
            to_remove = [i for i, elem in enumerate(layer.edges) if elem.index in selected_set]
            for i in reversed(to_remove):
                layer.edges.remove(i)
        elif self.element_type == "FACE":
            selected_set = {f.index for f in bm.faces if f.select}
            to_remove = [i for i, elem in enumerate(layer.faces) if elem.index in selected_set]
            for i in reversed(to_remove):
                layer.faces.remove(i)
        
        self.report({'INFO'}, f"Removed elements from {layer.name}")
        
        # Force viewport update
        context.area.tag_redraw()
        
        return {'FINISHED'}


class MESH_OT_select_layer_elements(Operator):
    """Select all elements in the active annotation layer"""
    bl_idname = "mesh.select_annotation_layer_elements"
    bl_label = "Select Layer Elements"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.object or context.object.type != 'MESH':
            return False
        if context.mode != 'EDIT_MESH':
            return False
        settings = context.object.mesh_annotation_settings
        return len(settings.layers) > 0
    
    def execute(self, context):
        import bmesh
        
        obj = context.object
        settings = obj.mesh_annotation_settings
        
        if settings.active_layer_index >= len(settings.layers):
            self.report({'ERROR'}, "No active layer")
            return {'CANCELLED'}
        
        layer = settings.layers[settings.active_layer_index]
        
        # Get the mesh data
        bm = bmesh.from_edit_mesh(obj.data)
        
        # Ensure indices are valid
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        
        # Select elements based on layer type
        if layer.element_type == "VERT":
            for elem in layer.vertices:
                if elem.index < len(bm.verts):
                    bm.verts[elem.index].select = True
        elif layer.element_type == "EDGE":
            for elem in layer.edges:
                if elem.index < len(bm.edges):
                    bm.edges[elem.index].select = True
        elif layer.element_type == "FACE":
            for elem in layer.faces:
                if elem.index < len(bm.faces):
                    bm.faces[elem.index].select = True
        
        bmesh.update_edit_mesh(obj.data)
        
        self.report({'INFO'}, f"Selected elements from {layer.name}")
        return {'FINISHED'}


class MESH_OT_clear_layer(Operator):
    """Clear all elements from the active annotation layer"""
    bl_idname = "mesh.clear_annotation_layer"
    bl_label = "Clear Layer"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if not context.object or context.object.type != 'MESH':
            return False
        settings = context.object.mesh_annotation_settings
        return len(settings.layers) > 0
    
    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotation_settings
        
        if settings.active_layer_index >= len(settings.layers):
            self.report({'ERROR'}, "No active layer")
            return {'CANCELLED'}
        
        layer = settings.layers[settings.active_layer_index]
        layer.vertices.clear()
        layer.edges.clear()
        layer.faces.clear()
        
        self.report({'INFO'}, f"Cleared {layer.name}")
        context.area.tag_redraw()
        
        return {'FINISHED'}


# ============================================================================
# UI Lists
# ============================================================================

class MESH_UL_annotation_layers(UIList):
    """UI List for annotation layers"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layer = item
        
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(layer, "name", text="", emboss=False, icon='OUTLINER_DATA_MESH')
            row.prop(layer, "color", text="")
            row.prop(layer, "visible", text="", icon='HIDE_OFF' if layer.visible else 'HIDE_ON', emboss=False)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.prop(layer, "color", text="")


# ============================================================================
# Panels
# ============================================================================

class MESH_PT_annotation_layers(Panel):
    """Main panel for annotation layers"""
    bl_label = "Annotation Layers"
    bl_idname = "MESH_PT_annotation_layers"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Annotation'
    bl_context = "mesh_edit"
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH'
    
    def draw(self, context):
        layout = self.layout
        obj = context.object
        settings = obj.mesh_annotation_settings
        
        # Layer list
        row = layout.row()
        row.template_list(
            "MESH_UL_annotation_layers",
            "",
            settings,
            "layers",
            settings,
            "active_layer_index",
            rows=3
        )
        
        # Add/Remove buttons
        col = row.column(align=True)
        col.operator("mesh.add_annotation_layer", icon='ADD', text="")
        col.operator("mesh.remove_annotation_layer", icon='REMOVE', text="")
        
        # Layer operations
        if len(settings.layers) > 0 and settings.active_layer_index < len(settings.layers):
            layer = settings.layers[settings.active_layer_index]
            
            box = layout.box()
            box.label(text=f"Active: {layer.name}")
            
            # Element type info
            col = box.column()
            
            # Count elements
            vert_count = len(layer.vertices)
            edge_count = len(layer.edges)
            face_count = len(layer.faces)
            
            if layer.element_type == "VERT":
                col.label(text=f"Vertices: {vert_count}")
            elif layer.element_type == "EDGE":
                col.label(text=f"Edges: {edge_count}")
            elif layer.element_type == "FACE":
                col.label(text=f"Faces: {face_count}")
            
            # Assignment buttons
            layout.label(text="Assign Selected:")
            row = layout.row(align=True)
            op = row.operator("mesh.assign_to_annotation_layer", text="Vertices")
            op.element_type = "VERT"
            op = row.operator("mesh.assign_to_annotation_layer", text="Edges")
            op.element_type = "EDGE"
            op = row.operator("mesh.assign_to_annotation_layer", text="Faces")
            op.element_type = "FACE"
            
            # Remove buttons
            layout.label(text="Remove Selected:")
            row = layout.row(align=True)
            op = row.operator("mesh.remove_from_annotation_layer", text="Vertices")
            op.element_type = "VERT"
            op = row.operator("mesh.remove_from_annotation_layer", text="Edges")
            op.element_type = "EDGE"
            op = row.operator("mesh.remove_from_annotation_layer", text="Faces")
            op.element_type = "FACE"
            
            # Selection and clear
            layout.separator()
            layout.operator("mesh.select_annotation_layer_elements", text="Select Layer Elements")
            layout.operator("mesh.clear_annotation_layer", text="Clear Layer")
        
        # Global settings
        layout.separator()
        layout.prop(settings, "overlay_opacity", text="Opacity")


# ============================================================================
# Drawing Handler
# ============================================================================

draw_handler = None

def draw_callback_3d(context):
    """Draw the annotation layer overlays in 3D view"""
    import gpu
    import bgl
    from gpu_extras.batch import batch_for_shader
    
    obj = context.object
    if not obj or obj.type != 'MESH':
        return
    
    if context.mode != 'EDIT_MESH':
        return
    
    settings = obj.mesh_annotation_settings
    
    # Enable blending for transparency
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    
    import bmesh
    
    # Get edit mesh
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    
    # Get transformation matrix
    matrix = obj.matrix_world
    
    # Draw each visible layer
    for layer in settings.layers:
        if not layer.visible:
            continue
        
        color = (layer.color[0], layer.color[1], layer.color[2], layer.color[3] * settings.overlay_opacity)
        
        # Draw faces
        if layer.element_type == "FACE" and len(layer.faces) > 0:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            
            vertices = []
            for elem in layer.faces:
                if elem.index < len(bm.faces):
                    face = bm.faces[elem.index]
                    # Triangulate face for drawing
                    verts = [matrix @ v.co for v in face.verts]
                    # Simple fan triangulation
                    for i in range(1, len(verts) - 1):
                        vertices.extend([verts[0], verts[i], verts[i + 1]])
            
            if vertices:
                batch = batch_for_shader(shader, 'TRIS', {"pos": vertices})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)
        
        # Draw edges
        elif layer.element_type == "EDGE" and len(layer.edges) > 0:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            
            vertices = []
            for elem in layer.edges:
                if elem.index < len(bm.edges):
                    edge = bm.edges[elem.index]
                    v1 = matrix @ edge.verts[0].co
                    v2 = matrix @ edge.verts[1].co
                    vertices.extend([v1, v2])
            
            if vertices:
                bgl.glLineWidth(3.0)
                batch = batch_for_shader(shader, 'LINES', {"pos": vertices})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)
                bgl.glLineWidth(1.0)
        
        # Draw vertices
        elif layer.element_type == "VERT" and len(layer.vertices) > 0:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            
            vertices = []
            for elem in layer.vertices:
                if elem.index < len(bm.verts):
                    vert = bm.verts[elem.index]
                    vertices.append(matrix @ vert.co)
            
            if vertices:
                bgl.glPointSize(8.0)
                batch = batch_for_shader(shader, 'POINTS', {"pos": vertices})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)
                bgl.glPointSize(1.0)
    
    # Restore OpenGL state
    bgl.glDisable(bgl.GL_BLEND)


def register_draw_handler():
    """Register the draw handler"""
    global draw_handler
    if draw_handler is None:
        draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_3d,
            (bpy.context,),
            'WINDOW',
            'POST_VIEW'
        )


def unregister_draw_handler():
    """Unregister the draw handler"""
    global draw_handler
    if draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
        draw_handler = None


# ============================================================================
# Registration
# ============================================================================

classes = (
    AnnotationLayerElement,
    AnnotationLayer,
    AnnotationLayerSettings,
    MESH_OT_add_annotation_layer,
    MESH_OT_remove_annotation_layer,
    MESH_OT_assign_to_layer,
    MESH_OT_remove_from_layer,
    MESH_OT_select_layer_elements,
    MESH_OT_clear_layer,
    MESH_UL_annotation_layers,
    MESH_PT_annotation_layers,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Object.mesh_annotation_settings = PointerProperty(type=AnnotationLayerSettings)
    
    register_draw_handler()


def unregister():
    unregister_draw_handler()
    
    del bpy.types.Object.mesh_annotation_settings
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
