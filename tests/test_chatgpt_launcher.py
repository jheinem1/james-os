import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ChatGPTLauncherTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        build = (Path(__file__).resolve().parents[1] / "build.sh").read_text()
        marker = "cat > /usr/lib/chatgpt/codex-launcher <<'EOF'\n"
        launcher_text = build.split(marker, 1)[1].split("\nEOF", 1)[0]
        app = self.root / "lib" / "chatgpt"
        app.mkdir(parents=True)
        launcher = app / "codex-launcher"
        launcher.write_text(launcher_text + "\n")
        launcher.chmod(0o755)
        executable = app / "ChatGPT"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "print(json.dumps([os.environ['CODEX_HOME'], sys.argv[1:]]))\n"
        )
        executable.chmod(0o755)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        self.command = bin_dir / "chatgpt"
        self.command.symlink_to("../lib/chatgpt/codex-launcher")
        self.real_home = self.root / "var" / "home" / "desktop user"
        self.real_home.mkdir(parents=True)
        (self.root / "home").symlink_to("var/home")
        self.linked_home = self.root / "home" / "desktop user"

    def launch(self, codex_home=None):
        env = dict(os.environ, HOME=str(self.linked_home))
        env.pop("CODEX_HOME", None)
        if codex_home is not None:
            env["CODEX_HOME"] = str(codex_home)
        args = ["--example", "value with spaces", "codex://example?x=1&y=2"]
        result = subprocess.run(
            [str(self.command), *args], env=env, capture_output=True,
            text=True, check=True,
        )
        home, forwarded = json.loads(result.stdout)
        self.assertEqual(forwarded, args)
        return Path(home)

    def test_default_home_with_symlink_ancestor(self):
        state = self.real_home / ".codex"
        state.mkdir()
        sentinel = state / "existing-state"
        sentinel.write_text("preserved")
        self.assertEqual(self.launch(), state)
        self.assertEqual(sentinel.read_text(), "preserved")

    def test_explicit_state_root_with_symlink(self):
        custom = self.real_home / "custom state"
        custom.mkdir()
        self.assertEqual(self.launch(self.linked_home / "custom state"), custom)

    def test_first_launch_before_state_directory_exists(self):
        state = self.real_home / ".codex"
        self.assertEqual(self.launch(), state)
        self.assertFalse(state.exists())

    def test_already_canonical_root(self):
        self.assertEqual(self.launch(self.real_home / ".codex"), self.real_home / ".codex")


if __name__ == "__main__":
    unittest.main()
