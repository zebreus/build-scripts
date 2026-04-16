import io
import os
import sys
import unittest
import tempfile
import random

import lz4
import lz4.frame as lz4f
import lz4.block as lz4b

random.seed(12345)

try:
    from lz4.stream import (
        LZ4StreamCompressor,
        LZ4StreamDecompressor,
        LZ4StreamError,
    )
    HAS_STREAM = True
except Exception:
    print("lz4.stream not available", file=sys.stderr)
    HAS_STREAM = False


def randbytes(n: int) -> bytes:
    chunks = []
    remaining = n
    while remaining > 0:
        if random.random() < 0.5:
            run_len = min(remaining, random.randint(32, 1024))
            chunks.append(b"A" * run_len)
            remaining -= run_len
        else:
            run_len = min(remaining, random.randint(32, 1024))
            chunks.append(os.urandom(run_len))
            remaining -= run_len
    return b"".join(chunks)


class TestLZ4TopLevel(unittest.TestCase):
    def test_library_version(self):
        num = lz4.library_version_number()
        s = lz4.library_version_string()
        self.assertIsInstance(num, int)
        self.assertGreater(num, 0)
        self.assertIsInstance(s, str)
        self.assertRegex(s, r"^\d+\.\d+\.\d+$")


class TestLZ4FrameSimple(unittest.TestCase):
    def setUp(self):
        self.data_small = randbytes(10 * 1024)
        self.data_medium = randbytes(256 * 1024)

    def test_compress_decompress_defaults(self):
        c = lz4f.compress(self.data_small)
        d = lz4f.decompress(c)
        self.assertEqual(d, self.data_small)

    def test_compress_level_and_block_sizes(self):
        for level in (lz4f.COMPRESSIONLEVEL_MIN, 3, 9, lz4f.COMPRESSIONLEVEL_MAX, 99):
            for bs in (
                lz4f.BLOCKSIZE_DEFAULT,
                lz4f.BLOCKSIZE_MAX64KB,
                lz4f.BLOCKSIZE_MAX256KB,
                lz4f.BLOCKSIZE_MAX1MB,
                lz4f.BLOCKSIZE_MAX4MB,
            ):
                with self.subTest(level=level, block_size=bs):
                    c = lz4f.compress(
                        self.data_small,
                        compression_level=level,
                        block_size=bs,
                        block_linked=True,
                        content_checksum=False,
                    )
                    d = lz4f.decompress(c)
                    self.assertEqual(d, self.data_small)

    def test_content_checksum_and_return_types(self):
        c1 = lz4f.compress(self.data_small, content_checksum=True, return_bytearray=False)
        d1 = lz4f.decompress(c1, return_bytearray=False)
        self.assertIsInstance(c1, (bytes, bytearray))
        self.assertIsInstance(d1, (bytes, bytearray))
        self.assertEqual(bytes(d1), self.data_small)

        c2 = lz4f.compress(self.data_small, content_checksum=True, return_bytearray=True)
        self.assertIsInstance(c2, bytearray)
        d2 = lz4f.decompress(c2, return_bytearray=True)
        self.assertIsInstance(d2, bytearray)
        self.assertEqual(bytes(d2), self.data_small)

    def test_return_bytes_read(self):
        frame = lz4f.compress(self.data_small)
        payload = frame + b"TRAILING"
        out, n = lz4f.decompress(payload, return_bytes_read=True)
        self.assertEqual(out, self.data_small)
        self.assertEqual(n, len(frame))

    def test_get_frame_info(self):
        frame = lz4f.compress(
            self.data_small,
            block_size=lz4f.BLOCKSIZE_MAX256KB,
            content_checksum=True,
            block_linked=True,
        )
        info = lz4f.get_frame_info(frame)
        self.assertIsInstance(info, dict)
        # Keys present
        for k in (
            "block_size",
            "block_size_id",
            "content_checksum",
            "content_size",
            "block_linked",
            "block_checksum",
            "skippable",
        ):
            self.assertIn(k, info)
        # Types/sanity
        self.assertIsInstance(info["block_size"], int)
        self.assertIsInstance(info["content_checksum"], bool)
        self.assertIsInstance(info["block_linked"], bool)
        self.assertGreaterEqual(info["block_size"], 64 * 1024)  # 64KB or more


