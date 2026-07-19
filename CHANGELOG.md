# Changelog / 更新日志

All notable changes are recorded here. User documentation is maintained in paired English
and Simplified Chinese files. / 所有重要变更记录于此；用户文档以英文和简体中文成对维护。

# [Unreleased]

### Added
- Added paired English and Simplified Chinese installation, user, FAQ, and development docs.
- Added repository-structure contracts for bilingual docs and build tooling.
- Keep annotations visible in Object, Weight Paint, Vertex Paint, Sculpt, and Texture Paint modes; assignment tools remain safely limited to Edit Mode.
- Added face/edge/vertex workspace tabs that synchronize Blender's mesh selection mode when editing.
- Added a one-click action to enter Edit Mode from read-only annotation views.
- Added a centralized translation catalog with safe named-parameter formatting.
- Added localized hover descriptions for every annotation operator, including
  icon-only layer controls and viewport overlay toggles.

### Changed
- Consolidated duplicated root documentation under `docs/en/` and `docs/zh-CN/`.
- Moved the archive builder to `tools/build.py` and folded beta packaging into `--dev`.
- Reorganized the sidebar around one active element type and moved display tuning into a collapsed child panel.
- Batched all visible edges in a layer into one GPU draw call and preserved the overlay cache during weight strokes that cannot deform the evaluated mesh.
- Removed per-row full-mesh layer counting from the layer list.
- Changed defaults to disable through-mesh display, use 7 px edges and 10 px points, and offset faces, edges, and points by 0.0001.
- Keep cached annotation geometry during vertex/texture paint strokes when paint data cannot drive deformation.
- Reuse sparse JSON layer assignments during coordinate-only edits instead of rescanning every mesh element and custom-data stack.
- Refresh evaluated overlays adaptively during mesh and sculpt interaction, prioritizing input responsiveness and scheduling a final redraw automatically.
- Split the former single-file implementation into focused constants, localization,
  model, evaluated-geometry, overlay, loop, property, operator, and UI modules.
- Replaced mutable element metadata dictionaries with validated immutable element specifications.
- Made registration transactional so partial Blender registration failures clean themselves up.
- Package every Python module instead of assuming a single-file add-on.
- Language selection now offers Automatic, English, and Chinese directly in the
  annotation panel; Automatic follows Blender and falls back to English when the
  interface language has no add-on translation.

### Fixed
- Map annotated source vertices to their actual Subdivision Surface descendants instead of relying on evaluated vertex ordering.
- Resolve fallback vertex mappings from intersections of evaluated source-edge chains instead of nearest-point guesses.
- Offset each evaluated edge endpoint with its own vertex normal so equal point/edge offsets remain exactly aligned on curved surfaces.
- Apply edge shortening to the two ends of the complete subdivided source-edge chain, eliminating gaps at internal subdivision segments.
- Ignore malformed serialized layer entries without breaking panel drawing or operators.
- Removed a duplicated context-menu implementation that could diverge during maintenance.
- Added repeatable source-contract and Blender integration smoke tests for future refactors.
- Restored manual language selection for extensions installed under Blender's
  `bl_ext.<repository>.<extension>` namespace.

# [1.1.5] - 2025-11-02

### Fixed
- Restored viewport GPU state after drawing overlays so Knife/Bisect preview lines no longer thicken or disappear.
- Added a retopology-specific depth bias so annotations stay visible with “Show Through Mesh” disabled while still respecting occlusion.
- Draw annotations on modifier-evaluated geometry so face, edge, and vertex layers follow Subdivision Surface and Mirror + Subdivision results.
- Cache evaluated overlay batches and read only annotated subdivision ranges, avoiding full evaluated-mesh rebuilds on every viewport redraw.

# [1.1.3] - 2025-11-02

### Added
- Optional "Propagate On New Geometry" toggle to control whether extruded or duplicated geometry copies existing annotations.

### Fixed
- Newly created geometry no longer inherits annotations when propagation is disabled, preventing accidental layer carry-over.

# [1.1.2] - 2025-10-31

### Changed
- Bumped extension version to 1.1.2 for refreshed package build on Blender 4.2+.
- Resolved annotation drift that occurred after complex topology edits by keeping layer mappings in sync with live bmesh data.

## [1.1.1] - 2025-10-30

### Added
- Language preference toggle to force English, Chinese, or show both labels side by side
- New overlay controls for line width, vertex size, face offset, edge trimming, opacity, and backface visibility
- Operators to assign the current selection or loops to a brand new layer in one click
- Context menu integration plus seam-marking tools that convert face layers to UV seams
- "Pick From Selection" action to activate the matching layer based on the current mesh selection
- **blender_manifest.toml** for Blender 4.2+ extension platform compliance
- Documentation and tracker URLs recorded in the extension manifest metadata

### Changed
- Annotation sidebar reorganised so assignment tools and overlay controls are easier to find
- Documentation refreshed in English and Chinese to cover the new workflow improvements
- Package script now includes blender_manifest.toml in distribution ZIP
- License identifier updated to SPDX format (GPL-3.0-or-later)
- Raised minimum supported Blender version to 4.2 to match the Extensions platform requirements

## [1.0.0] - 2025-10-29

### Added
- Initial release of Mesh Annotation Layers addon
- Multiple annotation layer support for mesh objects
- Custom color assignment for each layer
- Support for annotating vertices, edges, and faces
- Layer visibility toggle
- Adjustable overlay opacity
- Non-destructive annotation system (doesn't modify mesh data)
- Selection tools for layer elements
- Add, remove, and clear layer operations
- UI panel in 3D View sidebar under "Annotation" tab
- Real-time GPU-based overlay rendering
- Persistent layer data saved with Blender files
- Bilingual documentation (English and Chinese)

### Features
- Create unlimited annotation layers per mesh object
- Assign selected vertices, edges, or faces to layers
- Remove elements from layers
- Select all elements in a layer
- Clear all elements from a layer
- Color picker for each layer
- Eye icon for layer visibility control
- Active layer highlighting in UI list
- Layer renaming support
- Random color generation for new layers

### Technical
- Compatible with Blender 3.0+
- Uses bmesh for mesh data access
- GPU shader-based drawing for efficient rendering
- PropertyGroup-based data storage
- Edit Mode only functionality
- Per-object annotation storage
