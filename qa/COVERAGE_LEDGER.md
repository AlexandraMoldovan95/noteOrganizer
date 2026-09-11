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
| ~~C3~~ | **CLOSED (2026-09-11): given a home.** The commit-then-capture edge in `_grid_delete_table` existed only in a conversation, which is what the row was about. It is now an entry under Known limitations in `docs/ROADMAP.md`, beside its siblings, with the same caveat they carry: it needs a pixel-level look before any fix is trusted | — |
| ~~C4~~ | **CLOSED (2026-09-11): swept, no genuine miss.** All six sites that set `selectbackground`/`selectforeground`/`highlightcolor` were triaged against the project's own long-lived-vs-rebuilt rule. Two of them ARE the theme-switch recolour passes (the combobox popdown at `_recolor_combo_popups`, the note cards at the card recolour loop); the note card's creation deliberately does not track (the perf reason is written at the call site) and is covered by that recolour pass; the selection-highlight helper re-reads `self.colors` at call time; and the calendar's day-marker popup is a transient `Toplevel` rebuilt from current colours on every open, like every other popup. No qa4 check was added because there was nothing to witness | — |
| ~~C5~~ | **CLOSED (2026-09-11): run, and clean.** `visual_scenes.py` executed from a scratch copy for the first time since its exit-code fix: 13 scenes, 0 Tk callback errors, 0 scene errors, exit 0. The rich-text and table scenes were inspected by eye as well, because they are the two the styling ceiling could have damaged — formatting and tables both render correctly. One unrelated thing the eyes caught is recorded as C22 | — |
| ~~C6~~ | **CLOSED (2026-09-11): checked, and the checker kept.** All 424 in-repo Markdown links across 15 files resolve — file targets and heading anchors both. The pass is now `tools/check_doc_links.py` rather than a one-off, and it runs in `tools/pre_push_check.py`, because a link rots the day someone rewords a heading and a dead anchor just scrolls nowhere. Proven to bite before being believed: pointed at a file with four deliberately broken links (missing anchor, missing file, wrong anchor in a real file, and a heading that exists only inside a code fence) it catches all four and passes the five good ones | — |
| C7 | Screenshot CONTENT currency — only the calendar shot was inspected; 21 others unchecked (docs auditor) | The screenshot-regeneration pass (already on the table): retake all, diff against described UI |
| C8 | The qa seam-map per-cell accuracy was not re-verified after three audit rounds (technical-docs auditor) | Regenerate the seam table at the next feature's interaction pass, per qa/README's own instruction |
| ~~C9~~ | **CLOSED (2026-09-11).** CLAUDE.md said the entry file was ~13,250 lines; it is 14,510. Now ~14,500 | — |
| ~~C10~~ | **CLOSED (2026-09-11): the gesture executed at last.** qa1 now selects the whole note — table included — and types a single character over it, then asserts what survives: the typed character alone, no table row left in the text, nothing left drawn over it, a caret that still resolves inside what remains, and a stored body equal to exactly what was typed. Driven through Tk's `<<SelectAll>>` virtual event rather than a literal Ctrl+A, which Tk maps differently on Windows and X11. Two of the first version's assertions were wrong and both were caught before the check was believed: one compared the selection to the body as strings (select-all runs one past the last character), and one asserted on the app's own `_table_grids` list rather than on what the text widget actually holds — the list keeps a dead entry here that the user cannot see, recorded as C23. A third was VACUOUS: it asked whether the saved note had a table row while the autosave never fired, so it read an empty dict and passed, and a mutant storing a ghost table row walked through it. Mutation-tested until it did not: the mutant is now killed, with the run reaching its footer | — |
| ~~C11b~~ | **CLOSED (2026-09-11): the check finally gave its name.** Under a full-suite run it was `the one floating editor opens on the first cell`, and the cascade of cell-editor checks behind it. The mechanism was not the app: `focus_settles_on` reads an ASYNCHRONOUS focus result inside a bounded 60-try poll, so a loaded machine reports a false red about an app that placed the focus correctly — it passed three times standing alone straight afterwards, which is exactly the shape the standing rule forbids treating as a resolution. Repaired at the strategy, per qa/README's own instruction: the placement PROMISE is RECORDED (wrap `focus_set`, assert the call) rather than polled, which cannot flake under any load; the three sites that aim KEY events at the editor force focus with `take_focus`, because there the assertion is about what the key does, not about where the focus landed. Whether this was the same red as 2026-09-10 cannot be proven — that name was lost — but it is the same class, in the same file, under the same condition, and the tee-to-a-file rule is what made this one keep its name | — |
| C11 | Old CHANGELOG sections' prose and internal links (below line ~824) unreviewed (docs auditor) | Fold into the next editorial pass with the anchor-checker script extended to prose links |
| ~~C13~~ | **CLOSED (2026-09-11) — and the row as written was wrong, which is why it was re-measured instead of actioned.** The recorded number (">240 s at 2000 spans") did not reproduce: 2,000 **bold/italic** spans on a 3,000-char one-liner open in 0.75 s. The hang is real but belongs to a different mechanism — it is not the span count, it is how many tagged RANGES land on one line. Re-measured: 2,000 spans over 10 lines = 0.28 s; the same 2,000 on one line = never finished in 75 s; 500 overlapping on one line = 0.30 s; 1,000 = never finished. `highlight`, `text_color` and `font_size` all reach it; a second shape reaches it with no crowded line at all, by giving every span the same end offset so they all pile onto the LAST line. Fixed at the data door by `clamp_spans_per_line` (per-line coverage plus a ceiling on the note's total ranges) — NOT at the draw, because the editor reads formatting back out of the widget when it saves, so a note drawn without its tags would have been saved without its spans | — |
| C14 | **RE-MEASURED 2026-09-11 — real, and the row's numbers are now the measured ones rather than an agent's.** The count was wrong (3 calls per open, not 5–6) and the cost was understated. `_char_offset` is `len(w.get("1.0", index))`, so every range endpoint re-reads the note from its start; 500 styled pieces on one line means 1,000 such re-reads, three times over. Timed on the startup path: **100 pieces → 0.06 s, 250 → 1.49 s, 500 → 14.18 s**, and `load_note` itself is 0.16 s of that, so the read-back IS the cost. On the packaged `.exe` this is the whole gap between a window in 1.5 s and a window in 15.5 s. **Ordinary notes never feel it** — measured: 3,000 chars/30 spans = 1.18 s, 10,000/80 = 1.13 s, 20,000/150 = 1.38 s, 40,000 chars over 265 lines/300 spans = 1.55 s. The cost needs the pieces crowded onto ONE line, which is the hostile shape C13 closed, not a written note | Tier-1 perf work, and the first target when a perf round happens: compute the offsets in ONE pass (sort the endpoints, measure only the gap from the previous one) instead of a `get("1.0", index)` per endpoint — the exact `len(get())` semantics must be kept, because `count("chars")` counts UTF-16 units and shifted every span one right per preceding emoji once already |
| ~~C15~~ | **WITHDRAWN (2026-09-11): false as written, and it was written from inference rather than measurement.** A body alone is not Tk-hostile at any length this app can hold. Measured on the real editor: 300,000 characters on ONE line, zero styling spans, opens in 1.13 s; the same length wrapped into 60-char lines is faster still. The single-line mechanism it pointed at is real but needs SPANS to bite, and that is C13, now closed. Recorded rather than deleted because the lesson is the row itself: it entered the ledger as a measurement and was never one, and it sat next to a row whose numbers were also wrong | — |
| C16 | **Documented residual:** two checklists sharing their first 1000 items become identical after the cap, and the dedup then keeps one. Truncation IS announced on the share-paste route (the notice was dead code until it was passed down to the one status line that survives), but the collision itself is by construction | Accepted while the cap exists; revisit only if a field report ever shows two real >1000-item lists |
| C18 | **Measured, not fixed — a wave-1 survivor that had neither a fix nor a row until the wave-2 critic counted it.** MAX_CHECKLIST_ITEMS = 1000 is survivable but not comfortable: measured on a FAST machine, a 1000-item note costs 287 ms to open plus 1277 ms to paint (linear, ~1.5 ms/item), which projects to roughly 5–8 s on the weak machines the app targets — an apparent hang for one note. The measurement recommended 500 | Deliberately NOT lowered: the cap TRUNCATES, so halving it doubles the data a legitimate import loses, and real lists are tens of items. The honest fix is to stop paying paint cost for off-screen items (render the checklist lazily), which is Tier-1 work alongside C13/C14; until then the number stands and the reason is written here rather than assumed |
| ~~C17~~ | **CLOSED (2026-09-11) — the suspicion was right, and it was a real user-visible bug.** The one-time cleanup renumbers every note from 1 and saves settings in the same breath, but left `last_open_note_id` holding the old number, so the setting stopped meaning the note it was written for. Driven on the real startup path, both shapes reproduce: with one empty note in front of it, the note being read moved from id 2 to id 1 and the next launch opened THE NOTE AFTER IT — "A completely different note" — and when the number vanished instead, the app opened nothing. Fixed where the renumber happens: the remembered note is found before the cleanup and its NEW id written after, matched by identity (clean_notes returns the very dicts it was given), with a note the cleanup removed clearing the setting rather than aiming it at whoever inherited the number. Four checks in test_data_safety cover both broken shapes, the removed-note case, and the notebook with nothing to clean. Three mutants: two killed; the third — matching by value instead of identity — SURVIVED and is equivalent rather than a gap, because after a renumber no removed note can equal a kept one (empty notes are dropped, and a collapsed twin's survivor carries a different id) | — |

| C19 | **VERIFIED ON THE ARTIFACT (2026-09-11)** — recorded because nothing else can record it. The single-instance guard exists for one scenario no amount of code reading settles: two launches of the packaged `.exe` against `%APPDATA%`. Driven on the real build with `APPDATA` redirected to a scratch folder (the real notebook was never touched), and judged by enumerating the windows each PROCESS owns rather than by whether the process stayed alive — a modal dialog keeps a refused process alive, so "still running" proves nothing either way, which is how the first probe read a working guard as a failure. Result: the first launch owns a `Note Organizer` window; the second owns only `Note Organizer is already open` and NO notebook window; killing both leaves no stale lock and a fresh launch opens normally. Caveat worth keeping: on a COLD start the refused instance needs ~10-14 s to raise its dialog, so a probe at 9 s sees nothing at all | Re-run the same window-enumeration probe on any build that touches `_main`, the lock, or the startup order |

| C20 | **Measured and deliberately accepted (2026-09-11).** The per-line styling ceiling stops the app being bricked, and it sits just above a cliff rather than below one: a note built to sit AT the ceiling opens in 15.5 s on the packaged `.exe` (100 pieces on a line → 1.5 s, 250 → 2.5 s, 500 → 15.5 s). Lowering the ceiling was considered and REJECTED on measurement: bolding every word of a 250-word paragraph one at a time produces exactly 250 pieces, so a ceiling of 250 would silently trim a note a person could really write — and lost formatting is worse than a wait you sit through once. 500 leaves roughly double the headroom over the heaviest realistic shape measured (a 250-word wall bolded every other word = 125). The wait is not the ceiling's fault; it is C14 | Fix C14 and this row goes away on its own. Do NOT lower the ceiling instead — that trades a recoverable wait for silent data loss |

| C21 | **VERIFIED ON THE ARTIFACT (2026-09-11).** The `0.71.155` build was smoke-tested with `APPDATA` redirected to a scratch folder (the real notebook never touched), judged by enumerating the windows each PROCESS owns. Empty notebook: window in 1.0 s. The same bomb note that made earlier builds unopenable, seeded into the notebook and set as the last-open note: window in 15.5 s, process alive, window still there four seconds later, no crash log. So the brick is gone on the real artifact, and what remains is C20's wait | Re-run with the same harness on any build that touches formatting, `normalize_note`, or the startup order |

| C22 | **Seen in the visual pass (2026-09-11), not chased.** The sidebar's sort control shows `Recently up` — its label is clipped, because the control is narrower than its longest option. Visible in every scene shot, both themes. Cosmetic, and the fix is a layout change to a control several things sit beside | Widen or shorten it during the next pass over the sidebar, where the neighbouring widths can be judged together rather than one control at a time |

| C23 | **Measured, harmless, recorded so the next reader is not alarmed (2026-09-11).** After a table is typed over, `_table_grids` still holds an entry whose frame widget is already destroyed; the text widget itself holds no embedded window, so nothing is drawn over the text and the user sees nothing wrong. The next render rebuilds the list. Same family as the nested-dropdown bind bookkeeping already in ROADMAP's Known limitations | Prune the registry when the grids go, if any future work touches `_teardown_table_grids`. Do NOT write a check against the list itself — that is what C10's first version did, and it asserts bookkeeping the user cannot see |

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
