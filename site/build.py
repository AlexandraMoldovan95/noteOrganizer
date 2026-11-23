"""Build the Note Organizer site into public/.

    py site/build.py                 # the repository site/ sits in
    py site/build.py --repo D:/path/to/NoteOrganizer

What it does, in order:

1. Reads from the app's repository -- documentation, screenshots, the icon,
   and a few literal values from the source (themes, emoji, version) -- and
   never writes there. Values are read with ``ast.literal_eval`` on the
   source text, so none of the app's code runs.
2. Builds the site in public.building/: the pages in src/, the demo, the
   documentation pages converted from Markdown, and the screenshots,
   resized to WebP.
3. Checks what it built: every internal link and anchor resolves, no
   {{token}} is left unfilled, and nothing private (a home folder, a
   private account or folder name: FORBIDDEN, PRIVATE_WORDS) reached a page.
4. Only then puts it in public/'s place. Any failure stops the build with
   a non-zero exit and leaves the last good site in public/ untouched.

public/ is what Netlify publishes. Edit src/ and run this again; never
edit public/ by hand, because the next build replaces it.
"""

import argparse
import ast
import hashlib
import html
import json
import os
import re
import shutil
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
PUBLIC = os.path.join(HERE, "public")
# Everything is built here first and checked; only a site that passed
# every check takes public/'s place. A build that fails -- a broken link,
# or Windows refusing because an Explorer window has public/ open --
# leaves the last good site in public/ untouched.
STAGE = os.path.join(HERE, "public.building")
OUT = STAGE
CONFIG = os.path.join(HERE, "site.json")

# The repository's documents that become pages of their own, and their
# names here. Links to any of them are rewritten to the page; links to
# anything else in the repository become plain text until the repository
# is public (then "repo_url" in site.json turns them into GitHub links).
PAGES = {
    "docs/IN_MY_WORDS.md": ("in-my-words.html", "In my words",
                            "How I see the work, in my own words."),
    "docs/AI_WORKFLOW.md": ("how-its-built.html", "How it's built",
                            "How Note Organizer is built with an AI agent, "
                            "and how the agent's work is checked."),
    "docs/TEST_PLAN_EXCERPT.md": ("testing.html", "How it's tested",
                                  "The standard test case template, filled out "
                                  "four times with simple, easy-to-picture cases."),
    # Linked from In my words, not from the menu or the home page's cards.
    "docs/BUG_REPORTS.md": ("bug-reports.html", "Bug reports",
                            "The twenty bugs my manual testing found, three "
                            "written out in a standard bug-report format."),
}
# docs/PRIVACY.md is not one of them: the privacy policy belongs to the apps
# and is published on Google Sites. This site presents the project to the
# people sent here, and nothing the apps' users see points at it
# (check_kept_apart).

# Text that must never reach a published page. A build that finds one
# stops; the page is not published with it.
FORBIDDEN = [r"[A-Za-z]:\\Users\\"]
# ...and private words -- an account, a home folder's name, a folder of
# notes -- kept as the SHA-256 of each, lowercased, by its length: listed
# as words, the guard published what it guarded. Any run of letters and
# digits in a page that holds one stops the build too.
PRIVATE_WORDS = {
    5: {"0d7d48a65e977aff4d6360550c5bd34225aa217a68b495a898708a3dd561e2a2"},
    6: {"ef034696c770ea75c312c7be5d421e4cb9872dfab54fd21ed388525d6e9d9389"},
    11: {"a8885707c07fe4e003bb49e0f1519239d48ca8454fd82e70d4d07ca1e997aa0e"},
    23: {"808a8aa57b09e9f4d849741fe212622e62e20c99f22cd7f3c1e534275cf2f769"},
}


def private_text(text):
    """What private text *text* holds: each FORBIDDEN pattern it matches,
    and how many PRIVATE_WORDS -- never the words themselves."""
    found = ["text matching %r" % p for p in FORBIDDEN if re.search(p, text, re.IGNORECASE)]
    words = 0
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        for length, digests in PRIVATE_WORDS.items():
            for at in range(len(token) - length + 1):
                piece = token[at:at + length].encode("utf-8")
                words += hashlib.sha256(piece).hexdigest() in digests
    if words:
        found.append("%d private word(s)" % words)
    return found

# Pages are linked by file, never by folder ("demo/index.html", not
# "demo/"): a server opens a folder's index.html by itself, but a page
# opened from the computer gets a file listing instead.
NAV = [("index.html", "Overview"), ("android.html", "Android"),
       ("how-its-built.html", "How it's built"),
       ("in-my-words.html", "In my words"), ("testing.html", "How it's tested")]

# The Android app's repository, beside this one unless site.json or
# --android-repo says otherwise. The site presents both apps from one
# build (the owner's call, 2026-10-24) and reads the phone's repository
# the way it reads this one: its screenshots, its README's description,
# its version -- read, never written.
ANDROID_DEFAULT = os.path.join("..", "androidVersion")
# The Android README's sections the Android page shows, by their headings.
ANDROID_SECTIONS = ["What it does", "What it is not"]
# The Android page's pictures, each with its -dark partner: four upright,
# one row of them, then three on its side, each a row of its own (the
# owner's choice, 2026-10-24; four and then two upright looked unplaced).
# The calendar and Settings are shown on its side instead, the calendar
# with a note open beside it, Settings with Categories open. The note is
# shown being written in, its format bar on the keyboard, in place of the
# same note at rest (2026-11-21, the review panel's ask; the row stays four).
ANDROID_GALLERY = ["01-note-list", "12-writing", "03-a-table", "04-search",
                   "08-wide", "09-wide-calendar", "10-wide-settings"]


def fail(message):
    print("BUILD FAILED: " + message)
    sys.exit(1)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ---------------------------------------------------------------------
# Values from the app's source, without running it
# ---------------------------------------------------------------------

