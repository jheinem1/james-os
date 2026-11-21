"""Exercise the image's KVM recovery decision without touching a real display."""

import copy
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


def output(name, output_id, x, priority, hdr):
    return {
        "connected": True, "enabled": True, "name": name, "id": output_id,
        "pos": {"x": x, "y": 0}, "scale": 2, "rotation": 1, "priority": priority,
        "hdr": hdr, "wcg": hdr, "sdr-brightness": 700, "brightness": 0.9,
        "currentModeId": "1", "modes": [
            {"id": "1", "name": "3840x2160", "refreshRate": 159.99},
        ],
        "replicationSource": 0, "clones": [],
    }


class ReconnectTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            "acer": output("DP-3", 1, 0, 1, True),
            "gigabyte": output("DP-2", 2, 1920, 2, False),
        }
        self.after = copy.deepcopy(self.before)
        self.after["acer"].update(enabled=False, priority=0)
        self.after["gigabyte"]["priority"] = 1

    def test_already_enabled_is_left_alone(self):
        self.assertEqual(recover.recovery_commands("acer", self.before, self.before), [])

    def test_previously_disabled_target_is_left_alone(self):
        self.before["acer"]["enabled"] = False
        self.assertEqual(recover.recovery_commands("acer", self.before, self.after), [])

    def test_disabled_target_restored_once_with_previous_priorities(self):
        self.assertEqual(recover.recovery_commands("acer", self.before, self.after), [
            "output.1.enable", "output.1.priority.1", "output.2.priority.2",
        ])

    def test_physical_identity_survives_connector_and_mode_id_changes(self):
        self.after["acer"].update(name="DP-2", id=4, currentModeId="13")
        self.after["acer"]["modes"][0]["id"] = "13"
        self.after["gigabyte"].update(name="DP-3", id=3)
        self.assertEqual(recover.recovery_commands("acer", self.before, self.after), [
            "output.4.enable", "output.4.priority.1", "output.3.priority.2",
        ])

    def test_never_overwrites_settings(self):
        for key, value in {
            "pos": {"x": 1920, "y": 0}, "scale": 1, "hdr": False, "wcg": False,
            "brightness": 1, "sdr-brightness": 500, "rotation": 2,
            "iccProfilePath": "/new-profile", "currentModeId": "missing",
        }.items():
            with self.subTest(key=key):
                after = copy.deepcopy(self.after)
                after["acer"][key] = value
                self.assertEqual(recover.recovery_commands("acer", self.before, after), [])

    def test_never_guesses_replacement_topology(self):
        self.after["replacement"] = self.after.pop("acer")
        self.assertEqual(recover.recovery_commands("acer", self.before, self.after), [])

    def test_never_guesses_mirrored_topology(self):
        self.before["gigabyte"]["replicationSource"] = 1
        self.assertEqual(recover.recovery_commands("acer", self.before, self.after), [])

    def run_watcher(self, drm_samples, states):
        """Stop the infinite service after its provided sequence."""
        class EndSimulation(Exception):
            pass

        def sample():
            try:
                return next(samples)
            except StopIteration as exc:
                raise EndSimulation from exc

        samples = iter(drm_samples)
        with patch.object(recover, "drm_outputs", side_effect=sample),                 patch.object(recover, "read_state", side_effect=states),                 patch.object(recover.time, "sleep"), patch.object(recover, "log"),                 patch.object(subprocess, "run") as apply:
            with self.assertRaises(EndSimulation):
                recover.run()
        return apply

    def test_single_replug_triggers_only_one_atomic_apply(self):
        both = {"acer": "DP-3", "gigabyte": "DP-2"}
        peer = {"gigabyte": "DP-2"}
        switched = {"acer": "DP-2", "gigabyte": "DP-3"}
        self.after["acer"].update(id=2, name="DP-2")
        self.after["gigabyte"].update(id=1, name="DP-3")
        apply = self.run_watcher([both, both, peer, switched, switched, switched], [self.before, self.after])
        apply.assert_called_once_with(["kscreen-doctor", "output.2.enable",
                                       "output.2.priority.1", "output.1.priority.2"], check=True, timeout=8)

    def test_replug_already_enabled_does_not_apply(self):
        both = {"acer": "DP-3", "gigabyte": "DP-2"}
        peer = {"gigabyte": "DP-2"}
        self.run_watcher([both, both, peer, both, both], [self.before, self.before]).assert_not_called()

    def test_multiple_reconnects_are_ambiguous(self):
        both = {"acer": "DP-3", "gigabyte": "DP-2"}
        peer = {"gigabyte": "DP-2"}
        self.run_watcher([both, both, {}, peer, both], [self.before, self.after]).assert_not_called()


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
