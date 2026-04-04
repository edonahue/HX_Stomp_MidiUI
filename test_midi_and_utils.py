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
_mido_stub.get_input_names  = lambda: ["FakeMidi Port 1", "Another Port"]
_mido_stub.open_output = MagicMock(return_value=MagicMock(closed=False))
_mido_stub.open_input  = MagicMock(return_value=MagicMock(closed=False, __iter__=lambda s: iter([])))
_mido_stub.Message = MagicMock(side_effect=lambda *a, **kw: kw)
_mido_stub.ports = types.SimpleNamespace(BaseOutput=object, BaseInput=object)
sys.modules["mido"] = _mido_stub

from midi_interface import (
    HXStompMidi,
    CC_BANK_MSB, CC_BANK_LSB, CC_EXP1, CC_EXP2,
    CC_FS1, CC_FS7, CC_LOOP_REC, CC_LOOP_PLAY, CC_TUNER, CC_SNAPSHOT,
    SNAPSHOT_NEXT, SNAPSHOT_PREV, _FS_CC,
    CC_EXP_TOE, CC_LOOP_ONCE, CC_LOOP_UNDO, CC_TAP_TEMPO,
    CC_LOOP_REV, CC_LOOP_HALF, CC_LOOP_ONOFF,
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
                  "tkinter.font", "customtkinter", "_tkinter"):
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


# ===========================================================================
# Group L: Looper controls — exact CC values per HX Stomp MIDI spec
# ===========================================================================

def _looper_midi() -> tuple:
    """Return (hxi, captured_list) — hxi with send_cc spied upon."""
    hxi = HXStompMidi.__new__(HXStompMidi)
    hxi._port = None
    hxi._channel = 0
    hxi._tuner_state = False
    captured = []
    hxi.send_cc = lambda cc, val: captured.append((cc, val))
    return hxi, captured


class TestLooperControls(unittest.TestCase):

    def setUp(self):
        self.midi, self.captured = _looper_midi()

    def _assert_cc(self, cc: int, value: int):
        self.assertEqual(len(self.captured), 1,
                         f"Expected 1 CC message, got {self.captured}")
        self.assertEqual(self.captured[0], (cc, value))

    # ── Record / Overdub (CC 60) ─────────────────────────────────────────

    def test_looper_record_sends_cc60_127(self):
        self.midi.looper_record()
        self._assert_cc(CC_LOOP_REC, 127)

    def test_looper_overdub_sends_cc60_0(self):
        self.midi.looper_overdub()
        self._assert_cc(CC_LOOP_REC, 0)

    # ── Play / Stop (CC 61) ──────────────────────────────────────────────

    def test_looper_play_sends_cc61_127(self):
        self.midi.looper_play()
        self._assert_cc(CC_LOOP_PLAY, 127)

    def test_looper_stop_sends_cc61_0(self):
        self.midi.looper_stop()
        self._assert_cc(CC_LOOP_PLAY, 0)

    # ── Play Once (CC 62) ────────────────────────────────────────────────

    def test_looper_play_once_sends_cc62_127(self):
        self.midi.looper_play_once()
        self._assert_cc(CC_LOOP_ONCE, 127)

    # ── Undo/Redo (CC 63) ────────────────────────────────────────────────

    def test_looper_undo_redo_sends_cc63_127(self):
        self.midi.looper_undo_redo()
        self._assert_cc(CC_LOOP_UNDO, 127)

    # ── Tap Tempo (CC 64) ────────────────────────────────────────────────

    def test_tap_tempo_sends_cc64_127(self):
        self.midi.tap_tempo()
        self._assert_cc(CC_TAP_TEMPO, 127)

    # ── Reverse (CC 65) ──────────────────────────────────────────────────

    def test_looper_reverse_on_sends_cc65_127(self):
        self.midi.looper_reverse(True)
        self._assert_cc(CC_LOOP_REV, 127)

    def test_looper_reverse_off_sends_cc65_0(self):
        self.midi.looper_reverse(False)
        self._assert_cc(CC_LOOP_REV, 0)

    # ── Half Speed (CC 66) ───────────────────────────────────────────────

    def test_looper_half_speed_on_sends_cc66_127(self):
        self.midi.looper_half_speed(True)
        self._assert_cc(CC_LOOP_HALF, 127)

    def test_looper_half_speed_off_sends_cc66_0(self):
        self.midi.looper_half_speed(False)
        self._assert_cc(CC_LOOP_HALF, 0)

    # ── Looper On/Off (CC 67) ────────────────────────────────────────────

    def test_looper_enabled_on_sends_cc67_127(self):
        self.midi.looper_enabled(True)
        self._assert_cc(CC_LOOP_ONOFF, 127)

    def test_looper_enabled_off_sends_cc67_0(self):
        self.midi.looper_enabled(False)
        self._assert_cc(CC_LOOP_ONOFF, 0)

    # ── EXP Toe Switch (CC 59) ───────────────────────────────────────────

    def test_set_exp_toe_on_sends_cc59_127(self):
        self.midi.set_exp_toe(True)
        self._assert_cc(CC_EXP_TOE, 127)

    def test_set_exp_toe_off_sends_cc59_0(self):
        self.midi.set_exp_toe(False)
        self._assert_cc(CC_EXP_TOE, 0)


