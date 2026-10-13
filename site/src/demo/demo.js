// Note Organizer web demo -- a re-creation of the desktop app's interface.
//
// The real app is Python + Tkinter and cannot run in a browser. This file
// imitates its everyday parts, and where a rule of the app can be followed
// exactly it is followed exactly, ported from the app's own code:
//   - colours: the eight palettes, and the arithmetic that picks the words
//     on a fill or shades a category's colour until it reads
//     (noteorganizer/core/themes.py, via app-data.js);
//   - repeating notes: how a rule expands into days, and how it is described
//     (noteorganizer/core/recurrence.py);
//   - the order of every sort option (noteorganizer/ui/note_list.py);
//   - share codes: "NOTE1:" + Base64(zlib(JSON)), the format the desktop
//     app's Import code box reads (noteorganizer/core/sharing.py).
// Everything is kept in this browser's localStorage and nowhere else.

(function () {
  "use strict";

  var A = window.NO_APP;
  if (!A) {
    document.body.textContent = "The demo could not load its data file (app-data.js).";
    return;
  }

  var KEY = "noteorganizer-demo-v1";
  var WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  var WEEKDAYS_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"];
  var SORTS = ["Recently updated", "Oldest updated", "Title A–Z", "Title Z–A",
               "Category", "Calendar: soonest", "Calendar: oldest"];
  var TRASH_DAYS = 30;
  var PROTECTED = "General";

  // ------------------------------------------------------------------
  // Small helpers
  // ------------------------------------------------------------------

  function $(sel, root) { return (root || document).querySelector(sel); }

  function el(tag, props) {
    var e = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach(function (k) {
        var v = props[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "class") e.className = v;
        else if (k === "text") e.textContent = v;
        else if (k === "vars") Object.keys(v).forEach(function (n) { e.style.setProperty(n, v[n]); });
        else if (k.slice(0, 2) === "on" && typeof v === "function") e.addEventListener(k.slice(2), v);
        else if (v === true) e.setAttribute(k, "");
        else e.setAttribute(k, v);
      });
    }
    for (var i = 2; i < arguments.length; i++) append(e, arguments[i]);
    return e;
  }

  function append(parent, kid) {
    if (kid === null || kid === undefined || kid === false) return;
    if (Array.isArray(kid)) { kid.forEach(function (k) { append(parent, k); }); return; }
    parent.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  }

  function clampInt(value, fallback, lo, hi) {
    var n = parseInt(value, 10);
    if (isNaN(n)) return fallback;
    return Math.max(lo, Math.min(hi, n));
  }

  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var b = new Uint8Array(16);
    (window.crypto || {}).getRandomValues ? crypto.getRandomValues(b)
      : b.forEach(function (_, i) { b[i] = Math.floor(Math.random() * 256); });
    b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
    var h = Array.prototype.map.call(b, function (x) { return (x + 256).toString(16).slice(1); }).join("");
    return h.slice(0, 8) + "-" + h.slice(8, 12) + "-" + h.slice(12, 16) + "-" + h.slice(16, 20) + "-" + h.slice(20);
  }

  function isNarrow() { return window.matchMedia("(max-width: 820px)").matches; }

  // Toolbar pictures drawn as lines, so they look the same in every
  // browser: a font that lacks a symbol draws something else in its place.
  var ICONS = {
    left: "M2 3h12M2 6.5h8M2 10h12M2 13.5h7",
    center: "M2 3h12M4 6.5h8M2 10h12M4.5 13.5h7",
    right: "M2 3h12M6 6.5h8M2 10h12M7 13.5h7",
    table: "M2 2.5h12v11H2zM2 6.5h12M2 10h12M6.5 2.5v11M10.5 2.5v11",
    // Indent less and more: the lines pushed in, and an arrow which way.
    outdent: "M2 3h12M8 6.5h6M8 10h6M2 13.5h12M5.5 5.8L3 8.25l2.5 2.45",
    indent: "M2 3h12M8 6.5h6M8 10h6M2 13.5h12M3 5.8l2.5 2.45L3 10.7",
    sun: "M8 5.2a2.8 2.8 0 1 0 0 5.6a2.8 2.8 0 1 0 0-5.6M8 1v1.6M8 13.4V15M1 8h1.6M13.4 8H15" +
         "M3 3l1.1 1.1M11.9 11.9L13 13M3 13l1.1-1.1M11.9 4.1L13 3",
    moon: "M13.5 9.6A5.6 5.6 0 0 1 6.4 2.5a5.6 5.6 0 1 0 7.1 7.1z"
  };
  function icon(name) {
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    [["viewBox", "0 0 16 16"], ["width", "17"], ["height", "17"], ["aria-hidden", "true"], ["fill", "none"],
     ["stroke", "currentColor"], ["stroke-width", "1.6"], ["stroke-linecap", "round"], ["stroke-linejoin", "round"]]
      .forEach(function (a) { svg.setAttribute(a[0], a[1]); });
    var path = document.createElementNS(ns, "path");
    path.setAttribute("d", ICONS[name]);
    svg.appendChild(path);
    return svg;
  }

  // ------------------------------------------------------------------
  // Colour arithmetic, ported from noteorganizer/core/themes.py
  // ------------------------------------------------------------------

  function rgb(h) { return [1, 3, 5].map(function (i) { return parseInt(h.slice(i, i + 2), 16); }); }
  function hex(c) {
    return "#" + c.map(function (v) {
      return Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0");
    }).join("");
  }
  function blend(a, b, t) {
    var x = rgb(a), y = rgb(b);
    return hex(x.map(function (v, i) { return v + (y[i] - v) * t; }));
  }
  function luminance(h) {
    var c = rgb(h).map(function (v) {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function contrast(a, b) {
    var la = luminance(a), lb = luminance(b);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  }
  var LETTERS_LIGHT = "#ffffff", LETTERS_DARK = "#1a1a1a";
  function lettersOn(fill) {
    try {
      return contrast(LETTERS_DARK, fill) > contrast(LETTERS_LIGHT, fill) ? LETTERS_DARK : LETTERS_LIGHT;
    } catch (e) { return LETTERS_LIGHT; }
  }
  function rgbToHsv(r, g, b) {
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    if (mx === mn) return [0, 0, mx];
    var s = (mx - mn) / mx;
    var rc = (mx - r) / (mx - mn), gc = (mx - g) / (mx - mn), bc = (mx - b) / (mx - mn);
    var h = r === mx ? bc - gc : g === mx ? 2 + rc - bc : 4 + gc - rc;
    h = ((h / 6) % 1 + 1) % 1;
    return [h, s, mx];
  }
  function hsvToRgb(h, s, v) {
    if (s === 0) return [v, v, v];
    var i = Math.floor(h * 6), f = h * 6 - i;
    var p = v * (1 - s), q = v * (1 - s * f), t = v * (1 - s * (1 - f));
    return [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][i % 6];
  }
  // A colour the person picked, shown as words: itself where it reads,
  // else the nearest shade of it that does (themes.legible_on).
  var legibleCache = {};
  function legibleOn(colour, ground, ink, minimum) {
    minimum = minimum || 4.6;
    var key = colour + ground + ink + minimum;
    if (legibleCache[key]) return legibleCache[key];
    var answer = ink;
    try {
      if (contrast(colour, ground) >= minimum) answer = colour;
      else if (contrast(LETTERS_DARK, ground) >= contrast(LETTERS_LIGHT, ground)) {
        var c = rgb(colour).map(function (v) { return v / 255; });
        var hsv = rgbToHsv(c[0], c[1], c[2]);
        for (var step = 1; step <= 100; step++) {
          var shade = hsvToRgb(hsv[0], Math.min(1, hsv[1] * (1 + step / 200)), hsv[2] * (1 - step / 100));
          var darker = hex(shade.map(function (x) { return x * 255; }));
          if (contrast(darker, ground) >= minimum) { answer = darker; break; }
        }
      } else {
        for (var k = 1; k <= 20; k++) {
          var mixed = blend(colour, ink, k / 20);
          if (contrast(mixed, ground) >= minimum) { answer = mixed; break; }
        }
      }
    } catch (e) { answer = ink; }
    legibleCache[key] = answer;
    return answer;
  }

  // ------------------------------------------------------------------
  // Dates. Stored as YYYY-MM-DD, shown day first, as the app does.
  // ------------------------------------------------------------------

  function pad(n) { return String(n).padStart(2, "0"); }
  function iso(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function make(y, m, d) {
    var x = new Date(y, m - 1, d);
    return x.getFullYear() === y && x.getMonth() === m - 1 && x.getDate() === d ? x : null;
  }
  function parseIso(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || "");
    return m ? make(+m[1], +m[2], +m[3]) : null;
  }
  function showDate(s) {
    var d = parseIso(s);
    return d ? pad(d.getDate()) + "." + pad(d.getMonth() + 1) + "." + d.getFullYear() : "";
  }
  function longDate(d) {
    return WEEKDAYS_LONG[weekday(d)] + ", " + d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear();
  }
  function today() { var d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
  function addDays(d, n) { var x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); x.setDate(x.getDate() + n); return x; }
  function daysBetween(a, b) { return Math.round((b - a) / 86400000); }
  function weekday(d) { return (d.getDay() + 6) % 7; }

  // A date as people write it: 14.09.2026, 14/9/2026, 2026-09-14,
  // 14 Sep 2026, September 14, 2026, today, tomorrow. Returns YYYY-MM-DD,
  // "" for an empty box, or null when the text is not a real day.
  function readDate(text) {
    var t = String(text || "").trim().toLowerCase().replace(/\s+/g, " ");
    if (!t) return "";
    if (t === "today") return iso(today());
    if (t === "tomorrow") return iso(addDays(today(), 1));
    if (t === "yesterday") return iso(addDays(today(), -1));
    var m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(t), d;
    if (m) { d = make(+m[1], +m[2], +m[3]); return d ? iso(d) : null; }
    m = /^(\d{1,2})[.\/\- ](\d{1,2})[.\/\- ](\d{2}|\d{4})\.?$/.exec(t);
    if (m) {
      var y = +m[3]; if (y < 100) y += 2000;
      d = make(y, +m[2], +m[1]); return d ? iso(d) : null;
    }
    function month(word) {
      for (var i = 0; i < 12; i++) {
        var name = MONTHS[i].toLowerCase();
        if (word.length >= 3 && name.indexOf(word) === 0) return i + 1;
      }
      return 0;
    }
    m = /^(\d{1,2})(?:st|nd|rd|th)? ([a-z]+)\.?,? (\d{4})$/.exec(t);
    if (m && month(m[2])) { d = make(+m[3], month(m[2]), +m[1]); return d ? iso(d) : null; }
    m = /^([a-z]+)\.? (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})$/.exec(t);
    if (m && month(m[1])) { d = make(+m[3], month(m[1]), +m[2]); return d ? iso(d) : null; }
    return null;
  }

  // ------------------------------------------------------------------
  // Repeating notes, ported from noteorganizer/core/recurrence.py
  // ------------------------------------------------------------------

  function normRec(r) {
    r = r && typeof r === "object" ? r : {};
    var out = {
      freq: ["daily", "weekly", "monthly", "yearly"].indexOf(r.freq) >= 0 ? r.freq : "",
      interval: clampInt(r.interval, 1, 1, 1000),
      weekdays: [], month_days: [],
      month_day_policy: r.month_day_policy === "skip" ? "skip" : "clamp",
      end: "", count: clampInt(r.count, 0, 0, 5000)
    };
    if (Array.isArray(r.weekdays)) {
      out.weekdays = r.weekdays.filter(function (d, i, a) {
        return Number.isInteger(d) && d >= 0 && d <= 6 && a.indexOf(d) === i;
      }).sort(function (a, b) { return a - b; });
    }
    if (Array.isArray(r.month_days)) {
      out.month_days = r.month_days.filter(function (d, i, a) {
        return Number.isInteger(d) && d >= 1 && d <= 31 && a.indexOf(d) === i;
      }).sort(function (a, b) { return a - b; });
    }
    var end = readDate(r.end);
    out.end = end || "";
    return out;
  }

  function describeRec(rec) {
    rec = normRec(rec);
    if (!rec.freq) return "";
    var unit = { daily: "day", weekly: "week", monthly: "month", yearly: "year" }[rec.freq];
    var base = rec.interval === 1 ? "Every " + unit : "Every " + rec.interval + " " + unit + "s";
    if (rec.freq === "weekly" && rec.weekdays.length) {
      base += " on " + rec.weekdays.map(function (d) { return WEEKDAYS[d]; }).join(", ");
    } else if (rec.freq === "monthly" && rec.month_days.length) {
      base += " on day " + rec.month_days.join(", ");
    }
    if (rec.count) base += ", " + rec.count + " times";
    else if (rec.end) base += ", until " + showDate(rec.end);
    return base;
  }

  // Every day the note lands on between rangeStart and rangeEnd, inclusive,
  // as YYYY-MM-DD strings (recurrence.expand_occurrences).
  function occurrences(note, rangeStart, rangeEnd, limit) {
    var anchor = parseIso(note.date);
    if (!anchor) return [];
    var rec = normRec(note.recurrence);
    if (!rec.freq) return anchor >= rangeStart && anchor <= rangeEnd ? [iso(anchor)] : [];
    var interval = rec.interval, endDate = parseIso(rec.end), maxCount = rec.count;
    var horizon = endDate && endDate < rangeEnd ? endDate : rangeEnd;
    if (horizon < anchor) return [];
    var out = [], produced = 0, limited = maxCount > 0, guard = 0;

    function take(c) {
      if (c < anchor) return true;
      if (endDate && c > endDate) return false;
      produced += 1;
      if (c >= rangeStart && c <= rangeEnd) {
        out.push(iso(c));
        if (limit && out.length >= limit) return false;
      }
      return !(limited && produced >= maxCount);
    }

    var cur, stop;
    if (rec.freq === "daily") {
      cur = anchor;
      if (!limited && rangeStart > anchor) {
        cur = addDays(anchor, Math.floor(daysBetween(anchor, rangeStart) / interval) * interval);
      }
      while (cur <= horizon && guard++ < 5000) {
        if (!take(cur)) break;
        cur = addDays(cur, interval);
      }
    } else if (rec.freq === "weekly") {
      var days = rec.weekdays.length ? rec.weekdays : [weekday(anchor)];
      var weekStart = addDays(anchor, -weekday(anchor));
      if (!limited && rangeStart > anchor) {
        var ahead = Math.floor(daysBetween(weekStart, rangeStart) / (7 * interval));
        if (ahead > 0) weekStart = addDays(weekStart, ahead * 7 * interval);
      }
      stop = false;
      while (weekStart <= horizon && guard++ < 5000 && !stop) {
        for (var i = 0; i < days.length; i++) {
          var c = addDays(weekStart, days[i]);
          if (c > horizon) continue;
          if (!take(c)) { stop = true; break; }
        }
        weekStart = addDays(weekStart, 7 * interval);
      }
    } else if (rec.freq === "monthly") {
      var monthDays = rec.month_days.length ? rec.month_days : [anchor.getDate()];
      var k = 0;
      if (!limited && rangeStart > anchor) {
        var months = (rangeStart.getFullYear() - anchor.getFullYear()) * 12 + rangeStart.getMonth() - anchor.getMonth();
        k = Math.max(0, Math.floor(months / interval));
      }
      stop = false;
      while (guard++ < 5000 && !stop) {
        var total = anchor.getMonth() + k * interval;
        var y = anchor.getFullYear() + Math.floor(total / 12), m = total % 12;
        if (y > horizon.getFullYear() || (y === horizon.getFullYear() && m > horizon.getMonth())) break;
        var last = new Date(y, m + 1, 0).getDate(), landed = [];
        monthDays.forEach(function (d) {
          var day = d <= last ? d : (rec.month_day_policy === "clamp" ? last : 0);
          if (day && landed.indexOf(day) < 0) landed.push(day);
        });
        landed.sort(function (a, b) { return a - b; });
        for (var j = 0; j < landed.length; j++) {
          var cd = new Date(y, m, landed[j]);
          if (cd > horizon) break;
          if (!take(cd)) { stop = true; break; }
        }
        k += 1;
      }
    } else if (rec.freq === "yearly") {
      var ky = 0;
      if (!limited && rangeStart > anchor) {
        ky = Math.max(0, Math.floor((rangeStart.getFullYear() - anchor.getFullYear()) / interval));
      }
      while (guard++ < 5000) {
        var yy = anchor.getFullYear() + ky * interval;
        if (yy > horizon.getFullYear()) break;
        var lastDay = new Date(yy, anchor.getMonth() + 1, 0).getDate();
        var cy = new Date(yy, anchor.getMonth(), Math.min(anchor.getDate(), lastDay));
        if (cy > horizon) break;
        if (!take(cy)) break;
        ky += 1;
      }
    }
    return out;
  }

  function nextOccurrence(note, fromIso) {
    var from = parseIso(fromIso);
    var hits = occurrences(note, from, addDays(from, 366 * 4), 1);
    return hits[0] || "";
  }

  // ------------------------------------------------------------------
  // Rich text: a whitelist for what is stored and shown
  // ------------------------------------------------------------------

  // A style is kept on bold, italic and the rest as on a span: a browser
  // asked to colour, or set a font on, text that is exactly one bold run
  // puts the style on the <b> itself, and dropping it here lost the colour
  // or the font the moment the note was saved.
  var ALLOWED = {
    B: ["style"], STRONG: ["style"], I: ["style"], EM: ["style"], U: ["style"], S: ["style"],
    STRIKE: ["style"], DEL: ["style"],
    SPAN: ["style"], FONT: ["color"], BR: [], DIV: ["style", "data-indent"], P: ["style", "data-indent"],
    UL: [], OL: [], LI: ["style", "data-indent"], TABLE: [], THEAD: [], TBODY: [], TR: [], TD: [], TH: []
  };
  var DROPPED = ["SCRIPT", "STYLE", "IFRAME", "OBJECT", "EMBED", "TEMPLATE", "SVG",
                 "MATH", "IMG", "VIDEO", "AUDIO", "LINK", "META", "BUTTON", "INPUT",
                 "TEXTAREA", "SELECT", "FORM", "NOSCRIPT"];

  // A font the app offers, by the name it stores, or "" -- a browser writes
  // a family in quotes, and may list fallbacks after it.
  function appFamily(css) {
    var name = String(css || "").split(",")[0].trim().replace(/^["']|["']$/g, "");
    return A.fontFamilies.indexOf(name) >= 0 ? name : "";
  }
  // A size the app offers, in points as it stores them, or 0.
  function appSize(css) {
    var m = /^(\d+)pt$/.exec(String(css || "").trim());
    return m && A.fontSizes.indexOf(+m[1]) >= 0 ? +m[1] : 0;
  }
  // How far a line is pushed in, as the app counts it: 1 to its maximum.
  function appIndent(value) {
    var n = parseInt(value, 10);
    return n >= 1 ? Math.min(n, A.maxIndent) : 0;
  }

  function cleanStyle(style) {
    var keep = [];
    var colour = style.getPropertyValue("color");
    var ground = style.getPropertyValue("background-color");
    var align = style.getPropertyValue("text-align");
    var family = appFamily(style.getPropertyValue("font-family"));
    var size = appSize(style.getPropertyValue("font-size"));
    if (colour) keep.push("color: " + colour);
    if (ground) keep.push("background-color: " + ground);
    if (/^(left|center|right|justify)$/.test(align)) keep.push("text-align: " + align);
    // Only the app's own fonts and sizes: a note keeps what it can carry.
    if (family) keep.push('font-family: "' + family + '"');
    if (size) keep.push("font-size: " + size + "pt");
    return keep.join("; ");
  }

  function copyClean(src, dst) {
    Array.prototype.forEach.call(src.childNodes, function (node) {
      if (node.nodeType === 3) {
        dst.appendChild(document.createTextNode(node.nodeValue));
      } else if (node.nodeType === 1) {
        var tag = node.tagName;
        if (ALLOWED[tag]) {
          var e = document.createElement(tag.toLowerCase());
          ALLOWED[tag].forEach(function (a) {
            if (a === "style") {
              var st = cleanStyle(node.style);
              if (st) e.setAttribute("style", st);
            } else if (a === "color") {
              var c = node.getAttribute("color");
              if (c && /^#[0-9a-f]{3,6}$/i.test(c)) e.setAttribute("color", c);
            } else if (a === "data-indent") {
              var level = appIndent(node.getAttribute("data-indent"));
              if (level) e.setAttribute("data-indent", String(level));
            }
          });
          copyClean(node, e);
          dst.appendChild(e);
        } else if (DROPPED.indexOf(tag) < 0) {
          copyClean(node, dst);
        }
      }
    });
  }

  function sanitizeHtml(html) {
    var doc = new DOMParser().parseFromString("<body>" + (html || "") + "</body>", "text/html");
    var out = document.createElement("div");
    copyClean(doc.body, out);
    return out.innerHTML;
  }

  var textCache = {};
  function plainText(html) {
    if (textCache[html] !== undefined) return textCache[html];
    var doc = new DOMParser().parseFromString("<body>" + (html || "") + "</body>", "text/html");
    var parts = [];
    (function walk(node) {
      Array.prototype.forEach.call(node.childNodes, function (n) {
        if (n.nodeType === 3) parts.push(n.nodeValue);
        else if (n.nodeType === 1) {
          var block = /^(DIV|P|LI|TR|BR|TABLE|UL|OL)$/.test(n.tagName);
          if (block) parts.push("\n");
          walk(n);
          if (n.tagName === "TD" || n.tagName === "TH") parts.push(" ");
          if (block) parts.push("\n");
        }
      });
    })(doc.body);
    var text = parts.join("").replace(/[ \t]+\n/g, "\n").replace(/\n{2,}/g, "\n").trim();
    textCache[html] = text;
    return text;
  }

  // ------------------------------------------------------------------
  // State
  // ------------------------------------------------------------------

  var S = null;
  var storageOk = true;

  function blankNote(extra) {
    var now = Date.now();
    var n = {
      id: S ? S.nextId++ : 0, uid: uuid(), title: "", html: "", comments: "",
      category: PROTECTED, date: "", color: "", recurrence: normRec({}),
      checklist: [], pinned: false, created: now, updated: now
    };
    Object.keys(extra || {}).forEach(function (k) { n[k] = extra[k]; });
    return n;
  }

  function seed() {
    var t = today(), monday = addDays(t, -weekday(t));
    function day(n) { return iso(addDays(t, n)); }
    var state = {
      v: 1, nextId: 1, notes: [], trash: [], dayMarks: {}, dayColors: {},
      categories: Object.keys(A.categoryColors).map(function (name) {
        return { name: name, color: A.categoryColors[name] };
      }),
      theme: window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark",
      ui: { sort: SORTS[0], show: "All", group: false, openId: null, tab: "notes",
            calMonth: iso(t).slice(0, 7), selDay: null, section: "appearance" }
    };
    S = state;
    var clock = Date.now();
    function add(fields) {
      clock -= 3600 * 1000;
      var n = blankNote(fields);
      n.created = n.updated = clock;
      state.notes.push(n);
      return n;
    }
    var welcome = add({
      title: "Welcome to the demo \u{1F44B}", pinned: true,
      html: "<div>This page is a re-creation of Note Organizer's interface, so you can try it " +
        "without installing anything. The real app is a Windows program; what you do here is " +
        "kept in this browser only.</div><div><br></div>" +
        "<div><b>✍ Write</b></div><ul><li><b>+ New Note</b> starts a note. Give it a title " +
        "and write; it saves itself as you go.</li><li>The toolbar shapes your words: bold, " +
        "fonts and sizes, colours, highlights, lists, indents, alignment, emoji, and tables." +
        "</li><li>Under the text you'll " +
        "find a checklist for to-dos and a box for comments.</li></ul>" +
        "<div><b>\u{1F5C2} Organise</b></div><ul><li>The search box above the list looks through " +
        "all your notes at once.</li><li><b>Sort</b> and <b>Show</b> arrange the list, and " +
        "<b>Group by category</b> gathers notes together.</li><li>Right-click a note, or press " +
        "its ⋯, to pin it, move it to a category, duplicate it or delete it.</li></ul>" +
        "<div><b>\u{1F4C5} Plan</b></div><ul><li>Give a note a date and it appears on the " +
        "<b>Calendar</b>. A note can repeat daily, weekly, monthly or yearly.</li></ul>" +
        "<div><b>\u{1F512} Share and keep safe</b></div><ul><li><b>Generate code</b> turns a " +
        "note into a share code; <b>Import code</b> brings one in.</li><li>Deleted notes wait " +
        "in <b>Settings → Recently deleted</b>, so a slip can be undone.</li></ul>" +
        "<div><b>\u{1F3A8} Make it yours</b></div><ul><li>Pick one of eight light and dark " +
        "themes in <b>Settings → Appearance</b>, or switch with the ☀ / \u{1F319} " +
        "button on the toolbar.</li></ul><div><br></div>" +
        "<div>The desktop app does more than this page: attachments, templates, backups, " +
        "statistics, finding duplicates, editing one day of a repeating note on its own, and " +
        "a list you can arrange by hand.</div>"
    });
    add({
      title: "Weekly meal plan", color: "#7c5cff", date: day(2),
      html: "<div>Shopping on Sunday; batch-cook the soup.</div>" +
        "<table><tbody><tr><th>Day</th><th>Lunch</th><th>Dinner</th></tr>" +
        "<tr><td>Monday</td><td>Soup</td><td>Pasta</td></tr>" +
        "<tr><td>Tuesday</td><td>Salad</td><td>Tacos</td></tr>" +
        "<tr><td>Wednesday</td><td>Leftovers</td><td>Grilled fish</td></tr>" +
        "<tr><td>Thursday</td><td>Wraps</td><td>Stir-fry</td></tr></tbody></table>"
    });
    add({ title: "Bike service", date: day(4), html: "<div>Book it before the weekend ride.</div>" });
    add({ title: "Quarterly review", category: "Work",
          html: "<div>Numbers for the board pack, the team's targets.</div>",
          comments: "Ask finance for the latest figures." });
    add({ title: "Reading list", category: "Personal",
          html: "<div>Three books before the holidays.</div>",
          checklist: [{ text: "A novel for the train", done: true },
                      { text: "The book club pick", done: false },
                      { text: "Something about design", done: false }] });
    add({ title: "Shopping list", html: "<div>Milk, bread, coffee, olive oil.</div>",
          checklist: [{ text: "Milk", done: true }, { text: "Bread", done: true },
                      { text: "Coffee", done: false }, { text: "Olive oil", done: false }] });
    // Started four weeks back, so the series reaches every Monday of the
    // month the visitor opens the calendar on, whatever day that is.
    add({ title: "Team stand-up", category: "Work", date: iso(addDays(monday, -28)),
          recurrence: normRec({ freq: "weekly", interval: 1, weekdays: [0] }),
          html: "<div>What we shipped, what is stuck, what is next.</div>",
          comments: "Room 2 is booked for the whole quarter." });
    add({ title: "Dentist", category: "Personal", date: day(6), html: "<div>Check-up at 10:30.</div>" });
    add({ title: "Board review", category: "Work", date: day(10), html: "<div>Slides ready the day before.</div>" });
    state.dayMarks[day(13)] = ["✈"];
    state.ui.openId = welcome.id;
    return state;
  }

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) {
        var s = JSON.parse(raw);
        if (s && s.v === 1 && Array.isArray(s.notes) && Array.isArray(s.categories)) {
          S = s;
          S.trash = Array.isArray(S.trash) ? S.trash : [];
          S.dayMarks = S.dayMarks || {};
          S.dayColors = S.dayColors || {};
          S.ui = S.ui || {};
          if (SORTS.indexOf(S.ui.sort) < 0) S.ui.sort = SORTS[0];
          if (!A.themes[S.theme]) S.theme = "dark";
          S.notes.forEach(function (n) { n.recurrence = normRec(n.recurrence); });
          purgeTrash();
          return;
        }
      }
    } catch (e) { /* unreadable: start again from the sample notebook */ }
    S = null;
    S = seed();
  }

  function persist() {
    try {
      localStorage.setItem(KEY, JSON.stringify(S));
    } catch (e) {
      if (storageOk) toast("This browser is not keeping the demo's notes; they last until you close the page.");
      storageOk = false;
    }
  }

  function purgeTrash() {
    var limit = Date.now() - TRASH_DAYS * 86400000;
    S.trash = S.trash.filter(function (t) { return t.deletedAt > limit; });
  }

  function noteById(id) {
    for (var i = 0; i < S.notes.length; i++) if (S.notes[i].id === id) return S.notes[i];
    return null;
  }
  function current() { return noteById(S.ui.openId); }
  function category(name) {
    for (var i = 0; i < S.categories.length; i++) if (S.categories[i].name === name) return S.categories[i];
    return S.categories[0];
  }

  // ------------------------------------------------------------------
  // Theme
  // ------------------------------------------------------------------

  var P = null; // the palette in use

  function applyTheme(key) {
    P = A.themes[key] || A.themes.dark;
    var root = document.documentElement.style;
    var set = function (k, v) { root.setProperty(k, v); };
    set("--bg", P.bg); set("--sidebar", P.sidebar); set("--card", P.card);
    set("--accent", P.accent); set("--accent-hover", P.accent_hover);
    set("--text", P.text); set("--subtext", P.subtext);
    set("--danger", P.danger); set("--success", P.success);
    set("--accent-text", P.accent_text); set("--danger-text", P.danger_text);
    set("--success-text", P.success_text); set("--find-miss", P.find_miss);
    set("--check-well", P.check_well);
    set("--on-accent", lettersOn(P.accent)); set("--on-danger", lettersOn(P.danger));
    set("--on-success", lettersOn(P.success));
    set("--inset", blend(P.card, P.text, 0.07));
    set("--line", blend(P.card, P.subtext, 0.22));
    set("--find-all", blend(P.card, P.accent, 0.35));
    document.documentElement.style.colorScheme = A.darkThemes.indexOf(key) >= 0 ? "dark" : "light";
  }

  function setTheme(key) {
    S.theme = key;
    applyTheme(key);
    persist();
    renderAll();
  }

  // The toolbar's sun/moon: the same family, the other side.
  function partnerTheme(key) {
    var d = A.darkThemes.indexOf(key), l = A.lightThemes.indexOf(key);
    if (d >= 0) return A.lightThemes[d] || A.lightThemes[0];
    if (l >= 0) return A.darkThemes[l] || A.darkThemes[0];
    return "dark";
  }
  function isDark() { return A.darkThemes.indexOf(S.theme) >= 0; }

  // ------------------------------------------------------------------
  // Toast, popups, dialogs
  // ------------------------------------------------------------------

  var toastTimer = null;
  function toast(message) {
    var t = $("#toast");
    t.textContent = message;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove("show"); }, 2600);
  }

  var openPopup = null;
  function closePopup() {
    if (!openPopup) return;
    var p = openPopup;
    openPopup = null;
    p.el.remove();
    if (p.returnFocus && document.body.contains(p.returnFocus)) p.returnFocus.focus();
  }

  // A popup anchored to an element, or to a point (x, y).
  function popup(content, anchor, opts) {
    closePopup();
    opts = opts || {};
    var box = el("div", { class: "popup " + (opts.cls || ""), role: opts.role || "menu" }, content);
    $("#layer").appendChild(box);
    var r;
    if (anchor && anchor.getBoundingClientRect) r = anchor.getBoundingClientRect();
    else r = { left: anchor.x, right: anchor.x, top: anchor.y, bottom: anchor.y };
    var w = box.offsetWidth, h = box.offsetHeight;
    var vw = window.innerWidth, vh = window.innerHeight;
    var left = opts.alignRight ? r.right - w : r.left;
    left = Math.max(8, Math.min(left, vw - w - 8));
    var top = r.bottom + 4;
    if (top + h > vh - 8) top = Math.max(8, r.top - h - 4);
    box.style.left = left + "px";
    box.style.top = top + "px";
    openPopup = { el: box, returnFocus: opts.returnFocus || (anchor && anchor.focus ? anchor : null) };
    var first = box.querySelector("button, input");
    if (first && !opts.noFocus) first.focus();
    return box;
  }

  document.addEventListener("pointerdown", function (e) {
    if (openPopup && !openPopup.el.contains(e.target)) {
      openPopup.returnFocus = null;
      closePopup();
    }
  }, true);
  window.addEventListener("resize", function () { closePopup(); });

  function menuItem(label, action, cls) {
    return el("button", { type: "button", class: "menu-item " + (cls || ""), role: "menuitem",
      onclick: function () { closePopup(); action(); } }, label);
  }

  // Menus walk with the arrow keys, as the app's do.
  document.addEventListener("keydown", function (e) {
    if (!openPopup) return;
    if (e.key === "Escape") { e.preventDefault(); closePopup(); return; }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      var items = Array.prototype.slice.call(openPopup.el.querySelectorAll(".menu-item"));
      if (!items.length) return;
      e.preventDefault();
      var i = items.indexOf(document.activeElement);
      i = e.key === "ArrowDown" ? (i + 1) % items.length : (i - 1 + items.length) % items.length;
      items[i].focus();
    }
  });

  // A blocking question. Resolves with the value of the button pressed;
  // Escape gives `cancel`. Enter presses the default button.
  function dialog(opts) {
    closePopup();
    return new Promise(function (resolve) {
      var before = document.activeElement;
      var back = el("div", { class: "backdrop" });
      var box = el("div", { class: "dialog", role: "dialog", "aria-modal": "true", "aria-labelledby": "dlg-title" },
        el("h2", { id: "dlg-title", text: opts.title }),
        opts.text ? el("p", { text: opts.text }) : null,
        opts.body || null);
      var row = el("div", { class: "row" });
      var defaultBtn = null;
      function done(value) {
        back.remove();
        document.removeEventListener("keydown", onKey, true);
        if (before && document.body.contains(before)) before.focus();
        resolve(value);
      }
      (opts.buttons || [{ label: "OK", value: true, cls: "btn-accent", isDefault: true }]).forEach(function (b) {
        var btn = el("button", { type: "button", class: b.cls || "btn-quiet", text: b.label,
          onclick: function () {
            if (b.handler) { if (b.handler() === false) return; }
            done(b.value);
          } });
        if (b.isDefault) defaultBtn = btn;
        row.appendChild(btn);
      });
      box.appendChild(row);
      back.appendChild(box);
      back.addEventListener("pointerdown", function (e) { if (e.target === back) done(opts.cancel); });
      function onKey(e) {
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); done(opts.cancel); }
        else if (e.key === "Enter" && defaultBtn && e.target.tagName !== "TEXTAREA"
                 && e.target.tagName !== "BUTTON") { e.preventDefault(); defaultBtn.click(); }
        else if (e.key === "Tab") {
          var f = box.querySelectorAll("button, input, textarea, select");
          if (!f.length) return;
          if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
          else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
        }
      }
      document.addEventListener("keydown", onKey, true);
      $("#layer").appendChild(back);
      var focus = opts.focus ? box.querySelector(opts.focus) : defaultBtn || box.querySelector("button");
      if (focus) focus.focus();
    });
  }

  function swatchGrid(colours, selected, pick, extra) {
    var grid = el("div", { class: "swatches", role: "group" });
    colours.forEach(function (c) {
      grid.appendChild(el("button", { type: "button", "aria-label": c, title: c, vars: { "--c": c },
        "aria-pressed": c === selected ? "true" : "false",
        onclick: function () { closePopup(); pick(c); } }));
    });
    return el("div", null, grid, extra || null);
  }

  // ------------------------------------------------------------------
  // Saving: a moment after typing stops, and at once on leaving a note
  // ------------------------------------------------------------------

  var saveTimer = null, dirty = false;

  function touched() {
    dirty = true;
    setStatus("");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () { flush(true); }, 700);
  }

  function flush(announce) {
    clearTimeout(saveTimer);
    if (!dirty) return;
    dirty = false;
    var n = current();
    if (n) {
      var body = $("#ed-body");
      if (body) n.html = sanitizeHtml(body.innerHTML);
      n.updated = Date.now();
    }
    persist();
    renderList();
    if (S.ui.tab === "cal") renderCalendar();
    if (announce) setStatus("Auto-saved");
  }

  function setStatus(text) {
    var s = $("#ed-status");
    if (s) s.textContent = text;
  }

  // ------------------------------------------------------------------
  // The note list
  // ------------------------------------------------------------------

  function haystack(n) {
    return [n.title, plainText(n.html), n.comments,
            n.checklist.map(function (c) { return c.text; }).join(" "), n.category]
      .join(" \n ").toLowerCase();
  }

  function sortNotes(list, choice) {
    var t = iso(today());
    function inv(d) { return d.split("").map(function (c) { return String.fromCharCode(0xffff - c.charCodeAt(0)); }).join(""); }
    function cmp(a, b) { return a < b ? -1 : a > b ? 1 : 0; }
    function titleKey(n) { return [n.title.trim() ? 0 : 1, n.title.toLowerCase()]; }
    var keyed = list.map(function (n, i) { return { n: n, i: i }; });
    var key;
    if (choice === "Recently updated") key = function (n) { return [-n.updated]; };
    else if (choice === "Oldest updated") key = function (n) { return [n.updated]; };
    else if (choice === "Title A–Z") key = titleKey;
    else if (choice === "Title Z–A") key = function (n) { var k = titleKey(n); return [-k[0], inv(k[1])]; };
    else if (choice === "Category") key = function (n) { return [n.category, n.updated]; };
    else if (choice === "Calendar: soonest") {
      key = function (n) {
        if (normRec(n.recurrence).freq) {
          var nxt = nextOccurrence(n, t);
          if (nxt) return [0, nxt];
          return parseIso(n.date) ? [1, inv(n.date)] : [2, ""];
        }
        if (!parseIso(n.date)) return [2, ""];
        return n.date >= t ? [0, n.date] : [1, inv(n.date)];
      };
    } else key = function (n) { return parseIso(n.date) ? [0, n.date] : [1, ""]; };
    keyed.forEach(function (k) { k.key = key(k.n); });
    keyed.sort(function (a, b) {
      if (a.n.pinned !== b.n.pinned) return a.n.pinned ? -1 : 1;
      for (var i = 0; i < a.key.length; i++) {
        var c = cmp(a.key[i], b.key[i]);
        if (c) return c;
      }
      return a.i - b.i;
    });
    return keyed.map(function (k) { return k.n; });
  }

  function visibleNotes() {
    var q = $("#search").value.trim().toLowerCase();
    var list = S.notes.filter(function (n) {
      if (S.ui.show === "\u{1F4CC} Pinned" && !n.pinned) return false;
      if (S.ui.show !== "All" && S.ui.show !== "\u{1F4CC} Pinned" && n.category !== S.ui.show) return false;
      return !q || haystack(n).indexOf(q) >= 0;
    });
    return sortNotes(list, S.ui.sort);
  }

  function marked(text, q) {
    var frag = document.createDocumentFragment();
    if (!q) { frag.appendChild(document.createTextNode(text)); return frag; }
    var lower = text.toLowerCase(), at = 0, i;
    while ((i = lower.indexOf(q, at)) >= 0) {
      frag.appendChild(document.createTextNode(text.slice(at, i)));
      frag.appendChild(el("mark", { text: text.slice(i, i + q.length) }));
      at = i + q.length;
    }
    frag.appendChild(document.createTextNode(text.slice(at)));
    return frag;
  }

  function cardFor(n, q) {
    var cat = category(n.category);
    var stripe = n.color || cat.color;
    var rec = normRec(n.recurrence);
    var text = plainText(n.html).replace(/\s+/g, " ");
    var preview = text;
    if (q && text.toLowerCase().indexOf(q) > 60) {
      var at = text.toLowerCase().indexOf(q);
      preview = "…" + text.slice(at - 30);
    }
    if (preview.length > 140) preview = preview.slice(0, 140) + "…";
    var done = n.checklist.filter(function (c) { return c.done; }).length;
    var meta = el("span", { class: "nc-meta" },
      el("span", { class: "nc-cat", text: cat.name }),
      rec.freq ? el("span", { class: "nc-date", text: "\u{1F501} " + describeRec(rec) })
        : n.date ? el("span", { class: "nc-date", text: "\u{1F4C5} " + showDate(n.date) }) : null,
      n.comments.trim() ? el("span", { class: "nc-sub", title: "Has comments", text: "\u{1F4AC}" }) : null,
      n.checklist.length ? el("span", { class: "nc-sub", text: "☑ " + done + "/" + n.checklist.length }) : null);
    var title = el("span", { class: "nc-title" });
    if (n.pinned) title.appendChild(document.createTextNode("\u{1F4CC} "));
    title.appendChild(marked(n.title.trim() || "Untitled", q));
    var open = el("button", { type: "button", class: "nc-open",
      "aria-current": n.id === S.ui.openId ? "true" : "false",
      onclick: function () { openNote(n.id); } },
      title, el("span", { class: "nc-preview" }, marked(preview, q)), meta);
    var more = el("button", { type: "button", class: "nc-more", "aria-label": "More for " + (n.title || "Untitled"),
      "aria-haspopup": "menu", onclick: function (e) { e.stopPropagation(); cardMenu(n, more); } }, "⋯");
    var card = el("div", { class: "note-card" + (n.id === S.ui.openId ? " current" : ""), role: "listitem",
      vars: { "--stripe": stripe, "--catlabel": legibleOn(cat.color, P.card, P.text) } }, open, more);
    card.addEventListener("contextmenu", function (e) {
      e.preventDefault();
      cardMenu(n, { x: e.clientX, y: e.clientY }, open);
    });
    return card;
  }

  function renderList() {
    var listEl = $("#note-list");
    var q = $("#search").value.trim().toLowerCase();
    var notes = visibleNotes();
    var focusedId = document.activeElement && document.activeElement.closest &&
      document.activeElement.closest(".note-card") ? S.ui.openId : null;
    listEl.textContent = "";
    $(".search").classList.toggle("miss", !!q && !notes.length);
    $("#search-clear").hidden = !q;
    if (!notes.length) {
      listEl.appendChild(el("div", { class: "list-empty" },
        q ? el("p", null, "No notes match “" + $("#search").value.trim() + "”.")
          : el("p", { text: S.notes.length ? "No notes in this view." : "No notes yet. Start one below." }),
        q ? el("button", { type: "button", class: "btn-quiet small", text: "Clear the search",
          onclick: function () { $("#search").value = ""; renderList(); $("#search").focus(); } }) : null));
      return;
    }
    if (S.ui.group) {
      S.categories.forEach(function (c) {
        var inCat = notes.filter(function (n) { return n.category === c.name; });
        if (!inCat.length) return;
        listEl.appendChild(el("div", { class: "list-group", text: c.name + " (" + inCat.length + ")" }));
        inCat.forEach(function (n) { listEl.appendChild(cardFor(n, q)); });
      });
    } else {
      notes.forEach(function (n) { listEl.appendChild(cardFor(n, q)); });
    }
    if (focusedId !== null) {
      var cur = listEl.querySelector(".note-card.current .nc-open");
      if (cur) cur.focus();
    }
  }

  function renderShowOptions() {
    var show = $("#show");
    var options = ["All", "\u{1F4CC} Pinned"].concat(S.categories.map(function (c) { return c.name; }));
    if (options.indexOf(S.ui.show) < 0) S.ui.show = "All";
    show.textContent = "";
    options.forEach(function (o) { show.appendChild(el("option", { value: o, text: o })); });
    show.value = S.ui.show;
  }

  function cardMenu(n, anchor, returnFocus) {
    var items = [
      menuItem(n.pinned ? "\u{1F4CC} Unpin" : "\u{1F4CC} Pin to the top", function () { togglePin(n); }),
      menuItem("\u{1F5C2} Move to category…", function () { categoryMenu(n, anchor); }),
      menuItem("⧉ Duplicate", function () { duplicate(n); }),
      menuItem("\u{1F517} Generate code", function () { showShareCode(n); }),
      el("div", { class: "menu-sep" }),
      menuItem("\u{1F5D1} Delete", function () { askDelete(n); }, "danger")
    ];
    popup(items, anchor, { returnFocus: returnFocus });
  }

  function categoryMenu(n, anchor) {
    var items = [el("div", { class: "menu-label", text: "Move “" + (n.title || "Untitled") + "” to" })];
    S.categories.forEach(function (c) {
      items.push(menuItem(el("span", null, el("span", { class: "dot", vars: { "--dot": c.color } }), " ",
        c.name + (c.name === n.category ? "  ✓" : "")), function () { moveTo(n, c.name); }));
    });
    popup(items, anchor);
  }

  // ------------------------------------------------------------------
  // Note actions
  // ------------------------------------------------------------------

  function openNote(id, fromCalendar) {
    if (id !== S.ui.openId) flush(false);
    S.ui.openId = id;
    persist();
    if (S.ui.tab !== "notes") showTab("notes");
    renderList();
    renderEditor();
    if (isNarrow()) enterEditing();
    var t = $("#ed-title");
    if (t && !t.value && !fromCalendar) t.focus();
  }

  function newNote(fields) {
    flush(false);
    var n = blankNote(fields || {});
    if (S.ui.show !== "All" && S.ui.show !== "\u{1F4CC} Pinned" && !(fields && fields.category)) n.category = S.ui.show;
    S.notes.push(n);
    S.ui.openId = n.id;
    persist();
    if (S.ui.tab !== "notes") showTab("notes");
    if ($("#search").value) $("#search").value = "";
    renderList();
    renderEditor();
    if (isNarrow()) enterEditing();
    var t = $("#ed-title");
    if (t) t.focus();
  }

  function togglePin(n) {
    flush(false);
    n.pinned = !n.pinned;
    n.updated = Date.now();
    persist();
    renderAll();
    toast(n.pinned ? "Pinned to the top." : "Unpinned.");
  }

  function moveTo(n, name) {
    flush(false);
    n.category = name;
    n.updated = Date.now();
    persist();
    renderAll();
    toast("Moved to " + name + ".");
  }

  function duplicate(n) {
    flush(false);
    var copy = JSON.parse(JSON.stringify(n));
    copy.id = S.nextId++;
    copy.uid = uuid();
    copy.title = (n.title || "Untitled") + " (copy)";
    copy.pinned = false;
    copy.created = copy.updated = Date.now();
    S.notes.push(copy);
    S.ui.openId = copy.id;
    persist();
    renderAll();
    if (isNarrow()) enterEditing();
    toast("Duplicated.");
  }

  function askDelete(n) {
    dialog({
      title: "Move to the Trash?",
      text: "“" + (n.title || "Untitled") + "” goes to Settings → Recently deleted, " +
        "where you can restore it for " + TRASH_DAYS + " days.",
      buttons: [{ label: "Cancel", value: false, cls: "btn-quiet" },
                { label: "Move to the Trash", value: true, cls: "btn-danger-text", isDefault: true }],
      cancel: false
    }).then(function (yes) {
      if (!yes) return;
      flush(false);
      S.notes = S.notes.filter(function (x) { return x.id !== n.id; });
      S.trash.unshift({ note: n, deletedAt: Date.now() });
      if (S.ui.openId === n.id) S.ui.openId = null;
      persist();
      renderAll();
      leaveEditing();
      toast("Moved to the Trash.");
    });
  }

  // ------------------------------------------------------------------
  // The editor
  // ------------------------------------------------------------------

  var savedRange = null, lastField = null;

  function rememberRange() {
    var sel = window.getSelection(), body = $("#ed-body");
    if (body && sel.rangeCount && body.contains(sel.anchorNode)) savedRange = sel.getRangeAt(0).cloneRange();
  }
  function restoreRange() {
    var body = $("#ed-body");
    if (!body) return;
    body.focus();
    if (savedRange && body.contains(savedRange.startContainer)) {
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(savedRange);
    }
  }

  function exec(cmd, value) {
    restoreRange();
    var css = cmd === "hiliteColor" || cmd === "foreColor" || cmd === "fontName";
    try { document.execCommand("styleWithCSS", false, css); } catch (e) { /* older engines */ }
    document.execCommand(cmd, false, value);
    rememberRange();
    updateToolbar();
    updateCount();
    touched();
  }

  // "Default colour" and "No highlight" take the colour off rather than
  // painting the theme's own over it, which would stay behind, wrong, the
  // moment the theme changes.
  function clearInline(prop) {
    restoreRange();
    var sel = window.getSelection(), body = $("#ed-body");
    if (!body || !sel.rangeCount) return;
    var range = sel.getRangeAt(0);
    // Any element wearing a style: a browser puts one on a <b> as readily
    // as on a span (see ALLOWED).
    var nodes = Array.prototype.slice.call(body.querySelectorAll("[style], font"));
    var start = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
    for (var up = start; up && up !== body; up = up.parentElement) {
      if (nodes.indexOf(up) < 0 && (up.tagName === "FONT" || up.hasAttribute("style"))) nodes.push(up);
    }
    nodes.forEach(function (node) {
      if (!range.intersectsNode(node)) return;
      if (prop === "color" && node.tagName === "FONT") node.removeAttribute("color");
      if (prop === "font-family" && node.tagName === "FONT") node.removeAttribute("face");
      if (prop === "font-size" && node.tagName === "FONT") node.removeAttribute("size");
      node.style.removeProperty(prop);
      if (!node.getAttribute("style")) node.removeAttribute("style");
      // Only a span or a font left with nothing to say is unwrapped: a <b>
      // or a line without a style is still bold, still a line.
      if (/^(SPAN|FONT)$/.test(node.tagName) && !node.attributes.length) {
        node.replaceWith.apply(node, Array.prototype.slice.call(node.childNodes));
      }
    });
    rememberRange();
    touched();
  }

  // The formatting bar's font and size: on the selection, or on whatever is
  // typed next at the caret. "Default" (null) takes them off, so the text
  // follows the editor's own font, as in the app.
  var pendingSize = 0;
  function applyFontFamily(name) {
    if (!name) { clearInline("font-family"); updateToolbar(); return; }
    exec("fontName", name);
  }
  // A browser sizes text in seven steps, not in points: the largest step is
  // asked for, and every run it made is then given the size in points.
  function applyFontSize(points) {
    if (!points) { clearInline("font-size"); updateToolbar(); return; }
    restoreRange();
    pendingSize = points;
    try { document.execCommand("styleWithCSS", false, true); } catch (e) { /* older engines */ }
    document.execCommand("fontSize", false, "7");
    fixSizeMarkers();
    rememberRange();
    updateToolbar();
    touched();
  }
  // Runs still wearing the browser's step: text typed at a caret the size
  // was chosen for arrives in it after the choice.
  function fixSizeMarkers() {
    var body = $("#ed-body");
    if (!body || !pendingSize) return;
    body.querySelectorAll("[style], font[size]").forEach(function (node) {
      if (node.tagName === "FONT" && node.getAttribute("size") === "7") {
        node.removeAttribute("size");
        node.style.fontSize = pendingSize + "pt";
      } else if (node.style && node.style.fontSize === "xxx-large") {
        node.style.fontSize = pendingSize + "pt";
      }
    });
  }

  // Text sitting straight in the note -- its first line, typed before any
  // Enter -- is put in a line of its own, as every other line is.
  function wrapLooseLines(body) {
    var loose = [];
    Array.prototype.slice.call(body.childNodes).forEach(function (node) {
      var inline = node.nodeType === 3 || (node.nodeType === 1 && !/^(DIV|P|UL|OL|TABLE)$/.test(node.tagName));
      if (inline) loose.push(node);
      else if (loose.length) { wrapLine(loose); loose = []; }
    });
    if (loose.length) wrapLine(loose);
  }

  // The lines the selection touches, each as the element that holds it: a
  // list's items, any other line of the note.
  function linesInRange(body, range) {
    var out = [];
    Array.prototype.forEach.call(body.children, function (child) {
      if (!range.intersectsNode(child)) return;
      if (child.tagName === "UL" || child.tagName === "OL") {
        child.querySelectorAll("li").forEach(function (li) { if (range.intersectsNode(li)) out.push(li); });
      } else if (child.tagName !== "TABLE") out.push(child);
    });
    return out;
  }
  function wrapLine(nodes) {
    var line = document.createElement("div");
    nodes[0].parentNode.insertBefore(line, nodes[0]);
    nodes.forEach(function (n) { line.appendChild(n); });
  }

  // Indent less (-1) or more (+1): every line the selection touches, by one
  // step, between none and the app's maximum.
  function changeIndent(delta) {
    restoreRange();
    var sel = window.getSelection(), body = $("#ed-body");
    if (!body || !sel.rangeCount) return;
    var was = sel.getRangeAt(0);
    if (!body.contains(was.startContainer)) return;
    // Moving a text node into a line of its own collapses a selection held
    // inside it, so its two ends are kept and set again: the same text
    // nodes, at the same offsets, now inside the new line.
    var ends = [was.startContainer, was.startOffset, was.endContainer, was.endOffset];
    wrapLooseLines(body);
    var range = document.createRange();
    try {
      range.setStart(ends[0], Math.min(ends[1], ends[0] === body ? body.childNodes.length : ends[1]));
      range.setEnd(ends[2], Math.min(ends[3], ends[2] === body ? body.childNodes.length : ends[3]));
    } catch (e) { range.selectNodeContents(body); }
    sel.removeAllRanges();
    sel.addRange(range);
    linesInRange(body, range).forEach(function (line) {
      var level = Math.max(0, Math.min(A.maxIndent, appIndent(line.getAttribute("data-indent")) + delta));
      if (level) line.setAttribute("data-indent", String(level));
      else line.removeAttribute("data-indent");
    });
    rememberRange();
    updateToolbar();
    touched();
  }

  // The font and size the text at the caret wears, or "" and 0 for the
  // editor's own.
  function fontAtCaret() {
    var sel = window.getSelection(), body = $("#ed-body"), out = { family: "", size: 0 };
    if (!body || !sel.rangeCount) return out;
    var node = sel.getRangeAt(0).startContainer;
    if (node.nodeType === 3) node = node.parentElement;
    for (; node && node !== body && body.contains(node); node = node.parentElement) {
      if (!out.family && node.style) out.family = appFamily(node.style.fontFamily);
      if (!out.size && node.style) out.size = appSize(node.style.fontSize);
    }
    return out;
  }

  function insertTable() {
    var rows = ["<tr><th>Column 1</th><th>Column 2</th><th>Column 3</th></tr>"];
    for (var i = 0; i < 2; i++) rows.push("<tr><td><br></td><td><br></td><td><br></td></tr>");
    exec("insertHTML", "<table><tbody>" + rows.join("") + "</tbody></table><div><br></div>");
  }

  var TOOLS = [
    ["bold", "B", "Bold (Ctrl+B)", "b"], ["italic", "I", "Italic (Ctrl+I)", "i"],
    ["underline", "U", "Underline (Ctrl+U)", "u"], ["strikeThrough", "S", "Strikethrough", "s"]
  ];

  function updateToolbar() {
    var bar = $("#toolbar");
    if (!bar) return;
    bar.querySelectorAll("[data-state]").forEach(function (b) {
      var on = false;
      try { on = document.queryCommandState(b.getAttribute("data-state")); } catch (e) { on = false; }
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    // The two lists show what the text at the caret wears, as the app's do.
    var font = fontAtCaret(), family = $("#tb-family .tb-label"), size = $("#tb-size .tb-label");
    if (family) family.textContent = font.family || "Default";
    if (size) size.textContent = font.size ? String(font.size) : "Default";
  }

  function updateCount() {
    var body = $("#ed-body"), out = $("#ed-count");
    if (!body || !out) return;
    // Counted from the markup, not from innerText: innerText depends on
    // the layout, and on a phone the editor is still hidden when the note
    // opens, so a table's cells ran together into a third of the words.
    var text = plainText(body.innerHTML);
    var words = (text.match(/\S+/g) || []).length;
    var chars = Array.from(text).length;
    var minutes = Math.round(words / 200);
    out.textContent = "";
    out.appendChild(document.createTextNode(plural(words, "word") + " · " + plural(chars, "character")));
    out.appendChild(el("br"));
    out.appendChild(document.createTextNode(minutes < 1 ? "under a minute to read" : "about " + plural(minutes, "minute") + " to read"));
  }

  function toolbar() {
    var bar = el("div", { class: "toolbar", id: "toolbar", role: "toolbar", "aria-label": "Formatting" });
    function tool(label, title, onPress, extra) {
      var b = el("button", Object.assign({ type: "button", class: "tb", title: title, "aria-label": title }, extra || {}), label);
      // Pressing a tool must not take the selection out of the note.
      b.addEventListener("mousedown", function (e) { e.preventDefault(); });
      b.addEventListener("click", onPress);
      bar.appendChild(b);
      return b;
    }
    TOOLS.forEach(function (t) {
      tool(t[1], t[2], function () { exec(t[0]); }, { class: "tb " + t[3], "data-state": t[0], "aria-pressed": "false" });
    });
    bar.appendChild(el("span", { class: "sep" }));
    // Font and size, as the app's two lists: "Default" first, which is the
    // editor's own and stores nothing.
    function chooser(id, title, choices, show, pick) {
      var btn = tool(el("span", null, el("span", { class: "tb-label", text: "Default" }), el("span", { class: "tb-caret", text: "▾" })),
        title, function () {
          rememberRange();
          popup([menuItem("Default", function () { pick(null); })].concat(choices.map(function (c) {
            var item = menuItem(String(c), function () { pick(c); });
            show(item, c);
            return item;
          })), btn, { role: "menu" });
        }, { id: id, class: "tb tb-select", "aria-haspopup": "menu" });
      return btn;
    }
    chooser("tb-family", "Font", A.fontFamilies,
      function (item, f) { item.style.fontFamily = '"' + f + '"'; }, applyFontFamily);
    chooser("tb-size", "Font size", A.fontSizes, function () {}, applyFontSize);
    bar.appendChild(el("span", { class: "sep" }));
    var colourBtn = tool(el("span", null, "A", el("span", { class: "bar", vars: { "--bar": "#e63946" } })), "Text colour", function () {
      rememberRange();
      popup(swatchGrid(A.noteColors, null, function (c) { exec("foreColor", c); },
        el("button", { type: "button", class: "menu-item", onclick: function () { closePopup(); clearInline("color"); } }, "Default colour")),
        colourBtn, { role: "dialog" });
    });
    var markBtn = tool(el("span", null, "H", el("span", { class: "bar", vars: { "--bar": "#fff3b0" } })), "Highlight", function () {
      rememberRange();
      popup(swatchGrid(A.highlightColors, null, function (c) { exec("hiliteColor", c); },
        el("button", { type: "button", class: "menu-item", onclick: function () { closePopup(); clearInline("background-color"); } }, "No highlight")),
        markBtn, { role: "dialog" });
    });
    bar.appendChild(el("span", { class: "sep" }));
    tool("•", "Bulleted list", function () { exec("insertUnorderedList"); }, { "data-state": "insertUnorderedList", "aria-pressed": "false" });
    tool("1.", "Numbered list", function () { exec("insertOrderedList"); }, { "data-state": "insertOrderedList", "aria-pressed": "false" });
    bar.appendChild(el("span", { class: "sep" }));
    tool(icon("left"), "Align left", function () { exec("justifyLeft"); }, { "data-state": "justifyLeft", "aria-pressed": "false" });
    tool(icon("center"), "Centre", function () { exec("justifyCenter"); }, { "data-state": "justifyCenter", "aria-pressed": "false" });
    tool(icon("right"), "Align right", function () { exec("justifyRight"); }, { "data-state": "justifyRight", "aria-pressed": "false" });
    bar.appendChild(el("span", { class: "sep" }));
    tool(icon("outdent"), "Indent less", function () { changeIndent(-1); });
    tool(icon("indent"), "Indent more", function () { changeIndent(1); });
    bar.appendChild(el("span", { class: "sep" }));
    tool(icon("table"), "Insert a table", insertTable);
    var emojiBtn = tool("\u{1F642}", "Insert emoji", function () { rememberRange(); emojiPicker(emojiBtn, "body"); });
    tool(icon(isDark() ? "sun" : "moon"), isDark() ? "Switch to the light theme" : "Switch to the dark theme",
      function () { flush(false); setTheme(partnerTheme(S.theme)); });
    return bar;
  }

  function emojiPicker(anchor, target) {
    var wrap = el("div", { class: "emoji-pop" },
      el("div", { class: "emoji-head" }, el("span", { text: "Insert emoji" }),
        el("button", { type: "button", "aria-label": "Close", onclick: closePopup }, "✕")));
    A.emojiGroups.forEach(function (g) {
      wrap.appendChild(el("div", { class: "emoji-group", text: g[0] }));
      var grid = el("div", { class: "emoji-grid" });
      g[1].forEach(function (ch) {
        grid.appendChild(el("button", { type: "button", "aria-label": "Insert " + ch, text: ch,
          onclick: function () { insertEmoji(ch, target); } }));
      });
      wrap.appendChild(grid);
    });
    popup(wrap, anchor, { role: "dialog", cls: "", returnFocus: null });
  }

  function insertEmoji(ch, target) {
    if (target === "body") {
      restoreRange();
      document.execCommand("insertText", false, ch);
      rememberRange();
      updateCount();
      touched();
      return;
    }
    var field = target && target.tagName ? target : lastField;
    if (!field) return;
    var start = field.selectionStart || field.value.length, end = field.selectionEnd || start;
    field.setRangeText(ch, start, end, "end");
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.focus();
  }

  function renderEditor() {
    var ed = $("#editor");
    ed.textContent = "";
    savedRange = null;
    var n = current();
    if (!n) {
      ed.appendChild(el("div", { class: "ed-empty" }, el("div", null,
        el("h2", { text: "No note open" }),
        el("p", { text: "Pick a note from the list, or start a new one." }),
        el("button", { type: "button", class: "btn-accent", text: "+ New Note", onclick: function () { newNote(); } }))));
      return;
    }
    var rec = normRec(n.recurrence);
    var cat = category(n.category);
    var inner = el("div", { class: "ed-inner" });

    if (rec.freq) {
      inner.appendChild(el("div", { class: "ed-banner",
        text: "\u{1F501} This note repeats (" + describeRec(rec) + ") — edits here apply to every day" }));
    }

    var title = el("input", { id: "ed-title", class: "ed-title", type: "text", placeholder: "Title",
      "aria-label": "Title", maxlength: "300" });
    title.value = n.title;
    title.addEventListener("input", function () { n.title = title.value; touched(); });
    title.addEventListener("focus", function () { lastField = title; });
    title.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); $("#ed-body").focus(); }
    });
    var catBtn = el("button", { type: "button", class: "ed-cat", "aria-haspopup": "menu", "aria-label": "Category: " + cat.name,
      onclick: function () {
        var items = S.categories.map(function (c) {
          return menuItem(el("span", null, el("span", { class: "dot", vars: { "--dot": c.color } }), "  " + c.name),
            function () { n.category = c.name; dirty = true; flush(true); renderEditor(); });
        });
        items.push(el("div", { class: "menu-sep" }));
        items.push(menuItem("+ New category…", function () { addCategoryDialog(function (name) {
          n.category = name; dirty = true; flush(true); renderEditor(); }); }));
        popup(items, catBtn, { alignRight: true });
      } }, el("span", { class: "dot", vars: { "--dot": cat.color } }), cat.name, " ▾");
    inner.appendChild(el("div", { class: "ed-head" },
      el("button", { type: "button", class: "btn-quiet ed-back", onclick: leaveEditing, text: "◀ Notes" }),
      title, catBtn));

    // Date, colour, repeat.
    var date = el("input", { id: "ed-date", type: "text", placeholder: "DD.MM.YYYY", "aria-label": "Date",
      inputmode: "numeric", autocomplete: "off" });
    date.value = showDate(n.date);
    // Read when the field is left or Enter is pressed -- never mid-typing,
    // where "14.0" is not yet a day and must not become one.
    date.addEventListener("change", function () {
      var read = readDate(date.value);
      if (read === null) {
        date.classList.add("bad");
        setStatus("");
        toast("That is not a date the app can read, so it was left out. Try 14.09.2026.");
        return;
      }
      date.classList.remove("bad");
      n.date = read;
      if (!read && normRec(n.recurrence).freq) n.recurrence = normRec({});
      dirty = true; flush(true); renderEditor();
    });
    date.addEventListener("keydown", function (e) { if (e.key === "Enter") date.blur(); });
    var clear = el("button", { type: "button", class: "icon-btn", "aria-label": "Clear the date", title: "Clear the date",
      onclick: function () { n.date = ""; n.recurrence = normRec({}); dirty = true; flush(true); renderEditor(); } }, "✕");
    var swatch = el("button", { type: "button", class: "swatch" + (n.color ? "" : " none"), "aria-label": "Note colour",
      title: n.color ? "Colour " + n.color : "No colour of its own", vars: { "--swatch": n.color || "transparent" },
      onclick: function () {
        popup(swatchGrid(A.noteColors, n.color, function (c) { n.color = c; dirty = true; flush(true); renderEditor(); },
          el("button", { type: "button", class: "menu-item", onclick: function () {
            closePopup(); n.color = ""; dirty = true; flush(true); renderEditor(); } }, "Use the category's colour")),
          swatch, { role: "dialog" });
      } });
    var repeat = el("select", { id: "ed-repeat", "aria-label": "Repeat" });
    [["", "Does not repeat"], ["daily", "Daily"], ["weekly", "Weekly"], ["monthly", "Monthly"], ["yearly", "Yearly"]]
      .forEach(function (o) { repeat.appendChild(el("option", { value: o[0], text: o[1] })); });
    repeat.value = rec.freq;
    repeat.addEventListener("change", function () {
      var r = normRec(n.recurrence);
      r.freq = repeat.value;
      if (r.freq && !parseIso(n.date)) {
        n.date = iso(today());
        toast("A repeat starts on the note's date, so it starts today. Change the date to move it.");
      }
      if (r.freq === "weekly" && !r.weekdays.length) r.weekdays = [weekday(parseIso(n.date))];
      n.recurrence = normRec(r);
      dirty = true; flush(true); renderEditor();
    });
    inner.appendChild(el("div", { class: "ed-meta" },
      el("label", { class: "ed-field" }, "\u{1F4C5} Date:", date, clear),
      el("span", { class: "ed-field" }, "\u{1F3A8} Color:", swatch),
      el("label", { class: "ed-field" }, "\u{1F501} Repeat:", repeat,
        rec.freq ? el("span", { class: "repeat-summary", text: describeRec(rec) }) : null)));
    if (rec.freq) inner.appendChild(repeatBox(n, rec));

    inner.appendChild(el("div", { class: "ed-note-head" }, el("b", { text: "Note" }),
      el("span", { class: "ed-count", id: "ed-count", "aria-live": "off" })));
    inner.appendChild(toolbar());

    var body = el("div", { id: "ed-body", class: "ed-body", contenteditable: "true", role: "textbox",
      "aria-multiline": "true", "aria-label": "Note text", "data-placeholder": "Write your note here…", spellcheck: "true" });
    body.innerHTML = sanitizeHtml(n.html);
    body.addEventListener("input", function () { fixSizeMarkers(); updateCount(); touched(); });
    body.addEventListener("keyup", function () { rememberRange(); updateToolbar(); });
    body.addEventListener("mouseup", function () { rememberRange(); updateToolbar(); });
    body.addEventListener("focus", function () { lastField = null; });
    // Pasted or dropped text arrives as text: another page's markup is not
    // the note's to keep, and the app's own paste does the same with styles
    // it does not know.
    body.addEventListener("paste", function (e) {
      e.preventDefault();
      var text = (e.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, text);
    });
    body.addEventListener("drop", function (e) {
      e.preventDefault();
      var text = e.dataTransfer && e.dataTransfer.getData("text/plain");
      if (text) document.execCommand("insertText", false, text);
    });
    inner.appendChild(body);

    var sections = el("div", { class: "ed-sections" });
    sections.appendChild(checklistSection(n));
    var comments = el("textarea", { class: "ed-comments", id: "ed-comments", "aria-label": "Comments",
      placeholder: "Anything that belongs beside the note rather than in it." });
    comments.value = n.comments;
    comments.addEventListener("input", function () { n.comments = comments.value; touched(); });
    comments.addEventListener("focus", function () { lastField = comments; });
    var com = el("details", { class: "ed-section wide" }, el("summary", { text: "\u{1F4AC} Comments / additional notes" }),
      el("div", { class: "sec-body" }, comments));
    if (n.comments) com.open = true;
    sections.appendChild(com);
    inner.appendChild(sections);

    inner.appendChild(el("div", { class: "ed-status", id: "ed-status", role: "status" }));
    inner.appendChild(el("div", { class: "ed-actions" },
      el("button", { type: "button", class: "btn-success", onclick: function () {
        dirty = true; flush(false); setStatus("Saved"); toast("Saved."); } }, "\u{1F4BE} Save"),
      el("button", { type: "button", class: "btn-quiet", onclick: function () { showShareCode(n); } }, "\u{1F517} Generate code"),
      el("button", { type: "button", class: "btn-danger-text", onclick: function () { askDelete(n); } }, "\u{1F5D1} Delete"),
      el("button", { type: "button", class: "btn-quiet", onclick: function () { duplicate(n); } }, "⧉ Duplicate"),
      el("button", { type: "button", class: "btn-quiet", onclick: function () { togglePin(n); } },
        n.pinned ? "\u{1F4CC} Unpin" : "\u{1F4CC} Pin"),
      el("button", { type: "button", class: "btn-quiet", onclick: function (e) { categoryMenu(n, e.currentTarget); } },
        "\u{1F5C2} Move to…")));
    ed.appendChild(inner);
    updateCount();
    ed.scrollTop = 0;
  }

  function repeatBox(n, rec) {
    var unit = { daily: "day(s)", weekly: "week(s)", monthly: "month(s)", yearly: "year(s)" }[rec.freq];
    function change(mutate) {
      var r = normRec(n.recurrence);
      mutate(r);
      n.recurrence = normRec(r);
      dirty = true; flush(true); renderEditor();
    }
    var every = el("input", { type: "number", min: "1", max: "1000", value: String(rec.interval), "aria-label": "Every how many" });
    every.addEventListener("change", function () { change(function (r) { r.interval = clampInt(every.value, 1, 1, 1000); }); });
    var box = el("div", { class: "repeat-box" }, el("div", { class: "rb-row" }, "Every", every, unit));
    if (rec.freq === "weekly") {
      var row = el("div", { class: "rb-row", role: "group", "aria-label": "On these days" }, "On:");
      var anchorDay = weekday(parseIso(n.date) || today());
      WEEKDAYS.forEach(function (name, d) {
        var on = (rec.weekdays.length ? rec.weekdays : [anchorDay]).indexOf(d) >= 0;
        row.appendChild(el("button", { type: "button", class: "wd", "aria-pressed": on ? "true" : "false", text: name,
          onclick: function () {
            change(function (r) {
              var days = r.weekdays.length ? r.weekdays.slice() : [anchorDay];
              var i = days.indexOf(d);
              if (i >= 0) { if (days.length > 1) days.splice(i, 1); } else days.push(d);
              r.weekdays = days;
            });
          } }));
      });
      box.appendChild(row);
    }
    var mode = rec.count ? "after" : rec.end ? "on" : "never";
    var group = "ends-" + n.id;
    function radio(value, label) {
      var r = el("input", { type: "radio", name: group, value: value });
      r.checked = mode === value;
      r.addEventListener("change", function () {
        change(function (x) {
          if (value === "never") { x.end = ""; x.count = 0; }
          if (value === "on") { x.count = 0; x.end = x.end || iso(addDays(parseIso(n.date) || today(), 90)); }
          if (value === "after") { x.end = ""; x.count = x.count || 10; }
        });
      });
      return el("label", null, r, label);
    }
    var endDate = el("input", { type: "text", placeholder: "DD.MM.YYYY", "aria-label": "End date", value: showDate(rec.end) });
    endDate.disabled = mode !== "on";
    endDate.addEventListener("change", function () {
      var read = readDate(endDate.value);
      if (read === null) { endDate.classList.add("bad"); toast("That end date cannot be read, so it was left out."); return; }
      change(function (x) { x.end = read || ""; if (!read) x.count = 0; });
    });
    var times = el("input", { type: "number", min: "1", max: "5000", "aria-label": "How many times", value: String(rec.count || 10) });
    times.disabled = mode !== "after";
    times.addEventListener("change", function () { change(function (x) { x.count = clampInt(times.value, 10, 1, 5000); }); });
    box.appendChild(el("div", { class: "rb-row" }, "Ends:", radio("never", "Never"), radio("on", "On date"), endDate,
      radio("after", "After"), times, "times"));
    return box;
  }

  function checklistSection(n) {
    var done = n.checklist.filter(function (c) { return c.done; }).length;
    var details = el("details", { class: "ed-section wide" },
      el("summary", { text: "☑ Checklist" + (n.checklist.length ? " (" + done + "/" + n.checklist.length + ")" : "") }));
    if (n.checklist.length) details.open = true;
    var body = el("div", { class: "sec-body" });
    function redraw(focusIndex) {
      var fresh = checklistSection(n);
      fresh.open = true;
      details.replaceWith(fresh);
      if (focusIndex !== undefined) {
        var target = fresh.querySelectorAll(".cl-text")[focusIndex];
        if (target) target.focus();
        else { var add = fresh.querySelector(".cl-add input"); if (add) add.focus(); }
      }
    }
    if (n.checklist.length) {
      body.appendChild(el("div", { class: "cl-head", text: "Checklist — " + done + "/" + n.checklist.length + " done" }));
    }
    var list = el("ul", { class: "cl-list" });
    n.checklist.forEach(function (item, i) {
      var box = el("input", { type: "checkbox", "aria-label": "Done: " + item.text });
      box.checked = !!item.done;
      box.addEventListener("change", function () { item.done = box.checked; dirty = true; flush(true); redraw(); });
      var text = el("input", { type: "text", class: "cl-text", "aria-label": "Item " + (i + 1) });
      text.value = item.text;
      text.addEventListener("input", function () { item.text = text.value; touched(); });
      text.addEventListener("focus", function () { lastField = text; });
      function move(by) {
        var j = i + by;
        if (j < 0 || j >= n.checklist.length) return;
        var tmp = n.checklist[i]; n.checklist[i] = n.checklist[j]; n.checklist[j] = tmp;
        dirty = true; flush(true); redraw(j);
      }
      // The arrows sit beside the box, away from the bin: a slip of the
      // mouse moves an item instead of deleting it (the owner's call).
      list.appendChild(el("li", { class: "cl-item" + (item.done ? " done" : "") },
        el("span", { class: "cl-arrows" },
          el("button", { type: "button", "aria-label": "Move up", disabled: i === 0, onclick: function () { move(-1); } }, "▲"),
          el("button", { type: "button", "aria-label": "Move down", disabled: i === n.checklist.length - 1,
            onclick: function () { move(1); } }, "▼")),
        box, text,
        el("button", { type: "button", class: "cl-del", "aria-label": "Delete item: " + item.text, title: "Delete item",
          onclick: function () { n.checklist.splice(i, 1); dirty = true; flush(true); redraw(Math.min(i, n.checklist.length - 1)); } },
          "\u{1F5D1}")));
    });
    body.appendChild(list);
    var add = el("input", { type: "text", placeholder: "Add an item", "aria-label": "New checklist item", maxlength: "500" });
    function addItem() {
      var v = add.value.trim();
      if (!v) { add.focus(); return; }
      n.checklist.push({ text: v, done: false });
      dirty = true; flush(true);
      var fresh = checklistSection(n);
      fresh.open = true;
      details.replaceWith(fresh);
      var input = fresh.querySelector(".cl-add input");
      if (input) input.focus();
    }
    add.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); addItem(); } });
    body.appendChild(el("div", { class: "cl-add" }, add,
      el("button", { type: "button", class: "btn-accent", onclick: addItem }, "+ Add")));
    details.appendChild(body);
    return details;
  }

  // ------------------------------------------------------------------
  // Phones: the list and the editor take turns on one screen
  // ------------------------------------------------------------------

  function enterEditing() {
    var view = $("#view-notes");
    if (view.classList.contains("editing")) return;
    view.classList.add("editing");
    try { history.pushState({ editing: true }, ""); } catch (e) { /* not in this frame */ }
  }
  function leaveEditing() {
    var view = $("#view-notes");
    if (!view.classList.contains("editing")) return;
    flush(false);
    if (history.state && history.state.editing) history.back();
    else view.classList.remove("editing");
  }
  window.addEventListener("popstate", function () {
    flush(false);
    $("#view-notes").classList.remove("editing");
    renderList();
  });

  // ------------------------------------------------------------------
  // Calendar
  // ------------------------------------------------------------------

  function monthStart() {
    var m = /^(\d{4})-(\d{2})$/.exec(S.ui.calMonth || "");
    if (!m) { var t = today(); return new Date(t.getFullYear(), t.getMonth(), 1); }
    return new Date(+m[1], +m[2] - 1, 1);
  }
  function setMonth(d) { S.ui.calMonth = iso(d).slice(0, 7); persist(); renderCalendar(); }

  function renderCalendar() {
    var first = monthStart();
    var last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
    $("#cal-title").textContent = MONTHS[first.getMonth()] + " " + first.getFullYear();
    var hits = {};
    S.notes.forEach(function (n) {
      occurrences(n, first, last).forEach(function (d) { (hits[d] = hits[d] || []).push(n); });
    });
    var grid = $("#cal-grid");
    grid.textContent = "";
    WEEKDAYS.forEach(function (w) { grid.appendChild(el("div", { class: "cal-dow", role: "columnheader", text: w })); });
    for (var b = 0; b < weekday(first); b++) grid.appendChild(el("div", { class: "cal-day blank", "aria-hidden": "true" }));
    var t = iso(today());
    for (var day = 1; day <= last.getDate(); day++) {
      var d = new Date(first.getFullYear(), first.getMonth(), day);
      var key = iso(d);
      var notes = hits[key] || [];
      var marks = S.dayMarks[key] || [];
      var paint = S.dayColors[key];
      var cell = el("button", { type: "button", role: "gridcell",
        class: "cal-day" + (key === t ? " today" : "") + (paint ? " painted" : ""),
        "aria-selected": key === S.ui.selDay ? "true" : "false",
        "aria-label": longDate(d) + (notes.length ? ": " + notes.map(function (n) { return n.title || "Untitled"; }).join(", ") : ", nothing on this day")
          + (marks.length ? ", marked " + marks.join(" ") : ""),
        vars: paint ? { "--paint": paint, "--paint-ink": lettersOn(paint) } : null },
        el("span", { class: "cal-num", text: String(day) }),
        el("span", { class: "cal-marks", text: marks.join("") }),
        el("span", { class: "cal-dots" }, notes.slice(0, 4).map(function (n) {
          return el("span", { class: "dot", vars: { "--dot": n.color || category(n.category).color } });
        })),
        el("span", { class: "cal-titles" }, notes.slice(0, 3).map(function (n) {
          return el("span", { text: (normRec(n.recurrence).freq ? "\u{1F501} " : "") + (n.title || "Untitled") });
        }), notes.length > 3 ? el("span", { text: "+" + (notes.length - 3) + " more" }) : null));
      (function (k, c) {
        c.addEventListener("click", function () { selectDay(k); });
        c.addEventListener("contextmenu", function (e) { e.preventDefault(); dayMenu(k, { x: e.clientX, y: e.clientY }, c); });
      })(key, cell);
      grid.appendChild(cell);
    }
    renderDayPanel(hits);
  }

  function selectDay(key) {
    S.ui.selDay = key;
    persist();
    renderCalendar();
    // The month is drawn again; the day just pressed keeps the focus.
    var cell = $(".cal-day[aria-selected='true']");
    if (cell) cell.focus({ preventScroll: true });
    var panel = $("#day-panel");
    if (isNarrow() && !panel.hidden) panel.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function renderDayPanel(hits) {
    var panel = $("#day-panel");
    var key = S.ui.selDay, d = parseIso(key);
    var first = monthStart();
    if (!d || d.getMonth() !== first.getMonth() || d.getFullYear() !== first.getFullYear()) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    panel.textContent = "";
    var notes = hits[key] || [];
    panel.appendChild(el("div", { class: "dp-head" },
      el("h3", { text: longDate(d) }),
      el("button", { type: "button", class: "btn-accent small", onclick: function () { newNote({ date: key }); } }, "+ Add note"),
      el("button", { type: "button", class: "dp-close", "aria-label": "Close the day", onclick: function () {
        S.ui.selDay = null; persist(); renderCalendar(); } }, "✕")));
    var list = el("div", { class: "dp-list" });
    if (!notes.length) list.appendChild(el("p", { class: "dp-empty", text: "Nothing on this day yet." }));
    notes.forEach(function (n) {
      list.appendChild(el("button", { type: "button", class: "dp-item",
        vars: { "--stripe": n.color || category(n.category).color },
        onclick: function () { openNote(n.id, true); } },
        (normRec(n.recurrence).freq ? "\u{1F501} " : "") + (n.title || "Untitled")));
    });
    panel.appendChild(list);
    var marks = S.dayMarks[key] || [];
    var markBtn = el("button", { type: "button", class: "btn-quiet small", onclick: function () { dayMenu(key, markBtn); } },
      "⭐ Mark this day" + (marks.length ? " (" + marks.join(" ") + ")" : ""));
    panel.appendChild(el("div", { class: "dp-head", style: null }, markBtn));
  }

  function dayMenu(key, anchor, returnFocus) {
    var marks = (S.dayMarks[key] || []).slice();
    var grid = el("div", { class: "emoji-grid" });
    A.dayMarkers.forEach(function (m) {
      var on = marks.indexOf(m) >= 0;
      grid.appendChild(el("button", { type: "button", text: m, "aria-pressed": on ? "true" : "false",
        "aria-label": (on ? "Remove " : "Add ") + m,
        onclick: function () {
          var i = marks.indexOf(m);
          if (i >= 0) marks.splice(i, 1);
          else if (marks.length < 3) marks.push(m);
          else { toast("A day holds up to three marks."); return; }
          if (marks.length) S.dayMarks[key] = marks; else delete S.dayMarks[key];
          persist(); closePopup(); renderCalendar();
        } }));
    });
    var colours = swatchGrid(A.paletteColors, S.dayColors[key], function (c) {
      S.dayColors[key] = c; persist(); renderCalendar();
    });
    popup(el("div", { class: "emoji-pop" },
      el("div", { class: "emoji-head" }, el("span", { text: "Mark " + longDate(parseIso(key)) }),
        el("button", { type: "button", "aria-label": "Close", onclick: closePopup }, "✕")),
      el("div", { class: "emoji-group", text: "Up to three marks" }), grid,
      el("div", { class: "emoji-group", text: "Colour the day" }), colours,
      el("button", { type: "button", class: "menu-item", onclick: function () {
        delete S.dayMarks[key]; delete S.dayColors[key]; persist(); closePopup(); renderCalendar(); } }, "Clear marks and colour")),
      anchor, { role: "dialog", returnFocus: returnFocus });
  }

  // ------------------------------------------------------------------
  // Settings
  // ------------------------------------------------------------------

  function showSettings(section) {
    flush(false);
    S.ui.section = section || S.ui.section || "appearance";
    $("#app").classList.add("in-settings");
    ["view-notes", "view-cal"].forEach(function (id) { $("#" + id).hidden = true; });
    $("#view-settings").hidden = false;
    renderSettings();
  }
  function closeSettings() {
    $("#app").classList.remove("in-settings");
    $("#view-settings").hidden = true;
    showTab(S.ui.tab === "cal" ? "cal" : "notes");
  }

  function renderSettings() {
    document.querySelectorAll(".set-nav [data-section]").forEach(function (b) {
      b.setAttribute("aria-current", b.getAttribute("data-section") === S.ui.section ? "true" : "false");
    });
    var body = $("#set-body");
    body.textContent = "";
    var s = S.ui.section;
    if (s === "appearance") {
      body.appendChild(el("h2", { text: "Appearance" }));
      body.appendChild(el("p", { class: "lead", text: "Eight themes, light and dark. Every colour here is the app's own." }));
      [["Dark", A.darkThemes], ["Light", A.lightThemes]].forEach(function (group) {
        var grid = el("div", { class: "theme-grid" });
        group[1].forEach(function (key) {
          var p = A.themes[key];
          grid.appendChild(el("button", { type: "button", class: "theme-chip", "aria-pressed": key === S.theme ? "true" : "false",
            onclick: function () { setTheme(key); } },
            el("span", { class: "tc-preview", "aria-hidden": "true" },
              el("i", { vars: { background: p.sidebar } }),
              el("span", { class: "tc-main", vars: { background: p.bg } },
                el("span", { vars: { background: p.accent, width: "60%" } }),
                el("span", { vars: { background: p.card, width: "85%" } }),
                el("span", { vars: { background: p.subtext, width: "40%" } }))),
            el("span", { class: "tc-name", text: A.themeLabels[key] })));
        });
        body.appendChild(el("div", { class: "set-panel" }, el("h3", { text: group[0] }), grid));
      });
    } else if (s === "categories") {
      body.appendChild(el("h2", { text: "Categories" }));
      body.appendChild(el("p", { class: "lead", text: "A category gives its notes a colour. “General” is the safety net: it cannot be renamed or deleted." }));
      var rows = el("div", { class: "cat-rows" });
      S.categories.forEach(function (c) {
        var count = S.notes.filter(function (n) { return n.category === c.name; }).length;
        var dotBtn = el("button", { type: "button", class: "swatch", "aria-label": "Colour of " + c.name, vars: { "--swatch": c.color },
          onclick: function () {
            popup(swatchGrid(A.paletteColors, c.color, function (col) { c.color = col; persist(); renderAll(); }), dotBtn, { role: "dialog" });
          } });
        rows.appendChild(el("div", { class: "cat-row" }, dotBtn,
          el("span", { class: "cat-name", text: c.name }),
          el("span", { class: "cat-count", text: plural(count, "note") }),
          c.name === PROTECTED ? null : el("button", { type: "button", class: "btn-quiet small", onclick: function () { renameCategory(c); } }, "Rename"),
          c.name === PROTECTED ? null : el("button", { type: "button", class: "btn-danger-text small", onclick: function () { deleteCategory(c); } }, "Delete")));
      });
      body.appendChild(el("div", { class: "set-panel" }, rows,
        el("div", { class: "cat-add" }, el("button", { type: "button", class: "btn-accent", onclick: function () {
          addCategoryDialog(function () { renderSettings(); }); } }, "+ New category"))));
    } else if (s === "trash") {
      purgeTrash();
      body.appendChild(el("h2", { text: "Recently deleted" }));
      body.appendChild(el("p", { class: "lead", text: "Kept for " + TRASH_DAYS + " days, then removed automatically." }));
      var panel = el("div", { class: "set-panel" });
      if (!S.trash.length) panel.appendChild(el("p", { class: "dp-empty", text: "The Trash is empty." }));
      var list = el("div", { class: "trash-rows" });
      S.trash.forEach(function (t, i) {
        var left = Math.max(0, TRASH_DAYS - Math.floor((Date.now() - t.deletedAt) / 86400000));
        list.appendChild(el("div", { class: "trash-row" },
          el("div", { class: "tr-text" }, el("b", { text: t.note.title || "Untitled" }),
            el("small", { text: "deleted " + showDate(iso(new Date(t.deletedAt))) + " · " + left + " day(s) left" })),
          el("button", { type: "button", class: "btn-accent small", onclick: function () { restore(i); } }, "Restore"),
          el("button", { type: "button", class: "btn-danger small", onclick: function () { deleteForever(i); } }, "Delete")));
      });
      panel.appendChild(list);
      if (S.trash.length) {
        panel.appendChild(el("button", { type: "button", class: "btn-danger-text empty-trash", onclick: emptyTrash }, "Empty trash"));
      }
      body.appendChild(panel);
    } else if (s === "shortcuts") {
      body.appendChild(el("h2", { text: "Keyboard shortcuts" }));
      body.appendChild(el("p", { class: "lead", text: "The ones this demo knows. The desktop app has more, listed on this same page." }));
      var rowsK = [["Ctrl+S", "Save now"], ["Ctrl+B / Ctrl+I / Ctrl+U", "Bold / italic / underline"],
                   ["Ctrl+Z", "Undo, in the note"], ["↑ ↓", "Walk the note list, and the items of a menu"],
                   ["Enter", "From the title, go to the note's text"], ["Esc", "Close a menu or a question"]];
      var table = el("table", { class: "kbd-table" });
      rowsK.forEach(function (r) { table.appendChild(el("tr", null, el("td", null, el("kbd", { text: r[0] })), el("td", { text: r[1] }))); });
      body.appendChild(el("div", { class: "set-panel" }, table));
    } else {
      body.appendChild(el("h2", { text: "About this demo" }));
      body.appendChild(el("div", { class: "set-panel about" },
        el("p", { text: "Note Organizer is a desktop app for Windows, written in Python with Tkinter. A browser cannot run it, so this page is a re-creation of its interface in HTML and JavaScript, written to let you try the everyday parts without installing anything." }),
        el("p", { text: "Where the app has an exact rule, the demo follows it, taken from the app's own code: the eight themes and the arithmetic that picks readable letters on every colour, how a repeating note lands on the calendar, the order of each sort, the share-code format, and the fonts, sizes and indent the formatting bar offers." }),
        el("p", { text: "Only in the desktop app: attachments, templates, backups to another computer, statistics, finding duplicates, editing a single day of a repeating note, a list you arrange by hand, find-in-note, and a calculator." }),
        el("p", null, "It mirrors version " + A.version + ". Everything you type is kept in this browser's storage, on this device, and nowhere else. ",
          el("a", { href: "../index.html", text: "Back to the site" }), " · ",
          el("a", { href: "../how-its-built.html", text: "How the app is built" })),
        el("button", { type: "button", class: "btn-danger-text", onclick: resetDemo }, "Reset the demo")));
    }
    body.scrollTop = 0;
  }

  function addCategoryDialog(after) {
    var name = el("input", { type: "text", maxlength: "40", "aria-label": "Category name", placeholder: "Name" });
    var used = S.categories.map(function (c) { return c.color; });
    var colour = A.paletteColors.filter(function (c) { return used.indexOf(c) < 0; })[0] || A.paletteColors[0];
    var msg = el("div", { class: "msg bad" });
    var grid = el("div", { class: "swatches" });
    A.paletteColors.forEach(function (c) {
      grid.appendChild(el("button", { type: "button", "aria-label": c, vars: { "--c": c }, "aria-pressed": c === colour ? "true" : "false",
        onclick: function (e) {
          colour = c;
          grid.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
          e.currentTarget.setAttribute("aria-pressed", "true");
        } }));
    });
    dialog({
      title: "New category",
      body: el("div", null, name, el("p", { text: "Its colour:" }), grid, msg),
      focus: "input",
      buttons: [{ label: "Cancel", value: null, cls: "btn-quiet" },
                { label: "Add", value: true, cls: "btn-accent", isDefault: true, handler: function () {
                  var v = name.value.trim();
                  if (!v) { msg.textContent = "Give it a name."; return false; }
                  if (S.categories.some(function (c) { return c.name.toLowerCase() === v.toLowerCase(); })) {
                    msg.textContent = "There is already a category called that."; return false;
                  }
                  S.categories.push({ name: v, color: colour });
                  persist();
                  renderShowOptions();
                  after(v);
                  return true;
                } }],
      cancel: null
    });
  }

  function renameCategory(c) {
    var input = el("input", { type: "text", maxlength: "40", "aria-label": "New name" });
    input.value = c.name;
    var msg = el("div", { class: "msg bad" });
    dialog({
      title: "Rename “" + c.name + "”", body: el("div", null, input, msg), focus: "input",
      buttons: [{ label: "Cancel", value: null, cls: "btn-quiet" },
                { label: "Rename", value: true, cls: "btn-accent", isDefault: true, handler: function () {
                  var v = input.value.trim();
                  if (!v) { msg.textContent = "Give it a name."; return false; }
                  if (v !== c.name && S.categories.some(function (x) { return x.name.toLowerCase() === v.toLowerCase(); })) {
                    msg.textContent = "There is already a category called that."; return false;
                  }
                  S.notes.forEach(function (n) { if (n.category === c.name) n.category = v; });
                  if (S.ui.show === c.name) S.ui.show = v;
                  c.name = v;
                  persist(); renderAll();
                  return true;
                } }],
      cancel: null
    });
  }

  function deleteCategory(c) {
    var count = S.notes.filter(function (n) { return n.category === c.name; }).length;
    dialog({
      title: "Delete “" + c.name + "”?",
      text: count ? "Its " + plural(count, "note") + " move to “" + PROTECTED + "”; nothing is deleted with it."
        : "No notes are in it.",
      buttons: [{ label: "Cancel", value: false, cls: "btn-quiet", isDefault: true },
                { label: "Delete category", value: true, cls: "btn-danger-text" }],
      cancel: false
    }).then(function (yes) {
      if (!yes) return;
      S.notes.forEach(function (n) { if (n.category === c.name) n.category = PROTECTED; });
      S.categories = S.categories.filter(function (x) { return x !== c; });
      persist(); renderAll();
    });
  }

  function restore(i) {
    var t = S.trash[i];
    if (!t) return;
    S.trash.splice(i, 1);
    if (!S.categories.some(function (c) { return c.name === t.note.category; })) t.note.category = PROTECTED;
    if (noteById(t.note.id)) t.note.id = S.nextId++;
    t.note.updated = Date.now();
    S.notes.push(t.note);
    persist(); renderAll();
    toast("“" + (t.note.title || "Untitled") + "” is back in your notes.");
  }

  // Cannot be taken back, so Enter and Escape both give the safe answer.
  function deleteForever(i) {
    var t = S.trash[i];
    if (!t) return;
    dialog({
      title: "Delete for good?",
      text: "“" + (t.note.title || "Untitled") + "” will be gone. This cannot be undone.",
      buttons: [{ label: "Cancel", value: false, cls: "btn-quiet", isDefault: true },
                { label: "Delete for good", value: true, cls: "btn-danger" }],
      cancel: false
    }).then(function (yes) {
      if (!yes) return;
      S.trash.splice(S.trash.indexOf(t), 1);
      persist(); renderSettings();
    });
  }

  function emptyTrash() {
    dialog({
      title: "Empty the Trash?",
      text: plural(S.trash.length, "note") + " will be gone for good. This cannot be undone.",
      buttons: [{ label: "Cancel", value: false, cls: "btn-quiet", isDefault: true },
                { label: "Empty trash", value: true, cls: "btn-danger" }],
      cancel: false
    }).then(function (yes) {
      if (!yes) return;
      S.trash = [];
      persist(); renderSettings();
    });
  }

  function resetDemo() {
    dialog({
      title: "Reset the demo?",
      text: "Your notes here are replaced by the sample notebook the demo started with.",
      buttons: [{ label: "Cancel", value: false, cls: "btn-quiet", isDefault: true },
                { label: "Reset", value: true, cls: "btn-danger-text" }],
      cancel: false
    }).then(function (yes) {
      if (!yes) return;
      clearTimeout(saveTimer);
      dirty = false;
      S = null;
      S = seed();
      persist();
      applyTheme(S.theme);
      $("#app").classList.remove("in-settings");
      $("#view-settings").hidden = true;
      $("#view-notes").classList.remove("editing");
      $("#search").value = "";
      showTab("notes");
      toast("The demo is back to its sample notes.");
    });
  }

  // ------------------------------------------------------------------
  // Share codes: "NOTE1:" + Base64(zlib(JSON)), noteorganizer/core/sharing.py
  // ------------------------------------------------------------------

  var PREFIX = "NOTE1:";
  var MAX_CODE_CHARS = 5000000, MAX_DECOMPRESSED = 20000000, MAX_NOTES = 200;
  var SHAREABLE = ["uid", "title", "body", "formatting", "comments", "category", "date",
                   "color", "recurrence", "paragraphs", "checklist"];
  var STYLE_KEYS = ["bold", "italic", "underline", "strike", "text_color", "highlight"];

  function toHexColour(css) {
    if (!css) return "";
    var m = /^#([0-9a-f]{6})$/i.exec(css.trim());
    if (m) return "#" + m[1].toLowerCase();
    m = /^#([0-9a-f])([0-9a-f])([0-9a-f])$/i.exec(css.trim());
    if (m) return ("#" + m[1] + m[1] + m[2] + m[2] + m[3] + m[3]).toLowerCase();
    m = /^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/.exec(css.trim());
    if (m && (m[4] === undefined || parseFloat(m[4]) > 0)) return hex([+m[1], +m[2], +m[3]]);
    return "";
  }

  // The note's text as the app stores it: plain characters, with styling
  // as spans of character offsets, a table as lines of "| a | b |", and
  // what belongs to a whole line -- its list, how far it is pushed in, its
  // alignment -- as paragraph entries by line number.
  function htmlToBody(html) {
    var doc = new DOMParser().parseFromString("<body>" + sanitizeHtml(html) + "</body>", "text/html");
    var chars = [], styles = [], line = 0, blocks = [];
    function emit(text, st) {
      Array.from(text).forEach(function (ch) {
        chars.push(ch); styles.push(st);
        if (ch === "\n") line += 1;
      });
    }
    function newline() { if (chars.length && chars[chars.length - 1] !== "\n") emit("\n", {}); }
    function styleOf(node, inherited) {
      var st = Object.assign({}, inherited), tag = node.tagName;
      if (tag === "B" || tag === "STRONG") st.bold = true;
      if (tag === "I" || tag === "EM") st.italic = true;
      if (tag === "U") st.underline = true;
      if (tag === "S" || tag === "STRIKE" || tag === "DEL") st.strike = true;
      if (tag === "FONT" && node.getAttribute("color")) st.text_color = toHexColour(node.getAttribute("color")) || st.text_color;
      if (node.style) {
        var c = toHexColour(node.style.color), g = toHexColour(node.style.backgroundColor);
        var family = appFamily(node.style.fontFamily), size = appSize(node.style.fontSize);
        if (c) st.text_color = c;
        if (g) st.highlight = g;
        if (family) st.font_family = family;
        if (size) st.font_size = size;
        if (node.style.fontWeight === "bold" || +node.style.fontWeight >= 600) st.bold = true;
        if (node.style.fontStyle === "italic") st.italic = true;
      }
      return st;
    }
    // A line-holding element's own properties, for the lines it holds.
    function lineProps(node, kind) {
      var align = node.style ? node.style.textAlign : "";
      return { kind: kind || null, indent: appIndent(node.getAttribute("data-indent")),
               align: align === "center" || align === "right" ? align : "left" };
    }
    function block(node, kind, inner) {
      newline();
      var first = line;
      inner();
      newline();
      // An inner line-holder ends before the one around it, so the first
      // to claim a line is the innermost, which is the one it belongs to.
      blocks.push({ first: first, last: line - 1, props: lineProps(node, kind) });
    }
    function walk(node, st, listState) {
      Array.prototype.forEach.call(node.childNodes, function (n) {
        if (n.nodeType === 3) { emit(n.nodeValue.replace(/\n/g, " "), st); return; }
        if (n.nodeType !== 1) return;
        var tag = n.tagName;
        if (tag === "BR") { emit("\n", {}); return; }
        if (tag === "TABLE") { newline(); table(n); return; }
        if (tag === "UL" || tag === "OL") { newline(); walk(n, st, { ordered: tag === "OL", n: 0 }); newline(); return; }
        if (tag === "LI") {
          block(n, listState ? (listState.ordered ? "number" : "bullet") : null, function () {
            if (listState) { listState.n += 1; emit(listState.ordered ? listState.n + ". " : "• ", {}); }
            walk(n, styleOf(n, st), null);
          });
          return;
        }
        if (tag === "DIV" || tag === "P") { block(n, null, function () { walk(n, styleOf(n, st), listState); }); return; }
        walk(n, styleOf(n, st), listState);
      });
    }
    function table(t) {
      var rows = Array.prototype.filter.call(t.querySelectorAll("tr"), function (r) { return r.closest("table") === t; });
      rows.forEach(function (r, i) {
        var cells = Array.prototype.map.call(r.children, function (c) {
          return (c.textContent || "").replace(/\s+/g, " ").trim().replace(/\|/g, "/");
        });
        emit("| " + cells.join(" | ") + " |\n", {});
        if (i === 0) emit("| " + cells.map(function () { return "---"; }).join(" | ") + " |\n", {});
      });
    }
    walk(doc.body, {}, null);
    while (chars.length && chars[chars.length - 1] === "\n") { chars.pop(); styles.pop(); }
    var body = chars.join("");
    // One span per run of each style; bold and italic together are the
    // app's own "bold_italic" (formatting.py says why).
    var spans = [];
    function runs(test, makeStyle) {
      var start = -1, value = null;
      for (var i = 0; i <= chars.length; i++) {
        var v = i < chars.length ? test(styles[i]) : null;
        if (v !== value) {
          if (value) spans.push(makeStyle(start, i, value));
          start = i; value = v;
        }
      }
    }
    runs(function (s) { return s.bold && s.italic ? "bold_italic" : s.bold ? "bold" : s.italic ? "italic" : null; },
      function (a, b, v) { return { start: a, end: b, style: v }; });
    runs(function (s) { return s.underline ? "underline" : null; }, function (a, b, v) { return { start: a, end: b, style: v }; });
    runs(function (s) { return s.strike ? "strike" : null; }, function (a, b, v) { return { start: a, end: b, style: v }; });
    runs(function (s) { return s.text_color || null; }, function (a, b, v) { return { start: a, end: b, style: "text_color", value: v }; });
    runs(function (s) { return s.highlight || null; }, function (a, b, v) { return { start: a, end: b, style: "highlight", value: v }; });
    runs(function (s) { return s.font_family || null; }, function (a, b, v) { return { start: a, end: b, style: "font_family", value: v }; });
    runs(function (s) { return s.font_size || null; }, function (a, b, v) { return { start: a, end: b, style: "font_size", value: v }; });
    spans.sort(function (x, y) { return x.start - y.start || x.end - y.end; });
    // One entry per line that is more than a plain left-aligned paragraph,
    // as the app's normalize_paragraphs keeps them.
    var lineCount = body ? body.split("\n").length : 0, owner = {};
    blocks.forEach(function (b) {
      for (var l = b.first; l <= b.last && l < lineCount; l++) if (!(l in owner)) owner[l] = b.props;
    });
    var paragraphs = Object.keys(owner).map(Number).sort(function (x, y) { return x - y; })
      .map(function (l) {
        var p = owner[l], entry = { line: l };
        if (p.kind) entry.kind = p.kind;
        if (p.indent) entry.indent = p.indent;
        if (p.align !== "left") entry.align = p.align;
        return entry;
      })
      .filter(function (e) { return e.kind || e.indent || e.align; });
    return { body: body, formatting: spans, paragraphs: paragraphs };
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // The reverse: a shared note's text, spans and paragraph entries as the
  // editor's markup.
  function bodyToHtml(body, formatting, paragraphs) {
    var chars = Array.from(String(body || ""));
    var st = chars.map(function () { return {}; });
    (Array.isArray(formatting) ? formatting : []).forEach(function (sp) {
      if (!sp || typeof sp !== "object") return;
      var a = sp.start, b = sp.end;
      if (!Number.isInteger(a) || !Number.isInteger(b) || a < 0 || b <= a) return;
      b = Math.min(b, chars.length);
      var style = sp.style, value = typeof sp.value === "string" && /^#[0-9a-f]{6}$/i.test(sp.value) ? sp.value : null;
      // Only the fonts and sizes the app offers, as its own reader keeps them.
      var family = style === "font_family" && A.fontFamilies.indexOf(sp.value) >= 0 ? sp.value : "";
      var size = style === "font_size" && A.fontSizes.indexOf(sp.value) >= 0 ? sp.value : 0;
      for (var i = a; i < b; i++) {
        if (style === "bold" || style === "bold_italic") st[i].bold = true;
        if (style === "italic" || style === "bold_italic") st[i].italic = true;
        if (style === "underline") st[i].underline = true;
        if (style === "strike") st[i].strike = true;
        if (style === "text_color" && value) st[i].text_color = value;
        if (style === "highlight" && value) st[i].highlight = value;
        if (family) st[i].font_family = family;
        if (size) st[i].font_size = size;
      }
    });
    // What a line wears as a whole, by its number: pushed in, aligned.
    var lineAttrs = {};
    (Array.isArray(paragraphs) ? paragraphs : []).forEach(function (p) {
      if (!p || typeof p !== "object" || !Number.isInteger(p.line) || p.line < 0) return;
      var level = Number.isInteger(p.indent) ? appIndent(p.indent) : 0;
      var align = p.align === "center" || p.align === "right" ? p.align : "";
      var attrs = "";
      if (level) attrs += ' data-indent="' + level + '"';
      if (align) attrs += ' style="text-align: ' + align + '"';
      if (attrs && !(p.line in lineAttrs)) lineAttrs[p.line] = attrs;
    });
    function attrsOf(k) { return lineAttrs[k] || ""; }
    function inline(from, to) {
      var out = "", i = from;
      while (i < to) {
        var j = i + 1, key = JSON.stringify(st[i]);
        while (j < to && JSON.stringify(st[j]) === key) j++;
        var text = escapeHtml(chars.slice(i, j).join("")), s = st[i];
        if (s.bold) text = "<b>" + text + "</b>";
        if (s.italic) text = "<i>" + text + "</i>";
        if (s.underline) text = "<u>" + text + "</u>";
        if (s.strike) text = "<s>" + text + "</s>";
        var css = [];
        if (s.text_color) css.push("color: " + s.text_color);
        if (s.highlight) css.push("background-color: " + s.highlight);
        if (s.font_family) css.push('font-family: &quot;' + s.font_family + '&quot;');
        if (s.font_size) css.push("font-size: " + s.font_size + "pt");
        if (css.length) text = '<span style="' + css.join("; ") + '">' + text + "</span>";
        out += text;
        i = j;
      }
      return out;
    }
    var lines = [], start = 0;
    for (var i = 0; i <= chars.length; i++) {
      if (i === chars.length || chars[i] === "\n") { lines.push([start, i]); start = i + 1; }
    }
    function lineText(l) { return chars.slice(l[0], l[1]).join(""); }
    function isRow(t) { t = t.trim(); return t.length > 1 && t[0] === "|" && t[t.length - 1] === "|"; }
    function isSep(t) { return /^\s*\|(\s*:?-{3,}:?\s*\|)+\s*$/.test(t) || /^\s*\|(\s*~\s*\|)+\s*$/.test(t); }
    function cells(t) { t = t.trim().slice(1, -1); return t.split("|").map(function (c) { return escapeHtml(c.trim().replace(/<br>/gi, " ")); }); }
    var html = "", k = 0;
    while (k < lines.length) {
      var text = lineText(lines[k]);
      if (isRow(text)) {
        var rows = [];
        while (k < lines.length && isRow(lineText(lines[k]))) { rows.push(lineText(lines[k])); k++; }
        html += "<table><tbody>";
        rows.forEach(function (r, ri) {
          if (isSep(r)) return;
          var head = ri === 0 && rows[1] && isSep(rows[1]);
          html += "<tr>" + cells(r).map(function (c) { return head ? "<th>" + (c || "<br>") + "</th>" : "<td>" + (c || "<br>") + "</td>"; }).join("") + "</tr>";
        });
        html += "</tbody></table>";
        continue;
      }
      var bullet = /^[•◦▪] /.test(text), numbered = /^\d+\. /.exec(text);
      if (bullet || numbered) {
        var tag = bullet ? "ul" : "ol";
        html += "<" + tag + ">";
        while (k < lines.length) {
          var lt = lineText(lines[k]);
          var m = bullet ? /^[•◦▪] /.exec(lt) : /^\d+\. /.exec(lt);
          if (!m) break;
          html += "<li" + attrsOf(k) + ">" + (inline(lines[k][0] + Array.from(m[0]).length, lines[k][1]) || "<br>") + "</li>";
          k++;
        }
        html += "</" + tag + ">";
        continue;
      }
      html += "<div" + attrsOf(k) + ">" + (inline(lines[k][0], lines[k][1]) || "<br>") + "</div>";
      k++;
    }
    return sanitizeHtml(html);
  }

  function bytesToB64url(bytes) {
    var bin = "";
    for (var i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_");
  }
  function b64urlToBytes(text) {
    var s = text.replace(/-/g, "+").replace(/_/g, "/");
    if (!/^[A-Za-z0-9+\/]*={0,2}$/.test(s)) throw new Error("bad base64");
    while (s.length % 4) s += "=";
    var bin = atob(s), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function compressed(bytes) {
    var stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate"));
    return new Response(stream).arrayBuffer().then(function (b) { return new Uint8Array(b); });
  }
  // Never more than `limit` bytes out, as the app's _bounded_decompress.
  function decompressed(bytes, limit) {
    var reader = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate")).getReader();
    var parts = [], total = 0;
    function next() {
      return reader.read().then(function (r) {
        if (r.done) {
          var out = new Uint8Array(total), at = 0;
          parts.forEach(function (p) { out.set(p, at); at += p.length; });
          return out;
        }
        total += r.value.length;
        if (total > limit) { reader.cancel(); throw new Error("too large"); }
        parts.push(r.value);
        return next();
      });
    }
    return next();
  }

  function shareView(n) {
    var text = htmlToBody(n.html);
    var view = {
      uid: n.uid, title: n.title, body: text.body, formatting: text.formatting, paragraphs: text.paragraphs,
      comments: n.comments, category: n.category, date: n.date, color: n.color,
      recurrence: normRec(n.recurrence),
      checklist: n.checklist.map(function (c) { return { text: c.text, done: !!c.done }; })
    };
    var out = {};
    SHAREABLE.forEach(function (k) { if (k in view) out[k] = view[k]; });
    return out;
  }

  function encodeShareCode(notes) {
    var payload = { v: 1, notes: notes.map(shareView) };
    var raw = new TextEncoder().encode(JSON.stringify(payload));
    return compressed(raw).then(function (z) { return PREFIX + bytesToB64url(z); });
  }

  var DAMAGED = "This share code is damaged or incomplete. Ask the sender to copy the whole code again.";
  function decodeShareCode(code) {
    return Promise.resolve().then(function () {
      if (typeof code !== "string") throw new Error("That doesn't look like a share code.");
      code = code.split(/\s+/).join("");
      if (!code) throw new Error("No code was pasted.");
      if (code.length > MAX_CODE_CHARS) throw new Error("That code is far too large to import safely.");
      if (code.indexOf(PREFIX) !== 0) {
        throw new Error("This isn't a Note Organizer share code. A valid code starts with “" + PREFIX + "”.");
      }
      var bytes;
      try { bytes = b64urlToBytes(code.slice(PREFIX.length)); }
      catch (e) { throw new Error("This share code is damaged or incomplete. Ask the sender to copy the whole code again — chat apps sometimes cut long codes short."); }
      return decompressed(bytes, MAX_DECOMPRESSED).catch(function () {
        throw new Error("This share code is damaged, or too large to import safely. Ask the sender to send it again.");
      });
    }).then(function (raw) {
      var payload;
      try { payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw)); }
      catch (e) { throw new Error(DAMAGED); }
      if (!payload || typeof payload !== "object" || Array.isArray(payload) || !("notes" in payload)) {
        throw new Error("This share code doesn't contain any notes.");
      }
      var version = "v" in payload ? payload.v : 1;
      if (typeof version !== "number") throw new Error(DAMAGED);
      if (version > 1) throw new Error("This code was made by a newer version of Note Organizer. Update the app to import it.");
      if (!Array.isArray(payload.notes) || !payload.notes.length) throw new Error("This share code doesn't contain any notes.");
      if (payload.notes.length > MAX_NOTES) {
        throw new Error("This code contains " + payload.notes.length + " notes, which is over the " + MAX_NOTES + "-note limit for a single code.");
      }
      return payload.notes.map(function (n) {
        var out = {};
        if (n && typeof n === "object") SHAREABLE.forEach(function (k) { if (k in n) out[k] = n[k]; });
        return out;
      });
    });
  }

  function str(v, max) { return typeof v === "string" ? v.slice(0, max || 100000) : ""; }

  function importShared(shared) {
    var added = 0, updated = 0;
    shared.forEach(function (sn) {
      var catName = str(sn.category, 40).trim() || PROTECTED;
      if (!S.categories.some(function (c) { return c.name === catName; })) {
        var used = S.categories.map(function (c) { return c.color; });
        S.categories.push({ name: catName, color: A.paletteColors.filter(function (c) { return used.indexOf(c) < 0; })[0] || A.paletteColors[0] });
      }
      var date = readDate(str(sn.date, 40));
      var fields = {
        title: str(sn.title, 300),
        html: bodyToHtml(str(sn.body), sn.formatting, sn.paragraphs),
        comments: str(sn.comments),
        category: catName,
        date: date || "",
        color: /^#[0-9a-f]{6}$/i.test(str(sn.color)) ? sn.color.toLowerCase() : "",
        recurrence: date ? normRec(sn.recurrence) : normRec({}),
        checklist: (Array.isArray(sn.checklist) ? sn.checklist : []).slice(0, 500)
          .filter(function (c) { return c && typeof c === "object" && typeof c.text === "string"; })
          .map(function (c) { return { text: c.text.slice(0, 500), done: !!c.done }; })
      };
      var uid = str(sn.uid, 100).trim();
      var mine = uid ? S.notes.filter(function (n) { return n.uid === uid; })[0] : null;
      if (mine) {
        Object.keys(fields).forEach(function (k) { mine[k] = fields[k]; });
        mine.updated = Date.now();
        updated++;
      } else {
        var n = blankNote(fields);
        if (uid) n.uid = uid;
        S.notes.push(n);
        S.ui.openId = n.id;
        added++;
      }
    });
    persist();
    renderAll();
    var parts = [];
    if (added) parts.push("Imported " + plural(added, "note"));
    if (updated) parts.push((added ? "updated " : "Updated ") + plural(updated, "note") + " already here");
    return parts.join(", ") + ".";
  }

  function showShareCode(n) {
    flush(false);
    if (!window.CompressionStream) { toast("This browser cannot make share codes."); return; }
    encodeShareCode([n]).then(function (code) {
      var area = el("textarea", { readonly: true, "aria-label": "Share code" });
      area.value = code;
      var msg = el("div", { class: "msg good", role: "status" });
      dialog({
        title: "Share code for “" + (n.title || "Untitled") + "”",
        text: "Anyone with this code can bring the note into their copy of Note Organizer with Import code. " +
          "It is a copy of the text, compressed — not encrypted.",
        body: el("div", null, area, msg),
        buttons: [{ label: "Close", value: null, cls: "btn-quiet" },
                  { label: "Copy", value: null, cls: "btn-accent", isDefault: true, handler: function () {
                    function picked() { area.focus(); area.select(); msg.textContent = "Selected — press Ctrl+C to copy."; }
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                      navigator.clipboard.writeText(code).then(function () { msg.textContent = "Copied."; }, picked);
                    } else picked();
                    return false;
                  } }],
        cancel: null
      });
      area.select();
    });
  }

  function importDialog() {
    if (!window.DecompressionStream) { toast("This browser cannot read share codes."); return; }
    var area = el("textarea", { "aria-label": "Paste a share code", placeholder: "NOTE1:…" });
    var msg = el("div", { class: "msg", role: "status" });
    dialog({
      title: "Import code",
      text: "Paste a share code, from this demo or from the desktop app.",
      body: el("div", null, area, msg),
      focus: "textarea",
      buttons: [{ label: "Close", value: null, cls: "btn-quiet" },
                { label: "Import", value: null, cls: "btn-accent", isDefault: true, handler: function () {
                  msg.className = "msg";
                  msg.textContent = "Reading…";
                  decodeShareCode(area.value).then(function (shared) {
                    msg.className = "msg good";
                    msg.textContent = importShared(shared);
                    area.value = "";
                  }, function (err) {
                    msg.className = "msg bad";
                    msg.textContent = err.message;
                  });
                  return false;
                } }],
      cancel: null
    });
  }

  // ------------------------------------------------------------------
  // Tabs and the whole screen
  // ------------------------------------------------------------------

  function showTab(tab) {
    if (tab !== S.ui.tab) flush(false);
    S.ui.tab = tab;
    persist();
    $("#tab-notes").setAttribute("aria-selected", tab === "notes" ? "true" : "false");
    $("#tab-cal").setAttribute("aria-selected", tab === "cal" ? "true" : "false");
    $("#view-notes").hidden = tab !== "notes";
    $("#view-cal").hidden = tab !== "cal";
    $("#view-settings").hidden = true;
    $("#app").classList.remove("in-settings");
    if (tab === "cal") renderCalendar();
    else { renderList(); renderEditor(); }
  }

  function renderAll() {
    renderShowOptions();
    renderList();
    if (!$("#view-settings").hidden) renderSettings();
    else if (S.ui.tab === "cal") renderCalendar();
    else renderEditor();
  }

  function init() {
    load();
    applyTheme(S.theme);
    // How far one level of indent pushes a line in, as the app draws it.
    document.documentElement.style.setProperty("--indent-step", A.indentStep + "px");

    var sort = $("#sort");
    SORTS.forEach(function (o) { sort.appendChild(el("option", { value: o, text: o })); });
    sort.value = S.ui.sort;
    sort.addEventListener("change", function () { S.ui.sort = sort.value; persist(); renderList(); });
    renderShowOptions();
    $("#show").addEventListener("change", function () { S.ui.show = $("#show").value; persist(); renderList(); });
    var group = $("#group");
    group.checked = !!S.ui.group;
    group.addEventListener("change", function () { S.ui.group = group.checked; persist(); renderList(); });

    var search = $("#search");
    search.addEventListener("input", function () { renderList(); });
    search.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && search.value) { e.preventDefault(); search.value = ""; renderList(); }
      if (e.key === "ArrowDown") { var first = $(".nc-open"); if (first) { e.preventDefault(); first.focus(); } }
    });
    $("#search-clear").addEventListener("click", function () { search.value = ""; renderList(); search.focus(); });

    // The list walks with the arrow keys.
    $("#note-list").addEventListener("keydown", function (e) {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      var items = Array.prototype.slice.call(document.querySelectorAll(".nc-open"));
      var i = items.indexOf(document.activeElement);
      if (i < 0) return;
      e.preventDefault();
      var j = e.key === "ArrowDown" ? Math.min(items.length - 1, i + 1) : Math.max(0, i - 1);
      items[j].focus();
    });

    $("#new-note").addEventListener("click", function () { newNote(); });
    $("#import-code").addEventListener("click", importDialog);
    $("#open-settings").addEventListener("click", function () { showSettings(); });
    $("#set-back").addEventListener("click", closeSettings);
    document.querySelectorAll(".set-nav [data-section]").forEach(function (b) {
      b.addEventListener("click", function () { S.ui.section = b.getAttribute("data-section"); persist(); renderSettings(); });
    });
    $("#tab-notes").addEventListener("click", function () { showTab("notes"); });
    $("#tab-cal").addEventListener("click", function () { showTab("cal"); });
    $(".tabs").addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        var next = S.ui.tab === "notes" ? "cal" : "notes";
        showTab(next);
        $(next === "cal" ? "#tab-cal" : "#tab-notes").focus();
      }
    });
    $("#cal-prev").addEventListener("click", function () { var m = monthStart(); setMonth(new Date(m.getFullYear(), m.getMonth() - 1, 1)); });
    $("#cal-next").addEventListener("click", function () { var m = monthStart(); setMonth(new Date(m.getFullYear(), m.getMonth() + 1, 1)); });
    $("#cal-prev-year").addEventListener("click", function () { var m = monthStart(); setMonth(new Date(m.getFullYear() - 1, m.getMonth(), 1)); });
    $("#cal-next-year").addEventListener("click", function () { var m = monthStart(); setMonth(new Date(m.getFullYear() + 1, m.getMonth(), 1)); });
    $("#cal-today").addEventListener("click", function () { var t = today(); S.ui.selDay = iso(t); setMonth(new Date(t.getFullYear(), t.getMonth(), 1)); });
    $("#reset-demo").addEventListener("click", resetDemo);

    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
        e.preventDefault();
        if (current()) { dirty = true; flush(false); setStatus("Saved"); toast("Saved."); }
      }
    });
    document.addEventListener("selectionchange", function () {
      var body = $("#ed-body");
      if (body && document.activeElement === body) updateToolbar();
    });
    // Leaving the page saves what is still waiting, as closing the app does.
    window.addEventListener("pagehide", function () { flush(false); });
    document.addEventListener("visibilitychange", function () { if (document.hidden) flush(false); });

    if (S.ui.openId !== null && !noteById(S.ui.openId)) S.ui.openId = null;
    showTab(S.ui.tab === "cal" ? "cal" : "notes");
    persist();
  }

  // Exposed for the demo's own checks (tools/check_demo.mjs), not used by the page.
  window.__demo = {
    encodeShareCode: encodeShareCode, decodeShareCode: decodeShareCode,
    htmlToBody: htmlToBody, bodyToHtml: bodyToHtml, occurrences: occurrences,
    describeRec: describeRec, readDate: readDate, legibleOn: legibleOn, lettersOn: lettersOn,
    state: function () { return S; }, importShared: importShared,
    iso: iso, parseIso: parseIso
  };

  init();
})();
