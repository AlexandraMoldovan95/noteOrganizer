"""Dedicated test suite for the in-note calculator's expression evaluator,
separate from the GUI-based QA scripts — runs headlessly with no tkinter
needed, same pattern as test_recurrence.py. The calculator's buttons only
ever produce '+', '−' (not a plain ASCII hyphen), '×', '÷', '^', '(', ')',
'{', '}', '[', ']', '√', '%', digits, and '.', so every expression here
uses those exact characters — this also doubles as the evaluator's
coverage for expressions typed or pasted directly (see qa1.py for that),
since both paths feed the exact same plain-text string into this
function with no distinction made between them.
Check descriptions are kept ASCII-only on purpose — printing the real
'−'/'×' characters crashes on a plain Windows console using the cp1252
codepage, unrelated to whether the evaluator itself works correctly."""
import os
import sys
# Settled as a guest of this computer before the app's code (qa/_qa_support,
# beside this file in a scratch copy, in qa/ where CI runs it).
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa"))
from _qa_support import as_a_guest  # noqa: E402
as_a_guest()
import note_organizer as NO  # noqa: E402

fails = []
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

ev = NO.evaluate_calculator_expression
fmt = NO.format_calculator_result

# ---- Basic arithmetic ----
check('addition (5+3=8)', ev('5+3') == 8)
check('subtraction (10-4=6)', ev('10−4') == 6)
check('multiplication (6x7=42)', ev('6×7') == 42)
check('division (20/4=5)', ev('20÷4') == 5)

# ---- Operator precedence (x// bind tighter than +/-) ----
check('precedence: 5+3x2 = 11, not 16', ev('5+3×2') == 11)
check('precedence: 10-2x3 = 4', ev('10−2×3') == 4)
check('precedence: 2+6/3 = 4', ev('2+6÷3') == 4)

# ---- Parentheses override precedence ----
check('parens: (5+3)x2 = 16', ev('(5+3)×2') == 16)
check('parens: 5x(3+2) = 25', ev('5×(3+2)') == 25)
check('nested parens: ((1+2)x3) = 9', ev('((1+2)×3)') == 9)
check('parens: (2+3)x(4-1) = 15', ev('(2+3)×(4−1)') == 15)
check('parens: 10/(2+3) = 2', ev('10÷(2+3)') == 2)

# ---- Unary minus ----
check('leading unary minus: -5+3 = -2', ev('−5+3') == -2)
check('unary minus after operator: 5x-2 = -10', ev('5×−2') == -10)

# ---- Decimals ----
check('decimals: 1.5+2.5 = 4', ev('1.5+2.5') == 4)
check('decimal division: 5/2 = 2.5', ev('5÷2') == 2.5)

# ---- Alternate bracket styles ({} and [] as pure grouping, same as ()) ----
check('curly braces group like parens: {5+3}x2 = 16', ev('{5+3}×2') == 16)
check('square brackets group like parens: [5+3]x2 = 16', ev('[5+3]×2') == 16)
check('mismatched bracket styles still pair up: (5+3] = 8', ev('(5+3]') == 8)
check('nested mixed brackets: [(2+3)x{4-1}] = 15', ev('[(2+3)×{4−1}]') == 15)

# ---- Square root (prefix) ----
check('square root: sqrt(9) = 3', ev('√9') == 3)
check('square root of an expression: sqrt(4+5) = 3', ev('√(4+5)') == 3)
check('square root of a negative number returns None', ev('√(0−9)') == None)

# ---- Power (^, general, right-associative) and percent (postfix) ----
check('power: 5^2 = 25 (still works for a simple square)', ev('5^2') == 25)
check('power: 3^3 = 27 (not just squares)', ev('3^3') == 27)
check('power: 2^10 = 1024 (any exponent, not a fixed square button)', ev('2^10') == 1024)
check('power of a group: (2+3)^2 = 25', ev('(2+3)^2') == 25)
check('power is right-associative: 2^3^2 = 2^(3^2) = 512, not (2^3)^2 = 64',
      ev('2^3^2') == 512)
