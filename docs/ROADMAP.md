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

- **Follow-ups the audit programme scoped out** (see
  [Known limitations](#known-limitations) for the full residuals list): fonts inside table
  cells (the phase deliberately deferred in the 0.64.95 cycle); an end-to-end GUI check for
  re-importing an overlapping backup; a pixel-level investigation of the post-push-down second
  grid rebuild before any de-flicker fix is trusted.

- **Small candidates from the 2026-08-31 idea pass** (put aside deliberately, in rough order of
  appeal; two candidates from that pass have since shipped — see
  [Global keyboard shortcuts](#global-keyboard-shortcuts) and, for the delete-toast Undo,
  [CHANGELOG](../CHANGELOG.md)):
  - **Rebuild only the table block an edit touched** — `_render_table_grids` deliberately tears
    down and rebuilds every grid in the note ("a grid is cheap to make, and tracking which of them
    an arbitrary edit invalidated is not"). The 2026-09-02 senior audit measured the cost
    honestly: ~130ms for a 10-table note per rebuild, run on commits/pastes/menu ops, never on
    keystrokes — fine today, but it is also the root of the entire view-restore timer complexity
    (the explicit/ambient contract exists because rebuilt windows map late). Rebuilding only the
    touched block would cut both the cost and that complexity. An architectural phase with its own
    design pass, not a patch; measured before, it must be measured after.
- **Route template deletion through the Trash** — so templates would be restorable like notes.
  It is a data-format change, not a quick win; meanwhile the delete confirmation says plainly that
  it skips the Trash (see [Settings redesign](#settings-redesign)).
- **Spell-check in the editor (desktop only).** A red wavy underline on misspelled words with
  right-click suggestions — **not** silent auto-correct, which would mangle names, technical terms
  and other-language words in a notes app without asking. This is a desktop-only feature: Tkinter
  draws its own text and gets no spell-check from the OS the way a browser textarea or a native
  field does, so it must be built; on a future Android build the on-screen keyboard's IME already
  provides spell-check and auto-correct in the user's language for free, so nothing would be built
  there. It is a scoped phase, not a quick win, and it must clear the project's bar before
  shipping: **stays fully offline, stays fast on weak machines.** That means a dependency decision
  (the least-bad fit is `pyspellchecker` — pure Python, bundled dictionaries, no system libraries,
  works under PyInstaller — at the cost of a few MB per language in the `.exe`), picking the
  language from `locale` at startup, checking only the visible/changed text on a debounce rather
  than every word on every keystroke, and drawing the underline through the existing rich-text tag
  system without disturbing it. Decide deliberately, with the dependency approved, when picked.
- **Note list virtualization.** Most of it is done: the main list draws a screenful and the
  rest as the view comes near it, a save redraws one card instead of the list, and the cards are
  drawn on one canvas rather than built from widgets, so a drawn card costs a handful of canvas
  items instead of six windows (see
  ["Large lists: draw what can be seen, the rest on demand"](ARCHITECTURE.md#large-lists-draw-what-can-be-seen-the-rest-on-demand)).
  What is left is true windowed rendering — recycling one screenful of cards, so that a list
  scrolled to its end does not hold every card it passed. At 1,000 notes scrolled to the end,
  coming back to the list measured 81 ms; only worth it if notebooks far beyond that turn up.
- **An Android version.** Nothing decided yet on approach — a full rewrite with a mobile-first
  toolkit, or a port of the existing logic onto something like Kivy or BeeWare, are both on the
  table. This is a big enough undertaking that it needs its own scoping pass before any real work
  starts.
- **Whether to move off plain Tkinter entirely**, decided together with the Android question above
  rather than separately — the two are linked, since a cross-platform-friendly choice could mean
  rewriting the UI layer once for both desktop and mobile instead of twice. Candidates worth
  weighing when that scoping pass happens:
  - **PyQt / PySide (Qt for Python)** — far more capable widgets out of the box (native rich text
    editing, real tables, more polished look), at the cost of a much steeper learning curve, a
    heavier package, and (for PyQt specifically) a more restrictive license than this project has
    used so far.
  - **CustomTkinter** — a modern-looking skin built on top of Tkinter itself, meaning the bulk of
    the current codebase would still apply; the smallest migration cost of the options here, but
    also the smallest capability jump.
  - **Kivy** — built with touch/mobile in mind, so it's already on the table for the Android
    question specifically; would mean rebuilding the desktop UI too if adopted, not just extending
    it.
  - Doing nothing and staying on plain Tkinter remains a legitimate option — noted here so the
    decision is made deliberately, not by default.

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
(actually routing templates through the Trash stays an
[open candidate](#under-consideration)).

### Splitting the UI into modules

Done, and stopped deliberately rather than out of steam. The data-and-rules layer went first —
fourteen modules under `noteorganizer/core/`, none importing tkinter — and six UI areas now live
in `noteorganizer/ui/` as mixins: the calculator panel, the Settings page, the dialogs and popups,
the calendar, attachments, and — re-measured once it became one drawing — the note list. All the
pure logic went down into `core/` first. `note_organizer.py` is about 19,700 lines — it dipped
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
| `0.82.233` | 2026-09-30 | 82 | 233 | **One** `Fixed`, no `Added`, on a branch stacked straight after `0.82.232` and landing before the same rebuild — a bump of its own for the reason `0.82.232` gave, so the `.exe` built after all of them goes out as `0.82.233`. Counted: show/hide decisions asked whether a widget was on the screen, so a note opened from the Calendar kept the last note's Restore previous (a dead button), title counter and share-code strip — shipped behaviour, reproduced on that route, so it counts. **One** entry for fourteen sites: one mechanism, one fix (`_is_placed`), the rule `0.81.202` applied to three labels repaired by one act. NOT counted: the Settings sections stacking when chosen in the same breath as opening Settings — no route in the app does that, only scripts (`story_look`'s scenes 04 and 05 had photographed it since their first reference; their corrected pictures are `Testing`); the gate's new rule, the qa6 and qa7 checks, story chapter 12 and the six mutants — all `Testing`. |
| `0.83.335` | 2026-10-02 | 83 | 335 | **102** `Fixed` and **one** `Added` (the keyboard folds and opens the note list's groups), on branch 7: nineteen rounds of agents tried to break the app, each aimed at what the round before had changed, and every finding was reproduced with the agent's own probe before it was fixed. Counted: only defects that shipped in 0.82.233 or earlier, one entry per mechanism — where that was in doubt it was measured on 0.82.233 itself (the table header Ctrl+Z gave back one column off: four of six operations, in the Linux image; a bold italic word pasted, and bold pasted inside an italic word, were drawn italic only, and a paste at a bold word's edge inside a 20 pt heading came out at 12 pt, there too). NOT counted: defects introduced and repaired inside the branch, each folded into the entry of the shipped defect it belongs to — the formatting journal's cost, the edge guard refusing an empty line, merged cells losing a colour, the second "Save changes?" beside a template and its bin (and that bin after a Replace), a pause splitting a run of styled deletes, the ring after a wheel turn (and beside an undrawn row), the Custom order offer lost to a second move (and then the older one offered), the strip just outside the list's edge, the day a repeat-off Save left on screen and the left-out date its reload overwrote (and the status words a second autosave then replaced), the series a day saved on its own moved (and, with a field left out, moved anyway at the next save), cells pasted over a selection that went into the table beside it, came in as raw tabs after Ctrl+A or took two Ctrl+Z, and moves by hand that cancel out counted as a new arrangement (and then a new note placed by hand counted for nothing, and then a duplicate or a note restored or nudged into a place counted as placed by hand); a save that only met a left-out field moving "Last updated"; the selection's stop at a drawn table missed with two tables close together and on a first-line table (and select all in a note that begins with a table cut the table out); the summary under the repeat previewing a number the save no longer stores; and two things no one could see: the untracked autosaves a direct save left running, and Escape's silent background error in a rename box (`Testing`). From the eighth round on, many findings were regressions of the round before's own fixes — the line under a note-ending table, the turn-off that waits, the deleted day's Undo around it, the walk that lays the spans, the font tags where a size meets bold — each repaired in the branch and counted nowhere; the deleted day's Undo after a turn-off went through four designs, each broken by the next round, and was simplified back to what 0.82.233 said: the day can't come back. The qa checks, the stories and the mutants — at least 361 named in the commit messages — are `Testing`. |
| `0.83.338` | 2026-10-03 | 83 | 338 | **Three** `Fixed`, no `Added`, on a branch stacked straight after `0.83.335`: the security pass that followed the nineteenth round, aimed at what comes in from outside. All three shipped in `0.83.335` or earlier, so all count. One entry per mechanism, not per site: (1) every JSON reader caught one of the three ways a text turns out unreadable — **one** entry for fourteen readers (the four loaders, six at startup, the share-code decoder, three in the backup import), answered now by one definition, `JSON_UNREADABLE`; (2) `normalize_note` trusted an attachment record's own shape — the display name standing in for the stored one unflattened, and the record kept whole with whatever else it carried, are **one** entry: one choke point, now rebuilding the record from its two names as it already rebuilt a checklist item; (3) the formatted paste cut at its caps without a word. |
| `0.84.338` | 2026-10-03 | 84 | 338 | **One** `Added`, no `Fixed`, on a branch stacked straight after `0.83.338`: dates typed the way people write them and shown day first, asked for while preparing a usability test with pupils, who would write 17.10.2026 and find it left out. Counted **once**, as each formatting phase was: the reader, the field's form, the settling of a short year, the day-first display and the reading of a stored day-first date are one feature. The calendar's Add note writing the stored form past the field's own writer, and a note arriving with a day-first date missing the calendar, are this feature's edges, not shipped defects of their own -- not counted. |
| `0.84.340` | 2026-10-03 | 84 | 340 | **Two** `Fixed`, no `Added`, on two branches stacked after `0.84.338` and released as one, as they land before one rebuild: the light themes' secondary text below WCAG AA (as old as the light themes, so it counts), and the window's horizontal scrollbar shown at every width (as old as the scroll wrapper, so it counts). The note list's move to its own module is `Changed`; the gates, the mutation runner, coverage in CI, the bench, the comments convention and the language gate's prying are `Testing` -- none move the numbers. The 71 contrast pairs still below AA wait for a design decision; they are listed, not fixed, so nothing is counted for them. |
| `0.84.341` | 2026-10-04 | 84 | 341 | One `Fixed`: the hint shown with no templates named "Settings → Manage templates", a section renamed "Templates" when Settings became a list of sections in `0.32.51` -- as old as that rename, so it counts. The qa6 checks (the hint itself, and every "Settings → X" in the code against the real section names) and mutant M01 are `Testing` -- no bump from those. |
| `0.84.357` | 2026-10-07 | 84 | 357 | **Sixteen** `Fixed`, no `Added`: what the owner's first full manual pass over the test plan found on the `0.84.341` `.exe`, on seven stacked branches released as one, as they land before one rebuild. All shipped in `0.84.341` or earlier, so all count, one entry per mechanism: ticks on dark themes; a theme switch saying "Note updated"; a highlight in an open cell; previews drawing a table as bars; copied cells bare in the app; copied cells colourless in Word; size and typeface lost on copy; what goes into a checkbox cell beside its brackets; Enter in a numbered list throwing the view to the top; an emoji landing after a grey hint; the caret left in a box on a click on empty space; copying a long styled note freezing; Show more redrawing every row; unchanged notes skipped on import without asking; the share-code warning naming exports that do not exist; bold and italic from a web page arriving plain. NOT counted — introduced and repaired inside this unreleased work: the nine regressions three read-only reviews found in these fixes (a highlight lost when a note was left with its cell open, a copied header read one letter off, ticked rows unreadable after a theme switch, a table cell left open by a click on empty space, Show more after a delete, and four smaller), and the import questions counting one batch two ways. The two widenings after them — any road into a checkbox cell, maths kept as words in a preview — complete entries already counted. The qa checks, the story runs and the mutants (T, P, Q, K, A, B, G: 64 in all) are `Testing`. Measured and left as a decision: one very long paragraph is slow in Tk itself (Known limitations). |
| `0.82.232` | 2026-09-30 | 82 | 232 | **Two** `Fixed`, no `Added`, on a branch stacked straight after `0.82.230` and landing before the same rebuild — a bump of its own because `0.82.230` had already been cut in the branch before it, so the `.exe` built after both goes out as `0.82.232`. (1) The calendar as one drawing: counted, because the month's widgets are a mechanism of their own — the list's drawing did not touch them, and either fix would have shipped without the other, the rule `0.82.230` applied to the list and its on-demand drawing. Field-reported: the freeze of `0.82.230` kept the edge with the pointer but left the month standing still until the drag ended. (2) A day's markers drawn black on every theme — shipped since the markers did, found while drawing them, so it counts. NOT counted: the test harness pinning the mouse button (a check-strategy repair; the story's red it explains was the harness's, not the app's), the two new story chapters, the re-aimed mutant and the 28 mutants — all `Testing`. |
| `0.82.230` | 2026-09-30 | 82 | 230 | One `Added` and **seventeen** `Fixed`: three stacked branches released as one, because they land back to back before one rebuild. The `Added` is Custom order — the list arranged by hand, by dragging a card or with Alt+↑/↓ — counted **once**, as each formatting phase was: the drag, the keys and the sort are one feature. The `Fixed`, all shipped in `0.81.213` or earlier, so all count: **eight** from the keyboard-and-dialogs branch (Cancel on a repeating day's save question keeps you there; a question holds the app-wide shortcuts; the keyboard goes back after a question; formatting after a table cell; Ctrl+N and Ctrl+F leave Settings; a popup's button closes it on a second click; the smallest window shows a note; a cancelled backup import cleans up), **five** from the speed branch (the autosave that rebuilt the list; the list drawn on demand; window handlers run once per widget; a picture opens at once; the notes file written in one piece), and **four** from the list branch (the list as one drawing — the field-reported tearing and slow return; a click handing the list the keyboard; the Ends radio's dot on dark themes; the window's edge following the mouse). One entry per mechanism: the drawing and the on-demand drawing are two, because either would have shipped without the other. NOT counted — introduced and repaired inside this unreleased work: the drawing's extent read from Tk's `bbox` (8.6.15 and 8.6.16 pad a rectangle differently, and the Linux image read the list's top as 1); the Select-mode tick column guessed at 17 pixels; the drop line that promised a place across the pinned line or into another group; the dragged card leaving the list's view; the drag's edge scrolling at one fixed, slow step; and the travel story's Romanian failure message. The qa checks, the two new story chapters and the 71 mutants are `Testing`. The window's-edge entry grew inside this work — a second field test called the freeze alone heavy, and Tk's whole-window repaint styles came off too — and stays one entry: one complaint, one mechanism seen from two sides. |
| `0.81.213` | 2026-09-29 | 81 | 213 | **Eleven** `Fixed`, no `Added` — the data half of the 2026-09-29 "try to break it" audit, every one a place where the app moved, merged or removed a user's work from half the evidence, and every one shipped in `0.81.202` or earlier, so all count. One entry per mechanism, not per site: the categories lost at the loader's door (Add, Rename and the backup import — three doors, one rule); the categories lost with settings.json; automatic removal on a resemblance — the startup collapse and a restored backup's Trash skip are **one** entry, the same looser question asked in two places and answered by the one strict signature; Restore previous bringing back only the text; a backup's Update dropping what its copy carried; duplicate ids; the month-end repeat counted per landing; the share code's unchecked version; the double launch deciding its folder twice; the purge deleting what it never copied; and the migration notice's two false sentences. NOT counted: the test runner surviving a hung script, qa1's three fresh apps answering the startup notice, qa7's keyboard walk forcing its preconditions, the three new story chapters and the 27 mutants — all `Testing`. The warning dialogs' filled "Yes" against an Enter that presses "No", seen in a story photograph, is recorded for a person's judgement and moves nothing. |
| `0.81.202` | 2026-09-29 | 81 | 202 | **Two** `Fixed`, no `Added`, shipped as one release because they are the same complaint in two places: the app holding something and not showing it. (1) Every line on a note's card was a label with no wrapping inside a fixed-width sidebar, so anything longer than the card was drawn off its edge and simply not shown — the title, the preview, and the row of marks, which dropped whole tags and left "☑ 1/2" reading as "☑ 1/". Counted as **one** entry although three labels were repaired, by the rule `0.74.169` used for the three surfaces it redrew: one mechanism seen in three places, fixed by one act. Same mechanism `0.73.167` fixed on the Settings page, whose sweep never reached the note list — which is why the fix reuses that release's helper rather than inventing a second way. (2) Settings → Keyboard shortcuts opens by saying "Everything the keyboard can do" and had not held that since `0.81.199`: the note list's keys were bound and on no row of it. A repair rather than an addition, because the page and its promise already existed — what shipped is the promise being kept. **One** entry, not three: the omission is the group, and ↑/↓, Enter/Space and Shift+F10 were left out by the same act. These two were separate branches (`0.81.201` and `0.81.202`) until they were combined into one PR to stay inside the month's CI allowance; combining them also removed a changelog conflict and made the release read as one story. NOT counted: the qa1 overflow check, the qa6 check that reads what a card BINDS and requires each key to be named on the page, four `story_look` scenes, the `--accept` repair beside them (it blessed every picture it had taken, so accepting one screen rewrote sixteen files), and a version number written wrong in a comment (`0.84.198`, a release that does not exist) — all `Testing` and docs. The `Changed` entry about the themed dialogs' keyword handling ships inside this release and moves nothing. |
| `0.81.200` | 2026-09-29 | 81 | 200 | One `Fixed`, no `Added`. The focus restore shipped in `0.81.199` decided from `focus_get()`, which answers `None` whenever the process does not own the desktop foreground — so it read "nothing has the keyboard" in exactly the case where something did, and a list rebuild could pull the keyboard out of the title box. **Counted**, although no `.exe` ever carried it: the exemption in this policy is for a bug introduced and repaired inside the same unreleased branch, and this one left its branch and sat on `main`, where anyone running from source meets it. The qa1 clipboard fix beside it is `Testing` and moves nothing. |
| `0.81.199` | 2026-09-29 | 81 | 199 | One `Added` and one `Fixed` — the register's last two rows. The `Fixed` is C-8: the calendar chip did the wrong thing rather than lacking something, so it is a repair. The `Added` is C-9's keyboard half, counted as **one** entry although it is a focus ring, arrow navigation, Enter and the menu key — they are one feature, in the same way each formatting phase counted once. **Not counted:** a bug I introduced and repaired inside this branch. A third place marks which note is open, surgically, and it still spoke the old scheme's language of thickness 0 and 2 — so it stripped the focus ring off whichever card you left and painted the focused one accent. Found by the Linux image rather than by reading, along with `<App>` not being a keysym on X11 at all, which took every card down there while Windows was green. |
| `0.80.198` | 2026-09-29 | 80 | 198 | Five `Added`, no `Fixed` — the survey's "doing a thing to many notes" group (C-13, C-14, C-17, and the bulk half of C-9). Each is a capability that did not exist: the selection bar could not pin at all, the Share panel could not be filled in a click, the Trash had no bulk gesture but the irreversible one and no way to tell two notes apart, and a note's own menu could not change its category. The Trash counts as **two** because its row calls them "two separable additions" — the tick-and-restore and the hover preview are independently useful. Not counted: a comment claiming a Markdown export, a sibling of C-25's docstring missed by that sweep because it greps as a comment about Markdown rather than as a claim about the formats on offer. **C-9's keyboard half is NOT in this release** and is not counted anywhere: see its register row. |
| `0.76.198` | 2026-09-28 | 76 | 198 | Three `Fixed`, no `Added`. C-15 (the sort and filter are remembered) and C-16 (the day-marker cap explains itself), plus a **third** the pre-flight for C-15 turned up: the guard that keeps the filter selection valid asked `not in CATEGORY_COLORS`, which is true of both type filters — so adding a category in Settings silently reset a "Repeating" filter to All. Pre-existing in the shipped `0.76.195` and measured on the real app with a control before anything changed, so it counts. C-15 is `Fixed` rather than `Added` because the capability was already there twice over on the same panel — the grouping checkbox and the folded groups both persist — and this is the gap between three adjacent controls, not a new preference. |
| `0.76.195` | 2026-09-28 | 76 | 195 | Three `Fixed`, no `Added` — the survey's C-10, C-18 and C-23, all the same shape: a control that already did something and never said what. Counted as `Fixed` rather than `Added` because the capability existed in each case; the hover-label helper in particular has been in the editor since `0.34.51`, where introducing it *was* counted as an `Added`, and this is the gap between two screens rather than a new feature. **C-25 moves neither number**: a docstring, a comment and two lines of project description are documentation, and deleting the dead `_add_row` is `Removed`. |
| `0.76.192` | 2026-09-28 | 76 | 192 | One `Added` and seven `Fixed` — the consistency survey's seven cheap rows (C-11, C-12, C-19, C-20, C-21, C-22, C-24), one entry each. The `Added` is the search box's ✕: no search box in the app had a clear affordance, so it is a capability rather than a repair. The share panel's ✕ is counted inside C-24's `Fixed` instead, because the editor's code area already had one and that row is precisely about the two surfaces disagreeing. **Not counted:** the `<<Paste>>`→autosave binding on the date field. Measured before the change — a pasted date scheduled no save — but the route only exists because the paste menu in this same branch created it, so it is a hazard introduced and repaired unreleased, which the in-branch rule lists rather than counts. Also not counted: the three `qa/README` rules and the vacuous check found while doing it (`Testing`). |
| `0.75.185` | 2026-09-28 | 75 | 185 | One `Fixed`, no `Added`. A paste onto a field still showing its placeholder landed glued to it — the note title and the Calendar's History search, both shipped that way in the `0.75.184` `.exe`, so a pre-existing bug and it counts. Counted as **one** entry although it has two faces on screen (the glued text, and the title's 200-character cap losing thirteen characters to the hint): one mechanism, one missing binding, one fix. Not from a survey row but from the pre-flight sibling sweep for C-11/C-12, which asked which fields already had both a placeholder and a paste menu. The `qa/README` rules and the [story](ISSUES_LOG.md#the-paste-that-landed-on-top-of-the-placeholder) are `Testing`/documentation — neither moves the number. |
| `0.75.184` | 2026-09-26 | 75 | 184 | One `Fixed`, no `Added`. C-6, and the last of the survey's seven destructive findings. Counted as `Fixed` rather than `Changed` — the distinction against `0.75.183`'s folded-in Delete label, which moved no number — because that label was merely incomplete while this actively misinformed: the button that cleans up every duplicate group wore the sidebar's own fill, the ordinary text colour, a smaller font and less padding than the button below it that acts only on what you ticked. Photographed before the change, it did not read as a button at all. Neither button's behaviour changed; both go through one confirming path, so nothing was ever lost for good — what was wrong is what the screen said about which action is the broad one. NOT counted: the five qa2 checks and four mutants, one per dimension the weight can be wrong in (`Testing`); and the before/after screenshots, which are working artefacts rather than shipped files. |
| `0.75.183` | 2026-09-26 | 75 | 183 | Two `Fixed`, no `Added`. C-7, counted as two because they are two mechanisms with two symptoms and two very different reaches. The first: Escape answered none of the small anchored popups — 15+ of them — because the binding sat on a borderless Toplevel that never takes keyboard focus, so the key went to the app window, which had no Escape binding while a popup was open. The binding was always sound; measured by forcing the focus inside a popup, where it closed at once. The second: the bulk Category and Export popups had no Cancel and no close glyph, so leaving without acting meant clicking empty space and trusting it counted. Either one alone answers the report's "the only way out is a click on empty space", which is why they are not folded together the way C-1's question and undo were. NOT counted: `_escape_backs_out` and `_bulk_popup_cancel` (machinery); the `_nested_dropdown` tracking, which exists so Escape closes a nested list without tearing down its host — the breakage the code's own comment records (`Changed`); the twenty-five qa9 checks and five mutants (`Testing`); and the refuted half of the finding, that "none calls focus_set", when the inline rename popup focuses its own field and binds Escape there — corrected in the register, no bullet. |
| `0.75.181` | 2026-09-26 | 75 | 181 | One `Fixed`, no `Added`. C-5: three routes discarded a calendar day's colour or markers with no question and no way back, and the two menu entries that do it sit directly under the entries that create the same thing — a mis-aim by one row was a permanent loss. Counted as one entry although it covers three routes, because it is one act on one kind of thing reached three ways; the same rule that counted the series warnings as one sentence missing from four places. The third route is the palette's own "No color", which the finding did not mention and a sibling sweep found. NOT counted: `_clear_day_markers` and `_undo_day_clear` (the fix's own machinery); the twenty-three qa7 checks and seven mutants (`Testing`); the check that holds the marker popup unchanged, which needed no fix because it already works on a copy and writes only on Save (`Testing`); and the `Changed` entry folded in from `[Unreleased]` — the Delete label naming the whole series — which by policy moves no number. |
| `0.75.180` | 2026-09-25 | 75 | 180 | One `Fixed`, no `Added`. C-3: the Trash retention dropdown saved on the click, so choosing a shorter window destroyed everything the new window had already outlived at the next startup — attachment files deleted from disk with the notes — while the three other permanent deletions on that same screen all warn with `icon="warning", default="no"`. Counted as one entry although it adds both a question and a silence rule, because the silence is what makes the question worth having: a longer window never asks, and neither does a shorter one with nothing old enough to lose. NOT counted: `_trash_cutoff`, `_trash_entry_is_past`, `trash_entries_past_window` and `_retention_loss_warning` (the fix's own machinery — the first three exist so the dialog's count and the purge's deletion are one judgement rather than two that can drift); the thirty-seven qa6 checks and ten mutants (`Testing`); `--all-failures` and the truncation notice in `tools/run_tests.py`, which was printing only the first eight failures and so made two live mutants read as survivors (`Testing`); and seven dead `parent=` arguments found in `settings_page.py`, which `_themed_dialog` has never accepted — reported, not touched, since they are unrelated to this fix. |
| `0.75.179` | 2026-09-25 | 75 | 179 | Two `Fixed`, no `Added`. The first is C-2: a checklist item's bin was the one delete in the app with no route home — Ctrl+Z reaches the Text widgets through `edit_undo` and a checklist is a list of dicts beside them. No confirmation added, deliberately: the register's reason for the comparison turned out to be wrong (it said the removed attachment is one "the file system still remembers", and `remove_attachment` deletes the stored copy), so the attachment's warning is right for an irreversible act and the checklist's answer is to become recoverable instead. The second was found by probing the first and is counted separately because it is a different mechanism with a different symptom, on older ground: a plain toast replaces `_toast_action` with `None`, so the autosave's own "Note updated" wiped whatever Undo had just been offered — about a second, not the eight the banner appeared to promise. It counted even though it also repairs the category offer from `0.75.177` two rows above, which would fall under the introduced-and-fixed-unreleased rule on its own, because the same wipe took the trash and occurrence offers that shipped in the `0.75.173` build and did reach a user. NOT counted: `_undo_checklist_delete` and the `yield_to_action` parameter (the fix's own machinery); the thirty-three qa1 checks and nine mutants (`Testing`); the corrected register cell, the ISSUES_LOG story, the qa/README house rule and the test-plan rows (docs). |
| `0.75.177` | 2026-09-25 | 75 | 177 | One `Fixed`, no `Added`. The bulk category change was the only action in the selection bar that rewrote stored data with neither a question nor a way back, while `🗑 Trash` beside it had both — found by the consistency survey rather than in the field, and recorded as C-1. Counted as one entry although it adds two things, because they are two halves of one promise: the app's own rule is that a destructive action is confirmed in proportion to how recoverable it is, and neither half satisfies it alone. The reason it got the question as well as the toast is that the neighbour's real safety net is the thirty days the note then spends in the Trash — the toast is a convenience on top — whereas a category undo lasts eight seconds and then the old filing is gone from the file. NOT counted: `_undo_bulk_category` and `_category_override_warning` (the fix's own machinery, not separate bullets); the per-note marks carrying `updated` as well as `category`, which is how the one bullet is true of a mixed selection rather than only of a uniform one; the thirty-six qa1 checks and the ten mutants (`Testing`); and the ISSUES_LOG story, the register's status cell and the six test-plan rows (docs). |
| `0.75.176` | 2026-09-25 | 75 | 176 | Three `Fixed`, no `Added`, all in the calendar and all field-reported in one sitting. Two of them are about previews: one drew itself OVER the right-click menu the user had just opened (a menu keeps the event loop running under it, so the hover never stopped firing), and one showed a note's tables as raw vertical bars in both calendar previews — the panel filtered them with the EDITOR's strict rule, so a row typed past its last cell was neither counted nor stripped, and the small hover preview filtered nothing at all and never even said a table was there. The third: Field-reported as “two delete systems in the calendar”, and the report was right about the symptom and not about the cause: the menu it named is not a delete system but the note's whole actions menu, seven entries deep. The real fault was that the app already HAS a rule — a list of notes offers its actions by right-click and carries no button (the sidebar cards), a labelled Delete appears only where a single note is open (the editor) — and the calendar was the one screen breaking it, in both directions at once: its day list carried the only per-row note delete in the app, and its note preview was the only note surface with no right-click menu, which cost six actions besides Delete. Counted as one entry because it is one rule broken in one screen, the same way the series warnings counted as one sentence missing from four places. NOT counted: removing the per-row glyph (`Changed`) and the seven qa7 checks (`Testing`). |
| `0.75.173` | 2026-09-15 | 75 | 173 | One `Added` and three `Fixed`, all in the selection bar's neighbourhood and all field-reported. The `Added` is “Select all” turning into “Unselect all” once everything on screen is selected — a mis-aimed press used to cost the whole selection mode, since nothing else released a selection in one gesture. The `Fixed` are: selecting or unselecting every note redrawing the whole list to move a tick (140 widgets, ~170ms a press, and twice as often once the button could also let go); the bar's last action being cut off (“Export” drawn 13px short of what it asked on Windows, and at ONE pixel on the Linux image, where the fonts are wider and the same four controls ask 338px of the 250 available), and a check mark's well being set to the surface the box sits on, so on every dark theme a ticked box looked untouched — twelve widgets shared that one. NOT counted: the `check_well` palette entry, the two-by-two layout and the one-definition `_visible_note_ids` (`Changed`); the seven mutants, the width probe and the three existing checks repaired for naming the old colour (`Testing`); and a wrong first diagnosis of the tick boxes, built on a fixture that ticked nothing, which shipped nothing because a screenshot was asked for before the commit. |
| `0.74.170` | 2026-09-15 | 74 | 170 | One `Fixed`, no `Added`. A repeating series is one note in every list and every count, and deleting it takes every occurrence — but only the single-note delete said so. The bulk move to trash and both permanent deletes in the Trash called it “a note”, and the Trash listed it like any other. Counted because it is user-visible, shipped and field-reported, and because two thirds of it is irreversible. One entry, not four: the same sentence was missing from four places, and it is now written once. NOT counted: `is_recurring` raising on a recurrence field holding a string — real, but unreachable before this branch, since live notes are normalised on load and nothing had ever asked a TRASH entry (which is not) whether it repeats; the Restore/Delete buttons being squeezed, whose pack-order flaw is older but which only became visible when this branch gave the row a longer line; and the taller Trash list, which is `Changed`. The thirty-one checks and eight mutants are `Testing`. |
| `0.74.169` | 2026-09-15 | 74 | 169 | One `Fixed`, no `Added`. Deleting a note redrew the whole screen — 264 widgets, ~185ms — and two of the three things it rebuilt were not on screen at all. Counted because it is user-visible and shipped: reported from the field as “the picture breaks a little and rebuilds itself”. One entry rather than three, because the calendar, the statistics and the list are the same mechanism seen in three places: work done unconditionally on a data change for a surface nobody is looking at. NOT counted: the stale calendar after leaving Settings, which was introduced and closed inside this branch (found by listing the four routes back to the calendar rather than trusting that a mechanism existed); and the eighteen checks with their eight mutants, which are `Testing`. The repaired qa7 check is `Testing` too — it was passing on timing, not on its subject, and only the speed-up exposed it. |
| `0.74.168` | 2026-09-15 | 74 | 168 | One `Added` and one `Fixed`. The `Added` is Undo on the delete banner, counted as one entry the way each formatting phase was: the three delete routes (a note, several at once, one day of a repeating note) are one feature reached three ways, not three features. The `Fixed` is the banner opening with a tick of success whatever it had to say, so a failed disk write announced itself as “✓ Something went wrong with that” — pre-existing, shipped and user-visible, so it counts. NOT counted: the wording of the banner's own new text (“note(s)” → “notes”), which was written and corrected inside this branch without shipping in between; and the twenty-two qa checks with their thirteen mutants, which are `Testing`. Worth recording for the next cycle: a field report during this work (“the picture breaks a little and rebuilds itself when I delete”) was measured to be the note-list rebuild — 169 widgets, 129ms, identical with the banner removed entirely — so it belongs to the theme-switch flicker's class, not to this feature. |
| `0.73.167` | 2026-09-15 | 73 | 167 | One `Fixed`, no `Added`. The explanatory line under every Settings title was drawn wider than the label that held it, so each sentence stopped mid-word with nothing to say it had been cut -- three of them, by 51, 57 and up to 69 pixels. Counted because it is user-visible and shipped. The mechanism is one class, not three instances: every wrapping width in that page was a hand-picked number standing in for padding the label cannot see, and the panel's own `padx=48` a side made every guess short. Found by photographing the app for the documentation gallery, not by any check -- and the measurement that located it took three attempts, two of which asked the wrong question. |
| `0.73.166` | 2026-09-14 | 73 | 166 | One `Fixed`, no `Added`. A bulk category change was undone on whichever note was open in the editor, by the editor's own next save -- the same class as the import route's, fixed a day earlier, and now sharing its helper. Counted because it is user-visible and silent: the notes nobody had open kept the new category, so the one that reverted looked like a mistake the user had made. Found by `qa/story_audit.py`, which walks shapes the suite cannot express (a restart, a sequence, a second visit, a what-happens-next) over surfaces nobody had walked that way. NOT counted: nine of that audit's first ten flags, which were faults in the audit itself and are written into it.

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
submission requirements) is documented separately, since it's not decided or in progress and
doesn't belong mixed into the numbering policy above:

- [`docs/RELEASE_WINDOWS.md`](RELEASE_WINDOWS.md) — Microsoft Store (MSIX) and alternative Windows
  distribution channels.
- [`docs/RELEASE_ANDROID.md`](RELEASE_ANDROID.md) — exploratory only, kept ready for if an Android
  release is ever scoped; not current work (see
  [Explicitly not planned right now](#explicitly-not-planned-right-now) and `CLAUDE.md`'s Project
  focus).

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

**Audit residuals (2026-09-10)** — the code-audit programme (see
[Shipped & settled](#the-code-audit-programme-2026-09)) closed every finding that warranted code;
what follows is what it deliberately left as recorded edges rather than fixes. None is an open
bug being chased.

- *Straggler-pass colour collisions* — `_recolor_stragglers` remaps any widget colour matching
  another theme's palette hex, so a data-driven colour that happens to equal one (e.g. `#7c5cff`
  as both the accent and a category colour) can be swapped on widgets outside the note cards
  (which re-fix themselves afterwards, deliberately). Whitelisting data colours would be
  architectural; the exposure is cosmetic and theme-pair-specific.
- *A second full grid rebuild after a push-down* — a diagnostic-confidence finding about
  `_align_table_on_leaving` re-rendering redundantly (a late echo/flicker); needs a pixel-level
  investigation before any fix is trusted.
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
- *Zip-import overlap has no end-to-end test* — the re-import-your-own-backup attachment remap
  is unit-covered through its shared helper and review-verified end to end; a full GUI round-trip
  check remains worth writing.

**Break-it residuals (2026-10)** — nineteen rounds of agents tried to break the app (see the
[Changelog](../CHANGELOG.md)); what they measured and the fixes deliberately left is recorded
here. None is a bug being chased; each has a reason.

- *A view left deep in a very long list* — a rebuild still draws every row above the view
  (about 1–1.3 s at 5,000 notes for Select mode, Undo or a restore), because the drawing is a
  prefix of the rows by design. The keyboard coming back to the list joins it: when the ring's
  card was carried far below what the list had drawn (grouping turned on, the sort changed), Tab
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
- *A day's own text on a day the series no longer has* — changing a series' start date or its
  rule can leave a day's own text (saved "only this occurrence") on a date the new schedule never
  reaches. It stays in the file, so nothing is lost, but the calendar no longer shows it. Older
  than the rounds; whether to move it, ask, or keep it findable is a product decision, on the
  owner's list.
- *Note ids* — an id freed by a delete can be given to the next new note (ids are max + 1). Every
  holder of an id across a delete was checked and acts on the note it means; the one left is a
  keyboard ring that can land on the new note, which is a cursor, not an action.
- *A category move's Undo after a rename* — renaming the category the notes were moved into, or
  deleting the one they came from, while the Undo is on offer makes the Undo say "Nothing left
  to put back" with the notes still moved. Nothing is lost; whether the Undo should follow the
  rename or be withdrawn with it is a product decision, on the owner's list.
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
