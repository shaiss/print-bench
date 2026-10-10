# RFC: a non-sudo headless containment model for OVH `shai`

**Status: draft proposal (outbound).** This is a print-bench-authored RFC
*for upstream contribution to [`ovh/shai`](https://github.com/ovh/shai)* — the
reciprocal direction of the adoption study in
[issue #824](https://github.com/shaiss/print-bench/issues/824). It is a design
proposal, not a landed change: `shai` is a separate project under its own
Apache-2.0 license and governance, so nothing here is merged there by merging
it here. Merging this doc records print-bench's intent to offer the work and
freezes the design we would take upstream as an issue → PR.

## Why this exists

The adoption study of `shai` ([#824](https://github.com/shaiss/print-bench/issues/824))
declined it as a drop-in unattended *shipper* for print-bench's autonomy loop
on one hard blocker: **`shai` has no containment for unattended runs.** That is
also the single place where print-bench's own hard-won experience is deepest —
every scheduled routine here reads untrusted issue text while holding a
provider key and a GitHub token, and the whole safety model is a per-routine
deny-backstop that neutralises dangerous tool calls (`scripts/*-perms-check.sh`,
`.claude/*-settings.json`, the `reviewer-deny-canary.sh` matcher proof).

So the most valuable thing print-bench can give back to `shai` is the design it
has already paid for: a way to run an agent headless, on untrusted input,
without handing it unrestricted shell. This RFC states that design in `shai`'s
own terms, grounded in `shai`'s actual source.

## The gap in `shai` today (v0.1.11, commit `f076f61`)

Read against the real tree:

- **Headless mode auto-escalates.** `shai-cli/src/headless/app.rs` builds the
  agent with `.sudo()` on every path, and in sudo mode
  `ClaimManager::is_permitted` returns `true` unconditionally
  (`shai-core/src/agent/claims.rs`, "Sudo mode bypasses all permission
  checks"). So `echo "…" | shai` — the exact shape a CI/automation step uses —
  runs `bash`, `write`, `edit`, `multiedit` and `fetch` **with no approval and
  no restriction**.
- **The only interactive gate is a positive-match allow-list.** The TUI prompts
  `Allow`/`AllowAlways`/`Deny` and can persist granted claims
  (`shai-cli/src/tui/perm.rs`, `shai-core/src/agent/claims.rs`), and
  `AllowAlways` ("yolo") calls `controller.sudo()` to disable all further
  prompts. There is **no deny-list / deny-floor** concept: nothing can say "this
  tool call is never allowed, regardless of what was granted."
- **The coarse non-interactive levers are not a containment boundary.** Headless
  accepts `--tools` / `--remove` to add or drop whole tools
  (`shai-cli/src/headless/tools.rs`), and a config-file allow-list
  `ClaimManager` exists (`with_config_file`) — but it is positive-match, and it
  is **not wired into the sudo headless path**. Removing the `bash` tool
  entirely is the only way to stop arbitrary command execution today, which
  also removes every *safe* command.

The consequence: there is no middle ground between "fully interactive, a human
approves each action" and "fully sudo, the agent does anything." Unattended use
is all-or-nothing, and the only non-interactive option is unrestricted.

## What print-bench learned (the transferable design)

print-bench's containment is **deny-beats-allow with escape-hatch floors**, and
a test that proves the matcher actually refuses what the floors forbid. The
principles, not the code (see *Licensing*, below):

1. **A deny rule outranks every allow, from every source.** The agent may be
   handed a broad allow-list for convenience, but a deny-floor the operator
   pins can never be widened by a later allow (additive-allow is the bug a
   deny-floor exists to stop).
2. **Deny whole classes of escape hatch, not just command names.** A name-only
   block is trivially bypassed. The floors that matter in practice:
   - shell indirection — `bash -c` / `sh -c` / `dash -c` (and option-order
     variants like `bash -lc`), which smuggle an arbitrary command past a
     per-command matcher;
   - environment-prefix tricks — `FOO=bar some-cmd`, and `env`/`export`/`unset`
     resetting a locked variable;
   - global-option indirection — e.g. `git --git-dir=… …` or
     `git -c core.pager=… …`, where a global flag before the subcommand changes
     what runs without any watched token appearing;
   - package/toolchain installers and network fetchers the task does not need.
3. **Prove the matcher with a negative control.** print-bench extracts the real
   permission matcher the runtime uses and asserts that a representative hostile
   invocation for each floor is *refused* — a positive and a negative control
   per rule (`scripts/reviewer-deny-canary.sh`, the `*-perms-check.sh` family's
   `--selftest`). A containment claim with no failing test is a claim that has
   never been tested.
4. **State the threat model.** The floors are only meaningful against a written
   assumption — here, "the agent is reading attacker-controlled text while
   holding credentials" — so the doc that ships the policy says what it defends
   against and what it does not.

## Proposed design for `shai`

A minimal, `shai`-native shape that keeps the interactive experience unchanged
and adds a *bounded* non-interactive mode:

1. **A non-sudo headless policy mode.** Headless runs take an explicit policy
   instead of `.sudo()`. Concretely: a `--policy <file>` (or a
   `tools.permissions` block in the existing agent `*.config` JSON, beside
   `tools.mcp`) that wires the config-file `ClaimManager` *into the headless
   path*, so `is_permitted` is actually consulted rather than short-circuited.
   `--sudo` / `--yolo` stays available as an explicit, documented opt-out — the
   change is that **sudo is no longer the silent default of piped input.**
2. **Deny-floors that outrank allows.** Extend `ClaimManager` with a deny set
   evaluated before the allow set: a tool call matching any deny rule is
   refused even if an allow rule (or a persisted claim) would permit it. Ship a
   default deny-floor for the escape-hatch classes in principle (2) above, as a
   constant a caller can extend but not weaken.
3. **A capability-aware default.** Reuse `shai`'s existing tool capabilities
   (`Read` vs `Write`/`Network`, already in `shai-core/src/agent/actions/tools.rs`):
   in policy mode, read-only tools run; `Write`/`Network` tools require an
   explicit allow *and* must clear the deny-floors.
4. **A matcher negative-control test.** A Rust test suite (unit tests are
   required by `shai`'s `CONTRIBUTING.md`) that, for each deny-floor, feeds a
   hostile invocation and asserts it is refused, plus a benign control that is
   allowed — so the floor cannot silently rot. This is the `reviewer-deny-canary`
   idea expressed in `shai`'s own test harness.
5. **A short threat-model note** in `shai`'s docs: "running `shai` headless on
   untrusted input," stating the credential-exposure assumption and what policy
   mode does and does not guarantee.

### Non-goals / scope

- This does **not** make `shai` run Claude Code *skills* (`/ship-issue`,
  `/design-run`). `shai` runs its own agent and `SHAI.md` context; that is an
  architectural fact a containment change does not touch, and the study called
  it out separately. The goal here is to make `shai` *safe to run unattended in
  general*, which benefits every `shai` user, not only print-bench.
- This does **not** change the interactive TUI behaviour, the provider layer,
  or the HTTP server. It adds a bounded headless mode; it removes nothing.
- This is **not** a sandbox/jail (process isolation, seccomp, containers). It is
  an in-process policy on the agent's tool calls — complementary to, not a
  substitute for, running the whole agent in a sandbox.

## Licensing & how this gets upstreamed

The direction matters because the license boundary runs the opposite way to the
study's concern:

- `shai` is **Apache-2.0** and requires contributions under Apache-2.0 with a
  **DCO sign-off** (real name, no CLA), an Apache header on new files, unit
  tests and docs (`ovh/shai` `CONTRIBUTING.md`).
- print-bench's first-party tree — including `scripts/` and `tools/` — is
  **CC-BY-SA-4.0** (see `LICENSE`). ShareAlike is copyleft and is **not
  relicensable to Apache-2.0**, so print-bench's containment scripts **cannot be
  copied verbatim** into `shai`. (And they are bash/Python/Actions YAML, while
  `shai` is Rust — a verbatim port was never the shape anyway.)

Therefore this contribution is **design-and-knowledge transfer plus fresh
Apache-2.0 Rust authored directly for `shai`** — ideas, threat model and test
strategy are not copyrightable; the code is written new, under `shai`'s license,
with a DCO sign-off. The patterns above are stated at the design level precisely
so they can be re-implemented cleanly rather than lifted.

Given `shai` has effectively a single maintainer (Lucien Loiseau, OVH), the
sequence is **issue/RFC first, then PRs**, smallest-first to build rapport:

1. Open an upstream issue proposing the non-sudo headless policy mode + deny-floors,
   linking this RFC as the rationale and the threat model.
2. Land a small, uncontroversial precursor first (the license-hygiene PR the
   study noted — SPDX ids, `license` fields, NOTICE) to establish the
   contribution flow.
3. PR the deny-floor extension to `ClaimManager` with its negative-control test.
4. PR the headless policy-mode wiring + the threat-model doc.

Each upstream PR is Apache-2.0, DCO-signed, unit-tested and documented, per
`shai`'s contributing rules.

## The loop this closes

The study declined `shai` as a shipper because of this exact containment gap. If
the gap is closed upstream, a future re-evaluation could move from *declined* to
*additive*, and print-bench would gain a self-hostable, Apache-2.0,
EU-sovereign-capable agent runtime it helped harden — one that lives inside repo
workflows under `AI_ANDON_CORD`'s reach. Contributing the fix is both good OSS
citizenship and self-interested in the honest sense: print-bench benefits most
if the tool it might one day run is one it helped make safe.

## References

- Adoption study: [#824](https://github.com/shaiss/print-bench/issues/824) (the inbound evaluation this reciprocates).
- `shai` source (v0.1.11): `shai-cli/src/headless/app.rs`, `shai-core/src/agent/claims.rs`, `shai-cli/src/tui/perm.rs`, `shai-cli/src/headless/tools.rs`, `shai-core/src/agent/actions/tools.rs`.
- `shai` contribution terms: `ovh/shai` `CONTRIBUTING.md` (Apache-2.0, DCO).
- print-bench containment machinery this draws on: `scripts/reviewer-deny-canary.sh`, the `scripts/*-perms-check.sh` family, `.claude/*-settings.json`, and the backstop discipline described in `CLAUDE.md`.
- print-bench licensing boundary: `LICENSE`, `docs/licensing.md`.
