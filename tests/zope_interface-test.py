import sys
import unittest

import zope.interface
from zope.interface import (
    Interface,
    Attribute,
    implementer,
    implementer_only,
    provider,
    moduleProvides,
    directlyProvides,
    directlyProvidedBy,
    alsoProvides,
    noLongerProvides,
    providedBy,
    implementedBy,
    classImplements,
    classImplementsOnly,
    invariant,
    taggedValue,
    interfacemethod,
    Declaration,
)
from zope.interface.interfaces import Invalid


# --------------------------------------------------------------------
# Interface definitions used throughout the tests
# --------------------------------------------------------------------


class IBase(Interface):
    """Basic interface with an attribute and a method."""

    base = Attribute("Base attribute")

    def method(a, b=None):
        """Example method"""


class IExtra(Interface):
    extra = Attribute("Extra attribute")


class IMarker(Interface):
    """Marker interface (no attributes)"""


class ITagged(Interface):
    """Interface with tagged value attached at definition time."""

    taggedValue("category", "example-tagged-interface")


class IWithInvariant(Interface):
    """Interface that declares an invariant."""

    value = Attribute("Numeric value that must be non-negative")

    @invariant
    def non_negative(obj):
        if obj.value < 0:
            raise Invalid("value must be non-negative")


class IWithAdapt(Interface):
    """Interface that overrides __adapt__ using interfacemethod."""

    @interfacemethod
    def __adapt__(self, obj):
        # For testing, just return a predictable value
        return ("adapted", obj)


class IFactory(Interface):
    """Factory for creating IBase providers."""

    def __call__(x=None):
        """Create an object that provides IBase"""


class IModuleMarker(Interface):
    """Marker interface used with moduleProvides."""


# Declare that *this* module provides IModuleMarker
moduleProvides(IModuleMarker)


# --------------------------------------------------------------------
# Classes implementing the interfaces in various ways
# --------------------------------------------------------------------


@implementer(IBase)
class BaseImpl:
    """Class that implements IBase."""

    def __init__(self, base):
        self.base = base

    def method(self, a, b=None):
        return (self.base, a, b)


class SubImpl(BaseImpl):
    """Subclass that will have IExtra added via classImplements."""
    pass


# Add an additional interface to SubImpl externally
classImplements(SubImpl, IExtra)


@implementer_only(IMarker)
class OnlyMarkerImpl:
    """Class that only implements IMarker (via implementer_only)."""
    pass


@implementer(IBase)
@provider(IFactory)
class ProvidedClass:
    """Class that implements IBase and *provides* IFactory as a class."""

    def __init__(self, base=None):
        self.base = base

    def method(self, a, b=None):
        return (self.base, a, b)

    def __call__(self, x=None):
        return ProvidedClass(x)


@implementer(IWithInvariant)
class WithInvariant:
    """Class whose instances will be checked against IWithInvariant."""

    def __init__(self, value):
        self.value = value


class PlainObject:
    """Plain class, used for dynamic interface declarations."""
    pass


# --------------------------------------------------------------------
# Test cases
# --------------------------------------------------------------------


class InterfaceBasicsTests(unittest.TestCase):
    def test_interface_metadata_and_attributes(self):
        self.assertEqual(IBase.__name__, "IBase")
        self.assertTrue(issubclass(IBase, Interface))
        # Names declared on the interface
        names = set(IBase.names())
        self.assertIn("base", names)
        self.assertIn("method", names)

    def test_tagged_values(self):
        self.assertEqual(
            ITagged.getTaggedValue("category"),
            "example-tagged-interface",
        )
        self.assertIn("category", list(ITagged.getTaggedValueTags()))

    def test_interface_provided_and_implemented_by(self):
        # IBase is implemented by BaseImpl instances
        self.assertTrue(IBase.implementedBy(BaseImpl))
        self.assertTrue(IBase.providedBy(BaseImpl(42)))
        # The class itself does not *provide* IBase
        self.assertFalse(IBase.providedBy(BaseImpl))


class InvariantTests(unittest.TestCase):
    def test_invariant_passes_for_valid_object(self):
        obj = WithInvariant(10)
        # Should not raise
        IWithInvariant.validateInvariants(obj)

    def test_invariant_fails_for_invalid_object(self):
        obj = WithInvariant(-1)
        with self.assertRaises(Invalid):
            IWithInvariant.validateInvariants(obj)


