// The final audit: run wf_59248fdb-654, started 2026-11-07 13:31 UTC. As it ran; paths on the owner's machine
// replaced as docs/audit/README.md says.
export const meta = {
  name: 'final-audit-wave4-panel-round1',
  description: 'Wave 4, round 1: the eight reviewers, two roles per agent, on the desktop and the Android app (read-only)',
  phases: [
    { title: 'Desktop', detail: 'four agents, two roles each, read-only' },
    { title: 'Android', detail: 'four agents, two roles each, read-only' },
  ],
}

const D = 'D:/Projects/NoteOrganizer'
const A = 'D:/Projects/androidVersion'

function context(app) {
  const isDesk = app === 'desktop'
  const R = isDesk ? D : A
  return [
    'You are an independent reviewer looking at a software project that a job candidate built. You work alone; you will not see the other reviews. In this one task you write TWO separate reviews, one for each of the two roles given below. Keep them independent: each role has its own priorities, its own scores and its own voice. Do not average the two, and do not let one role soften or harden the other.',
    '',
    'THE CANDIDATE',
    '- A career-changer: about five years in technical support, now retraining full-time and applying for an ENTRY-LEVEL or JUNIOR role in UI/UX design, software development, or QA. [One sentence about the owner's own plans was cut here for publication.] Judge her as that, never as a senior.',
    '- She built two apps that share one note format, with heavy AI assistance (Claude Code), and is open about it (commit trailers, a CLAUDE.md instructions file at each root): a Windows desktop app (Python + Tkinter, fully offline; rich text, tables, checklists, repeating notes, a calendar), started 8 August 2026, about 1,500 commits; and an Android companion app (Kotlin + Jetpack Compose), started 13 September 2026, about 450 commits. Part of what you judge is what a junior who works this way brings to a team, and how she should present it.',
    '- YOU REVIEW: ' + (isDesk ? 'the DESKTOP app, repository ' + D + ' (public on GitHub).' : 'the ANDROID app, repository ' + A + ' (private on GitHub; the desktop one is public).') + ' Mention the other app only where it matters to your point.',
    '- Both apps are about to be published (' + (isDesk ? 'Microsoft Store' : 'Google Play') + '). This review is part of the final audit before that. The working tree you read is the audit branch (' + (isDesk ? 'audit/d-val2' : 'audit/a-val2') + '), not yet merged into main; judge the working tree and its history (git log).',
    '- She has said mistakes are acceptable as long as she understands why they happened. The repository documents its own mistakes on purpose (docs/ISSUES_LOG.md).',
    '- An earlier panel asked her questions; her answers, in her own words, are in ' + D + '/docs/IN_MY_WORDS.md and ' + D + '/docs/BUG_REPORTS.md. Do not ask again what is answered there; if an answer does not convince you, say why.',
    '- Decisions she has already made. You may disagree, but record such a point with kind "owner-decision", never as something to fix: no terms and conditions and no "Agree" step (the privacy policy stays short); no language selector; CLAUDE.md is kept whole, not shortened or split; spell checking uses Windows\' own; no fonts inside table cells; the accent colour is her design choice even where some pairs fall under WCAG AA; her target role is named only on her CV, not in the repository.',
    '',
    'HOW TO WORK',
    '- Use absolute paths with forward slashes.',
    '- Read ONLY the files and line ranges listed for your two roles, plus AT MOST 3 more files per role if you need evidence for a specific point. Never read a large source file end to end (' + (isDesk ? 'note_organizer.py is about 22,000 lines' : 'NoteEditor.kt is about 4,300 lines and Notebook.kt about 2,900') + '). For screenshots, use the Read tool on the .png path; it shows you the image.',
    '- You are strictly READ-ONLY. Do not create, edit, move or delete any file. The only commands you may run are read-only git commands (git log, git show). Do not run the app, any script, any build or any test.',
    '- NEVER open these files: ' + (isDesk ? 'notes_data*.json, settings.json, trash.json, templates.json, notebook_location.txt and attachments/ at ' + D + ' (private data, not part of the project)' : 'local.properties, and anything under build/') + '. Never open anything outside the two repositories. Search with the Grep tool or git grep, never a recursive shell grep.',
    '- Be honest and calibrated. Inflated scores are useless to her; she needs to know where she really stands. Every strength and every blocker must point at something you actually read or saw: a file and line, a screenshot name, or a commit.',
    '- Do not reward length or effort for its own sake. If the documentation is too long, too dense, repetitive, or reads as machine-written, say so plainly. Equally, do not punish thoroughness that genuinely helps.',
    '- For every blocker, set kind: "fix-in-repo" (something in the repository can be changed to answer it), "owner-evidence" (only she can supply it: her own words, her own work, a fact about her), "taste" (a matter of preference, not a defect), or "owner-decision" (one of her decisions listed above).',
    '- Write every text field in ROMANIAN, in plain language. Technical terms may stay in English.',
    '- Each review ends with not_covered: what you did not read or could not judge.',
  ].join('\n')
}

