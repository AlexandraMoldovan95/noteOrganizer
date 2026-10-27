"""Tests for turning HTML into a note and a note back into HTML.

Headless and pure, like test_recurrence.py and test_calculator.py: this
converts strings to strings, so it needs no clipboard, no window and no
Windows. That is the point of keeping the conversion out of the widget
layer -- the app runs on Windows and this suite runs on Linux.

Check descriptions stay ASCII-only, for the same reason test_calculator.py
does: printing a bullet crashes a plain Windows console on cp1252.
"""
import note_organizer as NO
from noteorganizer.core.richtext import (html_to_note, note_to_html,
                                        html_document, reflow_wrapped)
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

# Bold and italic as web pages really write them (field pass: bold and
# italic words copied from a page arrived plain). The reader knew four
# spellings of bold and one of italic.
_said = {}
for _name, _markup in (
        ("semibold 600", '<span style="font-weight:600">x</span>'),
        ("bolder", '<span style="font-weight: bolder">x</span>'),
        ("capitals and !important", '<span style="FONT-WEIGHT: BOLD !important">x</span>'),
        ("the font shorthand", '<span style="font: italic 700 14px/1.4 Arial">x</span>'),
        ("oblique", '<span style="font-style: oblique 10deg">x</span>'),
        ("medium 500", '<span style="font-weight:500">x</span>')):
    _said[_name] = sorted(s["style"] for s in html_to_note(_markup)[1])
check(f"bold and italic are read however a page writes them ({_said})",
      _said == {"semibold 600": ["bold"], "bolder": ["bold"],
                "capitals and !important": ["bold"],
                "the font shorthand": ["bold_italic"], "oblique": ["italic"],
                "medium 500": []})
# Google Docs wraps a whole copy in <b style="font-weight:normal">: the
# tag's own CSS takes back what the tag means, and only what Docs marks
# bold is bold. Its end tag closes only itself, never an outer bold.
_t, _s, _p = html_to_note(
    '<b style="font-weight:normal;" id="docs-internal-guid-1">'
    '<span style="font-weight:700">Bold</span> plain</b>')
check(f"a Google Docs copy is not bold all over ({_s})",
      _t == "Bold plain" and _s == [{"start": 0, "end": 4, "style": "bold"}])
_t, _s, _p = html_to_note('<strong>a <b style="font-weight:normal">b</b> c</strong>')
check(f"...and a tag that took its bold back closes no one else's ({_s})",
      _s == [{"start": 0, "end": 5, "style": "bold"}])
# The same reading serves colours and alignment, which met the same walls.
_t, _s, _p = html_to_note('<p style="TEXT-ALIGN: CENTER">x <span '
                          'style="color: #D32F2F !important">red</span></p>')
check(f"a colour marked !important and an alignment in capitals arrive "
      f"({_s}; {_p})",
      {"start": 2, "end": 5, "style": "text_color", "value": "#d32f2f"} in _s
      and {"line": 0, "align": "center"} in _p)

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

# A page's own theme is not emphasis. Pasting from a dark-mode source used
# to bring its near-white text and near-black background along, which is
# unreadable in a note and was never anybody's decision about the words.
# What survives is colour that is actually coloured.
CHROME = [
    ("dark-mode text", 'color:#e8e6f0'),
    ("a dark background", 'background-color:#1e1b2e'),
    ("black text", 'color:#111111'),
    ("a white background", 'background-color:#ffffff'),
    ("a grey code block", 'background-color:#3a3a4d'),
    ("a grey", 'color:#808080'),
    ("a dark red background, too dark to read through",
     'background-color:#4a0000'),
]
for label, css in CHROME:
    _t, _s, _p = html_to_note(f'<p><span style="{css}">x</span></p>')
    check(f"a page's own colouring is dropped: {label}",
          [s for s in _s if "value" in s] == [])

DELIBERATE = [
    ("a red warning", 'color:#e63946', "text_color", "#e63946"),
    ("a blue link", 'color:#3a86ff', "text_color", "#3a86ff"),
    ("a yellow highlight", 'background-color:#ffff00', "highlight", "#ffff00"),
    ("a pale green highlight", 'background-color:#c8f7c5', "highlight", "#c8f7c5"),
]
for label, css, style, value in DELIBERATE:
    _t, _s, _p = html_to_note(f'<p><span style="{css}">x</span></p>')
    check(f"a colour someone chose survives: {label}",
          [s for s in _s if "value" in s]
          == [{"start": 0, "end": 1, "style": style, "value": value}])

# The whole point, end to end: a dark page's list arrives as a list, with
# its words and its bold, and none of its theme.
_t, _s, _p = html_to_note(
    '<div style="background-color:#2b2b3d;color:#e8e6f0">'
    '<p style="color:#e8e6f0">Heading</p><ul>'
    '<li style="color:#e8e6f0">first with <b>bold</b> in it</li>'
    '<li><code style="background-color:#3a3a4d">code</code> here</li>'
    '</ul></div>')
check("pasting from a dark page keeps the structure and drops the theme",
      _p == [{"line": 1, "kind": "bullet"}, {"line": 2, "kind": "bullet"}]
      and [s for s in _s if "value" in s] == []
      and any(s["style"] == "bold" for s in _s))

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

# ---- A cap that cuts says so ----
# Past the caps the paste was cut without a word, and the rest of a long
# article was simply not in the note. The caller is told now, so it can say
# what was left out.
from noteorganizer.core.richtext import MAX_PASTE_CHARS, MAX_PASTE_SPANS


def _cut_report(markup):
    report = {"text_cut": None, "styles_cut": None}
    html_to_note(markup, report=report)
    return report


_NOTHING_CUT = {"text_cut": False, "styles_cut": False}
check("text past the character cap is reported as cut",
      _cut_report("<p>" + "x" * (MAX_PASTE_CHARS + 1) + "</p>")
      == {"text_cut": True, "styles_cut": False})
check("text exactly at the cap is not",
      _cut_report("<p>" + "x" * MAX_PASTE_CHARS + "</p>") == _NOTHING_CUT)
