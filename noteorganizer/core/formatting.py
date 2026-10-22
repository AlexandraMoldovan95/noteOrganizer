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

import bisect
import heapq
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
COLOR_FORMAT_STYLES = {"text_color", "highlight"}

# Size and family also carry a value, but they *do* fight the font option --
# the same collision that forced "bold_italic" to exist. Every combination of
# weight, slant, size and family therefore resolves to one composite tag; see
# font_tag_for. They are stored as separate spans regardless, so the four
# properties stay independent in the note and only meet at render time.
FONT_VALUE_STYLES = {"font_size", "font_family"}

# Everything that carries a "value". Kept as one name because most callers
# only need to know whether a span has one, not what kind.
VALUE_FORMAT_STYLES = COLOR_FORMAT_STYLES | FONT_VALUE_STYLES

# A curated list rather than whatever the machine happens to have installed.
# Notes travel -- as share codes, as backups, between machines -- and a font
# the reader does not have is silently swapped by Tk for something else, with
# nothing to say the note is no longer showing what it was written in. These
# ship with every Windows install.
FONT_FAMILIES = (
    "Segoe UI",
    "Arial",
    "Calibri",
    "Georgia",
    "Times New Roman",
    "Verdana",
    "Consolas",
    "Courier New",
)

# Columns can only line up in a face where every character is the same
# width. Both of these ship with Windows; the first the system actually has
# is the one used, and a table falls back to the note's own font rather than
# to something the reader does not have.
# Windows first (Consolas ships everywhere the app does), then the
# families a Linux CI runner actually has -- without them the table
# face silently fell back to the editor's proportional font there.
MONOSPACE_FAMILIES = ("Consolas", "Courier New", "DejaVu Sans Mono",
                      "Liberation Mono", "Noto Sans Mono", "Ubuntu Mono",
                      "Courier")

FONT_SIZES = (9, 10, 11, 12, 14, 16, 20, 24)

# The most styling spans one note may carry — an anti-bomb ceiling, NOT a
# performance promise. A crafted share code with 100,000 spans is a few KB
# of pasteable text; saved first and re-rendered on every launch, it was
# the same make-the-app-unopenable class as the checklist bomb, one field
# over. The ceiling sits far above real content (measured: a 3,000-char
# body wearing 10,000 spans still opens in ~4 s on a fast machine —
# unpleasant, alive), because a Word-paste of a long styled document
# produces THOUSANDS of legitimate spans and truncating those would be
# visible data corruption. What the ceiling deliberately does not fix,
# recorded in docs/archive/COVERAGE_LEDGER.md, not papered over: the editor
# reads formatting back 5-6 times per note-open, each read costs
# O(ranges x body length), and a single-line body with a few thousand
# spans hangs Tk's layout below ANY sane cap.
MAX_FORMATTING_SPANS = 10000

# How much styling may pile onto ONE LINE.
#
# MAX_FORMATTING_SPANS above counts a whole note and is set high on
# purpose, so it cannot be the defence here: what makes Tk give up is not
# how many spans a note carries but how many tagged ranges land on a
# single line. Measured on this app, opening one note (3,000-char body):
#
#     2,000 spans spread over 10 lines ......... 0.28 s
#     2,000 spans on ONE line .................. did not finish in 75 s
#       500 overlapping spans on one line ...... 0.30 s
#     1,000 overlapping spans on one line ...... did not finish in 75 s
#       500 on one line + 500 crossing it ...... 1.07 s
#
# Two shapes hang, and neither is exotic: short overlapping spans of
# different colours or sizes piled on one line, and spans that each run
# from somewhere in the body to its end, so they all lie over the last
# line without starting on it. Both fit inside a share code of a few
# kilobytes, and a pasted note is SAVED before it is ever drawn -- so
# such a note took the app down on every launch after, exactly the
# make-the-app-unopenable class as the checklist bomb.
#
# Hence two budgets, because one alone is walked straight through:
#
# * MAX_SPANS_PER_LINE bounds how many spans may COVER any one line --
#   counted by coverage, not by where a span starts. Counting starts was
#   the first version of this clamp, and a note whose spans each began on
#   a different line and ran to the END of the body dodged it completely:
#   five spans started on any given line, and the last line wore all
#   2,000. It still did not finish in 75 s.
# * MAX_LINE_RANGES bounds the note's TOTAL, because per-line alone is
#   not enough either: 500 spans over a 400-line body is only 500 spans,
#   under any per-line ceiling, and still asks Tk for 200,000 ranges.
#
# The pair is pinned to the last measured-alive row above: 500 covering
# one line and 20,000 in total is exactly that 1.07 s note. Real notes
# are nowhere near -- 300 bold words across 300 lines is 300 ranges, and
# a heavily styled long document a few thousand.
MAX_SPANS_PER_LINE = 500
MAX_LINE_RANGES = 20000


