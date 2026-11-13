"""Fail when a test run could take more of this computer than a test should.

WHY THIS GATE EXISTS
--------------------
On 2026-10-29 a mutant made one test process take 43 GB: Windows ran out of
memory, its desktop window manager crashed, and the shadow copies of C: were
deleted under the load (ISSUES_LOG: "The test that took the computer down").
tools/guest.py now gives a run its turn, a memory ceiling, and a sweep of
what dead runs left. This gate holds it:

1. Every runner settles first. A runner is found by what it does, not by a
   list or a word: any .py under tools/, qa/ and site/tools/, and every
   test_*.py, that imports the app's code (an import, importlib, runpy),
   builds the app, or starts a process (subprocess, os, multiprocessing, a
   process pool, asyncio, pty, webbrowser). Its syntax tree is walked along
   the paths it runs, from the top of the module through every function,
   nested function, lambda, class body and method it calls by name:
   guest.settle() must come before the first import of the app and the
   first child, on every path. A function the file never calls is called
   from another, and is walked as if before the ceiling: it settles first.
   A suite (qa1-qa9, test_*.py) settles through
   its guest step, qa/_qa_support.as_a_guest (which hermetic_seed calls):
   the suites were let off for "a runner starts them, and they inherit the
   ceiling", which nothing made true. A runner
   that builds the app, or starts a suite, the app or a runner that takes
   the turn, may not pass heavy=False.
2. Every child has a bound: subprocess.run/call/check_call/check_output
   pass timeout=, a Popen is waited on with one and is not left to a with
   block (whose exit waits with none), and the starts no timeout reaches
   -- os.system, os.popen, os.startfile, multiprocessing, process pools,
   asyncio's and pty's children, runpy, webbrowser -- are not used.
3. No document or tool starts a container of its own -- docker run,
   start, create, restart, unpause or compose's up, in the shapes
   DOCKER_SHAPES lists (the gate proves its pattern on them):
   tools/linux_ci.py is the one door to the Linux image, bounded, named,
   and removed on every way out. A killed docker client leaves its
   container running.
4. The ceiling holds here: a process capped at 256 MB starts one that asks
   for 64 MB, which runs, and one that asks for 1 GB, which fails alone.
5. The turn holds here, on a private lock: a second run waits, names the
   holder and gives up with BUSY; the holder's own child does not wait,
   nor does one whose temporary folder was moved (as run_tests moves each
   suite's); a holder killed outright frees the turn at once.
6. The homes hold here: a run started under an APPDATA that holds a
   notebook -- a stand-in, never the owner's -- and homes said to be
   inherited that APPDATA is not in, settles, and the app's own first
   start in an empty folder brings nothing in; its child keeps the same
   homes, and they are gone when the run ends.
7. Runners in other languages go through a door. A JavaScript file under
   the same folders that starts a process, and every shell script there
   (.ps1, .sh, .bat, .cmd: running commands is what they are for), checks
   before it starts anything that a Python runner which settled started
   it (guest.DOOR_ENV), and such a door names it -- or, for a script that
   runs inside Windows Sandbox, a throwaway machine, that it is there. The
   site's browser walk ran outside every guard.
   A sandbox guard is evaluated, not read for the account's name: it must
   refuse a user of this computer at the sandbox's folder and elsewhere,
   and the sandbox's account elsewhere, and let the sandbox's own start
   through; PowerShell, where there is one, is asked too. One that took
   the path alone as proof passed the name test. PowerShell's
   own parser, which runs nothing, reads the script as this gate does --
   nothing before the guard, no #requires, using or param block -- and
   only the literals' values are handed to PowerShell: this gate's reader
   once passed code after a block comment's '#>', and took a curly quote,
   at which PowerShell ends a string, for part of one.
8. The walk sees what it is shown: each shape in CASES, written to a
   scratch folder laid out as the repository is and found and walked as
   its files are, is caught or passes as it should; PowerShell's parser,
   where there is one, reads each PowerShell case as this gate does, and
   a literal handed to it stays one string.
9. What a run started ends with it: a process whose parent has gone, as
   Edge's have once node is gone, is ended by guest.end_others(); and a
   scratch folder something still holds stays marked for a later sweep.
10. The floor under the disk holds: a run with less free than its floor
    does not start, and one whose drive falls below it ends, and what it
    started ends with it.
11. The door to the Linux image shows the container only what git
    tracks, as the working tree has it: neither the ignored files (a
    notebook, settings, notebook_location.txt) nor what the ignore list
    misses (a Trash kept aside), read-only, with no network,
    and nothing writable but a /tmp sized inside its memory limit; and a
    link at a tracked name, which the copy followed, refuses
    the run.
12. A suite started outside a runner settles itself: each suite's opening
    lines, up to its guest step, run as CI runs them -- in the repository's
    layout, outside any run, under an APPDATA holding a stand-in notebook
    -- take the turn and homes of their own; in run_tests' scratch, beside
    a run that settled, they share its homes; and copied by hand without
    guest.py or the app, they refuse before they write anything. In a
    checkout whose notebook_location.txt names a stand-in notebook, by its
    path or through %USERPROFILE%, each refuses and the notebook stays as
    it was; so does a qa opening whose app would open another folder than
    its own. The guards looked beside themselves while the app opened the
    folder the file names: the owner's notebook.

    py tools/check_guest.py
"""

import ast
import base64
import getpass
import glob
import json
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
                         "posix_spawnp", "fork", "forkpty"}
# Other modules' ways to start a process, by function; None is every call
# into the module. No timeout this gate can see reaches any of them.
UNSEEN = {
    "multiprocessing": None,
    "concurrent.futures": {"ProcessPoolExecutor"},
    "asyncio": {"create_subprocess_exec", "create_subprocess_shell"},
    "pty": {"spawn", "fork"},
    "runpy": {"run_path", "run_module"},
    "webbrowser": None,
}
# An event loop's own ways, reached through the loop rather than a module.
LOOP_STARTS = {"subprocess_exec", "subprocess_shell"}
# Calls that import a module by its name or its file.
IMPORTERS = {("importlib", "import_module"), ("importlib.util", "spec_from_file_location"),
             ("importlib.machinery", "SourceFileLoader")}
APP_NAME = re.compile(r"^(note_organizer|noteorganizer)([./\\]|$)")
# A suite's guest step: it settles as guest.settle() does (item 12 runs it).
GUEST_STEPS = {("guest", "settle"), ("_qa_support", "as_a_guest"),
               ("_qa_support", "hermetic_seed"), ("_qa_support", "seed_here")}


def candidates(root=ROOT):
    paths = []
    for pattern in ("tools/**/*.py", "qa/**/*.py", "site/tools/**/*.py", "test_*.py"):
        paths += glob.glob(os.path.join(root, *pattern.split("/")), recursive=True)
    for path in sorted(set(paths)):
        if os.path.abspath(path) != os.path.join(root, "tools", "guest.py"):
            yield path


def suites(root=ROOT):
    return [path for path in candidates(root) if SUITE.match(os.path.basename(path))]


def _rel(path, root=ROOT):
    try:
        return os.path.relpath(path, root)
    except ValueError:   # on another drive
        return path


