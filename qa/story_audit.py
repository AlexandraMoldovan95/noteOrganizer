"""An audit, not a regression suite: paths nobody has walked this way.

WHY THIS EXISTS
---------------
Four user-visible bugs shipped in one week, and none was reachable by
the suite. Each needed one of four things a question cannot express:

    a RESTART between two steps
    a SEQUENCE, where the second step reads what the first left
    a SECOND VISIT to a page built earlier
    a WHAT-HAPPENS-NEXT, where the save after the change undoes it

`story_note_travels.py` proves those four shapes catch the bugs they
were written for. This file asks the harder question: **do they catch
anything nobody has found yet?** Its chapters are aimed at surfaces that
have never been walked in those shapes -- settings that must survive a
restart, attachments outliving their note, every Settings section on a
second visit, a bulk action followed by ordinary typing, a per-day
recurrence edit followed by a series edit.

A green run here is not proof of correctness. It is the honest result of
looking somewhere nobody had looked, and it is recorded as such.

    py qa/story_audit.py
"""
import io
import json
import os
import shutil
import subprocess
import sys

RESULTS = "audit_results.json"


def _root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CHAPTERS = [
    (1, "What I chose stays chosen after I close the app"),
    (2, "An attachment outlives the note it belongs to"),
    (3, "Every Settings section, on a second visit"),
    (4, "A bulk action, and then I keep typing"),
    (5, "One day edited on its own, then the whole series"),
    (6, "The trash countdown is read from what was written, not from the session"),
]


def drive():
    sys.stdout.reconfigure(encoding="utf-8")
    root = _root()
    sys.path.insert(0, os.path.join(root, "tools"))
    import guest  # this machine's turn and the memory ceiling (tools/guest.py)
    for line in guest.settle(label="story_audit"):
        print(line)
    # Marked as this run's: an audit killed halfway is removed by the next run.
    work = guest.scratch("audit-")
    shutil.copy2(os.path.join(root, "note_organizer.py"), work)
    shutil.copytree(os.path.join(root, "noteorganizer"),
                    os.path.join(work, "noteorganizer"))
    for name in (os.path.join("qa", "_qa_support.py"), os.path.join("tools", "guest.py")):
        shutil.copy2(os.path.join(root, name), work)
    shutil.copy2(os.path.abspath(__file__), os.path.join(work, "story_audit.py"))
    io.open(os.path.join(work, "notes_data.json"), "w", encoding="utf-8").write("[]")
    io.open(os.path.join(work, "settings.json"), "w", encoding="utf-8").write(
        json.dumps({"cleanup_done": True, "reclaimed_from_appdata": True}))

    print("the audit is running in: %s" % work)
    print()
    rows = []
    for number, title in CHAPTERS:
        print("--- chapter %d: %s" % (number, title))
        # A fresh notebook for every chapter. They used to share one,
        # and chapter five then failed on what chapter four had left --
        # a recurrence bug that did not exist, nearly reported as real.
        io.open(os.path.join(work, "notes_data.json"), "w",
                encoding="utf-8").write("[]")
        io.open(os.path.join(work, "trash.json"), "w",
                encoding="utf-8").write("[]")
        io.open(os.path.join(work, "settings.json"), "w",
                encoding="utf-8").write(json.dumps(
                    {"cleanup_done": True, "reclaimed_from_appdata": True}))
        try:
            run = subprocess.run(
                [sys.executable, "story_audit.py", "--chapter", str(number)],
                cwd=work, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600)
            said = (run.stdout or "") + (run.stderr or "")
        except subprocess.TimeoutExpired as hung:
            # A hang is this chapter's finding, named, and the audit goes on.
            said = "".join(v.decode("utf-8", "replace") if isinstance(v, bytes) else (v or "")
                           for v in (hung.stdout, hung.stderr))
            rows.append(("chapter %d finished within 600 s" % number, False, "HANG"))
            print("    HANG: chapter %d did not finish within 600 s" % number)
            for line in said.strip().splitlines()[-8:]:
                print("      | %s" % line)
            _clear(work)
            continue
        found = _read(work)
        rows.extend(found)
        for name, ok, detail in found:
            print("    %s %s%s" % ("PASS" if ok else "FAIL", name,
                                   "" if ok else "\n         <- %s" % detail))
        if not found:
            print("    THE CHAPTER SAID NOTHING (did it crash?)")
            for line in said.strip().splitlines()[-8:]:
                print("      | %s" % line)
            rows.append(("chapter %d ran" % number, False, "no results"))
        _clear(work)

    failed = [name for name, ok, _ in rows if not ok]
    print()
    print("AUDIT: %d checks, %d findings" % (len(rows), len(failed)))
    if failed:
        for name in failed:
            print("   * %s" % name)
        # The notebook it walked stays to be read; the app's copy goes, and
        # a later run removes the rest after guest.KEPT_DAYS.
        for name in ("note_organizer.py", "noteorganizer", "_qa_support.py", "guest.py",
                     "story_audit.py", "__pycache__"):
            path = os.path.join(work, name)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.exists(path):
                os.remove(path)
        guest.keep(work, "story_audit: the notebook of a failed audit")
        print("The directory was left in place: %s" % work)
        return 1
    guest.remove(work)
    print("Nothing new. That does not mean correct -- it means nothing is here.")
    return 0


