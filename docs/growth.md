# The growth desk — PMs queue, channel agents post

The growth desk is how print-bench talks about itself in public without any
agent ever holding an open microphone. It introduces one new concept to the
bench — **queuing** — and builds the first channel on top of it: product
managers (Vera on a design, Reeve on the platform, Remy scouting, or the
human lead) **queue messages** — what is worth announcing, the one link, and
the fact budget that makes it true — and a **channel-specific growth agent**
drains that queue on its own schedule, writing the channel-native copy. The
first channel agent is **Lark** (`/growth-twitter`, `people/lark.md`) for
Twitter/X; YouTube is the named next channel and gets its own agent when its
skills exist, because channels are crafts: what grows an audience on X
(hooks, weighted 280, threads) is not what grows one on YouTube (titles,
retention, chapters). The queue is the seam that keeps those crafts owned by
specialists while message intent stays with the PMs.

The whole desk is dry-run-first: until a human climbs every rung of the
arming ladder below, the "posts" are review comments on the queue issues and
committed accelerated-timeline reports under `growth/` — the feed you can
read before it exists.

## Voice — building in public

The account has one voice, and it is deliberate: **a maker at the bench who
shows their work** — sentence-case, first person, plain and a little dry, the
register of someone talking to fellow makers as equals rather than a brand
addressing an audience. print-bench is built in the open (human + AI, every
claim gated in CI), and the account grows the same way: by being useful and
honest post by post, never by hype. Two genres do the work — *here's how it
works* (a technique, a measured number, a mechanism) and *here's what we got
wrong* (the print that came out welded, the hinge that fused, and the gate
each failure became). The failure genre is the stronger one; being wrong in
public and fixing it in the open is the credibility, which is why the bench
gates its own claims at all.

This posture is **Reeve's** as the platform PM (`PM.md`): the growth desk is
how the bench humbly grows a community around open code, so a PM queues the
honest, technical, lesson-bearing stories and leaves hype off the queue. The
register itself lives where Lark reads it — the *Voice* and *Channel craft*
sections of `.claude/skills/growth-twitter/SKILL.md`, with a before/after
calibration example — and the fact-budget rule keeps it honest by
construction: a build-in-public voice with no source for a claim is still
refused, so "sound human" never becomes "make something up".

## Why a queue, and why the agent is per-channel

A PM knows *that* the printable-threads story is worth telling and *which
measured fact* makes it honest; a PM does not (and should not) know X's
weighted-length rule, thread etiquette, or posting-time craft. Inverting
that — letting a channel agent decide what the bench announces — would put
taste and scope decisions in the wrong seat (the same reason `/ship-issue`
declines design requests). The queue is the contract between the seats:

* a queue item carries **intent + a fact budget**, never finished copy —
  the channel agent may compose only from the facts it was handed and the
  repo's own committed text, so a claim with no source can never be posted;
* the channel agent owns **how the channel says it** — and each channel is a
  separate agent with its own skill, schedule, and (eventually) credentials,
  so adding YouTube never touches Lark;
* nothing is lost when nobody is listening: an unqueued idea is an issue
  nobody filed, an undrained item just waits, and every drain outcome lands
  on the item's own thread.

## The pieces

* **The queue** — open issues labeled `growth-queue` + `channel:<name>`,
  in the shape of `templates/growth-post.md` (Channel, Message, Link, Facts
  & sources, Timing & priority — the fourth stay-identical template/form
  pair; the form `.github/ISSUE_TEMPLATE/growth-post.yml` is the hand-filed
  Twitter variant). Drain order is deterministic — `priority:high` first,
  then oldest — pinned in `tools/growth` (`growth.queue`), not vibes.
