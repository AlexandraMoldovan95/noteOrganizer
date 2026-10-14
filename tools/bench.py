"""Measure the app at the sizes that hurt: start-up, the note list, a save.

    py tools/bench.py                       # this tree, 1,000 and 5,000 notes
    py tools/bench.py --notes 1000 --runs 5
    py tools/bench.py --against D:/old/copy # A/B: another copy, interleaved
    py tools/bench.py --rich --deep         # styled notes; the list scrolled to its end

Every number comes from a fresh process in a throwaway folder outside the
project: a copy of the app, a notebook generated from a fixed seed (so A
and B open the same notes), and an empty APPDATA, so the app has nothing
real to adopt. The project is only read. In an A/B run the processes
alternate A, B, A, B, so a machine that slows down halfway slows both
sides; the report gives medians.

What it measures, in milliseconds unless it says MB:

    start-up   process start to the first drawn list: import, load,
               build the window, draw what fits on screen
    rebuild    refresh_note_list() over the whole notebook, drawn
    save       one note's automatic save, the one a pause in typing makes
    memory     the process's memory once the window is up (MB)
    match      an import's matching of a backup that holds every note again
    deep       with --deep: refresh_note_list() with the list scrolled to its
               end, where a rebuild draws every row above the view
    pin        with --deep: pinning the note at the end of the list

--rich gives every note styled words (bold, colours, highlights), which is
what makes a real notebook's file, and so its save, heavier than plain text.
--deep scrolls the list to its end a screen at a time, as a wheel does: at
10,000 notes that alone takes most of a minute.

These are wall-clock numbers from one machine and say nothing about
another; the guards in CI are structural instead (qa4: a rebuild draws one
screenful and holds the rest), because a timing check that fires on a 20%
drift fires on a busy CI runner. Use this for before-and-after.
"""
import argparse
import io
import json
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PROBE = r'''
import json, os, sys, time
t_start = time.perf_counter()
import note_organizer as NO
app = NO.NoteOrganizer()
app._poll_active_dirty = lambda: None
app.update()
startup = (time.perf_counter() - t_start) * 1000

def ms(fn, times=3):
    out = []
    for _ in range(times):
        t = time.perf_counter(); fn(); app.update()
        out.append((time.perf_counter() - t) * 1000)
    return sorted(out)[len(out) // 2]

rebuild = ms(app.refresh_note_list)
app.open_note_in_tab(app.notes[0]); app.update()
def save():
    app.body_text.insert("end", " more")
    app.save_current_note(auto=True)
save_ms = ms(save)

memory = None
try:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
        psapi = ctypes.WinDLL("psapi")
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        # Without argtypes the 64-bit handle is passed as a C int and the
        # call fails without a word.
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC),
                                               wintypes.DWORD]
        psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        memory = pmc.WorkingSetSize / 1048576
    else:
        import resource
        memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
except Exception:
    pass
import copy
from noteorganizer.core import model
twins = [copy.deepcopy(n) for n in app.notes]
t = time.perf_counter()
model.split_by_identity(app.notes, twins)
match = (time.perf_counter() - t) * 1000

deep = pin = None
if os.environ.get("BENCH_DEEP"):
    cv = app.canvas
    while cv.yview()[1] < 0.999 or getattr(app, "_list_pending", None):
        cv.yview_scroll(1, "pages"); app.update()
    deep = ms(app.refresh_note_list)
    last = app._list_drawn[-1]["note"]["id"]
    pin = ms(lambda: app.toggle_pin(app.find_note(last)))
print("BENCH " + json.dumps({"startup": startup, "rebuild": rebuild,
                             "save": save_ms, "memory": memory, "match": match,
                             "deep": deep, "pin": pin}))
app.destroy()
'''

WORDS = ("meeting notes budget review plan draft travel recipe shopping list "
         "ideas project deadline call email report summary agenda follow up "
         "weekly monthly reading book garden repair invoice ticket").split()


STYLES = [{"style": "bold"}, {"style": "italic"}, {"style": "underline"},
          {"style": "text_color", "value": "#d32f2f"}, {"style": "highlight", "value": "#fff59d"}]


