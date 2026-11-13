import io
import unittest
import zipfile

from b109tasks.archive import UnsafeArchiveError, find, is_safe_member, list_archive, total_size


def make_zip(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in members:
            zf.writestr(name, data)
    buffer.seek(0)
    return buffer


class SafetyTest(unittest.TestCase):
    def test_safe_names(self):
        for name in ["a.txt", "dir/", "dir/sub/file.bin", "weird..name", "dir\\file.txt"]:
            with self.subTest(name=name):
                self.assertTrue(is_safe_member(name))

    def test_unsafe_names(self):
        for name in ["", "/etc/passwd", "\\server\\share", "C:/x", "c:\\x", "..", "../up.txt", "..\\up.txt"]:
            with self.subTest(name=name):
                self.assertFalse(is_safe_member(name))


class ListArchiveTest(unittest.TestCase):
    def test_directories_first(self):
        z = make_zip([("z/", b""), ("a.txt", b""), ("m/", b""), ("m/f.txt", b"")])
        self.assertEqual([e.name for e in list_archive(z)], ["m/", "z/", "a.txt", "m/f.txt"])

    def test_lists_sorted(self):
        z = make_zip([("b.txt", b"hello"), ("a/", b""), ("a/c.txt", b"x" * 10)])
        entries = list_archive(z)
        self.assertEqual([e.name for e in entries], ["a/", "a/c.txt", "b.txt"])
        self.assertTrue(entries[0].is_dir)
        self.assertEqual(total_size(entries), 15)

    def test_find(self):
        entries = list_archive(make_zip([("a/x.py", b""), ("a/y.txt", b""), ("b/z.py", b"")]))
        self.assertEqual([e.name for e in find(entries, "*.py")], ["a/x.py", "b/z.py"])

    def test_rejects_unsafe(self):
        z = make_zip([("ok.txt", b""), ("../evil.txt", b"")])
        with self.assertRaises(UnsafeArchiveError) as ctx:
            list_archive(z)
        self.assertEqual(ctx.exception.member, "../evil.txt")

    def test_max_entries(self):
        z = make_zip([(f"f{i}", b"") for i in range(5)])
        with self.assertRaises(ValueError):
            list_archive(z, max_entries=4)


if __name__ == "__main__":
    unittest.main()
