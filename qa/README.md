# The qa suite — read me before touching a guarded surface

Nine scripts, ~1,070 checks (the six unit suites beside them bring the
whole run to ~1,540), all driving the real app headlessly (Xvfb on
Linux CI, real Windows Tk on the Windows CI job and every dev machine).
The manual half of the QA story sits beside them:
`NoteOrganizer_TestPlan.xlsx`, the structured test plan for scenarios
easier to eyeball than to automate.

What all of it actually executes is measured: `py tools/run_coverage.py`
prints the line-coverage total, the per-file table and the largest
never-executed regions. The current baseline (81.5%), the per-layer
targets, and the ledger where every agent report's "NOT COVERED"
confession receives an explicit verdict live in
[`COVERAGE_LEDGER.md`](COVERAGE_LEDGER.md) — a confession may land
there, never scroll past.

## What each script owns

| Script | Primary ground |
|---|---|
| `qa1` | notes, categories, templates — plus the editor's heaviest surfaces: tables, rich text, the find bar, bulk actions |
| `qa2` | recurrence, calendar, duplicates |
| `qa3` | trash, sharing, import/export |
| `qa4` | theming, stress tests, leak regression — and the note list drawn a screenful at a time, with a save redrawing one card |
| `qa5` | corrupt data, edge cases |
| `qa6` | grouping, settings, attachments, multi-feature combinations |
| `qa7` | calendar delete, the calendar History register, multi-select, image preview, autosave & memory fixes |
| `qa8` | search debounce, background-timer robustness |
| `qa9` | the nested-dropdown-inside-popup fix |

Beside the GUI suite run six standalone **unit suites**, each runnable on
its own (`py test_<name>.py`, from a scratch copy like everything else):
`test_recurrence`, `test_calculator`, `test_data_safety`, `test_richtext`,
`test_tables` need no GUI; `test_entry_module_identity` builds a window —
it guards against a second copy of the entry module.

Each script's banner carries the finer print. "Primary" matters: checks
about one surface deliberately live in several files — which is the
first of two things here that are not obvious from the file names, and
both have cost a red CI run to learn:

## The seam map: one surface, many guards

A check about one UI surface does not necessarily live in "its" file.
The bulk-action bar taught this the expensive way: it was resized in a
round that updated qa1's checks — and a reconstruction-based check in
**qa7** (written months earlier) went red only on CI. **When you change
one of the surfaces below, sweep every file listed for it**, not just
the one you happen to be editing:

| Surface | Guarded in |
|---|---|
| Bulk-action bar / selection mode | **qa1**, **qa3**, qa7, qa9, qa4 |
| Theming (apply/track/toggle) | **qa1**, **qa4**, qa6 |
| Autosave (debounce, guards, flush) | **qa1**, qa7, qa8, qa5, qa6, qa3, qa2, qa4 |
| Editor page scroll/canvas | **qa1**, **qa8**, qa6 |
| Note list (refresh, scroll guards, grouping) | **qa1**, **qa4**, qa7, qa6, qa3, qa8, qa2, qa9, qa5 |
| Tables / drawn grids | **qa1**, qa7, qa2, qa5, qa3, qa6 |
| Find in note (Ctrl+F) / find bar | **qa1**, qa5 |
| Templates | **qa9**, **qa1**, qa6, qa3, qa7, qa4 |
| Settings panels | **qa6**, qa3, qa4, qa9, qa2, qa7, qa1 |
| Calendar | **qa7**, qa4, qa2, qa1, qa5, qa6, qa9, qa8, qa3 |
| Trash | **qa3**, **qa6**, qa7, qa2, qa1, qa4, qa5, qa9 |
| Share codes | **qa3**, qa1, qa5 |
| Export (files, backup) | **qa3**, **qa1**, qa6, qa8, qa4, qa9, qa5, qa7 |
| Attachments | **qa7**, qa6, qa3, qa1, qa4, qa8, qa2, qa5 |
| Recurrence / occurrences | **qa7**, **qa2**, qa3, qa1, qa8, qa5, qa4, qa6, qa9 |
| Checklist | **qa1**, qa3, qa7, qa6, qa2, qa4, qa5, qa9, qa8 |
| Formatting / rich text | **qa1**, qa3, qa2, qa9, qa7, qa6 |

Bold = the heavy owner(s): a file carrying at least a quarter of a
surface's mentions, or leading the next one by more than double.

**Regenerate it rather than editing it** — `py tools/regen_seam_map.py`
prints the table above, plus the raw per-file counts it came from. The
table used to be refreshed by hand and drifted through three audit
rounds without anyone re-running it (coverage-ledger C8): three whole
surfaces were missing — recurrence/occurrences, the checklist and rich
text — and several rows named fewer files than actually guard them, so
a sweep that trusted it would have skipped exactly the file that went
red on CI last time. Counts are mentions, not checks; they say where a
surface is *touched*, which is what a sweep needs.

## Running anything here

**Never in place.** Every script wipes `*.json` and `attachments/` in
its working directory first — run from the project root, that is the
real notebook (it has happened; see [CLAUDE.md](../CLAUDE.md),
"QA testing safety").
`py tools/run_tests.py` does the whole safe-scratch ritual for you and
is the verdict that counts before a push; `py tools/pre_push_check.py`
is the two-second static half (names, API surface, compile-all) you
run before *every* push. The CI's **Linux leg** runs locally too, via
Docker (`tools/linux-ci/` — build once, then
`docker run --rm -v "${PWD}:/repo:ro" noteorg-linux-ci`), so the
Xvfb-only behaviours that used to surface as red CI runs can be caught
before the push.

