import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class HomebrewUpdaterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = Path(__file__).resolve().parents[1]
        # Model both Bazzite's /home symlink and Homebrew's bin/brew symlink.
        self.prefix = self.root / "var" / "home" / "linuxbrew" / ".linuxbrew"
        (self.prefix / "Homebrew" / "bin").mkdir(parents=True)
        (self.prefix / "bin").mkdir()
        (self.prefix / "Cellar").mkdir()
        (self.root / "home").symlink_to("var/home")
        self.entrypoint = self.root / "home" / "linuxbrew" / ".linuxbrew" / "bin" / "brew"
        real_brew = self.prefix / "Homebrew" / "bin" / "brew"
        real_brew.write_text(
            "#!/bin/bash\n"
            "prefix=$(cd -- \"$(dirname -- \"$0\")/..\" && pwd -P)\n"
            "python3 - \"$prefix\" \"$@\" <<'PY'\n"
            "import json, os, pathlib, sys\n"
            "print(json.dumps({'prefix': sys.argv[1], 'args': sys.argv[2:], "
            "'cellar_exists': (pathlib.Path(sys.argv[1]) / 'Cellar').is_dir()}))\n"
            "sys.exit(int(os.environ.get('PROBE_EXIT_CODE', '0')))\n"
            "PY\n"
        )
        real_brew.chmod(0o755)
        self.entrypoint.symlink_to("../Homebrew/bin/brew")
        wrapper_text = (self.repo / "system/usr_bin__james-os-brew").read_text()
        self.assertEqual(wrapper_text.count("/home/linuxbrew/.linuxbrew/bin/brew"), 1)
        self.wrapper = self.root / "usr" / "bin" / "james-os-brew"
        self.wrapper.parent.mkdir(parents=True)
        self.wrapper.write_text(wrapper_text.replace(
            "/home/linuxbrew/.linuxbrew/bin/brew", str(self.entrypoint)
        ))
        self.wrapper.chmod(0o755)

    def invoke_resolved(self, executable, *args, **env):
        # pkexec canonicalizes only the program, preserving its arguments.
        result = subprocess.run(
            [str(executable.resolve()), *args],
            env=dict(os.environ, **env), text=True, capture_output=True,
        )
        return result, json.loads(result.stdout)

    def test_direct_brew_reproduces_empty_cellar(self):
        result, data = self.invoke_resolved(self.entrypoint, "upgrade")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(data["prefix"], str(self.prefix / "Homebrew"))
        self.assertFalse(data["cellar_exists"])

    def test_wrapper_sees_installed_cellar_for_update_and_upgrade(self):
        for command in ("update", "upgrade"):
            with self.subTest(command=command):
                result, data = self.invoke_resolved(self.wrapper, command)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(data["prefix"], str(self.prefix))
                self.assertTrue(data["cellar_exists"])
                self.assertEqual(data["args"], [command])

    def test_wrapper_preserves_arguments_and_errors(self):
        args = ["upgrade", "--dry-run", "name with spaces", "literal;$value"]
        result, data = self.invoke_resolved(self.wrapper, *args, PROBE_EXIT_CODE="23")
        self.assertEqual(result.returncode, 23)
        self.assertEqual(data["args"], args)

    def test_both_services_select_regular_wrapper_without_replacing_execstart(self):
        containerfile = (self.repo / "Containerfile").read_text()
        for service in ("uupd", "uupd-manual"):
            filename = f"usr_lib_systemd_system_{service}.service.d__20-homebrew-path.conf"
            self.assertEqual(
                (self.repo / "system" / filename).read_text(),
                "[Service]\nEnvironment=HOMEBREW_PATH=/usr/bin/james-os-brew\n",
            )
            self.assertIn(
                f"COPY --chmod=0644 system/{filename} "
                f"/usr/lib/systemd/system/{service}.service.d/20-homebrew-path.conf",
                containerfile,
            )
        self.assertIn(
            "COPY --chmod=0755 system/usr_bin__james-os-brew /usr/bin/james-os-brew",
            containerfile,
        )


if __name__ == "__main__":
    unittest.main()
