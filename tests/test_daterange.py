import datetime as dt
import unittest

from b109tasks.daterange import DateRange, DateRangeError, parse_range, split_by_month


def d(text):
    return dt.date.fromisoformat(text)


class ParseRangeTest(unittest.TestCase):
    def test_single_day(self):
        r = parse_range("2024-03-05")
        self.assertEqual((r.start, r.end), (d("2024-03-05"), d("2024-03-05")))
        self.assertEqual(r.days, 1)

    def test_whole_month(self):
        r = parse_range("2023-04")
        self.assertEqual((r.start, r.end), (d("2023-04-01"), d("2023-04-30")))

    def test_february_in_leap_year(self):
        self.assertEqual(parse_range("2024-02").end, d("2024-02-29"))
        self.assertEqual(parse_range("2023-02").end, d("2023-02-28"))

    def test_whole_year(self):
        r = parse_range("2022")
        self.assertEqual((r.start, r.end), (d("2022-01-01"), d("2022-12-31")))
        self.assertEqual(r.days, 365)

    def test_explicit_range_with_spaces(self):
        r = parse_range(" 2024-01-30 .. 2024-02-02 ")
        self.assertEqual(r.days, 4)

    def test_month_to_month(self):
        r = parse_range("2024-03..2024-05")
        self.assertEqual((r.start, r.end), (d("2024-03-01"), d("2024-05-31")))

    def test_errors(self):
        for bad in ["", "2024-13", "2024-02-30", "2024-03-10..2024-03-01", "yesterday", "2024..", "..2024"]:
            with self.subTest(bad=bad), self.assertRaises(DateRangeError):
                parse_range(bad)


class DateRangeTest(unittest.TestCase):
    def test_contains_and_iter(self):
        r = parse_range("2024-01-30..2024-02-01")
        self.assertIn(d("2024-01-31"), r)
        self.assertNotIn(d("2024-02-02"), r)
        self.assertNotIn("2024-01-31", r)
        self.assertEqual([x.isoformat() for x in r.iter_days()],
                         ["2024-01-30", "2024-01-31", "2024-02-01"])

    def test_overlap_and_intersection(self):
        a = parse_range("2024-01-01..2024-01-10")
        b = parse_range("2024-01-08..2024-01-20")
        c = parse_range("2024-02")
        self.assertTrue(a.overlaps(b))
        self.assertEqual(a.intersection(b), DateRange(d("2024-01-08"), d("2024-01-10")))
        self.assertIsNone(a.intersection(c))

    def test_str(self):
        self.assertEqual(str(parse_range("2024-01-05..2024-01-07")), "2024-01-05..2024-01-07")

    def test_reversed_constructor_rejected(self):
        with self.assertRaises(DateRangeError):
            DateRange(d("2024-01-02"), d("2024-01-01"))

    def test_split_by_month(self):
        parts = split_by_month(parse_range("2024-01-20..2024-03-03"))
        self.assertEqual([str(p) for p in parts], [
            "2024-01-20..2024-01-31",
            "2024-02-01..2024-02-29",
            "2024-03-01..2024-03-03",
        ])


if __name__ == "__main__":
    unittest.main()
