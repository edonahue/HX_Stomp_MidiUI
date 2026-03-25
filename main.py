"""
main.py

Entry point for the HX Stomp Soundboard.

Usage
-----
    python main.py [--presets presets.json]

Optional flags
--------------
    --presets   Path to the JSON file containing tone definitions.
                Defaults to presets.json in the current directory.
    --list-ports  Print available MIDI output ports and exit.
"""

import argparse
import sys

from midi_interface import HXStompMidi
from soundboard_ui import SoundboardApp


def main() -> None:
    parser = argparse.ArgumentParser(description="HX Stomp MIDI Soundboard")
    parser.add_argument(
        "--presets", default="presets.json",
        help="Path to tone definitions JSON file (default: presets.json)"
    )
    parser.add_argument(
        "--list-ports", action="store_true",
        help="Print available MIDI output ports and exit"
    )
    args = parser.parse_args()

    if args.list_ports:
        ports = HXStompMidi.list_output_ports()
        if ports:
            print("Available MIDI output ports:")
            for i, p in enumerate(ports):
                print(f"  [{i}] {p}")
        else:
            print("No MIDI output ports found.")
        sys.exit(0)

    app = SoundboardApp(presets_file=args.presets)
    app.mainloop()


if __name__ == "__main__":
    main()