## Stories: the app walked, not questioned

`py qa/story_note_travels.py` is a different kind of check, and it exists
because of a specific failure. Four user-visible bugs shipped in
`0.73.159` and `0.73.161`; a field test found all four in twenty minutes,
and not one of them was reachable by the suite as it stood — not because
the suite was thin, but because each needed something a question cannot
express:

| What the bug needed | Why no check had it |
|---|---|
| a **restart** between two steps | every check lived in one process |
| a **sequence** (make a code, then open another note, then look) | checks assert a state, not a path |
| a **second visit** to a page | nothing arrived anywhere twice |
| a **what-happens-next** (update, then carry on typing) | the check ended at the update |

A story fixes that by walking one thing a person does, from end to end,
pressing the buttons they press — the note card, `📋 Generate code`, the
dialog's own buttons — with each chapter in **its own process**, so
"close the app and open it again" is real rather than simulated. It
photographs the screen as it goes, and the pictures are meant to be
looked at: two bugs in this project were invisible in the source and
obvious in a photograph.

Two rules learned writing the first one, both by being burned:

- **Press the button by its whole name.** A loose search for `Import`
  found the sidebar's `📥 Import code` and closed the panel; the story
  then reported that the app had asked nothing. A story that presses the
  wrong button accuses the app of its own mistake.
- **Answer a blocking dialog from inside the wait.** The themed dialog
  waits on a variable, so nothing after the click runs until an answer
  arrives — which is also the only moment the question is on screen to be
  photographed.

A story is only worth its runtime if it would have caught the thing it
was written for, so each of the four bugs was **put back** and the story
walked again: all four turned it red, naming the step that broke. That
is the bar for adding another one.

Stories are slow by nature (a real window per chapter, seconds not
milliseconds), so they are not in `tools/run_tests.py`. Run them before
calling a user-facing feature done.

## Photographs: did a screen change shape while nobody was looking?

`py qa/story_look.py` opens the app on a fixed little notebook,
photographs six screens — the list, the editor, the calendar, two
Settings sections and a light theme — and compares each against the copy
in `qa/screens/`. Those copies are committed, so a change of appearance
shows up in a diff like any other change.

It does not say "this is wrong"; it cannot know that. It says **this
changed, and nobody said it would**, which is the honest half a script
can do. Approve a change you asked for with
`py qa/story_look.py --accept`.

Deliberately coarse: each picture is reduced to a small grid before
comparing, so a pixel of text rendering is not a finding while a moved
control is. Two identical runs report 0.0%. Shrinking one heading by
five points reported three screens changed, 6.6–10.9% each, and left the
two it could not affect at 0.0% — which is what "coarse but not blind"
has to look like before the tool is worth running.

## The surface inventory: what every new feature is walked against

The complete list of the app's functionality surfaces. Before a feature
or improvement is built, **every row gets an explicit verdict** in the
interaction pass (see CLAUDE.md, "Cross-feature verification"):
`none` / `touches` / `risky — with the weaving decision`. Walking all of
it is what makes "we thought of everything" checkable rather than felt.
A new surface joins this list the moment it ships.

- **Data & lifecycle:** save/load + `normalize_note` · autosave
  (debounce, flush, note switch, close) · undo/redo · Trash & restore ·
  duplicates · templates · data dir & migrations
- **Editor:** rich text (character styles) · paragraph formatting
  (lists, indent, alignment) · font size/family · tables (grid, cells,
  merges, widths, checkboxes, caption) · checklist · calculator ·
  comments · attachments · emoji picker · find-in-note · word count &
  reading time · Expand toggles · caret/scroll & view restore
- **Organization:** sidebar search · sort modes · categories · grouping ·
  pinning · multi-select & bulk bar · note list rendering & scroll guards ·
  the note list's keyboard route (focus ring, ↑/↓ walk, Enter, menu key,
  focus restored across a rebuild) · remembered sort & filter
