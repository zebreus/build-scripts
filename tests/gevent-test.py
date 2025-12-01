import unittest
import time

import gevent
from gevent import monkey
from gevent import event, queue, pool, Timeout

# It's common to patch stdlib for gevent-based programs.
# For these tests it's not strictly required, but it exercises a typical usage pattern.
monkey.patch_all()


def worker_double(x, delay=0.01):
    """Simple worker that sleeps a bit and returns x * 2."""
    gevent.sleep(delay)
    return x * 2


class TestGeventBasics(unittest.TestCase):

    def test_spawn_and_join(self):
        """spawn() should run a function in a greenlet and allow joining for result."""
        g = gevent.spawn(worker_double, 21)
        g.join()
        self.assertTrue(g.dead)
        self.assertEqual(g.value, 42)

    def test_joinall(self):
        """joinall() should wait for multiple greenlets to complete."""
        results = []

        def worker(i):
            gevent.sleep(0.01 * (3 - i))  # finish in different order
            results.append(i)

        greenlets = [gevent.spawn(worker, i) for i in range(3)]
        gevent.joinall(greenlets)

        # All greenlets should be done and results should contain all values.
        self.assertTrue(all(g.dead for g in greenlets))
        self.assertCountEqual(results, [0, 1, 2])

    def test_sleep(self):
        """sleep() should suspend the current greenlet for at least the given time."""
        start = time.time()
        gevent.sleep(0.05)
        elapsed = time.time() - start
        self.assertGreaterEqual(elapsed, 0.05)

    def test_timeout_context_manager_triggered(self):
        """Timeout should trigger when the block exceeds the allotted time."""
        with Timeout(0.02, False) as t:  # don't raise, just trigger
            gevent.sleep(0.05)
        self.assertTrue(t.triggered)

    def test_timeout_context_manager_no_trigger(self):
        """Timeout should not trigger if the block finishes in time."""
        with Timeout(0.05, False) as t:
            gevent.sleep(0.01)
        self.assertFalse(t.triggered)

    def test_event_set_and_wait(self):
        """Event should unblock waiters after being set."""
        evt = event.Event()
        container = {"value": None}

        def setter():
            gevent.sleep(0.02)
            container["value"] = "ready"
            evt.set()

        g = gevent.spawn(setter)

        # Wait with a reasonable timeout to avoid hanging tests.
        result = evt.wait(timeout=0.2)
        g.join()

        self.assertTrue(result)
        self.assertTrue(evt.is_set())
        self.assertEqual(container["value"], "ready")

    def test_queue_producer_consumer(self):
        """Queue should allow safe communication between greenlets."""
        q = queue.Queue()
        consumed = []

        def producer():
            for i in range(5):
                q.put(i)
                gevent.sleep(0.005)

        def consumer():
            for _ in range(5):
                item = q.get(timeout=0.1)
                consumed.append(item)

        producer_g = gevent.spawn(producer)
        consumer_g = gevent.spawn(consumer)
        gevent.joinall([producer_g, consumer_g])

        self.assertCountEqual(consumed, list(range(5)))

    def test_pool_map(self):
        """Pool.map should apply a function to all items with limited concurrency."""
        p = pool.Pool(2)  # max 2 concurrent greenlets

        def f(x):
            gevent.sleep(0.01)
            return x * 3

        result = p.map(f, [1, 2, 3, 4])
        self.assertEqual(result, [3, 6, 9, 12])

    def test_spawn_later(self):
        """spawn_later should schedule a greenlet in the future."""
        evt = event.Event()

        def mark():
            evt.set()

        # Schedule for a bit in the future
        gevent.spawn_later(0.03, mark)

        # It should not be set immediately
        self.assertFalse(evt.is_set())
        # After sleeping long enough, it should be set
        gevent.sleep(0.06)
        self.assertTrue(evt.is_set())


if __name__ == "__main__":
    unittest.main()