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
MAX_PASTE_SPANS = 2_000

# Tags that mean "a new line starts here".
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
    """A style attribute as a dict, lowercased, without failing on junk."""
    out = {}
    for chunk in (style_attr or "").split(";"):
        if ":" not in chunk:
            continue
        name, _, value = chunk.partition(":")
        out[name.strip().lower()] = value.strip()
    return out


class _Reader(HTMLParser):
    """Markup in, one note's worth of text and spans out."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.length = 0
        self.spans = []
        self.paragraphs = []
        self._open = []          # (style, value, start offset)
        self._lists = []         # ('bullet'|'number', count so far)
        self._line = 0
        self._line_has_text = False

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

    def _add(self, chunk):
        if self.length >= MAX_PASTE_CHARS:
            return
        chunk = chunk[:MAX_PASTE_CHARS - self.length]
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

    def _newline(self):
        self._trim_line_end()
        if self.length and not self.text[-1].endswith("\n"):
            self._add("\n")
            self._line += 1
            self._line_has_text = False

    def _close(self, style):
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == style:
                name, value, start = self._open.pop(i)
                if self.length > start and len(self.spans) < MAX_PASTE_SPANS:
                    span = {"start": start, "end": self.length, "style": name}
                    if value is not None:
                        span["value"] = value
                    self.spans.append(span)
                return

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
        self._add(tables.CELL + " " + marker + " ")
        if left - 1 > 0:
            pending[self._tbl_col][0] = left - 1
        else:
            del pending[self._tbl_col]
        self._tbl_col += 1
        return True

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self._tbl_active = getattr(self, "_tbl_active", 0) + 1
            self._tbl_pending = {}
            self._tbl_col = 0
        elif tag == "tr" and getattr(self, "_tbl_active", 0):
            self._tbl_col = 0
        if tag in _STYLE_TAGS:
            self._open.append((_STYLE_TAGS[tag], None, self.length))
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
            self._add(tables.CELL + lead)
        elif tag in _BLOCK_TAGS:
            if self.cell_depth:
                # Whatever the block meant, inside a cell it can only be a
                # gap between words.
                self._add(" ")
            else:
                self._newline()

        style = _css(attrs.get("style"))
        for prop, name in (("color", "text_color"),
                           ("background", "highlight"),
                           ("background-color", "highlight")):
            hex_value = _as_hex(style.get(prop))
            if hex_value and _is_meaningful(hex_value, name):
                self._open.append((name, hex_value, self.length))
        if style.get("font-weight") in ("bold", "700", "800", "900"):
            self._open.append(("bold", None, self.length))
        if style.get("font-style") == "italic":
            self._open.append(("italic", None, self.length))
        align = style.get("text-align")
        if align in ("center", "right"):
            self.paragraphs.append({"line": self._line, "align": align})

    def handle_endtag(self, tag):
        if tag in _STYLE_TAGS:
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
                self._add(tables.CELL + " " + tables.MERGE_LEFT + " ")
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
                        self._add(tables.CELL + "  ")
                        self._tbl_col += 1
                    self._owed_merge_cell()
            # The row's closing pipe, before the newline _BLOCK_TAGS gives it.
            self._add(tables.CELL)
            self._newline()
        elif tag in _BLOCK_TAGS:
            if not self.cell_depth:
                self._newline()
        elif tag in ("span", "font"):
            for name in ("text_color", "highlight", "bold", "italic"):
                if any(o[0] == name for o in self._open):
                    self._close(name)
                    break

    def handle_data(self, data):
        # Markup is indented for humans; a note should not inherit that.
        if self.keep_newlines:
            # Runs of spaces still collapse; the newlines are what survive.
            cleaned = re.sub(r"[ \t\r]+", " ", data)
            cleaned = re.sub(r" *\n *", "\n", cleaned)
        else:
            cleaned = re.sub(r"[ \t\r\n]+", " ", data)
        if self._at_line_start():
            cleaned = cleaned.lstrip(" ")
        if cleaned.strip() or self._line_has_text:
            self._add(cleaned)


_BLOCK_TAG_RE = re.compile(
    r"<\s*/?\s*(?:" + "|".join(sorted(_BLOCK_TAGS | {"li", "ul", "ol", "table"}))
    + r")\b", re.I)


def html_to_note(fragment):
    """Convert an HTML fragment into ``(text, formatting, paragraphs)``.

    Everything the app cannot express is dropped. The result is passed
    through the same normalisers the editor uses, so nothing reaches a note
    that would not have been allowed if it had been typed.
    """
    reader = _Reader()
    # Looked for in the source rather than during parsing: a block tag late in
    # the fragment still means the earlier newlines were markup, not content.
    reader.keep_newlines = not _BLOCK_TAG_RE.search(fragment or "")
    try:
        reader.feed(fragment or "")
        reader.close()
    except Exception:
        # html.parser is forgiving, but a pasted page is arbitrary input and
        # a failed paste must never take the editor with it.
        return "", [], []
    for name, _value, _start in list(reader._open):
        reader._close(name)

    text = "".join(reader.text).strip("\n")
    dropped = len("".join(reader.text)) - len("".join(reader.text).lstrip("\n"))
    spans = [dict(s, start=max(0, s["start"] - dropped),
                  end=max(0, s["end"] - dropped)) for s in reader.spans]
    spans = [s for s in spans if s["end"] > s["start"] and s["start"] < len(text)]
    for span in spans:
        span["end"] = min(span["end"], len(text))
    # A pasted table arrives with cells of whatever width they had. Padding
    # them here rather than in the editor keeps the offsets and the text in
    # step from the moment the note is built -- and align() reports what it
    # moved, so the spans move with it.
    if tables.find_blocks(text):
        # A cell that held a block tag has picked up the space put in its
        # place, and one that held several has picked up several. align()
        # rebuilds each row from its cells' stripped text, which settles all
        # of it, but the spans have to be moved by however much it removed.
        text, table_shifts = tables.align(text)
        spans = shift_spans(spans, table_shifts)
    paragraphs = [dict(p) for p in reader.paragraphs]
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
            elif style in ("text_color", "highlight"):
                colours[style] = span["value"]
    return frozenset(plain), tuple(sorted(colours.items()))


def _wrap(chunk, plain, colours):
    """One run of identically-styled text, as markup."""
    out = escape(chunk)
    for style in sorted(plain):
        out = f"<{_TAG_FOR[style]}>{out}</{_TAG_FOR[style]}>"
    css = "".join(
        f"color:{v};" if k == "text_color" else f"background-color:{v};"
        for k, v in colours)
    return f'<span style="{css}">{out}</span>' if css else out


def _line_html(line, spans, offset):
    """One line's text with its character styles applied."""
    if not line:
        return ""
    pieces, run_start = [], 0
    current = _styles_at(spans, offset)
    for i in range(1, len(line) + 1):
        here = _styles_at(spans, offset + i) if i < len(line) else None
        if here != current:
            pieces.append(_wrap(line[run_start:i], *current))
            run_start, current = i, here
    return "".join(pieces)


