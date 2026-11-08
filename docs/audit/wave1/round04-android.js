// The final audit: run wf_797b113b-493, started 2026-10-28 12:00 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round4-android',
  description: 'Final audit wave 1, round 4 (Android): 4 read-only break-it agents re-attack every round-3 Android fix by name, hunt the Android twins of desktop round-4 findings, and cover round 3 gaps; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '4 Android finders: data fixes, limit/UI fixes, desktop round-4 twins, round-3 gaps' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r4a'
const R3AGAPS = '<scratchpad>\\wave1\\r3a\\not_covered.txt'
const R3ASUMMARY = '<scratchpad>\\wave1\\r3a\\summary.txt'
const R4DESK = '<scratchpad>\\wave1\\r4\\findings'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- YOU MAY NOT run gradle, adb, the emulator, docker, or touch any phone: one emulator exists and the session owns it (a full walk is running on it now), and a phone attached is the owner's. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE ANDROID APP: ${ANDROID} (branch audit/a-val1, checked out; do not switch branches; version 0.13.0 plus the audit's fixes). Kotlin + Jetpack Compose, the same notebook format as the desktop (docs/DATA_FORMAT.md). Read its README, CLAUDE.md, docs/STATUS.md and docs/ISSUES_LOG.md (the newest story, "Guards that asked another question than the cost", is round 3's).
Work by reading the code closely, and with Python probes in SCRATCH_DIR (build a hostile backup .zip or share code; replay a Kotlin rule in Python to show its output). The JVM tests in app/src/test show how each rule is exercised. Every finding needs EXACT reproduction steps the session can replay on the emulator (what to tap, what file or code to feed) plus the code path (file:line) that proves it.
THE ROUND-3 ANDROID FIXES: 'git -C ${ANDROID} log --reverse --format="%h %s%n%b" d057e7e..audit/a-val1' lists all 18 with their reasoning and mutants (AS114-AS146). Round 3's findings, one line each: ${R3ASUMMARY}. In short: 191e767 the Off mark counts as the answer while settings.json holds none (Settings.forFullBackup, one rule for the backup agent and Settings -> Backup); 6d0596f a backup import finds each note by uid in the live list (apply and the look-alike question; a note gone since the plan comes in as new; the share-code route the same); 52c66cb one definition of a run (ends only where the layout surely breaks; no-break spaces join), each line of a body/title/comments weighed, heavy lines past the budget (twice one 10,000-letter run) read-only, CJK ideographs no longer one run; 6c32955 table cells weighed too, such a table read-only and never drawn as a grid; 531534b every bar, question and spoken label quotes at most 80 characters (a file name keeps its type), any bar or question capped at 1,000; 6185137 template rows show the read-only notice when too long, otherwise a 300-character start; cc32c99 export loops linear, the page built off the main thread; 08fb60a Share -> Text greyed past the ceiling and says why, the mail subject cut, a hand-off error said; 04332e3 the PDF breaks any line at the page edge, past 40 pages or something wider than the page the bar says so and a grey line on the PDF's page says so; 4744ab1 export file names as the desktop's export_file_stem; e16baf6 a note that no longer repeats is itself on its day (no kept words, no ✎, its first day not lost) and the restore copy keeps the repeat's date; 933a20b share ceiling 100,000 characters for codes and words (measured: 160,000 reached the share sheet, 180,000 did not -- TransactionTooLarge inside system_server, never reaching the app); 4e7451a notice wording "a run no line can break"; 403a4e4 picked files attached by uid first (Trash then Undo during the copy still attaches); dca1b9b escapes in sources.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; the app is offline (no INTERNET permission), no accounts, no Terms & Conditions; Google's backup on by default with an in-app switch (the owner's choice); Off sending Android a marker file, the Undo bar lasting 10 s, long unbroken text being read-only, the 100,000 share ceiling, and the PDF's grey foot line are under the owner's review -- report only a defect in how they WORK.
KNOWN OPEN, do not re-report unless worse: two quick checklist Undos restore rows out of order; Importing.apply's JSON work and notes write still on the main thread; an already-bloated settings.json filtered on read but rewritten only at the next paint; the template picker and Templates page not lazy (capped at 1,000); the cursor jumping after a paste makes a line read-only; a fitted attachment name not round-tripping through the desktop's import.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash, freeze or ANR, hostile input included; nothing from outside executes or escapes the app's storage, and no other app can read the notes; an ordinary person (TalkBack users included) is never trapped or misled.
Severity: critical = notes lost/corrupted, or outside content executes / an internal file reaches another app / data leaves the phone without the person's action. high = crash/ANR, freeze over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a mid-range phone would feel at realistic sizes; an accessibility trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran a probe and saw it (a Python replay of the Kotlin rule counts if you say so); otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 25 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'a4r1-fixes-data', focus: `RE-ATTACK THE ROUND-3 ANDROID DATA FIXES BY NAME (191e767, 6d0596f, e16baf6, 403a4e4, 4744ab1). Ideas: Settings.forFullBackup -- settings.json present but missing ONLY the backup key, holding it as a string or null, the marker AND an explicit On, Off then On then a restore, a device-to-device transfer where the marker exists but settings say On; the import by uid -- two notes sharing a uid (an old notebook, a desktop backup with duplicate ids), a note whose uid changed by Duplicate meanwhile, a note edited (not trashed) during "Importing...": does its new text survive or is it overwritten by the backup's, a note restored from Trash during the import, the look-alike question answered after the list changed; e16baf6 -- every reader of kept days agreeing that a one-off's days are inert (search, Find, the card, History, export, the share code, Duplicate, reminders, the calendar and its ✎), a turn-on bringing them back exactly, a share update arriving for a turned-off note, Restore previous twice with the restored date; 403a4e4 -- attach by uid when the note was Duplicated, deleted for good, or replaced by an import during the copy; export_file_stem parity with the desktop for titles of only punctuation, reserved Windows names (CON, NUL, COM1), trailing dots/spaces, emoji, RTL, 200+ characters, two notes giving the same stem (does one export overwrite the other?).` },
  { key: 'a4r2-fixes-limits-ui', focus: `RE-ATTACK THE ROUND-3 ANDROID LIMIT AND UI FIXES BY NAME (52c66cb, 6c32955, 531534b, 6185137, cc32c99, 08fb60a, 04332e3, 933a20b, 4e7451a). Ideas: the new run definition vs every character class that the layout may not break at (Thai/Lao/Khmer with no spaces, Japanese kana, Korean, emoji with ZWJ sequences, combining marks, U+2060 word joiner, U+FEFF, soft hyphen, figure space U+2007, narrow no-break space U+202F, tabs) -- can a heavy line still freeze the screen while judged light?; a line becoming heavy mid-typing (the caret, the letters typed, Undo); a body where every line is just under the budget (many lines, total size); the cell weighing vs a table converted from pasted Excel; the 80-character quote cutting inside a surrogate pair, a ZWJ emoji or an RTL run (does the bar show garbage or reorder the question's text?), TalkBack reading the cut label; the 1,000 cap on questions with a file name whose type is lost; cc32c99 -- the page built off the main thread: is the note read on the main thread first, can it change mid-build, what if the person leaves the screen or rotates mid-export?; the 100,000 ceiling counted in what (chars, UTF-16 units, bytes?) vs what the Binder carries (a 99,000-character text of CJK or emoji is ~3x the bytes: does it still pass system_server's limit?); the PDF line breaking with a 100,000-character unbroken run, a table wider than the page, RTL text, a page-40 boundary inside a table; the grey foot line's text in all 8 themes / dark PDF?` },
  { key: 'a4r3-desktop-r4-twins', focus: `THE ANDROID TWINS OF WHAT DESKTOP ROUND 4 FOUND. Read the desktop round-4 findings in ${R4DESK} (one JSON per finding, with mechanism and fix idea), then check whether the phone's app has the same mechanism. Above all: (1) the rescue copy (_prev) replaced by edits that lose nothing -- a table column added or removed, a numbered list renumbered, a cell widened (Android pads tables too): is loss measured by a span of changed text, and does an ordinary re-layout replace the only copy?; (2) a turn-off whose own save also clears text keeping the OLDER copy instead of the newest text; (3) typing into a blank editor (after a delete, or with no note open) lost by leaving -- back gesture, home, rotation, a share intent arriving, the process killed in the background; (4) settings.json unreadable for a moment (another process? Android storage is private -- but a partial write, a crash mid-write, a restore) read as damaged and rewritten with defaults, and the Trash cleanup run on an unknown window; (5) an export or backup made on a run that could not read the notes file packing an empty notebook as complete; (6) an attachment preview that fails half-way (animated PNG/WebP, a decoder error) leaving the file open or the app in a bad state; (7) template names of thousands of letters or many lines (a backup brings them) drawn whole in the picker, Settings and questions; (8) a row whose long name pushes its controls out of reach (template, category, attachment rows); (9) a table whose cells hold line breaks drawn past what a screen can draw (Compose has no 32,767-px X limit, but a LazyColumn item tens of thousands of pixels tall?).` },
  { key: 'a4r4-round3-gaps', focus: `WHAT ANDROID ROUND 3 SAID IT DID NOT COVER, and what round 3's fix agent confessed. Read ${R3AGAPS}. The fix agent's own list: the import race (a note trashed during "Importing...") verified only in JVM tests, never on a device; the 150,000-character attachment label; the turned-off repeat in the calendar row; the PDF's wide-table and long-link cases; Export of a 50,000-cell table; a share code above 100,000; the run/budget rule reasoned from Unicode's rules and walked only with Latin, no-break-space and Chinese text; no TalkBack listening; Google's real backup transport never exercised. Pick the gaps most likely to hide a defect that matters (data loss, crash/ANR, leak, a trap) and probe them by reading and Python replay -- at least five, and say which you skipped and why.` },
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
  return `You are a break-it auditor in the FINAL audit before the Note Organizer Android app is published (Google Play). This is ANDROID ROUND 4: round 3 found 12 Android defects (8 high, 1 medium, 3 low) and they were fixed (18 commits); the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the Android app's round-4 break-it findings in the final audit of Note Organizer. Four auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names (file:line), re-run its Python probe if it left one in its scratch folder, check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open item, whether an earlier fix covers it (git -C ${ANDROID} log d057e7e..audit/a-val1 for round 3), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`android round 4: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:android', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
