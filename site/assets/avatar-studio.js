// The avatar studio (People page): the recycle glyph's lazy module.
//
// Browser-local by design. A re-roll (or a style change from the curated
// set) regenerates the avatar right here with the vendored DiceBear build —
// nothing external, nothing uploaded — and persists in THIS browser's
// localStorage, so it follows the visitor around the site but changes no one
// else's view. The panel shows the `avatar-style:` / `avatar-seed:` header
// lines whose commit (or the "Regenerate avatar" Action) makes a combination
// everyone's reality. The committed repo stays the one authority on member
// identity; this is a lens on top.
//
// Loaded only when a glyph is first pressed (site.js does the import), and
// the per-style DiceBear modules load on first use of that style.

const KEY = (handle) => `print-bench-avatar:${handle}`;

// Repo constants, deliberately not read from the page: keeping the commit
// targets as module literals means no DOM-derived text ever reaches an href
// (CodeQL js/xss-through-dom) — the data block carries only the curated
// style sets and the background token.
const EDIT_BASE = "https://github.com/shaiss/print-bench/edit/main/people/";
const ACTION_URL = "https://github.com/shaiss/print-bench/actions/workflows/avatar.yml";

let data = null;
let panel = null;
let active = null; // { slot, handle, kind, committed: {style, seed}, current: {style, seed} }

function studioData() {
  if (data) return data;
  const el = document.getElementById("avatar-studio-data");
  data = el ? JSON.parse(el.textContent) : { styles: {}, background: "f3f2f2" };
  return data;
}

async function generate(style, seed) {
  const [core, mod] = await Promise.all([
    import("/assets/dicebear/core/index.js"),
    import(`/assets/dicebear/${style}/index.js`),
  ]);
  return core
    .createAvatar(mod, {
      seed,
      backgroundColor: [studioData().background],
      radius: 0,
    })
    .toString();
}

function randomSeed() {
  const bytes = new Uint8Array(4);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function svgToSrc(svg) {
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

/** Swap the slot's identity mark to the given SVG (span → img if needed). */
function applyToSlot(slot, kind, svg) {
  let mark = slot.querySelector(".monogram");
  if (mark && mark.tagName !== "IMG") {
    const img = document.createElement("img");
    img.className = `monogram monogram-${kind}`;
    img.width = 46;
    img.height = 46;
    img.alt = "";
    mark.replaceWith(img);
    mark = img;
  }
  if (mark) mark.src = svgToSrc(svg);
}

function store(handle, value) {
  try {
    if (value === null) localStorage.removeItem(KEY(handle));
    else localStorage.setItem(KEY(handle), JSON.stringify(value));
  } catch (e) {
    /* private mode — the re-roll still shows this visit */
  }
}

function stored(handle) {
  try {
    const raw = localStorage.getItem(KEY(handle));
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function configLines() {
  return `avatar-style: ${active.current.style}\navatar-seed: ${active.current.seed}`;
}

function refreshPanel() {
  panel.querySelector("[data-studio-style]").value = active.current.style;
  panel.querySelector("[data-studio-config]").textContent = configLines();
  panel.querySelector("[data-studio-edit]").href =
    `${EDIT_BASE}${encodeURIComponent(active.handle)}.md`;
  panel.querySelector("[data-studio-action]").href = ACTION_URL;
}

async function reroll(style, seed) {
  const svg = await generate(style, seed);
  active.current = { style, seed };
  applyToSlot(active.slot, active.kind, svg);
  store(active.handle, { style, seed, svg });
  refreshPanel();
}

function resetToCommitted() {
  store(active.handle, null);
  active.current = { ...active.committed };
  const mark = active.slot.querySelector(".monogram");
  // Reload the committed asset (or just reload the page state cheaply).
  if (mark && mark.tagName === "IMG") mark.src = `/assets/avatars/${active.handle}.svg`;
  refreshPanel();
}

function buildPanel() {
  const dialog = document.createElement("dialog");
  dialog.className = "avatar-studio";
  dialog.innerHTML = `
  <form method="dialog" class="avatar-studio-head">
    <p class="eyebrow">Avatar studio — your view only</p>
    <button class="avatar-studio-close" aria-label="Close">×</button>
  </form>
  <p class="avatar-studio-note">Re-rolls live in your browser. To make one
    everyone's, commit the lines below to the member's profile — or run the
    Regenerate avatar Action.</p>
  <div class="avatar-studio-row">
    <label>Style
      <select data-studio-style></select>
    </label>
    <button type="button" class="btn" data-studio-reroll>Re-roll</button>
    <button type="button" class="btn" data-studio-reset>Reset to committed</button>
  </div>
  <pre class="avatar-studio-config"><code data-studio-config></code></pre>
  <div class="avatar-studio-row">
    <button type="button" class="btn" data-studio-copy>Copy config</button>
    <a class="btn" data-studio-edit target="_blank" rel="noopener noreferrer">Edit profile on GitHub ↗</a>
    <a class="btn" data-studio-action target="_blank" rel="noopener noreferrer">Regenerate-avatar Action ↗</a>
  </div>`;
  document.body.append(dialog);

  const select = dialog.querySelector("[data-studio-style]");
  select.addEventListener("change", () => reroll(select.value, active.current.seed));
  dialog
    .querySelector("[data-studio-reroll]")
    .addEventListener("click", () => reroll(active.current.style, randomSeed()));
  dialog
    .querySelector("[data-studio-reset]")
    .addEventListener("click", () => resetToCommitted());
  dialog.querySelector("[data-studio-copy]").addEventListener("click", async (ev) => {
    try {
      await navigator.clipboard.writeText(configLines());
      ev.target.textContent = "Copied";
      setTimeout(() => (ev.target.textContent = "Copy config"), 1500);
    } catch (e) {
      /* clipboard denied — the lines are visible to copy by hand */
    }
  });
  return dialog;
}

/** Entry point: site.js calls this with the pressed glyph's slot. */
export async function open(slot) {
  const d = studioData();
  const handle = slot.dataset.handle;
  const kind = slot.dataset.kind;
  const committed = { style: slot.dataset.style, seed: slot.dataset.seed };
  const override = stored(handle);

  active = {
    slot,
    handle,
    kind,
    committed,
    current: override ? { style: override.style, seed: override.seed } : { ...committed },
  };

  if (!panel) panel = buildPanel();
  // Options built with the DOM API, never markup: the style names come from
  // the page's JSON data block, and DOM-read text must not meet innerHTML.
  const select = panel.querySelector("[data-studio-style]");
  select.replaceChildren(...(d.styles[kind] || []).map((s) => new Option(s, s)));

  // The glyph's promise is a fresh roll: re-roll immediately, then keep the
  // panel open for style changes and further rolls.
  await reroll(active.current.style, randomSeed());
  if (!panel.open) panel.showModal();
}
