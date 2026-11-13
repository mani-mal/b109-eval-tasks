import tempfile
import unittest
from pathlib import Path

from b109tasks.configmerge import (
    ConfigError, dumps, get, get_bool, get_float, get_int, interpolate, load_files, merge,
    parse,
)

SAMPLE = """
# service defaults
[server]
host = 0.0.0.0
port = 8080
banner = "  hello  "

; storage
[db]
url = postgres://localhost/app?sslmode=disable
pool = 5
"""


class ParseTest(unittest.TestCase):
    def test_parse(self):
        cfg = parse(SAMPLE)
        self.assertEqual(cfg["server"]["host"], "0.0.0.0")
        self.assertEqual(cfg["server"]["banner"], "  hello  ")
        self.assertEqual(cfg["db"]["url"], "postgres://localhost/app?sslmode=disable")

    def test_repeated_section_merges(self):
        cfg = parse("[a]\nx = 1\n[b]\ny = 2\n[a]\nz = 3\nx = 4\n")
        self.assertEqual(cfg["a"], {"x": "4", "z": "3"})

    def test_errors_carry_line_numbers(self):
        cases = {
            "x = 1": 1,
            "[a]\njunk": 2,
            "[a]\n= 1": 2,
            "[a\nx = 1": 1,
        }
        for text, line in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(ConfigError) as ctx:
                    parse(text)
                self.assertEqual(ctx.exception.line, line)


class MergeTest(unittest.TestCase):
    def test_disjoint_sections(self):
        merged = merge({"a": {"x": "1"}}, {"b": {"y": "2"}})
        self.assertEqual(merged, {"a": {"x": "1"}, "b": {"y": "2"}})

    def test_later_wins(self):
        merged = merge(parse("[a]\nx = 1\ny = 2"), parse("[a]\ny = 3"))
        self.assertEqual(merged["a"], {"x": "1", "y": "3"})

    def test_merge_nothing(self):
        self.assertEqual(merge(), {})


class AccessorTest(unittest.TestCase):
    def setUp(self):
        self.cfg = parse("[s]\nn = 42\nflag = Yes\nbad = maybe\nword = abc")

    def test_get(self):
        self.assertEqual(get(self.cfg, "s", "n"), "42")
        self.assertEqual(get(self.cfg, "s", "missing", "d"), "d")
        with self.assertRaises(KeyError):
            get(self.cfg, "nope", "n")

    def test_get_int(self):
        self.assertEqual(get_int(self.cfg, "s", "n"), 42)
        self.assertEqual(get_int(self.cfg, "s", "missing", 7), 7)
        with self.assertRaises(ConfigError):
            get_int(self.cfg, "s", "word")

    def test_get_float(self):
        cfg = parse("[s]\nratio = 0.25\n")
        self.assertEqual(get_float(cfg, "s", "ratio"), 0.25)
        self.assertEqual(get_float(cfg, "s", "missing", 1.5), 1.5)
        with self.assertRaises(KeyError):
            get_float(cfg, "s", "missing")

    def test_get_bool(self):
        self.assertTrue(get_bool(self.cfg, "s", "flag"))
        self.assertFalse(get_bool(self.cfg, "s", "missing", False))
        with self.assertRaises(ConfigError):
            get_bool(self.cfg, "s", "bad")


class DumpsAndFilesTest(unittest.TestCase):
    def test_dumps_sorted_and_round_trips(self):
        cfg = {"b": {"z": "1", "a": "2"}, "a": {"k": "v"}}
        text = dumps(cfg)
        self.assertEqual(text, "[a]\nk = v\n\n[b]\na = 2\nz = 1\n")
        self.assertEqual(parse(text), cfg)
        self.assertEqual(dumps({}), "")

    def test_load_files_skips_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp, "a.ini")
            second = Path(tmp, "b.ini")
            first.write_text("[s]\nx = 1\n", encoding="utf-8")
            second.write_text("[s]\nx = 2\n[t]\ny = 3\n", encoding="utf-8")
            cfg = load_files([first, Path(tmp, "missing.ini"), second])
        self.assertEqual(cfg, {"s": {"x": "2"}, "t": {"y": "3"}})


class InterpolateTest(unittest.TestCase):
    def test_references(self):
        cfg = parse("[paths]\nroot = /srv\n[app]\nlogs = ${paths.root}/logs\nold = ${app.logs}.1\n")
        out = interpolate(cfg)
        self.assertEqual(out["app"], {"logs": "/srv/logs", "old": "/srv/logs.1"})
        self.assertEqual(cfg["app"]["logs"], "${paths.root}/logs")

    def test_errors(self):
        with self.assertRaises(ConfigError):
            interpolate(parse("[a]\nx = ${a.nope}\n"))
        with self.assertRaises(ConfigError):
            interpolate(parse("[a]\nx = ${a.y}\ny = ${a.x}\n"))

    def test_load_files_resolves_after_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp, "base.ini")
            local = Path(tmp, "local.ini")
            base.write_text("[paths]\nroot = /srv\n[app]\nlogs = ${paths.root}/logs\n", encoding="utf-8")
            local.write_text("[paths]\nroot = /data\n", encoding="utf-8")
            cfg = load_files([base, local])
        self.assertEqual(cfg["app"]["logs"], "/data/logs")


if __name__ == "__main__":
    unittest.main()
