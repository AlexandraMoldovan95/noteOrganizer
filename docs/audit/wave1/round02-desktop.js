// The final audit: run wf_86e64089-00e, started 2026-10-28 00:52 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round2-desktop',
  description: 'Final audit wave 1, round 2 (desktop): 6 break-it agents re-attack every round-1 fix by name and the areas round 1 left uncovered, read-only; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '6 desktop finders: the fixes by name, the keyboard work, and round 1\'s uncovered areas' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r2'
const SMOKE = '<scratchpad>\\wave1\\r1\\_smoke\\probe.py'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Those are the owner's real notebooks. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- NEVER run qa*.py, test_*.py or note_organizer.py inside a repository, and never run the app on the Windows desktop (it would open windows on the owner's screens). No network access. No installing anything. If a command is refused, do not try another spelling of it -- note it under not_covered.
- Do not fix anything. Your job is to find and prove defects, and report them.
`

const HOW = `
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val1, checked out; do not switch branches). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, then docs/ARCHITECTURE.md and docs/ISSUES_LOG.md (its index names what earlier rounds found and fixed; the newest stories are the round-1 fixes listed below).
HOW TO RUN THE APP SAFELY: only inside the Linux test image, in a throwaway copy. Put a probe script in SCRATCH_DIR and run (Git Bash):
  MSYS_NO_PATHCONV=1 docker run --rm --entrypoint sh -v "D:/Projects/NoteOrganizer:/repo:ro" -v "<SCRATCH_DIR with forward slashes>:/work" noteorg-linux-ci -c "xvfb-run -a python /work/probe.py"
