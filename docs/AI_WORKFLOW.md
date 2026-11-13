# How Note Organizer is built with an AI agent

I'm Alexandra Moldovan, and I built Note Organizer with Claude Code, Anthropic's AI coding
agent. I decide what the app does, choose between the options the agent proposes, test the
packaged app by hand, and approve every change. The agent writes most of the code and the
documentation. Tools - CI, static gates, mutation tests, photographed end-to-end walks - check
most of the agent's work; what rests on review instead is named in the table below.

This page explains that process. The agent's rules are in [CLAUDE.md](../CLAUDE.md), what went
wrong and what changed is in the [Issues Log](ISSUES_LOG.md), and my own account of the work is
in [In my words](IN_MY_WORDS.md).

## Contents

- [Who does what](#who-does-what)
- [One change, start to finish](#one-change-start-to-finish)
- [How the agent's work is checked](#how-the-agents-work-is-checked)
- [What is enforced, and what is only asked](#what-is-enforced-and-what-is-only-asked)
- [Guardrails that came from real incidents](#guardrails-that-came-from-real-incidents)
- [Agent reviews, in numbers](#agent-reviews-in-numbers)
- [The final audit](#the-final-audit)
- [AI reviewers and simulations: what they are, and are not](#ai-reviewers-and-simulations-what-they-are-and-are-not)
- [Cost](#cost)
- [Models](#models)
- [How to read the other documents](#how-to-read-the-other-documents)

## Who does what

| | Me (Alexandra) | Agent (Claude Code) | Tools |
|---|---|---|---|
| What the app does | Decide; refuse ideas (see [Explicitly not planned](ROADMAP.md#explicitly-not-planned-right-now)) | Proposes options, with trade-offs | - |
| The code | Approve each change before it is pushed | Writes it, under [CLAUDE.md](../CLAUDE.md) | Static gates, unit and qa suites, CI on Windows and Linux |
| Is it right? | Walk the [test plan](../qa/NoteOrganizer_TestPlan.xlsx) on the packaged `.exe`; judge what no script can see | Proves the fix with a check that fails without it, a mutant, and photographs of the real app | `tools/mutate.py`, `qa/story_*.py`, the contrast gate |
| GitHub | Open and merge every pull request; file the issues | Writes the PR and issue texts for me to review | - |

Between sessions, the agent keeps a private memory: short notes it writes for itself - a
correction I made, a decision I took, where it left off - and reads back at the start of the
next session. It lives on my machine, outside the repository, so it isn't part of the record
here. A lesson meant to bind every session goes in [CLAUDE.md](../CLAUDE.md) instead, where it
can be reviewed; the memory is just the agent's working notebook.

## One change, start to finish

1. **Investigate, then plan.** For anything beyond a trivial fix, the agent explains its approach
   and walks the [surface inventory](../qa/README.md#the-surface-inventory-what-every-new-feature-is-walked-against) -
   what the change touches, what it risks - before writing any code. I approve it or send it back.
2. **A branch of its own.** The agent's work reaches `main` only as a merged pull request (a typo
   I fix by hand may go straight there: [GIT_WORKFLOW](GIT_WORKFLOW.md#scenario-a-trivial-docs-only-fix-straight-to-main)).
3. **The pre-flight.** Name the mechanism, find its siblings, list every reader of a value whose
   meaning changes, and test the heavy features (tables, recurring notes, attachments,
   formatting) with a small probe.
4. **The fix, with its check.** A regression check lands with the fix, then the fix is taken out
   again to watch the check fail - a *mutant*. A check that stays green without its fix proves
   nothing.
5. **Walk it on the real app.** Story scripts press the keys a person presses, restart the app
   the way a person would close it, and photograph the app's window - someone looks at every
   photograph.
6. **The whole suite, on both platforms.** About 5,000 checks, on Windows and in a Linux image
   that matches CI.
7. **My turn.** I review the diff, the commits and what was tested, approve the push, open and
   merge the pull request, then rebuild and test the `.exe`. Whatever only a person can judge -
   whether a screen reads well, whether the eye lands on the safe button - goes into the test
   plan marked as needing my eye.

## How the agent's work is checked

- **Checks are tested too.** Every fix's check is mutation-tested; the mutants worth keeping,
  and 2 that test the runner itself, live in [`tools/mutants.json`](../tools/mutants.json)
  and run on demand, here or in CI, a piece of the catalogue at a time; the whole of it last
  ran on 10 November 2026, and the 11 of its 1,161 verdicts that came out wrong, each the fault
  of a check or of the catalogue and none of the app, were put right that day. A verdict counts only if the suite reached its end - a mutant that
  crashes the import "survives nothing" by running nothing, and the runner refuses it.
- **Findings are hypotheses.** When agents review the app, each finding is checked against the
  code before it is believed, often by separate verifiers told to refute it when unsure. What
  was refuted stays on record, so nobody chases it again
  ([findings register](archive/PRODUCT_FINDINGS.md)).
- **Every report says what it did not cover.** An agent's report ends with what it skipped,
  and the gaps are weighed with the findings. Until October 2026 each one got a written
  verdict - cover it, it is covered elsewhere, or accept it - in a
  [coverage ledger](archive/COVERAGE_LEDGER.md), now archived.
- **Real numbers only.** Failed rounds and raw scores are reported as they are, never smoothed.
  When a document states a figure, a tool can usually reproduce it (`tools/bench.py` for speed,
  `tools/call_graph.py` for the module split, `tools/verify_findings.py` for the register).
  The final audit's figures cannot be: they were counted from the rounds' own records, which
  are kept outside the repository; the prompts that ran them are [published in it](audit/README.md).
- **The screen, not only the code.** Some bugs exist only in a photograph - a colour, a cut-off
  label. The story scripts and `tools/doc_screenshots.py` photograph the running app, and a fix
  to anything visible is looked at before it is called done.

## What is enforced, and what is only asked

A rule an agent is only asked to follow can be forgotten. The ones that matter most are held by
something that does not depend on the agent remembering:

| Rule | How it is held |
|---|---|
| Tests never run where they could wipe real notes | **Enforced.** The agent's deny list refuses any shell command that would start a destructive script in the project folder; `tools/run_tests.py` runs everything in a fresh scratch copy; the qa scripts' hermetic seed refuses to start outside one, or beside a notebook that holds notes. |
| Every destructive script has a deny rule | **Enforced** in CI by `tools/check_agent_rules.py`, which finds the scripts itself. |
| English throughout the repository; comments short and about *why* | **Enforced** in CI (`check_english.py`, `check_comments.py`) whenever code, tests or tools change; a change to the documentation alone runs the English check too, with the test plan's and the links' (below). |
| One definition per judgement (no hand-copied field lists) | **Enforced** in CI for nine named questions (`check_one_definition.py`); a question asked in a new place joins it by hand. |
| Text readable in every theme | **Enforced** in CI (`check_contrast.py`, WCAG AA). |
| `core/` never imports the interface | **Enforced** by a unit check. |
| The mutant catalogue still aims at real code | **Enforced** in CI (`check_mutant_targets.py`). |
| The test plan's numbers in the documents are the plan's, and their links lead somewhere | **Enforced** in CI (`check_test_plan.py`, `check_doc_links.py`), on every change to a document or the plan. |
| One heavy job at a time; a test held to a memory ceiling, every child to a time limit | **Enforced** for this repository's runners by `tools/guest.py` (an OS lock on the machine, a job object or RLIMIT_AS), and in CI by `check_guest.py`, which finds the runners by what they do. The Linux image runs only through `tools/linux_ci.py`. The Android build and its emulator: **asked**. |
| CI may only read the code, and runs only the actions it named | **Enforced** in CI (`check_workflows.py`): every workflow's token is read-only, every action is pinned to a commit, and no trigger hands a fork the repository's rights. The same gate holds the phone's repository. |
| A picture of the app shows only the app | **Enforced** by the one shutter every photographer uses (`qa/_qa_support.photograph`): it refuses a picture another program's window is over. |
| Push, merge, pull requests | **Held by me.** Push asks every time; I open and merge every pull request myself. |
| Code from GitHub is looked at before it runs here | **Asked.** After every pull the agent shows what arrived, and stops at a commit nobody here made; a stranger's pull request is only read on GitHub ([CLAUDE.md](../CLAUDE.md#code-that-arrives-from-github-the-owners-rule-2026-11-12)). |
| The pre-flight, the surface walk, the mutant for each fix, the photographs looked at, the report of what was not covered | **Asked.** Written in CLAUDE.md, checked by my review and by the next round finding what was skipped. |

## Guardrails that came from real incidents

Real notes were lost more than once early in the project - a misdirected cleanup, and a test run
from the wrong folder ([the story](ISSUES_LOG.md#the-cleanup-that-deleted-the-real-notebook)).
Each loss became a mechanism: tests run only from a scratch copy, destructive scripts are denied
by name in every spelling that could start them, my own notebook lives outside the working tree,
and any test that could delete a notebook checks for real notes first and refuses. The rule in
CLAUDE.md sums it up: the deny list exists because an agent's judgement about whether *this*
run is safe is the thing that failed.

## Agent reviews, in numbers

| When | Shape | Result |
|---|---|---|
| Early September 2026 | Code audit: ten read-only subsystem auditors, then adversarial critics | 152 findings; every one that warranted code shipped in five releases ([ROADMAP](ROADMAP.md#the-code-audit-programme-2026-09)) |
| 10 September | Product tour: four lenses, one adversarial verifier per finding | 33 kept, 4 refuted ([register](archive/PRODUCT_FINDINGS.md)) |
| 10 September | Hostile pass: five unkind lenses, three refute-by-default verifiers per finding | 27 kept (about 17 distinct), 7 refuted; a harshness audit on top found the worst items |
| 11 September | Thirteen hostile reviewers, three verifiers per material finding, a completeness critic | 33 kept; the critic's audit of the wave itself drove three fixes ([0.71.154](../CHANGELOG.md#071154--2026-09-11)) |
| Late September – 2 October | Nineteen rounds trying to break the app, each aimed at what the last one changed | Every finding reproduced with a probe before it was fixed ([0.83.335](../CHANGELOG.md#083335--2026-10-02)) |
| 8 October | Five reviewer personas on the palette, five rounds; four reviewers on colour-blindness simulations | The palette of [0.89.365](../CHANGELOG.md#089365--2026-10-08); the fixes of [0.89.371](../CHANGELOG.md#089371--2026-10-08) |
| 27 October – 8 November | The final audit before the stores, both apps, in waves of rounds, every finding of medium severity or worse re-graded by a sceptic | 1,246 findings; of the 756 re-graded, 6 refuted, 69 lowered, 85 told twice ([the final audit](#the-final-audit)) |

What the numbers taught: a wave is worth what its verification is worth - the hostile pass
reported one first-run dialog six times, and only the harshness audit noticed - and a grep later
found in one second a defect a 9.9-million-token review wave had reported
([the story](ISSUES_LOG.md#the-safety-net-that-could-not-see-the-gap)).

## The final audit

Before the Microsoft Store and Google Play, both apps went through one audit, from 27 October
2026. *Ready* was defined first: notes are never lost or damaged; nothing makes the app stop or
freeze, even on purpose; nothing from outside runs or leaves the notebook's folder; the stores'
rules are met; everything the documents say is true of the code; an ordinary person understands
every screen; the repositories are clean; the review panel has no objection of substance; and I
have walked the test plans on the final builds.

How a round worked:

- **Agents attacked the app** in a role - an ordinary person's week, a careless hand, hostile
  and huge input - each reading the code and running probes in a scratch copy.
- **Every finding of medium severity or worse was re-graded** before it counted: by a sceptic
  agent in waves 1 to 4, and in waves 5 and 6 by the agent leading the audit, checking it in
  the code. The severity rule is mine (1 November): only steps an ordinary person takes keep a
  round open, and a loss of notes is always serious.
- **Every fix came with a check, and a mutant**, where a check can reach it: the fix broken on
  purpose, to watch the check fail ([the desktop's catalogue](../tools/mutants.json)). The few
  no check can reach (a write with no effect today) are named in the issues log, and so is the
  walk or the probe, where one stood in.
- **The next round attacked the last round's fixes by name**, and the code beside them. A fix is
  a new road, and more than once it was the next round's finding.
- **A wave closed after two rounds in a row with nothing of medium severity or worse.** Its low
  findings were fixed in a wave of their own, verified the same way.

| Wave | Aim | Desktop | Phone |
|---|---|---|---|
| 0 | Mechanical: licences, history, packaging | done in one pass | done in one pass |
| 1 | Lost notes, hostile and huge input, security, accessibility | closed at round 20 | closed at round 25 |
| 1's lows | The low findings of wave 1 | closed at verification round 11 | closed at verification round 11 |
| 3 | What read as generated rather than written, in code and documents | closed at round 8 * | closed at round 8 * |
| 2 | An ordinary person's week, and a careless hand | closed at round 14 | closed at round 25 |
| 2's lows | The low findings of wave 2 | closed at verification round 8 | closed at verification round 10 |
| 4 | [The review panel](audit/wave4/README.md): eight roles, two to an agent | closed at round 4 † | closed at round 4 † |
| 5 | The release: a full reading of both apps, its fixes attacked by name, the builds proved | closed at round 2 | closed at round 8 ‡ |

\* Not by the two-clean-rounds rule. After round 5 I narrowed what kept a round of wave 3 open
to what a person using the app would meet and be misled by, and chose round 8 as the last.

† Not by its own rule either, which was to stop once the scores no longer rose. I chose the
fourth round as the last before it ran, and the scores still rose in it: for the person who
built it and for the project, the desktop's from 6.38 and 7.25 to 6.75 and 7.38, the phone's
from 6.62 and 6.88 to 6.88 and 7.50. What it found untrue in the code and the documents was fixed after it;
what it proposed beyond that waits for my decision.

‡ By the two-clean-rounds rule as I settled it on 12 November: a gap in what a self-test covers,
while the tool it tests is right, is a low finding. Rounds 3 to 8 attacked the phone's new runner
for the emulator walk; from round 6 on, none could break what it promises.

Wave 5 began with a reading rather than an attack. On 11 November ten read-only agents read both
apps' code and documents, and I checked what they reported in the code before it counted: 26
findings confirmed, 2 refuted, 8 written down unchecked. What reached a person, with five desktop
findings the phone's port had kept since October, became the desktop's eleven fixes in 0.100.524
and the phone's five in 0.14.1; the rest were documents and comments put right. A mini-audit then
attacked each fix by name. One more came after it: the desktop's
Statistics tile had changed, and the phone, ported from the old rule, was never asked; the
release build's photograph showed it, and it is 0.14.2. Then both apps were built and proved:
the desktop's package in Windows Sandbox and by the certification kit
([Windows release](RELEASE_WINDOWS.md#packing-it-and-proving-it-in-windows-sandbox)), the
phone's release build on the emulator.

The phone needed more rounds than the desktop in waves 1 and 2, and its issues log says why: most
of the extra rounds found the round before's own fixes wrong. Custom order's drag took twelve
rounds to settle; the list's messages were redone five times, and settled only once the phone
did what the desktop already did.

What each round found is in the [issues log](ISSUES_LOG.md), from
[A file with two names](ISSUES_LOG.md#a-file-with-two-names) on. The rounds' own records give
the numbers (counted 8 November 2026): each agent's findings with the severity it gave them, and
each verdict of the sceptic. The records stay outside the repository, with the probes; the
prompts are published, as they ran, in [the audit's folder](audit/README.md).

| Wave | App | Findings: all (high or worse / medium / low) | Shown by a probe | Re-graded by a sceptic: kept / told twice / refuted / lowered |
|---|---|---|---|---|
| 1 | Desktop | 309 (63 / 101 / 145) | 290 | 264: 232 / 32 / 0 / 20 |
| 1 | Phone | 268 (53 / 97 / 118) | 172 | 219: 182 / 35 / 2 / 16 |
| 1's lows | Desktop | 39 (0 / 9 / 30) | 35 | 9: 8 / 0 / 1 / 0 |
| 1's lows | Phone | 39 (0 / 16 / 23) | 32 | 16: 16 / 0 / 0 / 5 |
| 3 | Desktop | 120 (3 / 56 / 61) | 120 | 59: 51 / 6 / 2 / 6 |
| 3 | Phone | 111 (1 / 52 / 58) | 109 | 53: 50 / 3 / 0 / 6 |
| 2 | Desktop | 103 (9 / 39 / 55) | 97 | 48: 44 / 4 / 0 / 6 |
| 2 | Phone | 147 (3 / 71 / 73) | 129 | 72: 68 / 4 / 0 / 7 |
| 2's lows | Desktop | 53 (2 / 9 / 42) | 51 | 11: 10 / 0 / 1 / 2 |
| 2's lows | Phone | 57 (0 / 5 / 52) | 55 | 5: 4 / 1 / 0 / 1 |

In all, 1,246 findings, 1,090 of them shown by a probe rather than argued from the code. The
sceptic seldom refuted - 6 of the 756 it re-graded - and earned its place another way: it lowered
69 and caught 85 told twice. Most rounds after the first sent an agent after the last round's
fixes by name and the code beside them; in wave 1 those agents found 175 of the desktop's 309
findings and 120 of the phone's 268.

The agents used about 107 million tokens, as their runs recorded them: wave 1, 49.2 million;
its lows, 8.2; wave 3, 8.7; wave 2, 22.9; its lows, 11.2; the panel's first two rounds, 2.1, and
its fourth, 1.0; wave 5, 3.85 (the reading 2.63, the mini-audits 1.22). The whole audit had been
estimated at 8 to 13 million before it began. The count leaves out the main
session's own work between rounds, and the panel's third round, given to two agents by hand.

## AI reviewers and simulations: what they are, and are not

Wherever these documents speak of *reviewers*, *agents*, *waves* or a *panel*, they mean Claude
subagents given a role and a reading list - a designer, a QA lead, a hard-to-please head of
engineering - unless the text names a person. They are useful for finding what a role would look
at; they are not users and not experts.

The colour-blind check is the clearest case. Photographs of the app were transformed to show
what protanopia, deuteranopia and tritanopia take away (the Machado 2009 model), and AI
reviewers that saw only those pictures tried to use the app. That is an approximation: a model
reading a simulation is not a person who sees that way. The test plan's case 625 records this
simulated check. No colour-blind reader has looked at the app yet: that is the check still owed,
planned for the feedback after the public launch (see the [Roadmap](ROADMAP.md#under-consideration)).

## Cost

Agents are expensive and greps are free, so the order of work is fixed: mechanical prevention
first (the pre-flight, static gates, mutants - no agent needed), then at most one review wave of
four or five reviewers with separate territories, and a full wave only with my sign-off and a
stated reason. CI minutes are billed too - Windows minutes count double, so the mutant job runs
on Linux, and the workflow skips work a change cannot affect.

The final audit was such a sign-off, and it ran far past its estimate: about 107 million agent
tokens against 8 to 13 million ([the numbers](#the-final-audit)). The rounds made the difference.
A wave closed only after two clean rounds in a row, and waves 1 and 2 took 14 to 25, most of
them attacking the last round's fixes. A finding cost about 85,000 tokens in wave 1, 92,000 in
wave 2, over 100,000 in the waves of low findings, and 38,000 in wave 3, where I chose the last
round. On 31 October, with half a week's allowance spent, each round was cut to two agents per
app; no wave had a ceiling of its own, and each stopped by the severity rule alone.

## Models

Commits the agent made carry a `Co-Authored-By` line naming the model. Of the 1,280 commits that
are not merges, 1,194 carry one (counted on 7 November 2026, on the final audit's branch at
`dd891e9`): Claude Opus 5.5 (810), Claude Fable 5 (187), Claude Opus 5 (167), Claude Sonnet 5
(16) and Claude Opus 4.8 (14). The project's first week, and a few dozen commits soon after,
were made without the convention.

## How to read the other documents

- The [Issues Log](ISSUES_LOG.md) is the project's internal engineering journal, written by the
  agent and not published on this site - the day-to-day story of what went wrong and what
  changed, so its first person ("one of my own renames") is the agent. Once the repository is
  public, anyone curious can read it on GitHub.
- The **test plan** ([`qa/NoteOrganizer_TestPlan.xlsx`](../qa/NoteOrganizer_TestPlan.xlsx), with
  an [excerpt in Markdown](TEST_PLAN_EXCERPT.md)) is mine: I walk it, and its status column is
  mine to set.
- [CLAUDE.md](../CLAUDE.md) is written to the agent. Its dated rules ("standing rule, 2026-09-13")
  record when the agent and I agreed them, usually right after something went wrong.