class Runner:
    """One script's syntax tree, and what the paths through it do."""

    def __init__(self, path, source=None, root=ROOT):
        self.path = path
        self.root = root
        if source is None:
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
        self.tree = ast.parse(source, path)
        # What a call can reach, by the name it is called with: the
        # functions of this file at any depth and the lambdas bound to a
        # name (go()), a class's __init__ (Story()), and the methods of
        # every class here (anything.run() may be any class's run).
        self.funcs, self.methods, self.inits = {}, {}, {}
        in_class = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        in_class.add(id(item))
                        self.methods.setdefault(item.name, []).append(item)
                        if item.name == "__init__":
                            self.inits.setdefault(node.name, []).append(item)
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and id(node) not in in_class:
                self.funcs.setdefault(node.name, []).append(node)
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Lambda):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.funcs.setdefault(target.id, []).append(node.value)
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
        self.entered = {}     # id of a function walked before the ceiling: settles on every path
        self.reached = set()  # ids of functions walked, or seen to run only once settled

    # -- what a node does --

    def _aliases(self):
        """Local names for modules and for what is imported from them."""
        found = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        found[a.asname] = a.name
                    else:
                        root = a.name.split(".")[0]
                        found[root] = root
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                for a in node.names:
                    found[a.asname or a.name] = node.module + "." + a.name
        return found

    def callee(self, call):
        """(module, function) a call names, through this file's aliases."""
        parts, node = [], call.func
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name) or node.id not in self.aliases:
            return None, None
        full = self.aliases[node.id].split(".") + parts[::-1]
        if len(full) < 2:
            return None, None
        return ".".join(full[:-1]), full[-1]

    def is_settle(self, call):
        return self.callee(call) in GUEST_STEPS

    def unseen(self, call):
        """A start no timeout reaches: (what it is, True), else ('', False)."""
        mod, name = self.callee(call)
        if mod is not None:
            for module, names in UNSEEN.items():
                if (mod == module or mod.startswith(module + ".")) and (
                        names is None or name in names):
                    return "%s.%s" % (mod, name), True
        f = call.func
        if isinstance(f, ast.Attribute) and f.attr in LOOP_STARTS:
            return "an event loop's " + f.attr, True
        return "", False

    def is_start(self, call):
        mod, name = self.callee(call)
        return ((mod == "subprocess" and name in STARTS) or (mod == "os" and name in OS_STARTS)
                or self.unseen(call)[1])

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

    def imports_app_call(self, call):
        """importlib or __import__ with the app's name or file -- or with a
        name this gate cannot read, which could be the app's."""
        f = call.func
        if not (self.callee(call) in IMPORTERS
                or (isinstance(f, ast.Name) and f.id == "__import__")):
            return False
        texts = [n.value for arg in list(call.args) + [k.value for k in call.keywords]
                 for n in ast.walk(arg) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        return not texts or any(APP_NAME.match(t) for t in texts)

    def does_something(self, node):
        return ((isinstance(node, ast.Call) and (self.is_start(node) or self.builds_app(node)
                                                 or self.imports_app_call(node)))
                or self.imports_app(node))

    def is_runner(self):
        return any(self.does_something(node) for node in ast.walk(self.tree))

    def builds_the_app(self):
        """In this process, or in a script it writes for a child to run."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and self.builds_app(node):
                return True
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and "NoteOrganizer(" in node.value and "import note_organizer" in node.value):
                return True
        return False

    def every_def(self):
        return [n for n in ast.walk(self.tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))]

    def starting(self):
        """Ids of this file's functions that start a process, themselves or
        through another of them."""
        found, grew, defs = set(), True, self.every_def()
        while grew:
            grew = False
            for d in defs:
                if id(d) not in found and any(
                        isinstance(n, ast.Call) and (self.is_start(n) or any(
                            id(t) in found for t in self.targets(n))) for n in ast.walk(d)):
                    found.add(id(d))
                    grew = True
        return found

    def scripts_started(self):
        """(call, script) for each start, or call of a function that starts,
        that names a .py: the first one it names, in the order written."""
        starting = self.starting()
        for n in ast.walk(self.tree):
            if isinstance(n, ast.Call) and (self.is_start(n) or any(
                    id(t) in starting for t in self.targets(n))):
                named = sorted((c.lineno, c.col_offset, c.value)
                               for arg in list(n.args) + [k.value for k in n.keywords]
                               for c in ast.walk(arg)
                               if isinstance(c, ast.Constant) and isinstance(c.value, str)
                               and c.value.endswith(".py"))
                if named:
                    yield n, named[0][2]

    # -- the walk: is the ceiling set before anything starts? --

    def problem(self, node, what):
        self.problems.append("%s:%d %s" % (_rel(self.path, self.root), getattr(node, "lineno", 0),
                                           what))

    def block(self, stmts, settled):
        for s in stmts:
            settled = self.stmt(s, settled)
        return settled

    def stmt(self, s, settled):
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Its decorators and defaults run here; its body when it is called.
            for e in s.decorator_list + s.args.defaults + [d for d in s.args.kw_defaults if d]:
                settled = self.expr(e, settled)
            if settled:
                self.reach(s)       # made once settled: whatever calls it, calls it after
            return settled
        if isinstance(s, ast.ClassDef):
            for e in s.decorator_list + s.bases + [k.value for k in s.keywords]:
                settled = self.expr(e, settled)
            return self.block(s.body, settled)   # a class's body runs where it stands
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
        if settled:   # a lambda made once settled runs, whenever it runs, after
            for n in ast.walk(node):
                if isinstance(n, ast.Lambda):
                    self.reach(n)
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
        """The functions of this file a call may run."""
        f = call.func
        if isinstance(f, ast.Name):
            return self.funcs.get(f.id) or self.inits.get(f.id, [])
        if isinstance(f, ast.Attribute):
            return self.methods.get(f.attr, [])
        if (isinstance(f, ast.Subscript) and isinstance(f.value, ast.Name)
                and f.value.id in self.tables):
            return [n for name in self.tables[f.value.id] for n in self.funcs.get(name, [])]
        return []

    def call(self, c, settled):
        if self.is_settle(c):
            light = any(k.arg == "heavy" and isinstance(k.value, ast.Constant)
                        and k.value.value is False for k in c.keywords)
            if light:
                if self.builds_the_app():
                    self.problem(c, "builds the app, so it may not settle with heavy=False")
                for where, script in self.scripts_started():
                    what = weigh(script)
                    if what:
                        self.problem(where, "settles with heavy=False but starts %s, %s: a "
                                            "light run starts only light things" % (script, what))
            return True
        if not settled:
            if self.is_start(c) or self.builds_app(c):
                self.problem(c, "starts a process or builds the app before guest.settle()")
                return settled
            if self.imports_app_call(c):
                self.problem(c, "imports the app before guest.settle()")
                return settled
        nodes = self.targets(c)
        if not nodes:
            return settled
        if settled:
            for node in nodes:
                self.reach(node)
            return True
        return all([self.enter(node) for node in nodes])

    def enter(self, node):
        """Walk a function entered before the ceiling; True if it sets it on
        every path through it."""
        key = id(node)
        if key not in self.entered:
            self.entered[key] = False           # a cycle settles nothing
            self.reached.add(key)
            if isinstance(node, ast.Lambda):
                self.entered[key] = self.expr(node.body, False)
            else:
                self.entered[key] = self.block(node.body, False)
        return self.entered[key]

    def reach(self, node):
        """A function that runs once the ceiling is set, what is defined in
        it, and all it calls."""
        if id(node) in self.reached:
            return
        self.reached.add(id(node))
        for n in ast.walk(node):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                self.reached.add(id(n))
            elif isinstance(n, ast.Call):
                for target in self.targets(n):
                    self.reach(target)

    def check(self):
        settled_at_top = self.block(self.tree.body, False)
        # A function the walk never reached (a decorator's list, a callback)
        # may still start something: fine only once the module itself has
        # settled, at import, before anything could call it -- or when it
        # settles first itself. One this file never calls is called from
        # elsewhere, settled or not: walked as if before the ceiling.
        if not settled_at_top:
            called = {id(t) for n in ast.walk(self.tree) if isinstance(n, ast.Call)
                      for t in self.targets(n)}
            for fn in self.every_def():
                if id(fn) not in self.reached and id(fn) not in called:
                    self.enter(fn)
            for fn in self.every_def():
                if id(fn) in self.reached:
                    continue
                for node in self._own_nodes(fn):
                    if self.does_something(node):
                        what = ("%s()" % fn.name if hasattr(fn, "name")
                                else "a lambda (line %d)" % fn.lineno)
                        self.problem(node, "in %s, which no path that has settled is seen to "
                                           "call: settle first in it, or call it by name" % what)
                        break
        self.bounds()
        return self.problems

    # -- every child has a bound --

    def bounds(self):
        scopes = [self.tree] + [n for n in ast.walk(self.tree) if isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))]
        for scope in scopes:
            own_nodes = self._own_nodes(scope)
            own = [n for n in own_nodes if isinstance(n, ast.Call)]
            waits = [n for n in own if isinstance(n.func, ast.Attribute)
                     and n.func.attr in ("wait", "communicate")]
            bounded = [n for n in waits if any(k.arg == "timeout" for k in n.keywords)]
            for call in own:
                mod, name = self.callee(call)
                what, unseen = self.unseen(call)
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
                elif unseen:
                    self.problem(call, "%s starts a process no timeout here can reach; use "
                                       "subprocess.run(..., timeout=)" % what)
            # A Popen's __exit__ waits for the child with no limit, and a
            # bounded wait inside that raises TimeoutExpired goes straight to it.
            for node in own_nodes:
                if isinstance(node, (ast.With, ast.AsyncWith)):
                    for item in node.items:
                        e = item.context_expr
                        if isinstance(e, ast.Call) and self.callee(e) == ("subprocess", "Popen"):
                            self.problem(e, "a Popen in a with block: leaving it waits with no "
                                            "bound when the block raises; wait with timeout= "
                                            "and kill it yourself")

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


_WEIGHED = {}


def weigh(script):
    """What a light run would start in ``script``, when that is not a light
    thing: a suite, the app, or a runner that takes the turn; '' if light."""
    name = os.path.basename(script.replace("\\", "/"))
    if SUITE.match(name):
        return "a suite"
    if name == "note_organizer.py":
        return "the app"
    if name not in _WEIGHED:
        _WEIGHED[name] = ""
        for path in candidates():
            if os.path.basename(path) != name:
                continue
            runner = Runner(path)
            settles = [n for n in ast.walk(runner.tree)
                       if isinstance(n, ast.Call) and runner.is_settle(n)]
            light = settles and all(any(
                k.arg == "heavy" and isinstance(k.value, ast.Constant) and k.value.value is False
                for k in n.keywords) for n in settles)
            if runner.is_runner() and not light:
                _WEIGHED[name] = "a runner that takes the machine's turn"
    return _WEIGHED[name]


def runners_without_settle(root=ROOT):
    """Every problem in every runner, as 'path:line what'."""
    found = []
    for path in candidates(root):
        runner = Runner(path, root=root)
        if runner.is_runner():
            found += runner.check()
    return found


# -- 7: runners in other languages go through a door --

OTHER_LANGUAGES = (".mjs", ".js", ".cjs", ".ps1", ".psm1", ".sh", ".bash", ".bat", ".cmd")
SHELLS = (".ps1", ".psm1", ".sh", ".bash", ".bat", ".cmd")
# A JavaScript file starts a process through child_process (or a runtime's own).
NODE_STARTS = re.compile(r"child_process|\bDeno\.(?:Command|run)\b|\bBun\.spawn")
NODE_START_CALL = re.compile(r"\b(?:spawn|spawnSync|exec|execSync|execFile|execFileSync|fork)"
                             r"\s*\(|\bDeno\.(?:Command|run)\b|\bBun\.spawn")
# Windows Sandbox's one account, and the folder the .wsb that
# tools/msix/make_sandbox_test.py writes maps and starts its script from.
SANDBOX_ACCOUNT = "WDAGUtilityAccount"
SANDBOX_FOLDER = "C:\\pkg"
# A sandbox guard is evaluated, not read for the account's name (one that
# took the path alone as proof passed that), so it has one shape,
# GUARD_SHAPE, in which no evaluation can run anything. PowerShell's own parser
# reads it too, where there is one: this reader once missed code after a
# block comment's '#>', and quotes PowerShell ends a string at.
PS_QUOTES = "'‘’‚‛"
PS_TOKEN = re.compile(r"\s*(?:(?P<text>'(?:[^%s]|'')*')|(?P<var>\$[A-Za-z_][\w:]*)"
                      r"|(?P<op>-[A-Za-z]+)|(?P<word>[A-Za-z][\w-]*)|(?P<num>\d+)"
                      r"|(?P<mark>[(){};]))" % PS_QUOTES)
GUARD_VARS = {"$env:username": "$u", "$pscommandpath": "$p"}
GUARD_SHAPE = ("if (<$env:USERNAME and $PSCommandPath against literals, joined by -and or "
               "-or>) { [Write-Output '...';] exit <n> }")


def ps_tokens(text):
    tokens, at, text = [], 0, text.rstrip()
    while at < len(text):
        m = PS_TOKEN.match(text, at)
        if not m:
            return None
        tokens.append((m.lastgroup, m.group(m.lastgroup)))
        at = m.end()
    return tokens


def sandbox_guard(first):
    """A sandbox script's first statement read as its guard: (terms, the
    operator joining them), each term a (variable, equal?, literal's value);
    None when it is not of the one shape."""
    tokens = ps_tokens(first)
    low = [(kind, value.lower()) for kind, value in tokens or []]
    if low[:2] != [("word", "if"), ("mark", "(")] or ("mark", ")") not in low:
        return None
    close = low.index(("mark", ")"))
    cond, body = tokens[2:close], low[close + 1:]
    if body[:1] != [("mark", "{")] or body[-1:] != [("mark", "}")]:
        return None
    body = body[1:-1]
    if body[:1] == [("word", "write-output")]:
        if len(body) < 3 or body[1][0] != "text" or body[2] != ("mark", ";"):
            return None
        body = body[3:]
    if body[-1:] == [("mark", ";")]:
        body = body[:-1]
    if len(body) != 2 or body[0] != ("word", "exit") or body[1][0] != "num" or not int(body[1][1]):
        return None
    terms, joins, at = [], set(), 0
    while True:
        term = cond[at:at + 3]
        if len(term) == 3 and term[0][0] == "text":
            term = [term[2], term[1], term[0]]
        if (len(term) != 3 or term[0][0] != "var" or term[0][1].lower() not in GUARD_VARS
                or term[1][0] != "op" or term[1][1].lower() not in ("-eq", "-ne")
                or term[2][0] != "text"):
            return None
        terms.append((term[0][1].lower(), term[1][1].lower() == "-eq",
                      term[2][1][1:-1].replace("''", "'")))
        at += 3
        if at == len(cond):
            break
        if cond[at][0] != "op" or cond[at][1].lower() not in ("-and", "-or"):
            return None
        joins.add(cond[at][1].lower())
        at += 1
    if len(joins) > 1:
        return None
    return terms, (joins.pop() if joins else "-or")


def guard_refuses(guard, user, path):
    """Whether the guard refuses ``user`` running the script from ``path``:
    PowerShell compares strings without regard to case."""
    terms, join = guard
    held = [((user if var == "$env:username" else path).casefold() == literal.casefold()) == equal
            for var, equal, literal in terms]
    return all(held) if join == "-and" else any(held)


def sandbox_starts(path):
    """(user, path it is started from, must the guard refuse): a user of
    this computer at the sandbox's folder and where the script lies, the
    sandbox's account where it lies, and the sandbox's own start."""
    here = getpass.getuser()
    if here.casefold() == SANDBOX_ACCOUNT.casefold():
        here = "a-user-of-this-computer"
    at_pkg = SANDBOX_FOLDER + "\\" + os.path.basename(path)
    lies = os.path.abspath(path)
    return [(here, at_pkg, True), (here, at_pkg.lower(), True), (here, lies, True),
            (SANDBOX_ACCOUNT, lies, True), (SANDBOX_ACCOUNT, at_pkg, False)]


def powershell():
    return shutil.which("powershell") or shutil.which("pwsh")


def ps_literal(value):
    """``value`` as a PowerShell single-quoted literal: every quote PowerShell
    ends such a string at is doubled, so the value stays one string."""
    return "'%s'" % "".join(c * 2 if c in PS_QUOTES else c for c in value)


def run_powershell(script, env=None, timeout=60):
    """PowerShell's output for ``script``, passed encoded (no quoting of it
    by a command line), or the reason it could not be asked."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        run = subprocess.run([powershell(), "-NoProfile", "-NonInteractive", "-EncodedCommand",
                              encoded], capture_output=True, text=True, timeout=timeout,
                             env=env, encoding="utf-8", errors="replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    return run.stdout, (run.stdout + run.stderr).strip()[-200:]


