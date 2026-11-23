// The final audit: run wf_58c11657-d70, started 2026-10-28 12:21 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round5-desktop',
  description: 'Final audit wave 1, round 5 (desktop): 6 read-only break-it agents re-attack every round-4 fix by name (data half and interface half), round 4 gaps and the seams between the two hands; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '6 desktop finders: the round-4 fixes by name, their seams, and round 4\'s gaps' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r5'
const SMOKE = '<scratchpad>\\wave1\\r1\\_smoke\\probe.py'
const R4GAPS = '<scratchpad>\\wave1\\r4\\not_covered.txt'
const R4SUMMARY = '<scratchpad>\\wave1\\r4\\summary.txt'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- NEVER run qa*.py, test_*.py or note_organizer.py inside a repository, and never run the app on the Windows desktop (it would open windows on the owner's screens). Never call os.startfile on a real file. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- DOCKER HYGIENE (round 4 left 13 hung containers running for hours): every docker run uses --rm AND puts the timeout INSIDE the container, so the container itself ends: -c "timeout -k 10 240 xvfb-run -a python /work/probe.py". A probe that may wait on a dialog must answer or stub it (app.show_info / show_warning / ask_yes_no / _themed_dialog). Never start a container without that inner timeout, and never docker kill/stop/rm anything.
- The machine is busy (other suites run in parallel): a timing claim needs a same-run comparison (with and without, or small and large), never one absolute number.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val1, checked out; do not switch branches). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, docs/ARCHITECTURE.md, and docs/ISSUES_LOG.md -- its two newest stories ("Round four: days kept but not used, loss counted in words, and a run that saves nothing" and "Round four: what a click put away, and what a screen can draw") describe the round-4 fixes.
HOW TO RUN THE APP SAFELY: only inside the Linux test image, in a throwaway copy. Put a probe script in SCRATCH_DIR and run (Git Bash):
  MSYS_NO_PATHCONV=1 docker run --rm --entrypoint sh -v "D:/Projects/NoteOrganizer:/repo:ro" -v "<SCRATCH_DIR with forward slashes>:/work" noteorg-linux-ci -c "timeout -k 10 240 xvfb-run -a python /work/probe.py"
