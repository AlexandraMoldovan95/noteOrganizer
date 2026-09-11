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
- [What held up under attack](#what-held-up-under-attack)
- [Refuted — do not re-chase](#refuted--do-not-re-chase)
- [What this review did not cover](#what-this-review-did-not-cover)

Status values: **open** · **fixed** (with the version) · **accepted**
(with the reason, like the [coverage ledger](../qa/COVERAGE_LEDGER.md)'s
ACCEPT rows) · **deciding** (waiting on a product call).

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
| T0-1 | **The first-launch cleanup deletes real notes.** `note_is_empty` checks title/body/comments/attachments but **not checklist**, while `_autosave_now` explicitly counts a checklist as real content — so the app lets you create a checklist-only note and then deletes it as "empty". The dedup signature is `(title, body, comments, category, date)`, also without checklist, so two notes differing only in their checklists collapse to one. Nothing goes to the Trash. It re-arms whenever `settings.json` is unreadable. | `core/model.py` `note_is_empty` + `clean_notes` signature vs `note_organizer.py:759`. Executed: 5 seeded notes → 2 after first load. | open |
| T0-2 | **Two windows on one notebook silently destroy each other's work.** No single-instance guard, no lock file, no mtime check, no reload. Both load into memory; every save is a blind full-file rewrite, so the last writer wins the whole file. Trivially reached from a taskbar pin or Start menu. | No locking primitive anywhere; `core/storage.py` `save_notes`. Reproduced with two real app processes by two independent verifiers. | open |
| T0-3 | **Restoring your own backup flattens every custom category to "General".** `settings.json` — where categories live — is written into the backup zip, but the import never reads it back; `normalize_note` then re-files every note whose category is unknown. "Import complete", no warning. | Export entry list vs `_poll_import_progress`; `normalize_note`'s category fallback. Reproduced device-A → device-B. | open |
| T0-4 | **Every save silently strips the body**: `body = get("1.0","end").strip()` removes leading indentation on the first line and every trailing blank line. A pasted code block or quoted email loses its shape on the next load. | `note_organizer.py:13565`. Executed. | open |
| T0-5 | **An untitled note cannot be emptied.** Clear it, switch away, come back — the old text is on disk and returns; the autosave discarded the emptying in silence. Ctrl+S instead answers "Write something before saving!" | The empty-note guard in `save_current_note`. Executed. | open |
| T0-6 | **"Restore previous" is a one-session promise.** The rescue copy really is written to disk in `note["_prev"]`, but `_prev` is not in `NOTE_DEFAULTS`, so `normalize_note` discards it on the next launch — while the button that offers it looks permanent. | `note_organizer.py` `_prev` write vs `core/model.py` `NOTE_DEFAULTS`. Executed across a restart. | open |
| T0-7 | **A pasted share code can brick the app permanently.** `checklist` is in `SHAREABLE_FIELDS` with no size cap anywhere — 20,000 items is a 60 KB code that passes every guard (length, decompressed size, note count, path traversal). Rendering the note kills the process, and because the note is saved first, **the app never starts again**. | `core/sharing.py` `SHAREABLE_FIELDS` + `decode_share_code` caps; `core/model.py` keeps every item. Executed, 3/3 crashes. | open |
| T0-8 | **The dangerous-attachment list misses today's delivery vehicles**: `.lnk`, `.url`, `.scf`, `.iso`, `.img`, `.chm`, `.inf`, `.appref-ms`, `.settingcontent-ms`. A shortcut file arriving in an imported backup opens through `os.startfile` with no warning at all, running whatever command line it carries. | `DANGEROUS_EXTENSIONS` in `note_organizer.py`; `ui/attachments.py` gates on it. | open |

## Tier 1 — the reason a stranger would quit

| # | Finding | Evidence | Status |
|---|---|---|---|
| T1-1 | **Every pause in typing freezes the app.** `refresh_note_list` destroys and rebuilds every card, and is called from 32 sites — every autosave, search, sort, filter, delete and import. The harshness audit named this the single most likely reason a month-in user would stop. One fix (incremental card updates instead of destroy-and-rebuild) retires the whole class. | Measured, fresh process per size: **77 notes ≈ 0.9 s frozen per typing pause**, 300 → 1.6–1.8 s, 1000 → 7.5 s; with a search term active, worse. Confirmed independent of note *size* — it is note count. | open |
| T1-2 | **`render_calendar()` runs on every autosave** with no visibility guard, rebuilding every day cell and expanding occurrences over the whole notebook while the user is on the Notes tab — although `apply_theme` already has exactly the guard it needs. | `note_organizer.py` save path vs the `_calendar_is_showing()` guard used elsewhere. | open |
| T1-3 | **The disk write is 4.2× slower than it needs to be**: `json.dump` streams thousands of small chunks through the encoder instead of building one string. Byte-identical output either way. | Measured: 5,000 notes 322 ms → 76 ms; 1,000 notes 63 ms → 16 ms. | open |
| T1-4 | **The one check guarding all of this cannot fail**: `qa/qa4.py:334` is `check(..., True)` — it measures the time, prints it into the label, and asserts a literal `True`. | Read the line. | open |

Also measured, and worth recording as a **non**-finding: one-file JSON is
not a scale problem. Load at 5,000 notes is 112 ms and everything is
linear; the widget layer is 25–100× more sensitive than the storage
format. Do not trade the plain, greppable, hand-recoverable file for a
database — fix the list rendering instead.

## Tier 2 — the shop window

| # | Finding | Status |
|---|---|---|
| T2-1 | **The first screen of the product is a maintenance report**: a blocking modal reading "Cleanup pass (runs once) … 0 note(s) remain, IDs renumbered 1–0". Found independently by four lenses. (The deletion behind it is [T0-1](#tier-0--the-app-edits-or-deletes-data-without-saying-so).) | open |
| T2-2 | **No application icon anywhere**: the Tk feather in the title bar and taskbar, PyInstaller's own icon on the `.exe`, and an empty Win32 version resource (FileVersion 0.0.0.0, no ProductName). No `.ico` exists in the repository and `NoteOrganizer.spec` has no `icon=`. | open |
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
