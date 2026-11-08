"""Tests for tables kept as lines of text.

Headless and pure, like test_richtext.py: this converts strings to strings,
so it needs no clipboard, no window and no Windows.

Check descriptions stay ASCII-only, for the same reason test_calculator.py
does: printing a bullet crashes a plain Windows console on cp1252.
"""
import os
import sys
# Settled as a guest of this computer before the app's code (qa/_qa_support,
# beside this file in a scratch copy, in qa/ where CI runs it).
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa"))
from _qa_support import as_a_guest  # noqa: E402
as_a_guest()
from noteorganizer.core import tables  # noqa: E402
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
# Widths are asserted as properties rather than as strings: they depend on
# MIN_COLUMN, and a check written as a literal has to be rewritten every
# time that moves -- which is how a test stops testing and starts following.
_wide = tables.column_widths([["Name", "Qty"], ["A much longer cell", "2"]])
check(f"a column is as wide as its widest cell ({_wide})",
      _wide[0] == len("A much longer cell"))
check(f"and never narrower than the floor ({_wide})",
      all(w >= tables.MIN_COLUMN for w in _wide))

_padded = tables.format_table([["Name", "Qty"], ["Milk", "2"]])
check(f"a table is padded to line up ({_padded[0]!r})",
      len(_padded[0]) == len(_padded[1]))
check("the cells survive the padding",
      [tables.split_row(r) for r in _padded] == [["Name", "Qty"], ["Milk", "2"]])

# A row with fewer cells than its neighbours is not an error -- it is a row
# someone is still typing -- so it is filled out rather than refused.
_ragged = tables.format_table([["a", "b", "c"], ["d"]])
check(f"a short row is padded out to the full width ({_ragged[1]!r})",
      len(_ragged[0]) == len(_ragged[1])
      and tables.split_row(_ragged[1]) == ["d", "", ""])

_blank = tables.blank_table(2, 3)
check(f"a blank table is ready to type into ({_blank[0]!r})",
      len(_blank) == 2
      and all(tables.split_row(r) == ["", "", ""] for r in _blank))
check("its cells are wide enough to look like cells, not specks",
      all(w >= tables.MIN_COLUMN
          for w in tables.column_widths([["", "", ""]])))
check("a blank table is never smaller than one cell",
      len(tables.blank_table(0, 0)) == 1
      and tables.split_row(tables.blank_table(0, 0)[0]) == [""])

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
_rows = _aligned.split("\n")[1:3]
check(f"re-padding lines the columns up ({_rows[0]!r})",
      len(_rows[0]) == len(_rows[1]))
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
check(f"a pasted table keeps its cells apart ({_text.splitlines()[1]!r})",
      [tables.split_row(r) for r in _text.split("\n")]
      == [["Name", "Qty"], ["Milk", "2"], ["Eggs and bread", "12"]])
check("a pasted table needs no paragraph entries", _paras == [])

_mixed = "<p>Before</p><table><tr><td>A</td><td><b>B</b></td></tr></table><p>After</p>"
_t, _s, _p = html_to_note(_mixed)
check(f"a table between paragraphs keeps its place ({_t.splitlines()[1]!r})",
      [_t.split("\n")[0], _t.split("\n")[2]] == ["Before", "After"]
      and tables.split_row(_t.split("\n")[1]) == ["A", "B"])
check("and bold inside a cell survives the trip in",
      len(_s) == 1 and _t[_s[0]["start"]:_s[0]["end"]] == "B")

# --- copying one out -----------------------------------------------------
# Real markup, for the same reason a list goes out as <ul>: a word processor
# understands one and would paste the other as a row of pipe characters.
_note = "Before\n" + "\n".join(
    tables.format_table([["Name", "Qty"], ["Milk", "2"]])) + "\nAfter"
