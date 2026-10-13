# In my words

*Alexandra Moldovan, who builds Note Organizer. Most of this project's documentation is written by
the AI agent I build it with. This page is mine.*

## Contents

- [Why a notes app](#why-a-notes-app)
- [What I brought from support](#what-i-brought-from-support)
- [How I work with the agent](#how-i-work-with-the-agent)
- [The rules I set](#the-rules-i-set)
- [Decisions I made](#decisions-i-made)
- [How I test](#how-i-test)
- [What I learned](#what-i-learned)
- [What I would do differently](#what-i-would-do-differently)
- [What comes next](#what-comes-next)

## Why a notes app

Everyone takes notes - students, office workers, doctors, lawyers. Reading and writing are among
the first things we learn at school, and we keep using them to learn for the rest of our lives.
We write things down so we don't forget them, so we can study, or so we can pass an idea on. I
wanted to make a simple app that does that well, for anyone.

I started it in July, around the time I began a course in AI-assisted programming, as a project
of my own: a way to put what I was learning into practice. The course taught Python, so the app
is in Python. Its history on GitHub starts in August, when I put it under version control.

It works offline on purpose. When I started, I was still finding my feet with AI, and I didn't
want to pay for API keys whose usage I couldn't control, or that others could take advantage of. I
had also noticed how carefully companies guard their data, so it isn't exposed. An app that never
sends anything anywhere suits both.

## What I brought from support

Before this I worked in support for several years: customer support for games at Teleperformance,
on an EA project, and at Playtika, and three years in technical support at HP. I also did a
little crowdtesting on uTest.

At HP I was in first-line support, between the business and the development teams. We received
problems from the business, checked them, triaged them, and sent each one to the development team
that owned the tool. Part of the job was documenting the processes we followed, in OneNote, and
they had to be written so that someone else could follow them: there were many tools and many
teams, and everyone needed to know their part.

I saw how much time is lost when notes are short, when the real explanation is buried in years-old
email threads attached to a page, or when the person who wrote a process has moved to another role
or left. I spent a lot of time tracking people down to ask what a note meant. That is where my
habit comes from of writing things down completely and clearly, so that I can do my work well and
the people around me don't have to search for answers. It is also why the documentation of this
project matters so much to me.

I am a serious, organised person. I like to work on something until every detail is right, and I
can't leave a thing broken or half-done - it stays on my mind until I fix it.

## How I work with the agent

There are two of us working on the app, the agent and me, and alongside us, single-use AI agents
that each play a role for a while: they analyse the app, try to break it, review it from different
points of view, and the agent repairs what they find.

1. **We plan together.** We write our ideas in the roadmap. I bring mine and I encourage the agent
   to bring its own, then we agree on a plan.
2. **We build in parts.** One feature or a few small ones at a time, never several big changes at
   once. Doing too much at once is how things break, and then the bugs have to be found again
   through audits and test cases, which is more work for both of us. Being proactive pays off - I learned that at HP.
3. **The agent writes the code**, guided by my prompts, by audits, and by those review agents.
4. **I run the app and test it**, and say what still needs adjusting.
5. **The agent writes the pull request and, when there is a bug, the issue.** I read the texts,
   open them on GitHub, watch the CI checks, and merge when everything is green. We always work on
   branches, never on `main`, so the main code - and the app - stays safe.

We set up CI to make the work easier: one more safety net, one more filter the code goes through,
which also finds bugs that can slip past the editor. How much we cover in a day depends on how many
bugs we find and how much needs adjusting.

And because I try to think ahead, I agreed with the agent that every change goes through the list
of features it touches, to prevent bugs before they happen - and that when a bug does happen,
fixing it is not enough: we find its root cause, so the same conditions can't produce another one.

## The rules I set

Most of the rules in [CLAUDE.md](../CLAUDE.md) I thought of as I ran into things.

I started with safety: making sure I stay in control of what the agent does, so that what we
deliver is good. I wanted it to analyse and come up with ideas, but also to know when to stop,
instead of working more than needed or without a purpose. I worked in a balanced way to make a
balanced product.

As the app grew, I added more rules: to be organised; to work with review agents, imagining people
who examine the app and try to break it while it repairs it, so the app is solid from every side;
and to work in a loop until something is done properly. I made sure it knows who it works with and
what my background is, so it adapts to how I work. It always asks before pushing anything to
GitHub, so I can test the app first. And from the beginning I made sure I could learn from what
it does, to communicate with it better and to keep the experience myself.

After going through all this, I'm sure the next app I make will be even more organised than this
one.

## Decisions I made

These are a few of my decisions, picked as examples - not the only ones. I made the rest the same
way: the agent puts forward options, and I choose what the app does and how it behaves.

- **No language selector.** This is the first app I've built end to end this way. A language
  selector would have been hard to build, and I don't have the people to check six or seven
  languages for correct writing. I didn't want to risk badly written translations in the app.
- **Templates don't go through the Trash.** We were close to finishing, and I didn't want to risk
  breaking the app or adding bugs for a feature that would have meant a lot of extra work. There is
  a safety net: deleting a template shows a clear warning that it is gone for good. A template is
  also easy to write again, and you can keep copies. I weighed the need against the work it would
  take and decided it wasn't worth it; if it had been truly important, I would have made the time.
- **The checklist's arrows sit beside the checkboxes.** Priorities change, so a to-do list needs
  to be reordered. At first the ▲ ▼ arrows were beside each item's bin. I moved them next to the
  checkboxes, because a slip of the mouse could delete an item instead of moving it.
- **Settings was redesigned.** After a rework, Settings had the section names on one side and their
  buttons in the middle of the page, and I was zig-zagging with my eyes to take it all in. I
  described to the agent how it should look, made a separate mock-up in HTML of what it could be,
  and then we built it into the app.

The first two, and the other ideas we decided against, are listed in the roadmap, under
[Explicitly not planned](ROADMAP.md#explicitly-not-planned-right-now).

## How I test

I go through the whole interface: I imagine scenarios, the buttons a user would press and the
combinations worth trying, and I test them. I test on a dark and a light theme side by side as
much as I can, to see how each feature feels on both. When something doesn't look right, or
doesn't feel right from a human point of view, I ask the agent to look into it and we adjust it
together. While it works I often add small tasks or things to check, so the feature comes out
complete.

At the beginning, before our work was this organised, I found more bugs by hand than the automated
checks did. Now, whenever I find one, we add a check that would catch it, and mutants to prove the
check really works. I still find some by hand, fewer than before, and sometimes the automated
checks missed them and had to be reworked. So manual testing can never leave the picture. Even
when no technical bug is left, there are visual ones, and things no script can judge: whether a
feature feels right to a person. A test can pass and still not meet what the user expects. And as
one of the principles of testing says, finding no more bugs doesn't mean there are none - maybe I
just haven't imagined the scenario that finds them yet.

**Two bugs I found.** I was testing the Share panel, selecting several notes to make one share
code, and the notes wouldn't select. I switched to a light theme and there was no problem. On the
dark themes the tick simply didn't show - the notes were selected, but nothing on screen said so.
I reported it in detail, so the agent would know exactly where to look. Another time I noticed
that every theme change showed a "Note updated" message, although no note had changed. Small bugs
like these - a message with no reason, a flicker that took long sessions to get rid of, a cursor
that stayed in a search box after I clicked elsewhere - can be found all along the way. Explained
well and in detail, they can all be solved; and if not, we adapt and change things until they
work.

**What surprised me most** was how long and careful testing can be. But that is how I learned to
describe a problem clearly enough for a developer to know what to look at and fix. A small feature
everyone knows can be hard to explain if you don't have the words for it. It was a challenge, and
I'm glad I went through it. It also made me decide to take the ISTQB Foundation certification,
which I'm preparing for.

## What I learned

Software can be hard and painstaking: you have to think in detail about what comes next, so you
don't break what works. Testing has to be renewed all the time, with features tested and retested
to make sure everything works as it should. And working with AI connects all of it: you have to
speak clearly, in detail and logically, to build something from start to finish without getting
lost.

## What I would do differently

I would make a more detailed work plan at the start, get to know the AI before giving it work - so it knows who it is working with - and set clearer working rules from the beginning.

## What comes next

It is hard to judge my own app objectively. What bothers me is that it is still a first version,
when other apps are so far ahead. I plan to keep improving it as I gain experience; I don't intend
to leave it. There are always details to consider - some I can't see yet, but I'm sure I will.
After the desktop app, an Android version will follow, so your notes can come with you.

---

*Everything here comes from me: what I lived, what I decided and why. The agent helped me put it
into a page, and I checked every sentence. - Alexandra Moldovan, October 2026*
