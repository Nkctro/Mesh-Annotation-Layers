"""Centralized user-interface translations.

English text is the stable message key. Business, operator, and UI modules only
reference that key; translations never leak into feature logic.
"""

import bpy


ADDON_PACKAGE = __package__ or "mesh_annotation_layers"


ZH_CN = {
    "Face Layers": "面图层",
    "Edge Layers": "边图层",
    "Vertex Layers": "点图层",
    "faces": "面",
    "edges": "边",
    "vertices": "点",
    "face loop": "面循环",
    "edge loop": "边循环",
    "vertex path": "点循环",
    "Language": "语言",
    "Automatic": "自动",
    "English": "英语",
    "Chinese": "中文",
    "Use Blender's interface language; unsupported languages use English.": (
        "跟随 Blender 界面语言；不支持的语言使用英语。"
    ),
    "Always display the add-on in English.": "始终使用英语显示插件。",
    "Always display the add-on in Chinese.": "始终使用中文显示插件。",
    "Automatic language: {language}": "自动语言：{language}",
    "Auto follows Blender's interface language.": "自动模式会同步 Blender 的界面语言",
    "Type Selection Submenu": "右键添加类型子菜单",
    "No layers": "暂无图层",
    "Choose Element Type": "选择元素类型",
    "No action configured": "未配置操作",
    "Unsupported action": "未支持的操作",
    "Assign Selected to Active Layer": "将选中分配到当前层",
    "Assign Selected to New Layer": "将选中新建图层",
    "Assign Selected to Existing Layer": "添加选中到已有图层",
    "Assign Loop to Active Layer": "将循环分配到当前层",
    "Assign Loop to New Layer": "将循环分配到新图层",
    "Assign Loop to Existing Layer": "循环添加到已有图层",
    "Clear Selected (All Layers)": "清除选中（全部图层）",
    "Clear Selected (Top Layer)": "清除选中（顶部图层）",
    "Add": "添加",
    "Remove": "删除",
    "Selected Elements": "选中元素",
    "Loops / Paths": "循环 / 路径",
    "Remove Selected": "删除选中",
    "Select at least two faces to define the loop": "请选择至少两个面来确定循环",
    "Unable to derive a face loop from the selection": "无法根据选择推导出面循环",
    "No face loop passes through every selected face": "没有一个面循环能够覆盖所有已选面",
    "Multiple face loops detected; refine your selection": "检测到多个面循环，请精细调整选区",
    "No active 3D View found": "无可用的3D视图，无法派生循环",
    "Unable to resolve a loop from the current selection": "无法从当前选择推导循环",
    "Select at least one edge to derive a loop": "请选择至少一条边以推导循环",
    "Unable to resolve an edge loop": "无法生成边循环",
    "Selected edges are not on the same loop": "所选边不在同一个循环上",
    "Select at least two vertices to derive a loop": "请选择至少两个顶点以推导循环",
    "No vertex loop passes through every selected vertex": "没有一条顶点循环能够覆盖所有已选顶点",
    "Multiple vertex loops detected; refine your selection": "检测到多条顶点循环，请精细调整选区",
    "Add Annotation Layer": "新增标注图层",
    "Remove Annotation Layer": "移除标注图层",
    "Reorder Annotation Layer": "调整图层顺序",
    "Assign Selection to Active Layer": "将选中元素分配到当前层",
    "Select Elements in Layer": "选择图层元素",
    "Pick Active Layer From Selection": "从选择中激活图层",
    "Annotate Vertices by Valence": "按度数标注顶点",
    "Annotate Valence to New Layer": "度数标注到新图层",
    "Assign Selection to New Layer": "将选择分配到新图层",
    "Assign Selection to Layer": "将选择分配到指定图层",
    "Mark Active Layer Seams": "当前层缝合边",
    "Mark All Layer Seams": "全部层缝合边",
    "Clear Annotation From Selected": "清除选中元素的标注",
    "Switch Annotation Type": "切换标注类型",
    "Edit Annotations": "编辑标注",
    "Switch to Edit Mode to change annotation assignments": "切换到编辑模式以调整标注分配",
    "Mesh Annotation": "网格标注",
    "Display": "显示设置",
    "Select a mesh object": "请选择一个网格对象",
    "No active layer selected": "未选择图层",
    "Select at least one element": "请至少选择一个元素",
    "Layer is empty": "图层内没有元素",
    "Selected elements do not belong to any layer": "所选元素未包含在任何图层中",
    "Layer not found": "未找到图层",
    "No active vertex layer selected": "未选择顶点图层",
    "No vertices found with that valence": "未找到匹配度数的顶点",
    "Failed to assign vertices": "标注失败",
    "Nothing assigned; new layer cancelled": "没有元素分配，已取消创建新图层",
    "Annotated {count} vertices": "已标注 {count} 个顶点",
    "Layer Name": "图层名称",
    "Color": "颜色",
    "No seams updated": "未更新缝合边",
    "Marked {count} edges": "已标记 {count} 条边",
    "Switch to Edit Mode to use annotations": "请进入编辑模式以使用标注",
    "Overlay": "显示标注",
    "Solo": "仅当前层",
    "Faces": "面",
    "Edges": "边",
    "Vertices": "点",
    "Object Mode": "物体模式",
    "Weight Paint": "权重绘制",
    "Vertex Paint": "顶点绘制",
    "Sculpt Mode": "雕刻模式",
    "Texture Paint": "纹理绘制",
    "Visible in {mode}; assignments are read-only": "{mode}中持续显示；分配为只读",
    "Switch to Edit Mode to Edit": "切换到编辑模式编辑",
    "Active · {name} · {count} {selection}": "当前 · {name} · {count} 个{selection}",
    "No layers yet — use + to create one": "还没有图层，请用 + 新建",
    "Select Layer": "选中图层元素",
    "Pick Layer": "从选择拾取",
    "Add Selected": "添加选中",
    "Add Loop": "添加循环",
    "Selected → New Layer": "选中 → 新图层",
    "Loop → New Layer": "循环 → 新图层",
    "Valence": "度数",
    "Annotate": "标注",
    "Valence → New Layer": "度数 → 新图层",
    "Mark Seams (Layer)": "当前层缝合",
    "Mark Seams (All)": "全部层缝合",
    "Remove Annotations From Selected": "移除选中元素的标注",
    "Opacity": "整体透明度",
    "Show Through Mesh": "穿透显示",
    "Surface Offset": "表面偏移",
    "Thickness": "线条粗细",
    "Shortening": "线条截断",
    "Point Size": "点大小",
    "Debug Output": "调试输出",
    "Create a new annotation layer for the current element type.": (
        "为当前元素类型创建新的标注图层。"
    ),
    "Delete the active annotation layer and remove its assignments.": (
        "删除当前标注图层及其全部分配。"
    ),
    "Move the active layer up or down in the overlay order.": (
        "在标注叠放顺序中向上或向下移动当前图层。"
    ),
    "Add the selected elements to the active annotation layer.": (
        "将所选元素添加到当前标注图层。"
    ),
    "Select every mesh element assigned to this layer.": (
        "选择所有分配到此图层的网格元素。"
    ),
    "Make the layer used most by the current selection active.": (
        "将当前选择中使用最多的图层设为活动图层。"
    ),
    "Derive a complete loop or path from the selection and add it to the active layer.": (
        "从当前选择推导完整循环或路径，并添加到活动图层。"
    ),
    "Add every vertex with the chosen valence to the active vertex layer.": (
        "将符合所选度数的全部顶点添加到活动顶点图层。"
    ),
    "Create a vertex layer and add every vertex with the chosen valence.": (
        "创建顶点图层，并添加所有符合所选度数的顶点。"
    ),
    "Create a new layer and add the selection or derived loop to it.": (
        "创建新图层，并将当前选择或推导出的循环添加到其中。"
    ),
    "Add the selection or derived loop to this existing layer.": (
        "将当前选择或推导出的循环添加到此已有图层。"
    ),
    "Mark the boundary edges of the active face layer as UV seams.": (
        "将活动面图层的边界边标记为 UV 缝合边。"
    ),
    "Mark the boundary edges of every face layer as UV seams.": (
        "将所有面图层的边界边标记为 UV 缝合边。"
    ),
    "Remove annotation assignments from the selected elements.": (
        "移除所选元素的标注分配。"
    ),
    "Switch the annotation workspace and mesh selection mode.": (
        "切换标注工作区和网格选择模式。"
    ),
    "Show or hide annotation overlays in the viewport.": (
        "在视图中显示或隐藏标注覆盖层。"
    ),
    "Show only the active annotation layer for each element type.": (
        "每种元素类型仅显示其活动标注图层。"
    ),
    "Show or hide this annotation layer.": "显示或隐藏此标注图层。",
}


