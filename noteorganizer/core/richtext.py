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

from .formatting import (
    BULLET_GLYPHS,
    MAX_INDENT,
    marker_for,
    normalize_formatting,
    normalize_paragraphs,
)

# A pasted web page can carry a great deal of markup. These are not tuning
# knobs so much as a refusal to let one paste produce a note nobody can
# edit -- the same reasoning as the title cap.
MAX_PASTE_CHARS = 100_000
MAX_PASTE_SPANS = 2_000

# Tags that mean "a new line starts here".
_BLOCK_TAGS = {"p", "div", "br", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
               "blockquote", "pre", "section", "article"}

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
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
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
        elif tag in _BLOCK_TAGS:
            self._newline()

        style = _css(attrs.get("style"))
        for prop, name in (("color", "text_color"),
                           ("background-color", "highlight")):
            hex_value = _as_hex(style.get(prop))
            if hex_value:
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
        elif tag in _BLOCK_TAGS:
            self._newline()
        elif tag in ("span", "font"):
            for name in ("text_color", "highlight", "bold", "italic"):
                if any(o[0] == name for o in self._open):
                    self._close(name)
                    break

    def handle_data(self, data):
        # Markup is indented for humans; a note should not inherit that.
        cleaned = re.sub(r"[ \t\r\n]+", " ", data)
        if self._at_line_start():
            cleaned = cleaned.lstrip(" ")
        if cleaned.strip() or self._line_has_text:
            self._add(cleaned)


def html_to_note(fragment):
    """Convert an HTML fragment into ``(text, formatting, paragraphs)``.

    Everything the app cannot express is dropped. The result is passed
    through the same normalisers the editor uses, so nothing reaches a note
    that would not have been allowed if it had been typed.
    """
    reader = _Reader()
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

    out, offset, open_lists = [], 0, []
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
        while len(open_lists) > target:
            closed, was_nested = open_lists.pop()
            out.append("</ul>" if closed == "bullet" else "</ol>")
            if was_nested:
                out.append("</li>")
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
        else:
            align = entry.get("align")
            style = f' style="text-align:{align};"' if align else ""
            out.append(f"<div{style}>{_line_html(body, spans, body_offset) or '<br>'}</div>")
        offset += len(line) + 1

    while open_lists:
        closed, was_nested = open_lists.pop()
        out.append("</ul>" if closed == "bullet" else "</ol>")
        if was_nested:
            out.append("</li>")
    return "".join(out)
