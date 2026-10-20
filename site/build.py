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
   {{token}} is left unfilled, and nothing private (a home folder, an
   e-mail address) reached a page.
4. Only then puts it in public/'s place. Any failure stops the build with
   a non-zero exit and leaves the last good site in public/ untouched.

public/ is what Netlify publishes. Edit src/ and run this again; never
edit public/ by hand, because the next build replaces it.
"""

import argparse
import ast
import html
import json
import os
import re
import shutil
import sys

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
    # Linked from every page's footer and from the feedback form; both apps
    # open it from Settings > About, and both stores are given its address,
    # so its file name must not change (check_app_links).
    "docs/PRIVACY.md": ("privacy.html", "Privacy policy",
                        "What Note Organizer keeps, where it keeps it, and "
                        "the one thing that is ever sent."),
}
# Text that must never reach a published page. A build that finds one
# stops; the page is not published with it.
FORBIDDEN = [r"adas9", r"mekotrading", r"noteOrganizerSavedFiles",
             r"[A-Za-z]:\\Users\\", r"stepIT"]

# Pages are linked by file, never by folder ("demo/index.html", not
# "demo/"): a server opens a folder's index.html by itself, but a page
# opened from the computer gets a file listing instead.
NAV = [("index.html", "Overview"),
       ("how-its-built.html", "How it's built"),
       ("in-my-words.html", "In my words"), ("testing.html", "Testing")]


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
    numbers["test_cases"] = sum(
        1 for row in sheet.iter_rows(min_row=2, values_only=True)
        if row and row[0] not in (None, ""))
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
    href, or None when the target is not published here."""

    def __init__(self, link):
        self.link = link
        self.slugs = set()

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
            return '<img src="%s" alt="%s" loading="lazy">' % (
                html.escape(src), m.group(1))

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
        return (s.startswith(("#", "```", ">", "|")) or bool(self.LIST_RE.match(lines[i]))
                or bool(re.match(r"^(-{3,}|\*{3,})\s*$", s)))

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
        parts = ['<div class="table-wrap"><table><thead><tr>']
        parts += ["<th>%s</th>" % self.inline(c) for c in head]
        parts.append("</tr></thead><tbody>")
        for row in body:
            parts.append("<tr>" + "".join("<td>%s</td>" % self.inline(c) for c in row) + "</tr>")
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
            if not m or len(m.group(1)) != indent:
                break
            text = [m.group(3)]
            children = []
            i += 1
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
                        continue
                    break
                sub = self.LIST_RE.match(nxt)
                if sub and len(sub.group(1)) > indent:
                    child, i = self.list_block(lines, i, len(sub.group(1)))
                    children.append(child)
                    continue
                if sub:
                    break
                if len(nxt) - len(nxt.lstrip()) > indent:
                    text.append(nxt.strip())
                    i += 1
                    continue
                break
            items.append("<li>%s%s</li>" % (self.inline(" ".join(text)), "".join(children)))
        return "<%s%s>%s</%s>" % (tag, start, "".join(items), tag), i


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
        '<meta property="og:title" content="%s">' % html.escape(title),
        '<meta property="og:description" content="%s">' % html.escape(description),
        '<meta property="og:url" content="%s/%s">' % (url, page),
        '<meta property="og:image" content="%s/img/social-card.png">' % url,
        '<meta name="twitter:card" content="summary_large_image">',
    ])


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
    for hm in re.finditer(r'<h3 id="[^"]*">.*?</h3>\n<(\w+)', body_html):
        if hm.group(1) != "ul":
            problems.append("%s: a <h3> case heading is followed by <%s>, not its "
                            "metadata list" % (page, hm.group(1)))
    return problems


def build_doc_pages(repo, config, shell, version):
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
        body = Renderer(make_linker(path, repo_url)).render(text)
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
        for pattern in FORBIDDEN:
            if re.search(pattern, text, re.IGNORECASE):
                problems.append("%s: private text matching %r" % (rel, pattern))
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
                text = read(os.path.join(root, name))
                for pattern in FORBIDDEN:
                    if re.search(pattern, text, re.IGNORECASE):
                        problems.append("%s: private text matching %r" % (name, pattern))
    return problems, len(pages)


