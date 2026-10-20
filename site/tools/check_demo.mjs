// Walks the built site in a real browser and photographs it.
//
//   node tools/check_demo.mjs <folder for the photographs>
//
// Serves public/ on 127.0.0.1 with the headers Netlify will send
// (public/_headers, the Content-Security-Policy included), drives Microsoft
// Edge headless over the DevTools protocol, presses what a visitor presses,
// and fails on any console error, uncaught exception or CSP violation.
// Writes share codes made by the demo to the same folder, for the app's
// own decoder to read (tools/verify_share_codes.py).

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.resolve(HERE, "..", "public");
const OUT = path.resolve(process.argv[2] || path.join(os.tmpdir(), "noteorganizer-site-shots"));
fs.mkdirSync(OUT, { recursive: true });

const EDGE = [
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
].find((p) => fs.existsSync(p));
if (!EDGE) { console.log("Microsoft Edge not found"); process.exit(2); }

// ---- A static server that sends Netlify's headers ----

const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
  ".webp": "image/webp", ".png": "image/png", ".ico": "image/x-icon", ".txt": "text/plain", ".json": "application/json" };

function netlifyHeaders() {
  const rules = [];
  let current = null;
  for (const line of fs.readFileSync(path.join(PUBLIC, "_headers"), "utf8").split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith("#")) continue;
    if (!/^\s/.test(line)) { current = { pattern: line.trim(), headers: {} }; rules.push(current); continue; }
    const at = line.indexOf(":");
    current.headers[line.slice(0, at).trim()] = line.slice(at + 1).trim();
  }
  return rules;
}
const RULES = netlifyHeaders();

// Every address the browser asked for, as the server received it: what the
// site's host would see.
const requested = [];

const server = http.createServer((req, res) => {
  requested.push(req.url);
  const url = new URL(req.url, "http://x");
  let file = path.join(PUBLIC, decodeURIComponent(url.pathname));
  if (!file.startsWith(PUBLIC)) { res.writeHead(403); res.end(); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, "index.html");
  const headers = {};
  for (const rule of RULES) {
    const re = new RegExp("^" + rule.pattern.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$");
    if (re.test(url.pathname)) Object.assign(headers, rule.headers);
  }
  if (!fs.existsSync(file)) {
    res.writeHead(404, { ...headers, "Content-Type": TYPES[".html"] });
    res.end(fs.readFileSync(path.join(PUBLIC, "404.html")));
    return;
  }
  headers["Content-Type"] = TYPES[path.extname(file)] || "application/octet-stream";
  res.writeHead(200, headers);
  res.end(fs.readFileSync(file));
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const BASE = `http://127.0.0.1:${server.address().port}`;

// ---- Edge over the DevTools protocol ----

const profile = fs.mkdtempSync(path.join(os.tmpdir(), "no-site-edge-"));
const port = 9300 + Math.floor(Math.random() * 500);
const edge = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars",
  "--force-color-profile=srgb", "about:blank"], { stdio: "ignore" });

async function waitFor(fn, ms = 15000) {
  const end = Date.now() + ms;
  for (;;) {
    try { const v = await fn(); if (v) return v; } catch { /* not yet */ }
    if (Date.now() > end) throw new Error("timed out");
    await new Promise((r) => setTimeout(r, 100));
  }
}

const version = await waitFor(async () => (await fetch(`http://127.0.0.1:${port}/json/version`)).json());
const ws = new WebSocket(version.webSocketDebuggerUrl);
await new Promise((ok) => ws.addEventListener("open", ok, { once: true }));
let nextId = 1;
const pending = new Map();
const listeners = [];
ws.addEventListener("message", (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { ok, fail } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? fail(new Error(JSON.stringify(msg.error))) : ok(msg.result);
  } else if (msg.method) listeners.forEach((l) => l(msg));
});
function send(method, params = {}, sessionId) {
  const id = nextId++;
  ws.send(JSON.stringify({ id, method, params, sessionId }));
  return new Promise((ok, fail) => pending.set(id, { ok, fail }));
}

