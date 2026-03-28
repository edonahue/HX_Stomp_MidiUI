"""
test_hlx_builder.py

Test suite for the HLX generation pipeline.
Covers hlx_builder.py, hx_models.py, llm_generator.py, and tone_manager.py.

Run with:
    python -m unittest test_hlx_builder -v
"""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

# llm_generator and related modules import tkinter + customtkinter at module
# level. Create a stub module whose attribute access returns a base class so
# that class Foo(ctk.CTkFrame) and similar declarations work in headless envs.
class _UIStub:
    """No-op base class; absorbs any constructor args and attribute access."""
    def __init__(self, *a, **kw): pass
    def __getattr__(self, n): return lambda *a, **kw: None


def _make_ui_module(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    def _getattr(attr):
        # Return a proper class (not an instance) so it can be subclassed
        return type(attr, (_UIStub,), {})
    m.__getattr__ = _getattr
    return m


for _mod_name in ("tkinter", "tkinter.messagebox", "tkinter.filedialog",
                  "customtkinter", "_tkinter"):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _make_ui_module(_mod_name)

from hlx_builder import (
    _strip_fences,
    _match_gear_hints,
    _fuzzy_recover_model_id,
    _sanitize_params,
    build_hlx,
    build_hlx_prompt,
    parse_hlx_response,
    save_hlx,
    generate_hlx_preset,
    PresetCatalog,
    PresetResult,
)
from hx_models import ALL_MODELS, HXModel, catalog_for_prompt
from llm_generator import (
    get_provider,
    AnthropicProvider,
    OpenAIProvider,
    OllamaProvider,
    LLMGenerationError,
)
from tone_manager import Tone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Known valid model IDs used across tests
_AMP_ID   = "HD2_AmpUSDoubleNrm"
_DELAY_ID = "HD2_DelaySimpleDelay"
_REV_ID   = "HD2_ReverbPlate"

# Stub provider returns hardcoded JSON — no network required
_STUB_RESPONSE = json.dumps({
    "preset_name": "Test Preset",
    "description": "A test clean tone",
    "signal_chain_rationale": "Amp into delay",
    "blocks": [
        {
            "model_id":    _AMP_ID,
            "position":    0,
            "name":        "US Double Nrm",
            "category":    "Amp",
            "params":      {},
            "explanation": "Clean foundation",
        },
        {
            # Intentionally hallucinated: real ID is HD2_DelaySimpleDelay
            "model_id":    "HD2_DelaySimple",
            "position":    1,
            "name":        "Simple Delay",
            "category":    "Delay",
            "params":      {},
            "explanation": "Slapback echo",
        },
        {
            # Completely unknown — should be skipped
            "model_id":    "TOTALLY_UNKNOWN_XYZ",
            "position":    2,
            "name":        "Unknown",
            "category":    "??",
            "params":      {},
            "explanation": "Should be skipped",
        },
    ],
    "snapshots": [
        {"name": "Clean",  "description": "Low gain",  "block_states": {}},
        {"name": "Crunch", "description": "Mid gain",  "block_states": {}},
        {"name": "Lead",   "description": "High gain", "block_states": {}},
    ],
})


class StubProvider:
    """Drop-in LLMProvider that returns _STUB_RESPONSE without any network call."""
    def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        return _STUB_RESPONSE


# ---------------------------------------------------------------------------
# Group 1 — _strip_fences
# ---------------------------------------------------------------------------

class TestStripFences(unittest.TestCase):

    def test_plain_json(self):
        raw = '{"a": 1}'
        self.assertEqual(_strip_fences(raw), raw)

    def test_backtick_fence(self):
        raw = "```{\"a\": 1}```"
        self.assertEqual(json.loads(_strip_fences(raw)), {"a": 1})

    def test_json_fence(self):
        raw = "```json\n{\"a\": 1}\n```"
        self.assertEqual(json.loads(_strip_fences(raw)), {"a": 1})

    def test_prose_wrapper(self):
        raw = 'Here is the result:\n{"a": 1}\nHope that helps!'
        result = _strip_fences(raw)
        self.assertEqual(json.loads(result), {"a": 1})

    def test_empty_string(self):
        self.assertEqual(_strip_fences(""), "")


# ---------------------------------------------------------------------------
# Group 2 — _fuzzy_recover_model_id
# ---------------------------------------------------------------------------

class TestFuzzyRecoverModelId(unittest.TestCase):

    def test_close_amp_name(self):
        model, note = _fuzzy_recover_model_id("HD2_AmpUSDouble")
        self.assertIsNotNone(model)
        self.assertEqual(model.model_id, _AMP_ID)

    def test_hallucinated_delay(self):
        model, note = _fuzzy_recover_model_id("HD2_DelaySimple")
        self.assertIsNotNone(model)
        self.assertEqual(model.model_id, _DELAY_ID)

    def test_completely_unknown(self):
        # "QQQQ_QQQQ" → token "qqq" — no model name/alias contains this
        model, note = _fuzzy_recover_model_id("QQQQ_QQQQ")
        self.assertIsNone(model)

    def test_returns_hxmodel_type(self):
        model, _ = _fuzzy_recover_model_id("HD2_AmpUSDouble")
        self.assertIsInstance(model, HXModel)

    def test_note_string_returned(self):
        _, note = _fuzzy_recover_model_id("HD2_AmpUSDouble")
        self.assertIsInstance(note, str)
        self.assertTrue(len(note) > 0)


# ---------------------------------------------------------------------------
# Group 3 — _match_gear_hints
# ---------------------------------------------------------------------------

class TestMatchGearHints(unittest.TestCase):

    def test_known_alias_matched(self):
        hints = _match_gear_hints("I want a Fender Twin clean tone")
        joined = " ".join(hints)
        self.assertIn(_AMP_ID, joined)

    def test_case_insensitive(self):
        hints_lower = _match_gear_hints("fender twin")
        hints_mixed = _match_gear_hints("Fender Twin")
        self.assertEqual(len(hints_lower), len(hints_mixed))

    def test_no_match(self):
        hints = _match_gear_hints("generic jazz clean tone nothing specific")
        self.assertEqual(hints, [])

    def test_multiple_aliases(self):
        # Fender Twin → HD2_AmpUSDoubleNrm, Fender Bassman → HD2_AmpTweedBluesBrt
        hints = _match_gear_hints("Fender Twin into a Fender Bassman sound")
        self.assertGreaterEqual(len(hints), 2)


# ---------------------------------------------------------------------------
# Group 4 — _sanitize_params
# ---------------------------------------------------------------------------

class TestSanitizeParams(unittest.TestCase):

    def setUp(self):
        # US Double Nrm: Drive, Bass, Mid, Treble, Master, ChVol in [0, 1]
        self.model = ALL_MODELS[_AMP_ID]

    def test_valid_passthrough(self):
        cleaned, warnings = _sanitize_params(self.model, {"Drive": 0.5})
        self.assertAlmostEqual(cleaned["Drive"], 0.5)
        self.assertEqual(warnings, [])

    def test_clamped_over_1(self):
        cleaned, warnings = _sanitize_params(self.model, {"Drive": 5.0})
        self.assertAlmostEqual(cleaned["Drive"], 1.0)
        self.assertTrue(len(warnings) > 0)

    def test_clamped_under_0(self):
        cleaned, warnings = _sanitize_params(self.model, {"Drive": -0.5})
        self.assertAlmostEqual(cleaned["Drive"], 0.0)
        self.assertTrue(len(warnings) > 0)

    def test_fuzzy_key_rescue(self):
        # "channelvolume" should fuzzy-match to "ChVol"
        cleaned, warnings = _sanitize_params(self.model, {"channelvolume": 0.8})
        self.assertIn("ChVol", cleaned)
        self.assertAlmostEqual(cleaned["ChVol"], 0.8)

    def test_unknown_key_discarded(self):
        cleaned, warnings = _sanitize_params(self.model, {"FakeParamXYZ": 0.5})
        self.assertNotIn("FakeParamXYZ", cleaned)
        self.assertTrue(len(warnings) > 0)


# ---------------------------------------------------------------------------
# Group 5 — build_hlx
# ---------------------------------------------------------------------------

class TestBuildHlx(unittest.TestCase):

    def _amp_spec(self):
        return [{"model_id": _AMP_ID, "position": 0, "enabled": True, "params": {}}]

    def test_minimal_amp_only_schema_key(self):
        hlx_dict, warnings = build_hlx("Test", self._amp_spec())
        self.assertIn("schema", hlx_dict)
        self.assertEqual(hlx_dict["schema"], "L6Preset")

    def test_minimal_amp_paired_cab_added(self):
        hlx_dict, _ = build_hlx("Test", self._amp_spec())
        dsp0 = hlx_dict["data"]["tone"]["dsp0"]
        # An amp block (block0) and its cab (cab0) should both be present
        self.assertIn("block0", dsp0)
        self.assertIn("cab0", dsp0)

    def test_amp_and_delay(self):
        specs = [
            {"model_id": _AMP_ID,   "position": 0, "enabled": True, "params": {}},
            {"model_id": _DELAY_ID, "position": 1, "enabled": True, "params": {}},
        ]
        hlx_dict, _ = build_hlx("Test", specs)
        dsp0 = hlx_dict["data"]["tone"]["dsp0"]
        self.assertIn("block0", dsp0)
        self.assertIn("block1", dsp0)

    def test_preset_name_stored(self):
        hlx_dict, _ = build_hlx("MyPreset", self._amp_spec())
        self.assertEqual(hlx_dict["data"]["meta"]["name"], "MyPreset")

    def test_preset_name_truncated_to_16(self):
        long_name = "A Very Long Preset Name Indeed"
        hlx_dict, _ = build_hlx(long_name, self._amp_spec())
        stored_name = hlx_dict["data"]["meta"]["name"]
        self.assertLessEqual(len(stored_name), 16)
        self.assertEqual(stored_name, long_name[:16])

    def test_returns_warnings_list(self):
        _, warnings = build_hlx("Test", self._amp_spec())
        self.assertIsInstance(warnings, list)

    def test_empty_blocks_returns_no_error(self):
        # build_hlx itself does NOT enforce amp requirement — that's generate_hlx_preset
        hlx_dict, warnings = build_hlx("Empty", [])
        self.assertIn("schema", hlx_dict)

    def test_hlx_dict_is_json_serializable(self):
        hlx_dict, _ = build_hlx("Test", self._amp_spec())
        try:
            json.dumps(hlx_dict)
        except (TypeError, ValueError) as e:
            self.fail(f"hlx_dict not JSON serializable: {e}")


# ---------------------------------------------------------------------------
# Group 6 — PresetCatalog._sanitize
# ---------------------------------------------------------------------------

class TestCatalogSanitize(unittest.TestCase):

    def test_spaces_to_underscores(self):
        self.assertEqual(PresetCatalog._sanitize("My Cool Preset"), "my_cool_preset")

    def test_special_chars_stripped(self):
        result = PresetCatalog._sanitize("My Preset!!! #1")
        self.assertNotIn("!", result)
        self.assertNotIn("#", result)

    def test_lowercase(self):
        self.assertEqual(PresetCatalog._sanitize("ALLCAPS"), "allcaps")

    def test_leading_trailing_underscores_stripped(self):
        result = PresetCatalog._sanitize("  !!test!!  ")
        self.assertFalse(result.startswith("_"))
        self.assertFalse(result.endswith("_"))


# ---------------------------------------------------------------------------
# Group 7 — catalog_for_prompt
# ---------------------------------------------------------------------------

class TestCatalogForPrompt(unittest.TestCase):

    def test_contains_known_amp_model_id(self):
        text = catalog_for_prompt()
        self.assertIn(_AMP_ID, text)

    def test_contains_known_delay_model_id(self):
        text = catalog_for_prompt()
        self.assertIn(_DELAY_ID, text)

    def test_amp_category_header_present(self):
        text = catalog_for_prompt()
        self.assertIn("Amp", text)

    def test_filter_by_category_excludes_delay(self):
        text = catalog_for_prompt(["Amp"])
        self.assertNotIn(_DELAY_ID, text)

    def test_filter_by_category_includes_amp(self):
        text = catalog_for_prompt(["Amp"])
        self.assertIn(_AMP_ID, text)


# ---------------------------------------------------------------------------
# Group 8 — get_provider
# ---------------------------------------------------------------------------

class TestGetProvider(unittest.TestCase):

    def test_default_is_anthropic(self):
        provider = get_provider({})
        self.assertIsInstance(provider, AnthropicProvider)

    def test_openai_selected(self):
        provider = get_provider({"provider": "openai"})
        self.assertIsInstance(provider, OpenAIProvider)

    def test_ollama_selected(self):
        provider = get_provider({"provider": "ollama"})
        self.assertIsInstance(provider, OllamaProvider)

    def test_unknown_provider_falls_back_to_anthropic(self):
        provider = get_provider({"provider": "nonexistent_provider"})
        self.assertIsInstance(provider, AnthropicProvider)

    def test_api_key_passed_through(self):
        provider = get_provider({"provider": "anthropic", "anthropic_api_key": "sk-test"})
        self.assertEqual(provider.api_key, "sk-test")

    def test_model_passed_through(self):
        provider = get_provider({
            "provider": "anthropic",
            "anthropic_model": "claude-opus-4-6",
        })
        self.assertEqual(provider.model, "claude-opus-4-6")


# ---------------------------------------------------------------------------
# Group 9 — Tone.validate
# ---------------------------------------------------------------------------

class TestToneValidate(unittest.TestCase):

    def test_valid_tone_passes(self):
        Tone("Test", preset=64, snapshot=3).validate()  # no exception

    def test_preset_boundary_valid(self):
        Tone("T", preset=0).validate()
        Tone("T", preset=127).validate()

    def test_preset_out_of_range_high(self):
        with self.assertRaises(ValueError):
            Tone("T", preset=128).validate()

    def test_preset_out_of_range_low(self):
        with self.assertRaises(ValueError):
            Tone("T", preset=-1).validate()

    def test_snapshot_out_of_range(self):
        with self.assertRaises(ValueError):
            Tone("T", preset=0, snapshot=8).validate()

    def test_bank_msb_out_of_range(self):
        with self.assertRaises(ValueError):
            Tone("T", preset=0, bank_msb=128).validate()

    def test_bank_lsb_out_of_range(self):
        with self.assertRaises(ValueError):
            Tone("T", preset=0, bank_lsb=128).validate()


# ---------------------------------------------------------------------------
# Group 10 — ALL_MODELS data integrity
# ---------------------------------------------------------------------------

class TestAllModelsIntegrity(unittest.TestCase):

    def test_known_amp_present(self):
        self.assertIn(_AMP_ID, ALL_MODELS)

    def test_known_delay_present(self):
        self.assertIn(_DELAY_ID, ALL_MODELS)

    def test_all_models_are_hxmodel_instances(self):
        for mid, model in ALL_MODELS.items():
            self.assertIsInstance(model, HXModel, f"{mid} is not HXModel")

    def test_no_empty_model_ids(self):
        for mid in ALL_MODELS:
            self.assertTrue(len(mid) > 0, "Empty model_id found")

    def test_paired_cabs_exist_in_all_models(self):
        bad = []
        for mid, model in ALL_MODELS.items():
            if model.paired_cab and model.paired_cab not in ALL_MODELS:
                bad.append(f"{mid} → {model.paired_cab}")
        self.assertEqual(bad, [], f"Missing paired cabs: {bad}")

    def test_all_categories_are_strings(self):
        for mid, model in ALL_MODELS.items():
            self.assertIsInstance(model.category, str, f"{mid}.category not str")


# ---------------------------------------------------------------------------
# Group 11 — generate_hlx_preset (stub provider, no network)
# ---------------------------------------------------------------------------

class TestGenerateHlxPresetStub(unittest.TestCase):

    def setUp(self):
        self.result = generate_hlx_preset("clean Fender tone", StubProvider())

    def test_returns_preset_result(self):
        self.assertIsInstance(self.result, PresetResult)

    def test_preset_name_set(self):
        self.assertEqual(self.result.preset_name, "Test Preset")

    def test_unknown_id_not_in_blocks(self):
        ids = [b["model_id"] for b in self.result.blocks]
        self.assertNotIn("TOTALLY_UNKNOWN_XYZ", ids)

    def test_valid_amp_block_present(self):
        ids = [b["model_id"] for b in self.result.blocks]
        self.assertIn(_AMP_ID, ids)

    def test_hlx_dict_is_json_serializable(self):
        try:
            json.dumps(self.result.hlx_dict)
        except (TypeError, ValueError) as e:
            self.fail(f"hlx_dict not JSON serializable: {e}")

    def test_snapshots_present(self):
        self.assertGreaterEqual(len(self.result.snapshots), 1)

    def test_description_set(self):
        self.assertIsInstance(self.result.description, str)

    def test_warnings_is_list(self):
        self.assertIsInstance(self.result.warnings, list)


class TestGenerateHlxPresetErrors(unittest.TestCase):

    def test_no_amp_raises(self):
        no_amp_response = json.dumps({
            "preset_name": "No Amp",
            "description": "",
            "signal_chain_rationale": "",
            "blocks": [
                {"model_id": _DELAY_ID, "position": 0, "name": "Simple Delay",
                 "category": "Delay", "params": {}, "explanation": ""},
            ],
            "snapshots": [],
        })

        class NoAmpProvider:
            def complete(self, system, user, max_tokens=1500):
                return no_amp_response

        with self.assertRaises((ValueError, LLMGenerationError)):
            generate_hlx_preset("delay only", NoAmpProvider())

    def test_invalid_json_raises(self):
        class BadJsonProvider:
            def complete(self, system, user, max_tokens=1500):
                return "this is not json at all!!!"

        with self.assertRaises((LLMGenerationError, Exception)):
            generate_hlx_preset("anything", BadJsonProvider())


# ---------------------------------------------------------------------------
# Group 12 — save_hlx and PresetCatalog I/O (tempdir)
# ---------------------------------------------------------------------------

class TestSaveHlx(unittest.TestCase):

    def _minimal_hlx(self):
        hlx_dict, _ = build_hlx("IO Test", [
            {"model_id": _AMP_ID, "position": 0, "enabled": True, "params": {}}
        ])
        return hlx_dict

    def test_save_hlx_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "test.hlx"
            save_hlx(self._minimal_hlx(), dest)
            self.assertTrue(dest.exists())

    def test_save_hlx_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "test.hlx"
            save_hlx(self._minimal_hlx(), dest)
            loaded = json.loads(dest.read_text())
            self.assertIsInstance(loaded, dict)

    def test_save_hlx_schema_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "test.hlx"
            save_hlx(self._minimal_hlx(), dest)
            loaded = json.loads(dest.read_text())
            self.assertEqual(loaded["schema"], "L6Preset")


class TestPresetCatalog(unittest.TestCase):

    def _make_result(self, name="Test Preset"):
        hlx_dict, _ = build_hlx(name, [
            {"model_id": _AMP_ID, "position": 0, "enabled": True, "params": {}}
        ])
        return PresetResult(
            hlx_dict=hlx_dict,
            preset_name=name,
            description="Test",
            blocks=[{"model_id": _AMP_ID, "name": "US Double Nrm",
                     "category": "Amp", "explanation": ""}],
            signal_chain_rationale="",
            prompt="test",
            snapshots=[],
            warnings=[],
        )

    def _patched_catalog(self, tmp_path: Path):
        """Return (PresetCatalog, patch context manager)."""
        return (
            PresetCatalog(),
            patch.multiple(
                PresetCatalog,
                _PRESETS_DIR=tmp_path,
                _CATALOG_FILE=tmp_path / "catalog.json",
            ),
        )

    def test_save_preset_creates_hlx_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch.object(PresetCatalog, "_PRESETS_DIR", tmp_path), \
                 patch.object(PresetCatalog, "_CATALOG_FILE", tmp_path / "catalog.json"):
                catalog = PresetCatalog()
                dest = catalog.save_preset(self._make_result(), filepath=tmp_path / "out.hlx")
                self.assertTrue(dest.exists())
                self.assertEqual(dest.suffix, ".hlx")

    def test_save_preset_writes_catalog_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch.object(PresetCatalog, "_PRESETS_DIR", tmp_path), \
                 patch.object(PresetCatalog, "_CATALOG_FILE", tmp_path / "catalog.json"):
                catalog = PresetCatalog()
                catalog.save_preset(self._make_result(), filepath=tmp_path / "out.hlx")
                entries = catalog.list_presets()
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["preset_name"], "Test Preset")

    def test_list_presets_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch.object(PresetCatalog, "_PRESETS_DIR", tmp_path), \
                 patch.object(PresetCatalog, "_CATALOG_FILE", tmp_path / "catalog.json"):
                catalog = PresetCatalog()
                catalog.save_preset(self._make_result("First"),  filepath=tmp_path / "a.hlx")
                catalog.save_preset(self._make_result("Second"), filepath=tmp_path / "b.hlx")
                entries = catalog.list_presets()
                self.assertEqual(entries[0]["preset_name"], "Second")

    def test_remove_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch.object(PresetCatalog, "_PRESETS_DIR", tmp_path), \
                 patch.object(PresetCatalog, "_CATALOG_FILE", tmp_path / "catalog.json"):
                catalog = PresetCatalog()
                catalog.save_preset(self._make_result(), filepath=tmp_path / "out.hlx")
                entries_before = catalog.list_presets()
                self.assertEqual(len(entries_before), 1)
                catalog.remove_entry(entries_before[0]["filename"])
                self.assertEqual(catalog.list_presets(), [])


