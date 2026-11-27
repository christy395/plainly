#!/usr/bin/env python3
"""Regression tests for Plainly's binary bytecode compiler and VM."""
import contextlib
import io
import os
import tempfile
import unittest

import plainly
import plainly_bytecode as bc


class BytecodeTests(unittest.TestCase):
    def run_plain(self, source, **kwargs):
        blob = bc.compile_source(source)
        self.assertTrue(blob.startswith(bc.MAGIC))
        decoded = bc.loads(blob)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bc.run_program(decoded, **kwargs)
        return output.getvalue()

    def test_binary_container_round_trip(self):
        blob = bc.compile_source("say the words Hello from bytecode end words")
        self.assertNotIn(b"exec(", blob)
        self.assertEqual(self.run_plain("say the words Hello from bytecode end words"),
                         "Hello from bytecode\n")

    def test_calculations_and_variables(self):
        source = "let a be 6\nlet b be 7\nsay a times b plus 0"
        self.assertEqual(self.run_plain(source), "42\n")

    def test_conditions_and_boolean_logic(self):
        source = (
            "let score be 82\n"
            "if score is at least 60 and score is less than 90 then\n"
            "say the words Passed end words\n"
            "otherwise\n"
            "say the words Check score end words\n"
            "end if\n"
        )
        self.assertEqual(self.run_plain(source), "Passed\n")

    def test_repeat_and_while_loops(self):
        source = (
            "let total be 0\n"
            "repeat 3 times do\nadd 1 to total\nend repeat\n"
            "let counter be 1\n"
            "while counter is at most 2 do\n"
            "say counter\nadd 1 to counter\nend while\n"
            "say total\n"
        )
        self.assertEqual(self.run_plain(source), "1\n2\n3\n")

    def test_lists_and_for_each(self):
        source = (
            "let values be a list of 1 and 2 and 3\n"
            "add 4 to values\n"
            "for each value in values do\n"
            "say value times 2\n"
            "end for\n"
        )
        self.assertEqual(self.run_plain(source), "2\n4\n6\n8\n")

    def test_functions(self):
        source = (
            "define double of value as number giving number\n"
            "give back value times 2\n"
            "end define\n"
            "say double of 21\n"
        )
        self.assertEqual(self.run_plain(source), "42\n")

    def test_text_join_and_comparison(self):
        source = (
            "let name be the words Plainly end words\n"
            "say the words Hello followed by name\n"
            "if name is the words Plainly end words then\n"
            "say true\n"
            "end if\n"
        )
        self.assertEqual(self.run_plain(source), "Hello Plainly\nyes\n")

    def test_input_builtin(self):
        source = "let answer be what the user types\nsay answer"
        self.assertEqual(self.run_plain(source, input_fn=lambda: "hello"), "hello\n")

    def test_rejects_unsupported_files(self):
        source = (
            "allow reading the file private.txt\n"
            "let secret be the contents of the file private.txt\n"
            "say secret\n"
        )
        with self.assertRaises(bc.BytecodeError):
            bc.compile_source(source)

    def test_rejects_records_and_web_routes(self):
        with self.assertRaises(bc.BytecodeError):
            bc.compile_source("a record called item has price as number")
        with self.assertRaises(bc.BytecodeError):
            bc.compile_source(
                "when someone visits the path home do\n"
                "reply with the words hi end words\nend when"
            )

    def test_checksum_detects_changes(self):
        blob = bytearray(bc.compile_source("say 1"))
        blob[-1] ^= 1
        with self.assertRaises(bc.BytecodeError):
            bc.loads(blob)

    def test_invalid_magic_is_rejected(self):
        with self.assertRaises(bc.BytecodeError):
            bc.loads(b"not a pbc file")

    def test_instruction_limit_stops_endless_loop(self):
        source = "while true do\nadd 1 to counter\nend while"
        source = "let counter be 0\n" + source
        blob = bc.compile_source(source)
        with self.assertRaisesRegex(bc.BytecodeError, "instruction limit"):
            bc.run_bytes(blob, step_limit=25)

    def test_fizz_example_matches_interpreter(self):
        path = os.path.join(os.path.dirname(__file__), "fizz.plain")
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        expected = io.StringIO()
        with contextlib.redirect_stdout(expected):
            plainly.run_source(source, path)
        actual = io.StringIO()
        with contextlib.redirect_stdout(actual):
            bc.run_bytes(bc.compile_source(source))
        self.assertEqual(actual.getvalue(), expected.getvalue())

    def test_repository_hello_bytecode_sample(self):
        path = os.path.join(os.path.dirname(__file__), "hello.pbc")
        with open(path, "rb") as handle:
            blob = handle.read()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bc.run_bytes(blob)
        self.assertEqual(output.getvalue(), "Hello, world.\n")

    def test_file_and_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = os.path.join(directory, "hello.plain")
            with open(source_path, "w", encoding="utf-8") as handle:
                handle.write("say the words Saved bytecode end words\n")
            output_path = bc.compile_file(source_path)
            self.assertTrue(output_path.endswith("hello.pbc"))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                bc.run_file(output_path)
            self.assertEqual(output.getvalue(), "Saved bytecode\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
