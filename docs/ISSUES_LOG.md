# Notable Issues Log

A narrative log of the more interesting bugs found and fixed during development — chosen
because each one taught something worth remembering, not because they were the only bugs.
Routine fixes are just commits; these are the ones with a real "why did this happen" behind
them. The standing rules many of them produced live in [ARCHITECTURE.md](ARCHITECTURE.md);
the releases they shipped in are in the [Changelog](../CHANGELOG.md). See also the
repository's [Issues](https://github.com/AlexandraMoldovan95/noteOrganizer/issues) for
day-to-day tracking.

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
| [The paste that landed on top of the placeholder](#the-paste-that-landed-on-top-of-the-placeholder) | `bind()` replaces where `add="+"` accumulates, so a widget's own binding silently displaces a shared helper's; and a virtual event outranks the physical one beside it in the same bindtag. | 0.75.185 |
| [The sweep that stopped at the edge of the Settings page](#the-sweep-that-stopped-at-the-edge-of-the-settings-page) | A fix's sibling sweep must name the surfaces it did not visit; a cap in characters is not a width; and text that wraps for the first time inherits every multi-line default the widget was hiding. | 0.81.202 |
| [The seven small rows, four of which were not what they said](#the-seven-small-rows-four-of-which-were-not-what-they-said) | A suggested fix is a hypothesis about the code — four of seven were wrong about scope, premise or mechanism, each found by a grep; and a check asserting `not in` against a name the code would never write cannot fail. | 0.76.192 |
| [The guard that knew half the vocabulary](#the-guard-that-knew-half-the-vocabulary) | Before persisting a value, read what the app already does to it at runtime — a stored preference inherits every rule the live one has, including the wrong ones; and a guard written against one kind of value governs every kind sharing the variable. | 0.76.198 |
| [The template editor that "did nothing" when clicked](#the-template-editor-that-did-nothing-when-clicked) | 'Nothing happens' in a --windowed build is a real bug report — the exception was invisible. | 0.3.0 |
| [The panel that lost its content depending on how you got there](#the-panel-that-lost-its-content-depending-on-how-you-got-there) | Recalculate layout on Tk's `<Map>` event, not after a guessed delay. | 0.3.0 |
| [The scroll that stopped twice, for two different reasons](#the-scroll-that-stopped-twice-for-two-different-reasons) | Same symptom, unrelated causes — check neighbouring areas instead of assuming one fix covers all. | 0.28.38 |
| [The chip that looked clickable, and the fix that looked like it worked](#the-chip-that-looked-clickable-and-the-fix-that-looked-like-it-worked) | Tk doesn't update winfo_ismapped synchronously; when the work is cheap, skip the visibility optimization. | 0.28.38 |
| [The DPI fix that made things worse](#the-dpi-fix-that-made-things-worse) | An unverifiable fix is a gamble — flag the uncertainty up front, revert without shame. | 0.30.38 |
| [The module that existed twice](#the-module-that-existed-twice) | 'All tests pass' only reassures if the suite can represent the failing case. | 0.32.51 |
| [The bullet that had no bullet in it](#the-bullet-that-had-no-bullet-in-it) | Text inserted between same-tagged characters inherits the tag; content, not presentation tags, decides state. | 0.34.51 |
| [The text box that was always eighty characters wide](#the-text-box-that-was-always-eighty-characters-wide) | When a check passes, ask what it would take to make it fail. | 0.38.59 |
| [The list that lost its place, twice, for two silent reasons](#the-list-that-lost-its-place-twice-for-two-silent-reasons) | 'Hard to reproduce' means unmeasured timing; instrument what the widget experiences until it's deterministic. | 0.58.82 |
| [The click that was never delivered](#the-click-that-was-never-delivered) | Tk discards a generated event aimed at a widget with no native window, in silence — and `winfo_ismapped`/`winfo_viewable` do not predict delivery. | 0.71.154 |
| [The safety net that could not see the gap](#the-safety-net-that-could-not-see-the-gap) | A gate tuned to the instances it already found certifies the ones it cannot see — worse than no gate, because the next reader trusts it. | 0.71.154 |
| [The same net, woven again](#the-same-net-woven-again--and-the-question-it-was-answering) | A wordlist answers "are any of MY words here", not "is this English" — when a check's method can only answer a narrower question than its promise, say so where the promise is made. | — |
| [The check that pinned the behaviour a release had deliberately replaced](#the-check-that-pinned-the-behaviour-a-release-had-deliberately-replaced) | When a feature changes what the app promises, the checks asserting the old promise are part of the change — and a suite that cannot run a check cannot tell you it is wrong. | — |
| [A calendar that kept navigating behind the user's back](#a-calendar-that-kept-navigating-behind-the-users-back) | Changing how a page becomes visible invalidates 'is X visible' assumptions in unrelated code. | 0.5.0 |
| [The date field that either lost your edit, or wouldn't let you finish typing it](#the-date-field-that-either-lost-your-edit-or-wouldnt-let-you-finish-typing-it) | Reusing Save's validation in silent autosave turns a helpful warning into an interruption. | 0.28.38 |
| [The autosave that could interrupt you over a note that was already gone](#the-autosave-that-could-interrupt-you-over-a-note-that-was-already-gone) | A guard added to one path doesn't cover other routes into the same code. | 0.28.38 |
| [The autosave that asked questions](#the-autosave-that-asked-questions) | A background timer must never ask the user anything; dialogs happen at gestures. | 0.66.102 |
| [The username cap that took three tries](#the-username-cap-that-took-three-tries) | Never trust one validation mechanism against fast input — layer cheap redundant checks. | 0.28.38 |
| [The focus fix that broke the thing it wasn't touching](#the-focus-fix-that-broke-the-thing-it-wasnt-touching) | A fix scoped to the reported widgets can break already-working behaviour; re-test the working case. | 0.28.38 |
| [The fast-typing fix that took three tries to land safely](#the-fast-typing-fix-that-took-three-tries-to-land-safely) | Decide from what the widget contains, not event internals; boring-safe beats precise-dangerous. | 0.31.39 |
| [The paste that kept the formatting it was told to drop](#the-paste-that-kept-the-formatting-it-was-told-to-drop) | Clipboard 'plain text' isn't plain — strip whatever the app itself would read as markers. | 0.37.56 |
| [The paragraphs a PDF does not have](#the-paragraphs-a-pdf-does-not-have) | A paragraph almost never stops mid-sentence; punctuation beats width arithmetic for rejoining broken lines. | 0.38.59 |
| [The rebuild under the click](#the-rebuild-under-the-click) | Re-anchor gestures by what survives a rebuild — a line number, never a widget reference. | 0.39.63 |
| [The centring that would not save itself](#the-centring-that-would-not-save-itself) | A comparison that lists fields silently exempts whatever field is added next. | 0.39.63 |
| [The accepted cost that nobody had accepted](#the-accepted-cost-that-nobody-had-accepted) | When a docstring says 'accepted cost', check who pays it, and for what. | 0.64.95 |
| [The undo that stopped halfway](#the-undo-that-stopped-halfway) | Burst edits owe undo a boundary, redraws owe it silence; probe what Tk records. | 0.64.95 |
| [The undo that stopped halfway, the sequel](#the-undo-that-stopped-halfway-the-sequel-lists-and-the-grid-trio) | When a fix has a sibling family, audit which siblings were missed; a "drawn?" check reads real windows, not a stale dict. | 0.71.116 |
| [The table that outlived its own deletion](#the-table-that-outlived-its-own-deletion) | A cached handle to a drawn thing must prove the drawing still exists — Tk marks survive the delete that killed the widgets. | 0.71.125 |
| [The clipping that turned out to be a feature](#the-clipping-that-turned-out-to-be-a-feature) | Before fixing "wrong" behaviour, find who relies on it; the fix moved from render to parse once the ellipsis check spoke up. | 0.71.134 |
| [The Trash panel that took two seconds to open](#the-trash-panel-that-took-two-seconds-to-open) | Don't build and wire every row up front; render a page, reveal more on demand. | 0.4.0 |
| [The slowdown that only showed up after a long session](#the-slowdown-that-only-showed-up-after-a-long-session) | 'Slow after a while, fine at first' means unbounded growth; reproduce with a loop. | 0.4.0 |
| [Export/import freezing the app](#exportimport-freezing-the-app) | Do file I/O on a worker thread; only the main thread touches Tkinter widgets. | 0.4.0 |
| [The theme-switch flicker, and three ways not to fix it](#the-theme-switch-flicker-and-three-ways-not-to-fix-it) | Profile before reaching for rendering tricks; the fix was stopping work nothing asked for. | 0.32.49 |
| [The Settings panels that stayed dark on a light theme](#the-settings-panels-that-stayed-dark-on-a-light-theme) | A computed colour is invisible to palette matching; derive it once, teach the theme switch. | 0.36.54 |
| [The title box that took three and a half seconds a keystroke](#the-title-box-that-took-three-and-a-half-seconds-a-keystroke) | Measure to isolate: the app was fine, one widget was quadratic — cap its input. | 0.36.55 |
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
| [The width that was guessed](#the-width-that-was-guessed) | A layout number that must agree with a layout it cannot see is wrong the first time either changes — ask the widget; and when a measurement disagrees with a photograph, doubt the measurement. | 0.73.167 |
| [The rebuild nobody was looking at](#the-rebuild-nobody-was-looking-at) | When a new feature makes the user look somewhere new, expect a report about something that was always wrong there — measure before blaming the newest change; and a guard applied at one call site out of thirty-one is a comment, not a guard. | 0.74.169 |
| [The sentence that counted notes](#the-sentence-that-counted-notes) | When a dialog counts things, ask what one of those things can be — a repeating series is one note in the count and every occurrence in the consequence; and a guard that has only ever been asked well-formed questions has been lucky, not tested. | 0.74.170 |
| [Two ways to be invisible](#two-ways-to-be-invisible) | A layout whose last element absorbs every shortfall reports nothing and fails last — measure asked-for against given, on every font it will meet; and a fixture that does not do what its name says turns a measurement into a rumour. | 0.74.172 |
| [The rule the app already had](#the-rule-the-app-already-had) | When two screens disagree, do not pick one — ask what the rest of the app does and make the odd one out match; and read what a gesture really offers before calling it a duplicate. | 0.75.174 |


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

**Symptom:** After rebuilding and testing the `.exe`, the notes it showed were completely different from — and far fewer than — the notes visible when running `python note_organizer.py` from the project folder. It looked as if the `.exe`'s notebook had simply reset itself.

**Root cause:** Two pieces of migration logic, both run automatically at import time (`MIGRATION_INFO = run_migrations(APP_DIR)` / `PURGED_DIRS = purge_stale_copies(APP_DIR)`), combined into a real data-loss bug. `run_migrations()`'s job is to pull old notes forward from `%APPDATA%\NoteOrganizer` into whatever directory the app is currently running from in script mode (dev checkout, or literally any script that does `import note_organizer`) — reasonable on its own, and non-destructive, since it only *copies*. But `purge_stale_copies()` then runs right after, looking for "redundant leftover copies" to clean up — and the AppData folder it just copied *from* now looks perfectly redundant, since every note in it also exists in the copy that was just made. So it got deleted: `notes_data.json`, `settings.json`, and the whole `attachments/` folder, gone. This could be triggered by nothing more than running one of the project's own headless test scripts (`test_calculator.py`, `test_recurrence.py`, `test_data_safety.py`) from a fresh scratch directory — exactly the practice `CLAUDE.md`'s QA safety rule requires — since a brand-new directory never has the `reclaimed_from_appdata` flag that would otherwise skip the reclaim.

**Fix:** `purge_stale_copies()` now permanently exempts `%APPDATA%\NoteOrganizer` from deletion, full stop — no redundancy check ever applies to it. It's the durable, cross-run store the distributed `.exe` actually reads from, never a disposable leftover, regardless of what directory happens to be running the code. Genuinely stale, non-AppData leftovers (like an old `dist\` copy from a previous build layout) are still cleaned up exactly as before — verified with a dedicated regression test alongside the ones proving AppData now survives even a maximally "redundant-looking" scenario.

**Recovery:** the real notes weren't actually gone — they'd been copied into a directory before AppData was cleared. In this case a plain `python note_organizer.py` run at the project root held an intact copy, which was restored back into AppData by hand (a direct file copy, deliberately not routed through any app code, to stay isolated from the very bug being fixed).

**Follow-up (0.33.x):** the deeper cause — that any `import note_organizer` performed migrations at all — is now gone. Resolving the data folder, migrating, purging and writing settings moved into an explicit `initialise()`, called by `NoteOrganizer.__init__` and by `_main()`. Importing the module creates no files and touches no notes, verified by importing it into a directory holding a decoy notebook and confirming nothing was read, moved or deleted. The exemption below still stands as defence in depth; it is no longer the only thing standing between a stray import and someone's notes.

**Takeaway:** "Copy it somewhere else, then delete the original because it's now redundant" is a dangerous pattern to apply to anything that's a *permanent* store rather than a genuinely disposable one — the logic has no way to tell those apart from the data alone. A cleanup routine should name its exemptions explicitly (as this fix now does) rather than relying on every possible caller happening to avoid the deletion condition. Also worth remembering: a safety practice designed to protect data from one specific script (`qa*.py`'s working-directory wipe) doesn't automatically protect against a completely different destructive path living inside the very code being tested.

### The safety test that needed its own safety

*([0.39.63](../CHANGELOG.md#03963--2026-08-28) · 2026-08-27)*

**Symptom:** The app, launched from the project root, opened onto an empty
notebook. `notes_data.json` held two bytes — `[]` — and `settings.json` had
been reset to defaults. The trash, templates and attachments were untouched.

**Root cause:** `test_data_safety.py` exercises the backup/migration layer,
so unlike the other unit tests it deletes and rewrites `notes_data.json` in
its own directory (`os.remove(NO.DATA_FILE)` near the top, fixtures after).
Its docstring says plainly that it must be run from a throwaway copy — but
during a routine pre-commit sweep the whole unit suite was run from the
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

**Symptom:** A static gate was written specifically so that one class of
omission — a question the app asks in several places, answered by a
hand-rolled field list at each one — "cannot come back quietly". It
reported the codebase clean. A review wave, running at the same time,
found a live instance of exactly that class: the share-as-code guard,
refusing a checklist-only note the app had just saved as real content.

**Root cause:** the gate's pattern required THREE content-field names in
the same window of lines, because the three instances that prompted it
all had at least three. The share guard enumerated two. A net woven from
the shape of what it had already caught was blind, by construction, to
the *under-inclusive* guards — which are precisely the ones that lose
data, since an over-inclusive guard merely asks an unnecessary question.

**Fix:** the threshold is two, and the reason is written above the
pattern rather than left implicit. With it widened, the gate found the
share guard in its first second — the same defect a 9.9-million-token
review wave had reported, for the cost of a grep.

**Takeaway:** a detector built from the examples you already have will
match the examples you already have. Ask what a WEAKER instance of the
class would look like and make sure the pattern still catches it —
before the clean report starts being used as evidence. And a gate that
reports clean over a known-live instance is not merely incomplete: it
actively certifies the gap, and the next reader believes it.

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
[consistency survey](PRODUCT_FINDINGS.md#round-2--the-consistency-survey-2026-09-25).

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

### The DPI fix that made things worse

*([0.30.38](../CHANGELOG.md#03038--2026-08-18) · 2026-08-18)*

**Symptom:** Two side-by-side sections in the note editor (Checklist and Calculator), built with `grid()` and a shared `uniform` group specifically to force equal column widths, still rendered visibly unequal in a real screenshot from the user — despite `winfo_width()` proving both columns were pixel-identical inside Tk's own geometry math, on every window size and maximize state tested locally.

**Root cause:** The app was never declared DPI-aware, so on a display scaled above 100% (125%/150%, the user's actual setup) Windows renders the whole window at 100% internally and then stretches the finished bitmap to match the scaling factor — a blunt, whole-window operation that can apply inconsistently across nested widget hierarchies. Tk's own layout math was correct the entire time; the mismatch was introduced afterward, by the OS.

**Fix attempted:** Declared the process DPI-aware (`SetProcessDpiAwareness`, with a `SetProcessDPIAware` fallback for older Windows) and told Tk to scale its own font/spacing math to match (`tk scaling`) — the standard fix for this class of problem. Couldn't be verified visually in the development environment, since it isn't running at 125%/150% scaling, so it shipped for the user to test on the real machine that reported the bug, with that limitation flagged up front.

**Reverted:** On the actual 150%-scaled machine, the fix didn't resolve the column mismatch, and made the app's overall rendering visibly blurrier. Reverted in full rather than trading one visible cosmetic problem for a worse one.

**Takeaway:** A fix that's well-understood in theory and impossible to verify locally is still a gamble — flagging that uncertainty explicitly up front made the revert a quick, low-friction call once real-machine testing disagreed, instead of a surprise. Sometimes the right outcome is to leave a minor cosmetic issue unresolved rather than layer an unverifiable fix on top of it.

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
where the glued query — `Search all calendar entries...bugetul` — matched
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
underneath) is tracked separately as hardening.

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
table cell from `1` to `schimbat`, press Ctrl+Z once, and the cell
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

**Fix:** titles are capped at 200 characters — far past any real title, far short of where the widget struggles, and well above the 60 the note list displays.

**Two things that needed care.** A validator can only accept or refuse a change *whole*, so pasting something longer left the field empty, which reads as the paste having failed rather than having been shortened; pasting now trims to fit. And validation fires on programmatic inserts as well as on typing — so without a guard, opening a note written before the cap would have had the widget silently drop the overflow, and the next autosave would have written that shortened title back over the real one. Loading a note must never edit it.

**Why the body is fine:** it is a `tk.Text`, which stays near-linear — a million characters costs 363ms a keystroke against `tk.Entry`'s three and a half seconds at a tenth of the size. Someone can write a book in one note; measured at 1M characters, typing is 14ms and saving 377ms.

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

Two reports, one strip of sidebar, and two different ways for a thing to
be on screen and not be seen.

**The word against the edge.** "Export is very cramped, you can barely
see the whole word." The bar laid five controls in one line across a
sidebar of fixed width, and the packer hands out that width in order:
each control takes what it asks for and the LAST one lives on the
remainder. So everything before it is drawn perfectly and the failure
lands entirely on whoever is last — which is why nothing looks wrong
until the end of the row.

Measured: Export asked 40px and was drawn at 27. Everything else got
exactly what it asked for.

The comment being replaced had recorded the same fight, won by one pixel:
*"four controls need 281px and the sidebar is a fixed 280 — the emoji
alone is the overflow."* A layout that fits by one pixel is one font away
from not fitting, and this one had already lost that bet somewhere nobody
had looked: on the Linux CI image, where DejaVu is wider, the same four
asked **338px of the 250 available and Export was drawn at one pixel**.
It had been that broken there the whole time.

So the fix is not a smaller font, which would just move the margin. The
count went to its own line and the four actions went two by two, which
changes what has to be TRUE: the widest row now needs the two widest
labels side by side — 180px on Linux, 105 on Windows — instead of all
four. Room to spare on both, rather than a margin waiting for the next
label.

**The tick that was the same colour as its box.** "The tick boxes are
almost invisible in dark mode, being black. Maybe we can lighten the
squares, so the black tick shows better in them."

She was right, and the first attempt at it was wrong in a way worth
writing down.

The photograph taken to study it showed every box empty — because the
script had called `_toggle_note_selected`, which updates the set of
selected ids, rather than invoking the widget, which is what moves a
checkbox. **The fixture ticked nothing.** On that picture a whole
diagnosis was built: pixel measurements, a table of candidate colours, a
conclusion of "use the accent", and a change to twelve call sites.

Ticking the boxes properly showed the accent making an EMPTY box look
filled — worse than before. The change was reverted whole, and she was
asked for a screenshot of her own machine instead. Hers showed what the
report said all along: a ticked box dark, with a dark mark in it, barely
distinguishable from an empty one.

The mechanism, once the picture was honest: `selectcolor` is the well a
check mark sits in, and every one of them in this app was set to `card`
or `sidebar` — the very surface the box is drawn on. Tk draws the mark
dark on Windows whatever the palette says. Dark mark, dark well.

Light themes never showed it, because their card already is white. That
is the trap that kept it alive: the well has to be light because the MARK
is dark, not because the theme is one thing or the other. It is a named
palette entry now, `check_well`, light in all eight, so a future theme
disagrees in one place instead of twelve.

**Takeaway:** a layout whose last element absorbs every shortfall reports
nothing and fails last, so measure what it ASKS against what it is GIVEN,
on every font it will meet. And a fixture that does not do what its name
says turns a measurement into a rumour — the tick boxes cost a full wrong
diagnosis, and the only reason it shipped nothing was a screenshot asked
for before the commit.

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
first-run migration, which executes at `import note_organizer` time,
helpfully adopted the developer's REAL notebook from
`%APPDATA%\NoteOrganizer` into every test run. The checks were being
graded against whatever the owner had done in her app that day; the
morning failure appeared because she had field-tested the `.exe` the
evening before, changing the very data the tests were unknowingly
inheriting.

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

**The fix was the easy half.** Shortening the Trash retention window
destroyed everything the new window had already outlived, at the next
startup, with no dialog. Ten mutants were written for the ten mechanisms
behind the fix. Four survived, and every one of them was right to.

**Four checks satisfied by coincidence.** None was wrong about what it
asserted; each was simply also true when the mechanism was broken.

1. The lengthening fixture used a note deleted 40 days ago and lengthened
   the window to 90. Removing the "is this shorter?" test changed nothing,
   because 40 days is *inside* a 90-day window — the doomed list was empty
   either way, so the test never had to hold. The fixture now uses a note
   older than every window the dropdown offers, the only shape where
   lengthening has something already expired and the test therefore
   matters.
2. The clamp check compared a previewed window of 0 days against 1, on a
   note deleted a day ago. A day-old note sits exactly on that boundary
   and reads as expired under both, so unclamping changed neither side.
   Twelve hours tells them apart.
3. The ceiling check compared 10000 days against the 365-day clamp on a
   40-day-old note: inside both, zero twice. It needed a note older than
   the ceiling itself.
4. The "counts only what would go" check asserted the number 1. Inverting
   the window comparison also yields 1 — the other note. A count is
   satisfied by the wrong answer whenever the wrong answer is the same
   size, so the check now names *which* entry.

**And two of the four had not survived at all.** After the first three
were repaired, two mutants still read as survivors with no explanation.
`tools/run_tests.py` prints the first eight failing checks; those mutants
broke nine and fourteen, so the names the runner was searching for were
never printed. The checks had fired. The verdict was the tool's.

That is the more dangerous of the two lessons, because it inverts the
sign: a mutation runner exists to say "this check has teeth", and a
silently truncated list makes it say the opposite of the truth. The runner
now asks for `--all-failures`, refuses to trust a list it can see was cut,
and `run_tests.py` says "… and N more" when it cuts one.

**The lessons.**

1. A check that asserts a *count* is satisfied by any wrong answer of the
   same size. Assert which, not how many, wherever identity is the point.
2. A fixture chosen to look realistic is often chosen to sit inside every
   boundary at once. Pick the value that can only be explained one way —
   twelve hours, not one day; four hundred days, not forty.
3. Never read a verdict out of output that can be truncated without saying
   so. A tool that can be quietly wrong about whether a check works is
   worse than no tool.
4. Four of ten checks were satisfied by coincidence, and every one of them
   passed against the real code. Mutation testing is not a formality that
   confirms good checks; it is the only thing that finds this class at all.

### The finding that described a dialog nobody had opened

*(no version — the label change it produced is `Changed`, and the version
counts `Added` and `Fixed` alone)*

**Three findings in a row, and each one's reasoning was wrong.** The
consistency survey recorded 25 asymmetries by reading the source. Working
through its destructive rows in order, the first three all held as
*findings* and all three were wrong about *why*:

- **C-2** said the checklist item was the worse of the pair because the
  attachment beside it is one "the file system still remembers".
  `remove_attachment` deletes the stored copy. The comparison survived;
  its reason did not, and the reason was what pointed at the wrong fix —
  a dialog, where the answer was an undo.
- **C-3** described the retention dropdown as destroying notes. It also
  deletes their attached files from disk, which no sentence on that screen
  had ever mentioned, and which the new confirmation now names.
- **C-4** said a day row's Delete "removes only that day", with nothing
  but the row you aimed at to distinguish it from deleting the series. It
  raises a three-button question naming the day. Two more of its claims
  were false: Enter answering the dialog, which no dialog on this Tk
  accepts and which the same register records as T3-1 two sections above;
  and a series being lost, when it goes to the Trash with an Undo.

**One cause, admitted in advance.** The survey's own coverage confession
said no reader ran the app. Everything above is what that produces: the
code says `if is_recurring(note) and occurrence_date:` and the reader
follows the branch, but the *dialog inside it* is a call to a function two
files away whose three buttons nobody saw. Reading gets the control flow
right and the experience wrong, and a finding is a claim about the
experience.

**What the pattern is worth keeping for.** The survey was still the most
productive thing in the cycle: C-1 was real and serious, C-2 and C-3 were
real with the wrong reasons attached, and C-4's label was worth changing.
A review that reads is cheap and finds where to look. It just cannot be
the thing that decides, and the corrections belong in the register beside
the claims rather than replacing them — otherwise the next reader inherits
the confidence without the correction.

**The lessons.**

1. A finding is a claim about what a person meets. Confirm it by meeting
   it: drive the real route and record which dialogs actually appear.
2. Where a finding gives a reason, check the reason separately from the
   finding. Three times running, the finding survived and the reason did
   not — and the reason is what chooses the fix.
3. A refuted finding is corrected in place, struck through rather than
   deleted, with the measurement beside it. A register that quietly loses
   its wrong rows teaches nothing about how it got them wrong.
4. Cross-check a new finding against the register's own older rows. C-4's
   "Yes ready for Enter" was contradicted by T3-1, already recorded on the
   same page.

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

The consistency survey's cheapest seven — a search box with no paste menu,
a box that forgot its size, two different plus signs — were picked precisely
because each looked like one or two lines. The pre-flight that runs before
any fix here changed the shape of **four of the seven** before a line was
written, and that is the whole point of the story: the cheap batch was where
it paid off most, because nobody was looking hard at it.

**C-11 grew a constant.** The row asked for `_add_paste_menu(search_entry)`
and an ✕. The ✕ needs to know whether the box holds a real query or only its
grey hint — and that judgement was already written out **three times**: once
where the box is built, and twice, lowercased, inside the two functions that
read the query (`if query == "search notes...": query = ""`). Nothing
connected them, so rewording the hint would have left the app quietly
filtering every list by it. The ✕ would have been a fourth. There is one
`SEARCH_PLACEHOLDER` and one `_search_query()` now. The gate that polices
this class, `tools/check_one_definition.py`, says of itself that it gains a
rule when a duplicate costs the project something; this one had not, so it
was consolidated without adding one.

**C-12 grew from one field to six, and from a menu to a save.** The row said
"the date entry at minimum; the recurrence number boxes are a weaker case,
since they hold single digits". There are four Repeat boxes, and two are not
digits: the end-date is a date, the same shape as the field the row *did*
want fixed, and the day list holds "1,15". They are also free, because each
one's variable traces to `update_recurrence_summary`, which schedules the
autosave. The date field is **not** free: it autosaves on `<KeyRelease>`
alone, and a paste fires none — measured, a pasted date scheduled no save
while a typed character did. That is the silent loss the field's own comment
says was repaired once for typing, and the new menu would have re-opened it
on a new route. The check is now an invariant over the whole editor rather
than a list of four fields, so the next box added without a menu fails it.

**C-19's premise was different from the row's.** The row offered two
branches: persist it, or say in a comment that the omission is deliberate.
The code had something in between — a line at the **body's** call site
noting that the comments box did not remember. That states the difference
without giving a reason, so the row's condition was never met.

**C-24 needed a different mechanism from its twin, and hid a third
divergence.** The row asked for one sentence and an ✕ "to match the
editor's". The editor's ✕ calls `pack_forget()` on its own area; the
sidebar's frame is packed once when the Share panel is built and is part of
that panel's layout, so forgetting it would take the panel's space with it —
it clears the frame's children instead. And the two surfaces disagreed in a
**third** way the row never mentioned: their titles ("Code for 3 notes (412
chars)" against "Share code (412 characters)"). Left alone deliberately: the
sidebar's note count is information the editor cannot carry, and its "chars"
is a width accommodation in the 250px panel this project has already lost
time to clipping fights over.

**Two checks were wrong in instructive ways, and mutants found both.**

A new one asserted the date reached the store *after calling
`_flush_autosave()`* — a forcing call, which saves whatever the editor holds
whether anything asked it to. It survived the mutant that removed the paste's
save binding outright. That rule was already written down in `qa/README`,
six rules above where the same mistake was made.

An **old** one could never have failed:
`check('the comments box is deliberately not persisted', 'comments_expanded'
not in load_settings())`. The key the helper would write is
`editor_comments_expanded`; `comments_expanded` was never a candidate, so the
check asserted the absence of a name nothing would ever create. It stayed
green through the change that made the box persist, which is how it was
found — by a change that should have broken it, not by anyone reading it.

**And one platform difference, caught by the Linux image and not by
Windows:** Tk's Entry paste deletes the selected text only on non-X11. A
check that selected a field's contents and pasted over them passed here and
failed there with the field holding both values. The app ships on Windows, so
that is the test's problem rather than the product's — but it is the third
time the Linux image has found something invisible on Windows.

**The lessons.**

1. A row's own suggested fix is a hypothesis about the code, and it is
   cheaper to check than to unpick. Four of seven were wrong about scope,
   premise or mechanism, and every one of those was found by a grep.
2. Where a new reader of a judgement is being added, count the existing
   readers first. The fourth copy is the one that makes the first three a
   bug.
3. A check about an absence has to name the thing that would actually be
   there. Asserting `not in` against a name the code would never write is a
   check that cannot fail.
4. Reading a rule is not following it. The forcing-call mistake was made
   again on the same page it is documented on, so the mutant is what caught
   it — which is the argument for running mutants on checks that look
   obviously right.
