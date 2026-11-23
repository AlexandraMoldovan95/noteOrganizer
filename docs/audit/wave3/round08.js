// The final audit: run wf_a92b6d99-729, started 2026-11-02 19:35 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave3-slop-round8',
  description: 'Final audit, wave 3 (AI slop), round 8, one app (args.side), the small closing round the owner chose: one read-only finder re-attacking rounds 6 and 7 fixes by name, a skeptic re-checks findings of medium or above',
  phases: [
    { title: 'Find', detail: 'one finder on the fixes of rounds 6-7, read-only' },
    { title: 'Refute', detail: 'one skeptic re-checks the findings of medium or above, merges duplicates' },
  ],
}

const SIDE = args && args.side === 'android' ? 'android' : 'desktop'
const W3 = '<scratchpad>\\wave3'
const SCRATCH = W3 + '\\r8' + (SIDE === 'android' ? 'a' : 'd')
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
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 3: the "AI slop" scan the owner asked for in her words: "We both know the apps are built with AI, but that does not mean they should not be made well." Waves 0-1 and a lows wave already closed: data safety, hostile input and crashes were attacked for twenty-five rounds, so this wave is not a general bug hunt (rounds 6-7 read behaviour only on the roads a person takes, named in your area). Find what makes the code or the documentation read as generated rather than written for its reader -- and anything either one says that is not true.

