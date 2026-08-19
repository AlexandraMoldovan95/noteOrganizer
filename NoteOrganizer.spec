# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['note_organizer.py'],
    pathex=[],
    binaries=[],
    datas=[],
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
