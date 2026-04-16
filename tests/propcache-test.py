import unittest

try:
    from propcache.api import cached_property, under_cached_property
    _PROPCACHE_AVAILABLE = True
except Exception:  # pragma: no cover
    cached_property = None
    under_cached_property = None
    _PROPCACHE_AVAILABLE = False


@unittest.skipUnless(_PROPCACHE_AVAILABLE, "propcache is not installed; skipping propcache tests.")
class TestCachedProperty(unittest.TestCase):
    def test_caches_in_instance_dict_and_only_calls_once(self):
        class C:
            def __init__(self):
                self.calls = 0

            @cached_property
            def value(self):
                self.calls += 1
                return ("computed", self.calls)

        c = C()
        self.assertNotIn("value", c.__dict__)
        v1 = c.value
        self.assertIn("value", c.__dict__)
        v2 = c.value

        self.assertEqual(v1, v2)
        self.assertEqual(c.calls, 1)
        self.assertEqual(c.__dict__["value"], v1)

    def test_manual_override_does_not_call_function(self):
        class C:
            def __init__(self):
                self.calls = 0

            @cached_property
            def value(self):
                self.calls += 1
                return self.calls

        c = C()
        c.__dict__["value"] = 999
        self.assertEqual(c.value, 999)
        self.assertEqual(c.calls, 0)

    def test_delete_clears_cache_and_recomputes(self):
        class C:
            def __init__(self):
                self.calls = 0

            @cached_property
            def value(self):
                self.calls += 1
                return self.calls

        c = C()
        self.assertEqual(c.value, 1)
        self.assertEqual(c.value, 1)
        self.assertEqual(c.calls, 1)

        del c.value
        self.assertNotIn("value", c.__dict__)
        self.assertEqual(c.value, 2)
        self.assertEqual(c.calls, 2)

    def test_pop_from_dict_clears_cache_and_recomputes(self):
        class C:
            def __init__(self):
                self.calls = 0

            @cached_property
            def value(self):
                self.calls += 1
                return self.calls

        c = C()
        self.assertEqual(c.value, 1)
        c.__dict__.pop("value", None)
        self.assertEqual(c.value, 2)

    def test_cached_property_on_class_returns_descriptor(self):
        class C:
            @cached_property
            def value(self):
                return 123

        attr = C.__dict__["value"]
        self.assertIs(attr, C.value)

    def test_inheritance_works(self):
        class Base:
            def __init__(self):
                self.calls = 0

            @cached_property
            def value(self):
                self.calls += 1
                return self.calls

        class Child(Base):
            pass

        c = Child()
        self.assertEqual(c.value, 1)
        self.assertEqual(c.value, 1)
        self.assertEqual(c.calls, 1)

    def test_no_instance_dict_raises_helpful_error(self):
        class NoDict:
            __slots__ = ()

            @cached_property
            def value(self):
                return 1

        obj = NoDict()
        with self.assertRaises((TypeError, AttributeError)):
            _ = obj.value


@unittest.skipUnless(_PROPCACHE_AVAILABLE, "propcache is not installed; skipping propcache tests.")
class TestUnderCachedProperty(unittest.TestCase):
    def test_caches_in_private_cache_dict_not_in_instance_dict(self):
        class C:
            def __init__(self):
                self.calls = 0
                self._cache = {}

            @under_cached_property
            def value(self):
                self.calls += 1
                return ("computed", self.calls)

        c = C()
        self.assertNotIn("value", c.__dict__)
        self.assertEqual(c._cache, {})

        v1 = c.value
        v2 = c.value

        self.assertEqual(v1, v2)
        self.assertEqual(c.calls, 1)
        self.assertIn("value", c._cache)
        self.assertEqual(c._cache["value"], v1)
        self.assertNotIn("value", c.__dict__)

    def test_clearing_cache_recomputes(self):
        class C:
            def __init__(self):
                self.calls = 0
                self._cache = {}

            @under_cached_property
            def value(self):
                self.calls += 1
                return self.calls

            def clear_cache(self):
                self._cache.clear()

        c = C()
        self.assertEqual(c.value, 1)
        self.assertEqual(c.value, 1)
        self.assertEqual(c.calls, 1)

        c.clear_cache()
        self.assertEqual(c.value, 2)
        self.assertEqual(c.calls, 2)

    def test_manual_override_in_cache_short_circuits_computation(self):
        class C:
            def __init__(self):
                self.calls = 0
                self._cache = {}

            @under_cached_property
            def value(self):
                self.calls += 1
                return self.calls

        c = C()
        c._cache["value"] = 777
        self.assertEqual(c.value, 777)
        self.assertEqual(c.calls, 0)

    def test_missing_cache_attribute_raises_helpful_error(self):
        class C:
            def __init__(self):
                self.calls = 0

            @under_cached_property
            def value(self):
                self.calls += 1
                return self.calls

        c = C()
        with self.assertRaises((AttributeError, TypeError, KeyError)):
            _ = c.value

    def test_cache_attribute_wrong_type_raises_helpful_error(self):
        class C:
            def __init__(self):
                self.calls = 0
                self._cache = None  # wrong type; C-extension may throw SystemError

            @under_cached_property
            def value(self):
                self.calls += 1
                return self.calls

        c = C()
        with self.assertRaises((AttributeError, TypeError, SystemError)):
            _ = c.value

    def test_delattr_raises_notimplementederror(self):
        class C:
            def __init__(self):
                self._cache = {}
                self.calls = 0

            @under_cached_property
            def value(self):
                self.calls += 1
                return self.calls

        c = C()
        _ = c.value

        with self.assertRaises((NotImplementedError, AttributeError)):
            del c.value

        c._cache.pop("value", None)
        self.assertEqual(c.value, 2)

    def test_inheritance_works(self):
        class Base:
            def __init__(self):
                self._cache = {}
                self.calls = 0

            @under_cached_property
            def value(self):
                self.calls += 1
                return self.calls

        class Child(Base):
            pass

        c = Child()
        self.assertEqual(c.value, 1)
        self.assertEqual(c.value, 1)
        self.assertEqual(c.calls, 1)
        self.assertIn("value", c._cache)


if __name__ == "__main__":
    unittest.main(verbosity=2)
