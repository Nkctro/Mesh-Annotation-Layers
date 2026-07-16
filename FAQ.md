# FAQ

简体中文综合用户指南：[README.zh-CN.md](README.zh-CN.md)

## Which Blender versions are supported?

The manifest requires Blender 4.2 or newer. Release validation should always
state which versions were actually run, rather than treating a manifest check as
a runtime test.

## Where is the interface?

Select a Mesh object and open the **Mesh Annotation** tab in the 3D View sidebar.
Create and change assignments in Edit Mode. Existing overlays remain visible in
Object, Sculpt, Weight Paint, Vertex Paint, and Texture Paint modes.

## Why are annotation controls locked?

The active Mesh has more than one Object user. Durable annotations belong to
each Object, but the topology-following edit stack belongs to the Mesh. Editing
that shared stack could mix the two Objects' labels.

Click **Make Mesh Single User**. Automatic recovery proceeds only when the
Object's JSON is proven to match the current topology and custom-data stack. If
shared topology changed, the dialog requires an explicit choice: trust the
current element indices or discard stale assignments. The operation supports
Undo and never silently turns an unverified index into a permanent label.
Proof also requires lossless JSON decoding and rejects any extra non-empty stack
payload that is not owned by the Object mapping.
Older files that were already shared before the proof token existed are also
treated as unverified; this is intentional because their topology history
cannot be reconstructed safely.

## Can one element belong to several layers?

Yes. Assigning another layer adds ownership instead of replacing existing
ownership. The highest visible layer in the current layer order is drawn.
Removing from the active layer reveals lower visible assignments.

## What do active, top, and all removal mean?

- Active removes only the chosen active layer.
- Top removes the highest layer in the current order.
- All removes every annotation from the selected elements.

The primary sidebar action uses Active so it does not accidentally erase other
labels.

## How do I select or identify a layer?

**Select Layer** selects all elements assigned to the active layer. **Pick
Layer** examines the current selection and activates the layer with the highest
usage count.

## How are loops detected?

Select enough faces, edges, or vertices to disambiguate a continuous loop/path,
then use **Add Loop**. Ambiguous, disconnected, or insufficient selections are
rejected with a message instead of guessing.

## Can face layers become UV seams?

Yes. In the Faces workspace, use **Mark Seams (Layer)** or **Mark Seams (All)**.
Only boundary edges are marked. Edge annotation layers are visual planning data
and are not converted by those face-boundary tools.

## Why was an overlap assignment refused?

Blender BMesh string custom layers have a 255-byte value limit. Version 1.3 uses
a compact checksummed binary stack and preflights every write. If one element
still has too many overlapping layer IDs, the operation is cancelled without
partial changes. Remove unnecessary overlap before adding more.

## What happens to annotations after topology edits?

The BMesh mirror follows mesh elements through Blender edit history. Geometry
updates are coalesced briefly, then reconciled into durable JSON by a timer;
viewport drawing itself is read-only. Explicit Select/Pick/write actions always
force a complete stack check first, including in the same call flow before a
dependency-graph update arrives. Undo/Redo clears derived caches and restores
ownership from the history state.

For shared Mesh data, native Blender topology tools can still change the Mesh
even though annotation writes are locked. A topology/custom-data mismatch
quarantines the affected Object mapping: it is not drawn, selected, or used by
automatic single-user recovery until the user resolves it.

## Why can the first overlay update lag slightly during active editing?

Topology, coordinate, and selection updates can share the same dependency-graph
signal. The extension debounces reconciliation for 150 ms to avoid a full stack
scan on every event and schedules a final redraw after interaction stops.

## Do modifiers work?

The overlay is drawn on evaluated geometry and has dedicated mapping paths for
common Subdivision Surface and Mirror workflows. Unusual topology-generating
modifier stacks should be tested on the target Blender version.

## How do I change language?

Open **Edit > Preferences > Add-ons > Mesh Annotation Layers**. Choose Automatic,
English, or Chinese. Automatic uses Chinese for supported Chinese locales and
English otherwise.

## How do I develop or reload the extension?

Use a dedicated local extension repository and link the
mesh_annotation_layers source directory into it. Then use **F3 > Reload
Scripts** after edits. See [INSTALL.md](INSTALL.md); do not copy source into
Blender's managed user_default directory.

## How is a release built?

Only Blender's official extension commands are used:

    blender --command extension validate mesh_annotation_layers

    blender --command extension build --source-dir mesh_annotation_layers --output-dir dist

Install and validate the generated archive before release.

## Is commercial use allowed?

Yes, under GPL-3.0-or-later. Distribution and modification must comply with that
license; the complete text is in [LICENSE](LICENSE).