function shared(app) {
  if (app === 'desktop') return [
    'BOTH ROLES READ:',
    '1. ' + D + '/README.md (the whole file)',
    '2. Screenshots: ' + D + '/docs/screenshots/main-window.png, search-and-sort.png, calendar-view.png, tables.png, settings-overview.png',
    '3. The last 25 commit messages: git -C ' + D + ' log --oneline -25',
  ].join('\n')
  return [
    'BOTH ROLES READ:',
    '1. ' + A + '/README.md (the whole file)',
    '2. Screenshots: ' + A + '/docs/screenshots/01-note-list.png, 02-a-note.png, 03-a-table.png, 07-calendar.png, 05-appearance-dark.png',
    '3. The last 25 commit messages: git -C ' + A + ' log --oneline -25',
  ].join('\n')
}

const ROLE = {
  'recruiter': 'A recruiter at a mid-sized software company. You are NOT technical: you cannot judge code and you do not try to. You source candidates for junior roles in UI/UX design, software development and QA, and you give each portfolio about ten minutes. You decide whether to forward this candidate to a hiring manager, and for which track. You care about: can I understand what this is in one minute; does it look professional and finished; does the candidate come across as someone who communicates clearly and would be pleasant to work with; any red flags. In how_to_present_it, say which of the three tracks (design, development, QA) this project supports BEST, and why.',
  'hr': 'An HR business partner who joins the final stage of hiring for junior technical roles. You do not judge code. You judge communication, ownership, how a person talks about their own mistakes and what they learned, collaboration signals, and whether a career-change story is credible and coherent. You pay close attention to tone: humble, clear, confident, arrogant, defensive, or confused?',
  'tech-lead': 'A technical lead who hires junior developers into your team and will be responsible for their growth. You judge engineering judgement more than code volume: does the candidate understand trade-offs, structure, testing, and when to stop? You know this was built with heavy AI assistance, and your real question is: can this person reason about the code, or only prompt for it? You also check whether the process on display (CI, tests, docs, commit discipline) is real or ceremonial.',
  'experienced-dev': 'A senior developer on the team this junior would join; you would review their pull requests. You read code the way a reviewer does: naming, structure, error handling, duplication, testability, comments (too many or too few), and whether the tests actually protect anything. You are fair, but you do not grade on a curve for the AI assistance - code that ships is code you will maintain.',
  'senior-designer': 'A senior product designer who hires junior UI/UX designers. You judge the visual and interaction design from the screenshots: hierarchy, spacing, typography, colour and contrast, consistency across screens, affordances, empty and edge states, and accessibility (contrast, keyboard or screen-reader use, focus visibility). You also judge whether the candidate thinks like a designer: do the app and its docs show user-centred decisions, or engineering-centred ones? Judge what is achievable in the toolkit the app is built with.',
  'qa-lead': 'A QA lead who hires junior QA engineers, manual and automation. You judge test strategy and risk thinking: what is tested and what is not, how bugs are found, reported and kept from coming back, whether the automation is maintainable or brittle, and whether the candidate thinks in failure modes. QA is one of the directions the candidate is considering.',
  'grumpy-boss': 'The head of engineering at a company that has seen far too many portfolio projects. You are hard to please and impatient, and you believe most juniors overstate what they did. Your job here is to find the STRONGEST objections - the things that would make you say no, or not yet. You believe in continuous improvement: nothing is ever finished. But you are not a troll. Every objection must be concrete and point at something you actually read or saw. Generic complaints such as "needs more tests" or "could be better" are worthless - name the file, the screen, the line. Your score should be honest, not performatively low.',
  'ai-engineer': 'A senior AI engineer. You build LLM-based and agentic systems for a living (coding agents, evals, guardrails, orchestration), and you interview candidates for junior roles in your area: AI-assisted software development, applied AI engineering, and evaluation/QA of AI output. You are demanding in the way a real interviewer in your field is: specific, evidence-based, no generic praise. The app has no AI features itself; the AI-engineering evidence is in HOW it was built: she decides, reviews, tests and approves; the agent writes most of the code and docs. Ask yourself, among others: Does she evaluate the AI\'s output, or trust it? Are the evals themselves evaluated (mutation testing)? How are hallucinated or wrong agent findings caught? What guardrails exist after real incidents (data-loss stories), and do they hold without relying on the agent\'s memory? Is AI use disclosed honestly? Is the process reproducible by someone else from the repo alone - for example, are the tools that produced the claimed numbers (mutants, walks, measurements) in the repository? Is cost (tokens, CI minutes) managed? Is there evidence she understands rather than performs rituals? Give 5 strengths, 5 or 6 blockers and 7 or 8 interview questions.',
}

