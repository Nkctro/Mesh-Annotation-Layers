# Architecture

## Boundaries

Mesh Annotation Layers is a Blender 4.2+ Extension. The complete extension
source is mesh_annotation_layers/: its blender_manifest.toml, __init__.py,
Python modules, and LICENSE are built together by Blender's official CLI.

| Module | Responsibility |
| --- | --- |
| constants.py | Immutable element-type specifications |
| i18n.py | Translation catalog and language resolution |
| model.py | Durable data, BMesh mirror, validation, and transactions |
| evaluated_geometry.py | Source-to-evaluated geometry mapping |
| loops.py | Face/edge/vertex loop and path derivation |
| overlay.py | Dependency handlers, bounded caches, GPU batching, drawing |
| properties.py | Blender RNA property groups |
| operators.py | User actions, write guard, and localized error reporting |
| preferences.py | Add-on preferences |
| ui.py | Sidebar and Edit Mode context menu |
| __init__.py | Hot reload and registration lifecycle |

Dependencies point from Blender-facing operators/UI toward the model. Model
logic is not duplicated in panels or menu callbacks.

## Data ownership

Each Object owns MeshAnnotationSettings. Every element type has:

- a layer collection and active index;
- a monotonic next-ID hint;
- a validated JSON map from element index to ordered layer IDs.
- a compatibility token recording the last agreement among JSON, topology, and
  the BMesh stack.

JSON is the durable per-object source of truth. While editing, each Mesh element
also carries a compact string stack. The BMesh mirror lets assignments follow
topology and Blender Undo/Redo.

Because BMesh custom data belongs to Mesh while JSON belongs to Object, a Mesh
with several users is annotation-read-only. Before a shared mapping is consumed,
its JSON, persisted compatibility token, current topology, and custom-data stack are
validated together. A mismatch quarantines that element type: draw and selection
cannot use the stale indices. **Make Mesh Single User** rebuilds automatically
only for a verified mapping; otherwise the user must explicitly trust current
indices or discard assignments.

The persisted compatibility token is sparse: it hashes global element counts plus only
annotated indices, their current payloads, and their local vertex/connectivity
identity, so normal writes scale with annotation density. Before a shared mapping
is trusted, a read-only full-stack comparison also proves that no untracked,
missing, or damaged payload exists. Explicit single-user reads and writes perform
the same complete reconciliation for correctness.

## Stack encoding and transactions

Blender silently truncates BMesh string values beyond 255 bytes. The 1.3 stack
format contains:

    magic | version | item count | positive unsigned varints | CRC32

Empty and invalid are distinct. A truncated header, unsupported version,
non-positive/duplicate ID, trailing data, or checksum mismatch is invalid and
cannot erase JSON. Malformed, non-object, or lossy JSON is likewise quarantined
instead of being treated as a valid empty mapping. Legacy comma-separated stacks
remain readable; a prefix that matches known longer JSON is treated as historical
truncation.

The complete final mapping is encoded and serialized before BMesh layer creation
or assignment updates. The commit records old BMesh payloads, JSON, cache and
compatibility state and attempts to restore them if a later phase fails. New-layer
operators also restore the collection, active index, and next-ID hint when
assignment fails. A Mesh state that cannot be confirmed as restored loses its
synchronized status and is quarantined instead of being replayed automatically.

## Topology synchronization

Counts alone cannot detect deletion/recreation that leaves the same number of
vertices, edges, and faces. Every explicit model read/write force-checks the
complete stack, so correctness never waits for an asynchronous dependency-graph
event. Geometry updates are still coalesced for 150 ms for background syncing.
The timer commits durable JSON; viewport drawing only consumes a private snapshot
and never writes RNA data.

Undo/Redo invalidates all derived ownership and overlay state so restored BMesh
custom data is read again. load_pre clears every identity-keyed mapping,
signature, geometry, and GPU cache before Blender replaces its ID database.

## Overlay pipeline

    object JSON ownership
      -> sparse source filters
      -> evaluated mesh
      -> source-to-evaluated face/edge/vertex mapping
      -> local-space offsets and edge-chain trimming
      -> per-layer GPU batches
      -> viewport draw

GPU batches, evaluated local geometry, decoded JSON, and usage counts have
separate bounded caches. This allows color/opacity changes and many transforms
to avoid expensive remapping. Dependency entries include the object, mesh, and
modifier pointer dependencies so unrelated scene updates do not dirty a cache.
Only index-preserving and supported Subdivision Surface stacks use evaluated
mapping; Mirror and unknown topology generators fall back to the edit cage.

Interactive modes reuse a still-valid previous batch for a short interval based
on measured build cost and schedule a final redraw. Paint updates reuse geometry
only when visible modifiers cannot consume that painted data.

## Lifecycle

The entry point uses the extension package name and relative imports. On a real
module reload, a registered old runtime is fully unregistered before submodules
are reloaded; normal Blender Reload Scripts has already unregistered it and is
not registered twice.

Registration records each class only after Blender accepts it and unwinds the
completed steps if setup fails. Teardown removes the menu, draw handler,
dependency/history/load handlers, timers, Object property, and classes in
dependency order. Stale handlers/menu callbacks are identified by module and
function name, not only object identity. The Object property check verifies the
RNA pointer's fixed type; teardown never deletes a foreign same-name property.

## Verification focus

Tests cover source contracts plus Blender background behavior:

- registration, external draw-handle removal, disable/enable, and reload;
- face/edge/vertex assignment and overlapping ownership;
- binary round-trip, corruption rejection, capacity preflight, and legacy read;
- shared-Mesh topology quarantine and explicit recovery choices;
- equal-count immediate-write reconciliation, Undo/Redo, and load boundaries;
- cross-element capacity rollback and incomplete-merge cache isolation;
- evaluated geometry, cache scope/reuse, and context/panel draw;
- official manifest validation, build, archive inspection, and archive validation.
