# Roadmap

What's planned, what was decided against, what already shipped and settled, how versions are
counted, and the standing constraints. Nothing here is a promise or a deadline — this is a working
list for a project developed in spare time by a small team of two.

- [Under consideration](#under-consideration)
- [Explicitly not planned right now](#explicitly-not-planned-right-now)
- [Shipped & settled](#shipped--settled)
- [Versioning](#versioning)
- [Known limitations](#known-limitations)

## Under consideration

Genuinely open ideas, roughly ordered by how soon they're likely to happen.

- **Small candidates from the 2026-08-31 idea pass** (put aside deliberately, in rough order of
  appeal; the keyboard-shortcuts candidate from that pass has since shipped — see
  [Global keyboard shortcuts](#global-keyboard-shortcuts)):
  - **Undo on the delete toast** — moving a note to the Trash could offer a one-click Undo right
    on the confirmation toast, instead of the trip through Settings → Recently deleted.
  - **Import a .md/.html file as a note** — the reverse of the single-note export; `html_to_note`
    already exists, and a Markdown file's tables/checkboxes are already the note format.
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
- **"Export as PDF" via Edge headless** — phase 2 of the single-note export:
  `msedge --headless --print-to-pdf` exists on every Windows 10/11, no Python dependency; needs an
  honest fallback ("saved as HTML, open it and Ctrl+P") for machines where Edge is missing or
  changes flags.
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
- **Note list virtualization.** The main note list currently builds a full widget per note on
  every refresh. Trash and the Share panel already cap what they render up front (see
  ["Large lists: paginate, don't virtualize (yet)"](ARCHITECTURE.md#large-lists-paginate-dont-virtualize-yet));
  doing the same for the main list — or true windowed rendering, building only the cards currently
  scrolled into view — would help further at very large note counts (many hundreds to thousands).
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
thirteen modules under `noteorganizer/core/`, none importing tkinter — and five UI areas now live
in `noteorganizer/ui/` as mixins: the calculator panel, the Settings page, the dialogs and popups,
the calendar, and attachments. All the pure logic went down into `core/` first.
`note_organizer.py` is about 13,250 lines — it dipped when the extractions landed and has grown
again through the rich-text, tables and field-testing work, but the pure logic behind all of that
went into `core/` rather than into it, which is the point: the entry file is a UI hub, not a junk
drawer.

The stopping point is a measurement, not fatigue. The seams were measured from the call graph and
nothing else clears the bar — the note list keeps 41% of its calls to itself, sharing 33%,
open-note tabs 26%, and the editor 17%. The editor barely moved across three extractions, which is
the clearest evidence that it is the hub the class turns around rather than a module waiting
inside it. What remains in the entry file is genuinely shared surface — the note list, the
open-note tabs and the editor all call heavily into each other — and moving any of it into a file
would relocate the tangle rather than remove it. The full method-by-method analysis lives in
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
