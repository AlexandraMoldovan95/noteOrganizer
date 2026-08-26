# Notable Issues Log

A narrative log of the more interesting bugs found and fixed during development — chosen because each one taught something worth remembering, not because they were the only bugs. Routine fixes are just commits; these are the ones with a real "why did this happen" behind them. See also the repository's [Issues](../../issues) for day-to-day tracking.

---

### The text box that was always eighty characters wide

**Symptom:** pasted text used only about half the width of the note, and deleting a character further down did not make it reflow into the space. It behaved as though the box were half its apparent size.

**Root cause:** it was. The Expand toggle added for the writing area called `pack_configure(expand=False)` on the box it was given, meaning to stop it filling the available space so the row count would govern its height. Both text boxes are packed with `side="left"`, where `expand` hands out *horizontal* space — vertical space is the container's to give. So the call never affected the height it was written for, and left each box at a Text widget's default width of eighty characters inside a much wider frame. Measured: 752px of 1027px for the body, 672px for comments.

**What it was *not*:** the paste. Every paste path showed it, because the box was narrow before anything was pasted into it.

**Fix:** delete the line. The height is governed by the frame around the box, which sizes itself to what the box asks for, so nothing was lost.

**Two checks that could not have caught it.** The first measured whether the text ran the full width of the box — but text always fills the box it is given; with the bug it filled a 752px box perfectly well. The second compared the box against its frame, which is the right comparison, but a Text widget's default eighty characters is about 700px and the frame in that test happened to be 727px, so it passed anyway. What does catch it is the invariant behind the measurement: a box packed `side="left"` without `expand` cannot fill its frame at *any* window size.

**Takeaway:** when a check passes, ask what it would take to make it fail. Both of these were written to guard a specific bug, and neither would have.

### The paragraphs a PDF does not have

**Symptom:** text copied from a PDF arrived either as one run-on block (**Ctrl+V**) or as narrow ragged lines a third of the way across the note (**Ctrl+Shift+V**). Numbering it then put a number on every line, including mid-sentence.

**Root cause:** a PDF has no paragraphs. It has lines placed on a page, and copying from one hands those line breaks over as though they were meant. Both behaviours followed from that honestly: the plain path kept every break, and the HTML path dropped them all, because HTML says a newline in text is whitespace — true for a web page, whose markup is laid out for a human to read, and false for a fragment carrying no block tag at all, which is what a PDF viewer offers.

**Fix:** keep those breaks when the fragment has no block structure, then rejoin the lines a column broke.

**Three heuristics, two of them wrong.** The first used width-relative thresholds — a line reaching 90% of the widest was "full" — and got 60-column text wrong in one direction and 110-column wrong in the other. The second asked the right question, *would the next line's first word have fitted here?*, which needs no threshold tuned to a width; but the column is never narrower than the longest line seen and usually a little wider, so a near-miss read as a deliberate ending and split paragraphs in half. The third added two characters of slack for that decision — and only for that decision, since allowing it when deciding whether the text is a column at all made three short paragraphs look like wrapped prose and merged them.

**And the signal that was missing from all three.** A paragraph almost never stops in the middle of a sentence. A line ending in no punctuation at all was broken by the column, whatever the arithmetic says — unless it falls well short of the column, which is a heading or a last line however it ends.

**Tested by property, not by result.** Which widths happen to come out exactly right is not the point and invites tuning the test until it passes, which this project has done once before and regretted. What is asserted instead, at eight widths, indented and not: no word is ever lost or altered, and no paragraph is ever split in two. Merging two paragraphs is possible — without indentation, a paragraph whose last line lands nearly full cannot be told from a line the column broke — and that limit is asserted rather than hidden, because losing a break is survivable and cutting a sentence in half is not.

**One check written during the fix passed without testing anything.** A three-line fixture meant to prove a heading keeps its own line was never recognised as a column in the first place, so it never reached the code it was guarding. Deleting that code changed nothing. It was found by deliberately breaking the code and noticing that nothing failed.

---

### The paste that kept the formatting it was told to drop

**Symptom:** "paste without formatting" pasted a bullet list. Both choices did the same thing, which made it look like the wrong function was wired to the shortcut.

**Root cause:** nothing in the paste code. When you copy a list, the source puts it on the clipboard twice — once as HTML, once as its own plain-text version — and that plain-text version has real bullet characters in it. Everything worked exactly as written; the "plain text" simply was not plain.

**Why it hit this app in particular:** here a marker in the text *is* what makes a line a list. A bullet is not a property of the line, it is the two characters `"• "` at the start of it, because the character offsets in `formatting` have to index that same body text. So pasting the source's plain text verbatim did not merely show bullet characters — it built genuine, indented list paragraphs out of them.

**What pointed at it:** the same paste from a source that sends no bullets was already correct. That ruled out the paste path and left the clipboard.

**Fix:** plain paste strips what the app itself would read as a marker — the three bullet glyphs and a numbered prefix, with the indentation in front of them. A line starting `- ` keeps its characters, since those never made a list here anyway.

**The cost, accepted deliberately:** any number followed by a dot and a space starts a numbered item in this app, so `2026. was a year` loses its year. The stripper matches what the editor does with that line rather than being cleverer than it. A gentler rule would paste text that looked plain and came back as a list the next time the note was opened, which is worse than being consistent.

### The title box that took three and a half seconds a keystroke

**Symptom:** none, until someone pasted something long into a note's title. Then the title field stopped responding — and because the only way to fix a title is to edit it, there was no way back out.