check("nor is a cap reached with only blank paragraphs after it",
      _cut_report("<p>" + "x" * MAX_PASTE_CHARS + "</p><p> </p><p></p>")
      == _NOTHING_CUT)
check("styles past the style cap are reported as cut",
      _cut_report("<p>x</p>" + "<p><b>x</b></p>" * (MAX_PASTE_SPANS + 1))
      == {"text_cut": False, "styles_cut": True})
check("styles exactly at the cap are not",
      _cut_report("<p>x</p>" + "<p><b>x</b></p>" * MAX_PASTE_SPANS)
      == _NOTHING_CUT)
check("a style still open when the text runs out is counted too",
      _cut_report("<p>x</p>" + "<p><b>x</b></p>" * MAX_PASTE_SPANS
                  + "<p><i>unclosed")["styles_cut"] is True)
check("a report on nothing at all says nothing was cut",
      _cut_report("") == _NOTHING_CUT and _cut_report(None) == _NOTHING_CUT)


# ---- Pasting without formatting must not leave a list behind ----
# A marker in the text is what makes a line a list line in this app, and
# plenty of sources write their own bullets into the plain text they offer.
# Pasting that verbatim produced exactly the formatting the user had asked
# to be left behind.
for label, before, after in [
    ("a bullet", BULLET + "milk", "milk"),
    ("a nested bullet", "  " + SUB_BULLET + "inner", "inner"),
    ("a third-level bullet", SUB_SUB + "deep", "deep"),
    ("a numbered item", "1. first", "first"),
    ("several lines", BULLET + "a\n" + BULLET + "b", "a\nb"),
]:
    check(f"paste-without-formatting drops {label}",
          NO.strip_list_markers(before) == after)

for label, line in [
    ("a dash, which was never a marker here", "- not an app marker"),
    ("an asterisk", "* also not"),
    ("ordinary words", "just words"),
    ("a bullet in the middle of a line", "see " + BULLET.strip() + " here"),
]:
    check(f"and leaves {label} alone", NO.strip_list_markers(line) == line)

# Known and accepted: any number followed by a dot and a space starts a
# numbered item in this app, so a year at the start of a line loses it.
# Stripping matches what the editor itself would do with that line -- a
# second, different rule would mean text that looks plain but comes back
# as a list the moment it is reopened.
check("a leading year is treated as a marker, matching how it is typed",
      NO.strip_list_markers("2026. was a year") == "was a year")


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

# A list changing kind at the same depth needs a list element of its own,
# not another item in the one already open. Writing it as another <li> put
# a numbered line inside a <ul>, so it came back as a bullet.
KIND_CHANGES = [
    ("bullets then numbers", BULLET + "milk\n1. collect",
     [{"line": 0, "kind": "bullet"}, {"line": 1, "kind": "number"}]),
    ("numbers then bullets", "1. one\n" + BULLET + "aside",
     [{"line": 0, "kind": "number"}, {"line": 1, "kind": "bullet"}]),
    ("alternating", BULLET + "a\n1. b\n" + BULLET + "c",
     [{"line": 0, "kind": "bullet"}, {"line": 1, "kind": "number"},
      {"line": 2, "kind": "bullet"}]),
    ("kind changing while nested", BULLET + "top\n1. sub\n" + BULLET + "back",
     [{"line": 0, "kind": "bullet"}, {"line": 1, "kind": "number", "indent": 1},
      {"line": 2, "kind": "bullet"}]),
]
for label, text, paras in KIND_CHANGES:
    markup = note_to_html(text, [], paras)
    back_text, _bs, back_paras = html_to_note(markup)
    check(f"a list changing kind starts a new list: {label}",
          back_text == text and back_paras == paras and valid(markup))

# Styles must survive the trip. Bold+italic went out as one span and came
# back as two, bold and italic -- which the note format allows, but as two
# Tk tags that both set the font they do not compose, and the text was
# drawn italic alone. It comes back as the one span it went out as.
markup = note_to_html("abc", [{"start": 0, "end": 3, "style": "bold_italic"}])
_t, _s, _p = html_to_note(markup)
check("bold_italic survives the trip as bold_italic over the same characters",
      [(s["style"], s["start"], s["end"]) for s in _s]
      == [("bold_italic", 0, 3)])

# --- reflow_wrapped: rejoining what a column broke --------------------------
# A PDF hands over its own line breaks. Keeping them gives narrow ragged text;
# dropping them all gives one run-on block. Each break is judged by whether the
# next line's first word would have fitted on the line before it.
#
# What is checked here is what the function actually promises, at every width
# rather than at the widths that happen to work: no word is ever lost or
# changed, no paragraph is ever split in two, and a document that indents its
# paragraphs is recovered exactly. Merging two paragraphs IS possible without
# indentation -- a paragraph whose last line lands nearly full cannot be told
# from a line the column broke -- and that limit is asserted rather than hidden.
import textwrap

PARAS = [
    "Lorem Ipsum is simply dummy text of the printing and typesetting "
    "industry. Lorem Ipsum has been the industry standard dummy text ever "
    "since 1966, when designers at Letraset and James Mosley took a 1914 "
    "Cicero translation and scrambled it to make dummy text.",
    "It is a long established fact that a reader will be distracted by the "
    "readable content of a page when looking at its layout. The point of "
    "using Lorem Ipsum is that it has a more-or-less normal distribution.",
    "Contrary to popular belief, Lorem Ipsum is not simply random text. It "
    "has roots in a piece of classical Latin literature from 45 BC, making "
    "it over 2000 years old.",
]
ORIGINAL = "\n".join(PARAS)
WIDTHS = (45, 52, 60, 70, 80, 95, 110, 130)


def _wrapped(width, indent=""):
    return "\n".join("\n".join(textwrap.wrap(p, width, initial_indent=indent))
                     for p in PARAS)


def _only_merges(out, paragraphs):
    """True if every output paragraph is whole original paragraphs joined.

    Merging is allowed and sometimes unavoidable; splitting one apart is the
    failure that would break a sentence in half, so it must never happen.
    """
    remaining = list(paragraphs)
    for line in out.split("\n"):
        taken = ""
        while remaining and taken != line:
            taken = (taken + " " + remaining.pop(0)).strip()
            if len(taken) > len(line):
                return False
        if taken != line:
            return False
    return not remaining


