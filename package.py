#!/usr/bin/env python3
"""
Package Mesh Annotation Layers addon for distribution
Creates a ZIP file suitable for Blender addon installation
"""

import os
import zipfile
from pathlib import Path
import datetime

def create_addon_zip():
    """Create a ZIP package of the addon"""
    
    # Paths
    script_dir = Path(__file__).parent
    addon_dir = script_dir / "mesh_annotation_layers"
    output_dir = script_dir / "dist"
    
    # Create dist directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    
    # Generate filename with version and date
    version = "1.0.0"
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    zip_filename = f"mesh_annotation_layers_v{version}_{date_str}.zip"
    zip_path = output_dir / zip_filename
    
    print(f"Creating addon package: {zip_filename}")
    
    # Files to include in the ZIP
    addon_files = [
        "__init__.py",
    ]
    
    # Create ZIP file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filename in addon_files:
            file_path = addon_dir / filename
            if file_path.exists():
                arcname = f"mesh_annotation_layers/{filename}"
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")
            else:
                print(f"  Warning: {filename} not found")
    
    # Get file size
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    
    print(f"\n✓ Package created successfully!")
    print(f"  Location: {zip_path}")
    print(f"  Size: {size_mb:.2f} MB")
    print(f"\nTo install in Blender:")
    print(f"  1. Open Blender")
    print(f"  2. Go to Edit > Preferences > Add-ons")
    print(f"  3. Click 'Install...'")
    print(f"  4. Select: {zip_path}")
    print(f"  5. Enable the checkbox next to 'Mesh: Mesh Annotation Layers'")
    
    return zip_path

if __name__ == "__main__":
    create_addon_zip()