def powershell_reads(guard, starts):
    """PowerShell's own verdict on the guard's condition for each start, or
    None where there is no PowerShell to ask. The condition is built from
    the literals' values, never from the script's text: nothing to run."""
    if not powershell():
        return None
    terms, join = guard
    cond = (" %s " % join).join("(%s %s %s)" % (GUARD_VARS[var], "-eq" if equal else "-ne",
                                                  ps_literal(literal))
                                for var, equal, literal in terms)
    rows = ",".join("@(%s,%s)" % (ps_literal(user), ps_literal(where)) for user, where, _ in starts)
    out, said = run_powershell("foreach ($c in @(%s)) { $u = $c[0]; $p = $c[1]; [bool](%s) }"
                               % (rows, cond))
    verdicts = [line.strip() == "True" for line in (out or "").splitlines()
                if line.strip() in ("True", "False")]
    return verdicts or [said]


# PowerShell's parser reads each script, and runs nothing: its first statement
# must be the guard, before which nothing may run -- no #requires or using
# (they load modules), no param, begin, process or dynamicparam block.
PS_READER = r"""
function B64($s) { [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([string]$s)) }
function Term($e) {
  if ($e -isnot [System.Management.Automation.Language.BinaryExpressionAst]) { return $false }
  $op = $e.ErrorPosition.Text.ToLowerInvariant()
  if ($op -eq '-and' -or $op -eq '-or') {
    $script:joins[$op] = 1
    return ((Term $e.Left) -and (Term $e.Right))
  }
  if ($op -ne '-eq' -and $op -ne '-ne') { return $false }
  $v, $s = $e.Left, $e.Right
  if ($v -is [System.Management.Automation.Language.StringConstantExpressionAst]) { $v, $s = $s, $v }
  if ($v -isnot [System.Management.Automation.Language.VariableExpressionAst] -or $v.Splatted) { return $false }
  if ($s -isnot [System.Management.Automation.Language.StringConstantExpressionAst]) { return $false }
  if ([string]$s.StringConstantType -ne 'SingleQuoted') { return $false }
  $name = '$' + $v.VariablePath.UserPath.ToLowerInvariant()
  if ($name -ne '$env:username' -and $name -ne '$pscommandpath') { return $false }
  $script:terms += ,@($name, $op, $s.Value)
  return $true
}
function Guard($path) {
  $tokens = $null; $errors = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)
  if ($errors.Count) { return 'NOT it does not parse' }
  if ($ast.ScriptRequirements -or $ast.UsingStatements.Count) { return 'NOT #requires or using loads code before its first statement' }
  if ($ast.ParamBlock -or $ast.DynamicParamBlock -or $ast.BeginBlock -or $ast.ProcessBlock) { return 'NOT a param, begin, process or dynamicparam block runs before its first statement' }
  if (-not $ast.EndBlock -or $ast.EndBlock.Traps.Count -or $ast.EndBlock.Statements.Count -eq 0) { return 'NOT no first statement, or a trap' }
  $first = $ast.EndBlock.Statements[0]
  if ($first -isnot [System.Management.Automation.Language.IfStatementAst] -or $first.Clauses.Count -ne 1 -or $first.ElseClause) { return 'NOT its first statement is not an if of one clause' }
  $cond = $first.Clauses[0].Item1.GetPureExpression()
  $script:terms = @(); $script:joins = @{}
  if (-not (Term $cond) -or $script:joins.Count -gt 1) { return 'NOT its condition is not comparisons of $env:USERNAME and $PSCommandPath with single-quoted literals' }
  $body = @($first.Clauses[0].Item2.Statements)
  if ($body.Count -eq 2) {
    $w = $body[0]
    $c = if ($w -is [System.Management.Automation.Language.PipelineAst] -and $w.PipelineElements.Count -eq 1) { $w.PipelineElements[0] }
    if ($c -isnot [System.Management.Automation.Language.CommandAst] -or $c.CommandElements.Count -ne 2 -or $c.Redirections.Count -or [string]$c.InvocationOperator -ne 'Unknown' -or $c.GetCommandName() -ne 'Write-Output' -or $c.CommandElements[1] -isnot [System.Management.Automation.Language.StringConstantExpressionAst] -or [string]$c.CommandElements[1].StringConstantType -ne 'SingleQuoted') { return 'NOT its first step is not Write-Output of a literal' }
  } elseif ($body.Count -ne 1) { return 'NOT its body is not [Write-Output; ] exit' }
  $x = $body[$body.Count - 1]
  $n = if ($x -is [System.Management.Automation.Language.ExitStatementAst] -and $x.Pipeline) { $x.Pipeline.GetPureExpression() }
  if ($n -isnot [System.Management.Automation.Language.ConstantExpressionAst] -or $n.Value -isnot [int] -or $n.Value -eq 0) { return 'NOT it does not end in exit with a code other than 0' }
  $out = @()
  foreach ($t in $script:terms) { $out += ('TERM ' + $t[0] + ' ' + $t[1] + ' ' + (B64 $t[2])) }
  $join = '-or'
  foreach ($k in $script:joins.Keys) { $join = $k }
  return ($out + @('JOIN ' + $join))
}
foreach ($path in ($env:NOTEORG_GATE_PS_FILES -split "`n")) {
  if (-not $path) { continue }
  'FILE ' + (B64 $path)
  try { Guard $path } catch { 'NOT PowerShell could not read it: ' + $_.Exception.Message }
}
"""
PS_FILES_ENV = "NOTEORG_GATE_PS_FILES"
_PS_READ = {}


def powershell_guards(paths):
    """PowerShell's parser's reading of each script's guard: (terms, join) as
    sandbox_guard gives them, or the reason it is not one; {} where there is
    no PowerShell. Read in one PowerShell for all, once each."""
    if not powershell():
        return {}
    keys = {os.path.normcase(os.path.abspath(p)): p for p in paths}
    wanted = [p for k, p in keys.items() if k not in _PS_READ]
    if wanted:
        env = dict(os.environ)
        env[PS_FILES_ENV] = "\n".join(os.path.abspath(p) for p in wanted)
        out, said = run_powershell(PS_READER, env=env, timeout=120)
        read, at = {}, None
        try:
            for line in (out or "").splitlines():
                kind, _, rest = line.strip().partition(" ")
                if kind == "FILE":
                    at = os.path.normcase(base64.b64decode(rest, validate=True).decode("utf-8"))
                    read[at] = "PowerShell said nothing of it"
                elif at is None or kind not in ("NOT", "TERM", "JOIN"):
                    continue
                elif kind == "NOT":
                    read[at] = rest
                else:
                    terms, join = read[at] if isinstance(read[at], tuple) else ([], None)
                    if kind == "TERM":
                        var, op, value = rest.split(" ")
                        terms.append((var, op == "-eq",
                                      base64.b64decode(value, validate=True).decode("utf-8")))
                    read[at] = (terms, rest if kind == "JOIN" else join)
        except ValueError as exc:
            read = {}
            said = "its answer could not be read (%s)" % exc
        for k in (os.path.normcase(os.path.abspath(p)) for p in wanted):
            _PS_READ[k] = read.get(k, "PowerShell could not be asked: %s" % said)
    return {p: _PS_READ[k] for k, p in keys.items()}


