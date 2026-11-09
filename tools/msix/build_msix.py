"""Pack the built app (dist/NoteOrganizer) into an MSIX package, unsigned.

    py tools/msix/build_msix.py              # test identity, version from APP_VERSION
    py tools/msix/build_msix.py --update     # and one a build higher, to play an update
    py tools/msix/build_msix.py --name N --publisher "CN=..." --publisher-display "..."

Build the app first (NoteOrganizer.spec, see docs/RELEASE_WINDOWS.md); the
packages land in dist/msix/. The identity is a test one, NoteOrganizer.Test
and CN=NoteOrganizerTest, until Partner Center reserves the Store's; the
Store signs what it publishes, and a test package is signed inside Windows
Sandbox (make_sandbox_test.py), so this machine's certificate stores are
never touched. The Store also wants a Major of 1 or more: 0.x.y.0 is for
Sandbox only.

MinVersion is Windows 11, version 24H2 (build 26100): the oldest Windows the
package was proved on, in Windows Sandbox. Below it the Store does not offer
the app. The owner's choice, 2026-11-09: what was never tried is not declared
(docs/RELEASE_WINDOWS.md, "Which Windows").
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST = os.path.join(ROOT, "dist", "NoteOrganizer")
OUT = os.path.join(ROOT, "dist", "msix")
ICON = os.path.join(ROOT, "assets", "icon_256.png")

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap rescap">
  <Identity Name="{name}" Publisher="{publisher}" Version="{version}" ProcessorArchitecture="x64"/>
  <Properties>
    <DisplayName>Note Organizer</DisplayName>
    <PublisherDisplayName>{publisher_display}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.26100.0" MaxVersionTested="10.0.26100.0"/>
  </Dependencies>
  <Resources>
    <Resource Language="en-us"/>
  </Resources>
  <Applications>
    <Application Id="NoteOrganizer" Executable="NoteOrganizer.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="Note Organizer" Description="Your notes, kept on your computer."
                          BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png"
                          Square44x44Logo="Assets\\Square44x44Logo.png"/>
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust"/>
  </Capabilities>
</Package>
"""

# The sizes the manifest names; the Store asks for more once there is a listing.
LOGOS = (("StoreLogo.png", 50), ("Square44x44Logo.png", 44), ("Square150x150Logo.png", 150))


def sdk_tool(name):
    """The newest Windows SDK's x64 copy of *name*, or exit saying how to get it."""
    found = sorted(glob.glob(os.path.join(
        r"C:\Program Files (x86)\Windows Kits\10\bin", "*", "x64", name)))
    if not found:
        sys.exit("%s not found: install the Windows SDK (docs/RELEASE_WINDOWS.md)" % name)
    return found[-1]


def app_version():
    with open(os.path.join(ROOT, "note_organizer.py"), encoding="utf-8") as f:
        match = re.search(r'^APP_VERSION = "(\d+)\.(\d+)\.(\d+)"', f.read(), re.M)
    if not match:
        sys.exit("APP_VERSION not found in note_organizer.py")
    return [int(part) for part in match.groups()]


def pack(version, args, makeappx):
    layout = os.path.join(OUT, "layout_" + version)
    if os.path.isdir(layout):
        shutil.rmtree(layout)
    shutil.copytree(DIST, layout)
    os.makedirs(os.path.join(layout, "Assets"))
    icon = Image.open(ICON).convert("RGBA")
    for filename, size in LOGOS:
        icon.resize((size, size), Image.LANCZOS).save(os.path.join(layout, "Assets", filename))
    with open(os.path.join(layout, "AppxManifest.xml"), "w", encoding="utf-8") as f:
        f.write(MANIFEST.format(name=args.name, publisher=args.publisher,
                                publisher_display=args.publisher_display, version=version))
    package = os.path.join(OUT, "NoteOrganizer_%s.msix" % version)
    run = subprocess.run([makeappx, "pack", "/d", layout, "/p", package, "/o"],
                         capture_output=True, text=True, timeout=600)
    shutil.rmtree(layout)
    if run.returncode != 0:
        sys.exit("makeappx failed for %s:\n%s" % (version, (run.stdout + run.stderr)[-2000:]))
    print("packed", package)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", default="NoteOrganizer.Test")
    parser.add_argument("--publisher", default="CN=NoteOrganizerTest")
    parser.add_argument("--publisher-display", default="Alexandra Moldovan")
    parser.add_argument("--update", action="store_true",
                        help="also pack a build one higher, to play an update in Sandbox")
    args = parser.parse_args()
    # The memory ceiling, before makeappx starts (tools/guest.py, a folder up).
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import guest
    guest.settle(heavy=False)
    if not os.path.isfile(os.path.join(DIST, "NoteOrganizer.exe")):
        sys.exit("no build in dist/NoteOrganizer: build the app first")
    if os.path.exists(os.path.join(DIST, "notes_data.json")):
        sys.exit("a notebook lies beside the built exe; it would ship in the package")
    makeappx = sdk_tool("makeappx.exe")
    os.makedirs(OUT, exist_ok=True)
    major, minor, build = app_version()
    versions = ["%d.%d.%d.0" % (major, minor, build)]
    if args.update:
        versions.append("%d.%d.%d.0" % (major, minor, build + 1))
    for version in versions:
        pack(version, args, makeappx)


if __name__ == "__main__":
    main()
