// The final audit: run wf_a063f175-24a, started 2026-11-03 01:38 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave2-round1',
  description: 'Final audit, wave 2 (an ordinary person, and a careless or mischievous one), round 1, both apps: two read-only finders per app, one skeptic per app on findings of medium or above',
  phases: [
    { title: 'Find', detail: 'per app: an ordinary first week, and the careless or mischievous person; read-only' },
    { title: 'Refute', detail: 'per app, one skeptic re-checks the findings of medium or above' },
  ],
}

const W2 = '<scratchpad>\\wave2'
const AUDIT = '<scratchpad>\\audit\\register.md'
const LOWS3 = '<scratchpad>\\wave3\\lows.md'
const DESKTOP = 'D:\\Projects\\NoteOrganizer'
const ANDROID = 'D:\\Projects\\androidVersion'

const SAFETY = `
HARD SAFETY RULES (real user data has been lost four times in this project; on 2026-10-29 a test run took the owner's whole computer down -- not negotiable):
- You are READ-ONLY on both repositories (${DESKTOP} and ${ANDROID}). Do not edit, create or delete any file inside them. Git: only log, show, diff, grep, ls-files, blame.
- Write ONLY inside your own folder, SCRATCH_DIR (given below). Create it if needed.
- NEVER read, list or write: C:\\Users\\<name>\\Note Organizer, anything under %APPDATA%\\NoteOrganizer*, C:\\Users\\<name>\\Desktop\\<the owner's notebook>, any notebook_location.txt, or any notes_data.json / trash.json / templates.json / settings.json / attachments folder at a repository root. Never run a search (find, grep -r, dir /s) from / or C:\\ or the user folder -- use the Grep tool or git grep inside a repository.
- You READ the code and walk a person's road through it in your head. Never run the app, a test (qa*.py, test_*.py, story_*.py, gradle), tools/run_tests.py, tools/mutate.py, tools/linux_ci.py, docker, gradle, adb or the emulator -- an emulator walk is running on this machine right now, and one heavy job at a time is the rule. No network, no installing. You MAY run your own Python scripts in SCRATCH_DIR with 'py -I' that read source files as text (never import the app's code). If a command is refused, do not try another spelling -- note it under not_covered.
- Do not fix anything. Find, prove (from the code), report.
`

const WAVE = `
THE WAVE. This is the FINAL audit before Note Organizer is published (Microsoft Store, Google Play), wave 2: the app as an ORDINARY PERSON meets it, and as a CARELESS OR MISCHIEVOUS one uses it. Earlier waves already attacked data safety, hostile files and huge inputs for twenty-five rounds, and an AI-slop wave read the code and the documents -- so this wave is not about crafted backups, decompression bombs or 60-million-letter notes. It is about a real person on an ordinary day: what they do, in what order, with what slips, and what the app then does to them.

HOW TO WORK. Pick concrete journeys and walk each through the code, step by step, the way a person's fingers would: which handler a click or key reaches, what it changes, what it saves, what the screen then says. Think of: doing it slowly; leaving it half done (a date half typed, a dialog left open, a name with a trailing space); clicking away or switching notes mid-action; doing it twice, fast; the window small or the phone turned; the keyboard only; a screen reader's names; dark and light themes; a different language on the computer or phone (dates written day-first, comma decimals, 12-hour clock, Romanian letters ă â î ș ț in names and searches). Every finding must name the steps an ordinary person takes, in order, and what goes wrong.

SEVERITY -- THE OWNER'S RULE (1 Nov), it decides when the rounds stop:
- A finding keeps a round open (medium or above) only if it reproduces through ORDINARY STEPS a person takes. Rare roads -- a hand-edited file, many uncommon steps in a row, a clock set wrong on purpose -- are recorded as known (low), EXCEPT data loss.
- Data loss is always serious, however rare the road: anything that loses, corrupts or silently changes a person's notes, files, templates or settings, or a choice that looks safe and destroys.
- high = notes, files or settings lost or corrupted; a crash or a freeze; the safe-looking answer of a question destroying something. medium = on an ordinary road, a person is misled or stuck: a button or key that does not do what it says, an action that silently does nothing or the wrong thing, a message that is false or leaves them with no way forward, a trap where the obvious choice is the bad one, two parts of the app that call one thing by two names in a way that misleads. low = everything else: rare roads (not data loss), polish, wording that is merely clumsy, taste.
Rounds stop after two in a row with nothing of medium or above.

ALREADY FOUND -- do not report again: everything in ${AUDIT} (the audit's register) and every '### <key> (<title>)' heading in ${LOWS3} (the last wave's lows) -- grep both before reporting. DECIDED -- do not report: no Terms & Conditions or "Agree" screen; the phone has no "Follow the phone" theme on purpose; Store review is the feedback route; the app is offline on purpose (no sync, no accounts); history in docs/ISSUES_LOG.md and CHANGELOG.md is the past, not a claim about now.

GROUND TRUTH AT HEAD (do not recompute). Desktop ${DESKTOP}, branch audit/d-lows3: Python + Tkinter, the entry file note_organizer.py (~24,400 lines) plus noteorganizer/core (18 modules, data and rules, no tkinter) and noteorganizer/ui (7 mixins); the full suite passes on Windows and Linux; docs/USER_GUIDE.md says what each thing does. Phone ${ANDROID}, branch audit/a-lows3: Kotlin + Jetpack Compose, app/src/main/java/ro/noteorganizer/app (NoteEditor.kt, NotesScreen.kt, CalendarScreen.kt, SettingsScreens.kt, AppState.kt, Notebook.kt, Organizing.kt, ...), texts in app/src/main/res/values/strings.xml; 938 unit tests and 8 gates pass; README.md and docs/STATUS.md say what works.

HOW TO REPORT. Each finding: the steps a person takes (numbered), the exact code places (file:line) that make it happen, what the person sees, why it matters, and the smallest fix. proved=true only when you traced it through the code yourself; otherwise proved=false and say what you could not settle. Prefer 5 real findings over 25 guesses; spend your effort on about 15 journeys, the likeliest first -- the owner's usage is limited this week: read the functions you need, not whole files. A clean journey is a real result: list what you walked in 'covered'. End with an honest coverage confession: what you did NOT walk.
`

