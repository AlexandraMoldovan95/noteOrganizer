"""The in-note calculator's expression evaluator.

WHAT THIS MODULE IS FOR
-----------------------
The note editor has a small calculator panel. Whatever the user builds
there — by tapping buttons, or by typing/pasting straight into the
display — arrives here as an ordinary string like ``"(5+3)×2"``. This
module turns that string into a number.

Three things are exported:

* :func:`evaluate_calculator_expression` — string in, number out (or
  ``None`` if the string doesn't make sense).
* :func:`format_calculator_result` — number in, tidy display string out.
* :class:`CalcError` — raised internally while parsing; callers outside
  this module never see it.

WHY IT'S HAND-WRITTEN INSTEAD OF USING eval()
---------------------------------------------
Python has a built-in ``eval()`` that would run ``"(5+3)*2"`` in one
line. It is not used here on purpose: ``eval()`` runs *any* Python code
it is given, so a pasted string could do far more than arithmetic. A
parser this small costs little to write and removes that risk entirely,
rather than depending on the input always staying well behaved.

HOW THE PARSING WORKS (the part worth learning)
-----------------------------------------------
It happens in two stages, which is how most real language parsers are
built:

1. **Tokenising** (:func:`_tokenize_calc_expression`) — chop the raw text
   into a flat list of meaningful pieces. ``"12+3"`` becomes
   ``[12.0, "+", 3.0]``. Numbers become real floats here; everything else
   stays a one-character string.

2. **Parsing** — walk that list and compute the answer, using one small
   function per precedence level. They call each other in a chain, and
   that chain *is* the precedence rule:

   ``parse_expression`` (+ −) → ``parse_term`` (× ÷) → ``parse_percent``
   (%) → ``parse_power`` (^ and unary sign) → ``parse_unary`` (√,
   brackets, plain numbers)

   Because ``parse_expression`` asks ``parse_term`` for its operands, and
   ``parse_term`` binds more tightly, ``2+3×4`` correctly gives 14 rather
   than 20. Nothing else enforces that — the call order does.

   The innermost level, ``parse_unary``, handles brackets by calling
   ``parse_expression`` again on what's inside them. A function that
   (indirectly) calls itself like this is *recursion*, and it's what lets
   brackets nest to any depth without extra code.

Two small implementation details that are easy to miss:

* ``pos = [0]`` is a one-item list, not a plain number, because the inner
  functions need to *change* how far through the token list we are.
  Reassigning a plain ``pos`` inside a nested function would create a new
  local variable instead of updating the outer one; mutating a list
  avoids that. (``nonlocal`` would also work.)
* Anything malformed raises :class:`CalcError`, which is caught once at
  the bottom and turned into ``None``. That keeps every failure path —
  bad characters, unbalanced brackets, division by zero — in one place,
  so a bad expression can never crash the app.
"""

import math

__all__ = [
    "CalcError",
    "evaluate_calculator_expression",
    "format_calculator_result",
]


class CalcError(Exception):
    """Raised while parsing when an expression turns out to be invalid.

    Used purely as an internal signal: every raise is caught inside
    :func:`evaluate_calculator_expression`, which returns ``None``
    instead. Callers therefore never need to handle this themselves.
    """


# The three bracket styles are interchangeable and purely visual — '(', '{'
# and '[' all mean "start a group". They are NOT treated as distinct types,
# so a mismatched pair like "(5+3]" still evaluates rather than being
# rejected for a difference the user almost certainly didn't intend.
_CALC_OPEN_BRACKETS = "({["
_CALC_CLOSE_BRACKETS = ")}]"

# Every character that is a complete token on its own. Note these are the
# typographic symbols shown on the calculator buttons (− × ÷, not - * /),
# because that is literally what ends up in the display text.
_CALC_SINGLE_CHAR_TOKENS = "+−×÷√^%" + _CALC_OPEN_BRACKETS + _CALC_CLOSE_BRACKETS


def _tokenize_calc_expression(expr):
    """Split raw expression text into a flat list of tokens.

    Numbers come out as ``float``, operators and brackets as
    one-character strings. ``"12+3"`` becomes ``[12.0, "+", 3.0]``.

    Raises:
        CalcError: if a character can't be part of any valid expression.
    """
    tokens = []
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue
        if ch in _CALC_SINGLE_CHAR_TOKENS:
            tokens.append(ch)
            i += 1
            continue
        # isdecimal(), not isdigit(): str.isdigit() is True for superscript/
        # other non-ASCII digit-like characters too (they have a defined
        # digit value even though they aren't plain 0-9) — isdecimal() is
        # the one that actually means "a real decimal digit," so pasted
        # text with a lookalike character correctly falls through to the
        # "unexpected character" error instead of silently merging into a
        # nearby number literal.
        if ch.isdecimal() or ch == ".":
            j = i
            seen_dot = False
            # Walk forward while we're still inside one number. The
            # seen_dot flag stops "1.2.3" being read as a single value.
            while j < n and (expr[j].isdecimal() or (expr[j] == "." and not seen_dot)):
                if expr[j] == ".":
                    seen_dot = True
                j += 1
            # The walk admits a bare "." (one dot, zero digits), which
            # float() rejects with a ValueError that used to escape the
            # CalcError contract and reach the caller raw.
            try:
                tokens.append(float(expr[i:j]))
            except ValueError:
                raise CalcError(f"not a number: {expr[i:j]!r}")
            i = j
            continue
        raise CalcError(f"unexpected character {ch!r}")
    return tokens


