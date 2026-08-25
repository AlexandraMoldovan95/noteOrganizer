# Note Organizer

A fast, fully offline desktop notes app built with Python and Tkinter — no cloud, no accounts, no dependencies beyond the standard library. Every note, attachment, and setting lives in a folder on your own machine.

Built as a solo/pair project (developer + AI pairing partner) over an extended iterative development cycle, with a strong focus on real-world polish: a custom themed UI (no OS-native popups anywhere), a recurring-events engine, background-threaded import/export, and a defensive data layer that keeps the app usable even when things go wrong.

![screenshot placeholder](docs/screenshots/main-window.png)
*(screenshots to be added — see [docs/screenshots](docs/screenshots))*

---

## Features

**Notes**
- Create, edit, pin, duplicate, and soft-delete notes
- Rich note metadata: category, color, date, comments, checklist, file attachments
- Autosave on pause and on note switch — nothing is ever lost mid-edit
- Full-text search and six sort modes (recency, title, category, date)
- Group notes by category, with persistent collapse state per group
- A collapsible in-note calculator (with parentheses and standard operator precedence), for quick sums without leaving the note
- Rich text formatting (Bold, Italic, Underline, Strikethrough, text color, highlight) in the note body — via a toolbar, the right-click menu, or keyboard shortcuts — applied to a selection or to whatever's typed next
- A reading-time estimate for each note, beside its word and character counts
- Font size and family, per selection or as the default for every note (Settings → Appearance), from a curated list that ships with Windows so a shared note renders as it was written
- Paragraph formatting: bullet and numbered lists that nest with Tab, indentation for any paragraph, and left/centre/right alignment. List markers are kept in the note's own text, so a list stays readable when exported, shared as a code, or pasted anywhere else

**Recurring notes**
- Daily / weekly / monthly / yearly recurrence, with custom intervals
- Weekly: pick specific weekdays. Monthly: pick specific days, with a *clamp* or *skip* policy for months that don't have that day (e.g. "the 31st")
- End conditions: after N occurrences, by a date, or never
- Per-occurrence editing and deletion ("just this one" vs "this and all future")
- A full calendar view with month navigation, jump-to-date, and per-day coloring

**Categories & templates**
- Custom categories with colors, safely renameable/deletable (with reassignment of affected notes)
- Reusable note templates, including checklist content, editable inline

**Data safety**
- Soft-delete to a Trash with automatic purge after a configurable retention window
- Duplicate detection (title/body/comments/category match), with per-group or one-click "clean up everything" resolution
- A defensive data layer: corrupt or missing fields on any note degrade to safe defaults instead of crashing the app

**Sharing & backup**
- Share one or many notes as a compact, copy-pasteable text code (no attachments — content only)
- Full backup export/import as a single `.zip` (notes, settings, attachments), running on a background thread with a live progress bar so the app never freezes during the operation
- Import safely checks for duplicates before merging, rather than silently doubling up your notes

**Interface**
- A fully custom themed UI — dialogs, dropdowns, color pickers, and popups are all hand-built to match the active theme; nothing falls back to an OS-native white popup
- 8 built-in themes (4 dark, 4 light variants), switchable live
- Single-editor-tab design (like a browser with one tab): switching notes always autosaves the previous one first

---

## Tech notes

