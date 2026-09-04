# The qa suite — read me before touching a guarded surface

Nine scripts, ~870 checks, all driving the real app headlessly (Xvfb on
Linux CI, real Windows Tk on the Windows CI job and every dev machine).
Each script's banner says what it owns. Two things live here that are
not obvious from the file names, and both have cost a red CI run to
learn:

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
real notebook (it has happened; see CLAUDE.md, "QA testing safety").
`py tools/run_tests.py` does the whole safe-scratch ritual for you and
is the verdict that counts before a push; `py tools/pre_push_check.py`
is the two-second static half (names, API surface, compile-all) you
run before *every* push.

## House rules for new checks

- A new feature's checks land **with the feature**, covering its seams
  with the old features — not after a field test finds the gap.
- Every new check is **mutation-tested**: break the mechanism it
  guards, watch it fail, then trust it. Old checks go stale silently —
  see ISSUES_LOG, "The teeth that had gone dull"; the fixes documented
  there are a ready-made mutant catalogue for periodic audits.
- Windows-specific pixel checks assert on `sys.platform == 'win32'`
  only (fonts differ on Xvfb), and the Windows CI job is what makes
  them bite remotely — never delete the assertion, aim it.
- Timing-sensitive measurements settle first (five stable reads with a
  hard cap) instead of counting update() pumps — see the menu-op and
  push-down checks for the pattern, and prove the settled check still
  fails under its mutant before trusting it.
