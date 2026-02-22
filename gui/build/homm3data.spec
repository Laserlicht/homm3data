# -*- mode: python ; coding: utf-8 -*-
import os
import glob

block_cipher = None

def collect_gi_typelibs():
    typelibs = []
    paths = [
        '/usr/lib/girepository-1.0',
        '/usr/lib64/girepository-1.0',
        '/usr/local/lib/girepository-1.0',
    ]
    for path in paths:
        if os.path.exists(path):
            for f in glob.glob(os.path.join(path, '*.typelib')):
                typelibs.append((f, 'gi_typelibs'))
    return typelibs

gi_datas = collect_gi_typelibs()

a = Analysis(
    ['../app.py'],
    pathex=['../..'],
    binaries=[],
    datas=[
        ('../homm3data.png', '.'),
    ] + gi_datas,
    hiddenimports=[
        'gi',
        'gi.repository.Gtk',
        'gi.repository.Gdk',
        'gi.repository.Gio',
        'gi.repository.GLib',
        'gi.repository.GObject',
        'gi.repository.Pango',
        'gi.repository.PangoCairo',
        'gi.repository.cairo',
        'PIL',
        'PIL.Image',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='homm3data',
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='homm3data',
)