- **Time:** date field · recurrence · calendar (view, day colours, day
  markers with their cap, preview) · a day cell's note chips as notes
  (click opens, right-click gives the note's menu, hover previews one) ·
  calendar History register (search incl. override content, year chips,
  collapsible series groups, pagination)
- **In/out:** clipboard in (rich, plain, TSV) · clipboard out (HTML,
  TSV) · share codes · single-note export (HTML, TXT) · backup `.zip`
  export/import · background threading
- **Shell:** theming (both patterns, canvas repaints) · popups & dialogs
  (positioning, multi-monitor) · the toast banner, plain and carrying an
  action (Undo) · keyboard shortcuts · Settings page · statistics ·
  open-note tabs · window sizing
- **Standing invariants:** plain text is the store · `core/` never
  imports tkinter · the worker thread never touches a widget · offsets
  counted in characters · any-script input · fast on weak machines ·
  the built `.exe` and `%APPDATA%`

## House rules for new checks

- A new feature's checks land **with the feature**, covering its seams
  with the old features — not after a field test finds the gap.
- Every new check is **mutation-tested**: break the mechanism it
  guards, watch it fail, then trust it. Old checks go stale silently —
  see the [Issues Log](../docs/ISSUES_LOG.md), "The teeth that had gone
  dull"; the fixes documented there are a ready-made mutant catalogue
  for periodic audits. And a mutant run's verdict counts **only if the
  suite ran to completion** — check for the script's FAILURES footer,
  never just grep for FAIL lines: a mutant that crashes the import
  prints no failures at all, and reads as "survived nothing" when it
  really ran nothing (this exact false-clean happened here once).
- **A check that can be decided by how fast the code above it runs is
  measuring the machine.** The sidebar search debounces with
  `after(180, refresh_note_list)`, and a full rebuild puts every card
  and header back correctly — so that timer repairs whatever a surgical
  update got wrong, and a check reading the result afterwards reports it
  as right. It had been doing exactly that for months: qa7's
  "switching notes does NOT rebuild the list" passed because the work
  ahead of it was slow enough for the timer to have always fired
  already. When deleting a note stopped rebuilding the whole list
  (185ms → 31ms) the slack vanished, the timer landed *between* the two
  readings, and the check went red with nothing wrong. Worse, in the
  same window a mutant **survived under load and died when run alone** —
  the timer had rebuilt the list and undone the damage.
  **Settle every timer that can rebuild what you are about to measure,
  and assert that they are settled** (`_flush_autosave()`, cancel
  `_search_debounce_job`), so the reading is about its subject. A check
  that only passes on a fast machine — or only on a slow one — has not
  been written yet.

  The list's scroll has a **third** timer, and it is not a debounce:
  `_restore_list_scroll` stays in force for 400ms and re-applies itself
  at 60, 160 and 360, because a rebuilt list's geometry settles over
  several passes and each one re-clamps the canvas. A `yview_moveto`
  made inside that window is simply put back — measured, with `yview`
  reading bit-for-bit identical before and after the move. The app says
  what beats it: `_list_scrollbar_moved` clears `_list_restore_px`
  because "a deliberate drag beats a rebuild's still-pending restore",
  so a test that positions the view does the same.
- **A fixture that does not do what its name says turns a
  measurement into a rumour.** A script studying the note checkboxes
  called `_toggle_note_selected` — which updates the set of selected ids
  — instead of invoking the widget, which is what actually moves a
  checkbox. Every box in the resulting photograph was empty, and a whole
  diagnosis was built on it: pixel measurements, a table of candidate
  colours, a conclusion, and a change to twelve call sites. All of it
  wrong, and none of it visibly wrong. **Assert the state you set up**,
  in the fixture, before measuring anything from it: one line checking
  that a box really is ticked would have caught it before the first
  number was written down.

  A quieter instance of the same rule: a fixture can be *accidentally
  indistinguishable* from what it is meant to contrast with. The bulk
  category checks seed notes and then move them, and the undo is supposed
  to put each note's `updated` stamp back — but notes created a moment
  earlier carry a stamp equal to the change's own, to the second, so the
  mutant that removed the restore entirely changed nothing the suite could
  see. The fixture now seeds an explicit **old** stamp and checks that it
  did. Where a check compares a value before and after, make sure the
  fixture's value could not have been the answer by coincidence.
- **If the point is that the app ASKED for something, look for the
  request, not the result.** A check that the checklist undo persists
  reached disk by calling `_flush_autosave()` — which saves whatever the
  editor holds whether anything asked it to or not — so removing the
  undo's own `_schedule_autosave()` changed nothing it could see. The
  check now looks for the queued job. A forcing call in a check proves the
  forcing call works.

  **This one recurred, which is why it is worth re-reading before writing
  any save check.** The new "a pasted date is saved" check called
  `_flush_autosave()` and then read the store — and survived the mutant
  that removed the paste's save binding outright. Identical shape, six
  rules further down the same page, written by someone who had read it.
  It now asserts the queued job AND, separately, waits for the app's own
  timer to put the value in the store; the mutant kills both.
- **A check that counts on an action CREATING something assumes no timer
  beat it to it.** "...the overtyped note really was saved" proved the
  save by watching `len(app.notes)` go up by one — true only while the
  500ms autosave has not already created the note, in which case the
  explicit save merely updates and the count never moves. Green on a
  developer machine, red on CI. Prove the outcome by **identity** — the
  note the editor points at, and its stored content — so create and
  update both satisfy it and only a real failure does not.

  Two things that came with it. A slow machine is reproducible: pause
  long enough for the timer to fire and the red appears locally, which is
  how the diagnosis was confirmed instead of guessed. And a mutant that
  aborts the script before the check runs is **not** a surviving mutant —
  a 2-second run with one unrelated failure means the suite never reached
  the line. Read the timing and the failure count, not just the absence
  of the name.
- **"A timer is pending" is a fact about a MOMENT, and the moment can pass
  inside your own `update()`.** Four checks asserted a save had been asked
  for by reading `_autosave_job is not None`. Between the action and the
  read sits an `app.update()`, and on a loaded runner that can outlast the
  500ms debounce: the timer fires, the job is cleared, and the check
  reports a missing request about an app that made one. One of them went
  red on CI while passing here three times running. **Ask for "pending OR
  already fired"** — both answer the promise, and together they cannot be
  decided by speed. Proved rather than argued: pausing past the debounce
  turns the old form red on an unmodified app.

  Two traps met while fixing it, both worth knowing. **Replacing
  `_schedule_autosave` on the instance catches nothing** — every binding
  captured the bound method when it was bound, long before, so they still
  call the original. What the timer captures at SCHEDULE time is
  `_autosave_now`, so that is the one to replace, and it has to be
  replaced before the action. And **clear any pending save first, and
  assert it is clear**: without that the check passes on a job left over
  from something earlier in the same script, which is exactly how one of
  these survived the mutant that deleted the binding it guards.
- **Never decide from `focus_get()` whether something has the keyboard.**
  It answers `None` whenever the process does not own the desktop
  foreground — already measured here on the Ctrl+F checks, and true of a
  real window for a moment after any other program comes to the front. A
  guard reading `focus_get() is None` as "nothing has the keyboard" fires
  in exactly the case where something does: the note list's focus restore
  shipped that way and could pull the keyboard out of the title box mid
  typing. **Record what happened as it happens** — a `<FocusIn>` /
  `<FocusOut>` pair on the widgets that can hold it — and read the record.

  Two things that made this hard to see, both worth copying. The first
  probe ran with the foreground held, so it exercised the safe branch and
  proved nothing; forcing `focus_get` to answer `None` is what reproduced
  it. And the check compared the focused widget against a list of cards
  captured BEFORE the rebuild — which destroyed them — so `where in cards`
  was False for the new card that now held the keyboard, and the check
  passed while the theft happened. Ask by a marker on the widget, never by
  identity against something the code under test is about to replace.
- **A photograph of a focus ring is a photograph of the desktop foreground.**
  Tk draws a widget's `highlightcolor` only while its toplevel really owns
  the foreground, so `focus_set()` on a card records the focus and draws
  nothing if another process is in front. `story_look` runs PowerShell
  between scenes to make each grab, and that process can hold the
  foreground when the next scene starts — so the focus-ring scene lost its
  ring about one run in three, 0.6% apart, reported as a change of shape.
  It passed often enough that the first sighting was written down as
  "observed, not diagnosed" and the next re-run went green — which is how
  a flake gets a second life. The fix is `focus_force()` on the window
  **before** `focus_set()` on the
  card; the other order moves the focus off the card and loses the ring
  every time, turning the flake into a certainty. Found by opening the
  failing picture beside the reference — the ring was simply not there.
- **A `Toplevel` parented to a widget JOINS that widget's tree, and on a
  headless display the pointer never moves.** A hover preview created as
  `tk.Toplevel(row)` appears in `row.winfo_children()`, so it lands inside
  the panel the row belongs to — where a theme sweep, the wheel binding
  and any check counting what is on screen all meet it. qa3 counts the
  trash rows by walking the panel, and CI went red on two pull requests
  while the same script passed on a desktop and on the local Linux image:
  on a headless display the pointer sits still over whatever gets drawn
  under it, so one row's preview opened every run and was counted as an
  extra row. On a desktop the pointer is somewhere else and it never
  happened once. **Parent a floating window to `winfo_toplevel()`**, and
  when a check looks for one, find it by being NEW rather than by being a
  child of the thing it describes.

  The second half is the part worth carrying: *"it passes on my machine
  and on my own Linux image"* is not the same claim as *"it passes"*. The
  pointer's resting position is a hidden input, and it is the one input a
  developer's machine can never reproduce.
- **`winfo_ismapped()` is False for a moment after packing, and code that
  asks it will skip the widget you just packed.** `toggle_settings_panel`
  hides whichever section is showing by looping over the panels and
  unpacking the mapped one. Called straight after `show_settings_page()`
  with no `update()` between, the previous section is packed but not yet
  mapped, the loop skips it, and BOTH sections end up on screen — a
  reference photograph came out with Recently deleted stacked under a nav
  reading Templates. A person never hits this, because a click always
  arrives after Tk has drawn. A script does. **Put an `update()` between
  showing a thing and selecting within it**, and the same applies to any
  check reading `winfo_ismapped` to decide what is on screen. Sibling of
  the chip that looked clickable, in the Issues Log.
- **A check about an ABSENCE must name the thing that would actually be
  there.** `check('the comments box is deliberately not persisted',
  'comments_expanded' not in NO.load_settings())` could never have failed:
  the key the helper would write is `editor_comments_expanded`, and
  `comments_expanded` was never a candidate for it. The check asserted the
  absence of a name nothing would ever create, and stayed green straight
  through the change that made the box persist — which is how it was found,
  rather than by anyone reading it. Sibling of the rule that a probe whose
  finding is an absence needs a control producing the presence: here the
  control would have been writing the key and watching the check go red.
- **`_qa_click` cannot press a `tk.Button`.** It fires `<Button-1>`, and a
  button runs its command from `<ButtonRelease-1>` — which is why this file
  presses buttons with `.invoke()` in eighty-odd places. Measured while
  writing the share-panel checks: a bare release does not reach it either,
  nor does a generated press+release. Half an hour went into diagnosing an
  app bug that was the wrong tool. Generated clicks are for widgets that
  bind `<Button-1>` themselves (labels, canvases, list rows); a real button
  gets `.invoke()`.
- **A paste does not replace the selection on X11.** Tk's Entry paste
  deletes the selected text only on non-X11 platforms; on X11 it inserts at
  the caret and leaves the selection in place. A check that did
  `select_range(0, 'end')` then `<<Paste>>` passed on Windows and failed on
  the Linux image with the field holding both values. The app ships on
  Windows, so this is the test's problem and not the product's — clear the
  field with `delete(0, 'end')` when what is being checked is what landed,
  and reach for the selection only when the selection itself is the subject.
- **A length is a weaker question than the content, and a cap makes the
  two look alike.** A new check for the title's paste cap read
  `len(title.get()) == TITLE_MAX_LEN` after pasting something far too
  long. It survived two mutants: with the bug present the field held the
  placeholder `Note title...` plus `TITLE_MAX_LEN - 13` q's, which is
  `TITLE_MAX_LEN` characters exactly. The right length, and the first
  thirteen characters were somebody else's text. Anywhere a limit clips
  the result, the size is the one property the bug preserves — assert what
  the field HOLDS (`get() == 'q' * CAP`), not how much of it there is.
  Sibling of the count that was satisfied by the wrong answer of the same
  size, two rules above.
- **Reach the widget the user reaches, not the handler behind it.** qa1
  had covered pasting an over-long title since the cap shipped — by
  calling `app._on_title_paste()` directly, on a field it had emptied
  first. Both of those made it pass while the real route was broken: a
  right-click Paste arrives as `event_generate("<<Paste>>")` on a field
  that still holds its placeholder, and the pasted text landed glued to
  the hint text. A check that calls the handler proves the handler. Where
  a binding, a placeholder, a validator or a menu sits between the user
  and the function, drive the outermost thing the app itself drives —
  here, the same virtual event the app's own menu sends.
- **The note list is a drawing, drawn a screenful at a time.** Three
  things every check about the list has to know.

  A card has no widgets to read. Ask the app what it drew:
  `_card_view(id)` (texts, fills, ring, tick, where it stands),
  `_header_view(cat)`, `_card_order()` (screen order), `_card_point(id)`
  (where a click on it lands, for a real `<Button-1>` on `app.canvas`).
  Whether a card was *redrawn* is the identity of its canvas items —
  `_note_cards[id]['items']['bg']` — which a move keeps and a redraw
  replaces, as a widget's path used to.

  A card beyond the first `LIST_FIRST_DRAW` rows does not exist until the
  view comes near it: a check about such a card draws it first, the way
  scrolling would (`_draw_list_rows` until it is there), and says so.
  Whether a note lands in the first screenful can hinge on the second its
  fixture was made in, because Recently updated sorts by that stamp — one
  of qa1's checks passed a run and failed the next on exactly that.

  And the ring's colour means two things (the text colour where the list
  holds the keyboard, accent for the open note), so a check about "the
  open note is highlighted" first forces the keyboard somewhere else. Two
  older checks asked for the ring's *thickness* — two pixels, which every
  card has — and could not fail at all. A property every candidate shares
  cannot tell them apart.
