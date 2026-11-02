"""Tables, as lines of text.

A table row really is the line ``| Milk | 2 |`` in the note's body, in the
same way a bullet really is the ``"• "`` at the start of its line. That is
not a shortcut: ``formatting`` stores character offsets into that same body,
so anything drawn on screen but absent from the text would put every offset
after it out by however wide the drawing was -- see ``docs/ARCHITECTURE.md``,
"The marker lives in the body text".

What follows from keeping it in the text:

* the note format does not change at all, so old notes, share codes, export
  and search keep working with no special case anywhere;
* a table survives being pasted into anything else as something still
  readable, which a grid of widgets would not;
* and re-padding a table rewrites real characters, which moves every offset
  after them -- the same problem ``renumber()`` already solves by returning
  its shifts for ``shift_spans()`` to apply. This module returns shifts in
  the same shape for the same reason.

Pipes rather than box-drawing characters, because prose does not begin with
one, which is what makes a row recognisable from its own text.

Nothing here imports tkinter: it turns strings into strings, so it can be
tested on any machine.
"""

import re

CELL = "|"
# A line break INSIDE a cell, as markdown itself writes one -- a table
# row must stay one line of text, so the break is a marker in the value.
# Export, share codes and any markdown-aware tool read it natively.
LINE_BREAK = "<br>"
# A cell holding exactly one of these IS a checkbox -- markdown's own
# task idiom, so the stored text stays plainly readable and any
# markdown-aware tool shows a task box. The app draws it as a real
# box and a click toggles it; opened, it shows empty, and what is
# typed there takes the box's place.
CHECKBOX_EMPTY = "[ ]"
CHECKBOX_DONE = "[x]"


def checkbox_state(value):
    """None when the cell is not a checkbox; False unchecked, True
    checked. Tolerates a capital X, which hand-written markdown uses."""
    v = (value or "").strip()
    if v == CHECKBOX_EMPTY:
        return False
    if v.lower() == CHECKBOX_DONE:
        return True
    return None


# A table's caption, as the app writes one under it: a numbered label --
# "Tab. N:" in notes from before the labels went English -- and the line
# its source goes on.
_CAPTION_LABEL = re.compile(r"(?:Table|Tab\.) \d+:")


def is_caption_line(line):
    """True for a caption's label line: "Table 3: ...". Prose that merely
    begins with the word is not one -- the number and colon are."""
    return bool(_CAPTION_LABEL.match((line or "").strip()))


def is_source_line(line):
    """True for the line a caption keeps its source on."""
    return (line or "").strip().startswith("Source:")
# A cell holding exactly one of these is not content but a merge marker:
# "<" belongs to the cell on its left, "^" to the cell above. Anchors sit
# at the top-left of their rectangle. Typing one of these alone into a cell
# genuinely means merging -- the same kind of accepted trade-off as "2."
# starting a numbered item.
MERGE_LEFT = "<"
MERGE_UP = "^"
# A row needs at least this much text to be worth calling a table. A line
# holding only pipes and spaces is a separator someone typed, not data.
_MIN_CELLS = 2


def is_table_row(line):
    """True if this line reads as a table row.

    Both ends must be a pipe. A sentence that merely contains one -- "a | b"
    in prose, a maths expression -- is not a row, and neither is a line that
    only opens with one.
    """
    stripped = (line or "").strip()
    if len(stripped) < 3 or not stripped.startswith(CELL):
        return False
    if not stripped.endswith(CELL):
        return False
    return len(split_row(stripped)) >= _MIN_CELLS


def cell_display_lines(value):
    """A cell's display lines: the value split on the ``<br>`` marker.

    The split is on the literal marker, so a cell without one is a
    single line and nothing changes for it.
    """
    return (value or "").split(LINE_BREAK)


def split_row(line):
    """The cells of a row, without their padding.

    ``"| Milk |   2 |"`` gives ``["Milk", "2"]``. The empty strings either
    side of the outer pipes are not cells and are dropped.
    """
    stripped = (line or "").strip()
    if not stripped.startswith(CELL):
        return []
    parts = stripped.split(CELL)
    # First and last are what sits outside the outer pipes: nothing.
    return [part.strip() for part in parts[1:-1]]


