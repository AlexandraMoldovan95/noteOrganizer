"""Regenerate qa/README's seam map from what the scripts actually mention.

The table's own note says it was produced by grepping each surface's
identifiers across qa*.py, so refreshing it is a loop rather than
archaeology. This is that loop. Coverage-ledger C8 is about the table
having drifted from the suite through three audit rounds without anyone
re-running it.

Bold ownership is not a judgement here: a file is a heavy owner when it
carries at least a quarter of a surface's mentions, or leads the next one
by more than double -- the rule qa/README states under the table.
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QA = sorted(glob.glob(os.path.join(ROOT, "qa", "qa[0-9].py")))

SURFACES = [
    ("Bulk-action bar / selection mode", (r"bulk_", r"selection_mode", r"_bulk")),
    ("Theming (apply/track/toggle)", (r"track_theme", r"apply_theme", r"toggle_theme",
                                      r"_recolor")),
    ("Autosave (debounce, guards, flush)", (r"autosave", r"_flush_autosave")),
    ("Editor page scroll/canvas", (r"editor_canvas", r"page_canvas", r"_page_scroll",
                                   r"editor_scroll")),
    ("Note list (refresh, scroll guards, grouping)",
     (r"refresh_note_list", r"_note_card", r"_card_view", r"_card_order", r"_list_drawn",
      r"group_by_category")),
    ("Tables / drawn grids", (r"_insert_table", r"_table_grids", r"is_table_row",
                              r"_grid_", r"_render_table")),
    ("Find in note (Ctrl+F) / find bar", (r"find_bar", r"_find_in_note", r"find_var",
                                          r"_find_next")),
    ("Templates", (r"template",)),
    ("Settings panels", (r"settings_page", r"open_settings", r"_settings_")),
    ("Calendar", (r"calendar", r"TAB_CALENDAR", r"open_day_popup", r"selected_day")),
    ("Trash", (r"trash",)),
    ("Share codes", (r"share_code", r"encode_share", r"decode_share", r"import_box")),
    ("Export (files, backup)", (r"export",)),
    ("Attachments", (r"attachment",)),
    ("Recurrence / occurrences", (r"recurrence", r"occurrence", r"rec_freq", r"override")),
    ("Checklist", (r"checklist",)),
    ("Formatting / rich text", (r"_extract_formatting", r"_apply_formatting",
                                r"font_spans", r"_apply_body_font", r"formatting")),
]

counts = {}
for path in QA:
    name = os.path.splitext(os.path.basename(path))[0]
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    for surface, patterns in SURFACES:
        n = sum(len(re.findall(p, text)) for p in patterns)
        counts.setdefault(surface, {})[name] = n

print("| Surface | Guarded in |")
print("|---|---|")
for surface, _ in SURFACES:
    per = counts[surface]
    present = {k: v for k, v in per.items() if v > 0}
    if not present:
        print("| %s | *(nothing mentions it)* |" % surface)
        continue
    total = sum(present.values())
    ordered = sorted(present.items(), key=lambda kv: (-kv[1], kv[0]))
    # Heavy owner: carries at least a quarter of the mentions, or is the
    # clear leader with more than twice the runner-up.
    heavy = []
    for i, (name, n) in enumerate(ordered):
        if n >= max(3, total * 0.25):
            heavy.append(name)
        elif i == 0 and len(ordered) > 1 and n > 2 * ordered[1][1]:
            heavy.append(name)
    cells = ["**%s**" % n if n in heavy else n for n, _ in ordered]
    print("| %s | %s |" % (surface, ", ".join(cells)))

print()
print("raw counts, for the record:")
for surface, _ in SURFACES:
    per = {k: v for k, v in counts[surface].items() if v}
    print("   %-46s %s" % (surface, per))
