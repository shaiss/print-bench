// Theme toggle. The page defaults to the OS preference via CSS
// (prefers-color-scheme); this only records an explicit override on
// documentElement, which the [data-theme] rules in site.css outrank.
//
// The inline bootstrap in the page <head> applies the stored choice before
// first paint — this file only wires the button, so a slow load never
// flashes the wrong theme.
(function () {
  var KEY = "print-bench-theme";
  var root = document.documentElement;

  function current() {
    var stored = null;
    try {
      stored = localStorage.getItem(KEY);
    } catch (e) {
      /* private mode / storage disabled — fall through to the OS preference */
    }
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    var btn = document.querySelector(".theme-toggle");
    if (btn) {
      btn.textContent = theme === "dark" ? "☀" : "☾";
      btn.setAttribute(
        "aria-label",
        theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
      );
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    apply(current());
    var btn = document.querySelector(".theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(KEY, next);
      } catch (e) {
        /* not persisting is survivable; the toggle still works this visit */
      }
      apply(next);
    });
  });
})();

// Avatar overrides + the studio hook.
//
// A visitor's avatar re-rolls (see avatar-studio.js) persist per-browser in
// localStorage as {style, seed, svg}; this applies the stored SVG wherever
// that member's avatar renders — profile, contributor card, timeline — so
// the personal view is consistent site-wide, while the committed SVG stays
// what everyone else sees. Also reveals the People page's re-roll glyphs and
// lazy-loads the studio on first press.
(function () {
  function stored(handle) {
    try {
      var raw = localStorage.getItem("print-bench-avatar:" + handle);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function src(svg) {
    return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Committed-avatar <img>s anywhere on the page.
    document.querySelectorAll('img.monogram[src^="/assets/avatars/"]').forEach(function (img) {
      var m = img.getAttribute("src").match(/\/assets\/avatars\/([a-z0-9-]+)\.svg$/);
      var o = m && stored(m[1]);
      if (o && o.svg) img.src = src(o.svg);
    });

    // People-page slots (which may hold an initials span when no avatar is
    // committed): swap in the override and reveal the re-roll glyph.
    document.querySelectorAll("[data-avatar-slot]").forEach(function (slot) {
      var o = stored(slot.dataset.handle);
      if (o && o.svg) {
        var mark = slot.querySelector(".monogram");
        if (mark && mark.tagName !== "IMG") {
          var img = document.createElement("img");
          img.className = "monogram monogram-" + slot.dataset.kind;
          img.width = 46;
          img.height = 46;
          img.alt = "";
          mark.replaceWith(img);
          mark = img;
        }
        if (mark) mark.src = src(o.svg);
      }
      var btn = slot.querySelector("[data-avatar-reroll]");
      if (btn) {
        btn.hidden = false;
        btn.addEventListener("click", function () {
          import("/assets/avatar-studio.js").then(function (studio) {
            studio.open(slot);
          });
        });
      }
    });
  });
})();

// Product-page tabs (wireframe 1d: one concern on screen at a time).
//
// The page ships as a stacked document: the tab bar is `hidden` and every
// panel is visible with its own ruled label, so without JavaScript nothing
// is unreachable. This unhides the bar, adds `tabs-live` (which hides the
// fallback labels and lets `hidden` bite on panels), and drives selection.
// A hash naming a panel — from a link on the page or an inbound URL — wins
// over the default first tab, so "#workbench" deep-links keep working.
(function () {
  var bar = document.querySelector("[data-tabs]");
  if (!bar) return;

  document.addEventListener("DOMContentLoaded", function () {
    var tabs = Array.prototype.slice.call(bar.querySelectorAll("[role=tab]"));
    var panels = tabs
      .map(function (t) {
        return document.getElementById(t.getAttribute("aria-controls"));
      })
      .filter(Boolean);
    if (!panels.length) return;

    function select(id) {
      tabs.forEach(function (t) {
        t.setAttribute("aria-selected", String(t.getAttribute("aria-controls") === id));
      });
      panels.forEach(function (p) {
        p.hidden = p.id !== id;
      });
    }

    document.documentElement.classList.add("tabs-live");
    bar.hidden = false;
    tabs.forEach(function (t) {
      t.addEventListener("click", function () {
        select(t.getAttribute("aria-controls"));
      });
    });

    // In-page anchors may target a panel itself ("Open workbench →") or a
    // heading inside one (the Overview rail's table of contents): activate
    // the containing panel so the target is on screen, then let the browser
    // finish the scroll.
    function panelFor(hash) {
      if (!hash || hash.length < 2) return null;
      var el;
      try {
        el = document.getElementById(decodeURIComponent(hash.slice(1)));
      } catch (e) {
        return null;
      }
      if (!el) return null;
      return el.closest(".tab-panel");
    }

    window.addEventListener("hashchange", function () {
      var panel = panelFor(location.hash);
      if (panel) select(panel.id);
    });

    var initial = panelFor(location.hash);
    select(initial ? initial.id : panels[0].id);
  });
})();

/* Gallery card hover: swap the hero still for the turntable GIF (the media
   rework, PR #159). Skipped under prefers-reduced-motion; without JavaScript
   the card is simply the still hero. */
(function () {
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".card-media[data-spin]").forEach(function (a) {
      var img = a.querySelector("img");
      if (!img) return;
      var card = a.closest(".card") || a;
      card.addEventListener("mouseenter", function () { img.src = a.getAttribute("data-spin"); });
      card.addEventListener("mouseleave", function () { img.src = a.getAttribute("data-still"); });
    });
  });
})();

/* Product-page media stage: thumbnail rail switches the stage image and its
   caption (label, kind, alt text, AI disclosure), with arrow-key navigation.
   The stage ships showing the hero, so without JavaScript nothing is broken —
   the rail is still every preview at thumbnail size. */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var stage = document.querySelector("[data-media-stage]");
    if (!stage) return;
    var img = stage.querySelector("[data-stage-img]");
    var label = stage.querySelector("[data-stage-label]");
    var kind = stage.querySelector("[data-stage-kind]");
    var count = stage.querySelector("[data-stage-count]");
    var alt = stage.querySelector("[data-stage-alt]");
    var disclosure = stage.querySelector("[data-stage-disclosure]");
    var thumbs = Array.prototype.slice.call(stage.querySelectorAll(".stage-thumb"));
    if (!thumbs.length) return; // rail-less single-media stage: nothing to switch
    var cur = 0;
    function show(i) {
      cur = (i + thumbs.length) % thumbs.length;
      var t = thumbs[cur];
      img.src = t.getAttribute("data-src");
      img.alt = t.getAttribute("data-alt") || "";
      label.textContent = t.getAttribute("data-label") || "";
      kind.textContent = t.getAttribute("data-kind") || "";
      count.textContent = String(cur + 1) + " / " + thumbs.length;
      alt.textContent = t.getAttribute("data-alt") || "";
      var d = t.getAttribute("data-disclosure");
      disclosure.hidden = !d;
      disclosure.textContent = d || "";
      thumbs.forEach(function (b, j) { b.classList.toggle("sel", j === cur); });
    }
    thumbs.forEach(function (t, i) {
      t.addEventListener("click", function () { show(i); });
    });
    document.addEventListener("keydown", function (e) {
      if (e.target && /^(input|textarea|select)$/i.test(e.target.tagName)) return;
      if (e.key === "ArrowRight") show(cur + 1);
      else if (e.key === "ArrowLeft") show(cur - 1);
    });
  });
})();