def literal_assignments(source, names, inside_class=None):
    """The literal values assigned to `names` at module level, or in the
    body of the class `inside_class`."""
    tree = ast.parse(source)
    bodies = [tree.body]
    if inside_class:
        bodies = [node.body for node in tree.body
                  if isinstance(node, ast.ClassDef) and node.name == inside_class]
    found = {}
    for body in bodies:
        for node in body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id in names:
                    found[target.id] = ast.literal_eval(node.value)
    missing = set(names) - set(found)
    if missing:
        fail("not found in the app's source: " + ", ".join(sorted(missing)))
    return found


def main_class_name(source):
    """The class that holds EMOJI_GROUPS -- the app's window class."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if (isinstance(item, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "EMOJI_GROUPS"
                                for t in item.targets)):
                    return node.name
    fail("no class in note_organizer.py defines EMOJI_GROUPS")


def app_facts(repo):
    themes_src = read(os.path.join(repo, "noteorganizer", "core", "themes.py"))
    themes = literal_assignments(themes_src, [
        "THEMES", "THEME_LABELS", "DARK_THEMES", "LIGHT_THEMES",
        "DEFAULT_CATEGORY_COLORS", "PALETTE_COLORS", "PRESET_NOTE_COLORS",
        "HIGHLIGHT_COLOR_PALETTE"])
    entry_src = read(os.path.join(repo, "note_organizer.py"))
    version = literal_assignments(entry_src, ["APP_VERSION"])["APP_VERSION"]
    ui = literal_assignments(entry_src, ["EMOJI_GROUPS", "DAY_MARKER_EMOJIS", "INDENT_STEP"],
                             inside_class=main_class_name(entry_src))
    # The formatting bar's fonts, sizes and how deep a line may be pushed:
    # the demo offers exactly what the app does, and keeps nothing else.
    ui.update(literal_assignments(
        read(os.path.join(repo, "noteorganizer", "core", "formatting.py")),
        ["FONT_FAMILIES", "FONT_SIZES", "MAX_INDENT"]))
    return version, themes, ui


def project_numbers(repo):
    """Figures quoted on the overview page, each from its own source."""
    numbers = {}
    try:
        import openpyxl
    except ImportError:
        fail("openpyxl is needed to count the test plan's cases")
    plan = os.path.join(repo, "qa", "NoteOrganizer_TestPlan.xlsx")
    workbook = openpyxl.load_workbook(plan, read_only=True)
    sheet = workbook["Test Cases"]
    rows = sheet.iter_rows(values_only=True)
    head = [str(h or "").strip() for h in next(rows)]
    status, tested_by = head.index("Status"), head.index("Tested By")
    cases = [row for row in rows if row and row[0] not in (None, "")]
    numbers["test_cases"] = len(cases)
    # Passed by a person, not by the scripts' run ("Claude (automated, ...)").
    numbers["hand_passed"] = sum(
        1 for row in cases
        if row[status] == "Pass" and not str(row[tested_by] or "").startswith("Claude"))
    workbook.close()

    with open(os.path.join(repo, "tools", "mutants.json"), encoding="utf-8") as f:
        mutants = json.load(f)
    # The two entries marked self_test test the runner itself.
    numbers["mutants"] = sum(1 for m in mutants if not m.get("self_test"))

    workflow = read(os.path.join(repo, "docs", "AI_WORKFLOW.md"))
    match = re.search(r"About ([0-9][0-9,]*) checks", workflow)
    if not match:
        fail("AI_WORKFLOW.md no longer says 'About N checks'; update build.py")
    numbers["checks"] = match.group(1)

    numbers["unit_suites"] = len([n for n in os.listdir(repo)
                                  if re.fullmatch(r"test_\w+\.py", n)])
    numbers["qa_suites"] = len([n for n in os.listdir(os.path.join(repo, "qa"))
                                if re.fullmatch(r"qa\d+\.py", n)])
    return numbers


# ---------------------------------------------------------------------
# Markdown, the subset these documents use
# ---------------------------------------------------------------------

def strip_inline(text):
    """Heading text as GitHub reads it for the anchor: no markup."""
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return text.replace("`", "").replace("**", "").replace("__", "")


def github_slug(text, seen):
    slug = strip_inline(text).strip().lower()
    slug = re.sub(r"[^\w\- ]", "", slug)
    slug = slug.replace(" ", "-")
    base, n = slug, 0
    while slug in seen:
        n += 1
        slug = "%s-%d" % (base, n)
    seen.add(slug)
    return slug


class Renderer:
    """Markdown to HTML for one document. `link` maps an href to a new
    href, or None when the target is not published here; `sizes` gives each
    built picture's width and height, by its name under img/."""

    def __init__(self, link, sizes=None):
        self.link = link
        self.sizes = sizes or {}
        self.slugs = set()

    def picture(self, src, alt):
        """A picture of the project's, at its size -- so the text does not
        jump when it loads -- and a click away from its full size. A
        picture with a NAME-light partner (NAME itself being the dark one,
        as main-window and main-window-light are) is shown in the theme the
        page is in, as every picture on the site is (the owner, 2026-10-24)."""
        name = os.path.splitext(os.path.basename(src))[0]

        def img(source, key, css=""):
            size = ' width="%d" height="%d"' % self.sizes[key] if key in self.sizes else ""
            return '<img%s src="%s" alt="%s"%s loading="lazy">' % (css, html.escape(source), alt, size)
        shown = img(src, name)
        if name + "-light" in self.sizes:
            light = "%s/%s-light.webp" % (os.path.dirname(src), name)
            shown = img(src, name, ' class="for-dark"') + img(light, name + "-light", ' class="for-light"')
        return '<a class="zoom" href="%s">%s</a>' % (html.escape(src), shown)

    # -- inline --------------------------------------------------------
    def inline(self, text):
        codes = []

        def keep_code(m):
            codes.append("<code>" + html.escape(m.group(1), quote=False) + "</code>")
            return "\x00%d\x00" % (len(codes) - 1)

        text = re.sub(r"`([^`]+)`", keep_code, text)
        text = html.escape(text, quote=False)

        def image(m):
            src = self.link(html.unescape(m.group(2)), image=True)
            if not src:
                return html.escape(m.group(1))
            return self.picture(src, m.group(1))

        def anchor(m):
            label, href = m.group(1), html.unescape(m.group(2)).strip()
            target = self.link(href)
            if target is None:
                return '<span class="offsite" title="In the project\'s repository">%s</span>' % label
            extra = ' rel="noopener" target="_blank"' if target.startswith("http") else ""
            return '<a href="%s"%s>%s</a>' % (html.escape(target), extra, label)

        text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", image, text)
        text = re.sub(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\(([^)\s]+)\)", anchor, text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
        text = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<em>\1</em>", text)
        # Some documents write a dash as a spaced hyphen; on the page it is
        # set as the dash it stands for (code is held aside above, untouched).
        text = text.replace(" - ", " – ")
        return re.sub("\x00(\\d+)\x00", lambda m: codes[int(m.group(1))], text)

    # -- blocks --------------------------------------------------------
    LIST_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.*)$")
    TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")

    def heading(self, level, text):
        slug = github_slug(text, self.slugs)
        return '<h%d id="%s">%s</h%d>' % (level, slug, self.inline(text), level)

    def render(self, text, shift=0):
        lines = text.replace("\r\n", "\n").split("\n")
        out, i = [], 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                i += 1
                continue
            if stripped.startswith("```"):
                j, buf = i + 1, []
                while j < len(lines) and not lines[j].strip().startswith("```"):
                    buf.append(lines[j])
                    j += 1
                out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(buf), quote=False))
                i = j + 1
                continue
            m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
            if m:
                out.append(self.heading(min(6, len(m.group(1)) + shift), m.group(2)))
                i += 1
                continue
            if re.match(r"^(-{3,}|\*{3,})\s*$", stripped):
                out.append("<hr>")
                i += 1
                continue
            if stripped.startswith("|") and i + 1 < len(lines) and self.TABLE_SEP_RE.match(lines[i + 1]):
                i = self.table(lines, i, out)
                continue
            if stripped.startswith(">"):
                buf = []
                while i < len(lines) and lines[i].strip().startswith(">"):
                    buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                    i += 1
                out.append("<blockquote>%s</blockquote>" % self.render("\n".join(buf)))
                continue
            if self.LIST_RE.match(line):
                html_list, i = self.list_block(lines, i, len(self.LIST_RE.match(line).group(1)))
                out.append(html_list)
                continue
            buf = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip() and not self.starts_block(lines, i):
                buf.append(lines[i].strip())
                i += 1
            out.append("<p>%s</p>" % self.inline(" ".join(buf)))
        return "\n".join(out)

    def starts_block(self, lines, i):
        s = lines[i].strip()
        m = self.LIST_RE.match(lines[i])
        return (s.startswith(("#", "```", ">", "|")) or bool(m and self.may_interrupt(m))
                or bool(re.match(r"^(-{3,}|\*{3,})\s*$", s)))

    @staticmethod
    def may_interrupt(m):
        """Whether a line LIST_RE matched may start a list right under a line
        of running text: GitHub's rule, CommonMark's, is that a numbered line
        may only when its number is 1. A sentence wrapped before "2026. I
        walk it" was drawn as a list counted from 2026 (2026-11-21)."""
        return not m.group(2)[0].isdigit() or m.group(2) == "1."

    def table(self, lines, i, out):
        def cells(row):
            row = row.strip()
            if row.startswith("|"):
                row = row[1:]
            if row.endswith("|"):
                row = row[:-1]
            return [c.strip() for c in re.split(r"(?<!\\)\|", row)]

        head = cells(lines[i])
        i += 2
        body = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            body.append(cells(lines[i]))
            i += 1
        # Pictures set side by side in a table, a caption over each: the
        # overview's .pair of figures, which stacks on a phone. As a table
        # they were two thumbnails 150px wide there, and the row jumped.
        picture = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)$")
        if body and all(picture.match(c) for row in body for c in row):
            figures = []
            for row in body:
                for k, c in enumerate(row):
                    m = picture.match(c)
                    src = self.link(html.unescape(m.group(2)), image=True)
                    caption = self.inline(head[k]) if k < len(head) else ""
                    shown = self.picture(src, html.escape(m.group(1))) if src else html.escape(m.group(1))
                    figures.append('<figure class="shot">%s<figcaption>%s</figcaption></figure>'
                                   % (shown, caption))
            out.append('<div class="pair">%s</div>' % "".join(figures))
            return i
        figure = re.compile(r"^[~≈]?[\d][\d,.\s]*%?$")
        numeric = [k for k in range(len(head))
                   if body and all(k < len(row) and figure.match(row[k]) for row in body)]

        def cell(tag, k, c):
            css = ' class="num"' if k in numeric else ""
            return "<%s%s>%s</%s>" % (tag, css, self.inline(c), tag)

        narrow = " narrow" if len(head) <= 2 else ""
        parts = ['<div class="table-wrap%s"><table><thead><tr>' % narrow]
        parts += [cell("th", k, c) for k, c in enumerate(head)]
        parts.append("</tr></thead><tbody>")
        for row in body:
            parts.append("<tr>" + "".join(cell("td", k, c) for k, c in enumerate(row)) + "</tr>")
        parts.append("</tbody></table></div>")
        out.append("".join(parts))
        return i

    def list_block(self, lines, i, indent):
        first = self.LIST_RE.match(lines[i])
        ordered = first.group(2)[0].isdigit()
        tag = "ol" if ordered else "ul"
        start = ""
        if ordered and first.group(2) != "1.":
            start = ' start="%s"' % first.group(2)[:-1]
        items = []
        while i < len(lines):
            m = self.LIST_RE.match(lines[i])
            # A list of the other kind is a list of its own, as on GitHub.
            if not m or len(m.group(1)) != indent or m.group(2)[0].isdigit() != ordered:
                break
            text = [m.group(3)]
            children = []
            i += 1
            blank = False
            while i < len(lines):
                nxt = lines[i]
                if not nxt.strip():
                    # A blank line ends the list unless the next line
                    # continues it, indented or as a sibling item.
                    if i + 1 < len(lines) and (
                            (self.LIST_RE.match(lines[i + 1])
                             and len(self.LIST_RE.match(lines[i + 1]).group(1)) >= indent)
                            or (lines[i + 1].startswith(" " * (indent + 2)) and lines[i + 1].strip())):
                        i += 1
                        blank = True
                        continue
                    break
                sub = self.LIST_RE.match(nxt)
                if sub:
                    depth = len(sub.group(1))
                    if depth < indent:
                        break                   # the outer list's
                    if depth == indent and sub.group(2)[0].isdigit() == ordered:
                        break                   # this list's next item
                    # After a blank line nothing runs on to be interrupted:
                    # any number starts a list there, as on GitHub.
                    if blank or self.may_interrupt(sub):
                        if depth > indent:
                            child, i = self.list_block(lines, i, depth)
                            children.append(child)
                            blank = False
                            continue
                        break                   # a list of another kind
                    # A numbered line that may not start a list here: the
                    # item's words go on, as they do on GitHub.
                    text.append(nxt.strip())
                    i += 1
                    continue
                if len(nxt) - len(nxt.lstrip()) > indent:
                    text.append(nxt.strip())
                    i += 1
                    blank = False
                    continue
                break
            items.append("<li>%s%s</li>" % (self.inline(" ".join(text)), "".join(children)))
        return "<%s%s>%s</%s>" % (tag, start, "".join(items), tag), i


