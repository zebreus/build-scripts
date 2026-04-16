import unittest

import multidict
from multidict import MultiDict, CIMultiDict, MultiDictProxy, CIMultiDictProxy, istr


class TestMultiDictReferenceAPI(unittest.TestCase):
    def test_constructor_variants_and_len(self):
        d1 = MultiDict()
        self.assertEqual(len(d1), 0)

        d2 = MultiDict([("a", 1), ("b", 2), ("a", 3)])
        self.assertEqual(len(d2), 3)
        self.assertEqual(list(d2.items()), [("a", 1), ("b", 2), ("a", 3)])

        d3 = MultiDict({"x": "y"}, z="w")
        self.assertEqual(list(d3.items()), [("x", "y"), ("z", "w")])

        d4 = MultiDict(red=1, blue=2)
        self.assertEqual(d4.getone("red"), 1)
        self.assertEqual(d4.getone("blue"), 2)

    def test_getitem_setitem_delitem_semantics(self):
        d = MultiDict([("a", 1), ("a", 2), ("b", 3)])

        # d[key] returns first value
        self.assertEqual(d["a"], 1)
        with self.assertRaises(KeyError):
            _ = d["missing"]

        # assignment replaces ALL occurrences with a single one
        d["a"] = 10
        self.assertEqual(d.getall("a"), [10])
        self.assertEqual(list(d.items()), [("a", 10), ("b", 3)])

        # deletion removes ALL occurrences
        del d["a"]
        self.assertNotIn("a", d)
        self.assertEqual(list(d.items()), [("b", 3)])
        with self.assertRaises(KeyError):
            del d["missing"]

    def test_in_iter_keys_items_values(self):
        d = MultiDict([("a", 1), ("a", 2), ("b", 3)])

        self.assertIn("a", d)
        self.assertNotIn("c", d)

        # iter(d) == iter(d.keys())
        self.assertEqual(list(iter(d)), list(d.keys()))
        self.assertEqual(list(d.keys()), ["a", "a", "b"])
        self.assertEqual(list(d.items()), [("a", 1), ("a", 2), ("b", 3)])
        self.assertEqual(list(d.values()), [1, 2, 3])

    def test_add_clear_copy(self):
        d = MultiDict()
        d.add("a", 1)
        d.add("a", 2)
        self.assertEqual(d.getall("a"), [1, 2])

        c = d.copy()
        self.assertEqual(c.getall("a"), [1, 2])
        c.add("a", 3)
        self.assertEqual(d.getall("a"), [1, 2])
        self.assertEqual(c.getall("a"), [1, 2, 3])

        d.clear()
        self.assertEqual(len(d), 0)

    def test_get_getone_getall_defaults_and_errors(self):
        d = MultiDict([("a", 1), ("a", 2)])

        self.assertEqual(d.get("a"), 1)
        self.assertIsNone(d.get("missing"))

        self.assertEqual(d.getone("a"), 1)
        self.assertEqual(d.getone("missing", 99), 99)
        with self.assertRaises(KeyError):
            d.getone("missing")

        self.assertEqual(d.getall("a"), [1, 2])
        self.assertEqual(d.getall("missing", []), [])
        with self.assertRaises(KeyError):
            d.getall("missing")

    def test_popone_pop_popall_semantics(self):
        d = MultiDict([("a", 1), ("a", 2), ("a", 3), ("b", 9)])

        # popone removes only first occurrence
        self.assertEqual(d.popone("a"), 1)
        self.assertEqual(d.getall("a"), [2, 3])

        # pop is alias to popone and also removes only first occurrence
        self.assertEqual(d.pop("a"), 2)
        self.assertEqual(d.getall("a"), [3])

        # popall removes all occurrences and returns list in order
        self.assertEqual(d.popall("a"), [3])
        self.assertNotIn("a", d)

        # defaults / KeyError
        self.assertEqual(d.popone("missing", "D"), "D")
        self.assertEqual(d.pop("missing", "D2"), "D2")
        self.assertEqual(d.popall("missing", ["X"]), ["X"])
        with self.assertRaises(KeyError):
            d.popone("missing2")
        with self.assertRaises(KeyError):
            d.pop("missing3")
        with self.assertRaises(KeyError):
            d.popall("missing4")

    def test_popitem(self):
        d = MultiDict([("a", 1), ("b", 2)])
        k, v = d.popitem()
        self.assertIn((k, v), {("a", 1), ("b", 2)})
        self.assertEqual(len(d), 1)
        d.popitem()
        self.assertEqual(len(d), 0)
        with self.assertRaises(KeyError):
            d.popitem()

    def test_setdefault(self):
        d = MultiDict([("a", 1), ("a", 2)])
        self.assertEqual(d.setdefault("a", 100), 1)  # first value
        self.assertEqual(d.getall("a"), [1, 2])      # unchanged for existing key

        self.assertEqual(d.setdefault("missing", 7), 7)
        self.assertEqual(d.getall("missing"), [7])

        d2 = MultiDict()
        self.assertIsNone(d2.setdefault("x"))         # default defaults to None
        self.assertEqual(d2.getall("x"), [None])

    def test_extend_update_and_merge(self):
        # extend appends values for existing keys
        d = MultiDict([("a", 1)])
        d.extend([("a", 2), ("b", 3)], c=4)
        self.assertEqual(d.getall("a"), [1, 2])
        self.assertEqual(d.getall("b"), [3])
        self.assertEqual(d.getall("c"), [4])

        # update overwrites existing keys (replaces all occurrences)
        d2 = MultiDict([("a", 1), ("a", 2), ("b", 9)])
        d2.update([("a", 10), ("a", 11)], b=7)
        self.assertEqual(d2.getall("a"), [10, 11])
        self.assertEqual(d2.getall("b"), [7])

        # merge appends only non-existing keys; existing keys are skipped
        d3 = MultiDict([("a", 1)])
        if hasattr(d3, "merge"):
            d3.merge([("a", 2), ("b", 3)], c=4)
            self.assertEqual(d3.getall("a"), [1])     # unchanged (skipped)
            self.assertEqual(d3.getall("b"), [3])     # added
            self.assertEqual(d3.getall("c"), [4])     # added
        else:
            self.skipTest("merge() not available in this multidict version")

    def test_key_type_is_str_or_subclass(self):
        d = MultiDict()
        with self.assertRaises(TypeError):
            d.add(1, "nope")

        class S(str):
            pass

        d.add(S("k"), "v")
        self.assertIn("k", d)
        self.assertEqual(d.getone("k"), "v")

    def test_version_changes_on_mutation_and_works_for_proxies(self):
        d = MultiDict([("a", 1)])
        v1 = multidict.getversion(d)

        d.add("a", 2)
        v2 = multidict.getversion(d)
        self.assertNotEqual(v1, v2)

        p = MultiDictProxy(d)
        self.assertEqual(multidict.getversion(p), multidict.getversion(d))

        d["a"] = 100
        self.assertNotEqual(v2, multidict.getversion(d))
        self.assertEqual(multidict.getversion(p), multidict.getversion(d))