def _is_valid_hex_color(value):
    return (isinstance(value, str) and len(value) == 7 and value[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in value[1:]))


def clamp_spans_per_line(body, spans):
    """Drop the styling spans that would pile too deep on one line.

    Takes an ALREADY-normalized span list plus the body those offsets
    point into, and returns it unchanged unless one of the two budgets
    above is broken -- which no note a person writes can do. See
    MAX_SPANS_PER_LINE for the measurements, and for why one budget is
    per line and the other covers the whole note.

    Trimming here rather than at the point the spans are drawn is
    deliberate: the editor reads a note's formatting back OUT of the text
    widget when it saves, so a note drawn without its tags would be saved
    without its spans. Refusing the data at the door keeps that
    round-trip honest -- what is kept is what is shown is what is saved.
    """
    if not isinstance(spans, list) or not spans or not isinstance(body, str):
        return spans if isinstance(spans, list) else []
    if len(spans) <= MAX_SPANS_PER_LINE and "\n" not in body:
        return spans            # one line, too few spans to break either
    breaks = [i for i, ch in enumerate(body) if ch == "\n"]
    if not breaks:
        return spans[:MAX_SPANS_PER_LINE]        # one line, one budget
    kept, covered, drawn = [], {}, 0
    # Lines already carrying their full share, kept sorted so a span can
    # ask "do I touch one?" without walking its whole range. That answer
    # is what keeps this loop linear: a span either is refused in one
    # lookup, or it is cheap to count because none of its lines are full.
    full = []
    for span in spans:
        start = span["start"]
        first = bisect.bisect_left(breaks, start)
        last = bisect.bisect_left(breaks, max(start, span["end"] - 1))
        width = last - first + 1
        if drawn + width > MAX_LINE_RANGES:
            continue
        at = bisect.bisect_left(full, first)
        if at < len(full) and full[at] <= last:
            continue                 # crosses a line that has its fill
        for line in range(first, last + 1):
            seen = covered.get(line, 0) + 1
            covered[line] = seen
            if seen >= MAX_SPANS_PER_LINE:
                bisect.insort(full, line)
        drawn += width
        kept.append(span)
    return kept


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
        elif style in COLOR_FORMAT_STYLES and _is_valid_hex_color(span.get("value")):
            spans.append({"start": start, "end": end, "style": style,
                          "value": span["value"].lower()})
        elif style == "font_size":
            size = span.get("value")
            # Only sizes the app offers. An arbitrary number would render
            # fine but could never be shown as selected in the picker, and a
            # note is not the place to discover a size you cannot get back to.
            if isinstance(size, int) and not isinstance(size, bool) \
                    and size in FONT_SIZES:
                spans.append({"start": start, "end": end, "style": style,
                              "value": size})
        elif style == "font_family":
            family = span.get("value")
            if isinstance(family, str) and family in FONT_FAMILIES:
                spans.append({"start": start, "end": end, "style": style,
                              "value": family})
        if len(spans) >= MAX_FORMATTING_SPANS:
            # See MAX_FORMATTING_SPANS above: a bomb ceiling at the one
            # choke point every route passes through, generous enough
            # that no real document ever reaches it.
            break
    return _fold_bold_with_italic(spans)[:MAX_FORMATTING_SPANS]


