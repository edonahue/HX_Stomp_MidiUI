"""
llm_generator.py

LLM-powered tone generation for the HX Stomp Soundboard.

Supports multiple providers: Anthropic (Claude), OpenAI, Ollama (local), Gemini.
Only the `anthropic` package is required for the default provider; others are
optional and detected at runtime.

Config is persisted to ~/.hxstomp/config.json.
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from tone_manager import Tone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONFIG_PATH    = Path.home() / ".hxstomp" / "config.json"
_MAX_TOKENS     = 200
_HLX_MAX_TOKENS = 1500

_SYSTEM_PROMPT = """\
You are a MIDI tone assistant for the Line 6 HX Stomp guitar processor.
Respond with ONLY a JSON object — no markdown, no explanation.

Required fields:
{
  "name":     "<tone name, max 20 chars, title case>",
  "category": "<one of: Clean | Overdrive | High Gain | Fuzz | Ambient | Bass | Acoustic | Other>",
  "snapshot": <integer 0-2, 0=default, 1=light variation, 2=heavy variation>,
  "color":    "<6-digit hex like #E67E22 that visually represents the tone character>"
}

Do not include preset, bank_msb, or bank_lsb."""

# UI palette (mirrors soundboard_ui constants)
_TEXT_DIM    = "#888888"
_TEXT_BRIGHT = "#e0e0e0"
_ACCENT      = "#4A90D9"
_COL_DISC    = "#e74c3c"
_BG_TOOLBAR  = "#1e1e1e"
_BG_SURFACE  = "#1e1e1e"
_BG_CARD     = "#252525"
_BG_INPUT    = "#2d2d2d"
_BORDER_DIM    = "#333333"
_BG_TEXT_INPUT = "#2b2b2b"
_TEXT_WARN     = "#e8a838"
_BG_WARN       = "#2a2000"

_PROVIDER_COLORS: dict[str, str] = {
    "anthropic": "#d97706",
    "openai":    "#10a37f",
    "gemini":    "#4285f4",
    "ollama":    "#6366f1",
}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Read ~/.hxstomp/config.json or return empty dict."""
    try:
        return json.loads(_CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict) -> None:
    """Write config dict to ~/.hxstomp/config.json, creating the dir."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


# ---------------------------------------------------------------------------
# Provider abstraction
# ---------------------------------------------------------------------------

class LLMGenerationError(Exception):
    """Raised when tone generation fails for any reason."""


class LLMProvider(ABC):
    name: str           # e.g. "anthropic"
    label: str          # e.g. "Anthropic (Claude)"
    requires_key: bool  # False for Ollama
    default_model: str
    env_var: str = ""   # env variable checked for API key (empty = none needed)

    def __init__(self, api_key: str = "", model: str = "", base_url: str = ""):
        self.api_key  = api_key  or ""
        self.model    = model    or self.default_model
        self.base_url = base_url or ""

    @abstractmethod
    def complete(self, system: str, user: str,
                 max_tokens: int = _MAX_TOKENS) -> str:
        """Return raw text response. Raise LLMGenerationError on failure."""


class AnthropicProvider(LLMProvider):
    name          = "anthropic"
    label         = "Anthropic (Claude)"
    requires_key  = True
    default_model = "claude-haiku-4-5"
    env_var       = "ANTHROPIC_API_KEY"

    def complete(self, system: str, user: str,
                 max_tokens: int = _MAX_TOKENS) -> str:
        try:
            import anthropic  # type: ignore
        except ImportError as exc:
            raise LLMGenerationError(
                "anthropic package not installed. Run: pip install anthropic"
            ) from exc
        key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise LLMGenerationError(
                "No Anthropic API key. Set ANTHROPIC_API_KEY or configure via ⚙ Configure…"
            )
        client = anthropic.Anthropic(api_key=key, timeout=60.0)
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text
        except Exception as exc:
            raise LLMGenerationError(f"Anthropic API error: {exc}") from exc


class OpenAIProvider(LLMProvider):
    name          = "openai"
    label         = "OpenAI (GPT)"
    requires_key  = True
    default_model = "gpt-4o-mini"
    env_var       = "OPENAI_API_KEY"

    def complete(self, system: str, user: str,
                 max_tokens: int = _MAX_TOKENS) -> str:
        try:
            import openai  # type: ignore
        except ImportError as exc:
            raise LLMGenerationError(
                "openai package not installed. Run: pip install openai"
            ) from exc
        key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise LLMGenerationError(
                "No OpenAI API key. Set OPENAI_API_KEY or configure via ⚙ Configure…"
            )
        client = openai.OpenAI(api_key=key, timeout=60.0)
        try:
            resp = client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            raise LLMGenerationError(f"OpenAI API error: {exc}") from exc


class OllamaProvider(LLMProvider):
    name          = "ollama"
    label         = "Ollama (local)"
    requires_key  = False
    default_model = "llama3.2"

    def complete(self, system: str, user: str,
                 max_tokens: int = _MAX_TOKENS) -> str:
        base    = (self.base_url or "http://localhost:11434").rstrip("/")
        url     = f"{base}/api/chat"
        payload = json.dumps({
            "model":  self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "options": {"num_predict": max_tokens},
        }).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data["message"]["content"]
        except urllib.error.URLError as exc:
            raise LLMGenerationError(
                f"Ollama not reachable at {base}. Is it running?"
            ) from exc
        except (KeyError, json.JSONDecodeError) as exc:
            raise LLMGenerationError(f"Unexpected Ollama response: {exc}") from exc


class GeminiProvider(LLMProvider):
    name          = "gemini"
    label         = "Google Gemini"
    requires_key  = True
    default_model = "gemini-1.5-flash"
    env_var       = "GOOGLE_API_KEY"

    def complete(self, system: str, user: str,
                 max_tokens: int = _MAX_TOKENS) -> str:
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as exc:
            raise LLMGenerationError(
                "google-generativeai not installed. "
                "Run: pip install google-generativeai"
            ) from exc
        key = self.api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            raise LLMGenerationError(
                "No Google API key. Set GOOGLE_API_KEY or configure via ⚙ Configure…"
            )
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_name=self.model,
                                      system_instruction=system)
        try:
            resp = model.generate_content(
                user,
                generation_config={"max_output_tokens": max_tokens},
                request_options={"timeout": 60},
            )
            return resp.text
        except Exception as exc:
            raise LLMGenerationError(f"Gemini API error: {exc}") from exc


# Registry of all known providers (order = dropdown display order)
PROVIDERS: list[type[LLMProvider]] = [
    AnthropicProvider, OpenAIProvider, OllamaProvider, GeminiProvider
]


def get_provider(cfg: dict) -> LLMProvider:
    """Instantiate the provider specified in config (defaults to Anthropic)."""
    name = cfg.get("provider", "anthropic")
    cls  = next((p for p in PROVIDERS if p.name == name), None)
    if cls is None:
        known = [p.name for p in PROVIDERS]
        print(f"[LLM] Unknown provider '{name}' (known: {known}). "
              "Falling back to Anthropic.")
        cls = AnthropicProvider
    return cls(
        api_key  = cfg.get(f"{name}_api_key",  ""),
        model    = cfg.get(f"{name}_model",    ""),
        base_url = cfg.get(f"{name}_base_url", ""),
    )


# ---------------------------------------------------------------------------
# Core generation function
# ---------------------------------------------------------------------------

def generate_tone(description: str, provider: LLMProvider) -> Tone:
    """
    Ask the provider to generate tone metadata for `description`.

    Returns a Tone with preset=0 / bank_msb=0 / bank_lsb=0 so the user can
    fill in the correct preset number in the follow-up ToneDialog.

    Retries once on JSON parse failure. Raises LLMGenerationError on any error.
    """
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            raw  = provider.complete(_SYSTEM_PROMPT, description)
            text = raw.strip()
            # Strip optional markdown code fences
            if text.startswith("```"):
                parts = text.split("```")
                text  = parts[1] if len(parts) > 1 else text
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())
            return Tone(
                name     = str(data["name"])[:20],
                preset   = 0,
                snapshot = max(0, min(2, int(data.get("snapshot", 0)))),
                bank_msb = 0,
                bank_lsb = 0,
                color    = str(data.get("color", "#4A90D9")),
                category = str(data.get("category", "Other")) or None,
            )
        except LLMGenerationError:
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
    raise LLMGenerationError(f"Could not parse JSON response: {last_exc}")


# ---------------------------------------------------------------------------
# ProviderConfigDialog
# ---------------------------------------------------------------------------

class ProviderConfigDialog(ctk.CTkToplevel):
    """Configure API key / endpoint for one LLM provider."""

    def __init__(self, parent, provider_name: str):
        super().__init__(parent)
        self.title("Configure Provider")
        self.resizable(False, False)
        self.transient(parent)
        self.lift()
        self.after(10, self._safe_grab)

        self._name = provider_name
        self._cfg  = load_config()
        cls = next((p for p in PROVIDERS if p.name == provider_name),
                   AnthropicProvider)

        pad = {"padx": 12, "pady": 6}
        row = 0

        # Header row: colored badge + provider name
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        badge_color = _PROVIDER_COLORS.get(provider_name, _ACCENT)
        ctk.CTkFrame(header, width=14, height=14, corner_radius=4,
                     fg_color=badge_color).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            header, text=cls.label,
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w",
        ).pack(side="left")
        row += 1

        self._fields: dict[str, tk.StringVar] = {}

        _KEY_SOURCES = {
            "anthropic": "Get a key at console.anthropic.com → API Keys",
            "openai":    "Get a key at platform.openai.com → API Keys",
            "gemini":    "Get a free key at aistudio.google.com → Get API Key",
            "ollama":    "No key needed — just run: ollama serve",
        }

        if cls.requires_key:
            ctk.CTkLabel(self, text="API Key", anchor="w", width=90).grid(
                row=row, column=0, sticky="w", **pad)
            var = tk.StringVar(
                value=self._cfg.get(f"{provider_name}_api_key", ""))
            self._fields["api_key"] = var
            ctk.CTkEntry(self, textvariable=var, width=280, show="*").grid(
                row=row, column=1, **pad)
            row += 1
        else:
            ctk.CTkLabel(self, text="Base URL", anchor="w", width=90).grid(
                row=row, column=0, sticky="w", **pad)
            var = tk.StringVar(
                value=self._cfg.get(f"{provider_name}_base_url",
                                    "http://localhost:11434"))
            self._fields["base_url"] = var
            ctk.CTkEntry(self, textvariable=var, width=280).grid(
                row=row, column=1, **pad)
            row += 1

        hint = _KEY_SOURCES.get(provider_name, "")
        if hint:
            ctk.CTkLabel(
                self, text=hint,
                font=ctk.CTkFont(size=10), text_color=_TEXT_DIM,
                anchor="w", wraplength=300, justify="left",
            ).grid(row=row, column=0, columnspan=2, sticky="w",
                   padx=12, pady=(0, 4))
            row += 1

        ctk.CTkLabel(self, text="Model", anchor="w", width=90).grid(
            row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(
            value=self._cfg.get(f"{provider_name}_model", cls.default_model))
        self._fields["model"] = var
        ctk.CTkEntry(self, textvariable=var, width=280).grid(
            row=row, column=1, **pad)
        row += 1

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=12)
        ctk.CTkButton(btn_frame, text="Save",
                      command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(
            btn_frame, text="Cancel",
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self.destroy,
        ).pack(side="left", padx=6)

    def _save(self) -> None:
        from tkinter import messagebox as _mb
        name = self._name
        cls  = next((p for p in PROVIDERS if p.name == name), AnthropicProvider)
        if cls.requires_key:
            api_key = self._fields.get("api_key", tk.StringVar()).get().strip()
            if not api_key:
                if not _mb.askokcancel(
                    "Empty API Key",
                    f"No API key entered for {cls.label}.\n"
                    "Generation won't work without a key. Save anyway?",
                    parent=self,
                ):
                    return
        for key, var in self._fields.items():
            self._cfg[f"{name}_{key}"] = var.get().strip()
        save_config(self._cfg)
        self.destroy()
    def _safe_grab(self):
        try:
            self.wait_visibility()
            self.grab_set()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# GenerateToneDialog
# ---------------------------------------------------------------------------

class GenerateToneDialog(ctk.CTkToplevel):
    """
    Dialog that calls an LLM to generate tone metadata from a text description.
    Invokes `on_tone_generated(tone)` on success, then closes itself.
    """

    def __init__(self, parent, on_tone_generated: Callable[[Tone], None]):
        super().__init__(parent)
        self.title("Generate Tone with AI")
        self.resizable(False, False)
        self.grab_set()

        self._on_tone_generated = on_tone_generated
        self._cfg     = load_config()
        self._loading = False

        self._build()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _available_labels(self) -> list[str]:
        return [cls.label for cls in PROVIDERS]

    def _label_to_name(self, label: str) -> str:
        for cls in PROVIDERS:
            if cls.label == label:
                return cls.name
        return "anthropic"

    def _name_to_label(self, name: str) -> str:
        for cls in PROVIDERS:
            if cls.name == name:
                return cls.label
        return AnthropicProvider.label

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        pad = {"padx": 14, "pady": 6}

        # Provider row
        prov_frame = ctk.CTkFrame(self, fg_color="transparent")
        prov_frame.pack(fill="x", **pad)

        ctk.CTkLabel(prov_frame, text="Provider:", width=70,
                     anchor="w").pack(side="left")

        current_label = self._name_to_label(
            self._cfg.get("provider", "anthropic"))
        self._prov_var = tk.StringVar(value=current_label)
        ctk.CTkOptionMenu(
            prov_frame,
            variable=self._prov_var,
            values=self._available_labels(),
            width=200,
            command=self._on_provider_changed,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            prov_frame, text="⚙  Configure…", width=115,
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self._configure_provider,
        ).pack(side="left")

        # Active model readout — dim, updates on provider change / configure save
        self._model_lbl = ctk.CTkLabel(
            prov_frame, text="",
            font=ctk.CTkFont(size=10), text_color=_TEXT_DIM, anchor="w")
        self._model_lbl.pack(side="left", padx=(10, 0))

        # Key warning — amber, shown only when key is absent for a cloud provider
        self._key_warn_lbl = ctk.CTkLabel(
            self, text="",
            text_color=_TEXT_WARN,
            font=ctk.CTkFont(size=11),
            anchor="w", wraplength=400, justify="left")
        # Not packed here — shown/hidden by _refresh_provider_ui()

        # Description label
        ctk.CTkLabel(self, text="Describe your tone:", anchor="w").pack(
            fill="x", padx=14, pady=(8, 2))

        # Multi-line text area
        txt_frame = ctk.CTkFrame(self, fg_color=_BG_TEXT_INPUT, corner_radius=6)
        txt_frame.pack(fill="x", padx=14, pady=(0, 4))
        self._text = tk.Text(
            txt_frame,
            height=4, width=46,
            wrap="word",
            bg=_BG_TEXT_INPUT, fg=_TEXT_BRIGHT,
            insertbackground=_TEXT_BRIGHT,
            relief="flat", bd=0,
            font=("Helvetica", 12),
            padx=8, pady=8,
        )
        self._text.pack(fill="x", padx=2, pady=2)
        self._text.focus_set()

        # Hint — explains what the LLM generates vs what the user must supply
        ctk.CTkLabel(
            self,
            text="AI suggests a name, card color, category, and snapshot index "
                 "for your soundboard grid.\n"
                 "You'll enter the preset number in the next step — it's specific "
                 "to your rig. To generate a full .hlx preset file with amp and "
                 "effects, use 📦 Preset instead.",
            font=ctk.CTkFont(size=10),
            text_color=_TEXT_DIM,
            anchor="w", justify="left", wraplength=440,
        ).pack(fill="x", padx=14, pady=(2, 6))

        # Progress bar (created but not packed; shown during loading)
        self._progress = ctk.CTkProgressBar(self, mode="indeterminate")

        # Status label
        self._status_lbl = ctk.CTkLabel(
            self, text="", text_color=_TEXT_DIM,
            font=ctk.CTkFont(size=11), anchor="w")
        self._status_lbl.pack(fill="x", padx=14, pady=(0, 2))

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(4, 14))

        # Initialise both dynamic labels
        self._refresh_provider_ui()
        self._gen_btn = ctk.CTkButton(
            btn_frame, text="✨  Generate", width=120,
            command=self._start_generate)
        self._gen_btn.pack(side="left", padx=6)
        ctk.CTkButton(
            btn_frame, text="Cancel", width=90,
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self.destroy,
        ).pack(side="left", padx=6)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _refresh_provider_ui(self) -> None:
        """Update the model label and key warning to reflect the current provider."""
        name = self._label_to_name(self._prov_var.get())
        cls  = next((p for p in PROVIDERS if p.name == name), AnthropicProvider)

        # Model readout
        model = self._cfg.get(f"{name}_model", "") or cls.default_model
        self._model_lbl.configure(text=f"using {model}")

        # Key warning (cloud providers only)
        if cls.requires_key:
            has_key = bool(
                self._cfg.get(f"{name}_api_key")
                or (cls.env_var and os.environ.get(cls.env_var))
            )
            if has_key:
                self._key_warn_lbl.pack_forget()
            else:
                self._key_warn_lbl.configure(
                    text=f"⚠  No API key for {cls.label}. "
                         f"Click ⚙ Configure… above to add your key, "
                         f"or switch to Ollama (local) for keyless use.")
                self._key_warn_lbl.pack(fill="x", padx=14, pady=(0, 4))
        else:
            self._key_warn_lbl.pack_forget()

    def _on_provider_changed(self, label: str) -> None:
        self._cfg["provider"] = self._label_to_name(label)
        save_config(self._cfg)
        self._refresh_provider_ui()

    def _configure_provider(self) -> None:
        name = self._label_to_name(self._prov_var.get())
        dlg  = ProviderConfigDialog(self, name)
        self.wait_window(dlg)
        self._cfg = load_config()
        self._refresh_provider_ui()

    def _set_loading(self, loading: bool) -> None:
        self._loading = loading
        if loading:
            self._gen_btn.configure(state="disabled", text="Generating…")
            self._progress.pack(fill="x", padx=14, pady=(0, 4),
                                 before=self._status_lbl)
            self._progress.start()
        else:
            self._progress.stop()
            self._progress.pack_forget()
            self._gen_btn.configure(state="normal", text="✨  Generate")

    def _start_generate(self) -> None:
        description = self._text.get("1.0", "end").strip()
        if not description:
            self._status_lbl.configure(
                text="Please describe your tone first.",
                text_color=_COL_DISC)
            return
        self._status_lbl.configure(text="", text_color=_TEXT_DIM)
        self._set_loading(True)
        threading.Thread(target=self._worker, args=(description,),
                         daemon=True).start()

    def _worker(self, description: str) -> None:
        try:
            provider = get_provider(self._cfg)
            tone     = generate_tone(description, provider)
            self.after(0, lambda: self._on_result(tone))
        except LLMGenerationError as exc:
            msg = str(exc)
            self.after(0, lambda m=msg: self._on_error(m))

    def _on_result(self, tone: Tone) -> None:
        self._set_loading(False)
        self.destroy()
        self._on_tone_generated(tone)

    def _on_error(self, msg: str) -> None:
        self._set_loading(False)
        self._status_lbl.configure(text=f"Error: {msg}",
                                    text_color=_COL_DISC)


# ---------------------------------------------------------------------------
# GeneratePresetDialog
# ---------------------------------------------------------------------------

# Category label → short emoji badge shown in the signal chain strip
_CAT_BADGE: dict[str, str] = {
    "Amp":        "🎸",
    "Distortion": "🔥",
    "Dynamics":   "⚡",
    "EQ":         "🎛",
    "Modulation": "🌀",
    "Delay":      "🔁",
    "Reverb":     "🌊",
    "Cab":        "📦",
}

_CAT_COLOR: dict[str, str] = {
    "Amp":        "#c0392b",
    "Distortion": "#e67e22",
    "Dynamics":   "#2980b9",
    "EQ":         "#8e44ad",
    "Modulation": "#16a085",
    "Delay":      "#2471a3",
    "Reverb":     "#1a6b8a",
    "Cab":        "#555555",
}

# Snapshot pill colors — blue / purple / green for slots 0, 1, 2
_SNAP_COLORS: tuple[str, ...] = ("#2c5f8a", "#5a3c82", "#2e6b4f")


# ---------------------------------------------------------------------------
# HLXWorkspacePanel  — embeddable CTkFrame (used in the HLX Generator tab)
# ---------------------------------------------------------------------------

class HLXWorkspacePanel(ctk.CTkFrame):
    """
    Embeddable version of GeneratePresetDialog content.

    Can be placed directly inside a tab or any other container frame.
    Pass no_llm=True to show a notice instead of the generation form.
    Pass on_preset_saved callback to be notified after a successful save.
    """

    def __init__(self, parent, no_llm: bool = False,
                 on_preset_saved: "Callable[[], None] | None" = None):
        super().__init__(parent, fg_color="transparent")
        self._no_llm          = no_llm
        self._on_preset_saved = on_preset_saved
        self._cfg             = load_config()
        self._loading         = False
        self._result          = None
        self._result_frame: "ctk.CTkFrame | None" = None

        if no_llm:
            self._build_no_llm_notice()
        else:
            self._build()

    # ------------------------------------------------------------------
    # No-LLM notice
    # ------------------------------------------------------------------

    def _build_no_llm_notice(self) -> None:
        ctk.CTkLabel(
            self,
            text="AI preset generation is disabled.\n\n"
                 "Restart without --no-llm to enable.",
            font=ctk.CTkFont(size=14),
            text_color=_TEXT_DIM,
            justify="center",
        ).pack(expand=True, pady=60)

    # ------------------------------------------------------------------
    # Helpers (shared with GenerateToneDialog)
    # ------------------------------------------------------------------

    def _available_labels(self) -> list:
        return [cls.label for cls in PROVIDERS]

    def _label_to_name(self, label: str) -> str:
        for cls in PROVIDERS:
            if cls.label == label:
                return cls.name
        return "anthropic"

    def _name_to_label(self, name: str) -> str:
        for cls in PROVIDERS:
            if cls.name == name:
                return cls.label
        return AnthropicProvider.label

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        pad = {"padx": 14, "pady": 6}

        # ── Provider row ──────────────────────────────────────────────
        prov_frame = ctk.CTkFrame(self, fg_color="transparent")
        prov_frame.pack(fill="x", **pad)

        ctk.CTkLabel(prov_frame, text="Provider:", width=70,
                     anchor="w").pack(side="left")

        # Status dot — colored by provider brand, amber when key is missing
        self._prov_dot = ctk.CTkLabel(
            prov_frame, text="●", font=ctk.CTkFont(size=12),
            text_color=_PROVIDER_COLORS.get("anthropic", _ACCENT))
        self._prov_dot.pack(side="left", padx=(0, 4))

        current_label = self._name_to_label(
            self._cfg.get("provider", "anthropic"))
        self._prov_var = tk.StringVar(value=current_label)
        ctk.CTkOptionMenu(
            prov_frame,
            variable=self._prov_var,
            values=self._available_labels(),
            width=200,
            command=self._on_provider_changed,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            prov_frame, text="⚙  Configure…", width=115,
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self._configure_provider,
        ).pack(side="left")

        self._model_lbl = ctk.CTkLabel(
            prov_frame, text="",
            font=ctk.CTkFont(size=10), text_color=_TEXT_DIM, anchor="w")
        self._model_lbl.pack(side="left", padx=(10, 0))

        # Key warning
        self._key_warn_lbl = ctk.CTkLabel(
            self, text="",
            text_color=_TEXT_WARN,
            font=ctk.CTkFont(size=11),
            anchor="w", wraplength=460, justify="left")

        # ── Description ───────────────────────────────────────────────
        ctk.CTkLabel(self, text="Describe the tone or artist to emulate:",
                     anchor="w").pack(fill="x", padx=14, pady=(8, 2))

        txt_frame = ctk.CTkFrame(self, fg_color=_BG_TEXT_INPUT, corner_radius=6)
        txt_frame.pack(fill="x", padx=14, pady=(0, 4))
        self._text = tk.Text(
            txt_frame,
            height=4, width=52,
            wrap="word",
            bg=_BG_TEXT_INPUT, fg=_TEXT_BRIGHT,
            insertbackground=_TEXT_BRIGHT,
            relief="flat", bd=0,
            font=("Helvetica", 12),
            padx=8, pady=8,
        )
        self._text.pack(fill="x", padx=2, pady=2)
        self._text.focus_set()

        # Hint
        ctk.CTkLabel(
            self,
            text="The AI selects amp, cab, and effect models from the HX Stomp "
                 "catalog, sets starting parameters, and creates three named snapshots.\n"
                 "To load onto your Stomp:  ① In HX Edit: File → Import Preset… → select the .hlx file  "
                 "② Drag to your desired slot  ③ Click the sync icon to transfer.\n"
                 "HX Edit is free at line6.com/software",
            font=ctk.CTkFont(size=10),
            text_color=_TEXT_DIM,
            anchor="w", justify="left", wraplength=460,
        ).pack(fill="x", padx=14, pady=(2, 6))

        # Progress bar
        self._progress = ctk.CTkProgressBar(self, mode="indeterminate")

        # Status label
        self._status_lbl = ctk.CTkLabel(
            self, text="", text_color=_TEXT_DIM,
            font=ctk.CTkFont(size=11), anchor="w", wraplength=460)
        self._status_lbl.pack(fill="x", padx=14, pady=(0, 2))

        # ── Buttons ───────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(4, 8))

        self._gen_btn = ctk.CTkButton(
            btn_frame, text="📦  Generate Preset", width=150,
            command=self._start_generate)
        self._gen_btn.pack(side="left", padx=6)

        self._manual_btn = ctk.CTkButton(
            btn_frame, text="📋  Manual Mode", width=130,
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self._open_manual_dialog)
        self._manual_btn.pack(side="left", padx=6)

        # Result area — built dynamically after generation
        self._result_frame = None

        # Initialise dynamic labels
        self._refresh_provider_ui()

    # ------------------------------------------------------------------
    # Provider helpers
    # ------------------------------------------------------------------

    def _refresh_provider_ui(self) -> None:
        name = self._label_to_name(self._prov_var.get())
        cls  = next((p for p in PROVIDERS if p.name == name), AnthropicProvider)

        model = self._cfg.get(f"{name}_model", "") or cls.default_model
        self._model_lbl.configure(text=f"using {model}")

        brand_color = _PROVIDER_COLORS.get(name, _ACCENT)

        if cls.requires_key:
            has_key = bool(
                self._cfg.get(f"{name}_api_key")
                or (cls.env_var and os.environ.get(cls.env_var))
            )
            if has_key:
                self._prov_dot.configure(text_color=brand_color)
                self._key_warn_lbl.pack_forget()
            else:
                self._prov_dot.configure(text_color=_TEXT_WARN)
                self._key_warn_lbl.configure(
                    text=f"⚠  No API key for {cls.label}. "
                         f"Click ⚙ Configure… to add your key.")
                self._key_warn_lbl.pack(fill="x", padx=14, pady=(0, 4))
        else:
            # Ollama — no key needed, always show brand color
            self._prov_dot.configure(text_color=brand_color)
            self._key_warn_lbl.pack_forget()

    def _on_provider_changed(self, label: str) -> None:
        self._cfg["provider"] = self._label_to_name(label)
        save_config(self._cfg)
        self._refresh_provider_ui()

    def _configure_provider(self) -> None:
        name = self._label_to_name(self._prov_var.get())
        dlg  = ProviderConfigDialog(self, name)
        self.winfo_toplevel().wait_window(dlg)
        self._cfg = load_config()
        self._refresh_provider_ui()

    # ------------------------------------------------------------------
    # Loading state
    # ------------------------------------------------------------------

    def _set_loading(self, loading: bool) -> None:
        self._loading = loading
        if loading:
            self._gen_btn.configure(state="disabled", text="Generating…")
            self._progress.pack(fill="x", padx=14, pady=(0, 4),
                                 before=self._status_lbl)
            self._progress.start()
        else:
            self._progress.stop()
            self._progress.pack_forget()
            self._gen_btn.configure(state="normal", text="📦  Generate Preset")

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _start_generate(self) -> None:
        description = self._text.get("1.0", "end").strip()
        if not description:
            self._status_lbl.configure(
                text="Please describe a tone or artist first.",
                text_color=_COL_DISC)
            return
        self._status_lbl.configure(text="", text_color=_TEXT_DIM)
        if self._result_frame is not None:
            self._result_frame.destroy()
            self._result_frame = None
        self._set_loading(True)
        threading.Thread(target=self._worker, args=(description,),
                         daemon=True).start()

    def _open_manual_dialog(self) -> None:
        description = self._text.get("1.0", "end").strip()
        if not description:
            self._status_lbl.configure(
                text="Please describe a tone or artist first.",
                text_color=_COL_DISC)
            return
        ManualHLXDialog(self, description, self._on_result)

    def _worker(self, description: str) -> None:
        try:
            from hlx_builder import generate_hlx_preset
            provider = get_provider(self._cfg)
            result   = generate_hlx_preset(description, provider)
            self.after(0, lambda: self._on_result(result))
        except LLMGenerationError as exc:
            msg = str(exc)
            self.after(0, lambda m=msg: self._on_error(m))
        except Exception as exc:
            msg = f"Unexpected error: {exc}"
            self.after(0, lambda m=msg: self._on_error(m))

    # ------------------------------------------------------------------
    # Result display
    # ------------------------------------------------------------------

    def _on_result(self, result) -> None:
        self._set_loading(False)
        self._result = result
        self._build_result_panel(result)

    def _on_error(self, msg: str) -> None:
        self._set_loading(False)
        self._status_lbl.configure(text=f"Error: {msg}", text_color=_COL_DISC)

    def _clear_result(self) -> None:
        if self._result_frame is not None:
            self._result_frame.destroy()
            self._result_frame = None
        self._result = None
        self._status_lbl.configure(text="", text_color=_TEXT_DIM)

    def _build_result_panel(self, result) -> None:
        """Build (or rebuild) the result panel below the action buttons."""
        if self._result_frame is not None:
            self._result_frame.destroy()

        rf = ctk.CTkFrame(self, fg_color=_BG_SURFACE, corner_radius=8)
        rf.pack(fill="x", padx=14, pady=(4, 8))
        self._result_frame = rf

        # Separator line
        ctk.CTkFrame(rf, height=1, fg_color=_BORDER_DIM).pack(
            fill="x", padx=0, pady=(0, 8))

        # Preset name + description
        ctk.CTkLabel(
            rf,
            text=result.preset_name,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=_TEXT_BRIGHT, anchor="w",
        ).pack(fill="x", padx=12, pady=(4, 0))

        if result.description:
            ctk.CTkLabel(
                rf, text=result.description,
                font=ctk.CTkFont(size=11),
                text_color=_TEXT_DIM, anchor="w",
                wraplength=440, justify="left",
            ).pack(fill="x", padx=12, pady=(2, 8))

        # ── Signal chain strip ────────────────────────────────────────
        n_blocks  = len(result.blocks)
        chain_lbl = ctk.CTkLabel(
            rf,
            text=f"Signal Chain  ({n_blocks} block{'s' if n_blocks != 1 else ''})",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_TEXT_DIM, anchor="w",
        )
        chain_lbl.pack(fill="x", padx=12, pady=(0, 4))

        chain_outer = ctk.CTkFrame(rf, fg_color="transparent")
        chain_outer.pack(fill="x", padx=12, pady=(0, 6))

        for i, blk in enumerate(result.blocks):
            cat   = blk.get("category", "")
            color = _CAT_COLOR.get(cat, "#4A90D9")
            badge = _CAT_BADGE.get(cat, "•")

            card = ctk.CTkFrame(chain_outer, fg_color=color,
                                corner_radius=6)
            card.pack(side="left", padx=(0, 4))

            # Emoji — large, centered
            ctk.CTkLabel(
                card,
                text=badge,
                font=ctk.CTkFont(size=16),
                text_color="#ffffff",
            ).pack(padx=10, pady=(8, 1))

            # Block name — bold
            ctk.CTkLabel(
                card,
                text=blk.get("name", blk.get("model_id", "?")),
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#ffffff",
            ).pack(padx=8, pady=(0, 1))

            # Category — small, muted
            ctk.CTkLabel(
                card,
                text=cat,
                font=ctk.CTkFont(size=9),
                text_color="#d9d9d9",
            ).pack(padx=8, pady=(0, 8))

            if i < len(result.blocks) - 1:
                ctk.CTkLabel(
                    chain_outer, text="▸",
                    font=ctk.CTkFont(size=12), text_color="#555555",
                ).pack(side="left", padx=2)

        # ── Warnings strip (amber) ────────────────────────────────────
        result_warnings = getattr(result, "warnings", [])
        if result_warnings:
            warn_frame = ctk.CTkFrame(rf, fg_color=_BG_WARN, corner_radius=6)
            warn_frame.pack(fill="x", padx=12, pady=(6, 2))
            ctk.CTkLabel(
                warn_frame,
                text="⚠  Generation notes",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=_TEXT_WARN, anchor="w",
            ).pack(fill="x", padx=10, pady=(6, 2))
            for w in result_warnings:
                ctk.CTkLabel(
                    warn_frame,
                    text=f"  • {w}",
                    font=ctk.CTkFont(size=9),
                    text_color="#c8980a", anchor="w",
                    wraplength=420, justify="left",
                ).pack(fill="x", padx=10, pady=(0, 2))
            ctk.CTkFrame(warn_frame, height=4, fg_color="transparent").pack()

        # ── Per-block explanations ────────────────────────────────────
        expl_blocks = [b for b in result.blocks if b.get("explanation")]
        if expl_blocks:
            ctk.CTkLabel(rf, text="Block Notes",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=_TEXT_DIM, anchor="w").pack(
                fill="x", padx=12, pady=(6, 2))
            for blk in expl_blocks:
                cat   = blk.get("category", "")
                color = _CAT_COLOR.get(cat, "#4A90D9")
                row   = ctk.CTkFrame(rf, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=1)
                ctk.CTkLabel(
                    row,
                    text=f"  {blk.get('name', '?')}",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=color, width=140, anchor="w",
                ).pack(side="left")
                ctk.CTkLabel(
                    row,
                    text=blk.get("explanation", ""),
                    font=ctk.CTkFont(size=10),
                    text_color=_TEXT_DIM, anchor="w",
                    wraplength=290, justify="left",
                ).pack(side="left", padx=(4, 0))

        # ── Snapshots ─────────────────────────────────────────────────
        snaps = getattr(result, "snapshots", [])
        if snaps:
            ctk.CTkLabel(rf, text="Snapshots",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=_TEXT_DIM, anchor="w").pack(
                fill="x", padx=12, pady=(6, 4))
            snap_row = ctk.CTkFrame(rf, fg_color="transparent")
            snap_row.pack(fill="x", padx=12, pady=(0, 6))
            for si, snap in enumerate(snaps[:3]):
                sc = _SNAP_COLORS[si % len(_SNAP_COLORS)]
                pill = ctk.CTkFrame(snap_row, fg_color=sc, corner_radius=6)
                pill.pack(side="left", padx=(0, 6))
                ctk.CTkLabel(
                    pill,
                    text=snap.get("name", f"Snapshot {si + 1}"),
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color="#ffffff",
                ).pack(padx=10, pady=(5, 1))
                desc = snap.get("description", "")
                if desc:
                    ctk.CTkLabel(
                        pill, text=desc,
                        font=ctk.CTkFont(size=9),
                        text_color="#d9d9d9",
                        wraplength=130, justify="left",
                    ).pack(padx=10, pady=(0, 5))

        # ── Rationale ─────────────────────────────────────────────────
        if result.signal_chain_rationale:
            ctk.CTkLabel(rf, text="Design Rationale",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=_TEXT_DIM, anchor="w").pack(
                fill="x", padx=12, pady=(6, 2))
            ctk.CTkLabel(
                rf, text=result.signal_chain_rationale,
                font=ctk.CTkFont(size=10),
                text_color=_TEXT_DIM, anchor="w",
                wraplength=440, justify="left",
            ).pack(fill="x", padx=12, pady=(0, 4))

        # ── Action buttons ────────────────────────────────────────────
        ctk.CTkFrame(rf, height=1, fg_color=_BORDER_DIM).pack(
            fill="x", padx=0, pady=(4, 0))
        act_frame = ctk.CTkFrame(rf, fg_color="transparent")
        act_frame.pack(pady=8)

        ctk.CTkButton(
            act_frame, text="💾  Save .hlx…", width=130,
            command=self._save_hlx,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            act_frame, text="🔄  Regenerate", width=130,
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self._regenerate,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            act_frame, text="✕  Clear", width=80,
            fg_color="transparent", border_width=1, text_color=_TEXT_DIM,
            command=self._clear_result,
        ).pack(side="left", padx=6)

    # ------------------------------------------------------------------
    # Save / Regenerate
    # ------------------------------------------------------------------

    def _save_hlx(self) -> None:
        if self._result is None:
            return
        from hlx_builder import PresetCatalog, save_hlx
        catalog  = PresetCatalog()
        name     = self._result.preset_name
        filepath = filedialog.asksaveasfilename(
            title="Save .hlx Preset",
            defaultextension=".hlx",
            filetypes=[("HX Stomp Preset", "*.hlx"), ("All files", "*.*")],
            initialfile=f"{name.replace(' ', '_')}.hlx",
        )
        if not filepath:
            return
        from pathlib import Path as _Path
        dest = _Path(filepath)
        try:
            catalog.save_preset(self._result, filepath=dest)
            self._status_lbl.configure(
                text=f"Saved: {dest.name}", text_color=_ACCENT)
            if self._on_preset_saved is not None:
                self._on_preset_saved()
        except Exception as exc:
            from tkinter import messagebox as _mb
            _mb.showerror("Save failed", str(exc))
            self._status_lbl.configure(text="Save failed", text_color=_COL_DISC)

    def _regenerate(self) -> None:
        description = self._text.get("1.0", "end").strip()
        if not description:
            return
        self._status_lbl.configure(text="", text_color=_TEXT_DIM)
        if self._result_frame is not None:
            self._result_frame.destroy()
            self._result_frame = None
        self._set_loading(True)
        threading.Thread(target=self._worker, args=(description,),
                         daemon=True).start()


class ManualHLXDialog(ctk.CTkToplevel):
    """
    Two-step wizard that lets users generate a preset without an API key.

    Step 1 — Copy the assembled prompt (system + user) to any AI chatbot.
    Step 2 — Paste the chatbot's JSON response; validate and import it.
    """

    _TIP = (
        "Tip: For best results use Claude Sonnet, GPT-4o, or Gemini 1.5 Pro.\n"
        "The prompt includes the full HX Stomp model catalog (~4 000 tokens)."
    )
    _STEP1_HEADER = "Step 1 of 2 — Copy the prompt"
    _STEP1_BODY   = (
        "Paste this into Claude.ai, ChatGPT, Gemini, or any capable AI.\n"
        "Copy the chatbot's complete response, then click Next."
    )
    _STEP2_HEADER = "Step 2 of 2 — Paste the response"
    _STEP2_BODY   = (
        "Paste the chatbot's complete reply below.\n"
        "It should be a JSON object starting with {."
    )

    def __init__(self, parent, description: str, on_result_callback: Callable):
        super().__init__(parent)
        self.title("📋 Use Your Own Chatbot")
        self.resizable(False, False)
        self.minsize(660, 460)
        self.grab_set()

        self._description = description
        self._on_result   = on_result_callback

        from hlx_builder import build_hlx_prompt
        system_prompt, user_prompt = build_hlx_prompt(description)
        self._combined_prompt = (
            "[SYSTEM INSTRUCTIONS]\n"
            + system_prompt
            + "\n\n[YOUR REQUEST]\n"
            + user_prompt
        )

        self._step = 1
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        for w in self.winfo_children():
            w.destroy()

        # Title bar
        header = ctk.CTkFrame(self, fg_color=_BG_TOOLBAR, corner_radius=0, height=44)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text="📋  Use Your Own Chatbot",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=_TEXT_BRIGHT,
        ).pack(side="left", padx=14)

        body = ctk.CTkFrame(self, fg_color=_BG_BASE, corner_radius=0)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        if self._step == 1:
            self._build_step1(body)
        else:
            self._build_step2(body)

    def _build_step1(self, body: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            body, text=self._STEP1_HEADER,
            font=ctk.CTkFont(size=12, weight="bold"), text_color=_TEXT_BRIGHT,
            anchor="w",
        ).pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(
            body, text=self._STEP1_BODY,
            font=ctk.CTkFont(size=11), text_color=_TEXT_DIM,
            anchor="w", justify="left",
        ).pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            body, text=self._TIP,
            font=ctk.CTkFont(size=10), text_color=_TEXT_DIM,
            anchor="w", justify="left",
        ).pack(fill="x", pady=(0, 6))

        # Scrollable prompt display
        txt = ctk.CTkTextbox(body, height=260, font=ctk.CTkFont(size=10),
                             wrap="word", state="normal")
        txt.insert("1.0", self._combined_prompt)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            btn_row, text="📋  Copy to Clipboard", width=160,
            command=lambda: self._copy_and_advance(txt),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Next: Paste Response →", width=160,
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self._go_step2,
        ).pack(side="left")
        ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color="transparent", text_color=_TEXT_DIM,
            command=self.destroy,
        ).pack(side="right")

    def _build_step2(self, body: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            body, text=self._STEP2_HEADER,
            font=ctk.CTkFont(size=12, weight="bold"), text_color=_TEXT_BRIGHT,
            anchor="w",
        ).pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(
            body, text=self._STEP2_BODY,
            font=ctk.CTkFont(size=11), text_color=_TEXT_DIM,
            anchor="w", justify="left",
        ).pack(fill="x", pady=(0, 6))

        self._paste_box = ctk.CTkTextbox(body, height=260, font=ctk.CTkFont(size=10),
                                         wrap="word")
        self._paste_box.pack(fill="both", expand=True)

        self._error_lbl = ctk.CTkLabel(
            body, text="", font=ctk.CTkFont(size=11),
            text_color=_COL_DISC, anchor="w", justify="left", wraplength=600,
        )
        self._error_lbl.pack(fill="x", pady=(4, 0))

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            btn_row, text="← Back", width=80,
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self._go_step1,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="✓  Import & Validate", width=160,
            command=self._import,
        ).pack(side="left")
        ctk.CTkButton(
            btn_row, text="Cancel", width=80,
            fg_color="transparent", text_color=_TEXT_DIM,
            command=self.destroy,
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _copy_and_advance(self, txt_widget) -> None:
        self.clipboard_clear()
        self.clipboard_append(self._combined_prompt)
        self._go_step2()

    def _go_step2(self) -> None:
        self._step = 2
        self._build_ui()

    def _go_step1(self) -> None:
        self._step = 1
        self._build_ui()

    # ------------------------------------------------------------------
    # Import / validate
    # ------------------------------------------------------------------

    def _import(self) -> None:
        raw = self._paste_box.get("1.0", "end").strip()
        if not raw:
            self._error_lbl.configure(text="Nothing pasted yet.")
            return
        self._error_lbl.configure(text="Validating…", text_color=_TEXT_DIM)
        self.update_idletasks()
        threading.Thread(target=self._parse_worker, args=(raw,), daemon=True).start()

    def _parse_worker(self, raw: str) -> None:
        try:
            from hlx_builder import parse_hlx_response
            result = parse_hlx_response(raw, self._description)
            self.after(0, lambda: self._on_parse_success(result))
        except Exception as exc:
            msg = self._user_message(str(exc))
            self.after(0, lambda m=msg: self._on_parse_error(m))

    @staticmethod
    def _user_message(exc_msg: str) -> str:
        if not exc_msg or "Empty response" in exc_msg:
            return "Nothing pasted yet."
        if "{" not in exc_msg and "JSON" not in exc_msg and exc_msg.startswith("Could not"):
            return (
                "Could not find JSON in the pasted text. "
                "Make sure you copied the chatbot's complete reply."
            )
        if "JSONDecodeError" in exc_msg or "not valid JSON" in exc_msg.lower():
            return "The pasted text is not valid JSON. Check for cut-off responses."
        if "No valid amp block" in exc_msg or "No recognisable" in exc_msg:
            return (
                "No recognisable HX Stomp models found. "
                "Try a different description or chatbot."
            )
        return exc_msg

    def _on_parse_success(self, result) -> None:
        self.destroy()
        self._on_result(result)

    def _on_parse_error(self, msg: str) -> None:
        self._error_lbl.configure(text=msg, text_color=_COL_DISC)


class GeneratePresetDialog(ctk.CTkToplevel):
    """
    Thin wrapper around HLXWorkspacePanel for standalone dialog use.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Generate HX Stomp Preset")
        self.resizable(False, False)
        self.minsize(520, 380)
        self.grab_set()

        self._panel = HLXWorkspacePanel(self)
        self._panel.pack(fill="both", expand=True, padx=0, pady=0)

        ctk.CTkButton(
            self, text="Close", width=90,
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self.destroy,
        ).pack(pady=(0, 8))


