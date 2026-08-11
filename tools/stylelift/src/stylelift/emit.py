"""Write a style pack: style.json, style.scad, and a STYLE.md draft.

The pack is the committed artifact. style.json is the source of truth,
style.scad is generated from it so a design's geometry and the checker can
never disagree about what "the family's corner radius" is, and STYLE.md is the
page a human or an agent reads before modelling.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .measure import measure
from .spec import StyleSpec, derive

# Tokens that become OpenSCAD variables: the numbers somebody types into
# geometry. Ratios and targets stay in style.json, where the checker reads them.
# Tokens stylelift proposes itself, with the wording for their comment. A pack
# may define others by hand — different families have different vocabularies,
# and a ribbed family needs words a rounded-box family does not — so this is
# the annotation table, not the permitted set.
SCAD_TOKENS = (
    ("corner_r", "mm", "radius of the family's rounded edges"),
    ("edge_chamfer", "mm", "leg length of the family's chamfers"),
    ("wall", "mm", "material thickness the family builds at"),
    ("hole_d", "mm", "the family's fastener clearance hole"),
    ("fn", "segments", "curve resolution ($fn) the family draws at"),
)

# Tokens that exist so a rule has something to compare against, and that you
# would never build with. Kept out of style.scad: a design that wrote
# `softness = 0.79` into its geometry would be doing something meaningless.
CHECK_ONLY = frozenset({"softness", "bbox_fill", "grammar_rounded"})


def sha256(path: str | Path) -> str:
    """Content hash of a reference file, for provenance."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def render_tokens(spec: StyleSpec) -> str:
    """Render style.scad from a spec's tokens (generated, never hand-edited)."""
    lines = [
        f"// {spec.name} — style tokens.",
        "//",
        "// GENERATED from style.json by `stylelift sync "
        f"styles/{spec.name}` — edit style.json, not this file.",
        "// All dimensions in millimeters.",
        "//",
        "// Use from a design (OPENSCADPATH includes the repo root):",
        f"//     include <styles/{spec.name}/style.scad>",
        "//     $fn = style_fn;",
        # The third example line must only reference a token this pack
        # actually defines: a copied `style_corner_r` in a pack without one
        # resolves to undef and renders nothing, with only a warning.
        *(["//     rounded_box([w, d, h], r = style_corner_r);"]
          if "corner_r" in spec.tokens else []),
        "",
        f'style_name = "{spec.name}";',
    ]
    known = {k: (u, b) for k, u, b in SCAD_TOKENS}
    # Every token the pack defines reaches style.scad, in a stable order:
    # the ones stylelift knows about first, then the pack's own vocabulary.
    ordered = ([k for k, _, _ in SCAD_TOKENS if k in spec.tokens]
               + sorted(k for k in spec.tokens if k not in known))
    for key in ordered:
        if key in CHECK_ONLY:
            continue
        value = spec.tokens[key]
        text = f"{value:g}" if isinstance(value, (int, float)) else f'"{value}"'
        unit, blurb = known.get(key, ("", ""))
        comment = f"  // {unit} — {blurb}" if blurb else ""
        lines.append(f"style_{key} = {text};{comment}")
    missing = [k for k, _, _ in SCAD_TOKENS if k not in spec.tokens]
    if missing:
        lines += ["",
                  "// Not part of this style (the reference gave no evidence "
                  "for them): " + ", ".join(missing)]
    return "\n".join(lines) + "\n"


def _block(name: str, body: list[str]) -> str:
    """Wrap generated markdown in markers so `sync` can refresh it in place."""
    return "\n".join([f"<!-- stylelift:{name} -->", *body,
                      f"<!-- /stylelift:{name} -->"])


def _rules_table(spec: StyleSpec) -> list[str]:
    rows = ["| Rule | Requirement | Severity | Why |",
            "|---|---|---|---|"]
    for rule in spec.rules:
        op, value, tol = rule.get("op", "near"), rule["value"], rule.get("tol", 0)
        if op == "near":
            requirement = f"`{rule['metric']}` = {value:g} ±{tol:.0%}"
        elif op == "min":
            requirement = f"`{rule['metric']}` ≥ {value:g}"
        elif op == "max":
            requirement = f"`{rule['metric']}` ≤ {value:g}"
        else:
            requirement = f"`{rule['metric']}` in {value}"
        rows.append(f"| `{rule['id']}` | {requirement} | "
                    f"{rule.get('severity', 'required')} | {rule.get('why', '')} |")
    return rows


