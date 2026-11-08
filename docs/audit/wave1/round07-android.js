// The final audit: run wf_bf6993de-e43, started 2026-10-29 15:49 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round7-android',
  description: 'Final audit wave 1, round 7 (Android): 5 read-only break-it agents re-attack every round-6 Android fix by name (the days model and the 0.12.0 upgrade, the template draft and interface, the data and limit fixes), round 6 gaps and the seams with desktop parity; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '5 Android finders: days model, draft and UI, data and limits, round-6 gaps, seams and parity' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r7a'
const R6AGAPS = '<scratchpad>\\wave1\\r6a\\not_covered.txt'
const R6ASUMMARY = '<scratchpad>\\wave1\\r6a\\summary.txt'
const R6AFINDINGS = '<scratchpad>\\wave1\\r6a\\findings'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project, and on 2026-10-29 a test run took the owner's whole computer down -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- YOU MAY NOT run gradle, adb, the emulator, docker, tools/make_days_fixture.py, any test runner, or touch any phone: one emulator exists and the session owns it, and a phone attached is the owner's. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- MEMORY CEILINGS (the machine has 15.6 GB and about 4 GB free; the desktop's audit runs beside yours): every Python probe begins with these two lines, before any other import:
    import sys; sys.path.insert(0, r'${DESKTOP}\\tools'); import guest; print(guest.settle(512, 512))
  and no probe builds a fixture whose size comes from a value a bug could make huge (a cap read from the code, a count from a file): sizes are literal numbers you chose, at most 2,000 rows / 5 MB.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE ANDROID APP: ${ANDROID} (branch audit/a-val1 at cc5b853, checked out; do not switch branches; version 0.13.0 plus the audit's fixes). Kotlin + Jetpack Compose, the same notebook format as the desktop (docs/DATA_FORMAT.md). Read its README, CLAUDE.md, docs/STATUS.md and docs/ISSUES_LOG.md -- its stories "A day's text in a copy the other program erased" and "A cap that cut what it was meant to keep", and "What the audit's sixth round left".
Work by reading the code closely, and with Python probes in SCRATCH_DIR (build a hostile backup .zip or share code; replay a Kotlin rule in Python to show its output; for parity, run the DESKTOP's pure core -- noteorganizer/core, which never imports tkinter -- from a copy inside SCRATCH_DIR with the guest lines first and APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import, asserted first). The JVM tests in app/src/test show how each rule is exercised; app/src/test/resources/days_cases.json is the desktop's own answers for 21 days cases (tools/make_days_fixture.py made it; DaysTest compares). Every finding needs EXACT reproduction steps the session can replay on the emulator (what to tap, what file or code to feed) plus the code path (file:line) that proves it.
THE ROUND-6 ANDROID FIXES: 'git -C ${ANDROID} log --reverse --format="%h %s%n%b" 24aeb6f..cc5b853' lists them with their reasoning and mutants. Round 6's findings, one line each: ${R6ASUMMARY}; one JSON per finding in ${R6AFINDINGS}. In short: 91c0264 Undo/Redo place the cursor through placeCaret (a caption, a line above a table, list markers too), and Insert table writes nothing where no field shows it and says where to tap; f873ee2 a checklist row keeps its own words at the 2,000 cap (Editing.fitRow, the desktop's _limit_entry; RowCap said once; weighed in code points), a moved row stays in sight (keepMovedInSight; drag lands on the nearest drawn row), a long row is read whole (ReadOnlyRow); 6c7c96b the template editor draws a long list in part (TemplateRows: first 200 and last five, Show for more), keeps "A new item" to a row's length (Templates.newRow), refuses Add at 1,000 (CHECKLIST_FULL) and Save with waiting words that do not fit (waitingLeftOut); cef36b1 the comments weighed for the rescue copy as a text of their own (shouldKeepPrevious); 1bde357 Find's stop in a row read in parts brings the part into sight, and the template editor shows the app's messages over itself; fe714f7 THE OWNER'S DAYS MODEL: a turned-off series' days with own text live in the NOTE (Notebook.daysHoldOwnText, clearDays), no copy carries days (carryDays gone), a share code restarting a series keeps the old deleted days in its copy, a restore that ends the repeat leaves the series' days in the copy, and 0.12.0's days kept only in _prev come back into the note as it is read (daysBackFromCopy, at load on the raw notes array and in Normalize.normalizeNote for imports); 5f5318c a template being written is kept as a draft (template_draft.json in noBackupFilesDir) when the app goes to the background, and Settings > Templates offers it back ("You were writing a template. Continue it?" [Continue] [Discard]); a57f1d4 AppSheet can show the app's messages over itself, and the details sheet does (the Repeat sheet's turn-off message).
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; offline (no INTERNET permission), no accounts, no Terms & Conditions; Google's backup on by default with an in-app switch; Off sending Android a marker file; the Undo bar lasting 10 s / 8 s; long unbroken text read-only; the share ceiling (100,000 Latin, weighed in bytes) said before the share; the PDF asking first ([Web page][PDF, first 40 pages][Cancel]); the long code dialog; on a series restarted from another date or rule, only the old series' deleted days are dropped and days with their own text stay; a turned-off series' days with own text living in the note, and the one-time move of 0.12.0's _prev days into the note (attack HOW it is done, not THAT it is done); the template draft kept in noBackupFilesDir, offered at Settings > Templates.
KNOWN OPEN, do not re-report unless worse: "What the audit's sixth round left" in docs/ISSUES_LOG.md (a word a keyboard commits past the cap cut as a paste is; a moved row with no Undo of its own; the template editor's rows a box and two buttons each, 2.5-3.0 s to open 1,000 rows of 2,000 letters; a share code's turn-off keeping days with no own text until the next edit; a row read in parts starting each part on its own line; long_lines' 150,000-letter title timing); and from round 5: a three-cell row typed by hand becoming a grid at its second pipe; past 40,000 drawn lines the end is read-only; the first 200 checklist rows redrawn per letter at 0.2 s; two quick checklist Undos restore rows out of order; Importing.apply's JSON work on the main thread; an already-bloated settings.json filtered on read but rewritten only at the next paint; the template picker and Templates page not lazy (capped at 1,000); a fitted attachment name not round-tripping through the desktop's import; Backspace at a field boundary does not join lines.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash, freeze or ANR, hostile input included; nothing from outside executes or escapes the app's storage, and no other app can read the notes; an ordinary person (TalkBack users included) is never trapped or misled; the two apps agree on every note that travels between them.
Severity: critical = notes lost/corrupted, or outside content executes / an internal file reaches another app / data leaves the phone without the person's action. high = crash/ANR, freeze over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes; a note that travels and comes back changed. medium = misleading or wrong but recoverable; a slowdown a mid-range phone would feel at realistic sizes; an accessibility trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran a probe and saw it (a Python replay of the Kotlin rule counts if you say so); otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 20 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'a7r1-days-model', focus: `RE-ATTACK THE DAYS MODEL BY NAME (fe714f7, a57f1d4's message, and the 0.12.0 upgrade). The phone's 0.12.0 (on the owner's phone now) wrote a turned-off series' days only into _prev; fe714f7 brings them back into the note as it is read (daysBackFromCopy) and stops carrying days in copies. Attack HOW: (1) every place notes are READ: notes_data.json at load (the raw array), Normalize.normalizeNote for imports -- and trash.json (a Trash entry holding a 0.12.0-shaped note: is the move applied there, and on Restore from the Trash?), the backup .zip import's Add and Update, a share code's import and its update of an existing note, Google's backup restore (a whole notebook restored by Android), the template made from such a note; is any reader missed? (2) is the move WRITTEN BACK once, or done at every read -- and if written, by which save, and does a notebook that changes nothing else get rewritten at every start (wear, races with the desktop over a synced folder)? (3) shapes the fixture's 21 cases do not hold: a note whose _prev holds days with own text AND the note holds days without own text; a note that repeats again with a _prev from the old series; a _prev that is a copy of words alone yet holds days (hand-edited, or older); moved days (moved map) and overrides whose dates are outside the old series; an exceptions list with duplicates or dates in another format; a day whose own text is only whitespace or only comments; (4) the move then "↩ Restore previous": does the restore duplicate the days, bring back a series whose days are in both the note and the copy, or lose the days (the copy's days were moved, the copy then replaced)?; (5) daysHoldOwnText vs the desktop's days_hold_own_text (noteorganizer/core/model.py, recurrence.py day_as_kept): replay both on the same inputs, including title/body/comments differences of only whitespace, an override equal to the series' own text, astral characters; (6) a one-off's inert days in a share code or an export (text, markdown, PDF, web page): shown? leaked into the other app as live days?; (7) a57f1d4: is the turn-off message shown twice (once over the details sheet and once in the main window when the sheet closes), or lost if the sheet closes within the message's time?` },
  { key: 'a7r2-draft-and-ui', focus: `RE-ATTACK THE TEMPLATE DRAFT AND THE ROUND-6 INTERFACE FIXES BY NAME (5f5318c, a57f1d4, 91c0264, 1bde357). 5f5318c the draft (Templates.Draft, saveDraft, loadDraft, deleteDraft, draftTarget, draftLostItsTemplate; AppState.keepTemplateDraft; MainActivity's flush calls state.flush then state.keepTemplateDraft): when is it written -- onStop only? what of a process killed without onStop (the system's low-memory kill after onStop is fine; a crash; "Force stop"; a reboot), a configuration change (rotation, dark mode, font size, a split screen) while the editor is open -- does the draft get written and then offered on top of the editor still open?; two drafts in a row (the second overwrites the first? the first template's words lost unasked?); a draft for template A, then A renamed or deleted from another route (Settings > Templates, an import, a backup Update) -- does Continue open the right template, a wrong one with the same name, or write over a template that is now a different one?; Continue then Save when the target was renamed to a name another template holds (two templates of one name?); Discard -- does it delete only the draft; a draft larger than a template may be (1,000 rows of 2,000 letters, the waiting box) -- written atomically, read back whole, within a memory bound?; a corrupt draft "set aside, never offered half" -- where does the set-aside file go, does it pile up at every start, is it ever cleaned?; the draft in noBackupFilesDir: is it ever reachable by another app, by a share, by the backup .zip export?; the question's buttons with TalkBack and a hardware keyboard, and dismissed by Back (comes back next time, as said?). 91c0264 placeCaret in Undo/Redo: Undo/Redo of a caption added under a table, of a line made above a table, of list markers on a selection that spans a table, at the very start and end of a note, in a note at 40,000 drawn lines; Insert table "writes nothing and says where to tap": with the cursor in a caption, in a checklist row, in the title, with a selection. 1bde357 Find's stop in a ReadOnlyRow: the first and last part, a word split across parts, Find next/previous across parts and rows, rotation while a part is in sight; the template editor's messages over itself: shown twice when the editor closes?` },
  { key: 'a7r3-data-and-limits', focus: `RE-ATTACK THE ROUND-6 DATA AND LIMIT FIXES BY NAME (cef36b1, f873ee2, 6c7c96b). cef36b1 shouldKeepPrevious weighs the comments as a text of their own: is it IDENTICAL to the desktop's rescue_copy_due (noteorganizer/core -- replay both on the same inputs: comments only, body only, both changed a little, both changed a lot, under-15-letter changes, emoji, CRLF)? Can a big comment edit now make a copy REPLACE an older copy that held a body the person needed (one slot)? Does every save route pass the comments (the editor, a share-code update, a backup Update, Restore previous, the template applied)? f873ee2 Editing.fitRow: an edit within the cap, one leaving the words shorter, past it -- a replacement of a selection by a longer paste (is the selection's removal counted as room?), IME composition (a composing region that grows past the cap, then is committed), a paste of only combining marks or ZWJ sequences at the cut (a family emoji split into its parts?), a surrogate pair at exactly the cut, a row of 2,000 code points that is 4,000 UTF-16 units moved through Share and the desktop (code points vs Python len: is it the same count for every character, including lone surrogates from a hostile code?); RowCap "said once while edits meet the cap" -- said again after the person leaves and comes back?; keepMovedInSight -- a move by TalkBack's custom action of the first and last rows, the 200th and the first tail row, a drag that crosses the "… N more rows" line upward and downward fast, then Undo of the move; ReadOnlyRow's long row read whole: editing a row that long (is it read-only, and is that said?). 6c7c96b TemplateRows: a row moved across the hidden middle in the template editor, Show more then Save (are hidden rows saved whole and in order?), waitingLeftOut at exactly 1,000 and with the box holding only spaces, Templates.newRow vs the desktop's strip()[:2000] on leading/trailing whitespace, NBSP, tabs, newlines inside the box (a paste of many lines: one row or many?).` },
  { key: 'a7r4-round6-gaps', focus: `WHAT ANDROID ROUND 6 SAID IT DID NOT COVER. Read ${R6AGAPS} (every section and the skeptic's not_checked), "What the audit's sixth round left" in docs/ISSUES_LOG.md, and the story "A day's text in a copy the other program erased". Pick the gaps most likely to hide a defect that matters (data loss, crash/ANR, leak, a trap) and probe them by reading and Python replay -- at least five, and say which you skipped and why. Include: any round-6 fix not walked on the emulator (the commit bodies and the walk's limits_round6, days_in_the_note and template_draft in tools/emulator/walk.py say which were, and what each walk part checks -- is any check weaker than the fix's promise?); the process ended behind Home mid-way through each round-6 path (a row being fitted, a move across the hidden middle, the template editor with Show more drawn, a Find in a row read in parts); TalkBack over the new controls (the draft question, the template editor's Show, a row read in parts); a 16 KB-page device; work that grows with the square of the note size in the new code (daysBackFromCopy at load over 1,000 notes with 1,000 days each, fitRow per keystroke on a 1,000-row list, TemplateRows' keepMovedInSight); and the upgrade from 0.12.0 on the owner's phone: install over it, first start, every note read -- what a person sees, and whether anything is written before they touch a note.` },
  { key: 'a7r5-seams-and-parity', focus: `THE SEAMS BETWEEN THE ROUND-6 ANDROID FIXES, AND THEIR PARITY WITH THE DESKTOP'S ROUND-6 FIXES. Seams: the template draft (5f5318c) x TemplateRows' hidden middle (6c7c96b) x the 1,000 cap and waitingLeftOut (is a draft of 1,001 rows possible, and what does Continue then Save do?) x fitRow on its box; the comments weighing (cef36b1) x the days moved into the note (fe714f7) x Restore previous (can either replace the one slot holding the days' only copy?); the days move x Trash x the backup export (does an export written right after the upgrade hold the days in the note, in the copy, or both, and does the desktop read that export the same?); a57f1d4/1bde357's messages over sheets and dialogs x two messages at once (the turn-off's and a row cap's). Parity (a note made on one app and opened on the other must come back the same): replay the DESKTOP's own core (noteorganizer/core, isolated as in the rules) and the phone's Kotlin rule on the same inputs for: the 1,000-item checklist ceiling at every door (desktop 6db4824 refuses with "Checklist full" -- the phone's CHECKLIST_FULL says "A checklist holds at most 1000 items." -- the same doors on both? a desktop note of exactly 1,000 items gets an Add on the phone?); the comments rescue rule (desktop 45899a1 vs cef36b1); the days back from the copy (desktop 5e228c0 _days_back_from_copy vs daysBackFromCopy) on shapes NOT in days_cases.json (moved days, a Trash entry, a copy of words alone holding days, an update's copy of a note that did not repeat -- the desktop never takes those in: does the phone refuse them too?); Use template over a note (desktop 2058d8f leaves a saved note and saves it first -- what does the phone do with a note open and Use template?); the 2,000-letter row cut (desktop _limit_entry vs fitRow) on astral, combining and CRLF input. A disagreement that changes a note that travels is high.` },
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
  return `You are a break-it auditor in the FINAL audit before the Note Organizer Android app is published (Google Play). This is ANDROID ROUND 7: round 6 found 12 distinct Android defects (2 high, 6 medium, 4 low), fixed in 8 commits, among them the owner's decision on where a turned-off series' days live (the note) and a draft for a template being written; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the Android app's round-7 break-it findings in the final audit of Note Organizer. Five auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names (file:line), re-run its Python probe if it left one in its scratch folder (with the guest lines first), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open item, whether an earlier fix covers it (git -C ${ANDROID} log 24aeb6f..cc5b853 for round 6), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`android round 7: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:android', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
