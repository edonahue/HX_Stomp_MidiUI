"""
hlx_builder.py

Constructs Line 6 HX Stomp .hlx preset files from LLM-selected amp/effect
blocks and manages a local catalog of generated presets.

.hlx files are plain JSON understood by HX Edit (Line 6's desktop editor).
The format is community-reverse-engineered; schema is based on:
  - helix-preset-viewer (dbagchee/helix-preset-viewer)
  - phelix random preset generator (sensorium/phelix)
  - helix-py-api (HackLabsGuitar/helix-py-api)
  - real .hlx files from EmmanuelBeziat/helix-presets
"""

from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from hx_models import ALL_MODELS, HXModel, catalog_for_prompt

# llm_generator is imported lazily inside generate_hlx_preset() to avoid
# pulling in tkinter (and circular imports) at module load time.
_HLX_MAX_TOKENS = 1500


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HX_STOMP_DEVICE_ID = 2162694   # HX Stomp device integer (from helix-preset-viewer)
_MAX_BLOCKS         = 6          # HX Stomp processing block limit
_DELAY_REVERB_CATS  = {"Delay", "Reverb"}

# Categories where @type = 7 (trails-capable)
_TRAILS_CATEGORIES  = {"Delay", "Reverb"}

# Prefix → category mapping for fuzzy model-ID recovery
_PREFIX_CAT: list[tuple[str, str]] = [
    ("HD2_Amp",     "Amp"),
    ("HD2_Reverb",  "Reverb"),
    ("HD2_Delay",   "Delay"),
    ("HD2_Dist",    "Distortion"),
    ("HD2_Comp",    "Dynamics"),
    ("HD2_Dyn",     "Dynamics"),
    ("HD2_Gate",    "Dynamics"),
    ("HD2_EQ",      "EQ"),
    ("HD2_Mod",     "Modulation"),
    ("HD2_Chorus",  "Modulation"),
    ("HD2_Flanger", "Modulation"),
    ("HD2_Phaser",  "Modulation"),
    ("HD2_Rotary",  "Modulation"),
    ("HD2_Tremolo", "Modulation"),
]

# Expected left-to-right position rank for signal chain order validation
_CHAIN_RANK: dict[str, int] = {
    "Dynamics":   0,
    "Distortion": 1,
    "Amp":        2,
    "EQ":         3,
    "Modulation": 4,
    "Delay":      5,
    "Reverb":     6,
    "Cab":        7,  # internally paired with Amp; not user-positioned
}


# ---------------------------------------------------------------------------
# System prompt for .hlx generation
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    catalog = catalog_for_prompt()
    return f"""\
You are a guitar tone designer for the Line 6 HX Stomp.
Respond with ONLY a JSON object — no markdown, no explanation.

CRITICAL RULES:
1. Use ONLY the exact model_id strings from the catalog below — no invented IDs.
   If unsure, pick the closest available option from the list; never invent a name.
2. Maximum {_MAX_BLOCKS} processing blocks (HX Stomp hardware limit)
3. Exactly ONE amp block required
4. Signal order: Dynamics → Distortion → Amp → EQ → Modulation → Delay → Reverb
   Assign positions 0, 1, 2… in this order — position 0 is first in the chain.
5. Preset name: max 16 chars, title case. Snapshot names: max 12 chars.
6. Parameter values: most knobs 0.0–1.0; Level/Gain in dB (e.g. -3.0);
   HighCut/LowCut in Hz (e.g. 8000.0); Threshold in negative dB (e.g. -65.0)
7. Parameter names are case-sensitive abbreviations. Common amp params: Drive,
   Bass, Mid, Treble, Presence, Master, ChVol. Effect params: Drive, Tone, Level,
   Mix, Rate, Depth, Decay, Feedback, Time. Use only names visible in the catalog.

AVAILABLE MODELS — use ONLY these model_ids:
{catalog}

SNAPSHOTS: Define exactly 3 named snapshots (e.g. Rhythm / Lead / Clean).
Per snapshot: state which blocks are active (true) or bypassed (false).
The amp block should almost always stay active.

EXAMPLE (2-block chain — your response must follow this exact structure):
{{
  "preset_name": "Plexi Crunch",
  "description": "Classic British crunch with vintage spring reverb.",
  "blocks": [
    {{"model_id": "HD2_AmpBritPlexiNrm", "position": 0, "enabled": true,
      "params": {{"Drive": 0.6, "Bass": 0.5, "Treble": 0.6, "Master": 0.7}},
      "explanation": "Marshall Plexi for responsive crunch."}},
    {{"model_id": "HD2_Reverb63Spring", "position": 1, "enabled": true,
      "params": {{"Decay": 0.4, "Mix": 0.2}},
      "explanation": "Vintage spring splash."}}
  ],
  "signal_chain_rationale": "Simple crunch platform with vintage reverb.",
  "snapshots": [
    {{"name": "Rhythm",  "description": "Full chain.",   "block_states": {{"block0": true,  "block1": true}}}},
    {{"name": "Lead",    "description": "Reverb off.",   "block_states": {{"block0": true,  "block1": false}}}},
    {{"name": "Dry",     "description": "Amp only.",     "block_states": {{"block0": true,  "block1": false}}}}
  ]
}}

Now generate a preset for the tone described by the user. Your response must be a single JSON object in the same structure as the example above."""


