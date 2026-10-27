"""The static gates CI runs, runnable locally in seconds.

WHY THIS EXISTS
---------------
Two pull requests in a row went red on the same avoidable round-trip: a
method was added to the app class after the API baseline had already been
re-recorded earlier on the branch, nobody re-ran the check locally, and
the first thing to notice was CI -- twenty minutes and one push later.

CI's first step runs cheap, purely-static gates. There was never a
reason to discover their verdict remotely; this script is those same
gates, in the same order, on the machine where the fix is one keystroke
away. It complements ``run_tests.py`` (the full suite in a safe scratch
folder, minutes) -- this is the two-second half you run before EVERY
push, that one is the real verdict you run before asking for one.

WHAT IT RUNS
------------
1. ``check_undefined_names`` over the entry point, the core and ui
   packages, the qa scripts, the unit suites and the tools -- names used
   but never defined or imported (the moved-code classic).
2. ``check_class_api`` -- the app class's method surface against its
   recorded baseline, so an added, lost or re-signatured method is a
   deliberate, recorded act rather than a surprise.
3. ``check_one_definition`` -- a question the app asks in several
   places, answered by a hand-rolled field list at each one. Every
   omission an adversarial review has caught in this project had that
   shape; this is the grep that catches it.
4. ``check_doc_links`` and ``check_english`` -- anchors that still go
   somewhere, and no Romanian in anything a reader of this repository
   sees. The app's interface is English; the qa stories had drifted.
5. ``check_agent_rules`` -- the agent's committed deny rules cover every
   script that wipes its working folder, in every spelling.
6. ``check_comments`` -- no release named in the app's comments, every
   pointer into the issues log leads somewhere, and the condensed modules
   keep their comments to a reason.
7. ``check_contrast`` -- every theme's text against WCAG AA; the pairs
   still below it are listed, and the list can only shrink.
8. ``check_shipped`` -- the Pillow CI tests is the one the .exe ships,
   and the licenses the build bundles name it.
9. ``compile()`` over every tracked ``.py`` in the repo -- tests and qa
   scripts included, because a syntax error in a TEST file is exactly
   what the remote runner would otherwise find first (a locally-valid
   PEP 701 f-string once died only on CI's older Python; the interpreter
   versions now match, this keeps even that class of gap local).

USAGE
-----
    py tools/pre_push_check.py

Exits non-zero on the first failing gate, so it can sit in front of any
push ritual. Read-only: nothing here writes, so there is nothing it can
break.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _run_gate(label, args):
    print("== %s" % label, flush=True)
    proc = subprocess.run([sys.executable] + args, cwd=ROOT)
    if proc.returncode != 0:
        print("\nPRE-PUSH: FAILED at '%s' -- fix it here, not on CI."
              % label)
        sys.exit(proc.returncode)


def main():
    scanned = []
    for layer in ("core", "ui"):
        scanned += [os.path.join("noteorganizer", layer, f)
                    for f in sorted(os.listdir(
                        os.path.join(ROOT, "noteorganizer", layer)))
                    if f.endswith(".py")]
    # The qa scripts, the unit suites and the tools as well: a qa check
    # once used two names from a block that had been replaced, and died
    # halfway through a full run with a NameError this finds at once.
    scanned += [os.path.join("qa", f)
                for f in sorted(os.listdir(os.path.join(ROOT, "qa")))
                if f.endswith(".py")]
    scanned += sorted(f for f in os.listdir(ROOT)
                      if f.startswith("test_") and f.endswith(".py"))
    scanned += [os.path.join("tools", f)
                for f in sorted(os.listdir(os.path.join(ROOT, "tools")))
                if f.endswith(".py")]
    _run_gate("names resolve",
              [os.path.join("tools", "check_undefined_names.py"),
               "note_organizer.py"] + scanned)
    _run_gate("class surface unchanged",
              [os.path.join("tools", "check_class_api.py")])
    _run_gate("one definition per judgement",
              [os.path.join("tools", "check_one_definition.py")])
    # The docs cross-reference each other by anchor, and reworded headings
    # break those links silently -- a dead anchor just scrolls nowhere.
    # Cheap enough to run on every push rather than once a release.
    _run_gate("documentation links resolve",
              [os.path.join("tools", "check_doc_links.py")])
    # The work is discussed in Romanian and written down in English. The
    # qa stories crossed that line without anybody noticing, and every CI
    # run then printed Romanian check names into a public log.
    _run_gate("English throughout",
              [os.path.join("tools", "check_english.py")])
    # The agent's deny rules, committed without this machine's paths: every
    # script that wipes its working folder, in every spelling that could
    # start it -- and the live lists here hold every committed rule.
    _run_gate("deny rules cover the wipers",
              [os.path.join("tools", "check_agent_rules.py")])
    # Comments say why in a few lines, and the story they point to exists.
    _run_gate("comments say why, briefly",
              [os.path.join("tools", "check_comments.py")])
    # Every theme's text measured against WCAG, and kept from getting worse.
    _run_gate("contrast measured",
              [os.path.join("tools", "check_contrast.py")])
    _run_gate("what ships is what is tested",
              [os.path.join("tools", "check_shipped.py")])

    print("== every tracked .py compiles", flush=True)
    listed = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT,
                            capture_output=True, text=True)
    bad = []
    for rel in listed.stdout.split():
        path = os.path.join(ROOT, rel)
        try:
            with open(path, encoding="utf-8") as f:
                compile(f.read(), rel, "exec")
        except SyntaxError as exc:
            bad.append("%s: %s" % (rel, exc))
    if bad:
        for line in bad:
            print("  " + line)
        print("\nPRE-PUSH: FAILED at 'every tracked .py compiles'.")
        sys.exit(1)

    print("\nPRE-PUSH: all static gates green. "
          "(The full suite is run_tests.py -- that verdict still counts.)")


if __name__ == "__main__":
    main()