class TestCIMultiDictReferenceAPI(unittest.TestCase):
    def test_case_insensitive_lookup_and_contains(self):
        d = CIMultiDict([("Header", "v1"), ("header", "v2")])

        self.assertIn("HEADER", d)
        self.assertIn("header", d)
        self.assertEqual(d["HEADER"], "v1")
        self.assertEqual(d.getall("HeAdEr"), ["v1", "v2"])

    def test_case_insensitive_assignment_replaces_all(self):
        d = CIMultiDict([("Header", "v1"), ("header", "v2"), ("Other", "x")])
        d["HEADER"] = "NEW"
        self.assertEqual(d.getall("header"), ["NEW"])
        self.assertEqual(d.getall("other"), ["x"])

    def test_case_insensitive_del_and_popall(self):
        d = CIMultiDict([("A", 1), ("a", 2), ("B", 3)])
        del d["a"]
        self.assertNotIn("A", d)
        self.assertIn("b", d)

        d2 = CIMultiDict([("A", 1), ("a", 2), ("B", 3)])
        vals = d2.popall("a")
        self.assertEqual(vals, [1, 2])
        self.assertNotIn("A", d2)

    def test_istr_optimization_key_behaves(self):
        key = istr("Key")
        d = CIMultiDict([("key", "value")])
        self.assertIn(key, d)
        self.assertEqual(d[key], "value")

    def test_ci_rejects_non_str_keys(self):
        d = CIMultiDict()
        with self.assertRaises(TypeError):
            d.add(1, "nope")


class TestProxiesReferenceAPI(unittest.TestCase):
    def test_proxy_requires_correct_type(self):
        with self.assertRaises(TypeError):
            MultiDictProxy({"a": 1})  # not a MultiDict

        with self.assertRaises(TypeError):
            CIMultiDictProxy(MultiDict([("a", 1)]))  # wrong underlying type

    def test_multidict_proxy_read_only_surface(self):
        d = MultiDict([("a", 1), ("a", 2)])
        p = MultiDictProxy(d)

        self.assertEqual(len(p), 2)
        self.assertEqual(p["a"], 1)
        self.assertEqual(p.getall("a"), [1, 2])
        self.assertEqual(list(p.items()), [("a", 1), ("a", 2)])

        # proxy should not allow item assignment/deletion
        with self.assertRaises(TypeError):
            p["a"] = 10
        with self.assertRaises(TypeError):
            del p["a"]

        # proxy provides copy() returning a MultiDict (mutable copy of underlying)
        c = p.copy()
        self.assertIsInstance(c, MultiDict)
        c.add("a", 3)
        self.assertEqual(d.getall("a"), [1, 2])      # underlying unchanged by modifying copy
        self.assertEqual(c.getall("a"), [1, 2, 3])

    def test_proxy_is_dynamic_view(self):
        d = MultiDict([("a", 1)])
        p = MultiDictProxy(d)
        self.assertEqual(p.getall("a"), [1])

        d.add("a", 2)
        self.assertEqual(p.getall("a"), [1, 2])

        d["a"] = 100
        self.assertEqual(p.getall("a"), [100])

    def test_ci_proxy_case_insensitive(self):
        d = CIMultiDict([("Header", "v1"), ("header", "v2")])
        p = CIMultiDictProxy(d)
        self.assertEqual(p["HEADER"], "v1")
        self.assertEqual(p.getall("HeAdEr"), ["v1", "v2"])

        with self.assertRaises(TypeError):
            p["header"] = "X"
        with self.assertRaises(TypeError):
            del p["HEADER"]


if __name__ == "__main__":
    unittest.main(verbosity=2)
