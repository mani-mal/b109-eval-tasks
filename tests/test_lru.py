import unittest

from b109tasks.lru import LRUCache


class LRUCacheTest(unittest.TestCase):
    def test_put_and_get(self):
        cache = LRUCache(2)
        cache.put("a", 1)
        self.assertEqual(cache.get("a"), 1)
        self.assertIsNone(cache.get("zzz"))
        self.assertEqual(cache.get("zzz", 0), 0)

    def test_evicts_oldest_insert(self):
        evicted = []
        cache = LRUCache(2, on_evict=lambda k, v: evicted.append((k, v)))
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertNotIn("a", cache)
        self.assertEqual(evicted, [("a", 1)])
        self.assertEqual(cache.keys(), ["b", "c"])

    def test_put_existing_refreshes(self):
        cache = LRUCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 10)
        cache.put("c", 3)
        self.assertEqual(cache.keys(), ["a", "c"])
        self.assertEqual(cache.get("a"), 10)

    def test_contains_does_not_count(self):
        cache = LRUCache(2)
        cache.put("a", 1)
        self.assertIn("a", cache)
        self.assertEqual(cache.stats()["hits"], 0)

    def test_stats(self):
        cache = LRUCache(3)
        cache.put("a", 1)
        cache.get("a")
        cache.get("a")
        cache.get("b")
        self.assertEqual(cache.stats(), {"hits": 2, "misses": 1, "size": 1, "hit_rate": 2 / 3})
        cache.clear()
        self.assertEqual(cache.stats()["hit_rate"], 0.0)
        self.assertEqual(len(cache), 0)

    def test_resize_evicts(self):
        evicted = []
        cache = LRUCache(3, on_evict=lambda k, v: evicted.append(k))
        for k in "abc":
            cache.put(k, k)
        cache.resize(1)
        self.assertEqual(evicted, ["a", "b"])
        self.assertEqual(cache.keys(), ["c"])

    def test_delete(self):
        cache = LRUCache(2)
        cache.put("a", 1)
        self.assertTrue(cache.delete("a"))
        self.assertFalse(cache.delete("a"))

    def test_bad_capacity(self):
        with self.assertRaises(ValueError):
            LRUCache(0)


if __name__ == "__main__":
    unittest.main()
