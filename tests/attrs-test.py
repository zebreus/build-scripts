import unittest
import attr


class TestAttrsBasic(unittest.TestCase):
    def test_simple_class_equality_and_repr(self):
        @attr.s
        class Point:
            x = attr.ib()
            y = attr.ib(default=0)

        p1 = Point(1, 2)
        p2 = Point(1, 2)
        p3 = Point(1, 3)

        self.assertEqual(p1, p2)
        self.assertNotEqual(p1, p3)
        self.assertEqual("Point(x=1, y=2)", repr(p1))

    def test_slots_and_frozen(self):
        @attr.s(slots=True, frozen=True)
        class Config:
            name = attr.ib()

        c = Config("prod")
        self.assertEqual("prod", c.name)

        with self.assertRaises(attr.exceptions.FrozenInstanceError):
            c.name = "dev"  # type: ignore[assignment]


class TestAttrsConvertersAndFactories(unittest.TestCase):
    def test_basic_converter(self):
        @attr.s
        class Model:
            x = attr.ib(converter=int)
            y = attr.ib(converter=lambda v: v.strip())

        m = Model("5", "  hello  ")
        self.assertEqual(5, m.x)
        self.assertEqual("hello", m.y)

    def test_factory_param(self):
        @attr.s
        class Container:
            items = attr.ib(factory=list)

        c1 = Container()
        c2 = Container()
        self.assertEqual([], c1.items)
        self.assertIsNot(c1.items, c2.items)  # different lists

    def test_factory_object(self):
        @attr.s
        class Container:
            items = attr.ib(default=attr.Factory(list))

        c = Container()
        self.assertEqual([], c.items)
        c.items.append(1)
        self.assertEqual([1], c.items)


class TestAttrsValidators(unittest.TestCase):
    def test_instance_of_validator(self):
        @attr.s
        class User:
            name = attr.ib(validator=attr.validators.instance_of(str))
            age = attr.ib(validator=attr.validators.instance_of(int))

        u = User("Alice", 30)
        self.assertEqual("Alice", u.name)
        self.assertEqual(30, u.age)

        with self.assertRaises(TypeError):
            User(123, 30)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            User("Bob", "not-int")  # type: ignore[arg-type]

    def test_optional_validator(self):
        optional_int = attr.validators.optional(attr.validators.instance_of(int))

        @attr.s
        class MaybeValue:
            value = attr.ib(validator=optional_int)

        MaybeValue(None)
        MaybeValue(10)

        with self.assertRaises(TypeError):
            MaybeValue("nope")  # type: ignore[arg-type]

    def test_in_min_len_max_len_validators(self):
        @attr.s
        class TokenList:
            token = attr.ib(
                validator=attr.validators.in_(("A", "B", "C"))
            )
            values = attr.ib(
                validator=[
                    attr.validators.instance_of(list),
                    attr.validators.min_len(2),
                    attr.validators.max_len(4),
                ]
            )

        TokenList("A", [1, 2])
        TokenList("B", [1, 2, 3, 4])

        with self.assertRaises(ValueError):
            TokenList("Z", [1, 2])  # "Z" not in allowed set

        with self.assertRaises(ValueError):
            TokenList("A", [1])  # too short

        with self.assertRaises(ValueError):
            TokenList("A", [1, 2, 3, 4, 5])  # too long

    def test_and_or_deep_iterable_mapping_validators(self):
        int_and_positive = attr.validators.and_(
            attr.validators.instance_of(int),
            attr.validators.gt(0),
        )

        @attr.s
        class Data:
            numbers = attr.ib(
                validator=attr.validators.deep_iterable(
                    member_validator=int_and_positive,
                    iterable_validator=attr.validators.instance_of(list),
                )
            )
            mapping = attr.ib(
                validator=attr.validators.deep_mapping(
                    key_validator=attr.validators.instance_of(str),
                    value_validator=attr.validators.instance_of(int),
                    mapping_validator=attr.validators.instance_of(dict),
                )
            )

        d = Data([1, 2, 3], {"a": 1, "b": 2})
        self.assertEqual([1, 2, 3], d.numbers)
        self.assertEqual({"a": 1, "b": 2}, d.mapping)

        with self.assertRaises(TypeError):
            Data([1, "2"], {"a": 1})  # type: ignore[list-item]

        with self.assertRaises(ValueError):
            Data([1, -1], {"a": 1})  # negative violates gt(0)

        with self.assertRaises(TypeError):
            Data([1, 2], {1: 2})  # key is not str

    def test_or_validator(self):
        number_or_str = attr.validators.or_(
            attr.validators.instance_of(int),
            attr.validators.instance_of(str),
        )

        @attr.s
        class Flexible:
            value = attr.ib(validator=number_or_str)

        Flexible(1)
        Flexible("hello")

        # attrs' or_ raises ValueError if none of the validators pass
        with self.assertRaises(ValueError):
            Flexible(1.5)  # float not allowed


