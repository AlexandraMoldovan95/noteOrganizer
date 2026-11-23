// The final audit: run wf_ef11a046-5ae, started 2026-11-02 13:03 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave3-slop-round1',
  description: 'Final audit, wave 3 (AI slop), round 1, one app (args.side): a read-only finder on the app code and one on the reader-facing documents, each judging the mechanical scan and looking past it; a skeptic re-checks findings of medium or above',
  phases: [
    { title: 'Find', detail: 'code finder + documents finder, read-only' },
    { title: 'Refute', detail: 'one skeptic re-checks the findings of medium or above, merges duplicates' },
  ],
}

const SIDE = args && args.side === 'android' ? 'android' : 'desktop'
const W3 = '<scratchpad>\\wave3'
const SCRATCH = W3 + '\\r1' + (SIDE === 'android' ? 'a' : 'd')
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

ROUND 1 COVERS the app's own code and the reader-facing documents. Round 2 takes tools/, qa/, the tests, site/, ROADMAP, ISSUES_LOG, CHANGELOG and docs/archive -- leave those (you may read them to check a claim).

GROUND TRUTH AT HEAD (do not recompute; use it for number claims). Desktop ${DESKTOP}, branch audit/d-lows: the entry file note_organizer.py has 24,401 lines; noteorganizer/core has 18 modules and noteorganizer/ui 7 mixins; the full suite is 27 suites, 4,842 checks on Windows and 4,815 on Linux, all passing; the test plan's case IDs run to 966. Phone ${ANDROID}, branch audit/a-lows: 937 unit tests pass, 0 fail; 7 gates; the emulator walk has 67 parts (its last full run: 533 checks passed, 20 failed, both causes the walk's own and fixed); the test plan's rows run to 430.

THE MECHANICAL SCAN (free, already run, in ${SCAN}): candidate lists with false hits -- judge them against the code, never trust them. Each file says in its name what it lists; the documents' lists are empty_words.txt, number_claims.txt, sentences_in_two_docs.txt, long_sentences.txt. Your work is the judgement and what no scan can see.

HOW TO REPORT. Each finding: the exact place (file:line), the evidence (quote the document and the code or command that contradicts it), why it matters, and the smallest fix. proved=true only when you checked it against the code or the repository yourself; otherwise proved=false and say why you still believe it. Prefer 5 real findings over 25 guesses; about 15 targeted checks, the strongest first -- the owner's usage is limited this week: read the functions and sections you need, not whole files you do not. A clean, well-checked area is a real result: say what you checked in 'covered'. End with an honest coverage confession: what you did NOT check.
`

const AREAS = SIDE === 'desktop' ? [
  { key: 'w3d-code', focus: `THE DESKTOP APP'S CODE: ${DESKTOP}\\note_organizer.py and ${DESKTOP}\\noteorganizer (core/ never imports tkinter; ui/ holds the mixins). Start from the scan: dead_candidates.txt; unused_params.txt (is the parameter part of a signature a caller or Tk dictates? then it is fine); swallowed_exceptions.txt (the app's ~30 that are NOT tk.TclError alone -- OSError, IOError, Exception, ValueError -- especially on paths that read or write files); print_calls_app.txt; comment_runs_over_3.txt (measure it; read the 20 longest: does each give a reason, or tell a story that belongs in ISSUES_LOG?). Then what no scan sees: helpers in the hub and core/ that answer the same question (two that normalise, clamp, format a date, escape text, count words, compare bodies...; tools/check_one_definition.py already guards some -- read its rules first); defensive checks for cases the code makes impossible; settings, options or flags nothing sets or reads; docstrings that promise what the function no longer does (sample 20 in core/ against their bodies); names a reader would map across the two apps that differ for one thing (the note's fields; compare with ${ANDROID}\\docs\\DATA_FORMAT.md).` },
  { key: 'w3d-docs', focus: `THE DESKTOP'S READER-FACING DOCUMENTS, in this order: README.md, docs/PRIVACY.md, docs/USER_GUIDE.md, CLAUDE.md, docs/ARCHITECTURE.md, docs/CODE_TOUR.md, qa/README.md, docs/AI_WORKFLOW.md, docs/RELEASE_WINDOWS.md, docs/RELEASE_ANDROID.md, docs/GIT_WORKFLOW.md, docs/TEST_PLAN_EXCERPT.md, docs/IN_MY_WORDS.md, docs/BUG_REPORTS.md, site/README.md (all under ${DESKTOP}). Check: every number and command in them against the repository (number_claims.txt lists the numbers); every file, function, gate or script they name (git grep); behaviours stated in the present tense that you can check in the code in a few minutes -- USER_GUIDE and PRIVACY first, since a user acts on them; contradictions between them; one topic told in full in two of them; and text that reads generated -- the empty words (empty_words.txt, mostly "very" and "simply": judge), filler openings, sentences over 55 words (long_sentences.txt), three adjectives where one would do, a paragraph that restates its heading. The standard they are held to: CLAUDE.md, "Documentation standards".` },
] : [
  { key: 'w3a-code', focus: `THE PHONE APP'S CODE: ${ANDROID}\\app\\src\\main (Kotlin, Jetpack Compose). Start from the scan: dead_fun_candidates.txt and dead_val_candidates.txt; duplicate_bodies.txt (are the twins really one thing told twice?); swallowed_catches.txt (35: which hide a failure on a path that reads or writes notes, backups, files or reminders, with no reason given?); comment_runs_over_3.txt (KDoc included; measure it; read the 20 longest: a reason, or a story that belongs in docs/ISSUES_LOG.md?). Then what no scan sees: helpers answering one question twice (body comparison beside Normalize.sameBody, date parsing in Recurrence/Stats/Days, clamps and limits written out twice); defensive checks for impossible cases; parameters and options nothing passes; Compose blocks copied rather than shared; KDoc that promises what the function no longer does (sample 20); names a reader maps across the two apps that differ for one thing (the note's fields: docs/DATA_FORMAT.md; the desktop is at ${DESKTOP}).` },
  { key: 'w3a-docs', focus: `THE PHONE'S READER-FACING DOCUMENTS: README.md, CLAUDE.md, docs/ARCHITECTURE.md, docs/DATA_FORMAT.md, docs/STATUS.md, qa/README.md, tools/emulator/README.md (all under ${ANDROID}). Check: every number and command in them against the repository (number_claims.txt); every file, function, gate or script they name (git grep); behaviours stated in the present tense that you can check in the code in a few minutes -- DATA_FORMAT first (the desktop reads the same file: compare it with the desktop's noteorganizer/core/model.py and storage.py where it makes a claim about the shared format), then STATUS; contradictions between them and with the desktop's docs where both describe the same thing; one topic told in full in two places; and text that reads generated -- empty words (empty_words.txt), filler openings, sentences over 55 words (long_sentences.txt), a paragraph that restates its heading. The standard: CLAUDE.md's documentation rules.` },
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
log(`${SIDE} wave 3 round 1: ${found.length} findings from ${reports.filter(Boolean).length} finders, ${weighty.length} of medium or above sent to the skeptic; the lows kept as reported`)
log('not covered this round, by the rotation: tools/, qa/, the tests, site/, ROADMAP, ISSUES_LOG, CHANGELOG, docs/archive (round 2)')
let verdicts = null
if (weighty.length) {
  verdicts = await agent(verifierPrompt(weighty), { label: `refute:${SIDE}`, phase: 'Refute', schema: VERDICT_SCHEMA })
}
return { reports, verdicts }
