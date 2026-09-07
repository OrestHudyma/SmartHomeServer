#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
update_remote="${SMARTHOME_REMOTE:-origin}"
update_timeout="${SMARTHOME_UPDATE_TIMEOUT:-30s}"
lock_file="${SMARTHOME_LOCK_FILE:-${XDG_RUNTIME_DIR:-/tmp}/smarthome-server-${UID}.lock}"
secrets_path="${SmartHome_secrets:-}"

candidate_root=""
candidate_dir=""

log() {
    printf '%s\n' "$*"
}

warn() {
    printf 'WARNING: %s\n' "$*" >&2
}

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

cleanup_candidate() {
    if [[ -n "$candidate_dir" && -d "$candidate_dir" ]]; then
        git -C "$project_dir" worktree remove --force "$candidate_dir" \
            >/dev/null 2>&1 || true
    fi

    if [[ -n "$candidate_root" && -d "$candidate_root" ]]; then
        rmdir "$candidate_root" 2>/dev/null || true
    fi
}

trap cleanup_candidate EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$project_dir"

command -v git >/dev/null 2>&1 || fail "git is not installed"
command -v flock >/dev/null 2>&1 || fail "flock is not installed"
command -v timeout >/dev/null 2>&1 || fail "timeout is not installed"

if [[ -n "${SMARTHOME_PYTHON:-}" ]]; then
    python_bin="$SMARTHOME_PYTHON"
elif [[ -x "$project_dir/.venv/bin/python" ]]; then
    python_bin="$project_dir/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    python_bin="$(command -v python3)"
else
    fail "Python 3 is not installed"
fi

[[ -x "$python_bin" ]] || fail "Python is not executable: $python_bin"
[[ -n "$secrets_path" ]] || fail "SmartHome_secrets is not set"
[[ -f "$secrets_path" && -r "$secrets_path" ]] || \
    fail "Secrets file is not readable: $secrets_path"

exec 9>"$lock_file" || fail "Cannot open lock file: $lock_file"
flock -n 9 || fail "SmartHomeServer is already running"

update_server() {
    local branch
    local current_branch
    local remote_ref
    local local_revision
    local remote_revision

    current_branch="$(git branch --show-current)"
    if [[ -z "$current_branch" ]]; then
        warn "Detached HEAD; automatic update skipped"
        return
    fi

    branch="${SMARTHOME_BRANCH:-$current_branch}"
    if ! git check-ref-format --branch "$branch" >/dev/null 2>&1; then
        warn "Invalid update branch '$branch'; automatic update skipped"
        return
    fi

    if [[ "$current_branch" != "$branch" ]]; then
        warn "Current branch is '$current_branch', expected '$branch'; automatic update skipped"
        return
    fi

    if ! git remote get-url "$update_remote" >/dev/null 2>&1; then
        warn "Git remote '$update_remote' does not exist; automatic update skipped"
        return
    fi

    if ! git diff --quiet || ! git diff --cached --quiet; then
        warn "Tracked files contain local changes; automatic update skipped"
        return
    fi

    log "Checking ${update_remote}/${branch} for updates..."
    if ! timeout "$update_timeout" env GIT_TERMINAL_PROMPT=0 \
        git fetch --quiet --prune "$update_remote" \
        "+refs/heads/${branch}:refs/remotes/${update_remote}/${branch}"; then
        warn "Update check failed; starting the current version"
        return
    fi

    remote_ref="refs/remotes/${update_remote}/${branch}"
    local_revision="$(git rev-parse HEAD)"
    remote_revision="$(git rev-parse "$remote_ref")"

    if [[ "$local_revision" == "$remote_revision" ]]; then
        log "Server is up to date"
        return
    fi

    if ! git merge-base --is-ancestor "$local_revision" "$remote_revision"; then
        warn "Remote update is not a fast-forward; starting the current version"
        return
    fi

    candidate_root="$(mktemp -d)"
    candidate_dir="$candidate_root/checkout"
    git worktree add --quiet --detach "$candidate_dir" "$remote_revision"

    log "Testing update $remote_revision..."
    if ! (
        cd "$candidate_dir"
        "$python_bin" -m py_compile \
            main.py nmea.py periphery.py telegram_interface.py test.py
        "$python_bin" -m unittest -q test.py
    ); then
        warn "Update tests failed; starting the current version"
        cleanup_candidate
        candidate_dir=""
        candidate_root=""
        return
    fi

    cleanup_candidate
    candidate_dir=""
    candidate_root=""

    if [[ "$(git rev-parse HEAD)" != "$local_revision" ]] || \
        ! git diff --quiet || ! git diff --cached --quiet; then
        warn "Repository changed while testing; automatic update skipped"
        return
    fi

    git merge --ff-only "$remote_revision"
    log "Server updated to $remote_revision"
}

update_server
exec "$python_bin" -u "$project_dir/main.py"
