"""Write the Windows Sandbox file that proves the package keeps the notes.

    py tools/msix/build_msix.py --update
    py tools/msix/make_sandbox_test.py

Then double-click dist/msix/NoteOrganizer-msix-test.wsb. Inside the
sandbox, sandbox_test.ps1 signs the two packages with a certificate made
there, puts an older exe's notebook in AppData, and installs, starts,
updates, uninstalls and reinstalls the app, writing after each step what
the profile's notebook, the package's private copy and AppData hold, to
dist/msix/out/result.txt. A message says when it is done; closing the
sandbox throws everything in it away. The sandbox runs without a virtual
GPU, which made it lose its connection on this machine, and without a
network, which an offline app does not need.
"""
import glob
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "dist", "msix")
HERE = os.path.dirname(os.path.abspath(__file__))

WSB = """<Configuration>
  <vGPU>Disable</vGPU>
  <Networking>Disable</Networking>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>{packages}</HostFolder>
      <SandboxFolder>C:\\pkg</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{sdk}</HostFolder>
      <SandboxFolder>C:\\sdk</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{out}</HostFolder>
      <SandboxFolder>C:\\out</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\pkg\\sandbox_test.ps1</Command>
  </LogonCommand>
</Configuration>
"""


def main():
    packages = sorted(glob.glob(os.path.join(OUT, "NoteOrganizer_*.msix")))
    if len(packages) < 2:
        sys.exit("two packages wanted in dist/msix: run build_msix.py --update first")
    signtools = sorted(glob.glob(os.path.join(
        r"C:\Program Files (x86)\Windows Kits\10\bin", "*", "x64", "signtool.exe")))
    if not signtools:
        sys.exit("signtool.exe not found: install the Windows SDK (docs/RELEASE_WINDOWS.md)")
    shutil.copy2(os.path.join(HERE, "sandbox_test.ps1"), OUT)
    results = os.path.join(OUT, "out")
    os.makedirs(results, exist_ok=True)
    wsb = os.path.join(OUT, "NoteOrganizer-msix-test.wsb")
    with open(wsb, "w", encoding="utf-8") as f:
        f.write(WSB.format(packages=OUT, sdk=os.path.dirname(signtools[-1]), out=results))
    print("double-click:", wsb)
    print("the result lands in:", os.path.join(results, "result.txt"))


if __name__ == "__main__":
    main()
