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
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm NoteOrganizer.spec
```

The build needs the pinned Pillow (the spec stops when another one is installed) and Python
installed with its documentation: the third-party notices are made from its `license.html`.

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

`build_msix.py` packs `APP_VERSION`'s three numbers with a last `0` (0.100.524 is 0.100.524.0) and refuses an `.exe` of another version, so the package's version is always the app's own (`--update` packs a second one, its last number before the `0` one higher, for the Sandbox's update test only).

Source: [Microsoft Learn — App package requirements for MSIX apps](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements)

### Packing it, and proving it in Windows Sandbox

Two tools in `tools/msix/`, both needing the Windows SDK (its signing tools, the x64 desktop
tools and the App Certification Kit) and, for the proof, Windows Sandbox:

```powershell
py tools/msix/build_msix.py --update    # dist/msix: the package, and one a build higher
py tools/msix/make_sandbox_test.py      # dist/msix: a .wsb file for each of three proofs
```

`make_sandbox_test.py` refuses while `dist/msix` holds any package but that pair: the first proof
installs the lowest package there and updates to the highest, and with an older release's
packages left beside it would have played an update from that one.

Double-clicking a `.wsb` opens a disposable Windows whose script signs the packages with a
certificate made there. Only `dist/msix/out` leaves it; a message says when it is done, and
closing the window throws the rest away. Nothing touches this machine's certificates or
notebooks. The package carries the Store's identity, reserved in Partner Center on 2026-11-25
and written in `build_msix.py` as its default: `AlexandraMoldovan.NoteOrganizer`, published by
`CN=64AA2E20-9F7F-4AD8-B932-ABAFCE65CBA2` as Alexandra Moldovan
([the listing](STORE_LISTING.md#product-identity)). Before that it was a test one,
`NoteOrganizer.Test`, which `--name` and `--publisher` still give. The sandbox scripts read the
identity from the package itself, so the package the Store receives is the one signed and proved
(they read it since 2026-11-13; the runs below up to 0.103.558 are of the test identity).
A Major of `0` is for Sandbox only. The sandboxes run without a network, and without
a virtual GPU: started from the Start menu, one lost its connection on this machine.

| `.wsb` | What it proves | Last run |
|---|---|---|
| `NoteOrganizer-msix-test.wsb` | The package's life. An older `.exe`'s notebook in AppData; install, start, update, uninstall, reinstall; after each step, what the profile's notebook, the package's private copy and AppData hold, and whether the licenses About opens are inside the package (`out/result.txt`). | 2026-10-27, 2026-11-09 for 0.100.512 and 0.100.513, 2026-11-12 for 0.100.524, 2026-11-21 for 0.101.540 (updated to 0.101.541), 2026-11-22 for 0.101.542 (updated to 0.101.543), 2026-11-23 for 0.102.556 (updated to 0.102.557), 2026-11-25 for 1.0.0, the first with the Store's identity (updated to 1.0.1), and 2026-11-27 for 1.0.1, asking for Windows 11 21H2 (updated to 1.0.2): the old notebook came in, both notes byte for byte through the update, the uninstall and the reinstall; the private copy held no file; AppData untouched. |
| `NoteOrganizer-msix-look.wsb` | The package to ship on a Windows with 2 GB of memory, started in each of the eight themes on a notebook of 40 notes: how soon the window shows, whether it lies inside the work area, a photo of it, the app's memory, a close as the X closes it, the theme kept, no crash log (`out/look/`). | 2026-11-09 for 0.100.513, 2026-11-12 for 0.100.524, 2026-11-21 for 0.101.540, 2026-11-22 for 0.101.542, 2026-11-23 for 0.102.556, 2026-11-25 for 1.0.0 and 2026-11-27 for 1.0.1, at the sandbox's 150%: all eight themes; the window in 1 s (2 s at 0.101.540's first start) and inside the work area every time; the app 67 to 68 MB (37 to 38 MB its own), with 330 to 470 MB of the sandbox's left (223 to 303 MB for 0.101.540, 64 to 290 MB for 0.101.542, the 64 at one theme's start, 251 to 280 MB for 0.102.556, 290 to 349 MB for 1.0.0, 256 to 343 MB for 1.0.1). For 0.100.512 two of the eight had opened with their foot under the taskbar ([why](ISSUES_LOG.md#wave-5-the-window-that-opened-under-the-taskbar)). |
| `NoteOrganizer-msix-wack.wsb` | The Windows App Certification Kit, as Partner Center runs it (`out/wack/`). | 2026-11-09 for 0.100.512, 2026-11-10 for 0.100.513, 2026-11-12 for 0.100.524, 2026-11-21 for 0.101.540, 2026-11-22 for 0.101.542, 2026-11-23 for 0.102.556, 2026-11-25 for 1.0.0 and 2026-11-27 for 1.0.1, the last two with the Store's identity: overall WARNING each time, below. |

#### The certification kit (WACK)

WACK installs the package it tests and starts the app, which on this computer would open the
owner's notebook, and it needs a test certificate trusted; so it runs only in the sandbox. The kit
alone does not run there. `make_sandbox_test.py` maps in its test engine (TAEF, the SDK's
`Testing` folder), Windows' metadata and API contracts (`UnionMetadata`, `References`,
`Platforms`), and reads the kit's COM classes and type libraries out of this computer's registry
with `reg export`, for the sandbox to import. A run without each of them stopped at it.

Run on 2026-11-09 for 0.100.512, on 2026-11-10 for 0.100.513, on 2026-11-12 for 0.100.524, on
2026-11-21 for 0.101.540, on 2026-11-22 for 0.101.542, on 2026-11-23 for 0.102.556, on 2026-11-25 for 1.0.0 and on 2026-11-27 for 1.0.1, the result was **WARNING** each time, which is not a failure: of 24 tests, 22 passed, and two did not.

- **Blocked executables** failed. It is an optional test, and optional tests "are informational
  only and will not be used to evaluate your app during Microsoft Store onboarding"
  ([Desktop Bridge app tests](https://learn.microsoft.com/en-us/windows/uwp/debug-test-perf/windows-desktop-bridge-app-tests)).
  It found `CreateProcessW` in `NoteOrganizer.exe` (PyInstaller's launcher), in Python and in
  Tcl, and `ShellExecuteW` in Python; and the names of blocked programs (`cmd`, `reg`, `cdb` and
  others) in Tcl's scripts and, as chance letters, inside binary files, the launcher among them.
  The app starts no program by name: it opens a file or a folder with the program Windows gives
  it, and the privacy policy in the browser. The same page says a flagged
  file that is part of the app may be ignored.
- **DPI awareness** gave a warning: the `.exe` declares no per-monitor awareness. The app declares
  system awareness itself as it starts, and only while Sharp text is on. Per-monitor awareness needs
  redraws Tk cannot do ([why](ARCHITECTURE.md#sharp-on-a-scaled-screen-every-size-is-given-at-100)),
  and a declaration inside the `.exe` would take the setting away.

### Which Windows

The package asks for **Windows 11, version 21H2 or later**, every Windows 11:
`MinVersion="10.0.22000.0"` in the manifest `build_msix.py` writes. Below it Windows does not
count the package as applicable, so the Store does not offer the app there
([TargetDeviceFamily](https://learn.microsoft.com/en-us/uwp/schemas/appxpackage/uapmanifestschema/element-targetdevicefamily));
the Store accepts any Windows 10 or 11 version it supports, given in that attribute
([package requirements](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements#supported-versions)).

**How it came to this.** Until 1.0.1 the package asked for 24H2 (`10.0.26100.0`), the owner's
choice of 2026-11-09: what was never tried is not declared. It had said Windows 10 version 1809
(`10.0.17763.0`) while it had only ever run on Windows 11, and Windows Sandbox, where the package
is proved, is 24H2. On 2026-11-27, just after 1.0.0 went public, a person on Windows 11 23H2
was refused by the Store ("doesn't meet minimum requirements"): people keep older versions of
Windows, and not all of them update. The owner's choice then was every Windows 11, and no
Windows 10 ([why not](ROADMAP.md#explicitly-not-planned-right-now)).

**What stands behind it**, since 21H2 to 23H2 can no longer be downloaded to try:

- The whole suite runs in CI on Windows Server 2022 as well (build 20348, older than any
  Windows 11; `.github/workflows/tests.yml`), beside the newest Windows and Linux.
- The Sandbox proofs run on 24H2, and 1.0.0 was installed from the Store on 26H2 and updated
  there to 1.0.1 on 2026-11-27, every note kept.
- On 2026-11-27 the PC on Windows 11 23H2 that 1.0.0 had been refused on installed 1.0.1 from
  the Store and opened it on its welcome note.
- The app uses nothing those versions lack: the title bar's colours are Windows 11's own and
  fail silently elsewhere, the call that keeps text sharp is Windows 8.1's, the spelling check
  Windows 8's.

A Windows without the Microsoft Store (an LTSC edition, many modified copies) cannot install the
app from it whatever its version; a download outside the Store is a separate decision, not
taken.

Changing the number again is a new package and a new proof, never only an edit.

### What the listing needs

Every value and text typed into Partner Center, ready to paste, is in
[STORE_LISTING.md](STORE_LISTING.md); this section says why some of them are as they are.

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
- **The review button.** `STORE_REVIEW_URL` in `noteorganizer/core/diagnostics.py` holds the
  Store page's review link since 1.0.0 (`ms-windows-store://review/?ProductId=9NBS2548QTXF`), so
  **Settings → About** shows the Feedback card, whose **Write a review** opens it; set to `None`,
  the card is gone. It is the app's only way in for feedback.
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

