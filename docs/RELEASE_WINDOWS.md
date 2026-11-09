# Windows Release Reference

Reference material for publishing the built `.exe` on Windows. The
Microsoft Store is the planned route; the decisions taken for it so far
are dated below, and the alternatives are kept for reference. This file
is specifically about building and distributing;
the app's own version-numbering policy lives in
[`docs/ROADMAP.md`](ROADMAP.md), "Versioning".

## Building the artifact

Everything below distributes the same artifact: the PyInstaller
one-folder build.

```powershell
pip install pyinstaller
pyinstaller --noconfirm NoteOrganizer.spec
```

Build from the spec file rather than passing options on the command
line: `NoteOrganizer.spec` is where the project's build settings live
(windowed mode, the numpy exclusion that saves 28 MB), and building the
script directly would generate a competing spec of its own. The result
lands in `dist/NoteOrganizer/` — `NoteOrganizer.exe` beside the
`_internal` folder it needs; ship the whole folder, never the `.exe`
alone.

### The licenses that ship with it

The build carries other people's software: Python (with Tcl/Tk,
OpenSSL, zlib and the rest of its Windows build), Pillow with its image
libraries, PyInstaller's bootloader and Microsoft's C runtime. Their
licenses travel inside the build as `THIRD_PARTY_NOTICES.txt`, which
**Settings → About → Open-source licenses** opens.

`py tools/make_third_party_notices.py` writes that file from the
installed copies themselves, never by hand. Run it and commit the result
whenever Python, Pillow or PyInstaller is updated on the machine that
builds. You cannot forget: the spec compares the committed file with a
fresh one and stops the build when they differ.

### Updating Pillow

The `.exe` ships the Pillow installed where it is built, and CI tests
the one `requirements.txt` pins. They must be the same, so the spec
stops a build when they are not, and `tools/check_shipped.py` holds the
rest on every run. To move to a new version:

1. Change the pin in `requirements.txt` and in
   `tools/linux-ci/Dockerfile`.
2. Install it: `py -m pip install Pillow==<version>`.
3. Rebuild the Linux image: `py tools/linux_ci.py --build`.
4. `py tools/make_third_party_notices.py`, then the full suite on both
   (`py tools/run_tests.py`, then `py tools/linux_ci.py` -- one at a time),
   then build.

## Microsoft Store (MSIX)

The Microsoft Store expects the app packaged as MSIX. MSIX packages use a 4-part version number, `Major.Minor.Build.Revision` (e.g. `1.5.6.0`), with three hard requirements:

- The first part (Major) **cannot be `0`** — which our own rule of staying at `0.x.x` until real launch already satisfies by the time this matters, since we'd be at `1.0.0` or higher.
- The last part (Revision) **must be left as `0`** when building the package — it's reserved for the Store's own use.
- The middle two parts (Minor, Build) must each be an integer between 0 and 65535.

This MSIX package version is separate from, and doesn't need to match, the app's own `APP_VERSION`/`CHANGELOG.md` number — it's a store-specific wrapper version, decided at packaging time, not a replacement for our own scheme.

Source: [Microsoft Learn — App package requirements for MSIX apps](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements)

### Packing it, and proving it in Windows Sandbox

Two tools in `tools/msix/`, both needing the Windows SDK (its signing tools, the x64 desktop
tools and the App Certification Kit) and, for the proof, Windows Sandbox:

```powershell
py tools/msix/build_msix.py --update    # dist/msix: the package, and one a build higher
py tools/msix/make_sandbox_test.py      # dist/msix/NoteOrganizer-msix-test.wsb
```

Double-clicking the `.wsb` opens a disposable Windows in which `sandbox_test.ps1` signs both
packages with a certificate made there, puts an older `.exe`'s notebook in AppData, and installs,
starts, updates, uninstalls and reinstalls the app; `dist/msix/out/result.txt` says after each
step what the profile's notebook, the package's private copy and AppData hold — and, after each
install, whether the licenses About opens are inside the package — and a message says
when it is done. Nothing touches this machine's certificates or notebooks. The identity is a test
one (`NoteOrganizer.Test`) until Partner Center reserves the Store's, and a Major of `0` is for
Sandbox only. Run on 2026-10-27: the old notebook came in, both notes stayed byte for byte
through the update, the uninstall and the reinstall, the package's private copy held no file,
and AppData was untouched. The sandbox runs without a virtual GPU: started from the Start menu,
it lost its connection on this machine.

### Which Windows

