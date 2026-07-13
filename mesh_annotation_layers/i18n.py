"""Centralized user-interface translations.

English text is the stable message key. Business, operator, and UI modules only
reference that key; translations never leak into feature logic.
"""

import bpy


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
}


def _addon_preferences():
    context = getattr(bpy, "context", None)
    preferences = getattr(context, "preferences", None)
    if preferences is None:
        return None
    package = (__package__ or "").partition(".")[0]
    addon = preferences.addons.get(package)
    return addon.preferences if addon else None


def language_mode() -> str:
    preferences = _addon_preferences()
    mode = getattr(preferences, "language_display", "AUTO")
    if mode in {"EN", "ZH", "BOTH"}:
        return mode

    view = getattr(getattr(bpy.context, "preferences", None), "view", None)
    language = getattr(view, "language", "")
    if not language or language in {"DEFAULT", "AUTO"}:
        language = getattr(getattr(bpy.app, "translations", None), "locale", "")
    return "ZH" if (language or "").lower().startswith("zh") else "EN"


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
    if mode == "BOTH" and chinese != english:
        return f"{english} / {chinese}"
    return chinese
