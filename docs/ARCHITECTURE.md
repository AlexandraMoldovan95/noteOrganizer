# Architecture

How Note Organizer is built, and why. Written for anyone reading the code for the first time —
including future-me.

## Contents

- [The shape today](#the-shape-today)
- [Startup](#startup)
- [Data layer](#data-layer)
- [UI layer](#ui-layer)
- [Background work: exporting and importing](#background-work-exporting-and-importing)
- [Autosave](#autosave)
- [Testing](#testing)
- [Case study: deciding the split with a call graph](#case-study-deciding-the-split-with-a-call-graph)

## The shape today

Note Organizer is a Python/Tkinter desktop app, entered through `note_organizer.py`. The code
lives in two places: the `noteorganizer/` package — a `core/` layer of data and rules, and a
`ui/` layer of mixins — and `note_organizer.py` itself, the entry point and the UI hub the
pieces hang off.

Both layers are fully extracted: fifteen `core/` modules and six `ui/` mixins. The annotated,
module-by-module inventory is [the code tour's project tree](CODE_TOUR.md#the-shape-of-the-project), and
[CODE_TOUR.md](CODE_TOUR.md) walks through the modules for someone learning the codebase. Three
of the core modules — `richtext`, `clipboard` and `tables` — landed with the rich-text and
tables work; the core layer is complete.

### `core/` — data and rules

`noteorganizer/core/` holds persistence, validation, recurrence, the calculator parser, and
sharing. **No module in here may import tkinter**, which is what keeps it testable headlessly
and reusable by a different front end. `test_data_safety.py` checks that rather than trusting
it — the property is easy to lose to one stray import and impossible to notice by hand.

### `ui/` — six mixins over one class

`noteorganizer/ui/` holds everything on screen, split one area at a time into **mixin** classes
that `NoteOrganizer` inherits from. The methods are unchanged: they still reach for
`self.colors`, `self.notes` and each other exactly as before, so each move was cut-and-paste
rather than a redesign.

This is organisation, not decoupling — the mixins share one object, and `self.colors` alone is
read in ~800 places.

Two rules keep the arrangement honest:

- A method lives in exactly one mixin. A duplicate is silently resolved by class order, with no
  error, so `tools/check_class_api.py` enforces this by comparing the class's whole method list
  against a recorded baseline.
- Mixins never define `__init__` — construction stays in `NoteOrganizer`.

### What stays on the hub

Scope is decided by what an area *owns*, not by keyword: the theming engine (`apply_theme`,
`set_theme`, `track_theme`) and the shared widgets (`_themed_dialog`,
`_build_themed_dropdown`) stay on `NoteOrganizer`, because the whole app uses them — only the
Settings *UI* for picking a theme moved.

Where a mixin needs a value that lives on the entry module and is only filled in by
`initialise()` (`APP_VERSION`, `APP_DIR`, `FIRST_LAUNCH_DATE`), it reads it through a small
local-import helper rather than importing `note_organizer` at module level, which would be
circular — and reading it at call time is what the original code did anyway.

### `note_organizer.py` — entry point and UI hub

`note_organizer.py` stays the entry point (`py note_organizer.py`) and re-exports the names
that have moved, so existing callers — including the ~270 `note_organizer.<name>` references
across the QA scripts — keep working untouched. That's deliberate: it means each extraction is
a pure move that leaves the whole test suite green, rather than a rewrite.

What remains in the file is ~20,500 lines of genuinely shared surface. It grew again through
the rich-text and tables work even as the pure logic behind those features went into `core/`,
and dropped by ~2,700 when the note list moved to `ui/note_list.py` (see the
[case study](#the-list-measured-again)).

### How it got here

This part is history. The app was a single file by design for most of its life — no build step,
no import graph to reason about, readable top-to-bottom — but at ~11,000 lines that stopped
paying for itself, and the app was reorganised into the package, module by module. How the move
groups were chosen, and why the split deliberately stopped where it did, is the
[case study](#case-study-deciding-the-split-with-a-call-graph) at the end of this document.

## Startup

`note_organizer.py` is inert to import. Resolving the data folder, running migrations, purging
stale copies, pointing `core.paths` at the result and recording the version all happen in
`initialise()`, which `NoteOrganizer.__init__` and `_main()` both call (it's idempotent, so
order doesn't matter).

This matters for more than tidiness: those steps move and delete files, and running them as a
side effect of `import note_organizer` is how a real notebook was once destroyed — see
[ISSUES_LOG.md](ISSUES_LOG.md). Anything that wants the data layer without building a window
must now call `initialise()` deliberately, which is what `test_data_safety.py` does.

## Data layer

### Storage

Everything is local JSON — next to the script when run from source, per-user under
`%APPDATA%\NoteOrganizer` when running as the built `.exe` (`core/paths.py` decides). A source run
can keep its notebook elsewhere: a git-ignored `notebook_location.txt` beside the script names the
folder. It exists because every notebook this project lost was lost in the working tree; a file
rather than an environment variable, because the tests run copies of the code that must keep
their data in their own folders, and a copy carries no such file while every child process
inherits a variable. The folder it names is never migrated into — an empty one would otherwise
copy in the `.exe`'s notebook from `%APPDATA%`:

| File | Contents |
|---|---|
| `notes_data.json` | All active notes |
| `settings.json` | Theme, username, categories, window prefs |
| `trash.json` | Soft-deleted notes, with a `deleted_at` timestamp |
| `templates.json` | Saved note templates |
| `attachments/` | Attached files, referenced by name from each note |

There's no database — the note counts this app is built for don't need one, and plain JSON
keeps the format simple to inspect, back up, and hand-edit if something ever goes wrong.

Two promises sit on top of the files themselves. Every write is **atomic** — surrogates
mended, dumped to a sibling `.tmp`, then `os.replace`d — so a crash mid-write leaves the old
file whole, and an unreadable file is preserved aside and announced rather than silently
emptied (0.66.104). And a **failed write is never silent** (0.71.125): every saver returns
`(ok, exception)`, every failure lands in `crash_log.txt`, and core reaches the screen through
the one channel it has without importing tkinter — the `storage.on_write_failure` callback the
app registers at startup, which shows an error toast naming the file.

Restoring from the Trash writes the notes first and the trash second, once each for any number of
notes (`restore_many_from_trash` writes nothing itself): a failed notes write then leaves the note
still in the trash file, where the old order could leave it in neither.

### Defensive normalization

`normalize_note()` is the single choke point every note passes through before it's trusted
anywhere else in the app — on load, on import, on paste-from-share-code. It coerces missing or
malformed fields (a `None` title, a checklist that isn't a list, a category that no longer
exists) into safe defaults rather than letting a bad record propagate into the UI and crash
something. This is what lets the app survive hand-edited or corrupted data files without
special-casing every call site.

### Ceilings live at the data door, not at the render

Several fields of a note are lists a share code can inflate for free: a
checklist, attachment records, styling spans. A 60 KB pasted code carrying
twenty thousand checklist items was saved before it was ever drawn, and then
killed the app on every launch after — the note was waiting, and drawing it
was what failed. So each of those fields has a ceiling, and every ceiling sits
in `normalize_note()` (and `normalize_template()`, which is the second door
into the editor) rather than at the point the data is drawn.

That placement is deliberate and was arrived at the hard way. The obvious
alternative — let the data through and refuse to DRAW past a limit — passes its
tests and is a silent data-loss bug: the editor reads a note's formatting back
out of the text widget when it saves, so a note drawn without its tags would be
saved without its spans. Trimming at the door keeps the round trip honest:
what is kept is what is shown is what is saved.

The styling ceilings also show why a ceiling has to bound *what the victim
pays*, not the nearest countable thing. `MAX_FORMATTING_SPANS` caps how many
spans a whole note may carry, and it is set high (10,000) on purpose, because a
Word paste of a long styled document legitimately produces thousands and
truncating those would be visible corruption. But Tk does not charge per span —
it charges per tagged range landing on one LINE, and per range drawn in total.
Two shapes reach the point where the editor never finishes drawing while using
a fifth of that cap: every span crowded onto one line, and every span stretched
to the end of the note so they all pile onto the last one. `MAX_SPANS_PER_LINE`
and `MAX_LINE_RANGES` bound those two, and the numbers behind all three are in
[the coverage ledger](archive/COVERAGE_LEDGER.md), now archived, rather than guessed.

An anti-bomb ceiling is not a performance promise, and the two should not be
confused: what makes a heavily styled note open quickly is
`_char_offsets` reading every span's offsets in one pass instead of re-reading
the note once per range end — 14.2 s of a 15.5 s startup, measured, before that
changed — and `_offset_indices` laying them back the same way, in one walk:
each span end used to be a walk from the top of the note, and Enter in a
numbered list, which lays every span again, took 3.4 s at 8,000 styled words.

### Recurrence model

A recurring note is stored once — the "base" note carries a `recurrence` rule (frequency,
interval, specific weekdays/month-days, an end condition) plus two small maps:

- `exceptions`: dates removed from the series entirely
- `overrides`: date → partial note, for edits that apply to one occurrence only
- `moved`: the date the rule gives a day → the date it is held on instead ("Move this day")

`expand_occurrences(note, range_start, range_end)` is the only place that turns a rule into
actual dates — everything else (calendar rendering, list previews) asks it for occurrences
within a window rather than re-deriving the logic. The series view edits the base note
directly; one day opened on its own from the calendar (day mode, `_day_mode`) writes an override.

A day saves to itself, asking nothing: every overridable field goes to the day, a series-owned
one (checklist, attachments) to the series, and the date and the repeat nowhere —
`_show_day_mode` keeps them in their fields, out of sight, so the save finds them unchanged, and
puts them back if anything reached them. A day whose edit ends equal to the series
(`day_matches_series`) keeps no override: kept, a copy of the series' own text would cut that
day off from every later edit of the series. Until 2026-10-12 a day's edits waited instead for
a question — "this occurrence or the whole series?" — asked only on leaving, and nothing on
screen said they waited ([Issues Log](ISSUES_LOG.md#the-day-that-waited-for-a-question)).

An override is keyed by its date and nothing moves it, so changing the start or the rule can
leave one on a date the series no longer has. Such overrides are **kept**, not moved and not
dropped — the owner's call (2026-10-12): moving guesses which new day an edit meant, and
dropping loses text, while kept they come back by themselves if the rule is put back.
`off_schedule_days(note)` names them, asking `expand_occurrences` about each date, so it
cannot disagree with the calendar; the series line counts them apart and offers the walk that
turns each into a note of its own or a Trash entry (`_show_off_schedule_days`), and the
calendar History marks them rather than opening them as days of the series.

A moved day (2026-10-13) is the same idea from the other side: the person, not a rule change,
puts one day on another date. `moved` maps the date the rule gives the day to the date it is held
on, and the day's own edit is kept under the date it is held on, so every surface that opens a
day by its date opens this one unchanged. `expand_occurrences` skips the rule's date and draws the
new one — while the rule still gives the original date and it was not deleted, so a move
outlives neither — and the moved day still counts as one of a "N times" series' N. A move whose
original date the rule no longer gives leaves its edit off the schedule, where the walk above
finds it. `move_day` re-keys the edit and drops the move when a day goes home; deleting a moved
day skips its original date and takes the move with it. Share codes carry no moves, as they carry
no exceptions or overrides; a backup carries all three.

### An import asks first, and acts after

An import that meets notes this device already has (a share code or a backup) asks every
question before it changes anything: `_take_known_notes` hands back the updates "Update" agreed
to, and the caller applies them (`_apply_known_updates`) only after its last question — the
duplicate check — is answered. A note that arrives exactly as it is here is never an update
(`shared_update_changes`): an update that changes nothing would still overwrite the rescue copy
that "↩ Restore previous" reads. Whether to add it again is asked once for all such notes
(`_unchanged_copies`, Skip by default); copies asked for leave without their identity and are
added past the duplicate check, having just been asked about. The duplicate check is asked about
the notebook as it will be (`_dup_keys_after`), since the updates are not applied yet when it
runs.

### A name lives in more than one place

A category's name is held by the notes (and their per-day overrides), the Trash, the templates,
the folded groups, the list's filter and the editor's own category box. A rename and a deletion
both move every holder in one method, `_refile_category_everywhere`; a rename also carries the
fold, the filter and the open note's box, and keeps the category's place in the order. A day of a
restored series filed under a category that no longer exists comes back under General, the rule
the note's own category has always followed.

### Colours: one form past the gate

`sanitize_color` admits `#rgb` and `#rrggbb` on every door a colour can arrive through (a day
colour in settings.json, a restored backup, a note's or a day's colour, a category's), and gives
`#rgb` back as `#rrggbb` — the same colour, in the only form the app itself writes. Every reader
that works a colour out by hand (the painted day's text contrast, the blends, a chip's darker
hover) then reads six digits; `contrasting_fg` also answers white for anything it cannot read,
so a future door cannot freeze the calendar's month. Formatting colours have their own gate,
which accepts six digits only.

## UI layer

### Hand-built popups, and the system's own dialog in two places

Every dropdown, color picker, confirmation prompt, and date picker in this app is a hand-built
`Toplevel` popup — never `tkinter.messagebox`, `ttk.Combobox`, or `colorchooser`. The trade-off
is more code to maintain; what it buys is a UI that's fully themed (dark/light variants apply
everywhere, including every dialog) and behaves consistently across the app.

The system's own dialogs appear in exactly two situations, both deliberate. Choosing a file or
folder — saving an export, opening a backup, picking a folder, attaching files — uses
`filedialog`, because the system's chooser knows the person's drives and recent places and a
hand-built one would be worse. And the last-resort startup-crash dialog uses the plain
standard-library messagebox, precisely because it must not depend on the app's own UI having
come up (see [ISSUES_LOG.md](ISSUES_LOG.md#a-crash-handler-that-would-have-crashed-itself)). This
heading used to read "No native dialogs, anywhere", which was wrong about the first while the
code was right.

The shared building block is `_place_dropdown_popup()`: given a popup and an anchor widget, it
positions the popup against the *app's own window bounds* (not the full virtual screen — this
specifically avoids popups landing on the wrong monitor in a multi-monitor setup), keeps
`-topmost` set so it can't get pushed behind the main window on a focus change, and live-tracks
the app window if it's moved or resized while the popup is open. New popups should use this
rather than reinventing positioning.

For yes/no/multi-choice prompts, `_themed_dialog()` renders an in-app overlay (not a real OS
window) and blocks via `wait_variable` until a button is clicked, returning the chosen value.
Since 0.71.119 it is also a safety contract: the messagebox-style wrappers honour `icon=` (the
glyph) and `default=` (which button keyboard focus — and therefore Enter — lands on; Escape
always returns the safe first option), and every irreversible confirm in the app passes
`icon="warning", default="no"` so a reflexive Enter can never fire the destructive choice. New
destructive confirms must do the same.

A question waits in a nested event loop, so the app goes on running under it, and the question
has to hold three things for that not to matter. **The pointer:** a grab on the card; when a
question asked inside another ends (a timer's "Export complete" over a waiting "Move to
trash?"), the grab goes back to the one still waiting (`_asking_dialogs`), because Tk has one
grab and its release leaves none. **The keyboard:** Tab and Shift+Tab walk the question's own
buttons and come back round, as a Windows message box does (Shift+Tab is `<<PrevWindow>>` too,
for X11's ISO_Left_Tab); Enter presses the focused button, Escape the first (safe) one, and only
the innermost question hears either; the app's global shortcuts stand still while any question
asks (`_a_dialog_is_asking`), and the window's close is refused, bringing the question forward.
**The subject:** every confirmation acts on what its question named, captured before asking —
the notes, the Trash entries, the attachment, the note being restored — and checks each is still
there; something that arrived during the wait was never asked about, and is left alone.

### The window-level lines a popup adds

A popup that needs the app window's own events (a click outside it, a resize, Escape) adds lines
to the window's bindings through `_bind_window_for_popup`, and each popup keeps its own list of
the lines it added, removed by `_unbind_window_for_popup` when the popup goes — by any route,
through its own `<Destroy>`. Every line names its popup and calls one command that is never
deleted, `_on_popup_window_event`, which looks the popup up and does nothing if it is gone. Two
Tk rules make this the shape: Tk expands every script of an event before it runs any, so
unbinding a handler from inside the same event deleted a command that event was still about to
call (a silent "invalid command name"); and one stored binding id per kind, as before, let a list
opened inside a popup overwrite its host's id, so the host's handler stayed bound for good and
every later dropdown was closed by the click that opened it. The same reasoning gives the
tooltip one hide command registered on the window (`_hide_tooltip_command`), appended to each
widget's click with the "+" written into the script — given a string, tkinter's `bind()` ignores
`add="+"` and replaces the widget's other click handlers.

A widget's own `<Button-1>` runs before the window's click-outside line for the same press. So
a widget whose press answers it — asks a question, or opens something in the popup's place —
returns `"break"`, and the click-outside does not answer the press a second time. When it did,
the questions came twice, and a template's bin beside its own half-written editor deleted the
template "for good" and then had the editor's "Save changes?" write it back.

### Right-click menus: one at a time

Each right-click builds its menu anew (`_new_context_menu`), and destroys the previous one first.
It is not destroyed when `tk_popup` returns: on Windows that call blocks until the menu is
dismissed, but on Linux it returns at once with the menu still open (measured in the CI image),
so destroying it there would make it vanish. Only one right-click menu is ever open, so the
previous one is done with when the next is asked for.

### Theme tracking — two different patterns, on purpose

`track_theme(widget, **option_map)` registers a widget so a later theme switch re-applies the
right colors to it. This is for **persistent** widgets — ones built once at startup and never
destroyed (the sidebar, the main buttons, the tab bar).

For content that gets **destroyed and rebuilt** on every refresh — the attachments list, the
History register's rows, anything inside a Settings section panel — widgets are colored with
plain `.configure(bg=self.colors[...])` calls instead. (The note list and the calendar's month
are not widgets any more but drawings, whose items take their colours when drawn: the list is
recoloured in place, below, and the month is drawn again.) Since this content is always rebuilt fresh, it
never needs live tracking; using `track_theme` here just means every rebuilt widget's tracking
registration outlives the widget itself. That was an actual bug this codebase had for a while
(see [CHANGELOG.md](../CHANGELOG.md) 0.4.0) — a growing, unbounded list of registrations for
windows that no longer existed, which measurably slowed the app down. Since 0.71.134
`apply_theme` prunes dead entries at every switch, so a stray registration now costs one switch
rather than living forever — a safety net, not a licence: re-registering per rebuild is still
churn the pattern never needs.

**Rule of thumb: `track_theme` for widgets built once — and when you do, track EVERY colour
option the widget sets (`insertbackground`, `selectcolor`, `highlightbackground`, the
`active*` pair), not just `bg`/`fg`; a partial map leaves the missing option frozen on the
build-time palette (the invisible-caret class of 0.71.125). Direct `.configure()` for widgets
inside anything with a `redraw()`/rebuild pattern.**

There's a third case, added in 0.32.49: content that is normally rebuilt on refresh but must
**not** be rebuilt just because the palette changed. `apply_theme()` used to call
`refresh_note_list()`, which destroyed and rebuilt every note card — about 85ms of a 121ms
theme switch, with the list visibly emptying and refilling. Nothing about a theme switch
changes note *data*, so `_recolor_note_cards()` now re-applies colors to the cards already
drawn, through the items each card's record in `_note_cards` names (the list is a drawing on
one canvas; see [Large lists](#large-lists-draw-what-can-be-seen-the-rest-on-demand)).

This is **not** the `track_theme` pattern that leaked: `_note_cards` is rebuilt from scratch
by every `refresh_note_list()`, and every update that stops short of one keeps it exact, so it
only ever holds the cards that are drawn. And since a drawing is not a widget,
`_recolor_stragglers()` never reaches the list at all — this is its only recolour.

Two ordering rules matter here — `_recolor_note_cards()` runs *after* `_recolor_stragglers()`
so a note's own color (recomputed from the note, not color-swapped) wins over the generic
remap, and the calendar is skipped entirely while off screen and caught up by
`_catch_up_deferred_refresh()`. See
[The theme-switch flicker, and three ways not to fix it](ISSUES_LOG.md#the-theme-switch-flicker-and-three-ways-not-to-fix-it).

### Rich text: two kinds of formatting, stored two different ways

A note carries formatting in two separate fields, because the two kinds of it answer different
questions.

#### Character styles: spans of offsets

`formatting` holds **character** styles — bold, italic, colours — as spans of character offsets
into the body: `{"start": 9, "end": 13, "style": "bold"}`. Offsets, not Tk's own `line.column`
indices, because a note reopened in a window of a different width wraps differently and every
column would move.

`formatting` also carries font size and family, as value-bearing spans like the colours. Unlike
the colours, those two *fight* bold and italic: they all set the widget's `font` option, and
two Tk tags that set the same option do not compose — one simply wins. That collision is why
`bold_italic` exists as a tag of its own, and adding size and family turns it from a two-way
problem into a four-way one.

Rather than a tag per combination in the *data*, all four stay separate spans and are merged
only at render time. `resolve_font_runs()` works out the stretches over which the answer is
constant, and one composite tag is built per stretch on demand — lazily, because creating all
192 combinations the app can offer costs about 190ms of startup for tags most notes never use.
Composite tags are configured at runtime, so they land later in Tk's tag order than `bold` and
`italic` and win the font option; the plain `bold` tag stays on the text underneath as the
marker the toolbar reads, which is what keeps "is this selection bold?" answering correctly
inside a resized run. With neither size nor family set, `font_tag_for()` returns the historic
names unchanged, so a note that never touches fonts tags exactly as it always did.

Reading back is the inverse: a composite tag yields size and family only, with weight and slant
taken from their own tags rather than saved twice. Because a composite tag is split at every
bold boundary inside it, extraction also **merges touching identical spans** — otherwise one
size across a paragraph reads back as several pieces, gets written that way, and splits further
on the next save.

The composite carries the weight and slant, so a change to bold or italic under it is drawn
only once the composite is fitted again. Ctrl+B and Ctrl+I swap the composites inside the
selection for ones with the new weight (`_weigh_font_tags`); typed and pasted letters are
refitted (`_fit_font_tags`) by stretches over which their tags stay the same, keeping the size
or font they did not pick — and leaving one plain font tag where typing or a paste laid bold
and italic on the same letters. Before they were, the toolbar and the save said bold while the
text stayed drawn as before until the note was opened again — and laying every composite in
the note again instead cost a long note set in a font 250 ms per Ctrl+B; fitting a character at
a time cost a long paste two to three times that. For the same reason, bold and italic over the
same letters are folded into one `bold_italic` span in `normalize_formatting()`, the list given
back in the order the editor reads spans in (in any other, an untouched note read as unsaved).
`resolve_font_runs()` works its stretches out in one sweep over the boundaries: checking every
span at every boundary made one size in a note of 8,000 styled words cost 1.7 s at every open
and every Enter in a numbered list.

Text put in between two pieces of one size or font that differ only in weight — right after a
bold word inside a bigger heading — wears neither piece's composite, since Tk passes a tag on
only to text inserted between two characters that both wear it. Every road in asks one helper,
`_take_run_between()`, for the run's size and font: the typing, a formatted paste, Ctrl+Shift+V,
the emoji picker, the calculator, and Tk's own paste, settled after idle between two marks
because Tk inserts after the handlers return. Fixed on the typing alone first, the same finding
came back from the pastes a round later.

#### Line styles: `paragraphs`

`paragraphs` holds **line-level** formatting — which lines are list items, at what depth, and
how they are aligned — keyed by line number, since that is the unit it applies to. Only
non-default properties are stored, so an ordinary paragraph produces no entry at all.

#### The marker lives in the body text

A bullet really is a `"• "` at the start of the line, and a numbered item really begins
`"1. "`. The alternative — drawing the marker without storing it — was considered and rejected:
`formatting` is stored as offsets into that same body, so a marker on screen but not in the
text would put every offset after it out by the marker's length, on every line, forever.
Keeping the text and the widget identical means the offsets need no translation at all. It also
means a list survives export, share codes and plain-text copy as something still readable.

Because the marker is in the text, **the text is what decides** whether a line is a list item;
the tag over it is only the hanging indent. Reading the tag instead let a pasted line come back
as a bullet with no bullet in it — see
[The bullet that had no bullet in it](ISSUES_LOG.md#the-bullet-that-had-no-bullet-in-it).
Renumbering therefore rewrites real characters, which moves everything after them, so
`renumber()` returns the shifts it caused, for anything holding spans as offsets
(`shift_spans()` moves them to match; otherwise bold slides sideways the moment `9.` becomes
`10.`). The editor itself writes only the characters of each marker that changed, so Tk carries
every tag, the view and every drawn table along by itself — see
[The list that rewrote the whole note](ISSUES_LOG.md#the-list-that-rewrote-the-whole-note).

#### One tag per combination, built lazily

List kind and depth both set the same two Tk options (`lmargin1`/`lmargin2`), and a widget
applies only the winning tag's value for an option — so they cannot be separate tags that
stack. `_paragraph_tag()` makes one tag per combination on demand and records what it was built
from, which is also what lets them be rebuilt when the editor's font size changes: the margins
are in pixels and the marker they leave room for is not. Alignment *is* a separate tag, because
`justify` is a different option and composes cleanly.

#### Numbered levels are not lettered on purpose

The usual nested scheme — `1.` then `a.` then `i.` — is ambiguous with ordinary prose, and a
note is exactly the kind of document where a line can legitimately begin `"a. "`. Since
recognising a list from its own text is what keeps markers and tags from drifting apart, that
recognition has to stay reliable. Bullets vary by depth (`•`, `◦`, `▪`) because those glyphs
are not typed by accident; numbered depth shows through indentation and the count restarting
under each parent instead.

### The clipboard: a small platform part, and a large testable one

Pasting formatted text needs something Tkinter cannot do — its clipboard only ever offers plain
text, while Windows keeps `CF_HTML` alongside it. Reaching that needs the Win32 API, through
`ctypes`, which is in the standard library and so costs no dependency.

That work is split deliberately across two modules:

- **`core/clipboard.py`** is the platform part, and is kept as small as possible: open the
  clipboard, read or write one format, close it. Every function returns None or does nothing
  off Windows, or when the clipboard is momentarily held by another program, so a paste that
  cannot find rich content simply falls back to the plain-text paste the app always did.
- **`core/richtext.py`** is the conversion, and knows nothing about clipboards. It turns HTML
  into a note's text, spans and paragraph entries, and back again — strings in, strings out.

The split is what makes the feature testable. Anything that depends on the platform's exact
font metrics is fragile to pin in an assertion — the same bar measures differently on different
machines (see
[Layout arithmetic belongs in core, not in the widgets](#layout-arithmetic-belongs-in-core-not-in-the-widgets))
— so keeping that surface to one small module leaves the part with all the decisions in it —
what maps to what, how lists nest, where the offsets go — under test on every machine, and the
CI suite now runs on both Windows and Linux. `test_richtext.py` covers it with no window and no
clipboard at all.

#### The mapping is lossy on purpose

HTML can express unlimited styling; a note has a fixed vocabulary. Anything with no equivalent
is dropped rather than approximated — the same choice `normalize_formatting` makes about
malformed spans, and for the same reason: guessing produces notes nobody asked for.

### Colours that are computed, not looked up

`apply_theme()` re-applies the palette to every widget registered with `track_theme`, and
`_recolor_stragglers()` catches strays by remapping any other theme's palette values onto the
current theme's — but the net repaints **only `bg` and `fg`**. Every other colour option
(`insertbackground`, `selectcolor`, `highlightbackground`, `activebackground`…) is invisible
to it, which is why partial tracking froze the caret at its build-time colour, and why the
net can quietly mask a missing registration when two themes share a hex — checks must assert
the mechanism there, not the behaviour (see
["The safety net that hid the missing mechanism"](ISSUES_LOG.md#the-safety-net-that-hid-the-missing-mechanism)).

Settings does not work that way throughout. It derives two surfaces by blending: a well inside
a card is `card` mixed toward `text`, and a hairline is `card` mixed toward `subtext`. Those
results belong to no palette, so the straggler pass cannot recognise them — which is exactly
how the Settings information bars stayed dark on a light theme — see
[The Settings panels that stayed dark on a light theme](ISSUES_LOG.md#the-settings-panels-that-stayed-dark-on-a-light-theme).

Both derivations therefore live in `core/themes.py` as `inset_surface()` and `hairline()`, and
`_recolor_stragglers()` remaps each theme's derived surfaces alongside its palette. **If you
compute a colour rather than looking one up, derive it in one place and teach the theme switch
about it there** — otherwise it is invisible to everything that fixes colours by matching known
values.

### Contrast, measured

Every theme's text is measured against WCAG 2.1: the contrast ratio worked out from relative
luminance, by formula rather than by eye. All of the app's text is 8–11 pt, which WCAG counts as
normal size, so every pair of words owes 4.5:1, the AA level; a drawn glyph owes 3:1, WCAG's
non-text contrast. `tools/check_contrast.py` measures each pair the app draws and prints the
table below (`--markdown`). In CI it fails on any pair below its level that is not listed with
its reason, and on a listed pair that has started to pass, so the list can only shrink — it is
empty now. It also checks that a colour value means one role across all eight themes, which
the theme switch depends on, since it remaps colours by value.

The four light themes' secondary text was below AA, on the sidebar most of all, where Sort and
Show sit. Each is now one step darker: Soft Lavender `#6b6b85` → `#676780`, Sky Blue `#5a748c` →
`#536b81`, Fresh Mint `#5b7d6c` → `#527061`, Warm Cream `#8a7660` → `#776653`. Text and secondary
text now pass in every theme.

What did not pass, for a long time, was every pair that used the accent, the warning red or the
confirming green — 71 of them — because that waited for a design decision rather than a
calculation. Each of those colours was used two ways: as text on a surface, and as a button's
fill under white text. On a light theme one darker shade serves both, but it changes how the
theme looks — Warm Cream's orange would turn brown. On a dark theme no single shade can: text
on a dark surface wants a lighter shade, and a fill under white text a darker one.

The decision was made by eye — the owner's — from five proposals that a panel of AI reviewer
personas (Claude subagents) put forward, photographed on the running app in all eight themes,
with these numbers beside them. Each role now has two colours: a **fill** (`accent`,
`danger`, `success` — a button, a banner, a selected tab) and a **text** shade (`accent_text`,
`danger_text`, `success_text`). The words *on* a fill are not written down at all:
`letters_on` in `core/themes.py` picks white or near-black by the same measure this table uses,
and the theme switch asks for them by name (`on_accent`, through `palette_value`) or, on a
widget it does not track, by the fill they sit on (`_recolor_stragglers`). Most themes keep the
fills they had; Warm Cream stays orange, and only its small orange words became a brown-orange
(`#8a4600`), the cost of reading on cream.

The proposal chosen added one rule the numbers alone did not ask for: **the `danger` fill is
dark with white words in every theme, the `success` fill light with dark words**, so they
differ in lightness as well as hue. Simulated for the two common kinds of colour blindness
(deuteranopia and protanopia, Machado 2009), Save and Delete had been the same khaki in all
eight themes; they now differ by at least ΔE2000 20.7 (below 10 reads as the same colour). For
the same reason Save is turquoise rather than green on the four themes whose accent is green or
orange.

The same reviewers, shown the result on the running app, found the next layer: on a light
theme the dark red Delete was now the loudest thing in the window (7.3:1 against it) and Save
the palest (2.3–2.6:1). So the editor's Delete became a quiet button with the warning's text
shade — the note goes to the Trash, and can come back — and Save is the one filled button
there. Midnight Purple's accent moved lighter, `#8771ff` → `#a48fff`: the near-black words on it
had read as muddy in the README's own screenshot, and the lighter shade raises them to 6.6:1 and
the selected note's ring to 5.0:1.

That left a rule worth stating, and a third look caught it stated wrongly: these docs said the
dark fill stayed "where a deletion is final", naming the calendar's day and the selection bar,
both of which only move notes to the Trash. The rule is now true in the code: **the dark red
fill marks a single deletion that cannot be undone** — a row's Delete in the Trash, an
attachment's ✕ — and the moves to the Trash wear the warning's words instead: the editor's
Delete, a day's note in the calendar, the selection bar's Trash, and the Duplicates clean-up,
outlined as Empty trash is so that it still reads as a button (finding C-6 had it blend into
its panel once). A fourth look held the sentence to every button and found two that keep their
own look by design, so they are named rather than swept under "every": Empty trash, final for
everything in it, is outlined — findable, not inviting — and asks first; and the Duplicates
panel's "Move ticked…" is that panel's main action, in the accent, now above the clean-up.
Two smaller strays went the same way: the selection bar's Category menu, filled though it is
no main action, is quiet like Export; and the question before attaching only some of the files
picked was asked as a warning, which dresses its Yes in the deletion red, and is a question now.

Measuring every pair the app draws, rather than the ones the table already had, found three
it had never measured: the selected Settings section's name on its tint of the accent, a
warning button's words when pointed at, and the find bar's current match — the note's own
text colour on the full accent, below 4.5:1 in every theme. The match's words now come from
`letters_on` too.

Then the app was checked for colour-blind readers, as far as a model can check it: photographs
of the running app simulated for protanopia, deuteranopia and tritanopia, each read by an AI
reviewer (a Claude subagent) that saw only those pictures, and a fourth with the originals as
the control. A model reading a simulation is an approximation, not a colour-blind person — the
test plan's case 625 asks a real one. None was blocked; what they hesitated over was wherever
colour carried a meaning alone. The find bar's current match is now **boxed** as well
as filled (Tk draws a `solid` relief dark on any fill), as a table cell's match already was.
The open Notes/Calendar tab is now the **taller** one: clam maps its own padding for a selected
tab, which beat the app's and drew it smaller, so its shape said the opposite of its colour —
the app restates it in `style.map`. And the letters for a colour the person picks have one
answer: `contrasting_fg` had a brightness threshold of its own, put white on 9 of the 20 day
colours (2.2:1 on `#00bbf9`), and is now `letters_on` by name — two formulas for one question
disagree somewhere. The colour picker's tick, the only sign of the colour in use when two
swatches look alike, takes the same letters. The simulation also measured what holds: on the
dark themes Save's fill and Delete's words are nearly one colour to a deuteranope
(ΔE2000 2.7–3.4), and the deuteranopia reviewer still found Save first, because it is the one
filled button.

| Text, and where | Midnight Purple | Ocean Blue | Forest Green | Warm Charcoal | Soft Lavender | Sky Blue | Fresh Mint | Warm Cream |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| text on the window | 14.7 | 15.3 | 15.1 | 15.2 | 14.2 | 12.4 | 12.7 | 12.5 |
| text on a card or panel | 11.8 | 11.3 | 10.8 | 12.2 | 15.5 | 13.5 | 13.6 | 13.5 |
| text in the sidebar | 13.1 | 13.3 | 12.7 | 13.4 | 12.8 | 11.1 | 11.3 | 11.0 |
| secondary text on the window | 6.5 | 7.1 | 7.5 | 7.2 | 5.0 | 5.1 | 5.1 | 5.1 |
| secondary text on a card (a note's preview) | 5.2 | 5.2 | 5.4 | 5.8 | 5.5 | 5.5 | 5.5 | 5.5 |
| secondary text in the sidebar (Sort, Show) | 5.8 | 6.1 | 6.3 | 6.4 | 4.6 | 4.6 | 4.5 | 4.5 |
| accent text on the window (the repeat summary) | 7.4 | 7.7 | 7.8 | 7.0 | 7.0 | 6.6 | 6.6 | 6.6 |
| accent text on a card or panel | 5.9 | 5.7 | 5.6 | 5.6 | 7.6 | 7.1 | 7.1 | 7.1 |
| accent text in the sidebar | 6.6 | 6.7 | 6.5 | 6.2 | 6.3 | 5.9 | 5.9 | 5.8 |
| the selected Settings section's name | 5.0 | 5.2 | 4.8 | 4.8 | 5.1 | 4.8 | 5.1 | 5.1 |
| warning text on the window | 7.4 | 7.9 | 8.4 | 7.7 | 6.7 | 6.7 | 6.8 | 6.8 |
| warning text on a card or panel | 6.0 | 5.8 | 6.0 | 6.2 | 7.3 | 7.3 | 7.3 | 7.3 |
| warning text in the sidebar | 6.7 | 6.9 | 7.0 | 6.8 | 6.1 | 6.0 | 6.1 | 6.0 |
| a warning button's words, pointed at | 5.8 | 5.8 | 6.0 | 5.9 | 5.7 | 5.7 | 5.7 | 5.7 |
| a bin on a card, pointed at (a glyph, owes 3:1) | 5.7 | 5.8 | 6.0 | 5.9 | 5.5 | 5.5 | 5.5 | 5.5 |
| a bin in a list row, pointed at (a glyph, owes 3:1) | 6.3 | 6.6 | 6.9 | 6.4 | 4.6 | 4.5 | 4.6 | 4.6 |
| confirmation text on the window | 10.4 | 10.0 | 10.6 | 11.0 | 5.6 | 5.6 | 5.4 | 5.4 |
| confirmation text on a card or panel | 8.3 | 7.4 | 7.6 | 8.8 | 6.1 | 6.1 | 5.8 | 5.8 |
| confirmation text in the sidebar | 9.3 | 8.7 | 8.9 | 9.7 | 5.1 | 5.0 | 4.8 | 4.7 |
| words on an accent button (and the find bar's current match) | 6.6 | 5.7 | 7.5 | 6.3 | 5.7 | 5.0 | 5.6 | 5.6 |
| words on an accent button, pointed at | 8.8 | 7.3 | 9.4 | 7.9 | 7.1 | 6.7 | 7.2 | 6.9 |
| words on a destructive button | 6.8 | 6.8 | 6.8 | 6.8 | 7.9 | 7.9 | 7.9 | 7.9 |
| words on a confirming button | 9.7 | 8.7 | 9.7 | 9.9 | 6.2 | 6.2 | 7.0 | 7.1 |
| words on a confirming button, held down | 7.5 | 6.8 | 7.5 | 7.6 | 4.9 | 4.9 | 5.4 | 5.6 |
| text of the other find matches | 6.5 | 6.7 | 5.8 | 6.9 | 9.1 | 8.2 | 9.4 | 9.3 |
| text in the find box when nothing is found | 10.7 | 10.3 | 10.3 | 10.4 | 12.1 | 10.6 | 10.6 | 10.5 |

A note's own colour, or its category's, is the person's choice and so is not in this table, but
it is shown as words: the tags line on its card. Picked for its look, it often did not read —
the default Personal yellow was 1.6:1 on a light card. The stripe still wears it whole; the
words wear `legible_on(colour, card, text)` (in `core/themes.py`): the colour itself when it
reads at 4.6:1 — a step over AA, for canvas text at 8–9 pt — and otherwise the nearest shade
that does. On a light card that shade is darker in the same hue, a little richer; it was first
mixed toward the theme's text, which is bluish, and the yellow came out khaki. On a dark card it
is mixed toward the theme's light text. test_data_safety holds every swatch the app offers to
4.6:1 on every theme's card, and the warm ones to their hue and saturation.

The last row is the find box's ground while its words are found nowhere: a tint of the warning
red over white on a light theme (a truer red there, its pink taken out) and over near-black on a
dark one (`miss_surface` in `core/themes.py`). It used to be one fixed dark red on every theme,
which put dark words on a dark ground on the light ones (1.2:1); mixed into each theme's own
surface instead, the red went grey on the blue and green themes. The tints were mixed from the
warning reds of the time, and since those reds darkened for contrast they are written into each
palette as `find_miss`, so a shade chosen by eye did not move. The surfaces the app does still
mix — the find matches, the Settings tints — are measured here like any other, through the
gate's `DERIVED` table.

### Layout arithmetic belongs in core, not in the widgets

The formatting toolbar wraps when it will not fit on one row, so no control can be out of reach
at any window width, in any font, at any display scaling. The decision of *what goes on which
row* is `split_toolbar_rows()` in `core/formatting.py`, and it takes widths as plain numbers
rather than measuring widgets.

That split is deliberate, and it was learned the hard way. A check that measures widget widths
is testing whatever font the machine has: the same bar is 577px here and 827px under Xvfb, and
which control lands on a row boundary — and therefore whether the bug shows at all — moves with
it. Given numbers, the same inputs give the same answer everywhere, so the behaviour can be
pinned down exactly. The widget side keeps only the measuring and the packing.

### Paste from a PDF: lines are not paragraphs

A PDF has no paragraphs — only lines placed on a page — so pasting from one hands over the
column's line breaks as though the writer meant them. `reflow_wrapped()` (in
`core/richtext.py`) rejoins what the column broke while leaving real breaks alone, judging each
line by measurable signals rather than guesswork: would the next line's first word have fitted
(a break with room to spare was chosen, not forced), does the line end in sentence punctuation
(paragraphs almost never stop mid-sentence), and is the next line indented past the block's own
left edge (many documents mark a new paragraph exactly that way). A run that does not look like
a wrapped column at all — lists, addresses, poems, anything under three lines — comes back
untouched: a break someone meant is worse to lose than a break left in.

It runs on both paste paths, but only when the clipboard carried no real structure of its own —
a source that sent block markup already has paragraphs, and rejoining would slide its
formatting offsets. The trade-off is stated rather than hidden: without indentation, a
paragraph whose last line lands nearly full cannot be told from a line the column broke, so the
function can merge two paragraphs — never split one — and `test_richtext.py` asserts that as a
property across eight column widths: no word lost, no word altered, no paragraph ever cut in
half.

### Tables: plain text is the store, a drawn grid is the view

A table in a note is stored as ordinary lines of text in the note body, in Markdown's own table
syntax:

```
| Day       | Lunch  |
| :-------: | ------ |
| Monday    | Soup   |
```

What the user *sees* is none of that: the pipe lines are hidden, and a canvas-drawn grid is
embedded in their place — real cell borders, a highlighted header, merged cells, one floating
entry box that materialises over whichever cell is being edited (the spreadsheet architecture:
hundreds of cells are cheap to *draw*, and only one of them ever needs to be a live widget).

Keeping the text as the single source of truth is the load-bearing decision. Search finds words
inside cells because they are simply words in the note. Share codes, backups, export and word
count carry tables with zero table-specific code. A table pasted from Excel or a web page
becomes text and therefore a grid; a table copied out arrives in any Markdown-aware tool as a
table. And the second row — `| :---: | --- |` — is not decoration: the dash count stores each
column's hand-dragged width (with one reading nuance since 0.71.134: a minimum-width cell of
three characters or fewer is markdown's conventional spelling, not an authored size, so it
parses as "no width opinion" and the column sizes to its content — authored widths floor at 4
so they always round-trip as authored), the colons store its alignment, and a `~` marks a
hidden column, so even *layout* survives every trip through plain text.

The `0.55.81` round extended the same storage idiom in three directions, none of which changed
the note format:

- a line break *inside* a cell is Markdown's own `<br>` marker in the value (rows grow to their
  tallest cell);
- a cell whose whole value is `[ ]` or `[x]` — Markdown's task syntax — is drawn as a real
  checkbox that a click toggles, and becomes an ordinary text cell again the moment the marker
  is overwritten;
- character styles inside a cell (a single coloured letter, a bold word) are ordinary
  formatting spans on the hidden pipe text, rendered as per-run canvas items.

The floating editor grew to match: a rich `tk.Text` that opens wearing the cell's styles,
styles just the selection inside it, dresses typed characters in the style they land beside (or
in the *active colour*), and hands the style layout back to the body tags on commit.

One offset lesson sits under all of it: every span offset is counted in *Python characters* —
the same space the saved body string lives in — because Tk's `count("chars")` counts UTF-16
units (an emoji is two) while its `+Nc` index arithmetic counts characters, and extracting with
one against spans applied with the other made every emoji-bearing note re-save itself, one
character further, on every launch — see
[The version that updated itself](ISSUES_LOG.md#the-version-that-updated-itself). The same
`+Nc` counts a drawn table's window as a character, which the saved offsets never do, so the
walk that lays spans back hops again over every window it passes: a font size set under a
table landed one character early per table above it until it did — see
[The character only the drawn tables had](ISSUES_LOG.md#the-character-only-the-drawn-tables-had).

The grid is rebuilt (never patched) at settled moments — load, paste, leaving the block, a
structural edit — and every editing gesture writes through to the hidden text first, so the
drawn view can always be thrown away and rebuilt from it. The costs live where they can be
tested: Tk counts text columns in UTF-16 units (an emoji is two of them), embedded windows
occupy an index but are skipped by character counts, and a rebuild mid-gesture destroys the
canvas under the mouse — each of those has burned this codebase once, and each now has a
regression check in `qa/qa1.py` and a war story in [ISSUES_LOG.md](ISSUES_LOG.md).

The caret never rests on a drawn table's hidden text: a guard (`_caret_out_of_hidden`) walks it
to the line under the table. A selection is the one case where that is not enough, because a
selection has two ends and the guard moved only one: it now keeps the caret with the selection's
moving end (`_selection_end_at_table`). A first press towards a table stops at its near edge, so
no selection takes a table in unasked — a grid shows no selection of its own — and a second press
at that edge crosses it, so the keyboard can still select across a table; a mouse drag stops at
the edge it came from. See
[The selection the caret left behind](ISSUES_LOG.md#the-selection-the-caret-left-behind).

### Undo: Tk's stack for the text, a journal beside it for the formatting

Tk's undo stack holds text, never a tag. A journal beside it (`_fmt_undo` / `_fmt_redo`) notes
the body's formatting before and after every undo unit of the app's (`_undo_atom`), and
`_body_undo_redo` lays a snapshot back only on the very text it was taken from — matched by the
text's signature, never by counting steps. Tk's own deletes (Delete, BackSpace, typing over a
selection, Cut) are no unit of the app's, so a bindtag put first on the body,
`NoteBodyStyledDelete`, sees each key before the body's own bindings and the Text class do: when
one is about to delete text that carries formatting, `_note_styled_delete` notes the formatting
and starts a step with a separator; a run of BackSpaces stays open (Tk merges contiguous deletes
into one unit) and closes at the first other event, at an app undo unit, at the autosave's
boundary, or at the next Ctrl+Z / Ctrl+Y. Plain text is left to Tk entirely.

Three details keep every route inside that net. The tag's `<<Cut>>`, `<<Clear>>` and `<<Paste>>`
bindings say they are virtual (`virtual=True`): a key that means Cut or Paste reaches them as the
key's own press, and read by its type, Ctrl+X was a control character typed over nothing. A
paste that falls through to Tk's own gives the run back (`_on_body_paste`): the app's paste routes
are undo units, and opening one ends any run before Tk has deleted anything. And Tk's own Ctrl+H,
Ctrl+K and Ctrl+T, bound by text.tcl on every platform, are worked out as text.tcl works them
(`_tk_control_delete_range`).

What a step costs is what it changed, not what the note holds. A snapshot (`_fmt_state`) is the
text's signature, the embedded windows' positions, and each journal tag's ranges as Tk's own
`line.col` string — all read in one Tcl round trip (`_FMT_RANGES_TCL`); a tag's string equal to
the previous snapshot's is that same object, so steps share what they did not change.
`_fmt_restore` removes and adds only the ranges that differ, tag by tag, and moves a snapshot's
indices past a table's window where Tk's undo put the table's text back without it. The five
actions that only restyle (`_toggle_body_style`, `_apply_body_color`, `_apply_body_font`,
`_set_paragraph_align`, `_grid_apply_style`) open a tags-only unit, which leaves Tk's
autoseparators alone: any configure makes Tk lay out every line of the note again. The tags the
journal keeps are written down once, in `_fmt_journal_tag`.

Tables add one rule. A drawn table's first line holds its grid's window at column 0, and Tk
records every edit by its index, so a step is replayed in the state it was recorded in. When a
unit takes the grids down (`_teardown_table_grids`), it is told first
(`_undo_atom_grids_coming_down`): what it did so far becomes a step of its own, ended by a
separator on Tk's stack, and the rest of the unit is a step marked `grids_down`. A unit that
begins with no table drawn is marked so from its start, and split where it goes on to write into
a drawn table's first line with the window there (`_note_edit_with_window`); a unit that lines
up a table not yet drawn is marked too (`_mark_unit_window_free`). A step no unit of the app's
noted — typing, Tk's own deletes and paste — never touches a drawn table's line, because the
caret guard keeps the caret off them, so it is replayed with the tables down, as is a run of
Tk's styled deletes the app notes. Past the journal's 100 full steps a text step stays as a
stub (`_trim_fmt_journal`): its text's signature on each side and how it was recorded. Stubs are
not capped, because Tk's own stack is not (`maxundo=-1`); a dropped step read as typing and was
replayed in the wrong state. `_body_undo_redo` takes the grids down before Tk replays a step so
marked, and draws them again after every step. It also forgets the line the caret was last seen on: a table is tidied when the
caret leaves it (`_align_table_on_leaving`, at every key's release), the tidy is a recorded edit,
and a recorded edit empties every redo stack — so the caret an undo moves must never read as the
person leaving a table. The grids themselves are destroyed through tkinter when taken down
(`_remove_grid_windows`): deleting their window's character ends the widget inside Tk only, and
left its callbacks registered for good.

One line of a note can be the drawing's rather than the person's: the empty line put under a
table that ends the note, so the caret guard has somewhere to put the caret
(`_add_line_under_last_table`). The drawing is `_undo_hidden`, so Tk never records that line, and
Tk's idea of the text is one line shorter than the note. While nothing has changed the text
since, the app holds the line (`_undo_tail_held`): the journal counts the note without it, and
the next Ctrl+Z or Ctrl+Y takes it out before Tk replays a step (`_drop_undo_tail`). Left in, a
redone Enter doubled it, and every step after that read as typing. What says "nothing changed"
is Tk's own modified flag, reset when the line is drawn: every insert and delete sets it,
recorded or not, and a redraw leaves it as it found it. A position cannot say it: a word typed
on the line and erased leaves the same text, but Tk now holds steps on that line, and an earlier
version that followed the line with a mark took it out from under them — the word came back
glued to the table's last row. Once the text changes, the line is the note's for good
(`_settle_undo_tail`): every state the journal noted before then counts one more line break at
its end (`_undo_sig_is`), because that is how Tk will give each of those texts back.

### Large lists: draw what can be seen, the rest on demand

The Trash (Settings → Recently deleted) and the multi-note Share panel both cap how many rows
they build at once (25 and 100 respectively), with a "Show more" button to reveal the next
batch, rather than rendering every entry immediately. This was enough to take the Trash panel
from ~1.8s to ~100ms with 600 entries. "Show more" adds the next batch under the rows already
drawn — drawing them all again flickered — unless the list has moved under them since (a note
deleted while the panel is open), when it draws them all once more.

The main note list does the same job without a button, because it is the app's main way
around and a button every thirty notes would be felt — and it is **drawn**, not built of
widgets. In Tk on Windows every widget is its own OS window; a card built of widgets was six,
and everything the list did scaled with them: rebuilding it, showing it again after the
Calendar or Settings, scrolling it fast (Windows moved hundreds of child windows per step, and
the picture tore). The cards are rectangles and text on the list's one canvas now
(`_draw_note_card`, from `_card_texts`, the one definition of what a card says), laid out in
records that know where each row stands.

On top of that, a rebuild draws `LIST_FIRST_DRAW` rows (30); the rest wait in `_list_pending`,
and `_list_view_changed` — the canvas's `yscrollcommand`, which hears every way the view can
move: wheel, scrollbar, a taller window, a drawn step lengthening the content — draws
`LIST_DRAW_STEP` more whenever less than a screen of drawn list is left below the view. The
keyboard's ↓ draws ahead of itself.

Rules that keep it honest:

- **One definition of what the list shows.** `_list_rows()` (built on `_notes_on_the_list()`)
  is read by the rebuild, the top-up, the one-card save and Select all. Nothing asks the
  *cards* which notes are on the list — "all" means every note the list shows, drawn yet or not.
- **The drawn part is a prefix.** `_list_drawn` (records, in screen order) followed by
  `_list_pending` is exactly `_list_rows()`. Every update short of a rebuild — a delete
  (`_remove_note_cards`), a save (`_redraw_saved_card`) — keeps that true, moves the rows below
  the change with `_reflow_list` (one repaint), and asks for a top-up itself when it leaves rows
  waiting, because the canvas reports only when something changes size.
- **Screen order is the records' order.** `_card_order()`; a card has no widget to ask.
- **The drawing's extent comes from the rows, not from Tk.** `_list_extent()` is (0, 0, width,
  bottom of the last row), and the scrollregion, the top-up and every scroll guard below read it.
  A drawing's `bbox` starts at its first item, four pixels down, where the old frame's started
  at 0; and how Tk pads a rectangle's `bbox` changed between releases (8.6.15 counts a pixel
  round one with no outline, 8.6.16 does not), so an invisible rectangle from 0 held on Windows
  and failed on the Linux image.
- **Input is found by position.** Mouse and keys are bound once on the canvas
  (`_bind_list_input`); a click, a right-click or the pointer's hand asks `_list_record_at`
  which row it is over. A click on a card also puts the keyboard on the list, with the ring on
  that card, and the ring's walk scrolls the list to keep it in view.

A rebuild keeps the depth that was drawn when the list was scrolled, so the position restored
in pixels (below) has content to land on, and draws the card the keyboard was on. This is not
virtualization: a card once drawn stays drawn until the next rebuild — which costs the drawing
little, since a drawn card is a handful of canvas items rather than six windows. Windowed
rendering stays on the [ROADMAP](ROADMAP.md) for notebooks far larger than the thousand notes
this was measured with. See
[The list that was drawn whole, for every pause in typing](ISSUES_LOG.md#the-list-that-was-drawn-whole-for-every-pause-in-typing).

### Measured, at 1,000 and 5,000 notes

`py tools/bench.py` reproduces these: each number is a fresh process in a throwaway folder,
over a notebook generated from a fixed seed, and `--against <copy>` alternates the two
versions run by run, so a machine that slows down halfway slows both. Medians of three runs,
on the development machine (Windows), 3 October 2026; 0.81.202 is the release before the
list was drawn:

| | 1,000 notes, now | 1,000 notes, 0.81.202 | 5,000 notes, now |
|---|---|---|---|
| start-up, to the first drawn list | 1.9 s | 8.3 s | 2.0 s |
| a rebuild of the whole list | 7 ms | 9.8 s | 9 ms |
| one note's automatic save | 12 ms | 9.8 s | 42 ms |
| memory once the window is up | 56 MB | 117 MB | 68 MB |

The guards in CI are structural rather than these timings: qa4 checks that a rebuild draws one
screenful and holds the rest, which fails when the list goes back to drawing everything, and a
check that fired on a slower runner would be a flaky one.

### Custom order: a place is written only by a move

A note's place in Custom order is its `order` number, and only a person's move writes it — a
drag on the list or Alt+↑/↓ (`_move_note`). Nothing else touches it: a save, an edit, a
recolour. A move is not an edit, so no `updated` changes. `normalize_note` keeps the number only
if it is a real one, and a note without it has not been placed yet: it stands above the placed
ones, newest first — where a new note, or one from a share code, is looked for.

`_move_note` renumbers every note in one pass (0, 1, 2 …) rather than squeezing a number between
two neighbours, so there is never a precision problem to manage. It works on the whole notebook
in Custom order, not only on what a search shows, so a hidden note keeps its place among the
rest. When the list was sorted some other way, it first places every note as that sort had them
(`_place_notes_as_sorted`) — the drag happened in *that* order — and switches the sort.

Two rules keep a move from being undone by the next rebuild: a card only trades places with
cards of the same pin state, and, in a grouped list, the same category (`_same_list_block`).

The drag itself (`_list_drag_arm` → `_start_list_drag` → `_follow_list_drag` → `_list_released`)
moves only the card's **drawing**: its record keeps its place, and the lifted card's offset is
tracked on the side. That matters because a drag near the list's edge scrolls it, and scrolling
draws the rows still waiting — which `_draw_list_rows` places from the records. Anything that
changes the rows under a drag (a rebuild, a save redrawing a card, a delete) ends it first
(`_cancel_list_drag`), putting the card back before the rows move.

The number is this notebook's own: `SHAREABLE_FIELDS` leaves it out of a share code, while a
backup — the same notebook on another machine — keeps it.

### Scrollable canvases guard their own view

A Tk canvas holding rebuilt content will lie to you twice. A rebuilt frame's geometry settles
over *several* event-loop passes — one measured collapse reported heights 106 → 276 → 820 as
three separate Configure events — and each intermediate, too-small scrollregion re-clamps a
canvas that was scrolled down.

And a rebuild that only *shrinks* content scrolled out of view fires no Configure at all (Tk
stops resizing an embedded window it no longer shows), leaving a stale scrollregion and a
viewport parked past the end of the real content. Both were caught by instrumentation, not
deduction — see
[The list that lost its place, twice, for two silent reasons](ISSUES_LOG.md#the-list-that-lost-its-place-twice-for-two-silent-reasons).

So the two scrolling canvases carry the same guard family. The editor page has pinned short
content to the top since `0.32.x`; the note list (since `0.58.82`) additionally remembers its
offset in **pixels** across a full rebuild and keeps that restore *in force* for a short
window — re-applied on every late Configure and on short timers for the silent-shrink case,
with the scrollregion refreshed from the content's real extent before any fraction math (the
editor page's window item, the list's own `_list_extent()`), because a scrollregion is a claim,
not a fact.

A deliberate wheel or scrollbar move cancels the pending restore: the user always outranks the
machinery. Any new scrollable canvas whose content gets rebuilt should either reuse this family
or consciously argue why it can't suffer the same two failures.

### Showing and hiding asks the layout, not the screen

Every "show this if it is not showing" and "hide this if it is" — Restore previous, the title
counter, the share code, the Settings sections, the day panel and the rest — asks `_is_placed()`:
does the widget have its place in the layout (`winfo_manager()`)? Never `winfo_ismapped()`, which
asks whether it is on the screen and says no for a placed widget until Tk first draws it, and for
as long as its page is hidden. A hide that asked the screen skipped a sleeping widget, which woke
up with its page; a show that asked it packed a placed widget again, moving it to the end of its
container. `tools/check_one_definition.py` fails on `winfo_ismapped()` outside the three places
that mean the screen (a tooltip, a click on the Settings page, the calendar's keys). See
[The button that woke up with its page](ISSUES_LOG.md#the-button-that-woke-up-with-its-page).

### A drag of the window's edge waits for the hand

The whole window sits in one frame inside `main_canvas`, and every size the window takes is
handed to that frame — which places and paints every widget again. A drag of the edge sends a
new size every few milliseconds, and a layout cost more than that: 275 ms a step with the
Calendar showing, 149 with the editor, 70 on Settings, 98% of it inside Tk.

So `_on_main_canvas_configure` asks whether the mouse's primary button is down
(`_pointer_button_held`, a question for Windows: the edge belongs to the operating system, and Tk
hears the sizes but not the button). While it is, the new size waits; `_lay_out_at_window_size`
hands it over once, when the drag pauses for `RESIZE_PAUSE_MS` or a watch every
`RESIZE_WATCH_MS` sees the button let go. With no button held — maximising, a snap, the
keyboard — it is handed over at once, as it always was. Anywhere but Windows, or if the question
fails, the answer is "not held", which is the old behaviour.

A held step still cost about 70 ms on the Calendar, and that turned out to be a class style.
Tk registers its two window classes, `TkTopLevel` and `TkChild`, with `CS_HREDRAW` and
`CS_VREDRAW`, so Windows invalidates a window whole whenever its size changes, and everything
on screen was painted again at every step. Tk does not need that: each of its widgets redraws
itself when its own size changes. `_stop_whole_repaints` takes the two styles off both classes
when the window is first mapped (Windows only, by class name). After it, a held step costs
about 10 ms and a step laid out live about half of what it did. Photographed with and without,
mid-drag and at a new size, the window is the same to the pixel. See
[The window that crawled behind its edge](ISSUES_LOG.md#the-window-that-crawled-behind-its-edge).

One page does not wait. The Calendar's month is a drawing (next section), and a step of the drag
costs it under 40 ms, so `_page_follows_the_drag` has a held drag laid out at every step while
the month is on screen. Every other page is built of widgets and waits for the hand; so does
the calendar's History register, which is rows of widgets too.

### The calendar's month is one drawing

The month grid was built the way the note list used to be: a frame per day, a label for its
number, one for each dot and each note title, a frame per divider — 216 widgets for a month
holding 46 notes, each of them an OS window on Windows. `_draw_calendar_grid` draws the same
cells as rectangles and text on one canvas, `cal_canvas`, laid out from measurements of the
widget grid it replaced: seven columns at floor(i × width / 7), a row of weekday names, week
rows all as tall as the busiest day needs and never under 90, and the paddings pack used inside
a cell. A day's content is drawn at the origin first (`_draw_cal_cell_content`), because the row
height depends on the tallest day, and moved into place once that is known.

The rules that keep the list honest keep this one too:

- **Records, not widgets.** `_cal_cells` holds each drawn day: its box, its items and the boxes
  of its note titles. `_cal_cell_view` reads a day back from the drawing — what it says, its
  colours, its outline — which is what checks ask now that a day has no widget.
- **Input is found by position.** Click, right-click and hover are bound once on the canvas, and
  `_cal_hit` answers whether the pointer is over a note's title — that note: open it, its menu,
  its preview — or the rest of a day: the day's list, the day's menu, its titles-only summary.
- **A new width draws; it does not render.** `render_calendar` works out which notes fall on
  which day and keeps the answer (`_cal_month_data`). A change of size draws again from it
  (`_cal_canvas_configured`) without expanding a single occurrence. Crossing the 1,150-pixel
  step between small and large titles is the one resize that renders.
- **Colours are taken when drawn.** Nothing tracks a drawn item's colour, so a theme switch
  draws the month again: `apply_theme` asks for a render like every other change, and one made
  while the calendar is hidden is caught up when it is shown.

The grid's frame is given the month's height, as the widget grid's rows gave it, so one busy day
still makes every week taller and the calendar area scrolls. Measured on that 46-note month: the
next month in 25 ms instead of 295, the Calendar tab after a change in 33 instead of 275, a step
of a window resize in 38 instead of 162. See
[The month that was two hundred windows](ISSUES_LOG.md#the-month-that-was-two-hundred-windows).

The calendar forgets its hover and takes a preview down whenever the days move under a pointer
that stayed still: at every redraw (`_draw_calendar_grid`), and whenever the top of the scroll
area's view changes (`_cal_scroll_moved`, called from the area's `yscrollcommand`) — so the
wheel, the scrollbar and a History landing all count, and content that only grows or shrinks
below does not.

## Background work: exporting and importing

Full backup export/import (`.zip`, including attachments) runs on a `threading.Thread`, not the
main thread — with enough attachments, doing this synchronously visibly froze the UI for
several seconds. The pattern used, and the one to follow for any future long-running I/O:

1. The worker thread does file I/O only, and updates a plain shared `dict`
   (e.g. `{"current": i, "total": n, "done": False}`) as it progresses. **It never touches a
   Tkinter widget.**
2. The main thread polls that dict on a timer (`self.after(100, poll_fn)`), and is the *only*
   place that updates the progress bar or shows a completion dialog.

This division is a hard rule, not a style preference — Tkinter isn't thread-safe, and any
widget access from the worker thread is a race condition waiting to surface as a rare,
hard-to-reproduce crash.

Three more rules joined the pattern in 0.71.125, and any future worker follows them too:
workers start through `_start_io_worker` (tracked, so `on_app_close` waits — capped — via
`_wait_for_io_workers` instead of destroying a daemon thread mid-file); anything that
replaces an existing file the user cares about writes beside it and `os.replace`s into place
only when whole (the backup zip and the single-note export both do); and only one
export/import runs at a time — a second click is refused with a status line, not queued.

A worker's completion is main-thread work, so closing the window has to do it: `on_app_close`
waits for the workers and then runs `_settle_background_work_at_close`. A finished export is
recorded as the last one; a finished import that was never merged is dropped whole — the unpacked
backup leaves the temp folder, and the files the worker copied in (it records them) leave the
attachments folder unless a note uses them. Merging at close would mean asking the import's
questions in a window that is closing.

## Autosave

Typing pauses trigger a debounced autosave; switching notes (or tabs) flushes any pending
change immediately first, so nothing written is ever lost to a note switch. Autosave explicitly
skips refreshing the note list while a popup is open (deferring the refresh until the popup
closes) to avoid the sidebar visibly flickering underneath an open dropdown.

A debounced callback cancels a waiting timer; it never just forgets one. `_autosave_now` used to
set its job to None on entry, assuming it was the timer that job tracked. Run any other way while
a timer waited, it left that timer running with nothing tracking it, and each stray timer, firing,
did the same to the next. It now cancels whatever waits (`_cancel_pending_autosave`); the
Calendar's History render does the same; and the find bar's rescan clears its job only from its
own timer (`_find_debounce_fire`), since a waiting rescan may carry a reveal the direct one does
not. See [The save that forgot the next one](ISSUES_LOG.md#the-save-that-forgot-the-next-one).

The spine's guards are deliberately quiet (a background path must never interrupt typing), but
never silent: every swallowed exception — including a save failing at note-switch or close —
appends one trace per spot per session to `crash_log.txt` via `_log_swallowed` (0.71.134), so
a persistent bug can no longer stop saving with nothing anywhere to diagnose.

A save never lets one field veto the rest. A date the app cannot read, a repeat with no start
date, a repeat's end date it cannot read, or a repeat's "Every" / "After … times" that is not a
whole number is *left out*: it keeps the note's last good value, everything else is saved, and
the status line says what was left out. (Read as 1, as the widgets used to read it, "After abc
times" ended a series after its first day.) Leaving the note — another note, Ctrl+N, a delete,
closing the window — asks "Go back and fix it" or "Continue without it", and "Continue" puts the
stored values back on screen so the editor agrees with the note again. The save and the question
ask one judgement, `_date_and_repeat_to_store`, so they cannot disagree about what stayed behind.
A save whose only difference from the note was a field it left out changes nothing the note
stores, so it keeps the note's "updated" stamp (`_stored_signature`): otherwise every way out of
a note with an unreadable date on screen moved it up "Recently updated". Before 0.83.335 the save returned nothing for such a field, and every automatic route read
that as success and replaced the editor — see
[One unreadable field, and every word typed after it](ISSUES_LOG.md#one-unreadable-field-and-every-word-typed-after-it).

What the app can read is wider since 0.84.338: a date as people write it — the day first in
figures (17.10.2026, 17/10/2026), the month first only where the day first cannot be (the
American 10/17/2026), the year first (2026-10-17), the month as a word in English or Romanian,
with English's day names and ordinal endings set aside — through one reader, `read_date` in
`core/recurrence.py`, and shown in one form,
`show_date` (17.10.2026). The store is unchanged: everything that reaches a note goes through
`format_date`, so `notes_data.json` keeps YYYY-MM-DD whatever was typed. Two rules make that safe:

- **A short or a missing year is read only when the person has finished** (`read_date(...,
  settled=True)`: leaving the field, Enter, a click anywhere else, an explicit Save, leaving the
  note, asking for a code — `_settle_date_fields`, wired by `_watch_date_field`). A click on
  anything that takes no keyboard leaves Tk's focus where it was, so it is caught app-wide
  rather than waited for as a `<FocusOut>` that never comes. The autosave reads strictly, so "17.10.20" on its way to 2026 is left
  out for half a second instead of saved as 2020.
- **The editor compares a date by the day it names, not its text** (`same_date`). The field
  shows 17.10.2026 where the note stores 2026-10-17; compared as text, every dated note read as
  unsaved the moment it opened — the same shape as the table-ending note the dirty comparator
  once read as changed forever.

The field is read in one place, `_typed_date` (a rule in `tools/check_one_definition.py` holds
it there): its empty form was compared by hand in five places, five places to forget the day it
changed.

## Testing

Everything runs automatically on every Pull Request, and every push to
`main`, that changes more than the documentation, via GitHub Actions
(`.github/workflows/tests.yml`), on **both** Windows and Linux: the Linux job supplies a
virtual display via Xvfb, and Windows runs through native win32, which is what makes the
platform-specific pixel checks bite in CI. A regression shows up as a failed check rather than
being found by hand later.

The automated coverage is nine headless GUI scripts (`qa/qa1.py`–`qa9.py`) plus seven standalone
unit suites: the recurrence engine, data-safety (backups & migration), the in-note calculator's
expression evaluator, the rich-text conversion and PDF-rejoin logic (`test_richtext.py`), the
table engine (`test_tables.py`) and a note's identity (`test_note_identity.py`) — these six need
no GUI — and the entry-module-identity guard, which builds a window. [qa/README.md](../qa/README.md) owns the per-script inventory: which script guards which
surface, and the house rules new checks follow.

`test_entry_module_identity.py` *does* build a window: it exists because the qa scripts'
`import note_organizer as NO` cannot catch a Settings label reading an uninitialised second
copy of the entry module.

### The hermetic seed

Every automated qa script opens with a *hermetic seed*, `qa/_qa_support.hermetic_seed` — one
definition, where there used to be nine copies of it. It runs before `note_organizer` is even
imported — earlier than it must, since the data migrations run in `initialise()`, which
constructing the app calls ([Startup](#startup)) — and writes an empty `notes_data.json` and the
migration marker, so a test's empty folder cannot invite the first-run migration to adopt the
developer's real notebook from `%APPDATA%`. And it fails closed: it refuses to run unless a scratch run was
declared (`NOTEORG_SCRATCH=1`, set only by `tools/run_tests.py` and the CI workflow), and beside
any `notes_data.json` it cannot prove empty — one that holds notes, or one it cannot read. The
copies it replaced read an unreadable notebook as empty and overwrote it.

Manual QA lives as a structured spreadsheet in `qa/` (`NoteOrganizer_TestPlan.xlsx`). See
[ISSUES_LOG.md](ISSUES_LOG.md) for notable bugs these checks caught (and a few they didn't,
caught by hand-testing instead).

## Case study: deciding the split with a call graph

This section is history — the split it describes is finished. It is kept because the method,
and its blind spot, are worth knowing before trusting the measurement again.

### Three plans that failed the same way

Three attempts to plan the split from section comments and method names were all wrong, in the
same way: the comment markers in `note_organizer.py` have drifted (the block headed "Trash /
recently deleted" contains `set_status` and `_show_toast`; "Daily reminder bar" covers
attachments, the colour picker and the date picker), so grouping by heading produces units that
do not hold together.

### Measuring instead of guessing

The fourth attempt measured the call graph instead — for each method, which other methods of
the same class it calls — and asked what share of a candidate group's outgoing calls stay
inside it. That is what "cohesive" means here: a group whose calls mostly stay inside it can
leave without dragging the class behind it.

| group | methods | lines | internal traffic, first plan | re-measured later |
|---|---|---|---|---|
| dialogs | 11 | ~400 | 62% | extracted first |
| calendar | 29 | ~917 | 59% | extracted second |
| attachments | 6 | ~227 | 38% | 67% by its turn — extracted third |
| note list | 5 | ~256 | 46% | 41%; 90% once drawn — extracted fourth (below) |
| sharing | 6 | ~323 | 19% | 33% |
| open-note tabs | 5 | ~148 | 24% | 26% |
| editor | 10 | ~447 | **11%** | **17%** |

The last column is the measurement of record for the groups that stayed: 33 / 26 / 17 — and
41 for the note list, until it became one drawing ([below](#the-list-measured-again)).

At planning time, only the top two were cohesive enough to move as units. **`editor` is the
important negative result** — at 11%, fifty of its fifty-six calls went outside the group. It
is not a module waiting to be extracted; it is the hub the rest of the class turns around, and
forcing it into a file would move the tangle rather than remove it.

The rest of the methods belong to no group at all — 157 of them (~4,550 lines) at the first
measurement, still ~144 at the re-measure after the three extractions. They are the genuinely
shared surface: `_dismiss_mini_popup` has eighteen callers, `set_status` sixteen,
`_schedule_autosave` eleven, `find_note` ten. A large shared core is not a failure to split; it
is what an application's main window is.

So the plan was: extract what measures as cohesive, re-measure afterwards, and stop when
nothing else clears the bar — rather than pursuing a target number of files. That is now done,
and re-measuring proved its worth: attachments scored 38% at the start and 67% by the time it
was its turn, because most of what had looked like outside traffic was this code asking for a
confirmation box. Planning all the groups up front would have ranked it near the bottom.

### Where it stopped, and why

After dialogs, the calendar and attachments, nothing else cleared the bar. The editor moved from
11% to 17% across three extractions, which is the strongest evidence available that it is not a
module hiding inside the class — moving any of the shared surface into a file would relocate
the tangle rather than remove it.

The entry file then grew well past that measurement — to ~22,400 lines — mostly through the
rich-text and tables UI, which is more of exactly this shared surface, not a new extractable
module.

### The list, measured again

One part of that growth was different. In 0.82.230 the note list stopped being a column of
widgets and became one drawing (see
[Large lists](#large-lists-draw-what-can-be-seen-the-rest-on-demand)), and a drawing brings its
own geometry, input handling and painting code. Measured again on 3 October 2026 with the same
question — by `tools/call_graph.py`, committed so the number can be checked; the first plan's
script was not kept — the group around it — 117 methods, ~2,500 lines: drawing the cards and
headers, filtering, searching, sorting, the keyboard ring, dragging into Custom order, Select
mode — sent **90%** of its calls to itself. That is well past the bar the dialogs (62%)
and the calendar (59%) cleared, so it moved, as they did, to `ui/note_list.py`, and the hub went
from ~22,400 lines to ~19,700.

It was a move, not a rewrite: the class exposes exactly the same methods (the API gate's
baseline did not change), every name the module uses is imported from `core/` (the names gate),
and the full suite is unchanged. The one line that changed is a static method that called its
siblings through `NoteOrganizer`, a name the module cannot import without a cycle; it calls them
through the mixin that defines them. What stayed behind is what the list does not own: the bulk
actions and their confirmations, which Settings shares, and `add_placeholder`, which every
entry field uses. No other group was re-measured into moving; the rule is still to measure,
not to aim for a number of files.

### One blind spot in the measurement

The first measurements read `note_organizer.py` alone, so they could not see calls made from the
mixins already extracted. That made them pull `_rounded_rect` and `_show_color_palette` into the
calendar group — both are used by `settings_page.py`, so their only *visible* callers were
calendar ones. Neither belongs there.

`tools/call_graph.py` reads the whole class — the entry file and every mixin — unless asked for
`--hub-only`, the old view. The two agree on the note list: 90% read the old way, at the commit
before it moved, and 89% with the mixins' four extra calls counted.

Read the methods before moving them; the graph shortlists, it does not decide. The rule this
taught — scope is decided by what an area *owns*, not by keyword — is recorded under
[What stays on the hub](#what-stays-on-the-hub).