- **A widget clipped by its window still reports its full height.** The
  check for the window's smallest size first asked whether the note
  list's `winfo_height()` could hold a card, and passed at the old,
  broken 500x400: pack had given the list its requested 354px, running
  past the bottom of the window, while the New Note button was drawn
  over the card. The mutant restoring the old minimum survived it. What
  shows is a question about where things ARE: compare screen
  coordinates (`winfo_rooty()` + height) against the window's edge and
  the next widget's top.
- **A red that loses its name costs a day, so the runner writes it down.**
  `tools/run_tests.py` saves a failing run's whole output to
  `%TEMP%/notesorg-failure-<label>.txt` and prints the path — the terminal
  shows a summary, and a summary is what a piped `tail` throws away. The
  static gates had this and the qa half did not, which is how a rare qa3
  red during a full run went undiagnosed: the names scrolled past, the
  next run was green, and there was nothing left to read. **When a check
  goes red, open that file before re-running anything.** Re-running is
  how a flake escapes.
- **Every app a check builds answers its own dialogs, before it handles
  one event.** The startup notice is scheduled 250ms after the window and
  blocks until someone presses OK; nobody does in a test. qa1 built three
  fresh apps that answered nothing, and was lucky for months that there
  was nothing to announce — until a fixture's note filed under a category
  the settings never had ('Zeta') met a fix that now brings such a
  category back and says so. The script hung for ten minutes, and the
  runner, which did not survive a timeout, never ran the eight suites
  after it. qa8 does it right in all twelve places:
  `app.show_info = lambda *a, **k: True` on the line after the constructor.
  A hang is reported now as that script's failure, with its last printed
  lines, and the run goes on.
