"""Ensure reconnect monitoring never mutates the desktop."""

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


path = Path(__file__).resolve().parents[1] / "system/usr_bin__kvm-display-recover"
loader = SourceFileLoader("kvm_recover", str(path))
spec = spec_from_loader(loader.name, loader)
recover = module_from_spec(spec)
loader.exec_module(recover)


class ReconnectTests(unittest.TestCase):
    def simulate(self, samples, kde_samples):
        class EndSimulation(Exception):
            pass

        def sample():
            try:
                return next(iterator)
            except StopIteration as exc:
                raise EndSimulation from exc

        iterator = iter(samples)
        with patch.object(recover, "drm_outputs", side_effect=sample), \
                patch.object(recover, "read_state", side_effect=kde_samples) as query, \
                patch.object(recover.time, "sleep"), patch.object(recover, "log") as logs, \
                patch.object(subprocess, "run") as apply, \
                patch.dict(recover.os.environ, {"KVM_DISPLAY_SETTLE_ATTEMPTS": "2"}):
            with self.assertRaises(EndSimulation):
                recover.run()
            apply.assert_not_called()
        return query, logs

    def test_explicit_disable_immediately_before_unplug_is_not_reenabled(self):
        both = {"acer": "DP-3", "gigabyte": "DP-2"}
        peer = {"gigabyte": "DP-2"}
        # The explicit disable occurs between two DRM polls. The only KDE
        # observations occur after reconnect and both see it still disabled.
        disabled = {"acer": {"enabled": False}, "gigabyte": {"enabled": True}}
        query, logs = self.simulate([both, peer, both, both, both], [disabled, disabled])
        self.assertEqual(query.call_count, 2)
        self.assertIn("left unchanged", logs.call_args.args[0])

    def test_normal_reconnect_already_enabled_is_left_alone(self):
        both = {"acer": "DP-3", "gigabyte": "DP-2"}
        peer = {"gigabyte": "DP-2"}
        switched = {"acer": "DP-2", "gigabyte": "DP-3"}
        enabled = {"acer": {"enabled": True}, "gigabyte": {"enabled": True}}
        query, logs = self.simulate([both, peer, switched, switched], [enabled])
        query.assert_called_once_with(switched)
        self.assertIn("DP-2 reconnected and is enabled", logs.call_args.args[0])

    def test_multiple_disconnects_are_ambiguous(self):
        both = {"acer": "DP-3", "gigabyte": "DP-2"}
        peer = {"gigabyte": "DP-2"}
        query, _ = self.simulate([both, {}, peer, both], [])
        query.assert_not_called()

    def test_replaced_monitor_is_not_matched_as_same(self):
        both = {"acer": "DP-3", "gigabyte": "DP-2"}
        peer = {"gigabyte": "DP-2"}
        replacement = {"other": "DP-3", "gigabyte": "DP-2"}
        query, _ = self.simulate([both, peer, replacement], [])
        query.assert_not_called()


class DrmIdentityTests(unittest.TestCase):
    def test_identical_edids_are_ambiguous(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("card1-DP-2", "card1-DP-3"):
                connector = Path(root) / name
                connector.mkdir()
                (connector / "status").write_text("connected\n")
                (connector / "edid").write_bytes(bytes.fromhex("00ffffffffffff00") + bytes(120))
            self.assertIsNone(recover.drm_outputs(Path(root)))

    def test_no_edid_does_not_guess_identity(self):
        with tempfile.TemporaryDirectory() as root:
            connector = Path(root) / "card1-DP-2"
            connector.mkdir()
            (connector / "status").write_text("connected\n")
            (connector / "edid").write_bytes(b"")
            self.assertIsNone(recover.drm_outputs(Path(root)))


if __name__ == "__main__":
    unittest.main()
