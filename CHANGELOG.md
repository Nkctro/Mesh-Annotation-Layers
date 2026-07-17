# Changelog

All notable changes to the Mesh Annotation Layers addon will be documented in this file.

# [1.3.1] - 2026-07-17

### Changed

- Replaced implementation-shape source tests with a smaller set of behavioral
  contracts and isolated mutable Blender smoke-test fixtures.
- Removed duplicated release-version text and the obsolete template labeler
  workflow, which was the repository's only automated GitHub job.
- Renamed the shared-state fingerprint as a compatibility token so its guarantee
  is not confused with historical mesh-element identity.

### Fixed

- Avoid direct evaluated-index mapping for unknown or topology-generating
  modifier stacks merely because their element counts match the source mesh.
- Invalidate retained evaluated geometry through its own dependency closure even
  after the corresponding GPU batch entry has been discarded.
- Invalidate Texture Paint geometry conservatively when painted images may
  drive modifiers, while retaining cage geometry for unsupported node stacks.
- Fall back to the edit cage for Mirror until evaluated faces have reliable
  source provenance instead of assigning them by nearest-face distance.
- Tessellate concave evaluated polygons in scale-normalized coordinates without
  drawing triangles outside the source face, including micro-scale meshes.
- Route filtered Subdivision vertices through topology mapping so later
  deformers and loose geometry do not lose or misplace annotations.
- Treat a zero-level Subdivision Surface modifier as index-preserving so later
  deformers still draw on evaluated coordinates.
- Track Shape Key dependencies and invalidate Weight Paint geometry when key
  values change.
- Invalidate Solo Active GPU batches when the active layer index changes.
- Invalidate the property owner's GPU batch rather than the currently active
  Object when a non-active object's layer or display setting changes.

# [1.3.0] - 2026-07-16

### Added
- Keep annotations visible in Object, Weight Paint, Vertex Paint, Sculpt, and Texture Paint modes; assignment tools remain safely limited to Edit Mode.
- Added face/edge/vertex workspace tabs that synchronize Blender's mesh selection mode when editing.
- Added a one-click action to enter Edit Mode from read-only annotation views.
- Added a centralized translation catalog with safe named-parameter formatting.
- Added localized hover descriptions for every annotation operator, including
  icon-only layer controls and viewport overlay toggles.

### Changed
- Converted the repository into a directly valid Blender Extension source tree:
  `mesh_annotation_layers/` now contains both `blender_manifest.toml` and
  `__init__.py`, so the official validate/build commands work without repacking.
- Reload all extension submodules in dependency order when Blender runs Reload
  Scripts, eliminating stale operators, panels, data models, and overlay code.
- Removed legacy `bl_info` metadata and unused file/network permissions; the
  extension manifest is now the single metadata source.
- Flattened the Edit Mode context menu around the current face/edge/vertex
  selection mode. Active-layer assignment, one-click layer creation, loop/path
  assignment, and all removal modes are now direct actions; only choosing a
  different target layer opens a submenu.
- Selecting a target from the context menu now makes it active for subsequent
  assignments, and the target-layer menu no longer calculates per-layer element
  counts while opening.
- Scoped dependency-graph invalidation to objects and modifier dependencies that
  can actually affect a cached overlay, eliminating rebuilds caused by unrelated
  scene edits.
- Made evaluated fallback mapping demand-driven so face-only overlays no longer
  calculate edge and vertex provenance, and sparse edge/vertex mapping considers
  only the annotated source neighbourhood.
- Added bounded LRU caches for decoded annotation data, layer usage counts,
  local evaluated geometry, and GPU batches; large entries are weighted so
  switching among dense meshes cannot grow memory without limit.
- Draw face, point, and default untrimmed edge batches from local coordinates,
  moving object transforms and surface offsets to the GPU where possible.
- Reuse decoded mappings and update only changed BMesh custom-data elements for
  assignment and removal operations.
- Debounce expensive interactive overlay rebuilds according to measured build
  cost while preserving a final idle redraw.
- Reorganized the sidebar around one active element type and moved display tuning into a collapsed child panel.
- Batched all visible edges in a layer into one GPU draw call and preserved the overlay cache during weight strokes that cannot deform the evaluated mesh.
- Removed per-row full-mesh layer counting from the layer list.
- Changed defaults to disable through-mesh display, use 7 px edges and 10 px points, and offset faces, edges, and points by 0.0001.
- Keep cached annotation geometry during vertex/texture paint strokes when paint data cannot drive deformation.
- Reuse sparse JSON layer assignments during coordinate-only edits instead of rescanning every mesh element and custom-data stack.
- Keep the persisted compatibility token sparse after normal writes, while validating every
  non-empty custom-data payload before shared Object data is trusted.
- Refresh evaluated overlays adaptively during mesh and sculpt interaction, prioritizing input responsiveness and scheduling a final redraw automatically.
- Split the former single-file implementation into focused constants, localization,
  model, evaluated-geometry, overlay, loop, property, operator, and UI modules.
