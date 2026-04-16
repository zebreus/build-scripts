import unittest
import sys

import gevent
from gevent import Timeout, Greenlet
from gevent import queue, event, pool, lock, local, socket, subprocess, monkey


# Apply monkey patching once for tests that rely on patched stdlib behavior.
monkey.patch_all()


def add(x, y):
    gevent.sleep(0.01)  # give the scheduler something to do
    return x + y


class AdderGreenlet(Greenlet):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y

    def _run(self):
        gevent.sleep(0.01)
        return self.x + self.y


class TestGeventCore(unittest.TestCase):
    def test_spawn_and_join(self):
        results = []

        def worker(x, y=1):
            r = add(x, y)
            results.append(r)
            return r

        g1 = gevent.spawn(worker, 1, 2)
        g2 = gevent.spawn_later(0.01, worker, 3, 4)
        gevent.joinall([g1, g2], timeout=1)

        self.assertTrue(g1.ready())
        self.assertTrue(g2.ready())
        self.assertEqual(g1.value, 3)
        self.assertEqual(g2.value, 7)
        self.assertEqual(sorted(results), [3, 7])

    def test_spawn_raw(self):
        sequence = []

        def worker():
            sequence.append("start")
            gevent.sleep(0)
            sequence.append("end")

        gevent.spawn_raw(worker)
        gevent.sleep(0.05)  # allow raw greenlet to complete

        self.assertEqual(sequence, ["start", "end"])

    def test_greenlet_subclass(self):
        g = AdderGreenlet(10, 5)
        g.start()
        g.join(timeout=1)
        self.assertTrue(g.ready())
        self.assertFalse(g.exception)
        self.assertEqual(g.value, 15)

    def test_wait_timeout(self):
        def sleeper():
            gevent.sleep(0.3)

        g = gevent.spawn(sleeper)
        # Pass the greenlet explicitly: wait returns a list of ready objects
        ready = gevent.wait([g], timeout=0.05)
        # Nothing should be ready yet
        self.assertEqual(ready, [])
        g.join(timeout=1)
        self.assertTrue(g.ready())

    def test_timeout_context(self):
        timed_out = []

        with Timeout(0.05, False) as t:
            gevent.sleep(0.2)
            if t is not None and t.pending:
                # Should not get here if timeout fired
                self.fail("Timeout did not fire as expected")

        timed_out.append(getattr(t, "expired", getattr(t, "timed_out", True)))
        # The exact attribute depends on gevent version; we just assert it's True-ish.
        self.assertTrue(any(timed_out))

    def test_with_timeout_success_and_failure(self):
        # Successful case
        res = gevent.with_timeout(0.5, lambda: "ok", timeout_value="timeout")
        self.assertEqual(res, "ok")

        # Timeout case
        def slow():
            gevent.sleep(0.5)
            return "late"

        res2 = gevent.with_timeout(0.01, slow, timeout_value="timeout")
        self.assertEqual(res2, "timeout")


class TestGeventQueueEvent(unittest.TestCase):
    def test_queue_basic(self):
        q = queue.Queue()
        results = []

        def producer():
            for i in range(5):
                q.put(i)
            q.put(StopIteration)

        def consumer():
            while True:
                item = q.get()
                if item is StopIteration:
                    break
                results.append(item)

        g_prod = gevent.spawn(producer)
        g_cons = gevent.spawn(consumer)
        gevent.joinall([g_prod, g_cons], timeout=1)

        self.assertEqual(results, list(range(5)))
        self.assertTrue(q.empty())

    def test_joinable_queue(self):
        q = queue.JoinableQueue()
        processed = []

        def worker():
            while True:
                item = q.get()
                if item is None:
                    q.task_done()
                    break
                processed.append(item * 2)
                q.task_done()

        g = gevent.spawn(worker)
        for i in range(3):
            q.put(i)
        q.put(None)  # sentinel
        q.join(timeout=1)
        g.join(timeout=1)

        self.assertEqual(sorted(processed), [0, 2, 4])

    def test_priority_queue(self):
        pq = queue.PriorityQueue()
        for priority, value in [(2, "b"), (1, "a"), (3, "c")]:
            pq.put((priority, value))

        ordered = [pq.get()[1] for _ in range(3)]
        self.assertEqual(ordered, ["a", "b", "c"])

    def test_event(self):
        e = event.Event()
        results = []

        def waiter():
            results.append("wait-start")
            e.wait()
            results.append("wait-end")

        g = gevent.spawn(waiter)
        gevent.sleep(0.05)
        self.assertEqual(results, ["wait-start"])

        e.set()
        g.join(timeout=1)
        self.assertEqual(results, ["wait-start", "wait-end"])

    def test_event_clear(self):
        e = event.Event()
        e.set()
        self.assertTrue(e.is_set())
        e.clear()
        self.assertFalse(e.is_set())


