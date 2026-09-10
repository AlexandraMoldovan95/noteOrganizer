"""Pin down the app class's shape, so a refactor can't quietly change it.

WHY THIS EXISTS
---------------
The UI is being split from one ~9,700-line class into several files using
mixins: each group of methods moves to its own class, and `NoteOrganizer`
inherits from all of them. Done correctly this changes nothing at all — the
same methods, with the same names and arguments, end up on the same class.

The failure modes are all quiet ones:

* a method gets lost in a move and nothing notices until a button is clicked
* a method is accidentally left in two mixins, and which one wins depends on
  the order the classes are listed in
* an argument is dropped or renamed while shuffling code around

None of those stop the app importing, and the GUI tests only cover the paths
they happen to exercise. This locks the whole surface instead: it records
every method on the class and its exact signature, and compares that against
a committed baseline.

If the split is a true move, the comparison is empty. Any difference is
either a real mistake or something deliberate — in which case update the
baseline in the same commit, so the change is visible in review rather than
discovered later.

USAGE
-----
    py tools/check_class_api.py            # compare against the baseline
    py tools/check_class_api.py --update   # re-record it (do this on purpose)

Importing the app is safe: `note_organizer` no longer does anything on
import, and this only inspects the class, never builds a window — so it runs
headlessly with no display.
"""

import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).resolve().parent / "class_api_baseline.json"


def current_api():
    """Every method on NoteOrganizer that the app itself defines.

    Inherited tkinter machinery is skipped — this is about the app's own
    surface, not Tk's.
    """
    sys.path.insert(0, str(ROOT))
    import note_organizer

    cls = note_organizer.NoteOrganizer
    # Walk the class's own MRO entries but stop before tkinter's, so mixins
    # added by the split are included while Tk internals are not.
    own = {}
    owners = {}
    duplicates = []
    for klass in cls.__mro__:
        if klass.__module__.startswith("tkinter") or klass is object:
            continue
        for name, value in vars(klass).items():
            # classmethods, staticmethods and properties are descriptor
            # objects, not callables — the plain callable() test made
            # them invisible to both the baseline and the duplicate
            # detector (a mixin shadowing a classmethod went uncaught).
            if isinstance(value, (staticmethod, classmethod)):
                value = value.__func__
            elif isinstance(value, property):
                value = value.fget
            if not callable(value):
                continue
            if name in own:
                # The exact failure this tool exists to catch, which the
                # old skip made invisible: the same method defined in
                # two of OUR classes. Only the MRO winner ever runs; the
                # loser is silent dead code or a silent behaviour swap.
                duplicates.append((name, owners[name], klass.__name__))
                continue
            owners[name] = klass.__name__
            try:
                own[name] = str(inspect.signature(value))
            except (TypeError, ValueError):
                own[name] = "(<unavailable>)"
    return dict(sorted(own.items())), sorted(duplicates)


def load_baseline():
    if not BASELINE.exists():
        return None
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def main(argv):
    api, duplicates = current_api()

    if duplicates:
        print(f"DUPLICATE METHODS ({len(duplicates)}) — defined in two "
              f"classes; only the MRO winner runs:")
        for name, winner, loser in duplicates:
            print(f"    {name}: {winner} shadows {loser}")
        return 1

    if "--update" in argv:
        BASELINE.write_text(json.dumps(api, indent=2) + "\n", encoding="utf-8")
        print(f"Recorded {len(api)} methods to {BASELINE.name}")
        return 0

    baseline = load_baseline()
    if baseline is None:
        print(f"No baseline yet. Create one with:\n"
              f"    py tools/check_class_api.py --update")
        return 2

    removed = sorted(set(baseline) - set(api))
    added = sorted(set(api) - set(baseline))
    changed = sorted(n for n in set(api) & set(baseline)
                     if api[n] != baseline[n])

    print(f"baseline: {len(baseline)} methods | current: {len(api)} methods")

    if not (removed or added or changed):
        print("\nThe class exposes exactly the same methods as the baseline.")
        return 0

    if removed:
        print(f"\nMISSING ({len(removed)}) — on the class before, gone now:")
        for n in removed:
            print(f"    {n}{baseline[n]}")
    if added:
        print(f"\nNEW ({len(added)}) — not in the baseline:")
        for n in added:
            print(f"    {n}{api[n]}")
    if changed:
        print(f"\nSIGNATURE CHANGED ({len(changed)}):")
        for n in changed:
            print(f"    {n}\n        was: {baseline[n]}\n        now: {api[n]}")

    print("\nIf every difference above is intended, re-record the baseline:")
    print("    py tools/check_class_api.py --update")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
