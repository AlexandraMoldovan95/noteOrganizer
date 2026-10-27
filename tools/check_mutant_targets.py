"""Every mutant in the catalogue still finds the code it mutates.

tools/mutate.py reports a mutant whose text has gone as PATTERN -- but only
when someone runs that mutant, and a run names the mutants it is asked for.
A later fix split the two lines Q05 mutated, and for a day it guarded
nothing without anyone being told. This reads the catalogue on every run of
the gates: each "find" must occur exactly once in its file.

    py tools/check_mutant_targets.py
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    with io.open(os.path.join(ROOT, "tools", "mutants.json"), encoding="utf-8") as fh:
        entries = json.load(fh)
    sources, lost = {}, []
    # An id is how a mutant is asked for: two with one id, and mutate.py ran
    # both under it without a word (TB01 was given twice, 2026-10-27).
    seen = set()
    for entry in entries:
        if entry["id"] in seen:
            lost.append("%s: the id is used twice in the catalogue" % entry["id"])
        seen.add(entry["id"])
    for entry in entries:
        for edit in entry["edits"]:
            path = os.path.join(ROOT, edit["file"])
            if path not in sources:
                # Read as the runner matches: line endings as one.
                with io.open(path, encoding="utf-8", newline="") as fh:
                    sources[path] = fh.read().replace("\r\n", "\n")
            found = sources[path].count(edit["find"])
            if found != 1:
                lost.append("%s: its text is found %d times in %s"
                            % (entry["id"], found, edit["file"]))
    for line in lost:
        print("  " + line)
    if lost:
        print("%d mutant(s) no longer find what they mutate: aim each at the "
              "code as it is now, or drop it with the check it guarded."
              % len(lost))
        return 1
    print("Every one of the %d mutants has its own id and finds the code it mutates."
          % len(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