def sandbox_guard_problems(path, first, ext, rel):
    guard = sandbox_guard(first) if ext in (".ps1", ".psm1") else None
    if guard is None:
        return ["%s: a script for Windows Sandbox starts with its guard, in the one shape this "
                "gate can evaluate: %s" % (rel, GUARD_SHAPE)]
    read = powershell_guards([path]).get(path)
    if read is not None and read != guard:
        return ["%s: PowerShell's parser reads its first statement otherwise than this gate "
                "(%s)" % (rel, read if isinstance(read, str) else "terms %s" % (read,))]
    starts, found = sandbox_starts(path), []
    verdicts = [guard_refuses(guard, user, where) for user, where, _ in starts]
    for (user, where, refuse), refused in zip(starts, verdicts):
        if refuse and not refused:
            found.append("%s: its guard lets it run outside the sandbox, for %s at %s"
                         % (rel, user, where))
        elif refused and not refuse:
            found.append("%s: its guard refuses the sandbox's own start, %s at %s"
                         % (rel, user, where))
    read = powershell_reads(guard, starts)
    if read is not None and read != verdicts:
        found.append("%s: PowerShell reads its guard otherwise than this gate (%s, against %s)"
                     % (rel, read, verdicts))
    return found


def other_candidates(root=ROOT):
    for pattern in ("tools/**/*", "qa/**/*", "site/tools/**/*"):
        for path in sorted(glob.glob(os.path.join(root, *pattern.split("/")), recursive=True)):
            if os.path.isfile(path) and path.lower().endswith(OTHER_LANGUAGES):
                yield path


def first_statement(text, ext):
    """The first line of a shell script that does something: in PowerShell,
    what follows a block comment's '#>' on its line, and #requires, which
    loads modules before the first statement runs."""
    in_block = False
    for line in text.splitlines():
        s = line.strip()
        while s and (in_block or s.startswith("<#")):     # PowerShell's block comment
            if not in_block:
                in_block, s = True, s[2:]
            end = s.find("#>")
            in_block, s = (True, "") if end < 0 else (False, s[end + 2:].strip())
        low = s.lower()
        if ext in (".ps1", ".psm1") and low.startswith("#requires"):
            return s
        if not s or s.startswith("#"):
            continue
        if ext in (".bat", ".cmd") and (low.startswith(("rem ", "::")) or low in ("rem", "@echo off")):
            continue
        return s
    return ""


def script_problems(path, doors, root=ROOT):
    """What is wrong with one script in another language; ``doors`` is the
    text of every Python runner, to find its door in."""
    rel = _rel(path, root)
    with open(path, encoding="utf-8-sig", errors="replace") as fh:   # a BOM is not a statement
        text = fh.read()
    ext = os.path.splitext(path)[1].lower()
    if ext in SHELLS:
        first = first_statement(text, ext)
        if guest.DOOR_ENV not in first and SANDBOX_ACCOUNT.lower() not in first.lower():
            return ["%s: a shell script runs commands, so its first statement refuses to run "
                    "but through its door (%s) or inside Windows Sandbox (%s)"
                    % (rel, guest.DOOR_ENV, SANDBOX_ACCOUNT)]
        if guest.DOOR_ENV not in first:
            return sandbox_guard_problems(path, first, ext, rel)
        needs_door = True
    else:
        if not NODE_STARTS.search(text):
            return []
        start = NODE_START_CALL.search(text)
        guard = text.find(guest.DOOR_ENV)
        if guard < 0 or (start is not None and start.start() < guard):
            at = start.start() if start is not None else 0
            return ["%s:%d starts a process before it checks %s, the mark of its door"
                    % (rel, text.count("\n", 0, at) + 1, guest.DOOR_ENV)]
        needs_door = True
    name = os.path.basename(path)
    if needs_door and not any(name in door and "DOOR_ENV" in door for door in doors):
        return ["%s: no Python runner is its door (one that names it and, once settled, "
                "hands it guest.DOOR_ENV)" % rel]
    return []


def scripts_without_a_door(root=ROOT):
    doors = []
    for path in candidates(root):
        with open(path, encoding="utf-8") as fh:
            doors.append(fh.read())
    found = []
    for path in other_candidates(root):
        found += script_problems(path, doors, root)
    return found


# -- 3: one door to the Linux image --

DOOR = os.path.join("tools", "linux_ci.py")
# The history may quote the commands it replaced, and this file names them.
EXEMPT = (DOOR, os.path.join("docs", "ISSUES_LOG.md"), os.path.join("tools", "check_guest.py"))
WRITTEN = ("*.md", "*.py", "docs/**/*.md", "qa/**/*.md", "qa/**/*.py", "tools/**/*.py",
           "tools/**/Dockerfile", "tools/**/*.ps1", ".github/**/*.yml", ".github/**/*.yaml",
           "site/*.md", "site/**/*.py", "site/tools/**/*", "**/*.sh", "**/*.bat", "**/*.cmd")


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
            # Read across lines: a subprocess list split over two missed.
            for found in DOCKER_STARTS.finditer(text):
                hits.append("%s:%d" % (rel, text.count("\n", 0, found.start()) + 1))
    return hits


# The shapes a container is started in: typed, in an f-string, as a list for
# subprocess or a helper's arguments, through a name of its own (DOCKER,
# docker_exe, run_docker), docker.exe, global flags before the verb, and
# compose's own verbs, up among them. Lower case as commands are written:
# "keep Docker up to date" in prose is not one. A rewrite once dropped
# compose's middle word; every shape seen since is in its self-test below.
_D_NAME = r"""(?:\b\w*docker\w*(?:\.exe)?|\bDOCKER\w*)"""
# A comma or a bracket after a closing quote or before an opening one, as
# code writes it: "docker, run it" and "docker (start it first)" are prose.
# A shell's line continuation.
_D_GAP = r"""(?:[}"']\s*[\\`]?\s*[,(]?\s*[{"']?|\s*[\\`]?\s*(?:[,(]\s*[{"']|[{"']?))"""
_D_FLAG = (r"""(?:--?[a-zA-Z][\w-]*""" + _D_GAP
           + r"""(?:[^\s"',()\[\]{}-][^\s"',()\[\]{}]*""" + _D_GAP + r""")?"""
           + r"""|\{[^{}\n]*\}\s*)""")
_D_VERB = r"""(?:run|start|create|restart|unpause)"""
DOCKER_STARTS = re.compile(
    _D_NAME + _D_GAP + "(?:" + _D_FLAG + ")*(?:container" + _D_GAP + "(?:" + _D_FLAG + ")*)?"
    + _D_VERB + r"\b"
    + "|" + _D_NAME + r"(?:[-_]|" + _D_GAP + ")" + "(?:" + _D_FLAG + ")*compose" + _D_GAP
    + "(?:" + _D_FLAG + ")*(?:" + _D_VERB + r"|up)\b"
    # A list built in pieces (DOCKER + ["run"], [docker, *flags, "run"]):
    # the verb quoted, later in the same expression.
    + "|" + _D_NAME + r"""["']?\]?\s*(?:\+|,\s*\*)[^\n;]{0,60}?["'](?:""" + _D_VERB + r"|up)[\"']"
    + "|" + _D_NAME + r"""["']?,\s*f["'][^"'\n]*["'],\s*["']""" + _D_VERB + r"[\"']")

# Shapes the pattern must see, and prose it must not take for a command.
DOCKER_SHAPES = [
    "docker run x", "docker start web", "docker create img", "docker restart a", "docker unpause a",
    "docker container restart a", "docker.exe run img", "docker --context x run img",
    "docker -H tcp://h:2375 run img", "docker-compose up", "docker-compose -f ci.yml up",
    "docker compose up", "docker compose run --rm app", "docker compose start", "docker compose -f x.yml up",
    '["docker", "run", "-it"]', '[DOCKER, "run", "-it"]', '[docker,\n   "run"]', '[docker_exe, "run"]',
    '["docker", "compose", "up", "-d"]', '["docker", "compose", "run", "app"]',
    '["docker", "--context", ctx, "run"]', '["docker", "-H", host, "start"]', 'docker("run", "img")',
    '_docker("run")', 'run_docker("run")', 'f"{docker} run"', 'subprocess.run(["docker", "start", name])',
    'subprocess.run(DOCKER + ["run", img])', '["docker"] + ["run", img]', '[docker, *flags, "run"]',
    '["docker", f"--context={ctx}", "run"]', 'f"docker {flags} run"', "docker \\\n    run img",
    "docker `\n    run img",
]
DOCKER_PROSE = [
    "keep Docker up to date", "Open Docker, start the app", "Docker\nStart it", "docker ps", "docker build .",
    "docker exec it", "docker images", "the docker image is started by linux_ci", "docker compose ps",
    "with docker, run tools/linux_ci.py", "needs docker (start Docker Desktop first)",
]


# -- 8: the walk sees what it is shown --

