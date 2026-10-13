# How Note Organizer is built with an AI agent

I'm Alexandra Moldovan, and I built Note Organizer with Claude Code, Anthropic's AI coding
agent. I decide what the app does, choose between the options the agent proposes, test the
packaged app by hand, and approve every change. The agent writes most of the code and the
documentation. Tools - CI, static gates, mutation tests, photographed end-to-end walks - check
the agent's work, so nothing rests on its word.

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
   and walks the [surface inventory](../qa/README.md#the-surface-inventory-what-every-new-feature-is-walked-against)
   - what the change touches, what it risks - before writing any code. I approve it or send it back.
2. **A branch of its own.** `main` only receives merged pull requests.
3. **The pre-flight.** Name the mechanism, find its siblings, list every reader of a value whose
   meaning changes, and test the heavy features (tables, recurring notes, attachments,
   formatting) with a small probe.
4. **The fix, with its check.** A regression check lands with the fix, then the fix is taken out
   again to watch the check fail - a *mutant*. A check that stays green without its fix proves
   nothing.
5. **Walk it on the real app.** Story scripts press the keys a person presses, restart the app
   the way a person would close it, and photograph the screen - someone looks at every
   photograph.
6. **The whole suite, on both platforms.** About 3,400 checks, on Windows and in a Linux image
   that matches CI.
7. **My turn.** I review the diff, the commits and what was tested, approve the push, open and
   merge the pull request, then rebuild and test the `.exe`. Whatever only a person can judge -
   whether a screen reads well, whether the eye lands on the safe button - goes into the test
   plan marked as needing my eye.

## How the agent's work is checked

- **Checks are tested too.** Every fix's check is mutation-tested; the mutants worth keeping
  (225, and 2 that test the runner itself) live in [`tools/mutants.json`](../tools/mutants.json)
  and run on demand in CI. A verdict counts only if the suite reached its end - a mutant that
  crashes the import "survives nothing" by running nothing, and the runner refuses it.
- **Findings are hypotheses.** When agents review the app, each finding is checked against the
  code before it is believed, often by separate verifiers told to refute it when unsure. What
  was refuted stays on record, so nobody chases it again
  ([findings register](archive/PRODUCT_FINDINGS.md)).
- **Every report says what it did not cover.** An agent's report ends with what it skipped;
  each such gap gets a verdict - cover it, it is covered elsewhere, or accept it
  ([coverage ledger](archive/COVERAGE_LEDGER.md)).
- **Real numbers only.** Failed rounds and raw scores are reported as they are, never smoothed.
  When a document states a figure, a tool can usually reproduce it (`tools/bench.py` for speed,
  `tools/call_graph.py` for the module split, `tools/verify_findings.py` for the register).
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
| English throughout the repository; comments short and about *why* | **Enforced** in CI (`check_english.py`, `check_comments.py`) whenever code, tests or tools change. A change to the documentation alone skips CI to save minutes; for those, the English check runs in `tools/pre_push_check.py` before the push - a step the agent is asked to take, not one CI repeats. |
| One definition per judgement (no hand-copied field lists) | **Enforced** in CI (`check_one_definition.py`). |
| Text readable in every theme | **Enforced** in CI (`check_contrast.py`, WCAG AA). |
| `core/` never imports the interface | **Enforced** by a unit check. |
| The mutant catalogue still aims at real code | **Enforced** in CI (`check_mutant_targets.py`). |
| Push, merge, pull requests | **Held by me.** Push asks every time; I open and merge every pull request myself. |
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

What the numbers taught: a wave is worth what its verification is worth - the hostile pass
reported one first-run dialog six times, and only the harshness audit noticed - and a grep later
found in one second a defect a 9.9-million-token review wave had reported
([the story](ISSUES_LOG.md#the-safety-net-that-could-not-see-the-gap)).

## AI reviewers and simulations: what they are, and are not

Wherever these documents speak of *reviewers*, *agents*, *waves* or a *panel*, they mean Claude
subagents given a role and a reading list - a designer, a QA lead, a hard-to-please head of
engineering - unless the text names a person. They are useful for finding what a role would look
at; they are not users and not experts.

The colour-blind check is the clearest case. Photographs of the app were transformed to show
what protanopia, deuteranopia and tritanopia take away (the Machado 2009 model), and AI
reviewers that saw only those pictures tried to use the app. That is an approximation: a model
reading a simulation is not a person who sees that way. The test plan keeps a case for a real
colour-blind reader (case 625), and that case is the check that counts.

## Cost

Agents are expensive and greps are free, so the order of work is fixed: mechanical prevention
first (the pre-flight, static gates, mutants - no agent needed), then at most one review wave of
four or five reviewers with separate territories, and a full wave only with my sign-off and a
stated reason. CI minutes are billed too - Windows minutes count double, so the mutant job runs
on Linux, and the workflow skips work a change cannot affect.

## Models

Commits the agent made carry a `Co-Authored-By` line naming the model. Of the 807 commits that are
not merges, 721 carry one (counted at 0.89.371): Claude Opus 5.5 (338), Claude Fable 5 (187),
Claude Opus 5 (167), Claude Sonnet 5 (16) and Claude Opus 4.8 (14). The project's first week, and
a few dozen commits soon after, were made without the convention.

## How to read the other documents

- The [Issues Log](ISSUES_LOG.md) is my own internal engineering journal, not published on this
  site - the day-to-day story of what went wrong and what changed, including the agent's own
  first-person entries ("one of my own renames"). Anyone curious can read it on GitHub.
- The **test plan** ([`qa/NoteOrganizer_TestPlan.xlsx`](../qa/NoteOrganizer_TestPlan.xlsx), with
  an [excerpt in Markdown](TEST_PLAN_EXCERPT.md)) is mine: I walk it, and its status column is
  mine to set.
- [CLAUDE.md](../CLAUDE.md) is written to the agent. Its dated rules ("standing rule, 2026-09-13")
  record when the agent and I agreed them, usually right after something went wrong.