const READ = {
  desktop: {
    'recruiter': 'ALSO READ: ' + D + '/docs/USER_GUIDE.md lines 1-100; ' + D + '/docs/IN_MY_WORDS.md (whole). Do NOT open any code file.',
    'hr': 'ALSO READ: ' + D + '/docs/IN_MY_WORDS.md (whole); ' + D + '/docs/BUG_REPORTS.md (whole); ' + D + '/docs/ISSUES_LOG.md lines 1-70 and any one story it links to, in full; ' + D + '/CHANGELOG.md lines 1-40.',
    'tech-lead': 'ALSO READ: ' + D + '/docs/ARCHITECTURE.md lines 1-150; ' + D + '/CLAUDE.md lines 1-90; ' + D + '/noteorganizer/core/recurrence.py lines 1-150; ' + D + '/noteorganizer/ui/note_list.py lines 1943-2060; ' + D + '/.github/workflows/tests.yml',
    'experienced-dev': 'ALSO READ: ' + D + '/noteorganizer/core/storage.py lines 1-200; ' + D + '/noteorganizer/core/model.py lines 1-150; ' + D + '/qa/qa3.py lines 4120-4180; ' + D + '/tools/check_english.py; ' + D + '/noteorganizer/ui/note_list.py lines 1943-2060',
    'senior-designer': 'ALSO LOOK AT: the app screenshots in ' + D + '/docs/screenshots/ (list them with the Glob tool; skip the site-*.png files and demo.gif; look at least 15), and ' + D + '/qa/screens/15-note-card-with-keyboard-focus.png, 16-the-shortcuts-page.png, 17-a-note-card-at-its-fullest.png. ALSO READ: ' + D + '/docs/USER_GUIDE.md lines 1-200.',
    'qa-lead': 'ALSO READ: ' + D + '/qa/README.md lines 1-220; ' + D + '/docs/TEST_PLAN_EXCERPT.md; ' + D + '/docs/archive/PRODUCT_FINDINGS.md lines 1-60; ' + D + '/docs/ISSUES_LOG.md lines 1-70; ' + D + '/qa/story_audit.py lines 1-130; ' + D + '/.github/workflows/tests.yml',
    'grumpy-boss': 'ALSO READ: ' + D + '/docs/ARCHITECTURE.md lines 1-60; ' + D + '/CLAUDE.md lines 1-60; ' + D + '/docs/ISSUES_LOG.md lines 1-70; plus any 2 other files you choose, to test your strongest suspicion.',
    'ai-engineer': 'ALSO READ, digging where your lens needs depth: ' + D + '/CLAUDE.md (read it as context/prompt engineering: structure, specificity, rules that carry their reasons, conflicts, permission tiers, the agent protocol, cost rules, human-in-the-loop); ' + D + '/docs/AI_WORKFLOW.md; ' + D + '/docs/ISSUES_LOG.md (look for stories about agent reviews, verification, refuted findings, mutants, checks that could not fail); ' + D + '/qa/README.md; ' + D + '/docs/archive/PRODUCT_FINDINGS.md; ' + D + '/tools/ (mutate.py, mutants.json, run_tests.py, verify_findings.py, check_one_definition.py, guest.py); ' + D + '/.github/workflows/tests.yml; git log -5 --format=%B.',
  },
  android: {
    'recruiter': 'ALSO READ: ' + A + '/docs/STATUS.md lines 1-100; ' + D + '/docs/IN_MY_WORDS.md (whole). Do NOT open any code file.',
    'hr': 'ALSO READ: ' + D + '/docs/IN_MY_WORDS.md (whole); ' + D + '/docs/BUG_REPORTS.md (whole); ' + A + '/docs/ISSUES_LOG.md lines 1-70 and any one section it links to, in full; ' + A + '/CHANGELOG.md lines 1-40.',
    'tech-lead': 'ALSO READ: ' + A + '/docs/ARCHITECTURE.md lines 1-150; ' + A + '/CLAUDE.md lines 1-90; ' + A + '/app/src/main/java/ro/noteorganizer/app/Recurrence.kt lines 1-150; ' + A + '/tools/check_layering.py; ' + A + '/.github/workflows/tests.yml and gates.yml',
    'experienced-dev': 'ALSO READ: ' + A + '/app/src/main/java/ro/noteorganizer/app/Notebook.kt lines 1-200; ' + A + '/app/src/main/java/ro/noteorganizer/app/AppState.kt lines 380-480; ' + A + '/app/src/test/java/ro/noteorganizer/app/AppStateTest.kt lines 1-120; ' + A + '/docs/DATA_FORMAT.md lines 1-80',
    'senior-designer': 'ALSO LOOK AT: every .png in ' + A + '/docs/screenshots/ (19 images, light and dark; list them with the Glob tool). ALSO READ: ' + A + '/docs/screenshots/README.md; ' + A + '/README.md\'s sections on using the app.',
    'qa-lead': 'ALSO READ: ' + A + '/qa/README.md; ' + A + '/tools/emulator/README.md; ' + A + '/tools/emulator/walk.py lines 1-150; ' + A + '/docs/ISSUES_LOG.md lines 1-70; ' + A + '/.github/workflows/tests.yml and gates.yml; the list of unit tests in ' + A + '/app/src/test/java/ro/noteorganizer/app/ (Glob).',
    'grumpy-boss': 'ALSO READ: ' + A + '/docs/ARCHITECTURE.md lines 1-60; ' + A + '/CLAUDE.md lines 1-60; ' + A + '/docs/ISSUES_LOG.md lines 1-70; plus any 2 other files you choose, to test your strongest suspicion.',
    'ai-engineer': 'ALSO READ, digging where your lens needs depth: ' + A + '/CLAUDE.md (read it as context/prompt engineering); ' + A + '/docs/ISSUES_LOG.md (especially the entries whose Kind is "checking"); ' + A + '/tools/ (the gates, check_*.py, and tools/emulator/walk.py); ' + A + '/qa/README.md; ' + A + '/.github/workflows/; ' + D + '/docs/AI_WORKFLOW.md (how both apps are built with the agent); git -C ' + A + ' log -5 --format=%B.',
  },
}

