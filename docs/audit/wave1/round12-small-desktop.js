// The final audit: run wf_140b20c4-493, started 2026-10-31 02:57 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round12-small-desktop',
  description: 'Final audit wave 1, round 12, small for the usage limit (desktop): 2 read-only break-it agents re-attack the round-11 fixes with the seams around them, and what rounds 10 and 11 did not cover; a skeptic re-checks the findings of medium or above',
  phases: [
    { title: 'Attack', detail: '2 desktop finders: the round-11 fixes and their seams, the round 10-11 gaps' },
    { title: 'Refute', detail: 'one skeptic re-checks the findings of medium or above, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r12'
const SMOKE = '<scratchpad>\\wave1\\r1\\_smoke\\probe.py'
const R10GAPS = '<scratchpad>\\wave1\\r10\\not_covered.txt'
const R10SUMMARY = '<scratchpad>\\wave1\\r10\\summary.txt'
const R10FINDINGS = '<scratchpad>\\wave1\\r10\\findings'
const R10FIX = '<scratchpad>\\wave1\\r10fix'
const R11GAPS = '<scratchpad>\\wave1\\r11\\not_covered.txt'
const R11SUMMARY = '<scratchpad>\\wave1\\r11\\summary.txt'
const R11FINDINGS = '<scratchpad>\\wave1\\r11\\findings'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project, and on 2026-10-29 a test run took the owner's whole computer down -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- NEVER run qa*.py, test_*.py, tools/run_tests.py, tools/mutate.py, a qa/story_*.py script or note_organizer.py inside a repository, and never run the app on the Windows desktop (it would open windows on the owner's screens). Never call os.startfile on a real file. No gradle, adb, emulator. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- THE LINUX IMAGE HAS ONE DOOR, and you use it for every run of the app: write your probe as a .py file inside SCRATCH_DIR and run
    py ${DESKTOP}\\tools\\linux_ci.py --probe <SCRATCH_DIR>\\<name>.py
  NEVER a docker command of your own (no docker run/exec/kill/stop/rm): a killed docker client leaves its container running. The door takes this machine's one heavy-job turn: while another run holds it, yours prints "machine : waiting for ..." and waits. So call it with the Bash tool's timeout at 600000 ms; if the call times out while waiting, nothing was started -- wait and try once more later, and if it still waits, note it under not_covered. Exit 75 means it gave up waiting. Exit 124 is your probe hanging past its 600 s limit (inside the container: answer or stub every dialog -- app.show_info / show_warning / ask_yes_no / ask_yes_no_cancel / _themed_dialog). Only one door call of yours at a time. Keep each probe short (well under 600 s): many small checks in one probe are better than many probes, since every run waits its turn behind the other auditors'.
- Every Python probe on WINDOWS begins with these two lines, before any other import (the ceiling only, no turn: such probes must be small):
    import sys; sys.path.insert(0, r'${DESKTOP}\\tools'); import guest; print(guest.settle(512, 512, heavy=False))
  and no probe, on either side, builds a fixture whose size comes from a value a bug could make huge (a cap read from the code, a count from a file): sizes are literal numbers you chose, at most 2,000 rows / 5 MB.
- The machine is shared: a timing claim needs a same-run comparison (with and without, or small and large), never one absolute number.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val1, checked out; do not switch branches). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, docs/ARCHITECTURE.md, and docs/ISSUES_LOG.md -- its stories "Round ten: the days a date held without a word, and older words given back", "Round ten: the note read again by every reader, and an edit the find bar never heard" and "The test that took the computer down" (with its round-seven to round-ten follow-ups) describe the round-10 fixes.
HOW TO RUN THE APP: only through the door in the rules. Inside the container your probe runs in a fresh throwaway folder that already holds note_organizer.py, noteorganizer/, _qa_support.py and guest.py (so "import note_organizer as NO" works there), the repository is mounted read-only at /repo, and SCRATCH_DIR is /work (read-write: write outputs and photographs there; read your own seed files from there). Seed notes by writing notes_data.json in the current folder BEFORE building NO.NoteOrganizer(). ${SMOKE} is a working older example (it copies the app itself to /tmp/app; either way works). qa/qa*.py and qa/_qa_support.py show how the suite drives the app (read for technique; never run them on the host). For a photograph inside the container, grab the app's own window (PIL ImageGrab under Xvfb, or xwd of its window id) into /work and LOOK at it.
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with the guest lines first and APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE importing the app's code (assert that first).
`

const FIXES = `
THE ROUND-11 FIXES (c55a9dd on audit/d-val1 -- 'git show c55a9dd' gives its reasoning; round 11's findings, one line each: ${R11SUMMARY}; one JSON per finding in ${R11FINDINGS}; what round 11 did not cover: ${R11GAPS}; the session's take-back probe over 9,000 editor-made shapes, with idempotency and a reset after: <scratchpad>\\wave1\\r11fix\\core_probe\\probe1.py). (a) MOVES: _day_is_free refuses a date the series keeps an override for that no day is drawn on (off the schedule, or deleted with its edit kept), and a day's own date is no longer free whatever stands on it (the phone's Phase 3 rule); _move_this_day says 'This series still keeps the words of a day on ...'; _reset_occurrence_override asks _day_is_free before any question ('Another day of this series is on ... now'); _undo_day_move asks it as before. (b) THE TAKE-BACK: spend_series_days/_copy_days_placed drop a copy's day only where the note deleted that day; one with words that the note's day does not hold (_own_words_held: every word the copy's day holds unlike its own series must be the note's day's), or that lost a tie for its date, stays in _prev['overrides'] under the date it wanted (its own key on a second tie), and Restore previous brings it (rescue_copy_spent is false while they are there). The owner chose this over a finer test of the words on 31 Oct. Written down: a copy is one slot -- a later turn-off or big delete on that note replaces it. (c) Settings > Your name is under _limit_entry. Mutants DR140-DR144, RX88; MV06, DR132, DR135 re-aimed. The phone's side: a8c74db, 8bafc63 in ${ANDROID} (its read path, daysBackAsRead, kept too).
THE ROUND-10 FIXES (all on audit/d-val1; 'git log --reverse --format="%h %s%n%b" cd5527f..HEAD' lists them with their reasoning and mutants). Round 10's findings, one line each: ${R10SUMMARY}; one JSON per finding in ${R10FINDINGS}. The fixers' briefs, draft test rows and probes: ${R10FIX} (data\\ and android_days\\ the data fixer's, perf\\ the speed fixer's with its photographs in perf\\shots, walk\\ the find fixer's with its photographs in walk\\shots, the tools fixer's mutant runner mutant_tools.py).
DATA (04044ce, 99f041e; mutants DR131-DR139, DR126/DR44/DR32/DR127 re-aimed): spend_series_days works BY THE DAY, not the date -- a copy's day is dropped only where the note deleted that day or wrote words of its own for it; anywhere else its words go to the date the note draws that day (_copy_days_placed: where the note moved it or where a taken copy move put it, else its own date; an edit there with no words of its own -- day_has_words -- takes the copy's words and keeps its colour and category; an edit the copy draws on no day stays on its date); _copy_moves_taken drops transitively a copy move onto a day whose own move stays behind; _dates_held still decides the copy's deleted days and moves. _turn_off_rescue_copy: ANY earlier copy but an Update's (which is kept whole first) gives its words to the new copy only when rescue_copy_due(copy -> note) says the note lost words, whatever series it held; else the note is copied as it stands. _repeat_off_line promises Restore previous only while _holds_unspent_rescue. Written down, not fixed: a notebook this build saved must not go back to 0.97.405; the fuzz's residual shapes (a copy holding two edits for one date, one drawn on no day) neither app writes.
SPEED (41dcc6f, 1400717, c5f1d65, 18b35a6; mutants RX36-RX59, RX80-RX86, SP28-SP30, DM01 re-aimed): a save, an opening and a key read the note ONCE (_capture_and_read; save_current_note(body_read=...); _char_offsets(..., text=) counting Tk columns in Python -- a window or image one, an emoji two; _extract_paragraphs/_extract_formatting from the caller's text; _lines_starting_in per para_/align tag; _line_head reads 64 characters of the caret's line, the whole line when its start is blank, a pipe or a decimal run); the doubled snapshots removed; Ctrl+C, the size/font picker, Tab and the bullet button over a selection, the renumbering read once; the format buttons answer from tag ranges (_stretches_over, _only_line_breaks); _spread_typed_run finds the typed run's space in Python, not by Tk's search; the per-key word count waits (_count_waits_for_pause, _word_count_due) while the find bar shows hits, caught up at the pause and when the bar closes; the spelling underlines at most 500 a line and 2,000 a box, those nearest the caret (core/spelling.nearest_underlines). Byte-for-byte equivalence of the stored note against cd5527f's readers on 80 random notes.
FIND AND TITLE (8d66be3; mutants RX60-RX79, RX29/RX30/RV06/RV07 re-aimed, RX31 dropped): _schedule_autosave tells the find bar of every edit; the EditWithoutKey bindtag, first in the body's, title's, comments' and date's bindtags, hears Tk's own <<Cut>>, <<Paste>>, <<Clear>>, <<PasteSelection>> and schedules the autosave; _align_table_on_leaving schedules it too; the find model remembers what it was read from (_find_stale) and Enter rescans when the note moved under it; a line-break query is found in Python (_find_across_lines), Tk's search no longer called by the find code; emoji queries go through the same loop with _tcl_lower; clipboard.fragment_of finds <body with re.I; the title's <<PasteSelection>> goes through its paste's cap and one-line rule (_on_title_paste_selection, _title_take_paste); _limit_entry's boxes have a middle-click door; _title_within_limit(proposed, current) has the shrink rule; the title paste and _limit_entry measure room before deleting a selection (_entry_selected); add_placeholder clears the hint on a middle-click. And the session's 491e942 (found by the phone's round 10; RX87): _limit_entry says "Pasted text shortened" only when words were left out, not when its cap took only the paste's own trailing space, as the title has since 737efe7.
MACHINE SAFETY (790487e, 6a28f7c, 30903cc; GT42-GT57 in copies by ${R10FIX}\\mutant_tools.py, GT58 in the catalogue; GT54 expected to survive): every suite's as_a_guest finds where 'import note_organizer' would load the app from and REFUSES if that app's notebook_location.txt names any folder; _qa_support.seed_here is the one seed and refuses unless the folder the app will open (where_the_app_opens: the named folder, else resolve_data_dir) is the working folder; hermetic_seed = the scratch marker + seed_here; test_data_safety, doc_screenshots, visual_scenes, probe_bar_width use it; check_guest item 12 stands a stand-in notebook_location.txt (absolute and %USERPROFILE%) in a checkout and every suite opening must refuse; initialise(app_dir) still reads the location file (only its docstring changed). check_guest item 7/8: PowerShell's own parser (ParseFile through -EncodedCommand) reads the sandbox script, a param/begin/process block, #requires/using, a trap, more than one if-clause or an else refused, the literals' values re-quoted by ps_literal for the cross-check, code after '#>' a statement, any of PowerShell's five single quotes refused in a literal. linux_ci's tracked_copy refuses a link or junction at a tracked name or any folder of it.
Accepted by the owner, NOT findings: share codes Base64+zlib (not encryption); offline, no accounts, no Terms & Conditions; Tk 8.6 exposes no names/roles to screen readers; the zip build adopting its unpack folder; USERPROFILE missing; Trash clock far ahead; clock set back mid-session; the Settings section entries draw no keyboard ring; an over-long checklist item's row shows no way to read the rest beyond its tooltip.
KNOWN OPEN LOWS (do not re-report unless you show it is worse than low): a template lost at close after a failed templates write; pasted HTML that is markup-only read whole; the paste ceiling counted in characters, not Tk indices, for astral emoji; search/find boxes and other never-saved one-line boxes take pastes of any length; the find highlights have no bound per line, and a key with the bar open on a paragraph of 2,000 hits was not timed after round ten's typed-run fix; the undo journal reads the note once per undo step; "Your name" takes a middle-click's line breaks raw (its KeyRelease corrector handles the length); cell matches can pass FIND_MATCH_CAP by one per remaining row; a day reset while the series ran from another start can come back from the turn-off's copy when the start returns (judged contrived on both apps); everything in docs/ISSUES_LOG.md's "Written down, not fixed" paragraphs of rounds nine and ten.
NOTE ON THE MACHINE: in round 10 the Android emulator walk held the machine's turn for over two hours and two auditors' door calls gave up after 3,600 s. This round no emulator runs while you work; the turn is shared only with the other auditors. If a door call still gives up, say so and what it would have shown.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled; keyboard-only use works; and nothing the project's own tools do can harm the owner's computer or her data.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action; a test tool that can take the computer's memory or disk or its other windows, or reach the owner's own notebook. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes; a test tool that can leave processes or gigabytes behind. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes, a 1,000-row checklist); a keyboard trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 10 probes at most, the strongest first -- the owner's usage is limited this week: read the functions named, not whole files, and stop when your area is well tried. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two rounds in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'r12d1-round11-fixes-and-seams', focus: `RE-ATTACK THE ROUND-11 FIXES BY NAME (c55a9dd), AND THE SEAMS AROUND THEM. (a) Every road that puts a series' day onto a date: _relocate_day's callers, a deleted day's Undo (_undo_occurrence_delete) when an edit now sits on its date, a day settled off the schedule, the calendar's own routes, Restore previous of a copy whose moves land on such a date, an import or backup bringing moves -- does any still write over a kept edit or hide a day? Are the two messages true in every case they show (a deleted day's kept edit is not 'a day the calendar no longer shows' to the person?). (b) The take-back's kept days, on every road a note travels: load and a second load (idempotent?), duplicate, Trash restore, a backup import and the same backup again (_known_note_differs / shared_update_changes: does a copy holding kept overrides make the same backup read as changed?), a share code (does _prev travel? must it not?), export to every format, Restore previous of a copy holding only kept overrides (what does the note become: overrides replaced while exceptions and moves stay -- and is the swap reversible, copy_replaced_by_restore?), a turn-off after the keep, a big delete after the keep (the one-slot loss: how likely on an ordinary road, and is the status line honest about Restore previous?), _days_back_from_copy on a note that stops repeating with kept overrides, kept days keyed by a date that is a rule date of the note later moved. (c) PARITY: replay the desktop core at c55a9dd (isolated, as in the rules) and the phone's Kotlin (a line-by-line Python replay of a8c74db's Notebook.kt copyDaysPlaced/ownWordsHeld/spendSeriesDays/daysBackAsRead and Days.dayIsFree) on shapes NOT in days_cases.json's 68; a disagreement that changes a note travelling between the apps is high. (d) The round-10 seams round 11 left: the readers-once save x the take-back at load (does the first save write what the editor shows?); the find bar hearing every edit x the readers-once save x the spelling caps (three tag producers, one line).` },
  { key: 'r12d2-gaps-and-tools', focus: `WHAT ROUNDS 10 AND 11 SAID THEY DID NOT COVER, AND THE PROJECT'S OWN TOOLS. Read ${R10GAPS} and ${R11GAPS}, and pick the gaps most likely to hide a defect that matters (data loss, a crash or freeze, a trap, harm to the owner's computer) -- at least five, and say which you skipped and why. Include, unless you show them covered: the PowerShell parser gate (check_guest items 7/8: a script the parser and PowerShell read differently -- a here-string, a backtick continuation, a comment-based help block, an en dash as an operator, a Zero Width Space in a name; is -EncodedCommand side-effect free, -NoProfile set; does the gate ever RUN the sandbox script?); linux_ci's tracked_copy refusal of a link or junction (a hard link, a case-only collision, a path past MAX_PATH); the Windows Tk 8.6.15 side of round 10's readers (the emoji index counting, '+Nc' over an astral character, checked only on Linux's 8.6.16 -- read only, or a Windows pure-core probe where it applies); the format buttons' tag ranges (_stretches_over, _only_line_breaks) beyond the fixer's equivalence run; the spelling caps (core/spelling.nearest_underlines: do the 500 follow the caret? a second box?); the undo journal with a table cell editor open; line breaks pasted into one-line limited boxes (the known 'Your name' low's class -- is any of them a box that stores them and breaks a later read?); and a real key timed with the find bar open on 2,000 hits on a weak machine (round ten did not). NEVER run sandbox_test.ps1, never open any notebook_location.txt in a real checkout, never read the owner's data.` },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      key: { type: 'string' }, title: { type: 'string' },
      severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
      fix_attacked: { type: 'string' },
      mechanism: { type: 'string' }, where: { type: 'string' },
      reproduction: { type: 'string' }, reproduced: { type: 'boolean' },
      evidence: { type: 'string' }, impact: { type: 'string' }, fix_idea: { type: 'string' },
    }, required: ['key', 'title', 'severity', 'mechanism', 'where', 'reproduction', 'reproduced', 'evidence', 'impact'] } },
    covered: { type: 'string' }, not_covered: { type: 'string' },
  },
  required: ['findings', 'covered', 'not_covered'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: { type: 'array', items: { type: 'object', properties: {
      key: { type: 'string' },
      verdict: { type: 'string', enum: ['confirmed', 'plausible', 'refuted', 'already-decided', 'duplicate'] },
      severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
      duplicate_of: { type: 'string' }, reason: { type: 'string' },
    }, required: ['key', 'verdict', 'severity', 'reason'] } },
    not_checked: { type: 'string' },
  },
  required: ['verdicts', 'not_checked'],
}

