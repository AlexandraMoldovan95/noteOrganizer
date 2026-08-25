"""Tests for turning HTML into a note and a note back into HTML.

Headless and pure, like test_recurrence.py and test_calculator.py: this
converts strings to strings, so it needs no clipboard, no window and no
Windows. That is the point of keeping the conversion out of the widget
layer -- the app runs on Windows and this suite runs on Linux.

Check descriptions stay ASCII-only, for the same reason test_calculator.py
does: printing a bullet crashes a plain Windows console on cp1252.
"""
import note_organizer as NO
from noteorganizer.core.richtext import html_to_note, note_to_html
from html.parser import HTMLParser

fails = []


def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        fails.append(name)


BULLET, SUB_BULLET, SUB_SUB = "• ", "◦ ", "▪ "


# ---------------------------------------------------------------- in ----
text, spans, paras = html_to_note(
    "<p>A <b>bold</b> word and an <i>italic</i> one.</p>")
check("markup becomes plain text with the tags gone",
      text == "A bold word and an italic one.")
check("bold arrives as a span over the right characters",
      {"start": 2, "end": 6, "style": "bold"} in spans)
check("italic likewise",
      {"start": 19, "end": 25, "style": "italic"} in spans)

for markup, style in (("<strong>x</strong>", "bold"), ("<em>x</em>", "italic"),
                      ("<u>x</u>", "underline"), ("<s>x</s>", "strike"),
                      ("<del>x</del>", "strike"), ("<ins>x</ins>", "underline")):
    _t, _s, _p = html_to_note(markup)
    check(f"{markup} maps to {style}",
          _s == [{"start": 0, "end": 1, "style": style}])

_t, _s, _p = html_to_note('<p style="font-weight:bold">x</p>')
check("bold expressed as CSS rather than a tag is still bold",
      _s == [{"start": 0, "end": 1, "style": "bold"}])

text, spans, paras = html_to_note("<ul><li>milk</li><li>eggs</li></ul>")
check("a bulleted list gets markers in the text",
      text == BULLET + "milk\n" + BULLET + "eggs")
check("and a paragraph entry per line",
      paras == [{"line": 0, "kind": "bullet"}, {"line": 1, "kind": "bullet"}])

text, spans, paras = html_to_note("<ol><li>first</li><li>second</li></ol>")
check("a numbered list counts from one",
      text == "1. first\n2. second")

text, spans, paras = html_to_note(
    "<ul><li>top<ul><li>inner</li></ul></li></ul>")
check("a nested list is recorded at depth one",
      paras == [{"line": 0, "kind": "bullet"},
                {"line": 1, "kind": "bullet", "indent": 1}])
check("and uses the glyph for that depth",
      text == BULLET + "top\n" + SUB_BULLET + "inner")

_t, _s, _p = html_to_note(
    '<p>plain <span style="color:#ff0000">red</span> and '
    '<span style="background-color:rgb(255,255,0)">marked</span></p>')
check("a hex colour becomes a text colour span",
      {"start": 6, "end": 9, "style": "text_color", "value": "#ff0000"} in _s)
check("an rgb() background becomes a highlight span",
      {"start": 14, "end": 20, "style": "highlight", "value": "#ffff00"} in _s)

_t, _s, _p = html_to_note('<p style="text-align:center">middle</p>')
check("text-align becomes an alignment entry",
      _p == [{"line": 0, "align": "center"}])

# Everything the app has no word for is dropped rather than guessed at.
_t, _s, _p = html_to_note(
    '<p>a <sup>super</sup> and <code>code</code> and '
    '<span style="font-size:42px">huge</span> text</p>')
check("styling with no equivalent keeps the words and drops the styling",
      _t == "a super and code and huge text" and _s == [])

_t, _s, _p = html_to_note("<div>\n    line one\n</div>\n<div>\n    line two\n</div>")
check("indentation in the source does not become part of the note",
      _t == "line one\nline two")

check("junk does not raise", html_to_note("<p><b>unclosed")[0] == "unclosed")
check("empty input is handled", html_to_note("") == ("", [], []))
check("None is handled", html_to_note(None) == ("", [], []))

_t, _s, _p = html_to_note("<p>" + ("x" * 200_000) + "</p>")
check(f"an enormous paste is capped ({len(_t)} chars kept)",
      len(_t) <= NO_MAX if (NO_MAX := 100_000) else False)


