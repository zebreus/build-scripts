import asyncio
import unittest
from contextlib import suppress

import aiojobs


class TestAiojobsSchedulerAndJob(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ctxs = []

        def handler(scheduler, context):
            # Store contexts for assertions (don’t re-raise).
            self.ctxs.append(context)

        self.handler = handler

    async def test_collection_protocol_and_basic_counts(self):
        sched = aiojobs.Scheduler(exception_handler=self.handler, limit=10)

        ran = asyncio.Event()

        async def work():
            ran.set()
            return 123

        job = await sched.spawn(work(), name="basic")
        self.assertIn(job, sched)
        self.assertGreaterEqual(len(sched), 1)

        jobs = list(iter(sched))
        self.assertTrue(all(isinstance(j, aiojobs.Job) for j in jobs))

        result = await job.wait()
        self.assertEqual(result, 123)
        self.assertTrue(job.closed)
        self.assertTrue(ran.is_set())

        self.assertNotIn(job, sched)

        await sched.close()
        self.assertTrue(sched.closed)

    async def test_concurrency_limit_and_pending_state(self):
        sched = aiojobs.Scheduler(exception_handler=self.handler, limit=1)

        gate1 = asyncio.Event()
        started2 = asyncio.Event()

        async def first():
            await gate1.wait()
            return "first"

        async def second():
            started2.set()
            return "second"

        job1 = await sched.spawn(first())
        await asyncio.sleep(0)  # allow to start
        self.assertTrue(job1.active)
        self.assertEqual(sched.active_count, 1)

        job2 = await sched.spawn(second())
        await asyncio.sleep(0)
        self.assertTrue(job2.pending)
        self.assertEqual(sched.pending_count, 1)

        gate1.set()
        self.assertEqual(await job1.wait(), "first")

        await asyncio.sleep(0)  # promote pending
        self.assertTrue(started2.is_set())
        self.assertEqual(await job2.wait(), "second")

        await sched.close()

    async def test_pending_limit_may_block_spawn(self):
        sched = aiojobs.Scheduler(exception_handler=self.handler, limit=1, pending_limit=1)

        gate = asyncio.Event()
        started = asyncio.Event()

        async def long_running():
            started.set()
            await gate.wait()
            return "ok"

        async def quick(val):
            return val

        job1 = await sched.spawn(long_running())
        await asyncio.sleep(0)
        self.assertTrue(job1.active)
        await asyncio.wait_for(started.wait(), timeout=1.0)

        job2 = await sched.spawn(quick("j2"))
        await asyncio.sleep(0)
        self.assertTrue(job2.pending)

        async def spawn_third():
            j3 = await sched.spawn(quick("j3"))
            return j3

        t = asyncio.create_task(spawn_third())

        # If pending_limit is enforced as a hard cap, t may not finish yet.
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(t), timeout=0.02)

        if t.done():
            j3 = t.result()
            self.assertIsInstance(j3, aiojobs.Job)
            self.assertIn(j3, sched)  # likely tracked until finished
            self.assertEqual(await j3.wait(), "j3")
        else:
            # Drain to let the third spawn proceed.
            gate.set()
            await job1.wait()
            j3 = await asyncio.wait_for(t, timeout=1.0)
            self.assertIsInstance(j3, aiojobs.Job)
            self.assertEqual(await j3.wait(), "j3")

        gate.set()
        with suppress(Exception):
            await job1.wait()
        with suppress(Exception):
            await job2.wait()
        await sched.close()

    async def test_job_wait_timeout_and_close_behavior(self):
        sched = aiojobs.Scheduler(exception_handler=self.handler, limit=10)

        async def slow():
            await asyncio.sleep(1.0)
            return "done"

        job = await sched.spawn(slow())

        # Must time out while the job is still running.
        with self.assertRaises(asyncio.TimeoutError):
            await job.wait(timeout=0.001)

        # Different aiojobs versions may or may not time out on close() here
        # (some cancellations finish instantly). Accept either outcome.
        try:
            await job.close(timeout=0.001)
        except asyncio.TimeoutError:
            await job.close(timeout=2.0)

        self.assertTrue(job.closed)
        await sched.close()

    async def test_unhandled_job_exception_calls_exception_handler(self):
        sched = aiojobs.Scheduler(exception_handler=self.handler, limit=10)

        async def boom():
            await asyncio.sleep(0)
            raise RuntimeError("kaboom")

        job = await sched.spawn(boom())
        await asyncio.sleep(0.05)  # allow it to fail

        await sched.close()

        self.assertTrue(any(isinstance(c.get("exception"), RuntimeError) for c in self.ctxs))
        self.assertTrue(any(c.get("job") is job for c in self.ctxs))

    async def test_close_timeout_logs_via_exception_handler(self):
        # Create a job that swallows CancelledError long enough that scheduler.close()
        # should hit close_timeout and report via exception_handler (message text varies by version).
        sched = aiojobs.Scheduler(exception_handler=self.handler, close_timeout=0.02, limit=10)

        async def stubborn():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                # Ignore cancellation and keep the task alive past close_timeout
                await asyncio.sleep(0.2)

        j = await sched.spawn(stubborn())
        await asyncio.sleep(0)

        await sched.close()

        # Don’t overfit on message wording; just ensure handler was called with a "job" context.
        self.assertTrue(
            any((c.get("job") is j) and isinstance(c.get("message"), str) for c in self.ctxs),
            msg=f"exception_handler contexts: {self.ctxs!r}",
        )

    async def test_scheduler_shield_tracks_task_to_completion(self):
        sched = aiojobs.Scheduler(exception_handler=self.handler, wait_timeout=1.0, limit=10)

        done = asyncio.Event()

        async def work():
            await asyncio.sleep(0.05)
            done.set()
            return 7

        # aiojobs versions differ: Scheduler.shield may be a normal function returning a Future
        # OR an async function returning a Future. Handle both.
        shield_ret = sched.shield(work())
        if asyncio.iscoroutine(shield_ret):
            fut = await shield_ret
        else:
            fut = shield_ret

        # fut should be Future-like in this branch; but if a version returns an awaitable directly,
        # normalize by ensuring it’s awaited via wait_and_close().
        if hasattr(fut, "done"):
            self.assertFalse(fut.done())

        await sched.wait_and_close(timeout=1.0)

        self.assertTrue(done.is_set())

        if hasattr(fut, "done"):
            self.assertTrue(fut.done())
            self.assertEqual(fut.result(), 7)

        self.assertTrue(sched.closed)

    async def test_wait_and_close_cancels_remaining(self):
        sched = aiojobs.Scheduler(exception_handler=self.handler, wait_timeout=0.05, limit=10)

        started = asyncio.Event()

        async def never_finishes():
            started.set()
            await asyncio.Event().wait()

        await sched.spawn(never_finishes())
        await asyncio.wait_for(started.wait(), timeout=1.0)

        await sched.wait_and_close(timeout=0.01)
        self.assertTrue(sched.closed)


class TestAiojobsAiohttpIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_aiohttp_integration_if_available(self):
        try:
            from aiohttp import web
            from aiohttp.test_utils import make_mocked_request
            from aiojobs import aiohttp as aj_web
        except Exception:
            self.skipTest("aiohttp (and aiohttp.test_utils) not available")

        app = web.Application()
        aj_web.setup(app, limit=10)

        # Newer aiohttp requires signals to be frozen before sending on_startup/on_cleanup.
        # In normal operation this happens via AppRunner; here we do it explicitly.
        if hasattr(app, "freeze"):
            app.freeze()

        await app.startup()

        req = make_mocked_request("GET", "/", app=app)

        sched = aj_web.get_scheduler(req)
        self.assertIsInstance(sched, aiojobs.Scheduler)

        async def ok():
            await asyncio.sleep(0)
            return "hi"

        job = await aj_web.spawn(req, ok())
        self.assertIsInstance(job, aiojobs.Job)
        self.assertEqual(await job.wait(), "hi")

        shield_ret = aj_web.shield(req, ok())
        if asyncio.iscoroutine(shield_ret):
            fut = await shield_ret
        else:
            fut = shield_ret
        self.assertEqual(await fut, "hi")

        @aj_web.atomic
        async def handler(request):
            return web.Response(text="atomic-ok")

        resp = await handler(req)
        self.assertEqual(resp.text, "atomic-ok")

        await app.cleanup()
        self.assertTrue(sched.closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
