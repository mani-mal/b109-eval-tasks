import unittest

from b109tasks.semver import Version, VersionError, compare, max_satisfying, satisfies


class VersionTest(unittest.TestCase):
    def test_parse(self):
        v = Version.parse("v1.2.3-beta.1+build.7")
        self.assertEqual(v.core, (1, 2, 3))
        self.assertEqual(v.prerelease, ("beta", "1"))
        self.assertEqual(v.build, ("build", "7"))

    def test_str_drops_build(self):
        self.assertEqual(str(Version.parse("1.2.3+b1")), "1.2.3")
        self.assertEqual(str(Version.parse("1.2.3-rc.1")), "1.2.3-rc.1")

    def test_invalid(self):
        for bad in ["1.2", "01.2.3", "1.2.3-", "a.b.c", "1.2.3+"]:
            with self.subTest(bad=bad), self.assertRaises(VersionError):
                Version.parse(bad)

    def test_ordering(self):
        self.assertLess(Version.parse("1.2.3"), Version.parse("1.10.0"))
        self.assertLess(Version.parse("1.0.0-alpha"), Version.parse("1.0.0"))
        self.assertLess(Version.parse("1.0.0-alpha"), Version.parse("1.0.0-beta"))
        self.assertLess(Version.parse("1.0.0-alpha"), Version.parse("1.0.0-alpha.1"))
        self.assertLess(Version.parse("1.0.0-alpha.1"), Version.parse("1.0.0-alpha.2"))

    def test_build_ignored_for_equality(self):
        self.assertEqual(Version.parse("1.0.0+a"), Version.parse("1.0.0+b"))
        self.assertEqual(compare("1.0.0", "1.0.0+x"), 0)
        self.assertEqual(compare("2.0.0", "1.9.9"), 1)


class SatisfiesTest(unittest.TestCase):
    def test_comparators(self):
        self.assertTrue(satisfies("1.4.0", ">=1.2.0 <2.0.0"))
        self.assertFalse(satisfies("2.0.0", ">=1.2.0 <2.0.0"))
        self.assertTrue(satisfies("1.2.3", "1.2.3"))
        self.assertTrue(satisfies("1.2.3", "=1.2.3"))

    def test_caret(self):
        self.assertTrue(satisfies("1.9.0", "^1.2.3"))
        self.assertFalse(satisfies("2.0.0", "^1.2.3"))
        self.assertTrue(satisfies("0.2.9", "^0.2.3"))
        self.assertFalse(satisfies("0.3.0", "^0.2.3"))
        self.assertFalse(satisfies("0.0.4", "^0.0.3"))

    def test_tilde(self):
        self.assertTrue(satisfies("1.2.9", "~1.2.3"))
        self.assertFalse(satisfies("1.3.0", "~1.2.3"))

    def test_or(self):
        self.assertTrue(satisfies("3.1.0", "^1.0.0 || ^3.0.0"))
        self.assertFalse(satisfies("2.1.0", "^1.0.0 || ^3.0.0"))

    def test_max_satisfying(self):
        versions = ["1.0.0", "1.4.2", "1.10.1", "2.0.0"]
        self.assertEqual(str(max_satisfying(versions, "^1.0.0")), "1.10.1")
        self.assertIsNone(max_satisfying(versions, ">3.0.0"))


if __name__ == "__main__":
    unittest.main()