- **Assert the app's DECISION, not the arrival, wherever the promise is
  about focus.** `focus_get()` needs the process to own the desktop
  foreground, which a test run never does; measured, it answers 100/100
  when the window happens to hold it and nothing at all when it does not.
  So a check that polls it reports a false red about an app that placed
  the focus correctly. Wrap `tk.Misc.focus_set`, record which widget was
  asked for, and assert that — synchronously, and it cannot flake. The
  table-insert check has done this since C11b; the Ctrl+F one was the
  sibling it was never applied to.

  Keep the waiting helpers for what they are genuinely for: establishing
  a precondition before generating a real keystroke, where the focus must
  actually have arrived. There, force it with `take_focus` and assert it
  took — do not assert an arrival nobody forced.
- **For a change that is about how something LOOKS, take the picture.** The
  measurement for C-6 said the sweeping cleanup button was "quieter" than
  its neighbour — a different fill, a smaller font. The photograph said it
  did not read as a button at all: it blended into the panel behind it. The
  numbers were right and the conclusion they supported was too small, so
  the fix moved the size and padding as well as the colour. A before/after
  pair costs one scratch script (stage the panel, `ImageGrab` the window)
  and the "before" is taken by putting the old code back in a `finally`,
  exactly as a mutant runner does.
- **When a check's finding is an ABSENCE, it needs a control that produces
  the presence.** "I generated an Escape and the popup did not close" is
  equally consistent with the bug and with a harness that cannot deliver
  the key — and Tk delivers a generated keypress to the FOCUS window, not
  to the widget it was aimed at, which is why `fire()` refuses keyboard
  sequences outright. The probe that established C-7 forced the focus
  *inside* the popup and watched Escape close it; that one reading is what
  makes the silence a fact about focus rather than about the probe. Without
  it the file is a rumour with a conclusion attached.
