# Note Organizer

A fast, fully offline desktop notes app built with Python and Tkinter — no cloud, no accounts, and a single third-party dependency (Pillow, for image previews). Every note, attachment, and setting lives in a folder on your own machine.

Built as a solo/pair project (developer + AI pairing partner) across 40 versioned releases, with a strong focus on real-world polish: a custom themed UI (every popup and dialog is drawn by the app; only picking a file hands over to the system), a recurring-events engine, background-threaded import/export, and a defensive data layer that keeps the app usable even when things go wrong.

![The main window: a note with a table, the formatting toolbar, and the notes sidebar](docs/screenshots/main-window.png)
*More screenshots throughout the [User Guide](docs/USER_GUIDE.md).*

Every image here is this app: the screenshots are captures of it running,
and the icon is **drawn from code** at build time by
[`tools/make_icon.py`](tools/make_icon.py) rather than stored as a file —
five designs to choose between, each one redrawn (not shrunk) at small
sizes so it still reads at 16px in a taskbar. Nothing was taken from
anywhere else.

## Project highlights

- **Ships as a real Windows app** — a PyInstaller one-folder build, released across 40 versions — five early milestones plus 35 numbered bumps — and field-tested against a written test plan along the way (the [Changelog](CHANGELOG.md) tells the story; the [version ledger](docs/ROADMAP.md#version-ledger) accounts for every number).
- **~1,540 automated checks on every pull request** — a nine-script headless GUI suite (~1,070 checks) driving the real app plus six unit suites, run in CI on both Windows and Linux.
- **Fully offline by design** — plain local JSON files, no accounts, no network calls, one dependency.
- **A hand-built themed UI** — every dialog, dropdown and picker is drawn by the app itself; only choosing a file or folder uses the system's own chooser. 8 themes, switchable live.
- **Everything is plain text underneath** — tables drawn as real grids, checkboxes, rich text and lists are all stored as readable Markdown-style text, so notes survive export, sharing and backup intact.

---

## Features

### Notes & writing

- Create, edit, pin, duplicate and soft-delete notes; each carries a category, colour, date, comments, a checklist and file attachments
- Autosave on pause, on note switch and on close — quitting never asks about "unsaved notes"
- Rich text (bold, italic, underline, strikethrough, colour, highlight, font size & family) plus nested bullet/numbered lists, indentation and alignment
- Paste from a browser, a word processor or a PDF and keep the formatting (**Ctrl+Shift+V** for plain text); a PDF's broken line endings are rejoined into the paragraphs they came from
- Full-text search across the notebook with six sort modes — plus **Ctrl+F** to find within the open note, text and tables alike
- A collapsible in-note calculator, and a reading-time estimate beside the word count

*Full walkthrough: [User Guide → Notes](docs/USER_GUIDE.md#notes)*

### Tables

- Spreadsheet-style grids drawn in the note: click a cell to edit, drag to select, Tab to move, Enter for a new line inside the cell
- Excel-familiar editing: copy/paste blocks of cells in and out of the app, merge, insert/duplicate/hide rows and columns, drag edges to resize, double-click to autofit
- Real clickable checkboxes, per-character colours and styles inside cells, per-cell alignment, and an auto-numbered caption from the table menu
- Stored as plain, readable Markdown table text inside the note — tables survive search, share codes, backups and export, and travel cleanly to any Markdown-aware tool

*Full walkthrough: [User Guide → Tables](docs/USER_GUIDE.md#tables)*

### Recurring notes & calendar

- Daily / weekly / monthly / yearly repeats with custom intervals — specific weekdays, or month-days with a *clamp/skip* choice for "the 31st"
- End after N occurrences, by a date, or never; edit or delete "just this one" vs "this and all future"
- A full calendar view with month navigation, jump-to-date and per-day colouring — plus a searchable **History** register of every dated note and each series' edited days

*Full walkthrough: [User Guide → Recurring notes](docs/USER_GUIDE.md#recurring-notes)*

### Organizing

- Custom colour-coded categories, safely renameable and deletable (affected notes are reassigned, never lost)
- Group the note list by category with per-group collapse; reusable note templates with a live preview
- Duplicate detection with per-group or one-click cleanup

*Full walkthrough: [User Guide → Finding notes](docs/USER_GUIDE.md#finding-notes-search-sort-and-grouping)*

### Data safety, sharing & backup

- Soft-delete to a Trash (Settings → Recently deleted) with a retention window you choose (7–90 days); a corrupt or half-missing note degrades to safe defaults instead of crashing the app
- Share one or many notes as a compact copy-pasteable text code; export a note or a selection as formatted HTML (opens in any browser or Word) or plain text
- A note keeps one identity wherever it travels, so a code that brings back a note you already have is recognised as that note — the app asks whether to update your copy or keep both, instead of quietly leaving you with two
- Full backup as a single `.zip` — notes, settings, attachments, templates and the Trash together — written atomically on a background thread with live progress; import checks for duplicates before merging instead of silently doubling notes

*Full walkthrough: [User Guide → Sharing & backup](docs/USER_GUIDE.md#sharing--backup)*

### Interface

- A fully custom themed UI — every message, confirmation, dropdown and picker is drawn by the app; the system's dialog appears only where it belongs, choosing a file or folder. 8 themes with a one-press ☀/🌙 flip in the editor
- Single-editor design, like a browser with one tab: switching notes always autosaves the previous one first
- App-wide shortcuts — **Ctrl+N** new note, **Ctrl+S** save, **Ctrl+F** find in note — with every bound combo listed under Settings → Keyboard shortcuts

*Full walkthrough: [User Guide → Settings](docs/USER_GUIDE.md#settings)*

<p align="center">
<img src="docs/screenshots/tables.png" alt="A table drawn as a grid inside a note" width="32%"> <img src="docs/screenshots/theme-picker.png" alt="The theme picker with live preview cards" width="32%"> <img src="docs/screenshots/calendar-view.png" alt="The calendar view with coloured days" width="32%">
</p>

---

## Tech notes

- **Pure Python + Tkinter, with one dependency.** No GUI framework beyond the standard library; [Pillow](https://pypi.org/project/Pillow/) is the one exception, used to decode and scale image attachments (including composing animated GIF frames, which plain Tkinter doesn't do).
- **Custom widget system throughout.** Every dropdown and palette is a hand-positioned `Toplevel` popup, anchored and multi-monitor-safe; every confirmation is an in-window overlay dialog that warns before anything irreversible and pre-selects the safe answer — nothing uses `tkinter.messagebox` / `ttk.Combobox` defaults.
- **Background threading for I/O.** Export and import run on a worker thread; the main thread only ever touches Tkinter widgets from a polling callback, keeping the UI responsive.
- **A defensive data layer.** `normalize_note()` coerces any note — however old, however malformed — into a known-good shape before it reaches the UI, so one corrupted entry can't take down the app.

*The reasoning behind these and every other design decision: [Architecture](docs/ARCHITECTURE.md).*

---

## Getting started

```bash
git clone https://github.com/AlexandraMoldovan95/noteOrganizer.git
cd noteOrganizer
pip install -r requirements.txt
python note_organizer.py
```

(Three spellings, one app: **Note Organizer** is the app, **NoteOrganizer** the built folder and the PyInstaller spec, and **noteOrganizer** the GitHub repository.)

Requires Python 3.9+ with Tkinter (bundled with most standard Python installs; on Linux you may need `sudo apt install python3-tk`), plus [Pillow](https://pypi.org/project/Pillow/) for image previews (installed above via `requirements.txt`).

### Building a standalone `.exe` (Windows)

```powershell
pip install pyinstaller
pyinstaller --noconfirm NoteOrganizer.spec
```

The built app appears under `dist/NoteOrganizer/` as a folder — move the whole folder, not the `.exe` on its own. Why the build goes through the spec file, and the distribution channels the result can ship through: [Windows Release Reference](docs/RELEASE_WINDOWS.md).

## Documentation

Where to start depends on who you are. **Just curious what the app can
do?** The [User Guide](docs/USER_GUIDE.md) walks every feature with
screenshots. **Wondering why things behave the way they do?** The User
Guide notes the reasoning beside each behaviour, and the
[Roadmap records what was decided against, and why](docs/ROADMAP.md#explicitly-not-planned-right-now).
**A developer or reviewer?** [Architecture](docs/ARCHITECTURE.md) holds
the design decisions, the [Code tour](docs/CODE_TOUR.md) reads the code
with you, and the [Issues Log](docs/ISSUES_LOG.md) tells the war
stories — each bug's cause, fix, and lesson. **Interested in the
testing?** [qa/README](qa/README.md) maps which suite guards which
surface and sets the house rules for new checks. **How the project is
run?** The [Changelog](CHANGELOG.md) holds the full release history, the
[Roadmap](docs/ROADMAP.md) what's planned and how versions are counted,
the [Git Workflow](docs/GIT_WORKFLOW.md) the exact branch/commit/PR flow,
and [CLAUDE.md](CLAUDE.md) the working agreement the AI-assisted sessions
follow. Platform packaging lives in the
[Windows](docs/RELEASE_WINDOWS.md) and
[Android](docs/RELEASE_ANDROID.md) release references (the latter
exploratory only).

## Project structure

```
noteOrganizer/
├── .github/
│   └── workflows/
│       └── tests.yml         # runs the full QA suite on every PR, and on main
├── note_organizer.py         # entry point + the UI hub (run this) — see docs/ARCHITECTURE.md
├── noteorganizer/            # the application package (core + ui both extracted)
│   ├── core/                 #   data & rules layer — never imports tkinter
│   │   ├── calculator.py     #   the in-note calculator's expression parser
│   │   ├── recurrence.py     #   repeat rules & which dates a note falls on
│   │   ├── themes.py         #   colour palettes and layout constants (pure data)
│   │   ├── formatting.py     #   how rich-text spans are stored on a note
│   │   ├── richtext.py       #   HTML in/out, for paste, copy and export
│   │   ├── clipboard.py      #   the Windows clipboard's richer formats
│   │   ├── tables.py         #   tables as lines of text (pipes are the store)
│   │   ├── sharing.py        #   share codes + safe-import guards
│   │   ├── duplicates.py     #   deciding when two notes are the same note
│   │   ├── paths.py          #   data location, migrations, safe cleanup
│   │   ├── storage.py        #   reading/writing notes, settings, templates, trash
│   │   ├── categories.py     #   the live category map, saved in settings
│   │   └── model.py          #   what a note is; normalize_note validates every one
│   └── ui/                   #   on-screen areas, one mixin per area
│       ├── calculator_panel.py  #   the in-note calculator panel
│       ├── settings_page.py     #   the Settings page and its panels
│       ├── dialogs.py           #   the hand-built dialogs and popups
│       ├── calendar_view.py     #   the Calendar tab
│       └── attachments.py       #   the attachments section
├── tools/                    # refactor safety net, run by CI
│   ├── check_*.py                # five static gates: names that resolve, the app
│   │                             #   class's surface, one definition per judgement,
│   │                             #   documentation links that go somewhere, and
│   │                             #   English in everything a reader sees
│   ├── pre_push_check.py         # all five, runnable locally in seconds
│   ├── run_tests.py              # the whole suite, safely, from a scratch copy
│   ├── visual_scenes.py          # screenshot harness for eyeballing rendered scenes
│   ├── make_icon.py              # draws the app icon, rather than storing one
│   ├── doc_screenshots.py        # retakes the documentation's own screenshots
│   ├── regen_seam_map.py         # rebuilds qa/README's seam map from the suite
│   └── linux-ci/                 # one Docker command reproduces the Ubuntu CI leg
├── test_*.py                 # six standalone unit suites: recurrence, data safety,
│                             #   calculator, tables, rich text, entry-module identity
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
    ├── README.md                     # the suite map: which script guards which surface
    ├── NoteOrganizer_TestPlan.xlsx   # manual QA test case tracker
    └── qa1.py … qa9.py               # the headless GUI suite (per-script index in qa/README.md)
```

## Testing

Every push and Pull Request runs the whole suite on GitHub Actions, on
**both Windows and Linux**: about 1,540 checks — ~1,070 across the
nine-script headless GUI suite, plus the six unit suites. [qa/README](qa/README.md)
maps which script guards which surface and carries the house rules new
checks follow; the [Issues Log](docs/ISSUES_LOG.md) tells how some of
those rules were earned. Check the **Actions** tab for the latest run.

Locally, one command runs everything the same safe way CI does — from a
scratch copy, because the GUI scripts wipe the data files beside them
(and `test_data_safety.py` refuses outright to run next to real notes):

```bash
py tools/run_tests.py          # everything — or one script: py tools/run_tests.py qa6
```

There's also a manual QA test plan (`qa/NoteOrganizer_TestPlan.xlsx`) covering scenarios that are easier to eyeball than to automate.

## Local data

The app keeps everything in one folder — `notes_data.json`, `settings.json`, `trash.json`, `templates.json`, and an `attachments/` folder — and nothing is sent anywhere (there are no network calls). When run from source, that folder sits next to the script; the built `.exe` stores it per-user under `%APPDATA%\NoteOrganizer` instead (so copying the `dist` folder to another machine does not carry your notes with it).

## License

© 2026 Alexandra Moldovan. All rights reserved.

This project is shared for portfolio and demonstration purposes. The source code may not be copied, modified, or redistributed without permission.
