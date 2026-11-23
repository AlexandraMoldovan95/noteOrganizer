// The final audit: run wf_4c91e8b6-0a8, started 2026-10-29 05:48 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round6-android',
  description: 'Final audit wave 1, round 6 (Android): 4 read-only break-it agents re-attack every round-5 Android fix by name, the seams between them and their parity with the desktop, and round 5 gaps; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '4 Android finders: data fixes, limit/UI fixes, seams and desktop parity, round-5 gaps' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r6a'
const R5AGAPS = '<scratchpad>\\wave1\\r5a\\not_covered.txt'
const R5ASUMMARY = '<scratchpad>\\wave1\\r5a\\summary.txt'
const R5AFINDINGS = '<scratchpad>\\wave1\\r5a\\findings'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- YOU MAY NOT run gradle, adb, the emulator, docker, or touch any phone: one emulator exists and the session owns it, and a phone attached is the owner's. The machine is busy with the desktop's full suites and the desktop audit's containers -- keep your probes light. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE ANDROID APP: ${ANDROID} (branch audit/a-val1 at 24aeb6f, checked out; do not switch branches; version 0.13.0 plus the audit's fixes). Kotlin + Jetpack Compose, the same notebook format as the desktop (docs/DATA_FORMAT.md). Read its README, CLAUDE.md, docs/STATUS.md and docs/ISSUES_LOG.md (its newest code story is round five's, "A ceiling for hostile notes that ordinary ones reached", plus "What the audit's fifth round left").
Work by reading the code closely, and with Python probes in SCRATCH_DIR (build a hostile backup .zip or share code; replay a Kotlin rule in Python to show its output; for parity, run the DESKTOP's pure core -- noteorganizer/core, which never imports tkinter -- from a copy inside SCRATCH_DIR with APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import, asserted first). The JVM tests in app/src/test show how each rule is exercised. Every finding needs EXACT reproduction steps the session can replay on the emulator (what to tap, what file or code to feed) plus the code path (file:line) that proves it.
THE ROUND-5 ANDROID FIXES: 'git -C ${ANDROID} log --reverse --format="%h %s%n%b" ea4b9f9..35644c7' lists them with their reasoning and mutants (AS172-AS204). Round 5's findings, one line each: ${R5ASUMMARY}; one JSON per finding in ${R5AFINDINGS}. In short: 583099d underline and strike merged in one sweep; 9f2a82f a letter typed in a long note weighed for a rescue copy by the span it changed alone; 09c9ead the backup Update question says a copy is replaced only for a note whose words the update changes; 8af33c8 a merge marker "^" under a row too short to have its column is content, as on the desktop; d15de96 a checklist row's words the phone cannot write said once, the next row's letters kept; e79e11e Share weighs a note's code and words away from the screen's thread and refuses an oversized one before deflating; 1caebef the template editor saves the words waiting in its "A new item" box and asks before closing over them; f1a38aa a repeat turned off after a big delete keeps the deleted words when the delete's copy carried days; a030d21 Undo keeps what a phone can hold of a long note (a byte budget), never fewer than its last step; b800f3c the cursor goes where its line went (under a table typed by hand, past a read-only line, or the keyboard is let go); 83e59ff an ordinary note of many small tables drawn to its end (pieces 100 -> 500), and what a note shows read-only is found by Find and read; f5198aa a checklist draws what one list may, each row up to the desktop's 2,000 letters; 24b62d3 a template's comments too long to edit shown under their own label; f53d1da a list's markers changed lose no words; 9cc69da a series turned back on from another start drops its old deleted days; b13ab13 a long checklist draws its first 200 rows and its last five, the rest on asking; 07c0d4c a note draws 40,000 lines in its fields (was 20,000). 9d15cf8 (the walk's log check) is test-only.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; offline (no INTERNET permission), no accounts, no Terms & Conditions; Google's backup on by default with an in-app switch; Off sending Android a marker file; the Undo bar lasting 10 s / 8 s; long unbroken text read-only; the share ceiling (100,000 Latin, weighed in bytes) said before the share; the PDF asking first ([Web page][PDF, first 40 pages][Cancel]) and writing nothing into the file; the long code dialog; on a series restarted from another date or rule, only the old series' deleted days are dropped and days with their own text stay (the owner's decision, the desktop's 3c3b644; no new data field).
KNOWN OPEN, do not re-report unless worse: "What the audit's fifth round left" in docs/ISSUES_LOG.md (a template being written lost if Android ends the app behind Home -- the owner's call, pending; a three-cell row typed by hand becoming a grid at its second pipe; past 40,000 drawn lines the end is read-only; the first 200 checklist rows redrawn per letter at 0.2 s); two quick checklist Undos restore rows out of order; Importing.apply's JSON work on the main thread; an already-bloated settings.json filtered on read but rewritten only at the next paint; the template picker and Templates page not lazy (capped at 1,000); a fitted attachment name not round-tripping through the desktop's import; Backspace at a field boundary does not join lines; Find over the read-only rest only where 83e59ff says.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash, freeze or ANR, hostile input included; nothing from outside executes or escapes the app's storage, and no other app can read the notes; an ordinary person (TalkBack users included) is never trapped or misled; the two apps agree on every note that travels between them.
Severity: critical = notes lost/corrupted, or outside content executes / an internal file reaches another app / data leaves the phone without the person's action. high = crash/ANR, freeze over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes; a note that travels and comes back changed. medium = misleading or wrong but recoverable; a slowdown a mid-range phone would feel at realistic sizes; an accessibility trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran a probe and saw it (a Python replay of the Kotlin rule counts if you say so); otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 25 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'a6r1-fixes-data', focus: `RE-ATTACK THE ROUND-5 ANDROID DATA FIXES BY NAME (9f2a82f, 09c9ead, f1a38aa, a030d21, f53d1da, 9cc69da, 8af33c8, d15de96, 1caebef, e79e11e). Ideas: 9f2a82f weighs a typed letter by the span it changed -- can a REAL big loss now slip through as a "small span" (select-all and type one letter; a paste over a long selection; Undo of a big paste; a cut; a drag of text; a delete done in two quick edits inside one autosave window)? a030d21's Undo byte budget -- a note just over and under it; Undo after the budget dropped the oldest steps (does the person learn the history is shorter? can Undo restore a state that never existed, or lose the last step?); Redo after a budget trim. f53d1da list markers -- a deleted paragraph whose words are markers or numbers ("1." "2." "-" "*"), a numbered list of bare numbers ("1. 2024"), a sentence starting "2.5 kg", bullets inside a table cell; is the rule IDENTICAL to the desktop's strip_list_markers (replay both on the same inputs)? 9cc69da -- turned off, kept days, restarted from another date AND another rule AND back to the old date; a day with own text that the new series skips (hidden? shown twice? lost on the next save?). f1a38aa -- every route that turns a repeat off (the Repeat sheet, a share code's update, an import's Update, Restore previous). 1caebef -- the template editor's pending item: Save, ✕/Back, rotation, process death, an item of spaces, an item over 2,000, the template already at 1,000 items, Save as template FROM A NOTE with words in the note's own "A new item" field (the desktop's 7b3bb72 takes them into the template -- does the phone?). d15de96 -- the failure said once: is a later, different failure still said? 09c9ead -- several notes in one backup, some changing words, some only files. e79e11e -- Share refused before deflating: a code just at the ceiling, a note whose words fit but whose code does not, and the reverse.` },
  { key: 'a6r2-fixes-limits-ui', focus: `RE-ATTACK THE ROUND-5 ANDROID LIMIT AND UI FIXES BY NAME (583099d, b800f3c, 83e59ff, f5198aa, 24b62d3, b13ab13, 07c0d4c). Ideas: b13ab13 the checklist draws its first 200 rows and its last five, the rest on asking -- can a row in the hidden middle be lost, reordered or duplicated by a move (drag handle / the move menu), a delete, Undo, a paste of many lines into a row, a share or export while the middle is hidden? Is the "rest on asking" control reachable with TalkBack and Switch Access, and does it say how many rows it hides? Does Find reach a word in a hidden row? f5198aa rows up to 2,000 letters: a paste over 2,000 into a row (shortened like the title, by the owner's decision on the desktop -- does the phone agree?), a row of 2,000 astral emoji, combining marks at the cut. 83e59ff pieces 100 -> 500: a note just at 500 pieces that one edit pushes over; Find in the read-only rest: does "Read on" land on the found line, and can the person get back? 07c0d4c 40,000 lines: a note at 39,999 lines that a paste pushes past; the time to open such a note (same-session comparison against 20,000 if you can replay it). b800f3c the cursor: a line moved into the read-only rest while the person types fast; a hardware keyboard's Enter at the end of what is drawn; Undo right after the keyboard was let go. 583099d one sweep for underline and strike: overlapping, nested, zero-length and reversed spans; a span past the text's end from a hostile code. 24b62d3 comments too long shown under their own label: are they still saved whole when the template is saved?` },
  { key: 'a6r3-seams-and-parity', focus: `THE SEAMS BETWEEN THE ROUND-5 ANDROID FIXES, AND THEIR PARITY WITH THE DESKTOP. Seams: the Undo byte budget (a030d21) x the rescue copy's span weighing (9f2a82f) x a 40,000-line note (07c0d4c) -- can Undo bring back text the rescue copy no longer protects, or a save drop words both believe the other keeps?; the checklist's hidden middle (b13ab13) x the template editor's pending item (1caebef) x Save as template; list markers (f53d1da) x a table x the rescue copy x Undo; the read-only rest x Find x Share x the PDF question; a share refused off the main thread (e79e11e) x the 100,000 ceiling said before x the multi-select share. Parity (a note made on one app and opened on the other must come back the same): replay the DESKTOP's own core (noteorganizer/core, isolated as in the rules) and the phone's Kotlin rule on the same inputs for: the list-marker rule (desktop 5a21fbb strip_list_markers vs f53d1da); the "^" merge marker under a short row (desktop f8818dd vs 8af33c8) in the grid, the share code, export to text/markdown/HTML; a series restarted from another date (desktop 3c3b644 vs 9cc69da: exactly which exceptions and which days with own text survive, on each side); the checklist item cap of 2,000 and the 1,000-item list cap on paste and on import from the other app (is a desktop note of 1,000 rows of 2,000 letters fully readable and saved byte for byte on the phone?); a template with words left in its new-item box (desktop 7b3bb72) and how the phone stores the same template. A disagreement that changes a note that travels is high.` },
  { key: 'a6r4-round5-gaps', focus: `WHAT ANDROID ROUND 5 SAID IT DID NOT COVER. Read ${R5AGAPS} (every section and the skeptic's not_checked) and "What the audit's fifth round left" in docs/ISSUES_LOG.md. Pick the gaps most likely to hide a defect that matters (data loss, crash/ANR, leak, a trap) and probe them by reading and Python replay -- at least five, and say which you skipped and why. Include: any round-5 fix that was not walked on the emulator (the commit bodies and the walk's limits_round5 in tools/emulator/walk.py say which were); the process ended behind Home while each round-5 path is mid-way (the pending template item, a share being weighed off the main thread, a long checklist with its middle hidden, Undo trimmed); a 16 KB-page device; work in the autosave or the drawing that grows with the square of the note size; TalkBack over the new controls (the checklist's "rest on asking", the read-only rest's "Read on", the template's comments label).` },
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
  return `You are a break-it auditor in the FINAL audit before the Note Organizer Android app is published (Google Play). This is ANDROID ROUND 6: round 5 found 14 distinct Android defects (2 high, 4 medium, 8 low) and they were fixed (17 commits); the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the Android app's round-6 break-it findings in the final audit of Note Organizer. Four auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names (file:line), re-run its Python probe if it left one in its scratch folder, check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open item, whether an earlier fix covers it (git -C ${ANDROID} log ea4b9f9..35644c7 for round 5), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`android round 6: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:android', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
