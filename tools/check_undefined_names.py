"""Find names a module uses but never defines, imports, or gets for free.

WHY THIS EXISTS
---------------
When code is moved between files it stops seeing the imports of the file it
left. The moved code still *looks* correct, and — this is the part that
bites — the module still imports successfully, because Python only looks a
name up at the moment the line actually runs. So a function can sit there
happily broken until someone calls it.

That happened twice while extracting `noteorganizer/core/`:

* `sharing.py` used `base64`, `json`, `os` and `zlib` without importing any
  of them. It imported fine. It would have failed the first time anyone
  shared a note.
* Two re-export blocks were swallowed by a line-range removal, so the app
  called `normalize_formatting` and `_dup_key`, which no longer existed. It
  crashed on startup.

Both were found by running the app, which is a slow and unreliable way to
learn about it. This finds them by reading the source instead, before
anything runs.

USAGE
-----
    py tools/check_undefined_names.py note_organizer.py noteorganizer/core/*.py \
        noteorganizer/ui/*.py qa/*.py test_*.py tools/*.py      (as CI runs it)

Exits non-zero if anything is missing, so CI can use it as a gate.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It is a simple checker, not a type checker. It resolves names within a
module only, and treats every name bound *anywhere* in a file as available
everywhere in it, so it will not catch use-before-assignment. That is fine:
it exists to catch one specific mistake — a name with no source at all —
and it catches that reliably with no dependencies to install.
"""

import ast
import builtins
import sys
from pathlib import Path

# Names Python provides to every module without an import.
MODULE_GLOBALS = {
    "__file__", "__name__", "__doc__", "__package__", "__spec__",
    "__loader__", "__builtins__", "__path__", "__all__", "__debug__",
}


class _Collector(ast.NodeVisitor):
    """Gather every name a module binds, and every name it reads."""

    def __init__(self):
        self.defined = set()
        self.used = {}          # name -> first line it is read on

    # -- things that introduce names ------------------------------------
    def visit_Import(self, node):
        for alias in node.names:
            self.defined.add((alias.asname or alias.name).split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.defined.add(alias.asname or alias.name)
        self.generic_visit(node)

    def _function(self, node):
        self.defined.add(node.name)
        args = node.args
        for a in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            self.defined.add(a.arg)
        if args.vararg:
            self.defined.add(args.vararg.arg)
        if args.kwarg:
            self.defined.add(args.kwarg.arg)
        self.generic_visit(node)

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_Lambda(self, node):
        args = node.args
        for a in (*args.posonlyargs, *args.args, *args.kwonlyargs):
            self.defined.add(a.arg)
        if args.vararg:
            self.defined.add(args.vararg.arg)
        if args.kwarg:
            self.defined.add(args.kwarg.arg)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.defined.add(node.name)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.defined.add(node.name)
        self.generic_visit(node)

    def visit_Global(self, node):
        self.defined.update(node.names)
        self.generic_visit(node)

    def visit_Nonlocal(self, node):
        self.defined.update(node.names)
        self.generic_visit(node)

    # -- name reads and writes ------------------------------------------
    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.defined.add(node.id)
        elif node.id not in self.used:
            self.used[node.id] = node.lineno
        self.generic_visit(node)


def missing_names(path):
    """Names read in this file that nothing could provide.

    Returns a sorted list of (name, line_number).
    """
    collector = _Collector()
    collector.visit(ast.parse(Path(path).read_text(encoding="utf-8")))
    known = collector.defined | MODULE_GLOBALS | set(dir(builtins))
    return sorted((n, ln) for n, ln in collector.used.items() if n not in known)


def main(argv):
    paths = argv[1:]
    if not paths:
        print(__doc__.strip().splitlines()[0])
        print("\nusage: py tools/check_undefined_names.py FILE [FILE ...]")
        return 2

    failures = 0
    for path in paths:
        problems = missing_names(path)
        name = Path(path).name
        if problems:
            failures += 1
            print(f"FAIL {name}")
            for n, line in problems:
                print(f"       {n!r} used at line {line}, but never defined or imported")
        else:
            print(f"ok   {name}")

    print()
    if failures:
        print(f"{failures} file(s) reference names that do not exist.")
        print("Most likely cause: code was moved and left an import behind.")
        return 1
    print(f"All {len(paths)} file(s) resolve every name they use.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
