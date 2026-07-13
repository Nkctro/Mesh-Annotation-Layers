import ast
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
        is_catalog = any(
            isinstance(target, ast.Name) and target.id == "ZH_CN"
            for target in node.targets
        )
        if is_catalog:
            return {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant)
            }
    return set()


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
        catalog = translation_catalog()
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
        self.assertEqual(set(), used - catalog)

    def test_every_operator_has_a_localized_tooltip(self):
        catalog = translation_catalog()
        tree = parse(PACKAGE / "operators.py")
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            is_operator = any(
                isinstance(base, ast.Attribute) and base.attr == "Operator"
                for base in node.bases
            )
            uses_mixin = any(
                isinstance(base, ast.Name) and base.id == "LocalizedDescription"
                for base in node.bases
            )
            if not is_operator:
                continue
            self.assertTrue(
                uses_mixin,
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

    def test_legacy_inline_translation_pairs_are_gone(self):
        for path in PACKAGE.glob("*.py"):
            self.assertNotIn("bi(", path.read_text(encoding="utf-8"))

    def test_language_modes_are_auto_english_and_chinese_only(self):
        source = (PACKAGE / "i18n.py").read_text(encoding="utf-8")
        self.assertNotIn('"BOTH"', source)
        self.assertNotIn('partition(".")', source)

    def test_language_selector_lives_only_in_addon_preferences(self):
        panel_source = (PACKAGE / "ui.py").read_text(encoding="utf-8")
        preferences_source = (PACKAGE / "preferences.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('"language_display"', panel_source)
        self.assertIn('layout.prop(self, "language_display"', preferences_source)

    def test_entry_point_stays_small(self):
        line_count = len(
            (PACKAGE / "__init__.py").read_text(encoding="utf-8").splitlines()
        )
        self.assertLess(line_count, 100)

    def test_overlay_color_does_not_depend_on_selection(self):
        source = (PACKAGE / "overlay.py").read_text(encoding="utf-8")
        self.assertNotIn('blend_set("ADDITIVE")', source)
        self.assertNotIn('entry.get("selected")', source)

    def test_undo_and_redo_have_explicit_cache_boundaries(self):
        source = (PACKAGE / "overlay.py").read_text(encoding="utf-8")
        for handler_name in ("undo_pre", "undo_post", "redo_pre", "redo_post"):
            self.assertIn(f"bpy.app.handlers.{handler_name}", source)

    def test_primary_remove_selected_action_preserves_other_layers(self):
        operator_source = (PACKAGE / "operators.py").read_text(encoding="utf-8")
        panel_source = (PACKAGE / "ui.py").read_text(encoding="utf-8")
        self.assertIn('default="ACTIVE"', operator_source)
        self.assertIn('clear_op.mode = "ACTIVE"', panel_source)


if __name__ == "__main__":
    unittest.main()
