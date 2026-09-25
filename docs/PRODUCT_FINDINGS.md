# Product findings register

What a hostile, outside look at the app found — and what was done about
each thing. This is the working list for getting the app to the standard
a stranger who paid nothing but expects a real product would accept.

The [code audit](ROADMAP.md#the-code-audit-programme-2026-09) asked "is
this code correct?" and closed. This asked a different question: **"would
you actually use this, and would you be embarrassed if people saw it?"**
Different question, different findings — none of these are audit misses.

- [How this was produced](#how-this-was-produced)
- [Tier 0 — the app edits or deletes data without saying so](#tier-0--the-app-edits-or-deletes-data-without-saying-so)
- [Tier 1 — the reason a stranger would quit](#tier-1--the-reason-a-stranger-would-quit)
- [Tier 2 — the shop window](#tier-2--the-shop-window)
- [Tier 3 — keyboard and accessibility](#tier-3--keyboard-and-accessibility)
- [Tier 4 — product gaps worth a decision](#tier-4--product-gaps-worth-a-decision)
- [Round 2 — the consistency survey](#round-2--the-consistency-survey-2026-09-25)
- [What held up under attack](#what-held-up-under-attack)
- [Refuted — do not re-chase](#refuted--do-not-re-chase)
- [What this review did not cover](#what-this-review-did-not-cover)

Status values: **open** · **fixed** (with the version) · **accepted**
(with the reason, like the [coverage ledger](../qa/COVERAGE_LEDGER.md)'s
ACCEPT rows) · **deciding** (waiting on a product call).

## Keeping the Status column honest

This column drifted badly once: every one of the eight Tier-0 findings
shipped as counted `Fixed` bullets in `0.71.154`, and the register went
on saying `open` for all of them — along with T2-1, fixed in the same
release. A register that does not know what has been done makes the
work that remains unreadable, which is worse than having no register.

`py tools/verify_findings.py` asks the **code** what is still true, one
finding at a time, for every finding that can be answered by looking. It
prints `DONE`, `still open`, or — for the ones that need a measurement
rather than a grep, like T1-1 — says so instead of guessing. Run it
before planning a round, and correct this column from what it says
rather than from memory.

Two findings are marked fixed on the changelog's evidence rather than
the code's, and are labelled that way above: T0-3 and T2-1 are
user-visible messages, where the shipped bullet is the better witness.

One thing the column cannot keep honest on its own is a line number. An
evidence cell cites `file:line` as it stood when the finding was written
down, so on a **fixed** row it points into code that has since moved or
gone — three do today, in T0-1, T0-4 and T1-4. Read those as part of the
story rather than as directions. Only citations on rows still awaiting
work are worth keeping current, which is why Round 2's rows name the
build theirs were read against.

## How this was produced

Two waves of parallel reviewers, each finding verified against the code
before it earned a place here:

1. **The product tour** — four lenses (feature gaps, UX walkthrough,
   keyboard/accessibility, scale/longevity), one adversarial verifier per
   finding. 33 survived, 4 were refuted.
2. **The hostile pass** — five deliberately unkind lenses
   (first-impression, chaos/abuse, drive-it-for-real, code-craft,
   store-readiness), each finding put to **three** diverse verifiers with
   *refute-by-default when uncertain* and majority rule. 27 survived, 7
   were refuted. Most were reproduced by executing the real app in
   isolated scratch copies, not by reading.
3. **A harshness audit** on top, asking "is this list still too soft?" —
   which found the most severe items on this page, and pointed out that
   the hostile pass's 27 entries were really about ~17 findings (the
   first-run modal was reported six times).

Two lessons worth keeping from the process itself: the first, polite wave
refuted nothing at all, which was the tell that its verification was too
lenient; and six reviewers quoted the wording of a startup dialog without
one of them reading the function behind it — which is where the worst
finding was hiding.

## Tier 0 — the app edits or deletes data without saying so

These are one family: routes where the app changes the user's data with
no message, no Trash and no undo.

| # | Finding | Evidence | Status |
|---|---|---|---|
| T0-1 | **The first-launch cleanup deletes real notes.** `note_is_empty` checks title/body/comments/attachments but **not checklist**, while `_autosave_now` explicitly counts a checklist as real content — so the app lets you create a checklist-only note and then deletes it as "empty". The dedup signature is `(title, body, comments, category, date)`, also without checklist, so two notes differing only in their checklists collapse to one. Nothing goes to the Trash. It re-arms whenever `settings.json` is unreadable. | `core/model.py` `note_is_empty` + `clean_notes` signature vs `note_organizer.py:759`. Executed: 5 seeded notes → 2 after first load. | **fixed 0.71.154 — `note_is_empty` counts the checklist** |
| T0-2 | **Two windows on one notebook silently destroy each other's work.** No single-instance guard, no lock file, no mtime check, no reload. Both load into memory; every save is a blind full-file rewrite, so the last writer wins the whole file. Trivially reached from a taskbar pin or Start menu. | No locking primitive anywhere; `core/storage.py` `save_notes`. Reproduced with two real app processes by two independent verifiers. | **fixed 0.71.154 — `core/single_instance.py` holds the lock** |
| T0-3 | **Restoring your own backup flattens every custom category to "General".** `settings.json` — where categories live — is written into the backup zip, but the import never reads it back; `normalize_note` then re-files every note whose category is unknown. "Import complete", no warning. | Export entry list vs `_poll_import_progress`; `normalize_note`'s category fallback. Reproduced device-A → device-B. | **fixed 0.71.154 — an imported backup restores the filing system** |
| T0-4 | **Every save silently strips the body**: `body = get("1.0","end").strip()` removes leading indentation on the first line and every trailing blank line. A pasted code block or quoted email loses its shape on the next load. | `note_organizer.py:13565`. Executed. | **fixed 0.71.154 — the save reads the body unstripped** |
| T0-5 | **An untitled note cannot be emptied.** Clear it, switch away, come back — the old text is on disk and returns; the autosave discarded the emptying in silence. Ctrl+S instead answers "Write something before saving!" | The empty-note guard in `save_current_note`. Executed. | **fixed 0.71.154 — one emptiness answer, consulted by every gate** |
| T0-6 | **"Restore previous" is a one-session promise.** The rescue copy really is written to disk in `note["_prev"]`, but `_prev` is not in `NOTE_DEFAULTS`, so `normalize_note` discards it on the next launch — while the button that offers it looks permanent. | `note_organizer.py` `_prev` write vs `core/model.py` `NOTE_DEFAULTS`. Executed across a restart. | **fixed 0.71.154 — `_prev` survives `normalize_note`** |
| T0-7 | **A pasted share code can brick the app permanently.** `checklist` is in `SHAREABLE_FIELDS` with no size cap anywhere — 20,000 items is a 60 KB code that passes every guard (length, decompressed size, note count, path traversal). Rendering the note kills the process, and because the note is saved first, **the app never starts again**. | `core/sharing.py` `SHAREABLE_FIELDS` + `decode_share_code` caps; `core/model.py` keeps every item. Executed, 3/3 crashes. | **fixed 0.71.154 — ceilings at the choke point; the styling shape that got past them closed in 0.71.155** |
| T0-8 | **The dangerous-attachment list misses today's delivery vehicles**: `.lnk`, `.url`, `.scf`, `.iso`, `.img`, `.chm`, `.inf`, `.appref-ms`, `.settingcontent-ms`. A shortcut file arriving in an imported backup opens through `os.startfile` with no warning at all, running whatever command line it carries. | `DANGEROUS_EXTENSIONS` in `note_organizer.py`; `ui/attachments.py` gates on it. | **fixed 0.71.154 — `.lnk` and its family are in the warn list** |

## Tier 1 — the reason a stranger would quit

| # | Finding | Evidence | Status |
|---|---|---|---|
| T1-1 | **Every pause in typing freezes the app.** `refresh_note_list` destroys and rebuilds every card, and is called from 32 sites — every autosave, search, sort, filter, delete and import. The harshness audit named this the single most likely reason a month-in user would stop. One fix (incremental card updates instead of destroy-and-rebuild) retires the whole class. | Measured, fresh process per size: **77 notes ≈ 0.9 s frozen per typing pause**, 300 → 1.6–1.8 s, 1000 → 7.5 s; with a search term active, worse. Confirmed independent of note *size* — it is note count. | **partly fixed** — deleting a note and Select all/Unselect all no longer rebuild the list (`0.74.169`, `0.75.173`): 264 widgets and 185ms became 3 and 31ms for a delete, 140 and 170ms became 0 and 3.5ms for a tick. The autosave path still rebuilds, so the finding stays open for that. |
| T1-2 | **`render_calendar()` runs on every autosave** with no visibility guard, rebuilding every day cell and expanding occurrences over the whole notebook while the user is on the Notes tab — although `apply_theme` already has exactly the guard it needs. | `note_organizer.py` save path vs the `_calendar_is_showing()` guard used elsewhere. | **fixed 0.74.169** — the test lives inside `render_calendar()` now, so all thirty-one callers get it rather than each having remembered; the skipped rebuild is caught up on every route back to the calendar. Measured at 36ms and 98 widgets per data change from the Notes tab. |
| T1-3 | **The disk write is 4.2× slower than it needs to be**: `json.dump` streams thousands of small chunks through the encoder instead of building one string. Byte-identical output either way. | Measured: 5,000 notes 322 ms → 76 ms; 1,000 notes 63 ms → 16 ms. | open |
| T1-4 | **The one check guarding all of this cannot fail**: `qa/qa4.py:334` is `check(..., True)` — it measures the time, prints it into the label, and asserts a literal `True`. | Read the line. | **fixed** — `qa/qa4.py` now asserts `_cards_built == 300` and `elapsed < NOTE_LIST_BUDGET_MS`; the literal `True` is gone. The remaining `check(name, True)` in that file is the `safe()` helper's success path, not a timing assertion. |

Also measured, and worth recording as a **non**-finding: one-file JSON is
not a scale problem. Load at 5,000 notes is 112 ms and everything is
linear; the widget layer is 25–100× more sensitive than the storage
format. Do not trade the plain, greppable, hand-recoverable file for a
database — fix the list rendering instead.

## Tier 2 — the shop window

| # | Finding | Status |
|---|---|---|
| T2-1 | **The first screen of the product is a maintenance report**: a blocking modal reading "Cleanup pass (runs once) … 0 note(s) remain, IDs renumbered 1–0". Found independently by four lenses. (The deletion behind it is [T0-1](#tier-0--the-app-edits-or-deletes-data-without-saying-so).) | **fixed 0.71.154 — a fresh install opens straight to the notes** |
| T2-2 | **No application icon anywhere**: the Tk feather in the title bar and taskbar, PyInstaller's own icon on the `.exe`, and an empty Win32 version resource (FileVersion 0.0.0.0, no ProductName). No `.ico` exists in the repository and `NoteOrganizer.spec` has no `icon=`. | **fixed 0.71.158 — drawn in `tools/make_icon.py`; window, `.exe` and version resource** |
| T2-3 | **The app is DPI-unaware**, so Windows bitmap-stretches the whole window on any scaled display (the factory default on most modern laptops) — soft text, fuzzy 1px borders. Engage with ["The DPI fix that made things worse"](ISSUES_LOG.md#the-dpi-fix-that-made-things-worse) before touching this; the previous attempt was reverted for good reasons. | open |
| T2-4 | **A dead horizontal scrollbar spans the bottom of the window permanently**, and a first run with zero notes shows five scrollbars, all in ttk's bevelled `clam` style. | open |
| T2-5 | **The A and H toolbar buttons render in raw Windows grey** until the first click in the body — they are coloured only by `_refresh_format_buttons`, which never runs with no note loaded. This is the first-run frame anyone screenshots. | open |
| T2-6 | **Note previews clip mid-word with no ellipsis** — the text is truncated by character count while the card is sized in pixels. Visible in the README's own hero screenshot. | open |
| T2-7 | **A failed save produces three contradictory messages**, two of them false: a green "✓ Note updated" toast, then the error dialog, then an error toast that still reads "✓ …" because `_show_toast` hardcodes the checkmark and only varies the colour. | open |
| T2-8 | **Two documented promises are no longer true**: README's "nothing ever falls back to an OS-native dialog" (five `filedialog` calls on core flows — attach, export, bulk export, import), and the User Guide's clickable Statistics chips (deliberately made inert). | open |
| T2-9 | **The delete confirmation promises "30 days"** whatever retention the user chose (7–90), and never mentions the Trash at all. | open |
| T2-10 | **Ctrl+S confirms nothing visible** — the deliberate save writes to a status label at the bottom of a scrolling page, while the autosave nobody asked for gets the floating toast. | open |
| T2-11 | **The editor's whole action row is below the fold** at the shipped 900×600: Save, Delete, Generate code, Duplicate, template buttons and ↩ Restore previous are all off-screen on first launch. | open |

## Tier 3 — keyboard and accessibility

| # | Finding | Status |
|---|---|---|
| T3-1 | **Enter answers no dialog in the app.** On this Tk, `tk.Button`'s class bindings carry `<Key-space>` but no `<Key-Return>`, and the dialogs bind only `<Escape>` — so the Windows reflex is a no-op on every confirm. (It also means the 0.71.119 "focus No so Enter is safe" work rests on a premise that never held.) | open |
| T3-2 | **No note in the list can take keyboard focus** — 0 of 12 widgets; Tab skips the entire list. Same for the calendar: 60 click targets, 0 focusable days. A keyboard-only user can create and save a note but can never open one that already exists. | open |
| T3-3 | **Escape closes 3 of ~18 popups** — it is bound on borderless Toplevels that keyboard focus never enters. | open |
| T3-4 | **White-on-accent fails WCAG AA in all eight themes** (2.32–4.35:1; four themes fail even the 3:1 large-text floor). `success` as status text is 2.80:1 on every light theme. | open |
| T3-5 | **The note body and Comments are Tab traps**; only undocumented Ctrl+Tab escapes. In Comments, Tk's legacy bindings are live: Ctrl+I inserts a tab and Ctrl+D deletes a character, because the formatting shortcuts are bound on the body only. | open |
| T3-6 | **The in-app shortcut reference omits real keys** it calls "everything the keyboard can do" (the list-editing keys, Ctrl+Tab), and mislabels Ctrl+A as table-only. | open |

## Tier 4 — product gaps worth a decision

Not defects — decisions. Ranked by the reviewers as the gaps this
audience would actually feel.

| # | Gap | Status |
|---|---|---|
| T4-1 | **A note you missed yesterday never surfaces again.** There is no overdue concept anywhere: the daily bar counts only today, the card prints a bare date with identical styling whether it is two years past or future, and History buckets by year. | deciding |
| T4-2 | **Repeating notes and checklists do not compose**: `OVERRIDABLE_FIELDS` has no `checklist`, so ticking an item on one day of a series is silently discarded — there is no "done today" for a recurring routine. | deciding |
| T4-3 | **Window size and position are never remembered**, though the app remembers the theme, the font, collapsed groups and the last open note. Sort order and category filter reset every launch too. | deciding |
| T4-4 | **Checklist text is invisible to both searches**, and find-in-note cannot see the Comments box — so the two searches also disagree with each other. | deciding |
| T4-5 | **The Trash cannot be searched** — 25 at a time with a "Show 25 more" button, for a store that can hold 90 days of deletions. | deciding |
| T4-6 | **The app hoards full plaintext copies of the notebook** (`notes_data_backup_*.json`, never pruned — measured 26 files at 12.5× the live notebook) and no screen in the app admits they exist. The crash message even points at "Settings → Backup" to restore, where Import only accepts `.zip`. | deciding |
| T4-7 | **Nothing in the shipped app teaches the app**: no starter templates, no welcome note, no Help section — and `NoteOrganizer.spec` has `datas=[]`, so the User Guide does not ship with the build. | deciding |
| T4-8 | Ranked feature gaps a peer app would have: a **quick-switcher** (Ctrl+K), **clickable URLs** in a note, **find-and-replace**, **OS dark-mode following**, inline images. The existing ROADMAP candidates were ranked too — Undo on the delete toast first, then `.md`/`.html` import, then PDF via Edge. | deciding |
| T4-9 | **The multi-tab machinery** — both waves agree independently: **do not build real tabs** (the single-editor model *is* the product's promise, and tabs would reintroduce N dirty buffers, N deferred occurrence prompts and N view-restore timers), **but delete the dead half**, which still runs on the hot path of every save and makes every future reader believe a feature exists. Keep `open_tabs`/`active_tab_index` as a documented single-slot snapshot. | deciding |

## Round 2 — the consistency survey (2026-09-25)

A different question from the one above. The hostile review asked "would
you use this?"; this asked **"does the same kind of thing behave the same
way everywhere?"** — after a field report that the calendar offered a
note's actions two different ways depending on how you reached it.

Five readers went through one region each (the sidebar list, the editor,
the calendar, the Settings page, the popups and dialogs) and wrote down,
for every surface that shows a note or a note-like item, what a person
can do to it and **how they reach it**: a button with a word on it, a
wordless glyph, right-click only, a double-click, the keyboard. 114
surfaces. Then one pass compared them.

It found the app's own rule, which is worth writing down because it is
not in any document and the code follows it almost everywhere:

> A row in a list offers its actions through right-click, with a plain
> click doing the single most likely thing; a single open item offers the
> same actions as worded buttons; and a destructive action is confirmed
> in proportion to how recoverable it is — recoverable-to-Trash asks a
> plain yes/no with Yes ready, irreversible asks with a warning glyph and
> "No" pre-selected.

Twenty-five places disagree with it. **Seven of those involve destroying
something** and are marked in bold; they are listed first. Everything
here is `deciding` until it is triaged — a finding lands in this table
whether or not anyone intends to act on it, and an `accepted` row with a
reason is as good an outcome as a fixed one.

Two things to read with suspicion, both admitted by the survey itself.
It reported the calendar day panel's wordless bin as a headline problem
while that was being removed in the working tree — so its picture of the
calendar is one commit stale, and the rows below have been checked
against `0.75.176` rather than trusted — every line number in them is
as of that build. And no reader ran the app or took a screenshot:
every claim about how something *looks* is read off the source, and
the ones that turn on appearance say so in their own row.

| # | Finding | Where | Suggested fix | Status |
|---|---|---|---|---|
| C-1 | **Changing the category of a batch of ticked notes overwrites every one of them the instant you click a category name — no question asked, and no way back. The button next to it, Trash, asks first and then offers Undo.** Tick fifty notes, mean to export them, click the button one to the left, and fifty notes have silently lost the category that told you what they were. Nothing on screen but a status line, and no undo exists — the previous categories are gone from the file. It is the only bulk action in that bar with no guard at all, and the bar's whole purpose is acting on many notes at once, which is exactly when the mistake is largest. | Bulk bar: "🗂 Category ▾" applies at note_organizer.py:12711-12736 (only self.set_status afterwards) vs its neighbour "🗑 Trash" at note_organizer.py:12657-12665 (ask_yes_no + undo toast) and the single-note delete at note_organizer.py:15054. Reported by survey 1 (asymmetry #1); I read both call sites. | Give it the same shape as its neighbour: ask_yes_no naming the count and the target category, then an undo toast built from the same (id, old_category) marks pattern _bulk_move_to_trash already uses. If only one is affordable, the undo toast matters more than the question. | **fixed 0.75.177** — it got both, and the reason it got both is that the neighbour's real safety net is the thirty days in the Trash rather than its toast, so an eight-second offer does not replace the question. The marks carry `(id, category, updated)` per note, not one value for the batch, and `updated` goes back too. [Story](ISSUES_LOG.md#the-undo-that-would-have-put-everything-in-one-place). |
| C-2 | **Deleting a checklist item takes one click on a small bin with no word next to it, no question and no undo. Removing an attached file, one panel below, asks first with a warning triangle and "No" already chosen.** Both gestures are "take this small thing off this note", they sit within a few centimetres of each other, and they behave oppositely. The checklist item is written away by the autosave immediately, so a mis-click on a twenty-item shopping list loses the line with no route back — while the attachment is the one that gets the ceremony. **One sentence of that was wrong and is corrected here rather than quietly dropped:** it read "the attachment, which at least the file system still remembers", and `remove_attachment` calls `_delete_attachment_files`, so the stored copy goes with it. The comparison still holds as a finding — one of the two had no way back — but not for the reason first given, and the right answer changed with it. | Checklist row 🗑 at note_organizer.py:8941-8943 (delete() at :8933 → list remove + _schedule_autosave) vs the attachment ✕ at noteorganizer/ui/attachments.py:102-107 (icon="warning", default="no"). Reported by survey 2; I read both. | Match the attachment row it sits beside: either ask_yes_no with icon="warning", default="no", or — better for something this small and this often repeated — keep the single click and follow it with an undo toast (note_organizer.py:15190) that puts the item back at its old index. Do not leave it as the one child-object removal in the editor with neither. | **fixed 0.75.179** — the undo toast, not the dialog: with the attachment's file really being deleted, its warning is right for an irreversible act, and the checklist's answer is to become recoverable instead. The item returns to its own index, and the offer is guarded by the identity of the working list, since five routes rebind it. Probing the fix found a second bug on older ground — the autosave's banner was wiping every Undo the app offered, about a second after it appeared. [Story](ISSUES_LOG.md#the-offer-that-was-gone-before-you-could-take-it). |
| C-3 | **Shortening how long the Trash keeps notes is a quiet dropdown. Pick "7 days" while forty notes are sitting in there from last month, and they are gone for good the next time the app starts.** Every other permanent deletion in Settings — one trashed note, Empty trash, a template — stops and warns with "this can't be undone". This one does the same damage, to potentially more notes, with no dialog at all, and the consequence lands on a later launch when nobody connects it to the dropdown they touched. The subtitle mentions timing but never says notes will be destroyed. | noteorganizer/ui/settings_page.py:1221-1240 (set_retention → save_setting, no confirm). The only warning is the row's own subtitle at :1214-1216, "A change applies from the next startup's cleanup." Reported by survey 4, which flagged it as needing human judgement rather than asserting it. | When the new value is shorter than the current one AND the Trash holds notes the new window would already have expired, ask once with icon="warning", default="no", naming how many notes that is. Leave lengthening it silent. | **fixed 0.75.180** — exactly that, plus the attached files, which the purge also deletes from disk and which nothing on that screen had ever mentioned. The count and the purge are now one judgement (`trash_entries_past_window`), so the dialog cannot name a number the purge will not deliver. [Story](ISSUES_LOG.md#the-eight-failures-that-hid-two-live-mutants). |
| C-4 | ~~**In the History list, right-clicking a repeating series and choosing Delete removes the entire series. Right-clicking one of its days, indented just below, and choosing the identically worded Delete removes only that day.** One menu, one label, two very different amounts of damage, and the only thing distinguishing them is which row you aimed at.~~ **Mostly wrong, and corrected rather than quietly dropped.** Driven through both rows' real menus, the day row does **not** remove only that day: it raises a three-button question naming the day (*Cancel / The entire series / This occurrence only*), and cancelling it destroys nothing. The series row asks a yes/no that says "Delete this entire repeating series?" and then moves the note to the **Trash**, recoverable for the retention window, with an Undo toast on top. So each route names its own scope before acting, and the more destructive one is recoverable twice over. Two further claims in the row were also false: "Yes ready for Enter" — Enter answers no dialog on this Tk, which is [T3-1](#tier-3--keyboard-and-accessibility), already in this register; and "a series that may cover years of days" being lost, when what is lost is one Trash entry. **What was true is the label:** both rows read `🗑 Delete`, so the menu said nothing about scope until after the click. | Series group row passes no occurrence_date: noteorganizer/ui/calendar_view.py:1155-1157 (show_note_context_menu(e, n)). Child day row passes it: :1146-1152. _delete_note then skips the scope question when occurrence_date is falsy (note_organizer.py:15019-15025). Reported by surveys 3 and 5. | Word the entry for what it will do: "🗑 Delete the whole series" on the group row, leaving "🗑 Delete" for a single day. The mechanism behind it is already correct; only the label lies. | **the label changed, the finding refuted** — the suggested fix was right about the label and wrong about why, so it was done as a `Changed` rather than as a repair: the entry now names the series on the two surfaces that open a note's menu without a day, and keeps the plain word on a day row, where the scope is still a question. No version bump, since nothing was `Added` or `Fixed`. [Story](ISSUES_LOG.md#the-finding-that-described-a-dialog-nobody-had-opened). |
| C-5 | **"Clear day color" and "Clear day markers" on a calendar day happen the moment you release the mouse, with no question and no way back.** Low stakes — it is decoration, not content — but it is the same "destroy stored state with one click" shape the app elsewhere refuses. Worth listing because a user who has marked a year of birthdays and anniversaries has invested real effort in something the app treats as free to discard. | noteorganizer/ui/calendar_view.py:1252-1265; the markers entry does pop + _persist_day_emoji + render_calendar inline. Reported by surveys 3 and 5. | Cheapest consistent fix is a toast with Undo (the machinery exists at note_organizer.py:15190), not a dialog; a dialog for clearing a colour would be heavier than the action deserves. | **fixed 0.75.181** — exactly that, on **three** routes rather than two: a sibling sweep found the day palette's own "No color" button, which discards the colour precisely as the menu entry does. Measured while confirming the report: the two Clear entries sit directly under the entries that create the same thing, so a mis-aim by one menu row was the real hazard. The marker popup was left alone on purpose — it works on a copy, writes only on Save and discards on ✕ — and a check holds it that way. [Story](ISSUES_LOG.md#the-undo-that-guarded-the-wrong-state). |
| C-6 | **In Settings → Duplicates, the button that cleans up every group at once is painted quieter than the button just below it that only cleans up what you ticked.** Visual weight is how a user reads which action is the big one. Here it is inverted: the sweep across every group looks like a secondary link, and the narrower, deliberate action looks like the main event. Both go to Trash and both confirm, so nothing is lost for good — but the eye is being pointed at the wrong one. | noteorganizer/ui/settings_page.py:1444-1449 ("🧹✨ Clean up ALL N groups", bg=self.colors["sidebar"]) sits above :1451-1454 ("🧹 Move ticked duplicates to trash", bg=self.colors["accent"], white text, larger font). Reported by survey 4. | Swap the two fills, or give the all-groups button the danger colour. Its confirm already names the real count, so the dialog is fine; only the button's weight is wrong. | deciding |
| C-7 | **Escape probably does not close any of the small anchored popups in the app — including the bulk category popup, which has no Cancel button either, so the only way out is a click on empty space.** Escape is the reflex for backing out of something opened by accident, and the bulk category popup is precisely where backing out matters — it is one click from overwriting the category of every ticked note. If Escape is inert there, the user's instinct fails at the riskiest popup in the app. | noteorganizer/ui/dialogs.py:474-475 binds Escape on the popup Toplevel itself, but those popups deliberately never take keyboard focus (note_organizer.py:9204-9205: "Deliberately does NOT use grab_set()"), and none calls focus_set. By contrast _themed_dialog binds Escape on the app window (dialogs.py:158), which is why Escape works there. The image-preview overlay gets no Escape binding at all (noteorganizer/ui/attachments.py:224-272 places a Frame directly). Surveys 1 and 5 both said "no Escape"; the code says the binding exists — so both are half right. | Bind Escape on the app window inside _place_dropdown_popup the way _themed_dialog does (guarding for a nested dropdown's own binding), and give the bulk Category and Export popups a "Cancel" the way the Import and Share panels have "Close". Prove it by pressing Escape on the real app, not by reading the binding. | **fixed 0.75.183** — both halves, and the row's "prove it by pressing Escape" was the right instruction: pressing it is not enough on its own, because Tk delivers a generated keypress to the FOCUS window, so "nothing happened" is equally consistent with a harness that cannot deliver keys. The probe therefore carried a control — with the focus forced inside the popup, the old binding closed it at once — which is what makes the silence a fact about focus rather than about the probe. The "none calls focus_set" half is **wrong**: the inline rename popup focuses its own field and binds Escape there, which is the shape this fix generalised rather than invented. [Story](ISSUES_LOG.md#the-binding-that-could-never-fire). |
| C-8 | On the calendar grid, a note's own title is clickable and hovering it previews that one note — but clicking it opens the whole day instead, and right-clicking it offers day actions, never the note's. The hover makes a promise the click breaks. A user who has just read a preview of "Dentist, 14:00" clicks it and lands on a list of the day's six notes, then has to find that one again; right-click, the app's usual route to a note's actions, hands them "Color this day…" instead. Every action a note has — Open, Pin, Export, Duplicate, Delete, and for a series the two scoped edits — is unreachable from the grid, although the same-looking row in the day panel carries all of them. | noteorganizer/ui/calendar_view.py:458 (<Button-1> → open_day_popup(date)), :459-460 (<Button-3> → show_day_context_menu), :461-462 (<Enter> → show_note_hover_preview, which previews just that note). Reported by surveys 3 and 5. | Point the chip at itself: <Button-1> → show_day_note(note, date) (the day panel's own single-note view), and <Button-3> → show_note_context_menu(e, note, occurrence_date=date), matching what the day panel rows already do. The day menu stays on the cell background, the day number and the dot row, where it belongs. | deciding |
| C-9 | Pinning a note to the top of the list exists in exactly one place: the right-click menu on one note at a time. There is no button for it anywhere, no keyboard route, and no way to pin several at once. A user who never discovers right-click never discovers pinning at all — and the app otherwise teaches that anything you can do to the open note has a worded button under it. Someone reorganising twenty notes must open the menu twenty times. Anyone who works by keyboard cannot reach it at all, which is also true of Export-as-file and every other menu entry. | The only caller of toggle_pin is note_organizer.py:13995, inside show_note_context_menu (toggle_pin itself at :14075). Absent from the bulk bar (note_organizer.py:10051-10124) and from the editor's six-button action row (:10912). No Shift+F10 or Menu-key binding exists to reach any context menu. Reported by surveys 1 and 5. | Two independent, cheap steps: bind <Shift-F10> and <App> on the note cards and rows to the same show_note_context_menu handler, making the whole menu keyboard-reachable at once; and add a bulk Pin/Unpin to the selection bar, where Trash, Category and Export already live. | deciding |
| C-10 | A line in the calculator's history silently inserts itself into your note when clicked. Nothing says so — no button, no wording, just a row of text. The same panel has a worded "⬇ Insert into note" button, so the user has already been taught that inserting is something a button does. A stray click on the history then writes into the note body, which reads as the app typing on its own. The reverse problem is just as real: someone wanting the third calculation back retypes it, never guessing the row was the shortcut. | noteorganizer/ui/calculator_panel.py:310-316; the row is a Label with cursor="hand2" bound to _calc_insert_formula. Reported by survey 2. | One line of hint text above the list — "Click a line to insert it" — costs nothing and is the pattern the attachment rows already use ("Opens in your default app for this file type"). | deciding |
| C-11 | The search box over the note list is the only text field in the app with no right-click Paste menu, and the only search box with no way to clear it except selecting the text and deleting it. It is the most-used field in the app and the one that behaves least like the rest. A user pasting a title copied from elsewhere right-clicks, gets nothing, and concludes pasting is not allowed here; a user who has finished searching has no ✕ to get their full list back, while the Calendar's search box two tabs away at least offers the paste menu. | note_organizer.py:9946-9953: the entry gets track_theme, _guard_entry_astral and a placeholder, but no _add_paste_menu. Fourteen other fields do get one, including the Calendar's own History search at noteorganizer/ui/calendar_view.py:1025. Reported by survey 1. | Call _add_paste_menu(search_entry) — one line, matching the thirteen other call sites. The clear affordance is a second, slightly larger change: an ✕ that appears only while the box holds a real query. | deciding |
| C-12 | The note's date field and every box in the Repeat panel also have no right-click Paste menu, unlike the title, body, comments, checklist and find boxes beside them. Pasting a date copied out of an email is an obviously ordinary thing to want, and the field that most invites it is the one that refuses. The refusal is invisible: right-click simply does nothing, which reads as the app being stuck rather than the feature being absent. | Editor date row at note_organizer.py:10364-10400 and the recurrence entries built from note_organizer.py:11441 onward: none appears among the fourteen _add_paste_menu call sites (title :10314, body :10765, comments :10858, checklist :8875, find :13326, plus the Settings and Calendar ones). Reported by survey 2. | _add_paste_menu on the date entry at minimum; the recurrence number boxes are a weaker case, since they hold single digits, and are reasonable to leave as they are. | deciding |
| C-13 | The Share panel makes you tick notes one at a time, with no "select all" — while the selection bar a few centimetres above it has exactly that button. Two tick-box lists in the same sidebar, one of which can be filled in a click and one of which cannot. Sharing a whole notebook means a hundred clicks, then "Show 100 more", then a hundred more. | Share panel per-note Checkbuttons at note_organizer.py:7868-7962, paginated 100 at a time with a "Show 100 more" but no select-all; the bulk bar's "Select all / Unselect all" at note_organizer.py:10051-10124. Reported by surveys 1 and 5. | Reuse the bulk bar's label-flipping pattern ("Select all" / "Unselect all") over whatever page of notes is currently revealed. | deciding |
| C-14 | In Recently deleted you can restore one note at a time, or destroy all of them at once, and nothing in between — and you cannot read a note before deciding. The list grows to whatever the retention window holds, and the only bulk gesture available is the irreversible one. Recovering yesterday's forty deleted notes is forty clicks; wiping them is one. And a user facing two notes both called "Notes" has nothing to tell them apart, so the safe choice is to restore both and sort it out afterwards — more work than the screen should have cost. | noteorganizer/ui/settings_page.py:1136-1205 (per-row Restore and Delete; title, date and days-left only, no preview and no tick box) and :1320 ("Empty trash"). Reported by survey 4. | Two separable additions: tick boxes with "Restore selected" (the Duplicates panel already demonstrates the tick-and-act pattern in this same file), and a hover preview on the row (_attach_dup_preview at note_organizer.py:14907 already does exactly this for duplicates). | deciding |
| C-15 | The note list remembers whether you grouped it by category, and which groups you folded shut, but forgets your sort order and your filter every time you close the app. Three controls on adjacent rows of the same panel, two of which are remembered. A user who prefers Title A–Z re-picks it at every launch and cannot tell why that one preference does not stick when the checkbox beside it does. | sort_var and filter_var at note_organizer.py:9982-10000 carry no save_setting; group_by_category and collapsed_groups load from settings at :10008-10010. Reported by survey 1. | Persist both through the existing save_setting/load_settings path, validating on load that the stored sort key and filter still exist (a stored filter may name a deleted category — fall back to "All"). | deciding |
| C-16 | Marking a calendar day stops accepting emoji after the third, and nothing says why the fourth click does nothing. A dead click with no explanation reads as the app being broken, not as a rule being enforced. The popup's header says "up to 3", so the rule is stated once at the top and then enforced by silence. | noteorganizer/ui/calendar_view.py around :1338-1351 — toggle() refuses silently past the cap and returns "break". Reported by surveys 3 and 5. | Dim the unpicked chips once three are chosen, or put a one-line message under the grid when a fourth is attempted. | deciding |
| C-17 | The bulk bar can Trash, recategorise and export, but cannot duplicate; the single-note right-click menu can duplicate, pin and export, but cannot change category. There is no rule a user can learn about which actions come in a bulk form and which do not. It is a patchwork, so finding out costs a trip to each menu. | Bulk bar at note_organizer.py:10051-10124 vs show_note_context_menu at note_organizer.py:13959-14040. Reported by survey 1. | Not worth closing every gap — but two are cheap and obviously wanted: bulk Pin (see above) and a single-note "Move to category" on the card menu, which would also stop the bulk Category popup from being the only route to recategorising without opening the note. | deciding |
| C-18 | The Settings page has no hover explanations at all, although almost every control there is a wordless glyph — while the formatting toolbar in the editor explains all of its buttons on hover. The app teaches, in the editor, that a wordless button explains itself when you rest on it. Settings then breaks that lesson on the screen where the wordless buttons do irreversible things — a pencil and a bin, side by side, both silent. Two surveys reached this from opposite directions, which is the strongest agreement in the set. | Survey 4 grepped noteorganizer/ui/settings_page.py for tooltip/_tip/Tooltip and found nothing, against pencil/trash/lock/swatch icon buttons at :2465, :2515, :2520, :2523, :636-641 and the moon/sun canvases at :2329-2334. Survey 2 independently found _attach_tooltip called from exactly twelve places, all in the formatting toolbar. | Call the existing _attach_tooltip on the category and template row icons and the theme halves. No new machinery; the helper exists and is already themed. | deciding |
| C-19 | The Expand/Collapse toggle under the note body remembers your choice; the identical-looking toggle under the Comments box, built by the same helper, forgets it. Same control, same place, same wording, different memory — and by the helper's own stated test the comments box is a size someone chose, so the rule as written argues for persisting it. A user who works with long comments re-expands the box at every launch. | note_organizer.py:10782-10785 passes remember_key="editor_body_expanded"; :10866-10868 passes none. The helper's own docstring (note_organizer.py:9070-9072) states the rule: a key belongs on "one someone chose", not on "a box whose size is incidental". | Pass remember_key="editor_comments_expanded". If the omission is deliberate, say so in a comment at the call site, because the docstring currently reads as an argument against it. | deciding |
| C-20 | Buttons that add something are spelled three different ways: "+ Add" for a category, "＋ New template" and "＋ Add" inside the template editor, and "+ Add file" for an attachment — with two different plus characters. Purely visual, but the two plus signs are noticeably different widths on screen, so adjacent panels in the same Settings page look like they came from different apps. | ASCII plus at noteorganizer/ui/settings_page.py:560 and note_organizer.py:10897; fullwidth U+FF0B at settings_page.py:608 and :1018. Reported by survey 4. | Settle on the ASCII "+" everywhere and change the two fullwidth ones, in one pass rather than incidentally. | deciding |
| C-21 | Delete buttons in Settings are drawn glyphs everywhere except inside the template editor, where one is an emoji bin. An emoji renders in a different weight and colour from the app's own drawn icons, so the one row using it looks like it belongs to another screen. | Drawn glyph via _icon_button(row, "trash", danger=True) at noteorganizer/ui/settings_page.py:2520 and :636; a literal "🗑" Label at :992. Reported by survey 4. | Use _icon_button(..., "trash", danger=True) there too. | deciding |
| C-22 | The text-colour popup has a title line telling you what it is for; the highlight popup, opened from the button right next to it, has none. Trivial in isolation, but the two popups are siblings opened from adjacent toolbar buttons, and the un-titled one is the one whose swatches are harder to interpret out of context. | note_organizer.py:7082 onward renders "Pick a text color"; the highlight column at note_organizer.py:4797 has no header (it does carry "Clear highlight"). Reported by survey 2. | Add a matching "Pick a highlight color" header. | deciding |
| C-23 | The sort and filter buttons are labelled with their current value — "Recently updated ▾", "All ▾" — so the words "sort" and "filter" appear nowhere on the screen. "All ▾" sitting beside "Recently updated ▾" gives a first-time user nothing to work out what either does, and "All" in particular reads as a state rather than a control. Showing the current value is the right default for a dropdown; the problem is only that neither carries a label anywhere near it. | note_organizer.py:9982-10000, both built by _build_themed_dropdown with width_chars=0. Reported by survey 1. | A small "Sort" / "Show" caption above the row, or tooltips via the existing _attach_tooltip. Do not change the button text — the comments at :9978-10000 record real clipping fights the value-only labels were sized around. | deciding |
| C-24 | The share code generated in the sidebar cannot be dismissed except by closing the whole panel, while the identical code area under the editor has an ✕ — and the two warn about attachments in different words. Same feature, two surfaces, two behaviours and two sentences for one fact. The wording difference is the kind of thing that makes documentation impossible to keep straight. | Sidebar: note_organizer.py:7977 onward, "⚠ Attachments not included — use Export for files.", no ✕. Editor: note_organizer.py:8212 onward, has an ✕ and reads "⚠ Attachments aren't included in a code — use Export for files." Reported by surveys 1, 2 and 5. | One sentence, used in both places, and an ✕ on the sidebar area to match the editor's. | deciding |
| C-25 | Four written claims in the project no longer match the code: a docstring promising a Markdown export that does not exist, a comment describing a drag handle that cannot be dragged, a dead helper documented as the add-category control, and the project's own CLAUDE.md saying the app uses no native OS dialogs when five remain. None of it is visible to a user, but all of it misleads the next person reading the code — and CLAUDE.md is the file an agent trusts first. A native file picker for saving a .zip is genuinely the right choice, so the code is fine and the sentence is what needs correcting. | export_note_as_file's docstring promises three formats (note_organizer.py:8012-8022) while kinds holds only html and txt (:8024-8026). noteorganizer/ui/settings_page.py:1243-1245 says "The drag handle below still takes it anywhere from 100 to 800", but _add_resize_handle's own docstring says "no dragging" and "Height not persisted" (note_organizer.py:9113-9117). _add_row (settings_page.py:2132), documented as the "+ Add category" affordance, has no callers. Five filedialog sites remain: note_organizer.py:1325, :8029, :8341, :12784 and noteorganizer/ui/attachments.py:51. Surveys 1, 2, 4 and 5 each found part of this; I verified all four. | Four one-line edits, as a docs/comment change with no version bump: trim the docstring to the two real formats, fix or drop the drag-handle sentence, delete or mark _add_row, and amend CLAUDE.md to say native dialogs are used for choosing files and folders and nowhere else. | deciding |

## What held up under attack

Recorded because a review that praises nothing is not credible, and
because these are the things not to break later:

- **The privacy promise is real.** No `socket`, `urllib`, `requests`,
  `http.client`, `webbrowser` or `urlopen` anywhere, and not one URL
  string in the codebase — the README's strongest claim survives a
  hostile grep.
- **The atomic write is genuine.** With the folder ACL-denied, nothing
  was corrupted, no truncated file and no stray `.tmp` were left, and the
  previous file stayed whole.
- **The share-code decoder's stated defences work**: the length cap, the
  chunked decompression ceiling, the note cap and the shareable-slice
  re-projection all behaved as documented — a crafted code cannot smuggle
  an id, an attachment reference or a path. (Its one hole is the
  uncapped checklist, [T0-7](#tier-0--the-app-edits-or-deletes-data-without-saying-so).)
- **The occurrence save choreography does not lose work.** A reviewer
  expected data loss on every exit route, found none, and refuted their
  own finding.
- **Exception hygiene**: 236 `except` clauses across the entry file and
  the package, not one of them bare.
- **All eight themes are presentable** — no unusable palette, no
  half-themed panel, no unreadable pair beyond the contrast ratios above.
- **The layout survives a small screen**: 900×600 with a 500×400 minimum
  fits a 1366×768 laptop with nothing cut off, and every dialog sizes
  itself to its content.
- **Table round-tripping held**: save → reload → redraw, share-code
  encode/decode byte-identical, HTML export with real cells.

## Refuted — do not re-chase

Claims that reviewers filed and verification killed, kept so nobody
files them again: the missing-LICENSE/third-party-notice alarm (real
paperwork, wrong reasoning, premature severity); "three icon languages in
one toolbar"; MSIX breaking the data-folder logic three ways (rebuilt on
a real filesystem tree, it does not); "ships OpenSSL so the no-network
claim is false" (the modules are stdlib baggage, not calls — and the
proposed exclusion was disproved by executing it); the hardcoded window
title; attachment size/dedup complaints (per-note copies are a
deliberately enforced invariant); `day_colors`/`day_emoji` "keeping every
date forever" (every entry is visible and one-click removable);
Settings being nav-only by keyboard (Trash rows carry real focusable
buttons); and "UI chrome ignores the editor font" (real mechanism,
false user harm as filed).

## What this review did not cover

- **Nobody ran the packaged `.exe`.** Every finding is from source runs;
  the frozen build's `%APPDATA%` behaviour, its startup time and anything
  MSIX-specific are unexercised. The safety rule made using the real data
  directory unacceptable.
- **The visual half is thin.** The lens that drove the app end-to-end did
  it headlessly and never looked at a pixel; the lens that looked at
  pixels never loaded a realistic notebook.
- **Whole features went untouched**: templates, the History register, the
  calculator panel, the emoji picker and most of `core/tables.py`,
  `richtext.py`, `formatting.py` and `clipboard.py` got grep coverage
  only.
- **No screen reader was involved** — the accessibility findings are
  keyboard and contrast only.
- **The reviewers' own numbers** were measured on one fast machine under
  parallel load; the verifiers corrected several of them downward, and
  the performance figures here are the corrected ones.