**Root cause:** `tk.Entry` slows roughly with the square of what it holds. Measured on a bare widget with no bindings and no app around it: 0.5ms a keystroke at 30 characters, 38ms at 10,000, 892ms at 50,000, and 3,535ms at 100,000. Nothing in this codebase was involved.

**What it was *not*:** the question that prompted the measurement was whether a long title slows the app down. It does not. Twenty notes with million-character titles make a 19MB file that still loads in 50ms, the note list costs the same as with ordinary titles, and searching them takes 1ms. The app was never the problem; one widget was.

**Fix:** titles are capped at 200 characters — far past any real title, far short of where the widget struggles, and well above the 60 the note list displays.

**Two things that needed care.** A validator can only accept or refuse a change *whole*, so pasting something longer left the field empty, which reads as the paste having failed rather than having been shortened; pasting now trims to fit. And validation fires on programmatic inserts as well as on typing — so without a guard, opening a note written before the cap would have had the widget silently drop the overflow, and the next autosave would have written that shortened title back over the real one. Loading a note must never edit it.

**Why the body is fine:** it is a `tk.Text`, which stays near-linear — a million characters costs 363ms a keystroke against `tk.Entry`'s three and a half seconds at a tenth of the size. Someone can write a book in one note; measured at 1M characters, typing is 14ms and saving 377ms.

---

### The Settings panels that stayed dark on a light theme

**Symptom:** switching to a light theme left the information bars in Settings → General, Backup and About dark, with their text almost unreadable against it.

**Root cause:** `_recolor_stragglers()` fixes any widget still holding a colour from another theme by remapping that theme's palette entries onto the current one's. Settings does not use only palette entries: it *derives* two surfaces by blending — `card` toward `text` for the well inside a card, `card` toward `subtext` for its hairlines. Neither result is in any theme's palette, so the remap could not see them, and a panel built once under a dark theme kept the dark inset for the rest of the session. Measured: 19 widgets across those three panels.

**Fix:** the two derivations moved to `core/themes.py` as `inset_surface()` and `hairline()`, so Settings and the straggler pass share one definition, and the remap now includes each theme's derived surfaces alongside its palette. One change covers all 44 blended call sites rather than touching any of them.

**The rule worth keeping:** a colour that is computed rather than looked up is invisible to anything that works by matching known palette values. Derive it in one place, and teach the theme switch about it there.

---

### A toolbar check that measured the wrong thing, three times

**Symptom:** the formatting toolbar overflowed the editor, so the last group could not be reached without widening the window. Fixed — and then CI failed three times running on the check meant to prove it.

**Root cause, each time the same one:** the check asserted *measured pixel widths*. Pixel widths depend on the font, and CI runs under Xvfb where "Segoe UI" does not exist and Tk substitutes something wider — the same bar measures 577px on the development machine and 827px there. A display at different scaling would diverge the same way.

**Three rounds of it.** First, a width budget against a constant: passed locally, failed on CI. Second, the bar was made to wrap, but a special case meant to keep a divider from starting a row kept it on the row it overflowed instead — reintroducing the overflow the wrap existed to prevent, at widths that depend on the font. Third — the worst one — the swept range was narrowed until the bug fell outside it. That turned CI green while making the check unable to catch the very bug it was written for, which was confirmed afterwards by reintroducing the bug and watching the check pass.

**Fix:** the row splitting moved to `core/formatting.py` as `split_toolbar_rows()`, taking widths as plain numbers. Given widths directly it behaves identically everywhere, so the checks are deterministic on any machine. Writing them immediately found two more faults: an invariant of mine that called a lone oversized control an overflow when there is nowhere narrower to put it, and a real one — the "a divider never opens a row" rule was enforced at the break, so a divider dropped there left an empty row for the *next* divider to open.

**The rule worth keeping:** when a test asserts a number that came from measuring this machine, it is testing this machine. Push the logic somewhere it can be given its inputs, and assert the property instead. See also "Tests that always passed, no matter what".

---

### The bullet that had no bullet in it

**Symptom:** Put the cursor at the end of the last item in a bullet list, paste a couple of lines, and the pasted lines behaved as though they were list items — they were saved that way and came back indented on reload — while showing no bullet at all. Worse, clicking the bullet button on one of them appeared to do nothing: the app thought the line was already a bullet, so the button toggled it *off*.

**Root cause:** A list line carries its marker in the note's text and gets its hanging indent from a Tk tag drawn over it. The tag was applied from the line's start to `line.end+1c` — one character past the end, which is the newline. Tk gives text inserted between two characters that *both* carry a tag that same tag, so anything typed or pasted at that boundary inherited it. The line then had the tag but no marker, and the code decided what was a list item by reading the tag.

**Fix:** Two halves. The tag stops at `line.end` so it no longer covers the newline, and the marker in the text — not the tag — is what decides whether a line is a list item. The tag is presentation only.

**What it cost to get right:** the obvious fix, ending the tag one character earlier, broke the opposite case. Tk's inheritance rule cuts both ways: text typed at the *end* of an item is also between a tagged character and an untagged newline, so it arrived untagged too — and a wrap point in untagged text loses the hanging indent, so a long item's second line slid back under its own marker. Measuring the display lines showed them at the bare left padding instead of the indent. The tag is now rebuilt from the markers as the line is edited, one line at a time on each keystroke rather than the whole body, since rebuilding everything on every keystroke is exactly the kind of refresh work that has cost this app real responsiveness before.

