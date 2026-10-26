# Roadmap

What's planned, what was decided against, what already shipped and settled, how versions are
counted, and the standing constraints. Nothing here is a promise or a deadline — this is a working
list for a project developed in spare time by a small team of two.

- [Under consideration](#under-consideration)
- [Explicitly not planned right now](#explicitly-not-planned-right-now)
- [Shipped & settled](#shipped--settled)
- [Versioning](#versioning)
- [Known limitations](#known-limitations)

The outside view of the app — what a hostile product review found and what is
being done about it — lives in its own register, now archived:
[`docs/archive/PRODUCT_FINDINGS.md`](archive/PRODUCT_FINDINGS.md).

## Under consideration

Genuinely open ideas, roughly ordered by how soon they're likely to happen.

- **The website, its demo, and where the app is published.** The site — a page presenting the
  app, a web demo that re-creates its interface in a browser, and the key documents as pages —
  lives in this repository under [`site/`](../site/README.md) since 2026-10-14. It is built from
  this repository and published on Netlify by hand, with changes gathered into one upload because
  every deploy counts against the account's credits. What is planned for it, nearest first:
  - **The demo closer to the app.** Its formatting bar has the app's font and size lists and its
    indent buttons since 2026-10-14, taken from the app's own source and carried in share codes
    both ways. It stays as it is now (the owner's call, 2026-10-14): the calculator under a note,
    and opening or moving one day of a repeating series, remain among the things the demo names
    as the desktop app's alone.
  - **One site for both apps** — done on 2026-10-24, the owner's call: the overview presents the
    Android app beside the desktop one, an Android page is built from that repository's README
    and screenshots, and an Android demo draws the phone's screens over the desktop demo's rules,
    so a share code crosses between the two demos as between the apps. Its code stays in its own
    repository, which the site's build reads the way it reads this one — no third repository for
    the site. Each repository is named as a link once it is public (`site/site.json`).
  - **At the public launch, links to the stores** — the Microsoft Store for the desktop app,
    Google Play for Android — rather than the built `dist/` folder to download. A store signs the
    app (an unsigned `.exe` from a website meets Windows' unknown-publisher warning), keeps it up
    to date, and is where people look for it. The Windows options are in
    [`docs/RELEASE_WINDOWS.md`](RELEASE_WINDOWS.md).

- **Feedback from real readers at the public launch, colour-blind readers among them.** The
  colour-blind check so far is an AI simulation: photographs of the app simulated for
  protanopia, deuteranopia and tritanopia, read by AI reviewers (the test plan's case 625). A
  person with red-green colour blindness telling Save from Delete is the check still owed (the
  owner's call, 2026-10-14).

- **Small candidates from the 2026-08-31 idea pass** (put aside deliberately, in rough order of
  appeal; two candidates from that pass have since shipped — see
  [Global keyboard shortcuts](#global-keyboard-shortcuts) and, for the delete-toast Undo,
  [CHANGELOG](../CHANGELOG.md)):
  - **Rebuild only the table block an edit touched** — `_render_table_grids` deliberately tears
    down and rebuilds every grid in the note ("a grid is cheap to make, and tracking which of them
    an arbitrary edit invalidated is not"). The 2026-09-02 senior audit measured ~130ms for a
    10-table note per rebuild, run on commits/pastes/menu ops, never on keystrokes. Re-measured
    on 2026-10-14, after the one-pass draw and width cache of 2026-10-01: **7 ms for 1 table, 34 ms
    for 10, 65 ms for 30, 254 ms for 100** in one note. The cost depends on the tables in the
    open note, never on how many notes the notebook holds. It is also the root of the
    view-restore timer complexity (the explicit/ambient contract exists because rebuilt windows
    map late), though an analysis that day doubts the work would remove it: a rebuilt block is
    still a new window that maps late. **Decided 2026-10-14, the owner's question answered with
    measurements and four reviewing agents: not needed now.** Worth doing if a real note of 30+
    tables lags past ~100 ms, if another bug lands in the view-restore class, or if opening very
    long notes needs tables drawn as they come into view. The one small step that came first is
    done (2026-10-15): each cell of a table being drawn asked every grid already drawn whether it
    started on that line — 59,600 such questions for 100 tables, quadratic — when during a build
    the answer is always no. Now 2 per table; drawing 100 tables went from 236 ms to 140 ms, 30
    from 75 to 53, and 10 tables is unchanged at about 28 ms. What is left grows in a straight
    line with the tables. The rest is an architectural phase with its own design pass, not a
    patch; measured before, it must be measured after.
- **Note list virtualization.** Most of it is done: the main list draws a screenful and the
  rest as the view comes near it, a save redraws one card instead of the list, and the cards are
  drawn on one canvas rather than built from widgets, so a drawn card costs a handful of canvas
  items instead of six windows (see
  ["Large lists: draw what can be seen, the rest on demand"](ARCHITECTURE.md#large-lists-draw-what-can-be-seen-the-rest-on-demand)).
  Since 2026-10-15 a pin, a new category or a move in Custom order also redraws one card.
  What is left is true windowed rendering — recycling one screenful of cards, so that a list
  scrolled to its end does not hold every card it passed. Measured on 2026-10-14
  (`tools/bench.py --rich --deep`), with the list scrolled to its very end, a full rebuild
  (Select mode, Undo, a restore) takes 0.11 s at 1,000 notes, 0.56 s at 5,000 and 1.2 s at
  10,000; at the top of the list it stays under 15 ms at every size. **Decided 2026-10-14: not
  needed now.** Worth it when a real notebook passes about 2,000–3,000 notes, or when a slow
  computer shows a deep rebuild above ~0.3 s at 1,000. It is weeks of work: cards differ in
  height, and placing one without drawing those above it needs every card's height known first.
- **A save that writes one note, not the whole notebook.** Every save, the autosave in a pause
  of typing included, rewrites `notes_data.json` whole (`save_notes`: written beside the file,
  then swapped in). Measured on 2026-10-14 (`tools/bench.py --rich`), one note's automatic save
  takes 22 ms at 1,000 notes, 84 ms at 5,000 and 174 ms at 10,000 — it grows with the notebook,
  not with the note. Under about 100 ms nobody feels it; 174 ms is a hitch in a pause of typing.
  Profiled on 2026-10-15, at 10,000 notes (186 ms): 108 ms turning every note into JSON text,
  45 ms writing the 24.6 MB file, 24 ms finding the saved card's place in the list. Writing the
  file compact saves only a tenth. The way out that keeps the file exactly as it is — so the
  Android exploration, backups and old copies notice nothing — keeps each note's text beside a
  copy of the note, and remakes only the text of notes that compare unequal to their copy:
  90 ms → 21 ms at 10,000 (the comparison of every note costs 8 ms), the same bytes written,
  ~6 MB more memory per 1,000 notes and a one-off ~210 ms at the first save of a session. Next
  after it: the disk write moved off the window's thread (45 ms), and the card's place found
  without sorting every note (24 ms). **Decided 2026-10-15, the owner's call: not now** — weeks of
  care in the riskiest code for a cost nobody has met. The signal to reopen it is a report that
  the app is slow: the bug form asks how many notes the person has, and every crash log names the
  notebook's size, so such a report says at once whether this is the cause.
  `tools/bench.py --rich` re-measures the save at any size.
- **A Share button like the phone's.** The Android app has one Share button in a note — PDF,
  web page, plain text or share code, handed to the phone's share sheet — which replaced its
  "Send by email" on 2026-10-19, because the sheet covers email too. Here the same ground is
  covered in three places: **Generate code** in the editor, **🔗 Share notes** for several notes,
  and right-click → **Export as file** (.html or .txt), a file to attach by hand. Weighed on
  2026-10-23: Windows has a share window of its own (the one Edge and File Explorer open), which
  a desktop app reaches only through Windows' COM interfaces (`IDataTransferManagerInterop`). That
  needs no new dependency, but it is native code that can take the app down where the crash log
  cannot follow, and no script can press anything in the window once it opens. What it offers
  depends on the machine — on many, little beyond Nearby Share and Outlook, and never a webmail
  open in a browser tab — and PDF would not be among the choices
  ([decided against](#explicitly-not-planned-right-now)). The lighter routes weighed with it: a
  Share popup offering Copy text, a file put on the clipboard to paste into a mail or a chat, and
  a `mailto:` link, which carries only the words and cuts a long note short. **Decided
  2026-10-23, the owner's call: not now** — the app does the job as it is. Worth reopening
  together with the toolkit question further down this list, if the desktop ever moves off
  Tkinter.
- **An Android version.** It is built in a repository of its own (`noteOrganizerForAndroid`,
  private), begun on 2026-09-13: a native Android app in Kotlin that reads and writes the same
  notes file as this one. It began as an exploration of whether the data format survives the trip
  and what a touch-sized version costs, and is now on its way to Google Play, after this app's
  Store release. Of the two
  routes once weighed here, it took the first — a full rewrite with a mobile-first toolkit — rather
  than a port of this code onto Kivy or BeeWare, and nothing in this repository is shaped for it
  (CLAUDE.md's project focus).
- **Whether to move off plain Tkinter entirely.** This was to be decided together with the Android
  question, since a cross-platform choice could have meant rewriting the UI layer once for both
  desktop and mobile instead of twice. With Android explored natively in its own repository, the
  two are no longer linked, and the desktop app stays on Tkinter for now. The candidates, kept for
  when the question comes up again:
  - **PyQt / PySide (Qt for Python)** — far more capable widgets out of the box (native rich text
    editing, real tables, more polished look), at the cost of a much steeper learning curve, a
    heavier package, and (for PyQt specifically) a more restrictive license than this project has
    used so far.
  - **CustomTkinter** — a modern-looking skin built on top of Tkinter itself, meaning the bulk of
    the current codebase would still apply; the smallest migration cost of the options here, but
    also the smallest capability jump.
  - **Kivy** — built with touch/mobile in mind, which is why it was weighed for Android before the
    native route was taken; adopted here, it would mean rebuilding the desktop UI too, not just
    extending it.
  - Doing nothing and staying on plain Tkinter remains a legitimate option — noted here so the
    decision is made deliberately, not by default. **The owner's call, 2026-10-14: stay on
    Tkinter.**

## Explicitly not planned right now

- Tags as a separate feature from categories — removed in 0.3.0 after concluding categories cover
  the need on their own; revisiting this isn't currently planned.
- Cloud sync / accounts — the app is intentionally offline-only.
- Importing a `.md`/`.html` file as a note — decided against (2026-09-15). Exporting one is
  enough: it answers "get this note out of here", which is the question people actually ask.
  The reverse direction asks the app to align somebody else's HTML with the editor's own idea of
  a note, and every mismatch — markup the editor has no concept of, a malformed file, a structure
  that arrives looking nothing like what the writer saw — becomes an error we would then have to
  design and defend. A feature whose failure modes are mostly other people's files is a poor
  trade for a return trip nobody has asked for.
- "Export as PDF" — decided against (2026-09-15). The single-note export already writes HTML, and
  turning HTML into a PDF is something the machine already does: open it and print to PDF.
  Wrapping that would add a dependency on Edge's headless flags, a fallback for when they change
  or Edge is missing, and a second export path to keep honest — to save one step of something
  Windows does natively.
- Recognising tables pasted from a PDF — decided against (2026-08-28). A PDF carries no table
  structure at all, only text positioned on a page; guessing columns from spacing is a large,
  unreliable feature of its own. Pasting from a PDF keeps working as it does today — the table's
  *text* arrives through the normal PDF paragraph-rejoin — and anyone who wants it structured can
  drop it into a table made from the toolbar. Tables pasted from Excel, Word or web pages (which
  *do* carry structure) arrive as real grids and stay fully supported.
- A language selector for the interface — decided against (2026-10-03); the app stays in
  English. Counted at the time: about 470 distinct interface texts with no translation layer to
  hold them, some 390 places where the qa suite reads the English wording, and layouts tuned to
  English widths (German runs about 30% longer). The deciding reason was the owner's: nobody
  available to check six or seven languages for correct writing, and badly written translations
  would be worse than none. If it ever returns, the order is a text catalogue first, tested with a
  fake language that stretches every text, and then one real language.
- Routing template deletion through the Trash — decided against (2026-10-09). Deleting a
  template already asks first and says plainly that it skips the Trash and cannot be undone
  (see [Settings redesign](#settings-redesign)). Making templates restorable would put a second
  kind of entry in `trash.json`, which every reader of the Trash would then have to understand —
  restore, the retention purge, Empty trash, the selection, backup and import — and so would
  every older version of the app that opens the file. The warning is the safeguard; a new class
  of Trash bugs is not worth one extra way back.
- Fonts inside table cells — decided against by the owner (2026-10-14). It was the phase
  deliberately deferred in the 0.64.95 cycle, the last follow-up the audit programme had scoped
  out; a table's cells keep the note's own font.
- A visible cue that Settings' section list scrolls — decided against by the owner
  (2026-10-14). In a short window, About sits below the list's foot and is reached with the
  wheel; she judged the list fine as it is.

Three more features were tried and deliberately taken out again — the decision record, since
"we had it and removed it" is a stronger ruling than "we never built it":

- **Quote blocks** — shipped with paragraph formatting (0.34.51), removed at 0.36.54: a heavy
  visual device for something a note rarely needs, and the only paragraph property carrying
  colours of its own. Old notes load cleanly as ordinary paragraphs
  (see the [Changelog](../CHANGELOG.md#03656--2026-08-25)).
- **A Markdown export** — built alongside the HTML and plain-text exports (0.64.95), measured
  against them, and removed before shipping: everything it could say, the HTML says with the
  colours on.
- **Clickable Statistics chips** — the chips highlighted on hover but the click's failure never
  reproduced under test; rather than chase it, the interactivity was removed outright, because
  Statistics is a quick snapshot, not another way to filter notes
  (the investigation: ["The chip that looked clickable"](ISSUES_LOG.md#the-chip-that-looked-clickable-and-the-fix-that-looked-like-it-worked)).

## Shipped & settled

Work that reached `main`, kept here as a decision record — the questions each piece settled, so
they aren't reopened from scratch. The feature-by-feature detail lives in
[CHANGELOG.md](../CHANGELOG.md).

### Spelling (2026-10-14)

Windows' own spell checker, reached with `ctypes` (no new dependency: `comtypes` was not
needed), following the languages installed in Windows — a word right in any of them is right.
The owner's worry decided its shape: text in a language the computer has no dictionary for must
not turn red, so a sentence where most words are unknown is left alone, and the word being typed
waits. Her decisions: **on by default**, **Ignore remembered on this computer**, and **no
per-note "don't check this note"** for now. Trying it, she asked why an English sentence next to
a Romanian one went unchecked: the first version judged whole paragraphs, and she chose
**sentence by sentence** instead. She also chose the plainer **"Add to Windows dictionary"**,
since the word goes to Windows and not to this app alone. Not checked: titles and checklist items (Tk
cannot underline one word in a one-line box) and table cells (drawn on a canvas). The design is
[Spelling](ARCHITECTURE.md#spelling-windows-own-dictionaries-built-to-stay-quiet).

### Sharp text on a scaled screen (2026-10-14)

The owner's call, measured on her own screens first: the app declares itself aware of the main
screen's scale, sharp on a 150% laptop. **Settings → Appearance → Sharp text**, on by default,
turns it off for someone who keeps the app on a second screen that isn't enlarged. Settled along
the way: GDI scaling does not sharpen Tk's text, and Tk cannot follow a window across screens of
different scales. The design is [Sharp on a scaled screen](ARCHITECTURE.md#sharp-on-a-scaled-screen-every-size-is-given-at-100);
the story, with the first attempt's, is in [ISSUES_LOG](ISSUES_LOG.md#sharp-text-measured-this-time).

### The product review (2026-09-10)

After the code audit closed, two waves of parallel reviewers asked the other
question — not "is this correct?" but "would you use it, and would you be
embarrassed if people saw it?" — with every finding verified against the code, the
hostile wave putting each to three refute-by-default verifiers, and a harshness
audit on top asking whether the surviving list was still too soft (it was; the
worst findings came from that pass). The full register, including what held up
under attack and what verification refuted, is
[`docs/archive/PRODUCT_FINDINGS.md`](archive/PRODUCT_FINDINGS.md). The headline: the app's
correctness held, but several routes edit or delete the user's data with no
message, no Trash and no undo, and the note-list rebuild makes every pause in
typing freeze the window.

### The code-audit programme (2026-09)

A full multi-agent audit of the codebase (ten read-only subsystem auditors, then adversarial
critics) produced 152 findings in early September; every one that warranted code shipped, in
severity order, across five releases:
[0.71.113](../CHANGELOG.md#071113--2026-09-09) (highs: import hardening),
[0.71.116](../CHANGELOG.md#071116--2026-09-09) (undo atoms),
[0.71.119](../CHANGELOG.md#071119--2026-09-09) (user-facing safety),
[0.71.125](../CHANGELOG.md#071125--2026-09-10) (mediums) and
[0.71.134](../CHANGELOG.md#071134--2026-09-10) (smalls + the tool gates). Each fix was
mutation-tested and widened to its whole class by an adversarial review round before merge.
What stayed open on purpose is recorded under
[Known limitations](#known-limitations) ("Audit residuals"), and the investigation stories live
in [ISSUES_LOG.md](ISSUES_LOG.md).

### Rich text formatting

Complete, in five phases:

- Phase 1 (`0.31.39`): a Bold/Italic/Underline/Strikethrough toolbar and right-click menu, with
  keyboard shortcuts, applying either to a selection or to whatever's typed next.
- Phase 2a (`0.32.44`): text color and highlight, added to the same toolbar with swatch-style
  pickers (no hex-code entry — see [CHANGELOG.md](../CHANGELOG.md)).
- Phase 2b (`0.34.51`): paragraph formatting — bullet and numbered lists with multilevel nesting,
  indentation and alignment (CHANGELOG records why numbered levels are not lettered). Quote blocks
  shipped with it and were removed again in `0.36.54`.
- Phase 3 (`0.35.51`): font size and family, per selection and as an app-wide default.
- Phase 4 (`0.37.56`): paste that keeps its source formatting, with Ctrl+Shift+V for plain text,
  and copy that carries formatting out.

It also turned out to be the foundation tables were waiting on — a pasted table arrives as HTML,
`core/richtext.py` is where its `<table>` is understood, and tables were then built on top of it.

### Tables

`0.39.63` delivered the spreadsheet-style grid (drawn cells, one floating editor, merges,
per-column width/alignment/hiding in Markdown's separator-row syntax, block copy/paste
round-tripping with Excel, table placement on the page), and the `0.55.81` field-testing marathon
grew it up: multi-line cells (`<br>`), per-character styles rendered as runs, a rich live cell
editor with an active colour, real checkboxes (`[ ]`/`[x]`), row-height drags, row duplication and
auto-scrolling drag-selection.

The standing decision: the note's plain text remains the single source of truth throughout — see
["Tables: plain text is the store, a drawn grid is the view"](ARCHITECTURE.md#tables-plain-text-is-the-store-a-drawn-grid-is-the-view).

### Global keyboard shortcuts

From the 2026-08-31 idea pass; the Settings → Keyboard shortcuts page had shown the gaps plainly.
Ctrl+N (new note) and Ctrl+S (save now) landed first; then Ctrl+F, which grew past the original
"jump to the list search" sketch into a full find-*in*-the-current-note bar — an in-window popup
that searches the open note's text and its tables, distinct from the left-hand list search that
finds *which* note. All three are bound app-wide and listed under Settings → Keyboard shortcuts.

### Settings redesign

Settings is a list of sections on the left and one open section on the right, grouped under
General / Content / Data / More. The questions the redesign settled:

- **Page, not a popup.** Nine settings-related actions open popups of their own (the template
  editor opens nine on its own), and `qa/qa9.py` exists because a nested-dropdown-inside-a-popup
  already broke once. Putting the whole of Settings inside a modal would have stacked another
  layer on that.
- **Flat list, then grouped.** It shipped flat and was grouped shortly after: nine entries in one
  run mixed four different kinds of thing — preferences, managers for content you made, tools that
  delete things, and read-only information.
- **The nav does not shrink on a narrow window.** It was built to, and the breakpoint could never
  fire: the app holds its whole content area to at least `SIDEBAR_WIDTH + EDITOR_MIN_WIDTH`
  (900px) and scrolls horizontally below that rather than reflowing, so the Settings pane never
  gets narrow enough. The dead code was removed and the reason recorded in `settings_page.py`.

The four follow-up quick wins all shipped on 2026-08-30: a "last exported" line in Backup (showing
the last successful export's date and time; failed exports don't move it), trash retention as a
real setting (a 7–90 day selector in the Trash panel; the purge, the days-left column and every
message quote it, and unusable hand-edited values read as the 30-day default), a keyboard-shortcut
reference (Settings → Keyboard shortcuts, every bound combo grouped and verified against the
bindings), and template deletion saying plainly that it skips the Trash and can't be undone
(actually routing templates through the Trash was later
[decided against](#explicitly-not-planned-right-now)).

### Splitting the UI into modules

Done, and stopped deliberately rather than out of steam. The data-and-rules layer went first —
fifteen modules under `noteorganizer/core/`, none importing tkinter — and six UI areas were moved
into `noteorganizer/ui/` as mixins: the calculator panel, the Settings page, the dialogs and popups,
the calendar, attachments, and — re-measured once it became one drawing — the note list. Spelling
(2026-10-14) was written into both layers from the start: two `core/` modules and a seventh mixin. All the
pure logic went down into `core/` first. `note_organizer.py` is about 22,000 lines — it dipped
when the extractions landed and grew again through the rich-text, tables and field-testing work,
but the pure logic behind all of that went into `core/` rather than into it, which is the point:
the entry file is a UI hub, not a junk drawer.

The stopping point is a measurement, not fatigue. The seams were measured from the call graph, and
after the first three extractions nothing else cleared the bar — sharing kept 33% of its calls to
itself, open-note tabs 26%, and the editor 17%. The editor barely moved across those three
extractions, which is the clearest evidence that it is the hub the class turns around rather than
a module waiting inside it. The one group that changed shape later was the note list: it stayed
at 41%, but once it became one drawing it kept 90% of its calls to itself, so it was measured
again and moved. What remains in the entry file is genuinely shared surface — the editor the rest
turns around, and methods such as `set_status` and `find_note` that are called from everywhere —
and moving any of it into a file would relocate the tangle rather than remove it. The full
method-by-method analysis lives in
[ARCHITECTURE.md's call-graph case study](ARCHITECTURE.md#case-study-deciding-the-split-with-a-call-graph).

If the UI is ever rebuilt on a different toolkit, that is the moment to revisit this — not before.

## Versioning

### Right now: pre-1.0.0

Keep the first number at `0` until the app actually has a real public launch, so `1.0.0` stays
meaningful (a clean first release, not used up early).

Until then, the other two numbers are **cumulative all-time totals**, not per-release counts —
`MAJOR.<total Added entries ever>.<total Fixed entries ever>`, counted from `CHANGELOG.md`'s
`Fixed` and `Added` sections only (across every version section, `[Unreleased]` included).
`Changed`, `Testing`, and `Removed` entries don't count — they're neither a shipped fix nor a
shipped feature. This file's own open items ("Under consideration", "Known limitations") don't
count either, since they're not done yet, and `docs/ISSUES_LOG.md` entries aren't counted
separately since they're narrative write-ups of fixes already counted in `CHANGELOG.md` — counting
both would double-count the same work.

Bump the version, and cut `CHANGELOG.md`'s `[Unreleased]` section into that new version number
(with today's date), every time `note_organizer.py` changes and the app gets rebuilt for real
use — the same moment a `.exe` rebuild is already called for. Docs-only changes don't move the
version, same as they don't call for a rebuild. If several small PRs land back-to-back before the
next rebuild, they share one bump — the trigger is "about to rebuild," not "one bump per PR."

This exists specifically because `APP_VERSION` drives two real things in the code: the
backup-before-upgrade safety net in `load_notes()`, and the "Updated to version X" startup banner
(`detect_version_change()`) — both only fire when this number actually changes.

### Version ledger

One row per recorded bump. `Added`/`Fixed` are the cumulative totals the number encodes; the
counting notes record what counted, what didn't, and why. The features themselves are described in
[CHANGELOG.md](../CHANGELOG.md).

| Version | Date | Added | Fixed | Counting notes |
|---|---|---|---|---|
| `0.28.38` | 2026-08-17 | 28 | 38 | First recorded total: everything from `0.1.0` through the batch that included the Statistics read-only/live-update fix. |
| `0.30.38` | 2026-08-18 | 30 | 38 | The in-note calculator counted. |
| `0.30.39` | 2026-08-18 | 30 | 39 | The AppData-notes-deleted-by-`purge_stale_copies` bug counted. |
| `0.31.39` | 2026-08-18 | 31 | 39 | Rich text Phase 1 counted as one entry (four character styles together). |
| `0.32.44` | 2026-08-19 | 32 | 44 | Phase 2a (text color + highlight) counted, plus five selection/rendering fixes found while building it. |
| `0.32.49` | 2026-08-20 | 32 | 49 | Five fixes counted: multi-line highlight bleed, right-click menu alignment, comments-box selection, note-colour clobbering, and the theme-switch flicker/performance work. The numpy build change is `Changed` — not counted. |
| `0.32.51` | 2026-08-21 | 32 | 51 | Two fixes counted: Settings storage path and first-launch date reading from a second, uninitialised copy of the entry module; the category-delete dialog calling a soft delete permanent. The Settings redesign itself, the notes-storage move and the visual pass are all `Changed` — not counted. |
| `0.34.51` | 2026-08-25 | 34 | 51 | Paragraph formatting counted as one `Added` (lists, nesting, indentation, alignment and quote blocks together — the same rule as Phase 1), plus a second entry for the formatting toolbar's hover labels. |
| `0.35.51` | 2026-08-25 | 35 | 51 | Font size and family counted as one `Added`. The composite-tag scheme, the list margin scaling with the font size, and the `paragraphs` note field are `Changed`; the two bugs found while building it were introduced in the same unreleased branch — not counted. |
| `0.36.54` | 2026-08-25 | 36 | 54 | Reading-time estimate counted; three fixes counted (Settings information bars on light themes, formatting toolbar overflowing the editor pane, Settings section list not scrolling). Removing the quote block is `Removed` — moves neither number. |
| `0.36.55` | 2026-08-25 | 36 | 55 | Note title capped at 200 characters, after measuring `tk.Entry` slow to 3.5 seconds a keystroke at 100,000 — counted. |
| `0.36.56` | 2026-08-25 | 36 | 56 | The raw hex code taken off the note colour label — counted. |
| `0.37.56` | 2026-08-26 | 37 | 56 | Paste and copy that keep formatting counted; the clipboard and conversion modules behind them are a `Changed` entry. |
| `0.38.56` | 2026-08-26 | 38 | 56 | The expandable writing area counted; the `Testing` entry beside it does not. |
| `0.38.59` | 2026-08-26 | 38 | 59 | Three fixes counted: text boxes stuck at eighty characters, paste from a PDF losing its paragraphs, numbered lists counting the blank lines between their items. The mid-sentence split was introduced and fixed inside the same unreleased branch — not counted. |
| `0.39.63` | 2026-08-28 | 39 | 63 | Tables counted as one `Added` (the same way each formatting phase counted as one); four fixes counted (share codes dropping the paragraphs, autosave skipping tag-only changes, the bilingual Expand/Collapse toggles, the list-renumbering shift arithmetic). The many table bugs found and fixed inside the same branch — not counted, per the in-branch rule. |
| `0.39.64` | 2026-08-28 | 39 | 64 | The app agreeing on its own name (Note Organizer everywhere, as the docs already said) — counted. |
| `0.55.81` | 2026-08-30 | 55 | 81 | Tables-and-templates field-testing marathon (PR #82): sixteen `Added` — the table growth catalogued under [Tables](#tables), plus the template table preview and the editor light/dark toggle — and seventeen counted `Fixed`, led by the startup "Note updated" ghost (UTF-16 span drift). Three fixes introduced+repaired in-branch (template body gaps, the dialog's hidden-table caret corruption, the push-down scroll yank): listed, not counted. The checkmark palette folded into the checkbox entry that replaced it in the same branch; the `Testing` entry (hermetic qa seeding) does not count. |
| `0.58.82` | 2026-08-30 | 58 | 82 | Three `Added` (the Backup panel's last-exported line, trash retention as a real 7–90 day setting, the keyboard-shortcut reference) and one `Fixed` — the note list's scroll guards, closing both long-standing "known bugs" with the measured staged-Configure/silent-shrink root cause (a pre-existing bug, so it counts). The template-delete wording is `Changed` and the menu-op check settling is `Testing` — neither moves the number. |
| `0.64.95` | 2026-09-02 | 64 | 95 | Table field-testing cycle (rounds 2–8 plus the senior audit, PRs #95–96) and the checklist box resize: six `Added` (the system table caption, the grouped table menu, autofit for a whole selection, copied cells arriving in Word as a table, single-note export as a file, the checklist box matching the calculator with a runtime-measured Expand); thirteen counted `Fixed`, all against bugs that shipped in the `0.55.81` `.exe` she field-tested (Ctrl+Z on tables; the one-column table; word count and search reading table plumbing — two entries; the checkbox flicker; the view holding through cell edits; pipe rows pasting onto their own lines; glued letters inheriting styles; the checkbox palette going surgical; the resize burning styles; centred typing staying centred; the cell-deep highlight; the cell editor wearing its cell). Ten fixes inside the two features new this cycle (single-note export, the cells-to-Word clipboard HTML) — introduced and repaired without shipping in between: listed, not counted. The Close-button removal is `Changed`; the `Testing` entries (pre-push gates, the Windows CI runner, the old-teeth audit) and the ROADMAP-scoped phases (fonts inside cells, block-level rebuild) do not count. |
| `0.64.97` | 2026-09-02 | 64 | 97 | Two field-report fixes (PR #98): tables kept out of the comments box (they only ever rendered as raw pipe rows there), and the calendar day preview reduced to plain text plus flags (▦/☑/💬) instead of dumping the raw body and comments. Both are pre-existing bugs in already-shipped features (comments, calendar preview, tables all predate `0.64.95`) — both count. The docs refresh alongside (PR #100) is documentation-only — no bump. |
| `0.66.97` | 2026-09-04 | 66 | 97 | Keyboard-shortcuts + find-in-note cycle (PRs #101–107): two `Added` — app-wide Ctrl+N/Ctrl+S bindings, and find-in-the-current-note (Ctrl+F), an in-window bar searching both a note's text and its tables. No `Fixed` moves the count: the two theme-seam fixes shipped with the find bar (its "Aa" case checkbox and its accent border not following a theme switch) were introduced and repaired inside the same unreleased work — listed, not counted. |
| `0.66.98` | 2026-09-05 | 66 | 98 | English-everywhere cycle (PR #115): one counted `Fixed` — share codes silently dropped the checklist, a gap as old as the two features themselves, so it counts. The caption's switch to English labels ("Table N: description" / "Source:") is a `Changed`, and the multi-script input block plus the promised-state de-flake are `Testing` — none of those move the numbers. |
| `0.66.99` | 2026-09-05 | 66 | 99 | Field-found share-route fix (PR #119): one counted `Fixed` — the editor's "Copy code" built its note from a hand-rolled field list (dropping checklist, formatting and paragraphs) and the single-note import loader skipped the checklist; both ends predate this cycle, so it counts. The end-to-end route check that pins it is `Testing` — no bump from it. |
| `0.66.100` | 2026-09-05 | 66 | 100 | Audit-found delete fix: one counted `Fixed` — the context menu's Delete aimed the shared delete routine by repointing the editor's selection, and a cancelled confirm left it on the wrong note, letting the next autosave overwrite it; the mechanism long predates this cycle, so it counts. The cancel-route regression checks in qa7 are `Testing` — no bump from them. |
| `0.66.102` | 2026-09-07 | 66 | 102 | Autosave-is-mute cycle: two counted `Fixed` — the occurrence-scope prompt firing from the background debounce timer (with its stacked-ghost variant that could mix another note's state into a series), and Ctrl+N plus the calendar's "Add note for this day" clearing the editor without a flush; both mechanisms long predate the cycle, so both count. The delete-route gap-closing checks (PR #127) and the qa8 mute-timer section are `Testing` — no bump from them. |
| `0.66.104` | 2026-09-07 | 66 | 104 | Storage write-safety cycle: two counted `Fixed` — the naive non-atomic writers (trash/templates/settings truncatable by an emoji or a crash mid-write, guards notes_data.json had long carried), and the silent empty-on-corrupt loaders (an unreadable file is preserved aside and announced now); both mechanisms predate the cycle, so both count. The new data-safety and qa5 checks, plus the test suite's ghost-path restore fix, are `Testing` — no bump from them. |
| `0.66.105` | 2026-09-07 | 66 | 105 | Field-reported emoji tear: one counted `Fixed` — Tk Entry's stock BackSpace/Delete removed one UTF-16 unit (half an astral emoji), leaving a torn character that the save's mend rendered as question marks; the mechanism is as old as emoji in titles, so it counts. The qa1 entry-family checks are `Testing` — no bump from them. |
| `0.69.108` | 2026-09-07 | 69 | 108 | Calendar-occurrence cycle: three counted `Added` (the day/series banner naming what the editor holds; ✎ marks in the calendar plus the per-day reset entry; the Repeating/Dated filters and the Calendar: soonest sort with its next-occurrence core helper) and three counted `Fixed` (the right-click edit routes losing the Back to Calendar button; the dropdown button blinking instead of toggling its list; Back to Calendar leaving unsaved occurrence edits behind a stale day panel) — all field-reported against shipped behaviour, so all count. The Date (soonest)→Calendar: oldest rename, the menu cleanup and the Save-return rule are `Changed`; the ~50 qa checks and mutants are `Testing` — no bump from those. |
| `0.71.111` | 2026-09-09 | 71 | 111 | Calendar History cycle: two counted `Added` (the 📋 History register — a searchable, year-filtered list of dated notes and each series' occurrences, built by the pure `history_entries` core helper; and the accent frame on the open day) and three counted `Fixed`, all field-reported against the History/occurrence work as it was built and refined in this same branch but each a distinct user-visible defect: a just-saved occurrence reading dirty forever (Back to Calendar refused to navigate), a History delete not refreshing until a trip to the grid, and the Calendar tab reopening on stale History. The header regroup and the single labelled History⇄Calendar toggle are `Changed`; the unit + qa checks and mutants are `Testing` — no bump from those. |
| `0.71.113` | 2026-09-09 | 71 | 113 | Untrusted-import hardening cycle (two audit high-severity `Fixed`, both a distinct user-visible risk on the same "trust the boundary" class): a hand-crafted share code could smuggle an attachment whose `stored_as` aimed a later delete-forever at a file outside the attachments folder (decode now projects through the shareable slice, and `_delete_attachment_files` refuses paths escaping the folder); and an enormous recurrence interval overflowed `timedelta` in the calendar's startup render, so a corrupt/hostile value could make the app unlaunchable (`normalize_recurrence` clamps the interval at the choke point). Both predate this cycle, so both count. The unit/qa checks and mutants are `Testing` — no bump from those. |
| `0.71.116` | 2026-09-09 | 71 | 116 | Undo-atom cycle: three counted `Fixed`, the same burst-edit-vs-undo class as 0.64.95 in the corners it hadn't reached — a list toggle/indent rewrites the whole body to renumber and, unbracketed, one Ctrl+Z left the note EMPTY; that same rewrite dissolved a drawn table above the list into raw pipe rows (never redrawn); and the grid trio (checkbox set-marker, append rows/cols) were the only structural ops missing the `@_undo_atom` decorator. All predate the cycle, so all count. The button ops' wrapping and the key-handler decision (deliberately NOT wrapped, to keep normal-typing undo grouping) are implementation detail; the qa1 checks and four mutants are `Testing` — no bump from those. |
| `0.71.119` | 2026-09-09 | 71 | 119 | Audit user-facing-safety cycle: three counted `Fixed`, each a class swept whole after adversarial review widened the initial one-site fixes. Copy-a-note aliasing (a copy shared the original's attachment files, so deleting either erased the other's file) closed on all three routes — `duplicate_note`, the Settings duplicate clean-up merge (whose trashed twin's purge destroyed the merged file), and overlapping backup re-import — all via `copy_attachment_file`. Surrogate-mending at boundaries (a just-typed astral emoji crashed `.encode("utf-8")` because mending only ran on disk writes) closed at both remaining boundaries: `encode_share_code` and `_note_export_content` (single + bulk export, whose `(IOError, OSError)` guards never caught the `UnicodeEncodeError`). And the dialog wrappers' dropped `icon=`/`default=` (destructive confirms drew the neutral glyph and pre-focused "Yes") honoured now via `_kind_from_kw` and a `default=` focus target, applied across all ten irreversible confirms; recoverable move-to-trash confirms deliberately keep Enter="proceed". All predate the cycle, so all count. The pure decision helpers are implementation detail; the qa1/qa4/qa6/unit checks, six mutants, and the qa7 dropped-click de-flake are `Testing` — no bump from those. |
| `0.71.125` | 2026-09-10 | 71 | 125 | Audit mediums Level-2 cycle: six counted `Fixed`, one per audit class, each then widened in-branch by an adversarial review round (32 mutants across the branch). Restore-redraw + the dead-grid liveness guard (Z09-F07 widened); table-delete view capture (Z08-F02); silent trash/templates/settings writes surfaced at the `_write_json_atomic` choke point (Z01-F06/Z02-F03); atomic zip + single-note export, close-waits-for-workers, one-at-a-time guard, `.part` attachment copies (Z05-F00/F01, absorbing Z05-F05); the track-every-colour-option sweep — insertbackground family, selectcolor, press colours, event-time hovers (Z07-F03/F04); the Tk-UTF-16-vs-Python conversion boundary — `_py_col` + double-click, cell nav, find widths (Z09-F05/F06). All predate the cycle, so all count. Check-strategy repairs (stale zip artifact, masking straggler net, capture-ordering spies) and the new qa rows are `Testing` — no bump from those. Review-verified residuals recorded under [Known limitations](#known-limitations). |
| `0.71.134` | 2026-09-10 | 71 | 134 | Audit smalls (Level-3) cycle: nine counted `Fixed`, one per class, each widened in-branch by an adversarial round (19 mutants + 2 empirical tool proofs). Calculator contract (lone dot + non-finite, Z00-F01/02); the style-span registry with void-tag exclusion (Z04-F00/01); cell `<br>` round-trip (Z04-F02); the shared visibility predicate (Z03-F01); the nested-Escape guard (Z07-F01); the separator width waiver with the authored-width floor of 4 (Z08-F03 — first attempt at render broke the deliberate ellipsis feature; the fix moved to parse); the whole-notebook backup with trash normalization/dedup and the trash-inclusive claimed set (Z05-F07); swallowed-exception traces across the whole autosave spine with a per-spot latch (Z02-F04); the themed_widgets prune. The Z06 tool gates (ROOT-anchored ui-inclusive file lists, scenes exit code, descriptor-aware duplicate detection) and the qa9 focus-handback are `Testing` — no bump. Declared residuals: recorded under [Known limitations](#known-limitations). |
| `0.71.135` | 2026-09-10 | 71 | 135 | Coverage-programme cycle 2 (the safety sweep): one counted `Fixed` — the attachment ✕ deleted the stored file permanently with no confirmation, the one destructive gesture outside the dialog system (found in passing by a documentation auditor, which is what triggered the full sweep). Every delete/overwrite gesture now carries a verdict in `qa/COVERAGE_LEDGER.md` (C1 closed); the checklist-item ✕ is the documented ACCEPT. The qa6 confirm checks and mutant are `Testing` — no bump from those. |
| `0.71.154` | 2026-09-11 | 71 | 154 | Product-review Tier-0 cycle: nineteen counted `Fixed`, one per user-visible class that predates this branch. The eight Tier-0 findings themselves (the clean-up that deleted checklist-only notes and the duplicate scan that merged them; two windows on one notebook; categories and calendar decor lost on import; the body's shape and the spans that drifted with it; a saved note that could not be emptied; `_prev` dropped on the next launch; the uncapped checklist bomb; the warn-before-opening list), plus the maintenance modal on every fresh install, and — from three adversarial passes over the fixes — the colour doors that could brick startup, the malformed attachment record that corrupted the note next door, the stale-copy purge deleting folders holding unique work, the series edit made in occurrence view that never reached disk, share-as-code and Save-as-template refusing content the app had just saved, the uncapped category door, and "Restore previous" on a repeating note. FIVE bullets were deliberately NOT counted and were folded into the work that caused them: each described a defect this branch both introduced and fixed (the override caret line, the short-note rescue copy, the Ctrl+S/Save disagreement, the dead Back-to-Calendar button, the truncated category name) — none reached a user, so none is a shipped fix. The qa/unit checks, the 29 mutants, the third static gate (`check_one_definition`), the suite-wide generated-event sweep and the UTF-8 repair to `run_tests.py` are all `Testing` — no bump from those. Measured residuals recorded as C13-C18 in `qa/COVERAGE_LEDGER.md`. |
| `0.71.155` | 2026-09-11 | 71 | 155 | One counted `Fixed`: the styling shape that could still make a pasted note unopenable, reached with a fifth of the span ceiling shipped in `0.71.154` — that ceiling counts spans, and the editor pays per tagged range on a LINE. Found by re-measuring coverage-ledger row C13, whose recorded numbers did not reproduce; C15 next to it was false outright and is withdrawn. The regression checks, the five mutants, and both corrected ledger rows are `Testing` and docs — no bump from those.
| `0.71.158` | 2026-09-11 | 71 | 158 | Three counted `Fixed`, none of them reported — all three came from re-checking the project's own records. The one-time cleanup repointed the remembered last-open note at whoever inherited its number (coverage-ledger C17, recorded as a suspicion and never verified); the formatting read-back cost 14.2 s of a 15.5 s startup on a heavily styled note (C14, whose recorded numbers were also wrong); and the sidebar's sort label was clipped on both platforms (C22, seen in a screenshot). The link checker, the generated seam map, the screenshot-retake tool, the regression checks and eleven mutants are `Testing`; the ledger corrections, the retaken screenshots and the currency pass are docs — no bump from any of those.
| `0.72.159` | 2026-09-12 | 72 | 159 | One `Added` and one `Fixed`, both about the parts of the window that were never the app's. The `Added` is the themed title bar together with a per-accent icon — one feature, since the icon's colour IS the title bar's. The `Fixed` is T2-2: no icon anywhere plus a version resource reading `0.0.0.0`. NOT counted: the first-launch title bar bug, introduced and fixed inside this same unreleased work (the same rule that folded five bullets in the 0.71.154 cycle) — it never reached a user. The register corrections, the un-blinded perf check and the theme-switch measurements are `Testing` and docs.
| `0.73.159` | 2026-09-12 | 73 | 159 | One `Added`, no `Fixed`. A note gains a `uid` alongside its `id`, share codes carry it, and both import routes ask whether an arriving note should update the copy here or be added beside it. Counted as a capability rather than a repair: the old text-matching behaviour was deliberate and documented, and its gap only appears once a second device exists. NOT counted: the duplicate-note collision the sibling sweep found, introduced and closed inside this same unreleased work — the rule that folded five bullets in the 0.71.154 cycle. The new headless suite, the qa3 and qa4 checks and the thirteen mutants are `Testing`.
| `0.73.161` | 2026-09-13 | 73 | 161 | Two `Fixed`, no `Added`. The identity minted at every read was never written to disk, so a notebook that was only READ came back with a different set of identities on the next launch — counted, because a share code made before closing the app stopped matching the note it came from, which is the behaviour 0.73.159 shipped to prevent. Counted separately from it: a restore from the Trash could take an identity already in use, a different mechanism (a copy arriving by code while the note sat in the Trash) with its own field check. The eleven new checks and the six mutants are `Testing`.
| `0.73.165` | 2026-09-13 | 73 | 165 | Four `Fixed`, no `Added`. All four came out of one field test on the previous build, and none was reachable by the suite as it stood: the editor's share code carried no identity (its payload is built from the editor snapshot, and identity is not editor content); an update applied from a code was written back over by the editor, which still showed the replaced version; a generated code stayed on screen under the next note opened; and Settings showed the section built on an earlier visit. Counted as four because they are four mechanisms with four field checks, not one report. NOT counted: dropping "Open / Edit" from the note list's right-click menu (`Changed`) and removing the unreachable multi-tab machinery (`Removed`, the C12 finding settled). The sixteen qa3 checks, the qa7 menu and single-note checks and the nine mutants are `Testing`.
| `0.73.166` | 2026-09-14 | 73 | 166 | One `Fixed`, no `Added`. A bulk category change was undone on whichever note was open in the editor, by the editor's own next save -- the same class as the import route's, fixed a day earlier, and now sharing its helper. Counted because it is user-visible and silent: the notes nobody had open kept the new category, so the one that reverted looked like a mistake the user had made. Found by `qa/story_audit.py`, which walks shapes the suite cannot express (a restart, a sequence, a second visit, a what-happens-next) over surfaces nobody had walked that way. NOT counted: nine of that audit's first ten flags, which were faults in the audit itself and are written into it.
| `0.73.167` | 2026-09-15 | 73 | 167 | One `Fixed`, no `Added`. The explanatory line under every Settings title was drawn wider than the label that held it, so each sentence stopped mid-word with nothing to say it had been cut -- three of them, by 51, 57 and up to 69 pixels. Counted because it is user-visible and shipped. The mechanism is one class, not three instances: every wrapping width in that page was a hand-picked number standing in for padding the label cannot see, and the panel's own `padx=48` a side made every guess short. Found by photographing the app for the documentation gallery, not by any check -- and the measurement that located it took three attempts, two of which asked the wrong question. |
| `0.74.168` | 2026-09-15 | 74 | 168 | One `Added` and one `Fixed`. The `Added` is Undo on the delete banner, counted as one entry the way each formatting phase was: the three delete routes (a note, several at once, one day of a repeating note) are one feature reached three ways, not three features. The `Fixed` is the banner opening with a tick of success whatever it had to say, so a failed disk write announced itself as “✓ Something went wrong with that” — pre-existing, shipped and user-visible, so it counts. NOT counted: the wording of the banner's own new text (“note(s)” → “notes”), which was written and corrected inside this branch without shipping in between; and the twenty-two qa checks with their thirteen mutants, which are `Testing`. Worth recording for the next cycle: a field report during this work (“the picture breaks a little and rebuilds itself when I delete”) was measured to be the note-list rebuild — 169 widgets, 129ms, identical with the banner removed entirely — so it belongs to the theme-switch flicker's class, not to this feature. |
| `0.74.169` | 2026-09-15 | 74 | 169 | One `Fixed`, no `Added`. Deleting a note redrew the whole screen — 264 widgets, ~185ms — and two of the three things it rebuilt were not on screen at all. Counted because it is user-visible and shipped: reported from the field as “the picture breaks a little and rebuilds itself”. One entry rather than three, because the calendar, the statistics and the list are the same mechanism seen in three places: work done unconditionally on a data change for a surface nobody is looking at. NOT counted: the stale calendar after leaving Settings, which was introduced and closed inside this branch (found by listing the four routes back to the calendar rather than trusting that a mechanism existed); and the eighteen checks with their eight mutants, which are `Testing`. The repaired qa7 check is `Testing` too — it was passing on timing, not on its subject, and only the speed-up exposed it. |
| `0.74.170` | 2026-09-15 | 74 | 170 | One `Fixed`, no `Added`. A repeating series is one note in every list and every count, and deleting it takes every occurrence — but only the single-note delete said so. The bulk move to trash and both permanent deletes in the Trash called it “a note”, and the Trash listed it like any other. Counted because it is user-visible, shipped and field-reported, and because two thirds of it is irreversible. One entry, not four: the same sentence was missing from four places, and it is now written once. NOT counted: `is_recurring` raising on a recurrence field holding a string — real, but unreachable before this branch, since live notes are normalised on load and nothing had ever asked a TRASH entry (which is not) whether it repeats; the Restore/Delete buttons being squeezed, whose pack-order flaw is older but which only became visible when this branch gave the row a longer line; and the taller Trash list, which is `Changed`. The thirty-one checks and eight mutants are `Testing`. |
| `0.75.173` | 2026-09-15 | 75 | 173 | One `Added` and three `Fixed`, all in the selection bar's neighbourhood and all field-reported. The `Added` is “Select all” turning into “Unselect all” once everything on screen is selected — a mis-aimed press used to cost the whole selection mode, since nothing else released a selection in one gesture. The `Fixed` are: selecting or unselecting every note redrawing the whole list to move a tick (140 widgets, ~170ms a press, and twice as often once the button could also let go); the bar's last action being cut off (“Export” drawn 13px short of what it asked on Windows, and at ONE pixel on the Linux image, where the fonts are wider and the same four controls ask 338px of the 250 available), and a check mark's well being set to the surface the box sits on, so on every dark theme a ticked box looked untouched — twelve widgets shared that one. NOT counted: the `check_well` palette entry, the two-by-two layout and the one-definition `_visible_note_ids` (`Changed`); the seven mutants, the width probe and the three existing checks repaired for naming the old colour (`Testing`); and a wrong first diagnosis of the tick boxes, built on a fixture that ticked nothing, which shipped nothing because a screenshot was asked for before the commit. |
| `0.75.176` | 2026-09-25 | 75 | 176 | Three `Fixed`, no `Added`, all in the calendar and all field-reported in one sitting. Two of them are about previews: one drew itself OVER the right-click menu the user had just opened (a menu keeps the event loop running under it, so the hover never stopped firing), and one showed a note's tables as raw vertical bars in both calendar previews — the panel filtered them with the EDITOR's strict rule, so a row typed past its last cell was neither counted nor stripped, and the small hover preview filtered nothing at all and never even said a table was there. The third: Field-reported as “two delete systems in the calendar”, and the report was right about the symptom and not about the cause: the menu it named is not a delete system but the note's whole actions menu, seven entries deep. The real fault was that the app already HAS a rule — a list of notes offers its actions by right-click and carries no button (the sidebar cards), a labelled Delete appears only where a single note is open (the editor) — and the calendar was the one screen breaking it, in both directions at once: its day list carried the only per-row note delete in the app, and its note preview was the only note surface with no right-click menu, which cost six actions besides Delete. Counted as one entry because it is one rule broken in one screen, the same way the series warnings counted as one sentence missing from four places. NOT counted: removing the per-row glyph (`Changed`) and the seven qa7 checks (`Testing`). |
| `0.75.177` | 2026-09-25 | 75 | 177 | One `Fixed`, no `Added`. The bulk category change was the only action in the selection bar that rewrote stored data with neither a question nor a way back, while `🗑 Trash` beside it had both — found by the consistency survey rather than in the field, and recorded as C-1. Counted as one entry although it adds two things, because they are two halves of one promise: the app's own rule is that a destructive action is confirmed in proportion to how recoverable it is, and neither half satisfies it alone. The reason it got the question as well as the toast is that the neighbour's real safety net is the thirty days the note then spends in the Trash — the toast is a convenience on top — whereas a category undo lasts eight seconds and then the old filing is gone from the file. NOT counted: `_undo_bulk_category` and `_category_override_warning` (the fix's own machinery, not separate bullets); the per-note marks carrying `updated` as well as `category`, which is how the one bullet is true of a mixed selection rather than only of a uniform one; the thirty-six qa1 checks and the ten mutants (`Testing`); and the ISSUES_LOG story, the register's status cell and the six test-plan rows (docs). |
| `0.75.179` | 2026-09-25 | 75 | 179 | Two `Fixed`, no `Added`. The first is C-2: a checklist item's bin was the one delete in the app with no route home — Ctrl+Z reaches the Text widgets through `edit_undo` and a checklist is a list of dicts beside them. No confirmation added, deliberately: the register's reason for the comparison turned out to be wrong (it said the removed attachment is one "the file system still remembers", and `remove_attachment` deletes the stored copy), so the attachment's warning is right for an irreversible act and the checklist's answer is to become recoverable instead. The second was found by probing the first and is counted separately because it is a different mechanism with a different symptom, on older ground: a plain toast replaces `_toast_action` with `None`, so the autosave's own "Note updated" wiped whatever Undo had just been offered — about a second, not the eight the banner appeared to promise. It counted even though it also repairs the category offer from `0.75.177` two rows above, which would fall under the introduced-and-fixed-unreleased rule on its own, because the same wipe took the trash and occurrence offers that shipped in the `0.75.173` build and did reach a user. NOT counted: `_undo_checklist_delete` and the `yield_to_action` parameter (the fix's own machinery); the thirty-three qa1 checks and nine mutants (`Testing`); the corrected register cell, the ISSUES_LOG story, the qa/README house rule and the test-plan rows (docs). |
| `0.75.180` | 2026-09-25 | 75 | 180 | One `Fixed`, no `Added`. C-3: the Trash retention dropdown saved on the click, so choosing a shorter window destroyed everything the new window had already outlived at the next startup — attachment files deleted from disk with the notes — while the three other permanent deletions on that same screen all warn with `icon="warning", default="no"`. Counted as one entry although it adds both a question and a silence rule, because the silence is what makes the question worth having: a longer window never asks, and neither does a shorter one with nothing old enough to lose. NOT counted: `_trash_cutoff`, `_trash_entry_is_past`, `trash_entries_past_window` and `_retention_loss_warning` (the fix's own machinery — the first three exist so the dialog's count and the purge's deletion are one judgement rather than two that can drift); the thirty-seven qa6 checks and ten mutants (`Testing`); `--all-failures` and the truncation notice in `tools/run_tests.py`, which was printing only the first eight failures and so made two live mutants read as survivors (`Testing`); and seven dead `parent=` arguments found in `settings_page.py`, which `_themed_dialog` has never accepted — reported, not touched, since they are unrelated to this fix. |
| `0.75.181` | 2026-09-26 | 75 | 181 | One `Fixed`, no `Added`. C-5: three routes discarded a calendar day's colour or markers with no question and no way back, and the two menu entries that do it sit directly under the entries that create the same thing — a mis-aim by one row was a permanent loss. Counted as one entry although it covers three routes, because it is one act on one kind of thing reached three ways; the same rule that counted the series warnings as one sentence missing from four places. The third route is the palette's own "No color", which the finding did not mention and a sibling sweep found. NOT counted: `_clear_day_markers` and `_undo_day_clear` (the fix's own machinery); the twenty-three qa7 checks and seven mutants (`Testing`); the check that holds the marker popup unchanged, which needed no fix because it already works on a copy and writes only on Save (`Testing`); and the `Changed` entry folded in from `[Unreleased]` — the Delete label naming the whole series — which by policy moves no number. |
| `0.75.183` | 2026-09-26 | 75 | 183 | Two `Fixed`, no `Added`. C-7, counted as two because they are two mechanisms with two symptoms and two very different reaches. The first: Escape answered none of the small anchored popups — 15+ of them — because the binding sat on a borderless Toplevel that never takes keyboard focus, so the key went to the app window, which had no Escape binding while a popup was open. The binding was always sound; measured by forcing the focus inside a popup, where it closed at once. The second: the bulk Category and Export popups had no Cancel and no close glyph, so leaving without acting meant clicking empty space and trusting it counted. Either one alone answers the report's "the only way out is a click on empty space", which is why they are not folded together the way C-1's question and undo were. NOT counted: `_escape_backs_out` and `_bulk_popup_cancel` (machinery); the `_nested_dropdown` tracking, which exists so Escape closes a nested list without tearing down its host — the breakage the code's own comment records (`Changed`); the twenty-five qa9 checks and five mutants (`Testing`); and the refuted half of the finding, that "none calls focus_set", when the inline rename popup focuses its own field and binds Escape there — corrected in the register, no bullet. |
| `0.75.184` | 2026-09-26 | 75 | 184 | One `Fixed`, no `Added`. C-6, and the last of the survey's seven destructive findings. Counted as `Fixed` rather than `Changed` — the distinction against `0.75.183`'s folded-in Delete label, which moved no number — because that label was merely incomplete while this actively misinformed: the button that cleans up every duplicate group wore the sidebar's own fill, the ordinary text colour, a smaller font and less padding than the button below it that acts only on what you ticked. Photographed before the change, it did not read as a button at all. Neither button's behaviour changed; both go through one confirming path, so nothing was ever lost for good — what was wrong is what the screen said about which action is the broad one. NOT counted: the five qa2 checks and four mutants, one per dimension the weight can be wrong in (`Testing`); and the before/after screenshots, which are working artefacts rather than shipped files. |
| `0.75.185` | 2026-09-28 | 75 | 185 | One `Fixed`, no `Added`. A paste onto a field still showing its placeholder landed glued to it — the note title and the Calendar's History search, both shipped that way in the `0.75.184` `.exe`, so a pre-existing bug and it counts. Counted as **one** entry although it has two faces on screen (the glued text, and the title's 200-character cap losing thirteen characters to the hint): one mechanism, one missing binding, one fix. Not from a survey row but from the pre-flight sibling sweep for C-11/C-12, which asked which fields already had both a placeholder and a paste menu. The `qa/README` rules and the [story](ISSUES_LOG.md#the-paste-that-landed-on-top-of-the-placeholder) are `Testing`/documentation — neither moves the number. |
| `0.76.192` | 2026-09-28 | 76 | 192 | One `Added` and seven `Fixed` — the consistency survey's seven cheap rows (C-11, C-12, C-19, C-20, C-21, C-22, C-24), one entry each. The `Added` is the search box's ✕: no search box in the app had a clear affordance, so it is a capability rather than a repair. The share panel's ✕ is counted inside C-24's `Fixed` instead, because the editor's code area already had one and that row is precisely about the two surfaces disagreeing. **Not counted:** the `<<Paste>>`→autosave binding on the date field. Measured before the change — a pasted date scheduled no save — but the route only exists because the paste menu in this same branch created it, so it is a hazard introduced and repaired unreleased, which the in-branch rule lists rather than counts. Also not counted: the three `qa/README` rules and the vacuous check found while doing it (`Testing`). |
| `0.76.195` | 2026-09-28 | 76 | 195 | Three `Fixed`, no `Added` — the survey's C-10, C-18 and C-23, all the same shape: a control that already did something and never said what. Counted as `Fixed` rather than `Added` because the capability existed in each case; the hover-label helper in particular has been in the editor since `0.34.51`, where introducing it *was* counted as an `Added`, and this is the gap between two screens rather than a new feature. **C-25 moves neither number**: a docstring, a comment and two lines of project description are documentation, and deleting the dead `_add_row` is `Removed`. |
| `0.76.198` | 2026-09-28 | 76 | 198 | Three `Fixed`, no `Added`. C-15 (the sort and filter are remembered) and C-16 (the day-marker cap explains itself), plus a **third** the pre-flight for C-15 turned up: the guard that keeps the filter selection valid asked `not in CATEGORY_COLORS`, which is true of both type filters — so adding a category in Settings silently reset a "Repeating" filter to All. Pre-existing in the shipped `0.76.195` and measured on the real app with a control before anything changed, so it counts. C-15 is `Fixed` rather than `Added` because the capability was already there twice over on the same panel — the grouping checkbox and the folded groups both persist — and this is the gap between three adjacent controls, not a new preference. |
| `0.80.198` | 2026-09-29 | 80 | 198 | Five `Added`, no `Fixed` — the survey's "doing a thing to many notes" group (C-13, C-14, C-17, and the bulk half of C-9). Each is a capability that did not exist: the selection bar could not pin at all, the Share panel could not be filled in a click, the Trash had no bulk gesture but the irreversible one and no way to tell two notes apart, and a note's own menu could not change its category. The Trash counts as **two** because its row calls them "two separable additions" — the tick-and-restore and the hover preview are independently useful. Not counted: a comment claiming a Markdown export, a sibling of C-25's docstring missed by that sweep because it greps as a comment about Markdown rather than as a claim about the formats on offer. **C-9's keyboard half is NOT in this release** and is not counted anywhere: see its register row. |
| `0.81.199` | 2026-09-29 | 81 | 199 | One `Added` and one `Fixed` — the register's last two rows. The `Fixed` is C-8: the calendar chip did the wrong thing rather than lacking something, so it is a repair. The `Added` is C-9's keyboard half, counted as **one** entry although it is a focus ring, arrow navigation, Enter and the menu key — they are one feature, in the same way each formatting phase counted once. **Not counted:** a bug I introduced and repaired inside this branch. A third place marks which note is open, surgically, and it still spoke the old scheme's language of thickness 0 and 2 — so it stripped the focus ring off whichever card you left and painted the focused one accent. Found by the Linux image rather than by reading, along with `<App>` not being a keysym on X11 at all, which took every card down there while Windows was green. |
| `0.81.200` | 2026-09-29 | 81 | 200 | One `Fixed`, no `Added`. The focus restore shipped in `0.81.199` decided from `focus_get()`, which answers `None` whenever the process does not own the desktop foreground — so it read "nothing has the keyboard" in exactly the case where something did, and a list rebuild could pull the keyboard out of the title box. **Counted**, although no `.exe` ever carried it: the exemption in this policy is for a bug introduced and repaired inside the same unreleased branch, and this one left its branch and sat on `main`, where anyone running from source meets it. The qa1 clipboard fix beside it is `Testing` and moves nothing. |
| `0.81.202` | 2026-09-29 | 81 | 202 | **Two** `Fixed`, no `Added`, shipped as one release because they are the same complaint in two places: the app holding something and not showing it. (1) Every line on a note's card was a label with no wrapping inside a fixed-width sidebar, so anything longer than the card was drawn off its edge and simply not shown — the title, the preview, and the row of marks, which dropped whole tags and left "☑ 1/2" reading as "☑ 1/". Counted as **one** entry although three labels were repaired, by the rule `0.74.169` used for the three surfaces it redrew: one mechanism seen in three places, fixed by one act. Same mechanism `0.73.167` fixed on the Settings page, whose sweep never reached the note list — which is why the fix reuses that release's helper rather than inventing a second way. (2) Settings → Keyboard shortcuts opens by saying "Everything the keyboard can do" and had not held that since `0.81.199`: the note list's keys were bound and on no row of it. A repair rather than an addition, because the page and its promise already existed — what shipped is the promise being kept. **One** entry, not three: the omission is the group, and ↑/↓, Enter/Space and Shift+F10 were left out by the same act. These two were separate branches (`0.81.201` and `0.81.202`) until they were combined into one PR to stay inside the month's CI allowance; combining them also removed a changelog conflict and made the release read as one story. NOT counted: the qa1 overflow check, the qa6 check that reads what a card BINDS and requires each key to be named on the page, four `story_look` scenes, the `--accept` repair beside them (it blessed every picture it had taken, so accepting one screen rewrote sixteen files), and a version number written wrong in a comment (`0.84.198`, a release that does not exist) — all `Testing` and docs. The `Changed` entry about the themed dialogs' keyword handling ships inside this release and moves nothing. |
| `0.81.213` | 2026-09-29 | 81 | 213 | **Eleven** `Fixed`, no `Added` — the data half of the 2026-09-29 "try to break it" audit, every one a place where the app moved, merged or removed a user's work from half the evidence, and every one shipped in `0.81.202` or earlier, so all count. One entry per mechanism, not per site: the categories lost at the loader's door (Add, Rename and the backup import — three doors, one rule); the categories lost with settings.json; automatic removal on a resemblance — the startup collapse and a restored backup's Trash skip are **one** entry, the same looser question asked in two places and answered by the one strict signature; Restore previous bringing back only the text; a backup's Update dropping what its copy carried; duplicate ids; the month-end repeat counted per landing; the share code's unchecked version; the double launch deciding its folder twice; the purge deleting what it never copied; and the migration notice's two false sentences. NOT counted: the test runner surviving a hung script, qa1's three fresh apps answering the startup notice, qa7's keyboard walk forcing its preconditions, the three new story chapters and the 27 mutants — all `Testing`. The warning dialogs' filled "Yes" against an Enter that presses "No", seen in a story photograph, is recorded for a person's judgement and moves nothing. |
| `0.82.230` | 2026-09-30 | 82 | 230 | One `Added` and **seventeen** `Fixed`: three stacked branches released as one, because they land back to back before one rebuild. The `Added` is Custom order — the list arranged by hand, by dragging a card or with Alt+↑/↓ — counted **once**, as each formatting phase was: the drag, the keys and the sort are one feature. The `Fixed`, all shipped in `0.81.213` or earlier, so all count: **eight** from the keyboard-and-dialogs branch (Cancel on a repeating day's save question keeps you there; a question holds the app-wide shortcuts; the keyboard goes back after a question; formatting after a table cell; Ctrl+N and Ctrl+F leave Settings; a popup's button closes it on a second click; the smallest window shows a note; a cancelled backup import cleans up), **five** from the speed branch (the autosave that rebuilt the list; the list drawn on demand; window handlers run once per widget; a picture opens at once; the notes file written in one piece), and **four** from the list branch (the list as one drawing — the field-reported tearing and slow return; a click handing the list the keyboard; the Ends radio's dot on dark themes; the window's edge following the mouse). One entry per mechanism: the drawing and the on-demand drawing are two, because either would have shipped without the other. NOT counted — introduced and repaired inside this unreleased work: the drawing's extent read from Tk's `bbox` (8.6.15 and 8.6.16 pad a rectangle differently, and the Linux image read the list's top as 1); the Select-mode tick column guessed at 17 pixels; the drop line that promised a place across the pinned line or into another group; the dragged card leaving the list's view; the drag's edge scrolling at one fixed, slow step; and the travel story's Romanian failure message. The qa checks, the two new story chapters and the 71 mutants are `Testing`. The window's-edge entry grew inside this work — a second field test called the freeze alone heavy, and Tk's whole-window repaint styles came off too — and stays one entry: one complaint, one mechanism seen from two sides. |
| `0.82.232` | 2026-09-30 | 82 | 232 | **Two** `Fixed`, no `Added`, on a branch stacked straight after `0.82.230` and landing before the same rebuild — a bump of its own because `0.82.230` had already been cut in the branch before it, so the `.exe` built after both goes out as `0.82.232`. (1) The calendar as one drawing: counted, because the month's widgets are a mechanism of their own — the list's drawing did not touch them, and either fix would have shipped without the other, the rule `0.82.230` applied to the list and its on-demand drawing. Field-reported: the freeze of `0.82.230` kept the edge with the pointer but left the month standing still until the drag ended. (2) A day's markers drawn black on every theme — shipped since the markers did, found while drawing them, so it counts. NOT counted: the test harness pinning the mouse button (a check-strategy repair; the story's red it explains was the harness's, not the app's), the two new story chapters, the re-aimed mutant and the 28 mutants — all `Testing`. |
| `0.82.233` | 2026-09-30 | 82 | 233 | **One** `Fixed`, no `Added`, on a branch stacked straight after `0.82.232` and landing before the same rebuild — a bump of its own for the reason `0.82.232` gave, so the `.exe` built after all of them goes out as `0.82.233`. Counted: show/hide decisions asked whether a widget was on the screen, so a note opened from the Calendar kept the last note's Restore previous (a dead button), title counter and share-code strip — shipped behaviour, reproduced on that route, so it counts. **One** entry for fourteen sites: one mechanism, one fix (`_is_placed`), the rule `0.81.202` applied to three labels repaired by one act. NOT counted: the Settings sections stacking when chosen in the same breath as opening Settings — no route in the app does that, only scripts (`story_look`'s scenes 04 and 05 had photographed it since their first reference; their corrected pictures are `Testing`); the gate's new rule, the qa6 and qa7 checks, story chapter 12 and the six mutants — all `Testing`. |
| `0.83.335` | 2026-10-02 | 83 | 335 | **102** `Fixed` and **one** `Added` (the keyboard folds and opens the note list's groups), on branch 7: nineteen rounds of agents tried to break the app, each aimed at what the round before had changed, and every finding was reproduced with the agent's own probe before it was fixed. Counted: only defects that shipped in 0.82.233 or earlier, one entry per mechanism — where that was in doubt it was measured on 0.82.233 itself (the table header Ctrl+Z gave back one column off: four of six operations, in the Linux image; a bold italic word pasted, and bold pasted inside an italic word, were drawn italic only, and a paste at a bold word's edge inside a 20 pt heading came out at 12 pt, there too). NOT counted: defects introduced and repaired inside the branch, each folded into the entry of the shipped defect it belongs to — the formatting journal's cost, the edge guard refusing an empty line, merged cells losing a colour, the second "Save changes?" beside a template and its bin (and that bin after a Replace), a pause splitting a run of styled deletes, the ring after a wheel turn (and beside an undrawn row), the Custom order offer lost to a second move (and then the older one offered), the strip just outside the list's edge, the day a repeat-off Save left on screen and the left-out date its reload overwrote (and the status words a second autosave then replaced), the series a day saved on its own moved (and, with a field left out, moved anyway at the next save), cells pasted over a selection that went into the table beside it, came in as raw tabs after Ctrl+A or took two Ctrl+Z, and moves by hand that cancel out counted as a new arrangement (and then a new note placed by hand counted for nothing, and then a duplicate or a note restored or nudged into a place counted as placed by hand); a save that only met a left-out field moving "Last updated"; the selection's stop at a drawn table missed with two tables close together and on a first-line table (and select all in a note that begins with a table cut the table out); the summary under the repeat previewing a number the save no longer stores; and two things no one could see: the untracked autosaves a direct save left running, and Escape's silent background error in a rename box (`Testing`). From the eighth round on, many findings were regressions of the round before's own fixes — the line under a note-ending table, the turn-off that waits, the deleted day's Undo around it, the walk that lays the spans, the font tags where a size meets bold — each repaired in the branch and counted nowhere; the deleted day's Undo after a turn-off went through four designs, each broken by the next round, and was simplified back to what 0.82.233 said: the day can't come back. The qa checks, the stories and the mutants — at least 361 named in the commit messages — are `Testing`. |
| `0.83.338` | 2026-10-03 | 83 | 338 | **Three** `Fixed`, no `Added`, on a branch stacked straight after `0.83.335`: the security pass that followed the nineteenth round, aimed at what comes in from outside. All three shipped in `0.83.335` or earlier, so all count. One entry per mechanism, not per site: (1) every JSON reader caught one of the three ways a text turns out unreadable — **one** entry for fourteen readers (the four loaders, six at startup, the share-code decoder, three in the backup import), answered now by one definition, `JSON_UNREADABLE`; (2) `normalize_note` trusted an attachment record's own shape — the display name standing in for the stored one unflattened, and the record kept whole with whatever else it carried, are **one** entry: one choke point, now rebuilding the record from its two names as it already rebuilt a checklist item; (3) the formatted paste cut at its caps without a word. |
| `0.84.338` | 2026-10-03 | 84 | 338 | **One** `Added`, no `Fixed`, on a branch stacked straight after `0.83.338`: dates typed the way people write them and shown day first, asked for while preparing a usability test with pupils, who would write 17.10.2026 and find it left out. Counted **once**, as each formatting phase was: the reader, the field's form, the settling of a short year, the day-first display and the reading of a stored day-first date are one feature. The calendar's Add note writing the stored form past the field's own writer, and a note arriving with a day-first date missing the calendar, are this feature's edges, not shipped defects of their own -- not counted. |
| `0.84.340` | 2026-10-03 | 84 | 340 | **Two** `Fixed`, no `Added`, on two branches stacked after `0.84.338` and released as one, as they land before one rebuild: the light themes' secondary text below WCAG AA (as old as the light themes, so it counts), and the window's horizontal scrollbar shown at every width (as old as the scroll wrapper, so it counts). The note list's move to its own module is `Changed`; the gates, the mutation runner, coverage in CI, the bench, the comments convention and the language gate's prying are `Testing` -- none move the numbers. The 71 contrast pairs still below AA wait for a design decision; they are listed, not fixed, so nothing is counted for them. |
| `0.84.341` | 2026-10-04 | 84 | 341 | One `Fixed`: the hint shown with no templates named "Settings → Manage templates", a section renamed "Templates" when Settings became a list of sections in `0.32.51` -- as old as that rename, so it counts. The qa6 checks (the hint itself, and every "Settings → X" in the code against the real section names) and mutant M01 are `Testing` -- no bump from those. |
| `0.84.357` | 2026-10-07 | 84 | 357 | **Sixteen** `Fixed`, no `Added`: what the owner's first full manual pass over the test plan found on the `0.84.341` `.exe`, on seven stacked branches released as one, as they land before one rebuild. All shipped in `0.84.341` or earlier, so all count, one entry per mechanism: ticks on dark themes; a theme switch saying "Note updated"; a highlight in an open cell; previews drawing a table as bars; copied cells bare in the app; copied cells colourless in Word; size and typeface lost on copy; what goes into a checkbox cell beside its brackets; Enter in a numbered list throwing the view to the top; an emoji landing after a grey hint; the caret left in a box on a click on empty space; copying a long styled note freezing; Show more redrawing every row; unchanged notes skipped on import without asking; the share-code warning naming exports that do not exist; bold and italic from a web page arriving plain. NOT counted — introduced and repaired inside this unreleased work: the nine regressions three read-only reviews found in these fixes (a highlight lost when a note was left with its cell open, a copied header read one letter off, ticked rows unreadable after a theme switch, a table cell left open by a click on empty space, Show more after a delete, and four smaller), and the import questions counting one batch two ways. The two widenings after them — any road into a checkbox cell, maths kept as words in a preview — complete entries already counted. The qa checks, the story runs and the mutants (T, P, Q, K, A, B, G: 64 in all) are `Testing`. Measured and left as a decision: one very long paragraph is slow in Tk itself (Known limitations). |
| `0.88.361` | 2026-10-08 | 88 | 361 | **Four** `Added` and **four** `Fixed`, from the owner's two re-tests of `0.84.357`, on five stacked branches released as one, as they land before one rebuild. The `Added`, each counted once with everything it grew while unreleased: the table that moves with its caption (and the dialog that says how a table moves when every cell is aligned); "📎 With files" in the Show filter; checklist items moved with ▲ ▼ and Alt+↑/↓ — the arrows' place, the ring, the keyboard after a press and the template editor's list are one feature; search and order in the Share panel, its live following of a new sort included. The `Fixed`, all shipped in `0.84.357` or earlier, so all count: an open checkbox cell showing its brackets; a long checklist item's bin squeezed out at 1024 pixels and below; the find bar's accent border going grey while typed in (since `0.66.97`); the find box unreadable on a light theme when nothing is found (as old). NOT counted: the find bar closing when the note is left (`Changed`); introduced and repaired inside this unreleased work — the checklist's ring drawn grey (seen on a photograph), the Share panel 14 pixels over its room at 1150×860 (seen in the Linux image), the banner that went before it was read, and the not-found tint adjusted twice by eye. The qa checks, `ring_mismatches`, the contrast gate's `DERIVED` surfaces, `check_mutant_targets` and 53 new mutants (H, L, F, O, V, X, Z) are `Testing`. |
| `0.89.362` | 2026-10-08 | 89 | 362 | One `Added` and one `Fixed`, on two stacked branches released as one. The `Added`: a welcome note on the first start — the owner's request, her words over three drafts — counted once with the Settings → About row that brings it back. The `Fixed`: emoji from the app's own pickers, three day markers and two icons written with U+FE0F, which Tk draws as a gap — shipped since the emoji picker, so it counts; the same character in the welcome note's headings was introduced and removed inside this work, not counted. Not counted, `Testing`: the qa5, qa3, test_data_safety and test_richtext checks, the source scan for the character and mutants Y01–Y09 and I01–I04. Known limitation recorded, not fixed: text that already carries the character keeps its gap. |
| `0.89.365` | 2026-10-08 | 89 | 365 | **Three** `Fixed`, no `Added`: the palette chosen by the owner from proposals by a panel of AI reviewer personas (Claude subagents), over five rounds on the running app. All three shipped in `0.89.362` or earlier, so all count, one entry per mechanism: (1) the accent, the warning red and the confirming green each doing two jobs, 71 pairs below WCAG AA (as old as the themes) -- the fill and text shades, the words picked per fill, the dark warning fill and the light confirming one are one entry; (2) find's current match in the note's own text colour on the full accent (since `0.66.97`); (3) a card's tags line in a colour picked for its look, often unreadable (as old as the tags line). NOT counted -- `Changed`: Save the one filled button, the editor row's order and pressed colours, the moves to the Trash in red words, Generate code and the selection bar's Category quiet, the attachment question no warning, and the source-run notebook location (PR #258); introduced and repaired inside this work: the card shades going khaki, the docs naming two moves to the Trash as final and then claiming "every", Midnight Purple's violet changed twice. The contrast gate's 208 pairs and icon checks, the qa checks and mutants PC01-PC21 are `Testing`. |
| `0.89.371` | 2026-10-08 | 89 | 371 | **Six** `Fixed`, no `Added`: what AI reviewers (Claude subagents) reading colour-blindness simulations hesitated over, and two things the owner found on the same run. All six shipped in `0.89.365` or earlier, so all count, one entry per mechanism: (1) find's current match told apart by its fill alone (boxed now); (2) the open tab drawn smaller than the closed one, clam's selected padding beating the app's; (3) `contrasting_fg`'s own brightness threshold putting white on 9 of the 20 day colours (now `letters_on`); (4) the colour picker's tick a literal white; (5) a clicked tab keeping its dotted focus ring; (6) icons the app uses missing from the emoji picker — the welcome note's six and the calendar's nine day markers are one entry, one promise. NOT counted: the screenshot tools opening notes by a person's route and the retaken screenshots (docs); introduced and repaired inside this work: a check that crashed on a colour name instead of failing (CB04 first ran nothing), a Tab handler bound where it never ran, and an icon check that missed ℹ because Unicode files it as a letter. The qa and unit checks and mutants CB01-CB10 are `Testing`. |
| `0.90.373` | 2026-10-12 | 90 | 373 | One `Added` and **two** `Fixed`, on four stacked branches released as one, as they land before one rebuild — the owner's pick of two roadmap groups, the two product decisions on her list and two follow-ups the audit scoped out. The `Added`: days a repeating note keeps its own edits for that its schedule no longer reaches, found (the series line, a walk through them, the calendar History), the owner's call between moving, asking and keeping them findable. The two `Fixed`, both as old as what they fix: a category move's Undo that said "Nothing left to put back" after a rename, and the series line that lost its first and last words at 1200 px. Not counted: the push-down's second rebuild of every table, removed under `Changed` (measured, and nothing on screen differed), and the tests — the own-backup re-import end to end, and seventeen mutants (RB01–RB03, TP01–TP02, CU01–CU03, OS01–OS09). |
| `0.92.374` | 2026-10-13 | 92 | 374 | **Two** `Added` and one `Fixed`, on stacked branches released as one before one rebuild — the owner's field report about one day of a series, and her ask that followed it. The two `Added`: one day of a series opened on its own (the strip, the day's own date and category, what belongs to the series marked so), and a day held on another date while it stays in its series (Move this day…, Undo, Reset from the day itself, which asks about the text). The `Fixed`, as old as the "only this occurrence" edit: a day's edits waited, unseen, for a question asked only on leaving — now a day saves itself. Not counted: rows that run out of room keeping every control (`Changed` — nothing differs at the sizes Windows gives the app), two rows of this release's own day mended before it shipped, the docs, and the tests — DM01–DM15, MV01–MV25, FIT01–FIT05, and five catalogue checks mended. |
| `0.93.374` | 2026-10-14 | 93 | 374 | One `Added`, no `Fixed`: sharp text on a scaled screen. The app declares itself aware of the main screen's scale, with everything that holds text grown to match, and Settings → Appearance → Sharp text to turn it off. It counts as one entry, the declaration, the sizes and the setting together, because none of them means anything without the others. The blur it ends was a known limitation, not a defect of something shipped, so it is not a `Fixed`. Not counted: the docs, and the tests — qa6's scaled screens and DPI01–DPI16. |
| `0.94.374` | 2026-10-14 | 94 | 374 | One `Added`, no `Fixed`: spelling, with Windows' own dictionaries. The underline, its right-click menu (suggestions, Ignore, Add to Windows dictionary), the quiet rules and Settings → Appearance → Spelling count as one entry, because none of them is any use without the others. Not counted: the owner's two changes made while trying it before release (judged by sentence rather than by paragraph, and the menu's plainer name), as they belong to the same entry; the mutant runner telling its own two entries by a mark rather than by the letter S, a repair to a tool rather than to the app, found before anything ran wrong; the docs; and the tests — `test_spelling.py`, qa6's spelling block, and SP01–SP27. |
| `0.94.379` | 2026-10-15 | 94 | 379 | **Five** `Fixed`, no `Added`, on two stacked branches released as one before one rebuild — what the owner's question about thousands of notes turned up, measured and reviewed by four agents. One entry per mechanism, each would have shipped without the others: (1) a backup the app made refused on import over 500 MB or 10,000 files (the zip-bomb check over the whole archive, found by a security review of the first version, is part of this entry: introduced and repaired inside this work); (2) a share code made past the limits its own import enforces; (3) an import's matching walking the notebook once per incoming note; (4) a pin, a new category or a Custom-order move rebuilding the whole list; (5) a day left open on the Calendar rebuilt at every save behind the Notes tab. All shipped in `0.94.374` or earlier, so all count. Not counted: `tools/bench.py --rich --deep` (a tool), the qa2/qa7 previews made deaf to a real mouse (`Testing`: a check's strategy, not the app's), the docs, and the tests — BK01–BK06, SH01–SH03, MN01–MN08. |
| `0.94.382` | 2026-10-15 | 94 | 382 | **Three** `Fixed`, no `Added`, on four stacked branches released as one before one rebuild — the owner's "1 2 si 3" (two small observations left by the scale work, and a pass over the docs) and her review of what followed. One entry per mechanism, each would have shipped without the others: (1) closing the app during a backup import or export let the worker die past the 30-second wait, leaving the unpacked backup, a half-copied attachment or an unfinished `.tmp`, and nothing said so — the next start's word, which the owner asked for at case 660, belongs to this entry (one complaint, completed inside this work); (2) drawing a note's tables asked every drawn grid for each cell, quadratic in the tables; (3) a theme switch rebuilt every drawn table, which flickered — field-reported by the owner. All three shipped in `0.94.379` or earlier, so all count. Not counted: the freshness pass over every `.md` and the retaken Appearance screenshot (docs), the part of the theme switch that remains (Known limitations, measured), and the tests — ST01–ST10, TB01–TB02, TH01–TH06, CN01–CN05. |
| `0.95.382` | 2026-10-15 | 95 | 382 | One `Added`, no `Fixed`: Send feedback, the owner's ask once the whole-file save was decided "not now" — a way for people to say the app is slow, and how many notes they have, without a GitHub account and without her address shown anywhere. Counted once: the button, the site's form with the details it shows, the copied link when no browser opens, and the Store button that waits for a Store page are one feature. NOT counted: every crash log entry carrying the same details through one writer (`Changed`, an existing log made more useful — its start-up writer no longer raising before the data folder is known is part of that change, found while making it), the GitHub bug form's new field and option (the repository, not the app), the site's pages and its build check, the docs, and the tests — FB01–FB10. |
| `0.95.391` | 2026-10-20 | 95 | 391 | **Nine** `Fixed`, no `Added`, on three stacked branches released as one before one rebuild — what comparing the Android port with the desktop turned up on the desktop's side, each tried by the owner from source before release. One entry per mechanism, each would have shipped without the others: (1) a superscript, subscript or circled figure in the date field raised in `read_date`, so the note stopped saving; (2) the Trash purged by a window it could not read — a damaged settings file, or a hand-edited `0`, `"forever"` or `400` (the startup notice, the "Choose…" selector and the promises without a number are part of this entry); (3) the startup purge and removing one attachment deleted a file another note still used (the purge not running on a launch whose notes file could not be read is part of this entry); (4) the cell menu's "Merge with cell to the left / above" wrote over the clicked cell's text; (5) "Insert row above" on a table's header pushed its separator out; (6) bold or italic over a partly styled selection gave all of it one answer for the other style, in the body and across cells; (7) Enter before a list marker's end put a second marker in front; (8) Enter over a selection in a list item or a table cell left the selected words; (9) Backspace over a selection ending just after a marker took the marker. All shipped in `0.95.382` or earlier, so all count. Not counted: the one-definition gate's new rule against a bare `.isdigit()` (a tool), the three new story-look scenes, the docs, and the tests — RD20, TW01–TW13, SF01–SF06, TM01–TM04, LS01–LS10. |
| `0.96.392` | 2026-10-21 | 96 | 392 | One `Added` and one `Fixed`, on three branches merged one after another before one rebuild (PRs #291, #292 and #294; #289 and #290, the docs' freshness and the site's walk, move nothing). The `Added`: the privacy policy from Settings → About — Privacy policy → Read, the link copied when no browser opens, and the policy itself (`docs/PRIVACY.md`, published by hand on Google Sites) counted once. The `Fixed`: the welcome note's headings in one column — ℹ and ✍ drawn as narrow as letters are one mechanism, Tk finding older symbols in the text font, so one entry; shipped in `0.89.362`, so it counts. Not counted: Send feedback and the site's form behind it (`Removed`); the welcome note's 🛡 Your privacy section and the MIT "provided as is" line in About (`Changed`); 🛡 joining the emoji picker (part of that section: every icon the note uses must be one a person can pick); the site kept apart from the apps, with its own privacy notice (the site, not the app); the docs, and the tests — FB02–FB10, FB12–FB13, Y06, Y10–Y12, CB09. |
| `0.96.394` | 2026-10-22 | 96 | 394 | **Two** `Fixed`, no `Added`, three commits merged as one PR (#297) before one rebuild — from the owner's list. One entry per mechanism: (1) a delete, a key typed or a paste across a numbered list left its numbers stale, a joined item's number among the words, or the next item's number glued to what went in — seven deleting routes and three pastes are one mechanism, Tk's own edits over a marker stored as characters, so one entry (issue #296); (2) Backspace just after a list marker took two Ctrl+Z, found beside it — a different mechanism, the marker branch missing its undo unit. Both shipped in `0.96.392` or earlier, so both count. Not counted: a new search showing its results from the top (`Changed`, the owner's call, on both apps); the demo's 🗂 drawn full width and the retaken emoji-picker screenshot (the site and the docs); the docs; and the tests — LD01–LD10, SS01–SS02. |
| `0.96.395` | 2026-10-23 | 96 | 395 | **One** `Fixed`, no `Added`, two commits merged as one PR (#301) — what an agent playing an ordinary user found on the Android app, brought to the desktop. The `Fixed`: an import's question for a single returning note said "Update the 1" and "Add it as new notes" (issue #300) — shipped, so it counts. Not counted: a click on a list's number or bullet putting the caret after it, and "↩ Restore previous" keeping what it replaces and going once the text is back (issue #299) — both `Changed`, the owner's call, on both apps; the docs; and the tests — MC01, RC01–RC03, IM01. |
| `0.96.396` | 2026-10-24 | 96 | 396 | **One** `Fixed`, no `Added`, one PR (#304) — found in a photograph of the Android app taken for its documentation, and the same on the desktop. The `Fixed`: a table pasted as markdown text came in with its columns cut short, every separator cell longer than three characters read as a width set by hand — as old as the hand-set widths, so it counts; the routes it reached (Ctrl+V, Ctrl+Shift+V, a page's HTML, a template's text) are one mechanism, the paste reading another world's spelling, so one entry. Not counted: the desktop Share button weighed and put aside in this file (docs), the website's design pass and its Android pages (PR #305, the site, not the app), and the tests — `test_tables`' `forget_widths`, qa1's paste routes, FW01–FW10. |
| `0.96.401` | 2026-10-26 | 96 | 401 | **Five** `Fixed`, no `Added`, one PR (#311, issues #307–#310) — four from the owner's test plan on the 0.96.396 `.exe`, one seen testing the Android app. The `Fixed`: "↩ Restore previous" missing when a short note's text was replaced before the autosave (the copy measured how much shorter the text got, not how much of it was gone); copied table cells pasted by Ctrl+Shift+V as tab-separated text; a row copied from Excel pasted as loose text (Excel marks the copy inside its table, and the fragment was read alone); a single cell or column pasted framed in pipes — a different mechanism from the row (a row of one cell is no table here), found while testing it, so its own entry; and a web page's non-breaking spaces kept, so search missed the words beside a bold one. Not counted: the binary search for a long column of lone cells, found by the automated security review before release (`Testing`, never shipped), the docs, and the tests — RD01–RD03, PP01–PP02, XL01–XL07, NB01. |
| `0.97.405` | 2026-10-27 | 97 | 405 | **One** `Added` and **four** `Fixed`, one PR (#318, issues #313–#316) — what checking the Trash against its promise and a mass delete turned up, and the owner's ask. The `Added`: Select all / Unselect all in the Trash with Delete N selected permanently — one capability, one commit, so one entry. The `Fixed`, one per mechanism: (1) the rows' days left not redrawn after a new window; (2) an entry's age measured on the wall clock, an hour off across a change to summer time (a stamp before 1970 read as UTC is part of this entry); (3) the toolbar moving with the words readout's line count; (4) "↩ Restore N selected" left over an emptied Trash. All four shipped in `0.96.401` or earlier, so all count. Not counted: the measurements of deleting 500–2,000 notes (nothing to fix), the docs, and the tests — TW14–TW17, WC01, SA01–SA06. |

### At the real launch: 1.0.0 and after

The version becomes exactly `1.0.0` at the actual public release, regardless of whatever
cumulative number it reached beforehand (even `0.150.320` or similar) — the pre-1.0 scheme is
explicitly a development-phase convention, not something that carries forward. From `1.0.0` on,
standard [Semantic Versioning](https://semver.org/) takes over, and **each number resets to 0 at
the release above it** — no more cumulative totals:

- **PATCH** (`1.0.x`) — a release containing only bug fixes, no new features.
- **MINOR** (`1.x.0`) — a release that includes at least one new feature; patch resets to `0`.
- **MAJOR** (`x.0.0`) — reserved for something big enough to warrant it: a real redesign, a
  breaking data-format change, a genuinely new "generation" of the app. Rare; minor and patch both
  reset to `0`.

### Platform-specific packaging/publishing

This section is only about the app's own `APP_VERSION`/`CHANGELOG.md` numbering — how a build
actually gets packaged and published on a given platform (store-specific package versions,
submission requirements) is documented separately, since it doesn't belong mixed into the
numbering policy above:

- [`docs/RELEASE_WINDOWS.md`](RELEASE_WINDOWS.md) — Microsoft Store (MSIX) and alternative Windows
  distribution channels.
- [`docs/RELEASE_ANDROID.md`](RELEASE_ANDROID.md) — Google Play, for the Android app built in its
  own repository (see "An Android version" under [Under consideration](#under-consideration) and
  `CLAUDE.md`'s Project focus).

## Known limitations

Nothing here is an open bug to chase — these are standing constraints of the toolkit, recorded so
they are not re-investigated from scratch. (The note-list scroll bugs that once sat here were fixed
on 2026-08-30 with a measured root cause; the write-up now lives in
["The list that lost its place, twice, for two silent reasons"](ISSUES_LOG.md#the-list-that-lost-its-place-twice-for-two-silent-reasons).)

**Theming** — each Tkinter widget is its own OS window that Windows repaints as soon as its colour
is set, so a very brief partial repaint during a theme switch is still possible; that residue is a
plain-Tkinter limitation, not something this codebase controls (the switch itself was cut from
~140ms to ~26ms, with no rebuilding of unchanged widgets, in 0.32.49). Three further approaches
were tried and reverted — read
["The theme-switch flicker, and three ways not to fix it"](ISSUES_LOG.md#the-theme-switch-flicker-and-three-ways-not-to-fix-it)
before attempting anything more.

*Field-reported again and re-measured 2026-09-12*, with screenshots caught mid-switch showing the
sweep plainly: the sidebar and the editor had changed while the Notes/Calendar tab strip had not,
in both directions. The numbers, so the next person does not start from scratch:

| | |
|---|---|
| `apply_theme`, the code | **37 ms**, and flat — the same at 0 notes and at 25 |
| of which `_recolor_stragglers` | 14–17 ms, the largest single item |
| the rest of the perceived ~75 ms | Windows actually painting, after the code has finished |

The obvious suspect was measured and is innocent: the straggler pass walks 886 widgets and asks
1,319 colour questions in **2.4 ms**, and skipping the ones already recoloured saves 0.2 ms. The
time is in the `configure` calls themselves — that is, in the repainting, which is the limitation
above and not a thing to optimise. The ttk tab strip is always last to change because ttk repaints
on its own schedule rather than with the widgets around it.

The growth from ~26 ms to 37 ms is five months of features, not a regression: nothing in the switch
rebuilds what it did not before. **Do not reach for a rendering trick here** — that is exactly what
the three reverted attempts were. The only thing that removes this is not being Tkinter, which is a
decision of a different size and lives under [Under consideration](#under-consideration).

*Tables, 2026-10-15.* The owner saw the switch flicker more on a note with tables, and it did:
`apply_theme` rebuilt every drawn table, and a rebuilt table appears late — caught mid-switch, a
table was simply gone for a frame. Tables are now repainted in place
([Theme tracking](ARCHITECTURE.md#theme-tracking--two-different-patterns-on-purpose)). What
remains was measured by reading two pixels every 9 ms, one in a table and one on the page beside
it, over twelve switches: in about a third of them the two disagree for 10–20 ms, because the
repaint after a switch takes ~23 ms, longer than one screen frame. A note without tables shows the
same in smaller pieces (the colour button, a scrollbar). Two more ways were tried and dropped:
repainting the tables next to the note's text changed nothing measurable, and Windows painting
the whole window off screen (`WS_EX_COMPOSITED`) stopped the app from finishing its start. Left as
it is — the owner's call.

**Sharp on one screen's scale only** — with Sharp text on, the app is drawn for the main screen's
scale, and Windows resizes it as a picture on a second screen at another scale, a little soft
there. Being sharp on every screen would need the app to rebuild every font and size when its
window crosses screens. Tk does not follow a change of scale, as measured on 2026-10-14: its text
already on screen kept its size. See
[Sharp on a scaled screen](ARCHITECTURE.md#sharp-on-a-scaled-screen-every-size-is-given-at-100).

**The emoji variation selector** — U+FE0F asks for an emoji's colour form; Tk has no colour emoji
and draws the character itself as a blank two letters wide after the emoji. The app writes none
of its own (the emoji picker, the day markers, its icons) and strips it from day markers as they
are read. Text that already carries it is left as it is, because removing a
character from a note's body would move every style span after it: a heart chosen from the old
picker, a paste from a web page, or an emoji typed with Win+. still shows its gap. Delete the
blank by hand (it is one character after the emoji) if it matters.

**Audit residuals (2026-09-10)** — the code-audit programme (see
[Shipped & settled](#the-code-audit-programme-2026-09)) closed every finding that warranted code;
what follows is what it deliberately left as recorded edges rather than fixes. None is an open
bug being chased.

- *Straggler-pass colour collisions* — `_recolor_stragglers` remaps any widget colour matching
  another theme's palette hex, so a data-driven colour that happens to equal one (e.g. `#4cd9a3`
  as both Midnight Purple's Save colour and a note colour) can be swapped on widgets outside the
  note cards (which re-fix themselves afterwards, deliberately). Whitelisting data colours would
  be architectural; the exposure is cosmetic and theme-pair-specific.
- *A second full grid rebuild after a push-down* — **settled 2026-10-12.** Measured on a real
  press and release: the Enter's own release read as leaving the table and rebuilt every table
  again, invisible in frames 45 ms apart; the menu twin did the same on the next letter. Both now
  note where they put the caret (see
  [the lesson](ISSUES_LOG.md#smaller-lessons-moved-out-of-the-code), "The push-down's caret
  line").
- *Three "same note" definitions* — **settled after the 2026-09-29 audit.** Recorded here as
  internal drift with "no user-visible wrong answer known"; the audit found one — the startup
  collapse, on the looser signature, merged away a copy of a routine edited on a single day. Every
  automatic removal (the startup collapse, the stale-copy purge, a restored backup's Trash skip)
  now asks the one strict `content_signature`. The duplicates panel keeps its deliberately
  fuzzier `_dup_key`, because there a person looks before anything is removed. See
  [the story](ISSUES_LOG.md#eleven-decisions-about-your-notes-made-from-half-the-evidence).
- *Omitted-close-tag HTML* — pasted HTML that legally omits `</li>`/`</p>` still bleeds inline
  styles to the end of the document; every real clipboard serializer closes its tags, which is
  why this stays an edge note rather than a parser rewrite.
- *Nested-dropdown bind bookkeeping* — **settled by the break-it rounds (2026-10).** It was not
  harmless: the host's leaked click-outside handler closed every later dropdown on the click that
  opened it, until a restart. Each popup now keeps its own window-level lines, removed by any
  route out. See [the story](ISSUES_LOG.md#the-click-that-deleted-its-own-next-command).
- *Theme-registry pruning cadence* — dead tracked widgets are pruned at each theme switch; a
  session that never switches themes still accumulates them (Python-side memory only).
- *`visual_scenes` burst errors* — a failed burst propagates loudly (nonzero exit) but is not
  counted in the tool's own scene-error tally; cosmetic asymmetry in a manual tool.
- *Dialogs ignore `parent=`* — the confirm wrappers accept and discard a `parent=` kwarg; the
  overlay always centres on the app window, so it never mattered, but a future caller could be
  misled.
- *Commit-then-capture in `_grid_delete_table`* — deleting a table while one of its cell
  editors is still open commits that editor first, and the commit's re-render can run before the
  delete takes its view snapshot, so the restored scroll position is the one from before the
  commit. Declared during the audit and recorded here because, unlike its siblings, it had no
  home in the repo at all — it lived only in a conversation. Cosmetic, and it needs the same
  pixel-level look as the push-down rebuild above before any fix is trusted.
- *Zip-import overlap has no end-to-end test* — **settled 2026-10-12.** qa3 now walks re-importing
  your own backup with a file attached through the real export and import, every answer and a
  delete for good included (mutants RB01–RB03).

**Break-it residuals (2026-10)** — nineteen rounds of agents tried to break the app (see the
[Changelog](../CHANGELOG.md)); what they measured and the fixes deliberately left is recorded
here. None is a bug being chased; each has a reason.

- *A view left deep in a very long list* — a rebuild still draws every row above the view
  (about 1–1.3 s at 5,000 notes for Select mode, Undo or a restore when measured here;
  re-measured 2026-10-14 at 0.56 s at 5,000 and 1.2 s at 10,000 with the view at the list's
  very end), because the drawing is a prefix of the rows by design. A pin, a new category and a
  move in Custom order no longer do: since 2026-10-15 they redraw the one card. The keyboard coming back to the list joins it: when the ring's
  card was carried far below what the list had drawn (grouping turned on, the sort changed, a
new search — which since `0.96.394` starts from the top), Tab
  draws every row down to it — 0.5–0.7 s at 5,000 notes — so that Enter opens the note being
  edited, and later rebuilds stay that deep. Putting the ring on a card in view instead would be
  quick and would open the wrong note, which is the bug the drawing exists to prevent. Windowed
  drawing would end the whole class; it is a change of shape, not a fix.
- *A calendar day holding a hundred notes* — opening its list takes 1–2 s: the list is rows of
  widgets, before and after the rounds alike.
- *Settings → Duplicates searches on every visit* — the drawing is a page at a time now, but the
  search for groups still runs whenever the section opens.
- *Table operations on a very long note* — a style change no longer re-lays out the note, but an
  operation that edits a table's text still turns Tk's grouping off and on, and pays one full
  layout for it.
- *The smallest window* — at 640×600 with the selection bar AND a share code open, "Copy code" is
  cut off by 41 px; the code itself can still be selected and copied.
- *X11 only* — Meta+D, Meta+BackSpace and Meta+Delete (Tk's word deletes, which Windows does not
  have) are not held at a table's edge.
- *A day's own text on a day the series no longer has* — **settled 2026-10-12, the owner's call:
  kept, and findable.** The series line counts such days apart and offers to go through them —
  each made a note of its own, moved to the Trash, or left — and the calendar History marks them
  instead of opening them as days of the series (see
  [the recurrence model](ARCHITECTURE.md#recurrence-model)).
- *Note ids* — an id freed by a delete can be given to the next new note (ids are max + 1). Every
  holder of an id across a delete was checked and acts on the note it means; the one left is a
  keyboard ring that can land on the new note, which is a cursor, not an action.
- *A category move's Undo after a rename* — **settled 2026-10-12, the owner's call: the Undo
  follows the rename.** A rename while it is on offer carries it along, the categories the notes
  came from included, and its banner says the new name; deleting the category they went into
  withdraws it. Deleting one they came from still gets the Undo's own answer, that those notes
  could not go back to a category that no longer exists.
- *Formatting edges seen and not chased* — picking the default size with nothing selected
  inside a 20 pt run types 20 pt while the status line says the size is back to the default;
  Ctrl+B on the whole of a note of 8,000 styled words takes 0.6–0.8 s (the toolbar's reading of
  the selection, a character at a time); a table cell's own size or font is not refitted when
  its bold changes, invisible while the grid is drawn. Seen by the last round, not measured further.

**One very long paragraph (measured 2026-10-06)** — Tk's text widget lays a paragraph out whole,
so the time to reach and edit the end of ONE paragraph grows with its square. Measured on a bare
Tk text box, nothing of the app's in it: 70,000 characters with no line break take 1.2 s to
scroll to the end and 0.2 s a keystroke there; 150,000 take 4.6 s and 0.8 s. Pasting a paragraph
onto itself again and again reaches the point where the window stops answering. The same text
broken into ordinary paragraphs is quick (a 140,000-character note: the paste 0.1 s). The app's
own share of it — copying, which asked every character about every style — was fixed with this
measurement; what is left is Tk's. **Decided 2026-10-07: no warning** — the owner's call, made
on the test plan after trying the case: left as it is.
