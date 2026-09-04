# The qa suite — read me before touching a guarded surface

Nine scripts, ~870 checks, all driving the real app headlessly (Xvfb on
Linux CI, real Windows Tk on the Windows CI job and every dev machine).
The manual half of the QA story sits beside them:
`NoteOrganizer_TestPlan.xlsx`, the structured test plan for scenarios
easier to eyeball than to automate.

## What each script owns

| Script | Primary ground |
|---|---|
| `qa1` | notes, categories, templates — plus the editor's heaviest surfaces: tables, rich text, the find bar, bulk actions |
| `qa2` | recurrence, calendar, duplicates |
| `qa3` | trash, sharing, import/export |
| `qa4` | theming, stress tests, leak regression |
| `qa5` | corrupt data, edge cases |
| `qa6` | grouping, settings, attachments, multi-feature combinations |
| `qa7` | calendar delete, multi-select, image preview, autosave & memory fixes |
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
| Bulk-action bar / selection mode | **qa1**, **qa7** |
| Theming (apply/track/toggle) | **qa1**, qa4, and every rebuilt-widget check |
| Autosave (debounce, guards, flush) | **qa1**, qa5, qa6, qa7, qa8 |
| Editor page scroll/canvas | **qa1**, qa6 |
| Note list (refresh, scroll guards, grouping) | **qa1**, qa4, qa5, qa6, qa7, qa8 |
| Tables / drawn grids | **qa1** (heavily), qa2, qa3 |
| Find in note (Ctrl+F) / find bar | **qa1** (crosses theming, tables, editor scroll) |
| Templates | **qa1**, **qa6**, **qa9**, qa4 |
| Settings panels | **qa6**, qa3, qa4, qa7 |
| Calendar | **qa7**, qa1, qa2, qa4, qa5, qa9 |
| Trash | **qa6**, **qa7**, qa1, qa3, qa4, qa5 |
| Share codes | **qa3**, qa1, qa4 |
| Export (files, backup) | **qa1**, qa3, qa8 |
| Attachments | **qa7**, **qa6**, qa1, qa2, qa3, qa4, qa5, qa8 |

Bold = the heavy owner(s). Regenerate the table after big rounds — it
was produced by grepping each surface's identifiers across `qa*.py`
(e.g. `grep -c "bulk_" qa/qa*.py`), so refreshing it is one loop, not
archaeology.

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
  preview)
- **In/out:** clipboard in (rich, plain, TSV) · clipboard out (HTML,
  TSV) · share codes · single-note export (HTML, TXT) · backup `.zip`
  export/import · background threading
- **Shell:** theming (both patterns, canvas repaints) · popups & dialogs
  (positioning, multi-monitor) · keyboard shortcuts · Settings page ·
  statistics · open-note tabs · window sizing
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
  for periodic audits.
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
