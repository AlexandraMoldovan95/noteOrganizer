# The qa suite — read me before touching a guarded surface

Nine scripts, ~1,070 checks (the six unit suites beside them bring the
whole run to ~1,540), all driving the real app headlessly (Xvfb on
Linux CI, real Windows Tk on the Windows CI job and every dev machine).
The manual half of the QA story sits beside them:
`NoteOrganizer_TestPlan.xlsx`, the structured test plan for scenarios
easier to eyeball than to automate.

What all of it actually executes is measured: `py tools/run_coverage.py`
prints the line-coverage total, the per-file table and the largest
never-executed regions. The current baseline (81.5%), the per-layer
targets, and the ledger where every agent report's "NOT COVERED"
confession receives an explicit verdict live in
[`COVERAGE_LEDGER.md`](COVERAGE_LEDGER.md) — a confession may land
there, never scroll past.

## What each script owns

| Script | Primary ground |
|---|---|
| `qa1` | notes, categories, templates — plus the editor's heaviest surfaces: tables, rich text, the find bar, bulk actions |
| `qa2` | recurrence, calendar, duplicates |
| `qa3` | trash, sharing, import/export |
| `qa4` | theming, stress tests, leak regression |
| `qa5` | corrupt data, edge cases |
| `qa6` | grouping, settings, attachments, multi-feature combinations |
| `qa7` | calendar delete, the calendar History register, multi-select, image preview, autosave & memory fixes |
| `qa8` | search debounce, background-timer robustness |
| `qa9` | the nested-dropdown-inside-popup fix |

Beside the GUI suite run six standalone **unit suites**, each runnable on
its own (`py test_<name>.py`, from a scratch copy like everything else):
`test_recurrence`, `test_calculator`, `test_data_safety`, `test_richtext`,
`test_tables` need no GUI; `test_entry_module_identity` builds a window —
it guards against a second copy of the entry module.

Each script's banner carries the finer print. "Primary" matters: checks
about one surface deliberately live in several files — which is the
first of two things here that are not obvious from the file names, and
both have cost a red CI run to learn:

## The seam map: one surface, many guards

A check about one UI surface does not necessarily live in "its" file.
The bulk-action bar taught this the expensive way: it was resized in a
round that updated qa1's checks — and a reconstruction-based check in
**qa7** (written months earlier) went red only on CI. **When you change
one of the surfaces below, sweep every file listed for it**, not just
the one you happen to be editing:

| Surface | Guarded in |
|---|---|
| Bulk-action bar / selection mode | **qa7**, **qa1** |
| Theming (apply/track/toggle) | **qa1**, **qa4**, qa6 |
| Autosave (debounce, guards, flush) | **qa8**, **qa7**, **qa1**, qa5, qa2, qa6, qa3 |
| Editor page scroll/canvas | **qa1**, **qa8**, qa6 |
| Note list (refresh, scroll guards, grouping) | **qa7**, **qa1**, qa6, qa8, qa4, qa5 |
| Tables / drawn grids | **qa1**, qa7, qa5, qa2, qa3 |
| Find in note (Ctrl+F) / find bar | **qa1**, qa5 |
| Templates | **qa9**, **qa1**, **qa6**, qa3, qa7, qa4 |
| Settings panels | **qa6**, qa7, qa4, qa3 |
| Calendar | **qa7**, qa2, qa5, qa1, qa8, qa9, qa4, qa6, qa3 |
| Trash | **qa3**, **qa7**, qa6, qa1, qa4, qa5 |
| Share codes | **qa3**, qa5, qa1 |
| Export (files, backup) | **qa3**, **qa1**, qa6, qa8, qa4, qa5 |
| Attachments | **qa7**, qa6, qa3, qa4, qa1, qa8, qa2, qa5 |
| Recurrence / occurrences | **qa7**, **qa2**, qa8, qa5, qa3, qa4, qa1 |
| Checklist | **qa1**, qa7, qa3, qa6, qa2, qa4, qa5, qa8, qa9 |
| Formatting / rich text | **qa1**, qa3, qa2, qa9, qa7, qa6 |

Bold = the heavy owner(s): a file carrying at least a quarter of a
surface's mentions, or leading the next one by more than double.

