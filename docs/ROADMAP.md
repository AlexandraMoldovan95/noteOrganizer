# Roadmap

Planned work and open ideas, roughly ordered by how soon they're likely to happen. Nothing here is a promise or a deadline — this is a working list for a project developed in spare time by a small team of two.

## Known bugs to investigate

Found by hand, not yet worked on. Grouped by area.

**Note list**
- Dragging the scrollbar with only a few notes in the list causes visible flicker and adds unexplained spacing between the top bar and the first note's title. Doesn't happen with a longer list — worth checking whether this is related to the scrollregion calculation only being "exercised" enough to self-correct once there's enough content to actually need scrolling.
- Grouping by category: after expanding the last (previously collapsed) group, editing a note inside it (which autosaves), then collapsing that group again, the note list's scroll position sometimes jumps back to the top instead of staying near where that group was. Hard to reproduce consistently — needs a closer look at what specifically triggers it.

**Theming**
- Theme switching was ~140ms and visibly flickered; it's now ~26ms and no longer rebuilds anything that didn't change (fixed in 0.32.49). What remains is much smaller and is a plain-Tkinter limitation rather than something this codebase controls: each widget is its own OS window that Windows repaints as soon as its colour is set, so a very brief partial repaint is still possible. See `docs/ISSUES_LOG.md`, "The theme-switch flicker, and three ways not to fix it", before attempting anything further — three approaches were tried and reverted, and the reasons they can't work are recorded there.

## Settings redesign — shipped

Settings is now a list of sections on the left and one open section on the
right, grouped under General / Content / Data / More. The questions this
section used to hold open were answered in the building:

- **Page, not a popup.** Nine settings-related actions open popups of their
  own (the template editor opens nine on its own), and `qa/qa9.py` exists
  because a nested-dropdown-inside-a-popup already broke once. Putting the
  whole of Settings inside a modal would have stacked another layer on that.
- **Flat list, then grouped.** It shipped flat and was grouped shortly
  after: nine entries in one run mixed four different kinds of thing —
  preferences, managers for content you made, tools that delete things, and
  read-only information.
- **The nav does not shrink on a narrow window.** It was built to, and the
  breakpoint could never fire: the app holds its whole content area to at
  least `SIDEBAR_WIDTH + EDITOR_MIN_WIDTH` (900px) and scrolls horizontally
  below that rather than reflowing, so the Settings pane never gets narrow
  enough. The dead code was removed and the reason recorded in
  `settings_page.py`.

Still open, in rough order of value:

- **A "last exported" line in Backup.** The app is offline by design, so an
  export is the only copy of the notes that is not in the app's own folder,
  and nothing currently says when one last happened. One settings key.
- **Trash retention is not configurable**, though `USER_GUIDE.md` says it
  is. `TRASH_RETENTION_DAYS = 30` is a constant. Either make the sentence
  true or make the setting real.
- **No keyboard-shortcut reference.** Thirteen shortcuts are bound and only
  the formatting ones are discoverable, via the right-click menu.
- **Template deletion is permanent and unlabelled as such** — templates are
  not routed through Trash like everything else.

## Versioning

### Right now: pre-1.0.0

Keep the first number at `0` until the app actually has a real public launch, so `1.0.0` stays meaningful (a clean first release, not used up early).

Until then, the other two numbers are **cumulative all-time totals**, not per-release counts — `MAJOR.<total Added entries ever>.<total Fixed entries ever>`, counted from `CHANGELOG.md`'s `Fixed` and `Added` sections only (across every version section, `[Unreleased]` included). `Changed`, `Testing`, and `Removed` entries don't count — they're neither a shipped fix nor a shipped feature. `docs/ROADMAP.md`'s own "known bugs"/"under consideration" items don't count either, since they're not done yet, and `docs/ISSUES_LOG.md` entries aren't counted separately since they're narrative write-ups of fixes already counted in `CHANGELOG.md` — counting both would double-count the same work.

Bump the version, and cut `CHANGELOG.md`'s `[Unreleased]` section into that new version number (with today's date), every time `note_organizer.py` changes and the app gets rebuilt for real use — the same moment a `.exe` rebuild is already called for. Docs-only changes don't move the version, same as they don't call for a rebuild. If several small PRs land back-to-back before the next rebuild, they share one bump — the trigger is "about to rebuild," not "one bump per PR."

