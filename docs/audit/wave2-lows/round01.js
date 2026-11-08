// The final audit: run wf_733ef097-671, started 2026-11-06 08:51 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave2-lows-round1',
  description: 'Final audit, the lows wave of wave 2, verification round 1: the lows fixes of both apps re-attacked by name, with their neighbourhood; one skeptic per app on findings of medium or above',
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
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 2: the app as an ORDINARY PERSON meets it, and as a CARELESS OR MISCHIEVOUS one uses it. Earlier waves attacked data safety, hostile files and huge inputs for twenty-five rounds; this wave is about a real person on an ordinary day: what they do, in what order, with what slips, and what the app then does to them. Rounds 1 to 25 found the roads listed in ${LISTS.join(', ')}; wave 2 closed after round 25. Its lows (${LOWS2}) were then fixed in a lows wave -- the commits named in your area -- and the rest written down as known. This round re-attacks those fixes.

SEVERITY -- THE OWNER'S RULE (1 Nov), it decides when the rounds stop:
- A finding keeps a round open (medium or above) only if it reproduces through ORDINARY STEPS a person takes. Rare roads -- a hand-edited file, many uncommon steps in a row, a clock set wrong on purpose -- are recorded as known (low), EXCEPT data loss.
- Data loss is always serious, however rare the road.
- high = notes, files or settings lost or corrupted; a crash or a freeze; the safe-looking answer of a question destroying something. medium = on an ordinary road, a person is misled or stuck: a button or key that does not do what it says, an action that silently does nothing or the wrong thing, a message that is false or leaves them with no way forward, a trap where the obvious choice is the bad one. low = everything else.
Rounds stop after two in a row with nothing of medium or above.

ALREADY FOUND -- do not report again: everything in ${AUDIT}, every '### <key>' heading in ${LOWS3}, every line of ${LOWS2} and of each of ${LISTS.join(', ')}. ALSO DECIDED (the owner, round 3): the list's search does not read one day's own words of a repeating note; when it finds nothing and such a day holds the words, the empty list says so and links to the Calendar's History. DECIDED -- do not report: no Terms & Conditions screen; the phone has no "Follow the phone" theme; Store review is the feedback route; the app is offline on purpose; history in docs/ISSUES_LOG.md and CHANGELOG.md is the past. THE OWNER'S FOUR WAVE-2 CHOICES, which the fixes carry out -- do not argue them, attack how they were done: (1) a new note hidden by Show, a search or a folded group is said, with Show all, and an empty list names its filter and offers Show all; (2) every search on both apps (the list, Find in note, the History) ignores diacritics and case, and Title A-Z sorts a letter with a mark beside the letter; (3) text shared into the phone app that is not a code becomes a new note, a code with words around it is still a code; (4) the list's search looks in checklist rows, both apps.

