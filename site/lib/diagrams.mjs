// Inline SVG diagrams for the "How it works" page.
//
// Authored markup, like the favicon and the avatars — not fetched, not a
// runtime. Every colour is a CSS token (see the `.diagram` block in site.css),
// so the diagrams theme light/dark with the rest of the site, and each sits in
// a viewBox that scales to its container.
//
// The visual vocabulary is the site's: flat panels, square corners, 2px ink
// rules, one red accent, mono labels. Marker ids are suffixed per-diagram so
// several SVGs can share one page without colliding.

/** A right-pointing arrowhead marker, id-suffixed to stay unique per page. */
function arrowDefs(id, cls = "arrow") {
  return `<defs>
    <marker id="${id}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path class="${cls}" d="M0,0 L10,5 L0,10 z"/>
    </marker>
  </defs>`;
}

/** Center-anchored text lines stacked from y, line height lh. */
function lines(x, y, items, cls = "", lh = 15) {
  return items
    .map((t, i) => `<text class="${cls}" x="${x}" y="${y + i * lh}" text-anchor="middle">${t}</text>`)
    .join("");
}

/** A labelled box with an optional mono sub-label. Shared across the diagrams. */
function box(x, y, w, h, cls, title, sub) {
  const ty = sub ? y + h / 2 - 2 : y + h / 2 + 5;
  return `<rect class="${cls}" x="${x}" y="${y}" width="${w}" height="${h}"/>
    <text class="t-bold" x="${x + w / 2}" y="${ty}" text-anchor="middle">${title}</text>${
      sub ? `<text class="t-mono t-sub" x="${x + w / 2}" y="${y + h / 2 + 16}" text-anchor="middle">${sub}</text>` : ""
    }`;
}

/**
 * The user journey map — the path a newcomer takes through the repo, drawn as
 * a subway line with numbered stations. Odd stations label above the line,
 * even below, to keep the labels from colliding.
 */
export function journeyMap() {
  const stops = [
    ["Arrive", "the site / README"],
    ["Orient", "read How it works"],
    ["Pick work", "a design-brief issue"],
    ["Scaffold", "/new-design"],
    ["Iterate", "render, review previews"],
    ["Preflight", "/preflight"],
    ["Open PR", "a draft PR"],
    ["Ship", "CI gates, then merge"],
  ];
  const x0 = 84;
  const x1 = 1036;
  const y = 168;
  const step = (x1 - x0) / (stops.length - 1);
  const xs = stops.map((_, i) => Math.round(x0 + i * step));

  const line = `<line class="rule" x1="${x0}" y1="${y}" x2="${x1}" y2="${y}" marker-end="url(#jm-arrow)"/>`;

  const a = xs[4];
  const b = xs[5];
  const loop = `<path class="loop" d="M ${b} ${y - 22} C ${b} ${y - 78}, ${a} ${y - 78}, ${a} ${y - 22}" marker-end="url(#jm-arrow-accent)"/>
    <text class="t-mono t-accent" x="${(a + b) / 2}" y="${y - 84}" text-anchor="middle">repeat until green</text>`;

  const nodes = xs
    .map((x, i) => {
      const [title, sub] = stops[i];
      const last = i === stops.length - 1;
      const above = i % 2 === 0;
      const ring = last
        ? `<rect class="node-ring" x="${x - 21}" y="${y - 21}" width="42" height="42"/>`
        : "";
      const b0 = `<rect class="box-accent" x="${x - 15}" y="${y - 15}" width="30" height="30"/>
        <text class="t-on t-bold" x="${x}" y="${y + 5}" text-anchor="middle">${i + 1}</text>`;
      const label = above
        ? `<text class="t-mono t-muted" x="${x}" y="${y - 42}" text-anchor="middle">${sub}</text>
           <text class="t-bold" x="${x}" y="${y - 25}" text-anchor="middle">${title}</text>`
        : `<text class="t-bold" x="${x}" y="${y + 40}" text-anchor="middle">${title}</text>
           <text class="t-mono t-muted" x="${x}" y="${y + 57}" text-anchor="middle">${sub}</text>`;
      return `${ring}${b0}${label}`;
    })
    .join("\n    ");

  return `<svg class="diagram-svg diagram-mid" viewBox="0 0 1120 250" role="img"
    aria-label="A newcomer's path through the repo, as eight stations: arrive at the site, orient by reading How it works, pick a design-brief issue, scaffold with /new-design, iterate on previews (repeating until the gates pass), run /preflight, open a draft PR, and ship once CI gates it and it merges.">
    ${arrowDefs("jm-arrow", "arrow")}
    ${arrowDefs("jm-arrow-accent", "arrow-accent")}
    ${line}
    ${loop}
    ${nodes}
  </svg>`;
}

