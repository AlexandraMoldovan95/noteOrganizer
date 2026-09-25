# Changelog

All notable changes to Note Organizer are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Version
numbers are retrospective groupings of related work — the project didn't tag formal
releases from day one, so early history is grouped by theme rather than exact date, and a
few back-to-back bumps ship inside one grouped section (the
[Roadmap's version ledger](docs/ROADMAP.md#version-ledger) records every single number).
How the numbers themselves are counted is the
[Roadmap's Versioning section](docs/ROADMAP.md#versioning).

| Version | Date | In one line |
|---|---|---|
| [0.75.180](#075180--2026-09-25) | 2026-09-25 | Shortening how long the Trash keeps notes asks first — and only when the shorter window would really destroy something. |
| [0.75.179](#075179--2026-09-25) | 2026-09-25 | A checklist item you remove can be put back where it was — and an offer of Undo stays on screen instead of being wiped a second later by the autosave's own banner. |
| [0.75.177](#075177--2026-09-25) | 2026-09-25 | Moving a batch of ticked notes to another category asks first, and offers a way back — each note to the category it actually came from. |
| [0.75.176](#075176--2026-09-25) | 2026-09-25 | The calendar stops drawing previews over menus and tables as rows of bars, and offers a note's actions the same way the rest of the app does. |
| [0.75.173](#075173--2026-09-15) | 2026-09-15 | The selection bar shows all four of its actions, and a ticked box looks ticked on a dark theme. |
| [0.74.170](#074170--2026-09-15) | 2026-09-15 | A repeating series says so wherever it can be deleted — including the Trash, where deleting cannot be undone. |
| [0.74.169](#074169--2026-09-15) | 2026-09-15 | Deleting a note stops redrawing the whole screen — the list, the calendar and the statistics were all rebuilt, two of them off screen. |
| [0.74.168](#074168--2026-09-15) | 2026-09-15 | Deleting something offers Undo where you deleted it — including the one delete that had no way back at all. |
| [0.73.166](#073166--2026-09-14) | 2026-09-14 | Changing several notes' category at once no longer comes undone on the one note you had open in the editor. |
| [0.73.165](#073165--2026-09-13) | 2026-09-13 | A code made in the editor carries the note it came from, an update from one is no longer undone by the editor a moment later, a generated code belongs to the note on screen, and Settings shows how things are now. |
| [0.73.161](#073161--2026-09-13) | 2026-09-13 | A note's identity is written down the first time it is given out, so it survives closing the app — and a note restored from the Trash never takes one another note is already using. |
| [0.73.159](#073159--2026-09-12) | 2026-09-12 | A note carries an identity that cannot collide, so one you already have — edited elsewhere and sent back — is recognised and you are asked whether to update it or keep both. |
| [0.72.159](#072159--2026-09-12) | 2026-09-12 | The window looks like it belongs to the app: its own icon, in the theme's colour, and a title bar that wears the theme instead of the system's. |
| [0.71.158](#071158--2026-09-11) | 2026-09-11 | Three defects found by re-checking what the project had written down: the wrong note opening after a tidy-up, a heavily styled note that looked frozen, and a clipped label in the sidebar. |
| [0.71.155](#071155--2026-09-11) | 2026-09-11 | Styling meets a per-line ceiling — the shape of a note's formatting, not just how much of it there is, can no longer keep the app from opening. |
| [0.71.154](#071154--2026-09-11) | 2026-09-11 | The product review's Tier 0 closed whole — every way the app could lose, mangle or refuse your work, then closed again where three adversarial passes proved the class was wider than the finding. |
| [0.71.135](#071135--2026-09-10) | 2026-09-10 | Removing an attachment asks first — the one permanent delete that skipped every confirmation, closed by the destructive-gesture sweep. |
| [0.71.134](#071134--2026-09-10) | 2026-09-10 | Nine audit small classes closed — the calculator, bleeding paste styles, honest Select-all, nested Escape, pasted tables, whole backups, autosave traces and a theming leak. |
| [0.71.125](#071125--2026-09-10) | 2026-09-10 | Six audit medium classes swept whole — visible carets and honest saves, atomic exports that closing waits for, tables that redraw and hold the view, emoji-proof clicks and finds. |
| [0.71.119](#071119--2026-09-09) | 2026-09-09 | Three audit-found user-facing safety fixes — every route that copies a note gives the copy its own attachment files, a fresh emoji no longer crashes sharing or export, and destructive confirms warn clearly instead of pre-selecting Yes. |
| [0.71.116](#071116--2026-09-09) | 2026-09-09 | Undo is whole on lists and tables — one Ctrl+Z never empties a note, dissolves a table, or half-undoes a checkbox. |
| [0.71.113](#071113--2026-09-09) | 2026-09-09 | Import hardening — a hostile share code can't delete outside files, and a corrupt repeat interval can't crash the app on launch. |
| [0.71.111](#071111--2026-09-09) | 2026-09-09 | A searchable calendar History register, a frame on the open day, and field-smoothed occurrence/History navigation. |
| [0.69.108](#069108--2026-09-07) | 2026-09-07 | The occurrence world becomes visible: banners, ✎ marks, per-day reset, calendar filters and sorts, the way back on every route. |
| [0.66.105](#066105--2026-09-07) | 2026-09-07 | BackSpace and Delete treat an emoji as one character in every text field. |
| [0.66.104](#066104--2026-09-07) | 2026-09-07 | Every data file saves atomically; an unreadable one is preserved and announced, never silently emptied. |
| [0.66.102](#066102--2026-09-07) | 2026-09-07 | Autosave goes mute — no background dialog, and every editor-clearing gesture saves first. |
| [0.66.100](#066100--2026-09-05) | 2026-09-05 | A cancelled right-click delete can no longer hand the autosave a wrong target. |
| [0.66.99](#06699--2026-09-05) | 2026-09-05 | A note shared from the editor arrives whole — checklist, formatting and paragraphs included. |
| [0.66.98](#06698--2026-09-05) | 2026-09-05 | The app speaks English everywhere; a shared note keeps its checklist; any-script input proven. |
| [0.66.97](#06697--2026-09-04) | 2026-09-04 | Keyboard reach — app-wide Ctrl+N and Ctrl+S shortcuts, and an in-note Ctrl+F find bar. |
| [0.64.97](#06497--2026-09-02) | 2026-09-02 | The comments box and the calendar preview stop showing tables as raw pipe rows. |
| [0.64.95](#06495--2026-09-02) | 2026-09-02 | A tables hardening wave — export, clipboard, Word, undo, search, styling and scroll all learn to treat a table as a table — alongside a Windows CI leg and a mutation audit of the old regression checks. |
| [0.58.82](#05882--2026-08-30) | 2026-08-30 | Scroll-position stability for the note list, plus new backup, trash and shortcut settings. |
| [0.55.81](#05581--2026-08-30) | 2026-08-30 | Tables grow up — per-character styling, multi-line cells, real checkboxes, draggable rows — while the template editor learns to draw them and the GUI tests become hermetic. |
| [0.39.64](#03964--2026-08-28) | 2026-08-28 | One fix — the app now calls itself Note Organizer everywhere, matching its docs. |
| [0.39.63](#03963--2026-08-28) | 2026-08-28 | Tables arrive as Markdown-backed grids, with cross-feature checks guarding the seams. |
| [0.38.59](#03859--2026-08-26) | 2026-08-26 | The editor's text boxes get their width back, and PDF paste builds real paragraphs. |
| [0.38.56](#03856--2026-08-26) | 2026-08-26 | The note body gains a remembered Expand toggle for long notes. |
| [0.37.56](#03756--2026-08-26) | 2026-08-26 | Paste becomes format-aware — rich text travels into and out of notes, with no new dependency. |
| [0.36.56](#03656--2026-08-25) | 2026-08-25 | Fonts land in notes and Settings, alongside theming, toolbar and title-field fixes. |
| [0.34.51](#03451--2026-08-25) | 2026-08-25 | Paragraph formatting lands — lists, indentation, alignment and quote blocks. |
| [0.32.51](#03251--2026-08-21) | 2026-08-21 | Settings rebuilt around a section list, and the core layer becomes a package. |
| [0.32.49](#03249--2026-08-20) | 2026-08-20 | Theme switching goes flicker-free and ~5× faster; selection quirks ironed out. |
| [0.32.44](#03244--2026-08-19) | 2026-08-19 | Text color and highlight join the toolbar, plus a round of selection fixes. |
| [0.31.39](#03139--2026-08-18) | 2026-08-18 | Rich text begins — Bold, Italic, Underline and Strikethrough in the editor. |
| [0.30.39](#03039--2026-08-18) | 2026-08-18 | One critical data-safety fix — script-mode runs can no longer delete the real notebook in `%APPDATA%\NoteOrganizer`. |
| [0.30.38](#03038--2026-08-18) | 2026-08-18 | An in-note calculator — hand-rolled parser, insert-into-note logging, session history — with 47 evaluator checks behind it. |
| [0.28.38](#02838--2026-08-17) | 2026-08-17 | A broad stability sweep — search debounce, a 16-timer crash-safety audit, autosave and backup hardening, a livelier Statistics page, and two new QA suites. |
| [0.5.0](#050--2026-08-09) | 2026-08-09 | Going public — docs, GitHub and CI arrive alongside bulk actions and image previews. |
| [0.4.0](#040--performance-overhaul--test-infrastructure) | — | Performance overhaul plus the first automated test suite backing it up. |
| [0.3.0](#030--tags-removed-categories-as-the-sole-organization-system) | — | Tags come out entirely, leaving categories as the app's one organization system. |
| [0.2.0](#020--inline-ui-overhaul--data-resilience) | — | Every OS-native popup becomes an in-app themed one, and the calendar grows richer. |
| [0.1.0](#010--core-application) | — | The founding feature set — notes, recurrence, calendar, templates, sharing, themes. |

---

## [0.73.167] — 2026-09-15

*Highlights: the explanations in Settings no longer stop mid-word.*

### Fixed

- **The explanatory line under each Settings title was cut off at the right edge.**
  Duplicates ended at "date and col", Templates at "use 🧩 Save as template on an",
  Backup at "not in the a folder" — and the missing words were the ones carrying the
  meaning. A label breaks its text at a set width and then draws those lines inside
  whatever width it was actually given; when the two disagree, the ends are not drawn
  and nothing says so. Each of those widths was a hand-picked number standing in for
  padding the label could not see, and each was short — the subtitle asked for 620
  pixels and was given 544. They are taken from the label itself now, so a change to
  the layout cannot leave them behind again.

---

## [0.75.180] — 2026-09-25

*Highlights: the quietest way to lose notes in the app now says what it is about to cost, and stays quiet the rest of the time.*

### Fixed

- **Shortening how long the Trash keeps notes asks first.** Picking a shorter window in
  Settings saved on the click. Choose "7 days" with notes sitting in the Trash from last
  month and they were destroyed for good at the next startup — their attached files
  deleted from disk with them — with no dialog at all, while every other permanent
  deletion on that same screen warns that it cannot be undone. The damage also landed on
  a *later* launch, when nobody would connect it to a dropdown they touched days before.
  It now asks with the same warning the panel's other permanent deletions use, naming how
  many notes would go, how many attached files go with them, that it happens the next time
  the app starts, and — if one of them repeats — that a whole series is among them.
  Backing out puts the dropdown back where it was rather than leaving it showing a window
  the app did not adopt. **And it stays quiet when there is nothing to lose:** a longer
  window never asks, and neither does a shorter one with nothing old enough to lose, since
  a question nobody needs teaches people to dismiss questions.

### Testing

- Thirty-seven checks in qa6 over seven scenarios, six of them stating what the fixture
  set up. Ten mutants, each dying on the check written for it — four only after the checks
  they exposed were rewritten, because each was satisfied by a coincidence: a lengthening
  fixture whose notes were inside the longer window either way, two clamp comparisons that
  returned the same number clamped or not, and a count that the inverted window satisfied
  with the wrong note. The count in
  the question and the startup purge now come from **one** function, so a dialog cannot
  name a number the purge will not deliver — and a check proves the two agree, on which
  entries as well as how many.
- `tools/run_tests.py` gained `--all-failures`, and says "... and N more" when it cuts the
  list. It printed only the first eight failing checks, which made two live mutants read
  as survivors: the checks they broke were the ninth and later, so the names being watched
  for were simply never printed.

---

## [0.75.179] — 2026-09-25

*Highlights: the last thing you could remove from a note with no way back has one — and the Undo offers that already existed now last as long as they look like they will.*

### Fixed

- **A checklist item you remove can be put back, where it was.** The small bin on a
  checklist row was the one delete in the app with no route home at all: Ctrl+Z reaches the
  note's text boxes, and a checklist is a list of items beside them, so nothing in the
  editor could return a line struck off by a mis-click. Removing one now offers **Undo**,
  and the item returns to its own position rather than to the end of the list. There is
  still no question first, deliberately — a dialog in front of every tick-list tidy-up
  would cost more than it protects, and the app's rule is that a destructive action is
  confirmed in proportion to how recoverable it is. What it needed was to become
  recoverable.
- **An offer of Undo stays on screen for as long as it looks like it will.** Every Undo in
  the app — a deleted note, a removed day of a repeating note, a batch refiled into
  another category — is offered on the small banner at the top, and the autosave's own
  "Note updated" banner replaced it. So the offer was gone about a second after it
  appeared rather than the eight it seemed to promise: long enough to see, rarely long
  enough to use. The autosave's banner is only reassurance, so it now waits while an offer
  is on screen, and the status line reports the save as it always did. Bad news never
  waits: an error still interrupts anything.

### Testing

- Thirty-three checks in qa1 over ten scenarios — the item returning to its own place, the
  offer surviving the save it triggered, the autosave's banner still appearing when no offer
  is up, an error never being held back, a second click on a toast that has not faded,
  switching notes or applying a template inside the offer's life, an item written in another
  alphabet, and one day of a repeating note. Ten of the thirty-three state what the fixture
  set up before anything is measured from it. Nine mutants, each dying on the check written
  for it — two of them only after the checks they exposed as toothless were rewritten.

---

## [0.75.177] — 2026-09-25

*Highlights: the one action in the selection bar that changed your notes with no question and no way back now has both.*

### Fixed

- **Moving a batch of ticked notes to another category asks first, and offers a way
  back.** It was the only action in that bar with no guard at all: pick a category and
  every ticked note was refiled the instant you clicked, with nothing on screen but a
  status line — while **Trash**, the button beside it, asked first *and* offered Undo.
  The categories it overwrote were gone from the file the moment it ran, which matters
  most for exactly the selection a bulk change is for: notes that sat in several
  different categories, whose old filing no single "put it back" could guess. So the
  Undo remembers each note's own category rather than one value for the batch, and puts
  the *last edited* stamps back too, so nothing you did not ask for is left behind. The
  question says how many categories are being overwritten, and — where it applies — that
  a day you gave its own category by hand keeps it.

### Testing

- Thirty-six checks in qa1 across eight scenarios: a mixed selection and the way back
  from it, saying No costing nothing, a second click on a toast that has not faded, the
  editor holding one of the ticked notes, a note ending in a table, a repeating series
  with a day of its own, a filtered list, and a category deleted while the offer was
  still on screen. Ten mutants break the mechanisms behind them one at a time, and each
  dies on the check written for it.

---

## [0.75.176] — 2026-09-25

*Highlights: whichever way you reach a note in the calendar, it now offers the same things — and offers them the way the rest of the app already does.*

### Fixed

- **A note's preview no longer hovers over the menu you just opened.** Right-click a day,
  then let the mouse drift a few pixels onto a neighbouring cell, and the day's preview
  drew itself on top of the menu you were reading. A menu keeps the app running
  underneath it, so the hover never stopped firing. Nothing hovers over an open menu now.
- **A table in a preview is mentioned, not drawn as a row of bars.** The panel under the
  calendar showed a note's tables as raw vertical lines, and the small preview that
  follows the mouse showed the note's body untouched — tables and all — without even
  saying a table was there. Both now show the note's words and a chip saying what else it
  carries, which is what the panel had always meant to do: the rule it used to strip
  tables is the editor's rule, and it is strict on purpose, so a row typed past its last
  cell was neither counted nor removed. That is the line you could see.
- **A note in the calendar answers the same way wherever you meet it.** Two screens show
  the same note and each had half the story. Arriving from the History register put you
  on a preview that was the only place in the app where right-clicking a note did
  nothing — so Pin, Export as file, Duplicate, and, for a repeating note, *edit just this
  day* / *edit the whole series* / *reset this day to the series content* were all simply
  unavailable there, even though the same note offered every one of them from the day's
  list. Meanwhile the day's list carried the only per-row delete button in the app: a
  grey glyph with no word, packed against the scrollbar, where a slipped click destroyed
  a note. The app already had a rule and the calendar was the one screen breaking it —
  a list of notes offers its actions by right-click, and a labelled **Delete** appears
  only where a single note is open. Both screens follow it now.

### Testing

- Seven checks in qa7: the day list carrying no button of its own, deleting from it
  still working through the menu, the menu being the whole menu rather than a delete on
  its own, and the preview answering to right-click with the actions appropriate to the
  day it is showing rather than to the series behind it.

---

## [0.75.173] — 2026-09-15

*Highlights: using Select is all of a piece now — seeing the actions you can take, seeing which notes you have ticked, and being able to change your mind about all of them at once.*

### Added

- **"Select all" becomes "Unselect all" once everything on screen is selected.** One
  button rather than two, because the second is only ever wanted straight after the
  first: a mis-aimed press used to mean leaving selection mode altogether and starting
  over, since nothing else lets go of a selection in one gesture. "All" still means what
  the list is showing, so with a search or a category filter active it takes — and
  releases — exactly those notes.

### Fixed

- **The selection bar's last button is no longer cut off.** Its five controls were laid
  out in one line across a sidebar of fixed width, so when they did not fit, the one at
  the end simply lost the room — everything before it looked perfect, which is why
  nothing seemed wrong until you reached "Export" against the edge with its caret sliced
  off. The count moved onto its own line and the four actions sit two by two, so the
  widest row needs the two widest labels rather than all four. Measured, that is 180
  pixels of the 250 available on the strictest of the fonts the app is drawn in, instead
  of 338 — room to spare rather than a margin waiting to be eaten by the next word.
- **Selecting or unselecting every note no longer redraws the list.** Moving a tick is
  not a change to the notes, but the whole list was destroyed and rebuilt to do it — 140
  widgets and about a sixth of a second, on every press, and twice as often now that the
  button can also let go. The tick boxes are moved where they stand.
- **A ticked box now looks ticked on a dark theme.** The little well a check mark sits in
  was set to the very surface the box sits on, and the mark itself is drawn dark
  whatever the theme — so on any dark theme a ticked note and an untouched one looked
  the same. Light themes hid it completely, because their surface is already white. The
  well is now a named colour of its own, light in every palette, because the reason has
  nothing to do with which theme is loaded: the mark is dark, so its background must not
  be.

### Testing

- The bar's fit is now measured rather than assumed — every action drawn at least as
  wide as it asks — and the tick boxes are judged on both things that matter: a well
  that is not the surface behind it, and one light enough for a dark mark, checked on
  both routes that build those boxes and across every palette. Four mutants, each dying
  on the check written for it. `qa/probe_bar_width.py` prints the widths on whatever
  system runs it, since the fonts differ between Windows and the Linux CI image and a
  layout that fits on only one of them is a coincidence.

---

## [0.74.170] — 2026-09-15

*Highlights: a repeating series is one note in every list and every count, and deleting it takes every occurrence — the routes that act on a selection now say so, including the two in the Trash that cannot be undone.*

### Fixed

- **Deleting several notes at once now tells you when one of them is a whole repeating
  series.** Deleting a single repeating note has always asked "Delete this entire
  repeating series?". Ticking it along with others asked only whether to move N notes to
  the trash — and a series is one note in that count while taking every occurrence with
  it. The same silence ran deeper: the Trash listed a series exactly like a one-off note,
  and both of its permanent deletes — one row, or Empty trash — called it "a note" while
  destroying the whole series with no way back. A series is now marked in the Trash the
  way it is marked everywhere else (🔁, and how often it repeats), and all three
  confirmations say what goes with it.

### Changed

- The Trash's list is taller (three rows and a lot of scrollbar became six), and the
  Restore and Delete buttons on each row are guaranteed their width — they used to be
  squeezed by a long title, since the text was given the space first.

### Testing

- Twenty-three checks in qa3 and eight in `test_recurrence.py`, covering the marking, all
  three confirmations, the silence when no series is involved, the row's layout
  guarantee, and a trash entry whose recurrence field holds something that is not a
  recurrence at all. Eight mutants, each dying on the check written for it.

---

## [0.74.169] — 2026-09-15

*Highlights: the note list no longer empties and refills every time you delete something — and the calendar and statistics stop being rebuilt for screens you are not looking at.*

### Fixed

- **Deleting a note no longer makes the screen flicker.** The whole note list was
  destroyed and rebuilt to take one card away, and two more screens were rebuilt
  alongside it that were not even visible: the calendar's month grid and the Settings
  statistics panel. Together that was 264 widgets and about a fifth of a second, every
  time — long enough to see, which is how it was reported ("the picture breaks a little
  and rebuilds itself"). A delete now takes the one card off the list, leaves the others
  exactly where they are, and rebuilds the calendar and the statistics only when someone
  is actually looking at them: 3 widgets and about a thirtieth of a second. Anything the
  surgical path is not certain of — an emptied list, a category header that would not
  update — still falls back to the full rebuild, because a list that quietly disagrees
  with your notes would be far worse than one that flickers.

### Testing

- Eighteen checks across qa1, qa6 and qa7 covering the surgical path and, as much,
  the fallback: a surviving card proved to be the same widget rather than a remade
  one, the scroll position untouched, category counts coming down (including for a
  collapsed group, which draws no cards at all), a group's header leaving with its
  last note, the calendar caught up on every route back to it, and the statistics
  current both while Settings is open and on the next visit. Eight mutants, each
  dying on the check written for it.
- **A check that had been passing on timing was repaired.** qa7's "switching notes
  does not rebuild the list" had always run after a 180ms search-debounce timer
  happened to have fired; once deleting got six times faster the timer landed
  mid-measurement instead. It — and the new checks beside it — now settle every
  timer that could rebuild the list first, and say so. Written up in
  [qa/README.md](qa/README.md).

---

## [0.74.168] — 2026-09-15

*Highlights: the way back from a delete is now where the delete happened, instead of three clicks away in Settings — and for one kind of delete, there was no way back at all until now.*

### Added

- **Undo on the delete banner.** Delete a note and the banner that confirms it carries an
  **Undo**: one click puts the note back and opens it, with everything it held — tables,
  formatting, checklist ticks, attached files. The same after deleting several at once;
  all of them return. Until now the only route home was Settings → Recently deleted,
  which asks you to already know the Trash exists. It also covers the one delete that
  was permanent and said nothing about it: removing a single day from a repeating note
  writes that day into the note's exceptions, and no screen in the app took it out
  again. The banner stays eight seconds when it carries an Undo, rather than the usual
  one and a half — an offer nobody can reach in time is decoration.

### Fixed

- **A banner reporting a failure no longer opens with a tick of success.** Every banner
  began with "✓", whatever it had to say — so a disk that could not be written to
  announced itself as "✓ Something went wrong with that". The mark now follows the kind
  of message.

### Testing

- Twenty-two checks for the new behaviour across qa3 (the Trash) and qa7 (the calendar's
  delete routes), covering the restore itself, an Undo after something else was deleted
  in between, an Undo on a trash that was emptied underneath it, a second click on a
  spent offer, a theme switched while the banner is on screen, and a note carrying a
  table, formatting, a checklist and an attachment making the round trip unchanged.
  Thirteen mutants, each dying on the check written for it.

---

## [0.73.166] — 2026-09-14

*Highlights: a bulk category change now sticks on the note you happen to have open, instead of being written back the moment you carry on typing.*

### Fixed

- **Changing several notes' category at once no longer comes undone on the one note you
  had open.** The change reached every note, and then the next thing you typed put the
  open one back where it was — because the editor was still showing that note's old
  category and its save writes what the editor shows. Nothing on screen said so, and the
  other notes kept the new category, which is what made it easy to miss. Anything you had
  typed before the change is saved first, so nothing is lost either way.

---

## [0.73.165] — 2026-09-13

*Highlights: a code made in the editor now says which note it is — and updating a note from one sticks, instead of being written back over a moment later by the editor that was still showing the old version.*

### Fixed

- **A code made in the editor now says which note it is, so bringing that note
  back updates it instead of copying it.** "Generate code" built the code out of what
  the editor had on screen, and a note's identity is not something on screen — so the
  code went out describing a note with those words rather than *that* note. Sent to
  another device and brought back, it was a stranger: you were asked whether to keep the
  duplicate, not whether to update the note it came from. Codes made by ticking notes in
  the sidebar's Share panel always carried it; the editor's did not, and the editor is
  the route you reach for when you have the note open.
- **Updating a note from a code no longer gets undone a moment later.** The note you
  send out is usually the note you have open — and the update replaced what was stored
  while the editor went on showing the version from before. Saving the editor, which any
  keystroke does, wrote that version straight back over the update. Nothing on screen
  said so: the note simply reverted. The editor is now brought onto the new version, and
  whatever you had typed is saved first, so "↩ Restore previous" still hands it back.
- **A generated code disappears when you open another note.** It used to stay on
  screen under whichever note you moved to, reading as though it belonged to that one.
  Copying it then shared the wrong note, and nobody proofreads a wall of characters.
- **Settings shows how things are now, not how they were when you last looked.**
  Recently deleted, Duplicates, Categories and Templates came back exactly as they were
  built on an earlier visit: a note deleted since then was missing from Recently deleted
  until you clicked the section again.

### Changed

- **Right-clicking a note in the list no longer offers "Open / Edit".** Clicking the
  note already opens it for editing, so the entry was a longer way to do what the click
  had just done. It stays where a click means something else: on a calendar day, where
  clicking opens the note inside the day panel, and in the calendar's History register,
  where clicking jumps to a date.

### Removed

- **The unused multi-note tab machinery.** A row of tabs above the editor was built for
  keeping several notes open at once, and the app never opened more than one: every path
  reset the list to a single entry, so the row could not appear and the code that closed
  a tab could not run. About a hundred lines guarding states the app could not reach.
  The choice it had been waiting on — build real multi-note tabs, or take it out — is
  settled by taking it out; nothing you could do in the app changes. What it wrapped and
  what does the real work, keeping the editor and the stored note in step, stays.

---

## [0.73.161] — 2026-09-13

*Highlights: the identity a note was given in 0.73.159 is now written down, so it is the same identity tomorrow — a share code made today still finds the right note after the app has been closed.*

### Fixed

- **A note's identity now survives closing the app, so a code you made yesterday still
  finds the right note today.** The identity was handed out the moment a note was read,
  but it was only kept in memory: on a session where you read and never changed
  anything, nothing wrote it down, and the next launch handed out a different one. The
  effect was invisible until it mattered — share a note, close the app, come back the
  next day and import that code, and the app no longer recognised the note it came from.
  It added a copy instead, which is exactly the behaviour the identity exists to prevent.
  The first read that hands out identities now writes them down, once. Nothing to run and
  nothing to decide; a notebook that already has them is not rewritten, and a notebook
  the app could not read is never written over.
- **A note restored from the Trash no longer takes an identity another note is already
  using.** A restore already gives the note a fresh number, because the one it had may
  have been taken while it was gone. Its identity can be taken the same way — by a copy
  of that very note arriving from a share code while the original sits in the Trash — and
  the restored note then shared a name with it. Now it keeps its identity when that is
  free, which is the normal case, and is given a new one only when it is not.

---

## [0.73.159] — 2026-09-12

*Highlights: a note now has a name of its own, not just a number — so a note you already have, edited somewhere else and sent back, is recognised instead of copied.*

### Added

- **A note keeps the same identity wherever it goes, so bringing one back updates
  it instead of copying it.** Until now a note's only name was its number, and that
  number is just its place in one file: a note written on a second computer gets the
  same number as an unrelated one here, and nothing on either side can tell them
  apart. Every note now also carries an identity that cannot collide, given to it the
  first time the app sees it — an existing notebook gains them on its next launch,
  with nothing to run and nothing to decide. Share codes carry it, which changes what
  happens when a note you already have comes back: the app recognises it and asks
  whether to **update the copy you have** or **add it as a separate note**. It used to
  compare the text instead, and the text differs precisely because the note was edited
  — which is the only reason anyone re-sends one — so it quietly left you with two.
  Updating is undone by the editor's existing "↩ Restore previous", so the reversible
  answer is the one you land on. Both routes that bring notes in, a pasted code and a
  restored backup, ask the same question through the same code; and duplicating a note
  gives the copy an identity of its own instead of the original's.

## [0.72.159] — 2026-09-12

*Highlights: the parts of the window that were never the app's — a system-grey title bar and
somebody else's placeholder icon — now belong to it, and follow whichever theme you are in.*

### Added

- **The window wears your theme, all the way to its edges.** The bar along the very top —
  the one with the app's name and the minimise, maximise and close buttons — used to be
  whatever colour Windows felt like, which meant a light strip sitting on top of a dark app.
  It now takes the theme's own background and text colour, with the window's outline in the
  theme's accent, and it changes in the same moment as everything else. The app's icon
  changes colour with the theme too: there is one drawn for each accent the themes use, so a
  green theme gets a green icon and an amber one an amber icon. It is still the native title
  bar, deliberately — a hand-drawn one would have cost snapping to screen edges, dragging,
  double-click to maximise, the system menu and every keyboard and accessibility affordance
  Windows provides for free. Windows 11 only; on anything older the bar is simply the
  system's usual one.

### Fixed

- **The app has an icon of its own, and the file says what it is.** There was none anywhere:
  a generic feather in the title bar and the taskbar, the toolkit's own placeholder stamped
  on the `.exe`, and a version resource reading `0.0.0.0` with no product name, so the file's
  Properties were blank. The icon is now drawn from the app's own palette, the `.exe` carries
  it, and the version resource is generated from the app's version at build time — so the
  number Windows shows can no longer drift from the one the app shows.

### Testing

- The product-findings register had gone stale in a way that made the remaining work
  unreadable: all thirty-eight findings were marked open, including the eight that shipped
  months ago. The nine that were done are marked done, each confirmed against the code rather
  than the changelog, and a tool now asks the code one finding at a time instead of anyone
  trusting the column.
- The one check guarding the note list's rebuild cost measured the time, printed it, and then
  asserted a literal `True` — it could not fail. It now asserts that the rebuild really built
  every card, and a budget set five times above the slowest measured run rather than anywhere
  near it.
- The theme switch was measured again after a field report, and the numbers recorded where
  the next person will find them. The obvious suspect turned out to account for 2.4 ms of it.

## [0.71.158] — 2026-09-11

*Highlights: none of these came from a bug report. They came from going back through the
project's own records — a coverage ledger, a seam map, a set of screenshots — and checking
whether what they claimed was still true. Three of them were not.*

### Fixed

- **The one-time tidy-up no longer opens the wrong note afterwards.** A notebook upgrading
  from an older version gets one cleanup pass: empty notes are dropped, exact duplicates are
  collapsed, and every note is renumbered from 1. The app also remembers which note you had
  open — by its number — and that number was left pointing wherever it landed. With a single
  empty note in front of it, the note you were reading moved from 2 to 1, the setting still
  said 2, and the next launch opened the note AFTER the one you left. Where the number fell
  off the end instead, the app opened nothing. It now follows the note rather than the
  number, and a remembered note the cleanup removed opens nothing at all — which is honest,
  and better than opening a stranger's.
- **A heavily styled note opens instead of looking frozen.** Saving reads a note's styling
  back out of the editor, and each styled piece's two ends were worked out by re-reading the
  note from its start — three times over, on every open. A note carrying the most styling the
  app allows spent 14 of its 15 seconds doing that, with nothing on screen to say so. The
  reading is done in one pass now: the same 500 styled pieces cost 0.19 seconds instead of
  14.3, and the window appears in about a second and a half. Ordinary notes were never slow
  and are unchanged — a 40,000-character note carrying 300 styled pieces opened in 1.55
  seconds before and still does.
- **The sidebar's sort control shows its whole name again.** It read "Recently up" with no
  arrow. The label had room; the row did not — it asked for more width than the sidebar has,
  and the space was taken off the one control that flexes, right edge first. Both dropdowns
  size themselves to what they are showing now, which is what lets that flex work. The old
  fixed width could not have been right on both platforms anyway: the number that fits
  Windows is 19 pixels over-full in the font the Linux build uses.

### Testing

- The documentation's own claims are checked now rather than trusted. A new link checker
  walks every in-repo Markdown link — 425 of them — and runs before every push, because a
  reworded heading breaks a link silently and a dead anchor just scrolls nowhere. It was
  proved against deliberately broken links before it was believed.
- The seam map that tells a sweep which test files guard which surface is generated from the
  suite instead of maintained by hand. It had drifted: three whole surfaces were missing from
  it, and several rows named fewer files than actually guard them.
- The documentation's screenshots are staged in code, so a retake is a command. Three were
  picturing controls that no longer exist and have been retaken.
- Two coverage-ledger rows that claimed measurements nobody had taken are corrected; the
  caret-over-emoji question they sat beside is answered on both platforms.

## [0.71.155] — 2026-09-11

*Highlights: the styling ceiling shipped one version earlier counted the wrong thing —
a note could still be built that the editor never finishes drawing, using a fifth of
what that ceiling allows.*

### Fixed

- **A pasted share code can't hang the app through its styling either.** The ceiling
  added in 0.71.154 caps how many styling spans a note may carry, and that turns out
  not to be what costs anything: what stops the editor finishing a draw is how many
  styled pieces land on a single LINE. Two shapes reach that while staying far under
  the cap — every span crowded onto one line, or every span stretched to the end of the
  note so they all pile onto the last one — and neither finished drawing at all. Since a
  pasted note is saved before it is ever shown, such a note made the app fail to open on
  every launch after, which is the same failure as the oversized checklist, one field
  over. Styling now meets two ceilings at the same door the checklist and attachment
  ceilings already use: how much may cover one line, and how much a note may draw in
  total. Both sit far above anything a person writes — 300 bold words across 300 lines,
  or a densely styled paragraph, pass through untouched — and all three ways styling
  reaches the editor (a note, a template, and the copy behind "Restore previous") meet
  them. From re-measuring a recorded residual that turned out to be wrong.

### Testing

- The shapes that used to hang are held by the unit suite, which builds no window and
  can therefore carry them safely; the GUI suite witnesses the same ceiling at the
  editor door, at a size just over it, so removing the fix turns a check red instead of
  hanging the run before it can report anything.
- Five mutants, every one killed with the run reaching its failures footer — and the two
  checks that guard ordinary, heavily-styled notes stay green under all five, which is
  what proves the ceiling only refuses what it is meant to.

## [0.71.154] — 2026-09-11

*Highlights: the product review's Tier 0 — every way the app could lose, mangle or
refuse your work — closed at the root of each class and then closed again where the
adversarial review of the first round proved the class was wider than the finding.*

### Fixed
- **A checklist-only note is a real note, to every part of the app that asks.** The
  startup clean-up judged a note empty by its title, body, comments and attachments
  alone, so a note whose content was its checklist (or repeat rule, or date) was deleted
  on the next launch — not moved to the Trash, simply gone. The first fix widened that
  one test; the adversarial review then found the same blind spot in three more places
  that answer "is this the same note?": the stale-copy purge — which authorises an
  irreversible delete of a leftover notebook folder on every launch — still judged by
  the old five fields, and Find-duplicates plus all three import scans ignored
  checklists and repeat rules entirely, though neither is merged when a duplicate is
  cleaned up. There is now ONE content signature in the data core that every consumer
  calls (with a check that fails the day anyone grows a private copy again); duplicate
  matching counts the checklist and the repeat rule, and deliberately keeps ignoring
  attachments, which the clean-up genuinely merges. From the product review, widened by
  the adversarial review.
- **One notebook, one window — and the lock can only ever refuse for the right
  reason.** Nothing stopped a second copy of the app opening on the same notes; both
  rewrote the file whole, so whichever autosaved last silently erased the other's work.
  A second launch now says the notebook is already open and steps aside. The guard is an
  OS file lock the kernel releases however the process dies, so a crash can never lock
  you out — and only the errnos that mean "another process holds it" refuse: a folder
  whose filesystem cannot do locks at all (network shares, exotic mounts) starts
  normally, where the first version of the guard read every locking error as "already
  open" and would have bricked the app on exactly those folders. From the product
  review; the fail-open repair from the adversarial review.
- **Importing your own backup brings your whole filing system back.** The backup zip has
  always carried settings.json and the import never read it: categories flattened to
  "General" under an "Import complete" message, and the calendar's day colours and emoji
  markers vanished entirely. Both now restore — additively, never overwriting this
  device's own — and the completion message names what came back. The categories merge
  runs BEFORE the duplicate scan, because the scan re-files unknown categories to
  General first, and a distinct note could read as a duplicate of a local General note
  and be silently skipped. From the product review, the scan order and day decor from
  the adversarial review.
- **A note body keeps the shape you gave it — and the app can now SEE that it did.**
  Every save trimmed leading/trailing whitespace, reshaping pasted code and quoted
  email, and drifting every styling span measured against the untrimmed text. The save
  now stores the body exactly as typed — and the change detector compares it exactly as
  typed too: the first fix left the dirty check stripping both sides, so a
  whitespace-only edit read as "no change" and the automatic saves threw away precisely
  the characters the save had just learned to keep. The same canonicalisation reaches a per-day edit of a repeating note, which is shown in the same editor: without it such a day read as permanently unsaved and raised a save-scope question nobody had asked for — whose “whole series” answer replaced the note's text with that one day's. From the product review, the
  detector half from the adversarial review.
- **A saved note can be emptied, on every route there is.** Clearing a note and
  switching away brought the old text back: the app asked "is the editor empty?" in six
  different hand-rolled places, and the first fix taught the answer to one of them — the
  autosave and flush gatekeepers in FRONT of it still discarded the emptying, so the
  finding's own scenario was unchanged. One shared content test now answers everywhere
  (Save, Ctrl+S, the autosave timer, the note-switch flush, the back-to-calendar guard,
  the template-replace question — which also learned that attachments and checklists
  deserve the "replace?" question before a template wipes them). Comments count as
  content on every route, closing a sibling hole where a comments-only note was
  discarded with a false "Write something before saving!". The automatic routes still
  refuse a date-only never-saved editor — the calendar prefills the date field, and an
  abandoned day-click must not autosave itself into a junk note. The rescue copy behind “Restore previous” follows it: that copy used to appear only when a lot of text vanished at once, which was enough while an emptied note could not be saved at all, so a short note cleared by accident keeps one too now. Ctrl+S and the Save button agree throughout, including about a note holding only a date: both are the user asking. And the way back from a calendar note never blocks on an edit no automatic route would persist — a new note holding only a repeat rule used to make “Back to Calendar” a dead button. From the product
  review, swept whole by the adversarial review.
- **"Restore previous" survives a restart — and an aborted save.** The rescue copy was
  discarded by the next launch while the button offering it looked permanent; it is now
  part of the note's known shape. And restoring no longer spends the copy up front: the
  old order deleted it and then ran a save with several legitimate abort paths (a
  half-typed date, a cancelled question), losing the copy and the restore in one
  stroke. The copy is cleared only after the save provably landed. From the product
  review, the ordering from the adversarial review.
- **A pasted share code can't brick the app through a field with no size limit.**
  Checklists had no size limit anywhere: a 60 KB code carrying twenty thousand items was
  saved first and then killed the app on every launch after. Checklists are now capped
  at 1000 items at the choke point every route passes through — templates included,
  which the first cap missed — and the sibling fields met the same review: styling spans
  gained an anti-bomb ceiling (generous enough that a long Word-paste's thousands of
  legitimate spans are never touched), attachment records a ceiling of 200. When an
  oversized note does arrive, the import says it was trimmed instead of losing 19,000
  items in silence. From the product review, the siblings from the adversarial review,
  the numbers from measurement.
- **The warn-before-opening list knows today's dangerous files — and can't be fooled by
  a trailing dot.** The list covered the classic executables and missed the vehicles
  actually used to deliver code now (.lnk, .url, .iso, .img, .chm, .scf, .appref-ms,
  .settingcontent-ms and more); a shortcut arriving inside an imported backup opened
  with no question at all. All warn first now, with "No" pre-selected. And the check
  can no longer be smuggled past: Windows strips trailing dots and spaces when opening a
  path, so "invoice.lnk. " read as extension-less to the gate while the OS executed the
  .lnk — stored names are normalised at the data choke point and the gate strips before
  deciding, so the name it inspects and the file the OS opens can never disagree. From
  the product review, the smuggle from the adversarial review.
- **A colour the app can't draw can't keep it from opening.** Colour strings arrive from
  every untrusted door — a share code, a backup's settings.json, a hand-edited file —
  and end their journey in a Tk configure(), which crashes on garbage; because a note is
  saved before it is first drawn, one bad value meant a crash on every launch after.
  Every intake now validates: a note's own colour, imported category colours, and the
  calendar's day colours, on load and on import alike. Found by the adversarial review
  as the checklist-bomb class wearing a different field.
- **A malformed attachment record can't corrupt the note next door.** One record without
  a filename aborted the note-load halfway through its render, leaving the editor still
  holding the PREVIOUS note's checklist — which the next save then wrote onto the note
  you had tried to open. Records are normalised at the data choke point (names
  guaranteed, nameless records dropped) and the render no longer trusts a field to
  exist. Found by the adversarial review.
- **A fresh install no longer opens with a maintenance report.** The one-time clean-up
  announced itself even when it had nothing to say, so the literal first screen of the
  product was a blocking modal about "IDs renumbered 1–0" over an empty notebook. It now
  speaks only when it actually removed something. From the product review.
- **A note you can only see one day of still saves what you change.** Tick an item on a
  repeating note's checklist while looking at a single day and the tick went nowhere: the
  editor asked for the save and the change-detector vetoed it, because in that view it
  only ever compared the five fields a per-day edit can carry. Everything the series owns
  — the checklist, the files, the date, the repeat rule — is compared against the note
  itself now, which is where the editor read them from in the first place. From the
  product review's second wave.
- **Sharing a note as a code no longer refuses the note.** A note whose content is its
  checklist, or its comments, was told "Write something before copying a code" — about a
  note the app had just saved, and whose code would have carried that content perfectly
  well. From the product review's second wave.
- **A leftover notebook folder is only deleted when it really is a duplicate.** The
  start-up tidy-up that removes old copies of your notes compared them by text alone, so
  a folder whose notes differed only in their styling, their layout, their per-day edits
  or their skipped dates was judged "already covered" and deleted — while the message on
  screen said nothing had been removed unless it already existed. It now compares
  everything a note holds before deleting anything. From the product review's second wave.
- **A colour on a single day of a repeating note can't stop the app opening.** Per-day
  edits carry their own colour, and that one was never checked: a bad value from a share
  code, a backup or a hand-edited file reached the calendar's drawing code on every
  launch. It is validated like every other colour now, and the day's text edit survives
  even when its colour does not. From the product review's second wave.
- **Your categories can't be turned into a wall.** The category list is read from
  settings and from any backup you import, and the sidebar draws one entry for each with
  its full name — with no limit on either, a hand-edited file or a hostile backup could
  make the app unopenable through a door nothing was watching. The limit leaves an over-long name out rather than shortening it: a shortened name would stop matching the notes filed under it, which is worse than the problem it solves. From the product review's
  second wave.
- **"Save as template" stopped calling a checklist a nothing.** A note whose content was
  its checklist was refused with "This note is empty" — by the same screen whose template
  goes on to store that checklist. From the product review's second wave.
- **"Restore previous" on a repeating note brings the note back, not a muddle.** It used
  to travel through the ordinary save, which on a repeating note asks whether you mean
  this day or the series: answering "this day" filed the recovered text as a per-day edit
  — plain text only, so the styling came back stripped, the note itself stayed shortened,
  and the rescue copy was spent anyway under a cheerful "Restored". It writes the note
  directly now, and says plainly that it restores the whole note. From the product
  review's second wave.
- **Changing something the whole series owns no longer asks an impossible question.**
  Tick a checklist item while looking at one day and the app asked whether you meant
  that day or the series — but a per-day edit can only hold text, so "this day" had
  nowhere to put the tick: it wrote a copy of the series' own words over that day,
  dropped the tick, and asked again the next time. It saves to the series now, without
  asking, and still asks whenever the edit is one a single day really can carry. From
  the product review's third pass.
### Testing
- Every fix above carries a regression check born red-under-mutation: the emptiness and
  whitespace checks drive the real gestures (the autosave timer's callee, the
  note-switch flush, Ctrl+S) rather than the writer those gestures guard; the
  single-instance guard's wiring is witnessed end-to-end by a subprocess driver that
  proves _main() consults the lock and honours both answers — deleting the guard used to
  leave every suite green; and the shared content signature has a delegation check that
  fails the day a consumer grows a private field list again.
- **The dropped-event class is closed for every generated POINTER event, not just bare
  clicks.** Tk silently discards any pointer event aimed at a widget with no native
  window; the first sweep converted the 26 bare Button-1 calls and left 48 siblings
  (coordinate clicks, releases, drags, wheel and hover events) on the raw pattern. All
  go through one helper now, which also refuses KEY events loudly — those follow the
  focus, not the window, and the six places that aimed keys without a settled focus got
  the suite's focus discipline instead. One drag stays raw on purpose: its canvas is
  deliberately dead, and the TclError from the corpse is the point.
- The wave that found this round's work: 13 hostile reviewers, three refute-by-default
  verifiers per material finding, and a completeness critic over the whole exchange —
  33 findings survived, and the critic's audit of the wave itself (which findings were
  wrongly refuted, what nobody ran) drove three of the fixes above.

## [0.71.135] — 2026-09-10

*Highlights: the destructive-gesture sweep — every way to delete or overwrite data now has a written verdict, and the one gap it found is closed.*

### Fixed
- **Removing an attachment asks first.** The ✕ next to an attached file deleted the
  stored copy from disk permanently, with no question at all — the one destructive
  gesture living entirely outside the dialog system, which is exactly why every earlier
  confirmation sweep missed it. It now confirms like its siblings: warning glyph, "No"
  pre-selected, Escape backs out. The full sweep that found it — every delete/overwrite
  gesture in the app, each with a verdict (confirms, trash-recoverable, undoable, or
  accepted with a reason) — is recorded in `qa/COVERAGE_LEDGER.md`. From the coverage
  programme's first cycle.

## [0.71.134] — 2026-09-10

*Highlights: the audit's small-findings tier, closed whole — nine classes from the calculator to the backup, each widened to its real edges by an adversarial review before merge.*

### Fixed
- **The calculator answers every impossible expression the same way.** A lone "." raised
  a raw error past the calculator's own error contract, and a 400-digit number (or any
  arithmetic reaching infinity) displayed `inf`. Both return the usual quiet "nothing"
  now. From the code audit.
- **A pasted style ends where its tag ends.** HTML pasted with an inline colour on a
  paragraph, list item or table cell bled that style to the end of the document, and a
  span carrying two styles closed only the first. Every start tag now remembers exactly
  which styles it opened and its end tag closes them all — and a styled `<br>`/`<img>`
  (which never gets an end tag) opens none at all. From the code audit, widened by
  adversarial review.
- **A cell's line breaks survive export → import.** A `<br>` inside a table cell was
  flattened to a space on import while export wrote exactly that `<br>` — every
  round-trip lost the breaks. From the code audit.
- **"Select all" selects exactly what you see.** The note list strips table plumbing
  from bodies before matching the search, but Select-all-visible matched the raw body —
  quietly selecting notes the filter had hidden, which bulk actions then hit. One shared
  predicate now defines "visible" for both. From the code audit.
- **Escape in a nested dropdown closes the list, not the editor.** Backing out of the
  category picker inside the template editor tore down the whole editor. From the code
  audit.
- **A pasted table draws its columns full width.** Markdown's conventional `---`
  separator was honoured as an exact display width, clipping the drawn column under its
  own text. A minimum-width separator now means "no width opinion" — while a
  hand-narrowed column keeps its deliberate ellipsis, and the narrowest drag now
  round-trips as authored. From the code audit, widened by adversarial review. ([the full story](docs/ISSUES_LOG.md#the-clipping-that-turned-out-to-be-a-feature))
- **A backup carries the whole notebook.** Templates and the trash were silently left
  out of the export and never read on import — moving devices lost both. They ride
  along now and merge additively, normalized, deduped, and with imported trash
  attachments given their own files so no purge can reach across. From the code audit,
  widened by adversarial review.
- **A silent save failure leaves a trace.** The autosave spine's guards — including the
  save at note-switch and close, the quietest spot of all — swallowed exceptions with no
  message and no log; a persistent bug there stopped saving invisibly. Every such guard
  now records one trace per spot per session in `crash_log.txt`. From the code audit,
  widened by adversarial review.
- **The theme registry lets its dead go.** Revisiting Settings re-registered its widgets
  on every visit and the registry kept the destroyed ones forever — unbounded growth,
  paid for on every theme switch. It prunes first now. From the code audit.

## [0.71.125] — 2026-09-10

*Highlights: six audit-found medium classes, each fixed and then widened to every sibling an adversarial review could find — the caret stays visible across theme switches, a failed save is never silent, backups export atomically and closing waits for them, restored tables draw themselves, and emoji stop shifting clicks, cells and find highlights.*

### Fixed
- **Restoring a previous version draws what it restores — and a dead table can't haunt a
  fresh note.** Restore was the one body-loader that skipped the redraw, so a restored
  table came back as raw pipe rows and the word count kept describing the replaced text.
  The review then proved the wider class live: after opening a table note, "New note"
  left a dead table's bookmark behind, and the caret guard walked the fresh note's caret
  to its end on the next keystroke. A grid whose drawing is gone now answers no queries
  at all. From the code audit, widened by adversarial review. ([the full story](docs/ISSUES_LOG.md#the-table-that-outlived-its-own-deletion))
- **Deleting a table no longer yanks the page.** Table delete was the one grid operation
  that never snapshotted the view before tearing down, so the redraw faithfully pinned
  the already-jumped scroll position. It now captures first, like its siblings. From the
  code audit.
- **A failed save of the trash, templates or settings is no longer silent.** Those three
  writers dropped the verdict their own writing routine returned — no message, no log,
  nothing. Every failed data-file write now lands in `crash_log.txt` and shows an error
  toast naming the file, whatever route it failed on. From the code audit.
- **A backup export can't destroy the old backup, and closing the app waits for it.**
  The export wrote its zip straight onto the file being replaced, so a mid-write failure
  — or closing the app, which killed the background writer mid-file — destroyed the very
  backup being refreshed. Exports (the single-note file export too) now write beside the
  target and move into place only when whole; closing waits for an in-flight
  export/import; a second Export can't start over a running one; and an imported
  attachment can no longer be left half-copied and then skipped forever. From the code
  audit, widened by adversarial review.
- **Theme switches now reach the colours they used to miss.** The caret went invisible
  after a dark↔light switch (its colour was frozen at build time in every long-lived
  field, the main editor included); dropdown and category borders, the export progress
  bar, recurrence radio wells, checklist checkboxes, press colours on Back to Notes and
  the right-click menus, and the settings buttons' hover all kept the old palette in one
  corner or another. All follow the live theme now. From the code audit, widened by ([the full story](docs/ISSUES_LOG.md#the-safety-net-that-hid-the-missing-mechanism))
  adversarial review.
- **An emoji earlier on the line no longer shifts what you click, tab to, or find.** Tk
  counts an emoji as two index steps while Python counts one, and three places mixed the
  two: double-click selected the wrong word, tabbing into a table cell landed the caret
  and selection one place short per emoji, and find-in-note's highlight swallowed the
  character after a matched emoji. One conversion helper now translates at every
  boundary. From the code audit, widened by adversarial review.

## [0.71.119] — 2026-09-09

*Highlights: three audit-found user-facing safety fixes — every route that copies a note gives the copy its own attachment files, a just-typed emoji no longer crashes sharing or export, and destructive confirmations warn clearly instead of pre-selecting "Yes".*

### Fixed
- **A copy of a note now gets its own attachment files, on every route that copies.** A
  duplicate pointed at the *same* files on disk as the original, so deleting either note —
  or removing an attachment from one of them — deleted the shared file out from under the
  other. The same aliasing hid in two more places the adversarial review swept up: the
  Settings duplicate clean-up merged a removed note's attachment into the survivor by
  reference, so the trashed twin's automatic purge later destroyed the very file the merge
  existed to preserve; and re-importing an overlapping backup could hand an imported note a
  file an existing note already owned. All three routes now give the copy its own fresh
  file. From the code audit. ([the full story](docs/ISSUES_LOG.md#the-duplicate-that-wasnt-a-copy))
- **A just-typed emoji no longer crashes sharing or exporting a note.** An emoji typed into
  a note is held internally as a UTF-16 surrogate pair, and the repair for those only ran
  when *saving to disk* — so building a share code for an unsaved emoji raised an encoding
  error, and exporting such a note to a file (single or bulk) crashed the export the same
  way. Both boundaries now repair surrogates before encoding, so the emoji arrives whole.
  From the code audit. ([the full story](docs/ISSUES_LOG.md#the-mend-that-only-ran-on-the-way-to-disk))
- **Destructive confirmations warn clearly and no longer pre-select "Yes".** Confirm
  dialogs could ask for a warning icon and for "No" to be the pre-selected button — but
  both requests were silently ignored, so the dialog showed the neutral question mark and
  put keyboard focus on "Yes", where a reflexive Enter fired the dangerous action. Both are
  honoured now, and every irreversible confirm uses them: replacing the editor with a
  template, deleting an attachment or a template forever, overwriting a template by name,
  emptying the trash, resetting an edited calendar day, restoring a previous version, and
  opening a risky file. Escape still chooses the safe option; recoverable move-to-trash
  confirms deliberately keep Enter as "proceed". From the code audit. ([the full story](docs/ISSUES_LOG.md#the-safety-request-the-dialog-never-read))

## [0.71.116] — 2026-09-09

*Highlights: undo on lists and tables is whole again — one Ctrl+Z never empties a note or dissolves a table.*

### Fixed
- **Undo on a list no longer wipes the note.** Turning a list on or off, or changing its
  indent, rewrites the whole note body to renumber it (delete everything, reinsert). That
  rewrite wasn't a single undo step, so one Ctrl+Z could take back the reinsert but not the
  delete — leaving the note showing empty. The rewrite is now one undo unit, on every path
  that triggers it. From the code audit. ([the full story](docs/ISSUES_LOG.md#the-undo-that-stopped-halfway-the-sequel-lists-and-the-grid-trio))
- **Editing a list above a table no longer dissolves the table.** The same whole-body
  renumber tore out the drawn table (its cells reverted to raw `| pipe | rows |`) because
  it never redrew the grid afterward. It now redraws any table the body still holds. From
  the code audit.
- **Checkbox and table-grow actions undo in one step.** Toggling a table checkbox, or
  copying a row/column to the end, was a burst of small edits that Ctrl+Z took back
  half-done. Each is now a single undo unit, like every other table operation. From the
  code audit.

## [0.71.113] — 2026-09-09

*Highlights: two audit-found hardening fixes — a hostile share code can't delete files outside the app, and a corrupt repeat interval can't crash it on launch.*

### Fixed
- **A crafted import can no longer reach files outside the app.** A genuine share code
  never carries attachments, but a hand-crafted code — or a backup `.zip` — could include
  one whose `stored_as` was a path like `../../something` or `C:\…`, and the app then
  acted on it: deleting that note forever removed the pointed-at file, and opening the
  attachment could launch — even execute — a file outside its folder (with the "unsafe
  file" warning fooled by a benign-looking display name). Closed on every side: decoding
  a share code keeps only the fields a real one carries, `normalize_note` reduces every
  attachment name to a bare filename at the data choke point (covering the `.zip` route
  too), and both the delete and the open paths now resolve through a guard that refuses
  anything outside the attachments folder and keys the safety warning off the real file.
  From the code audit's high-severity findings, completed under an adversarial security
  review. ([the full story](docs/ISSUES_LOG.md#the-share-code-that-could-delete-your-files))
- **A corrupt repeat interval can no longer crash the app on launch.** A recurrence rule
  whose interval was enormous — from a hand-edited `notes_data.json` or a crafted share
  code — overflowed the date maths and, because the calendar draws itself at startup,
  could stop the app from opening at all. The interval is now clamped to a sane maximum
  (every 1000 days/weeks/months/years — far beyond any real use) at the single point every
  route passes through, so no source of data can bring the app down this way. From the
  code audit's high-severity findings. ([the full story](docs/ISSUES_LOG.md#the-repeat-interval-with-no-ceiling))

## [0.71.111] — 2026-09-09

*Highlights: the calendar gains a searchable History register and the open day wears a frame; occurrence editing and History navigation get their field-reported rough edges smoothed.*

### Added
- **📋 History — the calendar's own register.** A History button on the Calendar tab swaps
  the month grid for a list of every day that carries real content: dated notes at their
  date, and each repeating series as a collapsible group of its separately-edited days
  (✎), newest first and paginated. Its search bar looks where the sidebar's cannot —
  inside each day's own edited content — and auto-opens the group that matched; year chips
  (All / This year / Last year / 2 years ago / Older) cut through the archive, and
  clicking a row lands back on that day's calendar preview, right-click carrying the
  usual day menu. A bounded, small series ("10 times", or ending soon) opens to ALL its
  occurrences — ✎ only on the edited ones — while an unbounded rule lists just its edited
  days with a line saying so, and a series with nothing to unfold wears a → instead of an
  arrow and jumps straight to its day (field feedback: a "10 times" group opening to
  nothing read as broken). Built for the long run: the list grows with what you write,
  never with the passage of time.
- **The open day wears a frame.** Clicking any calendar day (or landing on one from
  History) draws a thin accent border around its cell for as long as its panel is open —
  the "you are here" the eye was missing — and it survives month re-renders. Today's own
  accent top bar is a separate, permanent mark: browsing other days never dims it, and a
  selected today simply wears both (field request).

### Fixed
- **A delete inside History disappears on the spot.** Deleting an entry from the History
  list left it on screen until you went out to the grid and back — the delete redrew the
  grid and day panel but not the History view, a third view of the same data. It now
  refreshes wherever a calendar change is signalled (field report).
- **The calendar always opens on its grid, not on stale History.** Leaving the Calendar
  tab and returning showed whatever History state you left two switches ago; the grid is
  the tab's home and History a view of it, so switching tabs resets to the grid (field
  report).
- **Answering "this occurrence only" now actually takes you back.** A just-saved
  occurrence still read as having unsaved changes — the dirty check compared the series'
  own formatting and checklist against the edited day, and an override's body differs
  from the base's by definition, so the comparison could never match. Back to Calendar's
  cancel guard took that eternal "dirty" for a cancelled prompt and refused to navigate,
  re-asking the same question on every click (field report); the same mechanism also
  double-asked at app close. An occurrence now compares exactly the fields an override
  can carry — title, body, comments, category, colour — and a saved day reads clean.

### Changed
- **The calendar header regrouped around its title.** The month/year arrows now hug
  "September 2026" as one centered cluster, and Today + History moved to the far right
  with History outermost — navigation lives with the title, the register lives at the
  edge (field feedback).
- **History is one labelled toggle, not two buttons.** The single header button reads
  "📋 History" on the grid and "📅 Calendar" while the register is open, each saying where
  the click takes you; the separate in-view "← Calendar" button is gone (field feedback).

## [0.69.108] — 2026-09-07

*Highlights: the calendar's occurrence world becomes visible and navigable — the editor names what it holds, edited days are marked and resettable, and every calendar route keeps the way back.*

### Added
- **The editor says what kind of note it holds.** Opening one day of a repeating note from
  the calendar shows a line above the title — "📅 Editing this day of the series:
  Wednesday, 15 July 2026" — and opening the note normally shows the series line instead:
  "🔁 This note repeats (Every day) — edits here apply to every day · 1 day keeps its own
  edits (✎)". The date field only ever shows the series' start date, and a day edited with
  "only this occurrence" keeps its own content through later series edits — both were
  invisible, and the second read as "my edit skipped a day" (field report).
- **Days that live on their own are marked, and can come back.** A day carrying an
  "only this occurrence" edit now shows a ✎ mark in the calendar's day list and an
  "✎ edited for this day" chip in the preview — and its right-click menu gains
  "↺ Reset this day to the series content", the way back that never existed: dropping the
  day's separate edits (with a confirmation) so it follows the series again.
- **The sidebar filter and sort know calendar notes.** The filter dropdown offers
  🔁 Repeating and 📅 Dated alongside the categories — one judgment shared with bulk
  select-all, so the list and "select all visible" can never disagree about what is
  visible — and the sort dropdown gains **Calendar: soonest**, ranking by the note's NEXT
  relevant date from today: a repeating series by its next occurrence (not its start
  date), upcoming dates before past ones, the freshest past date leading that group,
  undated notes last — a mini-agenda in the sidebar. The filter button also stopped
  truncating its selected value (it read "🔁 R…" — caught in a screenshot).

### Fixed
- **The right-click edit routes keep the "Back to Calendar" button.** Opening a note
  through the calendar's right-click menu (Edit only this occurrence, Edit whole series,
  Open/Edit, Make this repeat) silently skipped the way-back memory that the day panel's
  own Edit button always kept — field-reported as the button having vanished. All calendar
  routes remember the way back now.
- **A dropdown's button now closes its open list.** Clicking the sort/filter/category
  button while its list was open blinked it — the shared click-outside dismiss closed the
  list and the button's handler reopened it in the same breath — so the only way to close
  it was clicking somewhere else (field report). The second click is a real toggle now.
- **"Back to Calendar" saves before it leaves.** Returning with unsaved occurrence edits
  used to render the day panel from the store — the old content, looking exactly like the
  edit had been lost. The button now saves first, asking the occurrence question as part
  of the click, like every other gesture that leaves the editor — and cancelling that
  question keeps you in the editor with the way back intact, instead of navigating anyway.

### Changed
- **"Date (soonest)" is now "Calendar: oldest", the name it always deserved.** The old
  sort was plain chronology by the note's own date — past dates first, a repeating series
  by its start date — which "soonest" never quite promised. Same behaviour, honest name:
  the archive walk. Its promise-keeping sibling is the new "Calendar: soonest" above.
- **A recurring note's calendar menu drops the redundant "Open / Edit".** The two explicit
  entries — only this occurrence, or the whole series — are the entire choice; a generic
  third option beside them was noise (field feedback).
- **Save returns you to the calendar only on the quick-add flow.** When editing an
  existing note opened from a calendar day, Save now stays in the editor: with occurrence
  saves riding on explicit gestures, the old always-return yanked you out on every save.
  The Back to Calendar button is the way back — and a trip that stops making sense ends
  cleanly: deleting a note or restoring a tab clears any pending return, so a later,
  unrelated Save can never teleport you onto a stale calendar day.

## [0.66.105] — 2026-09-07

*Highlights: BackSpace and Delete treat an emoji as one character in every text field.*

### Fixed
- **Deleting half an emoji is no longer possible.** Tk's Entry widget counts text in
  UTF-16 units and its stock BackSpace/Delete removed exactly one — half an astral emoji.
  The torn remnant rendered as a box, and the save's surrogate mend then faithfully turned
  its bytes into question marks after a restart (field-reported: an emoji in the title →
  box → three question marks). All nine free-text fields (the title, both search boxes,
  checklist items, category and template names, the username) now delete the whole
  character, and behave stock everywhere else; the note body, a Text widget, never had
  the problem.

## [0.66.104] — 2026-09-07

*Highlights: every data file saves atomically with surrogates mended, and an unreadable file is preserved and announced instead of silently emptied.*

### Fixed
- **Every data file now saves the way notes_data.json learned to.** trash.json,
  templates.json and settings.json wrote with a bare `open('w')`: an emoji carrying a lone
  surrogate half raised mid-dump and left the file truncated, and a crash mid-write
  truncated it just the same — guards the notes file had earned from real losses, never
  propagated to its siblings. All of them (plus the one-time cleanup rewrite and the
  migration's settings write, the last naive writer standing) now route through one
  atomic writer: surrogates mended, dumped to a sibling `.tmp`, replaced atomically — a
  failed write leaves the previous file intact. From the code audit's high-severity
  findings.
- **An unreadable data file is preserved and announced, never silently emptied.** A corrupt
  notes_data.json used to become an empty notebook without a word — and the very next save
  overwrote the corrupt file, turning recoverable corruption into permanent loss. Every
  loader now copies the unreadable file aside first (`*_corrupt_<timestamp>.json`, kept
  forever, exempt from every cleanup), and for the notebook the startup notice says plainly
  what happened, that the notes did not delete themselves, and where the preserved copy
  sits. The adversarial review of the fix itself then caught the leftovers — a list-shaped
  file of pure junk slipping past the net, the one-time cleanup racing to overwrite the
  corrupt bytes, and the reclaim migration clobbering an unreadable settings file — all
  closed in the same change.

## [0.66.102] — 2026-09-07

*Highlights: autosave is mute now — a background timer never opens a dialog, and every gesture that clears the editor saves first.*

### Fixed
- **Background autosave can no longer interrupt with a dialog.** Editing one day of a
  repeating series, every pause in typing popped the "occurrence or whole series?"
  question from the autosave timer — and one such prompt, stacked under a manual save's
  own, could freeze into a "ghost" save that later mixed another note's colour,
  attachments and checklist into the series. The timer now defers that save to the next
  explicit gesture (Save, a note switch, closing), which asks then — as part of your own
  action; the "Empty note" warning joined the other autosave guards behind the same rule,
  so a comments-only draft no longer warns except from the explicit Save button. Found by
  an adversarial review agent probing the delete fix's neighbourhood, pinned by
  mute-timer checks in qa8.
- **Ctrl+N and the calendar's "Add note for this day" no longer discard unsaved edits.**
  Both gestures cleared the editor without the flush every other route performs, silently
  dropping whatever the half-second autosave debounce hadn't caught yet — and they would
  have dropped a whole deferred occurrence session under the fix above. They flush first
  now, asking the occurrence question when one is pending. Found by the adversarial
  review of this very change, pinned in qa8.

### Testing
- **The delete routes' guard rails close their review gaps.** A three-agent post-merge
  review of the 0.66.100 fix confirmed it whole (no selection borrow remains on any
  route) but found four holes in the new checks themselves: the calendar wrapper carried
  no selection assertions, the store re-anchor had no proof, the editor Delete button's
  confirmed path had no assertion anywhere in the suite, and a scope-prompt mock was
  being "restored" as another mock. qa7 section 6c now drives the wrapper through both
  cancel prompts, proves a stale copy still mutates the store, and pins the confirmed
  editor delete end to end; the mock-hygiene rule joined the qa house rules.

## [0.66.100] — 2026-09-05

*Highlights: a cancelled right-click delete can no longer hand the autosave a wrong target.*

### Fixed
- **A cancelled right-click delete can no longer overwrite a different note.** The context
  menu's Delete aimed the shared delete routine by repointing the editor's selection at the
  right-clicked note; answering No (or cancelling the occurrence-scope prompt) left the
  selection there, so the next autosave silently wrote the open note's content over the
  right-clicked one — no trash entry, no visible sign. The target now travels as a
  parameter and the selection is never touched; the cancel routes are pinned by regression
  checks that fire a real autosave and assert the other note survives bit for bit. Found by
  the code audit, not a field report.

## [0.66.99] — 2026-09-05

*Highlights: a note shared from the editor arrives whole — checklist, formatting and paragraphs included.*

### Fixed
- **The editor's own share code carries everything now.** "Copy code" on the open note built its
  note from a hand-rolled seven-field list, so a code generated there — unlike one from the
  multi-note Share panel, which passes whole notes — silently dropped the formatting, the
  paragraphs and the checklist; and the single-note import loader skipped the checklist even
  when a code carried it (found in a field test: a shared checklist arrived missing at both
  ends). Both ends fixed — the editor's code is now built from the shared field list itself, and
  the import loader brings the checklist along, opening the section so the items are visible —
  and the whole path is pinned end-to-end through the real route: editor state → Copy code → the
  rendered code → the import box → the opened editor.

## [0.66.98] — 2026-09-05

*Highlights: the app speaks English everywhere — and a shared note finally keeps its checklist.*

### Fixed
- **A shared note keeps its checklist.** Share codes carried every piece of a note's content
  except one: the checklist was silently left behind, so a shared packing list arrived as a
  title and a body with the actual list missing. The checklist now travels in the code, done
  states included; older codes without one still decode exactly as before, and codes carrying
  one degrade gracefully in older builds (the import path has always normalized the field).

### Changed
- **The table caption speaks English.** The inserted labels were "Tab. N: descriere" / "Sursa:"
  (the academic convention the feature was first built around, in Romanian); they are now
  "Table N: description" / "Source: " — the app's own functions are English everywhere, and the
  caption stays plain editable text, so what's written after the labels (or instead of them) is
  the user's, in any language. Numbering now counts only caption-shaped lines ("Table 3:"), not
  prose that happens to start with the word — and it still counts the old "Tab. N:" labels, so
  the next caption in an older note carries on instead of restarting at 1.

### Testing
- **Multi-script input, proven through the real routes.** A new qa5 block pushes Arabic, Hebrew,
  Chinese, Japanese, Korean, Devanagari, Cyrillic, Greek and ZWJ-emoji text through the editor
  fields, a table cell, save → reload from disk, find-in-note, a share-code round-trip, the HTML
  export and the sidebar search — asserting the data survives byte-for-byte. The data-level
  half (normalize, share code, export) runs on both CI platforms; the widget routes run on the
  Windows job, the platform the app ships on, because Linux's Xft font stack can segfault Tk
  outright when *rendering* exotic glyph sequences — which says nothing about the shipped
  product (glyph shaping stays the platform's job, eyeballed via the manual test plan). The
  audit that came with it confirmed no validator anywhere restricts input to Latin characters,
  and every file the app opens is explicit UTF-8.

## [0.66.97] — 2026-09-04

*Highlights: keyboard reach — app-wide Ctrl+N and Ctrl+S shortcuts, and an in-note Ctrl+F find bar.*

### Added
- **App-wide keyboard shortcuts: Ctrl+N and Ctrl+S.** New note, and save the current note now —
  bound across the whole app so they work whichever pane has focus, and listed in Settings →
  Keyboard shortcuts under a new "App" group. Ctrl+N switches to the Notes tab first; Ctrl+S stays
  silent when there's nothing to save rather than popping a warning from wherever you pressed it.
- **Find in the current note: Ctrl+F.** A small find bar opens in the editor's top-right — inside
  the app window, not an OS dialog — and searches the note you're in (the left-hand search finds
  *which* note; this finds *within* it), tables included: a match in a cell scrolls the table into
  view and outlines the cell, and a cell's `<br>` line-break reads as a space so a phrase split
  across two lines still matches (separator rows, checkboxes and merge markers are never "words").
  Enter / Shift+Enter step through the matches with a "3/12" count (wrapping around), "Aa" toggles
  case-sensitivity, and Esc or the ✕ closes it. It only ever highlights — the note is never
  changed or marked edited — editing while it's open re-counts on the fly without twitching the
  view, and switching notes or themes keeps up. Reserved earlier when Ctrl+N/Ctrl+S landed; this
  is that bar.

## [0.64.97] — 2026-09-02

*Highlights: the comments box and the calendar preview stop showing tables as raw pipe rows.*

### Fixed
- **Comments keep tables out.** The comments box draws plain text — it has no grid renderer the
  way the body does — so a pasted table only ever showed as raw pipe rows (`| a | b |`), never a
  real table. A paste that carries table rows now drops them, keeps the prose, and says so with a
  brief note; a paste with no table is untouched.
- **The calendar preview is a quick look, not the editor.** A note with a table drew raw pipe rows
  in the calendar day preview, and its comments were dumped inline as if part of the body. The
  preview now shows the note's plain text only and, like the note-list cards, just flags what else
  the note carries (▦ a table, ☑ a checklist, 💬 comments); the full content shows when the note
  is opened in the editor.

## [0.64.95] — 2026-09-02

*Highlights: a tables hardening wave — export, clipboard, Word, undo, search, styling and scroll
all learn to treat a table as a table — alongside a Windows CI leg and a mutation audit of the old
regression checks.*

### Added
- **The checklist box matches the calculator, and expands.** It now opens at the calculator's size
  (measured at runtime rather than hard-coded, so the two stay equal on any machine's font
  metrics), and the same full-width **Expand** bar the note body and comments boxes use grows it to
  the calculator-with-history size when a list runs long. The scrollbar stays in both states — the
  expand is extra reach, not a replacement — and the expanded size resets to compact on a note
  switch, a per-view choice rather than saved note content. The redundant in-panel "Close" buttons
  were dropped from both boxes, since their header bars already toggle them shut.
- **A system-managed table caption.** Table menu → **Table → Add caption below…** inserts a
  centred, auto-numbered label line ("Tab. N: descriere" — *Table N: description*, the placeholder
  pre-selected so typing replaces it) plus a "Sursa:" (*Source*) line for as many sources or links
  as needed — the literal labels the app inserts, following the academic table-caption convention
  it was built for, as ordinary body text after that, editable like anything else. Nobody has to hand-build a caption and fight its
  alignment again.
- **The table menu got shelves.** The flat run had grown past fifteen entries ("finding the one you
  need takes minutes"). The everyday cell actions stay on top; Align cell, Rows, Columns, Merge and
  Table each hold their own group one hover away.
- **Autofit for a whole selection.** "Autofit column width(s)" joined the cell-selection menu,
  sizing every selected column in one pass — it existed only on the single-cell menu before.
- **Copied cells arrive in Word as a table.** The cell copy now puts an HTML table on the clipboard
  beside the spreadsheet text, so pasting into Word, mail or any rich editor lands a real table
  instead of one line of raw tabs.
- **Export notes as files.** Right-click a note → **Export as file** (or tick several in Select
  mode and use **Export ▾**) saves a standalone **HTML** page carrying everything the note has —
  styles, colours, highlights, the checklist, tables as real tables with real line breaks, kept
  centring and full-cell highlights — or **plain text**; wide tables wrap inside the page instead
  of running off it. The page opens in any browser (Ctrl+P → PDF, highlights kept — the export
  tells the browser to print backgrounds) and directly in Word (the title is a styled line, not a
  heading, so no collapsible outline); bulk export writes one file per note, suffixing same-titled
  notes "(2)" rather than overwriting, and after a save the app offers to open the result — the
  file itself is the only honest preview. A Markdown export was built, measured against these two,
  and removed before shipping: everything it could say, the HTML says with the colours on.

### Fixed
- **A copied table is no longer an invisible phantom in Word.** A clipboard fragment travels
  without the stylesheet the file export draws its borders from, so Word painted a bare HTML table
  with no borders at all — there but invisible, selectable only as "nothing", and inserting it
  rebuilt one row at a time. Copied cells (and a
  table copied as body text) now carry their borders as inline styles on every cell, so the table
  arrives drawn in Word, mail, anywhere; verified end-to-end against real Word via COM — visible
  single-line borders, the right shape, header bold.
- **Checkboxes stay centred everywhere.** The app draws every checkbox centred in its cell; the
  export left it to the cell's alignment, so a box in a left-aligned column sat left in the HTML,
  the PDF and Word. A checkbox cell now carries `text-align:center` in every exported flavour,
  matching what the app shows.
- **Ctrl+Z understands tables.** A cell commit, a resize, a fill or a checkbox drop is a burst of
  small inserts and deletes, and Tk's undo treated every one as its own step — undoing a cell edit
  could stop halfway, the old value gone and the padding collapsed (`|  | 2 |` in the audit's
  probe). Every table operation now forms one undo unit, the grid redraw stays off the undo stack
  entirely (recorded, every second Ctrl+Z undid the redraw instead of the edit), and undo/redo on
  the body redraws the tables the restored text describes — one Ctrl+Z takes back one whole
  operation, drawing included. ([the full story](docs/ISSUES_LOG.md#the-undo-that-stopped-halfway))
- **A one-column table can no longer be asked for.** `| x |` is indistinguishable from prose
  containing a pipe, so a one-column insert produced dead pipe lines that never became a grid. The
  size picker starts at two columns and the insert clamps to two.
- **The word count counts words, not plumbing.** Every pipe counted as a "word" — an empty 3×3
  table claimed twelve and inflated the reading estimate. Tables are now counted by what is written
  in their cells; checkboxes, merge markers, separators and pipes count for nothing.
- **Search reads tables the way you do.** Searching "---" or "br" matched every note holding a
  table, because the raw pipe text was the haystack. A body is now searched by its prose and cell
  contents; the mechanics are invisible to search too.
- **A hidden column stays hidden in the export.** The exported page used to show the column the app
  was hiding. What you see is what exports — the data never leaves the note's text, so unhiding
  brings it back into the next export — and a merge reaching across a hidden column narrows to the
  columns the page shows.
- **Checkboxes export as boxes.** `[x]` went out as bracket characters; the file now shows ☑/☐
  (with the checkbox's colour), and a re-import turns the glyphs back into real checkboxes — the
  round trip keeps them clickable.
- **The clipboard copy caught up with the file export.** Copied cells went to Word with a flattened
  header, literal `<`/`^` merge markers and bracket checkboxes. The copy's HTML now wears `<th>`,
  real colspan/rowspan cells and the checkbox glyphs, and leaves hidden columns out — while the
  tab-separated text keeps every column verbatim, so a duplicate inside the app stays faithful and
  a spreadsheet still gets all the data.
- **Our own table copy takes its own road home.** The cell copy puts an HTML table on the clipboard
  for Word's sake — and on Windows the rich-paste route saw that HTML first, so pasting a copied
  table back into a note bypassed the table route's own fixes on the shipping platform: no
  remembered widths, no placement, the first row glued onto the caret's line ("`Sursa: | fff |…`"
  in the field report). A paste whose plain text matches our own cell copy now goes straight to the
  table route with all its guards; content from other applications keeps the rich route. The qa
  clipboard stub gained a loopback mode that serves back exactly what the app wrote — the Windows
  behaviour the suite never exercised, which is how this shipped unseen.
- **The header row is bold in Word and the browser too.** The app draws the first table row bold on
  its own; the export flattened it into an ordinary row. Header cells now leave as `<th>` — bolded
  by every renderer, kept left-aligned like the app's own headers, and re-imported unchanged (the
  paste path always understood both).
- **A duplicated centred table pastes back centred.** The table's place on the page now travels
  with the copied cells, like the widths already did.
- **Dropping a checkbox no longer flickers the table.** It centred the cell through the full
  teardown-and-rebuild alignment op; the box now lands with the cell's own alignment, redrawn in
  place — the same quiet path a toggle uses.
- **The scroll stays put through cell edits.** Double-clicking into a table (or dropping a checkbox
  on a coloured cell) could throw the view to the table's start: the after-rebuild view restore ran
  once, at idle, and fresh grid windows mapping after it left the fraction landing against the
  wrong heights. For the operations that promise the view stays put (the menu-op family and the
  editor's commit) the restore now holds in force briefly on short timers — a deliberate wheel,
  scrollbar or drag-autoscroll move cancels it — while ambient renders (a push-down, an inserted
  table) deliberately keep the single application, because their content legitimately moves.
- **Pipe rows pasted mid-line land on their own lines.** Copying half a table plus its caption as
  body text and pasting it inside a line spliced the first row onto the caret's line
  ("`|   | [x] |fig2…`"). Table rows only mean something at a line start, so the paste now gives
  the edge rows the newlines that keep them rows — prose keeps Tk's default paste.
- **A duplicated table keeps its widths.** Pasting copied cells rebuilt the table at default column
  widths; the copy now remembers the source columns' set widths and the paste rebuilds the
  separator from them.
- **Letters glued onto a styled word wear its styles.** Tk extends a tag over an inserted character
  only when both neighbours carry it, so typing at the end of a coloured word produced bare
  letters. A non-space character typed directly after a styled non-space character now inherits its
  colour, highlight and font styles — type a space first and the styles stay behind, the word
  boundary the report asked for.
- **The checkbox palette went surgical.** It filled cells through the wholesale block rewrite,
  which expelled the caret to the line under the table and scrolled the view after it — an emoji
  never moved anything, because it goes through surgical paths. The checkbox now writes each cell
  in place and centres via pad edits; caret, scroll and every untouched line stay exactly where
  they were.
- **Resizing a table no longer burns its styles.** Dragging a column edge went through the
  wholesale block rewrite meant for structural reshaping, and every colour, highlight and bold in
  the table died for an operation that moves no text at all — width lives in the separator line
  alone, which is now the only line written. Dragging a row's height likewise kept re-writing the
  padded cell's whole value; the cell write now edits only the differing middle, so the styled text
  it pads around keeps its tags.
  ([the full story](docs/ISSUES_LOG.md#the-accepted-cost-that-nobody-had-accepted))
- **Typing on a centred line keeps it centred.** Tk justifies a line by the tag on its first
  character, and a typed character lands untagged — typing at the start of a centred line yanked it
  left, and the first character in an empty centred line lost the centring outright (deleting the
  text snapped the cursor back to the middle, because the line's newline remembered the tag all
  along — the field report's exact riddle). The caret's line now re-dresses itself in its own
  alignment on every keystroke.
- **A cell's highlight became cell-deep.** Colour an empty cell, type into it, drag a column — the
  colour used to die at the commit (logically at once, visibly at the next rebuild). A cell-level
  highlight now lives across the whole pipe-to-pipe region, so everything later inserted into the
  cell — typed text, the pad spaces a re-align shuffles, a checkbox — lands inside the tag and
  inherits it; the commit re-asserts it, and the checkbox palette (whose fill rewrites the block)
  snapshots and re-dresses every coloured cell.
- **Duplicating a table works.** Copying cells puts spreadsheet-style tab-separated lines on the
  clipboard, but pasting them below the table fell through to the plain-text path — raw tabs,
  stored `<br>` markers showing as text ("nothing happens or `<br> <br>` appears"). Tab-separated
  clipboard text pasted into the body now becomes a real table — one blank line kept between it and
  any table above, single cells (no tab) still paste as plain text — and the same shape arriving
  from a real spreadsheet lands as a grid too.
- **The cell editor wears its cell.** Editing a highlighted cell showed the highlight only where
  text lines carried it — the editor's empty area below showed the theme through ("half the cell's
  colour gone"), and an empty highlighted cell went bare the moment typing started, colour
  returning only on leaving. The editor now opens on the same blended background the cell draws,
  full and empty alike.

### Testing
- **CI's three static gates now run locally, in two seconds.** `tools/pre_push_check.py` bundles
  them — names resolve, class surface unchanged, every tracked `.py` compiles, tests included —
  after two pull requests went red learning why this should exist. `qa/README.md` now carries the
  suite's **seam map** — which files guard which UI surface (the bulk bar's qa1+qa7 split taught
  this) — plus the house rules for new checks: land with the feature, mutation-tested,
  platform-aimed, settled not raced.
- **CI now runs the entire suite on Windows too** — the platform the app actually ships on (real
  Segoe UI metrics, Windows Tk, no virtual display) — alongside the Linux run that keeps exercising
  the pure logic and the X11 behaviours that have caught real bugs. One matrix, one set of steps,
  both verdicts always visible (`fail-fast: false`); the handful of checks that measure
  Windows-specific pixels now assert in CI instead of only on a developer's machine — a failing
  check is fixed in the app, never routed around. Found and closed on the way: `test_richtext.py`
  was never wired into CI at all, and its first flight promptly caught the push-down settling flake
  fixed alongside it — the new runner earning its keep in its first five minutes.
- **The old teeth, audited.** Six long-standing regression fixes were sabotaged on purpose (each
  mutant = the original bug from ISSUES_LOG, reintroduced) to prove their guarding checks can
  actually fail: four bit immediately, two had gone dull — nothing pinned the startup purge
  deleting a purged note's attachment files, and nothing pinned the editor's 0.32.x "short content
  stays at the top" guard. Both have named, deterministic checks now, proven against the same
  mutants; the autosave-over-a-vanished-note guard additionally gained a named check, so a
  regression fails with a message instead of hanging the suite in a modal dialog.
  ([the full story](docs/ISSUES_LOG.md#the-teeth-that-had-gone-dull))

---

## [0.58.82] — 2026-08-30

*Highlights: Scroll-position stability for the note list, plus new backup, trash and shortcut settings.*

### Added
- **The Backup panel says when the notes last left the computer.** The app is offline by design,
  so an export is the only copy of the notes outside its own folder — and until now nothing said
  when that copy was last made. A line under the Export button shows the date and time of the
  last successful export ("Never exported from this computer." before the first one); a failed
  export leaves the stamp untouched.
- **Trash retention is a real setting.** The 30-day window was a hard-coded constant; the Trash
  panel now opens with a **Keep deleted notes for** selector (7–90 days), and the startup purge,
  the days-left column, and every "restorable for N days" message quote the chosen window. A
  hand-edited settings file saying `0`, `"forever"`, or anything else unusable reads as the
  default — a nonsense value must never make startup purge everything.
- **A keyboard-shortcut reference in Settings.** Thirteen combos were bound and only the
  formatting four were discoverable (via the right-click menu). Settings → Keyboard shortcuts
  lists every one of them, grouped and verified against the actual bindings: formatting,
  clipboard, undo/redo, table navigation, and the calendar keys (which act only while that tab
  is showing).

### Changed
- **Deleting a template says it skips the Trash.** The confirmation now reads "Templates don't
  go to the Trash — this can't be undone." instead of a bare "Delete?" that read like every
  other, safely undoable delete.

### Fixed
- **The note list stopped losing its place.** Both long-standing "known bugs to investigate"
  traced to one root, measured rather than guessed: a rebuilt list's geometry settles over
  several event-loop passes (one collapse reported heights 106 → 276 → 820), each intermediate,
  too-small scroll area re-clamping the canvas — while a rebuild that only *shrinks* the list
  fired no event at all, parking the view past the real content as a blank list. The list now
  carries the editor page's protections from `0.32.x`, hardened for both shapes: content that
  fits pins to the top, an origin above the first card snaps back, and a full rebuild (autosave
  included) remembers its scroll position in pixels and holds that restore *in force* briefly —
  re-applied when a late settling pass tries to re-clamp, and on short timers for the silent
  shrink case — so saving and expanding keep your place, and collapsing a group from below lands
  at the end of the shorter list instead of blank space. A deliberate wheel or scrollbar move
  during that brief window wins over the restore, always.
  ([the full story](docs/ISSUES_LOG.md#the-list-that-lost-its-place-twice-for-two-silent-reasons))

### Testing
- **The menu-op scroll check now measures the settled body view.** It used to race a fixed three
  pumps against X11's asynchronous window mapping — one CI run caught a mid-reflow 0.172 where
  the settled state sits at ~0.07, under the 0.1 threshold. Settling never rescues a broken
  build (verified by mutation: with the restore removed the view stays shifted 0.15+ and the
  check still fails).

---

## [0.55.81] — 2026-08-30

*Highlights: Tables grow up — per-character styling, multi-line cells, real checkboxes,
draggable rows — while the template editor learns to draw them and the GUI tests become hermetic.*

### Added
- **The template editor shows its tables AS tables.** A live, read-only preview under the body box
  draws every table and every row in the editor's own visual language — bold header, hairline
  rules, the separator row's hand-set widths honoured, hidden columns as slivers, merged cells
  drawn as one spanned cell — with scrollbars both ways once it outgrows the dialog. The body box
  shows only the note's plain text, its table lines hidden from display, while still holding the
  full body underneath, because the text is the store.
- **The template editor closes on a click elsewhere, like any dropdown.** Typed work is never lost
  silently: if something was changed, a small ask decides whether the change is saved first; an
  unchanged dialog just closes, no ceremony. Escape goes through the same question.
- **A note that begins with a table has somewhere to type above it now.** Clicking beside the
  table and pressing Enter pushes the table down a line and puts the cursor on the fresh first
  line. Between two adjacent tables the key keeps its old meaning.
- **"Add a line above the table" on the table's right-click menu.** The same move as the Enter
  gesture, for anyone who would never guess it — on any table, not just one being clicked beside.
- **A note's card says what a table cannot show at that size.** The preview line skips the table's
  raw `| pipe |` rows and shows only the note's plain text, and the card's tag row notes
  **▦ 1 table** (or how many there are) alongside the attachment and comment marks.
- **An empty table cell can be highlighted now.** The color rides on the cell's padding — the only
  style with something to show on nothing — and text typed into the cell later lands inside the
  colored region and keeps it.
- **Multi-line table cells.** Enter (or Shift+Enter) inside a cell starts a new line *in the
  cell* — the whole row grows to fit — instead of dumping the cursor under the table. The break is
  stored as Markdown's own `<br>`, so a multi-line cell survives share codes, backups, export, and
  any Markdown-aware tool unchanged; the template preview draws the lines as lines too. Leaving
  the cell is what it always was elsewhere: Tab, Escape, or a click somewhere else.
- **Styling inside a cell, character by character.** A drawn cell used to paint itself one style
  whole — colouring a single letter or emoji coloured everything. Cells now draw their text as
  runs, each with its own bold, italics, and colour, so one green checkmark next to plain text
  shows exactly as itself. With a cell open, the toolbar styles just the selection inside it; with
  cells merely selected, it still styles them whole.
- **The open cell shows its colours.** Editing a coloured cell used to show plain black text until
  the edit was committed. The floating editor is a real rich-text box now: it opens wearing the
  cell's colours, bold and highlights, keeps them while typing, and hands them back on commit.
- **Typing continues the style it lands beside.** Adding to a blue word in a cell used to come out
  plain — Tk only carries a style onto a typed character when both its neighbours wear it — and
  retyping over the select-all a click opens with wiped a coloured cell to plain ink. Typed
  characters now dress themselves in the style of what they land beside (or of what they replace),
  so a coloured cell stays coloured through ordinary editing.
- **An active colour you can see.** Picking a colour with nothing selected makes it the active
  one: the toolbar button wears it as a swatch — the same in a table cell as in the note body —
  and everything typed next comes out in that colour until it is switched or clicked off. The body
  half of this existed; a cell used to swallow the choice as an instant whole-cell repaint, so the
  swatch never showed and typing stayed plain.
- **Rows drag taller and shorter.** The rule between two rows drags up and down the way the one
  between columns always dragged sideways — the whole row resizes together, stored as empty
  in-cell lines so nothing about the table's format changes, and a drag can never cut into text a
  cell actually holds. Pressing Enter in a cell also grows the row on screen immediately, so the
  floating editor no longer hides the row below while you type. Ctrl+A selects the whole cell, and
  fast typing can no longer outrun the colour it should be wearing — every character gets dressed
  the moment it lands.
- **A light/dark switch in the editor.** The end of the formatting toolbar carries a small ☀ / 🌙
  button: one press flips between the last light and last dark theme without leaving the note. The
  full theme picker stays in Settings.
- **Checkboxes in cells are real checkboxes now.** The checkmark was a text character — you could
  type next to it, delete it by accident, and never simply *click* it. A cell now holds an actual
  little box: click ticks it, click again unticks it (a fast second click counts too), the palette
  colours it, dragging selects its cell whole for highlighting, and the text editor never opens on
  it by accident. It is stored as Markdown's own task syntax — `[ ]` and `[x]` — so export, share
  codes, and any Markdown tool read it natively; right-click → Edit cell as text turns it back
  into an ordinary cell.
- **Rows copy to the bottom, and drag-selection follows the pointer.** "Copy columns to the end"
  gained its vertical twin: select whole rows and copy them again to the table's bottom, text and
  all. Drag-selecting now auto-scrolls — hold the drag at the grid's edge and it pans sideways,
  hold it past the note's bottom (or top) and the note scrolls, fluidly, with the pointer — so a
  selection can reach every column of a wide table and every row of a tall one, which simply could
  not be done before.
- **A single table cell can be selected at last.** A firm drag that stays inside one cell selects
  that cell whole — selection used to begin only when the drag reached a neighbour, so grabbing
  one cell always grabbed two. A short click still opens the cell for editing.

### Fixed
- **The save-changes question no longer hides behind the popup it is about.** A themed ask could
  render under a `-topmost` popup, unreachable. Popups now step back for a dialog's duration and
  return after; the same fix surfaces the "Name needed" warning.
- **The template body no longer shows gaps where its hidden tables live.** Blank lines glued to a
  hidden table now hide with it, so the remaining text reads compactly; a blank line between two
  runs of text is left alone.
- **Editing a template through Settings no longer wipes its formatting.** The dialog cannot edit
  the formatting and paragraph data a template saved from the editor carries — but it no longer
  loses them either.
- **Empty template names are caught again.** The "Name needed" guard was unreachable — an empty
  name was defaulted to "Untitled template" before the check ran, so empty saves slipped through
  silently; the junk rows named exactly that were its proof. The guard now checks the raw field.
- **Tables paste as tables into the template editor.** Pasting from Excel, Word, or a web page
  used to drop the structure and keep only the words — the body box is a plain text field with the
  system's plain paste. When the clipboard's HTML holds a table, the same converter the main
  editor trusts now turns it into the note's own table text, from any source that carries real
  structure (a PDF does not, by decision).
- **Popups no longer follow you to the next page.** A popup opened on one page — a Settings
  dropdown, say — kept floating over the next page after switching. Entering Settings, Back to
  Notes, and Notes/Calendar tab changes now dismiss whatever popup the previous page left open.
- **The app's popups no longer float over OTHER programs.** They are deliberately kept on top so
  the app's own focus changes cannot bury them, and that flag cannot tell the app's windows from
  someone else's. They now hide while another program holds the front and come back with the
  app — never destroyed, because a half-typed template dialog must survive a trip to the browser
  and back; that round trip is exactly what it is for. The decision asks Windows directly which
  window is in front, on a light heartbeat: a popup holding keyboard focus receives no
  deactivation event at all, so events alone missed exactly the case where the user had typed into
  a dialog before switching away.
- **A template holding a table applies as a drawn grid now, not raw pipe rows.** The template path
  filled the editor and never rendered, while the import path already did. Found by the new
  automated check that carries a table through a template, written the same day.
- **The mouse wheel glides over tables instead of leaping.** A drawn table is one text line as
  tall as the whole grid, and the wheel scrolled in lines; it scrolls in pixels now, over tables
  and text alike. The first version of this fix was dead code for real mouse wheels — it sat on a
  direct binding a later line silently replaced (Tk's `bind()` without `add` overwrites) while the
  automated checks, calling the handler directly, stayed green; field testing caught it. The pixel
  scrolling now lives in the one real wheel handler, and the checks drive genuine wheel events
  through the binding chain so an overwrite like this can never pass again.
  ([the full story](docs/ISSUES_LOG.md#the-fix-that-was-dead-on-arrival))
- **Pasting a long text no longer leaves the view behind.** The freshly pasted end sat below the
  fold and the scrollbar read as having jumped away. After a paste — plain, formatted, or via
  Ctrl+Shift+V — the note now scrolls to where the pasted text ends, the way every editor does.
- **Quitting no longer asks about "unsaved notes" in an app that autosaves everything.** The
  question could only ever cover the last half-second of typing, so closing now saves whatever is
  still pending, silently, exactly like switching notes always has. Along the way a real gap
  closed: a brand-new note holding only comments never autosaved at all.
- **One highlight palette everywhere.** The table's right-click palette showed flat full-width
  swatches parted by one-pixel hairlines in the theme's own color, while the toolbar button and
  the text right-click menu opened an older grid of small squares. The hairline column is now the
  one highlight palette, built from a single shared piece so the looks cannot drift apart again.
- **A highlight on normal text no longer buries the words under it.** Plain text painted the
  palette color at full strength while the same color on a table cell showed as a soft translucent
  wash. The text ink now uses the cells' own recipe — the swatch color blended toward the page
  surface, re-blended when the theme changes — while the stored data still carries the pure color,
  so nothing about saving, sharing, or export moves.
- **Typing in a table-only template body can no longer destroy the table.** A click in a body that
  looks empty landed the cursor inside the hidden table text: typing glued letters onto an
  invisible pipe row — the row stopped being a table row, the preview broke, and the block's
  leftovers surfaced as bare pipe lines — while Backspace and Delete at the hidden text's edge
  quietly ate it, and the preview refresh yanked the cursor to the end after every keystroke. The
  cursor is now herded to visible text before a character can land, deletions refuse to touch the
  hidden table, the hide-tag no longer swallows the text's final newline (typing at the end used
  to inherit invisibility from it), the cursor stays where the user is typing, and a preview
  drawing failure is contained instead of leaving a half-updated dialog.
- **An Enter that pushes a leading table down no longer disturbs a mid-note scroll.** Measurement
  showed a view-restore against the fresh grid's estimated heights yanked the view several lines
  up, while doing nothing extra keeps the reader exactly where they were — so the code now
  deliberately does nothing extra, and a check pins that.
- **No more phantom "Note updated" on every launch — and it was not just cosmetic.** Saving read
  formatting positions back in UTF-16 units (an emoji counts as two) while applying them counted
  characters (an emoji counts as one), so any formatted note holding an emoji read as "changed"
  the moment it loaded: the startup autosave rewrote it, and the stored span crept one character
  further from its text on every single launch — silent, cumulative data damage dressed up as a
  friendly toast, and the same phantom difference made quitting ask about "unsaved notes" nothing
  had touched. Extraction now counts the exact same characters the saved note stores; opening the
  app touches nothing and says nothing, all pinned by checks that a deliberate re-break of either
  half makes fail. ([the full story](docs/ISSUES_LOG.md#the-version-that-updated-itself))
- **Aligning a table cell no longer throws away its styling.** Centering or right/left-aligning
  went through the wholesale block rewrite, whose accepted cost is dropping character styles — a
  fair price for reshaping columns, and entirely the wrong tool for what is really a padding
  change. Alignment now edits only the spaces, through the same surgical operations the column
  aligner already used precisely because Tk keeps a tag attached to the text around it — so bold,
  color, and highlight stay put, in the aligned cell and its neighbours alike.
- **Saving a template under an existing name asks before replacing.** Both roads used to silently
  overwrite the old template — different content, same name, gone without a word. They now ask
  "You already have a template named X. Replace the old template with this one?" — No keeps both
  and leaves the name box open for a different name. The Settings dialog had the same hole from
  the other side: renaming a template onto a neighbour's name quietly produced two templates with
  one name; it asks the same question now.
- **Colouring plain text works again after any visit to a table.** A cell selection left over from
  an earlier drag kept catching the toolbar's colour, so the body selection got nothing and no
  pending colour was ever set. Clicking into the note body now releases the table's cell
  selection, the way any spreadsheet lets go when you click elsewhere.
- **The intermittent "something went wrong" while flipping themes from Settings is fixed.** A
  theme switch rebuilds the settings widgets, and a click that still named a destroyed widget
  reached the focus-clearing handler as a bare string, which crashed it. The handler now checks it
  was handed a real widget.

### Testing
- **The GUI tests now run in a world of their own.** Each starts beside an empty data folder, and
  the app's own first-run migration then helpfully adopted the REAL notebook from `%APPDATA%` —
  the owner's actual notes leaked into every scenario, and checks passed or failed depending on
  what she had done in the app that day. Every qa script now seeds an empty notebook and the
  migration marker before the app is even imported, making runs hermetic; run beside a folder
  holding real notes, the script refuses to start at all rather than seed over them. Going
  hermetic surfaced two latent test bugs — a check that grabbed "the first Entry on the page" (a
  different widget on a fresh install) and one that replaced the app's username variable with its
  own copy, detached from the field it meant to type into — both fixed; this contamination is also
  the strongest suspect yet for the suite's rare unexplained flake.
  ([the full story](docs/ISSUES_LOG.md#the-tests-that-borrowed-the-notebook))

---

## [0.39.64] — 2026-08-28

*Highlights: One fix — the app now calls itself Note Organizer everywhere, matching its docs.*

### Fixed
- **The app agrees on its own name.** The window title, the crash dialog, the setup-complete
  message, and the share-code and backup error texts all said "Notes Organizer", while the
  README, the User Guide and every other document say "Note Organizer" — a mismatch a reviewer
  comparing a screenshot against the docs saw immediately. It is **Note Organizer** everywhere
  now.

---

## [0.39.63] — 2026-08-28

*Highlights: Tables arrive as Markdown-backed grids, with cross-feature checks guarding the seams.*

### Added
- **Tables.** A note can hold spreadsheet-style tables: drawn as a real grid with cell borders
  and a bold header row, edited through one floating entry box over whichever cell is clicked
  (cells are drawings, not widgets — which is what lets a large table scroll without stutter).
  Tab moves between cells and adds a row at the last one; drag selects a block; Delete clears a
  selection; Ctrl+C/Ctrl+V copy and paste blocks of cells in their true shape, in and out of the
  app — a table pasted from Excel, Word or a web page becomes a grid, cells copied from a web
  table land side by side the way they were on the page, and cells copied out arrive in Excel as
  cells. Cells merge (their texts join) and split; rows and columns insert, delete, and
  duplicate to the table's end with their content. Columns resize by dragging the rule between
  them (double-click autofits; narrowing below the content only shortens the drawing, with an
  `…` — the text is never cut), and a column selected top-to-bottom can be hidden to a sliver
  and brought back. The formatting toolbar works inside tables — bold, italic, colors, and a
  highlight palette parted by theme-colored hairlines — the alignment buttons align cell text,
  and the table itself can sit left, centred or right on the page from its right-click menu.
  Underneath it all, a table is stored as plain readable text in Markdown's own table syntax
  (the `|---|:---:|` separator row carries each column's width, alignment and hiding), so search
  finds words in cells, share codes, backups and export carry tables unchanged, and a table
  travels both ways between this app and any Markdown-aware tool.

### Changed
- **The table engine is pure core code.** It lives in `noteorganizer/core/tables.py` — text-in,
  text-out functions with no tkinter import, the same core/UI split as the rest of the package.
  Emoji survive the whole path: Tk widgets count text in UTF-16 units while Python counts
  characters, and every surgical edit now converts between the two — a malformed
  half-of-an-emoji can no longer take down a save.
  ([the full story](docs/ISSUES_LOG.md#the-emoji-that-multiplied-into-squares))

### Fixed
- **Shared notes keep their paragraph formatting.** Share codes never carried the paragraph
  data, so a shared note arrived flush left, its list indentation and line alignment flattened —
  silently, ever since paragraph formatting shipped. The field travels now (a table's place on
  the page rides along with it), and codes made before the change still decode.
- **A formatting-only change autosaves now.** Realigning a line without editing its text never
  triggered the autosave — the dirty comparison checked the title, body, character formatting
  and everything else, but not the paragraphs — so leaving the note quietly lost the change
  unless Save was pressed by hand.
  ([the full story](docs/ISSUES_LOG.md#the-centring-that-would-not-save-itself))
- **The interface's last two Romanian strings are gone.** The two editor-height toggles now say
  **Expand** and **Collapse** — what the User Guide already called them, so the app and its own
  manual agree again.
- **List renumbering can no longer misplace formatting.** It applied its formatting shifts one
  at a time, comparing each shift's position against text it had already moved — so a later
  shift could count as "before" a span it had itself pushed past. In a list it happened never to
  show; the shared helper was corrected once, for every caller.

### Testing
- **A standing cross-feature rule, written into the project's working instructions.** A change
  is done when the *older* features still work with it, with a qa check on every risky seam. The
  first audit under the rule found and fixed two holes — a theme switched mid-typing destroyed
  the cell editor under the keystrokes, and the share-code gap above.
- **The data-safety test refuses to run beside real notes.** `test_data_safety.py` deletes and
  rewrites `notes_data.json` as part of testing the backup layer, and run from the project root
  it once destroyed the real notebook (recovered from the app's own automatic backup). It now
  refuses to start beside a `notes_data.json` that holds real notes; the QA-safety rule covers
  every test file, with no per-file judgment calls.
  ([the full story](docs/ISSUES_LOG.md#the-safety-test-that-needed-its-own-safety))
- **The table work landed with its checks throughout.** Over eighty new qa1 assertions and a
  dozen unit tests, each round mutation-tested — every new check was made to fail by
  deliberately re-breaking the code it guards, and checks that could not fail were sharpened or
  removed.

---

## [0.38.59] — 2026-08-26

*Highlights: The editor's text boxes get their width back, and PDF paste builds real paragraphs.*

### Fixed
- **Both editor text boxes now use the window's full width.** They were stuck at eighty
  characters — the body measured 752px inside a 1027px frame, the comments box 672px — because
  the Expand toggle's `pack_configure(expand=False)` on a `side="left"` box gives away
  horizontal space rather than the height it was meant to control. The height comes from the
  frame around the box, so removing the line costs nothing; the body inherited the bug in
  `0.38.56`, the comments box had it far longer.
  ([the full story](docs/ISSUES_LOG.md#the-text-box-that-was-always-eighty-characters-wide))
- **Pasting from a PDF now produces real paragraphs.** A PDF has lines placed on a page, not
  paragraphs, so pasted text arrived either narrow and ragged (breaks kept) or as one run-on
  block (Ctrl+V dropped every break, since HTML treats a newline as whitespace). Both paste
  paths now rejoin the lines a column broke — judging each break by whether the next line's
  first word would have fitted, by sentence punctuation, and by indentation where the document
  offers it — while a line falling well short of the column still ends a paragraph, which is
  how a heading keeps its own line. Lists, addresses, poems and anything under three lines are
  left exactly as they came: a break someone meant is worse to lose than a break left in.
  ([the full story](docs/ISSUES_LOG.md#the-paragraphs-a-pdf-does-not-have))
- **Numbered lists skip the blank lines between items.** Numbering a spaced-out selection used
  to count the empty lines too, reading 1, 3, 5 — and a single blank line ended the run, so it
  could also read 1, 1, 1. Blank lines are no longer numbered and no longer end the run; two
  blank lines still do, which is how a genuinely new list is told apart from a spaced-out one.

### Testing
- **The PDF rejoining is checked by property, not by result.** At eight column widths, indented
  and not, no word is ever lost or altered and no paragraph is ever split in two. Merging two
  paragraphs remains possible and is asserted as a known limit rather than hidden: without
  indentation, a paragraph whose last line lands nearly full cannot be told from a line the
  column broke.

---

## [0.38.56] — 2026-08-26

*Highlights: The note body gains a remembered Expand toggle for long notes.*

### Added
- **The writing area can be made taller.** An **Expand** toggle under the body switches it from
  twelve rows to twenty-six and back — the same one-click control the comments box already had,
  until now the only resizable box in the editor — and unlike that one, the body remembers the
  choice across launches. Nothing below becomes unreachable, because the editor already scrolls;
  the page simply gets longer. Dragging the box's edge was built first and abandoned: the editor
  sits inside a scrolling canvas that recomputes its scrollregion whenever its contents resize,
  and a drag fires that dozens of times a second, leaving widgets drawn at stale positions — a
  conclusion both existing resize helpers had already written down in as many words.

### Testing
- **Seventeen checks in `qa6.py`.** They cover the toggle, the stored choice being written and
  read back, and the comments box — which shares the helper — being left exactly as it was:
  still four rows, still deliberately not remembered.

---

## [0.37.56] — 2026-08-26

*Highlights: Paste becomes format-aware — rich text travels into and out of notes, with no new
dependency.*

### Added
- **Pasting keeps the formatting it came with.** **Ctrl+V** brings bold, italics, colours and
  lists across from a browser or a word processor; **Ctrl+Shift+V** (also on the right-click
  menu) pastes the words alone, dropping even the list markers a source writes into its own
  plain-text copy. Copying works the same way in reverse: a note lands in an email or Word
  still formatted, and two notes copy between each other exactly. Ctrl+V used to paste plain
  text, but keeping formatting is what Word, Google Docs and every browser already do — and
  nothing rich on the clipboard, or anything at all going wrong reading it, falls back to the
  ordinary paste. A page's own theme is not treated as formatting: a dark-mode site's
  near-white-on-near-black stays behind, and colour survives only where it is actually coloured
  — a red warning or a pale-enough highlight comes through, greys, blacks and whites do not.
  ([the full story](docs/ISSUES_LOG.md#the-paste-that-kept-the-formatting-it-was-told-to-drop))

### Changed
- **Rich clipboard reading costs no new dependency.** It goes through `ctypes`, in the standard
  library — Tkinter's own clipboard only ever offers plain text, which is why paste was lossy.
  The HTML-to-note conversion lives apart from the clipboard in `core/richtext.py`, strings in
  and strings out, so it tests on any machine while the Windows-only part stays small and
  isolated. The mapping is deliberately lossy: anything HTML expresses that a note cannot is
  dropped rather than approximated — the app's existing choice for malformed formatting — and
  font size and family are dropped on the way in too, since the app offers eight of each and a
  web page uses neither.

### Testing
- **The paste checks now press the actual keys.** They used to drive `_on_body_paste` and
  `_paste_plain` by calling them, so a broken key binding would have passed unnoticed. They now
  send the `<<Paste>>` virtual event Tk turns Ctrl+V into, and `<Control-Shift-V>` — which is
  how anyone actually reaches either choice.

---

## [0.36.56] — 2026-08-25

*Highlights: Fonts land in notes and Settings, alongside theming, toolbar and title-field fixes.
(This grouped section covers the 0.35.51, 0.36.54 and 0.36.55 bumps too — see the
[version ledger](docs/ROADMAP.md#version-ledger).)*

### Added
- **Font size and family in the note body.** A **Font** group in the toolbar sets the typeface
  and size of the selection — or sticks for whatever is typed next, the way the colour pickers
  already do — while Settings → Appearance sets the baseline every note starts from, since "my
  notes should be bigger" is a statement about reading rather than one note. Choosing
  **Default** stores no span at all, which is what lets a note follow the setting instead of
  staying pinned; a selection spanning two sizes reads as Default rather than claiming the
  first run's size for the whole selection. Families are a curated eight that ship with every
  Windows install: notes travel as share codes and backups, and Tk silently substitutes a font
  the reader does not have, with nothing to say the note is no longer showing what it was
  written in.
- **Notes show an estimated reading time** under the word and character counts. It assumes 200
  words a minute — the slow end of the usual adult range, so a faster reader loses nothing
  while a slower one is never told the note is shorter than it is. Notes under a minute say so
  rather than rounding to zero.

### Changed
- **Size and family are stored as ordinary spans, merged with bold and italic only at render
  time.** All four collide over Tk's font option — two tags that set it do not compose, one
  simply wins, the same collision that made `bold_italic` a tag of its own — so they stay
  separate in the note and merge into one composite tag per run, built on demand. A note that
  never touches size or family tags exactly as it did before, and the plain `bold` tag stays on
  the text underneath as the marker the toolbar reads, so "is this selection bold?" still
  answers correctly inside a resized run. Two things follow the base font now: bold and italic
  are separate font objects built from it, and the list hanging indent moves with it — `• ` is
  11px at 12pt and 22px at 24pt, so the fixed margin that hung correctly at the default left a
  large-font item's second line out of true.

### Fixed
- **The information bars in Settings → General, Backup and About recolour with the theme.**
  They stayed dark after switching to a light theme, leaving their text almost unreadable:
  Settings builds both surfaces by blending (`card` toward `text` for the well inside a card,
  toward `subtext` for its hairlines), so neither result is an entry in any theme's palette and
  the pass that remaps stale colours could not see them — measured, 19 widgets across the three
  panels still carried the dark inset. Both derivations now live in one place that pass knows
  about, fixing all 44 blended call sites rather than any one of them.
  ([the full story](docs/ISSUES_LOG.md#the-settings-panels-that-stayed-dark-on-a-light-theme))
- **The formatting toolbar no longer runs off the editor's right edge.** It needed 868px
  against 787px of pane, leaving the last group unreachable without widening the window. Two
  things fixed it: the four group captions are gone — 182px of width whose job the hover labels
  added last release already carry — and the bar now wraps whatever will not fit onto a second
  row. Trimming alone would only fix one set of font metrics, since the same bar measures 577px
  here and 827px on a machine without these fonts — wrapping is what makes it correct at any
  width, any font and any display scaling.
  ([the full story](docs/ISSUES_LOG.md#a-toolbar-check-that-measured-the-wrong-thing-three-times))
- **The Settings section list scrolls.** Nine entries in four groups, plus the brand and the
  theme toggle, need more height than a short window has, and the list was a plain frame —
  whatever did not fit was simply unreachable. The wheel now scrolls it anywhere over the list,
  while the brand and the theme toggle stay put.
- **A note title is now limited to 200 characters.** Not for storage or layout — the note list
  already shortens titles to 60 for display — but because tk.Entry slows roughly with the
  square of what it holds: one keystroke measured 0.5ms at 30 characters, 38ms at 10,000 and
  3.5 seconds at 100,000, so a document pasted into the title by accident froze the field with
  no way to edit it back. An over-long paste is shortened to fit rather than refused whole,
  which would have left the field empty and looked like the paste failing; a counter (175/200)
  appears once within 40 characters of the limit and turns the warning colour when full, hidden
  until then. Titles already saved are never touched: a note written before the cap loads in
  full and saves back in full.
  ([the full story](docs/ISSUES_LOG.md#the-title-box-that-took-three-and-a-half-seconds-a-keystroke))
- **The raw hex label beside a note's colour swatch is gone.** It printed the value once a
  colour was picked — "#7c5cff" — which means nothing to most people, and which the swatch-only
  picker itself deliberately avoids. Naming the state instead ("custom color") only swapped one
  redundant thing for another, so the row now reads "Color:" and a swatch, and nothing else.

### Removed
- **The quote block is removed** — from the app and from the code, not merely hidden. It read
  as a heavy visual device for something a note rarely needs, and it was the only paragraph
  property carrying colours of its own. A note that still holds the old `block` key loads as an
  ordinary paragraph, keeping whatever list kind, indent and alignment it also had; nothing
  needs migrating.

---

## [0.34.51] — 2026-08-25
*Highlights: paragraph formatting lands — lists, indentation, alignment and quote blocks.*

### Added
- **Paragraph formatting in the note body**, as a **Paragraph** toolbar group: bullet and numbered
  lists nesting to eight levels with Tab and Shift+Tab, indentation for ordinary paragraphs too,
  left/centre/right alignment, and quote blocks. Enter continues a list — on an item you never
  typed into, it steps out one level before leaving the list — Backspace against a marker outdents
  a nested item and only removes the marker once it is back at the margin, and numbered lists keep
  a separate count per level, restarting at one under every parent and resuming the outer count
  after. The marker lives in the note's text ("• milk", "1. milk"), so a list survives export,
  share codes and being copied anywhere as readable plain text; only the indent is a Tk tag drawn
  over it. Bullets change glyph with depth (•, ◦, ▪) and numbers deliberately don't — 1. then a.
  then i. is ambiguous with ordinary prose — and a quote block is a coloured bar with a tinted
  background rather than a border, since Tk draws a bordered wrapped paragraph as several broken
  boxes instead of one block.

- **Every formatting-toolbar button now explains itself on hover** — its name plus a line saying
  what it acts on, appearing after a short pause so sweeping across the bar doesn't flash a row of
  labels. All thirteen carry one: the four style toggles, both colour pickers, both list buttons,
  the three alignment icons, indent and outdent, and the quote block. The alignment ones say
  outright that alignment applies to whole paragraphs and not to part of one — exactly the
  question those buttons raise when centring a selection moves the whole paragraph.

### Changed
- **Notes gained a `paragraphs` field** recording line-level formatting — which lines are list
  items, at what depth, how they are aligned, and whether they sit in a quote. Only non-default
  properties are stored, so a note with no paragraph formatting gains nothing at all, and
  `normalize_note` bounds every entry by the body's real line count, dropping an entry left
  pointing past the end of a shortened note rather than keeping it to indent a line that no longer
  exists.

---

## [0.32.51] — 2026-08-21
*Highlights: Settings rebuilt around a section list, and the core layer becomes a package.*

### Changed
- **Settings was rebuilt against a reference design.** The section list is grouped under
  General / Content / Data / More instead of running as one flat column, "Back to Notes" moved
  into that list (retiring the bar that used to span the top of every section), and light/dark
  became a small toggle at the foot of the list — reachable from any section rather than only from
  Appearance. Controls now sit in bordered cards where each setting reads as a row — what it is on
  the left, what you do about it on the right — and "Your name" became "General", since it carries
  the greeting settings.
- **The theme picker shows both the dark and the light sets at once**, each swatch previewing that
  theme in its own colours with a tick on the one in use. Picking a light theme used to mean
  switching mode first and then choosing; now it is one click either way.
- **Statistics no longer reads as a paragraph.** Figures used to render as sentences — "Added: 0
  this week 0 this month 5 this year 0 older" in one run of same-size text — so nothing could be
  taken in at a glance, which is the entire point of a snapshot. Standalone counts are now tiles
  with the number leading and its caption underneath, the time breakdown is a small table with
  right-aligned digits and dimmed zeros so the non-zero figures stand out, and the per-category
  split is a row of pills carrying each category's own colour.
- **The pencil, wastebasket and padlock on category and template rows are drawn glyphs rather than
  emoji**, matching the section list. The old set mixed a colour-bitmap wastebasket stuck at one
  shade on all eight themes with a monochrome pencil that recoloured correctly, so the two never
  matched each other or the interface around them. Rows are also separated by a hairline now,
  rather than running together as one block.
- **Every Settings section entry now carries an icon**, drawn as shapes rather than emoji or
  images — which is what lets each one take the current theme's colour instead of staying the same
  on all eight. Nielsen Norman Group measured people finding items in a list about 37% faster when
  entries carry both a distinct icon and colour rather than text alone, with text-only the slowest
  of the four arrangements they tested.
- **Recently deleted paints 25 rows before "Show more" instead of 50**, halving how long the
  section takes to open with a large trash (about 585ms to about 405ms). Profiling put roughly 95%
  of that time in Tk laying the widgets out rather than in any code here, so rows painted up front
  is the only real lever. The cost was always there; the old expand-in-place panel just re-closed
  on every other click, so it was only paid half the time.
- **Settings got a visual pass.** The selected section entry — previously a solid block of the
  accent colour, the loudest thing on the page, permanently — is now an accent rail beside a
  tinted row, and nav entries and action buttons respond to the cursor with the same hover
  convention the sort menu, emoji picker and category picker already used. "Empty trash" is
  outlined rather than filled: it keeps the warning colour reserved for destructive actions
  without a permanent-delete button being the heaviest element on screen.
- **Settings is now a list of sections on the left and one open section on the right**, instead of
  a single long scrolled column where everything competed for the same vertical space and reading
  meant zig-zagging. Categories, Templates, Recently deleted and Duplicates — formerly panels that
  expanded in place behind a button — are now ordinary list entries with no closing ✕, renamed for
  what they are ("Manage categories" → "Categories", "Manage templates" → "Templates", "Clean up
  duplicates" → "Duplicates"). The content column is capped so a short form isn't stretched across
  a wide window, and the theme preview cards wrap to fit it instead of running off the edge.
- **The app is being reorganised from one ~11,000-line file into a package.** The data and rules
  layer now lives in `noteorganizer/core/` as ten modules — the calculator's expression parser,
  recurrence, themes, rich-text spans, share codes, duplicate detection, data location and
  migrations, storage, categories, and the note model — and none of them imports tkinter, a rule
  the data-safety tests now enforce rather than only document. A new runner (`tools/run_tests.py`)
  copies the suite to a throwaway folder before running it, since every QA script deletes the data
  files in whatever directory it starts in. `note_organizer.py` went from 11,147 to 9,739 lines
  and still runs and re-exports everything that moved, so nothing about running the app, the
  tests, or the build changed; the interface itself hasn't been split yet.
- **Importing `note_organizer` no longer does anything.** It previously resolved a data folder,
  migrated notes into it, deleted files it judged redundant, and wrote settings — meaning an
  import alone could destroy a notebook, which is exactly how one was lost once. That work moved
  into `initialise()`, called by the app and by the entry point; anything that wants the data
  layer without opening a window now has to ask for it deliberately.

### Fixed
- **Settings → About showed a blank storage folder, and Statistics read "Using Note Organizer
  since None".** When Settings moved into its own module it imported the entry module to reach
  those values — but a real launch makes the running copy `__main__`, so that import returned a
  second, never-initialised copy of the module where everything was still `None`. Both labels now
  read from the core layer, which is only ever imported by name and can't be duplicated this way;
  the nine QA scripts all `import note_organizer` — precisely the condition under which the bug
  disappears — so a dedicated test (`test_entry_module_identity.py`) loads the app the way a real
  launch does. ([the full story](docs/ISSUES_LOG.md#the-module-that-existed-twice))
- **"Delete the notes too (permanent)" wasn't permanent.** Deleting a category that still held
  notes offered that wording, but the notes went to Trash with the usual 30-day grace period, the
  same as any other delete. The label now says so, instead of scaring people away from a safe
  choice or convincing them notes were unrecoverable while they sat in Trash.

## [0.32.49] — 2026-08-20
*Highlights: theme switching goes flicker-free and ~5× faster; selection quirks ironed out.*

### Changed
- **The Windows build no longer bundles numpy**, which the app never imported — it was only
  included because Pillow can optionally use it for array conversions that nothing here does. The
  packaged folder drops from 68 MB to 38 MB with no change in behaviour, and the image and
  animated-GIF preview path was verified to work with numpy made unavailable.
  `NoteOrganizer.spec` is now tracked in git as well, so the build recipe can be reproduced from a
  fresh clone instead of living on one machine.

### Fixed
- **Highlighting text across multiple lines no longer paints full-width bars** stretching far past
  the words. Tk paints a background across a line's whole remaining width whenever the highlight
  covers that line's invisible newline; highlights are now applied line by line and never include
  it. Notes highlighted before this fix render correctly too, without re-highlighting — and typing
  with a highlight still "stuck" on no longer bleeds when you press Enter.
- **The note body's right-click menu lines up.** Its entries mixed four kinds of decorative prefix
  (styled mathematical letters, combining underline/strike marks, plain letters and an emoji)
  which render at different widths, so the words after them lined up with neither each other nor
  the plain Cut/Copy/Paste entries above. All labels are plain text now, so every entry starts in
  the same place.
- **The comments box now shares the note body's selection fixes.** Double-clicking a row with no
  words in it used to select that row's invisible newline and paint a full-width highlight over an
  empty line. Both fields use the same handlers now: double-click treats punctuation as a word
  boundary (either side of `something.else` selects just that word), an empty row selects nothing,
  and triple-click stops at the real end of the line instead of swallowing the newline.
- **A note's own colour is no longer silently repainted with the theme's accent on theme
  switch.** Switching to a theme whose palette didn't contain that colour let the safety pass
  that remaps leftover colours mistake a deliberately coloured note for a themed widget. Note
  cards are now recoloured last, from the note's own data, so the note's colour always wins.
- **Switching themes no longer flickers** with dark bands across a half-recoloured page. The bulk
  of a switch was destroying and rebuilding every note card (about 85ms of 121ms, with the list
  visibly emptying and refilling), plus rebuilding the statistics panel and the off-screen
  calendar — none of it needed when only colours changed. A switch now takes roughly 26ms instead
  of about 140ms and no longer slows as notes accumulate: going from 40 to 100 notes used to add
  117ms; it now adds 19ms.
  ([the full story](docs/ISSUES_LOG.md#the-theme-switch-flicker-and-three-ways-not-to-fix-it))

## [0.32.44] — 2026-08-19
*Highlights: text color and highlight join the toolbar, plus a round of selection fixes.*

### Added
- **Phase 2a of rich text: text color and highlight**, on the same toolbar as
  Bold/Italic/Underline/Strikethrough and in the right-click menu. Both combine with each other
  and with the boolean styles, applied to a selection or queued to "stick" for whatever's typed
  next, the same way the Phase 1 styles work — and the toolbar buttons preview the active color as
  a real swatch, with the letter's contrast computed automatically so it stays legible against any
  color on any theme. The four style toggles and the two color pickers are visually grouped apart
  ("Style" / "Colors" labels with a divider), since they work differently — toggle vs.
  open-a-picker — and previously all looked like one undifferentiated row of buttons.

### Changed
- **The hex-code entry is gone from both color pickers** (the note's own color, and the new
  text-color/highlight pickers) — swatches only now, since most users don't think in hex. Both
  palettes were enlarged to compensate: the shared note-color/text-color palette grew from 10 to
  15 colors, and the highlight palette from 6 to 10.

### Fixed
- **Switching themes after opening a color picker could crash** with `TclError: invalid command
  name` — the picker's hex-code entry (since removed, see Changed) registered itself for live
  theme-tracking but was never un-registered once destroyed, the same class of bug as an
  unbounded-growth leak fixed earlier in the project, just in a different tracking list. This also
  retroactively fixes the pre-existing note-color picker, which had the exact same latent bug.
- **Right-click → "Select All" no longer selects the invisible trailing newline**, which visibly
  stretched the highlight to the full width of the last line regardless of how short it actually
  was.
- **Triple-clicking a line stops at the real end of its text.** It used to select through to the
  start of the next line (two double-clicks landing close enough in time counted the same),
  including the invisible newline in between — so a copy right after picked up an unwanted extra
  newline.
- **Double-clicking a word right up against punctuation selects just that word.** `something.else`
  used to select as one punctuated "word" regardless of which side was clicked; punctuation is now
  a hard word boundary, the way most editors treat it — clicking `something` selects only
  `something`, clicking `else` only `else`.
- **Selecting colored or highlighted text shows the selection again.** Tk gives later-created tags
  higher display priority, and the color tags were created after the built-in `sel` tag, so the
  color's own background silently painted over the selection color. Selection (and re-coloring
  already-colored text) was never actually broken, just invisible; `sel` is now kept on top of the
  tag stack so the selection color always wins visually.

## [0.31.39] — 2026-08-18
*Highlights: rich text begins — Bold, Italic, Underline and Strikethrough in the editor.*

### Added
- **A rich text formatting toolbar (Bold, Italic, Underline, Strikethrough)** in the note editor,
  with the same four options in the right-click menu and keyboard shortcuts (Ctrl+B/I/U/D). Apply
  a style to selected text, or toggle one with nothing selected so it "sticks" for whatever you
  type next until turned off — including correct handling of fast typing, where a burst of several
  keystrokes doesn't drop the style on any of them. This is Phase 1 of a larger rich-text effort;
  font size/color/highlight, bullet lists, and paste-with-formatting are still ahead.
  ([the full story](docs/ISSUES_LOG.md#the-fast-typing-fix-that-took-three-tries-to-land-safely))

## [0.30.39] — 2026-08-18

*Highlights: one critical data-safety fix — script-mode runs can no longer delete the real
notebook in `%APPDATA%\NoteOrganizer`.*

### Fixed
- **Running in script mode could silently delete the real notes in `%APPDATA%\NoteOrganizer`** —
  the store the distributed `.exe` actually reads from. Found by hand: `python note_organizer.py`
  (or any script that imports it, including the project's own headless test scripts), run from any
  directory that hadn't already reclaimed once, triggered migration logic that copied the AppData
  notes into the running directory — and a separate cleanup step then treated the AppData
  originals as a "redundant leftover copy" and deleted `notes_data.json`, `settings.json`, and the
  whole `attachments/` folder outright. `%APPDATA%\NoteOrganizer` is now permanently exempt from
  that cleanup, no matter how "redundant" it looks — it's the durable, cross-run store, never a
  disposable one. ([the full story](docs/ISSUES_LOG.md#the-cleanup-that-deleted-the-real-notebook))

## [0.30.38] — 2026-08-18

*Highlights: an in-note calculator — hand-rolled parser, insert-into-note logging, session
history — with 47 evaluator checks behind it.*

### Added
- **A collapsible in-note calculator**, next to Checklist in the note editor. Standard +/−/×/÷
  with three interchangeable bracket styles, a square root, a general power operator (any
  exponent, not just squaring), and percent — evaluated by a small hand-rolled parser rather than
  `eval()`. The display accepts typing and pasting directly, not just button presses, so an
  expression copied from elsewhere can be evaluated as-is.
- **Insert the calculator's result into the note body.** Inserts the whole formula (not just the
  answer), and repeated use builds a clean log downward — each insertion lands on its own line
  after the previous one — instead of gluing onto wherever the cursor happens to be. A
  collapsible, session-only history of past calculations comes with it, with a Clear button and
  click-to-insert on any past entry.

### Testing
- **Added `test_calculator.py` (47 checks)** covering the expression evaluator directly —
  precedence, brackets, power/root/percent, and a wide range of malformed input. Added extensive
  `qa1.py` coverage for the real button/paste/history UI flow.

## [0.28.38] — 2026-08-17

*Highlights: a broad stability sweep — search debounce, a 16-timer crash-safety audit, autosave
and backup hardening, a livelier Statistics page, and two new QA suites.*

### Added
- **Fuller Statistics breakdown.** Settings → Statistics now splits "new/updated this week" into
  a week / month / this year / older breakdown for both added and updated notes, laid out in an
  aligned grid so the numbers line up between the two rows regardless of digit count or icon
  width.
- **Standalone counts for templates, checklists, and Trash.** Statistics now shows counts for
  saved templates, notes with a checklist, and notes currently in Trash — each counts the thing
  itself, not how many notes reference it (a template can be reused across many notes; a checklist
  only ever lives inside the one note it's on).
- **"Using Note Organizer since `<date>`".** A first-launch date, stamped once and never
  overwritten, shown in Statistics. Existing installs get the date of their first launch *after*
  this update, since there's no way to know their real first-use date retroactively.

### Changed
- **QA steps in CI now start from a clean slate.** The GitHub Actions workflow didn't reset app
  state (settings, notes, trash) between QA test steps, so each script silently inherited whatever
  the previous one left behind — investigated after two workflow runs sat stuck for hours at the
  QA5 step. The exact hang never reproduced locally, but the order-dependency was worth fixing
  regardless; a new 15-minute job timeout also makes any future hang fail loudly within minutes
  instead of silently occupying a runner for hours.
- **Statistics counts restyled and moved.** Category counts now show as a colored dot plus plain
  text instead of a box-styled chip, since they're no longer clickable. The whole section moved
  from right after "Your name" to between "Clean up duplicates" and "Storage info."

### Fixed
- **Typing in the search box no longer lags.** Every keystroke rebuilt the entire note list —
  measured at ~800ms for 300 notes, so a short search term could cost several seconds of
  cumulative rebuild time. Now waits for a brief pause in typing before rebuilding once, the same
  debounce pattern already used for autosave.
- **Every scheduled timer audited for close-mid-wait crashes.** All 16 timers/callbacks in the app
  were checked for what happens if the window closes while one is still pending; nine were found
  unguarded and fixed (the export/import progress poller, the periodic unsaved-edit check, the
  debounced autosave and search refresh, the username-field autosave, the startup
  version-change/reminder banners, the editor's scroll-region sync, and the image preview's
  click-outside dismiss). Even checking "is the window still there" can itself fail once the whole
  application is torn down — one shared, properly-guarded check is now used everywhere this
  matters.
- **Unexpected errors in clicks and shortcuts are no longer silent.** Tkinter's default behavior
  only prints to a console the windowed build doesn't have, so the user saw nothing at all — no
  crash, no explanation, no way to know if their data was affected. Now logged to the same crash
  log the top-level handler uses, plus a brief on-screen toast so there's at least some signal.
- **Export/import can no longer hang the progress bar forever.** The background threads only
  caught `IOError`/`OSError`; any other unexpected error type killed the thread silently without
  ever marking the operation finished. Both now catch anything unexpected as a last resort, so the
  operation always resolves — a specific message for the failure cases already understood, a
  generic-but-honest one for anything else.
- **Changing a template's category no longer destroys the template editor.** Found by hand: the
  dropdown's opening logic closed whatever popup was "currently open" before showing its list —
  but the template editor *was* that popup, so clicking the category dropdown destroyed the very
  editor it lived inside, discarding unsaved changes; the calendar's "Jump to month" popup had the
  same bug. Both now distinguish a dropdown nested inside another popup from one replacing an
  unrelated previous one — which also fixed the category list appearing anchored to the window's
  top-left corner, a side effect of positioning against a just-destroyed button.
- **Typing a date into the Date field now autosaves.** It was the only editor field missing that
  wiring, so a typed date change could be silently lost by clicking away instead of pressing Save.
  Wiring it up naively made autosave interrupt mid-keystroke with an "Invalid date" warning on an
  as-yet-incomplete date — that warning and the "repeating note needs a start date" one now only
  show on an explicit manual Save, while autosave silently waits for a valid, complete value.
  ([the full story](docs/ISSUES_LOG.md#the-date-field-that-either-lost-your-edit-or-wouldnt-let-you-finish-typing-it))
- **"Recently updated" / "Oldest updated" sort could misorder notes.** The saved timestamp only
  tracked minutes, so two notes saved within the same minute looked identical to the sort and fell
  back to an unrelated order instead of true edit recency. Timestamps now carry second-level
  precision everywhere a note's timestamp gets written.
  ([the full story](docs/ISSUES_LOG.md#recently-updated-sort-that-couldnt-tell-recent-apart-from-recent))
- **Background autosave no longer shows a "Note missing" error.** Its debounced timer could fire
  after the note it was about to save had been removed some other way in the meantime, raising a
  dialog meant only for an explicit Save click. It now silently does nothing in that case,
  matching how switching notes already handled the same situation.
  ([the full story](docs/ISSUES_LOG.md#the-autosave-that-could-interrupt-you-over-a-note-that-was-already-gone))
- **Removed the calendar's redundant "View this day" right-click entry.** A plain left-click on
  the day already opens the same panel.
- **Username capped at 30 characters.** The Settings → Your name field had no length limit, which
  could make the sidebar greeting look broken. The cap is checked in real time as you type — the
  field simply stops accepting more instead of accepting everything and quietly trimming later —
  and the redundant "Save" button is gone, since the field already autosaves shortly after typing
  stops and immediately on Enter or clicking away.
  ([the full story](docs/ISSUES_LOG.md#the-username-cap-that-took-three-tries))
- **Clicking empty Settings space now clears field focus.** Clicking a non-interactive part of the
  page (a section title, a card's background) — including going straight to "Back to Notes" —
  left a previously-focused field's cursor visibly blinking even after its value had already
  autosaved. Both cases now clear focus correctly.
  ([the full story](docs/ISSUES_LOG.md#the-focus-fix-that-broke-the-thing-it-wasnt-touching))
- **The whole Settings page scrolls now.** The theme picker's preview cards swallowed the wheel
  event (a Canvas quirk — they have built-in scroll behavior of their own), and the Statistics
  summary/category chips were simply never wired into the page's scroll-forwarding. Both now
  scroll the page correctly, using the same forwarding pattern already used elsewhere in Settings.
  ([the full story](docs/ISSUES_LOG.md#the-scroll-that-stopped-twice-for-two-different-reasons))
- **Three layout fits, each measured with exact pixel numbers rather than assumed.** The sort
  dropdown's "Recently updated" option was cut off (it rendered at exactly its natural text width
  with zero margin), the bulk "Category" button was cramped (the bulk-action bar's four widgets
  needed more width than the fixed-width sidebar allowed), and Settings' "← Back to Notes"
  scrolled out of view (it was just another row inside the scrollable content). Widened the sort
  label, tightened the bulk bar's font and spacing, and pinned the Back button in its own fixed
  row outside the scrollable area.
- **Reclaiming notes from `%APPDATA%` now verifies its backup before overwriting.** Found during a
  deliberate review of the app's data-safety guarantees, not from an observed failure: the app
  backed up the local file before overwriting it with the AppData copy but never checked whether
  that backup succeeded — disk full, permissions, or a locked file meant the overwrite proceeded
  with no safety copy. It now aborts and leaves the local file untouched if the backup fails.
  ([the full story](docs/ISSUES_LOG.md#a-backup-that-assumed-it-had-worked))
- **Every version upgrade now takes a timestamped backup of `notes_data.json` first.** Previously
  only a brand-new first run got a backup; a normal upgrade re-reading (and potentially
  rewriting) the same file had no equivalent snapshot. Upgrade backups are kept forever, never
  auto-deleted — clearing old ones out is the user's call, not the app's.
- **Statistics category chips are no longer fake-clickable.** They looked clickable (hover
  highlight, hand cursor) but clicking silently did nothing — reproduced in both the script and
  the packaged `.exe` after scrolling the Settings page, yet never in a headless test despite
  several synthetic-repro attempts. Rather than keep chasing the exact cause, click-to-filter was
  removed outright: Statistics is a read-only snapshot, not another way to filter notes.
  ([the full story](docs/ISSUES_LOG.md#the-chip-that-looked-clickable-and-the-fix-that-looked-like-it-worked))
- **Statistics stays live while Settings is open.** It only recomputed when Settings first opened
  or the theme changed, so category renames/deletes, new notes, and template changes left stale
  numbers on screen until the user left and came back. An intermediate fix gated the refresh on
  `winfo_ismapped()` — which doesn't reliably reflect `pack()`/`pack_forget()` synchronously in
  real interactive use, so it silently skipped real updates. Statistics now refreshes
  unconditionally (a cheap operation) whenever the note list refreshes or a template is
  added/edited/deleted.

### Testing
- **Added `qa8.py`.** Automated coverage for the search debounce (no rebuild while typing, correct
  filtering after the pause), all nine timer-safety fixes, the callback-exception handler, and the
  export/import worker exception-safety fixes — each confirmed to resolve, not hang, when an
  unexpected error type is deliberately injected.
- **Added `qa9.py`.** Covers the nested-dropdown-destroys-its-own-parent-popup fix in both places
  it occurred (template editor, calendar's jump-to-month) — including the exact scenario reported:
  editing an already-saved template's category and confirming the change survives a reload from
  disk.
- **Typing a date schedules an autosave.** Added a regression check to `qa5.py` confirming it.
- **Fixed `qa1.py`'s sort-option test, which tested nothing.** It looped over made-up option
  labels ("Newest first", "Title A-Z", etc.) that matched none of the app's real sort options, so
  it never exercised any actual sorting logic — it only proved the app didn't crash. Now uses the
  real option labels against a small fixture of notes and checks each mode produces the exact
  correct order.
- **Regression tests added to `qa6.py`** for the username length cap (both the real-time and
  save-time correction) and the Settings focus-clearing fix (same-page clicks and the direct
  "Back to Notes" path).
- **Timestamps include seconds.** Added a regression check confirming a freshly-saved note's
  timestamp includes seconds — the fix for the "Recently updated" ordering bug.
- **Fixed `qa5.py`'s own date-autosave check** to flush its pending autosave timer immediately
  after confirming it was scheduled, instead of leaving it dangling for a later, unrelated test to
  potentially trip over — that dangling timer is what surfaced the "Note missing" autosave bug
  above.
- **Regression checks for the three layout fits** added to `qa1.py`, `qa6.py`, and `qa7.py` —
  pixel-measurement checks for the sort label and bulk-action bar, and a scroll-position check for
  the sticky Back button.
- **Fixed the bulk-action-bar width test itself after it failed in CI.** It compared against an
  absolute pixel number measured locally on Windows using "Segoe UI," but the CI runner is Linux,
  which doesn't have that font — Tk silently substitutes a wider fallback there. It now compares
  the fixed bar against a reconstruction of the pre-fix sizing, built with whatever font actually
  resolves on the machine running the test, verifying the fix's real effect instead of a
  Windows-specific pixel target.
  ([the full story](docs/ISSUES_LOG.md#the-pixel-perfect-test-that-only-worked-on-windows))
- **Wheel-over-widget scrolling is covered.** Added regression checks to `qa6.py` confirming a
  wheel event over a theme preview card, and over a Statistics chip, both scroll the Settings
  page.
- **Added `test_data_safety.py`.** A new standalone suite (no GUI, like `test_recurrence.py`)
  covering the backup/migration safety net directly — the version-upgrade backup, the migration
  backup-verification fix above, and the underlying
  `backup_notes_file`/`_timestamped_backup`/`detect_version_change` helpers — using temporary
  directories so it never touches real data. A companion `qa1.py` check confirms the running app
  actually takes the backup when a version upgrade is detected; both now run in CI on every push
  and PR.
- **`get_first_launch_date` is covered too.** A `test_data_safety.py` check confirms it stamps a
  date on first call and never overwrites an existing one.
- **Replaced `qa6.py`'s old "statistics chip navigation" test.** It never actually clicked the
  chip — it called the underlying functions directly, so it would have passed even if the real
  click were completely broken. The replacement confirms chips have no hand cursor and that
  clicking one changes neither the active tab nor the filter.
- **Regression checks for the new Statistics content in `qa6.py`.** Template/checklist/deleted
  counts and the first-launch date render correctly; stats reflect a category deletion, a normal
  multi-category save sequence, and a template add/edit/delete — all without needing to leave and
  reopen Settings; and separately, switching away to the editor and back still shows current data
  for the one thing that genuinely can't update while Settings itself is open (checklists, edited
  only in the note editor).

*(The jump from 0.28.38 down to 0.5.0 is the numbering policy changing: from here up,
versions are cumulative Added/Fixed totals — see the
[Roadmap's Versioning section](docs/ROADMAP.md#versioning).)*

## [0.5.0] — 2026-08-09

*Highlights: Going public — docs, GitHub and CI arrive alongside bulk actions and image previews.*

### Added
- **Project documentation set** — `README.md`, this changelog, architecture notes, roadmap,
  issues log.
- **Git version control**, hosted on GitHub.
- **Continuous integration via GitHub Actions** (`.github/workflows/tests.yml`): the full
  automated test suite now runs on every push and Pull Request.
- **Delete a note directly from the calendar day panel.** A small trash icon on each row in a
  day's note list, and a Delete button on the note-detail view reached from there. Reuses the
  same confirmation and recurring-series-scope prompts as deleting from anywhere else, so
  nothing about safety changes — it just no longer requires opening the full editor first.
- **Multi-select notes for bulk actions.** A "Select" toggle in the sidebar shows a checkbox on
  each note; pick several and move them all to trash or reassign them all to a different
  category in one action, instead of one at a time. The currently-open note's card is also now
  outlined in the theme's accent color, so it's clear at a glance which one is open.
- **Image attachments show a large in-app preview when clicked** (PNG, GIF, JPEG, WEBP, BMP) —
  most of the window, with a Close button and an "Open externally" option — instead of always
  handing off to an external viewer. Animated GIFs actually play, using real per-frame timing.
- **Delete confirmations count the attachments.** Single-note and bulk confirmations now
  mention how many attached files will go to the trash along with the note(s).
- **The app reopens the note you left off in.** It remembers which note was last open and
  restores it on the next launch with all its content — title, body, comments, checklist,
  attachments.

### Changed
- **Settings moved into its own sidebar button** (alongside New Note / Import / Share), out of
  the Notes/Calendar tab strip entirely, with a "← Back to Notes" button to return. Originally
  planned as "push it to the far right of the tab strip" (see ROADMAP), but that risked sitting
  too close to the window's own close button — the sidebar button avoids that concern and
  tested better in practice.
- **"📋 Copy code" renamed to "📋 Generate code".** Nothing has been generated or copied to the
  clipboard yet at the point it's clicked, which "Copy" implied. Matches the wording already
  used by the multi-note Share panel's equivalent button.
- **[Pillow](https://pypi.org/project/Pillow/) added as the app's first external dependency**,
  specifically for image handling. Plain Tkinter can only decode PNG/GIF natively and doesn't
  correctly composite animated GIF frames — many GIFs store only the region that changed from
  the previous frame, relying on the viewer to place it on a fixed canvas, and the in-app
  preview visibly jumped and resized itself every frame before this. Pillow fixes that, adds
  JPEG/WEBP/BMP support, and gives noticeably cleaner scaling.

### Fixed
- **Attachment files are now genuinely deleted from disk.** Removing an attachment from a note,
  and permanently deleting a trashed note (individually, via "Empty trash", or through the
  automatic purge after the retention window) all removed the note or reference but left the
  underlying file behind indefinitely — all four paths now clean up the physical file too.
  Moving a note to trash (the reversible, soft-delete path) correctly still leaves files
  untouched, since the note might be restored.
  ([the full story](docs/ISSUES_LOG.md#files-that-outlived-the-notes-they-belonged-to))
- **The calendar no longer navigates while hidden.** Keyboard navigation (PgUp/PgDn/Home) and
  the resize-driven font relayout could still act on the calendar behind the new Settings page
  if Calendar had been the last-selected tab — silently changing the visible month. Both now
  check that the calendar is actually on screen, not just that it's the notebook's internally
  "selected" tab.
  ([the full story](docs/ISSUES_LOG.md#a-calendar-that-kept-navigating-behind-the-users-back))
- **Single-note share codes get the duplicate check too.** Importing one skipped the check
  entirely and went straight to opening it for editing — found by hand, by re-importing a code
  copied from a note already present. Now checks for an exact match first and asks before
  opening it, same as the multi-note path.
- **Cancelling a calendar delete no longer bounces the view.** The day panel's delete actions
  (including the pre-existing right-click menu one) refreshed the panel unconditionally — even
  when the user canceled the confirmation dialog, which incorrectly bounced the view back to
  the day's note list. Now only refreshes if the note actually stopped occurring on that date.
- **Selecting notes and switching notes stopped flickering the list.** Both used to rebuild the
  entire note list just to reflect a small change; both are now targeted, direct updates to
  just the card(s) that actually changed. A bulk Trash/Category action still does a full
  rebuild afterward, since those genuinely change which notes exist or what they show —
  skipping that briefly left deleted notes' cards on screen, looking present but acting as if
  already gone.
- **No more spurious "Note missing" error** when deleting a note via right-click or the
  calendar while a *different* note sat open in the editor with unsaved changes. The delete
  flow temporarily repoints the editor's internal note-selection at the note being deleted to
  reuse the normal delete logic, so an autosave flush at that moment tried to save against the
  note about to be gone. Fixed at the root: an autosave flush now silently does nothing if the
  note it would save against no longer exists — appropriate for an automatic background action
  the user never directly asked for.
- **A note with only an attachment (or only checklist items) can now be saved.** Such a note
  was never autosaved, and even a manual Save was rejected as "empty" — attachments and
  checklist items now count as real, savable content everywhere this is checked.

### Testing
- **Two QA scripts had been passing for the wrong reason.** `qa3.py` and `qa4.py` still
  referenced the Settings page's old, removed notebook-tab index, and their exit code was never
  actually checked — a script erroring out still reported as a successful run. The scripts now
  call `show_settings_page()` directly, and every test script exits with a real failure status
  when a check fails, which is what makes the new CI integration meaningful rather than always
  green. ([the full story](docs/ISSUES_LOG.md#tests-that-always-passed-no-matter-what))
- **Added `qa6.py`** — automated coverage for category grouping (collapse state and
  persistence), Settings (username greeting, statistics navigation), attachments through the
  actual UI functions (not just the file-cleanup fix), several multi-feature combination
  scenarios, and the parts of window layout with a real right/wrong answer (sidebar toggle,
  dialogs staying within the app window). Wired into the CI workflow alongside the rest.
- **Added `qa7.py`, closing a coverage audit** across everything built in recent sessions:
  three of the four attachment-cleanup paths (permanent delete, empty trash, automatic purge)
  had never had a permanent regression test — only the fourth (removing a single attachment)
  did. Also newly covered: deleting a note from the calendar (including the
  Cancel-doesn't-bounce fix), multi-select bulk actions (including the no-rebuild-on-select/
  switch behavior and the currently-open-note cleanup fix), the Pillow-based image preview
  (scaling in both directions, corrupt-file handling), attachment mentions in delete
  confirmations, the "Note missing" bug fix, attachment-only-note autosave, and the
  last-open-note memory feature.

---

## [0.4.0] — Performance overhaul & test infrastructure

*Highlights: Performance overhaul plus the first automated test suite backing it up.*

### Added
- **"Clean up ALL duplicate groups"** — a one-click action that applies "keep the first copy,
  remove the rest" across every detected duplicate group at once, instead of working through
  each group individually.
- **A "Clear" button on the Import Code panel**, to wipe a pasted code (and any leftover status
  message) without manually selecting and deleting it.

### Fixed
- **Recently Deleted (Trash) panel opens fast.** It was rendering every entry at once — opening
  it with 600 deleted notes took ~1.8 seconds. Now paginates to 50 entries at a time with a
  "Show more" button; opens in ~100ms regardless of trash size.
  ([the full story](docs/ISSUES_LOG.md#the-trash-panel-that-took-two-seconds-to-open))
- **Memory leak affecting long sessions.** Five frequently-rebuilt UI areas (note cards,
  calendar cells, attachments list, the multi-note share panel, and the generated share-code
  display) registered for live theme updates on every redraw without ever cleaning up the old
  registrations, so the list grew unbounded and progressively slowed the app down. Fixed by
  only tracking widgets that persist for the app's lifetime — rebuilt content now picks up the
  current theme naturally each time it redraws.
  ([the full story](docs/ISSUES_LOG.md#the-slowdown-that-only-showed-up-after-a-long-session))
- **Share Notes panel paginated too.** It had the same "render everything, no cap" issue as the
  Trash panel (one checkbox per note); fixed with the same pagination approach.
- **Export and Import no longer freeze the app.** Both the full `.zip` backup and the text
  share-code used to block the entire UI while running — a backup with a lot of attachments
  could freeze the app for several seconds with no feedback. Both now run on a background
  thread with a live progress bar, and the app stays fully interactive throughout.
  ([the full story](docs/ISSUES_LOG.md#exportimport-freezing-the-app))
- **Importing the same data twice no longer creates duplicates.** Import (both code and `.zip`
  backup) could silently duplicate notes; it now checks incoming notes against what's already
  there and asks whether to skip duplicates, import everything anyway, or cancel.
  ([the full story](docs/ISSUES_LOG.md#importing-the-same-backup-twice))
- **Scroll wheel no longer gets "stuck" on small panels.** It could keep trying to scroll an
  already-fully-visible panel (e.g. an empty Trash list) instead of falling through to scroll
  the page underneath — added a small tolerance to the "is this panel already fully shown"
  check, making it robust against minor platform differences in how scroll position is
  reported.
- **The crash-recovery handler could itself have crashed.** A module-level handler referenced
  `self` in a context where it didn't exist — if the app had ever failed to start, the intended
  friendly error dialog would itself have crashed instead of showing.
  ([the full story](docs/ISSUES_LOG.md#a-crash-handler-that-would-have-crashed-itself))

### Removed
- **~700 lines of dead code** — several old dialog-based flows (category manager, tag manager,
  duplicate finder, trash dialog, share-all dialog, import-code dialog) fully superseded by
  inline panels earlier in development but never deleted, plus a handful of smaller orphaned
  helper functions.
- **Unused `messagebox` and `colorchooser` imports**, left over from before those were replaced
  by the app's own themed dialog and color-palette systems.

### Testing
- **The manual QA plan became an automated suite.** Rebuilt the spreadsheet test plan into a
  structured set of 5 automated headless test scripts (87 checks total) plus a dedicated
  recurrence-engine test suite (18 checks), covering notes CRUD, categories, templates,
  recurrence, calendar, duplicate detection, trash, share codes, threaded import/export,
  theming, popup/panel stress testing, and data-corruption resilience.

---

## [0.3.0] — Tags removed; categories as the sole organization system

*Highlights: Tags come out entirely, leaving categories as the app's one organization system.*

### Fixed
- **The Manage Tags panel intermittently lost its content** when switching between Settings
  accordion panels — root-caused to a layout calculation that ran before the panel had actually
  become visible, using an unreliable width. Superseded by removing the feature, but the
  underlying `<Map>`-event-based fix (relaying out deterministically the moment a panel becomes
  visible, instead of guessing a timer delay) is reused elsewhere in the Settings UI.
  ([the full story](docs/ISSUES_LOG.md#the-panel-that-lost-its-content-depending-on-how-you-got-there))
- **Template editor (New/Edit) could open behind the main window**, appearing to do nothing
  when clicked. Root cause: the `-topmost` window attribute was set *after* a layout
  recalculation call, which silently failed to take effect in that order on this platform. Also
  switched the editor to the same shared, multi-monitor-safe popup positioning used everywhere
  else in the app, after its own hand-rolled positioning logic was found capable of placing it
  off-screen entirely.
  ([the full story](docs/ISSUES_LOG.md#the-template-editor-that-did-nothing-when-clicked))
- **Category deletion confirmation matches the app's own dialogs.** It was still a separate
  OS-style window rather than the app's inline themed dialogs; converted to match.

### Removed
- **The Tags feature, entirely** — the tag registry and persistence layer, all tag UI (note
  editor tag entry/chips, sidebar tag filter, Settings → Manage Tags panel), tag-based
  duplicate-merge logic, and tag fields from the share-code and data model. Categories were
  judged sufficient on their own; tags added complexity without enough distinct value to
  justify maintaining two overlapping organization systems.
- **Old notes with a leftover `tags` field load normally** — the field is silently dropped on
  next save.

---

## [0.2.0] — Inline UI overhaul & data resilience

*Highlights: Every OS-native popup becomes an in-app themed one, and the calendar grows richer.*

### Added
- **Calendar quality-of-life layer** — day-level emoji markers, hover previews per note (not
  just per day), create-note-from-calendar-day, visual separators between multiple notes shown
  in one day cell, and adaptive preview text size based on window width.
- **Emoji picker for the note editor** (title/body/comments), with categorized emoji groups.
- **Username greeting on the sidebar** ("Hi \<name\>,"), configurable in Settings.

### Changed
- **Every remaining OS-native popup converted to the app's own.** Dialogs, dropdowns, color
  pickers, and date pickers are now borderless, themed, anchored popups — nothing falls back to
  a native white Windows dialog anymore.
- **Multi-monitor dropdown positioning.** Popups now measure against the app's own window
  bounds rather than the full virtual screen, with live position tracking as the window moves,
  so a dropdown can no longer land on a different monitor than the app itself.
  ([the full story](docs/ISSUES_LOG.md#the-dropdown-that-opened-on-the-wrong-monitor))

### Fixed
- **Fast typing no longer merges with placeholder text.** A race condition in the tag and title
  entry fields could concatenate fast typing immediately after clicking with the placeholder
  text instead of replacing it.
- **Note list scrollbar always reserves its width.** It was invisible in some layouts due to
  pack ordering; the scrollbar is now packed before the canvas.
- **Several popups couldn't scroll at all.** The emoji picker, tag filter, and calendar day
  list had their mousewheel binding wired up before their content existed, so scrolling
  silently didn't work; moved the binding to after content creation throughout.
- **Autosave no longer flickers the sidebar under an open popup.** Autosave while a popup (e.g.
  the emoji picker) was open used to visibly flicker the sidebar as the note list refreshed
  underneath it; the refresh is now deferred until the popup closes.

---

## [0.1.0] — Core application

*Highlights: The founding feature set — notes, recurrence, calendar, templates, sharing, themes.*

### Added
- **Note CRUD** — create, edit, pin, duplicate, soft-delete to trash with automatic purge after
  a configurable retention window.
- **Categories** — create, rename, delete (with reassignment of affected notes), custom colors.
- **Recurring notes** — daily / weekly / monthly / yearly recurrence with custom intervals,
  specific-weekday and specific-day-of-month selection, a clamp/skip policy for month-end edge
  cases, end conditions (count or date), and per-occurrence editing/deletion separate from the
  base series.
- **Calendar view** with month navigation and jump-to-date.
- **Templates** — reusable note content, including checklist items.
- **Checklist items within a note**, with progress shown on the note's card in the list.
- **Duplicate detection** (matching on title/body/comments/category) with per-group cleanup.
- **Search and six sort modes**; grouping by category with persistent collapse state.
- **Sharing** — single or multiple notes as a compact copy-pasteable text code; full backup
  export/import as a `.zip` including attachments.
- **File attachments per note.**
- **Eight built-in themes** (four dark, four light variants).
- **Single-editor-tab design** — switching notes always autosaves the one being left, no
  explicit tab management needed.
