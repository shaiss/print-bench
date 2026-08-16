// The site's notification model — the generic base a header bell renders from.
//
// Today one source feeds it: the open `needs-decision` queue (issue #181, the
// surfacing layer for the #161 HITL decision gate). It used to render as a
// full-width "Decision queue" panel that dominated the index page above the
// gallery. That real estate belongs to the designs; a parked decision is a
// notification, not a headline. So the queue now flows into a standard app
// notification tray behind a header bell (see templates.mjs `notificationBell`),
// and this module is the seam between "a data source" and "a notification the
// bell shows" — deliberately generic so the next source (a failing gate, a new
// release, a stalled PR) plugs in the same way instead of growing another panel.
//
// A NOTIFICATION is the render model the tray consumes:
//   { id, category, categoryLabel, title, url, meta }
//     id            — stable, unique per item (dedup / future read-state key)
//     category      — machine key grouping like items ("decision")
//     categoryLabel — the short human tag shown on the row ("Decision")
//     title         — the human line
//     url           — where the row links (opens the real issue/PR)
//     meta          — a small secondary line ("#42 · issue")
//
// A BUNDLE is what the bell renders:
//   { items: Notification[], actions: [{ label, url }] }
//     items   — the rows, newest concern first (the queue is oldest-parked
//               first, which is the one waiting longest — that order is kept)
//     actions — tray-footer links ("Every open decision →")
//
// Everything here is PURE and total on junk — the data it maps already came
// through decisions.mjs's best-effort fetch, so a malformed row must degrade to
// "fewer notifications", never a thrown build.

/** The empty bundle — an all-caught-up bell. */
export function emptyBundle() {
  return { items: [], actions: [] };
}

/**
 * Pure: the decision queue `{ rows, searchUrl }` (as build.mjs assembles it
 * from decisions.mjs) → a notification bundle. Each row becomes one
 * `category: "decision"` notification; the queue's saved-search link becomes
 * the tray's one footer action. Total on junk: a missing/empty queue yields the
 * empty bundle, and a row missing its number/title/url is skipped rather than
 * rendered half-blank.
 */
export function decisionsToNotifications(queue) {
  if (!queue || typeof queue !== "object" || !Array.isArray(queue.rows)) {
    return emptyBundle();
  }
  const items = [];
  for (const r of queue.rows) {
    if (!r || typeof r !== "object") continue;
    const number = typeof r.number === "number" ? r.number : null;
    const title = typeof r.title === "string" ? r.title.trim() : "";
    const url = typeof r.url === "string" ? r.url : "";
    if (number === null || !title || !url) continue;
    const kindLabel = r.kind === "pull" ? "PR" : "issue";
    items.push({
      id: `decision-${number}`,
      category: "decision",
      categoryLabel: "Decision",
      title,
      url,
      meta: `#${number} · ${kindLabel}`,
    });
  }
  const actions =
    items.length && typeof queue.searchUrl === "string" && queue.searchUrl
      ? [{ label: "Every open decision →", url: queue.searchUrl }]
      : [];
  return { items, actions };
}

/**
 * Merge several bundles into one, in the order given (each source's items and
 * actions are appended). The single seam every future notification source funnels
 * through — build.mjs calls this with the bundles it has, so adding a source is
 * one more argument here, never another panel on a page.
 */
export function mergeBundles(...bundles) {
  const out = emptyBundle();
  for (const b of bundles) {
    if (!b || typeof b !== "object") continue;
    if (Array.isArray(b.items)) out.items.push(...b.items);
    if (Array.isArray(b.actions)) out.actions.push(...b.actions);
  }
  return out;
}
