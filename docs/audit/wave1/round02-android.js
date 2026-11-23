// The final audit: run wf_3f8dc29b-2e5, started 2026-10-28 03:45 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round2-android',
  description: 'Final audit wave 1, round 2 (Android): 5 read-only break-it agents re-attack every round-1 Android fix by name, hunt the Android twins of desktop round-2 findings, and cover round 1 gaps; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '5 Android finders: data fixes, UI/lifecycle fixes, desktop twins, hostile input, round-1 gaps' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r2a'
const R1GAPS = '<scratchpad>\\wave1\\r1\\not_covered.txt'
const R2DESK = '<scratchpad>\\wave1\\r2\\findings'
const R2D2 = '<scratchpad>\\wave1\\r2\\r2d2_interpreted.md'
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
THE ANDROID APP: ${ANDROID} (branch audit/a-val1, checked out; do not switch branches; version 0.13.0 plus the audit's fixes). Kotlin + Jetpack Compose, the same notebook format as the desktop (docs/DATA_FORMAT.md). Read its README, CLAUDE.md, docs/STATUS.md and docs/ISSUES_LOG.md (newest stories are the audit's).
Work by reading the code closely, and with Python probes in SCRATCH_DIR (build a hostile backup .zip or share code; replay a Kotlin rule in Python to show its output). The JVM tests in app/src/test show how each rule is exercised. Every finding needs EXACT reproduction steps the session can replay on the emulator (what to tap, what file or code to feed) plus the code path (file:line) that proves it.
THE AUDIT'S ANDROID FIXES: 'git -C ${ANDROID} log --reverse --format="%h %s%n%b" audit/a-val0..audit/a-val1' lists all 34 with their reasoning and mutants (round 1 AS02-AS34 in 0ebec6e..2da00a7; round 1b AS35-AS57 in f0b7a79..2bb1c80, including the Google backup switch 3929bee, move without drag 817db98, states said f8efe7c, checklist Undo 2e24b51, contrast 72de2bf, calendar large letters 4128d9c, unreadable file in the next backup 29b5838, look-alikes off the main thread f2bcf98, reminder on time-zone change a006e5b, today at midnight 8f50774, long template comments d182784, answers after restart d6bd227, no shared-folder adoption d0a1b08, own files read through parseOwn e2043c6).
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; the app is offline (no INTERNET permission), no accounts, no Terms & Conditions; Google's backup stays on by default with an in-app switch (the owner's choice); a 120,000-character share code freezing the code dialog is ALREADY KNOWN (do not report it; do say if you find its siblings).
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash, freeze or ANR, hostile input included; nothing from outside executes or escapes the app's storage, and no other app can read the notes; an ordinary person (TalkBack users included) is never trapped or misled.
Severity: critical = notes lost/corrupted, or outside content executes / an internal file reaches another app / data leaves the phone without the person's action. high = crash/ANR, freeze over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a mid-range phone would feel at realistic sizes; an accessibility trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran a probe and saw it (a Python replay of the Kotlin rule counts if you say so); otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 25 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'a2r1-fixes-data', focus: `RE-ATTACK THE ANDROID DATA FIXES BY NAME (round 1 and 1b): the failed save that leaves the note as it was (0ebec6e) and the editor not closed under its words (d52adbf); checklist words kept on stop (1cb754e, f0b7a79); the backup's Trash window (4f7e8de -- does it also adopt a SHORTER window and purge this notebook's own Trash early? the desktop had exactly that regression); deep JSON (ae4383a); unreadable backups (e7a152f); too-large backups (6238098); restores in linear time (30997fa); the rescue copy's shape (89c7a8f); a backup saved over an older one (f42d563); the unreadable notebook file travelling in the next backup (29b5838); parseOwn strict UTF-8 on the app's own files (e2043c6 -- can a valid notebook written by the desktop now be refused? lone surrogates, a BOM, CRLF); no shared-folder adoption (d0a1b08); the Google backup switch (3929bee: what does a settings file that cannot be read do to it; what happens to a restore that brings phone_google_backup back; does the agent exclude anything it should not). For each: a variation the fix's own test did not try, a neighbour it broke, an unswept sibling.` },
  { key: 'a2r2-fixes-ui', focus: `RE-ATTACK THE ANDROID UI AND LIFECYCLE FIXES BY NAME: a table too large drawn read-only (1099615, f3a6aff: can a person edit around it, does Find or the calculator reach into it, does a save keep it byte for byte); symbol labels and states said (2da00a7, f8efe7c); move without drag (817db98: pinned notes, category groups, the first/last item, a filtered list, two quick moves); the checklist row's Undo (2e24b51: Undo after the note was left, after another row was removed, after the list shrank); contrast (72de2bf) in all themes; the calendar at the largest letters (4128d9c) on a small phone and in landscape; the reminder on a time-zone change (a006e5b) and today at midnight (8f50774: DST, the app in the background over midnight, a day bar dismissed); long template comments (d182784); Export as file and Attach files finishing after Android ends the app (d6bd227: two pickers in a row, a picked file that is gone, the note deleted meanwhile, a huge file and low storage).` },
  { key: 'a2r3-desktop-twins', focus: `THE ANDROID TWINS OF WHAT DESKTOP ROUND 2 FOUND. Read the desktop round-2 findings in ${R2DESK} (one JSON per finding, with mechanism and fix idea) and ${R2D2}, then check whether the phone's app has the same mechanism. Above all: (1) a share-code Update whose copy no longer repeats -- does the series' own day text (overrides/exceptions/moved) survive the next edit and come back with Restore previous? (desktop: critical); (2) the backup export after a failed save -- does it pack the file on disk or what the app holds?; (3) a backup's Trash window adopted when SHORTER; (4) Trash entries read raw (wrong types in a hand-made trash.json breaking the Trash page or an import); (5) an attachment's shown name vs the stored file -- which one decides the icon, the preview and what Intent/MIME type is handed to another app? Can a crafted backup label an .apk as a photo, and does opening it offer to INSTALL it (the phone's 'outside content executes')? What does the app do with an .apk, .html, .svg or a file with no extension? (6) the template editor keeping styles at old offsets after an edit; (7) a series with thousands of moved days, settings with a million day colours, twenty thousand templates arriving in a backup -- freezes or ANRs; (8) paste of huge plain text or HTML tables padded past a cap.` },
  { key: 'a2r4-hostile', focus: `HOSTILE AND HUGE INPUT ROUND 1 LEFT UNTRIED ON THE PHONE: share intents with many items, mixed MIME types, a text/plain of megabytes, a content:// URI that never ends or throws mid-read; a backup .zip with duplicate entry names, a lying size, directory entries, names with control characters or right-to-left overrides, a notes_data.json of deeply nested but legal JSON just under the limit, numbers like 1e999 or 9e18 in recurrence fields; a note body with a million characters on one line, astral emoji and lone surrogates in Find; the PDF print WebView fed hostile HTML from a note (scripts, <img src=file:///data/...>, <iframe>, CSS url(content://...)) -- can a note's text make the print path read an internal file or reach the network; the clipboard paste of HTML with external images. Goal: a crash/ANR, a freeze, an out-of-memory, an internal file leaking, or a save that comes back different.` },
  { key: 'a2r5-round1-gaps', focus: `WHAT ANDROID ROUND 1 SAID IT DID NOT COVER. Read ${R1GAPS}: the Android auditors are the sections "[1]/reports[0]" to "[1]/reports[5]" (data loss, hostile input, security/privacy, lifecycle/state, accessibility, desktop interop, in that order). Pick the gaps most likely to hide a defect that matters (data loss, crash, leak, a trap) and probe them -- at least one from each of the six sections, and say which you skipped and why. Interop in particular: a note written on the desktop with every heavy feature (tables, recurrence with own days and moves, checklist, comments, formatting spans and paragraphs, attachments, colours, categories, unknown fields) going through a share code and a backup to the phone and back -- what is dropped or changed.` },
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
  return `You are a break-it auditor in the FINAL audit before Note Organizer for Android is published (Google Play). This is ROUND 2: round 1 found 33 Android defects and they were fixed (34 commits); the owner asked that every fix be attacked again by name, and that what round 1 left uncovered be covered now. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the Android app's round-2 break-it findings in the final audit of Note Organizer. Five auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names (file:line), re-read any probe it left in its scratch folder, check whether a guard elsewhere already stops it, whether it is one of the decisions already taken, whether a round-1 fix already covers it (git log audit/a-val0..audit/a-val1), or whether two findings are the same mechanism. You may not run gradle, adb, the emulator or a phone. Default to "plausible" when you cannot settle it either way, "confirmed" only when the code leaves no doubt or a probe showed it. Re-grade severity on the scale in the rules.

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
log(`android round 2: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:android', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
