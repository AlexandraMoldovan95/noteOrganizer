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


def format_row(cells, widths):
    """One row, padded so its columns line up under the widths given."""
    padded = []
    for i, width in enumerate(widths):
        cell = cells[i] if i < len(cells) else ""
        padded.append(" " + cell.ljust(width) + " ")
    return CELL + CELL.join(padded) + CELL


def format_table(rows):
    """A table's lines, every column as wide as its widest cell."""
    widths = column_widths(rows)
    return [format_row(row, widths) for row in rows]


def pad_ops(line, widths):
    """The space edits that would line this row up, listed right to left.

    Each is ``(offset, delta)``: a positive delta inserts that many spaces at
    that offset in the line, a negative one deletes that many characters
    there. Right to left so applying one does not move the next one's offset.

    Editing the spaces rather than rewriting the line is what makes this
    usable in a widget. Tk moves a tag along with the text around it, so
    inserting a space beside a cell leaves the bold inside it exactly where
    it was; replacing the whole line would take the tags with it.
    """
    bounds = cell_bounds(line)
    if not bounds:
        return []
    raw = (line or "").rstrip()
    ops = []
    for i in range(len(bounds) - 1, -1, -1):
        start, end = bounds[i]
        width = widths[i] if i < len(widths) else (end - start)
        # After the text: however many spaces are needed to reach the width,
        # plus the one that always sits before the closing pipe.
        closing = raw.index(CELL, end)
        have, want = closing - end, width - (end - start) + 1
        if have != want:
            ops.append((end, want - have))
        # Before the text: exactly one space after the opening pipe.
        opening = start - 1
        while opening >= 0 and raw[opening] != CELL:
            opening -= 1
        have_lead = start - opening - 1
        if have_lead != 1:
            ops.append((opening + 1, 1 - have_lead))
    return ops


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
        rows = [split_row(line) for line in lines[first:last + 1]]
        widths = column_widths(rows)
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
            for at, delta in pad_ops(old, widths):
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


def blank_table(rows, columns):
    """A new empty table, ready to be typed into."""
    rows = max(1, int(rows))
    columns = max(1, int(columns))
    return format_table([[""] * columns for _ in range(rows)])
