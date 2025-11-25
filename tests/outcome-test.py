import unittest
import asyncio
import typing
import outcome


def _sync_ok(x, y=1):
    return x + y


def _sync_fail(msg):
    raise RuntimeError(msg)


async def _async_ok(x, y=1):
    await asyncio.sleep(0)
    return x * y


async def _async_fail(msg):
    await asyncio.sleep(0)
    raise RuntimeError(msg)


def _value_gen():
    """Sync generator receiving a value, then yielding the processed result."""
    received = yield "ready"
    yield f"got {received!r}"


def _error_handling_gen():
    """Sync generator that expects an exception to be thrown into it."""
    try:
        yield "ready"
    except RuntimeError as exc:
        yield f"handled {exc.args[0]!r}"


async def _value_agen():
    """Async generator version."""
    received = yield "ready"
    yield f"got {received!r}"


async def _error_handling_agen():
    """Async generator version handling thrown exceptions."""
    try:
        yield "ready"
    except RuntimeError as exc:
        yield f"handled {exc.args[0]!r}"


class TestOutcomeCaptureSync(unittest.TestCase):
    def test_capture_success_value(self):
        res = outcome.capture(_sync_ok, 2, y=3)
        self.assertIsInstance(res, outcome.Value)
        self.assertEqual(res.unwrap(), 5)

    def test_capture_exception_error(self):
        res = outcome.capture(_sync_fail, "boom")
        self.assertIsInstance(res, outcome.Error)
        with self.assertRaises(RuntimeError) as cm:
            res.unwrap()
        self.assertEqual(str(cm.exception), "boom")

    def test_capture_args_kwargs(self):
        def fn(*args, **kwargs):
            return args, kwargs
        res = outcome.capture(fn, 1, 2, a=3)
        args, kwargs = res.unwrap()
        self.assertEqual(args, (1, 2))
        self.assertEqual(kwargs, {"a": 3})


class TestOutcomeUnwrap(unittest.TestCase):
    def test_unwrap_once_value(self):
        v = outcome.Value(10)
        self.assertEqual(v.unwrap(), 10)
        with self.assertRaises(outcome.AlreadyUsedError):
            v.unwrap()

    def test_unwrap_once_error(self):
        e = outcome.Error(RuntimeError("oops"))
        with self.assertRaises(RuntimeError):
            e.unwrap()
        with self.assertRaises(outcome.AlreadyUsedError):
            e.unwrap()


class TestOutcomeEquality(unittest.TestCase):
    def test_value_equality(self):
        v1 = outcome.Value(42)
        v2 = outcome.Value(42)
        self.assertEqual(v1, v2)
        self.assertEqual(hash(v1), hash(v2))

    def test_error_equality(self):
        exc = RuntimeError("x")
        e1 = outcome.Error(exc)
        e2 = outcome.Error(exc)
        self.assertEqual(e1, e2)

    def test_type_mismatch(self):
        self.assertNotEqual(outcome.Value(1), outcome.Error(RuntimeError("1")))


class TestOutcomeSendSync(unittest.TestCase):
    def test_value_send(self):
        gen = _value_gen()
        self.assertEqual(next(gen), "ready")
        result = outcome.Value(123).send(gen)
        self.assertEqual(result, "got 123")

    def test_error_send(self):
        gen = _error_handling_gen()
        next(gen)
        result = outcome.Error(RuntimeError("boom")).send(gen)
        self.assertEqual(result, "handled 'boom'")


class TestOutcomeMaybe(unittest.TestCase):
    def test_maybe_union(self):
        maybe = outcome.Maybe[int]
        origin = typing.get_origin(maybe)
        self.assertIs(origin, typing.Union)


class TestOutcomeAsync(unittest.IsolatedAsyncioTestCase):
    async def test_acapture_success(self):
        res = await outcome.acapture(_async_ok, 3, y=4)
        self.assertEqual(res.unwrap(), 12)

    async def test_acapture_error(self):
        res = await outcome.acapture(_async_fail, "err")
        with self.assertRaises(RuntimeError):
            res.unwrap()

    async def test_asend_value(self):
        agen = _value_agen()
        self.assertEqual(await agen.__anext__(), "ready")
        result = await outcome.Value("hi").asend(agen)
        self.assertEqual(result, "got 'hi'")

    async def test_asend_error(self):
        agen = _error_handling_agen()
        await agen.__anext__()
        result = await outcome.Error(RuntimeError("err")).asend(agen)
        self.assertEqual(result, "handled 'err'")


if __name__ == "__main__":
    unittest.main()
