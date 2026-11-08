// The final audit: run wf_badb6761-7bc, started 2026-10-30 08:47 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round9-desktop',
  description: 'Final audit wave 1, round 9 (desktop): 5 read-only break-it agents re-attack every round-8 fix by name (the critical homes fix and the tools, data, interface), round 8 gaps and the seams with the phone; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '5 desktop finders: round-8 data fixes, interface fixes, machine safety, round 8 gaps, the seams' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r9'
const SMOKE = '<scratchpad>\\wave1\\r1\\_smoke\\probe.py'
const R8GAPS = '<scratchpad>\\wave1\\r8\\not_covered.txt'
const R8SUMMARY = '<scratchpad>\\wave1\\r8\\summary.txt'
const R8FINDINGS = '<scratchpad>\\wave1\\r8\\findings'
const R8FIX = '<scratchpad>\\wave1\\r8fix'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project, and on 2026-10-29 a test run took the owner's whole computer down -- these are not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Do not run git commands that change anything (git log/show/diff/grep are fine).
- Write ONLY inside your own folder: SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder.
- NEVER run qa*.py, test_*.py, tools/run_tests.py, tools/mutate.py, a qa/story_*.py script or note_organizer.py inside a repository, and never run the app on the Windows desktop (it would open windows on the owner's screens). Never call os.startfile on a real file. No gradle, adb, emulator. No network. No installing anything. If a command is refused, do not try another spelling -- note it under not_covered.
- THE LINUX IMAGE HAS ONE DOOR, and you use it for every run of the app: write your probe as a .py file inside SCRATCH_DIR and run
    py ${DESKTOP}\\tools\\linux_ci.py --probe <SCRATCH_DIR>\\<name>.py
  NEVER a docker command of your own (no docker run/exec/kill/stop/rm): a killed docker client leaves its container running. The door takes this machine's one heavy-job turn: while another run holds it, yours prints "machine : waiting for ..." and waits. So call it with the Bash tool's timeout at 600000 ms; if the call times out while waiting, nothing was started -- wait and try once more later, and if it still waits, note it under not_covered. Exit 75 means it gave up waiting. Exit 124 is your probe hanging past its 600 s limit (inside the container: answer or stub every dialog -- app.show_info / show_warning / ask_yes_no / ask_yes_no_cancel / _themed_dialog). Only one door call of yours at a time. Keep each probe short (well under 600 s): many small checks in one probe are better than many probes, since every run waits its turn behind the other auditors'.
- Every Python probe on WINDOWS begins with these two lines, before any other import (the ceiling only, no turn: such probes must be small):
    import sys; sys.path.insert(0, r'${DESKTOP}\\tools'); import guest; print(guest.settle(512, 512, heavy=False))
  and no probe, on either side, builds a fixture whose size comes from a value a bug could make huge (a cap read from the code, a count from a file): sizes are literal numbers you chose, at most 2,000 rows / 5 MB.
- The machine is shared: a timing claim needs a same-run comparison (with and without, or small and large), never one absolute number.
- Do not fix anything. Find and prove defects, and report them.
`

const HOW = `
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val1, checked out; do not switch branches). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, docs/ARCHITECTURE.md, and docs/ISSUES_LOG.md -- its stories "Round eight: a day reset that came back, and what one copy keeps", "Round eight: words said beneath an Undo, and Enter held on every box" and "The test that took the computer down" (with its round-seven and round-eight follow-ups) describe the round-8 fixes.
HOW TO RUN THE APP: only through the door in the rules. Inside the container your probe runs in a fresh throwaway folder that already holds note_organizer.py, noteorganizer/, _qa_support.py and guest.py (so "import note_organizer as NO" works there), the repository is mounted read-only at /repo, and SCRATCH_DIR is /work (read-write: write outputs and photographs there; read your own seed files from there). Seed notes by writing notes_data.json in the current folder BEFORE building NO.NoteOrganizer(). ${SMOKE} is a working older example (it copies the app itself to /tmp/app; either way works). qa/qa*.py and qa/_qa_support.py show how the suite drives the app (read for technique; never run them on the host). For a photograph inside the container, grab the app's own window (PIL ImageGrab under Xvfb, or xwd of its window id) into /work and LOOK at it.
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with the guest lines first and APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE importing the app's code (assert that first).
`

const FIXES = `
THE ROUND-8 FIXES (all on audit/d-val1; 'git log --reverse --format="%h %s%n%b" 81dae88..HEAD' lists them with their reasoning and mutants). Round 8's findings, one line each: ${R8SUMMARY}; one JSON per finding in ${R8FINDINGS}. The fixers' briefs, draft test rows, probes and photographs: ${R8FIX} (and its photos2 / walk_photos folders under the scratchpad).
THE CRITICAL (bcf82a9): test_data_safety.py started the app unseeded under the owner's environment, so every Windows run of run_tests/mutate/run_coverage copied %APPDATA%\\NoteOrganizer (the old .exe's notebook) into the suite's temp folder. guest.settle() now points APPDATA, LOCALAPPDATA and XDG_DATA_HOME at empty folders of the run's own (a marked scratch, removed at exit, swept when the run dies; a child keeps its parent's homes only while APPDATA is inside them; PYTHONUSERBASE keeps the person's packages; USERPROFILE untouched), and check_guest item 6 proves it with a stand-in notebook. test_data_safety is seeded before initialise().
DATA HALF (947e9d3, ae6efe2; mutants DR111-DR123, DR40 DR93 DR97 DR98 DR101 re-aimed): spend_series_days -- once a note repeats as its copy's series (_repeats_as), the copy's DAY_FIELDS are removed, at the end of every _days_back_from_copy and in save_current_note after the repeat is written; shared_update_changes compares BOTH sides without _prev; comments_kept_by_copy (the comments whose loss would be larger stay, by _lost) in the ordinary comments_alone save and the turn-off's; _turn_off_rescue_copy keeps an unspent update's copy (update_copy) whole, adding date/recurrence/days where it lacks them; _import_asking lowered after the merge is saved, before "Import complete" and in the error path; copy_replaced_by_restore weighs ANY style on words held in the copy's but not identical (styles_kept); announce_startup_changes keeps an import's word (said=True, temp_dir dropped) on a start that cannot read the notes; _settle_backups_at_session_end names copied/temp_dir for a worker held past the join; the template editor's Save takes back template_not_kept. Written down, NOT fixed: 0.12.0 notes turned off and on again with a rule written another way, or a day skipped since.
INTERFACE HALF (51f0c44, 7391897, 9ff0ab3, 503d025; mutants RX01-RX16): a title paste turns only line breaks/tabs into single spaces, keeping edge and double spaces; _offer_on_banner and _show_words_beneath -- a box's words go on a second banner beneath an Undo or error banner, and the autosave (set_status(reassurance=True), "Note updated") writes over neither for TOAST_MS; every Enter binding that acts asks _enter_repeats (list activate, calendar open, the Add boxes, the category/name/rename/year boxes, the date fields); "Checklist full" said once per note per words per session (_waiting_said), and the close asks only about notes still in the list.
MACHINE SAFETY (33402df; mutants GT01-GT23 in copies, by scratchpad wave1\\r8fix\\mutant_tools.py): site/tools/check_demo.py is the door to the browser walk (settles, job object, end_others, a marked scratch through guest.DOOR_ENV, 900 s); check_demo.mjs refuses without the door, timeouts on its messages; tools/msix/sandbox_test.ps1 refuses outside Windows Sandbox; check_guest walks methods, nested functions, lambdas, class bodies, multiprocessing/pools/asyncio/pty/runpy/webbrowser/importlib, 'with Popen', heavy=False starting a suite, and scripts in other languages (items 7-8, 28 self-cases); linux_ci mounts a read-only COPY of what git tracks (git ls-files --cached --others --exclude-standard) with --network none and a 512 MB tmpfs /tmp; a 3,072 MB disk floor with a watcher (exit 74) on Windows; the sweep clears read-only files before removing and re-marks what resists.
Accepted by the owner, NOT findings: share codes Base64+zlib (not encryption); offline, no accounts, no Terms & Conditions; Tk 8.6 exposes no names/roles to screen readers; the zip build adopting its unpack folder; USERPROFILE missing; Trash clock far ahead; clock set back mid-session; the Settings section entries draw no keyboard ring; an over-long checklist item's row shows no way to read the rest; an animation stopping after its budget; Escape closing the preview for mouse users too; the remove that leaves a held attachment file behind; days with own text staying after a series is restarted; words left in a full list's box waiting for the note and asked about at close (said once now).
KNOWN OPEN LOWS (do not re-report unless you show it is worse than low): a template lost at close after a failed templates write; pasted HTML that is markup-only read whole; the paste ceiling counted in characters, not Tk indices, for astral emoji; search/find boxes and other never-saved one-line boxes take pastes of any length; stored attachment names holding ':' from Linux source runs before 66a44e3; Windows' ~10,000-widget limit on a list of thousands of rows; qa2 slower on Windows; the one rescue-copy slot learning "what the series was"; 0.12.0 notes turned off/on with a rule written another way or a day skipped since (r8d1 0120-days); a day's save and the repeat-off suffix said only on the status line, out of sight on the note page; a .part file an import was writing at a session end not named in its word; the gate's remaining blind spots the tools fixer named (a thread lambda started before settle in a module that settles at top level; 'with Class():' not following __enter__; script guards checked as text; a light runner judged by the first .py its start names); Linux has no job object; the disk floor on Windows only.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled; keyboard-only use works; and nothing the project's own tools do can harm the owner's computer or her data.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action; a test tool that can take the computer's memory or disk or its other windows, or reach the owner's own notebook. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes; a test tool that can leave processes or gigabytes behind. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes, a 1,000-row checklist); a keyboard trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 15 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two rounds in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'r9d1-data-fixes', focus: `RE-ATTACK THE ROUND-8 DATA FIXES BY NAME (947e9d3, ae6efe2). For each: a variation its own check did not try, a neighbour it broke, an unswept sibling. Ideas: spend_series_days -- every road that makes a note repeat as its copy's series again (Restore previous of a series' own copy over a turned-off note; an import's Update that brings the repeat back; a Trash restore; Undo of a turn-off in the editor; a duplicate of a turned-off note turned on) -- which spend, which leave the copy's days until the next read, and can a day reset in between come back? A copy whose days were spent, then the repeat turned off again: does the new turn-off copy hold the days, and does Restore previous bring the series back whole? shared_update_changes with both copies stripped: an incoming note whose ONLY difference is its rescue copy (should it read as unchanged? does Update then drop a copy only the backup held?). comments_kept_by_copy: equal losses, whitespace-only comments, comments that differ by one word, a CJK comment (words_lost vs text_lost), and both branches (ordinary save, turn-off). _turn_off_rescue_copy keeping an update's copy: an update's copy that IS spent but holds a category the note changed since; a held save while the turn-off waits; days added to the kept copy that the note no longer has. The Import complete flag: a session end during "Import failed", during the questions of a second import started from the first's dialog. styles_kept: a note whose body is the copy's body plus trailing whitespace; paragraphs only; a restore when the note is empty. The unread start's said=True word: a third start, still unreadable; a settings.json another program writes with said=True and copied names that are real files in use; the held worker's word when the session does not end after all.` },
  { key: 'r9d2-ui-fixes', focus: `RE-ATTACK THE ROUND-8 INTERFACE FIXES BY NAME (51f0c44, 7391897, 9ff0ab3, 503d025; read ${R8FIX}\\testplan_rows_ui.txt and the fixer's photographs in the scratchpad's r8ui\\photos2). Ideas: the title paste keeping edge spaces -- a paste of only spaces, a paste with a tab inside a word, a paste at the cap with trailing spaces (fitRow/_limit_entry counting), a paste replacing a selection that ends in a space. The second banner beneath an Undo -- two box messages in a row, a message while the Undo banner is being dismissed, a theme switch while both stand, a window resized narrow (does the lower banner cover a control the person needs, or the find bar?), keyboard focus (does the banner take it?), a message beneath an ERROR banner that has no Undo. set_status(reassurance=True) -- a save that carries news within TOAST_MS of a box's words (is the news kept or lost?), the status line on a narrow window. _enter_repeats on every binding -- a quick double Enter (two real presses 100 ms apart) still acting twice where it should; Enter after the app regains focus with the key held from another window; Shift+Enter, KP_Enter, Ctrl+Enter on the same boxes; the year box's own validation; the date fields' autosave. _waiting_said -- the same words in two notes; words typed, removed, typed again; a note duplicated with waiting words; a Trash restore of the note in the same session (said again?); the close question after a note's words were added somewhere else.` },
  { key: 'r9d3-machine-safety', focus: `THE OWNER'S COMPUTER AND HER DATA, NOT THE APP. Re-attack round 8's machine-safety fixes by name (bcf82a9 homes; 33402df the door, the gate, the Linux copy, the disk floor, the sweep). Ideas: guest.own_homes -- any runner or tool that runs app code WITHOUT settle (check_guest's walk vs dynamic imports, scripts in site/tools, the Android repo's tools/desktop_guest.py and its fixture makers, a story script's child), a child that unsets HOMES_ENV, a runner that sets APPDATA itself after settle; PYTHONUSERBASE pointing at a folder the run then writes into; the homes folder removed at exit while a child still writes; USERPROFILE left as it is -- list every tool that runs the BUILT exe or a frozen path (sys.frozen) and would therefore reach C:\\Users\\<name>\\Note Organizer. The browser door -- the .mjs's refusal is a text guard: can it be started without the door by another route (npm, a .bat, the site build)? end_others on a process tree that spawned outside the job (Edge's crashpad, a broker); the 900 s limit vs a real slow machine. The disk floor -- the watcher's interval vs a test writing fast; a floor read on the wrong drive (TEMP on C:, the repo on D:); a run started on D: with C: full. linux_ci's copy -- untracked-but-not-ignored files that hold data (a notes_data.json someone forgot to ignore?), the copy's own size and where it is written (C: temp), symlinks in the tree, the git mount; --network none vs anything in the suite that needs it. The sweep's re-marking -- a folder the sweep cannot delete and re-marks forever (growth?). And the 26 unmarked noteorg-gate-* folders the tools fixer left: is there any other way a gate run leaves unmarked folders now? Read only for the owner's data; for tools, run only the gate (py tools/check_guest.py through the door is NOT needed: it is a static gate you may run on Windows) and probes through the Linux door.` },
  { key: 'r9d4-round8-gaps', focus: `WHAT ROUND 8 SAID IT DID NOT COVER. Read ${R8GAPS} (every section and the skeptic's not_checked), and the fixers' own confessions in the commit bodies (git log 81dae88..HEAD) and in ${R8FIX} (the briefs say what each fixer was asked). Pick the gaps most likely to hide a defect that matters (data loss, crash/freeze, a trap, harm to the owner's computer) and probe them -- at least five, and say which you skipped and why. Include: commits 1-3 of the interface fixer were never run on their own (does any intermediate state matter? -- it does not ship, so only if a later commit relies on an earlier one's half-change); the Linux full suite from the MAIN checkout under the new copy (the integrator runs it; read what could differ from a worktree); a real held key on Windows (simulated only); the sandbox guard never proven inside Windows Sandbox (read the .wsb and the guard: will the real sandbox run still pass?); the comments-alone rule on the turn-off road with a held save; the said=True word read by an OLDER build (a downgrade: does the older start loop or misread it?).` },
  { key: 'r9d5-round8-seams', focus: `THE SEAMS BETWEEN THE ROUND-8 FIXES, made by four hands (the session's critical and data fixes; interface; machine safety; the phone's mirror) and merged afterwards. Cross them: the second banner x the import's messages (an import's "Import complete" while a box's words stand beneath an Undo); _waiting_said x the close question x a session end; spend_series_days x the interface's held Enter on a date field that turns a repeat on (one save or two?); styles_kept x the title paste keeping spaces; the homes x the story scripts' own APPDATA (do the stories still photograph a seeded notebook, or now an empty one?); the disk floor x mutate.py's many copies; linux_ci's copy x the Android repo's desktop_guest (which imports the desktop's guest from D:\\Projects\\NoteOrganizer). And PARITY with the phone's round 8 (${ANDROID}, git log 4557f60..HEAD; days_cases.json was rebuilt from the desktop and has 37 cases): replay the desktop's own core (isolated, as in the rules) and the phone's Kotlin rule on shapes NOT in the 37 cases -- spend on the roads each app has that the other lacks (the phone spends in updateNote, the desktop in save_current_note; restorePrevious/applyUpdate spend on neither until the next read), comments_kept_by_copy with the phone's lost() vs the desktop's _lost on CJK and astral text, a title paste with CR LF on both (the phone's PyText.split), Enter held vs the phone's IME. A disagreement that changes a note travelling between them is high.` },
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
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store). This is ROUND 9: round 8 found 21 distinct desktop defects (1 critical, 2 high, 3 medium, 15 low after the skeptic, plus 4 duplicates), and they were fixed by three separate hands (data; interface; the machine-safety tools), then merged; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${FIXES}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the desktop app's round-9 break-it findings in the final audit of Note Organizer. Five auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (only through the door in the rules, or a Windows pure-Python probe under the same isolation and the guest lines), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open low, whether an earlier fix already covers it (git log a4bbf05..HEAD for round 7), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`desktop round 9: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:desktop', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
