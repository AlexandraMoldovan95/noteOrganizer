# The final audit's prompts

Note Organizer is a personal project: a notes app for Windows and its Android companion, made
to be used. Before the two went to the stores, AI agents checked them in waves of rounds, from
27 October to 14 November 2026. This folder holds what those agents were told: every script
that started them, as it ran, and the prompts of the agents started by hand.

How a round worked, what each wave was for, when it closed and what it found are told in
[How Note Organizer is built with an AI agent](../AI_WORKFLOW.md#the-final-audit). This page is
the index of the prompts. [The review panel](wave4/README.md) has a page of its own, with what
came of each of its rounds.

**Contents:** [Reading a script](#reading-a-script) ·
[What was changed for publication](#what-was-changed-for-publication) ·
[What is not here](#what-is-not-here) ·
[The scripts, wave by wave](#the-scripts-wave-by-wave)

## Reading a script

Each `.js` file is a workflow script for Claude Code, the AI coding agent the apps are built
with. `agent(...)` starts one agent with the prompt written above it, and `parallel(...)`
starts several at once.

- **Finders** each get a role and a part of the app, read the code, and try what they suspect
  in a throwaway copy. Each returns its findings in a fixed shape: what, where, how severe, how
  to reproduce it, and whether a probe showed it.
- **A sceptic** then re-grades every finding of medium severity or worse: confirmed,
  plausible, refuted, already decided or told twice, at the severity it would give.
- **Most rounds after the first** name the last round's fixes by commit and send an agent after
  them by name. That is why the scripts grow from round to round.
- **The limits come first** in every prompt: read-only on the repositories, the apps run only
  in throwaway copies, the owner's notebooks never opened.

## What was changed for publication

The scripts are copied from the runs' own records. Three things differ from what ran:

- **Paths on the owner's machine.** The session's scratch folder reads `<scratchpad>`, the
  user folder's name `<name>`, and the folder of the owner's own notebook
  `<the owner's notebook>`.
- **One sentence about the owner's own plans** was cut from the three panel scripts; a note in
  square brackets stands where it was.
- **Two comment lines** at the top of each script name its run and when it started.

Wave 3 ran each round's script twice, once per app; it is here once. Wave 4's third round was
two agents started by hand rather than by a script, and so were all of waves 5 and 6: their
prompts are the `.txt` files, taken from the agents' own transcripts (wave 6's from the files the
agents were pointed at), with the paths replaced the same way.

## What is not here

- **Wave 0** (licences, history, packaging) was mechanical, done in the main session without
  agents.
- **The agents' answers.** Their findings and the sceptic's verdicts stay in the runs' records,
  outside the repository. What they found is told in the
  [issues log](../ISSUES_LOG.md#a-file-with-two-names) and counted in
  [the final audit](../AI_WORKFLOW.md#the-final-audit).
- **The files the scripts point at in `<scratchpad>`**: the last round's findings, the
  mechanical scans wave 3 started from, the agents' probes. They stayed on the machine.
- **The prompts of the 30 agents** that wrote or measured fixes in wave 1's first ten rounds.
  From round 11 on, the fixes were written in the main session.
- **The main session's own instructions** are [CLAUDE.md](../../CLAUDE.md), at the root of each
  repository. The reviews before the final audit, from September and October, are listed in
  [Agent reviews, in numbers](../AI_WORKFLOW.md#agent-reviews-in-numbers).

## The scripts, wave by wave

The 125 runs of waves 1 to 4 recorded about 103.3 million tokens between them, and wave 5's 21
agents 3.85 million: the figure of about 107 million
[the final audit](../AI_WORKFLOW.md#the-final-audit) gives. "Agents" counts every agent a run
started, the sceptic included. The two agents of wave 4's third round were started by hand,
and their tokens were not recorded.

Wave 1's round 11 was stopped part-way, when half a week's usage allowance had gone, and run
again with two finders per app; until the panel, no round after it had more. A few runs came
after an app's wave had closed: wave 1's desktop rounds 22 and 24 checked a change made later,
and wave 2's lows rounds 11 and 12 re-attacked the phone's last fixes.

### Wave 1: lost notes, hostile and huge input, security, accessibility

| Script | App | Started (UTC) | Agents | Tokens (millions) |
|---|---|---|---|---|
| [round01.js](wave1/round01.js) | Both | 2026-10-27 18:27 | 14 | 3.18 |
| [round02-android.js](wave1/round02-android.js) | Phone | 2026-10-28 03:45 | 6 | 1.40 |
| [round02-desktop.js](wave1/round02-desktop.js) | Desktop | 2026-10-28 00:52 | 7 | 1.69 |
| [round03-android.js](wave1/round03-android.js) | Phone | 2026-10-28 08:17 | 5 | 1.25 |
| [round03-desktop.js](wave1/round03-desktop.js) | Desktop | 2026-10-28 04:16 | 7 | 1.77 |
| [round04-android.js](wave1/round04-android.js) | Phone | 2026-10-28 12:00 | 5 | 1.39 |
| [round04-desktop.js](wave1/round04-desktop.js) | Desktop | 2026-10-28 08:27 | 7 | 1.83 |
| [round05-android.js](wave1/round05-android.js) | Phone | 2026-10-28 22:11 | 5 | 1.32 |
| [round05-desktop.js](wave1/round05-desktop.js) | Desktop | 2026-10-28 12:21 | 7 | 1.91 |
| [round06-android.js](wave1/round06-android.js) | Phone | 2026-10-29 05:48 | 5 | 1.22 |
| [round06-desktop.js](wave1/round06-desktop.js) | Desktop | 2026-10-29 05:50 | 6 | 1.65 |
| [round07-android.js](wave1/round07-android.js) | Phone | 2026-10-29 15:49 | 6 | 1.41 |
| [round07-desktop.js](wave1/round07-desktop.js) | Desktop | 2026-10-29 15:53 | 6 | 1.64 |
| [round08-android.js](wave1/round08-android.js) | Phone | 2026-10-30 01:16 | 6 | 1.65 |
| [round08-desktop.js](wave1/round08-desktop.js) | Desktop | 2026-10-30 01:26 | 6 | 1.80 |
| [round09-android.js](wave1/round09-android.js) | Phone | 2026-10-30 08:49 | 6 | 1.64 |
| [round09-desktop.js](wave1/round09-desktop.js) | Desktop | 2026-10-30 08:47 | 6 | 1.68 |
| [round10-android.js](wave1/round10-android.js) | Phone | 2026-10-30 19:06 | 6 | 1.84 |
| [round10-desktop.js](wave1/round10-desktop.js) | Desktop | 2026-10-30 16:30 | 6 | 1.98 |
| [round11-android.js](wave1/round11-android.js), stopped | Phone | 2026-10-31 01:09 | 5 | 0.62 |
| [round11-desktop.js](wave1/round11-desktop.js), stopped | Desktop | 2026-10-31 01:09 | 5 | 0.69 |
| [round11-small-android.js](wave1/round11-small-android.js) | Phone | 2026-10-31 01:25 | 3 | 0.44 |
| [round11-small-desktop.js](wave1/round11-small-desktop.js) | Desktop | 2026-10-31 01:28 | 3 | 0.49 |
| [round12-small-android.js](wave1/round12-small-android.js) | Phone | 2026-10-31 02:48 | 3 | 0.62 |
| [round12-small-desktop.js](wave1/round12-small-desktop.js) | Desktop | 2026-10-31 02:57 | 3 | 0.68 |
| [round13-small-android.js](wave1/round13-small-android.js) | Phone | 2026-10-31 14:28 | 3 | 0.67 |
| [round13-small-desktop.js](wave1/round13-small-desktop.js) | Desktop | 2026-10-31 14:15 | 3 | 0.55 |
| [round14-small-android.js](wave1/round14-small-android.js) | Phone | 2026-10-31 15:19 | 3 | 0.58 |
| [round14-small-desktop.js](wave1/round14-small-desktop.js) | Desktop | 2026-10-31 15:22 | 3 | 0.68 |
| [round15-small-android.js](wave1/round15-small-android.js) | Phone | 2026-10-31 16:25 | 3 | 0.69 |
| [round15-small-desktop.js](wave1/round15-small-desktop.js) | Desktop | 2026-10-31 16:21 | 3 | 0.66 |
| [round16-small-android.js](wave1/round16-small-android.js) | Phone | 2026-11-01 01:17 | 3 | 0.64 |
| [round16-small-desktop.js](wave1/round16-small-desktop.js) | Desktop | 2026-11-01 01:20 | 3 | 0.68 |
| [round17-small-android.js](wave1/round17-small-android.js) | Phone | 2026-11-01 02:52 | 3 | 0.65 |
| [round17-small-desktop.js](wave1/round17-small-desktop.js) | Desktop | 2026-11-01 02:59 | 3 | 0.73 |
| [round18-small-android.js](wave1/round18-small-android.js) | Phone | 2026-11-01 04:19 | 3 | 0.61 |
| [round18-small-desktop.js](wave1/round18-small-desktop.js) | Desktop | 2026-11-01 05:09 | 3 | 0.82 |
| [round19-small-android.js](wave1/round19-small-android.js) | Phone | 2026-11-01 05:33 | 2 | 0.49 |
| [round19-small-desktop.js](wave1/round19-small-desktop.js) | Desktop | 2026-11-01 06:10 | 2 | 0.61 |
| [round20-small-android.js](wave1/round20-small-android.js) | Phone | 2026-11-01 06:05 | 3 | 0.57 |
| [round20-small-desktop.js](wave1/round20-small-desktop.js) | Desktop | 2026-11-01 06:37 | 2 | 0.53 |
| [round21-small-android.js](wave1/round21-small-android.js) | Phone | 2026-11-01 06:40 | 2 | 0.56 |
| [round22-small-android.js](wave1/round22-small-android.js) | Phone | 2026-11-01 12:41 | 3 | 0.64 |
| [round22-small-desktop.js](wave1/round22-small-desktop.js) | Desktop | 2026-11-01 12:36 | 1 | 0.24 |
| [round23-small-android.js](wave1/round23-small-android.js) | Phone | 2026-11-01 13:08 | 3 | 0.74 |
| [round24-small-android.js](wave1/round24-small-android.js) | Phone | 2026-11-01 13:52 | 1 | 0.30 |
| [round24-small-desktop.js](wave1/round24-small-desktop.js) | Desktop | 2026-11-01 13:49 | 1 | 0.26 |
| [round25-small-android.js](wave1/round25-small-android.js) | Phone | 2026-11-01 14:09 | 2 | 0.46 |

### Wave 1's lows

The low findings of wave 1, fixed in a wave of their own; each round re-attacked the last
round's fixes. Round 5 ran on the phone only.

| Script | App | Started (UTC) | Agents | Tokens (millions) |
|---|---|---|---|---|
| [round01-android.js](wave1-lows/round01-android.js) | Phone | 2026-11-01 16:30 | 2 | 0.51 |
| [round01-desktop.js](wave1-lows/round01-desktop.js) | Desktop | 2026-11-01 16:49 | 3 | 0.66 |
| [round02-android.js](wave1-lows/round02-android.js) | Phone | 2026-11-01 17:50 | 2 | 0.36 |
| [round02-desktop.js](wave1-lows/round02-desktop.js) | Desktop | 2026-11-01 17:48 | 2 | 0.33 |
| [round03-android.js](wave1-lows/round03-android.js) | Phone | 2026-11-01 19:20 | 2 | 0.35 |
| [round03-desktop.js](wave1-lows/round03-desktop.js) | Desktop | 2026-11-01 19:21 | 1 | 0.29 |
| [round04-android.js](wave1-lows/round04-android.js) | Phone | 2026-11-01 19:48 | 2 | 0.38 |
| [round04-desktop.js](wave1-lows/round04-desktop.js) | Desktop | 2026-11-01 19:49 | 1 | 0.29 |
| [round05-android.js](wave1-lows/round05-android.js) | Phone | 2026-11-01 20:29 | 2 | 0.39 |
| [round06-android.js](wave1-lows/round06-android.js) | Phone | 2026-11-01 21:17 | 2 | 0.41 |
| [round06-desktop.js](wave1-lows/round06-desktop.js) | Desktop | 2026-11-01 21:10 | 2 | 0.34 |
| [round07-android.js](wave1-lows/round07-android.js) | Phone | 2026-11-01 22:18 | 2 | 0.45 |
| [round07-desktop.js](wave1-lows/round07-desktop.js) | Desktop | 2026-11-01 22:12 | 2 | 0.35 |
| [round08-android.js](wave1-lows/round08-android.js) | Phone | 2026-11-01 23:03 | 2 | 0.42 |
| [round08-desktop.js](wave1-lows/round08-desktop.js) | Desktop | 2026-11-01 23:01 | 2 | 0.42 |
| [round09-android.js](wave1-lows/round09-android.js) | Phone | 2026-11-01 23:56 | 2 | 0.48 |
| [round09-desktop.js](wave1-lows/round09-desktop.js) | Desktop | 2026-11-01 23:58 | 2 | 0.53 |
| [round10-android.js](wave1-lows/round10-android.js) | Phone | 2026-11-02 00:43 | 1 | 0.28 |
| [round10-desktop.js](wave1-lows/round10-desktop.js) | Desktop | 2026-11-02 00:44 | 2 | 0.42 |
| [round11-android.js](wave1-lows/round11-android.js) | Phone | 2026-11-02 01:17 | 2 | 0.35 |
| [round11-desktop.js](wave1-lows/round11-desktop.js) | Desktop | 2026-11-02 01:12 | 1 | 0.24 |

### Wave 3: what read as generated rather than written

Wave 3 ran before wave 2. Each round had, per app, up to two finders, one on the code and one
on the documents, both starting from a mechanical scan, then a sceptic.

| Script | App | Started (UTC) | Agents | Tokens (millions) |
|---|---|---|---|---|
| [round01.js](wave3/round01.js) | Once per app | 2026-11-02 13:03 | 3 + 3 | 1.02 |
| [round02.js](wave3/round02.js) | Once per app | 2026-11-02 13:53 | 3 + 3 | 1.16 |
| [round03.js](wave3/round03.js) | Once per app | 2026-11-02 14:39 | 3 + 3 | 1.17 |
| [round04.js](wave3/round04.js) | Once per app | 2026-11-02 15:35 | 3 + 3 | 1.15 |
| [round05.js](wave3/round05.js) | Once per app | 2026-11-02 16:19 | 3 + 3 | 1.12 |
| [round06.js](wave3/round06.js) | Once per app | 2026-11-02 17:23 | 3 + 3 | 1.09 |
| [round07.js](wave3/round07.js) | Once per app | 2026-11-02 18:24 | 3 + 3 | 1.28 |
| [round08.js](wave3/round08.js) | Once per app | 2026-11-02 19:35 | 2 + 2 | 0.68 |

### Wave 2: an ordinary person's week, and a careless hand

One script per round for both apps. From round 15 the phone only: the desktop's wave had
closed at round 14.

| Script | App | Started (UTC) | Agents | Tokens (millions) |
|---|---|---|---|---|
| [round01.js](wave2/round01.js) | Both | 2026-11-03 01:38 | 6 | 1.48 |
| [round02.js](wave2/round02.js) | Both | 2026-11-03 04:27 | 6 | 1.31 |
| [round03.js](wave2/round03.js) | Both | 2026-11-03 05:07 | 6 | 1.21 |
| [round04.js](wave2/round04.js) | Both | 2026-11-03 13:07 | 6 | 1.22 |
| [round05.js](wave2/round05.js) | Both | 2026-11-03 14:02 | 6 | 1.17 |
| [round06.js](wave2/round06.js) | Both | 2026-11-03 15:04 | 6 | 1.09 |
| [round07.js](wave2/round07.js) | Both | 2026-11-03 17:09 | 6 | 1.28 |
| [round08.js](wave2/round08.js) | Both | 2026-11-03 18:50 | 6 | 1.17 |
| [round09.js](wave2/round09.js) | Both | 2026-11-03 20:08 | 6 | 1.21 |
| [round10.js](wave2/round10.js) | Both | 2026-11-03 21:49 | 6 | 1.06 |
| [round11.js](wave2/round11.js) | Both | 2026-11-03 23:36 | 6 | 1.18 |
| [round12.js](wave2/round12.js) | Both | 2026-11-04 00:43 | 6 | 1.29 |
| [round13.js](wave2/round13.js) | Both | 2026-11-04 01:39 | 5 | 1.03 |
| [round14.js](wave2/round14.js) | Both | 2026-11-04 02:12 | 5 | 1.04 |
| [round15.js](wave2/round15.js) | Both | 2026-11-04 03:14 | 3 | 0.52 |
| [round16.js](wave2/round16.js) | Both | 2026-11-04 03:55 | 3 | 0.58 |
| [round17.js](wave2/round17.js) | Both | 2026-11-04 05:01 | 3 | 0.68 |
| [round18.js](wave2/round18.js) | Both | 2026-11-04 06:15 | 3 | 0.54 |
| [round19.js](wave2/round19.js) | Both | 2026-11-04 07:12 | 3 | 0.49 |
| [round20.js](wave2/round20.js) | Both | 2026-11-05 20:34 | 3 | 0.56 |
| [round21.js](wave2/round21.js) | Both | 2026-11-05 21:36 | 3 | 0.54 |
| [round22.js](wave2/round22.js) | Both | 2026-11-05 22:10 | 3 | 0.65 |
| [round23.js](wave2/round23.js) | Both | 2026-11-05 23:24 | 3 | 0.72 |
| [round24.js](wave2/round24.js) | Both | 2026-11-06 00:13 | 2 | 0.46 |
| [round25.js](wave2/round25.js) | Both | 2026-11-06 00:33 | 2 | 0.45 |

### Wave 2's lows

The low findings of wave 2, fixed in a wave of their own and re-attacked the same way.

| Script | App | Started (UTC) | Agents | Tokens (millions) |
|---|---|---|---|---|
| [round01.js](wave2-lows/round01.js) | Both | 2026-11-06 08:51 | 6 | 1.26 |
| [round02.js](wave2-lows/round02.js) | Both | 2026-11-06 10:24 | 6 | 1.20 |
| [round03.js](wave2-lows/round03.js) | Both | 2026-11-06 11:57 | 5 | 1.04 |
| [round04.js](wave2-lows/round04.js) | Both | 2026-11-06 13:08 | 4 | 1.03 |
| [round05.js](wave2-lows/round05.js) | Both | 2026-11-06 14:43 | 5 | 1.25 |
| [round06.js](wave2-lows/round06.js) | Both | 2026-11-06 16:19 | 5 | 1.24 |
| [round07.js](wave2-lows/round07.js) | Both | 2026-11-06 17:50 | 5 | 1.23 |
| [round08.js](wave2-lows/round08.js) | Both | 2026-11-06 19:51 | 6 | 1.20 |
| [round09.js](wave2-lows/round09.js) | Both | 2026-11-06 21:13 | 3 | 0.72 |
| [round10.js](wave2-lows/round10.js) | Both | 2026-11-06 22:06 | 3 | 0.67 |
| [round11.js](wave2-lows/round11.js) | Both | 2026-11-06 22:54 | 1 | 0.21 |
| [round12.js](wave2-lows/round12.js) | Both | 2026-11-06 23:32 | 1 | 0.16 |

### Wave 4: the review panel

Eight roles, two to an agent: [the panel's page](wave4/README.md) says who they were and what
came of each round. Inside the scripts, rounds 1, 2 and 4 are named panel rounds 1 to 3; the
panel met three times.

| Script | App | Started (UTC) | Agents | Tokens (millions) |
|---|---|---|---|---|
| [round1-panel.js](wave4/round1-panel.js) | Both | 2026-11-07 13:31 | 8 | 1.04 |
| [round2-panel.js](wave4/round2-panel.js) | Both | 2026-11-07 15:11 | 8 | 1.05 |
| [round3-reattack-android.txt](wave4/round3-reattack-android.txt) | Phone | 2026-11-07 16:12 | 1 | not recorded |
| [round3-reattack-desktop.txt](wave4/round3-reattack-desktop.txt) | Desktop | 2026-11-07 16:12 | 1 | not recorded |
| [round4-panel.js](wave4/round4-panel.js) | Both | 2026-11-08 07:23 | 8 | 1.03 |

### Wave 5: the release

Ten read-only readers on 11 November, each given a part of one app, then a mini-audit that
attacked each fix by name: two agents for the desktop's first round, one for every round after.
The phone's rounds 3 to 8 attacked the runner for the emulator walk, written in the same wave.
No sceptic ran in this wave: the agent leading the audit checked each finding in the code
before it counted.

| Prompt | App | Started (UTC) | Agents | Tokens (millions) |
|---|---|---|---|---|
| [reading-desktop-hub-first-half.txt](wave5/reading-desktop-hub-first-half.txt) | Desktop | 2026-11-11 19:11 | 1 | 0.25 |
| [reading-desktop-hub-second-half.txt](wave5/reading-desktop-hub-second-half.txt) | Desktop | 2026-11-11 19:11 | 1 | 0.26 |
| [reading-desktop-ui-mixins.txt](wave5/reading-desktop-ui-mixins.txt) | Desktop | 2026-11-11 19:11 | 1 | 0.30 |
| [reading-desktop-core.txt](wave5/reading-desktop-core.txt) | Desktop | 2026-11-11 19:11 | 1 | 0.23 |
| [reading-desktop-tools-and-site.txt](wave5/reading-desktop-tools-and-site.txt) | Desktop | 2026-11-11 19:11 | 1 | 0.16 |
| [reading-desktop-documents.txt](wave5/reading-desktop-documents.txt) | Desktop | 2026-11-11 19:11 | 1 | 0.27 |
| [reading-phone-screens-and-manifest.txt](wave5/reading-phone-screens-and-manifest.txt) | Phone | 2026-11-11 19:11 | 1 | 0.37 |
| [reading-phone-rules-part1.txt](wave5/reading-phone-rules-part1.txt) | Phone | 2026-11-11 19:11 | 1 | 0.28 |
| [reading-phone-rules-part2.txt](wave5/reading-phone-rules-part2.txt) | Phone | 2026-11-11 19:11 | 1 | 0.27 |
| [reading-phone-documents-and-tools.txt](wave5/reading-phone-documents-and-tools.txt) | Phone | 2026-11-11 19:11 | 1 | 0.24 |
| [miniaudit-desktop-round1-data.txt](wave5/miniaudit-desktop-round1-data.txt) | Desktop | 2026-11-11 21:45 | 1 | 0.09 |
| [miniaudit-desktop-round1-ui.txt](wave5/miniaudit-desktop-round1-ui.txt) | Desktop | 2026-11-11 21:45 | 1 | 0.09 |
| [miniaudit-desktop-round2.txt](wave5/miniaudit-desktop-round2.txt) | Desktop | 2026-11-11 22:07 | 1 | 0.12 |
| [miniaudit-phone-round1.txt](wave5/miniaudit-phone-round1.txt) | Phone | 2026-11-11 22:07 | 1 | 0.12 |
| [miniaudit-phone-round2.txt](wave5/miniaudit-phone-round2.txt) | Phone | 2026-11-11 22:12 | 1 | 0.12 |
| [miniaudit-phone-round3.txt](wave5/miniaudit-phone-round3.txt) | Phone | 2026-11-11 22:20 | 1 | 0.09 |
| [miniaudit-phone-round4.txt](wave5/miniaudit-phone-round4.txt) | Phone | 2026-11-11 22:25 | 1 | 0.10 |
| [miniaudit-phone-round5.txt](wave5/miniaudit-phone-round5.txt) | Phone | 2026-11-11 22:33 | 1 | 0.11 |
| [miniaudit-phone-round6.txt](wave5/miniaudit-phone-round6.txt) | Phone | 2026-11-11 22:40 | 1 | 0.12 |
| [miniaudit-phone-round7.txt](wave5/miniaudit-phone-round7.txt) | Phone | 2026-11-11 22:47 | 1 | 0.12 |
| [miniaudit-phone-round8.txt](wave5/miniaudit-phone-round8.txt) | Phone | 2026-11-12 00:02 | 1 | 0.14 |

### Wave 6: the lows, before the stores

The full reading's findings of low severity, fixed from 12 November, then attacked by two
agents for each app in each round (the desktop's later rounds by one, below): one going after
each fix by name, one taking an ordinary person's side and reading the wave's documents against
the code. No sceptic ran: the agent
leading the audit checked each finding of medium severity in the code before it counted. The
totals above are waves 1 to 5's.

| Prompt | App | Started (UTC) | Agents | Tokens (millions) |
|---|---|---|---|---|
| [r1-desktop-fixes.txt](wave6/r1-desktop-fixes.txt) | Desktop | 2026-11-13 03:02 | 1 | 0.25 |
| [r1-desktop-person.txt](wave6/r1-desktop-person.txt) | Desktop | 2026-11-13 03:02 | 1 | 0.26 |
| [r1-phone-fixes.txt](wave6/r1-phone-fixes.txt) | Phone | 2026-11-13 03:02 | 1 | 0.25 |
| [r1-phone-person.txt](wave6/r1-phone-person.txt) | Phone | 2026-11-13 03:02 | 1 | 0.28 |
| [r2-desktop-fixes.txt](wave6/r2-desktop-fixes.txt) | Desktop | 2026-11-13 05:02 | 1 | 0.28 |
| [r2-desktop-person.txt](wave6/r2-desktop-person.txt) | Desktop | 2026-11-13 05:02 | 1 | 0.30 |
| [r2-phone-fixes.txt](wave6/r2-phone-fixes.txt) | Phone | 2026-11-13 05:02 | 1 | 0.33 |
| [r2-phone-person.txt](wave6/r2-phone-person.txt) | Phone | 2026-11-13 05:02 | 1 | 0.35 |
| [r3-desktop.txt](wave6/r3-desktop.txt) | Desktop | 2026-11-13 06:53 | 2 | 0.52 |
| [r3-phone.txt](wave6/r3-phone.txt) | Phone | 2026-11-13 06:53 | 2 | 0.63 |
| [r4-desktop.txt](wave6/r4-desktop.txt) | Desktop | 2026-11-13 08:06 | 2 | 0.53 |
| [r4-phone.txt](wave6/r4-phone.txt) | Phone | 2026-11-13 08:33 | 2 | 0.52 |
| [r5-desktop.txt](wave6/r5-desktop.txt) | Desktop | 2026-11-13 09:07 | 2 | 0.56 |
| [r5-phone.txt](wave6/r5-phone.txt) | Phone | 2026-11-13 09:44 | 2 | 0.56 |
| [r6-desktop.txt](wave6/r6-desktop.txt) | Desktop | 2026-11-13 09:55 | 2 | 0.53 |
| [r6-phone.txt](wave6/r6-phone.txt) | Phone | 2026-11-13 11:01 | 2 | 0.60 |
| [r7-desktop.txt](wave6/r7-desktop.txt) | Desktop | 2026-11-13 10:44 | 2 | 0.57 |
| [r8-desktop.txt](wave6/r8-desktop.txt) | Desktop | 2026-11-13 11:25 | 2 | 0.51 |
| [r7-phone.txt](wave6/r7-phone.txt) | Phone | 2026-11-13 11:54 | 2 | 0.68 |
| [r9-desktop.txt](wave6/r9-desktop.txt) | Desktop | 2026-11-13 12:04 | 2 | 0.65 |
| [r8-phone.txt](wave6/r8-phone.txt) | Phone | 2026-11-13 13:12 | 2 | 0.62 |
| [r10-desktop.txt](wave6/r10-desktop.txt) | Desktop | 2026-11-13 13:23 | 2 | 0.56 |
| [r11-desktop.txt](wave6/r11-desktop.txt) | Desktop | 2026-11-13 14:53 | 2 | 0.66 |
| [r9-phone.txt](wave6/r9-phone.txt) | Phone | 2026-11-13 15:46 | 2 | 0.67 |
| [r12-desktop.txt](wave6/r12-desktop.txt) | Desktop | 2026-11-13 16:02 | 2 | 0.53 |
| [r13-desktop.txt](wave6/r13-desktop.txt) | Desktop | 2026-11-13 16:42 | 2 | 0.45 |
| [r10-phone.txt](wave6/r10-phone.txt) | Phone | 2026-11-13 16:42 | 2 | 0.54 |
| [r14-desktop.txt](wave6/r14-desktop.txt) | Desktop | 2026-11-13 17:28 | 2 | 0.57 |
| [r15-desktop.txt](wave6/r15-desktop.txt) | Desktop | 2026-11-13 19:17 | 2 | 0.52 |
| [r11-phone.txt](wave6/r11-phone.txt) | Phone | 2026-11-13 19:17 | 2 | 0.51 |
| [r16-desktop.txt](wave6/r16-desktop.txt) | Desktop | 2026-11-13 20:29 | 2 | 0.52 |
| [r12-phone.txt](wave6/r12-phone.txt) | Phone | 2026-11-13 20:29 | 2 | 0.62 |
| [r17-desktop.txt](wave6/r17-desktop.txt) | Desktop | 2026-11-13 21:22 | 2 | 0.59 |
| [r13-phone.txt](wave6/r13-phone.txt) | Phone | 2026-11-13 21:29 | 2 | 0.46 |
| [r18-desktop.txt](wave6/r18-desktop.txt) | Desktop | 2026-11-13 22:30 | 2 | 0.45 |
| [r14-phone.txt](wave6/r14-phone.txt) | Phone | 2026-11-13 22:30 | 2 | 0.43 |
| [r15-phone.txt](wave6/r15-phone.txt) | Phone | 2026-11-13 23:08 | 2 | 0.55 |
| [r19-desktop.txt](wave6/r19-desktop.txt) | Desktop | 2026-11-13 23:32 | 2 | 0.48 |
| [r16-phone.txt](wave6/r16-phone.txt) | Phone | 2026-11-13 23:39 | 2 | 0.56 |
| [r17-phone.txt](wave6/r17-phone.txt) | Phone | 2026-11-14 00:09 | 2 | 0.46 |
| [r20-desktop.txt](wave6/r20-desktop.txt) | Desktop | 2026-11-14 00:51 | 1 | 0.22 |
| [r18-phone.txt](wave6/r18-phone.txt), [r18-phone-b.txt](wave6/r18-phone-b.txt) | Phone | 2026-11-14 00:51 | 2 | 0.46 |
| [r21-desktop.txt](wave6/r21-desktop.txt) | Desktop | 2026-11-14 02:01 | 2 | 0.53 |
| [r19-phone.txt](wave6/r19-phone.txt) | Phone | 2026-11-14 02:05 | 2 | 0.56 |
| [r22-desktop.txt](wave6/r22-desktop.txt) | Desktop | 2026-11-14 02:55 | 2 | 0.50 |
| [r20-phone.txt](wave6/r20-phone.txt) | Phone | 2026-11-14 02:55 | 2 | 0.48 |
| [r23-desktop.txt](wave6/r23-desktop.txt) | Desktop | 2026-11-14 03:56 | 2 | 0.48 |
| [r21-phone.txt](wave6/r21-phone.txt) | Phone | 2026-11-14 03:56 | 2 | 0.47 |
| [r24-desktop.txt](wave6/r24-desktop.txt) | Desktop | 2026-11-14 04:48 | 1 | 0.23 |
| [r22-phone.txt](wave6/r22-phone.txt) | Phone | 2026-11-14 04:48 | 2 | 0.50 |
| [r25-desktop.txt](wave6/r25-desktop.txt) | Desktop | 2026-11-14 05:40 | 1 | 0.20 |
| [r23-phone.txt](wave6/r23-phone.txt) | Phone | 2026-11-14 05:40 | 2 | 0.47 |
| [r26-desktop.txt](wave6/r26-desktop.txt) | Desktop | 2026-11-14 06:24 | 1 | 0.18 |
| [r24-phone.txt](wave6/r24-phone.txt) | Phone | 2026-11-14 06:24 | 2 | 0.52 |
| [r27-desktop.txt](wave6/r27-desktop.txt) | Desktop | 2026-11-14 07:03 | 1 | 0.22 |
| [r25-phone.txt](wave6/r25-phone.txt) | Phone | 2026-11-14 07:03 | 2 | 0.46 |
| [r28-desktop.txt](wave6/r28-desktop.txt) | Desktop | 2026-11-14 07:43 | 1 | 0.19 |
| [r26-phone.txt](wave6/r26-phone.txt) | Phone | 2026-11-14 07:43 | 2 | 0.48 |
| [r29-desktop.txt](wave6/r29-desktop.txt) | Desktop | 2026-11-14 08:18 | 1 | 0.19 |
| [r27-phone.txt](wave6/r27-phone.txt) | Phone | 2026-11-14 08:18 | 2 | 0.47 |
| [r30-desktop.txt](wave6/r30-desktop.txt) | Desktop | 2026-11-14 08:53 | 1 | 0.19 |
| [r28-phone.txt](wave6/r28-phone.txt) | Phone | 2026-11-14 08:53 | 2 | 0.49 |
| [r31-desktop.txt](wave6/r31-desktop.txt) | Desktop | 2026-11-14 09:52 | 1 | 0.24 |
| [r29-phone.txt](wave6/r29-phone.txt) | Phone | 2026-11-14 09:52 | 2 | 0.48 |
| [r32-desktop.txt](wave6/r32-desktop.txt) | Desktop | 2026-11-14 10:37 | 1 | 0.21 |
| [r30-phone.txt](wave6/r30-phone.txt) | Phone | 2026-11-14 10:37 | 2 | 0.47 |

From the third round, both agents of an app read one file; the line that started each named
where to begin, one at each fix by name, the other at the person's roads and the documents.
From the desktop's seventh round and the phone's sixth, the second agent's line gave it the
test plan instead, to read case by case against the code: the mediums of the rounds before were
sentences in it. Once the plan had been read whole (the desktop's twelfth round, the phone's
tenth), it was given the texts a person reads instead: the user guide, the privacy policy and
the READMEs, the welcome notes, the screen texts, and the steps of a release. The desktop's
twentieth round was one agent, attacking the fixes of a round that had found nothing of medium
severity, and so was every desktop round from the twenty-fourth, by the owner's rule of 1
November; the phone's eighteenth gave its second agent a file of its own, on the rules for a
file the phone cannot read.
