<!-- The growth-post format — the input contract of the growth desk
     (docs/growth.md). This is the shape /growth-queue files and the
     .github/ISSUE_TEMPLATE/growth-post.yml issue form collects; the section
     headings here and that form's field labels must stay identical (the
     design-brief pair's discipline — the fourth stay-identical pair). The
     message becomes the BODY of an issue titled "Growth post: <slug>" and
     labeled `growth-queue` + `channel:<name>`; the matching channel agent
     (Lark, /growth-twitter, for twitter) drains it on its schedule. A queued
     message is the PM's INTENT — what is worth saying and why it is true —
     never the finished copy: the channel agent owns the channel-native
     phrasing, and the posting tool refuses copy whose claims it was not
     handed facts for. Everything the post may claim must be in Facts &
     sources, each cited to a committed file, issue, or PR — the channel
     agent may not invent a fact, a number, or a link. Delete these
     comments. -->

## Channel

One word — which channel agent this message is for: `twitter` (Lark) or
`youtube` (reserved; no agent drains it yet). The channel decides who picks
it up, so a message wanted on two channels is two queue items.

## Message

What to announce, in the PM's words — the intent, the angle, who should
care. Not the finished copy: the channel agent writes that, in the channel's
native shape, from this section plus the facts below.

## Link

The one canonical URL the post should send readers to (the repo, a design's
directory, a PR, an issue). It must already exist and resolve — the channel
agent links only what it is handed here.

## Facts & sources

The claims the post may make, one per line, each cited to a committed file,
issue, or PR (`path`, `#123`). This is the whole fact budget: the channel
agent composes from these and the repo's own committed text, and may not
add a claim, a number, or a superlative that is not covered here.

## Timing & priority

`priority: normal` or `priority: high` (high jumps the FIFO queue — apply
the `priority:high` label too when filing by hand), plus any
earliest-post-date constraint, stated as a date. An empty section means
normal priority, post whenever the schedule reaches it.
