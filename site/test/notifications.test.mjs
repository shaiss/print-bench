// The header notification bell (issue #181's decision queue, generalized).
//
// Two halves, pinned like every other buildable seam:
//   - the PURE transform (decisionsToNotifications / mergeBundles / emptyBundle):
//     a data source → the generic notification bundle the bell renders. Total on
//     junk, since the queue it maps already came through a best-effort fetch.
//   - the RENDERED bell, driven through indexPage after setNotifications — the
//     positive path is deploy-only (local/CI has no network source and the bell
//     shows empty), so these hold the non-empty render against regression the
//     way how-it-works.test.mjs drives howItWorksPage.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  emptyBundle,
  decisionsToNotifications,
  mergeBundles,
} from "../lib/notifications.mjs";
import { indexPage, setNotifications } from "../lib/templates.mjs";

// A decision queue as build.mjs assembles it (decisions.mjs rows + searchUrl).
const QUEUE = {
  rows: [
    { number: 42, title: "Loosen the coupon fit?", url: "https://github.com/o/r/issues/42", kind: "issue" },
    { number: 9, title: "ship it?", url: "https://github.com/o/r/pull/9", kind: "pull" },
  ],
  searchUrl: "https://github.com/o/r/issues?q=needs-decision",
};

// --- the PURE transform, no network ---

test("decisionsToNotifications maps a queue to notification rows", () => {
  const { items, actions } = decisionsToNotifications(QUEUE);
  assert.equal(items.length, 2);
  assert.deepEqual(items[0], {
    id: "decision-42",
    category: "decision",
    categoryLabel: "Decision",
    title: "Loosen the coupon fit?",
    url: "https://github.com/o/r/issues/42",
    meta: "#42 · issue",
  });
  // an honest issue-vs-PR label rides in the meta line
  assert.equal(items[1].meta, "#9 · PR");
  // the saved-search link becomes the tray's one footer action
  assert.deepEqual(actions, [
    { label: "Every open decision →", url: QUEUE.searchUrl },
  ]);
});

test("decisionsToNotifications is total on junk / empty input", () => {
  assert.deepEqual(decisionsToNotifications(null), emptyBundle());
  assert.deepEqual(decisionsToNotifications(undefined), emptyBundle());
  assert.deepEqual(decisionsToNotifications("nope"), emptyBundle());
  assert.deepEqual(decisionsToNotifications({}), emptyBundle());
  assert.deepEqual(decisionsToNotifications({ rows: [] }), emptyBundle());
});

test("decisionsToNotifications skips a row missing a number, title or url", () => {
  const { items } = decisionsToNotifications({
    rows: [
      { number: 1, title: "kept", url: "u", kind: "issue" },
      { number: 2, title: "no url", url: "" },
      { number: 3, title: "", url: "u" },
      { title: "no number", url: "u" },
      null,
      "not an object",
    ],
    searchUrl: "s",
  });
  assert.equal(items.length, 1);
  assert.equal(items[0].id, "decision-1");
});

test("decisionsToNotifications emits no footer action when nothing is queued", () => {
  // a searchUrl with no rows must not render a lone "see all" footer
  assert.deepEqual(decisionsToNotifications({ rows: [], searchUrl: "s" }), emptyBundle());
});

test("mergeBundles concatenates items and actions in order", () => {
  const a = { items: [{ id: "a" }], actions: [{ label: "A", url: "a" }] };
  const b = { items: [{ id: "b" }], actions: [] };
  const merged = mergeBundles(a, b, null, "junk");
  assert.deepEqual(merged.items.map((i) => i.id), ["a", "b"]);
  assert.deepEqual(merged.actions, [{ label: "A", url: "a" }]);
});

// --- the rendered bell, driven through the shared header (no network) ---

test("the header bell renders a badge, rows and footer from a non-empty bundle", () => {
  setNotifications(decisionsToNotifications(QUEUE));
  try {
    const html = indexPage([]);
    assert.match(html, /class="notif"/, "the bell control is present");
    assert.match(html, /class="notif-badge"[^>]*>2</, "badge shows the count");
    assert.match(html, /Loosen the coupon fit\?/, "a decision title is listed");
    assert.match(html, /#42 · issue/, "the row carries its honest meta line");
    assert.match(html, /href="https:\/\/github\.com\/o\/r\/issues\/42"/, "row links to the issue");
    assert.match(html, /Every open decision/, "footer action rendered");
    assert.ok(!html.includes("undefined"), "no undefined leaked into the page");
    assert.ok(!html.includes("${"), "no unrendered template placeholder");
    // the old full-width panel is gone
    assert.ok(!html.includes('class="decisions"'), "no page-dominating decision panel");
  } finally {
    setNotifications(emptyBundle());
  }
});

test("the header bell renders an empty state with no badge when nothing is queued", () => {
  setNotifications(emptyBundle());
  const html = indexPage([]);
  assert.match(html, /class="notif"/, "the bell is always present (standard app pattern)");
  assert.ok(!/class="notif-badge"/.test(html), "no badge when the count is zero");
  assert.match(html, /You're all caught up\./, "the empty state is shown");
});