# The safety properties, at every width, indented or not.
for _w in WIDTHS:
    for _label, _indent in (("plain", ""), ("indented", "    ")):
        _out = reflow_wrapped(_wrapped(_w, _indent))
        check(f"{_label} text at {_w} columns keeps every word unchanged",
              _out.split() == ORIGINAL.split())
        check(f"{_label} text at {_w} columns never splits a paragraph in two",
              _only_merges(_out, PARAS))

# Where the document says where paragraphs start, there is nothing to guess.
for _w in WIDTHS:
    check(f"indented paragraphs are recovered exactly at {_w} columns",
          reflow_wrapped(_wrapped(_w, "    ")) == ORIGINAL)

# And where paragraph ends are unambiguous -- each ending well short of the
# column -- so is the plain case.
CLEAR = ["The first paragraph runs on for a while and then stops here.",
         "The second one also runs on for a while before it stops.",
         "The third is much the same, and then it ends."]
for _w in (52, 70, 95):
    _clear_wrapped = "\n".join("\n".join(textwrap.wrap(p, _w)) for p in CLEAR)
    check(f"unambiguous paragraphs are recovered exactly at {_w} columns",
          reflow_wrapped(_clear_wrapped) == "\n".join(CLEAR))

# --- what must be left alone ---
_address = "St. Mary's Road 12\nBlock A, Apt. 4\nCambridge"
check("an address keeps its own line breaks",
      reflow_wrapped(_address) == _address)

_poem = ("I wandered lonely as a cloud\nThat floats on high o'er vales and "
         "hills\nWhen all at once I saw a crowd")
check("short lines that were meant are kept", reflow_wrapped(_poem) == _poem)

_two = ("Lorem Ipsum is simply dummy text of the printing industry here\n"
        "and it continues on this second line of roughly equal length")
check("two lines are not enough evidence to join anything",
      reflow_wrapped(_two) == _two)

_list = ("\u2022 The first item, which runs on for quite a while and is long\n"
         "\u2022 The second item, also long enough to look like wrapped prose\n"
         "\u2022 And a third one, so there are enough lines to be a pattern")
check("a bullet list is never rejoined, however long its lines",
      reflow_wrapped(_list) == _list)

_numbered = ("1. The first item, which runs on for quite a while and is long\n"
             "2. The second item, also long enough to look like wrapped prose\n"
             "3. And a third one, so there are enough lines to be a pattern")
check("a numbered list is never rejoined either",
      reflow_wrapped(_numbered) == _numbered)

# --- blank lines, hyphens, and text that needs nothing done to it ---
_blocks = _wrapped(70, "    ") + "\n\n" + _wrapped(70, "    ")
check("a blank line still separates what it separated",
      reflow_wrapped(_blocks) == ORIGINAL + "\n\n" + ORIGINAL)

# A hyphen at the break is kept and the space dropped. "more-or-less" split as
# "more-" / "or-less" is the case that matters: removing the hyphen made it
# "moreor-less", which is not a word.
check("a hyphenated word broken across lines is not corrupted",
      "more-or-less" in reflow_wrapped(_wrapped(45)))

_dash_end = ("Everything below is quoted from the report, see page 12 -\n"
             "and the figures there disagree with the summary given above\n"
             "in three separate places, which nobody has yet explained.")
check("a trailing dash that is not part of a word keeps its space",
      "12 - and" in reflow_wrapped(_dash_end))

# A real PDF, justified, where a paragraph's line happens to fall a few
# characters short and the next word is small: "...at interdum magna augue" /
# "eget diam. Vestibulum..." was read as two paragraphs and numbered as two
# list items, splitting the sentence between them. A paragraph almost never
# stops mid-sentence, so a line ending in no punctuation at all is taken as
# the column's doing.
_PDF_LINES = [
    "Suspendisse in justo eu magna luctus suscipit. Sed lectus. Integer",
    "euismod lacus luctus magna. Quisque cursus, metus vitae pharetra",
    "auctor, sem massa mattis sem, at interdum magna augue",
    "eget diam. Vestibulum ante ipsum primis in faucibus orci luctus et",
    "ultrices posuere cubilia Curae; Morbi lacinia molestie dui.",
    "Morbi in dui quis est pulvinar ullamcorper. Nulla facilisi. Integer",
    "lacinia sollicitudin massa. Cras metus. Sed aliquet risus a tortor.",
]
_pdf_out = reflow_wrapped("\n".join(_PDF_LINES))
check(f"a sentence running past a short line is not split in two "
      f"({len(_pdf_out.splitlines())} paragraphs from {len(_PDF_LINES)} lines)",
      len(_pdf_out.splitlines()) == 2)
check("and the continuation stays with the sentence it belongs to",
      "magna augue eget diam." in _pdf_out)

# A heading still ends a paragraph, punctuation or not, because it falls well
# short of the column. Enough wrapped lines here for the block to be taken as
# a column in the first place -- an earlier version of this fixture was three
# lines long, was never recognised as wrapped, and so passed without testing
# anything at all.
_heading = ["Introduction",
            "The first paragraph of this section runs the full width of the",
            "column and carries on past the end of its first line without",
            "stopping, which is what makes the block read as a column here",
            "rather than as a handful of separate short lines of its own."]
_heading_out = reflow_wrapped("\n".join(_heading))
check(f"a short heading still starts its own paragraph "
      f"({_heading_out.splitlines()[0][:20]!r})",
      _heading_out.splitlines()[0] == "Introduction")
check("and the lines under it are joined into one",
      len(_heading_out.splitlines()) == 2)

check("already-joined paragraphs are returned untouched",
      reflow_wrapped(ORIGINAL) == ORIGINAL)
check("empty text is handled", reflow_wrapped("") == "")
check("None is handled", reflow_wrapped(None) == "")




_doc = html_document("Note <of mine>", "<div>the body</div>")
check("the HTML document declares its doctype and charset",
      _doc.startswith("<!DOCTYPE html>") and "utf-8" in _doc)
check("the title is escaped, not injected",
      "&lt;of mine&gt;" in _doc and "<of mine>" not in _doc)
check("the title is a styled div, not a heading Word would fold away",
      "<h1" not in _doc and "font-weight: bold" in _doc)
check("the fragment lands inside the body",
      "<div>the body</div>" in _doc)
check("table borders exist in the styling, or a table reads as loose words",
      "border" in _doc)

# A highlight covering a whole cell lands on the <td> itself -- an empty
# highlighted cell's colour would otherwise ride pad spaces that HTML
# collapses into nothing.
_hl_body = "| full | empty |" + chr(10) + "| --- | --- |" + chr(10) + "| aa | bb |"
_hl_row = _hl_body.index("| aa | bb |")
_hl_spans = [{"start": _hl_row + 5, "end": _hl_row + 10, "style": "highlight",
              "value": "#c8f7c5"}]
_hl_html = note_to_html(_hl_body, _hl_spans, [])
check("a full-cell highlight colours the td itself",
      'td style="background-color:#c8f7c5;"' in _hl_html
      or 'td style="background-color:#c8f7c5;"'.replace("td ", "td  ") in _hl_html)
_part_spans = [{"start": _hl_row + 7, "end": _hl_row + 8, "style": "highlight",
                "value": "#c8f7c5"}]
_part_html = note_to_html(_hl_body, _part_spans, [])
check("a partial highlight stays a span inside the cell",
      "background-color" in _part_html
      and 'td style="background-color' not in _part_html)

# The first row is the header the app draws bold -- exported as <th>
# so Word and the browsers bold it too; data rows stay <td>. Browsers
# centre th by default, so the stylesheet pins it back to the left.
_th_html = note_to_html(_hl_body, [], [])
check("the header row exports as th and data rows as td",
      "<th>full</th>" in _th_html and "<td>aa</td>" in _th_html
      and "<td>full</td>" not in _th_html)
_th_doc = html_document("T", "<div>x</div>")
check("the document CSS keeps th left-aligned and bordered",
      "th { text-align: left; }" in _th_doc
      and "th, td { border" in _th_doc)

# A multi-line cell stores its breaks as the literal <br> marker; left
# to escaping alone they arrived as visible "&lt;br&gt;" text in the page.
_br_body = ("| one<br>two | three |" + chr(10) + "| --- | --- |" + chr(10)
            + "| a | b |")
_br_html = note_to_html(_br_body, [], [])
check("a cell's <br> markers become real line breaks",
      "one<br>two" in _br_html and "&lt;br&gt;" not in _br_html)

# The table's place on the page rides its lines' alignment entries.
_pl_body = "| A | B |" + chr(10) + "| --- | --- |" + chr(10) + "| a | b |"
_pl_paras = [{"line": 0, "align": "center"}, {"line": 1, "align": "center"},
             {"line": 2, "align": "center"}]
_pl_html = note_to_html(_pl_body, [], _pl_paras)
check("a centred table centres in browsers AND in Word",
      'align="center"' in _pl_html and "margin:0.5em auto;" in _pl_html)
_pr_paras = [{"line": 0, "align": "right"}, {"line": 1, "align": "right"},
             {"line": 2, "align": "right"}]
_pr_html = note_to_html(_pl_body, [], _pr_paras)
check("a right-placed table pushes right in Word without floating in browsers",
      'align="right"' in _pr_html and "float:none" in _pr_html
      and "margin:0.5em 0 0.5em auto;" in _pr_html)
check("an unplaced table carries no margin style",
      "<table>" in note_to_html(_pl_body, [], []))

_doc2 = html_document("T", "<div>x</div>")
check("printing keeps background colours (PDF road)",
      "print-color-adjust: exact" in _doc2)
check("a wide table wraps instead of running off the page",
      "max-width: 100%" in _doc2 and "overflow-wrap" in _doc2)

# ---- Inline styles CLOSE with their tag (audit Z04-F00/F01) ----
# A colour on <p>/<div>/<li>/<td> used to bleed to the end of the
# document (block and cell end tags never closed style spans), and a
# span opening two styles closed only the first.
_t, _s, _p = html_to_note('<p style="color:#ff0000">red</p><p>black</p>')
_reds = [s for s in _s if s["style"] == "text_color"]
check("a coloured paragraph's colour stops at its own end tag",
      len(_reds) == 1 and _t[_reds[0]["start"]:_reds[0]["end"]] == "red"
      and "black" not in _t[_reds[0]["start"]:_reds[0]["end"]])

# A pale yellow: the highlight-legibility filter (deliberate) rejects
# saturated-dark fills like pure green, and would hide this bug.
_t, _s, _p = html_to_note(
    '<span style="color:#ff0000;background:#ffff99">x</span>y')
_cov = {(s["style"], _t[s["start"]:s["end"]]) for s in _s
        if s["style"] in ("text_color", "highlight")}
check("a span opening two styles closes BOTH at its end tag",
      _cov == {("text_color", "x"), ("highlight", "x")})

_t, _s, _p = html_to_note('a<br style="color:#ff0000">bcd<p>efg</p>')
check("a styled VOID tag opens no span at all (no end tag ever comes)",
      not any(s["style"] == "text_color" for s in _s))

# ---- A <br> inside a cell survives the round-trip (audit Z04-F02) ----
from noteorganizer.core import tables as _tbl
_t, _s, _p = html_to_note("<table><tr><td>a<br>b</td><td>c</td></tr></table>")
check("a cell's line break arrives as the cell break marker, not a space",
      _tbl.LINE_BREAK in _t and "a" + _tbl.LINE_BREAK + "b"
      in _t.replace(" ", ""))

# ---- One answer to "is this Tk tag character formatting?" ----
# The table rewrite carries these tags cell by cell and the undo journal
# clears and re-lays them; both ask this one function, so a new kind of
# format tag cannot be carried by one and dropped by the other.
from noteorganizer.core.formatting import (is_format_tag, font_tag_for,
                                           color_tag_name)
check("the plain styles are format tags",
      all(is_format_tag(t) for t in
          ("bold", "italic", "bold_italic", "underline", "strike")))