def cell_bounds(line):
    """Where each cell's text sits inside the row, as ``(start, end)``.

    Offsets into the line exactly as written, with the padding excluded, so
    formatting stored against the body can be carried across to the markup
    for one cell. Without this a bold word in a cell would be looked up at
    the wrong place once the row is split apart.
    """
    raw = line or ""
    lead = len(raw) - len(raw.lstrip())
    body = raw.strip()
    if not body.startswith(CELL) or not body.endswith(CELL):
        return []
    bounds, pos = [], lead + 1
    for part in body.split(CELL)[1:-1]:
        text = part.strip()
        if text:
            start = pos + (len(part) - len(part.lstrip()))
        else:
            # An empty cell is all padding, and skipping past it would put
            # the caret on the closing pipe -- outside the cell it is meant
            # to be in. One space in from the opening pipe is where typing
            # should start.
            start = pos + min(1, len(part))
        bounds.append((start, start + len(text)))
        pos += len(part) + 1
    return bounds


# No column is drawn narrower than this, however little is in it. A new
# table is all empty cells, and cells one character wide read as a row of
# specks rather than as something to type into -- and they lurch wider as
# soon as anything is typed. A floor costs a little width and makes an empty
# table look like the thing it is.
MIN_COLUMN = 8


ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT = "left", "center", "right"


def cell_alignments(line):
    """Per-cell alignment, read off the padding itself.

    Two or more spaces on both sides of the text is centred; two or more on
    the left alone is right-aligned; anything else -- including an empty
    cell -- is left. The padding is the store: no marker, no field, and a
    row hand-typed with its text against the left pipe means exactly what
    it looks like.
    """
    pipes = pipe_positions(line)
    aligns = []
    for i in range(len(pipes) - 1):
        segment = (line or "")[pipes[i] + 1:pipes[i + 1]]
        content = segment.strip()
        if not content:
            aligns.append(ALIGN_LEFT)
            continue
        lead = len(segment) - len(segment.lstrip(" "))
        trail = len(segment) - len(segment.rstrip(" "))
        if lead >= 2 and trail >= 2:
            aligns.append(ALIGN_CENTER)
        elif lead >= 2:
            aligns.append(ALIGN_RIGHT)
        else:
            aligns.append(ALIGN_LEFT)
    return aligns


def _padding_need(align):
    """Extra width a cell needs so its padding can say what it means:
    centre needs a spare space on each side, right needs one on the left."""
    if align == ALIGN_CENTER:
        return 2
    if align == ALIGN_RIGHT:
        return 1
    return 0


def layout_widths(rows, aligns=None):
    """Column widths honouring both content and each cell's padding need."""
    widths = []
    for r, row in enumerate(rows):
        for i, cell in enumerate(row):
            if i >= len(widths):
                widths.append(0)
            need = len(cell)
            if aligns and r < len(aligns) and i < len(aligns[r]):
                need += _padding_need(aligns[r][i])
            widths[i] = max(widths[i], need)
    return [max(MIN_COLUMN, w) for w in widths]


def column_widths(rows):
    """How wide each column has to be to hold every cell in it.

    Never narrower than MIN_COLUMN. Rows may be ragged -- a row with fewer
    cells than its neighbours is not an error, it is a row someone is still
    typing.
    """
    widths = []
    for row in rows:
        for i, cell in enumerate(row):
            if i >= len(widths):
                widths.append(0)
            widths[i] = max(widths[i], len(cell))
    return [max(MIN_COLUMN, w) for w in widths]


def format_row(cells, widths, aligns=None):
    """One row, padded so its columns line up under the widths given.

    The padding carries the alignment: extra space is dealt to the left,
    both sides, or the right of the text, and that layout is exactly what
    cell_alignments reads back.
    """
    padded = []
    for i, width in enumerate(widths):
        cell = cells[i] if i < len(cells) else ""
        align = (aligns[i] if aligns and i < len(aligns) else ALIGN_LEFT)
        extra = max(0, width - len(cell))
        if align == ALIGN_CENTER and cell:
            lead, trail = extra // 2, extra - extra // 2
        elif align == ALIGN_RIGHT and cell:
            lead, trail = extra, 0
        else:
            lead, trail = 0, extra
        padded.append(" " + " " * lead + cell + " " * trail + " ")
    return CELL + CELL.join(padded) + CELL


