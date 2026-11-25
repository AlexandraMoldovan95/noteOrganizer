# Note Organizer — the website

A small website for Note Organizer, for Windows and for Android: a page that
presents both apps, a page for the Android app, a web demo of each that anyone
can try in a browser (computer or phone), and the project's key documents as
pages of their own. It is a static site, ready for Netlify.

**The demos are re-creations.** The real apps are a Windows program in Python
and Tkinter and a native Android app in Kotlin, which a browser cannot run.
Each demo imitates its app's interface in HTML and JavaScript, says so on
every screen, and keeps what a visitor types in that visitor's own browser.
The Android demo draws its own screens over the desktop demo's rules: it
loads `demo/demo.js`, which starts its own screens only on its own page and
lends the rest (`window.NO_DEMO`) — the palettes, dates and repeats, a
note's body to HTML and back, and share codes in the app's format, so a code
made in one demo opens in the other, as between the apps.

The site lives in the desktop app's repository, in this `site/` folder, so it
has a history and builds from the same commit as the app it presents. The
Android app keeps its own repository; the build reads it, beside this one,
for its screenshots, the description in its README and its version, and
never writes to it. The commands below are run from the repository's root.
The test suite does not run for a change that only touches `site/`.

## What is in this folder

| Path | What it is |
|---|---|
| `public/` | **The finished site — this is what goes to Netlify.** Never edit it by hand: the build replaces it. Not in git: the build makes it again whenever it is needed. |
| `src/` | The source: the overview page, the page template, the site's privacy notice, the styles, the desktop demo (`demo/`), the Android demo (`android-demo/`), the Netlify headers. |
| `build.py` | Turns `src/` plus the two apps' repositories into `public/`. The Android page is made here, from the Android repository's README and screenshots. |
| `site.json` | The site's address; where the Android repository is (`android_repo`, beside this one by default); each repository's public address (`repo_url`, `android_repo_url`); and the portfolio's (`portfolio_url`), which every page's header links in its top right corner, first in the menu on a phone. |
| `tools/check_demo.mjs` | Walks the built site in a real browser (Edge), both demos included, on a computer and on a phone, and photographs it. |
| `tools/check_demo.py` | The walk's door: it starts `check_demo.mjs`, which will not start any other way, with the computer's turn, a memory ceiling and a time limit, and ends every Edge process with it. |
| `tools/verify_share_codes.py` | Holds both demos' share codes to the app's own code, both ways. |
| `netlify.toml` | Only for a deploy connected to Git, later (with `site` as the base directory). A drag-and-drop deploy ignores it. |

## Put it online the first time