- **An undo's guard is checked against the state its own action produced.**
  The day-clear undo first asked "is what is there now equal to what I am
  about to restore?", which catches a second click on the toast and nothing
  else — a marker chosen by hand in the seconds since is not equal, so the
  undo overwrote it. The clear left the slot **empty**, so an empty slot is
  the only state the offer fits. When writing checks for an undo, include
  the case where someone put something else there in between; it is one of
  the five questions in CLAUDE.md's quality bar, and it is the one that
  finds this.
- **Prove an undo on the screen as well as in the store.** A check that
  reads the calendar cell's own background is what stops a version which
  repairs the data and forgets to repaint. Asserting the model alone passes
  a half-done fix.
- **A check that asserts a COUNT is satisfied by any wrong answer of the
  same size.** Inverting the retention window's comparison still left one
  doomed entry in a two-entry fixture — the other one — so a check reading
  "1 note older than 7 days" passed over a mechanism that had been turned
  inside out. Assert *which*, not how many, wherever identity is the point.
  And pick fixture values that can only be explained one way: a note
  deleted a day ago sits exactly on the one-day boundary and reads as
  expired whether or not the clamp works, while twelve hours tells the two
  apart. Three of that block's ten checks were satisfied by a boundary
  coincidence like this one.
- **Never read a verdict out of output that can be truncated without
  saying so.** `tools/run_tests.py` prints the first eight failing checks.
  Two live mutants read as survivors because the checks they broke were the
  ninth and later: the names the runner searched for were never printed,
  and a tool whose whole job is to say "this check has teeth" said the
  opposite of the truth. Pass `--all-failures` when a script is reading the
  output, and treat a list you can see was cut as no answer at all.
- **A mutant that leaves no visible damage is telling you where the damage
  really is.** Removing the checklist undo's identity guard left the other
  note's list untouched, because the insert goes into the captured list,
  which is orphaned once the editor moves on. Nothing is corrupted; what
  is wrong is the status line claiming the item was put back. Before
  rewriting a mutant, ask what the broken code actually does — the answer
  names the check that was missing.
- **Never hold a widget across something that rebuilds.** A reference
  found before a resize, a theme switch or a note-list refresh can name
  a widget that no longer exists by the time it is used, and Tk answers
  "bad window path name" — which **kills the script** rather than
  failing a check, and a dead script reports no failures at all. qa6
  held a Statistics chip across `app.geometry(...)`; the panel is
  destroyed and rebuilt on every list refresh while Settings is open, so
  the reference was a coin toss. It had always been one, and only began
  landing wrong when gating that redraw on whether Settings is open
  moved WHEN the rebuild happens: two runs in four on Linux, none on
  Windows, none at all before the change. **Find it again immediately
  before using it**, and never index `find_all(...)[0]` without
  asserting there is something there.
- **Say out loud what the check needs to be true, or it will one day be
  true of nothing.** The same scroll check asserted that a delete does
  not move the list — with twelve cards in a tall window there was
  nothing to scroll, `canvasy(0)` was 0 before and after, and it passed
  on a tautology. It went red on CI, where the geometry differs, and the
  red was right twice over: the list did scroll there, and the check had
  also been scrolled to the BOTTOM, where removing a card must move the
  view. It now asserts that the list is long enough to scroll and that
  the view is away from the top *before* it measures anything. Reproduce
  a CI-only failure locally before fixing it — `tools/linux-ci/` is one
  docker command, and it showed both faults in ten seconds.
- **A surviving mutant is a question, not a verdict.** When a promise is
  held by two independent mechanisms, breaking one leaves the check
  green — and the honest reading is "I broke the wrong thing", not "the
  check is dead". The delete toast's *no second copy on a second click*
  took three simultaneous edits to make fail: the toast forgetting its
  offer, `_hide_toast` forgetting it again, and the restore taking its
  entry out of the trash. Two wrong guesses came first, and both would
  have read as a dead check to anyone who stopped at the first.
- Windows-specific pixel checks assert on `sys.platform == 'win32'`
  only (fonts differ on Xvfb), and the Windows CI job is what makes
  them bite remotely — never delete the assertion, aim it.
- Timing-sensitive measurements wait for the **promised state** (five
  consecutive reads inside the asserted band, with a hard cap), never
  for generic stability or a fixed window — the app's view-restore
  choreography re-pins on timers up to 360ms, and "any stable value"
  can certify the pause between a late yank and the re-pin that
  corrects it (the push-down check flaked exactly that way, twice
  settled wrongly before this pattern). A real regression parks
  outside the band, the band is never entered, and the cap expires
  into a hard failure — prove that asymmetry under the mutant before
  trusting the check.
