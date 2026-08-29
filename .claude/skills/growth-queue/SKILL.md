---
name: growth-queue
description: Queue a message to a growth agent — file ONE growth-post issue (the PM's intent, link, and fact budget) for a channel agent like Lark (/growth-twitter) to drain on its schedule. It queues; it never writes the copy, never posts to the channel, never approves. Use when a PM or the user wants something announced, promoted, or shared, or when invoked as /growth-queue [message].
---

# Growth queue — a PM queues, a channel agent posts

The write half of the growth desk's queuing seam (docs/growth.md): a product
manager — Vera on a design, Reeve on the platform, Remy scouting, or the
human lead — decides *something is worth saying* and queues it; the
channel-specific growth agent (Lark, `/growth-twitter`, for Twitter/X)
drains the queue on its own cadence and writes the channel-native copy. The
queue is the boundary between owning the message and owning the channel:
you hand over intent and a fact budget, never finished copy.

## The one boundary you may never cross

You **queue**; you never touch the channel. Three refusals, enforced by the
filing tool, not just this prompt:

- **Never write the post.** The Message section is intent — the channel
  agent owns phrasing, hashtags, thread structure, channel best practice.
- **Never invent the fact budget.** Every claim in Facts & sources must cite
  a committed file, issue, or PR you actually read this session. The channel
  agent composes ONLY from what you hand it; an uncited claim is a claim the
  post can never make.
- **Never approve or post.** Live posting is gated separately (the
  `approved-to-post` label, applied by a human) — filing a queue item grants
  nothing. You cannot apply that label; the tool has no label argument.

## The write surface — one MCP tool

Filing goes through the MCP tool **`queue_growth_post`** (a real tool, not a
shell command). Call it with `channel` (`twitter` or `youtube`), `title`
(must start with `Growth post: `) and `body` (the full markdown matching
`templates/growth-post.md`, section for section). Because the body travels
as a JSON argument and never touches a shell command line, it can carry
tables, pipes, and newlines. The tool hardcodes the `growth-queue` +
`channel:<name>` labels — it can apply no other — and caps filings per scheduled run (attended, the human in the loop is the trust boundary — the house posture).
You **MUST actually call the tool** for each message: writing a queue item
in your reply queues nothing.

## Run this — the exact procedure

1. **Settle the message.** From the request (or the PM charter you are
   currently enforcing): what is the announcement, who cares, which channel.
   One message per channel — a cross-post is two queue items.
2. **Gather the fact budget.** Read the committed files that prove each
   claim (Read/Grep/Glob) and note the path per fact. A number you did not
   read in the tree does not go in the budget. Pick the ONE canonical link.
3. **Compose the body** against `templates/growth-post.md`, section for
   section: Channel, Message, Link, Facts & sources, Timing & priority.
4. **File it**: `queue_growth_post({ channel, title: "Growth post: <slug>",
   body })`. For a `priority: high` item, say so in Timing & priority — and
   note in your reply that a human should add the `priority:high` label (the
   tool deliberately cannot).
5. **Report** the filed issue number(s) and what would make the item
   postable (the `approved-to-post` label, once a human reviews the dry-run
   comment the channel agent will leave).