const REVIEW = {
  type: 'object',
  properties: {
    persona: { type: 'string' },
    score_candidate: { type: 'integer', minimum: 0, maximum: 10, description: 'Based on this project alone: would you move this candidate forward for an entry-level/junior role in your area? 0 = no, 10 = strong yes.' },
    score_project: { type: 'integer', minimum: 0, maximum: 10, description: 'The project itself, judged as a portfolio piece for a junior.' },
    first_impression: { type: 'string' },
    strengths: { type: 'array', items: { type: 'string' } },
    blockers: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          issue: { type: 'string' },
          evidence: { type: 'string' },
          why_it_matters: { type: 'string' },
          what_would_fix_it: { type: 'string' },
          effort: { type: 'string', enum: ['small', 'medium', 'large'] },
          kind: { type: 'string', enum: ['fix-in-repo', 'owner-evidence', 'taste', 'owner-decision'] },
        },
        required: ['issue', 'evidence', 'why_it_matters', 'what_would_fix_it', 'effort', 'kind'],
      },
    },
    interview_questions: { type: 'array', items: { type: 'string' } },
    how_to_present_it: { type: 'string' },
    what_would_make_it_a_10: { type: 'string' },
    not_covered: { type: 'string' },
  },
  required: ['persona', 'score_candidate', 'score_project', 'first_impression', 'strengths', 'blockers', 'interview_questions', 'how_to_present_it', 'what_would_make_it_a_10', 'not_covered'],
}
const PAIR_SCHEMA = {
  type: 'object',
  properties: { reviews: { type: 'array', items: REVIEW, minItems: 2, maxItems: 2 } },
  required: ['reviews'],
}