1. Sign in at [app.netlify.com](https://app.netlify.com).
2. On the Projects page, open **Add new project → Deploy manually**.
3. Drag the **`site/public`** folder (not `site` itself) onto the drop zone.
4. Netlify gives the site a random address. Change it in the project's
   configuration by renaming the project — the name becomes the address,
   for example `note-organizer-demo` → `note-organizer-demo.netlify.app`.

Then, so that a link shared on a social site shows a picture and a title:

5. Put the address in `site.json`:
   `"site_url": "https://note-organizer-demo.netlify.app"`
6. Rebuild (`py site/build.py`) and drag `site/public` again (next section).

## Update it

When the app changes — a new version, new screenshots, edited documents — or
when you edit something in `src/`:

```
py site/build.py
```

Then on Netlify open the project's **Deploys** page and drag `site/public`
onto the drop zone at the bottom. The address stays the same.

The build reads the repository it sits in (or the folder given with
`--repo`) and only reads it: the documents, the screenshots, the
icon, the test plan's case count, and a few values from the source code (the
themes, the emoji, the version), read as text — none of the app's code runs.
A few figures are read out of sentences, so those sentences keep their
words: "About N checks" in `docs/AI_WORKFLOW.md`, the mutant count from
`tools/mutants.json`, and from the Android repository its version in
`app/build.gradle.kts` and, in its `qa/README.md`, "N tests across …
suites" and "N parts and about N checks".
It builds in `public.building/` first and only swaps that into `public/`
once every check has passed, so it stops, and leaves the old site alone, if
a link is broken, a value is missing, a page would contain something
private such as a home-folder path or a private account or folder name (`FORBIDDEN`, and
`PRIVATE_WORDS`, kept as hashes so the guard does not spell them out), if its Markdown renderer
draws one of the cases in `RENDER_CASES` otherwise than GitHub does
([why](../docs/ISSUES_LOG.md#a-year-read-as-a-list-number)) — or if Windows
will not let go of `public/` because an Explorer window or a browser tab
has it open (close it and run the build again).

Netlify counts every deploy against the account's monthly credits, so
gather changes and upload them together rather than one at a time.

## Check it before uploading

```
py site/tools/verify_share_codes.py <photos folder>
py site/tools/check_demo.py <photos folder>
py site/tools/verify_share_codes.py <photos folder>
```

The walk starts only through its door, `check_demo.py`. Headless Edge is a
tree of processes, and a walk stopped midway once left about ten of them
running; the door takes the computer's turn (one heavy job at a time, see
[qa/README](../qa/README.md#a-test-run-is-a-guest-on-the-computer-it-runs-on)),
holds Edge's whole tree in its job object, gives the walk 15 minutes, and
ends whatever is left when the walk ends, however it ends.

The browser walk serves `public/` with the same security headers Netlify will
send, presses what a visitor presses (opening notes, ticking a checklist,
searching, writing a new note, reloading, deleting and restoring, the
calendar, the themes, the phone layout) and fails on any error. It saves
photographs in the folder you name: look at them, the phone ones especially.
The document pages are photographed with motion reduced and scrolled through
first, so a full-length picture holds the whole page and its pictures; the
fade their blocks scroll in with has checks of its own, with motion on
([why](../docs/ISSUES_LOG.md#photographs-of-the-sites-pages-blank-below-the-first-screen)).

Three choices of the owner's (2026-10-24) are held by checks too, because
each was undone once by a review that meant well:

- **The fade is slow and gradual**: 0.6 seconds, a block arriving once
  its top passes the screen's lowest twelfth, a row of cards one after
  another. A quicker fade read as no animation at all.
- **Words run as wide as the pictures** on every page, one right edge
  for both, not a narrower reading measure.
- **Every picture of an app is shown in the page's theme**, dark on a
  dark page and light on a light one, switching with it; the build
  refuses a page with a picture in one theme only. A click opens a
  picture large over the page.

The share-code check copies the app's package to a temporary folder and runs
the app's own reader on every code the demo made, and the demo's reader on
codes the app made (its welcome note, a table, colours). The first run writes
the app's codes, the second reads the demo's.

## Kept apart from the apps

The site presents the project to the people the owner sends here — once
the apps are published, its overview links to their store pages. The
other way round, nothing the apps' users see points at it: not the apps,
not their store pages (whose optional website field stays empty), not
their privacy policy (the owner's rule, 2026-10-21). The build refuses a
site whose address appears in either app's sources, in
`docs/PRIVACY.md` or in the Store's listing, `docs/STORE_LISTING.md`.

So the apps' privacy policy is not one of the site's pages, and does not
cover it. The site has its own short notice, `src/site-privacy.html`:
who runs it, what Netlify sees and why, the transfer to the United
States, what the browser keeps, and how to object or complain. Every
page's footer links it, and so does the demo's About; the browser walk
checks both, and that the notice says those things. The site has no form
either — feedback is a review in the stores — and `_headers` says so
(`form-action 'none'`); the build refuses a page with a `<form>` in it.

## When a repository becomes public

Put its address in `site.json` and rebuild. For the desktop app's,
`"repo_url": "https://github.com/..."`: every mention of a document that is
not published on the site becomes a link to it on GitHub. For the Android
app's, `"android_repo_url"`: the Android page names it as a link, and its
mentions of the phone's documents become links too. Until then the pages say
that each app has a repository of its own, and link neither: a link to a
private repository shows a visitor GitHub's "not found" page.

## Linking to it from somewhere else

Link to the site's address, or straight to the demo (`/demo/`). The headers do
not forbid showing a page inside another site's frame, so another page you
own can embed the demo too.
