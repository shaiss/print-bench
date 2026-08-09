# Derivative designs

A **derivative** reuses another design's geometry and replaces part of it:
keep sushi-battleship's tray, put a different lid on it. Both designs stay
current — the parent is unchanged, still rendered, still gated, still on the
gallery — and the derivative is a second design directory that `include`s the
parent's source and redefines the handful of modules it wants different.

The mechanism has always worked in OpenSCAD. What did not exist until
`tools/lineage` is any *record* of the relationship, any way to know what a
change to the parent has to re-gate, and any way to notice when an override
quietly did nothing. This note is the background for all three; the format
reference and the enforcement list live in
[`tools/lineage/README.md`](../tools/lineage/README.md).

## What a derivative is not

| You want | Reach for |
|---|---|
| the same design, one number different | a parameter — designs are parametric first, and a tuned fit gets a coupon, not a fork |
| the same design, two printable parts | a `part` value in one `.scad`, or `<name>-<part>.scad` beside the entry point (see CLAUDE.md, "Multi-part designs") |
| another design's tray under your own lid, both shipping | a derivative |

Two nearby things it is specifically not:

- **Not a new version.** A version supersedes what came before, and git
  history is where versions live. A derivative and its parent are
  contemporaries: both render, both gate, both ship, and a change to the
  parent is expected to move the derivative.
- **Not a new design.** A new design owns its geometry. A derivative owns
  only its delta — which is exactly why *copying* a parent's geometry into a
  fresh directory is the failure this apparatus argues against, not a
  shortcut to it. The copy stops tracking the original the moment either one
  moves, and nothing reports that it has.

The dividing line is the design-directory boundary. Inside one directory,
parts and variants are already solved; a derivative is what crosses to
another design's directory and builds on what is there.

## The mechanism

```openscad
// designs/deep-tray/deep-tray.scad
include <../sushi-battleship/sushi-battleship.scad>   // the parent, verbatim

tray_depth = 24;      // the parent shipped 16

module top() {        // the parent's assembly calls top() — from here it calls this one
    ...
}
```

`include` (not `use`) pastes the parent's source in, and a later definition of
a name wins over an earlier one. The part that makes this useful rather than
merely convenient is the routing: the parent's *own* call sites pick up the
redefinition. A `top()` inside the parent's assembly module renders your
`top()`, so a derivative never has to restate the assembly it is varying.

Everything below follows from two properties of that:

- **Order decides.** Later wins, so a redefinition must sit after the include
  — and with more than one parent, the last include is the one that supplies
  any name they share.
- **Nothing is announced.** Overriding an existing name and defining a brand
  new one are the same syntax. OpenSCAD has no notion of "this was meant to
  replace something", so it cannot tell you when it didn't.

## Four things OpenSCAD will not tell you

All four were measured in this repo's container on OpenSCAD 2021.01.

