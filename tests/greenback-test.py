import unittest
import asyncio
import functools

import greenback

try:
    import trio
except ImportError:  # Trio is optional
    trio = None


async def async_double(x):
    """Simple async helper that yields to the event loop."""
    await asyncio.sleep(0)
    return 2 * x


async def async_increment(x):
    await asyncio.sleep(0)
    return x + 1


def sync_await_double(x):
    """Synchronous helper that uses greenback.await_."""
    return greenback.await_(async_double(x))


@greenback.autoawait
async def auto_triple(x):
    """Should be callable synchronously without 'await' when a portal exists."""
    await asyncio.sleep(0)
    return 3 * x


class RecordingAsyncContextManager:
    def __init__(self, log, value):
        self._log = log
        self._value = value

    async def __aenter__(self):
        self._log.append("enter")
        await asyncio.sleep(0)
        return self._value

    async def __aexit__(self, exc_type, exc, tb):
        self._log.append("exit")
        await asyncio.sleep(0)
        return False


async def async_generator(n):
    for i in range(n):
        await asyncio.sleep(0)
        yield i


call_log_for_cached = []


@greenback.decorate_as_sync(functools.lru_cache(maxsize=32))
async def cached_async_fn(x):
    """Decorated with a sync-only decorator; should still behave like an async fn."""
    call_log_for_cached.append(x)
    await asyncio.sleep(0)
    return x * 10


class GreenbackAsyncioPortalTests(unittest.IsolatedAsyncioTestCase):
    async def test_ensure_portal_and_has_portal(self):
        self.assertFalse(greenback.has_portal())
        await greenback.ensure_portal()
        self.assertTrue(greenback.has_portal())
        # Idempotent
        await greenback.ensure_portal()
        self.assertTrue(greenback.has_portal())

    async def test_await_in_sync_function_via_portal(self):
        await greenback.ensure_portal()
        result = sync_await_double(5)
        self.assertEqual(result, 10)

    async def test_with_portal_run_scopes_portal_to_call(self):
        async def inner():
            # Inside with_portal_run, a portal must be available.
            self.assertTrue(greenback.has_portal())
            return await async_increment(41)

        self.assertFalse(greenback.has_portal())
        result = await greenback.with_portal_run(inner)
        self.assertEqual(result, 42)
        # After returning, no portal should remain.
        self.assertFalse(greenback.has_portal())

    async def test_with_portal_run_sync_scopes_portal_to_call(self):
        def sync_fn(x):
            # Called in a sync context where await_ must be usable.
            self.assertTrue(greenback.has_portal())
            return greenback.await_(async_double(x))

        self.assertFalse(greenback.has_portal())
        result = await greenback.with_portal_run_sync(sync_fn, 7)
        self.assertEqual(result, 14)
        self.assertFalse(greenback.has_portal())

    async def test_bestow_portal_on_other_task(self):
        async def worker():
            # This task should see a portal immediately.
            self.assertTrue(greenback.has_portal())
            # And be able to use await_ from sync code.
            return sync_await_double(3)

        loop = asyncio.get_running_loop()
        task = loop.create_task(worker())

        # Before bestowing, the other task does not have a portal.
        self.assertFalse(greenback.has_portal(task))

        # Grant a portal to that task and verify visibility.
        greenback.bestow_portal(task)
        self.assertTrue(greenback.has_portal(task))

        result = await task
        self.assertEqual(result, 6)

    async def test_has_portal_with_explicit_task_argument(self):
        async def dummy():
            await asyncio.sleep(0)

        loop = asyncio.get_running_loop()
        task = loop.create_task(dummy())
        # Initially, the new task has no portal.
        self.assertFalse(greenback.has_portal(task))

        greenback.bestow_portal(task)
        self.assertTrue(greenback.has_portal(task))

        await task  # Clean up


class GreenbackAsyncioUtilitiesTests(unittest.IsolatedAsyncioTestCase):
    async def test_autoawait_decorator(self):
        await greenback.ensure_portal()
        # auto_triple is synchronous from the caller's perspective.
        result = auto_triple(7)
        self.assertEqual(result, 21)

    async def test_decorate_as_sync_with_lru_cache(self):
        # First call should execute the inner function.
        res1 = await cached_async_fn(5)
        self.assertEqual(res1, 50)
        # Second call with same argument should be served from cache.
        res2 = await cached_async_fn(5)
        self.assertEqual(res2, 50)
        self.assertEqual(call_log_for_cached, [5])

    async def test_async_context_allows_sync_with(self):
        await greenback.ensure_portal()
        log = []

        def sync_user():
            with greenback.async_context(RecordingAsyncContextManager(log, "value")) as v:
                log.append(f"body:{v}")

        sync_user()
        self.assertEqual(log, ["enter", "body:value", "exit"])

    async def test_async_iter_allows_sync_iteration(self):
        await greenback.ensure_portal()

        def collect(n):
            values = []
            for item in greenback.async_iter(async_generator(n)):
                values.append(item)
            return values

        self.assertEqual(collect(4), [0, 1, 2, 3])


@unittest.skipIf(trio is None, "Trio is not installed")
class GreenbackTrioTests(unittest.TestCase):
    def test_with_portal_run_tree_allows_child_tasks_to_use_await(self):
        child_has_portal_flags = []

        async def child_task():
            # Synchronous block that uses greenback.await_ in a Trio task
            def sync_block():
                greenback.await_(trio.sleep(0.01))
                return greenback.has_portal()

            child_has_portal_flags.append(sync_block())

        async def root_task():
            # root_task should also have a portal.
            self.assertTrue(greenback.has_portal())
            async with trio.open_nursery() as nursery:
                nursery.start_soon(child_task)

        async def main():
            await greenback.with_portal_run_tree(root_task)

        trio.run(main)
        self.assertEqual(child_has_portal_flags, [True])


if __name__ == "__main__":
    unittest.main()