- **Pure Python + Tkinter, with one dependency.** No GUI framework beyond the standard library — packages to a single-file Windows `.exe` via PyInstaller with no bundled runtime beyond Python itself. The one exception is [Pillow](https://pypi.org/project/Pillow/), used specifically for correctly decoding and scaling image attachments (including composing animated GIF frames properly, which plain Tkinter doesn't do).
- **Custom widget system throughout.** Every dropdown, color palette, and confirmation dialog is a hand-positioned `Toplevel` popup, anchored and multi-monitor-safe, rather than relying on `tkinter.messagebox` / `ttk.Combobox` defaults.
- **Background threading for I/O.** Export and import (both of which can move a meaningful amount of data through attachments) run on a worker thread; the main thread only ever touches Tkinter widgets from a polling callback, keeping the UI responsive throughout.
- **A defensive data layer.** `normalize_note()` coerces any note — however old, however malformed — into a known-good shape before it ever reaches the UI, so a single corrupted entry can't take down the whole app.

---

## Getting started

```bash
git clone https://github.com/AlexandraMoldovan95/noteOrganizer.git
cd noteOrganizer
pip install -r requirements.txt
python note_organizer.py
```

Requires Python 3.9+ with Tkinter (bundled with most standard Python installs; on Linux you may need `sudo apt install python3-tk`), plus [Pillow](https://pypi.org/project/Pillow/) for image previews (installed above via `requirements.txt`).

### Building a standalone `.exe` (Windows)

```powershell
pip install pyinstaller
pyinstaller --windowed --name NoteOrganizer note_organizer.py
```

The built app will appear under `dist/NoteOrganizer/`.

---

## Project structure

```
noteOrganizer/
├── .github/
│   └── workflows/
│       └── tests.yml         # runs the full QA suite automatically on every push
├── note_organizer.py         # entry point + the UI (run this); being split up — see docs/ARCHITECTURE.md
├── noteorganizer/            # the application package, growing as code is extracted
│   └── core/                 #   data & rules layer — never imports tkinter
│       ├── calculator.py     #   the in-note calculator's expression parser
│       ├── recurrence.py     #   repeat rules & which dates a note falls on
│       ├── themes.py         #   colour palettes and layout constants (pure data)
│       ├── formatting.py     #   how rich-text spans are stored on a note
│       ├── sharing.py        #   share codes + safe-import guards
│       ├── duplicates.py     #   deciding when two notes are the same note
│       ├── paths.py          #   data location, migrations, safe cleanup
│       ├── storage.py        #   reading/writing settings, templates, trash
│       ├── categories.py     #   the live category map, saved in settings
│       └── model.py          #   what a note is; normalize_note validates every one
│   └── ui/                   #   the interface, one mixin per area
│       ├── calculator_panel.py  #   the in-note calculator panel
│       └── settings_page.py     #   the Settings page and its panels
├── tools/                    # refactor safety net, run by CI
│   ├── check_undefined_names.py  # names used but never imported (moving code breaks these)
│   └── check_class_api.py        # the app class must keep exactly the same methods
├── test_recurrence.py        # standalone tests for the recurrence engine (no GUI needed)
├── test_data_safety.py       # standalone tests for backups & migration safety (no GUI needed)
├── test_calculator.py        # standalone tests for the in-note calculator's expression evaluator (no GUI needed)
├── docs/
│   ├── USER_GUIDE.md          # full walkthrough with screenshots
│   ├── ARCHITECTURE.md        # how the code is organized, and why
│   ├── CODE_TOUR.md           # annotated walkthrough of the modules, for learning the codebase
│   ├── ROADMAP.md             # what's planned next
│   ├── ISSUES_LOG.md          # notable bugs found & fixed during development
│   ├── GIT_WORKFLOW.md        # my own Git command reference for this project
│   ├── RELEASE_WINDOWS.md     # Microsoft Store (MSIX) and alternative Windows distribution channels
│   ├── RELEASE_ANDROID.md     # exploratory only, not current work
│   └── screenshots/
└── qa/
    ├── NoteOrganizer_TestPlan.xlsx   # manual QA test case tracker
    ├── qa1.py                        # automated: notes, categories, templates
    ├── qa2.py                        # automated: recurrence, calendar, duplicates
    ├── qa3.py                        # automated: trash, sharing, import/export
    ├── qa4.py                        # automated: theming, stress tests, leak regression
    ├── qa5.py                        # automated: corrupt data, edge cases
    ├── qa6.py                        # automated: grouping, settings, attachments, combinations
    ├── qa7.py                        # automated: calendar delete, multi-select, image preview, autosave & memory fixes
    ├── qa8.py                        # automated: search debounce, background-timer robustness
    └── qa9.py                        # automated: nested-dropdown-inside-popup fix
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) — full feature walkthrough
- [Architecture](docs/ARCHITECTURE.md) — how the codebase is structured
- [Code tour](docs/CODE_TOUR.md) — a guided, annotated walkthrough of the modules
- [Roadmap](docs/ROADMAP.md) — planned features and known open items
- [Changelog](CHANGELOG.md) — release history
- [Issues Log](docs/ISSUES_LOG.md) — notable bugs encountered during development, and how they were diagnosed/fixed
- [Git Workflow](docs/GIT_WORKFLOW.md) — the exact commands I use for this project's branch/commit/PR flow
- [Windows Release Reference](docs/RELEASE_WINDOWS.md) — Microsoft Store (MSIX) and alternative Windows distribution channels
- [Android Release Reference](docs/RELEASE_ANDROID.md) — exploratory only, not current work; kept ready for if an Android release is ever scoped

## Testing

Every push and Pull Request automatically runs the full QA suite via GitHub Actions (see `.github/workflows/tests.yml`) — recurrence engine tests, data-safety tests (backups made before a version upgrade, and the migration logic that moves notes between storage locations), the in-note calculator's expression evaluator, plus nine headless GUI test scripts covering notes/categories/templates, recurrence/calendar/duplicates, trash/sharing/import-export, theming/stress/leak-regression, data-corruption resilience, grouping/settings/attachments/multi-feature combinations, calendar-delete/multi-select/image-preview/autosave/memory fixes, search debounce/background-timer robustness, and the nested-dropdown-inside-popup fix. Check the **Actions** tab on GitHub for the latest run.

To run them locally:
```bash
python test_recurrence.py
python test_data_safety.py
python test_calculator.py
cd qa && python qa1.py   # and qa2.py – qa9.py
```

There's also a manual QA test plan (`qa/NoteOrganizer_TestPlan.xlsx`) covering scenarios that are easier to eyeball than to automate.

## Local data

The app stores everything next to the script (or next to the `.exe` when built), never anywhere else: `notes_data.json`, `settings.json`, `trash.json`, `templates.json`, and an `attachments/` folder. Nothing is sent anywhere — the app has no network calls.

## License

© 2026 Alexandra Moldovan. All rights reserved.

This project is shared for portfolio and demonstration purposes. The source code may not be copied, modified, or redistributed without permission.
