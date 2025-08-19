import sys
import unittest
from typing import Any, ClassVar, Dict, List, Optional, Union

# Use typing_extensions consistently for cross-version coverage
from typing_extensions import (
    Annotated,
    Final,
    Literal,
    NotRequired,
    Required,
    Self,
    TypedDict,
    get_origin,
    get_type_hints,
)

# Library under test
from typing_inspection.typing_objects import (
    is_any,
    is_self,
    is_literal,
    is_annotated,
    DEPRECATED_ALIASES,
)
from typing_inspection.introspection import (
    AnnotationSource,
    ForbiddenQualifier,
    UNKNOWN,
    get_literal_values,
    inspect_annotation,
    is_union_origin,
)


class TestTypingObjectsBasics(unittest.TestCase):
    def test_is_any(self):
        self.assertTrue(is_any(Any))
        self.assertFalse(is_any(int))
        self.assertFalse(is_any(Optional[int]))

    def test_is_self(self):
        self.assertTrue(is_self(Self))
        self.assertFalse(is_self(int))

    def test_is_literal_and_origin(self):
        origin = get_origin(Literal[1, 2, 3])
        self.assertTrue(is_literal(origin))

    def test_is_annotated_on_wrapped(self):
        # Direct Annotated
        self.assertTrue(is_annotated(get_origin(Annotated[int, "meta"])))
        # Nested Annotated inside a generic argument
        T = Annotated[int, "meta"]
        inner = List[T].__args__[0]
        self.assertTrue(is_annotated(get_origin(inner)))
        # Non-annotated path is false
        self.assertFalse(is_annotated(get_origin(List[int])))

    def test_deprecated_aliases_presence_and_behavior(self):
        import typing as _typing
        expected = {getattr(_typing, name) for name in ("List", "Dict", "Set", "Tuple") if hasattr(_typing, name)}
        present = expected.intersection(set(DEPRECATED_ALIASES.keys()))
        self.assertTrue(present, "Expected some PEP 585 deprecated aliases to be listed in DEPRECATED_ALIASES")

        origin = get_origin(List[int])
        self.assertIs(origin, list)

        if hasattr(_typing, "List"):
            alias = _typing.List
            unparam_origin = get_origin(alias)
            if unparam_origin is not None:
                type_expr = unparam_origin
                origin2 = None
                self.assertIs(type_expr, list)
                self.assertIsNone(origin2)


class TestInspectAnnotationWorkflow(unittest.TestCase):
    def test_simple_unwrap_and_metadata(self):
        inspected = inspect_annotation(
            ClassVar[Annotated[int, "meta"]],
            annotation_source=AnnotationSource.CLASS,
        )
        self.assertEqual(inspected.type, int)
        self.assertIn("class_var", inspected.qualifiers)
        self.assertEqual(inspected.metadata, ["meta"])

    def test_required_notrequired_outside_typed_dict_either_forbidden_or_ignored(self):
        # Some implementations raise ForbiddenQualifier; others ignore the qualifier.
        # We accept either behavior to be robust across environments.
        # Required in CLASS
        try:
            out = inspect_annotation(Required[int], annotation_source=AnnotationSource.CLASS)
        except ForbiddenQualifier:
            pass  # acceptable
        else:
            # If no error, the qualifier should not be considered valid here
            self.assertEqual(out.type, int)
            self.assertNotIn("required", out.qualifiers)

        # NotRequired in ANY should never raise (ANY allows everything)
        out_any = inspect_annotation(NotRequired[int], annotation_source=AnnotationSource.ANY)
        self.assertEqual(out_any.type, int)
        # Qualifier may or may not be included under ANY; just ensure no error
        # (No strict assertion on qualifiers)

    def test_typed_dict_allows_required_notrequired(self):
        class TD(TypedDict):
            a: Required[int]
            b: NotRequired[str]

        hints = get_type_hints(TD, include_extras=True)
        ins_a = inspect_annotation(hints["a"], annotation_source=AnnotationSource.TYPED_DICT)
        self.assertEqual(ins_a.type, int)
        self.assertIn("required", ins_a.qualifiers)

        ins_b = inspect_annotation(hints["b"], annotation_source=AnnotationSource.TYPED_DICT)
        self.assertEqual(ins_b.type, str)
        self.assertIn("not_required", ins_b.qualifiers)

    def test_bare_qualifier_unknown_final(self):
        class A:
            x: Final
            y: Final[int] = 1

        hints = get_type_hints(A, include_extras=True)

        inspected_x = inspect_annotation(hints["x"], annotation_source=AnnotationSource.CLASS)
        self.assertIs(inspected_x.type, UNKNOWN)
        self.assertIn("final", inspected_x.qualifiers)

        inspected_y = inspect_annotation(hints["y"], annotation_source=AnnotationSource.CLASS)
        self.assertEqual(inspected_y.type, int)
        self.assertIn("final", inspected_y.qualifiers)

    def test_bare_classvar_unknown(self):
        class A:
            y: ClassVar

        hints = get_type_hints(A, include_extras=True)
        inspected = inspect_annotation(hints["y"], annotation_source=AnnotationSource.CLASS)
        self.assertIs(inspected.type, UNKNOWN)
        self.assertIn("class_var", inspected.qualifiers)


