"""Shared, immutable definitions for annotation element types."""

from dataclasses import dataclass


FACE = "FACE"
EDGE = "EDGE"
VERTEX = "VERT"
ELEMENT_TYPES = (FACE, EDGE, VERTEX)


@dataclass(frozen=True, slots=True)
class ElementSpec:
    """All structural metadata needed for one mesh element type."""

    label: str
    selection_label: str
    loop_label: str
    collection: str
    active_index: str
    next_id: str
    data_property: str
    state_property: str
    stack_layer: str
    default_name: str
    icon: str
    select_mode_index: int


ELEMENT_SPECS = {
    FACE: ElementSpec(
        label="Face Layers",
        selection_label="faces",
        loop_label="face loop",
        collection="face_layers",
        active_index="active_face_layer_index",
        next_id="next_face_layer_id",
        data_property="face_layers_data",
        state_property="face_annotation_state",
        stack_layer="_mesh_annotation_face_stack",
        default_name="Face Layer",
        icon="FACESEL",
        select_mode_index=2,
    ),
    EDGE: ElementSpec(
        label="Edge Layers",
        selection_label="edges",
        loop_label="edge loop",
        collection="edge_layers",
        active_index="active_edge_layer_index",
        next_id="next_edge_layer_id",
        data_property="edge_layers_data",
        state_property="edge_annotation_state",
        stack_layer="_mesh_annotation_edge_stack",
        default_name="Edge Layer",
        icon="EDGESEL",
        select_mode_index=1,
    ),
    VERTEX: ElementSpec(
        label="Vertex Layers",
        selection_label="vertices",
        loop_label="vertex path",
        collection="vertex_layers",
        active_index="active_vertex_layer_index",
        next_id="next_vertex_layer_id",
        data_property="vertex_layers_data",
        state_property="vertex_annotation_state",
        stack_layer="_mesh_annotation_vertex_stack",
        default_name="Vertex Layer",
        icon="VERTEXSEL",
        select_mode_index=0,
    ),
}


def element_spec(element_type: str) -> ElementSpec:
    """Return validated metadata and fail clearly for programming errors."""

    try:
        return ELEMENT_SPECS[element_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported mesh element type: {element_type!r}") from exc
