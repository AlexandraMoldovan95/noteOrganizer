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
import tempfile

RESULTS = "audit_results.json"


def _root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CHAPTERS = [
    (1, "Ce am ales ramane ales dupa ce inchid aplicatia"),
    (2, "Un atasament traieste mai mult decat notita lui"),
    (3, "Fiecare sectiune din Settings, la a doua vizita"),
    (4, "O actiune in masa, si apoi scriu mai departe"),
    (5, "O zi editata separat, apoi seria intreaga"),
    (6, "Numaratoarea din cos se socoteste din ce e scris, nu din sesiune"),
]


def drive():
    sys.stdout.reconfigure(encoding="utf-8")
    root = _root()
    work = tempfile.mkdtemp(prefix="audit-")
    shutil.copy2(os.path.join(root, "note_organizer.py"), work)
    shutil.copytree(os.path.join(root, "noteorganizer"),
                    os.path.join(work, "noteorganizer"))
    shutil.copy2(os.path.join(root, "qa", "_qa_support.py"), work)
    shutil.copy2(os.path.abspath(__file__), os.path.join(work, "story_audit.py"))
    io.open(os.path.join(work, "notes_data.json"), "w", encoding="utf-8").write("[]")
    io.open(os.path.join(work, "settings.json"), "w", encoding="utf-8").write(
        json.dumps({"cleanup_done": True, "reclaimed_from_appdata": True}))

    print("auditul ruleaza in: %s" % work)
    print()
    rows = []
    for number, title in CHAPTERS:
        print("--- capitolul %d: %s" % (number, title))
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
        run = subprocess.run(
            [sys.executable, "story_audit.py", "--chapter", str(number)],
            cwd=work, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600)
        found = _read(work)
        rows.extend(found)
        for name, ok, detail in found:
            print("    %s %s%s" % ("PASS" if ok else "FAIL", name,
                                   "" if ok else "\n         <- %s" % detail))
        if not found:
            print("    CAPITOLUL NU A SPUS NIMIC (a crapat?)")
            for line in (run.stdout + run.stderr).strip().splitlines()[-8:]:
                print("      | %s" % line)
            rows.append(("capitolul %d a rulat" % number, False, "fara rezultate"))
        _clear(work)

    failed = [name for name, ok, _ in rows if not ok]
    print()
    print("AUDIT: %d verificari, %d gasiri" % (len(rows), len(failed)))
    if failed:
        for name in failed:
            print("   * %s" % name)
        print("Directorul a ramas pe loc: %s" % work)
        return 1
    shutil.rmtree(work, ignore_errors=True)
    print("Nimic nou. Asta nu inseamna corect -- inseamna ca aici nu e nimic.")
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
        "id": i + 1, "title": "Nota %d" % (i + 1),
        "body": "corpul notitei %d" % (i + 1), "category": "General"})
        for i in range(count)]
    app.save_notes()
    app.refresh_note_list()
    app.update()


# ---- 1: choices must survive the app closing -------------------------

def chapter_1():
    tk, NO, app = _app()
    story = Chapter()
    _seed(NO, app)
    NO.CATEGORY_COLORS.setdefault("Scoala", "#4477aa")

    app.set_theme(NO.LIGHT_THEMES[-1])
    app.sort_var.set(next(o for o in app.SORT_OPTIONS if o.startswith("Title Z")))
    app.filter_var.set("Scoala")
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
    story.check("tema aleasa se intoarce", again.theme_name == chosen["theme"],
                "%r -> %r" % (chosen["theme"], again.theme_name))
    # Sort and filter are NOT remembered, and the app never claimed
    # they were: it writes the theme, the open note, the day colours and
    # the grouping, and nothing else. Asserting a promise nobody made is
    # how an audit manufactures its own findings. What IS worth pinning
    # is that they come back at their honest defaults rather than at
    # something half-restored.
    story.check("sortarea porneste de la valoarea implicita, nu pe jumatate",
                again.sort_var.get() == again.SORT_OPTIONS[0],
                "%r" % again.sort_var.get())
    story.check("filtrul porneste de la Toate, nu pe o categorie fantoma",
                again.filter_var.get() == "All",
                "%r" % again.filter_var.get())
    story.check("gruparea pe categorii se intoarce",
                bool(again.group_by_category.get()))
    story.check("ziua colorata se intoarce",
                again.day_colors.get("2026-09-20") == "#ff8800",
                repr(again.day_colors))
    story.check("notita deschisa ultima oara se redeschide",
                again.selected_note_id == chosen["open"],
                "%r -> %r" % (chosen["open"], again.selected_note_id))
    again.destroy()
    story.save()