def note_to_html(text, formatting=None, paragraphs=None):
    """Render a note as an HTML fragment other applications understand.

    List markers are taken back out of the text and expressed as real
    ``<ul>``/``<ol>`` elements, because that is what a word processor or a
    mail client will recognise -- a literal bullet character would paste as
    a bullet-shaped letter rather than as a list.
    """
    text = text or ""
    spans = normalize_formatting(formatting or [])
    lines = text.split("\n")
    props = {p["line"]: p for p in normalize_paragraphs(paragraphs or [], len(lines))}

    # Merge markers only make sense against their whole block, so every
    # block's matrix is resolved up front and looked up per line.
    merge_at = {}
    for block_first, block_last in tables.find_blocks(text):
        matrix = [tables.split_row(lines[n])
                  for n in range(block_first, block_last + 1)]
        m_spans, m_covered = tables.merge_map(matrix)
        for r in range(len(matrix)):
            merge_at[block_first + r] = (
                {c: m_spans[(ar, c)] for (ar, c) in m_spans if ar == r},
                {c for (rr, c) in m_covered if rr == r})

    out, offset, open_lists, in_table = [], 0, [], False
    for number, line in enumerate(lines):
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
                out.append("<table>")
                in_table = True
            row_spans, row_covered = merge_at.get(number, ({}, set()))
            row_aligns = tables.cell_alignments(line)
            cells = []
            for c, (start, end) in enumerate(row):
                if c in row_covered:
                    continue
                rs, cs = row_spans.get(c, (1, 1))
                attr = ""
                if cs > 1:
                    attr += f' colspan="{cs}"'
                if rs > 1:
                    attr += f' rowspan="{rs}"'
                if c < len(row_aligns) and row_aligns[c] != tables.ALIGN_LEFT:
                    attr += f' style="text-align:{row_aligns[c]};"'
                cells.append(f"<td{attr}>"
                             f"{_line_html(line[start:end], spans, offset + start)}"
                             f"</td>")
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
