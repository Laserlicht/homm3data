"""
PyInstaller runtime hook for GTK4 GObject-Introspection apps.

Sets GI_TYPELIB_PATH so the bundled typelib files are found at runtime,
and configures GSK_RENDERER for reliable rendering in AppImage environments.
"""
import os
import sys

# PyInstaller sets sys._MEIPASS to the temp extraction directory (onefile)
# or the app directory (onedir). The typelibs are collected into 'gi_typelibs'.
if hasattr(sys, '_MEIPASS'):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(sys.executable)

typelib_dir = os.path.join(base_dir, 'gi_typelibs')

if os.path.isdir(typelib_dir):
    existing = os.environ.get('GI_TYPELIB_PATH', '')
    if existing:
        os.environ['GI_TYPELIB_PATH'] = typelib_dir + os.pathsep + existing
    else:
        os.environ['GI_TYPELIB_PATH'] = typelib_dir

# GTK4 defaults to the NGL/GL renderer (GSK), which may fail in sandboxed
# or AppImage environments where OpenGL context creation is unreliable.
# Fall back to the cairo renderer for maximum portability.
if 'GSK_RENDERER' not in os.environ:
    os.environ['GSK_RENDERER'] = 'cairo'
