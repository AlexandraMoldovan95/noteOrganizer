"""How rich-text formatting is stored on a note, and kept sane.

A note's ``formatting`` is a flat list of spans --
``{"start": 0, "end": 5, "style": "bold"}``, a colour or a font with a
``value`` -- whose offsets are CHARACTERS into the body, not Tk's
line.column, so they survive JSON, share codes and a window wrapped
differently. :func:`normalize_formatting` is the gatekeeper: a span that is
not valid is dropped, never repaired. Three kinds of style: on/off, colour
(a hex value) and font (a size or family from the app's own lists). The
walk through it is in docs/CODE_TOUR.md.
"""

import bisect
import heapq
import re

# Tk tags that both set the font do not compose -- one wins -- so bold and
# italic together are one style, as a real font has its own bold italic.
KNOWN_FORMAT_STYLES = {"bold", "italic", "bold_italic", "underline", "strike"}

# A hex colour in "value": foreground and background are separate Tk tag
# options, so these two need no compound tag.
COLOR_FORMAT_STYLES = {"text_color", "highlight"}

# Size and family DO fight the font, so each combination with weight and
# slant is one composite tag (font_tag_for); stored as separate spans, they
# meet only when drawn.
FONT_VALUE_STYLES = {"font_size", "font_family"}

# Curated, not what this machine has: notes travel, and a font the reader
# lacks is silently swapped. These ship with every Windows install.
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

# A table's columns line up only in a fixed-width face: the first one the
# system has -- Windows' first, then a Linux CI runner's, where the table
# fell back to the proportional font.
MONOSPACE_FAMILIES = ("Consolas", "Courier New", "DejaVu Sans Mono",
                      "Liberation Mono", "Noto Sans Mono", "Ubuntu Mono",
                      "Courier")

FONT_SIZES = (9, 10, 11, 12, 14, 16, 20, 24)

# The most spans one note may carry: an anti-bomb ceiling, not a speed
# promise -- far above a long styled Word paste, which truncated would be
# corruption. How the ceilings were measured: docs/ARCHITECTURE.md.
MAX_FORMATTING_SPANS = 10000

# What Tk pays for is tagged ranges on ONE line and drawn in all: spans
# COVERING a line (not starting on it), and the note's total -- pinned to
# the last measured-alive note (ISSUES_LOG: "The ceiling that counted the wrong thing").
MAX_SPANS_PER_LINE = 500
MAX_LINE_RANGES = 20000


def _is_valid_hex_color(value):
    return (isinstance(value, str) and len(value) == 7 and value[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in value[1:]))


def clamp_spans_per_line(body, spans):
    """Drop the styling spans that would pile too deep on one line.

    An ALREADY-normalized list and its body in; unchanged unless one of the
    two budgets above is broken, which no written note does. Trimmed here,
    not where spans are drawn: the save reads formatting back out of the
    widget, so what is kept is what is shown is what is saved.
    """
    if not isinstance(spans, list) or not spans or not isinstance(body, str):
        return spans if isinstance(spans, list) else []
    if len(spans) <= MAX_SPANS_PER_LINE and "\n" not in body:
        return spans            # one line, too few spans to break either
    breaks = [i for i, ch in enumerate(body) if ch == "\n"]
    if not breaks:
        return spans[:MAX_SPANS_PER_LINE]        # one line, one budget
    kept, covered, drawn = [], {}, 0
    # Lines at their full share, sorted: a span asks "do I touch one?" in one
    # lookup, which keeps the loop linear.
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
    non-integer offsets, for text_color/highlight a missing or invalid hex
    value, for a size or family one not in FONT_SIZES / FONT_FAMILIES)
    rather than ever letting bad data crash the editor."""
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
    """Where bold and italic spans cover the same characters, one
    bold_italic span there instead: as two font tags, italic won, and pasted
    bold italic was drawn italic alone. Unchanged when nothing overlaps;
    otherwise in merge_spans' order, or a note read back differed from its
    own save and its "Last updated" moved with no edit."""
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
# Pure string work, beside the span format they name rather than in the editor.

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
    """The single tag carrying this whole font combination, or None: weight,
    slant, size and family all set Tk's one font option, so they resolve to
    one name. With neither size nor family, the plain names, so older notes
    tag as they did and "bold" stays the tag the toolbar reads.
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
    """Where a composite font tag is needed, and which one: ``(start, end,
    is_bold, is_italic, size, family)`` for each run carrying a size or a
    family, weight and slant folded in. Bold alone keeps the plain tag.
    One sweep over the span boundaries -- every span checked at every one
    cost 1.7 s an open on 8,000 styled words.
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

    # What covers each stretch: bold and italic counted, sizes and families
    # as heaps on their place in the list (the last listed wins); one that
    # ended is let go when it reaches the top.
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
    """Deal toolbar controls, ``[(width, is_divider), ...]``, into rows no
    wider than *available*: a list of rows of indices into *items*. Pure
    arithmetic, as through widgets it tested the machine's font. A divider
    at a break is dropped, not carried; the last row takes what is left,
    as a control hard to reach beats one that is not there.
    """
    rows, used, index = [[]], 0, 0
    for i, (width, is_divider) in enumerate(items):
        if used and used + width > available and index < max_rows - 1:
            index += 1
            rows.append([])
            used = 0
        # A property of the row, not of the break: checked at the break, the
        # NEXT divider found the emptied row and opened it.
        if is_divider and index and not rows[index]:
            continue
        rows[index].append(i)
        used += width
    return rows


def merge_spans(spans):
    """Join spans that touch and say the same thing: read back, a composite
    font tag comes in pieces wherever bold or italic starts or stops inside
    it, and the pieces were saved that way, split further at every save.
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


