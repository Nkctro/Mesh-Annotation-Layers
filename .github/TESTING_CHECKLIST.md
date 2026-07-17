# Release testing checklist

Record the exact Blender build, OS, GPU, commit, and generated archive hash.
The commands and development setup are maintained in
[CONTRIBUTING.md](../CONTRIBUTING.md); this file contains only the release gate.

## Automated gate

- [ ] Python compileall passes.
- [ ] Source-contract unit tests pass.
- [ ] Blender background smoke test passes.
- [ ] Blender validates the source directory.
- [ ] Blender builds and validates the generated ZIP.
- [ ] Building leaves the working tree and manifest unchanged.

## Manual product gate

- [ ] Install the generated ZIP into a clean Blender profile.
- [ ] Enable, disable, re-enable, and Reload Scripts without a traceback or
      duplicate callback.
- [ ] Create, assign, select, reorder, hide, and remove face, edge, and vertex
      layers, including overlapping assignments.
- [ ] Verify overlays in Edit, Object, Sculpt, Weight Paint, Vertex Paint, and
      Texture Paint modes on the supported Blender builds being released.
- [ ] Verify Subdivision Surface evaluated overlays and Mirror/edit-cage fallback
      on a representative production mesh.
- [ ] After Knife and Bisect previews, verify overlay drawing restores GPU state:
      preview lines and later viewport drawing keep their expected width/depth.
- [ ] On a dense production mesh, verify interaction stays responsive and the
      final idle redraw catches up after editing stops.
- [ ] Verify shared-Mesh refusal plus verified and explicit recovery choices.
- [ ] Save/reopen and Undo/Redo after topology edits without ownership drift.
- [ ] Verify Automatic, English, and Chinese labels and tooltips.

## Artifact gate

- [ ] ZIP contains `__init__.py`, `blender_manifest.toml`, every runtime module,
      and the full `LICENSE` at the extension root.
- [ ] README, install guide, changelog, and manifest describe the release.
- [ ] The archive hash and actually tested Blender versions are recorded.
