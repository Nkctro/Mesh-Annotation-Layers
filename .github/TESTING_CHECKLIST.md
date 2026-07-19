# Release test checklist / 发布测试清单

Use Blender 4.2 or newer. / 使用 Blender 4.2 或更高版本。

## Automated / 自动检查

- [ ] `python -m compileall -q mesh_annotation_layers tests tools`
- [ ] `python tests/test_source_contracts.py`
- [ ] `blender --factory-startup --background --python tests/blender_smoke.py --python-exit-code 1`
- [ ] `python tools/build.py`
- [ ] Install the generated ZIP with **Install from Disk** / 使用**从磁盘安装**验证生成的 ZIP

## Core workflow / 核心流程

- [ ] Register and unregister without console errors / 启用与禁用无控制台错误
- [ ] Create, rename, reorder, show, solo, and delete layers / 新建、重命名、排序、显示、独显、删除图层
- [ ] Assign selected faces, edges, and vertices / 分配选中的面、边、点
- [ ] Assign derived loops/paths and vertex valence / 分配推导循环、路径和指定连接数顶点
- [ ] Select layer elements, pick from selection, and clear assignments / 选择整层、从选区激活、清理分配
- [ ] Mark active and all face-layer boundaries as UV seams / 将活动及全部面图层边界标记为 UV 缝

## Display and persistence / 显示与持久化

- [ ] Colors, opacity, offsets, edge trim, point size, and through-mesh display work / 显示参数生效
- [ ] Overlays remain correct in documented object/sculpt/paint modes / 非编辑模式显示符合文档
- [ ] Subdivision Surface and Mirror test scenes follow the evaluated surface / 细分与镜像场景跟随评估表面
- [ ] Two objects keep independent layers / 多对象图层互不干扰
- [ ] Save, reopen, undo, and redo preserve valid data / 保存、重开、撤销、重做后数据正确

## Record / 记录

- Blender version / Blender 版本:
- Operating system / 操作系统:
- GPU:
- Archive SHA-256:
- Notes / 备注:
