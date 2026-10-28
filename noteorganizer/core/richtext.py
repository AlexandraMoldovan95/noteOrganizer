"""Turning HTML into a note, and a note back into HTML.

WHAT THIS MODULE IS FOR
-----------------------
Pasting from a browser or a word processor, and copying a note back out
so it arrives somewhere else still formatted.

It is pure text work: no clipboard, no widgets, no Windows. The clipboard
itself is :mod:`noteorganizer.core.clipboard`, which is where the
platform-specific part lives. Keeping the conversion separate means it can
be tested with strings on any machine, which matters here more than usual
-- the app runs on Windows and the tests run on Linux.

THE MAPPING IS DELIBERATELY LOSSY
---------------------------------
HTML can express unlimited styling. A note can express bold, italic,
underline, strikethrough, two colours, a font, lists, alignment and
indentation. Everything else is dropped rather than approximated, the same
choice :func:`~noteorganizer.core.formatting.normalize_formatting` makes
about malformed spans: guessing what a `<blockquote>` or a CSS class was
meant to become would produce notes nobody asked for.

Font size and family are dropped on the way *in* for a related reason.
The app offers eight families and eight sizes; a web page uses neither, so
matching would mean picking a nearest value and silently claiming the note
is set in something it never was.

WHY LIST MARKERS ARE WRITTEN INTO THE TEXT
------------------------------------------
Because that is how this app stores them -- see ``formatting.py``. An
``<li>`` becomes a line beginning ``"• "`` and a ``paragraphs`` entry
saying so, which is exactly what the editor would have produced had the
list been typed by hand.
"""

import bisect
import re
from html import escape
from html.parser import HTMLParser

from . import tables
from .formatting import (
    BULLET_GLYPHS,
    MAX_INDENT,
    marker_for,
    normalize_formatting,
    normalize_paragraphs,
    parse_list_marker,
    shift_spans,
)

# A pasted web page can carry a great deal of markup. These are not tuning
# knobs so much as a refusal to let one paste produce a note nobody can
# edit -- the same reasoning as the title cap.
MAX_PASTE_CHARS = 100_000
# How much of a pasted page html_to_note reads before asking whether the
# ceiling has been passed: small beside a page, large beside a parser call.
_FEED_PIECE = 65_536
MAX_PASTE_SPANS = 2_000

# Tags that mean "a new line starts here".
# Tags HTML defines as having no end tag. Style spans must never open on
# one — with no close coming, they'd bleed to the end of the document.
_VOID_TAGS = {"br", "hr", "img", "input", "area", "base", "col", "embed",
              "source", "track", "wbr", "meta", "link"}

_BLOCK_TAGS = {"p", "div", "br", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
               "blockquote", "pre", "section", "article"}

# A cell is not a block tag: a cell does not start a line, the row does. Its
# text is wrapped in the pipes that make it a cell, opened at the start of
# each cell and closed once at the end of the row, which puts exactly one
# pipe between neighbours and one at either end -- "| A | B |".
_CELL_TAGS = {"td", "th"}

# Inline tags this app has a style for. Anything else is dropped.
_STYLE_TAGS = {
    "b": "bold", "strong": "bold",
    "i": "italic", "em": "italic",
    "u": "underline", "ins": "underline",
    "s": "strike", "strike": "strike", "del": "strike",
}

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGB = re.compile(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def _as_hex(value):
    """A CSS colour as ``#rrggbb``, or None if it is not one we can use."""
    if not value:
        return None
    value = value.strip().lower()
    if _HEX.match(value):
        if len(value) == 4:            # #abc -> #aabbcc
            return "#" + "".join(c * 2 for c in value[1:])
        return value
    match = _RGB.match(value)
    if match:
        parts = [int(p) for p in match.groups()]
        if all(0 <= p <= 255 for p in parts):
            return "#%02x%02x%02x" % tuple(parts)
    return None


# Below this, a colour is near enough to grey that it is almost certainly
# the page's own theme rather than a decision anyone made about the words.
# The app's own text-colour palette runs from 17 up to 247, so this does
# cut across the bottom of it -- but a grey chosen from a picker and a grey
# arriving from a stylesheet are different things, and only one of them was
# meant.
_MIN_SATURATION = 40

# A highlighter is pale by definition. The app's own highlight palette sits
# between 220 and 239, and a dark page background is nowhere near it.
_MIN_HIGHLIGHT_LIGHTNESS = 200


def _channels(hex_colour):
    return [int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)]


def _is_meaningful(hex_colour, kind):
    """Whether a colour says something about the words, or about the page.

    Pasting from a dark-mode page used to bring its theme along: near-white
    text on a near-black highlight, which is unreadable in a note and was
    never anybody's idea of emphasis. What survives is colour that is
    actually coloured -- a red warning, a yellow highlight -- and, for a
    highlight, only if it is pale enough to read black text through.
    """
    red, green, blue = _channels(hex_colour)
    if max(red, green, blue) - min(red, green, blue) < _MIN_SATURATION:
        return False
    if kind == "highlight":
        lightness = 0.299 * red + 0.587 * green + 0.114 * blue
        return lightness >= _MIN_HIGHLIGHT_LIGHTNESS
    return True


def _css(style_attr):
    """A style attribute as a dict, names and values lowercased, without
    failing on junk. "!important" is how a page insists, not part of the
    value: "700 !important" or "#D32F2F !important" read as nothing."""
    out = {}
    for chunk in (style_attr or "").split(";"):
        if ":" not in chunk:
            continue
        name, _, value = chunk.partition(":")
        value = value.strip().lower()
        if value.endswith("!important"):
            value = value[:-len("!important")].strip()
        out[name.strip().lower()] = value
    return out


def _weight_is_bold(value):
    """Whether a CSS font-weight is bold: the words, or a number from 600 --
    semibold, which pages use for bold more often than 700."""
    if value in ("bold", "bolder"):
        return True
    try:
        return float(value) >= 600
    except ValueError:
        return False


def _bold_and_italic(style):
    """``(bold, italic)`` as a parsed style says them: True or False where
    it says, None where it says nothing. The ``font`` shorthand counts too,
    and resets both as CSS does; the longhands win over it."""
    bold = italic = None
    font = style.get("font")
    if font:
        bold = italic = False
        for token in font.split("/")[0].split():
            if token == "italic" or token.startswith("oblique"):
                italic = True
            elif _weight_is_bold(token):
                bold = True
    if "font-weight" in style:
        bold = _weight_is_bold(style["font-weight"])
    if "font-style" in style:
        italic = style["font-style"].startswith(("italic", "oblique"))
    return bold, italic


class _Reader(HTMLParser):
    """Markup in, one note's worth of text and spans out."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.length = 0
        self.spans = []
        self.paragraphs = []
        # style -> [(value, start offset, order opened)], the latest last. One
        # list per style: a close searching one shared list behind every
        # other open style was quadratic; 195 KB of misnested HTML took 8.9 s.
        self._open = {}
        self._opened = 0
        self._implied = {}       # tag -> [whether each open one took its style]
        self._lists = []         # ('bullet'|'number', count so far)
        self._line = 0
        self._line_has_text = False
        self._row_cells = 0      # cells written on the row being read
        self._row_from = 0       # where that row's first cell begins
        self.lone_cells = []     # (start, end) of each row of one cell

    # -- helpers ---------------------------------------------------------
    def _at_line_start(self):
        return not self.length or "".join(self.text[-1:]).endswith("\n")

    # Set when the fragment carries no block-level tag at all. HTML says
    # a newline in text is just whitespace, and for a web page that is right
    # -- the markup was laid out for a human to read. A PDF viewer offers no
    # block tags and puts the page's real line breaks in the text, so
    # collapsing them there throws away the only structure on offer and
    # produces one run-on paragraph.
    keep_newlines = False
    # How deep inside <td>/<th> the parser currently is. A cell is one line
    # of the note, so a block tag inside it -- and a spreadsheet puts a <p>
    # or a <div> in every cell -- must not start a new one. Left unguarded,
    # a pasted table shattered: the header row survived because its cells
    # held bare text, and every row under it became six separate lines.
    cell_depth = 0
    # Whether the caps left anything out: text past MAX_PASTE_CHARS, styles
    # past MAX_PASTE_SPANS. The paste was cut there without a word, and the
    # rest of a long article was simply not in the note.
    text_cut = False
    styles_cut = False

    def _add(self, chunk):
        room = MAX_PASTE_CHARS - self.length
        if len(chunk) > room and chunk[max(room, 0):].strip():
            self.text_cut = True
        if room <= 0:
            return
        chunk = chunk[:room]
        if not chunk:
            return
        self.text.append(chunk)
        self.length += len(chunk)
        if chunk.strip():
            self._line_has_text = True

    def _trim_line_end(self):
        """Drop spaces left at the end of a line by indented markup.

        Source HTML is laid out for a human to read, and those newlines and
        indents arrive as data. They are not part of the note.
        """
        while self.text and self.text[-1] and not self.text[-1].strip(" "):
            self.length -= len(self.text.pop())
        if self.text and self.text[-1].endswith(" "):
            trimmed = self.text[-1].rstrip(" ")
            self.length -= len(self.text[-1]) - len(trimmed)
            self.text[-1] = trimmed

    def _cell(self, chunk):
        """Write one cell's opening, counted for its row (lone_cells)."""
        if not self._row_cells:
            self._row_from = self.length
        self._row_cells += 1
        self._add(chunk)

    def _newline(self):
        self._trim_line_end()
        if self.length and not self.text[-1].endswith("\n"):
            self._add("\n")
            self._line += 1
            self._line_has_text = False

    def _open_style(self, style, value=None):
        self._opened += 1
        self._open.setdefault(style, []).append((value, self.length, self._opened))

    def _close(self, style):
        opened = self._open.get(style)
        if not opened:
            return
        value, start, _order = opened.pop()
        if self.length > start and len(self.spans) >= MAX_PASTE_SPANS:
            self.styles_cut = True
        elif self.length > start:
            span = {"start": start, "end": self.length, "style": style}
            if value is not None:
                span["value"] = value
            self.spans.append(span)

    # -- parser callbacks ------------------------------------------------
    @staticmethod
    def _span_attr(attrs, name):
        try:
            return max(1, min(30, int(str(attrs.get(name, "1")).strip())))
        except (TypeError, ValueError):
            return 1

    def _owed_merge_cell(self):
        """Emit one owed marker cell if a rowspan covers the current column."""
        pending = getattr(self, "_tbl_pending", None)
        if not pending or self._tbl_col not in pending:
            return False
        left, marker = pending[self._tbl_col]
        self._cell(tables.CELL + " " + marker + " ")
        if left - 1 > 0:
            pending[self._tbl_col][0] = left - 1
        else:
            del pending[self._tbl_col]
        self._tbl_col += 1
        return True

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        style = _css(attrs.get("style"))
        bold, italic = _bold_and_italic(style)
        if tag == "table":
            self._tbl_active = getattr(self, "_tbl_active", 0) + 1
            self._tbl_pending = {}
            self._tbl_col = 0
        elif tag == "tr" and getattr(self, "_tbl_active", 0):
            self._tbl_col = 0
        if tag in _STYLE_TAGS:
            # A tag's own CSS can take back what the tag means: Google Docs
            # wraps a whole copy in <b style="font-weight:normal">, and all
            # of it came in bold. Remembered, so its end closes only itself.
            implied = _STYLE_TAGS[tag]
            kept = not ((implied == "bold" and bold is False)
                        or (implied == "italic" and italic is False))
            if kept:
                self._open_style(implied)
            self._implied.setdefault(tag, []).append(kept)
        if tag in ("ul", "ol"):
            if len(self._lists) < MAX_INDENT:
                self._lists.append(["bullet" if tag == "ul" else "number", 0])
        elif tag == "li":
            self._newline()
            if self._lists:
                kind, count = self._lists[-1]
                self._lists[-1][1] = count + 1
                indent = len(self._lists) - 1
                self._add(marker_for(kind, count + 1, indent))
                entry = {"line": self._line, "kind": kind}
                if indent:
                    entry["indent"] = indent
                self.paragraphs.append(entry)
        elif tag in _CELL_TAGS:
            self.cell_depth += 1
            css = _css(dict(attrs).get("style"))
            self._tbl_cell_align = css.get("text-align", "").strip().lower()
            # Columns still covered by a rowspan from an earlier row are
            # owed their marker before this cell can take its place --
            # without it every later cell lands one column too far left,
            # which is how a merged header shears the whole table under it.
            while self._owed_merge_cell():
                pass
            self._tbl_cell = (getattr(self, "_tbl_col", 0),
                              self._span_attr(attrs, "colspan"),
                              self._span_attr(attrs, "rowspan"))
            # An extra lead space is how the padding says "not left":
            # cell_alignments reads two-plus on the left as right-aligned,
            # two-plus on both sides as centred.
            lead = ("  " if self._tbl_cell_align in ("center", "right")
                    else " ")
            self._cell(tables.CELL + lead)
        elif tag in _BLOCK_TAGS:
            if self.cell_depth:
                # A <br> inside a cell is the cell's own line break — the
                # export writes exactly that marker back out, and
                # flattening it to a space silently lost the break on
                # every round-trip. Any OTHER block inside a cell can
                # only be a gap between words.
                self._add(tables.LINE_BREAK if tag == "br" else " ")
            else:
                self._newline()

        if tag in _VOID_TAGS:
            # A void tag never gets an end tag, so any style span it
            # opened could only close at end-of-document — the exact
            # bleed this registry exists to stop. A styled <br>/<img>
            # simply has its inline style ignored.
            return
        opened = []
        for prop, name in (("color", "text_color"),
                           ("background", "highlight"),
                           ("background-color", "highlight")):
            hex_value = _as_hex(style.get(prop))
            if hex_value and _is_meaningful(hex_value, name):
                self._open_style(name, hex_value)
                opened.append(name)
        if bold:
            self._open_style("bold")
            opened.append("bold")
        if italic:
            self._open_style("italic")
            opened.append("italic")
        if opened:
            # Remember exactly which style spans THIS tag opened, so its
            # end tag can close them all. Inline styles on <p>/<div>/<li>
            # and the cell tags used to never close (the style bled to
            # the end of the document), and a span opening two styles
            # closed only the first.
            reg = getattr(self, "_style_opens", None)
            if reg is None:
                reg = self._style_opens = {}
            reg.setdefault(tag, []).append(opened)
        align = style.get("text-align")
        if align in ("center", "right"):
            self.paragraphs.append({"line": self._line, "align": align})

    def handle_endtag(self, tag):
        # Close the style spans this tag's start opened FIRST, before any
        # structural output below — a </p> adds its newline before
        # anything else, and closing after it swept that newline into
        # the span. Keyed by tag name rather than a strict stack, so
        # HTML soup with a stray unclosed element degrades to closing at
        # the next same-named end tag instead of desynchronising.
        reg = getattr(self, "_style_opens", None)
        if reg:
            lst = reg.get(tag)
            if lst:
                for name in reversed(lst.pop()):
                    self._close(name)
        if tag in _STYLE_TAGS:
            taken = self._implied.get(tag)
            if not taken or taken.pop():
                self._close(_STYLE_TAGS[tag])
        if tag in ("ul", "ol"):
            if self._lists:
                self._lists.pop()
            self._newline()
        elif tag in _CELL_TAGS:
            self.cell_depth = max(0, self.cell_depth - 1)
            self._add("  " if getattr(self, "_tbl_cell_align", "")
                      == "center" else " ")
            col, span_c, span_r = getattr(self, "_tbl_cell", (0, 1, 1))
            # A colspan is written out as the anchor followed by "<" cells,
            # and a rowspan owes "^" cells to the rows below -- "^" under
            # the anchor, "<" under the rest of its width, so the rectangle
            # reads back unambiguously.
            for _ in range(span_c - 1):
                self._cell(tables.CELL + " " + tables.MERGE_LEFT + " ")
            if span_r > 1:
                pending = getattr(self, "_tbl_pending", None)
                if pending is None:
                    pending = self._tbl_pending = {}
                for cover in range(col, col + span_c):
                    pending[cover] = [
                        span_r - 1,
                        tables.MERGE_UP if cover == col else tables.MERGE_LEFT]
            self._tbl_col = col + span_c
        elif tag == "table":
            self._tbl_active = max(0, getattr(self, "_tbl_active", 1) - 1)
            self._tbl_pending = {}
        elif tag == "tr":
            if getattr(self, "_tbl_active", 0):
                # Rowspan columns the row never reached still owe markers,
                # with empty filler for any gap on the way to them.
                pending = getattr(self, "_tbl_pending", {})
                for cover in sorted(list(pending)):
                    if cover < self._tbl_col:
                        continue
                    while self._tbl_col < cover:
                        self._cell(tables.CELL + "  ")
                        self._tbl_col += 1
                    self._owed_merge_cell()
            # The row's closing pipe, before the newline _BLOCK_TAGS gives it.
            self._add(tables.CELL)
            if self._row_cells == 1:
                self.lone_cells.append((self._row_from, self.length))
            self._row_cells = 0
            self._newline()
        elif tag in _BLOCK_TAGS:
            if not self.cell_depth:
                self._newline()

    def handle_data(self, data):
        # Markup is indented for humans; a note should not inherit that.
        if self.keep_newlines:
            # Runs of spaces still collapse; the newlines are what survive.
            cleaned = re.sub(r"[ \t\r]+", " ", data)
            cleaned = re.sub(r" *\n *", "\n", cleaned)
        else:
            cleaned = re.sub(r"[ \t\r\n]+", " ", data)
        # A page's non-breaking spaces are plain ones in a note: Chrome writes
        # one at each edge of a bold word or a link, and a search for the
        # words either side found nothing (2026-10-25).
        cleaned = cleaned.replace("\xa0", " ")
        if self.cell_depth:
            # The export draws a checkbox cell as its glyph; coming back,
            # the glyph is the checkbox again. Only inside a cell -- the
            # same glyph in prose is just a character someone typed.
            cleaned = (cleaned.replace("☑", tables.CHECKBOX_DONE)
                              .replace("☐", tables.CHECKBOX_EMPTY))
        if self._at_line_start():
            cleaned = cleaned.lstrip(" ")
        if cleaned.strip() or self._line_has_text:
            self._add(cleaned)


_BLOCK_TAG_RE = re.compile(
    r"<\s*/?\s*(?:" + "|".join(sorted(_BLOCK_TAGS | {"li", "ul", "ol", "table"}))
    + r")\b", re.I)


def _unframe_lone_cells(text, rows):
    """*text* with each row of one cell -- *rows*, the (start, end) of its
    "| ... |" -- written as the cell's words alone, its line breaks real
    lines; with a function moving an offset into *text* to where it now
    falls, and one moving a line number. A row of one cell is no table here
    (tables._MIN_CELLS): left framed, one cell or one column copied from
    Excel or a page pasted as "| rent |"."""
    cuts, breaks, line, seen = [], [], 0, 0
    swaps = []                          # each break's "<", now its "\n"
    for start, end in rows:
        row = text[start:end]
        if len(row) < 2 or row[0] != tables.CELL or row[-1] != tables.CELL:
            continue                    # cut short by MAX_PASTE_CHARS
        line += text.count("\n", seen, start)
        seen = start
        inner = row[1:-1]
        if not inner.strip(" "):
            cuts.append((start, end))
            continue
        first = start + 1 + len(inner) - len(inner.lstrip(" "))
        last = end - 1 - len(inner) + len(inner.rstrip(" "))
        cuts.append((start, first))
        at = text.find(tables.LINE_BREAK, first, last)
        while at != -1:
            swaps.append(at)
            cuts.append((at + 1, at + len(tables.LINE_BREAK)))
            breaks.append(line)
            at = text.find(tables.LINE_BREAK, at + len(tables.LINE_BREAK), last)
        cuts.append((last, end))
    # Looked up by halving, not walked: a long column of styled cells has a
    # cut for every row and a span in most, and walking every cut for every
    # span froze the paste for tens of seconds inside the caps.
    starts = [a for a, _b in cuts]
    before = [0]                        # characters cut before each cut
    for a, b in cuts:
        before.append(before[-1] + b - a)

    def moved(pos):
        i = bisect.bisect_left(starts, pos)
        return pos - before[i - 1] - (min(pos, cuts[i - 1][1]) - starts[i - 1]) if i else pos

    if swaps:
        chars = list(text)
        for at in swaps:
            chars[at] = "\n"
        text = "".join(chars)
    kept, at = [], 0
    for a, b in cuts:
        kept.append(text[at:a])
        at = b
    kept.append(text[at:])
    return ("".join(kept), moved, lambda n: n + bisect.bisect_left(breaks, n))


def html_to_note(fragment, report=None):
    """Convert an HTML fragment into ``(text, formatting, paragraphs)``.

    Everything the app cannot express is dropped. The result is passed
    through the same normalisers the editor uses, so nothing reaches a note
    that would not have been allowed if it had been typed.

    A dict passed as *report* is told whether the caps left anything out:
    ``text_cut`` (text past MAX_PASTE_CHARS) and ``styles_cut`` (styles past
    MAX_PASTE_SPANS) -- so the paste can say so instead of cutting quietly.
    A fragment that cannot be read at all leaves it untouched: nothing is
    pasted, so there is nothing to say.
    """
    reader = _Reader()
    # Looked for in the source rather than during parsing: a block tag late in
    # the fragment still means the earlier newlines were markup, not content.
    reader.keep_newlines = not _BLOCK_TAG_RE.search(fragment or "")
    try:
        # Fed a piece at a time, and no further once the text has passed the
        # ceiling: nothing after it is kept, and a 10 MB page was read to its
        # end all the same, for seconds.
        fragment = fragment or ""
        for at in range(0, len(fragment), _FEED_PIECE):
            reader.feed(fragment[at:at + _FEED_PIECE])
            if reader.text_cut:
                break
        reader.close()
    except Exception:
        # html.parser is forgiving, but a pasted page is arbitrary input and
        # a failed paste must never take the editor with it.
        return "", [], []
    # What the page left open closes at its end, in the order it opened.
    for _order, name in sorted((entry[2], name) for name, entries in reader._open.items()
                               for entry in entries):
        reader._close(name)
    if report is not None:
        report["text_cut"] = reader.text_cut
        report["styles_cut"] = reader.styles_cut

    joined, moved, line_moved = _unframe_lone_cells("".join(reader.text),
                                                    reader.lone_cells)
    text = joined.strip("\n")
    dropped = len(joined) - len(joined.lstrip("\n"))
    spans = [dict(s, start=max(0, moved(s["start"]) - dropped),
                  end=max(0, moved(s["end"]) - dropped)) for s in reader.spans]
    spans = [s for s in spans if s["end"] > s["start"] and s["start"] < len(text)]
    for span in spans:
        span["end"] = min(span["end"], len(text))
    # A pasted table arrives with cells of whatever width they had. Padding
    # them here rather than in the editor keeps the offsets and the text in
    # step from the moment the note is built -- and align() reports what it
    # moved, so the spans move with it.
    if tables.find_blocks(text):
        # A page's own markdown -- a table written out in a code block --
        # brings its separator's dashes as whoever typed them, never a width
        # set in this app; the app's own copy is put back whole by the paste
        # (_paste_formatted), whatever this returns.
        text, forgotten = tables.forget_widths(text)
        spans = shift_spans(spans, forgotten)
        # The ceiling holds on what goes into the note, its padding counted:
        # lined up, a 16 KB clipboard became a 2-million-character note. Past
        # it the text is cut at a line before align() pads anything, and the
        # paste says so (ISSUES_LOG: "Limits that held at the door but not
        # after it").
        if tables.aligned_length(text) > MAX_PASTE_CHARS:
            lines = text.split("\n")
            keep = tables.longest_fitting(
                len(lines), lambda k: tables.aligned_length(
                    "\n".join(lines[:k])), MAX_PASTE_CHARS)
            text = "\n".join(lines[:keep])
            spans = [dict(s, end=min(s["end"], len(text))) for s in spans
                     if s["start"] < len(text)]
            if report is not None:
                report["text_cut"] = True
        # A cell that held a block tag has picked up the space put in its
        # place, and one that held several has picked up several. align()
        # rebuilds each row from its cells' stripped text, which settles all
        # of it, but the spans have to be moved by however much it removed.
        text, table_shifts = tables.align(text)
        spans = shift_spans(spans, table_shifts)
    paragraphs = [dict(p, line=line_moved(p["line"])) for p in reader.paragraphs]
    return (text,
            normalize_formatting(spans),
            normalize_paragraphs(paragraphs, len(text.split("\n"))))


# ---- the other direction ----

_TAG_FOR = {"bold": "b", "italic": "i", "underline": "u", "strike": "s"}


def _styles_at(spans, index):
    """Every style covering one character, as a hashable key."""
    plain, colours = set(), {}
    for span in spans:
        if span["start"] <= index < span["end"]:
            style = span["style"]
            if style == "bold_italic":
                plain.update(("bold", "italic"))
            elif style in _TAG_FOR:
                plain.add(style)
            elif style in _CSS_FOR:
                colours[style] = span["value"]
    return frozenset(plain), tuple(sorted(colours.items()))


# The valued styles, as the CSS another program reads. Size and typeface go
# out so Word keeps them; html_to_note drops them on the way IN by design.
_CSS_FOR = {"text_color": "color:{};", "highlight": "background-color:{};",
            "font_size": "font-size:{}pt;", "font_family": "font-family:'{}';"}


def _wrap(chunk, plain, colours):
    """One run of identically-styled text, as markup."""
    out = escape(chunk)
    for style in sorted(plain):
        out = f"<{_TAG_FOR[style]}>{out}</{_TAG_FOR[style]}>"
    # A typeface's name sits inside quotes inside an attribute: only the
    # characters a font name is made of may travel.
    css = "".join(_CSS_FOR[k].format(
        re.sub(r"[^\w .\-]", "", str(v)) if k == "font_family" else v)
        for k, v in colours)
    return f'<span style="{css}">{out}</span>' if css else out


def _line_html(line, spans, offset):
    """One line's text with its character styles applied.

    The styles are worked out only where a span starts or ends, never per
    character: asked at every character against every span, copying a long
    note with many styled words took seconds and then minutes."""
    if not line:
        return ""
    end = offset + len(line)
    cuts = {0, len(line)}
    for span in spans:
        for at in (span["start"], span["end"]):
            if offset < at < end:
                cuts.add(at - offset)
    points = sorted(cuts)
    pieces, run_start = [], 0
    current = _styles_at(spans, offset)
    for i in points[1:]:
        here = _styles_at(spans, offset + i) if i < len(line) else None
        if here != current:
            pieces.append(_wrap(line[run_start:i], *current))
            run_start, current = i, here
    return "".join(pieces)


def _spans_by_line(spans, lines):
    """Each line's spans -- the ones that reach into it -- in one pass, so
    a line is never checked against the whole note's styles."""
    starts, at = [], 0
    for line in lines:
        starts.append(at)
        at += len(line) + 1
    by_line = [[] for _ in lines]
    for span in spans:
        n = max(0, bisect.bisect_right(starts, span["start"]) - 1)
        while n < len(lines) and starts[n] < span["end"]:
            by_line[n].append(span)
            n += 1
    return by_line


def _cell_html(line, spans, offset, start, end):
    """One table cell's inner HTML.

    A multi-line cell stores its breaks as the literal ``<br>`` marker
    inside the value (see core/tables.LINE_BREAK). Left to _line_html
    alone, escaping turned each one into visible ``&lt;br&gt;`` text in
    the exported page -- so the value is split ON the markers, each
    segment styled from its own offsets, and rejoined with real breaks.
    """
    value = line[start:end]
    parts, pos = [], 0
    while True:
        cut = value.find(tables.LINE_BREAK, pos)
        if cut < 0:
            parts.append((pos, len(value)))
            break
        parts.append((pos, cut))
        pos = cut + len(tables.LINE_BREAK)
    return "<br>".join(
        _line_html(value[a:b], spans, offset + start + a)
        for a, b in parts)


def cell_html(value, spans):
    """One cell's inner HTML from its own value and spans counted in it:
    the copy of table cells writes a cell exactly as the export does."""
    return _cell_html(value, spans, 0, 0, len(value))


def html_document(title, body_html):
    """A complete standalone HTML file around one note's fragment.

    note_to_html() makes clipboard fragments; a FILE needs the document
    around one -- doctype, charset, a title, and just enough styling
    that the table borders exist (the fragment's <td>s carry none, and
    a borderless table reads as loose words in a browser).

    The visible title is a styled <div>, deliberately NOT an <h1>: Word
    maps HTML headings onto its own Heading styles, and a modern Word
    puts a collapse triangle on every heading -- with the whole note
    under the one heading, the exported document arrived offering to
    fold itself away. A div that merely looks like a title renders the
    same everywhere and means nothing to Word's outline.
    """
    safe_title = escape(title or "Untitled note")
    return (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{safe_title}</title>\n"
        "<style>\n"
        "body { font-family: 'Segoe UI', Arial, sans-serif; "
        "max-width: 800px; margin: 2em auto; padding: 0 1em; "
        "line-height: 1.5; }\n"
        # Browsers drop background colours when printing unless told
        # not to -- without this, Ctrl+P -> PDF lost every highlight.
        "* { -webkit-print-color-adjust: exact; "
        "print-color-adjust: exact; }\n"
        # A wide table must wrap inside the page rather than run off
        # its right edge; long cell content breaks rather than pushes.
        "table { border-collapse: collapse; margin: 0.5em 0; "
        "max-width: 100%; }\n"
        "th, td { border: 1px solid #999; padding: 4px 10px; "
        "overflow-wrap: anywhere; }\n"
        # Browsers centre <th> by default; the app's headers are
        # left like everything else, and a cell's own alignment
        # still wins via its inline style.
        "th { text-align: left; }\n"
        "</style>\n</head>\n<body>\n"
        f'<div style="font-size: 1.7em; font-weight: bold; '
        f'margin: 0 0 0.6em 0;">{safe_title}</div>\n'
        f"{body_html}\n</body>\n</html>\n")


def note_to_html(text, formatting=None, paragraphs=None,
                 inline_tables=False):
    """Render a note as an HTML fragment other applications understand.

    List markers are taken back out of the text and expressed as real
    ``<ul>``/``<ol>`` elements, because that is what a word processor or a
    mail client will recognise -- a literal bullet character would paste as
    a bullet-shaped letter rather than as a list.
    """
    text = text or ""
    lines = text.split("\n")
    line_spans = _spans_by_line(normalize_formatting(formatting or []), lines)
    props = {p["line"]: p for p in normalize_paragraphs(paragraphs or [], len(lines))}

    # Merge markers only make sense against their whole block, so every
    # block's matrix is resolved up front and looked up per line.
    merge_at = {}
    separator_lines = set()
    hidden_at = {}
    for block_first, block_last in tables.find_blocks(text):
        block = lines[block_first:block_last + 1]
        sep_at = tables.separator_index(block)
        hidden_cols = set()
        if sep_at is not None:
            # Mechanics, not data: the separator's dashes never reach the
            # markup a word processor sees.
            separator_lines.add(block_first + sep_at)
            # A column the author hid is hidden in the export too: the
            # page should show what the app shows. The data itself stays
            # in the note -- unhide, and the next export carries it.
            hidden_cols = {
                i for i, col in enumerate(
                    tables.parse_separator(block[sep_at]))
                if col.get("hidden")}
        data_lines = [n for n in range(block_first, block_last + 1)
                      if n - block_first != sep_at]
        matrix = [tables.split_row(lines[n]) for n in data_lines]
        m_spans, m_covered = tables.merge_map(matrix)
        for r, n in enumerate(data_lines):
            merge_at[n] = (
                {c: m_spans[(ar, c)] for (ar, c) in m_spans if ar == r},
                {c for (rr, c) in m_covered if rr == r})
            hidden_at[n] = hidden_cols

    out, offset, open_lists, in_table = [], 0, [], False
    for number, line in enumerate(lines):
        spans = line_spans[number]
        entry = props.get(number, {})
        kind = entry.get("kind")
        indent = entry.get("indent", 0)
        body, body_offset = line, offset
        if kind:
            marker = ""
            for glyph in BULLET_GLYPHS:
                if line.startswith(glyph + " "):
                    marker = glyph + " "
                    break
            if not marker:
                match = re.match(r"^\d+\. ", line)
                marker = match.group(0) if match else ""
            body, body_offset = line[len(marker):], offset + len(marker)

        target = indent + 1 if kind else 0
        # Close while there are too many levels open, and also when the
        # level we are about to write into is the wrong kind: a numbered
        # item following a bulleted one at the same depth needs its own
        # <ol>, not another <li> in the open <ul>.
        while open_lists and (
                len(open_lists) > target
                or (kind and len(open_lists) == target
                    and open_lists[-1][0] != kind)):
            closed, was_nested = open_lists.pop()
            out.append("</ul>" if closed == "bullet" else "</ol>")
            if was_nested:
                out.append("</li>")
        row = None if kind else tables.cell_bounds(line) if tables.is_table_row(line) else None
        if number in separator_lines:
            # The separator stays inside the table run (so in_table holds)
            # but emits nothing.
            offset += len(line) + 1
            continue
        if in_table and row is None:
            out.append("</table>")
            in_table = False
        if kind:
            while len(open_lists) < target:
                # A sub-list belongs *inside* the item it hangs off, so the
                # item's closing tag is taken back and re-emitted after the
                # sub-list ends. Browsers tolerate the flat version; Word and
                # mail clients are less forgiving, and this is markup other
                # applications have to read.
                nested = bool(out) and out[-1].endswith("</li>")
                if nested:
                    out[-1] = out[-1][:-len("</li>")]
                open_lists.append((kind, nested))
                out.append("<ul>" if kind == "bullet" else "<ol>")
            out.append(f"<li>{_line_html(body, spans, body_offset)}</li>")
        elif row is not None:
            # Real <table> markup rather than the pipes, for the same reason
            # a list goes out as <ul>: a word processor understands one and
            # would paste the other as a row of pipe characters. Each cell
            # is rendered from its own offsets so formatting inside it
            # survives the trip.
            if not in_table:
                # The table's place on the page (centred / right) lives
                # as an alignment entry on its lines. It goes out TWICE:
                # auto margins for browsers, and the legacy align
                # attribute for Word, which ignores margin:auto on
                # tables entirely. align="right" would also make
                # browsers float the table with text wrapping around it
                # (the UA sheet maps it to float:right), so float:none
                # rides along to keep the browser on the margin path.
                place = entry.get("align")
                # A clipboard fragment travels without the document's
                # stylesheet, and Word gives a bare HTML table no visible
                # borders at all -- the pasted table was a selectable
                # phantom. inline_tables rides the border on every tag.
                base = "border-collapse:collapse;" if inline_tables else ""
                if place == "center":
                    t_style = f' align="center" style="{base}margin:0.5em auto;"'
                elif place == "right":
                    t_style = (f' align="right" style="float:none; '
                               f'{base}margin:0.5em 0 0.5em auto;"')
                elif base:
                    t_style = f' style="{base}"'
                else:
                    t_style = ""
                out.append(f"<table{t_style}>")
                in_table = True
                header_row = True
            else:
                header_row = False
            row_spans, row_covered = merge_at.get(number, ({}, set()))
            row_hidden = hidden_at.get(number, set())
            row_aligns = tables.cell_alignments(line)
            cells = []
            for c, (start, end) in enumerate(row):
                if c in row_covered or c in row_hidden:
                    continue
                rs, cs = row_spans.get(c, (1, 1))
                # A merge reaching across a hidden column narrows by the
                # columns the page will not show.
                cs -= len([h for h in row_hidden if c < h < c + cs])
                attr = ""
                if cs > 1:
                    attr += f' colspan="{cs}"'
                if rs > 1:
                    attr += f' rowspan="{rs}"'
                state = tables.checkbox_state(line[start:end])
                styles = []
                if state is not None:
                    # The app draws a checkbox centred in its cell no
                    # matter what the padding says -- the page does too,
                    # or a left-padded box sits left only once exported.
                    styles.append("text-align:center;")
                elif c < len(row_aligns) and row_aligns[c] != tables.ALIGN_LEFT:
                    styles.append(f"text-align:{row_aligns[c]};")
                # A highlight covering the whole cell colours the <td>
                # itself, the way the app draws it. Left as a <span>, an
                # EMPTY highlighted cell (the highlight rides the pad
                # spaces) would collapse with the whitespace and show as
                # a sliver or nothing.
                cell_a, cell_b = offset + start, offset + end
                if cell_b == cell_a:
                    # An empty cell's highlight rides its padding.
                    pipes = tables.pipe_positions(line)
                    if c + 1 < len(pipes):
                        cell_a = offset + pipes[c] + 1
                        cell_b = offset + pipes[c + 1]
                if cell_b > cell_a:
                    for sp in spans:
                        if (sp["style"] == "highlight"
                                and sp["start"] <= cell_a
                                and sp["end"] >= cell_b):
                            styles.append(
                                f"background-color:{sp['value']};")
                            break
                if inline_tables:
                    styles.append("border:1px solid #999;padding:4px 10px;")
                if styles:
                    attr += f' style="{"".join(styles)}"'
                # The FIRST row is the header the app draws bold on
                # its own surface -- exported as <th>, so Word and the
                # browsers bold it too instead of flattening it into an
                # ordinary row.
                tag_name = "th" if header_row else "td"
                # A checkbox cell leaves as the glyph the app draws, not
                # as its bracket markers; its colour (a text_color span
                # riding the markers) comes along. The import maps the
                # glyphs back, so a round trip keeps a real checkbox.
                if state is not None:
                    glyph = "☑" if state else "☐"
                    for sp in spans:
                        if (sp["style"] == "text_color"
                                and sp["start"] <= offset + start
                                and sp["end"] >= offset + end):
                            glyph = (f'<span style="color:{sp["value"]};">'
                                     f"{glyph}</span>")
                            break
                    inner = glyph
                else:
                    inner = _cell_html(line, spans, offset, start, end)
                cells.append(f"<{tag_name}{attr}>{inner}</{tag_name}>")
            out.append(f"<tr>{''.join(cells)}</tr>")
        else:
            align = entry.get("align")
            style = f' style="text-align:{align};"' if align else ""
            out.append(f"<div{style}>{_line_html(body, spans, body_offset) or '<br>'}</div>")
        offset += len(line) + 1

    if in_table:
        out.append("</table>")
    while open_lists:
        closed, was_nested = open_lists.pop()
        out.append("</ul>" if closed == "bullet" else "</ol>")
        if was_nested:
            out.append("</li>")
    return "".join(out)


# --- Rejoining text that a column broke -------------------------------------
#
# A PDF has no paragraphs. It has lines placed on a page, and copying from one
# hands those line breaks over as though they were meant. Keeping them gives a
# note broken at the PDF's column width, narrow and ragged; dropping them all
# gives one run-on block. Neither is what the page said.
#
# Every break is judged by one question: **would the next line's first word
# have fitted on this one?** If it would have, the line was ended on purpose
# and the break is a real one. If it would not, the column forced it and the
# two lines are one. That test needs no threshold tuned to a particular width,
# which an earlier attempt did need -- and it got 60-character text wrong in
# one direction and 110-character text wrong in the other.
#
# Rejoining is still guesswork, so it only runs where the evidence is strong.
# Everything else -- an address, a list, a poem, a couple of lines -- comes
# back untouched. A break someone meant is worse to lose than a break left in:
# the first destroys what they wrote, the second is merely untidy.

# Fewer lines than this is not a pattern, it is a coincidence.
_MIN_WRAPPED_LINES = 3
# Narrow text is far more likely to be a list or an address than a column.
_MIN_COLUMN_WIDTH = 40
# How many of the breaks have to be forced before a column is the likely cause.
_MOSTLY_FORCED = 0.6


# The column is never narrower than the longest line seen, and usually a
# little wider -- no line ends exactly at the edge unless a word happens to
# land there. Judging a near-miss as a deliberate ending therefore splits
# paragraphs that were only wrapped, so a couple of characters of slack are
# allowed and a borderline break counts as forced. That errs towards joining,
# which loses a paragraph break at worst; erring the other way cuts sentences
# in half.
_COLUMN_SLACK = 2

# A paragraph almost never stops in the middle of a sentence, so a line that
# ends without any of these was almost certainly broken by the column even if
# the next word looked like it would have fitted. Closing quotes and brackets
# count, since a sentence can end inside them.
_SENTENCE_END = ('.', '!', '?', ':', ';', '"', "'", ')', ']', '’', '”')
# Unless the line is far short of the column, in which case it ended early on
# purpose -- a heading, or the last line of a paragraph -- whatever it ends in.
_CLEARLY_SHORT = 0.7


def _ends_a_paragraph(line, width):
    """Whether a line that *could* have taken another word really ended."""
    stripped = line.rstrip()
    if not stripped:
        return True
    if len(stripped) < width * _CLEARLY_SHORT:
        return True
    return stripped.endswith(_SENTENCE_END)


def _forced_break(line, next_line, width, slack=0):
    """True when the next line's first word could not have fitted on this one.

    Which means the column broke the line rather than the writer ending it.

    *slack* is used only when deciding where a paragraph ended, never when
    deciding whether this is a column at all. Allowing it in the detection
    made three short paragraphs -- each a single line, each followed by a
    word too long to join it -- look like wrapped prose and become one.
    """
    word = next_line.strip().split(" ")[0] if next_line.strip() else ""
    if not word:
        return False
    return len(line) + 1 + len(word) > width - slack


def _looks_wrapped(lines):
    """True when these lines were broken by a column, not on purpose."""
    if len(lines) < _MIN_WRAPPED_LINES:
        return False
    # A list's line breaks are the list, and a table's rows are its rows.
    # Never touch either, and do not let one anywhere in the run make the
    # rest of it look like prose.
    if any(parse_list_marker(line.lstrip(" \t"))[0] for line in lines):
        return False
    if any(tables.is_table_row(line) for line in lines):
        return False
    width = max(len(line) for line in lines)
    if width < _MIN_COLUMN_WIDTH:
        return False
    breaks = len(lines) - 1
    forced = sum(1 for i in range(breaks)
                 if _forced_break(lines[i], lines[i + 1], width))
    return forced >= max(2, int(breaks * _MOSTLY_FORCED))


def _join_wrapped(lines):
    """One paragraph out of the lines a column broke it into."""
    joined = ""
    for line in lines:
        piece = line.strip()
        if not joined:
            joined = piece
        elif (len(joined) > 1 and joined[-1] == "-" and joined[-2].isalpha()
              and piece[:1].islower()):
            # A hyphen at the break joins without a space: "more-" + "or-less"
            # is one word, and so is "type-" + "setting". The hyphen is kept,
            # because those two cases cannot be told apart and only one of the
            # two possible mistakes is survivable -- keeping it turns a
            # syllable break into "type-setting", which still reads, while
            # dropping it turned "more-or-less" into "moreor-less", which is
            # not a word at all. Only when a letter precedes the hyphen and
            # the next line goes on in lower case, so "see page 12 -" and
            # "- and then" keep their space.
            joined += piece
        else:
            joined += " " + piece
    return joined


def reflow_wrapped(text):
    """Rejoin lines that a fixed-width column broke, leaving real breaks alone.

    Blank lines always separate paragraphs and are never removed. Within a run
    that looks like a wrapped column, a line whose break was not forced by the
    column ends a paragraph. A run that does not look wrapped comes back
    exactly as it went in.
    """
    blocks = []
    for block in re.split(r"\n[ \t]*\n", text or ""):
        lines = [line.rstrip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if not _looks_wrapped(lines):
            blocks.append("\n".join(lines))
            continue
        width = max(len(line) for line in lines)
        # Many documents mark a new paragraph by indenting its first line.
        # Where that happens it is a far better signal than any measurement:
        # a line whose break looks forced still ends a paragraph if the line
        # after it is indented past the block's own left edge.
        edge = min(len(line) - len(line.lstrip()) for line in lines)
        paragraphs, current = [], []
        for i, line in enumerate(lines):
            current.append(line)
            last = i == len(lines) - 1
            if last:
                paragraphs.append(current)
                current = []
                continue
            following = lines[i + 1]
            indented = len(following) - len(following.lstrip()) > edge
            could_fit = not _forced_break(line, following, width, _COLUMN_SLACK)
            if indented or (could_fit and _ends_a_paragraph(line, width)):
                paragraphs.append(current)
                current = []
        if current:
            paragraphs.append(current)
        blocks.append("\n".join(_join_wrapped(p) for p in paragraphs))
    return "\n\n".join(blocks)