# ===========================================================================
# Group M: LLM provider factory
# ===========================================================================

from llm_generator import (
    get_provider,
    AnthropicProvider, OpenAIProvider, GeminiProvider, OllamaProvider,
)


class TestGetProvider(unittest.TestCase):

    def test_default_is_anthropic(self):
        provider = get_provider({})
        self.assertIsInstance(provider, AnthropicProvider)

    def test_anthropic_explicit(self):
        provider = get_provider({"provider": "anthropic"})
        self.assertIsInstance(provider, AnthropicProvider)

    def test_openai(self):
        provider = get_provider({"provider": "openai", "openai_api_key": "sk-x"})
        self.assertIsInstance(provider, OpenAIProvider)

    def test_gemini(self):
        provider = get_provider({"provider": "gemini", "gemini_api_key": "key"})
        self.assertIsInstance(provider, GeminiProvider)

    def test_ollama(self):
        provider = get_provider({"provider": "ollama"})
        self.assertIsInstance(provider, OllamaProvider)

    def test_unknown_provider_falls_back_to_anthropic(self):
        provider = get_provider({"provider": "nonexistent_provider"})
        self.assertIsInstance(provider, AnthropicProvider)

    def test_api_key_passed_through(self):
        provider = get_provider({"provider": "openai", "openai_api_key": "sk-test-123"})
        self.assertEqual(provider.api_key, "sk-test-123")

    def test_model_override(self):
        provider = get_provider({
            "provider": "anthropic",
            "anthropic_model": "claude-opus-4-6",
        })
        self.assertEqual(provider.model, "claude-opus-4-6")

    def test_default_model_used_when_not_in_config(self):
        provider = get_provider({"provider": "anthropic"})
        self.assertEqual(provider.model, AnthropicProvider.default_model)

    def test_ollama_no_api_key_required(self):
        # OllamaProvider should work with empty api_key
        provider = get_provider({"provider": "ollama"})
        self.assertEqual(provider.api_key, "")


# ===========================================================================
# Group N: Tone search filter logic
# ===========================================================================