check("a colour tag with a real hex is a format tag",
      is_format_tag(color_tag_name("text_color", "#E63946"))
      and is_format_tag(color_tag_name("highlight", "#ffe066")))
check("a composite font tag is a format tag",
      is_format_tag(font_tag_for(True, False, 14, "Georgia")))
check("paragraph, table and selection tags are not",
      not any(is_format_tag(t) for t in
              ("para_bullet_1", "align_center", "table_hidden", "sel",
               "text_color_nothex", "highlight_", "font_Nope_99_10",
               None, 5)))

# ---- Where a composite font tag goes, worked out in one sweep ----
# resolve_font_runs checked every span at every span boundary: one font
# size in a note of 8,000 styled words cost 1.7 s at every open, every
# Enter in a numbered list and every font change. The sweep must give the
# very runs the old way gave -- this is the old way, kept as the oracle.
import random as _random
import sys as _sys
from noteorganizer.core.formatting import (resolve_font_runs,
                                           normalize_formatting, merge_spans,
                                           FONT_FAMILIES, FONT_SIZES,
                                           FONT_VALUE_STYLES)


def _runs_checked_one_by_one(spans, text_length):
    spans = normalize_formatting(spans)
    affects = {"bold", "italic", "bold_italic"} | FONT_VALUE_STYLES
    relevant = [s for s in spans if s["style"] in affects]
    if not any(s["style"] in FONT_VALUE_STYLES for s in relevant):
        return []
    marks = {0, text_length}
    for s in relevant:
        marks.update((s["start"], s["end"]))
    points = sorted(m for m in marks if 0 <= m <= text_length)
    runs = []
    for a, z in zip(points, points[1:]):
        bold = italic = False
        size = family = None
        for s in relevant:
            if s["start"] > a or s["end"] < z:
                continue
            if s["style"] == "bold":
                bold = True
            elif s["style"] == "italic":
                italic = True
            elif s["style"] == "bold_italic":
                bold = italic = True
            elif s["style"] == "font_size":
                size = s["value"]
            else:
                family = s["value"]
        if size is not None or family is not None:
            runs.append((a, z, bold, italic, size, family))
    merged = []
    for run in runs:
        if merged and merged[-1][1] == run[0] and merged[-1][2:] == run[2:]:
            merged[-1] = (merged[-1][0], run[1]) + run[2:]
        else:
            merged.append(run)
    return merged


def _random_spans(rng, length):
    spans = []
    for _ in range(rng.randint(0, 14)):
        a = rng.randint(0, length + 3)
        z = a + rng.randint(1, 12)
        style = rng.choice(("bold", "italic", "bold_italic", "underline",
                            "font_size", "font_family", "font_size"))
        span = {"start": a, "end": z, "style": style}
        if style == "font_size":
            span["value"] = rng.choice(FONT_SIZES)
        elif style == "font_family":
            span["value"] = rng.choice(FONT_FAMILIES)
        spans.append(span)
    return spans


_rng = _random.Random(20261002)
_differ = []
for _case in range(4000):
    _len = _rng.randint(0, 30)
    _sp = _random_spans(_rng, _len)
    if resolve_font_runs(_sp, _len) != _runs_checked_one_by_one(_sp, _len):
        _differ.append((_sp, _len))
check(f"the sweep gives the runs every span checked in turn gave, on 4,000 "
      f"random notes -- overlapping sizes and families, bold_italic, spans "
      f"past the end ({len(_differ)} differ)", not _differ)


def _lines_run_in(fn, *args):
    """How many lines of *fn* itself ran: the work it does, counted rather
    than timed, so a slow machine cannot fail it and a fast one cannot
    hide a loop inside a loop."""
    ran = [0]

    def inside(frame, event, arg):
        if event == "line":
            ran[0] += 1
        return inside

    def calls(frame, event, arg):
        return inside if frame.f_code is fn.__code__ else None

    _sys.settrace(calls)
    try:
        fn(*args)
    finally:
        _sys.settrace(None)
    return ran[0]


# Bold and italic over the same letters are one bold_italic span: as two Tk
# tags that both set the font they do not compose, and italic won -- bold
# italic pasted from a web page or the app's own copy was drawn italic.
def _styles(spans):
    return sorted((s["start"], s["end"], s["style"])
                  for s in normalize_formatting(spans))


check("overlapping bold and italic become bold, bold_italic and italic",
      _styles([{"start": 0, "end": 5, "style": "bold"},
               {"start": 3, "end": 8, "style": "italic"}])
      == [(0, 3, "bold"), (3, 5, "bold_italic"), (5, 8, "italic")])
_apart = [{"start": 0, "end": 3, "style": "bold"},
          {"start": 5, "end": 8, "style": "italic"},
          {"start": 1, "end": 2, "style": "underline"}]
check("bold and italic that do not overlap are left exactly as they were",
      normalize_formatting(_apart) == _apart)
# ...and a list the fold changed comes back in the order the editor reads
# spans back in: with the folded pieces put after the rest, a note saved the
# old way read as unsaved the moment it was opened, and was saved again on
# leaving with no edit made.
_old_way = [{"start": 4, "end": 7, "style": "bold"},
            {"start": 4, "end": 7, "style": "italic"},
            {"start": 8, "end": 13, "style": "underline"}]
check("a list the fold changed is in the order the editor reads spans back in",
      normalize_formatting(_old_way)
      == merge_spans(normalize_formatting(_old_way))
      == [{"start": 4, "end": 7, "style": "bold_italic"},
          {"start": 8, "end": 13, "style": "underline"}])

_n = 600
_many = [{"start": 3 * i, "end": 3 * i + 2,
          "style": ("bold", "italic")[i % 2]} for i in range(_n)]
_many.append({"start": 0, "end": 3 * _n, "style": "font_size", "value": 20})
_lines = _lines_run_in(resolve_font_runs, _many, 3 * _n)
# About 46 lines a word now; checking every span at every boundary ran
# about 3,600 a word (2.2 million in all), measured.
check(f"working out the runs of {_n} styled words and one size takes work in "
      f"step with the words, not with their square ({_lines} lines ran)",
      _lines <= 120 * _n)