LANGUAGE_ITEM_KEYS = (
    (
        "AUTO",
        "Automatic",
        "Use Blender's interface language; unsupported languages use English.",
    ),
    ("EN", "English", "Always display the add-on in English."),
    ("ZH", "Chinese", "Always display the add-on in Chinese."),
)
_language_items_cache = {}


def addon_preferences():
    context = getattr(bpy, "context", None)
    preferences = getattr(context, "preferences", None)
    if preferences is None:
        return None
    addon = preferences.addons.get(ADDON_PACKAGE)
    return addon.preferences if addon else None


def blender_locale() -> str:
    view = getattr(getattr(bpy.context, "preferences", None), "view", None)
    language = getattr(view, "language", "")
    if not language or language in {"DEFAULT", "AUTO"}:
        language = getattr(getattr(bpy.app, "translations", None), "locale", "")
    return language or ""


def language_from_locale(locale: str) -> str:
    """Map only supported Blender locales; everything else uses English."""

    return "ZH" if (locale or "").lower().startswith("zh") else "EN"


def language_mode() -> str:
    preferences = addon_preferences()
    mode = getattr(preferences, "language_display", "AUTO")
    if mode in {"EN", "ZH"}:
        return mode
    return language_from_locale(blender_locale())


def language_items(_self, _context):
    """Return retained, dynamically translated enum items."""

    mode = language_mode()
    if mode not in _language_items_cache:
        _language_items_cache[mode] = tuple(
            (identifier, tr(label), tr(description))
            for identifier, label, description in LANGUAGE_ITEM_KEYS
        )
    return _language_items_cache[mode]


def redraw_ui(context=None):
    context = context or getattr(bpy, "context", None)
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None:
        return
    for window in window_manager.windows:
        screen = window.screen
        if screen is None:
            continue
        for area in screen.areas:
            area.tag_redraw()


def _format(message: str, values: dict) -> str:
    if not values:
        return message
    try:
        return message.format_map(values)
    except (KeyError, ValueError, AttributeError):
        # A malformed translation must never break an operator or panel draw.
        return message


def tr(message: str, **values) -> str:
    """Translate and format a stable English message key."""

    english = _format(message, values)
    mode = language_mode()
    if mode == "EN":
        return english

    chinese = _format(ZH_CN.get(message, message), values)
    return chinese


class LocalizedDescription:
    """Give Blender operators a tooltip resolved at hover time."""

    tooltip_key = ""

    @classmethod
    def description(cls, _context, _properties):
        return tr(cls.tooltip_key) if cls.tooltip_key else ""