def is_format_tag(name, fonts=True):
    """True for a Tk tag that carries CHARACTER formatting: a plain style, a
    colour with a valid hex, or a composite font -- the tags read back as
    spans. The one answer for code moving formatting tag by tag, as lists
    written out by hand dropped a new kind of tag. *fonts* False leaves the
    composite fonts out.
    """
    if not isinstance(name, str):
        return False
    if name in KNOWN_FORMAT_STYLES:
        return True
    for style in COLOR_FORMAT_STYLES:
        prefix = style + "_"
        if name.startswith(prefix):
            return _is_valid_hex_color("#" + name[len(prefix):])
    return fonts and parse_font_tag(name) is not None


# ---- Bullet and numbered lists ----
# A list line's marker is in the body ("• milk"), so offsets need no
# translation; ``paragraphs`` holds what a whole line is (CODE_TOUR).

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
    """Remove anything this app would read back as a list marker -- for
    "paste without formatting", as many sources write bullets into their
    plain text. "- " and "* " are the writer's, never a list, and stay.
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
    """The text a list line of this kind and depth starts with. Bullets
    change glyph with depth -- nobody types them by accident; numbers do
    not, as "a. " and "i. " begin ordinary lines: depth is the indent, and
    the count restarting under each parent.
    """
    if kind == "bullet":
        return BULLET_GLYPHS[level % len(BULLET_GLYPHS)] + " "
    return f"{number}. "


def normalize_paragraphs(value, line_count=None):
    """Drop anything that is not a usable paragraph entry -- discarded, not
    repaired, as :func:`normalize_formatting` does. Only non-default
    properties are kept: a plain left-aligned line has no entry at all.
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


def list_lines(paragraphs, body=None):
    """The list lines of *body*: each line starting with a list marker, its
    kind and the depth *paragraphs* give it (none when they give it to no
    such line). The one look a day of a series keeps of its own -- its text
    is plain, but a nested list's depth lives nowhere else (the owner's
    choice). Without *body*, the list entries as they are."""
    if not isinstance(body, str):
        return [{key: value for key, value in entry.items() if key != "align"}
                for entry in normalize_paragraphs(paragraphs) if entry.get("kind")]
    lines = body.split("\n")
    depth = {entry["line"]: (entry["kind"], entry.get("indent", 0))
             for entry in normalize_paragraphs(paragraphs, len(lines)) if entry.get("kind")}
    out = []
    for number, line in enumerate(lines):
        kind, marker, _rest = parse_list_marker(line)
        if kind:
            given = depth.get(number)
            # Given none, a bullet's glyph tells its level, as the editor reads it.
            indent = (given[1] if given and given[0] == kind
                      else bullet_level_of(marker) if kind == "bullet" else 0)
            entry = {"line": number, "kind": kind}
            if indent:
                entry["indent"] = indent
            out.append(entry)
    return out


def day_paragraphs(paragraphs, body, same_body, own=None):
    """The lines' looks a day of a series shows, *body* the day's text: the
    series' *paragraphs* while the day shows the series' words (*same_body*),
    its lists' depth its *own* when it keeps them; on text of its own, its
    own list lines, or -- a day saved before it kept them -- the series' list
    entries, by line (ISSUES_LOG: "The lows wave: a fuzz that never took the
    road it guarded")."""
    body = body or ""
    if not same_body:
        return list_lines(paragraphs if own is None else own, body)
    looks = {entry["line"]: entry for entry in normalize_paragraphs(paragraphs, len(body.split("\n")))}
    for entry in list_lines(own, body) if own is not None else ():
        looks[entry["line"]] = dict(looks.get(entry["line"], {}), **entry)
        if "indent" not in entry:
            looks[entry["line"]].pop("indent", None)
    return [looks[line] for line in sorted(looks)]