class TestToneSearch(unittest.TestCase):
    """Tests for the search filter applied in soundboard_ui._render_tones."""

    def setUp(self):
        from tone_manager import Tone, ToneManager
        self.Tone = Tone
        self.ToneManager = ToneManager

    def _make_manager(self, tone_dicts):
        import tempfile, json, os
        from tone_manager import ToneManager
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False)
        json.dump(tone_dicts, f)
        f.close()
        self._tmp = f.name
        return ToneManager(f.name)

    def tearDown(self):
        import os
        if hasattr(self, "_tmp"):
            os.unlink(self._tmp)

    def _apply_filter(self, tones_mgr, query: str) -> dict:
        by_cat = tones_mgr.tones_by_category()
        q = query.strip().lower()
        if q:
            by_cat = {
                cat: [t for t in tones
                      if q in t.name.lower() or q in (cat or "").lower()]
                for cat, tones in by_cat.items()
            }
            by_cat = {k: v for k, v in by_cat.items() if v}
        return by_cat

    def test_filter_by_name_substring(self):
        mgr = self._make_manager([
            {"name": "Blues Clean", "preset": 0, "category": "Clean"},
            {"name": "Fuzz Wall",   "preset": 1, "category": "Overdrive"},
        ])
        result = self._apply_filter(mgr, "blues")
        self.assertIn("Clean", result)
        names = [t.name for t in result["Clean"]]
        self.assertIn("Blues Clean", names)
        self.assertNotIn("Overdrive", result)

    def test_filter_by_category_substring(self):
        mgr = self._make_manager([
            {"name": "Alpha", "preset": 0, "category": "Clean"},
            {"name": "Beta",  "preset": 1, "category": "Overdrive"},
        ])
        result = self._apply_filter(mgr, "over")
        self.assertIn("Overdrive", result)
        self.assertNotIn("Clean", result)

    def test_empty_query_returns_all(self):
        mgr = self._make_manager([
            {"name": "A", "preset": 0, "category": "Clean"},
            {"name": "B", "preset": 1, "category": "Overdrive"},
        ])
        result = self._apply_filter(mgr, "")
        self.assertIn("Clean", result)
        self.assertIn("Overdrive", result)

    def test_no_match_returns_empty(self):
        mgr = self._make_manager([
            {"name": "Alpha", "preset": 0, "category": "Clean"},
        ])
        result = self._apply_filter(mgr, "zzznomatch")
        self.assertEqual(result, {})

    def test_case_insensitive(self):
        mgr = self._make_manager([
            {"name": "WARM CRUNCH", "preset": 0, "category": "Overdrive"},
        ])
        result = self._apply_filter(mgr, "warm crunch")
        self.assertIn("Overdrive", result)


# ===========================================================================
# Group O: generate_variants() unit tests
# ===========================================================================

class TestGenerateVariants(unittest.TestCase):
    """Tests for hlx_builder.generate_variants() with mocked generate_hlx_preset."""

    def _make_result(self, name="Test"):
        r = MagicMock()
        r.preset_name = name
        return r

    def test_returns_three_results_on_success(self):
        results = [self._make_result(f"Option {i}") for i in range(3)]
        call_count = 0

        def fake_generate(desc, provider, variant_hint=""):
            nonlocal call_count
            call_count += 1
            return results[call_count - 1]

        with patch("hlx_builder.generate_hlx_preset", side_effect=fake_generate):
            from hlx_builder import generate_variants
            out = generate_variants("test", MagicMock(), n=3)
        self.assertEqual(len(out), 3)
        self.assertEqual(call_count, 3)

    def test_partial_failure_stored_as_exception(self):
        def fake_generate(desc, provider, variant_hint=""):
            if "Prioritise" in variant_hint:
                raise RuntimeError("API timeout")
            return self._make_result()

        with patch("hlx_builder.generate_hlx_preset", side_effect=fake_generate):
            from hlx_builder import generate_variants
            out = generate_variants("test", MagicMock(), n=3)
        exceptions = [r for r in out if isinstance(r, Exception)]
        successes  = [r for r in out if not isinstance(r, Exception)]
        self.assertEqual(len(exceptions), 1)
        self.assertEqual(len(successes), 2)

    def test_calls_provider_exactly_n_times(self):
        call_count = 0

        def fake_generate(desc, provider, variant_hint=""):
            nonlocal call_count
            call_count += 1
            return self._make_result()

        with patch("hlx_builder.generate_hlx_preset", side_effect=fake_generate):
            from hlx_builder import generate_variants
            generate_variants("test", MagicMock(), n=3)
        self.assertEqual(call_count, 3)

    def test_variant_hint_applied(self):
        hints_used = []

        def fake_generate(desc, provider, variant_hint=""):
            hints_used.append(variant_hint)
            return self._make_result()

        with patch("hlx_builder.generate_hlx_preset", side_effect=fake_generate):
            from hlx_builder import generate_variants, _VARIANT_HINTS
            generate_variants("test", MagicMock(), n=3)
        self.assertEqual(hints_used[0], _VARIANT_HINTS[0])
        self.assertEqual(hints_used[1], _VARIANT_HINTS[1])
        self.assertEqual(hints_used[2], _VARIANT_HINTS[2])


# ===========================================================================
# Group P: Two-way device sync — _listen_loop parsing
# ===========================================================================

