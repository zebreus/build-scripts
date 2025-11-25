import unittest
import time as real_time

import eventlet
from eventlet import event, corolocal, greenthread, greenpool, timeout

# Try to get top-level aliases if present, otherwise fall back to submodules
try:
    Queue = eventlet.Queue
except AttributeError:  # older / different versions
    from eventlet.queue import Queue

try:
    GreenPool = eventlet.GreenPool
    GreenPile = eventlet.GreenPile
except AttributeError:
    from eventlet.greenpool import GreenPool, GreenPile

try:
    Lock = eventlet.lock.Lock
except (AttributeError, ImportError):
    from eventlet import semaphore as _sem_mod
    Lock = _sem_mod.Semaphore  # fallback: still exercises eventlet locking

from eventlet import semaphore as semaphore_mod


class TestGreenthreadSpawn(unittest.TestCase):
    def test_spawn_and_wait(self):
        def add(x, y=0):
            eventlet.sleep(0.01)
            return x + y

        gt = eventlet.spawn(add, 2, y=3)
        self.assertFalse(gt.dead)
        result = gt.wait()
        self.assertTrue(gt.dead)
        self.assertEqual(result, 5)

    def test_spawn_n_fire_and_forget(self):
        results = []

        def record(value):
            results.append(value)

        eventlet.spawn_n(record, 42)
        # Yield so the spawned greenthread can run
        eventlet.sleep(0)
        self.assertEqual(results, [42])

    def test_spawn_after_and_cancel(self):
        called = []

        def worker():
            called.append(True)

        gt = eventlet.spawn_after(0.05, worker)
        gt.cancel()
        # Give hub some time; worker should *not* run
        eventlet.sleep(0.1)
        self.assertEqual(called, [])

    @unittest.skipUnless(
        hasattr(eventlet, "spawn_after_local"),
        "spawn_after_local not available in this eventlet version",
    )
    def test_spawn_after_local_not_called_after_parent_exit(self):
        called = []

        def parent():
            def inner():
                called.append(True)

            # Only run this test if spawn_after_local exists
            eventlet.spawn_after_local(0.05, inner)
            # parent returns quickly; inner should never be called

        eventlet.spawn(parent).wait()
        eventlet.sleep(0.1)
        self.assertEqual(
            called, [],
            "spawn_after_local should not run if parent greenthread has exited"
        )

    def test_getcurrent_returns_current_greenthread(self):
        current_ids = []

        def worker():
            cur = greenthread.getcurrent()
            self.assertIsNotNone(cur)
            current_ids.append(id(cur))

        gt = eventlet.spawn(worker)
        gt.wait()
        self.assertEqual(len(current_ids), 1)


class TestGreenPoolAndPile(unittest.TestCase):
    def test_greenpool_imap(self):
        pool = GreenPool(10)

        def square(x):
            eventlet.sleep(0.01)
            return x * x

        data = list(pool.imap(square, range(5)))
        self.assertEqual(data, [0, 1, 4, 9, 16])
        self.assertEqual(pool.running(), 0)

    def test_greenpool_spawn_n_and_waitall(self):
        pool = GreenPool(2)
        results = []

        def worker(x):
            results.append(x)

        for i in range(5):
            pool.spawn_n(worker, i)

        pool.waitall()
        # order is not guaranteed
        self.assertCountEqual(results, list(range(5)))

    def test_greenpile_collect_results(self):
        pool = GreenPool(2)
        pile = GreenPile(pool)

        def double(x):
            eventlet.sleep(0.01)
            return x * 2

        for i in range(3):
            pile.spawn(double, i)

        collected = sorted(list(pile))
        self.assertEqual(collected, [0, 2, 4])


class TestQueue(unittest.TestCase):
    def test_queue_put_get_between_greenthreads(self):
        q = Queue()
        produced = list(range(3))

        def producer():
            for item in produced:
                q.put(item)

        def consumer():
            out = []
            for _ in produced:
                out.append(q.get())
            return out

        producer_gt = eventlet.spawn(producer)
        consumer_gt = eventlet.spawn(consumer)

        producer_gt.wait()
        consumed = consumer_gt.wait()
        self.assertEqual(consumed, produced)

    def test_queue_full_and_empty_behavior(self):
        q = Queue(maxsize=1)
        q.put(1)
        self.assertTrue(q.full())

        def consumer():
            eventlet.sleep(0.01)
            q.get()  # free space

        eventlet.spawn_n(consumer)
        # This would block without consumer; with_timeout ensures we fail fast.
        timeout.with_timeout(0.5, q.put, 2)
        self.assertFalse(q.empty())