def _tokens_table(spec: StyleSpec) -> list[str]:
    rows = ["| Token | Value | What it is |", "|---|---|---|"]
    # Same numeric/string branch as render_tokens: a hand-edited style.json may
    # carry a string token, and a table that crashes on it would take the whole
    # style gate down over a documentation detail.
    def show(value) -> str:
        return f"{value:g}" if isinstance(value, (int, float)) else str(value)

    for key, unit, blurb in SCAD_TOKENS:
        if key in spec.tokens:
            rows.append(
                f"| `style_{key}` | {show(spec.tokens[key])} {unit} | {blurb} |")
    # The pack's own vocabulary. These reach style.scad exactly like the known
    # ones (unless they are check-only), so they must be named the same way
    # here — a table that showed `rib_pitch` while style.scad defined
    # `style_rib_pitch` would send a modeller looking for a variable that does
    # not exist.
    for key in sorted(k for k in spec.tokens if k not in {t[0] for t in SCAD_TOKENS}):
        value = show(spec.tokens[key])
        if key in CHECK_ONLY:
            rows.append(f"| `{key}` | {value} | target the checker compares "
                        "against, not a number you build with |")
        else:
            rows.append(f"| `style_{key}` | {value} | "
                        "defined by this style — see the prose below |")
    return rows


def _evidence_table(spec: StyleSpec) -> list[str]:
    m = spec.measured
    edges = m.get("edges", {})
    rounding, chamfers = edges.get("rounding", {}), edges.get("chamfers", {})
    grammar, massing = edges.get("grammar", {}), m.get("massing", {})
    rows = [
        "| Property | Reference |", "|---|---|",
        f"| Edge softness | {edges.get('softness', 0):.2f} "
        "(1.0 = every edge curves) |",
        f"| Edge grammar | rounded {grammar.get('rounded_share', 0):.0%} / "
        f"chamfered {grammar.get('chamfered_share', 0):.0%} / "
        f"sharp {grammar.get('sharp_share', 0):.0%} |",
    ]
    if rounding.get("convex"):
        vocab = ", ".join(f"{c['r_mm']:g} mm ({c['share']:.0%})"
                          for c in rounding["convex"][:3])
        rows.append(f"| Rounding vocabulary | {vocab} |")
    if edges.get("form", {}).get("dominant_r_mm"):
        rows.append("| Form curvature (the shape, not its edges) | "
                    f"{edges['form']['dominant_r_mm']:.3g} mm |")
    if chamfers.get("dominant_leg_mm"):
        rows.append(f"| Chamfer leg | {chamfers['dominant_leg_mm']:.3g} mm |")
    if massing.get("bbox_fill") is not None:
        rows.append(f"| Fills its bounding box | {massing['bbox_fill']:.0%} |")
    if m.get("walls", {}).get("shelled"):
        rows.append(f"| Wall thickness | {m['walls']['mode_mm']:.3g} mm |")
    for f in m.get("features", {}).get("cylinders", [])[:4]:
        rows.append(f"| Round feature | {f['count']} x {f['kind']} "
                    f"{f['d_mm']:.3g} mm diameter, {f['axis']} axis |")
    return rows


def render_style_md(spec: StyleSpec) -> str:
    """Render the STYLE.md draft — prose the lifting session then finishes."""
    refs = spec.provenance.get("reference", [])

    lines = [
        f"# {spec.title or spec.name}",
        "",
        spec.summary or "<!-- One or two sentences: what this style feels like "
                        "and what it is for. Written by the lifting session. -->",
        "",
        "<!-- Style spec drafted by `stylelift lift`. The measured tables below",
        "     come from the reference mesh; the prose and the do/don't list are",
        "     yours to write. See .claude/skills/style-spec/SKILL.md. -->",
        "",
        "## Where it comes from",
        "",
    ]
    if refs:
        for r in refs:
            lines.append(f"- `{r.get('file')}` — sha256 `{r.get('sha256', '')[:16]}…`")
            lines.append(f"  - source: {r.get('source', '<!-- URL or where it came from -->')}")
            lines.append(f"  - author / license: {r.get('license', '<!-- fill in before sharing -->')}")
    else:
        lines.append("<!-- reference mesh provenance -->")
    lines += [
        "",
        "The reference mesh itself is **not** committed unless its license "
        "allows redistribution — the hash above identifies it, and every number "
        "on this page was measured from it.",
        "",
        "## The rules",
        "",
        "What a new design must do to belong to this family. `stylelift check` "
        "enforces these against the design's exported STL; a rule whose "
        "precondition does not apply to a given part is skipped, not failed.",
        "",
    ]
    lines += [
        _block("rules", _rules_table(spec)),
        "",
        "## Tokens",
        "",
        "Numbers to build with. `include <styles/" + spec.name +
        "/style.scad>` and use these rather than retyping the values — a design "
        "written from the tokens passes the rules by construction.",
        "",
        _block("tokens", _tokens_table(spec)),
        "",
        "## Measured evidence",
        "",
        _block("evidence", _evidence_table(spec)),
    ]
    lines += [
        "",
        "## What the mesh cannot tell you",
        "",
        "Asserted by a human, not measured — fill these in, they are half of "
        "what makes a style recognisable:",
        "",
        "- **Material / colour:** <!-- e.g. matte PLA, single colour -->",
        "- **Finish:** <!-- e.g. layer lines left visible, no post-processing -->",
        "- **What it is for:** <!-- the kind of object this language suits -->",
        "- **Deliberate non-goals:** <!-- what this style refuses to do -->",
        "",
        "## Designing in this style",
        "",
        "```scad",
        f"include <styles/{spec.name}/style.scad>",
        "$fn = style_fn;",
        "```",
        "",
        "Then check the result before calling it done:",
        "",
        "```bash",
        f"stylelift check build/<part>.stl --style styles/{spec.name}",
        "```",
        "",
        "## Swatch",
        "",
        "`swatch.scad` is a small part written in this style. It is the "
        "style's own regression test: the gate renders it and checks it "
        "against the rules above, so a style that no design can satisfy "
        "fails loudly rather than sitting on the shelf being wrong.",
        "",
        "![Swatch](previews/swatch.png)",
        "",
    ]
    return "\n".join(lines)


