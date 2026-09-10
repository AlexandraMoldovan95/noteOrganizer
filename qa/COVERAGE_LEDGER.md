# Coverage ledger — every confession gets a verdict

The agent protocol makes every report end with what was NOT covered. This
ledger is where those confessions stop scrolling past: each one lands here
and receives exactly one verdict — **COVER** (work queued, with the how),
**ELSEWHERE** (already covered; pointer), or **ACCEPT** (deliberately not
covered; the reason). An item may not be dropped silently. New reports'
confessions are appended at the next editorial pass.

Sources: the ten agent reports of the 2026-09-09/10 cycles (three fix
verifiers for 0.71.119, three for 0.71.125, one for 0.71.134, three docs
auditors), the residuals already recorded in ROADMAP → Known limitations,
and durable items carried from earlier cycles. **This ledger's own
confession:** the original ten-zone audit's per-zone confessions (early
September) were not re-mined — their findings were all triaged into the
shipped waves, but any purely-confessional item from that wave is not
individually listed here.

## COVER — queued work, in rough priority order

| # | Item (from whose confession) | How it gets covered |
|---|---|---|
| ~~C1~~ | **DONE (this cycle):** the destructive-gesture sweep ran — every delete/overwrite gesture now has a verdict: confirmed (attachments ✕ FIXED with warning+No; templates, trash, reset-day, replace flows already were), trash-recoverable (note deletes, bulk, duplicate cleanup), undo-atomic (all grid/body edits), auto-purge by design (retention), or ACCEPT with reason (the checklist item ✕ — editing-granularity: content visible at click, trivially recreatable, a per-item confirm would break flow; `clear date` — a re-enterable field, not data) | — |
| C2 | Arrow-key caret movement over an astral emoji (can ←/→ park the insert mark mid-pair?) — probe was inconclusive (0.71.125 grid/emoji verifier) | A focused probe on both CI platforms; if mid-pair parking is real, the caret guard family gets a sibling |
| C3 | The commit-then-capture edge in `_grid_delete_table` (an open cell editor's commit re-render may pre-empt the delete's view snapshot) — declared only in conversation | Add to ROADMAP Known limitations now (it has no in-repo home, unlike its siblings); pixel test only if the flicker investigation (already queued) reaches it |
| C4 | `selectbackground`/`selectforeground`/`highlightcolor` were outside the theming option sweep (0.71.125 theming verifier) | One grep-sweep pass with the same long-lived-vs-rebuilt triage as 0.71.125; qa4 check per genuine miss |
| C5 | `visual_scenes.py` has never been executed since its exit-code fix (0.71.134 verifier) | Run it once on the next visual round; its red-on-scene-failure now bites, which is what the fix promised |
| C6 | ISSUES_LOG mid-file stories' version-header links were never verified (docs auditor) | A 20-line checker script pass (slug + anchor verification already exists from this session) — run once, fix what it finds |
| C7 | Screenshot CONTENT currency — only the calendar shot was inspected; 21 others unchecked (docs auditor) | The screenshot-regeneration pass (already on the table): retake all, diff against described UI |
| C8 | The qa seam-map per-cell accuracy was not re-verified after three audit rounds (technical-docs auditor) | Regenerate the seam table at the next feature's interaction pass, per qa/README's own instruction |
| C9 | CLAUDE.md still carries the stale ~13,250 line count (docs auditor, drive-by) | One-line fix at the next CLAUDE.md touch |
| C10 | Ctrl+A-overtype gesture never executed as a gesture (mechanism proven, gesture untried) | Cheap qa1 addition next time that file is open: type over a select-all that includes a table, assert caret sanity |
| C11b | An unidentified qa1 check failed once under full-suite load (2026-09-10, 1-of-4 runs) and its NAME was lost — the verifying run was not captured to a file | Standing rule now: every verification full-run tees to a file, so a first red always keeps its name; the flake hunt starts the next time it shows itself |
| C11 | Old CHANGELOG sections' prose and internal links (below line ~824) unreviewed (docs auditor) | Fold into the next editorial pass with the anchor-checker script extended to prose links |

## ELSEWHERE — the confession was true for that agent, covered by another hand

