// The final audit: run wf_f7b28c76-435, started 2026-11-02 16:19 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave3-slop-round5',
  description: 'Final audit, wave 3 (AI slop), round 5, one app (args.side): a read-only finder re-attacking round 4 fixes by name and then the app code round 3 left unread, one on the reader-facing documents round 3 left unread; a skeptic re-checks findings of medium or above',
  phases: [
    { title: 'Find', detail: 'fixes + app code finder, reader documents finder, read-only' },
    { title: 'Refute', detail: 'one skeptic re-checks the findings of medium or above, merges duplicates' },
  ],
}

const SIDE = args && args.side === 'android' ? 'android' : 'desktop'
const W3 = '<scratchpad>\\wave3'
const SCRATCH = W3 + '\\r5' + (SIDE === 'android' ? 'a' : 'd')
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

ROUND 5. Rounds 1 and 3 covered the app's own code and the reader-facing documents; rounds 2 and 4 the tools, tests, site and history documents. All four found mediums on both apps, all fixed (round 4: desktop 3, phone 6). The owner's rule: every fix is attacked again BY NAME, and the rounds stop only after two in a row find nothing of medium or above. Round 5 re-attacks round 4's fixes and reads what round 3 said it had NOT read (named in each area below).

ROUND 4'S FIXES, to re-attack by name (read the commits with git show):
- Desktop, branch audit/d-val3: 6343bd3 (the title bar's dark test asks DARK_THEMES; five checks guarded by hasattr on names the app never had now run -- qa5's purge check calls purge_expired_trash and checks the unreadable entries are kept, story_audit's chapter 6 calls core_days_left_in_trash, qa1 applies its template through _apply_template and checks it, qa2 and doc_screenshots use the real names; qa1's opening checks read the category and the template back from their files and run the search over the note with None fields; style_ttk's docstring; the ninth theme's recipe once, in themes.py, with make_icon --all and the contrast table) and 74d084e (CODE_TOUR points to that recipe).
- Phone, branch audit/a-val3: 718f769 (tools/check_interop.py, a new gate: the code InteropTest writes out, decoded by the desktop's decode_share_code and compared field by field with phone_note.json, which the test now writes beside it; make_paste_fixture.py retargeted to today's tables.align and paste_cases.json remade from today's desktop; Pasting's private isTableRow asks Notebook.kt's; type_code.py reads the screen through fresh_tree; comments on the calculator's depth, the backup switch, take_screenshots) and 9b22834 (STATUS's three differences the desktop closed; qa/README points to walk.py for the parts; tools/emulator/README says what each tool writes; the interop gate named in README, CLAUDE.md, STATUS, DATA_FORMAT).

ROUND 3'S FIXES (attacked by round 4; read again only where round 5's area meets them):
- Desktop, branch audit/d-val3: 5d3c59c (Reset on a moved day with its own text: default="Only the date", qa5 checks the focus; every other _themed_dialog with buttons of its own was judged and left; formatting.is_format_tag(name, fonts=True) and the four hand-written tag lists now asking it with fonts=False, the caption scrub asking it whole, qa1 checking a caption sheds an inherited size; apply_theme's ttk.Combobox styling and _recolor_existing_combo_popups removed; qa1's sidebar-width check and qa6's missing-dictionary note print SKIP; docstrings of themes.py, recurrence.py, regen_seam_map.py, pre_push_check.py; the Android demo's About text) and 2592c1d (ARCHITECTURE's theming section and three small maps; CODE_TOUR's clean_notes and ninth theme; qa/README's SKIP house rule and story_look's count).
- Phone, branch audit/a-val3: 13658da (Notebook.kt's isTableRow and splitRow strip with PyText.strip, Pasting.isRow asks Notebook.kt's isTableRow, Tables.cellAlignments reads a blank cell by PyText.strip, a TablesTest on U+0085; the manifest's backup comment and EditorModel.props' KDoc) and c816a67 (ARCHITECTURE names Android's own backup among the doors out and links the test count; ISSUES_LOG's "Two Trash restores" closed; DATA_FORMAT's 45% highlight; qa/README and check_note_shape's docstring on its fifth comparison).

