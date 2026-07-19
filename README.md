# Mesh Annotation Layers

[简体中文](README.zh-CN.md)

Colored face, edge, and vertex annotation layers for Blender topology work.
Assignments are edited in Edit Mode, saved with the mesh, and drawn as viewport
overlays without using materials or vertex colors.

## Highlights

- Separate layer stacks for faces, edges, and vertices.
- Assign selections, detected loops/paths, or vertex valence results.
- Select a layer, activate a layer from the current selection, and clear assignments.
- Convert face-layer boundaries to UV seams.
- Control color, visibility, solo mode, opacity, offsets, edge trim, and point size.
- Keep annotations visible in supported object, sculpt, and paint workflows.
- English and Simplified Chinese interface modes.

## Requirements

- Blender 4.2 or newer.
- No third-party Python dependencies.

## Install

Download a release ZIP, then use Blender's **Preferences → Get Extensions →
Install from Disk** command. See the [installation guide](docs/en/installation.md)
for verification, source builds, and troubleshooting.

## Quick start

1. Select a mesh and open the 3D View sidebar with `N`.
2. Open the **Mesh Annotation** tab.
3. Enter Edit Mode and choose face, edge, or vertex mode.
4. Create a layer, select mesh elements, and choose **Assign Selected**.
5. Adjust visibility and display settings without leaving the panel.

## Documentation

| Topic | English | 简体中文 |
| --- | --- | --- |
| Installation | [Installation](docs/en/installation.md) | [安装](docs/zh-CN/installation.md) |
| Workflows | [User guide](docs/en/user-guide.md) | [用户指南](docs/zh-CN/user-guide.md) |
| Questions | [FAQ](docs/en/faq.md) | [常见问题](docs/zh-CN/faq.md) |
| Architecture and contribution | [Development](docs/en/development.md) | [开发说明](docs/zh-CN/development.md) |

## Repository layout

```text
mesh_annotation_layers/  Blender add-on runtime
docs/en/                 English documentation
docs/zh-CN/              简体中文文档
tests/                   Source and Blender smoke tests
tools/build.py           Release and development archive builder
blender_manifest.toml    Blender extension metadata
```

Build an installable archive with:

```bash
python tools/build.py
```

Use `python tools/build.py --dev` for a locally distinguishable beta build.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
