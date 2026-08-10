# NoteOrganizer — Claude Code Instructions

## Project overview

Note Organizer is a fully offline desktop notes app: Python + Tkinter, one
runtime dependency (Pillow, for image/GIF preview rendering). No network
calls, no accounts, no database.

- **Single-file design (intentional):** almost the entire app — data model,
  persistence, and UI — lives in `note_organizer.py` (~9,300 lines). This is
  a deliberate choice documented in `docs/ARCHITECTURE.md`, not an oversight.
  A future split into multiple files/modules is tracked in `docs/ROADMAP.md`
  but is not current work unless explicitly requested.
- **Storage:** plain local JSON — `notes_data.json`, `settings.json`,
  `trash.json`, `templates.json` — plus an `attachments/` folder, no
  database. Location is chosen by `resolve_data_dir()`: beside the script
  when run from source, `%APPDATA%\NoteOrganizer` when running as the built
  `.exe`. Every note passes through `normalize_note()` as a single choke
  point that coerces malformed/missing fields to safe defaults.
- **UI:** every dropdown, popup, and dialog is a hand-built `Toplevel` —
  no native OS dialogs anywhere except the last-resort startup-crash
  dialog. Two different, deliberate theming patterns exist
  (`track_theme()` for persistent widgets vs. plain `.configure()` for
  widgets that get rebuilt on every refresh) — see `docs/ARCHITECTURE.md`
  before touching theming code; mixing these up has caused a real
  perf regression before (see `docs/ISSUES_LOG.md`).
- **Background work:** export/import run on a `threading.Thread`; the
  worker thread must never touch a Tkinter widget directly — it only
  updates a shared dict that the main thread polls. This is a hard rule,
  not a style preference (Tkinter is not thread-safe).
- **Sharing:** "share codes" are Base64(zlib(JSON)) — a compact copy-paste
  format, **not encryption**. Full backup export/import uses a `.zip` with
  path-traversal and decompression-bomb guards. There is no encryption,
  password protection, or seed-based functionality anywhere in the app.
- **Testing:** `test_recurrence.py` is a standalone unit-style suite (no
  GUI). `qa/qa1.py`–`qa9.py` are headless GUI tests run under Xvfb, each
  starting from a clean data directory. Both run automatically via
  `.github/workflows/tests.yml` on every push/PR. There's also a manual
  test plan spreadsheet (`qa/NoteOrganizer_TestPlan.xlsx`) for scenarios
  not worth automating.
- **Build:** packaged via PyInstaller using `NoteOrganizer.spec`
  (`--windowed`, one-folder output to `dist/NoteOrganizer/`).

For anything non-trivial, `docs/ARCHITECTURE.md`, `docs/ISSUES_LOG.md`, and
`docs/ROADMAP.md` contain real, hard-won context — read them before assuming
something is a bug or an obvious improvement. Treat documentation as a
strong signal, not gospel: verify important claims against the actual code,
since docs can drift out of date.

## Project focus

This project is currently focused **exclusively** on the desktop
application. The current goal is to improve and stabilize the existing
Windows desktop app **without changing its fundamental platform or UI
technology.**

**Android/mobile development is intentionally out of scope for now.**

Do not:
- implement Android support;
- introduce Kivy, BeeWare, Flutter, React Native, or any other mobile
  framework;
- restructure the project specifically to prepare for Android;
- add mobile-specific abstractions unless explicitly requested.

Android may be discussed as future context, but do not implement or
optimize for it unless explicitly instructed.

## Working rules

### Before making changes

- Inspect the relevant existing code first.
- Understand the current implementation before proposing changes.
- Do not modify files when asked to investigate, inspect, audit, explain,
  or analyze something.
- If the requested change is ambiguous or could have significant
  architectural consequences, explain the proposed approach before editing.

### Scope control

- Make the smallest change that correctly solves the requested problem.
- Do not refactor unrelated code while fixing a bug.
- Do not reorganize the project unless explicitly requested.
- Do not rewrite large sections of working code simply because another
  design would be cleaner.
- Do not introduce new dependencies unless explicitly justified and
  approved.
- Preserve existing behavior outside the requested change.

### Architectural changes

- Treat the current architecture as intentional unless the task explicitly
  asks for architectural work.
- Do not split, rename, or move major parts of the application without
  first explaining the proposed changes.
- Do not begin an Android-oriented architecture migration.
- Prefer incremental changes over large rewrites.

### Approval before larger changes

- For changes that affect multiple files, architecture, data format,
  persistence behavior, or a large portion of the UI, first explain the
  proposed plan and wait for approval before editing.
- For small, localized bug fixes with clear scope, proceed directly.

### Testing

After making a change:
1. Run the most relevant existing tests.
2. Run broader tests when practical.
3. Report exactly what was tested and the result.
4. If tests cannot be run, say why.
5. Do not silently ignore unrelated test failures.

When fixing a bug, prefer adding a regression test when practical.

### File safety

Before editing:
- Know which files are expected to change.
- Avoid modifying documentation, configuration, or unrelated files unless
  required by the task.
- Do not delete files or data without explicit approval.

### Reporting changes

After completing a task, report:

1. What changed.
2. Which files changed.
3. Why the change was made.
4. Tests/checks that were run.
5. Any remaining risks or uncertainties.

Do not claim something was tested or verified if it was not actually
tested.

## Existing project documentation

Before making architectural or behavioral decisions, consult the relevant
documentation under `docs/`, especially:

- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/ISSUES_LOG.md`
- `docs/USER_GUIDE.md`

Do not assume that documentation is necessarily correct. When important,
verify claims against the actual source code.

## Important principle

When in doubt, investigate first and modify second.

Do not make broad improvements simply because they seem useful. Stay
within the explicit scope of the current task.
