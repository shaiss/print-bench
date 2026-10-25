Closes #875

## Cipher rulings on #876 (this revision)

Cipher's security review replaced the first-pass approach (global userns sysctl + `install.sh`). This PR implements that contract, plus the MED-1 / MED-2 hardening from the CHANGES_REQUESTED review at `4be650be`.

Non-blocking follow-ups from that review (MED-3 project-config reset, env blank-list gaps, canary dummy-secret assertion, sandbox-runtime 0.0.81 / advisories / GPG VALIDSIG / root-owned `node_modules`, zizmor pins) are tracked in **#926** — not in this PR.

### Agent uid

Agent steps (and the SCRUB smoke) run as the GitHub Actions runner user **`runner`** (typically uid **1001**) — the same non-root uid that owns the job after checkout. Nothing in this path escalates to root after disable-sudo.

### Disable-sudo still strips setuid after apt

Trusted preflight still runs **before** disable-sudo: `apt-get install bubblewrap apparmor-profiles` (+ toolchain on the burn), AppArmor profile load, GPG-pinned Claude install under `/opt`, root-owned Claude **managed-settings** under `/etc/claude-code/` with absolute `bwrapPath` / `socatPath` / `ripgrep.command`. Then disable-sudo still `chmod a-s` on sudo/pkexec/su/doas, drops docker group/sockets, and asserts `sudo -n true` fails. Setuid stripping is unchanged and still happens **after** those apt installs.

### Every agent step's `if:` requires preflight, disable_sudo, smoke, and per-link re-verify

Each of the five keyed ship/run links gates on:

- `steps.preflight.outcome == 'success'`
- `steps.disable_sudo.outcome == 'success'`
- `steps.scrub_smoke.outcome == 'success'`
- `steps.verify_claude_N.outcome == 'success'`

### MED-1 — verify scripts restored from `START_SHA`

`verify_claude_N` no longer executes `${GITHUB_WORKSPACE}/scripts/verify-*.sh` (agent-writable tree, `#!/usr/bin/env bash`). It restores both verify script blobs from `START_SHA` into `RUNNER_TEMP` (same pattern as the deliver/bundle step) and invokes them as `/usr/bin/bash <file>`.

### MED-2 — inherited PATH + absolute SCRUB helpers

`GITHUB_PATH` entries are prepended **ahead of** step-level `env.PATH`, so a planted fake `bwrap` could otherwise run unsandboxed and read `/proc/<claude>/environ`. This revision:

- Fails the verify step unless the **inherited** `PATH` is exactly `/usr/bin:/bin` (checked in the step and again inside the verify scripts — scripts do **not** re-export `PATH` before that check)
- Installs root-owned `/etc/claude-code/managed-settings.json` with absolute `sandbox.bwrapPath` / `sandbox.socatPath` / `sandbox.ripgrep.command` (Claude honors the first two from managed settings only)
- Pins the same absolute paths in the SCRUB smoke's `.srt-settings.json`

Allowlisted wipe of `/home/runner/.claude`, `/home/runner/.config/claude`, and `/home/runner/.claude.json` still runs before each keyed link; managed settings under `/etc/claude-code/` are not wiped.

### `design-run-deliver.sh --selftest` pins

The deliver selftest asserts SCRUB=`1` (never `0`), step order preflight → disable-sudo → SCRUB smoke → verify → agent, committed CLI sha256 `bc1aad9982c7b59c7d889ff92595d61cf46e0a6eae074cb551d932a989bcd222`, GPG fingerprint `31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE`, **absence** of `apparmor_restrict_unprivileged_userns=0`, **absence** of `curl|bash` / `install.sh` / `bootstrap.sh`, MED-1 START_SHA restore + `/usr/bin/bash` invoke, and MED-2 inherited-PATH / absolute helper pins.

## Also in this head

1. **`runs-on: ubuntu-24.04`** for canary / burn / design-run ship jobs — `ubuntu-latest` is 26.04 and lacks `bwrap-userns-restrict` (same pattern as #920).
2. **Lockfile-integrity install for sandbox-runtime** — committed `.github/sandbox-runtime/{package.json,package-lock.json}` (~64-line lockfile) + `npm ci --ignore-scripts` so transitive deps are hash-verified.

## Approach

| # | Cipher requirement | Implementation |
|---|---|---|
| 1 | No global userns sysctl; AppArmor `bwrap-userns-restrict` | `scripts/setup-bwrap-apparmor.sh` — copy profile, `apparmor_parser -r`, assert `bwrap`+`unpriv_bwrap` `(enforce)`, sysctl still `1`, `dpkg -S` ownership |
| 1 | Real SCRUB=1 Claude sandbox smoke (not `bwrap true`) | `scripts/smoke-claude-scrub-sandbox.sh` after disable-sudo as `runner`; on failure stop and report — no sysctl fallback |
| 2 | No install.sh / bootstrap / curl\|bash; GPG + pin | `scripts/install-claude-code-pin.sh` — import key, fingerprint match, `gpg --verify` manifest.sig, sha256 vs signed manifest **and** committed pin; install env clears ANTHROPIC/ZAI/OPENROUTER/PAT secrets |
| 3 | Root-owned `/opt/claude-code/2.1.301/claude` | `install -o root -g root -m 0755`; `path_to_claude_code_executable`; per-link `verify-claude-code-pin.sh` |
| MED-1 | Verify scripts not taken from agent-writable tree | Restore from `START_SHA` → `RUNNER_TEMP`; `/usr/bin/bash` invoke |
| MED-2 | GITHUB_PATH cannot plant fake bwrap for verify / SCRUB | Exact inherited `PATH=/usr/bin:/bin` on verify; absolute bwrap/socat/rg in Claude managed-settings + srt config |
| 4 | Out of scope here | Action dir, bun remain runner-writable; MED-3 / env gaps / canary assertion / supply chain / zizmor → **#926** |

## Coordination with #870

**Not absorbed.** Pip stays before disable-sudo on the burn so #870 can still land alone.

## Vendor `install.sh` note

Anthropic's `claude.ai/install.sh` fetches HTTPS checksums for the binary but does **not** GPG-verify `manifest.json.sig` in-script. This PR never uses it; the repo does the GPG verify + dual sha256 check itself.

## Proof

- `./scripts/design-run-deliver.sh --selftest`: ok

## Review

`.github/**` change → **Cipher CLEAR required before merge.** Do not merge from this agent.