# Markdown the documents write, and what GitHub draws of it, which the
# pages must draw too. Held at every build: two sentences wrapped before a
# year ("27 October / 2026. Ready", "14 November / 2026. I walk it") were
# drawn on the site as lists counted from 2026, while GitHub drew them
# whole (2026-11-21).
RENDER_CASES = [
    ("on 14 November\n2026. I walk it", "<p>on 14 November 2026. I walk it</p>"),
    ("- a bullet that wraps\n  2026. on", "<ul><li>a bullet that wraps 2026. on</li></ul>"),
    ("- a bullet that wraps\n2026. on", "<ul><li>a bullet that wraps 2026. on</li></ul>"),
    ("Steps:\n1. one\n2. two", "<p>Steps:</p>\n<ol><li>one</li><li>two</li></ol>"),
    ("Text\n- a bullet under it", "<p>Text</p>\n<ul><li>a bullet under it</li></ul>"),
    ("1. a\n   - x\n2. b", "<ol><li>a<ul><li>x</li></ul></li><li>b</li></ol>"),
    ("2026. A list counted from a year", '<ol start="2026"><li>A list counted from a year</li></ol>'),
    # After a blank line nothing runs on to be interrupted: a number starts a
    # list, of its own when the list before was of the other kind.
    ("- a bullet\n\n2026. a year", '<ul><li>a bullet</li></ul>\n<ol start="2026"><li>a year</li></ol>'),
    ("- a bullet\n\n  2. a nested list", '<ul><li>a bullet<ol start="2"><li>a nested list</li></ol></li></ul>'),
]


