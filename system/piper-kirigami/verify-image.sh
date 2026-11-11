#!/usr/bin/env bash
# Validate shipped integration, not a user Flatpak runtime or physical device.
set -euo pipefail
assets=/usr/share/james-os/piper-kirigami
for command_name in flatpak python3 flock timeout ratbagd rpm gpg; do
  command -v "$command_name" >/dev/null
done
for script in /usr/bin/james-os-install-piper "$assets/verify-runtime.sh"; do
  bash -n "$script"
done
/usr/bin/james-os-install-piper --version
python3 - "$assets/repository.json" <<'PY'
import json, subprocess, sys
release = json.load(open(sys.argv[1]))
assert release['app_id'] == 'io.github.jheinem1.PiperKirigami'
version = subprocess.check_output(['rpm', '-q', '--qf', '%{VERSION}', 'libratbag-ratbagd'], text=True).strip()
parts = tuple(int(p) for p in version.split('.')[:2])
assert parts >= (0, 18), f'ratbagd 0.18+ required, found {version}'
PY
printf 'Piper image integration verified; user runtime check remains mandatory at install.\n'
