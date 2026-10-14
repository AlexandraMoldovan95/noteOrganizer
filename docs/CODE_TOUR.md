# Code tour

A guided walk through the codebase, written for someone still learning
Python. It explains not just *what* each part does but *why* it's built
that way, and points at the real code so you can read along.

This is a companion to [ARCHITECTURE.md](ARCHITECTURE.md), which is the
short reference version for someone who already knows the codebase. Start
here; go there when you want the summary.

> **Scope:** the data and rules layer is fully extracted — all seventeen
> `core/` modules below are covered here in depth. The user interface has
> since been split too: seven areas now live in `noteorganizer/ui/` as mixins
> (calculator panel, Settings page, dialogs/popups, calendar, attachments,
> the note list, spelling), while `note_organizer.py` stays the entry point
> and the shared UI hub the rest hangs off. This tour walks the `core/`
> modules; six of the `ui/` mixins are plain cut-and-paste moves of methods
> that already lived on the class, so they read the same as they did in the
> single file — see [ARCHITECTURE.md](ARCHITECTURE.md) for how those six
> were chosen. The seventh, spelling, was written there from the start.

## Contents

- [How to run it](#how-to-run-it)
- [The shape of the project](#the-shape-of-the-project)
- [Reading order](#reading-order)
- [`noteorganizer/core/calculator.py`](#noteorganizercorecalculatorpy)
- [`noteorganizer/core/recurrence.py`](#noteorganizercorerecurrencepy)
- [`noteorganizer/core/themes.py`](#noteorganizercorethemespy)
- [`noteorganizer/core/formatting.py`](#noteorganizercoreformattingpy)
- [`noteorganizer/core/richtext.py` and `core/clipboard.py`](#noteorganizercorerichtextpy-and-coreclipboardpy)
- [`noteorganizer/core/spelling.py` and `core/winspell.py`](#noteorganizercorespellingpy-and-corewinspellpy)
- [`noteorganizer/core/tables.py`](#noteorganizercoretablespy)
- [`noteorganizer/core/sharing.py`](#noteorganizercoresharingpy)
- [`noteorganizer/core/duplicates.py`](#noteorganizercoreduplicatespy)
- [`noteorganizer/core/paths.py`](#noteorganizercorepathspy)
- [`noteorganizer/core/storage.py`](#noteorganizercorestoragepy)
- [`noteorganizer/core/categories.py`](#noteorganizercorecategoriespy)
- [`noteorganizer/core/model.py`](#noteorganizercoremodelpy)
- [`noteorganizer/core/welcome.py`](#noteorganizercorewelcomepy)
- [Where the app starts](#where-the-app-starts)

**Short on time?** Three sections repay a quick read:
[the calculator](#noteorganizercorecalculatorpy) (hand-rolled parsing
instead of `eval()`), [sharing](#noteorganizercoresharingpy) (defending
against hostile input), and [paths](#noteorganizercorepathspy) (the two
extraction bugs).

---

## How to run it

Nothing about running the app has changed, or will:

```
py note_organizer.py
```

`note_organizer.py` is still the front door. The pure logic has moved into
the `noteorganizer/` package next to it and is imported back in; the entry
file itself stays large (~20,500 lines) because it is the UI hub the pieces
hang off, not a junk drawer of stray logic.

To run every test — units + qa1–qa9 — safely in a scratch copy:

```
py tools/run_tests.py
```

The eight unit suites — `test_recurrence`, `test_calculator`,
`test_data_safety`, `test_richtext`, `test_tables`, `test_note_identity`,
`test_spelling`, `test_entry_module_identity` — also run individually
(`py test_<name>.py`).
See [qa/README.md](../qa/README.md) for the map of the whole suite,
and the QA safety rule in `CLAUDE.md` before running any test by hand —
the GUI tests delete data files in whatever folder they run from.

---

## The shape of the project

```
note_organizer.py         the entry point you run, and the UI hub
noteorganizer/
├── core/                 data and rules — never imports tkinter
│   ├── calculator.py     the in-note calculator's expression parser
│   ├── recurrence.py     repeat rules, and which dates a note lands on
│   ├── themes.py         colour palettes and layout numbers (pure data)
│   ├── formatting.py     how rich-text spans are stored on a note
│   ├── richtext.py       HTML in and out, for paste, copy and export
│   ├── clipboard.py      the Windows clipboard's richer formats
│   ├── spelling.py       which misspellings to show, and which to leave alone
│   ├── winspell.py       Windows' own spell checker, through COM
│   ├── tables.py         tables as lines of text (pipes are the store)
│   ├── sharing.py        share codes, and the guards that make import safe
│   ├── duplicates.py     deciding when two notes are the same note
│   ├── paths.py          where data lives, migrations, safe cleanup
│   ├── storage.py        reading/writing notes, settings, templates, trash
│   ├── categories.py     the live category map
│   ├── single_instance.py  one window per notebook (a lock on its folder)
│   ├── welcome.py        the note a first install opens on
│   └── model.py          what a note is; normalize_note validates every one
└── ui/                   on-screen areas, as mixins NoteOrganizer inherits
    ├── calculator_panel.py  the in-note calculator panel
    ├── settings_page.py     the Settings page and its sections
    ├── dialogs.py           the hand-built dialogs and popups
    ├── calendar_view.py     the Calendar tab
    ├── note_list.py         the note list: cards drawn on one canvas
    ├── attachments.py       the attachments section
    └── spelling.py          the red underline, and its right-click menu
docs/                     these documents
└── archive/              two finished registers, kept as history
qa/                       headless GUI tests, the stories and the test plan
test_*.py                 eight unit suites; seven need no window
tools/                    what CI runs, and the tools behind the docs' numbers
├── check_*.py            nine static gates: eight in CI, the link check before a push
├── pre_push_check.py     the gates, locally, in seconds (links in, mutant targets left to CI)
├── run_tests.py          the whole suite, safely, from a scratch copy
├── run_coverage.py       the whole suite again, measuring what it executes
├── mutate.py             takes each fix away and checks a check fails
├── bench.py              start-up, save, memory, an import, the list's end, at 1,000+ notes
├── call_graph.py         which methods call which: the measure behind the split
├── doc_screenshots.py    retakes the documentation's screenshots
├── make_icon.py          draws the app icon, rather than storing one
└── linux-ci/             one Docker command reproduces the Ubuntu CI leg
.github/workflows/        CI: tests on Windows and Linux; mutants and stories on demand
```

The layers are two:

* **`core`** — everything that would still make sense if the app had no
  windows at all: reading and writing notes, validating them, working out
  recurring dates, evaluating calculator expressions.
* **`ui`** — on-screen areas, extracted into mixin classes that
  `NoteOrganizer` inherits from. The methods are unchanged — they still
  reach for `self.colors`, `self.notes` and each other exactly as before —
  so each move was cut-and-paste, not a redesign. What remains in
  `note_organizer.py` is the shared hub they all lean on.

The rule that keeps them apart: **nothing in `core` may import tkinter.**
That's what lets the core be tested without opening a window, and what
would let a phone app reuse it one day.

---

## Reading order

If you're working through this for the first time:

1. **`calculator.py`** — start here. Small, completely self-contained, and
   it teaches a genuinely useful pattern (two-stage parsing).
2. **`recurrence.py`** — the best example of a design decision: store the
   rule, compute the results.
3. **[`model.py`](#noteorganizercoremodelpy)** — `normalize_note` is the
   single idea the whole data layer is built on.
4. The rest in any order. `sharing.py` is the one to read if you're
   interested in defending against hostile input, and
   [`tables.py`](#noteorganizercoretablespy) if you want to see a whole
   feature built on the idea that plain text can be the single source of
   truth.
5. The UI mixins in `noteorganizer/ui/` (see [ARCHITECTURE.md](ARCHITECTURE.md)).

**How to read a comment.** A comment says *why* in a line or three. When a
story sits behind it — a bug, what it cost, how it was found — the comment
points to [the issues log](ISSUES_LOG.md), either by a story's title
(`ISSUES_LOG: "…"`) or by name among its
[smaller lessons](ISSUES_LOG.md#smaller-lessons-moved-out-of-the-code).
A module's own docstring names what it is for in a few lines, and the walk
through it is here. `tools/check_comments.py` checks that every pointer
leads somewhere, and keeps the modules already condensed — `core/model.py`,
`core/storage.py` and `ui/note_list.py` so far — that way.

---

## `noteorganizer/core/calculator.py`

**What it's for.** The note editor has a calculator panel. Whatever the
user builds — by tapping buttons or by typing and pasting into the display
— arrives here as plain text like `"(5+3)×2"`. This module turns that text
into a number.

**Why it isn't one line of `eval()`.** Python has a built-in `eval()` that
would run `"(5+3)*2"` immediately. It's deliberately not used, because
`eval()` runs *any* Python code it's handed — a pasted string could do far
more than arithmetic. Writing a small parser costs maybe 150 lines and
removes that risk completely, instead of relying on the input always being
well-behaved. This is a common trade in real software: a bit more code in
exchange for not having to trust your input.

### The two stages

Almost every parser, from this one up to Python's own, works in two steps.

**Stage 1 — tokenising.** `_tokenize_calc_expression` walks the raw text
and chops it into a flat list of meaningful pieces:

```
"12+3"   →   [12.0, "+", 3.0]
```

Numbers become real `float` values here; operators and brackets stay as
one-character strings. After this stage there's no text left to interpret,
just a tidy list.

**Stage 2 — parsing.** A set of small functions walk that list and compute
the answer. There's one function per *precedence level*, and they call
each other in a chain:

```
parse_expression   +  −
      ↓
parse_term         ×  ÷
      ↓
parse_percent      %
      ↓
parse_power        ^  and leading + −
      ↓
parse_unary        √,  brackets,  plain numbers
```

**The chain is the precedence rule.** Nothing else enforces it. Because
`parse_expression` (which handles `+`) asks `parse_term` (which handles
`×`) for each of its operands, `×` is always resolved first. That's why
`2+3×4` gives 14 and not 20 — read the two functions and you can see it
happen.

### Recursion, which is the idea worth taking away

Look at `parse_unary` when it meets an opening bracket. It calls
`parse_expression` — the function at the *top* of the chain — on whatever
is inside:

```python
if isinstance(tok, str) and tok in _CALC_OPEN_BRACKETS:
    advance()
    value = parse_expression()   # start again, for the contents
```

A function that ends up calling itself (here, indirectly, through the
chain) is using **recursion**. It's what lets brackets nest to any depth —
`((1+2)×(3+4))` — without a single extra line of code handling "two levels
deep" or "three levels deep". Each nested bracket is just another trip
around the same loop of functions.

### Two details that are easy to trip over

**`pos = [0]` is a list, not a number.** It tracks how far through the
token list we've read. The inner functions need to *change* it. In Python,
assigning to a name inside a nested function creates a new local variable
rather than updating the outer one — so `pos = pos + 1` inside `advance()`
wouldn't work. Mutating a list instead (`pos[0] += 1`) changes the object
everyone shares. (The keyword `nonlocal` is the other way to solve this.)

**Every failure funnels through one exception.** Bad character, unbalanced
bracket, division by zero, square root of a negative — all raise
`CalcError`. That's caught once, right at the bottom:

```python
try:
    result = parse_expression()
    ...
except CalcError:
    return None
```

So the whole module has exactly one way to fail — it returns `None` — and
the calculator panel just shows "Error" when it sees that. No caller has
to handle exceptions, and no malformed expression can crash the app. This
is a deliberate pattern: **decide on one failure shape and keep it in one
place.**

### Things worth noticing about the operators

* `−`, `×`, `÷` in the code are the *typographic* symbols shown on the
  calculator buttons, not `-`, `*`, `/`. That's genuinely what ends up in
  the display text, so that's what the parser reads.
* `^` is **right-associative**: `2^3^2` means `2^(3^2)` = 512, not
  `(2^3)^2` = 64. That's the normal maths convention. It falls out of
  `parse_power` calling *itself* for the exponent instead of looping.
* A leading minus binds to the whole power: `−2^2` is `−(2^2)` = −4, which
  matches Python's own `**`. That's why unary signs live in `parse_power`
  and not further down in `parse_unary`.
* `(5+3]` evaluates fine. The three bracket styles are interchangeable and
  purely visual, so a mismatched pair isn't treated as an error the user
  probably didn't intend.

### Where it's tested

`test_calculator.py` — roughly fifty checks, no GUI needed, runs in under a second.
It's a good file to read straight after the module: each test names the
behaviour it's pinning down, so it doubles as a specification.

---

## `noteorganizer/core/recurrence.py`

**What it's for.** Notes can repeat — daily, weekly, monthly, yearly — and
the calendar needs to know which days each one lands on.

### The one idea that shapes everything else

> **A recurring note is stored exactly once.**

Its occurrences are worked out *on demand*, for whatever date range is
being shown, and never saved. A note repeating daily since 1990 is still a
single entry in `notes_data.json`.

It's worth pausing on why, because the alternative is tempting. If you
saved every occurrence you'd get: a file that grows forever, "edit the
whole series" meaning rewriting thousands of records, and no sensible
answer to "repeats forever". Computing instead keeps the stored data tiny
and the rule editable — at the cost of the code in this module. **That
trade, store the rule and compute the results, comes up constantly in real
software.**

Five fields carry it:

| Field | Meaning |
|---|---|
| `note["date"]` | the anchor — when the series starts |
| `note["recurrence"]` | the rule itself |
| `note["exceptions"]` | days the user deleted individually |
| `note["overrides"]` | per-day content edits |
| `note["moved"]` | days held on another date: the date the rule gives each, mapped to the date it is on |

### Normalising at the edge

`normalize_recurrence()` never raises and never returns anything odd. Give
it `None`, a string, or a dict with `interval` set to `"banana"` — it
returns a valid rule, falling back to "does not repeat" if it must. Every
field is checked on its own, so one bad value doesn't discard an otherwise
fine rule.

The payoff: **everything downstream can assume the shape is right.**
`expand_occurrences` never checks whether `interval` is a number, because
by then it always is. Without this you'd need defensive checks in every
function and would still miss one. Notes get the same treatment from
`normalize_note()` — it's why a single corrupt entry can't take down the
app.

One detail worth spotting:

```python
out = dict(RECURRENCE_DEFAULTS)
out["weekdays"] = []      # not the default's list!
out["month_days"] = []
```

`dict(...)` copies the dictionary, but **the lists inside it are shared**.
Without those two lines every rule would point at the same list object, and
adding a weekday to one note would change every other note too. Worth
remembering generally: copying a container doesn't copy what's inside it.

### Reading `expand_occurrences`

It's the biggest function here, but it's one shape repeated four times —
a branch per frequency. Each walks forward from the anchor and calls the
same inner helper:

```python
def take(candidate):
    nonlocal produced
    ...
```

`take()` decides whether a date counts, records it if it falls inside the
visible range, and returns `False` when the rule is spent. Note it counts
*every* occurrence since the anchor (so "stop after 10 times" works) while
only collecting the ones you can actually see.

`nonlocal produced` exists for the same reason the calculator used
`pos = [0]`: assigning to a name inside a nested function would create a
new local variable. `nonlocal` says "update the enclosing one instead".
Two solutions to the same Python quirk — you'll meet both in real code.

### Two things that make it fast and safe

**Skip ahead, don't walk.** For a rule with no count limit the code jumps
straight to the visible window:

```python
skipped = (range_start - anchor).days // interval
current = anchor + step * skipped
```

A daily note anchored in 1990 costs the same to display in 2026 as one
made yesterday. `test_recurrence.py` pins this down with a 36-year-old
recurrence that resolves in about **0.01 ms**.

**Guard rails.** Every loop counts iterations against `MAX_OCCURRENCES`
(5000) as well as checking dates. If a rule were ever malformed such that
the date stopped advancing, the guard ends the loop rather than freezing
the app. When a loop's exit depends on computed values, a bound is cheap
insurance.

### The awkward calendar cases

Two are handled explicitly, because dates are full of them:

- **"The 31st" in February.** `_day_in_month()` applies the rule's policy:
  `"clamp"` uses the last day that exists (Feb 28), `"skip"` produces no
  occurrence that month. The user chooses. Feb 29 anchors on yearly rules
  take exactly the same path.
- **Month arithmetic.** `_shift_month()` turns a year and month into a
  single running count of months, adds, then converts back — so there's no
  "what if we roll past December" case to get wrong.

### Where it's tested

`test_recurrence.py` — 47 checks, no GUI. Read it alongside the module: it
covers the clamp/skip policies, count and end-date limits, exceptions, and
the performance case above.

---

## `noteorganizer/core/themes.py`

**What it's for.** Eight colour palettes and a few fixed layout numbers.
Pure data — no logic, no file access, nothing that can fail.

The thing worth noticing is the *shape*. Every theme defines exactly the
same keys:

```python
"dark":  {"bg": "#1e1e2f", "card": "#2e2e48", "text": "#f2f2f7", ...}
"light": {"bg": "#f5f5fa", "card": "#ffffff", "text": "#22223a", ...}
```

Two colours are *computed* from a palette rather than stored in it:
`inset_surface()` (a well sunk inside a card) and `hairline()` (its
borders), both blends of `card` toward another key. They live here so that
Settings and the theme switch share one definition — a colour that is
derived rather than looked up is invisible to anything that fixes stray
colours by matching known palette values, which is exactly how the Settings
panels once stayed dark on a light theme.

Three roles come in pairs: `accent`, `danger` and `success` are **fills**
(a button, a banner), and `accent_text`, `danger_text`, `success_text` are
the same roles as words on an ordinary surface. The words *on* a fill are
never stored: `letters_on(fill)` picks white or near-black by measured
contrast, and code asks for them as `self._on_fill("accent")`, or as the
names `on_accent`, `on_danger`, `on_success` wherever a palette key is
expected (`track_theme`, `palette_keys`), which `palette_value()` resolves.
That way a fill and its words cannot drift apart from one theme to the
next. Letters on a colour the person picked — a painted calendar day, the
colour picker's tick — are `letters_on` too; `contrasting_fg`, which the
calendar and the formatting bar call, is it by name: it once had a formula
of its own and disagreed on 9 of the 20 day colours. Words in such a colour
(a category's, a note's own) go the
other way: `legible_on(colour, card, text)` keeps it if it reads as
words on the card and otherwise finds the nearest shade that does — darker
in the same hue on a light card, toward the text colour on a dark one;
that is the tags line under a card's title. Why two shades per
role, and how they were chosen, is in
[ARCHITECTURE](ARCHITECTURE.md#contrast-measured).

Nothing in the app ever asks *"which theme is this?"* before picking a
colour. It asks for `colors["card"]` and gets whatever that means right
now. **Adding a ninth theme means adding one dict here and changing
nothing else.**

That uniformity also enables the theme-switch safety net: because every
palette is known, the app can spot a widget still holding a colour from a
*different* theme and remap it (`_recolor_stragglers`). You couldn't do
that if themes were ad-hoc.

The layout numbers here (`SIDEBAR_WIDTH`, `EDITOR_MIN_WIDTH`) are pixels
as drawn at 100%. This module never sees a screen, since `core/` never
imports tkinter, so the UI grows them: `self.px(SIDEBAR_WIDTH)` is the
width on a 150% screen with Sharp text on, and exactly 280 at 100%.
`SHARP_TEXT_SETTING` is that setting's key, read once before the first
window opens. Why the sizes are written this way is in
[ARCHITECTURE](ARCHITECTURE.md#sharp-on-a-scaled-screen-every-size-is-given-at-100).

`CATEGORY_COLORS` — the *live* category map the user edits — is
deliberately **not** here. It reads and writes `settings.json`, so it now
lives in its own module,
[`noteorganizer/core/categories.py`](#noteorganizercorecategoriespy),
alongside the storage layer that was since extracted to
[`noteorganizer/core/storage.py`](#noteorganizercorestoragepy). Only the
immutable defaults (`DEFAULT_CATEGORY_COLORS`) live in this module, and
`categories.py` imports them.

---

## `noteorganizer/core/formatting.py`

**What it's for.** Deciding what a note's `formatting` field is allowed to
contain.

Formatting is stored as a flat list of spans:

```python
{"start": 0, "end": 5, "style": "bold"}
{"start": 6, "end": 9, "style": "highlight", "value": "#fff3b0"}
```

**Why character offsets and not Tkinter's own `line.column` positions?**
Because offsets are plain data. They survive being written to JSON, sent
as a share code, and loaded back into a window of a different width. Line
and column numbers shift the moment text wraps differently — they describe
*the screen*, not *the text*.

`normalize_formatting()` is a gatekeeper of the same kind as
`normalize_recurrence`, with one difference worth noting: **it drops bad
spans rather than repairing them.** A span with no valid colour, or a
zero-length range, is discarded entirely. Repairing would mean guessing
what the user meant; dropping is honest and can't corrupt the editor.

### Two kinds of formatting, stored two different ways

A note carries formatting in two fields, because they answer different
questions.

`formatting` describes **characters** — bold, italic, colours, and now font
size and family — as the spans above.

`paragraphs` describes **whole lines** — which are list items, at what
nesting depth, and how they are aligned — keyed by line number, since a
line is the unit those apply to. Only non-default properties are stored, so
an ordinary paragraph produces no entry at all.

It has its own gatekeeper, `normalize_paragraphs()`, which drops bad
entries the same way — and additionally throws away any pointing past the
end of the body, so a note that was later shortened can't come back with
an indent on a line that no longer exists.

### The rule that shapes most of this module

**Two Tk tags that both set the widget's `font` option do not compose. One
simply wins.**

That single constraint explains a surprising amount:

- Why `bold_italic` is its own style rather than a `bold` span overlapping
  an `italic` one.
- Why font size and family, which also set `font`, can't be independent
  tags either — so `font_tag_for()` folds weight, slant, size and family
  into *one* tag name, and `resolve_font_runs()` works out the stretches of
  text over which that combination is constant.
- Why the note still stores all four as **separate spans**. They only meet
  at render time. Keeping them separate in the data is what lets you bold
  part of a resized run without the two fighting.

`parse_font_tag()` is the inverse, used when reading the widget back: it
takes a composite tag apart again into size and family. Weight and slant
come from their own tags instead, so a run isn't saved twice.

`merge_spans()` exists because of that split: a composite tag is broken at
every bold boundary inside it, so one size across a paragraph reads back as
several pieces. Left alone they'd be written to the note that way and split
further on the next save.

### Markers live in the note's text

A bullet really is a `"• "` at the start of the line, and a numbered item
really begins `"1. "`. `parse_list_marker()` reads them back; `marker_for()`
writes them.

**Why store the marker instead of just drawing it?** Because `formatting`
is character offsets into that same body. A marker that existed on screen
but not in the text would put every offset after it out by the marker's
length, on every line, forever. Keeping the text and the widget identical
means the offsets need no translation — and a list still looks like a list
when the note is exported, shared as a code, or pasted into an email.

The cost is that renumbering rewrites real characters, which moves
everything after them. So `renumber()` returns the shifts it caused and
`shift_spans()` can move character spans to match — otherwise bold slides
sideways the moment `9.` becomes `10.`. In the editor, `_renumber_lists`
writes only the characters of each marker that changed, and Tk moves every
tag, the view and the drawn tables along by itself.

Bullets change glyph with depth (`•`, `◦`, `▪`) because those are
characters nobody types by accident. Numbers deliberately don't: `1.` then
`a.` then `i.` is ambiguous with ordinary prose, and a note is exactly the
kind of document where a line can legitimately begin `"a. "`. Depth shows
through indentation and the count restarting instead.

### One function here isn't about text at all

`split_toolbar_rows()` decides which formatting-toolbar controls go on
which row when the bar has to wrap. It lives in core, taking widths as
plain numbers, for a reason worth remembering: a check that measures widget
widths is testing whatever font the machine happens to have. The same
toolbar measures 577px on one machine and 827px under Xvfb, and which
control lands on a row boundary moves with it. Given numbers, the same
inputs give the same answer everywhere. See `docs/ISSUES_LOG.md`, "A
toolbar check that measured the wrong thing, three times".

---

## `noteorganizer/core/richtext.py` and `core/clipboard.py`

**What they're for.** Pasting formatted text in, and copying it back out.

`richtext.py` converts: HTML in, a note's text and spans out, and the
reverse. `clipboard.py` is the part that talks to Windows.

**Why two modules rather than one?** Because only one of them can be
tested here. Tkinter's clipboard only offers plain text, so reaching
`CF_HTML` means the Win32 API through `ctypes` — Windows-only, and the
test suite runs on Linux. Keeping that to one small module, where every
function returns None rather than failing when it cannot work, leaves all
the actual decisions — what maps to what, how lists nest, where offsets
land — in a module that turns strings into strings and can be tested
anywhere. That is `test_richtext.py`, which needs no window and no
clipboard.

**Two things that map more neatly than you might expect.** An `<li>`
becomes a line starting `"• "` plus a `paragraphs` entry, which is exactly
what the editor produces when a list is typed by hand. And `<b>text</b>`
becomes a span of character offsets, which is exactly how `formatting`
already stores bold. The note format and HTML line up almost one to one.

**And one that does not.** Everything else. HTML can say things a note
cannot, so `<sup>`, `<code>`, a background image and a CSS class are
dropped and their words kept. Font size and family are dropped too, even
though the app has both: a web page uses neither of the eight the app
offers, so matching would mean picking a nearest value and claiming the
note is set in something it never was.

---

**`reflow_wrapped()` — the PDF rejoiner.** The other big resident of
`richtext.py`. Text copied from a PDF arrives as the column's lines, not
the writer's paragraphs; this function decides, line by line, which
breaks were forced and which were meant. Four small helpers carry the
whole judgment — `_looks_wrapped()` (does this block behave like a
wrapped column at all), `_forced_break()` (would the next word have
fitted), `_ends_a_paragraph()` (sentence punctuation, or a line falling
well short of the column), and `_join_wrapped()` — and each is pure
string logic, which is why `test_richtext.py` can test the property
(nothing lost, nothing split) across many widths instead of pinning one
example. Blank lines always separate paragraphs and are never removed,
and anything that does not look wrapped comes back byte-for-byte.

### Where it's tested

`test_richtext.py` — needs no window and no clipboard, and covers
`reflow_wrapped()`'s property (nothing lost, nothing split) across many
widths.

## `noteorganizer/core/spelling.py` and `core/winspell.py`

**What they're for.** The red underline under a misspelled word, split the
same way the clipboard is: a small platform part, and the decisions in a
part that tests without Windows.

`winspell.py` reaches the spell checker Windows already has — one per
language the person installed — through COM, with `ctypes`, so no
dictionary ships with the app and nothing new is installed. Every function
returns an empty answer off Windows or on any failure. The one call that
writes, `Speller.add`, puts a word in the person's own Windows dictionary,
and runs only when they choose "Add to Windows dictionary".

`spelling.py` decides what to do with the answers, and most of it is about
staying quiet:

- `visible_errors()` leaves a sentence alone when most of its words are
  unknown — it is in a language the computer has no dictionary for — so an
  English sentence beside it keeps its underlines. A sentence too short to
  judge takes its paragraph's verdict, and a short paragraph the whole
  note's, so a list of short lines in another language is judged by all of
  its words. `sentence_spans()` cuts a line into its sentences.
- `line_errors()` keeps a range only when every installed language calls
  it wrong, and `pick_languages()` keeps one dictionary per language
  (Windows lists nineteen kinds of English).
- `worth_flagging()` turns down links, addresses, file names, words with
  digits, abbreviations in capitals, and the words ignored on this computer.

Positions are counted in UTF-16 units throughout, which is what Windows
reports and what a Tk Text widget's columns count; `utf16_slice()` cuts
text the same way. The editor's side — when to look, the menu — is
`ui/spelling.py`.

### Where it's tested

`test_spelling.py` needs no window and no Windows: the dictionaries are
stood in for. qa6 drives the editor with a stand-in that knows exactly which
words are wrong, and asks the real checker once, on Windows.

## `noteorganizer/core/tables.py`

**What it's for.** Everything a table *is*, with the screen nowhere in
sight: rows as lines of text, cells as what sits between pipes, and the
rules for keeping columns lined up, merging cells, and reading the
separator row. The drawn grid the user sees lives in `note_organizer.py`;
this module is what that grid reads from and writes back to.

**Three in-cell markers, same idiom.** `LINE_BREAK` (`<br>`) is a line break inside a cell — Markdown's own — so a multi-line cell is still one line of note text; `CHECKBOX_EMPTY`/`CHECKBOX_DONE` (`[ ]`/`[x]`, Markdown's task syntax) make a cell a clickable checkbox, read back by `checkbox_state()`; and `cell_display_lines()` splits a value into what the grid draws. All three are plain text in the stored row, which is the whole point.

**The one idea everything follows from.** A table is stored in the note's
own text, in Markdown's table syntax:

```
| Day       | Lunch  |
| :-------: | ------ |
| Monday    | Soup   |
```

Every function here is text-in, text-out. `split_row()` takes a line
apart into cell strings; `cell_bounds()` says where each cell's text
sits *inside* the line (so character formatting stored against the body
can find its cell); `find_blocks()` walks a whole note and returns which
line-ranges are tables. `is_table_row()` requires at least two cells —
`| just one |` reads as prose, on purpose.

**`align()` — the columns line up again.** After any edit, cells in one
column can be different widths. `align()` re-pads every cell to the
column's width — but the interesting part is that it *reports* every
character it added or removed as `(offset, delta)` pairs, the same shape
list renumbering uses, so `shift_spans()` can move the bold and the
colors along with the text. Without that, padding a table would slide
the formatting in every line after the edit. Each edit is recorded where
it happens, not at the line's end — padding goes *between* cells, so a
word in a later cell of the same row moves too.

**Merges.** A cell holding `<` means "part of the cell to my left"; `^`
means "part of the cell above". `merge_map()` resolves those markers
into spans (which anchor cell covers what) and the set of covered
positions. The markers are just text, so merges survive save, share and
export like everything else, and `richtext.py` turns them into
`colspan`/`rowspan` on the way out.

**The separator row.** `|-----|:---:|~|` as a block's second row is
mechanics, not data: the dash count is the column's display width (a
hand-dragged resize is remembered as more or fewer dashes), the colons
are its alignment, and `~` is a hidden column. `parse_separator()` reads
those into plain dicts — with one deliberate waiver since 0.71.134: a
minimum-width cell (three characters or fewer, the `---` every markdown
serializer writes regardless of content) carries no width opinion and
parses as `width=None`, so pasted tables size to their content while a
hand-authored width (always 4+, the setter floors it there) stays
exact. `make_separator()` writes authored widths back to the dash, so
regenerating the row never forgets a resize —
and `separator_index()` only accepts it in a block's first
two rows, where Markdown puts it; a dashed line further down is far more
likely to be content. `align()` treats the separator as mechanics too:
its dashes are never measured as content, but a column hand-widened past
its content pads the data out to match.

**What deliberately is NOT here.** Anything that knows about pixels,
fonts, clicks or canvases — that is the grid's half, in
`note_organizer.py`, and the split is what makes this half testable in
`test_tables.py` with no window at all. The border between the two
halves is where the hard-won lessons live (Tk counts text in UTF-16
units, embedded windows occupy an index but not a character, a rebuild
can destroy the canvas mid-click) — see ARCHITECTURE's "Tables: plain
text is the store" and the table entries in ISSUES_LOG.

### Where it's tested

`test_tables.py` — no window at all.

## `noteorganizer/core/sharing.py`

**What it's for.** Turning notes into a block of text you can paste into a
chat, and back again.

```
notes -> JSON -> zlib compress -> Base64 -> "NOTE1:" + text
```

**It's compression, not encryption.** Anyone with the code can read it.
Worth being clear about, because Base64 output *looks* scrambled and it
would be easy to assume otherwise.

### The part actually worth learning: distrusting your own input

Decoding runs on text a user pasted from who-knows-where, so every stage
assumes the worst. This is the best example of defensive programming in
the codebase:

| Guard | Stops |
|---|---|
| `MAX_SHARE_CODE_CHARS` | absurdly long input, rejected before any work |
| `_bounded_decompress` | a **zip bomb** |
| `MAX_SHARED_NOTES` | one code flooding the notebook |
| `_safe_extract_zip` | a **Zip Slip** path-traversal attack, a zip-bomb-shaped entry or archive (`backup_entries_problem`), a disk without room (`backup_space_problem`) |

Two of those deserve explanation.

**Zip bomb.** A tiny compressed payload that expands to gigabytes. Calling
`zlib.decompress()` on one exhausts memory *before it returns* — so
checking the size afterwards is already too late. The fix is to decompress
in chunks through a decompressor object and stop the moment you cross the
limit:

```python
while chunk := decompressor.decompress(..., limit_step):
    total += len(chunk)
    if total > limit:
        raise ValueError(...)
```

**Zip Slip.** A ZIP entry named `../../something` would, on naive
extraction, write *outside* the folder you chose. `_safe_extract_zip`
resolves each entry's final path and refuses anything that doesn't still
sit under the destination.

The general lesson: **when data comes from outside, enforce limits during
processing, not after.** Anything that checks "was that too big?" after
the fact has already paid the cost.

And its other half: **every limit on reading is a promise about writing.**
The app makes share codes and backups itself, so `encode_share_code`
refuses to make a code its decoder would refuse, and the export runs
`backup_entries_problem` over the archive it has just written. A fixed
500 MB ceiling on the reading side alone once made backups the app wrote
and then refused to restore
([the story](ISSUES_LOG.md#the-backup-the-app-could-not-restore)).

---

## `noteorganizer/core/duplicates.py`

**What it's for.** Deciding when two notes are really the same note, so
Settings can offer to tidy them up.

Two normalisations do the real work:

- `_strip_copy_suffix` removes any number of trailing `" (copy)"` markers,
  so a note and its duplicate match *even though the app renamed one of
  them*.
- `_normalize_ws` collapses runs of whitespace, so a stray blank line
  doesn't hide a match.

Date, colour, attachments and pinned state are ignored **on purpose**. Two
notes with identical text are the same note to a person, even if one is
pinned — the comparison encodes a human judgement, not a mechanical one.

### One performance idea

Grouping uses a dictionary of `key -> [notes]`, not a comparison of every
note against every other note:

```python
groups.setdefault(_dup_key(n), []).append(n)
```

Comparing every pair would be *quadratic* — 1,000 notes means ~500,000
comparisons; 5,000 notes means ~12.5 million. Building a dict touches each
note once. Same answer, and it stays fast as the notebook grows. Reaching
for a dict to avoid a nested loop is one of the most reliably useful
instincts in everyday Python.

---

## `noteorganizer/core/paths.py`

**What it's for.** Deciding which folder holds your notes, migrating data
forward from older locations, and cleaning up leftovers.

This is the most dangerous code in the project — it *moves and deletes
files* — and it's worth reading precisely for that reason.

### Two situations, handled differently

| Running as | Data goes | Why |
|---|---|---|
| a `.py` script | beside the script | convenient while developing |
| a `.py` script with a `notebook_location.txt` beside it | the folder that file names | the developer's own notebook, out of the working tree |
| a `.exe` | your `%APPDATA%` folder | always writable, never auto-cleaned |

`chosen_notebook_dir` reads that file: its first line that is not blank or
a `#` comment, with environment variables expanded. The file is git-ignored
and lives only beside the real checkout, so the scratch copies the tests run
keep their data in their own folders. And `initialise` brings nothing into
the folder it names: no migration, no purge.

A one-file `.exe` unpacks into a temp folder Windows later deletes, and
Program Files may be read-only — so "next to the app" is unreliable once
it's distributed.

Note that `resolve_data_dir` doesn't just *check* the folder exists, it
**writes a probe file** to prove it's writable. Existence isn't enough:
Program Files exists too, and fails only when you try to write.

### The rule: back up before you destroy

`run_migrations()` never overwrites a file it hasn't copied first — and if
the backup fails, it **aborts**. Losing a migration is recoverable; losing
the notes isn't. When a step can't be made safe, not doing it is the
correct outcome.

`purge_stale_copies()` is the one that deletes, and three rules hold it in
check:

1. It only removes files it recognises as its own (`OWNED_FILENAMES`,
   `OWNED_PREFIXES`) — never something you happened to put there. A
   `settings.json` also has to carry keys only this app writes, because in
   the built app one of the folders it looks at is wherever the zip was
   unpacked.
2. The `%APPDATA%` folder is **permanently exempt**, no matter how
   redundant it looks.
3. It deletes **file by file, only what it proved it had** — never a whole
   folder in one go.

The second rule exists because it was once missing, and a real notebook
was deleted. `docs/ISSUES_LOG.md` has the full story under "The cleanup
that deleted the real notebook". The exemption is not tidy-up-later code.
The third is newer: the purge used to compare attachments by name, at the
top level only, and then remove the whole attachments tree, so a file in a
subfolder was destroyed without ever having been copied.

`is_redundant_copy()` is the judgement behind it: a folder counts as
redundant only if every note in it is already present locally *and* every
attachment in it exists locally byte for byte, with nothing else beside
them. Content is compared by **signature**, not by counting files — "10
notes here, 10 notes there" must never be mistaken for "the same 10 notes".

### Two bugs this extraction caused — both worth learning from

Moving this code broke things in ways that looked impossible for a "pure
move". Both are classic Python traps.

**1. `__file__` means something different once a file moves.**

The old code decided where data lives like this:

```python
script_dir = os.path.dirname(os.path.abspath(__file__))
```

That was correct while it lived in `note_organizer.py`. The moment it
moved into `noteorganizer/core/paths.py`, `__file__` pointed *there* — so
the app chose a data folder two levels too deep, and cheerfully migrated
real notes into it.

The fix: pass the directory in as an argument.

```python
APP_DIR, STORAGE_WARNING = resolve_data_dir(
    os.path.dirname(os.path.abspath(__file__)))   # in the ENTRY POINT
```

Now the answer can't change again just because a file moved. **If a
function's behaviour depends on where its source file lives, moving it
changes its behaviour** — even when nothing else about it changed.

**2. Monkeypatching a re-exported name stops working.**

`test_data_safety.py` faked the AppData folder like this:

```python
NO.get_appdata_dir = lambda: fake_dir      # note_organizer.get_appdata_dir
```

That worked while `run_migrations` lived in the same module. After the
move, `run_migrations` looks up `get_appdata_dir` in **`paths.py`'s**
namespace, so the patch had no effect — and the test silently began
running against the *real* `%APPDATA%`.

The fix is to patch where the name is **looked up**, not where it's
re-exported:

```python
from noteorganizer.core import paths as NO_paths
NO_paths.get_appdata_dir = lambda: fake_dir
```

This is the single most common surprise when splitting a module. `from x
import y` copies a *reference*; rebinding one name never affects the
other. Both bugs are pinned by regression tests now.

---

## `noteorganizer/core/storage.py`

**What it's for.** Everything that reads or writes `notes_data.json`,
`settings.json`, `templates.json` and `trash.json`, plus the pre-flight
backup of the notes file.

`load_notes` and `save_notes` arrived here last, and are worth a look
because of *how* they had to change. They were methods on the app class —
not because either drew anything, but because that is where all the code
used to live. Two details did not survive the move unchanged:

* `load_notes` used to read the entry module's `VERSION_CHANGE` global.
  Values on that module are exactly what goes missing when the app runs as
  a script (see `docs/ISSUES_LOG.md`, "The module that existed twice"), so
  it is a parameter now — the caller, which does know, passes it in.
* `save_notes` used to open an error dialog itself. Nothing in this layer
  may touch the interface, so it returns `(ok, exception)` and lets the
  caller decide what a failure looks like on screen.

Both are the general shape of moving code down here: the logic comes as-is,
but anything that reached *up* — to a global on the entry module, or to a
widget — has to become an argument or a return value.

### A setting read fresh, clamped on the way in

`trash_retention_days()` is small but shows a pattern worth copying: the
trash window is a *setting*, so the function reads it from disk on every
call rather than caching it — the user can change it mid-session and the
next purge should honour the change. And it never trusts what it reads:
booleans and non-integers fall back to the 30-day default, and integers
clamp into 1–365. The failure it guards against is concrete — a
hand-edited `settings.json` saying `0` or `"forever"` must degrade to
"keep notes the normal length of time", never to "purge everything at
startup". When a bad value can choose between two wrong behaviours, pick
the one that keeps data.

### The binding rule this module is built around

Storage doesn't decide *where* the files are — `paths` does. It reads them
as **attributes**:

```python
with open(paths.SETTINGS_FILE) as f: ...
```

When `storage.py` is imported the paths are still `None` — they only get
filled in later, when `paths.configure()` runs — so `from .paths import
SETTINGS_FILE` would copy `None` permanently, while `paths.SETTINGS_FILE`
is looked up when the function actually runs; this is the same
import-binding trap that broke the monkeypatched test, told in full under
[the paths extraction bugs](#two-bugs-this-extraction-caused--both-worth-learning-from).

### The pattern every loader follows

Each `load_*` returns something usable no matter what it finds — missing
file, unreadable file, or valid JSON of entirely the wrong shape all give
an empty default rather than an exception. The app is meant to keep running
with an empty notebook, not refuse to start because one file got damaged.

`save_setting` (singular) is read-modify-write rather than a blind overwrite, so two
features updating different keys can't clobber each other.

---

## `noteorganizer/core/categories.py`

**What it's for.** The live category map, and moving it to and from
settings.

### Shared mutable state, and the one rule that makes it safe

`CATEGORY_COLORS` is a plain dict that the UI mutates in a handful of
places, and which `model.py` reads to decide whether a note's category
still exists.
Sharing mutable state across modules is usually asking for trouble. It
works here because of a single rule:

> The name is **bound exactly once**. Every change after that mutates the
> dict *in place*.

`.clear()`, `.update()`, `[name] = colour`, `.pop()` — all mutations.
Because `from ... import CATEGORY_COLORS` copies a **reference**, every
module ends up pointing at the same dict object and sees every change.

Rebinding it would silently break that:

```python
CATEGORY_COLORS = load_categories()     # DON'T — see below
```

The module doing that gets a brand-new dict; everyone else keeps the old
one. No error, no warning — the two just drift apart. Which is why the
startup path does this instead:

```python
CATEGORY_COLORS.clear()
CATEGORY_COLORS.update(load_categories())
```

Same visible outcome, one object.

This is the same distinction as the `paths.SETTINGS_FILE` case above, seen
from the other side: **mutation is shared, rebinding is not.**

### General is special

"General" always exists and always sorts first. It's the fallback home for
notes whose category is deleted, so it can never itself be removed —
guaranteed in `load_categories()` rather than trusted to the UI, because a
guarantee enforced at the data layer can't be forgotten by a caller.

---

## `noteorganizer/core/model.py`

**What it's for.** What a note *is* — and `normalize_note`, the single gate
every note passes through before the rest of the app is allowed to touch
it.

### Why this function matters more than it looks

Notes arrive from a JSON file you can hand-edit, from backups written by
older versions, and from share codes typed in from elsewhere. Any field
might be missing, be the wrong type, or hold something nonsensical.

Rather than defend against that everywhere, everything funnels through one
function that returns a note of known shape:

- a `None` title becomes `""`
- a checklist that isn't a list becomes `[]`
- a category that no longer exists falls back to "General"

So a corrupt entry degrades into a slightly emptier note instead of taking
down the note list.

**Validate once, at the edge, then trust the data inwards.** You've now
seen the same idea three times — `normalize_recurrence`,
`normalize_formatting`, and here — and `normalize_note` delegates to both
of those for their parts of the note. That repetition is the point: it's
one habit applied consistently, not three separate tricks.

### Richness, and why it exists

`note_is_empty` and `note_richness` support cleanup. When duplicates are
merged, richness decides *which copy to keep* — the one carrying the most
actual content — rather than picking arbitrarily and hoping. `clean_notes`
uses both to drop blank notes and de-duplicate on load, and reports what it
did so the app can tell you rather than silently changing your notebook.

---

## `noteorganizer/core/welcome.py`

**What it's for.** The note a first install opens on: a short guide to
each part of the app, ending in a good-luck line, as an ordinary note the
person can delete.

### Written the way the editor would write it

`LINES` is the text, one line at a time, in a markup small enough to read
at a glance: `# ` starts a heading, `- ` a bullet, `**` marks bold.
`build_welcome_note()` turns it into a note's own fields — the body with
its `• ` markers in the text, bold as character spans over that body, each
bullet line as a `paragraphs` entry — which is exactly the shape
[`formatting.py`](#noteorganizercoreformattingpy) describes for a typed
note. So nothing downstream treats it differently: `normalize_note`
changes nothing on it, and the editor shows it and saves it back
unchanged (`test_data_safety` and qa5 check both).

### Who gets it, once

`storage.load_notes` reports `fresh_notebook` only when there was no notes
file at all. The app adds the note on that start alone, and records
`welcome_offered` so it never adds another on its own. An emptied notebook
or an unreadable one still had its file, and a notebook a migration copied
in has one by the time it is read, so none of them is greeted. Settings →
About's **Show** opens the note by the uid it stored, or adds a fresh copy
if that one was deleted.

One thing learned building it: its icons carry no emoji variation selector
(U+FE0F). Tk draws that character as a blank two letters wide, so "✍️ Write"
showed a gap after the hand.

---

## Where the app starts

Worth knowing once you've read the modules: **importing `note_organizer`
does nothing.**

Resolving the data folder, migrating notes from older locations, purging
stale copies and recording the version all happen in `initialise()`, which
`NoteOrganizer.__init__` and `_main()` both call.

It didn't always work that way, and the reason it does now is the most
serious bug in this project's history: those steps move and delete files,
and running them as a side effect of an `import` destroyed a real notebook
once. Anything wanting the data layer without opening a window —
`test_data_safety.py`, for instance — now has to ask for it deliberately.

If you take one habit from this file, make it that one: **an import should
not change anything.**
