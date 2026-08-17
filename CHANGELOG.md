# Changelog

All notable changes to Note Organizer are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Version numbers below are retrospective groupings of related work — this project didn't tag formal releases from day one, so early history is grouped by theme rather than exact date.

---

## [Unreleased]

## [0.30.38] — 2026-08-18

### Added
- A collapsible in-note calculator, next to Checklist in the note editor. Supports standard +/−/×/÷ arithmetic with three interchangeable bracket styles, a square root, a general power operator (any exponent, not just squaring), and percent — evaluated via a small hand-rolled parser rather than eval(). The display accepts typing and pasting directly, not just button presses, so an expression copied from elsewhere can be evaluated as-is.
- Insert the calculator's result into the note body — inserts the whole formula (not just the answer), and repeated use builds a clean log downward (each insertion lands on its own line after the previous one) instead of gluing onto wherever the cursor happens to be. A collapsible, session-only history of past calculations is available too, with a Clear button and click-to-insert on any past entry.

### Testing
- Added test_calculator.py (47 checks) covering the expression evaluator directly — precedence, brackets, power/root/percent, and a wide range of malformed input. Added extensive qa1.py coverage for the real button/paste/history UI flow.

## [0.28.38] — 2026-08-17

### Fixed
- Typing in the note search box rebuilt the entire note list on every single keystroke — measured at ~800ms for 300 notes, meaning a short search term could cost several seconds of cumulative rebuild time, with visible input lag on every character. Now waits for a brief pause in typing before rebuilding once, the same debounce pattern already used for autosave.
- Audited every scheduled timer/callback in the app (16 in total) for crash-safety if the window closes while one is still pending — a genuine risk for anything that fires after a delay, since the user can close the app at any point in between. Nine were found unguarded and fixed: the export/import progress poller, the periodic unsaved-edit check, the debounced autosave, the debounced search refresh, the username-field autosave, the startup version-change/reminder banners, the editor's scroll-region sync, and the image preview's click-outside-to-dismiss binding. Also discovered that even checking "is the window still there" can itself fail once the whole application (not just one widget) has been torn down — added one shared, properly-guarded check used everywhere this matters now.
- An unexpected error inside any button click or keyboard shortcut (not related to the timer-safety issue above — any genuinely unanticipated bug) used to fail completely silently: Tkinter's default behavior only prints to the console, which doesn't exist in this app's windowed build, so the user would see nothing at all — no crash, but no explanation either, and no way to know if their data was affected. Now logged to the same crash log the top-level handler uses, with a brief on-screen toast so there's at least some signal instead of pure silence.
- The background export/import threads only caught `IOError`/`OSError` — any other unexpected error type killed the thread silently (Python's default behavior for an uncaught thread exception) without ever marking the operation as finished, leaving the progress bar stuck forever with nothing shown as wrong. Both now catch anything unexpected as a last resort, so the operation always resolves — with a specific message for the failure cases already understood, and a generic-but-honest one for anything else.
- Found by hand: changing a template's category (either while creating a new one, or editing an existing one — including templates originally saved from the note editor's "Save as template" shortcut) silently closed the entire template editor and discarded all unsaved changes, the moment the category dropdown was clicked. The dropdown's own opening logic was closing whatever popup was "currently open" before showing its list — but the template editor *was* that currently-open popup, so opening the category picker destroyed the very editor it lived inside, before the picker could even be used. The same bug affected the calendar's "Jump to month" popup. Both now correctly distinguish a dropdown that's nested inside another popup from one that's replacing an unrelated, previous one — fixing this also fixed the category list appearing anchored to the top-left corner of the window instead of under the button, which was a side effect of positioning against a button that had just been destroyed along with its parent.
- Typing a date directly into a note's Date field (rather than using the calendar-icon picker) never triggered autosave — the only field in the editor missing that wiring — so a typed date change could be silently lost if the user clicked away instead of pressing Save. Fixed by adding the same autosave binding the other fields already have. Doing so surfaced a second issue: autosave shares its date-format validation with the manual Save button, so wiring it up naively made autosave interrupt the user mid-keystroke with an "Invalid date" warning on an as-yet-incomplete date. Both that warning and the related "repeating note needs a start date" one now only show for an explicit manual Save; autosave silently waits for a valid/complete value instead.
- "Recently updated" / "Oldest updated" sort could show notes in the wrong order: the saved timestamp only tracked minutes, not seconds, so two notes saved within the same minute looked identical to the sort and fell back to an unrelated order instead of true edit recency. Now saved with second-level precision everywhere a note's timestamp gets written.
- A silent background autosave could show a real "Note missing" error dialog — meant only for an explicit Save click — if its debounced timer fired after the note it was about to save had been removed some other way in the meantime. Now silently does nothing in that case, matching how switching notes already handled the same situation.
- The calendar's right-click menu had a redundant "View this day" entry — a plain left-click on the day already opens the same panel. Removed.
- The username field (Settings → Your name) had no length limit, which could make the sidebar greeting look broken. Capped at 30 characters, checked in real time as you type (not just when the name is saved), so the field simply stops accepting more instead of accepting everything and quietly trimming it later. Also removed the field's redundant "Save" button, since it already autosaves shortly after typing stops, and immediately on Enter or clicking away.
- Settings: clicking a non-interactive part of the page (a section title, a card's background) — including going straight to "Back to Notes" — left a previously-focused field's cursor visibly blinking even after its value had already autosaved. Now correctly clears focus in both cases.
- Scrolling did nothing while hovering over certain parts of the Settings page — the theme picker's preview cards (a Canvas quirk: they have their own built-in scroll behavior that swallowed the wheel event) and the Statistics summary/category chips (plain widgets that were simply never wired into the page's scroll-forwarding). Both now scroll the page correctly, using the same forwarding pattern already used elsewhere in Settings.
- Three small layout fits, each measured and verified with exact pixel numbers rather than assumed: the sort dropdown's "Recently updated" option was cut off (it rendered at exactly its natural text width with zero margin); the multi-select bulk "Category" button was cramped (the bulk-action bar's four widgets needed more width than the fixed-width sidebar allowed); and Settings' "← Back to Notes" button scrolled out of view instead of staying pinned (it was just another row inside the scrollable content, with nothing making it special). Widened the sort label, tightened the bulk bar's font and spacing, and moved the Back button into its own fixed row outside the scrollable area.
- Found during a deliberate review of the app's data-safety guarantees (not from an observed failure): when reclaiming notes from `%APPDATA%` back into a local install, the app backed up the local file before overwriting it with the AppData copy, but never checked whether that backup actually succeeded. If it silently failed (disk full, permissions, the file locked by something else), the overwrite proceeded anyway with no safety copy of what was about to be replaced. Now aborts and leaves the local file untouched if the backup fails, instead of proceeding blind.
- A version upgrade only ever backed up `notes_data.json` on a brand-new first run — a normal upgrade re-reading (and potentially rewriting, via whatever changed in that version) the same file had no equivalent snapshot taken beforehand. Now every detected version upgrade takes a timestamped backup first, kept forever (never auto-deleted — clearing old ones out is the user's call, not the app's).
- Settings → Statistics category chips looked clickable (hover highlight, hand cursor) but clicking silently did nothing — reproduced in both the script and the packaged `.exe`, after scrolling the Settings page, but never in a headless test despite several attempts at a synthetic repro. Rather than keep chasing the exact cause, removed the click-to-filter interactivity outright: Statistics is a read-only snapshot, not another way to filter notes.
- Statistics only ever recomputed when Settings was first opened or the theme changed, so category renames/deletes, new notes, and template changes made while staying on the Settings page left stale data on screen until the user left and came back. An intermediate fix gated the refresh on the Settings page's `winfo_ismapped()` state, which looked like a safe optimization but doesn't reliably reflect `pack()`/`pack_forget()` synchronously in real interactive use — that gate silently skipped real updates instead of just avoiding unnecessary redraws. Statistics now refreshes unconditionally (a cheap operation) whenever the note list refreshes or a template is added/edited/deleted, so it stays live without needing to switch away and back.