check('unary minus is looser than power: -2^2 = -(2^2) = -4', ev('−2^2') == -4)
check('power binds tighter than plus: 1+2^2 = 5, not 9', ev('1+2^2') == 5)
check('power binds tighter than times: 2×3^2 = 18, not 36', ev('2×3^2') == 18)
check('fractional power of a negative base has no real result -> None',
      ev('(0−8)^0.5') == None)
check('zero to a negative power is undefined -> None', ev('0^(0−1)') == None)

check('percent: 50 percent = 0.5', ev('50%') == 0.5)
check('percent binds to the number right before it: 200+10 percent = 200.1',
      ev('200+10%') == 200.1)
check('percent applies after power: 5^2 percent = 25 percent = 0.25',
      ev('5^2%') == 0.25)

# ---- Division by zero ----
check('division by zero returns None (caller shows "Error")', ev('5÷0') == None)
check('division by zero inside parens also returns None', ev('1+5÷0') == None)

# ---- Malformed input: never crashes, always returns None ----
check('empty string returns None', ev('') == None)
check('whitespace-only returns None', ev('   ') == None)
check('trailing operator returns None', ev('5+') == None)
check('unbalanced open paren returns None', ev('(5+3') == None)
check('stray close paren returns None', ev('5+3)') == None)
check('invalid characters return None', ev('abc') == None)
check('not a string returns None', ev(None) == None)
# A bare '.' passes the digit walk but float('.') raises ValueError,
# which used to escape the CalcError contract and reach the caller raw
# (audit Z00-F01). Guarded call so the mutant crashes the CHECK red, not
# the suite before its footer.
def _ev_guarded(expr):
    try:
        return ev(expr)
    except Exception:
        return 'RAISED'
check('a lone dot returns None instead of raising', _ev_guarded('.') == None)
check('an operator then a dot returns None too', _ev_guarded('5+.') == None)
# A 400-digit literal overflows float to inf without raising anything;
# a calculator display has no honest way to show inf (audit Z00-F02).
check('an overflowing result returns None, not inf', ev('9' * 400) == None)
check('inf cannot sneak in through arithmetic either',
      ev('9' * 350 + '×' + '9' * 350) == None)

# ---- format_calculator_result: clean display formatting ----
check('whole number displays without decimal', fmt(4.0) == '4')
check('negative whole number displays cleanly', fmt(-10.0) == '-10')
check('fraction displays as-is', fmt(2.5) == '2.5')
check('float noise from 0.1+0.2 displays as clean 0.3', fmt(ev('0.1+0.2')) == '0.3')

# Brackets 200 deep, or a thousand signs, outran the parser's recursion: the
# RecursionError reached the window's error toast, and the display was not
# set to Error.
def _deep(expression):
    """The answer, or "raised": a raise is the failure this guards, and it
    must be one red check, not a crash that ends the suite before its footer."""
    try:
        return ev(expression)
    except RecursionError:
        return "raised"


# Typed on a keyboard, a sum said Error: - * x / : are the buttons'
# − × ÷, and a comma between digits is the decimal point, as Romanian writes.
check('a keyboard\'s - * x / : are the buttons\' signs',
      (ev('5-3'), ev('5*3'), ev('5x3'), ev('5/2'), ev('5:2')) == (2.0, 15.0, 15.0, 2.5, 2.5))
check('a comma between digits is the decimal point, and nowhere else',
      ev('2,5+2,5') == 5.0 and ev('2,+3') is None and ev('1,2345') == 1.2345)
# ...but not before exactly three digits: 1,000 is a thousand in English.
check('a comma before exactly three digits is refused, never read as a point',
      ev('1,000+5') is None and ev('2,500') is None)

check('200 nested brackets give no answer rather than an error',
      _deep('(' * 200 + '1' + ')' * 200) is None)
check('a thousand minus signs give no answer rather than an error',
      _deep('-' * 1000 + '1') is None)

print()
print(f"FAILURES: {fails if fails else 'none'}")

import sys
sys.exit(1 if fails else 0)
