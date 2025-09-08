import unittest
import numpy as np
import numpy.ma as ma

from contourpy import (
    contour_generator,
    FillType,
    LineType,
    ZInterp,
    convert_lines,
    convert_filled,
    convert_multi_lines,
    convert_multi_filled,
    dechunk_lines,
    dechunk_filled,
    dechunk_multi_lines,
    dechunk_multi_filled,
    max_threads,
    SerialContourGenerator,
    ThreadedContourGenerator,
    Mpl2005ContourGenerator,
    Mpl2014ContourGenerator,
)

# ---------------- Helpers ---------------- #

def lines_as_separate(lines_any, line_type_from):
    return list(convert_lines(lines_any, line_type_from, LineType.Separate))

def multi_lines_as_separate(multi_lines_any, line_type_from):
    ml = convert_multi_lines(multi_lines_any, line_type_from, LineType.Separate)
    return [list(group) for group in ml]

def filled_as_outer_offset(filled_any, fill_type_from):
    pts_list, offs_list = convert_filled(filled_any, fill_type_from, FillType.OuterOffset)
    return list(pts_list), list(offs_list)

def multi_filled_as_outer_offset(mf_any, fill_type_from):
    conv = convert_multi_filled(mf_any, fill_type_from, FillType.OuterOffset)
    out = []
    for pts_list, offs_list in conv:
        out.append((list(pts_list), list(offs_list)))
    return out

def count_line_vertices_separate(sep_lines):
    return sum(arr.shape[0] for arr in sep_lines)

def count_filled_vertices_outer_offset(outer_offset):
    pts_list, _ = outer_offset
    return sum(arr.shape[0] for arr in pts_list)

def make_grid(ny=32, nx=40, positive=False):
    y = np.linspace(-2.0, 2.0, ny)
    x = np.linspace(-3.0, 3.0, nx)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(X) * np.cos(Y) + 0.2 * X
    if positive:
        Z = Z - Z.min() + 1.0
    return x, y, Z

# ---------------- Tests ---------------- #