- The promise's **preconditions are content-addressed and asserted**,
  never assumed from a fraction: `yview_moveto(0.3)` lands on a
  different LINE per font metric (on the CI's Xvfb fonts, eight tall
  grids kept it inside line 1 — above the edit the check was about, so
  its +1 promise didn't even apply and the app was right to "fail" it).
  Scroll to an index (`yview('15.0')`), settle, then `check()` the
  precondition itself with its numbers in the message.
- The promise's **baseline settles first** (qa1's `settled()` helper:
  one value held for 500ms straight — longer than any restore timer —
  capped). The push-down check failed a *fourth* time with its
  promised-state wait already in place, because the baseline it
  promised `+1` against had been read mid-settle; a promise measured
  against a moving reference targets the wrong value no matter how
  well the wait afterwards is built. Failure messages carry the
  expected and landed values, so the next red names its mechanism.
- **Tk hands back the sequences it NORMALISED, not the ones you bound.**
  `bind("<Return>")` reads back from `widget.bind()` as `<Key-Return>`;
  `<space>` as `<Key-space>`; `<Shift-F10>` as `<Shift-Key-F10>`. A check
  that asks a widget what it binds and compares against the binding
  spelling matches nothing and reads as "everything is unnamed". The
  qa6 check that requires every key a note card binds to appear on the
  shortcuts page caught its own version of this on its first run, which
  is the argument for asking the widget rather than a hand-written list.
- **A cap in CHARACTERS is not a width.** `preview_src[:40]`,
  `_truncate(title, 42)` and friends keep a string short; they do not
  keep it inside a box. Forty narrow characters fit where forty wide
  ones do not, so a 39-character body still ran off the edge of a note
  card. Where a label is stretched by its parent (`fill="x"`), the only
  number that cannot disagree with the layout is the label's own width —
  `_wrap_to_own_width`. Where a label sizes itself (`side="left"` with
  no fill, inside a popup that grows), that helper is the wrong tool and
  its docstring says so.
- **`anchor` places the block, `justify` places the lines inside it.**
  A single-line Label looks identical either way, so `justify` is
  invisible until something makes the text wrap — and then Tk CENTRES
  the second line by default, with `anchor="w"` doing nothing about it.
  Any change that introduces wrapping has to set `justify="left"` in the
  same edit. Found in a photograph; unreachable by reading.
- **A "bless what is on screen" tool must bless only what CHANGED.**
  `story_look --accept` copied every picture it had just taken, and a
  PNG re-encoded from identical pixels is a different file — so
  accepting one new scene rewrote all sixteen references and put fifteen
  binary blobs into a commit about something else. Comparing the bytes
  does not fix it, for the same reason. It now blesses exactly what the
  report calls changed, from one shared threshold, so "accepted" and
  "CHANGED" cannot disagree.
- A failure gets a **permanent fix, at the root of its class**: when a
  check fails without a real regression, the check's *strategy* is
  wrong — fix the strategy, sweep the suite for every sibling using
  the same strategy, and record the lesson here. After the fix, the
  check may fail only when the promised behaviour is actually broken.
