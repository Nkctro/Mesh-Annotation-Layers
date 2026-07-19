# 安装指南

[English](../en/installation.md) · [项目主页](../../README.zh-CN.md)

## 安装发行版

1. 下载发行版 ZIP，不要解压。
2. 打开 Blender 4.2 或更高版本。
3. 进入**编辑 → 偏好设置 → 获取扩展**。
4. 打开右上角菜单，选择**从磁盘安装**。
5. 选择 ZIP 并确认安装。
6. 搜索 **Mesh Annotation Layers**，必要时启用扩展。

Blender 官方扩展文档同样建议通过“从磁盘安装”验证扩展包：
<https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html>。

## 验证安装

1. 选择网格对象。
2. 在 3D 视图中按 `N` 打开侧边栏。
3. 打开 **Mesh Annotation（网格标注）** 标签。
4. 进入编辑模式，新建图层或修改分配。

已有标注可在支持的非编辑模式中继续显示。

## 从源码构建

构建器使用 Python 标准库读取 TOML，因此需要 Python 3.11 或更高版本。

```bash
git clone https://github.com/Nkctro/Mesh-Annotation-Layers.git
cd Mesh-Annotation-Layers
python tools/build.py
```

压缩包输出到 `dist/`。需要带唯一测试版本号的开发包时运行：

```bash
python tools/build.py --dev
```

使用“从磁盘安装”安装生成的 ZIP。命令结束后，仓库中的清单和插件版本会恢复原值。

## 故障排除

- **没有面板：**选择网格对象、打开侧边栏，并确认扩展已启用。
- **无法分配：**进入编辑模式，选择元素，并激活或新建图层。
- **启用报错：**确认所有文件来自同一个发行版 ZIP，并使用 Blender 4.2+。
- **需要报告：**打开 Blender 系统控制台，将完整 traceback 附在问题报告中。

## 卸载

进入**偏好设置 → 获取扩展**，找到 Mesh Annotation Layers，打开其菜单并选择**卸载**。