ROUND 2'S FIXES (attacked by round 3; read again only where round 5's area meets them):
- Desktop, branch audit/d-val3: 1b27f95 (run_coverage.py reads run_tests' suite lists; pre_push_check.py runs check_mutant_targets and stops when git cannot list files; qa9's skipped keyboard checks print SKIP through a skip() helper and run_tests counts and names SKIP lines apart from PASS; site/build.py reads the phone's test and walk counts from the phone's qa/README; site/src/index.html and android-demo/android.js say the phone's Google backup copies notes while it is on; regen_seam_map.py finds its own root; comments about NOTEORG_SCRATCH and track_theme) and b5434bf (qa/README's seam map regenerated; CLAUDE.md says the qa suite and test_data_safety refuse without NOTEORG_SCRATCH; GIT_WORKFLOW and CODE_TOUR on pre_push_check; ROADMAP's two residuals settled; site/README names the parsed sentences; USER_GUIDE's crash-log entry head).
- Phone, branch audit/a-val3: ecdbe34 (Notebook.restoreFromTrash removed, the restore tests and the days fuzz on Organizing.restore through app/src/test/.../Trashed.kt; dup_explain names the key's six parts, OrganizingTest reads strings.xml to hold all three duplicate texts; Organizing.deletedAt reads a stamp to its end with a ParsePosition; a share test of a test helper removed) and 1a44fae (walk.py's main runs hostile_backups, code_read_away, long_lines -- 70 parts; emulator_only.fresh_tree used by walk, take_screenshots, tap_by_text; check_release_lookups and make_licenses --check fail when they read nothing; README's Google-backup sentence; ISSUES_LOG "Still open" items marked closed, its opening and count; STATUS's walk paragraph; CHANGELOG [Unreleased]'s note that it stops at round five).

ROUND 1'S FIXES (attacked by round 2; read again only where round 5's area meets them):
- Desktop, branch audit/d-val3: 6d49492 (duplicates.SAME_AS, one phrase for what a duplicate is, in every text that says it, held to _dup_key's length by a test; run_migrations case 1 keeps settings_replaced_<stamp>.json before replacing a readable settings.json, leaves the settings if that copy fails, copies with _copy_whole; _return_to_calendar's guard logs through _log_swallowed instead of a bare pass; removed as dead: _grid_read_rows, _grid_read_aligns, _grid_click, _settings_section_note, tables.to_rows, the "plus" glyph; tools/check_doc_links.py keeps an underscore inside a heading's code span) and 5b460ed (USER_GUIDE's crash-log promise scoped to each entry's first line; CODE_TOUR's new single_instance section; NOTEORG_SCRATCH=1 named in the by-hand run in CLAUDE.md, qa/README, ARCHITECTURE; the numbers rewritten and dated -- entry file ~24,000 lines, ~4,800 checks, 859 test-plan cases with recounted tables, eleven gates; the "already open" dialog named). And 531de6a: tools/check_english.py's docstring about the phone's language.
- Phone, branch audit/a-val3: 4287cff (Organizing.deletedAt, one strict parse for the Trash row's days left and the purge; Notebook.deleteNote, applyShareCode, shareCodeFor, updateTable and Tables' splitBody/BodyPart removed as code only tests ran; the delete tests now drive Organizing.trashNotes; the share tests use app/src/test/.../Shares.kt over Importing) and 394c705 (counts kept in qa/README, dated, the other documents linking there; the ARCHITECTURE map re-measured, GoogleBackup.kt added; permissions, uid minting, the desktop's notebook folder, the icon's 47% corrected; check_note_shape.py now also holds DATA_FORMAT.md's field list to the Python's).
Ask of each: is the new text true against the code? Did the change break a sibling (another text, a link, an anchor, a caller, a test that now proves less)? Did a removal take anything still needed (a mutant in tools/mutants.json, a tool, a document that names it)? Did a dated or linked number leave another copy of it stale?

