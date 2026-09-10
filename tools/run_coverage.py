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
different lines (Xvfb branches, POSIX paths). Where the current baseline
and targets live: qa/COVERAGE_LEDGER.md. A covered line is necessary, not
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
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUITES = [
    "test_recurrence", "test_calculator", "test_data_safety",
    "test_entry_module_identity", "test_richtext", "test_tables",
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

    wanted = [a for a in argv if not a.startswith("-")] or SUITES
    unknown = [w for w in wanted if w not in SUITES]
    if unknown:
        print("Unknown suite(s):", ", ".join(unknown))
        return 2

    cov_dir = tempfile.mkdtemp(prefix="noteorg-coverage-")
    print("scratch  :", cov_dir)
    run_dirs = []
    env_base = dict(os.environ,
                    PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                    COVERAGE_FILE=os.path.join(cov_dir, ".coverage"))
    for name in wanted:
        d = os.path.join(cov_dir, "run_" + name)
        os.makedirs(d)
        run_dirs.append(d)
        shutil.copy2(os.path.join(ROOT, "note_organizer.py"), d)
        shutil.copytree(os.path.join(ROOT, "noteorganizer"),
                        os.path.join(d, "noteorganizer"))
        src = os.path.join(ROOT, name + ".py")
        if not os.path.exists(src):
            src = os.path.join(ROOT, "qa", name + ".py")
        shutil.copy2(src, d)
    rc = _write_rc(cov_dir, run_dirs)

    for name, d in zip(wanted, run_dirs):
        print("running  :", name, flush=True)
        r = subprocess.run(
            [sys.executable, "-m", "coverage", "run", "--parallel-mode",
             "--rcfile=" + rc, name + ".py"],
            cwd=d, env=env_base, capture_output=True, text=True)
        if r.returncode != 0:
            print("  NOTE: nonzero exit (%d) — coverage still recorded"
                  % r.returncode)

    subprocess.run([sys.executable, "-m", "coverage", "combine",
                    "--rcfile=" + rc], cwd=cov_dir, env=env_base,
                   capture_output=True, text=True)
    rep = subprocess.run([sys.executable, "-m", "coverage", "report",
                          "--rcfile=" + rc, "--sort=-miss"],
                         cwd=cov_dir, env=env_base,
                         capture_output=True, text=True)
    print()
    print(rep.stdout)
    subprocess.run([sys.executable, "-m", "coverage", "json",
                    "--rcfile=" + rc, "-o", "cov.json", "-q"],
                   cwd=cov_dir, env=env_base, capture_output=True, text=True)

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

    shutil.rmtree(cov_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
