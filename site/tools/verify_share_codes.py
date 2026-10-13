"""Hold the demo's share codes to the app's own reader, and the other way.

    py tools/verify_share_codes.py <photographs folder> [--repo ../NoteOrganizer]

1. Writes share_codes_from_app.json: codes made by the app's own
   encode_share_code -- its real welcome note, a table, a checklist,
   colours -- with what the demo must show for each. tools/check_demo.mjs
   reads them in the browser.
2. Reads share_codes_from_demo.json (written by tools/check_demo.mjs) and
   puts every code through the app's decode_share_code and normalize_note,
   the first two steps of its Import code box, checking that nothing the
   demo meant to send is dropped or changed.

The app's package is copied into a fresh temporary folder and imported
from there, with APPDATA pointed at empty folders, so nothing here can
reach the repository or anyone's notebook. Run it twice: before
check_demo.mjs (to write the app's codes) and after (to read the demo's).
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    # Titles carry emoji; a Windows console's default code page cannot print them.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--repo", default=os.path.join(HERE, "..", "..", "NoteOrganizer"))
    args = parser.parse_args()
    repo = os.path.abspath(args.repo)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    work = tempfile.mkdtemp(prefix="no-share-verify-")
    try:
        shutil.copytree(os.path.join(repo, "noteorganizer"), os.path.join(work, "noteorganizer"))
        for name in ("APPDATA", "LOCALAPPDATA"):
            folder = os.path.join(work, name.lower())
            os.makedirs(folder)
            os.environ[name] = folder
        os.chdir(work)
        sys.path.insert(0, work)
        assert os.path.abspath(sys.path[0]) == os.path.abspath(work)
        return run(out)
    finally:
        os.chdir(HERE)
        shutil.rmtree(work, ignore_errors=True)


def run(out):
    from noteorganizer.core.sharing import encode_share_code, decode_share_code
    from noteorganizer.core.model import normalize_note
    from noteorganizer.core.formatting import normalize_formatting
    from noteorganizer.core.recurrence import normalize_recurrence
    from noteorganizer.core.tables import is_table_row, is_separator_row
    from noteorganizer.core.welcome import build_welcome_note, TITLE

    failures = []

    def check(name, ok, detail=""):
        print(("ok   " if ok else "FAIL ") + name + ("" if ok or not detail else "  -- " + detail))
        if not ok:
            failures.append(name)

    # ---- 1. Codes from the app, for the demo to read ----
    welcome = build_welcome_note()
    welcome.update({"category": "General", "uid": "welcome-from-the-app"})
    table_note = {
        "uid": "table-from-the-app", "title": "Packing", "category": "Personal",
        "body": "For the weekend.\n| Item | Bag |\n| --- | --- |\n| Charger | Backpack |\n| Boots | Car |",
        "formatting": [], "checklist": [{"text": "Passports", "done": True}, {"text": "Snacks", "done": False}],
        "date": "2026-10-17",
    }
    styled = {
        "uid": "styled-from-the-app", "title": "Colours and styles", "category": "Ideas",
        "body": "Bold, italic, both, underlined, struck, red, highlighted.",
        "formatting": [
            {"start": 0, "end": 4, "style": "bold"},
            {"start": 6, "end": 12, "style": "italic"},
            {"start": 14, "end": 18, "style": "bold_italic"},
            {"start": 20, "end": 30, "style": "underline"},
            {"start": 32, "end": 38, "style": "strike"},
            {"start": 40, "end": 43, "style": "text_color", "value": "#e63946"},
            {"start": 45, "end": 56, "style": "highlight", "value": "#fff3b0"},
        ],
        "recurrence": {"freq": "monthly", "interval": 1}, "date": "2026-10-01",
    }
    # What the demo must show bold: the welcome note's own bold runs, read
    # from its spans rather than retyped here.
    bold_runs = [welcome["body"][s["start"]:s["end"]] for s in welcome["formatting"] if s["style"] == "bold"]
    app_codes = {
        "welcome": {"code": encode_share_code(welcome),
                    "expect": {"title": TITLE, "bold": [bold_runs[0], bold_runs[1], bold_runs[-1]]}},
        "table": {"code": encode_share_code(table_note),
                  "expect": {"title": "Packing", "rows": 3, "items": 2}},
        "styles": {"code": encode_share_code(styled),
                   "expect": {"title": "Colours and styles", "bold": ["Bold", "both"]}},
    }
    with open(os.path.join(out, "share_codes_from_app.json"), "w", encoding="utf-8") as f:
        json.dump(app_codes, f, ensure_ascii=False, indent=1)
    print("wrote %d codes made by the app's encoder" % len(app_codes))

    # ---- 2. Codes from the demo, through the app's reader ----
    path = os.path.join(out, "share_codes_from_demo.json")
    if not os.path.exists(path):
        print("no share_codes_from_demo.json yet: run tools/check_demo.mjs, then this again")
        return 0 if not failures else 1
    with open(path, encoding="utf-8") as f:
        demo_codes = json.load(f)
    for title, code in demo_codes.items():
        try:
            shared = decode_share_code(code)
        except ValueError as e:
            check("the app reads the demo's code for %r" % title, False, str(e))
            continue
        raw = shared[0]
        note = normalize_note(dict(raw))
        check("the app reads the demo's code for %r" % title, note["title"] == title,
              "title came back as %r" % note["title"])
        spans = raw.get("formatting") or []
        kept = normalize_formatting(spans)
        check("  every style span survives the app's checks", len(kept) == len(spans),
              "%d sent, %d kept" % (len(spans), len(kept)))
        for span in spans:
            if span["end"] > len(note["body"]):
                check("  spans stay inside the text", False, repr(span))
                break
        check("  the checklist arrives whole", len(note["checklist"]) == len(raw.get("checklist") or []))
        if raw.get("recurrence", {}).get("freq"):
            check("  the repeat rule arrives as sent",
                  note["recurrence"] == normalize_recurrence(raw["recurrence"]) and note["recurrence"]["freq"],
                  repr(note["recurrence"]))
        lines = note["body"].split("\n")
        if any(line.startswith("|") for line in lines):
            rows = [l for l in lines if is_table_row(l)]
            seps = [l for l in lines if is_separator_row(l)]
            check("  the table is a table to the app", len(rows) >= 2 and len(seps) == 1,
                  "%d rows, %d separators" % (len(rows), len(seps)))
        if title == "Team stand-up":
            check("  weekly on Monday", note["recurrence"]["freq"] == "weekly" and note["recurrence"]["weekdays"] == [0],
                  repr(note["recurrence"]))
        if title == "Plant the tulips":
            check("  bold came across", any(s["style"] == "bold" for s in note["formatting"]), repr(note["formatting"]))
    print("\n%s" % ("all checks passed" if not failures else "%d check(s) failed" % len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
