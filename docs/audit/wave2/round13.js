// The final audit: run wf_279502b1-caf, started 2026-11-04 01:39 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave2-round13',
  description: 'Final audit, wave 2, round 13, both apps: the round-12 fixes re-attacked, and a second sweep of the desktop class, no new roads; one skeptic per app on findings of medium or above',
  phases: [
    { title: 'Find', detail: 'per app: the fixes re-attacked, and untouched roads; read-only' },
    { title: 'Refute', detail: 'per app, one skeptic re-checks the findings of medium or above' },
  ],
}

const W2 = '<scratchpad>\\wave2'
const AUDIT = '<scratchpad>\\audit\\register.md'
const LOWS3 = '<scratchpad>\\wave3\\lows.md'
const LOWS2 = W2 + '\\lows_w2.md'
const LISTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(n => `${W2}\\r${n}_list.txt`)
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
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 2: the app as an ORDINARY PERSON meets it, and as a CARELESS OR MISCHIEVOUS one uses it. Earlier waves attacked data safety, hostile files and huge inputs for twenty-five rounds; this wave is about a real person on an ordinary day: what they do, in what order, with what slips, and what the app then does to them. Rounds 1 to 12 found the roads listed in ${LISTS.join(', ')}; the latest fixes are in the newest commit per app (below), the earlier rounds' in the commits before them.

SEVERITY -- THE OWNER'S RULE (1 Nov), it decides when the rounds stop:
- A finding keeps a round open (medium or above) only if it reproduces through ORDINARY STEPS a person takes. Rare roads -- a hand-edited file, many uncommon steps in a row, a clock set wrong on purpose -- are recorded as known (low), EXCEPT data loss.
- Data loss is always serious, however rare the road.
- high = notes, files or settings lost or corrupted; a crash or a freeze; the safe-looking answer of a question destroying something. medium = on an ordinary road, a person is misled or stuck: a button or key that does not do what it says, an action that silently does nothing or the wrong thing, a message that is false or leaves them with no way forward, a trap where the obvious choice is the bad one. low = everything else.
Rounds stop after two in a row with nothing of medium or above.

ALREADY FOUND -- do not report again: everything in ${AUDIT}, every '### <key>' heading in ${LOWS3}, every line of ${LOWS2} and of each of ${LISTS.join(', ')}. ALSO DECIDED (the owner, round 3): the list's search does not read one day's own words of a repeating note; when it finds nothing and such a day holds the words, the empty list says so and links to the Calendar's History. DECIDED -- do not report: no Terms & Conditions screen; the phone has no "Follow the phone" theme; Store review is the feedback route; the app is offline on purpose; history in docs/ISSUES_LOG.md and CHANGELOG.md is the past. THE OWNER'S FOUR WAVE-2 CHOICES, which the fixes carry out -- do not argue them, attack how they were done: (1) a new note hidden by Show, a search or a folded group is said, with Show all, and an empty list names its filter and offers Show all; (2) every search on both apps (the list, Find in note, the History) ignores diacritics and case, and Title A-Z sorts a letter with a mark beside the letter; (3) text shared into the phone app that is not a code becomes a new note, a code with words around it is still a code; (4) the list's search looks in checklist rows, both apps.

HOW TO REPORT. Each finding: the steps a person takes (numbered), the exact code places (file:line), what the person sees, why it matters, the smallest fix. proved=true only when you traced it through the code yourself. Prefer 5 real findings over 25 guesses; the owner's usage is limited this week: read the functions you need, not whole files. A clean road is a real result: list what you walked in 'covered'. End with an honest coverage confession: what you did NOT walk.
`

const AREAS = [
  { side: 'desktop', key: 'w2d13-fixes', focus: `THE DESKTOP'S ROUND-12 FIXES, RE-ATTACKED BY NAME (${DESKTOP}, commit ${DCOMMITS}: read it with git show; rounds 7-11's open_note_in_tab and the import merge's wait are in the commits before it). (a) open_note_in_tab with flush=False no longer asks _dismiss_mini_popup_asking, and leaves any popup open: walk every flush=False caller (an import's Update, _editor_follows_external_change, _relocate_day) with each popup open over the editor -- the template editor, the emoji picker, a colour palette, a context menu, the spelling menu, a cell editor, the find bar -- does a popup act on the reloaded note as if it were the old one, or does its Save write something stale? (b) _restore_trash_entries rolls back by identity: walk a bulk Undo, a restore from Settings' Recently deleted, a restore of a note whose category was deleted, and the trash list after the rollback.` },
  { side: 'desktop', key: 'w2d13-waits', focus: `THE CLASS BEHIND ROUNDS 11-12, A SECOND SWEEP (${DESKTOP}, commit ${DCOMMITS}; round 12's sweep is in ${W2}\\r12_detail.txt -- read its covered and not_covered, walk what it did NOT, and do not repeat its findings). While a themed dialog waits (wait_variable), Tk's timers and bindings keep running: a value read before a question (an id, an index, a count, a note object, a copy of a list, the editor's text) and used after it can be stale. Look at the callers round 12 did not reach, and at the timers that fire inside a wait. Report a road only when an ordinary person can reach it; data loss is always serious.` },
  { side: 'android', key: 'w2a13-days', focus: `THE PHONE'S ROUND-12 FIX (a), RE-ATTACKED BY NAME (${ANDROID}, commit ${ACOMMITS}: read it with git show; rounds 7-11's saveStaying, closes and the editor built anew carrying 'A new item...' are in the commits before it). openNote for the note already open, on another of its days or as the whole series, now saves with saveStaying and only changes openDay (no opening += 1, no leaving()). Walk: a day the series no longer draws; a new note (id 0); a save that fails ('Leave anyway' and its answer); the calendar's way back; the find bar and other editor state remembered without the model as a key; the Calendar beside the editor and the History; one pane after the calendar's tap; the same note opened from the list while on a day.` },
  { side: 'android', key: 'w2a13-list', focus: `THE PHONE'S ROUND-12 FIX (b), RE-ATTACKED BY NAME (${ANDROID}, commit ${ACOMMITS}: read it with git show). Showing.revealAt (pure) and its callers in NotesScreen (revealLater, the effect, the Trash's Undo, pin, duplicate, move to category): several notes pinned at once and the first chosen by the flat order under grouping; a folded group; a search; Show; the window seen empty (the list not laid out yet); a card under a header at the very top; the list scrolled to its end; the unit tests in ListingTest -- do they hold the cases the person meets?` },
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

SCRATCH_DIR = ${W2}\\r13\\${area.key}
${SAFETY}
${WAVE}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(side, found) {
  return `You are the skeptic for the ${side} app's wave-2 round-13 findings in the final audit of Note Organizer (desktop ${DESKTOP}, phone ${ANDROID}). For EACH finding below, try to REFUTE it: re-trace the steps through the code yourself -- does the handler really do that, is there a guard the auditor missed, does the screen say something else, is it already known (grep the files named under ALREADY FOUND), is it one of the owner's choices, or are two findings one? Then answer ordinary_steps, and re-grade severity by the owner's rule. "confirmed" only when you traced it yourself; "plausible" when you cannot settle it.

SCRATCH_DIR = ${W2}\\r13\\skeptic-${side}
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
  log(`${side} wave 2 round 13: ${found.length} findings, ${weighty.length} of medium or above to the skeptic; lows kept as reported`)
  let verdicts = null
  if (weighty.length) {
    verdicts = await agent(verifierPrompt(side, weighty), { label: `refute:${side}`, phase: 'Refute', schema: VERDICT_SCHEMA })
  }
  results[side] = { reports, verdicts }
}))
return results
