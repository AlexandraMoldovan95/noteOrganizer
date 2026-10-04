"""Ask the code, one finding at a time, what is actually still true.

WHY THIS EXISTS
---------------
The register's Status column drifted badly once: all eight Tier-0 findings
shipped as counted `Fixed` bullets in `0.71.154` and the register went on
saying `open` for every one of them. A register that does not know what has
been done makes the work that remains unreadable, which is worse than
having no register.

So the column is corrected from what this says rather than from memory.
Every answer below is a specific thing in the source, not a reading of the
changelog -- except where the changelog IS the evidence (a user-visible
message), which is marked. Where a finding cannot be answered by looking,
it says so rather than guessing: a check that guesses is how this drifted
in the first place.

    py tools/verify_findings.py

Two groups, because the register has two rounds. The T rows come from the
product review (2026-09-10); the C rows from the consistency survey
(2026-09-25), which the earlier version of this file did not cover at all
-- twenty-five rows closed with nothing mechanical watching them, which is
exactly the shape of the drift above.
"""
import io
import os
import re
import sys

# The output carries em dashes and the app's own glyphs, and a Windows
# console defaults to cp1252, where printing one raises UnicodeEncodeError
# -- or, worse, prints a replacement character and looks like data.
sys.stdout.reconfigure(encoding="utf-8")

# Derived, not written down. This held one machine's absolute path, so the
# tool could not run anywhere else -- including in CI, and on hers.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read(*parts):
    with io.open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


# The note list left the hub for its own module (ui/note_list.py) on
# 2026-10-03; a check that asks the hub about the list reads both.
HUB = read("note_organizer.py") + read("noteorganizer", "ui", "note_list.py")
MODEL = read("noteorganizer", "core", "model.py")
STORAGE = read("noteorganizer", "core", "storage.py")
SHARING = read("noteorganizer", "core", "sharing.py")
SETTINGS_UI = read("noteorganizer", "ui", "settings_page.py")
CALENDAR_UI = read("noteorganizer", "ui", "calendar_view.py")
CALC_UI = read("noteorganizer", "ui", "calculator_panel.py")
DIALOGS_UI = read("noteorganizer", "ui", "dialogs.py")
SPEC = read("NoteOrganizer.spec")
CHANGELOG = read("CHANGELOG.md")
QA4 = read("qa", "qa4.py")
README = read("README.md")
CLAUDE_MD = read("CLAUDE.md")
ARCHITECTURE = read("docs", "ARCHITECTURE.md")
USER_GUIDE = read("docs", "USER_GUIDE.md")

# Every UI source a glyph could hide in, for the checks that ask whether a
# character appears anywhere rather than in one named place.
ALL_UI = HUB + SETTINGS_UI + CALENDAR_UI + CALC_UI + DIALOGS_UI

