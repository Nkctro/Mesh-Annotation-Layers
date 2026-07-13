#!/usr/bin/env python3
"""
Package Mesh Annotation Layers addon for distribution
Creates a ZIP file suitable for Blender addon installation
"""

import argparse
import datetime
import re
import zipfile
from pathlib import Path

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

def normalize_version_base(version_str: str) -> str:
    """Strip pre-release/build suffixes (e.g. 1.2.3-alpha+1 -> 1.2.3)."""
    return re.split(r"[-+]", version_str, 1)[0]


def next_beta_build_number(state_path: Path, base_version: str) -> int:
    """Fetch the next beta build number (1-999), resetting when base version changes."""
    try:
        raw = state_path.read_text(encoding="utf-8").strip()
        if not raw:
            raise ValueError
        if " " in raw:
            stored_version, counter_str = raw.split(None, 1)
            current_value = int(counter_str)
        else:
            stored_version = base_version
            current_value = int(raw)
    except (FileNotFoundError, ValueError):
        stored_version = None
        current_value = 0
    if stored_version != base_version:
        current_value = 0
    return (current_value % 999) + 1


def update_manifest_version(manifest_path: Path, new_version: str, original_text: str = None):
    if new_version is None:
        return original_text
    current_text = original_text or manifest_path.read_text(encoding="utf-8")
    updated = re.sub(
        r'(?m)^(\s*version\s*=\s*").*?"',
        lambda match: f'{match.group(1)}{new_version}"',
        current_text,
        count=1,
    )
    if updated == current_text:
        raise RuntimeError("Failed to update manifest version string.")
    manifest_path.write_text(updated, encoding="utf-8")
    return current_text


def update_bl_info_version(init_path: Path, version_tuple, original_text: str = None, build_label: str = None):
    if version_tuple is None and build_label is None:
        return original_text
    current_text = original_text or init_path.read_text(encoding="utf-8")
    updated = current_text

    if version_tuple is not None:
        tuple_str = ", ".join(str(part) for part in version_tuple)
        updated = re.sub(r'"version":\s*\([^\)]*\)', f'"version": ({tuple_str})', updated, count=1)
        if updated == current_text:
            raise RuntimeError("Failed to update bl_info version tuple.")

    if build_label is not None:
        if '"warning":' in updated:
            updated_warning = re.sub(r'"warning":\s*".*?"', f'"warning": "{build_label}"', updated, count=1)
            if updated_warning == updated:
                raise RuntimeError("Failed to update bl_info warning string.")
            updated = updated_warning
        else:
            inserted = re.sub(
                r'("description":\s*".*?",\s*\n)',
                r'\1    "warning": "' + build_label + '",\n',
                updated,
                count=1,
            )
            if inserted == updated:
                raise RuntimeError("Failed to insert bl_info warning string.")
            updated = inserted

    init_path.write_text(updated, encoding="utf-8")
    return current_text


def parse_version_parts(version_str: str):
    base_version = normalize_version_base(version_str)
    parts = base_version.split(".")
    if len(parts) < 3:
        raise ValueError(f"Version string '{version_str}' must have at least three components.")
    major, minor, patch = parts[:3]
    return int(major), int(minor), int(patch)

