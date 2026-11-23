// The final audit: run wf_55a25879-ee1, started 2026-11-02 13:53 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave3-slop-round2',
  description: 'Final audit, wave 3 (AI slop), round 2, one app (args.side): a read-only finder re-attacking round 1 fixes by name and then the tools and tests, one on the history documents; a skeptic re-checks findings of medium or above',
  phases: [
    { title: 'Find', detail: 'fixes + tools/tests finder, history documents finder, read-only' },
    { title: 'Refute', detail: 'one skeptic re-checks the findings of medium or above, merges duplicates' },
  ],
}

const SIDE = args && args.side === 'android' ? 'android' : 'desktop'
const W3 = '<scratchpad>\\wave3'
const SCRATCH = W3 + '\\r2' + (SIDE === 'android' ? 'a' : 'd')
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

ROUND 2. Round 1 covered the app's own code and the reader-facing documents, found medium findings on both apps (none high on the phone; one high on the desktop), and they were fixed. The owner's rule: every fix is attacked again BY NAME, and the rounds stop only after two in a row find nothing of medium or above. Round 2 re-attacks those fixes and covers what round 1 left: tools/, qa/, the tests, site/, ROADMAP, ISSUES_LOG, CHANGELOG and docs/archive.

ROUND 1'S FIXES, to re-attack by name (read the commits with git show):
- Desktop, branch audit/d-val3: 6d49492 (duplicates.SAME_AS, one phrase for what a duplicate is, in every text that says it, held to _dup_key's length by a test; run_migrations case 1 keeps settings_replaced_<stamp>.json before replacing a readable settings.json, leaves the settings if that copy fails, copies with _copy_whole; _return_to_calendar's guard logs through _log_swallowed instead of a bare pass; removed as dead: _grid_read_rows, _grid_read_aligns, _grid_click, _settings_section_note, tables.to_rows, the "plus" glyph; tools/check_doc_links.py keeps an underscore inside a heading's code span) and 5b460ed (USER_GUIDE's crash-log promise scoped to each entry's first line; CODE_TOUR's new single_instance section; NOTEORG_SCRATCH=1 named in the by-hand run in CLAUDE.md, qa/README, ARCHITECTURE; the numbers rewritten and dated -- entry file ~24,000 lines, ~4,800 checks, 859 test-plan cases with recounted tables, eleven gates; the "already open" dialog named). And 531de6a: tools/check_english.py's docstring about the phone's language.
- Phone, branch audit/a-val3: 4287cff (Organizing.deletedAt, one strict parse for the Trash row's days left and the purge; Notebook.deleteNote, applyShareCode, shareCodeFor, updateTable and Tables' splitBody/BodyPart removed as code only tests ran; the delete tests now drive Organizing.trashNotes; the share tests use app/src/test/.../Shares.kt over Importing) and 394c705 (counts kept in qa/README, dated, the other documents linking there; the ARCHITECTURE map re-measured, GoogleBackup.kt added; permissions, uid minting, the desktop's notebook folder, the icon's 47% corrected; check_note_shape.py now also holds DATA_FORMAT.md's field list to the Python's).
Ask of each: is the new text true against the code? Did the change break a sibling (another text, a link, an anchor, a caller, a test that now proves less)? Did a removal take anything still needed (a mutant in tools/mutants.json, a tool, a document that names it)? Did a dated or linked number leave another copy of it stale?

ALREADY RECORDED as lows (do not report again): the desktop's uncondensed comments outside BRIEF; the phone's comments telling history; nine KDoc blocks cut off from their functions; KDocs promising old behaviour (5); parameters no caller passes (9); small rules spelled out by hand (find-by-id x7, the stamp format, '(untitled)'); the stamp literal written 15 times on the desktop; build_notes_tab's size; filler 'simply' and long sentences in USER_GUIDE and STATUS; README's commit count told twice; GIT_WORKFLOW's Scenario A; unused imports zlib, base64, timedelta in the desktop's entry file; NOWHERE/UNREADABLE written three times on the phone; Notebook.inspectShareCode's Load overload used by tests only; the unused nrows/dlg parameters on the desktop.

