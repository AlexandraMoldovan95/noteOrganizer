# NoteOrganizer — Claude Code Instructions

> **For human readers.** This file is written to the AI agent the project is built with (Claude
> Code), which reads it at the start of every session. It is public on purpose: it is the working
> agreement between the owner and the agent. Most rules carry a date and a reason because they were
> agreed right after something went wrong — the stories are in the
> [Issues Log](docs/ISSUES_LOG.md). Which rules are enforced by tools and which are only asked of
> the agent is set out in
> [How Note Organizer is built with an AI agent](docs/AI_WORKFLOW.md#what-is-enforced-and-what-is-only-asked).

**Contents:** [Project overview](#project-overview) ·
[Project focus](#project-focus) ·
[Working rules](#working-rules) — [Testing](#testing),
[Cross-feature verification](#cross-feature-verification-standing-rule-2026-08-28-extended-2026-09-05-with-the-interaction-pass),
[QA testing safety](#qa-testing-safety-hard-rule--real-data-has-been-lost-to-this-three-times),
[What runs without asking](#what-runs-without-asking-permission-policy-2026-09-25),
[Versioning](#versioning) ·
[Git & GitHub workflow](#git--github-workflow) ·
[Full lifecycle](#full-lifecycle-for-an-issue-or-enhancement) ·
[Code quality bar](#code-quality-bar) ·
[Documentation standards](#documentation-standards-standing-rule-2026-09-04) ·
[Agent protocol](#agent-protocol-standing-rule-2026-09-05)

## Project overview

Note Organizer is a fully offline desktop notes app: Python + Tkinter, one
runtime dependency (Pillow, for image/GIF preview rendering). No network
calls, no accounts, no database. (Settings → About opens the privacy
policy, and — once the app is in the Store — its review page, in the
browser; feedback is a Store review, and the app itself connects to
nothing — `core/diagnostics.py`.)

- **Organised as a package (split complete, stopped deliberately):** the
  app was a single file by design for most of its life; it now lives as a
  `core/` layer (data and rules; **must never import tkinter**) and a `ui/`
  layer of mixin classes — eighteen `core/` modules and seven `ui/` mixins —
  with `note_organizer.py` (~21,900 lines) remaining the entry point and
  the genuinely shared UI hub, by measurement rather than by neglect (see
  `docs/ARCHITECTURE.md`'s call-graph case study for why the split stopped
  where it did, and why the note list moved later, once re-measured). The
  entry file re-exports whatever has moved, so
  `py note_organizer.py`, `import note_organizer as NO` in the QA scripts,
  and the PyInstaller build all keep working untouched. If a further
  extraction is ever attempted, it must be a pure move that leaves the full
  test suite green — if a step needs behaviour changes to pass, split the
  step. `docs/CODE_TOUR.md` is the annotated walkthrough.
- **Storage:** plain local JSON — `notes_data.json`, `settings.json`,
  `trash.json`, `templates.json` — plus an `attachments/` folder, no
  database. Location is chosen by `resolve_data_dir()`: beside the script
  when run from source — or in the folder a git-ignored
  `notebook_location.txt` beside it names, which keeps the owner's own
  source-run notebook out of the working tree (since 2026-10-08) —
  `%APPDATA%\NoteOrganizer` when running as the built `.exe`. Every note passes through `normalize_note()` as a single choke
  point that coerces malformed/missing fields to safe defaults.
- **UI:** every dropdown, popup, and dialog the app draws is a hand-built
  `Toplevel`. The system's own dialogs appear in exactly two situations,
  both deliberate: **choosing a file or folder** (`filedialog`, five call
  sites — save an export, open a backup `.zip`, pick a folder, attach
  files), because the OS chooser knows the user's drives and recent places
  and a hand-built one would be worse; and **the app failing to start**
  (the last-resort startup-crash dialog, and "Missing dependency" when
  Pillow is not installed). This line used to say "no native OS dialogs anywhere except the
  startup-crash dialog", which was wrong about the code while the code was
  right. Two different, deliberate theming patterns exist
  (`track_theme()` for persistent widgets vs. plain `.configure()` for
  widgets that get rebuilt on every refresh) — see `docs/ARCHITECTURE.md`
  before touching theming code; mixing these up has caused a real
  perf regression before (see `docs/ISSUES_LOG.md`). Every size in
  pixels that holds text or a drawn mark is written as at 100% and grown
  through `px()`, `_SIZES_AT_100` or `_scale_drawing()`. With Sharp text
  on, fonts grow on a scaled screen while bare pixel sizes do not, and
  the words get cut ("Sharp on a scaled screen" in `docs/ARCHITECTURE.md`).
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
  `test_richtext.py`, `test_tables.py`, `test_note_identity.py` and
  `test_spelling.py` need no GUI; `test_entry_module_identity.py` builds a window. `qa/qa1.py`–`qa9.py` are
  headless GUI tests, each starting from a clean data directory. All of them
  run automatically via `.github/workflows/tests.yml` on every pull request
  and every push to `main` that changes more than the documentation — on
  **both** Windows and Linux (the Linux job supplies the display via Xvfb;
  Windows runs through native win32). There's also a manual test plan
  spreadsheet (`qa/NoteOrganizer_TestPlan.xlsx`) for scenarios not worth
  automating.
- **Build:** packaged via PyInstaller using `NoteOrganizer.spec`
  (`--windowed`, one-folder output to `dist/NoteOrganizer/`).
- **Website:** `site/` holds the site that presents both apps and a web
  demo of each (re-creations of their interfaces in HTML and JavaScript;
  the build also reads the Android repository, beside this one, and never
  writes to it), published
  on Netlify. It is edited only there; `py site/build.py` builds it into
  `site/public/` (not in git), which is dragged onto Netlify by hand, with
  changes gathered into one upload because every deploy costs credits. The
  test workflow ignores `site/`; its own checks are in `site/tools/`.
  See `site/README.md`. **Kept apart from the apps (the owner's rule,
  2026-10-21):** the site may link to the apps' store pages, but nothing
  the apps' users see — the apps, their store listings (website field left
  empty), their privacy policy on Google Sites — ever points at the site.

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

**Who verifies what (standing rule, 2026-09-13).** Agreed after a field
test found four user-visible bugs the suite could not reach, and a story
written afterwards caught all four when they were put back:

- **Anything that can be proved mechanically is proved here, before
  saying it is done** — not handed over as "please check this on the
  exe". For a user-facing change that means walking it on the real app:
  `py qa/story_note_travels.py` and the stories beside it press the
  buttons a person presses, restart the process where a person would
  close the app, and photograph the app's window — never the whole
  screen, which takes the owner's other open windows with it. The
  photographs are looked at, not merely saved.
- **The test plan still gets the row** (`qa/NoteOrganizer_TestPlan.xlsx`),
  because a second pair of eyes on the built `.exe` catches what a script
  was never told to look for. Its "Automation status (Claude)" column
  must say plainly when a story already walks the case end to end, so a
  hand check is a choice rather than a duty.
- **What needs human judgement is named out loud.** After every fix, ask:
  *which part of this can no script see?* — whether something reads as
  confusing, whether the safer answer is the one the eye lands on,
  whether a screen means what it says. Those go to her explicitly AND
  into the test plan marked as needing her eye. A script checks what it
  was told to check; it never notices that a button *looks* like a trap.

After making a change:
1. Run the most relevant existing tests.
2. Run broader tests when practical.
3. Report exactly what was tested and the result.
4. If tests cannot be run, say why.
5. Do not silently ignore unrelated test failures.

When fixing a bug, prefer adding a regression test when practical.

**The pre-flight, before writing any fix (standing rule, 2026-09-11).**
Agents are expensive; greps are free. Every omission an adversarial
review has caught in this project came from skipping one of these four
steps, so they run FIRST, on every fix, and what they find is part of
the fix rather than of the next review round:

1. **Name the mechanism in one sentence** — not the symptom, not the
   route it was reported on. If the sentence names a file, it is still
   a symptom; keep going until it names a behaviour.
2. **Grep for siblings of that mechanism** and list every hit before
   editing: the same question asked elsewhere, the same field list
   written out twice, the same constant repeated. Fix all of them, or
   write down why a hit is genuinely different. (Missing this fixed 1
   of 6 emptiness guards and 1 of 3 content signatures.)
3. **Enumerate the readers** of any value whose definition changes. If
   what gets STORED changes, grep every consumer of that field and
   check each still agrees. (Missing this left the dirty comparator
   stripping a body the save had just learned to keep.)
4. **Round-trip the change against the heavy features** with a small
   local probe — tables, recurrence/occurrences, attachments,
   formatting — before believing it. (Missing this shipped a
   regression where every table-ending note read as permanently
   unsaved.)

Then the mutant, as always: revert the fix, watch the check fail, with
the suite reaching its FAILURES footer. Steps 2–4 plus the mutant cost
seconds and catch the mechanical omissions; reviewers are for judgment
and adversarial imagination, which is what they should be paid for.

Two things a mutant runner must do, both learned the hard way:

- **Restore the source in a `finally`.** One exited on an error with a
  mutant still in the file. A tool that can leave the code broken is a
  worse bug than anything it was written to find.
- **Read and write the file as BYTES.** Reading text and writing it back
  with `newline="\n"` rewrites every line ending in the file, so a
  "restore" that changed nothing still left two files rewritten end to
  end. The content was identical and `git diff` was empty, which is
  precisely why it went unnoticed until `git status` disagreed.

`tools/mutate.py` is that runner, committed: it works on a fresh copy, so
the source is never written and there is nothing to restore, and its
catalogue of mutants worth keeping is `tools/mutants.json`.

**Permanent fixes only (standing rule, 2026-09-05).** Every failure —
in the app or in a check — gets a fix at the root of its *class*, not a
patch over the instance, so the same failure cannot reappear:

1. Diagnose the mechanism, not the symptom. Name what class of failure
   it belongs to.
2. Fix the class: sweep the codebase/suite for every sibling with the
   same mechanism and fix those in the same change. And for a reported
   bug, sweep the FEATURE's neighbourhood too: walk the affected
   feature's row in the interaction inventory — its producers,
   consumers and seams — probing each for related breakage before the
   fix is declared done. A report about one seam is evidence the
   neighbouring seams were never exercised either (the field report
   about a shared note's missing checklist turned out to also cover
   formatting and paragraphs, silently dropped on the same route).
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
qa1–qa9, plus the static gates CI runs) there, and deletes the folder
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

### What runs without asking (permission policy, 2026-09-25)

The lists live in `.claude/settings.json`, which is **git-ignored on
purpose** — it holds absolute paths and one machine's home directory. That
means the policy can be lost with the machine, so it is written here in
words as well. Agreed after the lists had grown to ~90 entries that were
almost all one-off exact commands (full scratchpad paths, exact line
ranges, whole commit messages), so nothing matched twice and every
ordinary step asked again.

Three tiers:

- **Runs without asking:** read-only git (`status`, `diff`, `log`, `show`,
  `blame`, `fetch`, `pull --ff-only`), `git add` / `git commit` / new
  branches, `tools/run_tests.py` and every `tools/check_*.py`, the Linux
  CI image, the three story scripts (`qa/story_look.py`,
  `qa/story_audit.py`, `qa/story_note_travels.py` — see below), anything
  inside the session scratchpad, and edits to files in the repository.
- **Always asks:** `git push`, merge, PR creation, `git branch -d`, any
  `rm`, the PyInstaller build.
- **Denied outright, by the system:** running the qa suite (`qa1`–`qa9`),
  `qa/probe_bar_width.py`, any `test_*.py`, or `note_organizer.py` itself
  inside the project tree; `reset --hard`,
  `push --force`, `rebase`, `branch -D`, `restore`, `clean`; installing
  anything; and reading or writing `%APPDATA%\NoteOrganizer` or the real
  data files at the project root.

The last tier is the point: the [QA testing safety](#qa-testing-safety-hard-rule--real-data-has-been-lost-to-this-three-times)
rule stops depending on an agent remembering it. The chat protocol is
unchanged and independent — push, merge and PR creation are still
explained and approved in the moment, whatever the permission system says.

Two things learned while writing it, both worth keeping:

- **A prefix rule that stops inside a word never fires.** `Bash(py test_:*)`
  matched nothing; the deny list looked complete and protected nothing.
  Found by probing a harmless member of the rule shape (`py test_recurrence.py`,
  which touches no data files) and watching it run. Every dangerous script
  is now named in full, in each spelling that could reach it. That claim
  once read "204 spellings, none uncovered" while 141 bare and `./` forms
  were missing (a `:*` rule needs something after the name); it is now a
  gate, not a sentence: the deny tier is committed without this machine's
  paths as `tools/agent_deny_rules.json`, and `tools/check_agent_rules.py`
  finds the destructive scripts itself and fails on any uncovered spelling
  — and, here, on any committed rule the live lists lack.
- **Never probe a destructive deny rule with the destructive command.**
  Whether `py test_data_safety.py` is blocked is verified by reading the
  list, not by running it: if the rule were wrong, the probe would delete
  the notebook it was meant to protect.

**The story scripts moved from denied to allowed (2026-09-28), and why.**
The rule above once read "the screenshot tools" under *always asks*, while
the lists themselves had no `ask` tier at all and put all three story
scripts in `deny` — swept there with `qa1`–`qa9` because they live in the
same folder. The effect was that the [testing rule's](#testing) own
instruction, *walk a user-facing change on the real app with the story
scripts and look at the photographs*, could not be followed by an agent at
all. It surfaced when five visual changes shipped with nobody having
looked at them.

They are allowed now because the hazard the deny list exists to stop is
structurally impossible for them, which was **read in their code rather
than assumed**. Each one does what the
[QA testing safety](#qa-testing-safety-hard-rule--real-data-has-been-lost-to-this-three-times)
rule prescribes, in its own source:

```python
work = tempfile.mkdtemp(prefix=...)
shutil.copy2(<root>/note_organizer.py, work)
shutil.copytree(<root>/noteorganizer, work/noteorganizer)
io.open(os.path.join(work, "notes_data.json"), "w")...   # the seed, inside work
subprocess.run([...], cwd=work)
```

The seed is written **inside** the temp directory and the app runs with its
working directory there, so a wrong-directory mistake cannot reach the real
notebook. `qa1`–`qa9` stay denied, in every spelling, because
those genuinely wipe `*.json` in whatever directory they are run from — and
so does `qa/probe_bar_width.py`, which builds the app the same way.

Two things this cost, both worth not repeating:

- **A written policy and its configuration can disagree silently.** This
  one did for three weeks, and the config won every time. When a rule here
  describes what the lists do, check it against the lists rather than
  against memory.
- **Do not route around a deny rule.** When a command is refused, the
  answer is to say so and ask — not to try a different spelling until one
  gets through. The deny tier exists precisely because an agent's judgement
  about whether *this particular* run is safe is the thing that failed
  three times.

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
- **The privacy page, at every release (the owner's rule, 2026-10-21).**
  The privacy policy both apps open and both stores are given lives on
  Google Sites, as a copy of `docs/PRIVACY.md` the owner makes by hand —
  so nothing keeps the two in step but this. Every release cut, desktop or
  Android, asks whether the text changed or the release changes what the
  apps keep, send or open; if so, the owner republishes the page BEFORE
  the build goes out, and the live page is compared with the file either
  way. No build ships until the page, opened signed out, shows the
  policy's text — a Site that is missing or private sends visitors to a
  Google sign-in page instead of an error. The steps are in
  [RELEASE_WINDOWS](docs/RELEASE_WINDOWS.md#the-privacy-page-at-every-release).

## Git & GitHub workflow

### Branches

- `main` is the stable branch — never commit ordinary development work directly on it.
- Every bug fix, feature, refactor, or test addition gets its own branch, named
  `fix/...`, `feat/...`, `refactor/...`, `test/...`, or `docs/...`.
- Keep each branch focused on one logical task; don't mix unrelated changes
  into it unless explicitly asked to.
- Exception by agreement (2026-09-05): small, *related* docs-only changes
  may share one branch/PR to reduce review ceremony. Code changes always
  get their own branch.

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
- GitHub CLI (`gh`) is not installed — a deliberate choice (2026-09-05),
  not a gap: the user reviews PR texts here before they go up, and wants
  to stay hands-on with the GitHub side. Do not propose installing it.
- After pushing a branch, provide the GitHub PR creation link plus
  ready-to-paste PR title, description, and suggested label.
- **When an issue accompanies a PR** (agreed 2026-09-05): a user-visible
  bug — field-reported or shipped to `main` — gets an issue, and its PR
  description carries `Fixes #N`; provide ready-to-paste issue title and
  body alongside the PR text. Enhancements are tracked in ROADMAP, not
  issues. Internal-only work (tests, docs, refactors) needs no issue.
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
- **Release-time freshness check (agreed 2026-09-05).** Every release cut
  includes an unprompted currency pass over all `.md` files — the
  audit-all-docs discipline, on a schedule instead of on request. When
  shipped work has accumulated enough to warrant it, proactively propose
  a full editorial audit rather than waiting to be asked.

## Agent protocol (standing rule, 2026-09-05)

For any work that fans out to subagents (audits, rewrites, parallel
builds):

- **Ownership.** An agent reads or edits only the area it is assigned;
  agents that write files get isolated worktrees where they could
  collide. Changes to the hub (`note_organizer.py`) or `core/` integrate
  only through the session itself — the session is the integrator,
  because it carries the seam map and the memory.
- **Coverage confession.** Every agent report ends with what was NOT
  covered — files skipped, cases untried, checks not run. An audit that
  does not declare its gaps is more dangerous than an incomplete one.
- **Real numbers only.** Aggregation never smooths results: failed
  rounds, raw scores, and open gaps reach the user as they are. Never
  inflate, never summarize a failure into silence.

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
