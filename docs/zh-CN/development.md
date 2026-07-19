# 开发说明

[English](../en/development.md) · [项目主页](../../README.zh-CN.md)

## 设计边界

插件将标注数据与材质分离，并在 Blender 评估网格上绘制。运行模块各自承担单一职责；
包入口只负责注册、注销与失败回滚。

```text
mesh_annotation_layers/
├── __init__.py             注册生命周期
├── constants.py            元素类型规范
├── i18n.py                 语言选择与翻译
├── model.py                存储、校验、BMesh 同步
├── evaluated_geometry.py   源网格到评估网格的映射
├── overlay.py              GPU 批次、缓存、绘制处理器
├── loops.py                面/边/点路径推导
├── properties.py           Blender 属性组
├── operators.py            用户操作与校验
├── preferences.py          插件偏好设置
└── ui.py                   面板、列表和右键菜单
```

依赖应从 Blender 界面/操作层指向数据模型，模型不能反向导入 UI。绘制失效逻辑归
`overlay.py` 管理。

## 数据流

```text
编辑模式选区
  → 操作校验
  → 对象级图层映射
  → 编辑期间的 BMesh 自定义数据
  → .blend 文件中的序列化对象数据

可见分配
  → 评估网格映射
  → 局部显示偏移与边截断
  → GPU 批次
  → 缓存后的视口绘制
```

英文字符串是稳定的翻译键。新增用户可见文本时，应在调用处写英文，并同时在
`i18n.py` 中添加简体中文值。

## 开发环境与检查

运行时没有外部依赖。源码检查使用 Python，冒烟测试在 Blender 内运行。

```bash
python -m compileall -q mesh_annotation_layers tests tools
python tests/test_source_contracts.py
blender --factory-startup --background --python tests/blender_smoke.py --python-exit-code 1
```

必须显式指定 Python 失败退出码，否则 Blender 可能在未捕获断言后仍返回成功。

## 构建

```bash
python tools/build.py
python tools/build.py --dev
python tools/build.py --suffix rc1
```

压缩包输出到 `dist/`。构建器会临时修改开发版本元数据，写入压缩包，并在
`finally` 中恢复源码文件。

发布前应同步 `blender_manifest.toml` 与 `bl_info` 版本，更新变更日志，运行两层测试，
检查 ZIP 内容，并使用 Blender 的**从磁盘安装**流程验证。

## 贡献规则

- 保持 `__init__.py` 简短且具备事务式回滚。
- 除非明确引入兼容性变化，否则保持操作 ID 稳定。
- 在模型边界校验损坏的存储数据，不要让 UI 绘制承担修复逻辑。
- 英文翻译键与中文目录项必须一起添加。
- 行为变化必须提供回归测试。
- 聚焦修复中避免无关格式化或架构调整。

提交信息使用简短祈使句，例如 `Fix edge overlay invalidation`。拉取请求需说明用户影响、
测试证据，以及兼容性或性能风险。

## 文档规则

用户文档在 `docs/en/` 与 `docs/zh-CN/` 中一一对应。行为改变时必须同时更新两种语言。
README 只负责概览和导航，详细步骤放在 `docs/` 中。
