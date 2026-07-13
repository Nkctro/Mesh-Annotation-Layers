import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "mesh_annotation_layers"


def parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


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
        catalog = set()
        for node in parse(PACKAGE / "i18n.py").body:
            if not isinstance(node, ast.Assign):
                continue
            is_catalog = any(
                isinstance(target, ast.Name) and target.id == "ZH_CN"
                for target in node.targets
            )
            if is_catalog:
                catalog = {
                    key.value
                    for key in node.value.keys
                    if isinstance(key, ast.Constant)
                }

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

    def test_legacy_inline_translation_pairs_are_gone(self):
        for path in PACKAGE.glob("*.py"):
            self.assertNotIn("bi(", path.read_text(encoding="utf-8"))

    def test_entry_point_stays_small(self):
        line_count = len(
            (PACKAGE / "__init__.py").read_text(encoding="utf-8").splitlines()
        )
        self.assertLess(line_count, 100)


if __name__ == "__main__":
    unittest.main()
