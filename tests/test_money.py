import unittest
from decimal import Decimal

from b109tasks.money import CurrencyMismatch, Money, sum_money


class MoneyTest(unittest.TestCase):
    def test_of_rounds_half_even(self):
        self.assertEqual(Money.of("2.345", "USD").amount, Decimal("2.34"))
        self.assertEqual(Money.of("2.355", "usd").amount, Decimal("2.36"))
        self.assertEqual(Money.of("12.5", "JPY").amount, Decimal("12"))
        self.assertEqual(Money.of("1.0005", "KWD").amount, Decimal("1.000"))

    def test_rejects_float_and_unknown_currency(self):
        with self.assertRaises(TypeError):
            Money.of(1.5, "USD")
        with self.assertRaises(ValueError):
            Money.of("1", "XXX")
        with self.assertRaises(ValueError):
            Money.of("abc", "USD")

    def test_add_sub_neg(self):
        a = Money.of("10.00", "EUR")
        b = Money.of("2.50", "EUR")
        self.assertEqual(a + b, Money.of("12.50", "EUR"))
        self.assertEqual(a - b, Money.of("7.50", "EUR"))
        self.assertEqual(-b, Money.of("-2.50", "EUR"))

    def test_currency_mismatch(self):
        with self.assertRaises(CurrencyMismatch):
            Money.of("1", "USD") + Money.of("1", "EUR")
        with self.assertRaises(CurrencyMismatch):
            Money.of("1", "USD") < Money.of("1", "EUR")
        with self.assertRaises(TypeError):
            Money.of("1", "USD") + 1

    def test_multiply(self):
        self.assertEqual(Money.of("10.00", "USD") * 3, Money.of("30.00", "USD"))
        self.assertEqual(Decimal("0.5") * Money.of("10.00", "USD"), Money.of("5.00", "USD"))
        self.assertEqual(Money.of("1000", "JPY") * "0.333", Money.of("333", "JPY"))
        with self.assertRaises(TypeError):
            Money.of("1", "USD") * 1.5

    def test_allocate(self):
        parts = Money.of("100.00", "USD").allocate([1, 1, 1])
        self.assertEqual([p.amount for p in parts], [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")])
        parts = Money.of("5", "JPY").allocate([3, 7])
        self.assertEqual([p.amount for p in parts], [Decimal("2"), Decimal("3")])
        with self.assertRaises(ValueError):
            Money.of("1", "USD").allocate([0, 0])

    def test_formatting(self):
        self.assertEqual(Money.of("1234.5", "USD").format(), "USD 1,234.50")
        self.assertEqual(Money.of("-5", "USD").format(), "USD -5.00")
        self.assertEqual(str(Money.of("1234567", "JPY")), "JPY 1,234,567")
        self.assertEqual(Money.of("1234.5", "USD").to_plain(), "1234.50")

    def test_compare(self):
        self.assertLess(Money.of("1", "USD"), Money.of("2", "USD"))
        self.assertTrue(Money.zero("GBP").is_zero())

    def test_sum_money(self):
        items = [Money.of("1.10", "USD"), Money.of("2.20", "USD")]
        self.assertEqual(sum_money(items), Money.of("3.30", "USD"))
        self.assertEqual(sum_money([], "USD"), Money.zero("USD"))
        with self.assertRaises(ValueError):
            sum_money([])


class UnlistedCurrencyTest(unittest.TestCase):
    def test_to_plain(self):
        self.assertEqual(Money(Decimal("1.5"), "XYZ").to_plain(), "1.50")


if __name__ == "__main__":
    unittest.main()
