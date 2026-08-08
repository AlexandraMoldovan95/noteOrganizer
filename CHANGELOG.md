# Changelog

All notable changes to Note Organizer are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Version numbers below are retrospective groupings of related work — this project didn't tag formal releases from day one, so early history is grouped by theme rather than exact date.

---

## [Unreleased]

### Fixed
- Attachment files were never actually deleted from disk — removing an attachment from a note, permanently deleting a trashed note (individually, via "Empty trash", or through automatic purge after the retention window) all removed the note/reference but left the underlying file behind indefinitely. All four paths now clean up the physical file too. Moving a note to trash (the reversible, soft-delete path) correctly still leaves files untouched, since the note might be restored.
- Calendar keyboard navigation (PgUp/PgDn/Home) and the resize-driven font relayout could still act on the calendar while it was hidden behind the new Settings page, if Calendar had been the last-selected tab before opening Settings — silently changing the visible month behind the scenes. Both now check that the calendar is actually on screen, not just that it's the notebook's internally "selected" tab.
- Importing a single-note share code (as opposed to a multi-note one) skipped the duplicate check entirely and went straight to opening it for editing — found by hand, by copying a code from a note already present and re-importing it. Now checks for an exact match first and asks before opening it, same as the multi-note path.
- The calendar day panel's delete actions (including the pre-existing right-click menu one) refreshed the panel unconditionally after being clicked — including when the user canceled the confirmation dialog, which incorrectly bounced the view back to the day's note list instead of leaving it exactly as it was. Now only refreshes if the note actually stopped occurring on that date.

### Added
- Project documentation set (`README.md`, this changelog, architecture notes, roadmap, issues log)
- Git version control, hosted on GitHub
- Continuous integration via GitHub Actions (`.github/workflows/tests.yml`): the full automated test suite now runs on every push and Pull Request.
- Delete a note directly from the calendar day panel — a small trash icon on each row in a day's note list, and a Delete button on the note-detail view reached from there. Reuses the same confirmation and recurring-series-scope prompts as deleting from anywhere else, so nothing about safety changes; it just no longer requires opening the full editor first.

### Changed
- Settings moved out of the Notes/Calendar tab strip entirely, into its own button in the sidebar (alongside New Note / Import / Share), with a "← Back to Notes" button to return. Originally planned as "push it to the far right of the tab strip" (see ROADMAP), but that risked sitting too close to the window's own close button — the sidebar button avoids that concern and tested better in practice.
- The note editor's "📋 Copy code" button renamed to "📋 Generate code" — nothing has been generated or copied to the clipboard yet at the point it's clicked, which "Copy" implied. Matches the wording already used by the multi-note Share panel's equivalent button.

### Testing
- Two of the five automated QA scripts (`qa3.py`, `qa4.py`) still referenced the Settings page's old, removed notebook-tab index, and had been silently passing for the wrong reason (their own exit code was never actually checked, so a script erroring out still reported as a successful test run). Both issues are fixed: the scripts now call `show_settings_page()` directly, and every test script exits with a real failure status when a check fails, which is what makes the new CI integration meaningful rather than always green.
- Added `qa6.py`: automated coverage for category grouping (collapse state and persistence), Settings (username greeting, statistics navigation), attachments through the actual UI functions (not just the file-cleanup fix), several multi-feature combination scenarios, and the parts of window layout that have a real right/wrong answer (sidebar toggle, dialogs staying within the app window). Wired into the CI workflow alongside the rest.

---

## [0.4.0] — Performance overhaul & test infrastructure

### Fixed
- **Recently Deleted (Trash) panel** was rendering every entry at once — opening it with 600 deleted notes took ~1.8 seconds. Now paginates to 50 entries at a time with a "Show more" button; opens in ~100ms regardless of trash size.
- **Memory leak affecting long sessions**: five different frequently-rebuilt UI areas (note cards, calendar cells, attachments list, the multi-note share panel, and the generated share-code display) were registering themselves for live theme updates every time they were redrawn, without ever cleaning up the old registrations. Over a long session with many saves, this list grew unbounded and progressively slowed the app down. Fixed by only tracking widgets that persist for the app's lifetime — rebuilt content now picks up the current theme naturally each time it redraws instead.
- **Share Notes panel** had the same "render everything, no cap" issue as the Trash panel (one checkbox per note). Fixed with the same pagination approach.
- Export and Import (both the full `.zip` backup and the text share-code) used to block the entire UI while running — a backup with a lot of attachments could freeze the app for several seconds with no feedback. Both now run on a background thread with a live progress bar, and the app stays fully interactive throughout.
- Import (both code and `.zip` backup) could silently create duplicate notes if the same data was imported twice. Now checks incoming notes against what's already there and asks whether to skip duplicates, import everyone anyway, or cancel.
- Scroll wheel could get "stuck" trying to scroll an already-fully-visible small panel (e.g. an empty Trash list) instead of falling through to scroll the page underneath it — added a small tolerance to the "is this panel already fully shown" check to make it robust against minor platform differences in how scroll position is reported.
- A module-level crash-recovery handler referenced `self` in a context where it didn't exist — if the app had ever failed to start, the intended friendly error dialog would itself have crashed instead of showing.