def _read(work):
    path = os.path.join(work, RESULTS)
    if not os.path.exists(path):
        return []
    try:
        return [tuple(r) for r in json.load(io.open(path, encoding="utf-8"))]
    except Exception:
        return []


def _clear(work):
    path = os.path.join(work, RESULTS)
    if os.path.exists(path):
        os.remove(path)


class Chapter:
    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=""):
        self.rows.append((name, bool(ok), str(detail)[:300]))

    def save(self):
        io.open(RESULTS, "w", encoding="utf-8").write(
            json.dumps(self.rows, ensure_ascii=False))


def _app():
    import tkinter as tk
    sys.path.insert(0, ".")
    import note_organizer as NO
    from _qa_support import pin_popup_visibility
    pin_popup_visibility(NO)
    app = NO.NoteOrganizer()
    app._poll_active_dirty = lambda: None
    app.show_info = lambda *a, **k: True
    app.show_warning = lambda *a, **k: True
    app.ask_yes_no = lambda *a, **k: True
    app.geometry("1150x820")
    app.update()
    return tk, NO, app


def _seed(NO, app, count=4):
    app.notes = [NO.normalize_note({
        "id": i + 1, "title": "Note %d" % (i + 1),
        "body": "the body of note %d" % (i + 1), "category": "General"})
        for i in range(count)]
    app.save_notes()
    app.refresh_note_list()
    app.update()


# ---- 1: choices must survive the app closing -------------------------