class TestAttrsAsdictAstuple(unittest.TestCase):
    def test_asdict_astuple_nested(self):
        @attr.s
        class Inner:
            value = attr.ib()

        @attr.s
        class Outer:
            inner = attr.ib()
            label = attr.ib()

        obj = Outer(Inner(10), "x")
        d = attr.asdict(obj)
        t = attr.astuple(obj)

        self.assertEqual({"inner": {"value": 10}, "label": "x"}, d)
        # astuple recursively converts nested attrs instances to tuples of field values
        self.assertEqual(((10,), "x"), t)

    def test_asdict_filter_and_recurse_false(self):
        @attr.s
        class C:
            a = attr.ib()
            b = attr.ib()

        obj = C(a=1, b=None)

        def not_none(_, value):
            return value is not None

        d = attr.asdict(obj, filter=not_none)
        self.assertEqual({"a": 1}, d)

        # Non-recursive: nested attrs instances left as is
        d2 = attr.asdict(obj, recurse=False)
        self.assertIsInstance(d2, dict)
        self.assertEqual({"a": 1, "b": None}, d2)


class TestAttrsFieldsMetadata(unittest.TestCase):
    def test_fields_and_metadata(self):
        @attr.s
        class User:
            name = attr.ib(metadata={"doc": "user name"})
            age = attr.ib(default=0, metadata={"doc": "age in years"})

        f = attr.fields(User)
        self.assertEqual(2, len(f))
        self.assertEqual("name", f.name.name)
        self.assertEqual("user name", f.name.metadata["doc"])
        self.assertEqual("age in years", f.age.metadata["doc"])

    def test_has_and_fields_dict(self):
        @attr.s
        class Item:
            id = attr.ib()
            title = attr.ib()

        self.assertTrue(attr.has(Item))
        self.assertFalse(attr.has(int))

        fields = attr.fields_dict(Item)
        self.assertIn("id", fields)
        self.assertIn("title", fields)
        self.assertEqual("id", fields["id"].name)


class TestAttrsOrderingAndHashing(unittest.TestCase):
    def test_ordering(self):
        @attr.s(order=True)
        class Box:
            value = attr.ib()

        b1 = Box(1)
        b2 = Box(2)
        self.assertLess(b1, b2)
        self.assertGreater(b2, b1)
        self.assertEqual(sorted([b2, b1]), [b1, b2])

    def test_hashing_with_frozen(self):
        @attr.s(frozen=True)
        class Key:
            id = attr.ib()

        k1 = Key(1)
        k2 = Key(1)
        k3 = Key(2)
        s = {k1, k3}
        self.assertIn(k2, s)
        self.assertEqual(len(s), 2)


class TestAttrsEvolve(unittest.TestCase):
    def test_evolve_updates_fields(self):
        @attr.s
        class User:
            name = attr.ib()
            age = attr.ib()

        u1 = User("Alice", 30)
        u2 = attr.evolve(u1, age=31)

        self.assertEqual("Alice", u2.name)
        self.assertEqual(31, u2.age)
        self.assertEqual(30, u1.age)  # original unchanged

    def test_evolve_unknown_field_raises(self):
        @attr.s
        class User:
            name = attr.ib()

        u = User("Alice")
        with self.assertRaises(TypeError):
            attr.evolve(u, unknown="x")  # type: ignore[call-arg]


class TestAttrsInitReprControl(unittest.TestCase):
    def test_no_repr(self):
        @attr.s(repr=False)
        class NoRepr:
            value = attr.ib()

        obj = NoRepr(10)
        self.assertEqual("10", str(obj.value))
        # repr should fall back to object default
        self.assertTrue(repr(obj).startswith("<"))

    def test_init_false(self):
        @attr.s
        class CustomInit:
            value = attr.ib(init=False)
            other = attr.ib()

            def __attrs_post_init__(self):
                self.value = self.other * 2

        c = CustomInit(other=5)
        self.assertEqual(10, c.value)


class TestAttrsSlotsBehavior(unittest.TestCase):
    def test_slots_prevent_dict_attribute(self):
        @attr.s(slots=True)
        class Slotty:
            x = attr.ib()

        s = Slotty(1)
        with self.assertRaises(AttributeError):
            _ = s.__dict__  # slots instances generally do not have __dict__


if __name__ == "__main__":
    unittest.main()
