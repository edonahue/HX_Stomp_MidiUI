"""
test_build_release.py

Tests for build_release.py — cross-platform packaging dispatcher.

All tests are offline: subprocess.run is mocked so no real packaging tools
(dpkg-deb, hdiutil, makensis) are required.

Run with:
    python -m unittest test_build_release -v
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

import build_release


# ===========================================================================
# Group K1: Version detection
# ===========================================================================

class TestVersion(unittest.TestCase):

    def test_version_from_version_file(self):
        version = build_release._version()
        self.assertIsInstance(version, str)
        # Must match semver-ish pattern: "1.0.0"
        parts = version.split(".")
        self.assertEqual(len(parts), 3)
        for part in parts:
            self.assertTrue(part.isdigit(), f"Non-numeric version component: {part!r}")

    def test_version_matches_version_module(self):
        from __version__ import VERSION
        self.assertEqual(build_release._version(), VERSION)


# ===========================================================================
# Group K2: Architecture auto-detection
# ===========================================================================

class TestArchDetection(unittest.TestCase):
    """Tests the arch mapping used in main() (replicated inline for isolation)."""

    _ARCH_MAP = {
        "x86_64": "amd64", "amd64": "amd64",
        "arm64": "arm64", "aarch64": "arm64",
    }

    def _detect(self, machine: str) -> str:
        return self._ARCH_MAP.get(machine, machine)

    def test_x86_64_maps_to_amd64(self):
        self.assertEqual(self._detect("x86_64"), "amd64")

    def test_amd64_maps_to_amd64(self):
        self.assertEqual(self._detect("amd64"), "amd64")

    def test_arm64_maps_to_arm64(self):
        self.assertEqual(self._detect("arm64"), "arm64")

    def test_aarch64_maps_to_arm64(self):
        self.assertEqual(self._detect("aarch64"), "arm64")

    def test_unknown_passthrough(self):
        self.assertEqual(self._detect("riscv64"), "riscv64")


# ===========================================================================
# Group K3: build_linux()
# ===========================================================================

class TestBuildLinux(unittest.TestCase):

    def test_raises_when_app_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_app_dir = Path(tmp) / "nonexistent" / "HLXGenerator"
            with patch.object(build_release, "APP_DIR", fake_app_dir):
                with self.assertRaises(FileNotFoundError):
                    build_release.build_linux("1.0.0", "amd64")

    def _make_linux_env(self, tmp_path: Path) -> tuple:
        """Create minimal fake app + packaging dirs; return (fake_app, packaging_dir)."""
        # Minimal fake PyInstaller output dir
        fake_app = tmp_path / "HLXGenerator"
        fake_app.mkdir()
        (fake_app / "HLXGenerator").write_text("#!/bin/sh\necho mock\n")

        # DEBIAN packaging template
        packaging_dir = tmp_path / "packaging" / "deb" / "DEBIAN"
        packaging_dir.mkdir(parents=True)
        (packaging_dir / "control").write_text(
            "Package: hlx-generator\n"
            "Version: ${VERSION}\n"
            "Architecture: ${ARCH}\n"
        )
        postinst = packaging_dir / "postinst"
        postinst.write_text("#!/bin/sh\n")
        postinst.chmod(0o755)

        return fake_app, packaging_dir

    def test_control_file_version_substituted(self):
        """build_linux() expands ${VERSION} and ${ARCH} in DEBIAN/control."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_app, _ = self._make_linux_env(tmp_path)

            with (
                patch.object(build_release, "APP_DIR", fake_app),
                patch.object(build_release, "DIST_DIR", tmp_path),
                patch.object(build_release, "PACKAGING", tmp_path / "packaging"),
                patch.object(build_release, "REPO_ROOT", tmp_path),
                patch("build_release.subprocess.run") as mock_run,
            ):
                mock_run.return_value = MagicMock(returncode=0)
                build_release.build_linux("2.3.4", "amd64")

            written_control = tmp_path / "deb_root" / "DEBIAN" / "control"
            self.assertTrue(written_control.exists(), "DEBIAN/control was not created")
            content = written_control.read_text()
            self.assertIn("2.3.4", content)
            self.assertIn("amd64", content)
            self.assertNotIn("${VERSION}", content)
            self.assertNotIn("${ARCH}", content)

    def test_calls_dpkg_deb(self):
        """build_linux() must invoke dpkg-deb --build."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_app, _ = self._make_linux_env(tmp_path)

            with (
                patch.object(build_release, "APP_DIR", fake_app),
                patch.object(build_release, "DIST_DIR", tmp_path),
                patch.object(build_release, "PACKAGING", tmp_path / "packaging"),
                patch.object(build_release, "REPO_ROOT", tmp_path),
                patch("build_release.subprocess.run") as mock_run,
            ):
                mock_run.return_value = MagicMock(returncode=0)
                build_release.build_linux("1.0.0", "amd64")

            calls = mock_run.call_args_list
            dpkg_calls = [c for c in calls if c[0][0][0] == "dpkg-deb"]
            self.assertTrue(len(dpkg_calls) >= 1, "dpkg-deb was not called")
            self.assertIn("--build", dpkg_calls[0][0][0])


# ===========================================================================
# Group K4: build_macos()
# ===========================================================================

class TestBuildMacos(unittest.TestCase):

    def test_raises_when_app_bundle_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_bundle = Path(tmp) / "nonexistent.app"
            with patch.object(build_release, "APP_BUNDLE", fake_bundle):
                with self.assertRaises(FileNotFoundError):
                    build_release.build_macos("1.0.0", "arm64")

    def test_calls_hdiutil_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bundle = tmp_path / "HLXGenerator.app"
            fake_bundle.mkdir()
            (fake_bundle / "MacOS").mkdir()

            with (
                patch.object(build_release, "APP_BUNDLE", fake_bundle),
                patch.object(build_release, "DIST_DIR", tmp_path),
                patch("build_release.subprocess.run") as mock_run,
            ):
                mock_run.return_value = MagicMock(returncode=0)
                build_release.build_macos("1.0.0", "arm64")

            calls = mock_run.call_args_list
            hdiutil_calls = [c for c in calls if c[0][0][0] == "hdiutil"]
            self.assertTrue(len(hdiutil_calls) >= 1, "hdiutil was not called")

    def test_dmg_filename_includes_version_and_arch(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bundle = tmp_path / "HLXGenerator.app"
            fake_bundle.mkdir()

            with (
                patch.object(build_release, "APP_BUNDLE", fake_bundle),
                patch.object(build_release, "DIST_DIR", tmp_path),
                patch("build_release.subprocess.run") as mock_run,
            ):
                mock_run.return_value = MagicMock(returncode=0)
                result = build_release.build_macos("1.2.3", "x86_64")

            self.assertIn("1.2.3", str(result))
            self.assertIn("x86_64", str(result))
            self.assertTrue(str(result).endswith(".dmg"))


# ===========================================================================
# Group K5: build_windows()
# ===========================================================================

class TestBuildWindows(unittest.TestCase):

    def test_raises_when_app_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_app_dir = Path(tmp) / "nonexistent"
            with patch.object(build_release, "APP_DIR", fake_app_dir):
                with self.assertRaises(FileNotFoundError):
                    build_release.build_windows("1.0.0", "x86_64")

    def test_raises_when_makensis_not_on_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_app = Path(tmp) / "HLXGenerator"
            fake_app.mkdir()
            with (
                patch.object(build_release, "APP_DIR", fake_app),
                patch("build_release.shutil.which", return_value=None),
            ):
                with self.assertRaises(RuntimeError):
                    build_release.build_windows("1.0.0", "x86_64")

    def test_nsi_template_substitution(self):
        """build_windows() replaces ${VERSION}, ${APP_DIR}, ${DIST_DIR} in the template."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_app = tmp_path / "HLXGenerator"
            fake_app.mkdir()

            packaging_dir = tmp_path / "packaging" / "nsis"
            packaging_dir.mkdir(parents=True)
            template = packaging_dir / "installer.nsi.template"
            template.write_text(
                "!define APP_VERSION \"${VERSION}\"\n"
                "OutFile \"${DIST_DIR}\\HLXGenerator-${VERSION}-Setup.exe\"\n"
                "File /r \"${APP_DIR}\\*.*\"\n"
            )

            with (
                patch.object(build_release, "APP_DIR", fake_app),
                patch.object(build_release, "DIST_DIR", tmp_path),
                patch.object(build_release, "PACKAGING", tmp_path / "packaging"),
                patch("build_release.shutil.which", return_value="/usr/bin/makensis"),
                patch("build_release.subprocess.run") as mock_run,
            ):
                mock_run.return_value = MagicMock(returncode=0)
                build_release.build_windows("3.1.4", "x86_64")

            nsi_file = tmp_path / "installer.nsi"
            self.assertTrue(nsi_file.exists())
            content = nsi_file.read_text()
            self.assertIn("3.1.4", content)
            self.assertNotIn("${VERSION}", content)
            self.assertNotIn("${APP_DIR}", content)
            self.assertNotIn("${DIST_DIR}", content)


if __name__ == "__main__":
    unittest.main()
