# 版本对比：1.0.1 vs 1.1.1 | Version Comparison: 1.0.1 vs 1.1.1

[中文](#中文版本对比) | [English](#english-version-comparison)

---

## 中文版本对比

### 📋 版本信息

- **v1.0.1**: 2025年10月29日发布
- **v1.1.1**: 当前主分支版本（最新）

### 🎯 核心改进概述

版本 1.1.1 是对 1.0.1 的重大升级，主要集中在**代码架构重构**、**新功能添加**和**用户体验改善**三个方面。代码从单文件结构重构为模块化包结构，总代码量增加约 15,000 字符。

### ✨ 主要新功能

#### 1. **UV Seam 标记功能** ⭐
v1.1.1 新增了两个操作符，用于根据标注层自动标记 UV 接缝：
- `MESH_OT_annotation_mark_seam_active` - 将活动图层的边标记为 UV 接缝
- `MESH_OT_annotation_mark_seam_all` - 将所有可见图层的边标记为 UV 接缝

这个功能对 UV 展开工作流程特别有用，可以直接从标注层生成 UV 接缝。

#### 2. **语言显示模式** 🌐
新增了偏好设置系统，支持四种语言显示模式：
- **自动模式**: 跟随 Blender 界面语言
- **英文模式**: 始终显示英文
- **中文模式**: 始终显示中文
- **双语模式**: 同时显示中英文（例如："Face Layers / 面图层"）

这大大改善了多语言用户的体验。

#### 3. **上下文菜单集成** 🖱️
新增了右键上下文菜单集成选项：
- 可配置的类型选择子菜单
- 快速访问标注层操作
- 更流畅的工作流程

#### 4. **增强的元素类型系统** 📐
引入了统一的元素类型定义系统 (`ELEMENT_DEFS`)：
- 面（Face）图层
- 边（Edge）图层
- 顶点（Vertex）图层

每种类型都有独立的：
- 图标标识
- 数据存储
- 选择模式
- 颜色种子

#### 5. **改进的 GPU 渲染** 🎨
- 新增边缘绘制偏移量 (`EDGE_DRAW_OFFSET = 0.0008`)
- 改进的着色器批处理渲染
- 更高效的 3D 视口重绘机制 (`tag_view3d_redraw`)

### 🏗️ 架构改进

#### 1. **项目结构重组**
```
v1.0.1:
└── mesh_annotation_layers.py (单文件)

v1.1.1:
└── mesh_annotation_layers/ (包结构)
    └── __init__.py (主模块)
```

#### 2. **代码组织**
- 从 2,247 行增加到 2,621 行（+374 行）
- 更好的模块化和代码分离
- 新增了常量定义系统（`ELEMENT_DEFS`）
- 改进的辅助函数库

#### 3. **插件元数据更新**
```python
# v1.0.1
"author": "Mesh Annotation Layers Team",
"version": (1, 0, 0),
"location": "3D View > Sidebar > Annotation Layers",
"category": "Mesh",

# v1.1.1
"author": "Nkctro",
"version": (1, 1, 1),
"location": "3D Viewport > Sidebar > Mesh Annotation",
"category": "3D View",
```

### 📚 文档改进

#### 新增文档
1. **SECURITY.md** - 安全政策和漏洞报告指南
2. **.github/** 目录结构：
   - Issue 模板（Bug Report, Feature Request, Question）
   - Pull Request 模板
   - 工作流配置（自动标签、摘要生成）
   - 测试清单迁移

#### 改进的文档
- **README.md**: 新增打包说明和更详细的安装选项
- **INSTALL.md**: 更新了安装流程和故障排除
- **删除**: PROJECT_SUMMARY.md（不再需要）

### 🛠️ 开发工具改进

#### 1. **GitHub 集成**
- 新增 Issue 模板系统
- 新增 PR 模板
- 自动标签工作流
- 代码摘要自动生成

#### 2. **编辑器配置**
- `.editorconfig` - 统一代码风格
- `.gitattributes` - Git 属性配置
- `.gitignore` - 改进的忽略规则

#### 3. **打包脚本**
`package.py` 更新以支持新的包结构。

### 📊 操作符对比

| 功能分类 | v1.0.1 | v1.1.1 | 变化 |
|---------|--------|--------|------|
| 操作符总数 | 10 | 12 | +2 |
| 面板数量 | 1 | 1 | 0 |
| 属性组 | 2 | 2 | 0 |

**新增操作符**：
- ✅ `MESH_OT_annotation_mark_seam_active` - UV 接缝标记（活动层）
- ✅ `MESH_OT_annotation_mark_seam_all` - UV 接缝标记（所有层）

### 🎨 用户界面改进

1. **偏好设置面板**：新增插件偏好设置页面
2. **双语支持**：通过 `bi()` 函数实现动态语言切换
3. **改进的视觉反馈**：更好的 GPU 渲染和视口更新

### 🔧 技术变更

#### 导入库变化
**v1.0.1**:
```python
import bpy
from bpy.props import (StringProperty, FloatVectorProperty, ...)
from bpy.types import (PropertyGroup, UIList, ...)
```

**v1.1.1**:
```python
import bpy
import bmesh
import colorsys
import json
import random
from collections import Counter, defaultdict
from mathutils import Vector
import gpu
from gpu_extras.batch import batch_for_shader
```

新增导入：`bmesh`, `colorsys`, `json`, `random`, `Counter`, `defaultdict`, `Vector`, `gpu`, `batch_for_shader`

#### 新增工具函数
- `get_addon_prefs()` - 获取插件偏好设置
- `resolve_language_mode()` - 解析语言模式
- `bi(en, zh)` - 双语文本处理
- `tag_view3d_redraw()` - 3D 视口重绘标记

### 📦 安装方式改进

**v1.0.1**: 
- 手动复制文件夹到插件目录

**v1.1.1**:
- ✅ 推荐：通过 ZIP 文件安装（使用 `package.py` 打包）
- ✅ 可选：手动复制文件夹
- ✅ 自动版本检测

### 🐛 稳定性改进

1. 更好的错误处理
2. 改进的属性访问保护
3. 增强的 GPU 资源管理
4. 更稳定的视口渲染

### 💡 使用场景扩展

**新增使用场景**（v1.1.1）：
- ✨ **UV 接缝规划**：使用标注层直接生成 UV 接缝
- ✨ **自动化工作流**：通过标记功能加速重复任务

**保留场景**（两个版本都支持）：
- 拓扑规划
- 边流追踪
- 重新拓扑
- 建模笔记
- 细分规划

### 📈 文件变更统计

```
18 个文件修改
2,954 行新增
3,178 行删除
净增长: -224 行（重构导致代码更精简）
```

主要变更文件：
- ❌ `mesh_annotation_layers.py` (删除)
- ✅ `mesh_annotation_layers/__init__.py` (新增/重构)
- ✅ `.github/` 目录（新增完整的 GitHub 工作流）
- ✅ 各类配置文件（`.editorconfig`, `.gitattributes`, `.gitignore`）

### 🎯 升级建议

**推荐升级理由**：
1. ✅ 新的 UV 接缝标记功能
2. ✅ 更好的多语言支持
3. ✅ 改进的代码架构（更易维护）
4. ✅ 更完善的开发工具链
5. ✅ 更好的文档和社区支持

**升级步骤**：
1. 卸载 v1.0.1
2. 下载 v1.1.1 的 ZIP 包
3. 在 Blender 中安装新版本
4. 检查偏好设置中的语言选项

**注意事项**：
- ⚠️ 项目文件兼容（标注数据保留）
- ⚠️ 界面位置略有变化（从 "Annotation Layers" 到 "Mesh Annotation"）
- ⚠️ 插件类别从 "Mesh" 改为 "3D View"

---

## English Version Comparison

### 📋 Version Information

- **v1.0.1**: Released October 29, 2025
- **v1.1.1**: Current main branch version (latest)

### 🎯 Core Improvements Overview

Version 1.1.1 is a major upgrade from 1.0.1, focusing on **code architecture refactoring**, **new feature additions**, and **user experience improvements**. The code has been restructured from a single-file to a modular package structure, with approximately 15,000 characters of code added.

### ✨ Major New Features

#### 1. **UV Seam Marking Functionality** ⭐
v1.1.1 introduces two new operators for automatically marking UV seams based on annotation layers:
- `MESH_OT_annotation_mark_seam_active` - Mark active layer edges as UV seams
- `MESH_OT_annotation_mark_seam_all` - Mark all visible layer edges as UV seams

This feature is particularly useful for UV unwrapping workflows, allowing direct UV seam generation from annotation layers.

#### 2. **Language Display Modes** 🌐
New preference system supporting four language display modes:
- **Auto Mode**: Follows Blender's interface language
- **English Mode**: Always displays English
- **Chinese Mode**: Always displays Chinese
- **Both Mode**: Shows both English and Chinese simultaneously (e.g., "Face Layers / 面图层")

This greatly improves the experience for multilingual users.

#### 3. **Context Menu Integration** 🖱️
New right-click context menu integration options:
- Configurable type selection submenu
- Quick access to annotation layer operations
- Smoother workflow

#### 4. **Enhanced Element Type System** 📐
Introduced unified element type definition system (`ELEMENT_DEFS`):
- Face layers
- Edge layers
- Vertex layers

Each type has independent:
- Icon identification
- Data storage
- Selection mode
- Color seed

#### 5. **Improved GPU Rendering** 🎨
- New edge drawing offset (`EDGE_DRAW_OFFSET = 0.0008`)
- Improved shader batch rendering
- More efficient 3D viewport redraw mechanism (`tag_view3d_redraw`)

### 🏗️ Architecture Improvements

#### 1. **Project Structure Reorganization**
```
v1.0.1:
└── mesh_annotation_layers.py (single file)

v1.1.1:
└── mesh_annotation_layers/ (package structure)
    └── __init__.py (main module)
```

#### 2. **Code Organization**
- Increased from 2,247 to 2,621 lines (+374 lines)
- Better modularization and code separation
- New constant definition system (`ELEMENT_DEFS`)
- Improved helper function library

#### 3. **Plugin Metadata Updates**
```python
# v1.0.1
"author": "Mesh Annotation Layers Team",
"version": (1, 0, 0),
"location": "3D View > Sidebar > Annotation Layers",
"category": "Mesh",

# v1.1.1
"author": "Nkctro",
"version": (1, 1, 1),
"location": "3D Viewport > Sidebar > Mesh Annotation",
"category": "3D View",
```

### 📚 Documentation Improvements

#### New Documentation
1. **SECURITY.md** - Security policy and vulnerability reporting guidelines
2. **.github/** directory structure:
   - Issue templates (Bug Report, Feature Request, Question)
   - Pull Request template
   - Workflow configurations (auto-labeling, summary generation)
   - Testing checklist migration

#### Improved Documentation
- **README.md**: Added packaging instructions and more detailed installation options
- **INSTALL.md**: Updated installation process and troubleshooting
- **Removed**: PROJECT_SUMMARY.md (no longer needed)

### 🛠️ Development Tools Improvements

#### 1. **GitHub Integration**
- New Issue template system
- New PR template
- Auto-labeling workflow
- Automatic code summary generation

#### 2. **Editor Configuration**
- `.editorconfig` - Unified code style
- `.gitattributes` - Git attributes configuration
- `.gitignore` - Improved ignore rules

#### 3. **Packaging Script**
`package.py` updated to support new package structure.

### 📊 Operator Comparison

| Feature Category | v1.0.1 | v1.1.1 | Change |
|-----------------|--------|--------|--------|
| Total Operators | 10 | 12 | +2 |
| Panels | 1 | 1 | 0 |
| Property Groups | 2 | 2 | 0 |

**New Operators**:
- ✅ `MESH_OT_annotation_mark_seam_active` - UV seam marking (active layer)
- ✅ `MESH_OT_annotation_mark_seam_all` - UV seam marking (all layers)

### 🎨 User Interface Improvements

1. **Preferences Panel**: New addon preferences page
2. **Bilingual Support**: Dynamic language switching through `bi()` function
3. **Improved Visual Feedback**: Better GPU rendering and viewport updates

### 🔧 Technical Changes

#### Import Library Changes
**v1.0.1**:
```python
import bpy
from bpy.props import (StringProperty, FloatVectorProperty, ...)
from bpy.types import (PropertyGroup, UIList, ...)
```

**v1.1.1**:
```python
import bpy
import bmesh
import colorsys
import json
import random
from collections import Counter, defaultdict
from mathutils import Vector
import gpu
from gpu_extras.batch import batch_for_shader
```

New imports: `bmesh`, `colorsys`, `json`, `random`, `Counter`, `defaultdict`, `Vector`, `gpu`, `batch_for_shader`

#### New Utility Functions
- `get_addon_prefs()` - Get addon preferences
- `resolve_language_mode()` - Resolve language mode
- `bi(en, zh)` - Bilingual text processing
- `tag_view3d_redraw()` - Tag 3D viewport for redraw

### 📦 Installation Method Improvements

**v1.0.1**: 
- Manual folder copy to addons directory

**v1.1.1**:
- ✅ Recommended: Install via ZIP file (packaged with `package.py`)
- ✅ Optional: Manual folder copy
- ✅ Automatic version detection

### 🐛 Stability Improvements

1. Better error handling
2. Improved property access protection
3. Enhanced GPU resource management
4. More stable viewport rendering

### 💡 Extended Use Cases

**New Use Cases** (v1.1.1):
- ✨ **UV Seam Planning**: Generate UV seams directly from annotation layers
- ✨ **Automated Workflows**: Speed up repetitive tasks through marking features

**Retained Use Cases** (supported in both versions):
- Topology planning
- Edge flow tracking
- Retopology
- Modeling notes
- Subdivision planning

### 📈 File Change Statistics

```
18 files changed
2,954 lines added
3,178 lines deleted
Net change: -224 lines (refactoring made code more concise)
```

Major changed files:
- ❌ `mesh_annotation_layers.py` (removed)
- ✅ `mesh_annotation_layers/__init__.py` (added/refactored)
- ✅ `.github/` directory (complete GitHub workflow added)
- ✅ Various configuration files (`.editorconfig`, `.gitattributes`, `.gitignore`)

### 🎯 Upgrade Recommendations

**Reasons to Upgrade**:
1. ✅ New UV seam marking functionality
2. ✅ Better multilingual support
3. ✅ Improved code architecture (easier to maintain)
4. ✅ More complete development toolchain
5. ✅ Better documentation and community support

**Upgrade Steps**:
1. Uninstall v1.0.1
2. Download v1.1.1 ZIP package
3. Install new version in Blender
4. Check language options in preferences

**Considerations**:
- ⚠️ Project file compatibility (annotation data preserved)
- ⚠️ Slight interface location change (from "Annotation Layers" to "Mesh Annotation")
- ⚠️ Plugin category changed from "Mesh" to "3D View"

---

## 📝 Summary | 总结

### 中文总结

版本 1.1.1 相比 1.0.1 是一次**重大升级**，主要亮点包括：

1. **新功能**：UV 接缝自动标记
2. **多语言**：完善的双语支持系统
3. **架构**：从单文件重构为包结构
4. **开发**：完整的 GitHub 集成和开发工具
5. **文档**：更完善的文档和模板

这是一个**强烈推荐升级**的版本，特别是对需要 UV 展开工作流程和多语言支持的用户。

### English Summary

Version 1.1.1 compared to 1.0.1 is a **major upgrade**, with key highlights including:

1. **New Features**: Automatic UV seam marking
2. **Multilingual**: Complete bilingual support system
3. **Architecture**: Refactored from single file to package structure
4. **Development**: Complete GitHub integration and development tools
5. **Documentation**: More comprehensive documentation and templates

This is a **strongly recommended upgrade**, especially for users who need UV unwrapping workflows and multilingual support.

---

**Generated**: 2025-10-30  
**Repository**: [Nkctro/Mesh-Annotation-Layers](https://github.com/Nkctro/Mesh-Annotation-Layers)
