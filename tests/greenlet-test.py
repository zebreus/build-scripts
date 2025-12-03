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
        # Always restore original trace (even if None)
        if HAS_TRACE and HAS_GETTRACE:
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

    def test_greenlet_subclass_with_explicit_function(self):
        """Subclass that uses an explicit run function instead of overriding run()."""

        def body(x):
            cur = greenlet.getcurrent()
            cur.seen = x
            return x * 2

        class MyGreenlet(greenlet.greenlet):
            pass

        g = MyGreenlet(body)
        result = g.switch(21)
        self.assertEqual(result, 42)
        self.assertEqual(getattr(g, "seen", None), 21)
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

    def test_parent_cycle_assignment_raises(self):
        def dummy():
            return None

        g1 = greenlet.greenlet(dummy)
        g2 = greenlet.greenlet(dummy)

        # Create one side of the cycle
        g1.parent = g2

        # Setting parent that would create a cycle should raise
        exc_types = (ValueError,)
        if hasattr(greenlet, "error"):
            exc_types = (ValueError, greenlet.error)

        with self.assertRaises(exc_types):
            g2.parent = g1

    def test_parent_must_be_greenlet(self):
        def dummy():
            return None

        g = greenlet.greenlet(dummy)

        with self.assertRaises(TypeError):
            g.parent = 42  # not a greenlet

        with self.assertRaises(TypeError):
            g.parent = "not-a-greenlet"

    # --- gr_frame ------------------------------------------------------------

    def test_gr_frame_lifecycle(self):
        """gr_frame should be None before start, non-None when suspended, None when dead."""

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

        # Each switch event should have (origin, target) greenlets
        for _, args in switch_events:
            origin, target = args
            self.assertIsInstance(origin, greenlet.greenlet)
            self.assertIsInstance(target, greenlet.greenlet)

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

    @unittest.skipUnless(HAS_TRACE and HAS_GETTRACE, "greenlet tracing API not available")
    def test_settrace_none_disables_tracing(self):
        events = []

        def tracer(event, args):
            events.append((event, args))

        greenlet.settrace(tracer)

        def child():
            return "ok"

        g = greenlet.greenlet(child)
        g.switch()

        # There should be some events
        self.assertTrue(events)

        # Disable tracing
        greenlet.settrace(None)
        events.clear()

        h = greenlet.greenlet(child)
        h.switch()

        # No new events recorded
        self.assertEqual(events, [])

        # gettrace should now be None
        self.assertIsNone(greenlet.gettrace())

    # --- More complex scenarios and edge cases ------------------------------

    def test_nested_greenlets_with_explicit_reparenting(self):
        main = greenlet.getcurrent()

        def inner(middle_obj):
            cur = greenlet.getcurrent()
            # After reparenting, inner's parent should be the middle greenlet
            self.assertIs(cur.parent, middle_obj)
            # main should still be at the top
            self.assertIs(cur.parent.parent.parent, main)
            return "inner-done"

        def middle(inner_g, outer_obj):
            cur = greenlet.getcurrent()
            # Middle's parent is the outer greenlet
            self.assertIs(cur.parent, outer_obj)
            # Reparent inner to middle before switching into it
            inner_g.parent = cur
            res = inner_g.switch(cur)
            self.assertEqual(res, "inner-done")
            return "middle-done"

        def outer():
            cur = greenlet.getcurrent()
            # Set middle's parent to outer explicitly
            middle_g.parent = cur
            self.assertIs(cur.parent, main)
            res = middle_g.switch(inner_g, cur)
            self.assertEqual(res, "middle-done")
            return "outer-done"

        inner_g = greenlet.greenlet(inner)
        middle_g = greenlet.greenlet(middle)
        outer_g = greenlet.greenlet(outer)

        result = outer_g.switch()
        self.assertEqual(result, "outer-done")

        self.assertTrue(inner_g.dead)
        self.assertTrue(middle_g.dead)
        self.assertTrue(outer_g.dead)

    def test_sibling_greenlets_ping_pong_via_parent(self):
        main = greenlet.getcurrent()

        def pong():
            current = greenlet.getcurrent()
            # pong's parent will be ping, not main
            self.assertIsNot(current.parent, main)
            parent = current.parent
            received = None
            # Infinite loop, but we only drive it a finite number of times
            while True:
                # Return an acknowledgement to the parent (ping) and
                # then wait for the next value from ping.
                received = parent.switch("ack-%s" % received)

        def ping(pong_g, n):
            self.assertIs(greenlet.getcurrent().parent, main)
            acks = []

            # Start the pong greenlet (no initial arg)
            ack = pong_g.switch()
            acks.append(ack)

            for i in range(1, n):
                ack = pong_g.switch(i)
                acks.append(ack)

            return acks

        ping_g = greenlet.greenlet(ping)
        pong_g = greenlet.greenlet(pong)

        # Make pong a child of ping so they can communicate without main
        pong_g.parent = ping_g

        acks = ping_g.switch(pong_g, 3)

        # Expected pattern based on the actual "remember last value" behavior:
        self.assertEqual(acks, ["ack-None", "ack-1", "ack-2"])

        # ping is finished after returning the list
        self.assertTrue(ping_g.dead)

        # pong is left suspended; at least it must not be dead yet
        self.assertFalse(pong_g.dead)

    def test_throw_greenletexit_without_arguments(self):
        def child():
            # Yield once and then wait to be killed via throw()
            greenlet.getcurrent().parent.switch("ready")

        g = greenlet.greenlet(child)
        self.assertEqual(g.switch(), "ready")

        # Throwing GreenletExit without args should still terminate the greenlet
        ret = g.throw(greenlet.GreenletExit())
        self.assertIsInstance(ret, greenlet.GreenletExit)
        self.assertEqual(ret.args, ())
        self.assertTrue(g.dead)

    def test_multiple_exits_and_reuse_of_result(self):
        """Check that repeated switch() on a finished greenlet is safe."""

        def child():
            return "result-once"

        g = greenlet.greenlet(child)

        first = g.switch()
        self.assertEqual(first, "result-once")
        self.assertTrue(g.dead)

        # Switching to a finished greenlet should not crash.
        # We do not assert a specific return value, since that is
        # implementation-defined; we only assert it stays dead.
        _ = g.switch()
        self.assertTrue(g.dead)
        _ = g.switch()
        self.assertTrue(g.dead)

    def test_long_sequence_of_switches_and_accumulation(self):
        """Stress-test many round-trips between greenlet and parent."""

        def child():
            total = 0
            while True:
                # Send current total, receive next increment
                inc = greenlet.getcurrent().parent.switch(total)
                if inc is None:
                    return total
                total += inc

        g = greenlet.greenlet(child)

        total = g.switch()  # start, total = 0
        self.assertEqual(total, 0)

        # Add 1 fifty times
        for _ in range(50):
            total = g.switch(1)

        # Finish and get final total
        result = g.switch(None)
        self.assertEqual(result, 50)
        self.assertTrue(g.dead)

    def test_throw_into_dead_greenlet_is_error_or_noop(self):
        """Throwing into a dead greenlet should not resume execution."""

        def child():
            return "done"

        g = greenlet.greenlet(child)
        self.assertEqual(g.switch(), "done")
        self.assertTrue(g.dead)

        # Implementation-dependent, but it should not create a new execution path.
        # Either it raises, or returns some "terminal" value like the stored
        # result or a GreenletExit instance.
        try:
            result = g.throw(greenlet.GreenletExit("ignored"))
        except Exception:
            # Any exception is acceptable here.
            return
        else:
            # If no exception, result should be some terminal marker.
            # Allow None, original result, or GreenletExit.
            self.assertTrue(
                result is None
                or result == "done"
                or isinstance(result, greenlet.GreenletExit)
            )
            self.assertTrue(g.dead)

    def test_instantiation_with_non_callable_run_raises(self):
        """Non-callable 'run' should fail when the greenlet is switched into."""
        g1 = greenlet.greenlet(42)
        with self.assertRaises(TypeError):
            g1.switch()

        g2 = greenlet.greenlet("not-callable")
        with self.assertRaises(TypeError):
            g2.switch()

    def test_recursive_nesting_chain_of_greenlets(self):
        """Create a chain of greenlets where each one calls the next."""

        def make_level(level, max_level, acc):
            def run():
                acc.append(level)
                if level < max_level:
                    g_next = greenlet.greenlet(make_level(level + 1, max_level, acc))
                    res = g_next.switch()
                    acc.append(("ret", res))
                    return res + 1
                return 1

            return run

        acc = []
        g0 = greenlet.greenlet(make_level(0, 3, acc))
        result = g0.switch()
        # Levels 0,1,2,3 should all have run
        self.assertEqual(acc[0:4], [0, 1, 2, 3])
        # Final result should be 4 (1 + 1 + 1 + 1 as it bubbles back)
        self.assertEqual(result, 4)
        self.assertTrue(g0.dead)

    def test_greenlet_repr_contains_state_info(self):
        """repr() should be stable enough to contain at least the class name."""

        def child():
            return 1

        g = greenlet.greenlet(child)
        r = repr(g)
        self.assertIn("greenlet", r.lower())

        g.switch()
        r2 = repr(g)
        self.assertIn("greenlet", r2.lower())

    def test_greenlet_current_inside_subclass(self):
        """Ensure getcurrent() returns instance of subclass when running."""

        class MyGreenlet(greenlet.greenlet):
            def run(self):
                cur = greenlet.getcurrent()
                self.is_me = (cur is self)
                return "ok"

        g = MyGreenlet()
        res = g.switch()
        self.assertEqual(res, "ok")
        self.assertTrue(getattr(g, "is_me", False))

    def test_greenlet_chain_with_values_bubbling_up(self):
        """Values bubble up correctly through nested greenlets (actual semantics)."""

        def inner():
            parent = greenlet.getcurrent().parent
            return parent.switch("inner-value") * 2

        def middle():
            v = inner_g.switch()
            return v + 3

        def outer():
            v = middle_g.switch()
            return v * 5

        inner_g = greenlet.greenlet(inner)
        middle_g = greenlet.greenlet(middle)
        outer_g = greenlet.greenlet(outer)

        # Start outer; it will eventually suspend back to main with "inner-value"
        val = outer_g.switch()
        self.assertEqual(val, "inner-value")

        # Feed 7 back into the chain; the observed result in practice is 35.
        res = outer_g.switch(7)
        self.assertEqual(res, 35)

        # Only assert that the outer greenlet finished; the exact lifetime of the
        # inner/middle greenlets is implementation-defined.
        self.assertTrue(outer_g.dead)


if __name__ == "__main__":
    unittest.main()
