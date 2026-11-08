// The final audit: run wf_7b99d1db-c35, started 2026-10-29 05:50 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round6-desktop',
  description: 'Final audit wave 1, round 6 (desktop): 5 read-only break-it agents re-attack every round-5 fix by name (data, interface, the chunked lists of 1a, the late fixes), round 5 gaps and the seams between the hands; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '5 desktop finders: round-5 data fixes, interface fixes, the chunked lists, round 5 gaps, the seams' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r6'
const SMOKE = '<scratchpad>\\wave1\\r1\\_smoke\\probe.py'
const R5GAPS = '<scratchpad>\\wave1\\r5\\not_covered.txt'
const R5SUMMARY = '<scratchpad>\\wave1\\r5\\summary.txt'
const R5FINDINGS = '<scratchpad>\\wave1\\r5\\findings'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- NEVER run qa*.py, test_*.py, tools/run_tests.py, tools/mutate.py or note_organizer.py inside a repository, and never run the app on the Windows desktop (it would open windows on the owner's screens). Never call os.startfile on a real file. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- DOCKER HYGIENE: every docker run uses --rm AND puts the timeout INSIDE the container, so the container itself ends: -c "timeout -k 10 240 xvfb-run -a python /work/probe.py". A probe that may wait on a dialog must answer or stub it (app.show_info / show_warning / ask_yes_no / ask_yes_no_cancel / _themed_dialog). Never start a container without that inner timeout, and never docker kill/stop/rm anything (the full Linux suite runs in its own container right now -- leave it alone).
- The machine is busy (the full Windows and Linux suites run in parallel): a timing claim needs a same-run comparison (with and without, or small and large), never one absolute number.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val1 at 2a17ad7, checked out; do not switch branches). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, docs/ARCHITECTURE.md, and docs/ISSUES_LOG.md -- its three newest stories ("Round five: a retry paid at every read, and shares in the wrong unit", "Round five: the shortcuts under a picture, and a toolbar laid out again", and "The list that ended in the middle") describe the round-5 fixes.
HOW TO RUN THE APP SAFELY: only inside the Linux test image, in a throwaway copy. Put a probe script in SCRATCH_DIR and run (Git Bash):
  MSYS_NO_PATHCONV=1 docker run --rm --entrypoint sh -v "D:/Projects/NoteOrganizer:/repo:ro" -v "<SCRATCH_DIR with forward slashes>:/work" noteorg-linux-ci -c "timeout -k 10 240 xvfb-run -a python /work/probe.py"