# Lining a table up pads every cell to its column's widest, so the padding is
# the widest cell times the rows: one 60,000-character cell over 3,500 rows
# made 210 million characters of a 162 KB paste (ISSUES_LOG: "Limits that held
# at the door but not after it"). Past this many spaces a table is left
# ragged instead: each cell keeps only the spaces its alignment needs, which
# is all the padding says, and the drawn grid, which sizes its columns from
# the cells, looks the same. The paste ceiling's number (MAX_PASTE_CHARS): a
# tidy adds no more than a whole paste may bring, and a table typed by hand
# never comes near it.
MAX_TABLE_PADDING = 100_000


def _padding_fits(rows, widths):
    """Whether padding *rows* to *widths* adds at most MAX_TABLE_PADDING
    spaces -- counted as format_row pads, every row given every column, so
    the count is never short of what either padder adds. Worked out from
    sums: a row's missing cells are not walked one by one."""
    kept = 0
    for row in rows:
        for i in range(min(len(row), len(widths))):
            kept += min(len(row[i]), widths[i])
    return len(rows) * sum(widths) - kept <= MAX_TABLE_PADDING


def row_widths(rows, widths, aligns=None):
    """The widths each row is padded to: *widths*, the columns', for every
    row while that padding fits MAX_TABLE_PADDING -- else each row its own,
    every cell as wide as its text and the spaces its alignment needs."""
    if _padding_fits(rows, widths):
        return [widths] * len(rows)
    out = []
    for r, row in enumerate(rows):
        mine = aligns[r] if aligns and r < len(aligns) else []
        out.append([len(cell) + _padding_need(mine[i] if i < len(mine)
                                              else ALIGN_LEFT)
                    for i, cell in enumerate(row)])
    return out


def format_table(rows, aligns=None):
    """A table's lines, every column as wide as its widest cell -- or, past
    MAX_TABLE_PADDING, every cell as wide as its own (row_widths)."""
    per_row = row_widths(rows, layout_widths(rows, aligns), aligns)
    return [format_row(row, per_row[r],
                       aligns[r] if aligns and r < len(aligns) else None)
            for r, row in enumerate(rows)]


def tidy_plan(lines):
    """What the editor's tidy pads one block's *lines* to -- every line a
    row, a separator's dashes measured like any cell -- as ``(each row's
    widths, each row's alignments)``, for pad_ops."""
    aligns = [cell_alignments(line) for line in lines]
    rows = [split_row(line) for line in lines]
    return row_widths(rows, layout_widths(rows, aligns), aligns), aligns


def tidied_length(lines):
    """How long the block *lines* is once the editor's tidy has padded it
    (tidy_plan), worked out without making the edits."""
    per_row, aligns = tidy_plan(lines)
    return len("\n".join(lines)) + sum(
        delta for i, line in enumerate(lines)
        for _at, delta in pad_ops(line, per_row[i], aligns[i]))


def table_length(rows, aligns=None):
    """``len("\\n".join(format_table(rows, aligns)))``, worked out without
    building it: a paste decides how much of a table fits before it makes
    any of it."""
    per_row = row_widths(rows, layout_widths(rows, aligns), aligns)
    total = max(0, len(rows) - 1)
    for r, row in enumerate(rows):
        total += 1 + sum(max(width, len(row[i]) if i < len(row) else 0) + 3
                         for i, width in enumerate(per_row[r]))
    return total


def longest_fitting(count, size_of, limit):
    """The largest *k* in 0..*count* whose ``size_of(k)`` is at most *limit*,
    found by halving: a paste is cut at its ceiling before any of it is
    built. 0 when not even one fits; ``size_of(0)`` is taken to fit."""
    if size_of(count) <= limit:
        return count
    low, high = 0, count - 1
    while low < high:
        mid = (low + high + 1) // 2
        if size_of(mid) <= limit:
            low = mid
        else:
            high = mid - 1
    return low


