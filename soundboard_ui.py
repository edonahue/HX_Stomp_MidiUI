"""
soundboard_ui.py

Tkinter soundboard UI for the HX Stomp.

Layout
------
  Top bar  : MIDI port selector + Connect/Disconnect button + status label
  Toolbar  : Add Tone | Edit Tone | Remove Tone | Reload buttons
  Main area: Scrollable grid of tone buttons, optionally grouped by category
  Bottom   : Active tone label + tuner toggle
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser
from typing import Optional

from midi_interface import HXStompMidi
from tone_manager import Tone, ToneManager


# ---------------------------------------------------------------------------
# Helper dialogs
# ---------------------------------------------------------------------------

class ToneDialog(tk.Toplevel):
    """Modal dialog for creating or editing a Tone."""

    def __init__(self, parent, title: str = "Tone", tone: Tone | None = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: Optional[Tone] = None

        tone = tone or Tone(name="", preset=0)

        fields = [
            ("Name",      "name",     tone.name),
            ("Preset (0-127)", "preset",  str(tone.preset)),
            ("Snapshot (0-7)", "snapshot", str(tone.snapshot)),
            ("Bank MSB",  "bank_msb", str(tone.bank_msb)),
            ("Bank LSB",  "bank_lsb", str(tone.bank_lsb)),
            ("Category",  "category", tone.category or ""),
        ]

        self._vars: dict[str, tk.StringVar] = {}
        for row, (label, key, default) in enumerate(fields):
            tk.Label(self, text=label, anchor="w").grid(
                row=row, column=0, padx=8, pady=4, sticky="w")
            var = tk.StringVar(value=default)
            self._vars[key] = var
            tk.Entry(self, textvariable=var, width=22).grid(
                row=row, column=1, padx=8, pady=4)

        # Color picker
        self._color = tone.color
        color_row = len(fields)
        tk.Label(self, text="Color", anchor="w").grid(
            row=color_row, column=0, padx=8, pady=4, sticky="w")
        self._color_btn = tk.Button(
            self, bg=self._color, width=6, command=self._pick_color)
        self._color_btn.grid(row=color_row, column=1, padx=8, pady=4, sticky="w")

        # Buttons
        btn_row = color_row + 1
        tk.Button(self, text="OK",     width=8, command=self._ok).grid(
            row=btn_row, column=0, padx=8, pady=8)
        tk.Button(self, text="Cancel", width=8, command=self.destroy).grid(
            row=btn_row, column=1, padx=8, pady=8)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _pick_color(self) -> None:
        color = colorchooser.askcolor(color=self._color, parent=self)
        if color and color[1]:
            self._color = color[1]
            self._color_btn.configure(bg=self._color)

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

class SoundboardApp(tk.Tk):

    COLS = 4  # tone buttons per row

    def __init__(self, presets_file: str = "presets.json"):
        super().__init__()
        self.title("HX Stomp Soundboard")
        self.minsize(640, 480)

        self._midi   = HXStompMidi()
        self._tones  = ToneManager(presets_file)
        self._active: Optional[str] = None

        self._build_ui()
        self._refresh_ports()
        self._render_tones()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # ---- Top bar: port selection ----------------------------------
        top = tk.Frame(self, bd=1, relief=tk.GROOVE)
        top.pack(fill=tk.X, padx=6, pady=4)

        tk.Label(top, text="MIDI Port:").pack(side=tk.LEFT, padx=(4, 2))
        self._port_var = tk.StringVar()
        self._port_cb  = ttk.Combobox(
            top, textvariable=self._port_var, width=34, state="readonly")
        self._port_cb.pack(side=tk.LEFT, padx=2)

        tk.Button(top, text="Refresh",    command=self._refresh_ports).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="Connect",    command=self._connect).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="Disconnect", command=self._disconnect).pack(side=tk.LEFT, padx=2)

        tk.Label(top, text="Channel:").pack(side=tk.LEFT, padx=(10, 2))
        self._chan_var = tk.IntVar(value=1)
        tk.Spinbox(top, from_=1, to=16, textvariable=self._chan_var, width=4).pack(side=tk.LEFT)

        self._status_var = tk.StringVar(value="Disconnected")
        tk.Label(top, textvariable=self._status_var, fg="gray").pack(
            side=tk.RIGHT, padx=8)

        # ---- Toolbar -------------------------------------------------
        toolbar = tk.Frame(self)
        toolbar.pack(fill=tk.X, padx=6, pady=2)

        tk.Button(toolbar, text="+ Add Tone",    command=self._add_tone).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="✎ Edit Tone",   command=self._edit_tone).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="✕ Remove Tone", command=self._remove_tone).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="↺ Reload",      command=self._reload).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="💾 Save",        command=self._save).pack(side=tk.LEFT, padx=2)

        # ---- Scrollable tone grid ------------------------------------
        container = tk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._grid_frame = tk.Frame(canvas)
        self._grid_win = canvas.create_window((0, 0), window=self._grid_frame, anchor="nw")

        self._grid_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._grid_win, width=e.width))
        # Mouse-wheel scrolling
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # ---- Bottom bar ----------------------------------------------
        bottom = tk.Frame(self, bd=1, relief=tk.GROOVE)
        bottom.pack(fill=tk.X, padx=6, pady=4)

        self._active_var = tk.StringVar(value="No tone selected")
        tk.Label(bottom, textvariable=self._active_var, anchor="w").pack(
            side=tk.LEFT, padx=8)

        self._tuner_on = False
        self._tuner_btn = tk.Button(bottom, text="Tuner OFF",
                                    command=self._toggle_tuner, width=10)
        self._tuner_btn.pack(side=tk.RIGHT, padx=8, pady=4)

    # ------------------------------------------------------------------
    # MIDI connection
    # ------------------------------------------------------------------

    def _refresh_ports(self) -> None:
        ports = HXStompMidi.list_output_ports()
        self._port_cb["values"] = ports
        if ports:
            # Auto-select the HX Stomp if detected
            auto = HXStompMidi.find_hx_port()
            self._port_var.set(auto or ports[0])

    def _connect(self) -> None:
        port = self._port_var.get()
        if not port:
            messagebox.showwarning("No port", "Select a MIDI port first.")
            return
        self._midi.channel = self._chan_var.get() - 1  # 1-based → 0-based
        try:
            self._midi.connect(port)
            self._status_var.set(f"Connected: {self._midi.port_name}")
        except (ValueError, RuntimeError) as e:
            messagebox.showerror("Connection failed", str(e))

    def _disconnect(self) -> None:
        self._midi.disconnect()
        self._status_var.set("Disconnected")

    # ------------------------------------------------------------------
    # Tone grid rendering
    # ------------------------------------------------------------------

    def _render_tones(self) -> None:
        for widget in self._grid_frame.winfo_children():
            widget.destroy()

        by_cat = self._tones.tones_by_category()

        row_offset = 0
        for cat, tones in by_cat.items():
            # Category label
            lbl = tk.Label(
                self._grid_frame, text=cat,
                font=("Helvetica", 10, "bold"),
                anchor="w", bg="#2b2b2b", fg="white",
                padx=6, pady=2,
            )
            lbl.grid(row=row_offset, column=0,
                     columnspan=self.COLS, sticky="ew", pady=(8, 2))
            row_offset += 1

            for i, tone in enumerate(tones):
                btn_row = row_offset + i // self.COLS
                btn_col = i % self.COLS

                # Pick a readable text color based on button background
                fg = self._contrast_color(tone.color)

                btn = tk.Button(
                    self._grid_frame,
                    text=self._tone_label(tone),
                    bg=tone.color,
                    fg=fg,
                    activebackground=tone.color,
                    font=("Helvetica", 10, "bold"),
                    relief=tk.RAISED,
                    bd=3,
                    padx=10,
                    pady=14,
                    wraplength=130,
                    command=lambda t=tone: self._activate_tone(t),
                )
                btn.grid(row=btn_row, column=btn_col,
                         padx=4, pady=4, sticky="nsew")
                self._grid_frame.columnconfigure(btn_col, weight=1)

            num_rows = (len(tones) + self.COLS - 1) // self.COLS
            row_offset += num_rows

    @staticmethod
    def _tone_label(tone: Tone) -> str:
        lines = [tone.name]
        lines.append(f"Bank {tone.bank_lsb} · PC {tone.preset} · Snap {tone.snapshot + 1}")
        return "\n".join(lines)

    @staticmethod
    def _contrast_color(hex_color: str) -> str:
        """Return black or white depending on background brightness."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            return "#000000"
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return "#000000" if luminance > 128 else "#ffffff"

    # ------------------------------------------------------------------
    # Tone actions
    # ------------------------------------------------------------------

    def _activate_tone(self, tone: Tone) -> None:
        if not self._midi.is_connected:
            messagebox.showwarning(
                "Not connected",
                "Connect to a MIDI port before selecting a tone.")
            return
        try:
            self._midi.select_preset_and_snapshot(
                preset   = tone.preset,
                snapshot = tone.snapshot,
                bank_msb = tone.bank_msb,
                bank_lsb = tone.bank_lsb,
            )
            self._active = tone.name
            self._active_var.set(
                f"Active: {tone.name}  "
                f"(Bank {tone.bank_lsb} · PC {tone.preset} · Snap {tone.snapshot + 1})"
            )
        except Exception as e:
            messagebox.showerror("MIDI error", str(e))

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

    def _edit_tone(self) -> None:
        if not self._active:
            messagebox.showinfo("Select a tone", "Click a tone button first to select it.")
            return
        tone = self._tones.get(self._active)
        if not tone:
            return
        dlg = ToneDialog(self, title="Edit Tone", tone=tone)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._tones.update(dlg.result)
                self._tones.save()
                self._render_tones()
            except (ValueError, KeyError) as e:
                messagebox.showerror("Error", str(e))

    def _remove_tone(self) -> None:
        if not self._active:
            messagebox.showinfo("Select a tone", "Click a tone button first to select it.")
            return
        if not messagebox.askyesno("Remove tone",
                                   f"Remove '{self._active}'?"):
            return
        try:
            self._tones.remove(self._active)
            self._tones.save()
            self._active = None
            self._active_var.set("No tone selected")
            self._render_tones()
        except KeyError as e:
            messagebox.showerror("Error", str(e))

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
            messagebox.showwarning("Not connected", "Connect to MIDI first.")
            return
        self._tuner_on = not self._tuner_on
        self._midi.set_tuner(self._tuner_on)
        label = "Tuner ON" if self._tuner_on else "Tuner OFF"
        color = "#e74c3c"  if self._tuner_on else ""
        self._tuner_btn.configure(text=label, bg=color or self.cget("bg"))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self._midi.disconnect()
        self.destroy()
