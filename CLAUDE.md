# NoteOrganizer — Claude Code Instructions

## Project overview

Note Organizer is a fully offline desktop notes app: Python + Tkinter, one
runtime dependency (Pillow, for image/GIF preview rendering). No network
calls, no accounts, no database.

- **Organised as a package (split complete, stopped deliberately):** the
  app was a single file by design for most of its life; it now lives as a
  `core/` layer (data and rules; **must never import tkinter**) and a `ui/`
  layer of mixin classes — thirteen `core/` modules and five `ui/` mixins —
  with `note_organizer.py` (~13,250 lines) remaining the entry point and
  the genuinely shared UI hub, by measurement rather than by neglect (see
  `docs/ARCHITECTURE.md`'s call-graph case study for why the split stopped
  where it did). The entry file re-exports whatever has moved, so
  `py note_organizer.py`, `import note_organizer as NO` in the QA scripts,
  and the PyInstaller build all keep working untouched. If a further
  extraction is ever attempted, it must be a pure move that leaves the full
  test suite green — if a step needs behaviour changes to pass, split the
  step. `docs/CODE_TOUR.md` is the annotated walkthrough.
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
- **Testing:** the `test_*.py` files are standalone unit-style suites —
  `test_recurrence.py`, `test_calculator.py`, `test_data_safety.py`,
  `test_richtext.py` and `test_tables.py` need no GUI;
  `test_entry_module_identity.py` builds a window. `qa/qa1.py`–`qa9.py` are
  headless GUI tests, each starting from a clean data directory. All of them
  run automatically via `.github/workflows/tests.yml` on every push/PR — on
  **both** Windows and Linux (the Linux job supplies the display via Xvfb;
  Windows runs through native win32). There's also a manual test plan
  spreadsheet (`qa/NoteOrganizer_TestPlan.xlsx`) for scenarios not worth
  automating.
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

**Permanent fixes only (standing rule, 2026-09-05).** Every failure —
in the app or in a check — gets a fix at the root of its *class*, not a
patch over the instance, so the same failure cannot reappear:

1. Diagnose the mechanism, not the symptom. Name what class of failure
   it belongs to.
2. Fix the class: sweep the codebase/suite for every sibling with the
   same mechanism and fix those in the same change.
3. Prove the fix's asymmetry: after it, the thing may only fail when
   the promised behaviour is genuinely broken (for checks, that means
   the mutant still fails hard while load/timing can no longer produce
   a false red).
4. Record the lesson where the next person will meet it (qa/README's
   house rules for test strategy; ISSUES_LOG for app mechanisms).

A flaky check is a bug in the check's strategy and gets this same
treatment — "re-run it and it went green" is never the resolution.

### Cross-feature verification (standing rule, 2026-08-28; extended 2026-09-05 with the interaction pass)

A new feature is not done when it works alone — it is done when the
older features it crosses still work with it. And that thinking starts
BEFORE the first line of code, not at the end:

0. **The interaction pass (before code).** For any feature or
   improvement beyond a trivial fix, walk the FULL surface inventory in
   `qa/README.md` ("The surface inventory") — every row, every time,
   never just what comes to mind — and give each an explicit verdict:
   `none` / `touches` / `risky — with the weaving decision`. Where the
   new work couples two existing surfaces in a new way (as find-in-note
   coupled theming with tables), name that pair explicitly. Present the
   resulting table together with the plan, before editing anything.
   The point of walking all of it is that nothing can be missed by not
   being thought of.

Then, before reporting the change complete:

1. The pass's `touches`/`risky` rows are the list of seams — kept
   honest by the full walk above, not by memory.
2. Probe each seam, and add a qa check for every risky one. The check
   lands with the feature, not after a field test finds the gap —
   mutation-tested, per qa/README's house rules.
3. Accept the extra work; the theme switch silently stopped recoloring
   tables precisely because no check covered that seam.

The quality bar that goes with it: the app stays efficient enough for
weak machines, and a failure must not reach the user's face — guard the
UI entry points and let the crash log carry the details. Blanket
try/except everywhere is not the goal; hiding bugs is worse than
logging them.

### QA testing safety (hard rule — real data has been lost to this three times)

**This rule covers EVERY test file — `qa*.py` AND all `test_*.py` — with
no per-file safety judgments.** Running the `qa*.py` scripts requires a
working copy of `note_organizer.py` next to them, and each script wipes
`*.json` and `attachments/` in its working directory before running.
**This working directory must never be the project's own `qa/` folder in
place.** Copying files into `qa/` and cleaning up there has twice caused
a misdirected command to instead wipe the real `notes_data.json`,
`trash.json`, `templates.json`, `settings.json`, and `attachments/` at
the project root — both are git-ignored, so `git status` never flags the
damage.

