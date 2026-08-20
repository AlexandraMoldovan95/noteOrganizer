# Architecture

How Note Organizer is built, and why. Written for anyone reading the code for the first time — including future-me.

## Overview

Note Organizer is a Python/Tkinter desktop app, entered through `note_organizer.py`. It was a single file by design for most of its life — no build step, no import graph to reason about, readable top-to-bottom — but at ~11,000 lines that stopped paying for itself, and the app is now being reorganised into a `noteorganizer/` package one module at a time.

The target is two layers:

- **`noteorganizer/core/`** — data and rules: persistence, validation, recurrence, the calculator parser, sharing. **No module in here may import tkinter**, which is what keeps it testable headlessly and reusable by a different front end.
- **`noteorganizer/ui/`** — everything on screen, being split one area at a time into **mixin** classes that `NoteOrganizer` inherits from. The methods are unchanged: they still reach for `self.colors`, `self.notes` and each other exactly as before, so each move is cut-and-paste rather than a redesign. This is organisation, not decoupling — the mixins share one object, and `self.colors` alone is read in 655 places. Two rules: a method lives in exactly one mixin (a duplicate is silently resolved by class order, with no error), and mixins never define `__init__` — construction stays in `NoteOrganizer`. `tools/check_class_api.py` enforces the first by comparing the class's whole method list against a recorded baseline. Moved so far: `ui/calculator_panel.py`.

`note_organizer.py` stays the entry point (`py note_organizer.py`) and re-exports the names that have moved, so existing callers — including the ~154 `note_organizer.<name>` references across the QA scripts — keep working untouched while the move happens. That's deliberate: it means each extraction is a pure move that leaves the whole test suite green, rather than a rewrite.

Moved so far: `core/calculator.py`, `core/recurrence.py`, `core/themes.py`, `core/formatting.py`, `core/sharing.py`, `core/duplicates.py`, `core/paths.py`, `core/storage.py`, `core/categories.py`, `core/model.py` — the core layer is complete. [CODE_TOUR.md](CODE_TOUR.md) walks through the modules for someone learning the codebase.

## Startup

`note_organizer.py` is inert to import. Resolving the data folder, running migrations, purging stale copies, pointing `core.paths` at the result and recording the version all happen in `initialise()`, which `NoteOrganizer.__init__` and `_main()` both call (it's idempotent, so order doesn't matter).

This matters for more than tidiness: those steps move and delete files, and running them as a side effect of `import note_organizer` is how a real notebook was once destroyed — see [ISSUES_LOG.md](ISSUES_LOG.md). Anything that wants the data layer without building a window must now call `initialise()` deliberately, which is what `test_data_safety.py` does.

## Data layer

### Storage

Everything is local JSON, stored next to the script (or the built `.exe`):

| File | Contents |
|---|---|
| `notes_data.json` | All active notes |
| `settings.json` | Theme, username, categories, window prefs |
| `trash.json` | Soft-deleted notes, with a `deleted_at` timestamp |
| `templates.json` | Saved note templates |
| `attachments/` | Attached files, referenced by name from each note |

There's no database — the note counts this app is built for don't need one, and plain JSON keeps the format simple to inspect, back up, and hand-edit if something ever goes wrong.

### Defensive normalization

`normalize_note()` is the single choke point every note passes through before it's trusted anywhere else in the app — on load, on import, on paste-from-share-code. It coerces missing or malformed fields (a `None` title, a checklist that isn't a list, a category that no longer exists) into safe defaults rather than letting a bad record propagate into the UI and crash something. This is what lets the app survive hand-edited or corrupted data files without special-casing every call site.

### Recurrence model

A recurring note is stored once — the "base" note carries a `recurrence` rule (frequency, interval, specific weekdays/month-days, an end condition) plus two small maps:

- `exceptions`: dates removed from the series entirely
- `overrides`: date → partial note, for edits that apply to one occurrence only

`expand_occurrences(note, range_start, range_end)` is the only place that turns a rule into actual dates — everything else (calendar rendering, list previews) asks it for occurrences within a window rather than re-deriving the logic. Editing "just this occurrence" writes an override; editing "this and all future" (or the whole series) edits the base note directly.

## UI layer

### No native dialogs, anywhere

Every dropdown, color picker, confirmation prompt, and date picker in this app is a hand-built `Toplevel` popup — never `tkinter.messagebox`, `ttk.Combobox`, or `colorchooser`. The trade-off is more code to maintain; what it buys is a UI that's fully themed (dark/light variants apply everywhere, including every dialog) and behaves consistently across the app.

The shared building block is `_place_dropdown_popup()`: given a popup and an anchor widget, it positions the popup against the *app's own window bounds* (not the full virtual screen — this specifically avoids popups landing on the wrong monitor in a multi-monitor setup), keeps `-topmost` set so it can't get pushed behind the main window on a focus change, and live-tracks the app window if it's moved or resized while the popup is open. New popups should use this rather than reinventing positioning.

