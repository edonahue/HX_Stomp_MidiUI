"""
soundboard_ui.py

Modern dark-theme soundboard UI for the HX Stomp, built with customtkinter.

Layout
------
  Menu bar  : File | MIDI | Tones
  Toolbar   : ⊕ Add  ✏ Edit  🗑 Remove  ↺ Reload
  Main area : Responsive CTkScrollableFrame grid of tone cards grouped by category
  Status bar: Connection indicator pill + active tone label
"""

from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, messagebox
from typing import Optional

import customtkinter as ctk

from midi_interface import HXStompMidi
from tone_manager import Tone, ToneManager

# ---------------------------------------------------------------------------
# Global theme
# ---------------------------------------------------------------------------

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# UI chrome palette (kept minimal so tone card colors dominate)
_BG_TOOLBAR   = "#1e1e1e"
_BG_STATUS    = "#1a1a1a"
_TEXT_DIM     = "#888888"
_TEXT_BRIGHT  = "#e0e0e0"
_ACCENT       = "#4A90D9"
_COL_CONN     = "#2ecc71"   # green  — connected
_COL_DISC     = "#e74c3c"   # red    — disconnected
_CARD_W       = 160
_CARD_H       = 90
_CARD_RADIUS  = 10
_MIN_COLS     = 1


# ---------------------------------------------------------------------------
# Helper: color math
# ---------------------------------------------------------------------------

def _contrast_color(hex_color: str) -> str:
    """Return black or white for readable text on `hex_color` background."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "#ffffff"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 128 else "#ffffff"


def _adjust_brightness(hex_color: str, factor: float = 0.80) -> str:
    """Darken a hex color by `factor` for hover states."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return hex_color
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _muted_color(fg: str, bg: str, alpha: float = 0.55) -> str:
    """Blend `fg` toward `bg` to produce a muted variant for subtitle text."""
    def ch(h: str, i: int) -> int:
        return int(h.lstrip("#")[i:i + 2], 16)
    r = int(ch(fg, 0) * alpha + ch(bg, 0) * (1 - alpha))
    g = int(ch(fg, 2) * alpha + ch(bg, 2) * (1 - alpha))
    b = int(ch(fg, 4) * alpha + ch(bg, 4) * (1 - alpha))
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# ConnectDialog
# ---------------------------------------------------------------------------

class ConnectDialog(ctk.CTkToplevel):
    """Modal dialog for selecting MIDI port and channel."""

    def __init__(self, parent, on_connect):
        super().__init__(parent)
        self.title("Connect to MIDI Port")
        self.resizable(False, False)
        self.grab_set()
        self._on_connect = on_connect
        self._ports: list[str] = []

        self._build()
        self._refresh()

    def _build(self) -> None:
        pad = {"padx": 12, "pady": 6}

        ctk.CTkLabel(self, text="MIDI Output Port", anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="w", **pad)

        self._port_var = tk.StringVar()
        self._port_cb = ctk.CTkComboBox(
            self, variable=self._port_var, width=280, state="readonly")
        self._port_cb.grid(row=1, column=0, sticky="ew", padx=(12, 4), pady=4)

        ctk.CTkButton(self, text="↺", width=36, command=self._refresh).grid(
            row=1, column=1, padx=(0, 12), pady=4)

        ctk.CTkLabel(self, text="Channel (1–16)", anchor="w").grid(
            row=2, column=0, columnspan=2, sticky="w", **pad)

        self._chan_var = tk.IntVar(value=1)
        ctk.CTkSlider(
            self, from_=1, to=16, number_of_steps=15,
            variable=self._chan_var,
            command=lambda v: self._chan_lbl.configure(
                text=f"Channel {int(v)}")
        ).grid(row=3, column=0, sticky="ew", padx=(12, 4), pady=4)

        self._chan_lbl = ctk.CTkLabel(self, text="Channel 1", width=72)
        self._chan_lbl.grid(row=3, column=1, padx=(0, 12))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, columnspan=2, pady=12)

        ctk.CTkButton(btn_frame, text="Connect",
                      command=self._connect).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="transparent",
                      border_width=1, text_color=_TEXT_BRIGHT,
                      command=self.destroy).pack(side="left", padx=6)

    def _refresh(self) -> None:
        self._ports = HXStompMidi.list_output_ports()
        self._port_cb.configure(values=self._ports)
        auto = HXStompMidi.find_hx_port()
        if auto:
            self._port_var.set(auto)
        elif self._ports:
            self._port_var.set(self._ports[0])
        else:
            self._port_var.set("")

    def _connect(self) -> None:
        port = self._port_var.get()
        if not port:
            messagebox.showwarning("No port", "No MIDI port selected.", parent=self)
            return
        channel = int(self._chan_var.get())
        self._on_connect(port, channel)
        self.destroy()


