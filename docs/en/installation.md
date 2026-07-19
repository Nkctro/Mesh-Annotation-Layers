# Installation

[简体中文](../zh-CN/installation.md) · [Project home](../../README.md)

## Install a release

1. Download the release ZIP. Do not unpack it.
2. Open Blender 4.2 or newer.
3. Open **Edit → Preferences → Get Extensions**.
4. Open the menu in the upper-right corner and choose **Install from Disk**.
5. Select the ZIP and confirm the installation.
6. Search for **Mesh Annotation Layers** and enable it if necessary.

Blender's extension documentation also recommends testing packaged add-ons with
Install from Disk: <https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html>.

## Verify the installation

1. Select a mesh object.
2. Open the 3D View sidebar with `N`.
3. Open the **Mesh Annotation** tab.
4. Enter Edit Mode to create layers or change assignments.

Existing annotations remain available for display in supported non-edit modes.

## Build from source

Python 3.11 or newer is required because the builder reads TOML with the standard
library.

```bash
git clone https://github.com/Nkctro/Mesh-Annotation-Layers.git
cd Mesh-Annotation-Layers
python tools/build.py
```

The archive is written to `dist/`. A development build with a unique beta version
can be produced with:

```bash
python tools/build.py --dev
```

Install the generated ZIP with **Install from Disk**. Building does not modify the
committed manifest or add-on version after the command exits.

## Troubleshooting

- **No panel:** select a mesh, open the sidebar, and confirm the extension is enabled.
- **Cannot assign:** enter Edit Mode, select elements, and activate or create a layer.
- **Enable error:** confirm all files came from one release ZIP and use Blender 4.2+.
- **More detail:** open Blender's system console and include the traceback in a bug report.

## Uninstall

Open **Preferences → Get Extensions**, locate Mesh Annotation Layers, open its menu,
and choose **Uninstall**.
