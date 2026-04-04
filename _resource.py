"""
_resource.py — PyInstaller-safe resource path resolver.

When frozen by PyInstaller (onedir mode), data files are extracted into a
temporary directory referenced by ``sys._MEIPASS``.  This helper abstracts
that so the rest of the codebase can use relative paths transparently.

Usage::

    from _resource import resource_path
    icon = resource_path("assets/icons/app-icon.png")
"""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Return an absolute Path to a bundled resource.

    * In a PyInstaller-frozen build ``sys._MEIPASS`` holds the temp dir where
      data files were extracted; we resolve relative to that.
    * In normal (source) execution we resolve relative to this file's parent
      directory (the repo/package root).
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / relative
