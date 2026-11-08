"""Guard the image-owned Vencord bundle and its custom plugin overlay."""
from pathlib import Path
import os
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VencordBundleTests(unittest.TestCase):
    def test_pin_and_complete_overlay(self):
        build = (ROOT / "build.sh").read_text()
        self.assertRegex(build, r'VENCORD_REF="[0-9a-f]{40}"')
        self.assertIn('VENCORD_TAG="v1.15.16"', build)
        self.assertIn('cp -a /tmp/vencord-overlay/src/. /tmp/Vencord/src/', build)
        self.assertIn('/usr/share/vencord/james-os-version.txt', build)
        for path in (
            "plugins/kdeIdleSync.discordDesktop/index.ts",
            "plugins/kdeIdleSync.discordDesktop/native.ts",
            "plugins/codexWindowBridge.discordDesktop/index.ts",
            "plugins/codexWindowBridge.discordDesktop/native.ts",
            "userplugins/userTimeZones/index.tsx",
            "userplugins/userTimeZones/styles.css",
        ):
            self.assertTrue((ROOT / "vencord-overlay/src" / path).is_file(), path)

    def test_bridge_remains_opt_in_and_protected(self):
        plugin = ROOT / "vencord-overlay/src/plugins/codexWindowBridge.discordDesktop"
        self.assertIn('enabledByDefault: false', (plugin / "index.ts").read_text())
        native = (plugin / "native.ts").read_text()
        self.assertIn('chmodSync(socketPath, 0o600)', native)
        self.assertIn('allowMutation', native)

    def test_system_patcher_default(self):
        helper = (ROOT / "system/usr_bin__patch-discord-vencord-asar.mjs").read_text()
        self.assertIn('process.argv[3] || "/usr/share/vencord/patcher.js"', helper)

    def test_session_gate(self):
        build = (ROOT / "build.sh").read_text()
        gate = build.split("# Wait for Plasma/Xwayland", 1)[1].split("CHANNEL=stable", 1)[0]
        gate = "# Wait for Plasma/Xwayland" + gate
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, body in {"xdpyinfo": 'exit "$PROBE_STATUS"', "sleep": "exit 0"}.items():
                path = root / name
                path.write_text("#!/bin/sh\n" + body + "\n")
                path.chmod(0o755)
            env = dict(os.environ, PATH=directory + ":" + os.environ["PATH"],
                       XDG_RUNTIME_DIR=directory, WAYLAND_DISPLAY="test-wayland",
                       XDG_SESSION_TYPE="wayland", PROBE_STATUS="0")
            with socket.socket(socket.AF_UNIX) as compositor:
                compositor.bind(str(root / "test-wayland"))
                result = subprocess.run(["sh", "-c", gate], env=env, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                env["PROBE_STATUS"] = "1"
                result = subprocess.run(["sh", "-c", gate], env=env, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 3)
            (root / "test-wayland").unlink()
            env["PROBE_STATUS"] = "0"
            result = subprocess.run(["sh", "-c", gate], env=env, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 3)
            env["XDG_SESSION_TYPE"] = "x11"
            result = subprocess.run(["sh", "-c", gate], env=env, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