# ---------------------------------------------------------------------------
# .hlx fixed system blocks for HX Stomp
# ---------------------------------------------------------------------------

_SYSTEM_BLOCKS: dict = {
    "inputA": {
        "@model":    "HelixStomp_AppDSPFlowInput",
        "@input":    1,
        "noiseGate": False,
        "threshold": -48.0,
        "decay":     0.5,
    },
    "inputB": {
        "@model":    "HelixStomp_AppDSPFlowInput",
        "@input":    0,
        "noiseGate": False,
        "threshold": -48.0,
        "decay":     0.5,
    },
    "split": {
        "@model":    "HD2_AppDSPFlowSplitY",
        "@enabled":  True,
        "@position": 0,
        "BalanceA":  0.5,
        "BalanceB":  0.5,
        "bypass":    False,
    },
    "join": {
        "@model":    "HD2_AppDSPFlowJoin",
        "@enabled":  True,
        "@position": 6,
        "A Level":   0.0,
        "A Pan":     0.5,
        "B Level":   0.0,
        "B Pan":     0.5,
        "B Polarity": False,
        "Level":     0.0,
    },
    "outputA": {
        "@model":   "HelixStomp_AppDSPFlowOutputMain",
        "@output":  1,
        "gain":     0.0,
        "pan":      0.5,
    },
    "outputB": {
        "@model":   "HelixStomp_AppDSPFlowOutputSend",
        "@output":  0,
        "gain":     0.0,
        "pan":      0.5,
    },
}


# ---------------------------------------------------------------------------
# .hlx builder
# ---------------------------------------------------------------------------

def _make_block(model: HXModel, position: int, enabled: bool,
                params: dict, cab_key: str = "") -> dict:
    """Build a single dsp0 block dict."""
    if model.category == "Amp":
        block_type = 3  # Amp + cab combined
    elif model.category in _TRAILS_CATEGORIES:
        block_type = 7
    elif model.category == "Cab":
        block_type = 2
    else:
        block_type = 0

    merged = {**model.default_params, **params}

    blk: dict = {
        "@model":              model.model_id,
        "@enabled":            enabled,
        "@path":               0,
        "@position":           position,
        "@type":               block_type,
        "@bypassvolume":       1.0,
        "@no_snapshot_bypass": False,
    }
    if model.category in _TRAILS_CATEGORIES:
        blk["@trails"] = False
    if cab_key:
        blk["@cab"] = cab_key
    blk.update(merged)
    return blk


def _make_cab(cab_model: HXModel) -> dict:
    """Build a standalone cab block dict."""
    return {
        "@model":   cab_model.model_id,
        "@enabled": True,
        "@type":    2,
        **cab_model.default_params,
    }


