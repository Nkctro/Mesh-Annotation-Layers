# Installation and development

简体中文综合用户指南：[README.zh-CN.md](README.zh-CN.md)

## Install a release

Mesh Annotation Layers requires Blender 4.2 or newer.

1. Open **Edit > Preferences > Get Extensions**.
2. Open the repository menu and choose **Install from Disk...**.
3. Select the official extension ZIP.
4. Enable **Mesh Annotation Layers** if needed.
5. Select a mesh and open the **Mesh Annotation** sidebar tab.

The archive must contain blender_manifest.toml and __init__.py at the extension
root. A GitHub source archive is not necessarily an installable extension
archive; use a release artifact built by Blender.

## Development setup

Follow Blender's
[Add-on Development Setup](https://developer.blender.org/docs/handbook/extensions/addon_dev_setup/)
workflow. Keep source control outside Blender-managed extension directories and
use a dedicated local extension repository.

1. Clone this project to a normal development directory.
2. In Blender's Extensions preferences, add a local repository whose directory
   is outside Blender's managed user_default repository.
3. Link this project's mesh_annotation_layers directory into that local
   repository under the same directory name.
4. Enable the extension from **Preferences > Add-ons**.
5. After editing Python, use **F3 > Reload Scripts**.

Windows PowerShell example (Developer Mode or elevated privileges may be
required):

    New-Item -ItemType SymbolicLink -Path D:\BlenderExtensionDev\mesh_annotation_layers -Target E:\GIT\Mesh-Annotation-Layers\mesh_annotation_layers

macOS/Linux example:

    ln -s /path/to/Mesh-Annotation-Layers/mesh_annotation_layers /path/to/BlenderExtensionDev/mesh_annotation_layers

Remove the development link manually when finished. Do not use Blender's
extension uninstall action as a substitute for unlinking a source checkout.

The entry point detects a real module reload, unregisters a still-active old
runtime before reloading submodules, and restores registration only for a
manual Python reload. Blender's normal Reload Scripts flow already unregisters
the extension first and therefore does not double-register it.

## Validate and build

The mesh_annotation_layers directory is the complete extension source. From the
repository root:

    blender --command extension validate mesh_annotation_layers

    blender --command extension build --source-dir mesh_annotation_layers --output-dir dist

Validate the generated archive as well:

    blender --command extension validate dist/mesh_annotation_layers-<version>.zip

By default Blender names the archive from the manifest fields:
`<id>-<version>.zip`. Replace `<version>` above with the manifest version. The
project does not maintain a second packaging implementation; the official
Blender command is the release authority.

## Automated checks

Source contracts:

    python -m unittest discover -s tests -p "test_*.py" -v

Blender runtime smoke test:

    blender --background --factory-startup --python tests/blender_smoke.py

The runtime suite covers registration and teardown, assignments, multiple
ownership, evaluated overlays, cache invalidation, shared-Mesh isolation,
capacity handling, history restoration, and reload behavior.

## Clean-install release check

1. Start Blender with factory settings or a disposable user configuration.
2. Install the newly built ZIP with **Install from Disk...**.
3. Enable it and verify the sidebar plus Edit Mode context menu.
4. Run face, edge, and vertex create/assign/select/remove workflows.
5. Save and reopen a .blend file.
6. Disable and re-enable the extension, then run **Reload Scripts**.
7. Confirm the system console contains no traceback.