For yes/no/multi-choice prompts, `_themed_dialog()` renders an in-app overlay (not a real OS window) and blocks via `wait_variable` until a button is clicked, returning the chosen value.

### Theme tracking — two different patterns, on purpose

`track_theme(widget, **option_map)` registers a widget so a later theme switch re-applies the right colors to it. This is for **persistent** widgets — ones built once at startup and never destroyed (the sidebar, the main buttons, the tab bar).

For content that gets **destroyed and rebuilt** on every refresh — note cards, calendar cells, the attachments list, anything inside a Settings accordion panel — widgets are colored with plain `.configure(bg=self.colors[...])` calls instead. Since this content is always rebuilt fresh, it never needs live tracking; using `track_theme` here just means every rebuilt widget's tracking registration outlives the widget itself, since nothing ever prunes destroyed entries. That's an actual bug this codebase had for a while (see [CHANGELOG.md](../CHANGELOG.md) 0.4.0) — a growing, unbounded list of registrations for windows that no longer existed, which measurably slowed the app down over a long session. **Rule of thumb: `track_theme` for widgets built once; direct `.configure()` for widgets inside anything with a `redraw()`/rebuild pattern.**

There's a third case, added in 0.32.49: content that is normally rebuilt on refresh but must **not** be rebuilt just because the palette changed. `apply_theme()` used to call `refresh_note_list()`, which destroyed and rebuilt every note card — about 85ms of a 121ms theme switch, with the list visibly emptying and refilling. Nothing about a theme switch changes note *data*, so `_recolor_note_cards()` now re-applies colors to the cards already on screen, using named widget references recorded in `_note_card_widgets` when each card is built. This is **not** the `track_theme` pattern that leaked: `_note_card_widgets` is rebuilt from scratch by every `refresh_note_list()`, so it only ever holds cards currently on screen. Two ordering rules matter here — `_recolor_note_cards()` runs *after* `_recolor_stragglers()` so a note's own color (recomputed from the note, not color-swapped) wins over the generic remap, and the calendar is skipped entirely while off screen and caught up by `_catch_up_deferred_refresh()`. See `docs/ISSUES_LOG.md`, "The theme-switch flicker, and three ways not to fix it".

### Large lists: paginate, don't virtualize (yet)

Trash and the multi-note Share panel both cap how many rows they build at once (50 and 100 respectively), with a "Show more" button to reveal the next batch, rather than rendering every entry immediately. This was enough to take the Trash panel from ~1.8s to ~100ms with 600 entries. The main note list doesn't do this yet — see [ROADMAP.md](ROADMAP.md) for real windowed virtualization, which would help further at very large note counts.

## Background work: exporting and importing

Full backup export/import (`.zip`, including attachments) runs on a `threading.Thread`, not the main thread — with enough attachments, doing this synchronously visibly froze the UI for several seconds. The pattern used, and the one to follow for any future long-running I/O:

1. The worker thread does file I/O only, and updates a plain shared `dict` (e.g. `{"current": i, "total": n, "done": False}`) as it progresses. **It never touches a Tkinter widget.**
2. The main thread polls that dict on a timer (`self.after(100, poll_fn)`), and is the *only* place that updates the progress bar or shows a completion dialog.

This division is a hard rule, not a style preference — Tkinter isn't thread-safe, and any widget access from the worker thread is a race condition waiting to surface as a rare, hard-to-reproduce crash.

## Autosave

Typing pauses trigger a debounced autosave; switching notes (or tabs) flushes any pending change immediately first, so nothing written is ever lost to a note switch. Autosave explicitly skips refreshing the note list while a popup is open (deferring the refresh until the popup closes) to avoid the sidebar visibly flickering underneath an open dropdown.

## Testing

Manual QA lives as a structured spreadsheet in `qa/`. Automated coverage is a set of headless test scripts run under Xvfb (no visible display needed) — nine scripts covering CRUD/categories/templates, recurrence/calendar/duplicates, trash/share/import-export, theming/stress/leak-regression, data-corruption resilience, grouping/settings/attachments/combinations, calendar-delete/multi-select/image-preview/autosave fixes, search-debounce/background-timer robustness, and a nested-dropdown-inside-popup fix, plus three standalone suites that need no GUI at all: the recurrence engine, data-safety (backups & migration), and the in-note calculator's expression evaluator. All of them run automatically on every push and Pull Request via GitHub Actions (`.github/workflows/tests.yml`), so a regression shows up as a failed check rather than being found by hand later. See [ISSUES_LOG.md](ISSUES_LOG.md) for notable bugs these caught (and a few they didn't, caught by hand-testing instead).