def _fold_bold_with_italic(spans):
    """Where a bold span and an italic span cover the same characters, one
    bold_italic span there instead: the two are Tk tags that both set the
    font, which do not compose, and italic -- made after bold -- won. Bold
    italic text pasted from a web page, or from the app's own copy (which
    writes it as <i><b>), was drawn italic alone, on every open, while the
    toolbar lit Bold and the note saved it bold.

    One sweep over the two styles' ends, and the list as it was when
    nothing overlaps. When something does, the list comes back in the
    order the editor reads spans back in (merge_spans): the folded pieces
    put after the rest made a note saved the old way differ from its own
    reading at once -- unsaved, and saved again on leaving with no edit,
    its "Last updated" moved."""
    marks = sorted((s[edge], s["style"], step)
                   for s in spans if s["style"] in ("bold", "italic")
                   for edge, step in (("start", 1), ("end", -1)))
    held = {"bold": 0, "italic": 0}
    pieces, overlap, i = [], False, 0
    while i < len(marks):
        at = marks[i][0]
        while i < len(marks) and marks[i][0] == at:
            held[marks[i][1]] += marks[i][2]
            i += 1
        if i == len(marks):
            break
        style = ("bold_italic" if held["bold"] and held["italic"]
                 else "bold" if held["bold"] else
                 "italic" if held["italic"] else None)
        overlap = overlap or style == "bold_italic"
        if style is None:
            continue
        if (pieces and pieces[-1]["end"] == at
                and pieces[-1]["style"] == style):
            pieces[-1]["end"] = marks[i][0]
        else:
            pieces.append({"start": at, "end": marks[i][0], "style": style})
    if not overlap:
        return spans
    return sorted([s for s in spans if s["style"] not in ("bold", "italic")]
                  + pieces, key=lambda s: (s["start"], s["end"], s["style"]))


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


def font_tag_for(is_bold, is_italic, size=None, family=None):
    """The single tag carrying this whole font combination, or None.

    Two Tk tags that both set the widget's font option do not compose -- one
    simply wins -- which is why bold and italic together needed a compound
    tag rather than two independent ones. Size and family set the same
    option, so all four have to resolve to one name.

    With neither size nor family the historic names are returned unchanged,
    so notes written before this existed keep tagging exactly as they did,
    and the plain "bold" tag stays the one the toolbar reads.
    """
    if size is None and family is None:
        if is_bold and is_italic:
            return "bold_italic"
        if is_bold:
            return "bold"
        if is_italic:
            return "italic"
        return None
    # Slugged so the name survives being a Tk tag: spaces separate tag names
    # in some Tk calls, and a family like "Times New Roman" has two.
    slug = (family or "-").replace(" ", "+")
    return f"font_{slug}_{size or '-'}_{int(bool(is_bold))}{int(bool(is_italic))}"


