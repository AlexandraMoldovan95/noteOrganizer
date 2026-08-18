# Roadmap

Planned work and open ideas, roughly ordered by how soon they're likely to happen. Nothing here is a promise or a deadline — this is a working list for a project developed in spare time by a small team of two.

## Known bugs to investigate

Found by hand, not yet worked on. Grouped by area.

**Note list**
- Dragging the scrollbar with only a few notes in the list causes visible flicker and adds unexplained spacing between the top bar and the first note's title. Doesn't happen with a longer list — worth checking whether this is related to the scrollregion calculation only being "exercised" enough to self-correct once there's enough content to actually need scrolling.
- Grouping by category: after expanding the last (previously collapsed) group, editing a note inside it (which autosaves), then collapsing that group again, the note list's scroll position sometimes jumps back to the top instead of staying near where that group was. Hard to reproduce consistently — needs a closer look at what specifically triggers it.

**Settings**
- Layout: each section's title is left-aligned, but the action buttons are centered — inconsistent, makes the page harder to scan at a glance ("eye slalom"). Worth a proper design pass, not just a quick alignment fix — see "Settings redesign" below, this is likely folded into that.

## Settings redesign (bigger discussion, own design pass)

The current single-column Settings page makes for a lot of scrolling and doesn't clearly separate "which section am I in" from "what are this section's controls." Considering a restructure closer to how Chrome (and similar apps) lay out settings: a narrow column on the left listing every section, and the actual controls for whichever section is selected on the right, with empty space beyond that rather than everything stretched full-width. Not yet decided whether Settings should become an inline popup/modal (opened from the editor or calendar, floating over the app) or stay as a page of its own — worth a dedicated conversation before building anything, since it affects more than just this list of small alignment fixes above.

## Versioning

### Right now: pre-1.0.0

Keep the first number at `0` until the app actually has a real public launch, so `1.0.0` stays meaningful (a clean first release, not used up early).

Until then, the other two numbers are **cumulative all-time totals**, not per-release counts — `MAJOR.<total Added entries ever>.<total Fixed entries ever>`, counted from `CHANGELOG.md`'s `Fixed` and `Added` sections only (across every version section, `[Unreleased]` included). `Changed`, `Testing`, and `Removed` entries don't count — they're neither a shipped fix nor a shipped feature. `docs/ROADMAP.md`'s own "known bugs"/"under consideration" items don't count either, since they're not done yet, and `docs/ISSUES_LOG.md` entries aren't counted separately since they're narrative write-ups of fixes already counted in `CHANGELOG.md` — counting both would double-count the same work.

Bump the version, and cut `CHANGELOG.md`'s `[Unreleased]` section into that new version number (with today's date), every time `note_organizer.py` changes and the app gets rebuilt for real use — the same moment a `.exe` rebuild is already called for. Docs-only changes don't move the version, same as they don't call for a rebuild. If several small PRs land back-to-back before the next rebuild, they share one bump — the trigger is "about to rebuild," not "one bump per PR."

This exists specifically because `APP_VERSION` drives two real things in the code: the backup-before-upgrade safety net in `load_notes()`, and the "Updated to version X" startup banner (`detect_version_change()`) — both only fire when this number actually changes. Recorded history: `0.28.38` (2026-08-17) — 28 Added + 38 Fixed entries across `0.1.0` through the batch of work that included the Statistics read-only/live-update fix; `0.30.38` (2026-08-18) — 30 Added + 38 Fixed, adding the in-note calculator; `0.30.39` (2026-08-18) — 30 Added + 39 Fixed, fixing the AppData-notes-deleted-by-purge_stale_copies bug; `0.31.39` (2026-08-18) — 31 Added + 39 Fixed, adding Phase 1 of rich text formatting.

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

- **Rich text formatting, continued.** Phase 1 shipped in `0.31.39`: a Bold/Italic/Underline/Strikethrough toolbar and right-click menu, with keyboard shortcuts, applying either to a selection or to whatever's typed next. Still ahead: font size, font family, text color, highlight color, bullet lists, and paste that preserves (or discards) source formatting — the last of these is also a prerequisite for the table feature below, which needs to accept a pasted table, not just plain text.
- **A simple table feature** for structured content within a note.
- **Note list virtualization.** The main note list currently builds a full widget per note on every refresh. Trash and the Share panel already cap what they render up front (see [ARCHITECTURE.md](ARCHITECTURE.md)); doing the same for the main list — or true windowed rendering, building only the cards currently scrolled into view — would help further at very large note counts (many hundreds to thousands).
- **Reorganize the codebase into multiple files/modules**, once the single-file layout starts costing more in navigation than it saves in simplicity.

## Exploratory / long-term

- **An Android version.** Nothing decided yet on approach — a full rewrite with a mobile-first toolkit, or a port of the existing logic onto something like Kivy or BeeWare, are both on the table. This is a big enough undertaking that it needs its own scoping pass before any real work starts.
- **Whether to move off plain Tkinter entirely**, decided together with the Android question above rather than separately — the two are linked, since a cross-platform-friendly choice could mean rewriting the UI layer once for both desktop and mobile instead of twice. Candidates worth weighing when that scoping pass happens:
  - **PyQt / PySide (Qt for Python)** — far more capable widgets out of the box (native rich text editing, real tables, more polished look), at the cost of a much steeper learning curve, a heavier package, and (for PyQt specifically) a more restrictive license than this project has used so far.
  - **CustomTkinter** — a modern-looking skin built on top of Tkinter itself, meaning the bulk of the current codebase would still apply; the smallest migration cost of the options here, but also the smallest capability jump.
  - **Kivy** — built with touch/mobile in mind, so it's already on the table for the Android question specifically; would mean rebuilding the desktop UI too if adopted, not just extending it.
  - Doing nothing and staying on plain Tkinter remains a legitimate option — noted here so the decision is made deliberately, not by default.

## Explicitly not planned right now

- Tags as a separate feature from categories — removed in 0.3.0 after concluding categories cover the need on their own; revisiting this isn't currently planned.
- Cloud sync / accounts — the app is intentionally offline-only.
