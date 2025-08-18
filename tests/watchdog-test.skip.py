# Broken on Wasix, but works on native.
import os
import time
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileDeletedEvent,
    DirCreatedEvent,
    DirMovedEvent,
    DirDeletedEvent,
)
from watchdog.observers.polling import PollingObserver as Observer
# If you prefer the native backend, comment the line above and use:
# from watchdog.observers import Observer


# --- Utilities ---------------------------------------------------------------

def wait_for(predicate, timeout=5.0, interval=0.05, msg="condition not met in time"):
    """Poll until predicate() returns a truthy value or timeout (seconds) elapses."""
    end = time.time() + timeout
    while time.time() < end:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    raise AssertionError(msg)

# Add this helper near the other utilities
def wait_for_move_or_create_delete(handler, src, dst, timeout=5.0):
    def pred():
        evs = handler.events
        # Native backends (inotify/FSEvents/ReadDirectoryChangesW) usually emit FileMovedEvent
        if has_event(evs, FileMovedEvent, path=src, dest_path=dst, is_directory=False):
            return True
        # Polling backend typically emits delete+create instead of a move
        deleted = has_event(evs, FileDeletedEvent, path=src, is_directory=False)
        created = has_event(evs, FileCreatedEvent, path=dst, is_directory=False)
        return deleted and created
    wait_for(pred, timeout, msg="move (or delete+create) not observed")


class RecordingHandler(FileSystemEventHandler):
    """Collects incoming events; thread-safe."""
    def __init__(self):
        self._events = []
        self._lock = threading.Lock()
        self._new_event = threading.Event()

    def on_any_event(self, event):
        with self._lock:
            self._events.append(event)
            self._new_event.set()

    def clear_flag(self):
        self._new_event.clear()

    def wait_any(self, timeout=5.0):
        if not self._new_event.wait(timeout):
            raise AssertionError("no events received within timeout")

    @property
    def events(self):
        with self._lock:
            return list(self._events)


def has_event(events, event_type, path=None, dest_path=None, is_directory=None):
    """Return True if an event of (sub)class event_type matching optional fields exists."""
    for e in events:
        # print(f"Checking event: {e}")
        if isinstance(e, event_type):
            if path is not None and os.path.normcase(getattr(e, "src_path", "")) != os.path.normcase(str(path)):
                continue
            if dest_path is not None and os.path.normcase(getattr(e, "dest_path", "")) != os.path.normcase(str(dest_path)):
                continue
            if is_directory is not None and getattr(e, "is_directory", None) is not is_directory:
                continue
            return True
    return False


# --- Tests -------------------------------------------------------------------

class TestWatchdogBasics(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="wdt-")).resolve()
        self.handler = RecordingHandler()
        self.observer = Observer(timeout=0.2)
        # Use a short polling interval for responsive tests.
        self.observer.schedule(self.handler, str(self.tmpdir), recursive=True)
        self.observer.start()

    def tearDown(self):
        try:
            self.observer.stop()
            self.observer.join(5)
        finally:
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_file_triggers_FileCreatedEvent(self):
        f = self.tmpdir / "hello.txt"
        f.write_text("hi\n")

        wait_for(lambda: has_event(self.handler.events, FileCreatedEvent, path=f, is_directory=False))

    def test_modify_file_triggers_FileModifiedEvent(self):
        f = self.tmpdir / "mod.txt"
        f.write_text("a\n")
        # Clear previous events so we don't match the create event.
        self.handler.clear_flag()
        self.handler.wait_any(2)  # ensure the create was delivered
        self.handler.clear_flag()

        f.write_text("b\n")  # modify
        wait_for(lambda: has_event(self.handler.events, FileModifiedEvent, path=f, is_directory=False))

    def test_move_and_delete_file(self):
        src = self.tmpdir / "move_me.txt"
        dst = self.tmpdir / "moved.txt"
        src.write_text("x\n")
        time.sleep(0.5)  # Ensure the create event is processed
    
        # Move (rename)
        src.rename(dst)
        wait_for_move_or_create_delete(self.handler, src, dst)
    
        # Delete the destination
        dst.unlink()
        wait_for(lambda: has_event(self.handler.events, FileDeletedEvent, path=dst, is_directory=False))

    def test_create_move_delete_directory(self):
        d1 = self.tmpdir / "dirA"
        d2 = self.tmpdir / "dirB"

        d1.mkdir()
        wait_for(lambda: has_event(self.handler.events, DirCreatedEvent, path=d1, is_directory=True))

        d1.rename(d2)
        wait_for(lambda: has_event(self.handler.events, DirMovedEvent, path=d1, dest_path=d2, is_directory=True))

        d2.rmdir()
        wait_for(lambda: has_event(self.handler.events, DirDeletedEvent, path=d2, is_directory=True))

    def test_recursive_watch_sees_events_in_subdirs(self):
        sub = self.tmpdir / "nested"
        sub.mkdir()
        g = sub / "deep.txt"
        g.write_text("nested")

        # Creation inside subdir should be observed because recursive=True
        wait_for(lambda: has_event(self.handler.events, FileCreatedEvent, path=g, is_directory=False))

    def test_non_recursive_ignores_subdir_events(self):
        # Create a separate observer scheduled non-recursively.
        handler = RecordingHandler()
        obs = Observer(timeout=0.2)
        obs.schedule(handler, str(self.tmpdir), recursive=False)
        obs.start()
        try:
            sub = self.tmpdir / "only_deeper"
            sub.mkdir()
            (sub / "x.txt").write_text("x")

            # Give it a moment to deliver possible top-level events.
            time.sleep(0.5)
            evs = handler.events

            # We may see DirCreatedEvent for the subdir itself in the watched dir,
            # but must NOT see the file created *inside* that subdir.
            self.assertTrue(has_event(evs, DirCreatedEvent, path=sub, is_directory=True))
            self.assertFalse(any(isinstance(e, FileCreatedEvent) and os.path.normcase(e.src_path) == os.path.normcase(str(sub / "x.txt")) for e in evs))
        finally:
            obs.stop()
            obs.join(5)


if __name__ == "__main__":
    unittest.main(verbosity=2)