#!/usr/bin/env python3
"""Focused security regression tests for Plainly's host-side boundaries.

Run with: python3 audit_tests.py
These tests are regression checks, not a security certification or sandbox test.
"""
import contextlib
import io
import os
import tempfile
import unittest

import plainly


class PlainlyAuditRegressionTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = os.getcwd()
        self.work = tempfile.mkdtemp(prefix="plainly-audit-")
        os.chdir(self.work)
        plainly.PERMS.clear()
        plainly._MEM["file"] = None
        plainly._ROUTES.clear()
        plainly._TL.page = []

    def tearDown(self):
        plainly.PERMS.clear()
        plainly._MEM["file"] = None
        plainly._ROUTES.clear()
        os.chdir(self.old_cwd)
        import shutil
        shutil.rmtree(self.work, ignore_errors=True)

    def test_plain_program_runs(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            plainly.run_source("let answer be 6 times 7\nsay answer")
        self.assertEqual(output.getvalue(), "42\n")

    def test_file_read_requires_explicit_permission(self):
        with self.assertRaises(plainly.PlainlyError):
            plainly.compile_source(
                "let secret be the contents of the file secret.txt\nsay secret"
            )

    def test_parent_path_is_rejected(self):
        with self.assertRaises(plainly.PlainlyError):
            plainly.compile_source("allow reading the file ../secret.txt")

    def test_permitted_regular_file_read_and_write(self):
        with open("values.txt", "w", encoding="utf-8") as handle:
            handle.write("hello")
        plainly.PERMS.update({("read", "values.txt"), ("write", "report.txt")})
        self.assertEqual(plainly._read("values.txt"), "hello")
        plainly._write("report.txt", "safe")
        with open("report.txt", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "safe\n")

    def test_symbolic_link_read_is_rejected(self):
        with open("outside.txt", "w", encoding="utf-8") as handle:
            handle.write("outside")
        try:
            os.symlink("outside.txt", "shortcut.txt")
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable on this platform")
        plainly.PERMS.add(("read", "shortcut.txt"))
        with self.assertRaises(plainly.PlainlyRuntimeError):
            plainly._read("shortcut.txt")

    def test_symbolic_link_write_is_rejected_without_changing_target(self):
        with open("outside.txt", "w", encoding="utf-8") as handle:
            handle.write("original")
        try:
            os.symlink("outside.txt", "shortcut.txt")
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable on this platform")
        plainly.PERMS.add(("write", "shortcut.txt"))
        with self.assertRaises(plainly.PlainlyRuntimeError):
            plainly._write("shortcut.txt", "changed")
        with open("outside.txt", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "original")

    def test_hard_link_read_is_rejected(self):
        with open("outside.txt", "w", encoding="utf-8") as handle:
            handle.write("outside")
        try:
            os.link("outside.txt", "linked.txt")
        except (OSError, NotImplementedError):
            self.skipTest("hard links are unavailable on this platform")
        plainly.PERMS.add(("read", "linked.txt"))
        with self.assertRaises(plainly.PlainlyRuntimeError):
            plainly._read("linked.txt")

    def test_memory_file_symbolic_link_is_rejected(self):
        with open("outside.json", "w", encoding="utf-8") as handle:
            handle.write("{}")
        try:
            os.symlink("outside.json", "memory.json")
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable on this platform")
        plainly._MEM["file"] = "memory.json"
        with self.assertRaises(plainly.PlainlyRuntimeError):
            plainly._mem_load()

    def test_page_text_is_html_escaped(self):
        plainly._TL.page = []
        plainly._el("p", "<script>alert(1)</script>")
        self.assertIn("&lt;script&gt;", plainly._TL.page[0])
        self.assertNotIn("<script>", plainly._TL.page[0])


    def test_native_executable_name_is_platform_appropriate(self):
        self.assertEqual(plainly._native_executable_path("speed.plain", windows=False), "speed")
        self.assertEqual(plainly._native_executable_path("speed.plain", windows=True), "speed.exe")
        self.assertEqual(plainly._native_executable_path("speed.exe.plain", windows=True), "speed.exe")

    def test_native_backend_emits_a_compilable_program_shape(self):
        source, _ = plainly.compile_source("say 42", native=True)
        self.assertIn("int main(void)", source)
        self.assertIn("p_say_num(42.0)", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
