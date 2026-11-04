"""Comments say why, in a few lines; the story lives in the issues log.

WHAT IT CHECKS
--------------
Everywhere in the app's code -- the entry file and the noteorganizer
package -- two things:

* no comment or docstring names a release. The changelog says when; the
  code says why, and "fixed in 0.76.195" is history the day after;
* every pointer into the issues log leads somewhere: ``ISSUES_LOG: "..."``
  names the start of a story's title, and ``smaller lessons: ...`` names
  an entry in its "Smaller lessons, moved out of the code" section.

In the modules listed in BRIEF, three limits as well:

* a run of comment lines is at most three lines long;
* a function's or class's docstring spends at most six lines on prose;
* the module's own docstring, its overview, is at most ten lines.

Three lines hold a reason. What happened, and how it was found, is a
story: it goes to docs/ISSUES_LOG.md, and the code keeps a pointer to it.
A docstring's Args:/Returns: sections document an interface rather than
tell a story, so they are not counted. A module's overview names what the
module is for and why it is shaped so; the walk through it lives in
docs/CODE_TOUR.md.

WHY A LIST
----------
A module joins BRIEF once it has been condensed, and stays condensed from
then on. Much of the code still tells its stories at length; the list says
how far the convention has reached instead of pretending it is everywhere.

Run: py tools/check_comments.py
"""

import ast
import io
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISSUES_LOG = os.path.join(ROOT, "docs", "ISSUES_LOG.md")

# Modules whose comments have been condensed (paths from the repo root).
BRIEF = [
    "noteorganizer/__init__.py",
    "noteorganizer/core/__init__.py",
    "noteorganizer/core/calculator.py",
    "noteorganizer/core/categories.py",
    "noteorganizer/core/clipboard.py",
    "noteorganizer/core/diagnostics.py",
    "noteorganizer/core/model.py",
    "noteorganizer/core/paths.py",
    "noteorganizer/core/sharing.py",
    "noteorganizer/core/single_instance.py",
    "noteorganizer/core/spelling.py",
    "noteorganizer/core/storage.py",
    "noteorganizer/core/tables.py",
    "noteorganizer/core/themes.py",
    "noteorganizer/core/welcome.py",
    "noteorganizer/core/winspell.py",
    "noteorganizer/ui/__init__.py",
    "noteorganizer/ui/calculator_panel.py",
    "noteorganizer/ui/note_list.py",
    "noteorganizer/ui/spelling.py",
]

MAX_COMMENT_LINES = 3
MAX_DOCSTRING_LINES = 6
MAX_MODULE_DOCSTRING_LINES = 10

# A release as this project numbers them before 1.0.0. Dates such as
# 17.10.2026 and toolkit versions such as Tk 8.6.15 do not match.
RELEASE = re.compile(r"\b0\.\d{1,3}\.\d{1,4}\b")

# Where a docstring's prose ends and its interface sections begin.
SECTION = re.compile(r"^(Args|Arguments|Returns|Raises|Yields):\s*$")

# The two ways the code points into the issues log.
STORY = re.compile(r'ISSUES_LOG: "([^"]+)"')
LESSON = re.compile(r"smaller lessons: ([^.;)]+)")
LESSONS_HEADING = "## Smaller lessons, moved out of the code"


def app_files():
    files = ["note_organizer.py"]
    package = os.path.join(ROOT, "noteorganizer")
    for folder, _dirs, names in os.walk(package):
        for name in sorted(names):
            if name.endswith(".py"):
                path = os.path.join(folder, name)
                files.append(os.path.relpath(path, ROOT).replace(os.sep, "/"))
    return sorted(files)


def issues_log():
    """(story titles, smaller-lesson names) as docs/ISSUES_LOG.md holds
    them; the names lowercased, without their backticks."""
    with io.open(ISSUES_LOG, encoding="utf-8") as fh:
        text = fh.read()
    titles = [line[4:].strip() for line in text.splitlines()
              if line.startswith("### ")]
    lessons = []
    parts = text.split(LESSONS_HEADING, 1)
    if len(parts) == 2:
        for line in parts[1].splitlines():
            if line.startswith("## "):
                break
            found = re.match(r"- \*\*(.+?)\*\*", line)
            if found:
                lessons.append(found.group(1).replace("`", "").lower())
    return titles, lessons


