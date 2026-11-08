// The final audit: run wf_3c870f12-02b, started 2026-11-03 18:50 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave2-round8',
  description: 'Final audit, wave 2, round 8, both apps: per app one re-attacker of round 7\'s fixes by name and one finder on roads not walked yet; one skeptic per app on findings of medium or above',
  phases: [
    { title: 'Find', detail: 'per app: the fixes re-attacked, and untouched roads; read-only' },
    { title: 'Refute', detail: 'per app, one skeptic re-checks the findings of medium or above' },
  ],
}

const W2 = '<scratchpad>\\wave2'
const AUDIT = '<scratchpad>\\audit\\register.md'
const LOWS3 = '<scratchpad>\\wave3\\lows.md'
const LOWS2 = W2 + '\\lows_w2.md'
const LISTS = [1, 2, 3, 4, 5, 6, 7].map(n => `${W2}\\r${n}_list.txt`)
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'
const DCOMMITS = args.desktop
const ACOMMITS = args.android

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project; on 2026-10-29 a test run took the owner's whole computer down -- not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Git: only log, show, diff, grep, ls-files, blame.
- Write ONLY inside your own folder, SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, any notebook_location.txt, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder -- use the Grep tool or git grep inside a repository.
- You READ the code and walk a person's road through it in your head. Never run the app, a test (qa*.py, test_*.py, story_*.py, gradle), tools/run_tests.py, tools/mutate.py, tools/linux_ci.py, docker, gradle, adb or the emulator -- one heavy job at a time is the rule on this machine. No network, no installing. You MAY run your own Python scripts in SCRATCH_DIR with 'py -I' that read source files as text (never import the app's code). If a command is refused, do not try another spelling -- note it under not_covered.
- Do not fix anything. Find, prove (from the code), report.
`

const WAVE = `
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 2: the app as an ORDINARY PERSON meets it, and as a CARELESS OR MISCHIEVOUS one uses it. Earlier waves attacked data safety, hostile files and huge inputs for twenty-five rounds; this wave is about a real person on an ordinary day: what they do, in what order, with what slips, and what the app then does to them. Rounds 1 to 7 found the roads listed in ${LISTS.join(', ')}; round 7's fixes are in the newest commits per app (below), the earlier rounds' in the commits before them.

SEVERITY -- THE OWNER'S RULE (1 Nov), it decides when the rounds stop:
- A finding keeps a round open (medium or above) only if it reproduces through ORDINARY STEPS a person takes. Rare roads -- a hand-edited file, many uncommon steps in a row, a clock set wrong on purpose -- are recorded as known (low), EXCEPT data loss.
- Data loss is always serious, however rare the road.
- high = notes, files or settings lost or corrupted; a crash or a freeze; the safe-looking answer of a question destroying something. medium = on an ordinary road, a person is misled or stuck: a button or key that does not do what it says, an action that silently does nothing or the wrong thing, a message that is false or leaves them with no way forward, a trap where the obvious choice is the bad one. low = everything else.
Rounds stop after two in a row with nothing of medium or above.

ALREADY FOUND -- do not report again: everything in ${AUDIT}, every '### <key>' heading in ${LOWS3}, every line of ${LOWS2} and of each of ${LISTS.join(', ')}. ALSO DECIDED (the owner, round 3): the list's search does not read one day's own words of a repeating note; when it finds nothing and such a day holds the words, the empty list says so and links to the Calendar's History. DECIDED -- do not report: no Terms & Conditions screen; the phone has no "Follow the phone" theme; Store review is the feedback route; the app is offline on purpose; history in docs/ISSUES_LOG.md and CHANGELOG.md is the past. THE OWNER'S FOUR WAVE-2 CHOICES, which the fixes carry out -- do not argue them, attack how they were done: (1) a new note hidden by Show, a search or a folded group is said, with Show all, and an empty list names its filter and offers Show all; (2) every search on both apps (the list, Find in note, the History) ignores diacritics and case, and Title A-Z sorts a letter with a mark beside the letter; (3) text shared into the phone app that is not a code becomes a new note, a code with words around it is still a code; (4) the list's search looks in checklist rows, both apps.

