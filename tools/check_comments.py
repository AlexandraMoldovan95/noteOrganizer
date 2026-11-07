"""Comments say why, in a few lines; the story lives in the issues log.

WHAT IT CHECKS
--------------
Everywhere in the app's code -- the entry file and the noteorganizer
package -- two things:

* no comment or docstring names a release. The changelog says when; the
  code says why, and "fixed in 0.76.195" is history the day after;
* nor a round of an audit ("round 9", "the lows wave"): it says when a
  reason was found, never the reason, and a reader outside the audit
  cannot use it. A story's title quoted as a pointer is not counted;
* every pointer into the issues log leads somewhere: ``ISSUES_LOG: "..."``
  names the start of a story's title, and ``smaller lessons: ...`` names
  an entry in its "Smaller lessons, moved out of the code" section.

The tests' and tools' Python, and the reasons in tools/mutants.json, are
held to the round rule as well: they are read outside the audit too.

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
A module joined BRIEF once it had been condensed, and stays condensed from
then on. Since the entry file joined (2026-11-05) the list holds every
module; a new one joins it when it is written.

Run: py tools/check_comments.py
"""

import ast
import glob
import io
import json
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISSUES_LOG = os.path.join(ROOT, "docs", "ISSUES_LOG.md")

# Modules whose comments have been condensed (paths from the repo root).
BRIEF = [
    "note_organizer.py",
    "noteorganizer/__init__.py",
    "noteorganizer/core/__init__.py",
    "noteorganizer/core/calculator.py",
    "noteorganizer/core/categories.py",
    "noteorganizer/core/clipboard.py",
    "noteorganizer/core/diagnostics.py",
    "noteorganizer/core/duplicates.py",
    "noteorganizer/core/formatting.py",
    "noteorganizer/core/model.py",
    "noteorganizer/core/paths.py",
    "noteorganizer/core/recurrence.py",
    "noteorganizer/core/richtext.py",
    "noteorganizer/core/sharing.py",
    "noteorganizer/core/single_instance.py",
    "noteorganizer/core/spelling.py",
    "noteorganizer/core/storage.py",
    "noteorganizer/core/tables.py",
    "noteorganizer/core/themes.py",
    "noteorganizer/core/welcome.py",
    "noteorganizer/core/winspell.py",
    "noteorganizer/ui/__init__.py",
    "noteorganizer/ui/attachments.py",
    "noteorganizer/ui/calculator_panel.py",
    "noteorganizer/ui/calendar_view.py",
    "noteorganizer/ui/dialogs.py",
    "noteorganizer/ui/note_list.py",
    "noteorganizer/ui/settings_page.py",
    "noteorganizer/ui/spelling.py",
]

MAX_COMMENT_LINES = 3
MAX_DOCSTRING_LINES = 6
MAX_MODULE_DOCSTRING_LINES = 10

# A release as this project numbers them before 1.0.0. Dates such as
# 17.10.2026 and toolkit versions such as Tk 8.6.15 do not match.
RELEASE = re.compile(r"\b0\.\d{1,3}\.\d{1,4}\b")

# A round of an audit, as the comments once named them: in figures, in
# words ("round eleven", "the twelfth round"), or as the audit itself. Only
# figures were refused at first, and 9 labels in words stayed.
_NUM = (r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
        r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
        r"nineteen|twenty(?:-[a-z]+)?)")
_ORD = (r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|"
        r"tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|"
        r"seventeenth|eighteenth|nineteenth|twentieth|twenty-[a-z]+)")
ROUND = re.compile(
    r"\brounds? %s\b|\b(?:%s|%s)(?: and (?:%s|%s))? rounds?\b(?! trip)|\blows wave\b"
    r"|\bfinal audit\b|\baudit's\b|\bwave %s\b"
    % (_NUM, _ORD, _NUM, _ORD, _NUM, _NUM), re.I)

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


def named_round(text):
    """The audit's round *text* names, its lines joined and its pointers
    into the issues log left out; None when it names none."""
    found = ROUND.search(STORY.sub("", " ".join(text.split())))
    return found.group(0) if found else None


def test_and_tool_files():
    """The tests' and tools' Python, held to the round rule alone. This file
    is left out: it quotes the labels it refuses."""
    files = []
    for pattern in ("test_*.py", "qa/*.py", "tools/*.py", "site/*.py", "site/tools/*.py"):
        files += [os.path.relpath(path, ROOT).replace(os.sep, "/")
                  for path in glob.glob(os.path.join(ROOT, pattern))]
    return sorted(set(files) - {"tools/check_comments.py"})


def rounds_named(path):
    """(line, problem) for each comment run or docstring in *path* that
    names a round of the audit."""
    with io.open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        source = fh.read()
    problems = []
    for first, _length, text, _alone in comment_runs(comment_lines(source)):
        found = named_round(text)
        if found:
            problems.append((first, "names the audit's %r" % found))
    for line, doc, _module in docstrings(ast.parse(source)):
        found = named_round(doc)
        if found:
            problems.append((line, "docstring names the audit's %r" % found))
    return sorted(problems)


def catalogue_rounds():
    """(mutant id, label) for each mutant whose reason names a round:
    tools/mutants.json is read by whoever runs a mutant, as a comment is."""
    with io.open(os.path.join(ROOT, "tools", "mutants.json"), encoding="utf-8") as fh:
        catalogue = json.load(fh)
    return [(m.get("id", "?"), found) for m in catalogue
            for found in [named_round(m.get("about", "") + " " + m.get("note", ""))]
            if found]


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
        found = named_round(text)
        if found:
            problems.append((first, "names the audit's %r" % found))
    for line, doc, _module in docstrings(tree):
        for what in broken_pointers(doc, titles, lessons):
            problems.append((line, "docstring points to %s in ISSUES_LOG"
                             % what))
        found = named_round(doc)
        if found:
            problems.append((line, "docstring names the audit's %r" % found))
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
    others = test_and_tool_files()
    for path in others:
        for line, what in rounds_named(path):
            print("%s:%d: %s" % (path, line, what))
            failures += 1
    for mid, found in catalogue_rounds():
        print("tools/mutants.json: %s's reason names the audit's %r" % (mid, found))
        failures += 1
    if failures:
        print("\n%d problem(s). A comment says why in at most %d lines; the "
              "story goes to docs/ISSUES_LOG.md, with a pointer left here."
              % (failures, MAX_COMMENT_LINES))
        return 1
    print("Comments brief: %d module(s) read, no release or audit round named, every pointer "
          "into ISSUES_LOG leads somewhere, %d condensed module(s) within "
          "their limits; %d test and tool file(s) and the mutants' reasons name "
          "no round." % (len(files), len(BRIEF), len(others)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
