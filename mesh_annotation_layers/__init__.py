bl_info = {
    "name": "Mesh Annotation Layers",
    "author": "Nkctro",
    "version": (1, 1, 1),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Sidebar > Mesh Annotation",
    "description": "Annotate selected mesh elements with named color layers without altering materials",
    "category": "3D View",
    "doc_url": "https://github.com/Nkctro/Mesh-Annotation-Layers",
    "tracker_url": "https://github.com/Nkctro/Mesh-Annotation-Layers/issues",
}

import bpy
import bmesh
import colorsys
import json
import random
from collections import Counter, defaultdict
from mathutils import Vector
import gpu
from gpu_extras.batch import batch_for_shader


ELEMENT_FACE = "FACE"
ELEMENT_EDGE = "EDGE"
ELEMENT_VERTEX = "VERT"
ELEMENT_TYPES = (ELEMENT_FACE, ELEMENT_EDGE, ELEMENT_VERTEX)

ELEMENT_DEFS = {
    ELEMENT_FACE: {
        "label": ("Face Layers", "面图层"),
        "selection_label": ("faces", "面"),
        "loop_label": ("face loop", "面循环"),
        "collection": "face_layers",
        "active_index": "active_face_layer_index",
        "next_id": "next_face_layer_id",
        "data_prop": "face_layers_data",
        "int_layer": "_mesh_annotation_face",
        "stack_layer": "_mesh_annotation_face_stack",
        "color_seed": "color_seed_face",
        "default_name": "Face Layer",
        "icon": "FACESEL",
        "select_mode_index": 2,
    },
    ELEMENT_EDGE: {
        "label": ("Edge Layers", "边图层"),
        "selection_label": ("edges", "边"),
        "loop_label": ("edge loop", "边循环"),
        "collection": "edge_layers",
        "active_index": "active_edge_layer_index",
        "next_id": "next_edge_layer_id",
        "data_prop": "edge_layers_data",
        "int_layer": "_mesh_annotation_edge",
        "stack_layer": "_mesh_annotation_edge_stack",
        "color_seed": "color_seed_edge",
        "default_name": "Edge Layer",
        "icon": "EDGESEL",
        "select_mode_index": 1,
    },
    ELEMENT_VERTEX: {
        "label": ("Vertex Layers", "点图层"),
        "selection_label": ("vertices", "点"),
        "loop_label": ("vertex path", "点循环"),
        "collection": "vertex_layers",
        "active_index": "active_vertex_layer_index",
        "next_id": "next_vertex_layer_id",
        "data_prop": "vertex_layers_data",
        "int_layer": "_mesh_annotation_vertex",
        "stack_layer": "_mesh_annotation_vertex_stack",
        "color_seed": "color_seed_vertex",
        "default_name": "Vertex Layer",
        "icon": "VERTEXSEL",
        "select_mode_index": 0,
    },
}

EDGE_DRAW_OFFSET = 0.0008
_draw_handle = None


def get_addon_prefs():
    try:
        prefs = bpy.context.preferences
    except AttributeError:
        return None
    if not prefs:
        return None
    addon = prefs.addons.get(__name__)
    if addon:
        return addon.preferences
    return None


def resolve_language_mode():
    prefs = get_addon_prefs()
    mode = getattr(prefs, "language_display", "AUTO") if prefs else "AUTO"
    if mode == "BOTH":
        return "BOTH"
    if mode == "EN":
        return "EN"
    if mode == "ZH":
        return "ZH"
    try:
        lang = bpy.context.preferences.view.language
    except AttributeError:
        lang = ""
    if not lang or lang in {"DEFAULT", "AUTO"}:
        lang = getattr(getattr(bpy.app, "translations", None), "locale", "") or ""
    lang = (lang or "").lower()
    if lang.startswith("zh"):
        return "ZH"
    return "EN"


def bi(en: str, zh: str) -> str:
    mode = resolve_language_mode()
    if mode == "ZH":
        return zh
    if mode == "BOTH":
        return f"{en} / {zh}"
    return en


class MeshAnnotationPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    language_display: bpy.props.EnumProperty(
        name="Language",
        items=(
            ("AUTO", "Auto", "Follow Blender interface language"),
            ("EN", "English", "Always show English labels"),
            ("ZH", "中文", "始终显示中文"),
            ("BOTH", "Both", "Show both English and Chinese text"),
        ),
        default="AUTO",
    )

    context_menu_split_types: bpy.props.BoolProperty(
        name="Type Selection Submenu",
        description=(
            "Enable to show an extra submenu for choosing Faces/Edges/Vertices. "
            "Disable for quicker access with direct actions."
        ),
        default=True,
    )

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "language_display", text=bi("Language", "语言"))
        layout.label(text=bi("Auto follows Blender's interface language.", "自动模式会同步 Blender 的界面语言"))
        layout.prop(self, "context_menu_split_types", text=bi("Type Selection Submenu", "右键添加类型子菜单"))

def tag_view3d_redraw(context=None):
    context = context or bpy.context
    wm = context.window_manager if context else None
    if wm is None:
        return
    for window in wm.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def log_debug_from_settings(settings, *message):
    if settings and getattr(settings, "debug_output", False):
        print("[MeshAnnotation]", *message)


def element_meta(element_type: str):
    return ELEMENT_DEFS[element_type]


def get_layer_collection(settings, element_type: str):
    return getattr(settings, element_meta(element_type)["collection"])


def layer_order_map(settings, element_type: str):
    if not settings:
        return {}
    collection = get_layer_collection(settings, element_type)
    return {layer.layer_id: index for index, layer in enumerate(collection)}


def normalize_layer_ids(layers, order_lookup=None):
    unique = []
    seen = set()
    for lid in layers:
        lid = int(lid)
        if lid in seen:
            continue
        seen.add(lid)
        unique.append(lid)
    if order_lookup:
        unique.sort(key=lambda value: order_lookup.get(value, float("inf")))
    return unique


def apply_layer_order_to_mapping(obj: bpy.types.Object, element_type: str) -> bool:
    settings = getattr(obj, "mesh_annotations", None)
    if settings is None:
        return False
    mapping = load_element_layers(settings, element_type)
    if not mapping:
        return False
    order_lookup = layer_order_map(settings, element_type)
    changed = False
    for key, layers in list(mapping.items()):
        normalized = normalize_layer_ids(layers, order_lookup)
        if normalized != layers:
            mapping[key] = normalized
            changed = True
    if not changed:
        return False
    mesh = obj.data
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
        ensure_lookup_tables(bm, element_type)
        sync_mapping_to_bmesh(bm, int_layer, stack_layer, mapping, element_type)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    else:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
        ensure_lookup_tables(bm, element_type)
        sync_mapping_to_bmesh(bm, int_layer, stack_layer, mapping, element_type)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()
    save_element_layers(settings, element_type, mapping)
    return True


def get_active_index(settings, element_type: str) -> int:
    return getattr(settings, element_meta(element_type)["active_index"])


def set_active_index(settings, element_type: str, value: int):
    setattr(settings, element_meta(element_type)["active_index"], value)


def get_next_layer_id(settings, element_type: str) -> int:
    return getattr(settings, element_meta(element_type)["next_id"])


def increment_next_layer_id(settings, element_type: str):
    attr = element_meta(element_type)["next_id"]
    setattr(settings, attr, getattr(settings, attr) + 1)


def data_prop_name(element_type: str) -> str:
    return element_meta(element_type)["data_prop"]


def color_seed_name(element_type: str) -> str:
    return element_meta(element_type)["color_seed"]


def ensure_lookup_tables(bm: bmesh.types.BMesh, element_type: str):
    if element_type == ELEMENT_FACE:
        bm.faces.ensure_lookup_table()
    elif element_type == ELEMENT_EDGE:
        bm.edges.ensure_lookup_table()
    else:
        bm.verts.ensure_lookup_table()


def element_container(bm: bmesh.types.BMesh, element_type: str):
    if element_type == ELEMENT_FACE:
        return bm.faces
    if element_type == ELEMENT_EDGE:
        return bm.edges
    return bm.verts


def load_element_layers(settings, element_type: str):
    if settings is None:
        return {}
    data_str = getattr(settings, data_prop_name(element_type), "")
    if not data_str:
        return {}
    try:
        raw = json.loads(data_str)
        if isinstance(raw, dict):
            return {str(k): [int(v) for v in values] for k, values in raw.items()}
    except Exception:
        pass
    return {}


def save_element_layers(settings, element_type: str, mapping):
    if settings is None:
        return
    cleaned = {str(k): [int(v) for v in values] for k, values in mapping.items() if values}
    setattr(settings, data_prop_name(element_type), json.dumps(cleaned))


def get_layers_for_index(mapping, element_index: int):
    return list(mapping.get(str(element_index), []))


def set_layers_for_index(mapping, element_index: int, layers):
    key = str(element_index)
    if layers:
        mapping[key] = [int(v) for v in layers]
    elif key in mapping:
        del mapping[key]


def prune_mapping_to_indices(mapping, valid_indices):
    removed = False
    valid = set(valid_indices)
    for key in list(mapping.keys()):
        if int(key) not in valid:
            del mapping[key]
            removed = True
    return removed


def ensure_annotation_layers(bm: bmesh.types.BMesh, element_type: str):
    container = element_container(bm, element_type)
    meta = element_meta(element_type)
    layer_name = meta["int_layer"]
    stack_name = meta["stack_layer"]
    int_layer = container.layers.int.get(layer_name)
    if int_layer is None:
        int_layer = container.layers.int.new(layer_name)
        for elem in container:
            elem[int_layer] = -1
    stack_layer = container.layers.string.get(stack_name)
    if stack_layer is None:
        stack_layer = container.layers.string.new(stack_name)
        for elem in container:
            elem[stack_layer] = b""
    return int_layer, stack_layer


def decode_layer_bytes(data):
    if isinstance(data, bytes):
        data = data.decode("utf-8", "ignore")
    if not data:
        return []
    return [int(v) for v in data.split(",") if v.strip().isdigit()]


def encode_layers(layers):
    if not layers:
        return b""
    text = ",".join(str(v) for v in layers)
    return text.encode("utf-8")[:255]


def merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type: str):
    container = element_container(bm, element_type)
    changed = False
    for elem in container:
        data = elem[stack_layer]
        layers = decode_layer_bytes(data)
        if layers:
            mapping[str(elem.index)] = [int(v) for v in layers]
            changed = True
    return changed


