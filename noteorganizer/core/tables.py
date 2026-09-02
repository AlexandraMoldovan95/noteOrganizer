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

CELL = "|"
# A line break INSIDE a cell, as markdown itself writes one -- a table
# row must stay one line of text, so the break is a marker in the value.
# Export, share codes and any markdown-aware tool read it natively.
LINE_BREAK = "<br>"
# A cell holding exactly one of these IS a checkbox -- markdown's own
# task idiom, so the stored text stays plainly readable and any
# markdown-aware tool shows a task box. The app draws it as a real
# box and a click toggles it; delete it and type, and the cell is
# ordinary text again.
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


def format_table(rows, aligns=None):
    """A table's lines, every column as wide as its widest cell."""
    widths = layout_widths(rows, aligns)
    return [format_row(row, widths,
                       aligns[r] if aligns and r < len(aligns) else None)
            for r, row in enumerate(rows)]


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
        columns.append({"width": len(cell), "align": align, "hidden": False})
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
            elif value == MERGE_UP and r > 0:
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
    for first, last in find_blocks(text):
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
        # Offsets are counted from the start of the body, so the length of
        # every line before this block has to be walked first. Done per
        # block rather than kept running, because a block's own lines change
        # length as they are replaced.
        pos = sum(len(line) + 1 for line in lines[:first])
        for offset, old in enumerate(list(lines[first:last + 1])):
            new = old
            # Each edit is recorded where it actually happens, not at the end
            # of the line. Padding goes in *between* cells, so a word in a
            # later cell of the same row moves too -- recording it at the
            # line end left the bold in the second cell sitting on a space,
            # which only showed once columns had a minimum width and there
            # was padding to speak of.
            for at, delta in pad_ops(old, widths,
                                     aligns[offset] if offset < len(aligns)
                                     else None):
                if delta > 0:
                    new = new[:at] + " " * delta + new[at:]
                else:
                    new = new[:at] + new[at - delta:]
                shifts.append((pos + at, delta))
            pos += len(old) + 1
            lines[first + offset] = new
    return "\n".join(lines), shifts


def to_rows(text, first, last):
    """The cells of one block, as a list of rows."""
    lines = (text or "").split("\n")
    return [split_row(line) for line in lines[first:last + 1]]


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
