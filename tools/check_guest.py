"""Fail when a test run could take more of this computer than a test should.

WHY THIS GATE EXISTS
--------------------
On 2026-10-29 a mutant made one test process take 43 GB: Windows ran out of
memory, its desktop window manager crashed, and the shadow copies of C: were
deleted under the load (ISSUES_LOG: "The test that took the computer down").
tools/guest.py now gives a run its turn, a memory ceiling, and a sweep of
what dead runs left. This gate holds it:

1. Every runner settles first. A runner is found by what it does, not by a
   list or a word: any .py under tools/, qa/ and site/tools/ that imports
   the app's code, builds the app, or starts a process -- except the suites
   a runner starts (qa1-qa9, test_*.py), which inherit the ceiling. Its
   syntax tree is walked along the paths it runs, from the top of the
   module through every function it calls by name: guest.settle() must
   come before the first import of the app and the first child, on every
   path. A runner that builds the app may not pass heavy=False.
2. Every child has a bound: subprocess.run/call/check_call/check_output
   pass timeout=, a Popen is waited on with one, and os.system, os.popen
   and os.startfile (which cannot be bounded) are not used.
3. No document or tool writes a docker run of its own: tools/linux_ci.py
   is the one door to the Linux image, bounded, named, and removed on
   every way out. A killed docker client leaves its container running.
4. The ceiling holds here: a process capped at 256 MB starts one that asks
   for 64 MB, which runs, and one that asks for 1 GB, which fails alone.
5. The turn holds here, on a private lock: a second run waits, names the
   holder and gives up with BUSY; the holder's own child does not wait; a
   holder killed outright frees the turn at once.

    py tools/check_guest.py
"""

import ast
import glob
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

import guest  # noqa: E402  (this folder; the ceiling for this gate's own children)

SUITE = re.compile(r"^(qa\d+|test_.*)\.py$")
# subprocess's calls that wait for their child, and so take timeout=.
WAITING = {"run", "call", "check_call", "check_output"}
STARTS = WAITING | {"Popen", "getoutput", "getstatusoutput"}
# os's ways to start a process; the first three cannot be given a bound.
UNBOUNDED = {"system", "popen", "startfile"}
OS_STARTS = UNBOUNDED | {"spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve",
                         "spawnvp", "spawnvpe", "execl", "execle", "execlp", "execlpe",
                         "execv", "execve", "execvp", "execvpe", "posix_spawn",
                         "posix_spawnp"}


def candidates():
    paths = []
    for pattern in ("tools/**/*.py", "qa/**/*.py", "site/tools/**/*.py"):
        paths += glob.glob(os.path.join(ROOT, *pattern.split("/")), recursive=True)
    for path in sorted(set(paths)):
        name = os.path.basename(path)
        if SUITE.match(name) or os.path.abspath(path) == os.path.join(HERE, "guest.py"):
            continue
        yield path