# Each case: a file name, what one of its problems must say ('' for none),
# and its text: the fourteen shapes the walk once passed come first,
# and those with '' pass, so a walk that flags everything fails too.
CASES = [
    ("class_method.py", "before guest.settle()", """
import subprocess, sys
class Story:
    def run(self):
        subprocess.run([sys.executable, "-c", "pass"], timeout=5)
Story().run()
import guest
guest.settle()
"""),
    ("nested_function.py", "before guest.settle()", """
import subprocess, sys
def main():
    def go():
        subprocess.run([sys.executable, "-c", "pass"], timeout=5)
    go()
    import guest
    guest.settle()
main()
"""),
    ("lambda_by_name.py", "before guest.settle()", """
import subprocess, sys
go = lambda: subprocess.run([sys.executable, "-c", "pass"], timeout=5)
go()
import guest
guest.settle()
"""),
    ("multiprocessing_child.py", "no timeout here can reach", """
import multiprocessing
def work():
    pass
if __name__ == "__main__":
    import guest
    guest.settle()
    p = multiprocessing.Process(target=work)
    p.start()
    p.join()
"""),
    ("process_pool.py", "no timeout here can reach", """
from concurrent.futures import ProcessPoolExecutor
import guest
guest.settle()
with ProcessPoolExecutor() as pool:
    list(pool.map(abs, range(3)))
"""),
    ("asyncio_child.py", "before guest.settle()", """
import asyncio, sys
async def main():
    p = await asyncio.create_subprocess_exec(sys.executable, "-c", "pass")
    await p.wait()
asyncio.run(main())
"""),
    ("runpy_app.py", "no timeout here can reach", """
import runpy
import guest
guest.settle()
runpy.run_path("note_organizer.py", run_name="__main__")
"""),
    ("with_popen.py", "in a with block", """
import guest
guest.settle()
import subprocess, sys
with subprocess.Popen([sys.executable, "-c", "pass"]) as p:
    p.wait(timeout=1)
"""),
    ("importlib_app.py", "imports the app before guest.settle()", """
import importlib
NO = importlib.import_module("note_organizer")
"""),
    ("settle_in_if.py", "before guest.settle()", """
import guest, subprocess, sys
if len(sys.argv) > 1:
    guest.settle()
subprocess.run([sys.executable, "-c", "pass"], timeout=5)
"""),
    ("alias.py", "before guest.settle()", """
import guest as g
import subprocess as sp, sys
sp.run([sys.executable, "-c", "pass"], timeout=5)
g.settle()
"""),
    ("webbrowser_open.py", "no timeout here can reach", """
import webbrowser
import guest
guest.settle()
webbrowser.open("about:blank")
"""),
    ("method_before_settle_in_main.py", "before guest.settle()", """
import subprocess, sys
class R:
    def go(self):
        subprocess.run([sys.executable, "-c", "pass"], timeout=5)
def main():
    R().go()
    import guest
    guest.settle()
if __name__ == "__main__":
    main()
"""),
    ("light_runs_a_suite.py", "a light run starts only light things", """
import guest, subprocess, sys
guest.settle(heavy=False)
subprocess.run([sys.executable, "qa1.py"], timeout=600)
"""),
    ("class_body.py", "before guest.settle()", """
import subprocess, sys
class Probe:
    answer = subprocess.run([sys.executable, "-c", "pass"], timeout=5)
import guest
guest.settle()
"""),
    ("method_after_settle.py", "", """
import subprocess, sys
class R:
    def go(self):
        subprocess.run([sys.executable, "-c", "pass"], timeout=5)
def main():
    import guest
    guest.settle()
    R().go()
if __name__ == "__main__":
    main()
"""),
    ("nested_after_settle.py", "", """
import subprocess, sys
def main():
    import guest
    guest.settle()
    def go():
        subprocess.run([sys.executable, "-c", "pass"], timeout=5)
    go()
main()
"""),
    ("light_runs_a_gate.py", "", """
import os, subprocess, sys
import guest
guest.settle(heavy=False)
subprocess.run([sys.executable, os.path.join("tools", "check_english.py")], timeout=600)
"""),
    ("bounded_popen.py", "", """
import subprocess, sys
import guest
guest.settle()
p = subprocess.Popen([sys.executable, "-c", "pass"])
try:
    p.wait(timeout=5)
finally:
    if p.poll() is None:
        p.kill()
        p.wait(timeout=5)
"""),
    ("walk_bare.mjs", "before it checks", """
import { spawn } from "node:child_process";
spawn("msedge.exe", ["--headless"]);
"""),
    ("walk_late_guard.mjs", "before it checks", """
import { spawn } from "node:child_process";
spawn("msedge.exe", ["--headless"]);
if (!process.env.NOTEORG_GUEST_DOOR) process.exit(2);
"""),
    ("walk_no_door.mjs", "no Python runner is its door", """
import { spawn } from "node:child_process";
if (!process.env.NOTEORG_GUEST_DOOR) process.exit(2);
spawn("msedge.exe", ["--headless"]);
"""),
    ("walk_through_door.mjs", "", """
import { spawn } from "node:child_process";
if (!process.env.NOTEORG_GUEST_DOOR) process.exit(2);
spawn("msedge.exe", ["--headless"]);
"""),
    ("starts_nothing.js", "", """
const x = /a/.exec("abc");
console.log(x);
"""),
    ("host_script.ps1", "a shell script runs commands", """
# Signs a package.
$ErrorActionPreference = 'Continue'
& signtool.exe sign package.msix
"""),
    ("sandbox_script.ps1", "", """
<# Runs inside Windows Sandbox. #>
if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $PSCommandPath -ne 'C:\\pkg\\sandbox_script.ps1') { exit 2 }
& signtool.exe sign package.msix
"""),
    ("sandbox_path_alone.ps1", "lets it run outside the sandbox", """
if ($env:USERNAME -ne 'WDAGUtilityAccount' -and $PSCommandPath -ne 'C:\\pkg\\sandbox_path_alone.ps1') { exit 2 }
& signtool.exe sign package.msix
"""),
    ("sandbox_account_alone.ps1", "lets it run outside the sandbox", """
if ($env:USERNAME -ne 'WDAGUtilityAccount') { Write-Output 'only in the sandbox'; exit 2 }
& signtool.exe sign package.msix
"""),
    ("sandbox_lower_case.ps1", "", """
if ($env:USERNAME -ne 'wdagutilityaccount' -or $PSCommandPath -ne 'c:\\pkg\\sandbox_lower_case.ps1') { exit 2 }
& signtool.exe sign package.msix
"""),
    ("sandbox_refuses_itself.ps1", "refuses the sandbox's own start", """
if ('WDAGUtilityAccount' -ne $env:USERNAME -or $PSCommandPath -ne 'C:\\pkg\\another.ps1') { exit 2 }
"""),
    ("sandbox_no_exit.ps1", "the one shape this gate can evaluate", """
if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $PSCommandPath -ne 'C:\\pkg\\sandbox_no_exit.ps1') { Write-Output 'not here' }
& signtool.exe sign package.msix
"""),
    ("late_guard.sh", "a shell script runs commands", """
#!/bin/sh
echo starting
[ -n "$NOTEORG_GUEST_DOOR" ] || exit 2
"""),
    ("walk_door.py", "", """
import subprocess
import guest
guest.settle()
folder = guest.scratch("noteorg-site-walk-")
subprocess.run(["node", "walk_through_door.mjs"], env={guest.DOOR_ENV: folder}, timeout=60)
"""),
    ("test_app_first.py", "imports the app before guest.settle()", """
import os, sys
import note_organizer
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa"))
from _qa_support import as_a_guest
as_a_guest()
"""),
    ("test_guest_first.py", "", """
import os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa"))
from _qa_support import as_a_guest
as_a_guest()
import note_organizer
"""),
    ("qa0.py", "", """
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()
import note_organizer as NO
"""),
    ("tool_seeds_here.py", "", """
from _qa_support import seed_here
seed_here()
import note_organizer as NO
"""),
    # A function another file calls: it settles first, or says what it does before.
    ("entry_settles_first.py", "", """
def the_app():
    import guest
    guest.settle()
    import note_organizer
    return note_organizer
"""),
    ("entry_imports_first.py", "imports the app before guest.settle()", """
def the_app():
    import note_organizer
    import guest
    guest.settle()
    return note_organizer
"""),
    # What PowerShell runs before the guard this gate read, and
    # quotes it ends a string at. Each is read by PowerShell's parser too.
    ("inline_block_comment.ps1", "a shell script runs commands", """
<# header #> Write-Output 'ran before the guard'
if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $PSCommandPath -ne 'C:\\pkg\\inline_block_comment.ps1') { exit 2 }
"""),
    ("block_close_line.ps1", "a shell script runs commands", """
<#
 header
#> Write-Output 'ran before the guard'
if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $PSCommandPath -ne 'C:\\pkg\\block_close_line.ps1') { exit 2 }
"""),
    ("typographic_quote.ps1", "the one shape this gate can evaluate", """
if ($env:USERNAME -ne 'WDAGUtilityAccount\u2019+([IO.File]::WriteAllText($env:NOTEORG_GATE_RAN, "x"))+\u2018' -or $PSCommandPath -ne 'C:\\pkg\\typographic_quote.ps1') { exit 2 }
"""),
    ("requires_module.ps1", "a shell script runs commands", """
#Requires -Modules SomeModule
if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $PSCommandPath -ne 'C:\\pkg\\requires_module.ps1') { exit 2 }
"""),
    ("param_block.ps1", "a shell script runs commands", """
param($Where = 'C:\\pkg')
if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $PSCommandPath -ne 'C:\\pkg\\param_block.ps1') { exit 2 }
"""),
    ("begin_block.ps1", "a shell script runs commands", """
begin { Write-Output 'ran before the guard' }
end { if ($env:USERNAME -ne 'WDAGUtilityAccount' -or $PSCommandPath -ne 'C:\\pkg\\begin_block.ps1') { exit 2 } }
"""),
]
# Where a case is written, below the folder walked as the repository is:
# by its kind, so every folder the gate looks in is looked in ('' is the root).
PLACES = {".py": "tools", ".mjs": "site/tools", ".js": "tools", ".ps1": "tools/msix",
          ".sh": "qa", "light_runs_a_suite.py": "qa", "class_body.py": "site/tools",
          "walk_door.py": "site/tools", "test_app_first.py": "", "test_guest_first.py": "",
          "qa0.py": "qa"}
# What the typographic quote's case would write, were reading it to run it.
RAN_ENV = "NOTEORG_GATE_RAN"


def walk_sees_its_cases():
    """The cases written to a scratch folder laid out as the repository is,
    found and walked as the repository's files are, and weighed against
    what each should give; returns (all as they should be, what was wrong)."""
    folder = guest.scratch("noteorg-gate-cases-")   # marked: swept if this gate is killed
    wrong, ran = [], os.path.join(folder, "ran-inside-the-gate")
    held = os.environ.get(RAN_ENV)
    os.environ[RAN_ENV] = ran
    try:
        where, scripts = {}, {}
        for name, _expect, text in CASES:
            place = PLACES[name] if name in PLACES else PLACES[os.path.splitext(name)[1]]
            where[name] = (place + "/" if place else "") + name
            os.makedirs(os.path.join(folder, *place.split("/")), exist_ok=True)
            path = os.path.join(folder, *where[name].split("/"))
            # PowerShell's scripts with a BOM: Windows PowerShell reads one
            # without as the machine's code page, which has no curly quotes.
            with open(path, "w", encoding="utf-8-sig" if name.endswith(".ps1") else "utf-8") as fh:
                fh.write(text.lstrip("\n"))
            if name.endswith(".ps1"):
                scripts[name] = (path, text.lstrip("\n"))
        powershell_guards([path for path, _text in scripts.values()])   # one PowerShell for all
        found = runners_without_settle(folder) + scripts_without_a_door(folder)
        for name, expect, _text in CASES:
            said = [line for line in found
                    if line.split(":")[0].replace("\\", "/") == where[name]]
            if expect and not any(expect in line for line in said):
                wrong.append("%s passed, though it should give '%s'" % (name, expect))
            elif not expect and said:
                wrong.append("%s gave %s, though it should pass" % (name, said))
        wrong += readers_agree(scripts)
        if os.path.exists(ran):
            wrong.append("reading the cases ran one: %s was written" % ran)
    finally:
        guest.remove(folder)
        if held is None:
            os.environ.pop(RAN_ENV, None)
        else:
            os.environ[RAN_ENV] = held
    return not wrong, wrong