# ---- 2: an attachment outliving its note -----------------------------

def chapter_2():
    tk, NO, app = _app()
    story = Chapter()
    _seed(NO, app, 2)

    source = os.path.abspath("un_fisier.txt")
    io.open(source, "w", encoding="utf-8").write("continut de test")
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
    story.check("fisierul se ataseaza notitei", bool(stored), repr(note.get("attachments")))
    folder = os.path.join(os.getcwd(), "attachments")
    on_disk = [f for f in os.listdir(folder)] if os.path.isdir(folder) else []
    story.check("...si ajunge in folderul de atasamente", bool(on_disk), repr(on_disk))

    app._delete_note(note, None)
    app.update()
    still = [f for f in os.listdir(folder)] if os.path.isdir(folder) else []
    story.check("stergerea notitei NU sterge fisierul (e recuperabila)",
                still == on_disk, "%r -> %r" % (on_disk, still))
    app.destroy()

    tk2, NO2, again = _app()
    trashed = [e for e in again.trash if (e.get("attachments") or [])]
    story.check("dupa repornire, cosul tine minte atasamentul",
                bool(trashed), repr([e.get("title") for e in again.trash]))
    if trashed:
        again.notes, again.trash = NO2.core_restore_from_trash(
            again.notes, again.trash, trashed[0])
        again.save_notes()
        again.update()
        back = again.notes[-1]
        story.check("notita restaurata isi are atasamentul",
                    bool(back.get("attachments")), repr(back.get("attachments")))
        names = [a.get("stored_as") for a in (back.get("attachments") or [])]
        story.check("...si fisierul chiar exista pe disc",
                    all(os.path.exists(os.path.join(folder, n)) for n in names if n),
                    repr(names))
    again.destroy()
    story.save()


# ---- 3: every Settings section, on a second visit --------------------

def chapter_3():
    tk, NO, app = _app()
    story = Chapter()
    _seed(NO, app, 3)
    NO.CATEGORY_COLORS["DeSters"] = "#993333"
    app.save_templates([{"name": "Sablon vechi", "title": "T", "body": "b",
                         "comments": "", "category": "General", "checklist": []}]) \
        if hasattr(app, "save_templates") else None

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
    NO.CATEGORY_COLORS.pop("DeSters", None)
    NO.CATEGORY_COLORS["ProaspatAdaugata"] = "#227744"
    app.notes.append(NO.normalize_note({"id": 90, "title": "Geamana",
                                        "body": "idem", "category": "General"}))
    app.notes.append(NO.normalize_note({"id": 91, "title": "Geamana",
                                        "body": "idem", "category": "General"}))
    app._delete_note(app.notes[0], None)
    app.save_notes()
    app.update()

    app.show_settings_page()
    app.update()
    # Arriving rebuilds the section you LAND on; the others rebuild when
    # you go to them, which is the whole design. So walk there, the way
    # a person would, instead of reading a panel built on the last visit.
    app.toggle_settings_panel("categories")
    app.update()
    seen = texts(getattr(app, "settings_categories_panel", app))
    story.check("Categories, la a doua vizita, arata categoria noua",
                any("ProaspatAdaugata" in t for t in seen),
                "pe ecran: %s" % [t[:20] for t in seen if t][:6])
    story.check("...si nu mai arata categoria stearsa",
                not any("DeSters" in t for t in seen))
    app.toggle_settings_panel("trash")
    app.update()
    story.check("Recently deleted arata notita stearsa intre timp",
                any("Nota 1" in t for t in texts(app.settings_trash_panel)))
    app.toggle_settings_panel("duplicates")
    app.update()
    story.check("Duplicates arata perechea aparuta intre timp",
                any("Geamana" in t for t in texts(app.settings_duplicates_panel)))
    app.destroy()
    story.save()


