# Quick reference

简体中文综合用户指南：[README.zh-CN.md](README.zh-CN.md)

## Open the workspace

1. Select a Mesh object.
2. Press **N** in the 3D View.
3. Open **Mesh Annotation**.
4. Enter Edit Mode to modify assignments.

The Faces, Edges, and Vertices tabs also switch Blender's mesh selection mode
while editing.

## Layer controls

| Control | Result |
| --- | --- |
| + | Create a layer |
| − | Delete the active layer and its assignments |
| ▲ / ▼ | Change overlay order |
| Eye | Toggle visibility |
| Color swatch | Change layer color |
| Name | Rename layer |
| Overlay | Show or hide all annotation drawing |
| Solo | Draw only each type's active layer |

## Assignment

| Action | Result |
| --- | --- |
| Add Selected | Add the current selection to the active layer |
| Add Loop | Derive a loop/path and add it to the active layer |
| Selected → New Layer | Create a layer and assign the selection atomically |
| Loop → New Layer | Create a layer and assign the derived loop atomically |
| Select Layer | Select every element in the active layer |
| Pick Layer | Activate the layer most used by the current selection |
| Remove Selected From Active Layer | Preserve every non-active assignment |

Vertex mode also provides valence-based assignment. Face mode provides active
and all-layer UV seam boundary actions.

## Edit Mode context menu

Right-click and open **Mesh Annotation**. The menu follows the current selection
type and directly exposes:

- add selected/loop to the active layer;
- create a new layer from selected/loop;
- choose another existing target layer;
- remove the active, top, or all assignments from selected elements.

Only choosing another existing target opens a second submenu.

## Shared Mesh

A locked warning means more than one Object uses the active Mesh. Annotation
writes are blocked. Overlay, Select Layer, and Pick Layer consume assignments
only after the Object mapping agrees with the current Mesh state. If native
topology editing invalidated that agreement, those assignments are
quarantined. **Make Mesh Single User** then asks whether to trust current indices
explicitly or discard stale assignments; automatic recovery never guesses.

## Display

The collapsed **Display** panel contains:

- Opacity
- Show Through Mesh
- Face, edge, and vertex surface offsets
- Edge Thickness
- Edge Shortening
- Point Size
- Debug Output

## Shortcuts

The extension does not install keymap entries. Use Blender's keymap preferences
to bind operator search results if desired.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Nothing is drawn | Overlay toggle, eye icon, opacity, and layer ownership |
| Assignment is cancelled | Edit Mode, active layer, and non-empty selection |
| Loop is refused | Select a connected, unambiguous seed |
| Controls are locked | Make the Mesh single-user |
| Overlap error | Reduce the number of layers on that element |
| UI is stale after development edit | F3 > Reload Scripts |