def readers_agree(scripts):
    """Where there is PowerShell, its parser reads each PowerShell case as
    this gate reads it -- the same guard, or none -- and a literal this gate
    hands it stays one string, whatever quotes it holds."""
    if not powershell():
        return []
    wrong = []
    read = powershell_guards([path for path, _text in scripts.values()])
    for name, (path, text) in sorted(scripts.items()):
        mine, theirs = sandbox_guard(first_statement(text, ".ps1")), read.get(path)
        if mine is None and not isinstance(theirs, str) or mine is not None and theirs != mine:
            wrong.append("%s: PowerShell's parser reads %s, this gate %s" % (name, theirs, mine))
    values = ["a\u2019+(7*6)+\u2018b", "O'Brien", "\u201bx\u201a", "C:\\pkg\\x.ps1"]
    out, said = run_powershell("foreach ($s in @(%s)) { [Convert]::ToBase64String("
                               "[Text.Encoding]::UTF8.GetBytes($s)) }"
                               % ",".join(ps_literal(v) for v in values))
    try:
        back = [base64.b64decode(line.strip(), validate=True).decode("utf-8", "replace")
                for line in (out or "").splitlines() if line.strip()]
    except ValueError:
        back = None
    if back != values:
        wrong.append("a literal handed to PowerShell did not stay one string: %s, from %s (%s)"
                     % (ascii(back), ascii(values), ascii(said)))
    return wrong


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
import os, subprocess, sys, tempfile, time
sys.path.insert(0, sys.argv[1])
import guest
guest.settle(256, 512, label="the-gate-holder", wait_s=0)
kid = ("import sys; sys.path.insert(0, sys.argv[1]); import guest; "
       "print(guest.settle(256, 512, wait_s=0)[0])")
r = subprocess.run([sys.executable, "-c", kid, sys.argv[1]], capture_output=True, text=True,
                   timeout=60)
# And one whose temporary folder was moved, as run_tests moves each suite's.
moved = tempfile.mkdtemp(dir=os.environ[guest.LOCK_DIR_ENV])
env = dict(os.environ, TEMP=moved, TMP=moved, TMPDIR=moved)
env.pop(guest.LOCK_DIR_ENV)
m = subprocess.run([sys.executable, "-c", kid, sys.argv[1]], capture_output=True, text=True,
                   timeout=60, env=env)
print("KID", r.returncode, r.stdout.strip(), "| MOVED", m.returncode, m.stdout.strip(),
      flush=True)
time.sleep(60)
"""

OTHER = r"""
import sys
sys.path.insert(0, sys.argv[1])
import guest
print(guest.settle(256, 512, wait_s=int(sys.argv[2]))[0], flush=True)
"""


def private_turn_env(locks):
    """This environment with a lock of the gate's own: its runs never wait
    on, or hold up, the machine's real turn."""
    env = dict(os.environ, NOTEORG_GUEST_LOCK_DIR=locks)
    env.pop(guest.HOLDER_ENV, None)
    return env


def turn_holds():
    """The holder's child shares its turn; another run waits, names it and
    exits BUSY; a holder killed outright frees the turn."""
    locks = guest.scratch("noteorg-gate-lock-")    # marked: swept if this gate is killed
    env = private_turn_env(locks)
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
    kid_here, _, moved = kid.partition("| MOVED")
    ok = (kid_here.startswith("KID 0") and "the turn of the run that started this one" in kid_here
          and moved.strip().startswith("0 ")
          and "the turn of the run that started this one" in moved
          and other is not None and other.returncode == guest.BUSY
          and "waiting for the-gate-holder" in other.stdout
          and after is not None and after.returncode == 0
          and "this run's turn" in after.stdout and took < 8)
    return ok, seen


# -- 6: the homes hold --

HOMED = r"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import guest
guest.settle(heavy=False)
from noteorganizer.core import paths
empty = tempfile.mkdtemp(prefix="noteorg-gate-empty-", dir=os.environ[guest.HOMES_ENV])
said = paths.run_migrations(empty)
kid = subprocess.run([sys.executable, "-c", "import os, sys; sys.path.insert(0, sys.argv[1]); "
                      "import guest; print(guest.settle(heavy=False)[-1]); print(os.environ['APPDATA'])",
                      sys.argv[1]], capture_output=True, text=True, timeout=60).stdout.splitlines()
print(json.dumps({"homes": os.environ[guest.HOMES_ENV], "appdata": paths.get_appdata_dir(),
                  "said": said, "brought": sorted(os.listdir(empty)), "kid": kid,
                  "userbase": os.environ.get("PYTHONUSERBASE")}))
"""


def homes_hold():
    """Under an APPDATA holding a notebook, a settled run brings none of it in."""
    standin = guest.scratch("noteorg-gate-appdata-")   # marked: swept if this gate is killed
    try:
        store = os.path.join(standin, "NoteOrganizer")
        os.makedirs(store)
        with open(os.path.join(store, "notes_data.json"), "w", encoding="utf-8") as fh:
            fh.write('[{"id": 1, "uid": "gate-1", "title": "A stand-in notebook", "body": "x"}]')
        # And homes said to be inherited, where APPDATA does not point: a
        # run trusts its parent's homes only when they are the ones in use.
        elsewhere = os.path.join(standin, "elsewhere")
        os.makedirs(elsewhere)
        env = dict(os.environ, APPDATA=standin, LOCALAPPDATA=standin, XDG_DATA_HOME=standin)
        env[guest.HOMES_ENV] = elsewhere
        run = subprocess.run([sys.executable, "-c", HOMED, HERE, ROOT], env=env,
                             capture_output=True, text=True, timeout=120)
        try:
            seen = json.loads(run.stdout.strip().splitlines()[-1])
        except (IndexError, ValueError):
            return False, (run.stdout + run.stderr)[-400:]
        homes = seen["homes"]
        ok = (guest._inside(seen["appdata"], homes) and not seen["said"]
              and seen["brought"] == [] and len(seen["kid"]) == 2
              and "the run that started this one's" in seen["kid"][0]
              and guest._inside(seen["kid"][1], homes)
              and bool(seen["userbase"]) and not os.path.exists(homes))
        return ok, "%s, brought %s, child %s, gone after %s" % (
            seen["appdata"], seen["brought"], seen["kid"][:1], not os.path.exists(homes))
    finally:
        shutil.rmtree(standin, ignore_errors=True)


# -- 9: what a run started ends with it --

ORPHANED = r"""
import json, subprocess, sys, time
sys.path.insert(0, sys.argv[1])
import guest
guest.settle(256, 512, heavy=False)
# A child that starts a grandchild and leaves it: its parent gone, as
# Edge's is once node has gone.
leaver = ("import subprocess, sys; n = subprocess.DEVNULL; p = subprocess.Popen("
          "[sys.executable, '-c', 'import time; time.sleep(60)'], stdin=n, stdout=n, "
          "stderr=n); print(p.pid)")
kid = subprocess.run([sys.executable, "-c", leaver], capture_output=True, text=True, timeout=60)
pid = int(kid.stdout.strip())
born = guest.born_at(pid)
before = guest.alive(pid, born)
ended = guest.end_others()
for _ in range(50):
    if not guest.alive(pid, born):
        break
    time.sleep(0.1)
print(json.dumps({"before": before, "ended": ended, "after": guest.alive(pid, born)}))
"""


def leftovers_end():
    """A grandchild whose parent has gone is ended by end_others(); a
    scratch folder something still holds when it is removed stays marked,
    for a later sweep, and goes once it is let go."""
    if sys.platform != "win32":
        return None, "no job object on this OS (the browser walk runs on Windows only)"
    run = subprocess.run([sys.executable, "-c", ORPHANED, HERE], capture_output=True,
                         text=True, timeout=120)
    try:
        seen = json.loads(run.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return False, (run.stdout + run.stderr)[-400:]
    folder = guest.scratch("noteorg-gate-held-")
    held = open(os.path.join(folder, "held.txt"), "w")   # Windows will not delete it while open
    try:
        guest.remove(folder)
        seen["held stays marked"] = os.path.isdir(folder) and guest.read_marker(folder) is not None
    finally:
        held.close()
        guest.remove(folder)
    seen["then gone"] = not os.path.exists(folder)
    shutil.rmtree(folder, ignore_errors=True)   # the gate's own, should remove() have failed
    return bool(seen["before"] and seen["ended"] and not seen["after"]
                and seen["held stays marked"] and seen["then gone"]), seen


# -- 10: the floor under the disk holds --

FLOORED = r"""
import os, subprocess, sys, time
sys.path.insert(0, sys.argv[1])
import guest
guest.settle(256, 512, label="the-gate-disk", wait_s=0)
n = subprocess.DEVNULL
kid = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdin=n,
                       stdout=n, stderr=n)
