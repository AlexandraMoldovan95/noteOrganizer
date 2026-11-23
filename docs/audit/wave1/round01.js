// The final audit: run wf_d33945e0-352, started 2026-10-27 18:27 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round1',
  description: 'Final audit wave 1, round 1: 12 break-it agents (6 desktop, 6 Android) attack the apps read-only, then one skeptic per app tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '6 desktop + 6 Android finders, each on one area, read-only on the repos' },
    { title: 'Refute', detail: 'one skeptic per app re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r1'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY_COMMON = `
HARD SAFETY RULES (real user data has been lost four times in this project -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything.
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Those are the owner's real notebooks.
- NEVER run qa*.py, test_*.py or note_organizer.py inside a repository, and never run the app on the Windows desktop (it would open windows on the owner's screens). No network access. No installing anything. If a command is refused, do not try another spelling of it -- note it under not_covered.
- Do not fix anything. Your job is to find and prove defects, and report them.
`

const DESKTOP_HOW = `
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val0). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, then docs/ARCHITECTURE.md, docs/ISSUES_LOG.md (its index tells what was already found and fixed in earlier break-it rounds -- go for what they missed, and for what is NEW since: the notebook moved to the profile folder C:\\Users\\<name>\\Note Organizer with migrations in noteorganizer/core/paths.py, the MSIX package (tools/msix), the Trash's Select all / Delete selected, the licenses card in About, Trash ages in real time).
HOW TO RUN THE APP SAFELY: only inside the Linux test image, in a throwaway copy. Put a probe script in SCRATCH_DIR and run (Git Bash):
  MSYS_NO_PATHCONV=1 docker run --rm --entrypoint sh -v "D:/Projects/NoteOrganizer:/repo:ro" -v "<SCRATCH_DIR with forward slashes>:/work" noteorg-linux-ci -c "xvfb-run -a python /work/probe.py"
A working example is ${SCRATCH}\\_smoke\\probe.py: it copies note_organizer.py and noteorganizer/ to /tmp/app, chdirs there, imports note_organizer as NO and builds NO.NoteOrganizer(). Seed notes by writing /tmp/app/notes_data.json BEFORE building the app. qa/qa*.py and qa/_qa_support.py show how the suite drives the app (read them for technique; never run them on the host).
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import (the app adopts any notebook it finds there) -- assert that before doing anything. Prefer docker.
`

const ANDROID_HOW = `
THE ANDROID APP: ${ANDROID} (branch audit/a-val0, version 0.13.0). Kotlin + Jetpack Compose, the same notebook format as the desktop (docs/DATA_FORMAT.md). Read its README, CLAUDE.md, docs/STATUS.md and docs/ISSUES_LOG.md (what earlier rounds found -- go for what they missed, and for what is new: folding sections, merges right/down, Find in checklist/comments, the Trash's Select all, reminders, the licenses page).
YOU MAY NOT run gradle, adb, the emulator or touch any phone (another process owns the single emulator; a phone attached is the owner's). Work by reading the code closely, and with Python probes in SCRATCH_DIR (for instance building a hostile backup .zip or share code, or replaying a Kotlin rule in Python to show its output). Every finding needs EXACT reproduction steps that the session can replay on the emulator (what to tap, what file or code to feed), plus the code path (file:line) that proves it.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes). low = cosmetic or far-fetched.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; the app is offline with no accounts; there are no Terms & Conditions; Pillow/Kotlin library internals are out of scope unless the app feeds them something it should have refused.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses. Depth over breadth: about 25 probes at most, then report.
End with an honest coverage confession: what you checked, and what you did NOT (files skipped, cases untried, probes refused).
`

const DESKTOP_AREAS = [
  { key: 'd1-data-loss', focus: `DATA LOSS AND CORRUPTION. Every path that writes notes_data.json, trash.json, templates.json, settings.json or attachments/: the atomic save and its backups, the migrations in core/paths.py (Case 1, Case 2, companions copied, purge of stale copies, durable stores), two app windows on one folder, a save interrupted halfway, a full or read-only disk, a file locked by another program, malformed files at start, undo/redo, the Trash (restore, delete for good, Select all, the purge at start), repeating notes' own days, tables. Find an ordinary sequence that loses a note's words, formatting or files.` },
  { key: 'd2-hostile-input', focus: `HOSTILE AND HUGE INPUT. Share codes and backup .zip imports (malformed, huge, deeply nested JSON, wrong types in every field), pastes (HTML, RTF, TSV, markdown tables, megabytes of text), images and GIFs (Pillow decompression-bomb limits, malformed headers, thousands of frames, huge dimensions), dates, the calculator, search queries, titles, emoji, lone surrogates, right-to-left and zero-width characters, a 5 MB note, 10,000 notes, a 300x300 table. Goal: a crash, a freeze over 5 s, a memory blow-up, or a save that comes back different.` },
  { key: 'd3-security', focus: `SECURITY: can a share code, a backup or an attachment someone sends make the app execute something, read or write outside its data folder, or leak notes? Attachments (stored_as with ../ or absolute paths, reserved names CON/NUL/AUX, alternate data streams name:stream, UNC paths, .lnk/.url/.exe/.bat/.cmd/.scr/.cpl/.msc/.hta/.js/.vbs/.ps1 reaching os.startfile, double extensions, right-to-left override in names), exported HTML (script injection when the person opens the export in a browser), URLs and links in notes (which schemes open, file:// or javascript:), clipboard HTML parsing, the zip guards (zip-slip, symlinks, bombs, duplicate names), crafted settings.json values (theme, fonts, paths) reaching file operations, the crash log (does any note text reach it?), Settings -> About's Open folder / licenses / privacy openers.` },
  { key: 'd4-lifecycle-time', focus: `LIFECYCLE AND TIME. Closing the window in the middle of things (an import or export running on its worker thread, a dialog or popup open, an edit not yet autosaved, a table cell being typed), the rule that the worker thread never touches a widget, timers firing after destroy, the system clock moving (back and forward), DST changes and other time zones for Trash ages, repeating notes and the calendar, midnight while the app is open, a session switching notes 1,000 times (memory growth), Settings changed while a note is being edited.` },
  { key: 'd5-accessibility', focus: `ACCESSIBILITY AND KEYBOARD. Can every surface be used with the keyboard alone (Tab order, focus traps, buttons Tab never reaches, Escape closing every popup, focus lost after a dialog closes)? Text sizes: Windows' text scaling and the app's Sharp text at 125-225% clipping words or controls (sizes go through px()/_SIZES_AT_100/_scale_drawing -- find ones that do not). Meaning carried by colour alone. Popups placed off-screen on a small window. What Tk can and cannot expose to a screen reader -- report only what is fixable in Tk.` },
  { key: 'd6-first-start-install', focus: `FIRST START, INSTALL AND PACKAGING. The built app choosing its folder (core/paths.py resolve_data_dir when frozen) under unusual profiles: a non-ASCII user name (Stefan with S-comma, Chinese), paths over 260 characters, a OneDrive-redirected profile, USERPROFILE missing, a FILE already named "Note Organizer", a folder of that name holding someone else's files, an unwritable profile; the MSIX (tools/msix: AppxManifest, capabilities, virtualization, version), NoteOrganizer.spec (what is bundled, the licenses check), the startup-crash dialog and "Missing dependency", settings and notes from very old versions (0.5.0 data shapes) at first start of this one, the backup made when the version changes. Test the frozen-path logic by reading it and by calling it with sys.frozen and env stand-ins inside docker.` },
]

const ANDROID_AREAS = [
  { key: 'a1-data-loss', focus: `DATA LOSS. Autosave timing against the process being killed (onPause/onStop, a kill right after typing, before the debounce), rotation or a configuration change mid-edit, Back and gestures leaving an editor, low storage, atomic writes, the Trash purge at start (window unknown, dates unreadable), backup export/import, Android Auto Backup (allowBackup in the manifest: what it backs up, and a restore onto a phone that already has notes), older notebooks coming in, the reminder receiver and the activity writing at the same time.` },
  { key: 'a2-hostile-input', focus: `HOSTILE AND HUGE INPUT. Share intents (huge text, many items, a malformed or hostile share code), backup .zip import (traversal, bombs, huge entries, wrong types in every JSON field), pastes (HTML entities, megabytes), attachments that are huge or odd, images, a 300x300 table, Find in a huge note, emoji and lone surrogates, the calculator. Goal: a crash (ANR or exception), a freeze, an out-of-memory, or a save that comes back different.` },
  { key: 'a3-security-privacy', focus: `SECURITY AND PRIVACY. The manifest (exported components, intent filters, FileProvider paths and grants, permissions), attachments opened in other apps (which URIs, which grants -- can a crafted backup or code make the app hand an internal file, or the whole notebook, to another app?), content URIs received from other apps, the PDF print WebView (JavaScript, file access, network), what a notification shows on the lock screen, Auto Backup sending notes to the person's Google account versus what docs/STATUS.md's Data safety reasoning and the privacy policy (the desktop's docs/PRIVACY.md) promise, logs carrying note text, the clipboard.` },
  { key: 'a4-lifecycle-state', focus: `LIFECYCLE AND STATE. Configuration changes (rotation, dark mode, locale, font scale, multi-window, a foldable's unfold) on every screen including dialogs and sheets, process death and what rememberSaveable restores, Back on every screen including the new Settings -> About -> Open-source licenses page, reminders (exact alarms, boot, a time-zone change, DST, Doze, a note deleted after its reminder is scheduled), the date changing at midnight with the app open.` },
  { key: 'a5-accessibility', focus: `ACCESSIBILITY. TalkBack: icons drawn as text (arrows, triangles, crosses) and what they are announced as; contentDescription missing; touch targets under 48 dp; font scale 200%; contrast; focus order; gestures without an alternative (long press, drag handles, swipes); meaning carried by colour alone. Report what an ordinary blind or low-vision person could not do at all, first.` },
  { key: 'a6-desktop-interop', focus: `INTEROP WITH THE DESKTOP. Notes, share codes and backups crossing between the two apps with edge or hostile content: fields one app writes that the other misreads or drops (formatting spans out of range, paragraphs, tables, checklist, comments, recurrence and its own days, attachments' names, colours, categories, unknown fields -- are they kept?), docs/DATA_FORMAT.md versus both implementations (the desktop's noteorganizer/core is in ${DESKTOP}, read-only), round trips that lose something.` },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      key: { type: 'string' }, title: { type: 'string' },
      severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
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

function finderPrompt(app, area) {
  const dir = `${SCRATCH}\\${area.key}`
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store and Google Play). Your one area:

${area.focus}

SCRATCH_DIR = ${dir}
${SAFETY_COMMON}
${app === 'desktop' ? DESKTOP_HOW : ANDROID_HOW}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(app, found) {
  const dir = `${SCRATCH}\\${app}-skeptic`
  return `You are the skeptic for the ${app} app's break-it findings in the final audit of Note Organizer. Six auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (desktop: only through the docker command; Android: by reading the code -- no gradle, adb, emulator or phone), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken, or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

SCRATCH_DIR = ${dir}
${SAFETY_COMMON}
${app === 'desktop' ? DESKTOP_HOW : ANDROID_HOW}
${REPORT}
FINDINGS (JSON):
${JSON.stringify(found, null, 1)}

Return one verdict per finding key. Name what you could not check under not_checked.`
}

const APPS = [
  { app: 'desktop', areas: DESKTOP_AREAS },
  { app: 'android', areas: ANDROID_AREAS },
]

const results = await pipeline(
  APPS,
  a => parallel(a.areas.map(area => () =>
    agent(finderPrompt(a.app, area), { label: `attack:${area.key}`, phase: 'Attack', schema: FINDINGS_SCHEMA })
      .then(r => r ? { area: area.key, ...r } : { area: area.key, findings: [], covered: '', not_covered: 'AGENT RETURNED NOTHING' }))),
  async (reports, a) => {
    const found = reports.filter(Boolean).flatMap(r => r.findings.map(f => ({ ...f, area: r.area })))
    log(`${a.app}: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
    if (!found.length) return { app: a.app, reports, verdicts: null }
    const v = await agent(verifierPrompt(a.app, found), { label: `refute:${a.app}`, phase: 'Refute', schema: VERDICT_SCHEMA })
    return { app: a.app, reports, verdicts: v }
  },
)
return results