ALREADY RECORDED as lows (do not report again): the desktop's uncondensed comments outside BRIEF; the phone's comments telling history; nine KDoc blocks cut off from their functions; KDocs promising old behaviour (5); parameters no caller passes (9); small rules spelled out by hand (find-by-id x7, the stamp format, '(untitled)'); the stamp literal written 15 times on the desktop; build_notes_tab's size; filler 'simply' and long sentences in USER_GUIDE and STATUS; README's commit count told twice; GIT_WORKFLOW's Scenario A; unused imports zlib, base64, timedelta in the desktop's entry file; NOWHERE/UNREADABLE written three times on the phone; Notebook.inspectShareCode's Load overload used by tests only; the unused nrows/dlg parameters on the desktop. From round 2: check_doc_links walks the disk rather than tracked files; check_one_definition's docstring describes five of its eight rules; three stale tool docstrings; qa helpers written several times; swallowed errors in the machine guards; the SAME_AS test compares counts only; three ROADMAP passages out of step; the site's "859 manual test cases, walked" while 263 are Not Tested; docs/archive registers reading as live; on the phone, more app functions only tests call (parseNotes, sameDate, showStamp...), checks that go quiet, duplicated test helpers and deleteOnExit calls, history in tool comments, ISSUES_LOG index cells grown long, STATUS's copies of the fixture counts and the walk's run-by-run history. From round 3: three comments calling a day's override plain text (fixed); the moved-field counts (fixed); recurrence.py's claim that a test pins the skip-ahead's speed; contradictory bulk-bar comments; always-true/false guards in the hub; _grid_drag_autoscroll's displaced docstring; formatting.py's "two kinds of style"; qa/README's qa9 ownership row; the in-app shortcuts page's "everything"; the table height cap; four stale docstrings; on the phone, deletedAt still not exactly strptime on a leading space or a tab, copied code in six files (5 spots), htmlToNote catching every Exception, an unused string cal_today, small drift in STATUS's what-works list. From round 4: TCombobox left in two typing-widget lists; make_icon's docstring (five designs); two checks half-made on one platform; verify_share_codes comparing a normalizer with itself; the commit counts in README and AI_WORKFLOW; the desktop demo's Enter-in-title; ISSUES_LOG's "Smaller lessons" with two orphan entries; on the phone, walk checks that pass without reading their premise (statistics and four more), cell-level trims with Kotlin's trim(), a calendar screenshot that cannot tell an empty grid, a styling test measuring both sides with the phone's normalizer, "Still open" holding closed desktop items marked three ways, the CHANGELOG with no version index, STATUS on cell styling.