class TestLZ4FrameChunked(unittest.TestCase):
    def setUp(self):
        self.data = randbytes(512 * 1024)

    def _chunk(self, b: bytes, parts: int):
        sz = len(b)
        step = max(1, sz // parts)
        return [b[i : min(i + step, sz)] for i in range(0, sz, step)]

    def test_manual_context_chunked_with_flush(self):
        cctx = lz4f.create_compression_context()
        header = lz4f.compress_begin(
            cctx,
            compression_level=3,
            block_size=lz4f.BLOCKSIZE_MAX64KB,
            content_checksum=True,
            auto_flush=False,
            block_linked=True,
        )
        compressed_parts = [header]
        for chunk in self._chunk(self.data, 7):
            compressed_parts.append(lz4f.compress_chunk(cctx, chunk))
        compressed_parts.append(lz4f.compress_flush(cctx))
        compressed = b"".join(compressed_parts)

        dctx = lz4f.create_decompression_context()
        half = len(compressed) // 2
        d1, n1, e1 = lz4f.decompress_chunk(dctx, compressed[:half])
        d2, n2, e2 = lz4f.decompress_chunk(dctx, compressed[half:])
        self.assertTrue(e2)
        self.assertEqual(d1 + d2, self.data)
        self.assertEqual(n1 + n2, len(compressed))

    def test_auto_flush_true_and_mid_frame_flush(self):
        cctx = lz4f.create_compression_context()
        header = lz4f.compress_begin(cctx, auto_flush=True, block_linked=False)
        parts = [header]
        parts.append(lz4f.compress_chunk(cctx, self.data[:100_000]))
        try:
            parts.append(lz4f.compress_flush(cctx, end_frame=False))
        except RuntimeError:
            pass
        parts.append(lz4f.compress_chunk(cctx, self.data[100_000:]))
        parts.append(lz4f.compress_flush(cctx, end_frame=True))
        frame = b"".join(parts)
        self.assertEqual(lz4f.decompress(frame), self.data)

    def test_block_checksum_support_or_error(self):
        try:
            c = lz4f.compress(self.data, block_checksum=True)
        except RuntimeError:
            self.skipTest("Underlying LZ4 lib does not support block checksums")
        else:
            d = lz4f.decompress(c)
            self.assertEqual(d, self.data)


class TestLZ4FrameHelpers(unittest.TestCase):
    def setUp(self):
        self.data = randbytes(180 * 1024)

    def test_compressor_decompressor_classes(self):
        with lz4f.LZ4FrameCompressor(
            compression_level=3, block_size=lz4f.BLOCKSIZE_MAX64KB, auto_flush=False
        ) as comp:
            self.assertFalse(comp.started())
            header = comp.begin(source_size=len(self.data))
            self.assertTrue(comp.started())
            payload = header
            payload += comp.compress(self.data[:90 * 1024])
            payload += comp.compress(self.data[90 * 1024 :])
            payload += comp.flush()

        with lz4f.LZ4FrameDecompressor() as decomp:
            out = bytearray()
            chunk = decomp.decompress(payload[: len(payload) // 2], max_length=64 * 1024)
            out.extend(chunk)
            while not decomp.needs_input:
                out.extend(decomp.decompress(b"", max_length=64 * 1024))
            out.extend(decomp.decompress(payload[len(payload) // 2 :]))
            self.assertTrue(decomp.eof)
            # Some versions return None instead of b"" for "no trailing data"
            self.assertIn(decomp.unused_data, (b"", None))
            self.assertEqual(bytes(out), self.data)

    def test_reuse_after_reset(self):
        with lz4f.LZ4FrameCompressor() as comp:
            header = comp.begin()
            c1 = header + comp.compress(self.data) + comp.flush()
            header2 = comp.begin()
            c2 = header2 + comp.compress(self.data[:1024]) + comp.flush()
        d1 = lz4f.decompress(c1)
        d2 = lz4f.decompress(c2)
        self.assertEqual(d1, self.data)
        self.assertEqual(d2, self.data[:1024])


class TestLZ4FrameFiles(unittest.TestCase):
    def setUp(self):
        self.data_bin = randbytes(64 * 1024)
        self.data_txt = ("\n".join(f"line {i} — café 🥐" for i in range(1000))).encode("utf-8")

    def test_open_binary_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "data.lz4")
            with lz4f.open(path, mode="wb", compression_level=9, content_checksum=True) as fp:
                n = fp.write(self.data_bin)
                self.assertEqual(n, len(self.data_bin))
            with lz4f.open(path, mode="rb") as fp:
                out = fp.read()
            self.assertEqual(out, self.data_bin)

    def test_open_text_roundtrip(self):
        text = self.data_txt.decode("utf-8")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "text.lz4")
            with lz4f.open(path, mode="wt", encoding="utf-8", newline="\n") as fp:
                fp.write(text)
            with lz4f.open(path, mode="rt", encoding="utf-8") as fp:
                out = fp.read()
            self.assertEqual(out, text)

    def test_LZ4FrameFile_methods(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "fileobj.lz4")
            with open(path, "wb") as raw:
                with lz4f.LZ4FrameFile(raw, mode="wb", compression_level=3) as fp:
                    self.assertTrue(fp.writable())
                    self.assertFalse(fp.readable())
                    fp.write(self.data_bin)
                    fp.flush()
                    pos = fp.tell()
                    self.assertGreaterEqual(pos, 0)
            with lz4f.LZ4FrameFile(path, mode="rb") as fp:
                self.assertTrue(fp.readable())
                self.assertFalse(fp.writable())
                head = fp.read(1024)
                self.assertEqual(head, self.data_bin[:1024])
                p = fp.peek(10)
                self.assertGreaterEqual(len(p), 1)
                # read1 may not consume everything; keep reading until EOF
                rest = bytearray()
                chunk = fp.read1()
                while chunk:
                    rest.extend(chunk)
                    chunk = fp.read1()
                combined = head + bytes(rest)
                self.assertEqual(combined, self.data_bin)
                self.assertTrue(fp.seekable())
                fp.seek(0, io.SEEK_SET)
                again = fp.read(10)
                self.assertEqual(again, self.data_bin[:10])
            f = lz4f.LZ4FrameFile(path, mode="rb")
            self.assertFalse(f.closed)
            f.close()
            self.assertTrue(f.closed)
            with self.assertRaises(ValueError):
                f.read(1)


class TestLZ4BlockAPI(unittest.TestCase):
    def setUp(self):
        self.data = randbytes(128 * 1024)

    def test_block_simple(self):
        c = lz4b.compress(self.data)
        d = lz4b.decompress(c)
        self.assertEqual(d, self.data)

    def test_block_store_size_false_and_hint(self):
        data = b"0" * 255
        c = lz4b.compress(data, store_size=False)
        d = lz4b.decompress(c, uncompressed_size=255)
        self.assertEqual(d, data)
        d2 = lz4b.decompress(c, uncompressed_size=2048)
        self.assertEqual(d2, data)

    def test_block_error_on_too_small_hint(self):
        data = b"0" * 2048
        c = lz4b.compress(data, store_size=False)
        with self.assertRaises(lz4b.LZ4BlockError):
            _ = lz4b.decompress(c, uncompressed_size=64)

    def test_block_modes_and_return_types(self):
        for mode, accel, comp in [
            ("default", 1, 0),
            ("fast", 5, 0),
            ("high_compression", 1, 6),
        ]:
            with self.subTest(mode=mode):
                c = lz4b.compress(self.data, mode=mode, acceleration=accel, compression=comp, return_bytearray=True)
                self.assertIsInstance(c, bytearray)
                d = lz4b.decompress(c, return_bytearray=True)
                self.assertIsInstance(d, bytearray)
                self.assertEqual(bytes(d), self.data)

    def test_block_with_dictionary(self):
        dict_data = b"HEADER:" + (b"XYZ" * 64)
        payload = dict_data + self.data[:4096] + dict_data + self.data[4096:8192]
        c = lz4b.compress(payload, dict=dict_data)
        d = lz4b.decompress(c, dict=dict_data)
        self.assertEqual(d, payload)


@unittest.skipUnless(HAS_STREAM, "lz4.stream not available in this environment")
class TestLZ4StreamAPI(unittest.TestCase):
    def setUp(self):
        self.page_size = 8192
        self.data = randbytes(10 * self.page_size)

    def test_double_buffer_stream_roundtrip(self):
        """
        Correct usage with in-band block sizes:
        - store_comp_size=2 means each compressed block emitted by the compressor is
          prefixed with a 2-byte big-endian length.
        - Therefore we must NOT add our own size prefix. Instead, concatenate blocks
          as-is and, when decoding, let get_block() tell us where one block ends.
        """
        block_size_len = 2
        origin = self.data

        # Compress: just concatenate blocks; sizes are already embedded.
        compressed_stream = bytearray()
        with LZ4StreamCompressor("double_buffer", self.page_size, store_comp_size=block_size_len) as proc:
            offset = 0
            while offset < len(origin):
                chunk = origin[offset : offset + self.page_size]
                block = proc.compress(chunk)
                compressed_stream.extend(block)
                offset += len(chunk)

        # Decompress: use get_block() to extract each block and feed to decompress()
        decompressed_stream = bytearray()
        with LZ4StreamDecompressor("double_buffer", self.page_size, store_comp_size=block_size_len) as proc:
            offset = 0
            while offset < len(compressed_stream):
                block = proc.get_block(compressed_stream[offset:])
                decompressed_stream.extend(proc.decompress(block))
                offset += block_size_len + len(block)

        self.assertEqual(bytes(decompressed_stream), origin)

    def test_out_of_band_sizes(self):
        out_sizes = []
        compressed_stream = bytearray()
        with LZ4StreamCompressor("double_buffer", self.page_size, store_comp_size=0) as proc:
            for start in range(0, len(self.data), self.page_size):
                block = proc.compress(self.data[start : start + self.page_size])
                out_sizes.append(len(block))
                compressed_stream.extend(block)
        with LZ4StreamDecompressor("double_buffer", self.page_size, store_comp_size=0) as proc:
            decompressed = bytearray()
            offset = 0
            for sz in out_sizes:
                self.assertLessEqual(offset + sz, len(compressed_stream))
                block = compressed_stream[offset : offset + sz]
                offset += sz
                decompressed.extend(proc.decompress(block))
        self.assertEqual(bytes(decompressed), self.data)

if __name__ == "__main__":
    unittest.main()