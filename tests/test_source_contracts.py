import ast
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "mesh_annotation_layers"


def parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def translation_catalog():
    for node in parse(PACKAGE / "i18n.py").body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "ZH_CN"
            for target in node.targets
        ):
            continue
        return {
            key.value
            for key in node.value.keys
            if isinstance(key, ast.Constant)
        }
    return set()


def assigned_node(path, name):
    for node in ast.walk(parse(path)):
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return node.value
    return None


def dynamic_translation_keys():
    """Extract keys passed to tr() through production metadata and UI maps."""

    used = set()
    for node in ast.walk(parse(PACKAGE / "constants.py")):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "ElementSpec"
        ):
            continue
        for keyword in node.keywords:
            if (
                keyword.arg in {"label", "selection_label", "loop_label"}
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                used.add(keyword.value.value)

    language_items = assigned_node(PACKAGE / "i18n.py", "LANGUAGE_ITEM_KEYS")
    if language_items is not None:
        for _identifier, label, description in ast.literal_eval(language_items):
            used.update((label, description))

    ui_tree = parse(PACKAGE / "ui.py")
    for mapping_name in ("tab_labels", "mode_labels"):
        mapping_node = next(
            (
                node.value
                for node in ast.walk(ui_tree)
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == mapping_name
                    for target in node.targets
                )
            ),
            None,
        )
        if mapping_node is not None:
            used.update(
                value.value
                for value in mapping_node.values
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            )
    return used


def literal_translation_keys():
    used = set()
    for path in PACKAGE.glob("*.py"):
        for node in ast.walk(parse(path)):
            literal_translation = (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            )
            if literal_translation:
                used.add(node.args[0].value)
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            is_tooltip = any(
                isinstance(target, ast.Name) and target.id == "tooltip_key"
                for target in targets
            )
            if (
                is_tooltip
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                and node.value.value
            ):
                used.add(node.value.value)
    return used


class SourceContractsTest(unittest.TestCase):
    def test_every_module_parses_and_has_unique_top_level_definitions(self):
        for path in PACKAGE.glob("*.py"):
            definitions = {}
            for node in parse(path).body:
                name = getattr(node, "name", None)
                if name:
                    self.assertNotIn(
                        name,
                        definitions,
                        f"{path.name}:{node.lineno} duplicates {name}",
                    )
                    definitions[name] = node.lineno

    def test_translation_catalog_covers_literal_keys(self):
        dynamic_keys = dynamic_translation_keys()
        self.assertTrue(dynamic_keys)
        used = literal_translation_keys() | dynamic_keys
        self.assertEqual(set(), used - translation_catalog())

    def test_entry_point_lists_every_runtime_module(self):
        module_names = ast.literal_eval(
            assigned_node(PACKAGE / "__init__.py", "_SUBMODULE_NAMES")
        )
        expected = {
            path.stem
            for path in PACKAGE.glob("*.py")
            if path.name != "__init__.py"
        }
        self.assertEqual(expected, set(module_names))

    def test_every_operator_has_a_localized_tooltip(self):
        catalog = translation_catalog()
        for node in parse(PACKAGE / "operators.py").body:
            if not isinstance(node, ast.ClassDef):
                continue
            is_operator = any(
                isinstance(base, ast.Attribute) and base.attr == "Operator"
                for base in node.bases
            )
            if not is_operator:
                continue
            self.assertTrue(
                any(
                    isinstance(base, ast.Name)
                    and base.id == "LocalizedDescription"
                    for base in node.bases
                ),
                f"{node.name} does not use LocalizedDescription",
            )
            tooltip = next(
                (
                    child.value.value
                    for child in node.body
                    if isinstance(child, ast.Assign)
                    and any(
                        isinstance(target, ast.Name)
                        and target.id == "tooltip_key"
                        for target in child.targets
                    )
                    and isinstance(child.value, ast.Constant)
                ),
                None,
            )
            self.assertIsNotNone(tooltip, f"{node.name} has no tooltip_key")
            self.assertIn(tooltip, catalog, f"{node.name} tooltip is not translated")

    def test_extension_source_layout_and_release_manifest(self):
        manifest_path = PACKAGE / "blender_manifest.toml"
        self.assertTrue(manifest_path.is_file())
        self.assertTrue((PACKAGE / "__init__.py").is_file())
        self.assertFalse((ROOT / "blender_manifest.toml").exists())
        with manifest_path.open("rb") as manifest_file:
            manifest = tomllib.load(manifest_file)
        self.assertEqual("mesh_annotation_layers", manifest["id"])
        self.assertRegex(manifest["version"], re.compile(r"^\d+\.\d+\.\d+$"))
        self.assertNotIn("permissions", manifest)
        changelog_versions = re.findall(
            r"^# \[(\d+\.\d+\.\d+)\]",
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        self.assertTrue(changelog_versions)
        self.assertEqual(manifest["version"], changelog_versions[0])

        license_text = (PACKAGE / "LICENSE").read_text(encoding="utf-8")
        self.assertGreater(len(license_text), 30_000)
        self.assertIn("GNU GENERAL PUBLIC LICENSE", license_text)
        self.assertEqual(
            license_text,
            (ROOT / "LICENSE").read_text(encoding="utf-8"),
        )

    def test_every_annotation_write_uses_the_central_guard(self):
        write_operators = {
            "MESH_OT_annotation_layer_add",
            "MESH_OT_annotation_layer_remove",
            "MESH_OT_annotation_layer_move",
            "MESH_OT_annotation_assign_active",
            "MESH_OT_annotation_assign_loop",
            "MESH_OT_annotation_assign_valence",
            "MESH_OT_annotation_assign_valence_new_layer",
            "MESH_OT_annotation_assign_new_layer",
            "MESH_OT_annotation_assign_layer",
            "MESH_OT_annotation_mark_seam_active",
            "MESH_OT_annotation_mark_seam_all",
            "MESH_OT_annotation_clear_selected",
        }
        guarded = set()
        for node in parse(PACKAGE / "operators.py").body:
            if not isinstance(node, ast.ClassDef):
                continue
            execute = next(
                (
                    child
                    for child in node.body
                    if isinstance(child, ast.FunctionDef) and child.name == "execute"
                ),
                None,
            )
            if execute and any(
                isinstance(decorator, ast.Name)
                and decorator.id == "annotation_write"
                for decorator in execute.decorator_list
            ):
                guarded.add(node.name)
        self.assertEqual(write_operators, guarded)


if __name__ == "__main__":
    unittest.main()
