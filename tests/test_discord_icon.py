"""Exercise the image icon installation against current and legacy RPM layouts."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DiscordIconTests(unittest.TestCase):
    def run_install(self, current=None, legacy=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            icon = root / "usr/share/icons/hicolor/256x256/apps/discord.png"
            old = root / "usr/share/discord/discord.png"
            for path, data in ((icon, current), (old, legacy)):
                if data is not None:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            build = (ROOT / "build.sh").read_text()
            snippet = build.split("# Current RPMs own", 1)[1].split("###############################################################################", 1)[0]
            snippet = "# Current RPMs own" + snippet
            result = subprocess.run(["bash", "-euc", snippet.replace("/usr/share/", str(root / "usr/share") + "/")], capture_output=True)
            return result.returncode, icon.read_bytes() if icon.is_file() else None, icon.is_symlink()

    def test_current_rpm_payload_is_preserved(self):
        self.assertEqual(self.run_install(b"current", b"legacy"), (0, b"current", False))

    def test_legacy_rpm_is_copied(self):
        self.assertEqual(self.run_install(None, b"legacy"), (0, b"legacy", False))

    def test_missing_icon_fails_build(self):
        self.assertNotEqual(self.run_install()[0], 0)