### Rolling out, and stopping a release

Written down before the first release, so that a bad one is met with steps rather than a
scramble (2026-11-12).

1. **The first release goes to a few people first.** Partner Center can publish to a private
   audience before the listing is public, and the package installed from the Store is the one
   worth trying: the Store signs it again, so the Sandbox's package is close to it, not the same.
2. **An update goes out gradually.** Partner Center's gradual package rollout offers it to a
   share of people first; the share grows only after a few quiet days.
3. **When something is wrong, the rollout is halted first**, in Partner Center, before anything
   is fixed: nobody new receives the package while the fix is made. An installed version cannot
   be taken back; the way out is a newer version.
4. **The fix is a release like any other**: its own branch, the version a patch higher (ROADMAP,
   "Versioning"), the whole suite on Windows and Linux, the `.exe` and the package built again,
   the Sandbox proofs, then the submission. A fix is never made in the package by hand.
5. **What a person sees is read before anything is guessed**: the Store's reviews, Partner
   Center's health report, and `crash_log.txt` in the notebook's folder, which a person can send
   when asked (the app sends nothing itself).

## Alternatives to the Microsoft Store

None of these are decided on — just what exists, for when the choice comes up:

- **Winget** (Windows Package Manager) — command-line install (`winget install ...`) from a manifest submitted to a public repository. No Store review process in the same sense; still expects a MSIX/MSI/EXE installer to point at.
- **Chocolatey** — a long-standing community package manager, similar spirit to Winget.
- **Direct download from our own site/GitHub** — an MSIX package plus a `.appinstaller` file gives users real auto-update support without going through any store at all.
- **GitHub Releases** / **SourceForge** — plain, direct hosting of the built `.exe` (or a zip of `dist/NoteOrganizer/`), no packaging format requirements at all.
- **PortableApps.com** — a curated catalog of no-install, portable software. The app needs no installer and no registry entries, but it is not portable yet: the built `.exe` keeps its notebook in the profile's `Note Organizer` folder (beside itself only when the profile cannot be written), so a portable edition would first need the notebook kept beside the `.exe` by choice.
- **itch.io** — low-friction submission, commonly used by small/indie desktop apps; not particularly notes-app-specific, but a real option.

Source: [Microsoft Learn — Choose a distribution path for your Windows app](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/choose-distribution-path)