print("KID", kid.pid, guest.born_at(kid.pid), flush=True)
guest._free_mb = lambda folder: 0     # the drive, as a runaway writer would leave it
time.sleep(20)
print("STILL RUNNING", flush=True)
kid.kill()
kid.wait(timeout=30)
"""


def floor_holds():
    """Below its floor a run does not start; a run whose drive falls below
    it ends, and its child with it."""
    if sys.platform != "win32":
        return None, "no job object on this OS (the Linux image's /tmp is a sized tmpfs)"
    locks = guest.scratch("noteorg-gate-disk-")    # marked: swept if this gate is killed
    try:
        env = private_turn_env(locks)
        env[guest.DISK_ENV] = str(10 ** 9)
        refused = subprocess.run([sys.executable, "-c", OTHER, HERE, "0"], env=env,
                                 capture_output=True, text=True, timeout=60)
        env[guest.DISK_ENV] = "1"
        ended = subprocess.run([sys.executable, "-c", FLOORED, HERE], env=env,
                               capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(locks, ignore_errors=True)
    kid = [l.split() for l in ended.stdout.splitlines() if l.startswith("KID ")]
    kid_alive = True
    if kid and len(kid[0]) == 3:
        pid, born = int(kid[0][1]), (None if kid[0][2] == "None" else float(kid[0][2]))
        for _ in range(50):
            kid_alive = guest.alive(pid, born)
            if not kid_alive:
                break
            time.sleep(0.1)
    ok = bool(refused.returncode == guest.DISK_LOW and "disk    : REFUSED" in refused.stdout
              and ended.returncode == guest.DISK_LOW and "disk    : STOPPED" in ended.stdout
              and "STILL RUNNING" not in ended.stdout and kid and not kid_alive)
    return ok, "refused %d, ended %d, its child alive after: %s" % (
        refused.returncode, ended.returncode, kid_alive)


# -- 11: the Linux image sees only what git tracks --

def door_shows_only_tracked():
    """linux_ci's copy of a stand-in repository holds what git tracks, as
    the working tree has it: nothing it ignores, and nothing it does not
    track that the ignore list misses (the app's copy of a Trash kept
    aside); and the container's /repo is that copy, with
    no network, a sized /tmp and nothing else writable."""
    import linux_ci
    work = guest.scratch("noteorg-gate-git-")       # marked: swept if this gate is killed
    try:
        repo = os.path.join(work, "repo")
        os.makedirs(repo)

        def write(name, text):
            with open(os.path.join(repo, name), "w", encoding="utf-8") as fh:
                fh.write(text)

        def git(*args):
            # Inside the Linux image GIT_DIR names the real repository's.
            return subprocess.run(["git", "-c", "init.defaultBranch=main", "-c",
                                   "core.autocrlf=false"] + list(args), cwd=repo,
                                  env=linux_ci.git_env(), capture_output=True, text=True,
                                  timeout=60)

        if git("init", "-q").returncode != 0:
            return False, "git init failed here"
        write(".gitignore", "notes_data*.json\nnotebook_location.txt\n")
        write("tracked.txt", "as added")
        git("add", ".gitignore", "tracked.txt")
        write("tracked.txt", "as the working tree has it")
        write("new.txt", "not yet added")
        write("notes_data.json", '[{"title": "A stand-in notebook"}]')
        write("notebook_location.txt", "a stand-in folder")
        write("trash_corrupt_20261030_101500.json", '[{"title": "A stand-in deleted note"}]')
        copy = linux_ci.tracked_copy(repo)
        try:
            shown = os.path.join(copy, "repo")
            seen = sorted(os.path.relpath(os.path.join(top, f), shown).replace(os.sep, "/")
                          for top, _dirs, files in os.walk(shown) for f in files)
            with open(os.path.join(shown, "tracked.txt"), encoding="utf-8") as fh:
                body = fh.read()
            cmd = linux_ci.command("noteorg-ci-gate", None, 60, [], shown)
        finally:
            guest.remove(copy)
        # And git's own folder beside the copy, for a checkout and a worktree.
        git("-c", "user.name=gate", "-c", "user.email=gate@invalid", "commit", "-q", "-m", "x")
        git("worktree", "add", "-q", os.path.join(work, "wt"))
        dot_git = os.path.join(repo, ".git")
        mounts = {}
        for kind, where in (("checkout", repo), ("worktree", os.path.join(work, "wt"))):
            args = linux_ci.git_mounts(where)
            source = [a for a in args if "target=/gitcommon" in a]
            source = source[0].split("source=")[1].split(",")[0] if source else ""
            mounts[kind] = (bool(source) and os.path.exists(source)
                            and os.path.samefile(source, dot_git),
                            [a for a in args if a.startswith("GIT_DIR=")])
        linked = links_refused(work, repo, git)
    except RuntimeError as exc:
        return False, str(exc)
    finally:
        guest.remove(work)
    # A folder holding a git repository goes too: git's objects are read-only.
    gone = not os.path.exists(work)
    sources = [part.split("source=")[1].split(",")[0] for part in cmd if "source=" in part]
    at_repo = [part for part in cmd if "target=/repo," in part or part.endswith("target=/repo")]
    ok = (gone and seen == [".gitignore", "tracked.txt"]
          and body == "as the working tree has it"
          and at_repo == ["type=bind,source=%s,target=/repo,readonly" % shown]
          and ROOT not in sources
          and "none" == cmd[cmd.index("--network") + 1]
          and "--read-only" in cmd
          and any(part.startswith("/tmp:") and "size=" in part for part in cmd)
          and mounts["checkout"] == (True, ["GIT_DIR=/gitcommon"])
          and mounts["worktree"] == (True, ["GIT_DIR=/gitcommon/worktrees/wt"])
          and linked["folder"] == "refused"
          and (linked["file"] == "refused" or linked["file"].startswith("not tried")))
    return ok, ("shown %s; /repo %s; network %s; read-only %s; git %s; a link at a tracked "
                "name %s; stand-in gone after: %s" % (
                    seen, at_repo, cmd[cmd.index("--network") + 1] if "--network" in cmd
                    else "default", "--read-only" in cmd, mounts, linked, gone))


def links_refused(work, repo, git):
    """A tracked folder, then a tracked file, replaced by a link to a
    stand-in notebook: the copy refuses each, naming it, and shows nothing
    of it (the copy followed links). A file link
    needs a privilege Windows may not give; a junction does not."""
    import linux_ci
    her = os.path.join(work, "her")
    os.makedirs(her)
    for name in ("guide.md", "notes_data.json"):
        with open(os.path.join(her, name), "w", encoding="utf-8") as fh:
            fh.write('[{"title": "A stand-in notebook, through a link"}]')
    os.makedirs(os.path.join(repo, "docs"))
    for name in ("docs/guide.md", "linked.txt"):
        with open(os.path.join(repo, *name.split("/")), "w", encoding="utf-8") as fh:
            fh.write("tracked")
    git("add", "docs/guide.md", "linked.txt")

    def copied(link):
        try:
            copy = linux_ci.tracked_copy(repo)
        except RuntimeError as exc:
            return "refused" if link in str(exc) else "refused, not naming it: %s" % exc
        try:
            shown = [os.path.join(top, f) for top, _dirs, files in os.walk(copy) for f in files]
            leaked = any("through a link" in open(p, encoding="utf-8", errors="replace").read()
                         for p in shown)
        finally:
            guest.remove(copy)
        return "copied" + (", the stand-in notebook in it" if leaked else "")

    said = {}
    folder = os.path.join(repo, "docs")
    shutil.rmtree(folder)
    try:
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(her, folder)
        else:
            os.symlink(her, folder, target_is_directory=True)
    except OSError as exc:
        said["folder"] = "no link could be made: %s" % exc
    else:
        try:
            said["folder"] = copied(folder)
        finally:
            if os.name == "nt":
                os.rmdir(folder)        # the junction, not what it points at
            else:
                os.remove(folder)
    os.makedirs(folder)
    with open(os.path.join(folder, "guide.md"), "w", encoding="utf-8") as fh:
        fh.write("tracked")
    linked = os.path.join(repo, "linked.txt")
    os.remove(linked)
    try:
        os.symlink(os.path.join(her, "notes_data.json"), linked)
    except OSError as exc:
        said["file"] = "not tried: %s" % (exc.strerror or exc)
    else:
        try:
            said["file"] = copied(linked)
        finally:
            os.remove(linked)
    return said


# -- 12: a suite started outside a runner settles itself --

# Put after a suite's opening lines: where its guest step left it.
REPORT = ("\nimport json as _gate_json, os as _gate_os\n"
          "print('GUEST ' + _gate_json.dumps({'appdata': _gate_os.environ.get('APPDATA'), "
          "'homes': _gate_os.environ.get(%r)}), flush=True)\n" % guest.HOMES_ENV)


def opening(path):
    """A suite's lines up to and including the top-level statement that
    takes its guest step, itself or through a function of the file; None
    when none does."""
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    runner = Runner(path, source=source)
    for stmt in runner.tree.body:
        if not isinstance(stmt, ast.Expr):
            continue
        for call in Runner.calls_in_order(stmt):
            reached = [call] + [n for t in runner.targets(call) for n in ast.walk(t)]
            if any(isinstance(n, ast.Call) and runner.is_settle(n) for n in reached):
                return "".join(source.splitlines(True)[:stmt.end_lineno])
    return None


def outside_a_run(work, standin):
    """An environment no run settled, as CI's or a person's is, with an
    APPDATA holding a stand-in notebook and a temporary folder of the
    gate's own (its turn, its homes, its sweep)."""
    tmp = os.path.join(work, "tmp")
    os.makedirs(tmp, exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if k not in (guest.HOMES_ENV, guest.HOLDER_ENV, guest.LOCK_DIR_ENV)}
    env.update(APPDATA=standin, LOCALAPPDATA=standin, XDG_DATA_HOME=standin, TEMP=tmp,
               TMP=tmp, TMPDIR=tmp, NOTEORG_SCRATCH="1", PYTHONIOENCODING="utf-8")
    env[guest.DISK_ENV] = "0"
    return env


def start(path, env, cwd=None):
    """Run a stand-in: from its own folder, as CI does, or from ``cwd``."""
    run = subprocess.run([sys.executable, path if cwd else os.path.basename(path)],
                         cwd=cwd or os.path.dirname(path),
                         env=env, capture_output=True, text=True, timeout=120,
                         encoding="utf-8", errors="replace")
    said = [json.loads(line[6:]) for line in run.stdout.splitlines() if line.startswith("GUEST ")]
    return run, (said[-1] if said else None)


def settled_alone(run, seen, standin):
    return bool(run.returncode == 0 and seen and seen["homes"]
                and guest._inside(seen["appdata"], seen["homes"])
                and not guest._inside(seen["homes"], standin)
                and "this run's turn" in run.stdout and not os.path.exists(seen["homes"]))


def lay_app(folder):
    """The app as a checkout or a scratch copy has it: the entry file and its package."""
    os.makedirs(folder, exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "note_organizer.py"), folder)
    shutil.copytree(os.path.join(ROOT, "noteorganizer"), os.path.join(folder, "noteorganizer"),
                    ignore=shutil.ignore_patterns("__pycache__"))


def lay_repo(repo, openings, ci_copy):
    """The repository's layout with the suites' openings where the suites
    are, and the app in qa/ too when ``ci_copy`` (CI copies it there)."""
    lay_app(repo)
    for folder in ("qa", "tools"):
        os.makedirs(os.path.join(repo, folder), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "qa", "_qa_support.py"), os.path.join(repo, "qa"))
    shutil.copy2(os.path.join(HERE, "guest.py"), os.path.join(repo, "tools"))
    if ci_copy:
        lay_app(os.path.join(repo, "qa"))
    stands = []
    for name, in_qa, text in openings:
        stand = os.path.join(repo, "qa" if in_qa else "", name)
        with open(stand, "w", encoding="utf-8") as fh:
            fh.write(text + REPORT)
        stands.append((name, in_qa, stand))
    return stands


def files_of(folder):
    """A folder's files and what they hold, to see whether a run touched it."""
    if not os.path.isdir(folder):
        return None
    found = {}
    for name in sorted(os.listdir(folder)):
        if os.path.isfile(os.path.join(folder, name)):
            with open(os.path.join(folder, name), "rb") as fh:
                found[name] = fh.read()
    return found


def refused_untouched(run, seen, watched, before, seeded):
    """A run that refused, said so, and changed nothing: ``watched`` as it
    was (``before``), and no seed written in any folder of ``seeded``."""
    return (run.returncode != 0 and "REFUSING" in run.stdout + run.stderr and seen is None
            and files_of(watched) == before
            and not any(os.path.exists(os.path.join(f, n)) for f in seeded
                        for n in ("notes_data.json", "settings.json")))


