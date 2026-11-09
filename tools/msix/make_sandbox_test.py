"""Write the Windows Sandbox files that prove the package before the Store.

    py tools/msix/build_msix.py --update
    py tools/msix/make_sandbox_test.py

Then double-click one of the three .wsb files it writes in dist/msix. Each
opens a disposable Windows whose script signs the packages with a
certificate made there; a message says when it is done, and closing the
sandbox throws everything in it away. Only dist/msix/out leaves it.

- NoteOrganizer-msix-test.wsb, sandbox_test.ps1: the life of the package.
  An older exe's notebook in AppData; install, start, update, uninstall,
  reinstall; after each step what the profile's notebook, the package's
  private copy and AppData hold, in out/result.txt.
- NoteOrganizer-msix-look.wsb, sandbox_look.ps1: the package to ship on a
  Windows with 2 GB of memory, started once in each of the eight themes on
  a notebook of 40 notes: how soon its window shows, whether it lies inside
  the work area, a photo of it, the app's memory, a close as the X does,
  the theme kept, no crash log; in out/look/.
- NoteOrganizer-msix-wack.wsb, sandbox_wack.ps1: the Windows App
  Certification Kit on the package to ship, as Partner Center runs it --
  never on this computer, where the app it starts would open the owner's
  notebook. The kit, its test engine (TAEF) and the SDK's Windows metadata
  are copied in from read-only folders, and the kit's COM classes as this
  computer's registry holds them: read here with `reg export`, never
  written. Its report and a line for each test land in out/wack/.

The sandboxes run without a virtual GPU, which made one lose its
connection on this machine, and without a network, which an offline app
does not need.

dist/msix must hold exactly the pair build_msix.py --update made from
APP_VERSION: sandbox_test.ps1 installs the lowest package there and updates
to the highest, and with 0.97.405's packages left beside 0.100.512's it
would have played an update from 0.97.405.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "dist", "msix")
HERE = os.path.dirname(os.path.abspath(__file__))
KITS = r"C:\Program Files (x86)\Windows Kits\10"
# What the kit needs of the SDK beside it, each found missing in a sandbox
# that had only the kit: its test engine, Windows' metadata and the API
# contracts (the six metadata tests), the platform list.
KIT_PARTS = (("App Certification Kit", "C:\\kitsrc"), ("Testing", "C:\\testingsrc"),
             ("UnionMetadata", "C:\\unionsrc"), ("References", "C:\\referencessrc"),
             ("Platforms", "C:\\platformssrc"))

WSB = """<Configuration>
  <vGPU>Disable</vGPU>
  <Networking>Disable</Networking>
{memory}  <MappedFolders>
{folders}  </MappedFolders>
  <LogonCommand>
    <Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\pkg\\{script}</Command>
  </LogonCommand>
</Configuration>
"""
FOLDER = """    <MappedFolder>
      <HostFolder>{host}</HostFolder>
      <SandboxFolder>{inside}</SandboxFolder>
      <ReadOnly>{read_only}</ReadOnly>
    </MappedFolder>