def comment_lines(source):
    """(line number, text, stands alone) for every comment in *source*."""
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            alone = tok.line.strip().startswith("#")
            out.append((tok.start[0], tok.string, alone))
    return out


def docstrings(tree):
    """(line number, docstring, is the module's) for every docstring."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=True)
            if doc:
                line = node.body[0].lineno
                out.append((line, doc, isinstance(node, ast.Module)))
    return out


def prose_lines(doc):
    """How many lines *doc* spends before its first Args:/Returns: section."""
    lines = doc.split("\n")
    for index, line in enumerate(lines):
        if SECTION.match(line.strip()):
            lines = lines[:index]
            break
    while lines and not lines[-1].strip():
        lines.pop()
    return len(lines)


def comment_runs(comments):
    """(first line, length, text) of each run of consecutive lines that
    hold nothing but a comment; a comment after code is a run of its own."""
    runs = []
    for line, text, alone in comments:
        words = text.lstrip("#").strip()
        if alone and runs and runs[-1][3] and runs[-1][0] + runs[-1][1] == line:
            runs[-1][1] += 1
            runs[-1][2] += " " + words
        else:
            runs.append([line, 1, words, alone])
    return [(first, length, text, alone) for first, length, text, alone in runs]


def broken_pointers(text, titles, lessons):
    """What *text* points to in the issues log that is not there."""
    flat = " ".join(text.split())
    broken = []
    for found in STORY.finditer(flat):
        wanted = found.group(1)
        if not any(title.startswith(wanted) for title in titles):
            broken.append('no story titled "%s"' % wanted)
    for found in LESSON.finditer(flat):
        wanted = found.group(1).replace("`", "").strip().lower()
        if not any(wanted.startswith(name) for name in lessons):
            broken.append('no smaller lesson named "%s"' % wanted)
    return broken


def check(path, titles, lessons):
    with io.open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        source = fh.read()
    problems = []
    comments = comment_lines(source)
    tree = ast.parse(source)
    for line, text, _alone in comments:
        found = RELEASE.search(text)
        if found:
            problems.append((line, "names release %s" % found.group(0)))
    for line, doc, _module in docstrings(tree):
        found = RELEASE.search(doc)
        if found:
            problems.append((line, "docstring names release %s"
                             % found.group(0)))
    runs = comment_runs(comments)
    for first, _length, text, _alone in runs:
        for what in broken_pointers(text, titles, lessons):
            problems.append((first, "points to %s in ISSUES_LOG" % what))
    for line, doc, _module in docstrings(tree):
        for what in broken_pointers(doc, titles, lessons):
            problems.append((line, "docstring points to %s in ISSUES_LOG"
                             % what))
    if path in BRIEF:
        for first, length, _text, alone in runs:
            if alone and length > MAX_COMMENT_LINES:
                problems.append((first, "%d comment lines in a row (at most %d)"
                                 % (length, MAX_COMMENT_LINES)))
        for line, doc, module in docstrings(tree):
            length = prose_lines(doc)
            if module and length > MAX_MODULE_DOCSTRING_LINES:
                problems.append((line, "module docstring of %d lines (at most "
                                 "%d)" % (length, MAX_MODULE_DOCSTRING_LINES)))
            if not module and length > MAX_DOCSTRING_LINES:
                problems.append((line, "docstring prose of %d lines (at most "
                                 "%d)" % (length, MAX_DOCSTRING_LINES)))
    return sorted(problems)


def main():
    files = app_files()
    missing = [path for path in BRIEF if path not in files]
    if missing:
        for path in missing:
            print("BRIEF names a module that does not exist: %s" % path)
        return 1
    titles, lessons = issues_log()
    if not lessons:
        print("docs/ISSUES_LOG.md has no %r section, or it holds no entry."
              % LESSONS_HEADING)
        return 1
    failures = 0
    for path in files:
        for line, what in check(path, titles, lessons):
            print("%s:%d: %s" % (path, line, what))
            failures += 1
    if failures:
        print("\n%d problem(s). A comment says why in at most %d lines; the "
              "story goes to docs/ISSUES_LOG.md, with a pointer left here."
              % (failures, MAX_COMMENT_LINES))
        return 1
    print("Comments brief: %d module(s) read, no release named, every pointer "
          "into ISSUES_LOG leads somewhere, %d condensed module(s) within "
          "their limits." % (len(files), len(BRIEF)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
