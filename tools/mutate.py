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
tested: --self-test runs the two entries marked "self_test": true, one of
each kind. Marked, not told by their first letter: SP, the spelling's
mutants, start with S too.

"only_on": "win32" or "linux" marks a mutant only that system can kill: a
check that runs on one system alone (a file name holding a colon exists
only on Linux), or code the other never takes. Elsewhere it is ELSEWHERE,
named and not run: its verdict there would be wrong every time, and a wrong
verdict that is always excused hides the one that is not. Its note says why.

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
6. A run that passes its time (600 s a suite, and a margin) is HANG: the
   runner is ended with its suites, its scratch removed, and the
   catalogue goes on.

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

import guest  # tools/guest.py: the turn and the memory ceiling for a run

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CATALOGUE = os.path.join(HERE, "mutants.json")
ONLY_ON = ("win32", "linux")      # an entry's "only_on", as sys.platform starts
RUNNER_FOOTERS = (b"check(s) failed", b"check(s) passed")
# One mutant's suites may take this long each (run_tests' own limit for a
# script), plus a margin for the copy: a hang is a verdict, not the end.
TIMEOUT_PER_SUITE = 600
TIMEOUT_MARGIN = 300


def fresh_copy():
    # Marked as this run's (guest.scratch): if the run is killed, the next
    # run removes it.
    dest = guest.scratch("notesorg-mutant-")
    # The licenses are in run_tests.py's payload: qa6 opens them from About.
    for name in ("note_organizer.py", "THIRD_PARTY_NOTICES.txt"):
        shutil.copy2(os.path.join(ROOT, name), dest)
    shutil.copytree(os.path.join(ROOT, "noteorganizer"),
                    os.path.join(dest, "noteorganizer"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    for path in glob.glob(os.path.join(ROOT, "test_*.py")):
        shutil.copy2(path, dest)
    os.makedirs(os.path.join(dest, "qa"))
    for path in glob.glob(os.path.join(ROOT, "qa", "*.py")):
        shutil.copy2(path, os.path.join(dest, "qa"))
    os.makedirs(os.path.join(dest, "tools"))
    for name in ("run_tests.py", "guest.py"):
        shutil.copy2(os.path.join(ROOT, "tools", name), os.path.join(dest, "tools"))
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
    """Run the suites in the copy; return (output text, every suite
    completed, hung). A run past its time is a HANG: named, and the
    catalogue goes on."""
    # The runner writes each failed suite's whole output here, in this
    # mutant's own folder: under one fixed name in the shared temporary
    # folder, two runs at once read each other's.
    failures = os.path.join(copy_dir, "failures")
    os.makedirs(failures, exist_ok=True)
    limit = TIMEOUT_PER_SUITE * len(suites) + TIMEOUT_MARGIN
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(copy_dir, "tools", "run_tests.py")]
            + suites + ["--all-failures"],
            cwd=copy_dir, capture_output=True, timeout=limit,
            env=dict(os.environ, NOTEORG_FAILURE_DIR=failures))
    except subprocess.TimeoutExpired as hung:
        # The killed runner's job ends its suite with it; its scratch,
        # marked as a dead run's, goes in the sweep.
        guest.sweep()
        out = (hung.stdout or b"") + (hung.stderr or b"")
        return (out.decode("utf-8", "replace")
                + "\nHANG: the suites did not finish within %d s" % limit), False, True
    out = proc.stdout + proc.stderr
    completed = any(f in out for f in RUNNER_FOOTERS)
    # The runner prints its footer even when a suite died halfway; a suite's
    # own FAILURES footer is in the output the runner saves for each failure.
    for suite in suites:
        saved = os.path.join(failures, "notesorg-failure-%s.py.txt" % suite)
        if os.path.exists(saved):
            completed = completed and b"FAILURES" in io.open(saved, "rb").read()
    return out.decode("utf-8", "replace"), completed, False


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
        text, completed, hung = run_suites(copy_dir, entry["suites"])
    finally:
        guest.remove(copy_dir)
    if hung:
        return "HANG", [], text
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
    seen = set()
    for e in entries:
        # One id for two entries: a commit's "Mutant: <id>" named either, and
        # asking for one ran both (TP01 and RZ05, given twice on 2026-11-24).
        if e["id"] in seen:
            sys.exit("catalogue entry %s is in the catalogue twice" % e["id"])
        seen.add(e["id"])
        # A "killed" entry with nothing that must fail is killed by anything,
        # including a crash -- the vacuous verdict this runner exists to stop.
        if e["expect"] == "killed" and not e["must_fail"]:
            sys.exit("catalogue entry %s expects a kill but names no check" % e["id"])
        if e["expect"] == "survives" and e["must_fail"]:
            sys.exit("catalogue entry %s expects to survive but names checks" % e["id"])
        # Misspelt, it would be ELSEWHERE on every system, and never run.
        if e.get("only_on", "win32") not in ONLY_ON:
            sys.exit("catalogue entry %s is only_on %r, not one of %s"
                     % (e["id"], e["only_on"], ", ".join(ONLY_ON)))
    return entries


def runs_here(entry):
    """Whether this system can kill *entry* (its "only_on", if any)."""
    return sys.platform.startswith(entry.get("only_on", sys.platform))


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    # A flag it does not know is not an empty list of ids: "--help" ran the
    # whole catalogue, hours of it (2026-10-29).
    unknown = [a for a in argv[1:] if a.startswith("-") and a != "--self-test"]
    if unknown:
        print(__doc__)
        print("not a flag this runner knows: %s" % " ".join(unknown))
        return 2
    # This machine's turn and the memory ceiling, for every suite run below.
    for line in guest.settle(label="mutate " + " ".join(argv[1:])):
        print(line)
    if sys.platform != "win32":
        # Stopped from outside: each verdict's finally still removes its copy.
        import signal
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    entries = load_catalogue()
    if "--self-test" in argv:
        todo = [e for e in entries if e.get("self_test")]
        if len(todo) != 2:
            # None found would pass by running nothing.
            sys.exit("--self-test expects the catalogue's two self_test entries, "
                     "found %d" % len(todo))
    else:
        wanted = [a for a in argv[1:] if not a.startswith("--")]
        # A word that names no mutant ran nothing and passed: a typed "pn"
        # read "0 of 0 verdicts as the catalogue expects".
        unmatched = [w for w in wanted if not any(e["id"].startswith(w) for e in entries)]
        if unmatched:
            print("no mutant's id starts with: %s" % " ".join(unmatched))
            return 2
        todo = [e for e in entries
                if not wanted or any(e["id"].startswith(w) for w in wanted)]
    wrong, elsewhere = [], []
    for entry in todo:
        if not runs_here(entry):
            print("%-9s %s %s   (only %s can kill it)" % (
                "ELSEWHERE", entry["id"], entry["about"], entry["only_on"]))
            elsewhere.append(entry["id"])
            continue
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
    ran = len(todo) - len(elsewhere)
    print("%d of %d verdicts as the catalogue expects" % (ran - len(wrong), ran))
    if elsewhere:
        print("%d not run here, which only another system can kill: %s"
              % (len(elsewhere), " ".join(elsewhere)))
    if not ran:
        # Green for nothing run would read as the asked-for mutants proved.
        print("nothing here to run: every mutant asked for is another system's")
        return 2
    for mid in wrong:
        print("   wrong: %s" % mid)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