const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
const page = (method, params) => send(method, params, sessionId);
await page("Page.enable");
await page("Runtime.enable");
await page("Log.enable");

const problems = [];
const results = [];
listeners.push((msg) => {
  if (msg.sessionId !== sessionId) return;
  if (msg.method === "Runtime.exceptionThrown") {
    problems.push("exception: " + (msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text));
  }
  if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
    problems.push("console.error: " + msg.params.args.map((a) => a.value ?? a.description).join(" "));
  }
  if (msg.method === "Log.entryAdded" && (msg.params.entry.level === "error")) {
    const text = msg.params.entry.text + (msg.params.entry.url ? " " + msg.params.entry.url : "");
    // The walk visits /nowhere on purpose, to see the 404 page.
    if (!/favicon/.test(text) && !/404.*\/nowhere$/.test(text)) problems.push("log: " + text);
  }
});

async function viewport(width, height, mobile, scheme) {
  await page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
  await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: scheme }] });
  await page("Emulation.setTouchEmulationEnabled", { enabled: mobile });
}

function nextLoad() {
  return new Promise((ok) => {
    const l = (msg) => { if (msg.sessionId === sessionId && msg.method === "Page.loadEventFired") { listeners.splice(listeners.indexOf(l), 1); ok(); } };
    listeners.push(l);
  });
}

async function go(url) {
  const loaded = nextLoad();
  await page("Page.navigate", { url: /^(file|https?):/.test(url) ? url : BASE + url });
  await loaded;
  await sleep(250);
}