# Copying a long note with many styled words froze the app (field pass): the
# HTML asked every character about every span of the whole note. The sweep
# asks only where a span starts or ends, and only that line's spans -- and
# must write exactly what asking every character wrote.
from noteorganizer.core import richtext as _rt


def _line_html_char_by_char(line, spans, offset):
    if not line:
        return ""
    pieces, run_start = [], 0
    current = _rt._styles_at(spans, offset)
    for i in range(1, len(line) + 1):
        here = _rt._styles_at(spans, offset + i) if i < len(line) else None
        if here != current:
            pieces.append(_rt._wrap(line[run_start:i], *current))
            run_start, current = i, here
    return "".join(pieces)


_sw_rng = _random.Random(20261006)
_sw_differ = []
for _case in range(3000):
    _sw_text = "".join(_sw_rng.choice("ab \n") for _ in range(_sw_rng.randint(0, 40)))
    _sw_spans = []
    for _ in range(_sw_rng.randint(0, 10)):
        _a = _sw_rng.randint(0, len(_sw_text) + 2)
        _style = _sw_rng.choice(("bold", "italic", "underline", "text_color",
                                 "highlight", "font_size"))
        _sp = {"start": _a, "end": _a + _sw_rng.randint(1, 15), "style": _style}
        if _style in ("text_color", "highlight"):
            _sp["value"] = _sw_rng.choice(("#d32f2f", "#c8f7c5"))
        elif _style == "font_size":
            _sp["value"] = 20
        _sw_spans.append(_sp)
    _norm = normalize_formatting(_sw_spans)
    _off = 0
    for _ln in _sw_text.split("\n"):
        if _rt._line_html(_ln, _norm, _off) != _line_html_char_by_char(_ln, _norm, _off):
            _sw_differ.append((_sw_text, _sw_spans))
            break
        _off += len(_ln) + 1
check(f"the sweep writes the HTML asking every character wrote, on 3,000 "
      f"random notes ({len(_sw_differ)} differ)", not _sw_differ)

_sw_work = [0]
_sw_real = _rt._styles_at


def _sw_counting(spans, index):
    _sw_work[0] += len(spans) + 1
    return _sw_real(spans, index)


_rt._styles_at = _sw_counting
try:
    _sw_lines = ["plain words then a styled one here %d" % i for i in range(2000)]
    _sw_body = chr(10).join(_sw_lines)
    _sw_bold, _at = [], 0
    for _ln in _sw_lines:
        _k = _ln.index("styled")
        _sw_bold.append({"start": _at + _k, "end": _at + _k + 6, "style": "bold"})
        _at += len(_ln) + 1
    note_to_html(_sw_body, _sw_bold, [])
finally:
    _rt._styles_at = _sw_real
# Asked at every character against every span this was about 160 million;
# measured as work, so neither a slow machine nor a fast one decides it.
check(f"copying 2,000 lines with a bold word each asks in step with the "
      f"styles, not with characters times styles ({_sw_work[0]} asked)",
      _sw_work[0] <= 20 * len(_sw_bold))

# An EMPTY highlighted cell: its colour rides the padding between its pipes,
# and the td wears it -- it used to leave without any colour at all.
_eh_body = "| h1 | h2 |" + chr(10) + "| --- | --- |" + chr(10) + "| aa |    |"
_eh_row = _eh_body.index("| aa |")
_eh_html = note_to_html(_eh_body, [{"start": _eh_row + 6, "end": _eh_row + 10,
                                    "style": "highlight", "value": "#c8f7c5"}],
                        [])
check(f"an empty highlighted cell colours its td ({_eh_html})",
      'background-color:#c8f7c5;' in _eh_html)
# Size and typeface leave for Word, and a typeface's name cannot break out
# of the attribute it sits in.
_fz_html = note_to_html("big word", [
    {"start": 0, "end": 3, "style": "font_size", "value": 20},
    {"start": 4, "end": 8, "style": "font_family", "value": "Georgia"}], [])
check(f"a size and a typeface reach the HTML ({_fz_html})",
      'font-size:20pt;' in _fz_html and "font-family:'Georgia';" in _fz_html)
# A note's own spans are normalised to the known typefaces first; a cell
# copy's come straight off the editor's tags, so the guard is met there.
from noteorganizer.core.richtext import cell_html
_fq_html = cell_html("x", [{"start": 0, "end": 1, "style": "font_family",
                            "value": 'Evil"><b>'}])
check(f"a typeface name cannot break out of its attribute ({_fq_html})",
      '"><b>' not in _fq_html and "font-family:'Evilb';" in _fq_html)
# What our own cell copy writes is the export's own cell markup.
check("cell_html styles a cell's words and keeps its line breaks",
      cell_html("ab" + _tbl.LINE_BREAK + "cd",
                [{"start": 0, "end": 2, "style": "bold"}])
      == "<b>ab</b><br>cd")

# ------------------------------------------- the emoji variation selector --
# Tk draws U+FE0F as a blank two letters wide after the emoji it follows:
# the picker's heart, sun and warning sign left a gap in every note they
# went into. No string the app draws may carry it; a day's marker kept
# from before loses it on the way in.
import glob as _glob
import io as _io
import os as _os
from noteorganizer.core.formatting import without_variation_selector

check("the variation selector comes off, and nothing else",
      without_variation_selector("❤\ufe0f love ☀\ufe0f")
      == "❤ love ☀"
      and without_variation_selector("plain") == "plain"
      and without_variation_selector(None) == "")
_here = _os.path.dirname(_os.path.abspath(__file__))
_carriers = [
    _os.path.relpath(path, _here)
    for path in [_os.path.join(_here, "note_organizer.py")]
    + _glob.glob(_os.path.join(_here, "noteorganizer", "**", "*.py"),
                 recursive=True)
    if "\ufe0f" in _io.open(path, encoding="utf-8").read()]
check(f"no source file of the app carries the variation selector "
      f"({_carriers})", not _carriers)
