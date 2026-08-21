# Proposal: an agentic adoption-study assessor

**Status: proposed, not built.** This document designs an unattended agent that
would read a filed [adoption study](adoption-studies.md) and auto-draft its
split verdict — the *redundant / additive / where-integration* reading a human
writes today. It is written so a future session can build it in one PR against a
frozen design, the way `docs/decision-gate.md` shipped its gate before its
skills consumed it. **Nothing here exists yet**; the assessment stays
human-run until this is built and armed.

Why write the design down now and stop there: auto-drafting a disposition means
an agent reading **untrusted issue text** and writing back to GitHub, which is
exactly the boundary the labeler, the chunker, and the product scout sit behind.
That boundary is crossable — the repo has a proven, gated pattern for it — but it
is not crossed by accident, and it is not worth crossing until a human is drowning
in studies to read. This proposal reuses that pattern verbatim rather than
inventing machinery (N6): the bet is orchestration, not a new mechanism.

## The one boundary this agent may never cross

The assessor produces an **advisory disposition a human acts on** — one Reeve
*surfaces* to the lead but never acts on itself (Reeve stays a reporter, per
`docs/adoption-studies.md` and `PM.md`; the disposition is a human's call).
That single sentence is the whole safety story, and it decomposes into four
refusals the build must enforce by construction, not by prompt:

- **It never decides adoption.** It drafts a reading; a human adopts. The study
  it writes is input to a decision, never the decision.
- **It never applies a routing label.** Not `autonomy-ok`, not `design-brief`,
  not `needs-decision` — and not even the advisory `disposition:*` labels, which
  stay the human's reading (see `docs/adoption-studies.md`). Its only write is
  the drafted split-verdict *comment*.
- **It never crosses the license boundary (issue #160).** It *reports* license
  reach against `docs/licensing.md`; it changes no committed policy, adds no
  dependency, and touches no `lib/`/`scripts/`/`site/` code.
- **It never merges, pushes, or opens a PR.** No `contents: write`, no branch,
  no PR — the ambient `GITHUB_TOKEN` with the narrow scopes below.

Everything downstream (Reeve surfacing the study, a human raising a brief) is
unchanged: the assessor only fills the *awaiting-a-disposition* gap faster.

## The proven pattern it reuses

The scout (`docs/` layout bullet, issue #241/#242) and the labeler are the
templates. An adoption-study assessor is the scout with a different verb —
*comment a verdict on an existing issue* instead of *file a new brief* — so it
carries the same seven-part harness:

### 1. One narrow intake surface, split by direction

Reading and writing go through two different, minimal surfaces — never a general
shell:

- **Reading** is the narrow wrapper `assessor-helper.sh`
  (`list-awaiting` → open `adoption-study` issues with no `disposition:*` label;
  `read-thread <n>` → one issue body + comments). Trivial args that pass as bare
  commands under the deny backstop, exactly like the scout's
  `scout-helper.sh` `list-briefs`/`read-thread`.
- **Writing** is an **MCP stdio tool**, `post_adoption_disposition`, served by a
  committed `assessor_mcp.py` and wired with `--mcp-config`. A tool, not a Bash
  verb, for the reason the scout's `file_design_brief` is one: a study's split
  verdict is a rich, multi-line markdown body (tables, newlines) and a
  `gh issue comment --body '…'` with table pipes is **denied on a command line
  under `dontAsk` no matter how it is quoted**, whereas a JSON tool argument
  never touches a command line. The tool hardcodes what keeps it safe, and
  **validates the target at write time** rather than trusting the model's supplied
  number: immediately before posting it **re-reads the target issue and requires
  it to be open, still carry `adoption-study`, and carry no `disposition:*`
  label** — so a stale or prompt-injected run cannot comment on a closed or
  already-ruled study (the read wrapper's `list-awaiting` is a convenience, never
  the enforcement boundary, since the model supplies the number later). It
  **binds the write to the run's candidate set** and **rejects a duplicate**
  disposition on an issue it (or a prior run) already commented on; it prepends
  the advisory framing to every body, applies **no label**, and **caps
  dispositions per run** via a run-scoped in-process counter.

### 2. `--permission-mode dontAsk` makes `--allowedTools` exclusive

Run the agent with `--permission-mode dontAsk` over its own two surfaces
(`assessor-helper.sh` + the MCP tool) so nothing else is even proposable — the
same mode the scheduled scout, labeler, and chunker use.

### 3. A per-routine deny backstop

`claude-code-action` loads `.claude/settings.json` via `settingSources=project`,
and allow rules **merge additively**, so the narrow `--allowedTools` does not
remove the dev allows (`Bash(xvfb-run:*)`, `git`, `gh`, the sibling wrappers).
The assessor closes that with its **own** `.claude/adoption-assessor-settings.json`
(passed via `--settings`, where deny beats allow from every source), which must:

- **deny every non-wrapper Bash allow** in `settings.json` — the coverage rule,
  identical to the scout's;
- **additionally deny `chunk-helper.sh`, `label-helper.sh`, AND
  `scout-helper.sh`** — **none is the assessor's surface**; each is another
  issue-/label-writing capability it must not inherit (the scout already denies
  the first two; the assessor denies all three, adding its sibling scout's
  wrapper to the list);
- **deny `Write`, `Edit`, `NotebookEdit`** — it edits no files;
- **never deny its own `assessor-helper.sh`** — denying its one read wrapper
  fails the scheduled run closed with no other CI signal.

### 4. A perms-check with a `--selftest`, run by `check.sh`

`scripts/adoption-assessor-perms-check.sh`, modelled on `scout-perms-check.sh`:
prove every non-wrapper Bash allow in `settings.json` is denied in the
assessor's backstop, and that `assessor-helper.sh` is **not** denied. A
`--selftest` proves the check can both pass and fail on fixtures. Wire it into
`check.sh` beside the other perms-checks, and name it in `CLAUDE.md`'s
`scripts/` layout bullet and `README.md` (docs-check.sh section 5 requires both).

### 5. Two-key arming, shipped disarmed

`.github/adoption-assessor.conf` (house `key: value`, `enabled`/`provider`/
`cadence`) is the git-tracked intent; the repo variable
`ADOPTION_ASSESSOR_ENABLED` is the live, human-only arming switch kept out of
git. The routine acts only when **both** agree — shipped with `enabled: true`
possible but the **variable unset**, so a clone/fork can never inherit an armed
issue-writer, and a maintainer flips it off in seconds without a commit.

### 6. Cadence in two places, kept in parity

The `cadence:` key in the conf and the `cron:` literal in
`.github/workflows/adoption-assessor.yml` must agree (Actions can't read a file
for `on.schedule`). Add `adoption-assessor` to the `ROUTINES` list in
`scripts/cadence-sync-check.sh` so the parity is enforced. A calm cadence fits —
studies arrive rarely; weekly, after Reeve's morning report, is a sensible
default so a freshly-drafted disposition shows up in the next report.

### 7. The model comes from the registry, never pinned

Add a `[chain:adoption-assessor]` stanza to `.github/models/registry.conf`
(issue #206) and resolve it in the workflow the way `auto-review.yml` resolves
the `review` chain — so swapping the model is a registry edit, not a YAML edit.
Do **not** hardcode a `--model` in the workflow or the skill. Assessing untrusted
text into a careful verdict is nearer the review tier than the cheap scout tier;
the chain's ordering is where that judgment lives, and `model-smoke.yml` proves
each link is callable before a routine points at it (issue #298).

### Workflow permissions

`contents: read` and `issues: write` **only** — no `pull-requests`, no
`contents: write`. Check out the **default branch** (never PR head — the agent
reads untrusted issue text, so it must run trusted base tooling) with
`persist-credentials: false`. The single write is the MCP tool's disposition
comment through the ambient `GITHUB_TOKEN`; a `GITHUB_TOKEN`-authored comment
triggers no workflow, which is correct here — the assessor informs, it does not
re-trigger anything.

## The concrete files a build would add

| File | Role |
|---|---|
| `.claude/skills/adoption-assessor/SKILL.md` | the assessor's mandate: how it reads a study and writes the split verdict; the four refusals above stated as its charter |
| `.claude/skills/adoption-assessor/assessor-helper.sh` | the narrow **read** wrapper (`list-awaiting`, `read-thread`) — trivial bare-command args |
| `.claude/skills/adoption-assessor/assessor_mcp.py` | the MCP stdio server exposing the one **write** tool `post_adoption_disposition` (requires the `adoption-study` label, advisory framing hardcoded, per-run cap) |
| `.claude/skills/adoption-assessor/assessor-mcp.json` | wires the MCP server via `--mcp-config` |
| `.claude/adoption-assessor-settings.json` | the deny backstop (§3) |
| `scripts/adoption-assessor-perms-check.sh` | the drift check with `--selftest` (§4), run by `check.sh` |
| `.github/adoption-assessor.conf` | the two-key policy conf (§5) |
| `.github/workflows/adoption-assessor.yml` | the scheduled routine (`contents:read` + `issues:write`, default-branch pin, `persist-credentials:false`) |
| `[chain:adoption-assessor]` in `.github/models/registry.conf` | the model chain (§7), `model-smoke.yml`-provable |
| edit `scripts/cadence-sync-check.sh` `ROUTINES` | add `adoption-assessor` for cadence parity (§6) |
| edits to `CLAUDE.md` + `README.md` + `docs/adoption-studies.md` | document the built routine (docs-check.sh requires the script named in both layout docs) |

## What this deliberately does not do

- It does **not** decide, label-route, adopt, merge, or push (the one boundary).
- It does **not** replace the human reading — a `disposition:*` label stays the
  human's, and Reeve still surfaces both *awaiting* and *worth-raising-but-open*
  studies. The assessor only makes the draft the human reads land sooner.
- It does **not** gain "hands" beyond one comment. Widening its writes (applying
  labels, opening briefs) would be a separate, separately-argued proposal — the
  same staging Reeve's own "hands" (`PM.md` B1) sit behind.

## References

- `docs/adoption-studies.md` — the process this would automate.
- `docs/decision-gate.md` — the "ship the gate, defer the consumption" precedent.
- `docs/licensing.md` — the license boundary a study reports against (issue #160).
- `PM.md` — Reeve, the deterministic keeper the assessor feeds; and B1, the
  matching "hands behind a deny-backstop" staging.
- The scout (`CLAUDE.md`, issues #241/#242) and `scripts/scout-perms-check.sh` —
  the wrapper + MCP-write + deny-backstop pattern reused here.
