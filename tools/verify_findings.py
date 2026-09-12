"""Ask the code, one finding at a time, what is actually still true.

The register marks all 38 findings open or deciding, including the eight
that shipped as 0.71.154. Every answer below is a specific thing in the
source, not a reading of the changelog -- except where the changelog IS
the evidence (a user-visible message), which is marked.

Where a finding cannot be answered by looking, it says so rather than
guessing. A register that guesses is how this drifted in the first place.
"""
import io
import os
import re

ROOT = r"D:\Projects\NoteOrganizer"


def read(*parts):
    with io.open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


HUB = read("note_organizer.py")
MODEL = read("noteorganizer", "core", "model.py")
STORAGE = read("noteorganizer", "core", "storage.py")
SHARING = read("noteorganizer", "core", "sharing.py")
SPEC = read("NoteOrganizer.spec")
CHANGELOG = read("CHANGELOG.md")
QA4 = read("qa", "qa4.py")
README = read("README.md")

CHECKS = [
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
    ("T1-2", lambda: re.search(r"def render_calendar.*?\n(.{0,400})", HUB, re.S)
     and ("_calendar_is_showing" in HUB or "_is_calendar_visible" in HUB)
     and re.search(r"def render_calendar\b.*?(_calendar_is_showing|"
                   r"_is_calendar_visible)", HUB, re.S) is not None,
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
    ("T2-8", lambda: "filedialog" not in HUB,
     "no native file dialogs remain"),
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

print("%-7s %s" % ("#", "verdict"))
print("-" * 88)
for tag, test, done_means in CHECKS:
    if done_means is None:
        print("%-7s cannot be answered by looking — needs a measurement" % tag)
        continue
    try:
        done = bool(test())
    except Exception as exc:
        print("%-7s ? %s" % (tag, exc))
        continue
    print("%-7s %s" % (tag, ("DONE — " + done_means) if done else "still open"))
