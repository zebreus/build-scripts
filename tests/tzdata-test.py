import io
import os
import re
import unittest
from datetime import datetime, timedelta, timezone

# These imports are the primary surfaces tzdata is designed for
import pkgutil
from importlib import resources

import tzdata  # the package under test


def iana_key_to_resource(key: str):
    """
    Convert an IANA key like "America/New_York" to an importlib.resources
    (package, resource) pair. Also supports top-level keys like "UTC" or "Zulu".
    """
    if "/" not in key:
        # Top-level resource inside tzdata.zoneinfo/
        return "tzdata.zoneinfo", key

    package_loc, resource = key.rsplit("/", 1)
    package = "tzdata.zoneinfo." + package_loc.replace("/", ".")
    return package, resource


class TestTzdataPackageStructure(unittest.TestCase):
    def test_iana_version_exists_and_looks_like_tzdb(self):
        # IANA TZDB versions typically look like "2025a" or "2024b"
        self.assertTrue(hasattr(tzdata, "IANA_VERSION"))
        self.assertIsInstance(tzdata.IANA_VERSION, str)
        self.assertRegex(tzdata.IANA_VERSION, r"^\d{4}[a-z]$")

    def test_zones_file_exists_and_is_nonempty(self):
        # tzdata.zones is a newline-delimited list of IANA keys
        text = resources.files("tzdata").joinpath("zones").read_text(encoding="utf-8")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
        self.assertGreater(len(lines), 100)  # should be many zones available
        # Spot-check some very common zones
        self.assertIn("UTC", lines)
        self.assertIn("Etc/UTC", lines)  # often used canonical key
        self.assertIn("America/New_York", lines)
        self.assertIn("Europe/Berlin", lines)
        # Keep list for other tests
        self.zones_list = lines  # not relied upon by other tests directly

    def test_zoneinfo_package_and_core_resources_exist(self):
        # tzdata.zoneinfo should contain at least tzdata.zi and zone.tab (text resources)
        zi_bytes = resources.files("tzdata.zoneinfo").joinpath("tzdata.zi").read_bytes()
        zone_tab = resources.files("tzdata.zoneinfo").joinpath("zone.tab").read_text(encoding="utf-8")

        self.assertGreater(len(zi_bytes), 1000)
        self.assertIn("\n", zone_tab)
        # Optional: the tzdata.zi text usually embeds the version line; check presence of version string
        zi_text = zi_bytes.decode("utf-8", errors="replace")
        self.assertIn(tzdata.IANA_VERSION, zi_text)

    def test_pkgutil_get_data_also_works(self):
        # tzdata supports access via pkgutil.get_data too
        data = pkgutil.get_data("tzdata.zoneinfo", "tzdata.zi")
        self.assertIsNotNone(data)
        self.assertGreater(len(data), 1000)

    def test_open_binary_returns_tzif_header_for_sample_zones(self):
        # Validate the first four bytes are "TZif" for several zones
        sample_keys = [
            "UTC",
            "Etc/UTC",
            "America/New_York",
            "Europe/Berlin",
            "America/Indiana/Indianapolis",  # nested package path
            "Africa/Abidjan",
            "Asia/Tokyo",
        ]
        for key in sample_keys:
            with self.subTest(zone=key):
                pkg, res = iana_key_to_resource(key)
                with resources.open_binary(pkg, res) as f:
                    header = f.read(4)
                self.assertEqual(header, b"TZif")

    def test_open_binary_raises_for_missing_zone(self):
        with self.assertRaises(FileNotFoundError):
            with resources.open_binary("tzdata.zoneinfo.America", "Not_A_Real_City"):
                pass


