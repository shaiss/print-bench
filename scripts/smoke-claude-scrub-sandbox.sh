#!/usr/bin/env bash
# Smoke-test Claude Code SCRUB=1 sandboxed Bash under AppArmor unpriv_bwrap
# (Cipher ruling on #876). Run as the agent user AFTER disable-sudo.
#
# Usage: smoke-claude-scrub-sandbox.sh <absolute-claude-bin>
#
# - No provider/PAT secrets in the environment.
# - CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1.
# - Drives the pinned claude binary so Claude's own SCRUB path probes bwrap.
# - Then runs a real Bash command through Claude's sandbox-runtime (srt),
#   which is the library Claude uses to wrap Bash under SCRUB=1 — the
#   smallest equivalent that creates a user-namespace bwrap sandbox
#   (plain `bwrap true` is not enough; `bwrap --version` alone is not enough).
# - On failure: print the exact output and exit non-zero. Never suggest or
#   apply kernel.apparmor_restrict_unprivileged_userns=0.
set -euo pipefail

bin="${1:?usage: $0 <claude-bin>}"

for v in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_KEY ZAI_KEY \
         OPENROUTER_API_KEY GH_TOKEN REGEN_TOKEN; do
  if [ -n "${!v:-}" ]; then
    echo "error: ${v} must not be set during Claude SCRUB smoke" >&2
    exit 1
  fi
done

case "$bin" in
  /opt/claude-code/*) ;;
  *)
    echo "error: smoke requires the root-owned pin under /opt/claude-code/: ${bin}" >&2
    exit 1
    ;;
esac
[ -x "$bin" ] || {
  echo "error: not executable: ${bin}" >&2
  exit 1
}

export CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1

smoke_home="$(mktemp -d)"
cleanup() { rm -rf "$smoke_home"; }
trap cleanup EXIT
mkdir -p "${smoke_home}/.claude"
# Enable Claude's sandbox stack so dependency checks exercise bwrap+socat.
cat > "${smoke_home}/.claude/settings.json" <<'EOF'
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true
  }
}
EOF
cat > "${smoke_home}/.claude.json" <<EOF
{
  "hasCompletedOnboarding": true,
  "projects": {
    "${smoke_home}": { "hasTrustDialogAccepted": true }
  }
}
EOF

doctor_out="$(mktemp)"
set +e
HOME="$smoke_home" "$bin" doctor >"$doctor_out" 2>&1
doctor_rc=$?
set -e
echo "---- claude doctor (SCRUB=1) exit=${doctor_rc} ----"
cat "$doctor_out"
if grep -Eiq \
  'bubblewrap is required|bwrap.*not (installed|executable)|Creating new namespace failed|Operation not permitted|sandbox.*dependencies are missing|Failed RTM_NEWADDR|Namespace not supported' \
  "$doctor_out"; then
  echo "::error::Claude SCRUB=1 doctor failed under AppArmor unpriv_bwrap — not falling back to sysctl"
  exit 1
fi

srt_bin="$(command -v srt || true)"
[ -n "$srt_bin" ] || {
  echo "::error::srt (Claude sandbox-runtime) not on PATH — install it in trusted preflight before disable-sudo" >&2
  exit 1
}

srt_out="$(mktemp)"
set +e
HOME="$smoke_home" CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 \
  "$srt_bin" -c 'echo CLAUDE_SANDBOX_BASH_OK' >"$srt_out" 2>&1
srt_rc=$?
set -e
echo "---- srt sandboxed Bash (SCRUB=1) exit=${srt_rc} ----"
cat "$srt_out"
if [ "$srt_rc" -ne 0 ] || ! grep -qx 'CLAUDE_SANDBOX_BASH_OK' "$srt_out"; then
  echo "::error::Claude sandbox-runtime Bash wrap failed under AppArmor unpriv_bwrap — not falling back to sysctl"
  exit 1
fi

echo "smoke-claude-scrub-sandbox: ok"
