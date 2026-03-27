"""
test_midi_and_utils.py

Test suite for midi_interface.py, main.py (MockHXStompMidi),
soundboard_ui.py color utilities, and llm_generator.py config I/O.

Run with:
    python -m unittest test_midi_and_utils -v
"""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Stub mido before midi_interface is imported (no real MIDI hardware)
# ---------------------------------------------------------------------------

_mido_stub = types.ModuleType("mido")
_mido_stub.get_output_names = lambda: ["FakeMidi Port 1", "Another Port"]
_mido_stub.open_output = MagicMock(return_value=MagicMock(closed=False))
_mido_stub.Message = MagicMock(side_effect=lambda *a, **kw: kw)
_mido_stub.ports = types.SimpleNamespace(BaseOutput=object)
sys.modules["mido"] = _mido_stub

from midi_interface import (
    HXStompMidi,
    CC_BANK_MSB, CC_BANK_LSB, CC_EXP1, CC_EXP2,
    CC_FS1, CC_FS7, CC_LOOP_REC, CC_LOOP_PLAY, CC_TUNER, CC_SNAPSHOT,
    SNAPSHOT_NEXT, SNAPSHOT_PREV, _FS_CC,
)

# ---------------------------------------------------------------------------
# Stub tkinter / customtkinter before any UI module is imported
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
                  "customtkinter", "_tkinter"):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _make_ui_module(_mod_name)

# soundboard_ui imports tkinter at module level — import after stub
from soundboard_ui import _contrast_color, _adjust_brightness, _muted_color

# main.py imports soundboard_ui at module level — import after stub
from main import MockHXStompMidi

# llm_generator config functions
import llm_generator
from llm_generator import load_config, save_config


# ===========================================================================
# Group D: CC constants
# ===========================================================================

class TestCCConstants(unittest.TestCase):

    def test_cc_bank_msb(self):
        self.assertEqual(CC_BANK_MSB, 0)

    def test_cc_bank_lsb(self):
        self.assertEqual(CC_BANK_LSB, 32)

    def test_cc_exp1(self):
        self.assertEqual(CC_EXP1, 1)

    def test_cc_snapshot(self):
        self.assertEqual(CC_SNAPSHOT, 69)

    def test_cc_tuner(self):
        self.assertEqual(CC_TUNER, 68)

    def test_fs_cc_no_fs6(self):
        self.assertNotIn(6, _FS_CC)

    def test_fs7_maps_to_54(self):
        self.assertEqual(_FS_CC[7], 54)

    def test_snapshot_nav_values(self):
        self.assertEqual(SNAPSHOT_NEXT, 8)
        self.assertEqual(SNAPSHOT_PREV, 9)


# ===========================================================================
# Group E: HXStompMidi validation (no hardware)
# ===========================================================================

def _connected_hxi() -> HXStompMidi:
    """Return an HXStompMidi with a faked-open port (no real MIDI)."""
    hxi = HXStompMidi()
    hxi._port = MagicMock()
    hxi._port.closed = False
    return hxi


class TestHXStompMidiValidation(unittest.TestCase):

    def test_require_connection_raises(self):
        hxi = HXStompMidi()
        with self.assertRaises(RuntimeError):
            hxi._require_connection()

    def test_is_connected_false_fresh(self):
        hxi = HXStompMidi()
        self.assertFalse(hxi.is_connected)

    def test_port_name_empty_fresh(self):
        hxi = HXStompMidi()
        self.assertEqual(hxi.port_name, "")

    def test_select_snapshot_invalid_raises(self):
        hxi = _connected_hxi()
        hxi.send_cc = MagicMock()
        with self.assertRaises(ValueError):
            hxi.select_snapshot(10)

    def test_select_snapshot_valid_max(self):
        hxi = _connected_hxi()
        hxi.send_cc = MagicMock()
        hxi.select_snapshot(9)  # SNAPSHOT_PREV — should not raise
        hxi.send_cc.assert_called_once()

    def test_select_snapshot_zero_valid(self):
        hxi = _connected_hxi()
        hxi.send_cc = MagicMock()
        hxi.select_snapshot(0)  # should not raise

    def test_press_footswitch_invalid_fs6_raises(self):
        hxi = _connected_hxi()
        hxi.send_cc = MagicMock()
        with self.assertRaises(ValueError):
            hxi.press_footswitch(6)

    def test_press_footswitch_valid_fs7_sends_correct_cc(self):
        hxi = _connected_hxi()
        calls = []
        hxi.send_cc = lambda ctrl, val: calls.append((ctrl, val))
        hxi.press_footswitch(7)
        self.assertEqual(calls, [(54, 127)])

    def test_press_footswitch_valid_fs1(self):
        hxi = _connected_hxi()
        calls = []
        hxi.send_cc = lambda ctrl, val: calls.append((ctrl, val))
        hxi.press_footswitch(1)
        self.assertEqual(calls[0][0], CC_FS1)
        self.assertEqual(calls[0][1], 127)

    def test_set_exp1_out_of_range_raises(self):
        hxi = _connected_hxi()
        hxi.send_cc = MagicMock()
        with self.assertRaises(ValueError):
            hxi.set_exp1(200)

    def test_set_exp1_negative_raises(self):
        hxi = _connected_hxi()
        hxi.send_cc = MagicMock()
        with self.assertRaises(ValueError):
            hxi.set_exp1(-1)

    def test_set_exp2_out_of_range_raises(self):
        hxi = _connected_hxi()
        hxi.send_cc = MagicMock()
        with self.assertRaises(ValueError):
            hxi.set_exp2(128)

    def test_set_exp1_boundary_127_valid(self):
        hxi = _connected_hxi()
        hxi.send_cc = MagicMock()
        hxi.set_exp1(127)  # should not raise
        hxi.send_cc.assert_called_once()

    def test_disconnect_clears_port(self):
        hxi = _connected_hxi()
        hxi.disconnect()
        self.assertFalse(hxi.is_connected)
        self.assertEqual(hxi.port_name, "")


