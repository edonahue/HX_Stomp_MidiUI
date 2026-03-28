"""
main.py

Entry point for the HX Stomp Soundboard.

Usage
-----
    python main.py [--presets presets.json] [--mock-midi] [--list-ports]

Optional flags
--------------
    --presets     Path to the JSON file containing tone definitions.
                  Defaults to presets.json in the current directory.
    --list-ports  Print available MIDI output ports and exit.
    --mock-midi   Use a mock MIDI backend — no HX Stomp hardware needed.
                  All MIDI messages are printed to stdout instead of sent.
                  Useful for UI development and testing.
"""

from __future__ import annotations

import argparse
import sys

try:
    import soundboard_ui
    from midi_interface import HXStompMidi, _FS_CC
    from soundboard_ui import SoundboardApp
except ImportError as _exc:
    print(
        f"Missing dependency: {_exc}\n"
        "Install requirements with:  pip install -r requirements.txt\n"
        "On Linux you may also need: sudo apt install libasound2-dev libjack-dev"
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Mock MIDI backend (no hardware required)
# ---------------------------------------------------------------------------

class MockHXStompMidi:
    """
    Drop-in replacement for HXStompMidi that prints MIDI messages to stdout
    instead of sending them to a real device.  Injected via --mock-midi.
    Mirrors the full public API of HXStompMidi.
    """

    def __init__(self, port_name: str = None, channel: int = 0):
        self.channel = channel
        self._connected = False
        self._port_name = ""
        self._tuner_active = False
        if port_name:
            self.connect(port_name)

    # Port management --------------------------------------------------

    @staticmethod
    def list_output_ports() -> list[str]:
        return ["Mock HX Stomp [USB]", "Mock Virtual Port 1"]

    @staticmethod
    def find_hx_port() -> str | None:
        return "Mock HX Stomp [USB]"

    def connect(self, port_name: str) -> None:
        self._connected = True
        self._port_name = port_name
        self._tuner_active = False
        print(f"[MockMIDI] Connected → {port_name}")

    def connect_first_available(self) -> str:
        self.connect(self.list_output_ports()[0])
        return self._port_name

    def disconnect(self) -> None:
        if self._connected:
            print("[MockMIDI] Disconnected")
        self._connected = False
        self._port_name = ""

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def port_name(self) -> str:
        return self._port_name

    @property
    def tuner_active(self) -> bool:
        return self._tuner_active

    # Low-level --------------------------------------------------------

    def send_cc(self, control: int, value: int) -> None:
        print(f"[MockMIDI] CC  ch={self.channel + 1}  cc={control}  val={value}")

    def send_program_change(self, program: int) -> None:
        print(f"[MockMIDI] PC  ch={self.channel + 1}  program={program}")

    # Preset / snapshot ------------------------------------------------

    def select_preset(self, preset: int,
                      bank_msb: int = 0, bank_lsb: int = 0) -> None:
        print(f"[MockMIDI] Preset → bank({bank_msb},{bank_lsb})  PC {preset}")

    def select_snapshot(self, snapshot: int) -> None:
        if snapshot not in range(10):
            raise ValueError(f"Snapshot must be 0–9 (got {snapshot})")
        labels = {8: "next", 9: "previous"}
        label = labels.get(snapshot, str(snapshot + 1))
        print(f"[MockMIDI] Snapshot → {label}")

    def select_preset_and_snapshot(self, preset: int, snapshot: int = 0,
                                   bank_msb: int = 0, bank_lsb: int = 0) -> None:
        self.select_preset(preset, bank_msb, bank_lsb)
        self.select_snapshot(snapshot)

    def next_snapshot(self) -> None:
        self.select_snapshot(8)

    def prev_snapshot(self) -> None:
        self.select_snapshot(9)

    # Footswitches -----------------------------------------------------

    def press_footswitch(self, fs: int) -> None:
        if fs not in _FS_CC:
            valid = sorted(_FS_CC)
            raise ValueError(
                f"Invalid footswitch {fs}. Valid: {valid} (FS6 does not exist)")
        print(f"[MockMIDI] FS{fs} press (toggle block)")

    def release_footswitch(self, fs: int) -> None:
        if fs not in _FS_CC:
            raise ValueError(f"Invalid footswitch {fs}.")
        print(f"[MockMIDI] FS{fs} release")

    # Expression pedals ------------------------------------------------

    def set_exp1(self, value: int) -> None:
        if not 0 <= value <= 127:
            raise ValueError(f"EXP value must be 0–127 (got {value})")
        print(f"[MockMIDI] EXP1 → {value}")

    def set_exp2(self, value: int) -> None:
        if not 0 <= value <= 127:
            raise ValueError(f"EXP value must be 0–127 (got {value})")
        print(f"[MockMIDI] EXP2 → {value}")

    def set_exp_toe(self, engaged: bool) -> None:
        print(f"[MockMIDI] EXP Toe → {'engaged' if engaged else 'released'}")

    # Tap tempo --------------------------------------------------------

    def tap_tempo(self) -> None:
        print("[MockMIDI] Tap Tempo ♩")

    # Tuner ------------------------------------------------------------

    def toggle_tuner(self) -> bool:
        self._tuner_active = not self._tuner_active
        print(f"[MockMIDI] Tuner {'ON' if self._tuner_active else 'OFF'}")
        return self._tuner_active

    def set_tuner(self, on: bool) -> None:
        if self._tuner_active != on:
            self.toggle_tuner()

    # Looper -----------------------------------------------------------

    def looper_record(self) -> None:     print("[MockMIDI] Looper → Record")
    def looper_overdub(self) -> None:    print("[MockMIDI] Looper → Overdub")
    def looper_play(self) -> None:       print("[MockMIDI] Looper → Play")
    def looper_stop(self) -> None:       print("[MockMIDI] Looper → Stop")
    def looper_play_once(self) -> None:  print("[MockMIDI] Looper → Play Once")
    def looper_undo_redo(self) -> None:  print("[MockMIDI] Looper → Undo/Redo")

    def looper_reverse(self, on: bool) -> None:
        print(f"[MockMIDI] Looper Reverse → {'ON' if on else 'OFF'}")

    def looper_half_speed(self, on: bool) -> None:
        print(f"[MockMIDI] Looper Half Speed → {'ON' if on else 'OFF'}")

    def looper_enabled(self, on: bool) -> None:
        print(f"[MockMIDI] Looper Block → {'ON' if on else 'OFF'}")

    def __enter__(self):  return self
    def __exit__(self, *_): self.disconnect()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _install_desktop() -> None:
    """
    Install the .desktop launcher and app icon into the user's XDG directories.

    Installs icons at 48, 128, 256, 512 px into ~/.local/share/icons/hicolor/
    and creates ~/.local/share/applications/hxstomp.desktop.

    Safe to re-run — it overwrites any previous installation.
    """
    import shutil
    import subprocess
    from pathlib import Path

    src_icon = Path(__file__).parent / "assets" / "icons" / "app-icon.png"
    if not src_icon.exists():
        print(f"ERROR: App icon not found at {src_icon}")
        sys.exit(1)

    # ── Icons ──────────────────────────────────────────────────────────────────
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is required. Run: pip install Pillow")
        sys.exit(1)

    icon_base = Path.home() / ".local" / "share" / "icons" / "hicolor"
    img = Image.open(src_icon)
    for size in (48, 128, 256, 512):
        dest_dir = icon_base / f"{size}x{size}" / "apps"
        dest_dir.mkdir(parents=True, exist_ok=True)
        img.resize((size, size), Image.LANCZOS).save(dest_dir / "hxstomp.png")
        print(f"  Icon {size}x{size} → {dest_dir / 'hxstomp.png'}")

    # Write a minimal index.theme so icon tools can cache it
    index = icon_base / "index.theme"
    if not index.exists():
        index.write_text(
            "[Icon Theme]\nName=hicolor\nComment=Hicolor theme\n"
            "Directories=48x48/apps,128x128/apps,256x256/apps,512x512/apps\n\n"
            "[48x48/apps]\nSize=48\nContext=Applications\nType=Fixed\n\n"
            "[128x128/apps]\nSize=128\nContext=Applications\nType=Fixed\n\n"
            "[256x256/apps]\nSize=256\nContext=Applications\nType=Fixed\n\n"
            "[512x512/apps]\nSize=512\nContext=Applications\nType=Fixed\n"
        )

    for cmd in (
        ["gtk-update-icon-cache", "-f", str(icon_base)],
        ["update-desktop-database", str(Path.home() / ".local" / "share" / "applications")],
    ):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, capture_output=True)

    # ── .desktop file ──────────────────────────────────────────────────────────
    app_dir = Path.home() / ".local" / "share" / "applications"
    app_dir.mkdir(parents=True, exist_ok=True)
    python_bin = shutil.which("python3") or sys.executable
    main_py    = Path(__file__).resolve()
    desktop    = app_dir / "hxstomp.desktop"
    desktop.write_text(
        "[Desktop Entry]\n"
        "Version=1.1\n"
        "Type=Application\n"
        "Name=HX Stomp Soundboard\n"
        "GenericName=Guitar Pedal Controller\n"
        "Comment=MIDI soundboard for the Line 6 HX Stomp guitar processor\n"
        f"Exec={python_bin} {main_py} %F\n"
        "Icon=hxstomp\n"
        "Terminal=false\n"
        "Categories=Audio;Music;MIDI;\n"
        "Keywords=guitar;pedal;midi;line6;hx;stomp;\n"
        "StartupNotify=true\n"
        "StartupWMClass=hxstomp\n"
    )
    print(f"  .desktop    → {desktop}")

    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(app_dir)], capture_output=True)

    print("\nInstalled. The app will appear in your application launcher.")
    print("If you use the Cosmic dock, log out and back in to refresh it.")