**What made it findable:** mutation testing. Reverting each half of the fix separately showed the suite still passing both times — each half covered for the other in every scenario the tests exercised, so neither was actually pinned down. That produced a third test, which states the rule directly: a stray tag on a line with no marker is not a list item.

---

### The dropdown that opened on the wrong monitor

**Symptom:** On a multi-monitor setup, dropdowns (category picker, sort menu) could pop up on a completely different screen than the app itself.

**Root cause:** Popup positioning was calculated against `winfo_screenwidth()`/`winfo_screenheight()` — the *full virtual desktop* across all monitors — instead of the app's own window bounds. On a wide multi-monitor span, that math could place a popup well outside the monitor the app was actually on.

**Fix:** Rewrote the shared popup-positioning helper to measure against the app window's own `winfo_rootx()`/`winfo_width()` instead, with live tracking so the popup follows if the window is moved or resized while open. Every popup in the app now goes through this one shared function — no positioning logic is reinvented per popup.

---

### The template editor that "did nothing" when clicked

**Symptom:** Clicking Edit on a template appeared to do nothing at all — no window, no error, no console output (the app ships `--windowed`, so any silent exception would be invisible).

**Root cause:** Two, compounding. First, the editor's own window wasn't marked to always stay on top, so it could get pushed *behind* the main window by a focus change — it wasn't broken, it was invisible. Once that was fixed, a second, subtler bug surfaced: the `-topmost` attribute was being set *after* a layout recalculation call (`update_idletasks()`), which silently failed to make it stick, specifically in that order, on the platform being tested on. Reordering it to set `-topmost` immediately, before any layout call, fixed it for good.

**Takeaway:** A `--windowed` build swallows exceptions silently. "Nothing happens" is a legitimate bug report, not a dead end — it usually means something *did* happen, just not where anyone could see it.

---

### The panel that lost its content depending on how you got there

**Symptom:** A Settings panel would intermittently show its content correctly, or not, depending on the exact sequence of panels opened before it — hard to pin down because it wasn't reproducible on the first open, only after certain navigation paths.

**Root cause:** The panel's internal layout math ran once, immediately, using the container's width *at that instant* — but if the container hadn't actually been mapped onto the screen yet (which depends on Tkinter's own internal timing, not application code), that width was unreliable, and the resulting layout could be wrong (chip positions computed for a much narrower container than the real one, effectively invisible or overlapping).

**Fix:** Replaced a guessed fixed delay ("wait roughly this long, then try again") with a `<Map>` event binding — Tkinter's own notification that a widget has just become visible — so the layout recalculates deterministically at the exact right moment, rather than a best-effort timer that occasionally lost the race.

---

### The Trash panel that took two seconds to open

**Symptom:** Opening "Recently deleted" with several hundred entries visibly paused the app.

**Root cause:** The panel built and individually wired up (including recursive mousewheel bindings) a full row of widgets for *every* entry, every time it opened — regardless of how many were actually visible in the scrollable area at once.

**Fix:** Paginated: render the most recent 50 entries, with a "Show more" button to reveal further batches. Cut the time for 600 entries from ~1.8 seconds to roughly 100ms. The same pattern (build-everything-at-once, no cap) turned out to affect the multi-note Share panel too, and got the same fix pre-emptively before it caused a user-visible problem there.

---

### The slowdown that only showed up after a long session

**Symptom:** No single action was slow. The app simply felt progressively heavier the longer a session went on — more saves, more note switches, more sluggish each one felt.

**Root cause:** A theme-tracking system (which lets a later dark/light switch recolor a widget correctly) was registering every widget in frequently-rebuilt UI — note cards, calendar cells, the attachments list — but nothing ever removed the registration for a widget once it was destroyed. Every single note-list refresh (which happens on nearly every save) added new entries to a list that only ever grew, for the entire lifetime of the app.

**Fix:** For content that's destroyed and rebuilt on every refresh, there's no need for live theme-tracking at all — it naturally picks up the current theme colors the next time it's rebuilt anyway (including on a theme switch, since that itself triggers a full rebuild). Switched all frequently-rebuilt UI to plain, untracked color-setting instead. Verified with a test that runs 30 successive refreshes and asserts the tracking-list size doesn't grow.

**Takeaway:** "Slow after a while, fine at first" is close to a defining symptom of an unbounded-growth leak. Reproducing it needs a test that repeats the suspected action many times in a loop, not just once.

---

### Export/import freezing the app

**Symptom:** Exporting a backup with a meaningful number of attachments froze the entire UI — no feedback, just an unresponsive window — until the file finished writing.

**Fix:** Moved the actual file I/O to a background thread, with a strict rule: the worker thread only does file I/O and updates a plain shared dictionary with progress; the main thread is the *only* thing that ever touches a Tkinter widget, reading that dictionary on a timer. Added a live progress bar so waiting is at least visible and bounded, rather than looking identical to a crash.

---

### Importing the same backup twice

**Symptom:** Importing an export `.zip` that overlapped with notes already present silently created duplicates, with no warning.

**Fix:** Both import paths (pasted share-code, and full `.zip` backup) now check each incoming note against what's already there (same matching logic used for duplicate *detection* elsewhere in the app, for consistency) before merging, and ask whether to skip the ones that already exist, import everything anyway, or cancel outright.

---

### A crash handler that would have crashed itself

**Symptom:** Never actually observed in practice — found during an unrelated cleanup pass, not from a bug report.

