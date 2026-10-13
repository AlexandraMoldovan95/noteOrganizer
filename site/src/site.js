// The light/dark switch and the phone menu. The page follows the visitor's
// system setting until the switch is used; the choice is remembered in
// this browser only.
(function () {
  "use strict";
  var KEY = "noteorganizer-site-theme";
  var root = document.documentElement;

  function systemDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function current() {
    var set = root.getAttribute("data-theme");
    if (set) return set;
    return systemDark() ? "dark" : "light";
  }
  // Drawn as lines rather than taken from a font, which may not have them.
  var SHAPES = {
    sun: "M8 5.2a2.8 2.8 0 1 0 0 5.6a2.8 2.8 0 1 0 0-5.6M8 1v1.6M8 13.4V15M1 8h1.6M13.4 8H15" +
         "M3 3l1.1 1.1M11.9 11.9L13 13M3 13l1.1-1.1M11.9 4.1L13 3",
    moon: "M13.5 9.6A5.6 5.6 0 0 1 6.4 2.5a5.6 5.6 0 1 0 7.1 7.1z"
  };
  function drawn(name) {
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    [["viewBox", "0 0 16 16"], ["width", "18"], ["height", "18"], ["aria-hidden", "true"], ["fill", "none"],
     ["stroke", "currentColor"], ["stroke-width", "1.6"], ["stroke-linecap", "round"], ["stroke-linejoin", "round"]]
      .forEach(function (a) { svg.setAttribute(a[0], a[1]); });
    var path = document.createElementNS(ns, "path");
    path.setAttribute("d", SHAPES[name]);
    svg.appendChild(path);
    return svg;
  }

  function paint() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    var dark = current() === "dark";
    btn.textContent = "";
    btn.appendChild(drawn(dark ? "sun" : "moon"));
    btn.setAttribute("aria-label", dark ? "Switch to the light theme" : "Switch to the dark theme");
    btn.title = btn.getAttribute("aria-label");
  }

  try {
    var saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  } catch (e) { /* storage blocked: follow the system */ }

  document.addEventListener("DOMContentLoaded", function () {
    paint();
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        var next = current() === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        try { localStorage.setItem(KEY, next); } catch (e) { /* not remembered */ }
        paint();
      });
    }
    var menu = document.getElementById("menu-toggle");
    var nav = document.getElementById("site-nav");
    if (menu && nav) {
      menu.addEventListener("click", function () {
        var open = nav.classList.toggle("open");
        menu.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }
    revealDocSections();
  });

  // On a doc page (how it's built, in my words, testing), fade each
  // top-level block in as it scrolls into view. Skipped entirely when the
  // visitor's system asks for reduced motion, or when IntersectionObserver
  // is not available -- either way, every block is just shown as normal.
  function revealDocSections() {
    if (!window.IntersectionObserver) return;
    if (!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: no-preference)").matches)) return;
    var items = document.querySelectorAll(
      ".doc .wrap > h1, .doc .wrap > h2, .doc .wrap > h3, .doc .wrap > p, " +
      ".doc .wrap > ul, .doc .wrap > ol, .doc .wrap > pre, .doc .wrap > blockquote, " +
      ".doc .wrap > hr, .doc .wrap > .table-wrap"
    );
    if (!items.length) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    items.forEach(function (el) {
      el.classList.add("reveal");
      io.observe(el);
    });
  }
})();
