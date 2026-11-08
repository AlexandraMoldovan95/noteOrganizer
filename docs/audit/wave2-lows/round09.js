// The final audit: run wf_6e8cfb6f-368, started 2026-11-06 21:13 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave2-lows-round9',
  description: 'Final audit, the lows wave of wave 2, verification round 9: the fixes of round 8 re-attacked, and the lows fixes of the phone as a whole; one skeptic per app on findings of medium or above',
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
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 2: the app as an ORDINARY PERSON meets it, and as a CARELESS OR MISCHIEVOUS one uses it. Earlier waves attacked data safety, hostile files and huge inputs for twenty-five rounds; this wave is about a real person on an ordinary day: what they do, in what order, with what slips, and what the app then does to them. Rounds 1 to 25 found the roads listed in ${LISTS.join(', ')}; wave 2 closed after round 25. Its lows (${LOWS2}) were then fixed in a lows wave -- the commits named in your area -- and the rest written down as known. Its verification round 1 found three mediums, all in those fixes (${W2}\\rwl1_list.txt); round 2 found one more on the desktop, in a round-1 fix, and lows on both (${W2}\\rwl2_list.txt); round 3 one more on the desktop, in a round-2 fix, and lows on both (${W2}\\rwl3_list.txt); round 4 was clean on both, with lows (${W2}\\rwl4_list.txt); round 5 found a high and a medium on the desktop, the high in a round-4 fix, and was clean on the phone (${W2}\\rwl5_list.txt); round 6 found a high and a medium on the desktop, the high a road beside a round-5 fix, and was clean on the phone (${W2}\\rwl6_list.txt); round 7 was clean on the desktop and found a medium on the phone, in a round-6 fix (${W2}\\rwl7_list.txt); round 8 was clean on the desktop, its second clean round, which closed it, and found a medium on the phone, in a round-7 fix (${W2}\\rwl8_list.txt). All are fixed in the newest commit per app, or written down as known. This round re-attacks those fixes, and the lows fixes as a whole.

SEVERITY -- THE OWNER'S RULE (1 Nov), it decides when the rounds stop:
- A finding keeps a round open (medium or above) only if it reproduces through ORDINARY STEPS a person takes. Rare roads -- a hand-edited file, many uncommon steps in a row, a clock set wrong on purpose -- are recorded as known (low), EXCEPT data loss.
- Data loss is always serious, however rare the road.
- high = notes, files or settings lost or corrupted; a crash or a freeze; the safe-looking answer of a question destroying something. medium = on an ordinary road, a person is misled or stuck: a button or key that does not do what it says, an action that silently does nothing or the wrong thing, a message that is false or leaves them with no way forward, a trap where the obvious choice is the bad one. low = everything else.
Rounds stop after two in a row with nothing of medium or above.

