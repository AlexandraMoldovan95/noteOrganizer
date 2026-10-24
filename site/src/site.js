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
    moon: "M13.5 9.6A5.6 5.6 0 0 1 6.4 2.5a5.6 5.6 0 1 0 7.1 7.1z",
    menu: "M2.5 4.5h11M2.5 8h11M2.5 11.5h11",
    close: "M4 4l8 8M12 4l-8 8"
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
      var setMenu = function (open) {
        nav.classList.toggle("open", open);
        menu.setAttribute("aria-expanded", open ? "true" : "false");
        menu.textContent = "";
        menu.appendChild(drawn(open ? "close" : "menu"));
        menu.setAttribute("aria-label", open ? "Close the menu" : "Menu");
      };
      setMenu(false);
      menu.addEventListener("click", function () { setMenu(!nav.classList.contains("open")); });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && nav.classList.contains("open")) {
          setMenu(false);
          menu.focus();
        }
      });
    }
    revealOnScroll();
    openPicturesLarge();
  });

  // Fade each block in as it scrolls into view: on a doc page (how it's
  // built, in my words, testing...) every top-level block, on the overview
  // each section's heading and each card, picture and figure. Skipped
  // entirely when the visitor's system asks for reduced motion, or when
  // IntersectionObserver is not available -- either way, every block is
  // just shown as normal.
  //
  // The first version was slow and gradual, and read well; what it got
  // wrong, and this one must not: printing gave blank pages, a Contents
  // link landed on text still fading, and a tall table whose visible slice
  // never reached 5% of it stayed invisible (hence threshold 0, measured
  // against the screen less its lowest twelfth).
  var REVEAL =
    ".doc .wrap > h1, .doc .wrap > h2, .doc .wrap > h3, .doc .wrap > p, " +
    ".doc .wrap > ul, .doc .wrap > ol, .doc .wrap > pre, .doc .wrap > blockquote, " +
    ".doc .wrap > hr, .doc .wrap > .table-wrap, .doc .wrap > .pair, .doc .wrap > .phone-gallery, " +
    "main > section:not(.hero) .section-head, main > section:not(.hero) .card, " +
    "main > section:not(.hero) .shot, main > section:not(.hero) .phone-shot, " +
    "main > section:not(.hero) .figures li, main > section:not(.hero) .actions, " +
    ".cta > div:first-child";
  function revealOnScroll() {
    if (!window.IntersectionObserver) return;
    if (!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: no-preference)").matches)) return;
    var items = Array.prototype.slice.call(document.querySelectorAll(REVEAL));
    if (!items.length) return;
    // A jump, or a page opened at an anchor, or printing: every block at
    // once, with no fade to land on.
    function showAll() {
      items.forEach(function (el) { el.classList.add("instant", "in-view"); });
      io.disconnect();
    }
    var io = new IntersectionObserver(function (entries) {
      // Blocks that come into view together -- a row of cards, the first
      // screen on load -- arrive one after another, a tenth of a second
      // apart, in the order they are read.
      var arriving = entries.filter(function (entry) { return entry.isIntersecting; })
        .map(function (entry) { return entry.target; });
      arriving.sort(function (a, b) {
        return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
      });
      arriving.forEach(function (el, i) { arrive(el, Math.min(i, 5) * 100); });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0 });
    // Once it has arrived, a block is let go of: a card's lift under the
    // pointer must not wait out the delay it arrived with.
    function arrive(el, delay) {
      el.style.setProperty("--reveal-delay", delay / 1000 + "s");
      el.classList.add("in-view");
      io.unobserve(el);
      setTimeout(function () {
        el.classList.remove("reveal", "in-view");
        el.style.removeProperty("--reveal-delay");
      }, delay + 700);
    }
    if (location.hash) return;
    items.forEach(function (el) {
      el.classList.add("reveal");
      io.observe(el);
    });
    // At the very end of a page there is no further to scroll, and a last
    // short block in the screen's lowest twelfth would wait for ever.
    window.addEventListener("scroll", function () {
      var doc = document.documentElement;
      if (window.scrollY + window.innerHeight < doc.scrollHeight - 2) return;
      items.forEach(function (el) {
        if (el.classList.contains("reveal") && !el.classList.contains("in-view") &&
            el.getBoundingClientRect().top < window.innerHeight) arrive(el, 0);
      });
    }, { passive: true });
    // Caught on the click, before the browser jumps: hashchange comes only
    // after it, when the text it lands on would already have shown hidden.
    document.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest('a[href^="#"]')) showAll();
    }, true);
    window.addEventListener("hashchange", showAll);
    window.addEventListener("beforeprint", showAll);
  }

  // A picture that links to itself opens large over the page instead of
  // leaving it -- the one the theme shows, where a link holds a dark and a
  // light one. Without JS, or without <dialog>, the link opens the file.
  function openPicturesLarge() {
    var links = document.querySelectorAll("a.zoom, .doc a[href$='.webp']");
    if (!links.length || typeof HTMLDialogElement !== "function") return;
    var box = document.createElement("dialog");
    box.className = "lightbox";
    box.setAttribute("aria-label", "The picture, large");
    var big = document.createElement("img");
    var caption = document.createElement("p");
    caption.textContent = "Click anywhere or press Escape to close.";
    box.appendChild(big);
    box.appendChild(caption);
    document.body.appendChild(box);
    box.addEventListener("click", function () { box.close(); });
    box.addEventListener("close", function () { big.removeAttribute("src"); });
    Array.prototype.forEach.call(links, function (link) {
      link.addEventListener("click", function (e) {
        var shown = Array.prototype.filter.call(link.querySelectorAll("img"), function (img) {
          return img.offsetParent !== null || img.getClientRects().length;
        })[0];
        if (!shown || e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;
        e.preventDefault();
        big.src = shown.currentSrc || shown.src;
        big.alt = shown.alt;
        box.showModal();
      });
    });
  }
})();
