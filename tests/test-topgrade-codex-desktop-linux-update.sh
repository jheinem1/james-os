#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPDATE_SCRIPT="${REPO_ROOT}/system/usr_local_bin__topgrade-codex-desktop-linux-update"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

fail_test() {
    echo "test-topgrade-codex-desktop-linux-update: $*" >&2
    exit 1
}

initialize_repo() {
    local repo_dir="$1"
    local origin_url="$2"

    mkdir -p "$repo_dir"
    git init -q --initial-branch=main "$repo_dir"
    git -C "$repo_dir" config user.name "Codex Test"
    git -C "$repo_dir" config user.email "codex-test@example.invalid"
    printf 'initial\n' > "$repo_dir/tracked.txt"
    mkdir -p "$repo_dir/contrib/user-local-install"
    printf '#!/usr/bin/env bash\n' > "$repo_dir/contrib/user-local-install/install-user-local.sh"
    chmod +x "$repo_dir/contrib/user-local-install/install-user-local.sh"
    git -C "$repo_dir" add tracked.txt contrib/user-local-install/install-user-local.sh
    git -C "$repo_dir" commit -q -m "Initial test commit"
    git -C "$repo_dir" remote add origin "$origin_url"
    git -C "$repo_dir" update-ref refs/remotes/origin/main HEAD
}

export HOME="${TEST_ROOT}/home"
export XDG_DATA_HOME="${HOME}/.local/share"
export XDG_STATE_HOME="${HOME}/.local/state"
unset CODEX_DESKTOP_LINUX_REPO
mkdir -p "$HOME"

# shellcheck disable=SC1090
source "$UPDATE_SCRIPT"

legacy_repo="${HOME}/codex-desktop-linux"
initialize_repo "$legacy_repo" "https://example.invalid/user/codex-desktop-linux.git"
printf 'dirty user work\n' >> "$legacy_repo/tracked.txt"
legacy_head_before="$(git -C "$legacy_repo" rev-parse HEAD)"
legacy_status_before="$(git -C "$legacy_repo" status --porcelain --untracked-files=normal)"

production_canonical_url="$CANONICAL_REPO_URL"
canonical_test_repo="${TEST_ROOT}/canonical-source"
initialize_repo "$canonical_test_repo" "https://example.invalid/canonical-source.git"

initialize_repo "$MANAGED_REPO_DIR" "https://github.com/jheinem1/codex-desktop-linux.git"
printf 'obsolete fork state\n' >> "$MANAGED_REPO_DIR/tracked.txt"
git -C "$MANAGED_REPO_DIR" add tracked.txt
git -C "$MANAGED_REPO_DIR" commit -q -m "Obsolete managed source commit"
git -C "$MANAGED_REPO_DIR" update-ref refs/remotes/origin/main HEAD
managed_head_before="$(git -C "$MANAGED_REPO_DIR" rev-parse HEAD)"
CANONICAL_REPO_URL="$canonical_test_repo"

prepare_source_repo

[ "$SOURCE_MODE" = "managed" ] || fail_test "wrong-origin managed checkout was not treated as managed"
[ "$(git -C "$MANAGED_REPO_DIR" remote get-url origin)" = "$canonical_test_repo" ] \
    || fail_test "wrong-origin managed checkout was not repointed to canonical"
[ "$(git -C "$MANAGED_REPO_DIR" rev-parse HEAD)" = "$(git -C "$canonical_test_repo" rev-parse HEAD)" ] \
    || fail_test "wrong-origin managed checkout did not converge to canonical HEAD"
[ "$(git -C "$MANAGED_REPO_DIR" rev-parse HEAD)" != "$managed_head_before" ] \
    || fail_test "wrong-origin managed checkout retained its obsolete history"
[ "$(git -C "$legacy_repo" rev-parse HEAD)" = "$legacy_head_before" ] \
    || fail_test "managed-origin repair changed the dirty legacy checkout HEAD"
[ "$(git -C "$legacy_repo" status --porcelain --untracked-files=normal)" = "$legacy_status_before" ] \
    || fail_test "managed-origin repair changed the dirty legacy checkout worktree"

rm -rf "$MANAGED_REPO_DIR"
CANONICAL_REPO_URL="$production_canonical_url"

# Keep the test offline while exercising the complete managed-source selection
# and convergence path with a real temporary Git checkout.
clone_managed_repo() {
    initialize_repo "$MANAGED_REPO_DIR" "$CANONICAL_REPO_URL"
}

fetch_source_repo() {
    :
}

prepare_source_repo

