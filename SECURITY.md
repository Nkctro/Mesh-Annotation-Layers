# Security policy

## Supported versions

| Version | Security fixes |
| --- | --- |
| 1.3.x | Supported |
| 1.2.x and older | Unsupported |

Use the latest 1.3 patch release with a Blender version still supported by the
Blender project.

## Scope

Mesh Annotation Layers runs inside Blender with the current user's privileges.
Version 1.3 requests no extension permissions and performs no network access,
external process execution, dynamic code download, clipboard access, or
arbitrary file read/write.

Release archives are produced by Blender's official extension builder from the
mesh_annotation_layers source directory. Do not install untrusted repackaged
archives.

## Reporting a vulnerability

Do not open a public issue for an exploitable vulnerability. Contact the
maintainer at the address in blender_manifest.toml and include:

- affected extension and Blender versions;
- operating system;
- minimal reproduction;
- impact and whether a crafted .blend or archive is required;
- suggested embargo needs.

Non-security crashes, data-integrity bugs, and performance problems can use the
public bug template.