GROUND TRUTH AT HEAD (do not recompute; use it for number claims). Desktop ${DESKTOP}, branch audit/d-val3: the entry file note_organizer.py has 24,381 lines; noteorganizer/core has 18 modules and noteorganizer/ui 7 mixins; the full suite on Windows is 27 suites, 4,854 checks (unit suites 1,294, qa suite 3,560), all passing; on Linux 4,826, all passing, two SKIPs named (qa1's sidebar width, qa5's multi-script widget routes); tools/mutants.json holds 994 entries; the test plan holds 859 cases, IDs to 966; the site builds. Phone ${ANDROID}, branch audit/a-val3: 933 unit tests pass, 0 fail, in 31 suites; 8 gates pass (check_interop.py the eighth); the emulator walk has 70 parts (its last full run, 2 Nov, of the 67 there were then: 533 checks passed, 20 failed, both causes the walk's own and fixed; the three added parts are not yet run in a full walk -- known, the next full walk before an install runs them); the test plan holds 424 cases, IDs to 430.

THE MECHANICAL SCAN (free, already run, in ${SCAN}): candidate lists with false hits -- judge them against the code, never trust them. Each file says in its name what it lists; the documents' lists are empty_words.txt, number_claims.txt, sentences_in_two_docs.txt, long_sentences.txt. Your work is the judgement and what no scan can see.

HOW TO REPORT. Each finding: the exact place (file:line), the evidence (quote the document and the code or command that contradicts it), why it matters, and the smallest fix. proved=true only when you checked it against the code or the repository yourself; otherwise proved=false and say why you still believe it. Prefer 5 real findings over 25 guesses; about 15 targeted checks, the strongest first -- the owner's usage is limited this week: read the functions and sections you need, not whole files you do not. A clean, well-checked area is a real result: say what you checked in 'covered'. End with an honest coverage confession: what you did NOT check.
`

const AREAS = SIDE === 'desktop' ? [
  { key: 'w3d5-fixes-code', focus: `FIRST, ROUND 4'S DESKTOP FIXES BY NAME (6343bd3, 74d084e; see ROUND 4'S FIXES below): does each rewritten check now fail when what it names breaks (qa5's purge, story_audit's chapter 6, qa1's template, category and search checks), and is the title bar's DARK_THEMES the only answer left to "is this theme dark" (git grep for others); is the ninth theme's recipe in themes.py complete and true (follow it in your head: would every gate pass?). THEN THE DESKTOP APP'S CODE WHERE ROUND 3 DID NOT READ (${DESKTOP}): the module docstrings of core/model.py, storage.py, sharing.py, paths.py, categories.py, spelling.py against their bodies; the TclError-only handlers round 3 judged from call lists only (about 50: read the try bodies); getattr/hasattr guards on attributes the build_* methods set during construction (body_text, _checklist_rows and the like) that are always true after __init__; the calendar's comments that count call sites ("thirty-one", "exactly four ways back") recounted. Read only; never run a suite, a qa script, a story, mutate.py, run_tests.py or linux_ci.py.` },
  { key: 'w3d5-docs', focus: `FIRST, ROUND 4'S DESKTOP DOCUMENT CHANGES BY NAME (74d084e and the docstrings in 6343bd3): true, no sibling left. THEN THE DESKTOP'S READER-FACING DOCUMENTS WHERE ROUND 3 DID NOT READ (all under ${DESKTOP}): docs/USER_GUIDE.md lines 400-660 (Attachments, Checklists, Calculator, Emoji, Reading time, Spelling, Finding notes, Organizing, Templates) against the code, claim by claim, and its "Moving one day" and "Moving or ending a series" sections; the rest of the keyboard table, every row traced to a binding (the list keys Enter/Backspace/Tab in a bulleted list, Ctrl+Tab, the picker keys); docs/CODE_TOUR.md lines 200-776 (calculator, recurrence, formatting, richtext/clipboard, spelling, tables) against their modules; README's and qa/README's coverage figure ("89%") against what run_coverage now measures, and whether it is dated. Check numbers, names and present-tense behaviour against the code; contradictions; one topic in two homes; text that reads generated.` },
] : [
  { key: 'w3a5-fixes-code', focus: `FIRST, ROUND 4'S PHONE FIXES BY NAME (718f769, 9b22834; see ROUND 4'S FIXES below): can tools/check_interop.py pass when the desktop reads a field wrong (does it compare every field the code carries, and could a stale phone_note.json pass?); does the remade paste_cases.json hold the phone to what today's desktop answers, and does make_paste_fixture still say why the phone differs where it does; does every caller of Pasting's private isTableRow get the same answer as before for the code-point positions it uses; is type_code.py's fresh read right. THEN THE PHONE APP'S CODE WHERE ROUND 3 DID NOT READ (${ANDROID}\\app\\src\\main): NoteEditor.kt's Compose tree (about lines 1,470-2,900 and 3,000-4,200); Pasting.kt's parser and reader (about 590-1,430) and its reflow and align (1,534 on); TableView.kt 200-439; Paragraphs.kt 395-758 (toggleList, Enter and Backspace); CalendarScreen.kt's History (400-604); TemplateScreens.kt's TemplatesPage, TemplateBody and TemplateEditor -- copied blocks, KDoc that promises what the code no longer does, impossible-case checks, helpers answering one question twice; strings.xml beyond the questions round 3 sampled. Read only; no gradle, no adb, no emulator.` },
  { key: 'w3a5-docs', focus: `FIRST, ROUND 4'S PHONE DOCUMENT CHANGES BY NAME (9b22834 and the docstrings in 718f769): true, no sibling left (every place that counts the gates now says eight, or links?). THEN THE PHONE'S READER-FACING DOCUMENTS WHERE ROUND 3 DID NOT READ (all under ${ANDROID}): docs/STATUS.md items 14, 15, 17-19, 25-28 and 32-36, each behaviour traced to the code; docs/DATA_FORMAT.md's off-schedule settlement (which formatting and lines a day's note takes) and the days-back-from-copy conditions (about :336-375), traced line by line through the Kotlin and the desktop's noteorganizer/core/model.py; DATA_FORMAT:239-256 (uid minting) against Normalize.kt and Importing.kt; ARCHITECTURE's map rows re-measured (46-120); the scan's empty_words.txt, long_sentences.txt and number_claims.txt for these documents, walked. Check claims against the code; contradictions; one topic in two homes; text that reads generated.` },
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
log(`${SIDE} wave 3 round 5: ${found.length} findings from ${reports.filter(Boolean).length} finders, ${weighty.length} of medium or above sent to the skeptic; the lows kept as reported`)
log('not covered this round, by the rotation: the tools, tests, site and history documents beyond round 4 fixes (round 6)')
let verdicts = null
if (weighty.length) {
  verdicts = await agent(verifierPrompt(weighty), { label: `refute:${SIDE}`, phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