- Replaced mutable element metadata dictionaries with validated immutable element specifications.
- Kept registration transactional while reducing it to the normal Blender
  enable, disable, failure-cleanup, and Reload Scripts lifecycle.
- Package every Python module instead of assuming a single-file add-on.
- Language selection in the add-on preferences offers Automatic, English, and
  Chinese; Automatic follows Blender and falls back to English when the interface
  language has no add-on translation.
- Replaced comma-separated BMesh ownership values with a versioned, checksummed
  unsigned-varint stack that fails before Blender's 255-byte string limit can
  truncate data; legacy values remain readable.
- Made shared Mesh annotations explicitly read-only and added a single-user
  recovery action. Shared mappings now require a topology/custom-data agreement check;
  stale mappings are quarantined and recovery requires an explicit keep/discard
  choice instead of silently trusting element indices.
- Made discard recovery operate per element type, so a stale face mapping does
  not erase independently verified edge or vertex assignments.
- Excluded Blender's Fake User and Extra User retention flags from shared-Mesh
  detection and topology reconciliation while still locking data used by
  multiple real owners.
- Coalesced indistinguishable Edit Mode geometry events for 150 ms, then
  reconciled BMesh ownership even when topology counts did not change.
- Initialize new BMesh ownership layers sparsely, skip decoding empty payloads,
  and keep synchronized/quarantined signatures in one bounded state cache.
- Consolidated repeated operator properties, loop dispatch, create-and-assign
  rollback, evaluated-edge mapping, and reconciliation finalization.
- Removed obsolete loop helpers, compatibility fields, stale translations, and
  the custom packaging scripts; Blender's Extension CLI is now the only release
  builder.
- Added the full GPL-3.0-or-later license to the extension source so official
  build artifacts distribute it automatically.

### Fixed
- Preflight the complete final mapping before any BMesh/RNA mutation and roll
  back payloads, JSON, caches, compatibility state, collection cursors, active indices,
  and ID hints when a commit fails. Any Mesh state that cannot be confirmed as
  restored is quarantined instead of treated as synchronized.
- Merge topology ownership into private snapshots so an incomplete/unsavable
  legacy stack cannot poison the decoded cache or be marked synchronized.
- Force stack reconciliation before every explicit model read/write, closing the
  same-call-flow window before dependency-graph dirty notifications arrive.
- Keep viewport drawing read-only; the debounced topology timer owns durable
  JSON reconciliation.
- Roll back the classes and Object property accepted during a failed
  registration attempt.
- Verify the RNA fixed type of `Object.mesh_annotations`; a foreign same-name
  property is preserved and reported instead of accepted or deleted.
- Quarantine malformed, non-object, or lossy annotation JSON instead of treating
  it as a safely empty shared mapping.
- Make the primary remove-selected action affect only the active layer, preserving any other annotations assigned to the same mesh elements; explicit top-layer and all-layer removal remain available in the context menu.
- Treat Undo and Redo as complete overlay-cache boundaries, then restore annotation ownership from the mesh custom-data layers so labels cannot drift onto stale element indices.
- Keep annotation colors visually stable across selection changes by removing selection-dependent brightness boosts and additive blending.
- Map annotated source vertices to their actual Subdivision Surface descendants instead of relying on evaluated vertex ordering.
- Resolve fallback vertex mappings from intersections of evaluated source-edge chains instead of nearest-point guesses.
- Offset each evaluated edge endpoint with its own vertex normal so equal point/edge offsets remain exactly aligned on curved surfaces.
- Apply edge shortening to the two ends of the complete subdivided source-edge chain, eliminating gaps at internal subdivision segments.
- Ignore malformed serialized layer entries without breaking panel drawing or operators.
- Removed a duplicated context-menu implementation that could diverge during maintenance.
- Added repeatable source-contract and Blender integration smoke tests for future refactors.
- Restored manual language selection for extensions installed under Blender's
  `bl_ext.<repository>.<extension>` namespace.
- Prevented annotation JSON from being overwritten by another Object that shares
  the same Mesh data.
- Prevented malformed or silently truncated BMesh stacks from being interpreted
  as a valid empty assignment.
- Detect equal-count topology replacement through dirty edit-mesh boundaries
  instead of relying only on vertex/edge/face counts.
- Clear every identity-keyed cache before loading or factory-resetting a file.
- Make teardown best-effort across menus, handlers, timers, draw handles,
  properties, and classes so an already-removed resource cannot strand the
  extension in a half-registered state.

# [1.1.5] - 2025-11-02

### Fixed
- Restored viewport GPU state after drawing overlays so Knife/Bisect preview lines no longer thicken or disappear.
- Added a retopology-specific depth bias so annotations stay visible with “Show Through Mesh” disabled while still respecting occlusion.
- Draw annotations on modifier-evaluated geometry so face, edge, and vertex layers follow Subdivision Surface and Mirror + Subdivision results.
- Cache evaluated overlay batches and read only annotated subdivision ranges, avoiding full evaluated-mesh rebuilds on every viewport redraw.

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