def resolve_font_runs(spans, text_length):
    """Work out where a composite font tag is needed, and which one.

    Returns ``(start, end, is_bold, is_italic, size, family)`` for each run
    that carries a size or a family, weight and slant folded in from
    whatever bold/italic spans cover the same characters.

    Only those runs. Bold on its own still uses the plain "bold" tag, which
    keeps two things true: a note that never touches size or family tags
    exactly as it always did, and the toolbar can go on asking "is this
    range bold?" by looking for that tag.

    One sweep over the span boundaries, in order, carrying what covers the
    stretch to the next one. Every span used to be checked at every
    boundary: one font size in a note of 8,000 styled words cost 1.7 s at
    every open, every Enter in a numbered list and every font change.
    """
    spans = normalize_formatting(spans)
    affects_font = {"bold", "italic", "bold_italic"} | FONT_VALUE_STYLES
    relevant = [s for s in spans if s["style"] in affects_font]
    if not any(s["style"] in FONT_VALUE_STYLES for s in relevant):
        return []

    # Every span boundary is a point where the answer can change; between
    # two consecutive boundaries it cannot.
    marks = {0, text_length}
    starting, ending = {}, {}
    for index, span in enumerate(relevant):
        marks.add(span["start"])
        marks.add(span["end"])
        starting.setdefault(span["start"], []).append(index)
        ending.setdefault(span["end"], []).append(index)
    points = sorted(m for m in marks if 0 <= m <= text_length)

    # What covers the stretch from one boundary to the next: how many bold
    # and italic spans, and the sizes and families as heaps on their place
    # in the list -- the last one listed wins, as when every span was
    # checked in turn. One that ended is let go when it reaches the top.
    bold = italic = 0
    sizes, families = [], []
    runs = []
    for start, end in zip(points, points[1:]):
        for index in ending.get(start, ()):
            style = relevant[index]["style"]
            bold -= style in ("bold", "bold_italic")
            italic -= style in ("italic", "bold_italic")
        for index in starting.get(start, ()):
            span = relevant[index]
            style = span["style"]
            bold += style in ("bold", "bold_italic")
            italic += style in ("italic", "bold_italic")
            if style in FONT_VALUE_STYLES:
                heapq.heappush(sizes if style == "font_size" else families,
                               (-index, span["end"], span["value"]))
        for heap in (sizes, families):
            while heap and heap[0][1] <= start:
                heapq.heappop(heap)
        size = sizes[0][2] if sizes else None
        family = families[0][2] if families else None
        if size is not None or family is not None:
            runs.append((start, end, bold > 0, italic > 0, size, family))

    # Neighbouring runs that came out identical were split by a boundary
    # belonging to some other span; joining them keeps the widget holding one
    # tag range instead of several touching ones.
    merged = []
    for run in runs:
        if merged and merged[-1][1] == run[0] and merged[-1][2:] == run[2:]:
            merged[-1] = (merged[-1][0], run[1]) + run[2:]
        else:
            merged.append(run)
    return merged


def split_toolbar_rows(items, available, max_rows=3):
    """Deal toolbar controls into rows no wider than *available*.

    *items* is ``[(width, is_divider), ...]`` in the order they appear;
    the result is a list of rows, each holding indices into *items*.

    Pure arithmetic, deliberately: which control lands on a row boundary
    depends entirely on the font, so testing this through real widgets
    tests whatever font the machine happens to have. The bug this exists
    to prevent -- a divider making its row too wide -- showed up on a CI
    runner and not on the machine it was written on, purely for that
    reason.

    A divider that falls at a row break is dropped rather than carried
    over. Starting a row with a vertical rule reads as a mistake, and
    keeping it on the row it overflowed is what made that row too wide.

    The last row takes whatever is left even if it no longer fits: there
    is nowhere else to put it, and a control that is hard to reach is
    still better than one that is not there at all.
    """
    rows, used, index = [[]], 0, 0
    for i, (width, is_divider) in enumerate(items):
        if used and used + width > available and index < max_rows - 1:
            index += 1
            rows.append([])
            used = 0
        # Stated once, as a property of the row rather than of the break:
        # checking it only at the break missed the case where a divider was
        # dropped there and the *next* divider then found an empty row and
        # opened it.
        if is_divider and index and not rows[index]:
            continue
        rows[index].append(i)
        used += width
    return rows


def merge_spans(spans):
    """Join spans that touch and say the same thing.

    Reading the widget back gives one span per tag range, and a composite
    font tag is split wherever bold or italic starts or stops inside it --
    so a single size across a paragraph can come back as three or four
    pieces. Left alone they would be written to the note that way, and split
    again a little further on the next save.
    """
    by_style = {}
    for span in spans:
        by_style.setdefault((span["style"], span.get("value")), []).append(span)
    merged = []
    for (style, value), group in by_style.items():
        group.sort(key=lambda s: (s["start"], s["end"]))
        current = dict(group[0])
        for span in group[1:]:
            if span["start"] <= current["end"]:
                current["end"] = max(current["end"], span["end"])
            else:
                merged.append(current)
                current = dict(span)
        merged.append(current)
    return sorted(merged, key=lambda s: (s["start"], s["end"], s["style"]))