TIER_CHECKS = [
    ("T0-1", lambda: "checklist" in re.search(
        r"def note_is_empty.*?(?=\ndef )", MODEL, re.S).group(0),
     "note_is_empty counts the checklist"),
    ("T0-2", lambda: os.path.exists(
        os.path.join(ROOT, "noteorganizer", "core", "single_instance.py")),
     "core/single_instance.py holds the lock"),
    ("T0-3", lambda: "Importing your own backup brings your whole filing system back"
     in CHANGELOG, "shipped (changelog is the evidence: a user-visible route)"),
    ("T0-4", lambda: 'with_caret_line(self.body_text.get("1.0", "end-1c"))' in HUB,
     "the save reads the body unstripped"),
    ("T0-5", lambda: "_editor_state_has_content" in HUB,
     "one emptiness answer, consulted by every gate"),
    ("T0-6", lambda: '"_prev"' in MODEL,
     "_prev survives normalize_note"),
    ("T0-7", lambda: "MAX_CHECKLIST_ITEMS" in MODEL,
     "the checklist has a ceiling at the choke point"),
    ("T0-8", lambda: ".lnk" in HUB,
     ".lnk and its family are in the warn list"),

    ("T1-1", lambda: False, None),
    # render_calendar moved to ui/calendar_view.py with the module split;
    # asked of the hub alone, this row read "still open" for a fix that
    # was in the code all along. The guard must come before the rebuild,
    # inside the method, wherever the method lives.
    ("T1-2", lambda: re.search(
        r"def render_calendar\(self\):(?:(?!\n    def ).)*?"
        r"if not self\._calendar_is_showing\(\):", CALENDAR_UI + HUB, re.S)
     is not None,
     "render_calendar checks visibility before working"),
    ("T1-3", lambda: "json.dumps(" in STORAGE and "json.dump(" not in STORAGE,
     "the write builds one string"),
    ("T1-4", lambda: not re.search(r"^check\(f'refresh_note_list.*, True\)",
                                   QA4, re.M),
     "the perf check can fail"),

    ("T2-1", lambda: "A fresh install no longer opens with a maintenance report"
     in CHANGELOG, "shipped (changelog is the evidence: a user-visible message)"),
    ("T2-2", lambda: ("icon=" in SPEC and "icon=None" not in SPEC) or "version=" in SPEC,
     "the spec sets an icon or a version resource"),
    ("T2-3", lambda: "SetProcessDpiAware" in HUB or "shcore" in HUB,
     "DPI awareness is engaged"),
    # Resolved by correcting the documents, not the code (C-25): the file
    # chooser stays, because the system's own is the better one, and the
    # promises that said otherwise are gone. The check used to be
    # "filedialog not in HUB" -- the fix that was rejected -- so the row
    # could never close however true the documents became. A heading is
    # what makes the claim; ARCHITECTURE now quotes the old one in prose.
    ("T2-8", lambda: README.count("choosing a file or folder") >= 2
     and not re.search(r"^#+ .*[Nn]o native dialogs", ARCHITECTURE, re.M)
     and "clickable chip" not in USER_GUIDE,
     "the documents no longer promise no native dialogs or clickable "
     "Statistics chips"),
    ("T2-9", lambda: not re.search(r"30 days", HUB),
     "the delete confirmation no longer hardcodes 30 days"),

    ("T4-2", lambda: re.search(
        r"OVERRIDABLE_FIELDS\s*=\s*[\(\[{][^)\]}]*checklist", MODEL, re.S) is not None,
     "checklist is overridable per occurrence"),
    ("T4-3", lambda: "geometry" in HUB and re.search(
        r"save_setting\(\s*[\"']window", HUB) is not None,
     "the window geometry is remembered"),
    ("T4-6", lambda: re.search(r"backup.*(prune|keep|max)", STORAGE, re.I) is not None,
     "old backups are pruned"),
    # Asks for the USER GUIDE, not for a non-empty datas list. The icon
    # went into datas on 2026-09-12, which would have flipped this to
    # DONE while the guide still does not ship -- the exact kind of
    # almost-right check this file exists to replace.
    ("T4-7", lambda: "USER_GUIDE" in SPEC,
     "the build ships the User Guide"),
]