### Changed
- The GitHub Actions workflow didn't reset app state (settings, notes, trash) between QA test steps, so each script silently inherited whatever the previous one left behind — investigated after two workflow runs got stuck for hours at the QA5 step. Couldn't reproduce the exact hang locally, but this order-dependency was a real, independently-worth-fixing gap regardless of whether it was the specific cause; each step now starts from a clean slate. Also added a 15-minute job timeout, so any future hang (whatever the cause) fails loudly within minutes instead of silently occupying a runner for hours.
- Settings → Statistics: category counts now show as a colored dot plus plain text instead of a box-styled chip, since they're no longer clickable. The whole section moved from right after "Your name" to between "Clean up duplicates" and "Storage info."

### Added
- Settings → Statistics now breaks "new/updated this week" out into a fuller week/month/this year/older breakdown for both added and updated notes, laid out in an aligned grid so the numbers line up between the two rows regardless of digit count or icon width.
- Settings → Statistics also shows standalone counts for saved templates, notes with a checklist, and notes currently in Trash — each counts the thing itself, not how many notes reference it (a template can be reused across many notes; a checklist only ever lives inside the one note it's on).
- A first-launch date, stamped once and never overwritten, shown in Statistics as "Using Note Organizer since `<date>`". Existing installs get the date of their first launch *after* this update, since there's no way to know their real first-use date retroactively.

### Testing
- Added `qa8.py`: automated coverage for the search debounce (no rebuild while typing, correct filtering after the pause), all nine timer-safety fixes, the callback-exception handler, and the export/import worker exception-safety fixes (each confirmed to resolve, not hang, when an unexpected error type is deliberately injected).
- Added `qa9.py`: automated coverage for the nested-dropdown-destroys-its-own-parent-popup fix, across both places it occurred (template editor, calendar's jump-to-month) — including the exact scenario reported (editing an already-saved template's category and confirming the change survives a reload from disk).
- Added a regression check to `qa5.py` confirming that typing a date schedules an autosave.
- Fixed `qa1.py`'s sort-option test: it previously looped over made-up option labels ('Newest first', 'Title A-Z', etc.) that matched none of the app's real sort options, so it silently never exercised any actual sorting logic — only proved the app didn't crash. Now uses the real option labels against a small fixture of notes and checks each mode produces the exact correct order.
- Added regression tests to `qa6.py` for the username length cap (both the real-time and save-time correction) and the Settings focus-clearing fix (same-page clicks and the direct "Back to Notes" path).
- Added a regression check confirming a freshly-saved note's timestamp includes seconds (the fix for the "Recently updated" ordering bug).
- Fixed `qa5.py`'s own date-autosave regression check to flush its pending autosave timer immediately after confirming it was scheduled, instead of leaving it dangling for a later, unrelated test to potentially trip over — this dangling timer is what surfaced the "Note missing" autosave bug above.
- Added regression checks to `qa1.py`, `qa6.py`, and `qa7.py` for the three layout fits above (pixel-measurement checks for the sort label and bulk-action bar, a scroll-position check for the sticky Back button).
- Fixed the bulk-action-bar width regression test itself after it failed in CI: it compared against an absolute pixel number measured locally on Windows using "Segoe UI," but the CI runner is Linux, which doesn't have that font — Tk silently substitutes a wider fallback there. Now compares the fixed bar against a reconstruction of the pre-fix sizing, built with whatever font actually resolves on the machine running the test, so the check verifies the fix's real effect instead of a Windows-specific pixel target.
- Added regression checks to `qa6.py` confirming a wheel event over a theme preview card, and over a Statistics chip, both scroll the Settings page.
- Added `test_data_safety.py`: a new standalone suite (no GUI, like `test_recurrence.py`) covering the backup/migration safety net directly — the version-upgrade backup, the migration backup-verification fix above, and the underlying `backup_notes_file`/`_timestamped_backup`/`detect_version_change` helpers — using temporary directories so it never touches real data. Added a companion check to `qa1.py` confirming the running app actually takes the backup when a version upgrade is detected. Both now run in CI on every push and PR.
- Added a `get_first_launch_date` check to `test_data_safety.py`: confirms it stamps a date on first call and never overwrites an existing one.
- Replaced `qa6.py`'s old "statistics chip navigation" test (which never actually clicked the chip — it just called the underlying functions directly, so it would have passed even if the real click were completely broken) with regression checks confirming chips have no hand cursor and clicking one changes neither the active tab nor the filter.
- Added regression checks to `qa6.py` for the new Statistics content: template/checklist/deleted counts and the first-launch date render correctly; stats reflect a category deletion, a normal multi-category save sequence, and a template add/edit/delete — all without needing to leave and reopen Settings; and separately, that switching away to the editor and back still shows current data for the one thing that genuinely can't update while Settings itself is open (checklists, edited only in the note editor).

## [0.5.0] — 2026-08-09

### Fixed
- Attachment files were never actually deleted from disk — removing an attachment from a note, permanently deleting a trashed note (individually, via "Empty trash", or through automatic purge after the retention window) all removed the note/reference but left the underlying file behind indefinitely. All four paths now clean up the physical file too. Moving a note to trash (the reversible, soft-delete path) correctly still leaves files untouched, since the note might be restored.
- Calendar keyboard navigation (PgUp/PgDn/Home) and the resize-driven font relayout could still act on the calendar while it was hidden behind the new Settings page, if Calendar had been the last-selected tab before opening Settings — silently changing the visible month behind the scenes. Both now check that the calendar is actually on screen, not just that it's the notebook's internally "selected" tab.
- Importing a single-note share code (as opposed to a multi-note one) skipped the duplicate check entirely and went straight to opening it for editing — found by hand, by copying a code from a note already present and re-importing it. Now checks for an exact match first and asks before opening it, same as the multi-note path.
- The calendar day panel's delete actions (including the pre-existing right-click menu one) refreshed the panel unconditionally after being clicked — including when the user canceled the confirmation dialog, which incorrectly bounced the view back to the day's note list instead of leaving it exactly as it was. Now only refreshes if the note actually stopped occurring on that date.
- Selecting notes for a bulk action, and switching which note is open, both used to rebuild the entire note list just to reflect a small change — visibly flickering the whole list on every click. Both are now targeted, direct updates to just the card(s) that actually changed. A bulk Trash/Category action still does a full rebuild afterward, since those genuinely change which notes exist or what they show — skipping that briefly left deleted notes' cards on screen, looking present but acting as if already gone.
- Deleting a note via right-click or the calendar, while a *different* note was open in the editor with unsaved changes, could show a spurious "Note missing" error. The delete flow temporarily repoints the editor's internal note-selection at the note being deleted, to reuse the normal delete logic — if anything then tried to autosave-flush using that temporary value, it would try to save against the note that's about to be gone rather than the one genuinely open. Fixed at the root: an autosave flush now silently does nothing if the note it would save against no longer exists, instead of surfacing an error — appropriate for an automatic background action the user never directly asked for.
- A note with only an attachment (or only checklist items) and no typed title or body was never autosaved, and even a manual Save attempt was rejected as "empty" — attachments and checklist items now count as real, savable content everywhere this is checked.

### Added
- Project documentation set (`README.md`, this changelog, architecture notes, roadmap, issues log)
- Git version control, hosted on GitHub
- Continuous integration via GitHub Actions (`.github/workflows/tests.yml`): the full automated test suite now runs on every push and Pull Request.
- Delete a note directly from the calendar day panel — a small trash icon on each row in a day's note list, and a Delete button on the note-detail view reached from there. Reuses the same confirmation and recurring-series-scope prompts as deleting from anywhere else, so nothing about safety changes; it just no longer requires opening the full editor first.
- Multi-select notes for bulk actions — a "Select" toggle in the sidebar shows a checkbox on each note; pick several and move them all to trash or reassign them all to a different category in one action, instead of one at a time. The currently-open note's card is also now outlined in the theme's accent color, so it's clear at a glance which one is open.
- Image attachments (PNG, GIF, JPEG, WEBP, BMP) now show a large in-app preview when clicked — most of the window, with a Close button and an "Open externally" option — instead of always handing off to an external viewer. Animated GIFs actually play, using real per-frame timing.
- Delete confirmations (single note or bulk) now mention how many attached files will go to the trash along with the note(s).
- The app remembers which note was last open and reopens directly into it on the next launch, with all its content — title, body, comments, checklist, attachments — restored.

### Changed
- Settings moved out of the Notes/Calendar tab strip entirely, into its own button in the sidebar (alongside New Note / Import / Share), with a "← Back to Notes" button to return. Originally planned as "push it to the far right of the tab strip" (see ROADMAP), but that risked sitting too close to the window's own close button — the sidebar button avoids that concern and tested better in practice.
- The note editor's "📋 Copy code" button renamed to "📋 Generate code" — nothing has been generated or copied to the clipboard yet at the point it's clicked, which "Copy" implied. Matches the wording already used by the multi-note Share panel's equivalent button.
- Added [Pillow](https://pypi.org/project/Pillow/) as the app's first external dependency, specifically for image handling. Plain Tkinter can only decode PNG/GIF natively, and — critically — doesn't correctly composite animated GIF frames: many GIFs only store the region that changed from the previous frame, relying on the viewer to place it correctly on a fixed canvas, which plain Tkinter doesn't do (the in-app preview visibly jumped and resized itself every frame before this). Pillow fixes that, adds JPEG/WEBP/BMP support, and gives noticeably cleaner scaling.

### Testing
- Two of the five automated QA scripts (`qa3.py`, `qa4.py`) still referenced the Settings page's old, removed notebook-tab index, and had been silently passing for the wrong reason (their own exit code was never actually checked, so a script erroring out still reported as a successful test run). Both issues are fixed: the scripts now call `show_settings_page()` directly, and every test script exits with a real failure status when a check fails, which is what makes the new CI integration meaningful rather than always green.
- Added `qa6.py`: automated coverage for category grouping (collapse state and persistence), Settings (username greeting, statistics navigation), attachments through the actual UI functions (not just the file-cleanup fix), several multi-feature combination scenarios, and the parts of window layout that have a real right/wrong answer (sidebar toggle, dialogs staying within the app window). Wired into the CI workflow alongside the rest.
- Added `qa7.py`, closing a coverage audit across everything built in recent sessions: three of the four attachment-cleanup paths (permanent delete, empty trash, automatic purge) had never had a permanent regression test, only the fourth (removing a single attachment) did. Also newly covered: deleting a note from the calendar (including the Cancel-doesn't-bounce fix), multi-select bulk actions (including the no-rebuild-on-select/switch behavior and the currently-open-note cleanup fix), the Pillow-based image preview (scaling in both directions, corrupt-file handling), attachment mentions in delete confirmations, the "Note missing" bug fix, attachment-only-note autosave, and the last-open-note memory feature.

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