def parse_font_tag(name):
    """Turn a composite font tag name back into its four properties.

    Returns ``(is_bold, is_italic, size, family)``, or None if *name* is not
    one. The inverse of :func:`font_tag_for`, so saving can decompose what
    rendering composed -- the note stores the four properties separately and
    only the widget ever sees them merged.
    """
    if not isinstance(name, str) or not name.startswith("font_"):
        return None
    try:
        slug, size, flags = name[len("font_"):].rsplit("_", 2)
    except ValueError:
        return None
    if len(flags) != 2 or not set(flags) <= {"0", "1"}:
        return None
    family = slug.replace("+", " ")
    if family == "-":
        family = None
    elif family not in FONT_FAMILIES:
        return None
    if size == "-":
        size = None
    else:
        try:
            size = int(size)
        except ValueError:
            return None
        if size not in FONT_SIZES:
            return None
    return flags[0] == "1", flags[1] == "1", size, family
    return None


def tag_to_spans(tag, start, end):
    """The note spans one format tag stands for over [start, end).

    A plain style keeps its name, a colour tag gives its style and hex, and
    a composite font tag its size and family -- its weight and slant ride
    their own tags, which is how the editor reads them back too.
    """
    if end <= start or not is_format_tag(tag):
        return []
    if tag in KNOWN_FORMAT_STYLES:
        return [{"start": start, "end": end, "style": tag}]
    for style in COLOR_FORMAT_STYLES:
        if tag.startswith(style + "_"):
            return [{"start": start, "end": end, "style": style,
                     "value": "#" + tag[len(style) + 1:]}]
    _bold, _italic, size, family = parse_font_tag(tag)
    spans = []
    if size is not None:
        spans.append({"start": start, "end": end, "style": "font_size",
                      "value": size})
    if family is not None:
        spans.append({"start": start, "end": end, "style": "font_family",
                      "value": family})
    return spans


def is_format_tag(name):
    """True for a Tk tag that carries CHARACTER formatting.

    A plain style, a colour (``text_color_``/``highlight_`` and a valid
    hex), or a composite font -- exactly the tags the editor reads back as
    the note's spans. The one answer for code that has to move or restore
    formatting tag by tag instead of through the span list; a tag list
    written out by hand at each such place is how a new kind of tag gets
    carried by one of them and silently dropped by the next.
    """
    if not isinstance(name, str):
        return False
    if name in KNOWN_FORMAT_STYLES:
        return True
    for style in COLOR_FORMAT_STYLES:
        prefix = style + "_"
        if name.startswith(prefix):
            return _is_valid_hex_color("#" + name[len(prefix):])
    return parse_font_tag(name) is not None


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
# One glyph per nesting level, cycling past the third. All three are ones
# nobody types by accident, which is what lets a bullet be recognised from
# the text alone.
BULLET_GLYPHS = ("•", "◦", "▪")
_NUMBER_RE = re.compile(r"^(\d+)\. ")
LIST_KINDS = ("bullet", "number")

# How deep a paragraph may be pushed. A cap at all is what stops a held-down
# Tab from marching text off the right-hand edge of the editor.
MAX_INDENT = 8

# Alignment is a property of the whole line, so it lives here beside the
# list kinds rather than among the character styles. "left" is the default
# and is never stored -- see normalize_paragraphs.
ALIGNMENTS = ("left", "center", "right")


def parse_list_marker(line):
    """Split a line into ``(kind, marker, rest)``.

    Returns ``(None, "", line)`` for a line that is not a list item.
    """
    for glyph in BULLET_GLYPHS:
        if line.startswith(glyph + " "):
            return "bullet", glyph + " ", line[len(glyph) + 1:]
    m = _NUMBER_RE.match(line)
    if m:
        return "number", m.group(0), line[m.end():]
    return None, "", line


def strip_list_markers(text):
    """Remove anything this app would read back as a list marker.

    Needed by "paste without formatting". A marker in the text is what
    makes a line a list line here, and a source that writes its own bullets
    into the plain-text copy it offers -- many do -- would otherwise give
    exactly the formatted result that was asked to be left behind.

    Only markers this app recognises are removed. A line starting "- " or
    "* " keeps them: they are the writer's characters, and they were never
    going to become a list.
    """
    lines = []
    for line in (text or "").split("\n"):
        kind, _marker, rest = parse_list_marker(line.lstrip(" \t"))
        lines.append(rest if kind else line)
    return "\n".join(lines)


