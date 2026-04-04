"""
icon_manager.py — CTkImage icon loader with graceful fallback.

Icons are sourced from assets/icons/*.png (Phosphor Icons, MIT license).
If the directory or a specific file is missing the helpers return None and
all callers silently fall back to emoji/text-only buttons — no crashes.

Usage:
    from icon_manager import get_icon, icon_btn

    btn = icon_btn(parent, "trash", "Remove", fg_color="transparent", ...)
    lbl = ctk.CTkLabel(parent, image=get_icon("check-circle", SM), text="")
"""
from __future__ import annotations

import functools
from pathlib import Path

import customtkinter as ctk

from _resource import resource_path

try:
    from PIL import Image as _PilImage
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# ---------------------------------------------------------------------------
# Size constants (logical pixels — CTkImage scales for HiDPI automatically)
# ---------------------------------------------------------------------------
SM = (14, 14)   # status dots, small inline indicators
MD = (18, 18)   # toolbar / dialog buttons  (default)
LG = (20, 20)   # primary action buttons

_ICON_DIR = resource_path("assets/icons")


@functools.lru_cache(maxsize=None)
def get_icon(name: str, size: tuple[int, int] = MD) -> "ctk.CTkImage | None":
    """Return a cached CTkImage for *name*.png, or None if unavailable.

    The icon is loaded once per (name, size) pair and kept alive by the cache.
    Passing the returned value to a CTkButton/CTkLabel ``image=`` parameter is
    safe — the cache reference prevents Tkinter garbage collection.
    """
    if not _PIL_OK:
        return None
    path = _ICON_DIR / f"{name}.png"
    if not path.exists():
        return None
    try:
        img = _PilImage.open(path).convert("RGBA")
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None


def icon_btn(
    parent,
    icon_name: str,
    text: str = "",
    size: tuple[int, int] = MD,
    **kwargs,
) -> ctk.CTkButton:
    """Create a CTkButton with an optional leading icon.

    If the icon file is missing the button renders with text/emoji only —
    identical appearance to the pre-icon implementation.  All extra keyword
    arguments are forwarded to CTkButton unchanged.
    """
    img = get_icon(icon_name, size)
    if img is not None:
        label = f"  {text}" if text else ""
        compound = "left" if text else "center"
        return ctk.CTkButton(parent, image=img, text=label,
                             compound=compound, **kwargs)
    # Fallback — plain text button, caller keeps the emoji in text= if desired
    return ctk.CTkButton(parent, text=text, **kwargs)
