# test_annotated_types_basic.py
import math
import unittest
from dataclasses import dataclass
from datetime import datetime, time, timezone as dt_timezone
from decimal import Decimal
from typing import Annotated, Any, get_args, get_origin

try:
    # Python 3.9+ has zoneinfo in stdlib
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - optional on some platforms
    ZoneInfo = None  # type: ignore[assignment]

import annotated_types as atypes
from annotated_types import (
    Gt,
    Ge,
    Lt,
    Le,
    Interval,
    MultipleOf,
    MinLen,
    MaxLen,
    Len,
    Predicate,
    Not,
    Timezone,
    Unit,
    GroupedMetadata,
    doc,
)

# Optional predicate aliases: present in many versions but import-guarded for portability
ALIASES = {
    "IsLower": getattr(atypes, "IsLower", None),
    "IsUpper": getattr(atypes, "IsUpper", None),
    "IsDigit": getattr(atypes, "IsDigit", None),
    "IsFinite": getattr(atypes, "IsFinite", None),
    "IsNotFinite": getattr(atypes, "IsNotFinite", None),
    "IsNan": getattr(atypes, "IsNan", None),
    "IsNotNan": getattr(atypes, "IsNotNan", None),
    "IsInfinite": getattr(atypes, "IsInfinite", None),
    "IsNotInfinite": getattr(atypes, "IsNotInfinite", None),
}


def flatten_metadata(annotation):
    """
    Given an Annotated[...] type, return a flat list of metadata objects.

    - Expands GroupedMetadata (e.g., Interval, Len) by iterating over them.
    - Leaves unknown metadata untouched.
    """
    assert get_origin(annotation) is Annotated, "Expected an Annotated[...] type"
    base, *metadata = get_args(annotation)
    flat = []
    for m in metadata:
        if isinstance(m, GroupedMetadata):
            flat.extend(list(m))
        else:
            flat.append(m)
    return base, flat


def _jsonschema_multiple_of(value, m):
    """
    JSON Schema-style multipleOf using exact Decimal arithmetic.
    Treats value as a multiple if (value / m) is an integer (no fractional part).
    """
    try:
        q = Decimal(str(value)) / Decimal(str(m))
        return q == q.to_integral_value()
    except Exception:
        return False


def validate_value(value, annotation, *, multiple_of_semantics="python"):
    """
    A tiny consumer that enforces a subset of constraints described in the docs.
    This is ONLY for exercising the metadata objects (annotated-types
    doesn't enforce at runtime by itself).

    multiple_of_semantics: "python" -> (value % m == 0)
                           "json"   -> Decimal division integral check
    """
    _, meta = flatten_metadata(annotation)

    min_len = None
    max_len = None

    for m in meta:
        # Orderable bounds
        if isinstance(m, Gt):
            if not (value > m.gt):
                return False
        elif isinstance(m, Ge):
            if not (value >= m.ge):
                return False
        elif isinstance(m, Lt):
            if not (value < m.lt):
                return False
        elif isinstance(m, Le):
            if not (value <= m.le):
                return False

        # Length constraints (after Len(...) expansion, these are MinLen/MaxLen)
        elif isinstance(m, MinLen):
            min_len = m.min_length if min_len is None else max(min_len, m.min_length)
        elif isinstance(m, MaxLen):
            max_len = m.max_length if max_len is None else min(max_len, m.max_length)

        # MultipleOf
        elif isinstance(m, MultipleOf):
            mo = m.multiple_of
            if multiple_of_semantics == "python":
                try:
                    if value % mo != 0:  # may be float-imprecise by design
                        return False
                except Exception:
                    return False
            elif multiple_of_semantics == "json":
                if not _jsonschema_multiple_of(value, mo):
                    return False
            else:
                raise ValueError("multiple_of_semantics must be 'python' or 'json'")

        # Predicate (call whatever is wrapped)
        elif isinstance(m, Predicate):
            func = getattr(m, "func", None)
            if callable(func):
                try:
                    if not func(value):
                        return False
                except Exception:
                    return False
            else:
                if not callable(m) or not m(value):
                    return False

        # Timezone/Unit/Doc/unknown metadata: this consumer doesn't act on them
        elif isinstance(m, (Timezone, Unit)):
            pass
        else:
            # Unknown metadata -> ignore (per docs: consumers may ignore)
            pass

    # If we saw any length constraints, check them here.
    if min_len is not None or max_len is not None:
        try:
            L = len(value)
        except Exception:
            return False
        if min_len is not None and L < min_len:
            return False
        if max_len is not None and L > max_len:
            return False

    return True