check("a day's markers come in without it, three at most, and a single "
      "marker from an older file becomes a list",
      NO.NoteOrganizer._clean_day_markers(
          ["❤\ufe0f", "", "⭐", "✈\ufe0f", "\U0001f697"])
      == ["❤", "⭐", "✈"]
      and NO.NoteOrganizer._clean_day_markers("☀\ufe0f") == ["☀"]
      and NO.NoteOrganizer._clean_day_markers({"x": 1}) == []
      and NO.NoteOrganizer._clean_day_markers(["\ufe0f"]) == [])

# ---- A deletion that reaches a list (list_deletion_range) ----
# The editor deleted characters, and a marker is characters: a join kept the
# second line's marker among the words ("2. two3. three"), typing over whole
# items swallowed the next one's ("x4. four"), a marker half-deleted stayed
# half there. Each answer applied to the text and renumbered, as the editor
# does with it.
from noteorganizer.core.formatting import (list_deletion_range as _ldr,
                                           parse_list_marker, renumber)


def _ld_apply(body, start, end, typed=""):
    lines = body.split("\n")
    plan = _ldr(lines, start, end, typing=bool(typed))
    (l1, c1), (l2, c2) = plan if plan else (start, end)
    out = "\n".join(lines[:l1] + [lines[l1][:c1] + typed + lines[l2][c2:]]
                    + lines[l2 + 1:])
    paras = [{"line": i, "kind": parse_list_marker(line)[0]}
             for i, line in enumerate(out.split("\n"))
             if parse_list_marker(line)[0]]
    return renumber(out, paras)[0]


_LD = "1. one\n2. two\n3. three\n4. four"
for _ld_name, _ld_args, _ld_want in (
        ("items 2 and 3 deleted whole", (_LD, (1, 0), (3, 0)), "1. one\n2. four"),
        ("a letter typed over items 2 and 3", (_LD, (1, 0), (3, 0), "x"),
         "1. one\n2. x\n3. four"),
        ("a letter typed over item 2 alone", (_LD, (1, 0), (2, 0), "x"),
         "1. one\n2. x\n3. three\n4. four"),
        ("BackSpace at item 3's very start", (_LD, (1, 6), (2, 0)),
         "1. one\n2. twothree\n3. four"),
        ("item 2's marker selected", (_LD, (1, 0), (1, 3)),
         "1. one\ntwo\n1. three\n2. four"),
        ("one character inside a marker", (_LD, (1, 0), (1, 1)),
         "1. one\ntwo\n1. three\n2. four"),
        ("from item 2's words into item 3's", (_LD, (1, 4), (2, 5)),
         "1. one\n2. tree\n3. four"),
        ("from just after item 2's marker into item 3's words", (_LD, (1, 3), (2, 5)),
         "1. one\n2. ree\n3. four"),
        ("from item 2's words to item 4's start", (_LD, (1, 4), (3, 0)),
         "1. one\n2. tfour"),
        ("typed over from item 2's words to item 4's start", (_LD, (1, 4), (3, 0), "x"),
         "1. one\n2. txfour"),
        ("an empty item joined from below", ("1. one\n2. \n3. three", (1, 3), (2, 0)),
         "1. one\n2. three"),
        ("an empty line above an item", ("intro\n\n1. one\n2. two", (1, 0), (2, 0)),
         "intro\n1. one\n2. two"),
        ("words typed over a line up to an item", ("plain words\n1. one", (0, 0), (1, 0), "x"),
         "x\n1. one"),
        ("everything selected from the first line's start", (_LD, (0, 0), (3, 7)), ""),
        ("bullets joined", ("• a\n• b\n• c", (0, 3), (1, 0)), "• ab\n• c")):
    _ld_got = _ld_apply(*_ld_args)
    check(f"list deletion: {_ld_name} ({_ld_got!r})", _ld_got == _ld_want)
check("a deletion that reaches no list is left alone, as is one inside an "
      "item's words",
      _ldr(["plain words", "more words"], (0, 2), (1, 2)) is None
      and _ldr(["1. one", "2. two"], (1, 4), (1, 5)) is None)

# ---- A table copied from Excel (clipboard.fragment_of) ----
# Excel puts the CF_HTML markers inside the table: around one row's cells
# (the owner's copy of a test-plan row, 2026-10-25, its paths left out), or
# around rows. Cut out alone, the cells had no row and pasted as loose text.
from noteorganizer.core import clipboard as _clip
_XL_HEAD = (
    "Version:1.0\r\nStartHTML:0000000190\r\nEndHTML:0000002768\r\n"
    "StartFragment:0000002498\r\nEndFragment:0000002708\r\n\r\n"
    '<html xmlns:x="urn:schemas-microsoft-com:office:excel">\r\n<head>\r\n'
    "<meta name=ProgId content=Excel.Sheet>\r\n<!--[if !mso]>\r\n<style>\r\n"
    "v\\:* {behavior:url(#default#VML);}\r\n</style>\r\n<![endif]-->\r\n"
    '<style>\r\n<!--table\r\n\t{mso-displayed-decimal-separator:"\\.";}\r\n'
    ".xl66\r\n\t{font-weight:700;}\r\n-->\r\n</style>\r\n</head>\r\n\r\n"
    "<body link=blue vlink=purple>\r\n\r\n"
    "<table border=0 cellpadding=0 cellspacing=0 width=308 style='border-collapse:\r\n"
    " collapse;width:231pt'>\r\n <col width=73 style='width:55pt'>\r\n"
    " <col width=235 style='width:176pt'>\r\n")
_XL_TAIL = "\r\n</table>\r\n\r\n</body>\r\n\r\n</html>"
_xl_row = (_XL_HEAD + " <tr height=140 style='height:105.0pt'>\r\n<!--StartFragment-->\r\n"
           "  <td height=140 class=xl66 align=left width=73 style='height:105.0pt;\r\n"
           "  width:55pt'>High</td>\r\n  <td class=xl65 align=left width=235 "
           "style='border-left:none;width:176pt'>The\r\n  app open on the phone.</td>\r\n"
           "<!--EndFragment-->\r\n </tr>" + _XL_TAIL)
