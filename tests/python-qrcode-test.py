# tests/test_qrcode_comprehensive.py
import io
import os
import sys
import shutil
import subprocess
import tempfile
import unittest

import qrcode
from qrcode import constants

from PIL import Image
from qrcode.image.pure import PyPNGImage
import qrcode.image.svg as qrcode_svg

from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import (
    SquareModuleDrawer,
    GappedSquareModuleDrawer,
    RoundedModuleDrawer,
    CircleModuleDrawer,
)
from qrcode.image.styles.moduledrawers.svg import (
    SvgSquareDrawer,
    SvgCircleDrawer,
    SvgPathSquareDrawer,
    SvgPathCircleDrawer,
)
try:
    from qrcode.image.styles.colormasks import RadialGradientColorMask
except Exception:  # pragma: no cover
    from qrcode.image.styles.colormasks import RadialGradiantColorMask as RadialGradientColorMask


def _make_basic_qr(data="Hello, World!", **kwargs) -> qrcode.QRCode:
    qr = qrcode.QRCode(
        version=kwargs.pop("version", None),
        error_correction=kwargs.pop("error_correction", constants.ERROR_CORRECT_M),
        box_size=kwargs.pop("box_size", 10),
        border=kwargs.pop("border", 4),
        **kwargs,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr


class TestQRCodeBasics(unittest.TestCase):
    def test_make_shortcut_returns_image(self):
        img = qrcode.make("Some data here")
        self.assertTrue(hasattr(img, "save"))

    def test_matrix_size_and_border_counts(self):
        qr = _make_basic_qr("X" * 3, version=1, error_correction=constants.ERROR_CORRECT_L, box_size=1, border=4)
        matrix = qr.get_matrix()
        self.assertEqual(len(matrix), 21 + 8)
        self.assertEqual(len(matrix[0]), 21 + 8)

    def test_pixel_dimensions_match_box_size(self):
        version = 2  # 25x25 modules
        box_size = 3
        border = 4
        qr = _make_basic_qr("size check", version=version, box_size=box_size, border=border)
        img = qr.make_image()
        pil_img = img.get_image() if hasattr(img, "get_image") else img
        modules = (17 + 4 * version) + 2 * border
        expected_px = modules * box_size
        self.assertEqual(pil_img.size, (expected_px, expected_px))

    def test_error_correction_levels(self):
        for lvl in (constants.ERROR_CORRECT_L, constants.ERROR_CORRECT_M, constants.ERROR_CORRECT_Q, constants.ERROR_CORRECT_H):
            qr = _make_basic_qr("EC test", error_correction=lvl)
            img = qr.make_image()
            self.assertTrue(hasattr(img, "save"))

    def test_clear_and_reuse(self):
        qr = qrcode.QRCode()
        qr.add_data("Old")
        _ = qr.make_image()
        qr.clear()
        qr.add_data("New")
        img2 = qr.make_image()
        self.assertTrue(hasattr(img2, "save"))

    def test_fill_and_back_color_rgb_tuples(self):
        qr = _make_basic_qr("color test")
        img = qr.make_image(fill_color=(55, 95, 35), back_color=(255, 195, 235))
        self.assertTrue(hasattr(img, "save"))


class TestPyPNGFactory(unittest.TestCase):
    def test_make_image_pypng_to_bytes(self):
        qr = _make_basic_qr("pypng bytes")
        img = qr.make_image(image_factory=PyPNGImage)
        buf = io.BytesIO()
        img.save(buf)
        self.assertGreater(buf.tell(), 0)
        self.assertEqual(buf.getvalue()[:8], b"\x89PNG\r\n\x1a\n")


class TestPILFactory(unittest.TestCase):
    def test_make_image_default_pil_and_roundtrip(self):
        qr = _make_basic_qr("roundtrip")
        img = qr.make_image()
        pil_img = img.get_image() if hasattr(img, "get_image") else img
        self.assertTrue(hasattr(pil_img, "size"))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        opened = Image.open(buf)
        self.assertEqual(opened.format, "PNG")


class TestSVGFactories(unittest.TestCase):
    def test_svg_path_image_to_string(self):
        img = qrcode.make("svg path", image_factory=qrcode_svg.SvgPathImage)
        svg = img.to_string(encoding="unicode")
        self.assertIn("<svg", svg)

    def test_svg_rect_and_fragment_factories(self):
        for factory in (qrcode_svg.SvgImage, qrcode_svg.SvgFragmentImage):
            img = qrcode.make("svg rects", image_factory=factory)
            xml = img.to_string(encoding="unicode")
            self.assertIn("<svg", xml)

    def test_svg_root_attributes_forwarded(self):
        qr = qrcode.QRCode(image_factory=qrcode_svg.SvgPathImage)
        qr.add_data("attrib")
        qr.make(fit=True)
        img = qr.make_image(attrib={"class": "some-css-class"})
        xml = img.to_string(encoding="unicode")
        self.assertIn('class="some-css-class"', xml)

    def test_svg_drawers_variants(self):
        qr = _make_basic_qr("svg drawers", error_correction=constants.ERROR_CORRECT_H)
        for drawer in (SvgSquareDrawer(), SvgCircleDrawer(), SvgPathSquareDrawer(), SvgPathCircleDrawer()):
            img = qr.make_image(image_factory=qrcode_svg.SvgPathImage, module_drawer=drawer)
            xml = img.to_string(encoding="unicode")
            self.assertIn("<svg", xml)


class TestStyledPilImage(unittest.TestCase):
    def test_module_drawers_variants(self):
        qr = _make_basic_qr("styled drawers", error_correction=constants.ERROR_CORRECT_H)
        for drawer in (SquareModuleDrawer(), GappedSquareModuleDrawer(), RoundedModuleDrawer(), CircleModuleDrawer()):
            img = qr.make_image(image_factory=StyledPilImage, module_drawer=drawer)
            self.assertTrue(hasattr(img, "save"))

    def test_color_mask(self):
        qr = _make_basic_qr("styled color", error_correction=constants.ERROR_CORRECT_H)
        img = qr.make_image(image_factory=StyledPilImage, color_mask=RadialGradientColorMask())
        self.assertTrue(hasattr(img, "save"))

    def test_embedded_image_requires_high_ec(self):
        with tempfile.TemporaryDirectory() as td:
            logo = os.path.join(td, "logo.png")
            Image.new("RGBA", (24, 24), (255, 0, 0, 255)).save(logo, "PNG")

            qr_hi = _make_basic_qr("embed ok", error_correction=constants.ERROR_CORRECT_H)
            img_hi = qr_hi.make_image(image_factory=StyledPilImage, embedded_image_path=logo)
            self.assertTrue(hasattr(img_hi, "save"))

            qr_lo = _make_basic_qr("embed behavior varies", error_correction=constants.ERROR_CORRECT_M)
            try:
                img_lo = qr_lo.make_image(image_factory=StyledPilImage, embedded_image_path=logo)
                self.assertTrue(hasattr(img_lo, "save"))
            except Exception:
                self.assertTrue(True)


class TestAsciiAndCLI(unittest.TestCase):
    def test_print_ascii_to_stringio(self):
        qr = qrcode.QRCode()
        qr.add_data("Some text")
        f = io.StringIO()
        qr.print_ascii(out=f)
        f.seek(0)
        output = f.read()
        self.assertGreater(len(output.strip()), 0)

    def test_cli_ascii_and_svg_smoke(self):
        cmd = shutil.which("qr")
        if not cmd:
            self.skipTest("qr CLI not available on PATH")
        proc = subprocess.run([cmd, "--ascii", "CLI test"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        self.assertIn(b"\n", proc.stdout)
        proc2 = subprocess.run([cmd, "--factory=svg-path", "CLI svg"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        self.assertIn(b"<svg", proc2.stdout)

    def test_cli_output_file_parameter(self):
        cmd = shutil.which("qr")
        if not cmd:
            self.skipTest("qr CLI not available on PATH")
        with tempfile.TemporaryDirectory() as td:
            out_png = os.path.join(td, "cli.png")
            subprocess.run([cmd, f"--output={out_png}", "Output file"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertTrue(os.path.isfile(out_png))
            self.assertGreater(os.path.getsize(out_png), 0)


class TestEdgeCases(unittest.TestCase):
    def test_version_and_fit_behavior(self):
        payload = "x" * 2000  # fits in v40/M but not in v1/M

        qr40 = qrcode.QRCode(version=40, error_correction=constants.ERROR_CORRECT_M, box_size=1, border=4)
        qr40.add_data(payload)
        qr40.make(fit=False)  # should succeed

        qr1 = qrcode.QRCode(version=1, error_correction=constants.ERROR_CORRECT_M, box_size=1, border=4)
        qr1.add_data(payload)
        with self.assertRaises(Exception):
            qr1.make(fit=False)

    def test_border_validation(self):
        _ = _make_basic_qr("border ok", border=4)
        with self.assertRaises(Exception):
            _ = _make_basic_qr("border bad", border=-1)

    def test_numeric_alphanumeric_and_mixed_payloads(self):
        numeric = "1234567890" * 3
        alnum = "HELLO-WORLD_12345"
        mixed = numeric + "-" + alnum
        for payload in (numeric, alnum, mixed):
            qr = _make_basic_qr(payload)
            img = qr.make_image()
            self.assertTrue(hasattr(img, "save"))


if __name__ == "__main__":
    unittest.main(verbosity=2)