class TestContourPyAPI(unittest.TestCase):

    # ---------- Factory & basic generation ---------- #

    def test_factory_default_serial_and_basic_calls(self):
        _, _, Z = make_grid(8, 9)
        cg = contour_generator(z=Z)
        self.assertIsInstance(cg, SerialContourGenerator)

        lines = cg.lines(0.1)
        sep = lines_as_separate(lines, cg.line_type)
        self.assertIsInstance(sep, list)
        self.assertTrue(all(isinstance(a, np.ndarray) and a.shape[1] == 2 for a in sep))

        levels = [-0.5, 0.0, 0.5]
        ml = cg.multi_lines(levels)
        ml_sep = multi_lines_as_separate(ml, cg.line_type)
        single_sep = [lines_as_separate(cg.lines(lv), cg.line_type) for lv in levels]
        self.assertEqual([count_line_vertices_separate(s) for s in ml_sep],
                         [count_line_vertices_separate(s) for s in single_sep])

        filled = cg.filled(-0.2, 0.3)
        # Convert to a canonical representation for counting:
        filled_oo = filled_as_outer_offset(filled, cg.fill_type)
        self.assertGreater(count_filled_vertices_outer_offset(filled_oo), 0)

        mf = cg.multi_filled([-0.6, -0.2, 0.3])
        mf_oo = multi_filled_as_outer_offset(mf, cg.fill_type)
        self.assertEqual(len(mf_oo), 2)

    # ---------- x/y handling (1D & 2D) ---------- #

    def test_xy_1d_and_2d(self):
        x, y, Z = make_grid(10, 12)
        cg1 = contour_generator(x=x, y=y, z=Z)
        self.assertIsInstance(cg1, SerialContourGenerator)
        self.assertGreater(count_line_vertices_separate(
            lines_as_separate(cg1.lines(0.0), cg1.line_type)), 0)

        X2, Y2 = np.meshgrid(x, y)
        cg2 = contour_generator(x=X2, y=Y2, z=Z)
        self.assertIsInstance(cg2, SerialContourGenerator)
        self.assertGreater(count_line_vertices_separate(
            lines_as_separate(cg2.lines(0.0), cg2.line_type)), 0)

    def test_non_monotonic_x_not_checked(self):
        # ContourPy does not validate monotonicity of 1-D x/y; it "assumes" they are reasonable.
        # This should therefore NOT raise, but results are unspecified if non-monotonic.
        _, y, Z = make_grid(8, 8)
        x_nonmono = np.array([0.0, 1.0, 0.5, 2.0, 3.0, 4.0, 5.0, 6.0])
        cg = contour_generator(x=x_nonmono, y=y, z=Z)
        sep = lines_as_separate(cg.lines(0.0), cg.line_type)
        self.assertIsInstance(sep, list)

    # ---------- Properties and supports_* ---------- #

    def test_properties_and_supports(self):
        _, _, Z = make_grid(10, 10)
        cg = contour_generator(z=Z, quad_as_tri=True, z_interp=ZInterp.Linear)
        self.assertIsInstance(cg.fill_type, FillType)
        self.assertIsInstance(cg.line_type, LineType)
        self.assertIsInstance(cg.z_interp, ZInterp)
        self.assertTrue(cg.quad_as_tri)

        cls = type(cg)
        self.assertIsInstance(cls.default_fill_type, FillType)
        self.assertIsInstance(cls.default_line_type, LineType)
        for lt in [LineType.Separate, LineType.SeparateCode,
                   LineType.ChunkCombinedCode, LineType.ChunkCombinedOffset,
                   LineType.ChunkCombinedNan]:
            self.assertTrue(cls.supports_line_type(lt))
        for ft in [FillType.OuterCode, FillType.OuterOffset,
                   FillType.ChunkCombinedCode, FillType.ChunkCombinedOffset,
                   FillType.ChunkCombinedCodeOffset, FillType.ChunkCombinedOffsetOffset]:
            self.assertTrue(cls.supports_fill_type(ft))
        self.assertTrue(cls.supports_z_interp())
        self.assertTrue(cls.supports_quad_as_tri())
        self.assertFalse(cls.supports_threads())

    # ---------- Special level values and errors ---------- #

    def test_special_levels_and_errors(self):
        _, _, Z = make_grid(12, 12)
        cg = contour_generator(z=Z)

        for lv in [np.nan, np.inf, -np.inf]:
            sep = lines_as_separate(cg.lines(lv), cg.line_type)
            self.assertEqual(len(sep), 0)

        with self.assertRaises(ValueError):
            cg.filled(0.3, 0.3)
        with self.assertRaises(ValueError):
            cg.filled(0.4, 0.2)
        with self.assertRaises(ValueError):
            cg.multi_filled([0.1])
        with self.assertRaises(ValueError):
            cg.multi_filled([0.2, 0.1])
        with self.assertRaises(ValueError):
            cg.multi_filled([0.1, np.nan, 0.2])

        _ = cg.filled(-np.inf, 0.0)
        _ = cg.filled(0.0, np.inf)

    # ---------- LineType conversions & dechunk ---------- #

    def test_line_types_and_conversions(self):
        _, _, Z = make_grid(24, 24)
        cg = contour_generator(z=Z, line_type=LineType.ChunkCombinedOffset, chunk_count=(2, 3))
        lines_any = cg.lines(0.1)

        dechunked = dechunk_lines(lines_any, cg.line_type)
        sep = convert_lines(dechunked, LineType.ChunkCombinedOffset, LineType.Separate)
        self.assertGreater(count_line_vertices_separate(list(sep)), 0)

        for target in [LineType.Separate, LineType.SeparateCode,
                       LineType.ChunkCombinedCode, LineType.ChunkCombinedOffset,
                       LineType.ChunkCombinedNan]:
            converted = convert_lines(lines_any, cg.line_type, target)
            sep2 = convert_lines(converted, target, LineType.Separate)
            self.assertEqual(count_line_vertices_separate(list(sep2)),
                             count_line_vertices_separate(list(sep)))

        levels = [-0.5, 0.0, 0.5]
        ml_any = cg.multi_lines(levels)
        ml_dechunked = dechunk_multi_lines(ml_any, cg.line_type)
        ml_sep = convert_multi_lines(ml_dechunked, LineType.ChunkCombinedOffset, LineType.Separate)
        self.assertEqual([count_line_vertices_separate(list(g)) for g in ml_sep],
                         [count_line_vertices_separate(list(g))
                          for g in multi_lines_as_separate(ml_any, cg.line_type)])

    # ---------- FillType conversions & dechunk ---------- #

    def test_fill_types_conversions_and_errors(self):
        _, _, Z = make_grid(24, 24)

        # Start from a hole-aware non-chunked type (OuterOffset): we can convert widely.
        cg_outer = contour_generator(z=Z, fill_type=FillType.OuterOffset, chunk_count=(2, 2))
        filled_outer = cg_outer.filled(-0.3, 0.4)

        allowed_targets = [
            FillType.OuterCode,
            FillType.ChunkCombinedCode,
            FillType.ChunkCombinedOffset,
            FillType.ChunkCombinedCodeOffset,
            FillType.ChunkCombinedOffsetOffset,
        ]
        for target in allowed_targets:
            conv = convert_filled(filled_outer, cg_outer.fill_type, target)
            # For validation, if target is hole-aware, we can convert back to OuterOffset.
            if target in (FillType.OuterCode, FillType.ChunkCombinedCodeOffset, FillType.ChunkCombinedOffsetOffset):
                back = convert_filled(conv, target, FillType.OuterOffset)
                self.assertGreater(count_filled_vertices_outer_offset((list(back[0]), list(back[1]))), 0)
            else:
                # Non-hole-aware (ChunkCombinedCode/Offset) cannot legally convert back to Outer*.
                # Just ensure the forward conversion produced something well-formed (dechunk is a no-op here).
                self.assertTrue(isinstance(conv, tuple) and len(conv) in (2, 3))

        # Demonstrate dechunk keeps the same (chunked) type but merges chunks.
        cg_chunk = contour_generator(z=Z, fill_type=FillType.ChunkCombinedOffset, chunk_count=(2, 2))
        filled_chunk = cg_chunk.filled(-0.3, 0.4)
        dechunked = dechunk_filled(filled_chunk, cg_chunk.fill_type)
        self.assertEqual(len(dechunked[0]), 1)  # single merged chunk

        # Critically: conversion from hole-unaware to hole-aware is NOT supported and must raise.
        with self.assertRaises(ValueError):
            convert_filled(dechunked, FillType.ChunkCombinedOffset, FillType.OuterOffset)

        # And similarly for ChunkCombinedCode -> OuterOffset.
        cg_codes = contour_generator(z=Z, fill_type=FillType.ChunkCombinedCode, chunk_count=(2, 2))
        filled_codes = cg_codes.filled(-0.3, 0.4)
        with self.assertRaises(ValueError):
            convert_filled(filled_codes, FillType.ChunkCombinedCode, FillType.OuterOffset)

        # multi-filled path (using hole-aware to allow round-trip checks)
        levels = [-0.6, -0.1, 0.4]
        mf_any = cg_outer.multi_filled(levels)
        mf_dechunked = dechunk_multi_filled(mf_any, cg_outer.fill_type)  # no-op (not chunked)
        mf_oo = convert_multi_filled(mf_dechunked, FillType.OuterOffset, FillType.OuterOffset)
        counts = [count_filled_vertices_outer_offset((list(p), list(o))) for p, o in mf_oo]
        self.assertEqual(len(counts), len(levels) - 1)
        self.assertTrue(all(c >= 0 for c in counts))

    # ---------- Masked arrays & corner_mask ---------- #

    def test_masked_and_corner_mask(self):
        x, y, Z = make_grid(16, 16)
        M = ma.masked_array(Z, mask=False)
        M.mask[3, 3] = True
        cg0 = contour_generator(x=x, y=y, z=M, corner_mask=False)
        cg1 = contour_generator(x=x, y=y, z=M, corner_mask=True)
        self.assertFalse(cg0.corner_mask)
        self.assertTrue(cg1.corner_mask)
        for cg in (cg0, cg1):
            sep = lines_as_separate(cg.lines(0.0), cg.line_type)
            self.assertIsInstance(sep, list)

    # ---------- z-interp & quad_as_tri ---------- #

    def test_z_interp_log_and_quad_as_tri(self):
        x, y, Zpos = make_grid(20, 20, positive=True)
        cg_lin = contour_generator(x=x, y=y, z=Zpos, z_interp=ZInterp.Linear)
        lin_sep = lines_as_separate(cg_lin.lines(np.median(Zpos)), cg_lin.line_type)
        cg_log = contour_generator(x=x, y=y, z=Zpos, z_interp=ZInterp.Log)
        log_sep = lines_as_separate(cg_log.lines(np.median(Zpos)), cg_log.line_type)
        self.assertIsInstance(lin_sep, list)
        self.assertIsInstance(log_sep, list)

        cg_tri = contour_generator(x=x, y=y, z=Zpos, quad_as_tri=True)
        tri_sep = lines_as_separate(cg_tri.lines(np.median(Zpos)), cg_tri.line_type)
        self.assertIsInstance(tri_sep, list)

    # ---------- Chunking knobs ---------- #

    def test_chunking_knobs(self):
        _, _, Z = make_grid(30, 30)
        cg_sz = contour_generator(z=Z, chunk_size=(8, 10))
        self.assertEqual(cg_sz.chunk_size, (8, 10))

        cg_ct = contour_generator(z=Z, chunk_count=(3, 2))
        self.assertEqual(cg_ct.chunk_count, (3, 2))

        cg_tot = contour_generator(z=Z, total_chunk_count=4)
        yct, xct = cg_tot.chunk_count
        self.assertEqual(yct * xct, 4)

        with self.assertRaises((TypeError, ValueError)):
            contour_generator(z=Z, chunk_size=8, chunk_count=2)

    # ---------- Threaded algorithm ---------- #

    def test_threaded_generator(self):
        _, _, Z = make_grid(64, 64)
        cg = contour_generator(z=Z, name="threaded", chunk_count=(2, 2), thread_count=2)
        self.assertIsInstance(cg, ThreadedContourGenerator)
        self.assertTrue(type(cg).supports_threads())
        self.assertEqual(cg.thread_count, 2)
        ml = cg.multi_lines([-0.5, 0.0, 0.5])
        ml_sep = multi_lines_as_separate(ml, cg.line_type)
        self.assertEqual(len(ml_sep), 3)

    def test_max_threads(self):
        mt = max_threads()
        self.assertIsInstance(mt, int)
        self.assertGreaterEqual(mt, 1)

    # ---------- Legacy algorithm classes ---------- #

    def test_legacy_algorithms_exist(self):
        _, _, Z = make_grid(8, 8)
        cg05 = contour_generator(z=Z, name="mpl2005")
        cg14 = contour_generator(z=Z, name="mpl2014")
        self.assertIsInstance(cg05, Mpl2005ContourGenerator)
        self.assertIsInstance(cg14, Mpl2014ContourGenerator)
        for cg in (cg05, cg14):
            sep = lines_as_separate(cg.lines(0.0), cg.line_type)
            self.assertIsInstance(sep, list)

if __name__ == "__main__":
    unittest.main()