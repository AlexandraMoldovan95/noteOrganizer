"""How rich-text formatting is stored on a note, and kept sane.

WHAT THIS MODULE IS FOR
-----------------------
A note's ``formatting`` field is a flat list of spans::

    {"start": 0, "end": 5, "style": "bold"}
    {"start": 6, "end": 9, "style": "highlight", "value": "#fff3b0"}

``start``/``end`` are CHARACTER OFFSETS into the note body, not Tkinter's
own ``line.column`` indices. That is deliberate: offsets are plain data
that survive being saved to JSON, shared as a code, and reloaded into a
window of a different size, whereas line/column positions shift the
moment the text wraps differently.

:func:`normalize_formatting` is the gatekeeper. Anything that is not a
valid span is dropped rather than repaired, so one bad entry from an old
file or hand-edited JSON cannot corrupt the editor.

TWO KINDS OF STYLE
------------------
* :data:`KNOWN_FORMAT_STYLES` - on/off styles needing no extra data.
* :data:`VALUE_FORMAT_STYLES` - styles carrying a colour, which must also
  have a valid ``value``. A colour span without one is discarded.

Why ``bold_italic`` is its own style rather than two overlapping spans is
a Tkinter constraint, explained in the comment just below.
"""

import re

# Tkinter Text tags that both set the widget's font option don't compose —
# only one wins — so bold+italic together has to be one precomputed
# compound font, same as a real font would have a distinct bold-italic
# variant rather than layering two independent effects.
KNOWN_FORMAT_STYLES = {"bold", "italic", "bold_italic", "underline", "strike"}

# text_color/highlight carry a "value" (a hex color) instead of being plain
# on/off styles. Unlike bold/italic, foreground/background are independent
# Tk tag options — they don't fight the font option the way bold and italic
# do, so no compound-tag scheme is needed for these two.
VALUE_FORMAT_STYLES = {"text_color", "highlight"}


def _is_valid_hex_color(value):
    return (isinstance(value, str) and len(value) == 7 and value[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in value[1:]))


def normalize_formatting(value):
    """Coerce a note/template's formatting list to valid spans, silently
    dropping anything malformed (bad type, unknown style, out-of-order or
    non-integer offsets, or — for text_color/highlight — a missing/invalid
    hex value) rather than ever letting bad data crash the editor."""
    if not isinstance(value, list):
        return []
    spans = []
    for span in value:
        if not isinstance(span, dict):
            continue
        style = span.get("style")
        start, end = span.get("start"), span.get("end")
        if not (isinstance(start, int) and not isinstance(start, bool)
                and isinstance(end, int) and not isinstance(end, bool)
                and 0 <= start < end):
            continue
        if style in KNOWN_FORMAT_STYLES:
            spans.append({"start": start, "end": end, "style": style})
        elif style in VALUE_FORMAT_STYLES and _is_valid_hex_color(span.get("value")):
            spans.append({"start": start, "end": end, "style": style,
                          "value": span["value"].lower()})
    return spans


# ---- Naming the tags the editor applies ----
#
# These three were on the app class and are pure string work: no widget, no
# state. They decide what a Tk tag is *called*, which is why they sit beside
# the span format they name rather than in the editor that applies them.

_WORD_CHAR_RE = re.compile(r"\w", re.UNICODE)


def char_class(ch):
    """Which of three classes a character belongs to.

    Contiguous runs of one class form a double-click "word". Punctuation is
    its own class so that it always breaks a word, unlike Tk's built-in
    boundary detection, which glues a full stop to its neighbours and
    selects the whole of ``something.else`` whichever half was clicked.
    """
    if not ch:
        return None
    if _WORD_CHAR_RE.match(ch):
        return "word"
    if ch.isspace():
        return "space"
    return "other"


def color_tag_name(style, hex_color):
    """The tag name for one colour of one style, e.g. ``highlight_fff3b0``."""
    return f"{style}_{hex_color.lstrip('#').lower()}"


def font_tag_for(is_bold, is_italic):
    """The single font tag for this bold/italic combination, or None.

    Two Tk tags that both set the widget's font option do not compose -- one
    simply wins -- so bold and italic together needs its own precomputed
    compound tag rather than layering two independent ones.
    """
    if is_bold and is_italic:
        return "bold_italic"
    if is_bold:
        return "bold"
    if is_italic:
        return "italic"
    return None


