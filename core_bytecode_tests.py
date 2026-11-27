#!/usr/bin/env python3
"""Regression tests for Plainly's independent core bytecode backend."""
import hashlib
import struct
import unittest

import plainly_core as core
import plainly_core_bytecode as bytecode


class CoreBytecodeTests(unittest.TestCase):
    def assertBothBackends(self, source, expected):
        self.assertEqual(core.run_source(source), expected)
        self.assertEqual(bytecode.run_source(source), expected)

    def test_arithmetic_and_precedence(self):
        self.assertBothBackends("say (2 plus 3) times 4\nsay 2 ** 3 ** 2\n", "20\n512\n")

    def test_if_and_otherwise(self):
        self.assertBothBackends(
            "let score be 12\nif score is at least 10 then\nsay \"pass\"\notherwise\nsay \"fail\"\nend if\n",
            "pass\n",
        )

    def test_while_and_repeat(self):
        self.assertBothBackends(
            "let n be 0\nwhile n is less than 3 do\nset n to n plus 1\nend while\nrepeat 2 times do\nsay n\nend repeat\n",
            "3\n3\n",
        )

    def test_lists_and_builtins(self):
        self.assertBothBackends(
            "let values be [3, 8, 2]\nsay length(values)\nsay largest(values)\nsay smallest(values)\nsay sqrt(81)\n",
            "3\n8\n2\n9\n",
        )

    def test_short_circuit_and(self):
        self.assertBothBackends("say no and missing_name\nsay yes and yes\n", "no\nyes\n")

    def test_short_circuit_or(self):
        self.assertBothBackends("say yes or missing_name\nsay no or yes\nsay 2\n", "yes\nyes\n2\n")

    def test_boolean_operators_validate_right_operand(self):
        for source in ("say yes and 3\n", "say no or 3\n"):
            with self.subTest(source=source):
                with self.assertRaisesRegex(core.PlainlyCoreError, "yes/no"):
                    bytecode.run_source(source)

    def test_nested_repeat_and_conditionals(self):
        self.assertBothBackends(
            "let total be 0\nrepeat 2 times do\nrepeat 3 times do\nset total to total plus 1\nend repeat\nend repeat\nif total is equal to 6 then\nsay total\nend if\n",
            "6\n",
        )

    def test_unary_minus_rejects_non_numbers_cleanly(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "needs numbers"):
            bytecode.run_source('say -"text"\n')

    def test_duplicate_json_keys_are_rejected(self):
        payload = b'{"format":1,"format":1,"code":[["HALT"]]}'
        blob = bytecode.MAGIC + struct.pack(">HI", bytecode.VERSION, len(payload)) + hashlib.sha256(payload).digest() + payload
        with self.assertRaisesRegex(bytecode.CoreBytecodeError, "duplicate"):
            bytecode.loads(blob)

    def test_unicode(self):
        self.assertBothBackends('say "नमस्ते കേരളം"\n', "नमस्ते കേരളം\n")

    def test_division_by_zero(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "division by zero"):
            bytecode.run_source("say 4 divided by 0\n")

    def test_infinite_loop_is_bounded(self):
        program = bytecode.compile_source("while yes do\nsay \"x\"\nend while\n")
        with self.assertRaisesRegex(core.PlainlyCoreError, "step limit"):
            bytecode.VirtualMachine(max_steps=30).run(program)

    def test_binary_round_trip(self):
        program = bytecode.compile_source("let x be 7\nsay x times 6\n")
        blob = bytecode.dumps(program)
        self.assertEqual(bytecode.VirtualMachine().run(bytecode.loads(blob)), "42\n")

    def test_checksum_rejects_tampering(self):
        blob = bytearray(bytecode.dumps(bytecode.compile_source("say 1\n")))
        blob[-1] ^= 1
        with self.assertRaisesRegex(bytecode.CoreBytecodeError, "checksum"):
            bytecode.loads(blob)

    def test_unknown_opcode_rejected(self):
        program = bytecode.compile_source("say 1\n")
        program["code"][0][0] = "EXECUTE_PYTHON"
        with self.assertRaisesRegex(bytecode.CoreBytecodeError, "unknown instruction|invalid instruction"):
            bytecode.dumps(program)

    def test_non_text_opcode_is_rejected_cleanly(self):
        program = bytecode.compile_source("say 1\n")
        program["code"][0][0] = []
        with self.assertRaisesRegex(bytecode.CoreBytecodeError, "invalid instruction"):
            bytecode.dumps(program)

    def test_non_text_operator_is_rejected_cleanly(self):
        program = bytecode.compile_source("say 1 plus 2\n")
        for instruction in program["code"]:
            if instruction[0] == "BINARY":
                instruction[1] = []
                break
        with self.assertRaisesRegex(bytecode.CoreBytecodeError, "invalid binary operator"):
            bytecode.dumps(program)

    def test_invalid_jump_rejected(self):
        program = bytecode.compile_source("say 1\n")
        program["code"][0] = ["JUMP", 999999, 1]
        with self.assertRaisesRegex(bytecode.CoreBytecodeError, "outside the program"):
            bytecode.dumps(program)

    def test_repeat_budget_includes_empty_body(self):
        program = bytecode.compile_source("repeat 100000 times do\nend repeat\n")
        with self.assertRaisesRegex(core.PlainlyCoreError, "step limit"):
            bytecode.VirtualMachine(max_steps=30).run(program)


if __name__ == "__main__":
    unittest.main()