def _fuzzy_param_key(unknown: str, known_keys: list[str]) -> str | None:
    """
    Attempt to match an LLM-provided parameter name to a known key.

    Pass 1 — case-insensitive exact          ('channelvolume' → 'ChannelVolume')
    Pass 2 — substring either direction      ('Vol' → 'ChVol', 'Mid' → 'MiddleFreq')
    Pass 3 — any camelCase token of known key appears in unknown (≥3 chars)
             ('ChannelVolume' → 'ChVol' because 'vol' from ChVol ⊆ 'channelvolume')

    Returns the first matching known key, or None.
    """
    u = unknown.lower()
    for k in known_keys:
        if k.lower() == u:
            return k
    for k in known_keys:
        kl = k.lower()
        if kl in u or u in kl:
            return k
    for k in known_keys:
        k_toks = [t.lower() for t in re.findall(r"[A-Z][a-z]+|[A-Z]+", k) if len(t) >= 3]
        if any(tok in u for tok in k_toks):
            return k
    return None


def _sanitize_params(model: HXModel, raw_params: dict) -> tuple[dict, list[str]]:
    """
    Validate and clamp LLM-provided parameter values against the model's
    default_params schema.

    - Unknown keys are first attempted via _fuzzy_param_key rescue (catches
      abbreviations like ChannelVolume → ChVol, Vol → ChVol).
    - Truly unknown keys (no fuzzy match) are stripped with a warning.
    - Values are clamped to a range inferred from key name and default:
        • "Cut" / "Freq" in name → Hz range [20.0, 20_000.0]
        • "hreshold" in name     → dB range [-80.0, 0.0]
        • bool default           → cast to bool, no clamp
        • default in [0.0, 1.0] → normalized [0.0, 1.0]
        • otherwise              → large dB/level range [-40.0, 40.0]
    - Returns (cleaned_dict, warnings_list).
    """
    warnings: list[str] = []
    cleaned: dict = {}
    known_keys = list(model.default_params.keys())

    # Attempt fuzzy rescue on unknown keys before stripping
    rescued_raw: dict = {}   # unknown keys mapped to their rescued canonical key
    truly_unknown: list[str] = []
    for k in raw_params:
        if k in model.default_params:
            continue  # already known; handled in main loop
        matched = _fuzzy_param_key(k, known_keys)
        if matched and matched not in raw_params:
            # Only rescue if the canonical key wasn't already provided by LLM
            rescued_raw[matched] = raw_params[k]
            warnings.append(f"{model.name}: '{k}' substituted as '{matched}'")
        else:
            truly_unknown.append(k)

    if truly_unknown:
        keys_str = ", ".join(truly_unknown[:5])
        suffix = "…" if len(truly_unknown) > 5 else ""
        warnings.append(
            f"{model.name}: unknown param(s) ignored: {keys_str}{suffix}"
        )

    for key, default in model.default_params.items():
        if key in raw_params:
            raw_val = raw_params[key]
        elif key in rescued_raw:
            raw_val = rescued_raw[key]
        else:
            cleaned[key] = default
            continue

        # Boolean params — cast, no numeric clamping
        if isinstance(default, bool):
            cleaned[key] = bool(raw_val)
            continue

        # Try to coerce to float
        try:
            val = float(raw_val)
        except (TypeError, ValueError):
            warnings.append(
                f"{model.name}: {key} could not be converted "
                f"({raw_val!r}), using default"
            )
            cleaned[key] = default
            continue

        # Determine clamping range from key name / default magnitude
        key_lower = key.lower()
        if "cut" in key_lower or "freq" in key_lower:
            lo, hi = 20.0, 20_000.0
        elif "hreshold" in key_lower:
            lo, hi = -80.0, 0.0
        elif isinstance(default, float) and 0.0 <= default <= 1.0:
            lo, hi = 0.0, 1.0
        else:
            lo, hi = -40.0, 40.0

        clamped = max(lo, min(hi, val))
        if abs(clamped - val) > 1e-6:
            warnings.append(
                f"{model.name}: {key} clamped {val:.3g} → {clamped:.3g}"
            )
        cleaned[key] = clamped

    return cleaned, warnings


