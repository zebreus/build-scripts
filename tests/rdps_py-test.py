import unittest
# rpds-py exposes these from the 'rpds' package
from rpds import HashTrieMap, HashTrieSet, List

class TestRpdsBasic(unittest.TestCase):

    def test_hashtriemap_insert_remove_and_persistence(self):
        m0 = HashTrieMap({"foo": "bar", "baz": "quux"})
        # Insert returns a new map, original unchanged
        m1 = m0.insert("spam", 37)
        self.assertEqual(
            m1, HashTrieMap({"foo": "bar", "baz": "quux", "spam": 37}),
            "insert should return a new map with the extra key"
        )
        self.assertEqual(
            m0, HashTrieMap({"foo": "bar", "baz": "quux"}),
            "original map should remain unchanged (persistent/immutable)"
        )

        # Remove returns a new map, original unchanged
        m2 = m0.remove("foo")
        self.assertEqual(
            m2, HashTrieMap({"baz": "quux"}),
            "remove should return a new map without the key"
        )
        self.assertEqual(
            m0, HashTrieMap({"foo": "bar", "baz": "quux"}),
            "original map should still have the key after remove on the copy"
        )

        # Chaining operations should behave predictably
        m3 = m0.insert("x", 1).remove("baz").insert("y", 2)
        self.assertEqual(
            m3, HashTrieMap({"foo": "bar", "x": 1, "y": 2}),
            "chained inserts/removes should compose correctly"
        )

    def test_hashtrieset_insert_remove_and_persistence(self):
        s0 = HashTrieSet({"foo", "bar", "baz", "quux"})
        s1 = s0.insert("spam")
        self.assertEqual(
            s1, HashTrieSet({"foo", "bar", "baz", "quux", "spam"}),
            "insert should add an element and return a new set"
        )
        self.assertEqual(
            s0, HashTrieSet({"foo", "bar", "baz", "quux"}),
            "original set should remain unchanged"
        )

        s2 = s0.remove("foo")
        self.assertEqual(
            s2, HashTrieSet({"bar", "baz", "quux"}),
            "remove should return a new set without the element"
        )
        self.assertEqual(
            s0, HashTrieSet({"foo", "bar", "baz", "quux"}),
            "original set should remain unchanged after remove on the copy"
        )

        # Chaining
        s3 = s0.insert("x").remove("bar").insert("y")
        self.assertEqual(
            s3, HashTrieSet({"foo", "baz", "quux", "x", "y"}),
            "chained operations should compose correctly"
        )

    def test_list_push_front_and_rest_persistence(self):
        L0 = List([1, 3, 5])

        # push_front returns a new List, original unchanged
        L1 = L0.push_front(-1)
        self.assertEqual(
            L1, List([-1, 1, 3, 5]),
            "push_front should return a new list with the element prepended"
        )
        self.assertEqual(
            L0, List([1, 3, 5]),
            "original list should remain unchanged after push_front"
        )

        # rest should drop the first element and return a new List
        self.assertEqual(
            L0.rest, List([3, 5]),
            "rest should be the list without the first element"
        )

        # Multiple pushes should compose and preserve persistence
        L2 = L0.push_front(0).push_front(-1)
        self.assertEqual(L2, List([-1, 0, 1, 3, 5]))
        self.assertEqual(L0, List([1, 3, 5]))  # still unchanged

        # rest after multiple pushes should be consistent
        self.assertEqual(L2.rest, List([0, 1, 3, 5]))


if __name__ == "__main__":
    unittest.main()