def get_viewport_size():
    context = bpy.context
    region = getattr(context, "region", None)
    if region and region.type == "WINDOW":
        return float(region.width), float(region.height)
    wm = context.window_manager if context else None
    if wm:
        for window in wm.windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for reg in area.regions:
                    if reg.type == "WINDOW":
                        return float(reg.width), float(reg.height)
    return 1920.0, 1080.0


def sync_mapping_to_bmesh(bm, int_layer, stack_layer, mapping, element_type: str):
    container = element_container(bm, element_type)
    for elem in container:
        layers = mapping.get(str(elem.index), [])
        elem[int_layer] = layers[-1] if layers else -1
        elem[stack_layer] = encode_layers(layers)

def auto_generate_color(settings, element_type: str, existing_colors=None):
    seed_attr = color_seed_name(element_type)
    setattr(settings, seed_attr, random.random())
    if existing_colors is None:
        collection = get_layer_collection(settings, element_type) if settings else []
        existing_colors = [tuple(layer.color[:3]) for layer in collection]
    best_color = None
    best_score = -1.0
    for _ in range(16):
        hue = random.random()
        saturation = 0.65
        value = 1.0
        candidate = colorsys.hsv_to_rgb(hue, saturation, value)
        if not existing_colors:
            best_color = candidate
            break
        score = min(
            ((candidate[0] - col[0]) ** 2 + (candidate[1] - col[1]) ** 2 + (candidate[2] - col[2]) ** 2) ** 0.5
            for col in existing_colors
        )
        if score > best_score:
            best_score = score
            best_color = candidate
    if best_color is None:
        best_color = colorsys.hsv_to_rgb(random.random(), 0.65, 1.0)
    r, g, b = best_color
    alpha = 0.45 if element_type == ELEMENT_FACE else 1.0
    return (r, g, b, alpha)


def get_mesh_sequence(obj, element_type: str):
    if element_type == ELEMENT_FACE:
        return obj.data.polygons
    if element_type == ELEMENT_EDGE:
        return obj.data.edges
    return obj.data.vertices


def assign_elements_to_layer(obj: bpy.types.Object, element_type: str, layer_id: int, element_indices=None):
    mesh = obj.data
    settings = getattr(obj, "mesh_annotations", None)
    mapping = load_element_layers(settings, element_type)
    log_debug_from_settings(settings, f"Assign elements start: type={element_type}, layer_id={layer_id}, indices={element_indices}")
    order_lookup = layer_order_map(settings, element_type)
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
        ensure_lookup_tables(bm, element_type)
        container = element_container(bm, element_type)
        valid_indices = {elem.index for elem in container}
        if prune_mapping_to_indices(mapping, valid_indices):
            save_element_layers(settings, element_type, mapping)
        merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type)
        if element_indices is None:
            targets = [elem for elem in container if elem.select]
        else:
            targets = [container[i] for i in element_indices if i < len(container)]
        if not targets:
            log_debug_from_settings(settings, "Assign aborted: no selection in edit mode")
            return False
        for elem in targets:
            idx = elem.index
            layers = normalize_layer_ids(get_layers_for_index(mapping, idx), order_lookup)
            if layer_id in layers:
                layers.remove(layer_id)
            layers.append(layer_id)
            layers = normalize_layer_ids(layers, order_lookup)
            set_layers_for_index(mapping, idx, layers)
        sync_mapping_to_bmesh(bm, int_layer, stack_layer, mapping, element_type)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        save_element_layers(settings, element_type, mapping)
        log_debug_from_settings(settings, f"Assign edit success: {len(targets)} elements")
        return True
    bm = bmesh.new()
    bm.from_mesh(mesh)
    int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    valid_indices = {elem.index for elem in container}
    if prune_mapping_to_indices(mapping, valid_indices):
        save_element_layers(settings, element_type, mapping)
    merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type)
    if element_indices is None:
        element_indices = list(valid_indices)
    element_indices = [idx for idx in element_indices if idx in valid_indices]
    if not element_indices:
        bm.free()
        log_debug_from_settings(settings, "Assign aborted: no indices in object mode")
        return False
    for idx in element_indices:
        layers = normalize_layer_ids(get_layers_for_index(mapping, idx), order_lookup)
        if layer_id in layers:
            layers.remove(layer_id)
        layers.append(layer_id)
        layers = normalize_layer_ids(layers, order_lookup)
        set_layers_for_index(mapping, idx, layers)
    sync_mapping_to_bmesh(bm, int_layer, stack_layer, mapping, element_type)
    bm.to_mesh(mesh)
    mesh.update()
    save_element_layers(settings, element_type, mapping)
    bm.free()
    log_debug_from_settings(settings, f"Assign object success: {len(element_indices)} elements")
    return True

def clear_elements_from_layer(obj: bpy.types.Object, element_type: str, layer_id: int, only_selected: bool, mode: str = "ALL"):
    mesh = obj.data
    settings = getattr(obj, "mesh_annotations", None)
    mapping = load_element_layers(settings, element_type)
    order_lookup = layer_order_map(settings, element_type)
    log_debug_from_settings(
        settings,
        f"Clear elements: type={element_type}, layer_id={layer_id}, only_selected={only_selected}, mode={mode}",
    )
    if obj.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
        ensure_lookup_tables(bm, element_type)
        container = element_container(bm, element_type)
        valid_indices = {elem.index for elem in container}
        if prune_mapping_to_indices(mapping, valid_indices):
            save_element_layers(settings, element_type, mapping)
        merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type)
        targets = container if not only_selected else [elem for elem in container if elem.select]
        changed = False
        for elem in targets:
            idx = elem.index
            layers = normalize_layer_ids(get_layers_for_index(mapping, idx), order_lookup)
            if layer_id == -1:
                if mode == "TOP":
                    if layers:
                        layers = layers[:-1]
                        changed = True
                else:
                    if layers:
                        layers = []
                        changed = True
            elif layer_id in layers:
                new_layers = [l for l in layers if l != layer_id]
                if new_layers != layers:
                    layers = new_layers
                    changed = True
            if mode == "TOP" and layer_id != -1:
                # remove first occurrence matching layer_id only once
                if layer_id in layers:
                    layers.remove(layer_id)
                    changed = True
            layers = normalize_layer_ids(layers, order_lookup)
            set_layers_for_index(mapping, idx, layers)
        if changed:
            sync_mapping_to_bmesh(bm, int_layer, stack_layer, mapping, element_type)
            save_element_layers(settings, element_type, mapping)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        log_debug_from_settings(settings, f"Clear edit processed {len(targets)} elements (changed={changed})")
        return
    bm = bmesh.new()
    bm.from_mesh(mesh)
    int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    valid_indices = {elem.index for elem in container}
    if prune_mapping_to_indices(mapping, valid_indices):
        save_element_layers(settings, element_type, mapping)
    merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type)
    changed = False
    for elem in container:
        idx = elem.index
        layers = normalize_layer_ids(get_layers_for_index(mapping, idx), order_lookup)
        if layer_id == -1:
            if mode == "TOP":
                if layers:
                    layers = layers[:-1]
                    changed = True
            else:
                if layers:
                    layers = []
                    changed = True
        elif layer_id in layers:
            new_layers = [l for l in layers if l != layer_id]
            if new_layers != layers:
                layers = new_layers
                changed = True
        if mode == "TOP" and layer_id != -1 and layer_id in layers:
            layers.remove(layer_id)
            changed = True
        layers = normalize_layer_ids(layers, order_lookup)
        set_layers_for_index(mapping, idx, layers)
    if changed:
        sync_mapping_to_bmesh(bm, int_layer, stack_layer, mapping, element_type)
        bm.to_mesh(mesh)
        mesh.update()
        save_element_layers(settings, element_type, mapping)
    bm.free()
    log_debug_from_settings(settings, f"Clear object complete for layer {layer_id} (changed={changed})")


def count_elements_for_layer(obj: bpy.types.Object, element_type: str, layer_id: int) -> int:
    settings = getattr(obj, "mesh_annotations", None)
    mapping = load_element_layers(settings, element_type)
    sequence = get_mesh_sequence(obj, element_type)
    valid = {elem.index for elem in sequence}
    return sum(1 for key, layers in mapping.items() if int(key) in valid and layer_id in layers)


def collect_element_indices_for_layer(obj: bpy.types.Object, element_type: str, layer_id: int):
    settings = getattr(obj, "mesh_annotations", None)
    mapping = load_element_layers(settings, element_type)
    sequence = get_mesh_sequence(obj, element_type)
    valid = {elem.index for elem in sequence}
    return [int(idx) for idx, layers in mapping.items() if int(idx) in valid and layer_id in layers]


def select_elements_for_layer(obj: bpy.types.Object, element_type: str, layer_id: int) -> int:
    if obj.mode != "EDIT":
        return 0
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
    ensure_lookup_tables(bm, element_type)
    container = element_container(bm, element_type)
    settings = obj.mesh_annotations
    mapping = load_element_layers(settings, element_type)
    merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type)
    target_indices = {int(idx) for idx, layers in mapping.items() if layer_id in layers}
    selected = 0
    for elem in container:
        is_in_layer = elem.index in target_indices
        elem.select = is_in_layer
        if is_in_layer:
            selected += 1
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    log_debug_from_settings(settings, f"Select elements: type={element_type}, count={selected}")
    return selected


