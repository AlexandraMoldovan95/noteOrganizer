// The final audit: run wf_7fe34abf-f68, started 2026-10-28 08:27 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round4-desktop',
  description: 'Final audit wave 1, round 4 (desktop): 6 read-only break-it agents re-attack every round-3 fix by name (data, attachments, keyboard, limits), round 3 gaps and the seams between its two hands; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '6 desktop finders: the round-3 fixes by name, their seams, and round 3\'s gaps' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r4'
const SMOKE = '<scratchpad>\\wave1\\r1\\_smoke\\probe.py'
const R3GAPS = '<scratchpad>\\wave1\\r3\\not_covered.txt'
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
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val1, checked out; do not switch branches). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, docs/ARCHITECTURE.md, and docs/ISSUES_LOG.md -- its newest stories ("Round three: one rescue copy, and files another program holds"; the "Round three" paragraphs inside "Limits that held at the door but not after it" and "The photo that was a remote connection"; the keyboard story's newest round) describe the round-3 fixes.
HOW TO RUN THE APP SAFELY: only inside the Linux test image, in a throwaway copy. Put a probe script in SCRATCH_DIR and run (Git Bash):
  MSYS_NO_PATHCONV=1 docker run --rm --entrypoint sh -v "D:/Projects/NoteOrganizer:/repo:ro" -v "<SCRATCH_DIR with forward slashes>:/work" noteorg-linux-ci -c "xvfb-run -a python /work/probe.py"
A working example is ${SMOKE}: it copies note_organizer.py and noteorganizer/ to /tmp/app, chdirs there, imports note_organizer as NO and builds NO.NoteOrganizer(). Seed notes by writing /tmp/app/notes_data.json BEFORE building the app. qa/qa*.py and qa/_qa_support.py show how the suite drives the app (read for technique; never run them on the host).
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import (assert that first). Windows-only behaviour (NTFS streams, a file held by ANOTHER process with share mode 0 via ctypes CreateFileW in a child process, case-insensitive names) needs such a probe -- round 3 never ran one, and that is a named gap.
`

const FIXES = `
THE ROUND-3 FIXES (all on audit/d-val1; 'git log --reverse --format="%h %s%n%b" 31696cf..audit/d-val1' lists them with their reasoning and mutants):
DATA (mutants DR29-DR40), one hand: 1a949bc the one rescue copy (_prev): a share code ending a repeat COPIES the series' days into the copy and the note keeps them (core.model days_to_rescue, apply_shared_update, copy_replaced_by_restore); a table's padding is not counted as text lost (_PADDING / _without_padding in rescue_copy_due); a turn-off in the editor keeps the days and merges an unspent text-only copy (_turn_off_rescue_copy, _days_kept_off_repeat); the single and bulk update questions say when they replace an unspent copy (_REPLACES_EARLIER_RESCUE, _holds_unspent_rescue). 09c3ce5 a data file is read up to 3 times, 0.5 s apart (storage._read_data_file); a file neither read nor copied is never written that run (paths.hold_writes / writes_held; _write_json_atomic refuses with PermissionError); the first-start copy of an older notebook is all-or-nothing for notes + settings, holds writes, and says so; the export refuses after an unreadable start ("Nothing to back up yet") and packs templates/Trash raw when memory is empty. b4bbc04 a Windows session end saves a template editor's work (pop._save_without_asking, a taken name becomes "Name (2)"); a finished import takes back an earlier "cut short" line (_take_back_cut_short). a51272e (after review) a checklist item already longer than 2,000 is KEPT WHOLE by every load; only its row is drawn cut (core.model.checklist_shown: 2,000 characters / 100 lines, then "…").
ATTACHMENTS, KEYBOARD, LIMITS (mutants RT01-RT24), another hand: 66a44e3 a stored attachment name holding ":" is refused everywhere (storage._attachment_path_within), add_attachment stores ":" as "_"; bc921da an animation's canvas pixels are budgeted across all frames (ANIMATION_PIXEL_BUDGET = 4 x PREVIEW_PIXEL_BUDGET) and kept frames capped (PREVIEW_MAX_FRAMES 1,000); 31f9207 an attachment name is a Tab stop (Space/Return opens), a preview opened by key puts the keyboard on Close, Escape closes the preview (a root <Escape> binding added once), the keyboard returns to the row; d780cd9 a Tk button whose press HIDES it hands the keyboard on (dialogs._tk_press_ends); cb669e5 a hidden Undo lands on the sidebar arrow while the list is put away (_toast_landing); b601fdd Settings opened by a click takes the keyboard off the hidden note and gives it back on leaving (_keyboard_inside / _keyboard_to, which parks the keyboard on the main window until the target is mapped), a hidden text box no longer counts as typing, the sidebar hidden by its arrow does the same; a3d11a7 the template editor's table preview uses the cached _ellipsize / _measure_text with one font; 6e8a4ef the checklist Add boxes (note and template) refuse a key or paste past 2,000 (_limit_entry validator), template name/title boxes keep 200; c085ddc a picture the preview's decoders refuse is offered to its program (_cannot_preview, default Yes); 7aa5a85 a long attachment name gives way before its type (_fit_title from calendar_view); 16b85fb a Checkbutton/Radiobutton is looked at straight after Space (Button keeps its 100 ms); 8239c2e the attachment row's ✕ is packed before the name so a long name cannot squeeze it out.
Accepted by the owner or already in her test plan, NOT findings: the earlier accepted items (zip build adopting its unpack folder, USERPROFILE missing, Trash clock far ahead, clock set back mid-session); the Settings section entries draw no keyboard ring (existing styling, flagged for her eye); a checklist paste over 2,000 refused whole while the note title's box shortens a paste (flagged for her); an over-long checklist item's row shows no way to read the rest (by design, flagged); an animation stopping after its budget; Escape closing the preview for mouse users too.
KNOWN OPEN LOWS (do not re-report unless you show it is worse than low): a template lost at close after a failed templates write (save_templates' result ignored); pasted HTML that is markup-only read whole; the paste ceiling counted in characters, not Tk indices, for astral emoji; keyboard left in a hidden container by a click OTHER than Settings / the sidebar arrow (e.g. Share's Close clicked while typing in its search) -- known as a class, but DO report a case where such keys change saved data; search/find boxes and other never-saved one-line boxes take pastes of any length (no freeze measured on Linux).
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled; keyboard-only use works.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes); a keyboard trap. low = cosmetic or far-fetched.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; offline, no accounts, no Terms & Conditions; Tk 8.6 exposes no names/roles to screen readers; Pillow internals out of scope unless the app feeds them something it should have refused.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 25 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the round ends when two rounds in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'r4d1-data-fixes', focus: `RE-ATTACK THE ROUND-3 DATA FIXES BY NAME (1a949bc, 09c3ce5, b4bbc04, a51272e). For each: a variation the fix's own check did not try, a neighbour it broke, an unswept sibling. Ideas: the days now kept BOTH in the note and in _prev -- can they double up, resurface where they should not (a turn-on that shows stale day text, a second turn-off copy, Duplicate, an export, the share code, search or the dirty comparator reading hidden day text), or make the next rescue copy carry the wrong version?; _without_padding hiding a REAL loss (prose holding runs of spaces or dashes -- ASCII art, a hand-typed markdown table, a signature line of "-----" -- deleted whole: is a copy still made?); the update question's warning on the bulk route with many notes, some holding unspent copies; hold_writes: is there ANY route that still writes a held file (backup_notes_file, the migration, save_trash, save_templates, settings, the attachments cleanup, the export's temp file, the update's version backup, repair_note_ids), and can the hold be lifted wrongly mid-session?; a held start: is the person told before typing a whole session that cannot be saved, and does every later save say so without a modal storm?; the 3 tries x 0.5 s on each of four files at a start where all are unreadable (6 s before the window?); the all-or-nothing first start when only attachments fail; the session-end template save with an empty name, a name of 200 characters (+ " (2)"), an EXISTING template being edited (does it overwrite, duplicate, or drop the edit?), two template editors' worth of state; the cut-short take-back with two imports; checklist_shown at the cut point (an astral emoji or a combining mark split at 2,000; a line break as the 2,000th character) and every other reader of item text (content signatures, the card's 1/2 count, search, Find, the share code) agreeing with the stored, not the shown, text.` },
  { key: 'r4d2-attachment-fixes', focus: `RE-ATTACK THE ROUND-3 ATTACHMENT FIXES BY NAME (66a44e3, bc921da, c085ddc, 7aa5a85, 8239c2e, and the preview half of 31f9207). Ideas: the ":" refusal -- a notebook made on Linux before it whose stored names hold ":": is the attachment now shown as missing, and does ANY cleanup (orphan sweep, Empty Trash, Delete forever, attachment_names_in, the export) treat that real file as unreferenced and delete it or leave it out of a backup?; the animation budget against ORDINARY animations (an 800x600 GIF of 500 frames is 240 MP, past 200 MP -- does a normal animation now stop or loop strangely partway, and does a second open replay or redecode?), APNG and animated WebP, a GIF whose canvas grows; _cannot_preview's Yes -- does it go through the same allow list and warnings as every other hand-off (a file stored as .jpg whose content is a program; a stored type that is on the dangerous list but shown as a picture)?; the root <Escape> binding added once -- is it ever removed, and does Escape now also do something unwanted elsewhere (closing a popup AND the preview, cancelling a cell edit and backing out, Escape in the find bar or the calendar)?; _fit_title on names with right-to-left text, zero-width or astral characters, a type longer than the row, a name with no type; the ✕ packed first (Tab order, the hint row, a row at 200 attachments: time to draw now that each name measures itself).` },
  { key: 'r4d3-keyboard-fixes', focus: `RE-ATTACK THE ROUND-3 KEYBOARD FIXES BY NAME (31f9207 keyboard half, d780cd9, cb669e5, b601fdd, 16b85fb) as a keyboard-only user and as a mouse user they might have broken. Ideas: _keyboard_to parks the keyboard on the MAIN WINDOW until the target is mapped -- which root or bind_all shortcuts act while it is parked (Ctrl+S, Delete, Ctrl+Z, Ctrl+D, letters), and can one change a note nobody can see?; hide_settings_page giving the keyboard back to a widget whose note changed or was deleted while Settings was open (a note deleted from Settings' Trash, a category renamed, an import run from Settings) -- does the caret land in a body now showing another note and do keys type into it?; Settings opened by keyboard vs by mouse vs by a shortcut; the sidebar hidden by its arrow while a rename or a selection is active; the hidden-button handover when the press opens a modal question, destroys the whole popup, or is pressed twice fast; Space then Tab on every Checkbutton/Radiobutton now judged at once (the Trash's tick boxes, the share panel's rows, Settings radio groups); THE CLASS LEFT OPEN: enumerate EVERY mouse click that hides a container which can hold the keyboard (the Share and Import panels' Close, day mode's ✕, the calculator or checklist section collapsed by a click, the find bar's ✕, a tab closed, the template editor dismissed by a click outside) and check whether keys pressed afterwards still go into the hidden widget AND change saved data -- report each one that does; and the lead from round 3: the table cell's checkmark and highlight colour popups close on a <FocusOut> bound on their Toplevel's tag, so Tabbing between swatches may close them (a keyboard user could not pick a colour).` },
  { key: 'r4d4-limit-fixes', focus: `RE-ATTACK THE ROUND-3 LIMIT AND PERFORMANCE FIXES BY NAME (a3d11a7, 6e8a4ef, a51272e's drawing side) and the known open lows where they could be worse. Ideas: the template preview's measuring cache (_measure_text / _ellipsize) -- is it bounded? A 99,000-character cell bisected at every key, across many cells and templates: does memory grow without limit over a long session?; _limit_entry vs other validators or bindings on the same Entry (the title's own validator, the astral guard's bindings, the paste menu, middle-click, drag and drop of text), a value set programmatically past the limit (a template loaded with a 300-character name), Undo in the box; the checklist cap's add functions' slice vs the validator (can a 2,001st character arrive by a route the validator never sees -- the paste menu, middle-click, an IME, a programmatic insert?); 2,000 characters of one unbroken word in a checklist row or a template row (the wrap cannot break it: how wide does the row get, is the bin still reachable?); the template name/title boxes at 200 vs an imported template with a longer name being renamed; the open lows: a 600,000-character paste into the search box / find box on a 1,000-note notebook (each key filters: time per key?), the astral ceiling counted in characters, pasted HTML that is markup only (10 MB) -- measure, and say whether any is worse than low.` },
  { key: 'r4d5-round3-gaps-data', focus: `WHAT ROUND 3 SAID IT DID NOT COVER, data and time half. Read ${R3GAPS} (sections r3d1, r3d5, and the skeptic's not_checked). Probe the gaps most likely to hide a defect that matters, at least four, and say which you skipped and why. Above all: (1) a REAL hold by another process on Windows -- a child process opens notes_data.json (then trash.json, settings.json) with share mode 0 through ctypes CreateFileW, in an isolated SCRATCH copy, and the core start (storage loads, paths.run_migrations, the first save) runs against it; release the hold after 1 s and after 5 s; (2) the table operations OTHER than the cell editor that re-pad a table (insert or delete a column or row, autofit, paste cells, a column dragged wider, a narrower edit) against the rescue copy now that padding is not counted as loss; (3) NTFS: a data file or attachment whose case changed, trailing dot/space names, a junction as the data folder (Windows pure-Python only); (4) two app processes writing settings.json and the notes lock's fail-open cases; the migration cases; DST in History; the Welcome note re-shown.` },
  { key: 'r4d6-round3-seams', focus: `THE SEAMS BETWEEN THE ROUND-3 FIXES, made by two hands in parallel and merged afterwards, plus round 3's security/keyboard gaps. Read ${R3GAPS} (sections r3d2, r3d3, r3d6). Cross the fixes: held files x the export refusal x a session end x the first-start copy (a session end while writes are held: does anything write, does the template editor's session-end save try and fail loudly?); the checklist drawn cut x the rescue copy x a share update x Duplicate x Save as template (does a cut row ever get saved as its shown text?); the Settings keyboard handover x a session end x the reminder bar x the toast landing; the attachment keyboard x the hidden-button handover x the preview's Escape x click-outside dismissal x _cannot_preview's question (Space on a name whose preview fails: where is the keyboard after the question?); the template preview speedup x the session-end template save x the template editor's style tags; the ":" refusal x the export x a backup round trip. And from round 3: clicking a note card while Settings shows loads it into the hidden editor while Settings stays up (seen in r3d6 p12) -- with the new keyboard handover, where do keys go, and can they change that note unseen? Find an ordinary sequence where two fixes, each right alone, together lose work, crash, mislead, trap the keyboard, or open something unasked.` },
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
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store). This is ROUND 4: round 3 found 24 desktop defects (1 critical, 4 high) and they were fixed by two separate hands (one did the data fixes, another attachments/keyboard/limits) and merged; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${FIXES}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the desktop app's round-4 break-it findings in the final audit of Note Organizer. Six auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (only through the docker command, or a Windows pure-Python probe under the same isolation), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open low, whether an earlier fix already covers it (git log 31696cf..audit/d-val1 for round 3), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`desktop round 4: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:desktop', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