A working example is ${SMOKE}: it copies note_organizer.py and noteorganizer/ to /tmp/app, chdirs there, imports note_organizer as NO and builds NO.NoteOrganizer(). Seed notes by writing /tmp/app/notes_data.json BEFORE building the app. qa/qa*.py and qa/_qa_support.py show how the suite drives the app, keys and focus included (read them for technique; never run them on the host).
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import (the app adopts any notebook it finds there) -- assert that before doing anything. Prefer docker.
`

const FIXES = `
THE ROUND-1 FIXES (all on audit/d-val1; 'git log --oneline audit/d-val0..audit/d-val1' lists them, 'git show <hash>' shows each with its regression checks):
F1 6e41a7f+1a24e61 attachment aliases: storage._attachment_path_within refuses a stored name that resolves to a different path (8.3 short names, ::$DATA streams, symlinks); open_attachment's warning reads the resolved file's extension.
F2 38a001e a failed Trash write: move_notes_to_trash returns (ok, exc) and rolls back the list; every caller aborts with "Nothing was deleted".
F3 c570e41 start-up crashes: recurrence clamps catch OverflowError; is_redundant_copy fails closed; a scalar 'attachments' field read through storage.attachments_of everywhere.
F4 214abab close after a failed save: _notes_unsaved, a retry on close, then "Close without saving?" (default No).
F5 38b4464 an interrupted migration: copies go to .part and are renamed; the notes file is copied last.
F6 39c80b9+f5387c5 image preview memory: animated frames never grown, a 50-megapixel budget (_too_big_to_preview), PREVIEW_MEMORY_BYTES stops loading frames, the reference dropped on dismiss.
F7 b2c16bf a very large table shown as its text: MAX_DRAWN_TABLE_ROWS 400, MAX_DRAWN_TABLE_CELLS 3000.
F8 e5f6236 a backup without its Trash window: the import adopts the backup's trash_retention_days (1-365).
F9 c6a0015 fsync before os.replace in _write_json_atomic.
F10 ab322f5 Windows sign-out: on_session_end bound to WM_SAVE_YOURSELF (flush, save tabs, wait for workers up to 5 s).
F11 f2d9388 the reminder bar after midnight: _watch_the_day once a minute.
F12 85a72e7 an old folder judged by one file: migration Case 2 adopts a durable store whose notes file is empty or unreadable; the purge keeps a backup unless it is a redundant copy.
F13 89c2f99 misnested HTML in a paste: richtext's open-style stack per style.
F14 fface5e the crash log names only a file's basename/type/errno; the calculator catches RecursionError; an import refuses a backup whose notes are not a list.
F15 cf3ab2d the plain paste (Ctrl+Shift+V) capped at 100,000 characters, and says so.
F16 12e75d5 the Share panel's search-box trace removed on <Destroy>.
F17 2c55a7c+9e09ba6 a Trash row stamped in the future: days_left clamps elapsed to 0.
F18 f4d41e2 a FILE named "Note Organizer" where the notes folder goes is named as the cause in the fallback message.
F19 649313e 5dcb598 7da62b0 4f4f9e0 027d08c 07160f6 keyboard access across the app (NEW, large): two bind tags (_pressable, _key_walk) in ui/dialogs.py, popups taking and giving back the keyboard (_keyboard_into_popup/_keyboard_back/_keyboard_stays/_found_at), Tab scrolling its target into sight (_bring_into_sight), a focus_ring colour, drawn buttons as Tab stops, the calendar month walked by arrows, the delete toast's Undo as a Tab stop plus Ctrl+Z (bind_all) while it is offered, the Trash rows' ring and keyboard after Restore/Delete.
Accepted by the owner, NOT findings: the zip build adopting notes from its unpack folder (the Store ships MSIX only); USERPROFILE missing; the Trash clock set far ahead at start.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled; keyboard-only use works.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes); a keyboard trap. low = cosmetic or far-fetched.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; the app is offline with no accounts; there are no Terms & Conditions; Tk 8.6 exposes no names/roles to screen readers (not fixable in Tk); Pillow internals are out of scope unless the app feeds them something it should have refused.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses. Depth over breadth: about 25 probes at most, then report. For a fix you attacked and found sound, say so in 'covered' with what you tried -- that is a result too.
End with an honest coverage confession: what you checked, and what you did NOT (files skipped, cases untried, probes refused).
`

const AREAS = [
  { key: 'r2d1-fixes-data', focus: `RE-ATTACK THE DATA FIXES BY NAME: F1, F2, F3, F4, F5, F8, F9, F10, F12, F17, F18. For each: does it hold against a variation the fix's own check did not try (a different caller, the other platform's path, a second failure in a row, the fix's rollback itself failing, a race with autosave)? Did it break a neighbour (a caller that now aborts where it used to succeed, an alias refusal that hides a legitimate attachment, a migration that now leaves .part files or copies twice, a session end that saves a half-typed table cell wrongly)? Is the class fully swept (grep for siblings of each mechanism: other writes without fsync, other list mutations without rollback, other scalar-vs-list fields)?` },
  { key: 'r2d2-fixes-input', focus: `RE-ATTACK THE INPUT FIXES BY NAME: F6, F7, F11, F13, F14, F15, F16 -- then the hostile input round 1 never tried: clipboard HTML (core/clipboard.py read_html, richtext html_to_note) with hostile nesting, entities, huge attributes, script/style blocks; templates.json, trash.json and settings.json values (day_colors / day_emoji keys that are not dates, wrong types, huge lists) arriving in a hostile backup .zip; share codes with 200 large notes through the bulk route; 1e999 / NaN / huge ints reaching normalize_recurrence through a NOTE1: share code or a backup import; hostile recurrence rules (daily notes anchored in year 1, interval 0 or negative) and the calendar/History rendering them; lone surrogates and astral characters in find-in-note queries. Goal: a crash, a freeze over 5 s, a memory blow-up, or a save that comes back different.` },
  { key: 'r2d3-keyboard', focus: `ATTACK THE NEW KEYBOARD WORK (F19) as a keyboard-only user and as a mouse user it might have broken. Ideas: a focus trap anywhere (a popup that takes the keyboard and never gives it back; Tab cycling inside a page with no way out); Space or Return pressing a control when the person meant to type (the keyboard landing on a drawn control after a redraw while they were typing); _keyboard_stays / _keyboard_to_trash_row / _found_at landing the keyboard on a DESTRUCTIVE control (Delete forever, Empty trash, a category's delete) so that a second Enter does damage; Ctrl+Z (bind_all) taking a delete back when the person meant something else, or firing twice; the toast that waits while the keyboard is on Undo never going away or running its action late on a note that changed; a theme switch leaving rings in the old colours; the ring colour (focus_ring = the theme's text colour) failing on a surface; performance on a 1,000-note list (the bind_all ButtonPress counter, _bring_into_sight on every Tab); the pixel changes (padding traded for ring pixels) shifting layouts at 125-200% scale through px(). Then walk the surfaces round 1 never walked by keyboard: the Duplicates and Statistics panels, the template editor popup's insides, the Import panel, day mode, the Use template picker, the selection bar's Category and Export popups, the date picker, the table-size grid.` },
  { key: 'r2d4-uncovered-data', focus: `DATA PATHS ROUND 1 NEVER PROBED: undo/redo stacks (across note switches, after a table edit, after an autosave); tables with autosave and restore (grid edits, a table rebuilt mid-typing); share-code import and update end to end (apply_shared_update, rescue copies, a shared note that already exists, changed or deleted); backup export then import end to end with every heavy feature (tables, checklists, recurrence with own days, attachments, formatting, templates, Trash); the templates editor (save, cancel, half-written, delete while open); settings.json written by two windows on one folder; the welcome note and About paths; the migration's 'richest legacy copy' choice adopting a stale folder over the real notebook. Find an ordinary sequence that loses a note's words, formatting or files.` },
  { key: 'r2d5-uncovered-security', focus: `SECURITY ROUND 1 LEFT UNPROBED (its security auditor stopped early): crafted backup zips -- duplicate entry names, a lying file_size, absolute or drive-relative names, directory entries, Windows reserved names (CON, NUL, COM1) and trailing dots/spaces inside attachments/; attachment display names with right-to-left override or control characters (what the person sees versus what opens); bulk export with reserved device names, path separators and very long titles as file names; the attachment deny list checked one extension at a time (.py .pyw .msixbundle .appxbundle .rdp .xll .msu .theme .settingcontent-ms .library-ms .search-ms .url .lnk .scf .application .appref-ms and others); UNC and \\\\?\\ prefixes, NUL and invalid characters in stored_as; the Trash's Select all / Delete selected through _delete_attachment_files; HTML export injection (note text, titles, attachment names reaching the exported page); links in notes (schemes that open). Prove an escape, an execution, or a leak.` },
  { key: 'r2d6-uncovered-time', focus: `TIME AND LIFECYCLE ROUND 1 LEFT UNPROBED: the clock moving BACK mid-session ('Recently updated' order, the import's OLDER warning, reminder_last_shown, Trash ages); a time-zone change while the app is open; DST boundaries in recurrence, the calendar and History; deleting or renaming a category while a note in it is dirty; timers (every after/after_idle debounce) firing after their widget is destroyed -- probe them one by one, not through crash logs; the template picker with templates, opened and closed 500 times (memory); the version-change backup colliding in the same second or failing on a full disk; an export cut off by a session end (leftover .tmp, a missing notice); the licenses card in About. Goal: a crash, a wrong date or order the person acts on, a leak, or lost work.` },
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
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store). This is ROUND 2: round 1 found 32 desktop defects and they were fixed; the owner asked that every fix be attacked again by name, and that what round 1 left uncovered be covered now. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${FIXES}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the desktop app's round-2 break-it findings in the final audit of Note Organizer. Six auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (only through the docker command), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken, whether it is a round-1 finding already fixed (git log audit/d-val0..audit/d-val1), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

SCRATCH_DIR = ${SCRATCH}\\desktop-skeptic
${SAFETY}
${HOW}
${FIXES}
${REPORT}
FINDINGS (JSON):
${JSON.stringify(found, null, 1)}

Return one verdict per finding key. Name what you could not check under not_checked.`
}

const reports = await parallel(AREAS.map(area => () =>
  agent(finderPrompt(area), { label: `attack:${area.key}`, phase: 'Attack', schema: FINDINGS_SCHEMA })
    .then(r => r ? { area: area.key, ...r } : { area: area.key, findings: [], covered: '', not_covered: 'AGENT RETURNED NOTHING' })))
const found = reports.filter(Boolean).flatMap(r => r.findings.map(f => ({ ...f, area: r.area })))
log(`desktop round 2: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:desktop', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
