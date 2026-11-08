// The final audit: run wf_77cc2cb4-b06, started 2026-11-06 11:57 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave2-lows-round3',
  description: 'Final audit, the lows wave of wave 2, verification round 3: the fixes of round 2 re-attacked, and the lows fixes on roads rounds 1 and 2 did not walk; one skeptic per app on findings of medium or above',
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
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 2: the app as an ORDINARY PERSON meets it, and as a CARELESS OR MISCHIEVOUS one uses it. Earlier waves attacked data safety, hostile files and huge inputs for twenty-five rounds; this wave is about a real person on an ordinary day: what they do, in what order, with what slips, and what the app then does to them. Rounds 1 to 25 found the roads listed in ${LISTS.join(', ')}; wave 2 closed after round 25. Its lows (${LOWS2}) were then fixed in a lows wave -- the commits named in your area -- and the rest written down as known. Its verification round 1 found three mediums, all in those fixes (${W2}\\rwl1_list.txt); round 2 found one more on the desktop, in a round-1 fix, and lows on both (${W2}\\rwl2_list.txt). All are fixed in the newest commit per app, or written down as known. This round re-attacks those fixes, and the lows fixes again.

SEVERITY -- THE OWNER'S RULE (1 Nov), it decides when the rounds stop:
- A finding keeps a round open (medium or above) only if it reproduces through ORDINARY STEPS a person takes. Rare roads -- a hand-edited file, many uncommon steps in a row, a clock set wrong on purpose -- are recorded as known (low), EXCEPT data loss.
- Data loss is always serious, however rare the road.
- high = notes, files or settings lost or corrupted; a crash or a freeze; the safe-looking answer of a question destroying something. medium = on an ordinary road, a person is misled or stuck: a button or key that does not do what it says, an action that silently does nothing or the wrong thing, a message that is false or leaves them with no way forward, a trap where the obvious choice is the bad one. low = everything else.
Rounds stop after two in a row with nothing of medium or above.

