# Installation Guide

## Method 1: Install from ZIP (Recommended)

1. Create a distribution ZIP file:
   ```bash
   python3 package.py
   ```
   This creates a file like `dist/mesh_annotation_layers_v1.0.0_YYYYMMDD.zip`

2. Open Blender (version 3.0 or higher)
3. Go to `Edit` > `Preferences` > `Add-ons`
4. Click the `Install...` button
5. Navigate to the `dist` folder and select the ZIP file
6. Click `Install Add-on`
7. Enable the addon by checking the checkbox next to "Mesh: Mesh Annotation Layers"

## Method 2: Manual Installation from Repository

1. Clone or download this repository:
   ```bash
   git clone https://github.com/Nkctro/Mesh-Annotation-Layers.git
   ```

2. Locate your Blender addons directory:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`
   - **macOS**: `/Users/$USER/Library/Application Support/Blender/<version>/scripts/addons/`
   - **Linux**: `~/.config/blender/<version>/scripts/addons/`

3. Copy the entire `mesh_annotation_layers` folder from the repository to the addons directory

4. Restart Blender or refresh the addons list

5. Go to `Edit` > `Preferences` > `Add-ons`

6. Search for "Mesh Annotation Layers"

7. Enable the addon by checking the checkbox

## Verifying Installation

1. Create or select a mesh object in Blender
2. Enter Edit Mode (press Tab)
3. Press N to open the sidebar
4. You should see an "Annotation" tab
5. Click on the Annotation tab to access the addon panel

## Troubleshooting

**Addon doesn't appear in the list:**
- Make sure you've copied the entire `mesh_annotation_layers` folder (not just the `__init__.py` file)
- Check that the folder is in the correct addons directory
- Restart Blender

**Panel doesn't show up:**
- Make sure you're in Edit Mode with a mesh object selected
- Press N to toggle the sidebar visibility
- Check that the addon is enabled in Preferences

**Errors when enabling:**
- Check that you're using Blender 3.0 or higher
- Look at the Blender console for error messages
- Make sure all files in the addon folder are intact

## Uninstallation

1. Go to `Edit` > `Preferences` > `Add-ons`
2. Find "Mesh: Mesh Annotation Layers"
3. Click the checkbox to disable it
4. Click the `Remove` button to completely uninstall