/**
 * The non-technical infographic — four plain-language panels, idea to a part
 * in your hand. Minimal geometric pictographs in the house style.
 */
export function infographicNonTechnical() {
  const panels = [
    {
      icon: iconSpeech,
      title: "Describe it",
      body: ["Say what you need — the", "size, the fit, what it holds."],
    },
    {
      icon: iconCoDesign,
      title: "Design it together",
      body: ["You and an AI shape the", "model, previewing after", "every change."],
    },
    {
      icon: iconCheck,
      title: "It gets checked",
      body: ["Automatic checks confirm", "it's solid and actually", "printable — before it ships."],
    },
    {
      icon: iconPart,
      title: "Print it",
      body: ["Download the ready-to-slice", "file — designed to print", "without supports."],
    },
  ];
  const w = 250;
  const gap = 40;
  const x0 = 30;
  const py = 46;
  const ph = 210;

  const blocks = panels
    .map((p, i) => {
      const x = x0 + i * (w + gap);
      const cx = x + w / 2;
      const arrow =
        i < panels.length - 1
          ? `<line class="rule" x1="${x + w + 8}" y1="${py + ph / 2}" x2="${x + w + gap - 8}" y2="${py + ph / 2}" marker-end="url(#ing-arrow)"/>`
          : "";
      return `<g>
        <rect class="box" x="${x}" y="${py}" width="${w}" height="${ph}"/>
        <rect class="box-accent" x="${x}" y="${py}" width="34" height="34"/>
        <text class="t-on t-bold" x="${x + 17}" y="${py + 23}" text-anchor="middle">${i + 1}</text>
        ${p.icon(cx, py + 78)}
        <text class="t-title" x="${cx}" y="${py + 128}" text-anchor="middle">${p.title}</text>
        ${lines(cx, py + 150, p.body, "t-sub", 17)}
      </g>${arrow}`;
    })
    .join("\n    ");

  return `<svg class="diagram-svg diagram-mid" viewBox="0 0 1180 300" role="img"
    aria-label="From an idea to a printed part in four steps: describe what you need; design it together with an AI, previewing after every change; automatic checks confirm it is printable; then download and print it without supports.">
    ${arrowDefs("ing-arrow", "arrow")}
    ${blocks}
  </svg>`;
}

// --- pictographs for the non-technical infographic (a few strokes each) ------
function iconSpeech(cx, cy) {
  const x = cx - 26, y = cy - 20;
  return `<g class="ic"><rect x="${x}" y="${y}" width="52" height="34"/>
    <path d="M ${x + 12} ${y + 34} L ${x + 12} ${y + 46} L ${x + 26} ${y + 34} z" class="ic-fill"/>
    <line x1="${x + 10}" y1="${y + 12}" x2="${x + 42}" y2="${y + 12}"/>
    <line x1="${x + 10}" y1="${y + 22}" x2="${x + 34}" y2="${y + 22}"/></g>`;
}
function iconCoDesign(cx, cy) {
  return `<g class="ic"><rect x="${cx - 28}" y="${cy - 20}" width="36" height="36"/>
    <rect x="${cx - 8}" y="${cy - 4}" width="36" height="36" class="ic-accent"/></g>`;
}
function iconCheck(cx, cy) {
  return `<g class="ic"><rect x="${cx - 24}" y="${cy - 22}" width="48" height="48"/>
    <path class="ic-check" d="M ${cx - 13} ${cy + 2} L ${cx - 3} ${cy + 12} L ${cx + 15} ${cy - 12}" fill="none"/></g>`;
}
function iconPart(cx, cy) {
  return `<g class="ic"><rect x="${cx - 26}" y="${cy + 6}" width="52" height="10"/>
    <rect x="${cx - 22}" y="${cy - 6}" width="44" height="10"/>
    <rect x="${cx - 16}" y="${cy - 18}" width="32" height="10" class="ic-accent"/></g>`;
}

