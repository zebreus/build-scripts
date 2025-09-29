import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from contextlib import contextmanager

import caio


@contextmanager
def temporary_file(initial_bytes: bytes = b""):
    """
    Yield (path, fd) for a real on-disk file so we can pass the raw FD to caio.
    The file is deleted on context exit.
    """
    f = tempfile.NamedTemporaryFile(delete=False)
    try:
        if initial_bytes:
            f.write(initial_bytes)
            f.flush()
            os.fsync(f.fileno())
        path = f.name
        fd = f.fileno()
        yield path, fd
    finally:
        try:
            f.close()
        finally:
            try:
                os.unlink(f.name)
            except FileNotFoundError:
                pass


class TestCAIOPythonImpl(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the default python backend of caio.AsyncioContext.
    """

    def _new_ctx(self, **kwargs):
        return caio.AsyncioContext(max_requests=8, **kwargs)

    async def _roundtrip(self, ctx, data: bytes, path: str, offset: int = 0) -> bytes:
        with open(path, "r+b") as fp:
            fd = fp.fileno()
            await ctx.write(data, fd, offset=offset)
            if hasattr(ctx, "fdsync"):
                await ctx.fdsync(fd)
            out = await ctx.read(len(data), fd, offset=offset)
        return out

    async def test_basic_write_read(self):
        ctx = self._new_ctx()
        payload = b"Hello world"
        with temporary_file(b"\x00" * 64) as (path, _fd):
            result = await self._roundtrip(ctx, payload, path, offset=5)
            self.assertEqual(result, payload)

    async def test_concurrent_writes_then_read_whole(self):
        ctx = self._new_ctx()
        with temporary_file(b"\x00" * 64) as (path, _fd):
            with open(path, "r+b") as fp:
                fd = fp.fileno()
                op1 = ctx.write(b"Hello from ", fd, offset=0)
                op2 = ctx.write(b"async world", fd, offset=11)
                await asyncio.gather(op1, op2)

                data = await ctx.read(22, fd, offset=0)
                self.assertEqual(data, b"Hello from async world")

    async def test_read_partial_and_bounds(self):
        ctx = self._new_ctx()
        seed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        with temporary_file(seed) as (path, _fd):
            with open(path, "rb") as fp:
                fd = fp.fileno()
                part = await ctx.read(5, fd, offset=10)
                self.assertEqual(part, seed[10:15])
                beyond = await ctx.read(10, fd, offset=len(seed) - 3)
                self.assertEqual(beyond, seed[-3:])

    async def test_large_io_over_4k(self):
        ctx = self._new_ctx()
        big = os.urandom(128 * 1024 + 123)
        with temporary_file(b"") as (path, _fd):
            out = await self._roundtrip(ctx, big, path, offset=0)
            self.assertEqual(out, big)

    async def test_fdsync_if_available(self):
        ctx = self._new_ctx()
        with temporary_file(b"") as (path, _fd):
            with open(path, "r+b") as fp:
                fd = fp.fileno()
                await ctx.write(b"data", fd, offset=0)
                if hasattr(ctx, "fdsync"):
                    await ctx.fdsync(fd)  # Should not raise

    async def test_invalid_fd_operations_raise(self):
        ctx = self._new_ctx()
        with self.assertRaises(Exception):
            await ctx.read(3, -1, offset=0)
        with self.assertRaises(Exception):
            await ctx.write(b"x", 10**7, offset=0)

    async def test_context_close_is_idempotent(self):
        ctx = self._new_ctx()
        if hasattr(ctx, "close"):
            ctx.close()
            ctx.close()  # Should not raise


if __name__ == "__main__":
    unittest.main(verbosity=2)