def chapter_1():
    tk, NO, app = _app()
    story = Chapter()
    _seed(NO, app)
    NO.CATEGORY_COLORS.setdefault("School", "#4477aa")

    app.set_theme(NO.LIGHT_THEMES[-1])
    app.sort_var.set(next(o for o in app.SORT_OPTIONS if o.startswith("Title Z")))
    app.filter_var.set("School")
    app.group_by_category.set(True)
    app._on_toggle_group_by_category()
    app.day_colors["2026-09-20"] = "#ff8800"
    app._persist_day_colors()
    app.open_note_in_tab(app.notes[2])
    app.refresh_note_list()
    app.update()
    chosen = {"theme": app.theme_name, "sort": app.sort_var.get(),
              "filter": app.filter_var.get(), "open": app.selected_note_id}
    app.destroy()

    tk2, NO2, again = _app()
    story.check("the chosen theme comes back", again.theme_name == chosen["theme"],
                "%r -> %r" % (chosen["theme"], again.theme_name))
    # Sort and filter ARE remembered, since 0.76.198 (C-15). This comment
    # used to say the opposite and the check below asserted the default
    # coming back -- written when that was true, and left alone when the
    # app changed under it. A check that pins the behaviour a release
    # deliberately replaced is worse than no check: it either fails for
    # the right reason and gets explained away, or passes by accident.
    story.check("the sort I left the list on comes back",
                again.sort_var.get() == chosen["sort"],
                "%r -> %r" % (chosen["sort"], again.sort_var.get()))
    # The filter is the other half of C-15, and this is its guard rather
    # than its promise: "School" existed only as a runtime entry in the
    # first process, so on the way back in it names a category this
    # notebook does not have, and the honest answer is All rather than a
    # filter that hides everything.
    story.check("a filter naming a category that is gone falls back to All",
                again.filter_var.get() == "All",
                "%r -> %r" % (chosen["filter"], again.filter_var.get()))
    story.check("grouping by category comes back",
                bool(again.group_by_category.get()))
    story.check("the painted day comes back",
                again.day_colors.get("2026-09-20") == "#ff8800",
                repr(again.day_colors))
    story.check("the note open last time opens again",
                again.selected_note_id == chosen["open"],
                "%r -> %r" % (chosen["open"], again.selected_note_id))
    again.destroy()
    story.save()


# ---- 2: an attachment outliving its note -----------------------------

def chapter_2():
    tk, NO, app = _app()
    story = Chapter()
    _seed(NO, app, 2)

    source = os.path.abspath("a_file.txt")
    io.open(source, "w", encoding="utf-8").write("test content")
    app.open_note_in_tab(app.notes[0])
    app.update()
    # The real route asks the OS for the file; replacing that ask is the
    # ONLY thing stubbed -- everything after it is the app's own code.
    # (The first version of this chapter called a function that does not
    # exist, attached nothing, and then reported that attaching is
    # broken. An audit that invents its own API invents its findings.)
    import tkinter.filedialog as _fd
    _fd.askopenfilenames = lambda **k: (source,)
    app.add_attachment()
    app.save_current_note(auto=False)
    app.update()
    note = app.find_note(app.notes[0]["id"])
    stored = [a.get("stored_as") for a in (note.get("attachments") or [])]
    story.check("the file is attached to the note", bool(stored), repr(note.get("attachments")))
    folder = os.path.join(os.getcwd(), "attachments")
    on_disk = [f for f in os.listdir(folder)] if os.path.isdir(folder) else []
    story.check("...and lands in the attachments folder", bool(on_disk), repr(on_disk))

    app._delete_note(note, None)
    app.update()
    still = [f for f in os.listdir(folder)] if os.path.isdir(folder) else []
    story.check("deleting the note does NOT delete the file (it can be undone)",
                still == on_disk, "%r -> %r" % (on_disk, still))
    app.destroy()

    tk2, NO2, again = _app()
    trashed = [e for e in again.trash if (e.get("attachments") or [])]
    story.check("after a restart, the trash still remembers the attachment",
                bool(trashed), repr([e.get("title") for e in again.trash]))
    if trashed:
        again.notes, again.trash = NO2.core_restore_from_trash(
            again.notes, again.trash, trashed[0])
        again.save_notes()
        again.update()
        back = again.notes[-1]
        story.check("the restored note has its attachment",
                    bool(back.get("attachments")), repr(back.get("attachments")))
        names = [a.get("stored_as") for a in (back.get("attachments") or [])]
        story.check("...and the file really is on disk",
                    all(os.path.exists(os.path.join(folder, n)) for n in names if n),
                    repr(names))
    again.destroy()
    story.save()


# ---- 3: every Settings section, on a second visit --------------------