def check_renderer():
    for markdown, wanted in RENDER_CASES:
        drawn = Renderer(lambda href, image=False: href).render(markdown)
        if drawn != wanted:
            fail("the Markdown %r is drawn %r, where GitHub draws %r" % (markdown, drawn, wanted))


# ---------------------------------------------------------------------
# Links between the published pages
# ---------------------------------------------------------------------

def resolve(source_path, href):
    """A repository-relative path and anchor for `href`, written in
    the document at `source_path`."""
    path, _, anchor = href.partition("#")
    if not path:
        return source_path, anchor
    joined = os.path.normpath(os.path.join(os.path.dirname(source_path), path))
    return joined.replace("\\", "/"), anchor


def make_linker(source_path, repo_url, wanted=None):
    # Issues Log anchors are never published as their own page (see
    # build_doc_pages): a reference to one always falls through to repo_url,
    # or to None -- rendered by Renderer.inline as a plain "in the project's
    # repository" span, never a broken link.
    def link(href, image=False):
        if re.match(r"^(https?:|mailto:)", href):
            return href
        if href.startswith("#"):
            return href
        path, anchor = resolve(source_path, href)
        if image:
            if path.startswith("docs/screenshots/"):
                return "img/" + os.path.splitext(os.path.basename(path))[0] + ".webp"
            return None
        if path in PAGES:
            return PAGES[path][0] + ("#" + anchor if anchor else "")
        if path == "docs/ISSUES_LOG.md" and anchor and wanted is not None:
            wanted.add(anchor)
        if repo_url:
            return "%s/blob/main/%s%s" % (repo_url.rstrip("/"), path,
                                         "#" + anchor if anchor else "")
        return None
    return link


def issues_log_sections(text):
    """Every ### section of the Issues Log by its GitHub anchor: the
    heading line and the lines up to the next heading of level 1-3."""
    lines = text.replace("\r\n", "\n").split("\n")
    seen, starts = set(), []
    in_code = False
    for n, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
        if in_code:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            starts.append((n, len(m.group(1)), github_slug(m.group(2), seen), m.group(2)))
    sections = {}
    for k, (n, level, slug, title) in enumerate(starts):
        if level != 3:
            continue
        end = len(lines)
        for n2, level2, _, _ in starts[k + 1:]:
            if level2 <= 3:
                end = n2
                break
        sections[slug] = (title, "\n".join(lines[n + 1:end]).strip())
    return sections


# ---------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------

def nav_html(current, prefix=""):
    items = []
    for href, label in NAV:
        here = ' aria-current="page"' if href == current else ""
        items.append('<a href="%s%s"%s>%s</a>' % (prefix, href, here, label))
    return "\n        ".join(items)