def validate_container(value, annotation, *, multiple_of_semantics="python") -> bool:
    """
    Minimal container-aware validator:
    - If annotation is list[Annotated[T, ...]], validate each element against that inner Annotated.
    - Otherwise fall back to validate_value on the top-level annotation (if Annotated),
      or succeed if there's nothing to validate.
    """
    origin = get_origin(annotation)
    if origin in (list,):
        (elem_ann,) = get_args(annotation)
        if get_origin(elem_ann) is Annotated:
            # Validate each element using inner Annotated metadata
            return all(
                validate_value(elem, elem_ann, multiple_of_semantics=multiple_of_semantics)
                for elem in value
            )
        # No inner metadata -> nothing to enforce here
        return True

    # If top-level is Annotated, just validate the value itself
    if get_origin(annotation) is Annotated:
        return validate_value(value, annotation, multiple_of_semantics=multiple_of_semantics)
    return True


class TestAnnotatedTypesBasics(unittest.TestCase):
    def test_annotated_extraction(self):
        A = Annotated[int, Gt(1), Lt(10)]
        self.assertIs(get_origin(A), Annotated)
        base, meta = flatten_metadata(A)
        self.assertIs(base, int)
        self.assertEqual({type(m) for m in meta}, {Gt, Lt})

    def test_bounds_integers(self):
        A = Annotated[int, Gt(1), Le(5)]
        self.assertTrue(validate_value(2, A))
        self.assertTrue(validate_value(5, A))
        self.assertFalse(validate_value(1, A))
        self.assertFalse(validate_value(6, A))

    def test_bounds_mixed_types(self):
        # Docs say boundary and value can be comparable but different types
        A = Annotated[int, Gt(1.5)]
        self.assertTrue(validate_value(2, A))
        self.assertFalse(validate_value(1, A))

    def test_interval_unpacks_to_bounds(self):
        A = Annotated[int, Interval(ge=0, lt=10)]
        base, meta = flatten_metadata(A)
        self.assertIs(base, int)
        # Should expand to Ge + Lt
        kinds = {type(m) for m in meta}
        self.assertEqual(kinds, {Ge, Lt})

        self.assertTrue(validate_value(0, A))
        self.assertTrue(validate_value(9, A))
        self.assertFalse(validate_value(-1, A))
        self.assertFalse(validate_value(10, A))

    def test_len_min_max_and_exact(self):
        A = Annotated[list[int], Len(2, 4)]
        self.assertTrue(validate_value([1, 2], A))
        self.assertTrue(validate_value([1, 2, 3, 4], A))
        self.assertFalse(validate_value([1], A))
        self.assertFalse(validate_value([1, 2, 3, 4, 5], A))

        B = Annotated[str, MinLen(3)]
        self.assertTrue(validate_value("hey", B))
        self.assertFalse(validate_value("no", B))

        C = Annotated[bytes, MaxLen(2)]
        self.assertTrue(validate_value(b"ok", C))
        self.assertFalse(validate_value(b"nope", C))

        D = Annotated[list, Len(8, 8)]  # exactly 8
        self.assertTrue(validate_value(list(range(8)), D))
        self.assertFalse(validate_value(list(range(7)), D))
        self.assertFalse(validate_value(list(range(9)), D))

    def test_len_is_groupedmetadata(self):
        A = Len(3, 5)
        self.assertIsInstance(A, GroupedMetadata)
        parts = list(A)
        self.assertEqual({type(p) for p in parts}, {MinLen, MaxLen})
        self.assertEqual(parts[0].min_length if isinstance(parts[0], MinLen) else parts[1].min_length, 3)
        self.assertEqual(parts[0].max_length if isinstance(parts[0], MaxLen) else parts[1].max_length, 5)

    def test_multiple_of_python_semantics(self):
        A = Annotated[int, MultipleOf(2)]
        self.assertTrue(validate_value(10, A, multiple_of_semantics="python"))
        self.assertFalse(validate_value(7, A, multiple_of_semantics="python"))

        # Floating-point imprecision example: 0.3 % 0.1 != 0 under Python modulo
        B = Annotated[float, MultipleOf(0.1)]
        self.assertFalse(validate_value(0.3, B, multiple_of_semantics="python"))

    def test_multiple_of_jsonschema_semantics(self):
        A = Annotated[float, MultipleOf(0.1)]
        # Using Decimal semantics, 0.3 is a multiple of 0.1
        self.assertTrue(validate_value(0.3, A, multiple_of_semantics="json"))
        self.assertFalse(validate_value(0.35, A, multiple_of_semantics="json"))

    def test_multiple_of_with_decimal_type(self):
        A = Annotated[Decimal, MultipleOf(Decimal("0.1"))]
        self.assertTrue(validate_value(Decimal("0.3"), A, multiple_of_semantics="json"))
        self.assertFalse(validate_value(Decimal("0.35"), A, multiple_of_semantics="json"))

    def test_predicate_and_not(self):
        Lower = Annotated[str, Predicate(str.islower)]
        self.assertTrue(validate_value("hello", Lower))
        self.assertFalse(validate_value("Hello", Lower))

        # Use Not to negate a common predicate, then wrap with Predicate(...)
        NotNaN = Annotated[float, Predicate(Not(math.isnan))]
        self.assertTrue(validate_value(1.0, NotNaN))
        self.assertFalse(validate_value(float("nan"), NotNaN))

        # Ensure Not is callable and negates correctly
        self.assertTrue(callable(Not(math.isfinite)))
        self.assertTrue(Not(math.isfinite)(float("inf")))  # not finite -> True
        self.assertFalse(Not(math.isfinite)(1.23))         # finite -> False

    def test_timezone_construction_and_annotated_use(self):
        # Naive only
        A = Annotated[datetime, Timezone(None)]
        base, meta = flatten_metadata(A)
        self.assertIs(base, datetime)
        self.assertTrue(any(isinstance(m, Timezone) for m in meta))

        # Any timezone-aware: prefer subscript form if available; otherwise Ellipsis arg
        try:
            tz_any = Timezone[...]  # literal ellipsis (newer versions)
        except TypeError:
            tz_any = Timezone(Ellipsis)  # fallback for versions without __class_getitem__
        B = Annotated[datetime, tz_any]
        base, meta = flatten_metadata(B)
        self.assertIs(base, datetime)
        self.assertTrue(any(isinstance(m, Timezone) for m in meta))

        # Specific tzinfo
        C = Annotated[time, Timezone(dt_timezone.utc)]
        self.assertTrue(any(isinstance(m, Timezone) for m in flatten_metadata(C)[1]))

        # Specific IANA name if zoneinfo is available
        if ZoneInfo is not None:
            D = Annotated[datetime, Timezone("Africa/Abidjan")]
            self.assertTrue(any(isinstance(m, Timezone) for m in flatten_metadata(D)[1]))

    def test_unit_metadata(self):
        Speed = Annotated[float, Unit("m/s")]
        base, meta = flatten_metadata(Speed)
        self.assertIs(base, float)
        units = [m for m in meta if isinstance(m, Unit)]
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].unit, "m/s")

    def test_doc_metadata(self):
        info = doc("age of the user in years")
        # doc() returns a DocInfo-like object with a .documentation attribute
        self.assertTrue(hasattr(info, "documentation"))
        self.assertEqual(info.documentation, "age of the user in years")

        A = Annotated[int, info]
        base, meta = flatten_metadata(A)
        self.assertIs(base, int)
        self.assertIn(info, meta)  # exact object present

    def test_groupedmetadata_iter_contract(self):
        # Interval should expand to appropriate bound objects and ignore None
        I = Interval(gt=1, ge=None, lt=None, le=10)
        self.assertIsInstance(I, GroupedMetadata)
        parts = list(I)
        kinds = {type(p) for p in parts}
        self.assertEqual(kinds, {Gt, Le})
        # Sanity check with validator post-expansion
        A = Annotated[int, I]
        self.assertTrue(validate_value(5, A))
        self.assertFalse(validate_value(1, A))
        self.assertTrue(validate_value(10, A))
        self.assertFalse(validate_value(11, A))

    def test_combined_constraints(self):
        # A list of lowercase digit strings, length 2..3, and elements multiple-of-2 when cast to int
        # (just to exercise multiple metadata items together)
        A = Annotated[list[str], Len(2, 3)]
        elems_ok = all(str.isdigit(s) and int(s) % 2 == 0 for s in ["2", "4"])
        self.assertTrue(elems_ok)
        self.assertTrue(validate_value(["2", "4"], A))
        self.assertFalse(validate_value(["2"], A))         # too short
        self.assertFalse(validate_value(["2", "4", "6", "8"], A))  # too long

    # -----------------------
    # New coverage starts here
    # -----------------------

    def test_invalid_combinations_are_safe(self):
        # Len with int (no __len__) -> our consumer should return False, not crash
        A = Annotated[int, Len(3)]
        self.assertFalse(validate_value(5, A))

        # MultipleOf with non-numeric -> consumer returns False, not crash
        B = Annotated[int, MultipleOf("not-a-number")]  # type: ignore[arg-type]
        self.assertFalse(validate_value(10, B))

        # Predicate that raises (e.g., str.isdigit called on int) should be caught and return False
        C = Annotated[int, Predicate(str.isdigit)]
        self.assertFalse(validate_value(123, C))

    def test_custom_groupedmetadata_subclass(self):
        # An example custom GroupedMetadata that yields a Ge constraint and an unknown object
        class Description:
            def __init__(self, text: str) -> None:
                self.text = text

        @dataclass
        class Field(GroupedMetadata):
            ge: int | None = None
            description: str | None = None

            def __iter__(self):
                if self.ge is not None:
                    yield Ge(self.ge)
                if self.description is not None:
                    yield Description(self.description)  # unknown to our consumer -> ignored

        A = Annotated[int, Field(ge=3, description="must be >= 3")]
        base, meta = flatten_metadata(A)
        self.assertIs(base, int)
        # Ensure Ge is present and Description is present but ignored by validator
        self.assertTrue(any(isinstance(m, Ge) for m in meta))
        self.assertTrue(validate_value(3, A))
        self.assertFalse(validate_value(2, A))

    def test_nested_annotated_in_list_elements(self):
        Elem = Annotated[str, Predicate(str.isdigit)]
        L = list[Elem]
        # Validate container: each element must pass Elem's predicate
        self.assertTrue(validate_container(["1", "23", "456"], L))
        self.assertFalse(validate_container(["1", "abc"], L))

        # Also sanity-check the structure
        self.assertIs(get_origin(L), list)
        (inner,) = get_args(L)
        self.assertIs(get_origin(inner), Annotated)
        base, meta = flatten_metadata(inner)
        self.assertIs(base, str)
        self.assertTrue(any(isinstance(m, Predicate) for m in meta))

    # Aliases: guarded so we don't break on versions that don't export them
    def test_predicate_aliases_lower_upper_digit(self):
        if ALIASES["IsLower"] is None or ALIASES["IsUpper"] is None or ALIASES["IsDigit"] is None:
            self.skipTest("Predicate aliases IsLower/IsUpper/IsDigit not available in this version")

        LowerT = ALIASES["IsLower"][str]  # type: ignore[index]
        UpperT = ALIASES["IsUpper"][str]  # type: ignore[index]
        DigitT = ALIASES["IsDigit"][str]  # type: ignore[index]

        self.assertTrue(validate_value("hello", LowerT))
        self.assertFalse(validate_value("Hello", LowerT))

        self.assertTrue(validate_value("ABC", UpperT))
        self.assertFalse(validate_value("AbC", UpperT))

        self.assertTrue(validate_value("12345", DigitT))
        self.assertFalse(validate_value("12a45", DigitT))

    def test_predicate_aliases_numbers(self):
        needed = ("IsFinite", "IsNotFinite", "IsNan", "IsNotNan", "IsInfinite", "IsNotInfinite")
        if not all(ALIASES[name] is not None for name in needed):
            self.skipTest("Some numeric predicate aliases are not available in this version")

        IsFinite = ALIASES["IsFinite"][float]        # type: ignore[index]
        IsNotFinite = ALIASES["IsNotFinite"][float]  # type: ignore[index]
        IsNan = ALIASES["IsNan"][float]              # type: ignore[index]
        IsNotNan = ALIASES["IsNotNan"][float]        # type: ignore[index]
        IsInfinite = ALIASES["IsInfinite"][float]    # type: ignore[index]
        IsNotInfinite = ALIASES["IsNotInfinite"][float]  # type: ignore[index]

        self.assertTrue(validate_value(1.0, IsFinite))
        self.assertFalse(validate_value(float("inf"), IsFinite))

        self.assertTrue(validate_value(float("inf"), IsNotFinite))
        self.assertFalse(validate_value(1.0, IsNotFinite))

        self.assertTrue(validate_value(float("nan"), IsNan))
        self.assertFalse(validate_value(1.0, IsNan))

        self.assertTrue(validate_value(1.0, IsNotNan))
        self.assertFalse(validate_value(float("nan"), IsNotNan))

        self.assertTrue(validate_value(float("inf"), IsInfinite))
        self.assertFalse(validate_value(1.0, IsInfinite))

        self.assertTrue(validate_value(1.0, IsNotInfinite))
        self.assertFalse(validate_value(float("inf"), IsNotInfinite))


if __name__ == "__main__":
    unittest.main()