"""
LOOK_TITLES = ("Groceries", "Café with Ana", "Stand-up notes", "October budget",
               "Résumé draft", "Crème brûlée", "Books to read", "Trip to Cluj",
               "Dentist", "Car service", "Recipe: pancakes", "Gift ideas")


def the_pair():
    """The names of the two packages build_msix.py --update makes."""
    sys.path.insert(0, HERE)
    from build_msix import app_version
    major, minor, build = app_version()
    return ["NoteOrganizer_%d.%d.%d.0.msix" % (major, minor, b) for b in (build, build + 1)]


def look_notebook():
    """40 notes of an ordinary week: some with a checklist, one holding a
    table, a few with accented letters, in the three default categories."""
    notes = []
    for i in range(40):
        title = LOOK_TITLES[i % len(LOOK_TITLES)]
        if i >= len(LOOK_TITLES):
            title += " %d" % (i // len(LOOK_TITLES) + 1)
        day = 1 + i % 28
        note = {"id": i + 1, "uid": "look-%02d" % (i + 1), "title": title,
                "body": "Notes for %s.\nA second line, so the preview has words." % title,
                "category": ("General", "Work", "Personal")[i % 3],
                "date": "2026-11-%02d" % day,
                "created": "2026-11-%02d 09:00:00" % day,
                "updated": "2026-11-%02d 09:30:00" % day}
        if i % 4 == 0:
            note["checklist"] = [{"text": "Milk", "done": True},
                                 {"text": "Bread", "done": False},
                                 {"text": "Jalapeños", "done": False}]
        if i == 3:
            note["body"] = ("Spent so far:\n| Item | Lei |\n| --- | --- |\n"
                            "| Rent | 1200 |\n| Food | 650 |")
        notes.append(note)
    return notes


def export_kit_classes(target):
    """The COM classes and type libraries the kit's installer registered
    (every key whose data names the kit's folder), as .reg files in
    *target*; `reg query` and `reg export` only read the registry."""
    os.makedirs(target, exist_ok=True)
    for name in glob.glob(os.path.join(target, "*.reg")):
        os.remove(name)   # this tool's own earlier exports
    count = 0
    for kind in ("CLSID", "TypeLib"):
        base = r"HKLM\SOFTWARE\Classes\%s" % kind
        found = subprocess.run(["reg", "query", base, "/s", "/f", "App Certification Kit", "/d"],
                               capture_output=True, text=True, timeout=300).stdout
        guids = sorted(set(re.findall(r"\\%s\\(\{[0-9A-Fa-f-]{36}\})" % kind, found)))
        for guid in guids:
            count += 1
            done = subprocess.run(["reg", "export", base + "\\" + guid,
                                   os.path.join(target, "%s%02d.reg" % (kind[0].lower(), count)), "/y"],
                                  capture_output=True, text=True, timeout=60)
            if done.returncode != 0:
                sys.exit("reg export failed for %s: %s" % (guid, done.stderr.strip()))
    if not count:
        sys.exit("no COM class of the App Certification Kit in the registry: install it "
                 "with the Windows SDK (docs/RELEASE_WINDOWS.md)")
    return count


def write_wsb(name, script, folders, memory_mb=None):
    memory = "  <MemoryInMB>%d</MemoryInMB>\n" % memory_mb if memory_mb else ""
    text = WSB.format(memory=memory, script=script, folders="".join(
        FOLDER.format(host=host, inside=inside, read_only="true" if read_only else "false")
        for host, inside, read_only in folders))
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def main():
    pair = the_pair()
    there = sorted(os.path.basename(p) for p in glob.glob(os.path.join(OUT, "NoteOrganizer_*.msix")))
    missing = [p for p in pair if p not in there]
    if missing:
        sys.exit("not in dist/msix: %s -- run build_msix.py --update first" % ", ".join(missing))
    stray = [p for p in there if p not in pair]
    if stray:
        sys.exit("dist/msix holds other packages too: %s. Move them out of the folder: "
                 "sandbox_test.ps1 installs the lowest package there and updates to the "
                 "highest, so it would test those instead of %s."
                 % (", ".join(stray), " and ".join(pair)))
    signtools = sorted(glob.glob(os.path.join(KITS, "bin", "*", "x64", "signtool.exe")))
    if not signtools:
        sys.exit("signtool.exe not found: install the Windows SDK (docs/RELEASE_WINDOWS.md)")
    lacking = [part for part, _ in KIT_PARTS if not os.path.isdir(os.path.join(KITS, part))]
    if lacking:
        sys.exit("not in %s: %s -- install the Windows SDK with its App Certification Kit "
                 "(docs/RELEASE_WINDOWS.md)" % (KITS, ", ".join(lacking)))
    # The memory ceiling, before reg starts (tools/guest.py, a folder up).
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import guest
    guest.settle(heavy=False)
    classes = export_kit_classes(os.path.join(OUT, "wack_reg"))

    for script in ("sandbox_test.ps1", "sandbox_look.ps1", "sandbox_wack.ps1"):
        shutil.copy2(os.path.join(HERE, script), OUT)
    with open(os.path.join(OUT, "look_notes.json"), "w", encoding="utf-8") as f:
        json.dump(look_notebook(), f, ensure_ascii=False, indent=1)
    results = os.path.join(OUT, "out")
    os.makedirs(results, exist_ok=True)
    common = [(OUT, "C:\\pkg", True), (os.path.dirname(signtools[-1]), "C:\\sdk", True),
              (results, "C:\\out", False)]
    kit = [(os.path.join(KITS, part), inside, True) for part, inside in KIT_PARTS]
    made = [write_wsb("NoteOrganizer-msix-test.wsb", "sandbox_test.ps1", common),
            write_wsb("NoteOrganizer-msix-look.wsb", "sandbox_look.ps1", common, memory_mb=2048),
            write_wsb("NoteOrganizer-msix-wack.wsb", "sandbox_wack.ps1", common + kit)]
    print("packages:", " and ".join(pair))
    print("the kit's COM keys read:", classes)
    for path in made:
        print("double-click:", path)
    print("the results land in:", results)


if __name__ == "__main__":
    main()
