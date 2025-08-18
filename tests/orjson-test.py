# test_orjson_basic.py
import unittest
import datetime as dt
import enum
import json
import uuid
import sys

import orjson

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

try:
    from zoneinfo import ZoneInfo
    HAS_ZONEINFO = True
except Exception:
    HAS_ZONEINFO = False


# -----------------------------
# Helpers
# -----------------------------
def json_roundtrip_bytes(obj, **kw):
    """Serialize with orjson.dumps and parse back with orjson.loads for structural equality."""
    return orjson.loads(orjson.dumps(obj, **kw))

def is_bytes(x):
    return isinstance(x, (bytes, bytearray, memoryview))


# -----------------------------
# Basic dumps/loads
# -----------------------------
class TestBasicRoundtrip(unittest.TestCase):
    def test_dumps_returns_bytes(self):
        out = orjson.dumps({"a": 1})
        self.assertTrue(is_bytes(out))

    def test_simple_types_roundtrip(self):
        data = {
            "str": "hello",
            "int": 42,
            "float": 3.5,
            "bool_t": True,
            "bool_f": False,
            "none": None,
            "list": [1, 2, 3],
            "tuple": (4, 5),
            "dict": {"x": 1},
        }
        self.assertEqual(json_roundtrip_bytes(data), {
            "str": "hello",
            "int": 42,
            "float": 3.5,
            "bool_t": True,
            "bool_f": False,
            "none": None,
            "list": [1, 2, 3],
            "tuple": [4, 5],  # tuples become arrays
            "dict": {"x": 1},
        })

    def test_loads_accepts_bytes_and_str(self):
        for payload in (b'{"a":1}', '{"a":1}'):
            self.assertEqual(orjson.loads(payload), {"a": 1})

    def test_invalid_json_raises(self):
        with self.assertRaises(orjson.JSONDecodeError):
            orjson.loads("{bad")


# -----------------------------
# Options: formatting and sort
# -----------------------------
class TestFormattingOptions(unittest.TestCase):
    def test_indent_2(self):
        b = orjson.dumps({"a": 1, "b": [1, 2]}, option=orjson.OPT_INDENT_2)
        self.assertTrue(b.startswith(b"{\n"))
        self.assertIn(b'\n  "a": 1', b)

    def test_sort_keys(self):
        b = orjson.dumps({"b": 1, "a": 2}, option=orjson.OPT_SORT_KEYS)
        self.assertEqual(b, b'{"a":2,"b":1}')

    def test_append_newline(self):
        b = orjson.dumps({"a": 1}, option=orjson.OPT_APPEND_NEWLINE)
        self.assertTrue(b.endswith(b"\n"))


# -----------------------------
# Options: integers and floats
# -----------------------------
class TestNumericBehavior(unittest.TestCase):
    def test_strict_integer_53_bit(self):
        # 2**53 == 9007199254740992
        big = 9007199254740992
        with self.assertRaises(orjson.JSONEncodeError):
            orjson.dumps(big, option=orjson.OPT_STRICT_INTEGER)
        with self.assertRaises(orjson.JSONEncodeError):
            orjson.dumps(-big, option=orjson.OPT_STRICT_INTEGER)
        # Without strict, allowed up to 64-bit
        self.assertEqual(orjson.dumps(big), b"9007199254740992")

    def test_nan_inf_serialized_as_null(self):
        b = orjson.dumps([float("nan"), float("inf"), float("-inf")])
        self.assertEqual(b, b"[null,null,null]")


# -----------------------------
# Strings and UTF-8 strictness
# -----------------------------
class TestUtf8Strictness(unittest.TestCase):
    def test_dumps_rejects_invalid_utf8_surrogate(self):
        # Lone surrogate is invalid in UTF-8
        s = "\ud800"
        with self.assertRaises(orjson.JSONEncodeError):
            orjson.dumps(s)

    def test_loads_rejects_invalid_utf8_bytes(self):
        # b'"\xed\xa0\x80"' is "\ud800" encoded as UTF-8, which is invalid
        with self.assertRaises(orjson.JSONDecodeError):
            orjson.loads(b'"\xed\xa0\x80"')


