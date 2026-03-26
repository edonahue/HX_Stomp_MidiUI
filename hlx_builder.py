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


# ---------------------------------------------------------------------------
# System prompt for .hlx generation
# ---------------------------------------------------------------------------

def _build_system_prompt() -> str:
    catalog = catalog_for_prompt()
    return f"""\
You are a guitar tone designer for the Line 6 HX Stomp processor.
Given a tone description or artist to emulate, choose amp/effect models and
parameters to create a complete signal chain with 3 distinct snapshots.

CONSTRAINTS:
- Maximum {_MAX_BLOCKS} processing blocks (HX Stomp limit)
- Always include exactly ONE amp block
- Signal chain ordering: Dynamics → Distortion → Amp → EQ → Modulation → Delay → Reverb
- Preset name: max 16 characters, title case
- Parameter values: most knobs are 0.0–1.0 (floats); Level/Gain use real dB
  values (e.g. -3.0); HighCut/LowCut use Hz (e.g. 8000.0); Threshold uses
  negative dB (e.g. -65.0)

AVAILABLE MODELS (use ONLY model_ids from this list):
{catalog}

SNAPSHOTS:
Define exactly 3 snapshots with distinct purposes suited to the tone (e.g.
Rhythm / Lead / Clean, or Verse / Chorus / Solo).
For each snapshot specify which blocks are active (true) or bypassed (false).
The amp block should almost always stay active.
Snapshot names: max 12 characters.

Respond with ONLY a JSON object — no markdown, no extra text.

Required format:
{{
  "preset_name": "<name, max 16 chars>",
  "description": "<1-2 sentence tone description>",
  "blocks": [
    {{
      "model_id": "<exact model_id from list above>",
      "position": <integer 0-5, signal chain order>,
      "enabled": true,
      "params": {{"<param>": <value>, ...}},
      "explanation": "<why this model was chosen, 1 sentence>"
    }}
  ],
  "signal_chain_rationale": "<brief overall chain design explanation>",
  "snapshots": [
    {{
      "name": "<snapshot name, max 12 chars>",
      "description": "<one sentence>",
      "block_states": {{"block0": true, "block1": true, "block2": false}}
    }},
    {{
      "name": "<snapshot name>",
      "description": "<one sentence>",
      "block_states": {{"block0": true, "block1": true, "block2": true}}
    }},
    {{
      "name": "<snapshot name>",
      "description": "<one sentence>",
      "block_states": {{"block0": false, "block1": true, "block2": false}}
    }}
  ]
}}"""


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


def build_hlx(preset_name: str, blocks_spec: list[dict],
              snapshots_spec: list[dict] | None = None) -> dict:
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

    Returns the full .hlx dict ready for json.dumps().
    """
    name = preset_name[:16]

    dsp0: dict = copy.deepcopy(_SYSTEM_BLOCKS)

    snapshot_blocks: dict[str, bool] = {}
    cab_counter = 0

    for i, spec in enumerate(blocks_spec[:_MAX_BLOCKS]):
        mid = spec.get("model_id", "")
        model = ALL_MODELS.get(mid)
        if model is None:
            continue

        position = int(spec.get("position", i))
        enabled  = bool(spec.get("enabled", True))
        params   = spec.get("params", {})
        key      = f"block{i}"

        if model.category == "Amp":
            cab_key  = f"cab{cab_counter}"
            cab_mid  = model.paired_cab
            cab_mdl  = ALL_MODELS.get(cab_mid)
            if cab_mdl is None:
                # fall back to first available cab
                from hx_models import CAB_MODELS
                cab_mdl = CAB_MODELS[0]
            dsp0[cab_key] = _make_cab(cab_mdl)
            dsp0[key]     = _make_block(model, position, enabled, params, cab_key)
            cab_counter  += 1
        else:
            dsp0[key] = _make_block(model, position, enabled, params)

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
    }


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
    """Remove optional markdown code fences from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text  = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


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

    for attempt in range(2):
        try:
            raw  = provider.complete(system_prompt, description,
                                     max_tokens=_HLX_MAX_TOKENS)
            data = json.loads(_strip_fences(raw))

            preset_name = str(data.get("preset_name", "New Preset"))[:16]
            tone_desc   = str(data.get("description", ""))
            rationale   = str(data.get("signal_chain_rationale", ""))
            raw_blocks  = data.get("blocks", [])

            if not isinstance(raw_blocks, list) or not raw_blocks:
                raise ValueError("No blocks in response")

            # Validate model IDs; skip unknowns
            valid_blocks: list[dict] = []
            for blk in raw_blocks:
                mid = str(blk.get("model_id", ""))
                if mid in ALL_MODELS:
                    valid_blocks.append(blk)

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
            hlx = build_hlx(preset_name, blocks_spec,
                            snapshots_spec if snapshots_spec else None)

            return PresetResult(
                hlx_dict               = hlx,
                preset_name            = preset_name,
                description            = tone_desc,
                blocks                 = block_meta,
                signal_chain_rationale = rationale,
                prompt                 = description,
                snapshots              = snapshots_spec,
            )

        except LLMGenerationError:
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            last_exc = exc

    raise LLMGenerationError(
        f"Could not parse .hlx generation response: {last_exc}"
    )
