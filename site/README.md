# Note Organizer — the website

A small website for Note Organizer: a page that presents the app, a web demo
anyone can try in a browser (computer or phone), and the project's key
documents as pages of their own. It is a static site, ready for Netlify.

**The demo is a re-creation.** The real app is a Windows program in Python and
Tkinter, which a browser cannot run. The demo imitates its interface in HTML
and JavaScript, says so on every screen, and keeps what a visitor types in
that visitor's own browser.

The site lives in the app's repository, in this `site/` folder, so it has a
history and builds from the same commit as the app it presents. The commands
below are run from the repository's root. The test suite does not run for a
change that only touches `site/`.

## What is in this folder

| Path | What it is |
|---|---|
| `public/` | **The finished site — this is what goes to Netlify.** Never edit it by hand: the build replaces it. Not in git: the build makes it again whenever it is needed. |
| `src/` | The source: the overview page, the page template, the site's privacy notice, the styles, the demo, the Netlify headers. |
| `build.py` | Turns `src/` plus the app's repository into `public/`. |
| `site.json` | Two settings: the site's address and, later, the repository's address. |
| `tools/check_demo.mjs` | Walks the built site in a real browser (Edge), on a computer and on a phone, and photographs it. |
| `tools/verify_share_codes.py` | Holds the demo's share codes to the app's own code, both ways. |
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
It builds in `public.building/` first and only swaps that into `public/`
once every check has passed, so it stops, and leaves the old site alone, if
a link is broken, a value is missing, a page would contain something
private such as a home-folder path or a private account or folder name (the strings listed in
`FORBIDDEN`) — or if Windows
will not let go of `public/` because an Explorer window or a browser tab
has it open (close it and run the build again).

Netlify counts every deploy against the account's monthly credits, so
gather changes and upload them together rather than one at a time.

## Check it before uploading

```
py site/tools/verify_share_codes.py <photos folder>
node site/tools/check_demo.mjs <photos folder>
py site/tools/verify_share_codes.py <photos folder>
```

The browser walk serves `public/` with the same security headers Netlify will
send, presses what a visitor presses (opening notes, ticking a checklist,
searching, writing a new note, reloading, deleting and restoring, the
calendar, the themes, the phone layout) and fails on any error. It saves
photographs in the folder you name: look at them, the phone ones especially.

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
site whose address appears in the app's sources or in `docs/PRIVACY.md`;
the Android app, in its own repository, is held to the same by review.

So the apps' privacy policy is not one of the site's pages, and does not
cover it. The site has its own short notice, `src/site-privacy.html`:
who runs it, what Netlify sees and why, the transfer to the United
States, what the browser keeps, and how to object or complain. Every
page's footer links it, and so does the demo's About; the browser walk
checks both, and that the notice says those things. The site has no form
either — feedback is a review in the stores — and `_headers` says so
(`form-action 'none'`); the build refuses a page with a `<form>` in it.

## When the repository becomes public

Put its address in `site.json` (`"repo_url": "https://github.com/..."`) and
rebuild: every mention of a document that is not published on the site
becomes a link to it on GitHub.

## Linking to it from somewhere else

Link to the site's address, or straight to the demo (`/demo/`). The headers do
not forbid showing a page inside another site's frame, so another page you
own can embed the demo too.
