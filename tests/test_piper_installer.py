"""Exercise the release installer with isolated Flatpak/download fixtures."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class PiperInstallerTest(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            self.skipTest('The user installer deliberately refuses root')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'desktop data with spaces'
        self.root.mkdir()
        self.repo = Path(__file__).resolve().parents[1]
        self.data = self.root / 'data'
        self.state = self.root / 'state'
        self.profile = self.root / 'profiles'
        self.profile.mkdir()
        (self.profile / 'saved.json').write_text('{"private": "preserve"}\n')
        self.launcher = self.data / 'applications/org.freedesktop.Piper.desktop'
        self.launcher.parent.mkdir(parents=True)
        self.original = '[Desktop Entry]\nName=My Piper\nExec=old-piper\n'
        self.launcher.write_text(self.original)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.script = self.root / 'james-os-install-piper'
        source = (self.repo / 'system/usr_bin__james-os-install-piper').read_text()
        old = 'profile_library="$HOME/.var/app/org.freedesktop.Piper/data/piper/profiles"'
        self.assertEqual(source.count(old), 1)
        self.script.write_text(source.replace(old, f'profile_library="{self.profile}"'))
        assets = self.root / 'piper-kirigami'
        assets.mkdir()
        (assets / 'migrate-plasma-launcher.py').write_text(
            (self.repo / 'system/piper-kirigami/migrate-plasma-launcher.py').read_text())
        self.pin = assets / 'release.json'
        self.metadata = dict(app_id='io.github.jheinem1.PiperKirigami', tag='v0.1.0',
                             sha256=hashlib.sha256(b'tested-bundle').hexdigest(),
                             flatpak_commit='a' * 64, source_commit='b' * 40)
        self.pin.write_text(json.dumps(self.metadata))
        stub = self.bin / 'mock-command'
        stub.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['PIPER_TEST_LOG'], 'a') as log:
    log.write(json.dumps([name, *args]) + '\\n')
if name == 'curl':
    Path(args[args.index('-o') + 1]).write_bytes(b'tested-bundle')
elif name in ('qdbus', 'qdbus6'):
    print('[]')
elif name == 'flatpak':
    if args[0] == 'list':
        print('org.freedesktop.Piper/x86_64/master')
        print('unrelated.App/x86_64/stable')
    elif args[0] == 'build-bundle':
        Path(args[3]).write_bytes(b'old-piper-bundle')
    elif args[0] == 'install':
        if os.environ.get('PIPER_TEST_INSTALL_FAIL'): sys.exit(23)
        target = Path(os.environ['XDG_DATA_HOME']) / 'flatpak/exports/share/applications/io.github.jheinem1.PiperKirigami.desktop'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('[Desktop Entry]\\nName=Piper\\nExec=flatpak run io.github.jheinem1.PiperKirigami\\n')
    elif args[0] == 'info':
        print(os.environ.get('PIPER_TEST_COMMIT', 'a' * 64))
    else:
        sys.exit('Unexpected Flatpak command: ' + repr(args))
''')
        stub.chmod(0o755)
        for name in ('curl', 'flatpak', 'update-desktop-database', 'qdbus', 'qdbus6'):
            (self.bin / name).symlink_to(stub)
        self.log = self.root / 'commands.jsonl'
        self.env = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}',
                        XDG_DATA_HOME=str(self.data), XDG_STATE_HOME=str(self.state),
                        XDG_CACHE_HOME=str(self.root / 'cache'), PIPER_TEST_LOG=str(self.log))

    def run_installer(self, **extra):
        return subprocess.run(['bash', str(self.script)], env=dict(self.env, **extra),
                              capture_output=True, text=True)

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_checksum_failure_does_not_install_or_change_launcher(self):
        self.metadata['sha256'] = 'f' * 64
        self.pin.write_text(json.dumps(self.metadata))
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('checksum mismatch', result.stderr)
        self.assertEqual(self.launcher.read_text(), self.original)
        self.assertFalse(any(command[0] == 'flatpak' for command in self.commands()))

    def test_success_backs_up_before_install_and_preserves_profile(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        backup, = (self.state / 'james-os/piper').glob('before-qt-*')
        self.assertEqual((backup / 'org.freedesktop.Piper-x86_64-master.flatpak').read_bytes(), b'old-piper-bundle')
        self.assertEqual((backup / 'applications/org.freedesktop.Piper.desktop').read_text(), self.original)
        self.assertEqual((backup / 'profile-library/saved.json').read_bytes(), (self.profile / 'saved.json').read_bytes())
        self.assertIn('X-JamesOS-Piper-redirect=true', self.launcher.read_text())
        self.assertIn('NoDisplay=true', self.launcher.read_text())
        commands = self.commands()
        backup_index = next(i for i, c in enumerate(commands) if c[:2] == ['flatpak', 'build-bundle'])
        install_index = next(i for i, c in enumerate(commands) if c[:2] == ['flatpak', 'install'])
        self.assertLess(backup_index, install_index)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertFalse(any('uninstall' in c or '--system' in c for c in commands))

    def test_install_failure_preserves_launcher_and_backup(self):
        result = self.run_installer(PIPER_TEST_INSTALL_FAIL='1')
        self.assertEqual(result.returncode, 23)
        self.assertEqual(self.launcher.read_text(), self.original)
        self.assertEqual(len(list((self.state / 'james-os/piper').glob('before-qt-*/*.flatpak'))), 1)

    def test_commit_mismatch_does_not_redirect_launcher(self):
        result = self.run_installer(PIPER_TEST_COMMIT='c' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('commit mismatch', result.stderr)
        self.assertEqual(self.launcher.read_text(), self.original)


class ReleaseMetadataTest(unittest.TestCase):
    def test_release_is_pinned_to_real_commits_and_bundle_digest(self):
        root = Path(__file__).resolve().parents[1]
        release = json.loads((root / 'system/piper-kirigami/release.json').read_text())
        self.assertEqual(release['app_id'], 'io.github.jheinem1.PiperKirigami')
        self.assertRegex(release['tag'], r'^v[0-9][0-9A-Za-z._-]*$')
        for key, length in [('source_commit', 40), ('flatpak_commit', 64), ('sha256', 64)]:
            self.assertRegex(release[key], rf'^[0-9a-f]{{{length}}}$')
            self.assertNotEqual(release[key], '0' * length, f'{key} is still a placeholder')
        containerfile = (root / 'Containerfile').read_text()
        self.assertIn('COPY system/piper-kirigami /usr/share/james-os/piper-kirigami', containerfile)
        self.assertIn('system/usr_bin__james-os-install-piper-gtk /usr/bin/james-os-install-piper-gtk', containerfile)


class PlasmaLauncherTest(unittest.TestCase):
    def test_only_exact_piper_pins_change_and_order_is_preserved(self):
        path = Path(__file__).resolve().parents[1] / 'system/piper-kirigami/migrate-plasma-launcher.py'
        spec = importlib.util.spec_from_file_location('piper_launcher_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = Path('/tmp/desktop data')
        old = (data / 'flatpak/exports/share/applications/org.freedesktop.Piper.desktop').as_uri()
        pins = f'applications:unrelated.desktop,{old},applications:org.freedesktop.Piper.desktop,file:///tmp/other/Piper.desktop'
        panels = [dict(panel=4, widget=8, launchers=pins), dict(panel=4, widget=9, launchers='applications:unrelated.desktop')]
        changes = module.plan_changes(panels, data)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['before'], pins)
        self.assertEqual(changes[0]['after'], 'applications:unrelated.desktop,applications:io.github.jheinem1.PiperKirigami.desktop,applications:io.github.jheinem1.PiperKirigami.desktop,file:///tmp/other/Piper.desktop')
        self.assertEqual(panels[0]['launchers'], pins)


if __name__ == '__main__':
    unittest.main()
