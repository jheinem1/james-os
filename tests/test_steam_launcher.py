import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "system/usr_libexec__james-os-steam"


class SteamLauncherTest(unittest.TestCase):
    def setUp(self):
        self.launcher = runpy.run_path(str(LAUNCHER))
        self.env = patch.dict(os.environ, {
            "XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "KDE",
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def detect(self, outputs, clients_scale="true", args=()):
        results = [
            subprocess.CompletedProcess([], 0, clients_scale),
            subprocess.CompletedProcess([], 0, json.dumps({"outputs": outputs})),
        ]
        with patch("subprocess.run", side_effect=results):
            return self.launcher["desktop_scale"](args)

    @staticmethod
    def output(scale, enabled=True, connected=True):
        return {"scale": scale, "enabled": enabled, "connected": connected}

    def test_krunner_launch_on_dual_4k_displays(self):
        self.assertEqual(self.detect([self.output(2), self.output(2)], args=["-applaunch", "427520"]), "2")

    def test_fractional_and_mixed_scales_match_kwin(self):
        self.assertEqual(self.detect([self.output(1), self.output(1.5)]), "1.5")

    def test_disabled_and_disconnected_displays_are_ignored(self):
        self.assertIsNone(self.detect([
            self.output(1), self.output(2, enabled=False), self.output(3, connected=False),
        ]))

    def test_no_displays_does_not_override(self):
        self.assertIsNone(self.detect([]))

    def test_compositor_scaling_does_not_double_scale(self):
        self.assertIsNone(self.detect([self.output(2)], clients_scale="false"))

    def test_explicit_environment_override_skips_detection(self):
        os.environ["STEAM_FORCE_DESKTOPUI_SCALING"] = "1.25"
        with patch("subprocess.run") as run:
            self.assertIsNone(self.launcher["desktop_scale"]([]))
            run.assert_not_called()

    def test_explicit_arguments_and_game_mode_skip_detection(self):
        for args in [
            ["-forcedesktopscaling", "1.25"], ["-forcedesktopscaling=1.25"],
            ["-steamdeck"], ["-gamepadui"], ["-tenfoot"],
        ]:
            with self.subTest(args=args), patch("subprocess.run") as run:
                self.assertIsNone(self.launcher["desktop_scale"](args))
                run.assert_not_called()

    def test_other_sessions_skip_detection(self):
        for env in [
            {"XDG_SESSION_TYPE": "x11"}, {"XDG_CURRENT_DESKTOP": "GNOME"},
            {"XDG_CURRENT_DESKTOP": "gamescope"}, {"SteamDeck": "1"},
        ]:
            with self.subTest(env=env), patch.dict(os.environ, env), patch("subprocess.run") as run:
                self.assertIsNone(self.launcher["desktop_scale"]([]))
                run.assert_not_called()

    def test_missing_failed_and_timed_out_tools_allow_launch(self):
        for error in [FileNotFoundError(), subprocess.CalledProcessError(1, "kscreen-doctor"),
                      subprocess.TimeoutExpired("kscreen-doctor", 2)]:
            with self.subTest(error=error), patch("subprocess.run", side_effect=error):
                self.assertIsNone(self.launcher["desktop_scale"]([]))

    def test_malformed_display_data_allows_launch(self):
        for text in ["bad json", "{}", '{"outputs": null}', '{"outputs": [null]}',
                     '{"outputs": [{"enabled": true, "connected": true}]}']:
            with self.subTest(text=text), patch("subprocess.run", side_effect=[
                subprocess.CompletedProcess([], 0, "true"),
                subprocess.CompletedProcess([], 0, text),
            ]):
                self.assertIsNone(self.launcher["desktop_scale"]([]))
        for scale in [0, -1, "invalid", float("nan"), float("inf")]:
            with self.subTest(scale=scale):
                self.assertIsNone(self.detect([self.output(scale)]))

    def test_command_symlink_executes_bootstrap_with_scale_args_and_exit_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vendor = root / "lib/steam/bin_steam.sh"
            vendor.parent.mkdir(parents=True)
            vendor.write_text(
                f"#!{sys.executable}\nimport json, os, sys\n"
                "print(json.dumps([os.environ.get('STEAM_FORCE_DESKTOPUI_SCALING'), sys.argv[1:]]))\n"
                "sys.exit(13)\n"
            )
            vendor.chmod(0o755)
            helper = root / "libexec/james-os-steam"
            helper.parent.mkdir()
            helper.write_text(LAUNCHER.read_text().replace(
                'STEAM_BOOTSTRAP = "/usr/lib/steam/bin_steam.sh"',
                f"STEAM_BOOTSTRAP = {str(vendor)!r}",
            ))
            helper.chmod(0o755)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            command = bin_dir / "steam"
            command.symlink_to("../lib/steam/bin_steam.sh")
            before = vendor.read_bytes()
            # Exercise the same replacement as the image build, without modifying /usr.
            build = (ROOT / "build.sh").read_text()
            install = build.split("# Replace only the command symlink;", 1)[1]
            install = install.split("###############################################################################", 1)[0]
            subprocess.run(["bash", "-euc", install.split("\n", 1)[1].replace("/usr/", f"{root}/")], check=True)
            for name, value in [
                ("kreadconfig6", "true"),
                ("kscreen-doctor", json.dumps({"outputs": [self.output(2)]})),
            ]:
                tool = bin_dir / name
                tool.write_text(f"#!/bin/sh\nprintf '%s\\n' '{value}'\n")
                tool.chmod(0o755)
            args = ["-applaunch", "427520", "argument with spaces", "steam://url?a=1&b=2"]
            env = dict(os.environ, PATH=f"{bin_dir}:/usr/bin:/bin")
            result = subprocess.run([str(command), *args], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 13, result.stderr)
            self.assertEqual(json.loads(result.stdout), ["2", args])
            self.assertEqual(vendor.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