**Root cause:** The top-level function meant to catch a catastrophic startup failure and show a friendly error dialog referenced `self` — but it's a plain module-level function, outside the app's class, where `self` doesn't exist at all. Had the app ever genuinely failed to start, this fallback path would have thrown its own, unrelated error instead of the intended message.

**Fix:** Switched the fallback to the plain standard-library dialog, which doesn't depend on any of the app's own (possibly-broken) internal state — the right choice specifically *because* this code only runs when something has already gone wrong elsewhere.

**Takeaway:** Error-handling code is easy to leave untested, because the whole point is that it only runs when something else already broke. Worth a deliberate look now and then, not just trusting it because it "looks right."

---

### A backup that assumed it had worked

**Symptom:** Never actually observed in practice — found during a deliberate review of the app's data-safety guarantees, prompted by real (unrelated) data loss during development itself: two separate incidents where a misdirected terminal command wiped the real `notes_data.json` at the project root. Neither incident involved this code path, but they raised the right question: what *else* in this app assumes a backup succeeded without checking?

**Root cause:** When reclaiming notes from `%APPDATA%` back into a local install (one of the migration paths that runs on startup), the app backed up the local file before overwriting it with the AppData copy — but never checked the backup call's return value. A backup that silently failed (disk full, permissions, the file locked by something else) still let the overwrite proceed, with no safety copy of what was about to be replaced. Separately, the app only ever backed up `notes_data.json` before a version upgrade on the very first run ever — a normal upgrade re-reading the same file on every later run had no equivalent snapshot, even though newer code touching old data is exactly the situation a backup is for.

**Fix:** The migration path now aborts and leaves the local file untouched if its own backup fails, instead of proceeding blind. Every detected version upgrade now takes a timestamped backup first, not just the first one — kept forever, since deciding when old backups are no longer needed is the user's call, not the app's.

**Takeaway:** A backup call whose result is never checked isn't a safety net — it's an assumption wearing a safety net's clothes. Worth specifically auditing for elsewhere: any place that calls something named `backup_*` or `_timestamped_backup` should be checked for what happens on that call's *failure* path, not just its success path.

---

### Files that outlived the notes they belonged to

**Symptom:** Attachment files were still sitting in the `attachments/` folder well after the note (or the specific attachment) they belonged to had been deleted — noticed by accident while testing an unrelated change, not from a bug report.

**Root cause:** Every place that removed an attachment or permanently deleted a note (removing a single attachment, deleting a trashed note individually, emptying the trash, and the automatic purge after the retention window) only ever removed the *reference* — the JSON entry pointing at the file — and never the file itself on disk. Four separate code paths, the same gap in every one.

**Fix:** Added one shared helper that deletes the on-disk file for a given attachment reference, and called it from all four permanent-deletion paths. Deliberately *not* called from the soft-delete (move-to-trash) path — a note in trash might still be restored, and deleting its attachment out from under it would make that restoration incomplete. Verified this distinction explicitly with a test: restoring a trashed note with an attachment must leave the file exactly where it was.

**Takeaway:** "Delete the note" and "delete the note forever" are different operations with different safe behavior, even though they can look similar at the call site. Worth naming and testing them as genuinely separate cases, not just one path with an occasional extra step.

---

### Tests that always passed, no matter what

**Symptom:** Not a runtime bug in the app — found while setting up automated test runs (GitHub Actions). Two of the five automated QA scripts were failing when run by hand, but nothing about their own output made that obvious at a glance.

**Root cause:** None of the test scripts actually exited with a failure status code when a check failed — they printed a clear "FAILURES: [...]" line, but then exited normally (status 0) regardless. A human watching the output would notice the failure text; an automated system checking only "did this succeed or fail" would see success every time, even with real failures printed right there in the log.

**Fix:** Every test script now exits with a non-zero status if anything failed. This is what makes automated CI meaningful at all — without it, a broken build would show green forever, and the whole point of automation (finding out immediately, without reading logs by hand) would quietly not work.

**Takeaway:** A test suite's own exit code is part of its interface, not an implementation detail — a script that "looks" like it's testing something isn't actually testing anything from an automated system's point of view unless failure changes what it returns, not just what it prints.

---

### A calendar that kept navigating behind the user's back

**Symptom:** Found while testing the Settings-page restructuring, not reported by a user. If Calendar was the last tab open before switching to the new Settings page, the calendar's own keyboard shortcuts (Page Up/Down, Home) still worked — silently changing the month shown on a calendar the user could no longer see, behind the now-covering Settings page.

**Root cause:** The guard that's supposed to restrict calendar shortcuts to "only when Calendar is actually showing" checked which tab the notebook widget considered internally selected — but Settings became a separate page shown by hiding the notebook entirely, not a third tab. The notebook doesn't lose track of "Calendar was selected" just because something else is now covering it, so the guard's underlying assumption (selected tab == visible tab) quietly stopped holding once Settings could cover the notebook without changing its selection.

**Fix:** The guard now also checks that the notebook widget is actually mapped on screen, not just which tab it last had selected — both conditions have to be true.

**Takeaway:** A restructuring that changes *how* a page becomes visible can invalidate assumptions baked into unrelated code that never mentions the thing being restructured — this guard's code never referenced "Settings" at all, yet still broke because of it. Worth deliberately re-testing behavior that depends on "is X currently visible," specifically, after any change to how visibility is managed anywhere in the app.

---

### The date field that either lost your edit, or wouldn't let you finish typing it

**Symptom:** Typing a date into a note and clicking away (rather than pressing Save) silently didn't save it — the only field in the editor that behaved this way; Title, Body, and Comments all autosaved fine.

