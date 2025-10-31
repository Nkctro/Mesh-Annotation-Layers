#!/usr/bin/env python3
"""
Package Mesh Annotation Layers addon for distribution
Creates a ZIP file suitable for Blender addon installation
"""

import zipfile
from pathlib import Path
import datetime
import tomllib

def get_addon_version():
    """Extract version from blender_manifest.toml"""
    script_dir = Path(__file__).parent
    manifest_file = script_dir / "blender_manifest.toml"

    try:
        with open(manifest_file, "rb") as f:
            manifest_data = tomllib.load(f)
    except FileNotFoundError:
        return "unknown"
    except tomllib.TOMLDecodeError as ex:
        print(f"Warning: failed to parse manifest ({ex}).")
        return "unknown"

    version = manifest_data.get("version")
    return str(version) if version else "unknown"

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
    
    # Root files required for Blender extensions
    root_files = [
        "blender_manifest.toml",
        "LICENSE",
        "README.md",
    ]
    
    # Additional documentation files to include in root of ZIP
    doc_files = [
        "INSTALL.md",
        "CHANGELOG.md",
        "QUICK_REFERENCE.md",
        "EXAMPLES.md",
        "FAQ.md",
        "CONTRIBUTING.md",
        "ARCHITECTURE.md",
        "SECURITY.md",
    ]
    
    # Create ZIP file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add root files (required for Blender extensions)
        print("Adding root files:")
        for filename in root_files:
            file_path = script_dir / filename
            if file_path.exists():
                arcname = f"mesh_annotation_layers/{filename}"
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")
            else:
                print(f"  Warning: {filename} not found (required for Blender extensions)")
        
        # Add addon files
        print("\nAdding addon code:")
        for filename in addon_files:
            file_path = addon_dir / filename
            if file_path.exists():
                arcname = f"mesh_annotation_layers/{filename}"
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")
            else:
                print(f"  Warning: {filename} not found")
        
        # Add additional documentation files
        print("\nAdding documentation:")
        for filename in doc_files:
            file_path = script_dir / filename
            if file_path.exists():
                arcname = f"mesh_annotation_layers/{filename}"
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")
    
    # Get file size
    size_kb = zip_path.stat().st_size / 1024
    
    print(f"\n[OK] Package created successfully!")
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
