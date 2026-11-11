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
        (assets / 'verify-runtime.sh').write_text((self.repo / 'system/piper-kirigami/verify-runtime.sh').read_text())
        (assets / 'verify-repository.py').write_text((self.repo / 'system/piper-kirigami/verify-repository.py').read_text())
        self.pin = assets / 'repository.json'
        self.metadata = json.loads((self.repo / 'system/piper-kirigami/repository.json').read_text())
        self.metadata['gpg_fingerprint'] = 'A' * 40
        self.pin.write_text(json.dumps(self.metadata))
        (assets / 'piper-repository.gpg').write_text('A' * 40)
        stub = self.bin / 'mock-command'
        stub.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['PIPER_TEST_LOG'], 'a') as log:
    log.write(json.dumps([name, *args]) + '\\n')
if name == 'gpg':
    fingerprint = Path(args[-1]).read_text().strip()
    print('pub:-:4096:1:TEST:0:0::::::')
    print('fpr:::::::::' + fingerprint + ':')
elif name in ('qdbus', 'qdbus6'):
    print('[]')
elif name == 'flatpak':
    if args[0] == 'remote-add':
        repo = Path(os.environ['XDG_DATA_HOME']) / 'flatpak/repo'
        repo.mkdir(parents=True, exist_ok=True)
        (repo / 'config').write_text('[remote "piper-kirigami"]\\nurl=' + args[-1] + '\\ngpg-verify=true\\ngpg-verify-summary=true\\n')
        (repo / 'piper-kirigami.trustedkeys.gpg').write_text('A' * 40)
    elif args[0] == 'remote-info':
        if os.environ.get('PIPER_TEST_REMOTE_FAIL'): sys.exit(25)
        print('Signed remote fixture')
    elif args[0] == 'list':
        print('org.freedesktop.Piper/x86_64/master')
        print('unrelated.App/x86_64/stable')
    elif args[0] == 'build-bundle':
        Path(args[3]).write_bytes(b'old-piper-bundle')
    elif args[0] == 'install':
        if os.environ.get('PIPER_TEST_INSTALL_FAIL'): sys.exit(23)
        target = Path(os.environ['XDG_DATA_HOME']) / 'flatpak/exports/share/applications/io.github.jheinem1.PiperKirigami.desktop'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('[Desktop Entry]\\nName=Piper\\nExec=flatpak run io.github.jheinem1.PiperKirigami\\n')
    elif args[0] == 'run':
        if os.environ.get('PIPER_TEST_RUNTIME_FAIL'): sys.exit(24)
        if '--command=python3' in args:
            print(json.dumps(dict(qt='6.11.3', pyside=os.environ.get('PIPER_TEST_PYSIDE', '6.11.3'), shiboken='6.11.3')))
        elif args[-1].startswith('cat '):
            import struct
            sys.stdout.buffer.write(b'\\x89PNG\\r\\n\\x1a\\n' + b'\\0' * 8 + struct.pack('>II', int(os.environ.get('PIPER_TEST_WIDTH', '1200')), 820))
    elif args[0] == 'info':
        print(os.environ.get('PIPER_TEST_ORIGIN', 'piper-kirigami') if '--show-origin' in args else 'a' * 64)
    else:
        sys.exit('Unexpected Flatpak command: ' + repr(args))
''')
        stub.chmod(0o755)
        for name in ('gpg', 'flatpak', 'update-desktop-database', 'qdbus', 'qdbus6'):
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

    def test_unprovisioned_key_does_not_install_or_change_launcher(self):
        self.metadata['gpg_fingerprint'] = None
        self.pin.write_text(json.dumps(self.metadata))
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not been provisioned', result.stderr)
        self.assertEqual(self.launcher.read_text(), self.original)
        self.assertFalse(self.log.exists())

    def test_existing_remote_with_wrong_url_or_key_is_rejected(self):
        repo = self.data / 'flatpak/repo'
        repo.mkdir(parents=True)
        for url, key in [('https://example.com/', 'A'*40), (self.metadata['url'], 'B'*40)]:
            with self.subTest(url=url, key=key):
                (repo / 'config').write_text('[remote "piper-kirigami"]\nurl=' + url + '\ngpg-verify=true\n')
                (repo / 'piper-kirigami.trustedkeys.gpg').write_text(key)
                result = self.run_installer()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(c[0] == 'flatpak' for c in self.commands()))

    def test_remote_signature_failure_prevents_install(self):
        result = self.run_installer(PIPER_TEST_REMOTE_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[:2] == ['flatpak', 'install'] for c in self.commands()))

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
        self.assertEqual(commands[install_index][-2:], ['piper-kirigami', 'io.github.jheinem1.PiperKirigami/x86_64/development'])
        self.assertFalse(any('--delete-data' in c for c in commands))
        self.assertTrue((backup / 'runtime-verification/installed-smoke.png').is_file())
        self.assertTrue(any('--mock --headless' in ' '.join(c) for c in commands))
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertFalse(any('uninstall' in c or '--system' in c for c in commands))

    def test_install_failure_preserves_launcher_and_backup(self):
        result = self.run_installer(PIPER_TEST_INSTALL_FAIL='1')
        self.assertEqual(result.returncode, 23)
        self.assertEqual(self.launcher.read_text(), self.original)
        self.assertEqual(len(list((self.state / 'james-os/piper').glob('before-qt-*/*.flatpak'))), 1)

    def test_mismatched_qt_and_invalid_render_do_not_activate(self):
        for extra in (dict(PIPER_TEST_PYSIDE='6.11.2'), dict(PIPER_TEST_WIDTH='1')):
            with self.subTest(extra=extra):
                result = self.run_installer(**extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('runtime compatibility check failed', result.stderr)
                self.assertEqual(self.launcher.read_text(), self.original)

    def test_runtime_failure_keeps_launchers_and_backup(self):
        result = self.run_installer(PIPER_TEST_RUNTIME_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('runtime compatibility check failed', result.stderr)
        self.assertEqual(self.launcher.read_text(), self.original)
        self.assertEqual(len(list((self.state / 'james-os/piper').glob('before-qt-*/*.flatpak'))), 1)
        self.assertFalse(any(c[0] in ('qdbus', 'qdbus6') for c in self.commands()))

    def test_origin_mismatch_does_not_redirect_launcher(self):
        result = self.run_installer(PIPER_TEST_ORIGIN='untrusted-origin')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('origin mismatch', result.stderr)
        self.assertEqual(self.launcher.read_text(), self.original)


class ReleaseMetadataTest(unittest.TestCase):
    def test_repository_has_no_fixed_release_and_verified_publisher_key(self):
        root = Path(__file__).resolve().parents[1]
        release = json.loads((root / 'system/piper-kirigami/repository.json').read_text())
        self.assertEqual(release['app_id'], 'io.github.jheinem1.PiperKirigami')
        self.assertEqual(release['branch'], 'development')
        self.assertNotIn('tag', release)
        self.assertNotIn('flatpak_commit', release)
        self.assertEqual(release['gpg_fingerprint'], 'D5C33936E57050BC1B7A9210632AD854ECF1F599')
        assets = root / 'system/piper-kirigami'
        spec = importlib.util.spec_from_file_location('piper_repository', assets / 'verify-repository.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.primary_keys(assets / release['public_key']), [release['gpg_fingerprint']])
        verified, exists = module.validate(assets)
        self.assertEqual(verified, release)
        self.assertFalse(exists)
        containerfile = (root / 'Containerfile').read_text()
        self.assertIn('bash /usr/share/james-os/piper-kirigami/verify-image.sh', containerfile)
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