def mark_face_layer_edges_as_seam(obj: bpy.types.Object, layer_ids) -> int:
    if obj.mode != "EDIT":
        return 0
    mesh = obj.data
    settings = getattr(obj, "mesh_annotations", None)
    if settings is None:
        return 0
    target_layers = {int(lid) for lid in layer_ids if lid is not None}
    if not target_layers:
        return 0
    bm = bmesh.from_edit_mesh(mesh)
    int_layer, stack_layer = ensure_annotation_layers(bm, ELEMENT_FACE)
    ensure_lookup_tables(bm, ELEMENT_FACE)
    ensure_lookup_tables(bm, ELEMENT_EDGE)
    mapping = load_element_layers(settings, ELEMENT_FACE)
    merge_stack_layer_into_mapping(mapping, bm, stack_layer, ELEMENT_FACE)
    order_lookup = layer_order_map(settings, ELEMENT_FACE)
    face_layers_map = {}
    for face in bm.faces:
        layers = normalize_layer_ids(get_layers_for_index(mapping, face.index), order_lookup)
        if not layers and face[int_layer] >= 0:
            layers = normalize_layer_ids([face[int_layer]], order_lookup)
        face_layers_map[face.index] = layers
    edges_to_mark = set()
    for lid in target_layers:
        layer_faces = {idx for idx, layers in face_layers_map.items() if lid in layers}
        if not layer_faces:
            continue
        for face in bm.faces:
            if face.index not in layer_faces:
                continue
            for edge in face.edges:
                adjacent = {link_face.index for link_face in edge.link_faces}
                if len(adjacent) < 2:
                    edges_to_mark.add(edge)
                    continue
                if any(idx not in layer_faces for idx in adjacent):
                    edges_to_mark.add(edge)
    changed = 0
    for edge in edges_to_mark:
        if not edge.seam:
            edge.seam = True
            changed += 1
    if changed:
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    return changed


def get_layer_by_id(settings, element_type: str, layer_id: int):
    collection = get_layer_collection(settings, element_type)
    for layer in collection:
        if layer.layer_id == layer_id:
            return layer
    return None


def active_layer(settings, element_type: str):
    collection = get_layer_collection(settings, element_type)
    idx = get_active_index(settings, element_type)
    if 0 <= idx < len(collection):
        return collection[idx]
    return None


def create_layer(settings, element_type: str, name=None, color=None):
    collection = get_layer_collection(settings, element_type)
    meta = element_meta(element_type)
    existing_colors = [tuple(layer.color[:3]) for layer in collection]
    generated_color = color or auto_generate_color(settings, element_type, existing_colors=existing_colors)
    layer = collection.add()
    layer.element_type = element_type
    layer.layer_id = get_next_layer_id(settings, element_type)
    increment_next_layer_id(settings, element_type)
    layer.name = name or f"{meta['default_name']} {layer.layer_id}"
    layer.color = generated_color
    set_active_index(settings, element_type, len(collection) - 1)
    return layer


def remove_layer(settings, obj, element_type: str, index: int):
    collection = get_layer_collection(settings, element_type)
    if not (0 <= index < len(collection)):
        return
    layer = collection[index]
    clear_elements_from_layer(obj, element_type, layer.layer_id, only_selected=False, mode="ALL")
    collection.remove(index)
    new_index = min(index, len(collection) - 1)
    set_active_index(settings, element_type, new_index)


def collect_layer_usage_from_selection(obj, element_type: str):
    if obj.mode != "EDIT":
        return Counter()
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    settings = obj.mesh_annotations
    _int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
    ensure_lookup_tables(bm, element_type)
    mapping = load_element_layers(settings, element_type)
    merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type)
    container = element_container(bm, element_type)
    usage = Counter()
    order_lookup = layer_order_map(settings, element_type)
    for elem in container:
        if elem.select:
            for lid in normalize_layer_ids(get_layers_for_index(mapping, elem.index), order_lookup):
                usage[lid] += 1
    return usage

def infer_element_type_from_mode(context) -> str:
    try:
        mode = context.tool_settings.mesh_select_mode
    except AttributeError:
        mode = (False, False, False)
    for element_type, index in sorted(
        ((etype, element_meta(etype)["select_mode_index"]) for etype in ELEMENT_TYPES),
        key=lambda item: item[1],
        reverse=True,
    ):
        if index < len(mode) and mode[index]:
            return element_type
    return ELEMENT_FACE


def build_overlay_batches(obj: bpy.types.Object, settings):
    if obj.mode != "EDIT":
        log_debug_from_settings(settings, "Overlay skipped: not in edit mode")
        return {etype: [] for etype in ELEMENT_TYPES}
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    matrix = obj.matrix_world
    normal_matrix = matrix.to_3x3()
    results = {etype: [] for etype in ELEMENT_TYPES}
    edge_trim = float(getattr(settings, "overlay_edge_trim", 0.0))
    face_offset = float(getattr(settings, "overlay_face_offset", 0.002))
    for element_type in ELEMENT_TYPES:
        collection = get_layer_collection(settings, element_type)
        if not collection:
            continue
        int_layer, stack_layer = ensure_annotation_layers(bm, element_type)
        ensure_lookup_tables(bm, element_type)
        mapping = load_element_layers(settings, element_type)
        merge_stack_layer_into_mapping(mapping, bm, stack_layer, element_type)
        visible_layers = {layer.layer_id: layer for layer in collection if layer.is_visible}
        if not visible_layers:
            continue
        if getattr(settings, "solo_active", False):
            current = active_layer(settings, element_type)
            if current and current.layer_id in visible_layers:
                visible_layers = {current.layer_id: current}
            elif current:
                log_debug_from_settings(settings, f"Solo active requested but layer {current.layer_id} hidden for {element_type}")
                visible_layers = {}
        if not visible_layers:
            continue
        container = element_container(bm, element_type)
        buckets = defaultdict(list)
        order_lookup = layer_order_map(settings, element_type)
        order_lookup = layer_order_map(settings, element_type)
        if element_type == ELEMENT_FACE:
            for face in container:
                layers = normalize_layer_ids(get_layers_for_index(mapping, face.index), order_lookup)
                if not layers and face[int_layer] >= 0:
                    layers = normalize_layer_ids([face[int_layer]], order_lookup)
                target = [lid for lid in layers if lid in visible_layers]
                if not target:
                    continue
                verts = face.verts
                if len(verts) < 3:
                    continue
                normal_local = face.normal if face.normal.length else Vector((0.0, 0.0, 1.0))
                normal = (normal_matrix @ normal_local).normalized() if normal_local.length else Vector((0.0, 0.0, 1.0))
                offset = normal * face_offset
                transformed = [matrix @ v.co + offset for v in verts]
                root = transformed[0]
                triangles = [
                    (root, transformed[i], transformed[i + 1])
                    for i in range(1, len(transformed) - 1)
                ]
                if not triangles:
                    continue
                top_layer = max(target, key=lambda lid: order_lookup.get(lid, -1))
                bucket_key = (top_layer, bool(face.select))
                buckets[bucket_key].extend(triangles)
            shader = gpu.shader.from_builtin("UNIFORM_COLOR")
            for (layer_id, selected_flag), triangles in buckets.items():
                if not triangles:
                    continue
                flat = []
                for tri in triangles:
                    flat.extend(tri)
                batch = batch_for_shader(shader, "TRIS", {"pos": flat})
                layer_settings = visible_layers[layer_id]
                results[element_type].append(
                    {
                        "kind": "triangles",
                        "batch": batch,
                        "shader": shader,
                        "color": layer_settings.color,
                        "selected": selected_flag,
                    }
                )
        elif element_type == ELEMENT_EDGE:
            for edge in container:
                layers = normalize_layer_ids(get_layers_for_index(mapping, edge.index), order_lookup)
                if not layers and edge[int_layer] >= 0:
                    layers = normalize_layer_ids([edge[int_layer]], order_lookup)
                target = [lid for lid in layers if lid in visible_layers]
                if not target:
                    continue
                verts = edge.verts
                if len(verts) != 2:
                    continue
                avg_normal = Vector((0.0, 0.0, 0.0))
                for loop in edge.link_loops:
                    avg_normal += loop.face.normal
                if avg_normal.length == 0:
                    avg_normal = (verts[0].co - verts[1].co).cross(Vector((0.0, 0.0, 1.0)))
                if avg_normal.length == 0:
                    avg_normal = Vector((0.0, 0.0, 1.0))
                avg_normal.normalize()
                normal_world = (normal_matrix @ avg_normal)
                if normal_world.length == 0:
                    normal_world = Vector((0.0, 0.0, 1.0))
                normal_world.normalize()
                offset = normal_world * EDGE_DRAW_OFFSET
                p0 = matrix @ verts[0].co + offset
                p1 = matrix @ verts[1].co + offset
                if edge_trim < 0.0:
                    direction = p1 - p0
                    length = direction.length
                    if length > 1e-6:
                        shrink = min(length * (-edge_trim), length * 0.499)
                        dir_norm = direction / length
                        p0 = p0 + dir_norm * shrink
                        p1 = p1 - dir_norm * shrink
                top_layer = max(target, key=lambda lid: order_lookup.get(lid, -1))
                bucket_key = (top_layer, bool(edge.select))
                buckets[bucket_key].append((p0.copy(), p1.copy()))
            for (layer_id, selected_flag), segments in buckets.items():
                if not segments:
                    continue
                layer_settings = visible_layers[layer_id]
                results[element_type].append(
                    {
                        "kind": "edge_segments",
                        "segments": segments,
                        "color": layer_settings.color,
                        "selected": selected_flag,
                    }
                )
        else:
            for vert in container:
                layers = normalize_layer_ids(get_layers_for_index(mapping, vert.index), order_lookup)
                if not layers and vert[int_layer] >= 0:
                    layers = normalize_layer_ids([vert[int_layer]], order_lookup)
                target = [lid for lid in layers if lid in visible_layers]
                if not target:
                    continue
                normal_local = vert.normal if vert.normal.length else Vector((0.0, 0.0, 1.0))
                normal = (normal_matrix @ normal_local).normalized() if normal_local.length else Vector((0.0, 0.0, 1.0))
                offset = normal * 0.004
                coord = matrix @ vert.co + offset
                top_layer = max(target, key=lambda lid: order_lookup.get(lid, -1))
                bucket_key = (top_layer, bool(vert.select))
                buckets[bucket_key].append(coord)
            shader = gpu.shader.from_builtin("POINT_UNIFORM_COLOR")
            for (layer_id, selected_flag), coords in buckets.items():
                if not coords:
                    continue
                batch = batch_for_shader(shader, "POINTS", {"pos": coords})
                layer_settings = visible_layers[layer_id]
                results[element_type].append(
                    {
                        "kind": "points",
                        "batch": batch,
                        "shader": shader,
                        "color": layer_settings.color,
                        "selected": selected_flag,
                    }
                )
    return results


