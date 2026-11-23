"""The test plan's numbers, wherever they are written, are the plan's own.

The plan is a workbook, qa/NoteOrganizer_TestPlan.xlsx, whose Summary
counts itself with formulas -- which only a spreadsheet program works out,
and which nobody sees in a document. Its counts were copied into three
documents by hand, and drifted: the excerpt's tables gave 859 cases while
its heading said 921. This gate counts the rows itself and fails when:

* a case has no ID, or one another case has;
* a case's status or priority is one the Summary does not count, or its
  area is missing from the Summary's list by area, so the case is counted
  nowhere (43 were, until 7 November 2026);
* a Summary formula stops short of the last case;
* a document gives the plan a number the plan does not have:
  docs/TEST_PLAN_EXCERPT.md (the cases, those passed and those not yet
  walked, each priority, the six largest areas), docs/BUG_REPORTS.md and
  qa/README.md (the cases).

Every sentence it reads must be found: a gate that cannot find what it
checks fails, rather than passing over it.

    py tools/check_test_plan.py
"""

import collections
import os
import re
import sys

import openpyxl

import guest  # the ceiling and empty homes (tools/guest.py)

guest.settle(heavy=False)
sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "qa", "NoteOrganizer_TestPlan.xlsx")
CASES, SUMMARY = "Test Cases", "Summary"
# A range of the cases' sheet in a Summary formula, and what it counts.
RANGE = re.compile(r"'Test Cases'!\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)")
COUNTED = re.compile(r"'Test Cases'!\$?([A-Z]+)\$?\d+:\$?[A-Z]+\$?\d+,\"([^\"*]+)\"")


def number(text):
    return int(text.replace(",", ""))


def read_plan(path):
    """(cases, problems): every case as {header: value}, and what is wrong
    with the workbook itself."""
    wb = openpyxl.load_workbook(path)
    problems = []
    sheet = wb[CASES]
    rows = list(sheet.iter_rows(values_only=True))
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    letters = {openpyxl.utils.get_column_letter(i + 1): name for i, name in enumerate(header)}
    cases, last = [], 1
    for n, row in enumerate(rows[1:], start=2):
        if all(v is None or str(v).strip() == "" for v in row):
            continue
        last = n
        cases.append({name: ("" if v is None else str(v).strip()) for name, v in zip(header, row)})

    seen = collections.Counter(c["ID"] for c in cases)
    for c in cases:
        if not c["ID"]:
            problems.append("a case with no ID: %r" % c["Title"][:60])
    for ident, times in seen.items():
        if ident and times > 1:
            problems.append("case ID %s is used %d times" % (ident, times))

    counted = collections.defaultdict(set)
    for row in wb[SUMMARY].iter_rows():
        for cell in row:
            formula = cell.value if isinstance(cell.value, str) and cell.value.startswith("=") else ""
            for _col, _top, _end_col, end in RANGE.findall(formula):
                if int(end) < last:
                    problems.append("%s!%s counts the cases to row %s; the last case is on row %d"
                                    % (SUMMARY, cell.coordinate, end, last))
            for col, value in COUNTED.findall(formula):
                counted[letters.get(col, col)].add(value)
    for column in ("Status", "Priority", "Area"):
        if not counted[column]:
            problems.append("the Summary counts no %s at all" % column.lower())
            continue
        stray = collections.Counter(c[column] for c in cases if c[column] not in counted[column])
        for value, times in sorted(stray.items()):
            problems.append("%d case(s) with %s %r, which the Summary does not count"
                            % (times, column.lower(), value))
    return cases, problems


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def check_documents(cases):
    """What each document says of the plan, against the plan."""
    problems = []
    total = len(cases)
    status = collections.Counter(c["Status"] for c in cases)
    priority = collections.Counter(c["Priority"] for c in cases)
    area = collections.Counter(c["Area"] for c in cases)

    def said(rel, pattern, what):
        m = re.search(pattern, read(rel), re.S)
        if not m:
            problems.append("%s: the sentence giving %s is not found (the gate reads %r)"
                            % (rel, what, pattern))
        return m

    def agree(rel, what, written, actual):
        if written != actual:
            problems.append("%s says %s is %s; the plan has %s" % (rel, what, written, actual))

    excerpt = "docs/TEST_PLAN_EXCERPT.md"
    m = said(excerpt, r"\*\*([\d,]+) cases\*\* on", "the cases")
    if m:
        agree(excerpt, "the number of cases (heading)", number(m.group(1)), total)
    m = said(excerpt, r"Counted on [^:]+: ([\d,]+) cases, ([\d,]+) walked and passed, ([\d,]+) not yet\s+walked",
             "the cases passed and not yet walked")
    if m:
        agree(excerpt, "the number of cases", number(m.group(1)), total)
        agree(excerpt, "the cases passed", number(m.group(2)), status["Pass"])
        agree(excerpt, "the cases not yet walked", number(m.group(3)), status["Not Tested"])
    m = said(excerpt, r"### By priority\s*\n(.*?)\n\n", "the cases by priority")
    if m:
        rows = dict(re.findall(r"^\| ([^|]+?) \| ([\d,]+) \|$", m.group(1), re.M))
        agree(excerpt, "the priorities listed", sorted(rows), sorted(priority))
        for name, written in rows.items():
            agree(excerpt, "the %s cases" % name, number(written), priority[name])
    m = said(excerpt, r"### The six largest areas\s*\n(.*?)\n\n", "the six largest areas")
    if m:
        rows = [(name, number(n)) for name, n in re.findall(r"^\| ([^|]+?) \| ([\d,]+) \|$", m.group(1), re.M)
                if name != "Area"]
        for name, written in rows:
            agree(excerpt, "the %s cases" % name, written, area[name])
        listed = {name for name, _n in rows}
        smallest_listed = min((area[name] for name in listed), default=0)
        larger = sorted(name for name, n in area.items() if name not in listed and n > smallest_listed)
        if len(rows) != 6 or larger:
            problems.append("%s: the six largest areas are not the six listed (%d listed; larger, unlisted: %s)"
                            % (excerpt, len(rows), ", ".join(larger) or "none"))
    m = said("docs/BUG_REPORTS.md", r"of \*\*([\d,]+) test cases\*\*", "the cases")
    if m:
        agree("docs/BUG_REPORTS.md", "the number of cases", number(m.group(1)), total)
    m = said("qa/README.md", r"`NoteOrganizer_TestPlan\.xlsx`, ([\d,]+) cases on", "the cases")
    if m:
        agree("qa/README.md", "the number of cases", number(m.group(1)), total)
    return problems


def main():
    cases, problems = read_plan(PLAN)
    problems += check_documents(cases)
    if problems:
        print("The test plan and what is said of it disagree:")
        for p in problems:
            print("  - " + p)
        return 1
    status = collections.Counter(c["Status"] for c in cases)
    print("The test plan counts itself and is counted right: %d cases, %d passed, %d not yet walked, "
          "in %d areas; three documents agree." % (len(cases), status["Pass"], status["Not Tested"],
                                                  len({c["Area"] for c in cases})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
