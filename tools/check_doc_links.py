"""Do the documentation's own links actually go anywhere?

WHY THIS EXISTS
---------------
The docs cross-reference each other constantly -- "one canonical home per
topic, every other mention is a line plus a link" is a standing rule, so
the links ARE the structure. Nothing ever checked them. A heading gets
reworded during an editorial pass, every link pointing at its anchor goes
dead, and nothing says so: a dead in-page anchor scrolls nowhere, which
reads as "the link is broken on my machine" rather than as a bug.

WHAT IT CHECKS
--------------
Every Markdown link in every tracked .md file, for the three ways they go
wrong in this repo:

* ``#anchor``            -- an anchor in the same file
* ``OTHER.md#anchor``    -- a heading in another file
* ``OTHER.md``           -- the file itself

External links (http, mailto) are left alone: this is a repo checker, not
a link crawler, and a network check would make it flaky.

ANCHORS
-------
GitHub's slug rules, which are not obvious: lowercase, drop everything
that is not a letter, digit, space or hyphen (an underscore inside a code
span is kept; outside, it is emphasis and goes), spaces to hyphens. So
``## "Recently updated" sort`` becomes ``recently-updated-sort``, and a
heading holding a version like ``0.71.155 — 2026-09-11`` becomes
``071155--2026-09-11`` (the em dash vanishes, the spaces around it each
become a hyphen). Duplicate headings get ``-1``, ``-2`` suffixes, same as
GitHub.

Usage:  py tools/check_doc_links.py            (whole repo)
        py tools/check_doc_links.py docs/ROADMAP.md
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# [text](target) -- the target stops at whitespace or the closing paren, and
# nested parens inside a target are not something this repo's links use.
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$", re.M)


def slug(text):
    """GitHub's heading -> anchor rule."""
    # Link syntax inside a heading contributes only its text.
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # An underscore in code is a character, kept; outside, it is emphasis.
    text = re.sub(r"`([^`]*)`", lambda m: m.group(1).replace("_", "\0"), text)
    text = re.sub(r"[`*_~]", "", text).replace("\0", "_")
    out = []
    for ch in text.lower():
        if ch.isalnum() or ch in " -_":
            out.append(ch)
    return "".join(out).strip().replace(" ", "-")


def anchors_of(path):
    """Every anchor a reader can jump to in this file."""
    text = read(path)
    # Headings inside fenced code blocks are not headings.
    lines = []
    for i, part in enumerate(text.split("```")):
        if i % 2 == 0:
            lines.append(part)
    text = "\n".join(lines)
    seen, found = {}, set()
    for _, title in HEADING.findall(text):
        base = slug(title)
        if not base:
            continue
        n = seen.get(base, 0)
        seen[base] = n + 1
        found.add(base if n == 0 else "%s-%d" % (base, n))
    # Explicit HTML anchors, if any doc ever adds one.
    for name in re.findall(r'<a\s+(?:id|name)="([^"]+)"', text):
        found.add(name)
    return found


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def md_files(targets):
    """The files named, or every .md file git tracks. Walking the disk read
    a leftover agent worktree's copies too (44 files for 22 tracked); with
    nothing tracked to read, the gate refuses rather than passing."""
    if targets:
        return [os.path.abspath(t) for t in targets]
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=120)
    names = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    if out.returncode != 0 or not names:
        print("Cannot list the tracked .md files (is %s a git checkout?)." % ROOT)
        sys.exit(2)
    return sorted(os.path.join(ROOT, name) for name in names)


def main(argv):
    import guest  # the memory ceiling, before git starts (tools/guest.py)
    guest.settle(heavy=False)
    files = md_files(argv[1:])
    cache = {}
    problems = []
    checked = 0
    for path in files:
        text = read(path)
        here = os.path.dirname(path)
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#!")):
                continue
            checked += 1
            file_part, _, anchor = target.partition("#")
            if file_part:
                dest = os.path.normpath(os.path.join(here, file_part))
                if not os.path.exists(dest):
                    problems.append((path, target, "no such file"))
                    continue
                if not anchor:
                    continue
                if not dest.lower().endswith(".md"):
                    continue
            else:
                dest = path
            if dest not in cache:
                cache[dest] = anchors_of(dest)
            if anchor and anchor not in cache[dest]:
                problems.append((path, target, "no such heading"))

    def shown(path):
        # relpath raises across Windows drives, which is exactly the case
        # when this is pointed at a scratch copy to prove it still bites.
        try:
            return os.path.relpath(path, ROOT)
        except ValueError:
            return path

    for path, target, why in problems:
        print("%s  ->  %s   (%s)" % (shown(path), target, why))
    print()
    print("%d link(s) checked in %d file(s); %d broken"
          % (checked, len(files), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
