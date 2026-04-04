"""
test_resource.py

Tests for _resource.py — PyInstaller-safe resource path resolver.

Run with:
    python -m unittest test_resource -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _resource import resource_path


class TestResourcePath(unittest.TestCase):
    """Tests for resource_path() in both normal (source) and frozen modes."""

    def tearDown(self):
        # Always clean up injected _MEIPASS so it doesn't bleed into other tests
        sys.modules.pop("_resource", None)  # bust any cached reference
        if hasattr(sys, "_MEIPASS"):
            del sys._MEIPASS

    # ── Return type ──────────────────────────────────────────────────────────

    def test_returns_path_object(self):
        result = resource_path("anything")
        self.assertIsInstance(result, Path)

    # ── Non-frozen mode (normal Python execution) ─────────────────────────

    def test_nonfrozen_is_absolute(self):
        result = resource_path("assets/icons")
        self.assertTrue(result.is_absolute())

    def test_nonfrozen_resolves_from_package_root(self):
        # Without sys._MEIPASS, base should be the directory containing _resource.py
        expected_base = Path(__file__).parent  # same dir as _resource.py
        result = resource_path("assets/icons")
        self.assertEqual(result, expected_base / "assets" / "icons")

    def test_nonfrozen_subdirectory_preserved(self):
        result = resource_path("a/b/c")
        parts = result.parts
        self.assertEqual(parts[-3:], ("a", "b", "c"))

    def test_known_asset_exists_in_dev_mode(self):
        # In development (non-frozen) mode the real icon should be on disk
        icon_path = resource_path("assets/icons/plus.png")
        self.assertTrue(icon_path.exists(), f"Expected icon at {icon_path}")

    # ── Frozen mode (PyInstaller — sys._MEIPASS injected) ─────────────────

    def test_frozen_uses_meipass_root(self):
        sys._MEIPASS = "/tmp/fake_meipass"
        # Re-import to pick up the new _MEIPASS
        import importlib, _resource as res
        importlib.reload(res)
        result = res.resource_path("assets/icons")
        self.assertEqual(str(result), "/tmp/fake_meipass/assets/icons")

    def test_frozen_subdirectory_preserved(self):
        sys._MEIPASS = "/tmp/bundle"
        import importlib, _resource as res
        importlib.reload(res)
        result = res.resource_path("x/y/z")
        self.assertEqual(str(result), "/tmp/bundle/x/y/z")

    def test_meipass_isolation_between_tests(self):
        # Confirm _MEIPASS injected in one test doesn't bleed into the next
        self.assertFalse(hasattr(sys, "_MEIPASS"),
                         "_MEIPASS should have been cleaned up in tearDown")


if __name__ == "__main__":
    unittest.main()