ALREADY FOUND -- do not report again: everything in ${AUDIT}, every '### <key>' heading in ${LOWS3}, every line of ${LOWS2} (its last eight sections are the lows wave's rounds 1 to 8, with what was fixed and what left known) and of each of ${LISTS.join(', ')}, and ${W2}\\rwl1_list.txt to ${W2}\\rwl8_list.txt. ALSO DECIDED (the owner, round 3): the list's search does not read one day's own words of a repeating note; when it finds nothing and such a day holds the words, the empty list says so and links to the Calendar's History. DECIDED -- do not report: no Terms & Conditions screen; the phone has no "Follow the phone" theme; Store review is the feedback route; the app is offline on purpose; history in docs/ISSUES_LOG.md and CHANGELOG.md is the past. THE OWNER'S FOUR WAVE-2 CHOICES, which the fixes carry out -- do not argue them, attack how they were done: (1) a new note hidden by Show, a search or a folded group is said, with Show all, and an empty list names its filter and offers Show all; (2) every search on both apps (the list, Find in note, the History) ignores diacritics and case, and Title A-Z sorts a letter with a mark beside the letter; (3) text shared into the phone app that is not a code becomes a new note, a code with words around it is still a code; (4) the list's search looks in checklist rows, both apps.

HOW TO REPORT. Each finding: the steps a person takes (numbered), the exact code places (file:line), what the person sees, why it matters, the smallest fix. proved=true only when you traced it through the code yourself. Prefer 5 real findings over 25 guesses; the owner's usage is limited this week: read the functions you need, not whole files. A clean road is a real result: list what you walked in 'covered'. End with an honest coverage confession: what you did NOT walk.
`

const AREAS = [
  { side: 'desktop', key: 'wl9-d-round8', focus: `THE DESKTOP'S FIXES MADE AFTER ITS VERIFICATION CLOSED (round 8 was its second clean round; ${DESKTOP}, commits ${DCOMMITS}: read the newest with git show; ${W2}\\rwl8_detail.txt). The held arrivals banner reading the list once (a set of the notes by identity, the visible ids read once); 'Import cancelled' and the comments' table notice going through _banner_after_undo; save_current_note(stay=True) for Duplicate's "save first", through the _save_stays flag read in _after_note_saved. Walk each by name and the roads beside them: every caller of save_current_note and of _write_fields_to_note, a duplicate from the menu and from the editor with a note added for a calendar day, an exception inside the save while _save_stays is set, a big import and restore with Show set, every banner still shown with _show_toast directly while an Undo may be up. Look for an ordinary road on which a fix does not hold, or holds and harms something else.` },
  { side: 'android', key: 'wl9-a-round8', focus: `THE PHONE'S FIXES OF THE LOWS WAVE'S ROUND 8 (${ANDROID}, commits ${ACOMMITS}: read the newest with git show; ${W2}\\rwl8_detail.txt). The list's waiting words are no longer merged by their text, each is counted by its own notes, and the loop takes the next word only when the bar at the foot is free (state.snackbar.currentSnackbarData == null). Walk the loop with every other bar in the app (say, offer, offerUndo, Leave anyway, the import's Open, the editor's Show), with several words waiting, with words about the same notes twice, with the list left and come back to while the bar is busy, and on two panes where the editor's bars come and go beside the list. Is a word ever stuck waiting forever, said twice, or worded before its turn? Look for an ordinary road on which a fix does not hold, or holds and harms something else.` },
  { side: 'android', key: 'wl9-a-data', focus: `THE PHONE'S LOWS-WAVE FIXES AS A WHOLE, ON ROADS ROUNDS 1 TO 8 DID NOT WALK (${ANDROID}, commits 4a4e6f2, aa54e83, b495ab5, 8300d49, 5ec49e6, fcc0ffc, 8d38ce3, 6b10f34, 5697190, c01eeb4 and ${ACOMMITS}; ${W2}\\rwl1_detail.txt to rwl8_detail.txt name what was walked -- walk the others; the desktop in ${DESKTOP}\\note_organizer.py is what the phone must match). A person's whole day with the app, in an order no round has tried. Look for an ordinary road on which a fix does not hold, or holds and harms something else -- and above all any road on which words are lost.` },
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

SCRATCH_DIR = ${W2}\\wl9\\${area.key}
${SAFETY}
${WAVE}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(side, found) {
  return `You are the skeptic for the ${side} app's lows-wave round-9 findings in the final audit of Note Organizer (desktop ${DESKTOP}, phone ${ANDROID}). For EACH finding below, try to REFUTE it: re-trace the steps through the code yourself -- does the handler really do that, is there a guard the auditor missed, does the screen say something else, is it already known (grep the files named under ALREADY FOUND), is it one of the owner's choices, or are two findings one? Then answer ordinary_steps, and re-grade severity by the owner's rule. "confirmed" only when you traced it yourself; "plausible" when you cannot settle it.

SCRATCH_DIR = ${W2}\\wl9\\skeptic-${side}
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
  log(`${side} lows wave round 9: ${found.length} findings, ${weighty.length} of medium or above to the skeptic; lows kept as reported`)
  let verdicts = null
  if (weighty.length) {
    verdicts = await agent(verifierPrompt(side, weighty), { label: `refute:${side}`, phase: 'Refute', schema: VERDICT_SCHEMA })
  }
  results[side] = { reports, verdicts }
}))
return results