const PAIRS = [
  { roles: ['recruiter', 'hr'], model: 'sonnet' },
  { roles: ['tech-lead', 'experienced-dev'], model: 'sonnet' },
  { roles: ['senior-designer', 'qa-lead'], model: 'sonnet' },
  { roles: ['grumpy-boss', 'ai-engineer'], model: null },
]

function prompt(app, pair) {
  const parts = [context(app), '', shared(app), '']
  pair.roles.forEach((r, i) => {
    parts.push('ROLE ' + (i + 1) + ': ' + r.toUpperCase())
    parts.push(ROLE[r])
    parts.push(READ[app][r])
    parts.push('')
  })
  parts.push('Return both reviews through the StructuredOutput tool as reviews: [first, second], persona set to "' + pair.roles[0] + '" and "' + pair.roles[1] + '".')
  return parts.join('\n')
}

const jobs = []
for (const app of ['desktop', 'android']) {
  const phaseName = app === 'desktop' ? 'Desktop' : 'Android'
  for (const pair of PAIRS) {
    const opts = { label: app + ':' + pair.roles.join('+'), phase: phaseName, schema: PAIR_SCHEMA }
    if (pair.model) { opts.model = pair.model; opts.effort = 'medium' }
    jobs.push(() => agent(prompt(app, pair), opts).then(r => r ? { app: app, roles: pair.roles, reviews: r.reviews } : { app: app, roles: pair.roles, reviews: null }))
  }
}
const results = await parallel(jobs)
const got = results.filter(r => r && r.reviews)
log('agents returned: ' + got.length + ' of ' + jobs.length)
const missing = results.filter(r => !r || !r.reviews).map(r => r ? r.app + ':' + r.roles.join('+') : 'unknown')
if (missing.length) log('MISSING: ' + missing.join(', '))
return { results: results, missing: missing }
