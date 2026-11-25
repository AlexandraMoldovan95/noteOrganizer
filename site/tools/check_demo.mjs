// Walks the built site in a real browser and photographs it.
//
//   py tools/check_demo.py <folder for the photographs>
//
// Only through that door, which takes the computer's turn, holds Edge's
// whole tree of processes in its job object and gives the walk a time
// limit. Started bare, a walk stopped midway left headless Edge running;
// started bare, it refuses.
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
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// The door's mark: a scratch folder of its run's own, marked as tools/guest.py
// marks one. Edge's profile goes in it, so a killed run's is swept later.
const DOOR = process.env.NOTEORG_GUEST_DOOR;
if (!DOOR || !fs.existsSync(path.join(DOOR, ".noteorg-scratch"))) {
  console.log("Run the walk through its door: py site/tools/check_demo.py <folder for the photographs>");
  process.exit(2);
}

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

const server = http.createServer((req, res) => {
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

const profile = path.join(DOOR, "edge-profile");
fs.mkdirSync(profile);
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
// Every question to Edge has a time limit: an Edge that stops answering
// fails the walk, and the clean-up below still runs.
const ANSWER_MS = 120000;
function send(method, params = {}, sessionId) {
  const id = nextId++;
  ws.send(JSON.stringify({ id, method, params, sessionId }));
  const answer = new Promise((ok, fail) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      fail(new Error(`Edge did not answer ${method} within ${ANSWER_MS / 1000} s`));
    }, ANSWER_MS);
    pending.set(id, { ok: (v) => { clearTimeout(timer); ok(v); }, fail: (e) => { clearTimeout(timer); fail(e); } });
  });
  answer.catch(() => {});   // its caller sees the failure; node must not end on it unawaited
  return answer;
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

// `motion` is the visitor's motion setting. The document pages fade their
// blocks in as they scroll into view, so a full-length photograph taken
// with motion on shows a page blank below its first screen -- which every
// photograph of them did, unnoticed, until 2026-10-24. They are photographed
// with motion reduced, as a visitor who asks for it sees them, and the
// fade has checks of its own (below).
async function viewport(width, height, mobile, scheme, motion = "no-preference") {
  await page("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
  await page("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: scheme },
                                                        { name: "prefers-reduced-motion", value: motion }] });
  await page("Emulation.setTouchEmulationEnabled", { enabled: mobile });
}

