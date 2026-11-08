// The final audit: run wf_11dad950-e49, started 2026-11-06 16:19 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave2-lows-round6',
  description: 'Final audit, the lows wave of wave 2, verification round 6: the fixes of round 5 re-attacked, and the lows fixes as a whole; one skeptic per app on findings of medium or above',
  phases: [
    { title: 'Find', detail: 'per app: the fixes re-attacked, and untouched roads; read-only' },
    { title: 'Refute', detail: 'per app, one skeptic re-checks the findings of medium or above' },
  ],
}

const W2 = '<scratchpad>\\wave2'
const AUDIT = '<scratchpad>\\audit\\register.md'
const LOWS3 = '<scratchpad>\\wave3\\lows.md'
const LOWS2 = W2 + '\\lows_w2.md'
const LISTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25].map(n => `${W2}\\r${n}_list.txt`)
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
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 2: the app as an ORDINARY PERSON meets it, and as a CARELESS OR MISCHIEVOUS one uses it. Earlier waves attacked data safety, hostile files and huge inputs for twenty-five rounds; this wave is about a real person on an ordinary day: what they do, in what order, with what slips, and what the app then does to them. Rounds 1 to 25 found the roads listed in ${LISTS.join(', ')}; wave 2 closed after round 25. Its lows (${LOWS2}) were then fixed in a lows wave -- the commits named in your area -- and the rest written down as known. Its verification round 1 found three mediums, all in those fixes (${W2}\\rwl1_list.txt); round 2 found one more on the desktop, in a round-1 fix, and lows on both (${W2}\\rwl2_list.txt); round 3 one more on the desktop, in a round-2 fix, and lows on both (${W2}\\rwl3_list.txt); round 4 was clean on both, with lows (${W2}\\rwl4_list.txt); round 5 found a high and a medium on the desktop, the high in a round-4 fix, and was clean on the phone (${W2}\\rwl5_list.txt). All are fixed in the newest commit per app, or written down as known. This round re-attacks those fixes, and the lows fixes as a whole.

SEVERITY -- THE OWNER'S RULE (1 Nov), it decides when the rounds stop:
- A finding keeps a round open (medium or above) only if it reproduces through ORDINARY STEPS a person takes. Rare roads -- a hand-edited file, many uncommon steps in a row, a clock set wrong on purpose -- are recorded as known (low), EXCEPT data loss.
- Data loss is always serious, however rare the road.
- high = notes, files or settings lost or corrupted; a crash or a freeze; the safe-looking answer of a question destroying something. medium = on an ordinary road, a person is misled or stuck: a button or key that does not do what it says, an action that silently does nothing or the wrong thing, a message that is false or leaves them with no way forward, a trap where the obvious choice is the bad one. low = everything else.
Rounds stop after two in a row with nothing of medium or above.

