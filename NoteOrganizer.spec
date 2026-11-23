# -*- mode: python ; coding: utf-8 -*-
"""The build. Two things here are generated rather than typed.

The version resource is written from APP_VERSION at build time, so the
number Windows shows in the file's Properties cannot drift from the one
the app shows in its own About box -- which is exactly what an
0.0.0.0 with no product name was: nobody had typed anything, and
nothing would ever have noticed.

The icon is drawn by tools/make_icon.py, which writes the files in
assets/; the build takes those as they are, and ships them inside the
bundle as well as stamping one on the .exe -- the stamp is what Explorer
and the taskbar read, the shipped copy is what the window itself puts
in its title bar.

The licenses (THIRD_PARTY_NOTICES.txt) are checked, not generated: the
build stops when they are not those of the Python, Pillow and PyInstaller
doing it, or when that Pillow is not the one requirements.txt pins -- the
one CI tests.
"""
import glob
import importlib.util
import os
import re
from importlib import metadata


def _check_what_ships():
    """Stop the build when the licenses or the Pillow would not match."""
    pin = re.search(r"^Pillow==(\S+)", open("requirements.txt", encoding="utf-8").read(), re.M)
    if not pin or pin.group(1) != metadata.version("pillow"):
        raise SystemExit("Pillow %s is installed, but requirements.txt pins %s -- CI tests "
                         "the pinned one." % (metadata.version("pillow"), pin and pin.group(1)))
    spec = importlib.util.spec_from_file_location(
        "notices", os.path.join("tools", "make_third_party_notices.py"))
    notices = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notices)
    with open(notices.OUT, encoding="utf-8") as fh:
        if fh.read() != notices.render():
            raise SystemExit("THIRD_PARTY_NOTICES.txt is out of date: run "
                             "py tools/make_third_party_notices.py and commit it.")


_check_what_ships()


def _app_version():
    """The version the app reports, read from its own source."""
    src = open("note_organizer.py", encoding="utf-8").read()
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', src)
    return m.group(1) if m else "0.0.0"


def _write_version_resource(path):
    """A Windows version resource, from APP_VERSION.

    Windows wants four numbers; the app carries three, so the fourth is
    a zero. Everything else is plain truth about what this file is --
    there is no company, so there is no CompanyName.
    """
    version = _app_version()
    parts = [int(p) for p in version.split(".")[:3]] + [0]
    quad = ", ".join(str(p) for p in parts)
    resource = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(%(quad)s),
    prodvers=(%(quad)s),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription',
                   'Note Organizer - offline notes, calendar and checklists'),
      StringStruct('FileVersion', '%(version)s'),
      StringStruct('InternalName', 'NoteOrganizer'),
      StringStruct('OriginalFilename', 'NoteOrganizer.exe'),
      StringStruct('ProductName', 'Note Organizer'),
      StringStruct('ProductVersion', '%(version)s'),
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""" % {"quad": quad, "version": version}
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(resource)
    return path


ICON = os.path.join("assets", "icon.ico")
VERSION_FILE = _write_version_resource(os.path.join("build", "version_info.txt")) \
    if os.path.isdir("build") else None


a = Analysis(
    ['note_organizer.py'],
    pathex=[],
    binaries=[],
    # The window reads its own icon at runtime, so the icons travel
    # inside the bundle as well as one being stamped on the .exe. Every
    # accent, not just the default: the icon follows the theme, and a
    # theme whose icon did not ship would fall back to the purple one.
    # Globbed rather than listed, so adding a theme and re-running
    # tools/make_icon.py --all is the whole job.
    # The licenses beside them, where Settings -> About opens them.
    datas=[(f, 'assets') for f in glob.glob(os.path.join('assets', 'icon*.ico'))
           + glob.glob(os.path.join('assets', 'icon*.png'))]
          + [('THIRD_PARTY_NOTICES.txt', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # numpy is never imported by this app -- it only gets pulled in because
    # Pillow *can* use it for array interop (Image.fromarray and friends),
    # which nothing here does. Bundling it cost 28 MB of the 68 MB build.
    # Verified with numpy blocked at import level: opening, downscaling,
    # upscaling and frame-by-frame compositing of animated GIFs all still
    # work, i.e. the whole image-preview path is unaffected.
    # If a future feature ever does hand arrays to Pillow, drop this entry.
    excludes=['numpy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NoteOrganizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
    version=VERSION_FILE,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NoteOrganizer',
)