The third loss came from the unit tests, which an earlier version of this
rule did not name: `test_data_safety.py` deletes and rewrites
`notes_data.json` in its own directory, and being run from the project
root (during a routine full-suite sweep) it destroyed the real notebook —
recovered only because the app's own `notes_data_backup_*.json` existed,
minus that day's work. Most unit tests are genuinely pure; that is
exactly what made the dangerous one easy to misfile. The test now refuses
to run beside a `notes_data.json` that holds real notes, but the refusal
is the LAST line of defence, not permission to run tests in place.

The safest way is to let `tools/run_tests.py` do it for you: it makes a
fresh temp folder far outside the project, copies in `note_organizer.py`,
the `noteorganizer/` package and the tests, runs everything (units +
qa1–qa9, plus the two static gates CI runs) there, and deletes the folder
afterward — the project's own files are only ever read (`py
tools/run_tests.py`, or `py tools/run_tests.py qa6` for one script). The
manual ritual below is the fallback, and the reason that tool exists.

Instead (by hand): copy `note_organizer.py`, the `noteorganizer/` package,
and the target test script into a scratch directory **outside the project
tree entirely** (e.g. the session's own scratchpad folder), and run and
clean up there. This makes it physically impossible for a wrong-directory
mistake to reach real user data, rather than relying on correctly
remembering the working directory every single time.

The `noteorganizer/` package must travel with `note_organizer.py` — the
latter imports from it, so a copy on its own now fails with
`ModuleNotFoundError`. Copy the whole directory (`cp -r`), not just the
modules currently in use.

This applies to "quick" runs too: a pre-commit sweep like
`for t in test_*; do py $t.py; done` from the project root is exactly how
the third loss happened. The scratch copy costs seconds; run everything
there, every time.

If a destructive command must reference `notes_data.json`, `trash.json`,
`templates.json`, `settings.json`, or `attachments/` for any other reason,
always use a fully-qualified absolute path — never a bare relative
pattern like `*.json` — as a second layer of protection. Verify the
working directory (`pwd`) immediately before any destructive command,
every time, not just when something already looks risky.

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

### Versioning

The full policy (exact counting rules, what happens at the real 1.0.0
launch, Microsoft Store/Android specifics) lives in `docs/ROADMAP.md`'s
"Versioning" section — treat that as the source of truth, not this
summary.

- A version bump belongs with the code change it covers, not as an
  afterthought: whenever `note_organizer.py` changes and is about to be
  rebuilt into a new `.exe`, recompute the version per the documented
  policy and propose the exact new number.
- Always show the computed number and how it was derived, and wait for
  explicit confirmation before bumping `APP_VERSION` or cutting a
  `CHANGELOG.md` version section — never bump it silently as part of an
  unrelated change.
- Docs-only changes do not get a version bump, matching how they don't
  call for an `.exe` rebuild either.

## Git & GitHub workflow

### Branches

- `main` is the stable branch — never commit ordinary development work directly on it.
- Every bug fix, feature, refactor, or test addition gets its own branch, named
  `fix/...`, `feat/...`, `refactor/...`, `test/...`, or `docs/...`.
- Keep each branch focused on one logical task; don't mix unrelated changes
  into it unless explicitly asked to.

### Commits

- Make small, logical commits with messages that clearly describe the change.
- Always inspect `git diff` and `git status` before committing.
- Never commit files or changes that weren't part of the requested task
  without asking first.

### Push

- Never push automatically after making a change.
- Before pushing, show:
  - the branch name;
  - the commit(s) that will be pushed;
  - the files changed;
  - the tests/checks performed.
- Wait for explicit user approval before running `git push`.

### Pull requests

- Do not automatically create or merge pull requests.
- The user decides whether and when to open or merge a PR.
- GitHub CLI (`gh`) is currently not installed.
- Until `gh` is available, after pushing a branch, provide the GitHub PR
  creation link plus ready-to-paste PR title, description, and suggested label.
- Never merge a PR into `main` without explicit user approval.

### Main / remote safety

- Never force-push to `main`.
- Never use destructive Git commands (`reset --hard`, deleting branches,
  rewriting history, etc.) unless explicitly approved for that exact operation.
- Never overwrite or discard the user's existing uncommitted work.
- If pre-existing changes are found that weren't made by this session,
  stop and report them before touching anything.

### Working tree

- Inspect `git status` at the start of a task.
- Distinguish between changes made during the task and anything that already existed.
- Report the final `git status` at the end of a task.
- Do not leave the working tree with unexplained changes.

### After the user merges a PR on GitHub

- After the user confirms that a PR has been merged, switch to `main`,
  fetch/pull the latest `main`, prune stale remote-tracking references,
  and delete the local feature branch with `git branch -d`.
- Do not perform these cleanup operations automatically before the user
  confirms the merge.
- After code changes are merged into `main`, remind the user that the
  packaged `.exe` should be rebuilt and tested before release.
- Do not automatically create a release build unless explicitly requested.

### Approval required every time

The following always require explicit approval in the moment, even if
something similar was approved earlier:

- `git push`
- merge
- PR creation
- force push
- branch deletion
- history rewriting
- other destructive Git operations

Before running a command that requires approval, briefly explain what
the command will do.

## Full lifecycle for an issue or enhancement

1. Investigate the relevant code and documentation first.
2. For anything non-trivial, explain the proposed approach in plain language
   and wait for approval before editing.
3. Create a dedicated branch.
4. Implement the smallest change that correctly solves the requested problem.
5. Run the most relevant existing tests and broader tests when practical.
6. For bug fixes, add a regression test when practical.
7. Report the actual test results honestly.
8. Show the relevant diff before committing.
9. Commit with a clear, focused message.
10. Show the branch, commits, changed files, and tests performed.
11. Wait for explicit approval before pushing.
12. After pushing, provide the PR creation link and suggested PR title/body/label.
13. Wait for the user to review and merge the PR.
14. After the user confirms the merge, synchronize local `main`,
    prune stale references, and safely delete the local feature branch.
15. Remind the user to rebuild and test the `.exe` when packaged application
    code has changed.
16. Update `CHANGELOG.md`, `docs/ROADMAP.md`, or `docs/ISSUES_LOG.md`
    only when appropriate and as an explicit, reviewed part of the task.

## Code quality bar

Beyond making the requested change work, actively check what a normal,
non-malicious user's ordinary interaction does to any new code path —
not just the intended scenario.

Before considering a fix complete, ask:

- What happens if the user does this slowly?
- What happens if the input is only partially entered?
- What happens if the user clicks away mid-action?
- What happens if the action happens twice?
- What happens if the operation is interrupted or repeated?

The date-autosave fix in this project is a direct example: a fix can work
for the intended case while breaking normal mid-typing or partial-input
behavior. Explicitly test realistic interaction paths before considering
the change ready for merge.

## Documentation standards (standing rule, 2026-09-04)

The documentation serves both technical and non-technical readers, and it
is part of the product. Every docs change — documenting a new feature,
updating after a fix, or restructuring — follows these principles without
being re-asked:

- **Progressive disclosure.** Every major doc opens with a short,
  plain-language layer anyone can follow; behaviour and context next;
  implementation depth last. A reader should be able to stop early and
  still get the point.
- **Information density over word count.** Cut repetition, filler, and
  restated context — never substance. Decisions, trade-offs, constraints,
  and the stories behind fixes stay.
- **History is preserved, organized, never flattened.** CHANGELOG entries,
  ISSUES_LOG stories, and ROADMAP history are not deleted or summarized
  away; make them scannable with indexes, dates, grouping, and links.
  CHANGELOG's Added/Fixed bullet **counts are an invariant** — the version
  number is derived from them (see Versioning), so compression may shorten
  a bullet but never merge or split bullets.
- **One canonical home per topic.** Detail lives in exactly one doc; every
  other mention is a line plus a link. Homes: usage → `USER_GUIDE`,
  design decisions → `ARCHITECTURE`, code walkthrough → `CODE_TOUR`,
  release deltas → `CHANGELOG`, investigations → `ISSUES_LOG`,
  plans/versioning → `ROADMAP`, test map and house rules → `qa/README`,
  git commands → `GIT_WORKFLOW`.
- **README is the hub and stays a 1–2 minute read**: curated highlights
  rather than exhaustive lists, one hero screenshot plus a small gallery
  row, and a reader-routing Documentation section linking every deeper
  doc. No separate docs index file.
- **Style.** Short paragraphs — no single-line walls of text; real
  headings (they give anchors) instead of bold run-in pseudo-headings;
  small tables for keystrokes and comparisons; a TOC on any long doc;
  links instead of prose citations of other docs' section titles; wrap
  source lines at a readable width.
- **Terminology is consistent across all docs**: "Trash" (with
  "Settings → Recently deleted" on first mention per doc), "the entry
  file (`note_organizer.py`)", "the qa suite (qa1–qa9)" vs "the unit
  suites (`test_*.py`)", "popup" for anchored non-blocking windows vs
  "dialog" for blocking asks.
- Docs-only changes still get no version bump, matching the Versioning
  policy.

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
