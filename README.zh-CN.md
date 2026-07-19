# Mesh Annotation Layers（网格标注层）

[English](README.md)

面向 Blender 拓扑工作的面、边、点彩色标注层。标注在编辑模式中维护，随网格保存，
并通过视口叠加绘制，不占用材质或顶点颜色。

## 主要功能

- 面、边、点分别拥有独立的图层栈。
- 可分配当前选区、检测到的循环/路径或指定连接数的顶点。
- 支持选择整层、从当前选区激活图层以及清理标注。
- 可将面图层边界转换为 UV 缝。
- 可控制颜色、可见性、独显、透明度、偏移、边截断和点大小。
- 可在支持的物体、雕刻和绘制工作流中持续显示标注。
- 界面支持英文与简体中文。

## 环境要求

- Blender 4.2 或更高版本。
- 无第三方 Python 依赖。

## 安装

下载发行版 ZIP，在 Blender 中使用 **偏好设置 → 获取扩展 → 从磁盘安装**。
验证方法、源码构建和故障排除见[安装指南](docs/zh-CN/installation.md)。

## 快速开始

1. 选择网格对象，按 `N` 打开 3D 视图侧边栏。
2. 打开 **Mesh Annotation（网格标注）** 标签。
3. 进入编辑模式，选择面、边或点工作区。
4. 新建图层，选中网格元素，然后执行**分配选中**。
5. 直接在面板中调整可见性和显示样式。

## 文档

| 内容 | 简体中文 | English |
| --- | --- | --- |
| 安装 | [安装指南](docs/zh-CN/installation.md) | [Installation](docs/en/installation.md) |
| 工作流 | [用户指南](docs/zh-CN/user-guide.md) | [User guide](docs/en/user-guide.md) |
| 常见问题 | [常见问题](docs/zh-CN/faq.md) | [FAQ](docs/en/faq.md) |
| 架构与贡献 | [开发说明](docs/zh-CN/development.md) | [Development](docs/en/development.md) |

## 仓库结构

```text
mesh_annotation_layers/  Blender 插件运行代码
docs/en/                 英文文档
docs/zh-CN/              简体中文文档
tests/                   源码契约与 Blender 冒烟测试
tools/build.py           正式版与开发版构建工具
blender_manifest.toml    Blender 扩展清单
```

构建可安装压缩包：

```bash
python tools/build.py
```

本地测试版使用 `python tools/build.py --dev`。

## 许可证

GPL-3.0-or-later，详见 [LICENSE](LICENSE)。
