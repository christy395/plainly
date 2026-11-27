#!/usr/bin/env python3
"""Cross-platform CLI tests for independent Plainly bytecode commands."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
CLI = ROOT / "plainly.py"


class CoreBytecodeCliTests(unittest.TestCase):
    def run_cli(self, folder, *args):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_compile_and_execute_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            pathlib.Path(folder, "program.plain").write_text(
                'let answer be 6 times 7\nsay answer\n',
                encoding="utf-8",
            )
            compiled = self.run_cli(folder, "core-compile", "program.plain")
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            self.assertTrue(pathlib.Path(folder, "program.core.pbc").is_file())
            executed = self.run_cli(folder, "core-execute", "program.core.pbc")
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(executed.stdout, "42\n")

    def test_invalid_source_returns_clean_error(self):
        with tempfile.TemporaryDirectory() as folder:
            pathlib.Path(folder, "bad.plain").write_text("say (\n", encoding="utf-8")
            result = self.run_cli(folder, "core-compile", "bad.plain")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Plainly core bytecode error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_compile_refuses_to_overwrite_existing_bytecode(self):
        with tempfile.TemporaryDirectory() as folder:
            pathlib.Path(folder, "program.plain").write_text("say 1\n", encoding="utf-8")
            first = self.run_cli(folder, "core-compile", "program.plain")
            self.assertEqual(first.returncode, 0, first.stderr)
            output = pathlib.Path(folder, "program.core.pbc")
            original = output.read_bytes()
            second = self.run_cli(folder, "core-compile", "program.plain")
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
