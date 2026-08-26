"""Tests for tables kept as lines of text.

Headless and pure, like test_richtext.py: this converts strings to strings,
so it needs no clipboard, no window and no Windows.

Check descriptions stay ASCII-only, for the same reason test_calculator.py
does: printing a bullet crashes a plain Windows console on cp1252.
"""
from noteorganizer.core import tables
from noteorganizer.core.formatting import shift_spans
from noteorganizer.core.richtext import html_to_note, note_to_html, reflow_wrapped

fails = []


def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        fails.append(name)


# --- what counts as a row -----------------------------------------------
# Both ends have to be a pipe. Prose containing one, or a line that only
# opens with one, is not a table -- otherwise a sentence with a pipe in it
# would silently become a table row and be re-padded.
for line, want in (
        ("| Milk | 2 |", True),
        ("|a|b|", True),
        ("   | Milk | 2 |   ", True),
        ("a | b", False),
        ("| just one |", False),
        ("||", False),
        ("|", False),
        ("no pipes here at all", False),
        ("", False),
):
    check(f"is_table_row({line!r}) is {want}", tables.is_table_row(line) is want)

check("a row of empty cells is still a row", tables.is_table_row("|  |  |"))

# --- cells in, cells out ------------------------------------------------
check("padding is not part of a cell",
      tables.split_row("|  Milk   |   2 |") == ["Milk", "2"])
check("an empty cell is kept, not dropped",
      tables.split_row("| Milk |  | 2 |") == ["Milk", "", "2"])

# cell_bounds has to point at the text itself, padding excluded, or the
# formatting carried across to one cell would be read from the wrong place.
_row = "|  Milk   | 2 |"
_bounds = tables.cell_bounds(_row)
check(f"cell_bounds finds each cell's own text ({_bounds})",
      [_row[a:b] for a, b in _bounds] == ["Milk", "2"])
check("cell_bounds copes with a row that is indented",
      [("    " + _row)[a:b] for a, b in tables.cell_bounds("    " + _row)]
      == ["Milk", "2"])

# --- laying out ---------------------------------------------------------
check("every column is as wide as its widest cell",
      tables.column_widths([["Name", "Qty"], ["Milk", "2"], ["Eggs", "12"]])
      == [4, 3])
check("a table is padded to line up",
      tables.format_table([["Name", "Qty"], ["Milk", "2"]])
      == ["| Name | Qty |", "| Milk | 2   |"])

# A row with fewer cells than its neighbours is not an error -- it is a row
# someone is still typing -- so it is filled out rather than refused.
check("a short row is padded out to the full width",
      tables.format_table([["a", "b", "c"], ["d"]])
      == ["| a | b | c |", "| d |   |   |"])

check("a blank table is ready to type into",
      tables.blank_table(2, 3) == ["|  |  |  |", "|  |  |  |"])
check("a blank table is never smaller than one cell",
      tables.blank_table(0, 0) == ["|  |"])

# --- finding them in a note ---------------------------------------------
_body = "\n".join(["intro", "| a | b |", "| c | d |", "text", "| e | f |"])
check(f"consecutive rows are one block ({tables.find_blocks(_body)})",
      tables.find_blocks(_body) == [(1, 2), (4, 4)])
check("a note with no table has no blocks", tables.find_blocks("just words") == [])

# --- re-padding, and the formatting it would otherwise drag along --------
# Re-padding rewrites real characters, so everything after them moves. This
# is the same problem renumber() solves, and align() reports what it moved in
# the same shape so shift_spans() can put the formatting back.
_before = "start\n| Name | Qty |\n| Milk and bread | 2 |\nIMPORTANT after"
for _target in ("IMPORTANT", "Name", "start"):
    _at = _before.index(_target)
    _spans = [{"start": _at, "end": _at + len(_target), "style": "bold"}]
    _after, _shifts = tables.align(_before)
    _moved = shift_spans(_spans, _shifts)
    _covered = _after[_moved[0]["start"]:_moved[0]["end"]]
    check(f"bold on {_target!r} stays on it when the table is re-padded "
          f"(got {_covered!r})", _covered == _target)

_aligned, _ = tables.align(_before)
check("re-padding lines the columns up",
      _aligned.split("\n")[1] == "| Name           | Qty |")
check("and leaves everything around it alone",
      _aligned.split("\n")[0] == "start" and _aligned.split("\n")[3] == "IMPORTANT after")
check("re-padding an already-padded table changes nothing",
      tables.align(_aligned) == (_aligned, []))

# --- pasting one in ------------------------------------------------------
# Until this existed, td and th were neither block tags nor cells, so the
# cells ran together: "Milk | 2" arrived as "Milk2" with the boundary gone.
_html = ("<table><tr><th>Name</th><th>Qty</th></tr>"
         "<tr><td>Milk</td><td>2</td></tr>"
         "<tr><td>Eggs and bread</td><td>12</td></tr></table>")
_text, _spans, _paras = html_to_note(_html)
check("a pasted table keeps its cells apart",
      _text.split("\n") == ["| Name           | Qty |",
                            "| Milk           | 2   |",
                            "| Eggs and bread | 12  |"])
check("a pasted table needs no paragraph entries", _paras == [])

_mixed = "<p>Before</p><table><tr><td>A</td><td><b>B</b></td></tr></table><p>After</p>"
_t, _s, _p = html_to_note(_mixed)
check(f"a table between paragraphs keeps its place ({_t.splitlines()[1]!r})",
      _t.split("\n") == ["Before", "| A | B |", "After"])
check("and bold inside a cell survives the trip in",
      len(_s) == 1 and _t[_s[0]["start"]:_s[0]["end"]] == "B")

# --- copying one out -----------------------------------------------------
# Real markup, for the same reason a list goes out as <ul>: a word processor
# understands one and would paste the other as a row of pipe characters.
_note = "Before\n| Name | Qty |\n| Milk | 2   |\nAfter"
_out = note_to_html(_note)
check("a table goes out as real markup",
      "<table><tr><td>Name</td><td>Qty</td></tr>"
      "<tr><td>Milk</td><td>2</td></tr></table>" in _out)
check("the text around it is unaffected",
      _out.startswith("<div>Before</div>") and _out.endswith("<div>After</div>"))

_at = _note.index("Milk")
_bold = [{"start": _at, "end": _at + 4, "style": "bold"}]
check("bold in a cell is written into that cell alone",
      "<td><b>Milk</b></td>" in note_to_html(_note, _bold))

_back, _back_spans, _ = html_to_note(note_to_html(_note, _bold))
check(f"a table survives a round trip ({_back.splitlines()[1]!r})",
      _back == _note)
check("and so does the formatting inside it",
      len(_back_spans) == 1
      and _back[_back_spans[0]["start"]:_back_spans[0]["end"]] == "Milk")

# --- the PDF reflow must not eat a table ---------------------------------
# A table's line breaks are its rows, exactly as a list's are its items.
# Rejoining them would destroy the table rather than tidy it.
_table_text = "\n".join([
    "| The first column holds a fairly long piece of text |  1 |",
    "| The second row is about as long as the first one   |  2 |",
    "| And a third, so there are enough lines to be a run |  3 |",
])
check("reflow leaves a table exactly as it found it",
      reflow_wrapped(_table_text) == _table_text)

print()
print(f"FAILURES: {fails if fails else 'none'}")

import sys
sys.exit(1 if fails else 0)
