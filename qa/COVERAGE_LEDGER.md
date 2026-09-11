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
| C11b | An unidentified qa1 check failed once under full-suite load (2026-09-10, 1-of-4 runs) and its NAME was lost — the verifying run was not captured to a file | **Candidate cause found (2026-09-11), not proven for this red:** the dropped-click class ([The click that was never delivered](../docs/ISSUES_LOG.md#the-click-that-was-never-delivered)) made every popup click in the suite race a 300 ms heartbeat, and qa1 held five of them. That class is now closed suite-wide. The name of *this* red was still lost, so it stays listed until a full run under load comes back clean often enough to retire it — the tee-to-a-file rule stands either way |
| C11 | Old CHANGELOG sections' prose and internal links (below line ~824) unreviewed (docs auditor) | Fold into the next editorial pass with the anchor-checker script extended to prose links |
| C13 | **Measured, not fixed:** a SINGLE-LINE body wearing a few thousand styling spans hangs Tk's layout outright (>240 s at 2000 spans on a 3000-char one-liner; reachable below ANY sane span cap on a long enough line) — the span ceiling shipped this cycle is an anti-bomb ceiling, not a fix for this | Tier-1 perf work: a render strategy for long single lines (soft-wrap injection at render, or a paint cap with a notice); measured shapes and numbers in the 2026-09-11 measurement report |
| C14 | **Measured, not fixed:** one note-open calls `capture_editor_state`→`_extract_formatting` 5–6 times, and each call pays `_char_offset` = O(tag ranges × body length) characters copied through Tcl — the REAL formatting-cost cliff (~0.9–1.7 s/call at saturation), independent of any cap | Tier-1 perf work: dedupe the per-open captures, and read offsets back without a `get("1.0", index)` per range endpoint |
| C15 | The note BODY has no ceiling through the share code — a 300k-char single-line body is Tk-hostile with zero spans, same brick family as T0-7 (share-code guards cap the zip/decode size, not one field) | Decide a body ceiling (or a defence at render) alongside C13; it is the same single-line mechanism |
| C16 | **Documented residual:** two checklists sharing their first 1000 items become identical after the cap, and the dedup then keeps one. Truncation IS announced on the share-paste route (the notice was dead code until it was passed down to the one status line that survives), but the collision itself is by construction | Accepted while the cap exists; revisit only if a field report ever shows two real >1000-item lists |
| C18 | **Measured, not fixed — a wave-1 survivor that had neither a fix nor a row until the wave-2 critic counted it.** MAX_CHECKLIST_ITEMS = 1000 is survivable but not comfortable: measured on a FAST machine, a 1000-item note costs 287 ms to open plus 1277 ms to paint (linear, ~1.5 ms/item), which projects to roughly 5–8 s on the weak machines the app targets — an apparent hang for one note. The measurement recommended 500 | Deliberately NOT lowered: the cap TRUNCATES, so halving it doubles the data a legitimate import loses, and real lists are tens of items. The honest fix is to stop paying paint cost for off-screen items (render the checklist lazily), which is Tier-1 work alongside C13/C14; until then the number stands and the reason is written here rather than assumed |
| C17 | The one-time ID renumbering may silently repoint the remembered last-open note (wave 2 low-severity finding, never verified — the T2-1 reviewer dropped it for slots) | Verify cheaply next time qa5 is open: seed last_open_note_id, force a renumber, assert the remembered note is the same NOTE, not the same number |

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

**Totals after lift #2 (2026-09-10): Windows 86.0%, Linux 85.6%**
(from the 81.5% baseline; the two platforms execute different lines —
win32 branches on one, Xvfb/POSIX on the other — so both are reported
rather than blended). The journey: 81.5 → 84.9 (lift #1) → 86.0, every
point mutation-backed. `calendar_view` 88.4%, `sharing` 93.6%,
settings 84.7%, hub 85.3%.

What separates 86% from the ~90% aspiration is now DOMINATED by the
ACCEPT categories below — the last cheap coverable flows went into
lift #2. The honest restatement of the target: **everything that is
not a written ACCEPT gets covered**; the next lift runs after the
improvements tour reshapes what exists (per the working agreement). By layer, with the targets the
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
| ~~C12~~ | **RE-SCOPED (finding):** the multi-tab machinery is unreachable — nothing ever creates a second tab (`open_note_in_tab`/`open_blank_tab` both reset the list to one entry; no append exists), so `close_tab`'s neighbour-pick and unsaved-triage lines are dead code guarding impossible states. The REAL single-tab contract is asserted in qa7 (reset-to-one, flush-on-switch, single-close collapse). The dead machinery is a **product decision for the improvements tour**: build real multi-tabs someday, or simplify it out — until then its lines stay honestly uncovered rather than theater-covered | — |
| ~~C13~~ | **DONE (lift #1):** keyboard nav, both tooltips (incl. the 10-title cap), day colours through the real palette, emoji marks with the 3-marker cap — 14 qa2 checks, 2 mutants. File: 65.5% → 86.5%, target met | — |
| ~~C14~~ | **DONE (lift #1):** all five pickers driven through their real widgets (day-15 pick lands in the field, ▶ shifts the month, swatch colours the note, chip lands in the body, template fills the editor, size-cell inserts a drawn table) | — |
| ~~C15~~ | **DONE (lift #2):** the category panel's add / recolour (targeted swatch fill) / rename (through the inline popup's Save) all drive the real rows; tick-all-but-first + cleanup from lift #1. Residual: the template-editor checklist toggle (~10 lines) | — |
| ~~C16~~ | **CLOSED (lift #2):** sharing at 93.6%; the clipboard fallback half is a written ACCEPT — its branches select per-platform clipboard plumbing inside blanket guards, and a mocked-Tk harness would test the mock. The crash-relevant end (surrogates at the export boundary) is covered elsewhere | — |

### ACCEPT — added at lift #2

| Item | Reason |
|---|---|
| `_main` + the last-resort startup crash dialog (~19 lines) | Its whole point is running when nothing else can; a test would mock its own premise |
| `paths._settings` migration branches (~28 lines) | Per-environment first-launch paths; the reachable migrations are covered in test_data_safety, the rest need machines we don't simulate |
| `_on_wheel` / `_panel_or_page_wheel` platform branches | Wheel delta dialects (win32 vs X11) — each platform's CI leg executes its own half; the union covers both |
| `refresh_tab_strip` / `close_tab` multi-tab remainder | Dead machinery guarding unreachable states (the C12 finding); covered the day multi-tabs become real or get simplified out |
| `_maybe_close_cell_editor` focus-transfer branch | The asynchronous focus-handoff window the house rules tell checks to avoid; the synchronous commit path is covered directly |
| `core/clipboard` per-platform fallbacks (72.2%) | See C16 |

## The standing rule

A future report's NOT COVERED section is triaged into this file at the
cycle's end — the confession is the input, the verdict is the output, and
"we moved on" is not a verdict.
