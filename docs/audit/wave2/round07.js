// The final audit: run wf_e233dd66-b06, started 2026-11-03 17:09 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave2-round7',
  description: 'Final audit, wave 2, round 7, both apps: per app one re-attacker of round 6\'s fixes by name and one finder on roads not walked yet; one skeptic per app on findings of medium or above',
  phases: [
    { title: 'Find', detail: 'per app: the fixes re-attacked, and untouched roads; read-only' },
    { title: 'Refute', detail: 'per app, one skeptic re-checks the findings of medium or above' },
  ],
}

const W2 = '<scratchpad>\\wave2'
const AUDIT = '<scratchpad>\\audit\\register.md'
const LOWS3 = '<scratchpad>\\wave3\\lows.md'
const LOWS2 = W2 + '\\lows_w2.md'
const R1 = W2 + '\\r1_list.txt'
const R2 = W2 + '\\r2_list.txt'
const R3 = W2 + '\\r3_list.txt'
const R4 = W2 + '\\r4_list.txt'
const R5 = W2 + '\\r5_list.txt'
const R6 = W2 + '\\r6_list.txt'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'
const DCOMMIT = args.desktop
const ACOMMIT = args.android

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project; on 2026-10-29 a test run took the owner's whole computer down -- not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Git: only log, show, diff, grep, ls-files, blame.
- Write ONLY inside your own folder, SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, any notebook_location.txt, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder -- use the Grep tool or git grep inside a repository.
- You READ the code and walk a person's road through it in your head. Never run the app, a test (qa*.py, test_*.py, story_*.py, gradle), tools/run_tests.py, tools/mutate.py, tools/linux_ci.py, docker, gradle, adb or the emulator -- one heavy job at a time is the rule on this machine. No network, no installing. You MAY run your own Python scripts in SCRATCH_DIR with 'py -I' that read source files as text (never import the app's code). If a command is refused, do not try another spelling -- note it under not_covered.
- Do not fix anything. Find, prove (from the code), report.
`

const WAVE = `
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 2: the app as an ORDINARY PERSON meets it, and as a CARELESS OR MISCHIEVOUS one uses it. Earlier waves attacked data safety, hostile files and huge inputs for twenty-five rounds; this wave is about a real person on an ordinary day: what they do, in what order, with what slips, and what the app then does to them. Rounds 1 to 6 found the roads listed in ${R1}, ${R2}, ${R3}, ${R4}, ${R5} and ${R6}; round 6's fixes are in the newest commit per app (below), the earlier rounds' in the commits before it.

SEVERITY -- THE OWNER'S RULE (1 Nov), it decides when the rounds stop:
- A finding keeps a round open (medium or above) only if it reproduces through ORDINARY STEPS a person takes. Rare roads -- a hand-edited file, many uncommon steps in a row, a clock set wrong on purpose -- are recorded as known (low), EXCEPT data loss.
- Data loss is always serious, however rare the road.
- high = notes, files or settings lost or corrupted; a crash or a freeze; the safe-looking answer of a question destroying something. medium = on an ordinary road, a person is misled or stuck: a button or key that does not do what it says, an action that silently does nothing or the wrong thing, a message that is false or leaves them with no way forward, a trap where the obvious choice is the bad one. low = everything else.
Rounds stop after two in a row with nothing of medium or above.

ALREADY FOUND -- do not report again: everything in ${AUDIT}, every '### <key>' heading in ${LOWS3}, every line of ${LOWS2}, of ${R1}, of ${R2}, of ${R3}, of ${R4}, of ${R5} and of ${R6}. ALSO DECIDED (the owner, round 3): the list's search does not read one day's own words of a repeating note; when it finds nothing and such a day holds the words, the empty list says so and links to the Calendar's History. DECIDED -- do not report: no Terms & Conditions screen; the phone has no "Follow the phone" theme; Store review is the feedback route; the app is offline on purpose; history in docs/ISSUES_LOG.md and CHANGELOG.md is the past. THE OWNER'S FOUR WAVE-2 CHOICES, which the fixes carry out -- do not argue them, attack how they were done: (1) a new note hidden by Show, a search or a folded group is said, with Show all, and an empty list names its filter and offers Show all; (2) every search on both apps (the list, Find in note, the History) ignores diacritics and case, and Title A-Z sorts a letter with a mark beside the letter; (3) text shared into the phone app that is not a code becomes a new note, a code with words around it is still a code; (4) the list's search looks in checklist rows, both apps.