HOW TO REPORT. Each finding: the steps a person takes (numbered), the exact code places (file:line), what the person sees, why it matters, the smallest fix. proved=true only when you traced it through the code yourself. Prefer 5 real findings over 25 guesses; the owner's usage is limited this week: read the functions you need, not whole files. A clean road is a real result: list what you walked in 'covered'. End with an honest coverage confession: what you did NOT walk.
`

const AREAS = [
  { side: 'desktop', key: 'wl1-d-waits', focus: `THE DESKTOP'S LOWS-WAVE FIXES, BATCH 1 (${DESKTOP}, commits ${DCOMMITS}: read a02ad0d with git show; ${W2}\\lows_w2.md lists the lows they answer, rounds 1 to 14; ${W2}\\lows_wave_plan.md says which were fixed and which left known -- do not report the known ones again). What ran inside a wait: a popup with nothing to lose closed on a reload from outside; a Trash restore whose save fails putting the file back; Remove on a new note's file under its first save; History's off-schedule row of another note; a backup's Skip giving a look-alike's files to its twin; the merge waiting under a file chooser or a posted menu (_while_native, _natives_open) and saying it waits; Show all from a banner over Settings. And the imports: Add as a new note not asked again (both the one-note code and the batch), a backup bringing templates, Trash entries or day colours offered Skip them (_backup_brings_more), a one-note code's Update keeping the day, the double-click guards on Import and Restore selected. Walk each fix by name on the roads a person takes, then its neighbours: the same question asked elsewhere, a sibling route the fix did not reach, a fix that broke what stood beside it. Look for an ordinary road on which the fix does not hold, or holds and harms something else.` },
  { side: 'desktop', key: 'wl1-d-small', focus: `THE DESKTOP'S LOWS-WAVE FIXES, THE SMALL ONES (${DESKTOP}, commits ${DCOMMITS}: read ff2b129 and the aside parts of a02ad0d with git show; ${W2}\\lows_w2.md and ${W2}\\lows_wave_plan.md as above). The '(earlier text)' notes kept aside beside an Update's copy: a one-off's date kept, the note said hidden with Show all, said again when spent, told untouched by content_signature and its stamp (_aside_look), forgotten when put back from the Trash. Ctrl+Z routed to the banner's Undo (_toast_undo_key, the redo test for a Text), a new hidden note yielding to an Undo (undo_shown), 'Nothing was imported.', the category dot after a recolour, 'Move the series to category', a duplicate created now, a category added brought into sight, the welcome note's Show all, long category names cut with '…', 'Added 1 note', Statistics' In trash, the template box's Ctrl+K/O/T, the calculator's second Enter and minus after Error. Walk each by name, then its neighbours. Look for an ordinary road on which the fix does not hold, or holds and harms something else.` },
  { side: 'android', key: 'wl1-a-update-copy', focus: `THE PHONE'S PORT OF THE DESKTOP'S UPDATE-COPY RULE (${ANDROID}, commits ${ACOMMITS}: read 4a4e6f2 with git show, and the desktop's _keep_text_aside, _take_back_aside, _turn_off_rescue_copy and save_current_note's series branch in ${DESKTOP}\\note_organizer.py for what the phone must match). After an Update from a backup or a share code, a big delete keeps the Update's copy, the words it takes become '<title> (earlier text)' in the same write (Notebook.updateNote, keepTextAside), spent when typed back and untouched (takeBackAside, asideLook, Load.keptAside), forgotten when put back from the Trash (Organizing.restore, forgetAsides), carried over an import's reload (AppState.reload), said with Show by the editor (NoteEditor.writeNote) and by the list where it hides it. This is about data: walk every road on which the phone writes a note's words over an Update's copy -- the editor's save on the whole note and on a day (Days.saveDay), the Repeat sheet, Restore previous, a second import, a checklist or comments save, the app going to the background mid-edit (writeAway) -- and whether any still replaces the copy, loses the words taken, makes the aside twice, spends one that was touched, or differs from what the desktop does on the same steps. Then the neighbours: the days fixture (tools/make_days_fixture.py) and DaysTest, which hold the parity.` },
  { side: 'android', key: 'wl1-a-lows', focus: `THE PHONE'S OTHER LOWS-WAVE FIXES (${ANDROID}, commits ${ACOMMITS}: read f534a4c, aa54e83 and the newest with git show; ${W2}\\lows_w2.md and ${W2}\\lows_wave_plan.md as above -- the plan names the lows left known; do not report those). Custom order's handle and edge (a cancelled press, a second handle, a fling-stopping tap, the step menu disposed with its card, TalkBack's 'Moved above/below', the hold asked once composed, the edge's latch, clock and block, the pair's gap); the list bringing only cards that moved or arrived (Showing.movedIds, Reveal.arrived), the Trash's Undo said where hidden; the editor read back only when written (AppState.outside's day and refused, beforeImport/afterImport), Leave anyway's guard, the calendar following a moved day, the calculator and find bar kept for the visit, messages above the add box on a rebuilt model, folds dropped with their note and moved from '0:'; and the small ones: a duplicate created now, the app off its own share sheet, a new note's first attach, a calendar note said hidden, the older backup's question, the BOM, a missing file said, the reminder's timeout. Walk each by name on a person's road, then its neighbours. Look for an ordinary road on which the fix does not hold, or holds and harms something else.` },
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

SCRATCH_DIR = ${W2}\\wl1\\${area.key}
${SAFETY}
${WAVE}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(side, found) {
  return `You are the skeptic for the ${side} app's lows-wave round-1 findings in the final audit of Note Organizer (desktop ${DESKTOP}, phone ${ANDROID}). For EACH finding below, try to REFUTE it: re-trace the steps through the code yourself -- does the handler really do that, is there a guard the auditor missed, does the screen say something else, is it already known (grep the files named under ALREADY FOUND), is it one of the owner's choices, or are two findings one? Then answer ordinary_steps, and re-grade severity by the owner's rule. "confirmed" only when you traced it yourself; "plausible" when you cannot settle it.

SCRATCH_DIR = ${W2}\\wl1\\skeptic-${side}
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
  log(`${side} lows wave round 1: ${found.length} findings, ${weighty.length} of medium or above to the skeptic; lows kept as reported`)
  let verdicts = null
  if (weighty.length) {
    verdicts = await agent(verifierPrompt(side, weighty), { label: `refute:${side}`, phase: 'Refute', schema: VERDICT_SCHEMA })
  }
  results[side] = { reports, verdicts }
}))
return results