- **A path-based check asserts the invariant, not a fixed result** —
  the suite runs on Windows AND Linux, and the same string is a
  different path on each: `"C:\\x"` is a drive path on Windows but a
  plain (contained) filename on Linux, `\` separates only on Windows.
  A guard check must assert what's true on both — "never raises, and
  never returns a path outside the folder" — not "returns None for this
  specific input", which passed on Windows and went red on Linux CI.
  Use a value that escapes on every platform (a forward-slash
  `../../x`, or `os.path.relpath` to a sibling) when you need a
  guaranteed-None case.
- **Where a safety net masks the mechanism, assert the mechanism.** A
  fallback that repairs the symptom makes behaviour checks lie: the
  theming straggler pass repainted an UNTRACKED frame's fill, and the
  stock dark/light themes share an accent hex, so a both-themes
  behaviour check stayed green with the tracking deleted. Such a check
  asserts the registration itself (membership in `themed_widgets`)
  alongside the behaviour — and distrust any palette pair sharing a
  hex: it can vouch for nothing. The full story:
  ["The safety net that hid the missing mechanism"](../docs/ISSUES_LOG.md#the-safety-net-that-hid-the-missing-mechanism).
- **Prefer recording the synchronous call over reading asynchronous
  state back.** Polling (below) tames async reads, but when the
  promise IS the decision — which button got `focus_set`, whether the
  view snapshot existed when render ran, in what ORDER capture and
  teardown happened — wrap the method, record the call, assert the
  record. Deterministic under any load, and it can pin ordering, which
  no amount of polling the end state can (qa6's dialog-focus recorder,
  qa1's capture-before-teardown spy).
- **A stale artifact in the system temp dir can green a check.** The
  OS temp outlives runs: a zip left by a PREVIOUS run satisfied
  "export produced a file" with the export's move-into-place step
  deleted. Delete (or uniquely name) every temp-path artifact BEFORE
  the action that is supposed to create it.
- **Never hand Tcl's text search an astral needle.** `search` with
  `-nocase` and a non-BMP character (any emoji) SEGFAULTS Linux Tk 8.6
  outright — no FAIL line, no footer, a dead process whose buffered
  stdout also lies about where it died (see below). The app
  pre-screens: astral queries scan in Python and convert offsets with
  `_tk_col`. A check that needs to find emoji goes through the app's
  find model, never through a raw `text.search()` call.
- **A crashed run's last printed PASS is not where it died.** Piped
  stdout is block-buffered on Linux, so a segfault throws away up to a
  buffer's worth of already-printed lines — the CI log's last PASS
  once pointed ~200 checks before the real crash site. Bisect crashes
  on the Docker mirror with `-e PYTHONUNBUFFERED=1`; trust exit codes
  and the FAILURES footer, never the visible tail of a dead process.
  `tools/run_tests.py` sets `PYTHONUNBUFFERED` for every script it runs,
  so a local run's tail is honest — that is what located the qa1 hang
  above to its line.
- **Force a precondition; read back only a promise.** The two focus
  helpers are not interchangeable, and using the waiting one where the
  forcing one belongs is a false-red generator: a bounded poll on an
  asynchronous focus read times out on a loaded machine and reports a
  red about an app that did exactly the right thing. Ask which the line
  is. "The test needs the caret in this field before it types" is a
  PRECONDITION — force it (take_focus / _take_focus). "Ctrl+F puts the
  focus in the find entry" is a PROMISE — poll for it. And where the
  promise IS the app's own synchronous decision, do not poll at all:
  wrap the method, record the call, assert the record (qa1's cell
  editor records focus_set, which cannot flake under any load). This
  cost the suite a red whose name was lost for a day
  (COVERAGE_LEDGER C11b) and two more in qa6 the day it was found. qa7's
  keyboard walk was the fourth: seven checks that passed, failed and
  passed again on the same code minutes apart, whenever someone was
  using the PC during the run. Its "Up on the first card stays put" is
  an ABSENCE, so it records the handler's decision instead of polling —
  a poll there answers yes before a wrong move could land.
- **Focus is asynchronous both ways** — granting AND clearing. A check
  about where the app put the focus polls for the promised holder
  (qa1's `focus_settles_on`, the assert-only twin of `take_focus` —
  which FORCES focus and must never wrap an assertion about the app's
  own placement, or the check turns tautological), and a check about
  focus being cleared polls for it leaving (qa6's `_focus_leaves`).
  A bare `focus_get() is widget` assert reads the old focus now and
  then, even in solo runs — that flake blocked a release cut once.
- **Never generate a POINTER event on a widget that has no native
  window.** Tk silently DISCARDS one aimed at it — and not just
  `<Button-1>`: press, release, `<B1-Motion>`, `<MouseWheel>`,
  `<Enter>`/`<Leave>` are all delivered to the window named in the
  event, so every one of them fails the same way — no error, no return
  value, the binding just never runs and every assertion after it is
  about state nothing was asked to change. A widget gets that window
  when it is first mapped, so a freshly built popup, a rebuilt row, or
  one the app has hidden is precisely the case that swallows the
  event. And popups *do* get hidden here: they are `-topmost` by
  design, so a heartbeat withdraws them whenever another program holds
  the Windows foreground — which a test process never owns, the
  terminal that launched it does. `chip.event_generate('<Button-1>')`
  was therefore asking "did the 300 ms watch tick land before my
  click?", and qa2's 3-marker cap check answered by luck for weeks:
  measured mid-run, all five chips still read `highlightthickness=0`,
  not one click delivered. Go through
  [`_qa_support.py`](_qa_support.py): `_qa_pin(NO)` once at the top
  makes popup visibility independent of the OS foreground (qa1 still
  covers the real hide/restore by driving `_popup_watch_step()` with
  both answers stubbed), and `_qa_fire(w, seq, **kw)` — with
  `_qa_click(w)` as its `<Button-1>` shorthand — asks `winfo_id()`
  first, which *creates* the window rather than waiting for one.
  KEYBOARD events are the deliberate exception, not an oversight: Tk
  hands a generated key event to whatever holds the FOCUS, wherever it
  was aimed, so `winfo_id()` on the target repairs nothing there and
  `fire()` refuses them loudly — a key event stays on raw
  `event_generate` behind the focus discipline documented below
  (take_focus / focus_settles_on / generate-and-poll); a `<<virtual>>`
  event, by contrast, is window-delivered like a pointer event and may
  go through `fire()`. Do not gate on
  `winfo_ismapped()`/`winfo_viewable()`: both read 0 for a widget
  scrolled out of a canvas and for a withdrawn-but-once-mapped popup,
  and both of those receive events perfectly well — gating on them
  refused qa6's category swatch, which simply sits below the fold of a
  scrolling panel. Delivery is what the helper guarantees; whether a
  human could have reached the widget where it sits is a separate
  question a check asserts for itself. (One place stays raw on
  purpose: qa1's dead-canvas drag, where the press's commit destroys
  the canvas and the TclError from the corpse is the point.)
- **A mocked method is un-mocked with `del app.<name>`**, which
  un-shadows the real bound method — never by re-assigning a value
  saved earlier, unless that value is the script's own top-of-file
  baseline mock. A saved "original" can itself be an earlier section's
  leaked mock: qa7 once saved-and-restored an always-`'occurrence'`
  scope prompt this way, and the leak silently shadowed the real
  method for the rest of the run.