_xl_frag = _clip.fragment_of(_xl_row)
_xl_text = html_to_note(_xl_frag)[0]
check(f"a row copied from Excel comes back inside its row and table ({_xl_frag[:11]!r})",
      _xl_frag.startswith("<table><tr>") and _xl_frag.endswith("</tr></table>"))
check(f"...and reads as one table row, its words whole ({_xl_text!r})",
      _tbl.find_blocks(_xl_text) == [(0, 0)]
      and _tbl.split_row(_xl_text) == ["High", "The app open on the phone."])
_xl_rows = (_XL_HEAD + "<!--StartFragment-->\r\n <tr>\r\n  <td>What</td>\r\n  <td>How much</td>\r\n"
            " </tr>\r\n <tr>\r\n  <td>rent</td>\r\n  <td align=right>1500</td>\r\n </tr>\r\n"
            "<!--EndFragment-->" + _XL_TAIL)
_xl_frag = _clip.fragment_of(_xl_rows)
_xl_text = html_to_note(_xl_frag)[0]
check(f"rows copied without their table come back inside it ({_xl_text!r})",
      _xl_frag.startswith("<table>") and "<tr>" not in _xl_frag[:7]
      and _tbl.find_blocks(_xl_text) == [(0, 1)])
_own_frag = '<p><b>x</b> y</p><table><tr><td>a</td><td>b</td></tr></table>'
check("our own copy's fragment comes back exactly as it was written",
      _clip.fragment_of(_clip._wrap_html(_own_frag).decode("utf-8")) == _own_frag)
check("a browser's copy, its table inside the markers, comes back as it was",
      _clip.fragment_of("<html><body>\r\n<!--StartFragment--><table><tr><td>a</td>"
                        "<td>b</td></tr></table><!--EndFragment-->\r\n</body></html>")
      == "<table><tr><td>a</td><td>b</td></tr></table>")
check("rows and cells left open, as HTML allows, end where the next begins",
      _clip.fragment_of("<html><body><table><tr><td>a<td>b<tr><!--StartFragment-->"
                        "<td>c</td><!--EndFragment--></table></body></html>")
      == "<table><tr><td>c</td></tr></table>")
check("a document without markers still gives its body",
      _clip.fragment_of("<html><body><p>x</p></body></html>") == "<p>x</p></body></html>")

# ---- A row of one cell is no table here: its words come alone ----
check("one cell copied as a table pastes as its words",
      html_to_note("<table><tr><td>rent</td></tr></table>")[0] == "rent")
check("one column pastes as its words, one cell a line, an empty one empty",
      html_to_note("<table><tr><td>rent</td></tr><tr><td></td></tr>"
                   "<tr><td>food</td></tr></table>")[0] == "rent\n\nfood")
_t, _s, _p = html_to_note('<table><tr><td> <span style="color:#ff0000">rent</span>'
                          ' due</td></tr></table>')
check(f"a lone cell's colour stays on its words ({_t!r}, {_s})",
      _t == "rent due" and any(s["style"] == "text_color" and s["start"] == 0
                               and s["end"] == 4 for s in _s))
_t, _s, _p = html_to_note('<table><tr><td>a<br>b</td></tr><tr><td>c</td></tr></table>'
                          '<p style="text-align:center">d</p>')
check(f"a lone cell's line breaks are lines, and what follows keeps its line ({_t!r}, {_p})",
      _t == "a\nb\nc\nd" and {"line": 3, "align": "center"} in _p)
check("a table of two columns keeps its frame",
      html_to_note("<table><tr><td>a</td><td>b</td></tr></table>")[0].startswith("| a"))
# Chrome puts a non-breaking space at each edge of a bold word or a link; in
# a note it is a space, or a search for the words either side finds nothing.
_t, _s, _p = html_to_note("<p>The&nbsp;<b>Burj Khalifa</b>&nbsp;is tall, a&nbsp;&nbsp;b</p>")
check(f"a page's non-breaking spaces come in as spaces, as many as there were ({_t!r})",
      _t == "The Burj Khalifa is tall, a  b"
      and {"start": 4, "end": 16, "style": "bold"} in _s)
# Every span and line moved past every cut, walked one by one, froze a long
# styled column for tens of seconds inside the paste caps; halved, a few
# hundredths. The bound is wide on purpose: two seconds against fifteen.
import time as _time
from noteorganizer.core.richtext import _unframe_lone_cells
_uc_rows, _uc_at, _uc_text = [], 0, []
for _i in range(20_000):
    _uc_row = "| r%d |" % _i
    _uc_rows.append((_uc_at, _uc_at + len(_uc_row)))
    _uc_text.append(_uc_row + "\n")
    _uc_at += len(_uc_row) + 1
_uc_started = _time.perf_counter()
_uc_out, _uc_moved, _uc_line = _unframe_lone_cells("".join(_uc_text), _uc_rows)
_uc_last = [_uc_moved(_uc_rows[-1 - _i][0] + 2) for _i in range(2_000)][0]
_uc_took = _time.perf_counter() - _uc_started
check(f"a column of 20,000 lone cells comes out whole, its offsets moved "
      f"by halving ({_uc_took:.2f} s)",
      _uc_out.endswith("r19999\n") and _uc_out[_uc_last:].startswith("r19999")
      and _uc_took < 2.0)
# Misnested markup: 20,000 bolds, 20,000 italics, then the bolds closed --
# each close searched one shared list behind every open italic. 195 KB took
# 8.9 s on Linux; the bound is wide on purpose, as above.
from noteorganizer.core.richtext import html_to_note as _mn_read
_mn_html = "Hello " + "<b>" * 20_000 + "<i>" * 20_000 + "world" + "</b>" * 20_000
_mn_started = _time.perf_counter()
_mn_text, _mn_spans, _mn_paras = _mn_read(_mn_html)
_mn_took = _time.perf_counter() - _mn_started
check(f"misnested markup is read in one pass ({_mn_took:.2f} s), its text whole",
      _mn_text == "Hello world" and _mn_took < 2.0)

print()
print(f"FAILURES: {fails if fails else 'none'}")

import sys
sys.exit(1 if fails else 0)