The package asks for **Windows 11, version 24H2 or later**: `MinVersion="10.0.26100.0"` in the
manifest `build_msix.py` writes. Below it Windows does not count the package as applicable, so
the Store does not offer the app there
([TargetDeviceFamily](https://learn.microsoft.com/en-us/uwp/schemas/appxpackage/uapmanifestschema/element-targetdevicefamily));
the Store accepts any Windows 10 or 11 version it supports, given in that attribute
([package requirements](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements#supported-versions)).

The owner's choice, 2026-11-09: what was never tried is not declared. The package had said
Windows 10 version 1809 (`10.0.17763.0`) while it had only ever run on Windows 11; trying it on
Windows 10 needs a virtual machine this project does not have. Windows Sandbox is 24H2, the
oldest version it was proved on. Versions 21H2 to 23H2 no longer get updates on Home and Pro.
Lowering the number later is a new package and a new proof on that Windows, never only an edit.

Four things wait for the listing, when there is one:

- **The privacy policy's address**, which Partner Center asks for: Microsoft requires a policy for
  every Win32 product (Store Policy 10.5.1). It is `PRIVACY_URL` in
  `noteorganizer/core/diagnostics.py`: the [privacy policy](PRIVACY.md), published on Google
  Sites, which **Settings → About** opens as well.
- **The support contact** — optional for an app not on Xbox, given anyway — is the project's own
  address, noteorganizer.app@gmail.com, never a personal one.
- **The website field stays empty.** It is optional, and the project's site on Netlify is kept
  apart from the apps' users (the owner's rule, 2026-10-21; see
  [site/README.md](../site/README.md#kept-apart-from-the-apps)). Phone and postal address are
  optional for an individual developer and not shown to customers; they are left out too.
- **The review button.** `STORE_REVIEW_URL` in `noteorganizer/core/diagnostics.py` is `None`
  until the app has a Store page; set to that page's review link, **Settings → About** shows the
  Feedback card, whose **Write a review** opens it. It is the app's only way in for feedback.
  Answers to reviews stay public: a private reply by email would make the policy's "I answer in
  the store, publicly" untrue.

Two things to prove on the package itself, before the listing goes live:

- **Uninstalling leaves the notes.** The privacy policy says so. The built app keeps its notebook
  in the profile's `Note Organizer` folder, outside AppData, whose writes an MSIX package has
  virtualized into its own folder and deleted with the app — the owner's decision, 2026-10-27,
  replacing that of 2026-10-21 to exclude `%APPDATA%\NoteOrganizer` from virtualization, which
  needed the restricted capability `unvirtualizedResources` and the Store's review of it
  ([why](ARCHITECTURE.md#the-notebook-outside-appdata)). Proved in Windows Sandbox before the
  listing: install, notes written, an update to a newer package, uninstall, reinstall, the notes
  still there; then on a real Store install once more. If it does not hold, the policy's sentence
  changes before anything ships.
- **Markets.** `sites.google.com`, where the policy lives, is blocked in mainland China: untick
  China among the markets, or accept that the policy cannot be opened there.

### The privacy page, at every release

The policy's text is [`docs/PRIVACY.md`](PRIVACY.md); the page the apps and the stores point at
is a copy of it on Google Sites, made by hand, so nothing keeps the two in step but this step
(the owner's rule, 2026-10-21):

1. Before a release is cut, ask whether `docs/PRIVACY.md` changed since the last one, or whether
   the release changes what the apps keep, send or open. If the apps changed, the text changes
   first, with a new "Last updated" date.
2. If the text changed, the owner copies it to the Google Site — from the Markdown preview of
   `docs/PRIVACY.md` — and publishes it before the build goes out.
3. The live page is compared with `docs/PRIVACY.md` (the date line, then each section), and the
   release report says so, even when nothing changed. The one accepted difference is the
   Contents list: its links do not work on Google Sites, so the Site leaves it out or uses the
   Site's own table of contents instead.
4. Once the apps are in the stores, a change to the text also gets a dated line under the
   policy's **What changed**, saying exactly what is different, and the release that brings it
   says so in both stores' release notes, in a sentence or two with the policy's address. Nobody
   should learn of a change only by comparing the page with an older copy (the owner's rule,
   2026-11-08). An earlier version goes to whoever asks for it, from the file's history.

No build ships until `PRIVACY_URL`, opened signed out (in a private window), shows the policy's
text: a Google Site that is missing or not public sends a visitor to Google's sign-in page rather
than answering with an error, and Google Play rejects that. The Site is made under the project's
account, published with **Who can view** set to Public, typed into the Site rather than an
embedded document, and never renamed — its address is built into both apps.

## Alternatives to the Microsoft Store

None of these are decided on — just what exists, for when the choice comes up:

- **Winget** (Windows Package Manager) — command-line install (`winget install ...`) from a manifest submitted to a public repository. No Store review process in the same sense; still expects a MSIX/MSI/EXE installer to point at.
- **Chocolatey** — a long-standing community package manager, similar spirit to Winget.
- **Direct download from our own site/GitHub** — an MSIX package plus a `.appinstaller` file gives users real auto-update support without going through any store at all.
- **GitHub Releases** / **SourceForge** — plain, direct hosting of the built `.exe` (or a zip of `dist/NoteOrganizer/`), no packaging format requirements at all.
- **PortableApps.com** — a curated catalog of no-install, portable software. Worth noting specifically because this app is already a simple folder-based design with no installer and no registry use — a natural fit if that catalog's inclusion criteria are ever worth pursuing.
- **itch.io** — low-friction submission, commonly used by small/indie desktop apps; not particularly notes-app-specific, but a real option.

Source: [Microsoft Learn — Choose a distribution path for your Windows app](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/choose-distribution-path)
