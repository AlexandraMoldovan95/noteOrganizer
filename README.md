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

- **Pure Python + Tkinter.** No GUI framework dependency beyond the standard library — packages to a single-file Windows `.exe` via PyInstaller with no bundled runtime beyond Python itself.
- **Custom widget system throughout.** Every dropdown, color palette, and confirmation dialog is a hand-positioned `Toplevel` popup, anchored and multi-monitor-safe, rather than relying on `tkinter.messagebox` / `ttk.Combobox` defaults.
- **Background threading for I/O.** Export and import (both of which can move a meaningful amount of data through attachments) run on a worker thread; the main thread only ever touches Tkinter widgets from a polling callback, keeping the UI responsive throughout.
- **A defensive data layer.** `normalize_note()` coerces any note — however old, however malformed — into a known-good shape before it ever reaches the UI, so a single corrupted entry can't take down the whole app.

---

## Getting started

```bash
git clone https://github.com/AlexandraMoldovan95/noteOrganizer.git
cd noteOrganizer
python note_organizer.py
```

Requires Python 3.9+ with Tkinter (bundled with most standard Python installs; on Linux you may need `sudo apt install python3-tk`).

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
├── note_organizer.py       # the application (single file by design — see docs/ARCHITECTURE.md)
├── docs/
│   ├── USER_GUIDE.md        # full walkthrough with screenshots
│   ├── ARCHITECTURE.md       # how the code is organized, and why
│   ├── ROADMAP.md            # what's planned next
│   ├── ISSUES_LOG.md         # notable bugs found & fixed during development
│   └── screenshots/
└── qa/
    └── NoteOrganizer_TestPlan.xlsx   # manual QA test case tracker
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) — full feature walkthrough
- [Architecture](docs/ARCHITECTURE.md) — how the codebase is structured
- [Roadmap](docs/ROADMAP.md) — planned features and known open items
- [Changelog](CHANGELOG.md) — release history
- [Issues Log](docs/ISSUES_LOG.md) — notable bugs encountered during development, and how they were diagnosed/fixed

## Local data

The app stores everything next to the script (or next to the `.exe` when built), never anywhere else: `notes_data.json`, `settings.json`, `trash.json`, `templates.json`, and an `attachments/` folder. Nothing is sent anywhere — the app has no network calls.

## License

*(add a LICENSE file — MIT is a common default for a portfolio project)*