This exists specifically because `APP_VERSION` drives two real things in the code: the backup-before-upgrade safety net in `load_notes()`, and the "Updated to version X" startup banner (`detect_version_change()`) — both only fire when this number actually changes. Recorded history: `0.28.38` (2026-08-17) — 28 Added + 38 Fixed entries across `0.1.0` through the batch of work that included the Statistics read-only/live-update fix; `0.30.38` (2026-08-18) — 30 Added + 38 Fixed, adding the in-note calculator; `0.30.39` (2026-08-18) — 30 Added + 39 Fixed, fixing the AppData-notes-deleted-by-purge_stale_copies bug; `0.31.39` (2026-08-18) — 31 Added + 39 Fixed, adding Phase 1 of rich text formatting; `0.32.44` (2026-08-19) — 32 Added + 44 Fixed, adding Phase 2a (text color + highlight) plus five selection/rendering fixes found while building it; `0.32.49` (2026-08-20) — 32 Added + 49 Fixed, the multi-line highlight bleed, right-click menu alignment, comments-box selection, the note-colour clobbering bug, and the theme-switch flicker/performance work (the numpy build change is a `Changed` entry, so it doesn't move the number); `0.32.51` (2026-08-21) — 32 Added + 51 Fixed, the Settings storage path and first-launch date reading from a second, uninitialised copy of the entry module, and the category-delete dialog calling a soft delete permanent (the Settings redesign itself, the notes-storage move and the visual pass are all `Changed` entries, so they don't move the number); `0.34.51` (2026-08-25) — 34 Added + 51 Fixed, adding paragraph formatting as one `Added` entry covering lists, nesting, indentation, alignment and quote blocks together, the same way Phase 1 counted four character styles as one, plus a second entry for the formatting toolbar's hover labels; `0.35.51` (2026-08-25) — 35 Added + 51 Fixed, adding font size and family as one `Added` entry (the composite-tag scheme behind it, and the list margin now scaling with the font size, are `Changed` entries and do not move the number) (the `paragraphs` note field is a `Changed` entry, and the two bugs found while building it were introduced in the same unreleased branch, so neither moves the Fixed count); `0.36.54` (2026-08-25) — 36 Added + 54 Fixed, adding the reading-time estimate, and fixing the Settings information bars on light themes, the formatting toolbar overflowing the editor pane, and the Settings section list not scrolling (removing the quote block is a `Removed` entry, so it does not move either number); `0.36.55` (2026-08-25) — 36 Added + 55 Fixed, capping the note title at 200 characters after measuring tk.Entry slow to 3.5 seconds a keystroke at 100,000; `0.36.56` (2026-08-25) — 36 Added + 56 Fixed, taking the raw hex code off the note colour label; `0.37.56` (2026-08-26) — 37 Added + 56 Fixed, adding paste and copy that keep formatting (the clipboard and conversion modules behind them are a `Changed` entry); `0.38.56` (2026-08-26) — 38 Added + 56 Fixed, adding the expandable writing area (the `Testing` entry beside it does not count); `0.38.59` (2026-08-26) — 38 Added + 59 Fixed, fixing the text boxes stuck at eighty characters, paste from a PDF losing its paragraphs, and numbered lists counting the blank lines between their items (the mid-sentence split was introduced and fixed inside the same unreleased branch, so it does not count).

### At the real launch: 1.0.0 and after