def pad_ops(line, widths, aligns=None):
    """The space edits that would line this row up, listed right to left.

    Each is ``(offset, delta)``: a positive delta inserts that many spaces at
    that offset in the line, a negative one deletes that many characters
    there. Right to left so applying one does not move the next one's offset.

    Editing the spaces rather than rewriting the line is what makes this
    usable in a widget. Tk moves a tag along with the text around it, so
    inserting a space beside a cell leaves the bold inside it exactly where
    it was; replacing the whole line would take the tags with it.

    *aligns* preserves each cell's stored alignment: the padding is dealt to
    the sides the alignment asks for, which is also how it is read back.
    """
    bounds = cell_bounds(line)
    if not bounds:
        return []
    raw = (line or "").rstrip()
    ops = []
    for i in range(len(bounds) - 1, -1, -1):
        start, end = bounds[i]
        width = widths[i] if i < len(widths) else (end - start)
        align = (aligns[i] if aligns and i < len(aligns) else ALIGN_LEFT)
        content = end - start
        extra = max(0, width - content)
        if align == ALIGN_CENTER and content:
            want_lead, want_trail = 1 + extra // 2, 1 + extra - extra // 2
        elif align == ALIGN_RIGHT and content:
            want_lead, want_trail = 1 + extra, 1
        else:
            want_lead, want_trail = 1, 1 + extra
        closing = raw.index(CELL, end)
        have_trail = closing - end
        if have_trail != want_trail:
            ops.append((end, want_trail - have_trail))
        opening = start - 1
        while opening >= 0 and raw[opening] != CELL:
            opening -= 1
        have_lead = start - opening - 1
        if have_lead != want_lead:
            ops.append((opening + 1, want_lead - have_lead))
    return ops


def pipe_positions(line):
    """Where the pipes sit in a row, for edits at a column boundary."""
    raw = line or ""
    if not is_table_row(raw):
        return []
    return [i for i, ch in enumerate(raw) if ch == CELL]


SEPARATOR_HIDDEN = "~"


def is_separator_row(line):
    """True for a markdown-style separator row: every cell is dashes with
    optional alignment colons, or the hidden marker."""
    if not is_table_row(line):
        return False
    cells = split_row(line)
    if not cells:
        return False
    for cell in cells:
        if cell == SEPARATOR_HIDDEN:
            continue
        body = cell
        if body.startswith(":"):
            body = body[1:]
        if body.endswith(":"):
            body = body[:-1]
        if not body or body.strip("-"):
            return False
    return True


def parse_separator(line):
    """Each column's mechanics, off the separator's own text.

    Returns a list of ``{"width", "align", "hidden"}`` -- width is the
    cell's content length (dashes and colons together), which is what keeps
    a regenerated separator the same width it was written at; align comes
    from the colons, or None where the author left the column to its cells.
    """
    columns = []
    for cell in split_row(line):
        if cell == SEPARATOR_HIDDEN:
            columns.append({"width": None, "align": None, "hidden": True})
            continue
        left = cell.startswith(":")
        right = cell.endswith(":")
        align = (ALIGN_CENTER if left and right
                 else ALIGN_RIGHT if right
                 else ALIGN_LEFT if left else None)
        # A minimum-width separator (bare "---", or ":-:" and friends —
        # anything three characters or fewer) is markdown's conventional
        # spelling, not an authored size: the wild writes it regardless
        # of content, and honouring it exactly clipped the drawn column
        # under its own text. A hand-dragged width is always wider. The
        # alignment colons still count; only the width opinion is waived.
        # The wild also writes "---:" and "|------|", longer than this:
        # those are spelled at the minimum as they are pasted in
        # (forget_widths), since only there is it known whose they are.
        width = len(cell) if len(cell) > 3 else None
        columns.append({"width": width, "align": align, "hidden": False})
    return columns


