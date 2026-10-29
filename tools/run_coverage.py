"""Measure what the test suite actually executes.

Runs every unit suite and qa script under coverage.py, each in its own
scratch directory far outside the project tree (the same safety ritual as
run_tests.py — the scripts wipe their working directory's data files), then
combines the per-process data against the real source tree and prints:

* the total and per-file percentages, and
* the largest consecutive uncovered regions, each with the function it
  sits in — the actual worklist a coverage-lift cycle starts from.

Usage:
    py tools/run_coverage.py            # everything (a few minutes)
    py tools/run_coverage.py qa7 qa1    # just those scripts

Needs the `coverage` package (a dev tool, not an app dependency):
    py -m pip install coverage

The number this prints is a WINDOWS number: the Linux CI leg executes
different lines (Xvfb branches, POSIX paths). CI holds a floor under the
Linux number (--fail-under); the old per-layer targets are archived in
docs/archive/COVERAGE_LEDGER.md. A covered line is necessary, not
sufficient — whether the checks BITE is the mutation discipline's job
(qa/README, house rules).
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUITES = [
    "test_recurrence", "test_calculator", "test_data_safety",
    "test_entry_module_identity", "test_richtext", "test_tables",
    "test_note_identity",
    "qa1", "qa2", "qa3", "qa4", "qa5", "qa6", "qa7", "qa8", "qa9",
]


def _write_rc(cov_dir, run_dirs):
    lines = ["[run]", "parallel = True",
             "source = note_organizer, noteorganizer", "",
             "[paths]", "src =", "    " + ROOT]
    # coverage forbids a [paths] pattern ENDING in a wildcard, so each
    # scratch run-directory gets its own explicit entry.
    for d in run_dirs:
        lines.append("    " + d.replace("\\", "/"))
    lines += ["", "[report]", "precision = 1", ""]
    rc = os.path.join(cov_dir, ".coveragerc")
    io.open(rc, "w", encoding="utf-8").write("\n".join(lines))
    return rc


def _enclosing_defs(srcpath):
    defs = []
    for i, line in enumerate(io.open(srcpath, encoding="utf-8"), 1):
        m = re.match(r"(\s*)def\s+(\w+)", line)
        if m:
            defs.append((i, m.group(2)))
    return defs


def _owner(defs, ln):
    best = "(module level)"
    for start, name in defs:
        if start <= ln:
            best = name
        else:
            break
    return best


def main(argv):
    try:
        import coverage  # noqa: F401  (presence check only)
    except ImportError:
        print("The 'coverage' package is missing:  py -m pip install coverage")
        return 2
    import guest  # this machine's turn and the memory ceiling (tools/guest.py)
    for line in guest.settle(label="run_coverage " + " ".join(argv)):
        print(line)
    if sys.platform != "win32":
        # Stopped from outside: the finally below still removes the scratch.
        import signal
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    fail_under = None
    if "--fail-under" in argv:
        at = argv.index("--fail-under")
        fail_under = float(argv[at + 1])
        argv = argv[:at] + argv[at + 2:]
    wanted = [a for a in argv if not a.startswith("-")] or SUITES
    unknown = [w for w in wanted if w not in SUITES]
    if unknown:
        print("Unknown suite(s):", ", ".join(unknown))
        return 2

    # Marked as this run's (guest.scratch), and removed on every way out:
    # if the run is killed before its finally, the next run removes it.
    cov_dir = guest.scratch("noteorg-coverage-")
    try:
        return _measure(cov_dir, wanted, fail_under)
    finally:
        guest.remove(cov_dir)


# One suite under coverage may take this long (twice run_tests' limit: the
# tracer slows it). A hang is that suite's failure, named, and the run goes on.
SUITE_TIMEOUT = 1200


def _measure(cov_dir, wanted, fail_under):
    print("scratch  :", cov_dir)
    run_dirs = []
    # The suites' own temporary files (fixed-name zips, mkdtemp folders) go
    # in the scratch, so nothing outlives the run.
    child_tmp = os.path.join(cov_dir, "tmp")
    os.makedirs(child_tmp)
    # The scratch marker is what lets the qa scripts and test_data_safety
    # run at all: without it they refuse, before measuring anything. This
    # tool once ran without it for weeks and reported a number that was
    # mostly the scripts refusing.
    env_base = dict(os.environ,
                    PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                    NOTEORG_SCRATCH="1",
                    TEMP=child_tmp, TMP=child_tmp, TMPDIR=child_tmp,
                    COVERAGE_FILE=os.path.join(cov_dir, ".coverage"))
    for name in wanted:
        d = os.path.join(cov_dir, "run_" + name)
        os.makedirs(d)
        run_dirs.append(d)
        # The licenses with the app: qa6 opens them from About.
        for item in ("note_organizer.py", "THIRD_PARTY_NOTICES.txt"):
            shutil.copy2(os.path.join(ROOT, item), d)
        shutil.copytree(os.path.join(ROOT, "noteorganizer"),
                        os.path.join(d, "noteorganizer"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        src = os.path.join(ROOT, name + ".py")
        if not os.path.exists(src):
            src = os.path.join(ROOT, "qa", name + ".py")
        shutil.copy2(src, d)
        # Every qa script imports its seeding and its event helpers from
        # here, and so does a later block of test_data_safety; without it
        # the script dies at that import. run_tests.py copies it for all.
        shutil.copy2(os.path.join(ROOT, "qa", "_qa_support.py"), d)
    rc = _write_rc(cov_dir, run_dirs)

    unfinished = []
    for name, d in zip(wanted, run_dirs):
        print("running  :", name, flush=True)
        try:
            r = subprocess.run(
                [sys.executable, "-m", "coverage", "run", "--parallel-mode",
                 "--rcfile=" + rc, name + ".py"],
                cwd=d, env=env_base, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=SUITE_TIMEOUT)
        except subprocess.TimeoutExpired as hung:
            unfinished.append(name)
            print("  HANG: did not finish within %d s; its last lines:" % SUITE_TIMEOUT)
            tail = hung.stdout or ""
            if isinstance(tail, bytes):     # POSIX hands it over undecoded
                tail = tail.decode("utf-8", "replace")
            tail = tail.strip()
            for line in tail.splitlines()[-15:]:
                print("    " + line)
            continue
        # A suite that did not reach its own footer measured a fraction of
        # itself; a number built on it is not a measurement.
        if "FAILURES" not in r.stdout and "check(s)" not in r.stdout:
            unfinished.append(name)
            print("  DID NOT FINISH (exit %d):" % r.returncode)
            # The whole traceback: the frame that names who called is at
            # its top. Six lines showed only where it broke, never from
            # where -- run_tests.py learned this first, this tool did not.
            lines = (r.stdout + r.stderr).strip().splitlines()
            starts = [i for i, ln in enumerate(lines)
                      if ln.startswith("Traceback (most recent call last)")]
            shown = lines[starts[-1]:] if starts else lines[-25:]
            for line in shown[-80:]:
                print("    " + line)

    subprocess.run([sys.executable, "-m", "coverage", "combine",
                    "--rcfile=" + rc], cwd=cov_dir, env=env_base,
                   capture_output=True, text=True, timeout=600)
    rep = subprocess.run([sys.executable, "-m", "coverage", "report",
                          "--rcfile=" + rc, "--sort=-miss"],
                         cwd=cov_dir, env=env_base,
                         capture_output=True, text=True, timeout=600)
    print()
    print(rep.stdout)
    subprocess.run([sys.executable, "-m", "coverage", "json",
                    "--rcfile=" + rc, "-o", "cov.json", "-q"],
                   cwd=cov_dir, env=env_base, capture_output=True, text=True, timeout=600)

    data = json.load(io.open(os.path.join(cov_dir, "cov.json"),
                             encoding="utf-8"))
    regions = []
    for path, f in data["files"].items():
        miss = sorted(f["missing_lines"])
        if not miss:
            continue
        srcpath = path if ":" in path[:3] else os.path.join(ROOT, path)
        defs = _enclosing_defs(srcpath)
        start = prev = miss[0]
        runs = []
        for ln in miss[1:]:
            if ln <= prev + 2:
                prev = ln
            else:
                runs.append((start, prev))
                start = prev = ln
        runs.append((start, prev))
        rel = os.path.relpath(srcpath, ROOT).replace("\\", "/")
        for a, b in runs:
            regions.append((b - a + 1, rel, a, b, _owner(defs, a)))
    regions.sort(reverse=True)
    print("=== TOP UNCOVERED REGIONS ===")
    for size, path, a, b, fn in regions[:30]:
        print("%4d lines  %-34s %6d-%-6d in %s" % (size, path, a, b, fn))

    total = data["totals"]["percent_covered"]
    print("\nTOTAL: %.1f%% of the app's lines executed by the suite" % total)
    if unfinished:
        print("NOT A MEASUREMENT: %s did not finish." % ", ".join(unfinished))
        return 1
    if fail_under is not None and total < fail_under:
        print("BELOW THE FLOOR: %.1f%% < %.1f%%. A floor, not a target -- it "
              "exists to notice a suite that stopped running, not to be "
              "chased." % (total, fail_under))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
