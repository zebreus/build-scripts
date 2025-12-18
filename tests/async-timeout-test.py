import asyncio
import unittest

from async_timeout import timeout, timeout_at


class AsyncTimeoutTests(unittest.IsolatedAsyncioTestCase):
    SHORT = 0.03
    LONG = 0.20

    async def test_timeout_does_not_expire_for_fast_block(self):
        async with timeout(self.LONG) as cm:
            await asyncio.sleep(self.SHORT)
            self.assertFalse(cm.expired())
            self.assertFalse(cm.expired)
            self.assertIsInstance(cm.when(), float)
            self.assertIsInstance(cm.deadline, float)

        self.assertFalse(cm.expired())
        self.assertFalse(cm.expired)

    async def test_timeout_expires_and_raises_timeout_error_outside_scope(self):
        cm = None
        with self.assertRaises(asyncio.TimeoutError):
            async with timeout(self.SHORT) as cm:
                await asyncio.sleep(self.LONG)

        self.assertIsNotNone(cm)
        self.assertTrue(cm.expired())
        self.assertTrue(cm.expired)

    async def test_timeout_parameter_none_disables_timeout(self):
        async with timeout(None) as cm:
            await asyncio.sleep(self.SHORT)
            self.assertFalse(cm.expired())
            self.assertFalse(cm.expired)
            self.assertIsNone(cm.when())
            self.assertIsNone(cm.deadline)

        self.assertFalse(cm.expired())
        self.assertIsNone(cm.when())

    async def test_timeout_at_uses_absolute_loop_time(self):
        loop = asyncio.get_running_loop()
        now = loop.time()

        async with timeout_at(now + self.LONG) as cm:
            await asyncio.sleep(self.SHORT)
            self.assertFalse(cm.expired())
            self.assertAlmostEqual(cm.when(), now + self.LONG, delta=0.05)

        cm2 = None
        with self.assertRaises(asyncio.TimeoutError):
            async with timeout_at(loop.time() + self.SHORT) as cm2:
                await asyncio.sleep(self.LONG)
        self.assertIsNotNone(cm2)
        self.assertTrue(cm2.expired())

    async def test_expired_false_when_inner_raises_timeout_error_explicitly(self):
        class MyTimeout(asyncio.TimeoutError):
            pass

        cm = None
        with self.assertRaises(MyTimeout):
            async with timeout(self.LONG) as cm:
                raise MyTimeout("explicit timeout raised by inner code")

        # If the inner code raised TimeoutError explicitly, cm.expired must be False.
        self.assertIsNotNone(cm)
        self.assertFalse(cm.expired())
        self.assertFalse(cm.expired)

    async def test_when_deadline_are_equal_and_float_or_none(self):
        async with timeout(self.LONG) as cm:
            w = cm.when()
            d = cm.deadline
            self.assertIsInstance(w, float)
            self.assertIsInstance(d, float)
            self.assertAlmostEqual(w, d, delta=0.0001)

        async with timeout(None) as cm2:
            self.assertIsNone(cm2.when())
            self.assertIsNone(cm2.deadline)

    async def test_reschedule_shift_update_extend_timeout(self):
        loop = asyncio.get_running_loop()

        async with timeout(self.SHORT) as cm:
            original = cm.when()
            self.assertIsNotNone(original)

            cm.reschedule(original + self.LONG)
            self.assertGreater(cm.when(), original)

            await asyncio.sleep(self.SHORT)
            self.assertFalse(cm.expired())

        async with timeout(self.SHORT) as cm2:
            original2 = cm2.when()
            self.assertIsNotNone(original2)

            cm2.shift(self.LONG)
            self.assertGreater(cm2.when(), original2)

            cm2.update(loop.time() + self.LONG)
            self.assertGreater(cm2.when(), loop.time())

            await asyncio.sleep(self.SHORT)
            self.assertFalse(cm2.expired())

    async def test_disable_timeout_via_reschedule_none_and_reject(self):
        async with timeout(self.SHORT) as cm:
            self.assertIsInstance(cm.when(), float)
            cm.reschedule(None)
            self.assertIsNone(cm.when())
            await asyncio.sleep(self.LONG)
            self.assertFalse(cm.expired())

        async with timeout(self.SHORT) as cm2:
            cm2.reject()
            self.assertIsNone(cm2.when())
            await asyncio.sleep(self.LONG)
            self.assertFalse(cm2.expired())

    async def test_reschedule_forbidden_after_exit(self):
        async with timeout(self.LONG) as cm:
            pass

        with self.assertRaises(RuntimeError):
            cm.reschedule(asyncio.get_running_loop().time() + self.LONG)
        with self.assertRaises(RuntimeError):
            cm.shift(1)
        with self.assertRaises(RuntimeError):
            cm.update(asyncio.get_running_loop().time() + 1)

    async def test_reschedule_forbidden_after_expired(self):
        cm = None
        with self.assertRaises(asyncio.TimeoutError):
            async with timeout(self.SHORT) as cm:
                await asyncio.sleep(self.LONG)

        self.assertIsNotNone(cm)
        self.assertTrue(cm.expired())

        with self.assertRaises(RuntimeError):
            cm.reschedule(asyncio.get_running_loop().time() + self.LONG)
        with self.assertRaises(RuntimeError):
            cm.shift(1)
        with self.assertRaises(RuntimeError):
            cm.update(asyncio.get_running_loop().time() + 1)
        with self.assertRaises(RuntimeError):
            cm.reject()

    async def test_nested_timeouts_inner_shorter_triggers(self):
        outer_cm = None
        inner_cm = None

        with self.assertRaises(asyncio.TimeoutError):
            async with timeout(self.LONG) as outer_cm:
                async with timeout(self.SHORT) as inner_cm:
                    await asyncio.sleep(self.LONG)

        self.assertIsNotNone(outer_cm)
        self.assertIsNotNone(inner_cm)
        self.assertTrue(inner_cm.expired())
        self.assertFalse(outer_cm.expired())

    async def test_cancellation_from_outside_is_not_reported_as_expired(self):
        task_started = asyncio.Event()
        cm_holder = {}

        async def worker():
            async with timeout(self.LONG) as cm:
                cm_holder["cm"] = cm
                task_started.set()
                await asyncio.sleep(self.LONG)

        t = asyncio.create_task(worker())
        await task_started.wait()
        await asyncio.sleep(self.SHORT)
        t.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await t

        cm = cm_holder["cm"]
        self.assertFalse(cm.expired())
        self.assertFalse(cm.expired)


if __name__ == "__main__":
    unittest.main(verbosity=2)
