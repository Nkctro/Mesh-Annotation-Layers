# Quick Reference Guide

## Quick Start

1. **Enter Edit Mode**: Select mesh → Press `Tab`
2. **Open Panel**: Press `N` → Click "Annotation" tab
3. **Add Layer**: Click `+` button
4. **Select Elements**: Select vertices/edges/faces
5. **Assign**: Click "Vertices", "Edges", or "Faces" button

## Common Workflows

### Workflow 1: Marking Different Topology Regions

```
1. Add a new layer (click +)
2. Rename it to "Region 1"
3. Select faces in the first region
4. Click "Faces" to assign
5. Repeat for other regions with different layers
```

### Workflow 2: Edge Flow Annotation

```
1. Add layer named "Main Flow"
2. Change color to blue
3. Select edge loops for main flow
4. Click "Edges" to assign
5. Add layer "Secondary Flow" with different color
6. Assign secondary edge loops
```

### Workflow 3: Marking Problem Areas

```
1. Add layer "Needs Fixing"
2. Change color to red
3. Select problematic faces/vertices
4. Click appropriate assignment button
5. Later: Click "Select Layer Elements" to quickly find them
```

## Keyboard-Free Workflow

All operations can be done with mouse clicks only:
- Add/Remove layers: Click `+` or `-` buttons
- Select layer: Click on layer name in list
- Rename: Click on name, type, press Enter
- Change color: Click color box → Pick color
- Toggle visibility: Click eye icon
- Adjust opacity: Drag slider

## Tips & Tricks

### Color Organization

Use color coding for different purposes:
- **Red**: Areas that need attention
- **Blue**: Main edge flows
- **Green**: Completed areas
- **Yellow**: UV seams
- **Purple**: Special topology

### Layer Naming Conventions

Good naming examples:
- "Front Panel Quads"
- "Back Edge Flow"
- "UV Seam Edges"
- "4-Point Poles"
- "N-Gons to Fix"

### Efficiency Tips

1. **Create template layers**: Set up common layers at the start
2. **Use visibility toggle**: Hide layers you're not working on
3. **Opacity adjustment**: Lower opacity to see mesh underneath
4. **Selection workflow**: Use "Select Layer Elements" to quickly work on specific areas
5. **Clear and reuse**: Use "Clear Layer" to reuse a layer for different elements

## Common Operations

### Add a Layer
Click `+` → Layer appears with random color

### Remove a Layer
Select layer → Click `-` → Layer and all data removed

### Rename a Layer
Click on layer name → Type new name → Press Enter

### Change Layer Color
Click color box → Pick color → Close picker

### Hide/Show Layer
Click eye icon next to layer name

### Assign Selection to Layer
Select elements → Click "Vertices", "Edges", or "Faces"

### Remove Selection from Layer
Select elements → Click corresponding "Remove Selected" button

### Select All Layer Elements
Make layer active → Click "Select Layer Elements"

### Clear All Layer Data
Make layer active → Click "Clear Layer"

## Limitations

- Only works in Edit Mode
- Only works with mesh objects
- One element type per layer (can't mix vertices and faces in same layer)
- Overlays only visible in Edit Mode
- Performance may decrease with very large meshes (100k+ faces)

## Troubleshooting Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| Can't see overlays | Check eye icon is on, increase opacity |
| Can't assign elements | Make sure you're in Edit Mode |
| Panel missing | Press N, check you're in Edit Mode |
| Wrong elements selected | Check active layer and element type |

## Advanced Usage

### Multiple Objects

Each mesh object has its own independent annotation layers. Switch between objects to see their respective layers.

### Copying Layers Between Objects

Currently not supported - layers are per-object. You'll need to manually recreate layers on each object.

### Saving Work

Annotation layers are automatically saved with your .blend file. No special save action needed.

### Performance Optimization

For very large meshes:
- Use fewer layers
- Assign fewer elements per layer
- Hide layers you're not actively using
- Lower the overlay opacity slightly

## Integration with Other Tools

### UV Editing
Mark UV seams and islands with different layers for reference

### Retopology
Mark target edge flow before starting retopology work

### Sculpting
Mark areas in Edit Mode before switching to Sculpt Mode

### Modeling
Mark different detail levels or regions for organized modeling

## Video Tutorial Topics

If creating tutorials, consider covering:
1. Basic setup and first layer
2. Color coding system
3. Edge flow annotation
4. Retopology workflow
5. UV seam marking
6. Team collaboration tips