_out = note_to_html(_note)
check(f"a table goes out as real markup ({_out[:60]!r})",
      "<table><tr><th>Name</th><th>Qty</th></tr>"
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

# --- what the page shows is what the app shows ---------------------------
# A hidden column (the ~ separator marker) stays hidden in the export;
# the data itself never leaves the note's text, so unhiding brings it back.
_hid = "\n".join(["| a | SECRET | c |",
                  "| --- | ~ | --- |",
                  "| 1 | concealed | 3 |"])
_hid_out = note_to_html(_hid)
check("a hidden column stays hidden in the export",
      "SECRET" not in _hid_out and "concealed" not in _hid_out
      and "<th>a</th><th>c</th>" in _hid_out)
_span_hid = "\n".join(["| a | b | c |",
                       "| --- | ~ | --- |",
                       "| wide | < | < |"])
check("a merge across a hidden column narrows to what shows",
      '<td colspan="2">wide</td>' in note_to_html(_span_hid))

# A checkbox leaves as the glyph the app draws, and the glyph comes back
# as the checkbox -- brackets never reach Word, boxes always come home.
# The app draws every checkbox centred in its cell, so the page does too.
_cb = "\n".join(["| task | done |", "| --- | --- |", "| no | [ ] |",
                 "| yes | [x] |"])
_cb_out = note_to_html(_cb)
check("checkboxes export as centred glyphs",
      'text-align:center;">☐</td>' in _cb_out
      and 'text-align:center;">☑</td>' in _cb_out
      and "[x]" not in _cb_out)
_cb_back, _, _ = html_to_note(_cb_out)
check("and the glyphs come back as checkboxes",
      "[ ]" in _cb_back and "[x]" in _cb_back and "☑" not in _cb_back)

# The FILE export's borders live in its stylesheet; a CLIPBOARD fragment
# travels alone, and Word paints a bare HTML table with no borders at
# all -- a selectable phantom. inline_tables rides them on every tag.
check("the file-export markup stays bare of inline borders",
      "border:1px solid" not in _out)
_clip_out = note_to_html(_note, inline_tables=True)
check("the clipboard-flavoured markup carries its borders inline",
      "border-collapse:collapse;" in _clip_out
      and _clip_out.count("border:1px solid #999;") >= 4)

# --- counting and searching see the writing, not the plumbing ------------
_ct = tables.content_text("\n".join([
    "two words",
    "| Milk | 2 |",
    "| --- | ~ |",
    "| [x] | note<br>here |",
]))
check("content_text keeps prose and cell words only",
      "two words" in _ct and "Milk" in _ct and "note here" in _ct)
check("content_text drops pipes, dashes, markers and checkboxes",
      "|" not in _ct and "---" not in _ct and "[x]" not in _ct
      and "<br>" not in _ct)

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

# --- merged cells --------------------------------------------------------
# A cell holding exactly "<" belongs to the cell on its left, "^" to the
# cell above; anchors sit at the top-left of their rectangle. The markers
# live in the text like everything else, so a merge survives align(), save,
# share codes and export with no new note field.
_m_rows = [["No", "Channel", "Cable", "<", "<"],
           ["^", "^", "Vodafone", "Digi", "Orange"],
           ["1.", "TV", "x", "x", "x"]]
_m_spans, _m_covered = tables.merge_map(_m_rows)
check(f"merge_map finds the spans ({sorted(_m_spans.items())})",
      _m_spans == {(0, 0): (2, 1), (0, 1): (2, 1), (0, 2): (1, 3)})
check(f"and the covered positions ({len(_m_covered)})",
      _m_covered == {(0, 3), (0, 4), (1, 0), (1, 1)})

# A marker with nothing to attach to is content, not a merge.
_orphans, _orphan_covered = tables.merge_map([["<", "a"], ["^", "b"]])
check("an orphan marker stays ordinary content",
      _orphans == {} and _orphan_covered == set())
# ...and so does a "^" under a row too short to have its column: reading that
# cell raised, and Export note and Ctrl+C with it.
try:
    _ragged = tables.merge_map([["a", "b"], ["^", "^", "^"]])
    _ragged_html = note_to_html("| a | b |\n| ^ | ^ | ^ |")
except Exception as _ragged_exc:
    _ragged, _ragged_html = repr(_ragged_exc), ""
check(f"a merge marker under a row without its column is content ({_ragged})",
      _ragged == ({(0, 0): (2, 1), (0, 1): (2, 1)}, {(1, 0), (1, 1)})
      and "<table" in _ragged_html)

# The bug as reported: a spreadsheet header with rowspan and colspan sheared
# every row under it one column left, so the symbol columns came out empty.
_shear_html = ("<table>"
               "<tr><th rowspan='2'>No</th><th rowspan='2'>Channel</th>"
               "<th colspan='3'>Cable</th></tr>"
               "<tr><th>Vodafone</th><th>Digi</th><th>Orange</th></tr>"
               "<tr><td>1.</td><td>TV</td>"
               "<td>\u2713</td><td>\u2717</td><td>\u2713</td></tr>"
               "</table>")
_shear_text, _s2, _p2 = html_to_note(_shear_html)
_shear_rows = [tables.split_row(l) for l in _shear_text.split("\n")]
check(f"a merged header no longer shears the rows below ({_shear_rows[1]})",
      _shear_rows == [["No", "Channel", "Cable", "<", "<"],
                      ["^", "^", "Vodafone", "Digi", "Orange"],
                      ["1.", "TV", "\u2713", "\u2717", "\u2713"]])
check("the symbols come through as themselves",
      "\u2713" in _shear_text and "\u2717" in _shear_text)

# And back out: anchors leave with their spans, covered cells not at all.
_m_out = note_to_html(_shear_text)
check("a merged table goes out with colspan and rowspan",
      'colspan="3"' in _m_out and 'rowspan="2"' in _m_out)
check("the markers themselves never leak into the markup",
      "&lt;</td>" not in _m_out and ">^<" not in _m_out)
_m_back, _m_bs, _m_bp = html_to_note(_m_out)
check("a merged table survives the round trip", _m_back == _shear_text)

# --- alignment lives in the padding --------------------------------------
# "| x    |" is left, "|  x  |" centred, "|    x |" right. The spaces are
# the store, so alignment survives save, share codes and export with no new
# field, and align() must preserve it when widths move.
_al_rows = [["Name", "Qty"], ["x", "2"]]
_al = [["center", "left"], ["center", "right"]]
_al_lines = tables.format_table(_al_rows, _al)
check(f"formatting deals the padding by alignment ({_al_lines[0]!r})",
      [tables.cell_alignments(l) for l in _al_lines] == _al)
_al_body = "\n".join(_al_lines)
_al_after, _ = tables.align(_al_body)
check("align() preserves every cell's alignment",
      [tables.cell_alignments(l) for l in _al_after.split("\n")] == _al)
_al_html = note_to_html(_al_body)
check("alignment leaves as text-align",
      "text-align:center" in _al_html and "text-align:right" in _al_html)
_al_back, _b1, _b2 = html_to_note(_al_html)
check("and comes back through the round trip",
      [tables.cell_alignments(l) for l in _al_back.split("\n")] == _al)
# Widening a centred column keeps it centred.
_wider, _ = tables.align("\n".join(
    [_al_lines[0], "| a very much longer cell | 2 |"]))
check(f"a centred cell stays centred as its column widens "
      f"({_wider.splitlines()[0]!r})",
      tables.cell_alignments(_wider.splitlines()[0])[0] == "center")

# ---- THE SEPARATOR ROW: MECHANICS, NOT DATA ----
# |---|:---:|~| as row two carries per-column display width (dash count),
# alignment (colons) and hiding (~). It is exactly markdown's own syntax,
# so tables travel both ways between this app and anything markdown-aware.
check("a separator row is recognised",
      tables.is_separator_row("| --- | :---: | ~ |"))
check("a data row is not",
      not tables.is_separator_row("| --- | words |"))
check("only the first two rows can hold one",
      tables.separator_index(["| a | b |", "| c | d |", "| --- | --- |"]) is None
      and tables.separator_index(["| a | b |", "| --- | --- |", "| c | d |"]) == 1)
_sp = tables.parse_separator("| ----- | :---: | ---: | ~ |")
check(f"parse reads width, alignment and hiding ({_sp})",
      _sp[0] == {"width": 5, "align": None, "hidden": False}
      and _sp[1] == {"width": 5, "align": "center", "hidden": False}
      and _sp[2] == {"width": 4, "align": "right", "hidden": False}
      and _sp[3]["hidden"])
check("make/parse round-trips every column",
      tables.parse_separator(
          "| " + " | ".join(tables.make_separator(_sp)) + " |") == _sp)

# align() widens data to a hand-widened separator, and leaves a narrow
# one alone -- narrow is a display width, the text never truncates.
_sep_body = "\n".join(["| Name | Qty |",
                       "| ------------ | --- |",
                       "| ab | 2 |"])
_sep_after, _ = tables.align(_sep_body)
_sep_lines = _sep_after.split("\n")
check(f"align pads data out to a wide separator ({_sep_lines[2]!r})",
      len(_sep_lines[2].split("|")[1]) >= 12)
check("and the separator still parses with its width",
      tables.parse_separator(_sep_lines[1])[0]["width"] == 12)
_nar_body = "\n".join(["| Name | Qty |",
                       "| --- | --- |",
                       "| something long | 2 |"])
_nar_after, _ = tables.align(_nar_body)
check("a narrow separator never truncates the data",
      "something long" in _nar_after)
# (Measuring the separator AS content would give the same widths -- its
# cell length IS the stored width -- so that variant is equivalent, not a
# bug to test for.)

# Text from outside the app: markdown's "---:" is four characters, read as
# a column set by hand to four -- "How much" drawn "How…". forget_widths
# spells every such cell at markdown's minimum, and only that.
_fw, _fw_shifts = tables.forget_widths(
    "| What | How much |\n| --- | ---: |\n| rent | 1500 |")
check(f"a pasted '---:' keeps its colon and loses its width ({_fw!r})",
      _fw.split("\n")[1] == "| --- | --: |"
      and [c["width"] for c in tables.parse_separator(_fw.split("\n")[1])] == [None, None]
      and tables.parse_separator(_fw.split("\n")[1])[1]["align"] == "right")
_fw2, _ = tables.forget_widths("| a | b | c |\n|:------|:-----:|~|\n| 1 | 2 | 3 |")
check(f"left, centred and hidden columns keep their marks ({_fw2.split(chr(10))[1]!r})",
      _fw2.split("\n")[1] == "|:--|:-:|~|")
_fw3_text = "| a | b |\n| --- | :-: |\n| x | y |"
check("a separator already at markdown's minimum is left exactly as it came",
      tables.forget_widths(_fw3_text) == (_fw3_text, []))
check("so is text with no table in it, a line of dashes included",
      tables.forget_widths("one\n------\ntwo") == ("one\n------\ntwo", []))
# Two tables, a bold word after each separator: the shifts are counted in
# the text as it came, as shift_spans judges them, so both words keep it.
_fw4_text = ("| Name | Age |\n|------|-----|\n| Alexandra | 31 |\n\n"
             "| p | q |\n| ----: | :---- |\n| Radu | 2 |")
_fw4, _fw4_shifts = tables.forget_widths(_fw4_text)
_fw4_spans = shift_spans(
    [{"start": _fw4_text.index("Alexandra"), "end": _fw4_text.index("Alexandra") + 9,
      "style": "bold"},
     {"start": _fw4_text.index("Radu"), "end": _fw4_text.index("Radu") + 4,
      "style": "bold"}], _fw4_shifts)
check(f"a style after each forgotten width stays on its word "
      f"({[_fw4[s['start']:s['end']] for s in _fw4_spans]})",
      [_fw4[s["start"]:s["end"]] for s in _fw4_spans] == ["Alexandra", "Radu"])
check("and the tidy then sizes the column to what it holds, not to the dashes",
      "| Alexandra |" in tables.align(_fw4)[0]
      and tables.align(tables.forget_widths(
          "| a |\n| ------------ |\n| b |")[0])[0].split("\n")[0].count(" ") < 12)

# The separator never reaches exported HTML.
_sep_html = note_to_html(_sep_body)
check("export skips the separator row",
      "---" not in _sep_html and _sep_html.count("<tr>") == 2)

# ---------------------------------------------------------------------
# preview_text: a note's words, without its tables.
#
# A preview says what a note CARRIES rather than drawing it, so it needs
# a rule looser than is_table_row(). That one is strict on purpose --
# both ends must be a pipe, or the editor would treat prose as a table.
# A line whose last cell was typed past is therefore not a row, and a
# preview filtering on it left the line in: field-reported twice from
# the calendar as "I only see vertical lines".
# ---------------------------------------------------------------------
_pv, _pn = tables.preview_text("before\n| a | b |\n| c | d |\nafter")
check("preview_text keeps the words either side of a table",
      _pv == "before\nafter")
check("...and counts a run of rows as one table", _pn == 1)

# The line the strict test refuses, which is exactly the one that leaked.
_pv2, _pn2 = tables.preview_text("words\n| a | b | c |and then this")
check("a row typed past its last cell is not a row to the editor",
      tables.is_table_row("| a | b | c |and then this") is False)
check("...but a preview drops it anyway", _pv2 == "words")
check("...and counts it", _pn2 == 1)

# Her note: cells that are nearly all empty, which is also not a row.
_ragged = "|      |      |     | [x]  |    |    |     |fig2efwfwe"
_pv3, _pn3 = tables.preview_text("note\n" + _ragged)
check("a ragged half-empty row is dropped from a preview too", _pv3 == "note")

_pv4, _pn4 = tables.preview_text("| a | b |\n\n| c | d |")
check("two runs separated by a blank line count as two tables", _pn4 == 2)

_pv5, _pn5 = tables.preview_text("just words")
check("a note with no table is left exactly as it is",
      _pv5 == "just words" and _pn5 == 0)
check("an empty body survives", tables.preview_text("") == ("", 0))
check("a None body survives", tables.preview_text(None) == ("", 0))

# Prose that merely mentions a pipe must not be eaten.
_pv6, _pn6 = tables.preview_text("the command is ls | grep x")
check("prose containing a pipe is not mistaken for a table",
      _pv6 == "the command is ls | grep x" and _pn6 == 0)

_pv7, _pn7 = tables.preview_text("top\n\n\n| a | b |\n\n\nbottom")
check("the gap a table leaves behind is collapsed, not doubled",
      _pv7 == "top\n\nbottom")

# A line of maths starts with a pipe too, but not the way a cell is
# written -- the app pads every cell, so its rows open "| ". A card
# claimed "1 table" for this note and hid the line (audit).
_pv8, _pn8 = tables.preview_text("|x| = 5 for x = -5\n|x| + |y| = 3")
check(f"a line of maths is words, not a table ({_pv8!r}, {_pn8})",
      _pv8 == "|x| = 5 for x = -5\n|x| + |y| = 3" and _pn8 == 0)
check("a caption's label is a number and a colon after Table (or the old Tab.)",
      tables.is_caption_line("Table 3: sales") and tables.is_caption_line("  Tab. 2: x")
      and not tables.is_caption_line("Tables are useful")
      and not tables.is_caption_line("Table 3 has no colon")
      and not tables.is_caption_line(None))
check("...and its source line says Source:",
      tables.is_source_line("Source: the web") and not tables.is_source_line("Sources vary"))

_pv9, _pn9 = tables.preview_text("words\n|a|b|")
check("...while a row written without padding is still the row the editor "
      "draws", _pv9 == "words" and _pn9 == 1)


# ---- Lining a table up never multiplies it ----
# Padding every cell to its column's widest made the padding the widest
# cell times the rows: one 60,000-character cell over 3,500 rows turned a
# 162 KB paste into 210 million characters (ISSUES_LOG: "Limits that held
# at the door but not after it"). Measured in characters, never in time.
import random as _rnd
from noteorganizer.core.richtext import MAX_PASTE_CHARS as _CEIL

_wide_rows = [["x" * 60000, "y"]] + [["a", "b"]] * 3500
_wide_len = tables.table_length(_wide_rows)
check(f"a table whose lining up would pad past {tables.MAX_TABLE_PADDING:,} "
      f"spaces is left ragged ({_wide_len:,} chars)",
      _wide_len < 60000 + 3500 * 12)
check("...and table_length says so without building it, as format_table builds it",
      _wide_len == len("\n".join(tables.format_table(_wide_rows))))
_wide_text = "\n".join("| " + " | ".join(r) + " |" for r in _wide_rows)
_wide_aligned = tables.align(_wide_text)[0]
check(f"...align() likewise ({len(_wide_aligned):,} chars)",
      len(_wide_aligned) <= len(_wide_text) + 3500 * 4
      and tables.aligned_length(_wide_text) == len(_wide_aligned))
check("...while an ordinary table is lined up exactly as before",
      tables.format_table([["Name", "Qty"], ["Milk", "2"]])
      == ["| Name     | Qty      |", "| Milk     | 2        |"])

_rg = _rnd.Random(20261028)
_len_agree = True
for _i in range(400):
    _n, _c = _rg.randint(1, 6), _rg.randint(2, 4)
    _lines = []
    for _r in range(_n):
        _k = _c if _rg.random() < 0.8 else _rg.randint(2, _c + 1)
        if _r == 1 and _rg.random() < 0.5:
            _lines.append("|" + "|".join(_rg.choice(["---", ":-:", "--:", "~", "-" * 12])
                                         for _ in range(_k)) + "|")
        else:
            _lines.append("|" + "|".join(
                " " * _rg.randint(0, 3) + "ab c"[:_rg.randint(0, 4)].strip()
                + " " * _rg.randint(0, 3) for _ in range(_k)) + "|")
    _t = _rg.choice(["", "words\n"]) + "\n".join(_lines)
    _rows = [tables.split_row(l) for l in _lines]
    _len_agree = (_len_agree
                  and tables.aligned_length(_t) == len(tables.align(_t)[0])
                  and tables.table_length(_rows)
                  == len("\n".join(tables.format_table(_rows))))
check("the lengths worked out ahead agree with what align() and "
      "format_table() then build, on 400 random tables", _len_agree)

# The paste: the ceiling holds on what goes into the note, padding included.
_doc = ("<table><tr><td>" + "x" * 60000 + "</td><td>y</td></tr>"
        + "<tr><td>a</td><td>b</td></tr>" * 3500 + "</table>")
_cutW = {}
_txtW = html_to_note(_doc, report=_cutW)[0]
check(f"a pasted table with one 60,000-character cell over 3,500 rows stays "
      f"within the paste ceiling ({len(_txtW):,} chars)",
      len(_txtW) <= _CEIL)
_doc = ("<table><tr><td>" + "x" * 240 + "</td><td>y</td></tr>"
        + "<tr><td>a</td><td>b</td></tr>" * 400 + "</table>"
        + "<p>" + "z" * 60000 + "</p>")
_cutP = {}
_txtP = html_to_note(_doc, report=_cutP)[0]
check(f"a paste that padding carries past the ceiling is cut before the "
      f"padding, and says so ({len(_txtP):,} chars, {_cutP})",
      len(_txtP) <= _CEIL and _cutP.get("text_cut") is True
      and _txtP.startswith("| " + "x" * 240))

# A note's lines on one line, kept apart: the card and the question about a
# day off its schedule both read them so.
_apart = tables.lines_apart("the book borrowed\n\n  from   Radu \nthe article\n")
check(f"lines_apart keeps a note's lines apart, empty ones left out ({_apart!r})",
      _apart == "the book borrowed · from Radu · the article")
check("lines_apart of nothing is nothing",
      tables.lines_apart("") == "" and tables.lines_apart(None) == "")
# A list item with no words is an empty line, left out.
_items = tables.lines_apart("Pack the coat\n• \n• milk\n  ◦ \n2. \n3. eggs")
check(f"lines_apart leaves out a list item with no words ({_items!r})",
      _items == "Pack the coat · milk · eggs")
# A list item keeps its words, not its marker: "· • milk" read as two marks.
_marks = tables.lines_apart("• bread\n  ◦  rye   flour\n▪ salt\n12. butter\n•no space")
check(f"lines_apart keeps a list item's words without its marker ({_marks!r})",
      _marks == "bread · rye flour · salt · butter · •no space")
# Every cut the app shows: whole when it fits, its "…" held to the last word.
_cuts = [tables.glimpse(t, n) for t, n in (
    ("milk", 4), ("", 3), ("what is next", 8), ("water bottles · Call Ann", 16),
    ("one two", 5))]
check(f"glimpse keeps a text that fits and ends a cut at its last word ({_cuts!r})",
      _cuts == ["milk", "", "what is…", "water bottles…", "one t…"])

print()
print(f"FAILURES: {fails if fails else 'none'}")

import sys
sys.exit(1 if fails else 0)