# U+FE0F asks for an emoji's colour form. Tk has no colour emoji, and draws
# the character itself as a blank two letters wide right after the emoji.
VARIATION_SELECTOR = "\ufe0f"


def without_variation_selector(text):
    """*text* without the emoji variation selector, which only leaves a gap."""
    return (text or "").replace(VARIATION_SELECTOR, "")


def bullet_level_of(marker):
    """Which nesting level a bullet marker's glyph stands for, or 0.

    Only meaningful for bullets. Numbered levels are told apart by their
    indent, not by their marker -- see :func:`marker_for`.
    """
    glyph = marker.strip()
    return BULLET_GLYPHS.index(glyph) if glyph in BULLET_GLYPHS else 0


def marker_for(kind, number=1, level=0):
    """The text a list line of this kind and depth starts with.

    Bullets change glyph with depth, which is free: the three glyphs are
    ones nobody types by accident, so a line starting with one is a bullet
    beyond doubt.

    Numbers deliberately do not. The obvious nested scheme -- 1. then a.
    then i. -- is genuinely ambiguous with ordinary prose, and a note is
    exactly the kind of document where a line can legitimately begin "a. "
    or "i. ". Depth is shown by indentation and by the count restarting
    under each parent instead, which costs nothing and cannot misfire.
    """
    if kind == "bullet":
        return BULLET_GLYPHS[level % len(BULLET_GLYPHS)] + " "
    return f"{number}. "


def normalize_paragraphs(value, line_count=None):
    """Drop anything that is not a usable paragraph entry.

    The same gatekeeper idea as :func:`normalize_formatting`: one bad entry
    from an old file or hand-edited JSON should be discarded, not repaired
    into something that half-works.

    Only non-default properties are kept, so a line that is a plain,
    left-aligned paragraph produces no entry at all rather than a row of
    defaults in every note's JSON.
    """
    if not isinstance(value, list):
        return []
    clean, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            continue
        line = item.get("line")
        if not isinstance(line, int) or line < 0:
            continue
        if line_count is not None and line >= line_count:
            continue
        if line in seen:            # one set of properties per line
            continue

        kind = item.get("kind")
        if kind not in LIST_KINDS:
            kind = None
        align = item.get("align")
        if align not in ALIGNMENTS:
            align = "left"
        indent = item.get("indent")
        if not isinstance(indent, int) or isinstance(indent, bool) or indent < 0:
            indent = 0
        indent = min(indent, MAX_INDENT)

        if kind is None and align == "left" and indent == 0:
            continue                # nothing worth recording

        seen.add(line)
        entry = {"line": line}
        if kind:
            entry["kind"] = kind
        if indent:
            entry["indent"] = indent
        if align != "left":
            entry["align"] = align
        clean.append(entry)
    return sorted(clean, key=lambda b: b["line"])


def renumber(body, paragraphs):
    """Make every numbered run read 1, 2, 3 from its own start.

    A run ends at any line that is not a numbered item -- a blank line, a
    paragraph, or a bullet -- so two numbered lists separated by text each
    start again at one, which is what a person writing them expects.

    Returns ``(body, shift)``: the rewritten body, and a list of
    ``(offset, delta)`` describing where characters were inserted or removed,
    so the caller can move formatting spans to match.

    Nesting keeps one counter per level. Going deeper starts that level from
    one again on every parent, so the second item's sub-list reads 1, 2, 3
    rather than carrying on from the first item's. Coming back out resumes
    the shallower count where it left off.
    """
    lines = body.split("\n")
    by_line = {b["line"]: b
               for b in normalize_paragraphs(paragraphs, len(lines))}
    shifts, counters, pos, blanks = [], {}, 0, 0
    for i, line in enumerate(lines):
        entry = by_line.get(i) or {}
        kind = entry.get("kind")
        level = entry.get("indent", 0)
        if kind == "number":
            blanks = 0
            counters[level] = counters.get(level, 0) + 1
            # Anything deeper belongs to the item that just ended, so it
            # starts again under this one.
            for deeper in [lv for lv in counters if lv > level]:
                del counters[deeper]
            _, old_marker, rest = parse_list_marker(line)
            new_marker = marker_for("number", counters[level], level)
            if old_marker != new_marker:
                delta = len(new_marker) - len(old_marker)
                if delta:
                    # Only a change in marker *length* moves later text.
                    # "1." -> "2." rewrites a character without shifting
                    # anything, and recording it would be noise the caller
                    # then has to loop over for nothing.
                    shifts.append((pos, delta))
                lines[i] = new_marker + rest
        elif kind == "bullet":
            # A bullet interrupts numbering at its own depth and below, but
            # leaves an outer numbered list alone: a bulleted aside inside
            # item 2 should not restart the outer count at 1.
            blanks = 0
            for lv in [lv for lv in counters if lv >= level]:
                del counters[lv]
        elif line.strip():
            blanks = 0
            counters.clear()
        else:
            # One blank line does not end a list. People space their items
            # out, and restarting there numbered such a list 1, 1, 1. Two
            # blank lines do end it, which is how a genuinely new list is
            # told apart from a spaced-out one.
            blanks += 1
            if blanks > 1:
                counters.clear()
        pos += len(lines[i]) + 1        # +1 for the newline
    return "\n".join(lines), shifts