A working example is ${SMOKE}: it copies note_organizer.py and noteorganizer/ to /tmp/app, chdirs there, imports note_organizer as NO and builds NO.NoteOrganizer(). Seed notes by writing /tmp/app/notes_data.json BEFORE building the app. qa/qa*.py and qa/_qa_support.py show how the suite drives the app (read for technique; never run them on the host). For a photograph inside the container, grab the app's own window (xwd/import of the root window id, or PIL ImageGrab under Xvfb) into /work and LOOK at it.
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import (assert that first).
`

const FIXES = `
THE ROUND-5 FIXES (all on audit/d-val1; 'git log --reverse --format="%h %s%n%b" 8fbb831..2a17ad7' lists them with their reasoning and mutants). Round 5's findings, one line each: ${R5SUMMARY}; one JSON per finding in ${R5FINDINGS}.
DATA HALF (one hand; mutants DR57-DR71): ce3d2e0 a settings.json held for the run costs one try per read, not a second of retries (the start reads with retries once; later reads after a refusal try once and use the last good read); 498837b an item typed in the BLANK editor's checklist Add box is saved by any way out (_take_pending_checklist_item on every exit); 916926f a repeat turn-off whose own save also takes text keeps the newest text over a held save's copy too (_turn_off_rescue_copy(takes_text) on the held branch); 3e5b75d loss and its 30%/70% shares measured in one unit (words) so half a table deleted keeps a rescue copy; cb6761e a templates or Trash file the start could not read goes into the backup as the file on disk, or is named as left out; 0ad97fd a held start's refused write said once, and no categories said lost; 7fd930b a run that saves nothing says so on the status line from its first save; 5342c81 a lock file another program holds a moment is tried again before the lock fails open; 3c3b644 a series turned back on from another start date or rule drops the OLD series' deleted days (exceptions) only -- days with their own text stay in the note, by the owner's decision (no new data field); 5a21fbb a list's markers changed (bullets <-> numbers, renumbering) are no words lost (strip_list_markers), so the rescue copy stays; f8818dd a merge marker "^" under a row too short to have its column is content, not an error (export, merge_map); 7b3bb72 an item typed in a TEMPLATE's checklist Add box (the template editor, and Save as template from a note) is saved with the template, and closing the editor asks about it.
INTERFACE HALF (another hand; mutants RU/RT series): 2b4e870 Ctrl+N and Ctrl+F close a picture's preview before they give the keyboard to the note under it; 93bf85e a toolbar laid out again by a resize keeps the keyboard on its button (the <Unmap> watcher asks whether the manager forgot the widget, not whether it is mapped); 83fbe3f Tab and Enter in a table keep the keyboard in it, with a separator row or with the table kept as text past MAX_DRAWN_TABLE_PX; bf4c6c5 a paste past a limited box's limit is shortened to fit, as the title's is (checklist 2,000, template name 200, etc.); 93dfe70 exporting or copying a wide table of empty cells takes milliseconds; f3a53cc a picture's frame of 10 ms or less plays at 100 ms, as browsers do.
THE CHUNKED LISTS, "1a" (a third hand; mutants RW01-RW18): 9fa6258 RowStack -- a list taller than Tk's 32,767-px canvas-window limit is built in chunk frames of N rows (EVERY=8; checklist 4, picker 32, ...); a chunk near the view stands at its true y, the others are parked at -20,000 (still mapped, so Tab reaches them); readers ask the stack where rows really are (_drawn_box, _root_y, y_of, box); used by the checklist, the template picker and editor, Settings > Templates, Recently deleted, Duplicates, Share, a calendar day's notes, History, and the calculator's history. df691da a drawn tick box paints the shared images once. 6b0ac8b the waiting restack is scheduled on the app, not on its canvas. a770cf3 remeasure() re-fits the template editor after layout when its table grows only wider. The owner chose this ("1a": lists taller than ~32,767 px are built in chunks and scroll to their end, looking the same).
Accepted by the owner, NOT findings: share codes Base64+zlib (not encryption); offline, no accounts, no Terms & Conditions; Tk 8.6 exposes no names/roles to screen readers; the zip build adopting its unpack folder; USERPROFILE missing; Trash clock far ahead; clock set back mid-session; the Settings section entries draw no keyboard ring; an over-long checklist item's row shows no way to read the rest; an animation stopping after its budget; Escape closing the preview for mouse users too; the remove that leaves a held attachment file behind; days with own text staying after a series is restarted from another date (3c3b644, the owner's "stays as now").
KNOWN OPEN LOWS (do not re-report unless you show it is worse than low): a template lost at close after a failed templates write; pasted HTML that is markup-only read whole; the paste ceiling counted in characters, not Tk indices, for astral emoji; search/find boxes and other never-saved one-line boxes take pastes of any length; stored attachment names holding ':' from Linux source runs before 66a44e3; the template editor's Add box has no "1,000 items" message (normalize_template caps silently); Windows' ~10,000-widget limit on a list of thousands of rows (pre-existing); one single row taller than 20,000 px drawn wrong in a RowStack; qa2 slower on Windows.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled; keyboard-only use works.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes, a 1,000-row checklist); a keyboard trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 25 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two rounds in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'r6d1-data-fixes', focus: `RE-ATTACK THE ROUND-5 DATA FIXES BY NAME (ce3d2e0, 498837b, 916926f, 3e5b75d, cb6761e, 0ad97fd, 7fd930b, 5342c81, 3c3b644, 5a21fbb, f8818dd, 7b3bb72). For each: a variation its own check did not try, a neighbour it broke, an unswept sibling. Ideas: the one-try read after a refusal -- a hold that ENDS mid-session (is the next read fresh, or does the run keep a stale last-good copy and later WRITE it over a newer file another process wrote?); a hold beginning mid-session (no last good read for that path?). The pending-item saves (498837b blank editor, 7b3bb72 template editor and Save as template): every way out, twice in a row, an item of only spaces, an item over 2,000 characters (cut like a paste?), an item already in the list (duplicated?), the Add box holding text while the checklist is already at 1,000 items, Undo after the item was taken (does the box come back empty and the item stay?), a template opened, the box typed, then "Use template" or Duplicate. 916926f: the turn-off through every route (editor dropdown, Save, Ctrl+S, autosave, switch note, session end) with a held save -- and the sibling the Android agent named: _write_series_owned vs _turn_off (does one branch have the takes_text logic and the other not?). 3e5b75d + 5a21fbb: can a REAL loss now go uncounted -- a paragraph deleted whose words are list markers or numbers ("1." "2." "-" "*"), a numbered list whose items are bare numbers ("1. 2024" "2. 2025"), a table whose cells are all list-marker-like ("- | - | -"), a deletion that ALSO renumbers; strip_list_markers applied to a line starting with "-1" or "2." inside prose ("2. Then we left" vs a sentence starting "2.5 kg")? 3c3b644: turned off, kept days, restarted from another date AND another rule AND back to the old date -- do the dropped exceptions come back wrongly, does a day with own text land on a day the new series skips (hidden? shown twice?), export/share/History/Find for those days. f8818dd: a "^" in the FIRST row, a column of only "^", "^" in a header, round-trip through share code, export to markdown/HTML/text and back in.` },
  { key: 'r6d2-ui-fixes', focus: `RE-ATTACK THE ROUND-5 INTERFACE FIXES BY NAME (2b4e870, 93bf85e, 83fbe3f, bf4c6c5, 93dfe70, f3a53cc). Ideas: 2b4e870 -- every OTHER shortcut that moves the keyboard to the note while a preview, a palette, the emoji picker, the find bar, a cell editor or a popup is open (Ctrl+Shift+N, Ctrl+T new table, Ctrl+K, Alt+arrows, Ctrl+Tab, F-keys, the calendar's keys, Ctrl+, for Settings): does any still leave a popup over the note with the keyboard under it? 93bf85e -- the watcher's "manager forgot it" rule: a widget pack_forget()+pack() in one breath, grid_remove() (remembered config), place_forget(), a notebook tab hidden, a Toplevel withdrawn -- does any now NOT count as put away when it is (keyboard left on an invisible widget, Space then fires it)? 83fbe3f -- Tab/Shift+Tab/Enter at every edge (first cell, last cell, a merged cell, a hidden column, a header row, the separator row, a table of one cell, a table kept as text), with a selection, after Undo; does Enter in the last row of a table near the drawn limit add a row and flip the table without losing the keyboard or the letter? bf4c6c5 -- every limited box (title, checklist item 2,000, Add box, template name 200, category name, cell editor?, rename dialogs): a paste of exactly the limit, limit+1, a paste with CRLF on Windows (_clipboard_text reads CF_UNICODETEXT where CRLF counts 2 -- read the code and say what Windows does), a paste over a selection, a paste of astral emoji at the cut (surrogate split?), a paste of combining marks at the cut, a paste into a box already full -- is the person told the paste was shortened? 93dfe70 -- the fast path for empty cells: a table of empty cells with ONE non-empty cell far right, cells of only spaces/NBSP/zero-width, merged cells, does export/copy give the same text as before the fix? f3a53cc -- delays 10, 11, 0, None, negative in a GIF/APNG/WebP; a mix of 0 and 100.` },
  { key: 'r6d3-chunked-lists', focus: `RE-ATTACK THE CHUNKED LISTS (1a: 9fa6258, df691da, 6b0ac8b, a770cf3 -- RowStack) on EVERY list that uses it (checklist, template picker, template editor, Settings > Templates, Recently deleted with Show more, Duplicates, Share with Show more, a calendar day's notes, History, the calculator's history). Ideas: Tab and Shift+Tab across a chunk boundary and into a PARKED chunk (does the focused row come into view, or is the keyboard on a row at -20,000 the person cannot see? does Space then act on an invisible row?); the arrow keys / Home / End / PageUp / PageDown; the mouse wheel and the scrollbar dragged fast end to end; the window resized, maximised, made tiny while scrolled to the middle; a theme switch while scrolled (do parked chunks get recoloured -- track_theme vs configure -- or show the old theme when they come into view?); Sharp text at 150% and 225% (does the chunk height math use px()?); rows added, deleted, moved (Alt+Up/Down across a chunk boundary), Undo of each, at the first and last row of a chunk; a checklist row edited so it wraps to many lines (grows taller) in a parked or standing chunk -- do rows overlap or leave gaps?; find-in-note or Ctrl+F while a long checklist is open; the note switched or deleted while a restack is pending (6b0ac8b: after() on the app -- does it run against destroyed widgets, TclError in the crash log?); the <Unmap> put-away watcher when a chunk is parked/unparked (does parking count as "put away" and steal the keyboard?); cost: open a 1,000-row checklist, 1,000 templates, Share with 2,500 notes -- same-run comparison with a 100-row list, and widget counts (Windows' limit); the Android agent's named twin: the desktop checklist's widget cost per row. Take photographs inside the container at the list's start, middle and end, in dark and light, and LOOK at them (gaps, overlaps, a row drawn twice, a ring on the wrong row).` },
  { key: 'r6d4-round5-gaps', focus: `WHAT ROUND 5 SAID IT DID NOT COVER. Read ${R5GAPS} (every section and the skeptic's not_checked). Probe the gaps most likely to hide a defect that matters, at least six, and say which you skipped and why. Above all: (1) a session-only export recorded as the "last export" when the app closes within 100 ms of it finishing (_settle_background_work_at_close) -- does the backup reminder then lie?; (2) the held-run export of a whole attachments folder, and importing that backup later (duplicate or orphan files?); (3) Delete permanently / Empty Trash on a held notes run (the spare set built from the session's notes only -- can it delete a file an unread note uses?); (4) the picture preview during a held run and at a sign-out; (5) the shipped build's Python and tkinter.unbind: the machine's Python is 3.13 -- read NoteOrganizer.spec / docs/RELEASE_WINDOWS.md and the code that unbinds <Escape> and say whether any build path could use an older Python where unbind wipes every root binding; (6) Shift+F10's 5-minute poll expiring, two overlapping polls, a menu command that opens a question while the poll runs; (7) the template editor popup's own re-lays and the emoji picker scanned for watcher misfires; (8) the calendar's month switch with the keyboard on a day; (9) Return on the picture preview's Close button (does nothing by code reading -- is that a trap for a keyboard user?); (10) message_shown's bound in characters, not pixels, at 225%.` },
  { key: 'r6d5-round5-seams', focus: `THE SEAMS BETWEEN THE ROUND-5 FIXES, made by three hands (data, interface, the chunked lists) plus late fixes, merged afterwards; none of the hands saw the others' code. Cross them: the chunked checklist x the Add box pending item (is the Add box inside a chunk? parked? does a pending item survive a restack, a theme switch, a note switch?); the chunked template editor x 7b3bb72's pending item x the editor's Save/close question x a remeasure (a770cf3) -- does the question appear twice or not at all?; the chunked checklist x the paste shortening (bf4c6c5) x the 2,000 cut x a row that grows taller; the chunked lists x the <Unmap> watcher's new rule (93bf85e) -- does a parked chunk or a list rebuilt into chunks move the keyboard; the chunked Recently deleted x Empty Trash / Delete permanently on a held run; the chunked Share list x a held notes run; list markers (5a21fbb) x a table x the rescue copy x Undo; 3c3b644's dropped exceptions x Duplicate x Save as template x export x the calendar's chunked day list and History; the held settings one-try read (ce3d2e0) x the theme switch recolouring parked chunks x Sharp text; Tab in a table (83fbe3f) x a checklist below the table (does Tab leave the table into the chunked checklist correctly?). Find an ordinary sequence where two fixes, each right alone, together lose work, crash, mislead, trap the keyboard, or open something unasked.` },
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
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store). This is ROUND 6: round 5 found 15 distinct desktop defects (1 high, 8 medium, 6 low), and they were fixed by three separate hands (data; interface; the chunked lists) plus three late fixes, then merged; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${FIXES}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the desktop app's round-6 break-it findings in the final audit of Note Organizer. Five auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (only through the docker command with the inner timeout, or a Windows pure-Python probe under the same isolation), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open low, whether an earlier fix already covers it (git log 8fbb831..2a17ad7 for round 5), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`desktop round 6: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:desktop', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