def build_hlx(preset_name: str, blocks_spec: list[dict],
              snapshots_spec: list[dict] | None = None) -> tuple[dict, list[str]]:
    """
    Construct a complete .hlx JSON dict from a list of block specifications.

    Each block_spec: {
        "model_id": str,
        "position": int,
        "enabled":  bool,
        "params":   dict,          # LLM-provided overrides (may be empty)
    }

    snapshots_spec (optional): list of up to 3 dicts:
        {
            "name":         str,   # max 12 chars
            "block_states": {"block0": bool, "block1": bool, ...}
        }

    Returns (hlx_dict, warnings) — hlx_dict is ready for json.dumps();
    warnings is a list of human-readable validation notes.
    """
    name = preset_name[:16]

    dsp0: dict = copy.deepcopy(_SYSTEM_BLOCKS)
    all_warnings: list[str] = []

    snapshot_blocks: dict[str, bool] = {}
    cab_counter = 0

    for i, spec in enumerate(blocks_spec[:_MAX_BLOCKS]):
        mid = spec.get("model_id", "")
        model = ALL_MODELS.get(mid)
        if model is None:
            continue

        position = max(0, min(_MAX_BLOCKS - 1, int(spec.get("position", i))))
        enabled  = bool(spec.get("enabled", True))
        raw_params = spec.get("params", {})
        key      = f"block{i}"

        sanitized_params, param_warns = _sanitize_params(model, raw_params)
        all_warnings.extend(param_warns)

        if model.category == "Amp":
            cab_key  = f"cab{cab_counter}"
            cab_mid  = model.paired_cab
            cab_mdl  = ALL_MODELS.get(cab_mid)
            if cab_mdl is None:
                # fall back to first available cab
                from hx_models import CAB_MODELS
                cab_mdl = CAB_MODELS[0]
            dsp0[cab_key] = _make_cab(cab_mdl)
            dsp0[key]     = _make_block(model, position, enabled,
                                        sanitized_params, cab_key)
            cab_counter  += 1
        else:
            dsp0[key] = _make_block(model, position, enabled, sanitized_params)

        snapshot_blocks[key] = enabled

    # Build snapshots 0-2 as valid, 3-7 as empty
    snapshots: dict = {}
    for idx in range(8):
        if idx < 3:
            # Use LLM-provided block states if available, else default to all enabled
            if snapshots_spec and idx < len(snapshots_spec):
                snap_spec  = snapshots_spec[idx]
                snap_name  = str(snap_spec.get("name", f"SNAPSHOT {idx + 1}"))[:12]
                raw_states = snap_spec.get("block_states", {})
                # Only keep keys that exist in snapshot_blocks; fill missing with default
                block_states = {
                    k: bool(raw_states.get(k, v))
                    for k, v in snapshot_blocks.items()
                }
            else:
                snap_name    = f"SNAPSHOT {idx + 1}"
                block_states = dict(snapshot_blocks)

            snapshots[f"snapshot{idx}"] = {
                "@ledcolor":    0,
                "@name":        snap_name,
                "@tempo":       120.0,
                "@valid":       True,
                "@pedalstate":  2,
                "blocks":       {"dsp0": block_states},
                "controllers":  {},
            }
        else:
            snapshots[f"snapshot{idx}"] = {
                "@ledcolor": 0,
                "@name":     f"SNAPSHOT {idx + 1}",
                "@tempo":    120.0,
                "@valid":    False,
                "@pedalstate": 0,
                "blocks":    {},
                "controllers": {},
            }

    tone: dict = {
        "dsp0":       dsp0,
        "dsp1":       {},
        "global": {
            "@model":            "@global_params",
            "@current_snapshot": 0,
            "@tempo":            120.0,
            "@topology0":        "A",
            "@topology1":        0,
            "@guitarinputZ":     0,
            "@pedalstate":       2,
        },
        "controller": {},
        "footswitch":  {},
        **snapshots,
    }

    return {
        "schema":  "L6Preset",
        "version": 6,
        "meta":    {"original": 0, "pbn": 0, "premium": 0},
        "data": {
            "device":         _HX_STOMP_DEVICE_ID,
            "device_version": 0,
            "meta": {
                "application": "HX Edit",
                "appversion":  0,
                "build_sha":   "",
                "modifieddate": int(time.time()),
                "name":        name,
            },
            "tone": tone,
        },
    }, all_warnings