A fifth thing it will not tell you turns up as soon as you try to build the
gate, and it is documented under [Why the comparison is not a byte
comparison](#why-the-comparison-is-not-a-byte-comparison) below, because it is
the trap anyone re-implementing this will fall into.

### 1. A typo'd override is indistinguishable from a working one

Redefine `Lid` when the parent's module is `lid` and you get exit 0, no
WARNING, no ERROR, and a watertight STL that printcheck scores **100/100** —
of the base part you were trying to replace, shipped under the derivative's
name. Every downstream check agrees it is fine, and by their standards it is:
it is the parent's part, and the parent's part passes.

That is worse than an error and worse than nothing, because the design
renders, slices and prints. Without a gate, the first thing that tells you is
the part in your hand.

### 2. …but the mesh gives it away

A missed override renders **the parent's mesh**. Measured: base and typo'd
derivative both hashed to `cbd9c564b14e799f…`, where a real override hashed
differently.

That difference is the only observable evidence anywhere in the toolchain that
an override took, which is the whole design of the render gate: export the
derivative's part and the parent's part, compare the meshes, and read
"identical" as failure. `replaces:` exists to name which comparisons to make.

"The only evidence" is meant literally, and the obvious alternative was tried
first: **you cannot assert your way to this answer from inside OpenSCAD.**
Modules are not visible to the expression language at all — `is_undef()`
reports a module that plainly exists as undefined:

```openscad
module lid() { cube([10, 10, 2]); }
echo(is_undef(lid));            // -> true   (it is defined!)
echo(is_undef(never_defined));  // -> true
```

There is no `is_module()`, and no introspection of any kind, so a canary
`assert()` inside a derivative cannot tell "my redefinition bound" from "my
redefinition bound nothing" — the two cases are identical to every expression
you could write. Comparing the exported geometry is not the preferred option;
it is the only one.

#### Why the comparison is not a byte comparison

The obvious implementation — `sha256sum` the exported file — is wrong, and it
fails in the direction that hides the bug rather than the direction that
annoys you.

OpenSCAD 2021.01 writes the same mesh's facets in a **different order**
between renders of unchanged source. Measured on this repo's
`sushi-battleship`, `part=top`, rendered twice with nothing edited in between:

| | render 1 | render 2 |
|---|---|---|
| facet count | 24256 | 24256 |
| file size | 1 212 884 | 1 212 884 |
| differing bytes | — | **3248** |
| sorted triangle list | *identical* | *identical* |

The geometry is the same both times; only the write order moved. So a byte
hash reports "these differ" for two renders of the same thing — and in the
override check that means the derivative *always* looks different from its
parent. The gate passes unconditionally, guarding the one failure that already
looks like success.

Small models — a cube, a cylinder — do reproduce byte for byte, which is why
this is easy to miss: a byte hash looks sound on exactly the toy cases you
would test it with, then silently stops working on every real design.

`lineage mesh-hash` therefore canonicalises first: parse the facets, normalise
`-0.0` to `0.0`, sort the triangles, hash that. Per-facet normals are ignored
(they are derived from the vertices) and so is the 80-byte header (OpenSCAD's
banner, not geometry). A unit test shuffles a mesh's facet order and asserts
the hash does not move, so the property is pinned rather than hoped for.

### 3. With two parents, the last include wins — silently

Two parents both defining `lid()`: swapping the two `include` lines changed
the exported mesh from **12 facets to 72**, different hashes, zero
diagnostics. Include order is load-bearing and invisible, which is why
derives.conf's parent order has to match the entry `.scad`'s include order and
why `lineage check` compares the two lists as sequences, not as sets.

### 4. `include` is not guarded, so a diamond evaluates its ancestor twice

Echo-counted: a single parent fired the shared base's echo **1×**, a diamond —
two parents that both include the same ancestor — fired it **2×**. Whatever
that ancestor's top level draws is drawn twice, and the duplicate unions
cleanly: one body, watertight, printcheck 100/100. Nothing downstream can see
it. See [base-safety](#base-safety) below.

## The record: `designs/<name>/derives.conf`

House style, same as `ci.parts` / `printcheck.args` / `style.conf`:
line-oriented, `#` comments, blank lines ignored, `key: value`, values
comma-separated. Start from [`templates/derives.conf`](../templates/derives.conf),
which ships every key empty and annotated.

```
# Parents in include order. LAST WINS on any module both define.
variant-of:    sushi-battleship
derivative-of:
replaces:      sushi-battleship:top, sushi-battleship:door
```

| Key | Meaning |
|---|---|
| `variant-of` | Open Know-How "variant-of". Comma-separated parent design names. |
| `derivative-of` | OKH "derivative-of". Same shape; the tooling treats the two identically, so the choice is documentation for humans. |
| `replaces` | Parent-qualified `<parent>:<part>` entries — the parent `ci.parts` values this design claims to change. An empty part (`parent:`) means the parent's default render. |
| `diamond-ok` | Comma-separated ancestor names: an explicit, auditable "I know this creates a diamond on `<ancestor>`, and `<ancestor>` is base-safe". A signature, not a suppression — the render gate then proves the claim. |

Anything else is an error, including `reuses:`, an early draft key that named
the parts a derivative inherited unchanged so the gate could skip them.
Everything is gated now; nothing is assumed inherited, because "inherited" is
precisely the assumption a silent override failure breaks.

The **combined ordered parent list** is every parent-bearing line in file
order, left to right within a line — so two keys read top to bottom as
written.

The obvious alternative — skip the file, read the parents off the include
lines — fails at both jobs the record has. An included-but-undeclared parent
is exactly the drift worth reporting, and a record inferred from the thing it
is checking can never report it; and `replaces:` and `diamond-ok:` are claims
no source line expresses. The file is what turns silence into something that
can be wrong out loud.

## What is checked, and where

| Check | Where | What it catches |
|---|---|---|
| `lineage check` | `scripts/check.sh`, every run | Static faults: unknown or retired keys, duplicate keys, a parent that is not a design, self-reference, cycles, a `replaces` part the parent does not have, declaration-vs-include drift **including order**, any diamond that is not explicitly asserted, and a `ci.parts` that does not cover its parents' (which would leave inherited parts ungated). |
| derivative render gate | `scripts/gate.sh`, per design shipping a derives.conf | Renders each `replaces:` part from the derivative and from the parent with the same `-D part=`, compares facet-payload hashes, and fails on identical — the signature from silence #2. Fails first if the derivative renders **nothing** for a part it claims — an empty mesh is trivially unequal to the parent's, so folding that into "differs" would pass a part that went missing. Then renders each `diamond-ok:` ancestor in **every configuration it can ship in** — its default render and each of its `ci.parts` values — and requires zero facets from all of them, because a diamond doubles whatever a `-D part=` draws, not just the default. |
| `./scripts/lineage.sh selftest` | CI's render gate, before the gate itself | That the comparison still separates a working override from a typo'd one *on the OpenSCAD actually installed*. A gate that has silently stopped firing looks exactly like a gate with nothing to report. |
| blast radius | CI's classifier job, via `lineage blast-radius` | A change under `designs/<parent>/` re-gates every transitive descendant, whose geometry moved without the diff naming a file in its directory. A change under `tools/lineage/` counts as infra and gates everything, since it can move every blast radius including the one being computed. |
| product-page link | `scripts/readme-gate.sh` | A derivative whose README does not link each parent's directory. |
| gallery nesting | `scripts/gallery.sh` | Rows come from `lineage order`, so a derivative nests under its parent with a `↳` and names every parent in include order instead of reading as an independent design. |

`lineage check` runs unconditionally, including on a tree with no derives.conf
anywhere — it answers in one line, and the day someone adds the first
derivative the check is already wired in rather than waiting to be remembered.

### The product page

A derivative's `README.md` is still a product page and still needs everything
`readme-gate.sh` requires of one, but its content is the **delta plus a link to
the base**: what differs, why, which print settings and parameters changed —
and the parent's directory linked for everything that did not. Restating the
parent's page is how the two drift apart. The link is gated (sibling-relative
`../<parent>`, `../<parent>/` or `../<parent>/README.md`, as a markdown or
HTML anchor) because it is the only durable form the lineage takes for a human
reader.

Licensing needs no extra ceremony: first-party content here is CC BY-SA 4.0
(see [`LICENSE`](../LICENSE); vendored third-party code such as BOSL2 keeps its
own terms), so under ShareAlike a derivative must carry the same terms as its
parent. The README link records the lineage for a human reader, but the
attribution itself follows the LICENSE — credit, a license link, and a statement
of what changed (Section 3(a)).

## Base-safety

A design is **base-safe** — safe to sit at the confluence of a diamond — only
if its top level *defines* modules and *emits* no geometry: everything it
draws lives inside a module, and rendering the entry point produces zero
facets. Only then is silence #4 harmless, because evaluating the ancestor
twice draws nothing twice.

**No design in this repo qualifies today.** Every entry point ends by drawing
something, which is what makes `render.sh <name>` produce a preview at all.

That constrains almost nothing right now:

- **Single-parent derivatives are unaffected** — one parent cannot form a
  diamond.
- **Multi-parent derivatives are unaffected** as long as their parents share
  no ancestor.
- Only an actual confluence — two of your parents reaching the same ancestor —
  needs `diamond-ok:`, and `lineage check` fails a diamond by default until
  one is written, naming both paths.

If you reach one, the fix is to make the ancestor base-safe: split its entry
point into a geometry-free module library plus a thin dispatcher that calls
it, then re-assert `diamond-ok:`. Adding the line without doing the work does
not get past the gate — it renders the ancestor and counts facets.

## Prior art, and the lesson

The vocabulary is not invented here. **Open Know-How v1** — the hardware
documentation manifest standard — already carries `derivative-of` and
`variant-of`, so a derives.conf reads as OKH metadata rather than as a
repo-local dialect, and both keys are accepted for that reason alone.
The tooling treats them identically; which one describes the relationship
better is a judgement for the human writing it.

The cautionary tale is the **Thingiverse/Printables remix link**. Both
platforms model lineage properly and both surface it well — a remix names its
original, and originals list what was made from them. The flaw is *where the
record lives*: in a gesture at creation time, a field in the upload form. Skip
it and the model publishes anyway, indistinguishable from an original; nobody
downstream can tell, and nobody but the uploader can repair it. Whole families
of prints are now unattributable for want of one field nobody was required to
fill in.

So the lineage here is a **file in the repo, gated like any other claim**. It
cannot be skipped at creation time — `lineage check` fails a design that
includes another design's entry `.scad` without declaring it — and if it is
ever wrong, anyone can fix it in a pull request, which is the property the
platforms lack.

## Limitations

Stated plainly, because each of these is a place where the machinery is
weaker than it looks:

- **Whether `openscad-nightly` emits a *diagnostic* is still unasserted.** All
  four measurements above are from OpenSCAD 2021.01; the nightly (Manifold
  backend) build could not be installed in the container that made them — the
  egress proxy returns 403 for the OBS nightly repo.

  What CI does establish on every run that gates designs: `./scripts/lineage.sh
  selftest` executes in the `render-gate` job under
  `OPENSCAD_BIN=openscad-nightly OPENSCAD_ARGS=--backend=manifold`, before the
  gate and blocking, and it passes. `render-gate` is conditional, so a PR that
  gates nothing re-proves nothing. On nightly+Manifold a real override still changes the mesh, a
  typo'd override still reproduces the base's mesh exactly, and a geometry-free
  entry point is still distinguishable from one that emits geometry. The
  behaviours the gate is built on hold there.

  What it does *not* check is whether nightly prints a warning nobody is
  reading. If it turns out it does, this could be simplified — the mesh
  comparison would become a backstop for a diagnostic rather than the only
  evidence there is. Until someone checks, design for the silence.
- **An override that legitimately reproduces the parent's mesh fails the
  gate.** The signature is "identical to the parent", and a redefinition that
  happens to render the same geometry is indistinguishable from one that never
  bound. Rare, but if you meet it the honest fix is to stop claiming that part
  in `replaces:` — it replaces nothing observable.
- **Only what `replaces:` names is proven.** An override you did not write
  down is ungated, and the gate has no way to discover the ones you meant.
- **Base-safety is proven on the ancestor's default render.** It is a claim
  about the entry point with no `-D part=`, which is also the render
  `render.sh` uses for previews — so a design made base-safe has no default
  preview render until its previews are driven from `cameras.conf` or its
  parts. That tension is real and unresolved, and it is the main reason no
  design here has been converted yet.
- **Lineage edges are include lines, read as text.** `lineage check` compares
  the declared parents against the parent entry `.scad` files the entry point
  includes (comments stripped). A parent reached some other way — a wrapper
  file, a symlink, generated source — is not an edge the resolver can see.