**Regenerate it rather than editing it** — `py tools/regen_seam_map.py`
prints the table above, plus the raw per-file counts it came from. The
table used to be refreshed by hand and drifted through three audit
rounds without anyone re-running it (coverage-ledger C8): three whole
surfaces were missing — recurrence/occurrences, the checklist and rich
text — and several rows named fewer files than actually guard them, so
a sweep that trusted it would have skipped exactly the file that went
red on CI last time. Counts are mentions, not checks; they say where a
surface is *touched*, which is what a sweep needs.

## Running anything here

**Never in place.** Every script wipes `*.json` and `attachments/` in
its working directory first — run from the project root, that is the
real notebook (it has happened; see [CLAUDE.md](../CLAUDE.md),
"QA testing safety").
`py tools/run_tests.py` does the whole safe-scratch ritual for you and
is the verdict that counts before a push; `py tools/pre_push_check.py`
is the two-second static half (names, API surface, compile-all) you
run before *every* push. The CI's **Linux leg** runs locally too, via
Docker (`tools/linux-ci/` — build once, then
`docker run --rm -v "${PWD}:/repo:ro" noteorg-linux-ci`), so the
Xvfb-only behaviours that used to surface as red CI runs can be caught
before the push.

## Stories: the app walked, not questioned

`py qa/story_note_travels.py` is a different kind of check, and it exists
because of a specific failure. Four user-visible bugs shipped in
`0.73.159` and `0.73.161`; a field test found all four in twenty minutes,
and not one of them was reachable by the suite as it stood — not because
the suite was thin, but because each needed something a question cannot
express:

| What the bug needed | Why no check had it |
|---|---|
| a **restart** between two steps | every check lived in one process |
| a **sequence** (make a code, then open another note, then look) | checks assert a state, not a path |
| a **second visit** to a page | nothing arrived anywhere twice |
| a **what-happens-next** (update, then carry on typing) | the check ended at the update |

A story fixes that by walking one thing a person does, from end to end,
pressing the buttons they press — the note card, `📋 Generate code`, the
dialog's own buttons — with each chapter in **its own process**, so
"close the app and open it again" is real rather than simulated. It
photographs the screen as it goes, and the pictures are meant to be
looked at: two bugs in this project were invisible in the source and
obvious in a photograph.

Two rules learned writing the first one, both by being burned:

- **Press the button by its whole name.** A loose search for `Import`
  found the sidebar's `📥 Import code` and closed the panel; the story
  then reported that the app had asked nothing. A story that presses the
  wrong button accuses the app of its own mistake.
- **Answer a blocking dialog from inside the wait.** The themed dialog
  waits on a variable, so nothing after the click runs until an answer
  arrives — which is also the only moment the question is on screen to be
  photographed.

A story is only worth its runtime if it would have caught the thing it
was written for, so each of the four bugs was **put back** and the story
walked again: all four turned it red, naming the step that broke. That
is the bar for adding another one.

Stories are slow by nature (a real window per chapter, seconds not
milliseconds), so they are not in `tools/run_tests.py`. Run them before
calling a user-facing feature done.

## Photographs: did a screen change shape while nobody was looking?

`py qa/story_look.py` opens the app on a fixed little notebook,
photographs six screens — the list, the editor, the calendar, two
Settings sections and a light theme — and compares each against the copy
in `qa/screens/`. Those copies are committed, so a change of appearance
shows up in a diff like any other change.

It does not say "this is wrong"; it cannot know that. It says **this
changed, and nobody said it would**, which is the honest half a script
can do. Approve a change you asked for with
`py qa/story_look.py --accept`.

Deliberately coarse: each picture is reduced to a small grid before
comparing, so a pixel of text rendering is not a finding while a moved
control is. Two identical runs report 0.0%. Shrinking one heading by
five points reported three screens changed, 6.6–10.9% each, and left the
two it could not affect at 0.0% — which is what "coarse but not blind"
has to look like before the tool is worth running.

## The surface inventory: what every new feature is walked against

The complete list of the app's functionality surfaces. Before a feature
or improvement is built, **every row gets an explicit verdict** in the
interaction pass (see CLAUDE.md, "Cross-feature verification"):
`none` / `touches` / `risky — with the weaving decision`. Walking all of
it is what makes "we thought of everything" checkable rather than felt.
A new surface joins this list the moment it ships.

