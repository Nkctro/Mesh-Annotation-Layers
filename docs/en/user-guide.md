# User guide

[简体中文](../zh-CN/user-guide.md) · [Project home](../../README.md)

## Mental model

Each mesh object owns three independent layer stacks: faces, edges, and vertices.
A mesh element can belong to more than one layer. The active element type controls
which stack and actions are visible in the panel.

Assignments are changed in Edit Mode. Layer colors and assignments are stored with
the object in the `.blend` file; materials and vertex colors are not used.

## Basic workflow

1. Select a mesh, open the sidebar (`N`), and choose **Mesh Annotation**.
2. Enter Edit Mode and choose face, edge, or vertex selection mode.
3. Add a layer with **+**, then name it and choose a color.
4. Select mesh elements and choose **Assign Selected**.
5. Use the eye control for one layer or **Solo Active** to isolate it.

## Assignment tools

- **Assign Selected** adds the current selection to the active layer.
- **Assign Loop** derives a complete face loop, edge loop, or vertex path from the
  selection before assigning it.
- **Selected/Loop → New Layer** creates and assigns in one operation.
- **Assign to Existing Layer** avoids changing the active layer first.
- **Valence** in vertex mode finds vertices with the chosen number of connected edges.

If a derived loop is ambiguous, refine the selection and retry. The operation does
not silently assign an arbitrary path.

## Selection and cleanup

- **Select Layer Elements** selects everything assigned to a layer.
- **Pick From Selection** activates the layer most represented by the current selection.
- **Remove Selected** removes the selected elements from a chosen layer.
- **Clear Selected** can remove either the top assignment or all assignments from the
  selected elements.
- Deleting a layer also removes its assignments.

## UV seam workflow

In face mode, use **Mark Active Layer Seams** to mark the boundary of the active face
layer as UV seams. **Mark All Layer Seams** applies the same operation to every face
layer. Existing mesh geometry is not changed.

## Display controls

- **Show Overlay** is the global display switch.
- Per-layer eye controls and **Solo Active** limit what is drawn.
- **Opacity**, **line width**, and **point size** control visual weight.
- Separate face, edge, and vertex offsets reduce z-fighting.
- **Edge trim** shortens colored edge guides near their ends.
- **Show Through Mesh** changes depth testing so back-side annotations remain visible.

Use the smallest offsets that avoid z-fighting. Large offsets can make guides appear
detached from the surface.

## Practical layer schemes

- **Topology review:** poles, pinching, dense areas, and cleanup targets.
- **Retopology:** completed regions, uncertain flow, deformation-critical loops.
- **UV planning:** islands as face layers, then convert their boundaries to seams.
- **Team notes:** use stable names such as `review`, `approved`, and `rework`.

## Language

The add-on preference supports **Automatic**, **English**, and **Chinese**. Automatic
uses Chinese for supported Chinese Blender locales and English otherwise.

## Data and limitations

- Data is stored per object and saved with the `.blend` file.
- Assignments do not affect FBX/OBJ export unless another tool explicitly reads the
  add-on's custom data.
- Editing one object does not edit another object's layers.
- There are no default keyboard shortcuts; Blender keymaps can bind operator IDs.
- Very dense evaluated meshes cost more to draw. Hide unused layers and avoid excessive
  through-mesh overlays when interaction becomes slow.
