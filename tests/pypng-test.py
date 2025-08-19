import io
import os
import unittest
import itertools
import tempfile

import png


class TestPyPNGBasic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    # ---------- Helpers ----------
    def _write_from_array(self, rows, mode, filename):
        path = os.path.join(self.dir, filename)
        png.from_array(rows, mode).save(path)
        return path

    def _read_all_rows_from_filename(self, path):
        """Open file safely and fully materialize rows before closing."""
        with open(path, "rb") as f:
            reader = png.Reader(file=f)
            w, h, rows, info = reader.read()
            materialized = [list(r) for r in rows]
        return w, h, materialized, info

    # ---------- from_array modes ----------
    def test_from_array_L1_write_read(self):
        rows = [
            [0, 1, 1, 1, 1, 1, 1, 0],
            [1, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 1, 0, 0, 1, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 1, 0, 0, 1, 0, 1],
            [1, 0, 0, 1, 1, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 1],
            [0, 1, 1, 1, 1, 1, 1, 0],
        ]
        path = self._write_from_array(rows, "L;1", "smile_L1.png")
        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (8, 8))
        self.assertTrue(info["greyscale"])
        self.assertFalse(info.get("alpha", False))
        self.assertEqual(info["bitdepth"], 1)
        self.assertEqual(out_rows, rows)

    def test_from_array_L8_write_read(self):
        rows = [
            [0, 64, 128, 255],
            [255, 128, 64, 0],
        ]
        path = self._write_from_array(rows, "L", "grades_L8.png")
        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (4, 2))
        self.assertTrue(info["greyscale"])
        self.assertEqual(info["bitdepth"], 8)
        self.assertEqual(out_rows, rows)

    def test_from_array_L16_write_read(self):
        row = [0, 1024, 4096, 65535]
        path = self._write_from_array([row], "L;16", "grad_L16.png")
        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (4, 1))
        self.assertTrue(info["greyscale"])
        self.assertEqual(info["bitdepth"], 16)
        self.assertEqual(out_rows[0], row)

    def test_from_array_RGB_write_read(self):
        rows = [
            (255, 0, 0,   0, 255, 0,   0, 0, 255),
            (128, 0, 0,   0, 128, 0,   0, 0, 128),
        ]
        path = self._write_from_array(rows, "RGB", "swatch_RGB.png")
        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (3, 2))
        self.assertFalse(info["greyscale"])
        self.assertFalse(info.get("alpha", False))
        self.assertEqual(info["bitdepth"], 8)
        self.assertEqual(out_rows, [list(r) for r in rows])

    def test_from_array_RGBA_write_read(self):
        rows = [
            [255, 0, 0, 0,   255, 0, 0, 128],
            [255, 0, 0, 192, 255, 0, 0, 255],
        ]
        path = self._write_from_array(rows, "RGBA", "tiny_RGBA.png")
        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (2, 2))
        self.assertFalse(info["greyscale"])
        self.assertTrue(info["alpha"])
        self.assertEqual(info["bitdepth"], 8)
        self.assertEqual(out_rows, rows)

    def test_from_array_LA_write_read(self):
        rows = [
            [0, 0,   255, 255],
            [128, 64, 64, 128],
        ]
        path = self._write_from_array(rows, "LA", "tiny_LA.png")
        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (2, 2))
        self.assertTrue(info["greyscale"])
        self.assertTrue(info["alpha"])
        self.assertEqual(out_rows, rows)

    def test_from_array_RGB1bit_write_read(self):
        # All 3-bit colors in one row; 1 bit per channel
        row = list(itertools.chain(*itertools.product([0, 1], repeat=3)))
        path = self._write_from_array([row], "RGB;1", "rgb_1bit.png")
        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (8, 1))
        # Some PyPNG versions upcast to 8-bit on read; accept both.
        self.assertIn(info["bitdepth"], (1, 8))
        out = out_rows[0]
        if info["bitdepth"] == 1:
            self.assertTrue(set(out).issubset({0, 1}))
            self.assertEqual(out, row)
        else:
            self.assertTrue(set(out).issubset({0, 255}))
            self.assertEqual(out, [v * 255 for v in row])

    # ---------- Writer (palette, interlace, streaming, file-like) ----------
    def test_writer_palette_no_alpha(self):
        rows = [
            [0, 1, 1, 1, 1, 1, 1, 0],
            [1, 0, 0, 0, 0, 0, 0, 1],
        ]
        palette = [(0x55, 0x55, 0x55), (0xFF, 0x99, 0x99)]
        wobj = png.Writer(size=(8, 2), palette=palette, bitdepth=1)
        path = os.path.join(self.dir, "pal.png")
        with open(path, "wb") as f:
            wobj.write(f, rows)

        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (8, 2))
        self.assertIn("palette", info)
        self.assertEqual(len(info["palette"]), len(palette))
        self.assertTrue(all(set(r).issubset({0, 1}) for r in out_rows))
        self.assertEqual(out_rows, rows)

    def test_writer_palette_with_alpha(self):
        rows = [
            [0, 1, 0, 1],
            [1, 0, 1, 0],
        ]
        palette = [
            (255, 0, 0, 0),      # fully transparent red
            (0, 255, 0, 255),    # opaque green
        ]
        wobj = png.Writer(size=(4, 2), palette=palette, bitdepth=1)
        path = os.path.join(self.dir, "pal_alpha.png")
        with open(path, "wb") as f:
            wobj.write(f, rows)

        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (4, 2))
        self.assertIn("palette", info)
        self.assertEqual(len(info["palette"]), 2)
        self.assertEqual(out_rows, rows)
        has_trns = "transparent" in info and info["transparent"] is not None
        has_rgba_palette = any(len(c) == 4 for c in info["palette"])
        self.assertTrue(has_trns or has_rgba_palette)

    def test_writer_interlaced(self):
        rows = [
            [0, 0, 0, 0],
            [255, 255, 255, 255],
        ]
        path = os.path.join(self.dir, "interlaced.png")

        # Try to request interlace in a version-compatible way.
        wrote_interlaced = False
        try:
            # Some versions accept interlace in __init__
            wobj = png.Writer(size=(4, 2), greyscale=True, bitdepth=8, interlace=1)
            with open(path, "wb") as f:
                wobj.write(f, rows)
            wrote_interlaced = True
        except TypeError:
            # Fallback: pass interlace to write()
            wobj = png.Writer(size=(4, 2), greyscale=True, bitdepth=8)
            try:
                with open(path, "wb") as f:
                    wobj.write(f, rows, interlace=1)
                wrote_interlaced = True
            except TypeError:
                # Neither supported; write non-interlaced
                with open(path, "wb") as f:
                    wobj.write(f, rows)

        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (4, 2))
        self.assertEqual(out_rows, rows)
        # Some newer versions omit 'interlace' in info; only assert if present.
        if "interlace" in info:
            if wrote_interlaced:
                self.assertEqual(info["interlace"], 1)
            else:
                self.assertIn(info["interlace"], (0, 1))

    def test_writer_streaming_with_generator_rows(self):
        width, height = 8, 8

        def row_gen():
            for y in range(height):
                yield [(x + y) % 2 * 255 for x in range(width)]

        wobj = png.Writer(size=(width, height), greyscale=True, bitdepth=8)
        path = os.path.join(self.dir, "checker_stream.png")
        with open(path, "wb") as f:
            wobj.write(f, row_gen())

        w, h, out_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (width, height))
        for y, r in enumerate(out_rows):
            expected = [(x + y) % 2 * 255 for x in range(width)]
            self.assertEqual(r, expected)

    def test_write_to_bytes_and_reader_from_bytes(self):
        rows = [
            [0, 64, 128, 255],
        ]
        bio = io.BytesIO()
        wobj = png.Writer(size=(4, 1), greyscale=True, bitdepth=8)
        wobj.write(bio, rows)
        data = bio.getvalue()
        self.assertGreater(len(data), 0)

        reader = png.Reader(bytes=data)
        w, h, rows_out, info = reader.read()
        rows_out = [list(r) for r in rows_out]
        self.assertEqual((w, h), (4, 1))
        self.assertTrue(info["greyscale"])
        self.assertEqual(rows_out, rows)

    # ---------- Reader variations ----------
    def test_reader_read_returns_expected_shapes(self):
        rows = [
            [255, 0, 0,  0, 255, 0,  0, 0, 255],
            [0, 0, 0,    255, 255, 255,  127, 127, 127],
        ]
        path = self._write_from_array(rows, "RGB", "reader_shapes.png")
        w, h, it_rows, info = self._read_all_rows_from_filename(path)
        self.assertEqual((w, h), (3, 2))
        chans = 4 if info.get("alpha") else (1 if info["greyscale"] else 3)
        for r in it_rows:
            self.assertEqual(len(r), w * chans)

    def test_reader_info_contains_expected_keys(self):
        rows = [[0, 1], [1, 0]]
        path = self._write_from_array(rows, "L;1", "info_keys.png")
        w, h, _, info = self._read_all_rows_from_filename(path)
        # Require only the stable keys across versions:
        for key in ("greyscale", "alpha", "bitdepth"):
            self.assertIn(key, info)
        # Optional keys that may or may not exist:
        # - 'interlace' (older versions), 'planes', 'size' (newer versions)
        if "interlace" in info:
            self.assertIsInstance(info["interlace"], int)
        if "planes" in info:
            self.assertIn(info["planes"], (1, 2, 3, 4))
        if "size" in info:
            self.assertEqual(info["size"], (w, h))


if __name__ == "__main__":
    unittest.main()