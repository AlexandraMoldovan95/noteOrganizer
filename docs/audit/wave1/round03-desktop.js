// The final audit: run wf_58340178-0ce, started 2026-10-28 04:16 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round3-desktop',
  description: 'Final audit wave 1, round 3 (desktop): 6 read-only break-it agents re-attack every round-2 fix by name (data, attachments, keyboard, hostile input) and round 2 gaps; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '6 desktop finders: the 25 round-2 fixes by name, their seams, and round 2\'s gaps' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r3'
const SMOKE = '<scratchpad>\\wave1\\r1\\_smoke\\probe.py'
const R2GAPS = '<scratchpad>\\wave1\\r2\\not_covered.txt'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- NEVER run qa*.py, test_*.py or note_organizer.py inside a repository, and never run the app on the Windows desktop (it would open windows on the owner's screens). Never call os.startfile on a real file. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val1, checked out; do not switch branches). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, docs/ARCHITECTURE.md, and docs/ISSUES_LOG.md -- its newest stories ("Round two: each fix's next door", "The photo that was a remote connection", "Limits that held at the door but not after it", the keyboard story's second round) describe the round-2 fixes.
HOW TO RUN THE APP SAFELY: only inside the Linux test image, in a throwaway copy. Put a probe script in SCRATCH_DIR and run (Git Bash):
  MSYS_NO_PATHCONV=1 docker run --rm --entrypoint sh -v "D:/Projects/NoteOrganizer:/repo:ro" -v "<SCRATCH_DIR with forward slashes>:/work" noteorg-linux-ci -c "xvfb-run -a python /work/probe.py"
A working example is ${SMOKE}: it copies note_organizer.py and noteorganizer/ to /tmp/app, chdirs there, imports note_organizer as NO and builds NO.NoteOrganizer(). Seed notes by writing /tmp/app/notes_data.json BEFORE building the app. qa/qa*.py and qa/_qa_support.py show how the suite drives the app (read for technique; never run them on the host).
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import (assert that first). Windows-only behaviour (NTFS streams, the Mark of the Web, case-insensitive names) needs such a probe.
`

const FIXES = `
THE ROUND-2 FIXES (all on audit/d-val1; 'git log --reverse --format="%h %s%n%b" 1f972b0..audit/d-val1' lists them with their reasoning and mutants):
DATA (mutants DR01-DR28): 53353da a repeat ended by a share code or Restore previous keeps its days (core.model days_to_rescue, DAY_FIELDS; the editor's save keeps days no copy holds); 53c8f46 the end of a Windows session runs the close's own save list (_save_on_the_way_out), asks nothing, lets an export finish, stops and drops an import saying so, startup words for a session cut-short; e69721e a backup's Trash window taken only when longer, Trash rows read through a shaped copy, attachment_names_in everywhere; 5cfb25e the export packs what the app holds (storage.json_text), the migration retries held files then names what it could not copy, an unreadable old settings file travels, fsync before every os.replace (a source check in test_data_safety); a20fdec an attachment name resolves only to a file of exactly that name (bare name, case included); eb0d433 the template editor keeps styles as tags; 52e0580 the reminder bar above whichever page shows, the day watch re-armed in a finally; 60c6289 the update's safety copy whole or absent and said, the one-time cleanup waits for a copy.
ATTACHMENTS (mutants AX01-AX17): a7495d5 the shown name ends in the stored file's type, hidden characters stripped (attachment_display_name, HIDDEN_IN_NAMES); eed2fb9 an allow list (OPENS_WITHOUT_ASKING / how_to_open): known-dangerous kinds get the strong warning, unknown kinds a calm "Open this file?", every hand-off through _open_externally; 201f0f5 the zip's Zone.Identifier copied onto restored attachments (zone_mark_of / put_zone_mark); 1fcc189 export_file_stem for both exports, failed notes named; 9d96934 every animation frame judged before decode, Image.open restricted to PNG/JPEG/GIF/BMP/WEBP.
KEYBOARD (mutants KR01-KR12): 07e191b a popup with no choices lands in its first box, text selected; fcca27c Tk's Button/Checkbutton/Radiobutton <Key-space> class bindings wrapped so a destroyed button hands the keyboard on, the click counter per button; ed6ead1 Page Up/Down, arrows, Home/End scroll the Settings page unless in a text box or popup; be35df1 a ring's colours follow a theme switch; 1f9ed8c a hidden Undo hands the keyboard on.
HOSTILE INPUT (mutants IX01-IX23): 5e757e4 moved-days counts linear (_drawn_on_days, _rule_days_among, drawn_moves); a315c1c one paste cap on every route (_cap_paste / _clipboard_text), middle-click included; 8d68b6b table padding checked before it is built (MAX_TABLE_PADDING, row_widths), ragged past it; 304d430 day decorations capped and validated at start and import (MAX_DAY_DECORATIONS 20,000, is_calendar_day), collapsed_groups strings only; 0d05263 templates capped at 1,000 at load and import, the 1,001st refused; 9e2cb34 pasted HTML read in 64 KB pieces up to the ceiling; 846a126 lone surrogates mended on read (json_from_text) for the data files, the import and share codes.
Accepted by the owner, NOT findings: the zip build adopting notes from its unpack folder (the Store ships MSIX only); USERPROFILE missing; the Trash clock set far ahead at start; the clock set back mid-session stalling Tcl timers (no data lost).
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled; keyboard-only use works.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes); a keyboard trap. low = cosmetic or far-fetched.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; offline, no accounts, no Terms & Conditions; Tk 8.6 exposes no names/roles to screen readers; Pillow internals out of scope unless the app feeds them something it should have refused.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 25 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the round ends when two rounds in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'r3d1-data-fixes', focus: `RE-ATTACK THE ROUND-2 DATA FIXES BY NAME (53353da, 53c8f46, e69721e, 5cfb25e, a20fdec, eb0d433, 52e0580, 60c6289). For each: a variation the fix's own check did not try, a neighbour it broke, an unswept sibling. Ideas: days_to_rescue when the repeat changes kind (weekly to daily) or its anchor date moves; a second Update before the first's Restore; the editor keeping days no copy holds -- can they now resurface wrongly (turning a repeat back on, a duplicate, an export, search/find matching hidden day text)?; _save_on_the_way_out with several tabs, a cell editor open, a held repeat turn-off, a template editor open; a session end during an import's question, or twice; the export from memory while an autosave is pending, with 5,000 notes (main-thread time), with a Trash entry that json_text cannot serialise; the strict attachment name on a file whose on-disk case changed (renamed in Explorer), on Unicode names that normalise differently (NFC/NFD), on long or 8.3-only volumes; the template editor's tags with tables hidden (tblhide), list markers, and a body edited to empty; the reminder bar when Settings closes, opens and closes around midnight; the cleanup that now waits -- does it ever run again, and does a backup that fails every time mean the cleanup never runs?` },
  { key: 'r3d2-attachment-fixes', focus: `RE-ATTACK THE ROUND-2 ATTACHMENT FIXES BY NAME (a7495d5, eed2fb9, 201f0f5, 1fcc189, 9d96934). Ideas: names how_to_open misjudges (".PDF", "x.pdf.", "x.pdf::$DATA" now refused?, a name with no dot, ".jpg" alone, "x.tar.gz", double extensions where Windows uses the last); a kind on the allow list whose usual handler does run content (.svg is not on it -- check .ico, .heic, .md, .rtf, .csv, .log handlers, .mov/.mkv with external subtitles); attachment_display_name on a stored name with no type, on hidden characters inside the type, on a label longer than the row; the strong vs calm warning chosen from the shown or the stored name; a file attached by hand or duplicated keeping or losing the Zone mark, a backup exported and re-imported (marks lost through the zip?), a zip on FAT/exFAT; export_file_stem on reserved device names (CON, NUL, COM1, "aux.txt"), trailing dots, names that collide case-insensitively; the preview's frame budget against a GIF with thousands of tiny frames (time, not memory), an APNG, a WebP animation, a JPEG MPO, a PNG that is really a TIFF; Image.open's format restriction vs the row's preview choice (can the row promise a preview the decoder now refuses?).` },
  { key: 'r3d3-keyboard-fixes', focus: `RE-ATTACK THE ROUND-2 KEYBOARD FIXES BY NAME (07e191b, fcca27c, ed6ead1, be35df1, 1f9ed8c) as a keyboard-only user and as a mouse user they might have broken. Ideas: the wrapped <Key-space> class binding on every Tk Button/Checkbutton/Radiobutton -- a button whose command opens a modal question, destroys its own window, or is pressed twice fast; Space held down (auto-repeat); a popup landing in its box with text selected -- the first key replacing a template's name or a jump's year; Page Down on Settings while a dropdown, the find bar or a question is open; Up/Down on Settings no longer walking the nav; rings after theme switches on every ringed control, not only the reminder bar; the hidden Undo's landing when the note list is empty or Settings has no section; any focus trap or lost keyboard the round-2 changes introduced on the notes page, the calendar, day mode, the template editor, the share and import panels. Performance: the per-button click counter and update_idletasks in _keyboard_stays with 1,000 notes.` },
  { key: 'r3d4-input-fixes', focus: `RE-ATTACK THE ROUND-2 HOSTILE-INPUT FIXES BY NAME (5e757e4, a315c1c, 8d68b6b, 304d430, 0d05263, 9e2cb34, 846a126). Ideas: the paste cap on every door -- drag and drop of text into the body, the find box and search box, the title's 200, a paste over a selection that spans a table, Undo after a capped paste, the "Pasted in part" message twice, the cap counted in characters vs Tk indices for astral emoji; MAX_TABLE_PADDING -- a table typed by hand that grows past it, a ragged table round-tripped through share code / backup / the Android app's format (docs/DATA_FORMAT.md), Find and the calculator in a ragged table; day decorations -- a person's own markers dropped at a start (anything a real person made that is now refused: old date spellings, emoji with joiners past 16 characters, a marker on a date before 1900 or after 2100); templates at the cap -- import merging, rename onto a taken name, Save as template when at 1,000; json_from_text -- does mending change bytes of a VALID file (a note holding a real escaped backslash-u sequence as text, e.g. a programmer's note "\\\\ud83d"), and does a mended file get written back over the original without a copy; the linear moved-days code against the old predicate on odd date spellings and collisions.` },
  { key: 'r3d5-round2-gaps-data', focus: `WHAT ROUND 2 SAID IT DID NOT COVER, data and time half. Read ${R2GAPS} (sections r2d1, r2d4, r2d6 and the skeptic's not_checked). Probe the gaps most likely to hide a defect that matters, at least four, and say which you skipped and why: e.g. undo/redo after a table edit or an autosave; Restore previous while a cell editor is open; an Update replacing a rescue copy unasked; save_templates' result ignored by the template editor and the import (a failed templates write lost at close -- known low, check whether it is worse); a corrupt notes file whose preserve-copy fails and is then overwritten by the next save; stale %TEMP%\\notes_import_* folders after a killed import (no startup sweep); the grid autoscroll timer never stopped; a time-zone change while the app is open (on Windows Python, without time.tzset).` },
  { key: 'r3d6-round2-gaps-seams', focus: `WHAT ROUND 2 LEFT UNCOVERED, security/keyboard half, and THE SEAMS BETWEEN THE FOUR ROUND-2 FIX GROUPS (they were made by four different hands in parallel and merged afterwards). Read ${R2GAPS} (sections r2d3, r2d5). Then cross the fixes: the allow list x the display name x the Zone mark (a crafted backup whose label, stored type and mark disagree); the paste cap x the template editor's new tags (a capped paste into a template body with styles); the export from memory x templates capped at 1,000 x day decorations capped (an export then re-import of a notebook at every cap); the session end x a paste in progress x the keyboard wrap; the strict attachment name x export_file_stem x the bulk export; the reminder bar on Settings x the new Settings page keys. Find an ordinary sequence where two fixes, each right alone, together lose work, crash, mislead, or open something unasked.` },
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
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store). This is ROUND 3: round 2 found 25 desktop defects beyond round 1's and they were fixed by four separate hands (25 commits, merged); the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${FIXES}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the desktop app's round-3 break-it findings in the final audit of Note Organizer. Six auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (only through the docker command, or a Windows pure-Python probe under the same isolation), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken, whether a round-1 or round-2 fix already covers it (git log 1f972b0..audit/d-val1 for round 2), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`desktop round 3: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:desktop', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
