# Frequently Asked Questions (FAQ)

## General Questions

### Q: What is Mesh Annotation Layers?
**A:** It's a Blender addon that allows you to add colored overlay layers to mesh elements (vertices, edges, faces) in Edit Mode for organization and annotation purposes, without modifying the actual mesh data.

### Q: Is this addon free?
**A:** Yes, it's released under the GPL-3.0 license and is completely free to use.

### Q: Which Blender versions are supported?
**A:** Blender 3.0 and above. It may work on earlier versions but is not officially tested or supported.

### Q: Does it work with Blender 4.0+?
**A:** Yes, the addon is designed to be compatible with Blender 4.0 and future versions.

---

## Installation Questions

### Q: How do I install the addon?
**A:** See the [INSTALL.md](INSTALL.md) file for detailed installation instructions. The quick method is: Preferences → Add-ons → Install → Select `__init__.py` → Enable checkbox.

### Q: Can I install it as a ZIP file?
**A:** Yes, you can zip the `mesh_annotation_layers` folder and install the ZIP through Blender's addon preferences.

### Q: The addon doesn't appear in my addon list, why?
**A:** Make sure you installed the entire `mesh_annotation_layers` folder (or the ZIP), not just the `__init__.py` file alone. Also check you're using Blender 3.0+.

---

## Usage Questions

### Q: Why can't I see the annotation panel?
**A:** The panel only appears when:
1. You have a mesh object selected
2. You're in Edit Mode (press Tab)
3. The sidebar is open (press N)
4. You're on the "Annotation" tab

### Q: Can I use this in Object Mode?
**A:** No, the addon only works in Edit Mode as it's designed for topology work which requires edit-level access to mesh elements.

### Q: Can I annotate multiple objects at once?
**A:** No, each object has its own independent annotation layers. You need to work on objects one at a time.

### Q: Why are my overlays not visible?
**A:** Check:
- The layer visibility (eye icon) is enabled
- You're in Edit Mode
- Opacity is not set to 0
- The layer actually has elements assigned to it

### Q: Can I mix vertices, edges, and faces in the same layer?
**A:** No, each layer stores only one type of element. You can assign vertices, edges, OR faces to a layer, but not mix them. Create separate layers for different element types.

---

## Performance Questions

### Q: Will this slow down Blender?
**A:** For normal meshes (under 50k faces), performance impact is minimal. Very large meshes (100k+ faces) with many layers may see some slowdown in the viewport.

### Q: How many layers can I create?
**A:** Technically unlimited, but for performance reasons, it's recommended to use only the layers you actually need (typically 5-20 layers is plenty).

### Q: Does it affect render times?
**A:** No, annotations are only visual overlays in Edit Mode and have zero impact on rendering.

---

## Data and Persistence Questions

### Q: Are annotations saved with my Blender file?
**A:** Yes, all annotation layer data is saved with your .blend file automatically.

### Q: Can I export annotations?
**A:** The annotations themselves are not exported (they're Blender-specific data), but the underlying mesh geometry is exported normally.

### Q: Will annotations affect my mesh export (FBX, OBJ, etc.)?
**A:** No, annotations don't modify the mesh in any way and won't affect exports.

### Q: Can I share annotation layers between files?
**A:** Currently, you need to manually recreate layers in each file. Copying the entire object may preserve layers.

### Q: What happens if I delete a mesh object with annotations?
**A:** The annotation data is deleted along with the object. Make sure to save your file if you want to keep the annotations.

---

## Technical Questions

### Q: Does this modify my mesh data?
**A:** No, it only stores element indices and draws overlays. Your mesh geometry, materials, and vertex colors remain untouched.

### Q: Can I use this with modifiers?
**A:** Yes, annotations work with the base mesh and are independent of modifiers.

### Q: Does it work with sculpt mode or other modes?
**A:** No, it only works in Edit Mode. The overlays are also only visible in Edit Mode.

### Q: Can I use this in Blender's geometry nodes?
**A:** No, this is a separate annotation system and doesn't integrate with geometry nodes.

### Q: Does it support undo/redo?
**A:** Yes, all operations support Blender's standard undo/redo system (Ctrl+Z / Ctrl+Shift+Z).

---

## Compatibility Questions

### Q: Does it work with other addons?
**A:** Yes, it should work alongside other addons without conflicts as it uses its own data structures.

### Q: Can I use it with the built-in annotation tools?
**A:** Yes, these are separate systems. The built-in annotation tool is for drawing, while this addon is for mesh element annotation.

### Q: Does it work on Linux/Mac/Windows?
**A:** Yes, it's platform-independent and works on all platforms that support Blender.

---

## Workflow Questions

### Q: What's the best way to organize layers?
**A:** Use consistent naming and color coding. For example:
- Red for problems
- Blue for main flow
- Green for completed areas
- Yellow for UV seams

### Q: Can I animate layer visibility?
**A:** No, layer properties are not animatable as this is a modeling/topology tool, not an animation tool.

### Q: How do I copy layer settings to another object?
**A:** Currently not supported. You'll need to manually recreate layers on each object.

### Q: Can I import layer presets?
**A:** Not currently supported, but this could be a feature in future versions.

---

## Troubleshooting

### Q: I'm getting errors when enabling the addon
**A:** Check:
- You're using Blender 3.0 or higher
- You have Python installed correctly (comes with Blender)
- Look at the Blender console for specific error messages
- Try restarting Blender

### Q: The overlays look weird/glitchy
**A:** Try:
- Updating your graphics drivers
- Checking if other overlays work in Blender
- Reducing the number of elements assigned to layers
- Lowering the opacity

### Q: Colors don't show up correctly
**A:** Make sure:
- Opacity is above 0
- Layer visibility is enabled
- You're in Edit Mode
- The color isn't too similar to your viewport background

---

## Feature Requests

### Q: Can you add feature X?
**A:** Please open an issue on the GitHub repository with your feature request. We welcome community input!

### Q: Will there be more features in the future?
**A:** Yes, we plan to continue developing the addon based on user feedback.

### Q: Can I contribute to the addon?
**A:** Yes! The addon is open source. See CONTRIBUTING.md for guidelines (if available).

---

## Support

### Q: Where can I get help?
**A:** 
- Check this FAQ
- Read the README.md and QUICK_REFERENCE.md
- Open an issue on GitHub
- Check the Blender Artists forum

### Q: I found a bug, where do I report it?
**A:** Please open an issue on the GitHub repository with:
- Blender version
- Addon version
- Steps to reproduce
- Screenshots if applicable

### Q: Can I request a feature?
**A:** Yes, please open a feature request issue on GitHub.

---

## Miscellaneous

### Q: Can I use this for commercial projects?
**A:** Yes, the GPL-3.0 license allows commercial use.

### Q: Do I need to credit the addon in my work?
**A:** Not required, but appreciated! The annotations don't export anyway.

### Q: Can I modify the addon for my needs?
**A:** Yes, it's open source under GPL-3.0. Feel free to modify it, and consider contributing improvements back to the project.

### Q: Is there a video tutorial?
**A:** Check the GitHub repository README for links to video tutorials (if available).

---

**Still have questions?** Open an issue on GitHub or check the documentation files in the repository.