- **Data & lifecycle:** save/load + `normalize_note` · autosave
  (debounce, flush, note switch, close) · undo/redo · Trash & restore ·
  duplicates · templates · data dir & migrations
- **Editor:** rich text (character styles) · paragraph formatting
  (lists, indent, alignment) · font size/family · tables (grid, cells,
  merges, widths, checkboxes, caption) · checklist · calculator ·
  comments · attachments · emoji picker · find-in-note · word count &
  reading time · Expand toggles · caret/scroll & view restore
- **Organization:** sidebar search · sort modes · categories · grouping ·
  pinning · multi-select & bulk bar · note list rendering & scroll guards
- **Time:** date field · recurrence · calendar (view, day colours,
  preview) · calendar History register (search incl. override content,
  year chips, collapsible series groups, pagination)
- **In/out:** clipboard in (rich, plain, TSV) · clipboard out (HTML,
  TSV) · share codes · single-note export (HTML, TXT) · backup `.zip`
  export/import · background threading
- **Shell:** theming (both patterns, canvas repaints) · popups & dialogs
  (positioning, multi-monitor) · the toast banner, plain and carrying an
  action (Undo) · keyboard shortcuts · Settings page · statistics ·
  open-note tabs · window sizing
- **Standing invariants:** plain text is the store · `core/` never
  imports tkinter · the worker thread never touches a widget · offsets
  counted in characters · any-script input · fast on weak machines ·
  the built `.exe` and `%APPDATA%`

## House rules for new checks

- A new feature's checks land **with the feature**, covering its seams
  with the old features — not after a field test finds the gap.
- Every new check is **mutation-tested**: break the mechanism it
  guards, watch it fail, then trust it. Old checks go stale silently —
  see the [Issues Log](../docs/ISSUES_LOG.md), "The teeth that had gone
  dull"; the fixes documented there are a ready-made mutant catalogue
  for periodic audits. And a mutant run's verdict counts **only if the
  suite ran to completion** — check for the script's FAILURES footer,
  never just grep for FAIL lines: a mutant that crashes the import
  prints no failures at all, and reads as "survived nothing" when it
  really ran nothing (this exact false-clean happened here once).
- **A check that can be decided by how fast the code above it runs is
  measuring the machine.** The sidebar search debounces with
  `after(180, refresh_note_list)`, and a full rebuild puts every card
  and header back correctly — so that timer repairs whatever a surgical
  update got wrong, and a check reading the result afterwards reports it
  as right. It had been doing exactly that for months: qa7's
  "switching notes does NOT rebuild the list" passed because the work
  ahead of it was slow enough for the timer to have always fired
  already. When deleting a note stopped rebuilding the whole list
  (185ms → 31ms) the slack vanished, the timer landed *between* the two
  readings, and the check went red with nothing wrong. Worse, in the
  same window a mutant **survived under load and died when run alone** —
  the timer had rebuilt the list and undone the damage.
  **Settle every timer that can rebuild what you are about to measure,
  and assert that they are settled** (`_flush_autosave()`, cancel
  `_search_debounce_job`), so the reading is about its subject. A check
  that only passes on a fast machine — or only on a slow one — has not
  been written yet.
- **A surviving mutant is a question, not a verdict.** When a promise is
  held by two independent mechanisms, breaking one leaves the check
  green — and the honest reading is "I broke the wrong thing", not "the
  check is dead". The delete toast's *no second copy on a second click*
  took three simultaneous edits to make fail: the toast forgetting its
  offer, `_hide_toast` forgetting it again, and the restore taking its
  entry out of the trash. Two wrong guesses came first, and both would
  have read as a dead check to anyone who stopped at the first.
- Windows-specific pixel checks assert on `sys.platform == 'win32'`
  only (fonts differ on Xvfb), and the Windows CI job is what makes
  them bite remotely — never delete the assertion, aim it.
