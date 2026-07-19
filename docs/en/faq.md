# Frequently asked questions

[简体中文](../zh-CN/faq.md) · [Project home](../../README.md)

## Does the add-on modify my materials or vertex colors?

No. It stores annotation ownership separately and draws viewport overlays.

## Where is annotation data stored?

Per object, inside the `.blend` file. Face, edge, and vertex layers are independent.

## Why can I see annotations but cannot edit them?

Assignments are edited in Edit Mode. Other supported modes are display-oriented.

## Why is the panel missing?

Select a mesh object, open the 3D View sidebar with `N`, and confirm that the extension
is enabled. The tab is named **Mesh Annotation**.

## Why is an overlay invisible?

Check the global overlay switch, the layer eye icon, solo mode, and global opacity.
Also confirm the active element type matches the layer stack you expect.

## Can one element belong to multiple layers?

Yes. Assignments are ordered, and cleanup tools can remove the top assignment or all
assignments from selected elements.

## Does it work with modifiers?

The overlay pipeline uses Blender's evaluated mesh for supported workflows, including
Subdivision Surface and Mirror handling. Complex modifier combinations can be more
expensive and should be verified on the target model.

## Can it create UV seams?

Yes. Face-layer boundaries can be marked as seams for the active layer or all face layers.

## Can I annotate several objects at once?

Layer editing targets the active mesh object. Repeat the operation for each object.

## Does it affect rendering or exported geometry?

The viewport overlay is not a render material and does not change exported geometry.
Custom annotation data is only useful to tools that explicitly understand it.

## Is there a performance limit?

There is no fixed layer count limit, but more visible annotations and denser evaluated
meshes require more CPU/GPU work. Hide unused layers when needed.

## How should I report a problem?

Open a GitHub issue with Blender version, add-on version, operating system, reproduction
steps, modifier stack, and the full console traceback when available.
