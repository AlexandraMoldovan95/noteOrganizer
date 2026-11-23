"""The in-note calculator's expression evaluator: a string such as
``"(5+3)×2"``, built with the panel's buttons or typed and pasted into its
display, turned into a number (:func:`evaluate_calculator_expression`), and
a number into a tidy display string (:func:`format_calculator_result`).

Hand-written rather than ``eval()``, which runs any Python it is given: a
tokeniser, then one function per precedence level, each calling the next,
the call order being the precedence rule (``docs/CODE_TOUR.md`` walks it).
Anything malformed raises :class:`CalcError`, caught once and given as None.
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


# The three bracket styles are one and the same group, purely visual: a
# mismatched "(5+3]" still evaluates, rather than being refused for a
# difference the person almost certainly did not mean.
_CALC_OPEN_BRACKETS = "({["
_CALC_CLOSE_BRACKETS = ")}]"

# Every character that is a complete token on its own. Note these are the
# typographic symbols shown on the calculator buttons (− × ÷, not - * /),
# because that is literally what ends up in the display text.
_CALC_SINGLE_CHAR_TOKENS = "+−×÷√^%" + _CALC_OPEN_BRACKETS + _CALC_CLOSE_BRACKETS

# What a keyboard types for the buttons' symbols. Typed sums gave "Error".
_CALC_TYPED = {"-": "−", "*": "×", "x": "×", "X": "×", "/": "÷", ":": "÷"}


def _as_buttons_spell(expr):
    """*expr* with what a keyboard types read as the buttons' symbols, and a
    comma between two digits as the decimal point, as Romanian writes 2,5 --
    unless exactly three digits follow it: 1,000 is a thousand in English
    and one in Romanian, so it stays a comma and the sum says Error, never
    a number nobody meant."""
    out = []
    for k, ch in enumerate(expr):
        if ch == "," and k > 0 and expr[k - 1].isdecimal():
            run = 0
            while k + 1 + run < len(expr) and expr[k + 1 + run].isdecimal():
                run += 1
            if run and run != 3:
                out.append(".")
                continue
        out.append(_CALC_TYPED.get(ch, ch))
    return "".join(out)


def _tokenize_calc_expression(expr):
    """Split raw expression text into a flat list of tokens.

    Numbers come out as ``float``, operators and brackets as
    one-character strings. ``"12+3"`` becomes ``[12.0, "+", 3.0]``.

    Raises:
        CalcError: if a character can't be part of any valid expression.
    """
    expr = _as_buttons_spell(expr)
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
        # isdecimal(), not isdigit(), which is True for superscripts and
        # other digit-like characters too: a pasted lookalike is "unexpected",
        # rather than merged into the number beside it.
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
    """Evaluate a calculator expression like '(5+3)×2' or '√{4+5}^2':
    +/−/×/÷ with their usual precedence, three interchangeable bracket
    styles, a prefix '√', a right-associative '^' ('2^3^2' is '2^(3^2)')
    and a postfix '%'. Buttons and typing alike arrive as plain text, and
    go through the same checks; the caller shows "Error" for None, so a bad
    expression never crashes the app.

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
    # below can advance it: assigned there, a plain int would be a new local.
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
        # Unary +/− here, not in parse_unary, so a sign takes the whole power:
        # "-2^2" is -4, as Python's ** does. The exponent is parse_power()
        # again, not a loop: right-associative, "2^3^2" is 512.
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
    except (CalcError, RecursionError):
        # RecursionError: 200 nested brackets, or a thousand signs, outran
        # the parser's own recursion and reached the window's error toast.
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