# --------------------------------------------------------------- out ----
class _Valid(HTMLParser):
    """Balanced tags, and a list may only contain list items."""

    def __init__(self):
        super().__init__()
        self.stack, self.problems = [], []

    def handle_starttag(self, tag, attrs):
        if self.stack and self.stack[-1] in ("ul", "ol") and tag != "li":
            self.problems.append(f"<{tag}> inside <{self.stack[-1]}>")
        if tag != "br":
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"</{tag}> mismatched")
        else:
            self.stack.pop()


def valid(markup):
    parser = _Valid()
    parser.feed(markup)
    return not parser.problems and not parser.stack


check("plain text comes out as a line",
      note_to_html("hello") == "<div>hello</div>")
check("bold comes out as a tag",
      note_to_html("a bold word",
                   [{"start": 2, "end": 6, "style": "bold"}])
      == "<div>a <b>bold</b> word</div>")
check("characters that mean something in HTML are escaped",
      note_to_html("a < b & c") == "<div>a &lt; b &amp; c</div>")
check("a list is written as a real list, not as bullet characters",
      note_to_html(BULLET + "milk", [], [{"line": 0, "kind": "bullet"}])
      == "<ul><li>milk</li></ul>")
check("a numbered list uses ol",
      note_to_html("1. first", [], [{"line": 0, "kind": "number"}])
      == "<ol><li>first</li></ol>")

nested_text = BULLET + "top\n" + SUB_BULLET + "inner\n" + BULLET + "after"
nested_paras = [{"line": 0, "kind": "bullet"},
                {"line": 1, "kind": "bullet", "indent": 1},
                {"line": 2, "kind": "bullet"}]
nested_html = note_to_html(nested_text, [], nested_paras)
check("a sub-list is written inside the item it belongs to, not beside it",
      "<li>top<ul>" in nested_html)
check(f"and the result is valid markup ({nested_html})", valid(nested_html))

check("alignment is written as a style",
      'style="text-align:center;"' in note_to_html("x", [], [{"line": 0, "align": "center"}]))
check("a colour is written as a style",
      'color:#ff0000' in note_to_html(
          "red", [{"start": 0, "end": 3, "style": "text_color", "value": "#ff0000"}]))
check("an empty note produces no markup", note_to_html("") == "<div><br></div>")


# ------------------------------------------------------------ both ways --
ROUND_TRIP = [
    ("plain", "hello world", [], []),
    ("bold", "a bold word", [{"start": 2, "end": 6, "style": "bold"}], []),
    ("two styles at once", "abc",
     [{"start": 0, "end": 3, "style": "bold"},
      {"start": 0, "end": 3, "style": "italic"}], []),
    ("overlapping", "abcdef",
     [{"start": 0, "end": 4, "style": "bold"},
      {"start": 2, "end": 6, "style": "italic"}], []),
    ("a list", BULLET + "milk\n" + BULLET + "eggs", [],
     [{"line": 0, "kind": "bullet"}, {"line": 1, "kind": "bullet"}]),
    ("a nested list", nested_text, [], nested_paras),
    ("three levels", BULLET + "a\n" + SUB_BULLET + "b\n" + SUB_SUB + "c", [],
     [{"line": 0, "kind": "bullet"}, {"line": 1, "kind": "bullet", "indent": 1},
      {"line": 2, "kind": "bullet", "indent": 2}]),
    ("a numbered list", "1. one\n2. two", [],
     [{"line": 0, "kind": "number"}, {"line": 1, "kind": "number"}]),
    ("colour", "red text",
     [{"start": 0, "end": 3, "style": "text_color", "value": "#ff0000"}], []),
    ("escaping", "a < b & c > d", [], []),
]
for label, text, spans, paras in ROUND_TRIP:
    markup = note_to_html(text, spans, paras)
    back_text, back_spans, back_paras = html_to_note(markup)
    check(f"round trip keeps the text: {label}", back_text == text)
    check(f"round trip keeps the paragraphs: {label}", back_paras == paras)
    check(f"round trip produces valid markup: {label}", valid(markup))

# Styles must survive the trip, though bold+italic may come back as two
# spans where it went out as one -- the note format allows both.
markup = note_to_html("abc", [{"start": 0, "end": 3, "style": "bold_italic"}])
_t, _s, _p = html_to_note(markup)
check("bold_italic survives as bold and italic over the same characters",
      sorted(s["style"] for s in _s) == ["bold", "italic"]
      and all(s["start"] == 0 and s["end"] == 3 for s in _s))

print()
print(f"FAILURES: {fails if fails else 'none'}")

import sys
sys.exit(1 if fails else 0)