The version becomes exactly `1.0.0` at the actual public release, regardless of whatever cumulative number it reached beforehand (even `0.150.320` or similar) — the pre-1.0 scheme is explicitly a development-phase convention, not something that carries forward. From `1.0.0` on, standard [Semantic Versioning](https://semver.org/) takes over, and **each number resets to 0 at the release above it** — no more cumulative totals:

- **PATCH** (`1.0.x`) — a release containing only bug fixes, no new features.
- **MINOR** (`1.x.0`) — a release that includes at least one new feature; patch resets to `0`.
- **MAJOR** (`x.0.0`) — reserved for something big enough to warrant it: a real redesign, a breaking data-format change, a genuinely new "generation" of the app. Rare; minor and patch both reset to `0`.

### Platform-specific packaging/publishing

This section is only about the app's own `APP_VERSION`/`CHANGELOG.md` numbering — how a build actually gets packaged and published on a given platform (store-specific package versions, submission requirements) is documented separately, since it's not decided or in progress and doesn't belong mixed into the numbering policy above:

- [`docs/RELEASE_WINDOWS.md`](RELEASE_WINDOWS.md) — Microsoft Store (MSIX) and alternative Windows distribution channels.
- [`docs/RELEASE_ANDROID.md`](RELEASE_ANDROID.md) — exploratory only, kept ready for if an Android release is ever scoped; not current work (see "Exploratory / long-term" below and `CLAUDE.md`'s Project focus).

## Under consideration

- **Rich text formatting, continued.** Phase 1 shipped in `0.31.39`: a Bold/Italic/Underline/Strikethrough toolbar and right-click menu, with keyboard shortcuts, applying either to a selection or to whatever's typed next. Phase 2a shipped in `0.32.44`: text color and highlight, added to the same toolbar with swatch-style pickers (no hex-code entry — see `CHANGELOG.md`). Phase 2b shipped in `0.34.51`: paragraph formatting — bullet and numbered lists with multilevel nesting, indentation and alignment (see `CHANGELOG.md` for why numbered levels are not lettered). Quote blocks shipped with it and were removed again in `0.36.54`. Phase 3 shipped in `0.35.51`: font size and family, per selection and as an app-wide default. Phase 4 shipped in `0.37.56`: paste that keeps its source formatting, with Ctrl+Shift+V for plain text, and copy that carries formatting out. **Rich text formatting is complete.** The table feature below now has the prerequisite it was waiting on — a pasted table arrives as HTML, and `core/richtext.py` is where its `<table>` would be understood.
- **A simple table feature** for structured content within a note.
- **Note list virtualization.** The main note list currently builds a full widget per note on every refresh. Trash and the Share panel already cap what they render up front (see [ARCHITECTURE.md](ARCHITECTURE.md)); doing the same for the main list — or true windowed rendering, building only the cards currently scrolled into view — would help further at very large note counts (many hundreds to thousands).
- **Split the UI into modules.** The data and rules layer is done — twelve modules under `noteorganizer/core/`, none importing tkinter (see [ARCHITECTURE.md](ARCHITECTURE.md)). **Split the UI into modules — done.** Five areas now live in `noteorganizer/ui/` as mixins: the calculator panel, the Settings page, the dialogs and popups, the calendar, and attachments. All the pure logic went down into `noteorganizer/core/` first. `note_organizer.py` is about 7,790 lines, from 11,147 when the reorganisation began — it has grown again since, with the rich-text work, but the pure logic behind that went into `core/` rather than into it.

It stopped there deliberately rather than running out of steam. The seams were measured from the call graph (see [ARCHITECTURE.md](ARCHITECTURE.md)) and nothing else clears the bar — the note list keeps 41% of its calls to itself, sharing 33%, open-note tabs 26%, and the editor 17%. The editor barely moved across three extractions, which is the clearest evidence that it is the hub the class turns around rather than a module waiting inside it. What remains is roughly 4,300 lines of genuinely shared surface, and moving any of it into a file would relocate the tangle rather than remove it.

If the UI is ever rebuilt on a different toolkit, that is the moment to revisit this — not before.
- **An Android version.** Nothing decided yet on approach — a full rewrite with a mobile-first toolkit, or a port of the existing logic onto something like Kivy or BeeWare, are both on the table. This is a big enough undertaking that it needs its own scoping pass before any real work starts.
- **Whether to move off plain Tkinter entirely**, decided together with the Android question above rather than separately — the two are linked, since a cross-platform-friendly choice could mean rewriting the UI layer once for both desktop and mobile instead of twice. Candidates worth weighing when that scoping pass happens:
  - **PyQt / PySide (Qt for Python)** — far more capable widgets out of the box (native rich text editing, real tables, more polished look), at the cost of a much steeper learning curve, a heavier package, and (for PyQt specifically) a more restrictive license than this project has used so far.
  - **CustomTkinter** — a modern-looking skin built on top of Tkinter itself, meaning the bulk of the current codebase would still apply; the smallest migration cost of the options here, but also the smallest capability jump.
  - **Kivy** — built with touch/mobile in mind, so it's already on the table for the Android question specifically; would mean rebuilding the desktop UI too if adopted, not just extending it.
  - Doing nothing and staying on plain Tkinter remains a legitimate option — noted here so the decision is made deliberately, not by default.

## Explicitly not planned right now

- Tags as a separate feature from categories — removed in 0.3.0 after concluding categories cover the need on their own; revisiting this isn't currently planned.
- Cloud sync / accounts — the app is intentionally offline-only.