def list_deletion_range(lines, start, end, typing=False):
    """Where a deletion should fall when it reaches a list, or None.

    A list's marker is characters, and the editor's own deletes saw only
    characters: two lines joined kept the second one's marker among the
    words ("2. two3. three"), typing over whole items swallowed the next
    item's marker ("x4. four"), and a marker selected and deleted took one
    character of it, or all, and nothing renumbered. The answer is Word's,
    where a marker is no character at all:

    - two lines joined keep the first one's marker, and the second one's
      goes -- unless nothing of the first line is kept, when the second one
      simply takes its place, marker and all;
    - typing over a selection that ends at an item's start keeps that
      item, number and all, and what is typed takes the selection's place;
    - a deletion from just after a marker keeps it, and one reaching into
      a marker takes the whole marker, so the line stops being an item
      rather than keeping a broken one.

    *lines* are the body's lines; *start* and *end* are ``(line, column)``,
    lines from 0, columns in characters -- what the key would delete.
    *typing*: the selection is being typed over. Returns the
    ``(start, end)`` to delete instead, unchanged when only the numbering
    needs mending, or None when no list is touched. The caller renumbers.
    """
    (l1, c1), (l2, c2) = start, end
    k1, m1, _ = parse_list_marker(lines[l1])
    if l1 == l2:
        # Within one line only its own marker can be reached.
        if not k1 or c1 >= len(m1):
            return None
        return (l1, 0), (l2, max(c2, len(m1)))
    k2, m2, _ = parse_list_marker(lines[l2])
    if not (k1 or k2 or any(parse_list_marker(lines[n])[0]
                            for n in range(l1 + 1, l2))):
        return None
    keeps_words = c1 > (len(m1) if k1 else 0)
    if k2 and c2 <= len(m2):
        # The end is at the start of an item, before its words.
        if keeps_words:
            return (l1, c1), (l2, len(m2))
        if typing:
            return (l1, len(m1) if k1 else 0), (l2 - 1, len(lines[l2 - 1]))
        return (l1, 0), (l2, 0)
    if k1 and 0 < c1 <= len(m1):
        # From just after (or inside) a marker into words: the item keeps
        # its marker. From the line's very start the marker was chosen too,
        # and goes with the rest -- Ctrl+A and BackSpace empty the note.
        return (l1, len(m1)), (l2, c2)
    return (l1, c1), (l2, c2)


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
        # Every offset in *shifts* describes the text as it was, so each one
        # has to be judged against the span as it was. Adding the deltas one
        # at a time and comparing against the running total counted a later
        # shift as being "before" a span it had itself pushed past: with two
        # cells padded on one row, the bold in the first cell ended up in the
        # second. Renumbering never showed it, because a line rarely has more
        # than one marker widening before the same word.
        moved = dict(span)
        moved["start"] = start + sum(d for at, d in shifts if at < start)
        moved["end"] = end + sum(d for at, d in shifts if at < end)
        out.append(moved)
    return out