def og_tags(config, page, title, description):
    url = config.get("site_url", "").rstrip("/")
    if not url:
        return ""
    return "\n".join([
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="Note Organizer">',
        '<meta property="og:title" content="%s">' % html.escape(title),
        '<meta property="og:description" content="%s">' % html.escape(description),
        '<meta property="og:url" content="%s/%s">' % (url, page),
        '<meta property="og:image" content="%s/img/social-card.png">' % url,
        # Its size, so a network draws the large card at the first share.
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="%s">' % html.escape(SOCIAL_CARD_ALT),
        '<meta name="twitter:card" content="summary_large_image">',
    ])


SOCIAL_CARD_ALT = ("Note Organizer's main window: a list of notes beside a note holding a "
                   "weekly meal plan as a table.")


def tag_copied_page(config, page):
    """A page with a head of its own (a demo, the privacy notice) gets the
    sharing tags too, from its own title and description: without them it
    shared as a bare link."""
    path = os.path.join(OUT, page)
    text = read(path)
    title = re.search(r"<title>(.*?)</title>", text, re.S)
    description = re.search(r'<meta name="description" content="([^"]*)"', text)
    if not title or not description:
        fail("%s has no <title> or description for its sharing tags" % page)
    tags = og_tags(config, page, html.unescape(title.group(1).strip()), html.unescape(description.group(1)))
    if tags:
        write(path, text.replace("</head>", tags + "\n</head>", 1))


def fill(template, values, name):
    def sub(m):
        key = m.group(1)
        if key not in values:
            fail("%s uses {{%s}}, which the build does not provide" % (name, key))
        return str(values[key])
    return re.sub(r"\{\{(\w+)\}\}", sub, template)


def doc_page(shell, config, page, title, description, body_html, source_note, version):
    return fill(shell, {
        "title": html.escape(title),
        "description": html.escape(description),
        "og": og_tags(config, page, title, description),
        "nav": nav_html(page),
        "content": body_html,
        "source_note": source_note,
        "version": version,
    }, page)


def check_kept_apart(repo, config, android):
    """This site presents the project to the people sent here; the apps,
    and the privacy policy the stores are given, never point at it -- the
    owner's rule (2026-10-21), so its users need not know it exists. The
    desktop app's sources and docs/PRIVACY.md must not name the site's
    address, and neither may the Android app's, now that the build reads
    its repository too."""
    host = urllib.parse.urlparse(config.get("site_url", "")).netloc
    if not host:
        return ["site.json has no site_url, so the apps cannot be checked for it"]
    files = [os.path.join(repo, "note_organizer.py"), os.path.join(repo, "docs", "PRIVACY.md")]
    for root, _, names in os.walk(os.path.join(repo, "noteorganizer")):
        files += [os.path.join(root, n) for n in names if n.endswith(".py")]
    for root, _, names in os.walk(os.path.join(android, "app", "src", "main")):
        files += [os.path.join(root, n) for n in names if n.endswith((".kt", ".xml"))]
    return ["%s names this site (%s): the apps and their privacy policy must not point "
            "here" % (f, host)
            for f in sorted(files) if host.lower() in read(f).lower()]


def check_doc_structure(page, body_html):
    """A couple of things in site.css style a block by its position right
    after a heading, rather than by a class, because markdown gives the
    renderer no way to attach one: the Contents list (h2#contents + ul)
    and a test case's Area/Priority/Status line (h3 + ul). Both degrade
    quietly -- the list just renders plain -- if a future edit ever puts
    something else between the heading and its list, so this catches that
    at build time instead of leaving it for someone to notice on the live
    page."""
    problems = []
    m = re.search(r'<h2 id="contents">.*?</h2>\n<(\w+)', body_html)
    if m and m.group(1) not in ("ul", "ol"):
        problems.append("%s: the Contents heading is followed by <%s>, not a list" %
                        (page, m.group(1)))
    # Only a test case's heading ("Case 9 - Cancel a delete") owes a list:
    # other h3s, the plan's "By priority" among them, are plain sections.
    for hm in re.finditer(r'<h3 id="[^"]*">Case .*?</h3>\n<(\w+)', body_html):
        if hm.group(1) != "ul":
            problems.append("%s: a <h3> case heading is followed by <%s>, not its "
                            "metadata list" % (page, hm.group(1)))
    return problems


def build_doc_pages(repo, config, shell, version, sizes):
    repo_url = config.get("repo_url", "")
    # The Issues Log is the project's internal engineering journal, not
    # published as its own page here. A reference to one of its anchors is
    # still validated against real headings below (catches a typo'd link),
    # but it renders as plain "in the project's repository" text rather
    # than a page on this site -- see make_linker.
    wanted = set()
    for path in PAGES:
        Renderer(make_linker(path, repo_url, wanted)).render(read(os.path.join(repo, path)))
    sections = issues_log_sections(read(os.path.join(repo, "docs", "ISSUES_LOG.md")))
    missing = sorted(a for a in wanted if a not in sections)
    if missing:
        fail("pages link to Issues Log anchors that do not exist: " + ", ".join(missing))

    note = ('<p class="source-note">This page is the project document <code>%s</code>, '
            "converted for the web when the site was last built. Links to documents "
            "that are not published here are shown as plain text.</p>")
    written = {}
    structure_problems = []
    for path, (page, title, description) in PAGES.items():
        text = read(os.path.join(repo, path))
        body = Renderer(make_linker(path, repo_url), sizes).render(text)
        structure_problems += check_doc_structure(page, body)
        written[page] = doc_page(shell, config, page, title, description, body,
                                 note % html.escape(path), version)
    if structure_problems:
        fail("site.css styles some things by their position in the page, not a class "
             "(see the comments by h2#contents and h3 + ul in src/site.css) -- these "
             "no longer hold:\n  " + "\n  ".join(structure_problems))
    return written
