import unittest

from b109tasks.mdtable import format_table


class FormatTableTest(unittest.TestCase):
    def test_basic(self):
        out = format_table(["name", "qty"], [["apple", 3], ["kiwi", 12]])
        self.assertEqual(out, (
            "| name  | qty |\n"
            "| ----- | --- |\n"
            "| apple | 3   |\n"
            "| kiwi  | 12  |\n"
        ))

    def test_right_alignment(self):
        out = format_table(["item", "price"], [["tea", "1.50"], ["cake", "12.00"]],
                           align=["left", "right"])
        self.assertEqual(out, (
            "| item | price |\n"
            "| ---- | ----: |\n"
            "| tea  |  1.50 |\n"
            "| cake | 12.00 |\n"
        ))

    def test_none_and_newlines(self):
        out = format_table(["a", "b"], [[None, "two\nlines"]])
        self.assertIn("|     | two lines |", out)

    def test_no_rows(self):
        self.assertEqual(format_table(["x"], []), "| x   |\n| --- |\n")

    def test_errors(self):
        with self.assertRaises(ValueError):
            format_table([], [])
        with self.assertRaises(ValueError):
            format_table(["a", "b"], [["only one"]])
        with self.assertRaises(ValueError):
            format_table(["a"], [], align=["middle"])
        with self.assertRaises(ValueError):
            format_table(["a"], [], align=["left", "left"])


class MaxWidthTest(unittest.TestCase):
    def test_truncates_long_cells(self):
        out = format_table(["word"], [["hello"], ["hello world"]], max_width=5)
        self.assertEqual(out, "| word  |\n| ----- |\n| hello |\n| hell\u2026 |\n")


if __name__ == "__main__":
    unittest.main()
