# Notable Issues Log

A narrative log of the more interesting bugs found and fixed during development — chosen because each one taught something worth remembering, not because they were the only bugs. Routine fixes are just commits; these are the ones with a real "why did this happen" behind them. See also the repository's [Issues](../../issues) for day-to-day tracking.

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