def renumber(body, paragraphs):
    """Make every numbered run read 1, 2, 3 from its own start: a run ends at
    a paragraph, a bullet at its depth, or two blank lines. One counter per
    level, a deeper one starting again under each parent. Returns ``(body,
    shift)``, *shift* the ``(offset, delta)`` of each marker that changed
    length, for the caller to move the spans by.
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
                    # Only a change of length moves later text; "1." -> "2."
                    # shifts nothing.
                    shifts.append((pos, delta))
                lines[i] = new_marker + rest
        elif kind == "bullet":
            # A bullet ends the count at its depth and below; a bulleted
            # aside inside item 2 leaves the outer count alone.
            blanks = 0
            for lv in [lv for lv in counters if lv >= level]:
                del counters[lv]
        elif line.strip():
            blanks = 0
            counters.clear()
        else:
            # One blank line does not end a list -- a spaced-out one read
            # 1, 1, 1 -- two do: that is a new list.
            blanks += 1
            if blanks > 1:
                counters.clear()
        pos += len(lines[i]) + 1        # +1 for the newline
    return "\n".join(lines), shifts


def list_deletion_range(lines, start, end, typing=False, pasted=None):
    """Where a deletion should fall when it reaches a list, or None -- Word's
    answer, where a marker is no character: lines joined keep the first
    one's marker; typing over a selection ending at an item's start keeps
    that item; a deletion reaching into a marker takes all of it
    (ISSUES_LOG: "The marker that was only characters").

    Args:
        lines: The body's lines.
        start, end: ``(line, column)``, from 0, in characters -- what the
            key would delete.
        typing: The selection is typed over; *pasted* is a paste's text.

    Returns:
        The ``(start, end)`` to delete instead, or None when no list is
        touched. The caller renumbers.
    """
    (l1, c1), (l2, c2) = start, end
    k1, m1, _ = parse_list_marker(lines[l1])
    # A paste bringing its own marker over a selection begun at a marker takes
    # that marker's place: kept, an item pasted over another read "3. 1. Milk".
    own = bool(pasted) and bool(parse_list_marker(pasted.split("\n", 1)[0])[0])
    from_marker = own and bool(k1) and c1 <= len(m1)
    if l1 == l2:
        # Within one line only its own marker can be reached.
        if not k1 or (c1 >= len(m1) and not from_marker):
            return None
        return (l1, 0), (l2, max(c2, len(m1)))
    k2, m2, _ = parse_list_marker(lines[l2])
    if not (k1 or k2 or any(parse_list_marker(lines[n])[0]
                            for n in range(l1 + 1, l2))):
        return None
    keeps_words = c1 > (len(m1) if k1 else 0)
    if k2 and c2 <= len(m2):
        # The end is at the start of an item, before its words. A paste
        # bringing its own line break takes the covered break's place: kept,
        # a whole item pasted over another left an empty line after it.
        upto = (l2, 0) if pasted and pasted.endswith("\n") else None
        if keeps_words:
            return (l1, c1), upto or (l2, len(m2))
        if typing:
            return ((l1, len(m1) if k1 and not own else 0),
                    upto or (l2 - 1, len(lines[l2 - 1])))
        return (l1, 0), (l2, 0)
    if k1 and 0 < c1 <= len(m1):
        # From just after (or inside) a marker into words: the item keeps
        # its marker. From the line's very start the marker was chosen too,
        # and goes with the rest -- Ctrl+A and BackSpace empty the note.
        return (l1, 0 if from_marker else len(m1)), (l2, c2)
    return (l1, c1), (l2, c2)


def shift_spans(spans, shifts):
    """Move formatting spans by the character shifts renumbering caused:
    "9. " made "10. " pushes every later character one along.
    """
    if not shifts:
        return spans
    # Every shift is judged against the text as it was: a running total read
    # a later shift as before a span it had pushed past (the first cell's
    # bold in the second). Summed off sorted totals, not walked per span.
    order = sorted(shifts)
    places = [at for at, _delta in order]
    totals = [0]
    for _at, delta in order:
        totals.append(totals[-1] + delta)
    out = []
    for span in spans:
        moved = dict(span)
        moved["start"] = span["start"] + totals[bisect.bisect_left(places, span["start"])]
        moved["end"] = span["end"] + totals[bisect.bisect_left(places, span["end"])]
        out.append(moved)
    return out