// Follows a link the way a click does, and waits for the page it opens.
async function follow(selector) {
  const loaded = nextLoad();
  await click(selector);
  await loaded;
  await sleep(300);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function js(expression) {
  const r = await page("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error("in page: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  return r.result.value;
}

async function shot(name, full = false) {
  const params = { format: "png" };
  if (full) {
    const { cssContentSize } = await page("Page.getLayoutMetrics");
    params.captureBeyondViewport = true;
    params.clip = { x: 0, y: 0, width: cssContentSize.width, height: Math.min(cssContentSize.height, 12000), scale: 1 };
  }
  const { data } = await page("Page.captureScreenshot", params);
  fs.writeFileSync(path.join(OUT, name + ".png"), Buffer.from(data, "base64"));
}

async function click(selector) {
  const ok = await js(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return false; e.click(); return true; })()`);
  if (!ok) throw new Error("nothing to click at " + selector);
  await sleep(120);
}

async function typeInto(selector, text) {
  await js(`document.querySelector(${JSON.stringify(selector)}).focus()`);
  await page("Input.insertText", { text });
  await sleep(80);
}

function check(name, condition, detail = "") {
  results.push({ name, ok: !!condition, detail });
}

async function noHorizontalScroll(label) {
  const wide = await js("document.documentElement.scrollWidth - document.documentElement.clientWidth");
  check(`${label}: no sideways scroll`, wide <= 1, `${wide}px wider than the screen`);
}

try {
  // ---------------- The site's pages ----------------
  for (const [scheme, w, h, mobile, tag] of [["dark", 1366, 900, false, "desktop-dark"],
                                             ["light", 1366, 900, false, "desktop-light"],
                                             ["dark", 390, 844, true, "phone-dark"],
                                             ["light", 390, 844, true, "phone-light"]]) {
    await viewport(w, h, mobile, scheme);
    for (const p of ["index.html", "how-its-built.html", "in-my-words.html", "testing.html", "privacy.html",
                     "nowhere"]) {
      await go("/" + p);
      await noHorizontalScroll(`${p} ${tag}`);
      if (p === "index.html" || (mobile && p !== "nowhere")) await shot(`site-${p.replace(".html", "")}-${tag}`, true);
      if (mobile) await shot(`site-${p.replace(".html", "")}-${tag}-top`);
    }
  }
  await viewport(390, 844, true, "dark");
  await go("/index.html");
  await click("#menu-toggle");
  await shot("site-index-phone-menu-open");
  check("phone menu opens", await js("document.getElementById('site-nav').classList.contains('open')"));

  // ---------------- The feedback page, as the app opens it ----------------
  // The privacy policy promises the details reach the site only with the
  // form: the app puts them after a "#", which a browser never sends.
  await viewport(1366, 900, false, "light");
  const asked = requested.length;
  await go("/feedback.html#version=9.9.9&notes=3&title=SECRET");
  const listed = await js("[...document.querySelectorAll('#details-list li')].map(li => li.textContent).join(' | ')");
  check("the feedback page lists the details after the '#'",
    listed.includes("App version: 9.9.9") && listed.includes("Notes: 3"), listed);
  check("...fills the form with them", (await js("document.querySelector('input[name=version]').value")) === "9.9.9");
  check("...and nothing the app does not name", !listed.includes("SECRET"), listed);
  const sent = requested.slice(asked).filter((u) => u.includes("9.9.9") || u.includes("SECRET"));
  check("...while the site was never sent them", sent.length === 0, sent.join(", "));
  await shot("site-feedback-from-the-app");
  await go("/feedback.html?version=0.95.391&notes=4");
  check("an older app's details, in the query, are still listed",
    (await js("document.getElementById('details-list').textContent")).includes("App version: 0.95.391"));
  await go("/feedback.html");
  check("opened by itself, the page lists no details", await js("document.getElementById('details').hidden"));
  await follow("a[href='privacy.html#send-feedback']");
  check("its privacy link opens the policy at Send feedback",
    (await js("location.pathname + location.hash")) === "/privacy.html#send-feedback",
    await js("location.href"));
  await go("/index.html");
  await follow(".site-footer a[href='privacy.html']");
  check("the footer leads to the privacy policy",
    (await js("document.querySelector('h1') && document.querySelector('h1').textContent")) === "Privacy policy",
    await js("location.href"));

  // ---------------- Opened from the folder, with no server ----------------
  // As the owner previews it: a double-click on public/index.html, then
  // the buttons. A link to a folder works on a server and shows a file
  // listing here, which is how this walk came to exist.
  await viewport(1366, 860, false, "dark");
  const fileUrl = (p) => "file:///" + path.join(PUBLIC, p).replace(/\\/g, "/");
  await go(fileUrl("index.html"));
  await follow(".hero .btn-primary");
  check("from the folder, the overview's button opens the demo",
    (await js("document.querySelectorAll('.note-card').length")) === 9, await js("location.href"));
  await follow(".db-home");
  check("from the folder, the demo's Site link comes back", await js("!!document.querySelector('.hero h1')"));
  // The demo is reached from the overview's buttons: the menu and the
  // pages' footer no longer carry it (the owner's call, 2026-10-14), so a
  // page's menu leads back to the overview, and that opens it.
  await go(fileUrl("in-my-words.html"));
  await follow(".site-nav a[href='index.html']");
  check("from the folder, a page's menu leads back to the overview",
    await js("!!document.querySelector('.hero h1')"), await js("location.href"));
  await follow(".hero .btn-primary");
  check("...and from there the demo opens", (await js("document.querySelectorAll('.note-card').length")) > 0,
    await js("location.href"));

  // ---------------- The demo, desktop ----------------
  await viewport(1366, 860, false, "dark");
  await go("/demo/");
  await js("localStorage.clear()");
  await go("/demo/");
  await shot("demo-desktop-welcome");
  check("demo opens on the welcome note", (await js("document.getElementById('ed-title').value")).startsWith("Welcome"));
  check("nine sample notes", (await js("document.querySelectorAll('.note-card').length")) === 9);

  await js("[...document.querySelectorAll('.nc-open')].find(b => b.textContent.includes('Weekly meal plan')).click()");
  await sleep(200);
  await shot("demo-desktop-table-note");
  check("the meal plan shows its table", (await js("document.querySelectorAll('#ed-body table tr').length")) === 5);
  const deskCount = await js("document.getElementById('ed-count').textContent");
  await js("document.getElementById('ed-body').focus()");
  check("the title has no box of its own until it is edited",
    await js("getComputedStyle(document.getElementById('ed-title')).backgroundColor === 'rgba(0, 0, 0, 0)'"),
    await js("getComputedStyle(document.getElementById('ed-title')).backgroundColor"));

  await js("[...document.querySelectorAll('.nc-open')].find(b => b.textContent.includes('Shopping list')).click()");
  await sleep(200);
  await shot("demo-desktop-checklist");
  check("checklist counts 2/4", await js("document.querySelector('.cl-head').textContent.includes('2/4')"));
  await js("document.querySelectorAll('.cl-item input[type=checkbox]')[2].click()");
  await sleep(150);
  check("ticking an item counts 3/4", await js("document.querySelector('.cl-head').textContent.includes('3/4')"));
  await js("document.querySelectorAll('.cl-arrows button')[3].click()");
  await sleep(150);
  check("the down arrow moves an item", (await js("document.querySelectorAll('.cl-text')[2].value")) === "Bread");

  // Search narrows, and a miss says so.
  await typeInto("#search", "team");
  await sleep(150);
  const shown = await js("[...document.querySelectorAll('.nc-title')].map(t => t.textContent)");
  check("search 'team' finds the stand-up and the review", shown.length === 2 && shown.some((t) => t.includes("stand-up")), JSON.stringify(shown));
  await shot("demo-desktop-search");
  await js("document.getElementById('search').value=''; document.getElementById('search').dispatchEvent(new Event('input'))");
  await typeInto("#search", "zebra");
  await sleep(150);
  check("a search that finds nothing says so", await js("document.querySelector('.list-empty').textContent.includes('No notes match')"));
  await shot("demo-desktop-no-match");
  await click("#search-clear");

  // A new note, typed, saved by itself, still there after a reload.
  await click("#new-note");
  await typeInto("#ed-title", "Plant the tulips");
  await js("document.getElementById('ed-body').focus()");
  await page("Input.insertText", { text: "Before the first frost." });
  await sleep(1100);
  check("autosave says so", (await js("document.getElementById('ed-status').textContent")) === "Auto-saved");
  await go("/demo/");
  check("a new note survives a reload", await js("[...document.querySelectorAll('.nc-title')].some(t => t.textContent.includes('Plant the tulips'))"));

  // Formatting: bold on a selection, then the share code carries it.
  await js(`(() => { const b = document.getElementById('ed-body'); b.focus(); const r = document.createRange();
    r.selectNodeContents(b.firstChild || b); const s = getSelection(); s.removeAllRanges(); s.addRange(r); })()`);
  await js("document.querySelector('[data-state=bold]').dispatchEvent(new MouseEvent('mousedown', {bubbles:true})); document.querySelector('[data-state=bold]').click()");
  await sleep(900);
  check("bold applied", await js("!!document.querySelector('#ed-body b')"));

  // The formatting bar's font and size lists, and indent, as the app's: on
  // the same selection, pressed as a visitor presses them.
  const press = (sel) => js(`(() => { const b = document.querySelector(${JSON.stringify(sel)});
    b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true})); b.click(); return true; })()`);
  const pick = (label) => js(`(() => { const i = [...document.querySelectorAll('.popup .menu-item')]
    .find(x => x.textContent === ${JSON.stringify(label)}); if (!i) return false; i.click(); return true; })()`);
  await press("#tb-family"); await sleep(150);
  await shot("demo-desktop-font-list");
  check("the font list offers the app's fonts",
    (await js("[...document.querySelectorAll('.popup .menu-item')].map(i => i.textContent).join('|')")) ===
      ["Default", ...(await js("NO_APP.fontFamilies"))].join("|"));
  check("Georgia chosen", await pick("Georgia")); await sleep(150);
  await press("#tb-size"); await sleep(150);
  check("16 chosen", await pick("16")); await sleep(150);
  await press("[aria-label='Indent more']"); await sleep(100);
  await press("[aria-label='Indent more']"); await sleep(100);
  await press("[aria-label='Centre']"); await sleep(900);
  // Any element may wear them: a browser puts a font on the <b> itself when
  // the selection is exactly one bold run.
  const wornNow = `(() => { const b = document.getElementById('ed-body'), s = [...b.querySelectorAll('[style]')];
    return { family: s.some(x => /Georgia/.test(x.style.fontFamily)), size: s.some(x => x.style.fontSize === '16pt'),
             indent: !!b.querySelector('[data-indent="2"]'), centre: [...b.querySelectorAll('div')].some(d => d.style.textAlign === 'center'),
             labels: document.querySelector('#tb-family .tb-label').textContent + '/' + document.querySelector('#tb-size .tb-label').textContent,
             html: b.innerHTML.slice(0, 300) }; })()`;
  const worn = await js(wornNow);
  check("font, size, indent and alignment applied", worn.family && worn.size && worn.indent && worn.centre, JSON.stringify(worn));
  check("the two lists say what the text wears", worn.labels === "Georgia/16", worn.labels);
  await shot("demo-desktop-fonts");
  // Saved, and read back after a reload: what a note cannot carry is
  // cleaned out on the way into storage, and a style on a <b> once was.
  await go("/demo/");
  await js("[...document.querySelectorAll('.nc-open')].find(b => b.textContent.includes('Plant the tulips')).click()");
  await sleep(200);
  const kept = await js(wornNow);
  check("after a reload the note keeps its font, size, indent and alignment",
    kept.family && kept.size && kept.indent && kept.centre, JSON.stringify(kept));

  // Share codes: made here, read back here, and kept for the app's decoder.
  const codes = await js(`(async () => {
    const S = __demo.state();
    const out = {};
    for (const n of S.notes) out[n.title] = await __demo.encodeShareCode([n]);
    return out;
  })()`);
  fs.writeFileSync(path.join(OUT, "share_codes_from_demo.json"), JSON.stringify(codes, null, 1));
  const back = await js(`(async () => {
    const S = __demo.state();
    const n = S.notes.find(x => x.title === 'Shopping list');
    const code = await __demo.encodeShareCode([n]);
    const got = (await __demo.decodeShareCode(code))[0];
    return { title: got.title, items: got.checklist.length, done: got.checklist.filter(c => c.done).length, uid: got.uid === n.uid };
  })()`);
  check("a share code reads back in the demo", back.title === "Shopping list" && back.items === 4 && back.done === 3 && back.uid, JSON.stringify(back));
  const bad = await js(`__demo.decodeShareCode('hello').then(() => 'accepted', e => e.message)`);
  check("a wrong code gets the app's message", bad.startsWith("This isn't a Note Organizer share code"), bad);

  // Codes made by the app itself, if the verifier wrote them.
  const fromApp = path.join(OUT, "share_codes_from_app.json");
  if (fs.existsSync(fromApp)) {
    const appCodes = JSON.parse(fs.readFileSync(fromApp, "utf8"));
    for (const [name, spec] of Object.entries(appCodes)) {
      const got = await js(`(async () => {
        const notes = await __demo.decodeShareCode(${JSON.stringify(spec.code)});
        const html = __demo.bodyToHtml(notes[0].body, notes[0].formatting, notes[0].paragraphs);
        const box = document.createElement('div'); box.innerHTML = html;
        const spans = [...box.querySelectorAll('span')];
        return { title: notes[0].title, bold: [...box.querySelectorAll('b')].map(b => b.textContent),
                 rows: box.querySelectorAll('tr').length, items: (notes[0].checklist || []).length,
                 families: spans.map(s => s.style.fontFamily.replace(/["']/g, '')).filter(Boolean),
                 sizes: spans.map(s => s.style.fontSize).filter(Boolean),
                 indents: [...box.querySelectorAll('[data-indent]')].map(e => e.getAttribute('data-indent')),
                 aligns: [...box.querySelectorAll('div, li')].map(e => e.style.textAlign).filter(Boolean),
                 text: box.textContent };
      })()`);
      const want = spec.expect;
      const has = (list, wanted) => (wanted || []).every((w) => list.includes(w));
      check(`the app's code "${name}" reads in the demo`,
        got.title === want.title && (want.bold || []).every((b) => got.bold.includes(b))
        && (want.rows === undefined || got.rows === want.rows) && (want.items === undefined || got.items === want.items)
        && has(got.families, want.families) && has(got.sizes, want.sizes)
        && has(got.indents, want.indents) && has(got.aligns, want.aligns),
        JSON.stringify({ got: { ...got, text: got.text.slice(0, 80) }, want }));
      if (name === "fonts") {
        // Through the Import code box's own step, into a stored note.
        const stored = await js(`(async () => {
          __demo.importShared(await __demo.decodeShareCode(${JSON.stringify(spec.code)}));
          const n = __demo.state().notes.find(x => x.title === ${JSON.stringify(want.title)});
          return n ? n.html : '';
        })()`);
        check("the app's fonts and indents are kept by Import code",
          /data-indent="2"/.test(stored) && /text-align: center/.test(stored) && /Georgia/.test(stored) && /16pt/.test(stored),
          stored.slice(0, 300));
      }
    }
  } else {
    check("codes from the app were provided", false, "run tools/verify_share_codes.py first to write them");
  }

  // Delete goes to the Trash, and comes back.
  await js("[...document.querySelectorAll('.nc-open')].find(b => b.textContent.includes('Dentist')).click()");
  await sleep(150);
  await js("[...document.querySelectorAll('.ed-actions button')].find(b => b.textContent.includes('Delete')).click()");
  await sleep(150);
  await shot("demo-desktop-delete-question");
  await js("[...document.querySelectorAll('.dialog button')].find(b => b.textContent.includes('Move to the Trash')).click()");
  await sleep(150);
  check("deleting leaves the list", !(await js("[...document.querySelectorAll('.nc-title')].some(t => t.textContent.includes('Dentist'))")));
  await click("#open-settings");
  await click(".set-nav [data-section=trash]");
  await shot("demo-desktop-trash");
  check("the Trash holds it", await js("document.querySelector('.trash-row b').textContent === 'Dentist'"));
  await js("document.querySelector('.trash-row .btn-accent').click()");
  await sleep(150);
  await click("#set-back");
  check("restored", await js("[...document.querySelectorAll('.nc-title')].some(t => t.textContent.includes('Dentist'))"));

  // Calendar: the weekly stand-up lands on every Monday from its own start
  // date, and on none before it. The expectation is read from the note, not
  // assumed: assuming "every Monday of the month" passed or failed by the
  // day of the month the walk happened to run on.
  await click("#tab-cal");
  const mondays = await js(`(() => {
    const start = __demo.state().notes.find(n => n.title === 'Team stand-up').date;
    const cells = [...document.querySelectorAll('.cal-day:not(.blank)')];
    const first = document.querySelectorAll('.cal-day.blank').length;
    const month = __demo.state().ui.calMonth;
    const wrong = [];
    cells.forEach((c, i) => {
      if ((first + i) % 7 !== 0) return;
      const key = month + '-' + String(i + 1).padStart(2, '0');
      const shown = c.textContent.includes('stand-up');
      if (shown !== (key >= start)) wrong.push(key + (shown ? ' shown' : ' missing'));
    });
    return { start, wrong };
  })()`);
  check("the stand-up is on every Monday from its start", mondays.wrong.length === 0, JSON.stringify(mondays));
  await js("[...document.querySelectorAll('.cal-day:not(.blank)')].find(c => c.textContent.includes('stand-up')).click()");
  await sleep(200);
  await shot("demo-desktop-calendar");
  check("a day opens below the month", await js("!document.getElementById('day-panel').hidden"));

  // Settings: every theme, and the shortcut back.
  await click("#open-settings");
  await click(".set-nav [data-section=appearance]");
  await shot("demo-desktop-settings-dark");
  await js("[...document.querySelectorAll('.theme-chip')].find(b => b.textContent.includes('Soft Lavender')).click()");
  await sleep(150);
  await shot("demo-desktop-settings-light");
  await click("#set-back");
  await click("#tab-notes");
  await shot("demo-desktop-light-notes");
  for (const theme of ["dark_ocean", "dark_forest", "dark_slate", "light_sky", "light_mint", "light_warm"]) {
    await js(`(() => { const s = __demo.state(); s.theme = ${JSON.stringify(theme)}; localStorage.setItem('noteorganizer-demo-v1', JSON.stringify(s)); })()`);
    await go("/demo/");
    await shot("demo-theme-" + theme);
  }

  // ---------------- The demo, on a phone ----------------
  await viewport(390, 844, true, "dark");
  await go("/demo/");
  await js("localStorage.clear()");
  await go("/demo/");
  await noHorizontalScroll("demo phone list");
  await shot("demo-phone-list");
  check("on a phone the list comes first", await js("getComputedStyle(document.getElementById('editor')).display === 'none'"));
  await js("[...document.querySelectorAll('.nc-open')].find(b => b.textContent.includes('Weekly meal plan')).click()");
  await sleep(250);
  await noHorizontalScroll("demo phone editor");
  await shot("demo-phone-editor");
  await shot("demo-phone-editor-full", true);
  check("on a phone the note takes the screen", await js("getComputedStyle(document.querySelector('.sidebar')).display === 'none'"));
  check("on a phone the title has a line of its own",
    await js("document.getElementById('ed-title').getBoundingClientRect().width > 0.8 * document.querySelector('.ed-inner').getBoundingClientRect().width"),
    String(await js("document.getElementById('ed-title').getBoundingClientRect().width")));
  const phoneCount = await js("document.getElementById('ed-count').textContent");
  check("the word count is the same on a phone", phoneCount === deskCount, `${phoneCount} vs ${deskCount}`);
  await click(".ed-back");
  await sleep(250);
  check("Back returns to the list", await js("getComputedStyle(document.querySelector('.sidebar')).display !== 'none'"));
  await click("#tab-cal");
  await js("[...document.querySelectorAll('.cal-day:not(.blank)')].find(c => c.querySelector('.dot')).click()");
  await sleep(300);
  await noHorizontalScroll("demo phone calendar");
  await shot("demo-phone-calendar");
  await shot("demo-phone-calendar-full", true);
  await click("#tab-notes");
  await click("#open-settings");
  await noHorizontalScroll("demo phone settings");
  await shot("demo-phone-settings");
  await click(".set-nav [data-section=about]");
  await shot("demo-phone-about");
  await click("#set-back");
  await js("[...document.querySelectorAll('.nc-open')].find(b => b.textContent.includes('Team stand-up')).click()");
  await sleep(250);
  await shot("demo-phone-repeat-full", true);
  await click("#import-code").catch(() => {});
} catch (err) {
  problems.push("the walk stopped: " + err.message);
} finally {
  ws.close();
  edge.kill();
  server.close();
  await sleep(300);
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* Edge may hold it a moment */ }
}

for (const r of results) console.log((r.ok ? "ok   " : "FAIL ") + r.name + (r.ok || !r.detail ? "" : "  -- " + r.detail));
for (const p of problems) console.log("FAIL " + p);
const failed = results.filter((r) => !r.ok).length + problems.length;
console.log(`\n${results.length - results.filter((r) => !r.ok).length}/${results.length} checks passed, ${problems.length} browser problem(s). Photographs in ${OUT}`);
process.exit(failed ? 1 : 0);
