# Testing Checklist for Mesh Annotation Layers

This checklist should be used for manual testing in Blender once the addon is installed.

## Pre-Installation Tests

- [x] Python syntax validation passed
- [x] CodeQL security scan passed (0 vulnerabilities)
- [x] Code review completed
- [x] Packaging script tested
- [x] ZIP package created successfully

## Installation Tests

### Method 1: Install from ZIP
- [ ] Open Blender 3.x or 4.x
- [ ] Edit → Preferences → Add-ons
- [ ] Click "Install..."
- [ ] Select the ZIP file
- [ ] Addon appears in list
- [ ] Enable checkbox
- [ ] No errors in console

### Method 2: Install from Folder
- [ ] Copy mesh_annotation_layers folder to addons directory
- [ ] Restart Blender
- [ ] Addon appears in preferences
- [ ] Enable checkbox
- [ ] No errors in console

## Basic Functionality Tests

### Layer Creation
- [ ] Create a cube (Shift+A → Mesh → Cube)
- [ ] Enter Edit Mode (Tab)
- [ ] Open sidebar (N key)
- [ ] "Annotation" tab appears
- [ ] Click "+" to add layer
- [ ] Layer appears in list with random color
- [ ] Layer name is editable

### Face Annotation
- [ ] Select some faces
- [ ] Click "Faces" button
- [ ] Selected faces show colored overlay
- [ ] Overlay color matches layer color

### Edge Annotation
- [ ] Create new layer
- [ ] Switch to edge select mode (2)
- [ ] Select some edges
- [ ] Click "Edges" button
- [ ] Selected edges show colored overlay (thicker lines)

### Vertex Annotation
- [ ] Create new layer
- [ ] Switch to vertex select mode (1)
- [ ] Select some vertices
- [ ] Click "Vertices" button
- [ ] Selected vertices show colored overlay (points)

### Layer Management
- [ ] Rename a layer by clicking its name
- [ ] Change layer color by clicking color swatch
- [ ] Color picker works
- [ ] Toggle layer visibility (eye icon)
- [ ] Hidden layer doesn't show overlay
- [ ] Delete a layer (select and click "-")
- [ ] Layer and its data are removed

### Selection Operations
- [ ] Create layer with some faces
- [ ] Deselect all (Alt+A)
- [ ] Click "Select Layer Elements"
- [ ] Previously assigned faces are selected

### Remove Operations
- [ ] Assign faces to a layer
- [ ] Select some of those faces
- [ ] Click "Remove Selected" for faces
- [ ] Those faces no longer show overlay
- [ ] Other faces still show overlay

### Clear Operation
- [ ] Assign elements to a layer
- [ ] Click "Clear Layer"
- [ ] All overlays for that layer disappear
- [ ] Layer still exists but empty

### Opacity Control
- [ ] Adjust "Opacity" slider
- [ ] All overlays become more/less transparent
- [ ] Works with all element types

### Multiple Layers
- [ ] Create 5+ layers
- [ ] Assign different faces to different layers
- [ ] All layers show correctly with different colors
- [ ] Toggle visibility of individual layers
- [ ] Remove specific layers
- [ ] Remaining layers still work

## Advanced Tests

### Multiple Objects
- [ ] Create two separate mesh objects
- [ ] Each has its own independent layers
- [ ] Switching objects shows correct layers
- [ ] Layers don't interfere between objects

### Large Mesh Performance
- [ ] Create a subdivided plane (10k+ faces)
- [ ] Create annotation layers
- [ ] Assign large selections to layers
- [ ] Check viewport performance
- [ ] Overlays render smoothly

### Mode Switching
- [ ] Create layers in Edit Mode
- [ ] Switch to Object Mode
- [ ] Overlays disappear (expected)
- [ ] Switch back to Edit Mode
- [ ] Overlays reappear correctly

### Undo/Redo
- [ ] Create layer (Ctrl+Z to undo)
- [ ] Layer disappears
- [ ] Ctrl+Shift+Z to redo
- [ ] Layer reappears
- [ ] Test undo/redo for all operations

### File Save/Load
- [ ] Create layers with annotations
- [ ] Save .blend file
- [ ] Close Blender
- [ ] Open the .blend file
- [ ] All layers and annotations preserved
- [ ] Everything works as before

### Edge Cases
- [ ] Create layer with no elements
- [ ] Layer works, just shows nothing
- [ ] Try to remove layer when none selected
- [ ] Operation disabled or handled gracefully
- [ ] Rapidly toggle visibility
- [ ] No crashes or errors
- [ ] Create 20+ layers
- [ ] Performance acceptable

## UI/UX Tests

### Visual Clarity
- [ ] Colors are clearly visible
- [ ] Overlays don't obscure mesh too much
- [ ] Opacity adjustment helps visibility
- [ ] Eye icons are intuitive
- [ ] Layer names are readable

### Workflow Smoothness
- [ ] Common operations are quick
- [ ] No unnecessary clicks
- [ ] Keyboard-free workflow possible
- [ ] Intuitive for first-time users

### Error Handling
- [ ] Delete mesh with annotations
- [ ] No errors or crashes
- [ ] Switch to non-mesh object
- [ ] Panel disappears or disables appropriately
- [ ] Try operations in Object Mode
- [ ] Operations disabled appropriately

## Documentation Tests

- [ ] README.md is clear and helpful
- [ ] Installation instructions work
- [ ] Examples are practical
- [ ] FAQ answers common questions
- [ ] Quick reference is useful

## Final Checks

- [ ] No console errors during any operation
- [ ] No crashes
- [ ] All features work as documented
- [ ] Performance is acceptable
- [ ] Ready for production use

## Issues Found

List any issues found during testing:

1. 
2. 
3. 

## Test Environment

- Blender Version: _______________
- Operating System: _______________
- Graphics Card: _______________
- Date Tested: _______________
- Tester Name: _______________

## Overall Assessment

- [ ] Ready for release
- [ ] Needs minor fixes
- [ ] Needs major fixes

## Notes

(Add any additional notes here)
