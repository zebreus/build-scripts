import unittest
import asyncio
import threading
import contextvars
import importlib.util

import sniffio
from sniffio import (
    current_async_library,
    AsyncLibraryNotFoundError,
    current_async_library_cvar,
    thread_local,
)

# Optional backends – tests are skipped if they aren't installed
try:
    import trio
except ImportError:  # pragma: no cover - optional
    trio = None

try:
    import curio
except ImportError:  # pragma: no cover - optional
    curio = None


class TestSniffio(unittest.TestCase):
    """
    Comprehensive tests for the sniffio module.

    Exercises:
      * current_async_library()
      * AsyncLibraryNotFoundError
      * current_async_library_cvar (ContextVar)
      * thread_local (thread-local store)
      * Basic behaviour with asyncio
      * Optional behaviour with trio / curio (if installed)
      * ContextVar isolation across contexts and threads
    """

    def setUp(self):
        # Save original state so tests don't interfere with each other
        self._orig_thread_name = getattr(thread_local, "name", None)
        # Use get(None) to work across sniffio versions
        self._orig_cvar_value = current_async_library_cvar.get(None)

    def tearDown(self):
        # Restore original state
        thread_local.name = self._orig_thread_name
        current_async_library_cvar.set(self._orig_cvar_value)

    # ------------------------------------------------------------------ #
    # Public API shape and basic invariants
    # ------------------------------------------------------------------ #

    def test_public_api_is_exposed_from_top_level(self):
        self.assertTrue(hasattr(sniffio, "current_async_library"))
        self.assertTrue(callable(sniffio.current_async_library))

        self.assertTrue(hasattr(sniffio, "AsyncLibraryNotFoundError"))
        self.assertTrue(
            issubclass(sniffio.AsyncLibraryNotFoundError, RuntimeError)
        )

        self.assertTrue(hasattr(sniffio, "current_async_library_cvar"))
        self.assertTrue(hasattr(sniffio, "thread_local"))

        # __all__ should include the primary symbols (if defined)
        if hasattr(sniffio, "__all__"):
            for name in (
                "current_async_library",
                "AsyncLibraryNotFoundError",
                "current_async_library_cvar",
                "thread_local",
            ):
                self.assertIn(name, sniffio.__all__)

    def test_version_is_string_and_nonempty(self):
        self.assertTrue(hasattr(sniffio, "__version__"))
        self.assertIsInstance(sniffio.__version__, str)
        self.assertNotEqual(sniffio.__version__.strip(), "")

    # ------------------------------------------------------------------ #
    # current_async_library core behaviour (synchronous context)
    # ------------------------------------------------------------------ #

    def test_sync_context_without_any_markers_raises(self):
        """
        When no thread_local / cvar / async library is active,
        current_async_library() should raise AsyncLibraryNotFoundError.
        """
        thread_local.name = None
        current_async_library_cvar.set(None)

        with self.assertRaises(AsyncLibraryNotFoundError) as cm:
            current_async_library()

        # Exception type and basic repr sanity
        exc = cm.exception
        self.assertIsInstance(exc, AsyncLibraryNotFoundError)
        self.assertIn("AsyncLibraryNotFoundError", repr(exc))

    def test_thread_local_overrides_detection_from_sync_context(self):
        """
        Setting thread_local.name should cause current_async_library()
        to return that value even from synchronous code.
        """
        thread_local.name = "test-thread-lib"
        current_async_library_cvar.set(None)

        lib = current_async_library()
        self.assertEqual(lib, "test-thread-lib")
        self.assertIsInstance(lib, str)

    def test_cvar_used_when_thread_local_is_none(self):
        """
        If thread_local.name is None, the ContextVar should be consulted.
        """
        thread_local.name = None
        current_async_library_cvar.set("via-cvar")

        lib = current_async_library()
        self.assertEqual(lib, "via-cvar")
        self.assertIsInstance(lib, str)

    def test_thread_local_takes_precedence_over_cvar(self):
        """
        thread_local.name should win over current_async_library_cvar.
        """
        thread_local.name = "from-thread-local"
        current_async_library_cvar.set("from-cvar")

        lib = current_async_library()
        self.assertEqual(lib, "from-thread-local")

    def test_cvar_can_be_reset_to_none(self):
        """
        Setting the ContextVar to None should make sniffio ignore it again.
        """
        thread_local.name = None
        current_async_library_cvar.set("something")
        self.assertEqual(current_async_library(), "something")

        # Reset to None and expect a failure (no backend)
        current_async_library_cvar.set(None)
        with self.assertRaises(AsyncLibraryNotFoundError):
            current_async_library()

    # ------------------------------------------------------------------ #
    # Behaviour under asyncio
    # ------------------------------------------------------------------ #

    def test_detects_asyncio_inside_running_event_loop(self):
        """
        Inside an asyncio event loop, sniffio should detect 'asyncio'.
        """

        async def coro():
            thread_local.name = None
            current_async_library_cvar.set(None)
            lib = current_async_library()
            # In a plain asyncio loop this should be 'asyncio'.
            self.assertEqual(lib, "asyncio")

        asyncio.run(coro())

    def test_asyncio_nested_tasks_all_see_asyncio(self):
        """
        Multiple tasks in the same asyncio loop should all see 'asyncio'.
        """

        async def worker(results, idx):
            results[idx] = current_async_library()

        async def main():
            thread_local.name = None
            current_async_library_cvar.set(None)
            results = [None] * 3
            await asyncio.gather(*(worker(results, i) for i in range(3)))
            return results

        results = asyncio.run(main())
        self.assertEqual(results, ["asyncio", "asyncio", "asyncio"])

    # ------------------------------------------------------------------ #
    # Optional: behaviour under trio / curio if available
    # ------------------------------------------------------------------ #

    @unittest.skipUnless(
        trio is not None and importlib.util.find_spec("trio") is not None,
        "trio not installed",
    )
    def test_detects_trio_if_installed(self):
        """
        If trio is installed, sniffio should detect it inside a trio run.
        """

        async def trio_main():
            # Clear manual overrides to rely on the backend
            thread_local.name = None
            current_async_library_cvar.set(None)
            lib = current_async_library()
            self.assertEqual(lib, "trio")

        trio.run(trio_main)

    @unittest.skipUnless(
        curio is not None and importlib.util.find_spec("curio") is not None,
        "curio not installed",
    )
    def test_detects_curio_if_installed(self):
        """
        If curio is installed, sniffio should detect it inside curio.run().
        """

        async def curio_main():
            thread_local.name = None
            current_async_library_cvar.set(None)
            lib = current_async_library()
            self.assertEqual(lib, "curio")

        curio.run(curio_main)

    # ------------------------------------------------------------------ #
    # Thread / context isolation properties
    # ------------------------------------------------------------------ #

    def test_thread_local_is_per_thread(self):
        """
        thread_local.name should be independent per thread.
        """

        # In the main thread, set a value
        thread_local.name = "main-thread-lib"
        current_async_library_cvar.set(None)

        results = []

        def worker():
            # In a new thread, we should start with the default (None)
            before = getattr(thread_local, "name", None)
            thread_local.name = "worker-thread-lib"
            lib = current_async_library()
            results.append((before, lib))

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        # Main thread still sees its own value
        self.assertEqual(thread_local.name, "main-thread-lib")

        # Worker saw its own independent value
        self.assertEqual(len(results), 1)
        before, lib = results[0]
        self.assertIsNone(before)
        self.assertEqual(lib, "worker-thread-lib")

    def test_cvar_does_not_automatically_propagate_to_new_threads(self):
        """
        Context variables used by sniffio should not automatically
        leak into new OS threads started with threading.Thread().
        """
        thread_local.name = None
        current_async_library_cvar.set("main-thread-cvar-value")

        values = []

        def worker():
            # New threads get a fresh context; the value should be None
            value_in_worker = current_async_library_cvar.get(None)
            values.append(value_in_worker)

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(values, [None])
        # Main thread still sees its original value
        self.assertEqual(current_async_library_cvar.get(None), "main-thread-cvar-value")

    # ------------------------------------------------------------------ #
    # ContextVar semantics (copy_context, isolation)
    # ------------------------------------------------------------------ #

    def test_cvar_is_context_local_and_changes_do_not_leak_back(self):
        """
        Modifying the current_async_library_cvar in a copied context should
        not affect the original context.
        """
        thread_local.name = None
        current_async_library_cvar.set("outer")

        def inner():
            # In this copied context we see the outer value initially
            self.assertEqual(current_async_library_cvar.get(None), "outer")
            # Change it and verify current_async_library respects it
            current_async_library_cvar.set("inner")
            return current_async_library()

        ctx = contextvars.copy_context()
        inner_result = ctx.run(inner)

        # In the inner context we saw / set "inner"
        self.assertEqual(inner_result, "inner")

        # In the original context, we should still see "outer"
        self.assertEqual(current_async_library_cvar.get(None), "outer")
        self.assertEqual(current_async_library(), "outer")

    def test_thread_local_and_cvar_can_coexist_without_interference(self):
        """
        Changing the ContextVar should not disturb a value forced via
        thread_local.name, and vice versa.
        """
        # Force a library name via thread-local
        thread_local.name = "forced-lib"
        current_async_library_cvar.set("cvar-lib")

        # current_async_library must see the thread-local value
        self.assertEqual(current_async_library(), "forced-lib")

        # Changing the ContextVar should not change what current_async_library sees
        current_async_library_cvar.set("other-cvar-lib")
        self.assertEqual(current_async_library(), "forced-lib")

        # If we clear thread_local.name, then the ContextVar takes over
        thread_local.name = None
        self.assertEqual(current_async_library(), "other-cvar-lib")


if __name__ == "__main__":
    unittest.main()
