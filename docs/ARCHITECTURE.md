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

Both layers are fully extracted: fourteen `core/` modules and five `ui/` mixins. The annotated,
module-by-module inventory is [README's project tree](../README.md#project-structure), and
[CODE_TOUR.md](CODE_TOUR.md) walks through the modules for someone learning the codebase. Three
of the core modules — `richtext`, `clipboard` and `tables` — landed with the rich-text and
tables work; the core layer is complete.

### `core/` — data and rules

`noteorganizer/core/` holds persistence, validation, recurrence, the calculator parser, and
sharing. **No module in here may import tkinter**, which is what keeps it testable headlessly
and reusable by a different front end. `test_data_safety.py` checks that rather than trusting
it — the property is easy to lose to one stray import and impossible to notice by hand.

### `ui/` — five mixins over one class

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

What remains in the file is ~14,100 lines of genuinely shared surface. It grew again through
the rich-text and tables work even as the pure logic behind those features went into `core/`.

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
`%APPDATA%\NoteOrganizer` when running as the built `.exe` (`core/paths.py` decides):

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
[`qa/COVERAGE_LEDGER.md`](../qa/COVERAGE_LEDGER.md) rather than guessed.

An anti-bomb ceiling is not a performance promise, and the two should not be
confused: what makes a heavily styled note open quickly is
`_char_offsets` reading every span's offsets in one pass instead of re-reading
the note once per range end — 14.2 s of a 15.5 s startup, measured, before that
changed.

### Recurrence model

A recurring note is stored once — the "base" note carries a `recurrence` rule (frequency,
interval, specific weekdays/month-days, an end condition) plus two small maps:

- `exceptions`: dates removed from the series entirely
- `overrides`: date → partial note, for edits that apply to one occurrence only

`expand_occurrences(note, range_start, range_end)` is the only place that turns a rule into
actual dates — everything else (calendar rendering, list previews) asks it for occurrences
within a window rather than re-deriving the logic. Editing "just this occurrence" writes an
override; editing "this and all future" (or the whole series) edits the base note directly.

## UI layer

### No native dialogs, anywhere

Every dropdown, color picker, confirmation prompt, and date picker in this app is a hand-built
`Toplevel` popup — never `tkinter.messagebox`, `ttk.Combobox`, or `colorchooser`. The trade-off
is more code to maintain; what it buys is a UI that's fully themed (dark/light variants apply
everywhere, including every dialog) and behaves consistently across the app. The single
deliberate exception is the last-resort startup-crash dialog, which uses the plain
standard-library messagebox precisely because it must not depend on the app's own UI having come
up (see [ISSUES_LOG.md](ISSUES_LOG.md#a-crash-handler-that-would-have-crashed-itself)).

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

### Theme tracking — two different patterns, on purpose

`track_theme(widget, **option_map)` registers a widget so a later theme switch re-applies the
right colors to it. This is for **persistent** widgets — ones built once at startup and never
destroyed (the sidebar, the main buttons, the tab bar).

For content that gets **destroyed and rebuilt** on every refresh — note cards, calendar cells,
the attachments list, anything inside a Settings section panel — widgets are colored with plain
`.configure(bg=self.colors[...])` calls instead. Since this content is always rebuilt fresh, it
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
changes note *data*, so `_recolor_note_cards()` now re-applies colors to the cards already on
screen, using named widget references recorded in `_note_card_widgets` when each card is built.

This is **not** the `track_theme` pattern that leaked: `_note_card_widgets` is rebuilt from
scratch by every `refresh_note_list()`, so it only ever holds cards currently on screen.

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
`renumber()` returns the shifts it caused and `shift_spans()` moves the character spans to
match; otherwise bold slides sideways the moment `9.` becomes `10.`.

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
[The version that updated itself](ISSUES_LOG.md#the-version-that-updated-itself).

The grid is rebuilt (never patched) at settled moments — load, paste, leaving the block, a
structural edit — and every editing gesture writes through to the hidden text first, so the
drawn view can always be thrown away and rebuilt from it. The costs live where they can be
tested: Tk counts text columns in UTF-16 units (an emoji is two of them), embedded windows
occupy an index but are skipped by character counts, and a rebuild mid-gesture destroys the
canvas under the mouse — each of those has burned this codebase once, and each now has a
regression check in `qa/qa1.py` and a war story in [ISSUES_LOG.md](ISSUES_LOG.md).

### Large lists: paginate, don't virtualize (yet)

The Trash (Settings → Recently deleted) and the multi-note Share panel both cap how many rows
they build at once (50 and 100 respectively), with a "Show more" button to reveal the next
batch, rather than rendering every entry immediately. This was enough to take the Trash panel from ~1.8s to ~100ms with 600
entries. The main note list doesn't do this yet — see [ROADMAP.md](ROADMAP.md) for real
windowed virtualization, which would help further at very large note counts.

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
with the scrollregion refreshed from `bbox("all")` before any fraction math, because a
scrollregion is a claim, not a fact.

A deliberate wheel or scrollbar move cancels the pending restore: the user always outranks the
machinery. Any new scrollable canvas whose content gets rebuilt should either reuse this family
or consciously argue why it can't suffer the same two failures.

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

## Autosave

Typing pauses trigger a debounced autosave; switching notes (or tabs) flushes any pending
change immediately first, so nothing written is ever lost to a note switch. Autosave explicitly
skips refreshing the note list while a popup is open (deferring the refresh until the popup
closes) to avoid the sidebar visibly flickering underneath an open dropdown.

The spine's guards are deliberately quiet (a background path must never interrupt typing), but
never silent: every swallowed exception — including a save failing at note-switch or close —
appends one trace per spot per session to `crash_log.txt` via `_log_swallowed` (0.71.134), so
a persistent bug can no longer stop saving with nothing anywhere to diagnose.

## Testing

Everything runs automatically on every Pull Request, and on every push to
`main`, via GitHub Actions
(`.github/workflows/tests.yml`), on **both** Windows and Linux: the Linux job supplies a
virtual display via Xvfb, and Windows runs through native win32, which is what makes the
platform-specific pixel checks bite in CI. A regression shows up as a failed check rather than
being found by hand later.

The automated coverage is nine headless GUI scripts (`qa/qa1.py`–`qa9.py`) plus six standalone
unit suites: the recurrence engine, data-safety (backups & migration), the in-note calculator's
expression evaluator, the rich-text conversion and PDF-rejoin logic (`test_richtext.py`), and
the table engine (`test_tables.py`) — these five need no GUI — and the entry-module-identity
guard. [qa/README.md](../qa/README.md) owns the per-script inventory: which script guards which
surface, and the house rules new checks follow.

`test_entry_module_identity.py` *does* build a window: it exists because the qa scripts'
`import note_organizer as NO` cannot catch a Settings label reading an uninitialised second
copy of the entry module.

### The hermetic seed

Every automated qa script opens with a *hermetic seed*: before `note_organizer` is even
imported (its data migrations run at import time), the script writes an empty `notes_data.json`
and the migration marker, and refuses outright to run beside a file holding real notes. Without
this, a test's empty folder invited the app's own first-run migration to adopt the developer's
real notebook from `%APPDATA%` — and checks then passed or failed depending on what the owner
had done in the app that day.

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
| note list | 5 | ~256 | 46% | 41% |
| sharing | 6 | ~323 | 19% | 33% |
| open-note tabs | 5 | ~148 | 24% | 26% |
| editor | 10 | ~447 | **11%** | **17%** |

The last column is the measurement of record for the groups that stayed: 41 / 33 / 26 / 17.

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

After dialogs, the calendar and attachments, nothing else clears the bar. The editor moved from
11% to 17% across three extractions, which is the strongest evidence available that it is not a
module hiding inside the class — moving any of the shared surface into a file would relocate
the tangle rather than remove it.

The entry file has grown well past that measurement since — ~14,100 lines now — but the growth
is the rich-text and tables UI, which is more of exactly this shared surface, not a new
extractable module.

### One blind spot in the measurement

The call graph is built from `note_organizer.py` alone, so it cannot see calls made from the
mixins already extracted. That made it pull `_rounded_rect` and `_show_color_palette` into the
calendar group — both are used by `settings_page.py`, so their only *visible* callers were
calendar ones. Neither belongs there.

Read the methods before moving them; the graph shortlists, it does not decide. The rule this
taught — scope is decided by what an area *owns*, not by keyword — is recorded under
[What stays on the hub](#what-stays-on-the-hub).