def chapter_3():
    tk, NO, app = _app()
    story = Chapter()
    _seed(NO, app, 3)
    NO.CATEGORY_COLORS["OldFiling"] = "#993333"
    NO.save_templates([{"name": "An old template", "title": "T", "body": "b",
                        "comments": "", "category": "General", "checklist": []}])
    app.templates = NO.load_templates()

    def texts(widget, out=None):
        if out is None:
            out = []
        for child in widget.winfo_children():
            if isinstance(child, tk.Label):
                out.append(str(child.cget("text")))
            texts(child, out)
        return out

    app.show_settings_page()
    app.update()
    for key in ("categories", "templates", "trash", "duplicates"):
        app.toggle_settings_panel(key)
        app.update()
    app.hide_settings_page()
    app.update()

    # Change the world behind every one of them.
    NO.CATEGORY_COLORS.pop("OldFiling", None)
    NO.CATEGORY_COLORS["JustAdded"] = "#227744"
    app.notes.append(NO.normalize_note({"id": 90, "title": "Twin",
                                        "body": "idem", "category": "General"}))
    app.notes.append(NO.normalize_note({"id": 91, "title": "Twin",
                                        "body": "idem", "category": "General"}))
    app._delete_note(app.notes[0], None)
    app.save_notes()
    app.templates.append(NO.normalize_template({"name": "A template added since",
                                                "title": "T2", "body": "b2"}))
    NO.save_templates(app.templates)
    app.update()

    app.show_settings_page()
    app.update()
    # Arriving rebuilds the section you LAND on; the others rebuild when
    # you go to them, which is the whole design. So walk there, the way
    # a person would, instead of reading a panel built on the last visit.
    app.toggle_settings_panel("categories")
    app.update()
    seen = texts(getattr(app, "settings_categories_panel", app))
    story.check("Categories, on a second visit, shows the new category",
                any("JustAdded" in t for t in seen),
                "on screen: %s" % [t[:20] for t in seen if t][:6])
    story.check("...and no longer shows the deleted one",
                not any("OldFiling" in t for t in seen))
    app.toggle_settings_panel("templates")
    app.update()
    shown = texts(app.settings_templates_panel)
    story.check("Templates, on a second visit, shows the template added in the meantime",
                any("A template added since" in t for t in shown)
                and any("An old template" in t for t in shown),
                "on screen: %s" % [t[:24] for t in shown if t][:6])
    app.toggle_settings_panel("trash")
    app.update()
    story.check("Recently deleted shows the note deleted in the meantime",
                any("Note 1" in t for t in texts(app.settings_trash_panel)))
    app.toggle_settings_panel("duplicates")
    app.update()
    story.check("Duplicates shows the pair that appeared in the meantime",
                any("Twin" in t for t in texts(app.settings_duplicates_panel)))
    app.destroy()
    story.save()


# ---- 4: a bulk action, then ordinary typing --------------------------

def chapter_4():
    tk, NO, app = _app()
    story = Chapter()
    _seed(NO, app, 4)
    NO.CATEGORY_COLORS.setdefault("Errands", "#775599")

    app.open_note_in_tab(app.notes[0])
    app.update()
    app.selection_mode = True
    app.selected_note_ids = {n["id"] for n in app.notes[:3]}
    # Through the popup's own row, never by writing the categories here:
    # doing the app's job in the check is how this chapter went on
    # reporting the bug for an hour after it had been fixed.
    app._bulk_change_category()
    app.update()
    row = None

    def find_row(widget):
        nonlocal row
        for child in widget.winfo_children():
            if isinstance(child, tk.Label) and \
                    str(child.cget("text")).strip() == "Errands":
                row = child
                return
            find_row(child)

    popup = getattr(app, "_mini_popup", None)
    if popup is not None and popup.winfo_exists():
        find_row(popup)
    story.check("the popup offers the category by name", row is not None)
    if row is not None:
        row.event_generate("<Button-1>", x=3, y=3)
        app.update()
    story.check("the bulk action reaches the disk",
                all(n["category"] == "Errands" for n in app.notes[:3]),
                repr([n["category"] for n in app.notes[:3]]))

    # And then the user carries on typing in the note that was open.
    app.body_text.insert("end", " and I carry on typing")
    app._flush_autosave()
    app.update()
    after = json.load(io.open("notes_data.json", encoding="utf-8"))
    first = next(n for n in after if n["id"] == app.notes[0]["id"])
    story.check("typing afterwards does not undo the bulk change",
                first["category"] == "Errands", repr(first["category"]))
    story.check("...and the text typed afterwards really was saved",
                "carry on typing" in first["body"], repr(first["body"][:60]))
    app.destroy()
    story.save()


