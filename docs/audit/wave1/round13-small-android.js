// The final audit: run wf_08665721-d4f, started 2026-10-31 14:28 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round13-small-android',
  description: 'Final audit wave 1, round 13, small for the usage limit (Android): 2 read-only break-it agents re-attack the round-12 fixes, the data half and the editor half, each with its seams; a skeptic re-checks the findings of medium or above',
  phases: [
    { title: 'Attack', detail: '2 Android finders: the round-12 data fixes and seams, the round-12 editor fixes and seams' },
    { title: 'Refute', detail: 'one skeptic re-checks the findings of medium or above, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r13a'
const R10AGAPS = '<scratchpad>\\wave1\\r10a\\not_covered.txt'
const R10ASUMMARY = '<scratchpad>\\wave1\\r10a\\summary.txt'
const R10AFINDINGS = '<scratchpad>\\wave1\\r10a\\findings'
const WALKOUT = '<scratchpad>\\wave1\\android_walk_r10'
const R11AGAPS = '<scratchpad>\\wave1\\r11a\\not_covered.txt'
const R11ASUMMARY = '<scratchpad>\\wave1\\r11a\\summary.txt'
const R11AFINDINGS = '<scratchpad>\\wave1\\r11a\\findings'
const R12AGAPS = '<scratchpad>\\wave1\\r12a\\not_covered.txt'
const R12ASUMMARY = '<scratchpad>\\wave1\\r12a\\summary.txt'
const R12AFINDINGS = '<scratchpad>\\wave1\\r12a\\findings'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project, and on 2026-10-29 a test run took the owner's whole computer down -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- YOU MAY NOT run gradle, adb, the emulator, docker, tools/linux_ci.py, tools/make_days_fixture.py, any test runner, or touch any phone: one emulator exists and the session owns it, and a phone attached is the owner's. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- MEMORY CEILINGS (the machine has 15.6 GB and about 4 GB free; the desktop's audit runs beside yours): every Python probe begins with these two lines, before any other import (the ceiling only, not the machine's heavy-job turn: such probes must be small):
    import sys; sys.path.insert(0, r'${DESKTOP}\\tools'); import guest; print(guest.settle(512, 512, heavy=False))
  and no probe builds a fixture whose size comes from a value a bug could make huge (a cap read from the code, a count from a file): sizes are literal numbers you chose, at most 2,000 rows / 5 MB.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE ANDROID APP: ${ANDROID} (branch audit/a-val1, checked out; do not switch branches; version 0.13.0 plus the audit's fixes). Kotlin + Jetpack Compose, the same notebook format as the desktop (docs/DATA_FORMAT.md). Read its README, CLAUDE.md, docs/STATUS.md and docs/ISSUES_LOG.md -- its stories "Every place a change made, and every date a note holds" (round 9), "What the audit's ninth round left", "Kept where it was found, and kept on after it moved" (round 8, with what the full walk after it found), and "A day's text in a copy the other program erased".
Work by reading the code closely, and with Python probes in SCRATCH_DIR (build a hostile backup .zip or share code; replay a Kotlin rule in Python to show its output; for parity, run the DESKTOP's pure core -- noteorganizer/core, which never imports tkinter -- from a copy inside SCRATCH_DIR with the guest lines first and APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import, asserted first). The JVM tests in app/src/test show how each rule is exercised; app/src/test/resources/days_cases.json is the desktop's own answers for 49 days cases (tools/make_days_fixture.py made it from the desktop's 8b5d6cc; DaysTest compares). The session's full emulator walk after round 9 left its photographs and log in ${WALKOUT} (walk_log.txt is what it printed): read it for what the walk saw. Every finding needs EXACT reproduction steps the session can replay on the emulator (what to tap, what file or code to feed) plus the code path (file:line) that proves it.
THE ROUND-12 ANDROID FIXES (7564f2e, d6a1f70 -- 'git -C ${ANDROID} show 7564f2e'; round 12's findings, one line each: ${R12ASUMMARY}; JSON in ${R12AFINDINGS}; not covered: ${R12AGAPS}; mutants <scratchpad>\\wave1\\r12fix\\mutants_r12.json, AS346-AS351, all killed): copyDaysPlaced adds a copy's day's own words a day holding words lacks after them (wordsAdded, the desktop's _words_added) and spends the copy's days (spendSeriesDays and daysBackAsRead keep nothing in the copy); undoDeleteDay refuses a date another day or a kept edit holds; resetDay and keptThere say 'text or a colour of its own'; the editor moves styles through the edit as made (Paragraphs.moveSpans) for insertTable, addCaption, addLineAbove, deleteTable and insertCalculation, and spansAfterTyping moves a deletion at the cursor the same way; tools/check_test_results.py fails on any skipped test not in MAY_SKIP. days_cases.json 68 cases rebuilt from the desktop core with its round-12 fix.
THE ROUND-11 ANDROID FIXES (a8c74db, 8bafc63 -- 'git -C ${ANDROID} show a8c74db' gives the reasoning; round 11's findings, one line each: ${R11ASUMMARY}; JSON in ${R11AFINDINGS}; what round 11 did not cover: ${R11AGAPS}; mutants <scratchpad>\\wave1\\r11fix\\mutants_r11.json, AS339-AS345, all killed): Days.dayIsFree also refuses a date keepsWordsOn (an override no day is drawn on) and moveDay says why (keptThere); spendSeriesDays AND the notebook's read, daysBackAsRead, keep in the copy's overrides the copy's days whose own words the note's day does not hold (ownWordsHeld) or that lost a tie, by the date wanted; days_cases.json 68 cases rebuilt from the desktop core at c55a9dd (of the 62 before, one changed as intended: the note's own day over the copy's keeps the copy's words in the copy). Written down, not fixed: a copy is one slot; the walk's held_after_tap cuts the opening at the first idle second, not anchored at the tap (a low).
THE ROUND-10 ANDROID FIXES: 'git -C ${ANDROID} log --reverse --format="%h %s%n%b" 5d018c1..HEAD' lists them with their reasoning and mutants. Round 10's findings, one line each: ${R10ASUMMARY}; one JSON per finding in ${R10AFINDINGS}. The fixer's probes, mutant catalogue (mutants_r10.json, AS317-AS338) and test rows: <scratchpad>\\wave1\\android_fixes_r10. In short: 9bc86a0 the data half, as the desktop's 04044ce and 99f041e -- takeDaysBack works BY THE DAY (copyMovesTaken drops transitively a copy move onto a day whose own move stays behind; copyDaysPlaced puts each copy edit on the date the note draws its day, an edit the copy draws on no day stays on its date, a note edit with no words of its own -- dayHasWords -- takes the copy's words with its category and colour laid over, a note edit with words or a note exception wins; datesHeld still decides the copy's deleted days and moves); turnOffCopy gives ANY earlier copy's words but an Update's (kept whole first) only when shouldKeepPrevious says the note lost words, whatever series it held (copyHoldsThisSeries removed); Days.repeatOffWord promises Restore previous only while a copy the note does not hold again remains; days_cases.json 62 cases from the desktop core at 99f041e (fingerprint 3a2c7065). ff950dd DaysTest holds an edit the copy keeps under a day it deleted where the desktop leaves it (AS322). 54390f3 the phone's own half -- Editing.proseEdit reads a typed edit at the cursor and changeAt places a deletion at it; the calculator's place and the lines' looks (Paragraphs.follow's edit) carried through it; Insert table, Add caption, Add line above and Delete table record the edit as made; fitRow and BoxCap.fit take the cursor (keptBy/cursorOf, a row's onEdit, the add box) and say 'shortened' only when non-space words were left out; Organizing.heldId renumbers an id outside 1..Int.MAX (never clamps or wraps), repairIds keeps the first holders, Organizing.Ids gives max+1 or the lowest free number at the edge, Normalize no longer cuts a Long id; the find fold matches the desktop's _tcl_lower (basic plane only, never into more UTF-8 bytes); EditorModel.renamingRow counted at the editor's foot; MessagesShown: only the deepest sheet's host draws (a CompositionLocal depth); EditorTypingTest's timing Assume guards only its own cases. The walk: 5105c92 drawn_in times an opening from the tap with NO look inside the time (held_after_tap: the app's frames, the render thread's left out, and every message on its main thread the Looper logs as slow -- slow_dispatches_logged sets log.looper.<uid>.main.slow before the app starts -- read again until neither grows for a second); messages_held sets Android's accessibility_non_interactive_ui_timeout_ms while a message is read (put back after); limits_round10 walks a row being renamed; 970acf8 'still' only when no frame ends later (gfxinfo keeps a window's last 120 frames). The session's 816a8ca: said_over(touching=True) counts any overlap -- measured on the emulator, the message ended at the renamed row's top even with the fix taken out, so the check passes both ways there (the test plan's 387 for the owner's eye). The session walked big_table (0.40-0.98 s; the slow-template mutant 3.11 s, failed), limits_round5, limits_round10 and days_in_the_note on this build before the full walk. 2a75524 docs; 33bb2df the test plan's cases 374-388. THE FULL WALK on this build: 538 steps passed, 1 failed -- the template of 90,000 cells read 4.5 s (8.3, 8.3, 5.9 run alone) for an opening of 0.62 s read once ten seconds after the tap with no read between: each of held_after_tap's own reads (dumpsys gfxinfo) is a message on the app's thread (ActivityThread$H m=165) that ran 40 ms with that template open, logged as slow, so the reading never went still and a lone frame seconds later was taken in. 368885f: WALK_READ_MESSAGE leaves those lines out, and the opening is the spans before the first [quiet]=1 s gap on the device's clock (0.59-0.67 s in three runs; the template mutant 3.27 s, failed). Photos in wave1\\android_walk_r10 (log walk_log.txt).
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; offline (no INTERNET permission), no accounts, no Terms & Conditions; Google's backup on by default with an in-app switch; Off sending Android a marker file; the Undo bar lasting 10 s / 8 s; long unbroken text read-only; the share ceiling (100,000 Latin, weighed in bytes) said before the share; the PDF asking first ([Web page][PDF, first 40 pages][Cancel]); the long code dialog; on a series restarted from another date or rule, only the old series' deleted days are dropped and days with their own text stay; a turned-off series' days with own text living in the note, and the one-time move of 0.12.0's _prev days into the note (attack HOW it is done, not THAT it is done); the template draft kept in noBackupFilesDir, offered at Settings > Templates.
KNOWN OPEN, do not re-report unless worse: "What the audit's tenth round left" in docs/ISSUES_LOG.md (the fixer's own list: the reset day in a series run from another start, contrived on both apps, among it), "What the audit's ninth round left", and "What the audit's eighth round left" in docs/ISSUES_LOG.md (the fixer's own list: the per-note fold of the search query, the title's one-line paste not collapsed for a keyboard's word with its space, prepended marks in the grapheme rule, the "PASS when the state already held" class swept only for process-ending steps), "What the audit's seventh round left" in docs/ISSUES_LOG.md (words waiting in a full list's box said, not kept, behind Home -- the owner's call; the draft on the app's own way out walked by one road of two; Bold, Undo, Insert table proved in the model only; Settings' name box at 80 letters, the desktop's 30; two Trash restores, the older reached by tests alone; a word a keyboard commits past a cap cut as a paste is), "What the audit's sixth round left" (a moved row with no Undo of its own; the template editor's rows a box and two buttons each, 2.5-3.0 s to open 1,000 rows of 2,000 letters; a share code's turn-off keeping days with no own text until the next edit; a row read in parts starting each part on its own line; long_lines' 150,000-letter title timing); and from round 5: a three-cell row typed by hand becoming a grid at its second pipe; past 40,000 drawn lines the end is read-only; the first 200 checklist rows redrawn per letter at 0.2 s; two quick checklist Undos restore rows out of order; Importing.apply's JSON work on the main thread; an already-bloated settings.json filtered on read but rewritten only at the next paint; the template picker and Templates page not lazy (capped at 1,000); a fitted attachment name not round-tripping through the desktop's import; Backspace at a field boundary does not join lines.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash, freeze or ANR, hostile input included; nothing from outside executes or escapes the app's storage, and no other app can read the notes; an ordinary person (TalkBack users included) is never trapped or misled; the two apps agree on every note that travels between them.
Severity: critical = notes lost/corrupted, or outside content executes / an internal file reaches another app / data leaves the phone without the person's action. high = crash/ANR, freeze over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes; a note that travels and comes back changed. medium = misleading or wrong but recoverable; a slowdown a mid-range phone would feel at realistic sizes; an accessibility trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran a probe and saw it (a Python replay of the Kotlin rule counts if you say so); otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 10 probes at most, the strongest first -- the owner's usage is limited this week: read the functions named, not whole files, and stop when your area is well tried. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'a13d1-round12-data-and-seams', focus: `RE-ATTACK THE PHONE'S ROUND-12 DATA FIXES BY NAME (7564f2e: wordsAdded in copyDaysPlaced, spendSeriesDays and daysBackAsRead spending everything; undoDeleteDay's refusal; resetDay's and keptThere's sentences), word for word against the desktop's 93a9b73 in ${DESKTOP}. wordsAdded: a partial day edit (the phone's own shape, no body) given the series' body; comments only; a number as a title; the same words twice; a day near a cap; idempotency over two reads and a save (updateNote, setRepeat); parity: replay the desktop core at 93a9b73 (isolated, as in the rules) and the phone's Kotlin (a line-by-line Python replay) on shapes NOT in days_cases.json's 68. undoDeleteDay on every road: a moved day deleted, another moved onto its rule date or its held date; the snackbar queue (Undo tapped after a move's own snackbar); a Trash round trip between; the repeat changed between. A disagreement that changes a note travelling between the apps is high.` },
  { key: 'a13d2-round12-editor-and-tools', focus: `RE-ATTACK THE PHONE'S ROUND-12 EDITOR FIXES BY NAME (7564f2e: Paragraphs.moveSpans for insertTable, addCaption, addLineAbove, deleteTable, insertCalculation; spansAfterTyping's deletion at the cursor; check_test_results' MAY_SKIP). The inserts: a table at the note's end (caret past what is drawn, the '\n' put before it), a table inside a styled run's middle (Tk gives it the run's tags: does moveSpans?), a caption whose clearStyle now follows moveSpans, a line above a table whose first cell is styled, Undo/Redo of each (do the styles come back where they were?), the calculator's answer inside a table cell (activeCell: still remap?), Pasting's and carryCellStyles' own remaps. The deletion: an IME that deletes not at the cursor (a word-delete that moves the cursor, a composing region replaced, autocorrect shortening a word), a selection deleted with the cursor at its end, emoji and surrogate pairs at the edge. The gate: is MAY_SKIP's name exactly the test's, and would a renamed test skip silently again? Read only; no emulator, no adb, no gradle.` },
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
  return `You are a break-it auditor in the FINAL audit before the Note Organizer Android app is published (Google Play). This is ANDROID ROUND 13 (small, by the owner's usage limit; its areas rotate): round 12 found 1 high shared with the desktop (a deleted day's Undo over another day), 2 mediums (round 11's kept copy words coming back over a reset; an insert taking the style of the run it lands before) and 3 lows, fixed in 7564f2e; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the Android app's round-13 break-it findings in the final audit of Note Organizer. Two auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names (file:line), re-run its Python probe if it left one in its scratch folder (with the guest lines first), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open item, whether an earlier fix covers it (git -C ${ANDROID} log cc5b853..HEAD for round 7), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

SCRATCH_DIR = ${SCRATCH}\\android-skeptic
${SAFETY}
${HOW}
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
log(`android round 13 (small): ${found.length} findings from ${reports.filter(Boolean).length} auditors, ${weighty.length} of medium or above sent to the skeptic; the lows kept as reported`)
log('not covered this round, by the owner\'s decision: the round 10-12 gaps and the tools (round 14 takes them)')
let verdicts = null
if (weighty.length) {
  verdicts = await agent(verifierPrompt(weighty), { label: 'refute:android', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
