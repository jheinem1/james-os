import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]


class DesktopUpdaterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls'
        self.state = self.root / 'installed'
        self.state.write_text('26.908.70816')
        self.launcher = self.root / 'launcher'
        self.env = dict(os.environ, PROBE_ROOT=str(self.root), AVAILABLE='26.1002.52244',
                        UNLOCKED='none', SIGNATURE='signed', STAGED='1')
        probe = self.bin / 'probe'
        probe.write_text('''#!/usr/bin/python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ['PROBE_ROOT'])
cmd = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / 'calls').open('a') as out:
    out.write(json.dumps([cmd, args]) + '\\n')
if cmd == 'curl':
    pathlib.Path(args[args.index('-o') + 1]).write_text('package')
elif cmd == 'rpmkeys':
    if '--checksig' in args:
        kind = os.environ['SIGNATURE']
        if kind == 'bad': sys.exit(1)
        print('package: digests signatures OK' if kind == 'signed' else 'package: digests OK')
elif cmd == 'rpm':
    if '-Uvh' in args:
        if os.environ.get('INSTALL_FAIL'): sys.exit(7)
        (root / 'installed').write_text(os.environ['AVAILABLE'])
    elif '-qp' in args:
        print(os.environ.get('IDENTITY', 'chatgpt x86_64') if '%{NAME}' in args[args.index('--queryformat') + 1] else os.environ['AVAILABLE'], end='')
    else:
        print((root / 'installed').read_text(), end='')
elif cmd == 'rpm-ostree':
    if 'status' in args:
        print(json.dumps({'deployments': [{'booted': True, 'unlocked': os.environ['UNLOCKED']}, {'staged': os.environ['STAGED'] == '1'}]}))
elif cmd == 'systemctl':
    if os.environ.get('SERVICE_FAIL'): sys.exit(1)
''')
        probe.chmod(0o755)
        for name in ('curl', 'rpmkeys', 'rpm', 'rpm-ostree', 'systemctl'):
            (self.bin / name).symlink_to(probe)
        self.marker = self.root / 'ostree-booted'
        self.marker.touch()

    def invoke(self, name='update-chatgpt', **env):
        source = (REPO / 'system' / f'usr_bin__james-os-{name}').read_text()
        source = source.replace('export PATH=/usr/sbin:/usr/bin:/sbin:/bin',
                                f'export PATH={self.bin}:/usr/bin:/bin')
        source = source.replace('if [[ ${EUID} -ne 0 ]]; then', 'if false; then')
        source = source.replace('/run/james-os-update-chatgpt.lock', str(self.root / 'lock'))
        source = source.replace('/var/tmp/james-os-chatgpt.XXXXXXXX', str(self.root / 'work.XXXXXXXX'))
        source = source.replace('/run/ostree-booted', str(self.marker))
        source = source.replace('/usr/lib/chatgpt/codex-launcher', str(self.launcher))
        script = self.root / 'script'
        script.write_text(source)
        return subprocess.run(['/bin/bash', str(script)], env=dict(self.env, **env),
                              capture_output=True, text=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def mutations(self):
        return [(c, a) for c, a in self.calls()
                if (c == 'rpm' and '-Uvh' in a) or (c == 'rpm-ostree' and 'usroverlay' in a)]

    def test_upgrade_verifies_before_unlock_and_preserves_launcher(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state.read_text(), '26.1002.52244')
        calls = self.calls()
        checked = next(i for i, (c, a) in enumerate(calls) if c == 'rpmkeys' and '--checksig' in a)
        unlocked = next(i for i, (c, a) in enumerate(calls) if c == 'rpm-ostree' and 'usroverlay' in a)
        self.assertLess(checked, unlocked)
        self.assertIn('realpath -m', self.launcher.read_text())
        self.assertNotIn('restart', [a[0] for c, a in calls if c == 'systemctl'])
        self.assertEqual(list(self.root.glob('work.*')), [])

    def test_untrusted_or_unsigned_package_never_unlocks(self):
        for kind in ('bad', 'unsigned'):
            with self.subTest(kind=kind):
                self.log.unlink(missing_ok=True)
                self.assertNotEqual(self.invoke(SIGNATURE=kind).returncode, 0)
                self.assertEqual(self.mutations(), [])

    def test_wrong_package_identity_never_unlocks(self):
        self.assertNotEqual(self.invoke(IDENTITY='other x86_64').returncode, 0)
        self.assertEqual(self.mutations(), [])

    def test_current_or_older_download_never_unlocks(self):
        for available in ('26.908.70816', '26.908.40834'):
            with self.subTest(available=available):
                self.log.unlink(missing_ok=True)
                self.assertEqual(self.invoke(AVAILABLE=available).returncode, 0)
                self.assertEqual(self.mutations(), [])

    def test_existing_overlay_is_reused(self):
        self.assertEqual(self.invoke(UNLOCKED='development').returncode, 0)
        self.assertFalse(any(c == 'rpm-ostree' and 'usroverlay' in a for c, a in self.calls()))

    def test_unexpected_unlock_mode_is_rejected(self):
        self.assertNotEqual(self.invoke(UNLOCKED='hotfix').returncode, 0)
        self.assertEqual(self.mutations(), [])

    def test_rpm_failure_propagates(self):
        self.assertNotEqual(self.invoke(INSTALL_FAIL='1').returncode, 0)
        self.assertEqual(self.state.read_text(), '26.908.70816')
        self.assertFalse(self.launcher.exists())

    def test_staged_update_arms_and_checks_shutdown_services(self):
        result = self.invoke('check-staged-update')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['systemctl', ['start', 'ostree-finalize-staged.service']], self.calls())
        self.assertIn(['systemctl', ['is-active', '--quiet', 'ostree-finalize-staged-hold.service']], self.calls())
        self.assertFalse(any('finalize-staged' in a for c, a in self.calls() if c == 'rpm-ostree'))

    def test_shutdown_service_failure_propagates(self):
        self.assertNotEqual(self.invoke('check-staged-update', SERVICE_FAIL='1').returncode, 0)

    def test_no_staging_needs_no_shutdown_service(self):
        self.assertEqual(self.invoke('check-staged-update', STAGED='0').returncode, 0)
        self.assertFalse(any(c == 'systemctl' for c, a in self.calls()))

    def test_both_update_services_run_helpers(self):
        containerfile = (REPO / 'Containerfile').read_text()
        for service in ('uupd', 'uupd-manual'):
            name = f'usr_lib_systemd_system_{service}.service.d__30-desktop-update.conf'
            text = (REPO / 'system' / name).read_text()
            self.assertIn('ExecStartPost=/usr/bin/james-os-check-staged-update', text)
            self.assertIn('ExecStartPost=/usr/bin/james-os-update-chatgpt', text)
            self.assertIn(f'/usr/lib/systemd/system/{service}.service.d/30-desktop-update.conf', containerfile)


if __name__ == '__main__':
    unittest.main()
