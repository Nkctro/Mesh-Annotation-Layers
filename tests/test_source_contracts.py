import ast
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


DYNAMIC_TRANSLATION_KEYS = {
    "Face Layers",
    "Edge Layers",
    "Vertex Layers",
    "faces",
    "edges",
    "vertices",
    "face loop",
    "edge loop",
    "vertex path",
    "Automatic",
    "English",
    "Chinese",
    "Use Blender's interface language; unsupported languages use English.",
    "Always display the add-on in English.",
    "Always display the add-on in Chinese.",
    "Faces",
    "Edges",
    "Vertices",
    "Object Mode",
    "Weight Paint",
    "Vertex Paint",
    "Sculpt Mode",
    "Texture Paint",
}


def used_translation_keys():
    used = set(DYNAMIC_TRANSLATION_KEYS)
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
    def test_repository_layout_and_bilingual_docs_stay_paired(self):
        self.assertTrue((ROOT / "tools" / "build.py").is_file())
        self.assertFalse((ROOT / "package.py").exists())
        self.assertFalse((ROOT / "package_beta.py").exists())

        legacy_root_docs = {
            "ARCHITECTURE.md",
            "CONTRIBUTING.md",
            "EXAMPLES.md",
            "FAQ.md",
            "INSTALL.md",
            "QUICK_REFERENCE.md",
        }
        self.assertFalse(
            legacy_root_docs & {path.name for path in ROOT.glob("*.md")}
        )

        expected_docs = {
            "installation.md",
            "user-guide.md",
            "faq.md",
            "development.md",
        }
        english_docs = {path.name for path in (ROOT / "docs" / "en").glob("*.md")}
        chinese_docs = {
            path.name for path in (ROOT / "docs" / "zh-CN").glob("*.md")
        }
        self.assertEqual(expected_docs, english_docs)
        self.assertEqual(english_docs, chinese_docs)

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
        used = used_translation_keys()
        self.assertEqual(set(), used - catalog)

    def test_translation_catalog_has_no_stale_keys(self):
        self.assertEqual(set(), translation_catalog() - used_translation_keys())

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
        self.assertLess(line_count, 180)

    def test_extension_source_layout_and_release_manifest(self):
        manifest_path = ROOT / "blender_manifest.toml"
        self.assertTrue(manifest_path.is_file())
        self.assertTrue((PACKAGE / "__init__.py").is_file())
        self.assertFalse((PACKAGE / "blender_manifest.toml").exists())
        with manifest_path.open("rb") as manifest_file:
            manifest = tomllib.load(manifest_file)
        self.assertEqual("1.3.0", manifest["version"])
        self.assertEqual("mesh_annotation_layers", manifest["id"])
        self.assertNotIn("permissions", manifest)
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertGreater(len(license_text), 30_000)
        self.assertIn("GNU GENERAL PUBLIC LICENSE", license_text)
        self.assertIn(
            "Copyright (C) 2025 Mesh Annotation Layers Team", license_text
        )
        self.assertIn("at your option) any later version", license_text)

    def test_extension_entry_point_reloads_every_submodule(self):
        entry_tree = parse(PACKAGE / "__init__.py")
        module_names = next(
            (
                tuple(
                    item.value
                    for item in node.value.elts
                    if isinstance(item, ast.Constant)
                )
                for node in entry_tree.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "_SUBMODULE_NAMES"
                    for target in node.targets
                )
                and isinstance(node.value, ast.Tuple)
            ),
            (),
        )
        expected = {
            path.stem
            for path in PACKAGE.glob("*.py")
            if path.name != "__init__.py"
        }
        self.assertEqual(expected, set(module_names))
        entry_source = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("importlib.reload(module)", entry_source)
        self.assertIn('_needs_reload = "bpy" in locals()', entry_source)
        self.assertNotIn("bl_info", entry_source)
        self.assertNotIn('if __name__ == "__main__"', entry_source)

    def test_overlay_color_does_not_depend_on_selection(self):
        source = (PACKAGE / "overlay.py").read_text(encoding="utf-8")
        self.assertNotIn('blend_set("ADDITIVE")', source)
        self.assertNotIn('entry.get("selected")', source)

    def test_viewport_draw_path_does_not_commit_annotation_json(self):
        source = (PACKAGE / "overlay.py").read_text(encoding="utf-8")
        self.assertNotIn("save_element_layers", source)
        self.assertIn("synchronize_edit_mesh_annotations", source)

    def test_undo_and_redo_have_explicit_cache_boundaries(self):
        source = (PACKAGE / "overlay.py").read_text(encoding="utf-8")
        for handler_name in ("undo_pre", "undo_post", "redo_pre", "redo_post"):
            self.assertIn(f"bpy.app.handlers.{handler_name}", source)

    def test_primary_remove_selected_action_preserves_other_layers(self):
        operator_source = (PACKAGE / "operators.py").read_text(encoding="utf-8")
        panel_source = (PACKAGE / "ui.py").read_text(encoding="utf-8")
        self.assertIn('default="ACTIVE"', operator_source)
        self.assertIn('clear_op.mode = "ACTIVE"', panel_source)

    def test_context_menu_is_mode_aware_and_flat(self):
        ui_source = (PACKAGE / "ui.py").read_text(encoding="utf-8")
        preferences_source = (PACKAGE / "preferences.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("infer_element_type_from_mode(context)", ui_source)
        self.assertIn("draw_active_assignment(layout", ui_source)
        self.assertIn("draw_clear_assignment(layout", ui_source)
        self.assertNotIn("VIEW3D_MT_mesh_annotation_add", ui_source)
        self.assertNotIn("VIEW3D_MT_mesh_annotation_remove", ui_source)
        self.assertNotIn("MeshAnnotationTypeMenuBase", ui_source)
        self.assertNotIn("context_menu_split_types", preferences_source)

    def test_context_target_assignment_can_activate_the_layer(self):
        operator_source = (PACKAGE / "operators.py").read_text(encoding="utf-8")
        ui_source = (PACKAGE / "ui.py").read_text(encoding="utf-8")
        self.assertIn("make_active: bpy.props.BoolProperty", operator_source)
        self.assertIn("operator.make_active = True", ui_source)

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
        tree = parse(PACKAGE / "operators.py")
        guarded = set()
        for node in tree.body:
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

    def test_obsolete_implementations_and_packagers_are_gone(self):
        self.assertFalse((ROOT / "package.py").exists())
        self.assertFalse((ROOT / "package_beta.py").exists())
        sources = "\n".join(
            path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
        )
        for obsolete in (
            "_nearest_vertex_sources",
            "compute_edge_loop",
            "_walk_edge_loop_direction",
            "mark_overlay_cache_dirty",
            "_paint_cache_can_ignore_data_updates",
            "skip_dialog",
            "color_seed_face",
            "color_seed_edge",
            "color_seed_vertex",
            "integer_layer",
            "stack_rebuild_required",
            "save_element_layers",
            "_registration_cleanup_pending",
            "_registration_is_complete",
            "_BMESH_SYNC_SIGNATURES",
            "_BMESH_SYNC_QUARANTINED",
            "_callback_instance_count",
            "rollback_errors",
        ):
            self.assertNotIn(obsolete, sources)

    def test_load_and_history_handlers_are_explicit_lifecycle_boundaries(self):
        source = (PACKAGE / "overlay.py").read_text(encoding="utf-8")
        self.assertIn("bpy.app.handlers.load_pre", source)
        self.assertIn("annotation_load_pre", source)
        self.assertIn("invalidate_overlay_state()", source)


if __name__ == "__main__":
    unittest.main()
