# Mesh Annotation Layers

[English](#english) | [简体中文](README.zh-CN.md)

## English

Mesh Annotation Layers is a Blender Extension for keeping colored face, edge,
and vertex notes directly with a .blend file. Assignments are edited in Edit
Mode and remain visible in Object, Sculpt, Weight Paint, Vertex Paint, and
Texture Paint modes.

### Requirements

- Blender 4.2 or newer
- No network, file-system, clipboard, camera, or microphone permission
- No third-party Python dependency

### Main workflow

1. Select a mesh and open the **Mesh Annotation** tab in the 3D View sidebar.
2. Enter Edit Mode and choose the Faces, Edges, or Vertices workspace.
3. Create a layer with **+**, select mesh elements, then use **Add Selected**.
4. Use **Add Loop** when a selected face/edge/vertex path can define a loop.
5. Use **Selected → New Layer** or **Loop → New Layer** for a one-click
   create-and-assign operation.
6. Right-click in Edit Mode and open **Mesh Annotation** for the same common
   assignment and removal actions without navigating the sidebar.

Elements may belong to several layers. The visually highest visible layer wins.
**Remove Selected From Active Layer** preserves lower assignments; the context
menu also exposes explicit top-only and remove-all actions.

### Useful tools

- **Select Layer** selects every element assigned to the active layer.
- **Pick Layer** activates the layer used most by the current selection.
- Face layers can mark their outer boundaries as UV seams.
- The Display subpanel controls opacity, through-mesh drawing, surface offsets,
  edge thickness/shortening, and point size.
- Automatic, English, and Chinese interface modes live in the add-on
  preferences.

### Shared mesh data

Layer settings and durable JSON assignments belong to each Object, while the
topology-following edit stack is stored on its Mesh. To prevent two linked
objects from overwriting one another, annotation editing is read-only whenever
the Mesh has multiple users.

Use **Make Mesh Single User** in the panel or context menu. The extension copies
the Mesh only after the Object mapping agrees with the current topology and
custom-data stack. If Blender topology edits made that agreement impossible,
the recovery dialog requires an explicit choice to trust current indices or to
discard stale assignments. Unverified assignments are not drawn or selected.

### Install

1. Download the release ZIP built from the current extension manifest.
2. In Blender, open **Edit > Preferences > Get Extensions**.
3. Open the repository menu, choose **Install from Disk...**, and select the ZIP.
4. Enable **Mesh Annotation Layers** if Blender does not enable it automatically.

Do not unzip or rename files inside the release archive. Development setup and
official build commands are documented in [INSTALL.md](INSTALL.md).

### Storage and performance

- Validated per-object JSON is the durable source of truth.
- BMesh custom layers mirror assignments so topology and Undo/Redo can carry
  ownership with mesh elements.
- The overlap stack uses a versioned, checksummed binary representation and
  refuses a write before Blender's 255-byte string limit could truncate it.
- Full-map preflight prevents validation failures from mutating state, and commit
  rollback restores JSON, BMesh payloads, caches, and collection cursors. A Mesh
  state that cannot be confirmed as restored is quarantined rather than replayed.
- Decoded mappings, evaluated geometry, and GPU batches use bounded caches.
- Normal writes hash only annotated elements. Trusting shared data additionally
  performs a read-only full-stack check so copied, missing, or damaged payloads
  cannot masquerade as a valid sparse mapping.
- Dependency updates are scoped, interactive rebuilds are debounced, and
  style-only changes avoid geometry remapping.

### License

GPL-3.0-or-later. The complete license is included in [LICENSE](LICENSE) and in
the installable extension archive.

---

## 中文

完整的中文安装、操作、共享 Mesh 恢复、性能说明、故障排查和开发指南见
[README.zh-CN.md](README.zh-CN.md)。此处保留该入口以兼容已有的 `#中文` 链接。
