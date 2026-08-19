# Code tour

A guided walk through the codebase, written for someone still learning
Python. It explains not just *what* each part does but *why* it's built
that way, and points at the real code so you can read along.

This is a companion to [ARCHITECTURE.md](ARCHITECTURE.md), which is the
short reference version for someone who already knows the codebase. Start
here; go there when you want the summary.

> **Status:** the project is being reorganised from one large file into
> smaller modules, one at a time. This tour grows as that happens. Sections
> marked *(still in note_organizer.py)* haven't been moved yet.

---

## How to run it

Nothing about running the app has changed, or will:

```
py note_organizer.py
```

`note_organizer.py` is still the front door. It's just getting shorter, as
code moves into the `noteorganizer/` package next to it and gets imported
back in.

The tests are unchanged too:

```
py test_calculator.py
py test_recurrence.py
py test_data_safety.py
```

The GUI tests in `qa/` need a copy of the app beside them — see the QA
safety rule in `CLAUDE.md` before running those, because they delete data
files in whatever folder they run from.

---

## The shape of the project

```
note_organizer.py         the entry point you run, plus the UI (for now)
noteorganizer/
└── core/                 data and rules — never imports tkinter
    └── calculator.py     the in-note calculator's expression parser
docs/                     these documents
qa/                       headless GUI tests
test_*.py                 tests for the core logic, no GUI needed
```

The plan is two layers:

* **`core`** — everything that would still make sense if the app had no
  windows at all: reading and writing notes, validating them, working out
  recurring dates, evaluating calculator expressions.
* **`ui`** — everything the user sees. Not created yet.

The rule that keeps them apart: **nothing in `core` may import tkinter.**
That's what lets the core be tested without opening a window, and what
would let a phone app reuse it one day.

---

## Reading order

If you're working through this for the first time:

1. **`noteorganizer/core/calculator.py`** — start here. It's small,
   completely self-contained, and it teaches a genuinely useful pattern.
2. The rest of `core`, as it gets moved.
3. The UI.

---

## 1. `noteorganizer/core/calculator.py`

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

`test_calculator.py` — 28 checks, no GUI needed, runs in under a second.
It's a good file to read straight after the module: each test names the
behaviour it's pinning down, so it doubles as a specification.

---

## 2. `noteorganizer/core/recurrence.py`

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

Four fields carry it:

| Field | Meaning |
|---|---|
| `note["date"]` | the anchor — when the series starts |
| `note["recurrence"]` | the rule itself |
| `note["exceptions"]` | days the user deleted individually |
| `note["overrides"]` | per-day content edits |

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

`test_recurrence.py` — 18 checks, no GUI. Read it alongside the module: it
covers the clamp/skip policies, count and end-date limits, exceptions, and
the performance case above.

---

*More sections will be added here as further modules are extracted.*