def build_images(repo):
    try:
        from PIL import Image
    except ImportError:
        fail("Pillow is needed to resize the screenshots")
    shots = os.path.join(repo, "docs", "screenshots")
    out_dir = os.path.join(OUT, "img")
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for name in sorted(os.listdir(shots)):
        if not name.endswith(".png"):
            continue
        with Image.open(os.path.join(shots, name)) as img:
            img = img.convert("RGB")
            if img.width > 1400:
                img = img.resize((1400, round(img.height * 1400 / img.width)), Image.LANCZOS)
            target = os.path.join(out_dir, name[:-4] + ".webp")
            img.save(target, "WEBP", quality=84, method=6)
            made.append((name[:-4], img.width, img.height))
    # The card a shared link shows: the main window, at the size social
    # sites ask for (1200 x 630), cropped from the top.
    with Image.open(os.path.join(shots, "main-window.png")) as img:
        img = img.convert("RGB")
        scale = 1200 / img.width
        img = img.resize((1200, round(img.height * scale)), Image.LANCZOS)
        img.crop((0, 0, 1200, 630)).save(os.path.join(out_dir, "social-card.png"), optimize=True)
    shutil.copy2(os.path.join(repo, "assets", "icon.ico"), os.path.join(OUT, "favicon.ico"))
    with Image.open(os.path.join(repo, "assets", "icon_256.png")) as icon:
        icon.save(os.path.join(out_dir, "icon-256.png"), optimize=True)
        icon.resize((180, 180), Image.LANCZOS).save(os.path.join(out_dir, "apple-touch-icon.png"))
    return {name: (w, h) for name, w, h in made}


# ---------------------------------------------------------------------
# The Android app
# ---------------------------------------------------------------------

def android_facts(android):
    """What the pages say about the Android app, each from its own source
    in that repository: the version from its build file, the figures from
    its qa/README, the description from its README, the pictures' captions
    from the README beside them."""
    gradle = read(os.path.join(android, "app", "build.gradle.kts"))
    m = re.search(r'versionName\s*=\s*"([^"]+)"', gradle)
    if not m:
        fail("the Android app's build.gradle.kts no longer names a versionName")
    readme = read(os.path.join(android, "README.md"))
    # The counts' one home there is its qa/README, which says so.
    qa_readme = read(os.path.join(android, "qa", "README.md"))
    unit = re.search(r"^([0-9][0-9,]*) tests across \S+ suites", qa_readme, re.M)
    walk = re.search(r"[0-9]+ parts and about\s+([0-9][0-9,]*)\s+checks", qa_readme)
    if not unit or not walk:
        fail("the Android qa/README no longer gives its unit tests and walk checks "
             "in the words build.py reads; update one of them")
    captions = {}
    shots_readme = read(os.path.join(android, "docs", "screenshots", "README.md"))
    for name, caption in re.findall(r"^\| `([\w-]+)\.png` \| (.+?) \|$", shots_readme, re.M):
        captions[name] = caption
    return {"version": m.group(1), "unit_tests": unit.group(1), "walk_checks": walk.group(1),
            "readme": readme, "captions": captions}


def build_android_images(android):
    """The Android app's screenshots, as img/android-NAME.webp: a phone held
    upright at 540px wide, twice what a page shows it at; on its side at
    1200."""
    from PIL import Image
    shots = os.path.join(android, "docs", "screenshots")
    out_dir = os.path.join(OUT, "img")
    made = {}
    for name in sorted(os.listdir(shots)):
        if not re.fullmatch(r"\d\d-[\w-]+\.png", name):
            continue
        with Image.open(os.path.join(shots, name)) as img:
            img = img.convert("RGB")
            width = 540 if img.height > img.width else 1200
            if img.width > width:
                img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
            key = "android-" + name[:-4]
            img.save(os.path.join(out_dir, key + ".webp"), "WEBP", quality=84, method=6)
            made[key] = (img.width, img.height)
    if not made:
        fail("no screenshots in %s" % shots)
    return made


def readme_section(text, heading):
    """A README's `## heading` section, its heading included, up to the next."""
    m = re.search(r"^## %s\s*$(.*?)(?=^## |\Z)" % re.escape(heading), text, re.M | re.S)
    if not m:
        fail("the Android README has no '## %s' section" % heading)
    return "## %s\n%s" % (heading, m.group(1).strip())


def android_linker(config):
    """Links in the Android README: to the desktop app's repository, the
    site's own overview of it; to the phone's own files, GitHub once its
    repository is public (android_repo_url), plain text until then."""
    repo_url = config.get("android_repo_url", "")

    def link(href, image=False):
        if image:
            return None
        if re.match(r"^https?://github\.com/[^/]+/noteOrganizer/?$", href):
            return "index.html"
        if re.match(r"^(https?:|mailto:)", href):
            return href
        if href.startswith("#"):
            return None
        path, anchor = resolve("README.md", href)
        if repo_url:
            return "%s/blob/main/%s%s" % (repo_url.rstrip("/"), path, "#" + anchor if anchor else "")
        return None
    return link


