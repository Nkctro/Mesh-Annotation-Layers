# Mesh Annotation Layers

[English](#english) | [Chinese (中文)](#chinese-中文)

---

## English

### Overview

**Mesh Annotation Layers** is a topology assistance and annotation addon for Blender. Create and edit colored face, edge, and vertex layers in **Edit Mode**, then keep those guides visible while modeling, sculpting, or painting weights without modifying material or vertex color data.

### Features

- **Multiple annotation layers** for vertices, edges, and faces with per-object storage
- **Flexible assignments** including assign selected, assign loop, and one-click create-new-layer workflows
- **Custom overlay styling** with per-layer colors plus controls for opacity, line width, vertex size, independent face/edge/vertex offsets, edge trimming, and through-mesh visibility
- **Selection utilities** to pick from selection, select layer elements, or clear/remove assignments quickly
- **Optional propagation toggle** lets you decide if newly extruded or duplicated geometry should inherit existing annotations
- **Viewport context menu tools** for seam marking and faster access to layer actions
- **Bilingual interface** that can follow Blender, force English, force Chinese, or show both labels
- **Non-destructive workflow** that leaves geometry, materials, and vertex colors untouched
- **Persistent data** saved inside the .blend file alongside your meshes
- **Cross-mode visibility** in Object, Weight Paint, Vertex Paint, Sculpt, and Texture Paint modes
- **Compact type workspace** that shows one face/edge/vertex layer stack at a time and follows Edit Mode selection type
- **Interaction-aware caching** that avoids rebuilding annotation geometry for ordinary paint strokes and throttles expensive evaluated updates while editing dense meshes

### Installation

#### Option 1: Install as ZIP (Recommended)

1. Download or create the distribution ZIP file (see [Packaging](#packaging) below)
2. Open Blender and go to `Edit > Preferences > Add-ons`
3. Click `Install...` and select the ZIP file
4. Enable the addon by checking the box next to "Mesh: Mesh Annotation Layers"

#### Option 2: Manual Installation

1. Clone or download this repository
2. Copy the `mesh_annotation_layers` folder to your Blender addons directory:
   - Windows: `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`
   - macOS: `/Users/$USER/Library/Application Support/Blender/<version>/scripts/addons/`
   - Linux: `~/.config/blender/<version>/scripts/addons/`
3. Restart Blender or refresh the addons list
4. Go to `Edit > Preferences > Add-ons` and search for "Mesh Annotation Layers"
5. Enable the addon by checking the box

#### Packaging

To create a distribution ZIP file:
```bash
python3 package.py
```
This will create a ZIP file in the `dist/` folder that can be installed directly in Blender.

**Note:** This addon is compliant with Blender's extension platform requirements (Blender 4.2+) and includes a `blender_manifest.toml` file with proper metadata for the new extension system.

### Usage

#### Accessing the Panel

1. Select a mesh object
2. Open the **Sidebar** (N key)
3. Navigate to the **Mesh Annotation** tab
4. Enter **Edit Mode** when you need to create or change assignments; existing annotations remain visible in other modes

#### Creating Layers

1. Click the **+** button to add a new annotation layer
2. The layer will appear in the list with a random color
3. Click on a layer to make it active (highlighted)
4. Rename layers by clicking on their names

#### Assigning Elements to Layers

1. Select the mesh elements (vertices, edges, or faces) you want to annotate.
2. Use the assignment controls:
   - **Assign Selected**: Add the current selection to the active layer.
   - **Assign Loop**: Capture the detected edge or face loop and add it to the active layer.
   - **Selected -> New Layer**: Create a new layer and move the current selection there in one step.
   - **Loop -> New Layer**: Create a new layer directly from the detected loop.
3. The selected elements or loop will be overlaid with the layer's color.

#### Managing Layers

- **Add Layer**: Click the **+** button
- **Remove Layer**: Select a layer and click the **-** button
- **Toggle Visibility**: Click the eye icon next to a layer
- **Change Color**: Click the color swatch to open the color picker
- **Pick From Selection**: Use the eyedropper button to activate the layer that matches the current selection
- **Mark Seams**: In face mode, convert the active or all face layers into UV seams with the seam buttons

#### Selection Tools

- **Select Layer Elements**: Highlight every element currently assigned to the active layer
- **Remove Selected**: Remove only the selected elements from the active layer
- **Clear Selected**: Clear the entire active layer in one click

#### Overlay Controls

- Open the collapsed **Display** subpanel for detailed appearance controls
- **Show Overlay** toggles annotations on or off globally
- **Edge Thickness** controls overlay line width
- **Edge Shortening** trims overlay lines closer to the middle of an edge
- **Face Offset** lifts face overlays away from the surface to reduce z-fighting
- **Edge Offset** lifts edge overlays along the evaluated surface normal
- **Vertex Offset** lifts point markers along the evaluated surface normal
- **Vertex Size** adjusts the size of vertex markers
- **Overlay Opacity** sets a global transparency multiplier
- **Show Through Mesh** decides whether overlays appear on backfaces

#### Add-on Preferences

Open `Edit > Preferences > Add-ons > Mesh Annotation Layers` to configure:
- **Language** mode (Auto, English, Chinese (中文), or Both) for interface labels
- **Type Selection Submenu** to choose between a compact or split context menu layout

### Use Cases

1. **Topology Planning**: Mark different topology regions with different colors
2. **Edge Flow Tracking**: Annotate edge loops and flow patterns
3. **Retopology**: Mark areas that need rework or special attention
4. **Modeling Notes**: Create visual reminders for yourself or team members
5. **UV Mapping**: Mark UV seams and important boundaries
6. **Subdivision Planning**: Identify areas that need different subdivision levels

### Technical Details

- Compatible with Blender 4.2 and above
- Assignments are edited in Edit Mode; overlays also display in Object, Weight Paint, Vertex Paint, Sculpt, and Texture Paint modes
- Annotations are stored per object
- Uses GPU shader drawing for efficient overlay rendering
- Does not modify mesh geometry, materials, or vertex colors

### Keyboard Shortcuts

There are no default keyboard shortcuts, but you can add them in Blender's Keymap preferences if desired.

### Troubleshooting

**Problem**: Overlays are not visible
- **Solution**: Check that the layer visibility (eye icon) is enabled
- **Solution**: Check that the main Overlay toggle is enabled
- **Solution**: Adjust the opacity slider

**Problem**: Can't assign elements to a layer
- **Solution**: Make sure you have elements selected
- **Solution**: Ensure you're in Edit Mode
- **Solution**: Check that a layer is active (highlighted in the list)

**Problem**: Addon doesn't appear in the sidebar
- **Solution**: Make sure a mesh object is selected and the 3D View sidebar is open
- **Solution**: Check that the addon is enabled in Preferences

### License

This addon is released under the GPL-3.0 license.

---

## Chinese (中文)

### 概述

**Mesh Annotation Layers（网格标注层）** 是一个用于 Blender 的拓扑辅助与标注插件。你可以在**编辑模式**中创建和调整面、边、点彩色图层，并在建模、雕刻或权重绘制时持续查看这些拓扑辅助标记，同时不改变材质或顶点颜色数据。

### 功能特性

- **多图层标注**：针对顶点、边、面创建任意数量的图层，每个物体独立存储
- **灵活分配**：支持“分配选中”、“分配循环”以及一键新建图层并完成分配
- **叠加样式自定义**：提供颜色、透明度、线宽、点大小、面/边/点独立偏移、边截断和穿透显示等调节
- **快速工具**：可根据选择激活图层、选中整图层元素或快速清理分配
- **可选继承开关**：控制挤出或复制产生的新几何是否继承原有标注
- **视图菜单集成**：在 3D 视图右键菜单操作，可一键将面图层转换为 UV 缝
- **双语界面**：支持自动、仅英文、仅中文或双语标签
- **非破坏流程**：不会修改几何体、材质或顶点颜色数据
- **持久化数据**：标注内容随 .blend 文件一并保存
- **跨模式显示**：支持物体、权重绘制、顶点绘制、雕刻和纹理绘制模式
- **紧凑类型工作区**：一次只显示面、边或点的一组图层，并与编辑模式的选择类型联动
- **交互感知缓存**：普通绘制笔触不重建标注几何，密集网格编辑时限制昂贵的评估刷新频率

### 安装方法

#### 方法 1：安装 ZIP 文件（推荐）

1. 下载或创建发行版 ZIP 文件（见下方[打包](#打包)）
2. 打开 Blender，进入 `编辑 > 偏好设置 > 插件`
3. 点击 `安装...` 并选择 ZIP 文件
4. 在"Mesh Annotation Layers"旁边的复选框打勾以启用插件

#### 方法 2：手动安装

1. 克隆或下载此仓库
2. 将 `mesh_annotation_layers` 文件夹复制到 Blender 插件目录：
   - Windows: `%APPDATA%\Blender Foundation\Blender\<版本>\scripts\addons\`
   - macOS: `/Users/$USER/Library/Application Support/Blender/<版本>/scripts/addons/`
   - Linux: `~/.config/blender/<版本>/scripts/addons/`
3. 重启 Blender 或刷新插件列表
4. 进入 `编辑 > 偏好设置 > 插件` 并搜索 "Mesh Annotation Layers"
5. 在复选框打勾以启用插件

#### 打包

创建发行版 ZIP 文件：
```bash
python3 package.py
```
这将在 `dist/` 文件夹中创建可直接在 Blender 中安装的 ZIP 文件。

### 使用方法

#### 访问面板

1. 选择一个网格对象
2. 打开**侧边栏**（N 键）
3. 导航到 **Mesh Annotation（网格标注）** 选项卡
4. 需要创建或调整分配时进入**编辑模式**；已有标注可在其他模式中持续显示

#### 创建图层

1. 点击 **+** 按钮添加新的标注层
2. 图层将以随机颜色出现在列表中
3. 点击图层使其成为活动层（高亮显示）
4. 点击图层名称可以重命名

#### 将元素分配给图层

1. 选择要标注的网格元素（顶点、边或面），确保处于编辑模式。
2. 使用分配控制：
   - **分配选中**：将当前选区添加到活动图层。
   - **分配循环**：检测边/面循环，并添加到活动图层。
   - **选中 -> 新图层**：一键新建图层，并将当前选区移入其中。
   - **循环 -> 新图层**：根据检测的循环直接创建新图层。
3. 选中或循环将用图层的颜色进行叠加显示。

#### 管理图层

- **添加图层**：点击 **+** 按钮
- **删除图层**：选择一个图层并点击 **-** 按钮
- **切换可见性**：点击图层旁边的眼睛图标
- **更改颜色**：点击色块打开颜色选择器
- **根据选择激活图层**：使用吸管 “Pick From Selection” 按钮激活匹配当前选区的图层
- **标记接缝**：在面模式下，使用 UV 接缝按钮将当前或全部面图层转换为 UV 缝

#### 选择工具

- **Select Layer Elements（选择图层元素）**：高亮显示活动图层中的所有元素
- **Remove Selected（移除选中）**：仅移除选区内的元素
- **Clear Selected（清除选中）**：一键清理活动图层的所有分配

#### 叠加显示调整

- 展开折叠的**显示设置**子面板可调整详细外观
- **显示覆盖层**：总开关用于全局显示/隐藏标注
- **线条粗细**：调整边线的阈值
- **线条截断**：使线条更接近边的中点
- **面偏移**：顺着表面法线提升叠加
- **边偏移**：沿评估后表面法线抬高边标注
- **点偏移**：沿评估后表面法线抬高点标记
- **点大小**：控制顶点标识的大小
- **覆盖透明度**：设置全局透明度倍率
- **背面可见**：控制是否在背面显示标注

#### 插件偏好设置

在 `Edit > Preferences > Add-ons > Mesh Annotation Layers` 中可设置：
- **语言**：自动、仅英文、仅中文或双语标签
- **类型子菜单**：控制是否在右键菜单中拆分元素类型

### 使用场景

1. **拓扑规划**：用不同颜色标记不同的拓扑区域
2. **边流追踪**：标注边循环和流向模式
3. **重新拓扑**：标记需要重做或特别注意的区域
4. **建模笔记**：为自己或团队成员创建可视化提醒
5. **UV 映射**：标记 UV 接缝和重要边界
6. **细分规划**：识别需要不同细分级别的区域

### 技术细节

- 兼容 Blender 4.2 及以上版本
- 在编辑模式中调整分配；物体、权重绘制、顶点绘制、雕刻和纹理绘制模式也会显示标注
- 标注按对象存储
- 使用 GPU 着色器绘制实现高效的叠加渲染
- 不修改网格几何体、材质或顶点颜色

### 键盘快捷键

默认没有键盘快捷键，但如果需要，你可以在 Blender 的键盘映射偏好设置中添加。

### 故障排除

**问题**：叠加层不可见
- **解决方案**：检查图层可见性（眼睛图标）是否已启用
- **解决方案**：检查顶部“显示标注”总开关是否启用
- **解决方案**：调整不透明度滑块

**问题**：无法将元素分配给图层
- **解决方案**：确保你已选择元素
- **解决方案**：确保你处于编辑模式
- **解决方案**：检查图层是否处于活动状态（在列表中高亮显示）

**问题**：插件不出现在侧边栏中
- **解决方案**：确保已选择网格对象并打开 3D 视图侧边栏
- **解决方案**：检查插件是否在偏好设置中启用

### 许可证

此插件在 GPL-3.0 许可证下发布。
