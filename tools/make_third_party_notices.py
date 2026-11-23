"""Write THIRD_PARTY_NOTICES.txt: the licenses of everything the built app carries.

    py tools/make_third_party_notices.py

The texts are read from the installed Python, Pillow and PyInstaller
themselves, never retyped, so they are the licenses of the very copies the
build bundles. Run it again whenever one of them is updated -- the release
steps in docs/RELEASE_WINDOWS.md say when -- and commit the result: the
build ships it beside the app, and Settings -> About opens it.
"""
import html.parser
import os
import re
import sys
import textwrap
from importlib import metadata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "THIRD_PARTY_NOTICES.txt")
RULE = "=" * 72
# Python's LICENSE.txt holds the PSF license and the Windows build's own
# conditions; the libraries built into the interpreter (OpenSSL, expat,
# zlib, libmpdec...) are acknowledged only in its documentation.
INCORPORATED = "licenses-and-acknowledgements-for-incorporated-software"


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().strip()


def need(path, what):
    if not os.path.isfile(path):
        sys.exit("%s was not found: %s" % (what, path))
    return path


def dist_license(name, *candidates):
    dist = metadata.distribution(name)
    for candidate in candidates:
        for entry in dist.files or []:
            if str(entry).replace("\\", "/").endswith(candidate):
                return dist.version, read(dist.locate_file(entry))
    sys.exit("%s's license file was not found in its installed metadata" % name)


class _SectionText(html.parser.HTMLParser):
    """The text of one <section id=...> of a Sphinx page, its <pre> kept as is."""

    def __init__(self, section_id):
        super().__init__()
        self.section_id, self.depth, self.pre = section_id, 0, 0
        self.out, self.line, self.skip = [], [], 0

    def flush(self):
        text = re.sub(r"\s+", " ", "".join(self.line)).strip()
        if text:
            self.out.append(textwrap.fill(text, 72))
        self.line = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section" and (self.depth or attrs.get("id") == self.section_id):
            self.depth += 1
        if not self.depth:
            return
        if tag == "a" and "headerlink" in (attrs.get("class") or ""):
            self.skip += 1
        elif tag == "pre":
            self.flush()
            self.pre += 1
        elif tag in ("p", "li", "h2", "h3", "h4"):
            self.flush()

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag == "a" and self.skip:
            self.skip -= 1
        elif tag == "pre":
            self.out.append("".join(self.line).rstrip())
            self.line, self.pre = [], self.pre - 1
        elif tag in ("h2", "h3", "h4"):
            self.flush()
            self.out[-1] = "\n--- %s ---" % self.out[-1]
        elif tag in ("p", "li"):
            self.flush()
        elif tag == "section":
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.line.append(data)


def incorporated_software():
    page = need(os.path.join(sys.base_prefix, "Doc", "html", "license.html"),
                "Python's documentation (install it with the interpreter)")
    parser = _SectionText(INCORPORATED)
    parser.feed(read(page))
    if len(parser.out) < 10:
        sys.exit("The incorporated-software section was not found in %s" % page)
    return "\n\n".join(parser.out).strip()


def section(title, body):
    return "%s\n%s\n%s\n\n%s\n" % (RULE, title, RULE, body)


def render():
    """The file's whole text, for the Python running this and the Pillow and
    PyInstaller installed beside it. The build compares it with the
    committed file, and refuses to bundle a stale one."""
    python_license = need(os.path.join(sys.base_prefix, "LICENSE.txt"),
                          "Python's LICENSE.txt")
    python_version = "%d.%d.%d" % sys.version_info[:3]
    pillow_version, pillow_text = dist_license("pillow", "licenses/LICENSE", "LICENSE")
    pyi_version, pyi_text = dist_license("pyinstaller", "licenses/COPYING.txt", "COPYING.txt")
    parts = [
        "Note Organizer for Windows -- licenses\n\n"
        "Note Organizer is free software under the MIT license (the first section).\n"
        "The Windows app also carries the software below, each under its own\n"
        "license: Python %s, with Tcl/Tk, OpenSSL, libffi, bzip2, zlib, expat\n"
        "and the other libraries its Windows build includes; Pillow %s, with\n"
        "the image libraries it brings; PyInstaller %s's bootloader, the small\n"
        "program that starts the app; and Microsoft's C runtime.\n"
        % (python_version, pillow_version, pyi_version),
        section("Note Organizer -- MIT License", read(os.path.join(ROOT, "LICENSE"))),
        section("Python %s (with Tcl/Tk, OpenSSL and the other parts of its Windows build)"
                % python_version, read(python_license)),
        section("Python %s -- licenses and acknowledgements for incorporated software"
                % python_version, incorporated_software()),
        section("Pillow %s (with the image libraries it includes)" % pillow_version,
                pillow_text),
        section("PyInstaller %s (its bootloader starts the app)" % pyi_version, pyi_text),
        section("Microsoft Visual C++ runtime",
                "VCRUNTIME140.dll and VCRUNTIME140_1.dll are Microsoft's, included\n"
                "under the terms that allow the Visual C++ runtime to be\n"
                "redistributed with an application (see the Windows build's\n"
                "conditions in the Python section)."),
    ]
    return "\n".join(parts)


def main():
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(render())
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