ALREADY FOUND -- do not report again: everything in ${AUDIT}, every '### <key>' heading in ${LOWS3}, every line of ${LOWS2} (its last two sections are the lows wave's rounds 1 and 2, with what was fixed and what left known) and of each of ${LISTS.join(', ')}, and ${W2}\\rwl1_list.txt and ${W2}\\rwl2_list.txt. ALSO DECIDED (the owner, round 3): the list's search does not read one day's own words of a repeating note; when it finds nothing and such a day holds the words, the empty list says so and links to the Calendar's History. DECIDED -- do not report: no Terms & Conditions screen; the phone has no "Follow the phone" theme; Store review is the feedback route; the app is offline on purpose; history in docs/ISSUES_LOG.md and CHANGELOG.md is the past. THE OWNER'S FOUR WAVE-2 CHOICES, which the fixes carry out -- do not argue them, attack how they were done: (1) a new note hidden by Show, a search or a folded group is said, with Show all, and an empty list names its filter and offers Show all; (2) every search on both apps (the list, Find in note, the History) ignores diacritics and case, and Title A-Z sorts a letter with a mark beside the letter; (3) text shared into the phone app that is not a code becomes a new note, a code with words around it is still a code; (4) the list's search looks in checklist rows, both apps.

HOW TO REPORT. Each finding: the steps a person takes (numbered), the exact code places (file:line), what the person sees, why it matters, the smallest fix. proved=true only when you traced it through the code yourself. Prefer 5 real findings over 25 guesses; the owner's usage is limited this week: read the functions you need, not whole files. A clean road is a real result: list what you walked in 'covered'. End with an honest coverage confession: what you did NOT walk.
`

const AREAS = [
  { side: 'desktop', key: 'wl3-d-round2', focus: `THE DESKTOP'S FIXES OF THE LOWS WAVE'S ROUND 2 (${DESKTOP}, commits ${DCOMMITS}: read the newest with git show; ${W2}\\rwl2_detail.txt says what round 2 found and walked). Ctrl+Z and the banner's Undo: Tk's own <<Undo>> now bound on the Text class (_text_class_undo) and read by _toast_undo_key -- walk it in every text box the app has (the note's text, the comments, a table cell, the find bar, the import box, a template's text, a checklist row being edited, Settings' boxes), with Caps Lock, with Ctrl+Shift+Z, from the Edit menu, twice in a row, and after a redo. The banners held back behind an Undo, now a list shown in turn (_banners_in_turn) behind any banner put up since; the '(earlier text)' banner asking again whether its note is there; the hidden new note's banner naming the note. A backup's Skip giving files only to the twins that gain one, leaving the open note out after Go back and fix it, and saying the files in Import complete. A one-note code added as a new note, its look-alike test leaving out only the note it was asked about. Walk each by name on a person's road, then the roads beside them. Look for an ordinary road on which a fix does not hold, or holds and harms something else.` },
  { side: 'desktop', key: 'wl3-d-lows', focus: `THE DESKTOP'S LOWS-WAVE FIXES ON ROADS ROUNDS 1 AND 2 DID NOT WALK (${DESKTOP}, commits a02ad0d, ff2b129, 67c9546 and ${DCOMMITS}; ${W2}\\rwl1_detail.txt and ${W2}\\rwl2_detail.txt name what was walked -- walk the others). Banners over time: an Undo left to expire while two banners wait, a banner held back while Settings opens or the window is closed, the theme switched or the list re-sorted with one waiting, an Undo by keyboard from the list. Imports beside the editor: a backup and a code in the same visit while a note is open and dirty, an import while the editor holds a table or a checklist row being typed, a Skip while the open note is on a day of a series. Look for an ordinary road on which a fix does not hold, or holds and harms something else -- and above all any road on which words or files are lost.` },
  { side: 'android', key: 'wl3-a-round2', focus: `THE PHONE'S FIXES OF THE LOWS WAVE'S ROUND 2 (${ANDROID}, commits ${ACOMMITS}: read the newest with git show; ${W2}\\rwl2_detail.txt). Bars about a note kept by its id (AppState.offerAbout, offer now returning its Job) and cancelled, on screen or still queued, when a save takes the note kept aside back (asidesSpent, SaveResult.spentAside); the list's 'Kept aside, hidden by' bar offered the same way; showAll refusing a note gone; the list's reveal letting go of an id no note has. Walk each by name, then every other bar beside them: offerUndo replacing the bar on screen, say queued, Leave anyway, the Trash's Undo, an import's arrivals, on one pane and on two, upright and on its side, with the app sent to the background or ended while a bar is queued. Look for an ordinary road on which a fix does not hold, or holds and harms something else.` },
  { side: 'android', key: 'wl3-a-data', focus: `THE PHONE'S UPDATE-COPY PORT AND THE LOWS FIXES, ON ROADS ROUNDS 1 AND 2 DID NOT WALK (${ANDROID}, commits 4a4e6f2, aa54e83, b495ab5, 8300d49 and ${ACOMMITS}; ${W2}\\rwl1_detail.txt and ${W2}\\rwl2_detail.txt name what was walked -- walk the others; the desktop's _keep_text_aside, _take_back_aside and _banners_in_turn in ${DESKTOP}\\note_organizer.py are what the phone must match). Data first: three big deletes in a row beside one Update's copy taken back in another order, an aside whose words come back by a paste rather than an Undo, an aside on a note that is then moved to another category or pinned from the list beside it, an aside and the Trash's Undo, a note kept aside opened from the list and edited. Then the list: arrivals after an import while an aside waits, Show all for several notes when one of them is gone, the id of a spent aside given to the next new note. Look for an ordinary road on which a fix does not hold, or holds and harms something else -- and above all any road on which words are lost.` },
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

SCRATCH_DIR = ${W2}\\wl3\\${area.key}
${SAFETY}
${WAVE}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(side, found) {
  return `You are the skeptic for the ${side} app's lows-wave round-3 findings in the final audit of Note Organizer (desktop ${DESKTOP}, phone ${ANDROID}). For EACH finding below, try to REFUTE it: re-trace the steps through the code yourself -- does the handler really do that, is there a guard the auditor missed, does the screen say something else, is it already known (grep the files named under ALREADY FOUND), is it one of the owner's choices, or are two findings one? Then answer ordinary_steps, and re-grade severity by the owner's rule. "confirmed" only when you traced it yourself; "plausible" when you cannot settle it.

SCRATCH_DIR = ${W2}\\wl3\\skeptic-${side}
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
  log(`${side} lows wave round 3: ${found.length} findings, ${weighty.length} of medium or above to the skeptic; lows kept as reported`)
  let verdicts = null
  if (weighty.length) {
    verdicts = await agent(verifierPrompt(side, weighty), { label: `refute:${side}`, phase: 'Refute', schema: VERDICT_SCHEMA })
  }
  results[side] = { reports, verdicts }
}))
return results
