import asyncio
import unittest

from aiosignal import Signal


class TestAioSignalSignal(unittest.IsolatedAsyncioTestCase):
    def test_repr_includes_owner_and_frozen_state(self):
        class Owner:
            def __repr__(self) -> str:
                return "OWNER-REPR"

        sig = Signal(Owner())
        r = repr(sig)
        self.assertIn("Signal", r)
        self.assertIn("OWNER-REPR", r)
        self.assertIn("frozen=False", r)

        sig.freeze()
        r2 = repr(sig)
        self.assertIn("frozen=True", r2)

    def test_mutable_sequence_ops_before_freeze(self):
        sig = Signal("owner")

        async def a():
            return None

        async def b():
            return None

        async def c():
            return None

        # append / extend
        sig.append(a)
        sig.extend([b])
        self.assertEqual(len(sig), 2)
        self.assertIs(sig[0], a)
        self.assertIs(sig[1], b)

        # insert
        sig.insert(1, c)
        self.assertEqual(list(sig), [a, c, b])

        # setitem
        sig[1] = b
        self.assertEqual(list(sig), [a, b, b])

        # delitem
        del sig[2]
        self.assertEqual(list(sig), [a, b])

        # pop
        popped = sig.pop()
        self.assertIs(popped, b)
        self.assertEqual(list(sig), [a])

        # clear
        sig.clear()
        self.assertEqual(len(sig), 0)

        # misc read ops
        sig.extend([a, b, a])
        self.assertTrue(a in sig)
        self.assertEqual(sig.count(a), 2)
        self.assertEqual(sig.index(b), 1)

    def test_freeze_is_idempotent_and_frozen_property(self):
        sig = Signal("owner")
        self.assertFalse(sig.frozen)
        sig.freeze()
        self.assertTrue(sig.frozen)
        sig.freeze()
        self.assertTrue(sig.frozen)

    def test_freeze_prevents_modifications(self):
        sig = Signal("owner")

        async def cb():
            return None

        sig.append(cb)
        sig.freeze()

        def assert_frozen_raises(fn, *args, **kwargs):
            with self.assertRaises(RuntimeError) as ctx:
                fn(*args, **kwargs)
            self.assertIn("frozen", str(ctx.exception).lower())

        assert_frozen_raises(sig.append, cb)
        assert_frozen_raises(sig.extend, [cb])
        assert_frozen_raises(sig.insert, 0, cb)
        assert_frozen_raises(sig.remove, cb)
        assert_frozen_raises(sig.clear)
        assert_frozen_raises(sig.pop)
        assert_frozen_raises(sig.__setitem__, 0, cb)
        assert_frozen_raises(sig.__delitem__, 0)

    async def test_send_requires_frozen(self):
        sig = Signal("owner")

        async def cb():
            return None

        sig.append(cb)
        with self.assertRaises(RuntimeError) as ctx:
            await sig.send()
        self.assertIn("non-frozen", str(ctx.exception).lower())

    async def test_send_invokes_in_order_and_passes_args_kwargs(self):
        sig = Signal("owner")
        calls = []

        async def cb1(*args, **kwargs):
            calls.append(("cb1", args, kwargs))

        async def cb2(*args, **kwargs):
            calls.append(("cb2", args, kwargs))

        async def cb3(*args, **kwargs):
            calls.append(("cb3", args, kwargs))

        sig.extend([cb1, cb2, cb3])
        sig.freeze()

        await sig.send(42, "foo", k="v")
        self.assertEqual([c[0] for c in calls], ["cb1", "cb2", "cb3"])
        for _, args, kwargs in calls:
            self.assertEqual(args, (42, "foo"))
            self.assertEqual(kwargs, {"k": "v"})

    async def test_send_is_sequential_awaiting(self):
        sig = Signal("owner")
        started = []
        gate = asyncio.Event()

        async def first():
            started.append("first-start")
            await gate.wait()
            started.append("first-end")

        async def second():
            started.append("second")

        sig.extend([first, second])
        sig.freeze()

        task = asyncio.create_task(sig.send())
        await asyncio.sleep(0)  # let "first" start

        self.assertIn("first-start", started)
        self.assertNotIn("second", started)  # second must not run until first completes

        gate.set()
        await task
        self.assertEqual(started, ["first-start", "first-end", "second"])

    async def test_send_propagates_exceptions_and_stops_iteration(self):
        sig = Signal("owner")
        calls = []

        async def boom():
            calls.append("boom")
            raise ValueError("kaboom")

        async def should_not_run():
            calls.append("should-not-run")

        sig.extend([boom, should_not_run])
        sig.freeze()

        with self.assertRaises(ValueError):
            await sig.send()

        self.assertEqual(calls, ["boom"])

    async def test_send_rejects_non_coroutine_callback(self):
        sig = Signal("owner")

        def not_async(*args, **kwargs):
            return None

        sig.append(not_async)  # allowed before freeze
        sig.freeze()

        with self.assertRaises(TypeError):
            await sig.send(1, 2, x=3)

    async def test_send_with_no_callbacks_is_noop(self):
        sig = Signal("owner")
        sig.freeze()
        await sig.send(1, 2, x=3)  # should not raise


if __name__ == "__main__":
    unittest.main(verbosity=2)