# ---- Bullet and numbered lists ----
#
# A list line carries its marker in the body text: "• milk", "1. milk". The
# alternative -- drawing the marker without storing it -- was considered and
# rejected. Formatting is stored as character offsets into the body, so a
# marker that exists on screen but not in the body would put every offset
# after it out by the marker's length, on every line, forever. Keeping the
# body and the widget identical means the offsets need no translation at all.
#
# ``paragraphs`` on a note records line-level formatting -- what a whole line
# looks like, as opposed to the characters inside it, which ``formatting``
# covers. Today that means which lines are list items:
#
#     [{"line": 0, "kind": "bullet"}, {"line": 1, "kind": "number"}]
#
# The marker is derivable from the text, so this looks redundant -- but it is
# what tells the editor to give the line a hanging indent, and what lets
# renumbering tell a real "1." from a line that merely starts with one.

BULLET = "• "
_NUMBER_RE = re.compile(r"^(\d+)\. ")
LIST_KINDS = ("bullet", "number")


def parse_list_marker(line):
    """Split a line into ``(kind, marker, rest)``.

    Returns ``(None, "", line)`` for a line that is not a list item.
    """
    if line.startswith(BULLET):
        return "bullet", BULLET, line[len(BULLET):]
    m = _NUMBER_RE.match(line)
    if m:
        return "number", m.group(0), line[m.end():]
    return None, "", line


def marker_for(kind, number=1):
    """The text a list line of this kind starts with."""
    return BULLET if kind == "bullet" else f"{number}. "


def normalize_paragraphs(value, line_count=None):
    """Drop anything that is not a usable paragraph entry.

    The same gatekeeper idea as :func:`normalize_formatting`: one bad entry
    from an old file or hand-edited JSON should be discarded, not repaired
    into something that half-works.
    """
    if not isinstance(value, list):
        return []
    clean, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            continue
        line, kind = item.get("line"), item.get("kind")
        if not isinstance(line, int) or line < 0 or kind not in LIST_KINDS:
            continue
        if line_count is not None and line >= line_count:
            continue
        if line in seen:            # one kind per line
            continue
        seen.add(line)
        clean.append({"line": line, "kind": kind})
    return sorted(clean, key=lambda b: b["line"])


def renumber(body, paragraphs):
    """Make every numbered run read 1, 2, 3 from its own start.

    A run ends at any line that is not a numbered item -- a blank line, a
    paragraph, or a bullet -- so two numbered lists separated by text each
    start again at one, which is what a person writing them expects.

    Returns ``(body, shift)``: the rewritten body, and a list of
    ``(offset, delta)`` describing where characters were inserted or removed,
    so the caller can move formatting spans to match.
    """
    lines = body.split("\n")
    by_line = {b["line"]: b["kind"] for b in normalize_paragraphs(paragraphs, len(lines))}
    shifts, counter, pos = [], 0, 0
    for i, line in enumerate(lines):
        kind = by_line.get(i)
        if kind == "number":
            counter += 1
            _, old_marker, rest = parse_list_marker(line)
            new_marker = marker_for("number", counter)
            if old_marker != new_marker:
                delta = len(new_marker) - len(old_marker)
                if delta:
                    # Only a change in marker *length* moves later text.
                    # "1." -> "2." rewrites a character without shifting
                    # anything, and recording it would be noise the caller
                    # then has to loop over for nothing.
                    shifts.append((pos, delta))
                lines[i] = new_marker + rest
        else:
            counter = 0
        pos += len(lines[i]) + 1        # +1 for the newline
    return "\n".join(lines), shifts


def shift_spans(spans, shifts):
    """Move formatting spans by the character shifts renumbering caused.

    Without this, renumbering "9. " to "10. " would push every later
    character along by one and leave the bold in the wrong place -- exactly
    the mismatch that storing the marker in the body is meant to avoid.
    """
    if not shifts:
        return spans
    out = []
    for span in spans:
        start, end = span["start"], span["end"]
        for at, delta in shifts:
            if at < start:
                start += delta
            if at < end:
                end += delta
        moved = dict(span)
        moved["start"], moved["end"] = start, end
        out.append(moved)
    return out
