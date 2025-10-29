# Usage Examples

This document provides practical examples of how to use Mesh Annotation Layers in real-world scenarios.

## Example 1: Character Face Topology

**Goal**: Organize facial topology into different regions for easier management.

**Steps**:
1. Create layers for different facial features:
   - "Eye Loops" (Blue)
   - "Mouth Loops" (Green)
   - "Nose Bridge" (Yellow)
   - "Cheek Flow" (Purple)
   - "Problem Areas" (Red)

2. In Edit Mode, select face loops around eyes
3. Assign to "Eye Loops" layer
4. Repeat for each facial region

**Benefits**:
- Quickly identify which edges belong to which facial features
- Easy to select all edges in a specific region for adjustment
- Visual reference for maintaining good topology flow

---

## Example 2: Hard Surface Panel Organization

**Goal**: Mark different panels on a hard surface model (e.g., sci-fi armor, vehicle).

**Steps**:
1. Create layers for each panel section:
   - "Front Panels" (Red)
   - "Side Panels" (Blue)
   - "Back Panels" (Green)
   - "Detail Panels" (Yellow)

2. Select faces for each panel section
3. Assign to corresponding layer

**Benefits**:
- Clear visual separation of different panels
- Easy to work on one section at a time
- Helps maintain design consistency

---

## Example 3: UV Seam Planning

**Goal**: Plan and mark UV seams before unwrapping.

**Steps**:
1. Create layer "UV Seams" (Bright Red)
2. Switch to edge select mode
3. Select edges where you want seams
4. Assign to "UV Seams" layer
5. Add another layer "UV Islands" (Different colors) for island boundaries

**Benefits**:
- Visualize seam placement before committing
- Easy to adjust seam positions
- Reference while unwrapping
- No confusion with actual UV seams

---

## Example 4: Retopology Planning

**Goal**: Plan edge flow on a high-poly sculpt before retopologizing.

**Steps**:
1. Import or create high-poly mesh
2. Create layers:
   - "Main Loops" (Blue) - Primary edge flow
   - "Support Loops" (Green) - Secondary edge flow
   - "Poles" (Red) - Mark pole vertices
   - "Sharp Edges" (Yellow) - Hard edge boundaries

3. In Edit Mode, select edges that will form main loops
4. Assign to "Main Loops"
5. Mark support loops and poles similarly

**Benefits**:
- Clear topology plan before starting retopo work
- Reference for maintaining good edge flow
- Helps identify potential problem areas

---

## Example 5: Mesh Quality Control

**Goal**: Mark areas that need attention during cleanup.

**Steps**:
1. Create layers:
   - "N-Gons" (Red) - Non-quad faces
   - "Triangles" (Orange) - Triangulated areas
   - "Good Topo" (Green) - Clean quad topology
   - "Needs Cleanup" (Purple) - Problem areas

2. Select problem faces and assign to appropriate layers
3. Work through each layer systematically

**Benefits**:
- Systematic approach to mesh cleanup
- Track progress visually
- Ensure nothing is missed

---

## Example 6: Edge Flow Mapping

**Goal**: Document and visualize edge flow patterns.

**Steps**:
1. Create layers for different flow directions:
   - "Horizontal Flow" (Blue)
   - "Vertical Flow" (Red)
   - "Diagonal Flow" (Yellow)
   - "Circular Flow" (Green)

2. Select edge loops and assign to appropriate layer
3. Toggle visibility to study individual flows

**Benefits**:
- Understand complex topology
- Learn from well-made models
- Plan edge flow for your own models

---

## Example 7: Multi-Part Model Organization

**Goal**: Organize different parts of a complex model.

**Steps**:
1. For a character model, create layers:
   - "Head" (Red)
   - "Torso" (Blue)
   - "Arms" (Green)
   - "Legs" (Yellow)
   - "Hands" (Purple)
   - "Feet" (Orange)

2. Select faces for each body part
3. Assign to corresponding layer

**Benefits**:
- Quick selection of entire body parts
- Easy to hide/show specific parts
- Helps with weight painting planning

---

## Example 8: Subdivision Planning

**Goal**: Mark areas that need different subdivision levels.

**Steps**:
1. Create layers:
   - "High Detail" (Red) - Needs more subdivision
   - "Medium Detail" (Yellow) - Standard subdivision
   - "Low Detail" (Green) - Minimal subdivision
   - "No Subdivision" (Blue) - Keep as is

2. Analyze model and assign faces to appropriate layers

**Benefits**:
- Optimize subdivision for performance
- Focus detail where needed
- Maintain low poly count where possible

---

## Example 9: Animation-Ready Topology

**Goal**: Mark areas important for animation.

**Steps**:
1. Create layers:
   - "Deformation Zones" (Red) - High deformation areas (joints)
   - "Rigid Areas" (Blue) - Minimal deformation
   - "Edge Loops" (Green) - Important for animation
   - "Problem Areas" (Yellow) - May cause issues

2. Mark joints, elbows, knees with dense loops
3. Assign to "Deformation Zones"

**Benefits**:
- Ensure proper topology for animation
- Avoid deformation issues
- Plan edge loop placement

---

## Example 10: Learning/Reference

**Goal**: Study and learn from existing models.

**Steps**:
1. Import a well-made reference model
2. Create layers for different topology patterns:
   - "5-Point Poles"
   - "Edge Flow Pattern A"
   - "Edge Flow Pattern B"
   - "Interesting Solutions"

3. Mark and study different topology solutions

**Benefits**:
- Learn topology patterns
- Build personal reference library
- Improve modeling skills

---

## Tips for All Examples

1. **Color Consistency**: Use similar colors across projects for same purposes
2. **Naming**: Use clear, descriptive names
3. **Documentation**: Save examples in a reference .blend file
4. **Opacity**: Adjust opacity to see underlying mesh clearly
5. **Layering**: Don't overlap similar information - use separate layers
6. **Cleanup**: Remove layers when done with a project phase

---

## Combining Multiple Workflows

You can combine multiple examples in one project:

1. Start with panel organization (Example 2)
2. Add UV seam planning (Example 3)
3. Mark quality issues (Example 5)
4. Plan subdivision (Example 8)

Each serves a different purpose and can coexist in the same file.

---

## Performance Notes

For each example:
- **Small meshes** (< 10k faces): No performance concerns
- **Medium meshes** (10k-50k faces): Good performance with many layers
- **Large meshes** (50k-100k faces): Use fewer layers, hide when not needed
- **Very large meshes** (> 100k faces): Use sparingly, focus on specific areas

---

## File Organization

When using these workflows, consider:
- Save example files for future reference
- Document your layer naming conventions
- Create templates for common workflows
- Share useful layer setups with team members
