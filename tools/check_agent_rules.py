"""Fail when a script that wipes data could be started without a deny rule.

WHY THIS GATE EXISTS
--------------------
The qa scripts, the unit suites and the entry file all wipe or rewrite the
data files in their working folder. Run from the project root, that is the
real notebook -- it has happened three times (CLAUDE.md, "QA testing
safety"). Each of them now refuses to run outside a declared throwaway
folder, and the AI agent that works on this project is also denied
starting them from the project root at all.

Those deny rules live in .claude/settings.json and settings.local.json,
which are git-ignored because they hold one machine's paths -- so nobody
could review them, and they did not reach a new machine. Their committed,
machine-free copy is tools/agent_deny_rules.json, and this gate holds it
to the scripts it guards:

1. The scripts are FOUND, not listed: the entry file, every test_*.py at
   the root, every qa script that seeds its own data (hermetic_seed), and
   qa/probe_bar_width.py. A new one is covered the day it is written, or
   this gate goes red.
2. Each needs a rule for every way it can be started from the project
   root: py, python and python3; as name, ./name, and for qa scripts
   qa/name and qa\\name; bare and with arguments. A rule ending in ":*"
   needs something after the name, so the bare form is its own rule --
   141 of the 336 were missing when this gate was written.
3. The committed file names no machine: no drive-letter paths but the
   two "rm -rf" rules, no user folder.
4. On a machine that has the live lists, every committed rule is in them.
   A written policy and its configuration once disagreed for three weeks.

    py tools/check_agent_rules.py

Exit code 0 when clean, 1 when a rule is missing.
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMMITTED = os.path.join(HERE, "agent_deny_rules.json")
LIVE = (os.path.join(ROOT, ".claude", "settings.json"),
        os.path.join(ROOT, ".claude", "settings.local.json"))
INTERPRETERS = ("py", "python", "python3")
# The only drive letters a committed rule may carry: these two deny a
# command, they do not describe a machine.
MACHINE_FREE_EXCEPTIONS = {"Bash(rm -rf C:/:*)", "Bash(rm -rf D:/:*)"}


def tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    names = [n.strip() for n in out.stdout.splitlines() if n.strip()]
    if out.returncode != 0 or not names:
        print("Cannot list the tracked files (is %s a git checkout?)." % ROOT)
        sys.exit(2)
    return names


def destructive_scripts(names):
    """Every tracked script that rewrites the data files where it runs."""
    found = []
    for name in names:
        if not name.endswith(".py"):
            continue
        base = os.path.basename(name)
        if name == "note_organizer.py" or (base.startswith("test_") and "/" not in name):
            found.append(name)
        elif name.startswith("qa/") and base != "_qa_support.py":
            text = io.open(os.path.join(ROOT, name), encoding="utf-8",
                           errors="replace").read()
            if "hermetic_seed" in text or base == "probe_bar_width.py":
                found.append(name)
    return sorted(found)


def spellings(name):
    """The rules that stop one script from starting at the project root."""
    base = os.path.basename(name)
    forms = [base, "./" + base]
    if name.startswith("qa/"):
        forms += ["qa/" + base, "qa\\" + base]
    return ["Bash(%s %s%s)" % (interp, form, tail)
            for interp in INTERPRETERS for form in forms for tail in ("", ":*")]


def deny_rules(path):
    with io.open(path, encoding="utf-8") as fh:
        return set(json.load(fh).get("permissions", {}).get("deny", []))


def machine_free(rule):
    """A live rule with this machine taken out, as the committed file holds it."""
    rule = re.sub(r"[A-Za-z]:\\Users\\[^\\]+\\", "~/", rule)
    rule = re.sub(r"[A-Za-z]:\\Projects\\NoteOrganizer\\", "./", rule)
    return rule.replace("\\", "/") if rule[:5] in ("Read(", "Edit(", "Write") else rule


def main():
    names = tracked()
    committed = deny_rules(COMMITTED)
    problems = []

    scripts = destructive_scripts(names)
    for name in scripts:
        for rule in spellings(name):
            if rule not in committed:
                problems.append("no deny rule for %s: %s" % (name, rule))

    for rule in sorted(committed):
        if rule in MACHINE_FREE_EXCEPTIONS:
            continue
        if re.search(r"[A-Za-z]:[\\/]|\\Users\\|/Users/|/home/", rule):
            problems.append("the committed file names a machine: %s" % rule)

    live_files = [p for p in LIVE if os.path.exists(p)]
    if live_files:
        live = set()
        for path in live_files:
            live |= {machine_free(r) for r in deny_rules(path)}
        for rule in sorted(committed - live):
            problems.append("committed but missing from the live lists: %s" % rule)

    if problems:
        for line in problems[:40]:
            print("    " + line)
        if len(problems) > 40:
            print("    ... and %d more" % (len(problems) - 40))
        print("%d problem(s). A missing rule goes into tools/agent_deny_rules.json "
              "and the live .claude/settings.json; a machine's path comes out "
              "of the committed file." % len(problems))
        return 1
    print("Deny rules cover %d destructive script(s) in %d spelling(s)%s."
          % (len(scripts), sum(len(spellings(s)) for s in scripts),
             ", and the live lists hold every one" if live_files else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
