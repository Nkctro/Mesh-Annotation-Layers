# Release testing checklist

Record the exact Blender build, OS, GPU, commit, and generated archive hash.

## Automated

- [ ] Python compileall passes.
- [ ] Source-contract unit tests pass.
- [ ] Blender background smoke test passes.
- [ ] Official Blender manifest validation passes.
- [ ] Official Blender extension build passes.
- [ ] Generated ZIP validation passes.
- [ ] ZIP contains __init__.py, blender_manifest.toml, all modules, and full LICENSE.
- [ ] Working tree manifest remains version 1.3.0 after build.

## Lifecycle

- [ ] Enable, disable, and enable again without a traceback.
- [ ] F3 Reload Scripts leaves one draw callback/menu callback and one of each handler.
- [ ] A registered manual importlib reload safely restores registration.
- [ ] A failed registration attempt removes every class/property accepted by
      that attempt.
- [ ] A foreign same-name Object RNA property is rejected and never deleted by
      cleanup.
- [ ] Loading another .blend or factory settings clears derived caches.
- [ ] Undo/Redo restores assignment ownership after topology edits.

## Core workflow

For faces, edges, and vertices:

- [ ] Create, rename, recolor, reorder, show/hide, and remove a layer.
- [ ] Add Selected to the active layer.
- [ ] Add Loop succeeds for an unambiguous seed and refuses an ambiguous seed.
- [ ] Selected/Loop → New Layer creates exactly one layer on success.
- [ ] A failed create-and-assign leaves no empty layer or advanced ID hint.
- [ ] Select Layer and Pick Layer work.
- [ ] Active removal preserves other overlaps.
- [ ] Top removal removes only the highest assignment.
- [ ] All removal clears every assignment.

## Storage integrity

- [ ] Several overlapping layers survive save/reopen.
- [ ] Binary stack IDs around 127/128 and large positive IDs round-trip.
- [ ] A corrupted/truncated stack does not erase valid JSON.
- [ ] A newly created stack leaves unassigned elements empty, while a forced
      rebuild clears stale payloads on every unassigned element.
- [ ] An over-capacity assignment is cancelled with no JSON, BMesh, collection,
      or cache mutation.
- [ ] An over-capacity untouched element cannot cause a different target's
      BMesh payload to change before cancellation.
- [ ] An incomplete merge followed by save failure leaves durable JSON and the
      decoded cache unchanged and is force-inspected again.
- [ ] Delete/recreate topology with unchanged V/E/F counts reconciles after idle.
- [ ] An immediate write after equal-count topology replacement reconciles the
      stack even before a dependency-graph callback runs.
- [ ] Invalid JSON entries are ignored without breaking UI drawing.
- [ ] Malformed, non-object, or lossy non-empty JSON cannot pass shared-state
      verification as an empty mapping.

## Shared Mesh

- [ ] Shared Objects display/select only mappings that match the current
      topology/custom-data proof; unverified Object mappings are quarantined.
- [ ] Layer creation, assignment, clearing, reordering, seam writes, and removal
      are refused while shared.
- [ ] Refused operations do not change either Object or the Mesh.
- [ ] Make Mesh Single User works from Edit Mode and supports Undo.
- [ ] Verified recovery rebuilds from the active Object, not its sibling.
- [ ] Shared equal-count topology replacement blocks automatic recovery and
      cannot make a deleted annotation reappear on a new element.
- [ ] Explicit keep-current-indices and discard-assignment recovery modes behave
      exactly as labelled.
- [ ] Discard recovery clears only unverified element types and preserves other
      independently verified face, edge, or vertex assignments.
- [ ] A single Object with a Fake User can edit annotations; two real Object
      users remain locked even when the Mesh also has a Fake User.
- [ ] Equal-count topology reconciliation still runs for a single Object whose
      Mesh has a Fake User or Extra User.
- [ ] Duplicating an annotated disconnected component while deleting an
      unannotated equal-size component invalidates shared proof because of the
      extra inherited stack payload.
- [ ] Annotation edits work normally after detaching.

## Overlay and performance

- [ ] Overlays display in Edit, Object, Sculpt, Weight Paint, Vertex Paint, and
      Texture Paint modes.
- [ ] Hidden, solo, opacity, through-mesh, thickness, shortening, point size, and
      all three offsets update correctly.
- [ ] Subdivision Surface and Mirror workflows map expected elements.
- [ ] Selection/color changes do not alter layer color semantics.
- [ ] Unrelated scene edits do not rebuild the active overlay.
- [ ] Paint strokes that cannot deform geometry reuse cached geometry.
- [ ] Dense-mesh interaction remains responsive and receives a final idle redraw.
- [ ] GPU state is restored after drawing (Knife/Bisect previews remain normal).

## UI and localization

- [ ] Sidebar follows Edit Mode selection type.
- [ ] Shared-Mesh warning and recovery action are visible.
- [ ] Right-click menu is mode-aware and common actions are one submenu deep.
- [ ] Only choosing another target layer opens a second submenu.
- [ ] Automatic, English, and Chinese modes update labels and tooltips.
- [ ] No missing or unused translation catalog keys remain.

## Final

- [ ] Install the generated ZIP into a clean Blender profile.
- [ ] Save, close, reopen, disable, re-enable, and reload without console errors.
- [ ] README, INSTALL, FAQ, quick reference, changelog, security policy, issue
      templates, and manifest all describe 1.3 behavior.
- [ ] No uncommitted build-time source mutation exists.