class TestEventAndSemaphores(unittest.TestCase):
    def test_event_wait_and_send(self):
        ev = event.Event()
        results = []

        def waiter():
            value = ev.wait()
            results.append(value)

        def sender():
            eventlet.sleep(0.01)
            ev.send("done")

        wg = eventlet.spawn(waiter)
        sg = eventlet.spawn(sender)

        wg.wait()
        sg.wait()
        self.assertEqual(results, ["done"])
        self.assertTrue(ev.ready())

    def test_semaphore_acquire_release(self):
        sem = semaphore_mod.Semaphore(0)
        results = []

        def worker():
            sem.acquire()
            results.append("acquired")

        wt = eventlet.spawn(worker)
        eventlet.sleep(0.01)
        self.assertEqual(results, [])
        sem.release()
        wt.wait()
        self.assertEqual(results, ["acquired"])

    def test_lock_context_manager(self):
        lock = Lock(1)
        shared = {"value": 0}

        def worker():
            with lock:
                current = shared["value"]
                eventlet.sleep(0.01)
                shared["value"] = current + 1

        gts = [eventlet.spawn(worker) for _ in range(3)]
        for g in gts:
            g.wait()

        self.assertEqual(shared["value"], 3)


class TestTimeout(unittest.TestCase):
    def test_timeout_raises_when_block_too_long(self):
        def slow():
            eventlet.sleep(0.2)

        with self.assertRaises(timeout.Timeout):
            with timeout.Timeout(0.05):
                slow()

    def test_timeout_cancel_prevents_later_raise(self):
        t = timeout.Timeout(0.05)
        # Immediately cancel so it never fires
        t.cancel()
        # If cancel didn't work, this sleep might trigger an unexpected Timeout
        eventlet.sleep(0.1)

    def test_timeout_pending_property(self):
        t = timeout.Timeout(0.1)
        self.assertTrue(t.pending)
        t.cancel()
        self.assertFalse(t.pending)

    def test_with_timeout_successful_call(self):
        def fast():
            eventlet.sleep(0.01)
            return "ok"

        result = timeout.with_timeout(0.2, fast)
        self.assertEqual(result, "ok")

    def test_with_timeout_raises_timeout(self):
        def slow():
            eventlet.sleep(0.2)

        with self.assertRaises(timeout.Timeout):
            timeout.with_timeout(0.05, slow)


class TestCorolocal(unittest.TestCase):
    def test_corolocal_storage_is_per_greenthread(self):
        local = corolocal.local()
        values = []

        def worker1():
            local.x = 1
            eventlet.sleep(0)
            values.append(local.x)

        def worker2():
            # Should not see x set by worker1
            values.append(getattr(local, "x", 0))

        g1 = eventlet.spawn(worker1)
        g2 = eventlet.spawn(worker2)
        g1.wait()
        g2.wait()

        self.assertCountEqual(values, [1, 0])


class TestMonkeyPatchAndImportPatched(unittest.TestCase):
    def test_import_patched_time_module(self):
        patched_time = eventlet.import_patched("time")
        start = patched_time.time()

        def sleeper():
            patched_time.sleep(0.01)

        gt = eventlet.spawn(sleeper)
        gt.wait()
        elapsed = patched_time.time() - start
        self.assertGreaterEqual(elapsed, 0.01)

    def test_monkey_patch_time_only(self):
        # Patch only the time module to avoid impacting sockets/threads unnecessarily.
        eventlet.monkey_patch(time=True)

        import time as patched_time

        start_real = real_time.time()
        start_patched = patched_time.time()

        def sleeper():
            patched_time.sleep(0.02)

        gt = eventlet.spawn(sleeper)
        gt.wait()

        elapsed_real = real_time.time() - start_real
        elapsed_patched = patched_time.time() - start_patched

        # We mainly care that nothing exploded and that some time passed.
        self.assertGreaterEqual(elapsed_real, 0.02 * 0.5)  # loose bound
        self.assertGreaterEqual(elapsed_patched, 0.0)


if __name__ == "__main__":
    unittest.main()