def main() -> None:
    parser = argparse.ArgumentParser(description="HX Stomp MIDI Soundboard")
    parser.add_argument(
        "--presets", default="presets.json",
        help="Path to tone definitions JSON file (default: presets.json)",
    )
    parser.add_argument(
        "--list-ports", action="store_true",
        help="Print available MIDI output ports and exit",
    )
    parser.add_argument(
        "--mock-midi", action="store_true",
        help="Use mock MIDI backend (no hardware needed; messages printed to stdout)",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Disable AI tone generation (✨ Generate button shows info dialog)",
    )
    parser.add_argument(
        "--install-desktop", action="store_true",
        help="Install the .desktop launcher and app icon for the system (Pop!_OS / GNOME / KDE)",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="API key for the configured LLM provider (saves to ~/.hxstomp/config.json)",
    )
    parser.add_argument(
        "--llm-provider", default=None,
        choices=["anthropic", "openai", "ollama", "gemini"],
        help="Override LLM provider from config",
    )
    args = parser.parse_args()

    if args.install_desktop:
        _install_desktop()
        sys.exit(0)

    if args.list_ports:
        ports = HXStompMidi.list_output_ports()
        if ports:
            print("Available MIDI output ports:")
            for i, p in enumerate(ports):
                print(f"  [{i}] {p}")
        else:
            print("No MIDI output ports found.")
        sys.exit(0)

    if args.mock_midi:
        # Patch the HXStompMidi class used inside soundboard_ui at import time
        soundboard_ui.HXStompMidi = MockHXStompMidi
        print("[MockMIDI] Mock MIDI backend active — no hardware required.")

    if args.api_key or args.llm_provider:
        from llm_generator import load_config, save_config
        cfg = load_config()
        if args.llm_provider:
            cfg["provider"] = args.llm_provider
        if args.api_key:
            provider = cfg.get("provider", "anthropic")
            cfg[f"{provider}_api_key"] = args.api_key
        save_config(cfg)

    app = SoundboardApp(presets_file=args.presets, no_llm=args.no_llm)
    app.mainloop()


if __name__ == "__main__":
    main()
