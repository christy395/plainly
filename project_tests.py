import json
import os
import tempfile
import unittest

from plainly_project import (
    PROJECT_FILE, ProjectError, check_project, create_project,
    default_manifest, validate_manifest,
)


class ProjectTests(unittest.TestCase):
    def test_manifest_defaults_deny_capabilities(self):
        manifest = default_manifest("Example", "app")
        self.assertEqual(manifest["targets"], ["android", "ios", "windows", "linux", "macos"])
        self.assertEqual(manifest["security"]["capabilities"], [])
        self.assertEqual(manifest["security"]["network"], "deny")
        self.assertFalse(manifest["security"]["native_extensions"])
        validate_manifest(manifest)

    def test_create_and_check_app(self):
        with tempfile.TemporaryDirectory() as temp:
            root = create_project("DemoApp", "app", temp)
            manifest = check_project(root)
            self.assertEqual(manifest["kind"], "app")
            self.assertTrue(os.path.isfile(os.path.join(root, "main.plain")))

    def test_create_and_check_game(self):
        with tempfile.TemporaryDirectory() as temp:
            root = create_project("DemoGame", "game", temp)
            self.assertEqual(check_project(root)["kind"], "game")

    def test_reject_path_traversal_entry(self):
        manifest = default_manifest("Safe", "app")
        manifest["entry"] = "../outside.plain"
        with self.assertRaises(ProjectError):
            validate_manifest(manifest)

    def test_reject_unknown_target(self):
        manifest = default_manifest("Safe", "app")
        manifest["targets"].append("freebsd")
        with self.assertRaises(ProjectError):
            validate_manifest(manifest)

    def test_reject_unknown_capability(self):
        manifest = default_manifest("Safe", "app")
        manifest["security"]["capabilities"] = ["root-access"]
        with self.assertRaises(ProjectError):
            validate_manifest(manifest)

    def test_network_requires_explicit_capability(self):
        manifest = default_manifest("Safe", "app")
        manifest["security"]["network"] = "allow-listed"
        with self.assertRaises(ProjectError):
            validate_manifest(manifest)

    def test_reject_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            with open(os.path.join(temp, PROJECT_FILE), "w", encoding="utf-8") as f:
                f.write('{"format":1,"format":1}')
            with self.assertRaises(ProjectError):
                from plainly_project import load_project
                load_project(temp)

    def test_reject_symlink_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = create_project("LinkTest", "app", temp)
            entry = os.path.join(root, "main.plain")
            os.unlink(entry)
            outside = os.path.join(temp, "outside.plain")
            with open(outside, "w", encoding="utf-8") as f:
                f.write("say the words outside end words\n")
            try:
                os.symlink(outside, entry)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this platform")
            with self.assertRaises(ProjectError):
                check_project(root)

    def test_reject_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            create_project("Existing", "app", temp)
            with self.assertRaises(ProjectError):
                create_project("Existing", "game", temp)


if __name__ == "__main__":
    unittest.main()
