import unittest

import zope.event


class ZopeEventTests(unittest.TestCase):
    def setUp(self):
        # Save and clear the global subscribers list so each test is isolated.
        self._original_subscribers = list(zope.event.subscribers)
        zope.event.subscribers[:] = []

    def tearDown(self):
        # Restore the original subscribers list exactly as it was.
        zope.event.subscribers[:] = self._original_subscribers

    # ------------------------------------------------------------------
    # Basic structure / data tests
    # ------------------------------------------------------------------

    def test_subscribers_is_a_list(self):
        self.assertIsInstance(zope.event.subscribers, list)

    def test_subscribers_can_be_modified_like_a_list(self):
        def handler(event):
            pass

        zope.event.subscribers.append(handler)
        self.assertIn(handler, zope.event.subscribers)

        zope.event.subscribers.remove(handler)
        self.assertNotIn(handler, zope.event.subscribers)

    # ------------------------------------------------------------------
    # notify() basic behavior
    # ------------------------------------------------------------------

    def test_notify_calls_single_subscriber_with_event(self):
        events_seen = []

        def handler(event):
            events_seen.append(event)

        zope.event.subscribers.append(handler)

        event = object()
        zope.event.notify(event)

        self.assertEqual(events_seen, [event])

    def test_notify_calls_multiple_subscribers_in_registration_order(self):
        call_sequence = []

        def handler_one(event):
            call_sequence.append(("one", event))

        def handler_two(event):
            call_sequence.append(("two", event))

        zope.event.subscribers.append(handler_one)
        zope.event.subscribers.append(handler_two)

        event = "test-event"
        zope.event.notify(event)

        self.assertEqual(
            call_sequence,
            [("one", event), ("two", event)],
        )

    def test_notify_accepts_any_event_object(self):
        # The implementation does not care about the event type.
        recorded = []

        def handler(event):
            recorded.append(type(event))

        zope.event.subscribers.append(handler)

        zope.event.notify(42)
        zope.event.notify(None)

        class CustomEvent:
            pass

        zope.event.notify(CustomEvent())

        self.assertEqual(
            recorded,
            [int, type(None), CustomEvent],
        )

    # ------------------------------------------------------------------
    # Error propagation / short-circuit behavior
    # ------------------------------------------------------------------

    def test_notify_propagates_exceptions_and_stops_after_failing_subscriber(self):
        calls = []

        class MyError(Exception):
            pass

        def bad_handler(event):
            calls.append("bad")
            raise MyError("boom")

        def never_called_handler(event):
            calls.append("never")

        zope.event.subscribers.append(bad_handler)
        zope.event.subscribers.append(never_called_handler)

        with self.assertRaises(MyError):
            zope.event.notify("event")

        # Only the first (failing) subscriber should have been called.
        self.assertEqual(calls, ["bad"])

    def test_notify_works_again_after_exception(self):
        """
        After an exception from a handler, subsequent notify() calls
        should still work as normal once the exception is handled.
        """
        calls = []

        class MyError(Exception):
            pass

        def sometimes_bad(event):
            if event == "fail":
                raise MyError("boom")
            calls.append(("ok", event))

        zope.event.subscribers.append(sometimes_bad)

        # First call raises.
        with self.assertRaises(MyError):
            zope.event.notify("fail")

        # Second call should succeed and call the handler.
        zope.event.notify("success")

        self.assertEqual(calls, [("ok", "success")])

    # ------------------------------------------------------------------
    # Interaction with subscriber list operations
    # ------------------------------------------------------------------

    def test_subscriber_can_unsubscribe_itself(self):
        """
        Modifying the subscribers list during iteration is not part of
        the documented API, but this test records the current behavior:
        a handler can remove itself and still be called for the current
        notification.
        """
        calls = []

        def self_removing_handler(event):
            calls.append("self")
            zope.event.subscribers.remove(self_removing_handler)

        zope.event.subscribers.append(self_removing_handler)

        # First notify: handler should run and then remove itself.
        zope.event.notify("first")
        self.assertEqual(calls, ["self"])
        self.assertNotIn(self_removing_handler, zope.event.subscribers)

        # Second notify: handler should no longer be called.
        zope.event.notify("second")
        self.assertEqual(calls, ["self"])

    def test_subscriber_removed_before_notify_is_not_called(self):
        calls = []

        def handler(event):
            calls.append(event)

        zope.event.subscribers.append(handler)
        zope.event.subscribers.remove(handler)

        zope.event.notify("event")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()