| Item | Where it is covered |
|---|---|
| "I did not run any tests / the suite / the mutants" (every verifier — read-only mandate) | The session ran every suite (Windows twice + Linux mirror) and all 52 mutants; verdicts in the PR descriptions |
| `_note_export_content` never driven with surrogates end-to-end (0.71.119 emoji verifier) | qa3's export checks added the same cycle exercise it |
| Windows clipboard surrogate fallback behaviour (same verifier) | Degrades inside a blanket except by design; the crash class was closed at the export boundary — residual risk is formatting-only and noted in ROADMAP's residuals |
| Linux Tk index-unit semantics (0.71.125 verifier assumed Windows-only measurements) | Measured empirically on the Docker mirror during the segfault bisect: identical UTF-16 units |
| Dynamic check counts unknowable statically (docs auditor) | Counted at runtime in isolation: ~1,540 total, ~1,070 GUI (now in README/qa README) |
| Sibling commits "out of my scope" (each verifier) | Each commit had its own dedicated verifier; the union covered the branch |
| GIT_WORKFLOW lacked the Docker-mirror pointer (technical-docs auditor) | Added in the editorial pass |

## ACCEPT — deliberately not covered, and why

| Item | Reason |
|---|---|
| `os.replace`/MoveFileEx atomicity and CPython file-sharing flags taken from documentation, not probed | Platform contracts documented by Python/Windows; probing them tests the OS, not the app |
| GitHub's live anchor rendering (docs auditor computed slugs instead) | The slug algorithm is stable and was verified against dozens of known-good anchors |
| Malicious-zip fuzzing of `_safe_extract_zip` (0.71.134 verifier) | The guard's invariants are unit-covered; fuzzing is disproportionate for an offline app whose zips the user chooses |
| The PR-description texts as a documentation source (docs auditor) | Superseded: everything they declared now lives in ROADMAP Known limitations |
| The manual test-plan xlsx content (docs auditor) | It is the USER's working document; the session maintains its rows, the user its results |
| tkinter cross-thread `after` semantics probed only by reasoning | No current worker touches Tk (verified); the latent hazard is recorded in ARCHITECTURE's thread rules |
| `purge_stale_copies` interplay with a persistently-failing migration flag | Pre-configure edge on first launch only; the migration preserves a backup by design — bounded blast radius |
| x11 press/hover display semantics on the CI runner's exact Tk build | The checks assert the app's configure calls (the mechanism), which are platform-independent |

## Measured execution coverage (baseline 2026-09-10)

`py tools/run_coverage.py` runs the whole suite under coverage.py from
isolated scratch copies and prints the numbers below plus the largest
uncovered regions. This baseline is a WINDOWS measurement; the Linux CI
leg executes different lines (Xvfb branches, POSIX paths) and gets
merged in when the coverage-lift cycle lands.

**Total: 81.5% of 13,050 statements.** By layer, with the targets the
coverage-lift cycle aims at:

| Layer | Baseline | Target |
|---|---|---|
| `core/` tables, richtext, calculator, formatting | 93–96% | ≥96% |
| `core/` storage, recurrence | ~91% | ≥93% |
| `core/` sharing, clipboard, model, paths | 66–83% | error branches worth asserting; rest ACCEPT |
| hub (`note_organizer.py`) | 81.4% | ~90% |
| `ui/settings_page` | 78.5% | ~88% |
| `ui/calendar_view` | **65.5%** | ≥85% |
| **Total** | **81.5%** | **~90%** |

A covered line is necessary, not sufficient — whether the checks BITE is
the mutation discipline's job. 100% is explicitly NOT the target: a
large share of the remainder is one-line defensive guards (asserting
that `pass` passes is theater), environment-specific migration branches,
and the last-resort startup crash handler, whose whole point is running
when nothing else can.

### COVER — from the coverage measurement (the lift queue)

| # | Uncovered area | How it gets covered |
|---|---|---|
| C12 | The open-note TABS family (`close_tab` 28 lines, `refresh_tab_strip`, switch flows) — never driven by qa at all | A qa tab-lifecycle block: open several, edit, switch, close middle/active/last, dirty markers |
| C13 | `calendar_view` interactivity: keyboard navigation (`_calendar_key`), day hover previews, day-summary tooltips, emoji day marks | qa2/qa7 additions with generated key and pointer events |
| C14 | The pickers: date (64 lines), colour, emoji, template, table-size popups | One open→choose→assert→close pass per picker |
| C15 | Settings duplicates panel internals (`check_all_but_first`, add/rename/recolour category flows) | Extend qa6/qa7 panel drives |
| C16 | `core/sharing` error branches (decode failure paths) and `core/clipboard` fallbacks | Unit checks feeding each malformed input class |

## The standing rule

A future report's NOT COVERED section is triaged into this file at the
cycle's end — the confession is the input, the verdict is the output, and
"we moved on" is not a verdict.