def her_notebook(folder):
    """A stand-in for the notebook a checkout's notebook_location.txt names --
    never the owner's: three files, as bytes."""
    os.makedirs(folder, exist_ok=True)
    for name, text in (("notes_data.json", '[{"id": 1, "uid": "her-1", "title": "Her note"}]'),
                       ("trash.json", '[{"id": 2, "uid": "her-2", "title": "Her deleted note"}]'),
                       ("settings.json", '{"theme": "dark"}')):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    return files_of(folder)


def suites_settle_themselves():
    """Each suite's opening, up to its guest step, run as CI runs it and as
    a person would by hand, takes homes and a turn of its own; beside a run
    that settled, in run_tests' scratch, it shares that run's homes; copied
    without guest.py or without the app, it refuses before it writes
    anything; and beside a notebook the app would open, each refuses
    (beside_a_named_notebook)."""
    import run_tests
    work = guest.scratch("noteorg-gate-suites-")    # marked: swept if this gate is killed
    wrong, seen_kinds, openings = [], {}, []
    try:
        standin = os.path.join(work, "appdata")
        os.makedirs(os.path.join(standin, "NoteOrganizer"))
        with open(os.path.join(standin, "NoteOrganizer", "notes_data.json"), "w",
                  encoding="utf-8") as fh:
            fh.write('[{"id": 1, "uid": "gate-1", "title": "A stand-in notebook"}]')
        env = outside_a_run(work, standin)
        qa_opening = None
        for path in suites():
            text = opening(path)
            name, in_qa = os.path.basename(path), os.path.basename(os.path.dirname(path)) == "qa"
            if text is None:
                wrong.append("%s takes no guest step at its top" % name)
                continue
            kind = (in_qa, "\n".join(ast.unparse(s) for s in ast.parse(text).body
                                     if not (isinstance(s, ast.Expr)
                                             and isinstance(s.value, ast.Constant))))
            if kind in seen_kinds:
                continue
            seen_kinds[kind] = name
            openings.append((name, in_qa, text))
            qa_opening = text if in_qa else qa_opening
        if qa_opening is None:
            return False, wrong + ["no qa script's opening was found to run"]
        # The repository's layout, which CI runs the suites in.
        for name, _in_qa, stand in lay_repo(os.path.join(work, "repo"), openings, True):
            run, seen = start(stand, env)
            if not settled_alone(run, seen, standin):
                wrong.append("%s, as CI starts it, did not settle alone: exit %d, %s, %s" % (
                    name, run.returncode, seen, (run.stdout + run.stderr).strip()[-300:]))
        # Copied by hand: without guest.py it refuses, and without the app,
        # whose notebook it cannot ask after; with both beside, it settles.
        by_hand = os.path.join(work, "by_hand", "copy")
        os.makedirs(by_hand)
        shutil.copy2(os.path.join(ROOT, "qa", "_qa_support.py"), by_hand)
        stand = os.path.join(by_hand, "standin_qa.py")
        with open(stand, "w", encoding="utf-8") as fh:
            fh.write(qa_opening + REPORT)
        for missing, then in (("guest.py", lambda: shutil.copy2(os.path.join(HERE, "guest.py"),
                                                               by_hand)),
                              ("note_organizer.py", lambda: lay_app(by_hand))):
            run, seen = start(stand, env)
            wrote = os.path.exists(os.path.join(by_hand, "notes_data.json"))
            if run.returncode == 0 or missing not in run.stdout + run.stderr or wrote or seen:
                wrong.append("copied by hand without %s, it did not refuse: exit %d, "
                             "notes_data.json written %s" % (missing, run.returncode, wrote))
            then()
        run, seen = start(stand, env)
        if not settled_alone(run, seen, standin):
            wrong.append("copied by hand with guest.py and the app beside it, it did not "
                         "settle alone: exit %d, %s" % (run.returncode, seen))
        # In run_tests' scratch, started by a run that settled (this gate).
        scratch = run_tests.build_scratch()
        try:
            stand = os.path.join(scratch, "standin_qa.py")
            with open(stand, "w", encoding="utf-8") as fh:
                fh.write(qa_opening + REPORT)
            inside = dict(os.environ, NOTEORG_SCRATCH="1", TEMP=env["TEMP"], TMP=env["TMP"],
                          TMPDIR=env["TMPDIR"])
            inside[guest.DISK_ENV] = "0"
            inside.pop(guest.LOCK_DIR_ENV, None)
            run, seen = start(stand, inside)
        finally:
            guest.remove(scratch)
        if not (run.returncode == 0 and seen and seen["homes"] == os.environ.get(guest.HOMES_ENV)
                and seen["appdata"] == os.environ.get("APPDATA")
                and "the run that started this one's" in run.stdout):
            wrong.append("in run_tests' scratch, beside a run that settled, it did not share "
                         "its homes: exit %d, %s, %s" % (run.returncode, seen,
                                                         (run.stdout + run.stderr).strip()[-300:]))
        wrong += beside_a_named_notebook(work, env, openings)
    finally:
        guest.remove(work)
    return not wrong, wrong or [
        "%d opening(s) as CI starts them (%s), by hand, in run_tests' scratch; each refusing "
        "where a notebook_location.txt names a notebook, by its path and through "
        "%%USERPROFILE%%, and a qa opening where the app opens another folder"
        % (len(seen_kinds), ", ".join(seen_kinds.values()))]


def beside_a_named_notebook(work, env, openings):
    """The owner's checkout, stood in: its notebook_location.txt names a
    notebook outside it, by its path or through %USERPROFILE%, which a
    guest's homes leave as they are. Each opening, started as a person
    would there -- a unit suite from the root, CI's own recipe; a qa script
    from qa/ with the root on PYTHONPATH -- refuses, the notebook as it was.
    And the checkout as it was before the file, its notebook beside the
    app: a qa opening from qa/ refuses, for the app would open the root.
    The guards looked beside themselves while the app opened the folder the
    file names."""
    wrong = []
    profile = os.path.join(work, "profile")
    her = os.path.join(profile, "Note Organizer")
    before = her_notebook(her)
    var = "%USERPROFILE%\\" if os.name == "nt" else "$USERPROFILE/"
    for how, line, folder in (("by its path", her, "checkout_path"),
                              ("through %USERPROFILE%", var + "Note Organizer",
                               "checkout_profile")):
        checkout = os.path.join(work, folder)
        stands = lay_repo(checkout, openings, False)
        with open(os.path.join(checkout, "notebook_location.txt"), "w", encoding="utf-8") as fh:
            fh.write("# my own notebook, out of the repo\n%s\n" % line)
        named = dict(env, USERPROFILE=profile)
        for name, in_qa, stand in stands:
            if in_qa:
                run, seen = start(stand, dict(named, PYTHONPATH=checkout), os.path.dirname(stand))
            else:
                run, seen = start(stand, named, checkout)
            if not refused_untouched(run, seen, her, before,
                                     (checkout, os.path.join(checkout, "qa"))):
                wrong.append("%s, in a checkout whose notebook_location.txt names a notebook "
                             "%s, did not refuse with the notebook as it was: exit %d, %s" % (
                                 name, how, run.returncode,
                                 (run.stdout + run.stderr).strip()[-300:]))
    beside = os.path.join(work, "checkout_beside")
    stands = lay_repo(beside, [o for o in openings if o[1]], False)
    held = her_notebook(beside)
    for name, _in_qa, stand in stands:
        run, seen = start(stand, dict(env, PYTHONPATH=beside), os.path.dirname(stand))
        if not refused_untouched(run, seen, beside, held, (os.path.dirname(stand),)):
            wrong.append("%s, started from qa/ with the app at the root beside its notebook, "
                         "did not refuse with the notebook as it was: exit %d, %s" % (
                             name, run.returncode, (run.stdout + run.stderr).strip()[-300:]))
    return wrong


def main():
    for stream in (sys.stdout, sys.stderr):
        try:   # a curly quote in a finding must not end the gate on a cp1252 console
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    for line in guest.settle(heavy=False):
        print(line)
    missing = runners_without_settle()
    print("%s every runner sets the ceiling first, and bounds its children%s"
          % ("PASS" if not missing else "FAIL", "" if not missing else ":"))
    for line in missing:
        print("       " + line)
    doorless = scripts_without_a_door()
    print("%s runners in other languages go through a door%s"
          % ("PASS" if not doorless else "FAIL", "" if not doorless else ":"))
    for line in doorless:
        print("       " + line)
    cases, wrong = walk_sees_its_cases()
    print("%s the walk sees each of its %d cases as it should%s"
          % ("PASS" if cases else "FAIL", len(CASES), "" if cases else ":"))
    for line in wrong:
        print("       " + line)
    doors = docker_runs_outside_the_door()
    print("%s the Linux image is run only through %s%s"
          % ("PASS" if not doors else "FAIL", DOOR, "" if not doors else ": " + ", ".join(doors)))
    unseen = [s for s in DOCKER_SHAPES if not DOCKER_STARTS.search(s)]
    taken = [s for s in DOCKER_PROSE if DOCKER_STARTS.search(s)]
    print("%s the door's pattern sees each of its %d shapes and takes none of its %d prose lines%s"
          % ("PASS" if not (unseen or taken) else "FAIL", len(DOCKER_SHAPES), len(DOCKER_PROSE),
             "" if not (unseen or taken) else ": missed %r, taken %r" % (unseen, taken)))
    shown, where = door_shows_only_tracked()
    print("%s the Linux image sees only what git tracks (%s)"
          % ("PASS" if shown else "FAIL", where))
    ok, out = ceiling_holds()
    print("%s a process past the ceiling fails alone (%s)" % ("PASS" if ok else "FAIL", out))
    turn, seen = turn_holds()
    print("%s one heavy job at a time: %s" % ("PASS" if turn else "FAIL", seen))
    homes, where = homes_hold()
    print("%s a run's homes are its own, its app's first start bringing nothing in (%s)"
          % ("PASS" if homes else "FAIL", where))
    ended, how = leftovers_end()
    print("%s what a run started ends with it, its parent gone or not (%s)"
          % ({True: "PASS", False: "FAIL", None: "SKIP"}[ended], how))
    floor, said = floor_holds()
    print("%s a run keeps a floor under the disk (%s)"
          % ({True: "PASS", False: "FAIL", None: "SKIP"}[floor], said))
    alone, how = suites_settle_themselves()
    print("%s a suite started outside a runner settles itself%s"
          % ("PASS" if alone else "FAIL", " (%s)" % how[0] if alone else ":"))
    for line in ([] if alone else how):
        print("       " + line)
    return 1 if (missing or doorless or not cases or doors or unseen or taken or not shown or not ok
                 or not turn or not homes or ended is False or floor is False or not alone) else 0


if __name__ == "__main__":
    sys.exit(main())
