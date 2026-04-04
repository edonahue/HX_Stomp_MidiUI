"""
test_icon_manager.py

Tests for icon_manager.py: get_icon() and icon_btn() fallback behaviour.
No display is required — the test stubs out customtkinter and tkinter so
CTkImage objects can be constructed headlessly using PIL alone.

Run with:
    python -m unittest test_icon_manager -v
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Tkinter / customtkinter stub (same pattern as test_hlx_builder.py)
# ---------------------------------------------------------------------------
class _UIStub:
    def __init__(self, *a, **kw): pass
    def __getattr__(self, n): return lambda *a, **kw: None


def _make_ui_module(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    def _getattr(attr):
        return type(attr, (_UIStub,), {})
    m.__getattr__ = _getattr
    return m


for _mod_name in ("tkinter", "tkinter.messagebox", "tkinter.filedialog",
                  "tkinter.font", "_tkinter"):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _make_ui_module(_mod_name)

# CTkImage stub: stores the constructor args so tests can inspect them.
# Named "CTkImage" so __class__.__name__ matches the real customtkinter class
# and get_icon() test assertions on class name pass in headless environments.
class CTkImage(_UIStub):
    def __init__(self, *a, **kw):
        self._args = a
        self._kwargs = kw

# CTkButton stub: stores kwargs so tests can inspect text= and image=
class CTkButton(_UIStub):
    def __init__(self, *a, **kw):
        self._args = a
        self._kwargs = kw

_ctk_stub = _make_ui_module("customtkinter")
_ctk_stub.CTkImage = CTkImage
_ctk_stub.CTkButton = CTkButton
sys.modules["customtkinter"] = _ctk_stub

# ---------------------------------------------------------------------------
# Now import the module under test
# ---------------------------------------------------------------------------
import icon_manager  # noqa: E402  (must come after stubs)
from icon_manager import get_icon, icon_btn, MD, LG, SM


class TestGetIcon(unittest.TestCase):
    """Tests for icon_manager.get_icon()."""

    def setUp(self):
        # Clear lru_cache before every test so results are independent
        get_icon.cache_clear()

    # ------------------------------------------------------------------
    # Fallback paths
    # ------------------------------------------------------------------
    def test_empty_name_returns_none(self):
        result = get_icon("")
        self.assertIsNone(result)

    def test_nonexistent_icon_returns_none(self):
        result = get_icon("this-icon-does-not-exist-xyz")
        self.assertIsNone(result)

    def test_pil_unavailable_returns_none(self):
        """When PIL is not installed get_icon() should return None gracefully."""
        with patch.object(icon_manager, "_PIL_OK", False):
            get_icon.cache_clear()
            result = get_icon("plus")
        get_icon.cache_clear()
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    def test_known_good_icon_returns_ctk_image(self):
        """'plus.png' exists in assets/icons/ — should return a CTkImage."""
        result = get_icon("plus")
        self.assertIsNotNone(result)
        self.assertEqual(result.__class__.__name__, "CTkImage")

    def test_known_good_icon_with_lg_size(self):
        result = get_icon("plus", LG)
        self.assertIsNotNone(result)

    def test_known_good_icon_with_sm_size(self):
        result = get_icon("plus", SM)
        self.assertIsNotNone(result)

    def test_speaker_high_icon_returns_ctk_image(self):
        result = get_icon("speaker-high")
        self.assertIsNotNone(result)

    def test_waves_icon_returns_ctk_image(self):
        result = get_icon("waves")
        self.assertIsNotNone(result)

    def test_wave_sine_icon_returns_ctk_image(self):
        result = get_icon("wave-sine")
        self.assertIsNotNone(result)

    def test_sliders_horizontal_icon_returns_ctk_image(self):
        result = get_icon("sliders-horizontal")
        self.assertIsNotNone(result)

    def test_speaker_none_icon_returns_ctk_image(self):
        result = get_icon("speaker-none")
        self.assertIsNotNone(result)

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------
    def test_same_args_returns_cached_object(self):
        """Calling get_icon twice with the same args must return the identical object."""
        first = get_icon("plus", MD)
        second = get_icon("plus", MD)
        self.assertIs(first, second)

    def test_different_sizes_return_different_objects(self):
        """Different (name, size) pairs must produce distinct CTkImage instances."""
        small = get_icon("plus", SM)
        large = get_icon("plus", LG)
        # Both should succeed, and be different objects
        self.assertIsNotNone(small)
        self.assertIsNotNone(large)
        self.assertIsNot(small, large)

    def test_cache_info_reports_hits(self):
        """After two calls with the same args, cache_info().hits should be >= 1."""
        get_icon("plus", MD)
        get_icon("plus", MD)
        info = get_icon.cache_info()
        self.assertGreaterEqual(info.hits, 1)


class TestIconBtn(unittest.TestCase):
    """Tests for icon_manager.icon_btn().

    We patch icon_manager.ctk.CTkButton so we can inspect the kwargs passed
    to it regardless of which tkinter/customtkinter stub is active.
    """

    def setUp(self):
        get_icon.cache_clear()

    def _run_icon_btn(self, icon_name, text="", size=MD, **kwargs):
        """Call icon_btn() with a patched CTkButton, return (mock_class, result)."""
        from unittest.mock import MagicMock, call
        mock_cls = MagicMock(name="CTkButton")
        with patch.object(icon_manager.ctk, "CTkButton", mock_cls):
            result = icon_btn(None, icon_name, text, size, **kwargs)
        return mock_cls, result

    def test_known_good_icon_sets_image(self):
        """When the icon file exists CTkButton should receive a non-None image= kwarg."""
        mock_cls, _ = self._run_icon_btn("plus", "Label")
        _, call_kwargs = mock_cls.call_args
        self.assertIn("image", call_kwargs)
        self.assertIsNotNone(call_kwargs["image"])

    def test_known_good_icon_with_text_uses_left_compound(self):
        mock_cls, _ = self._run_icon_btn("plus", "Label")
        _, call_kwargs = mock_cls.call_args
        self.assertEqual(call_kwargs.get("compound"), "left")

    def test_known_good_icon_no_text_uses_center_compound(self):
        mock_cls, _ = self._run_icon_btn("plus", "")
        _, call_kwargs = mock_cls.call_args
        self.assertEqual(call_kwargs.get("compound"), "center")

    def test_missing_icon_fallback_no_image_kwarg(self):
        """Missing icon → CTkButton called without an image= kwarg."""
        mock_cls, _ = self._run_icon_btn("no-such-icon-xyz", "Fallback")
        _, call_kwargs = mock_cls.call_args
        self.assertNotIn("image", call_kwargs)

    def test_missing_icon_fallback_preserves_text(self):
        mock_cls, _ = self._run_icon_btn("no-such-icon-xyz", "Fallback Text")
        _, call_kwargs = mock_cls.call_args
        self.assertEqual(call_kwargs.get("text"), "Fallback Text")

    def test_extra_kwargs_forwarded(self):
        mock_cls, _ = self._run_icon_btn("plus", "Btn", fg_color="red", corner_radius=8)
        _, call_kwargs = mock_cls.call_args
        self.assertEqual(call_kwargs.get("fg_color"), "red")
        self.assertEqual(call_kwargs.get("corner_radius"), 8)

    def test_pil_unavailable_produces_plain_button(self):
        """With PIL unavailable get_icon returns None → icon_btn falls back to text."""
        with patch.object(icon_manager, "_PIL_OK", False):
            get_icon.cache_clear()
            mock_cls, _ = self._run_icon_btn("plus", "No PIL")
        get_icon.cache_clear()
        _, call_kwargs = mock_cls.call_args
        self.assertNotIn("image", call_kwargs)
        self.assertEqual(call_kwargs.get("text"), "No PIL")


if __name__ == "__main__":
    unittest.main()
