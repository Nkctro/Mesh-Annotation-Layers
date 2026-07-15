# Mesh Annotation Layers architecture

## Design goals

The add-on keeps annotation data independent from materials and renders it on the
modifier-evaluated surface. The implementation is organized around three rules:

1. Feature modules own one responsibility.
2. Dependencies point from Blender-facing code toward the data model, never back
   from the model into the UI.
3. Expensive evaluated geometry is rebuilt only when geometry or display inputs
   actually change.

## Package layout

| Module | Responsibility |
| --- | --- |
| `__init__.py` | Transactional registration and unregistration |
| `constants.py` | Immutable element-type specifications |
| `i18n.py` | Language selection, translation catalog, safe formatting |
| `model.py` | Layer storage, JSON validation, BMesh synchronization, assignments |
| `evaluated_geometry.py` | Source-to-evaluated geometry mapping and edge-chain trimming |
| `overlay.py` | GPU batches, cache policy, drawing, and handler lifecycle |
| `loops.py` | Face-loop, edge-loop, and vertex-path derivation |
| `properties.py` | Blender property groups and display defaults |
| `operators.py` | User actions and validation |
| `ui.py` | Context menus, layer list, and sidebar panels |

The entry point contains no feature logic. Registration order is explicit:
preferences, property groups, operators, then UI classes. If any step fails, all
already-registered state is removed before the exception is re-raised.

## Data model

Each mesh object owns a `MeshAnnotationSettings` pointer. Faces, edges, and
vertices have separate layer collections, active indices, ID counters, and
serialized index-to-layer mappings.

The serialized JSON mapping is the durable source of truth:

```text
element index -> ordered list of layer IDs
```

BMesh integer and string custom-data layers mirror that state while editing so
topology operations can carry assignments with mesh elements. Input JSON is
validated field by field; malformed keys and layer IDs are ignored instead of
breaking operators or panel drawing.

## Overlay pipeline

```text
source annotations
    -> sparse source index filters
    -> evaluated mesh from Blender dependency graph
    -> source-to-evaluated face/edge/vertex mapping
    -> offset and whole-edge trimming
    -> one GPU batch per element kind/layer
    -> cached viewport draw
```

Subdivision Surface and Mirror are handled on evaluated geometry. Vertex
positions are derived from topology-aware edge-chain intersections, avoiding
assumptions about evaluated vertex ordering. Edge shortening applies to the two
ends of a complete source-edge chain, not to every subdivision segment.

## Cache policy

The runtime uses bounded, weighted caches keyed by Blender object or settings
identity. Decoded annotation mappings, usage counts, local evaluated geometry,
and GPU batches have separate lifetimes so a style-only change does not force
source-to-evaluated remapping.

- Normal redraws reuse existing GPU batches without rescanning modifier RNA.
- Dependency-graph updates dirty only caches that depend on the updated Blender ID.
- Face, point, and default edge batches stay in local coordinates, so ordinary
  object transforms are applied at draw time.
- Mapping fallbacks calculate only the annotated element kinds and source
  neighbourhoods required by the current overlay.
- Coordinate edits use a build-cost-aware interval to bound main-thread work.
- Vertex/texture paint data updates reuse geometry when paint cannot deform it.
- Weight paint reuses geometry only when no visible modifier consumes weights.
- A timer schedules the final redraw after throttled interaction.

Cache ownership and dependency-graph handlers live entirely in `overlay.py`.

## Localization

English messages are stable keys in `i18n.py`; Chinese translations exist only
in the central `ZH_CN` catalog. Other modules call:

```python
tr("Marked {count} edges", count=count)
```

The formatter tolerates a malformed or incomplete translation and falls back
without crashing Blender UI drawing. Dynamic element and mode labels are also
resolved through catalog keys rather than carrying language pairs.

Language preferences use the complete Python package name so Blender extension
namespaces resolve correctly. Automatic mode maps supported Chinese locales to
Chinese and every other locale to English. Operator hover text is resolved at
hover time through `LocalizedDescription`, so manual language changes apply
immediately without re-registering Blender classes.

## Extension boundaries

- Add a mesh element type by extending `ElementSpec` and then implementing its
  model, overlay, operator, and UI behavior.
- Add a user-visible message only in English at the call site and add its Chinese
  value to `ZH_CN`.
- Add a new drawing invalidation source inside `overlay.py`; UI/property modules
  should only request `tag_view3d_redraw()`.
- Keep Blender operator IDs stable unless the interaction itself is intentionally
  redesigned.

## Verification

Release validation covers:

- Python syntax compilation for every module;
- Blender background registration/unregistration;
- face, edge, and vertex assignment round trips;
- evaluated Subdivision Surface overlay generation;
- cache reuse and paint-mode invalidation behavior;
- archive contents and clean installation from the generated ZIP.
