"""Tables, as lines of text: a row really is the line ``| Milk | 2 |`` in the
body, as a bullet is its ``"• "``, since ``formatting``'s offsets count that
same body (``docs/ARCHITECTURE.md``, "The marker lives in the body text").
So the note format does not change, a pasted table stays readable, and
re-padding a row moves the offsets after it: this module returns its shifts
in ``renumber()``'s shape for ``shift_spans()``. Pipes, because prose does
not begin with one, so a row is known from its own text. Strings in,
strings out: no tkinter, tested on any machine.
"""

import re

CELL = "|"
# A line break INSIDE a cell, as markdown itself writes one -- a table
# row must stay one line of text, so the break is a marker in the value.
# Export, share codes and any markdown-aware tool read it natively.
LINE_BREAK = "<br>"
# A cell holding exactly one of these IS a checkbox, markdown's own task
# idiom: drawn as a box a click toggles; opened, it shows empty, and what is
# typed takes the box's place.
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
# A cell holding exactly one of these is a merge marker: "<" belongs to the
# cell on its left, "^" to the one above, anchors at their rectangle's top
# left. Typed alone it means a merge, as "2." starts a numbered item.
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
            # An empty cell is all padding: skipped, the caret landed on the
            # closing pipe. Typing starts one space in from the opening one.
            start = pos + min(1, len(part))
        bounds.append((start, start + len(text)))
        pos += len(part) + 1
    return bounds


# No column narrower: a new table's empty cells, one character wide, read as
# specks rather than places to type, and lurched wider at the first letter.
MIN_COLUMN = 8


ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT = "left", "center", "right"


def cell_alignments(line):
    """Per-cell alignment, read off the padding itself: two or more spaces
    on both sides of the text is centred, on the left alone right-aligned,
    anything else -- an empty cell too -- left. The padding is the store, so
    a row typed by hand means what it looks like."""
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


# Padding is the widest cell times the rows; past this many spaces (the paste
# ceiling's number) a table is left ragged, and the drawn grid looks the same.
# ISSUES_LOG: "Limits that held at the door but not after it".
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
    """The space edits that would line this row up, right to left so one
    does not move the next: ``(offset, delta)``, a positive delta inserting
    that many spaces, a negative one deleting that many characters. Edits,
    not a new line, so Tk keeps the bold inside a cell where it was.
    *aligns* deals the padding to the sides each cell's alignment asks for,
    which is how it is read back."""
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
        # Three characters or fewer ("---", ":-:") is markdown's usual spelling,
        # not a size: honoured, it clipped the column under its own text. Longer
        # pasted ones are spelled at the minimum as they come in (forget_widths).
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
    """Resolve merge markers into spans: ``(spans, covered)``, with
    ``spans[(r, c)] = (rowspan, colspan)`` for every anchor spanning more
    than one cell, and ``covered`` the (r, c) positions some anchor swallows.
    A marker with nothing to attach to -- "<" in the first column, "^" in
    the first row -- is left as ordinary content rather than guessed at."""
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
    """Re-pad every table in *text* so its columns line up. Returns ``(text,
    shifts)``, *shifts* the ``(offset, delta)`` list of characters added or
    removed, in ``renumber()``'s shape, for ``shift_spans()`` to move the
    formatting: without it, the bold in every later line would slide."""
    lines = (text or "").split("\n")
    shifts = []
    # Offsets from the body's start, the lines before each block summed once
    # and kept running: summed afresh, 6,000 pasted tables walked it 6,000 times.
    counted = prefix = 0
    for first, block, per_row, aligns in _alignment_plans(lines):
        prefix += sum(len(line) + 1 for line in lines[counted:first])
        counted = first
        pos = prefix
        for offset, old in enumerate(block):
            # Each edit recorded where it happens, between cells: at the line's
            # end, a later cell's bold sat on a space. Right to left, the line
            # is joined once from its pieces, not copied at every edit.
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
            # The separator is not content, but a hand-widened column's dash
            # count is its width, which the cells pad out to; narrower dashes
            # are only the drawn grid's width, never a cut of the text.
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
    """Every table's separator in *text* without the widths its dashes spell,
    for text from outside: markdown's "---:" or "|------|", read as this
    app's record of a width set by hand, drew the column that narrow, its
    words cut. Each cell past markdown's minimum is spelled at it, colons
    and a hidden mark kept. Returns ``(text, shifts)`` in align()'s shape,
    offsets counted in the text as it came."""
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
    """*text* with the table mechanics stripped out: separator rows, pipes,
    merge markers and checkbox cells (a control, not a word) go, and
    ``<br>`` becomes the gap it draws. What remains is what the person wrote
    -- the text to count words in or search through; prose passes untouched."""
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
    """A body ending in a table, plus the line the editor always draws below
    it for the caret: applied wherever a body leaves the editor or enters a
    note, so the stored form is a fixed point of the render. Without it, a
    body kept as typed differed from the editor by that newline, and every
    note ending in a table read as unsaved for good. Idempotent; a no-op
    for every other body."""
    if not body or body.endswith("\n"):
        return body
    blocks = find_blocks(body)
    if blocks and blocks[-1][1] == len(body.split("\n")) - 1:
        return body + "\n"
    return body


def _reads_as_plumbing(line):
    """True if a PERSON would see this line as part of a table: looser than
    :func:`is_table_row`, which the editor needs strict (a pipe at both
    ends), so a row typed past -- ``| a | b |and then this`` -- is not shown
    in a preview as a line of pipes. Not past how a row is written: every
    cell opens with a pipe and a space, so "|x| = 5" stays words."""
    stripped = (line or "").strip()
    if is_table_row(stripped):
        return True
    return (stripped.startswith(CELL) and stripped.count(CELL) >= 2
            and stripped[1:2].isspace())


def preview_text(body):
    """A note's words, without its tables, and how many it had: ``(prose,
    tables)`` from one pass, so "2 tables" and the text beside it answer
    about the same lines (two rules once announced five and showed a sixth
    as pipes). A run of table lines is one table, as :func:`find_blocks`
    counts, and the blank line a table leaves is collapsed."""
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