**Root cause:** The Date field was simply never wired up to the autosave debounce timer that every other field uses.

**Fix, and a second bug it uncovered:** Adding the missing binding was a one-line fix — but it immediately surfaced a second, subtler issue. Autosave reuses the exact same validation as the manual Save button, which requires a complete, correctly-formatted date. With autosave now firing mid-keystroke, a still-incomplete date (e.g. "2026-1") tripped that validation and popped an "Invalid date" warning that blocked further typing — an automatic, unrequested action interrupting the user is a worse bug than the one being fixed. The fix: keep the warning for an explicit Save click (where the user is done and wants to know something's wrong), but have autosave silently do nothing until the field holds a valid value, instead of complaining.

**Takeaway:** Reusing validation logic between an explicit user action (Save) and a silent background one (autosave) is risky by default — what's a helpful, blocking warning in one context is a disruptive interruption in the other. Worth checking, deliberately, whenever wiring a new field into an existing autosave path.

---

### "Recently updated" sort that couldn't tell recent apart from recent

**Symptom:** Sorting by "Recently updated" didn't always put the note you *just* edited at the top, even though it genuinely had been saved.

**Root cause:** Every note's saved timestamp only tracked minutes, not seconds. Two notes saved within the same minute ended up with the exact same sort value — the sort couldn't tell them apart, so it silently fell back to whatever order they already happened to be in (their original creation order, since editing a note in place doesn't move it within the underlying list), not the order they were actually last touched in.

**Fix:** Added seconds to the timestamp everywhere it gets written. Checked both places that read this field first: one already trimmed to the first 16 characters before parsing (unaffected by the extra length), the other only ever read the first 10 (date only, also unaffected) — so the change was safe to make without touching either reader.

**Takeaway:** A timestamp's precision is part of its contract with anything that sorts or compares it — "close enough for display" and "fine-grained enough to break ties correctly" are two different bars, and a field can quietly fail the second while looking completely normal for the first.

---

### The autosave that could interrupt you over a note that was already gone

**Symptom:** Never reported by a user — found while testing the fix above. An automatic, silent autosave could, in rare timing-dependent cases, pop a real "Note missing" error dialog and block until clicked.

**Root cause:** There are two paths that trigger autosave: switching notes/tabs, and a debounced timer that fires shortly after you stop typing. The first already had a safety check — if the note it's about to save no longer exists, do nothing quietly. The second, timer-driven path was missing that same check, so if it fired after its note had been removed some other way in the meantime, it hit the same "Note missing" dialog a manual Save would show — appropriate for something the user directly asked for, not for something automatic.

**Fix:** Added the same existing guard to the timer-driven path.

**Takeaway:** The same protective check is sometimes needed in more than one place that leads to the same outcome — a fix applied to one path doesn't automatically cover another path that ends up calling the same risky code. Worth asking "is there another way to reach this same code?" whenever adding a guard like this one.

---

### The username cap that took three tries

**Symptom:** Found during manual testing of a planned 30-character cap on the username field. Typing past the limit was still sometimes accepted well beyond 30 characters, and the eventual correction only happened silently when the name was saved — visually indistinguishable from the app just losing whatever was typed past that point.

**Root cause:** The per-keystroke block used Tkinter's standard `validate="key"` mechanism, which has a known real-world reliability gap under very fast or held-down typing — it can miss keystrokes it should have caught.

**Fix:** Layered instead of relying on one mechanism. Kept the per-keystroke validation as a first pass, added an immediate correction on every key release (a plain, more reliable event binding, not the special validate hook with the gap) so an over-length value gets caught within a fraction of a second instead of being left to grow freely, and kept a final save-time truncation as an ultimate backstop regardless of how the value became too long in the first place.

**Takeaway:** Don't trust a single validation mechanism for something a user can trigger arbitrarily fast — independent, redundant layers cost little to add and catch what any one layer alone can miss.

---

### The focus fix that broke the thing it wasn't touching

**Symptom:** Clicking a non-interactive part of the Settings page didn't move keyboard focus away from a field that had it, leaving its cursor blinking even after the value had autosaved. A first attempt at fixing this — binding a click handler individually on every section's title, subtitle, and card — worked inconsistently under rapid clicking, and, worse, broke the "switch tabs and back" case, which had already been working correctly before this fix was ever written.

**Root cause:** Binding the same handler separately on many individual widgets is easy to get inconsistent, and the first fix was only tested against the specific scenario in the bug report (same-page clicks) — not the already-working tab-switch case, so nothing caught the regression before it was noticed by hand.

**Fix:** Replaced the scattered bindings with a single, centralized handler bound once on the whole app — clicks bubble up to the toplevel by default unless something along the way stops them, so one handler reliably catches all of them — scoped narrowly by checking whether Settings is actually visible and whether focus is genuinely on a field that should lose it.

**Takeaway:** A fix scoped to "the exact widgets named in the bug report" can still break unrelated, already-working behavior that happens to depend on the same underlying mechanism. Worth explicitly re-testing the previously-working case, not just the newly-reported one, before considering a fix complete.

---

### The scroll that stopped twice, for two different reasons

**Symptom:** Scrolling the mouse wheel while hovering over the theme picker's preview cards did nothing, instead of scrolling the Settings page underneath.

**Root cause:** Each preview card is a small `Canvas` widget, and Tk's `Canvas` has a built-in default mouse-wheel behavior of its own — it "handles" the scroll itself (even though it has nothing to actually scroll), which stops the event from ever reaching the Settings page's own scrollable area.

**Fix:** Forwarded the wheel event explicitly to the page's own scroll — the exact same pattern already used for every other Settings panel (categories, templates, trash, duplicates), reusing the existing shared helper rather than inventing something new.

**A second bug, found immediately after:** The same symptom — scrolling does nothing — also showed up over the Statistics summary text and its category chips. This turned out to be a *different* root cause wearing the same symptom: those are plain `Frame`/`Label` widgets with no `Canvas` involved at all, simply never wired into the page's scroll-forwarding in the first place, unlike most of the rest of Settings. Fixed with the identical forwarding pattern, applied to the Statistics panel specifically.

**Takeaway:** The same visible symptom can have unrelated causes in different parts of the same page. Confirming a fix in one spot is not evidence the rest of the page is fine — each widget subtree that's supposed to forward scroll needs to actually be wired in, and it's worth deliberately checking neighboring areas with the same symptom rather than assuming one fix covers all of them.

---

### The pixel-perfect test that only worked on Windows

**Symptom:** Three small layout cramps (a cut-off sort label, a cramped bulk-action button, a Settings button that scrolled out of view) were fixed and verified with exact `tkinter.font` pixel measurements — genuinely precise, not eyeballed. The regression test for one of them then failed in CI, even though the fix itself was correct.

**Root cause:** The test asserted an absolute pixel width, measured locally on Windows using the "Segoe UI" font. The CI runner is Linux, which doesn't have "Segoe UI" installed — Tk silently substitutes a fallback font there with different (wider) character metrics, so the exact same code measured a different width on CI than on a real Windows machine. The fix itself was never wrong; only the test's hardcoded number was tied to a font that isn't guaranteed to exist everywhere the test runs.

**Fix:** Replaced the absolute pixel assertion with a relative one — reconstruct the pre-fix sizing using whatever font actually resolves on the machine running the test, and confirm the real, fixed version is narrower than that reconstruction. This verifies the fix's actual effect (smaller font, tighter spacing making it narrower) rather than a Windows-specific pixel target, so it holds regardless of which font a given environment substitutes.

**Takeaway:** A pixel-exact measurement is only as portable as the font it was measured with. This app only ships for Windows, so the *fix* only ever needed to be correct there — but the *test* runs in CI on a different OS, and a test's environment doesn't have to match the app's target platform. Prefer testing a change's relative effect over asserting an absolute number tied to something environment-specific, when the two can drift independently like this.

---

### The chip that looked clickable, and the fix that looked like it worked

**Symptom:** Two things, found close together while working on the same panel. First: Statistics category chips visibly highlighted on hover and showed a hand cursor, but clicking one did nothing — reproduced consistently in both the plain script and the packaged `.exe`, after scrolling the Settings page first. Second, found while building a live-update fix for the first: after deleting a category (or, later, adding a template), Statistics kept showing the old data until the page was left and reopened.

**Root cause (the chip click):** Never conclusively found. Simulated the click three different ways — including using real window hit-testing (`winfo_containing`) to find whichever widget was genuinely under the cursor at that screen position, exactly as a physical click would land — and every synthetic version worked correctly. The failure was never reproduced headlessly, despite that. Rather than keep chasing it, the interactivity was removed outright: Statistics was only ever meant to be a quick snapshot, not another way to filter notes, so a broken shortcut to a feature nobody asked to keep wasn't worth further investigation.

**Root cause (the stale count):** More straightforward — `_render_statistics()` only ever got called when Settings was first opened or the theme changed, not whenever the underlying notes/categories/templates actually changed while already on the page.

**A fix that made things worse before better:** The first attempt refreshed `_render_statistics()` from inside `refresh_note_list()`, but gated it on the Settings page's `winfo_ismapped()` state — the idea being: only redo the work if Statistics is actually visible. This looked correct and passed every scripted test, because the test scripts force `update_idletasks()` after nearly every single action. In real interactive use, `pack()`/`pack_forget()` don't reliably flip `winfo_ismapped()` synchronously — so the guard sometimes silently skipped a real update, and the reported symptom (a frozen category list, an unaligned older layout) persisted even after this "fix" had already shipped.

**Fix that actually stuck:** Removed the visibility guard entirely. `_render_statistics()` now runs unconditionally whenever `refresh_note_list()` runs, and whenever a template is added/edited/deleted. It only ever draws a handful of small widgets — genuinely cheap to redraw every time — so there's no real cost to just always doing it, and no Tk mapping-timing subtlety left to get wrong.

**Takeaway:** A visibility check that "looks like the right optimization" is worth being suspicious of when it depends on exact widget-mapping timing — Tk doesn't guarantee `winfo_ismapped()` reflects a `pack()` call synchronously, and a test suite that forces `update_idletasks()` at every step can hide exactly this kind of bug, passing cleanly while the real app still misbehaves. When the underlying work is cheap, skipping the optimization entirely can be the more robust choice.

---

### The DPI fix that made things worse

**Symptom:** Two side-by-side sections in the note editor (Checklist and Calculator), built with `grid()` and a shared `uniform` group specifically to force equal column widths, still rendered visibly unequal in a real screenshot from the user — despite `winfo_width()` proving both columns were pixel-identical inside Tk's own geometry math, on every window size and maximize state tested locally.

**Root cause:** The app was never declared DPI-aware, so on a display scaled above 100% (125%/150%, the user's actual setup) Windows renders the whole window at 100% internally and then stretches the finished bitmap to match the scaling factor — a blunt, whole-window operation that can apply inconsistently across nested widget hierarchies. Tk's own layout math was correct the entire time; the mismatch was introduced afterward, by the OS.

**Fix attempted:** Declared the process DPI-aware (`SetProcessDpiAwareness`, with a `SetProcessDPIAware` fallback for older Windows) and told Tk to scale its own font/spacing math to match (`tk scaling`) — the standard fix for this class of problem. Couldn't be verified visually in the development environment, since it isn't running at 125%/150% scaling, so it shipped for the user to test on the real machine that reported the bug, with that limitation flagged up front.

**Reverted:** On the actual 150%-scaled machine, the fix didn't resolve the column mismatch, and made the app's overall rendering visibly blurrier. Reverted in full rather than trading one visible cosmetic problem for a worse one.

**Takeaway:** A fix that's well-understood in theory and impossible to verify locally is still a gamble — flagging that uncertainty explicitly up front made the revert a quick, low-friction call once real-machine testing disagreed, instead of a surprise. Sometimes the right outcome is to leave a minor cosmetic issue unresolved rather than layer an unverifiable fix on top of it.

---

### The cleanup that deleted the real notebook

**Symptom:** After rebuilding and testing the `.exe`, the notes it showed were completely different from — and far fewer than — the notes visible when running `python note_organizer.py` from the project folder. It looked as if the `.exe`'s notebook had simply reset itself.

**Root cause:** Two pieces of migration logic, both run automatically at import time (`MIGRATION_INFO = run_migrations(APP_DIR)` / `PURGED_DIRS = purge_stale_copies(APP_DIR)`), combined into a real data-loss bug. `run_migrations()`'s job is to pull old notes forward from `%APPDATA%\NoteOrganizer` into whatever directory the app is currently running from in script mode (dev checkout, or literally any script that does `import note_organizer`) — reasonable on its own, and non-destructive, since it only *copies*. But `purge_stale_copies()` then runs right after, looking for "redundant leftover copies" to clean up — and the AppData folder it just copied *from* now looks perfectly redundant, since every note in it also exists in the copy that was just made. So it got deleted: `notes_data.json`, `settings.json`, and the whole `attachments/` folder, gone. This could be triggered by nothing more than running one of the project's own headless test scripts (`test_calculator.py`, `test_recurrence.py`, `test_data_safety.py`) from a fresh scratch directory — exactly the practice `CLAUDE.md`'s QA safety rule requires — since a brand-new directory never has the `reclaimed_from_appdata` flag that would otherwise skip the reclaim.

**Fix:** `purge_stale_copies()` now permanently exempts `%APPDATA%\NoteOrganizer` from deletion, full stop — no redundancy check ever applies to it. It's the durable, cross-run store the distributed `.exe` actually reads from, never a disposable leftover, regardless of what directory happens to be running the code. Genuinely stale, non-AppData leftovers (like an old `dist\` copy from a previous build layout) are still cleaned up exactly as before — verified with a dedicated regression test alongside the ones proving AppData now survives even a maximally "redundant-looking" scenario.

**Recovery:** the real notes weren't actually gone — they'd been copied into a directory before AppData was cleared. In this case a plain `python note_organizer.py` run at the project root held an intact copy, which was restored back into AppData by hand (a direct file copy, deliberately not routed through any app code, to stay isolated from the very bug being fixed).

**Follow-up (0.33.x):** the deeper cause — that any `import note_organizer` performed migrations at all — is now gone. Resolving the data folder, migrating, purging and writing settings moved into an explicit `initialise()`, called by `NoteOrganizer.__init__` and by `_main()`. Importing the module creates no files and touches no notes, verified by importing it into a directory holding a decoy notebook and confirming nothing was read, moved or deleted. The exemption below still stands as defence in depth; it is no longer the only thing standing between a stray import and someone's notes.

**Takeaway:** "Copy it somewhere else, then delete the original because it's now redundant" is a dangerous pattern to apply to anything that's a *permanent* store rather than a genuinely disposable one — the logic has no way to tell those apart from the data alone. A cleanup routine should name its exemptions explicitly (as this fix now does) rather than relying on every possible caller happening to avoid the deletion condition. Also worth remembering: a safety practice designed to protect data from one specific script (`qa*.py`'s working-directory wipe) doesn't automatically protect against a completely different destructive path living inside the very code being tested.

---

### The fast-typing fix that took three tries to land safely

**Symptom:** Building Phase 1 of rich text formatting, a user asked for "sticky" formatting — toggle Bold with nothing selected, and it should apply to whatever gets typed next, until toggled off again. The first working version tagged "the one character right before the cursor" on every `<KeyRelease>`. It passed every test, including manual use — until the same user reported that typing quickly while Bold was on left some letters un-bolded.

**Root cause (the original gap):** `<KeyRelease>` fires once per keystroke, right after that keystroke's own insertion — true, but under a fast burst Tk can process several `KeyPress` insertions before it gets around to dispatching the `KeyRelease` callbacks for them. A callback can end up running once the cursor has already moved past more than one new character, and "the character right before the cursor, right now" silently skips whichever ones came in between. Every test that exercised this called `update()` after each simulated keystroke, which gives Tk time to fully settle between them — exactly the condition that hides this bug, and exactly why it only ever showed up in real, fast human typing.

**Attempt 1 (reverted): hooking the Tcl level.** To close the gap with true per-insert precision, the Text widget's own Tcl command was renamed and a Python proxy installed in its place, so every insertion — real typing, at any speed — could be tagged synchronously as part of the exact same call that performed it. This caused **three separate, unpredictable app-launch crashes** in real use, each from a different Tk-internal operation (a `sel.first`/`sel.last` selection query; an empty-string index from the proxy's own bookkeeping re-entering itself recursively) that normally fails silently and harmlessly at the C level, but turned into a real, escaping Python exception the moment a Python proxy sat in the call path. There was no way to find each one except from a crash log after it had already happened once — an unacceptable trade for closing what was, ultimately, a minor formatting gap.

**Attempt 2: a tracked anchor mark.** Reverted to `<KeyRelease>`, but instead of tagging one guessed character, a left-gravity mark tracks *where the pending run started*; each callback tags the whole span from that mark to the current cursor, however many characters that turns out to be, then advances the mark. However many keystrokes pile up before a callback gets its turn, the next one covers all of them in one go. Deciding *whether* a given `KeyRelease` represented real typing (vs. a navigation key, or the toggle shortcut's own key-release) was done by inspecting `event.char`/`event.state`. This passed a five-round fast-typing stress test locally on Windows — and then failed the exact same test in CI (Linux + Xvfb).

**Attempt 3 (the one that stuck): stop inspecting the event, inspect the text.** A differently-behaving Tk build populates `event.char` differently for at least one synthetic key event in a fast burst, which got misread as "not real typing" and silently ate a chunk of already-typed text out of the tag — the same *class* of bug as the original gap, just relocated. The fix: decide whether to extend the tag based on whether the note's actual character count grew since the last check, a fact about the widget's content that doesn't depend on how any particular platform's Tk build fills in event details. A paste (which also grows the count) is excluded separately, via its own `<<Paste>>` handler that resyncs tracking right after the paste lands — not by trying to tell "typing" and "paste" apart from the event that happens to follow either one.

**Takeaway:** The safest-*looking* fix (closing a timing gap with true synchronous precision) was the most dangerous one in practice — three crashes from internal Tk behavior that had never needed to be visible to Python code before. The fix that actually shipped uses only ordinary, already-proven-safe Tkinter mechanisms (the same mark-tracking pattern the calculator's insert-into-note feature already relies on) and is *less* theoretically precise, but categorically safer. And even having learned that lesson once, the second version still leaned on `event.char` — inspecting event internals for a decision that should be about *what the widget actually contains* was the recurring mistake across both the original bug and its first fix; only checking the text itself, directly, finally closed it for good.

---

### The theme-switch flicker, and three ways not to fix it

**Symptom:** Switching between dark and light showed a visible flicker — briefly, a half-recoloured page with dark bands across it. Colors always ended up correct; it was the transition itself that looked broken. It also got worse as more notes accumulated.

**The three attempts that failed, and why they were always going to.** All three tried to *hide* the flicker rather than ask what was producing it:

1. **`WM_SETREDRAW` (reverted).** Sent the Win32 "hold off repainting" message to the window before the update. No effect. The reason only became clear later: in Tk on Windows every widget is its own OS window, so suppressing repaints on the top-level does nothing about the hundreds of child windows that actually paint themselves.
2. **A full-window colour cover (reverted).** Covered the window with a plain `tk.Frame` during the rebuild. This made it *worse*: the UI shows several genuinely different background shades at once (sidebar, cards, main background), so one flat colour can't blend into any of them — the cover became its own visible flash on top of the original churn.
3. **A screenshot "freeze frame" (never shipped).** Grab the window with Pillow, show it as an image over the UI, recolour underneath, remove it. Measured *before* building it: 57–93ms of overhead, more than the entire switch it was meant to hide. Rejected on the measurement.

**What the measurements actually showed.** Profiling the switch (40 notes) instead of guessing: `refresh_note_list()` was ~85ms of ~121ms, at roughly 2ms per note card — and it is a destroy-then-repopulate, so the list visibly emptied and refilled. Statistics rebuilt itself too (no statistic changes when only the palette does), and the calendar rebuilt every day cell even while off screen. A probe using `after_idle` confirmed Tk's event loop never gets a turn mid-switch, so **Tk was not repainting partway through** — Windows was, because each widget's background flips the moment it's configured.

**The fix:** stop doing work that nothing asked for. Note cards are recoloured in place (`_recolor_note_cards`) instead of destroyed and rebuilt; statistics isn't touched; the calendar is deferred through the existing `_catch_up_deferred_refresh()` when it isn't visible. ~140ms → ~26ms, and it no longer degrades with note count (40→100 notes used to add 117ms, now 19ms). Verified by asserting the in-place result is identical, option for option, to what a real rebuild produces across four themes.

**A real bug fell out of verifying it.** That equivalence check caught a custom note colour being repainted with the new theme's accent — `_recolor_stragglers` can't tell a themed widget from a note the user deliberately coloured the same hex. It was confirmed present on `main`, i.e. pre-existing and unrelated to the new work. Fixed by running the card recolour *after* the straggler pass and recomputing each stripe from the note's own data, so the note's colour is authoritative.

**Takeaway:** three attempts were spent hiding a symptom before anyone measured where the time went; the measurement pointed straight at the fix and took less effort than any of them. When something looks like a rendering problem, profile before reaching for a rendering trick. Also worth remembering: an "additive" fix that only wraps existing behaviour can still make things worse (attempt 2), and reverting cleanly is a legitimate outcome rather than a failure. What remains is a genuine plain-Tkinter limit — one OS window per widget, each repainting as it is recoloured — not something further code can remove.

---

### The module that existed twice

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