HOW TO REPORT. Each finding: the steps a person takes (numbered), the exact code places (file:line), what the person sees, why it matters, the smallest fix. proved=true only when you traced it through the code yourself. Prefer 5 real findings over 25 guesses; the owner's usage is limited this week: read the functions you need, not whole files. A clean road is a real result: list what you walked in 'covered'. End with an honest coverage confession: what you did NOT walk.
`

const AREAS = [
  { side: 'desktop', key: 'w2d7-fixes', focus: `THE DESKTOP'S ROUND-6 FIX, RE-ATTACKED BY NAME (${DESKTOP}, commit ${DCOMMIT}: read it with git show; the commits before it are rounds 1-5). (a) _take_back_aside: the words put back only in part, or put back and changed by one letter; the aside opened and edited (or only opened) before the words come back; two big deletes in a row, then one Ctrl+Z; the words put back after a restart or after another note was opened; the aside already in the Trash, or renamed; the status line it holds; is anything lost, or does a note the person wanted vanish. (b) comments_only: the comments cleared together with a big delete in the same save; the aside's title, category, date and the banner's words. (c) _see_cell: Find's next and previous across a tall table and back into prose; Tab and Shift+Tab across rows; a cell clicked with the mouse; a small window; a table at the very end of a note; the view restored when the cell editor closes -- does the note jump, or does the box scroll on its own while a person reads.` },
  { side: 'desktop', key: 'w2d7-roads', focus: `THE DESKTOP, ROADS NOT WALKED YET (${DESKTOP}). Read ${R1} to ${R6} (the files named above) for what was walked, then walk others an ordinary person takes in the first week: the Trash (Settings -> Recently deleted): Restore of a note whose category was deleted meanwhile, Restore twice, Empty, a note deleted while its tab is open; a category renamed or deleted with notes in it, then Undo; a checklist edited by keys (Enter on an empty row, Backspace at a row's start, a row dragged); a template made, edited and deleted while a note made from it is open; a link in a note opened.` },
  { side: 'android', key: 'w2a7-fixes', focus: `THE PHONE'S ROUND-6 FIXES, RE-ATTACKED BY NAME (${ANDROID}, commit ${ACOMMIT}: read it with git show; the commits before it are rounds 1-5). (a) font_size as em against 12 and linesGrown in NoteEditor's paintLines: a size span that runs across two lines, or covers only part of a line; a size on a checklist row or in a table cell; the list's preview, the read view, the share code and the PDF -- do they all agree; typing at the end of a sized span; a size of 6 or 96; the cursor and the selection handles on a grown line; a long note's speed (the per-line work on every keystroke). (b) the keyboard foot as a Spacer of windowInsetsBottomHeight(ime) in the list and the History: a short list, an empty list with its Show all and History link, the keyboard up while selecting notes, a tablet with the list beside the editor, the phone turned, the keyboard opened from the editor beside the list.` },
  { side: 'android', key: 'w2a7-roads', focus: `THE PHONE, ROADS NOT WALKED YET (${ANDROID}). Read ${R1} to ${R6} (the files named above) for what was walked, then walk others an ordinary person takes in the first week: the Trash: Restore of a note whose category was deleted meanwhile, Restore twice, Empty; a category renamed or deleted with notes in it; the checklist edited by keys (Enter on an empty row, Backspace at a row's start, a row moved); several notes selected and deleted or moved, then Undo; the back gesture from every screen with something half-typed; a backup made and read back on the same phone.` },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      key: { type: 'string' }, title: { type: 'string' },
      severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
      kind: { type: 'string' }, steps: { type: 'string' }, where: { type: 'string' },
      evidence: { type: 'string' }, proved: { type: 'boolean' },
      why_it_matters: { type: 'string' }, fix_idea: { type: 'string' },
    }, required: ['key', 'title', 'severity', 'kind', 'steps', 'where', 'evidence', 'proved', 'why_it_matters', 'fix_idea'] } },
    covered: { type: 'string' }, not_covered: { type: 'string' },
  },
  required: ['findings', 'covered', 'not_covered'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: { type: 'array', items: { type: 'object', properties: {
      key: { type: 'string' },
      verdict: { type: 'string', enum: ['confirmed', 'plausible', 'refuted', 'already-known', 'duplicate'] },
      severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
      ordinary_steps: { type: 'boolean' },
      duplicate_of: { type: 'string' }, reason: { type: 'string' },
    }, required: ['key', 'verdict', 'severity', 'ordinary_steps', 'reason'] } },
    not_checked: { type: 'string' },
  },
  required: ['verdicts', 'not_checked'],
}

function finderPrompt(area) {
  return `You are an auditor in the final audit of Note Organizer, an offline notes app with a desktop version (Python + Tkinter, ${DESKTOP}, branch audit/d-val2) and a phone version (Kotlin, ${ANDROID}, branch audit/a-val2) that read the same notebook format. Your one area:

${area.focus}

SCRATCH_DIR = ${W2}\\r7\\${area.key}
${SAFETY}
${WAVE}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(side, found) {
  return `You are the skeptic for the ${side} app's wave-2 round-7 findings in the final audit of Note Organizer (desktop ${DESKTOP}, phone ${ANDROID}). For EACH finding below, try to REFUTE it: re-trace the steps through the code yourself -- does the handler really do that, is there a guard the auditor missed, does the screen say something else, is it already known (grep the files named under ALREADY FOUND), is it one of the owner's choices, or are two findings one? Then answer ordinary_steps, and re-grade severity by the owner's rule. "confirmed" only when you traced it yourself; "plausible" when you cannot settle it.

SCRATCH_DIR = ${W2}\\r7\\skeptic-${side}
${SAFETY}
${WAVE}
FINDINGS (JSON):
${JSON.stringify(found, null, 1)}

Return one verdict per finding key. Name what you could not check under not_checked.`
}

const results = {}
await parallel(['desktop', 'android'].map(side => async () => {
  const reports = await parallel(AREAS.filter(a => a.side === side).map(area => () =>
    agent(finderPrompt(area), { label: `find:${area.key}`, phase: 'Find', schema: FINDINGS_SCHEMA })
      .then(r => r ? { area: area.key, ...r } : { area: area.key, findings: [], covered: '', not_covered: 'AGENT RETURNED NOTHING' })))
  const found = reports.filter(Boolean).flatMap(r => r.findings.map(f => ({ ...f, area: r.area })))
  const weighty = found.filter(f => f.severity !== 'low')
  log(`${side} wave 2 round 7: ${found.length} findings, ${weighty.length} of medium or above to the skeptic; lows kept as reported`)
  let verdicts = null
  if (weighty.length) {
    verdicts = await agent(verifierPrompt(side, weighty), { label: `refute:${side}`, phase: 'Refute', schema: VERDICT_SCHEMA })
  }
  results[side] = { reports, verdicts }
}))
return results
