// The final audit: run wf_f2954b4d-86d, started 2026-10-30 19:06 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round10-android',
  description: 'Final audit wave 1, round 10 (Android): 5 read-only break-it agents re-attack every round-9 Android fix by name (the editor half, the data half as the desktop mirrored it, the tools and the walk), round 7 gaps and the seams with desktop parity; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '5 Android finders: editor fixes, data fixes, checks and tools, round-9 gaps, seams and parity' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r10a'
const R9AGAPS = '<scratchpad>\\wave1\\r9a\\not_covered.txt'
const R9ASUMMARY = '<scratchpad>\\wave1\\r9a\\summary.txt'
const R9AFINDINGS = '<scratchpad>\\wave1\\r9a\\findings'
const WALKOUT = '<scratchpad>\\wave1\\android_walk_r9'
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
THE ROUND-9 ANDROID FIXES: 'git -C ${ANDROID} log --reverse --format="%h %s%n%b" b3f04db..HEAD' lists them with their reasoning and mutants. Round 9's findings, one line each: ${R9ASUMMARY}; one JSON per finding in ${R9AFINDINGS}. In short: 2a15681 (AS288-AS305) the editor half -- remembered places (calcMark, the caret) carried through EACH edit of a change in turn, as the desktop's Tk mark of right gravity moves (Paragraphs.moveMark, Calculator.follow/back; list edits via Done.inTurn, pastes via Pasting.Inserted.edits, the calculator's own insert; every History step records its edits in EditorModel.Step, and joined typing adds its letters' edits); pythonIntOf refuses what Python's int() refuses (U+001C-U+001F among them) and repairIds reads ids as the desktop's int(str(id).strip()) does; the title paste gives the desktop's 51f0c44 results in one linear pass, anchored on the cursor the field leaves; a CR that comes in is dropped from the note's text, comments, cells and a template's text; Restore previous weighs styles as the desktop's ae6efe2; the editor reports its foot (format bar, table bar, calculator, 'A new item...' while focused) as AppState.editorFootTop and the window's message is raised above it; while a sheet or the template editor draws the app's messages, the window's own host draws nothing (MessagesShown). aba5a72 (AS306-AS315; AS316 equivalent, survived) the data half, as the desktop's 8b5d6cc -- spendSeriesDays takes the copy's days back per date first (dates held: override keys, exceptions, moved keys AND values; a copy's move never onto a held date) on every road that spends (both reads, updateNote, setRepeat), daysBackAsRead writes the note's days as the normalized view holds them; turnOffCopy: an unspent Update copy first, then a text-only copy OR copyHoldsThisSeries gives its words (the phone has no held save); the Update-copy turn-off word (repeat_off_update_kept via Notebook.keepsUpdateCopy); sharedUpdateChanges reads the arriving note with its copy, then compares bare; updateNote(scheduleFollows = true) lets the Repeat sheet spend once, at setRepeat; the read skips copies that are not recurring or hold an Update's fields; days_cases.json 49 cases (12 new; one answer changed: an older backup whose copy holds a day reset here since now reads as changed). 37d5385 the walk: screen_xml (old dump deleted, three tries, a look that gave up is a failure), drawn_in reads frames after a look, walk.py <folder> <part>... walks one part and a part called from another script takes the turn at its first adb call, limits_round7's said_over check that a message covers neither the box being typed in nor its Add. 64eb4ce docs; 2649a4b the test plan's cases 354-373. Then the session's walk fix after round nine's full walk (the newest commit; its story is the last paragraph of round nine's in docs/ISSUES_LOG.md): the full walk failed 'a template holding the 300 by 300 table opens within two seconds' at 3.2 s for an opening of half a second -- the ripple of a row tapped to open a dialog animates about seven seconds under it on the render thread alone (gfxinfo flag 2), and the walk's own looks make the app draw again; frames_since_reset now lists no flag-2 frame, and drawn_in times an opening by the frames the app's thread held WORKED (5 ms) or more before drawing (DrawStart - IntendedVsync) or that took HELD (0.1 s) or more; a template editor mutated to spend 2.4 s in thirty frames of 80 ms read 2.04-2.10 s and failed.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; offline (no INTERNET permission), no accounts, no Terms & Conditions; Google's backup on by default with an in-app switch; Off sending Android a marker file; the Undo bar lasting 10 s / 8 s; long unbroken text read-only; the share ceiling (100,000 Latin, weighed in bytes) said before the share; the PDF asking first ([Web page][PDF, first 40 pages][Cancel]); the long code dialog; on a series restarted from another date or rule, only the old series' deleted days are dropped and days with their own text stay; a turned-off series' days with own text living in the note, and the one-time move of 0.12.0's _prev days into the note (attack HOW it is done, not THAT it is done); the template draft kept in noBackupFilesDir, offered at Settings > Templates.
KNOWN OPEN, do not re-report unless worse: "What the audit's ninth round left" in docs/ISSUES_LOG.md (the fixer's own list), and "What the audit's eighth round left" in docs/ISSUES_LOG.md (the fixer's own list: the per-note fold of the search query, the title's one-line paste not collapsed for a keyboard's word with its space, prepended marks in the grapheme rule, the "PASS when the state already held" class swept only for process-ending steps), "What the audit's seventh round left" in docs/ISSUES_LOG.md (words waiting in a full list's box said, not kept, behind Home -- the owner's call; the draft on the app's own way out walked by one road of two; Bold, Undo, Insert table proved in the model only; Settings' name box at 80 letters, the desktop's 30; two Trash restores, the older reached by tests alone; a word a keyboard commits past a cap cut as a paste is), "What the audit's sixth round left" (a moved row with no Undo of its own; the template editor's rows a box and two buttons each, 2.5-3.0 s to open 1,000 rows of 2,000 letters; a share code's turn-off keeping days with no own text until the next edit; a row read in parts starting each part on its own line; long_lines' 150,000-letter title timing); and from round 5: a three-cell row typed by hand becoming a grid at its second pipe; past 40,000 drawn lines the end is read-only; the first 200 checklist rows redrawn per letter at 0.2 s; two quick checklist Undos restore rows out of order; Importing.apply's JSON work on the main thread; an already-bloated settings.json filtered on read but rewritten only at the next paint; the template picker and Templates page not lazy (capped at 1,000); a fitted attachment name not round-tripping through the desktop's import; Backspace at a field boundary does not join lines.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash, freeze or ANR, hostile input included; nothing from outside executes or escapes the app's storage, and no other app can read the notes; an ordinary person (TalkBack users included) is never trapped or misled; the two apps agree on every note that travels between them.
Severity: critical = notes lost/corrupted, or outside content executes / an internal file reaches another app / data leaves the phone without the person's action. high = crash/ANR, freeze over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes; a note that travels and comes back changed. medium = misleading or wrong but recoverable; a slowdown a mid-range phone would feel at realistic sizes; an accessibility trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran a probe and saw it (a Python replay of the Kotlin rule counts if you say so); otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 15 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'a10r1-editor-fixes', focus: `RE-ATTACK THE ROUND-9 EDITOR FIXES BY NAME (2a15681). The places carried through each edit (Paragraphs.moveMark, Done.inTurn, Pasting.Inserted.edits, EditorModel.Step): Undo/Redo across a table cell and the note's text in one joined step; an Undo after the note was switched and back; the calculator's own Insert then Undo (does the mark survive as the desktop's does?); a paste that replaces a selection holding the mark; Enter at the mark; an indent change over the mark's line; a step recorded before the build that added Step (an older history: none persist? confirm). The editor's foot (editorFootTop): rotation while a message stands, the calculator panel opening while a message stands, a table bar replacing the format bar, the find bar, a split-screen or freeform window, the keyboard floating; does the raised message now cover the note's text where the person reads, and can it rise under the status bar on a short landscape window? MessagesShown counting hosts: a sheet dismissed while its message stands (does the window host take it, or is it lost?), two sheets in a row, the template editor over a sheet. pythonIntOf and repairIds: ids past Int range (held at the edge -- can two notes collide there?), '+7', ' 7 ', Unicode digits, floats as text. The title paste anchored on the cursor: a selection, a paste at the cap, a keyboard's committed word with a trailing space. The CR drop: a template's comments (the fixer says not handled), a CR typed from a hardware keyboard, a share code carrying CRs.` },
  { key: 'a10r2-data-fixes', focus: `RE-ATTACK THE ROUND-9 DATA FIXES BY NAME (aba5a72), word for word against the desktop's 8b5d6cc. The per-date take-back: a copy override on a date the note MOVED AWAY vs one the note's moved day SITS ON; a copy move onto a copy exception; more moves than the cap leaves; a rule equal but written differently (interval 1 vs absent, weekday order); a series end/count changed so a copy date is no longer an occurrence. Every road that makes a note repeat as its copy's series again on the phone (Restore previous, an import's Update, both Trash restores, a duplicate, the Repeat sheet, Undo) -- which take back when, and can a day reset between the take-back and the next read come back? updateNote(scheduleFollows = true): every caller that should pass it and does not (grep), a Repeat sheet Save that fails between the two writes (Android ends the app between them: is the half-state read correctly at the next start?). turnOffCopy without a held branch: is there truly no phone road where a save while a turn-off waits makes a copy (the Repeat sheet's word save, autosave on background)? sharedUpdateChanges with each kind of copy (series, text, Update holding days); the same older backup imported twice. The read skipping non-recurring / Update copies: a copy whose recurrence is present but empty, a copy from 0.12.0 with a rule written another way. days_cases.json's 49 cases: replay the desktop core at 8b5d6cc on shapes NOT in them.` },
  { key: 'a10r3-checks-and-tools', focus: `THE CHECKS AND TOOLS (37d5385, and the session's 0f69756/9e55407: shot_as_said photographs the moment the words are read; over_keys reads the words' place against keyboard_top from dumpsys window's ime insets; walk_parts_named.py). screen_xml's three tries and the failure on a dump that gave up: any step that now fails where a slow emulator only lagged (flaky by design?), or passes on a stale tree; said_over's block rule against a real dump shape (read the walk's code against the uiautomator XML the session's photos show); keyboard_top on a floating or split keyboard, with no keyboard (None) and a check that then passes vacuously; the walk's turn taken at the first adb call when a part is imported -- can an import alone (no adb yet) start the emulator or touch the phone? The class: every walk check whose PASS needs a premise the walk does not read back (premises-held-before-the-act was decided to stay -- re-report only a new member of the class that hides a real defect). THE SESSION'S FRAME FILTER (the newest commit): can a real slow opening hide under WORKED/HELD (work spread so each frame is held under 5 ms and takes under 0.1 s; work that draws nothing at all, which gfxinfo never lists -- what bounds it?), can a frame of the walk's own look on a busy machine pass 5 ms and give a false red, and does dropping flag-2 frames change any other reader of frames_since_reset (a check whose act draws only render-thread frames now reads [99.0])? AND A LEAD: a parts walk on the same APK (big_table, code_read_away, import_questions_quick, limits_round3-6) failed limits_round5's 'Enter at the end of what is drawn lets the keyboard go and says why' with 'said False, keyboard False', where the full walk passed it -- find the mechanism from the code (a look on a note of 20,000 lines slower than the message's four seconds? says_soon's first look, screen_xml's three tries) and say whether the check, the walk or the app is at fault. Read only; no emulator, no adb, no gradle.` },
  { key: 'a10r4-round9-gaps', focus: `WHAT ANDROID ROUND 9 SAID IT DID NOT COVER. Read ${R9AGAPS} (every section and the skeptic's not_checked), "What the audit's ninth round left" in docs/ISSUES_LOG.md, and the fixer's confessions in the commit bodies (git -C ${ANDROID} log b3f04db..HEAD): no unit test reaches the UI-only wiring (MainActivity's foot padding, the window's host hidden, the Repeat sheet's scheduleFollows pass-through, the CR handling in comments/cells/templates); the editor's foot does not count a checklist row being renamed or the comments box; a CR into a template's comments; ids past Int range held at the edge; the Undo carry for a typing step joined across two tables' cells; EditorTypingTest's Assume on a one-second join. Pick the gaps most likely to hide a defect that matters (data loss, crash/ANR, a trap) and probe them by reading and Python replay -- at least five, and say which you skipped and why. Include the upgrade from 0.12.0 on the owner's phone with round 9's reads (what is written at the first start before she touches a note? does a 0.12.0 notebook gain days in notes she will see on the calendar -- and is each such day one she had before?).` },
  { key: 'a10r5-seams-and-parity', focus: `THE SEAMS BETWEEN THE ROUND-9 ANDROID FIXES, AND THEIR PARITY WITH THE DESKTOP'S ROUND-9 FIXES. Seams: the per-date take-back x the calendar's day view right after a load (merged days shown without a save?) x the dirty state (a note whose days merged at load reads as edited?); moveMark x the CR drop x the title paste anchored on the cursor; editorFootTop x MessagesShown x a sheet over the editor. Parity -- the desktop's round 9 is in ${DESKTOP} (git log 3e4200b..HEAD there: 8b5d6cc the data, 737efe7 the title paste, 098d5a8 the find bar's case folding as Tcl does it): replay the DESKTOP's own core (isolated, as in the rules) and the phone's Kotlin rule on shapes NOT in days_cases.json's 49 cases -- the take-back with moves on both sides, sharedUpdateChanges with each copy kind, the turn-off's copy after Update/text/series copies, the title paste on CR LF and U+2028, int() on the shapes both refuse. And the find: the desktop's find bar now folds case as Tcl does (a letter whose lower case takes more UTF-8 bytes stays as it is); does the phone's in-note find agree on İ, the Kelvin sign, ß/ẞ, Σ/ς? A disagreement that changes a note travelling between them is high; one that only changes what a search finds is low unless it hides a note.` },
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
  return `You are a break-it auditor in the FINAL audit before the Note Organizer Android app is published (Google Play). This is ANDROID ROUND 10: round 9 found 14 distinct Android defects (1 high, 2 medium, 11 low after the skeptic, plus 3 duplicates and 2 already decided), fixed in two commits (the editor half; the data half, mirroring the desktop's own fix) with the tools made to hold to the computer they run on; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the Android app's round-10 break-it findings in the final audit of Note Organizer. Five auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names (file:line), re-run its Python probe if it left one in its scratch folder (with the guest lines first), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open item, whether an earlier fix covers it (git -C ${ANDROID} log cc5b853..HEAD for round 7), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`android round 10: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:android', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