class Runner:
    """One script's syntax tree, and what the paths through it do."""

    def __init__(self, path):
        self.path = path
        self.tree = ast.parse(open(path, encoding="utf-8").read(), path)
        self.funcs = {n.name: n for n in self.tree.body
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        # A module-level dict of this file's functions, called by key
        # (CHAPTERS[number]()): each of them is reached by that call.
        self.tables = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                names = [v.id for v in node.value.values
                         if isinstance(v, ast.Name) and v.id in self.funcs]
                if names:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.tables[target.id] = names
        self.aliases = self._aliases()
        self.problems = []
        self.entered = {}
        self.reached = set()

    # -- what a node does --

    def _aliases(self):
        """Local names for subprocess/os/guest and for their functions."""
        found = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in ("subprocess", "os", "guest"):
                        found[a.asname or a.name] = (a.name, None)
            elif isinstance(node, ast.ImportFrom) and node.module in ("subprocess", "os", "guest"):
                for a in node.names:
                    found[a.asname or a.name] = (node.module, a.name)
        return found

    def callee(self, call):
        """(module, function) a call names, through this file's aliases."""
        f = call.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            mod = self.aliases.get(f.value.id)
            if mod and mod[1] is None:
                return mod[0], f.attr
        if isinstance(f, ast.Name) and f.id in self.aliases and self.aliases[f.id][1]:
            return self.aliases[f.id]
        return None, None

    def is_settle(self, call):
        return self.callee(call) == ("guest", "settle")

    def is_start(self, call):
        mod, name = self.callee(call)
        return (mod == "subprocess" and name in STARTS) or (mod == "os" and name in OS_STARTS)

    @staticmethod
    def builds_app(call):
        f = call.func
        return ((isinstance(f, ast.Name) and f.id == "NoteOrganizer")
                or (isinstance(f, ast.Attribute) and f.attr == "NoteOrganizer"))

    @staticmethod
    def imports_app(node):
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        return any(n.split(".")[0] in ("note_organizer", "noteorganizer") for n in names)

    def is_runner(self):
        for node in ast.walk(self.tree):
            if self.imports_app(node):
                return True
            if isinstance(node, ast.Call) and (self.is_start(node) or self.builds_app(node)):
                return True
        return False

    def builds_the_app(self):
        """In this process, or in a script it writes for a child to run."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and self.builds_app(node):
                return True
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and "NoteOrganizer(" in node.value and "import note_organizer" in node.value):
                return True
        return False

    # -- the walk: is the ceiling set before anything starts? --

    def problem(self, node, what):
        self.problems.append("%s:%d %s" % (os.path.relpath(self.path, ROOT),
                                           getattr(node, "lineno", 0), what))

    def block(self, stmts, settled):
        for s in stmts:
            settled = self.stmt(s, settled)
        return settled

    def stmt(self, s, settled):
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return settled
        if isinstance(s, (ast.Import, ast.ImportFrom)):
            if self.imports_app(s) and not settled:
                self.problem(s, "imports the app before guest.settle()")
            return settled
        if isinstance(s, ast.If):
            settled = self.expr(s.test, settled)
            body = self.block(s.body, settled)
            return self.block(s.orelse, settled) and body
        if isinstance(s, (ast.For, ast.AsyncFor, ast.While)):
            settled = self.expr(s.iter if hasattr(s, "iter") else s.test, settled)
            self.block(s.body, settled)
            self.block(s.orelse, settled)
            return settled
        if isinstance(s, (ast.With, ast.AsyncWith)):
            for item in s.items:
                settled = self.expr(item.context_expr, settled)
            return self.block(s.body, settled)
        if isinstance(s, ast.Try) or type(s).__name__ == "TryStar":
            body = self.block(s.body, settled)
            handled = [self.block(h.body, settled) for h in s.handlers]
            body = self.block(s.orelse, body)
            final = self.block(s.finalbody, settled)
            return final or (body and all(handled))
        if type(s).__name__ == "Match":
            settled = self.expr(s.subject, settled)
            return all([self.block(c.body, settled) for c in s.cases])
        return self.expr(s, settled)

    def expr(self, node, settled):
        for call in self.calls_in_order(node):
            settled = self.call(call, settled)
        return settled

    @staticmethod
    def calls_in_order(node):
        """Calls as Python evaluates them: arguments before the call."""
        out = []

        def visit(n):
            if isinstance(n, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return
            for child in ast.iter_child_nodes(n):
                visit(child)
            if isinstance(n, ast.Call):
                out.append(n)
        visit(node)
        return out

    def targets(self, call):
        f = call.func
        if isinstance(f, ast.Name) and f.id in self.funcs:
            return [f.id]
        if (isinstance(f, ast.Subscript) and isinstance(f.value, ast.Name)
                and f.value.id in self.tables):
            return self.tables[f.value.id]
        return []

    def call(self, c, settled):
        if self.is_settle(c):
            light = any(k.arg == "heavy" and isinstance(k.value, ast.Constant)
                        and k.value.value is False for k in c.keywords)
            if light and self.builds_the_app():
                self.problem(c, "builds the app, so it may not settle with heavy=False")
            return True
        if (self.is_start(c) or self.builds_app(c)) and not settled:
            self.problem(c, "starts a process or builds the app before guest.settle()")
            return settled
        names = self.targets(c)
        if not names:
            return settled
        if settled:
            for name in names:
                self.reach(name)
            return True
        return all([self.enter(name) for name in names])

    def enter(self, name):
        """Walk a function entered before the ceiling; True if it sets it on
        every path through it."""
        if name not in self.entered:
            self.entered[name] = False          # a cycle settles nothing
            self.reached.add(name)
            self.entered[name] = self.block(self.funcs[name].body, False)
        return self.entered[name]

    def reach(self, name):
        """A function called once the ceiling is set, and all it calls."""
        if name in self.reached:
            return
        self.reached.add(name)
        for node in ast.walk(self.funcs[name]):
            if isinstance(node, ast.Call):
                for target in self.targets(node):
                    self.reach(target)

    def check(self):
        settled_at_top = self.block(self.tree.body, False)
        # A function the walk never reached (a decorator's list, a callback)
        # may still start something: fine only once the module itself has
        # settled, at import, before anything could call it.
        for name, fn in self.funcs.items():
            if name in self.reached or settled_at_top:
                continue
            for node in ast.walk(fn):
                if ((isinstance(node, ast.Call) and (self.is_start(node) or self.builds_app(node)))
                        or self.imports_app(node)):
                    self.problem(node, "in %s(), which no path that has settled is seen to "
                                       "call: settle first in it, or call it by name" % name)
                    break
        self.bounds()
        return self.problems

    # -- every child has a bound --

    def bounds(self):
        scopes = [self.tree] + [n for n in ast.walk(self.tree)
                                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for scope in scopes:
            own = [n for n in self._own_nodes(scope) if isinstance(n, ast.Call)]
            waits = [n for n in own if isinstance(n.func, ast.Attribute)
                     and n.func.attr in ("wait", "communicate")]
            bounded = [n for n in waits if any(k.arg == "timeout" for k in n.keywords)]
            for call in own:
                mod, name = self.callee(call)
                if mod == "subprocess" and name in WAITING:
                    if not any(k.arg == "timeout" for k in call.keywords):
                        self.problem(call, "subprocess.%s without timeout=: a hang has no bound"
                                     % name)
                elif mod == "subprocess" and name == "Popen":
                    # Waited on, and every wait beside it bounded.
                    if not bounded:
                        self.problem(call, "a Popen never waited on with timeout=")
                    for wait in waits:
                        if wait not in bounded:
                            self.problem(wait, "a wait on a process without timeout=")
                elif mod == "os" and name in UNBOUNDED:
                    self.problem(call, "os.%s cannot be given a bound; use subprocess.run(..., "
                                       "timeout=)" % name)

    @staticmethod
    def _own_nodes(scope):
        """The nodes of a scope, not of the functions defined inside it."""
        out, stack = [], list(ast.iter_child_nodes(scope))
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            out.append(n)
            stack.extend(ast.iter_child_nodes(n))
        return out


def runners_without_settle():
    """Every problem in every runner, as 'path:line what'."""
    found = []
    for path in candidates():
        runner = Runner(path)
        if runner.is_runner():
            found += runner.check()
    return found


# -- 3: one door to the Linux image --

DOOR = os.path.join("tools", "linux_ci.py")
# The history may quote the commands it replaced, and this file names them.
EXEMPT = (DOOR, os.path.join("docs", "ISSUES_LOG.md"), os.path.join("tools", "check_guest.py"))
WRITTEN = ("*.md", "docs/**/*.md", "qa/**/*.md", "qa/**/*.py", "tools/**/*.py",
           "tools/**/Dockerfile", "tools/**/*.ps1", ".github/**/*.yml", "site/*.md",
           "site/tools/**/*")


def docker_runs_outside_the_door():
    hits, seen = [], set()
    for pattern in WRITTEN:
        for path in glob.glob(os.path.join(ROOT, *pattern.split("/")), recursive=True):
            rel = os.path.relpath(path, ROOT)
            if rel in seen or rel in EXEMPT or not os.path.isfile(path):
                continue
            seen.add(rel)
            try:
                text = open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if re.search(r"docker\s+(container\s+)?run\b", line):
                    hits.append("%s:%d" % (rel, number))
    return hits


# -- 4: the ceiling holds --

CHILD = r"""
import subprocess, sys
sys.path.insert(0, sys.argv[1])
import guest
print(guest.cap_memory(256, 512))
for mb in (64, 1024):
    r = subprocess.run([sys.executable, "-c", "b = bytearray(%d * 1048576)" % mb],
                       capture_output=True, text=True, timeout=120)
    print(mb, r.returncode, "MemoryError" in r.stderr)
"""


def ceiling_holds():
    out = subprocess.run([sys.executable, "-c", CHILD, HERE], capture_output=True,
                         text=True, timeout=120).stdout.splitlines()
    ok = (len(out) == 3 and "NO ceiling" not in out[0]
          and out[1] == "64 0 False" and out[2].startswith("1024 1") and out[2].endswith("True"))
    return ok, out


# -- 5: the turn holds --

HOLDER = r"""
import subprocess, sys, time
sys.path.insert(0, sys.argv[1])
import guest
guest.settle(256, 512, label="the-gate-holder", wait_s=0)
kid = ("import sys; sys.path.insert(0, sys.argv[1]); import guest; "
       "print(guest.settle(256, 512, wait_s=0)[0])")
r = subprocess.run([sys.executable, "-c", kid, sys.argv[1]], capture_output=True, text=True,
                   timeout=60)
print("KID", r.returncode, r.stdout.strip(), flush=True)
time.sleep(60)
"""

OTHER = r"""
import sys
sys.path.insert(0, sys.argv[1])
import guest
print(guest.settle(256, 512, wait_s=int(sys.argv[2]))[0], flush=True)
"""


def turn_holds():
    """The holder's child shares its turn; another run waits, names it and
    exits BUSY; a holder killed outright frees the turn."""
    locks = guest.scratch("noteorg-gate-lock-")    # marked: swept if this gate is killed
    env = dict(os.environ, NOTEORG_GUEST_LOCK_DIR=locks)
    env.pop(guest.HOLDER_ENV, None)
    seen, kid, other, after, took = [], "", None, None, 99.0
    holder = subprocess.Popen([sys.executable, "-c", HOLDER, HERE], env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        kid = holder.stdout.readline().strip()
        seen.append(kid)
        other = subprocess.run([sys.executable, "-c", OTHER, HERE, "3"], env=env,
                               capture_output=True, text=True, timeout=60)
        seen.append("%d %s" % (other.returncode, other.stdout.strip().replace("\n", " | ")))
        holder.kill()
        holder.wait(timeout=30)
        started = time.time()
        after = subprocess.run([sys.executable, "-c", OTHER, HERE, "10"], env=env,
                               capture_output=True, text=True, timeout=60)
        took = time.time() - started
        seen.append("%d %s (%.1f s)" % (after.returncode, after.stdout.strip(), took))
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=30)
        shutil.rmtree(locks, ignore_errors=True)
    ok = (kid.startswith("KID 0") and "the turn of the run that started this one" in kid
          and other is not None and other.returncode == guest.BUSY
          and "waiting for the-gate-holder" in other.stdout
          and after is not None and after.returncode == 0
          and "this run's turn" in after.stdout and took < 8)
    return ok, seen


def main():
    for line in guest.settle(heavy=False):
        print(line)
    missing = runners_without_settle()
    print("%s every runner sets the ceiling first, and bounds its children%s"
          % ("PASS" if not missing else "FAIL", "" if not missing else ":"))
    for line in missing:
        print("       " + line)
    doors = docker_runs_outside_the_door()
    print("%s the Linux image is run only through %s%s"
          % ("PASS" if not doors else "FAIL", DOOR, "" if not doors else ": " + ", ".join(doors)))
    ok, out = ceiling_holds()
    print("%s a process past the ceiling fails alone (%s)" % ("PASS" if ok else "FAIL", out))
    turn, seen = turn_holds()
    print("%s one heavy job at a time: %s" % ("PASS" if turn else "FAIL", seen))
    return 1 if missing or doors or not ok or not turn else 0


if __name__ == "__main__":
    sys.exit(main())
