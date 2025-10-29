#!/usr/bin/env python3
"""
Package Mesh Annotation Layers addon for distribution
Creates a ZIP file suitable for Blender addon installation
"""

import os
import zipfile
from pathlib import Path
import datetime
import re

def get_addon_version():
    """Extract version from __init__.py bl_info"""
    script_dir = Path(__file__).parent
    init_file = script_dir / "mesh_annotation_layers" / "__init__.py"
    
    with open(init_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find version in bl_info
    version_match = re.search(r'"version":\s*\((\d+),\s*(\d+),\s*(\d+)\)', content)
    if version_match:
        return f"{version_match.group(1)}.{version_match.group(2)}.{version_match.group(3)}"
    return "unknown"

def create_addon_zip():
    """Create a ZIP package of the addon"""
    
    # Paths
    script_dir = Path(__file__).parent
    addon_dir = script_dir / "mesh_annotation_layers"
    output_dir = script_dir / "dist"
    
    # Create dist directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    
    # Get version from addon
    version = get_addon_version()
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    zip_filename = f"mesh_annotation_layers_v{version}_{date_str}.zip"
    zip_path = output_dir / zip_filename
    
    print(f"Creating addon package: {zip_filename}")
    print(f"Version: {version}\n")
    
    # Files to include in the addon ZIP
    addon_files = [
        "__init__.py",
    ]
    
    # Documentation files to include in root of ZIP
    doc_files = [
        "README.md",
        "LICENSE",
        "INSTALL.md",
        "CHANGELOG.md",
        "QUICK_REFERENCE.md",
        "EXAMPLES.md",
        "FAQ.md",
        "CONTRIBUTING.md",
        "ARCHITECTURE.md",
    ]
    
    # Create ZIP file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add addon files
        for filename in addon_files:
            file_path = addon_dir / filename
            if file_path.exists():
                arcname = f"mesh_annotation_layers/{filename}"
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")
            else:
                print(f"  Warning: {filename} not found")
        
        # Add documentation files
        print("\nAdding documentation:")
        for filename in doc_files:
            file_path = script_dir / filename
            if file_path.exists():
                arcname = f"mesh_annotation_layers/{filename}"
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")
    
    # Get file size
    size_kb = zip_path.stat().st_size / 1024
    
    print(f"\n✓ Package created successfully!")
    print(f"  Location: {zip_path}")
    print(f"  Size: {size_kb:.2f} KB")
    print(f"\nTo install in Blender:")
    print(f"  1. Open Blender")
    print(f"  2. Go to Edit > Preferences > Add-ons")
    print(f"  3. Click 'Install...'")
    print(f"  4. Select: {zip_path}")
    print(f"  5. Enable the checkbox next to 'Mesh: Mesh Annotation Layers'")
    
    return zip_path

if __name__ == "__main__":
    create_addon_zip()