def create_addon_zip(dev_suffix: str = None, dev_build_timestamp: bool = False):
    """Create a ZIP package of the addon"""
    script_dir = Path(__file__).parent
    addon_dir = script_dir / "mesh_annotation_layers"
    output_dir = script_dir / "dist"
    manifest_path = script_dir / "blender_manifest.toml"
    init_path = addon_dir / "__init__.py"

    output_dir.mkdir(exist_ok=True)

    now = datetime.datetime.now()
    base_version_raw = get_addon_version()
    base_version = base_version_raw
    base_version_clean = normalize_version_base(base_version_raw)
    if dev_build_timestamp or dev_suffix:
        base_version = base_version_clean
    date_str = now.strftime("%Y%m%d")
    manifest_version = base_version
    bl_info_version = None
    build_label = None
    display_version = base_version
    package_label = display_version
    build_state_path = script_dir / ".beta_build_counter"
    build_number = None

    original_manifest = None
    original_init = None

    if dev_build_timestamp:
        major, minor, patch = parse_version_parts(base_version)
        build_number = next_beta_build_number(build_state_path, base_version)
        manifest_version = f"{base_version}-{build_number}"
        if manifest_version == base_version_raw:
            build_number = (build_number % 999) + 1
            manifest_version = f"{base_version}-{build_number}"
        display_version = manifest_version
        package_label = f"{base_version}-beta{build_number}"
        if dev_suffix:
            package_label = f"{package_label}-{dev_suffix}"
        bl_info_version = (major, minor, patch, build_number)
        build_label = f"Beta build #{build_number} {now.strftime('%Y-%m-%d %H:%M:%S')}"
        original_manifest = update_manifest_version(manifest_path, manifest_version)
        original_init = update_bl_info_version(init_path, bl_info_version, build_label=build_label)
    elif dev_suffix:
        manifest_version = f"{base_version}-{dev_suffix}"
        display_version = manifest_version
        package_label = display_version
        major, minor, patch = parse_version_parts(base_version)
        bl_info_version = (major, minor, patch)
        original_manifest = update_manifest_version(manifest_path, manifest_version)
        original_init = update_bl_info_version(init_path, bl_info_version)

    if dev_build_timestamp:
        zip_filename = f"mesh_annotation_layers_v{package_label}.zip"
    else:
        zip_filename = f"mesh_annotation_layers_v{package_label}_{date_str}.zip"
    zip_path = output_dir / zip_filename

    print(f"Creating addon package: {zip_filename}")
    print(f"Manifest version: {manifest_version}")
    if package_label != manifest_version:
        print(f"Package label: {package_label}")
    print()

    addon_files = ["__init__.py"]
    root_files = ["blender_manifest.toml", "LICENSE", "README.md"]
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

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            print("Adding root files:")
            for filename in root_files:
                file_path = script_dir / filename
                if file_path.exists():
                    arcname = f"mesh_annotation_layers/{filename}"
                    zipf.write(file_path, arcname)
                    print(f"  Added: {arcname}")
                else:
                    print(f"  Warning: {filename} not found (required for Blender extensions)")

            print("\nAdding addon code:")
            for filename in addon_files:
                file_path = addon_dir / filename
                if file_path.exists():
                    arcname = f"mesh_annotation_layers/{filename}"
                    zipf.write(file_path, arcname)
                    print(f"  Added: {arcname}")
                else:
                    print(f"  Warning: {filename} not found")

            print("\nAdding documentation:")
            for filename in doc_files:
                file_path = script_dir / filename
                if file_path.exists():
                    arcname = f"mesh_annotation_layers/{filename}"
                    zipf.write(file_path, arcname)
                    print(f"  Added: {arcname}")
    finally:
        if original_manifest is not None:
            manifest_path.write_text(original_manifest, encoding="utf-8")
        if original_init is not None:
            init_path.write_text(original_init, encoding="utf-8")

    if dev_build_timestamp and build_number is not None:
        build_state_path.write_text(f"{base_version} {build_number}", encoding="utf-8")

    size_kb = zip_path.stat().st_size / 1024

    print(f"\n[OK] Package created successfully!")
    print(f"  Location: {zip_path}")
    print(f"  Size: {size_kb:.2f} KB")
    print("\nTo install in Blender:")
    print("  1. Open Blender")
    print("  2. Go to Edit > Preferences > Add-ons")
    print("  3. Click 'Install...'")
    print(f"  4. Select: {zip_path}")
    print("  5. Enable the checkbox next to 'Mesh: Mesh Annotation Layers'")

    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Package Mesh Annotation Layers addon.")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Generate a developer build with an automatic timestamp suffix so Blender recognises it as a new version.",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default=None,
        help="Custom suffix appended to the manifest version (e.g. 'alpha1'). Implies --dev for bl_info build number.",
    )
    args = parser.parse_args()

    if args.suffix and not re.fullmatch(r"[0-9A-Za-z\-\.]+", args.suffix):
        raise SystemExit("Invalid suffix: only alphanumeric characters, hyphen and dot are allowed.")

    create_addon_zip(dev_suffix=args.suffix, dev_build_timestamp=args.dev or bool(args.suffix))


if __name__ == "__main__":
    main()
