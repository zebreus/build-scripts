import unittest

import greenlet

try:
    import contextvars
except ImportError:  # pragma: no cover - old Python
    contextvars = None


HAS_TRACE = hasattr(greenlet, "settrace")
HAS_GETTRACE = hasattr(greenlet, "gettrace")


class GreenletModuleTest(unittest.TestCase):
    def setUp(self):
        # Remember original trace function so we can always restore it.
        if HAS_GETTRACE:
            self._orig_trace = greenlet.gettrace()
        else:
            self._orig_trace = None

    def tearDown(self):
        if HAS_TRACE and self._orig_trace is not None:
            greenlet.settrace(self._orig_trace)

    # --- Basic API: getcurrent, main greenlet, simple switching -------------

    def test_getcurrent_and_main_properties(self):
        current = greenlet.getcurrent()
        self.assertIsInstance(current, greenlet.greenlet)

        # Main greenlet should have no parent and not be dead.
        self.assertIsNone(current.parent)
        self.assertTrue(hasattr(current, "dead"))
        self.assertFalse(current.dead)
        self.assertTrue(bool(current))

    def test_simple_switch_and_return_value(self):
        def child():
            return "child-result"

        g = greenlet.greenlet(child)
        self.assertIsInstance(g, greenlet.greenlet)
        self.assertFalse(g.dead)

        result = g.switch()
        self.assertEqual(result, "child-result")
        self.assertTrue(g.dead)
        self.assertFalse(bool(g))

    def test_switch_with_arguments_and_bidirectional_communication(self):
        def child(a, b):
            self.assertEqual((a, b), (1, 2))
            # send value back to parent, then receive one more value
            parent = greenlet.getcurrent().parent
            response = parent.switch("from-child")
            return "child-got-%s" % (response,)

        g = greenlet.greenlet(child)
        main = greenlet.getcurrent()
        self.assertIs(g.parent, main)

        # First switch starts the child with args
        value_from_child = g.switch(1, 2)
        self.assertEqual(value_from_child, "from-child")

        # Second switch sends a value back to the child
        final = g.switch("from-parent")
        self.assertEqual(final, "child-got-from-parent")
        self.assertTrue(g.dead)

    def test_bool_and_dead_states(self):
        def runner():
            parent = greenlet.getcurrent().parent
            parent.switch("from-runner")
            return "done"

        g = greenlet.greenlet(runner)
        # Not started yet
        self.assertFalse(bool(g))
        self.assertFalse(g.dead)

        # After first switch, runner is suspended => active
        first = g.switch()
        self.assertEqual(first, "from-runner")
        self.assertTrue(bool(g))
        self.assertFalse(g.dead)

        # After completion, it is dead
        second = g.switch()
        self.assertEqual(second, "done")
        self.assertFalse(bool(g))
        self.assertTrue(g.dead)

    # --- Exceptions, throw, and GreenletExit --------------------------------

    def test_exception_propagation_to_parent(self):
        class CustomError(Exception):
            pass

        def child():
            greenlet.getcurrent().parent.switch("before-error")
            raise CustomError("boom")

        g = greenlet.greenlet(child)
        self.assertEqual(g.switch(), "before-error")

        with self.assertRaises(CustomError):
            g.switch()

        self.assertTrue(g.dead)

    def test_throw_greenletexit_returns_exception_object(self):
        def child():
            # Yield once, then wait to be killed by throw()
            greenlet.getcurrent().parent.switch("loop")

        g = greenlet.greenlet(child)
        self.assertEqual(g.switch(), "loop")
        exc = greenlet.GreenletExit("bye")

        # Per docs, GreenletExit is caught in the child and returned to parent
        ret = g.throw(exc)
        self.assertIs(ret, exc)
        self.assertTrue(g.dead)
        self.assertFalse(bool(g))

    def test_throw_regular_exception_into_greenlet(self):
        class CustomError(Exception):
            pass

        def child():
            try:
                while True:
                    greenlet.getcurrent().parent.switch("loop")
            except CustomError as e:
                # Turn the exception into a return value
                return "caught-%s" % (e.args[0],)

        g = greenlet.greenlet(child)
        self.assertEqual(g.switch(), "loop")

        result = g.throw(CustomError("oops"))
        self.assertEqual(result, "caught-oops")
        self.assertTrue(g.dead)

    # --- run attribute and subclassing --------------------------------------

    def test_run_attribute_removed_after_start(self):
        def child():
            return "ok"

        g = greenlet.greenlet(child)
        # Before start, 'run' attribute is present and callable
        self.assertTrue(hasattr(g, "run"))
        self.assertTrue(callable(g.run))

        res = g.switch()
        self.assertEqual(res, "ok")

        # After the first run, the instance 'run' attribute is removed
        self.assertFalse(hasattr(g, "run"))

    def test_greenlet_subclass_with_run_method(self):
        class MyGreenlet(greenlet.greenlet):
            def __init__(self):
                super().__init__()
                self.history = []

            def run(self):
                self.history.append("started")
                return 42

        g = MyGreenlet()
        self.assertIsInstance(g, MyGreenlet)
        self.assertFalse(g.dead)

        result = g.switch()
        self.assertEqual(result, 42)
        self.assertEqual(g.history, ["started"])
        self.assertTrue(g.dead)

    # --- parent attribute ----------------------------------------------------

    def test_parent_assignment_and_default(self):
        def dummy():
            return None

        main = greenlet.getcurrent()
        g1 = greenlet.greenlet(dummy)
        g2 = greenlet.greenlet(dummy)

        # Default parent is current greenlet (main)
        self.assertIs(g1.parent, main)
        self.assertIs(g2.parent, main)

        # Reassign parent (no cycles)
        g1.parent = g2
        self.assertIs(g1.parent, g2)

    # --- gr_frame ------------------------------------------------------------

    def test_gr_frame_lifecycle(self):
        """gr_frame should be None before start, non-None when suspended, None when dead."""
        frames_supported = True
        def check_attr(obj):
            try:
                _ = obj.gr_frame
                return True
            except AttributeError:
                return False

        g = greenlet.greenlet(lambda: None)
        if not check_attr(g):
            self.skipTest("gr_frame not supported by this greenlet build")

        def child():
            # Suspend to parent; at this point, this greenlet becomes "suspended"
            parent = greenlet.getcurrent().parent
            parent.switch("yielded")
            return "done"

        g = greenlet.greenlet(child)

        # Not started yet
        self.assertIsNone(g.gr_frame)

        # First switch: child runs and switches back to parent, so g is suspended
        msg = g.switch()
        self.assertEqual(msg, "yielded")
        self.assertIsNotNone(g.gr_frame)

        # Resume and finish
        final = g.switch()
        self.assertEqual(final, "done")
        self.assertTrue(g.dead)
        self.assertIsNone(g.gr_frame)

    # --- gr_context / contextvars -------------------------------------------

    @unittest.skipIf(contextvars is None, "contextvars module not available")
    def test_gr_context_runs_in_given_context(self):
        g = greenlet.greenlet(lambda: None)
        try:
            _ = g.gr_context
        except AttributeError:
            self.skipTest("gr_context not supported by this greenlet build")

        var = contextvars.ContextVar("var", default=0)

        # Create a separate context where var is set to 123
        ctx = contextvars.Context()
        ctx.run(var.set, 123)

        def child():
            # Should see the value from the context we configured
            return var.get()

        g = greenlet.greenlet(child)
        g.gr_context = ctx

        value = g.switch()
        self.assertEqual(value, 123)
        self.assertTrue(g.dead)

    # --- Tracing: gettrace / settrace ---------------------------------------

    @unittest.skipUnless(HAS_TRACE and HAS_GETTRACE, "greenlet tracing API not available")
    def test_settrace_and_gettrace_switch_event(self):
        events = []

        def tracer(event, args):
            events.append((event, args))

        original = greenlet.gettrace()
        previous = greenlet.settrace(tracer)

        # settrace returns the previous trace function
        self.assertIs(previous, original)

        def child():
            return "ok"

        g = greenlet.greenlet(child)
        res = g.switch()
        self.assertEqual(res, "ok")
        self.assertTrue(g.dead)

        # We should have seen at least one 'switch' event
        switch_events = [e for e in events if e[0] == "switch"]
        self.assertGreaterEqual(len(switch_events), 1)

    @unittest.skipUnless(HAS_TRACE and HAS_GETTRACE, "greenlet tracing API not available")
    def test_trace_throw_event(self):
        events = []

        def tracer(event, args):
            events.append((event, args))

        greenlet.settrace(tracer)

        def child():
            # Wait for an exception to be thrown into this greenlet
            greenlet.getcurrent().parent.switch("ready")

        g = greenlet.greenlet(child)
        self.assertEqual(g.switch(), "ready")

        # Throw a regular exception into the child; it will propagate up.
        class CustomError(Exception):
            pass

        with self.assertRaises(CustomError):
            g.throw(CustomError("boom"))

        throw_events = [e for e in events if e[0] == "throw"]
        self.assertGreaterEqual(len(throw_events), 1)
        # Each throw event should have (origin, target) greenlets
        for _, args in throw_events:
            origin, target = args
            self.assertIsInstance(origin, greenlet.greenlet)
            self.assertIsInstance(target, greenlet.greenlet)


if __name__ == "__main__":
    unittest.main()