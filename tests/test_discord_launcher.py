"""Exercise the image Discord wrapper with the current RPM bootstrap contract."""

import json
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DiscordLauncherTests(unittest.TestCase):
    def test_bootstrap_arguments_and_failure(self):
        launcher = (ROOT / "build.sh").read_text().split(
            "cat > /usr/bin/discord <<'EOF'\n", 1
        )[1].split("\nEOF\n", 1)[0]

        with tempfile.TemporaryDirectory(prefix="discord launcher ") as directory:
            root = Path(directory)
            discord_root = root / "discord"
            app = discord_root / "app-1.0.170"
            app.mkdir(parents=True)
            bootstrap = root / "updater_bootstrap"
            host = app / "Discord"
            probe = root / "xdpyinfo"
            patcher = root / "patcher"
            probe.write_text("#!/bin/sh\nexit 0\n")
            patcher.write_text("#!/bin/sh\nexit 0\n")
            host.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$HOST_LOG"\n')
            bootstrap.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "args = sys.argv[1:]\n"
                "with open(os.environ['BOOTSTRAP_LOG'], 'w') as log:\n"
                "    json.dump(args, log)\n"
                "if args[:1] == ['--no-gui']:\n"
                "    args = args[1:]\n"
                "if len(args) != 3 or args[0].startswith('--'):\n"
                "    sys.exit(2)\n"
                "if os.environ.get('CANCEL'):\n"
                "    sys.exit(1)\n"
                "print('app-1.0.170')\n"
            )
            for path in (bootstrap, host, probe, patcher):
                path.chmod(0o755)
            launcher = launcher.replace(
                "bootstrap=/usr/share/$BOOTSTRAP_SUFFIX",
                'bootstrap="$XDG_CONFIG_HOME/updater_bootstrap"',
            ).replace(
                "VENCORD_PATCHER=/usr/bin/patch-discord-vencord-asar.mjs",
                'VENCORD_PATCHER="$XDG_CONFIG_HOME/patcher"',
            )
            wrapper = root / "wrapper"
            wrapper.write_text(launcher)
            bootstrap_log = root / "bootstrap.json"
            host_log = root / "host.log"
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ["PATH"],
                       XDG_CONFIG_HOME=directory, XDG_SESSION_TYPE="x11",
                       BOOTSTRAP_LOG=str(bootstrap_log), HOST_LOG=str(host_log))
            command = ["sh", str(wrapper), "discord://example"]
            defaults = [str(discord_root), "stable", "https://updates.discord.com/"]

            for terminal, cancel in ((False, False), (True, False), (False, True)):
                with self.subTest(terminal=terminal, cancel=cancel):
                    host_log.unlink(missing_ok=True)
                    master, slave = pty.openpty()
                    try:
                        result = subprocess.run(
                            command, env=env | ({"CANCEL": "1"} if cancel else {}),
                            stdout=slave if terminal else subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=10,
                        )
                    finally:
                        os.close(slave)
                        os.close(master)
                    expected = (["--no-gui"] if terminal else []) + defaults
                    self.assertEqual(json.loads(bootstrap_log.read_text()), expected)
                    if cancel:
                        self.assertEqual(result.returncode, 2)
                        self.assertFalse(host_log.exists())
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn("discord://example", host_log.read_text().splitlines())
