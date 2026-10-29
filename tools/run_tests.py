"""Run the whole test suite, safely, from anywhere.

WHY THIS EXISTS
---------------
The tests cannot be run where the code lives. Every ``qa*.py`` script starts
by deleting ``*.json`` and ``attachments/`` in its working directory, and
``test_data_safety.py`` calls ``initialise()`` in the current folder. Run
either from the project root and it wipes the real notebook -- which has
happened three times, and never showed up in ``git status`` because those
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
    py tools/run_tests.py --all-failures   # print every failing check, not
                                           # the first eight (for tools that
                                           # read this output)

Exits non-zero if anything failed, so it works as a pre-commit check.
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time

import guest  # tools/guest.py: the memory ceiling for a run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Copied into the scratch folder. The package has to travel with the entry
# point: note_organizer.py imports from it, so a copy on its own fails with
# ModuleNotFoundError. The licenses travel too: About opens them, and qa6
# presses that button.
PAYLOAD = ["note_organizer.py", "noteorganizer", "THIRD_PARTY_NOTICES.txt"]

STANDALONE = ["test_recurrence.py", "test_calculator.py", "test_data_safety.py",
              "test_entry_module_identity.py", "test_richtext.py",
              "test_tables.py", "test_note_identity.py", "test_spelling.py"]
QA = [f"qa{i}.py" for i in range(1, 10)]
# Every qa script imports this one; it must travel with them or the whole
# suite dies at import. Kept out of QA itself so it is never *run* as a test.
QA_SUPPORT = ["_qa_support.py"]

# The static checks CI runs before any of the above. They were missing here, so a
# green run of this script did not mean a green run on GitHub -- a signature
# change once passed everything locally and failed CI on the next push.
#
# These read the project directly rather than the scratch copy, which is both
# safe and necessary: neither writes anything (check_class_api only records a
# new baseline when passed --update, which this never does), and the baseline
# it compares against lives in tools/ and is not part of the payload copied
# into scratch.
STATIC = [
    # ROOT-anchored globs: the old relative pattern resolved against the
    # INVOKER's cwd, so run from anywhere but the repo root this gate
    # silently checked fewer files. And ui/*.py is scanned too — ~5200
    # lines of mixins used to be outside the gate in all three homes.
    # The qa scripts, the unit suites and the tools too: a qa check once
    # borrowed two names from the copied seed block, and when the block
    # became one call the script died halfway with a NameError -- found by
    # a full run minutes later, where this gate finds it in two seconds.
    ("names resolve", [sys.executable, os.path.join("tools", "check_undefined_names.py"),
                       "note_organizer.py"]
     + sorted(glob.glob(os.path.join(ROOT, "noteorganizer", "core", "*.py")))
     + sorted(glob.glob(os.path.join(ROOT, "noteorganizer", "ui", "*.py")))
     + sorted(glob.glob(os.path.join(ROOT, "qa", "*.py")))
     + sorted(glob.glob(os.path.join(ROOT, "test_*.py")))
     + sorted(glob.glob(os.path.join(ROOT, "tools", "*.py")))),
    ("class surface unchanged", [sys.executable,
                                 os.path.join("tools", "check_class_api.py")]),
    # The third gate, added 2026-09-11: a question the app asks in
    # several places, answered by a hand-rolled field list at each one,
    # is how every review-caught omission in this project happened. This
    # is the grep that would have caught them, run every time.
    ("one definition per judgement",
     [sys.executable, os.path.join("tools", "check_one_definition.py")]),
    # The fourth, added 2026-09-15. The work is discussed in Romanian and
    # written down in English, and the qa stories had drifted across that
    # line -- naming their checks in Romanian, which every CI run then
    # printed into a log anybody can open.
    ("English throughout",
     [sys.executable, os.path.join("tools", "check_english.py")]),
    # The fifth: every script that wipes its working folder has a deny rule
    # for the agent in every spelling that could start it from the project
    # root -- and, here on a machine with the live lists, they hold them all.
    ("deny rules cover the wipers",
     [sys.executable, os.path.join("tools", "check_agent_rules.py")]),
    # The sixth: no release named in the app's comments, every pointer into
    # the issues log leads somewhere, and condensed modules stay condensed.
    ("comments say why, briefly",
     [sys.executable, os.path.join("tools", "check_comments.py")]),
    # The seventh: every theme's text measured against WCAG AA, with the
    # pairs still below it listed and the list allowed only to shrink.
    ("contrast measured",
     [sys.executable, os.path.join("tools", "check_contrast.py")]),
    # The eighth: every mutant in the catalogue still finds the code it
    # mutates. One lost its lines to a later fix and guarded nothing for a day.
    ("mutants find their code",
     [sys.executable, os.path.join("tools", "check_mutant_targets.py")]),
    # The ninth: the Pillow CI tests is the one the .exe ships, and the
    # licenses the build bundles name it.
    ("what ships is what is tested",
     [sys.executable, os.path.join("tools", "check_shipped.py")]),
    # The tenth, added 2026-10-29: every runner sets guest.py's memory
    # ceiling, and the ceiling holds -- a test took 43 GB and the desktop
    # went down with it.
    ("a test run is a guest",
     [sys.executable, os.path.join("tools", "check_guest.py")]),
]


# Every child runs in UTF-8, whatever the console it was launched from.
#
# The qa scripts print check names containing emoji and box glyphs, and a
# default Windows console is cp1252: `print` then raises
# UnicodeEncodeError mid-run and takes the script down. Three suites died
# that way on a plain `py tools/run_tests.py`, which is the door CLAUDE.md
# tells everyone to use -- and it is why an entire review wave declared it
# had run no tests at all. The runner owns the child environment, so it
# sets this rather than asking each caller to remember two env vars.
CHILD_ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                 # Unbuffered, so a script that HANGS still hands over every
                 # line it printed. Piped stdout is block-buffered, and a
                 # killed process takes its last few kilobytes with it --
                 # exactly the lines that say where it stopped.
                 PYTHONUNBUFFERED="1")

# How long one script may run before it is called hung. A hang is a real
# finding -- usually a dialog nobody answers -- so it is reported as a
# failure of THAT script, with everything it printed, and the run goes on.
SCRIPT_TIMEOUT = 600


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
    for name in _present(QA + QA_SUPPORT, qa_dir):
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


def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def run_one(scratch, script):
    wipe_data(scratch)
    started = time.time()
    try:
        # The scratch marker: the scripts that wipe their working folder
        # refuse to run without it (qa/_qa_support.hermetic_seed,
        # test_data_safety.py), and only a run in a throwaway folder --
        # this one, or CI's fresh checkout -- sets it.
        proc = subprocess.run([sys.executable, script], cwd=scratch,
                              capture_output=True, text=True,
                              timeout=SCRIPT_TIMEOUT,
                              env=dict(CHILD_ENV, NOTEORG_SCRATCH="1"),
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as hung:
        # This used to escape and end the whole run: one hung script,
        # and every suite after it was never run at all -- the report
        # said nothing about them, which reads like nothing to report.
        # A hang is this script's failure, named, with the output it
        # had printed up to the moment it stopped.
        took = time.time() - started
        out = _as_text(hung.stdout)
        failed = [l for l in out.splitlines() if l.startswith("FAIL ")]
        failed.append("FAIL %s did not finish within %d seconds (last lines "
                      "below)" % (script, SCRIPT_TIMEOUT))
        return 1, failed, took, out + _as_text(hung.stderr)
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
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          timeout=600, env=CHILD_ENV, encoding="utf-8",
                          errors="replace")
    return proc.returncode, time.time() - started, (proc.stdout or "") + (proc.stderr or "")


def _save_failure_output(label, output):
    """Write a failed run's WHOLE output where it will still be there later.

    The terminal shows a summary, and a summary is what a piped `tail`
    throws away. A red that loses its name costs a day: COVERAGE_LEDGER's
    C11b was a flake whose name was lost for exactly this reason, and the
    rule that recovered it was writing the output down. A second flake,
    in qa3, went undiagnosed the same way before this covered the qa half
    as well as the static one.

    Deliberately outside the repository and outside the scratch folder the
    run deletes, so it survives both.
    """
    try:
        path = os.path.join(tempfile.gettempdir(),
                            f"notesorg-failure-{label}.txt")
        with open(path, "w", encoding="utf-8", errors="replace") as fh:
            fh.write(output)
        print(f"          [full output: {path}]")
    except OSError:
        pass


def main(argv):
    # Same reason as CHILD_ENV, for THIS process: it echoes the children's
    # failing check names, glyphs and all, and a cp1252 console would
    # raise on the first one -- turning a readable report into a
    # traceback.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    keep = "--keep" in argv
    # For anything reading this output rather than looking at it: print
    # every failing check instead of the first eight. A mutation runner
    # that judges a mutant by which check names appear needs the whole
    # list, or a mutant that breaks nine checks reads as one that broke
    # none of the ones being watched for.
    all_failures = "--all-failures" in argv
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
    # Before anything is started: every script below inherits the ceiling.
    for line in guest.settle():
        print(line)
    scratch = build_scratch()
    print(f"scratch : {scratch}")
    print(f"running : {len(statics) + len(scripts)} check(s)\n")

    broken = []
    # Every check a suite runs prints one PASS or FAIL line: counted here, so
    # the docs' "how many checks" is a measurement, not a recollection.
    counted = {"unit": 0, "qa": 0}
    # Static first: they take a moment and catch the kind of mistake that
    # would otherwise be reported only after a minute of GUI tests.
    for label, cmd in statics:
        code, took, output = run_static(label, cmd)
        print(f"  {'PASS' if code == 0 else 'FAIL'}  {label:<32} {took:5.1f}s")
        if code != 0:
            broken.append(label)
            for line in output.strip().splitlines()[-25:]:
                print(f"          {line}")
            # ...and the WHOLE thing to a file, because the twenty-five
            # lines above are the ones a piped `tail` throws away.
            _save_failure_output(label, output)
    try:
        for script in scripts:
            code, failed, took, output = run_one(scratch, script)
            ok = (code == 0 and not failed)
            ran = sum(1 for l in output.splitlines() if l.startswith(("PASS ", "FAIL ")))
            counted["qa" if script.startswith("qa") else "unit"] += ran
            print(f"  {'PASS' if ok else 'FAIL'}  {script:<32} {took:5.1f}s {ran:6,} checks")
            if not ok:
                broken.append(script)
                for line in (failed if all_failures else failed[:8]):
                    print(f"          {line}")
                # Say when the list was cut. Eight lines is the right
                # amount for a person reading a terminal, and a silent
                # truncation is a trap for anything reading this output:
                # a mutation runner judged two mutants "survived" because
                # the checks they broke were the ninth and later, so the
                # names it was looking for were simply not printed. A
                # verdict a tool can get wrong quietly is worse than no
                # tool.
                if not all_failures and len(failed) > 8:
                    print(f"          ... and {len(failed) - 8} more "
                          f"({len(failed)} checks failed in total)")
                if any("did not finish within" in l for l in failed):
                    # A hang: the last lines it printed are where it
                    # stopped, which is the whole diagnosis.
                    for line in output.strip().splitlines()[-15:]:
                        print(f"          | {line}")
                if not failed:
                    # No "FAIL" line means the script died rather than
                    # reporting -- so this is a traceback, and the frames
                    # that name the app are at its top, not its end. Six
                    # lines showed only tkinter's own innards; a rare,
                    # hard-to-reproduce crash then left nothing to work
                    # from. Deep enough to reach the app's own frames.
                    for line in output.strip().splitlines()[-25:]:
                        print(f"          {line}")
                # ...and the WHOLE thing to a file, exactly as the static
                # gates above already do. They learned this and the qa
                # half never did: a rare red in qa3 during a full run was
                # reported with a piped `tail`, the names scrolled away,
                # and the run after it was green -- so a real flake went
                # undiagnosed for want of the output it had already
                # produced. The file lives outside the repo and outside
                # the scratch folder deleted below, so it survives both.
                _save_failure_output(script, output)
    finally:
        if keep:
            print(f"\nscratch kept at {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)

    print()
    peak = guest.memory_peak()
    if peak:
        print(peak)
    if scripts:
        print(f"Individual checks run: {sum(counted.values()):,} (unit suites "
              f"{counted['unit']:,}, qa suite {counted['qa']:,}).")
    if broken:
        print(f"{len(broken)} check(s) failed: {', '.join(broken)}")
        return 1
    print(f"All {len(statics) + len(scripts)} check(s) passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
