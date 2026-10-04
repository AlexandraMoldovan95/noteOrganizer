"""Mutation testing: take a fix away, and watch the check that guards it fail.

A mutant is one small, deliberate change to the app -- usually a fix taken
back out -- together with the checks that must fail because of it. A check
that stays green while the thing it guards is gone protects nothing, and
this is how the project finds such checks before a user does.

The catalogue is tools/mutants.json (not under qa/, whose .json files are
the suite's own throwaway data and are wiped between runs). Each entry:

    {"id": "D01", "about": "a short year is read while typing",
     "edits": [{"file": "...", "find": "...", "replace": "..."}],
     "must_fail": ["the name of a check, as it prints"],
     "suites": ["test_recurrence"],
     "expect": "killed"}

"expect" is "killed" for a real mutant and "survives" for an equivalent
one -- a change that alters nothing, kept so the runner's own verdicts are
tested: --self-test runs the two S entries, one of each kind.

HOW A VERDICT IS REACHED
------------------------
1. A fresh copy of the code and the tests goes into a temp folder outside
   the project. The project is only ever READ, so no error here can leave
   a mutant in the real source, and there is nothing to restore.
2. Each edit is applied as bytes, matched against the file's own line
   endings. An edit that matches nowhere, or twice, is PATTERN: the
   catalogue has drifted from the code, and that is reported, not guessed.
3. Every edited .py file is compiled first. A mutant that does not compile
   is NO-COMPILE -- a broken import prints no FAIL lines and would
   otherwise read as a survivor.
4. The copy's own tools/run_tests.py runs the named suites.
5. KILLED only when every suite reached its own FAILURES footer AND every
   must_fail check printed a FAIL line. An expected survivor SURVIVES only
   when every suite ran to the end with no FAIL line at all.

    py tools/mutate.py               # the whole catalogue
    py tools/mutate.py D01 E03       # entries whose id starts so
    py tools/mutate.py --self-test   # the runner's own two checks

Exit code 0 when every verdict is the one the catalogue expects.
"""
import glob
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CATALOGUE = os.path.join(HERE, "mutants.json")
RUNNER_FOOTERS = (b"check(s) failed", b"check(s) passed")
TIMEOUT = 1500


