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
