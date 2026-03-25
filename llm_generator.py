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
from typing import Callable

import customtkinter as ctk

from tone_manager import Tone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path.home() / ".hxstomp" / "config.json"
_MAX_TOKENS  = 200

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

    def __init__(self, api_key: str = "", model: str = "", base_url: str = ""):
        self.api_key  = api_key  or ""
        self.model    = model    or self.default_model
        self.base_url = base_url or ""

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return raw text response. Raise LLMGenerationError on failure."""


class AnthropicProvider(LLMProvider):
    name          = "anthropic"
    label         = "Anthropic (Claude)"
    requires_key  = True
    default_model = "claude-haiku-4-5"

    def complete(self, system: str, user: str) -> str:
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
        client = anthropic.Anthropic(api_key=key)
        try:
            msg = client.messages.create(
                model=self.model,
                max_tokens=_MAX_TOKENS,
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

    def complete(self, system: str, user: str) -> str:
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
        client = openai.OpenAI(api_key=key)
        try:
            resp = client.chat.completions.create(
                model=self.model,
                max_tokens=_MAX_TOKENS,
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

    def complete(self, system: str, user: str) -> str:
        base    = (self.base_url or "http://localhost:11434").rstrip("/")
        url     = f"{base}/api/chat"
        payload = json.dumps({
            "model":  self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
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

    def complete(self, system: str, user: str) -> str:
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
            resp = model.generate_content(user)
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
    cls  = next((p for p in PROVIDERS if p.name == name), AnthropicProvider)
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
        self.grab_set()

        self._name = provider_name
        self._cfg  = load_config()
        cls = next((p for p in PROVIDERS if p.name == provider_name),
                   AnthropicProvider)

        pad = {"padx": 12, "pady": 6}
        row = 0

        ctk.CTkLabel(
            self, text=cls.label,
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w",
        ).grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        self._fields: dict[str, tk.StringVar] = {}

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
        name = self._name
        for key, var in self._fields.items():
            self._cfg[f"{name}_{key}"] = var.get().strip()
        save_config(self._cfg)
        self.destroy()


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

        # Description label
        ctk.CTkLabel(self, text="Describe your tone:", anchor="w").pack(
            fill="x", padx=14, pady=(8, 2))

        # Multi-line text area
        txt_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=6)
        txt_frame.pack(fill="x", padx=14, pady=(0, 8))
        self._text = tk.Text(
            txt_frame,
            height=4, width=46,
            wrap="word",
            bg="#2b2b2b", fg=_TEXT_BRIGHT,
            insertbackground=_TEXT_BRIGHT,
            relief="flat", bd=0,
            font=("Helvetica", 12),
            padx=8, pady=8,
        )
        self._text.pack(fill="x", padx=2, pady=2)
        self._text.focus_set()

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

    def _on_provider_changed(self, label: str) -> None:
        self._cfg["provider"] = self._label_to_name(label)
        save_config(self._cfg)

    def _configure_provider(self) -> None:
        name = self._label_to_name(self._prov_var.get())
        dlg  = ProviderConfigDialog(self, name)
        self.wait_window(dlg)
        self._cfg = load_config()

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
                text_color="#e74c3c")
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
                                    text_color="#e74c3c")