- Timing-sensitive measurements wait for the **promised state** (five
  consecutive reads inside the asserted band, with a hard cap), never
  for generic stability or a fixed window — the app's view-restore
  choreography re-pins on timers up to 360ms, and "any stable value"
  can certify the pause between a late yank and the re-pin that
  corrects it (the push-down check flaked exactly that way, twice
  settled wrongly before this pattern). A real regression parks
  outside the band, the band is never entered, and the cap expires
  into a hard failure — prove that asymmetry under the mutant before
  trusting the check.
- The promise's **preconditions are content-addressed and asserted**,
  never assumed from a fraction: `yview_moveto(0.3)` lands on a
  different LINE per font metric (on the CI's Xvfb fonts, eight tall
  grids kept it inside line 1 — above the edit the check was about, so
  its +1 promise didn't even apply and the app was right to "fail" it).
  Scroll to an index (`yview('15.0')`), settle, then `check()` the
  precondition itself with its numbers in the message.
- The promise's **baseline settles first** (qa1's `settled()` helper:
  one value held for 500ms straight — longer than any restore timer —
  capped). The push-down check failed a *fourth* time with its
  promised-state wait already in place, because the baseline it
  promised `+1` against had been read mid-settle; a promise measured
  against a moving reference targets the wrong value no matter how
  well the wait afterwards is built. Failure messages carry the
  expected and landed values, so the next red names its mechanism.
- A failure gets a **permanent fix, at the root of its class**: when a
  check fails without a real regression, the check's *strategy* is
  wrong — fix the strategy, sweep the suite for every sibling using
  the same strategy, and record the lesson here. After the fix, the
  check may fail only when the promised behaviour is actually broken.
