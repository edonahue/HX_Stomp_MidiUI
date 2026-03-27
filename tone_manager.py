"""
tone_manager.py

Manages a collection of named "tones" — each tone maps a friendly label
to the MIDI parameters needed to recall it on the HX Stomp.

A tone definition (dict / JSON):
    {
        "name":      "Clean Surf",   # Display label
        "preset":    3,              # Program Change number (0-127)
        "snapshot":  0,              # Snapshot index (0-7), default 0
        "bank_msb":  0,              # Bank Select MSB, usually 0
        "bank_lsb":  0,              # Bank Select LSB (setlist 0-3)
        "color":     "#4A90D9",      # Button color for the UI (optional)
        "category":  "Clean"         # Grouping label (optional)
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Tone:
    name:     str
    preset:   int
    snapshot: int           = 0
    bank_msb: int           = 0
    bank_lsb: int           = 0
    color:    str           = "#4A90D9"
    category: Optional[str] = None

    def validate(self) -> None:
        if not 0 <= self.preset <= 127:
            raise ValueError(f"preset must be 0-127, got {self.preset}")
        if not 0 <= self.snapshot <= 7:
            raise ValueError(f"snapshot must be 0-7, got {self.snapshot}")
        if not 0 <= self.bank_msb <= 127:
            raise ValueError(f"bank_msb must be 0-127, got {self.bank_msb}")
        if not 0 <= self.bank_lsb <= 127:
            raise ValueError(f"bank_lsb must be 0-127, got {self.bank_lsb}")

    def to_dict(self) -> dict:
        d = asdict(self)
        # Drop None values to keep JSON tidy
        return {k: v for k, v in d.items() if v is not None}

    @classmethod
    def from_dict(cls, d: dict) -> "Tone":
        return cls(
            name     = d["name"],
            preset   = int(d["preset"]),
            snapshot = int(d.get("snapshot", 0)),
            bank_msb = int(d.get("bank_msb", 0)),
            bank_lsb = int(d.get("bank_lsb", 0)),
            color    = d.get("color", "#4A90D9"),
            category = d.get("category"),
        )


class ToneManager:
    """
    Loads, saves, and provides access to a list of Tone objects.
    """

    def __init__(self, filepath: str | Path = "presets.json"):
        self.filepath = Path(filepath)
        self._tones: list[Tone] = []
        if self.filepath.exists():
            self.load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @property
    def tones(self) -> list[Tone]:
        return list(self._tones)

    def get(self, name: str) -> Tone | None:
        return next((t for t in self._tones if t.name == name), None)

    def add(self, tone: Tone) -> None:
        tone.validate()
        if any(t.name == tone.name for t in self._tones):
            raise ValueError(f"A tone named '{tone.name}' already exists.")
        self._tones.append(tone)

    def update(self, tone: Tone) -> None:
        tone.validate()
        for i, t in enumerate(self._tones):
            if t.name == tone.name:
                self._tones[i] = tone
                return
        raise KeyError(f"No tone named '{tone.name}' found.")

    def remove(self, name: str) -> None:
        before = len(self._tones)
        self._tones = [t for t in self._tones if t.name != name]
        if len(self._tones) == before:
            raise KeyError(f"No tone named '{name}' found.")

    def categories(self) -> list[str]:
        seen, cats = set(), []
        for t in self._tones:
            c = t.category or "Uncategorized"
            if c not in seen:
                seen.add(c)
                cats.append(c)
        return cats

    def tones_by_category(self) -> dict[str, list[Tone]]:
        result: dict[str, list[Tone]] = {}
        for tone in self._tones:
            cat = tone.category or "Uncategorized"
            result.setdefault(cat, []).append(tone)
        return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        with open(self.filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Could not parse {self.filepath}: {exc}"
                ) from exc
        try:
            self._tones = [Tone.from_dict(d) for d in data]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                f"Malformed entry in {self.filepath}: missing field {exc}"
            ) from exc
        print(f"[ToneManager] Loaded {len(self._tones)} tones from {self.filepath}")

    def save(self) -> None:
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self._tones], f, indent=2)
        print(f"[ToneManager] Saved {len(self._tones)} tones to {self.filepath}")

    def reload(self) -> None:
        self.load()