function nextLoad(ms = 60000) {
  const loaded = new Promise((ok, fail) => {
    const timer = setTimeout(() => {
      const at = listeners.indexOf(l);
      if (at >= 0) listeners.splice(at, 1);
      fail(new Error(`a page did not finish loading within ${ms / 1000} s`));
    }, ms);
    const l = (msg) => { if (msg.sessionId === sessionId && msg.method === "Page.loadEventFired") { listeners.splice(listeners.indexOf(l), 1); clearTimeout(timer); ok(); } };
    listeners.push(l);
  });
  loaded.catch(() => {});   // a walk that stopped before awaiting it must not end node on it
  return loaded;
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

// Asked again every 40ms until [ok] holds of the answer or [ms] run out;
// the last answer comes back either way. A fixed wait measures the
// machine's speed as well as the page: a busy computer could fail it with
// nothing wrong.
async function until(expression, ok, ms = 5000) {
  const end = Date.now() + ms;
  let value = await js(expression);
  while (!ok(value) && Date.now() < end) {
    await sleep(40);
    value = await js(expression);
  }
  return value;
}

async function shot(name, full = false) {
  const params = { format: "png" };
  if (full) {
    // Scrolled through first, and its pictures waited for: a picture
    // marked loading="lazy" loads only once it nears the screen, and a
    // full-length photograph taken from the top showed every one below the
    // first screen as an empty frame.
    await js(`(async () => {
      for (let y = 0; y < document.documentElement.scrollHeight; y += innerHeight) {
        scrollTo(0, y);
        await new Promise((r) => setTimeout(r, 60));
      }
      scrollTo(0, 0);
      await Promise.all([...document.images].filter((i) => !i.complete).map((i) =>
        new Promise((r) => { i.addEventListener("load", r); i.addEventListener("error", r); setTimeout(r, 3000); })));
    })()`);
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
    await viewport(w, h, mobile, scheme, "reduce");
    for (const p of ["index.html", "android.html", "how-its-built.html", "in-my-words.html", "testing.html", "nowhere"]) {
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
  await page("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
  await page("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
  await sleep(100);
  check("Escape closes the phone menu", await js("!document.getElementById('site-nav').classList.contains('open')"));

  // ---------------- The way back to the portfolio ----------------
  // site.json's portfolio_url, on every page that wears the site's header:
  // in the top right corner, last before the theme button, with the bar
  // still one row; on a phone, first in the menu (the owner, 2026-11-25).
  const portfolioUrl = JSON.parse(fs.readFileSync(path.resolve(HERE, "..", "site.json"), "utf8")).portfolio_url;
  const corner = `(() => {
    const a = document.querySelector(".site-header .portfolio-link");
    const t = document.getElementById("theme-toggle");
    if (!a || !t) return { found: false };
    const r = a.getBoundingClientRect(), tr = t.getBoundingClientRect();
    const links = [...document.querySelectorAll(".site-nav a")];
    const others = links.filter((e) => e !== a).map((e) => e.getBoundingClientRect());
    return { found: true, href: a.href, shown: r.width > 0 && r.height > 0,
             corner: r.right <= tr.left && others.every((o) => o.right <= r.left),
             row: Math.abs((r.top + r.bottom) / 2 - (tr.top + tr.bottom) / 2) <= 4,
             header: Math.round(document.querySelector(".site-header").getBoundingClientRect().height),
             first: links.every((e) => e === a || e.getBoundingClientRect().top > r.top) };
  })()`;
  check("site.json names the portfolio's address", /^https:\/\//.test(portfolioUrl || ""), String(portfolioUrl));
  // A drawn arrow or caret beside a control's words is shown, not said: a
  // screen reader reads the words alone (aria-hidden), or the control's
  // aria-label in their place (the owner, 2026-11-25). Asked on the site's
  // pages here and in both demos below. Only at either end of what is said:
  // inside, an arrow is a note's own text ("Settings → Trash" on a card).
  const arrowsSaid = `(() => {
    const g = "[\\u2190-\\u21FF\\u25B2-\\u25C5\\u2039\\u203A]";
    const drawn = new RegExp("^" + g + "|" + g + "$");
    const said = (n) => n.nodeType === 3 ? n.textContent
      : n.nodeType === 1 && n.getAttribute("aria-hidden") !== "true" ? [...n.childNodes].map(said).join("") : "";
    return [...document.querySelectorAll("a, button")]
      .filter((e) => !e.hasAttribute("aria-label") && drawn.test(said(e).trim()))
      .map((e) => e.outerHTML.slice(0, 90));
  })()`;
  // 901: the narrowest bar that still holds every page (site.css, 900).
  for (const w of [1366, 1024, 901]) {
    await viewport(w, 900, false, "light", "reduce");
    for (const p of ["index.html", "android.html", "how-its-built.html", "in-my-words.html", "testing.html",
                     "bug-reports.html", "site-privacy.html", "nowhere"]) {
      await go("/" + p);
      const c = await js(corner);
      check(`${p} at ${w}px: Portfolio in the top right corner, the bar one row`,
            c.found && c.href === new URL(portfolioUrl).href && c.shown && c.corner && c.row && c.header <= 62,
            JSON.stringify(c));
      if (p === "index.html") await shot(`site-index-portfolio-corner-${w}`);
      if (w === 1366) {
        const said = await js(arrowsSaid);
        check(`${p}: no link or button says a drawn arrow`, said.length === 0, JSON.stringify(said));
      }
    }
  }
  for (const [w, mobile, label] of [[390, true, "phone"], [900, false, "900px"]]) {
    await viewport(w, 844, mobile, "light", "reduce");
    await go("/index.html");
    const shut = await js(corner);
    check(`${label}: Portfolio waits in the closed menu, the bar one row`,
          shut.found && !shut.shown && shut.header <= 62, JSON.stringify(shut));
    await click("#menu-toggle");
    const open = await js(corner);
    check(`${label}: Portfolio is first in the open menu`, open.shown && open.first, JSON.stringify(open));
    await shot(`site-index-menu-portfolio-${w}`);
    await click("#menu-toggle");
  }

  // ---------------- The fade, with motion on ----------------
  // Kept by the owner's choice (2026-10-24), slow and gradual as it first
  // was -- a quicker one read as no animation at all -- and held to what
  // that first version broke: printing gave blank pages, a Contents link
  // landed on text still fading, and a tall table whose visible slice stayed
  // under the threshold never appeared.
  const HIDDEN_ON_SCREEN = `[...document.querySelectorAll('.doc .wrap > *')].filter((e) => {
      const r = e.getBoundingClientRect();
      return r.bottom > 0 && r.top < innerHeight && parseFloat(getComputedStyle(e).opacity) < 0.99;
    }).length`;
  // Above the lowest twelfth, where a block counts as arrived.
  const HIDDEN_ABOVE_LINE = `[...document.querySelectorAll('.doc .wrap > *')].filter((e) => {
      const r = e.getBoundingClientRect();
      return r.bottom > 0 && r.top < innerHeight * 0.9 && parseFloat(getComputedStyle(e).opacity) < 0.99;
    }).length`;
  await viewport(1366, 900, false, "light");
  await go("/how-its-built.html");
  const fading = await js(`(() => { const h = document.querySelector('.doc h1');
      return { reveal: h.classList.contains('reveal'), s: parseFloat(getComputedStyle(h).transitionDuration) }; })()`);
  check("a document page's first screen fades in on opening, slowly (0.6s, not the quick .35s tried)",
        fading.reveal && fading.s >= 0.55, JSON.stringify(fading));
  const arrived = await until(HIDDEN_ABOVE_LINE, (n) => n === 0);
  check("...and has all arrived a moment later", arrived === 0, arrived + " block(s) on the first screen still hidden");
  check("...while the blocks below it wait to fade in as they are scrolled to",
        await js("document.querySelectorAll('.doc .wrap > .reveal:not(.in-view)').length") > 5);
  await js("window.scrollBy(0, innerHeight * 0.6)");
  const midway = await until(`[...document.querySelectorAll('.doc .wrap > .reveal.in-view')].filter((e) => {
      const o = parseFloat(getComputedStyle(e).opacity); return o > 0.02 && o < 0.98; }).length`, (n) => n > 0, 1500);
  check("...gradually: just after a scroll, the blocks it brought are seen on their way in", midway > 0,
        midway + " block(s) part-way");
  await go("/how-its-built.html");
  await page("Emulation.setEmulatedMedia", { media: "print", features: [{ name: "prefers-reduced-motion", value: "no-preference" }] });
  const hiddenInPrint = await js(`[...document.querySelectorAll('.doc .wrap > *')]
      .filter((e) => parseFloat(getComputedStyle(e).opacity) < 0.99).length`);
  check("printed, a document page hides nothing", hiddenInPrint === 0, hiddenInPrint + " block(s) hidden in print");
  await viewport(1366, 900, false, "light");
  await go("/how-its-built.html");
  await click(".doc h2#contents + ul li:nth-child(4) a");
  await sleep(60);
  check("a Contents link lands on text already shown, not fading in",
        await js(HIDDEN_ON_SCREEN) === 0, await js(HIDDEN_ON_SCREEN) + " block(s) on screen still hidden");
  await go("/testing.html");
  await js("window.scrollTo(0, document.documentElement.scrollHeight)");
  const atEnd = await until(HIDDEN_ON_SCREEN, (n) => n === 0);
  check("at a page's end every block on screen has appeared, a tall table's too",
        atEnd === 0, atEnd + " block(s) on screen still hidden");
  await shot("site-testing-desktop-end");

  // The overview: its parts fade in the same way, a row of cards one card
  // after another -- the owner found the page static (2026-10-24).
  await go("/index.html");
  check("the overview's hero is never hidden", await js("!document.querySelector('.hero h1').closest('.reveal')"));
  const below = await js(`(() => { const cards = [...document.querySelectorAll('.cards .card')]
      .filter((c) => c.getBoundingClientRect().top > innerHeight * 0.92);
    return { n: cards.length, waiting: cards.filter((c) => c.matches('.reveal:not(.in-view)')).length }; })()`);
  check("...its cards below the screen wait to fade in", below.n >= 6 && below.waiting === below.n, JSON.stringify(below));
  await js("document.getElementById('features').scrollIntoView()");
  // The delay the browser applies, not the property set for it: a
  // transition shorthand on .card once reset it to nothing, while the
  // property still said otherwise. Read in the moment the row has arrived
  // and before its cards are let go of.
  const row = await until(`(() => { const cards = [...document.querySelectorAll('.cards .card')].slice(0, 3);
      return { ready: cards.every((c) => c.classList.contains('in-view')),
               delays: cards.map((c) => getComputedStyle(c).transitionDelay.split(',')[0].trim()) }; })()`,
    (v) => v.ready, 4000);
  check("...and a row of them arrives one card after another", row.ready && new Set(row.delays).size === 3,
        JSON.stringify(row));
  const lifted = await until(`(() => { const c = document.querySelector('.cards .card');
      return { settled: !c.classList.contains('reveal'), delay: getComputedStyle(c).transitionDelay }; })()`,
    (v) => v.settled);
  check("...then each is let go of, so its lift under the pointer is not delayed", lifted.settled
        && lifted.delay.split(",").every((d) => parseFloat(d) === 0), JSON.stringify(lifted));

  // ---------------- Every picture in the page's theme ----------------
  // The owner's rule (2026-10-24): a dark page shows the apps dark, a light
  // one light, and the switch changes them with it. A picture with no
  // theme of its own counts as wrong.
  const WRONG_THEME = `(() => {
      const set = document.documentElement.getAttribute('data-theme');
      const dark = set ? set === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
      const imgs = [...document.querySelectorAll('main img')];
      const wrong = imgs.filter((i) => {
        const shown = i.getClientRects().length > 0;
        if (i.classList.contains('for-dark')) return shown !== dark;
        if (i.classList.contains('for-light')) return shown === dark;
        return true;
      });
      return { dark, n: imgs.length, wrong: wrong.map((i) => i.getAttribute('src')) };
    })()`;
  for (const scheme of ["dark", "light"]) {
    await viewport(1366, 900, false, scheme, "reduce");
    for (const p of ["index.html", "android.html", "in-my-words.html"]) {
      await go("/" + p);
      await js("document.documentElement.removeAttribute('data-theme')");
      const seen = await js(WRONG_THEME);
      check(`${p}, ${scheme}: every picture is shown in the page's theme`, seen.n > 0 && seen.wrong.length === 0,
            JSON.stringify(seen));
    }
  }
  await go("/index.html");
  await js("document.documentElement.removeAttribute('data-theme')");
  await click("#theme-toggle");
  const switched = await js(WRONG_THEME);
  check("the theme switch changes the pictures with the page", switched.dark && switched.wrong.length === 0,
        JSON.stringify(switched));
  await click("#theme-toggle");
  // The switch remembers its choice in this browser; forgotten again, so
  // the pages after this follow the system's setting the walk emulates.
  await js("localStorage.removeItem('noteorganizer-site-theme')");

  // ---------------- A picture opened large ----------------
  for (const scheme of ["light", "dark"]) {
    await viewport(1366, 900, false, scheme, "reduce");
    await go("/index.html");
    await js("document.documentElement.removeAttribute('data-theme')");
    await click(".card a.zoom");
    const opened = await js(`(() => { const d = document.querySelector('dialog.lightbox');
        return d && { open: d.open, src: d.querySelector('img').getAttribute('src') }; })()`);
    check(`${scheme}: a card's picture opens large over the page, in the page's theme`,
          opened && opened.open && opened.src.endsWith(`-${scheme}.webp`), JSON.stringify(opened));
    if (scheme === "light") await shot("site-index-picture-open");
    await page("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
    await page("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
    await sleep(150);
    check(`${scheme}: ...and Escape closes it`, await js("!document.querySelector('dialog.lightbox').open"));
    // The hero's window too: the whole app made small, where the large
    // picture helps most (the owner, 2026-10-24).
    await click(".hero a.zoom");
    const hero = await js("document.querySelector('dialog.lightbox img').getAttribute('src')");
    check(`${scheme}: the hero's window opens large too, in the page's theme`,
          await js("document.querySelector('dialog.lightbox').open")
          && hero.endsWith(scheme === "dark" ? "main-window.webp" : "main-window-light.webp"), hero);
    await js("document.querySelector('dialog.lightbox').close()");
  }
  await go("/android.html");
  await click(".phone-gallery a.zoom");
  check("the Android page's pictures open large too, in the page's theme",
        await js("document.querySelector('dialog.lightbox').open && /-dark\\.webp$/.test(document.querySelector('dialog.lightbox img').getAttribute('src'))"));

  // ---------------- Text as wide as the pictures ----------------
  // The owner's choice (2026-10-24): one right edge for words and pictures
  // alike, on every page -- not a narrower measure for the words.
  await viewport(1366, 900, false, "light", "reduce");
  await go("/index.html");
  const rows = await js(`[...document.querySelectorAll('main section')].map((s) => {
      const p = s.querySelector('.section-head p');
      const row = s.querySelector('.cards, .phones, .figures');
      if (!p || !row || s.querySelector('.split')) return null;
      return { id: s.getAttribute('aria-labelledby'), p: Math.round(p.getBoundingClientRect().right),
               row: Math.round(row.getBoundingClientRect().right) };
    }).filter(Boolean)`);
  check("the overview: each section's words reach as far as its row of pictures",
        rows.length >= 3 && rows.every((r) => Math.abs(r.p - r.row) <= 2), JSON.stringify(rows));
  const split = await js(`(() => { const w = document.querySelector('.split'); const cs = getComputedStyle(w);
      const right = w.getBoundingClientRect().right - parseFloat(cs.paddingRight);
      const left = w.getBoundingClientRect().left + parseFloat(cs.paddingLeft);
      return { figure: Math.round(right - w.querySelector('figure').getBoundingClientRect().right),
               words: Math.round(w.querySelector('.section-head').getBoundingClientRect().left - left) }; })()`);
  check("...and the themes section fills its row, the words beside the picture",
        Math.abs(split.figure) <= 2 && Math.abs(split.words) <= 2, JSON.stringify(split));
  for (const p of ["in-my-words.html", "how-its-built.html", "testing.html", "android.html", "bug-reports.html"]) {
    await go("/" + p);
    const narrow = await js(`(() => { const w = document.querySelector('.doc .wrap'); const cs = getComputedStyle(w);
        const full = w.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
        return [...w.querySelectorAll(':scope > p:not(.source-note):not(.page-actions)')]
          .filter((e) => e.getBoundingClientRect().width < full - 2).length; })()`);
    check(`${p}: every paragraph runs the column's full width`, narrow === 0, narrow + " narrower");
  }
  await go("/in-my-words.html");
  const pair = await js(`(() => { const p = document.querySelector('.doc .pair'); const t = document.querySelector('.doc .wrap > p');
      return p && Math.round(p.getBoundingClientRect().width - t.getBoundingClientRect().width); })()`);
  check("In my words: the words are as wide as the pictures set side by side", pair === 0, String(pair));

  // ---------------- The site's own privacy notice ----------------
  // The apps' privacy policy does not cover this site, so every footer
  // leads to the site's own notice, and it says what its host sees.
  for (const p of ["index.html", "how-its-built.html"]) {
    await go("/" + p);
    check(`${p}: the footer leads to the site's own privacy notice`,
      await js("!!document.querySelector(\".site-footer a[href='site-privacy.html']\")"));
  }
  await go("/site-privacy.html");
  const notice = await js("document.querySelector('main').textContent");
  check("the site's notice names its host, what it sees, and how to object",
    notice.includes("Netlify") && notice.includes("IP address") && notice.includes("object"));
  await noHorizontalScroll("site-privacy.html");

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
  await go(fileUrl("index.html"));
  await follow("a.btn-primary[href='android-demo/index.html']");
  check("from the folder, the Android demo opens too, the desktop demo's rules loaded beside it",
    (await js("document.querySelectorAll('.card').length")) > 0 && await js("!!window.NO_DEMO && !window.NO_DEMO.state()"),
    await js("location.href"));

  // ---------------- The demo, desktop ----------------
  await viewport(1366, 860, false, "dark");
  await go("/demo/");
  await js("localStorage.clear()");
  await go("/demo/");
  await shot("demo-desktop-welcome");
  check("demo opens on the welcome note", (await js("document.getElementById('ed-title').value")).startsWith("Welcome"));
  // Where each heading's first word starts: the icons are from the emoji
  // block, drawn full width by the emoji font (demo.css, "Emoji block").
  // 🗂 asks for its plain form, and the browser drew it narrow.
  const starts = await js(`[...document.querySelectorAll('#ed-body div > b')]
    .filter((b) => /^\\p{Extended_Pictographic}/u.test(b.textContent))
    .map((b) => { const t = b.firstChild, at = t.textContent.indexOf(" ") + 1, r = document.createRange();
      r.setStart(t, at); r.setEnd(t, at + 1); return Math.round(r.getBoundingClientRect().left); })`);
  check("the welcome note's five headings start their words in one column",
    starts.length === 5 && Math.max(...starts) - Math.min(...starts) <= 1, JSON.stringify(starts));
  check("nine sample notes", (await js("document.querySelectorAll('.note-card').length")) === 9);

  await js("[...document.querySelectorAll('.nc-open')].find(b => b.textContent.includes('Weekly meal plan')).click()");
  await sleep(200);
  await shot("demo-desktop-table-note");
  const deskSaid = await js(arrowsSaid);
  check("desktop demo, a note open: no link or button says a drawn arrow", deskSaid.length === 0, JSON.stringify(deskSaid));
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
      ["Default font", ...(await js("NO_APP.fontFamilies"))].join("|"));
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
  check("the demo's About leads to the site's privacy notice, where its storage is explained",
    await js("!!document.querySelector(\".set-panel.about a[href='../site-privacy.html']\")"));
  await click("#set-back");
  await js("[...document.querySelectorAll('.nc-open')].find(b => b.textContent.includes('Team stand-up')).click()");
  await sleep(250);
  await shot("demo-phone-repeat-full", true);
  await click("#import-code").catch(() => {});

  // ---------------- The Android demo ----------------
  // Its own screens over the desktop demo's rules (window.NO_DEMO), its
  // own notebook -- and share codes that cross between the two, as
  // between the apps.
  const cardWith = (words) => `[...document.querySelectorAll('.card')].find(c => c.textContent.includes(${JSON.stringify(words)}))`;
  await viewport(390, 844, true, "light");
  await go("/android-demo/index.html");
  await js("localStorage.removeItem('noteorganizer-android-demo-v1')");
  await go("/android-demo/index.html");
  await noHorizontalScroll("android demo list");
  await shot("android-phone-list");
  check("the Android demo opens on its own sample notebook, five notes",
    await js("document.querySelectorAll('.card').length") === 5, String(await js("document.querySelectorAll('.card').length")));
  check("...with no name set, the list is headed with the app's name",
    await js("document.querySelector('.greeting').textContent") === "Note Organizer");
  const listSaid = await js(arrowsSaid);
  check("android demo list: no link or button says a drawn arrow", listSaid.length === 0, JSON.stringify(listSaid));
  check("a card's preview leaves its table out, as the phone's does, and badges it",
    await js(`(() => { const c = ${cardWith("September expenses")}; const p = c.querySelector('.c-preview');
      return (!p || !p.textContent.includes('1500')) && c.textContent.includes('1 table'); })()`));
  check("...and it leaves the desktop demo's notebook alone",
    await js("JSON.parse(localStorage.getItem('noteorganizer-demo-v1') || '{\"notes\":[]}').notes.some(n => n.title === 'Shopping list')"));
  await typeInto("#search", "boat");
  check("search narrows the cards to the one that says it, an untitled note by its first line",
    await js("document.querySelectorAll('.card').length") === 1 && await js(`!!${cardWith("boat trip")}`));
  await js("const s = document.getElementById('search'); s.value = ''; s.dispatchEvent(new Event('input'))");
  await js(`${cardWith("Home-made bread")}.click()`);
  await sleep(200);
  await noHorizontalScroll("android demo note");
  await shot("android-phone-note");
  check("a note opens on the whole screen, its checklist below it and the format bar under it",
    await js("document.getElementById('ed-title').value") === "Home-made bread"
    && await js("document.querySelectorAll('.cl-row').length") === 3
    && await js("!!document.getElementById('fmt') && document.getElementById('navbar').hidden"));
  const noteSaid = await js(arrowsSaid);
  check("android demo note: no link or button says a drawn arrow", noteSaid.length === 0, JSON.stringify(noteSaid));
  check("its date reads day first, as the app shows it, not in the browser's own order",
    /\d{2}\.\d{2}\.\d{4}/.test(await js("document.querySelector('.date-chip').textContent")),
    await js("document.querySelector('.date-chip').textContent"));
  await js("document.getElementById('ed-title').focus(); document.getElementById('ed-title').setSelectionRange(99, 99)");
  await page("Input.insertText", { text: " for Sunday" });
  await sleep(1100);
  check("typing saves itself, and says so", await js("document.getElementById('ed-status').textContent") === "Auto-saved");
  await js("[...document.querySelectorAll('.ed-top .icon-btn')].find(b => b.getAttribute('aria-label') === 'More').click()");
  await sleep(150);
  await js("[...document.querySelectorAll('.menu-item')].find(b => b.textContent.includes('Add comments')).click()");
  await sleep(150);
  check("⋮ adds comments under the note", await js("!!document.getElementById('ed-comments')"));
  await go("/android-demo/index.html");
  check("after a reload the note is open again, its title as typed",
    await js("document.getElementById('ed-title') && document.getElementById('ed-title').value") === "Home-made bread for Sunday");
  await js("[...document.querySelectorAll('.ed-top .icon-btn')].find(b => b.getAttribute('aria-label') === 'Share').click()");
  await sleep(150);
  await js("[...document.querySelectorAll('.sheet .btn')].find(b => b.textContent === 'Make a share code').click()");
  await sleep(400);
  const breadCode = await js("(document.querySelector('.sheet .code-area') || {}).value || ''");
  const breadBack = await js(`__demo.decodeShareCode(${JSON.stringify(breadCode)}).then(n => ({ title: n[0].title, items: n[0].checklist.length }), e => ({ error: e.message }))`);
  check("Share makes a share code that reads back", breadBack.title === "Home-made bread for Sunday" && breadBack.items === 3,
    JSON.stringify(breadBack));
  await js("document.querySelector('.scrim').click()");
  await js("[...document.querySelectorAll('.ed-top .icon-btn')].find(b => b.getAttribute('aria-label') === 'Back to the notes').click()");
  await sleep(150);
  check("Back returns to the list and its bar", await js("!document.getElementById('navbar').hidden && document.querySelectorAll('.card').length === 5"));
  await click("#navbar [data-tab=calendar]");
  await noHorizontalScroll("android demo calendar");
  await shot("android-phone-calendar");
  check("the calendar marks the days a repeating note falls on", await js("document.querySelectorAll('.cal-dots span').length") >= 4,
    String(await js("document.querySelectorAll('.cal-dots span').length")));
  await click("#navbar [data-tab=settings]");
  await js("[...document.querySelectorAll('.set-row')].find(b => b.textContent.includes('Appearance')).click()");
  await js("[...document.querySelectorAll('.seg button')].find(b => b.textContent === 'Dark').click()");
  await sleep(150);
  await shot("android-phone-appearance-dark");
  check("Light | Dark switches the whole app to the dark side of its theme",
    await js("NO_APP.darkThemes.includes(__android.state().theme) && document.documentElement.style.colorScheme === 'dark'"));
  // Codes both ways: the desktop demo's into this one, and this one's into the desktop demo.
  const standupCode = codes["Team stand-up"];
  await js("document.querySelector('.page-title .icon-btn').click()");
  await js("[...document.querySelectorAll('.set-row')].find(b => b.textContent.includes('Import')).click()");
  await js(`document.querySelector('.code-area').value = ${JSON.stringify(standupCode)}`);
  await js("[...document.querySelectorAll('.btn')].find(b => b.textContent === 'Import').click()");
  await sleep(500);
  const imported = await js("(() => { const n = __android.state().notes.find(x => x.title === 'Team stand-up'); return n ? { freq: n.recurrence.freq, days: n.recurrence.weekdays } : null; })()");
  check("a share code from the desktop demo opens in the Android demo, its repeat with it",
    imported && imported.freq === "weekly" && JSON.stringify(imported.days) === "[0]", JSON.stringify(imported));
  const androidCodes = await js(`(async () => {
    const out = {};
    for (const n of __android.state().notes) if (n.title !== 'Team stand-up') out[n.title] = await __demo.encodeShareCode([n]);
    return out;
  })()`);
  const allCodes = Object.assign(JSON.parse(fs.readFileSync(path.join(OUT, "share_codes_from_demo.json"), "utf8")), androidCodes);
  fs.writeFileSync(path.join(OUT, "share_codes_from_demo.json"), JSON.stringify(allCodes, null, 1));
  check("...and the Android demo's own notes make codes for the app's reader", Object.keys(androidCodes).length === 5,
    Object.keys(androidCodes).join(", "));
  await js("[...document.querySelectorAll('#navbar [data-tab]')].find(b => b.dataset.tab === 'settings').click()");
  await js("[...document.querySelectorAll('.set-row')].find(b => b.textContent.includes('About')).click()");
  check("the Android demo's About leads to the site's privacy notice",
    await js("!!document.querySelector(\".about a[href='../site-privacy.html']\")"));
  await viewport(1366, 900, false, "light");
  await go("/demo/");
  const crossed = await js(`(async () => {
    __demo.importShared(await __demo.decodeShareCode(${JSON.stringify(breadCode)}));
    const n = __demo.state().notes.find(x => x.title === 'Home-made bread for Sunday');
    return n ? n.checklist.length : -1;
  })()`);
  check("a share code from the Android demo opens in the desktop demo, its checklist with it", crossed === 3, String(crossed));
  await go("/android-demo/index.html");
  await noHorizontalScroll("android demo on a computer");
  await shot("android-desktop");
  check("on a computer the Android demo is drawn as a phone, with a word beside it",
    await js("document.getElementById('phone').getBoundingClientRect().width") < 440
    && await js("getComputedStyle(document.querySelector('.beside')).display !== 'none'"));
  // Photographed with motion reduced, as the document pages are: the fade
  // caught the page's last block half-way in.
  await viewport(1366, 900, false, "light", "reduce");
  await go("/android.html");
  await shot("site-android-desktop-light", true);
  // Seven screens, each dark and light and captioned in both: four
  // upright in one row, then three on its side, a row each -- four and then
  // two upright looked unplaced (the owner, 2026-10-24).
  check("the Android page shows seven screens, each in both themes and captioned in both",
    await js("document.querySelectorAll('.phone-gallery .phone-shot').length") === 7
    && await js("[...document.querySelectorAll('.phone-gallery .phone-shot')].every(f => f.querySelector('img.for-dark') && f.querySelector('img.for-light'))")
    && await js("[...document.querySelectorAll('.phone-gallery figcaption span')].every(s => s.textContent.trim().length > 20)"));
  const galleryRows = await js(`(() => { const tops = [...document.querySelectorAll('.phone-gallery .phone-shot')]
      .map((f) => Math.round(f.getBoundingClientRect().top));
    const rows = []; tops.forEach((t) => { if (!rows.length || rows[rows.length - 1][0] !== t) rows.push([t, 0]); rows[rows.length - 1][1]++; });
    return rows.map((r) => r[1]); })()`);
  check("...four upright on one row, then each one on its side on a row of its own",
    JSON.stringify(galleryRows) === "[4,1,1,1]", JSON.stringify(galleryRows));
} catch (err) {
  problems.push("the walk stopped: " + err.message);
} finally {
  // Edge is a tree of processes. edge.kill() ended only the one started
  // here; the rest ran on, holding the profile, so removing it failed in
  // silence and every run left about ten headless Edge processes behind
  // (thirty were found from three runs). Browser.close shuts the browser
  // down, taskkill /T takes what is left of the tree, and a profile that
  // still cannot be removed fails the walk instead of passing quietly.
  await Promise.race([send("Browser.close").catch(() => {}), sleep(3000)]);
  ws.close();
  spawnSync("taskkill", ["/PID", String(edge.pid), "/T", "/F"], { stdio: "ignore" });
  server.close();
  let removed = false;
  for (let i = 0; i < 20 && !removed; i++) {
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* still held */ }
    removed = !fs.existsSync(profile);
    if (!removed) await sleep(250);
  }
  if (!removed) problems.push("Edge outlived the walk: its profile could not be removed, " + profile);
}

for (const r of results) console.log((r.ok ? "ok   " : "FAIL ") + r.name + (r.ok || !r.detail ? "" : "  -- " + r.detail));
for (const p of problems) console.log("FAIL " + p);
const failed = results.filter((r) => !r.ok).length + problems.length;
console.log(`\n${results.length - results.filter((r) => !r.ok).length}/${results.length} checks passed, ${problems.length} browser problem(s). Photographs in ${OUT}`);
process.exit(failed ? 1 : 0);