ALREADY FOUND -- do not report again: everything in ${AUDIT}, every '### <key>' heading in ${LOWS3}, every line of ${LOWS2} (its last five sections are the lows wave's rounds 1 to 5, with what was fixed and what left known) and of each of ${LISTS.join(', ')}, and ${W2}\\rwl1_list.txt to ${W2}\\rwl5_list.txt. ALSO DECIDED (the owner, round 3): the list's search does not read one day's own words of a repeating note; when it finds nothing and such a day holds the words, the empty list says so and links to the Calendar's History. DECIDED -- do not report: no Terms & Conditions screen; the phone has no "Follow the phone" theme; Store review is the feedback route; the app is offline on purpose; history in docs/ISSUES_LOG.md and CHANGELOG.md is the past. THE OWNER'S FOUR WAVE-2 CHOICES, which the fixes carry out -- do not argue them, attack how they were done: (1) a new note hidden by Show, a search or a folded group is said, with Show all, and an empty list names its filter and offers Show all; (2) every search on both apps (the list, Find in note, the History) ignores diacritics and case, and Title A-Z sorts a letter with a mark beside the letter; (3) text shared into the phone app that is not a code becomes a new note, a code with words around it is still a code; (4) the list's search looks in checklist rows, both apps.

HOW TO REPORT. Each finding: the steps a person takes (numbered), the exact code places (file:line), what the person sees, why it matters, the smallest fix. proved=true only when you traced it through the code yourself. Prefer 5 real findings over 25 guesses; the owner's usage is limited this week: read the functions you need, not whole files. A clean road is a real result: list what you walked in 'covered'. End with an honest coverage confession: what you did NOT walk.
`

const AREAS = [
  { side: 'desktop', key: 'wl6-d-round5', focus: `THE DESKTOP'S FIXES OF THE LOWS WAVE'S ROUND 5 (${DESKTOP}, commits ${DCOMMITS}: read the newest with git show; ${W2}\\rwl5_detail.txt says what round 5 found and walked). Show all (_show_all_notes) now leaves Settings through _leave_settings_for_the_editor and stops when a popup holding typed work is kept: walk every banner with Show all or Show over Settings, over a template editor, over another mini popup (a category picker, a colour, a calculator, find), with Yes, No and Cancel. A banner's Undo now keeps the count of the note's journal steps when offered (_toast_units_at, counted in _push_atom_step), and the open table cell leaves the banner alone after a step since: walk Ctrl+Z in a cell after Enter, Tab, a pasted block, a row or column command, a style, a cell just clicked, a cell clicked after typing elsewhere in the note, a second banner offered after the edit, and the same in the note's text and comments. The reworded Import complete sentence and keyboard reference. Look for an ordinary road on which a fix does not hold, or holds and harms something else.` },
  { side: 'desktop', key: 'wl6-d-lows', focus: `THE DESKTOP'S LOWS-WAVE FIXES AS A WHOLE, ON ROADS ROUNDS 1 TO 5 DID NOT WALK (${DESKTOP}, commits a02ad0d, ff2b129, 67c9546, 0ade940, 43b49d7, bf5b109 and ${DCOMMITS}; ${W2}\\rwl1_detail.txt to rwl5_detail.txt name what was walked -- walk the others). The banner and its Undo across the whole app: every action that offers Undo, every key and click that can take it or stand between, every message held back behind it, in an order no round has tried. Look for an ordinary road on which a fix does not hold, or holds and harms something else -- and above all any road on which words or files are lost.` },
  { side: 'android', key: 'wl6-a-round5', focus: `THE PHONE'S FIXES OF THE LOWS WAVE'S ROUND 5 (${ANDROID}, commits ${ACOMMITS}: read the newest with git show; ${W2}\\rwl5_detail.txt). offerUndo now replaces the bar on screen and holds back the offers still waiting (heldBack), asking them again once the Undo is done, after its own words (askHeldBackAgain), each by its maker (Offered.again: the list's bars become its waiting words again); the list's own bars live while the list does (NotesScreen listBars, cancelled and asked again on dispose); refresh drops newNoteMade and arrivals for notes gone; the import's Open is about its note. Walk every offer against every Undo, two Undos in a row, an Undo left to run out, a list left and come back to while a bar shows and while one is held back, on one pane and two, with a rotation. Look for an ordinary road on which a fix does not hold, or holds and harms something else.` },
  { side: 'android', key: 'wl6-a-data', focus: `THE PHONE'S LOWS-WAVE FIXES AS A WHOLE, ON ROADS ROUNDS 1 TO 5 DID NOT WALK (${ANDROID}, commits 4a4e6f2, aa54e83, b495ab5, 8300d49, 5ec49e6, fcc0ffc, 8d38ce3 and ${ACOMMITS}; ${W2}\\rwl1_detail.txt to rwl5_detail.txt name what was walked -- walk the others; the desktop in ${DESKTOP}\\note_organizer.py is what the phone must match). A person's day with the bars at the foot and the list's words, in an order no round has tried. Look for an ordinary road on which a fix does not hold, or holds and harms something else -- and above all any road on which words are lost.` },
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

SCRATCH_DIR = ${W2}\\wl6\\${area.key}
${SAFETY}
${WAVE}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(side, found) {
  return `You are the skeptic for the ${side} app's lows-wave round-6 findings in the final audit of Note Organizer (desktop ${DESKTOP}, phone ${ANDROID}). For EACH finding below, try to REFUTE it: re-trace the steps through the code yourself -- does the handler really do that, is there a guard the auditor missed, does the screen say something else, is it already known (grep the files named under ALREADY FOUND), is it one of the owner's choices, or are two findings one? Then answer ordinary_steps, and re-grade severity by the owner's rule. "confirmed" only when you traced it yourself; "plausible" when you cannot settle it.

SCRATCH_DIR = ${W2}\\wl6\\skeptic-${side}
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
  log(`${side} lows wave round 6: ${found.length} findings, ${weighty.length} of medium or above to the skeptic; lows kept as reported`)
  let verdicts = null
  if (weighty.length) {
    verdicts = await agent(verifierPrompt(side, weighty), { label: `refute:${side}`, phase: 'Refute', schema: VERDICT_SCHEMA })
  }
  results[side] = { reports, verdicts }
}))
return results