def make_separator(columns):
    """A separator's cells from parsed (or edited) column mechanics.

    The width is honoured exactly: the dash count IS the stored display
    width, so regenerating a separator never forgets a hand-dragged size.
    """
    cells = []
    for column in columns:
        if column.get("hidden"):
            cells.append(SEPARATOR_HIDDEN)
            continue
        width = max(3, column.get("width") or 3)
        align = column.get("align")
        if align == ALIGN_CENTER:
            cells.append(":" + "-" * max(1, width - 2) + ":")
        elif align == ALIGN_RIGHT:
            cells.append("-" * max(1, width - 1) + ":")
        elif align == ALIGN_LEFT:
            cells.append(":" + "-" * max(1, width - 1))
        else:
            cells.append("-" * width)
    return cells


def separator_index(lines):
    """Which line of a block is its separator, or None.

    Only the first counts, and only in the block's first two rows -- that
    is where markdown puts it, and a dashed line further down is far more
    likely to be content than mechanics.
    """
    for i, line in enumerate(lines[:2]):
        if is_separator_row(line):
            return i
    return None


def merge_map(rows):
    """Resolve merge markers into spans.

    Returns ``(spans, covered)``: ``spans[(r, c)] = (rowspan, colspan)`` for
    every anchor that spans more than one cell, and ``covered`` is the set
    of (r, c) positions swallowed by some anchor. A marker with nothing to
    attach to -- "<" in the first column, "^" in the first row -- is left
    alone as ordinary content rather than guessed at.
    """
    anchor_of = {}
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if value == MERGE_LEFT and c > 0:
                left = anchor_of.get((r, c - 1), (r, c - 1))
                if rows[left[0]][left[1]] not in (MERGE_LEFT, MERGE_UP):
                    anchor_of[(r, c)] = left
            # A row above too short to have this column is nothing to attach
            # to: reading it raised, and Export note and Ctrl+C with it.
            elif value == MERGE_UP and r > 0 and c < len(rows[r - 1]):
                above = anchor_of.get((r - 1, c), (r - 1, c))
                if rows[above[0]][above[1]] not in (MERGE_LEFT, MERGE_UP):
                    anchor_of[(r, c)] = above
    spans = {}
    for (r, c), (ar, ac) in anchor_of.items():
        rs, cs = spans.get((ar, ac), (1, 1))
        spans[(ar, ac)] = (max(rs, r - ar + 1), max(cs, c - ac + 1))
    return spans, set(anchor_of)


def find_blocks(text):
    """Every run of consecutive table rows, as ``(first_line, last_line)``.

    Line numbers are zero-based and inclusive, matching how ``paragraphs``
    entries are keyed.
    """
    blocks, start = [], None
    lines = (text or "").split("\n")
    for i, line in enumerate(lines):
        if is_table_row(line):
            if start is None:
                start = i
        elif start is not None:
            blocks.append((start, i - 1))
            start = None
    if start is not None:
        blocks.append((start, len(lines) - 1))
    return blocks


def align(text):
    """Re-pad every table in *text* so its columns line up.

    Returns ``(text, shifts)``, where *shifts* is a list of
    ``(offset, delta)`` describing where characters were added or removed --
    the same shape ``renumber()`` returns, so ``shift_spans()`` can move the
    formatting to match. Without that, re-padding a table would slide the
    bold in every line after it.
    """
    lines = (text or "").split("\n")
    shifts = []
    # Offsets are counted from the start of the body: the lines before each
    # block, as earlier blocks left them, are summed once and kept running.
    # Summed afresh for every block, 6,000 small pasted tables walked the
    # text 6,000 times.
    counted = prefix = 0
    for first, block, per_row, aligns in _alignment_plans(lines):
        prefix += sum(len(line) + 1 for line in lines[counted:first])
        counted = first
        pos = prefix
        for offset, old in enumerate(block):
            # Each edit is recorded where it actually happens, not at the end
            # of the line. Padding goes in *between* cells, so a word in a
            # later cell of the same row moves too -- recording it at the
            # line end left the bold in the second cell sitting on a space,
            # which only showed once columns had a minimum width and there
            # was padding to speak of. The ops come right to left, each at
            # its place in the line as it was, so the line is put together
            # once from its pieces -- rebuilt at every op, a row of thousands
            # of cells was copied thousands of times.
            pieces, end = [], len(old)
            for at, delta in pad_ops(old, per_row[offset],
                                     aligns[offset] if offset < len(aligns)
                                     else None):
                if delta > 0:
                    pieces += [old[at:end], " " * delta]
                else:
                    pieces.append(old[at - delta:end])
                end = at
                shifts.append((pos + at, delta))
            pieces.append(old[:end])
            pos += len(old) + 1
            lines[first + offset] = "".join(reversed(pieces))
    return "\n".join(lines), shifts