def notebook(n, seed=7, rich=False):
    """n notes, the same every time for the same n and seed. *rich*: each
    also wears a dozen styled runs of words."""
    rnd = random.Random(seed)
    notes = []
    for i in range(n):
        words = [rnd.choice(WORDS) for _ in range(rnd.randint(20, 160))]
        body = " ".join(words)
        spans = []
        if rich:
            for _ in range(12):
                start = rnd.randint(0, max(0, len(body) - 30))
                spans.append(dict(rnd.choice(STYLES), start=start,
                                  end=start + rnd.randint(4, 30)))
        if i % 20 == 0:
            body += "\n| Item | Qty |\n| --- | --- |\n| tea | 2 |\n| milk | 1 |"
        note = {"id": i + 1, "title": "Note %d %s" % (i + 1, rnd.choice(WORDS)),
                "body": body, "category": rnd.choice(["General", "Work", "Personal", "Ideas"]),
                "created": "2026-01-01 09:00:00",
                "updated": "2026-%02d-%02d 10:00:00" % (rnd.randint(1, 9), rnd.randint(1, 28)),
                "checklist": ([{"text": "step %d" % k, "done": k % 2 == 0} for k in range(5)]
                              if i % 10 == 0 else []),
                "attachments": []}
        if spans:
            note["formatting"] = spans
        if i % 7 == 0:
            note["date"] = "2026-%02d-%02d" % (rnd.randint(1, 12), rnd.randint(1, 28))
        if i % 50 == 0:
            note["date"] = "2026-01-05"
            note["recurrence"] = {"freq": "weekly"}
        notes.append(note)
    return notes


def make_run(tree, n, rich=False):
    run = tempfile.mkdtemp(prefix="notesorg-bench-")
    shutil.copy2(os.path.join(tree, "note_organizer.py"), run)
    shutil.copytree(os.path.join(tree, "noteorganizer"), os.path.join(run, "noteorganizer"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    with io.open(os.path.join(run, "notes_data.json"), "w", encoding="utf-8") as fh:
        json.dump(notebook(n, rich=rich), fh)
    with io.open(os.path.join(run, "settings.json"), "w", encoding="utf-8") as fh:
        json.dump({"reclaimed_from_appdata": True}, fh)
    os.makedirs(os.path.join(run, "appdata_empty"))
    with io.open(os.path.join(run, "bench_probe.py"), "w", encoding="utf-8") as fh:
        fh.write(PROBE)
    return run


def measure(tree, n, rich=False, deep=False):
    run = make_run(tree, n, rich)
    try:
        env = dict(os.environ, PYTHONIOENCODING="utf-8",
                   APPDATA=os.path.join(run, "appdata_empty"),
                   LOCALAPPDATA=os.path.join(run, "appdata_empty"),
                   XDG_DATA_HOME=os.path.join(run, "appdata_empty"))
        env.pop("BENCH_DEEP", None)
        if deep:
            env["BENCH_DEEP"] = "1"
        proc = subprocess.run([sys.executable, "bench_probe.py"], cwd=run, env=env,
                              capture_output=True, text=True, timeout=900,
                              encoding="utf-8", errors="replace")
        for line in proc.stdout.splitlines():
            if line.startswith("BENCH "):
                return json.loads(line[6:])
        raise RuntimeError("the probe printed no result:\n" + (proc.stdout + proc.stderr)[-1500:])
    finally:
        shutil.rmtree(run, ignore_errors=True)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--notes", type=int, nargs="*", default=[1000, 5000])
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--against", help="another copy of the app, for an A/B run")
    p.add_argument("--rich", action="store_true", help="every note wears styled words")
    p.add_argument("--deep", action="store_true", help="also measure at the list's end")
    args = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sides = [("this tree", ROOT)] + ([("against", args.against)] if args.against else [])
    keys = ["startup", "rebuild", "save", "memory", "match"] + (["deep", "pin"] if args.deep else [])
    rows = []
    for n in args.notes:
        results = {label: [] for label, _ in sides}
        for _ in range(args.runs):
            for label, tree in sides:      # interleaved: A, B, A, B ...
                results[label].append(measure(tree, n, args.rich, args.deep))
        for label, _ in sides:
            got = results[label]
            med = {}
            for k in keys:
                values = [r.get(k) for r in got if r.get(k) is not None]
                med[k] = statistics.median(values) if values else None
            rows.append((n, label, med))
    print("%-7s %-10s" % ("notes", "") + "".join("%10s" % k for k in keys))
    for n, label, m in rows:
        cells = ["%10s" % "n/a" if m[k] is None
                 else "%8.0fMB" % m[k] if k == "memory" else "%8.0fms" % m[k] for k in keys]
        print("%-7d %-10s" % (n, label) + "".join(cells))
    print("(medians of %d runs each%s%s)" % (args.runs, ", interleaved" if args.against else "",
                                             ", styled notes" if args.rich else ""))


if __name__ == "__main__":
    main()