def draw_overlay():
    context = bpy.context
    obj = context.object
    if not obj or obj.type != "MESH":
        return
    settings = getattr(obj, "mesh_annotations", None)
    if not settings or not settings.enable_overlay:
        return
    line_width = max(1.0, float(getattr(settings, "overlay_line_width", 2.0)))
    point_size = max(1.0, float(getattr(settings, "overlay_point_size", 6.0)))
    alpha_mult = max(0.0, min(1.0, float(getattr(settings, "overlay_alpha_multiplier", 0.5))))
    show_backfaces = bool(getattr(settings, "overlay_show_backfaces", True))
    batches = build_overlay_batches(obj, settings)
    if not any(batches[etype] for etype in ELEMENT_TYPES):
        log_debug_from_settings(settings, "Draw overlay: nothing to draw")
        return
    depth_mode = "ALWAYS" if show_backfaces else "LESS_EQUAL"
    gpu.state.blend_set("ALPHA")
    current_blend = "ALPHA"
    gpu.state.depth_mask_set(False)
    gpu.state.depth_test_set(depth_mode)
    try:
        viewport_size = get_viewport_size()
        polyline_shader = None
        for element_type in ELEMENT_TYPES:
            entries = batches[element_type]
            if not entries:
                continue
            for entry in entries:
                kind = entry.get("kind")
                base_color = entry.get("color", (1.0, 1.0, 1.0, 1.0))
                if len(base_color) < 4:
                    base_color = (*base_color[:3], 1.0)
                color = (
                    base_color[0],
                    base_color[1],
                    base_color[2],
                    base_color[3] * alpha_mult,
                )
                selected_flag = bool(entry.get("selected"))
                if selected_flag:
                    boost = 0.2
                    color = (
                        min(1.0, color[0] + boost),
                        min(1.0, color[1] + boost),
                        min(1.0, color[2] + boost),
                        min(1.0, max(color[3], alpha_mult * 0.85)),
                    )
                    target_blend = "ADDITIVE"
                else:
                    target_blend = "ALPHA"
                if target_blend != current_blend:
                    gpu.state.blend_set(target_blend)
                    current_blend = target_blend
                if kind == "triangles":
                    shader = entry["shader"]
                    batch = entry["batch"]
                    shader.bind()
                    shader.uniform_float("color", color)
                    batch.draw(shader)
                elif kind == "points":
                    shader = entry["shader"]
                    batch = entry["batch"]
                    gpu.state.point_size_set(point_size)
                    shader.bind()
                    shader.uniform_float("color", color)
                    batch.draw(shader)
                    gpu.state.point_size_set(1.0)
                elif kind == "edge_segments":
                    if polyline_shader is None:
                        polyline_shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
                    polyline_shader.bind()
                    polyline_shader.uniform_float("viewportSize", viewport_size)
                    polyline_shader.uniform_float("lineWidth", line_width)
                    polyline_shader.uniform_float("color", color)
                    for segment in entry["segments"]:
                        batch = batch_for_shader(polyline_shader, "LINES", {"pos": [segment[0], segment[1]]})
                        batch.draw(polyline_shader)
    finally:
        if current_blend != "ALPHA":
            gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set("NONE")


def register_draw_handler():
    global _draw_handle
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_overlay, (), "WINDOW", "POST_VIEW")


def unregister_draw_handler():
    global _draw_handle
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        _draw_handle = None


def draw_existing_layer_menu(layout, obj, element_type: str, use_loop: bool):
    settings = getattr(obj, "mesh_annotations", None)
    if not settings:
        layout.label(text=bi("No layers", "暂无图层"))
        return
    collection = get_layer_collection(settings, element_type)
    if not collection:
        layout.label(text=bi("No layers", "暂无图层"))
        return
    for layer in collection:
        count = count_elements_for_layer(obj, element_type, layer.layer_id)
        text = f"{layer.name} ({count})" if count else layer.name
        operator = layout.operator("mesh.annotation_assign_layer", text=text, icon="BRUSH_DATA")
        operator.layer_id = layer.layer_id
        operator.element_type = element_type
        operator.use_loop = use_loop




def context_menu_use_type_choice():
    prefs = get_addon_prefs()
    if prefs is None:
        return True
    return bool(getattr(prefs, "context_menu_split_types", True))


def context_menu_default_type(context):
    return infer_element_type_from_mode(context)


