#!/usr/bin/env bash
# Smoke-test Claude Code SCRUB=1 sandboxed Bash under AppArmor unpriv_bwrap
# (Cipher ruling on #876). Run as the agent user AFTER disable-sudo.
#
# Usage: smoke-claude-scrub-sandbox.sh <absolute-claude-bin>
#
# - No provider/PAT secrets in the environment.
# - CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1.
# - Drives the pinned claude binary so Claude's own SCRUB path probes bwrap.
# - Then runs a real Bash command through Claude's sandbox-runtime (srt).
#   Full srt seccomp uses apply-seccomp's nested userns, which AppArmor's
#   bwrap-userns-restrict does NOT cover (only /usr/bin/bwrap gets the
#   capability-bearing userns). SCRUB=1 itself wraps via bwrap, so the smoke
#   configures srt with allowAllUnixSockets so the wrap goes through bwrap
#   under unpriv_bwrap — never by clearing the userns sysctl.
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

# srt settings: skip apply-seccomp nested userns (not covered by
# bwrap-userns-restrict); keep the wrap on bwrap under unpriv_bwrap.
cat > "${smoke_home}/.srt-settings.json" <<'EOF'
{
  "allowAllUnixSockets": true
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
[ "$doctor_rc" -eq 0 ] || {
  echo "::error::claude doctor exited ${doctor_rc} under SCRUB=1 — not falling back to sysctl"
  exit 1
}

srt_bin="$(command -v srt || true)"
[ -n "$srt_bin" ] || {
  echo "::error::srt (Claude sandbox-runtime) not on PATH — install it in trusted preflight before disable-sudo" >&2
  exit 1
}
command -v rg >/dev/null || {
  echo "::error::ripgrep (rg) not on PATH — srt requires it; apt-install ripgrep in preflight" >&2
  exit 1
}

srt_out="$(mktemp)"
set +e
HOME="$smoke_home" CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 \
  "$srt_bin" -s "${smoke_home}/.srt-settings.json" \
  -c 'echo CLAUDE_SANDBOX_BASH_OK' >"$srt_out" 2>&1
srt_rc=$?
set -e
echo "---- srt sandboxed Bash via bwrap (SCRUB=1, allowAllUnixSockets) exit=${srt_rc} ----"
cat "$srt_out"
if [ "$srt_rc" -ne 0 ] || ! grep -qx 'CLAUDE_SANDBOX_BASH_OK' "$srt_out"; then
  echo "::error::Claude sandbox-runtime Bash wrap failed under AppArmor unpriv_bwrap — not falling back to sysctl"
  echo "::error::exact srt output above; sysctl must stay 1"
  exit 1
fi

# Also prove a SCRUB-shaped bwrap clearenv wrap (what CLAUDE_CODE_SUBPROCESS_ENV_SCRUB
# uses for child env isolation) can create a userns under unpriv_bwrap.
bwrap_out="$(mktemp)"
set +e
bwrap --ro-bind / / --dev /dev --proc /proc --die-with-parent \
  --clearenv \
  --setenv PATH /usr/bin:/bin \
  --setenv HOME "$smoke_home" \
  --setenv CLAUDE_CODE_SUBPROCESS_ENV_SCRUB 1 \
  /bin/bash -c 'echo CLAUDE_SCRUB_BWRAP_OK; test -z "${ANTHROPIC_API_KEY:-}${ZAI_KEY:-}${GH_TOKEN:-}"' \
  >"$bwrap_out" 2>&1
bwrap_rc=$?
set -e
echo "---- SCRUB-shaped bwrap Bash wrap exit=${bwrap_rc} ----"
cat "$bwrap_out"
if [ "$bwrap_rc" -ne 0 ] || ! grep -qx 'CLAUDE_SCRUB_BWRAP_OK' "$bwrap_out"; then
  echo "::error::SCRUB-shaped bwrap Bash wrap failed under AppArmor unpriv_bwrap — not falling back to sysctl"
  exit 1
fi

echo "smoke-claude-scrub-sandbox: ok"
