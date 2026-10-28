# Notable Issues Log

A narrative log of the more interesting bugs found and fixed during development — chosen
because each one taught something worth remembering, not because they were the only bugs.
Routine fixes are just commits; these are the ones with a real "why did this happen" behind
them. The standing rules many of them produced live in [ARCHITECTURE.md](ARCHITECTURE.md);
the releases they shipped in are in the [Changelog](../CHANGELOG.md). See also the
repository's [Issues](https://github.com/AlexandraMoldovan95/noteOrganizer/issues) for
day-to-day tracking.

**Who is speaking.** The stories are written by the AI agent the project is built with (Claude
Code), so a first person ("one of my own renames") is the agent. **The owner** or **she** is
Alexandra; a **field test** or **field report** is her, testing the packaged `.exe`; and
*reviewers*, *agents* or *waves* are Claude subagents unless a person is named. How the work is
divided and checked is in [How Note Organizer is built with an AI agent](AI_WORKFLOW.md).

## Start here: five stories

New to this log? Between them, these five show most of what the rest of it teaches; each
is in the table below as well.

1. [The cleanup that deleted the real notebook](#the-cleanup-that-deleted-the-real-notebook) —
   two harmless steps that together deleted the very notes they were moving, and why the safety
   rules here are categorical rather than lists of file names.
2. [The safety net that could not see the gap](#the-safety-net-that-could-not-see-the-gap) — a
   check written for one kind of bug reported the code clean while that bug was live in it.
3. [Eleven decisions about your notes, made from half the evidence](#eleven-decisions-about-your-notes-made-from-half-the-evidence)
   — a deliberate attempt to break the app, and what each automatic action had trusted too much.
4. [The list that was drawn whole, for every pause in typing](#the-list-that-was-drawn-whole-for-every-pause-in-typing)
   — measuring where the time went, then removing the cost instead of trimming around it.
5. [The click that was never delivered](#the-click-that-was-never-delivered) — a toolkit that
   drops an event in silence, and the experiment that told a flaky test from a real regression.

## The stories at a glance

| Story | The lesson | Version |
|---|---|---|
| [Importing the same backup twice](#importing-the-same-backup-twice) | Check incoming data against what exists and ask, instead of silently creating duplicates. | 0.4.0 |
| [A crash handler that would have crashed itself](#a-crash-handler-that-would-have-crashed-itself) | Error-handling code goes untested by nature — review it deliberately; depend on nothing app-internal. | 0.4.0 |
| [Files that outlived the notes they belonged to](#files-that-outlived-the-notes-they-belonged-to) | 'Delete' and 'delete forever' are different operations; name and test them as separate cases. | 0.5.0 |
| ["Recently updated" sort that couldn't tell recent apart from recent](#recently-updated-sort-that-couldnt-tell-recent-apart-from-recent) | A timestamp's precision is part of its contract with whatever sorts or compares it. | 0.28.38 |
| [A backup that assumed it had worked](#a-backup-that-assumed-it-had-worked) | A backup whose result is never checked is an assumption, not a safety net. | 0.28.38 |
| [The cleanup that deleted the real notebook](#the-cleanup-that-deleted-the-real-notebook) | Copy-then-delete-the-original must never touch a permanent store; cleanups name their exemptions explicitly. | 0.30.39 |
| [The safety test that needed its own safety](#the-safety-test-that-needed-its-own-safety) | Safety rules must be categorical, not filename lists; dangerous tests carry their own refusal. | 0.39.63 |
| [The delete that kept aiming at the wrong note](#the-delete-that-kept-aiming-at-the-wrong-note) | An operation aimed by mutating shared state lies on every cancel path — pass the target as a parameter. | 0.66.100 |
| [The guards that never reached the siblings](#the-guards-that-never-reached-the-siblings) | A safety lesson learned in one function must be swept to its siblings the same day. | 0.66.104 |
| [The share code that could delete your files](#the-share-code-that-could-delete-your-files) | Validate filesystem-bound values where they enter AND where they act; encode/decode must project the same fields. | 0.71.113 |
| [The repeat interval with no ceiling](#the-repeat-interval-with-no-ceiling) | Clamp untrusted values on both sides at the choke point — valid means valid for every consumer. | 0.71.113 |
| [The duplicate that wasn't a copy](#the-duplicate-that-wasnt-a-copy) | A "copy" that shares its source's files isn't one — the class is every route that clones a note, not the route reported. | 0.71.119 |
| [The mend that only ran on the way to disk](#the-mend-that-only-ran-on-the-way-to-disk) | A repair at one serialization boundary is a todo list for the others; and UnicodeEncodeError is a ValueError, not an OSError. | 0.71.119 |
| [The safety request the dialog never read](#the-safety-request-the-dialog-never-read) | A `**kw` wrapper that forwards a subset silently swallows the rest — callers' safety asks can be dead code for months. Recurred; "forward two more keywords" was never "stop swallowing keywords". | 0.71.119, and again after |
| [The note the editor let you make and the launcher deleted](#the-note-the-editor-let-you-make-and-the-launcher-deleted) | A predicate that enumerates a type's fields comes due silently the day someone adds one — and two that disagree is data loss waiting for its first user. | 0.71.154 |
| [Two windows, one file, and the last one to autosave wins](#two-windows-one-file-and-the-last-one-to-autosave-wins) | Full-file rewrites turn concurrency into data loss; a guard over data must fail open where its own failure would be worse. | 0.71.154 |
| [The trim that moved every colour](#the-trim-that-moved-every-colour) | When a transformation forces a second function to undo its effect, the transformation is the bug — and tidying what the user typed is a data change. | 0.71.154 |
| [The ceiling that counted the wrong thing](#the-ceiling-that-counted-the-wrong-thing) | A ceiling has to bound what the victim actually pays — and a defence at the render is a data-loss bug when the save reads its data back out of the widget. | 0.71.155 |
| [The identity that only lasted until you closed the app](#the-identity-that-only-lasted-until-you-closed-the-app) | A value computed on every read is not stored; if it must be stable, something has to write it down — and the test that proves it must survive a restart, not a function call. | 0.73.161 |
| [The code that would not say which note it was](#the-code-that-would-not-say-which-note-it-was) | A payload built from the screen carries only what is on the screen — and a checked route proves nothing about the field added to it afterwards. | 0.73.165 |
| [The undo that would have put everything in one place](#the-undo-that-would-have-put-everything-in-one-place) | An undo over many items remembers each item's own previous value; and "like the thing beside it" means asking what that thing's safety net really is. | 0.75.177 |
| [The offer that was gone before you could take it](#the-offer-that-was-gone-before-you-could-take-it) | Reassurance must never displace a one-time offer — and re-read the reason a finding gives, not just the finding. | 0.75.179 |
| [The eight failures that hid two live mutants](#the-eight-failures-that-hid-two-live-mutants) | A check asserting a count is satisfied by the wrong answer of the same size; and never read a verdict out of output that truncates silently. | 0.75.180 |
| [The finding that described a dialog nobody had opened](#the-finding-that-described-a-dialog-nobody-had-opened) | A review that only reads finds where to look but cannot decide — check a finding's reason separately from the finding, and correct a refuted row in place. | — |
| [The undo that guarded the wrong state](#the-undo-that-guarded-the-wrong-state) | An undo must test for the state its own action produced, not the one it means to restore; and sweep for what else reaches the same loss. | 0.75.181 |
| [The binding that could never fire](#the-binding-that-could-never-fire) | A binding is not an answer to "does this key work" — ask where the key goes; and a probe whose finding is an absence needs a control that produces the presence. | 0.75.183 |
| [Eleven decisions about your notes, made from half the evidence](#eleven-decisions-about-your-notes-made-from-half-the-evidence) | When two files must agree, rebuild the weaker from the stronger; an automatic removal asks the strictest question there is; a dialog's promise is part of the mechanism. | 0.81.213 |
| [The backup the app could not restore](#the-backup-the-app-could-not-restore) | Every limit on reading is a promise about writing: when the app makes what it later reads, one definition checks both ends. | 0.94.379 |
| [The import the close waited for, then threw away](#the-import-the-close-waited-for-then-threw-away) | A cap on a wait is half a decision: say what happens to the work still running at the cap — and test the cleanup on the case it exists for. | 0.94.382 |
| [The figure that was not one of the ten](#the-figure-that-was-not-one-of-the-ten) | The fourth fix of one mistake is the moment for a gate that refuses the pattern, not a fifth fix by hand. | 0.95.391 |
| [The Trash that forgot its window](#the-trash-that-forgot-its-window) | "I don't know" and "the default" are different answers: carry the not-knowing in the data until a person resolves it. | 0.95.391 |
| [The Cancel that went ahead anyway](#the-cancel-that-went-ahead-anyway) | A function that can be told "no" must say so to its caller; a modal dialog holds the mouse only unless the keyboard is held too; bind the end of a widget-level record to the widget's own end. | 0.82.230 |
| [The paste that landed on top of the placeholder](#the-paste-that-landed-on-top-of-the-placeholder) | `bind()` replaces where `add="+"` accumulates, so a widget's own binding silently displaces a shared helper's; and a virtual event outranks the physical one beside it in the same bindtag. | 0.75.185 |
| [The sweep that stopped at the edge of the Settings page](#the-sweep-that-stopped-at-the-edge-of-the-settings-page) | A fix's sibling sweep must name the surfaces it did not visit; a cap in characters is not a width; and text that wraps for the first time inherits every multi-line default the widget was hiding. | 0.81.202 |
| [The seven small rows, four of which were not what they said](#the-seven-small-rows-four-of-which-were-not-what-they-said) | A suggested fix is a hypothesis about the code — four of seven were wrong about scope, premise or mechanism, each found by a grep; and a check asserting `not in` against a name the code would never write cannot fail. | 0.76.192 |
| [The guard that knew half the vocabulary](#the-guard-that-knew-half-the-vocabulary) | Before persisting a value, read what the app already does to it at runtime — a stored preference inherits every rule the live one has, including the wrong ones; and a guard written against one kind of value governs every kind sharing the variable. | 0.76.198 |
| [The template editor that "did nothing" when clicked](#the-template-editor-that-did-nothing-when-clicked) | 'Nothing happens' in a --windowed build is a real bug report — the exception was invisible. | 0.3.0 |
| [The panel that lost its content depending on how you got there](#the-panel-that-lost-its-content-depending-on-how-you-got-there) | Recalculate layout on Tk's `<Map>` event, not after a guessed delay. | 0.3.0 |
| [The scroll that stopped twice, for two different reasons](#the-scroll-that-stopped-twice-for-two-different-reasons) | Same symptom, unrelated causes — check neighbouring areas instead of assuming one fix covers all. | 0.28.38 |
| [The chip that looked clickable, and the fix that looked like it worked](#the-chip-that-looked-clickable-and-the-fix-that-looked-like-it-worked) | Tk doesn't update winfo_ismapped synchronously; when the work is cheap, skip the visibility optimization. | 0.28.38 |
| [The button that woke up with its page](#the-button-that-woke-up-with-its-page) | "Is it placed?" is not "is it on the screen?" — they part exactly when a page is hidden; and a reference picture is a claim about what is right, so look at it as the thing its name says. | 0.82.233 |
| [The DPI fix that made things worse](#the-dpi-fix-that-made-things-worse) | An unverifiable fix is a gamble — flag the uncertainty up front, revert without shame. | 0.30.38 |
| [Sharp text, measured this time](#sharp-text-measured-this-time) | The fix that failed blind was right once measured on every screen the person uses — and the trade-off measuring found belonged to her. | 0.93.374 |
| [The module that existed twice](#the-module-that-existed-twice) | 'All tests pass' only reassures if the suite can represent the failing case. | 0.32.51 |
| [The bullet that had no bullet in it](#the-bullet-that-had-no-bullet-in-it) | Text inserted between same-tagged characters inherits the tag; content, not presentation tags, decides state. | 0.34.51 |
| [The text box that was always eighty characters wide](#the-text-box-that-was-always-eighty-characters-wide) | When a check passes, ask what it would take to make it fail. | 0.38.59 |
| [The list that lost its place, twice, for two silent reasons](#the-list-that-lost-its-place-twice-for-two-silent-reasons) | 'Hard to reproduce' means unmeasured timing; instrument what the widget experiences until it's deterministic. | 0.58.82 |
| [The click that was never delivered](#the-click-that-was-never-delivered) | Tk discards a generated event aimed at a widget with no native window, in silence — and `winfo_ismapped`/`winfo_viewable` do not predict delivery. | 0.71.154 |
| [The window that closed under its own question](#the-window-that-closed-under-its-own-question) | A wait only one event can end needs every other way out to end it too — or to be refused while it waits. | 0.83.335 |
| [The click that deleted its own next command](#the-click-that-deleted-its-own-next-command) | Tk expands every script of an event before running any: ask what the same event still calls after you destroy or unbind. | 0.83.335 |
| [The Cut that arrived as a key](#the-cut-that-arrived-as-a-key) | A virtual event's binding is reached by keys too, as the key's own press: tell what happened by which binding fired, and test with the key a person presses. | 0.83.335 |
| [The table that changed shape under its own undo](#the-table-that-changed-shape-under-its-own-undo) | A recorded position is only as good as the layout it was recorded in: replay every step in the state it was recorded in. | 0.83.335 |
| [The line under a table that knew where it was, not what happened on it](#the-line-under-a-table-that-knew-where-it-was-not-what-happened-on-it) | The same text can sit on top of different undo histories: ask what changed since (a flag every change sets), never where something is. | 0.83.335 |
| [The safety net that could not see the gap](#the-safety-net-that-could-not-see-the-gap) | A gate tuned to the instances it already found certifies the ones it cannot see — worse than no gate, because the next reader trusts it. | 0.71.154 |
| [The same net, woven again](#the-same-net-woven-again--and-the-question-it-was-answering) | A wordlist answers "are any of MY words here", not "is this English" — when a check's method can only answer a narrower question than its promise, say so where the promise is made. | — |
| [The check that pinned the behaviour a release had deliberately replaced](#the-check-that-pinned-the-behaviour-a-release-had-deliberately-replaced) | When a feature changes what the app promises, the checks asserting the old promise are part of the change — and a suite that cannot run a check cannot tell you it is wrong. | — |
| [One unreadable field, and every word typed after it](#one-unreadable-field-and-every-word-typed-after-it) | A refusal the caller cannot tell from success is data loss; one bad field must not take the good ones down with it. | 0.83.335 |
| [The delete that put an older version back](#the-delete-that-put-an-older-version-back) | Code kept for a feature that no longer exists goes on doing what it did — find what it still touches. | 0.83.335 |
| [Importing the same backup twice, the second time](#importing-the-same-backup-twice-the-second-time) | Several questions guarding one change: change after the last answer; a change that changes nothing must change nothing. | 0.83.335 |
| [The category renamed in one place of six](#the-category-renamed-in-one-place-of-six) | Before renaming anything, list everything that holds the name. | 0.83.335 |
| [The Trash that gave notes back one at a time](#the-trash-that-gave-notes-back-one-at-a-time) | A write inside a loop is a quadratic waiting for its first big batch; a row's reference must still mean what it did. | 0.83.335 |
| [The day whose own words went missing](#the-day-whose-own-words-went-missing) | When a view shows one layer over another, every write must know which layer each field came from. | 0.83.335 |
| [A question holds the app three ways, and it held one](#a-question-holds-the-app-three-ways-and-it-held-one) | "Modal" is three promises — pointer, keyboard, subject; act on the subject the question named, captured before the wait. | 0.83.335 |
| [The list the note shared with the editor](#the-list-the-note-shared-with-the-editor) | Store a copy of anything you keep editing, or "is it saved?" asks the object about itself; test the route the bug took. | 0.83.335 |
| [The copy that exposed a reload](#the-copy-that-exposed-a-reload) | Removing an accidental behaviour exposes whatever leaned on it: list the routes that read what the fix changes. | 0.83.335 |
| [The turn-off that stopped every save to wait](#the-turn-off-that-stopped-every-save-to-wait) | Hold back the one value that must wait, not the save around it: stopping the whole save broke every promise it keeps. | 0.83.335 |
| [The file the app could not start beside](#the-file-the-app-could-not-start-beside) | An `except` clause is a claim about every way its call can fail: when one call is guarded in many places, write the list once and let a gate refuse a hand-written copy. | 0.83.338 |
| [A calendar that kept navigating behind the user's back](#a-calendar-that-kept-navigating-behind-the-users-back) | Changing how a page becomes visible invalidates 'is X visible' assumptions in unrelated code. | 0.5.0 |
| [The date field that either lost your edit, or wouldn't let you finish typing it](#the-date-field-that-either-lost-your-edit-or-wouldnt-let-you-finish-typing-it) | Reusing Save's validation in silent autosave turns a helpful warning into an interruption. | 0.28.38 |
| [The autosave that could interrupt you over a note that was already gone](#the-autosave-that-could-interrupt-you-over-a-note-that-was-already-gone) | A guard added to one path doesn't cover other routes into the same code. | 0.28.38 |
| [The autosave that asked questions](#the-autosave-that-asked-questions) | A background timer must never ask the user anything; dialogs happen at gestures. | 0.66.102 |
| [The day that waited for a question](#the-day-that-waited-for-a-question) | An edit that waits must be seen waiting; when where the person came from answers a question, ask it at the door, not at the exit. | 0.92.374 |
| [The username cap that took three tries](#the-username-cap-that-took-three-tries) | Never trust one validation mechanism against fast input — layer cheap redundant checks. | 0.28.38 |
| [The focus fix that broke the thing it wasn't touching](#the-focus-fix-that-broke-the-thing-it-wasnt-touching) | A fix scoped to the reported widgets can break already-working behaviour; re-test the working case. | 0.28.38 |
| [The fast-typing fix that took three tries to land safely](#the-fast-typing-fix-that-took-three-tries-to-land-safely) | Decide from what the widget contains, not event internals; boring-safe beats precise-dangerous. | 0.31.39 |
| [The paste that kept the formatting it was told to drop](#the-paste-that-kept-the-formatting-it-was-told-to-drop) | Clipboard 'plain text' isn't plain — strip whatever the app itself would read as markers. | 0.37.56 |
| [The paragraphs a PDF does not have](#the-paragraphs-a-pdf-does-not-have) | A paragraph almost never stops mid-sentence; punctuation beats width arithmetic for rejoining broken lines. | 0.38.59 |
| [The History row that re-dated the open note](#the-history-row-that-re-dated-the-open-note) | An insertion between two methods can leave the end of one inside the other; sweep for the shape, not the field. | 0.83.335 |
| [Ctrl+Z, and the formatting Tk's stack never held](#ctrlz-and-the-formatting-tks-stack-never-held) | Keep what an undo system cannot see beside it, keyed to what it does see — and measure how it groups steps first. | 0.83.335 |
| [The key that typed nothing, and the line it forgot](#the-key-that-typed-nothing-and-the-line-it-forgot) | A fix that narrows when a feature acts must re-walk its main path; ask the text what a key did, and press modifiers as keys. | 0.83.335 |
| [The bold the screen kept for later](#the-bold-the-screen-kept-for-later) | When one tag draws several properties, a change to any of them must reach it: the screen shows what was laid last. | 0.83.335 |
| [The keys that took over from Tk and dropped its first step](#the-keys-that-took-over-from-tk-and-dropped-its-first-step) | A handler that takes a key over from the toolkit takes over everything the toolkit's binding did: read it and list its steps first. | 0.95.391 |
| [The rebuild under the click](#the-rebuild-under-the-click) | Re-anchor gestures by what survives a rebuild — a line number, never a widget reference. | 0.39.63 |
| [The centring that would not save itself](#the-centring-that-would-not-save-itself) | A comparison that lists fields silently exempts whatever field is added next. | 0.39.63 |
| [The accepted cost that nobody had accepted](#the-accepted-cost-that-nobody-had-accepted) | When a docstring says 'accepted cost', check who pays it, and for what. | 0.64.95 |
| [The undo that stopped halfway](#the-undo-that-stopped-halfway) | Burst edits owe undo a boundary, redraws owe it silence; probe what Tk records. | 0.64.95 |
| [The undo that stopped halfway, the sequel](#the-undo-that-stopped-halfway-the-sequel-lists-and-the-grid-trio) | When a fix has a sibling family, audit which siblings were missed; a "drawn?" check reads real windows, not a stale dict. | 0.71.116 |
| [The table that outlived its own deletion](#the-table-that-outlived-its-own-deletion) | A cached handle to a drawn thing must prove the drawing still exists — Tk marks survive the delete that killed the widgets. | 0.71.125 |
| [The clipping that turned out to be a feature](#the-clipping-that-turned-out-to-be-a-feature) | Before fixing "wrong" behaviour, find who relies on it; the fix moved from render to parse once the ellipsis check spoke up. | 0.71.134 |
| [The table header Ctrl+Z gave back one column off](#the-table-header-ctrlz-gave-back-one-column-off) | A stack that records positions replays right only in the state it recorded in; one step never holds two states. | 0.83.335 |
| [The tidy that ate the redo](#the-tidy-that-ate-the-redo) | A side effect keyed to "the caret moved" has to ask who moved it — an undo's caret is not the person's. | 0.83.335 |
| [The selection the caret left behind](#the-selection-the-caret-left-behind) | A selection is two positions: code that moves one must say what happens to the other; an invisible selection is a trap. | 0.83.335 |
| [The paste that drew the row you were typing](#the-paste-that-drew-the-row-you-were-typing) | The app's own redraw can undo what the person is doing: a step typing does not take must follow the 'like typing' rule too. | 0.83.335 |
| [The Trash panel that took two seconds to open](#the-trash-panel-that-took-two-seconds-to-open) | Don't build and wire every row up front; render a page, reveal more on demand. | 0.4.0 |
| [The slowdown that only showed up after a long session](#the-slowdown-that-only-showed-up-after-a-long-session) | 'Slow after a while, fine at first' means unbounded growth; reproduce with a loop. | 0.4.0 |
| [Export/import freezing the app](#exportimport-freezing-the-app) | Do file I/O on a worker thread; only the main thread touches Tkinter widgets. | 0.4.0 |
| [The theme-switch flicker, and three ways not to fix it](#the-theme-switch-flicker-and-three-ways-not-to-fix-it) | Profile before reaching for rendering tricks; the fix was stopping work nothing asked for. | 0.32.49 |
| [The list that was drawn whole, for every pause in typing](#the-list-that-was-drawn-whole-for-every-pause-in-typing) | Measure where the time goes before trimming what is easy to count; before removing work that looks wasted, ask what it was doing for someone; when every symptom is the same cost seen from another side, remove the cost — six windows per card became none. | 0.82.230 |
| [The window that crawled behind its edge](#the-window-that-crawled-behind-its-edge) | When the cost is inside the toolkit and paid per step, stop taking the step until it counts — then measure what the step costs when it does nothing (here, a window class style asking Windows to repaint everything); a smooth frame over a stale picture is a judgement for the eye. | 0.82.230 |
| [The line that promised a place the card could not take](#the-line-that-promised-a-place-the-card-could-not-take) | When the screen re-sorts after an action, the end state proves nothing about what was promised during it — check the promise itself; and look at the photograph, because a green check does not see a card that is not there. | 0.82.230 |
| [The month that was two hundred windows](#the-month-that-was-two-hundred-windows) | A fix to one screen's cost is a list of its siblings; a colour a widget took by default is a colour nobody chose; and whatever the app reads from the desktop, the person at the machine feeds every test run until a test answers it. | 0.82.232 |
| [The Settings panels that stayed dark on a light theme](#the-settings-panels-that-stayed-dark-on-a-light-theme) | A computed colour is invisible to palette matching; derive it once, teach the theme switch. | 0.36.54 |
| [The title box that took three and a half seconds a keystroke](#the-title-box-that-took-three-and-a-half-seconds-a-keystroke) | Measure to isolate: the app was fine, one widget was quadratic — cap its input. | 0.36.55 |
| [The colour the door let in and the drawing could not read](#the-colour-the-door-let-in-and-the-drawing-could-not-read) | A gate defines what its readers may receive; every reader must read all it lets through, or it must narrow. | 0.83.335 |
| [Every right-click left its menu behind](#every-right-click-left-its-menu-behind) | A widget built per event needs an owner that ends it; whether a call blocks differs by platform. | 0.83.335 |
| [The dropdown that opened on the wrong monitor](#the-dropdown-that-opened-on-the-wrong-monitor) | Position popups against the app window's own bounds, not the full virtual desktop. | 0.2.0 |
| [The emoji that multiplied into squares](#the-emoji-that-multiplied-into-squares) | An off-by-one appearing only after an emoji is a units bug; audit every boundary. | 0.39.63 |
| [The backspace that ate half an emoji](#the-backspace-that-ate-half-an-emoji) | Tk's Entry deletes UTF-16 units, not characters — guard every free-text Entry, not just the one reported. | 0.66.105 |
| [The search that killed the interpreter](#the-search-that-killed-the-interpreter) | Tcl's -nocase text search segfaults on an astral needle (Linux); and a dead process's buffered stdout lies about where it died. | 0.71.125 |
| [The copy that took the row above](#the-copy-that-took-the-row-above) | Three failures in different costumes shared one cause — follow the data, not the behaviour. | 0.39.63 |
| [The version that updated itself](#the-version-that-updated-itself) | When one word names two different units, every conversion site is a latent off-by-N. | 0.55.81 |
| [Tests that always passed, no matter what](#tests-that-always-passed-no-matter-what) | Failure must change a test's exit code, not just its printed output. | 0.5.0 |
| [The pixel-perfect test that only worked on Windows](#the-pixel-perfect-test-that-only-worked-on-windows) | A pixel measurement is only as portable as its font; assert relative effects instead. | 0.28.38 |
| [A toolbar check that measured the wrong thing, three times](#a-toolbar-check-that-measured-the-wrong-thing-three-times) | A test asserting a number measured on this machine tests this machine; assert the property. | 0.36.54 |
| [The tests that borrowed the notebook](#the-tests-that-borrowed-the-notebook) | A clean directory isn't a clean world when the app imports data on first run. | 0.55.81 |
| [The fix that was dead on arrival](#the-fix-that-was-dead-on-arrival) | A test calling the method proves the method; only the user's route proves the feature. | 0.55.81 |
| [The teeth that had gone dull](#the-teeth-that-had-gone-dull) | Reintroduce the original bug occasionally — green must prove it can still go red. | 0.64.95 |
| [The safety net that hid the missing mechanism](#the-safety-net-that-hid-the-missing-mechanism) | When a fallback masks the primary mechanism, assert the mechanism — a behaviour check green under two themes proved nothing. | 0.71.125 |
| [The safety guard that read a broken notebook as empty](#the-safety-guard-that-read-a-broken-notebook-as-empty) | A safety guard's fallback must be the safe answer: "I cannot tell" means stop. | 0.83.335 |
| [The save that forgot the next one](#the-save-that-forgot-the-next-one) | A job attribute answers only for the timer it tracks: cancel, never just forget; a flake that re-runs green has a mechanism — slow the machine down and watch. | 0.83.335 |
| [The clipboard the tests shared with whoever was at the machine](#the-clipboard-the-tests-shared-with-whoever-was-at-the-machine) | A flaky check has a hidden dependency: waiting moves the race, taking the shared thing out of the test ends it. | 0.83.335 |
| [The width that was guessed](#the-width-that-was-guessed) | A layout number that must agree with a layout it cannot see is wrong the first time either changes — ask the widget; and when a measurement disagrees with a photograph, doubt the measurement. | 0.73.167 |
| [The rebuild nobody was looking at](#the-rebuild-nobody-was-looking-at) | When a new feature makes the user look somewhere new, expect a report about something that was always wrong there — measure before blaming the newest change; and a guard applied at one call site out of thirty-one is a comment, not a guard. | 0.74.169 |
| [The sentence that counted notes](#the-sentence-that-counted-notes) | When a dialog counts things, ask what one of those things can be — a repeating series is one note in the count and every occurrence in the consequence; and a guard that has only ever been asked well-formed questions has been lucky, not tested. | 0.74.170 |
| [Two ways to be invisible](#two-ways-to-be-invisible) | A layout whose last element absorbs every shortfall reports nothing and fails last — measure asked-for against given, on every font it will meet; and a fixture that does not do what its name says turns a measurement into a rumour. | 0.75.173 |
| [The rule the app already had](#the-rule-the-app-already-had) | When two screens disagree, do not pick one — ask what the rest of the app does and make the odd one out match; and read what a gesture really offers before calling it a duplicate. | 0.75.176 |
| [The list that moved under the pointer](#the-list-that-moved-under-the-pointer) | An action that moves the layout must keep the user's target under the pointer — or remember what they pointed at. | 0.83.335 |
| [The character only the drawn tables had](#the-character-only-the-drawn-tables-had) | An offset belongs to the space it was counted in: convert at every crossing, and compare in the space both sides share. | 0.83.335 |
| [The tick that took the colour of its words](#the-tick-that-took-the-colour-of-its-words) | A rule written as "always" is a measurement nobody made; judge a control by what it draws, on every theme. | 0.84.357 |
| [The copy that wrote its own table](#the-copy-that-wrote-its-own-table) | A second writer of the same thing starts as a copy and ends as a subset; when one writer exists, call it. | 0.84.357 |
| [The list that rewrote the whole note](#the-list-that-rewrote-the-whole-note) | Write only what changed: a rewrite of everything moves everything that hangs off the text — the view, the tables, the caret. | 0.84.357 |
| [Nine regressions in fifteen fixes](#nine-regressions-in-fifteen-fixes) | A fix that changes WHEN something happens must be walked through every reader of that moment, not only the route it was reported on. | 0.84.357 |
| [The border that went grey whenever it was used](#the-border-that-went-grey-whenever-it-was-used) | A check that reads the option you set proves the option, not the colour on the screen; photograph what a person sees. | 0.88.361 |
| [The heart that left a gap](#the-heart-that-left-a-gap) | An invisible character is still drawn; when the toolkit draws it badly, keep it out of what the app writes, and say what is left. | 0.89.362 |
| [Save and Delete, the same khaki](#save-and-delete-the-same-khaki) | A gate measures the pairs it was told about — walk what is on the screen; and two colours that differ only in hue are one colour to a reader who cannot see hue. | 0.89.365 |
| [Two answers to one question](#two-answers-to-one-question) | Two helpers answering one question disagree somewhere — measure them against each other; and a base theme's state map silently overrides what you configured. | 0.89.371 |
| [The icon drawn as narrow as a letter](#the-icon-drawn-as-narrow-as-a-letter) | An icon's width is the width of whichever font answered for it; where icons must line up, choose them from the range one font draws, and measure the column. | 0.96.392 |
| [The marker that was only characters](#the-marker-that-was-only-characters) | When a structure is stored as text, every route that edits text edits it: count the routes that reach it, not the ones the feature was written for. | 0.96.394 |
| [The rescue copy that outlived what it rescued](#the-rescue-copy-that-outlived-what-it-rescued) | A safety net that can be pressed later must know whether it still rescues anything, and must itself be undoable. | 0.96.395 |
| [A separator's dashes, read as a width nobody set](#a-separators-dashes-read-as-a-width-nobody-set) | When a format borrows another's syntax, the borrowed form arrives written as the other world writes it: decide whose it is where that is still known — at the way in. | 0.96.396 |
| [The safety net that measured the wrong thing](#the-safety-net-that-measured-the-wrong-thing) | A guard has to measure the harm itself, not something that usually moves with it: a proxy holds until the day the two part ways. | 0.96.401 |
| [The plain paste that read only the spreadsheet's copy](#the-plain-paste-that-read-only-the-spreadsheets-copy) | A copy written in several forms has one that is the thing itself: every paste, plain included, starts from it and drops only what it promises to. | 0.96.401 |
| [The row Excel marked inside its own table](#the-row-excel-marked-inside-its-own-table) | A stand-in for another program must say what that program says, not what we expect it to. | 0.96.401 |
| [The Trash that counted on the wall clock](#the-trash-that-counted-on-the-wall-clock) | An age is the distance between two moments, not between two clock readings; a rule that deletes must count the moments. | 0.97.405 |
| [The flicker that was a word count](#the-flicker-that-was-a-word-count) | A label whose text can come and go sizes its row by what it says; give it the height of its tallest state. | 0.97.405 |
| [Photographs of the site's pages, blank below the first screen](#photographs-of-the-sites-pages-blank-below-the-first-screen) | A photograph proves only what was on the screen when it was taken: photograph a page as a reader meets it, and give what changes it checks of its own. | the website |
| [A file with two names](#a-file-with-two-names) | When a check and the action after it each name a file, they must name it the same way: resolve once, compare what was resolved. | next |
| [A delete that trusted the Trash](#a-delete-that-trusted-the-trash) | An order that is safe only if the first step worked needs the first step's answer. | next |
| [The number too big to start](#the-number-too-big-to-start) | Code that runs before the window exists takes the safe answer for whatever it cannot read. | next |
| [The close that outran a failed save](#the-close-that-outran-a-failed-save) | A warning that something will be lost is a promise to stop before losing it. | next |
| [The preview that kept every frame](#the-preview-that-kept-every-frame) | A limit has to hold while the thing it limits is being built, not only once it is finished. | next |
| [The table drawn whole](#the-table-drawn-whole) | Anything drawn whole needs a size past which it is not drawn; outside content chooses the size. | next |
| [The Trash restored under a window it never had](#the-trash-restored-under-a-window-it-never-had) | A setting that decides what is deleted travels with the things it decides about. | next |
| [An old folder judged by one file](#an-old-folder-judged-by-one-file) | Before acting on a folder, read every file the action touches. | next |
| [The app the keyboard could reach only half of](#the-app-the-keyboard-could-reach-only-half-of) | A mouse binding is not a control; ask every page what a click can press that Tab cannot reach. And a focus ring is a claim about the screen: Windows draws none round a label. | next |
| [The plain paste with no ceiling](#the-plain-paste-with-no-ceiling) | A limit with a way round is not a limit: protect every door to what it protects. | next |
| [Round two: each fix's next door](#round-two-each-fixs-next-door) | A fix is for the behaviour, not the route it was reported on; ask every other road that reaches it. | next |
| [The photo that was a remote connection](#the-photo-that-was-a-remote-connection) | What a person sees about a file is read from the file that will open; where the safe kinds are few, list those, not the dangerous ones. | next |
| [Limits that held at the door but not after it](#limits-that-held-at-the-door-but-not-after-it) | A cap on what comes in is not a cap on what is done with it: bound the work at the limit, and everything a load keeps. | next |
| [Round three: one rescue copy, and files another program holds](#round-three-one-rescue-copy-and-files-another-program-holds) | A store with one slot keeps only the last thing put in it; and a file that could not be opened is not a file that could not be read. | next |

Smaller lessons, each once a long comment in the code, are collected
[at the end](#smaller-lessons-moved-out-of-the-code), by the name the code points with.


## Data safety & integrity

*The incidents that could cost real data — and the guards they left behind.*

### Importing the same backup twice

*([0.4.0](../CHANGELOG.md#040--performance-overhaul--test-infrastructure))*

**Symptom:** Importing an export `.zip` that overlapped with notes already present silently created duplicates, with no warning.

**Root cause:** both import paths appended every incoming note without comparing it against the notebook — merging and duplicate detection existed as two features that had never met.

**Fix:** Both import paths (pasted share-code, and full `.zip` backup) now check each incoming note against what's already there (same matching logic used for duplicate *detection* elsewhere in the app, for consistency) before merging, and ask whether to skip the ones that already exist, import everything anyway, or cancel outright.

**Takeaway:** when two features need the same judgment — "are these the same note?" — they must share the one implementation, or their answers will drift apart.

### A crash handler that would have crashed itself

*([0.4.0](../CHANGELOG.md#040--performance-overhaul--test-infrastructure))*

**Symptom:** Never actually observed in practice — found during an unrelated cleanup pass, not from a bug report.

**Root cause:** The top-level function meant to catch a catastrophic startup failure and show a friendly error dialog referenced `self` — but it's a plain module-level function, outside the app's class, where `self` doesn't exist at all. Had the app ever genuinely failed to start, this fallback path would have thrown its own, unrelated error instead of the intended message.

**Fix:** Switched the fallback to the plain standard-library dialog, which doesn't depend on any of the app's own (possibly-broken) internal state — the right choice specifically *because* this code only runs when something has already gone wrong elsewhere.

**Takeaway:** Error-handling code is easy to leave untested, because the whole point is that it only runs when something else already broke. Worth a deliberate look now and then, not just trusting it because it "looks right."

### Files that outlived the notes they belonged to

*([0.5.0](../CHANGELOG.md#050--2026-08-09) · 2026-08-09)*

**Symptom:** Attachment files were still sitting in the `attachments/` folder well after the note (or the specific attachment) they belonged to had been deleted — noticed by accident while testing an unrelated change, not from a bug report.

**Root cause:** Every place that removed an attachment or permanently deleted a note (removing a single attachment, deleting a trashed note individually, emptying the trash, and the automatic purge after the retention window) only ever removed the *reference* — the JSON entry pointing at the file — and never the file itself on disk. Four separate code paths, the same gap in every one.

**Fix:** Added one shared helper that deletes the on-disk file for a given attachment reference, and called it from all four permanent-deletion paths. Deliberately *not* called from the soft-delete (move-to-trash) path — a note in trash might still be restored, and deleting its attachment out from under it would make that restoration incomplete. Verified this distinction explicitly with a test: restoring a trashed note with an attachment must leave the file exactly where it was.

**Takeaway:** "Delete the note" and "delete the note forever" are different operations with different safe behavior, even though they can look similar at the call site. Worth naming and testing them as genuinely separate cases, not just one path with an occasional extra step.

### "Recently updated" sort that couldn't tell recent apart from recent

*([0.28.38](../CHANGELOG.md#02838--2026-08-17) · 2026-08-12)*

**Symptom:** Sorting by "Recently updated" didn't always put the note you *just* edited at the top, even though it genuinely had been saved.

**Root cause:** Every note's saved timestamp only tracked minutes, not seconds. Two notes saved within the same minute ended up with the exact same sort value — the sort couldn't tell them apart, so it silently fell back to whatever order they already happened to be in (their original creation order, since editing a note in place doesn't move it within the underlying list), not the order they were actually last touched in.

**Fix:** Added seconds to the timestamp everywhere it gets written. Checked both places that read this field first: one already trimmed to the first 16 characters before parsing (unaffected by the extra length), the other only ever read the first 10 (date only, also unaffected) — so the change was safe to make without touching either reader.

**Takeaway:** A timestamp's precision is part of its contract with anything that sorts or compares it — "close enough for display" and "fine-grained enough to break ties correctly" are two different bars, and a field can quietly fail the second while looking completely normal for the first.

### A backup that assumed it had worked

*([0.28.38](../CHANGELOG.md#02838--2026-08-17) · 2026-08-14)*

**Symptom:** Never actually observed in practice — found during a deliberate review of the app's data-safety guarantees, prompted by real (unrelated) data loss during development itself: two separate incidents where a misdirected terminal command wiped the real `notes_data.json` at the project root. Neither incident involved this code path, but they raised the right question: what *else* in this app assumes a backup succeeded without checking?

**Root cause:** When reclaiming notes from `%APPDATA%` back into a local install (one of the migration paths that runs on startup), the app backed up the local file before overwriting it with the AppData copy — but never checked the backup call's return value. A backup that silently failed (disk full, permissions, the file locked by something else) still let the overwrite proceed, with no safety copy of what was about to be replaced. Separately, the app only ever backed up `notes_data.json` before a version upgrade on the very first run ever — a normal upgrade re-reading the same file on every later run had no equivalent snapshot, even though newer code touching old data is exactly the situation a backup is for.

**Fix:** The migration path now aborts and leaves the local file untouched if its own backup fails, instead of proceeding blind. Every detected version upgrade now takes a timestamped backup first, not just the first one — kept forever, since deciding when old backups are no longer needed is the user's call, not the app's.

**Takeaway:** A backup call whose result is never checked isn't a safety net — it's an assumption wearing a safety net's clothes. Worth specifically auditing for elsewhere: any place that calls something named `backup_*` or `_timestamped_backup` should be checked for what happens on that call's *failure* path, not just its success path.

### The cleanup that deleted the real notebook

*([0.30.39](../CHANGELOG.md#03039--2026-08-18) · 2026-08-18)*

**Symptom:** After rebuilding and testing the `.exe`, it showed far fewer notes than
`python note_organizer.py` did from the project folder - as if the `.exe`'s notebook had reset
itself.

**Root cause:** Two migration steps ran automatically on import, and together they destroyed data:

- `run_migrations()` copies old notes forward from `%APPDATA%\NoteOrganizer` into wherever the
  app is currently running from (a dev checkout, or any script that does
  `import note_organizer`). On its own this is safe - it only copies.
- `purge_stale_copies()` then runs right after, looking for "redundant leftover copies" to
  delete. The AppData folder it just copied *from* now looks redundant, since every note in it
  also exists in the copy just made - so it got deleted: `notes_data.json`, `settings.json`, and
  the whole `attachments/` folder.

This could be triggered just by running one of the project's own headless test scripts
(`test_calculator.py`, `test_recurrence.py`, `test_data_safety.py`) from a fresh scratch
directory - exactly the practice `CLAUDE.md`'s QA safety rule requires, since a brand-new
directory never has the flag that would otherwise skip the reclaim.

**Fix:** `purge_stale_copies()` now permanently exempts `%APPDATA%\NoteOrganizer` from deletion,
full stop. It's the durable store the distributed `.exe` actually reads from, never a disposable
leftover. Genuinely stale leftovers (like an old `dist\` copy) are still cleaned up as before,
verified with a dedicated regression test.

**Recovery:** The real notes weren't gone - they'd been copied into a directory before AppData
was cleared. A plain `python note_organizer.py` run at the project root held an intact copy,
restored back into AppData by hand (a direct file copy, not routed through any app code).

**Follow-up (0.33.x):** The deeper cause - that any `import note_organizer` performed migrations
at all - is now gone. Resolving the data folder, migrating, purging and writing settings moved
into an explicit `initialise()`, called by `NoteOrganizer.__init__` and by `_main()`. Importing
the module now creates no files and touches no notes.

**Takeaway:** "Copy it somewhere else, then delete the original because it's now redundant" is
dangerous for anything that's a *permanent* store rather than a disposable one - the logic can't
tell those apart from the data alone. A cleanup routine should name its exemptions explicitly,
rather than relying on every caller avoiding the deletion condition.
### The safety test that needed its own safety

*([0.39.63](../CHANGELOG.md#03963--2026-08-28) · 2026-08-27)*

**Symptom:** The app, launched from the project root, opened onto an empty
notebook. `notes_data.json` held two bytes — `[]` — and `settings.json` had
been reset to defaults. The trash, templates and attachments were untouched.

**Root cause:** `test_data_safety.py` exercises the backup/migration layer,
so unlike the other unit tests it deletes and rewrites `notes_data.json` in
its own directory (`os.remove(NO.DATA_FILE)` near the top, fixtures after).
Its docstring says plainly that it must be run from a throwaway copy — but
during a routine pre-commit sweep the agent ran the whole unit suite from the
project root, where `NO.DATA_FILE` resolves to the real notebook. The
CLAUDE.md hard rule that exists for exactly this class of accident named
only the `qa*.py` scripts; the unit tests were mentally filed as safe
because most of them genuinely are pure. One wasn't, and a warning inside
a file only protects the person who reads that file that day.

**Recovery:** the app's own version-upgrade backups (`notes_data_backup_*`)
held a copy from the previous evening — 27 notes, restored by a plain file
copy. Everything changed between that backup and the wipe was lost, along
with the settings. The `%APPDATA%` store and the trash were never touched.

**Fix:** two layers. The test now refuses to run at all when the
`notes_data.json` beside it holds real notes (a check at the top, before
any import side effects or file operations — proven to refuse beside a
populated file and to pass in a clean scratch copy and in CI, where the
git-ignored file never exists). And the CLAUDE.md rule now covers every
test file, `test_*.py` and `qa*.py` alike, with no per-file safety
judgments allowed.

**Takeaway:** a safety rule that lists specific filenames invites the
accident to arrive under a filename it forgot to list. The durable form of
the rule is categorical — *all tests run from scratch copies outside the
tree* — and the file that can do damage carries its own refusal, so the
last line of defence does not depend on anyone remembering anything.

### The delete that kept aiming at the wrong note

*([0.66.100](../CHANGELOG.md#066100--2026-09-05) · 2026-09-05)*

**Symptom:** Never reported from the field — surfaced by a code audit,
then reproduced by hand. Editing note A, right-clicking note B in the
list, choosing Delete and answering **No** left the app looking perfectly
normal — and the next autosave silently overwrote note B, title to
checklist, with note A's content. Nothing arrived in the Trash
("Settings → Recently deleted"), because officially nothing was deleted.

**Root cause:** `delete_current_note` could only act on "the selected
note", so the context menu aimed it by overwriting `selected_note_id`
with the right-clicked note's id — relying on the delete itself to reset
the editor afterwards. Both cancel paths (answering No, or dismissing the
occurrence-scope prompt of a repeating note) returned without restoring
the selection, leaving the editor's content and its identity pointing at
two different notes. Autosave trusted the identity: its only guard
checked that the selected note *exists* — and it did, since the delete
had just been cancelled. A comment in the flush path even documented the
repointing as a known hazard, but the guard written for it covered only
the confirmed-delete half (note gone), never the cancelled half (note
alive and about to be overwritten).

**Fix:** The delete target now travels as a parameter
(`_delete_note(note, occurrence_date)`) and the editor's selection is
never touched on the way in — a cancel leaves no state to restore because
none was borrowed. The regression checks drive the real cancel routes (No
on the confirm, cancel on the scope prompt) and then fire a genuine
autosave, asserting the right-clicked note survives bit for bit;
reintroducing the old repointing makes five of them fail.

**Takeaway:** an operation that aims itself by mutating shared state
leaves a lie behind on every path that doesn't finish the job — and
cancel paths never finish the job. Pass the target explicitly instead of
steering shared state, and when a comment says "restoring isn't needed",
ask on which branch that's actually true.

### The guards that never reached the siblings

*([0.66.104](../CHANGELOG.md#066104--2026-09-07) · 2026-09-07)*

**Symptom:** Found by the general code audit (the core-data agent), not
from the field. `save_notes` carried three hard-won guards — surrogate
mending, an atomic tmp-then-replace write, and a broad except clause —
each with a comment naming the real loss that taught it. Its siblings
`save_trash`, `save_templates` and `save_settings`, written to the same
shape for the same kind of file, had none of them: an emoji in a deleted
note could truncate trash.json mid-write. And on the reading side,
`load_notes` quietly turned an unreadable notes file into an empty
list — with the very next save overwriting the corrupt file, converting
a recoverable corruption into a permanent, unexplained loss.

**Root cause:** each guard was added where a bug first bit, and only
there. Nothing ever swept the lesson across the family of functions
doing the same job — so the protections mapped where failures had
already happened, not where they could happen next.

**Fix:** one shared atomic writer (`_write_json_atomic`) that every data
file saves through, and one preserve-aside helper (`_preserve_corrupt`)
that every loader calls before falling back to an empty default — the
unreadable original is copied to `*_corrupt_<timestamp>.json`, exempt
from every cleanup, and for the notebook the startup notice tells the
user what happened and where the preserved copy sits. The adversarial
review of the fix then swept its own leftovers: a list-shaped file of
pure junk that slipped past the corrupt-detection net, the one-time
cleanup rewrite racing to overwrite the corrupt bytes the notice still
pointed at, and the reclaim migration's settings write — the last naive
writer standing, which could also clobber a corrupt settings file with
no trace. While landing the
checks, the same list-the-fields trap surfaced once more in the test
suite itself: sections restored a hand-picked subset of the path globals
they had reconfigured, leaving every later section on ghost paths into
deleted temp dirs — the restore is a full `configure(previous_dir)` now.

**Takeaway:** a safety lesson learned in one function must be swept
across its siblings the same day it is learned. A guard that exists only
where the bug first bit is a map of where it will bite next — and the
sweep is cheap exactly because the lesson is already understood.

### The share code that could delete your files

*([0.71.113](../CHANGELOG.md#071113--2026-09-09) · 2026-09-09)*

**Symptom:** Found by the code audit. A genuine share code never
contains attachments — they aren't in `SHAREABLE_FIELDS`, so
`encode_share_code` strips them. But `decode_share_code` handed back
the raw JSON unfiltered, so a *hand-crafted* code could include an
`attachments` entry with a `stored_as` of `../../<some real file>`.
Importing that note and later deleting it forever (or letting the trash
auto-purge) ran `_delete_attachment_files`, which did
`os.path.join(ATTACHMENTS_DIR, stored_as)` and `os.remove` — deleting a
file well outside the attachments folder.

**Root cause:** two halves of the same "trust the boundary" gap. Encode
projected notes through the shareable slice; decode did not, so the two
ends weren't symmetric. And the deletion path assumed `stored_as` was
always the bare timestamped filename the app itself writes — true for
every file the app creates, never verified for one that arrived from
outside.

**Fix:** decode now projects each note through the same
`_shareable_view` encode uses, so an imported note can carry only the
fields a real code would (no attachments, no arbitrary keys) —
`normalize_note` still whitelists on top, making the boundary symmetric
at both layers. And `_delete_attachment_files` resolves each
`stored_as` through `_attachment_path_within`, which rejects anything
landing outside the attachments folder — the same path-traversal guard
the zip import already applies, now on the delete side too.

**Fix, completed under adversarial review.** The pre-merge attacker
found the first cut guarded only some of the surface, and closed the
rest in the same branch: the containment guard itself *raised*
(`os.path.commonpath` across drives/UNC, `realpath`/`os.remove` on an
embedded NUL) instead of returning None, and those raises escaped the
delete loop that runs unguarded at startup purge — so a crafted
*expired* trash entry could make the app fail to launch every time;
the guard now returns None on `(ValueError, OSError)` and on a NUL. The
open/preview sink (`os.startfile`) joined `stored_as` raw with no guard
at all, and keyed its "unsafe file" warning off the display filename a
crafted note controls separately — so a `.exe` labelled `doc.pdf` could
be executed on a click; `open_attachment` now resolves through the same
guard and keys the warning off the real on-disk extension. And the
share-code filter was one channel only — zip import merges attachments
verbatim — so the traversal is now also flattened at the data choke
point: `normalize_note` reduces every `stored_as` to a bare filename,
a no-op for genuine data.

**Takeaway:** a value that will be fed to a filesystem operation must be
validated where it *enters* (the import boundary AND the data
normaliser) AND at every place it *acts* (delete, open, preview) — not
trusted because the app's own code always produces a safe form. A guard
that can *raise* is not a guard; on an unguarded startup path a raise is
a launch-blocker. And a safety warning must key off the real artifact,
never a display label the attacker sets independently.

### The repeat interval with no ceiling

*([0.71.113](../CHANGELOG.md#071113--2026-09-09) · 2026-09-09)*

**Symptom:** Found by the code audit, then reproduced. A recurrence
rule with an enormous interval — `{"freq": "daily", "interval": 1e10}`
— crashed `expand_occurrences` with `OverflowError: Python int too
large to convert to C int`, because `timedelta(days=interval)` has a
hard ceiling of 999,999,999 days. And the calendar renders at startup,
so such a value sitting in `notes_data.json` could stop the app from
opening at all.

**Root cause:** `normalize_recurrence` clamped the interval from below
(`max(1, int(...))`, so zero or negative degraded to 1) but never from
above. A value from a hand-edited notebook, or a crafted share code
(share import runs through `normalize_note`, but the clamp that would
have caught it wasn't there), sailed through untouched. Recurrence is
in `SHAREABLE_FIELDS`, so the poison had a delivery route as well as a
hand-edit one.

**Fix:** one upper clamp, `MAX_RECURRENCE_INTERVAL = 1000`, in
`normalize_recurrence` — the single choke point both `normalize_note`
(every load and import) and `expand_occurrences` (every draw) pass
through, so one line closes every route. 1000 is beyond any real use
(every 1000 years) and orders of magnitude below the overflow point.
A qa5 check now builds the app and renders its calendar against a
poisoned `notes_data.json` to prove it launches.

**Takeaway:** a value that flows from untrusted data into a library
call with its own limits (here `timedelta`) needs clamping on BOTH
sides at the normalization choke point — "coerce to valid" has to mean
valid for every consumer downstream, not just non-negative. And the
calendar rendering at startup makes any calendar-data crash a
launch-blocker, which raises the stakes of every such value.

### The duplicate that wasn't a copy

*([0.71.119](../CHANGELOG.md#071119--2026-09-09) · 2026-09-09)*

**Symptom:** Found by the code audit. Duplicate a note that has an
attachment, then delete either note forever — the survivor's attachment
is gone too. The "copy" had copied the note's *reference* to the file,
not the file.

**Root cause:** `duplicate_note` deep-copied the note dict, and a deep
copy of a filename is the same filename: both notes' `stored_as` pointed
at one physical file in `attachments/`, while delete-forever removes
each of a note's files unconditionally. The adversarial review then
swept the class and found the same aliasing on two more routes. The
Settings duplicate clean-up merged a removed note's attachments into the
survivor **by reference** — and since the removed twin goes to the
Trash, whose retention purge deletes its files, the purge was
*guaranteed* to destroy the very file the merge existed to preserve.
And re-importing an overlapping backup skipped copying files whose names
already existed, handing an imported note a file an existing note owned.

**Fix:** one helper, `copy_attachment_file` in `core/storage.py` —
resolve the source through the same containment guard the delete side
uses, copy to a fresh timestamped name, return the new name or `None` —
called on all three routes. The import route keeps a "claimed" set
(files owned by kept notes, plus first claimants within the import
itself) so only real collisions pay for a copy. qa4 checks pin the
duplicate and merge routes with mutants: the survivor's merged file now
outlives the trashed twin's purge.

**Takeaway:** a "copy" that shares its source's resources isn't a copy,
and the resource here — a file on disk — is invisible in the dict the
code copies. When one route is caught aliasing, the class is "every
route that clones a note" (duplicate, merge, import), not the route in
the report.

### The mend that only ran on the way to disk

*([0.71.119](../CHANGELOG.md#071119--2026-09-09) · 2026-09-09)*

**Symptom:** Found by the code audit. Type an emoji into a note and
immediately share it — crash. Export it to a file, single or bulk —
crash. Save the note first, and both work.

**Root cause:** Tk hands an astral emoji over as a UTF-16 surrogate
pair, which Python strings carry happily but `.encode("utf-8")`
refuses. `mend_surrogates` existed for exactly this — but only the
disk writer called it, so the in-memory notebook keeps its surrogates
for the whole session, and every *other* path that encodes live note
content inherited a crash: `encode_share_code`, and both file exports
through `_note_export_content`. The export guards made it worse:
`except (IOError, OSError)` reads like "any failure writing the file",
but `UnicodeEncodeError` is a `ValueError` — it sailed past the guard,
and on the bulk path aborted the whole loop.

**Fix:** mend at each boundary's choke point — `encode_share_code`
before its encode, `_note_export_content` before returning (one line
covering both the single and bulk callers). The emoji arrives whole
rather than the export failing politely. qa1 and qa3 checks with
mutants pin both boundaries.

**Takeaway:** a repair applied where one boundary serializes is a todo
list for every other boundary that serializes the same data — sweep
them the day the first lands (the lesson of
[The guards that never reached the siblings](#the-guards-that-never-reached-the-siblings),
on a new class). And know the exception hierarchy of what you guard:
`UnicodeEncodeError` is not an `OSError`, so the "file write failed"
handler never saw it.

### The safety request the dialog never read

*([0.71.119](../CHANGELOG.md#071119--2026-09-09) · 2026-09-09)*

**Symptom:** Found by the code audit. The template-replace confirm —
"Any unsaved changes here will be lost. Continue?" — showed a neutral
❓ and opened with keyboard focus on **Yes**, so Enter, the reflex that
closes most dialogs, replaced the note. The call site read
`icon="warning", default="no"`: the caller had asked for both
protections, long ago.

**Root cause:** the dialog wrappers accept `**kw` and forwarded only
`kind`. `icon=` and `default=` — messagebox's own vocabulary, used by
ten call sites — were silently swallowed, and `_themed_dialog` always
focused the last (primary) button. Nothing failed, nothing warned: the
safety requests were dead code that *looked* like protection in every
review since.

**Fix:** honour both across the wrapper family — `_kind_from_kw` maps
`icon=`/`kind=` to the glyph, and a new `default=` names the button
that takes focus (`_dialog_focus_index`, pure; a typo falls back to the
primary rather than leaving nothing focused). Then the sweep: every
irreversible confirm — replace-with-template, delete an attachment or
template forever, overwrite a template by name, empty the trash, reset
an edited calendar day, restore a previous version, open a risky file —
now passes `icon="warning", default="no"`. Recoverable move-to-trash
confirms deliberately keep Enter as "proceed": irreversibility is the
criterion. qa6 pins the mechanism by recording the `focus_set` *call*
on a 3-button dialog (the target is the middle button, so any
hard-coded position fails) instead of reading focus back
asynchronously.

**Takeaway:** a `**kw` wrapper that forwards a subset silently swallows
the rest, and the silence is the trap — call sites then document
protections that don't exist. The fix is the wrapper (make the
vocabulary real), then a sweep that classifies every caller against an
explicit criterion — here "is it irreversible?" — so the next reader
knows which confirms are safe by choice, not by omission.

**It happened again, and that is why the root was not the vocabulary.**
Seventeen days later the consistency survey turned up seven `parent=`
arguments on these same five wrappers. `_themed_dialog` has never had
such a parameter — the dialog is an overlay inside the app window and
never needed one — so all seven were doing nothing, while reading at
every call site like the dialog was being anchored somewhere.

Harmless this time, which is exactly the point: the first instance cost
a safety guarantee, the second cost nothing, and neither announced
itself. The 2026-09-09 fix taught the wrappers two more words; it left
them able to swallow the next one.

So the signatures are named and keyword-only now — `icon`, `kind`, and
`default` on the two that ask — and Python refuses anything else at the
call. A stray keyword is a `TypeError` the first time that path runs
instead of a silence that survives every review. An AST sweep of all 58
call sites, the qa suite included, found `parent` and nothing else, and
confirmed no caller passes a third positional argument that the
keyword-only marker would now reject.

**The second takeaway:** when a class recurs, the first fix addressed the
instance even if it looked general. "Forward two more keywords" is not
"stop swallowing keywords". Ask which of those two a fix is, before
calling the class closed.

### The note the editor let you make and the launcher deleted

*([0.71.154](../CHANGELOG.md#071154--2026-09-11) · 2026-09-11)*

**Symptom:** Found by the product review. Create a note with no title
and no body but a checklist of three items. It saves, it appears in the
list, it is yours. Restart the app and it is gone — not in the Trash,
gone. Executed on a seeded notebook: five notes in, two notes out.

**Root cause:** two field lists that never grew with the app. The
startup clean-up asks `note_is_empty`, which judged by title, body,
comments and attachments — checklists, repeat rules and dates all
arrived later and were never added — while `_autosave_now` explicitly
counts a checklist as real content. One part of the app was creating
notes another part deleted as empty. The duplicate signature carried the
same gap, `(title, body, comments, category, date)`, so two notes
differing only in their checklists collapsed into one. And the clean-up
re-arms whenever `settings.json` is unreadable, so this was never a
once-ever risk.

**Fix:** both judgements now cover everything a note can actually hold —
and the adversarial review of the first fix found the class was wider
still: the stale-copy purge (which authorises an IRREVERSIBLE delete of a
leftover notebook folder, every launch) still judged by the old five
fields, and Find-duplicates plus all three import scans ignored
checklists and repeat rules though neither is merged on cleanup. There
is now ONE `content_signature` in the data core; every consumer calls
it, and a test bends the definition to prove each consumer follows —
the check that fires the day someone grows a private field list again.
The recurrence component signs by MEANING, not representation: a raw
`{}` and a fully-defaulted no-repeat dict are the same rule, and
signing them differently (the first draft did) split every raw-vs-
normalized comparison.

**Takeaway:** a predicate that enumerates a data type's fields is a debt
that comes due in silence, on the day someone adds a field — the same
shape as
[The centring that would not save itself](#the-centring-that-would-not-save-itself).
Two such predicates that disagree with each other are not an
inconsistency; they are a data-loss bug waiting for its first user.

### Two windows, one file, and the last one to autosave wins

*([0.71.154](../CHANGELOG.md#071154--2026-09-11) · 2026-09-11)*

**Symptom:** Found by the product review and reproduced by two
independent verifiers with two real app processes. Open the app twice —
a taskbar pin and a Start-menu entry is enough — write in both, and
whichever window autosaves last silently erases everything the other
wrote. No warning, nothing recoverable in the Trash.

**Root cause:** nothing anywhere prevented a second instance: no lock,
no PID file, no modification-time check, no reload. Each process loads
the whole notebook into memory and every save rewrites the file whole,
so the two copies diverge from the first keystroke and the file only
ever holds the last writer's version of everything.

**Fix:** a single-instance guard taken before the app window is built;
a second launch says the notebook is already open and steps aside.
Deliberately a file lock (`msvcrt.locking` on Windows, `fcntl.flock`
elsewhere) rather than a PID file, because the kernel releases it
however the process dies — a crash, or End task from the Task Manager,
cannot leave a stale lock that keeps the owner out of their own notes.
And when the lock file itself cannot be created, `acquire()` reports
success: refusing to start because a *lock* failed would turn a
cosmetic problem into "the app won't open".

**Takeaway:** a full-file rewrite makes concurrency a data-loss bug
rather than a merge problem — the moment two writers are possible, the
last one wins everything. And a guard that protects data must fail open
wherever its own failure would be worse than what it guards against —
which the first version got wrong in the fine print: it read EVERY
locking error as "already open", so a folder whose filesystem cannot do
byte-range locks at all would have bricked the app. Only the
someone-holds-it errnos refuse now. The review also proved the guard was
implemented but UNWITNESSED: deleting it from `_main()` left every
suite green, so a subprocess driver now walks the real launch path and
asserts both answers — the tested-library-untested-call-site gap, on
the one call site a user ever travels through.

### The trim that moved every colour

*([0.71.154](../CHANGELOG.md#071154--2026-09-11) · 2026-09-11)*

**Symptom:** Found by the product review. A body typed with an indented
first line and a couple of blank lines at the end came back reshaped
after a save — a pasted code block or a quoted email lost its shape.
Harder to see, and worse: in some notes a colour or a bold started a
character or two away from where it had been.

**Root cause:** the save read the body as
`get("1.0", "end").strip()`. The trim removes the first line's
indentation and every trailing blank line — already a silent edit of
what the user typed. But the styling spans and paragraph marks are
captured from the Text widget's own indices, which count the
*untrimmed* text, so once the leading whitespace was gone every span
described a different string than the one being stored. The codebase
even carried the evidence: two adapters,
`_extract_formatting_for_stripped_body` and
`_extract_paragraphs_for_stripped_body`, whose entire job was to shift
the spans back — a correction for a problem that existed only because
of the trim.

**Fix:** read `end-1c` and stop trimming. The body is stored exactly as
the widget holds it, the spans are measured against that same text, and
the two shifting adapters are deleted — the entry file came out of this
fix two functions shorter. Emptiness is still judged on a trimmed copy,
because that question really is about whitespace; what gets *stored*
never is.

**Takeaway:** when a transformation forces you to write a second
function that undoes its effect on related data, the transformation is
the bug, and the adapter is the symptom telling you so. And "tidying"
content the user typed is a data change wearing cosmetic clothes.

**The half the first fix missed:** the change DETECTOR still compared
`.strip()`ed bodies, so a whitespace-only edit read as "no change" —
the autosave, the flush and the dirty dot all ignored exactly the
characters the save had just learned to keep, and nothing automatic
ever wrote them. A promise kept by the writer means nothing if the gate
in front of the writer cannot see the difference; the comparator now
compares the body exactly as stored.

### The safety net that could not see the gap

*([0.71.154](../CHANGELOG.md#071154--2026-09-11) · 2026-09-11)*

**Symptom:** A static gate was written so that one class of omission - a question the app asks
in several places, answered by a hand-rolled field list at each one - "cannot come back
quietly". It reported the codebase clean. A review wave, running at the same time, found a live
instance of exactly that class: the share-as-code guard, refusing a checklist-only note the app
had just saved as real content.

**Root cause:** The gate's pattern required three content-field names in the same window of
lines, because the three instances that prompted it all had at least three. The share guard
enumerated only two. A net woven from the shape of what it had already caught was blind, by
construction, to the *under-inclusive* guards - precisely the ones that lose data, since an
over-inclusive guard only asks an unnecessary question.

**Fix:** The threshold is now two, and the reason is written above the pattern rather than left
implicit. With it widened, the gate found the share guard in its first second - the same defect
a 9.9-million-token review wave had reported, for the cost of a grep.

**Takeaway:** A detector built from the examples you already have will match the examples you
already have. Ask what a weaker instance of the class would look like, and make sure the pattern
still catches it, before the clean report starts being used as evidence. A gate that reports
clean over a known-live instance doesn't just miss it - it actively certifies the gap, and the
next reader believes it.
### The same net, woven again — and the question it was answering

*(2026-09-29, `Testing`)*

The story above, with a different gate, eighteen days later. Worth its
own entry only because of how the second one failed: not by being too
narrow for a *weaker* instance, but by answering a different question
from the one it claimed to.

**Symptom:** `tools/check_english.py` reported the repository clean. Its
own docstring says it exists because "the qa stories named their checks
in Romanian … and every CI run printed those names into a log anybody
can open". Six check names in `story_note_travels` were doing exactly
that, plus two printed messages in `doc_screenshots`, one in `qa1`, and
some eighty lines of seeded test data across eleven files.

**Root cause:** the gate searches a hand-written list of Romanian words.
That answers *"are any of MY words here"*. The question it claims to
answer is *"is this English"*, and the two are only the same question
while the list happens to be complete. Nothing that leaked used a word on
the list — not one.

The gate had been widened once before, in September, after it read a
seeded notebook full of Romanian nouns and called the repository clean.
That widening added nouns. It did not change the shape of the answer.

**What made it visible:** not the gate. A sweep for something else
noticed one Romanian line in a tool, and the question *"what else is
like this"* did the rest.

**Fix, and how little it proves:** the list is roughly three times
longer, built from what a sweep actually found rather than from guessing,
and words that are also English were tried and rejected on purpose —
`face`, `nota`, `plan`, `corp`, `lista` — because a gate that cries wolf
gets switched off. The commit says in the source that this is a floor and
not a proof.

The widening was itself the evidence for that. Run once, the longer list
immediately found **eight more lines** the hand sweep had missed,
including an assertion left stranded by one of my own renames. A third
pass found **seven more**. Three rounds in one day, each one finding what
the round before had certified as clean.

**Mutation-tested on the line it started from:** restoring the original
wording of `story_note_travels`' "the Settings button is in the sidebar"
check — the one that had been printing Romanian into every CI log — turns
the gate red, naming the file, the line and the word that caught it. The
Romanian is described rather than quoted here on purpose: quoting it made
this very paragraph fail the gate, which is a small proof that the
widened list now bites.

**Takeaway:** when a check's method can only answer a narrower question
than its promise, say so where the promise is made. The widened list is
worth having; believing it is finished is the thing that costs. And the
second failure of a class is the one worth reading — the first looks like
an oversight, the second shows you the shape.

**A third time (2026-10-03):** a two-word search string in qa7 and
`test_recurrence`, written on 9 September, had sat through both passes
above. This sweep did not sample. It read the repository by the endings
Romanian gives its words, by every word in a string or comment that the
docs' English prose never uses, and by the short words a three-letter
floor skips, and a person read every candidate: about three hundred
lines in nineteen files. Two of the ways they hid were in the gate's
method, not its list — `\b` reads a camelCase title, a word with a digit
on its end or a word right after a `\n` escape as one unknown word, and
no list knows the words nobody has written yet. The gate now pries lines
apart at those seams and knows Romanian's commonest endings. On the old
tree it flags 265 lines; without the new words it would miss 242 of
them, without the prying 37, without the endings 17. It still cannot see
two-letter words or words English shares, and says so in its source —
35 of the lines this pass translated. On the way, a qa8 check turned out
to have been unable to fail since the second pass: it asked about a
title that pass had renamed line by line (now a
[house rule](../qa/README.md#house-rules-for-new-checks)).

### The check that pinned the behaviour a release had deliberately replaced

*(2026-09-29, `Testing`)*

**Symptom:** none, for a fortnight. `story_audit`'s first chapter sets the
note list's sort to "Title Z–A" and its filter to a category, closes the
app, reopens it, and checks that both come back at their defaults — with
a comment above explaining, reasonably, that the app writes the theme,
the open note, the day colours and the grouping, and never claimed to
write these two. "Asserting a promise nobody made is how an audit
manufactures its own findings."

All of that was true when it was written. Then `0.76.198` shipped C-15,
which made sort and filter persist — the exact behaviour the check
asserts does not happen.

**Why nobody noticed:** the stories are not in `tools/run_tests.py`. The
suite ran green through the whole cycle that changed the behaviour, and
the check that contradicted it was never executed. It was found by
reading the file for an unrelated reason.

**Measured rather than assumed:** run on `main`, the chapter fails with
`<- 'Title Z–A'` — the value coming back off disk, which is the fix
working and the check disagreeing.

**Fix:** the check now asks for the sort it was left on. The filter check
stays as written, because its category only ever existed as a runtime
entry in the first process, so `All` really is the honest answer on the
way back in — which turns it from a contradiction of C-15's promise into
the guard on C-15's fallback.

**Takeaway:** a check that pins behaviour a release deliberately replaced
is worse than no check — it either fails for the right reason and gets
explained away, or passes by accident. When a feature changes what the
app promises, the checks that asserted the old promise are part of the
change, and a suite that cannot run a check cannot tell you that.

### The ceiling that counted the wrong thing

**Symptom.** None reported. This one came out of asking whether a row in
the coverage ledger was honest — the row said a long single-line note
"hangs Tk's layout outright (>240 s at 2000 spans)" and had been carried
for a day as a measured, deliberately-accepted residual.

**It did not reproduce.** Two thousand bold and italic spans on a
3,000-character one-liner open in 0.75 seconds. The neighbouring row was
worse: it claimed a 300,000-character single-line body is Tk-hostile on
its own, and a body that size with no styling at all opens in 1.13 s.
Neither row had ever been measured by the person who wrote it. One was
wrong about its numbers, the other about its mechanism, and they had
been sitting next to each other agreeing.

**But something there was real.** Swapping the span style from `bold` to
`font_size` on the same shape never finished in 90 seconds. That was the
start of four rounds of measurement, each of which killed the theory the
round before had produced:

| The theory | What killed it |
|---|---|
| It is the number of composite font RUNS | `highlight` and `text_color` hang identically and make no font runs |
| It is the number of distinct tags | 2,000 spans in ONE colour open in 0.24 s; the same spans in 50 colours never finish |
| It is the number of ranges on a line | 800 disjoint spans on one line open in 0.59 s |
| It is spans that START on a crowded line | 2,000 spans each starting on a DIFFERENT line and running to the end of the body never finish — five start on any given line |

What survives all four is narrower and less tidy: the cost is how many
tagged ranges end up COVERING one line, and the note's total range count
matters independently, because 500 spans over a 400-line body is 500
spans and 200,000 ranges.

**Why it is a data-safety story and not a performance one.** A pasted
note is SAVED before it is ever drawn. A share code of a few kilobytes
could therefore make the app fail to open on every launch after — the
same class as the checklist bomb one field over, and through a field
that cycle had already declared closed, because the ceiling it shipped
counts spans and the victim pays in ranges.

**The fix that was nearly worse than the bug.** The first version
refused to lay out the tags past a ceiling: the note opens, the text is
all there, only the styling is skipped, and the user is told. It passed.
It was also a silent data-loss bug, caught by walking the readers of the
value being changed rather than by any test: the editor reads a note's
formatting back OUT of the text widget when it saves, so the first save
after opening such a note would have written an empty formatting list
over the user's styled note. The ceiling belongs at the data door beside
the checklist and attachment ceilings, where what is kept is what is
shown is what is saved — and where all three doors into the editor (the
note, a template, and the previous version behind the restore button)
are one function away.

**Lessons.**

1. A ceiling must bound the quantity the victim actually pays in. Ours
   counted spans; Tk charges for ranges per line. Between those two is
   a whole family of notes that fit under the cap and never open.
2. A defence at the render is a data change whenever something reads the
   render back. Enumerating the readers of a value is step 3 of the
   pre-flight for exactly this reason, and it is the step that caught it.
3. A ledger row that says "measured" and was not is worse than an empty
   row, because it buys silence with a number nobody will re-check. Both
   rows are now marked with what they actually were.

### The identity that only lasted until you closed the app

**Symptom.** None reported, and none reachable by any test the feature
shipped with. It surfaced while preparing to smoke-test the packaged
build of the release that had *just* been merged: the last question
before launching the `.exe` was whether an existing notebook would gain
its identities on that first read, or only in memory.

**What was true.** `normalize_note()` mints an identity for any note that
arrives without one, and it is the choke point every read passes through
— which is exactly why minting there was chosen as the migration. But
minting there produces a value in memory. The notes file is written when
something *saves*, and a session where you open the app, read a note and
close it saves nothing. So the file kept no identities, and the next
launch minted a different set.

Two launches over the same notebook, measured rather than reasoned
about:

```
launch 1: ['59518893-…', 'd9ece3c8-…']
launch 2: ['36c264bb-…', '1048d093-…']
file on disk: no identities at all
```

**Why it mattered.** Share a note, close the app, come back tomorrow and
import that code: the note it came from is no longer recognisable, and a
copy is added — precisely the behaviour the identity was introduced to
prevent. The feature worked perfectly within one session, which is the
only place its tests ever looked.

**Why every test passed.** They called the functions. `normalize_note`
mints; `find_by_uid` finds; a share code carries it; `apply_shared_update`
updates in place — all true, all still true. Not one of them crossed a
process boundary, and the bug lived exactly there. The new checks load
the notebook **twice** through the real load path and then read the file
itself.

**The fix.** The first read that mints writes them down, once — guarded
like the one-time cleanup beside it: never over a file this launch has
just declared unreadable, and not at all when the file already has them
(checked by seeding the file with an indentation the app never writes, so
"untouched" is provable without leaning on a timestamp).

**The sibling, found by sweeping rather than by failing.** A restore from
the Trash already hands the note a fresh *number*, because the one it had
may have been taken while it was gone. Its *identity* can be taken the
same way — a copy of that very note arriving from a share code while the
original sits in the Trash — and nothing checked. Fixed in the same
change, one line below the one it mirrors: keep the identity when it is
free, mint a new one when it is not.

**The lessons.**

1. A value computed on every read is not *stored*. If it has to be stable
   across runs, name the thing that writes it down — "the choke point
   mints it" answers a different question.
2. A test that never crosses a process boundary cannot see a bug that
   lives there. For anything whose promise is "this stays the same", the
   check restarts.
3. The question that found it came from preparing to photograph the
   build, not from reviewing the code. That step has now caught bugs in
   three consecutive cycles, always the same shape: something the code
   was asked for before it existed.

### The code that would not say which note it was

**Symptom, field-reported, one day after the feature shipped.** Generate
a code for a note, close the app, reopen it, edit the note, import the
code. Instead of "Same note, a different version", a second note
appeared holding the original text. The whole point of the identity —
and on the route a user is most likely to take, it had never worked.

**The mechanism.** The editor's "Generate code" builds its payload from
`capture_editor_state()` — the title, the body, the styling, the
comments, the checklist: what is *on the screen*. The identity is not on
the screen. It belongs to the note, so the snapshot has no reason to
carry it, and the payload was assembled with a comprehension that drops
anything the snapshot lacks. The field was added to `SHAREABLE_FIELDS`
and this route silently declined it.

The comment directly above that line warns about this exact shape: the
dict "once named seven fields by hand and silently dropped everything
added to sharing later". It was rewritten to read `SHAREABLE_FIELDS`,
which fixed the field list — and left the assumption underneath it
intact, that every shareable field is something the editor holds.

**Why the checks did not see it.** There is an end-to-end check for this
exact route, added after the earlier loss: editor state → the code
widget → the import box → the opened editor. It asserts the content
arrives. Content was never the problem. A route check pins what it
compares, and the field added a release later was not in its list.

**The second bug, found by the check written for the first.** With the
identity travelling, the new check still failed: the note was recognised,
`_prev` was written, and the body was the OLD version. Updating a note
writes onto the stored note — while the editor goes on showing what it
had. The route then re-opened the note, and re-opening flushes the
editor first, which saw a difference and wrote the editor's version
straight back over the update. The note reverted with nothing on screen
to say it had ever changed, and the same is true one keystroke later on
the bulk route, which does not re-open anything at all.

So: flush first, deliberately, so the user's unsaved work is what the
rescue copy holds; then apply; then bring the editor onto the new
version without flushing again.

**Two more from the same field test**, both about the screen telling the
truth: a generated code stayed on display under whichever note you moved
to next, and Settings came back showing a section built on an earlier
visit — so a note deleted in between was simply missing from Recently
deleted.

**The lessons.**

1. A payload built from the screen carries only what is on the screen.
   When a field is added to a shared shape, the question is not "which
   list names it" but "does every producer HAVE it".
2. A green route check proves what it compares, not that the route is
   whole. Adding a field to a format is a reason to revisit every check
   that walks it.
3. Writing onto a note behind the editor's back is a save waiting to
   undo it. Any route that does it owns making the editor agree.
4. Four user-visible bugs, none of them findable by the suite as it
   stood, all found in twenty minutes of somebody actually using the
   app. The field test is not a formality at the end of the cycle.

### The undo that would have put everything in one place

*([0.75.177](../CHANGELOG.md#075177--2026-09-25))*

**Symptom, found by comparing neighbours rather than by using the app.**
Tick fifty notes, mean to export them, click one button to the left, and
every one of them is refiled the instant a category name is clicked — no
question, nothing on screen but a status line, and the categories they
came from gone from the file. The button beside it, **Trash**, asks first
*and* offers Undo. Recorded as C-1 in the
[consistency survey](archive/PRODUCT_FINDINGS.md#round-2--the-consistency-survey-2026-09-25).

**Why the obvious fix would have been the wrong one.** "Same shape as its
neighbour" is easy to say and easy to get half right. The Trash's real
safety net is not its toast — it is the thirty days the note then spends
in the Trash; the toast is a convenience on top. A category undo lasts
eight seconds and then the old filing is gone for good. *Less durable
recovery is what earns the question*, which is why this got both halves
rather than the toast alone.

**The part that was actually hard.** An undo for a batch is not one value
remembered, it is one value *per member*. A bulk change exists for a
mixed selection — notes sitting in several categories at once — so a
single remembered "old category" would file every one of them back under
whichever happened to be read first, and would have passed any check
built on notes that all started in the same place. The marks therefore
carry `(id, category, updated)` per note, mirroring how `_undo_trash`
matches on `(id, deleted_at)` rather than on an object held from a moment
ago.

Three smaller things came out of the same read:

- The confirmation had to be raised **after** the category popup is
  dismissed. That popup is a borderless `Toplevel` that never takes
  focus, so a modal opened in front of it leaves it floating over the
  very question it is asking.
- `updated` goes back too, because the alternative — stamping now, as
  `_undo_occurrence_delete` does, having no record of the old value — would
  send the whole batch to the top of a "Recently updated" list on account
  of a change the user had just said they did not want.
- The question must not over-promise. `category` is in
  `OVERRIDABLE_FIELDS`, so a repeating note can have one day filed by
  hand; the change leaves that day alone, which is right, and so "this
  replaces the category on each of them" needed the same kind of
  footnote the trash confirmation gives attached files.

**A mutant that survived, and the fixture that was lying.** Breaking the
`updated` restore changed nothing the suite could see. The reason was not
the check but the notes it ran on: created a moment before the change,
their stamp and the change's stamp were the same string to the second, so
restoring it and not restoring it looked identical. The fixture now seeds
an explicit old stamp and *states* it in a check of its own — a new
instance of the rule qa/README already carries, that a fixture which does
not do what its name says turns a measurement into a rumour.

**The lessons.**

1. An undo over many items remembers each item's own previous value. One
   value for the batch is a bug that only shows on the selection the
   feature exists for.
2. "Make it like the thing beside it" is a starting point, not a
   specification — ask what the neighbour's safety net actually is before
   copying its shape. Here the neighbour's net was thirty days, not the
   toast.
3. A modal raised from inside a focus-less popup needs that popup gone
   first, or it opens behind its own question.
4. A surviving mutant is a question about the fixture as often as about
   the check.

### The offer that was gone before you could take it

*([0.75.179](../CHANGELOG.md#075179--2026-09-25))*

**What was being fixed.** A checklist item's bin was the last delete in
the app with no route home: Ctrl+Z reaches the note's Text widgets
through `edit_undo`, and a checklist is a list of dicts beside them, so
nothing in the editor could return a line struck off by a mis-click.
Recorded as C-2. The plan was an Undo toast rather than a confirmation —
a question in front of every tick-list tidy-up costs more than it
protects.

**The premise was wrong, and the right answer changed with it.** The
register's reason for the comparison read: the attachment, "which at
least the file system still remembers", is the one that gets the
ceremony. `remove_attachment` calls `_delete_attachment_files`; the
stored copy goes with the note's reference to it, and the code says so
three lines above. So the asymmetry was not unfair in the way it had
been written down — the attachment's warning is correct for something
irreversible on disk, and the checklist's answer was never to add a
dialog but to stop being irreversible. The finding survived; its
reasoning did not, and the cell now says so rather than quietly dropping
the sentence.

**Then the probe found the bug behind the bug.** The new toast worked and
then vanished, in a probe written only to confirm the removal reached
disk. `_show_toast` stores the pending action in `self._toast_action`,
and a banner with no action stores `None` — so the autosave's own "Note
updated", firing a second later on the very save the deletion had
scheduled, wiped the Undo that deletion had just offered. Eight seconds
on the banner, about one in practice: long enough to see, rarely long
enough to use.

That was not new and not the checklist's. **Every Undo in the app was
affected** — a deleted note, a removed day of a repeating note, a batch
refiled into another category — because typing anything at all schedules
an autosave, and the trash and occurrence offers had been shipping that
way since `0.74.168`. The fix is at the class: a banner that is only
reassurance now yields while an offer is on screen (`yield_to_action`,
passed by the three autosave call sites and nothing else), and the status
line reports the save as it always did. An error never yields.

**Two of the nine mutants survived, and both were right to.**

- Removing the identity guard — the check that the working list is still
  the one the item came out of — left the other note's checklist
  untouched, so the check watching that list could not see it. The reason
  is that the undo inserts into the *captured* list, which is orphaned
  once the editor moves on: nothing is corrupted. What is wrong is the
  claim — a redraw of somebody else's checklist, a save of the note now
  open, and a status line saying the item was put back. The check now
  watches for that sentence, and the docstring no longer asserts a
  contamination that cannot happen.
- Removing the `_schedule_autosave()` from the undo also changed nothing
  the suite could see, because the check reached disk by calling
  `_flush_autosave()` — which saves whatever the editor holds whether
  anything asked it to or not. The check now looks for the queued job.

**The lessons.**

1. A banner that only reassures must never displace one that offers a
   one-time choice. Reassurance can be repeated; an offer cannot.
2. Re-read the reason a finding gives, not just the finding. This one's
   comparison was sound and its explanation was false, and the
   explanation was what pointed at the wrong fix.
3. A check that reaches its end state through a *forcing* call proves the
   forcing call works. If the point is that the app asked for something,
   look for the request.
4. A probe written to confirm one thing is where the next thing is found.
   This one was three lines about whether a delete reached disk.

### The undo that guarded the wrong state

*([0.75.181](../CHANGELOG.md#075181--2026-09-26))*

**The finding held; the map around it did not.** Clearing a calendar day's
colour or its markers wrote to disk on the spot with nothing offered in
return — the third destructive finding in the survey to survive contact
with the code, and the first whose reasoning survived with it. Two things
about its neighbourhood were wrong, in opposite directions.

A **third** route discarded the same thing: the day's own colour palette
carries a "No color" button whose handler pops the colour exactly as the
menu entry does. Fixing only the two entries the report named would have
left one of two doors unguarded — and the unguarded one is reached from
inside the very popup you open to *change* a colour.

And a route the report implied was broken was already safe. The marker
popup works on a copy, writes nothing until Save, and discards on ✕,
which its own docstring explains was a deliberate change. A check now
holds it that way, so a later pass cannot helpfully give it an undo it has
never needed.

**The hazard was geometry, not stakes.** The report argued from effort
invested — a year of marked birthdays. Reading the menu the app actually
draws makes a sharper case:

```
➕ Add note for this day │ 🎨 Color this day… │ ✖ Clear day color │ 🏷 Mark this day… │ ✖ Clear day markers
```

Each Clear sits *directly under* the entry that creates the same thing. A
mis-aim by one row turns "let me change this" into "discard it".

**The mistake worth recording is in the guard.** The first version asked:
*is what is there now equal to what I am about to restore?* That catches a
second click on a toast, and nothing else. A marker chosen by hand in the
seconds since is not equal to the old one, so the undo cheerfully
overwrote it. The right question is *is the slot still in the state the
clear left it in?* — and the clear left it **empty**, so an empty slot is
the only state the offer still fits.

Both earlier undos in this cycle had got that right without naming it:
the bulk category undo acts only on notes still filed under the category it
applied, and the checklist undo only while the working list is the one the
item came out of. Written as a rule: **an undo is a claim about a state, and
the state it must test for is the one its own action produced** — not the
one it intends to restore.

It was found by probing, not by review. The check for it was in the probe
before the guard was written, because the question "what if they decorate
the day again in those seconds?" is one of the five in the project's own
quality bar.

**The lessons.**

1. An undo guards the state its action *created*, not the state it means
   to put back. The weaker test passes the double-click case and fails
   everything else.
2. Sweep for siblings by asking what else reaches the same loss, not what
   else looks like the reported control. The second door here was inside
   the popup for changing the thing.
3. Check whether a neighbour the report implies is broken is actually
   broken. One of them was already correct, and "fixing" it would have
   undone a deliberate design.
4. Prove an undo on the screen as well as in the store. A check reading
   the calendar cell's own background is what stops a version that repairs
   the data and forgets to repaint.

### The binding that could never fire

*([0.75.183](../CHANGELOG.md#075183--2026-09-26))*

**Two reviewers said Escape does not close the app's popups. The code said
the binding is right there.** Both were looking at the truth. The binding
sits on the popup's own Toplevel — and those windows are borderless, take
no keyboard focus and never call `grab_set`, so Tk delivers a keypress to
the window that *does* hold the focus: the app window, which had no Escape
binding at all while a popup was open. A handler nothing could ever reach.

**Why "press it and see" is not enough on its own.** The register's row
ended with the right instruction — prove it by pressing Escape on the real
app, not by reading the binding — but pressing it proves less than it
looks. `qa/_qa_support.py` states the reason plainly, and refuses keyboard
sequences in `fire()` because of it: **Tk delivers a generated key event to
the focus window, not to the widget it was aimed at.** So "I generated an
Escape and nothing happened" is exactly as consistent with a harness that
cannot deliver keys as with the bug.

The probe therefore carried a control: force the focus *inside* the popup,
then press Escape. It closed at once. That single reading is what turns the
silence into a fact about focus rather than a fact about the probe — and
without it the whole file would have been a rumour with a conclusion
attached.

**The part that was easy to break.** A dropdown nested inside another popup
— a category list inside the template editor — is deliberately not
`self._mini_popup`; the host is. An app-window handler that simply called
`_dismiss_mini_popup()` would tear down the editor the list is sitting in,
which is precisely the breakage recorded in a comment beside the per-popup
binding, from an earlier attempt. So the handler closes one level at a
time, and the app-level binding is installed **once** rather than per
popup: a nested placement runs through the same method while the host's
binding is still live, and two handlers would mean one Escape closing both
levels. Each of those has a mutant.

**Two smaller things, both worth the ink.** The row's claim that "none
calls focus_set" is wrong — the inline rename popup focuses its own field
and binds Escape there, which is exactly why Escape works in that one, and
is the shape this fix generalised rather than invented. And the new block
passed once and failed once with nothing changed but how fast the run
happened to be: a section earlier in the same file can leave the keyboard
inside a leftover Toplevel, where a key never reaches the app window's
bindtags at all. Every press now states its precondition and establishes
it.

**The lessons.**

1. A binding is not an answer to "does this key work". Ask where the key
   goes, which for keyboard events is never the widget you aimed at.
2. When a probe's finding is an absence, it needs a control that produces
   the presence. Otherwise the probe cannot distinguish the bug from its
   own limits.
3. Two reviewers disagreeing with the code usually means the code is true
   and irrelevant. Look for the thing that stops it mattering.
4. A verdict that changes with the speed of the run is not a verdict.
   State the precondition and establish it, in the check itself.

### Eleven decisions about your notes, made from half the evidence

*([0.81.213](../CHANGELOG.md#081213--2026-09-29))*

**A deliberate attempt to break the app found eleven places that moved,
merged or removed a user's work on their own — and each one decided from a
partial view of the facts.** Three agents were each given one territory
(the data layer, the interface, the first run and packaging) and one rule:
reproduce it in a scratch copy, or it does not count. Every finding was
then read again in the code before anything changed. None was false.

**What each one trusted too much.**

- *A second file's word over the note's own.* A note stores only its
  category's name; which names exist lives in settings.json. Everything
  that made the two disagree — deleting settings.json to reset the
  preferences, copying only the notes file to a new PC, a category the
  loader dropped for being too long, or for being the 201st — ended with
  `normalize_note` filing the note under General, and the startup clean-up
  writing that to disk before the user had touched anything. The fix
  believes the notes: missing categories are rebuilt from them, and the
  doors a name comes in by refuse what the loader would drop. The loader's
  own comment said a dropped name went missing "loudly". Nothing was said.
- *Resemblance where identity was needed.* `content_signature` had a loose
  default — styling, per-day edits and skipped days left out, because "a
  stray bold word does not make a duplicate" — and a strict mode for "the
  one caller whose wrong answer is unrecoverable". The startup collapse's
  wrong answer is unrecoverable too: the copy it merges away goes nowhere,
  not even the Trash. Two copies of a weekly routine, one edited on a single
  day and pinned, became one, under a notice calling it an exact duplicate.
  The loose mode is gone. The sweep for siblings found a third automatic
  remover — a restored backup's Trash skip — asking the fuzzier question the
  Settings duplicate panel asks, where a person looks before anything goes.
- *A promise wider than its mechanism.* The Update dialog said each update
  "can be undone with ↩ Restore previous", and the rescue copy held five
  fields while the update replaced ten. Next to it, a backup's copy of a
  note went down the share-code route, which by design carries no
  attachments and no per-day timeline: right for a stranger's code, wrong
  for the user's own notebook arriving on a new PC.
- *Two answers to one question.* `_main` resolved the data folder, locked
  it, and `initialise()` resolved it again. The writability probe wrote one
  fixed file name, so two launches probing together collided — measured at
  46% of overlapping probes answering "not writable" — and a launch that
  read AppData that way locked a fallback folder, then opened the notebook
  its twin was holding. Deciding once removes the second answer; a probe
  file of its own removes the collision.
- *A check narrower than the delete it allowed.* The stale-copy purge
  compared attachment names, at the top level only, and then removed the
  whole tree. It compares bytes now, leaves a folder with anything else in
  it alone, and deletes file by file. One limit, stated rather than hidden:
  once the check has passed, deleting file by file and deleting the tree
  remove the same files, so no test can tell them apart. The second layer
  only matters if the folder changes between the check and the delete.

**How it was proved.** Twenty-four mutants, each applied to a fresh copy of
the project rather than to the source, so no failure of the runner could
leave one behind: every fix taken away in turn, and every one caught by the
check written for it.

**The lessons.**

1. When two files must agree, decide which one holds the truth and rebuild
   the other from it. Never let the weaker one rewrite the stronger.
2. An automatic removal has nobody in the loop, so it asks the strictest
   question there is. A looser one is for suggestions a person confirms.
3. What a dialog promises is part of the mechanism. An undo that cannot put
   back what the action replaced is a data-loss bug with a reassuring label.
4. A decision taken twice can be answered twice. Take it once and pass the
   answer down.
5. Judge what a deletion removes by the bytes it removes, not by the names.

### The Cancel that went ahead anyway

*([0.82.230](../CHANGELOG.md#082230--2026-09-30))*

**The same "try to break it" audit found seven places where the app did
something other than what a person had just asked — each small, each met
every day, and each one a gesture whose answer never reached the code
that acted on it.**

- *An answer nobody was told about.* Leaving an edited day of a repeating
  note asks where the edit belongs. On Cancel, `save_current_note`
  returned without saving — and returned nothing, so `_flush_autosave`
  could not say so, and every caller loaded the next note, cleared the
  editor or closed the window anyway. The edit was gone, and the
  docstring of the close route even recorded it as intended. One route,
  Back to Calendar, had already learned to stay, by asking afterwards
  whether the editor was still dirty. The fix makes the answer explicit
  (`_SAVE_CANCELLED`) and passes it up through every caller that replaces
  the editor — and through `open_note_in_tab`'s own callers, three of
  which armed a way back to the calendar for a note that had not opened.
- *A grab that holds the mouse and not the keys.* A dialog confines the
  pointer; shortcuts bound with `bind_all` run for any focused widget,
  the dialog's own button included. So Ctrl+S twice stacked a question
  on itself, and Ctrl+N under it emptied the editor, after which the
  answer wrote the edit under a day of `None`. The shortcuts now wait
  while a question does, and the save reads its day before asking.
- *A focus taken and not given back.* Every dialog put the keyboard on
  its button and then destroyed itself. It remembers where the keyboard
  was now — through `focus -lastfor` when the process does not own the
  desktop foreground, since `focus_get()` then answers None.
- *A record that outlived its widget.* The open table cell's editor died
  with the table when another note opened; its record did not, and the
  toolbar kept aiming at it. A `<Destroy>` binding ends the record on
  every route that ends the widget, including the ones nobody listed.
- *A shortcut acting on a page that was not on screen.* Settings is
  swapped in place of the notebook, so selecting the Notes tab from it
  changed nothing visible while the hidden editor was emptied — and a
  half-written template was dismissed without the question a click would
  have asked.
- *Press and release.* A `tk.Button` acts on the release; the popup's
  click-outside handler closes it on the press. Eleven buttons therefore
  reopened their popup on a second click. One helper,
  `_toggles_its_popup`, decides on the press, in the button's own
  binding, which runs before the window's.
- *A minimum nobody measured.* At the allowed 500 by 400 the sidebar's
  fixed parts used all the height and the list showed nothing. Measured
  and photographed, the minimum is now the smallest size where a card
  fits.

**Found on the way.** A probe written to measure the window's minimum
crashed on the first note it opened — the new code read
`_pending_calendar_return` before the app had ever set it. Every existing
check happened to set it first. It is read with a default now.

**The lessons.**

1. A function that can be told "no" has to say so to whoever called it.
   Silence is read as "done", and the caller carries on.
2. A dialog that looks modal is modal for the mouse only, unless the
   keyboard is held as well.
3. What a widget-level record describes should die with the widget —
   bind the ending, rather than list the routes that end it.
4. A button's press and its command are two events with the whole
   window's bindings in between. Decide on the press what the release
   will mean.

### One unreadable field, and every word typed after it

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Type a note's date the way many people write it — 30/09/2026, or "Oct 3" — keep
typing, and click another note: everything typed after the date was gone. No dialog, no status;
the status line still said "Auto-saved" from before. The same with a repeat chosen on a note that
had no date, and a note that arrived by share code carrying such a date could not be edited at all.

**Root cause:** The save treated one field it could not read as a reason to save nothing, and
said so only on the explicit Save button. The automatic routes — a pause in typing, another note,
Ctrl+N, closing the window — read that silent "no" as "done" and replaced the editor. One route
of eight (Back to Calendar) had learned to check; the rest never asked. And a code made in the
editor sent the date field's raw text, so the far end received a date its own save would refuse.

**Fix:** A field the app cannot read is left out, never allowed to veto the rest: it keeps the
note's last good value, everything else is saved, the status line says what was left out, and
leaving the note asks "Go back and fix it" or "Continue without it". The save and the question
ask one judgement (`_date_and_repeat_to_store`), so they cannot disagree about what stayed
behind. A repeat's end date typed day-first joined the same rule, instead of quietly making the
series endless; and a code carries the date a save would keep.

**Takeaway:** a refusal the caller cannot tell from success is data loss — and when several
fields are checked, one bad field must not take the good ones down with it.

### The delete that put an older version back

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Press "↩ Restore previous" on a note, then delete some other note from the list:
the open note jumped back to the version Restore had just replaced — and clicking away saved it
over the restored one, with no rescue copy left.

**Root cause:** The editor keeps a snapshot of the note it opened, left over from when several
notes could be open in tabs. Every delete "switched" to the first remaining tab afterwards —
with one tab, the note already on screen — and restored it from that snapshot, taken when the
note was opened. Whatever had been saved since went back to the older version, silently.

**Fix:** Deleting some other note leaves the editor exactly as it is. Every delete route — the
editor's Delete, the selection bar's Trash, a category deleted with its notes, the Duplicates
clean-up — also saves the editor's unsaved typing first, as the right-click delete already did.

**Takeaway:** code kept for a feature that no longer exists goes on doing what it did — find what
it still touches before trusting that it is inert.

### Importing the same backup twice, the second time

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Import a backup older than this device's notes and choose "Update": this device's
text was kept as the rescue copy, as promised. Import the same backup again — the first import had
said "Added 0 notes", which read as "nothing happened" — and that rescue copy was replaced by the
backup's own text: the newer text was in no file at all. And around it: Cancel at the duplicate
question after "Update" left the update in memory for the next save to write; Cancel on a
repeating day's question loaded the import into that day, whose Save then replaced the whole
series; and a note sent out by code, edited elsewhere and sent back arrived as a second copy.

**Root cause:** One habit in four shapes — acting before the last question was answered, and
acting when there was nothing to act on. An update that changed nothing still rewrote the rescue
copy; the updates were applied at the first answer, before the second question; the import went
on after a Cancel; and the review editor dropped the identity the code carried.
[The 0.4.0 story](#importing-the-same-backup-twice) was the same gesture's first lesson.

**Fix:** An import asks every question first and changes nothing until the last answer. A note
that arrives exactly as it is here is neither updated nor copied, and the result counts updated
and unchanged notes as well as added ones. "Update" flags a backup copy that is older than this
device's. Cancel on a day's question keeps the day and the code. A note under review keeps the
identity it arrived with for its first save.

**Takeaway:** when several questions guard one change, the change happens after the last answer
— and an operation that would change nothing must change nothing, its side effects included.

### The category renamed in one place of six

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Rename the category of the note open in the editor, and a moment later that note was
filed under General. Templates and the Trash kept the old name, a folded group unfolded while its
old name stayed folded in the settings for good, and the category moved to the end of the list.
Delete a category and restore an old series from the Trash, and the next launch re-created the
deleted category as having "gone missing from the settings".

**Root cause:** A category's name lives in six places — the notes, the Trash, the templates, the
folded groups, the list's filter and the editor's own category box — and the rename rewrote one.
The editor's box was left holding a name that no longer existed, a guard written for deleted
categories reset it to General, and the next save wrote that. A deletion likewise left the Trash
holding the name, and one day of a restored series carried it back in.

**Fix:** One method moves every holder of the name (`_refile_category_everywhere`), for a rename
and for a deletion alike; a rename keeps the category's place among the groups; and a day filed
under a category that no longer exists comes back under General, as the note itself always did.

**Takeaway:** before renaming anything, list everything that holds the name — the place you
remembered is rarely the only one.

### The Trash that gave notes back one at a time

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Undo after moving a thousand notes to the Trash froze the app for 30–46 seconds, and
restoring ten ticked notes took up to four. A row in Recently deleted could restore a second copy
of a note the toast's Undo had already brought back — and its Delete destroyed the file that
note was showing.

**Root cause:** Restoring went note by note, each one rewriting the whole trash file — quadratic
in the size of the batch. The trash was written before the notes, so a failed notes write could
leave a note in neither file. And the panel's rows held the entries they were drawn for, with
nothing redrawing them when a restore happened somewhere else.

**Fix:** A batch comes back in one pass, each file written once, the notes first. The rows check
that their entry is still in the Trash; a permanent delete spares any file a note still uses;
and the toast's Undo redraws an open Trash panel.

**Takeaway:** a write inside a loop is a quadratic waiting for its first big batch — and a row
that holds a reference must check the reference still means what it did when it was drawn.

### The day whose own words went missing

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Undo after removing one day of a repeating note brought the day back showing the
series' text — that day's own edit gone for good. Saving a day with its own text to "The entire
series" gave every day those words, left the day unchanged, and asked the same question again at
every exit. And ticking a checklist item on such a day wrote that day's words over every day of
the series, wiping the series' formatting.

**Root cause:** A day's own text lives in the note's overrides, and three routes forgot it: the
delete dropped it and handed the Undo nothing to put back; the series save wrote the editor — the
day's text — into the series but kept the day's now-identical copy; and a save made without a
question, because only a series-owned field had changed, still wrote the whole editor.

**Fix:** The Undo carries the day's own text back. "The entire series", answered on such a day,
makes its words the series' and drops the day's copy, keeping the series' old text as the rescue
copy. A save made without asking writes only what belongs to the series — the checklist, the
attachments, the date, the repeat.

Two more rounds of breakers found the same lesson at the edges of the fix. "This occurrence
only" wrote the day's text to the day and dropped the series-owned fields changed in the same
visit — a file attached was left in the folder with no note. Turning the repeat off took every
day's own text with it, and when the day on screen was saved first, the editor went on showing
the day's text as the note's, so leaving wrote it over the series' text. Every day-view save now
writes the series-owned fields to the series, a repeat turned off keeps the whole note as it was
(repeat and days) as the rescue copy, and the editor is filled from the note the save left.

**Takeaway:** when a view shows one layer over another, every write from that view must know
which layer each field on screen came from — and when a save removes the layer the view stood
on, the view has to be rebuilt from what is left.

### A question holds the app three ways, and it held one

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** While a question waited — "Move to trash?", "Empty trash?", "Restore previous
version?" — the app under it could still change. A timer's own question answered inside it
("Export complete") left the app taking clicks. Tab walked out of the question's buttons into
the note under it, where typing landed, and onto the note list, whose Shift+F10 menu holds
Delete. And the answer then acted on the app as it was after the wait: a note ticked meanwhile
was removed with no Trash copy; Empty trash destroyed a note trashed meanwhile; deleting a
category's notes trashed one more than the question said; Restore previous wrote the old text
into whichever note the editor had moved to, and its next save kept it.

**Root cause:** A question waits in a nested event loop, so the app goes on running under it.
To be modal it has to hold three things — the pointer, the keyboard, and what it asked about —
and it held only the pointer, through Tk's grab. Even that went when a question inside it
ended: Tk has one grab, and the inner question's release left none. Tab is the keyboard's own
walk between widgets, which no grab stops. And every one of these actions read its target
after the answer.

**Fix:** A question that ends gives the grab back to the one still waiting under it. Tab and
Shift+Tab walk the question's own buttons and come back round, as a Windows message box does.
And every confirmation acts on what its question named, captured before asking — the notes,
the Trash entries, the attachment, the note being restored — and checks each is still where it
was; one that arrived meanwhile was never asked about, so it is left alone.

**Takeaway:** "modal" is three promises — pointer, keyboard, subject. A confirmation acts on
the subject it named, captured before the wait, because a nested event loop lets the world move
under it.

**Follow-up:** Capturing the subject is not enough when the wait itself can change it. Restore
previous captured its rescue copy, then asked — and an edit still waiting for its autosave was
saved while it waited. After a big delete, that save made a new rescue copy of the words just
taken, which the restore, of the copy captured before, then replaced: the deleted words were in
no file. A pending autosave now runs before the copy is captured, so the question offers the
newest one. A timer due inside a question is part of the world that moves under it.

### The list the note shared with the editor

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Type a word, let the autosave run, attach a photo, close the app: after a restart the
note had no attachment, and the photo sat in the attachments folder with no note. A file removed
the same way was still listed, its stored copy already deleted.

**Root cause:** The save stored the editor's own list of files in the note — the same Python
object, not a copy. From then on, attaching or removing changed the note in memory too, so the
dirty check compared the list with itself, found nothing unsaved, and the autosave, the note
switch and the window's close all skipped the save. It needed only one save earlier in the visit.
The checklist stored beside it had always been copied, which is why ticks never went the same
way. The line was there from the first commit.

**Fix:** Both saves of an existing note store a copy. A new note's save already copied (through
`normalize_note`), which is also why the first fixture written for this check could not fail: it
saved a new note, and the shared list lived only on the save of an existing one.

**Takeaway:** storing a mutable object you will keep editing makes "is it saved?" ask the object
about itself. Copy at the boundary — and make the check take the route the bug took.

### The copy that exposed a reload

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** On a day of a repeating note: save the day, attach a photo, press "↩ Restore previous".
After a restart the photo was gone from the note, its copy left in the attachments folder. The same
steps had kept the photo an hour earlier, on the code before the fix for
[The list the note shared with the editor](#the-list-the-note-shared-with-the-editor).

**Root cause:** That fix stopped the save storing the editor's own list of files in the note. The
shared list had also made every file attached after a save land in the note at once, in memory —
so two routes that fill the editor from the note as stored, Restore previous and "Reset this day",
kept the file by accident. On a day nothing else stores the editor's files before a save or a way
out (the autosave does not run there), and without a save earlier in the visit, or for a ticked
checklist item, both routes had always dropped them.

**Fix:** Both routes store the editor's files and checklist first — copies, through the same write
a day's own save uses, never its date or repeat — and a rescue copy that holds them still wins.
The right-click Duplicate, which copied the stored note in silence, asks about unsaved changes as
the editor's own Duplicate does.

**Takeaway:** removing an accidental behaviour exposes whatever leaned on it. Before such a fix
lands, list the routes that read what it changes — here, every route that reloads the editor from
the stored note.

### The turn-off that stopped every save to wait

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** On a series whose days hold edits of their own, "Does not repeat" picked by mistake
and put right a second later brought the series back without its days.

**Root cause:** The autosave saved the turn-off like any other edit, half a second later — and
turning a repeat off moves every day's own edits into the rescue copy.

**Fix:** The first fix stopped the autosave altogether while the turn-off waited. The next round
found what that cost: everything typed meanwhile was lost on a crash; Restore previous, which
saves the waiting edit before it asks, saved nothing and put an older copy over the newest
text; and routes that save on their way to something else — deleting another note, deleting one
day on the Calendar — made the turn-off anyway, then asked the wrong question. Now only the
turn-off is held, the way a value the app cannot read is left out: a save nobody asked for —
the autosave, a route saving on its way — keeps the stored repeat and names "turning the repeat
off" as left out, and leaving the note or Save makes it.

**Takeaway:** hold back the one thing that must wait, not everything around it. Stopping the
whole save to protect one field broke every other promise the save keeps — crash safety, the
rescue copy, the routes that rely on it — at once.

**Follow-up:** "The one thing" turned out to have edges, found by the next round. A date typed
beside the held turn-off was saved alone onto a series that still repeated, and a new start date
moves every day of a series: a one-off typed on a Thursday moved a Monday series to Thursdays.
The date waits with the turn-off now. A big delete made while it waited was saved with its own
rescue copy, and the turn-off, saved last, replaced that copy with one of the note as the held
saves left it — the person had acted in the other order, so their deleted text was in no file.
The turn-off's copy keeps that text now, within the same wait. And every delete saves before
its question, which made the waiting turn-off before an answer that could be No; those saves
hold it too. What is held is whatever cannot be separated from it.

A day deleted during the wait taught a harder lesson, four rounds running. Its own text was held
only by the delete's Undo, and each round tried to keep it once the turn-off took the series
away. Kept in the note, it read as a day with edits of its own. Counted by the turn-off, it made
a copy for an Undo that might never be clicked, and that copy replaced an older one. Carried by
the Undo and made into a copy only when clicked, the copy picked up an older series, undid what
was saved since, and once wrote itself into a new note that had taken the old note's number.
Each design was broken by the next round of breakers. Now the Undo puts the day back only into
the series the note still holds, and once that series is gone it says so: the day can't come
back. That is what 0.82.233 said too — the person had deleted the day — and nothing the Undo
writes can be wrong. A convenience for an edge case is not worth machinery that every round
finds a new way to break.

Even the one convenience kept — the day's own text put back on a repeat picked anew — broke
once more: it was written behind an editor that could be showing that very day, and the
editor's next save read its own stale view as an edit and wrote the series' text over the day's.
A route that writes a note behind the editor saves the editor first, every time; the rule was
already written down, and one more route had to learn it.

### The file the app could not start beside

*([0.83.338](../CHANGELOG.md#083338--2026-10-03))*

**Symptom:** A security pass after the nineteenth round tried the data files with two kinds of
damage nobody had tried: a notes file saved by another program in one of Windows' older text
encodings, and one nested deeper than a JSON reader can follow. With either in the notes,
settings, Trash or templates file, the app did not start. A share code damaged the same way said
"Something went wrong", and a backup carrying such a file failed whole, sound notes and all.

**Root cause:** Every reader caught `json.JSONDecodeError` and took that to mean "unreadable".
It is one of three ways a JSON text turns out unreadable: bytes that are not UTF-8 raise
`UnicodeDecodeError` before the parser sees them, and nesting past the parser's depth raises
`RecursionError`. Fourteen readers each wrote the list out by hand. Two also caught
`UnicodeDecodeError` — met once each, and fixed where it was met — and none caught
`RecursionError`.

**Fix:** One definition, `JSON_UNREADABLE` in `core/paths.py`, names all three, and every reader
catches it. The loaders already knew what to do with damage — keep the file's bytes aside, start
empty, say so at startup — so none of that changed; the two new kinds simply reach it now.
`tools/check_one_definition.py` fails on any `except` that names `JSONDecodeError` itself.

**Takeaway:** an `except` clause is a claim about every way its call can fail. When one call is
guarded in many places, that list is a definition: write it once, and let a gate refuse a copy
written by hand. Hand-written copies are how two readers learned about the encoding and twelve
did not.

### The backup the app could not restore

*([0.94.379](../CHANGELOG.md#094379--2026-10-15) · 2026-10-15)*

**Symptom:** none reported. The owner asked how the app would hold up at thousands of notes, and
an analysis that read the backup's two ends side by side found it.

**Root cause:** the import's guard against hostile archives refused anything over 500 MB or
10,000 files. That sat below what the app's own export writes: every attached file, whatever its
size. One long video, or a few hundred phone photos, made a backup the app refused with "too
large to import safely", at the moment it is needed, on a new computer. Nothing had ever tested
the guard. Share codes had the same gap on a smaller scale: the Share panel's Select all could
tick more than the 200 notes one code may carry, and the receiving app refused the code.

**Fix:** the import's limits now guard against what a hostile archive does, not against size.
It checks that the disk has room (on one disk the attachments are counted twice: unpacked, then
copied in), and refuses an entry, or an archive as a whole, shaped like a zip bomb. The first
version asked only each entry on its own, and a security review of the commit found the way
round it: a thousand entries, each just under the size one was asked about. The writer asks the
reader's question
too: the export runs the import's rules over the archive it has just written before putting it
in place, and no share code is made past a limit its import enforces. Every other reading limit
in the app was walked against what writes it. The one left out of step on purpose is the
formatting ceiling, an anti-bomb limit set above any real note and recorded where it is defined.

**Takeaway:** every limit on reading is a promise about writing. When the app makes the thing it
later reads, one definition must check both ends, or the guard that protects the import becomes
the bug that loses the backup.

### The import the close waited for, then threw away

*([0.94.382](../CHANGELOG.md#094382--2026-10-15) · 2026-10-15)*

**Symptom:** none reported. A probe asked what closing the app leaves behind. Closed three
seconds into importing a 600 MB backup, the window took 33 seconds to go and left 1.2 GB on
disk: 600 MB of unpacked backup in the temp folder, and a 600 MB half-copied `.part` in the
notebook's own attachments folder. Closed during a 600 MB export, it left a 511 MB `.tmp` beside
the backup.

**Root cause:** the close waited for a running backup worker, but only for 30 seconds, so that a
hung one could not hold the window open. Then the process ended, and a worker still running died
wherever it was, with nothing to take its unfinished files away. An earlier fix ("Abandoning an
import leaves nothing behind") cleaned up after an import that finished inside the wait, which
was the case its test built; an import still running at the cap was never built. For the import,
the wait bought nothing even when it was long enough: the close drops an import that was never
merged, so the half minute went on copying files that were then removed.

**Fix:** the close asks the work to stop, and waits only for the answer. An import is asked at
once. An export is waited for, as the guide promises, and asked only if it is still writing at
the cap. The worker hands zipfile its file wrapped in a `StoppableFile`, whose next read or write
raises once a stop is asked, so even one huge file stops between two chunks, inside zipfile's own
loops, without reaching into them. The worker's own error path then removes what it had begun.
The same 600 MB import now closes in about 3 seconds and leaves nothing.

**What the owner added.** Leaving nothing is half of it: the person also has to know that nothing
was kept, or they believe the import (or the backup) happened. A closing window cannot say so,
so the close writes it down and the next start reads it out once, naming the file and what to do
again.

**Takeaway:** a cap on a wait is half a decision; the other half is what happens to the work
still running when the cap is reached. And a cleanup tested only on work that finished in time
has not been tested on the case it exists for.

### The figure that was not one of the ten

*([0.95.391](../CHANGELOG.md#095391--2026-10-20) · 2026-10-20)*

**Symptom:** none reported. Found while comparing the Android port with the desktop. Type
"17²" in a note's date field ("²" has a key of its own on a French keyboard) and every autosave
of that note failed: nothing typed after it was kept, body included, and closing the app stopped
on "Something went wrong". A notes file holding such a date, edited by hand, kept the app from
opening at all.

**Root cause:** `read_date` sorted each piece of the field into letters and figures with
`str.isdigit()`, which is True for "²", "①" and "₂" as well as for 0–9. The patterns that read
the figures are written `[0-9]`, so a piece sent to them as a figure matched nothing, and the
match's `None` raised. The same mistake had been fixed three times before, one reader at a
time: a day of the month, a year, the calculator. Each fix closed its own door and left the
next.

**Fix:** a figure is one of `"0123456789"`, the same set the patterns read. And the one-definition
gate (`tools/check_one_definition.py`) now refuses a bare `.isdigit()` anywhere in the app's
code, naming `isdecimal()` (what `int()` reads) or a test against the ten figures instead. The
one remaining use is allowed by name, with its reason: it runs only after `isascii()`.

**Takeaway:** the fourth fix of one mistake is the moment to stop fixing it by hand — a gate
that refuses the pattern closes every door at once, including the ones not yet written.

### The Trash that forgot its window

*([0.95.391](../CHANGELOG.md#095391--2026-10-20) · 2026-10-20)*

**Symptom:** none reported; the Android port had the same weakness, found by its own audit, and
the desktop was checked for it. Someone who keeps deleted notes for 90 days, and whose
settings file is damaged by a bad shutdown, starts the app — and every note in the Trash older
than 30 days is removed for good, with its attached files. A hand-edited window of `0` removed
everything older than a day. Separately, the automatic cleanup could delete a file that a
living note was still showing.

**Root cause:** three gaps, one theme — a deletion nobody asks for acting on something it
could not know.

- An unreadable `settings.json` read as `{}`. Before the purge ran, the first write of any
  setting (the app writes several while it starts) stored a fresh file with no window in it,
  so "unknown" had already become "never chosen", which means 30 days.
- A stored value no app writes was clamped rather than refused: `0` became one day, `"forever"`
  became 30.
- Two notes can share one stored file, when a duplicate or an import could not copy it and kept
  the name. Delete and Empty trash spared a file a note still used; the startup purge, and
  removing one attachment from a note, did not.

**Fix:** `load_settings()` answers an unreadable file with a marker,
`desktop_trash_window_unknown`, instead of `{}`. Every writer reads, changes and writes, so the
marker survives until the person chooses a window again, in one write
(`choose_trash_window()`). `trash_retention_days()` answers `None` while the marker is set or the
stored value is not a whole number from 1 to 365, and `None` purges nothing. The next start says
so once; the Trash panel says nothing is removed automatically and its selector reads
**Choose…**; the texts that promised "restorable for N days" leave the number out while there is
none to promise. The purge and the single-attachment removal now spare every file a note or a
kept entry still uses, and on a launch whose notes file could not be read the purge does not run
at all, since there are no notes to ask.

**Takeaway:** "I don't know" and "the default" are different answers, and a store that turns
one into the other on its next write erases the difference before anyone can act on it. Carry
the not-knowing in the data until a person resolves it.

### The Trash that counted on the wall clock

*([0.97.405](../CHANGELOG.md#097405--2026-10-27) · 2026-10-26 · found answering the owner's
question, on both apps · issues #313, #314)*

**Symptom:** the owner deleted every note on both apps and asked one thing: if she sets 90 days,
do notes stay 90 days, and 30 for 30? A probe for each window (7, 14, 30, 60, 90) put entries in
the Trash at its edges, picked the window, started the app again and read `trash.json` back.
Both apps kept exactly what they should. The phone's probe failed once anyway: with entries an
hour either side of the window, the one an hour short of 30 days was gone. It was the day after
the clocks went back. Beside it, on the desktop, the Trash panel's rows went on quoting the old
window after a new one was picked, while the subtitle above them said the new one.

**Root cause:** `deleted_at` is a wall-clock stamp, and the desktop measured an entry's age by
subtracting two wall-clock readings. Across a change to summer time those differ from the time
that really passed by an hour: in spring a note was purged an hour before its window was up, in
autumn kept an hour longer. The phone counted real time and was right; its probe had built its
"an hour short" on the wall clock, the same mistake from the other side. The rows were a second
reader of the window: the window change rewrote the subtitle in place and left the rows, which
work out their "days left" only as they are drawn.

**Fix:** the purge, the shorter-window warning and the rows' days left count real seconds now
— each stamp placed by the offset in force on its own day (`time.mktime`), now as `time.time()`
— through one reader of the stamp, `_deleted_epoch`. A stamp before 1970, which Windows'
`mktime` refuses, is read as UTC, so it stays past as it always was rather than being kept for
good as unreadable. A new window redraws the rows with the subtitle. `test_data_safety` plays a
zone that springs forward on 29 March, with a control that has no change; the probe's margins
became two hours.

**Takeaway:** an age is the distance between two moments, not between two clock readings; the
two part by an hour twice a year, and a rule that deletes must count the moments.

### A file with two names

*(2026-10-27 · found by the final audit's break-it round, on Windows)*

**Symptom:** a backup whose Trash held one entry, its file named `202610~1.JPG`, deleted a
note's own photo at the next start. A note whose file was `evil.exe::$DATA` opened the program
without the "Potentially unsafe file" question.

**Root cause:** NTFS answers more than one string for the same file. It gives every long name
an 8.3 short name — for the app's timestamped names, predictable from the year and month — and
reads a `::$DATA` suffix as the file's own data. Every check before a delete or an open compares
names: the import's list of files it owns, the spare list a delete leaves alone, the extension
that decides the warning. `_attachment_path_within` resolved the name with `realpath`, which
follows the alias to the long file. So the file deleted or opened was not the name checked.

**Fix:** the resolver refuses a name that reaches a file under another name: what `realpath`
returns must be, letter for letter, the name joined to the folder. Every delete and every open
goes through it, so the purge, Delete forever, Empty trash and the warning all see the same file.
The warning also reads its extension from the resolved path. `test_data_safety` makes a real
short name and a `::$DATA` suffix on Windows and a symlink on Linux, and holds that each is
refused while the file's own name still opens; mutant TN01 takes the check away. "Except case"
was first allowed on purpose, and round two found the capitals were an alias too
([Round two](#round-two-each-fixs-next-door)).

**Round three** *(2026-10-28)*: a name can reach a part of the file as well as the file. On NTFS
`x.docx:Zone.Identifier` is the stream holding the file's Mark of the Web, and `realpath` hands it
back unchanged, so it passed the letter-for-letter test. A backup's Trash entry naming it was
purged at the next start, and the mark the import had just written went with it. The resolver now
refuses any name holding a colon, which no Windows file name has, on every system; a file attached
on Linux, where one can, is stored without it. `test_data_safety` writes the stream and purges by
five spellings of it; qa7 attaches a file named with a colon; mutants RT01, RT02.

**Takeaway:** when a check and the action after it each name the file, they must name it the
same way. Resolve once, and compare what was resolved.

### A delete that trusted the Trash

*(2026-10-27 · found by the final audit's break-it round, on a disk filled on purpose)*

**Symptom:** on a disk with room for the notes file but not for the Trash, Delete took the note
out of both. The status line said "recoverable for 30 days"; after a restart the note was in
neither file.

**Root cause:** every delete wrote the Trash first, the right order, and then removed the note and
wrote the notes file — without asking whether the first write worked. `move_notes_to_trash`
dropped `save_trash`'s answer. The smaller notes file then saved fine, and the Trash held the
note only in memory, where nothing writes it at close. The restore direction had been fixed for
the same class long before ("a duplicate at worst, never a note in neither file"); this direction
had the order and not the check.

**Fix:** `move_notes_to_trash` returns the write's result and, when it failed, takes back what it
appended. The app's wrapper says "Nothing was deleted" and returns None, and all five delete
routes — a note, the selection, a category with its notes, the Duplicates panel, a series day
sent to the Trash — stop there with everything as it was. `test_data_safety` and qa3 make
`trash.json` unwritable; mutants TF01 and TF02.

**Takeaway:** an order that is safe only if the first step worked needs the first step's answer.
A write whose result nobody reads is a write nobody checked.

### The number too big to start

*(2026-10-27 · found by the final audit's break-it round)*

**Symptom:** three files that stopped the app at every start, for as long as they were there: a
`notes_data.json` whose repeat interval was `1e999`; a leftover notebook in the folder above the
app's, nested 990 lists deep; a `trash.json` whose entry said `"attachments": 7`.

**Root cause:** the start-up readers expected the errors JSON usually gives and not these. Python
reads `1e999` as infinity, and `int()` of infinity raises `OverflowError`, which the repeat rule's
clamps did not catch. The stale-copy purge signs raw notes by recursion, and 990 levels plus its
own frames overflowed the stack. The Trash comes in as the file held it, and the purge's list of
files to spare iterated whatever `attachments` was. None of the three was inside a guard.

**Fix:** the clamps catch `OverflowError` and fall back to their defaults. The purge's judgement
— the one place that signs raw notes — keeps a folder it cannot judge. `attachments_of` reads a
note's or entry's files as dicts with a string name, and every reader of a Trash entry's files
goes through it. A probe gave every field of a note, a Trash entry and the settings infinity,
minus infinity, NaN and deep nesting; nothing on the start-up path raises now.
`test_data_safety` holds each; mutants AT01, NF01, NF02.

**Takeaway:** a value from a file is any value its format can carry, infinity and depth
included. Code that runs before the window exists must take the safe answer — keep, skip,
default — for whatever it cannot read.

### The close that outran a failed save

*(2026-10-27 · found by the final audit's break-it round)*

**Symptom:** with the disk full, closing the window showed "Couldn't save your notes … recent
changes may be lost when you close the app" — and then closed, losing them. The message also
said to move the app to Documents, advice from when the notebook lived beside it.

**Root cause:** the close saves whatever is unsaved on its way out, and stops only for the one
question that means "take me back" (a date it could not store). A save that failed to write
showed its error and returned; the close went on to `destroy()`. The words were in the widgets
and in memory, and nowhere else.

**Fix:** `save_notes` remembers whether its last write failed. The close tries once more — the
disk may have room by then — and if that fails too, asks "Close without saving?", No being the
answer Enter and Escape give. The error says what usually causes it (a full disk, a program
holding the file) and that the changes are still on screen. qa3 fills the way with a folder
where the write's temporary file goes; mutants CS01 and CS02.

**Takeaway:** a warning that something will be lost is a promise to stop before losing it. If the
next step is the loss, the warning has to be a question.

### The preview that kept every frame

*(2026-10-27 · found by the final audit's break-it round)*

**Symptom:** a 33 KB GIF ran the app out of memory as its preview played; a 1.2 MB one grew it by
1.8 GB. A 439 KB PNG of 12000×12000 peaked at 1.7 GB on its way to a preview the size of a
window.

**Root cause:** the preview decodes an animation one frame per tick and keeps each, so its next
loop plays from memory. The 64 MB limit applied only to what is remembered after the first loop;
during it, nothing was counted. Small animations were enlarged up to eight times first, and the
list stayed referenced after the preview closed. A still image was converted to RGBA and copied
at full size before it was shrunk — `draft()` shrinks only a JPEG.

**Fix:** frames stop being kept once they pass the same 64 MB, and the animation plays the part
it has. An animation is never enlarged. Closing the preview lets its frames go. A still is shrunk
before it is converted, and an image past 50 megapixels (a JPEG is decoded small and passes) is
offered to the program the computer opens images with instead. qa7 plays each; mutants GF01–GF04.

**A frame later** *(2026-10-28 · found by the final audit's second round)*: the 50-megapixel
budget asked the first frame only. A 923 KB TIFF named `.png`, its first page 16×16 and its second
13,000×13,000, showed at once; then the animation reached page two and took 46 seconds and 2 GB.
Seeking to a frame reads its size without decoding it, so every frame is now judged before it is
decoded, and the animation stops at the first one past the budget. The preview also lets Pillow
use only the decoders of the pictures it shows: Pillow knows a file by its contents, so a `.png`
could be a TIFF, an icon set, or an EPS that Pillow hands to Ghostscript. Nothing else in the app
decodes an outside image. qa7 plays a JPEG holding a small and a large picture, and previews an
icon set named `.png`; mutants AX16, AX17.

**Takeaway:** a limit has to hold while the thing it limits is being built, not only once it is
finished — and for every part of it, not the first.

### The table drawn whole

*(2026-10-27 · found by the final audit's break-it round)*

**Symptom:** a note holding a 300×300 table — 2.9 KB as a share code — froze the app for about
40 seconds each time it opened. A 1,000-row table killed the app on Linux outright: "X Error …
BadAlloc … X_CreatePixmap", no traceback.

**Root cause:** a table is drawn as a grid of real cells, every cell at once, on one canvas as tall
as the table. Nothing limited either. 90,000 cells meant 90,000 rounds of measuring and drawing;
1,000 rows at 34 pixels passed the 32,767 pixels a window may be, and the canvas could not be
made. On Windows the result is unmeasured, which is reason enough not to find out on someone's
notes.

**Fix:** a table past 400 rows or 3,000 cells stays as its text — the pipe rows it is stored as,
searchable and editable like any line — and the status line says why. The note's data does not
change; 400 rows stay under the canvas limit at 225%. qa1 draws a 40×5 table and keeps a 401-row
and a 3,100-cell one as text; mutants TD01 and TD02. The phone's app draws the same way and got
the same kind of limit.

**Takeaway:** anything drawn whole needs a size past which it is not drawn. Outside content
chooses the size.

### The Trash restored under a window it never had

*(2026-10-27 · found by the final audit's break-it round, on the phone's app; the desktop had the
same gap)*

**Symptom:** a backup restored onto a new phone brought its Trash, kept for a year, and the next
start deleted every entry older than 30 days for good, attached files included.

**Root cause:** the import kept each Trash entry with the moment it was deleted, and took from the
backup's settings its categories and calendar decorations — but not the Trash's window. A new
notebook has none chosen, so the start-up purge went by the default 30 days: a window nobody
chose for those entries, the class of "The Trash that forgot its window".

**Fix:** when the notebook receiving the backup has never chosen a window, it takes the backup's,
if it is a whole number of days from 1 to 365. A window chosen on this device stays; a window that
could not be read stays unknown, so nothing is purged. qa3 imports a backup with a 365-day window
into a notebook without one and into one that chose 30; mutants TW18 and TW19. The phone's app
follows the same rule. Round two found the window taken when it was shorter too, which emptied
this notebook's own Trash; it is now taken only when longer than the default
([Round two](#round-two-each-fixs-next-door)).

**Takeaway:** a setting that decides what is deleted travels with the things it decides about.

### An old folder judged by one file

*(2026-10-27 · found by the final audit's break-it round)*

**Symptom:** two start-up routes acted on an older notebook's folder after reading only its
`notes_data.json`. The first start passed over an old notebook whose notes file was empty (every
note in the Trash) or unreadable — its Trash and templates with it — and a welcome note then
ended every later attempt. The cleanup of a leftover folder deleted its `notes_data_backup_*`
files unread, once the notes file beside them was covered, so a note that lived only in a backup
was gone.

**Root cause:** both asked "how many notes does `notes_data.json` hold?" and took the answer for
the whole folder. Zero meant "nothing here" to the adoption, though zero is also "all in the
Trash" and "cannot be read"; covered meant "all of it" to the cleanup, though a backup is a
notebook of its own.

**Fix:** the old app's own store (AppData, the profile folder) is adopted whatever its notes file
holds; an unreadable one comes in to be kept aside and announced as anywhere else, and its Trash
and templates come without waiting on a settings file that may be the one that cannot be read. A
backup in a leftover folder goes only when every note in it is the app's already.
`test_data_safety`; mutants MG03, MG04, PB01.

**Takeaway:** a folder holds more than its main file. Before acting on a folder, read every file
the action touches.

### The plain paste with no ceiling

*(2026-10-27 · found by the final audit's break-it round; the ceiling is the owner's choice)*

**Symptom:** pasting a long text with Ctrl+Shift+V froze the app: 600 KB took ten seconds, a
megabyte twenty-seven — and then every key typed after it took as long again.

**Root cause:** the formatted paste stops at 100,000 characters, so one paste cannot make a
note nobody can edit; its message then offered Ctrl+Shift+V, "which has no limit", for the rest.
A probe showed what the limit protects against. Text copied from a PDF has its lines rejoined
into paragraphs, and lines of one length — the probe's — became one line of 600,000 characters.
Tk lays out a wrapped line whole wherever the view or the caret moves on it, so each step paid
for the whole line.

**Fix:** Ctrl+Shift+V keeps the same 100,000 characters and says so with the same message, which
now suggests pasting the rest into a note of its own rather than a way round. The user guide
says the same. qa1 pastes past the ceiling both ways; mutant PL01.

**Takeaway:** a limit with a way round is not a limit. If something is worth protecting against,
protect every door to it.

### Round two: each fix's next door

*(2026-10-28 · found by the final audit's second break-it round, which attacked every fix of the
first by name)*

**Symptom:** eight of round one's fixes held for the case reported and not for the case beside
it, and the rounds found four new data routes as well:

- **A repeat ended another way.** A share code whose copy no longer repeated, answered Update,
  kept the series' own days in the note, out of sight, with a rescue copy that had no room for
  them. The next small edit's save dropped them with no copy anywhere, after a dialog promising
  Restore previous would undo the update. A Restore previous of a version that did not repeat
  did the same.
- **Export after a failed save.** The failed save's message sends the person to Settings →
  Backup → Export, and the backup was packed from the file on disk. It said "Export complete"
  without the very changes it was made to rescue.
- **The Trash window, shortened.** The import adopted a backup's Trash window whenever this
  notebook had never chosen one, shorter windows too. A backup from a seven-day notebook emptied
  this notebook's own Trash at the next start.
- **Signing out.** The end of a Windows session saved by its own copy of the close's list. The
  copy had drifted: a date typed short stayed unsettled, so unsaved, and a write that had failed
  was never tried again. And the end of a session is only a question the person can still cancel.
  The app stopped its backup work outright, behind a progress bar that never moved again.
- **The rest.** A Trash entry's title of 7 kept Recently deleted from opening. A first start that
  could not copy one file said "Imported" all the same. An old notebook whose settings could not
  be read lost its Trash to the default window. A name in other capitals reached a kept note's
  file. Three writers renamed files into place before their bytes were on the disk. The template
  editor moved a template's bold onto other words, and the day's reminder broke on the Settings
  page.

**Root cause:** each first fix named the route it was reported on — the update from a share code
"turns off a repeat in the editor", the purge "compares names" — and its sibling took another
route to the same behaviour.

**Fix:**
- Whatever ends a repeat keeps the series' days in the rescue copy (`days_to_rescue`), and the
  save that clears a one-off note's days keeps days no copy holds. Moving them there was itself a
  loss, which round three made a copy
  ([Round three](#round-three-one-rescue-copy-and-files-another-program-holds)).
- The export packs what the app holds.
- A backup's window is taken only when it is longer.
- The close and the end of a session run one list of saves (`_save_on_the_way_out`). The session
  asks nothing, lets an export finish and says on screen that an import was stopped.
- Trash rows read a shaped copy. Files that cannot be copied are tried again, then named. An
  unreadable old settings file travels as it is. An attachment resolves only to a file of exactly
  its name. Every rename into place waits for the disk, which `test_data_safety` now reads in the
  source. The template editor keeps styles as tags. The reminder bar goes above whichever page
  shows.
- Mutants DR01–DR24.

**Takeaway:** a fix is for the behaviour, not the route it was reported on. Before calling it
done, name the behaviour and ask every other road that reaches it.

### The photo that was a remote connection

*(2026-10-28 · found by the final audit's second round, with a crafted backup)*

**Symptom:** a backup's note listed "🖼 Holiday photo.jpg", with the picture icon and without the
"Opens in your default app" hint. Clicked, it handed Windows an `.rdp` file — a remote-desktop
connection, not a photo — and asked nothing. So did a `.pyw` (which the Python launcher runs), a
`.theme`, an Excel add-in, a Word document with macros and a Windows update package. A label
holding a right-to-left override showed its letters in another order. And a backup downloaded
from the internet gave up Windows' mark of where it came from: none of the files the import took
out of it carried one.

**Root cause:** the app trusted two things it had no reason to. The first was the label. An
attachment record has two names: `stored_as` is the file on disk, and the open, its warning and
the alias guard had all learned to judge that one ("A file with two names"). `filename` is a
label, and the row took its text, its icon and the choice of hint from it, and the warning quoted
it. The app never writes a pair that disagrees — it stores "stamp_" plus the original name — so
nothing checked that the two agree, and a backup can write any label over any file.

The second was its own list. The question before opening was asked only for the kinds on a list of
dangerous ones, and a list of dangerous kinds is never complete: Windows has hundreds of file
associations, every installed program adds more, and it had already been extended once, for the
shortcuts and disk images it missed. Everything else went straight to `os.startfile`.

The mark was lost rather than trusted. A browser leaves a `Zone.Identifier` stream on what it
downloads — the "Mark of the Web" — and SmartScreen, Office's Protected View and its block on
macros from the internet all go by it. A zip keeps it on the zip alone: `zipfile` writes plain
files, and the import copied only their contents, so its files lost the last defences Windows
would have added after the app's own.

**Fix:** `normalize_note` makes the label end in the type of the file that opens ("Holiday
photo.rdp") and takes out the characters that reorder or hide text: the controls, and the bidi
marks, overrides and isolates. The row, the remove question, the warning and the note list's hover
card read the name through the same `attachment_display_name`, so a record that never passed
`normalize_note` shows the same. The icon and the hint come from the stored file, as the click
does. A record the app made itself shows exactly as before.

And the list is turned round. `how_to_open` names the short list of kinds whose usual app only
shows what is in them — pictures, PDF, plain text and CSV, Word, Excel and PowerPoint files that
cannot hold macros, sound and video — and those open at once, so a person's own documents meet no
new question. Every other kind asks. The kinds known to run code keep the old warning; the rest
get a calm one that says only that the app does not know the kind, and opens on "Open". Missing a
kind from the dangerous list now costs the wording, never the question. Every handoff to Windows,
the preview's "Open externally" included, goes through the one gate in `_open_externally`.

The import now writes the backup's mark onto each attachment it copies out, before the file takes
its place, as Explorer's own unzip does (`zone_mark_of`, `put_zone_mark`); a disk that keeps no
streams goes without, and the import carries on. A file attached by hand already kept its own —
`shutil.copy2` copies the stream on Windows — and so does a duplicated note's copy; both are now
checked, so a change of copy can no longer drop it unseen.

`test_data_safety` (the marks on Windows); qa7 puts a raw crafted record in the editor and clicks
each kind; mutants AX01–AX12.

**Takeaway:** a label is a claim about a file; what a person sees is read from the file that will
open. And where the safe kinds are few and the dangerous ones are anything else, list the safe
ones: a list of what is dangerous is wrong the day it is written, and wrong quietly. A copy that
drops where a file came from switches off defences the app never sees, so it carries that too.

### Limits that held at the door but not after it

*(2026-10-28 · found by the final audit's second round, with files and clipboards made to hurt)*

**Symptom:** several, each from something a person could be handed — a backup, a clipboard:

- a repeating note with 5,000 moved days took a minute and a half to open, and the same again at
  every launch, for as long as it was the note last open;
- Ctrl+V of 600,000 characters of plain text pasted all of them, and every key after took more
  than a second;
- a table on the clipboard — 161 KB of HTML, or 74 KB copied from a spreadsheet — became a note
  of 210 million characters, 1.2 GB of memory, and every save took half a minute;
- a backup whose settings carried a million day colours (2.4 MB packed) made every note take
  seconds to open and the app twenty to start, for good;
- 20,000 templates in a 49 KB backup took fourteen seconds to import, and the template picker
  five to open.

**Root cause:** every one had a limit, and every limit was checked where the data came in and
nowhere after it.

- *The moved days.* A load keeps at most 5,000, the number a rule may generate, because each is
  worked out on every calendar draw. The editor's banner ("5,000 days moved") counted them by
  asking the calendar about each moved day in turn, and each question read every moved day of the
  series: 5,000 questions of 5,000 readings, twenty-five million in all. The History asked the
  same way, the count of days whose own edits fell off the schedule likewise, and the load itself
  looked each move up along the whole list of deleted days. A cap of 5,000 on the input was a
  promise of twenty-five million on the work.
- *The paste.* The 100,000-character ceiling lived in the formatted paste, and Ctrl+Shift+V had
  been given it the day before ([The plain paste with no
  ceiling](#the-plain-paste-with-no-ceiling)). Plain Ctrl+V never met either: with no HTML on the
  clipboard it was Tk's own paste, and so was the right-click menu's Paste, the comments box, a
  table's cell, a template's fields and the middle mouse button.
- *The tables.* A table's text is lined up: every cell padded to its column's widest. The paste
  ceiling counted what came in, then the padding was added — one 60,000-character cell over 3,500
  rows is 210 million spaces. A sum was capped; the padding is a product. The same padding ran
  when the caret left a table, when a cell was written and when cells were pasted in, and a row
  of 30,000 pasted cells also added 30,000 columns to every row.
- *The day colours.* Each colour's value was checked; how many there were, and whether each key
  was a day at all, was not. The import took them whole, and every settings write — one for each
  note opened — rewrote all 62 MB of them. The day markers were capped at three a day, at any
  length each, and the list of collapsed groups could stop the app starting with one wrong value.
- *The templates.* No limit at all — and the import checked each incoming name against every
  template before it, the square of 20,000.

**Fix:**

- *The moved days.* Each question is asked of all the days at once. The rule is asked once for
  every day in question — a repeat that stops after N times is walked once from its first day, not
  once per moved day — and the moved days are read once. The answers are the same, which the unit
  suite checks against the old day-by-day questions on 300 random series. The note opens in under
  half a second, restart included. test_recurrence counts how often the moved days are read
  whole, never the time, so a slow machine cannot fail it; mutants IX01–IX04.
- *The paste.* Every route reads the clipboard through one reader that keeps the ceiling. Where
  Tk would have pasted the text itself, the app pastes what it keeps, and says so in the
  formatted paste's own words. qa1 and qa9 paste past the ceiling by every door; mutants
  IX05–IX09, and PL01 now aims at the shared ceiling.
- *The tables.* Every way a table is lined up asks first what the padding would come to, and past
  100,000 spaces leaves the table ragged: each cell keeps the spaces its alignment needs, which is
  all the padding says, and the drawn grid looks the same. A paste weighs itself with its padding
  before any of it is built, and stops at the row — or the cell — where it would pass the
  ceiling; the 161 KB table now goes in as its 95,000 characters. test_tables checks the lengths
  worked out ahead against what is then built, on 400 random tables; qa1 pastes the spreadsheet
  and the 30,000 cells; mutants IX10–IX13.
- *The day colours.* The start and the import read them through one door: real days only, as the
  calendar writes them, a marker an emoji's length, and at most 20,000 days of each — every day
  of 54 years. The calendar refuses a 20,001st, so a start never drops one, and what a start does
  not keep leaves the file. The probe's import now keeps none of its million, and a note opens in
  a hundredth of a second. qa3 imports the backup and loads the file; mutants IX14–IX17, and I02
  and I03 aim at the shared door.
- *The templates.* At most 1,000, far past anyone's use: a load keeps the first thousand, the
  import stops there and looks names up in a set, and saving a 1,001st by hand is refused with a
  word. The probe's import takes a tenth of a second and the picker a third.
  test_data_safety loads the file, qa3 imports the backup and saves one too many; mutants
  IX18–IX20.
- *The reading.* The same probes found a pasted page's own reading slow: 10 MB of paragraphs
  parsed to the end after the ceiling had been passed (7 s), the styles moved once per shift of
  every padded cell, and the structure at a copy's start marker looked for each stray end tag
  along every open table. The page is now read no further than the ceiling, the shifts are summed
  once, and the open tags are counted; the slowest probe takes about a second. test_richtext
  counts what is fed to the parser and what is compared; mutants IX21–IX22.
- *Half an emoji.* A probe setting the find box to a lone UTF-16 surrogate led further: JSON can
  spell one as an escape, Tk will not draw it, and a notes file holding one in a title stopped
  the app starting, at every launch — the mend existed, but only on the way to disk ([The mend
  that only ran on the way to disk](#the-mend-that-only-ran-on-the-way-to-disk)). Every data
  file, the backup's files and a share code are now read through one reader that mends what an
  escape spells. test_data_safety reads each with one in it; mutant IX23.

**Takeaway:** a limit on what comes in says nothing about what is then done with it. Ask what the
work costs at the limit — a capped number squared is not capped — and count every door to it, not
the one the limit was written for.

### Round three: one rescue copy, and files another program holds

*(2026-10-28 · found by the final audit's third break-it round, which attacked round two's fixes
by name)*

**Symptom:**
- **Days erased.** Round two's fix for a share code that ends a repeat *moved* the series' own day
  text into the rescue copy. A second code that turned the repeat back on, or a big rewrite after
  the repeat was put back by hand, erased the days with no word. Before that fix they had stayed
  in the note.
- **The copy replaced.** Widening one table cell re-pads every row, which read as the whole table
  lost. Its copy replaced the rescue copy the note held. A big delete saved first, then the
  repeat turned off, lost the deleted words the same way.
- **A held notes file.** One held by another program at the start read as unreadable. Its copy
  failed for the same reason, and the first keystroke's autosave replaced fifty notes with one.
  At the first start of a new version, the copy of the old notebook gave the notes file one try
  and returned in silence when it was held. The app then opened empty, its first save wrote a
  notes file, and the old notebook was never looked at again.
- **Smaller gaps.** The export on such a start packed an empty notebook as "Export complete". A
  template half written in its editor went with a Windows sign-out. An import's "cut short" line
  outlived a re-import that finished.

**Root cause:** a note has one rescue copy. Anything that writes a new one takes the old one's place,
so whatever lives only there lives one save. Separately, a read that failed was taken for a file
that could not be parsed, and a copy that failed for the same reason was taken for an ordinary
failure.

**Fix:**
- Whatever ends a repeat copies the days into the rescue copy and keeps them in the note.
- Loss is measured in cells, not padding (`_without_padding`).
- A turn-off's copy keeps the text of a copy the note does not hold again, whatever came first.
- An update's question says when it replaces such a copy.
- The start reads its data files three times, half a second apart. A file it can neither read
  nor copy is never written over that run (`paths.hold_writes`), and the start says so.
- The first start's copy of the old notebook is all or nothing for the notes and settings, and
  writes nothing until it succeeds.
- The export refuses on a start that could not read the notes.
- The session end saves a template editor's work beside any template of its name.
- A finished import takes its line back.
- `test_data_safety`, qa3, qa5; mutants DR29–DR40.

**Takeaway:** a store with one slot keeps only the last thing put in it. Before moving anything
into it, ask what else will write there next. And a file that could not be opened is not a file
that could not be read: one is a moment, the other is damage.


## Tk & platform gotchas

*Where the toolkit's own behaviour was the bug: quiet defaults, platform differences, ordering rules.*

### The template editor that "did nothing" when clicked

*([0.3.0](../CHANGELOG.md#030--tags-removed-categories-as-the-sole-organization-system))*

**Symptom:** Clicking Edit on a template appeared to do nothing at all — no window, no error, no console output (the app ships `--windowed`, so any silent exception would be invisible).

**Root cause:** Two, compounding. First, the editor's own window wasn't marked to always stay on top, so it could get pushed *behind* the main window by a focus change — it wasn't broken, it was invisible. Once that was fixed, a second, subtler bug surfaced: the `-topmost` attribute was being set *after* a layout recalculation call (`update_idletasks()`), which silently failed to make it stick, specifically in that order, on the platform being tested on. Reordering it to set `-topmost` immediately, before any layout call, fixed it for good.

**Takeaway:** A `--windowed` build swallows exceptions silently. "Nothing happens" is a legitimate bug report, not a dead end — it usually means something *did* happen, just not where anyone could see it.

### The panel that lost its content depending on how you got there

*([0.3.0](../CHANGELOG.md#030--tags-removed-categories-as-the-sole-organization-system))*

**Symptom:** A Settings panel would intermittently show its content correctly, or not, depending on the exact sequence of panels opened before it — hard to pin down because it wasn't reproducible on the first open, only after certain navigation paths.

**Root cause:** The panel's internal layout math ran once, immediately, using the container's width *at that instant* — but if the container hadn't actually been mapped onto the screen yet (which depends on Tkinter's own internal timing, not application code), that width was unreliable, and the resulting layout could be wrong (chip positions computed for a much narrower container than the real one, effectively invisible or overlapping).

**Fix:** Replaced a guessed fixed delay ("wait roughly this long, then try again") with a `<Map>` event binding — Tkinter's own notification that a widget has just become visible — so the layout recalculates deterministically at the exact right moment, rather than a best-effort timer that occasionally lost the race.

### The scroll that stopped twice, for two different reasons

*([0.28.38](../CHANGELOG.md#02838--2026-08-17) · 2026-08-12)*

**Symptom:** Scrolling the mouse wheel while hovering over the theme picker's preview cards did nothing, instead of scrolling the Settings page underneath.

**Root cause:** Each preview card is a small `Canvas` widget, and Tk's `Canvas` has a built-in default mouse-wheel behavior of its own — it "handles" the scroll itself (even though it has nothing to actually scroll), which stops the event from ever reaching the Settings page's own scrollable area.

**Fix:** Forwarded the wheel event explicitly to the page's own scroll — the exact same pattern already used for every other Settings panel (categories, templates, trash, duplicates), reusing the existing shared helper rather than inventing something new.

**A second bug, found immediately after:** The same symptom — scrolling does nothing — also showed up over the Statistics summary text and its category chips. This turned out to be a *different* root cause wearing the same symptom: those are plain `Frame`/`Label` widgets with no `Canvas` involved at all, simply never wired into the page's scroll-forwarding in the first place, unlike most of the rest of Settings. Fixed with the identical forwarding pattern, applied to the Statistics panel specifically.

**Takeaway:** The same visible symptom can have unrelated causes in different parts of the same page. Confirming a fix in one spot is not evidence the rest of the page is fine — each widget subtree that's supposed to forward scroll needs to actually be wired in, and it's worth deliberately checking neighboring areas with the same symptom rather than assuming one fix covers all of them.

### The chip that looked clickable, and the fix that looked like it worked

*([0.28.38](../CHANGELOG.md#02838--2026-08-17) · 2026-08-17)*

**Symptom:** Two things, found close together while working on the same panel. First: Statistics category chips visibly highlighted on hover and showed a hand cursor, but clicking one did nothing — reproduced consistently in both the plain script and the packaged `.exe`, after scrolling the Settings page first. Second, found while building a live-update fix for the first: after deleting a category (or, later, adding a template), Statistics kept showing the old data until the page was left and reopened.

**Root cause (the chip click):** Never conclusively found. Simulated the click three different ways — including using real window hit-testing (`winfo_containing`) to find whichever widget was genuinely under the cursor at that screen position, exactly as a physical click would land — and every synthetic version worked correctly. The failure was never reproduced headlessly, despite that. Rather than keep chasing it, the interactivity was removed outright: Statistics was only ever meant to be a quick snapshot, not another way to filter notes, so a broken shortcut to a feature nobody asked to keep wasn't worth further investigation.

**Root cause (the stale count):** More straightforward — `_render_statistics()` only ever got called when Settings was first opened or the theme changed, not whenever the underlying notes/categories/templates actually changed while already on the page.

**A fix that made things worse before better:** The first attempt refreshed `_render_statistics()` from inside `refresh_note_list()`, but gated it on the Settings page's `winfo_ismapped()` state — the idea being: only redo the work if Statistics is actually visible. This looked correct and passed every scripted test, because the test scripts force `update_idletasks()` after nearly every single action. In real interactive use, `pack()`/`pack_forget()` don't reliably flip `winfo_ismapped()` synchronously — so the guard sometimes silently skipped a real update, and the reported symptom (a frozen category list, an unaligned older layout) persisted even after this "fix" had already shipped.

**Fix that actually stuck:** Removed the visibility guard entirely. `_render_statistics()` now runs unconditionally whenever `refresh_note_list()` runs, and whenever a template is added/edited/deleted. It only ever draws a handful of small widgets — genuinely cheap to redraw every time — so there's no real cost to just always doing it, and no Tk mapping-timing subtlety left to get wrong.

**Takeaway:** A visibility check that "looks like the right optimization" is worth being suspicious of when it depends on exact widget-mapping timing — Tk doesn't guarantee `winfo_ismapped()` reflects a `pack()` call synchronously, and a test suite that forces `update_idletasks()` at every step can hide exactly this kind of bug, passing cleanly while the real app still misbehaves. When the underlying work is cheap, skipping the optimization entirely can be the more robust choice.

### The button that woke up with its page

*([0.82.233](../CHANGELOG.md#082233--2026-09-30))*

**Symptom:** a note updated from a share code keeps its earlier version, and the editor offers
"↩ Restore previous". Open another note from the Calendar, with its day's "Open in editor", and
the button was still there although that note had nothing to restore — pressing it did nothing.
The same switch made from the note list hid it.

**What was happening.** Fourteen places decide whether to show or hide a button, a counter or a
panel, and each asked Tk `winfo_ismapped()` — "is it on the screen?" — when what they meant was
"does it have its place in the layout?". The answers differ in two ordinary moments: until Tk
first draws a widget after it was packed (the half the story above met in 0.28.38), and for as
long as the page holding it is hidden, because Tk unmaps every child of a hidden container and
maps them again when it comes back. From the Calendar the editor is still asleep when the note
loads, so "hide it if it shows" read Restore previous as hidden already, left it in the layout,
and it woke up with the page. The title counter did the same, and so did the share code's area,
as an empty strip.

**The fix.** One question, one answer: `_is_placed()` asks the geometry manager, which does not
change while a page sleeps, and every show/hide decision asks it. The three places that really
mean the screen — a tooltip, a click on the Settings page, the calendar's keys — keep
`winfo_ismapped()`, and are named in `tools/check_one_definition.py`, which now fails on any other
use.

**The reference pictures had the bug in them.** The fix changed two of `story_look`'s reference
photographs, and it was the references that were wrong. Scenes 04 and 05 open Settings and choose
a section in one breath, and since their first reference, on 2026-09-15, they had shown two
sections stacked — General above Recently deleted — under a nav naming one. They were accepted five
times. The tool reported "unchanged" each time, truthfully: it compares a picture with the last
one, and cannot know the last one was wrong.

**Takeaway:** ask the question you mean — "is it placed?" is not "is it on the screen?", and they
part exactly when a page is hidden. And a reference picture is a claim about what is right: look
at it as the thing its name says, not only at whether it moved.

### The DPI fix that made things worse

*([0.30.38](../CHANGELOG.md#03038--2026-08-18) · 2026-08-18)*

**Symptom:** Two side-by-side sections in the note editor (Checklist and Calculator), built with `grid()` and a shared `uniform` group specifically to force equal column widths, still rendered visibly unequal in a real screenshot from the user — despite `winfo_width()` proving both columns were pixel-identical inside Tk's own geometry math, on every window size and maximize state tested locally.

**Root cause:** The app was never declared DPI-aware, so on a display scaled above 100% (125%/150%, the user's actual setup) Windows renders the whole window at 100% internally and then stretches the finished bitmap to match the scaling factor — a blunt, whole-window operation that can apply inconsistently across nested widget hierarchies. Tk's own layout math was correct the entire time; the mismatch was introduced afterward, by the OS.

**Fix attempted:** Declared the process DPI-aware (`SetProcessDpiAwareness`, with a `SetProcessDPIAware` fallback for older Windows) and told Tk to scale its own font/spacing math to match (`tk scaling`) — the standard fix for this class of problem. Couldn't be verified visually in the development environment, since it isn't running at 125%/150% scaling, so it shipped for the user to test on the real machine that reported the bug, with that limitation flagged up front.

**Reverted:** On the actual 150%-scaled machine, the fix didn't resolve the column mismatch, and made the app's overall rendering visibly blurrier. Reverted in full rather than trading one visible cosmetic problem for a worse one.

**Takeaway:** A fix that's well-understood in theory and impossible to verify locally is still a gamble — flagging that uncertainty explicitly up front made the revert a quick, low-friction call once real-machine testing disagreed, instead of a surprise. Sometimes the right outcome is to leave a minor cosmetic issue unresolved rather than layer an unverifiable fix on top of it.

**Followed up** two months later, measured this time: [Sharp text, measured this time](#sharp-text-measured-this-time).

### Sharp text, measured this time

*([0.93.374](../CHANGELOG.md#093374--2026-10-14) · 2026-10-14)*

**The ask:** The owner chose sharp text on a 150% screen as the next piece of work. The first attempt, above, had gone out unmeasured and come back blurrier, and its code had not been kept. So nothing was written until the question had been answered on her own machine.

**What was measured:** The app was started three ways on her 150% laptop, on a made-up notebook, and photographed. The crispness of the letters' edges was compared on the same field each time:

| Mode | Edge sharpness |
|---|---|
| As it was | 1,992 |
| GDI scaling, where Windows sharpens a program's text for it | 2,177 |
| Declared aware of the main screen's scale | 4,264 |

GDI scaling looked like a one-line answer, and it was not one: Tk draws its text into an off-screen picture first, and Windows stretches that picture like any other.

**What the first attempt never saw:** She has three screens: the laptop at 150% and two monitors at 100%. Windows lets a program like this be sharp at one scale only, the main screen's. So the same build was photographed on a 100% monitor, where Windows shrinks it. There it was softer than before. That is the likeliest reading of August's "blurrier", though it cannot be proved now. Sharp on every screen ("per monitor") was probed too, and Tk cannot do it: told that the scale had changed, the text already on screen kept its size.

Shown the two copies side by side, she had not noticed the blur before: she keeps the app on a monitor. That made the choice hers rather than the code's. Sharp text is on by default, since most people who install it will have only a laptop, and there is a switch in **Settings → Appearance** for someone who keeps the app on a second screen. She asked for its words to say plainly what it does, for people who are not technical.

**What it took:** Fonts grow with the scale and pixel sizes do not. At a simulated 150% the Settings menu, two statistics captions and two theme names were cut, and at 200% thirteen things on every page. Every size that holds text or a drawn mark now goes through one of three doors; see [Sharp on a scaled screen](ARCHITECTURE.md#sharp-on-a-scaled-screen-every-size-is-given-at-100). Afterwards, every page and popup was in sight at 150% and 200%, on Windows and on Linux.

Two things were caught before they shipped:
- **CI's virtual display reports 100 dots per inch, not 96.** That was found by asking it before writing the formula. Unsnapped, the scale would have read 1.04 there and moved every pixel the suite measures.
- **A hint that pointed at the wrong Settings.** The first wording said "Settings → Display → Scale", meaning Windows. An old check, that every "Settings → X" the app shows names a real section, refused it. A person would have looked for Display in Note Organizer's own Settings, too.

**Takeaway:** The fix that failed blind was right once measured, on every screen the person actually uses. Measuring found the trade-off the first attempt never knew it was making, and a trade-off belongs to the person who lives with it. A question about how a screen looks is not answered on one screen.

### The module that existed twice

*([0.32.51](../CHANGELOG.md#03251--2026-08-21) · 2026-08-21)*

**Symptom:** Settings → About showed a blank space where the storage folder
should be, and Settings → Statistics read "Using Note Organizer since None".
The version number, two lines away from the blank path, displayed correctly.
Nothing crashed, and every one of the nine QA scripts passed.

**Root cause:** Running the app the normal way — `py note_organizer.py` — makes
the running module `__main__`. Anything that then does `import note_organizer`
does not get that module back: Python builds a *second* module object from the
same file, with its own globals, and `initialise()` has never run on it. Every
value `initialise()` assigns is still `None` there.

That mattered because the Settings page had just moved into its own mixin. It
could no longer say `APP_DIR` directly, so it grew a `_host()` helper that
imported the entry module to reach it — and under a real launch that helper
handed back the uninitialised copy. `APP_VERSION` kept working throughout,
which is what made the symptom so lopsided: it is a module-level constant, so
it has the same value in both copies. Only the values filled in at startup went
missing.

**Fix:** The two labels read from the core layer instead. `core/paths.py` now
keeps `APP_DIR` alongside the file paths it already derives from it, and the
first-launch date is read back from settings. Core modules are only ever
imported by name, so there is only ever one of them — the duplicate-module
situation cannot arise. `_host()` survives for `APP_VERSION` alone, with a
docstring saying why nothing else may use it.

**Why the test suite could not have caught it:** every QA script begins
`import note_organizer as NO`. That import *is* what makes the running module
`note_organizer`, so `_host()` returns the very same object the test is holding
and the bug disappears. The suite was not merely missing a case; it was
structurally incapable of expressing one. That is why this got its own file,
`test_entry_module_identity.py`, which loads the source under the name
`__main__` the way a launch does.

**A false negative worth recording:** the first version of that test passed
against the broken code. It tried to force the failure by blanking
`note_organizer.APP_DIR` after the app was built — but About is one of the
eagerly-built panels, so its labels already had their text and no later change
to a global could affect them. The test that works does not fake anything: it
builds the app from the `__main__` copy while the imported copy stays
uninitialised, which is precisely the production situation.

**Takeaway:** "the tests all pass" is only reassuring if the tests *could* have
failed. When a bug reaches a user through code the suite covers heavily, the
question is not "which case did we miss" but "is there a case this suite is
unable to represent at all". Here, the very act of importing the module under
test removed the condition that caused the bug.

### The bullet that had no bullet in it

*([0.34.51](../CHANGELOG.md#03451--2026-08-25) · 2026-08-24)*

**Symptom:** Put the cursor at the end of the last item in a bullet list, paste a couple of lines, and the pasted lines behaved as though they were list items — they were saved that way and came back indented on reload — while showing no bullet at all. Worse, clicking the bullet button on one of them appeared to do nothing: the app thought the line was already a bullet, so the button toggled it *off*.

**Root cause:** A list line carries its marker in the note's text and gets its hanging indent from a Tk tag drawn over it. The tag was applied from the line's start to `line.end+1c` — one character past the end, which is the newline. Tk gives text inserted between two characters that *both* carry a tag that same tag, so anything typed or pasted at that boundary inherited it. The line then had the tag but no marker, and the code decided what was a list item by reading the tag.

**Fix:** Two halves. The tag stops at `line.end` so it no longer covers the newline, and the marker in the text — not the tag — is what decides whether a line is a list item. The tag is presentation only.

**What it cost to get right:** the obvious fix, ending the tag one character earlier, broke the opposite case. Tk's inheritance rule cuts both ways: text typed at the *end* of an item is also between a tagged character and an untagged newline, so it arrived untagged too — and a wrap point in untagged text loses the hanging indent, so a long item's second line slid back under its own marker. Measuring the display lines showed them at the bare left padding instead of the indent. The tag is now rebuilt from the markers as the line is edited, one line at a time on each keystroke rather than the whole body, since rebuilding everything on every keystroke is exactly the kind of refresh work that has cost this app real responsiveness before.

**What made it findable:** mutation testing. Reverting each half of the fix separately showed the suite still passing both times — each half covered for the other in every scenario the tests exercised, so neither was actually pinned down. That produced a third test, which states the rule directly: a stray tag on a line with no marker is not a list item.

### The text box that was always eighty characters wide

*([0.38.59](../CHANGELOG.md#03859--2026-08-26) · 2026-08-26)*

**Symptom:** pasted text used only about half the width of the note, and deleting a character further down did not make it reflow into the space. It behaved as though the box were half its apparent size.

**Root cause:** it was. The Expand toggle added for the writing area called `pack_configure(expand=False)` on the box it was given, meaning to stop it filling the available space so the row count would govern its height. Both text boxes are packed with `side="left"`, where `expand` hands out *horizontal* space — vertical space is the container's to give. So the call never affected the height it was written for, and left each box at a Text widget's default width of eighty characters inside a much wider frame. Measured: 752px of 1027px for the body, 672px for comments.

**What it was *not*:** the paste. Every paste path showed it, because the box was narrow before anything was pasted into it.

**Fix:** delete the line. The height is governed by the frame around the box, which sizes itself to what the box asks for, so nothing was lost.

**Two checks that could not have caught it.** The first measured whether the text ran the full width of the box — but text always fills the box it is given; with the bug it filled a 752px box perfectly well. The second compared the box against its frame, which is the right comparison, but a Text widget's default eighty characters is about 700px and the frame in that test happened to be 727px, so it passed anyway. What does catch it is the invariant behind the measurement: a box packed `side="left"` without `expand` cannot fill its frame at *any* window size.

**Takeaway:** when a check passes, ask what it would take to make it fail. Both of these were written to guard a specific bug, and neither would have.

### The list that lost its place, twice, for two silent reasons

*([0.58.82](../CHANGELOG.md#05882--2026-08-30) · 2026-08-30)*

**Symptom:** two "known bugs to investigate" that had resisted every
reproduction attempt: the note list sometimes jumped back to the top
after an autosave or a category-group collapse, and a short list
sometimes flickered and sat displaced while its scrollbar was
dragged. "Sometimes" was the whole problem — scripted replays of the
exact reported steps came out clean, run after run.

**Root cause (found by instrumenting, not guessing):** logging every
`Configure` on the list's inner frame showed a rebuilt list's
geometry settling over *several* event-loop passes — one collapse
reported heights 106 → 276 → 820 as three separate events. Each
intermediate height becomes a too-small scrollregion for a moment,
and Tk clamps a canvas scrolled beyond it: measured live, a scroll
sitting at 546px was yanked to 380px by a transient 654px stage.
Whether an intermediate stage lands at all depends on where the event
loop happens to breathe — which is why the bug kept "sometimes" in
its description for months. The same instrumentation caught a second,
stranger shape: collapse a group while scrolled *below* it and the
content shrinks entirely above the viewport — Tk stops resizing an
embedded frame it no longer shows, so no Configure fires at all, the
scrollregion goes stale, and the canvas stays parked past the end of
the real content: a blank list until the next touch. Same family,
opposite silence — one bug fired too many events, the other none.

**Fix:** the scroll protections the editor page has carried since
0.32.x, hardened for both shapes. A full rebuild remembers its offset
in pixels and keeps the restore *in force* for a short window — 
re-applied on every late Configure (for the staged re-clamps) and on
short timers (for the shrink that announces nothing), with the
scrollregion refreshed from `bbox("all")` first so the fractions are
computed against the truth. A deliberate wheel or scrollbar move
cancels the pending restore: the user always outranks the machinery.
Four qa checks pin the behaviour — two forcing the transient states
directly, two walking the real collapse and rebuild paths — and each
was proven able to fail by mutation before it was trusted.

**Takeaway:** "hard to reproduce" usually means the trigger lives in
timing you haven't measured yet. The way in was not trying the steps
again harder — it was instrumenting what the widget actually
experiences until the "sometimes" resolved into two deterministic
mechanisms. And Tk has opinions worth writing down: geometry settles
in stages, each stage fires its own Configure; an embedded window
scrolled out of view stops being resized, taking its Configure events
with it; and a scrollregion is a claim, not a fact — refresh it from
`bbox` before trusting any fraction math built on it.

### The click that was never delivered

*([0.71.154](../CHANGELOG.md#071154--2026-09-11) · 2026-09-11)*

**Symptom:** qa2's check "clicking five chips saves exactly the
3-marker cap" failed three runs out of three on one machine and passed
on another with identical code. Instrumented mid-run, every chip still
read `highlightthickness=0`: not one of the five clicks had ever run its
binding. The decisive experiment — today's check against the *previous*
release's app code — failed too, which ruled out the regression it
looked like and named it a flake in the check.

**Root cause:** Tk discards a generated `<Button-1>` when the target
widget has no native window yet, in complete silence — no error, no
return value, the binding simply never runs and every assertion after it
is about state nothing was asked to change. A widget gets that window
when it is first mapped, and the app hides its popups whenever another
program holds the Windows foreground (they are `-topmost` by design, so
a heartbeat withdraws them rather than let them float over other
people's windows). A test process never owns the foreground — the
terminal that launched it does. So every popup click in the suite was
really asking "did the 300 ms heartbeat tick before my click?".

Both obvious predicates are wrong, which is what made the first fix
attempt worse than the bug: measured directly, a widget scrolled out of
a canvas and a popup that was mapped and then withdrawn each report
`winfo_ismapped()` and `winfo_viewable()` as 0 **and receive events
perfectly well**. Gating on them refused qa6's category swatch, which
merely sits below the fold of a scrolling settings panel — on Windows
and on Linux alike.

**Fix:** ask for `winfo_id()` first. It is not a query: it calls Tk's
`Tk_MakeWindowExist`, so the native window is created on the spot and
the event has somewhere to land. Measured side by side, a never-mapped
popup child receives the click after `winfo_id()` and drops it without.
All 26 generated clicks across qa1, qa2, qa6, qa7 and qa9 go through one
helper (`qa/_qa_support.py`), and popup visibility is pinned so it no
longer depends on who owns the OS foreground — the app's real
hide-and-restore behaviour keeps its own coverage in qa1, which drives
the heartbeat directly with both answers stubbed.

**The class was wider than the click:** Tk delivers EVERY generated
pointer event — press, release, drag motion, wheel, hover — to the
window named in the event, so all of them shared the failure; the first
sweep converted the 26 bare clicks and left 48 siblings raw, which the
completeness critic counted. All pointer events go through one door now
(`fire()`, with `click()` as its shorthand), and that door refuses
KEYBOARD events loudly: a generated key follows the FOCUS, wherever it
was aimed, so the window repair would be a lie for it — key events keep
the focus discipline instead, and the six sites that aimed keys off an
unpolled focus_force got insist-loops the same day.

**Takeaway:** an input event with no error path is a silent no-op, and a
silent no-op inside a test is worse than a crash — it can produce a
false green just as easily as a false red, on any check asserting that
some click did *nothing*. Sibling of
[The chip that looked clickable, and the fix that looked like it worked](#the-chip-that-looked-clickable-and-the-fix-that-looked-like-it-worked):
the same widget-visibility machinery, met from the other direction.

### The paste that landed on top of the placeholder

*([0.75.185](../CHANGELOG.md#075185--2026-09-28))*

Right-click a new note's title, choose Paste, and the field read
`Note title...My pasted title`. The grey hint text the app puts there to
say "type a title here" was still sitting in the box, and the pasted text
was glued to the end of it. The same on the Calendar's History search,
where the glued query — `Search all calendar entries...budget` — matched
nothing, so the search read as broken rather than as misfilled.

**Found by a pre-flight, not by a report.** The register wanted a paste
menu on two fields that had none (the sidebar search, the date field), and
the sibling sweep that precedes any fix here asked the obvious next
question: which fields have a placeholder *and* a paste menu already? Two
did. Both were broken, and had been for as long as the two features had
coexisted.

**The mechanism is a Tk precedence rule.** `add_placeholder` clears the
hint in two places — `<FocusIn>`, and `<KeyPress>`, the latter with a
comment explaining that focus alone loses the race when someone clicks and
types immediately. A paste is neither. `_add_paste_menu`'s Paste entry
performs the paste with `event_generate("<<Paste>>")`, so no key is
pressed at all and the `<KeyPress>` clear never runs.

Ctrl+V looked like it should be safe — it *is* a key press — and on the
date field it was. On the title it was not, and the difference is the
whole lesson: **Tk fires one binding per bindtag, and in the same tag a
VIRTUAL event outranks the physical one that produced it.** The title
binds `<<Paste>>` itself, for its length cap. So on Ctrl+V the title's own
handler won the widget tag and `<KeyPress>` was never consulted. The date
field binds no `<<Paste>>`, so `<KeyPress>` matched and the hint cleared.
One field, two routes broken; the other, one route broken — from a single
missing binding, and the shape of the difference was invisible until it
was measured on both.

**A prediction of mine was wrong in the middle of this**, which is why the
second half is measured rather than argued: I reasoned that Ctrl+V must
already be safe everywhere because it is a key press, and the probe said
otherwise on the title. The bindtag rule above is the explanation that
survived being measured on both fields.

**The second face of the same bug.** `_on_title_paste` computes
`room = TITLE_MAX_LEN - len(self.title_entry.get())`, and with the hint
still in the box that `len` was 13 too large — so a long paste came back
thirteen characters short of the cap. One mechanism, two symptoms.

**Fixed at the root of the class:** `add_placeholder` now clears on
`<<Paste>>` too, which covers all four placeholder fields at once and the
next one added without anybody remembering to. That needed a second edit
to work: the title bound its own `<<Paste>>` with a plain `bind()`, which
*replaces* the widget's binding for that sequence — so the new clear would
have been silently displaced on the one field where the bug was worst.
Both are `add="+"` now, and registration order makes the clear run first.

**What the existing check had proved, and what it hadn't.** qa1 already
covered pasting a long title — by calling `app._on_title_paste()`
directly, on a field it had just emptied. So it proved the handler and
said nothing about the route, and it passed throughout. The same shape as
the register's C-22, found days earlier: a check only ever proves what it
actually exercises.

**One of the new checks was satisfied by coincidence**, caught by the
mutants rather than by review. It read
`len(title.get()) == TITLE_MAX_LEN` after a long paste — and with the bug
present the field held `Note title...` plus `TITLE_MAX_LEN - 13` q's,
which is `TITLE_MAX_LEN` characters exactly. Right length, first thirteen
characters wrong. It now asserts the content, and a length is on notice as
the weaker question.

**Takeaway:** when a widget's own binding and a shared helper's binding
name the same sequence, one of them is about to disappear — `bind()`
replaces, `add="+"` accumulates. And a "clear the hint before input lands"
rule must enumerate the ways input *arrives*, not the ways it is typed:
`<KeyPress>` is one door, `<<Paste>>` is another, and a virtual event will
quietly take precedence over the physical one beside it.

### The sweep that stopped at the edge of the Settings page

*([0.81.202](../CHANGELOG.md#081202--2026-09-29))*

**Symptom:** a note card in the sidebar showed its checklist as `☑ 1/` —
a fraction with its denominator gone. Not reported: noticed in a
screenshot taken for the documentation, of an ordinary note.

**What it really was:** every line on a card is a `tk.Label` with no
`wraplength`, packed `fill="x"` into a sidebar of fixed width. Tk draws
such a label as one line as long as its text and lets the container show
whatever fits. Nothing marks the cut. Staging a note carrying everything
a note can carry showed the size of it: the title lost four words, the
preview stopped mid-word with the `...` it had earned cut off as well,
and the row of marks dropped the attachment count, the table mark and the
checklist progress outright.

**Why it is a story rather than a commit:** this exact mechanism had
already been found and fixed — in `0.73.167`, where three Settings
subtitles stopped mid-word, and which left behind `_wrap_to_own_width`
precisely so nobody would hand-pick a width again. That sweep looked at
the Settings page and stopped there. The note list has the narrowest
labels in the app and was never walked.

Two things made it survive eleven weeks. The character caps beside it
*look* like width management: `preview_src[:40]` and
`_truncate(title, 42)` keep a string short, and a reader checking for
"is the length bounded" finds a yes. They bound the wrong quantity —
forty narrow characters fit where forty wide ones do not, which is how a
39-character body still ran off the card. And the qa suite had no check
that asks what a card actually *shows*: everything about cards was
asserted against the model, never against the pixels.

**The fix and its sibling sweep.** Three calls to the existing helper,
and no new idea — a second way to do the same thing would have been the
real regression. Then every other `_truncate` call site was walked, and
the sweep's result is mostly *not a bug*, which is worth recording as
much as a fix: the Trash row's sub-line had already been wrapped by an
earlier report, its title's 42-character cap is enough in a panel that
wide (photographed to check, not assumed), the calendar's day chips carry
`wraplength=88`, and the day tooltip packs `side="left"` inside a popup
that grows — where the helper would be actively wrong, as its own
docstring says.

**One thing only the photograph could say.** Wrapping the preview left it
ragged, because `anchor="w"` places the text *block* and `justify` places
the lines inside it — and Tk centres a second line by default. The label
had been single-line for its whole life, so `justify` had never mattered.
No amount of reading the diff would have shown that; looking at the
picture did, immediately.

**Takeaway:** a fix's sweep has to name the surfaces it did *not* visit,
or the next instance waits for a screenshot. A cap in characters is not a
width. And any change that makes text wrap for the first time inherits
every multi-line default the widget had been hiding.

### The window that closed under its own question

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Closing the window while a question was on screen ("Save changes?", a delete
confirmation) made the window disappear — and left the app running with no window, holding the
notebook's lock, so the next launch said another copy was open.

**Root cause:** A question waits in `wait_variable()`, which only its own answer ends. The close
handler destroyed the window underneath it, so the answer could never come and the wait never
returned.

**Fix:** While a question asks, the close is refused and the question comes forward instead —
out of the taskbar if needed, with the keyboard on its button — as a modal question on Windows
does. And a question whose card is destroyed by any route ends its wait with its safe answer.

**Takeaway:** a wait that only one event can end needs every other way out to end it too — or
to be refused while the wait is on.

### The click that deleted its own next command

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** After a dropdown was opened inside a popup — the Category list in the template
editor, the Month list in Jump to month — every dropdown in the app was closed by the same click
that opened it, until a restart. Elsewhere, silently, many clicks raised "invalid command name"
background errors that nobody saw.

**Root cause:** Two Tk rules, met by several handlers. Tk expands every script bound to an
event before it runs any, so a handler that destroys its own widget or popup, or unbinds a
neighbour, deletes a command the same event is about to call. And each popup stored the
window-level binding it added in one slot per kind, so a list inside a popup overwrote its
host's slot and the host's handler stayed bound for good. A third rule surfaced while fixing a
sibling: given a string script, tkinter's `bind()` ignores `add="+"` and replaces the widget's
other bindings.

**Fix:** Each popup keeps its own window-level lines, removed when it goes by whatever route,
and every line calls one command that is never deleted. The tooltip's hide is one command
registered on the window, its "+" spelled into the script.

The same rule came back a round later through the keyboard. The rename box's Escape closed the
box and returned nothing, so Tk went on to call the box's own Escape binding, which the close
had just deleted: every Escape in a category rename or a template name left an error in the
background. A widget-level handler that destroys the popup it lives in returns `"break"` now —
nine such handlers, swept, though only that Escape raised.

**Takeaway:** in Tk, a handler is not alone with its event — ask what else the same event will
still call after you destroy, unbind or rebind something. And capture `bgerror` in tests:
Tk reports these errors to nobody by default.

### The Cut that arrived as a key

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Selecting a bold word and pressing Ctrl+X, then Ctrl+Z, gave the word back plain —
though the same Cut chosen from the right-click menu came back bold. Ctrl+V over the word did
the same, and so did Tk's own Ctrl+H, Ctrl+K and Ctrl+T.

**Root cause:** The bindtag that notes the formatting before Tk's own deletes listened for
`<<Cut>>` and `<<Paste>>`, and told a virtual event from a key by the event's type. A key that
means Cut fires that binding with the key's own press — type KeyPress, keysym `x` — so the
handler read Ctrl+X as a control character typed over a selection, which deletes nothing. Only
the menu's `event_generate('<<Cut>>')` was a true virtual event, and that is what the checks had
generated. Paste had a second gap: the app's own paste routes, each an undo unit, ended the run
before Tk's paste deleted anything. And Tk binds Ctrl+H, Ctrl+K and Ctrl+T on every platform,
keys the app had never heard of.

**Fix:** Each virtual binding says what it is, whatever reached it; a paste that falls through
to Tk gives the run back while the text is unchanged; and the three Tk keys are worked out as
Tk's own text.tcl works them. The checks press the keys a person presses, with Tcl's clipboard
replaced inside the test process so the machine's own is never touched.

**Takeaway:** a binding for a virtual event is reached by keys too, and then the event is the
key's — tell what happened by which binding fired, not by the event's type. And check with the
key a person presses, not with the event a menu generates.

### The table that changed shape under its own undo

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Type a table by hand, press Down to leave it — it lines up and turns into a grid —
then Ctrl+Z: the header came back as "| Item name | Qt  |", a letter gone. The next Ctrl+Z took
another. Even Ctrl+Z then Ctrl+Y inside a table still being typed brought back "Qyt" for "Qty".

**Root cause:** Tk's undo stack records every edit by its position, line and column. A drawn
table's grid is an embedded window, and a window takes a column: the first one of the table's
first line. A table typed by hand is plain text while it is typed, so its rows — and the tidy
that pads them as the caret leaves — were recorded with no window there, then replayed with one.
Every position on that line landed one column to the left. The table operations had been fixed
for exactly this months before (a step recorded with the grids down is replayed with them down);
the typed table never went through a table operation, so nothing marked its steps.

**Fix:** A step no unit of the app's noted — typing, Tk's own deletes and paste — can never touch
a drawn table's line, because the caret guard keeps the caret off them; so it is replayed with
the tables down, always, and marked so for Ctrl+Y. A unit that lines up a table not yet drawn is
marked the same way, split only if it already wrote into a drawn table's first line with the
window in place.

**Takeaway:** a recorded position is only as good as the layout it was recorded in. Whatever can
insert something that occupies a position — a window, an image, a hidden mark that counts — must
either be on the undo stack itself, or make every replay happen in the state the step was
recorded in.

**Follow-up:** The next round found where the rule did not reach. The formatting journal keeps
100 steps; past them a step was dropped, read as typing, and replayed with the tables down — a
header cell written long before came back a column off. A step past the cap now stays as a
stub that says how it was recorded, and stubs are not capped, because Tk's own stack is not:
a cap would only move the bug further back. A unit that begins with no table drawn is recorded
with the tables down from its start, and split where it goes on to write into a table it drew;
Tk's own deletes of styled text, which the app notes, are marked like every other step of Tk's.
A record that is trimmed must keep what its replay reads.

### The line under a table that knew where it was, not what happened on it

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** A table at the very end of a note gets an empty line under it from the drawing, so
the caret has somewhere to go. Ctrl+Z back past the Enter that had made a line there, then
Ctrl+Y, doubled the line, and from then on a header cell's edit was replayed a column off
(`| Name s   |`).

**Root cause:** Tk never records the drawing's line — the drawing is kept off the undo stack —
so Tk's idea of the text is one line shorter than the note. Redoing that Enter put Tk's own line
back beside the drawing's, and every snapshot the formatting journal took after that named a
text Tk could not reach: the steps stopped matching, read as typing, and were replayed with the
tables down.

**Fix:** The first fix followed the line with a mark, left it out of the journal's count, and
took it out before every Ctrl+Z. The next round of breakers found four ways it lost data. A
word typed on the line and erased left the same text, but Tk now held steps on that line:
taking the line out glued the word to the table's last row. A delete that took the line moved
the mark onto the person's own line, and Ctrl+Z put the table back glued to the line above. A
list renumber, which rewrites the whole body, came back without a single bold or italic. The
mark knew where the line was, never what had happened on it. Now the line is held only while
nothing has changed the text since it was drawn, which Tk's own modified flag says: every
insert and delete sets it, recorded or not. The moment anything does change it, the line is
the note's for good, and every older snapshot counts one more line break at its end — which is
how Tk will give those texts back.

**Takeaway:** the same text can sit on top of different histories. A check that reads where
something is, or what the text says, cannot tell whether an undo stack has steps there; ask
what has changed since — here, a flag every change sets.

**Follow-up:** One of the readers the fix had to reorder — a unit's first snapshot, read before
the call that settles the line — was fixed in its near-twin instead: two methods with the same
few lines, one named in the commit message, the other edited. The next round found the
untouched one by the symptom it left (a cell's bold half lost on Ctrl+Z). The sweep that would
have caught it is mechanical: list every reader of the value, not the ones memory offers.

### The flicker that was a word count

*([0.97.405](../CHANGELOG.md#097405--2026-10-27) · 2026-10-26 · seen by the owner after deleting
every note at once · issue #315)*

**Symptom:** right after moving all her notes to the Trash, the editor's menu flickered, and the
app felt slow until she reached the Trash. She asked whether a person deleting hundreds of notes
at once would meet the same.

**Root cause:** not the delete. Measured at 500, 1,000 and 2,000 notes, the move, opening the
Trash, Undo, Empty trash and a start over a full Trash each took under a quarter of a second, and
nothing brought the screen up to date in the middle of the delete (the slowness that day was the
machine, busy with an emulator). A second probe recorded where every widget of the editor stood
before the delete and after it: one row had shrunk from 32 pixels to 21, and everything under it
had moved up by the difference. That row holds "Note" and the words readout — "46 words · 223
characters" with "under a minute to read" on a second line, and nothing at all for an empty
note. Tk sizes a row to its tallest widget, so the toolbar and the note's box jumped whenever
the editor went from written to empty (a deleted note, + New Note) and back at the first letter.

**Fix:** the readout is two lines tall whether it says anything or not (`height=2`); qa1 holds
the toolbar's place as the editor empties, and photographs before and after a delete show it
still.

**Takeaway:** a label whose text can come and go sizes its row by what it says at the moment;
give it the height of its tallest state, or the layout moves with the words.

### The app the keyboard could reach only half of

**Symptom:** in the final audit before publishing, an agent walked Tk's own Tab chain on every
page and listed what a mouse could press that Tab never reached. The list was long: all thirteen
dropdowns (Text size, the app's one setting for reading, among them), the colour and emoji
pickers, a category's rename, colour and delete, the eight theme tiles, the alignment buttons,
the sidebar's arrow, every day of the calendar, and the delete toast's Undo, gone after eight
seconds. Where Tab did go, it often went out of sight: at the window's opening size it landed on
Save and Delete below the fold, and on sixty Trash controls, with the view standing still.

**Root cause:** four things, one of them Tk's and three the app's. A control the app draws — a
canvas, a label, a frame of labels — was given a mouse binding and nothing else: no `takefocus`,
no key. A popup is a window of its own, and Tab never leaves the window it is in, so even a
picker made of real buttons was out of reach once open. Tk's Tab moves the keyboard and never the
view, and the pages here are frames drawn on canvases. And then, found only by a photograph of
the emoji picker: **Windows draws no focus colour round a label.** Tk said the keyboard was on
the second emoji, its `highlightcolor` was the ring's, and the picture showed nothing; it draws a
label's resting colour, `highlightbackground`, and only that.

**Fix:** once, in the helpers every popup and drawn control goes through. Two bind tags, bound
once: Space and Return press a drawn control, and the arrows, Home and End walk a popup's choices
by where they stand. A popup asked for from the keyboard takes it, on its current choice, and
gives it back to its opener when it closes, by any road; a click's popup leaves the keyboard
where it was. A press that draws its page again puts the keyboard back where the control stood.
The calendar's month has its own ring and arrows, as the note list has. What Tab lands on is
scrolled into sight. And the ring is both border colours while the keyboard is on a control, in
the theme's text colour, which the contrast gate now measures (the accent the checklist's ring
wore is under 3:1 on two light themes).

**How it is held:** qa6 walks every page — the notes page, the calendar with a day open, History,
each Settings section — and fails on any widget a click acts on that is neither a Tab stop nor
inside one. It is the class's check rather than a list of the instances, so the next control
drawn with a mouse binding alone turns it red. Each route has its own checks and mutants (KF, KD,
KP, KB, KC in `tools/mutants.json`).

**Round 2, the fix's neighbourhood walked a day later:** six more, each fixed as a class. A popup
with no choices landed on the ✕ its header builds first, so a space typed into a new template's
name closed the editor; it lands in its first box to type in now. Every "Show N more" left the
keyboard on the window, about a hundred Tabs back: Tk's own buttons take Space through their
class binding, which never reached the put-it-back step, and run the command 100 ms after the
key. The binding is wrapped once, and a template checklist's tick box was found on the same road.
Keyboard shortcuts, all labels, could not be scrolled at all; Page Up and Down, the arrows, Home
and End scroll every Settings section. The click counter never counted a left click, because Tk
runs only a tag's most specific binding. The reminder bar's ring kept an old theme's colours, and
a banner hid the Undo the keyboard was on without moving it. Mutants KR01–KR12.

**Takeaway:** a mouse binding is not a control; a control is what both hands can press. And a
focus ring is a claim about the screen: Tk saying the keyboard is there, and a colour option
saying what to draw, were both true while nothing was drawn — look at the picture.

## Editor & input interaction

*Typing, pasting, focus and timing — bugs that live between the keyboard and the widget.*

### A calendar that kept navigating behind the user's back

*([0.5.0](../CHANGELOG.md#050--2026-08-09) · 2026-08-09)*

**Symptom:** Found while testing the Settings-page restructuring, not reported by a user. If Calendar was the last tab open before switching to the new Settings page, the calendar's own keyboard shortcuts (Page Up/Down, Home) still worked — silently changing the month shown on a calendar the user could no longer see, behind the now-covering Settings page.

**Root cause:** The guard that's supposed to restrict calendar shortcuts to "only when Calendar is actually showing" checked which tab the notebook widget considered internally selected — but Settings became a separate page shown by hiding the notebook entirely, not a third tab. The notebook doesn't lose track of "Calendar was selected" just because something else is now covering it, so the guard's underlying assumption (selected tab == visible tab) quietly stopped holding once Settings could cover the notebook without changing its selection.

**Fix:** The guard now also checks that the notebook widget is actually mapped on screen, not just which tab it last had selected — both conditions have to be true.

**Takeaway:** A restructuring that changes *how* a page becomes visible can invalidate assumptions baked into unrelated code that never mentions the thing being restructured — this guard's code never referenced "Settings" at all, yet still broke because of it. Worth deliberately re-testing behavior that depends on "is X currently visible," specifically, after any change to how visibility is managed anywhere in the app.

### The date field that either lost your edit, or wouldn't let you finish typing it

*([0.28.38](../CHANGELOG.md#02838--2026-08-17) · 2026-08-10)*

**Symptom:** Typing a date into a note and clicking away (rather than pressing Save) silently didn't save it — the only field in the editor that behaved this way; Title, Body, and Comments all autosaved fine.

**Root cause:** The Date field was simply never wired up to the autosave debounce timer that every other field uses.

**Fix, and a second bug it uncovered:** Adding the missing binding was a one-line fix — but it immediately surfaced a second, subtler issue. Autosave reuses the exact same validation as the manual Save button, which requires a complete, correctly-formatted date. With autosave now firing mid-keystroke, a still-incomplete date (e.g. "2026-1") tripped that validation and popped an "Invalid date" warning that blocked further typing — an automatic, unrequested action interrupting the user is a worse bug than the one being fixed. The fix: keep the warning for an explicit Save click (where the user is done and wants to know something's wrong), but have autosave silently do nothing until the field holds a valid value, instead of complaining.

**Takeaway:** Reusing validation logic between an explicit user action (Save) and a silent background one (autosave) is risky by default — what's a helpful, blocking warning in one context is a disruptive interruption in the other. Worth checking, deliberately, whenever wiring a new field into an existing autosave path.

### The autosave that could interrupt you over a note that was already gone

*([0.28.38](../CHANGELOG.md#02838--2026-08-17) · 2026-08-12)*

**Symptom:** Never reported by a user — found while testing the fix above. An automatic, silent autosave could, in rare timing-dependent cases, pop a real "Note missing" error dialog and block until clicked.

**Root cause:** There are two paths that trigger autosave: switching notes/tabs, and a debounced timer that fires shortly after you stop typing. The first already had a safety check — if the note it's about to save no longer exists, do nothing quietly. The second, timer-driven path was missing that same check, so if it fired after its note had been removed some other way in the meantime, it hit the same "Note missing" dialog a manual Save would show — appropriate for something the user directly asked for, not for something automatic.

**Fix:** Added the same existing guard to the timer-driven path.

**Takeaway:** The same protective check is sometimes needed in more than one place that leads to the same outcome — a fix applied to one path doesn't automatically cover another path that ends up calling the same risky code. Worth asking "is there another way to reach this same code?" whenever adding a guard like this one.

### The autosave that asked questions

*([0.66.102](../CHANGELOG.md#066102--2026-09-07) · 2026-09-07)*

**Symptom:** Found by an adversarial review agent probing the delete fix's
neighbourhood, not from a field report. Editing one day of a repeating
series, every pause in typing popped the modal "Save: this occurrence or
the whole series?" — the background autosave was asking it. Worse:
pressing Ctrl+S while a debounced autosave was pending stacked a second,
pixel-identical prompt exactly over the first. Answering the top one
released the only input grab Tk has (local grabs don't stack), leaving
the bottom save frozen mid-function — a ghost that, if answered later
after switching notes, wrote the *other* note's colour, attachments and
checklist into the series.

**Root cause:** `save_current_note` opens the occurrence-scope prompt
with no regard for `auto` — while the two warning guards beside it
(invalid date, repeat-without-a-date) are both gated `if not auto:`,
with comments explaining exactly why a background save must not
interrupt. The scope prompt and the "Empty note" warning simply never
got the same treatment. Underneath, the dialog helper's modality is a
single non-stacking local grab: a second `grab_set` steals it, and the
first dialog's `grab_release` never gives it back.

**Fix:** The invariant is now *autosave is mute*. The timer path
(`_autosave_now`) defers an occurrence save instead of asking — the
edits stay in the editor, and the next explicit gesture (Save, a note
switch, closing the app) asks then and saves. Answering saves where the
user chose; cancelling keeps the edit only as long as the view stays —
cancelling on a switch or at close still discards it, as those paths
always have. The "Empty note" warning joined its two neighbours behind
`if not auto:`. With no timer able to ask a question or raise a warning
(the one deliberate exception stays: a failed disk *write* still
surfaces its error, because silent data loss is worse than an
interruption), the stacked-prompt ghost has no way to form. Making the
dialog helper itself stack-safe (returning the grab to the dialog
underneath) was tracked separately as hardening, and shipped in
[0.83.335](../CHANGELOG.md#083335--2026-10-02).

The adversarial review of the fix itself then caught two gestures that
broke the new promise: Ctrl+N and the calendar's "Add note for this
day" cleared the editor without flushing at all — a pre-existing
half-second hole that the deferral would have widened into losing a
whole session. Both flush first now, and the sweep confirmed every
other route into an empty editor already flushed, asked, or acted on a
note that no longer existed.

**Takeaway:** a background timer must never ask the user anything — a
dialog is a conversation, and conversations happen at gestures. And when
one guard in a function carries an `if not auto:` with a good comment,
every dialog below it in the same function deserves the same audit; the
two that lacked it were the two that bit.

### The day that waited for a question

*(2026-10-12)*

**Symptom:** A field report on the packaged app, in the owner's words: how to change just one
day of a repeating note could not be found — opening a day offered only the series' date and its
repeat, as fields to change. And a category changed on a note "seemed to do nothing": picked
from the editor's corner, it stayed the old one.

**Root cause:** Two halves of one design. A day opened from the calendar was the series' editor
with one line above it: the date field showed the series' start, the repeat its rule, and only
that line said which day this was. And a day never saved by itself. Its save asked "This
occurrence only, or the entire series?", a question a timer must never raise
([The autosave that asked questions](#the-autosave-that-asked-questions)), so its edits waited
in the editor for a gesture — Save, a note switch, closing — and nothing on screen said they
waited. Measured on the real app: the corner said Work, the file said General, the status line
said only the day's date, and the series' card in the list, which a day never changes, kept the
old category.

**Fix:** The owner chose a clear day mode, of three options put to her. The calendar offers two
doors for a repeating note, **✏ Edit this day** and **🔁 Edit the whole series**. A day's
editor shows a strip naming the day and saying that what changes there stays on it, with the
way to the series; its date as words and its repeat as a line, the series' own values kept out
of sight in their fields; "This day:" beside the category; and the checklist and the files
marked as the whole series'. The person chose the day before typing, so the question went: a
day saves to itself as it is typed, like any note, and the timer's mute promise holds with
nothing deferred.

Removing the question exposed two things. A day saving itself as it is typed would leave a copy
of the series behind whenever a letter was typed and taken back, and that copy cuts the day off
from every later edit of the series: a day whose edit ends equal to the series now keeps none
(`day_matches_series`). And the save's routes that served only the answer "The entire series",
given on a day, could no longer be reached; they went, rather than staying as code nothing can
run. 52 checks in five suites failed on the old promise. They were rewritten to say what the app
does now — a few merged or dropped along with the route they described — and where one guarded a
mechanism that still exists (going back on the way out keeps you where you are), it was wired to
the question that still asks it: a date the save cannot store.

**Lesson:** an edit that waits must be seen waiting. Deferring for a good reason — no question
from a timer — still owes the screen a sign that something was deferred; without one, the wait
reads as "nothing happened". And when where the person came from can answer a question, ask it
at the door, not at the exit.

### The username cap that took three tries

*([0.28.38](../CHANGELOG.md#02838--2026-08-17) · 2026-08-12)*

**Symptom:** Found during manual testing of a planned 30-character cap on the username field. Typing past the limit was still sometimes accepted well beyond 30 characters, and the eventual correction only happened silently when the name was saved — visually indistinguishable from the app just losing whatever was typed past that point.

**Root cause:** The per-keystroke block used Tkinter's standard `validate="key"` mechanism, which has a known real-world reliability gap under very fast or held-down typing — it can miss keystrokes it should have caught.

**Fix:** Layered instead of relying on one mechanism. Kept the per-keystroke validation as a first pass, added an immediate correction on every key release (a plain, more reliable event binding, not the special validate hook with the gap) so an over-length value gets caught within a fraction of a second instead of being left to grow freely, and kept a final save-time truncation as an ultimate backstop regardless of how the value became too long in the first place.

**Takeaway:** Don't trust a single validation mechanism for something a user can trigger arbitrarily fast — independent, redundant layers cost little to add and catch what any one layer alone can miss.

### The focus fix that broke the thing it wasn't touching

*([0.28.38](../CHANGELOG.md#02838--2026-08-17) · 2026-08-12)*

**Symptom:** Clicking a non-interactive part of the Settings page didn't move keyboard focus away from a field that had it, leaving its cursor blinking even after the value had autosaved. A first attempt at fixing this — binding a click handler individually on every section's title, subtitle, and card — worked inconsistently under rapid clicking, and, worse, broke the "switch tabs and back" case, which had already been working correctly before this fix was ever written.

**Root cause:** Binding the same handler separately on many individual widgets is easy to get inconsistent, and the first fix was only tested against the specific scenario in the bug report (same-page clicks) — not the already-working tab-switch case, so nothing caught the regression before it was noticed by hand.

**Fix:** Replaced the scattered bindings with a single, centralized handler bound once on the whole app — clicks bubble up to the toplevel by default unless something along the way stops them, so one handler reliably catches all of them — scoped narrowly by checking whether Settings is actually visible and whether focus is genuinely on a field that should lose it.

**Takeaway:** A fix scoped to "the exact widgets named in the bug report" can still break unrelated, already-working behavior that happens to depend on the same underlying mechanism. Worth explicitly re-testing the previously-working case, not just the newly-reported one, before considering a fix complete.

### The fast-typing fix that took three tries to land safely

*([0.31.39](../CHANGELOG.md#03139--2026-08-18) · 2026-08-18)*

**Symptom:** Building Phase 1 of rich text formatting, a user asked for "sticky" formatting — toggle Bold with nothing selected, and it should apply to whatever gets typed next, until toggled off again. The first working version tagged "the one character right before the cursor" on every `<KeyRelease>`. It passed every test, including manual use — until the same user reported that typing quickly while Bold was on left some letters un-bolded.

**Root cause (the original gap):** `<KeyRelease>` fires once per keystroke, right after that keystroke's own insertion — true, but under a fast burst Tk can process several `KeyPress` insertions before it gets around to dispatching the `KeyRelease` callbacks for them. A callback can end up running once the cursor has already moved past more than one new character, and "the character right before the cursor, right now" silently skips whichever ones came in between. Every test that exercised this called `update()` after each simulated keystroke, which gives Tk time to fully settle between them — exactly the condition that hides this bug, and exactly why it only ever showed up in real, fast human typing.

**Attempt 1 (reverted): hooking the Tcl level.** To close the gap with true per-insert precision, the Text widget's own Tcl command was renamed and a Python proxy installed in its place, so every insertion — real typing, at any speed — could be tagged synchronously as part of the exact same call that performed it. This caused **three separate, unpredictable app-launch crashes** in real use, each from a different Tk-internal operation (a `sel.first`/`sel.last` selection query; an empty-string index from the proxy's own bookkeeping re-entering itself recursively) that normally fails silently and harmlessly at the C level, but turned into a real, escaping Python exception the moment a Python proxy sat in the call path. There was no way to find each one except from a crash log after it had already happened once — an unacceptable trade for closing what was, ultimately, a minor formatting gap.

**Attempt 2: a tracked anchor mark.** Reverted to `<KeyRelease>`, but instead of tagging one guessed character, a left-gravity mark tracks *where the pending run started*; each callback tags the whole span from that mark to the current cursor, however many characters that turns out to be, then advances the mark. However many keystrokes pile up before a callback gets its turn, the next one covers all of them in one go. Deciding *whether* a given `KeyRelease` represented real typing (vs. a navigation key, or the toggle shortcut's own key-release) was done by inspecting `event.char`/`event.state`. This passed a five-round fast-typing stress test locally on Windows — and then failed the exact same test in CI (Linux + Xvfb).

**Attempt 3 (the one that stuck): stop inspecting the event, inspect the text.** A differently-behaving Tk build populates `event.char` differently for at least one synthetic key event in a fast burst, which got misread as "not real typing" and silently ate a chunk of already-typed text out of the tag — the same *class* of bug as the original gap, just relocated. The fix: decide whether to extend the tag based on whether the note's actual character count grew since the last check, a fact about the widget's content that doesn't depend on how any particular platform's Tk build fills in event details. A paste (which also grows the count) is excluded separately, via its own `<<Paste>>` handler that resyncs tracking right after the paste lands — not by trying to tell "typing" and "paste" apart from the event that happens to follow either one.

**Takeaway:** The safest-*looking* fix (closing a timing gap with true synchronous precision) was the most dangerous one in practice — three crashes from internal Tk behavior that had never needed to be visible to Python code before. The fix that actually shipped uses only ordinary, already-proven-safe Tkinter mechanisms (the same mark-tracking pattern the calculator's insert-into-note feature already relies on) and is *less* theoretically precise, but categorically safer. And even having learned that lesson once, the second version still leaned on `event.char` — inspecting event internals for a decision that should be about *what the widget actually contains* was the recurring mistake across both the original bug and its first fix; only checking the text itself, directly, finally closed it for good.

### The paste that kept the formatting it was told to drop

*([0.37.56](../CHANGELOG.md#03756--2026-08-26) · 2026-08-26)*

**Symptom:** "paste without formatting" pasted a bullet list. Both choices did the same thing, which made it look like the wrong function was wired to the shortcut.

**Root cause:** nothing in the paste code. When you copy a list, the source puts it on the clipboard twice — once as HTML, once as its own plain-text version — and that plain-text version has real bullet characters in it. Everything worked exactly as written; the "plain text" simply was not plain.

**Why it hit this app in particular:** here a marker in the text *is* what makes a line a list. A bullet is not a property of the line, it is the two characters `"• "` at the start of it, because the character offsets in `formatting` have to index that same body text. So pasting the source's plain text verbatim did not merely show bullet characters — it built genuine, indented list paragraphs out of them.

**What pointed at it:** the same paste from a source that sends no bullets was already correct. That ruled out the paste path and left the clipboard.

**Fix:** plain paste strips what the app itself would read as a marker — the three bullet glyphs and a numbered prefix, with the indentation in front of them. A line starting `- ` keeps its characters, since those never made a list here anyway.

**The cost, accepted deliberately:** any number followed by a dot and a space starts a numbered item in this app, so `2026. was a year` loses its year. The stripper matches what the editor does with that line rather than being cleverer than it. A gentler rule would paste text that looked plain and came back as a list the next time the note was opened, which is worse than being consistent.

### The paragraphs a PDF does not have

*([0.38.59](../CHANGELOG.md#03859--2026-08-26) · 2026-08-26)*

**Symptom:** text copied from a PDF arrived either as one run-on block (**Ctrl+V**) or as narrow ragged lines a third of the way across the note (**Ctrl+Shift+V**). Numbering it then put a number on every line, including mid-sentence.

**Root cause:** a PDF has no paragraphs. It has lines placed on a page, and copying from one hands those line breaks over as though they were meant. Both behaviours followed from that honestly: the plain path kept every break, and the HTML path dropped them all, because HTML says a newline in text is whitespace — true for a web page, whose markup is laid out for a human to read, and false for a fragment carrying no block tag at all, which is what a PDF viewer offers.

**Fix:** keep those breaks when the fragment has no block structure, then rejoin the lines a column broke.

**Three heuristics, two of them wrong.** The first used width-relative thresholds — a line reaching 90% of the widest was "full" — and got 60-column text wrong in one direction and 110-column wrong in the other. The second asked the right question, *would the next line's first word have fitted here?*, which needs no threshold tuned to a width; but the column is never narrower than the longest line seen and usually a little wider, so a near-miss read as a deliberate ending and split paragraphs in half. The third added two characters of slack for that decision — and only for that decision, since allowing it when deciding whether the text is a column at all made three short paragraphs look like wrapped prose and merged them.

**And the signal that was missing from all three.** A paragraph almost never stops in the middle of a sentence. A line ending in no punctuation at all was broken by the column, whatever the arithmetic says — unless it falls well short of the column, which is a heading or a last line however it ends.

**Tested by property, not by result.** Which widths happen to come out exactly right is not the point and invites tuning the test until it passes, which this project has done once before and regretted. What is asserted instead, at eight widths, indented and not: no word is ever lost or altered, and no paragraph is ever split in two. Merging two paragraphs is possible — without indentation, a paragraph whose last line lands nearly full cannot be told from a line the column broke — and that limit is asserted rather than hidden, because losing a break is survivable and cutting a sentence in half is not.

**One check written during the fix passed without testing anything.** A three-line fixture meant to prove a heading keeps its own line was never recognised as a column in the first place, so it never reached the code it was guarding. Deleting that code changed nothing. It was found by deliberately breaking the code and noticing that nothing failed.

### The History row that re-dated the open note

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Since 0.71.111, clicking any row in the calendar's History register while a saved
note sat in the editor changed that note's date — a series' start date, a weekly series'
weekday, an undated note gained one — at the next note switch, New note, Back to Calendar or
close. Nothing on screen said so.

**Root cause:** The row's landing ended with the last lines of `_add_note_for_date` — the new
note's date prefill — left there when History was inserted next to it. Those lines wrote the
row's date into whatever note the editor held, and the next save stored it. A second tail of
the same kind turned up a round later: "Reset this day" ended with the lines "Make this
repeat…" was missing, so it announced "Set a repeat frequency" about a note that already
repeats and sent the keyboard to the hidden editor.

**Fix:** The stray lines are gone from the landing, and the reset's tail went back where it
belonged. A History landing only navigates now; a check opens each kind of note, clicks a row,
leaves, and compares the stored note field by field.

**Takeaway:** an insertion between two methods can leave the end of one inside the other, and
it runs on every call. Sweep for the shape — a function that does a second, unrelated job at
its very end — not only for the field the first report named.

### Ctrl+Z, and the formatting Tk's stack never held

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Making a word bold and pressing Ctrl+Z took back the last sentence typed instead,
and the autosave stored that. Undoing a table operation brought the cells back without their
bold and colours. And deleting styled text — Delete, BackSpace, typing over it, Cut — then
pressing Ctrl+Z brought the words back plain.

**Root cause:** Tk's undo stack records text, never a tag. A style change left nothing on it,
so Ctrl+Z reached past it; and text Tk puts back comes back bare.

**Fix:** A formatting journal beside Tk's stack notes the formatting before and after every
undo unit of the app's, and lays it back on the very text it was taken from — matched by the
text, never by counting steps, so the two stacks cannot drift. Tk's own deletes are no unit of
the app's, so a bindtag placed ahead of the body's bindings notes the formatting before one of
them reaches styled text; a run of BackSpaces stays one Ctrl+Z, as Tk merges it, and plain text
is left to Tk entirely. Measured before it was built: typing over a selection, Cut and Paste are
one Tk unit each, five BackSpaces are one, and a separator from the front tag splits them where
it is put.

The journal's first version paid for itself three ways on a long, styled note, all found by the
second wave of breakers: every unit made Tk lay out every line again (Ctrl+B went from 46 to
266 ms at 19,000 characters); each unit kept two snapshots of the whole note's formatting
(60 MB more after 100 cell edits); and Ctrl+Z of a style stripped every tag and laid every span
back (3.9–4.9 s at 8,000 words). A snapshot is now Tk's own ranges, one string per tag, read in
one Tcl call and shared with the step before when unchanged; actions that only restyle leave
Tk's grouping alone; and a restore touches only the ranges that differ. At 8,000 spans, Ctrl+B
takes 44 ms and its Ctrl+Z 51 ms.

**Takeaway:** when an undo system cannot see part of the state, keep that part beside it, keyed
to what the system does see — and measure how the system groups its steps before deciding where
yours begin and end.

### The key that typed nothing, and the line it forgot

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** A word's style spreads to the letters typed right after it — the field report was "the
new letters don't get the colour". An arrow key, or a Shift+Down stopping at a table under
"Prices:", turned the plain ":" after a bold word bold with nothing typed. Fixed once, the fix
broke the feature itself: letters typed after a bold or coloured word stayed plain on every line
but the note's last, and Delete, BackSpace, Ctrl+B, Ctrl+Z and Ctrl+Shift+V still spread the bold.

**Root cause:** The spreading ran on every key's release and read the two characters left of the
caret, so a key that typed nothing counted. The first fix asked "did the text grow?" by comparing
where the text *ended* before and after the key — an index, which an edit on any line above the
last never moves. And it noted the press in the body's generic `<KeyPress>`, which Tk never runs
for a key with a more specific binding of its own: those keys' releases found no press and fell
back to the old reading.

**Fix:** A key going down sets two marks at the caret, one staying put and one carried along by
whatever goes in there. What the key typed lands between them, after any selection it replaced;
a key that types nothing leaves them together. Every key is noted first by a bindtag ahead of the
body's own, so a key with its own binding — and Ctrl or Shift pressed before it, which reach the
generic binding as keys of their own — spreads nothing.

**Takeaway:** a fix that narrows *when* a feature acts must re-walk the feature's main path, not
only the reported case: the first fix's check was one line long. And ask the text what a key did
— a position that only looks like a size is not one.

### The bold the screen kept for later

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Select a word in a bigger heading — or anywhere in a note set to Georgia — and
press Ctrl+B. The toolbar's Bold lights up and the save stores the word bold, but on screen
nothing changes; opened again, the note shows it bold. Taking bold off fails the other way
round, and so do Bold turned on before typing and a bold paste. A letter typed onto a bold word
at a heading's end came out bold, small and saved small.

**Root cause:** Tk tags that set the same option do not compose, so a size or a font is drawn
by one composite tag with the weight and slant folded in, made after the plain bold and italic
tags so that it wins. Every route that changes bold or italic changed only the plain tag, which
the composite outranks; only opening the note, a renumber or a font change worked the
composites out again. The same lines held a second cost: those composites were worked out by
checking every styled word at every boundary, so one size in a note of 8,000 styled words cost
1.7 s at every open and every Enter in a numbered list.

**Fix:** Ctrl+B, Ctrl+I and a formatted paste lay every composite again from what the note
holds; typing refits only the letters typed, from the composite they wear or the one of the
word they were glued onto. The stretches are worked out in one sweep, checked against the old
way on thousands of random notes.

**Takeaway:** when one tag draws several properties, a change to any of them must reach that
tag. What the toolbar and the file say is not what the person sees: the screen shows the last
thing laid.

**Follow-up:** The next round found the first fix too broad and too narrow at once. It laid
every composite in the note again for one word's Ctrl+B — five times slower in a long note set
in a font — and a size picked before typing replaced the composite the letters had inherited,
taking the run's font with it. Ctrl+B now swaps only the composites inside the selection, and
typed letters keep the property that was not picked. The same round found bold italic pasted
from a web page drawn italic: the reader gave back bold and italic as two spans, two tags that
both set the font. They are folded into one at the choke point every span passes through.

The round after that found the same three rules each kept on one road only. Typed text at a
bold word's edge took the heading's size, while a paste, an emoji or the calculator's result at
the same place did not; a picked size kept the run's font in the run's middle, not at its
edges; the fold reached span lists, not two tags laid by typing or pasting. One more cost had
come in too: the refit went a character at a time, and a long paste paid for every one. Each
rule now lives in one helper that every road asks, and the refit goes by stretches of
unchanging tags. Fixing a mechanism on the road it was reported on, rather than on every road
that reaches it, is how the same finding came back three rounds running.

### The keys that took over from Tk and dropped its first step

*([0.95.391](../CHANGELOG.md#095391--2026-10-20) · 2026-10-20)*

**Symptom:** none reported; found while comparing the Android port's lists with the desktop's.
Select "and " in the item "• milk and eggs" and press Enter: the words stayed, with a new item
cut into the middle of them. In an open table cell, Enter did the same. Select back to just after
a bullet and press Backspace: the bullet went and the words stayed. Press Home, then Enter, on an
item: "• • milk". And making a sentence bold took the italic off its one italic word.

**Root cause:** the list's Enter and Backspace, and the cell's Enter, are handlers that take a key
over from Tk's own. Tk's first step for both keys is "if the caret is in a selection, delete the
selection", and none of the three handlers did it: they asked only where the caret stood. The
Enter handler also put its new marker at the caret without asking whether the caret was inside
the old one. Bold and italic had the matching flaw in another shape: one answer, read from the
whole selection, for a style that each part of it holds differently.

**Fix:** one helper asks Tk's own question (`_selection_holds_caret`, also now used by the three
places that had written it out by hand). Backspace steps aside when it is true; the list's Enter
deletes the selection and continues the list from there, as one Ctrl+Z, keeping the marker when
all of an item's words were selected; the cell's Enter deletes it first. Enter before a marker's
end starts from the marker's end, which leaves an empty item above. Bold and italic keep the
whole selection's on/off decision and give each stretch its own other style
(`_set_weight_by_stretch`), in the body and across table cells.

**Takeaway:** a handler that takes a key over from the toolkit takes over everything the
toolkit's binding did — read that binding first, and list its steps before writing the first line.

## Tables

*The drawn-grid feature earning its complexity, one investigation at a time.*

### The rebuild under the click

*([0.39.63](../CHANGELOG.md#03963--2026-08-28) · 2026-08-28)*

**Symptom:** After typing something wide into a cell, the next click on
another cell did nothing — and from then on the table misbehaved:
selections stopped working, a paste landed in the note as literal
`pasted text`, and the crash log filled with `bad window path name`.

**Root cause:** committing a cell whose content widened its column
rebuilds the whole drawn grid — tearing down the canvas and building a
fresh one. The click that *triggered* that commit was still in flight:
its release handler held references to the old, now-destroyed canvas,
and opening the editor on it raised mid-callback. The wreckage was
worse than the crash — the half-finished gesture left a dead selection
behind, so the next Ctrl+V found no cells selected and fell through to
the body's plain-text paste.

**Fix:** the same dance `_editor_step` already knew, applied everywhere
a gesture can cross a rebuild: anchor the table by its line number
*before* the commit, pick up the fresh grid *after*, and read canvas
coordinates while the canvas is certainly alive. Where the gesture
physically cannot continue (the mouse grab dies with the canvas), it
degrades loudly — the press becomes a click on the cell it started at,
on the fresh grid — never into a selection that flashes and silently
vanishes.

**Takeaway:** "rebuild the world on change" is a fine architecture, but
every pointer into the old world becomes a landmine the moment a
rebuild can happen *inside* a user gesture. The durable pattern is
re-anchoring by something that survives the rebuild (a line number, not
a widget), and the honest part is deciding out loud what the one
impossible case degrades into.

### The centring that would not save itself

*([0.39.63](../CHANGELOG.md#03963--2026-08-28) · 2026-08-28)*

**Symptom:** Centre a table on the page, switch to another note and
back — the table is flush left again. Press Save by hand first and it
stays. The autosave indicator never appeared.

**Root cause:** two bugs stacked, the second hiding under the first.
The autosave asks "did anything change?" by comparing the editor
against the saved note — title, body, character formatting, comments,
category, colour, checklist, date, recurrence… but not `paragraphs`,
the field where line alignment, list indentation and a table's place on
the page live. A change that touched only tags read as "nothing new".
Fixing that exposed the second bug: on load, the alignment tag covered
the line's newline, and the writable line the renderer keeps under
every table was born *inside* the tag — a phantom centred empty line
that made the note read as dirty forever, an autosave every half
second, and stray centred typing under the table.

**Fix:** `paragraphs` joined the dirty comparison, and on table rows
the loaded tag stops at the text instead of covering the newline. The
checks assert both directions: centring alone makes the note dirty, and
a reloaded note is clean with exactly the entries it was saved with.

**Takeaway:** a comparison that lists fields is a comparison that
silently exempts whatever field is added next — the autosave had been
skipping alignment-only edits since paragraph formatting shipped, and
nobody noticed until a feature made tag-only changes worth noticing.
And the first fix's perma-dirty loop is why "no stray saves when
nothing changed" became its own assertion: the opposite failure mode of
the bug being fixed is exactly where the fix's own bug will sit.

### The accepted cost that nobody had accepted

*([0.64.95](../CHANGELOG.md#06495--2026-09-02) · 2026-09-01)*

**Symptom:** colour a cell, drag a column edge to widen it, colour
gone — every character style in the whole table, gone. Dragging a
row's height quietly did the same to the one cell it padded.

**Root cause:** the wholesale block rewrite behind the structural
table operations says, in its own docstring, "character formatting
does not survive these ops — the accepted cost of reshaping." The
cost was accepted for operations that genuinely move text between
cells. Column WIDTH is not one of them: width lives in the separator
line's dashes, and not a single character of any data row changes —
yet the resize path went through the same rewrite and paid the full
price for nothing. The row-height drag was subtler: it edits cell
values properly, one at a time, but the cell writer replaced the whole
value, and a Tk delete takes every tag with it — so padding a styled
cell with empty trailing lines re-created its text bare.

**Fix:** the column-mechanics family (width, autofit, hide, unhide)
writes ONLY the separator line — replaced in place when it exists,
inserted under the header when it does not; every tag elsewhere stays
untouched because nothing else is touched. The cell writer now diffs
the old and new value and edits only the differing middle, so a pad
appends its markers after the styled text instead of rewriting through
it. The genuinely structural operations keep the wholesale rewrite and
its documented cost.

**Takeaway:** when a docstring says "accepted cost", check who is
paying it and for what. A cost accepted for reshaping was being
charged on a resize — the operation users do most, on the tables they
styled most carefully. The fix was not making the rewrite cleverer;
it was noticing which operations never needed it at all.

### The undo that stopped halfway

*([0.64.95](../CHANGELOG.md#06495--2026-09-02) · 2026-09-02)*

**Symptom:** found by an audit probe, not a field report — edit a
table cell from `1` to `changed`, press Ctrl+Z once, and the cell
reads neither: `|  | 2 |`. The old value gone, the padding collapsed,
and the drawn grid still showing the text from before the undo.

**Root cause:** three separate holes lined up. A cell commit is a
burst of small inserts and deletes (the value write, then the padding
shuffle on every row), and Tk's autoseparators made each its own undo
step — so one Ctrl+Z peeled back half an operation. Nothing after an
undo redrew the grids, so the canvas kept showing text the undo had
already changed underneath it. And the rebuild machinery was writing
its own edits into the same stack: probes against a live Text widget
showed `window_create` never records, but DELETING an embedded
window's character does — and undoing that delete re-inserts a
phantom character that shifts every index after it (the same
phantom-index family as "a/b became |a/be" above).

**Fix:** three layers, matched to the three holes. Every table
operation now runs as ONE undo unit (a decorator brackets it with
separators and holds autoseparators off, re-entrant for ops that call
ops). The grid teardown and redraw run with undo recording off —
verified first that Tk keeps the existing stack across that toggle.
And Ctrl+Z/Ctrl+Y on the body go through a handler that, after Tk
walks the stack, resyncs the tags and redraws the tables the restored
text describes. Mutants: the missing atom and the missing handler both
die by named checks; the recording-off layer's mutant survives the
suite because the other two layers repair every scenario the checks
can reach — kept anyway, on the strength of the probes, as layered
defence and said so here rather than dressed up as a pinned mechanism.

**Takeaway:** undo is a feature, and features cross. Every operation
that writes text in bursts owes the undo stack a boundary, everything
that redraws owes it silence, and the probe that settles what Tk
actually records costs one minute — cheaper than the theory it
replaces.

### The undo that stopped halfway, the sequel: lists and the grid trio

*([0.71.116](../CHANGELOG.md#071116--2026-09-09) · 2026-09-09)*

**Symptom:** found by the code audit — the same class as the story
above, in the corners it hadn't reached. Turn three lines into a
numbered list, press Ctrl+Z once: the note shows EMPTY. Press Enter in
a list sitting above a table: the table dissolves into raw `| pipe |`
rows. Toggle a table checkbox, Ctrl+Z: the toggle comes back half-done.

**Root cause:** the list operations renumber by rewriting the WHOLE
body — `delete("1.0","end-1c")` then reinsert — and that rewrite wasn't
bracketed as one undo unit, so a single Ctrl+Z undid the reinsert but
not the delete and the note was left empty. The same rewrite tore out
any drawn table's embedded windows and never redrew them. And three
structural grid ops — the checkbox `_grid_set_marker`, `_grid_append_cols`,
`_grid_append_rows` — were the only ones in their family missing the
`@_undo_atom` decorator every sibling carried.

**Fix, matched to each hole.** The whole-body rewrite in
`_renumber_lists` is now bracketed as one undo unit — placed *after* its
no-change early return, so a keystroke that doesn't renumber emits no
separator and normal typing undo is untouched, and re-entrant so a
wrapped list op stays one unit. When the rewritten body still holds a
table, it redraws the grids (skipped when there's none, keeping the
plain-list path keystroke-cheap). The three grid ops got the decorator
their siblings already had. The button ops (`_toggle_list`,
`_change_paragraph_indent`) are wrapped too, so their marker/indent
edits plus the renumber are one unit; the key handlers are deliberately
NOT wrapped (a decorator on every Backspace would split normal
delete-to-undo grouping — the renumber's own atom is what protects
their editing branches).

**A check that tested the wrong thing.** The first cut of the
table-survival check asserted `len(_table_grids) == 1`, and the mutant
that removed the redraw SURVIVED it: the whole-body delete tears the
embedded windows out of the widget but leaves a stale entry in the
`_table_grids` dict. The check now asserts on `body_text.window_names()`
— the real embedded windows — which is what "actually drawn" means.

**Takeaway:** when a fix has a sibling family (here `@_undo_atom`), the
audit is "which siblings were missed", not "does the reported one work".
And a check for "is it drawn" must read the widget's real embedded
windows, never a bookkeeping dict that a teardown can leave stale.

### The table that outlived its own deletion

*([0.71.125](../CHANGELOG.md#071125--2026-09-10) · 2026-09-10)*

**The report.** An adversarial review of the 0.71.125 grid fixes went
looking for other body-loaders that skipped the redraw tail — and found
something worse than a missing redraw. Open a note with a drawn table,
click New note, type two lines, click back into line 1: the next
keystroke threw the caret to the end of the note and the character
landed there.

**The mechanism.** "New note" clears the editor with a bare
`delete("1.0","end")`. That destroys the table's embedded window
characters — but the grid bookkeeping lives on: Tk *marks* survive a
full-range delete, collapsed to `1.0`. `_grid_first_line` read only the
mark, so the dead table answered "I start on line 1" in a note that had
no table at all. Every consumer believed it: the caret guard "escaped"
the phantom hidden rows by walking to the end, and line-1 column math
budgeted for a window character that wasn't there. The qa suite's own
`set_body` helper tears grids down before deleting — the tests knew a
bare delete was unsafe; the app's `new_note` didn't.

**Fix:** liveness at the root. `_grid_first_line` refuses to answer for
a grid whose frame no longer exists, which covers every route that can
destroy the windows without a teardown (typing over a Ctrl+A selection
takes the same path) instead of patching `new_note` alone.

**Takeaway:** a cached handle to a drawn thing must prove the drawing
still exists before answering questions about it. Tk's marks are
deliberately durable — they outlive the widgets they were planted for,
and durable state plus dead widgets is a haunting.

### The clipping that turned out to be a feature

*([0.71.134](../CHANGELOG.md#071134--2026-09-10) · 2026-09-10)*

**The report.** The audit flagged that a table pasted from ordinary
markdown drew its columns clipped: the conventional `---` separator's
dash count was honoured as the exact display width, and three dashes is
narrower than almost any content.

**The first fix, and the check that stopped it.** The obvious repair —
treat the separator width as a floor at render time, never a ceiling —
went in, and a pre-existing qa check went red: *"a too-narrow column
draws an ellipsis and keeps its text."* Clipping was not a bug. It was
the deliberate behaviour behind hand-narrowed columns: drag a column
edge left and the drawing clips to an ellipsis while the text
underneath stays whole. The same mechanism, a defect on one route and
a shipped feature on the other.

**The real fix.** The two routes differ at the *meaning* of the width,
so the fix moved to where meaning is read: `parse_separator` treats a
minimum-width cell (three characters or fewer — bare `---`, `:-:` and
friends) as markdown convention carrying no width opinion, while any
wider, hand-authored width stays exact. The adversarial review then
falsified the premise "authored is always wider" — the drag could
write width 2, which round-tripped through a three-dash cell straight
back into "no opinion" — so authored widths now floor at 4, the
narrowest that survives its own spelling.

**Takeaway:** before fixing behaviour that looks wrong, find who
relies on it — the qa suite is the census of deliberate behaviour, and
a red pre-existing check on a "fix" is it speaking up. And when one
byte pattern serves two meanings, disambiguate where it is parsed, not
where it is drawn.

### The table header Ctrl+Z gave back one column off

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Centring a table cell from the toolbar, inserting a row below or autofitting a
column, then pressing Ctrl+Z, gave the table's header back as `| Ite  | Qt  | Not  |`: every
cell of the first line one letter short, and the line no longer a match for its rows. Measured
on 0.82.233 in the Linux image: four of six table operations did it; inserting a column and
merging cells did not.

**Root cause:** A drawn table's first line holds the grid's embedded window at column 0, and
Tk's undo stack records every edit by its index. These operations take the grids down —
which deletes the window's character — edit the text, and draw the grids again. Their edits
were recorded with the window gone and replayed by Ctrl+Z with it drawn: one column off.

**Fix:** An undo unit now learns when the grids come down inside it, while Tk is still
recording, and the journal step it leaves is marked as recorded with the grids down; Ctrl+Z
takes the grids down before Tk replays such a step, and draws them again after it, as after
every step. A unit that had already edited the text with the grids up — a header cell still
being edited when the toolbar centred it — held both kinds of edit in one step, right in
neither state; it is split where the grids come down, so the first Ctrl+Z takes back the
centring and the second the word.

**Takeaway:** a stack that records positions replays correctly only in the state it recorded
in. When an operation changes what the positions count, the replay must restore that state
first — and one step must never hold edits from two states.

### The tidy that ate the redo

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** On a table pasted from Markdown, Ctrl+Z twice past a table operation, then Ctrl+Y,
brought nothing back: what had been undone was gone.

**Root cause:** A table is tidied — its columns padded — when the caret leaves it, at every key's
release, so it never shifts under someone typing. Undo moves the caret without the person moving
it. The release of the undo key found the caret "leaving" the table the undo had put it in, and
padded it: a new recorded edit, and a new edit empties every redo stack.

**Fix:** Undo and redo forget where the caret was last seen, so no release after them reads as
leaving a table.

**Takeaway:** a side effect keyed to "the caret moved" has to ask who moved it — the caret an undo
puts somewhere is not the person's.

### The selection the caret left behind

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Shift+Down on the line above a drawn table, then a letter: the letter appeared under
the table and the line stayed selected; a paste deleted the line and glued its text to the next
one; cells pasted from a spreadsheet went *into* the table. Shift+Up from under a table seemed to
select nothing — and the next letter typed deleted the whole table.

**Root cause:** The caret is never allowed on a drawn table's hidden pipe text: a guard walks it to
the line under the table. Tk's selection has two ends, and the guard moved only the caret. Shift+Down
had selected the line and the table's own line break, so the caret stood under the table while the
selection ended above it; typing lands at the caret and replaces a selection only when the caret
is in it. Shift+Up jumped over the whole table in one display line, selecting all its rows — a
grid shows no selection — and the guard put the caret back under the table, where it was the
selection's end: the next key replaced the table.

**Fix:** The guard keeps the caret with the selection's moving end. A first press stops at the
table's near edge — the line above without its break, or the line under the table — so no
selection takes a table in unasked; a second press at that edge crosses it, so the keyboard can
still select across a table. A mouse drag stops at the edge it came from. The spreadsheet paste,
for its own part, never deletes a table's line break with a selection.

**Takeaway:** a selection is two positions. Code that moves one of them on the person's behalf
must say what happens to the other — and an invisible selection is a trap whatever it holds.

### The paste that drew the row you were typing

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** Type a table's first row by hand — `| Item name | Qty |` — click back into it, and
paste a word. The word went in, but the row turned into a drawn table at once and the caret
jumped under it: the next letter typed landed on the line below. Typing the same word by hand
did not do it. Every paste route did — Ctrl+V, the menu's Paste, Ctrl+Shift+V, a paste from a
web page — and so did the release the app shipped before this branch.

**Root cause:** A table typed by hand stays text while the caret is on it, and is drawn when the
caret leaves; that is what lets you finish typing it. Typing never asks for a drawing. Every
paste route ends by drawing every table in the note, because a paste can bring a whole table
in — and the row being typed counts as a table (one pipe row is enough). Drawn, the row's text
is hidden behind a grid, and the caret guard, which never lets the caret rest on a drawn table,
moved it to the line below. The paste route already knew the row was being typed: it had
decided, a round earlier, that "a paste that stays on its line is a letter typed there" — but
only for tidying the row, not for drawing it.

**Fix:** The paste's tidy names the line of the table being typed that the caret is still on,
and every paste route hands that line to the drawing, which leaves that one table as text until
the caret leaves it.

**Takeaway:** the app's own redraw can undo what the person is doing. When a rule says "treat
this like typing", find every step that typing does not take — here, a redraw — and make it
follow the rule too.

**Follow-up:** Two more redraws nobody asked for did it as well: a theme switch and a new font
size drew any row being typed, pasted into or not, and the next letter went under the table.
They ask the same question now — is the caret on a row of a table not yet drawn? — and leave
that row as it is.

### A separator's dashes, read as a width nobody set

*([0.96.396](../CHANGELOG.md#096396--2026-10-24) · 2026-10-23 · seen in a photograph of the
Android app taken for its documentation; the desktop did the same)*

**Symptom:** a table's header drawn "How…" instead of "How much", its column barely wider than
"1500". The note had been written as GitHub's markdown writes a table with a right-aligned
column: `| What | How much |` over `| --- | ---: |`. Any table pasted as text — from a chat's
Copy button, a `.md` file, a page's code block — came in the same way whenever its separator had
a colon or more dashes than three.

**Root cause:** the app keeps a column's hand-set width in the separator itself, as its dash
count; `---:` is four characters, so it read as a column set by hand to four, and a set width is
drawn exactly, cut short with an ellipsis. A waiver from 0.71.134 already read three characters
or fewer as markdown's spelling rather than a width — but markdown's spelling of an aligned
column is four or five, and of a column as wide as its header, more. The two meanings share one
form, and in the file nothing says which one a separator is.

**Fix:** the decision is made where it is still known: at the paste. Text from outside the app has
every separator spelled at markdown's minimum on its way in — `---:` becomes `--:`, colons and `~`
kept (`tables.forget_widths`) — by every route a paste takes: `html_to_note` for a page's HTML,
and `_foreign_plain` for plain text, from rows on their own lines, a table in the middle of words
(which Tk used to paste itself, now made by the app in one undo unit), a table being typed,
Ctrl+Shift+V and a template's text. The app's own copy from a note keeps its dashes, which are
widths set here. Notes already saved are read as before: a reading rule changed would have
widened every column someone narrowed on purpose. The phone has the same fix, held to the
desktop's answers on 86 texts by its paste fixture.

**Takeaway:** when a format borrows another's syntax, the borrowed form arrives written the
way the other world writes it. Decide whose it is where that is still known — at the way in — and
leave what is already stored alone.

## Theming & performance

*Keeping a hand-themed UI consistent, and fast enough for weak machines.*

### The Trash panel that took two seconds to open

*([0.4.0](../CHANGELOG.md#040--performance-overhaul--test-infrastructure))*

**Symptom:** Opening the Trash (Settings → Recently deleted) with several hundred entries visibly paused the app.

**Root cause:** The panel built and individually wired up (including recursive mousewheel bindings) a full row of widgets for *every* entry, every time it opened — regardless of how many were actually visible in the scrollable area at once.

**Fix:** Paginated: render only an initial batch of entries (currently 25, via `TRASH_PAGE_SIZE`), with a "Show more" button to reveal further batches. Cut the time for 600 entries from ~1.8 seconds to roughly 100ms. The same pattern (build-everything-at-once, no cap) turned out to affect the multi-note Share panel too, and got the same fix pre-emptively before it caused a user-visible problem there.

### The slowdown that only showed up after a long session

*([0.4.0](../CHANGELOG.md#040--performance-overhaul--test-infrastructure))*

**Symptom:** No single action was slow. The app simply felt progressively heavier the longer a session went on — more saves, more note switches, more sluggish each one felt.

**Root cause:** A theme-tracking system (which lets a later dark/light switch recolor a widget correctly) was registering every widget in frequently-rebuilt UI — note cards, calendar cells, the attachments list — but nothing ever removed the registration for a widget once it was destroyed. Every single note-list refresh (which happens on nearly every save) added new entries to a list that only ever grew, for the entire lifetime of the app.

**Fix:** For content that's destroyed and rebuilt on every refresh, there's no need for live theme-tracking at all — it naturally picks up the current theme colors the next time it's rebuilt anyway (including on a theme switch, since that itself triggers a full rebuild). Switched all frequently-rebuilt UI to plain, untracked color-setting instead. Verified with a test that runs 30 successive refreshes and asserts the tracking-list size doesn't grow.

**Takeaway:** "Slow after a while, fine at first" is close to a defining symptom of an unbounded-growth leak. Reproducing it needs a test that repeats the suspected action many times in a loop, not just once.

### Export/import freezing the app

*([0.4.0](../CHANGELOG.md#040--performance-overhaul--test-infrastructure))*

**Symptom:** Exporting a backup with a meaningful number of attachments froze the entire UI — no feedback, just an unresponsive window — until the file finished writing.

**Root cause:** the file I/O ran on the Tk main thread — the same thread that services every click and repaint — so the event loop simply stopped until the write finished.

**Fix:** Moved the actual file I/O to a background thread, with a strict rule: the worker thread only does file I/O and updates a plain shared dictionary with progress; the main thread is the *only* thing that ever touches a Tkinter widget, reading that dictionary on a timer. Added a live progress bar so waiting is at least visible and bounded, rather than looking identical to a crash.

**Takeaway:** anything that takes real time comes off the main thread — and the worker never touches a widget. This incident is where the app's standing threading rule comes from.

### The theme-switch flicker, and three ways not to fix it

*([0.32.49](../CHANGELOG.md#03249--2026-08-20) · 2026-08-20)*

**Symptom:** Switching between dark and light showed a visible flicker — briefly, a half-recoloured page with dark bands across it. Colors always ended up correct; it was the transition itself that looked broken. It also got worse as more notes accumulated.

**The three attempts that failed, and why they were always going to.** All three tried to *hide* the flicker rather than ask what was producing it:

1. **`WM_SETREDRAW` (reverted).** Sent the Win32 "hold off repainting" message to the window before the update. No effect. The reason only became clear later: in Tk on Windows every widget is its own OS window, so suppressing repaints on the top-level does nothing about the hundreds of child windows that actually paint themselves.
2. **A full-window colour cover (reverted).** Covered the window with a plain `tk.Frame` during the rebuild. This made it *worse*: the UI shows several genuinely different background shades at once (sidebar, cards, main background), so one flat colour can't blend into any of them — the cover became its own visible flash on top of the original churn.
3. **A screenshot "freeze frame" (never shipped).** Grab the window with Pillow, show it as an image over the UI, recolour underneath, remove it. Measured *before* building it: 57–93ms of overhead, more than the entire switch it was meant to hide. Rejected on the measurement.

**What the measurements actually showed.** Profiling the switch (40 notes) instead of guessing: `refresh_note_list()` was ~85ms of ~121ms, at roughly 2ms per note card — and it is a destroy-then-repopulate, so the list visibly emptied and refilled. Statistics rebuilt itself too (no statistic changes when only the palette does), and the calendar rebuilt every day cell even while off screen. A probe using `after_idle` confirmed Tk's event loop never gets a turn mid-switch, so **Tk was not repainting partway through** — Windows was, because each widget's background flips the moment it's configured.

**The fix:** stop doing work that nothing asked for. Note cards are recoloured in place (`_recolor_note_cards`) instead of destroyed and rebuilt; statistics isn't touched; the calendar is deferred through the existing `_catch_up_deferred_refresh()` when it isn't visible. ~140ms → ~26ms, and it no longer degrades with note count (40→100 notes used to add 117ms, now 19ms). Verified by asserting the in-place result is identical, option for option, to what a real rebuild produces across four themes.

**A real bug fell out of verifying it.** That equivalence check caught a custom note colour being repainted with the new theme's accent — `_recolor_stragglers` can't tell a themed widget from a note the user deliberately coloured the same hex. It was confirmed present on `main`, i.e. pre-existing and unrelated to the new work. Fixed by running the card recolour *after* the straggler pass and recomputing each stripe from the note's own data, so the note's colour is authoritative.

**Takeaway:** three attempts were spent hiding a symptom before anyone measured where the time went; the measurement pointed straight at the fix and took less effort than any of them. When something looks like a rendering problem, profile before reaching for a rendering trick. Also worth remembering: an "additive" fix that only wraps existing behaviour can still make things worse (attempt 2), and reverting cleanly is a legitimate outcome rather than a failure. What remains is a genuine plain-Tkinter limit — one OS window per widget, each repainting as it is recoloured — not something further code can remove.

**2026-10-15, the same class again.** The owner noticed the switch flickering on a note with tables, and less on one without. `apply_theme()` rebuilt every drawn table, since their colours live in canvas items no tracked widget reaches. Each rebuilt table is a new window that appears a moment late. The fix is the cards' fix: `_recolor_table_grids()` repaints the grids in place, proven against what a rebuild draws. Measured with 30 tables: 103 ms down to 87, and no window is created. It does not make the switch perfect: in about a third of switches a table and the page beside it still disagree for 10–20 ms, the per-window repaint above, measured and recorded under [Known limitations](ROADMAP.md#known-limitations) with the two further ways tried.

### The list that was drawn whole, for every pause in typing

*([0.82.230](../CHANGELOG.md#082230--2026-09-30))*

**Symptom:** with a few hundred notes the app froze at every pause in typing — about a second
with 100 notes, three with 300, twelve with 1,000 — and switching back to the list from the
Calendar or from Settings took most of a second at 300 notes and over three at 1,000. The product review had it as T1-1, "the single most likely reason a month-in
user would stop"; deleting a note and Select all had already been taken off the full rebuild
(`0.74.169`, `0.75.173`), and the autosave was the one frequent route still paying for it.

**What the profile said, and what it did not.** One rebuild of 300 notes, under cProfile: about a
second destroying the old cards, a seventh of a second building the new ones in Python, and 2.7
seconds inside Tk laying them out and mapping them. Inside that last part were about two thousand
calls of the title bar's paint and four thousand of the calendar's width check (counted: 1,939
and 3,882 per rebuild) — handlers meant for the window,
bound with `self.bind`, which every widget in the window hears too, because each carries its
window's tag. Taking them off the storm took the counts to zero and the wall clock down by only
a few per cent: outside a profiler a Python call is cheap. The cost that scaled was the cards
themselves — six OS windows each — and the fact that all of them were made on every rebuild,
and all of them mapped again whenever the list came back on screen. No amount of trimming the
Python would have moved that.

**The fix, in four parts.**

1. **The window's own handlers hear only the window.** The title bar's paint lives on a bind tag
   only the main window carries (`_bind_window_only`); the Alt+Tab handler moved from `bind_all`
   to the two window classes. Tk delivers Activate to every widget in a window, so with 300
   notes it ran 2,132 times per switch — counted by delivering the event the way Tk does — only
   to return at its first line.
2. **The list draws what can be seen.** A rebuild draws thirty rows and the rest wait; the
   canvas's `yscrollcommand`, which hears every way the view can move, draws twenty more whenever
   less than a screen is left below the view, and the keyboard's ↓ draws ahead of itself. One
   definition of what the list shows (`_list_rows`) serves the rebuild, the top-up, the save
   and Select all.
3. **A save redraws its own card.** The rows are worked out again and compared with what is
   drawn; when the only difference is the saved note, its card is redrawn and packed where the
   sort puts it. Anything else still rebuilds.
4. **The notebook file is written in one piece.** `json.dump` streamed the same text through
   the file's encoder in thousands of small writes; one string and one write is twice as fast
   here (36 → 18 ms for 1,000 notes), and a test compares the bytes with the old way of writing
   them.

**Measured** with the code before the branch and after it run in alternating rounds on the
same machine, the same afternoon — medians, a mixed notebook of tables, checklists and
repeating notes:

| | 100 notes | 300 notes | 1,000 notes |
|---|---|---|---|
| A pause in typing (autosave) | 1.0 s → 74 ms | 3.2 s → 75 ms | 12.6 s → 90 ms |
| Starting the app | 2.3 → 1.9 s | 3.4 → 1.9 s | 8.6 → 1.9 s |
| Back to the list from the Calendar | 330 → 146 ms | 850 → 141 ms | 3.4 s → 142 ms |
| Closing Settings | 321 → 148 ms | 843 → 146 ms | 3.4 s → 150 ms |
| Switching the theme | 194 → 136 ms | 358 → 152 ms | 887 → 150 ms |

The cost of a card did not disappear; it moved to when the card is reached. Scrolling a
1,000-note list to its end drew the rest in steps of twenty, about a fifth of a second each,
9.4 seconds in all where it used to be nothing — and once everything was drawn, coming back to
the list cost 3.0 seconds against 3.3 before. That was still a widget list; the next paragraph
is what changed it.

**Three things that nearly slipped, each caught before it shipped.**

- **The storm had been doing a job.** The calendar's width check was on the window with
  `self.bind`, and the per-widget events were what noticed the window had been resized while
  the calendar was hidden: maximise on the Notes tab, come back, and the calendar switched to
  its larger text. Moved to the window alone, it stopped doing that — found by asking, before
  the move was finished, what the storm had been doing for the handler rather than only what it
  cost. It now listens to its own grid, which changes size in exactly those two cases.
- **A card that went to wait, with nothing to ask for it.** A new note landing just below the
  last drawn row joined the rows waiting — and the canvas reports only when something changes
  size, which nothing had. qa1's "the list calls it (untitled)" went red. A list drawn to its
  end now stays drawn to its end, and every update that leaves rows waiting asks for a top-up
  itself.
- **Made order is not screen order.** `winfo_children()` lists widgets in the order they were
  made, `pack_slaves()` in the order they are packed; they agreed only while every change was a
  full rebuild. The keyboard's walk and two checks comparing the list against a rebuild had to
  learn the difference the first time a saved card was made last and packed first.

**Then the field test, and the cards became a drawing.** Drawing on demand fixed what scaled
with the notebook, and left what scaled with the cards that were drawn. The first person to use
it said so in four ways: coming back to the list from the Calendar still showed it being built;
a fast drag of the scrollbar tore the list and repaired it; the first regroup after a while was
slow; and after scrolling through everything, coming back cost what it always had. Each was the
same fact — six OS windows per card — seen from a different side: mapping them, moving them,
destroying them. No arrangement of widgets gets under that, so the cards stopped being widgets.
They are rectangles and text on the list's one canvas (`_draw_note_card`), laid out in records,
found under the pointer by position, recoloured item by item. Photographed side by side with a
widget card first, to be sure it could look the same; it does.

On the drawing, at 300 notes: coming back to the list 74 ms whether one screenful or all 300 are
drawn (the widget list: 141 ms and 794 ms), a rebuild 20 ms (320), a save 21 ms (75), a scroll
to the end that draws all 300 in 0.09 s (2.4 s), a regroup of all 300 in 62 ms.

And against 0.81.213 at 1,000 notes, in a second alternating run: a save 14.1 s → 22 ms, a
rebuild 14.4 s → 9 ms, back to the list 3.7 s → 82 ms with one screenful drawn and 3.6 s → 81 ms
with all of it, closing Settings 3.7 s → 83 ms, starting the app 9.1 → 1.9 s, and a scroll to
the end that draws all 1,000 in 0.34 s. The old code's save took 12.6 s in the first run and
14.1 s in this one — the same code on the same machine, another afternoon — which is why a
number here is only ever compared with its own run.

Two things the drawing asked for that the widgets had done unasked. A drawing's `bbox` starts at
its first item, four pixels down, where a frame's started at 0 — so the top of the list read as
"scrolled four pixels", every rebuild kept its old depth, and a list scrolled to its end once was
drawn whole ever after. And the same field test found the keyboard stranded: a click opened a
note and left the keyboard wherever it had been, so Down "did nothing", and the walk itself had
never scrolled the list after the ring. A click puts the keyboard on the list now, and the list
follows its ring.

The first fix for the four pixels was an invisible rectangle from 0, placed one pixel in from
each edge because Tk counts a pixel round a rectangle into its `bbox`. Twenty checks green on
Windows; on the Linux image, qa1 and qa4 failed eight checks, every one about the list's top.
Asked of plain Tk in both places, the same rectangle at (1, 1, 249, 199) read (0, 0, 250, 200) on
Windows' Tk 8.6.15 and (1, 1, 249, 199) on the image's 8.6.16: the newer release stopped padding a
rectangle with no outline. So "the top" read as 1 there, and every guard believed the list was
scrolled. The rectangle is gone. The app knows where its rows end, and `_list_extent()` says so
to the scrollregion, the top-up and every guard, whatever Tk thinks a rectangle measures.

One measurement was a guess until a photograph caught it: the column the tick box takes in Select
mode was drawn 17 pixels wide, and the widget card's Checkbutton had been 22 — so on the
photograph the stripe and the text of every card in Select mode stood five pixels left of where
they had always been. Measured on the old code and drawn at 22. The comparison tool had called
that screen "changed" by 0.6% of its area; only looking at it said what had changed.

**The preview, in the same pass.** Opening an animated GIF decoded every frame before showing
the first: 1.3 seconds of nothing for a 60-frame animation, on every opening. The first frame is
shown at once now (35 ms) and the rest are decoded as the animation reaches them; a JPEG photo
is decoded straight at the size it will be shown; and a finished preview is remembered for the
next opening, up to a memory limit, and forgotten when the file changes. Decoding lazily keeps
the file open while it plays the first time round, and an open file is a lock on Windows — so
the file is closed at the last frame and whenever the preview goes away before it.

**Takeaway:** measure where the time goes before trimming what is easy to count — two thousand
callbacks were real and worth removing, and still not the cost; the cost was how many things
existed. Before removing work that looks wasted, ask what it was doing for someone. And a list
that stops drawing everything owes every reader of "what is on the list" an answer that does
not depend on what happens to be drawn.

### The window that crawled behind its edge

*([0.82.230](../CHANGELOG.md#082230--2026-09-30))*

**Symptom:** dragging the window's edge to make it wider or narrower moved in jerks, the
Calendar most of all — the edge fell behind the pointer and caught up in steps. Field-reported,
with the observation that Settings felt better, "maybe because half of it is empty".

**What was happening.** A drag of the edge sends the window a new size every few milliseconds,
and the app handed each one to its content at once: every widget placed and painted again.
Timed per step, dragging from 1,400 pixels wide to 900 and back: 275 ms with the Calendar
showing, 149 with a note in the editor, 70 on Settings — the field report's ranking, and for its
reason, since the cost follows the number of widgets on screen. Profiled, 98% of it was inside
Tk, so no Python was going to make a step cheap.

**The fix: take the step away until it counts.** While the mouse button holds the edge, the new
size waits. The window's frame follows the pointer, and the content is laid out once — when the
button is let go, or when the drag pauses for 120 ms. A resize with no button held (maximising,
a snap to the side of the screen, the keyboard) is laid out at once, as before. Tk hears the
sizes and nothing of the button making them, so the app asks Windows whether the primary button
is down — the physical right one, for someone who has swapped them; anywhere else, or if the
question fails, the answer is no, which is the old behaviour.

Timed the same way, a held step is 66–77 ms on the Calendar and 52–54 on the editor, and the one
layout at the end about a third of a second. The layout a settled drag leaves was compared with
the same size given at once: identical. Photographed mid-drag, the Calendar keeps its old width
— cut off at the right when the window shrinks, an empty strip when it grows — and at the
release it fits the window again.

What a held step still cost was Windows repainting what is on screen while the window changes
size. With the content hidden for the drag a step measured 13 ms — and the window would show
nothing until the button was let go. That trade went to the field test instead of being decided
here.

**The field test answered first.** Still heavy: the page "rebuilds slowly", and her screenshot
showed black strips where the window had grown faster than it was painted. So the 70 ms of a
step that lays nothing out was taken apart. Holding repaints off during the layout
(`WM_SETREDRAW`) made a live step slower, not faster — 299 ms against 258 — because nearly all
of it (246 ms) was the painting that follows the layout, not the layout. What Windows repaints
on a change of size is decided by the window CLASS: Tk registers `TkTopLevel` and `TkChild` with
`CS_HREDRAW | CS_VREDRAW`, which tell Windows to invalidate the whole window every time its size
changes. Taken off the child class alone, a held step went from 91 to 60 ms; off both, 9 ms.
Tk has no use for them — each of its widgets redraws itself when its own size changes — so the
styles only paid for the same paint twice. A live step fell with them: 264 → 128 ms on the
Calendar, 145 → 75 on the editor. Photographed before and after the change, mid-drag and at a
new size: the same to the pixel.

**One check that asked nothing.** The first version of "a pause in a held drag lays it out"
passed with the pause taken out of the code: its wait began before the window had changed
size, when the content's width and the window's still agreed, so it was over before it started.
It now sees the layout waiting first, then waits for the pause.

**Takeaway:** when the cost is inside the toolkit and paid per step, stop taking the step until
it counts — and then measure what the step costs when it does nothing, because that part is not
the work, it is overhead someone asked for. A smooth frame over a stale picture is a judgement,
not a measurement: say so, and hand it to someone who will look.

### The line that promised a place the card could not take

*([0.82.230](../CHANGELOG.md#082230--2026-09-30))*

**What was built.** The field test asked to move a note up or down the list with the mouse.
The list now has a sort arranged by hand, Custom order: a card is dragged, a line shows where it
will land, and letting go puts it there — or Alt+↑/↓ moves it from the keyboard. Two rules keep
a drop honest. A pinned note stands above the rest, and a grouped list sorts every card into its
category, so a card may only trade places with cards on its own side of both lines.

**Two checks that looked at the wrong moment.** The first versions checked where a card ended up.
Mutants that let a card cross the pinned line, or leave its group, survived them: the drop went
through, the list re-sorted the card back to its side, and the end state was exactly right. What
was wrong happened *during* the drag. The line had been drawn above the pinned card, or inside
the other group — a promise of a place the card could never take. The checks now ask where the
line said the card would go as well as where it went, and both mutants fail.

**One problem only the photograph showed.** The story that walks the feature on the real app
passed, and its picture of a drag in progress showed the line at the top of the list and no
card anywhere. The pointer had been carried past the list's top edge, the list had scrolled up
under it, and the card had followed the pointer out of the canvas. It now stays at the edge it
was carried to, in sight, while the list scrolls under it — and a check asks for that, with a
mutant that removes it.

**And one number that was guessed.** A drag near the edge scrolled the list one step every 40
milliseconds. Worked out rather than tried, that is over a minute to take a card from the bottom
of 300 notes to the top; the step now grows with how far past the edge the pointer is pushed.

**Takeaway:** when the screen re-sorts after an action, the state it settles into proves nothing
about what the screen promised during it — check the promise too. And look at the photograph:
the story's checks asked whether a line appeared, and none of them could see that the card it
belonged to had not.

### The month that was two hundred windows

*([0.82.232](../CHANGELOG.md#082232--2026-09-30))*

**Symptom:** after the window learned to wait while its edge is dragged, the field test found it
better but not right: on the Calendar the month stood still at its old width for the whole drag
— cut off, or beside an empty strip — then caught up in one jump when the hand stopped.

**What was happening.** The month was built the way the note list had been: a frame for every
day, a label for its number, one for each dot and each note title, a frame per divider. Counted
on a month holding 46 notes, 216 widgets, and each is a window the operating system makes, places
and paints. Laying them out cost 162 ms a step of the drag, which is why the window had to stop
laying them out at all; and the same cost was paid everywhere else the month was drawn — 295 ms
to move to the next month, 275 to open the Calendar tab after a change.

**The fix: the same move the list made.** The month is rectangles and text on one canvas now, laid
out from measurements of the widget grid it replaced — column edges, the weekday row, rows as tall
as the busiest day and never under 90, the paddings pack used — and a click, a right-click or the
pointer is matched to a day or a note's title by where it is. Photographed side by side with the
old grid, on a light and a dark theme and a six-week month, the two agree, but for the markers'
colour (below) and the open day's frame, two pixels from where it was. The numbers, measured
both ways in turn on the same machine: 25 ms to the next month, 33 to open the tab, and 38 a step
of the drag — little enough that the month is now drawn at every step and follows the edge. The
other pages are still built of widgets, so they keep waiting for the hand.

**Found by drawing it.** A drawing has to name every colour it uses, and the day's markers had
never named one: their label took the system default, black, on every theme, so on a dark day the
emoji all but disappeared. Nobody had asked for black — it was simply what a widget does when
nobody says. They take the day's own text colour now.

**One red that was not the app's.** Walking the travel story to prove this, chapter 3 went red on
a share code "still on screen" after a note switch — code nobody had touched, green minutes
before. The story's photograph showed the whole desktop, and on it the person at the machine,
busy in another program. The window's resize freeze asks Windows whether the mouse button is down
anywhere on the desktop: a click held elsewhere as the story's app started made it wait, as if
its own edge were being dragged; the note list was still unlaid, one pixel tall, never mapped;
the story's click on a card was dropped without a word; and the next step blamed the app.
Answering "held" for the app reproduced it, one run in two. The test harness already pinned the
one other thing the app asks the desktop — who owns the foreground — and now pins the button
too, for every script and story; and a story's click fails at the click when its note did not
open. See [qa/README](../qa/README.md#house-rules-for-new-checks).

**Takeaway:** when one screen's cost turns out to be its widgets, the other screens built the
same way are its siblings — the list's fix was a list of candidates, and the month was on it. A
colour a widget took by default is a colour nobody chose. And an input the app reads from the
desktop is an input the person at the machine is feeding every test run, until a test answers it.

### The Settings panels that stayed dark on a light theme

*(0.36.54 · 2026-08-25)*

**Symptom:** switching to a light theme left the information bars in Settings → General, Backup and About dark, with their text almost unreadable against it.

**Root cause:** `_recolor_stragglers()` fixes any widget still holding a colour from another theme by remapping that theme's palette entries onto the current one's. Settings does not use only palette entries: it *derives* two surfaces by blending — `card` toward `text` for the well inside a card, `card` toward `subtext` for its hairlines. Neither result is in any theme's palette, so the remap could not see them, and a panel built once under a dark theme kept the dark inset for the rest of the session. Measured: 19 widgets across those three panels.

**Fix:** the two derivations moved to `core/themes.py` as `inset_surface()` and `hairline()`, so Settings and the straggler pass share one definition, and the remap now includes each theme's derived surfaces alongside its palette. One change covers all 44 blended call sites rather than touching any of them.

**The rule worth keeping:** a colour that is computed rather than looked up is invisible to anything that works by matching known palette values. Derive it in one place, and teach the theme switch about it there.

### The title box that took three and a half seconds a keystroke

*(0.36.55 · 2026-08-25)*

**Symptom:** none, until someone pasted something long into a note's title. Then the title field stopped responding — and because the only way to fix a title is to edit it, there was no way back out.

**Root cause:** `tk.Entry` slows roughly with the square of what it holds. Measured on a bare widget with no bindings and no app around it: 0.5ms a keystroke at 30 characters, 38ms at 10,000, 892ms at 50,000, and 3,535ms at 100,000. Nothing in this codebase was involved.

**What it was *not*:** the question that prompted the measurement was whether a long title slows the app down. It does not. Twenty notes with million-character titles make a 19MB file that still loads in 50ms, the note list costs the same as with ordinary titles, and searching them takes 1ms. The app was never the problem; one widget was.

**Fix:** titles are capped at 200 characters — far past any real title, far short of where the widget struggles, and well above the 42 a card in the note list displays.

**Two things that needed care.** A validator can only accept or refuse a change *whole*, so pasting something longer left the field empty, which reads as the paste having failed rather than having been shortened; pasting now trims to fit. And validation fires on programmatic inserts as well as on typing — so without a guard, opening a note written before the cap would have had the widget silently drop the overflow, and the next autosave would have written that shortened title back over the real one. Loading a note must never edit it.

**Why the body is fine:** it is a `tk.Text`, which stays near-linear — a million characters costs 363ms a keystroke against `tk.Entry`'s three and a half seconds at a tenth of the size. Someone can write a book in one note; measured at 1M characters, typing is 14ms and saving 377ms.

### The colour the door let in and the drawing could not read

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** A calendar day coloured `#abc` — three hex digits, from a hand-edited or restored
settings.json — stopped its whole month from drawing: the days piled up in the corner and
nothing was clickable, on every visit.

**Root cause:** The day's text had just learned to contrast with its paint, and the contrast
reads six digits. The colour gate, `sanitize_color`, admits three on purpose, since Tk draws
both. The gate and its newest reader disagreed about what a colour is.

**Fix:** The gate gives `#rgb` back as `#rrggbb` — the same colour, in the only form the app
itself ever writes — so every reader that works a colour out by hand sees six digits. And the
contrast answers white for anything it cannot read, so no future door can freeze a month.

**Takeaway:** a gate defines what its readers may receive; a new reader must be able to read
everything the gate lets through, or the gate must narrow what it hands on.

### Every right-click left its menu behind

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** After a thousand right-clicks on notes, switching the theme took 420 ms instead of
80; each right-click left three windows and eighteen Tcl commands behind, each menu holding the
note it was built for.

**Root cause:** Every right-click built its menu anew and nothing ever destroyed one.

**Fix:** The previous menu is destroyed when the next is built. Not when `tk_popup` returns:
on Linux it returns at once with the menu still open (measured in the CI image: 1 ms, still
mapped), so the menu would vanish before anyone chose. The price is Tk's own: destroying a menu
with two cascades costs about 3 ms on Windows, with no app code involved.

**Takeaway:** a widget built per event needs an owner that ends it; and "destroy it when the
call returns" depends on whether the call blocks, which differs by platform.

### Save and Delete, the same khaki

*([0.89.365](../CHANGELOG.md#089365--2026-10-08) · found by a panel of AI reviewer personas and a colour-blindness simulation)*

**Symptom:** none reported, which was the point. The contrast gate had listed 71 pairs below
WCAG AA for weeks — every use of the accent, the warning red and the confirming green, Save's
white words on mint at 1.8:1 — each waiting on a design decision. An AI reviewer playing a
senior designer (one of five Claude subagent personas), looking at
the editor's row of three filled buttons, wrote: "colour no longer means anything".

**Root cause:** two, and only the first had been seen. Each role colour did two jobs, words on a
surface and a button under white words, and on a dark theme no single shade does both; the
white was written by hand in some forty places, so no palette alone could fix it. The second
came from simulating the two common colour-vision deficiencies (Machado 2009): Save's green and
Delete's red came out the same khaki in all eight themes, ΔE2000 8.6–12.7 where 10 and below
reads as one colour. They differed only in hue, and hue is exactly what about one man in twelve
does not see. Measuring every pair the app draws, not only the ones in the table, then found
three nobody had measured: the selected Settings section's name on its tint, a warning button's
words when pointed at, and find's current match, where the note's own text sat below 4.5:1 on the
full accent in every theme.

**Fix:** five proposals were photographed on the running app in all eight themes and chosen by
eye. Each role now has a fill and a text shade, and the words on a fill are never written down:
`letters_on` picks white or near-black by the gate's own measure. The warning fill is dark with
white words and the confirming fill light with dark words in every theme, so they differ in
lightness, not only in hue: ΔE2000 20.7 at the closest. The theme switch's straggler net picks a
fill's words by the fill they sit on, because a remap by value would have turned white words
into a dark theme's card. The gate measures 208 pairs now, mixed surfaces included, and qa1
walks every widget showing words on a fill, in every theme.

Shown the result, the same reviewers found the next layer: on the light themes the dark red
Delete was now the loudest thing in the window and Save the palest. The editor's Delete became
quiet, in red words (the note goes to the Trash), leaving Save the one filled button there; and
the tags line under each card's title, written in a colour the person picked, now takes a shade
of it that reads (`legible_on`) while the stripe keeps it whole.

A third look found a sentence wrong rather than a colour. The docs said the dark fill stayed
"where a deletion is final", and named the calendar's day and the selection bar — read in the
code, both call the same move to the Trash as the editor's Delete. A rule had been written down
from three examples nobody had traced. It is true now: the dark red fill marks a single
deletion that cannot be undone (a Trash row's Delete, an attachment's ✕), and the moves to the
Trash wear the warning's words, the Duplicates clean-up outlined so it still reads as a button.
The fix was written with "every" in it, and a fourth look found the word untrue twice: Empty
trash (final, outlined on purpose) and the Duplicates panel's main action (a move to the Trash,
in the accent). Both are deliberate, so the sentence now names them instead of the code
bending to the word.

**Takeaway:** a gate measures the pairs it was told about; walk what is on the screen instead.
And two colours that differ only in hue are one colour to a reader who cannot see hue — make the
destructive one the dark one. A rule stated in the docs is a claim about every instance: trace
each one to the function it calls before writing it down.

### Two answers to one question

*([0.89.371](../CHANGELOG.md#089371--2026-10-08) · found by AI reviewers reading colour-blindness simulations)*

**Symptom:** none reported. Photographs of the running app were simulated for protanopia,
deuteranopia and tritanopia (Machado 2009, full severity) and given to three AI reviewers
(Claude subagents) who saw only those, with a fourth seeing the originals as the control. A
model reading a simulation is an approximation, not a colour-blind person; the test plan's case
625 asks a real one. *(2026-10-14: no real reader has looked yet. Case 625 now records this
simulated check, and a real reader waits for the feedback after the public launch.)* None was
blocked. All four hesitated over the find bar's current match,
and two over which tab was open.

**Root cause:** three, none of them a colour. The current match differed from the others by its
fill alone — the match inside a table cell was already boxed. The open tab was drawn smaller
than the closed one: the base theme, clam, maps its own padding for a selected tab, and a state
map beats a configured value, so the app's padding applied to every tab but the open one. And
the letters for a colour the person picks had a formula of their own. `contrasting_fg` used a
brightness threshold; `letters_on`, written the same morning for the palette, used the measured
contrast — and its docstring said the two answered "a different question". Measured on the 20
colours a day can be painted, they disagreed on 9, the old one putting white at 2.2:1 on the
light blue. They answered the same question; one answered it worse. The colour picker's tick,
the only sign of the colour in use when two swatches look alike, was a literal white beside
both.

**Fix:** the current match is boxed (a `solid` relief, which Tk draws dark on any fill). The
selected tab's padding is restated in the app's own `style.map`, 4px taller than the others,
so the open tab is the raised one. `contrasting_fg` is `letters_on` by name, and the tick takes
the same letters. The checks read the promise rather than the option: where each tab begins on
screen, the tick on all 20 colours at 4.1:1 or better, every pickable colour given the letters
that read on it.

**Takeaway:** two helpers answering one question disagree somewhere — measure them against each
other before writing that they differ. And a base theme's state map overrides the value you
configured, silently: list what it maps for every option you set.

## Coordinate systems & units

*Two rulers measuring the same thing differently — pixels, characters, UTF-16 units, monitors.*

### The dropdown that opened on the wrong monitor

*([0.2.0](../CHANGELOG.md#020--inline-ui-overhaul--data-resilience))*

**Symptom:** On a multi-monitor setup, dropdowns (category picker, sort menu) could pop up on a completely different screen than the app itself.

**Root cause:** Popup positioning was calculated against `winfo_screenwidth()`/`winfo_screenheight()` — the *full virtual desktop* across all monitors — instead of the app's own window bounds. On a wide multi-monitor span, that math could place a popup well outside the monitor the app was actually on.

**Fix:** Rewrote the shared popup-positioning helper to measure against the app window's own `winfo_rootx()`/`winfo_width()` instead, with live tracking so the popup follows if the window is moved or resized while open. Every popup in the app now goes through this one shared function — no positioning logic is reinvented per popup.

**Takeaway:** the full virtual desktop is not the screen the user is looking at — position against the window they can see, and keep that arithmetic in one shared helper so no popup can get it wrong on its own.

### The emoji that multiplied into squares

*([0.39.63](../CHANGELOG.md#03963--2026-08-28) · 2026-08-28)*

**Symptom:** Typing two emoji into a table cell showed one emoji and a
square. Hovering made more squares. Committing the cell wrote diamonds
and fragments into neighbouring cells, and eventually a save crashed the
app outright.

**Root cause:** Two facts about Tk, stacked. First, a Tk text widget
addresses columns in UTF-16 units, while Python counts characters — an
emoji beyond the basic plane is *two* Tk units but *one* Python
character. Every surgical edit the grid made (write this cell, pad that
column) computed offsets in Python characters and applied them as Tk
columns, so after one emoji every later cut landed one unit early —
slicing the second emoji in half, and re-slicing at the drifted position
on every flush, which is how one emoji became a trail of broken pairs.
Second, a Tk Entry hands back exactly what it holds — including a
*severed half* of an emoji (a lone surrogate), which is a valid Python
string that `json.dump` refuses to serialise. The save failed with the
temp file already open, and the old `except (IOError, OSError)` did not
catch a `UnicodeEncodeError`, so the failure escaped as a crash.

**Fix:** every boundary between Python offsets and Tk columns goes
through a pair of converters (`_tk_units`/`_tk_col`), and the storage
layer mends surrogate pairs (`mend_surrogates`) before serialising —
plus the save's `except` was widened and its temp file is removed on
failure. The regression checks type two emoji through three flushes and
assert two come out.

**Takeaway:** an off-by-one that only appears after an emoji is not an
emoji bug — it is a units bug, and it was everywhere the two counting
systems met. Fixing the visible site (the cell write) without the
audit would have left the same drift in the alignment ops and the
column inserts. The mutation test that made `_tk_col` an identity
function reproduced the user's exact "two in, one out" report, which is
what confirmed the mechanism rather than the symptom had been fixed.

*Sister story: ["The version that updated itself"](#the-version-that-updated-itself) — the same UTF-16-vs-characters unit mismatch, surfacing as silent span drift instead of squares.*

### The backspace that ate half an emoji

*([0.66.105](../CHANGELOG.md#066105--2026-09-07) · 2026-09-07)*

**Symptom:** Field-reported, with the whole life cycle observed: an
emoji in a note's title, one press of Backspace, and the emoji became a
box; saved and reopened, the box became **three** question marks.

**Root cause:** the third member of the UTF-16-units family (see the two
sister stories above). Tk's Entry widget stores text in UTF-16 units and
its stock Backspace and Delete remove exactly one — half an astral
emoji. Internally the emoji is six CESU-8 bytes; deleting one unit
leaves three bytes no decoder can read, which the Tk→Python bridge hands
over as three escape characters (the box), and the save's surrogate mend
then faithfully converts each into a replacement character — the three
question marks, one per orphaned byte. The note body never had the
problem: a Text widget deletes whole characters on its own. Only the
Entry family tears.

**Fix:** a shared pair of handlers walks the entry's text in UTF-16
units (the `_tk_units` arithmetic the emoji picker already learned) and,
when the character beside the caret is astral, deletes both units;
everywhere else they stand down and stock behavior is untouched. Bound
on all nine free-text entries — title, both search boxes, checklist
items (editor and template), category and template names, the
username — not just the reported one. Mutation-tested: unbinding the
title's guard fails the Backspace and Delete checks while the search
box's own binding stays green.

**Takeaway:** when a widget family shares a defect, the report names one
member but the fix belongs to the family — and this family (UTF-16
units vs. characters) has now bitten three times in three costumes:
caret drift, span drift, and torn deletion. Any new code that indexes
into a Tk Entry should reach for `_tk_units` first.

### The copy that took the row above

*([0.39.63](../CHANGELOG.md#03963--2026-08-28) · 2026-08-28)*

**Symptom:** Copying two cells and pasting them somewhere else put the
wrong text in the target — sometimes an empty pair, sometimes a word
from a different row, once a pair of literal `---` dashes. It looked
random, and it haunted three field-test sessions under three different
descriptions.

**Root cause:** any table that has ever been resized carries an
invisible mechanics row — the Markdown separator `|---|---|` — as its
second line of *text*, which the drawn grid deliberately does not show.
The copy's selection matrix indexed rows by grid position into the raw
*text* rows, so in every such table the copy read one row above the one
on screen. The user copied what they saw; the clipboard got the line
above it.

**Fix:** the selection matrix reads data rows through the same
separator-aware mapping every other grid operation already used. The
regression check pins the exact haunting: with a separator present,
Ctrl+C must produce the row on screen — and the mutation that
resurrects the bug fails it with the clipboard reading `---	---`,
the ghost made visible.

**Takeaway:** when the same feature breaks three field tests in three
different costumes, stop patching the costumes. The reports ("pastes
the wrong thing", "fills a random cell", "only the first cell landed")
shared one cause, and it was found by following the data — what exactly
was on the clipboard — rather than the behaviour.

### The version that updated itself

*([0.55.81](../CHANGELOG.md#05581--2026-08-30) · 2026-08-29)*

**Symptom:** a green "Note updated" toast on every single launch, with
nothing edited — reported as a cosmetic annoyance. It was not cosmetic:
the notes file was rewritten on every start, and one note's formatting
span crept one character further from its text with each launch
(measured live: 1176 → 1177 → 1178 across three starts).

**Root cause:** two coordinate systems, both called "characters".
Applying a span uses Tk's `+Nc` index arithmetic, which counts an emoji
as ONE character — the same as Python's string offsets, which is what
the note stores. Extracting spans back used `count("chars")`, which
counts UTF-16 units — an emoji is TWO. Any formatted note holding an
emoji before a span therefore read back one further right per emoji:
"changed" the moment it loaded, so the startup autosave re-saved it,
storing the shifted span, which shifted again next launch. The same
phantom difference had earlier powered a "you have unsaved notes"
question at quit that autosave should have made impossible.

**Fix:** one method — `_char_offset` now measures `len(get("1.0",
index))`, the exact space the saved body string lives in (it also skips
embedded window characters, which the drawn tables add). Verified on a
copy of the real notebook: two consecutive launches, zero toasts, file
untouched, all 36 notes reading clean at load.

**Takeaway:** when the same word ("characters") names two different
units, every conversion site is a latent off-by-N. The bug also hid
behind its own symptom: the toast looked like noise, and only tracing
*why* the file was being rewritten exposed the data damage underneath.

*Sister story: ["The emoji that multiplied into squares"](#the-emoji-that-multiplied-into-squares) — the same unit mismatch, caught the first time it showed.*

### The search that killed the interpreter

*([0.71.125](../CHANGELOG.md#071125--2026-09-10) · 2026-09-10)*

**Symptom:** the Linux CI leg died with `Segmentation fault (core
dumped)` — no traceback, no FAILURES footer — right after a PASS line
sitting in the middle of qa1's tables section.

**Two mechanisms, stacked.** The PASS line was a lie of buffering, not
a location: piped stdout is block-buffered on Linux, and a segfault
throws away everything still in the buffer, so the log's last visible
line pointed ~200 checks before the real crash site. Re-run on the
Docker CI mirror with `PYTHONUNBUFFERED=1`, the true site surfaced: the
new find-across-emoji check. A bare-Text probe then isolated the crash
to one call — `text.search()` with `-nocase` and an astral character in
the pattern kills this Tcl/Tk outright. The same search without
`-nocase` is fine; so is the same emoji in the *text* being searched.

**Fix:** the app never hands Tcl an astral needle. `_find_scan_model`
pre-screens the query; anything holding a non-BMP character scans the
prose in Python (case folded there, offsets converted with `_tk_col`,
the same hide-tag skip dropping elided table text). The mutant routing
astral queries back through Tcl reproduces the exact CI crash
signature — the one mutant in this log whose "failure" is a dead
interpreter rather than a red check.

**Takeaway:** a native-code boundary can fail harder than any exception
— budget for "the process just dies" when a check feeds user input to
Tcl. And never bisect a crash from a piped log's tail: trust exit codes
and the footer, re-run unbuffered for the location.

### The width that was guessed

*([0.73.167](../CHANGELOG.md#073167--2026-09-15) · 2026-09-15)*

**Symptom:** In Settings, the explanatory line under each title stopped
mid-word. Duplicates ended at "date and col"; Templates at "use Save as
template on an"; Backup at "not in the a folder". Nothing on screen said
anything had been cut, and the missing words were the ones carrying the
meaning — "date and col" should read "date and color). Tick the copies
you want to remove — the rest are kept."

**Cause:** A `tk.Label` breaks its text at `wraplength` pixels and then
draws those lines inside whatever width the geometry manager gave it.
When the two disagree, the ends of the lines are simply not drawn.

Every wrapping width in that page was `SETTINGS_CONTENT_MAX` minus a
hand-picked number — a guess at the padding between the pane and the
label. The panel alone is packed with `padx=48` a side, so every guess
was short by at least 96 pixels before anything else was counted: the
section subtitle asked for 620 and was given 544.

Three labels were clipped, by 51, 57 and up to 69 pixels. A fourth had
the same construction and survived only because its text was short
enough not to wrap.

**Fix:** the numbers are gone rather than corrected. `_wrap_to_own_width`
binds `<Configure>` and sets the wraplength from the label's own width,
less four pixels for the border Tk adds when it asks for room. The only
number that cannot disagree with the layout is the one the layout
produced. Applied to all four labels, including the one still fitting.

Only for labels a parent stretches. A label that sizes itself to its text
would shrink, re-wrap, and shrink again.

**How it was found, and the two wrong measurements:** it was found by
*photographing* the app for the documentation gallery — no check had ever
compared a wraplength with a width, and reading the code would not have
shown it either, because both numbers look reasonable on their own.

Locating it took three measurements, and the first two were wrong in
instructive ways.

*"wraplength larger than the label's width"* flags every label that sizes
itself to its text — those are always narrower than their wraplength and
are never clipped. It reported six problems, two imaginary.

*"does the label reach past the pane"* reported none at all. The widget
fits; it is the text inside it that does not.

*`winfo_reqwidth()` against `winfo_width()`* — what Tk asked for, given
the text and the wrapping, against what it was given — matched the
photographs exactly, down to which three sentences were cut and by how
much.

**Takeaway:** a layout number that has to agree with a layout it cannot
see is wrong the first time either changes, and stays wrong silently. Ask
the widget. And when a measurement disagrees with a photograph, the
measurement is the thing to doubt first.

### The rebuild nobody was looking at

*([0.74.169](../CHANGELOG.md#074169--2026-09-15) · 2026-09-15)*

**Symptom:** field-reported in four words — "the picture breaks a little
and rebuilds itself when I delete a note and the Undo button appears".

**First finding: it was not the Undo.** The banner had just shipped and
was the obvious suspect, so it was measured rather than blamed. A delete
cost 185ms and rebuilt 264 widgets *with the banner removed from the code
entirely*; the banner itself cost 7ms and built nothing. What the new
feature had done was hold her eyes on that part of the screen for eight
seconds instead of one and a half. The flicker had always been there.

**Cause:** three rebuilds, of which two were invisible.

| Piece | Cost | Widgets | On screen? |
|---|---|---|---|
| `refresh_note_list()` | 129ms | 169 | yes |
| `render_calendar()` | 36ms | 98 | no — the Notes tab was showing |
| `_render_statistics()` | 12ms | 49 | no — Settings was closed |

One mechanism in three places: work done unconditionally on a data
change, for a surface nobody was looking at. And the app already knew
better — `apply_theme` had skipped the calendar since the theme-switch
flicker work, with the reasoning written beside it. That test lived at
one call site out of thirty-one.

**Fix:** the test moved *inside* `render_calendar()`, so every caller is
right by construction rather than by having remembered. The statistics
panel gained the same gate. And deleting a note stopped rebuilding the
list at all: `_remove_note_cards()` takes the one card off and leaves the
rest untouched — the fourth member of a family the list already had
(`_recolor_note_cards`, `_apply_selection_mode_to_cards`,
`_update_open_highlight`), each written because a full rebuild "visibly
flickered the whole list" for a change that touched a few cards.

185ms and 264 widgets became 31ms and 3.

Every uncertain case still hands over to the full rebuild — an emptied
list (whose message depends on whether anything is filtered), a header
that would not update, a card that is not where the registry says. A list
that quietly disagrees with the notes is far worse than one that
flickers.

**The gap that listing the routes found.** Deferring a rebuild is only
safe if something catches it up before the screen can be seen again.
There are exactly four ways back to the calendar, and the fourth had no
catch-up: leaving Settings re-packs the notebook with the *same tab still
selected*, so no tab-change event ever fires — and Settings is exactly
where notes are restored, purged and recategorised. Found by enumerating
the routes, not by testing.

**And the trap inside that fix.** The first attempt called the catch-up
from `hide_settings_page()`, which asked `_calendar_is_showing()`, which
read `winfo_ismapped()` — and `pack()` does not settle that until Tk next
goes idle. It answered "not showing", deferred again, and left exactly
the staleness it was added to prevent. `after_idle` did not escape it
either: measured, the callback still ran with the notebook reading as
hidden. The fix was to stop asking an unreliable question: an explicit
flag, set by the two methods that own the swap — the same lesson
`_calendar_is_showing()` had already learned for the *tab* half of the
question and not for the other.

**Takeaway:** when a feature makes a user look somewhere new, expect a
report about something that was always wrong there. Measure before
believing the newest change caused it. And a guard that exists at one
call site out of thirty-one is not a guard — it is a comment.

### The sentence that counted notes

*([0.74.170](../CHANGELOG.md#074170--2026-09-15) · 2026-09-15)*

**Symptom, field-reported:** "I selected two notes to delete — one was an
ordinary note, the second was a series. It didn't ask me about the
series the way it does when I delete one on its own."

**Cause:** a confirmation that counts notes is telling the truth and
hiding the consequence. A repeating series is ONE note in every list and
every count, and deleting it takes every occurrence it has. The
single-note delete has asked "Delete this entire repeating series?" since
the feature shipped. Nothing that acts on a SELECTION asked anything.

Walking the siblings rather than the report found the same silence three
more times, and the worst two are past the point of no return:

| Place | Said it was a series? | Consequence |
|---|---|---|
| Note list card | yes — 🔁 on the title and in the tags | — |
| Calendar day panel | yes — 🔁 | — |
| Single delete confirm | yes | recoverable |
| Bulk move to trash | **no** | recoverable |
| Trash row | **no** | — |
| Delete permanently | **no** | **irreversible** |
| Empty trash | **no** | **irreversible** |

`settings_page.py` did not import `is_recurring` at all. In the one list
in the app where deleting cannot be undone, a whole series looked exactly
like a note about milk.

**Fix:** the sentence is written once, in `_series_warning()`, and used by
all three confirmations; the Trash marks a series the way every other
list does. Four copies of a sentence is four chances for them to stop
agreeing.

**What the check found that the fix had not.** The interaction pass
listed "a trash entry whose recurrence is corrupt" as a risky row, so a
check was written for it — and it went red. `is_recurring` read
``(note.get("recurrence") or {}).get("freq")``: safe for a note that has
been through `normalize_note`, fatal for one that has not, because a
string in that field is truthy and `.get` on a string raises. Live notes
are normalised on load. **Trash entries are not** — `load_trash()`
returns whatever the file held. So the first caller ever to ask a trashed
note whether it repeats would have taken the whole Trash panel down with
it, on a file a hand-edit or an older format could easily produce. The
type check now lives in `is_recurring`, at the choke point.

**And the fix's own bruise.** Giving a trash row its "repeats ..." line
made the Restore and Delete buttons cramped — reported within the hour.
The packer hands out the cavity in pack order, and the expanding text
frame was packed first, so the buttons lived on the remainder. They are
packed first now. A row can afford a shortened title; it cannot afford an
unclickable Restore.

**Takeaway:** when a dialog counts things, ask what one of those things
can be. And a guard that has only ever been asked well-formed questions
has not been tested — it has been lucky.

### Two ways to be invisible

*([0.75.173](../CHANGELOG.md#075173--2026-09-15) · 2026-09-15)*

Two reports, one strip of sidebar, and two different ways for a thing to be on screen and not be
seen.

**The word against the edge.** "Export is very cramped, you can barely see the whole word." The
bar laid five controls in one line across a sidebar of fixed width. The packer hands out that
width in order: each control takes what it asks for, and the *last* one lives on the remainder.
So everything before it draws perfectly, and the failure lands entirely on whoever is last -
which is why nothing looks wrong until the end of the row.

- Measured: Export asked for 40px and was drawn at 27px. Everything else got exactly what it
  asked for.
- The comment being replaced had recorded the same fight, won by one pixel: *"four controls need
  281px and the sidebar is a fixed 280 - the emoji alone is the overflow."*
- On the Linux CI image, where the font is wider, the same four controls asked for 338px of the
  250 available, and Export was drawn at one pixel. It had been that broken there the whole time.

A layout that fits by one pixel is one font away from not fitting.

So the fix isn't a smaller font, which would just move the margin. The count moved to its own
line, and the four actions went two by two - which changes what has to be true: the widest row
now needs the two widest labels side by side (180px on Linux, 105 on Windows) instead of all
four. Room to spare on both.

**The tick that was the same colour as its box.** "The tick boxes are almost invisible in dark
mode, being black. Maybe we can lighten the squares, so the black tick shows better in them."
She was right - but the first attempt at fixing it was wrong, in a way worth writing down.

- The photograph taken to study it showed every box empty, because the script had called
  `_toggle_note_selected` (which updates the set of selected ids) rather than invoking the
  widget (which is what actually moves a checkbox). The fixture ticked nothing.
- On that empty picture, a whole diagnosis got built: pixel measurements, a table of candidate
  colours, a conclusion of "use the accent", and a change to twelve call sites.
- Ticking the boxes properly showed the accent making an *empty* box look filled - worse than
  before. The change was reverted whole, and she was asked for a screenshot of her own machine
  instead. Hers showed what the report had said all along: a ticked box, dark, with a dark mark
  in it, barely distinguishable from an empty one.

The mechanism, once the picture was honest: `selectcolor` is the well a check mark sits in, and
every one of them in this app was set to `card` or `sidebar` - the very surface the box is drawn
on. Tk draws the mark dark on Windows whatever the palette says, so a dark well hides a dark
mark. Light themes never showed it, because their card is already white - that's what kept it
alive.

It's a named palette entry now, `check_well`, light in all eight themes, so a future theme
disagrees in one place instead of twelve.

**Takeaway:** A layout whose last element absorbs every shortfall reports nothing and fails last
- measure what it *asks* against what it is *given*, on every font it will meet. And a fixture
that doesn't do what its name says turns a measurement into a rumour: the tick boxes cost a full
wrong diagnosis, and the only reason it shipped nothing was a screenshot asked for before the
commit.
### The rule the app already had

*([0.75.176](../CHANGELOG.md#075176--2026-09-25) · 2026-09-25)*

**Symptom, field-reported:** "the delete button only shows up when I go
through History; if I click a date there's no delete button, only
right-click — and the History path has no right-click. Let's keep a
single delete system."

**The report was right about what she saw and wrong about what it was.**
The thing reachable by right-click is not a delete system: it is the
note's actions menu, and it carries Open/Edit, Pin, Export as file,
Duplicate, and — for a repeating note on a given day — edit only this
occurrence, edit the whole series, and reset this day to the series
content. Picking "one of the two systems" by deleting that one would
have cost six actions to gain consistency.

**What was actually wrong** is that the app already had a rule, applied
everywhere except here:

| Surface | Right-click menu | Labelled Delete |
|---|---|---|
| Sidebar note card (*a list*) | yes | no |
| Editor (*one note open*) | — | yes |
| Calendar day list | yes | **also a bare 🗑 per row** |
| Calendar note preview | **none** | yes |

So the calendar broke it in both directions at once. Its day list held
the only per-row note delete in the app — a grey glyph with no word,
packed hard against the scrollbar, which is a destructive action sitting
exactly where a click is most likely to slip. And its preview was the
only note surface in the app that ignored a right-click, so arriving
there from History meant arriving somewhere with fewer actions than the
list you could have reached the same note from.

**Fix:** the glyph is gone and the preview answers to right-click, with
the occurrence date passed through — which is the point of passing it:
the panel is opened ON a day, so its menu must offer to edit THAT day
rather than silently acting on the series behind it.

**Takeaway:** when two screens disagree, do not pick one. Ask what the
REST of the app does, and make the odd one out match it — the answer is
usually already written somewhere in the code, and it is better than
either of the two you were choosing between. And read what a gesture
actually offers before calling it "the delete system": the menu that
looked like a duplicate way to delete was the only way to reach a third
of the note's actions.

### The list that moved under the pointer

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** With unsaved typing in one note, double-clicking another note's card opened its
neighbour; a click with a tiny slip could drop the card into a new place and switch the list to
Custom order.

**Root cause:** The click's own open saved the note left behind, and the save moved rows under a
pointer that had not moved. The double-click's second press, and the drag the first press had
armed, then acted on whatever had slid under it. The drag threshold was even measured in the
canvas, so a view moving under a still hand counted as the hand travelling.

**Fix:** A press keeps its row where it stood on screen, scrolling as far as the list can;
where it cannot, the press leaves an aim that the double-click's second press follows for half
a second. A drag arms only if the card is still under the pointer, and the threshold is measured
on the screen.

A second slip lived at the list's edges. A drag that began in an edge zone — a click on the
card the edge cuts, the one a hand most often clicks — scrolled the list from its first 40 ms
beat, so a five-pixel slip dropped the card one to three places away. A drag that begins at an
edge now scrolls only after the pointer has been out in the open list, or has stayed at the edge
for 400 ms, and every arrival at an edge starts at a tenth of the step and grows.

**Takeaway:** an action that changes the layout as a side effect must keep the user's target
where the user is pointing — or remember what they pointed at.

### The character only the drawn tables had

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** A font size set on "hello", under a drawn table, landed on "\nhell" — and the next
size or font set anywhere moved it again, to "|\nhel", saved that way. In the same lines, Enter
in a numbered list of a note of 8,000 styled words froze the editor for 3.4 s.

**Root cause:** A drawn table is an embedded window, and to Tk's index arithmetic ("+Nc") a
window is one character. The note's text has no such character: the app's offsets are counted
in what `get()` returns, which skips windows. Reading spans out had been made to agree with the
saved text long ago; laying them back still asked Tk for "1.0+Nc", one character early for
every table above. Every font change re-reads all the font runs and lays them again, so each
one moved every run under a table once more. And each of those "1.0+Nc" walked the note from
its first character — the freeze. A breaker reported only the freeze; the misplacement came
out of the sweep the fix owed anyway — every line that turns a saved offset into a place.

**Fix:** One walk lays every span: the offsets sorted, each reached from the one before, and
the windows a hop passes hopped again. With no table drawn every index is the one "1.0+Nc"
gave, checked at every offset of a text with emoji, Chinese and tabs; with tables drawn, every
offset read back from its index is itself. The same round found the undo journal comparing
two snapshots by moving one into the other's windows, which put a position at a window's column
past the window, where Tk keeps a range's end before it: a centred line above a table left an
empty Ctrl+Z after every renumber. It compares both in the text without windows now.

**Takeaway:** an offset belongs to the space it was counted in. Where two spaces differ by
characters only one of them has, convert at every crossing, in both directions — and compare
in the space both sides share, never by moving one side into the other's.

## Tests & CI discipline

*Bugs in the safety net itself: checks that could not fail, suites that lied, and how they got teeth.*

### Tests that always passed, no matter what

*([0.5.0](../CHANGELOG.md#050--2026-08-09) · 2026-08-09)*

**Symptom:** Not a runtime bug in the app — found while setting up automated test runs (GitHub Actions). Two of the five automated QA scripts were failing when run by hand, but nothing about their own output made that obvious at a glance.

**Root cause:** None of the test scripts actually exited with a failure status code when a check failed — they printed a clear "FAILURES: [...]" line, but then exited normally (status 0) regardless. A human watching the output would notice the failure text; an automated system checking only "did this succeed or fail" would see success every time, even with real failures printed right there in the log.

**Fix:** Every test script now exits with a non-zero status if anything failed. This is what makes automated CI meaningful at all — without it, a broken build would show green forever, and the whole point of automation (finding out immediately, without reading logs by hand) would quietly not work.

**Takeaway:** A test suite's own exit code is part of its interface, not an implementation detail — a script that "looks" like it's testing something isn't actually testing anything from an automated system's point of view unless failure changes what it returns, not just what it prints.

### The pixel-perfect test that only worked on Windows

*([0.28.38](../CHANGELOG.md#02838--2026-08-17) · 2026-08-12)*

**Symptom:** Three small layout cramps (a cut-off sort label, a cramped bulk-action button, a Settings button that scrolled out of view) were fixed and verified with exact `tkinter.font` pixel measurements — genuinely precise, not eyeballed. The regression test for one of them then failed in CI, even though the fix itself was correct.

**Root cause:** The test asserted an absolute pixel width, measured locally on Windows using the "Segoe UI" font. The CI runner is Linux, which doesn't have "Segoe UI" installed — Tk silently substitutes a fallback font there with different (wider) character metrics, so the exact same code measured a different width on CI than on a real Windows machine. The fix itself was never wrong; only the test's hardcoded number was tied to a font that isn't guaranteed to exist everywhere the test runs.

**Fix:** Replaced the absolute pixel assertion with a relative one — reconstruct the pre-fix sizing using whatever font actually resolves on the machine running the test, and confirm the real, fixed version is narrower than that reconstruction. This verifies the fix's actual effect (smaller font, tighter spacing making it narrower) rather than a Windows-specific pixel target, so it holds regardless of which font a given environment substitutes.

**Takeaway:** A pixel-exact measurement is only as portable as the font it was measured with. This app only ships for Windows, so the *fix* only ever needed to be correct there — but the *test* runs in CI on a different OS, and a test's environment doesn't have to match the app's target platform. Prefer testing a change's relative effect over asserting an absolute number tied to something environment-specific, when the two can drift independently like this.

*Sister story: ["A toolbar check that measured the wrong thing, three times"](#a-toolbar-check-that-measured-the-wrong-thing-three-times) — the same font-metrics trap, met from the other side.*

### A toolbar check that measured the wrong thing, three times

*(0.36.54 · 2026-08-25)*

**Symptom:** the formatting toolbar overflowed the editor, so the last group could not be reached without widening the window. Fixed — and then CI failed three times running on the check meant to prove it.

**Root cause, each time the same one:** the check asserted *measured pixel widths*. Pixel widths depend on the font, and CI runs under Xvfb where "Segoe UI" does not exist and Tk substitutes something wider — the same bar measures 577px on the development machine and 827px there. A display at different scaling would diverge the same way.

**Three rounds of it.** First, a width budget against a constant: passed locally, failed on CI. Second, the bar was made to wrap, but a special case meant to keep a divider from starting a row kept it on the row it overflowed instead — reintroducing the overflow the wrap existed to prevent, at widths that depend on the font. Third — the worst one — the swept range was narrowed until the bug fell outside it. That turned CI green while making the check unable to catch the very bug it was written for, which was confirmed afterwards by reintroducing the bug and watching the check pass.

**Fix:** the row splitting moved to `core/formatting.py` as `split_toolbar_rows()`, taking widths as plain numbers. Given widths directly it behaves identically everywhere, so the checks are deterministic on any machine. Writing them immediately found two more faults: an invariant of mine that called a lone oversized control an overflow when there is nowhere narrower to put it, and a real one — the "a divider never opens a row" rule was enforced at the break, so a divider dropped there left an empty row for the *next* divider to open.

**The rule worth keeping:** when a test asserts a number that came from measuring this machine, it is testing this machine. Push the logic somewhere it can be given its inputs, and assert the property instead. See also "Tests that always passed, no matter what".

*Sister story: ["The pixel-perfect test that only worked on Windows"](#the-pixel-perfect-test-that-only-worked-on-windows) — the same font-metrics trap, met from the other side.*

### The tests that borrowed the notebook

*([0.55.81](../CHANGELOG.md#05581--2026-08-30) · 2026-08-29)*

**Symptom:** a qa check that had been green for days failed
deterministically one morning — nothing in the code had changed
overnight. Separately, qa1 had a rare unexplained crash (roughly one
run in twenty-six) that four instrumented hypotheses had failed to
pin.

**Root cause:** the qa scripts were never running in a world of their
own. Each starts beside an empty data folder — and the app's own
first-run migration, which runs as soon as a script builds the app,
helpfully adopted the developer's REAL notebook from
`%APPDATA%\NoteOrganizer` into every test run. The checks were being
graded against whatever the owner had done in her app that day; the
morning failure appeared because she had field-tested the `.exe` the
evening before, changing the very data the tests were unknowingly
inheriting. *(Corrected 2026-10-09: this paragraph first said the
migration ran at import time. It had moved into `initialise()`, which
building the app calls, on 2026-08-20 — nine days before this story.)*

**Fix:** a hermetic seed at the top of all nine qa scripts, ABOVE the
`note_organizer` import: write an empty `notes_data.json` plus the
migration marker, closing both migration doors — and refuse outright to
run beside a file holding real notes. Going hermetic immediately
surfaced two latent test bugs that the inherited data had been masking
(a check grabbing "the first Entry on the page", and one replacing the
app's username variable with its own detached copy).

**Takeaway:** "starts from a clean directory" is not the same as
"starts from a clean world" when the application under test actively
imports data on first run. The flake that follows the owner's daily
usage around is the signature of test-data contamination.

### The fix that was dead on arrival

*([0.55.81](../CHANGELOG.md#05581--2026-08-30) · 2026-08-29)*

**Symptom:** mouse-wheel scrolling over tables was fixed to glide in
pixels; every automated check agreed. The user reported, correctly,
that real wheels still leapt from table to table.

**Root cause:** the pixel handler was bound to the body with
`bind()` — and a later line in the same build sequence bound its own
wheel handler to the same widget, which *replaces* a binding made
without `add="+"`. The fix was dead code for every real wheel event.
The checks stayed green because they called the handler method
directly, bypassing the binding chain that reality uses.

**Fix:** one real wheel handler (`_text_wheel_scroll`) that both the
body's binding and the grids' forwarding land in — and the checks now
drive genuine `<MouseWheel>` events through the binding chain, so a
silent overwrite can never pass again. A deliberately manual test-plan
case ("try the physical wheel") exists for the same reason.

**Takeaway:** a test that calls the method proves the method; only a
test that travels the same route as the user proves the feature. And
`bind()` without `add="+"` is a quiet assassin: the second binding
wins, and nothing anywhere reports the first one gone.

### The teeth that had gone dull

*([0.64.95](../CHANGELOG.md#06495--2026-09-02) · 2026-09-01)*

**Symptom:** none — that was the problem. Every test was green, and the
question nobody usually asks is whether green still means anything.
After a run of CI failures the owner asked for exactly that audit.

**Method:** each old regression fix documented in this log names the
bug it killed — so the perfect mutant is the original bug itself,
reintroduced on purpose in a scratch copy. Six fixes were sabotaged
this way; a guarding check was required to go red.

**Findings:** four bit immediately (the title cap, share codes
carrying paragraphs, restore-from-trash normalising, and the autosave
guard — though that one "bit" by hanging the whole suite in a modal
error dialog rather than failing a named check). Two had gone dull:
nothing anywhere pinned the startup purge deleting a purged note's
attachment files — the exact bug of "Files that outlived the notes
they belonged to" could have quietly returned — and nothing pinned the
editor's `0.32.x` short-content-stays-at-top guard, whose list-canvas
sibling had gained mutation-proven checks only the day before.

**Fix:** named, deterministic checks for all three weak spots, each
proven against the same mutant that exposed it. The editor-guard check
stubs `winfo_height` huge so "content fits" holds on any platform and
any font — the check targets the pin, not the geometry lottery.

**Takeaway:** a check written the day a bug is fixed can stop matching
the code years later while staying green the whole time. Reintroducing
the original bug is the cheapest possible proof either way — and the
fixes this log documents are a ready-made mutant catalogue. Audit a
few, every so often; green should have to earn itself.

### The safety net that hid the missing mechanism

*([0.71.125](../CHANGELOG.md#071125--2026-09-10) · 2026-09-10)*

**The report.** While proving the 0.71.125 theming mutants, one refused
to die. The export progress frame had never been theme-tracked; the fix
tracked it; the mutant deleted the tracking — and the qa check asserting
"the frame's colours follow a switch, under BOTH themes" stayed green
with the tracking gone.

**The mechanism.** Two accidents stacked. `apply_theme` ends with
`_recolor_stragglers`, a safety net that walks the whole widget tree
remapping any bg/fg still painted in another theme's palette — so the
untracked frame's fill followed anyway. And the frame's border was the
accent colour, which happens to be the same hex in the stock dark and
light themes — so the one option the net does NOT cover matched "the
right colour" by coincidence, in both themes the check used. The net is
designed as a fallback for exactly such misses; it did its job so well
it made the missing primary mechanism untestable through behaviour
alone.

**Fix:** the check asserts the mechanism alongside the behaviour — the
frame must actually be registered in `themed_widgets`. Same move as the
dialog-focus checks that record the `focus_set` call instead of reading
asynchronous focus back: when the observable outcome is reachable by
more than one route, pin the route the promise is about.

**Takeaway:** a fallback that masks the primary mechanism makes
behaviour checks lie — they go green when the belt is gone and only the
braces remain. Assert the mechanism where a net exists, and distrust
any palette pair that shares a hex: it can vouch for nothing.

### The eight failures that hid two live mutants

*([0.75.180](../CHANGELOG.md#075180--2026-09-25))*

**The fix was the easy half.** Shortening the Trash retention window destroyed everything the
new window had already outlived, at the next startup, with no dialog. Ten mutants were written
for the ten mechanisms behind the fix. Four survived, and every one of them was right to.

**Four checks satisfied by coincidence.** None was wrong about what it asserted; each was simply
also true when the mechanism was broken.

1. The lengthening fixture used a note deleted 40 days ago and lengthened the window to 90.
   Removing the "is this shorter?" test changed nothing, because 40 days is *inside* a 90-day
   window - the doomed list was empty either way, so the test never had to hold. The fixture now
   uses a note older than every window the dropdown offers, the only shape where lengthening has
   something already expired and the test therefore matters.
2. The clamp check compared a previewed window of 0 days against 1, on a note deleted a day ago.
   A day-old note sits exactly on that boundary and reads as expired under both, so unclamping
   changed neither side. Twelve hours tells them apart.
3. The ceiling check compared 10000 days against the 365-day clamp on a 40-day-old note: inside
   both, zero twice. It needed a note older than the ceiling itself.
4. The "counts only what would go" check asserted the number 1. Inverting the window comparison
   also yields 1 - the other note. A count is satisfied by the wrong answer whenever the wrong
   answer is the same size, so the check now names *which* entry.

**And two of the four had not survived at all.** After the first three were repaired, two
mutants still read as survivors with no explanation. `tools/run_tests.py` prints the first eight
failing checks; those mutants broke the ninth and fourteenth, so the names the runner was
searching for were never printed. The checks had fired - the verdict was the tool's.

That is the more dangerous lesson, because it inverts the sign: a mutation runner exists to say
"this check has teeth", and a silently truncated list makes it say the opposite of the truth.
The runner now asks for `--all-failures`, refuses to trust a list it can see was cut, and
`run_tests.py` says "... and N more" when it cuts one.

**The lessons.**

1. A check that asserts a *count* is satisfied by any wrong answer of the same size. Assert
   which, not how many, wherever identity is the point.
2. A fixture chosen to look realistic is often chosen to sit inside every boundary at once. Pick
   the value that can only be explained one way - twelve hours, not one day; four hundred days,
   not forty.
3. Never read a verdict out of output that can be truncated without saying so. A tool that can
   be quietly wrong about whether a check works is worse than no tool.
4. Four of ten checks were satisfied by coincidence, and every one of them passed against the
   real code. Mutation testing isn't a formality that confirms good checks - it's the only thing
   that finds this class at all.
### The finding that described a dialog nobody had opened

*(no version - the label change it produced is `Changed`, and the version counts `Added` and
`Fixed` alone)*

**Three findings in a row, and each one's reasoning was wrong.** The consistency survey recorded
25 asymmetries by reading the source. Working through its destructive rows in order, the first
three all held as *findings*, and all three were wrong about *why*:

- **C-2** said the checklist item was the worse of the pair because the attachment beside it is
  one "the file system still remembers". `remove_attachment` deletes the stored copy. The
  comparison survived; its reason did not - and the reason was what pointed at the wrong fix (a
  dialog, where the answer was an undo).
- **C-3** described the retention dropdown as destroying notes. It also deletes their attached
  files from disk, which no sentence on that screen had ever mentioned, and which the new
  confirmation now names.
- **C-4** said a day row's Delete "removes only that day", with nothing but the row you aimed at
  to distinguish it from deleting the series. It raises a three-button question naming the day.
  Two more of its claims were false: Enter answering the dialog (which no dialog on this Tk
  accepts, and which the same register records as T3-1 two sections above), and a series being
  lost (when it goes to the Trash with an Undo).

**One cause, admitted in advance.** The survey's own coverage confession said no reader ran the
app. Everything above is what that produces: the code says
`if is_recurring(note) and occurrence_date:`, and the reader follows the branch - but the
*dialog inside it* is a call to a function two files away whose three buttons nobody saw.
Reading gets the control flow right and the experience wrong, and a finding is a claim about the
experience.

**What the pattern is worth keeping for.** The survey was still the most productive thing in the
cycle: C-1 was real and serious, C-2 and C-3 were real with the wrong reasons attached, and C-4's
label was worth changing. A review that reads is cheap and finds where to look - it just can't be
the thing that decides. The corrections belong in the register beside the claims rather than
replacing them, otherwise the next reader inherits the confidence without the correction.

**The lessons.**

1. A finding is a claim about what a person meets. Confirm it by meeting it: drive the real
   route and record which dialogs actually appear.
2. Where a finding gives a reason, check the reason separately from the finding. Three times
   running, the finding survived and the reason did not - and the reason is what chooses the fix.
3. A refuted finding is corrected in place, struck through rather than deleted, with the
   measurement beside it. A register that quietly loses its wrong rows teaches nothing about how
   it got them wrong.
4. Cross-check a new finding against the register's own older rows. C-4's "Yes ready for Enter"
   was contradicted by T3-1, already recorded on the same page.
### The guard that knew half the vocabulary

*([0.76.198](../CHANGELOG.md#076198--2026-09-28))*

Filter the note list to **🔁 Repeating**, go to Settings and add a
category, come back — and you are looking at every note again. The filter
reset itself, said nothing, and the two things are far enough apart that
nobody would connect them.

**Found by a pre-flight, and it was not what the pre-flight was for.** The
register's C-15 asks for the sort and filter to survive a restart. Before
storing a value it is worth knowing what the app already does to that
value at runtime, and `refresh_category_widgets()` carried this:

```python
current = self.filter_var.get()
if current != "All" and current not in CATEGORY_COLORS:
    self.filter_var.set("All")
```

The dropdown offers more than categories. Two of its entries are type
filters — `FILTER_REPEATING` and `FILTER_DATED` — and neither is a key in
`CATEGORY_COLORS`, so the guard threw both away. Five call sites in
Settings reach it: adding, renaming and deleting a category all do.

**Measured before it was believed, with a control.** A probe set each of
the four kinds of value in turn, asserted the field really held it, then
made the ordinary call: both type filters were reset, a real category
survived, and a deleted one was correctly reset. The control is what makes
the first result a fact about the vocabulary rather than about the guard
firing on everything.

**The class is one judgement written twice.** The vocabulary lived inline
at the dropdown — `["All", FILTER_REPEATING, FILTER_DATED] + categories` —
and the guard held a half-remembered copy of it. There is one
`_filter_options()` now, which the dropdown is built from and which
`_keep_filter_valid()` asks; and because C-15 needed exactly the same
question at startup, both the load-time and the runtime answer come from
that one place. The alternative was a third copy.

**Takeaway:** before persisting a value, read what the app already does to
that value while it is running. A stored preference inherits every rule
the live one has, including the wrong ones — and a guard written against
one *kind* of value silently governs every kind that shares the variable.
Sibling of
[The paste that landed on top of the placeholder](#the-paste-that-landed-on-top-of-the-placeholder):
both were found by asking what else touches the thing about to be changed,
and both had been shipped for a long time.

### The seven small rows, four of which were not what they said

*([0.76.192](../CHANGELOG.md#076192--2026-09-28))*

The consistency survey's cheapest seven - a search box with no paste menu, a box that forgot its
size, two different plus signs - were picked because each looked like one or two lines. The
pre-flight that runs before any fix changed the shape of **four of the seven** before a line was
written. That's the whole point of the story: the cheap batch was where it paid off most,
because nobody was looking hard at it.

**C-11 grew a constant.** The row asked for `_add_paste_menu(search_entry)` and an ✕. The ✕
needs to know whether the box holds a real query or only its grey hint - and that judgement was
already written out three times: once where the box is built, and twice (lowercased) inside the
two functions that read the query (`if query == "search notes...": query = ""`). Nothing
connected them, so rewording the hint would have left the app quietly filtering every list by it;
the ✕ would have been a fourth. There is one `SEARCH_PLACEHOLDER` and one `_search_query()` now.

**C-12 grew from one field to six, and from a menu to a save.** The row said "the date entry at
minimum; the recurrence number boxes are a weaker case, since they hold single digits." There
are four Repeat boxes, and two are not digits: the end-date is a date (the same shape the row
did want fixed), and the day list holds "1,15". Those two are free, because each one's variable
traces to `update_recurrence_summary`, which schedules the autosave. The date field is *not*
free: it autosaves on `<KeyRelease>` alone, and a paste fires none - measured, a pasted date
scheduled no save while a typed character did. That's the silent loss the field's own comment
says was repaired once for typing; the new menu would have re-opened it on a new route. The
check is now an invariant over the whole editor rather than a list of four fields.

**C-19's premise was different from the row's.** The row offered two branches: persist it, or
say in a comment that the omission is deliberate. The code had something in between - a line at
the body's call site noting that the comments box did not remember. That states the difference
without giving a reason, so the row's condition was never met.

**C-24 needed a different mechanism from its twin, and hid a third divergence.** The row asked
for one sentence and an ✕ "to match the editor's". The editor's ✕ calls `pack_forget()` on its
own area; the sidebar's frame is packed once when the Share panel is built and is part of that
panel's layout, so forgetting it would take the panel's space with it - it clears the frame's
children instead. The two surfaces also disagreed in a third way the row never mentioned: their
titles ("Code for 3 notes (412 chars)" against "Share code (412 characters)"). Left alone
deliberately: the sidebar's note count is information the editor can't carry, and its "chars" is
a width accommodation in the 250px panel this project has already lost time to clipping fights
over.

**Two checks were wrong in instructive ways, and mutants found both.** A new one asserted the
date reached the store after calling `_flush_autosave()` - a forcing call that saves whatever
the editor holds whether anything asked it to. It survived the mutant that removed the paste's
save binding outright; that rule was already written down in `qa/README`, six rules above where
the same mistake was made.

An old one could never have failed:
`check('the comments box is deliberately not persisted', 'comments_expanded' not in
load_settings())`. The key the helper would write is `editor_comments_expanded`;
`comments_expanded` was never a candidate, so the check asserted the absence of a name nothing
would ever create. It stayed green through the change that made the box persist - found only
because a change that should have broken it did not.

**One platform difference was caught by the Linux image and not by Windows:** Tk's Entry paste
deletes the selected text only on non-X11. A check that selected a field's contents and pasted
over them passed here and failed there, with the field holding both values. The app ships on
Windows, so that's the test's problem rather than the product's - but it's the third time the
Linux image has found something invisible on Windows.

**The lessons.**

1. A row's own suggested fix is a hypothesis about the code, and it's cheaper to check than to
   unpick. Four of seven were wrong about scope, premise or mechanism, and every one of those was
   found by a grep.
2. Where a new reader of a judgement is being added, count the existing readers first. The
   fourth copy is the one that makes the first three a bug.
3. A check about an absence has to name the thing that would actually be there. Asserting
   `not in` against a name the code would never write is a check that cannot fail.
4. Reading a rule is not following it. The forcing-call mistake was made again on the same page
   it is documented on, so the mutant is what caught it - which is the argument for running
   mutants on checks that look obviously right.
### The safety guard that read a broken notebook as empty

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** None yet — found by reading. The block at the top of all nine qa scripts, written
after real notebooks were lost to tests run in the wrong folder, treated a notes_data.json it
could not read as an empty notebook and overwrote it with `[]`, and overwrote settings.json
unconditionally. `test_data_safety.py`'s own guard let an unreadable file through too.

**Root cause:** a guard written for one case — a readable notebook holding notes — whose fallback
assumed that anything else meant safe; and nine copies of it, so any fix had to be made nine
times.

**Fix:** One definition, `qa/_qa_support.hermetic_seed`, that fails closed: it refuses outside a
declared scratch run (`NOTEORG_SCRATCH=1`, set only by `tools/run_tests.py` and the CI workflow)
and beside any notebook it cannot prove empty. `test_data_safety.py` follows the same rule, and
proves the guard's four answers.

**Takeaway:** a safety guard's fallback must be the safe answer — "I cannot tell" means stop.

### The save that forgot the next one

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** One qa1 check went red on the Linux runner and nowhere else: holding BackSpace
through a bold word, then Ctrl+Z, gave back "Fr" alone. Re-run, it passed. A second check failed
on every re-run in the same folder and never on a fresh one.

**Root cause:** Two, of different kinds. The second was the test's: the bulk export names its
files after what the folder already holds, and the check listed a fixed folder that an earlier
run had filled. The first was the app's. The autosave's timer callback began by setting its job
to None — assuming it was the timer that job tracked. Run any other way while a timer waited (the
qa scripts call it directly, as "the timer firing now"), it left that timer scheduled with
nothing tracking it, and the next cancel had nothing to cancel. On firing, the stray timer set
the *next* job to None the same way: a relay of untracked saves, 28 of them in one qa1 run,
counted by wrapping every timer the app scheduled. One fired between two presses of the held
key, and a save's boundary ends a run of deletes — on purpose, as a pause does. A 0.7-second
wait between presses reproduced it on any machine. The find bar's rescan and the Calendar
History's search render had the same shape, run directly from the Aa box and the year chips:
duplicate work in the app, nothing a person sees.

**Fix:** The autosave and the History render cancel a waiting timer instead of forgetting it —
work that runs now makes the waiting one redundant. The find rescan's job is cleared only by its
own timer: a waiting rescan may carry a reveal the direct one does not. The checks ask Tcl which
timers wait, not the attribute the app keeps, and a held key in the checks presses and releases
with the autosave held for the burst. The export check gets a folder of its own each run.

**Takeaway:** a job attribute answers only for the timer it tracks. A callback that clears its
own job must be sure it is that job's timer — or cancel instead of forget. And a flake that
re-runs green has a mechanism: slow the machine down on purpose and watch it fail.

### The clipboard the tests shared with whoever was at the machine

*([0.83.335](../CHANGELOG.md#083335--2026-10-02))*

**Symptom:** qa1's check "pasting copied cells below the table makes a SECOND table" went red
on a developer machine — a third time — while the Linux run stayed green and the same run passed
again a minute later. The tables were never wrong.

**Root cause:** The suite copied and pasted through the machine's real clipboard, which every
program on the machine shares. One that holds it open for an instant — Windows' own clipboard
history reads it right after every copy — makes a read return nothing: the app's clipboard
module returns None and Tk's fallback fails the same way, so the paste pastes nothing. The
check's earlier repair waited until one read succeeded, and only moved the race: the paste then
read the clipboard again. And every run wrote over the clipboard of whoever was working at the
machine while it ran.

**Fix:** The helper every qa script and story already calls, `pin_the_desktop`, gives every app
the script builds a stand-in clipboard kept in the process: Tcl's `clipboard` command, Tk's
CLIPBOARD selection that Text and Entry paste through, and on Windows the app's own clipboard
module — with Tk's own rules (an append claims the clipboard and drops its HTML; an empty one
refuses a read). No other program can take part, and nothing the person copied is touched.

**Takeaway:** a flaky check is a check with a hidden dependency. "Wait for it to work" moves the
race; taking the shared thing out of the test ends it — the same lesson as
[The tests that borrowed the notebook](#the-tests-that-borrowed-the-notebook), for the
clipboard.

### The tick that took the colour of its words

*(found in the owner's first full manual pass, on the 0.84.341 `.exe`)*

**Symptom:** on every dark theme, a tick in Share notes or in Settings → Duplicates did not
show. The tick was taken — the copies still went to the Trash, the code was still made — so a
second click "to make it work" took it away again, and Share answered "Pick at least one note".
Light themes were fine.

**Root cause:** Tk paints a tick box's mark in the box's own text colour. That had been
measured for the radio buttons, whose dot vanished the same way; for the tick boxes the palette
and a comment said the opposite — "the mark is dark whatever the palette says" — eight times
over, and nobody had measured it. It held only for boxes that set no text colour. Once every
well became light, the two boxes that carry light words drew a light mark on a light well;
"Group by category" and the find bar's "Aa" drew a faint one.

**Fix:** a tick box that carries words draws its own box (`_drawn_tick_box`): two shared
images, a light well and a dark mark, redrawn with the theme — the way the Select-mode boxes on
the note cards were already drawn. Boxes without words keep Tk's dark default. qa4 now judges
every ticked box on every theme by what is drawn, the mark against its well, with Share,
Duplicates and the find bar open; the old rule asked only that the well be light.

**Takeaway:** a rule written as "always" is a measurement nobody made. The radio was measured
and fixed; its twin was assumed and shipped. Judge a control by what it draws, on every theme,
not by the option you think draws it.

### The copy that wrote its own table

*(found in the owner's first full manual pass, on the 0.84.341 `.exe`)*

**Symptom:** table cells copied into Word arrived as a bordered table with every colour gone;
pasted back into a note, as a second table or into another table's cells, they came as bare
values. A word set in another size or font lost both on its way to Word and on its way into
another note — though the guide promised that copying between notes keeps everything.

**Root cause:** the cell copy built its own HTML, one escaped value per cell, while the export
already knew how to write a cell with its highlight, styled words and alignment. And what it
remembered for a paste back here — values, widths, the table's place — had no room for styles.
The note's own HTML writer, for its part, left size and typeface out entirely, and a paste
reads neither back on purpose (a web page's sizes are not the note's), so even a copy between
two notes had nowhere to carry them.

**Fix:** one cell writer — the copy now writes each cell through the export's own
(`cell_html`) — and the copy remembers each cell's styles and alignment, laid back on the same
cells when our own copy is pasted (`_grid_lay_cell_styles`, through the rewrite's `extra`). The
HTML now carries size and typeface out; a paste still reads none in, and our own copy brings
them from what it remembered, recognised by its exact HTML rather than by its words, so the
same words copied from elsewhere bring nothing of ours.

**Takeaway:** a second writer of the same thing starts out as a copy and ends as a subset —
every feature the first one learns, the second never hears of. When one writer exists, call it.

### The list that rewrote the whole note

*(found in the owner's first full manual pass, on the 0.84.341 `.exe`)*

**Symptom:** Enter on a numbered line threw the note's scroll back to the top. The new item and
the numbers were right; the place in the note was gone, and with tables in the note it went
further. Backspace, Tab and the list buttons did the same whenever a number changed.

**Root cause:** keeping a numbered list reading 1, 2, 3 changes only the markers, each on its own
line — but the renumber deleted the whole body and inserted it again, re-laying every style from
a saved copy. Tk moves the view to the first line when everything above it is deleted, and every
drawn table went with the text, so each Enter tore every table down and drew it again. The
caret was put back by hand; nothing put back the view.

**Fix:** `_renumber_lists` writes only the characters of each marker that changed, carrying the
line's own tags onto the new digits. Every style, the view and every drawn table stay where they
were, and a caret at an item's start stays there (the caret's mark is left-leaning for the
edit). Enter in a list now keeps its new line in sight, as Tk's own Enter does.

**Takeaway:** write only what changed. A rewrite of everything moves everything that hangs off
the text — the view, the tables, the caret — and each of those then needs its own repair, one of
which will be forgotten.

### The marker that was only characters

*([0.96.394](../CHANGELOG.md#096394--2026-10-22) · 2026-10-22 · found probing numbered lists,
after 0.96.392)*

**Symptom:** items 2 and 3 of a numbered list selected and deleted left "1. one / 4. four"; a
letter typed over them left "x4. four"; Backspace at the very start of item 3 left
"2. two3. three"; a paste over them left "zz4. four". The numbers came right only at the next
Enter. Every one of seven deleting routes and three pastes did it, and so did the Android app,
which had ported the same rules.

**Root cause:** a list's marker is stored as characters (`core/formatting.py` says why), and the
deletes that reached a list were Tk's own: Backspace and Delete over a selection, Cut, typing
over it, a paste, Backspace at a line's start. Each deleted characters and nothing else. The
list's own keys — Enter, Backspace just after a marker, Tab, the buttons — renumbered; nothing
else did, and nothing knew that a marker left in the middle of a line had stopped being one.

**Fix:** `list_deletion_range` decides where a delete that reaches a list really falls, the way
Word behaves, where a marker is no character at all: two lines joined keep the first one's marker
and lose the second's, and typing or pasting over whole items keeps the next item's number.
`_list_aware_delete` takes Tk's own deletes over in the bindtag that sees every key first, the
paste routes ask the same question, and each renumbers in one undo unit. A net renumbers after
any key that took lines away, for a route nobody has named yet. Backspace just after a marker,
the list's own route, took two Ctrl+Z (the numbers first, then the marker); it is one unit now.

**Takeaway:** when a structure is stored as text, every route that edits text edits the
structure. Count the routes that reach it — the keys, the clipboard's three, typing over a
selection — not the ones the feature was written for.

### The rescue copy that outlived what it rescued

*([0.96.395](../CHANGELOG.md#096395--2026-10-23) · 2026-10-22 · found on the Android app by an
agent playing an ordinary user; the desktop did the same · issue #299)*

**Symptom:** a note's text selected whole and deleted, then brought back with Ctrl+Z. The button
**↩ Restore previous** stayed. Later edits were made — a line added, words appended, two items
bolded — and the button pressed: the note went back to the version before the deletion, the later
edits gone, Undo empty, the button gone. The question had said only "The current text will be
replaced".

**Root cause:** the rescue copy (`_prev`) was made by the save that shrank the note and spent only
by a restore. Nothing asked whether the note still needed rescuing, so a copy whose words were
back on the page went on offering itself; and a restore, the one action that replaces text
wholesale, left nothing behind to take it back.

**Fix:** the owner's call, on both apps. A save that holds again everything the copy kept spends
it (`rescue_copy_spent`), and the button goes. A restore keeps what it replaces as the copy in
its turn (`copy_replaced_by_restore`), so the same button brings it back — unless it holds
nothing the restored version lacks, an emptied note above all, when a button offering it back
would only mislead. The question says the text is kept only when it will be.

**Takeaway:** a safety net that can be pressed later must know whether it still rescues
anything — and pressing it must leave a way back, or the net becomes the fall.

### The safety net that measured the wrong thing

*([0.96.401](../CHANGELOG.md#096401--2026-10-26) · 2026-10-24 · found by the owner walking test case 692 on the 0.96.396 `.exe`; the
Android app did the same · issue #307)*

**Symptom:** a note of three short lines, selected whole and deleted, then a new line typed before
the autosave ran. No **↩ Restore previous**, and the three lines were gone. Wiped and left until
the autosave, the same note kept its copy.

**Root cause:** the copy was made when the text got *shorter* by more than 40 characters, and by
30% of it or 200 characters — or was emptied. Thirty characters replaced by ten shrink by twenty:
under the bar, no copy. The rule measured how much shorter the text was, while what it guards
against is how much of it is *gone*, and the two part ways whenever something new is written in
its place. A paragraph of 300 characters replaced by one as long did not get shorter at all, in
a note of any length. The emptied-note rule of 2026-09 had caught one case of the same mismatch,
the emptied short note, and left the rest.

**Fix:** `rescue_copy_due` counts what of the old text is gone — its length less the longest start
and end the old and new text share (`text_lost`) — with the same bars as before, plus one for
most of a short note: 70% of it, 15 characters at least. A word changed, words added, a tiny note
retyped and a title renamed still keep no copy. The Android app's `updateNote`, which follows the
desktop's thresholds by design, takes the same rule.

**Takeaway:** a guard has to measure the harm itself, not something that usually moves with it. A
proxy holds until the day the two part ways — and a safety net is exactly where that day costs
the most.

### The plain paste that read only the spreadsheet's copy

*([0.96.401](../CHANGELOG.md#096401--2026-10-26) · 2026-10-24 · found by the owner beside test case 693 on the 0.96.396 `.exe`; the
Android app has no cell copy · issue #308)*

**Symptom:** a table's cells selected in its grid, copied, and pasted into a new note. Ctrl+V
brought the table back. Ctrl+Shift+V brought words separated by tabs, a ticked box as "[x]". The
same paste of a text selection holding the table, which test case 693 walks, was fine.

**Root cause:** a cell copy writes three things: tab-separated text, for a spreadsheet; HTML, for
a document; and the app's own record of the cells, styles and place included. Ctrl+V recognises
its own copy and rebuilds the table from it. Ctrl+Shift+V reads the plain text alone, by design —
and for this copy the plain text is the spreadsheet's form, not the note's.

**Fix:** when the plain text is exactly what this app's own cell copy wrote, Ctrl+Shift+V builds
the table from it as Ctrl+V does (`_paste_tsv_as_table(plain=True)`), leaving out the cells'
colours, bold and the table's place on the page — the formatting a plain paste promises to drop.
Tabs from anywhere else still paste as text: there Ctrl+Shift+V stays the way to get words when
Ctrl+V would make a table.

**Takeaway:** a copy written in several forms for several readers has one form that is the
thing itself; every paste of it, plain included, has to start from that one, and drop only what
it promises to drop.

### The row Excel marked inside its own table

*([0.96.401](../CHANGELOG.md#096401--2026-10-26) · 2026-10-25 · found by the owner on 0.96.396, beside test case 693; the cause read
from her clipboard, once, with her leave · issue #309)*

**Symptom:** one row of the test plan copied in Excel and pasted into a note with Ctrl+V came in as
loose text: "| High", then "| The", then "app open on the phone." — the second cell broken where
Excel had wrapped it. The guide said a table copied from Excel lands as a real table, and every
check of that passed.

**Root cause:** the HTML on the Windows clipboard is a whole document with two markers around what
was copied, and the app read only what lay between them. Excel puts the markers inside its table:
around the rows, and for a single row around its cells. Between them, then, were two cells with no
row and no table, and the reader writes a row's closing pipe only at the row's end, so the line
was no table row. With no block tag in sight, the reader also took the markup's own line breaks
for a PDF's real ones. The template editor and a paste over selected cells look for `<table>`
between the markers before anything else, so they never saw a table in a copy from Excel either.
The checks had never seen what Excel writes: they handed the paste a fragment holding `<table>`,
as a web page writes it, and the cutting itself runs only on Windows, where no check reached it.

Testing the paste found one more: a table of one column, or one cell, came in framed —
"| rent |" — which is no table here, a table having two columns at least.

**Fix:** `fragment_of` reads the document up to the start marker and opens again, around the
fragment, the table, row, cell or list still open there, closing them after it; formatting open
there is left out, since only structure changes what the text is. Our own copy, marked straight
inside `<body>`, comes back exactly as written, which is how a paste still knows it. A row of one
cell is written as the cell's words alone, its line breaks real lines.

**Takeaway:** a stand-in for another program must say what that program says, not what we expect
it to. The checks were written from how a web page puts a table on the clipboard, and passed all
along while Excel, the program the guide named, wrote something else.

### Nine regressions in fifteen fixes

*(found by three read-only reviews of the fixes above, before any of them shipped)*

**Symptom:** none reached a user. Fifteen fixes from the owner's manual pass were done, tested,
mutation-tested and green on the whole suite; three reviewers, each reading one part of the change
and running nothing, found nine ways the fixes broke something else.

**Root cause:** most of them changed WHEN something happens, and were checked only on the route
they were reported on. The open-cell highlight was laid when the cell closed — and leaving a note
flushes a cell without closing it. The click on empty space moved the keyboard to the window — and
an open table cell's own focus check reads "the window" as a passing moment, so it stayed open.
"Show more" now added a page under the rows on screen — and nothing redraws those rows when a
note is deleted from the sidebar beside them. The tick boxes took their fill at build — and a theme
switch does not rebuild an open panel. The cell copy read styles with the tables drawn — while the
reader had only ever run with them down, where no window sits at a line's start.

**Fix:** each one, with a check that fails without it (mutants A01–A09). And one older mutant,
U40, survived the whole-catalogue run for a good reason: the new click handler now finishes the
date field on a click on empty space too, so the date's own click watch is needed only where a
click moves no keyboard — the check was moved to that case.

**Takeaway:** a fix that changes when something happens has to be walked through every reader of
that moment — every caller of the flush, every holder of the focus, every panel left open across
the change — not only the route it was reported on. The suite proves what it was told to; readers
of the diff find what nobody told it.

### The border that went grey whenever it was used

*(found on a photograph of the checklist's new ring, before it shipped)*

**Symptom:** the ring that marks the checklist item the keyboard is on came out grey in the
photograph, not the theme's accent — while the check for it, reading the row's border colour,
passed. Looking for siblings turned up a shipped one: the find bar's accent border was the same
grey the whole time anyone typed in it, on every theme, since the bar was built.

**Root cause:** Tk paints a frame's border in `highlightbackground` only while the keyboard is
outside the frame. The moment it is on anything inside — the tick box in the row, the box in the
find bar — Tk counts the frame as holding the focus and paints `highlightcolor` instead, which
nobody had set, so the system grey stood in. A pure-Tk probe showed it in four lines: red with the
focus outside, grey (100, 100, 100) with it on the frame's child, blue once `highlightcolor` was
blue. The check read the option that was set, so it agreed with the code and not with the screen.

**Fix:** a frame with a coloured border sets both colours, and moves both together: the
checklist's rows (a note's and a template's), the find bar, which tracks both with the theme, and
the picture preview, whose buttons can hold the keyboard. `ring_mismatches` in qa's support
module walks a window for any bordered frame holding something that takes the keyboard, with the
two colours apart; qa1, qa7 and qa9 run it where those frames are open. Mutants O21–O23 and
X01–X03 take each part back out. The frames left alone hold only labels, which never take the
keyboard: the category dropdowns and the export progress bar. The Settings buttons are another
case: the border changes while the button itself holds the keyboard, which is Tk's focus ring,
there on purpose.

**Takeaway:** an option is a request, and the toolkit decides when it applies. A check that reads
back the option you set can only agree with you; the photograph is what disagreed.

### The heart that left a gap

*(found on a photograph of the welcome note, before it shipped)*

**Symptom:** the welcome note's headings showed a wide gap after their icon — "✍     Write". The
same gap followed ❤️, ✌️, ☀️ and ⚠️ chosen from the emoji picker, three of the calendar's day
markers, and the picture icon in the attachments list.

**Root cause:** each was written with U+FE0F, the variation selector that asks for an emoji's
colour form. Tk has no colour emoji, so it ignores the request — and draws the selector itself
as a blank about two letters wide. A pure-Tk probe measured it: "❤️ love" 71 px, "❤ love" 49 px,
the same 22 px on every pair, plain and bold.

**Fix:** the app writes none: the picker, the day markers and the icons lost theirs, and
`without_variation_selector` (in `core/formatting.py`) strips it from day markers as they are
read from settings or a backup, so a heart saved by the old picker matches the new picker's heart
and can be taken off its day. test_richtext scans every source file of the app for the character.
Text that already carries it is left alone on purpose: removing a character from a note's body
moves every style span after it, which is a change to stored data of its own (Known limitations
in the ROADMAP).

**Takeaway:** an invisible character is still drawn. When the toolkit draws it badly, keep it out
of what the app writes, clean it where nothing hangs off the text, and say plainly what is left.

### The icon drawn as narrow as a letter

*([0.96.392](../CHANGELOG.md#096392--2026-10-21) · 2026-10-21 · found by the owner, reading the
welcome note thirteen days after it shipped)*

**Symptom:** the welcome note's "Good to know" heading started further left than the headings
above it. Measured, every icon was 23 px wide and its title began at 43 px — but ℹ was 7 px and
"Good to know" began at 27, and ✍ was 17 px, putting "Write" at 37.

**Root cause:** Tk draws each character with the first font that has it. The note's text font has
ℹ (U+2139) and ✍ (U+270D), older symbols, and draws them at the width of a letter. The other
icons are in the emoji block (U+1F000 up), which only Segoe UI Emoji has, at one width of its own.
Table cells were never affected: they tag every emoji with the emoji font themselves, a rule the
body does not have.

**Fix:** the note's two icons are 💡 and 📝, from the emoji block. Extra spaces were measured as
the other way and rejected: a space is about 4 px against a 6 px gap that changes with each text
size, so no count of them lined up at the default size, and some made it worse. Giving the whole
body the cells' emoji font was rejected as well — a rule over every character of every note, for a
column only the app's own note has. `test_data_safety` holds every heading's icon to the emoji
block; qa5 measures the column on Windows.

**Takeaway:** an icon's width is the width of whichever font answered for it. Where icons must
line up, choose them from the one range a single font draws, and measure the column rather than
trust the look of one line.

### Photographs of the site's pages, blank below the first screen

*(2026-10-24 · found by a design review of the website, run by an agent at the owner's request)*

**Symptom:** the website's document pages, printed or saved as a PDF, gave the title, the
Contents and then blank pages. A Contents link landed on text still fading in; a tall table at the
bottom of a page could stay invisible. And the site's own browser walk, whose full-length
photographs of those pages were looked at before each upload, had been photographing pages empty
below their first screen — nobody had seen the problem in pictures taken to show it.

**Root cause:** each block of a document page faded in as it scrolled into view. The walk photographs
a whole page from the top, so nothing below the first screen ever "came into view"; printing never
scrolls either; a jump lands before the fade ends; and a visible slice of a tall table under 5% of
its height never crossed the threshold. The same blind spot hid the pictures too: an image marked
`loading="lazy"` loads only near the screen, and showed in the photographs as an empty frame.

**Fix:** the fade was kept, the owner's choice, and held to what it broke: blocks on the first
screen are never hidden; any visible pixel shows a block; a click on an in-page link, a page opened
at an anchor and printing show every block at once. The walk photographs the document pages with
motion reduced, as a visitor who asks for it sees them, scrolls a page through and waits for its
pictures before a full-length photograph, and checks the fade on its own, with motion on: the
first screen shown at once, nothing hidden in print, a Contents jump landing on text already shown,
every block on screen at a page's end. All four failed against the old code.

**Later the same day:** the owner found the repaired fade "almost instant" — it had been made quicker
too (.35s and 8px, from the first pixel), and it no longer flowed as she scrolled. The first pace
came back: 0.6s and 16px, a block arriving once its top passes the screen's lowest twelfth, the
first screen fading in on opening as before. Of the repairs, the ones a reader never sees stayed:
print, jumps and anchors show everything; threshold 0 against that line still shows a tall table;
and a page's last short block, which could sit in the lowest twelfth with nowhere left to scroll,
arrives at the end of the page. The overview fades the same way now, a row of cards one after
another. The walk's first-screen check became "fades in slowly, and has all arrived a moment
later", with one that a block is still on its way in just after a scroll.

**Takeaway:** a photograph proves only what was on the screen when it was taken. A page that
changes with scrolling or time has to be photographed in the state a reader meets it — and the
behaviour that changes it needs checks of its own, not the photograph's silence.

## Smaller lessons, moved out of the code

*Each of these was once a long comment beside the code it explains. The code now says why in a
line or three and points here, by name, for what happened.*

### From the entry file (`note_organizer.py`)

- **The export menu's comment** — It said "Markdown is portable but drops what Markdown cannot
  say", describing a third format the menu has never built. A docstring making the same claim had
  been corrected a release earlier; the sweep missed this one because it greps as a comment about
  Markdown rather than as a claim about the formats on offer.
- **`_sync_editor_snapshot`** — This was `refresh_tab_strip`, which drew a row of tabs above the
  editor — a row that could never appear. Every path that touches the list of open notes resets
  it to a single entry and nothing appends to it, so the strip's "hidden at 0–1 notes" branch was
  the only one ever taken. Recorded as finding C12 in the coverage ledger and closed by removing
  the strip rather than by building tabs for several notes. What was never dead is the snapshot
  it refreshed on the way: the dirty comparison and the restore after a bulk delete both read it,
  so it is kept under the name of what it actually does.
- **`_tab_ring_if_tabbed_to`** — Bound first on `<Tab>` in the `all` tag, it never ran: Tk walks
  the keyboard on the virtual events `<<NextWindow>>` and `<<PrevWindow>>`, and with both bound
  on one tag the virtual binding won, so traversal carried on and the handler stayed silent. A
  probe that printed what the tag held is what showed it. It now joins Tk's own script there with
  `add="+"`, after the traversal, which it must never replace — and it asks `tk_focusNext` where
  the key is going rather than `focus_get` where it went.
- **The push-down's caret line** — The Enter that pushes a leading table down moves the caret by
  code, and did not say so: the release of that same key then read as the caret leaving a table,
  and every table in the note was tidied and rebuilt a second time. Its menu twin, "Add a line
  above the table", paid the same rebuild on the first letter typed after it. The 2026-09 audit
  could only call this a diagnostic-confidence finding, and two things kept it unmeasured: the
  frames a burst capture takes are about 45 ms apart, and the second rebuild changed no pixel in
  them — and the burst scene named for it opened with a caption line, so it had timed an ordinary
  Enter all along. Counted on a real press and release (2026-10-12): two rebuilds per Enter,
  about 8 ms and 12 ms for a note of ten tables on a fast machine, and one with the fix. Code that
  moves the caret notes the line it left it on (`_last_caret_line`), as paste already did.

### From `core/model.py`

- **`shared_update_changes`** — Both sides are compared in the shape a load gives them. The note
  in memory can still hold what the editor wrote raw — a day's edit carried an empty colour that
  `normalize_note` drops — while the incoming copy has been through `normalize_note`. Compared as
  they were, a backup holding this very note read as "edited elsewhere" until the next restart,
  and Update spent the rescue copy on it.
- **`clean_override`** — Written raw, a day's edit kept an empty colour the load then dropped,
  and the two copies of one note compared as different until the next launch. An override
  carries a colour as the note does, and it ends in a Tk `configure()` when the day is drawn:
  checking only that it was text let "#nope" through, so one per-day colour from a share code, a
  backup or a hand-edited file could raise during the startup calendar render — the
  make-the-app-unopenable class the note's own colour had been closed for, through the one door
  that fix did not cover. And a day's text had to take the base body's canonical form as well:
  the editor draws a line under a trailing table, so a stored day's text was one newline short
  of the screen, and an edit ending in a table read as unsaved forever — a save question at every
  note switch and at close, for an edit nobody made.
- **The checklist ceiling** (`normalize_note`) — Every checklist item becomes a frame, a check
  box, a label and a variable when the note is drawn, and nothing upstream limited how many could
  arrive: a hand-made share code carrying 20,000 items is only 60 KB of pasteable text, passes
  every guard the decoder has, and killed the process on render — permanently, because the note
  is saved first and drawn again on the next launch. The cap (1,000) is far above any real list
  and lives in `normalize_note`, the one choke point every route passes.
- **`repair_note_ids`** — The id is how the whole app finds a note — `find_note` returns the
  first match, and a delete filters by it — yet nothing kept it unique after the one-time cleanup.
  Two notebooks merged by hand both number from 1: editing the second note of a pair saved into
  the first, silently replacing its text, and deleting either took both to the Trash. And
  `normalize_note` turns an unusable id into 0, which the editor reads as "no note selected".
- **`rename_category_everywhere`** — The rescue copy an update leaves holds the category and the
  per-day edits it replaced. Left out of a rename, a later "↩ Restore previous" filed the note
  under General and its day under the old name, which the next launch brought back as a category
  of its own.

### From `core/storage.py`

- **`load_notes`** — The note the user had open is remembered by its id, and the one-time
  cleanup renumbers every id from 1, so the remembered number has to be re-pointed at the same
  note, or it silently comes to mean whichever note inherits it. Measured before the fix: with
  one empty note in front of it, the note being read moved from id 2 to id 1, the setting still
  said 2, and the next launch opened the note after it. It is matched by identity, not content —
  `clean_notes` returns the very dicts it was handed — and a note the cleanup removed (empty, or
  an exact duplicate merged into its twin) leaves nothing to re-point at: the app then opens no
  note at all, the honest outcome, and far better than opening someone else's.
- **`restore_many_from_trash`** — A note whose category was deleted while it sat in the Trash
  comes back under General, but that is `normalize_note`'s doing. The method this replaced
  checked the category itself and fell back to the same value, which had no effect; the check was
  dropped rather than carried over, and the guarantee is tested where it lives.

### From `ui/note_list.py`

- **`_list_scrolled_by_hand`** — Only a scroll that leaves the ring's row out of sight counts,
  read once the view has moved. Every wheel notch used to count, even one that kept the card in
  view or moved nothing at the end of the list: the next save that took the card away then put the
  ring on another note, and Enter opened that one.
- **`_filter_options`** — The filter's choices had been written out inline at the dropdown and
  then half-remembered by the guard that keeps the selection valid, which asked
  `not in CATEGORY_COLORS` — true of both type filters, neither of which is a category. So
  filtering the list to Repeating and then adding a category in Settings silently threw the
  filter away and showed everything. Measured on the real app before the change, with a control:
  a real category survived the same call, and a deleted one was correctly reset.
- **`refresh_note_list`** — A rebuild's scroll restore is in force from the moment the rows are
  drawn, not from when the app is next idle. Every deliberate scroll — the wheel, the scrollbar,
  the ring's scroll into view, a click keeping its card under the pointer — cancels a restore by
  clearing `_list_restore_px`, and since 0.96.394 so does a new search, which starts at the top. A restore queued as a bare callback could not be cancelled, and
  scrolled the view back after them; a press measured in one view and a jitter read in the other
  then passed for a drag.
- **`_list_extent`** — How far the list reaches is worked out from its rows, never asked of Tk.
  The frame the cards once lived in started at y=0, so `bbox("all")` did too, and every scroll
  guard counts on that. A drawing's bbox starts at its first item, at the first card's margin,
  and the top of the list read as "scrolled four pixels": every rebuild kept its old depth, and a
  snap to the top landed at 4. An empty rectangle from 0 papered over it on Windows and failed on
  the Linux image — Tk 8.6.15 counts a pixel round a rectangle with no outline into its bbox and
  8.6.16 does not, so the same rectangle read (0, 0, …) on one and (1, 1, …) on the other. The
  app knows where its rows end.
- **`_reflow_list`** — Rows that move by the same amount move together, in one tagged move of the
  band they stand in. A canvas finds a tag by walking every item it holds, so moving each row by
  its own tag cost rows times items: 2.6 s to close the gap one delete left in a list drawn to the
  end of 5,000 notes, and a first autosave of a note far down paid the same. A band is tagged by
  what lies wholly inside it, before any band moves, and trusted only if it holds exactly its
  rows' items; otherwise those rows move one by one. Tk's search for what lies inside skips hidden
  items, and in Select mode every unticked card's tick mark is one: every band came up a mark
  short per card and moved row by row — 4.7 s for a delete at 5,000 notes. The marks join their
  band by id, a lookup rather than a walk of the canvas, so they travel with their cards.
- **The Custom order offer** (`_move_note`, `_on_sort_chosen`, `_custom_order_knows`) — A move
  made while the list is sorted some other way starts Custom order again from the order shown,
  which replaces any arrangement made by hand earlier. It used to go without a word: one Alt+Down
  while looking at the list by title, and the arrangement was gone from the notes file. The toast
  then said so and offered it back for eight seconds — and the next toast with an Undo, a
  delete's say, took the offer's place, so the arrangement had no way back at all. It is kept for
  the session now, and choosing Custom order asks whether to bring it back. Which arrangement is
  kept took three rounds. A second move in a sorted view "replaced" the first replacement, and its
  marks took the place of the hand-made order's, which then had no way back; so the one made by
  hand is kept. But an arrangement made by hand *on* that replacement is then the newest one made
  by hand, and offered the older one, the newer was lost; so "made by hand" means the order
  differs from the one the last such move left — not that a card was moved, since Alt+Down then
  Alt+Up arranges nothing, and counted as an arrangement it gave the older one's place to the
  replacement itself. And counting only the note a move by hand moved missed an arrangement made
  by moving a known card past a new one: the known notes' order was unchanged, and the newest
  arrangement was replaced by the older. Counting every note a move passed would count a card
  moved past a new note and back; so new notes are placed in the record where they stand, and the
  move is compared like any other.
- **Dragging at the list's edge** (`_scroll_list_drag_near_edge`, `_list_drag_scroll_step`) — The
  card cut by the list's edge is the one a hand most often clicks, and a click whose hand slips
  five pixels starts a drag: it scrolled the list under the held card from the first beat, and
  the release dropped the card one to three places away — the list switched to Custom order, or
  a hand-made one changed without a word. So a drag that began at an edge waits, and every
  arrival at an edge starts slowly. The speed itself grows with how far the pointer is pushed
  past the edge, because at a tenth of the view a beat, taking a card from the bottom of 300 notes
  to the top took over a minute; and the first beats ramp up, because at the full step from the
  first beat, an edge reached a moment before the release had already carried the list a card or
  two along.
- **`_list_focus_in`** — When the keyboard comes back to the list, the ring must be where the
  person can see it: a ring left 900 pixels above the view had Enter open a note nobody could see,
  and the menu key post its menu off the screen. What took the ring's row out of sight decides
  how. If the person scrolled the list away, the ring goes to the first row the view shows, and
  the view stays where they put it. If the list moved the row while the keyboard was elsewhere —
  a save took the card to the top, a search showed its results from the top with the card far
  below them (until 2026-10, by filtering out the notes above it, the view kept) — the ring
  stays on its row and the row is brought into view; given to the first row in view instead, it
  sat on another note, and Enter opened that one.
- **`_restore_card_focus`** — Since the cards became a drawing, a rebuild never moves the
  keyboard: the canvas that holds it survives, and only the drawing is replaced. That ended a
  whole class of trouble the widget cards had — a keyboard left on a destroyed card, and a guard
  that had to decide from `focus_get()`, which answers None whenever another program holds the
  desktop's foreground, whether to pull the keyboard back.
- **The surgical updates** (`_remove_note_cards`, `_bulk_select_all`, `_toggle_note_selected`) —
  A family of updates that change a few cards instead of rebuilding the list, each written
  because a full rebuild "visibly flickered the whole list" for a change that touched a few cards:
  the theme recolour, Select mode, the open note's outline, then deleting — the one frequent
  action still paying the full price when the cards were widgets, 120 of them destroyed and remade
  in 115 ms to take one card away (field-reported as "the picture breaks a little and rebuilds
  itself") — then Select all, where a rebuild to move the ticks cost 140 widgets and about 170 ms,
  the flicker the button was reported for, and every single tick, which flickered on each click.
  The save's one-card redraw is the sixth
  ([The list that was drawn whole, for every pause in typing](#the-list-that-was-drawn-whole-for-every-pause-in-typing)).
  The two that move rows return False when they cannot be sure, and the caller rebuilds: a list
  that quietly disagrees with the notes is far worse than one that flickers.
- **`_query_matches_note`** — The list and "Select all visible" each carried a hand-rolled copy of
  the search rule, and the copies drifted: the list stripped a table's plumbing from bodies (so
  searching "---" stopped matching every table note) while Select all matched the raw body — so
  Select all quietly ticked notes the filter had hidden, and bulk actions hit them. And an empty
  query is answered without reading a note: every rebuild, every autosave's one-card redraw and
  every tick in Select mode used to lowercase every body and parse every table in the notebook to
  find that nothing typed is in all of them.