A working example is ${SMOKE}: it copies note_organizer.py and noteorganizer/ to /tmp/app, chdirs there, imports note_organizer as NO and builds NO.NoteOrganizer(). Seed notes by writing /tmp/app/notes_data.json BEFORE building the app. qa/qa*.py and qa/_qa_support.py show how the suite drives the app (read for technique; never run them on the host).
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE the import (assert that first). Windows-only behaviour (a file held by ANOTHER process with share mode 0 via ctypes CreateFileW in a child process, NTFS names) needs such a probe.
`

const FIXES = `
THE ROUND-4 FIXES (all on audit/d-val1; 'git log --reverse --format="%h %s%n%b" 3a6a1c7..audit/d-val1' lists them with their reasoning and mutants). Round 4's findings, one line each: ${R4SUMMARY}.
DATA HALF (mutants DR41-DR56, DR31/DR32/DR08 re-aimed), one hand: b26394c days a turned-off repeat keeps steer nothing while the note does not repeat (core.recurrence.effective_note returns the note itself unless is_recurring; day_as_kept answers the keep-or-drop question; a one-off ignores kept exceptions; load_note shows effective_note only for a day; calendar ✎ marks and chip only for a series). 9c787fc loss measured as min(text_lost span, words_lost) in core.model (_lost, words_lost counts each vanished word with its space; _without_padding removed): a column added/removed or a list renumbered no longer replaces the rescue copy (_prev); _turn_off_rescue_copy(takes_text) -- a turn-off whose own save also clears text keeps the newest text. a5127ab _flush_autosave: with no note and no tab open, the blank editor's content is still flushed (Ctrl+N, a sign-out, closing). 8f48c81 settings.json read with retries at start; a read that fails with OSError is NOT damage (nothing copied aside; settings held for the run, TRASH_WINDOW_UNKNOWN, the Trash cleanup waits); later refusals use the last good read (cache keyed by path in storage); the migration hold includes settings.json; _notes_file_unread() is the one question for "the notes file was not read"; a held run says "Nothing is saved in this session" once, then the status line; export packs the session's notes and says so ("Backup of this session saved"), refusing only when nothing is in memory; import is refused ("Import after reopening"); no dialog at a Windows sign-out (_ending_session); held Trash/templates named in the start notice. 4760c5f the export probe-opens each attachment and leaves out a file another program holds, naming it ("Export complete, but not all of it").
INTERFACE HALF (mutants RU01-RU32; RT06 RT07 RT09 RT12 RT19 re-aimed), another hand: bb9db36 an animated PNG's frame delay made whole milliseconds (_frame_delay); a preview failing half-built is taken down and its file released; removing an attachment releases a preview still reading it. 4438417 the picture preview takes the keyboard on Close however opened; Tab/Shift+Tab cycle its two buttons only. 35ded8b a table is also judged by its drawn pixel height (MAX_DRAWN_TABLE_PX 30,000 via _grid_row_height and cell_display_lines); the cell editor's window is capped at that size and scrolls. 172f905 Save as template's box keeps 200; dialogs.one_line() draws long/multi-line names on one line (_fit_title, _fit_name with NAME_SHOWN_CHARS 400, Settings > Templates, the status line, the hover card's attachment names, questions quoting names); message_shown() caps any dialog message at 12,000 characters / 300 lines keeping start and end; a length-safe _name_and_type (dotted İ). 620fcb0 rows pack their right-hand buttons first (template row, category row, statistics pill, the picture preview's header). 9cab8f3 ONE watcher: bind_all("<Unmap>") -> _part_put_away -> _keyboard_off_part: when a widget its geometry manager forgot held the keyboard, the keyboard goes to the control clicked within 1 s, else tk_focusNext; deferred two idle rounds; Settings records the keyboard before the find bar or a cell editor closes; a notebook tab switch moves the keyboard off a hidden widget. 780cf21 Shift+F10 / App / Menu in a cell editor opens the cell's menu at the cell (_grid_menu_from_keys); the keyboard returns to that cell or the nearest (_grid_keyboard_back, polling 100 ms up to 5 min); the colour palettes are placed by _place_grid_palette (_place_mini_popup) with no <FocusOut>. 5159491 dialogs._scrolling_rows: the template editor's and the picker's growing part is a viewport capped to the window; popups re-placed when they grow (a <Configure> on the popup), never past the window's bottom, skipping no-op moves. 9f07d55 the template preview redrawn only when its tables change; a paste over a selection in a _limit_entry box weighed whole first (<<Paste>> binding); after a quiet save at a cancelled sign-out the editor points at what it wrote.
Accepted by the owner or already in her test plan, NOT findings: the earlier accepted items (zip build adopting its unpack folder, USERPROFILE missing, Trash clock far ahead, clock set back mid-session); the Settings section entries draw no keyboard ring; a checklist paste over 2,000 refused whole while the title's box shortens a paste (flagged for her); an over-long checklist item's row shows no way to read the rest (by design); an animation stopping after its budget; Escape closing the preview for mouse users too; the remove that leaves a held attachment file behind (deliberate trade-off in code).
KNOWN OPEN LOWS (do not re-report unless you show it is worse than low): a template lost at close after a failed templates write; pasted HTML that is markup-only read whole; the paste ceiling counted in characters, not Tk indices, for astral emoji; search/find boxes and other never-saved one-line boxes take pastes of any length; stored attachment names holding ':' from Linux source runs before 66a44e3 (shown missing; no migration); the category dropdown and bulk-category popup with ~200 categories run past the window (DO report it if it traps the keyboard or loses work).
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled; keyboard-only use works.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes); a keyboard trap. low = cosmetic or far-fetched.
Already decided, NOT findings: share codes are Base64+zlib, deliberately not encryption; offline, no accounts, no Terms & Conditions; Tk 8.6 exposes no names/roles to screen readers; Pillow internals out of scope unless the app feeds them something it should have refused.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 25 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two rounds in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'r5d1-data-fixes', focus: `RE-ATTACK THE ROUND-4 DATA FIXES BY NAME (b26394c, 9c787fc, a5127ab, 8f48c81, 4760c5f). For each: a variation its own check did not try, a neighbour it broke, an unswept sibling. Ideas: effective_note now returns the note itself for a one-off -- EVERY reader of overrides/exceptions (search, Find, the card preview, History, export to text/markdown/html, the share code, Duplicate, the dirty comparator, statistics, reminders, the calendar's day list and day mode) must agree that kept days are inert; a turn-on later must bring the kept days back exactly; a share update or import arriving for a turned-off note with kept days. words_lost: can a REAL loss now go uncounted -- deleting a paragraph that repeats words present elsewhere in the note (Counter subtraction: "the the the" kept elsewhere), moving text vs deleting it, deleting one copy of a duplicated paragraph, a note of one huge repeated word, CJK text with no spaces, a table whose deleted row's words appear in other rows? Is min() ever the WRONG choice (words_lost far under text_lost on a real deletion)? takes_text on every turn-off route (editor dropdown, Save, Ctrl+S, autosave, switching notes, the session end). The blank-editor flush: every way out (Ctrl+N, click a note, close, sign-out, Settings, calendar, import, a share code applied) and twice in a row; does it ever make an empty or duplicate note? Held settings: a setting changed during a held run (theme, Trash window, sort, Sharp text) -- written later over the file once it frees? A cache keyed by path after a data-folder change; settings held at start + the welcome note + the first-launch date; the held run's single message vs a second held file found later; export of a session with attachments while the notes file is held.` },
  { key: 'r5d2-attachment-fixes', focus: `RE-ATTACK THE ROUND-4 ATTACHMENT FIXES BY NAME (bb9db36, 4438417, 620fcb0's preview header, 172f905's attachment labels and _name_and_type). Ideas: _frame_delay with delays of 0, None, negative, huge (1e9), NaN, a float string; an APNG with a default image, with disposal/blend ops, 1-frame APNG, a WebP animation, a GIF with per-frame delay 0; the half-built teardown -- is the file released on EVERY failure path (decoder error mid-frames, MemoryError, the window closed while decoding, the attachment deleted while the preview is open, two previews of the same file opened fast); does a released preview leave after() callbacks running against destroyed widgets (TclError storm in the crash log)? The preview's keyboard: opened by click, by Space/Return on the name, by Ctrl+click; Tab cycling with Open externally disabled or absent; the keyboard's return when the note was switched/deleted while the preview was open; Escape with a dialog over the preview. Labels: RTL names, zero-width joiners, combining marks at the cut, astral characters, a name that is only a type (".png"), a 400-char name with no dot, the hover card listing 200 attachments.` },
  { key: 'r5d3-keyboard-fixes', focus: `RE-ATTACK THE ROUND-4 KEYBOARD FIXES BY NAME (9cab8f3 the <Unmap> watcher, 780cf21 the cell menu by key, 4438417 the preview's keyboard, the tab-switch move) as a keyboard-only user and as a mouse user they might have broken. Ideas: the watcher is bind_all on <Unmap> -- does it misfire when a part is forgotten and re-packed in the same breath (list rebuilds, the reminder bar, the find bar re-laid, Settings sections, day mode, the toast), stealing the keyboard from where the person is typing? Does it ever move the keyboard INTO a widget that then receives keys meant elsewhere (the "click within 1 s" target being stale: a timer-driven hide such as a toast or autosave status 0.9 s after a click on a delete button)? What does tk_focusNext land on when the next control is a destructive button (Delete, Empty Trash) and the person presses Space/Enter next? Cost: count watcher calls during heavy operations (1,000-note list refresh, Settings open/close, calendar month switch, a 400-row table drawn) -- a cheap early return is fine, real work per unmap is not. The cell menu: Shift+F10 with no cell editor, on a merged cell, in a header cell, after the table was converted to text by MAX_DRAWN_TABLE_PX; the 5-minute polling of _grid_keyboard_back -- what if the note is switched, the table deleted, Settings opened, or the menu's command opened a dialog that edits the note while it polls (does it later open a cell editor in another note or steal the keyboard from a dialog)? The palettes without <FocusOut>: do they close on every way out (click elsewhere, Escape, the window losing focus, the note switched)?` },
  { key: 'r5d4-limit-fixes', focus: `RE-ATTACK THE ROUND-4 LIMIT, DRAWING AND POPUP FIXES BY NAME (35ded8b, 172f905, 5159491, 9f07d55, 620fcb0). Ideas: MAX_DRAWN_TABLE_PX at 225% scale with Sharp text on (px() and font sizes grow), a table just under 30,000 px that grows past it by one edit in the cell editor (does it flip to text mid-edit and lose the edit or the caret?), and back again by deleting; _grid_row_height vs the real row height (headers, a bigger text size setting) -- can a table still pass 32,767 px while judged under 30,000?; the cell editor's width cap with emoji measured as wide; one_line on a name of 3,000 lines that is ALSO a duplicate of another template (do the two read the same and can the person tell which they delete?); message_shown keeping the end -- a question whose answer buttons depend on text in the cut middle; the status line's 1,000-character one_line hiding the important end of a message ("... not saved")? _scrolling_rows: Tab into rows scrolled out of view (are they brought into sight?), the wheel over a Text inside it, a window resized smaller while the editor is open, the editor at a 600 px tall window with Sharp text at 150%; popups re-placed on <Configure> -- any feedback loop (a popup whose size depends on its position) that spins the CPU? The template preview's redraw skip -- a change that alters only the table's STYLE or a merged cell: does the preview go stale? The <<Paste>> weigh -- a selection made by keyboard, a paste via the right-click menu, middle-click on Linux.` },
  { key: 'r5d5-round4-gaps', focus: `WHAT ROUND 4 SAID IT DID NOT COVER. Read ${R4GAPS} (every section and the skeptic's not_checked). Probe the gaps most likely to hide a defect that matters, at least five, and say which you skipped and why. Above all: (1) on WINDOWS (pure-Python, isolated, core only): settings.json, trash.json, templates.json and an attachment held with share mode 0 by a child process at start, mid-session and at the export, released after 1 s and 5 s -- does the core (storage, paths, the export's worker logic if it can run without tkinter) do what the round-4 data story promises? (2) the round-4 interface half's Windows-only claims: anything proven only on X11 (32,767-pixel limits behave differently on Windows -- read the code paths and say what Windows would do); (3) Settings lists taller than 32,767 px (1,000 templates, 1,000 categories) and the category dropdown / bulk popup with 200 categories -- crash, hang, or only cosmetic?; (4) the data-half gaps round 4 listed (two app processes, the notes lock's fail-open, DST in History, the welcome note re-shown, migration cases).` },
  { key: 'r5d6-round4-seams', focus: `THE SEAMS BETWEEN THE ROUND-4 FIXES, made by two hands in parallel and merged afterwards (the data hand never saw the interface hand's code and vice versa). Cross them: the held run's single message and status line x message_shown / one_line (is "Nothing is saved in this session" ever cut away, or hidden behind a later status?); the held run x the <Unmap> watcher x a session end x the template editor's quiet save (does the quiet save try to write a held templates file, and what does it say?); kept days inert x the calendar marks x Save as template x Duplicate x export; words_lost x a table flipped to text by MAX_DRAWN_TABLE_PX x the cell editor's cap (does an edit in a capped editor ever count as a loss, or a real loss in a table drawn as text go uncounted?); the blank-editor flush x the watcher moving the keyboard x a delete from the keyboard (Delete, then type: where do the letters go, and are they saved?); the export's left-out attachment x a long attachment name x message_shown; the turn-off's takes_text x the template preview x a share update arriving; the cell menu by key x the rescue copy (Rows > Delete via keyboard: is a copy made?); Settings' recorded keyboard x a held settings file x the tab switch. Find an ordinary sequence where two fixes, each right alone, together lose work, crash, mislead, trap the keyboard, or open something unasked.` },
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
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store). This is ROUND 5: round 4 found 23 desktop defects (6 high, 8 medium, 9 low) and they were fixed by two separate hands (one did the data fixes, another the interface: attachments, keyboard, limits, drawing) and merged; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${FIXES}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the desktop app's round-5 break-it findings in the final audit of Note Organizer. Six auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (only through the docker command with the inner timeout, or a Windows pure-Python probe under the same isolation), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open low, whether an earlier fix already covers it (git log 3a6a1c7..audit/d-val1 for round 4), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`desktop round 5: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:desktop', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
