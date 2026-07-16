# Contributing

Contributions are welcome. Target Blender 4.2+ Extension behavior, keep the
package installable without third-party dependencies, and preserve existing
.blend annotation data unless a migration is explicitly designed and tested.

## Before changing code

1. Read [ARCHITECTURE.md](ARCHITECTURE.md).
2. Reproduce the issue with a small mesh and note the Blender version.
3. Check whether the object uses shared Mesh data; annotation mutations are
   intentionally read-only until **Make Mesh Single User** succeeds.
4. Keep unrelated working-tree changes untouched.

## Module ownership

- constants.py: immutable element metadata
- model.py: JSON validation, BMesh stack encoding/synchronization, transactions
- evaluated_geometry.py: source-to-evaluated mapping
- loops.py: face, edge, and vertex loop/path derivation
- overlay.py: handlers, cache policy, GPU batches, and drawing
- properties.py: Blender property groups
- operators.py: user-facing mutations and error reporting
- ui.py: sidebar and Edit Mode context menu
- i18n.py and preferences.py: translations and language preference
- __init__.py: dependency-ordered reload plus registration lifecycle

Do not put feature logic into __init__.py or duplicate model behavior in an
operator or panel.

## Data invariants

- Validated per-object JSON is durable.
- BMesh integer/string layers are edit-history mirrors, not a second independent
  user database.
- Binary stack decoding distinguishes valid empty data from malformed or
  truncated data.
- Any stack that would exceed Blender's 255-byte string layer must fail before
  JSON, BMesh, layer collections, or caches are mutated.
- Shared Mesh data is never reconciled into an Object's JSON and is never
  modified by annotation operators.
- A missing stack is initialized from durable JSON, never treated as proof that
  JSON should be erased.
- Undo/Redo, file loading, registration, and teardown are explicit cache
  boundaries.

## UI and translations

English text is the stable key. Add its Chinese translation to ZH_CN in i18n.py.
Every operator must use LocalizedDescription and define a translated tooltip_key.
Keep the context menu mode-aware and flat; only target-layer choice should need
an additional submenu.

## Required verification

Run before submitting:

    python -m compileall -q mesh_annotation_layers tests

    python -m unittest discover -s tests -p "test_*.py" -v

    blender --background --factory-startup --python tests/blender_smoke.py

    blender --command extension validate mesh_annotation_layers

    blender --command extension build --source-dir mesh_annotation_layers --output-dir dist

    blender --command extension validate path/to/generated.zip

For a storage, lifecycle, or overlay change, also test manually:

- face, edge, and vertex assignment;
- several overlapping layers and active/top/all removal;
- shared Mesh refusal and single-user recovery;
- an equal-count topology replacement followed by Undo/Redo;
- save/reopen;
- disable/enable and F3 Reload Scripts;
- object, edit, sculpt, and paint display modes.

## Pull requests

Describe the failure mode, the invariant restored, and the exact Blender versions
tested. Include before/after measurements for performance changes and screenshots
for visible UI changes. Do not claim support for an untested minimum version;
report validator-only and runtime-tested versions separately.

By contributing, you agree that your contribution is distributed under
GPL-3.0-or-later.
