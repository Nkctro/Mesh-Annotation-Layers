# Development

[简体中文](../zh-CN/development.md) · [Project home](../../README.md)

## Design boundaries

The add-on keeps annotation data separate from materials and renders it on Blender's
evaluated mesh. Runtime modules have narrow responsibilities; the package entry point
only coordinates registration and rollback.

```text
mesh_annotation_layers/
├── __init__.py             registration lifecycle
├── constants.py            element-type specifications
├── i18n.py                 language selection and translations
├── model.py                storage, validation, BMesh synchronization
├── evaluated_geometry.py   source-to-evaluated geometry mapping
├── overlay.py              GPU batches, caches, draw handlers
├── loops.py                face/edge/vertex path derivation
├── properties.py           Blender property groups
├── operators.py            user actions and validation
├── preferences.py          add-on preferences
└── ui.py                   panels, lists, and context menus
```

Dependencies should point from Blender-facing UI/operators toward the model. The model
must not import UI code. Drawing invalidation belongs in `overlay.py`.

## Data flow

```text
Edit Mode selection
  → operator validation
  → per-object layer mappings
  → BMesh custom data during editing
  → serialized object data in the .blend file

visible assignments
  → evaluated mesh mapping
  → local display offsets and edge trimming
  → GPU batches
  → cached viewport draw
```

English strings are stable translation keys. Add user-visible English text at the call
site and its Simplified Chinese value in `i18n.py`.

## Setup and checks

No external runtime dependencies are required. Source checks use Python; the smoke test
runs inside Blender.

```bash
python -m compileall -q mesh_annotation_layers tests tools
python tests/test_source_contracts.py
blender --factory-startup --background --python tests/blender_smoke.py --python-exit-code 1
```

The explicit Python exit code matters because Blender may otherwise return success after
an uncaught test assertion.

## Build

```bash
python tools/build.py
python tools/build.py --dev
python tools/build.py --suffix rc1
```

Archives are written to `dist/`. The builder temporarily updates development version
metadata, writes the archive, and restores source files in `finally`.

Before release, keep `blender_manifest.toml` and `bl_info` versions aligned, update the
changelog, run both test layers, inspect the ZIP contents, and install it through Blender's
**Install from Disk** workflow.

## Contribution rules

- Keep `__init__.py` small and transactional.
- Preserve operator IDs unless intentionally introducing a compatibility break.
- Validate malformed stored data at model boundaries, not in UI drawing.
- Add an English translation key and Chinese catalog entry together.
- Include a regression test for behavior changes.
- Avoid unrelated formatting or architectural churn in focused fixes.

Use concise imperative commits such as `Fix edge overlay invalidation`. Pull requests
should explain user impact, test evidence, and any compatibility or performance risk.

## Documentation rule

User-facing docs are paired under `docs/en/` and `docs/zh-CN/`. When behavior changes,
update both files in the same change. README files are navigation and overview pages;
detailed procedures belong in `docs/`.
