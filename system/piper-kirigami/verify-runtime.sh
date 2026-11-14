#!/usr/bin/env bash
# Read-only mock checks: never connect to ratbagd or apply device settings.
set -euo pipefail
out=${1:?Usage: verify-runtime.sh OUTPUT_DIRECTORY}
mkdir -p -- "$out"
ref=io.github.jheinem1.PiperKirigami/x86_64/development
run=(timeout --kill-after=5s 90s flatpak run --user --env=QT_QPA_PLATFORM=offscreen --env=QT_QUICK_BACKEND=software)
"${run[@]}" --command=python3 "$ref" /app/share/piper-kirigami/check-runtime.py > "$out/runtime-check.json"
python3 - "$out/runtime-check.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
assert r['qt'] == r['pyside'] == r['shiboken'], 'Mismatched Qt bindings'
PY
# Remove only our previous mock screenshot, so a stale PNG cannot pass this check.
"${run[@]}" --command=sh "$ref" -c 'rm -f "$XDG_CACHE_HOME/james-os-install-smoke.png"; exec piper-kirigami --mock --headless --screenshot "$XDG_CACHE_HOME/james-os-install-smoke.png"'
"${run[@]}" --command=sh "$ref" -c 'cat "$XDG_CACHE_HOME/james-os-install-smoke.png"' > "$out/installed-smoke.png"
python3 - "$out/installed-smoke.png" <<'PY'
from pathlib import Path
import struct, sys
image = Path(sys.argv[1]).read_bytes()
assert image[:8] == b'\x89PNG\r\n\x1a\n', 'Missing mock screenshot'
width, height = struct.unpack('>II', image[16:24])
assert width >= 960 and height >= 700, 'Invalid mock screenshot dimensions'
PY
