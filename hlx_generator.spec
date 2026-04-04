# hlx_generator.spec — PyInstaller build specification for HLX Generator.
#
# Build:
#   pyinstaller hlx_generator.spec
#
# Produces dist/HLXGenerator/ (onedir) on all platforms.
# Run build_release.py after PyInstaller to wrap into the platform installer.

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ---------------------------------------------------------------------------
# Version (read from source so it stays in sync)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(SPECPATH)))
from __version__ import VERSION

# ---------------------------------------------------------------------------
# Data files to bundle
# ---------------------------------------------------------------------------
datas = []

# customtkinter ships its own theme JSON / images — must be bundled
datas += collect_data_files("customtkinter")

# Our own PNG icon set
datas += [("assets/icons", "assets/icons")]

# Default tone definitions (shipped so the app works out-of-the-box)
datas += [("presets.json", ".")]

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hiddenimports = []

# Pillow sub-modules that PIL's lazy loader may miss
hiddenimports += collect_submodules("PIL")

# LLM provider SDKs (all three bundled; user activates via config)
hiddenimports += [
    "anthropic",
    "anthropic._legacy_response",
    "openai",
    "openai._models",
    "google.generativeai",
    "google.generativeai.types",
]

# MIDI
hiddenimports += ["mido", "mido.backends.rtmidi", "rtmidi"]

# ---------------------------------------------------------------------------
# Platform-specific icon
# ---------------------------------------------------------------------------
if sys.platform == "darwin":
    icon_file = "assets/icons/app-icon.icns"
elif sys.platform == "win32":
    icon_file = "assets/icons/app-icon.ico"
else:
    icon_file = None  # Linux: set via .desktop file

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    ["main.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep the bundle lean — exclude test/dev-only packages
        "pytest",
        "unittest",
        "IPython",
        "jupyter",
        "notebook",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir mode — binaries go in COLLECT
    name="HLXGenerator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # no terminal window
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HLXGenerator",
)

# macOS: wrap COLLECT into a proper .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="HLXGenerator.app",
        icon=icon_file,
        bundle_identifier="com.edonahue.hlx-generator",
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15",
            "NSHumanReadableCopyright": "© 2024 edonahue. MIT License.",
        },
    )
