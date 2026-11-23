// The final audit: run wf_a1c47f29-6b6, started 2026-10-28 08:17 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round3-android',
  description: 'Final audit wave 1, round 3 (Android): 4 read-only break-it agents re-attack every round-2 Android fix by name, hunt the Android twins of desktop round-3 findings, and cover round 2 gaps; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '4 Android finders: data fixes, UI fixes, desktop round-3 twins, round-2 gaps' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r3a'
const R2AGAPS = '<scratchpad>\\wave1\\r2a\\not_covered.txt'
const R3DESK = '<scratchpad>\\wave1\\r3\\findings'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- YOU MAY NOT run gradle, adb, the emulator, or touch any phone: one emulator exists and the session owns it, and a phone attached is the owner's. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE ANDROID APP: ${ANDROID} (branch audit/a-val1, checked out; do not switch branches; version 0.13.0 plus the audit's fixes). Kotlin + Jetpack Compose, the same notebook format as the desktop (docs/DATA_FORMAT.md). Read its README, CLAUDE.md, docs/STATUS.md and docs/ISSUES_LOG.md (the newest story, "Fixes that were holes of their own", is round 2's).
Work by reading the code closely, and with Python probes in SCRATCH_DIR (build a hostile backup .zip or share code; replay a Kotlin rule in Python to show its output). The JVM tests in app/src/test show how each rule is exercised. Every finding needs EXACT reproduction steps the session can replay on the emulator (what to tap, what file or code to feed) plus the code path (file:line) that proves it.
THE ROUND-2 ANDROID FIXES: 'git -C ${ANDROID} log --reverse --format="%h %s%n%b" b8cacf1..audit/a-val1' lists all 22 with their reasoning and mutants (AS58-AS113): 0a66b9b Trash window only between 31 and 365 days and only when the backup holds Trash; 112d848 Google backup Off survives a damaged settings.json (the start writes phone_google_backup false) and a restore (Off, the agent hands Android only phone_google_backup_off.json, which replaces the copy made while On; restored, the start writes Off and deletes the file); 32e8393 an older backup kept when its place refuses to open, a backup this phone cannot read back (past heap/16) still saved and said; 81c3575 a large table weighed as drawn (rows x widest), shown so in the template editor, left out of Find; e1772ba + 7bec9af a repeat ended by a share code COPIES the days into _prev and the note keeps them (Notebook.daysToRescue, Notebook.carryDays in updateNote, applyUpdate, restorePrevious, setRepeat); 8ecdf04 moved days in linear time (Recurrence.Schedule), the banner remembered per revision; 8df2456 paste padding checked before it is built (MAX_TABLE_PADDING 100,000, ragged past it), align() linear; 028b0b2 the template editor carries styles and list lines through every edit (Notebook.throughEdit); 6505532 Calendar: soonest works out each note's place once; 2b62c29 backup side lists capped (real days only, 20,000 colours, 20,000 markers of at most 16 characters, 1,000 templates), a new one past a cap refused with a message; 22f9ed2 NaN/Infinity nulled by Files.parseOutside, templates normalized on import, Importing.apply turns a crash into a sentence; 74145f4 attachment names over 250 bytes unpacked under a shortened name, notes and Trash told; 3e2cf02 backup attachments MOVED into place instead of copied, a share code decoded/planned/checked off the main thread with "Reading the code..."; af7c6c9 qa; 130e22b a line, title, comments or checklist row holding a run of more than 10,000 characters with no space is shown READ-ONLY by LongText (a notice, the length, the first 300 characters), each such body line its own segment (Segment.long), list cards/calendar rows/template lists show the first 300 characters of a title, the code dialog shows a code over 5,000 characters as its start and length with Copy; 22ecced attached files go only to the note they were picked for (uid checked too); 0195b58 the Undo bar uses SnackbarDuration.Long counted from when it shows, a checklist row's Undo saves words typed into another row first; 3bacf87 Material primary is a readable shade of the accent (Themes.primaryRole), the snackbar action Themes.barAction, 4.5:1 in all 8 themes; 4c6a0ca an attachment label ends in the stored file's type and loses hidden/bidi characters, the MIME type handed to another app comes from the stored file, a share code sent as styled text arrives (getCharSequenceExtra); 2b04a5a glyph buttons have screen-reader names, a move handle with nowhere to go says so.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; the app is offline (no INTERNET permission), no accounts, no Terms & Conditions; Google's backup stays on by default with an in-app switch (the owner's choice); Off sending Android a marker file is under the owner's review (the privacy wording) -- report only a defect in how it works; the Undo bar lasting 10 s and long unbroken text being read-only are under the owner's review -- report only a defect in how they work.
KNOWN OPEN, do not re-report unless worse: two quick checklist Undos restore rows out of order; Importing.apply's JSON work and notes write still on the main thread; an already-bloated settings.json filtered on read but rewritten only at the next paint; the template picker and Templates page not lazy (capped at 1,000).
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash, freeze or ANR, hostile input included; nothing from outside executes or escapes the app's storage, and no other app can read the notes; an ordinary person (TalkBack users included) is never trapped or misled.
Severity: critical = notes lost/corrupted, or outside content executes / an internal file reaches another app / data leaves the phone without the person's action. high = crash/ANR, freeze over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a mid-range phone would feel at realistic sizes; an accessibility trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran a probe and saw it (a Python replay of the Kotlin rule counts if you say so); otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 25 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'a3r1-fixes-data', focus: `RE-ATTACK THE ROUND-2 ANDROID DATA FIXES BY NAME (0a66b9b, 112d848, 32e8393, e1772ba, 8ecdf04, 2b62c29, 22f9ed2, 74145f4, 3e2cf02, 22ecced). Ideas: the Off marker -- Off then On again (is the marker gone from the next backup, does the full copy resume), a restore of a marker-only backup onto a phone that already holds notes (device transfer, a reinstall over data), the marker surviving into a backup .zip made in the app, settings.json damaged AND the marker present; the days copied AND kept -- double copies, days resurfacing wrongly after a turn-on, Restore previous twice, Duplicate, export, the share code; carryDays carrying a stale day text over a newer one; the side-list caps dropping something a PERSON made (an old date spelling, a marker of an emoji with joiners past 16 characters, a day before 1900 or after 2100, an existing notebook with more than 1,000 templates from the desktop); NaN nulled in a field where null then crashes or changes meaning (recurrence count, order, interval); two long non-Latin names shortened to the SAME name (collision: does one file overwrite the other, do the notes point to the right file, Trash entries too); attachments MOVED into place: an import that fails halfway -- are moved files orphaned, referenced by nothing, or lost from the extracted backup that a retry needs; a move across storage volumes; the uid check on attach with a note duplicated or restored meanwhile.` },
  { key: 'a3r2-fixes-ui', focus: `RE-ATTACK THE ROUND-2 ANDROID UI FIXES BY NAME (81c3575, 8df2456, 028b0b2, 6505532, 130e22b, 0195b58, 3bacf87, 4c6a0ca, 2b04a5a). Ideas: LongText read-only -- can a person DELETE or edit around a read-only line (select across it, Backspace at its start, cut, Undo), does typing a run past 10,000 by hand or a paste make the line read-only mid-edit and lose the caret or typed letters, does Find reach it, is the note saved byte for byte, what about a 10,001-character run inside a table cell or a checklist row, an astral emoji run, a title?; the code dialog's start+length with Copy (does Copy copy the WHOLE code, does Import still read a long code pasted back, codes of exactly 5,000/5,001); the Undo bar counted from when it shows (two bars in a row, the app backgrounded while it shows, rotation); a checklist row's Undo saving words typed into another row (the typed row deleted meanwhile); Themes.primaryRole in all 8 themes for every Material component it now colours (switch thumbs, sliders, selected chips, text selection handles, the date picker) -- any now unreadable or invisible?; the attachment label vs the stored file's type for an intent (an .apk or .html stored under a photo label: what MIME goes out, can opening it offer to INSTALL or run script?); getCharSequenceExtra with a huge styled text (ANR?); the template editor's throughEdit with tables and list lines; Calendar: soonest with 1,000 series.` },
  { key: 'a3r3-desktop-r3-twins', focus: `THE ANDROID TWINS OF WHAT DESKTOP ROUND 3 FOUND. Read the desktop round-3 findings in ${R3DESK} (one JSON per finding, with mechanism and fix idea), then check whether the phone's app has the same mechanism. Above all: (1) the ONE rescue copy slot: anything else that writes _prev (a big rewrite, an update, Restore previous, a turn-off) after the days were copied -- can the next copy erase the only copy of something?; (2) a table's padding counted as text lost, so widening one cell replaces the rescue copy (the phone pads tables too: Tables.kt); (3) a notes file that cannot be read at the start -- treated as empty and then overwritten by the first save? read again after a moment?; (4) an export or backup made after an unreadable start packing an empty notebook as complete; (5) a turn-off after a big delete replacing the delete's copy with the note as it stands; (6) an update replacing an earlier rescue copy without saying so; (7) a checklist item of 60,000 characters WITH spaces (LongText only covers unbroken runs) drawn in a checklist row or the template editor -- a frame of tens of thousands of pixels, jank, a crash?; (8) an attachment row whose long name pushes its delete/open control out of reach; (9) a share code or backup whose attachment name holds ":" or a stream-like spelling; (10) an animated GIF or WebP preview with a huge canvas or thousands of frames (does the phone preview animations at all? Coil/ImageDecoder budgets?).` },
  { key: 'a3r4-round2-gaps', focus: `WHAT ANDROID ROUND 2 SAID IT DID NOT COVER, and what round 2's fix agent confessed. Read ${R2AGAPS}. The fix agent's own list: TalkBack never turned on; the dark-theme photo never taken; the Material-role wiring untested by JVM; Google's real backup transport unverified; PDF/HTML export of a huge table or a long line not checked; title displays OUTSIDE the list card, calendar rows and template lists (History, Trash dialogs, the share sheet, notifications, the reminder) not swept for a 150,000-character title; single-line fields with huge text not measured; MAX_UNBROKEN (10,000) and the 5,000-character code limit set on the emulator, not a slow phone; finiteOnly's extra walk on every parse not timed. Pick the gaps most likely to hide a defect that matters (data loss, crash/ANR, leak, a trap) and probe them by reading and Python replay -- at least five, and say which you skipped and why.` },
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
  return `You are a break-it auditor in the FINAL audit before the Note Organizer Android app is published (Google Play). This is ANDROID ROUND 3: round 2 found 27 Android defects and they were fixed (22 commits); the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the Android app's round-3 break-it findings in the final audit of Note Organizer. Four auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names (file:line), re-run its Python probe if it left one in its scratch folder, check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open item, whether an earlier fix covers it (git -C ${ANDROID} log b8cacf1..audit/a-val1 for round 2), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`android round 3: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:android', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