# ---------------------------------------------------------------------

OPEN_ELSEWHERE = ("Windows would not let go of %s/: something has it open -- an Explorer "
                  "window, or a browser tab showing a page from it. Close it and run "
                  "this again. The site in public/ was left as it was.")


def check_feedback_form(repo):
    """The feedback page keeps its promises: Netlify sees the form (and its
    trap for robots), it has a field for every detail the app sends -- the
    app's own list, DETAIL_KEYS, read from its source -- the page's script
    knows each one, the thank-you page exists, and the site's headers let a
    form send to the site itself."""
    keys = literal_assignments(
        read(os.path.join(repo, "noteorganizer", "core", "diagnostics.py")),
        ["DETAIL_KEYS"])["DETAIL_KEYS"]
    problems = []
    page = os.path.join(OUT, "feedback.html")
    if not os.path.exists(page):
        return ["feedback.html is missing"]
    html = read(page)
    script = read(os.path.join(OUT, "feedback.js"))
    for needed in ('name="feedback"', 'data-netlify="true"', 'netlify-honeypot="company"',
                   'name="company"', '<input type="hidden" name="form-name" value="feedback">',
                   'action="thanks.html"'):
        if needed not in html:
            problems.append("feedback.html: no %s" % needed)
    for key in keys:
        if '<input type="hidden" name="%s">' % key not in html:
            problems.append("feedback.html: no hidden field for the app's detail %r" % key)
        if '["%s",' % key not in script:
            problems.append("feedback.js: no label for the app's detail %r" % key)
    if not os.path.exists(os.path.join(OUT, "thanks.html")):
        problems.append("thanks.html is missing: the form's answer page")
    if "form-action 'self'" not in read(os.path.join(OUT, "_headers")):
        problems.append("_headers: form-action must be 'self', or the feedback form cannot send")
    # The privacy policy promises the details arrive only with the form:
    # the app puts them after a "#", and only the page's script reads them.
    if "location.hash" not in script:
        problems.append("feedback.js: does not read the details after the '#' the app "
                        "puts them behind")
    return problems


def check_app_links(repo, config):
    """The pages the app opens by their address are pages this build makes,
    at the site's own address: the feedback form, and the privacy policy,
    whose address both stores are given as well."""
    urls = literal_assignments(
        read(os.path.join(repo, "noteorganizer", "core", "diagnostics.py")),
        ["FEEDBACK_URL", "PRIVACY_URL"])
    site = config.get("site_url", "").rstrip("/") + "/"
    problems = []
    for name, url in sorted(urls.items()):
        if not url.startswith(site):
            problems.append("diagnostics.%s (%s) is not on the site's address, %s" %
                            (name, url, site))
        elif not os.path.isfile(os.path.join(OUT, url[len(site):])):
            problems.append("diagnostics.%s opens %s, a page this build does not make" %
                            (name, url[len(site):]))
    return problems


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
    args = parser.parse_args()
    repo = os.path.abspath(args.repo)
    if not os.path.isfile(os.path.join(repo, "note_organizer.py")):
        fail("no note_organizer.py in %s; pass --repo" % repo)

    config = {}
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            config = json.load(f)

    version, themes, ui = app_facts(repo)
    numbers = project_numbers(repo)

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
            if name in ("index.html", "page.html") and root == SRC:
                continue
            source = os.path.join(root, name)
            target = os.path.join(OUT, os.path.relpath(source, SRC))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)

    images = build_images(repo)

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

    shell = read(os.path.join(SRC, "page.html"))
    doc_pages = build_doc_pages(repo, config, shell, version)
    for page, text in doc_pages.items():
        write(os.path.join(OUT, page), text)

    index_values = dict(numbers)
    index_values.update({
        "version": version,
        "og": og_tags(config, "", "Note Organizer",
                      "An offline notes app for Windows, with a web demo you can try "
                      "in the browser."),
        "nav": nav_html("index.html"),
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
    problems += check_feedback_form(repo)
    problems += check_app_links(repo, config)
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