# -----------------------------
# Datetime / Date / Time
# -----------------------------
class TestDatetime(unittest.TestCase):
    def test_naive_datetime_default(self):
        d = dt.datetime(1970, 1, 1, 0, 0, 0)
        self.assertEqual(orjson.dumps(d), b'"1970-01-01T00:00:00"')

    def test_opt_naive_utc_adds_offset(self):
        d = dt.datetime(1970, 1, 1, 0, 0, 0)
        b = orjson.dumps(d, option=orjson.OPT_NAIVE_UTC)
        self.assertEqual(b, b'"1970-01-01T00:00:00+00:00"')

    @unittest.skipUnless(HAS_ZONEINFO, "zoneinfo not available")
    def test_utc_z(self):
        d = dt.datetime(1970, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
        b = orjson.dumps(d, option=orjson.OPT_UTC_Z)
        self.assertEqual(b, b'"1970-01-01T00:00:00Z"')

    def test_time_and_date(self):
        t = dt.time(12, 0, 15, 290)
        d = dt.date(1900, 1, 2)
        self.assertEqual(orjson.dumps(t), b'"12:00:15.000290"')
        self.assertEqual(orjson.dumps(d), b'"1900-01-02"')

    def test_omit_microseconds(self):
        d = dt.datetime(1970, 1, 1, 0, 0, 0, 1)
        b = orjson.dumps(d, option=orjson.OPT_OMIT_MICROSECONDS)
        self.assertEqual(b, b'"1970-01-01T00:00:00"')

    def test_passthrough_datetime_custom_format(self):
        def default(obj):
            if isinstance(obj, dt.datetime):
                return obj.strftime("%a, %d %b %Y %H:%M:%S GMT")
            raise TypeError

        d = {"created_at": dt.datetime(1970, 1, 1)}
        with self.assertRaises(orjson.JSONEncodeError):
            orjson.dumps(d, option=orjson.OPT_PASSTHROUGH_DATETIME)
        b = orjson.dumps(d, option=orjson.OPT_PASSTHROUGH_DATETIME, default=default)
        self.assertEqual(b, b'{"created_at":"Thu, 01 Jan 1970 00:00:00 GMT"}')


# -----------------------------
# Dataclass
# -----------------------------
class TestDataclass(unittest.TestCase):
    def test_dataclass_native_and_passthrough(self):
        import dataclasses

        @dataclasses.dataclass
        class User:
            id: str
            name: str
            password: str

        # Native serialization includes all fields
        native = orjson.dumps(User("3b1", "alice", "secret"))
        self.assertEqual(
            orjson.loads(native),
            {"id": "3b1", "name": "alice", "password": "secret"},
        )

        # Passthrough to default for customization
        def default(obj):
            if isinstance(obj, User):
                return {"id": obj.id, "name": obj.name}
            raise TypeError

        with self.assertRaises(orjson.JSONEncodeError):
            orjson.dumps(User("3b1", "alice", "secret"), option=orjson.OPT_PASSTHROUGH_DATACLASS)

        customized = orjson.dumps(
            User("3b1", "alice", "secret"),
            option=orjson.OPT_PASSTHROUGH_DATACLASS,
            default=default,
        )
        self.assertEqual(orjson.loads(customized), {"id": "3b1", "name": "alice"})


# -----------------------------
# Enum
# -----------------------------
class TestEnum(unittest.TestCase):
    def test_enum_native(self):
        class Color(enum.Enum):
            RED = 1
            GREEN = 2

        self.assertEqual(orjson.dumps(Color.RED), b"1")

    def test_enum_with_custom_default(self):
        class Wrapper:
            def __init__(self, v): self.v = v

        class WrappedEnum(enum.Enum):
            ONE = Wrapper(1)

        def default(obj):
            if isinstance(obj, Wrapper): return obj.v
            raise TypeError

        self.assertEqual(orjson.dumps(WrappedEnum.ONE, default=default), b"1")


# -----------------------------
# UUID
# -----------------------------
class TestUUID(unittest.TestCase):
    def test_uuid_native(self):
        u = uuid.uuid5(uuid.NAMESPACE_DNS, "python.org")
        self.assertEqual(orjson.dumps(u), b'"886313e1-3b8a-5372-9b90-0c9aee199e5d"')


# -----------------------------
# numpy (optional)
# -----------------------------
@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class TestNumpy(unittest.TestCase):
    def test_numpy_array(self):
        arr = np.array([[1, 2, 3], [4, 5, 6]])
        b = orjson.dumps(arr, option=orjson.OPT_SERIALIZE_NUMPY)
        self.assertEqual(b, b"[[1,2,3],[4,5,6]]")

    def test_numpy_scalars(self):
        for val in [np.int32(5), np.float32(1.5), np.bool_(True)]:
            b = orjson.dumps(val, option=orjson.OPT_SERIALIZE_NUMPY)
            # Compare via roundtrip for floats
            self.assertEqual(orjson.loads(b), json.loads(b.decode()))

    def test_numpy_datetime64(self):
        t = np.datetime64("2021-01-01T00:00:00.172")
        b = orjson.dumps(t, option=orjson.OPT_SERIALIZE_NUMPY)
        # RFC3339 with microseconds expanded
        self.assertEqual(b, b'"2021-01-01T00:00:00.172000"')


# -----------------------------
# dict key handling
# -----------------------------
class TestNonStrKeys(unittest.TestCase):
    def test_non_str_keys_requires_option(self):
        data = {1: "a", "1": "b"}
        with self.assertRaises(orjson.JSONEncodeError):
            orjson.dumps(data)
        b = orjson.dumps(data, option=orjson.OPT_NON_STR_KEYS)
        # last-in wins on duplicate keys; but ordering of dict insertion is deterministic in Python
        self.assertEqual(orjson.loads(b), {"1": "b"})  # both keys become "1"

    def test_non_str_keys_types(self):
        d = {
            1: [1, 2, 3],
            True: "t",
            None: "n",
            dt.date(1970, 1, 1): 5,
            uuid.UUID(int=0): 6,
        }
        b = orjson.dumps(d, option=orjson.OPT_NON_STR_KEYS)
        self.assertIsInstance(b, bytes)
        # Ensure it's valid JSON
        orjson.loads(b)


# -----------------------------
# default= handler
# -----------------------------
class TestDefaultCallable(unittest.TestCase):
    def test_default_converts_unknown_type(self):
        class Money:
            def __init__(self, cents): self.cents = cents

        def default(obj):
            if isinstance(obj, Money):
                return {"cents": obj.cents}
            raise TypeError

        m = Money(199)
        out = orjson.dumps({"price": m}, default=default)
        self.assertEqual(orjson.loads(out), {"price": {"cents": 199}})

    def test_default_must_raise(self):
        class Unknown: pass

        def default(obj):
            # BUGGY default that forgets to raise for unknowns
            if hasattr(obj, "x"):
                return obj.x
            # implicit None -> serialized as null
        b = orjson.dumps({"u": Unknown()}, default=default)
        self.assertEqual(b, b'{"u":null}')


# -----------------------------
# Subclass passthrough
# -----------------------------
class TestSubclassPassthrough(unittest.TestCase):
    class Secret(str): pass

    def test_passthrough_subclass(self):
        def default(obj):
            if isinstance(obj, TestSubclassPassthrough.Secret):
                return "******"
            raise TypeError

        # Without passthrough, serialized as a normal string
        self.assertEqual(orjson.dumps(TestSubclassPassthrough.Secret("pw")), b'"pw"')
        # With passthrough + default
        with self.assertRaises(orjson.JSONEncodeError):
            orjson.dumps(TestSubclassPassthrough.Secret("pw"), option=orjson.OPT_PASSTHROUGH_SUBCLASS)
        masked = orjson.dumps(
            TestSubclassPassthrough.Secret("pw"),
            option=orjson.OPT_PASSTHROUGH_SUBCLASS,
            default=default,
        )
        self.assertEqual(masked, b'"******"')


# -----------------------------
# Fragment
# -----------------------------
class TestFragment(unittest.TestCase):
    def test_fragment_injection(self):
        frag = orjson.Fragment(b'{"a": "b", "c": 1}')
        out = orjson.dumps({"key": "zxc", "data": frag})
        self.assertEqual(orjson.loads(out), {"key": "zxc", "data": {"a": "b", "c": 1}})


# -----------------------------
# Error scenarios
# -----------------------------
class TestErrorCases(unittest.TestCase):
    def test_unsupported_type_raises(self):
        with self.assertRaises(orjson.JSONEncodeError):
            orjson.dumps(set([1, 2]))

    def test_circular_reference_raises(self):
        a = []
        a.append(a)
        with self.assertRaises(orjson.JSONEncodeError):
            orjson.dumps(a)

    def test_loads_rejects_json_with_nan_literals(self):
        # Standard json() accepts NaN; orjson.loads must reject as invalid JSON
        payload = '[NaN, Infinity, -Infinity]'
        with self.assertRaises(orjson.JSONDecodeError):
            orjson.loads(payload)


if __name__ == "__main__":
    unittest.main()