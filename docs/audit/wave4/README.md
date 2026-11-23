# The review panel

The final audit's last wave, on 7 and 8 November 2026, asked eight reviewers how the two apps
and their repositories read, rather than whether they break. This page says who the reviewers
were, what they scored, and what came of each round. Their prompts are beside it; the
[index of the audit's prompts](../README.md) says how they were published.

**Contents:** [The reviewers](#the-reviewers) · [The rounds](#the-rounds) ·
[The scores](#the-scores) · [The objections, by kind](#the-objections-by-kind) ·
[What came of each round](#what-came-of-each-round)

## The reviewers

Eight roles, two to an agent, four agents per app. They only read: no app, script or test was
run.

| Role | Reads for |
|---|---|
| Recruiter | Not technical: what the project is in a minute, whether it looks finished, red flags |
| HR business partner | Communication, ownership, how mistakes are told and what was learned |
| Tech lead | Judgement: trade-offs, structure, testing, when to stop; whether the process is real |
| Experienced developer | The code as a reviewer of pull requests reads it |
| Senior product designer | The screens: hierarchy, spacing, type, colour, states, accessibility |
| QA lead | Test strategy and risk: what is tested, what is not, how bugs stay fixed |
| Head of engineering, hard to please | The strongest objections, each pointing at a file, a screen or a line |
| AI engineer | How the agent was directed, checked, held to rules and kept within cost |

The project is a personal one. Most of these roles hire: their work is judging other people's
work, quickly and without sentiment, which makes them the strictest readers a published app
and its repository get. What they hold against a project is a fair measure of what it should
be before it goes out.

Each review gave two scores out of ten: one for the person who built it (in the prompt's words,
whether the reviewer would move its author forward for a junior role), one for the project. It
also gave its objections, each of one kind:

- **fix-in-repo**: something in the repository can be changed to answer it;
- **owner-evidence**: only the owner can answer it, with her own words or work;
- **taste**: a preference, not a defect;
- **owner-decision**: one of the owner's decisions, recorded and not reopened.

The prompt asked for the reviews in Romanian, the language the owner works in. They stay
outside the repository; what follows is their substance, in English.

## The rounds

| Round | What | Started (UTC) | Prompt |
|---|---|---|---|
| 1 | The panel | 7 Nov, 13:31 | [round1-panel.js](round1-panel.js) |
| 2 | The panel again, after round 1's fixes | 7 Nov, 15:11 | [round2-panel.js](round2-panel.js) |
| 3 | One agent per app attacks round 2's fixes by name | 7 Nov, 16:12 | [desktop](round3-reattack-desktop.txt), [phone](round3-reattack-android.txt) |
| 4 | The panel a last time, after round 3's fixes and the owner's decisions | 8 Nov, 07:23 | [round4-panel.js](round4-panel.js) |

Inside the scripts, rounds 1, 2 and 4 are named panel rounds 1 to 3: the panel met three times.

## The scores

The person who built it / the project, out of ten, in rounds 1, 2 and 4.

| Role | Desktop 1 | Desktop 2 | Desktop 4 | Phone 1 | Phone 2 | Phone 4 |
|---|---|---|---|---|---|---|
| Recruiter | 7 / 7 | 7 / 7 | 7 / 7 | 6 / 7 | 7 / 7 | 7 / 7 |
| HR business partner | 8 / 7 | 8 / 8 | 8 / 7 | 8 / 7 | 8 / 7 | 8 / 8 |
| Tech lead | 7 / 7 | 6 / 7 | 7 / 8 | 7 / 8 | 7 / 7 | 7 / 8 |
| Experienced developer | 6 / 7 | 5 / 7 | 6 / 7 | 6 / 7 | 6 / 7 | 6 / 7 |
| Senior product designer | 5 / 6 | 5 / 6 | 6 / 7 | 6 / 7 | 5 / 6 | 6 / 7 |
| QA lead | 7 / 8 | 7 / 8 | 7 / 8 | 7 / 8 | 7 / 8 | 8 / 8 |
| Head of engineering | 6 / 6 | 6 / 7 | 6 / 7 | 6 / 7 | 6 / 6 | 6 / 7 |
| AI engineer | 7 / 7 | 7 / 8 | 7 / 8 | 7 / 7 | 7 / 7 | 7 / 8 |
| **Average** | **6.62 / 6.88** | **6.38 / 7.25** | **6.75 / 7.38** | **6.62 / 7.25** | **6.62 / 6.88** | **6.88 / 7.50** |

The wave was to stop once the scores no longer rose. The owner chose round 4 as the last before
it ran, and the scores still rose in it.

## The objections, by kind

| Round | All | fix-in-repo | owner-evidence | owner-decision | taste |
|---|---|---|---|---|---|
| 1 | 96 | 61 | 19 | 7 | 9 |
| 2 | 95 | 49 | 21 | 18 | 7 |
| 4 | 93 | 40 | 24 | 20 | 9 |

The owner's decisions grow from round to round because each round raised questions she then
decided, and the next round's prompt listed them.

## What came of each round

Every fix-in-repo objection was checked in the code or the documents before anything changed,
and not all of them held.

### Round 1

True, and fixed:

- The desktop README said every theme met WCAG AA, while the accent's fill falls under 3:1 on
  two of the eight.
- Comments in both apps named the audit's rounds ("round 7", "the lows wave") where they should
  have said why. They were rewritten, and both apps' comment gates now refuse such names.
- The table of agent reviews had no row for the final audit; the audit was given a row and a
  section of its own, with its rules.
- The phone's README said every test had been watched failing, with no mutant runner in its
  repository; the runner and its catalogue were committed.
- Numbers on the phone had gone stale: tests, the walk's checks, the test plan's cases.
- A mistake in the prompt itself: round 1 told the reviewers the desktop's repository was
  public, when it stays private until after the audit. Round 2's prompt said so.

True, and fixed only after round 4: the desktop's mutant job had 30 minutes for a catalogue of
over a thousand mutants (D#43 below).

The owner decided, when asked: the editor's six action buttons and the share names stay as
they are; the font and size lists say "Font" and "Size" when nothing is chosen; a card's
preview joins its lines with " · ". Commit subjects name the part of the app from then on.

The larger restructurings wait for after the stores: splitting the phone's editor and notebook
files, a core module of its own, the desktop's settings in one place, the banners' queue as an
object, UI tests of the phone in CI.

### Round 2

It found round 1's fixes incomplete: round names left in words ("round ten"), a second place
that joined a note's lines and was never looked for, a count off by one. All three were fixed.

Fixed besides: the desktop README says screen readers cannot read the app (Tk exposes nothing
to them); the English gate proves its own examples before it reads the repository; claims in
the documents were made exact; the phone finds its Android tools without a path written for one
machine. One objection was refuted: the Save button on the light themes measures 6.21:1, where
the reviewer had read its letters as white.

The owner then said yes to every recommendation on round 2's list: list markers dropped from
the cards' previews, the phone's + moved into the list's header on wide screens, a gate that
keeps the test plan's workbook coherent, the audit's branches written into CLAUDE.md as an
exception, numbers per wave, a test for the phone's fallback branch, contrast measured on all
eight phone themes, short summaries at the top of the READMEs, no second mutation tool. Later
she decided to publish the prompts: this folder.

### Round 3

One agent per app re-attacked round 2's fixes by name. On the desktop, one finding was of
medium severity, and it was the agent's own mistake: a note it had rewritten about a mutant said
something untrue. The reviewer's correction was checked against git and taken. The rest were
low, and all but one were fixed: round names in places the comments gate did not read (the
Dockerfile, a PowerShell script, the CI workflows, which it reads now), dead exceptions in the
English gate, and every cut ending in "…" moved into one helper. The one left is in the
website's demo, for its next upload.

On the phone, all low. Fixed: words left in comments and test names, no time limit on reading a
stopped build, a mutant's build left from the last mutant. Two more, about the order of the
phone's messages, were written down in the code to be fixed later. After the fixes no finding of
medium severity or worse was open on either app.

### Round 4

The 40 fix-in-repo objections, checked one by one.

| Objection | What it was | What was done |
|---|---|---|
| D#36, D#48 | A card's "…" was meant to end at the last whole word, and cut through one ("the team's t…"); the guide's picture showed it | The cut goes back to the last whole word, through a word only when that would lose over half the room; checked in two suites, four mutants killed, picture retaken |
| D#38, A#32 | "Approved every change", beside a pull request of about 360 commits | "Approved every push and every merge; the audit reaches main as one pull request per app" |
| D#43 | The mutant workflow ran 1,156 mutants in 30 minutes, which cannot finish | It runs a piece of the catalogue at a time; an id that names no mutant is refused, where it ran nothing and passed |
| D#32 | Coverage was quoted from 3 October | Measured again: 90.8% |
| D#45 | "A tool can reproduce every figure", while the audit's cannot be | Said: the audit's records stay outside the repository |
| D#40, D#46, A#41 | About 103 million tokens against 8 to 13 million estimated, unexplained | Where they went, and the cost of a finding per wave |
| A#34 | "Walked on 7, 10 and 14-inch tablets": an emulator set to their sizes | Said as it is; no real tablet yet |
| A#33 | "Minimum Android 8.0", without what it ran on | Built for 8.0; walked on Android 17 on the emulator, used on 16 on one phone |
| A#37, A#43 | Seven parts of the phone's walk named after rounds | Named after what they walk; both comment gates refuse such names in functions too |
| A#43 | A gate missing from the phone's pre-push list, a note to the agent in its QA README | Added; the note moved into a comment |
| A#42 | Two mutants left alive without a reason | Reasons written; both catalogues' gates now require one for any mutant left alive |

Not fixed, each with its reason:

- **D#15**: the settings picture shows Statistics on purpose, and the script that takes it says
  why.
- **D#21**: the English gate already reads every tracked file; a stricter list would fail on
  them at once.
- **D#48**: two mutants said to "detect text": the words are the behaviour that was fixed.
- **D#48**: a register tool marking an item done on a name found; not checked, as the register
  it reads is archived.
- **D#37, D#14**: one commit holding two changes, old subjects hard to read: history is not
  rewritten; the subject rule applies from 7 November.
- **D#18, A#15**: comments that tell stories: the pass over them was made on both apps, and what
  remains is within the gates' limits.
- **After the stores, by the owner's decision on restructuring:** D#17, D#22, A#16, A#18,
  A#35.
- **A#33, its second half** (running on Android 8 to 12): the owner decided on 22 October that
  the emulator stays as it is; the README now says what it ran on.

Left to the owner, as only she can answer them: a link to try the app near the top of each
README, her own writing higher up, a calibration of the sceptic with planted false findings,
and the owner-evidence objections, which ask for her own account of what she checked, refused
and found.