def android_page(shell, config, facts, sizes, version):
    """The Android page: the README's opening, the pictures ANDROID_GALLERY
    names with the captions their own README gives them, its sections,
    where it stands."""
    readme = facts["readme"]
    m = re.search(r"^# [^\n]*\n(.*?)^---\s*$", readme, re.M | re.S)
    if not m:
        fail("the Android README no longer opens with a description above a --- line")
    link = android_linker(config)
    parts = ["<h1>Note Organizer for Android</h1>", Renderer(link).render(m.group(1))]
    # Each screen in the theme the page is in: NN-name in a light theme
    # beside NN-name-dark, a caption for each (06-dark, the set's one dark
    # picture, has no light one to pair with, and is not shown).
    missing = [n for n in ANDROID_GALLERY if "android-" + n not in sizes]
    if missing:
        fail("the Android page's pictures are not in the Android repository's "
             "docs/screenshots: %s (ANDROID_GALLERY in build.py)" % ", ".join(missing))
    figures = []
    for name in ANDROID_GALLERY:
        key = "android-" + name
        w, h = sizes[key]
        wide = " wide" if w > h else ""

        def shown(k, css):
            caption = Renderer(link).inline(facts["captions"].get(k[len("android-"):], ""))
            alt = re.sub(r"<[^>]+>", "", caption)
            return ('<img%s src="img/%s.webp" width="%d" height="%d" alt="%s" loading="lazy">'
                    % (css, k, sizes[k][0], sizes[k][1], html.escape(alt)), caption)
        if key + "-dark" in sizes:
            light, light_caption = shown(key, ' class="for-light"')
            dark, dark_caption = shown(key + "-dark", ' class="for-dark"')
            pictures = light + dark
            caption = ('<span class="for-light">%s</span><span class="for-dark">%s</span>'
                       % (light_caption, dark_caption))
        else:
            pictures, caption = shown(key, "")
        figures.append('<figure class="phone-shot%s"><a class="zoom" href="img/%s.webp">%s</a>'
                       '<figcaption>%s</figcaption></figure>' % (wide, key, pictures, caption))
    parts.append('<div class="phone-gallery">%s</div>' % "".join(figures))
    for heading in ANDROID_SECTIONS:
        parts.append(Renderer(link).render(readme_section(readme, heading)))
    repo = config.get("android_repo_url", "")
    # Named by its path, which may break anywhere: the whole address ran
    # 149 px past a phone's screen.
    where = ("in a repository of its own on GitHub, "
             '<a class="repo-link" href="%s" rel="noopener" target="_blank">%s</a>'
             % (html.escape(repo), html.escape(re.sub(r"^https?://(www\.)?github\.com/", "", repo)))
             if repo else "in a repository of its own on GitHub, published when the time comes")
    parts.append(
        '<h2 id="where-it-stands">Where it stands</h2>'
        "<p>Version %s, on its way to Google Play and not published there yet. It is checked by "
        "%s unit tests and by a walk of about %s checks on an emulator, each reading the file the app "
        "wrote; a note, a share code and a backup it makes are read back by the desktop app's own "
        "code. Its code lives %s.</p>"
        % (facts["version"], facts["unit_tests"], facts["walk_checks"], where))
    parts.append('<p class="page-actions"><a class="btn btn-primary" href="android-demo/index.html">'
                 "Try the Android demo</a></p>")
    note = ('<p class="source-note">This page is built from the Android app\'s README and its '
            "screenshots, read from its repository when the site was last built. %s</p>"
            % ("Links to its documents lead to them in that repository." if repo else
               "Links to its documents are shown as plain text until that repository is published."))
    return doc_page(shell, config, "android.html", "Android",
                    "Note Organizer for Android: the same notes as the desktop app, on a phone, "
                    "offline.", "\n".join(parts), note, version)


# ---------------------------------------------------------------------
# Checks on what was written
# ---------------------------------------------------------------------

def check_output():
    problems = []
    ids_by_file = {}
    pages = []
    for root, _, files in os.walk(OUT):
        for name in files:
            if name.endswith(".html"):
                path = os.path.join(root, name)
                text = read(path)
                pages.append((path, text))
                ids_by_file[os.path.normcase(path)] = set(re.findall(r'\bid="([^"]+)"', text))
    for path, text in pages:
        rel = os.path.relpath(path, OUT)
        if "{{" in text:
            problems.append("%s: an unfilled {{token}}" % rel)
        for what in private_text(text):
            problems.append("%s: private %s" % (rel, what))
        if re.search(r"<form\b", text, re.IGNORECASE):
            problems.append("%s: a form, which cannot send: _headers says form-action "
                            "'none', and feedback goes through the stores" % rel)
        # Every picture of an app is shown in the theme the page is in (the
        # owner, 2026-10-24): one in a single theme needs its partner taken.
        for tag in re.findall(r"<img\b[^>]*>", text):
            src = re.search(r'\bsrc="([^"]+)"', tag)
            if src and "img/" in src.group(1) and "icon-256" not in src.group(1) \
                    and not re.search(r'\bclass="for-(dark|light)"', tag):
                problems.append("%s: %s is shown in one theme only; take its partner "
                                "(NAME-light, or NN-name-dark for the Android app's)"
                                % (rel, src.group(1)))
        for attr, href in re.findall(r'\b(href|src)="([^"]+)"', text):
            if re.match(r"^(https?:|mailto:|data:)", href):
                continue
            target, _, anchor = href.partition("#")
            # Relative links must name a file: see NAV. (Absolute ones are
            # only in 404.html, which only a server ever shows.)
            if target.endswith("/") and not target.startswith("/"):
                problems.append("%s: %s=%s names a folder; opened from the computer it shows "
                                "a file listing, so link to its index.html" % (rel, attr, href))
                continue
            if target:
                base = OUT if target.startswith("/") else os.path.dirname(path)
                full = os.path.normpath(os.path.join(base, target.lstrip("/")))
                if href.endswith("/") or os.path.isdir(full):
                    full = os.path.join(full, "index.html")
                if not os.path.exists(full):
                    problems.append("%s: %s=%s points at nothing" % (rel, attr, href))
                    continue
            else:
                full = path
            if anchor and full.endswith(".html"):
                if anchor not in ids_by_file.get(os.path.normcase(full), set()):
                    problems.append("%s: #%s is not an anchor in %s" % (
                        rel, anchor, os.path.relpath(full, OUT)))
    for root, _, files in os.walk(OUT):
        for name in files:
            if name.endswith((".js", ".css", ".txt")):
                for what in private_text(read(os.path.join(root, name))):
                    problems.append("%s: private %s" % (name, what))
    return problems, len(pages)


# ---------------------------------------------------------------------

OPEN_ELSEWHERE = ("Windows would not let go of %s/: something has it open -- an Explorer "
                  "window, or a browser tab showing a page from it. Close it and run "
                  "this again. The site in public/ was left as it was.")