/**
 * The pipeline as a step-through carousel: instead of one dense chart, six
 * focused slides a reader steps through. Each is a small, legible SVG plus a
 * title and a one-line note. Returned as data so the template can render the
 * carousel shell (controls, dots) around them.
 */
export function pipelineSlides() {
  return [
    { id: "classify", title: "A change is classified", note: "The pipeline reads your diff and picks only the gates that apply — a docs change never spins up the render stack.", svg: slideClassify() },
    { id: "gates", title: "It fans out to the gates", note: "Only the checks the change needs run: syntax + geometry, printcheck + a real test-slice, per-tool unit tests, style conformance.", svg: slideGates() },
    { id: "ci-ok", title: "One gate decides", note: "Every check converges on a single ci-ok. Green means merge — and a skipped check counts as OK, so unrelated PRs never stall.", svg: slideCiOk() },
    { id: "regenerate", title: "Derived files regenerate themselves", note: "Previews, galleries and pages rebuild and commit themselves in one guarded pass, so a committed image can't be older than its source.", svg: slideRegen() },
    { id: "runs-itself", title: "It runs itself", note: "Smart CI proposes new gates, an autonomy loop turns issues into draft PRs, and telemetry records every gate run.", svg: slideRuns() },
    { id: "two-layers", title: "Two layers, three seams", note: "Underneath sits a generic platform you can lift as a template, and the 3D-print layer you'd swap out — joined at classify, regenerate and gate.", svg: slideLayers() },
  ];
}

function slideWrap(id, aria, defs, inner, extra = "") {
  return `<svg class="diagram-svg diagram-slide${extra}" viewBox="0 0 620 240" role="img" aria-label="${aria}">
    ${defs}
    ${inner}
  </svg>`;
}

function slideClassify() {
  const y = 96;
  const inner = `${box(40, y, 130, 48, "box-tint", "PR change")}
    <line class="rule" x1="170" y1="${y + 24}" x2="212" y2="${y + 24}" marker-end="url(#ps1-arrow)"/>
    ${box(212, y, 120, 48, "box", "classify")}
    <line class="rule" x1="332" y1="${y + 24}" x2="372" y2="${y + 24}" marker-end="url(#ps1-arrow)"/>
    <polygon class="box" points="440,${y + 24} 500,${y} 560,${y + 24} 500,${y + 48}"/>
    <text class="t-bold" x="500" y="${y + 29}" text-anchor="middle">gate set</text>`;
  return slideWrap("classify", "A PR change goes into a classify step, which selects the gate set that applies to it.", arrowDefs("ps1-arrow", "arrow"), inner);
}

function slideGates() {
  const gates = [
    ["scad-check", "syntax + geometry"],
    ["render-gate", "printcheck + slice"],
    ["unit tests", "per tool"],
    ["style-gate", "conformance"],
  ];
  const gw = 288, gh = 54, gx = [16, 316], gy = [96, 168];
  const set = `<polygon class="box" points="250,44 310,20 370,44 310,68"/>
    <text class="t-bold" x="310" y="49" text-anchor="middle">gate set</text>`;
  const boxes = gates
    .map((g, i) => {
      const x = gx[i % 2];
      const yy = gy[Math.floor(i / 2)];
      return `<line class="rule-soft" x1="310" y1="68" x2="${x + gw / 2}" y2="${yy}" marker-end="url(#ps2-arrow)"/>
        ${box(x, yy, gw, gh, "box", g[0], g[1])}`;
    })
    .join("\n    ");
  return slideWrap("gates", "The gate set fans out to scad-check, render-gate, unit tests and style-gate.", arrowDefs("ps2-arrow", "arrow-soft"), set + "\n    " + boxes);
}