# ---- 5: one day edited, then the whole series ------------------------

def chapter_5():
    tk, NO, app = _app()
    story = Chapter()
    app.notes = [NO.normalize_note({
        "id": 1, "title": "Standup", "body": "the series text",
        "category": "General", "date": "2026-09-07",
        "recurrence": {"freq": "weekly", "interval": 1, "weekdays": [0]}})]
    app.save_notes()
    app.update()

    note = app.notes[0]
    note.setdefault("overrides", {})["2026-09-14"] = {
        "title": "Standup", "body": "only this day is different",
        "comments": "", "category": "General", "color": ""}
    app.save_notes()
    app.update()

    app.open_note_in_tab(note)
    app.update()
    app.body_text.delete("1.0", "end")
    app.body_text.insert("1.0", "the series text, changed")
    app.save_current_note(auto=False)
    app.update()
    app.destroy()

    tk2, NO2, again = _app()
    back = again.notes[0]
    story.check("the series received the new text",
                "changed" in back["body"], repr(back["body"][:50]))
    story.check("the day edited on its own kept its own text",
                (back.get("overrides") or {}).get("2026-09-14", {}).get("body")
                == "only this day is different",
                repr(back.get("overrides")))
    story.check("and the recurrence stayed whole",
                (back.get("recurrence") or {}).get("freq") == "weekly",
                repr(back.get("recurrence")))
    again.destroy()
    story.save()


# ---- 6: the trash countdown across a restart -------------------------

def chapter_6():
    tk, NO, app = _app()
    story = Chapter()
    _seed(NO, app, 2)
    app._delete_note(app.notes[0], None)
    app.update()
    entry = app.trash[0]
    stamp = entry.get("deleted_at")
    story.check("deleting writes the moment into the trash", bool(stamp), repr(entry))
    app.destroy()

    tk2, NO2, again = _app()
    back = again.trash[0] if again.trash else {}
    story.check("after a restart, the moment of deletion is the same",
                back.get("deleted_at") == stamp,
                "%r -> %r" % (stamp, back.get("deleted_at")))
    left = NO2.core_days_left_in_trash(back.get("deleted_at"))
    story.check("...and the days left are counted from it",
                isinstance(left, int) and 0 < left <= NO2.trash_retention_days(),
                repr(left))
    again.destroy()
    story.save()


CHAPTER_FNS = {1: chapter_1, 2: chapter_2, 3: chapter_3,
               4: chapter_4, 5: chapter_5, 6: chapter_6}


if __name__ == "__main__":
    if "--chapter" in sys.argv:
        number = int(sys.argv[sys.argv.index("--chapter") + 1])
        # A ceiling of its own before the app is built, inside the driver's
        # turn (guest.py, copied beside this file into the scratch).
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import guest
        guest.settle(label="story_audit chapter %d" % number)
        try:
            CHAPTER_FNS[number]()
        except Exception:
            import traceback
            traceback.print_exc()
            io.open(RESULTS, "w", encoding="utf-8").write(json.dumps(
                [["chapter %d ran to the end" % number, False,
                  traceback.format_exc().strip().splitlines()[-1]]],
                ensure_ascii=False))
        sys.exit(0)
    sys.exit(drive())