HOW TO REPORT. Each finding: the steps a person takes (numbered), the exact code places (file:line), what the person sees, why it matters, the smallest fix. proved=true only when you traced it through the code yourself. Prefer 5 real findings over 25 guesses; the owner's usage is limited this week: read the functions you need, not whole files. A clean road is a real result: list what you walked in 'covered'. End with an honest coverage confession: what you did NOT walk.
`

const AREAS = [
  { side: 'desktop', key: 'w2d8-fixes', focus: `THE DESKTOP'S ROUND-7 FIXES, RE-ATTACKED BY NAME (${DESKTOP}, commits ${DCOMMITS}: read them with git show; the commits before them are rounds 1-6). (a) open_note_in_tab now looks the note up again by uid after its flush, and refuses with 'That note is no longer here' when it is gone: walk all of its callers (git grep open_note_in_tab), the flush=False ones, a note opened from the calendar, the welcome note, Undo of a delete, a duplicate, the last note opened at start -- can any legitimate open now be refused, or open a different note that wears the same uid, or leave the calendar's way back or the card highlight wrong? (b) _kept_asides as a list per note, spent by words_lost == 0: can an aside the person still needs be removed (its words present but its table, formatting, checklist or comments not; the words back in the note only for a moment; Ctrl+Z through several states), or one never be spent? (c) _see_cell measured before it moves: Find next/previous, Tab and Shift+Tab, Enter inside a cell, a click on a cell, a small window, a table at the end of a note. (d) the template editor's close button asking: Save, Don't save, Cancel, a name left empty or already taken, the window closed while it asks.` },
  { side: 'desktop', key: 'w2d8-roads', focus: `THE DESKTOP, ROADS NOT WALKED YET (${DESKTOP}). Read the round lists named above for what was walked, then walk others an ordinary person takes in the first week: the note list from the keyboard (Up, Down, Delete, Enter, Home, End) and several notes selected with Shift or Ctrl then deleted, pinned or exported; the Settings page's appearance (theme switch and Sharp text with a note open and unsaved); the spell check's suggestions menu and 'Add to dictionary'; an attachment opened, renamed or removed; Statistics; the duplicates finder.` },
  { side: 'android', key: 'w2a8-fixes', focus: `THE PHONE'S ROUND-7 FIXES, RE-ATTACKED BY NAME (${ANDROID}, commits ${ACOMMITS}: read them with git show; the commits before them are rounds 1-6). (a) moveToCategory's Undo (Organizing.filedNow / putBackFiled): the open note among those moved and typed into before Undo; Undo after one of the notes was deleted, or restored from the Trash under a new id; a category renamed or deleted meanwhile; a second move before the first's Undo; what the message bar then says. (b) writeStaying / saveStaying: every caller of flush and of outside() (closes or not), beforeImport, leaving -- can words in 'A new item...' now be lost (the note closed, the app ended, an import replacing the note), or a row rename not written? (c) the key watch (rowsHaveKeys, findHasKeys, calcHasKeys set by onFocusChanged): can one stay true after its box is gone or folded, so Ctrl+Z in the body does nothing; the Column wrapper around the checklist. (d) sizeRuns and the grown line height in em: a size span inside another, spans meeting at an edge, a span crossing a line break, the cursor typing at a span's end.` },
  { side: 'android', key: 'w2a8-roads', focus: `THE PHONE, ROADS NOT WALKED YET (${ANDROID}). Read the round lists named above for what was walked, then walk others an ordinary person takes in the first week: the list's sort options and grouping; a card's long-press menu actions one by one; the note details sheet (the i button); the duplicates clean-up; Statistics; the Settings page (theme, reminder time, categories) with a note open; the calendar's day list and a new note started from a day.` },
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

SCRATCH_DIR = ${W2}\\r8\\${area.key}
${SAFETY}
${WAVE}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(side, found) {
  return `You are the skeptic for the ${side} app's wave-2 round-8 findings in the final audit of Note Organizer (desktop ${DESKTOP}, phone ${ANDROID}). For EACH finding below, try to REFUTE it: re-trace the steps through the code yourself -- does the handler really do that, is there a guard the auditor missed, does the screen say something else, is it already known (grep the files named under ALREADY FOUND), is it one of the owner's choices, or are two findings one? Then answer ordinary_steps, and re-grade severity by the owner's rule. "confirmed" only when you traced it yourself; "plausible" when you cannot settle it.

SCRATCH_DIR = ${W2}\\r8\\skeptic-${side}
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
  log(`${side} wave 2 round 8: ${found.length} findings, ${weighty.length} of medium or above to the skeptic; lows kept as reported`)
  let verdicts = null
  if (weighty.length) {
    verdicts = await agent(verifierPrompt(side, weighty), { label: `refute:${side}`, phase: 'Refute', schema: VERDICT_SCHEMA })
  }
  results[side] = { reports, verdicts }
}))
return results
