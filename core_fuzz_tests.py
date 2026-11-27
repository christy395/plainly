#!/usr/bin/env python3
"""Deterministic robustness tests for untrusted Plainly source and bytecode."""
import random
import unittest

import plainly_core as core
import plainly_core_bytecode as bytecode


class CoreFuzzTests(unittest.TestCase):
    def test_seeded_source_mutations_never_escape_as_unexpected_errors(self):
        rng = random.Random(0x504C4149)
        seeds = [
            "say 1\n",
            "let name be \"Plainly\"\nsay name\n",
            "if yes then\nsay \"ok\"\nend if\n",
            "repeat 2 times do\nsay 3\nend repeat\n",
            "say [1, 2, 3]\n",
        ]
        alphabet = "abcXYZ0123 +-*/()[],:#\"\\\n\t_"
        cases = list(seeds)
        for _ in range(300):
            base = rng.choice(seeds)
            chars = list(base)
            for _ in range(rng.randint(1, 5)):
                action = rng.randrange(3)
                position = rng.randrange(len(chars) + 1)
                if action == 0 and chars:
                    if position == len(chars):
                        position -= 1
                    chars.pop(position)
                elif action == 1:
                    chars.insert(position, rng.choice(alphabet))
                elif chars:
                    if position == len(chars):
                        position -= 1
                    chars[position] = rng.choice(alphabet)
            cases.append("".join(chars))
        for source in cases:
            try:
                program = bytecode.compile_source(source)
                blob = bytecode.dumps(program)
                bytecode.VirtualMachine(max_steps=1000).run(bytecode.loads(blob))
            except (core.PlainlyCoreError, bytecode.CoreBytecodeError):
                pass

    def test_random_binary_inputs_are_rejected_or_decoded_safely(self):
        rng = random.Random(0x50424331)
        for _ in range(300):
            blob = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 256)))
            try:
                program = bytecode.loads(blob)
                bytecode.VirtualMachine(max_steps=1000).run(program)
            except bytecode.CoreBytecodeError:
                pass

    def test_deeply_nested_json_bytecode_is_rejected_cleanly(self):
        payload = b'{"format":1,"code":' + (b"[" * 5000) + b"0" + (b"]" * 5000) + b"}"
        import hashlib
        import struct
        blob = bytecode.MAGIC + struct.pack(">HI", bytecode.VERSION, len(payload)) + hashlib.sha256(payload).digest() + payload
        with self.assertRaises(bytecode.CoreBytecodeError):
            bytecode.loads(blob)


if __name__ == "__main__":
    unittest.main()