[ "$SOURCE_MODE" = "managed" ] || fail_test "default source mode was not managed"
[ "$REPO_DIR" = "$MANAGED_REPO_DIR" ] || fail_test "default source did not use the managed checkout"
[ "$REPO_DIR" != "$legacy_repo" ] || fail_test "dirty legacy checkout was selected"
[ "$(git -C "$legacy_repo" rev-parse HEAD)" = "$legacy_head_before" ] \
    || fail_test "dirty legacy checkout HEAD changed"
[ "$(git -C "$legacy_repo" status --porcelain --untracked-files=normal)" = "$legacy_status_before" ] \
    || fail_test "dirty legacy checkout worktree changed"

wrong_origin_repo="${TEST_ROOT}/explicit-wrong-origin"
initialize_repo "$wrong_origin_repo" "https://example.invalid/not-canonical.git"
wrong_origin_head_before="$(git -C "$wrong_origin_repo" rev-parse HEAD)"
CODEX_DESKTOP_LINUX_REPO="$wrong_origin_repo"

if (prepare_source_repo) 2>"${TEST_ROOT}/explicit-wrong-origin.err"; then
    fail_test "explicit checkout with the wrong origin was accepted"
fi
grep -q 'origin is not the canonical source' "${TEST_ROOT}/explicit-wrong-origin.err" \
    || fail_test "wrong-origin explicit checkout did not fail clearly"
[ "$(git -C "$wrong_origin_repo" rev-parse HEAD)" = "$wrong_origin_head_before" ] \
    || fail_test "wrong-origin explicit checkout HEAD changed"

fast_forward_repo="${TEST_ROOT}/explicit-fast-forward"
initialize_repo "$fast_forward_repo" "$CANONICAL_REPO_URL"
printf 'upstream update\n' >> "$fast_forward_repo/tracked.txt"
git -C "$fast_forward_repo" add tracked.txt
git -C "$fast_forward_repo" commit -q -m "Upstream test update"
git -C "$fast_forward_repo" update-ref refs/remotes/origin/main HEAD
fast_forward_target="$(git -C "$fast_forward_repo" rev-parse HEAD)"
git -C "$fast_forward_repo" reset -q --hard HEAD^
CODEX_DESKTOP_LINUX_REPO="$fast_forward_repo"

prepare_source_repo
[ "$SOURCE_MODE" = "explicit" ] || fail_test "explicit override was not preserved"
[ "$(git -C "$fast_forward_repo" rev-parse HEAD)" = "$fast_forward_target" ] \
    || fail_test "clean explicit checkout did not fast-forward"

explicit_repo="${TEST_ROOT}/explicit-dirty"
initialize_repo "$explicit_repo" "$CANONICAL_REPO_URL"
printf 'dirty override\n' >> "$explicit_repo/tracked.txt"
explicit_head_before="$(git -C "$explicit_repo" rev-parse HEAD)"
explicit_status_before="$(git -C "$explicit_repo" status --porcelain --untracked-files=normal)"
CODEX_DESKTOP_LINUX_REPO="$explicit_repo"

if (prepare_source_repo) 2>"${TEST_ROOT}/explicit-dirty.err"; then
    fail_test "dirty explicit checkout was accepted"
fi
grep -q 'CODEX_DESKTOP_LINUX_REPO is dirty' "${TEST_ROOT}/explicit-dirty.err" \
    || fail_test "dirty explicit checkout did not fail clearly"
[ "$(git -C "$explicit_repo" rev-parse HEAD)" = "$explicit_head_before" ] \
    || fail_test "dirty explicit checkout HEAD changed"
[ "$(git -C "$explicit_repo" status --porcelain --untracked-files=normal)" = "$explicit_status_before" ] \
    || fail_test "dirty explicit checkout worktree changed"

diverged_repo="${TEST_ROOT}/explicit-diverged"
initialize_repo "$diverged_repo" "$CANONICAL_REPO_URL"
printf 'local commit\n' >> "$diverged_repo/tracked.txt"
git -C "$diverged_repo" add tracked.txt
git -C "$diverged_repo" commit -q -m "Local divergent commit"
diverged_head_before="$(git -C "$diverged_repo" rev-parse HEAD)"
CODEX_DESKTOP_LINUX_REPO="$diverged_repo"

if (prepare_source_repo) 2>"${TEST_ROOT}/explicit-diverged.err"; then
    fail_test "diverged explicit checkout was accepted"
fi
grep -q 'has local or diverged commits' "${TEST_ROOT}/explicit-diverged.err" \
    || fail_test "diverged explicit checkout did not fail clearly"
[ "$(git -C "$diverged_repo" rev-parse HEAD)" = "$diverged_head_before" ] \
    || fail_test "diverged explicit checkout HEAD changed"

echo "Codex Desktop managed-source tests passed."
