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
        start = pos + (len(part) - len(part.lstrip()))
        bounds.append((start, start + len(part.strip())))
        pos += len(part) + 1
    return bounds


def column_widths(rows):
    """How wide each column has to be to hold every cell in it.

    Rows may be ragged -- a row with fewer cells than its neighbours is not
    an error, it is a row someone is still typing.
    """
    widths = []
    for row in rows:
        for i, cell in enumerate(row):
            if i >= len(widths):
                widths.append(0)
            widths[i] = max(widths[i], len(cell))
    return widths


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
        formatted = format_table(rows)
        # Offsets are counted from the start of the body, so the length of
        # every line before this block has to be walked first. Done per
        # block rather than kept running, because a block's own lines change
        # length as they are replaced.
        pos = sum(len(line) + 1 for line in lines[:first])
        for offset, (old, new) in enumerate(zip(lines[first:last + 1], formatted)):
            delta = len(new) - len(old)
            if delta:
                # Recorded at the end of the line: padding is added inside
                # it, so only text after the line moves. Anything formatted
                # within the line keeps its place, which is what a person
                # editing one cell expects of the bold in another.
                shifts.append((pos + len(old), delta))
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