GROUND TRUTH AT HEAD (do not recompute; use it for number claims). Desktop ${DESKTOP}, branch audit/d-val3: the entry file note_organizer.py has 24,381 lines; noteorganizer/core has 18 modules and noteorganizer/ui 7 mixins; the full suite on Windows is 27 suites, 4,850 checks (unit suites 1,294, qa suite 3,556), all passing; tools/mutants.json holds 992 entries; the test plan holds 859 cases, IDs to 966. Phone ${ANDROID}, branch audit/a-val3: 932 unit tests pass, 0 fail, in 31 suites; 7 gates pass; the emulator walk has 67 parts (its last full run, 2 Nov: 533 checks passed, 20 failed, both causes the walk's own and fixed); the test plan holds 424 cases, IDs to 430.

THE MECHANICAL SCAN (free, already run, in ${SCAN}): candidate lists with false hits -- judge them against the code, never trust them. Each file says in its name what it lists; the documents' lists are empty_words.txt, number_claims.txt, sentences_in_two_docs.txt, long_sentences.txt. Your work is the judgement and what no scan can see.

HOW TO REPORT. Each finding: the exact place (file:line), the evidence (quote the document and the code or command that contradicts it), why it matters, and the smallest fix. proved=true only when you checked it against the code or the repository yourself; otherwise proved=false and say why you still believe it. Prefer 5 real findings over 25 guesses; about 15 targeted checks, the strongest first -- the owner's usage is limited this week: read the functions and sections you need, not whole files you do not. A clean, well-checked area is a real result: say what you checked in 'covered'. End with an honest coverage confession: what you did NOT check.
`

const AREAS = SIDE === 'desktop' ? [
  { key: 'w3d2-fixes-tools', focus: `FIRST, ROUND 1'S DESKTOP FIXES BY NAME (6d49492, 5b460ed, 531de6a; see ROUND 1'S FIXES below), then THE DESKTOP'S TOOLS AND TESTS AS CODE: ${DESKTOP}\\tools\\*.py, qa\\*.py (the stories and _qa_support.py included) and test_*.py. In the tools and tests: gates whose docstring promises more than they check, or that cannot fail (read what each check_*.py actually compares); helpers copied between qa scripts (scan: duplicate_bodies.txt lists five pairs -- one thing told twice, or two that only look alike?); swallowed exceptions in the tools (scan: swallowed_exceptions.txt, the tools/qa/test lines), especially in what guards the owner's machine and data (tools/guest.py, run_tests.py, linux_ci.py, mutate.py); dead tools or dead options in them; docstrings and --help texts that no longer say what the tool does; checks in the tests that assert nothing a regression could change (sample some). Read only; never run a suite, a qa script, a story, mutate.py, run_tests.py or linux_ci.py.` },
  { key: 'w3d2-history-site', focus: `THE DESKTOP'S HISTORY DOCUMENTS AND ITS SITE: ${DESKTOP}\\docs\\ROADMAP.md, docs\\ISSUES_LOG.md (large: read its index, its structure, the stories of the last two weeks, and sample older ones), CHANGELOG.md (its index and the last three versions; its bullet counts are an invariant), docs\\archive\\*.md, and site\\ (README.md, the page texts under site/src, and what site/build.py claims or counts). History is preserved: flag only text that claims to describe the PRESENT and is false (a ROADMAP item listed as pending that has shipped, or as shipped that has not; a "today the app does" that it no longer does), indexes and tables of contents that miss or misname entries, anchors that lead nowhere, contradictions with the code about the present, one topic told in full in two homes, and text that reads generated (empty words, filler, run-on sentences -- the scan's empty_words.txt and long_sentences.txt list candidates). The site is public: every number and feature it states must be true of the app today.` },
] : [
  { key: 'w3a2-fixes-tests', focus: `FIRST, ROUND 1'S PHONE FIXES BY NAME (4287cff, 394c705; see ROUND 1'S FIXES below), then THE PHONE'S TESTS AND TOOLS AS CODE: ${ANDROID}\\app\\src\\test (31 suites and Shares.kt), tools\\*.py and tools\\emulator\\*.py. In them: tests that cannot fail or that prove a property on a copy of the code rather than the code the app runs (round 1 found the delete and share tests doing that: look for more of the same kind -- helpers in app/src/main called only from tests, a test helper re-implementing a rule); helpers duplicated across suites; gates whose docstring promises more than they check (read what each check_*.py compares, and what the fixture makers make); swallowed errors in the tools, especially in what guards the owner's phone and machine (emulator_only.py, desktop_guest.py, walk.py's adb door); dead tools or options; comments telling history instead of a reason. Read only; no gradle, no adb, no emulator.` },
  { key: 'w3a2-history', focus: `THE PHONE'S HISTORY DOCUMENTS: ${ANDROID}\\docs\\ISSUES_LOG.md (large: read its index, its structure, the stories of the last two weeks, and sample older ones) and CHANGELOG.md (its index and the last three versions; bullet counts are an invariant), plus docs/STATUS.md's parts that tell history (the phases, the verification stories). History is preserved: flag only text that claims to describe the PRESENT and is false, indexes and tables of contents that miss or misname entries, anchors that lead nowhere, contradictions with the code about the present (a function a story names as live that is gone -- round 1 removed several: Notebook.deleteNote, applyShareCode, shareCodeFor, updateTable, splitBody), one topic told in full in two homes, and text that reads generated (empty words, filler, run-on sentences -- the scan's empty_words.txt and long_sentences.txt list candidates).` },
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
log(`${SIDE} wave 3 round 2: ${found.length} findings from ${reports.filter(Boolean).length} finders, ${weighty.length} of medium or above sent to the skeptic; the lows kept as reported`)
log('not covered this round, by the rotation: the app code and reader-facing documents beyond round 1 fixes (round 3, if this round is clean)')
let verdicts = null
if (weighty.length) {
  verdicts = await agent(verifierPrompt(weighty), { label: `refute:${SIDE}`, phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
