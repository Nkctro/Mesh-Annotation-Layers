# Mesh Annotation Layers

[English](#english) | [中文](#中文)

---

## English

### Overview

**Mesh Annotation Layers** is a topology assistance and annotation addon for Blender. It allows you to add multiple colored overlay layers to mesh objects (faces, edges, vertices) in **Edit Mode**, helping you identify different regions, flow patterns, or modeling logic without modifying material or vertex color data.

### Features

- ✨ **Multiple Annotation Layers**: Create unlimited annotation layers for organizing your mesh
- 🎨 **Custom Colors**: Each layer can have its own color with adjustable opacity
- 📐 **Element Support**: Annotate vertices, edges, or faces independently
- 👁️ **Layer Visibility**: Toggle layer visibility on/off
- 🔄 **Non-Destructive**: Annotations don't modify mesh data, materials, or vertex colors
- 🎯 **Selection Tools**: Select all elements in a layer with one click
- 💾 **Persistent**: Annotations are saved with your Blender file

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

### Usage

#### Accessing the Panel

1. Select a mesh object
2. Enter **Edit Mode** (Tab key)
3. Open the **Sidebar** (N key)
4. Navigate to the **Annotation** tab

#### Creating Layers

1. Click the **+** button to add a new annotation layer
2. The layer will appear in the list with a random color
3. Click on a layer to make it active (highlighted)
4. Rename layers by clicking on their names

#### Assigning Elements to Layers

1. Select the mesh elements (vertices, edges, or faces) you want to annotate
2. Click one of the assignment buttons:
   - **Vertices**: Assign selected vertices
   - **Edges**: Assign selected edges
   - **Faces**: Assign selected faces
3. The selected elements will be overlaid with the layer's color

#### Managing Layers

- **Add Layer**: Click the **+** button
- **Remove Layer**: Select a layer and click the **-** button
- **Toggle Visibility**: Click the eye icon next to a layer
- **Change Color**: Click the color swatch to open the color picker
- **Adjust Opacity**: Use the "Opacity" slider at the bottom of the panel

#### Selection Tools

- **Select Layer Elements**: Select all elements currently assigned to the active layer
- **Remove Selected**: Remove selected elements from the active layer
- **Clear Layer**: Remove all elements from the active layer

### Use Cases

1. **Topology Planning**: Mark different topology regions with different colors
2. **Edge Flow Tracking**: Annotate edge loops and flow patterns
3. **Retopology**: Mark areas that need rework or special attention
4. **Modeling Notes**: Create visual reminders for yourself or team members
5. **UV Mapping**: Mark UV seams and important boundaries
6. **Subdivision Planning**: Identify areas that need different subdivision levels

### Technical Details

- Compatible with Blender 3.0 and above
- Works only in Edit Mode for mesh objects
- Annotations are stored per object
- Uses GPU shader drawing for efficient overlay rendering
- Does not modify mesh geometry, materials, or vertex colors

### Keyboard Shortcuts

There are no default keyboard shortcuts, but you can add them in Blender's Keymap preferences if desired.

### Troubleshooting

**Problem**: Overlays are not visible
- **Solution**: Check that the layer visibility (eye icon) is enabled
- **Solution**: Ensure you're in Edit Mode
- **Solution**: Adjust the opacity slider

**Problem**: Can't assign elements to a layer
- **Solution**: Make sure you have elements selected
- **Solution**: Ensure you're in Edit Mode
- **Solution**: Check that a layer is active (highlighted in the list)

**Problem**: Addon doesn't appear in the sidebar
- **Solution**: Make sure you're in Edit Mode with a mesh object selected
- **Solution**: Check that the addon is enabled in Preferences

### License

This addon is released under the GPL-3.0 license.

---

## 中文

### 概述

**Mesh Annotation Layers（网格标注层）** 是一个用于 Blender 的拓扑辅助与标注插件。它允许你在**编辑模式**下，为网格对象的面、边、顶点添加多个彩色叠加层，用以标识不同的区域、流向或建模逻辑，而不会改变材质或顶点颜色数据。

### 功能特性

- ✨ **多个标注层**：创建无限的标注层来组织你的网格
- 🎨 **自定义颜色**：每个层可以有自己的颜色和可调节的透明度
- 📐 **元素支持**：独立标注顶点、边或面
- 👁️ **图层可见性**：开关图层的显示/隐藏
- 🔄 **非破坏性**：标注不会修改网格数据、材质或顶点颜色
- 🎯 **选择工具**：一键选择图层中的所有元素
- 💾 **持久化**：标注会随 Blender 文件一起保存

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
2. 进入**编辑模式**（Tab 键）
3. 打开**侧边栏**（N 键）
4. 导航到 **Annotation（标注）** 选项卡

#### 创建图层

1. 点击 **+** 按钮添加新的标注层
2. 图层将以随机颜色出现在列表中
3. 点击图层使其成为活动层（高亮显示）
4. 点击图层名称可以重命名

#### 将元素分配给图层

1. 选择要标注的网格元素（顶点、边或面）
2. 点击分配按钮之一：
   - **Vertices（顶点）**：分配选中的顶点
   - **Edges（边）**：分配选中的边
   - **Faces（面）**：分配选中的面
3. 选中的元素将以图层的颜色覆盖显示

#### 管理图层

- **添加图层**：点击 **+** 按钮
- **删除图层**：选择一个图层并点击 **-** 按钮
- **切换可见性**：点击图层旁边的眼睛图标
- **更改颜色**：点击色块打开颜色选择器
- **调整透明度**：使用面板底部的"Opacity（不透明度）"滑块

#### 选择工具

- **Select Layer Elements（选择图层元素）**：选择当前分配给活动图层的所有元素
- **Remove Selected（移除选中）**：从活动图层中移除选中的元素
- **Clear Layer（清空图层）**：从活动图层中移除所有元素

### 使用场景

1. **拓扑规划**：用不同颜色标记不同的拓扑区域
2. **边流追踪**：标注边循环和流向模式
3. **重新拓扑**：标记需要重做或特别注意的区域
4. **建模笔记**：为自己或团队成员创建可视化提醒
5. **UV 映射**：标记 UV 接缝和重要边界
6. **细分规划**：识别需要不同细分级别的区域

### 技术细节

- 兼容 Blender 3.0 及以上版本
- 仅在网格对象的编辑模式下工作
- 标注按对象存储
- 使用 GPU 着色器绘制实现高效的叠加渲染
- 不修改网格几何体、材质或顶点颜色

### 键盘快捷键

默认没有键盘快捷键，但如果需要，你可以在 Blender 的键盘映射偏好设置中添加。

### 故障排除

**问题**：叠加层不可见
- **解决方案**：检查图层可见性（眼睛图标）是否已启用
- **解决方案**：确保你处于编辑模式
- **解决方案**：调整不透明度滑块

**问题**：无法将元素分配给图层
- **解决方案**：确保你已选择元素
- **解决方案**：确保你处于编辑模式
- **解决方案**：检查图层是否处于活动状态（在列表中高亮显示）

**问题**：插件不出现在侧边栏中
- **解决方案**：确保你在编辑模式下选择了网格对象
- **解决方案**：检查插件是否在偏好设置中启用

### 许可证

此插件在 GPL-3.0 许可证下发布。