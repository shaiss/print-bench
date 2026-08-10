// Inline SVG diagrams for the "How it works" page.
//
// Authored markup, like the favicon and the avatars — not fetched, not a
// runtime. Every colour is a CSS token (see the `.diagram` block in site.css),
// so the diagrams theme light/dark with the rest of the site, and each sits in
// a viewBox that scales to its container. Dense ones are wrapped in an
// overflow-x scroller by the template so they stay legible on a phone.
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

  // The iterate↔preflight loop: a dashed arc from Preflight (5) back to
  // Iterate (4), the review round that repeats until the gates pass.
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
      const box = `<rect class="box-accent" x="${x - 15}" y="${y - 15}" width="30" height="30"/>
        <text class="t-on t-bold" x="${x}" y="${y + 5}" text-anchor="middle">${i + 1}</text>`;
      const label = above
        ? `<text class="t-mono t-muted" x="${x}" y="${y - 42}" text-anchor="middle">${sub}</text>
           <text class="t-bold" x="${x}" y="${y - 25}" text-anchor="middle">${title}</text>`
        : `<text class="t-bold" x="${x}" y="${y + 40}" text-anchor="middle">${title}</text>
           <text class="t-mono t-muted" x="${x}" y="${y + 57}" text-anchor="middle">${sub}</text>`;
      return `${ring}${box}${label}`;
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
      body: ["Download the ready-to-slice", "file and print. No supports,", "by design."],
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

  return `<svg class="diagram-svg diagram-mid" viewBox="0 0 1120 300" role="img"
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
  // A little printed stack — three layers.
  return `<g class="ic"><rect x="${cx - 26}" y="${cy + 6}" width="52" height="10"/>
    <rect x="${cx - 22}" y="${cy - 6}" width="44" height="10"/>
    <rect x="${cx - 16}" y="${cy - 18}" width="32" height="10" class="ic-accent"/></g>`;
}

/**
 * The technical infographic — the pipeline in one view, in four labelled lanes:
 * the gate flow a change moves through, the regenerate-and-commit loop, the
 * self-running rail, and the platform/domain foundation. Dense on purpose; the
 * template wraps it in a horizontal scroller for small screens.
 */
export function infographicTechnical() {
  const box = (x, y, w, h, cls, title, sub) =>
    `<rect class="${cls}" x="${x}" y="${y}" width="${w}" height="${h}"/>
     <text class="t-bold" x="${x + w / 2}" y="${y + (sub ? h / 2 - 2 : h / 2 + 5)}" text-anchor="middle">${title}</text>${
       sub ? `<text class="t-mono t-sub" x="${x + w / 2}" y="${y + h / 2 + 16}" text-anchor="middle">${sub}</text>` : ""
     }`;
  // Lane titles sit ABOVE their lane, left-aligned with the content, so a
  // filled box can never paint over them.
  const laneLabel = (y, t) => `<text class="t-lane" x="56" y="${y}">${t}</text>`;

  // Lane 1 — the gate flow. ci-ok is the convergence point.
  const l1y = 66;
  const cx = 936, ciY = 262;
  const gateSet = `<polygon class="box" points="352,${l1y} 404,${l1y + 24} 352,${l1y + 48} 300,${l1y + 24}"/>
    <text class="t-bold" x="352" y="${l1y + 29}" text-anchor="middle">gate set</text>`;
  const gates = [
    ["scad-check", "syntax + geometry"],
    ["render-gate", "printcheck + slice"],
    ["unit tests", "per tool"],
    ["style-gate", "conformance"],
  ];
  const gy = 150;
  const gw = 172, ggap = 18, gx0 = 452;
  const gateBoxes = gates
    .map((g, i) => {
      const x = gx0 + i * (gw + ggap);
      return `<line class="rule-soft" x1="352" y1="${l1y + 48}" x2="${x + gw / 2}" y2="${gy}" marker-end="url(#tech-arrow-s)"/>
        ${box(x, gy, gw, 52, "box", g[0], g[1])}
        <line class="rule-soft" x1="${x + gw / 2}" y1="${gy + 52}" x2="${cx}" y2="${ciY}" marker-end="url(#tech-arrow-s)"/>`;
    })
    .join("\n    ");
  const lane1 = `${laneLabel(l1y - 18, "A CHANGE MOVES THROUGH THE GATES")}
    ${box(56, l1y + 4, 108, 40, "box-tint", "PR change")}
    <line class="rule" x1="164" y1="${l1y + 24}" x2="222" y2="${l1y + 24}" marker-end="url(#tech-arrow)"/>
    ${box(222, l1y + 4, 78, 40, "box", "classify")}
    <line class="rule" x1="300" y1="${l1y + 24}" x2="300" y2="${l1y + 24}"/>
    ${gateSet}
    ${gateBoxes}
    ${box(848, ciY, 176, 44, "box-accent-line", "ci-ok", "one gate to rule them")}
    <line class="rule" x1="1024" y1="${ciY + 22}" x2="1072" y2="${ciY + 22}" marker-end="url(#tech-arrow)"/>
    ${box(1072, ciY, 72, 44, "box-tint", "merge")}`;

  // Lane 2 — regenerate + commit, with the loop.
  const l2y = 372;
  const rboxes = [
    ["gate source", 56],
    ["regenerate", 250],
    ["commit back", 444],
  ];
  const rw = 150;
  const lane2 =
    `${laneLabel(l2y - 62, "DERIVED FILES REGENERATE THEMSELVES")}` +
    `<path class="loop" d="M ${444 + rw / 2} ${l2y} C ${444 + rw / 2} ${l2y - 28}, ${131} ${l2y - 28}, ${131} ${l2y}" marker-end="url(#tech-arrow-accent)"/>
     <text class="t-mono t-accent" x="${(131 + 444 + rw / 2) / 2}" y="${l2y - 42}" text-anchor="middle">re-trigger (PAT) · loop guard: one push</text>` +
    rboxes
      .map(([t, x], i) => {
        const arrow =
          i < rboxes.length - 1
            ? `<line class="rule" x1="${x + rw}" y1="${l2y + 22}" x2="${rboxes[i + 1][1]}" y2="${l2y + 22}" marker-end="url(#tech-arrow)"/>`
            : "";
        return `${box(x, l2y + 2, rw, 40, "box", t)}${arrow}`;
      })
      .join("\n    ");

  // Lane 3 — the self-running rail.
  const l3y = 478;
  const rail = [
    ["smart-ci", "proposes new gates"],
    ["autonomy", "issue → draft PR"],
    ["telemetry", "records every run"],
  ];
  const lane3 =
    `${laneLabel(l3y - 12, "AND IT RUNS ITSELF")}` +
    rail
      .map((r, i) => {
        const w = 292, g = 20, x = 56 + i * (w + g);
        return box(x, l3y + 2, w, 48, "box-soft", r[0], r[1]);
      })
      .join("\n    ");

  // Foundation — platform over domain, three seams. Titles are left-aligned so
  // the seam ticks never cross them.
  const fy = 566;
  const band = (y, cls, t) =>
    `<rect class="${cls}" x="56" y="${y}" width="1088" height="30"/>
     <text class="t-bold" x="72" y="${y + 20}">${t}</text>`;
  const foundation = `${band(fy, "band-platform", "PLATFORM — generic (the reusable template)")}
    ${band(fy + 30, "band-domain", "DOMAIN — 3D-print / OpenSCAD (the part you replace)")}
    ${[840, 980, 1064]
      .map((x) => `<line class="seam" x1="${x}" y1="${fy}" x2="${x}" y2="${fy + 60}"/>`)
      .join("")}
    <text class="t-mono t-sub" x="1052" y="${fy + 78}" text-anchor="end">three seams: classify · regenerate · gate</text>`;

  return `<svg class="diagram-svg diagram-wide" viewBox="0 0 1240 660" role="img"
    aria-label="The pipeline in one view. A PR change is classified into a gate set that fans out to scad-check, render-gate (printcheck plus test-slice), per-tool unit tests and style-gate, all converging on a single ci-ok gate before merge. Derived files regenerate and commit themselves in a guarded loop. A rail of smart-ci, autonomy and telemetry lets it run itself. Underneath, a generic platform layer supports the replaceable 3D-print domain layer, joined at three seams.">
    ${arrowDefs("tech-arrow", "arrow")}
    ${arrowDefs("tech-arrow-s", "arrow-soft")}
    ${arrowDefs("tech-arrow-accent", "arrow-accent")}
    ${lane1}
    ${lane2}
    ${lane3}
    ${foundation}
  </svg>`;
}

/**
 * The regenerate-and-commit loop — a compact cycle for the section that
 * explains why derived files are the pipeline's job.
 */
export function regenLoop() {
  const cx = 250, cy = 140, r = 88, g = 17;
  const pt = (deg) => {
    const a = (deg * Math.PI) / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  // Four clockwise arcs (gate→regenerate→commit→verify→gate), each stopping a
  // few degrees short of the next node so its arrowhead reads.
  const seg = (from, to) => {
    const [x1, y1] = pt(from + g);
    const [x2, y2] = pt(to - g);
    return `<path class="loop-arc" d="M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}" marker-end="url(#rl-arrow-accent)"/>`;
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
  return `<svg class="diagram-svg diagram-narrow" viewBox="80 26 384 244" role="img"
    aria-label="A four-step clockwise loop: gate the source, regenerate the derived files, commit them back, and verify — bounded by a loop guard so it runs at most once per change.">
    ${arrowDefs("rl-arrow-accent", "arrow-accent")}
    ${arcs}
    ${stations}
    <text class="t-mono t-sub" x="${cx}" y="${cy - 4}" text-anchor="middle">loop guard:</text>
    <text class="t-mono t-sub" x="${cx}" y="${cy + 12}" text-anchor="middle">at most one push</text>
  </svg>`;
}