def _alignment_plans(lines):
    """Each table block in *lines*, with what align() pads it to:
    ``(first line, its lines, each row's widths, each row's alignments)``.
    One reading of a block, shared by align() and aligned_length(), so the
    size a paste weighs is the size align() makes."""
    for first, last in find_blocks("\n".join(lines)):
        block = lines[first:last + 1]
        sep_at = separator_index(block)
        rows = [split_row(line) for line in block]
        aligns = [cell_alignments(line) for line in block]
        if sep_at is not None:
            # The separator is mechanics, not data. Its dashes must not be
            # treated as content when measuring -- but where a column was
            # hand-widened, the dash count IS the wider width, and the data
            # cells pad out to honour it. Narrower-than-content dashes are
            # left alone: they are a display width for the drawn grid, and
            # the text never truncates what a cell holds.
            data_rows = [row for i, row in enumerate(rows) if i != sep_at]
            data_aligns = [a for i, a in enumerate(aligns) if i != sep_at]
            widths = layout_widths(data_rows, data_aligns)
            for i, column in enumerate(parse_separator(block[sep_at])):
                if i < len(widths) and not column["hidden"] and column["width"]:
                    widths[i] = max(widths[i], column["width"])
        else:
            widths = layout_widths(rows, aligns)
        yield first, block, row_widths(rows, widths, aligns), aligns


def aligned_length(text):
    """``len(align(text)[0])``, worked out without building it: what the
    padding adds, summed off the same edits align() would make."""
    lines = (text or "").split("\n")
    total = len(text or "")
    for _first, block, per_row, aligns in _alignment_plans(lines):
        for offset, line in enumerate(block):
            total += sum(delta for _at, delta in pad_ops(
                line, per_row[offset],
                aligns[offset] if offset < len(aligns) else None))
    return total


def forget_widths(text):
    """Every table's separator in *text* without the widths its dashes spell.

    For text that came from outside this app. A separator there is
    markdown's, its dashes as many as its writer typed: "---:" and ":---:"
    are how markdown spells an aligned column, and "|------|" one as wide
    as its header. Read as this app's own record, each was a width set by
    hand -- the column drawn exactly that narrow, its words cut to
    "How…". Each cell longer than markdown's minimum is spelled at the
    minimum instead, its colons and a hidden mark kept, so
    parse_separator's waiver applies and the column sizes to what it holds.

    Returns ``(text, shifts)`` in align()'s shape, every offset counted in
    the text as it came, for shift_spans().
    """
    lines = (text or "").split("\n")
    starts, pos = [], 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1
    shifts = []
    for first, last in find_blocks(text):
        at = separator_index(lines[first:last + 1])
        if at is None:
            continue
        n = first + at
        line, new, cut = lines[n], lines[n], 0
        for (a, b), column in zip(cell_bounds(line), parse_separator(line)):
            if not column["width"]:
                continue
            short = make_separator([dict(column, width=None)])[0]
            new = new[:a - cut] + short + new[b - cut:]
            shifts.append((starts[n] + a + len(short), len(short) - (b - a)))
            cut += (b - a) - len(short)
        lines[n] = new
    return "\n".join(lines), shifts


