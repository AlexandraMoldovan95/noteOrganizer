"""What the build ships is what is tested, and its licenses say so.

The .exe carries the Pillow installed where it is built, and the licenses
in THIRD_PARTY_NOTICES.txt. NoteOrganizer.spec stops a build whose Pillow
is not the one requirements.txt pins, or whose licenses are stale. This
holds the rest of the chain on every run of the gates: the Linux image
installs that same Pillow, the licenses name it, and the build still
bundles the file About opens. CI once tested a newer Pillow than the .exe
shipped, because nothing pinned it.

    py tools/check_shipped.py
"""
import io
import os
import re
import sys

import guest  # noqa: E402 -- the memory ceiling, before the app's code (tools/guest.py)

guest.settle(heavy=False)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from noteorganizer.core import diagnostics  # noqa: E402 -- after the path


def text(*parts):
    path = os.path.join(ROOT, *parts)
    if not os.path.isfile(path):
        return ""
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def main():
    pin = re.search(r"^Pillow==(\S+)$", text("requirements.txt"), re.M)
    pillow = pin.group(1) if pin else None
    checks = [
        ("requirements.txt pins Pillow to one version", pillow is not None),
        ("the Linux image installs the pinned Pillow (%s)" % pillow,
         bool(pillow) and ("Pillow==%s\n" % pillow) in text("tools", "linux-ci", "Dockerfile")),
        ("%s holds the licenses of that Pillow" % diagnostics.NOTICES,
         bool(pillow) and ("\nPillow %s (" % pillow) in text(diagnostics.NOTICES)),
        ("NoteOrganizer.spec bundles %s where About looks for it" % diagnostics.NOTICES,
         re.search(r"\(\s*'%s'\s*,\s*'\.'\s*\)" % re.escape(diagnostics.NOTICES),
                   text("NoteOrganizer.spec")) is not None),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print("  %s  %s" % ("ok  " if ok else "FAIL", name))
    if failed:
        print("%d of %d failed: the steps are in docs/RELEASE_WINDOWS.md, "
              "\"Updating Pillow\"." % (len(failed), len(checks)))
        return 1
    print("What the build ships is what is tested (%d checks)." % len(checks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
