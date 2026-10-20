# Windows Release Reference

Reference material for actually publishing the built `.exe` on Windows,
once the app is stable enough for that. Nothing here is decided or in
progress. This file is specifically about building and distributing;
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

## Microsoft Store (MSIX)

The Microsoft Store expects the app packaged as MSIX. MSIX packages use a 4-part version number, `Major.Minor.Build.Revision` (e.g. `1.5.6.0`), with three hard requirements:

- The first part (Major) **cannot be `0`** — which our own rule of staying at `0.x.x` until real launch already satisfies by the time this matters, since we'd be at `1.0.0` or higher.
- The last part (Revision) **must be left as `0`** when building the package — it's reserved for the Store's own use.
- The middle two parts (Minor, Build) must each be an integer between 0 and 65535.

This MSIX package version is separate from, and doesn't need to match, the app's own `APP_VERSION`/`CHANGELOG.md` number — it's a store-specific wrapper version, decided at packaging time, not a replacement for our own scheme.

Source: [Microsoft Learn — App package requirements for MSIX apps](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements)

Three things wait for the listing, when there is one:

- **The privacy policy's address**, which Partner Center asks for: Microsoft requires a policy for
  every Win32 product (Store Policy 10.5.1). It is `PRIVACY_URL` in
  `noteorganizer/core/diagnostics.py`, the site's [privacy policy](PRIVACY.md), which
  **Settings → About** opens as well.
- **The support contact** the listing asks for is the project's own address (the one the
  feedback form forwards to — see [site/README.md](../site/README.md#the-feedback-form)), never a
  personal one.
- **The review button.** `STORE_REVIEW_URL` in `noteorganizer/core/diagnostics.py` is `None`
  until the app has a Store page; set to that page's review link, **Settings → About** shows
  **Rate on the Store** beside Send feedback.

## Alternatives to the Microsoft Store

None of these are decided on — just what exists, for when the choice comes up:

- **Winget** (Windows Package Manager) — command-line install (`winget install ...`) from a manifest submitted to a public repository. No Store review process in the same sense; still expects a MSIX/MSI/EXE installer to point at.
- **Chocolatey** — a long-standing community package manager, similar spirit to Winget.
- **Direct download from our own site/GitHub** — an MSIX package plus a `.appinstaller` file gives users real auto-update support without going through any store at all.
- **GitHub Releases** / **SourceForge** — plain, direct hosting of the built `.exe` (or a zip of `dist/NoteOrganizer/`), no packaging format requirements at all.
- **PortableApps.com** — a curated catalog of no-install, portable software. Worth noting specifically because this app is already a simple folder-based design with no installer and no registry use — a natural fit if that catalog's inclusion criteria are ever worth pursuing.
- **itch.io** — low-friction submission, commonly used by small/indie desktop apps; not particularly notes-app-specific, but a real option.

Source: [Microsoft Learn — Choose a distribution path for your Windows app](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/choose-distribution-path)