function slideCiOk() {
  const gates = ["scad-check", "render-gate", "unit tests", "style-gate"];
  const gy = [24, 68, 112, 156];
  const ciX = 320, ciY = 66;
  const list = gates
    .map((g, i) => `${box(24, gy[i], 168, 32, "box-soft", g)}
      <line class="rule-soft" x1="192" y1="${gy[i] + 16}" x2="${ciX}" y2="${ciY + 40}" marker-end="url(#ps3-arrow)"/>`)
    .join("\n    ");
  const inner = `${list}
    ${box(ciX, ciY, 170, 52, "box-accent-line", "ci-ok", "one gate to rule them")}
    <line class="rule" x1="490" y1="${ciY + 26}" x2="524" y2="${ciY + 26}" marker-end="url(#ps3-arrow-k)"/>
    ${box(524, ciY, 72, 52, "box-tint", "merge")}`;
  return slideWrap("ci-ok", "The four gates converge on a single ci-ok, which leads to merge.", arrowDefs("ps3-arrow", "arrow-soft") + arrowDefs("ps3-arrow-k", "arrow"), inner);
}

function slideRegen() {
  const cx = 310, cy = 120, r = 84, g = 18;
  const pt = (deg) => {
    const a = (deg * Math.PI) / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const seg = (from, to) => {
    const [x1, y1] = pt(from + g);
    const [x2, y2] = pt(to - g);
    return `<path class="loop-arc" d="M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}" marker-end="url(#ps4-arrow)"/>`;
  };
  const arcs = [seg(270, 360), seg(0, 90), seg(90, 180), seg(180, 270)].join("\n    ");
  const stations = [
    ["gate the source", 270, "middle", 0, -13],
    ["regenerate", 0, "start", 13, 5],
    ["commit back", 90, "middle", 0, 24],
    ["verify", 180, "end", -13, 5],
  ]
    .map(([t, deg, anchor, dx, dy]) => {
      const [x, y] = pt(deg);
      return `<rect class="box-accent" x="${(x - 7).toFixed(1)}" y="${(y - 7).toFixed(1)}" width="14" height="14"/>
        <text class="t-bold" x="${(x + dx).toFixed(1)}" y="${(y + dy).toFixed(1)}" text-anchor="${anchor}">${t}</text>`;
    })
    .join("\n    ");
  const inner = `${arcs}
    ${stations}
    <text class="t-mono t-sub" x="${cx}" y="${cy - 4}" text-anchor="middle">loop guard:</text>
    <text class="t-mono t-sub" x="${cx}" y="${cy + 12}" text-anchor="middle">at most one push</text>`;
  return slideWrap("regenerate", "A four-step loop: gate the source, regenerate the derived files, commit them back, and verify, bounded by a loop guard.", arrowDefs("ps4-arrow", "arrow-accent"), inner);
}

function slideRuns() {
  const cards = [
    ["smart-ci", "proposes new gates"],
    ["autonomy", "issue → draft PR"],
    ["telemetry", "records each gate run"],
  ];
  const w = 190, gap = 15, x0 = 15, y = 84, h = 72;
  const inner = cards
    .map(([t, s], i) => box(x0 + i * (w + gap), y, w, h, "box-soft", t, s))
    .join("\n    ");
  return slideWrap("runs-itself", "Three self-running parts: smart-ci proposes new gates, autonomy turns an issue into a draft PR, telemetry records each gate run.", "", inner);
}

function slideLayers() {
  const fy = 70, bw = 580, bh = 36;
  const band = (y, cls, t) =>
    `<rect class="${cls}" x="20" y="${y}" width="${bw}" height="${bh}"/>
     <text class="t-bold" x="36" y="${y + 23}">${t}</text>`;
  const inner = `${band(fy, "band-platform", "PLATFORM — generic (the reusable template)")}
    ${band(fy + bh, "band-domain", "DOMAIN — 3D-print / OpenSCAD (you replace this)")}
    ${[300, 420, 510].map((x) => `<line class="seam" x1="${x}" y1="${fy}" x2="${x}" y2="${fy + bh * 2}"/>`).join("")}
    <text class="t-mono t-sub" x="600" y="${fy + bh * 2 + 24}" text-anchor="end">three seams: classify · regenerate · gate</text>`;
  return slideWrap("two-layers", "A generic platform layer beneath a replaceable 3D-print domain layer, joined at three seams: classify, regenerate, gate.", "", inner);
}
