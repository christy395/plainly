import os
import tempfile
import unittest

import plainly_core as core


class PlainlyCoreTests(unittest.TestCase):
    def test_own_interpreter_arithmetic_and_output(self):
        source = 'let total be 6 plus 4 times 2\nsay total\n'
        self.assertEqual(core.run_source(source), "14\n")

    def test_english_comparisons_and_branches(self):
        source = (
            "let points be 8\n"
            "if points is at least 5 then\n"
            "say \"passed\"\n"
            "otherwise\n"
            "say \"failed\"\n"
            "end if\n"
        )
        self.assertEqual(core.run_source(source), "passed\n")

    def test_while_loop_and_assignment(self):
        source = (
            "let n be 0\n"
            "while n is less than 3 do\n"
            "set n to n plus 1\n"
            "end while\n"
            "say n\n"
        )
        self.assertEqual(core.run_source(source), "3\n")

    def test_repeat_loop(self):
        source = "repeat 3 times do\nsay \"go\"\nend repeat\n"
        self.assertEqual(core.run_source(source), "go\ngo\ngo\n")

    def test_list_and_builtins(self):
        source = "let values be [3, 8, 2]\nsay length(values)\nsay largest(values)\nsay smallest(values)\n"
        self.assertEqual(core.run_source(source), "3\n8\n2\n")

    def test_short_circuit_does_not_evaluate_right_side(self):
        source = "say no and missing_name\nsay yes or missing_name\n"
        self.assertEqual(core.run_source(source), "no\nyes\n")

    def test_zero_division_is_reported(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "division by zero"):
            core.run_source("say 5 divided by 0\n")

    def test_unknown_names_are_reported(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "unknown name"):
            core.run_source("say missing\n")

    def test_invalid_block_is_reported(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "needs 'end if'"):
            core.check_source("if yes then\nsay \"x\"\n")

    def test_wrong_condition_type_is_reported(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "yes/no"):
            core.run_source("if 1 then\nsay \"x\"\nend if\n")

    def test_infinite_loop_hits_step_limit(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "step limit"):
            core.run_source("while yes do\nsay \"x\"\nend while\n", max_steps=30)

    def test_repeat_limit_is_enforced(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "repeat needs"):
            core.run_source("repeat 100001 times do\nsay \"x\"\nend repeat\n")

    def test_empty_repeat_still_spends_execution_budget(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "step limit"):
            core.run_source("repeat 100000 times do\nend repeat\n", max_steps=30)

    def test_cumulative_output_limit_is_enforced(self):
        payload = "a" * 7000
        source = 'let big be "' + payload + '"\nrepeat 200 times do\nsay big\nend repeat\n'
        with self.assertRaisesRegex(core.PlainlyCoreError, "output exceeded"):
            core.run_source(source)

    def test_text_limit_is_enforced(self):
        huge = "a" * (core.MAX_TEXT_LENGTH + 1)
        source = 'say "' + huge + '"\n'
        with self.assertRaisesRegex(core.PlainlyCoreError, "text value is too large|source is larger"):
            core.run_source(source)

    def test_token_limit_is_enforced(self):
        source = "say 1\n" * (core.MAX_TOKENS // 2 + 1)
        with self.assertRaisesRegex(core.PlainlyCoreError, "too many tokens"):
            core.check_source(source)

    def test_boolean_is_not_a_number(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "needs numbers"):
            core.run_source("say yes plus 1\n")

    def test_parentheses_and_precedence(self):
        self.assertEqual(core.run_source("say (2 plus 3) times 4\n"), "20\n")

    def test_power_binds_more_tightly_than_unary_minus(self):
        self.assertEqual(core.run_source("say -2 ** 2\n"), "-4\n")

    def test_empty_largest_list_has_clear_error(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "non-empty list"):
            core.run_source("say largest([])\n")

    def test_english_greater_than(self):
        self.assertEqual(core.run_source("say 9 is greater than 4\n"), "yes\n")

    def test_unicode_text_is_preserved(self):
        self.assertEqual(core.run_source('say "नमस्ते കേരളം"\n'), "नमस्ते കേരളം\n")

    def test_not_binds_to_comparison_before_and(self):
        self.assertEqual(core.run_source("say not 2 is less than 1\n"), "yes\n")

    def test_token_limit_counts_tokens_not_lines(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "too many tokens"):
            core.check_source("say 1\n" * (core.MAX_TOKENS // 2 + 1))

    def test_huge_integer_is_rejected_cleanly(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "number literal is too long"):
            core.run_source("say " + ("9" * 129) + "\n")

    def test_block_nesting_limit(self):
        depth = core.MAX_AST_DEPTH + 2
        source = "if yes then\n" * depth + "say 1\n" + "end if\n" * depth
        with self.assertRaisesRegex(core.PlainlyCoreError, "block nesting is too deep"):
            core.check_source(source)

    def test_unknown_function_is_reported(self):
        with self.assertRaisesRegex(core.PlainlyCoreError, "unknown function"):
            core.run_source("say do_something(1)\n")

    def test_execution_budget_rejects_invalid_values(self):
        for budget in (0, -1, True, 1.5, core.MAX_STEPS + 1):
            with self.subTest(budget=budget):
                with self.assertRaisesRegex(core.PlainlyCoreError, "execution budget"):
                    core.run_source("say 1\n", max_steps=budget)

    def test_combined_runtime_text_limit(self):
        source = 'let first be "' + ("a" * 6000) + '"\n'
        source += "".join("let copy_%d be first\n" % index for index in range(180))
        with self.assertRaisesRegex(core.PlainlyCoreError, "combined runtime text limit"):
            core.run_source(source)

    def test_source_loader_rejects_symlink(self):
        if not hasattr(os, "symlink") or not hasattr(os, "O_NOFOLLOW"):
            self.skipTest("platform does not expose no-follow file opens")
        with tempfile.TemporaryDirectory() as folder:
            target = os.path.join(folder, "target.plain")
            link = os.path.join(folder, "link.plain")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("say 1\n")
            os.symlink(target, link)
            with self.assertRaises(core.PlainlyCoreError):
                core.read_source_file(link)

    def test_source_loader_rejects_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "invalid.plain")
            with open(path, "wb") as handle:
                handle.write(b"say \xff\n")
            with self.assertRaisesRegex(core.PlainlyCoreError, "valid UTF-8"):
                core.read_source_file(path)



if __name__ == "__main__":
    unittest.main()