# Round 2, the consistency survey. Each asks for the MECHANISM the row's
# status cell names, so reverting the fix turns the row back to "still
# open" -- not for a word in the changelog, which would go on saying DONE
# forever once written.
SURVEY_CHECKS = [
    ("C-1", lambda: "_undo_bulk_category" in HUB,
     "the bulk category change offers a way back"),
    ("C-2", lambda: "Checklist item removed" in HUB,
     "removing a checklist item offers Undo"),
    ("C-3", lambda: "_retention_loss_warning" in SETTINGS_UI,
     "shortening the retention window says what it would destroy"),
    # Refuted rather than fixed: the label was worth changing and the
    # finding's reasoning was not. There is no repair to look for, so this
    # asks for the label the Changed shipped instead -- and asks for the
    # CONDITION with it, because the label alone would go on passing if it
    # were shown on a day row too, which is the thing the row got wrong.
    ("C-4", lambda: re.search(
        r'"🗑  Delete the whole series"\s*\n\s*if occurrence_date is None '
        r'and is_recurring\(note\)', HUB) is not None,
     "Delete names the series only where it means the series"),
    ("C-5", lambda: "_undo_day_clear" in CALENDAR_UI,
     "clearing a day's colour or markers can be undone"),
    ("C-6", lambda: "clean_up_everything" in SETTINGS_UI,
     "the all-groups duplicate cleanup is its own, louder button"),
    ("C-7", lambda: "_mini_popup_escape_bind" in DIALOGS_UI,
     "Escape backs out of the anchored popups"),
    ("C-8", lambda: "_open_note_from_grid" in CALENDAR_UI,
     "a day cell's note title opens that note"),
    # The cards stopped being widgets (they are drawn on the list's canvas),
    # so the keys moved from each card's bindings to the canvas's own.
    ("C-9", lambda: "_bulk_toggle_pin" in HUB and re.search(
        r'cv\.bind\("<Down>", lambda _e: self\._list_step\(1\)\)', HUB) is not None,
     "bulk Pin, and the note list answers the keyboard"),
    ("C-10", lambda: "Click a line to insert it into the note" in CALC_UI,
     "the calculator history says what clicking a line does"),
    ("C-11", lambda: "SEARCH_PLACEHOLDER" in HUB and "_refresh_search_clear" in HUB,
     "the search box has a paste menu and a clear affordance"),
    # The paste menu alone was not the fix: a pasted date scheduled no save
    # at all, because the field autosaves on <KeyRelease> and a paste fires
    # none. Both halves or the row re-opens on a new route.
    ("C-12", lambda: re.search(r"_add_paste_menu\(\s*self\.date_entry", HUB)
     is not None and re.search(r"date_entry\.bind\(\s*[\"']<<Paste>>", HUB)
     is not None,
     "the date field pastes, and a pasted date is saved"),
    ("C-13", lambda: "_all_revealed_ticked" in HUB,
     "the Share panel fills in a click, on what it actually rendered"),
    ("C-14", lambda: "Restore %d selected" in SETTINGS_UI
     and "_attach_dup_preview" in SETTINGS_UI,
     "the Trash restores a batch, and a row can be read before deciding"),
    ("C-15", lambda: '"note_sort"' in HUB and '"note_filter"' in HUB
     and "_keep_filter_valid" in HUB,
     "sort and filter persist, and a stale filter falls back"),
    ("C-16", lambda: "MAX_DAY_MARKERS" in CALENDAR_UI
     and "Three is the most a day can show" in CALENDAR_UI,
     "the day-marker cap dims the rest and says why"),
    ("C-17", lambda: "_ctx_move_to_category" in HUB,
     "a note's own menu can change its category"),
    ("C-18", lambda: "ICON_TIPS" in SETTINGS_UI,
     "the Settings glyphs explain themselves on hover"),
    ("C-19", lambda: "editor_comments_expanded" in HUB,
     "the comments box remembers its size"),
    # Asks for the absence of the fullwidth plus anywhere a widget is
    # built, rather than for the presence of the ASCII one: the ASCII plus
    # was always there too, so its presence proves nothing.
    ("C-20", lambda: "＋" not in ALL_UI,
     "one plus character, everywhere"),
    ("C-21", lambda: re.search(r'_icon_button\(\s*row,\s*"trash"', SETTINGS_UI)
     is not None,
     "the template editor's bin is drawn, like every other"),
    ("C-22", lambda: re.search(
        r"def _highlight_swatch_column.*?Pick a highlight color",
        HUB, re.S) is not None,
     "the highlight picker has a title, from the shared function"),
    ("C-23", lambda: 'text="Sort"' in HUB and 'text="Show"' in HUB,
     "the two dropdowns say which is which"),
    ("C-24", lambda: "SHARE_ATTACHMENT_WARNING" in HUB,
     "one attachments sentence, used by both share areas"),
    # The four claims C-25 corrected. `_add_row` was deleted rather than
    # marked unused, so its absence is the witness; and the native-dialogs
    # sentence was corrected in three places, two of them in README.
    ("C-25", lambda: "def _add_row" not in SETTINGS_UI
     and README.count("choosing a file or folder") >= 2
     and "recent places" in CLAUDE_MD,
     "the dead helper is gone and the dialogs sentence is true"),
]


def run(title, checks):
    open_rows, unanswerable = [], []
    print(title)
    print("%-7s %s" % ("#", "verdict"))
    print("-" * 88)
    for tag, test, done_means in checks:
        if done_means is None:
            print("%-7s cannot be answered by looking — needs a measurement" % tag)
            unanswerable.append(tag)
            continue
        try:
            done = bool(test())
        except Exception as exc:
            print("%-7s ? %s: %s" % (tag, type(exc).__name__, exc))
            unanswerable.append(tag)
            continue
        print("%-7s %s" % (tag, ("DONE — " + done_means) if done else "still open"))
        if not done:
            open_rows.append(tag)
    print()
    return open_rows, unanswerable


tier_open, tier_unknown = run("THE PRODUCT REVIEW (T rows)", TIER_CHECKS)
survey_open, survey_unknown = run("THE CONSISTENCY SURVEY (C rows)", SURVEY_CHECKS)

print("-" * 88)
print("T rows: %d still open%s" % (
    len(tier_open), (" — " + ", ".join(tier_open)) if tier_open else ""))
print("C rows: %d still open%s" % (
    len(survey_open), (" — " + ", ".join(survey_open)) if survey_open else ""))
unknown = tier_unknown + survey_unknown
if unknown:
    print("Not answerable by looking: %s" % ", ".join(unknown))
print()
print("Correct the register's Status column from this, not from memory.")