def fresh_copy():
    dest = tempfile.mkdtemp(prefix="notesorg-mutant-")
    shutil.copy2(os.path.join(ROOT, "note_organizer.py"), dest)
    shutil.copytree(os.path.join(ROOT, "noteorganizer"),
                    os.path.join(dest, "noteorganizer"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    for path in glob.glob(os.path.join(ROOT, "test_*.py")):
        shutil.copy2(path, dest)
    os.makedirs(os.path.join(dest, "qa"))
    for path in glob.glob(os.path.join(ROOT, "qa", "*.py")):
        shutil.copy2(path, os.path.join(dest, "qa"))
    os.makedirs(os.path.join(dest, "tools"))
    shutil.copy2(os.path.join(ROOT, "tools", "run_tests.py"),
                 os.path.join(dest, "tools"))
    return dest


def apply(copy_dir, edit):
    """Apply one edit as bytes; return how many places it matched."""
    path = os.path.join(copy_dir, edit["file"])
    data = io.open(path, "rb").read()
    find = edit["find"].encode("utf-8")
    replace = edit["replace"].encode("utf-8")
    if b"\r\n" in data:
        find = find.replace(b"\n", b"\r\n")
        replace = replace.replace(b"\n", b"\r\n")
    hits = data.count(find)
    if hits == 1:
        io.open(path, "wb").write(data.replace(find, replace, 1))
    return hits


def does_not_compile(copy_dir, edits):
    broken = []
    for rel in sorted({e["file"] for e in edits if e["file"].endswith(".py")}):
        try:
            compile(io.open(os.path.join(copy_dir, rel), "rb").read(), rel, "exec")
        except SyntaxError as exc:
            broken.append("%s:%s %s" % (rel, exc.lineno, exc.msg))
    return broken


def run_suites(copy_dir, suites):
    """Run the suites in the copy; return (output text, every suite completed)."""
    started = time.time()
    proc = subprocess.run(
        [sys.executable, os.path.join(copy_dir, "tools", "run_tests.py")]
        + suites + ["--all-failures"],
        cwd=copy_dir, capture_output=True, timeout=TIMEOUT)
    out = proc.stdout + proc.stderr
    completed = any(f in out for f in RUNNER_FOOTERS)
    # The runner prints its footer even when a suite died halfway; a suite's
    # own FAILURES footer is in the output the runner saves for each failure.
    for suite in suites:
        saved = os.path.join(tempfile.gettempdir(),
                             "notesorg-failure-%s.py.txt" % suite)
        if os.path.exists(saved) and os.path.getmtime(saved) >= started:
            completed = completed and b"FAILURES" in io.open(saved, "rb").read()
    return out.decode("utf-8", "replace"), completed


def verdict(entry):
    """Run one mutant; return (status, the must_fail checks seen failing, output)."""
    copy_dir = fresh_copy()
    try:
        bad = [(e["file"], hits) for e in entry["edits"]
               for hits in [apply(copy_dir, e)] if hits != 1]
        if bad:
            return "PATTERN %s" % bad, [], ""
        broken = does_not_compile(copy_dir, entry["edits"])
        if broken:
            return "NO-COMPILE %s" % broken, [], ""
        text, completed = run_suites(copy_dir, entry["suites"])
    finally:
        shutil.rmtree(copy_dir, ignore_errors=True)
    if not completed:
        return "NO-RUN", [], text
    fail_lines = [l for l in text.splitlines() if "FAIL" in l
                  and "check(s)" not in l and "FAILURES" not in l]
    died = [c for c in entry["must_fail"] if any(c in l for l in fail_lines)]
    if entry["expect"] == "survives":
        return ("SURVIVED" if not fail_lines else "KILLED"), died, text
    return ("KILLED" if len(died) == len(entry["must_fail"]) else "SURVIVED"), died, text


def load_catalogue():
    with io.open(CATALOGUE, encoding="utf-8") as fh:
        entries = json.load(fh)
    for e in entries:
        # A "killed" entry with nothing that must fail is killed by anything,
        # including a crash -- the vacuous verdict this runner exists to stop.
        if e["expect"] == "killed" and not e["must_fail"]:
            sys.exit("catalogue entry %s expects a kill but names no check" % e["id"])
        if e["expect"] == "survives" and e["must_fail"]:
            sys.exit("catalogue entry %s expects to survive but names checks" % e["id"])
    return entries


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    entries = load_catalogue()
    if "--self-test" in argv:
        todo = [e for e in entries if e["id"].startswith("S")]
    else:
        wanted = [a for a in argv[1:] if not a.startswith("--")]
        todo = [e for e in entries
                if not wanted or any(e["id"].startswith(w) for w in wanted)]
    wrong = []
    for entry in todo:
        status, died, text = verdict(entry)
        expected = "KILLED" if entry["expect"] == "killed" else "SURVIVED"
        ok = status == expected
        print("%-9s %s %s%s" % (status.split()[0], entry["id"], entry["about"],
                               "" if ok else "   <-- expected " + expected))
        if not ok:
            wrong.append(entry["id"])
            for check in entry["must_fail"]:
                print("            %s %s" % ("x" if check in died else "!", check))
            if status.startswith(("PATTERN", "NO-COMPILE")):
                print("            " + status)
            elif text:
                print("            " + "\n            ".join(text.splitlines()[-12:]))
        sys.stdout.flush()
    print()
    print("%d of %d verdicts as the catalogue expects" % (len(todo) - len(wrong), len(todo)))
    for mid in wrong:
        print("   wrong: %s" % mid)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
