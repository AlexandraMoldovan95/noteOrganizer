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

*More sections will be added here as further modules are extracted.*