### Added
- "Clean up ALL duplicate groups" — a one-click action that applies "keep the first copy, remove the rest" across every detected duplicate group at once, instead of working through each group individually.
- A "Clear" button on the Import Code panel, to wipe a pasted code (and any leftover status message) without manually selecting and deleting it.

### Removed
- ~700 lines of dead code: several old dialog-based flows (category manager, tag manager, duplicate finder, trash dialog, share-all dialog, import-code dialog) that had been fully superseded by inline panels earlier in development but were never deleted, plus a handful of smaller orphaned helper functions.
- Unused `messagebox` and `colorchooser` imports, left over from before those were replaced by the app's own themed dialog and color-palette systems.

### Testing
- Rebuilt the manual QA test plan (spreadsheet) into a structured set of 5 automated headless test scripts (87 checks total) plus a dedicated recurrence-engine test suite (18 checks), covering notes CRUD, categories, templates, recurrence, calendar, duplicate detection, trash, share codes, threaded import/export, theming, popup/panel stress testing, and data-corruption resilience.

---

## [0.3.0] — Tags removed; categories as the sole organization system

### Removed
- The Tags feature, entirely: the tag registry and persistence layer, all tag UI (note editor tag entry/chips, sidebar tag filter, Settings → Manage Tags panel), tag-based duplicate-merge logic, and tag fields from the share-code and data model. Categories were judged sufficient on their own, and tags added complexity without enough distinct value to justify maintaining two overlapping organization systems.
- Old notes with a leftover `tags` field from before this change load normally; the field is silently dropped on next save.

### Fixed
- The Manage Tags panel intermittently lost its content when switching between Settings accordion panels — root-caused to a layout calculation that ran before the panel had actually become visible, using an unreliable width. Superseded by removing the feature, but the underlying `<Map>`-event-based fix (relaying out deterministically the moment a panel becomes visible, instead of guessing a timer delay) is reused elsewhere in the Settings UI.
- Template editor (New/Edit) could open positioned behind the main window, appearing to do nothing when clicked. Root cause: the `-topmost` window attribute was being set *after* a layout recalculation call, which silently failed to take effect in that order on this platform. Also switched the editor to the same shared, multi-monitor-safe popup positioning used everywhere else in the app, after the editor's own hand-rolled positioning logic was found capable of placing it off-screen entirely.
- Category deletion confirmation was still a separate OS-style window rather than the app's inline themed dialogs; converted to match.

---

## [0.2.0] — Inline UI overhaul & data resilience

### Changed
- Converted essentially every remaining OS-native popup (dialogs, dropdowns, color pickers, date pickers) to the app's own borderless, themed, anchored popups — nothing falls back to a native white Windows dialog anymore.
- Multi-monitor dropdown positioning: popups now measure against the app's own window bounds rather than the full virtual screen, with live position tracking as the window moves, so a dropdown can no longer land on a different monitor than the app itself.

### Fixed
- A placeholder-text race condition in the tag and title entry fields, where fast typing immediately after clicking could concatenate with the placeholder text instead of replacing it.
- Note list scrollbar was invisible in some layouts due to pack ordering; scrollbar is now packed before the canvas so it always reserves its width.
- Several popups (emoji picker, tag filter, calendar day list) had their mousewheel binding wired up before their content existed, so scrolling silently didn't work; moved the binding to after content creation throughout.
- Autosave while a popup (e.g. the emoji picker) was open used to visibly flicker the sidebar as the note list refreshed underneath it; autosave now defers the refresh until the popup closes.

### Added
- Calendar: day-level emoji markers, hover previews per note (not just per day), create-note-from-calendar-day, visual separators between multiple notes shown in one day cell, adaptive preview text size based on window width.
- Emoji picker for the note editor (title/body/comments), with categorized emoji groups.
- Username greeting on the sidebar ("Hi \<name\>,"), configurable in Settings.

---

## [0.1.0] — Core application

### Added
- Note CRUD: create, edit, pin, duplicate, soft-delete to trash with automatic purge after a configurable retention window.
- Categories: create, rename, delete (with reassignment of affected notes), custom colors.
- Recurring notes: daily / weekly / monthly / yearly recurrence with custom intervals, specific-weekday and specific-day-of-month selection, a clamp/skip policy for month-end edge cases, end conditions (count or date), and per-occurrence editing/deletion separate from the base series.
- Calendar view with month navigation and jump-to-date.
- Templates: reusable note content, including checklist items.
- Checklist items within a note, with progress shown on the note's card in the list.
- Duplicate detection (matching on title/body/comments/category) with per-group cleanup.
- Search and six sort modes; grouping by category with persistent collapse state.
- Sharing: single or multiple notes as a compact copy-pasteable text code; full backup export/import as a `.zip` including attachments.
- File attachments per note.
- Eight built-in themes (four dark, four light variants).
- Single-editor-tab design: switching notes always autosaves the one being left, no explicit tab management needed.
