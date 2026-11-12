"""Exercise bounded image verification with inert fake executables."""
import pathlib
import subprocess
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'system/bazzite-updater-kde/verify'


class VerifyTests(unittest.TestCase):
    def check_case(self, app, ldd='exit 0', expected=False, library=False, suffix=None):
        with tempfile.TemporaryDirectory(suffix=suffix) as tmp:
            root = pathlib.Path(tmp)
            (root / 'bin').mkdir()
            if library:
                (root / 'lib/qml').mkdir(parents=True)
                (root / 'lib/qml/plugin.so').write_text('inert test library')
            (root / 'source-commit').write_text('test-source\n')
            for name, body in [('app', app), ('ldd', ldd)]:
                file = root / 'bin' / name
                file.write_text('#!/usr/bin/bash\n' + body + '\n')
                file.chmod(0o755)
            # Shorten test timeouts before inserting paths: random directory names
            # can contain duration strings such as '3s', which must remain intact.
            script = SOURCE.read_text()
            script = script.replace('20s', '0.2s').replace('8s', '0.2s').replace('3s', '0.2s')
            script = script.replace('/usr/lib/bazzite-updater-kde', tmp)
            script = script.replace('/usr/bin/bazzite-updater', str(root / 'bin/app'))
            script = script.replace('/tmp/updater-', tmp + '/updater-')
            script = script.replace('ldd -r', str(root / 'bin/ldd') + ' -r')
            result = subprocess.run(['bash', '-c', script], capture_output=True, text=True, timeout=3)
            self.assertEqual(result.returncode == 0, expected, result.stdout + result.stderr)
            self.assertEqual((root / 'runtime-verified').exists(), expected)

    def test_success(self):
        self.check_case('exec sleep 10', expected=True)

    def test_timeout_strings_in_temporary_paths_are_preserved(self):
        for suffix in ('3s', '8s', '20s'):
            with self.subTest(suffix=suffix):
                self.check_case('exec sleep 10', expected=True, suffix=suffix)

    def test_sdl_signal_handler_is_disabled(self):
        self.check_case('[[ ${SDL_NO_SIGNAL_HANDLERS:-} == 1 ]] || trap "" TERM; exec sleep 10', expected=True)

    def test_early_exit(self):
        self.check_case('exit 1')

    def test_qml_error(self):
        self.check_case('echo "Type Main unavailable"; exec sleep 10')

    def test_abi_error(self):
        self.check_case('exec sleep 10', 'echo "libmissing.so not found"')

    def test_private_qml_library_abi_error(self):
        self.check_case('exec sleep 10', '[[ "$2" != *.so ]] || echo "undefined symbol: missing"', library=True)

    def test_abi_hang(self):
        self.check_case('exec sleep 10', "trap '' TERM; exec sleep 10")

    def test_startup_ignores_term(self):
        self.check_case("trap '' TERM; exec sleep 10")