# ---------------------------------------------------------------------------
# Group 13 — build_hlx_prompt
# ---------------------------------------------------------------------------

class TestBuildHlxPrompt(unittest.TestCase):

    def test_returns_tuple(self):
        result = build_hlx_prompt("clean blues tone")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_both_strings(self):
        system, user = build_hlx_prompt("clean blues tone")
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)

    def test_system_contains_catalog(self):
        system, _ = build_hlx_prompt("any description")
        self.assertIn(_AMP_ID, system)

    def test_user_contains_description(self):
        desc = "warm ambient reverb pad"
        _, user = build_hlx_prompt(desc)
        self.assertIn(desc, user)

    def test_gear_hints_injected_when_known_alias(self):
        """Fender Twin is aliased to HD2_AmpUSDoubleNrm in hx_models.py."""
        _, user = build_hlx_prompt("I want a Fender Twin clean tone")
        self.assertIn(_AMP_ID, user)

    def test_no_gear_hints_when_no_alias(self):
        """A description with no recognisable aliases injects no hint lines."""
        _, user = build_hlx_prompt("generic clean tone")
        self.assertNotIn("Gear Match Hints", user)


# ---------------------------------------------------------------------------
# Group 14 — parse_hlx_response
# ---------------------------------------------------------------------------

class TestParseHlxResponse(unittest.TestCase):

    def test_valid_response_returns_preset_result(self):
        result = parse_hlx_response(_STUB_RESPONSE, "test description")
        self.assertIsInstance(result, PresetResult)

    def test_preset_name_from_response(self):
        result = parse_hlx_response(_STUB_RESPONSE, "test")
        self.assertEqual(result.preset_name, "Test Preset")

    def test_strips_markdown_fences(self):
        fenced = f"```json\n{_STUB_RESPONSE}\n```"
        result = parse_hlx_response(fenced, "test")
        self.assertIsInstance(result, PresetResult)

    def test_invalid_json_raises_llm_error(self):
        with self.assertRaises(LLMGenerationError):
            parse_hlx_response("not valid json at all", "test")

    def test_empty_string_raises_llm_error(self):
        with self.assertRaises(LLMGenerationError):
            parse_hlx_response("", "test")

    def test_whitespace_only_raises_llm_error(self):
        with self.assertRaises(LLMGenerationError):
            parse_hlx_response("   \n\t  ", "test")

    def test_prompt_field_set_to_description(self):
        desc = "unique test description string"
        result = parse_hlx_response(_STUB_RESPONSE, desc)
        self.assertEqual(result.prompt, desc)

    def test_response_with_unknown_ids_has_warnings(self):
        result = parse_hlx_response(_STUB_RESPONSE, "test")
        warning_text = " ".join(result.warnings)
        self.assertIn("TOTALLY_UNKNOWN_XYZ", warning_text)

    def test_generate_hlx_preset_uses_helpers(self):
        """generate_hlx_preset() still works correctly through the refactored helpers."""
        result = generate_hlx_preset("clean blues tone", StubProvider())
        self.assertIsInstance(result, PresetResult)
        self.assertEqual(result.preset_name, "Test Preset")


if __name__ == "__main__":
    unittest.main(verbosity=2)