def save_hlx(hlx_dict: dict, filepath: Path) -> None:
    """Write .hlx JSON to disk."""
    filepath.write_text(json.dumps(hlx_dict, indent=2))


# ---------------------------------------------------------------------------
# PresetResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class PresetResult:
    hlx_dict:               dict
    preset_name:            str
    description:            str
    blocks:                 list[dict]  # [{model_id, name, category, explanation}, ...]
    signal_chain_rationale: str
    prompt:                 str
    snapshots:              list[dict] = field(default_factory=list)
    # Each snapshot: {"name": str, "description": str, "block_states": {blockN: bool}}
    warnings:               list[str]  = field(default_factory=list)
    # Validation notes: clamped params, unknown model IDs, truncated blocks, etc.


# ---------------------------------------------------------------------------
# PresetCatalog
# ---------------------------------------------------------------------------

class PresetCatalog:
    """Tracks generated .hlx files with metadata in ~/.hxstomp/presets/."""

    _PRESETS_DIR  = Path.home() / ".hxstomp" / "presets"
    _CATALOG_FILE = _PRESETS_DIR / "catalog.json"

    def _ensure_dir(self) -> None:
        self._PRESETS_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        try:
            return json.loads(self._CATALOG_FILE.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _dump(self, entries: list[dict]) -> None:
        self._ensure_dir()
        self._CATALOG_FILE.write_text(json.dumps(entries, indent=2))

    @staticmethod
    def _sanitize(name: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")

    def save_preset(self, result: PresetResult, filepath: Path | None = None) -> Path:
        """
        Write the .hlx file and append a catalog entry.

        If `filepath` is None, auto-generate a path under ~/.hxstomp/presets/.
        Returns the path of the written file.
        """
        self._ensure_dir()
        if filepath is None:
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem     = self._sanitize(result.preset_name) or "preset"
            filepath = self._PRESETS_DIR / f"{stem}_{ts}.hlx"

        save_hlx(result.hlx_dict, filepath)

        entries = self._load()
        entries.append({
            "filename":               filepath.name,
            "preset_name":            result.preset_name,
            "description":            result.description,
            "created":                datetime.now().isoformat(timespec="seconds"),
            "prompt":                 result.prompt,
            "blocks":                 result.blocks,
            "signal_chain_rationale": result.signal_chain_rationale,
            "snapshots":              result.snapshots,
        })
        self._dump(entries)
        return filepath

    def list_presets(self) -> list[dict]:
        """Return all catalog entries, newest first."""
        return list(reversed(self._load()))

    def remove_entry(self, filename: str) -> None:
        """Remove a catalog entry (does not delete the file)."""
        entries = [e for e in self._load() if e.get("filename") != filename]
        self._dump(entries)


# ---------------------------------------------------------------------------
# Core generation function
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    """
    Extract JSON from an LLM response that may include markdown fences or prose.

    Handles:
    - Triple-backtick fences (``` or ```json)
    - Prose wrapping: "Here is the JSON:\n{...}\nHope this helps!"
    """
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text  = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    # Fallback: extract the outermost {...} object from any surrounding prose
    if not text.startswith("{"):
        start = text.find("{")
        end   = text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]

    return text.strip()


def _match_gear_hints(description: str) -> list[str]:
    """
    Case-insensitive substring scan of the user description against all
    model aliases.  Returns hint strings ready for injection into the LLM
    user message, e.g. "'Tube Screamer' → HD2_DistScream808 (Scream 808)".
    One hint per model (first matching alias wins).
    """
    desc_lower = description.lower()
    seen_ids: set[str] = set()
    hints: list[str] = []
    for model in ALL_MODELS.values():
        if not model.aliases or model.model_id in seen_ids:
            continue
        for alias in model.aliases:
            if alias.lower() in desc_lower:
                hints.append(
                    f"'{alias}' \u2192 {model.model_id} ({model.name})"
                )
                seen_ids.add(model.model_id)
                break
    return hints


def _fuzzy_recover_model_id(unknown_id: str) -> tuple[HXModel | None, str]:
    """
    Attempt to recover a hallucinated model_id by token-matching against the
    catalog.  Returns (matched_model, display_name) or (None, reason).

    Steps:
      1. Infer category from the ID prefix (HD2_Amp* → Amp, etc.)
      2. Extract the name fragment after the prefix and tokenize camel-case words
         ("FenderDeluxeNrm" → ["fender", "deluxe"])
      3. Score each category candidate:
           +2 per token found in model.name
           +3 per token found in any model.alias
      4. Return the highest-scoring model if score >= 2, else None.
    """
    candidates = list(ALL_MODELS.values())
    fragment   = unknown_id
    for prefix, cat in _PREFIX_CAT:
        if unknown_id.startswith(prefix):
            candidates = [m for m in ALL_MODELS.values() if m.category == cat]
            fragment   = unknown_id[len(prefix):]   # strip "HD2_Amp", "HD2_Delay", etc.
            break
    else:
        # No prefix matched — strip only "HD2_" so tokens don't include the literal prefix
        fragment = unknown_id.split("_", 1)[-1] if "_" in unknown_id else unknown_id
    tokens = [
        t.lower()
        for t in re.findall(r"[A-Z][a-z]+|[A-Z]+(?=[A-Z]|$)|[a-z]+", fragment)
        if len(t) > 2
    ]
    if not tokens:
        return None, "no tokens extracted"

    best_score, best_model = 0, None
    for model in candidates:
        score = 0
        name_lower = model.name.lower()
        for tok in tokens:
            if tok in name_lower:
                score += 2
        for alias in model.aliases:
            alias_lower = alias.lower()
            for tok in tokens:
                if tok in alias_lower:
                    score += 3
        if score > best_score:
            best_score, best_model = score, model

    if best_model and best_score >= 2:
        return best_model, best_model.name
    return None, "no confident match"


def generate_hlx_preset(description: str, provider) -> PresetResult:
    """
    Ask the LLM to design an HX Stomp preset for the given description.

    Returns a PresetResult containing the constructed .hlx dict plus metadata
    (block list with explanations, rationale, etc.).

    Retries once on JSON parse failure.
    Raises LLMGenerationError on API failure or persistent parse errors.
    """
    from llm_generator import LLMGenerationError  # lazy import (avoids tkinter at module load)

    system_prompt = _build_system_prompt()
    last_exc: Exception | None = None

    # Pre-match real-world gear names to model_ids before the first API call
    hints = _match_gear_hints(description)
    base_msg = description
    if hints:
        base_msg = (
            description
            + "\n\nGear Match Hints — use these model_ids for the gear named above:\n"
            + "\n".join(f"- {h}" for h in hints)
        )

    for attempt in range(2):
        try:
            # On retry, prepend a context hint so weaker models know what failed
            user_msg = base_msg
            if attempt > 0 and last_exc is not None:
                user_msg = (
                    f"{base_msg}\n\n"
                    f"Note: previous attempt failed ({last_exc}). "
                    "Return ONLY a JSON object — no markdown, no prose. "
                    "Use ONLY model_ids from the catalog."
                )

            raw  = provider.complete(system_prompt, user_msg,
                                     max_tokens=_HLX_MAX_TOKENS)
            data = json.loads(_strip_fences(raw))

            preset_name = str(data.get("preset_name", "New Preset"))[:16]
            tone_desc   = str(data.get("description", ""))
            rationale   = str(data.get("signal_chain_rationale", ""))
            raw_blocks  = data.get("blocks", [])

            if not isinstance(raw_blocks, list) or not raw_blocks:
                raise ValueError("No blocks in response")

            total_raw = len(raw_blocks)

            # Validate model IDs; try fuzzy recovery before discarding unknowns
            valid_blocks:  list[dict] = []
            skipped_ids:   list[str]  = []
            recovered_ids: list[str]  = []
            for blk in raw_blocks:
                mid = str(blk.get("model_id", ""))
                if mid in ALL_MODELS:
                    valid_blocks.append(blk)
                else:
                    recovered, note = _fuzzy_recover_model_id(mid)
                    if recovered:
                        blk = {**blk, "model_id": recovered.model_id}
                        valid_blocks.append(blk)
                        recovered_ids.append(
                            f"'{mid}' \u2192 {recovered.model_id} ({note})"
                        )
                    else:
                        skipped_ids.append(mid or "<empty>")

            # Check signal chain category order (warn only, do not reorder)
            order_warnings: list[str] = []
            prev_rank, prev_label = -1, ""
            for blk in valid_blocks:
                mdl  = ALL_MODELS[blk["model_id"]]
                rank = _CHAIN_RANK.get(mdl.category, 99)
                if rank < prev_rank:
                    order_warnings.append(
                        f"Signal order: '{mdl.name} ({mdl.category})' at pos "
                        f"{blk.get('position', '?')} follows '{prev_label}' — "
                        "chain may not sound as intended"
                    )
                if rank != 7:  # don't track Cab (auto-paired, not user-positioned)
                    prev_rank  = rank
                    prev_label = f"{mdl.name} ({mdl.category})"

            # Track blocks truncated beyond the 6-block limit
            truncated = max(0, len(valid_blocks) - _MAX_BLOCKS)
            valid_blocks = valid_blocks[:_MAX_BLOCKS]

            # Require at least one amp block
            amp_blocks = [b for b in valid_blocks
                          if ALL_MODELS[b["model_id"]].category == "Amp"]
            if not amp_blocks:
                raise ValueError("No valid amp block in response")

            # Build flat block metadata list for UI display
            block_meta: list[dict] = []
            for blk in valid_blocks:
                mdl = ALL_MODELS[blk["model_id"]]
                block_meta.append({
                    "model_id":    mdl.model_id,
                    "name":        mdl.name,
                    "category":    mdl.category,
                    "explanation": str(blk.get("explanation", "")),
                    "enabled":     bool(blk.get("enabled", True)),
                })

            # Parse snapshot specs from LLM response
            raw_snapshots = data.get("snapshots", [])
            snapshots_spec: list[dict] = []
            if isinstance(raw_snapshots, list):
                for snap in raw_snapshots[:3]:
                    if isinstance(snap, dict):
                        snapshots_spec.append({
                            "name":        str(snap.get("name", ""))[:12],
                            "description": str(snap.get("description", "")),
                            "block_states": snap.get("block_states", {}),
                        })

            # Build the .hlx structure
            blocks_spec = [
                {
                    "model_id": b["model_id"],
                    "position": int(b.get("position", i)),
                    "enabled":  bool(b.get("enabled", True)),
                    "params":   b.get("params", {}),
                }
                for i, b in enumerate(valid_blocks)
            ]
            hlx, param_warnings = build_hlx(
                preset_name, blocks_spec,
                snapshots_spec if snapshots_spec else None,
            )

            # Accumulate all generation warnings
            gen_warnings: list[str] = []
            gen_warnings.extend(order_warnings)
            for r in recovered_ids:
                gen_warnings.append(f"Auto-recovered: {r}")
            if skipped_ids:
                ids_str  = ", ".join(skipped_ids[:3])
                ellipsis = "…" if len(skipped_ids) > 3 else ""
                gen_warnings.append(
                    f"{len(skipped_ids)} model(s) not in catalog, skipped: "
                    f"{ids_str}{ellipsis}"
                )
            if truncated:
                gen_warnings.append(
                    f"{truncated} block(s) beyond the {_MAX_BLOCKS}-block "
                    "limit were dropped"
                )
            gen_warnings.extend(param_warnings)

            return PresetResult(
                hlx_dict               = hlx,
                preset_name            = preset_name,
                description            = tone_desc,
                blocks                 = block_meta,
                signal_chain_rationale = rationale,
                prompt                 = description,
                snapshots              = snapshots_spec,
                warnings               = gen_warnings,
            )

        except LLMGenerationError:
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            last_exc = exc

    raise LLMGenerationError(
        f"Could not parse .hlx generation response: {last_exc}"
    )
