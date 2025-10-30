# Changelog

All notable changes to the Mesh Annotation Layers addon will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2025-10-30

### Added
- UV seam marking functionality with two new operators:
  - Mark UV seams from active annotation layer (`MESH_OT_annotation_mark_seam_active`)
  - Mark UV seams from all visible annotation layers (`MESH_OT_annotation_mark_seam_all`)
- Multilingual support system with configurable language display modes
  - Auto mode: Follows Blender's interface language
  - English mode: Always display in English
  - Chinese mode: Always display in Chinese (中文)
  - Both mode: Display both English and Chinese simultaneously
- Addon preferences panel for language and UI customization
- Context menu integration with configurable type selection submenu
- Bilingual text processing system (`bi()` function) for dynamic language switching

### Changed
- **Architecture**: Refactored from single file to package structure
  - Moved from `mesh_annotation_layers.py` to `mesh_annotation_layers/__init__.py`
  - Better code organization and modularity
- **Plugin metadata updates**:
  - Author: "Mesh Annotation Layers Team" → "Nkctro"
  - Location: "3D View > Sidebar > Annotation Layers" → "3D Viewport > Sidebar > Mesh Annotation"
  - Category: "Mesh" → "3D View"
- Enhanced GPU rendering system:
  - Added edge drawing offset for better visual clarity (`EDGE_DRAW_OFFSET = 0.0008`)
  - Improved shader batch rendering
  - More efficient 3D viewport redraw mechanism
- Unified element type definition system (`ELEMENT_DEFS`) for better code organization
  - Separate configurations for faces, edges, and vertices
  - Dedicated icons, data storage, and selection modes for each type

### Improved
- Code organization: 2,247 → 2,621 lines (+374 lines of enhanced functionality)
- Better error handling and property access protection
- Enhanced GPU resource management
- More stable viewport rendering
- Improved documentation with packaging instructions

### Technical
- New utility functions:
  - `get_addon_prefs()` - Retrieve addon preferences
  - `resolve_language_mode()` - Determine current language mode
  - `bi(en, zh)` - Bilingual text processing
  - `tag_view3d_redraw()` - Efficient viewport redraw
- New imports: `colorsys`, `json`, `random`, `Counter`, `defaultdict`, `Vector`, `gpu`, `batch_for_shader`
- Enhanced element type system with unified definitions

### Documentation
- Added SECURITY.md for security policy
- Added GitHub templates (Issues, Pull Requests)
- Added GitHub workflows (auto-labeling, summary generation)
- Enhanced README.md with packaging instructions
- Updated INSTALL.md with more detailed installation options
- Added .editorconfig for consistent code style
- Added .gitattributes for Git configuration
- Improved .gitignore rules

## [1.0.1] - 2025-10-29

### Added
- Initial public release of Mesh Annotation Layers addon
- Multiple annotation layer support for mesh objects
- Custom color assignment for each layer
- Support for annotating vertices, edges, and faces
- Layer visibility toggle with eye icon
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

### Documentation
- Comprehensive README with usage instructions
- Architecture documentation (ARCHITECTURE.md)
- FAQ document (FAQ.md)
- Examples document (EXAMPLES.md)
- Quick reference guide (QUICK_REFERENCE.md)
- Contributing guidelines (CONTRIBUTING.md)
- Installation guide (INSTALL.md)

## [1.0.0] - 2025-10-29

### Added
- Initial development release
- Core functionality for mesh annotation
- Basic UI implementation
- Documentation foundation
