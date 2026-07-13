#!/usr/bin/env python3
"""
Build a beta package of Mesh Annotation Layers.

Manifest version gets a short incremental build tag (max three digits),
while the archive name keeps a timestamped suffix for easy identification.
"""

from package import create_addon_zip


def main():
    create_addon_zip(dev_build_timestamp=True)


if __name__ == "__main__":
    main()