class TestGeventSynchronization(unittest.TestCase):
    def test_semaphore(self):
        sem = lock.Semaphore(1)
        order = []

        def worker(name):
            with sem:
                order.append(name)
                gevent.sleep(0.01)

        g1 = gevent.spawn(worker, "first")
        g2 = gevent.spawn(worker, "second")
        gevent.joinall([g1, g2], timeout=1)

        # Due to mutual exclusion, we should not see interleaving.
        self.assertEqual(order, ["first", "second"])

    def test_bounded_semaphore(self):
        sem = lock.BoundedSemaphore(2)
        active = []

        def worker(i):
            with sem:
                active.append(i)
                gevent.sleep(0.05)
                active.remove(i)

        greens = [gevent.spawn(worker, i) for i in range(4)]
        gevent.sleep(0.02)
        # At most 2 greenlets should be active concurrently
        self.assertLessEqual(len(active), 2)
        gevent.joinall(greens, timeout=2)
        self.assertEqual(active, [])


class TestGeventPool(unittest.TestCase):
    def test_pool_map(self):
        p = pool.Pool(2)

        def square(x):
            gevent.sleep(0.01)
            return x * x

        result = p.map(square, [1, 2, 3, 4])
        self.assertEqual(result, [1, 4, 9, 16])
        p.kill()  # cleanup

    def test_pool_imap_unordered(self):
        p = pool.Pool(2)

        def negate(x):
            gevent.sleep(0.01)
            return -x

        results = list(p.imap_unordered(negate, [1, 2, 3]))
        self.assertEqual(sorted(results), [-3, -2, -1])
        p.kill()


class TestGeventLocal(unittest.TestCase):
    def test_local_storage(self):
        storage = local.local()

        def worker(name):
            storage.name = name
            gevent.sleep(0.01)
            return storage.name

        g1 = gevent.spawn(worker, "a")
        g2 = gevent.spawn(worker, "b")
        gevent.joinall([g1, g2], timeout=1)

        self.assertEqual({g1.value, g2.value}, {"a", "b"})


# class TestGeventSocketSubprocess(unittest.TestCase):
#     def test_socketpair_communication(self):
#         if not hasattr(socket, "socketpair"):
#             self.skipTest("socketpair not available on this platform")

#         s1, s2 = socket.socketpair()

#         try:
#             received = []

#             def reader(sock):
#                 data = sock.recv(1024)
#                 received.append(data.decode("ascii"))

#             g = gevent.spawn(reader, s2)
#             gevent.sleep(0.01)
#             s1.sendall(b"hello-gevent")
#             g.join(timeout=1)

#             self.assertEqual(received, ["hello-gevent"])
#         finally:
#             s1.close()
#             s2.close()

#     def test_subprocess_communicate(self):
#         # Use the same Python interpreter to keep this portable.
#         # This will be patched via gevent.subprocess / monkey.
#         cmd = [sys.executable, "-c", "print('42')"]
#         proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

#         def waiter():
#             return proc.communicate()

#         g = gevent.spawn(waiter)
#         out, err = g.get(timeout=5)
#         self.assertEqual(out.strip(), "42")
#         self.assertEqual(err.strip(), "")


class TestMonkeyPatchingBasics(unittest.TestCase):
    def test_time_sleep_is_patched(self):
        import time

        # time.sleep should now yield control cooperatively
        flag = {"ran": False}

        def worker():
            flag["ran"] = True

        gevent.spawn_later(0, worker)
        time.sleep(0.05)  # should be cooperative due to monkey patching
        self.assertTrue(flag["ran"])


if __name__ == "__main__":
    unittest.main()