const AREAS = [
  { side: 'desktop', key: 'w2d1-user', focus: `THE DESKTOP, AN ORDINARY PERSON'S FIRST WEEK (${DESKTOP}). Install, first start, the welcome note; writing notes and lists, a table, a checklist; categories (make, rename, delete); a date and a repeating note, the calendar, editing one day; search, sort, Show and groups; a template; the Trash and getting a note back; Export and a backup, then importing it on a second computer; a share code sent and received; Settings (name, theme, Sharp text, reminders, Trash window); closing with work unsaved. Where would they be misled, stuck, or lose something? Read docs/USER_GUIDE.md for what is promised, then the code for what happens.` },
  { side: 'desktop', key: 'w2d1-careless', focus: `THE DESKTOP, A CARELESS OR MISCHIEVOUS PERSON (${DESKTOP}). Ordinary hands doing careless things: double-clicking every button; pressing Enter or Escape on every question without reading; deleting the category of the open note; renaming a category to an existing name, to spaces, to a name with emoji; two notes with one title; a title of only spaces; switching notes, tabs and pages while a dialog, a dropdown or the calculator is open; closing the window from the taskbar with a question open; Ctrl+Z after leaving a note; undoing past a save; pasting a picture, a web page, a spreadsheet; dragging the window to another screen; changing the computer's date, time zone or language while the app is open; the attachments folder emptied by hand while a note shows its files; a second launch while the first is busy.` },
  { side: 'android', key: 'w2a1-user', focus: `THE PHONE, AN ORDINARY PERSON'S FIRST WEEK (${ANDROID}). Install, first start, the welcome note; writing with the on-screen keyboard (autocorrect, the suggestion strip, swipe typing), lists, a table, a checklist; categories; a date and a repeating note, the calendar, editing and moving one day; search, sort, Show and groups; a template; the Trash; Share (text, PDF, web page, share code) and receiving a code from another app; a backup to a file and restoring it on a new phone; the day's reminder notification; Settings. One hand, the phone turned, the back gesture, the keyboard covering the field, larger system fonts, dark mode. Where would they be misled, stuck, or lose something? Read README.md and docs/STATUS.md for what is promised, then the code for what happens.` },
  { side: 'android', key: 'w2a1-careless', focus: `THE PHONE, A CARELESS OR MISCHIEVOUS PERSON (${ANDROID}). Ordinary hands doing careless things: tapping a button twice fast; Back pressed again and again; the phone turned while a sheet or a question is open; the app sent Home mid-edit and Android ending it; a call coming in mid-typing; split screen and a small window; denying the notification permission, then turning the reminder on; the phone's language, date format or 12/24-hour clock changed; the time zone changed by travel across midnight; storage nearly full; sharing a photo, a contact or a huge text into the app; a share code pasted with extra words around it; two codes pasted at once; renaming a category to an existing name or to spaces; deleting the category of the open note; Undo after leaving a note.` },
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
  return `You are an auditor in the final audit of Note Organizer, an offline notes app with a desktop version (Python + Tkinter, ${DESKTOP}) and a phone version (Kotlin, ${ANDROID}) that read the same notebook format. Your one area:

${area.focus}

SCRATCH_DIR = ${W2}\\r1\\${area.key}
${SAFETY}
${WAVE}
Use finding keys starting with "${area.key}-".`
}

function verifierPrompt(side, found) {
  return `You are the skeptic for the ${side} app's wave-2 findings in the final audit of Note Organizer (desktop ${DESKTOP}, phone ${ANDROID}). The auditors reported the findings below. For EACH one, try to REFUTE it: re-trace the steps through the code yourself -- does the handler really do that, is there a guard the auditor missed, does the screen say something else, is it already in the register or the lows (grep them), is it a decision already taken, or are two findings one? Then answer ordinary_steps: would an ordinary person reach it in ordinary use? Re-grade severity by the owner's rule: medium or above only on ordinary steps, except data loss, which stays serious however rare. "confirmed" only when you traced it yourself; "plausible" when you cannot settle it.

SCRATCH_DIR = ${W2}\\r1\\skeptic-${side}
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
  log(`${side} wave 2 round 1: ${found.length} findings, ${weighty.length} of medium or above to the skeptic; lows kept as reported`)
  let verdicts = null
  if (weighty.length) {
    verdicts = await agent(verifierPrompt(side, weighty), { label: `refute:${side}`, phase: 'Refute', schema: VERDICT_SCHEMA })
  }
  results[side] = { reports, verdicts }
}))
return results