def lift(references: list[str], name: str, out_dir: str | Path,
         title: str = "", summary: str = "", force: bool = False,
         source: str = "", license_note: str = "") -> dict:
    """Measure reference mesh(es) and write a style pack. Returns what changed."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "style.json"
    if json_path.exists() and not force:
        raise FileExistsError(
            f"{json_path} exists — rerun with --force to overwrite it "
            "(style.json carries hand-tuned rules; overwriting discards them)")

    # Multiple references: measure each, keep the first as the spec's evidence
    # and record the rest in provenance. Averaging measurements across meshes
    # would invent a design that does not exist, so we do not.
    measurements = [measure(r) for r in references]
    primary = measurements[0]
    tokens, rules = derive(primary, name)
    spec = StyleSpec(
        name=name, title=title, summary=summary, tokens=tokens, rules=rules,
        provenance={
            # Where the reference came from and what it is licensed as belongs
            # here, not in someone's memory: a style is measured from another
            # person's work often enough that "which model was this?" has to be
            # answerable months later.
            "reference": [{"file": Path(r).name, "sha256": sha256(r),
                           "source": source, "license": license_note}
                          for r in references],
            "lifted_by": "stylelift",
            "primary": Path(references[0]).name,
        },
        measured=primary,
    )
    if len(measurements) > 1:
        spec.provenance["others_measured"] = [
            {"file": Path(r).name, "softness": m["edges"].get("softness"),
             "dominant_r_mm": m["edges"]["rounding"].get("dominant_r_mm")}
            for r, m in zip(references[1:], measurements[1:])]

    json_path.write_text(spec.to_json() + "\n")
    (out / "style.scad").write_text(render_tokens(spec))
    written = ["style.json", "style.scad"]
    md_path = out / "STYLE.md"
    if not md_path.exists() or force:
        md_path.write_text(render_style_md(spec))
        written.append("STYLE.md")
    return {"dir": str(out), "written": written, "spec": spec}


def refresh_blocks(text: str, spec: StyleSpec) -> str:
    """Rewrite the generated tables inside STYLE.md, leaving the prose alone.

    The rules and tokens live in style.json, but they also have to be readable
    on the page somebody actually opens. Regenerating the tables in place is
    what stops a spec from *saying* 4 mm while *checking* 3 — the failure mode
    of every design guide that is maintained by retyping.
    """
    generators = {"rules": _rules_table, "tokens": _tokens_table,
                  "evidence": _evidence_table}
    for name, generate in generators.items():
        start, end = f"<!-- stylelift:{name} -->", f"<!-- /stylelift:{name} -->"
        i, j = text.find(start), text.find(end)
        if i < 0 or j < 0 or j < i:
            continue                       # block removed by hand: leave it out
        text = text[:i] + _block(name, generate(spec)) + text[j + len(end):]
    return text


def sync(style_dir: str | Path, check: bool = False) -> tuple[bool, str]:
    """Regenerate style.scad and STYLE.md's tables from style.json.

    With check=True nothing is written and stale output is reported instead —
    what CI runs, so a pack whose generated files were edited by hand (or left
    behind by a rule change) fails rather than quietly disagreeing with itself.
    """
    directory = Path(style_dir)
    spec = StyleSpec.load(directory / "style.json")
    targets = [(directory / "style.scad", render_tokens(spec))]
    md = directory / "STYLE.md"
    if md.exists():
        targets.append((md, refresh_blocks(md.read_text(), spec)))

    stale = [(path, wanted) for path, wanted in targets
             if (path.read_text() if path.exists() else "") != wanted]
    if not stale:
        return True, f"ok    {directory} generated files match style.json"
    if check:
        names = ", ".join(str(p) for p, _ in stale)
        return False, (f"FAIL  {names} is stale — regenerate with "
                       f"`stylelift sync {directory}`")
    for path, wanted in stale:
        path.write_text(wanted)
    return True, "wrote " + ", ".join(str(p) for p, _ in stale)