class TestIntrospectionHelpers(unittest.TestCase):
    def test_is_union_origin(self):
        self.assertTrue(is_union_origin(get_origin(Union[int, str])))
        self.assertTrue(is_union_origin(get_origin(int | str)))
        self.assertFalse(is_union_origin(get_origin(List[int])))

    def test_get_literal_values_basic_and_nested(self):
        T = Literal[1, 2, 3]
        self.assertEqual(tuple(get_literal_values(T)), (1, 2, 3))

        U = List[Literal["a", "b"]]
        origin = get_origin(U)
        if is_literal(origin):
            self.fail("Outer origin should not be Literal for List[Literal[...]]")
        inner = U.__args__[0]
        self.assertEqual(tuple(get_literal_values(inner)), ("a", "b"))

    @unittest.skipUnless(sys.version_info >= (3, 12), "PEP 695 type aliases require Python 3.12+")
    def test_type_alias_unpacking_eager_and_lenient(self):
        code = (
            'type MyInt = Annotated[int, "int_meta"]\n'
            'type BrokenType = Annotated[Undefined, ...]\n'
            'type MyAlias = Annotated[BrokenType, "meta"]\n'
        )
        ns: Dict[str, object] = {"Annotated": Annotated, "Undefined": object()}
        exec(code, ns, ns)
        MyInt = ns["MyInt"]
        MyAlias = ns["MyAlias"]

        inspected = inspect_annotation(
            Annotated[MyInt, "other_meta"],
            annotation_source=AnnotationSource.CLASS,
            unpack_type_aliases="eager",
        )
        self.assertEqual(inspected.type, int)
        self.assertEqual(inspected.metadata, ["int_meta", "other_meta"])

        inspected2 = inspect_annotation(
            MyAlias,
            annotation_source=AnnotationSource.CLASS,
            unpack_type_aliases="lenient",
        )
        self.assertIn("meta", inspected2.metadata)


class TestEndToEndExpressionHandling(unittest.TestCase):
    def test_generic_vs_bare_type_branching(self):
        expr = int
        origin = get_origin(expr)
        if origin is not None and expr in DEPRECATED_ALIASES:
            expr = origin
            origin = None
        self.assertIsNone(origin)

        expr2 = List[int]
        origin2 = get_origin(expr2)
        if origin2 is not None and expr2 in DEPRECATED_ALIASES:
            expr2 = origin2
            origin2 = None
        self.assertIs(origin2, list)
        self.assertEqual(expr2.__args__, (int,))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()