# ---- 4: a bulk action, then ordinary typing --------------------------

def chapter_4():
    tk, NO, app = _app()
    story = Chapter()
    _seed(NO, app, 4)
    NO.CATEGORY_COLORS.setdefault("Munca", "#775599")

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
                    str(child.cget("text")).strip() == "Munca":
                row = child
                return
            find_row(child)

    popup = getattr(app, "_mini_popup", None)
    if popup is not None and popup.winfo_exists():
        find_row(popup)
    story.check("popup-ul ofera categoria pe nume", row is not None)
    if row is not None:
        row.event_generate("<Button-1>", x=3, y=3)
        app.update()
    story.check("actiunea in masa ajunge pe disc",
                all(n["category"] == "Munca" for n in app.notes[:3]),
                repr([n["category"] for n in app.notes[:3]]))

    # And then the user carries on typing in the note that was open.
    app.body_text.insert("end", " si scriu mai departe")
    app._flush_autosave()
    app.update()
    after = json.load(io.open("notes_data.json", encoding="utf-8"))
    first = next(n for n in after if n["id"] == app.notes[0]["id"])
    story.check("scrisul de dupa nu anuleaza schimbarea in masa",
                first["category"] == "Munca", repr(first["category"]))
    story.check("...si textul scris dupa chiar s-a salvat",
                "mai departe" in first["body"], repr(first["body"][:60]))
    app.destroy()
    story.save()


# ---- 5: one day edited, then the whole series ------------------------

def chapter_5():
    tk, NO, app = _app()
    story = Chapter()
    app.notes = [NO.normalize_note({
        "id": 1, "title": "Sedinta", "body": "text de serie",
        "category": "General", "date": "2026-09-07",
        "recurrence": {"freq": "weekly", "interval": 1, "weekdays": [0]}})]
    app.save_notes()
    app.update()

    note = app.notes[0]
    note.setdefault("overrides", {})["2026-09-14"] = {
        "title": "Sedinta", "body": "doar ziua asta e altfel",
        "comments": "", "category": "General", "color": ""}
    app.save_notes()
    app.update()

    app.open_note_in_tab(note)
    app.update()
    app.body_text.delete("1.0", "end")
    app.body_text.insert("1.0", "text de serie, schimbat")
    app.save_current_note(auto=False)
    app.update()
    app.destroy()

    tk2, NO2, again = _app()
    back = again.notes[0]
    story.check("seria a primit textul nou",
                "schimbat" in back["body"], repr(back["body"][:50]))
    story.check("ziua editata separat si-a pastrat textul ei",
                (back.get("overrides") or {}).get("2026-09-14", {}).get("body")
                == "doar ziua asta e altfel",
                repr(back.get("overrides")))
    story.check("si repetarea a ramas intreaga",
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
    story.check("stergerea scrie momentul in cos", bool(stamp), repr(entry))
    app.destroy()

    tk2, NO2, again = _app()
    back = again.trash[0] if again.trash else {}
    story.check("dupa repornire, momentul stergerii e acelasi",
                back.get("deleted_at") == stamp,
                "%r -> %r" % (stamp, back.get("deleted_at")))
    left = NO2.days_left_in_trash(back) if hasattr(NO2, "days_left_in_trash") else None
    if left is not None:
        story.check("...si zilele ramase se socotesc din el",
                    isinstance(left, int) and 0 < left <= NO2.trash_retention_days(),
                    repr(left))
    again.destroy()
    story.save()


CHAPTER_FNS = {1: chapter_1, 2: chapter_2, 3: chapter_3,
               4: chapter_4, 5: chapter_5, 6: chapter_6}


if __name__ == "__main__":
    if "--chapter" in sys.argv:
        number = int(sys.argv[sys.argv.index("--chapter") + 1])
        try:
            CHAPTER_FNS[number]()
        except Exception:
            import traceback
            traceback.print_exc()
            io.open(RESULTS, "w", encoding="utf-8").write(json.dumps(
                [["capitolul %d a mers pana la capat" % number, False,
                  traceback.format_exc().strip().splitlines()[-1]]],
                ensure_ascii=False))
        sys.exit(0)
    sys.exit(drive())