WHAT TO LOOK FOR
- Code: dead or never-called code; helpers duplicated that answer the same question (the next fix lands on one); try/except or catch that swallows errors with no reason given; defensive checks for cases the code makes impossible; comments that repeat the code or tell history instead of why; names inconsistent for one thing between the desktop and the phone; huge functions that should be split (only where it hurts a reader -- do not propose refactors for taste); parameters or options nobody uses; tests that cannot fail; TODOs, placeholders, invented APIs.
- Documents: filler and repetition; marketing or empty words; claims the code does not support; stale numbers; contradictions between documents; one topic explained in full in two places (the project's rule is one canonical home per topic -- CLAUDE.md, "Documentation standards"); sentences far too long; text that sounds generated rather than written for its reader.

SEVERITY FOR THIS WAVE -- THE OWNER'S NARROWED BAR, from round 6 on (her decision on 2 Nov, after five rounds each of which found medium-grade drift in a different unread corner). Only these keep a round open (medium or above); the rounds stop after two in a row with none:
- (a) what a PERSON USING THE APP meets that is false or misleading: docs/USER_GUIDE.md, docs/PRIVACY.md, README's parts for users, the texts the app itself shows (dialogs, messages, buttons, the in-app shortcuts page, Settings and About, strings.xml on the phone), and the public site's pages;
- (b) anything that can lose or corrupt a person's notes, or crash or freeze the app;
- (c) code that BEHAVES wrong on a road a person takes: a key or button that does not do what it says, two copies of one rule that already answer differently where a person can reach it, an error swallowed so that a person's action silently does the wrong thing.
high = (a) false about what the app keeps, sends, deletes or protects, or any (b); medium = the rest of (a) and (c).
EVERYTHING ELSE IS LOW, recorded and fixed later in bulk: internal documents (CLAUDE.md, qa/README, ARCHITECTURE, CODE_TOUR, DATA_FORMAT, STATUS, AI_WORKFLOW, the tools' READMEs, ISSUES_LOG, CHANGELOG, ROADMAP), docstrings and comments, dead code, duplicated helpers that agree, tests or gates that cannot fail, style and taste. Report lows briefly; a cluster of one kind is ONE finding with a count and three examples. Say for each medium which of (a), (b), (c) it is, and the road a person takes to meet it.

HISTORY IS PRESERVED, NOT FALSE. docs/ISSUES_LOG.md stories, CHANGELOG.md entries and ROADMAP history describe the past; a past statement there is not wrong because the code changed later. Flag only text that claims to describe the present. CHANGELOG's bullet counts are an invariant (the version number is derived from them). docs/IN_MY_WORDS.md and docs/BUG_REPORTS.md are the owner's own voice: flag false facts only, never her tone.

ALREADY DECIDED -- do not report: no Terms & Conditions and no "Agree" screen; nothing in git history is rewritten (an old note "mate" in the phone's history, six photographs with a strip of desktop in the desktop's); commit messages and PR texts are history. Known and counted already: the comment gate's BRIEF list (desktop tools/check_comments.py) is partial on purpose -- "a module joins BRIEF once it has been condensed" -- so report the uncondensed remainder as ONE finding with its measure and the five worst examples, not comment by comment; swallowing tk.TclError on a widget that may already be destroyed is the desktop's idiom -- report one only if it hides something other than a gone widget. The phone's ExampleInstrumentedTest.kt (a template leftover) waits on the owner's yes -- report it once, as a low, if it is still there.

ROUND 8, THE CLOSING ROUND. Rounds 6 and 7, under the owner's narrowed bar, each read new roads and found real defects there (round 7: a high and three mediums on each app), all fixed. The owner chose to close the wave with one small round that re-attacks THOSE FIXES BY NAME and nothing else: is each fix right, complete on its own road, and did it break a neighbour (another caller, a text that says the old thing, a test that now proves less)? Do NOT go looking along roads no fix touched -- what is still unread is known and is left for a later wave. If this round finds nothing of medium or above, the wave closes.

ROUND 7'S FIXES, to re-attack by name (read the commits with git show):
- Desktop, branch audit/d-val3: 14d6449 (split_by_identity: the first arrival claims an identity, a second comes in without it; bind_class("Entry") swallows Ctrl+D, Ctrl+K and Ctrl+T; _cleanup_selected_duplicates stops merging at MAX_ATTACHMENTS, its hint says the rest stay in the Trash; _dup_key and SAME_AS take in a series' own days -- exceptions, overrides, moved; the imported one-note code says it is saved as a new note; checks in test_note_identity, test_data_safety, qa4, qa6; mutants WS12-WS15, MN01 and WS02 re-aimed) and e7296b7 (USER_GUIDE's Duplicates names a repeating note's own days).
- Phone, branch audit/a-val3: 4ffe5d1 (EditorModel.typeInCell holds a cell's words that read as a box's or a merge's mark, writeHeldCell writes them when the cell is left -- CellEditor's DisposableEffect -- before editTable, editColumns, mergeCells, setRowLines, the calculator, Undo and Redo, and in write(); Organizing.cleanUpDuplicates stops at Normalize.MAX_ATTACHMENTS and dup_merge_note says so; Normalize.dupKey takes in seriesDaysSignature and the three duplicate texts name it; the backup switch's Off line names a move to a new phone; walk.py's photo check on the Off line).

ROUND 6'S FIXES, to re-attack by name too:
- Desktop, branch audit/d-val3: fbb8330 (_leave_note_by_keys: Ctrl+Tab / Ctrl+Shift+Tab from the note's text and from an open table cell go through Tk's <<NextWindow>> / <<PrevWindow>>, the cell committed first; FORMAT_KEYS listed once, the open cell styling with them through _toggle_body_style; _swallow_format_keys on the comments box, the template editor's text boxes and the import box; the category delete question with notes defaults to Cancel; three export/import messages name Settings → Backup → Import; the Duplicates subtitle names a "(copy)", the styling and the pin; the shortcuts page's group "Text formatting, in the note"; qa5 and qa6 checks, mutants WS08-WS11) and 64669c5 (USER_GUIDE: the Trash's Select all and "Delete N selected permanently", the update copies a deleted note stays in, what a backup import brings back, what Duplicates ignores, the formatting keys' row, the Expand sentence, Settings → General → Your name, the crash log's line; PRIVACY: the copies of the notes file the app keeps and never deletes, dated 2 November).
- Phone, branch audit/a-val3: 9f1a5aa (strings.xml: backup_google_off says Android's NEXT backup replaces the Google copy; dup_explain names a "(copy)", the styling and the pin among what is ignored).

EARLIER ROUNDS' FIXES (rounds 1-5, each attacked at least twice since): read them again only where your area meets them -- git log --oneline main..audit/d-val3 (desktop) and main..audit/a-val3 (phone) list every commit of this wave.
Ask of each: is the new text true against the code? Did the change break a sibling (another text, a link, an anchor, a caller, a test that now proves less)? Did a removal take anything still needed (a mutant in tools/mutants.json, a tool, a document that names it)? Did a dated or linked number leave another copy of it stale?

ALREADY RECORDED as lows (do not report again): every '### <key> (<title>)' heading in ${W3}\\lows.md (six rounds of them, and the 'Needs her eye' items) -- grep it before reporting a low; a low already there is not a finding.

GROUND TRUTH AT HEAD (do not recompute; use it for number claims). Desktop ${DESKTOP}, branch audit/d-val3: the entry file note_organizer.py has about 24,350 lines; noteorganizer/core has 18 modules and noteorganizer/ui 7 mixins; the full suite on Windows is 27 suites, 4,869 checks (unit suites 1,298, qa suite 3,571), all passing; on Linux 4,841, all passing, two SKIPs named (qa1's sidebar width, qa5's multi-script widget routes); tools/mutants.json holds 1,004 entries; the test plan holds 859 cases, IDs to 966; the site builds. Phone ${ANDROID}, branch audit/a-val3: 936 unit tests pass, 0 fail, in 31 suites; 8 gates pass (check_interop.py the eighth); the emulator walk has 70 parts (its last full run, 2 Nov, of the 67 there were then: 533 checks passed, 20 failed, both causes the walk's own and fixed; the three added parts are not yet run in a full walk -- known, the next full walk before an install runs them); the test plan holds 424 cases, IDs to 430.

THE MECHANICAL SCAN (free, already run, in ${SCAN}): candidate lists with false hits -- judge them against the code, never trust them. Each file says in its name what it lists; the documents' lists are empty_words.txt, number_claims.txt, sentences_in_two_docs.txt, long_sentences.txt. Your work is the judgement and what no scan can see.

HOW TO REPORT. Each finding: the exact place (file:line), the evidence (quote the document and the code or command that contradicts it), why it matters, and the smallest fix. proved=true only when you checked it against the code or the repository yourself; otherwise proved=false and say why you still believe it. Prefer 5 real findings over 25 guesses; about 15 targeted checks, the strongest first -- the owner's usage is limited this week: read the functions and sections you need, not whole files you do not. A clean, well-checked area is a real result: say what you checked in 'covered'. End with an honest coverage confession: what you did NOT check.
`

const AREAS = SIDE === 'desktop' ? [
  { key: 'w3d8-fixes', focus: `THE DESKTOP'S FIXES OF ROUNDS 6 AND 7, BY NAME (fbb8330, 64669c5, 14d6449, e7296b7 in ${DESKTOP}; read each with git show, then the code around it). For each: is it right on the road a person takes (walk it in the code: the keys, the import routes -- share code and backup -- the clean-up's question and its Trash, the Entry boxes that take typing), is the same mechanism answered the same way everywhere it is asked (git grep the siblings), does every text that describes it -- the shortcuts page, USER_GUIDE, PRIVACY, the in-app messages, the site's demo -- now say what the code does, and does each new check fail when its fix is undone? Read only; never run a suite, a qa script, a story, mutate.py, run_tests.py or linux_ci.py.` },
] : [
  { key: 'w3a8-fixes', focus: `THE PHONE'S FIXES OF ROUNDS 6 AND 7, BY NAME (9f1a5aa, 4ffe5d1 in ${ANDROID}; read each with git show, then the code around it). For each: is it right on the road a person takes (a cell typed into and left -- by tapping another cell, the text, Back, Home, the bar's buttons, the calculator, Undo; the clean-up's question and its Trash; the backup switch), is the same mechanism answered the same way everywhere it is asked (git grep the siblings: every field that holds words back, every merge of files, every duplicate text), does every text that describes it -- strings.xml, README, the privacy policy's phone parts in ${DESKTOP}\\docs\\PRIVACY.md, the site's Android demo -- now say what the code does, and does each new test fail when its fix is undone? Read only; no gradle, no adb, no emulator.` },
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
log(`${SIDE} wave 3 round 8: ${found.length} findings from ${reports.filter(Boolean).length} finders, ${weighty.length} of medium or above sent to the skeptic; the lows kept as reported`)
log('round 8 reads under the narrowed bar: what a person meets, what can lose notes, code that behaves wrong; internal texts are lows')
let verdicts = null
if (weighty.length) {
  verdicts = await agent(verifierPrompt(weighty), { label: `refute:${SIDE}`, phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