# ---------------------------------------------------------------------------
# PresetCatalogPanel  — embeddable CTkFrame (used in the HLX Generator tab)
# ---------------------------------------------------------------------------

class PresetCatalogPanel(ctk.CTkFrame):
    """
    Embeddable catalog browser. Can be placed inside a tab or PanedWindow.
    Call refresh() to reload after a new preset is saved.
    """

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        from hlx_builder import PresetCatalog
        self._catalog = PresetCatalog()

        # ── Header bar ────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=_BG_TOOLBAR, corner_radius=0)
        hdr.pack(fill="x")

        ctk.CTkLabel(
            hdr,
            text="Generated Presets",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=_TEXT_BRIGHT,
        ).pack(side="left", padx=14, pady=10)

        self._footer_lbl = ctk.CTkLabel(
            hdr, text="", font=ctk.CTkFont(size=11),
            text_color=_TEXT_DIM, anchor="w")
        self._footer_lbl.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            hdr, text="↺  Refresh", width=90,
            fg_color="transparent", border_width=1, text_color=_TEXT_BRIGHT,
            command=self._refresh,
        ).pack(side="right", padx=8, pady=8)

        # ── Scrollable list ───────────────────────────────────────────
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="#1c1c1c", corner_radius=0)
        self._scroll.pack(fill="both", expand=True)

        self._render_list()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._refresh()

    # ------------------------------------------------------------------
    # List rendering
    # ------------------------------------------------------------------

    def _render_list(self) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()

        entries = self._catalog.list_presets()

        if not entries:
            ctk.CTkLabel(
                self._scroll,
                text="No generated presets yet.\n\n"
                     "Use the generator above to create your first .hlx file.",
                font=ctk.CTkFont(size=12),
                text_color=_TEXT_DIM,
                justify="center",
            ).pack(expand=True, pady=60)
            self._footer_lbl.configure(text="0 presets")
            return

        self._footer_lbl.configure(
            text=f"{len(entries)} preset{'s' if len(entries) != 1 else ''}")

        for entry in entries:
            self._build_row(entry)

    def _build_row(self, entry: dict) -> None:
        filename  = entry.get("filename", "")
        name      = entry.get("preset_name", filename)
        desc      = entry.get("description", "")
        created   = entry.get("created", "")
        blocks    = entry.get("blocks", [])
        rationale = entry.get("signal_chain_rationale", "")

        # Outer card with border
        first_cat   = blocks[0].get("category", "") if blocks else ""
        accent_color = _CAT_COLOR.get(first_cat, _BORDER_DIM)
        card = ctk.CTkFrame(self._scroll, fg_color=_BG_CARD, corner_radius=8,
                            border_width=1, border_color=_BORDER_DIM)
        card.pack(fill="x", padx=10, pady=(6, 0))

        # Left category accent strip
        ctk.CTkFrame(card, width=4, fg_color=accent_color,
                     corner_radius=2).pack(side="left", fill="y", padx=(2, 6), pady=4)

        # Inner content frame (sits to the right of the accent strip)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(side="left", fill="both", expand=True)

        # ── Top row: name + date + actions ────────────────────────────
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x", padx=(0, 10), pady=(8, 2))

        ctk.CTkLabel(
            top,
            text=name,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_TEXT_BRIGHT, anchor="w",
        ).pack(side="left")

        date_str = created[:10] if created else ""
        if date_str:
            ctk.CTkLabel(
                top, text=date_str,
                font=ctk.CTkFont(size=10), text_color=_TEXT_DIM,
            ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            top, text="🗑", width=30, height=24,
            fg_color="transparent", hover_color="#3a1515",
            text_color=_COL_DISC, font=ctk.CTkFont(size=12),
            command=lambda fn=filename: self._remove(fn),
        ).pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            top, text="💾  Export…", width=90, height=24,
            fg_color="transparent", border_width=1,
            text_color=_TEXT_BRIGHT, font=ctk.CTkFont(size=11),
            command=lambda e=entry: self._export(e),
        ).pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            top, text="📂  Show", width=72, height=24,
            fg_color="transparent", border_width=1,
            text_color=_TEXT_BRIGHT, font=ctk.CTkFont(size=11),
            command=lambda fn=filename: self._show_in_folder(fn),
        ).pack(side="right", padx=(4, 0))

        # ── Description ───────────────────────────────────────────────
        if desc:
            ctk.CTkLabel(
                inner, text=desc,
                font=ctk.CTkFont(size=10), text_color=_TEXT_DIM,
                anchor="w", wraplength=560, justify="left",
            ).pack(fill="x", padx=10, pady=(0, 4))

        # ── Mini signal chain strip ───────────────────────────────────
        if blocks:
            chain = ctk.CTkFrame(inner, fg_color="transparent")
            chain.pack(fill="x", padx=10, pady=(0, 6))

            for i, blk in enumerate(blocks):
                cat      = blk.get("category", "")
                color    = _CAT_COLOR.get(cat, "#4A90D9")
                badge    = _CAT_BADGE.get(cat, "•")
                blk_name = blk.get("name", blk.get("model_id", "?"))

                chip = ctk.CTkFrame(chain, fg_color=color, corner_radius=4)
                chip.pack(side="left", padx=(0, 2))
                ctk.CTkLabel(
                    chip,
                    text=f"{badge} {blk_name}",
                    font=ctk.CTkFont(size=9, weight="bold"),
                    text_color="#ffffff",
                ).pack(padx=6, pady=(3, 3))

                if i < len(blocks) - 1:
                    ctk.CTkLabel(
                        chain, text="▸",
                        font=ctk.CTkFont(size=10), text_color="#555555",
                    ).pack(side="left", padx=1)

        # ── Snapshot pills ────────────────────────────────────────────
        snaps = entry.get("snapshots", [])
        if snaps:
            snap_row = ctk.CTkFrame(inner, fg_color="transparent")
            snap_row.pack(fill="x", padx=10, pady=(0, 4))
            for si, snap in enumerate(snaps[:3]):
                sc   = _SNAP_COLORS[si % len(_SNAP_COLORS)]
                pill = ctk.CTkFrame(snap_row, fg_color=sc, corner_radius=4)
                pill.pack(side="left", padx=(0, 4))
                ctk.CTkLabel(
                    pill,
                    text=snap.get("name", f"Snap {si + 1}"),
                    font=ctk.CTkFont(size=9, weight="bold"),
                    text_color="#ffffff",
                ).pack(padx=7, pady=(3, 3))

        # ── Rationale ─────────────────────────────────────────────────
        if rationale:
            ctk.CTkLabel(
                inner, text=rationale,
                font=ctk.CTkFont(size=9, slant="italic"),
                text_color="#666666", anchor="w",
                wraplength=560, justify="left",
            ).pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkFrame(inner, height=1, fg_color=_BORDER_DIM).pack(
            fill="x", padx=0, pady=(4, 0))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        from hlx_builder import PresetCatalog
        self._catalog = PresetCatalog()
        self._render_list()

    def _show_in_folder(self, filename: str) -> None:
        import subprocess, sys
        from hlx_builder import PresetCatalog
        filepath = PresetCatalog._PRESETS_DIR / filename
        if not filepath.exists():
            self._footer_lbl.configure(
                text=f"File not found: {filename}", text_color=_COL_DISC)
            return
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(filepath)])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(filepath)])
            else:
                subprocess.Popen(["xdg-open", str(filepath.parent)])
        except Exception as exc:
            self._footer_lbl.configure(
                text=f"Could not open folder: {exc}", text_color=_COL_DISC)

    def _export(self, entry: dict) -> None:
        import shutil
        from hlx_builder import PresetCatalog
        src = PresetCatalog._PRESETS_DIR / entry.get("filename", "")
        if not src.exists():
            self._footer_lbl.configure(
                text=f"File not found: {src.name}", text_color=_COL_DISC)
            return
        name = entry.get("preset_name", src.stem)
        dest = filedialog.asksaveasfilename(
            title="Export .hlx Preset",
            defaultextension=".hlx",
            filetypes=[("HX Stomp Preset", "*.hlx"), ("All files", "*.*")],
            initialfile=f"{name.replace(' ', '_')}.hlx",
        )
        if not dest:
            return
        shutil.copy2(src, dest)
        self._footer_lbl.configure(
            text=f"Exported: {Path(dest).name}", text_color=_ACCENT)

    def _remove(self, filename: str) -> None:
        from hlx_builder import PresetCatalog
        import tkinter.messagebox as mb
        if not mb.askyesno(
            "Remove Entry",
            f"Remove '{filename}' from the catalog?\n\n"
            "The .hlx file is not deleted.",
            parent=self.winfo_toplevel(),
        ):
            return
        PresetCatalog().remove_entry(filename)
        self._refresh()


# ---------------------------------------------------------------------------
# PresetCatalogDialog
# ---------------------------------------------------------------------------

class PresetCatalogDialog(ctk.CTkToplevel):
    """
    Thin wrapper around PresetCatalogPanel for standalone dialog use.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Generated Preset Catalog")
        self.geometry("640x520")
        self.resizable(True, True)
        self.minsize(600, 400)
        self.grab_set()

        self._panel = PresetCatalogPanel(self)
        self._panel.pack(fill="both", expand=True)

        footer = ctk.CTkFrame(self, fg_color=_BG_TOOLBAR, corner_radius=0,
                              height=44)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        ctk.CTkButton(
            footer, text="Close", width=80,
            fg_color="transparent", border_width=1, text_color=_TEXT_DIM,
            command=self.destroy,
        ).pack(side="right", padx=8, pady=8)
