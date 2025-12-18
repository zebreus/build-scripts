import unittest
from collections.abc import MutableSequence

# Requires: pip install frozenlist
from frozenlist import FrozenList


class TestFrozenList(unittest.TestCase):
    def test_is_mutable_sequence(self):
        fl = FrozenList([1, 2, 3])
        self.assertIsInstance(fl, MutableSequence)

    def test_construction_from_iterables(self):
        self.assertEqual(list(FrozenList([])), [])
        self.assertEqual(list(FrozenList([1, 2])), [1, 2])
        self.assertEqual(list(FrozenList((1, 2, 3))), [1, 2, 3])
        self.assertEqual(list(FrozenList(x for x in [4, 5])), [4, 5])

    def test_frozen_property_and_freeze(self):
        fl = FrozenList([1, 2])
        self.assertFalse(fl.frozen)
        fl.freeze()
        self.assertTrue(fl.frozen)
        # Freezing twice should be safe
        fl.freeze()
        self.assertTrue(fl.frozen)

    def test_len_iter_getitem_setitem_delitem(self):
        fl = FrozenList([10, 20, 30])
        self.assertEqual(len(fl), 3)
        self.assertEqual(list(iter(fl)), [10, 20, 30])
        self.assertEqual(fl[0], 10)
        self.assertEqual(fl[-1], 30)

        fl[1] = 200
        self.assertEqual(list(fl), [10, 200, 30])

        del fl[0]
        self.assertEqual(list(fl), [200, 30])

    def test_slice_get_set_delete(self):
        fl = FrozenList([0, 1, 2, 3, 4, 5])
        self.assertEqual(fl[1:5], [1, 2, 3, 4])
        self.assertEqual(fl[::-1], [5, 4, 3, 2, 1, 0])

        fl[2:4] = [20, 30, 40]  # resize via slice assignment
        self.assertEqual(list(fl), [0, 1, 20, 30, 40, 4, 5])

        del fl[1:3]
        self.assertEqual(list(fl), [0, 30, 40, 4, 5])

    def test_insert_append_extend_pop_remove_clear(self):
        fl = FrozenList([1, 3])
        fl.insert(1, 2)
        self.assertEqual(list(fl), [1, 2, 3])

        fl.append(4)
        self.assertEqual(list(fl), [1, 2, 3, 4])

        fl.extend([5, 6])
        self.assertEqual(list(fl), [1, 2, 3, 4, 5, 6])

        v = fl.pop()
        self.assertEqual(v, 6)
        self.assertEqual(list(fl), [1, 2, 3, 4, 5])

        v2 = fl.pop(0)
        self.assertEqual(v2, 1)
        self.assertEqual(list(fl), [2, 3, 4, 5])

        fl.remove(4)
        self.assertEqual(list(fl), [2, 3, 5])

        fl.clear()
        self.assertEqual(list(fl), [])

    def test_contains_index_count(self):
        fl = FrozenList([1, 2, 2, 3])
        self.assertIn(2, fl)
        self.assertNotIn(9, fl)
        self.assertEqual(fl.index(2), 1)
        self.assertEqual(fl.count(2), 2)
        with self.assertRaises(ValueError):
            fl.index(9)

    def test_reverse_and_sequence_ops_supported(self):
        fl = FrozenList([1, 2, 3])
        # reverse() is part of MutableSequence and should exist
        fl.reverse()
        self.assertEqual(list(fl), [3, 2, 1])

        # FrozenList does NOT necessarily implement +/* like list; ensure it fails (as observed)
        with self.assertRaises(TypeError):
            _ = fl + [9]  # type: ignore[operator]
        with self.assertRaises(TypeError):
            _ = [9] + fl  # type: ignore[operator]
        with self.assertRaises(TypeError):
            _ = fl * 2  # type: ignore[operator]

    def test_repr_and_equality(self):
        fl = FrozenList([1, "a"])
        r = repr(fl)
        self.assertIsInstance(r, str)
        self.assertIn("FrozenList", r)

        self.assertEqual(fl, [1, "a"])
        self.assertTrue(fl == [1, "a"])
        self.assertFalse(fl == [1, "b"])

        fl2 = FrozenList([1, "a"])
        self.assertEqual(fl, fl2)

    def test_freeze_blocks_mutations(self):
        fl = FrozenList([1, 2, 3])
        fl.freeze()
        self.assertTrue(fl.frozen)

        # Mutations should raise RuntimeError once frozen
        mutators = [
            lambda: fl.append(4),
            lambda: fl.extend([4]),
            lambda: fl.insert(0, 9),
            lambda: fl.__setitem__(0, 99),
            lambda: fl.__setitem__(slice(0, 1), [7, 8]),
            lambda: fl.__delitem__(0),
            lambda: fl.__delitem__(slice(0, 1)),
            lambda: fl.pop(),
            lambda: fl.remove(2),
            lambda: fl.clear(),
            lambda: fl.reverse(),
        ]
        for op in mutators:
            with self.subTest(op=op):
                with self.assertRaises(RuntimeError):
                    op()

        # Non-mutating operations still work
        self.assertEqual(fl[0], 1)
        self.assertEqual(list(fl), [1, 2, 3])
        self.assertIn(2, fl)

    def test_hashing_rules(self):
        fl = FrozenList([1, 2, 3])
        with self.assertRaises(RuntimeError):
            hash(fl)

        fl.freeze()
        h1 = hash(fl)
        h2 = hash(fl)
        self.assertEqual(h1, h2)

        # Often implemented as tuple hash; if not, at least ensure stable & usable as key
        d = {fl: "ok"}
        self.assertEqual(d[fl], "ok")
        s = {fl}
        self.assertIn(fl, s)

    def test_frozen_hash_compatible_with_equal_frozenlists(self):
        a = FrozenList([1, 2, 3])
        b = FrozenList([1, 2, 3])
        a.freeze()
        b.freeze()
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_error_conditions(self):
        fl = FrozenList([1, 2, 3])

        with self.assertRaises(IndexError):
            _ = fl[999]
        with self.assertRaises(IndexError):
            fl.pop(999)
        with self.assertRaises(ValueError):
            fl.remove(999)

        with self.assertRaises(TypeError):
            # slice assignment requires an iterable (not an int)
            fl[0:1] = 123  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main(verbosity=2)