# ---------------------------------------------------------------------------
# ToneDialog
# ---------------------------------------------------------------------------

class ToneDialog(ctk.CTkToplevel):
    """Modal dialog for creating or editing a Tone."""

    def __init__(self, parent, title: str = "Tone", tone: Tone | None = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: Optional[Tone] = None

        tone = tone or Tone(name="", preset=0)
        self._color = tone.color

        fields = [
            ("Name",           "name",     tone.name),
            ("Preset (0–127)", "preset",   str(tone.preset)),
            ("Snapshot (0–2)", "snapshot", str(tone.snapshot)),
            ("Bank MSB",       "bank_msb", str(tone.bank_msb)),
            ("Bank LSB",       "bank_lsb", str(tone.bank_lsb)),
            ("Category",       "category", tone.category or ""),
        ]

        self._vars: dict[str, tk.StringVar] = {}
        for row, (label, key, default) in enumerate(fields):
            ctk.CTkLabel(self, text=label, anchor="w", width=120).grid(
                row=row, column=0, padx=(12, 4), pady=5, sticky="w")
            var = tk.StringVar(value=default)
            self._vars[key] = var
            ctk.CTkEntry(self, textvariable=var, width=200).grid(
                row=row, column=1, padx=(4, 12), pady=5)

        color_row = len(fields)
        ctk.CTkLabel(self, text="Color", anchor="w", width=120).grid(
            row=color_row, column=0, padx=(12, 4), pady=5, sticky="w")
        self._color_btn = ctk.CTkButton(
            self, text="  Pick color",
            fg_color=self._color,
            hover_color=_adjust_brightness(self._color),
            text_color=_contrast_color(self._color),
            width=120,
            command=self._pick_color,
        )
        self._color_btn.grid(row=color_row, column=1, padx=(4, 12), pady=5, sticky="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=color_row + 1, column=0, columnspan=2, pady=12)

        ctk.CTkButton(btn_frame, text="OK", width=90,
                      command=self._ok).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Cancel", width=90,
                      fg_color="transparent", border_width=1,
                      text_color=_TEXT_BRIGHT,
                      command=self.destroy).pack(side="left", padx=6)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _pick_color(self) -> None:
        result = colorchooser.askcolor(color=self._color, parent=self)
        if result and result[1]:
            self._color = result[1]
            self._color_btn.configure(
                fg_color=self._color,
                hover_color=_adjust_brightness(self._color),
                text_color=_contrast_color(self._color),
            )

    def _ok(self) -> None:
        try:
            self.result = Tone(
                name     = self._vars["name"].get().strip(),
                preset   = int(self._vars["preset"].get()),
                snapshot = int(self._vars["snapshot"].get()),
                bank_msb = int(self._vars["bank_msb"].get()),
                bank_lsb = int(self._vars["bank_lsb"].get()),
                color    = self._color,
                category = self._vars["category"].get().strip() or None,
            )
            self.result.validate()
        except (ValueError, KeyError) as e:
            messagebox.showerror("Invalid input", str(e), parent=self)
            return
        self.destroy()


# ---------------------------------------------------------------------------
# Main soundboard window
# ---------------------------------------------------------------------------

class SoundboardApp(ctk.CTk):

    def __init__(self, presets_file: str = "presets.json"):
        super().__init__()
        self.title("HX Stomp Soundboard")
        self.minsize(600, 480)

        self._midi         = HXStompMidi()
        self._tones        = ToneManager(presets_file)
        self._active: Optional[str] = None
        self._focused: Optional[str] = None   # keyboard-focused tone (not yet activated)
        self._cols         = 4
        self._card_frames: dict[str, ctk.CTkFrame] = {}  # name → wrapper frame
        self._tuner_state: bool = False

        self._build_ui()
        self._render_tones()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._build_menu()
        self._build_toolbar()
        self._build_bypass_panel()
        self._build_grid()
        self._build_statusbar()

    # ---- Menu bar ----------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self, tearoff=0,
                          bg="#2b2b2b", fg=_TEXT_BRIGHT,
                          activebackground=_ACCENT, activeforeground="#ffffff",
                          bd=0)

        # File
        file_menu = tk.Menu(menubar, tearoff=0,
                            bg="#2b2b2b", fg=_TEXT_BRIGHT,
                            activebackground=_ACCENT, activeforeground="#ffffff")
        file_menu.add_command(label="💾  Save",          command=self._save,
                              accelerator="Ctrl+S")
        file_menu.add_command(label="↺  Reload",         command=self._reload,
                              accelerator="Ctrl+R")
        file_menu.add_separator()
        file_menu.add_command(label="Exit",              command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # MIDI
        midi_menu = tk.Menu(menubar, tearoff=0,
                            bg="#2b2b2b", fg=_TEXT_BRIGHT,
                            activebackground=_ACCENT, activeforeground="#ffffff")
        midi_menu.add_command(label="⏵  Connect…",      command=self._open_connect_dialog)
        midi_menu.add_command(label="⏹  Disconnect",    command=self._disconnect)
        midi_menu.add_command(label="↺  Refresh Ports", command=self._refresh_ports_silent)
        midi_menu.add_separator()

        # Channel submenu
        self._chan_var = tk.IntVar(value=1)
        chan_menu = tk.Menu(midi_menu, tearoff=0,
                            bg="#2b2b2b", fg=_TEXT_BRIGHT,
                            activebackground=_ACCENT, activeforeground="#ffffff")
        for ch in range(1, 17):
            chan_menu.add_radiobutton(
                label=f"Channel {ch}", value=ch,
                variable=self._chan_var)
        midi_menu.add_cascade(label="Channel", menu=chan_menu)
        midi_menu.add_separator()
        midi_menu.add_command(label="🎵  Toggle Tuner",  command=self._toggle_tuner)
        midi_menu.add_command(label="🎛  FS Bypass Panel", command=self._toggle_bypass_panel)
        menubar.add_cascade(label="MIDI", menu=midi_menu)

        # Tones
        tones_menu = tk.Menu(menubar, tearoff=0,
                             bg="#2b2b2b", fg=_TEXT_BRIGHT,
                             activebackground=_ACCENT, activeforeground="#ffffff")
        tones_menu.add_command(label="⊕  Add Tone",        command=self._add_tone)
        tones_menu.add_command(label="✏  Edit Selected",   command=self._edit_tone)
        tones_menu.add_command(label="⧉  Duplicate Selected", command=self._duplicate_tone)
        tones_menu.add_command(label="🗑  Remove Selected", command=self._remove_tone)
        menubar.add_cascade(label="Tones", menu=tones_menu)

        self.configure(menu=menubar)

        # Keyboard shortcuts
        self.bind_all("<Control-s>", lambda _: self._save())
        self.bind_all("<Control-r>", lambda _: self._reload())
        # Number keys 1–9 activate tone at that display position
        for n in range(1, 10):
            self.bind_all(str(n), lambda e, i=n: self._activate_by_index(i - 1))
        # Arrow keys navigate focus; Enter activates the focused tone
        self.bind_all("<Up>",    lambda _: self._kb_navigate(-1))
        self.bind_all("<Down>",  lambda _: self._kb_navigate(+1))
        self.bind_all("<Return>", lambda _: self._kb_activate())

    # ---- Toolbar -----------------------------------------------------

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, height=44, fg_color=_BG_TOOLBAR,
                               corner_radius=0)
        toolbar.pack(fill="x", side="top")
        toolbar.pack_propagate(False)

        btn_opts = dict(
            fg_color    = "transparent",
            hover_color = "#333333",
            text_color  = _TEXT_BRIGHT,
            height      = 32,
            corner_radius = 6,
        )

        ctk.CTkButton(toolbar, text="⊕  Add",       width=90,
                      command=self._add_tone,       **btn_opts).pack(
            side="left", padx=(8, 2), pady=6)
        ctk.CTkButton(toolbar, text="✏  Edit",      width=90,
                      command=self._edit_tone,      **btn_opts).pack(
            side="left", padx=2,      pady=6)
        ctk.CTkButton(toolbar, text="⧉  Duplicate", width=105,
                      command=self._duplicate_tone, **btn_opts).pack(
            side="left", padx=2,      pady=6)
        ctk.CTkButton(toolbar, text="🗑  Remove",    width=100,
                      command=self._remove_tone,    **btn_opts).pack(
            side="left", padx=2,      pady=6)
        ctk.CTkButton(toolbar, text="↑",            width=36,
                      command=lambda: self._move_tone(-1), **btn_opts).pack(
            side="left", padx=2,      pady=6)
        ctk.CTkButton(toolbar, text="↓",            width=36,
                      command=lambda: self._move_tone(+1), **btn_opts).pack(
            side="left", padx=2,      pady=6)
        ctk.CTkButton(toolbar, text="↺  Reload",    width=90,
                      command=self._reload,         **btn_opts).pack(
            side="left", padx=2,      pady=6)

    # ---- Effect bypass panel -----------------------------------------

    def _build_bypass_panel(self) -> None:
        """Collapsible panel with 6 footswitch bypass toggles (FS1–FS6)."""
        self._bypass_states: list[bool] = [False] * 6   # False = engaged, True = bypassed
        self._bypass_panel_visible: bool = False

        # Toggle button in toolbar area (added after toolbar is built)
        self._bypass_toggle_btn = ctk.CTkButton(
            self,
            text="FS Bypass ▾",
            height=26,
            fg_color="transparent",
            hover_color="#333333",
            text_color=_TEXT_DIM,
            corner_radius=4,
            font=ctk.CTkFont(size=11),
            command=self._toggle_bypass_panel,
        )
        # Don't pack yet — will be shown inline; skip for now

        self._bypass_frame = ctk.CTkFrame(self, fg_color="#181818",
                                           height=50, corner_radius=0)
        self._bypass_frame.pack_propagate(False)
        # Build 6 FS toggle buttons inside
        self._fs_btns: list[ctk.CTkButton] = []
        for fs in range(1, 7):
            btn = ctk.CTkButton(
                self._bypass_frame,
                text=f"FS{fs}\nON",
                width=72,
                height=38,
                fg_color="#2a6a2a",
                hover_color="#235923",
                text_color="#ccffcc",
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda f=fs: self._toggle_fs_bypass(f),
            )
            btn.pack(side="left", padx=(8 if fs == 1 else 4, 4), pady=6)
            self._fs_btns.append(btn)

        # Add a "FS Bypass" toggle button to the MIDI menu
        # (wired via _toggle_bypass_panel)

    def _toggle_bypass_panel(self) -> None:
        self._bypass_panel_visible = not self._bypass_panel_visible
        if self._bypass_panel_visible:
            self._bypass_frame.pack(fill="x", side="top", after=self._scroll)
            # re-pack to place it between toolbar and grid
            self._bypass_frame.pack_forget()
            # Insert between toolbar and scrollable frame by re-ordering packs
            # Easiest approach: use place geometry on a known anchor
            self._bypass_frame.pack(fill="x", side="top",
                                    before=self._scroll)
        else:
            self._bypass_frame.pack_forget()

    def _toggle_fs_bypass(self, footswitch: int) -> None:
        if not self._midi.is_connected:
            messagebox.showwarning("Not connected",
                                   "Connect via MIDI → Connect… first.")
            return
        idx = footswitch - 1
        self._bypass_states[idx] = not self._bypass_states[idx]
        bypassed = self._bypass_states[idx]
        self._midi.set_effect_bypass(footswitch, bypassed)
        btn = self._fs_btns[idx]
        if bypassed:
            btn.configure(text=f"FS{footswitch}\nBYP",
                          fg_color="#6a2a2a", hover_color="#592323",
                          text_color="#ffcccc")
        else:
            btn.configure(text=f"FS{footswitch}\nON",
                          fg_color="#2a6a2a", hover_color="#235923",
                          text_color="#ccffcc")

    # ---- Tone grid ---------------------------------------------------

    def _build_grid(self) -> None:
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="#1c1c1c",
                                              corner_radius=0)
        self._scroll.pack(fill="both", expand=True)
        # Responsive column recalculation
        self._scroll.bind("<Configure>", self._on_grid_resize)

    def _on_grid_resize(self, event) -> None:
        new_cols = max(_MIN_COLS, event.width // (_CARD_W + 12))
        if new_cols != self._cols:
            self._cols = new_cols
            self._render_tones()

    # ---- Status bar --------------------------------------------------

    def _build_statusbar(self) -> None:
        bar = ctk.CTkFrame(self, height=32, fg_color=_BG_STATUS,
                           corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._dot_lbl = ctk.CTkLabel(
            bar, text="●", text_color=_COL_DISC,
            font=ctk.CTkFont(size=14))
        self._dot_lbl.pack(side="left", padx=(10, 4))

        self._active_lbl = ctk.CTkLabel(
            bar, text="No tone selected",
            font=ctk.CTkFont(size=12),
            text_color=_TEXT_DIM, anchor="w")
        self._active_lbl.pack(side="left", fill="x", expand=True)

        self._port_lbl = ctk.CTkLabel(
            bar, text="Not connected",
            font=ctk.CTkFont(size=11),
            text_color=_TEXT_DIM, anchor="e")
        self._port_lbl.pack(side="right", padx=10)

    # ------------------------------------------------------------------
    # Tone grid rendering
    # ------------------------------------------------------------------

    def _render_tones(self) -> None:
        for widget in self._scroll.winfo_children():
            widget.destroy()
        self._card_frames.clear()

        by_cat = self._tones.tones_by_category()
        row_offset = 0

        for cat, tones in by_cat.items():
            # Category separator
            self._render_category_separator(cat, row_offset)
            row_offset += 1

            for i, tone in enumerate(tones):
                card_row = row_offset + i // self._cols
                card_col = i % self._cols
                self._render_card(tone, card_row, card_col)
                self._scroll.columnconfigure(card_col, weight=1)

            row_offset += (len(tones) + self._cols - 1) // self._cols

    def _render_category_separator(self, cat: str, row: int) -> None:
        frame = ctk.CTkFrame(self._scroll, fg_color="transparent", height=28)
        frame.grid(row=row, column=0, columnspan=max(self._cols, 1),
                   sticky="ew", padx=4, pady=(14, 2))

        accent = ctk.CTkFrame(frame, width=4, height=20, fg_color=_ACCENT,
                               corner_radius=2)
        accent.pack(side="left", fill="y", padx=(4, 8))

        ctk.CTkLabel(
            frame,
            text=cat.upper(),
            font=ctk.CTkFont(family="Helvetica", size=10, weight="bold"),
            text_color=_TEXT_DIM,
            anchor="w",
        ).pack(side="left", anchor="w")

    def _render_card(self, tone: Tone, row: int, col: int) -> None:
        is_active    = tone.name == self._active
        is_focused   = tone.name == self._focused and not is_active
        border_color = _ACCENT if is_active else ("#555555" if is_focused else "#1c1c1c")
        fg           = _contrast_color(tone.color)
        sub_fg       = _muted_color(fg, tone.color, alpha=0.55)
        hover_color  = _adjust_brightness(tone.color)

        # Wrapper provides the accent border when this card is active
        wrapper = ctk.CTkFrame(
            self._scroll,
            fg_color=border_color,
            corner_radius=_CARD_RADIUS + 2,
        )
        wrapper.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        self._card_frames[tone.name] = wrapper

        # Card body — CTkFrame so name and subtitle can have independent fonts
        card = ctk.CTkFrame(
            wrapper,
            width=_CARD_W,
            height=_CARD_H,
            corner_radius=_CARD_RADIUS,
            fg_color=tone.color,
        )
        card.pack(padx=2, pady=2)
        card.pack_propagate(False)

        # Tone name — large bold
        name_lbl = ctk.CTkLabel(
            card,
            text=tone.name,
            font=ctk.CTkFont(family="Helvetica", size=13, weight="bold"),
            text_color=fg,
            wraplength=_CARD_W - 16,
            anchor="center",
        )
        name_lbl.pack(expand=True, pady=(12, 2))

        # MIDI detail — small, muted
        sub_lbl = ctk.CTkLabel(
            card,
            text=f"PC {tone.preset} · S{tone.snapshot + 1}",
            font=ctk.CTkFont(family="Helvetica", size=9),
            text_color=sub_fg,
            anchor="center",
        )
        sub_lbl.pack(pady=(0, 10))

        # Click + hover on all three surfaces
        def on_click(e, t=tone):   self._activate_tone(t)
        def on_enter(e):           card.configure(fg_color=hover_color)
        def on_leave(e):           card.configure(fg_color=tone.color)

        for w in (card, name_lbl, sub_lbl):
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>",    on_enter)
            w.bind("<Leave>",    on_leave)

        # Right-click context menu
        ctx = tk.Menu(self, tearoff=0,
                      bg="#2b2b2b", fg=_TEXT_BRIGHT,
                      activebackground=_ACCENT, activeforeground="#ffffff")
        ctx.add_command(label="✏  Edit",      command=lambda t=tone: self._edit_tone(t))
        ctx.add_command(label="⧉  Duplicate", command=lambda t=tone: self._duplicate_tone(t))
        ctx.add_command(label="🗑  Remove",    command=lambda t=tone: self._remove_tone(t))

        def show_ctx(event, menu=ctx, t=tone):
            self._active = t.name
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        for w in (card, name_lbl, sub_lbl):
            w.bind("<Button-3>", show_ctx)

    # ------------------------------------------------------------------
    # MIDI connection
    # ------------------------------------------------------------------

    def _open_connect_dialog(self) -> None:
        ConnectDialog(self, on_connect=self._do_connect)

    def _do_connect(self, port: str, channel: int) -> None:
        self._chan_var.set(channel)
        self._midi.channel = channel - 1
        try:
            self._midi.connect(port)
            self._update_status()
        except (ValueError, RuntimeError) as e:
            messagebox.showerror("Connection failed", str(e))

    def _disconnect(self) -> None:
        self._midi.disconnect()
        self._update_status()

    def _refresh_ports_silent(self) -> None:
        # Ports are fetched fresh in ConnectDialog._refresh(); nothing to do here
        # but we can show a quick confirmation
        ports = HXStompMidi.list_output_ports()
        messagebox.showinfo(
            "MIDI Ports",
            "Available ports:\n" + ("\n".join(f"  {p}" for p in ports) or "  (none)"),
        )

    def _update_status(self) -> None:
        if self._midi.is_connected:
            self._dot_lbl.configure(text_color=_COL_CONN)
            self._port_lbl.configure(text=self._midi.port_name)
        else:
            self._dot_lbl.configure(text_color=_COL_DISC)
            self._port_lbl.configure(text="Not connected")

    # ------------------------------------------------------------------
    # Tone actions
    # ------------------------------------------------------------------

    def _activate_tone(self, tone: Tone) -> None:
        if not self._midi.is_connected:
            messagebox.showwarning(
                "Not connected",
                "Use MIDI → Connect… to connect before selecting a tone.")
            return
        try:
            self._midi.select_preset_and_snapshot(
                preset   = tone.preset,
                snapshot = tone.snapshot,
                bank_msb = tone.bank_msb,
                bank_lsb = tone.bank_lsb,
            )
        except Exception as e:
            messagebox.showerror("MIDI error", str(e))
            return

        old = self._active
        self._active = tone.name
        self._focused = tone.name
        self._active_lbl.configure(
            text=f"{tone.name}  ·  Bank {tone.bank_lsb}  PC {tone.preset}  S{tone.snapshot + 1}",
            text_color=_TEXT_BRIGHT,
        )
        # Refresh border on old and new cards
        for name in (old, tone.name):
            if name and name in self._card_frames:
                color = _ACCENT if name == self._active else "#1c1c1c"
                self._card_frames[name].configure(fg_color=color)

    def _add_tone(self) -> None:
        dlg = ToneDialog(self, title="Add Tone")
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._tones.add(dlg.result)
                self._tones.save()
                self._render_tones()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

    def _duplicate_tone(self, tone: Tone | None = None) -> None:
        name = tone.name if tone else self._active
        if not name:
            messagebox.showinfo("Select a tone",
                                "Click a tone card first, or right-click one.")
            return
        existing = self._tones.get(name)
        if not existing:
            return
        import dataclasses
        copy = dataclasses.replace(existing, name=f"{existing.name} Copy")
        dlg = ToneDialog(self, title="Duplicate Tone", tone=copy)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._tones.add(dlg.result)
                self._tones.save()
                self._render_tones()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

    def _edit_tone(self, tone: Tone | None = None) -> None:
        name = tone.name if tone else self._active
        if not name:
            messagebox.showinfo("Select a tone",
                                "Click a tone card first, or right-click one.")
            return
        existing = self._tones.get(name)
        if not existing:
            return
        dlg = ToneDialog(self, title="Edit Tone", tone=existing)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._tones.update(dlg.result, old_name=name)
                self._tones.save()
                if self._active == name:
                    self._active = dlg.result.name
                self._render_tones()
            except (ValueError, KeyError) as e:
                messagebox.showerror("Error", str(e))

    def _remove_tone(self, tone: Tone | None = None) -> None:
        name = tone.name if tone else self._active
        if not name:
            messagebox.showinfo("Select a tone",
                                "Click a tone card first, or right-click one.")
            return
        if not messagebox.askyesno("Remove tone", f"Remove '{name}'?"):
            return
        try:
            self._tones.remove(name)
            self._tones.save()
            if self._active == name:
                self._active = None
                self._active_lbl.configure(text="No tone selected",
                                           text_color=_TEXT_DIM)
            self._render_tones()
        except KeyError as e:
            messagebox.showerror("Error", str(e))

    def _move_tone(self, direction: int) -> None:
        if not self._active:
            messagebox.showinfo("Select a tone",
                                "Click a tone card first to select it.")
            return
        try:
            self._tones.move(self._active, direction)
            self._tones.save()
            self._render_tones()
        except KeyError as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # Keyboard navigation
    # ------------------------------------------------------------------

    def _all_tones_flat(self) -> list[Tone]:
        """Return all tones in display order (category groups, insertion order within)."""
        result = []
        for tones in self._tones.tones_by_category().values():
            result.extend(tones)
        return result

    def _activate_by_index(self, index: int) -> None:
        flat = self._all_tones_flat()
        if 0 <= index < len(flat):
            tone = flat[index]
            self._focused = tone.name
            self._activate_tone(tone)

    def _kb_navigate(self, direction: int) -> None:
        flat = self._all_tones_flat()
        if not flat:
            return
        names = [t.name for t in flat]
        current = self._focused or self._active
        if current and current in names:
            idx = names.index(current)
        else:
            idx = -1 if direction > 0 else len(names)
        new_idx = max(0, min(len(names) - 1, idx + direction))
        self._focused = names[new_idx]
        # Highlight the focused card without sending MIDI
        self._render_tones()

    def _kb_activate(self) -> None:
        if not self._focused:
            return
        tone = self._tones.get(self._focused)
        if tone:
            self._activate_tone(tone)

    def _reload(self) -> None:
        self._tones.reload()
        self._render_tones()

    def _save(self) -> None:
        self._tones.save()

    # ------------------------------------------------------------------
    # Tuner
    # ------------------------------------------------------------------

    def _toggle_tuner(self) -> None:
        if not self._midi.is_connected:
            messagebox.showwarning("Not connected",
                                   "Connect via MIDI → Connect… first.")
            return
        self._tuner_state = not self._tuner_state
        self._midi.set_tuner(self._tuner_state)
        state_str = "ON" if self._tuner_state else "OFF"
        self._active_lbl.configure(
            text=f"Tuner {state_str}",
            text_color=_COL_DISC if self._tuner_state else _TEXT_DIM,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self._midi.disconnect()
        self.destroy()