def evaluate_calculator_expression(expr):
    """Evaluate a calculator expression like '(5+3)×2' or '√{4+5}^2', with
    standard +/−/×/÷ precedence, three interchangeable bracket styles
    (`()`, `{}`, `[]` — purely visual grouping, not distinct types, so
    mismatched pairs like '(5+3]' still evaluate), a prefix square-root
    '√', a power operator '^' (right-associative, e.g. '2^3^2' is
    '2^(3^2)', not '(2^3)^2' — the usual math convention), and a postfix
    percent '%'. Returns the numeric result, or None if the expression is
    empty, malformed (unbalanced brackets, trailing operator, stray
    characters, a square root of a negative number, a power with no real
    result like a fractional power of a negative base...), or divides by
    zero — the caller shows "Error" for None rather than ever letting a
    bad expression crash the app. Input can come from the calculator's
    own buttons OR from directly typing/pasting into the display field —
    both are just plain text by the time they reach here, so both go
    through the exact same validation with nothing assumed about where
    the string came from.

    Deliberately hand-rolled instead of eval(): a parser this small costs
    little and removes the risk entirely, rather than relying on the
    input always staying constrained to safe characters.

    Args:
        expr: The expression text. Anything that isn't a non-empty
            string is rejected rather than assumed valid.

    Returns:
        The result as a number, or ``None`` for any invalid expression.
        There is deliberately no "partly worked" result and no exception
        to handle — one return value covers every failure.
    """
    if not isinstance(expr, str) or not expr.strip():
        return None
    try:
        tokens = _tokenize_calc_expression(expr)
    except CalcError:
        return None
    if not tokens:
        return None

    # A one-item list rather than a plain int, so the nested functions
    # below can advance it — see the module docstring.
    pos = [0]

    def peek():
        """The token we're looking at, without consuming it (None at end)."""
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def advance():
        """Consume the current token and return it."""
        tok = tokens[pos[0]]
        pos[0] += 1
        return tok

    def parse_expression():
        """Lowest precedence: addition and subtraction."""
        value = parse_term()
        while peek() in ("+", "−"):
            op = advance()
            rhs = parse_term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def parse_term():
        """Multiplication and division — binds tighter than + and −."""
        value = parse_percent()
        while peek() in ("×", "÷"):
            op = advance()
            rhs = parse_percent()
            if op == "×":
                value = value * rhs
            else:
                if rhs == 0:
                    raise CalcError("division by zero")
                value = value / rhs
        return value

    def parse_percent():
        # Postfix — binds to the whole power expression immediately
        # preceding it, e.g. "5^2%" is "(5^2)%" = 0.25, not "5^(2%)".
        value = parse_power()
        while peek() == "%":
            advance()
            value = value / 100
        return value

    def parse_power():
        # Unary +/− live HERE, not in parse_unary below, so a leading sign
        # applies to the whole power expression that follows — "-2^2" is
        # "-(2^2)" = -4 (matching Python's own ** operator and standard
        # convention), not "(-2)^2" = 4. Right-associative: "2^3^2" is
        # "2^(3^2)" = 512, not "(2^3)^2" = 64 — which is what calling
        # parse_power() again for the exponent (rather than looping) does.
        if peek() == "−":
            advance()
            return -parse_power()
        if peek() == "+":
            advance()
            return parse_power()
        base = parse_unary()
        if peek() == "^":
            advance()
            exponent = parse_power()
            try:
                result = base ** exponent
            except (OverflowError, ZeroDivisionError, ValueError):
                raise CalcError("invalid power")
            # e.g. (-8) ** 0.5 — Python returns a complex number rather
            # than failing, and there is no sensible way to show that on a
            # calculator display, so it's treated as invalid.
            if isinstance(result, complex):
                raise CalcError("power has no real result")
            return result
        return base

    def parse_unary():
        # Only √, brackets, and plain numbers — unary +/− are handled one
        # level up, in parse_power, so a sign correctly applies to an
        # entire power expression rather than just the base.
        tok = peek()
        if tok == "√":
            advance()
            operand = parse_power()
            if operand < 0:
                raise CalcError("square root of a negative number")
            return math.sqrt(operand)
        if isinstance(tok, str) and tok in _CALC_OPEN_BRACKETS:
            advance()
            # Recursion: whatever is inside the brackets is itself a full
            # expression, so we start again from the top for it.
            value = parse_expression()
            nxt = peek()
            if not (isinstance(nxt, str) and nxt in _CALC_CLOSE_BRACKETS):
                raise CalcError("unbalanced brackets")
            advance()
            return value
        if isinstance(tok, float):
            advance()
            return tok
        raise CalcError("unexpected token")

    try:
        result = parse_expression()
        if pos[0] != len(tokens):
            return None  # leftover tokens, e.g. a stray closing bracket
        if not math.isfinite(result):
            # 9e307+9e307 overflows float to inf without raising anything;
            # a calculator display has no honest way to show inf/nan.
            return None
        return result
    except CalcError:
        return None


def format_calculator_result(value):
    """1.0 -> '1' (whole numbers display clean); rounds to 10 decimal
    places first to hide float noise like 0.1+0.2 != 0.3 exactly.

    Args:
        value: The number returned by :func:`evaluate_calculator_expression`.

    Returns:
        A display string with no trailing zeros or trailing dot.
    """
    rounded = round(value, 10)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.10f}".rstrip("0").rstrip(".")
