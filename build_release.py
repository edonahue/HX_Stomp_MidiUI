#!/usr/bin/env python3
"""
build_release.py — Post-PyInstaller packaging dispatcher.

Run AFTER ``pyinstaller hlx_generator.spec`` has produced dist/HLXGenerator/.

Usage:
    python build_release.py [--version X.Y.Z] [--arch ARCH]

The script auto-detects the platform and runs the appropriate packager:
  Linux   → dpkg-deb  → dist/hlx-generator_X.Y.Z_amd64.deb
  macOS   → hdiutil   → dist/HLXGenerator-X.Y.Z-{arch}.dmg
  Windows → makensis  → dist/HLXGenerator-X.Y.Z-Setup.exe
"""
from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT   = Path(__file__).resolve().parent
DIST_DIR    = REPO_ROOT / "dist"
APP_DIR     = DIST_DIR / "HLXGenerator"       # onedir output
APP_BUNDLE  = DIST_DIR / "HLXGenerator.app"   # macOS .app (from BUNDLE step)
PACKAGING   = REPO_ROOT / "packaging"


def _version() -> str:
    sys.path.insert(0, str(REPO_ROOT))
    from __version__ import VERSION
    return VERSION


# ---------------------------------------------------------------------------
# Linux — dpkg-deb
# ---------------------------------------------------------------------------

def build_linux(version: str, arch: str) -> Path:
    """Build a .deb package using dpkg-deb (always available on ubuntu-latest)."""
    if not APP_DIR.exists():
        raise FileNotFoundError(f"PyInstaller output not found: {APP_DIR}")

    deb_root = DIST_DIR / "deb_root"
    if deb_root.exists():
        shutil.rmtree(deb_root)

    install_dir = deb_root / "opt" / "hlx-generator"
    install_dir.mkdir(parents=True)
    shutil.copytree(APP_DIR, install_dir / "HLXGenerator")

    # Desktop launcher wrapper script
    bin_dir = deb_root / "usr" / "local" / "bin"
    bin_dir.mkdir(parents=True)
    launcher = bin_dir / "hlx-generator"
    launcher.write_text(
        "#!/bin/sh\nexec /opt/hlx-generator/HLXGenerator/HLXGenerator \"$@\"\n"
    )
    launcher.chmod(0o755)

    # Copy DEBIAN control files
    debian_src = PACKAGING / "deb" / "DEBIAN"
    debian_dst = deb_root / "DEBIAN"
    shutil.copytree(debian_src, debian_dst)

    # Expand version + arch into control file
    control_tpl = (debian_dst / "control").read_text()
    (debian_dst / "control").write_text(
        control_tpl.replace("${VERSION}", version).replace("${ARCH}", arch)
    )

    # Desktop + icon
    apps_dir = deb_root / "usr" / "share" / "applications"
    apps_dir.mkdir(parents=True)
    (apps_dir / "hlx-generator.desktop").write_text(
        "[Desktop Entry]\n"
        "Version=1.1\n"
        "Type=Application\n"
        "Name=HLX Generator\n"
        "Comment=MIDI soundboard and AI preset builder for Line 6 HX Stomp\n"
        "Exec=/usr/local/bin/hlx-generator\n"
        "Icon=hlx-generator\n"
        "Terminal=false\n"
        "Categories=Audio;Music;\n"
        "Keywords=guitar;pedal;midi;line6;\n"
    )

    src_icon = REPO_ROOT / "assets" / "icons" / "app-icon.png"
    if src_icon.exists():
        icon_dst = deb_root / "usr" / "share" / "pixmaps"
        icon_dst.mkdir(parents=True)
        shutil.copy(src_icon, icon_dst / "hlx-generator.png")

    out_deb = DIST_DIR / f"hlx-generator_{version}_{arch}.deb"
    subprocess.run(["dpkg-deb", "--build", str(deb_root), str(out_deb)], check=True)
    print(f"[deb] Created {out_deb}")
    return out_deb


# ---------------------------------------------------------------------------
# macOS — hdiutil DMG
# ---------------------------------------------------------------------------

def build_macos(version: str, arch: str) -> Path:
    """Create a drag-to-install DMG using hdiutil."""
    if not APP_BUNDLE.exists():
        raise FileNotFoundError(
            f"macOS .app bundle not found at {APP_BUNDLE}\n"
            "Did you run pyinstaller hlx_generator.spec on macOS?"
        )

    vol_name = f"HLX Generator {version}"
    out_dmg  = DIST_DIR / f"HLXGenerator-{version}-{arch}.dmg"

    with tempfile.TemporaryDirectory() as staging:
        staging_path = Path(staging)
        shutil.copytree(APP_BUNDLE, staging_path / "HLXGenerator.app")
        # Symlink to /Applications for convenience
        (staging_path / "Applications").symlink_to("/Applications")

        subprocess.run([
            "hdiutil", "create",
            "-volname", vol_name,
            "-srcfolder", staging,
            "-ov",
            "-format", "UDZO",
            str(out_dmg),
        ], check=True)

    print(f"[dmg] Created {out_dmg}")
    return out_dmg


# ---------------------------------------------------------------------------
# Windows — NSIS
# ---------------------------------------------------------------------------

def build_windows(version: str, arch: str) -> Path:
    """Build a Windows NSIS installer."""
    if not APP_DIR.exists():
        raise FileNotFoundError(f"PyInstaller output not found: {APP_DIR}")

    makensis = shutil.which("makensis")
    if not makensis:
        raise RuntimeError(
            "makensis not found.  Install NSIS: https://nsis.sourceforge.io/"
        )

    nsi_template = (PACKAGING / "nsis" / "installer.nsi.template").read_text()
    nsi_content  = (
        nsi_template
        .replace("${VERSION}", version)
        .replace("${ARCH}", arch)
        .replace("${DIST_DIR}", str(DIST_DIR).replace("\\", "\\\\"))
        .replace("${APP_DIR}", str(APP_DIR).replace("\\", "\\\\"))
    )

    nsi_path = DIST_DIR / "installer.nsi"
    nsi_path.write_text(nsi_content, encoding="utf-8")

    subprocess.run([makensis, str(nsi_path)], check=True)

    out_exe = DIST_DIR / f"HLXGenerator-{version}-Setup.exe"
    print(f"[nsis] Created {out_exe}")
    return out_exe


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build platform release package")
    parser.add_argument("--version", default=None, help="Override version string")
    parser.add_argument(
        "--arch", default=None,
        help="Architecture label (e.g. amd64, arm64, x86_64). Auto-detected if omitted."
    )
    args = parser.parse_args()

    version = args.version or _version()
    machine = platform.machine().lower()
    arch    = args.arch or {
        "x86_64": "amd64", "amd64": "amd64",
        "arm64": "arm64",  "aarch64": "arm64",
    }.get(machine, machine)

    system = platform.system()
    print(f"Platform: {system} / arch: {arch} / version: {version}")

    DIST_DIR.mkdir(exist_ok=True)

    if system == "Linux":
        build_linux(version, arch)
    elif system == "Darwin":
        build_macos(version, arch)
    elif system == "Windows":
        build_windows(version, arch)
    else:
        print(f"ERROR: Unsupported platform: {system}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
