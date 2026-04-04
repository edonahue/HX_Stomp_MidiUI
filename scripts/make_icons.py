#!/usr/bin/env python3
"""
scripts/make_icons.py — Convert app-icon.png → platform icon formats.

Generates:
  assets/icons/app-icon.icns   (macOS, multi-resolution)
  assets/icons/app-icon.ico    (Windows, multi-resolution)

Requires Pillow:
    pip install Pillow

Usage:
    python scripts/make_icons.py
"""
from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required.  Run: pip install Pillow")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_PNG   = REPO_ROOT / "assets" / "icons" / "app-icon.png"
OUT_ICNS  = REPO_ROOT / "assets" / "icons" / "app-icon.icns"
OUT_ICO   = REPO_ROOT / "assets" / "icons" / "app-icon.ico"

# Sizes required for a proper macOS .icns (iconutil iconset)
ICNS_SIZES = [16, 32, 64, 128, 256, 512, 1024]

# Sizes embedded in the Windows .ico
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def make_ico(src: Image.Image) -> None:
    """Save a multi-resolution .ico file."""
    frames = [src.resize((s, s), Image.LANCZOS).convert("RGBA") for s in ICO_SIZES]
    frames[0].save(
        OUT_ICO,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=frames[1:],
    )
    print(f"  Created {OUT_ICO}")


def make_icns_iconutil(src: Image.Image) -> bool:
    """Use macOS iconutil to build .icns (only works on macOS)."""
    if not Path("/usr/bin/iconutil").exists():
        return False
    with tempfile.TemporaryDirectory(suffix=".iconset") as iconset:
        iconset_path = Path(iconset)
        for size in ICNS_SIZES:
            for scale, suffix in [(1, ""), (2, "@2x")]:
                px = size * scale
                if px > 1024:
                    continue
                fname = f"icon_{size}x{size}{suffix}.png"
                img = src.resize((px, px), Image.LANCZOS).convert("RGBA")
                img.save(iconset_path / fname)
        result = subprocess.run(
            ["iconutil", "-c", "icns", iconset, "-o", str(OUT_ICNS)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  iconutil error: {result.stderr}")
            return False
    print(f"  Created {OUT_ICNS}")
    return True


def make_icns_pillow(src: Image.Image) -> None:
    """Fallback: write a minimal ICNS using Pillow's ICNS encoder."""
    # Pillow supports writing .icns directly on all platforms
    src.resize((1024, 1024), Image.LANCZOS).convert("RGBA").save(
        OUT_ICNS, format="ICNS"
    )
    print(f"  Created {OUT_ICNS} (single-size fallback — use macOS for full iconset)")


def main() -> None:
    if not SRC_PNG.exists():
        print(f"ERROR: Source icon not found at {SRC_PNG}")
        sys.exit(1)

    src = Image.open(SRC_PNG).convert("RGBA")
    print(f"Source: {SRC_PNG} ({src.size[0]}×{src.size[1]})")

    # Windows .ico (cross-platform)
    make_ico(src)

    # macOS .icns — prefer iconutil, fall back to Pillow
    if not make_icns_iconutil(src):
        make_icns_pillow(src)

    print("Done.")


if __name__ == "__main__":
    main()
