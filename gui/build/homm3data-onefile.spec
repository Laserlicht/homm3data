# -*- mode: python ; coding: utf-8 -*-
import os
import glob
import sys

SPECPATH = os.path.dirname(os.path.abspath(SPEC))

block_cipher = None

def collect_gi_typelibs():
    typelibs = []
    if sys.platform == 'win32':
        paths = [
            '/mingw64/lib/girepository-1.0',
        ]
    else:
        paths = [
            '/usr/lib/girepository-1.0',
            '/usr/lib/x86_64-linux-gnu/girepository-1.0',
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
        'gi.repository.GdkPixbuf',
        'PIL',
        'PIL.Image',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={
        'gi': {
            'module-versions': {
                'Gtk': '4.0',
                'Gdk': '4.0',
            },
        },
    },
    runtime_hooks=[os.path.join(SPECPATH, 'gi_runtime_hook.py')],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='homm3data',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../homm3data.ico',
)