function finderPrompt(area) {
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store). This is ROUND 12 (small, by the owner's usage limit; its areas rotate, so two clean rounds together cover what one large round did): round 11 found 2 desktop highs (one shared with the phone, one the auditor proved on both apps) and 1 low, fixed in c55a9dd; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${FIXES}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the desktop app's round-12 break-it findings in the final audit of Note Organizer. Two auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (only through the door in the rules, or a Windows pure-Python probe under the same isolation and the guest lines), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open low, whether an earlier fix already covers it (git log a4bbf05..HEAD for round 7), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

SCRATCH_DIR = ${SCRATCH}\\desktop-skeptic
${SAFETY}
${HOW}
${FIXES}
${REPORT}
FINDINGS (JSON):
${JSON.stringify(found, null, 1)}

Return one verdict per finding key. Name what you could not check under not_checked.`
}

const reports = await parallel(AREAS.map(area => () =>
  agent(finderPrompt(area), { label: `attack:${area.key}`, phase: 'Attack', schema: FINDINGS_SCHEMA })
    .then(r => r ? { area: area.key, ...r } : { area: area.key, findings: [], covered: '', not_covered: 'AGENT RETURNED NOTHING' })))
const found = reports.filter(Boolean).flatMap(r => r.findings.map(f => ({ ...f, area: r.area })))
const weighty = found.filter(f => f.severity !== 'low')
log(`desktop round 12 (small): ${found.length} findings from ${reports.filter(Boolean).length} auditors, ${weighty.length} of medium or above sent to the skeptic; the lows kept as reported`)
log('not covered this round, by the owner\'s decision: the round-10 data and editor fixes (round 11 took them)')
let verdicts = null
if (weighty.length) {
  verdicts = await agent(verifierPrompt(weighty), { label: 'refute:desktop', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
