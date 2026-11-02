// Note Organizer for Android, re-created for the browser.
//
// The real app is native Android, in Kotlin, and cannot run in a page. This
// file imitates its everyday screens -- the list, a note, the calendar,
// Settings -- in the phone's own shapes. The rules underneath are not
// written twice: demo.js, the desktop demo, is loaded first and lends its
// own (window.NO_DEMO): the palettes and their arithmetic, dates and
// repeats, the sort orders, a note's body to HTML and back, and share codes
// in the desktop app's format -- so a code made here opens in the desktop
// demo, and one made there opens here, as between the two apps.
// Everything is kept in this browser's localStorage, under a key of its own.

(function () {
  "use strict";

  var D = window.NO_DEMO, A = window.NO_APP, PHONE = window.NO_ANDROID || {};
  var screen = document.getElementById("screen");
  if (!D || !A) {
    screen.textContent = "The demo could not load its files.";
    return;
  }
  var el = D.el, plural = D.plural, iso = D.iso, parseIso = D.parseIso;

  var KEY = "noteorganizer-android-demo-v1";
  var S = null, storageOk = true;
  var query = "";
  var saveTimer = null, dirty = false;

  // ------------------------------------------------------------------
  // Pictures drawn as lines, the phone's outlined icons
  // ------------------------------------------------------------------

  var LINES = {
    notes: "M7 3h7l5 5v13H7zM14 3v5h5M10 12h6M10 16h6",
    calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
    settings: "M12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3" +
              "M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1",
    back: "M19 12H5M11 6l-6 6 6 6",
    undo: "M9 14L4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3",
    redo: "M15 14l5-5-5-5M20 9H10a6 6 0 0 0 0 12h3",
    share: "M18 8a3 3 0 1 0 0-6a3 3 0 1 0 0 6M6 15a3 3 0 1 0 0-6a3 3 0 1 0 0 6M18 22a3 3 0 1 0 0-6" +
           "a3 3 0 1 0 0 6M8.6 13.5l6.8 4M15.4 6.5l-6.8 4",
    info: "M12 22a10 10 0 1 0 0-20a10 10 0 1 0 0 20M12 11v6M12 7.5v.5",
    more: "M12 5v.5M12 12v.5M12 19v.5",
    search: "M11 18a7 7 0 1 0 0-14a7 7 0 1 0 0 14M21 21l-5-5",
    close: "M6 6l12 12M18 6L6 18",
    prev: "M15 6l-6 6 6 6",
    next: "M9 6l6 6-6 6"
  };
  function line(name, size) {
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    [["viewBox", "0 0 24 24"], ["width", size || 22], ["height", size || 22], ["aria-hidden", "true"],
     ["fill", "none"], ["stroke", "currentColor"], ["stroke-width", name === "more" ? "3" : "1.8"],
     ["stroke-linecap", "round"], ["stroke-linejoin", "round"]]
      .forEach(function (a) { svg.setAttribute(a[0], a[1]); });
    var path = document.createElementNS(ns, "path");
    path.setAttribute("d", LINES[name]);
    svg.appendChild(path);
    return svg;
  }
  function iconBtn(name, label, onPress, extra) {
    return el("button", Object.assign({ type: "button", class: "icon-btn", "aria-label": label, title: label,
      onclick: onPress }, extra || {}), line(name));
  }

  // ------------------------------------------------------------------
  // The notebook: kept in this browser
  // ------------------------------------------------------------------

  function categoryNamed(names, wanted) {
    return names.indexOf(wanted) >= 0 ? wanted : D.PROTECTED;
  }

  function seed() {
    var t = D.today(), monday = D.addDays(t, -D.weekday(t));
    var state = {
      v: 1, nextId: 1, notes: [], trash: [], name: "", reminderShown: "",
      categories: Object.keys(A.categoryColors).map(function (name) {
        return { name: name, color: A.categoryColors[name] };
      }),
      theme: window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
      ui: { tab: "notes", openId: null, sort: D.SORTS[0], show: "All", page: null,
            calMonth: iso(t).slice(0, 7), selDay: iso(t), checklistOpen: null, commentsOpen: null }
    };
    var names = state.categories.map(function (c) { return c.name; });
    var clock = Date.now();
    function add(fields) {
      clock -= 3600 * 1000;
      var n = D.blankNote(fields, state);
      n.created = n.updated = clock;
      state.notes.push(n);
      return n;
    }
    add({
      title: "Welcome to the Android demo \u{1F44B}",
      html: "<div>This is a re-creation of Note Organizer for Android, so you can try it without " +
        "installing anything. What you write here stays in this browser.</div><div><br></div>" +
        "<div><b>\u{1F4DD} Write</b></div><ul><li>The <b>+</b> button starts a note. Give it a " +
        "title and write; it saves itself as you go.</li><li>The bar under the note shapes your " +
        "words: bold, italic, lists and alignment.</li><li><b>⋮</b> at the top of a note adds " +
        "a checklist for to-dos and comments.</li></ul>" +
        "<div><b>\u{1F5C2} Organise</b></div><ul><li><b>Search</b> at the top looks through all " +
        "your notes at once.</li><li><b>Sort</b> and <b>Show</b> arrange the list. Categories give " +
        "notes a colour.</li></ul>" +
        "<div><b>\u{1F512} Share and keep safe</b></div><ul><li><b>Share</b> turns a note into a " +
        "code: paste it into the desktop demo's Import code, and it opens there.</li><li>Deleted " +
        "notes wait in <b>Settings → Trash</b>, so a slip can be undone.</li></ul>" +
        "<div><b>\u{1F3A8} Make it yours</b></div><ul><li><b>Settings → Appearance</b> has the " +
        "desktop's eight themes, four light and four dark.</li></ul><div><br></div>" +
        "<div>The app does more than this page: tables written in their cells, a calculator, " +
        "templates, backups, attached files, and sharing through the phone's own share sheet.</div>"
    });
    add({
      title: "Home-made bread", category: categoryNamed(names, "Personal"), color: "#f9c74f",
      date: iso(D.addDays(t, 2)),
      html: "<div><b>500 g flour</b></div><div>300 ml warm water</div><div>10 g salt</div><div><br></div>" +
        "<div>Knead for 10 minutes, let it rise for 2 hours, bake for 45 minutes at 220 °C.</div>",
      checklist: [{ text: "flour", done: true }, { text: "yeast", done: true }, { text: "seeds", done: false }]
    });
    add({
      title: "September expenses",
      html: "<table><tbody><tr><th>What</th><th>How much</th></tr>" +
        "<tr><td>rent</td><td>1500</td></tr><tr><td>electricity</td><td>180</td></tr>" +
        "<tr><td>internet</td><td>60</td></tr></tbody></table>"
    });
    add({
      title: "", category: categoryNamed(names, "Ideas"),
      html: "<div>An idea for Ana's birthday: a boat trip, then cake from the little place in the " +
        "centre.</div>"
    });
    add({
      title: "To read", category: categoryNamed(names, "Work"), pinned: true,
      date: iso(D.addDays(monday, -14)),
      recurrence: D.normRec({ freq: "weekly", interval: 1, weekdays: [0, 3] }),
      html: "<div>the book borrowed from Radu</div><div>the article about sleep</div>",
      checklist: [{ text: "the book", done: true }, { text: "the article", done: false }]
    });
    return state;
  }

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) {
        var s = JSON.parse(raw);
        if (s && s.v === 1 && Array.isArray(s.notes) && Array.isArray(s.categories)) {
          s.trash = Array.isArray(s.trash) ? s.trash : [];
          s.ui = s.ui || {};
          if (D.SORTS.indexOf(s.ui.sort) < 0) s.ui.sort = D.SORTS[0];
          if (!A.themes[s.theme]) s.theme = "light";
          s.notes.forEach(function (n) { n.recurrence = D.normRec(n.recurrence); });
          S = s;
          purgeTrash();
          return;
        }
      }
    } catch (e) { /* unreadable: start again from the sample notebook */ }
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
    var limit = Date.now() - D.TRASH_DAYS * 86400000;
    S.trash = S.trash.filter(function (t) { return t.deletedAt > limit; });
  }

  function noteById(id) { return S.notes.filter(function (n) { return n.id === id; })[0] || null; }
  function current() { return S.ui.openId === null || S.ui.openId === undefined ? null : noteById(S.ui.openId); }
  function category(name) {
    return S.categories.filter(function (c) { return c.name === name; })[0] ||
      { name: name, color: A.categoryColors[D.PROTECTED] || A.paletteColors[0] };
  }
  function palette() { return A.themes[S.theme] || A.themes.light; }
  function isDark() { return A.darkThemes.indexOf(S.theme) >= 0; }

  function setTheme(key) {
    S.theme = key;
    D.applyTheme(key);
    persist();
    render();
  }

  // ------------------------------------------------------------------
  // Sheets, menus and the toast
  // ------------------------------------------------------------------

  var layer = document.getElementById("layer");
  var toastBox = document.getElementById("toast");
  var toastTimer = null;

  function toast(message, actionLabel, action) {
    clearTimeout(toastTimer);
    toastBox.textContent = "";
    toastBox.appendChild(el("span", { text: message }));
    if (actionLabel) {
      toastBox.appendChild(el("button", { type: "button", text: actionLabel, onclick: function () {
        toastBox.classList.remove("show");
        action();
      } }));
    }
    toastBox.classList.add("show");
    toastTimer = setTimeout(function () { toastBox.classList.remove("show"); }, actionLabel ? 6000 : 3000);
  }

  function closeSheet() { layer.textContent = ""; }

  function sheet(title, body, intro) {
    closeSheet();
    var box = el("div", { class: "sheet", role: "dialog", "aria-label": title },
      el("div", { class: "grab" }), el("h3", { text: title }), intro ? el("p", { text: intro }) : null, body);
    layer.appendChild(el("div", { class: "scrim", onclick: closeSheet }));
    layer.appendChild(box);
    var first = box.querySelector("button, input, textarea");
    if (first) first.focus();
    return box;
  }

  function menuItem(label, action, extra) {
    return el("button", Object.assign({ type: "button", class: "menu-item", onclick: function () {
      closeSheet();
      action();
    } }, extra || {}), label);
  }

  function confirmSheet(title, intro, yes, action) {
    sheet(title, el("div", { class: "sheet-actions" },
      el("button", { type: "button", class: "btn", text: "Cancel", onclick: closeSheet }),
      el("button", { type: "button", class: "btn primary", text: yes, onclick: function () {
        closeSheet();
        action();
      } })), intro);
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && layer.childNodes.length) closeSheet();
  });

  // ------------------------------------------------------------------
  // Saving a note: a moment after typing stops, and at once on leaving it
  // ------------------------------------------------------------------

  function touched() {
    dirty = true;
    setStatus("");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () { flush(true); }, 700);
  }

  function flush(announce) {
    clearTimeout(saveTimer);
    var n = current();
    if (!dirty || !n) return;
    var title = document.getElementById("ed-title"), body = document.getElementById("ed-body");
    var comments = document.getElementById("ed-comments");
    if (title) n.title = title.value.slice(0, 300);
    if (body) n.html = D.sanitizeHtml(body.innerHTML);
    if (comments) n.comments = comments.value;
    n.updated = Date.now();
    dirty = false;
    persist();
    if (announce) setStatus("Auto-saved");
  }

  function setStatus(text) {
    var s = document.getElementById("ed-status");
    if (s) s.textContent = text;
  }

  function isEmpty(n) {
    return !n.title.trim() && !D.plainText(n.html).trim() && !n.comments.trim() && !n.checklist.length;
  }

  // ------------------------------------------------------------------
  // The note list
  // ------------------------------------------------------------------

  function haystack(n) {
    return [n.title, D.plainText(n.html), n.comments,
            n.checklist.map(function (c) { return c.text; }).join(" "), n.category].join(" \n ").toLowerCase();
  }

  function visibleNotes() {
    var q = query.trim().toLowerCase();
    var list = S.notes.filter(function (n) {
      if (S.ui.show === "\u{1F4CC} Pinned" && !n.pinned) return false;
      if (S.ui.show !== "All" && S.ui.show !== "\u{1F4CC} Pinned" && n.category !== S.ui.show) return false;
      return !q || haystack(n).indexOf(q) >= 0;
    });
    return D.sortNotes(list, S.ui.sort);
  }

  function dueToday() {
    var t = D.today();
    return S.notes.filter(function (n) { return D.occurrences(n, t, t, 1).length > 0; }).length;
  }

  function cardFor(n) {
    var cat = category(n.category), P = palette();
    // The preview leaves tables out, as the phone's card does: a table read
    // as a line ran its cells together ("What How much rent 1500"), and the
    // badge already says there is one.
    var prose = n.html.replace(/<table[\s\S]*?<\/table>/gi, " ");
    var lines = D.plainText(prose).split("\n").map(function (s) { return s.trim(); }).filter(Boolean);
    var title = n.title.trim(), borrowed = !title;
    var shown = title || lines[0] || "Untitled";
    var preview = (borrowed ? lines.slice(1) : lines).join(" ");
    var rec = D.normRec(n.recurrence);
    var marks = (n.pinned ? "\u{1F4CC} " : "") + (rec.freq ? "\u{1F501} " : "");
    var tables = (n.html.match(/<table/gi) || []).length;
    var done = n.checklist.filter(function (c) { return c.done; }).length;
    var meta = el("div", { class: "c-meta" },
      el("span", { class: "c-cat", text: n.category }),
      n.date && !rec.freq ? el("span", { text: "\u{1F4C5} " + D.showDate(n.date) }) : null,
      rec.freq ? el("span", { text: "\u{1F501} " + D.describeRec(rec) }) : null,
      tables ? el("span", { text: "▦ " + plural(tables, "table") }) : null,
      n.checklist.length ? el("span", { text: "☑ " + done + "/" + n.checklist.length }) : null);
    return el("button", { type: "button", class: "card", role: "listitem",
      vars: { "--stripe": n.color || cat.color, "--catlabel": D.legibleOn(cat.color, P.card, P.text) },
      onclick: function () { openNote(n.id); } },
      el("p", { class: "c-title" + (borrowed ? " borrowed" : ""), text: marks + shown }),
      preview ? el("p", { class: "c-preview", text: preview }) : null, meta);
  }

  function fillCards(box) {
    box.textContent = "";
    var list = visibleNotes();
    if (!list.length) {
      box.appendChild(el("p", { class: "empty", text: query ? "No notes match your search." : "No notes here yet. Tap + to write one." }));
      return;
    }
    list.forEach(function (n) { box.appendChild(cardFor(n)); });
  }

  function choose(title, options, currentValue, pick) {
    sheet(title, el("div", { role: "radiogroup" }, options.map(function (o) {
      return menuItem(o, function () { pick(o); }, { role: "radio", "aria-checked": o === currentValue ? "true" : "false" });
    })));
  }

  function renderNotes() {
    var t = iso(D.today());
    screen.appendChild(el("div", { class: "top-row" },
      el("h1", { class: "greeting", text: S.name ? "Hi " + S.name + "," : "Note Organizer" }),
      iconBtn("more", "More", function () {
        sheet("Notes", el("div", null,
          menuItem("\u{1F4E5} Import a share code", function () { S.ui.tab = "settings"; S.ui.page = "import"; render(); }),
          menuItem("⚙ Settings", function () { S.ui.tab = "settings"; S.ui.page = null; render(); })));
      })));
    var due = dueToday();
    if (due && S.reminderShown !== t) {
      var bar = el("div", { class: "reminder", role: "status" },
        el("button", { type: "button", class: "go", onclick: function () {
          S.reminderShown = t;
          S.ui.tab = "calendar"; S.ui.calMonth = t.slice(0, 7); S.ui.selDay = t;
          persist(); render();
        } }, "\u{1F514} You have " + plural(due, "note") + " for today (" + D.longDate(D.today()).replace(/ \d{4}$/, "") + ")."),
        iconBtn("close", "Dismiss", function () { S.reminderShown = t; persist(); render(); }));
      screen.appendChild(bar);
    }
    var cards = el("div", { class: "cards", role: "list", "aria-label": "Your notes" });
    var input = el("input", { type: "search", id: "search", placeholder: "Search notes…", "aria-label": "Search notes",
      autocomplete: "off", oninput: function () { query = input.value; fillCards(cards); } });
    input.value = query;
    screen.appendChild(el("div", { class: "search" }, line("search", 20), input));
    var shows = ["All", "\u{1F4CC} Pinned"].concat(S.categories.map(function (c) { return c.name; }));
    screen.appendChild(el("div", { class: "chips" },
      el("button", { type: "button", class: "chip", onclick: function () {
        choose("Sort", D.SORTS, S.ui.sort, function (o) { S.ui.sort = o; persist(); render(); });
      } }, "Sort: " + S.ui.sort + " ▾"),
      el("button", { type: "button", class: "chip", onclick: function () {
        choose("Show", shows, S.ui.show, function (o) { S.ui.show = o; persist(); render(); });
      } }, "Show: " + S.ui.show + " ▾")));
    fillCards(cards);
    screen.appendChild(cards);
    screen.appendChild(el("button", { type: "button", class: "fab", "aria-label": "New note", title: "New note",
      onclick: function () { newNote(""); } }, "+"));
  }

  function newNote(date) {
    var n = D.blankNote({ date: date || "" }, S);
    S.notes.push(n);
    S.ui.openId = n.id;
    S.ui.checklistOpen = S.ui.commentsOpen = null;
    persist();
    render();
    var title = document.getElementById("ed-title");
    if (title) title.focus();
  }

  function openNote(id) {
    S.ui.openId = id;
    S.ui.checklistOpen = S.ui.commentsOpen = null;
    persist();
    render();
  }

  function closeNote() {
    flush(false);
    var n = current();
    S.ui.openId = null;
    // A note left as it was started, with nothing in it, is not kept.
    if (n && isEmpty(n)) S.notes = S.notes.filter(function (x) { return x !== n; });
    persist();
    render();
  }

  // ------------------------------------------------------------------
  // A note
  // ------------------------------------------------------------------

  var TOOLS = [["bold", "B", "Bold", ""], ["italic", "I", "Italic", "i"],
               ["underline", "U", "Underline", "u"], ["strikeThrough", "S", "Strikethrough", "s"]];

  function fmtBar() {
    var bar = el("div", { class: "fmt", id: "fmt", role: "toolbar", "aria-label": "Formatting" });
    function tool(content, title, command, cls) {
      var b = el("button", { type: "button", class: cls || "", title: title, "aria-label": title,
        "data-state": command, "aria-pressed": "false" }, content);
      // Pressing a tool must not take the cursor out of the note.
      b.addEventListener("mousedown", function (e) { e.preventDefault(); });
      b.addEventListener("click", function () {
        var body = document.getElementById("ed-body");
        if (body && document.activeElement !== body) body.focus();
        document.execCommand(command, false, null);
        touched();
        updateFmt();
      });
      bar.appendChild(b);
    }
    TOOLS.forEach(function (t) { tool(t[1], t[2], t[0], t[3]); });
    bar.appendChild(el("span", { class: "gap" }));
    tool("•", "Bulleted list", "insertUnorderedList");
    tool("1.", "Numbered list", "insertOrderedList");
    bar.appendChild(el("span", { class: "gap" }));
    tool(D.icon("left"), "Align left", "justifyLeft");
    tool(D.icon("center"), "Centre", "justifyCenter");
    tool(D.icon("right"), "Align right", "justifyRight");
    return bar;
  }

  function updateFmt() {
    var bar = document.getElementById("fmt"), body = document.getElementById("ed-body");
    if (!bar || !body) return;
    var inside = document.activeElement === body;
    bar.querySelectorAll("[data-state]").forEach(function (b) {
      var on = false;
      if (inside) { try { on = document.queryCommandState(b.getAttribute("data-state")); } catch (e) { on = false; } }
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  document.addEventListener("selectionchange", updateFmt);

  function renderEditor(n) {
    var top = el("div", { class: "ed-top" },
      iconBtn("back", "Back to the notes", closeNote),
      iconBtn("undo", "Undo", function () { var b = document.getElementById("ed-body"); if (b) b.focus(); document.execCommand("undo"); touched(); }),
      iconBtn("redo", "Redo", function () { var b = document.getElementById("ed-body"); if (b) b.focus(); document.execCommand("redo"); touched(); }),
      el("span", { class: "spacer" }),
      el("span", { class: "ed-status", id: "ed-status", "aria-live": "polite" }),
      iconBtn("share", "Share", function () { flush(false); shareSheet(n); }),
      iconBtn("info", "Details", function () { flush(false); detailsSheet(n); }),
      iconBtn("more", "More", function () { flush(false); noteMenu(n); }));
    screen.appendChild(top);

    var cat = category(n.category);
    var title = el("input", { class: "ed-title", id: "ed-title", placeholder: "Title", "aria-label": "Title",
      maxlength: "300", oninput: touched,
      onkeydown: function (e) {
        // Enter in the title goes to the note, as on the phone.
        if (e.key === "Enter") { e.preventDefault(); document.getElementById("ed-body").focus(); }
      } });
    title.value = n.title;
    // The date reads day first, as the app shows it; the browser's own date
    // field, laid over the chip and unseen, is what a tap opens -- shown, it
    // spoke the browser's language ("10/26/2026").
    var date = el("input", { type: "date", class: "date-under", "aria-label": "Date", onchange: function () {
      n.date = date.value || "";
      if (!n.date) n.recurrence = D.normRec({});
      n.updated = Date.now();
      persist();
      render();
    } });
    date.value = n.date || "";
    var rec = D.normRec(n.recurrence);
    var meta = el("div", { class: "ed-meta" },
      el("button", { type: "button", class: "chip", onclick: function () { categorySheet(n); } },
        el("span", { class: "ed-cat-dot", vars: { "--dot": n.color || cat.color } }), n.category + " ▾"),
      el("label", { class: "chip date-chip" }, "\u{1F4C5} " + (n.date ? D.showDate(n.date) : "Date"), date),
      el("button", { type: "button", class: "chip", onclick: function () {
        if (!n.date) { toast("Give the note a date first: a repeat starts on it."); return; }
        repeatSheet(n);
      } }, "\u{1F501} " + (rec.freq ? "Repeats" : "Repeat")));
    var body = el("div", { class: "ed-body", id: "ed-body", contenteditable: "true", role: "textbox",
      "aria-multiline": "true", "aria-label": "Note", "data-placeholder": "Write here…",
      oninput: touched });
    body.innerHTML = D.sanitizeHtml(n.html);
    // Words come in as words: a pasted page brings no styles of its own here.
    body.addEventListener("paste", function (e) {
      var text = (e.clipboardData || window.clipboardData).getData("text/plain");
      e.preventDefault();
      document.execCommand("insertText", false, text);
    });
    var ed = el("div", { class: "ed" }, title, meta,
      rec.freq ? el("p", { class: "ed-repeat", text: "\u{1F501} " + D.describeRec(rec) }) : null, body);
    if (n.checklist.length || S.ui.checklistOpen === n.id) ed.appendChild(checklistSection(n));
    if (n.comments || S.ui.commentsOpen === n.id) {
      var comments = el("textarea", { class: "comments", id: "ed-comments", "aria-label": "Comments",
        placeholder: "Comments", oninput: touched });
      comments.value = n.comments;
      ed.appendChild(el("p", { class: "section-label", text: "Comments" }));
      ed.appendChild(comments);
    }
    screen.appendChild(ed);
    document.getElementById("phone").insertBefore(fmtBar(), document.getElementById("navbar"));
  }

  function checklistSection(n) {
    var box = el("div", { class: "checklist" });
    var done = n.checklist.filter(function (c) { return c.done; }).length;
    box.appendChild(el("p", { class: "section-label", text: "Checklist · " + done + "/" + n.checklist.length }));
    n.checklist.forEach(function (item, i) {
      var tick = el("input", { type: "checkbox", "aria-label": "Done: " + item.text, onchange: function () {
        item.done = tick.checked;
        n.updated = Date.now();
        persist();
        render();
      } });
      tick.checked = !!item.done;
      var text = el("input", { class: "cl-text", "aria-label": "Item", oninput: function () {
        item.text = text.value.slice(0, 500);
        n.updated = Date.now();
        persist();
        setStatus("Auto-saved");
      } });
      text.value = item.text;
      box.appendChild(el("div", { class: "cl-row" + (item.done ? " done" : "") }, tick, text,
        iconBtn("close", "Remove " + item.text, function () {
          n.checklist.splice(i, 1);
          n.updated = Date.now();
          persist();
          render();
        })));
    });
    var add = el("input", { placeholder: "A new item", "aria-label": "A new item", enterkeyhint: "done" });
    function addItem() {
      var text = add.value.trim();
      if (!text) return;
      n.checklist.push({ text: text.slice(0, 500), done: false });
      n.updated = Date.now();
      S.ui.checklistOpen = n.id;
      persist();
      render();
      var again = document.querySelector(".cl-add input");
      if (again) again.focus();
    }
    add.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); addItem(); } });
    box.appendChild(el("div", { class: "cl-add" }, add,
      el("button", { type: "button", class: "btn", text: "Add", onclick: addItem })));
    return box;
  }

  function noteMenu(n) {
    sheet(n.title.trim() || "This note", el("div", null,
      !n.checklist.length && S.ui.checklistOpen !== n.id ?
        menuItem("☑ Add a checklist", function () { S.ui.checklistOpen = n.id; render(); var f = document.querySelector(".cl-add input"); if (f) f.focus(); }) : null,
      !n.comments && S.ui.commentsOpen !== n.id ?
        menuItem("\u{1F4AC} Add comments", function () { S.ui.commentsOpen = n.id; render(); var c = document.getElementById("ed-comments"); if (c) c.focus(); }) : null,
      menuItem(n.pinned ? "\u{1F4CC} Unpin" : "\u{1F4CC} Pin", function () {
        n.pinned = !n.pinned;
        n.updated = Date.now();
        persist();
        toast(n.pinned ? "Pinned to the top of the list." : "Unpinned.");
      }),
      menuItem("\u{1F5D1} Delete", function () { deleteNote(n); }, { class: "menu-item danger" })));
  }

  function deleteNote(n) {
    flush(false);
    S.notes = S.notes.filter(function (x) { return x !== n; });
    var entry = Object.assign({}, n, { deletedAt: Date.now() });
    S.trash.unshift(entry);
    S.ui.openId = null;
    persist();
    render();
    toast("Moved to the Trash.", "Undo", function () { restore(entry); });
  }

  function restore(entry) {
    S.trash = S.trash.filter(function (t) { return t !== entry; });
    var n = Object.assign({}, entry);
    delete n.deletedAt;
    if (noteById(n.id)) n.id = S.nextId++;
    S.notes.push(n);
    persist();
    render();
  }

  function categorySheet(n) {
    choose("Category", S.categories.map(function (c) { return c.name; }), n.category, function (name) {
      n.category = name;
      n.updated = Date.now();
      persist();
      render();
    });
  }

  function repeatSheet(n) {
    var rec = D.normRec(n.recurrence);
    var anchor = D.weekday(parseIso(n.date));
    var freq = rec.freq;
    var days = rec.weekdays.length ? rec.weekdays.slice() : [anchor];
    var LABELS = [["", "Does not repeat"], ["daily", "Every day"], ["weekly", "Every week"],
                  ["monthly", "Every month"], ["yearly", "Every year"]];
    var box = el("div");
    function draw() {
      box.textContent = "";
      LABELS.forEach(function (pair) {
        box.appendChild(el("button", { type: "button", class: "menu-item", role: "radio",
          "aria-checked": pair[0] === freq ? "true" : "false", onclick: function () { freq = pair[0]; draw(); } }, pair[1]));
      });
      if (freq === "weekly") {
        box.appendChild(el("div", { class: "sheet-body" }, el("div", { class: "wd-row", role: "group", "aria-label": "On these days" },
          D.WEEKDAYS.map(function (name, d) {
            return el("button", { type: "button", "aria-pressed": days.indexOf(d) >= 0 ? "true" : "false", onclick: function () {
              var at = days.indexOf(d);
              if (at >= 0 && days.length > 1) days.splice(at, 1);
              else if (at < 0) days.push(d);
              draw();
            } }, name);
          }))));
      }
      box.appendChild(el("div", { class: "sheet-actions" },
        el("button", { type: "button", class: "btn", text: "Cancel", onclick: closeSheet }),
        el("button", { type: "button", class: "btn primary", text: "Save", onclick: function () {
          n.recurrence = D.normRec(freq ? { freq: freq, interval: 1, weekdays: freq === "weekly" ? days : [] } : {});
          n.updated = Date.now();
          persist();
          closeSheet();
          render();
        } })));
    }
    draw();
    sheet("Repeat", box, "From " + D.showDate(n.date) + ", the note's date.");
  }

  function shareSheet(n) {
    var body = el("div", { class: "sheet-body" });
    var make = el("button", { type: "button", class: "btn primary", text: "Make a share code", onclick: function () {
      if (!window.CompressionStream) { toast("This browser cannot make share codes."); return; }
      D.encodeShareCode([n]).then(function (code) {
        body.textContent = "";
        var area = el("textarea", { class: "code-area", readonly: true, "aria-label": "Share code" });
        area.value = code;
        var msg = el("p", { class: "msg good", role: "status" });
        body.appendChild(area);
        body.appendChild(el("div", { class: "sheet-actions" },
          el("button", { type: "button", class: "btn primary", text: "Copy", onclick: function () {
            area.select();
            var done = function () { msg.textContent = "Copied. Paste it into Import code in the desktop demo, or here in Settings."; };
            if (navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(code).then(done, function () { msg.textContent = "Select the code and copy it."; });
            } else { done(); }
          } })));
        body.appendChild(msg);
      });
    } });
    body.appendChild(el("div", { class: "sheet-actions" }, make));
    sheet("Share", body, "On the phone, Share hands a note to any app: as a PDF of its page, a web page, " +
      "its words, or a share code. Here it makes the share code — text that brings the note, its " +
      "formatting, checklist and repeat into another copy of the app.");
  }

  function detailsSheet(n) {
    var text = D.plainText(n.html);
    var words = (text.match(/\S+/g) || []).length;
    function when(ms) { var d = new Date(ms); return D.showDate(iso(d)) + ", " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); }
    sheet("Details", el("div", { class: "sheet-body" },
      el("p", { text: "Created " + when(n.created) }),
      el("p", { text: "Last updated " + when(n.updated) }),
      el("p", { text: plural(words, "word") + " · " + plural(Array.from(text).length, "character") })));
  }

  // ------------------------------------------------------------------
  // The calendar
  // ------------------------------------------------------------------

  function renderCalendar() {
    var parts = S.ui.calMonth.split("-").map(Number);
    var first = new Date(parts[0], parts[1] - 1, 1);
    var start = D.addDays(first, -D.weekday(first));
    var last = new Date(parts[0], parts[1], 0);
    var end = D.addDays(last, 6 - D.weekday(last));
    function shift(months) {
      var d = new Date(parts[0], parts[1] - 1 + months, 1);
      S.ui.calMonth = iso(d).slice(0, 7);
      persist();
      render();
    }
    screen.appendChild(el("div", { class: "cal-head" },
      el("h2", { text: D.MONTHS[first.getMonth()] + " " + first.getFullYear(), "aria-live": "polite" }),
      iconBtn("prev", "Previous month", function () { shift(-1); }),
      el("button", { type: "button", class: "chip", text: "Today", onclick: function () {
        var t = D.today();
        S.ui.calMonth = iso(t).slice(0, 7);
        S.ui.selDay = iso(t);
        persist();
        render();
      } }),
      iconBtn("next", "Next month", function () { shift(1); })));
    var marks = {};
    S.notes.forEach(function (n) {
      var colour = n.color || category(n.category).color;
      D.occurrences(n, start, end).forEach(function (day) { (marks[day] = marks[day] || []).push(colour); });
    });
    var grid = el("div", { class: "cal-grid", role: "grid", "aria-label": "The month" },
      D.WEEKDAYS.map(function (w) { return el("div", { class: "cal-wd", text: w.slice(0, 1) }); }));
    var todayIso = iso(D.today());
    for (var d = start; d <= end; d = D.addDays(d, 1)) {
      (function (day) {
        var key = iso(day), dots = (marks[key] || []).slice(0, 3);
        var cls = "cal-day" + (day.getMonth() !== first.getMonth() ? " other" : "") + (key === todayIso ? " today" : "");
        grid.appendChild(el("button", { type: "button", class: cls, "aria-pressed": key === S.ui.selDay ? "true" : "false",
          "aria-label": D.longDate(day) + ((marks[key] || []).length ? ", " + plural(marks[key].length, "note") : ""),
          onclick: function () { S.ui.selDay = key; persist(); render(); } },
          el("span", { class: "cal-num", text: String(day.getDate()) }),
          el("span", { class: "cal-dots" }, dots.map(function (c) { return el("span", { vars: { "--dot": c } }); }))));
      })(d);
    }
    screen.appendChild(grid);
    var sel = parseIso(S.ui.selDay) || D.today();
    screen.appendChild(el("p", { class: "day-head", text: D.longDate(sel) }));
    var onDay = D.sortNotes(S.notes.filter(function (n) { return D.occurrences(n, sel, sel, 1).length; }), D.SORTS[0]);
    var box = el("div", { class: "cards" });
    if (!onDay.length) box.appendChild(el("p", { class: "empty", text: "Nothing on this day." }));
    onDay.forEach(function (n) { box.appendChild(cardFor(n)); });
    box.appendChild(el("button", { type: "button", class: "btn", text: "+ A note on this day",
      onclick: function () { newNote(iso(sel)); } }));
    screen.appendChild(box);
  }

  // ------------------------------------------------------------------
  // Settings
  // ------------------------------------------------------------------

  function pageHead(title) {
    return el("div", { class: "page-title" },
      iconBtn("back", "Back to Settings", function () { S.ui.page = null; persist(); render(); }),
      el("h2", { text: title }));
  }

  var PAGES = {
    name: function () {
      screen.appendChild(pageHead("Your name"));
      var input = el("input", { class: "field", "aria-label": "Your name", maxlength: "30", enterkeyhint: "done" });
      input.value = S.name;
      var saved = el("p", { class: "saved", role: "status" });
      function save() {
        S.name = input.value.trim();
        persist();
        saved.textContent = "✓ Saved";
      }
      input.addEventListener("input", function () { saved.textContent = ""; });
      input.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); save(); } });
      screen.appendChild(el("div", { class: "page-pad" },
        el("p", { text: "Shown above your notes as “Hi Maria,”. Leave it empty for no greeting." }),
        input, saved, el("div", { class: "sheet-actions" },
          el("button", { type: "button", class: "btn primary", text: "Save", onclick: save }))));
    },
    appearance: function () {
      screen.appendChild(pageHead("Appearance"));
      var dark = isDark();
      var list = dark ? A.darkThemes : A.lightThemes;
      var seg = el("div", { class: "seg", role: "group", "aria-label": "Light or dark" },
        el("button", { type: "button", "aria-pressed": dark ? "false" : "true", text: "Light",
          onclick: function () { if (isDark()) setTheme(D.partnerTheme(S.theme)); } }),
        el("button", { type: "button", "aria-pressed": dark ? "true" : "false", text: "Dark",
          onclick: function () { if (!isDark()) setTheme(D.partnerTheme(S.theme)); } }));
      var cards = el("div", { class: "themes" }, list.map(function (key) {
        var P = A.themes[key];
        return el("button", { type: "button", class: "theme-card", "aria-pressed": key === S.theme ? "true" : "false",
          onclick: function () { setTheme(key); } },
          el("span", { class: "tc-preview", vars: { background: P.card } },
            el("span", { vars: { background: P.sidebar } }),
            el("span", { class: "tc-lines", vars: { background: P.bg } },
              el("span", { vars: { background: P.accent, width: "60%" } }),
              el("span", { vars: { background: P.text, width: "85%" } }),
              el("span", { vars: { background: P.subtext, width: "45%" } }))),
          el("b", { text: A.themeLabels[key] }));
      }));
      screen.appendChild(el("div", { class: "page-pad" },
        el("p", { text: "The desktop's eight themes: four light and four dark, every colour the app's own." }),
        seg, cards));
    },
    trash: function () {
      purgeTrash();
      screen.appendChild(pageHead("Trash"));
      var box = el("div", { class: "page-pad" },
        el("p", { text: "Deleted notes wait here for " + D.TRASH_DAYS + " days, then go for good." }));
      if (!S.trash.length) box.appendChild(el("p", { class: "empty", text: "The Trash is empty." }));
      S.trash.forEach(function (entry) {
        var left = Math.max(0, D.TRASH_DAYS - Math.floor((Date.now() - entry.deletedAt) / 86400000));
        var name = entry.title.trim() || D.plainText(entry.html).trim().split("\n")[0] || "Untitled";
        box.appendChild(el("div", { class: "trash-row" },
          el("div", { class: "tr-text" }, el("b", { text: name }),
            el("small", { text: "deleted " + D.showDate(iso(new Date(entry.deletedAt))) + " · " + plural(left, "day") + " left" })),
          el("button", { type: "button", class: "btn", text: "Restore", onclick: function () { restore(entry); toast("Restored."); } }),
          el("button", { type: "button", class: "btn danger", text: "Delete", onclick: function () {
            confirmSheet("Delete for good?", "“" + name + "” cannot be brought back.", "Delete", function () {
              S.trash = S.trash.filter(function (t) { return t !== entry; });
              persist();
              render();
            });
          } })));
      });
      if (S.trash.length) {
        box.appendChild(el("div", { class: "sheet-actions" }, el("button", { type: "button", class: "btn danger",
          text: "Empty the Trash", onclick: function () {
            confirmSheet("Empty the Trash?", plural(S.trash.length, "note") + " will be gone for good.", "Empty", function () {
              S.trash = [];
              persist();
              render();
            });
          } })));
      }
      screen.appendChild(box);
    },
    "import": function () {
      screen.appendChild(pageHead("Import a share code"));
      var area = el("textarea", { class: "code-area", "aria-label": "Share code",
        placeholder: "Paste a code that starts with NOTE1:" });
      var msg = el("p", { class: "msg", role: "status" });
      screen.appendChild(el("div", { class: "page-pad" },
        el("p", { text: "A share code from the desktop demo, the desktop app or the phone app brings its note here, " +
          "formatting, checklist and repeat included. One you already have is updated." }),
        area, el("div", { class: "sheet-actions" },
          el("button", { type: "button", class: "btn primary", text: "Import", onclick: function () {
            if (!window.DecompressionStream) { msg.className = "msg bad"; msg.textContent = "This browser cannot read share codes."; return; }
            D.decodeShareCode(area.value).then(function (shared) {
              var said = D.importShared(shared, S);
              persist();
              toast(said);
              render();
            }, function (e) {
              msg.className = "msg bad";
              msg.textContent = e.message;
            });
          } })), msg));
    },
    about: function () {
      screen.appendChild(pageHead("About"));
      screen.appendChild(el("div", { class: "page-pad about" },
        el("p", null, el("b", { text: "Note Organizer for Android" }), PHONE.version ? " · version " + PHONE.version : ""),
        el("p", { text: "This page re-creates the app's screens in HTML and JavaScript. The real app is native " +
          "Android, written in Kotlin, and on its way to Google Play. It has no account and no server of its " +
          "own, and makes no connection; the phone's own backup to a Google account copies its notes while " +
          "that is on, and Settings → Backup turns that off." }),
        el("p", { text: "What you write here stays in this browser. Clearing this site's data removes it." }),
        el("p", null, el("a", { href: "../site-privacy.html", text: "This website's privacy notice" })),
        el("p", null, el("a", { href: "../demo/index.html", text: "The desktop demo" }), " · ",
          el("a", { href: "../android.html", text: "About the Android app" }))));
    }
  };

  function renderSettings() {
    if (S.ui.page && PAGES[S.ui.page]) { PAGES[S.ui.page](); return; }
    screen.appendChild(el("div", { class: "top-row" }, el("h1", { class: "greeting", text: "Settings" })));
    function row(icon, title, sub, page) {
      return el("button", { type: "button", class: "set-row", onclick: function () { S.ui.page = page; persist(); render(); } },
        el("span", { class: "sr-icon", "aria-hidden": "true", text: icon }),
        el("span", null, el("b", { text: title }), el("small", { text: sub })));
    }
    screen.appendChild(el("div", { class: "set-list" },
      row("\u{1F464}", "Your name", S.name ? "Hi " + S.name + "," : "The greeting above your notes", "name"),
      row("\u{1F3A8}", "Appearance", A.themeLabels[S.theme] + (isDark() ? ", dark" : ", light"), "appearance"),
      row("\u{1F5D1}", "Trash", S.trash.length ? plural(S.trash.length, "note") + ", kept " + D.TRASH_DAYS + " days" : "Empty", "trash"),
      row("\u{1F4E5}", "Import a share code", "A note from the desktop demo, or from anyone", "import"),
      row("ⓘ", "About", "A re-creation of the Android app" + (PHONE.version ? ", version " + PHONE.version : ""), "about")));
  }

  // ------------------------------------------------------------------
  // The frame
  // ------------------------------------------------------------------

  var navbar = document.getElementById("navbar");
  var NAV_ICONS = { notes: "notes", calendar: "calendar", settings: "settings" };
  Object.keys(NAV_ICONS).forEach(function (tab) {
    document.getElementById("nb-" + tab).appendChild(line(NAV_ICONS[tab]));
  });
  navbar.querySelectorAll("[data-tab]").forEach(function (b) {
    b.addEventListener("click", function () {
      if (current()) closeNote();
      var tab = b.getAttribute("data-tab");
      if (tab === "settings" && S.ui.tab === "settings") S.ui.page = null;
      S.ui.tab = tab;
      persist();
      render();
    });
  });

  function render() {
    closeSheet();
    var old = document.getElementById("fmt");
    if (old) old.parentNode.removeChild(old);
    screen.textContent = "";
    screen.scrollTop = 0;
    var n = current();
    navbar.hidden = !!n;
    navbar.querySelectorAll("[data-tab]").forEach(function (b) {
      if (b.getAttribute("data-tab") === S.ui.tab) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    if (n) renderEditor(n);
    else if (S.ui.tab === "calendar") renderCalendar();
    else if (S.ui.tab === "settings") renderSettings();
    else renderNotes();
  }

  document.getElementById("reset-demo").addEventListener("click", function () {
    confirmSheet("Reset the demo?", "Everything you wrote here goes, and the sample notes come back.", "Reset", function () {
      try { localStorage.removeItem(KEY); } catch (e) { /* not kept anyway */ }
      S = seed();
      query = "";
      D.applyTheme(S.theme);
      persist();
      render();
    });
  });

  // Leaving the page saves what is still waiting, as closing the app does.
  window.addEventListener("pagehide", function () { flush(false); });
  document.addEventListener("visibilitychange", function () { if (document.hidden) flush(false); });

  load();
  if (S.ui.openId !== null && S.ui.openId !== undefined && !noteById(S.ui.openId)) S.ui.openId = null;
  D.applyTheme(S.theme);
  persist();
  render();

  // For the site's own checks (tools/check_demo.mjs), not used by the page.
  window.__android = { state: function () { return S; }, render: render };
})();
