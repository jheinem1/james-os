#!/usr/bin/env bash
# Verify a corrupted download cannot reach uv installation or create a backup.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "$0")/.." && pwd)
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT
mkdir -p "$work_dir/bin"
cat > "$work_dir/bin/curl" <<'EOF'
#!/usr/bin/env bash
while (( $# )); do
  if [[ "$1" == -o ]]; then printf 'corrupt wheel\n' > "$2"; exit 0; fi
  shift
done
exit 1
EOF
cat > "$work_dir/bin/uv" <<'EOF'
#!/usr/bin/env bash
printf 'unexpected uv invocation\n' >> "$INSTALLER_TEST_MARKER"
exit 91
EOF
chmod +x "$work_dir/bin/"*
export INSTALLER_TEST_MARKER="$work_dir/uv-called"
if PATH="$work_dir/bin:$PATH" XDG_STATE_HOME="$work_dir/state" \
    bash "$repo_root/system/usr_bin__james-os-install-kwin-mcp"; then
  echo 'Corrupt download was accepted' >&2
  exit 1
fi
test ! -e "$INSTALLER_TEST_MARKER"
test -d "$work_dir/state/james-os/kwin-mcp"
echo 'PASS: checksum mismatch rejected before backup/install'
