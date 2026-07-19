#!/usr/bin/env python3
"""Build installable Mesh Annotation Layers archives."""

import argparse
import datetime
import re
import zipfile
from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]


def get_addon_version():
    """Extract version from blender_manifest.toml"""
    manifest_file = ROOT / "blender_manifest.toml"

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
    return re.split(r"[-+]", version_str, maxsplit=1)[0]


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


def create_addon_zip(dev_suffix: str = None, dev_build_timestamp: bool = False):
    """Create a ZIP package of the addon"""
    script_dir = ROOT
    addon_dir = script_dir / "mesh_annotation_layers"
    output_dir = script_dir / "dist"
    manifest_path = script_dir / "blender_manifest.toml"
    output_dir.mkdir(exist_ok=True)

    now = datetime.datetime.now()
    base_version_raw = get_addon_version()
    base_version = base_version_raw
    base_version_clean = normalize_version_base(base_version_raw)
    if dev_build_timestamp or dev_suffix:
        base_version = base_version_clean
    date_str = now.strftime("%Y%m%d")
    manifest_version = base_version
    display_version = base_version
    package_label = display_version
    build_state_path = script_dir / ".beta_build_counter"
    build_number = None

    original_manifest_bytes = None

    if dev_build_timestamp:
        build_number = next_beta_build_number(build_state_path, base_version)
        manifest_version = f"{base_version}-{build_number}"
        if manifest_version == base_version_raw:
            build_number = (build_number % 999) + 1
            manifest_version = f"{base_version}-{build_number}"
        display_version = manifest_version
        package_label = f"{base_version}-beta{build_number}"
        if dev_suffix:
            package_label = f"{package_label}-{dev_suffix}"
        original_manifest_bytes = manifest_path.read_bytes()
    elif dev_suffix:
        manifest_version = f"{base_version}-{dev_suffix}"
        display_version = manifest_version
        package_label = display_version
        original_manifest_bytes = manifest_path.read_bytes()

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

    addon_files = sorted(addon_dir.glob("*.py"))
    root_files = [
        "blender_manifest.toml",
        "LICENSE",
        "README.md",
        "README.zh-CN.md",
    ]
    doc_files = [
        "CHANGELOG.md",
        "SECURITY.md",
        "docs/en/installation.md",
        "docs/en/user-guide.md",
        "docs/en/faq.md",
        "docs/en/development.md",
        "docs/zh-CN/installation.md",
        "docs/zh-CN/user-guide.md",
        "docs/zh-CN/faq.md",
        "docs/zh-CN/development.md",
    ]

    try:
        if original_manifest_bytes is not None:
            update_manifest_version(manifest_path, manifest_version)
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
            for file_path in addon_files:
                if file_path.exists():
                    arcname = f"mesh_annotation_layers/{file_path.name}"
                    zipf.write(file_path, arcname)
                    print(f"  Added: {arcname}")
                else:
                    print(f"  Warning: {file_path.name} not found")

            print("\nAdding documentation:")
            for filename in doc_files:
                file_path = script_dir / filename
                if file_path.exists():
                    arcname = f"mesh_annotation_layers/{filename}"
                    zipf.write(file_path, arcname)
                    print(f"  Added: {arcname}")
    finally:
        if original_manifest_bytes is not None:
            manifest_path.write_bytes(original_manifest_bytes)

    if dev_build_timestamp and build_number is not None:
        build_state_path.write_text(f"{base_version} {build_number}", encoding="utf-8")

    size_kb = zip_path.stat().st_size / 1024

    print(f"\n[OK] Package created successfully!")
    print(f"  Location: {zip_path}")
    print(f"  Size: {size_kb:.2f} KB")
    print("\nTo install in Blender:")
    print("  1. Open Blender")
    print("  2. Go to Edit > Preferences > Get Extensions")
    print("  3. Open the menu and choose 'Install from Disk'")
    print(f"  4. Select: {zip_path}")
    print("  5. Enable Mesh Annotation Layers if necessary")

    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Build Mesh Annotation Layers.")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Generate a developer build with an automatic timestamp suffix so Blender recognises it as a new version.",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default=None,
        help="Custom label appended to an automatically numbered developer package (e.g. 'alpha1').",
    )
    args = parser.parse_args()

    if args.suffix and not re.fullmatch(r"[0-9A-Za-z\-\.]+", args.suffix):
        raise SystemExit("Invalid suffix: only alphanumeric characters, hyphen and dot are allowed.")

    create_addon_zip(dev_suffix=args.suffix, dev_build_timestamp=args.dev or bool(args.suffix))


if __name__ == "__main__":
    main()