class TestZoneInfoInteroperability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import here to allow running tests on Python 3.9+
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # noqa: F401

    def _open_zoneinfo(self, key: str):
        """
        Open a tzdata resource and construct a ZoneInfo from its binary stream.
        This ensures we are using tzdata's bundled data regardless of system TZDB.
        """
        from zoneinfo import ZoneInfo

        pkg, res = iana_key_to_resource(key)
        with resources.open_binary(pkg, res) as f:
            # ZoneInfo.from_file consumes a file-like of a TZif binary
            zi = ZoneInfo.from_file(f)
        return zi

    def test_utc_behavior(self):
        zi = self._open_zoneinfo("Etc/UTC")
        dt = datetime(2020, 1, 1, 0, 0, tzinfo=zi)
        self.assertEqual(dt.utcoffset(), timedelta(0))
        self.assertEqual(dt.tzname(), "UTC")

        # Conversions should be stable and reversible
        naive = dt.astimezone(timezone.utc).replace(tzinfo=None)
        self.assertEqual(naive, datetime(2020, 1, 1, 0, 0))

    def test_new_york_dst_transitions(self):
        zi = self._open_zoneinfo("America/New_York")

        winter = datetime(2020, 1, 15, 12, 0, tzinfo=zi)
        summer = datetime(2020, 7, 15, 12, 0, tzinfo=zi)

        self.assertEqual(winter.utcoffset(), timedelta(hours=-5))
        self.assertEqual(winter.tzname(), "EST")

        self.assertEqual(summer.utcoffset(), timedelta(hours=-4))
        self.assertEqual(summer.tzname(), "EDT")

    def test_berlin_dst_transitions(self):
        zi = self._open_zoneinfo("Europe/Berlin")

        winter = datetime(2020, 1, 15, 12, 0, tzinfo=zi)
        summer = datetime(2020, 7, 15, 12, 0, tzinfo=zi)

        self.assertEqual(winter.utcoffset(), timedelta(hours=1))
        self.assertEqual(winter.tzname(), "CET")

        self.assertEqual(summer.utcoffset(), timedelta(hours=2))
        self.assertEqual(summer.tzname(), "CEST")

    def test_roundtrip_with_from_file_multiple_times(self):
        # Ensure multiple instantiations from tzdata resources work
        keys = ["UTC", "Etc/UTC", "Asia/Tokyo", "America/New_York"]
        for key in keys:
            with self.subTest(zone=key):
                zi1 = self._open_zoneinfo(key)
                zi2 = self._open_zoneinfo(key)
                self.assertEqual(zi1.key, zi2.key)  # ZoneInfo records the IANA key
                # Same offset at a fixed instant
                instant = datetime(2021, 3, 1, 0, 0, tzinfo=zi1)
                self.assertEqual(instant.utcoffset(), datetime(2021, 3, 1, 0, 0, tzinfo=zi2).utcoffset())

    def test_invalid_file_rejected(self):
        from zoneinfo import ZoneInfo

        # Feed a non-TZif buffer; ZoneInfo should raise
        bad = io.BytesIO(b"NOTZ")
        with self.assertRaises(Exception):
            ZoneInfo.from_file(bad)


class TestZonesIndexIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = resources.files("tzdata").joinpath("zones").read_text(encoding="utf-8")
        cls.zones = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]

    def test_sampled_zones_in_index_openable(self):
        # Sample a handful across different top-level regions and nested paths
        samples = [
            "Africa/Abidjan",
            "America/Adak",
            "America/Argentina/Buenos_Aires",
            "America/Indiana/Indianapolis",
            "Antarctica/McMurdo",
            "Asia/Kolkata",
            "Australia/Sydney",
            "Europe/London",
            "Pacific/Auckland",
            "Pacific/Honolulu",
            "Atlantic/Azores",
            "Indian/Maldives",
            "UTC",
            "Etc/GMT+0",
        ]

        for key in samples:
            with self.subTest(zone=key):
                self.assertIn(key, self.zones, f"{key} not present in tzdata.zones")
                pkg, res = iana_key_to_resource(key)
                with resources.open_binary(pkg, res) as f:
                    self.assertEqual(f.read(4), b"TZif")

    def test_zones_index_has_only_valid_keys_format(self):
        pat = re.compile(r"^[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*$")
        bad = [z for z in self.zones if not pat.match(z)]
        self.assertFalse(bad, f"Invalid zone key format(s): {bad[:5]}")

    def test_no_duplicate_zone_entries(self):
        self.assertEqual(len(self.zones), len(set(self.zones)))


if __name__ == "__main__":
    unittest.main()