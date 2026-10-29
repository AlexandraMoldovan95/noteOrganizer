"""How much a group of the app's methods talk to each other.

The question ARCHITECTURE's case study asked before each extraction: of
the calls a candidate group makes to other methods of the class, what
share stays inside the group? A group whose calls mostly stay inside it
can leave without dragging the class behind it. The dialogs measured
62%, the calendar 59%, the note list 90%.

The class is read whole by default: the entry file and every mixin it is
built from, so a call into a method that has already moved counts like
any other. The first measurements read the entry file alone, which is the
blind spot ARCHITECTURE records; --hub-only measures that way again.

    py tools/call_graph.py --defined-in noteorganizer/ui/note_list.py
    py tools/call_graph.py --group names.txt          # one name a line
    py tools/call_graph.py --rev ef853c2~1 --hub-only \\
        --defined-in noteorganizer/ui/note_list.py    # the list before it moved

--rev reads the class from that commit; the group always comes from the
working tree. A reference such as self.save_note in command=... counts
as a call, as it did in the first measurement. Read-only. The graph
shortlists; reading the methods decides.
"""
import ast
import collections
import glob
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = "note_organizer.py"


def source(path, rev=None):
    """A file of the repository, from the working tree or from a commit."""
    if rev is None:
        return io.open(os.path.join(ROOT, path), encoding="utf-8").read()
    return subprocess.run(["git", "show", "%s:%s" % (rev, path)], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          check=True, timeout=120).stdout


def mixin_paths(rev=None):
    if rev is None:
        found = glob.glob(os.path.join(ROOT, "noteorganizer", "ui", "*.py"))
        return sorted(os.path.relpath(p, ROOT).replace(os.sep, "/") for p in found)
    listing = subprocess.run(["git", "ls-tree", "--name-only", rev,
                              "noteorganizer/ui/"], cwd=ROOT,
                             capture_output=True, text=True, check=True,
                             timeout=120).stdout
    return sorted(p for p in listing.split() if p.endswith(".py"))


def class_methods(path, rev=None, only=None):
    """{name: FunctionDef} for the classes of one file (NoteOrganizer, or
    the ...Mixin classes it is built from)."""
    tree = ast.parse(source(path, rev))
    methods = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if only is not None and node.name != only:
            continue
        if only is None and not node.name.endswith("Mixin"):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.setdefault(item.name, item)
    return methods


def the_class(rev=None, hub_only=False):
    """Every method of NoteOrganizer: its own body first, as Python looks
    them up, then each mixin's."""
    methods = class_methods(HUB, rev, only="NoteOrganizer")
    if not hub_only:
        for path in mixin_paths(rev):
            for name, fn in class_methods(path, rev).items():
                methods.setdefault(name, fn)
    return methods


def calls_of(fn, names):
    return [n.attr for n in ast.walk(fn)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
            and n.value.id == "self" and n.attr in names and n.attr != fn.name]


def main(argv):
    import guest  # the memory ceiling, before git starts (tools/guest.py)
    guest.settle(heavy=False)
    rev = argv[argv.index("--rev") + 1] if "--rev" in argv else None
    if "--defined-in" in argv:
        path = argv[argv.index("--defined-in") + 1]
        group = set(class_methods(path)) or set(class_methods(path, only="NoteOrganizer"))
    elif "--group" in argv:
        path = argv[argv.index("--group") + 1]
        group = {line.strip() for line in io.open(path, encoding="utf-8")
                 if line.strip() and not line.startswith("#")}
    else:
        print(__doc__)
        return 2

    methods = the_class(rev, hub_only="--hub-only" in argv)
    names = set(methods)
    missing = sorted(group - names)
    group &= names
    calls = {name: calls_of(fn, names) for name, fn in methods.items()}
    lines = sum(methods[m].end_lineno - methods[m].lineno + 1 for m in group)
    outgoing = [c for m in group for c in calls[m]]
    inside = sum(1 for c in outgoing if c in group)
    into = sum(1 for m in names - group for c in calls[m] if c in group)

    print("class read: %s%s, %d methods" % (
        "the entry file alone" if "--hub-only" in argv else "the entry file and its mixins",
        " at %s" % rev if rev else "", len(names)))
    print("group: %d methods, %d lines" % (len(group), lines))
    if missing:
        print("not in the class as read: %d (%s)" % (
            len(missing), ", ".join(missing[:8]) + (" ..." if len(missing) > 8 else "")))
    print("calls out of the group's methods: %d, staying inside: %d -> %.0f%%"
          % (len(outgoing), inside, 100.0 * inside / max(1, len(outgoing))))
    print("calls into the group from the rest of the class: %d" % into)
    outside = collections.Counter(c for c in outgoing if c not in group)
    print("most called outside it:", ", ".join(
        "%s (%d)" % pair for pair in outside.most_common(10)) or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