TYPE_MENU_ACTIONS = {
    "assign_selected_active": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_active",
        "props": {},
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_selected_new": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_new_layer",
        "props": {"use_loop": False, "skip_dialog": True},
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_selected_existing": {
        "kind": "existing",
        "use_loop": False,
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_loop_active": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_loop",
        "props": {},
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_loop_new": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_new_layer",
        "props": {"use_loop": True, "skip_dialog": True},
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_loop_existing": {
        "kind": "existing",
        "use_loop": True,
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "clear_selected_all": {
        "kind": "clear",
        "mode": "ALL",
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "clear_selected_top": {
        "kind": "clear",
        "mode": "TOP",
        "label": ("Choose Element Type", "选择元素类型"),
    },
}


class MeshAnnotationTypeMenuBase(bpy.types.Menu):
    bl_label = bi("Choose Element Type", "选择元素类型")
    action_key = ""

    def draw(self, context):
        layout = self.layout
        action = TYPE_MENU_ACTIONS.get(self.action_key)
        if not action:
            layout.label(text=bi("No action configured", "未配置操作"))
            return
        label_en, label_zh = action.get("label", ("Choose Element Type", "选择元素类型"))
        layout.label(text=bi(label_en, label_zh))
        obj = context.object
        for element_type in ELEMENT_TYPES:
            meta = element_meta(element_type)
            item_en, item_zh = meta["label"]
            text = bi(item_en, item_zh)
            icon = meta["icon"]
            kind = action["kind"]
            if kind == "operator":
                op = layout.operator(action["operator"], text=text, icon=icon)
                op.element_type = element_type
                for attr, value in action.get("props", {}).items():
                    setattr(op, attr, value)
            elif kind == "existing":
                col = layout.column()
                col.label(text=text, icon=icon)
                draw_existing_layer_menu(col, obj, element_type, use_loop=action.get("use_loop", False))
            elif kind == "clear":
                op = layout.operator("mesh.annotation_clear_selected", text=text, icon=icon)
                op.element_type = element_type
                op.mode = action["mode"]
            else:
                layout.label(text=bi("Unsupported action", "未支持的操作"), icon="ERROR")


class VIEW3D_MT_mesh_annotation_type_assign_selected_active(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_selected_active"
    action_key = "assign_selected_active"


class VIEW3D_MT_mesh_annotation_type_assign_selected_new(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_selected_new"
    action_key = "assign_selected_new"


class VIEW3D_MT_mesh_annotation_type_assign_selected_existing(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_selected_existing"
    action_key = "assign_selected_existing"


class VIEW3D_MT_mesh_annotation_type_assign_loop_active(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_loop_active"
    action_key = "assign_loop_active"


class VIEW3D_MT_mesh_annotation_type_assign_loop_new(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_loop_new"
    action_key = "assign_loop_new"


class VIEW3D_MT_mesh_annotation_type_assign_loop_existing(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_loop_existing"
    action_key = "assign_loop_existing"


class VIEW3D_MT_mesh_annotation_type_clear_selected_all(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_clear_selected_all"
    action_key = "clear_selected_all"


class VIEW3D_MT_mesh_annotation_type_clear_selected_top(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_clear_selected_top"
    action_key = "clear_selected_top"


def context_menu_use_type_choice():
    prefs = get_addon_prefs()
    return bool(prefs and getattr(prefs, "context_menu_split_types", True))


def context_menu_default_type(context):
    return infer_element_type_from_mode(context)


TYPE_MENU_ACTIONS = {
    "assign_selected_active": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_active",
        "props": {},
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_selected_new": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_new_layer",
        "props": {"use_loop": False, "skip_dialog": True},
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_selected_existing": {
        "kind": "existing",
        "use_loop": False,
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_loop_active": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_loop",
        "props": {},
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_loop_new": {
        "kind": "operator",
        "operator": "mesh.annotation_assign_new_layer",
        "props": {"use_loop": True, "skip_dialog": True},
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "assign_loop_existing": {
        "kind": "existing",
        "use_loop": True,
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "clear_selected_all": {
        "kind": "clear",
        "mode": "ALL",
        "label": ("Choose Element Type", "选择元素类型"),
    },
    "clear_selected_top": {
        "kind": "clear",
        "mode": "TOP",
        "label": ("Choose Element Type", "选择元素类型"),
    },
}


class MeshAnnotationTypeMenuBase(bpy.types.Menu):
    bl_label = bi("Choose Element Type", "选择元素类型")
    action_key = ""

    def draw(self, context):
        layout = self.layout
        action = TYPE_MENU_ACTIONS.get(self.action_key)
        if not action:
            layout.label(text=bi("No action configured", "未配置操作"))
            return
        label_en, label_zh = action.get("label", ("Choose Element Type", "选择元素类型"))
        layout.label(text=bi(label_en, label_zh))
        obj = context.object
        for element_type in ELEMENT_TYPES:
            meta = element_meta(element_type)
            item_en, item_zh = meta["label"]
            text = bi(item_en, item_zh)
            icon = meta["icon"]
            kind = action["kind"]
            if kind == "operator":
                op = layout.operator(action["operator"], text=text, icon=icon)
                op.element_type = element_type
                for attr, value in action.get("props", {}).items():
                    setattr(op, attr, value)
            elif kind == "existing":
                col = layout.column()
                col.label(text=text, icon=icon)
                draw_existing_layer_menu(col, obj, element_type, use_loop=action.get("use_loop", False))
            elif kind == "clear":
                op = layout.operator("mesh.annotation_clear_selected", text=text, icon=icon)
                op.element_type = element_type
                op.mode = action["mode"]
            else:
                layout.label(text=bi("Unsupported action", "未支持的操作"), icon="ERROR")


class VIEW3D_MT_mesh_annotation_type_assign_selected_active(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_selected_active"
    action_key = "assign_selected_active"


class VIEW3D_MT_mesh_annotation_type_assign_selected_new(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_selected_new"
    action_key = "assign_selected_new"


class VIEW3D_MT_mesh_annotation_type_assign_selected_existing(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_selected_existing"
    action_key = "assign_selected_existing"


class VIEW3D_MT_mesh_annotation_type_assign_loop_active(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_loop_active"
    action_key = "assign_loop_active"


class VIEW3D_MT_mesh_annotation_type_assign_loop_new(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_loop_new"
    action_key = "assign_loop_new"


class VIEW3D_MT_mesh_annotation_type_assign_loop_existing(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_assign_loop_existing"
    action_key = "assign_loop_existing"


class VIEW3D_MT_mesh_annotation_type_clear_selected_all(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_clear_selected_all"
    action_key = "clear_selected_all"


class VIEW3D_MT_mesh_annotation_type_clear_selected_top(MeshAnnotationTypeMenuBase):
    bl_idname = "VIEW3D_MT_mesh_annotation_type_clear_selected_top"
    action_key = "clear_selected_top"



def add_assign_selected_active_entry(layout, context):
    text = bi("Assign Selected to Active Layer", "将选中分配到当前层")
    if context_menu_use_type_choice():
        layout.menu("VIEW3D_MT_mesh_annotation_type_assign_selected_active", text=text, icon="BRUSH_DATA")
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_assign_active", text=text, icon="BRUSH_DATA")
        op.element_type = element_type



def add_assign_selected_new_entry(layout, context):
    text = bi("Assign Selected to New Layer", "将选中新建图层")
    if context_menu_use_type_choice():
        layout.menu("VIEW3D_MT_mesh_annotation_type_assign_selected_new", text=text, icon="ADD")
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_assign_new_layer", text=text, icon="ADD")
        op.element_type = element_type
        op.use_loop = False
        op.skip_dialog = True



def add_assign_selected_existing_entry(layout, context):
    text = bi("Assign Selected to Existing Layer", "添加选中到已有图层")
    if context_menu_use_type_choice():
        layout.menu("VIEW3D_MT_mesh_annotation_type_assign_selected_existing", text=text, icon="GROUP_VCOL")
    else:
        layout.label(text=text, icon="GROUP_VCOL")
        element_type = context_menu_default_type(context)
        draw_existing_layer_menu(layout, context.object, element_type, use_loop=False)



def add_assign_loop_active_entry(layout, context):
    text = bi("Assign Loop to Active Layer", "将循环分配到当前层")
    if context_menu_use_type_choice():
        layout.menu("VIEW3D_MT_mesh_annotation_type_assign_loop_active", text=text, icon="BRUSH_DATA")
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_assign_loop", text=text, icon="BRUSH_DATA")
        op.element_type = element_type



def add_assign_loop_new_entry(layout, context):
    text = bi("Assign Loop to New Layer", "将循环分配到新图层")
    if context_menu_use_type_choice():
        layout.menu("VIEW3D_MT_mesh_annotation_type_assign_loop_new", text=text, icon="ADD")
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_assign_new_layer", text=text, icon="ADD")
        op.element_type = element_type
        op.use_loop = True
        op.skip_dialog = True



def add_assign_loop_existing_entry(layout, context):
    text = bi("Assign Loop to Existing Layer", "循环添加到已有图层")
    if context_menu_use_type_choice():
        layout.menu("VIEW3D_MT_mesh_annotation_type_assign_loop_existing", text=text, icon="GROUP_VCOL")
    else:
        layout.label(text=text, icon="GROUP_VCOL")
        element_type = context_menu_default_type(context)
        draw_existing_layer_menu(layout, context.object, element_type, use_loop=True)



def add_clear_selected_entry(layout, context, mode: str):
    if mode == "ALL":
        text = bi("Clear Selected (All Layers)", "清除选中（全部图层）")
        icon = "X"
    else:
        text = bi("Clear Selected (Top Layer)", "清除选中（顶部图层）")
        icon = "REMOVE"
    if context_menu_use_type_choice():
        menu_id = (
            "VIEW3D_MT_mesh_annotation_type_clear_selected_all"
            if mode == "ALL"
            else "VIEW3D_MT_mesh_annotation_type_clear_selected_top"
        )
        layout.menu(menu_id, text=text, icon=icon)
    else:
        element_type = context_menu_default_type(context)
        op = layout.operator("mesh.annotation_clear_selected", text=text, icon=icon)
        op.element_type = element_type
        op.mode = mode



class VIEW3D_MT_mesh_annotation_add(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_add"
    bl_label = bi("Add", "添加")

    def draw(self, context):
        layout = self.layout
        layout.menu(
            "VIEW3D_MT_mesh_annotation_add_selected",
            text=bi("Selected Elements", "选中元素"),
            icon="FACESEL",
        )
        layout.menu(
            "VIEW3D_MT_mesh_annotation_add_loop",
            text=bi("Loops / Paths", "循环 / 路径"),
            icon="EDGESEL",
        )


class VIEW3D_MT_mesh_annotation_add_selected(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_add_selected"
    bl_label = bi("Selected Elements", "选中元素")

    def draw(self, context):
        layout = self.layout
        add_assign_selected_active_entry(layout, context)
        add_assign_selected_new_entry(layout, context)
        add_assign_selected_existing_entry(layout, context)


class VIEW3D_MT_mesh_annotation_add_loop(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_add_loop"
    bl_label = bi("Loops / Paths", "循环 / 路径")

    def draw(self, context):
        layout = self.layout
        add_assign_loop_active_entry(layout, context)
        add_assign_loop_new_entry(layout, context)
        add_assign_loop_existing_entry(layout, context)


class VIEW3D_MT_mesh_annotation_remove(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_remove"
    bl_label = bi("Remove", "删除")

    def draw(self, context):
        layout = self.layout
        layout.menu(
            "VIEW3D_MT_mesh_annotation_remove_selected",
            text=bi("Selected Elements", "选中元素"),
            icon="TRASH",
        )


class VIEW3D_MT_mesh_annotation_remove_selected(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_remove_selected"
    bl_label = bi("Remove Selected", "删除选中")

    def draw(self, context):
        layout = self.layout
        add_clear_selected_entry(layout, context, mode="ALL")
        add_clear_selected_entry(layout, context, mode="TOP")


def element_labels(element_type: str):
    meta = element_meta(element_type)
    return meta["selection_label"], meta["loop_label"], meta["label"]


def collect_face_loop_faces(context, obj, bm, settings):
    ensure_lookup_tables(bm, ELEMENT_FACE)
    bm.edges.ensure_lookup_table()
    selected_faces = [face for face in bm.faces if face.select]
    if len(selected_faces) < 2:
        msg = bi("Select at least two faces to define the loop", "请选择至少两个面来确定循环")
        return set(), msg
    selected_set = set(selected_faces)
    required_indices = {face.index for face in selected_faces}
    loop_candidates = []
    processed_edges = set()

    def gather_loop(face, other, edge):
        loop = set()
        loop |= _walk_face_loop(face, other, edge, set())
        loop |= _walk_face_loop(other, face, edge, set())
        loop.add(face)
        loop.add(other)
        return loop

    for face in selected_faces:
        if len(face.verts) != 4:
            continue
        for edge in face.edges:
            if len(edge.link_faces) != 2:
                continue
            linked = [f for f in edge.link_faces if f is not face]
            if not linked:
                continue
            other = linked[0]
            edge_key = (edge.index, tuple(sorted((face.index, other.index))))
            if edge_key in processed_edges:
                continue
            processed_edges.add(edge_key)
            loop = gather_loop(face, other, edge)
            if loop:
                loop_candidates.append(loop)

    if not loop_candidates:
        msg = bi("Unable to derive a face loop from the selection", "无法根据选择推导出面循环")
        return set(), msg

    unique_candidates = []
    seen_signatures = set()
    for loop in loop_candidates:
        signature = frozenset(face.index for face in loop)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique_candidates.append(loop)
    matching_loops = []
    for loop in unique_candidates:
        loop_indices = {face.index for face in loop}
        if required_indices.issubset(loop_indices):
            matching_loops.append(loop)
    if not matching_loops:
        msg = bi("No face loop passes through every selected face", "没有一个面循环能够覆盖所有已选面")
        return set(), msg
    if len(matching_loops) > 1:
        msg = bi("Multiple face loops detected; refine your selection", "检测到多个面循环，请精细调整选区")
        return set(), msg
    final_loop = matching_loops[0]
    for face in bm.faces:
        face.select = face in final_loop

    log_debug_from_settings(settings, f"collect_face_loop_faces gathered {len(final_loop)} faces")
    return final_loop, None


def _walk_face_loop(start_face, previous_face, shared_edge, visited_faces):
    loop = set()
    current_face = start_face
    prev_face = previous_face
    incoming_edge = shared_edge
    while current_face not in loop:
        loop.add(current_face)
        visited_faces.add(current_face)
        opposite_edge = _find_opposite_edge(current_face, incoming_edge)
        if opposite_edge is None:
            break
        linked_faces = [f for f in opposite_edge.link_faces if f is not current_face]
        if not linked_faces:
            break
        next_face = linked_faces[0]
        if next_face is prev_face:
            break
        prev_face = current_face
        incoming_edge = opposite_edge
        current_face = next_face
    return loop


def _find_opposite_edge(face: bmesh.types.BMFace, incoming_edge: bmesh.types.BMEdge):
    incoming_vertices = {v.index for v in incoming_edge.verts}
    for edge in face.edges:
        if edge is incoming_edge:
            continue
        if incoming_vertices.isdisjoint({v.index for v in edge.verts}):
            return edge
    return None


def is_pole_edge(edge: bmesh.types.BMEdge) -> bool:
    return any(len(vert.link_edges) != 4 for vert in edge.verts)


def _walk_edge_loop_direction(start_edge: bmesh.types.BMEdge, start_face: bmesh.types.BMFace):
    sequence = [start_edge]
    current_edge = start_edge
    current_face = start_face
    while True:
        if current_face is None or len(current_face.edges) != 4:
            break
        if is_pole_edge(current_edge):
            break
        opposite = _find_opposite_edge(current_face, current_edge)
        if opposite is None or opposite in sequence:
            break
        sequence.append(opposite)
        if is_pole_edge(opposite):
            break
        next_face = next((f for f in opposite.link_faces if f is not current_face), None)
        if next_face is None:
            break
        current_edge = opposite
        current_face = next_face
    return sequence


def compute_edge_loop(seed_edge: bmesh.types.BMEdge):
    faces = list(seed_edge.link_faces)
    if not faces:
        return [seed_edge]
    if len(faces) == 1:
        return _walk_edge_loop_direction(seed_edge, faces[0])
    forward = _walk_edge_loop_direction(seed_edge, faces[0])
    backward = _walk_edge_loop_direction(seed_edge, faces[1])
    combined = list(reversed(forward[1:])) + [seed_edge] + backward[1:]
    ordered = []
    seen = set()
    for edge in combined:
        if edge not in seen:
            seen.add(edge)
            ordered.append(edge)
    return ordered


def _select_loop_via_builtin(context, obj, element_type: str):
    mesh = obj.data
    tool_settings = context.tool_settings
    original_mode = tuple(tool_settings.mesh_select_mode)
    target_mode = {
        ELEMENT_VERTEX: (True, False, False),
        ELEMENT_EDGE: (False, True, False),
        ELEMENT_FACE: (False, False, True),
    }[element_type]
    try:
        if original_mode != target_mode:
            tool_settings.mesh_select_mode = target_mode
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        window = context.window
        if window is None:
            return False, bi("No active 3D View found", "无可用的3D视图，无法派生循环")
        screen = window.screen
        last_error = None
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is None:
                continue
            override_kwargs = {
                "window": window,
                "screen": screen,
                "area": area,
                "region": region,
                "mode": "EDIT_MESH",
                "object": obj,
                "active_object": obj,
            }
            try:
                with context.temp_override(**override_kwargs):
                    result = bpy.ops.mesh.loop_multi_select(ring=False)
            except (RuntimeError, ValueError) as exc:
                last_error = str(exc)
                continue
            if "FINISHED" in result:
                bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
                return True, None
        message = last_error or bi("Unable to resolve a loop from the current selection", "无法从当前选择推导循环")
        return False, message
    except Exception as exc:
        return False, str(exc)
    finally:
        if tool_settings.mesh_select_mode != original_mode:
            tool_settings.mesh_select_mode = original_mode
    return True, None


def collect_edge_loop_edges(context, obj, bm, settings):
    ensure_lookup_tables(bm, ELEMENT_EDGE)
    bm.edges.ensure_lookup_table()
    selected_edges = [edge for edge in bm.edges if edge.select]
    if not selected_edges:
        msg = bi("Select at least one edge to derive a loop", "请选择至少一条边以推导循环")
        return set(), msg
    mesh = obj.data
    original_selection = {edge.index for edge in bm.edges if edge.select}
    active_index = selected_edges[0].index
    for edge in bm.edges:
        edge.select = False
    bm.select_history.clear()
    bm.edges[active_index].select = True
    bm.select_history.add(bm.edges[active_index])
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    ok, message = _select_loop_via_builtin(context, obj, ELEMENT_EDGE)
    if not ok:
        bm_restore = bmesh.from_edit_mesh(mesh)
        ensure_lookup_tables(bm_restore, ELEMENT_EDGE)
        for edge in bm_restore.edges:
            edge.select = edge.index in original_selection
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        return set(), message
    bm_after = bmesh.from_edit_mesh(mesh)
    ensure_lookup_tables(bm_after, ELEMENT_EDGE)
    loop_edges = {edge for edge in bm_after.edges if edge.select}
    loop_indices = {edge.index for edge in loop_edges}
    if not loop_edges:
        for edge in bm_after.edges:
            edge.select = edge.index in original_selection
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        msg = bi("Unable to resolve an edge loop", "无法生成边循环")
        return set(), msg
    if not original_selection.issubset(loop_indices):
        for edge in bm_after.edges:
            edge.select = edge.index in original_selection
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        msg = bi("Selected edges are not on the same loop", "所选边不在同一个循环上")
        return set(), msg
    log_debug_from_settings(settings, f"collect_edge_loop_edges gathered {len(loop_edges)} edges")
    return loop_edges, None


def _gather_vertex_path_components(bm, vertex_indices):
    components = []
    visited = set()
    for index in vertex_indices:
        if index in visited:
            continue
        component = set()
        stack = [index]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            vert = bm.verts[current]
            for edge in vert.link_edges:
                for other in edge.verts:
                    other_index = other.index
                    if other_index == current or other_index not in vertex_indices:
                        continue
                    stack.append(other_index)
        if component:
            components.append(component)
    return components


def _component_is_vertex_path(bm, component):
    if not component:
        return False
    if len(component) == 1:
        return True
    endpoints = 0
    for index in component:
        vert = bm.verts[index]
        neighbours = {
            other.index
            for edge in vert.link_edges
            for other in edge.verts
            if other.index != index and other.index in component
        }
        degree = len(neighbours)
        if degree > 2:
            return False
        if degree == 1:
            endpoints += 1
        elif degree == 0:
            return False
    return endpoints in {0, 2}



def collect_vertex_loop_vertices(context, obj, bm, settings):
    ensure_lookup_tables(bm, ELEMENT_VERTEX)
    bm.edges.ensure_lookup_table()
    selected_vertices = [vert for vert in bm.verts if vert.select]
    if len(selected_vertices) < 2:
        msg = bi("Select at least two vertices to derive a loop", "请选择至少两个顶点以推导循环")
        return set(), msg
    mesh = obj.data
    target_indices = [vert.index for vert in selected_vertices]
    required = set(target_indices)
    original_selection = {vert.index for vert in bm.verts if vert.select}
    chosen_loop = None
    last_message = None
    for candidate_index in target_indices:
        bm_candidate = bmesh.from_edit_mesh(mesh)
        ensure_lookup_tables(bm_candidate, ELEMENT_VERTEX)
        for vert in bm_candidate.verts:
            vert.select = False
        bm_candidate.select_history.clear()
        candidate = bm_candidate.verts[candidate_index]
        candidate.select = True
        bm_candidate.select_history.add(candidate)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        ok, message = _select_loop_via_builtin(context, obj, ELEMENT_VERTEX)
        if not ok:
            last_message = message
            continue
        bm_after = bmesh.from_edit_mesh(mesh)
        ensure_lookup_tables(bm_after, ELEMENT_VERTEX)
        loop_indices = {vert.index for vert in bm_after.verts if vert.select}
        components = _gather_vertex_path_components(bm_after, loop_indices)
        valid_components = [comp for comp in components if _component_is_vertex_path(bm_after, comp)]
        containing = [comp for comp in valid_components if required.issubset(comp)]
        if not containing:
            last_message = bi(
                "No vertex loop passes through every selected vertex",
                "没有一条顶点循环能够覆盖所有已选顶点",
            )
            continue
        if len(containing) > 1:
            last_message = bi(
                "Multiple vertex loops detected; refine your selection",
                "检测到多条顶点循环，请精细调整选区",
            )
            continue
        chosen_loop = set(containing[0])
        break
    if chosen_loop is None:
        bm_restore = bmesh.from_edit_mesh(mesh)
        ensure_lookup_tables(bm_restore, ELEMENT_VERTEX)
        for vert in bm_restore.verts:
            vert.select = vert.index in original_selection
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        return set(), last_message or bi(
            "No vertex loop passes through every selected vertex",
            "没有一条顶点循环能够覆盖所有已选顶点",
        )
    bm_final = bmesh.from_edit_mesh(mesh)
    ensure_lookup_tables(bm_final, ELEMENT_VERTEX)
    loop_vertices = {bm_final.verts[index] for index in chosen_loop}
    for vert in bm_final.verts:
        vert.select = vert.index in chosen_loop
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    log_debug_from_settings(settings, f"collect_vertex_loop_vertices gathered {len(loop_vertices)} vertices")
    return loop_vertices, None

class MeshAnnotationLayer(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="Layer")
    color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype="COLOR_GAMMA",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.8, 0.3, 0.3, 1.0),
        update=lambda self, context: tag_view3d_redraw(context),
    )
    layer_id: bpy.props.IntProperty()
    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
        options={'HIDDEN'},
    )
    is_visible: bpy.props.BoolProperty(name="Visible", default=True, update=lambda self, context: tag_view3d_redraw(context))


class MeshAnnotationSettings(bpy.types.PropertyGroup):
    enable_overlay: bpy.props.BoolProperty(name="Show Overlay", default=True, update=lambda self, context: tag_view3d_redraw(context))
    solo_active: bpy.props.BoolProperty(name="Solo Active Layer", default=False, update=lambda self, context: tag_view3d_redraw(context))
    debug_output: bpy.props.BoolProperty(name="Debug Output", default=False)
    overlay_line_width: bpy.props.FloatProperty(
        name="Edge Thickness",
        min=1.0,
        max=10.0,
        default=2.0,
        update=lambda self, context: tag_view3d_redraw(context),
    )
    overlay_point_size: bpy.props.FloatProperty(
        name="Vertex Size",
        min=1.0,
        max=20.0,
        default=6.0,
        update=lambda self, context: tag_view3d_redraw(context),
    )
    overlay_edge_trim: bpy.props.FloatProperty(
        name="Edge Shortening",
        description="Adjust edge overlay length; set negative values to trim both ends while keeping the line centered",
        min=-0.45,
        max=0.0,
        default=0.0,
        step=0.01,
        precision=3,
        update=lambda self, context: tag_view3d_redraw(context),
    )
    overlay_face_offset: bpy.props.FloatProperty(
        name="Face Offset",
        description="Offset face overlays along the surface normal to avoid z-fighting",
        min=0.0,
        max=0.01,
        default=0.002,
        step=0.0001,
        precision=4,
        update=lambda self, context: tag_view3d_redraw(context),
    )

    overlay_alpha_multiplier: bpy.props.FloatProperty(
        name="Overlay Opacity",
        description="Global multiplier applied to each layer's own alpha value",
        min=0.0,
        max=1.0,
        default=0.5,
        update=lambda self, context: tag_view3d_redraw(context),
    )

    overlay_show_backfaces: bpy.props.BoolProperty(
        name="Show Through Mesh",
        default=True,
        update=lambda self, context: tag_view3d_redraw(context),
    )

    face_layers: bpy.props.CollectionProperty(type=MeshAnnotationLayer)
    edge_layers: bpy.props.CollectionProperty(type=MeshAnnotationLayer)
    vertex_layers: bpy.props.CollectionProperty(type=MeshAnnotationLayer)

    active_face_layer_index: bpy.props.IntProperty(default=-1)
    active_edge_layer_index: bpy.props.IntProperty(default=-1)
    active_vertex_layer_index: bpy.props.IntProperty(default=-1)

    next_face_layer_id: bpy.props.IntProperty(default=1)
    next_edge_layer_id: bpy.props.IntProperty(default=1)
    next_vertex_layer_id: bpy.props.IntProperty(default=1)

    face_layers_data: bpy.props.StringProperty(default="{}")
    edge_layers_data: bpy.props.StringProperty(default="{}")
    vertex_layers_data: bpy.props.StringProperty(default="{}")

    color_seed_face: bpy.props.FloatProperty(default=0.0)
    color_seed_edge: bpy.props.FloatProperty(default=0.0)
    color_seed_vertex: bpy.props.FloatProperty(default=0.0)

    def active_layer(self, element_type=ELEMENT_FACE):
        return active_layer(self, element_type)

class MESH_UL_annotation_layers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layer = item
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            icon_id = "HIDE_OFF" if layer.is_visible else "HIDE_ON"
            row.prop(layer, "is_visible", text="", emboss=False, icon=icon_id)
            row.prop(layer, "color", text="")
            obj = context.object if context else None
            element_type = layer.element_type
            count = 0
            if obj and obj.type == "MESH":
                count = count_elements_for_layer(obj, element_type, layer.layer_id)
            row.label(text=str(count))
            row.prop(layer, "name", text="", emboss=False)
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=layer.name)


class MESH_OT_annotation_layer_add(bpy.types.Operator):
    bl_idname = "mesh.annotation_layer_add"
    bl_label = bi("Add Annotation Layer", "新增标注图层")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != "MESH":
            self.report({"WARNING"}, bi("Select a mesh object", "请选择一个网格对象"))
            return {"CANCELLED"}
        settings = obj.mesh_annotations
        create_layer(settings, self.element_type)
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_layer_remove(bpy.types.Operator):
    bl_idname = "mesh.annotation_layer_remove"
    bl_label = bi("Remove Annotation Layer", "移除标注图层")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        index = get_active_index(settings, self.element_type)
        if index < 0:
            self.report({"WARNING"}, bi("No active layer selected", "未选择图层"))
            return {"CANCELLED"}
        remove_layer(settings, obj, self.element_type, index)
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_layer_move(bpy.types.Operator):
    bl_idname = "mesh.annotation_layer_move"
    bl_label = bi("Reorder Annotation Layer", "调整图层顺序")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )
    direction: bpy.props.EnumProperty(
        name="Direction",
        items=(
            ("UP", "Up", "Move the layer up"),
            ("DOWN", "Down", "Move the layer down"),
        ),
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != "MESH":
            return False
        settings = getattr(obj, "mesh_annotations", None)
        if not settings:
            return False
        for etype in ELEMENT_TYPES:
            if len(get_layer_collection(settings, etype)) > 1:
                return True
        return False

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        collection = get_layer_collection(settings, self.element_type)
        idx = get_active_index(settings, self.element_type)
        if not (0 <= idx < len(collection)):
            return {"CANCELLED"}
        offset = -1 if self.direction == "UP" else 1
        new_idx = idx + offset
        if new_idx < 0 or new_idx >= len(collection):
            return {"CANCELLED"}
        collection.move(idx, new_idx)
        set_active_index(settings, self.element_type, new_idx)
        apply_layer_order_to_mapping(obj, self.element_type)
        tag_view3d_redraw(context)
        return {"FINISHED"}

class MESH_OT_annotation_assign_active(bpy.types.Operator):
    bl_idname = "mesh.annotation_assign_active"
    bl_label = bi("Assign Selection to Active Layer", "将选中元素分配到当前层")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = active_layer(settings, self.element_type)
        if layer is None:
            self.report({"WARNING"}, bi("No active layer selected", "未选择图层"))
            return {"CANCELLED"}
        if not assign_elements_to_layer(obj, self.element_type, layer.layer_id):
            self.report({"WARNING"}, bi("Select at least one element", "请至少选择一个元素"))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_select_layer(bpy.types.Operator):
    bl_idname = "mesh.annotation_select_layer"
    bl_label = bi("Select Elements in Layer", "选择图层元素")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )
    layer_id: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        count = select_elements_for_layer(obj, self.element_type, self.layer_id)
        if count == 0:
            self.report({"INFO"}, bi("Layer is empty", "图层内没有元素"))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_activate_from_selection(bpy.types.Operator):
    bl_idname = "mesh.annotation_activate_from_selection"
    bl_label = bi("Pick Active Layer From Selection", "从选择中激活图层")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        usage = collect_layer_usage_from_selection(obj, self.element_type)
        if not usage:
            self.report({"WARNING"}, bi("Selected elements do not belong to any layer", "所选元素未包含在任何图层中"))
            return {"CANCELLED"}
        layer_id, _count = usage.most_common(1)[0]
        collection = get_layer_collection(settings, self.element_type)
        for idx, layer in enumerate(collection):
            if layer.layer_id == layer_id:
                set_active_index(settings, self.element_type, idx)
                tag_view3d_redraw(context)
                return {"FINISHED"}
        self.report({"WARNING"}, bi("Layer not found", "未找到对应图层"))
        return {"CANCELLED"}


class MESH_OT_annotation_assign_loop(bpy.types.Operator):
    bl_idname = "mesh.annotation_assign_loop"
    bl_label = bi("Assign Loop to Active Layer", "将循环分配到当前层")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = active_layer(settings, self.element_type)
        if layer is None:
            self.report({"WARNING"}, bi("No active layer selected", "未选择图层"))
            return {"CANCELLED"}
        bm = bmesh.from_edit_mesh(obj.data)
        if self.element_type == ELEMENT_FACE:
            loop_elems, message = collect_face_loop_faces(context, obj, bm, settings)
            indices = [face.index for face in loop_elems]
        elif self.element_type == ELEMENT_EDGE:
            loop_elems, message = collect_edge_loop_edges(context, obj, bm, settings)
            indices = [edge.index for edge in loop_elems]
        else:
            loop_elems, message = collect_vertex_loop_vertices(context, obj, bm, settings)
            indices = [vert.index for vert in loop_elems]
        if message:
            self.report({"INFO"}, message)
            return {"CANCELLED"}
        if not assign_elements_to_layer(obj, self.element_type, layer.layer_id, element_indices=indices):
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_new_layer(bpy.types.Operator):
    bl_idname = "mesh.annotation_assign_new_layer"
    bl_label = bi("Assign Selection to New Layer", "将选择分配到新图层")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )
    use_loop: bpy.props.BoolProperty(default=False)
    skip_dialog: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    layer_name: bpy.props.StringProperty(name="Layer Name")
    color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype="COLOR_GAMMA",
        size=4,
        min=0.0,
        max=1.0,
        default=(0.9, 0.6, 0.2, 0.4),
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def invoke(self, context, event):
        settings = context.object.mesh_annotations
        default_name = f"{element_meta(self.element_type)['default_name']} {get_next_layer_id(settings, self.element_type)}"
        self.layer_name = default_name
        self.color = auto_generate_color(settings, self.element_type)
        if self.skip_dialog:
            return self.execute(context)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "layer_name", text=bi("Layer Name", "图层名称"))
        layout.prop(self, "color", text=bi("Color", "颜色"))

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        indices = None
        if self.use_loop:
            bm = bmesh.from_edit_mesh(obj.data)
            if self.element_type == ELEMENT_FACE:
                loop_elems, message = collect_face_loop_faces(context, obj, bm, settings)
                indices = [face.index for face in loop_elems]
            elif self.element_type == ELEMENT_EDGE:
                loop_elems, message = collect_edge_loop_edges(context, obj, bm, settings)
                indices = [edge.index for edge in loop_elems]
            else:
                loop_elems, message = collect_vertex_loop_vertices(context, obj, bm, settings)
                indices = [vert.index for vert in loop_elems]
            if message:
                self.report({"INFO"}, message)
                return {"CANCELLED"}
        layer = create_layer(settings, self.element_type, name=self.layer_name.strip() or None, color=self.color)
        if not assign_elements_to_layer(obj, self.element_type, layer.layer_id, element_indices=indices):
            collection = get_layer_collection(settings, self.element_type)
            collection.remove(len(collection) - 1)
            attr = element_meta(self.element_type)["next_id"]
            setattr(settings, attr, getattr(settings, attr) - 1)
            self.report({"WARNING"}, bi("Nothing assigned; new layer cancelled", "没有元素分配，已取消创建新图层"))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_assign_layer(bpy.types.Operator):
    bl_idname = "mesh.annotation_assign_layer"
    bl_label = bi("Assign Selection to Layer", "将选择分配到指定图层")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )
    layer_id: bpy.props.IntProperty()
    use_loop: bpy.props.BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = get_layer_by_id(settings, self.element_type, self.layer_id)
        if layer is None:
            self.report({"WARNING"}, bi("Layer not found", "未找到图层"))
            return {"CANCELLED"}
        indices = None
        if self.use_loop:
            bm = bmesh.from_edit_mesh(obj.data)
            if self.element_type == ELEMENT_FACE:
                loop_elems, message = collect_face_loop_faces(context, obj, bm, settings)
                indices = [face.index for face in loop_elems]
            elif self.element_type == ELEMENT_EDGE:
                loop_elems, message = collect_edge_loop_edges(context, obj, bm, settings)
                indices = [edge.index for edge in loop_elems]
            else:
                loop_elems, message = collect_vertex_loop_vertices(context, obj, bm, settings)
                indices = [vert.index for vert in loop_elems]
            if message:
                self.report({"INFO"}, message)
                return {"CANCELLED"}
        if not assign_elements_to_layer(obj, self.element_type, layer.layer_id, element_indices=indices):
            self.report({"WARNING"}, bi("Select at least one element", "请至少选择一个元素"))
            return {"CANCELLED"}
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_mark_seam_active(bpy.types.Operator):
    bl_idname = "mesh.annotation_mark_seam_active_face_layer"
    bl_label = bi("Mark Active Layer Seams", "当前层缝合边")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != "MESH" or context.mode != "EDIT_MESH":
            return False
        settings = getattr(obj, "mesh_annotations", None)
        if not settings:
            return False
        layer = active_layer(settings, ELEMENT_FACE)
        return layer is not None

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer = active_layer(settings, ELEMENT_FACE)
        count = mark_face_layer_edges_as_seam(obj, [layer.layer_id])
        if count == 0:
            self.report({"INFO"}, bi("No seams updated", "未更新缝合边"))
        else:
            self.report({"INFO"}, bi(f"Marked {count} edges", f"已标记 {count} 条边"))
        tag_view3d_redraw(context)
        return {"FINISHED"}


class MESH_OT_annotation_mark_seam_all(bpy.types.Operator):
    bl_idname = "mesh.annotation_mark_seam_all_face_layers"
    bl_label = bi("Mark All Layer Seams", "全部层缝合边")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != "MESH" or context.mode != "EDIT_MESH":
            return False
        settings = getattr(obj, "mesh_annotations", None)
        if not settings:
            return False
        return len(settings.face_layers) > 0

    def execute(self, context):
        obj = context.object
        settings = obj.mesh_annotations
        layer_ids = [layer.layer_id for layer in settings.face_layers]
        count = mark_face_layer_edges_as_seam(obj, layer_ids)
        if count == 0:
            self.report({"INFO"}, bi("No seams updated", "未更新缝合边"))
        else:
            self.report({"INFO"}, bi(f"Marked {count} edges", f"已标记 {count} 条边"))
        tag_view3d_redraw(context)
        return {"FINISHED"}

class MESH_OT_annotation_clear_selected(bpy.types.Operator):
    bl_idname = "mesh.annotation_clear_selected"
    bl_label = bi("Clear Annotation From Selected", "清除选中元素的标注")
    bl_options = {"REGISTER", "UNDO"}

    element_type: bpy.props.EnumProperty(
        name="Element",
        items=(
            (ELEMENT_FACE, "Face", "Face layer"),
            (ELEMENT_EDGE, "Edge", "Edge layer"),
            (ELEMENT_VERTEX, "Vertex", "Vertex layer"),
        ),
        default=ELEMENT_FACE,
    )
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ("ALL", "All Layers", "Remove all annotations from the selection"),
            ("TOP", "Top Layer Only", "Remove only the most recently assigned annotation layer"),
        ),
        default="ALL",
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def execute(self, context):
        obj = context.object
        clear_elements_from_layer(obj, self.element_type, -1, only_selected=True, mode=self.mode)
        tag_view3d_redraw(context)
        return {"FINISHED"}


class VIEW3D_MT_mesh_annotation_context(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mesh_annotation_context"
    bl_label = bi("Mesh Annotation", "网格标注")

    def draw(self, context):
        layout = self.layout
        obj = context.object
        if not obj or obj.type != "MESH" or context.mode != "EDIT_MESH":
            layout.label(text=bi("Switch to Edit Mode to use annotations", "请进入编辑模式以使用标注"), icon="INFO")
            return
        layout.menu("VIEW3D_MT_mesh_annotation_add", text=bi("Add", "添加"), icon="ADD")
        layout.menu("VIEW3D_MT_mesh_annotation_remove", text=bi("Remove", "删除"), icon="TRASH")


class VIEW3D_PT_mesh_annotation(bpy.types.Panel):
    bl_label = bi("Mesh Annotation", "网格标注")
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = bi("Mesh Annotation", "网格标注")

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        settings = obj.mesh_annotations
        layout.prop(settings, "enable_overlay", text=bi("Show Overlay", "显示叠加"))
        layout.prop(settings, "overlay_line_width", text=bi("Edge Thickness", "线条粗细"))
        layout.prop(settings, "overlay_edge_trim", text=bi("Edge Shortening", "线条截断"))
        layout.prop(settings, "overlay_face_offset", text=bi("Face Offset", "面偏移"))
        layout.prop(settings, "overlay_point_size", text=bi("Vertex Size", "点大小"))
        layout.prop(settings, "overlay_alpha_multiplier", text=bi("Overlay Opacity", "整体透明度"))
        layout.prop(settings, "overlay_show_backfaces", text=bi("Show Through Mesh", "背面可见"))
        layout.prop(settings, "debug_output", text=bi("Debug Output", "调试输出"))
        layout.prop(settings, "solo_active", text=bi("Solo Active Layer", "仅显示当前层"))
        if context.mode != "EDIT_MESH":
            layout.label(text=bi("Enter Edit Mode to assign elements", "进入编辑模式以分配图层"), icon="INFO")
        for element_type in ELEMENT_TYPES:
            self.draw_layer_section(layout, context, obj, settings, element_type)

    def draw_layer_section(self, parent_layout, context, obj, settings, element_type):
        selection_label, loop_label, header_label = element_labels(element_type)
        head_en, head_zh = header_label
        box = parent_layout.box()
        row_header = box.row()
        row_header.label(text=bi(head_en, head_zh), icon=element_meta(element_type)["icon"])
        row = box.row()
        row.template_list(
            "MESH_UL_annotation_layers",
            element_type,
            settings,
            element_meta(element_type)["collection"],
            settings,
            element_meta(element_type)["active_index"],
            rows=3,
        )
        col = row.column(align=True)
        op_add = col.operator("mesh.annotation_layer_add", icon="ADD", text="")
        op_add.element_type = element_type
        op_remove = col.operator("mesh.annotation_layer_remove", icon="REMOVE", text="")
        op_remove.element_type = element_type
        move_up = col.operator("mesh.annotation_layer_move", icon="TRIA_UP", text="")
        move_up.element_type = element_type
        move_up.direction = "UP"
        move_down = col.operator("mesh.annotation_layer_move", icon="TRIA_DOWN", text="")
        move_down.element_type = element_type
        move_down.direction = "DOWN"

        layer = active_layer(settings, element_type)
        if layer:
            info = box.column(align=True)
            count = count_elements_for_layer(obj, element_type, layer.layer_id)
            sel_en, sel_zh = selection_label
            info.label(text=bi(f"Active: {layer.name} ({count} {sel_en})", f"当前：{layer.name}（{count} 个{sel_zh}）"))
            row_info = info.row(align=True)
            op = row_info.operator("mesh.annotation_select_layer", text=bi("Select Elements", "选中图层元素"))
            op.layer_id = layer.layer_id
            op.element_type = element_type
            picker = info.operator(
                "mesh.annotation_activate_from_selection",
                text=bi("Pick From Selection", "从选择拾取"),
                icon="EYEDROPPER",
            )
            picker.element_type = element_type
        if context.mode == "EDIT_MESH":
            row_assign = box.row(align=True)
            assign_active = row_assign.operator(
                "mesh.annotation_assign_active",
                text=bi("Assign Selected", "分配选中"),
            )
            assign_active.element_type = element_type
            assign_loop = row_assign.operator(
                "mesh.annotation_assign_loop",
                text=bi("Assign Loop", "分配循环"),
            )
            assign_loop.element_type = element_type
            row_new = box.row(align=True)
            new_layer = row_new.operator(
                "mesh.annotation_assign_new_layer",
                text=bi("Selected → New Layer", "选中 → 新图层"),
                icon="ADD",
            )
            new_layer.element_type = element_type
            new_layer.use_loop = False
            new_layer.skip_dialog = True
            new_loop = row_new.operator(
                "mesh.annotation_assign_new_layer",
                text=bi("Loop → New Layer", "循环 → 新图层"),
                icon="ADD",
            )
            new_loop.element_type = element_type
            new_loop.use_loop = True
            new_loop.skip_dialog = True
            if element_type == ELEMENT_FACE:
                seam_row = box.row(align=True)
                seam_row.operator(
                    "mesh.annotation_mark_seam_active_face_layer",
                    text=bi("Mark Seams (Layer)", "当前层缝合"),
                    icon="MOD_UVPROJECT",
                )
                seam_row.operator(
                    "mesh.annotation_mark_seam_all_face_layers",
                    text=bi("Mark Seams (All)", "全部层缝合"),
                    icon="MOD_UVPROJECT",
                )
            clear_op = box.operator(
                "mesh.annotation_clear_selected",
                text=bi("Clear Selected", "清除选中"),
                icon="X",
            )
            clear_op.element_type = element_type
            clear_op.mode = "ALL"
        else:
            box.label(text=bi("Enter Edit Mode to edit assignments", "进入编辑模式以调整分配"), icon="INFO")


def draw_context_menu(self, context):
    obj = context.object
    if not obj or obj.type != "MESH" or context.mode != "EDIT_MESH":
        return
    layout = self.layout
    layout.separator()
    layout.menu(
        "VIEW3D_MT_mesh_annotation_context",
        text=bi("Mesh Annotation", "网格标注"),
        icon="GROUP_VCOL",
    )


classes = (
    MeshAnnotationPreferences,
    MeshAnnotationLayer,
    MeshAnnotationSettings,
    MESH_UL_annotation_layers,
    MESH_OT_annotation_layer_add,
    MESH_OT_annotation_layer_remove,
    MESH_OT_annotation_layer_move,
    MESH_OT_annotation_assign_active,
    MESH_OT_annotation_select_layer,
    MESH_OT_annotation_activate_from_selection,
    MESH_OT_annotation_assign_loop,
    MESH_OT_annotation_assign_new_layer,
    MESH_OT_annotation_assign_layer,
    MESH_OT_annotation_mark_seam_active,
    MESH_OT_annotation_mark_seam_all,
    MESH_OT_annotation_clear_selected,
    VIEW3D_MT_mesh_annotation_type_assign_selected_active,
    VIEW3D_MT_mesh_annotation_type_assign_selected_new,
    VIEW3D_MT_mesh_annotation_type_assign_selected_existing,
    VIEW3D_MT_mesh_annotation_type_assign_loop_active,
    VIEW3D_MT_mesh_annotation_type_assign_loop_new,
    VIEW3D_MT_mesh_annotation_type_assign_loop_existing,
    VIEW3D_MT_mesh_annotation_type_clear_selected_all,
    VIEW3D_MT_mesh_annotation_type_clear_selected_top,
    VIEW3D_MT_mesh_annotation_add,
    VIEW3D_MT_mesh_annotation_add_selected,
    VIEW3D_MT_mesh_annotation_add_loop,
    VIEW3D_MT_mesh_annotation_remove,
    VIEW3D_MT_mesh_annotation_remove_selected,
    VIEW3D_MT_mesh_annotation_context,
    VIEW3D_PT_mesh_annotation,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.mesh_annotations = bpy.props.PointerProperty(type=MeshAnnotationSettings)
    register_draw_handler()
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.append(draw_context_menu)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(draw_context_menu)
    unregister_draw_handler()
    del bpy.types.Object.mesh_annotations
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