- **A path-based check asserts the invariant, not a fixed result** —
  the suite runs on Windows AND Linux, and the same string is a
  different path on each: `"C:\\x"` is a drive path on Windows but a
  plain (contained) filename on Linux, `\` separates only on Windows.
  A guard check must assert what's true on both — "never raises, and
  never returns a path outside the folder" — not "returns None for this
  specific input", which passed on Windows and went red on Linux CI.
  Use a value that escapes on every platform (a forward-slash
  `../../x`, or `os.path.relpath` to a sibling) when you need a
  guaranteed-None case.
- **Where a safety net masks the mechanism, assert the mechanism.** A
  fallback that repairs the symptom makes behaviour checks lie: the
  theming straggler pass repainted an UNTRACKED frame's fill, and the
  stock dark/light themes share an accent hex, so a both-themes
  behaviour check stayed green with the tracking deleted. Such a check
  asserts the registration itself (membership in `themed_widgets`)
  alongside the behaviour — and distrust any palette pair sharing a
  hex: it can vouch for nothing. The full story:
  ["The safety net that hid the missing mechanism"](../docs/ISSUES_LOG.md#the-safety-net-that-hid-the-missing-mechanism).
- **Prefer recording the synchronous call over reading asynchronous
  state back.** Polling (below) tames async reads, but when the
  promise IS the decision — which button got `focus_set`, whether the
  view snapshot existed when render ran, in what ORDER capture and
  teardown happened — wrap the method, record the call, assert the
  record. Deterministic under any load, and it can pin ordering, which
  no amount of polling the end state can (qa6's dialog-focus recorder,
  qa1's capture-before-teardown spy).
- **A stale artifact in the system temp dir can green a check.** The
  OS temp outlives runs: a zip left by a PREVIOUS run satisfied
  "export produced a file" with the export's move-into-place step
  deleted. Delete (or uniquely name) every temp-path artifact BEFORE
  the action that is supposed to create it.
- **Never hand Tcl's text search an astral needle.** `search` with
  `-nocase` and a non-BMP character (any emoji) SEGFAULTS Linux Tk 8.6
  outright — no FAIL line, no footer, a dead process whose buffered
  stdout also lies about where it died (see below). The app
  pre-screens: astral queries scan in Python and convert offsets with
  `_tk_col`. A check that needs to find emoji goes through the app's
  find model, never through a raw `text.search()` call.
- **A crashed run's last printed PASS is not where it died.** Piped
  stdout is block-buffered on Linux, so a segfault throws away up to a
  buffer's worth of already-printed lines — the CI log's last PASS
  once pointed ~200 checks before the real crash site. Bisect crashes
  on the Docker mirror with `-e PYTHONUNBUFFERED=1`; trust exit codes
  and the FAILURES footer, never the visible tail of a dead process.
- **Force a precondition; read back only a promise.** The two focus
  helpers are not interchangeable, and using the waiting one where the
  forcing one belongs is a false-red generator: a bounded poll on an
  asynchronous focus read times out on a loaded machine and reports a
  red about an app that did exactly the right thing. Ask which the line
  is. "The test needs the caret in this field before it types" is a
  PRECONDITION — force it (take_focus / _take_focus). "Ctrl+F puts the
  focus in the find entry" is a PROMISE — poll for it. And where the
  promise IS the app's own synchronous decision, do not poll at all:
  wrap the method, record the call, assert the record (qa1's cell
  editor records focus_set, which cannot flake under any load). This
  cost the suite a red whose name was lost for a day
  (COVERAGE_LEDGER C11b) and two more in qa6 the day it was found.
- **Focus is asynchronous both ways** — granting AND clearing. A check
  about where the app put the focus polls for the promised holder
  (qa1's `focus_settles_on`, the assert-only twin of `take_focus` —
  which FORCES focus and must never wrap an assertion about the app's
  own placement, or the check turns tautological), and a check about
  focus being cleared polls for it leaving (qa6's `_focus_leaves`).
  A bare `focus_get() is widget` assert reads the old focus now and
  then, even in solo runs — that flake blocked a release cut once.
- **Never generate a POINTER event on a widget that has no native
  window.** Tk silently DISCARDS one aimed at it — and not just
  `<Button-1>`: press, release, `<B1-Motion>`, `<MouseWheel>`,
  `<Enter>`/`<Leave>` are all delivered to the window named in the
  event, so every one of them fails the same way — no error, no return
  value, the binding just never runs and every assertion after it is
  about state nothing was asked to change. A widget gets that window
  when it is first mapped, so a freshly built popup, a rebuilt row, or
  one the app has hidden is precisely the case that swallows the
  event. And popups *do* get hidden here: they are `-topmost` by
  design, so a heartbeat withdraws them whenever another program holds
  the Windows foreground — which a test process never owns, the
  terminal that launched it does. `chip.event_generate('<Button-1>')`
  was therefore asking "did the 300 ms watch tick land before my
  click?", and qa2's 3-marker cap check answered by luck for weeks:
  measured mid-run, all five chips still read `highlightthickness=0`,
  not one click delivered. Go through
  [`_qa_support.py`](_qa_support.py): `_qa_pin(NO)` once at the top
  makes popup visibility independent of the OS foreground (qa1 still
  covers the real hide/restore by driving `_popup_watch_step()` with
  both answers stubbed), and `_qa_fire(w, seq, **kw)` — with
  `_qa_click(w)` as its `<Button-1>` shorthand — asks `winfo_id()`
  first, which *creates* the window rather than waiting for one.
  KEYBOARD events are the deliberate exception, not an oversight: Tk
  hands a generated key event to whatever holds the FOCUS, wherever it
  was aimed, so `winfo_id()` on the target repairs nothing there and
  `fire()` refuses them loudly — a key event stays on raw
  `event_generate` behind the focus discipline documented below
  (take_focus / focus_settles_on / generate-and-poll); a `<<virtual>>`
  event, by contrast, is window-delivered like a pointer event and may
  go through `fire()`. Do not gate on
  `winfo_ismapped()`/`winfo_viewable()`: both read 0 for a widget
  scrolled out of a canvas and for a withdrawn-but-once-mapped popup,
  and both of those receive events perfectly well — gating on them
  refused qa6's category swatch, which simply sits below the fold of a
  scrolling panel. Delivery is what the helper guarantees; whether a
  human could have reached the widget where it sits is a separate
  question a check asserts for itself. (One place stays raw on
  purpose: qa1's dead-canvas drag, where the press's commit destroys
  the canvas and the TclError from the corpse is the point.)
- **A mocked method is un-mocked with `del app.<name>`**, which
  un-shadows the real bound method — never by re-assigning a value
  saved earlier, unless that value is the script's own top-of-file
  baseline mock. A saved "original" can itself be an earlier section's
  leaked mock: qa7 once saved-and-restored an always-`'occurrence'`
  scope prompt this way, and the leak silently shadowed the real
  method for the rest of the run.