class TestDeviceSync(unittest.TestCase):
    """Tests for HXStompMidi two-way sync listener."""

    def _make_midi(self):
        from midi_interface import HXStompMidi
        midi = HXStompMidi.__new__(HXStompMidi)
        midi.channel = 0
        midi._port = None
        midi._port_name = ""
        midi._tuner_active = False
        midi._in_port = None
        midi._listener_thread = None
        midi._device_callback = None
        return midi

    def _make_msg(self, type_, **kwargs):
        msg = MagicMock()
        msg.type = type_
        for k, v in kwargs.items():
            setattr(msg, k, v)
        return msg

    def test_stop_listening_clears_callback(self):
        midi = self._make_midi()
        midi._device_callback = lambda *a: None
        midi.stop_listening()
        self.assertIsNone(midi._device_callback)

    def test_list_input_ports(self):
        from midi_interface import HXStompMidi
        ports = HXStompMidi.list_input_ports()
        self.assertIsInstance(ports, list)

    def test_find_hx_input_port_no_hx(self):
        from midi_interface import HXStompMidi
        # Stub returns "FakeMidi Port 1" — no HX keywords
        result = HXStompMidi.find_hx_input_port()
        self.assertIsNone(result)

    def test_listen_loop_fires_preset_change(self):
        """Simulate one program_change message and check callback fires."""
        from midi_interface import HXStompMidi, CC_BANK_MSB, CC_BANK_LSB

        events = []
        midi = self._make_midi()

        def callback(event_type, data):
            events.append((event_type, data))
            if event_type == "disconnected":
                midi._device_callback = None  # stop the retry loop

        midi._device_callback = callback

        # Build a fake message sequence: bank MSB 0, bank LSB 1, PC 5
        msgs = [
            self._make_msg("control_change", control=CC_BANK_MSB, value=0),
            self._make_msg("control_change", control=CC_BANK_LSB, value=1),
            self._make_msg("program_change", program=5),
        ]

        class FakePort:
            closed = False
            def __iter__(self):
                yield from msgs
                raise RuntimeError("end of test")
            def close(self): pass

        import sys
        sys.modules["mido"].open_input = MagicMock(return_value=FakePort())
        sys.modules["mido"].get_input_names = lambda: ["FakeMidi Port 1"]

        with patch("midi_interface.time") as mock_time:
            mock_time.sleep = MagicMock()
            midi._listen_loop("FakeMidi")

        preset_events = [e for e in events if e[0] == "preset_change"]
        self.assertEqual(len(preset_events), 1)
        self.assertEqual(preset_events[0][1]["preset"],   5)
        self.assertEqual(preset_events[0][1]["bank_msb"], 0)
        self.assertEqual(preset_events[0][1]["bank_lsb"], 1)

    def test_listen_loop_fires_snapshot_change(self):
        from midi_interface import HXStompMidi, CC_SNAPSHOT

        events = []
        midi = self._make_midi()

        def callback(event_type, data):
            events.append((event_type, data))
            if event_type == "disconnected":
                midi._device_callback = None  # stop the retry loop

        midi._device_callback = callback

        msgs = [self._make_msg("control_change", control=CC_SNAPSHOT, value=2)]

        class FakePort:
            closed = False
            def __iter__(self):
                yield from msgs
                raise RuntimeError("end")
            def close(self): pass

        import sys
        sys.modules["mido"].open_input = MagicMock(return_value=FakePort())
        sys.modules["mido"].get_input_names = lambda: ["FakeMidi Port 1"]

        with patch("midi_interface.time") as mock_time:
            mock_time.sleep = MagicMock()
            midi._listen_loop("FakeMidi")

        snap_events = [e for e in events if e[0] == "snapshot_change"]
        self.assertEqual(len(snap_events), 1)
        self.assertEqual(snap_events[0][1]["snapshot"], 2)

    def test_listen_loop_stops_when_callback_cleared(self):
        """Listener should exit cleanly when _device_callback is set to None."""
        from midi_interface import HXStompMidi

        midi = self._make_midi()
        midi._device_callback = None   # already cleared — loop exits immediately

        # Should return without blocking or crashing
        midi._listen_loop("NonExistentPort")


if __name__ == "__main__":
    unittest.main()
