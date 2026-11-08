// The final audit: run wf_96ba8c00-e28, started 2026-11-02 14:39 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave3-slop-round3',
  description: 'Final audit, wave 3 (AI slop), round 3, one app (args.side): a read-only finder re-attacking round 2 fixes by name and then the app code round 1 left unread, one on the reader-facing documents round 1 left unread; a skeptic re-checks findings of medium or above',
  phases: [
    { title: 'Find', detail: 'fixes + app code finder, reader documents finder, read-only' },
    { title: 'Refute', detail: 'one skeptic re-checks the findings of medium or above, merges duplicates' },
  ],
}

const SIDE = args && args.side === 'android' ? 'android' : 'desktop'
const W3 = '<scratchpad>\\wave3'
const SCRATCH = W3 + '\\r3' + (SIDE === 'android' ? 'a' : 'd')
const SCAN = W3 + '\\scan\\' + SIDE
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'
const REPO = SIDE === 'android' ? ANDROID : DESKTOP

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project; on 2026-10-29 a test run took the owner's whole computer down -- not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Git: only log, show, diff, grep, ls-files, blame.
- Write ONLY inside your own folder, SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, any notebook_location.txt, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder -- use the Grep tool or git grep inside a repository.
- This wave READS. Never run the app, a test (qa*.py, test_*.py, story_*.py, gradle tests), tools/run_tests.py, tools/mutate.py, tools/linux_ci.py, docker, gradle, adb or the emulator. No network, no installing. You MAY run: your own Python scripts in SCRATCH_DIR with 'py -I' that read source files as text (never import the app's code); and the read-only static gates -- desktop: py ${DESKTOP}\\tools\\check_doc_links.py, check_comments.py, check_one_definition.py, check_undefined_names.py, check_english.py, check_class_api.py (no flags); phone: py -I ${ANDROID}\\tools\\check_layering.py, check_note_shape.py, check_english.py, check_palettes.py. If a command is refused, do not try another spelling -- note it under not_covered.
- Do not fix anything. Find, prove, report.
`

const WAVE = `
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 3: the "AI slop" scan the owner asked for in her words: "We both know the apps are built with AI, but that does not mean they should not be made well." Waves 0-1 and a lows wave already closed: data safety, hostile input and crashes were attacked for twenty-five rounds, so this wave is not a bug hunt. Find what makes the code or the documentation read as generated rather than written for its reader -- and anything either one says that is not true.

WHAT TO LOOK FOR
- Code: dead or never-called code; helpers duplicated that answer the same question (the next fix lands on one); try/except or catch that swallows errors with no reason given; defensive checks for cases the code makes impossible; comments that repeat the code or tell history instead of why; names inconsistent for one thing between the desktop and the phone; huge functions that should be split (only where it hurts a reader -- do not propose refactors for taste); parameters or options nobody uses; tests that cannot fail; TODOs, placeholders, invented APIs.
- Documents: filler and repetition; marketing or empty words; claims the code does not support; stale numbers; contradictions between documents; one topic explained in full in two places (the project's rule is one canonical home per topic -- CLAUDE.md, "Documentation standards"); sentences far too long; text that sounds generated rather than written for its reader.

SEVERITY FOR THIS WAVE (only medium or above keeps the round open; the rounds stop after two in a row with nothing of medium or above):
- high: a statement a user or a store reviewer reads (README, USER_GUIDE, PRIVACY, a store or in-app text a document quotes) that is false about what the app keeps, sends, deletes or protects; or slop hiding a real defect -- two copies of one rule that already behave differently, an error swallowed where a note or a backup is written or read so that a failure loses words silently.
- medium: a statement in a document a reader acts on (README, CLAUDE.md, USER_GUIDE, ARCHITECTURE, CODE_TOUR, DATA_FORMAT, STATUS, qa/README, RELEASE_*, AI_WORKFLOW, the tools' READMEs) that is false against the code or the repository TODAY -- a number, a command that would not run as written, a file or function that no longer exists, a behaviour the code does not have; two documents that contradict each other about the present; code nothing runs, beyond a few lines; two helpers answering one question; an error swallowed with no reason on a path that reads or writes notes, settings, backups or files; a test or gate that cannot fail.
- low: style and taste -- empty or marketing words, filler, repetition inside one document, an over-long sentence, a comment repeating its code, a comment telling a story instead of a reason, inconsistent naming, a stale but harmless comment, a duplicated test helper.
The test for medium: would a reader acting on it be misled, or would a maintainer's next change go wrong because of it? If it only reads badly, it is low. Lows are recorded and fixed later in bulk -- report them briefly; a cluster of the same kind is ONE finding with a count and three examples.

HISTORY IS PRESERVED, NOT FALSE. docs/ISSUES_LOG.md stories, CHANGELOG.md entries and ROADMAP history describe the past; a past statement there is not wrong because the code changed later. Flag only text that claims to describe the present. CHANGELOG's bullet counts are an invariant (the version number is derived from them). docs/IN_MY_WORDS.md and docs/BUG_REPORTS.md are the owner's own voice: flag false facts only, never her tone.

ALREADY DECIDED -- do not report: no Terms & Conditions and no "Agree" screen; nothing in git history is rewritten (an old note "mate" in the phone's history, six photographs with a strip of desktop in the desktop's); commit messages and PR texts are history. Known and counted already: the comment gate's BRIEF list (desktop tools/check_comments.py) is partial on purpose -- "a module joins BRIEF once it has been condensed" -- so report the uncondensed remainder as ONE finding with its measure and the five worst examples, not comment by comment; swallowing tk.TclError on a widget that may already be destroyed is the desktop's idiom -- report one only if it hides something other than a gone widget. The phone's ExampleInstrumentedTest.kt (a template leftover) waits on the owner's yes -- report it once, as a low, if it is still there.

ROUND 3. Round 1 covered the app's own code and the reader-facing documents; round 2 re-attacked round 1's fixes and covered the tools, tests, site and history documents. Both found mediums on both apps, all fixed. The owner's rule: every fix is attacked again BY NAME, and the rounds stop only after two in a row find nothing of medium or above. Round 3 re-attacks round 2's fixes and reads what round 1 said it had NOT read (named in each area below).

ROUND 2'S FIXES, to re-attack by name (read the commits with git show):
- Desktop, branch audit/d-val3: 1b27f95 (run_coverage.py reads run_tests' suite lists; pre_push_check.py runs check_mutant_targets and stops when git cannot list files; qa9's skipped keyboard checks print SKIP through a skip() helper and run_tests counts and names SKIP lines apart from PASS; site/build.py reads the phone's test and walk counts from the phone's qa/README; site/src/index.html and android-demo/android.js say the phone's Google backup copies notes while it is on; regen_seam_map.py finds its own root; comments about NOTEORG_SCRATCH and track_theme) and b5434bf (qa/README's seam map regenerated; CLAUDE.md says the qa suite and test_data_safety refuse without NOTEORG_SCRATCH; GIT_WORKFLOW and CODE_TOUR on pre_push_check; ROADMAP's two residuals settled; site/README names the parsed sentences; USER_GUIDE's crash-log entry head).
- Phone, branch audit/a-val3: ecdbe34 (Notebook.restoreFromTrash removed, the restore tests and the days fuzz on Organizing.restore through app/src/test/.../Trashed.kt; dup_explain names the key's six parts, OrganizingTest reads strings.xml to hold all three duplicate texts; Organizing.deletedAt reads a stamp to its end with a ParsePosition; a share test of a test helper removed) and 1a44fae (walk.py's main runs hostile_backups, code_read_away, long_lines -- 70 parts; emulator_only.fresh_tree used by walk, take_screenshots, tap_by_text; check_release_lookups and make_licenses --check fail when they read nothing; README's Google-backup sentence; ISSUES_LOG "Still open" items marked closed, its opening and count; STATUS's walk paragraph; CHANGELOG [Unreleased]'s note that it stops at round five).

ROUND 1'S FIXES (attacked by round 2; read again only where round 3's area meets them):
- Desktop, branch audit/d-val3: 6d49492 (duplicates.SAME_AS, one phrase for what a duplicate is, in every text that says it, held to _dup_key's length by a test; run_migrations case 1 keeps settings_replaced_<stamp>.json before replacing a readable settings.json, leaves the settings if that copy fails, copies with _copy_whole; _return_to_calendar's guard logs through _log_swallowed instead of a bare pass; removed as dead: _grid_read_rows, _grid_read_aligns, _grid_click, _settings_section_note, tables.to_rows, the "plus" glyph; tools/check_doc_links.py keeps an underscore inside a heading's code span) and 5b460ed (USER_GUIDE's crash-log promise scoped to each entry's first line; CODE_TOUR's new single_instance section; NOTEORG_SCRATCH=1 named in the by-hand run in CLAUDE.md, qa/README, ARCHITECTURE; the numbers rewritten and dated -- entry file ~24,000 lines, ~4,800 checks, 859 test-plan cases with recounted tables, eleven gates; the "already open" dialog named). And 531de6a: tools/check_english.py's docstring about the phone's language.
- Phone, branch audit/a-val3: 4287cff (Organizing.deletedAt, one strict parse for the Trash row's days left and the purge; Notebook.deleteNote, applyShareCode, shareCodeFor, updateTable and Tables' splitBody/BodyPart removed as code only tests ran; the delete tests now drive Organizing.trashNotes; the share tests use app/src/test/.../Shares.kt over Importing) and 394c705 (counts kept in qa/README, dated, the other documents linking there; the ARCHITECTURE map re-measured, GoogleBackup.kt added; permissions, uid minting, the desktop's notebook folder, the icon's 47% corrected; check_note_shape.py now also holds DATA_FORMAT.md's field list to the Python's).
Ask of each: is the new text true against the code? Did the change break a sibling (another text, a link, an anchor, a caller, a test that now proves less)? Did a removal take anything still needed (a mutant in tools/mutants.json, a tool, a document that names it)? Did a dated or linked number leave another copy of it stale?

ALREADY RECORDED as lows (do not report again): the desktop's uncondensed comments outside BRIEF; the phone's comments telling history; nine KDoc blocks cut off from their functions; KDocs promising old behaviour (5); parameters no caller passes (9); small rules spelled out by hand (find-by-id x7, the stamp format, '(untitled)'); the stamp literal written 15 times on the desktop; build_notes_tab's size; filler 'simply' and long sentences in USER_GUIDE and STATUS; README's commit count told twice; GIT_WORKFLOW's Scenario A; unused imports zlib, base64, timedelta in the desktop's entry file; NOWHERE/UNREADABLE written three times on the phone; Notebook.inspectShareCode's Load overload used by tests only; the unused nrows/dlg parameters on the desktop. From round 2: check_doc_links walks the disk rather than tracked files; check_one_definition's docstring describes five of its eight rules; three stale tool docstrings; qa helpers written several times; swallowed errors in the machine guards; the SAME_AS test compares counts only; three ROADMAP passages out of step; the site's "859 manual test cases, walked" while 263 are Not Tested; docs/archive registers reading as live; on the phone, more app functions only tests call (parseNotes, sameDate, showStamp...), checks that go quiet, duplicated test helpers and deleteOnExit calls, history in tool comments, ISSUES_LOG index cells grown long, STATUS's copies of the fixture counts and the walk's run-by-run history.

GROUND TRUTH AT HEAD (do not recompute; use it for number claims). Desktop ${DESKTOP}, branch audit/d-val3: the entry file note_organizer.py has 24,381 lines; noteorganizer/core has 18 modules and noteorganizer/ui 7 mixins; the full suite on Windows is 27 suites, 4,850 checks (unit suites 1,294, qa suite 3,556), all passing; on Linux 4,823, all passing, one SKIP (qa5's multi-script widget routes); tools/mutants.json holds 992 entries; the test plan holds 859 cases, IDs to 966; the site builds. Phone ${ANDROID}, branch audit/a-val3: 932 unit tests pass, 0 fail, in 31 suites; 7 gates pass; the emulator walk has 70 parts (its last full run, 2 Nov, of the 67 there were then: 533 checks passed, 20 failed, both causes the walk's own and fixed; the three added parts are not yet run in a full walk -- known, the next full walk before an install runs them); the test plan holds 424 cases, IDs to 430.

THE MECHANICAL SCAN (free, already run, in ${SCAN}): candidate lists with false hits -- judge them against the code, never trust them. Each file says in its name what it lists; the documents' lists are empty_words.txt, number_claims.txt, sentences_in_two_docs.txt, long_sentences.txt. Your work is the judgement and what no scan can see.

HOW TO REPORT. Each finding: the exact place (file:line), the evidence (quote the document and the code or command that contradicts it), why it matters, and the smallest fix. proved=true only when you checked it against the code or the repository yourself; otherwise proved=false and say why you still believe it. Prefer 5 real findings over 25 guesses; about 15 targeted checks, the strongest first -- the owner's usage is limited this week: read the functions and sections you need, not whole files you do not. A clean, well-checked area is a real result: say what you checked in 'covered'. End with an honest coverage confession: what you did NOT check.
`

const AREAS = SIDE === 'desktop' ? [
  { key: 'w3d3-fixes-code', focus: `FIRST, ROUND 2'S DESKTOP FIXES BY NAME (1b27f95, b5434bf; see ROUND 2'S FIXES below) -- the tools' changes read as code: does run_coverage still run as CI starts it, does pre_push_check now match CI's list exactly, does every qa script that skips print SKIP and nothing counts a SKIP as a PASS, does site/build.py's new reading fail loudly when the phrase moves again. THEN THE DESKTOP APP'S CODE WHERE ROUND 1 DID NOT READ (${DESKTOP}\\note_organizer.py and noteorganizer\\): the docstrings of core/recurrence.py, richtext.py, formatting.py, tables.py, calculator.py, themes.py and winspell.py against their bodies; the tk.TclError-only handlers whose try body does more than touch a widget (does any swallow a failure of something else -- a save, a parse, a file?); hasattr/getattr guards on app state that the build order makes always true or always false (sample the hub); the eleven longest comment runs round 1 did not read (scan: comment_runs_over_3.txt). Read only; never run a suite, a qa script, a story, mutate.py, run_tests.py or linux_ci.py.` },
  { key: 'w3d3-docs', focus: `FIRST, ROUND 2'S DESKTOP DOCUMENT CHANGES BY NAME (b5434bf and the documents 1b27f95 touched): true against the code, and no sibling left saying the old thing. THEN THE DESKTOP'S READER-FACING DOCUMENTS WHERE ROUND 1 DID NOT READ (all under ${DESKTOP}): docs/USER_GUIDE.md beyond its first 400 lines -- the keyboard-shortcut tables (about :1082-1145, and the in-table and list keys) against the bindings in the code, and the recurrence, calendar and Tables how-to sections against the app; docs/ARCHITECTURE.md's theming, large lists, Sharp-on-a-scaled-screen and contrast sections; docs/CODE_TOUR.md beyond its first 200 lines (each module section against its module); qa/README.md's house rules, script-ownership tables and surface inventory against the qa scripts; docs/BUG_REPORTS.md's figures ('20 bugs', the fixed-in versions) against CHANGELOG and the test plan; README.md as a whole. Check numbers, commands, names and present-tense behaviour against the code; contradictions; one topic in two homes; text that reads generated.` },
] : [
  { key: 'w3a3-fixes-code', focus: `FIRST, ROUND 2'S PHONE FIXES BY NAME (ecdbe34, 1a44fae; see ROUND 2'S FIXES below): does Trashed.kt build the keys Organizing.restore expects, and does every test that used to prove the restore still prove it on the live code; does OrganizingTest's read of strings.xml hold where Gradle runs it; is deletedAt now as strict as the desktop's strptime, no more and no less; do the three tools share fresh_tree with the walk's old behaviour kept (its failure count and message); do the release gates now fail only when nothing was read. THEN THE PHONE APP'S CODE WHERE ROUND 1 DID NOT READ (${ANDROID}\\app\\src\\main): NoteEditor.kt, Pasting.kt, Paragraphs.kt, TableView.kt, CalendarScreen.kt and TemplateScreens.kt -- copied Compose blocks, KDoc that promises what the code no longer does, defensive checks for impossible cases, helpers answering one question twice; res/values/strings.xml against what the code does when it shows each text (sample the questions and the refusals); the manifest's backup rules (backup_rules.xml, data_extraction_rules.xml) against GoogleBackup.kt. Read only; no gradle, no adb, no emulator.` },
  { key: 'w3a3-docs', focus: `FIRST, ROUND 2'S PHONE DOCUMENT CHANGES BY NAME (the documents in 1a44fae): true against the code, no sibling left saying the old thing. THEN THE PHONE'S READER-FACING DOCUMENTS WHERE ROUND 1 DID NOT READ (all under ${ANDROID}): docs/STATUS.md lines 40-385, the "What works today" list, against the app (check each item that names a behaviour you can find in the code); docs/ARCHITECTURE.md lines 130-355, the decisions (two representations, write order, AppState, layout); docs/DATA_FORMAT.md lines 213-405 -- the _prev rescue copy and a series' days, traced through the Kotlin AND the desktop's noteorganizer/core/model.py, the densest claims in the area -- plus 560-600 (paste), 800-840 (what a shared note may change) and the write order it states (about :893); qa/README.md lines 70-158 and 215-318. Check claims against the code; contradictions; one topic in two homes; text that reads generated.` },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      key: { type: 'string' }, title: { type: 'string' },
      severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
      kind: { type: 'string' }, where: { type: 'string' },
      evidence: { type: 'string' }, proved: { type: 'boolean' },
      why_it_matters: { type: 'string' }, fix_idea: { type: 'string' },
    }, required: ['key', 'title', 'severity', 'kind', 'where', 'evidence', 'proved', 'why_it_matters', 'fix_idea'] } },
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
  return `You are an auditor in the final audit of Note Organizer, an offline notes app with a desktop version (Python + Tkinter, ${DESKTOP}) and a phone version (Kotlin, ${ANDROID}) that read the same notebook format. Your one area:

${area.focus}

SCRATCH_DIR = ${SCRATCH}\\${area.key}
${SAFETY}
${WAVE}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(found) {
  return `You are the skeptic for the ${SIDE} app's wave-3 ("AI slop") findings in the final audit of Note Organizer (desktop ${DESKTOP}, phone ${ANDROID}). The auditors reported the findings below. For EACH one, try to REFUTE it: re-read the document and the code it cites, check whether the claim is true after all (a function found under another name, a number that is right for what it counts, a command that does run), whether the text is history rather than a claim about the present, whether it is one of the decisions already taken, whether a gate or a test already holds it, or whether two findings are one. "confirmed" only when you saw it yourself or the code leaves no doubt; "plausible" when you cannot settle it. Re-grade severity on the wave's scale -- the test for medium is whether a reader acting on it would be misled or a maintainer's next change would go wrong; if it only reads badly it is low.

SCRATCH_DIR = ${SCRATCH}\\skeptic
${SAFETY}
${WAVE}
FINDINGS (JSON):
${JSON.stringify(found, null, 1)}

Return one verdict per finding key. Name what you could not check under not_checked.`
}

const reports = await parallel(AREAS.map(area => () =>
  agent(finderPrompt(area), { label: `find:${area.key}`, phase: 'Find', schema: FINDINGS_SCHEMA })
    .then(r => r ? { area: area.key, ...r } : { area: area.key, findings: [], covered: '', not_covered: 'AGENT RETURNED NOTHING' })))
const found = reports.filter(Boolean).flatMap(r => r.findings.map(f => ({ ...f, area: r.area })))
const weighty = found.filter(f => f.severity !== 'low')
log(`${SIDE} wave 3 round 3: ${found.length} findings from ${reports.filter(Boolean).length} finders, ${weighty.length} of medium or above sent to the skeptic; the lows kept as reported`)
log('not covered this round, by the rotation: the tools, tests, site and history documents beyond round 2 fixes (round 4)')
let verdicts = null
if (weighty.length) {
  verdicts = await agent(verifierPrompt(weighty), { label: `refute:${SIDE}`, phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