# ===========================================================================
# Group F: HXStompMidi tuner state machine
# ===========================================================================

class TestHXStompMidiTuner(unittest.TestCase):

    def setUp(self):
        self.hxi = _connected_hxi()
        self.hxi.send_cc = MagicMock()

    def test_tuner_starts_false(self):
        hxi = HXStompMidi()
        self.assertFalse(hxi.tuner_active)

    def test_toggle_tuner_returns_true_on_first_toggle(self):
        result = self.hxi.toggle_tuner()
        self.assertTrue(result)

    def test_toggle_tuner_state_flips(self):
        self.hxi.toggle_tuner()
        self.assertTrue(self.hxi.tuner_active)
        self.hxi.toggle_tuner()
        self.assertFalse(self.hxi.tuner_active)

    def test_set_tuner_on_sends_one_cc(self):
        # starts False; set True → should call toggle once
        self.hxi.set_tuner(True)
        self.assertEqual(self.hxi.send_cc.call_count, 1)
        self.assertTrue(self.hxi.tuner_active)

    def test_set_tuner_noop_when_already_correct(self):
        # starts False; set False → no CC sent
        self.hxi.set_tuner(False)
        self.hxi.send_cc.assert_not_called()

    def test_toggle_twice_sends_cc_twice(self):
        self.hxi.toggle_tuner()
        self.hxi.toggle_tuner()
        self.assertEqual(self.hxi.send_cc.call_count, 2)


# ===========================================================================
# Group G: MockHXStompMidi API parity & behavior
# ===========================================================================

class TestMockHXStompMidi(unittest.TestCase):

    def setUp(self):
        self.mock = MockHXStompMidi()

    def test_list_ports_returns_list(self):
        ports = MockHXStompMidi.list_output_ports()
        self.assertIsInstance(ports, list)
        self.assertGreater(len(ports), 0)

    def test_find_hx_port_returns_string(self):
        port = MockHXStompMidi.find_hx_port()
        self.assertIsNotNone(port)
        self.assertIsInstance(port, str)

    def test_connect_sets_connected(self):
        self.mock.connect("TestPort")
        self.assertTrue(self.mock.is_connected)
        self.assertEqual(self.mock.port_name, "TestPort")

    def test_disconnect_clears_state(self):
        self.mock.connect("TestPort")
        self.mock.disconnect()
        self.assertFalse(self.mock.is_connected)
        self.assertEqual(self.mock.port_name, "")

    def test_is_connected_false_initially(self):
        self.assertFalse(self.mock.is_connected)

    def test_tuner_toggle_returns_bool(self):
        result = self.mock.toggle_tuner()
        self.assertIsInstance(result, bool)
        self.assertTrue(result)
        self.assertTrue(self.mock.tuner_active)

    def test_set_tuner_idempotent(self):
        # Patch toggle_tuner to count calls
        call_count = []
        original = self.mock.toggle_tuner
        def counting_toggle():
            call_count.append(1)
            return original()
        self.mock.toggle_tuner = counting_toggle

        self.mock.set_tuner(True)   # should call toggle once (False→True)
        self.mock.set_tuner(True)   # already True, no-op
        self.assertEqual(len(call_count), 1)

    def test_connect_first_available(self):
        self.mock.connect_first_available()
        self.assertTrue(self.mock.is_connected)

    def test_context_manager_disconnects(self):
        with MockHXStompMidi() as m:
            m.connect("CtxPort")
            self.assertTrue(m.is_connected)
        self.assertFalse(m.is_connected)

    def test_tuner_starts_false(self):
        self.assertFalse(self.mock.tuner_active)

    def test_select_preset_and_snapshot_runs(self):
        # No exceptions; just exercises the path
        self.mock.select_preset_and_snapshot(10, snapshot=2)

    def test_next_snapshot_delegates(self):
        # next_snapshot should call select_snapshot(8)
        called = []
        self.mock.select_snapshot = lambda s: called.append(s)
        self.mock.next_snapshot()
        self.assertEqual(called, [8])

    def test_prev_snapshot_delegates(self):
        called = []
        self.mock.select_snapshot = lambda s: called.append(s)
        self.mock.prev_snapshot()
        self.assertEqual(called, [9])


