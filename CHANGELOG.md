# Changelog

All notable changes to the Mesh Annotation Layers addon will be documented in this file.

## [1.1.1] - 2025-10-30

### Added
- Language preference toggle to force English, Chinese, or show both labels side by side
- New overlay controls for line width, vertex size, face offset, edge trimming, opacity, and backface visibility
- Operators to assign the current selection or loops to a brand new layer in one click
- Context menu integration plus seam-marking tools that convert face layers to UV seams
- "Pick From Selection" action to activate the matching layer based on the current mesh selection

### Changed
- Annotation sidebar reorganised so assignment tools and overlay controls are easier to find
- Documentation refreshed in English and Chinese to cover the new workflow improvements

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