* **`/growth-queue`** — the PM-side filing skill. Its one write is the MCP
  tool `queue_growth_post` (`.claude/skills/growth-queue/queue_mcp.py`),
  which hardcodes the `growth-queue` + `channel:<name>` labels (it can never
  apply `approved-to-post`, `priority:high`, or a routing label — queuing
  grants nothing), requires the `Growth post:` title prefix, and caps
  filings per scheduled run (attended, a human is the trust boundary — the
  sibling servers' posture).
* **`/growth-twitter` (Lark)** — the Twitter/X channel agent and the desk's
  first drain. Oracle-shaped: **no shell wrapper**; reads are Read/Grep/Glob
  over `.growth-context/<n>/issue.md` (assembled by trusted workflow bash,
  the `.oracle-context/` pattern) and the repo tree; the one write is the
  MCP tool `post_tweet` (`.claude/skills/growth-twitter/growth_mcp.py`).
* **The posting tool** — the most-guarded write surface on the bench,
  because it alone can eventually reach *outside* the repo. It re-reads the
  target at write time (open, not a PR, `growth-queue` + `channel:twitter`,
  not `needs-decision`), binds to the trusted Select step's candidate set
  (`GROWTH_SELECTED_ISSUES`), meters copy with the weighted rule (URLs = 23,
  wide code points = 2, hard cap 280 — `growth.tweetlen` is the reference,
  and `tools/growth/tests/test_server_parity.py` pins the server's copy to
  it), enforces one post per queue item ever (`<!-- growth-twitter:posted
  -->` / `<!-- growth-twitter:dry-run -->` marker comments), caps posts per
  run, applies no labels, and decides dry-run vs live itself — the model
  never does. After a live post it closes the drained item (queue
  semantics); after a dry run it only comments.
* **`tools/growth`** — the deterministic engine (strict conf parser, the
  weighted-length rule, the drain policy, a minimal cron matcher, the
  per-UTC-day live-post cap (`daycap`), the accelerated-timeline simulator,
  the OAuth 1.0a X poster seam), stdlib-only with its own pytest suite; see
  its README.
* **The routine** — `.github/workflows/growth-twitter.yml` +
  `.github/growth-twitter.conf` (enabled / provider / cadence /
  `max_posts_per_run` / `max_posts_per_day` / `require_approval`, parsed by tools/growth's own
  strict parser), cadence-parity-checked by `scripts/cadence-sync-check.sh`,
  model from the `[chain:growth-twitter]` registry chain (a GLM head, then
  the Anthropic tail `claude-sonnet-5` → `claude-haiku-4-5`, walked across
  providers since #544 — the adoption-assessor's reasoning), deny backstop
  `.claude/growth-twitter-settings.json` pinned by
  `scripts/growth-perms-check.sh` (no wrapper exemption; must deny every
  sibling write surface AND `mcp__growth_queue` — the poster can never
  refill the queue it drains. Every *other* sibling backstop denies both
  growth servers in return; the one exception is `reeve-growth` (the
  generative front, below), which owns the queue server and denies the poster
  instead — the mirror of this backstop, pinned by
  `scripts/reeve-growth-perms-check.sh`).
* **`growth/`** — the desk's committed artifacts: the accelerated dry-run
  timelines (`growth/twitter/dryruns/`) a human reads before arming
  anything.
* **The approval board** — a GitHub Project (v2) where each stageable queue
  issue is a card grouped by its derived Stage, so a human sees where each post
  sits and approves it at a glance (a closed, unposted item — a human's
  rejection — has no Stage and is left off the board). Its schema lives in git
  (`scripts/gh-project.sh --board growth`), the Stage policy in
  `tools/growth` (`growth.board.stage_of`), and `growth-board-sync.yml`
  reflects each issue's state onto it. Detailed below; a LENS, not a control
  surface — approving is still applying `approved-to-post`.

## The arming ladder — three human rungs, no agent on any of them

1. **Run at all** — `.github/growth-twitter.conf` `enabled: true` (in git,
   reviewed) **and** the `GROWTH_TWITTER_ENABLED` repo variable (live,
   human-only). Shipped disarmed: the variable is unset. Armed at this rung
   the routine drains the queue as **dry-run comments** — nothing leaves
   GitHub.
2. **May publish** — the `GROWTH_TWITTER_LIVE` repo variable set to `true`
   **and** the four X credentials (`X_API_KEY`, `X_API_SECRET`,
   `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`) as repo secrets. The posting
   tool checks both itself; a model cannot reach either.
3. **This post, now** — per item, the human-applied `approved-to-post`
   label (while the committed policy says `require_approval: true`). The
   dry-run comment on the queue issue is exactly what is being approved.
   The label itself is **auto-ensured by the first armed run** (the drain
   job creates it idempotently), so it always exists for a human to apply —
   merging the desk's code never creates repo labels.

Turning `require_approval` off (a one-line reviewed PR) is the deliberate
last step to a fully autonomous channel — never a default, and rungs 1–2
still hold.

## Cadence — a bounded number of posts a day, at times GitHub varies for us

A fixed daily cron makes every tweet land at the same clock minute — a
robotic drumbeat a reader clocks instantly, the opposite of "a maker posting
when they have something to say". Lark keeps its **≤`max_posts_per_day`
(default 2) live posts/day** cap but varies *when* those posts land — and it
does so by leaning into, rather than fighting, how GitHub actually runs
scheduled workflows.

The load-bearing fact is that **GitHub's scheduled-workflow queue is
best-effort**: it delivers runs heavily delayed (tens of minutes to hours),
at an arbitrary time, and drops most of a day's cron slots under load.
Observed on this repo across three consecutive days, the workflow was
delivered *once* each day at **21:55, 19:31 and 00:39 UTC** — not at any of
its nominal slot minutes, one even past midnight. So:

* The cadence (`19 13-21/2 * * *`) is **delivery redundancy**, not five post
  times: five reader-awake slots (13:19 / 15:19 / 17:19 / 19:19 / 21:19 UTC)
  are five chances for GitHub to land at least one firing on a given day. The
  drain runs on **whichever firing GitHub delivers** — there is no chosen-hour
  gate. (An earlier design *did* gate on a per-date chosen hour; because the
  one delivered firing almost never equalled it, the drain was skipped every
  day and **nothing posted** — the failure this section's design replaces.)
* **≤`max_posts_per_day` live posts per UTC calendar day** is held by a
  per-day guard, not a slot count. A live post writes the
  `<!-- growth-twitter:posted -->` marker *claim-first* (exactly one per post —
  the closing comment carries only the header) and closes the item; the trusted
  Select step asks `tools/growth`'s tested `daycap` how many desk issues carry
  that marker dated today (UTC) — reading via the REST list + comments (not the
  eventually-consistent Search API) — and holds once the count reaches the cap.
  The workflow's `concurrency` group serializes its own runs, so a later
  same-day firing sees the earlier run's committed marker. The guard is keyed
  on the **live** marker only, so a dry-run never consumes a slot. **Changing
  the cap** is a reviewed one-line diff to `max_posts_per_day` in
  `.github/growth-twitter.conf` that you PR and merge (or a future
  `/growth-twitter set` comment command); nothing in the agent path can change
  it.

  > **Author identity — the bug this design originally carried.** The guard
  > only counts a marker from the posting identity (an outsider commenting the
  > marker string on a public queue issue must not suppress or, with a count,
  > mis-tally a day). GitHub names the Actions bot two ways: the REST API's
  > `user.login` is `github-actions[bot]`, but the GraphQL `author.login` that
  > `gh issue view --json comments` returns (what the Select step reads) is
  > `github-actions`, with no `[bot]` suffix. An early hardening trusted the
  > REST spelling literally, so the guard rejected its *own* posting tool's
  > markers and never held — the daily cap was silently disabled, and it
  > slipped through because the unit test fed the REST spelling the live scan
  > never produces. `daycap` now normalizes both spellings (stripping a
  > trailing `[bot]`); the DoS guard is unweakened, because GitHub reserves the
  > real bot names so no human can register one that normalizes to the poster.
* The post **time** varies day to day for free — it is whatever hour GitHub
  delivered the day's first firing, which the run history shows is wide and
  unpredictable. That delivery jitter is the "not a robotic drumbeat", with no
  computed pick and no new persistent state.

Everything above is orthogonal to the safety rungs: dry-run stays the default
and the arming ladder is untouched.

## Dry runs, and the accelerated timeline

Two dry-run forms, both designed to be read:

* **Per item** — an armed-but-not-live drain leaves the would-be tweet as a
  comment on the queue issue (marker `<!-- growth-twitter:dry-run -->`),
  with the weighted length and exactly what going live still needs. That
  comment is the approval artifact.
* **Accelerated** — `python3 -m growth simulate` walks N days of the
  committed cadence over a queue snapshot plus composed copy and writes the
  would-have-been feed to `growth/<channel>/dryruns/<stamp>.md` (+ ndjson):
  what would have been posted, when, in drain order, before the routine has
  ever fired. Copy over the weighted 280 fails the simulation loudly — a dry
  run that renders an unpostable tweet is a lie.

## Reeve-growth — the generative front (scheduled PM queueing)

The queue has two ends. Lark *drains* it; **Reeve-growth** (`/reeve-growth`,
`.github/workflows/reeve-growth.yml`) *fills* it — the "Scheduled PM queueing"
the Future work below named, now built. On a daily cadence Reeve (the
platform PM) reads the committed signals — `CLAUDE.md`, `docs/`, the design
catalog and its `NOTES.md` field-test logs — and files `growth-queue` +
`channel:twitter` issues proposing forward-looking posts: a platform feature
and how to use it, a design's unique technique, a pattern the bench
established. It is the growth sibling of `/product-scout`: the scout
originates *designs*, this originates *posts about the platform and its
designs*.

It reuses the desk's machinery rather than adding any:

* **One write, the shared queue tool.** Reeve-growth mounts the SAME
  `queue_growth_post` server (`mcp__growth_queue`) the attended `/growth-queue`
  skill uses — it gets no second filing surface, and so inherits every
  queue-tool guard: the hardcoded `growth-queue` + `channel:twitter` labels
  (it can never approve, prioritize, or route), the `Growth post:` title
  prefix, the closed channel set, and the `GROWTHQ_MAX_POSTS` per-run cap.
* **It queues intent, never copy.** A filed item carries the message angle +
  a fact budget cited to committed files — never the finished tweet. Lark
  writes the words from those facts. The queue seam keeps finished copy off
  both PMs' desks.
* **It can never reach a channel — the backstop inversion.** Its deny backstop
  (`.claude/reeve-growth-settings.json`) is the mirror of Lark's: where Lark
  *owns* the poster and *denies* the queue server, Reeve-growth *owns* the
  queue server and *denies* the poster (`mcp__growth_twitter`).
  `scripts/reeve-growth-perms-check.sh` pins that inversion (no-wrapper
  coverage of every Bash allow + every sibling surface + the poster, with the
  queue tool asserted never-denied), and it is the one exception to "every
  sibling denies both growth servers".
* **Oracle-shaped.** No shell wrapper: reads are Read/Grep/Glob over the
  checkout plus a trusted workflow-assembled `.reeve-growth-context/` (the open
  queue, for dedup). The run allow-lists exactly the queue tool + the read-only
  file tools.

**Dry-run-first, and disarmed.** Everything Reeve-growth files is a *draft*: a
human reads and culls the queue issue, Lark then dry-runs it, and it still
needs the human `approved-to-post` label before a live post — so there is no
path from this routine to a tweet without a human. It ships **disarmed** under
the two-key model: committed `enabled: true` in `.github/reeve-growth.conf`,
but the `REEVE_GROWTH_ENABLED` repo variable unset. Arming the *queue
generation* is independent of Lark's live rungs: `gh variable set
REEVE_GROWTH_ENABLED --body true`, then read the queue issues it files before
approving any of them for Lark. Model from the `reeve-growth` registry chain
(a GLM head, then the Anthropic tail, walked across providers since #544);
cadence parity is `cadence-sync-check.sh`-covered.

## Failure modes and what handles each

| Failure | Handled by |
|---|---|
| A prompt-injected queue item steers the agent | The item is DATA (the context banner); the agent's only write is `post_tweet`; the tool re-reads state, binds to the trusted candidate set, hardcodes markers, applies no labels — at worst the item's own copy is bad, which a human reads before it can go live |
| The agent invents a fact, number, or link | The skill's fact-budget rule; the dry-run comment surfaces the copy for review before approval; the Link is the queue item's, verbatim |
| A post goes out twice | The claim-first marker: the `posted` marker is written on the issue BEFORE the first tweet, so a *mid-thread* or bookkeeping failure keeps it and loses at most one post a human retries deliberately — never a channel duplicate; all comment pages are walked |
| A rejected post strands the item behind a false claim | The complement of claim-first: a **first-tweet** rejection published nothing, so the tool **withdraws** the claim and records the reason — the `⚠️ Growth post failed` comment carries X's actual error body (`poster.py` reads it instead of swallowing the HTTP status), and the item stays retryable rather than frozen until a human hand-deletes a marker (the credits-depleted 402 lesson) |
| Over-long copy burns an approval at the API | The weighted-length guard refuses at compose review time (tool + simulator), parity-pinned against the reference rule |
| The poster refills its own queue | Its backstop denies `mcp__growth_queue` (pinned by `growth-perms-check.sh` with a negative control); the reverse — the queuer reaching the channel — is closed the same way: `reeve-growth`, the one scheduled routine that *owns* the queue server, denies the poster `mcp__growth_twitter`, pinned by `reeve-growth-perms-check.sh` with its own negative control. Every *other* sibling backstop denies **both** growth servers |
| A sibling routine acquires either growth surface | Every sibling backstop denies both servers — except the two owners, Lark (denies the queue server) and `reeve-growth` (denies the poster); each perms-check pins the denies in `REQUIRED_DENIES` and asserts the owner's one write surface is never denied |
| The labeler sweeps a queue item (parking it `needs-decision`, or arming it `autonomy-ok` for the burn) | `growth-queue` is in the labeler's `NON_TRIAGE_LABELS` (label-helper.sh) — the sweep never selects a queue item, the agent-brief precedent |
| The routine silently stops (or silently starts) | Two-key arming + the `disarmed-notice` job; a disabled conf logs; an empty queue logs; Reeve's `routine-dead` detector reads run conclusions once armed |
| A dead model id kills the sweep | The chain walks past it since #544: a dead GLM head falls through to the Anthropic tail (`claude-sonnet-5` → `claude-haiku-4-5`), and total exhaustion runs `provider-triage` → `classify`, escalating a human-fixable cause (billing, a bad key) once through the `needs-decision` gate instead of a silent red; `model-registry smoke growth-twitter` proves every link before arming |
| A hijacked run floods the channel | `GROWTH_MAX_POSTS` (default 1) per run, in-process, unreachable by the agent; live posts additionally need per-item labels no agent can apply |
| The feed reads robotic (every post at the same clock minute) | The post time is whatever hour GitHub delivers the day's first firing — heavily and variably delayed by GitHub's own scheduler (observed 21:55 / 19:31 / 00:39 on consecutive days), so it walks widely on its own (above) |
| More posts than the cap land on the same day (GitHub delivers 2+ firings, or a re-run) | The per-UTC-day cap: `daycap` (tested) counts today's live `posted` markers and holds the drain once the count reaches `max_posts_per_day`; runs serialize via the `concurrency` group, and each marker is written claim-first, so a later same-day run always sees the earlier ones (and the scan fails closed — a transient API error holds the drain rather than posting again). The count matches the poster across the bot's REST/GraphQL login spellings (`[bot]`-suffix normalization), so it recognizes its own markers. `max_posts_per_run` still caps each run |
| GitHub drops all of a day's firings | 0 posts that day; the queue is durable, so it drains next day. The five slots are delivery redundancy precisely to make this rare |

## Arming it (the morning-after checklist)

1. Merge the desk. CI green means: tools/growth pytest, both MCP selftests,
   `growth-perms-check.sh` (+ the widened oracle/wright checks), cadence
   parity, docs drift — all proven.
2. Read the committed accelerated timeline under `growth/twitter/dryruns/`
   — that is the feed being signed up for.
3. `gh variable set GROWTH_TWITTER_ENABLED --body true` → the routine runs
   daily, dry-run comments only. Watch a sweep or two.
4. Add the four X secrets (`gh secret set X_API_KEY` …), then
   `gh variable set GROWTH_TWITTER_LIVE --body true`. Optionally dispatch
   `model-smoke.yml` on the `growth-twitter` chain first.
5. Approve items one at a time: read the dry-run comment on a queue issue,
   apply `approved-to-post`, let the next sweep post it. Un-label or close
   to veto; `needs-decision` parks an item indefinitely. The **approval
   board** (below) is the surface built for this step — every pending post in
   one view, approved by applying the label from the card.
6. To stop everything instantly: unset `GROWTH_TWITTER_ENABLED` (or
   `GROWTH_TWITTER_LIVE` to fall back to dry-runs).

## The approval board (GitHub Projects)

The queue is issues; the board is the **view a human approves from** — a
GitHub Project (v2), `print-bench growth`, where each stageable `growth-queue`
issue is a card grouped by its Stage. It answers "where is each post, and which
are waiting on me?" without scrolling the issue list. (A closed `growth-queue`
issue with no posted marker — one a human rejected — has no Stage, so it is
excluded rather than shown.) It is the exact sibling of
the autonomy roadmap board (`docs/roadmap-board.md`): the schema lives in git
and the board is provisioned by a committed, idempotent `gh` recipe, because
this session's automation cannot create or populate a Projects v2 board (the
API is GraphQL-only and unavailable here, and a Project is settings-shaped
anyway).

**The board is a LENS, not a control surface.** Each card's Stage is
*derived* from its issue's real state by one tested pure function
(`growth.board.stage_of` in `tools/growth`), not set by hand:

| Stage | The issue state it reflects |
|---|---|
| **Queued** | open `growth-queue`, no dry-run yet — filed, awaiting Lark |
| **Drafted** | open, carries the `<!-- growth-twitter:dry-run -->` comment — **awaiting your approval** |
| **Approved** | open, carries the `approved-to-post` label — awaiting the next live sweep |
| **Posted** | closed with the `<!-- growth-twitter:posted -->` marker — published |
| **Parked** | open, `needs-decision` — a human paused it |
| **Attention** | open with a posted marker that never closed — a mid-thread/in-flight post to check |

Because the Stage is derived, **approving a post is still applying the
`approved-to-post` label** — the very label Lark's posting tool reads — now
doable from the card's side panel where you see every pending post at once.
**Dragging a card does nothing to the post**: it changes only the board's own
Stage field, not the label, and the next reconcile re-derives Stage from the
real state anyway. This is the deliberate difference from the roadmap board,
whose Stage is human-owned (a card a person drags, so its sync sets Stage
only when the item is first added). The growth board's Stage is a reflection,
so its sync always re-sets it.

**Provisioning + wiring.**

- Create the board once: `scripts/gh-project.sh --board growth setup | bash`
  (needs `gh` + the `project` scope). Then, one-time in the UI, group the
  Board view by `Stage` and — optionally — filter by the `channel:twitter`
  label. View layout is UI-only, as on the roadmap board.
- `.github/workflows/growth-board-sync.yml` reflects each queue issue's
  derived Stage onto the board: on `issues` events (the approve/park/close
  transitions land immediately) and every three hours (to catch Lark's
  once-daily dry-run as a Drafted card). It is **gated on the same
  `PROJECT_TOKEN`** the roadmap board uses — one Projects-scoped PAT covers
  every board under this owner — and is a no-op until that secret is set, so
  merging the desk provisions nothing on its own.

The board adds **no new write to any issue**: the sync only reads the queue
(labels + comment markers) and writes the Project. The posting tool still
applies no labels, and `growth-queue` stays in the labeler's
`NON_TRIAGE_LABELS` — the board is a reflection of the queue, never a second
source of truth for it.

## Relationship to earlier decisions

The desk composes the house patterns rather than inventing new machinery:
labeled-issue queues with a template/form pair (design-brief, #96), the
scout/assessor MCP-write + trusted-Select harness, the oracle's
no-wrapper/context-assembly shape (#333), two-key arming shipped disarmed
(every routine since the burn), the #206 registry chain, cadence parity
(#276), and the deny-backstop web with per-routine perms-checks
(docs/actions-security.md, CR-A). The one genuinely new element — the
channel-credential rung and per-item approval label — exists because this is
the bench's first write surface that can leave GitHub, and N3 ("the human
lead stays primary") has to survive that step.

## Future work (deliberately not in v1)

* **The YouTube agent** — the queue already accepts `channel:youtube`
  (reserved in the filing tool); the agent, its skill, its credentials rung,
  and its form arrive as their own routine when the content-creation skills
  exist. Nothing in v1 needs changing to add it.
* **Scheduled PM queueing — BUILT** (see the *Reeve-growth* section above).
  Reeve's `/reeve-growth` routine wires the queue server into a scheduled
  sibling exactly as this bullet anticipated — its own deny backstop
  (`.claude/reeve-growth-settings.json`, the mirror of Lark's) allows the queue
  tool and denies the poster, pinned by `reeve-growth-perms-check.sh`.
  Extending the same shape to Vera (per-design, from a design's `PM.md`) or to
  Remy is a follow-up: a new conf + workflow + registry chain pointed at the
  same queue server, when wanted.
* **Growth telemetry** — reading back post performance into `telemetry/` so
  queue priorities can be data-driven (the #93 pattern), and a ledger of
  live posts beyond the issue threads.
* **Media** — product shots / animation GIFs attached to posts (the tier-1
  artifacts are already committed and disclosed; attaching them is an X API
  media-upload feature with its own review questions).
