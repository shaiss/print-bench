# Member avatars

One SVG per `people/<handle>.md` member, generated with
[DiceBear](https://www.dicebear.com/) — curated people-like styles for
humans, machine-like for agents (the sets live in `site/lib/avatars.mjs`),
rendered grayscale and square on the page ground. Each file embeds its own
Dublin Core metadata block naming the artwork, its creator and its license —
the provenance ships inside the asset.

Committed rather than fetched: the served output references nothing
external, and the build performs no network I/O. The member's
`people/<handle>.md` header is the one authority — optional `avatar-style:`
and `avatar-seed:` keys, defaulting to notionists/bottts seeded by first
name — and these SVGs are derived from it:

```bash
npm --prefix site run avatars          # regenerate every member's SVG
node site/avatars.mjs --set <handle> [--style <style>] [--seed <seed>]
                                       # update a member's header, then regenerate
```

`site/test/avatars.test.mjs` regenerates each committed SVG from its header
and fails on any byte difference, so a header change cannot leave a stale
face behind. The *Regenerate avatar* Action (`.github/workflows/avatar.yml`)
runs the `--set` mode and opens a draft PR; the browser avatar studio on
`/people/` explores styles and seeds locally before anything is committed.

A member without an SVG here is fine — profiles fall back to the initials
monogram (`site/lib/team.mjs` only marks `avatar` when the file exists).