# ===========================================================================
# Group H: Color utility functions
# ===========================================================================

class TestContrastColor(unittest.TestCase):

    def test_white_bg_returns_black(self):
        self.assertEqual(_contrast_color("#ffffff"), "#000000")

    def test_black_bg_returns_white(self):
        self.assertEqual(_contrast_color("#000000"), "#ffffff")

    def test_mid_blue_returns_black(self):
        # #4A90D9: r=74, g=144, b=217 → luminance ≈ 131 > 128 → black text
        self.assertEqual(_contrast_color("#4A90D9"), "#000000")

    def test_bright_yellow_returns_black(self):
        # #ffff00 luminance ≈ 237 → > 128 → black
        self.assertEqual(_contrast_color("#ffff00"), "#000000")

    def test_invalid_hex_returns_white(self):
        # Invalid hex chars (length-6 but non-hex digits) now safely return white
        self.assertEqual(_contrast_color("#xyz123"), "#ffffff")

    def test_too_short_hex_returns_white(self):
        self.assertEqual(_contrast_color("#fff"), "#ffffff")


class TestAdjustBrightness(unittest.TestCase):

    def test_darken_white_by_half(self):
        result = _adjust_brightness("#ffffff", 0.5)
        self.assertEqual(result, "#7f7f7f")

    def test_darken_black_stays_black(self):
        result = _adjust_brightness("#000000", 0.5)
        self.assertEqual(result, "#000000")

    def test_factor_1_unchanged(self):
        result = _adjust_brightness("#abcdef", 1.0)
        self.assertEqual(result, "#abcdef")

    def test_invalid_hex_passthrough(self):
        result = _adjust_brightness("not-a-color")
        self.assertEqual(result, "not-a-color")

    def test_default_factor_darkens(self):
        # Default factor is 0.80; white → should produce something darker
        result = _adjust_brightness("#ffffff")
        r = int(result[1:3], 16)
        self.assertLess(r, 255)


class TestMutedColor(unittest.TestCase):

    def test_full_alpha_returns_fg(self):
        result = _muted_color("#ffffff", "#000000", alpha=1.0)
        self.assertEqual(result, "#ffffff")

    def test_zero_alpha_returns_bg(self):
        result = _muted_color("#ffffff", "#000000", alpha=0.0)
        self.assertEqual(result, "#000000")

    def test_half_alpha_midpoint(self):
        # fg=white, bg=black, 0.5 → ~127 per channel
        result = _muted_color("#ffffff", "#000000", alpha=0.5)
        r = int(result[1:3], 16)
        self.assertAlmostEqual(r, 127, delta=1)

    def test_returns_hex_string(self):
        result = _muted_color("#aabbcc", "#112233")
        self.assertTrue(result.startswith("#"))
        self.assertEqual(len(result), 7)


# ===========================================================================
# Group I: load_config / save_config
# ===========================================================================

class TestLoadSaveConfig(unittest.TestCase):

    def test_load_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "no_such_dir" / "config.json"
            with patch.object(llm_generator, "_CONFIG_PATH", fake_path):
                result = load_config()
        self.assertEqual(result, {})

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "config.json"
            with patch.object(llm_generator, "_CONFIG_PATH", fake_path):
                save_config({"provider": "anthropic", "api_key": "testkey"})
                result = load_config()
        self.assertEqual(result["provider"], "anthropic")
        self.assertEqual(result["api_key"], "testkey")

    def test_load_bad_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "config.json"
            fake_path.write_text("this is not json {{{")
            with patch.object(llm_generator, "_CONFIG_PATH", fake_path):
                result = load_config()
        self.assertEqual(result, {})

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "a" / "b" / "config.json"
            with patch.object(llm_generator, "_CONFIG_PATH", fake_path):
                save_config({"x": 1})
            self.assertTrue(fake_path.exists())

    def test_save_produces_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "config.json"
            with patch.object(llm_generator, "_CONFIG_PATH", fake_path):
                save_config({"nested": {"key": [1, 2, 3]}})
            data = json.loads(fake_path.read_text())
        self.assertEqual(data["nested"]["key"], [1, 2, 3])

    def test_empty_dict_saves_and_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "config.json"
            with patch.object(llm_generator, "_CONFIG_PATH", fake_path):
                save_config({})
                result = load_config()
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