def content_text(text):
    """*text* with the table mechanics stripped out.

    Separator rows vanish, pipes and merge markers vanish, checkbox cells
    vanish (a checkbox is a control, not a word), and the ``<br>`` marker
    becomes the gap it draws. What remains is what the user actually
    wrote -- the right text to count words in or search through. Prose
    lines pass through untouched.
    """
    out = []
    for line in (text or "").split("\n"):
        if is_table_row(line):
            if is_separator_row(line):
                continue
            cells = [c.replace(LINE_BREAK, " ")
                     for c in split_row(line)
                     if c not in (MERGE_LEFT, MERGE_UP)
                     and checkbox_state(c) is None]
            line = " ".join(c for c in cells if c)
        out.append(line)
    return "\n".join(out)


def blank_table(rows, columns):
    """A new empty table, ready to be typed into."""
    rows = max(1, int(rows))
    columns = max(1, int(columns))
    return format_table([[""] * columns for _ in range(rows)])


def with_caret_line(body):
    """A body ending in a table, plus the line the editor guarantees below it.

    The editor ALWAYS draws a line under a trailing table — the caret needs
    somewhere to live or writing could never continue past the table, and
    ``_render_table_grids`` appends one on every draw. So "the note as
    stored" and "the note as shown" disagree by that one newline unless
    something reconciles them.

    Nothing had to, while every save ran ``.strip()`` over the body: the
    trim erased the difference (and much else the user had typed). Storing
    the body exactly as typed made it visible, and every table-ending note
    became permanently "unsaved" — an autosave rewrite on each note switch,
    a dirty dot that lied, and a recurring note asking its save-scope
    question unprompted.

    The render is not the bug, so this canonicalises the other side: apply
    it wherever a body is read out of the editor or written into a note,
    and the stored form becomes a FIXED POINT of the render — draw it and
    nothing changes. Idempotent, and a no-op for every body that does not
    end in a table.
    """
    if not body or body.endswith("\n"):
        return body
    blocks = find_blocks(body)
    if blocks and blocks[-1][1] == len(body.split("\n")) - 1:
        return body + "\n"
    return body


def _reads_as_plumbing(line):
    """True if a PERSON would see this line as part of a table.

    Deliberately looser than :func:`is_table_row`, and the difference is
    the whole point. That function decides what the editor will treat as
    a row, so it is strict: both ends must be a pipe. A line whose last
    cell was typed past -- ``| a | b | c |and then this`` -- is therefore
    not a row, and every caller that filtered on it left the line in.

    In an editor that is right: the line is what the user typed and must
    be shown back. In a PREVIEW it is wrong, because a preview shows a
    note's words and that line has none to show -- just punctuation. It
    was field-reported twice from the calendar, as "I only see vertical
    lines".

    Loose, but not past the way a row is written: every cell the app
    writes opens with a pipe and a space. A line of maths does not --
    "|x| = 5" stayed words, where a card had claimed a table for it.
    """
    stripped = (line or "").strip()
    if is_table_row(stripped):
        return True
    return (stripped.startswith(CELL) and stripped.count(CELL) >= 2
            and stripped[1:2].isspace())


def preview_text(body):
    """A note's words, without its tables, and how many it had.

    Returns ``(prose, tables)``. Both halves come from the same pass on
    purpose: a preview says what a note CARRIES rather than drawing it,
    so the sentence "this note has 2 tables" and the text beside it have
    to be answering about the same lines. Counting with one rule and
    stripping with another is how a preview came to announce five tables
    and then show a sixth as pipes.

    A run of consecutive table lines counts as one table, the way
    :func:`find_blocks` counts, and the blank line a table leaves behind
    is collapsed so the prose does not float in a gap.
    """
    lines = (body or "").split("\n")
    kept, tables, inside = [], 0, False
    for line in lines:
        if _reads_as_plumbing(line):
            if not inside:
                tables += 1
                inside = True
            continue
        inside = False
        kept.append(line)

    prose = []
    for line in kept:
        if not line.strip() and (not prose or not prose[-1].strip()):
            continue          # no runs of blank lines where a table was
        prose.append(line)
    while prose and not prose[-1].strip():
        prose.pop()
    return "\n".join(prose), tables
