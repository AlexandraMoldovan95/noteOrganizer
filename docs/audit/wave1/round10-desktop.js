// The final audit: run wf_2116cd26-93e, started 2026-10-30 16:30 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round10-desktop',
  description: 'Final audit wave 1, round 10 (desktop): 5 read-only break-it agents re-attack every round-9 fix by name (the days taken back per date, the turn-off copies, the linear finds and pastes, the guards of the test tools), round 9 gaps and the seams with the phone; then a skeptic tries to refute every finding',
  phases: [
    { title: 'Attack', detail: '5 desktop finders: round-9 data fixes, interface fixes, machine safety, round 9 gaps, the seams' },
    { title: 'Refute', detail: 'one skeptic re-checks every finding, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r10'
const SMOKE = '<scratchpad>\\wave1\\r1\\_smoke\\probe.py'
const R9GAPS = '<scratchpad>\\wave1\\r9\\not_covered.txt'
const R9SUMMARY = '<scratchpad>\\wave1\\r9\\summary.txt'
const R9FINDINGS = '<scratchpad>\\wave1\\r9\\findings'
const R9FIX = '<scratchpad>\\wave1\\r9fix'
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
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val1, checked out; do not switch branches). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, docs/ARCHITECTURE.md, and docs/ISSUES_LOG.md -- its stories "Round nine: days spent before they came back, and a copy kept twice", "Round nine: work that grew with the square of what was typed" and "The test that took the computer down" (with its round-seven, round-eight and round-nine follow-ups) describe the round-9 fixes.
HOW TO RUN THE APP: only through the door in the rules. Inside the container your probe runs in a fresh throwaway folder that already holds note_organizer.py, noteorganizer/, _qa_support.py and guest.py (so "import note_organizer as NO" works there), the repository is mounted read-only at /repo, and SCRATCH_DIR is /work (read-write: write outputs and photographs there; read your own seed files from there). Seed notes by writing notes_data.json in the current folder BEFORE building NO.NoteOrganizer(). ${SMOKE} is a working older example (it copies the app itself to /tmp/app; either way works). qa/qa*.py and qa/_qa_support.py show how the suite drives the app (read for technique; never run them on the host). For a photograph inside the container, grab the app's own window (PIL ImageGrab under Xvfb, or xwd of its window id) into /work and LOOK at it.
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with the guest lines first and APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE importing the app's code (assert that first).
`

const FIXES = `
THE ROUND-9 FIXES (all on audit/d-val1; 'git log --reverse --format="%h %s%n%b" 3e4200b..HEAD' lists them with their reasoning and mutants). Round 9's findings, one line each: ${R9SUMMARY}; one JSON per finding in ${R9FINDINGS}. The fixers' briefs, draft test rows and probes: ${R9FIX} (ui\\ for the interface fixer's probes and photographs, probe\\ for the tools fixer's).
DATA HALF (the session's 8b5d6cc; mutants DR124-DR130, DR114/DR32/DR112 re-aimed): spend_series_days now TAKES THE COPY'S DAYS BACK PER DATE before spending them -- each of a series' own copy's overrides, exceptions and moves goes into the note on every date the note's own days leave free (_dates_held: the note's override keys, exceptions, moved keys AND moved values), a copy's move never onto a date the note holds, then the copy's DAY_FIELDS are removed; it runs at every read (_days_back_from_copy, whose all-or-nothing move for a note holding no day stays) and in save_current_note after the repeat is written; copy_holds_this_series(note) is the public judgement. _turn_off_rescue_copy's order is now: takes_text; an unspent update copy kept whole (before the held branch); the held text copy; a text-only copy OR an earlier turn-off's copy of the same series (copy_holds_this_series) gives its words. _repeat_off_line: after a turn-off that kept an update copy the status line says Restore previous brings back the note as it was before it was updated (three call sites). shared_update_changes reads the ARRIVING note as a load does, WITH its copy (the take-back runs), then compares both bare; this side is not re-read -- this REVERSES round 8's bare reading of the arriving side: a backup whose copy holds a day reset here since now reads as changed. "Import failed": the unpacked folder is removed before the dialog.
INTERFACE HALF (737efe7, 8372571, 81078b6, f550fe3, 098d5a8, a657938; mutants RX17-RX35, SP06/SP07/SP24, RZ10/RX01/RX14 re-aimed): the title paste splits on the break characters alone (_title_paste_line) after _cap_paste; "shortened" only when words are left out; richtext._BLOCK_TAG_RE and spelling._SENTENCE_END no longer backtrack; _waiting_said is forgotten when the words are added and set only when the message is shown (the close's question counts); spelling.visible_errors / sentence_spans / pieces measure a line once (_units_of, bisection); the find bar's rescan reads each line once (_find_prose with Tcl-style case folding in _tcl_lower, columns counted as it goes, hidden table text dropped by its ranges' starts, _find_shown for text before a table's window; emoji queries keep a Python branch; queries holding a line break keep Tk's loop), and the tables' walk splits once; _spell_read clears _spell_job when the look ends. Each quadratic fix has a check timed against its own half in one run (ratio bounds), compared with the old code on tens of thousands of random inputs.
MACHINE SAFETY (47e82f7; mutants GT01-GT41 in copies, by scratchpad wave1\\r9fix\\mutant_tools.py): tools/msix/sandbox_test.ps1 refuses unless the user is WDAGUtilityAccount AND the script is C:\\pkg\\sandbox_test.ps1 (this computer has a disabled WDAGUtilityAccount of its own); check_guest item 7 EVALUATES the guard in one strict shape (and asks PowerShell the same); linux_ci copies only what git tracks (git ls-files --cached), counts untracked files without naming them, runs the container --read-only with the 512 MB /tmp tmpfs; .gitignore names *.json.tmp, *.json.part, *_corrupt_*.json; every suite's first act is qa/_qa_support.as_a_guest() (hermetic_seed; the unit suites' openings): started by a runner it shares the run's turn and homes, otherwise it settles, and refuses without tools/guest.py; guest.lock_dir follows HOLDER_ENV to the parent's turn; test_data_safety's child has a timeout; check_guest item 12 runs each suite's opening as CI starts it.
Accepted by the owner, NOT findings: share codes Base64+zlib (not encryption); offline, no accounts, no Terms & Conditions; Tk 8.6 exposes no names/roles to screen readers; the zip build adopting its unpack folder; USERPROFILE missing; Trash clock far ahead; clock set back mid-session; the Settings section entries draw no keyboard ring; an over-long checklist item's row shows no way to read the rest; an animation stopping after its budget; Escape closing the preview for mouse users too; the remove that leaves a held attachment file behind; days with own text staying after a series is restarted; words left in a full list's box waiting for the note and asked about at close (said once).
KNOWN OPEN LOWS (do not re-report unless you show it is worse than low): a template lost at close after a failed templates write; pasted HTML that is markup-only read whole; the paste ceiling counted in characters, not Tk indices, for astral emoji; search/find boxes and other never-saved one-line boxes take pastes of any length; stored attachment names holding ':' from Linux source runs before 66a44e3; Windows' ~10,000-widget limit on a list of thousands of rows; qa2 slower on Windows; the one rescue-copy slot learning "what the series was"; a day's save and the repeat-off suffix said only on the status line; a .part file an import was writing at a session end not named in its word; the gate's blind spots the round-8 tools fixer named; Linux has no job object; the disk floor on Windows only; the AUTOSAVE reading a heavily tagged line ~4,000 times per save (quadratic in the bold words on ONE line, capped near 0.3 s by the per-line span ceiling -- re-report only with a shape that escapes the cap); an emoji find query also matching a drawn table's hidden text; Tk's own per-hit tagging at the 2,000-hit cap on one line (~0.3 s); queries holding a line break still searched by Tk per hit; the JS and shell door guards still found by name, not evaluated.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled; keyboard-only use works; and nothing the project's own tools do can harm the owner's computer or her data.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action; a test tool that can take the computer's memory or disk or its other windows, or reach the owner's own notebook. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes; a test tool that can leave processes or gigabytes behind. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes, a 1,000-row checklist); a keyboard trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 15 probes at most. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two rounds in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'r10d1-data-fixes', focus: `RE-ATTACK THE ROUND-9 DATA FIXES BY NAME (8b5d6cc). For each: a variation its own check did not try, a neighbour it broke, an unswept sibling. Ideas: spend_series_days' per-date take-back -- a copy's override on a date the note has MOVED AWAY (moved key) vs a date the note's moved day now SITS ON (moved value); a copy's move whose target is one of the copy's own exceptions; a copy holding more moves than MAX_OCCURRENCES leaves room for; the caps on overrides and exceptions after a merge (can a merge push a note past a ceiling normalize_note keeps elsewhere?); a copy override for a date that is no longer an occurrence of the rule (the rule is the same, but the series' end/count changed?); the take-back when the note's rule is equal but written differently (normalize_recurrence equality: interval 1 vs absent, weekday lists in another order); and every road that makes a note repeat as its copy's series again (Restore previous of a series copy over a turned-off note, an import's Update bringing the repeat back, a Trash restore, a duplicate, the calendar's own repeat controls, Undo in the editor) -- which merge when, and can a day the person resets between a merge and the next read come back? The turn-off's new order: an update copy that IS spent but holds a category the note changed since; a held save whose copy is a TEXT copy over an update copy; a series copy whose rule equals the note's but whose words are the same (spent -- dropped?) vs differ only in comments. shared_update_changes now reading the arriving note with its copy: an arriving note whose copy is an UPDATE copy holding days (the round-7 reason the take-back skips update copies -- still skipped?); a share code (not a backup) of a turned-off series from the phone; importing the same older backup twice -- the second time unchanged? The status line's update-copy words on the three call sites, including the left-out route. The failed import's folder removed before the dialog: a failure while the worker still writes into it.` },
  { key: 'r10d2-ui-fixes', focus: `RE-ATTACK THE ROUND-9 INTERFACE FIXES BY NAME (737efe7, 8372571, 81078b6, f550fe3, 098d5a8, a657938; read ${R9FIX}\\testplan_rows_ui.txt and the probes in ${R9FIX}\\ui). The find bar's _find_prose: every rule it must keep -- case-insensitive with letters Tcl and Python fold differently (Unicode version gaps: a letter added recently, Georgian Mtavruli, Cherokee), whole-word if any, a query at a table cell's edge, text typed on a table's first line before its window (_find_shown), a partly hidden line, a hit across a styled run boundary, a hit inside a link or an embedded image's alt, the 2,000-match cap with hits on many lines, the highlight and "n of m" counter after an edit while the bar is open, Enter/Shift+Enter navigation landing on the right letters after an emoji or a Tcl-folded letter; queries holding a line break (still Tk's loop) -- is any freeze reachable through them by typing? The title paste: a clipboard of only spaces, only breaks, a mix of CR/LF/U+2028 at the cap, a paste replacing a selection. The spelling's linear look: notes past 100,000 characters on one line; a line whose sentences end in odd punctuation (ellipsis char, CJK full stop, emoji); ignored words; a look interrupted by typing (the slice ids). _waiting_said after this round's change: the route the fixer could only test in qa3 (leaving the note, the sign-out, the close). And THE CLASS: sweep everything that runs on every keystroke, pause, scroll or redraw (the note list's filter as you type, the calendar redraw, the outline/heading list if any, the word count, the table bar, the drag of a column) for a loop that re-measures from the start on every step -- time each at two sizes, as the round-9 fixer did; a 4x per doubling is a finding.` },
  { key: 'r10d3-machine-safety', focus: `THE OWNER'S COMPUTER AND HER DATA, NOT THE APP. Re-attack round 9's machine-safety fixes by name (47e82f7). The sandbox guard -- evaluate it yourself in the gate's own shape for every case the gate tries and some it does not (a path with a trailing space, short 8.3 names like C:\\PKG~1, a UNC path, $PSCommandPath empty when the script is dot-sourced or piped into powershell, -Command with the script's text); can the .wsb still start it (read it)? NEVER run the script. Every suite settling itself (as_a_guest): a suite imported by another (a qa script that imports a helper suite), a suite run twice in one process, a suite under run_coverage, under mutate.py's copies, under the story scripts' children (do they still share the parent's turn, or deadlock waiting for their own parent's lock?), on GitHub Actions' Windows and Linux runners (read .github/workflows/tests.yml: the disk floor of 3,072 MB on a hosted runner's drive -- will a CI run REFUSE? the job object there?), and guest.lock_dir following HOLDER_ENV when the parent is gone. The Linux door's tracked-only copy: a file staged with git add but not committed, a file deleted in the working tree but still tracked, a submodule, a symlink; the read-only root vs anything the suite writes outside /tmp (matplotlib/fontconfig caches, Tk's ~/.Xauthority, pip's cache); --read-only with the probe's /work. And the class: list every place a test tool trusts a word in a file, an environment variable or a path instead of asking the thing itself, and say which could let a test reach the owner's data. Read only for her data; run only the static gates and probes through the Linux door.` },
  { key: 'r10d4-round9-gaps', focus: `WHAT ROUND 9 SAID IT DID NOT COVER. Read ${R9GAPS} (every section and the skeptic's not_checked), the fixers' confessions in the commit bodies (git log 3e4200b..HEAD) and their reports' "not covered" (in ${R9FIX}: the briefs, and the interface fixer's ui\\ notes). Pick the gaps most likely to hide a defect that matters (data loss, crash/freeze, a trap, harm to the owner's computer) and probe them -- at least five, and say which you skipped and why. Include: the find bar's equivalence was compared on Windows Tk only (Linux Tk: run a comparison through the Linux door); Tcl's and Python's Unicode versions differing; the autosave's tagged-line reads (is there a shape that escapes the 500-span-per-line clamp -- many lines each at the clamp? a table cell?); the phone's round-9 mirror (the walk has not run on it yet: read, do not run); the CI layout of as_a_guest never run on GitHub; a downgrade -- a notebook this build wrote (copies' days spent, days merged into notes) opened by 0.97.405: does the older build misread anything or lose a day?` },
  { key: 'r10d5-round9-seams', focus: `THE SEAMS BETWEEN THE ROUND-9 FIXES, made by three hands (the session's data fixes; interface; machine safety; the phone's mirror) and merged afterwards. Cross them: the per-date take-back x the find bar (a merged day's text found? the find bar searches the note, not days -- confirm), x the calendar's day panel and the occurrence banner right after a load merged days (shown without a save?), x the dirty comparator (does a note whose days were merged at load read as unsaved, or save on open?), x duplicates and Trash restores; the turn-off's update-copy branch x the held save x the interface's _waiting_said; as_a_guest x mutate.py x the timed ratio checks (do the new timed checks stay stable under the guest's memory ceiling and a busy machine -- run them twice through the Linux door and compare); the title paste's _cap_paste x the title's 200-letter cap x the "shortened" word. And PARITY with the phone's round 9 (${ANDROID}, git log b3f04db..HEAD; days_cases.json rebuilt from the desktop at 8b5d6cc, 49 cases): replay the desktop's own core (isolated, as in the rules) and the phone's Kotlin rule on shapes NOT in the 49 cases -- the per-date take-back with moves on both sides, a rule written differently on each app, the Repeat sheet's single spend vs the desktop's save, sharedUpdateChanges with each kind of copy, the title paste on CR LF and U+2028, int() on the shapes the phone now refuses. A disagreement that changes a note travelling between them is high.` },
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
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store). This is ROUND 10: round 9 found 16 distinct desktop defects (2 high, 3 medium, 11 low after the skeptic, plus 4 duplicates), and the fixers' own sweeps found two more highs of the same class (the find bar open while typing, the spelling's look), and they were fixed by three separate hands (data; interface; the machine-safety tools), then merged; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${FIXES}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the desktop app's round-10 break-it findings in the final audit of Note Organizer. Five auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (only through the door in the rules, or a Windows pure-Python probe under the same isolation and the guest lines), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open low, whether an earlier fix already covers it (git log a4bbf05..HEAD for round 7), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
log(`desktop round 10: ${found.length} findings from ${reports.filter(Boolean).length} auditors`)
let verdicts = null
if (found.length) {
  verdicts = await agent(verifierPrompt(found), { label: 'refute:desktop', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
