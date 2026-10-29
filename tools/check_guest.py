"""Fail when a test run could take more of this computer than a test should.

WHY THIS GATE EXISTS
--------------------
On 2026-10-29 a mutant made one test process take 43 GB: Windows ran out of
memory, its desktop window manager crashed, and the shadow copies of C: were
deleted under the load (ISSUES_LOG: "The test that took the computer down").
tools/guest.py now sets a memory ceiling for a run and everything it starts.
This gate holds it:

1. Every runner calls guest.settle() -- found, not listed: each script in
   tools/ and qa/ that starts a Python process, except the suites a runner
   starts (qa1-qa9, test_*.py), which inherit the ceiling.
2. The ceiling holds here: a process capped at 256 MB starts one that asks
   for 64 MB, which runs, and one that asks for 1 GB, which fails alone.

    py tools/check_guest.py
"""

import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SUITE = re.compile(r"^(qa\d+|test_.*)\.py$")


def runners_without_settle():
    missing = []
    for path in sorted(glob.glob(os.path.join(HERE, "*.py"))
                       + glob.glob(os.path.join(ROOT, "qa", "*.py"))):
        name = os.path.basename(path)
        if SUITE.match(name) or name in ("guest.py", "check_guest.py"):
            continue
        text = open(path, encoding="utf-8").read()
        if "sys.executable" in text and "guest.settle()" not in text:
            missing.append(os.path.relpath(path, ROOT))
    return missing


CHILD = r"""
import subprocess, sys
sys.path.insert(0, sys.argv[1])
import guest
print(guest.cap_memory(256, 512))
for mb in (64, 1024):
    r = subprocess.run([sys.executable, "-c", "b = bytearray(%d * 1048576)" % mb],
                       capture_output=True, text=True)
    print(mb, r.returncode, "MemoryError" in r.stderr)
"""


def ceiling_holds():
    out = subprocess.run([sys.executable, "-c", CHILD, HERE], capture_output=True,
                         text=True, timeout=120).stdout.splitlines()
    ok = (len(out) == 3 and "NO ceiling" not in out[0]
          and out[1] == "64 0 False" and out[2].startswith("1024 1") and out[2].endswith("True"))
    return ok, out


def main():
    missing = runners_without_settle()
    print("%s every runner sets the ceiling%s" % ("PASS" if not missing else "FAIL",
                                                 "" if not missing else ": " + ", ".join(missing)))
    ok, out = ceiling_holds()
    print("%s a process past the ceiling fails alone (%s)" % ("PASS" if ok else "FAIL", out))
    return 1 if missing or not ok else 0


if __name__ == "__main__":
    sys.exit(main())
