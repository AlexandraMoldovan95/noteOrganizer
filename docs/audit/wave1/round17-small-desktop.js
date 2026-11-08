// The final audit: run wf_e127599f-901, started 2026-11-01 02:59 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave1-round17-small-desktop',
  description: 'Final audit wave 1, round 17, small for the usage limit (desktop): 2 read-only break-it agents re-attack the round-16 fixes with their seams, and the series days as a whole; a skeptic re-checks the findings of medium or above',
  phases: [
    { title: 'Attack', detail: '2 desktop finders: the round-16 fixes and seams, the series days as a whole' },
    { title: 'Refute', detail: 'one skeptic re-checks the findings of medium or above, merges duplicates' },
  ],
}

const SCRATCH = '<scratchpad>\\wave1\\r17'
const SMOKE = '<scratchpad>\\wave1\\r1\\_smoke\\probe.py'
const R10GAPS = '<scratchpad>\\wave1\\r10\\not_covered.txt'
const R10SUMMARY = '<scratchpad>\\wave1\\r10\\summary.txt'
const R10FINDINGS = '<scratchpad>\\wave1\\r10\\findings'
const R10FIX = '<scratchpad>\\wave1\\r10fix'
const R11GAPS = '<scratchpad>\\wave1\\r11\\not_covered.txt'
const R11SUMMARY = '<scratchpad>\\wave1\\r11\\summary.txt'
const R11FINDINGS = '<scratchpad>\\wave1\\r11\\findings'
const R12GAPS = '<scratchpad>\\wave1\\r12\\not_covered.txt'
const R12SUMMARY = '<scratchpad>\\wave1\\r12\\summary.txt'
const R12FINDINGS = '<scratchpad>\\wave1\\r12\\findings'
const R13GAPS = '<scratchpad>\\wave1\\r13\\not_covered.txt'
const R13SUMMARY = '<scratchpad>\\wave1\\r13\\summary.txt'
const R13FINDINGS = '<scratchpad>\\wave1\\r13\\findings'
const R14GAPS = '<scratchpad>\\wave1\\r14\\not_covered.txt'
const R14SUMMARY = '<scratchpad>\\wave1\\r14\\summary.txt'
const R14FINDINGS = '<scratchpad>\\wave1\\r14\\findings'
const R15GAPS = '<scratchpad>\\wave1\\r15\\not_covered.txt'
const R15SUMMARY = '<scratchpad>\\wave1\\r15\\summary.txt'
const R15FINDINGS = '<scratchpad>\\wave1\\r15\\findings'
const R16GAPS = '<scratchpad>\\wave1\\r16\\not_covered.txt'
const R16SUMMARY = '<scratchpad>\\wave1\\r16\\summary.txt'
const R16FINDINGS = '<scratchpad>\\wave1\\r16\\findings'
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
THE DESKTOP APP: ${DESKTOP} (branch audit/d-val1, checked out; do not switch branches). Offline Python + Tkinter notes app; core/ (no tkinter) + ui/ mixins + the entry file note_organizer.py. Read CLAUDE.md's overview, docs/ARCHITECTURE.md, and docs/ISSUES_LOG.md -- its stories "Round ten: the days a date held without a word, and older words given back", "Round ten: the note read again by every reader, and an edit the find bar never heard" and "The test that took the computer down" (with its round-seven to round-ten follow-ups) describe the round-10 fixes.
HOW TO RUN THE APP: only through the door in the rules. Inside the container your probe runs in a fresh throwaway folder that already holds note_organizer.py, noteorganizer/, _qa_support.py and guest.py (so "import note_organizer as NO" works there), the repository is mounted read-only at /repo, and SCRATCH_DIR is /work (read-write: write outputs and photographs there; read your own seed files from there). Seed notes by writing notes_data.json in the current folder BEFORE building NO.NoteOrganizer(). ${SMOKE} is a working older example (it copies the app itself to /tmp/app; either way works). qa/qa*.py and qa/_qa_support.py show how the suite drives the app (read for technique; never run them on the host). For a photograph inside the container, grab the app's own window (PIL ImageGrab under Xvfb, or xwd of its window id) into /work and LOOK at it.
Pure-Python probes on Windows are allowed only for code that does not import tkinter, from a copy inside SCRATCH_DIR, with the guest lines first and APPDATA, LOCALAPPDATA, USERPROFILE and HOME set to empty folders inside SCRATCH_DIR BEFORE importing the app's code (assert that first).
`

const FIXES = `
THE ROUND-16 FIXES (47be083 on audit/d-val1 -- 'git show 47be083'; round 16's findings, one line each: ${R16SUMMARY}; JSON in ${R16FINDINGS}; not covered: ${R16GAPS}; docs/ISSUES_LOG.md 'Round sixteen'). moves_home walks each chain of moves once (a memo per day, a loop's days never free): a day moved onto a date the rule now gives leaves it, going home with its words only where the rule still gives its own date and it was not deleted -- else the move goes and its words stay where they showed, on the rule's day there; restore_previous_version calls it too. copy_days_set_aside counts a copy's day held where the note holds it now: its date, the date the copy moved it from, or where the note has moved that day since. The core's settle_set_aside makes the notes of days set aside, numbered once: at the start inside storage.load_notes (report['set_aside_made'], written in the same once-only write as minted identities) and at the head of every save_notes, said after the save's own status line ('<line> -- Earlier text of N days ...'); notes_set_aside reads entries through _shaped_aside. The start's news says 'titled with the day's or the series' name'. Mutants DR146, DR152, DR153, DR159 re-aimed; DR161-DR169 new; all 25 of DR143-DR169 killed. Written down: a rule changed and changed back does not bring back a move it dropped; a share code's Update keeps no move in its copy, so Restore previous after it brings the rule back, not the move; the import's own status line still follows the made notes' one. The phone's side: daa4576 in ${ANDROID}.
THE ROUND-15 FIXES (d086330 and 1e72edd on audit/d-val1 -- 'git show d086330'; round 15's findings, one line each: ${R15SUMMARY}; JSON in ${R15FINDINGS}; not covered: ${R15GAPS}). THE OWNER CHOSE THE SIMPLER RULE (1 Nov): rounds 11-14's merging of a copy's words into a day (_words_added, _lines_lacked, _line_key, the LCS) is GONE -- the round-11 to round-14 paragraphs below are history. Now a day holding words of its own keeps them exactly; a copy's day whose words the note's day does not hold (_own_words_held, compared by _same_word: a title stripped, a text through with_caret_line) is set aside in note['_set_aside'] (_aside_entry; _copy_days_placed returns (overrides, aside); spend_series_days appends it) and becomes a note of its own on that date titled '<the copy day's title, else the series'> (earlier text)' (notes_set_aside: the entry's body, comments, category, colour), made by _set_aside_days at the start (said in the start's news, written with the first save) and at the head of every save_notes (said on the status line). normalize_note carries _set_aside through _shaped_aside (a real date written as the calendar keys it, a word, every field text; at most MAX_OCCURRENCES since 1e72edd, from a commit's security review, which also numbers the notes made from one look at the notebook). copy_days_set_aside(note): before a copy is replaced -- _turn_off_rescue_copy, the save's big-delete branch (not when only the comments are due), apply_shared_update (after kept_days_fit and days_to_rescue have read the old copy) -- a series' own copy the note no longer repeats as sets its days with words aside and drops its day fields. moves_home(note) (_rule_days_among): a day moved onto a date its rule gives by itself goes home with its words, to a fixpoint (a chain on dates the rule leaves free holds; never onto a deleted day's date or a date another day was moved from) -- in normalize_note, the series save and apply_shared_update. Mutants DR143, DR144 re-aimed, DR146-DR148 and DR150-DR160. Written down, not fixed: _write_series_owned's whole-note copy for a turn-off has no caller (every day's save passes schedule=False); a set-aside note may repeat lines the day also holds (only the same words count as held); a day settled off the schedule as a note, or sent to the Trash, while the note repeats as another series can come back as '(earlier text)' at a later turn-off, the old copy still holding it. The phone's side: 378a49b, c6fb1c7 in ${ANDROID}.
THE ROUND-14 FIXES (14ce276 on audit/d-val1 -- 'git show 14ce276'; round 14's findings, one line each: ${R14SUMMARY}; JSON in ${R14FINDINGS}; not covered: ${R14GAPS}). _lines_lacked now adds the copy's lines outside the longest run the two texts share in order (an LCS over _line_key; past 250,000 line pairs, the lines whose key the day lacks), a table's rows compared by their cells' words (padding and a box's tick left out, every separator alike), a table among the added lines with its header and separator; blank lines alone add nothing. So a corrected line adds its old form once at the end; an edited cell adds its old row under the table's header; a ticked box adds nothing. Mutants DR149, DR150 new; DR146, DR147 re-aimed. The phone's side: 2db7826, d187a93 in ${ANDROID}.
THE ROUND-13 FIXES (d81b843 on audit/d-val1 -- 'git show d81b843'; round 13's findings, one line each: ${R13SUMMARY}; JSON in ${R13FINDINGS}; not covered: ${R13GAPS}). (a) _lines_lacked in _words_added: a copy's word adds nothing when the day holds its lines as one run, else all but the lines the day begins with, whole (a table keeps its rows); empty pieces add nothing; a body ending in a table keeps the line under it (with_caret_line). (b) _find_paint_around paints the 200 hits a line around the hit current once a rescan is done; _find_nav repaints when it walks past the painted ones (and refreshes _find_model_on). Mutants DR146-DR148, RX91, RX92 new; DR144 re-aimed. Written down: a cell's Ctrl+Z after Enter or an alignment has nothing to take back. The phone's side: d730673, b9afa68, 4ac6b33, 7ad4b04 in ${ANDROID}.
THE ROUND-12 FIXES (93a9b73 on audit/d-val1 -- 'git show 93a9b73' gives its reasoning; round 12's findings, one line each: ${R12SUMMARY}; JSON in ${R12FINDINGS}; what round 12 did not cover: ${R12GAPS}). (a) THE TAKE-BACK, the owner's second choice (31 Oct): round 11's keep-in-the-copy is gone; _copy_days_placed now ADDS a copy's day's own words that a day already holding words lacks after them (_words_added: a title and text appended to the day's text, comments to its comments, each on a line of its own; the series' words are not the day's), the copy's days are spent as before (nothing stays in _prev), and Restore previous is as it was. (b) _undo_occurrence_delete refuses while another day is drawn on the date or the series keeps an edit there ('Another day of this series is on ... now, so that day can't come back' / 'This series keeps text or a colour of its own on ... now, ...'). The refusals of a move and of Reset say 'text or a colour of its own' where no day is drawn. (c) _open_cell_editor calls entry.edit_reset() once the cell's words are in. (d) _find_painted paints at most FIND_LINE_PAINT (200) prose hits a line, those around the current hit (the cursor for a cell's match); the model keeps every hit for the count and Enter. Mutants DR145, RX89, RX90 new; DR143, DR144, DR135, DR134 re-aimed; 76 of 76 with the move, data, find and limited-box families. The phone's side: 7564f2e and d6a1f70 in ${ANDROID}.
THE ROUND-11 FIXES (c55a9dd on audit/d-val1 -- 'git show c55a9dd' gives its reasoning; round 11's findings, one line each: ${R11SUMMARY}; one JSON per finding in ${R11FINDINGS}; what round 11 did not cover: ${R11GAPS}; the session's take-back probe over 9,000 editor-made shapes, with idempotency and a reset after: <scratchpad>\\wave1\\r11fix\\core_probe\\probe1.py). (a) MOVES: _day_is_free refuses a date the series keeps an override for that no day is drawn on (off the schedule, or deleted with its edit kept), and a day's own date is no longer free whatever stands on it (the phone's Phase 3 rule); _move_this_day says 'This series still keeps the words of a day on ...'; _reset_occurrence_override asks _day_is_free before any question ('Another day of this series is on ... now'); _undo_day_move asks it as before. (b) THE TAKE-BACK: spend_series_days/_copy_days_placed drop a copy's day only where the note deleted that day; one with words that the note's day does not hold (_own_words_held: every word the copy's day holds unlike its own series must be the note's day's), or that lost a tie for its date, stays in _prev['overrides'] under the date it wanted (its own key on a second tie), and Restore previous brings it (rescue_copy_spent is false while they are there). The owner chose this over a finer test of the words on 31 Oct. Written down: a copy is one slot -- a later turn-off or big delete on that note replaces it. (c) Settings > Your name is under _limit_entry. Mutants DR140-DR144, RX88; MV06, DR132, DR135 re-aimed. The phone's side: a8c74db, 8bafc63 in ${ANDROID} (its read path, daysBackAsRead, kept too).
THE ROUND-10 FIXES (all on audit/d-val1; 'git log --reverse --format="%h %s%n%b" cd5527f..HEAD' lists them with their reasoning and mutants). Round 10's findings, one line each: ${R10SUMMARY}; one JSON per finding in ${R10FINDINGS}. The fixers' briefs, draft test rows and probes: ${R10FIX} (data\\ and android_days\\ the data fixer's, perf\\ the speed fixer's with its photographs in perf\\shots, walk\\ the find fixer's with its photographs in walk\\shots, the tools fixer's mutant runner mutant_tools.py).
DATA (04044ce, 99f041e; mutants DR131-DR139, DR126/DR44/DR32/DR127 re-aimed): spend_series_days works BY THE DAY, not the date -- a copy's day is dropped only where the note deleted that day or wrote words of its own for it; anywhere else its words go to the date the note draws that day (_copy_days_placed: where the note moved it or where a taken copy move put it, else its own date; an edit there with no words of its own -- day_has_words -- takes the copy's words and keeps its colour and category; an edit the copy draws on no day stays on its date); _copy_moves_taken drops transitively a copy move onto a day whose own move stays behind; _dates_held still decides the copy's deleted days and moves. _turn_off_rescue_copy: ANY earlier copy but an Update's (which is kept whole first) gives its words to the new copy only when rescue_copy_due(copy -> note) says the note lost words, whatever series it held; else the note is copied as it stands. _repeat_off_line promises Restore previous only while _holds_unspent_rescue. Written down, not fixed: a notebook this build saved must not go back to 0.97.405; the fuzz's residual shapes (a copy holding two edits for one date, one drawn on no day) neither app writes.
SPEED (41dcc6f, 1400717, c5f1d65, 18b35a6; mutants RX36-RX59, RX80-RX86, SP28-SP30, DM01 re-aimed): a save, an opening and a key read the note ONCE (_capture_and_read; save_current_note(body_read=...); _char_offsets(..., text=) counting Tk columns in Python -- a window or image one, an emoji two; _extract_paragraphs/_extract_formatting from the caller's text; _lines_starting_in per para_/align tag; _line_head reads 64 characters of the caret's line, the whole line when its start is blank, a pipe or a decimal run); the doubled snapshots removed; Ctrl+C, the size/font picker, Tab and the bullet button over a selection, the renumbering read once; the format buttons answer from tag ranges (_stretches_over, _only_line_breaks); _spread_typed_run finds the typed run's space in Python, not by Tk's search; the per-key word count waits (_count_waits_for_pause, _word_count_due) while the find bar shows hits, caught up at the pause and when the bar closes; the spelling underlines at most 500 a line and 2,000 a box, those nearest the caret (core/spelling.nearest_underlines). Byte-for-byte equivalence of the stored note against cd5527f's readers on 80 random notes.
FIND AND TITLE (8d66be3; mutants RX60-RX79, RX29/RX30/RV06/RV07 re-aimed, RX31 dropped): _schedule_autosave tells the find bar of every edit; the EditWithoutKey bindtag, first in the body's, title's, comments' and date's bindtags, hears Tk's own <<Cut>>, <<Paste>>, <<Clear>>, <<PasteSelection>> and schedules the autosave; _align_table_on_leaving schedules it too; the find model remembers what it was read from (_find_stale) and Enter rescans when the note moved under it; a line-break query is found in Python (_find_across_lines), Tk's search no longer called by the find code; emoji queries go through the same loop with _tcl_lower; clipboard.fragment_of finds <body with re.I; the title's <<PasteSelection>> goes through its paste's cap and one-line rule (_on_title_paste_selection, _title_take_paste); _limit_entry's boxes have a middle-click door; _title_within_limit(proposed, current) has the shrink rule; the title paste and _limit_entry measure room before deleting a selection (_entry_selected); add_placeholder clears the hint on a middle-click. And the session's 491e942 (found by the phone's round 10; RX87): _limit_entry says "Pasted text shortened" only when words were left out, not when its cap took only the paste's own trailing space, as the title has since 737efe7.
MACHINE SAFETY (790487e, 6a28f7c, 30903cc; GT42-GT57 in copies by ${R10FIX}\\mutant_tools.py, GT58 in the catalogue; GT54 expected to survive): every suite's as_a_guest finds where 'import note_organizer' would load the app from and REFUSES if that app's notebook_location.txt names any folder; _qa_support.seed_here is the one seed and refuses unless the folder the app will open (where_the_app_opens: the named folder, else resolve_data_dir) is the working folder; hermetic_seed = the scratch marker + seed_here; test_data_safety, doc_screenshots, visual_scenes, probe_bar_width use it; check_guest item 12 stands a stand-in notebook_location.txt (absolute and %USERPROFILE%) in a checkout and every suite opening must refuse; initialise(app_dir) still reads the location file (only its docstring changed). check_guest item 7/8: PowerShell's own parser (ParseFile through -EncodedCommand) reads the sandbox script, a param/begin/process block, #requires/using, a trap, more than one if-clause or an else refused, the literals' values re-quoted by ps_literal for the cross-check, code after '#>' a statement, any of PowerShell's five single quotes refused in a literal. linux_ci's tracked_copy refuses a link or junction at a tracked name or any folder of it.
Accepted by the owner, NOT findings: share codes Base64+zlib (not encryption); offline, no accounts, no Terms & Conditions; Tk 8.6 exposes no names/roles to screen readers; the zip build adopting its unpack folder; USERPROFILE missing; Trash clock far ahead; clock set back mid-session; the Settings section entries draw no keyboard ring; an over-long checklist item's row shows no way to read the rest beyond its tooltip.
KNOWN OPEN LOWS (do not re-report unless you show it is worse than low): a template lost at close after a failed templates write; pasted HTML that is markup-only read whole; the paste ceiling counted in characters, not Tk indices, for astral emoji; search/find boxes and other never-saved one-line boxes take pastes of any length; the find highlights have no bound per line, and a key with the bar open on a paragraph of 2,000 hits was not timed after round ten's typed-run fix; the undo journal reads the note once per undo step; "Your name" takes a middle-click's line breaks raw (its KeyRelease corrector handles the length); cell matches can pass FIND_MATCH_CAP by one per remaining row; a day reset while the series ran from another start can come back from the turn-off's copy when the start returns (judged contrived on both apps); everything in docs/ISSUES_LOG.md's "Written down, not fixed" paragraphs of rounds nine and ten.
NOTE ON THE MACHINE: in round 10 the Android emulator walk held the machine's turn for over two hours and two auditors' door calls gave up after 3,600 s. This round no emulator runs while you work; the turn is shared only with the other auditors. If a door call still gives up, say so and what it would have shown.
`

const REPORT = `
WHAT COUNTS (the owner's definition of "ready to publish"): notes are never lost or corrupted; nothing makes the app crash or freeze, hostile input included; nothing from outside executes or escapes the data folder, and nobody can steal data; an ordinary person is never trapped or misled; keyboard-only use works; and nothing the project's own tools do can harm the owner's computer or her data.
Severity: critical = notes lost/corrupted, or outside content executes / reads or writes outside the data folder / data leaves the device without the person's action; a test tool that can take the computer's memory or disk or its other windows, or reach the owner's own notebook. high = crash, hang over 5 s, or loss the person is warned about; a realistic action that silently does the wrong thing to notes; a test tool that can leave processes or gigabytes behind. medium = misleading or wrong but recoverable; a slowdown a weak machine would feel at realistic sizes (1,000 notes, a 1,000-row checklist); a keyboard trap. low = cosmetic or far-fetched.
Prove what you can: reproduced=true only if you actually ran it and saw it; otherwise reproduced=false and say why you still believe it. Prefer 3 real findings over 15 guesses; about 10 probes at most, the strongest first -- the owner's usage is limited this week: read the functions named, not whole files, and stop when your area is well tried. For a fix you attacked and found sound, say so in 'covered' with what you tried -- the rounds end when two rounds in a row find nothing of medium or above, so a clean, well-tried area is a real result.
End with an honest coverage confession: what you checked, and what you did NOT.
`

const AREAS = [
  { key: 'r17d1-round16-fixes-and-seams', focus: `RE-ATTACK THE ROUND-16 FIXES BY NAME (47be083), AND THEIR SEAMS. moves_home: chains whose links mix a date the rule gives and one it does not, a loop through a deleted day, a move whose origin is deleted, two days moved onto dates each other's chains free, a rule with a count or an end (_rule_days_among's walked branch), the cost on 5,000 moves under every rule kind (a same-run comparison, never one number); is any day now lost, shown twice, or its words moved to a date that holds another's? restore_previous_version: an Update copy, a turn-off copy, a big delete's copy, Restore twice; its question and the status line against what it now does. copy_days_set_aside's held(): a copy's day whose words the note holds on two dates, a moved day of the note whose words differ, a copy moved day onto a date the note deleted. settle_set_aside at the start: a cleanup launch (cleanup_done unset), a notes file set aside unreadable, held writes, a backup import whose notes carry _set_aside, two windows of the app writing one notebook. The combined status line: every caller of save_notes that sets its own line before or after (import, Restore previous, the Trash, a template, Settings), and a line already long.` },
  { key: 'r17d2-series-days-whole-again', focus: `THE SERIES' DAYS AS A WHOLE AGAIN, now that rounds 10 to 16 rewrote them and round 16 changed where a moved day goes. Attack the ROADS a person takes, end to end in the app through the door: a weekly meeting edited, moved, deleted, its Undo; the repeat turned off and on (as it was, from another start, another rule), Restore previous after each; a backup and an import of it; a share code; the Trash and back; a notebook from 0.97.405 (the fixer's v405 snapshot in ${R10FIX}) read by this build. Does any road still lose a day's words, show a day twice, hide a day, make an '(earlier text)' note that should not exist or none where one should, or say on the status line what the note does not do? Say which roads you walked and which you did not.` },
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
  return `You are a break-it auditor in the FINAL audit before Note Organizer is published (Microsoft Store). This is ROUND 17 (small, by the owner's usage limit; its areas rotate): round 16 found 1 desktop high (moves_home quadratic on a chain, a crafted backup freezing the window) and 2 mediums (a day sent 'home' to a date the rule no longer gives; Restore previous sending no day home), fixed in 47be083; the owner's rule is that every fix is attacked again by name, and the rounds stop only after two rounds in a row find nothing of medium severity or above. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${HOW}
${FIXES}
${REPORT}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the desktop app's round-17 break-it findings in the final audit of Note Organizer. Two auditors reported the findings below. For EACH one, try to REFUTE it: read the code path it names, re-run its probe if it left one in its scratch folder (only through the door in the rules, or a Windows pure-Python probe under the same isolation and the guest lines), check whether a guard elsewhere already stops it, whether it is one of the decisions already taken or a known open low, whether an earlier fix already covers it (git log a4bbf05..HEAD for round 7), or whether two findings are the same mechanism. Default to "plausible" when you cannot settle it either way, "confirmed" only when you saw it or the code leaves no doubt. Re-grade severity on the scale in the rules.

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
const weighty = found.filter(f => f.severity !== 'low')
log(`desktop round 17 (small): ${found.length} findings from ${reports.filter(Boolean).length} auditors, ${weighty.length} of medium or above sent to the skeptic; the lows kept as reported`)
log('not covered this round, by the owner\'s decision: the gaps and the tools (round 16 took them; round 18 rotates back)')
let verdicts = null
if (weighty.length) {
  verdicts = await agent(verifierPrompt(weighty), { label: 'refute:desktop', phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
