import unittest
from decimal import Decimal

from b109tasks.csvreport import Column, Report, format_value
from b109tasks.money import CurrencyMismatch, Money


class FormatValueTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(format_value(None, "int"), "")
        self.assertEqual(format_value(7.0, "int"), "7")
        self.assertEqual(format_value(Decimal("3.456"), "decimal2"), "3.46")
        self.assertEqual(format_value(0.125, "percent"), "12.5%")
        self.assertEqual(format_value(Money.of("12.5", "USD"), "money"), "12.50")
        self.assertEqual(format_value(Money.of("1000", "JPY"), "money"), "1000")
        self.assertEqual(format_value("x", None), "x")

    def test_money_column_rejects_other_types(self):
        with self.assertRaises(TypeError):
            format_value(12.5, "money")

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            Column("a", fmt="hex")


class ReportTest(unittest.TestCase):
    def make(self):
        report = Report([
            Column("region", "Region"),
            Column("orders", "Orders", "int"),
            Column("revenue", "Revenue", "money"),
        ])
        report.add_rows([
            {"region": "north", "orders": 3, "revenue": Money.of("120.5", "EUR")},
            {"region": "south, east", "orders": 10, "revenue": Money.of("99", "EUR")},
            {"region": "west"},
        ])
        return report

    def test_to_csv(self):
        self.assertEqual(self.make().to_csv(), (
            "Region,Orders,Revenue\n"
            "north,3,120.50\n"
            '"south, east",10,99.00\n'
            "west,,\n"
        ))

    def test_delimiter(self):
        self.assertTrue(self.make().to_csv(delimiter=";").startswith("Region;Orders;Revenue\n"))

    def test_sort_by(self):
        report = self.make()
        report.sort_by("orders", reverse=True)
        self.assertEqual([r["region"] for r in report.rows], ["south, east", "north", "west"])

    def test_plain_string_columns(self):
        report = Report(["a", "b"])
        report.add_row({"a": 1, "b": "x"})
        self.assertEqual(report.to_csv(), "a,b\n1,x\n")

    def test_bad_columns(self):
        with self.assertRaises(ValueError):
            Report([])
        with self.assertRaises(ValueError):
            Report(["a", "a"])


class TotalsTest(unittest.TestCase):
    def make(self):
        report = Report([Column("region", "Region"), Column("orders", "Orders", "int"),
                         Column("revenue", "Revenue", "money")])
        report.add_rows([
            {"region": "north", "orders": 3, "revenue": Money.of("120.5", "EUR")},
            {"region": "south", "orders": 10, "revenue": Money.of("99", "EUR")},
            {"region": "west"},
            {"region": "east", "revenue": Money.of("-20", "EUR")},
        ])
        return report

    def test_csv_totals(self):
        out = self.make().to_csv(totals=["orders", "revenue"]).splitlines()
        self.assertEqual(out[4], "east,,-20.00")
        self.assertEqual(out[-1], "Total,13,199.50")

    def test_totals_errors(self):
        with self.assertRaises(ValueError):
            self.make().to_csv(totals=["region"])
        with self.assertRaises(ValueError):
            self.make().to_csv(totals=["nope"])

    def test_markdown(self):
        self.assertEqual(self.make().to_markdown(totals=["orders"]), (
            "| Region | Orders | Revenue (EUR) |\n"
            "| ------ | -----: | ------------: |\n"
            "| north  |      3 |        120.50 |\n"
            "| south  |     10 |         99.00 |\n"
            "| west   |        |               |\n"
            "| east   |        |        -20.00 |\n"
            "| Total  |     13 |               |\n"
        ))

    def test_markdown_mixed_currencies(self):
        report = Report(["k", Column("m", fmt="money")])
        report.add_rows([{"k": 1, "m": Money.of("1", "USD")}, {"k": 2, "m": Money.of("1", "EUR")}])
        with self.assertRaises(CurrencyMismatch):
            report.to_markdown()


if __name__ == "__main__":
    unittest.main()
