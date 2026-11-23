// The final audit: run wf_7af3bba7-032, started 2026-10-28 22:11 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round5-android',
  description: 'Final audit wave 1, round 5 (Android): 4 read-only break-it agents re-attack every round-4 Android fix by name, hunt the Android twins of desktop round-5 findings, and cover round 4 gaps; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '4 Android finders: data fixes, limit/UI fixes, desktop round-5 twins, round-4 gaps' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r5a'
const R4AGAPS = '<scratchpad>\\wave1\\r4a\\not_covered.txt'
const R4ASUMMARY = '<scratchpad>\\wave1\\r4a\\summary.txt'
const R4AHANDOFF = '<scratchpad>\\wave1\\android_fixes_r4\\HANDOFF.md'
const R5DESK = '<scratchpad>\\wave1\\r5\\findings'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- YOU MAY NOT run gradle, adb, the emulator, docker, or touch any phone: one emulator exists and the session owns it (a full walk is running on it now and needs a quiet machine -- keep your probes light), and a phone attached is the owner's. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE ANDROID APP: ${ANDROID} (branch audit/a-val1, checked out; do not switch branches; version 0.13.0 plus the audit's fixes). Kotlin + Jetpack Compose, the same notebook format as the desktop (docs/DATA_FORMAT.md). Read its README, CLAUDE.md, docs/STATUS.md and docs/ISSUES_LOG.md (its newest story is round 4's, plus "What the audit's fourth round left").
Work by reading the code closely, and with Python probes in SCRATCH_DIR (build a hostile backup .zip or share code; replay a Kotlin rule in Python to show its output). The JVM tests in app/src/test show how each rule is exercised. Every finding needs EXACT reproduction steps the session can replay on the emulator (what to tap, what file or code to feed) plus the code path (file:line) that proves it.
THE ROUND-4 ANDROID FIXES: 'git -C ${ANDROID} log --reverse --format="%h %s%n%b" 815cc8c..audit/a-val1' lists them with their reasoning and mutants (AS147-AS171). Round 4's findings, one line each: ${R4ASUMMARY}. In short: 30a3038 one limit on what a whole note draws (1,000 grid cells across all tables -- a later table shown as its lines with a reason; 20,000 drawn lines in its fields; 100 pieces; past any, the rest is ONE read-only piece with its counts; long prose cut into fields of at most 1,000 drawn lines, all typable; empty lines between read-only lines join them; one line / a title / comments heavier than 150,000 letters with spaces read-only; the cursor follows a line moved into the next field; "… and N more lines"; the template editor uses the same rules); 94ab95c rescue copy: loss = min(changed span, words gone), a repeat turned off keeps an unspent words-only copy's words, the import's Update question says when it replaces an earlier version; aa072cb each identity claimed by the first arriving note (a second comes in as its own note with a new identity), a note planned as new whose uid is back at apply time loses its identity, Organizing.indexOfNote (attach and both day Undos); 2eea143 the share ceiling weighed in BYTES (2 per UTF-16 unit plus the UTF-8 copy, at most 300,000 bytes = 100,000 Latin letters), "about M of them", the count includes the title, the Share code card greyed with its reason before the tap; 2fba942 the PDF asks BEFORE anything is handed over ([Web page] [PDF, first 40 pages | cut at the edge] [Cancel]) and writes nothing into the PDF; e00a008 Restore previous on a day of a series that no longer repeats opens the whole note; ba548e9 the 30%/70% shares of the old text measured as the loss is (Notebook.measured).
The fixer's own confession and open items: ${R4AHANDOFF} (Backspace at a field boundary does not join lines and a selection cannot cross; the template editor's cursor does not follow a moved line; Find does not search the read-only rest; the list's multi-select "Share as a code" still refuses after the tap; a 0.4-0.8 s autosave frame on very long notes; the PDF is drawn into the cache before the question).
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; the app is offline (no INTERNET permission), no accounts, no Terms & Conditions; Google's backup on by default with an in-app switch; Off sending Android a marker file; the Undo bar lasting 10 s; long unbroken text read-only; the share ceiling (100,000 Latin / weighed in bytes) said before the share; the PDF asking first and writing nothing into the file. Report only a defect in how these WORK.
KNOWN OPEN, do not re-report unless worse: two quick checklist Undos restore rows out of order; Importing.apply's JSON work and notes write on the main thread; an already-bloated settings.json filtered on read but rewritten only at the next paint; the template picker and Templates page not lazy (capped at 1,000); the cursor jumping after a paste makes a line read-only; a fitted attachment name not round-tripping through the desktop's import; and the fixer's open items listed above (Backspace at a field boundary etc.) -- report one only if it LOSES data or traps a person.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash, freeze or ANR, hostile input included; nothing from outside executes or escapes the app's storage, and no other app can read the notes; an ordinary person (TalkBack users included) is never trapped or misled.
Severity: critical = notes lost/corrupted, or outside content executes / an internal file reaches another app / data leaves the phone without the person's action. high = crash/ANR, freeze over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a mid-range phone would feel at realistic sizes; an accessibility trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran a probe and saw it (a Python replay of the Kotlin rule counts if you say so); otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 25 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'a5r1-fixes-data', focus: `RE-ATTACK THE ROUND-4 ANDROID DATA FIXES BY NAME (94ab95c, aa072cb, e00a008, ba548e9, and 2eea143's counting). Ideas: the rescue copy -- does min(span, words) plus measured() ever let a REAL loss pass uncounted (deleting a paragraph whose words repeat elsewhere in the note; a note of one repeated word; CJK text with no spaces where measured() is one "word"; a table of short cells; a checklist row deleted -- is the checklist part of the measure at all?); the turn-off keeping an unspent words-only copy's words vs the newest text the same save takes (the desktop's 916926f: when the save that turns the repeat off ALSO takes text, the newest text must win -- the fixer claimed the Repeat sheet saves first; verify on every route that turns a repeat off: the Repeat sheet, a share code's update, an import's Update, Restore previous); the Update question's "earlier version" sentence when several notes differ, some with unspent copies; identity: the first arrival claims a uid -- a code with three notes sharing one uid, a backup whose Trash shares a uid with a live note, a note duplicated on the phone (two live notes with one uid?) then a code arriving for that uid; Organizing.indexOfNote when two live notes wear one uid; e00a008 on every day route (Calendar day, day mode, a reminder tap); the byte ceiling counted for a code made of several notes, and for Text when the title is empty or huge.` },
  { key: 'a5r2-fixes-limits-ui', focus: `RE-ATTACK THE ROUND-4 ANDROID LIMIT AND UI FIXES BY NAME (30a3038, 2fba942, 2eea143's UI). Ideas: the whole-note budget -- a note just under each limit (999 cells, 19,999 lines, 99 pieces) that one edit pushes over: does the editor re-segment mid-typing, move the cursor wrongly, lose the letter typed, or turn the part being typed into read-only under the finger?; typing INTO the field boundary (the line that moves to the next field) quickly, pasting across it, Undo across it, deleting a whole field's worth with a selection; the read-only "rest" -- is the note still saved byte for byte, does the autosave rewrite the read-only part from a cut copy, does Duplicate / Save as template / export / share carry it whole?; the 150,000-letters-with-spaces rule for a title or comments -- edit a note whose title is read-only: can the person still rename it?; the template editor with the same rules (Save of a template whose body has a read-only rest -- whole?); the PDF question's three answers and Back/rotation/process death while the question shows (is the cached PDF cleaned up? does the share happen twice?); TalkBack: the greyed Share cards' reasons read aloud, the question's buttons in order.` },
  { key: 'a5r3-desktop-r5-twins', focus: `THE ANDROID TWINS OF WHAT DESKTOP ROUND 5 FOUND. Read the desktop round-5 findings in ${R5DESK} (one JSON per finding, with mechanism and fix idea), then check whether the phone's app has the same mechanism. Above all: (1) an item typed in a checklist's add field (not yet added) lost when the person leaves the note -- back gesture, opening another note from a notification, Home then the process killed, rotation, a share intent arriving (desktop r5d1 blank-editor pending item); (2) a measure of loss whose share is taken of a length counted in another unit (desktop r5d1 words-lost-vs-padded-length; Android ported measured() in ba548e9 -- check every caller uses it); (3) a fix added to one branch of a rule and missing from its sibling (desktop r5d1 turn-off held-copy branch); (4) an export or backup claiming completeness while a side list (templates, Trash, colours) was not read at start (desktop r5d6 held templates); (5) an error message raised at every repeated failure, replacing an Undo bar (desktop r5d1 toast wipes Undo) -- e.g. a failing write shown at each autosave over a delete's Undo snackbar; (6) a table merge marker "^" under a row with fewer cells (desktop f8818dd: merge_map read past the shorter row and the export raised) -- Android's own merge resolution in Tables/TableView/Exporting/Finding; (7) frame-time handling for animated previews (desktop 1-ms ticks), if the phone animates attachments; (8) a list that cannot scroll to its end (desktop r5d4 16-bit clamp) -- Compose has no such clamp, but a single LazyColumn item of tens of thousands of pixels, or a Column inside a verticalScroll with thousands of children?` },
  { key: 'a5r4-round4-gaps', focus: `WHAT ANDROID ROUND 4 SAID IT DID NOT COVER. Read ${R4AGAPS} (every section and the skeptic's not_checked) and the fixer's confession ${R4AHANDOFF}. Pick the gaps most likely to hide a defect that matters (data loss, crash/ANR, leak, a trap) and probe them by reading and Python replay -- at least five, and say which you skipped and why. Include: the fixes the fixer did NOT walk on a device (rescue copy, identity, restore-during-plan, attach, day restore) -- replay their rules against the Kotlin with hostile inputs; a 16 KB-page device; the autosave frame on very long notes (is any work in it quadratic in the note size?); Find over the read-only rest (does Find say it did not look there, or claim "no matches" wrongly?).` },
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
  return `You are a break-it auditor in the FINAL audit before the Note Organizer Android app is published (Google Play). This is ANDROID ROUND 5: round 4 found 11 Android defects (2 high, 3 medium, 5 low + 1 duplicate) and they were fixed (13 commits); the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the Android app's round-5 break-it findings in the final audit of Note Organizer. Four auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names (file:line), re-run its Python probe if it left one in its scratch folder, check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open item, whether an earlier fix covers it (git -C ${ANDROID} log 815cc8c..audit/a-val1 for round 4), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`android round 5: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:android', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
