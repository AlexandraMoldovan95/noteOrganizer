// The final audit: run wf_13ee117b-9d2, started 2026-10-30 08:49 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round9-android',
  description: 'Final audit wave 1, round 9 (Android): 5 read-only break-it agents re-attack every round-8 Android fix by name (the editor half, the data half as the desktop mirrored it, the tools and the walk), round 7 gaps and the seams with desktop parity; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '5 Android finders: editor fixes, data fixes, checks and tools, round-8 gaps, seams and parity' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r9a'
const R8AGAPS = '<scratchpad>\\wave1\\r8a\\not_covered.txt'
const R8ASUMMARY = '<scratchpad>\\wave1\\r8a\\summary.txt'
const R8AFINDINGS = '<scratchpad>\\wave1\\r8a\\findings'
const WALKOUT = '<scratchpad>\\wave1\\android_walk_r8'
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
THE ANDROID APP: ${ANDROID} (branch audit/a-val1, checked out; do not switch branches; version 0.13.0 plus the audit's fixes). Kotlin + Jetpack Compose, the same notebook format as the desktop (docs/DATA_FORMAT.md). Read its README, CLAUDE.md, docs/STATUS.md and docs/ISSUES_LOG.md -- its stories "Kept where it was found, and kept on after it moved" (round 8), "What the audit's eighth round left", "A stop Android made ten seconds late", and "A day's text in a copy the other program erased".
Work by reading the code closely, and with Python probes in SCRATCH_DIR (build a hostile backup .zip or share code; replay a Kotlin rule in Python to show its output; for parity, run the DESKTOP's pure core -- noteorganizer/core, which never imports tkinter -- from a copy inside SCRATCH_DIR with the guest lines first and APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import, asserted first). The JVM tests in app/src/test show how each rule is exercised; app/src/test/resources/days_cases.json is the desktop's own answers for 37 days cases (tools/make_days_fixture.py made it from the desktop's 947e9d3; rebuilt by the session at the desktop's 3e4200b, identical; DaysTest compares). The session's full emulator walk after round 8 left its photographs and log in ${WALKOUT} (walk_log.txt is what it printed): read it for what the walk saw. Every finding needs EXACT reproduction steps the session can replay on the emulator (what to tap, what file or code to feed) plus the code path (file:line) that proves it.
THE ROUND-8 ANDROID FIXES: 'git -C ${ANDROID} log --reverse --format="%h %s%n%b" 67fdd0b..HEAD' lists them with their reasoning and mutants. Round 8's findings, one line each: ${R8ASUMMARY}; one JSON per finding in ${R8AFINDINGS}. In short: d6b5850 (AS258-AS259) Undo and Redo of words typed in a table cell leave the cursor in the cell (EditorModel.restore, inActiveTable); bb6cd71 the walk waits for STOPPED after Home and reads that an ended process is gone; 9a2586c (AS260-AS277) the caret and calcMark carried through Undo/Redo by Calculator.follow (the inActiveTable return too); the category editor and the Repeat sheet pass messages = state.snackbar, AppSheet keeps the message room (weight(fill=false)), the details and category sheets scroll, DeleteCategoryQuestion speaks over the category sheet; Editing.isEnter asks only what came in, a tap that moves the cursor no longer rewrites the title, a stored break becomes a space at the first real edit; fitRow turns CR LF and a lone CR into one break in what came in, a title paste's breaks joined by PyText.split with single spaces; Modifier.saidAloud() (a polite live region) on the cap words under Save as template's name and Your name, on Saved, on the code import's refusal; letterEdge -- a row read in parts never cut inside a grapheme (marks, ZWJ, variation selectors, skin tones, tags, Hangul jamo, flags paired); pythonIntOf reads a rule's numbers as Python's int() (underscores, Unicode digits, the 4,300-digit limit; true/false as 1/0); the list's search not saved (remember), searches kept only up to 10,000 letters (Showing.searchKept). 5b6803d the walk takes the desktop guest's turn at main()'s start (take_the_turn, exit 75 if refused), frames_once_shown() looks at the screen before reading frames (11 reads), end_the_app waits for STOPPED and reads the pid gone, template_draft's Continue/Discard need the question and the tap, limits_round8 (8 checks). 5c7b520 (AS278-AS286, the desktop's 947e9d3) spendSeriesDays in daysBackFromCopy (every normalizeNote), daysBackAsRead (every load, both Trash restores; now for any copy holding a day field), Days.setRepeat and updateNote (not a pin-only save); restorePrevious and applyUpdate do not spend, the next read does; sharedUpdateChanges compares both sides without _prev; commentsKeptByCopy (the phone's lost()) in updateNote's comments-alone branch; turnOffCopy (replacing takeUnspentWords) keeps an unspent update copy whole, adding date/recurrence/days where it lacks them; days_cases.json 37 cases (6 new; two answers changed: 0.12.0's turn-off then on as it was no longer leaves the days in the copy); DaysTest judges a step that writes nothing by the note in memory. c2b2814 docs; 2af3c08 the test plan's cases 331-351. THEN THE SESSION'S FULL WALK AFTER ROUND 8 (10 steps failed, all in limits_round8; two were the app's): 6d8e458 (AS287) the title's box shows the title on one line from the start (EditorModel.titleBox; the note keeps its break until something is typed), because the first letter typed rewrote the box under the keyboard and letters arriving at once were lost (' list' came back ' li'); 0f69756 the walk's own: the category refusal photographed as said, Gym opened upright (on its side the list shows 2 of 4 notes); b851704 the main window's SnackbarHost (MainActivity) now has imePadding and 8.dp while the keyboard is up -- in the note's editor every word said while typing was drawn behind the keys (the walk's photo 112; the words at y 2,220, the keyboard from 1,517); 9e55407 the walk's shot_as_said photographs from the reading that found the words, over_keys checks the place against keyboard_top (dumpsys window's ime insets); b3f04db docs and the test plan's cases 352-353.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; offline (no INTERNET permission), no accounts, no Terms & Conditions; Google's backup on by default with an in-app switch; Off sending Android a marker file; the Undo bar lasting 10 s / 8 s; long unbroken text read-only; the share ceiling (100,000 Latin, weighed in bytes) said before the share; the PDF asking first ([Web page][PDF, first 40 pages][Cancel]); the long code dialog; on a series restarted from another date or rule, only the old series' deleted days are dropped and days with their own text stay; a turned-off series' days with own text living in the note, and the one-time move of 0.12.0's _prev days into the note (attack HOW it is done, not THAT it is done); the template draft kept in noBackupFilesDir, offered at Settings > Templates.
KNOWN OPEN, do not re-report unless worse: "What the audit's eighth round left" in docs/ISSUES_LOG.md (the fixer's own list: the per-note fold of the search query, the title's one-line paste not collapsed for a keyboard's word with its space, prepended marks in the grapheme rule, the "PASS when the state already held" class swept only for process-ending steps), "What the audit's seventh round left" in docs/ISSUES_LOG.md (words waiting in a full list's box said, not kept, behind Home -- the owner's call; the draft on the app's own way out walked by one road of two; Bold, Undo, Insert table proved in the model only; Settings' name box at 80 letters, the desktop's 30; two Trash restores, the older reached by tests alone; a word a keyboard commits past a cap cut as a paste is), "What the audit's sixth round left" (a moved row with no Undo of its own; the template editor's rows a box and two buttons each, 2.5-3.0 s to open 1,000 rows of 2,000 letters; a share code's turn-off keeping days with no own text until the next edit; a row read in parts starting each part on its own line; long_lines' 150,000-letter title timing); and from round 5: a three-cell row typed by hand becoming a grid at its second pipe; past 40,000 drawn lines the end is read-only; the first 200 checklist rows redrawn per letter at 0.2 s; two quick checklist Undos restore rows out of order; Importing.apply's JSON work on the main thread; an already-bloated settings.json filtered on read but rewritten only at the next paint; the template picker and Templates page not lazy (capped at 1,000); a fitted attachment name not round-tripping through the desktop's import; Backspace at a field boundary does not join lines.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash, freeze or ANR, hostile input included; nothing from outside executes or escapes the app's storage, and no other app can read the notes; an ordinary person (TalkBack users included) is never trapped or misled; the two apps agree on every note that travels between them.
Severity: critical = notes lost/corrupted, or outside content executes / an internal file reaches another app / data leaves the phone without the person's action. high = crash/ANR, freeze over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes; a note that travels and comes back changed. medium = misleading or wrong but recoverable; a slowdown a mid-range phone would feel at realistic sizes; an accessibility trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran a probe and saw it (a Python replay of the Kotlin rule counts if you say so); otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 15 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'a9r1-editor-fixes', focus: `RE-ATTACK THE ROUND-8 EDITOR FIXES BY NAME (9a2586c, d6b5850). Calculator.follow through Undo/Redo: Undo of a change that SPANS the mark, Redo after the note was switched and back, Undo after the calculator's own Insert (the mark moves with it?), a table cell's Undo then the calculator before the cell lets go. The sheets' messages: every AppSheet now passing messages -- a message while the keyboard is up in landscape, two messages in a row, a sheet dismissed while its message stands (does the bar move to the window under it, or vanish?), the details sheet's scroll vs a message room of fill=false on a tiny phone. Editing.isEnter: an IME that commits a word with a trailing newline, a paste of exactly one line break into the title, Gboard's "Enter" vs Samsung's, a hardware keyboard. fitRow's CR handling: a paste that is ONLY CR LF, CR LF at the exact cap, a row whose own words hold a lone CR from an old notebook. saidAloud(): repeated announcements on every recomposition? (a live region re-reading on each letter would be a trap for TalkBack users). letterEdge: an emoji at exactly a part's edge made of 10 code points, a flag sequence odd-length, a Devanagari conjunct; the bound on letters read. pythonIntOf vs Python on ' 7 ', '+7', '0x7', '7.0', '٣' and a 4,301-digit string; true/false written back as 1/0 by the phone -- does the desktop read the phone's 1 as the same rule (normalize_recurrence equality)? Showing.searchKept: a search of 10,001 letters, then Android ends the app. AND THE WALK'S TWO (6d8e458, b851704): titleBox through Undo/Redo of the title (is a break the Undo brings back shown as a space, the cursor kept?), a title with two breaks or a CR, a title edited and then put back by hand to its stored text -- is the note saved, and with or without its break? The main window's messages over the keyboard: on its side, on a tablet's two panes, a floating or split keyboard, the keyboard closing while a message stands (does it jump, cover the bar or the +?), and what the message now covers while it stands -- in the walk's photo it lay over "A new item..." being typed into: can a person still see what they type, and does a tap meant for the field land on the message's ✕? Other windows that say words under them: every AlertDialog/Dialog that calls state.say while it stays open (the sheets were fixed in round 8; dialogs were not swept).` },
  { key: 'a9r2-data-fixes', focus: `RE-ATTACK THE ROUND-8 DATA FIXES BY NAME (5c7b520, as the desktop's 947e9d3). spendSeriesDays on every road: list every road on the phone that makes a note repeat as its copy's series again (setRepeat, updateNote, restorePrevious, applyUpdate, a Trash restore, an import's insert, a share code, Undo of a turn-off) and which spend now; can a day reset between a non-spending road and the next read come back? updateNote spending on any save -- a save that changes only a checklist tick of a repeating note: is the copy's day data dropped when the note does NOT hold those days (a copy whose days the note never took)? daysBackAsRead now asked of any copy holding a day field: an update's copy with days (should give nothing), a words copy with days from an older phone build. sharedUpdateChanges without either copy: an update whose only difference is the copy (dropped?). commentsKeptByCopy with lost(): equal losses, CJK, astral, whitespace. turnOffCopy: asked of the note as it was before the Save -- a Repeat sheet save that also changes the words in the same tap. DaysTest's new judging (a no-write step by the note in memory): could it hide a case where the FILE is wrong because the memory is right (a write that never happened)? Replay the DESKTOP's own core on each shape and say where the phone answers differently.` },
  { key: 'a9r3-checks-and-tools', focus: `ARE ROUND 8'S CHECKS AS STRONG AS ITS FIXES' PROMISES, AND DO THE TOOLS HOLD TO THE COMPUTER? (1) For each round-8 fix, its JVM tests and mutants AS258-AS286 (the catalogues in the session's scratchpad wave1\\android_fixes_r8\\ and android_walkfix\\): does each test fail for the defect it names or only one shape of it? a mutant aimed at the wrong place? a promise in a commit body with no test (the sheets' messages are UI-only: is limits_round8 really checking them, or the words anywhere on screen?). (2) The walk's round-8 changes in tools/emulator/walk.py: take_the_turn (what if the desktop repository is absent or its guest refuses mid-walk? the homes it sets -- does anything in the walk read APPDATA/LOCALAPPDATA/TEMP after it, e.g. put_inside's TEMP, adb's own files?), frames_once_shown (does looking at the screen first guarantee the frame finished?), end_the_app and stopped() (the 15 s, a phone whose launcher idles at once), limits_round8's 8 checks (could each pass with its fix reverted?). Read what the walk actually printed: ${WALKOUT}\\walk_log.txt. (3) The class the fixer did NOT sweep: steps that PASS because the state already held before the tap -- find concrete ones in walk.py and say which checks they weaken. Read only; run nothing but small Python reads.` },
  { key: 'a9r4-round8-gaps', focus: `WHAT ANDROID ROUND 8 SAID IT DID NOT COVER. Read ${R8AGAPS} (every section and the skeptic's not_checked), "What the audit's eighth round left" in docs/ISSUES_LOG.md, and the fixer's confessions in the commit bodies (git -C ${ANDROID} log 67fdd0b..HEAD): not walked -- the Repeat sheet's refusal over itself, the calculator after the bar's Undo and Redo, a CR LF paste, TalkBack, the release build (R8 renaming anything the new code looks up by name? read proguard rules and check_release_lookups); prepended marks in letterEdge; the title's one-line paste for a keyboard's word with its space. Pick the gaps most likely to hide a defect that matters (data loss, crash/ANR, a trap) and probe them by reading and Python replay -- at least five, and say which you skipped and why. Include the upgrade from 0.12.0 on the owner's phone once more with round 8's reads (spend at first load: is anything written before she touches a note? does a phone that already moved days in round 7's build lose the copy's days now, and is that right?).` },
  { key: 'a9r5-seams-and-parity', focus: `THE SEAMS BETWEEN THE ROUND-8 ANDROID FIXES, AND THEIR PARITY WITH THE DESKTOP'S ROUND-8 FIXES. Seams: Calculator.follow x the title's isEnter x a stored break; the sheets' messages x the details sheet's scroll x saidAloud (one message read twice?); spendSeriesDays x turnOffCopy x commentsKeptByCopy in one Repeat sheet save; fitRow's CR x the paste ceiling x letterEdge on a row read in parts. Parity (a note made on one app and opened on the other must come back the same) -- the desktop's round 8 is in ${DESKTOP} (git log 81dae88..HEAD there: 947e9d3 and ae6efe2 the data, 51f0c44 the title paste keeping edge spaces, 7391897 words beneath an Undo, 9ff0ab3 held Enter, 503d025 Checklist full once): replay the DESKTOP's own core (isolated, as in the rules) and the phone's Kotlin rule on shapes NOT in days_cases.json's 37 cases -- the desktop's styles_kept on a restore over part of the copy's words (does the phone's replacedByRestore weigh the same?), the desktop's unread-start import word (the phone's equivalent?), a title paste of ' fresh ' with spaces at its edges (the desktop keeps them; the phone?), a rule written with a bool or a string number written back by the phone and read by the desktop. A disagreement that changes a note travelling between them is high.` },
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
  return `You are a break-it auditor in the FINAL audit before the Note Organizer Android app is published (Google Play). This is ANDROID ROUND 9: round 8 found 16 distinct Android defects (4 medium, 12 low after the skeptic, plus 1 duplicate), fixed in two commits (the editor half; the data half, mirroring the desktop's own fix) with the tools made to hold to the computer they run on; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the Android app's round-9 break-it findings in the final audit of Note Organizer. Five auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names (file:line), re-run its Python probe if it left one in its scratch folder (with the guest lines first), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open item, whether an earlier fix covers it (git -C ${ANDROID} log cc5b853..HEAD for round 7), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`android round 9: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:android', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
