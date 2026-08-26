"""Run the whole test suite, safely, from anywhere.

WHY THIS EXISTS
---------------
The tests cannot be run where the code lives. Every ``qa*.py`` script starts
by deleting ``*.json`` and ``attachments/`` in its working directory, and
``test_data_safety.py`` calls ``initialise()`` in the current folder. Run
either from the project root and it wipes the real notebook -- which has
happened twice, and neither time showed up in ``git status`` because those
files are git-ignored.

CLAUDE.md's answer is "copy everything to a scratch folder outside the
project and run it there, every time". That works, but it relies on a person
remembering a multi-step ritual correctly on every single run. This does the
ritual instead:

* makes a fresh temporary folder, far away from the project
* copies in the entry point, the package, and the tests
* runs everything there, with that folder as the working directory
* deletes the folder afterwards

The project's own files are only ever read. Nothing here writes inside the
project, so a wrong turn cannot reach a notebook.

USAGE
-----
    py tools/run_tests.py            # everything
    py tools/run_tests.py qa6        # one script
    py tools/run_tests.py --keep     # leave the scratch folder for poking at

Exits non-zero if anything failed, so it works as a pre-commit check.
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Copied into the scratch folder. The package has to travel with the entry
# point: note_organizer.py imports from it, so a copy on its own fails with
# ModuleNotFoundError.
PAYLOAD = ["note_organizer.py", "noteorganizer"]

STANDALONE = ["test_recurrence.py", "test_calculator.py", "test_data_safety.py",
              "test_entry_module_identity.py", "test_richtext.py"]
QA = [f"qa{i}.py" for i in range(1, 10)]

# The two checks CI runs before any of the above. They were missing here, so a
# green run of this script did not mean a green run on GitHub -- a signature
# change once passed everything locally and failed CI on the next push.
#
# These read the project directly rather than the scratch copy, which is both
# safe and necessary: neither writes anything (check_class_api only records a
# new baseline when passed --update, which this never does), and the baseline
# it compares against lives in tools/ and is not part of the payload copied
# into scratch.
STATIC = [
    ("names resolve", [sys.executable, os.path.join("tools", "check_undefined_names.py"),
                       "note_organizer.py"] + sorted(
        glob.glob(os.path.join("noteorganizer", "core", "*.py")))),
    ("class surface unchanged", [sys.executable,
                                 os.path.join("tools", "check_class_api.py")]),
]


def _present(names, folder=ROOT):
    """Only what actually exists -- branches differ in which tests they have."""
    return [n for n in names if os.path.exists(os.path.join(folder, n))]


def build_scratch():
    scratch = tempfile.mkdtemp(prefix="notesorg-tests-")
    for item in PAYLOAD:
        src = os.path.join(ROOT, item)
        dst = os.path.join(scratch, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst,
                            ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, dst)
    for name in _present(STANDALONE):
        shutil.copy2(os.path.join(ROOT, name), scratch)
    qa_dir = os.path.join(ROOT, "qa")
    for name in _present(QA, qa_dir):
        shutil.copy2(os.path.join(qa_dir, name), scratch)
    return scratch


def wipe_data(scratch):
    """Between scripts, the way CI does it -- but only ever inside scratch."""
    assert scratch.startswith(tempfile.gettempdir()), "refusing to clean outside temp"
    for name in os.listdir(scratch):
        if name.endswith(".json"):
            os.remove(os.path.join(scratch, name))
    att = os.path.join(scratch, "attachments")
    if os.path.isdir(att):
        shutil.rmtree(att, ignore_errors=True)


def run_one(scratch, script):
    wipe_data(scratch)
    started = time.time()
    proc = subprocess.run([sys.executable, script], cwd=scratch,
                          capture_output=True, text=True, timeout=600)
    took = time.time() - started
    out = proc.stdout or ""
    # "FAIL " with the space, deliberately: a failing check prints
    # "FAIL <name>", but every suite also ends with a summary line reading
    # "FAILURES: none", and matching on "FAIL" alone reports a clean run as
    # three failures. (It did, the first time this was run.)
    failed = [l for l in out.splitlines() if l.startswith("FAIL ")]
    return proc.returncode, failed, took, out + (proc.stderr or "")


def run_static(name, cmd):
    """Run one static check against the project itself. Read-only."""
    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600)
    return proc.returncode, time.time() - started, (proc.stdout or "") + (proc.stderr or "")


def main(argv):
    keep = "--keep" in argv
    wanted = [a for a in argv[1:] if not a.startswith("--")]

    scripts = _present(STANDALONE) + [
        n for n in QA if os.path.exists(os.path.join(ROOT, "qa", n))]
    statics = STATIC
    if wanted:
        scripts = [s for s in scripts if any(w in s for w in wanted)]
        statics = [s for s in STATIC
                   if any(w == "static" or w in s[0] for w in wanted)]
        # Only give up once nothing at all matched: "static" selects no
        # script, which is not the same as a typo selecting nothing.
        if not scripts and not statics:
            print(f"nothing matches {wanted}")
            return 2

    print(f"project : {ROOT}")
    scratch = build_scratch()
    print(f"scratch : {scratch}")
    print(f"running : {len(statics) + len(scripts)} check(s)\n")

    broken = []
    # Static first: they take a moment and catch the kind of mistake that
    # would otherwise be reported only after a minute of GUI tests.
    for label, cmd in statics:
        code, took, output = run_static(label, cmd)
        print(f"  {'PASS' if code == 0 else 'FAIL'}  {label:<32} {took:5.1f}s")
        if code != 0:
            broken.append(label)
            for line in output.strip().splitlines()[-25:]:
                print(f"          {line}")
    try:
        for script in scripts:
            code, failed, took, output = run_one(scratch, script)
            ok = (code == 0 and not failed)
            print(f"  {'PASS' if ok else 'FAIL'}  {script:<32} {took:5.1f}s")
            if not ok:
                broken.append(script)
                for line in failed[:8]:
                    print(f"          {line}")
                if not failed:
                    # No "FAIL" line means the script died rather than
                    # reporting -- so this is a traceback, and the frames
                    # that name the app are at its top, not its end. Six
                    # lines showed only tkinter's own innards; a rare,
                    # hard-to-reproduce crash then left nothing to work
                    # from. Deep enough to reach the app's own frames.
                    for line in output.strip().splitlines()[-25:]:
                        print(f"          {line}")
    finally:
        if keep:
            print(f"\nscratch kept at {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)

    print()
    if broken:
        print(f"{len(broken)} check(s) failed: {', '.join(broken)}")
        return 1
    print(f"All {len(statics) + len(scripts)} check(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