class ImplementerAndClassImplementsTests(unittest.TestCase):
    def test_implementer_decorator_for_class(self):
        # IBase is implemented by BaseImpl, declared via @implementer
        self.assertTrue(IBase.implementedBy(BaseImpl))
        impls = list(implementedBy(BaseImpl))
        self.assertIn(IBase, impls)

    def test_classImplements_adds_extra_interface(self):
        # SubImpl inherits IBase via BaseImpl and has IExtra via classImplements
        impls = list(implementedBy(SubImpl))
        self.assertIn(IBase, impls)
        self.assertIn(IExtra, impls)

        obj = SubImpl("base")
        provided = list(providedBy(obj))
        self.assertIn(IBase, provided)
        self.assertIn(IExtra, provided)

    def test_classImplementsOnly_replaces_interfaces(self):
        class C(BaseImpl):
            pass

        # Initially C implements IBase via inheritance
        self.assertTrue(IBase.implementedBy(C))

        # Replace the implemented interfaces with IExtra only
        classImplementsOnly(C, IExtra)

        impls = list(implementedBy(C))
        self.assertIn(IExtra, impls)
        self.assertNotIn(IBase, impls)

    def test_implementer_only_decorator(self):
        # OnlyMarkerImpl *only* implements IMarker
        self.assertTrue(IMarker.implementedBy(OnlyMarkerImpl))
        self.assertFalse(IBase.implementedBy(OnlyMarkerImpl))

        impls = list(implementedBy(OnlyMarkerImpl))
        self.assertEqual(impls, [IMarker])


class DirectlyProvidesTests(unittest.TestCase):
    def test_directlyProvides_and_directlyProvidedBy_on_object(self):
        obj = PlainObject()

        # Initially no specific interfaces are directly provided
        self.assertEqual(list(directlyProvidedBy(obj)), [])

        # Declare direct interfaces
        directlyProvides(obj, IBase)
        alsoProvides(obj, IExtra)

        direct = list(directlyProvidedBy(obj))
        self.assertIn(IBase, direct)
        self.assertIn(IExtra, direct)

        # providedBy sees the union of direct and class interfaces;
        # PlainObject doesn't implement anything, so it's just the direct ones.
        provided = list(providedBy(obj))
        self.assertIn(IBase, provided)
        self.assertIn(IExtra, provided)

    def test_alsoProvides_and_noLongerProvides(self):
        obj = PlainObject()
        directlyProvides(obj, IBase)
        alsoProvides(obj, IExtra)

        self.assertIn(IBase, directlyProvidedBy(obj))
        self.assertIn(IExtra, directlyProvidedBy(obj))

        # Remove IBase, keep IExtra
        noLongerProvides(obj, IBase)

        direct = list(directlyProvidedBy(obj))
        self.assertNotIn(IBase, direct)
        self.assertIn(IExtra, direct)

    def test_directlyProvides_on_class(self):
        class C:
            pass

        # Directly declare factory interface on the class
        directlyProvides(C, IFactory)
        self.assertTrue(IFactory.providedBy(C))
        self.assertIn(IFactory, list(providedBy(C)))


class ProviderAndModuleProvidesTests(unittest.TestCase):
    def test_provider_decorator_adds_class_provided_interfaces(self):
        # ProvidedClass instances implement IBase
        self.assertTrue(IBase.implementedBy(ProvidedClass))
        self.assertTrue(IBase.providedBy(ProvidedClass(1)))

        # The class itself provides IFactory, via @provider
        self.assertTrue(IFactory.providedBy(ProvidedClass))
        self.assertIn(IFactory, list(providedBy(ProvidedClass)))

    def test_moduleProvides_marks_module(self):
        module = sys.modules[__name__]
        self.assertTrue(IModuleMarker.providedBy(module))
        self.assertIn(IModuleMarker, list(providedBy(module)))


class DeclarationAndInterfacemethodTests(unittest.TestCase):
    def test_declaration_combines_interfaces(self):
        decl = Declaration(IBase, IExtra)
        as_list = list(decl)
        self.assertIn(IBase, as_list)
        self.assertIn(IExtra, as_list)

    def test_interfacemethod_on_interface(self):
        # __adapt__ was defined using @interfacemethod, overriding the default.
        # Calling it directly:
        result = IWithAdapt.__adapt__("obj")
        self.assertEqual(result, ("adapted", "obj"))

        # And via the adaptation API (__call__ on the interface):
        adapted = IWithAdapt("obj")
        self.assertEqual(adapted, ("adapted", "obj"))


class QueryFunctionsTests(unittest.TestCase):
    def test_providedBy_and_implementedBy_alias_methods(self):
        obj = BaseImpl("x")

        # module-level functions
        self.assertIn(IBase, list(providedBy(obj)))
        self.assertIn(IBase, list(implementedBy(BaseImpl)))

        # equivalent interface methods
        self.assertTrue(IBase.providedBy(obj))
        self.assertTrue(IBase.implementedBy(BaseImpl))

    def test_implementedBy_raises_for_non_callable(self):
        obj = BaseImpl("x")
        with self.assertRaises(TypeError):
            # As documented, implementedBy expects a factory (callable).
            IBase.implementedBy(obj)


if __name__ == "__main__":
    unittest.main()
