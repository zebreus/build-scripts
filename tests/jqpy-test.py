import unittest
import jq  # Will raise ImportError immediately if not installed


def _drain_iterator(it):
    return list(iter(it))


class TestPythonJQ(unittest.TestCase):
    # ---------- Compile & basic passthrough ----------
    def test_compile_and_passthrough_program_string(self):
        program = jq.compile(".")
        self.assertEqual(program.program_string, ".")
        self.assertIsNone(program.input_value(None).first())
        self.assertEqual(program.input_value(42).first(), 42)
        self.assertEqual(program.input_value(0.42).first(), 0.42)
        self.assertEqual(program.input_value(True).first(), True)
        self.assertEqual(program.input_value("hello").first(), "hello")

    # ---------- Input methods: input_value(s) ----------
    def test_input_values_list(self):
        self.assertEqual(
            jq.compile(".+5").input_values([1, 2, 3]).all(),
            [6, 7, 8],
        )

    def test_input_values_generator(self):
        def gen():
            for i in range(3):
                yield i
        self.assertEqual(
            jq.compile(".+10").input_values(gen()).all(),
            [10, 11, 12],
        )

    # ---------- Input methods: input_text (including slurp) ----------
    def test_input_text_scalars_and_lines(self):
        self.assertIsNone(jq.compile(".").input_text("null").first())
        self.assertEqual(jq.compile(".").input_text("42").first(), 42)
        self.assertEqual(jq.compile(".").input_text("0.42").first(), 0.42)
        self.assertEqual(jq.compile(".").input_text("true").first(), True)
        self.assertEqual(jq.compile(".").input_text('"hello"').first(), "hello")
        # multiple JSON values across lines
        self.assertEqual(
            jq.compile(".").input_text("1\n2\n3").all(),
            [1, 2, 3],
        )

    def test_input_text_slurp(self):
        self.assertEqual(
            jq.compile(".").input_text("1\n2\n3", slurp=True).first(),
            [1, 2, 3],
        )

    def test_input_text_unicode(self):
        text = '"😊 café 𝛑"'
        self.assertEqual(jq.compile(".").input_text(text).first(), "😊 café 𝛑")

    # ---------- Legacy input() ----------
    def test_legacy_input_api(self):
        self.assertEqual(jq.compile(".").input("hello").first(), "hello")
        self.assertEqual(jq.compile(".").input(text='"hello"').first(), "hello")

    # ---------- Output methods ----------
    def test_output_first(self):
        self.assertEqual(
            jq.compile("[.[]+1]").input_value([1, 2, 3]).first(),
            [2, 3, 4],
        )
        self.assertEqual(
            jq.compile(".[]+1").input_value([1, 2, 3]).first(),
            2,
        )

    def test_output_text_single_and_multiple(self):
        self.assertEqual(
            jq.compile(".").input_value("42").text(),
            '"42"',
        )
        self.assertEqual(
            jq.compile(".[]").input_value([1, 2, 3]).text(),
            "1\n2\n3",
        )

    def test_output_all(self):
        self.assertEqual(
            jq.compile(".[]+1").input_value([1, 2, 3]).all(),
            [2, 3, 4],
        )

    def test_output_iter(self):
        iterator = iter(jq.compile(".[]+1").input_value([1, 2, 3]))
        self.assertEqual(next(iterator, None), 2)
        self.assertEqual(next(iterator, None), 3)
        self.assertEqual(next(iterator, None), 4)
        self.assertIsNone(next(iterator, None))

    def test_iter_drain_helper(self):
        it = jq.iter(".[] + 1", [0, 10, 20])
        self.assertEqual(_drain_iterator(it), [1, 11, 21])

    # ---------- Predefined args ----------
    def test_predefined_args(self):
        program = jq.compile("$a + $b + .", args={"a": 100, "b": 20})
        self.assertEqual(program.input_value(3).first(), 123)

    # ---------- Convenience functions ----------
    def test_convenience_first_text_all_iter(self):
        self.assertEqual(jq.first(".[] + 1", [1, 2, 3]), 2)
        self.assertEqual(jq.first(".[] + 1", text="[1, 2, 3]"), 2)
        self.assertEqual(jq.text(".[] + 1", [1, 2, 3]), "2\n3\n4")
        self.assertEqual(jq.all(".[] + 1", [1, 2, 3]), [2, 3, 4])
        self.assertEqual(list(jq.iter(".[] + 1", [1, 2, 3])), [2, 3, 4])

    # ---------- Structured data ----------
    def test_structured_outputs_objects_arrays(self):
        data = {"a": 1, "b": 2}
        # Avoid potential parse quirks with .[] inside object literals by building arr explicitly
        program = jq.compile('{ "sum": (.a + .b), "arr": [(.a + 1), (.b + 1)] }')
        self.assertEqual(program.input_value(data).first(), {"sum": 3, "arr": [2, 3]})

    def test_boolean_and_null_handling(self):
        self.assertEqual(jq.compile("true").input_value(None).first(), True)
        self.assertIsNone(jq.compile("null").input_value("ignored").first())

    # ---------- Multi-input ----------
    def test_multiple_inputs_stream(self):
        prog = jq.compile(".+1 | . * 2")
        self.assertEqual(prog.input_values([1, 2, 3]).all(), [4, 6, 8])

    # ---------- Roundtrip ----------
    def test_text_roundtrip_complex(self):
        data = {"name": "alice", "tags": ["a", "b"], "active": True, "score": 9.5, "meta": None}
        out_text = jq.compile(".").input_value(data).text()
        parsed = jq.compile(".").input_text(out_text).first()
        self.assertEqual(parsed, data)


if __name__ == "__main__":
    unittest.main(verbosity=2)