def publish():
    """Put the checked build in public/'s place, keeping the old one until
    the new one is there."""
    old = PUBLIC + ".old"
    shutil.rmtree(old, ignore_errors=True)
    try:
        if os.path.isdir(PUBLIC):
            os.replace(PUBLIC, old)
        os.replace(STAGE, PUBLIC)
    except PermissionError:
        if not os.path.isdir(PUBLIC) and os.path.isdir(old):
            os.replace(old, PUBLIC)  # the last good site goes back
        fail(OPEN_ELSEWHERE % "public")
    shutil.rmtree(old, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # The site lives in the app's repository, under site/: by default the
    # repository is the folder this one sits in.
    parser.add_argument("--repo", default=os.path.dirname(HERE),
                        help="the app's repository (read only)")
    parser.add_argument("--android-repo", default=None,
                        help="the Android app's repository (read only); by default "
                             "site.json's android_repo, or ../androidVersion beside the app's")
    args = parser.parse_args()
    repo = os.path.abspath(args.repo)
    if not os.path.isfile(os.path.join(repo, "note_organizer.py")):
        fail("no note_organizer.py in %s; pass --repo" % repo)

    config = {}
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            config = json.load(f)
    android = os.path.abspath(args.android_repo or os.path.join(
        repo, config.get("android_repo") or ANDROID_DEFAULT))
    if not os.path.isfile(os.path.join(android, "app", "build.gradle.kts")):
        fail("no Android app in %s; pass --android-repo" % android)

    check_renderer()
    version, themes, ui = app_facts(repo)
    numbers = project_numbers(repo)
    droid = android_facts(android)

    # Only these two folders, both this folder's own output, are ever
    # emptied or replaced.
    for folder, name in ((PUBLIC, "public"), (STAGE, "public.building")):
        if os.path.basename(folder) != name or os.path.dirname(folder) != HERE:
            fail("refusing to touch %s" % folder)
    try:
        if os.path.isdir(STAGE):
            shutil.rmtree(STAGE)  # what a build that stopped half-way left
        os.makedirs(STAGE)
    except PermissionError:
        fail(OPEN_ELSEWHERE % "public.building")

    # Static files from src/, as they are, except the templates.
    for root, _, files in os.walk(SRC):
        for name in files:
            if name in ("index.html", "page.html", "site-privacy.html", "404.html") and root == SRC:
                continue
            source = os.path.join(root, name)
            target = os.path.join(OUT, os.path.relpath(source, SRC))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)
    for page in ("demo/index.html", "android-demo/index.html"):
        tag_copied_page(config, page)

    images = build_images(repo)
    images.update(build_android_images(android))

    app_data = {
        "version": version,
        "themes": themes["THEMES"],
        "themeLabels": themes["THEME_LABELS"],
        "darkThemes": themes["DARK_THEMES"],
        "lightThemes": themes["LIGHT_THEMES"],
        "categoryColors": themes["DEFAULT_CATEGORY_COLORS"],
        "paletteColors": themes["PALETTE_COLORS"],
        "noteColors": themes["PRESET_NOTE_COLORS"],
        "highlightColors": themes["HIGHLIGHT_COLOR_PALETTE"],
        "emojiGroups": [[name, list(chars)] for name, chars, _ in ui["EMOJI_GROUPS"]],
        "dayMarkers": [mark for mark, _ in ui["DAY_MARKER_EMOJIS"]],
        "fontFamilies": list(ui["FONT_FAMILIES"]),
        "fontSizes": list(ui["FONT_SIZES"]),
        "maxIndent": ui["MAX_INDENT"],
        "indentStep": ui["INDENT_STEP"],
    }
    write(os.path.join(OUT, "demo", "app-data.js"),
          "// Generated by build.py from the app's own source -- do not edit.\n"
          "window.NO_APP = " + json.dumps(app_data, ensure_ascii=False, indent=1) + ";\n")
    write(os.path.join(OUT, "android-demo", "android-data.js"),
          "// Generated by build.py from the Android app's build file -- do not edit.\n"
          "window.NO_ANDROID = " + json.dumps({"version": droid["version"]}) + ";\n")

    shell = read(os.path.join(SRC, "page.html"))
    doc_pages = build_doc_pages(repo, config, shell, version, images)
    for page, text in doc_pages.items():
        write(os.path.join(OUT, page), text)
    write(os.path.join(OUT, "android.html"), android_page(shell, config, droid, images, version))

    # The privacy notice and the 404 wear the site's header and footer, so
    # neither reads as a dead end from another site. The 404 is shown at any
    # address, so its links start at the site's root.
    for name, prefix in (("site-privacy.html", ""), ("404.html", "/")):
        write(os.path.join(OUT, name), fill(read(os.path.join(SRC, name)), {
            "nav": nav_html("", prefix), "version": version, "root": prefix}, name))
    tag_copied_page(config, "site-privacy.html")   # the 404 is never shared

    index_values = dict(numbers)
    index_values.update({
        "version": version,
        "og": og_tags(config, "", "Note Organizer",
                      "An offline notes app for Windows 11, with a web demo you can try "
                      "in the browser."),
        "nav": nav_html("index.html"),
        "android_version": droid["version"],
        "theme_count": len(themes["THEMES"]),
        "theme_names": ", ".join(themes["THEME_LABELS"][key] for key in
                                 themes["DARK_THEMES"] + themes["LIGHT_THEMES"]),
    })
    for name, (w, h) in images.items():
        index_values["w_" + name.replace("-", "_")] = w
        index_values["h_" + name.replace("-", "_")] = h
    write(os.path.join(OUT, "index.html"),
          fill(read(os.path.join(SRC, "index.html")), index_values, "index.html"))

    problems, page_count = check_output()
    problems += check_kept_apart(repo, config, android)
    if problems:
        print("\n".join(problems))
        shutil.rmtree(STAGE, ignore_errors=True)
        fail("%d problem(s) in the output; public/ was left as it was" % len(problems))
    publish()
    print("Built %d pages into %s" % (page_count, PUBLIC))
    print("  from the app at version %s" % version)
    print("  %d screenshots, %d themes, %d emoji groups" % (
        len(images), len(themes["THEMES"]), len(ui["EMOJI_GROUPS"])))
    print("  figures: %(test_cases)s test cases, %(mutants)s mutants, about %(checks)s checks, "
          "%(unit_suites)s unit suites, %(qa_suites)s qa suites" % numbers)


if __name__ == "__main__":
    main()
