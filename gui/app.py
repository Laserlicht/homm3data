#!/usr/bin/env python3
"""
H3 Data Editor — GTK4 GUI for Heroes of Might and Magic III data files.

Modes:
  - Archive Browser: Browse and manage LOD/PAK archives
  - DEF Editor: View and edit DEF animation frames
  - PCX Converter: Convert between H3 PCX/P32 and common image formats
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Gio

import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.archive_browser import ArchiveBrowser
from gui.def_editor import DefEditor
from gui.pcx_converter import PcxConverter
from gui.i18n import _


CSS = """
.primary-toolbar {
    padding: 2px;
}

.sidebar-button {
    border-radius: 6px;
    padding: 12px 16px;
    margin: 2px 8px;
    font-size: 13px;
}

.sidebar-button:checked {
    background: @accent_bg_color;
    color: @accent_fg_color;
}

.mode-header {
    font-size: 11px;
    font-weight: bold;
    padding: 8px 16px 4px 16px;
    opacity: 0.6;
}

.app-title {
    font-size: 14px;
    font-weight: bold;
    padding: 12px 16px;
}

.sidebar {
    background: mix(@window_bg_color, @view_bg_color, 0.5);
}
"""


class MainWindow(Gtk.ApplicationWindow):
    """Main application window with mode-switching sidebar."""

    def __init__(self, app):
        super().__init__(application=app, title="H3 Data Editor")
        self.set_default_size(1200, 750)

        # Apply CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self._build_ui()

    def _build_ui(self):
        # Main horizontal layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        # Sidebar
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.set_size_request(200, -1)
        sidebar.add_css_class("sidebar")

        # App title in sidebar
        title_label = Gtk.Label(label=_("H3 Data Editor"))
        title_label.add_css_class("app-title")
        title_label.set_xalign(0)
        sidebar.append(title_label)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar.append(sep)

        # Mode header
        mode_label = Gtk.Label(label=_("MODES"))
        mode_label.add_css_class("mode-header")
        mode_label.set_xalign(0)
        sidebar.append(mode_label)

        # Mode buttons (ToggleButtons acting as radio group)
        self.mode_buttons = []

        btn_archive = Gtk.ToggleButton(label="📁  " + _("Archive Browser"))
        btn_archive.set_halign(Gtk.Align.FILL)
        btn_archive.add_css_class("sidebar-button")
        btn_archive.connect("toggled", self._on_mode_changed, "archive")
        sidebar.append(btn_archive)
        self.mode_buttons.append(btn_archive)

        btn_def = Gtk.ToggleButton(label="🎬  " + _("DEF Editor"))
        btn_def.set_halign(Gtk.Align.FILL)
        btn_def.add_css_class("sidebar-button")
        btn_def.set_group(btn_archive)
        btn_def.connect("toggled", self._on_mode_changed, "def")
        sidebar.append(btn_def)
        self.mode_buttons.append(btn_def)

        btn_pcx = Gtk.ToggleButton(label="🖼  " + _("PCX Converter"))
        btn_pcx.set_halign(Gtk.Align.FILL)
        btn_pcx.add_css_class("sidebar-button")
        btn_pcx.set_group(btn_archive)
        btn_pcx.connect("toggled", self._on_mode_changed, "pcx")
        sidebar.append(btn_pcx)
        self.mode_buttons.append(btn_pcx)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar.append(spacer)

        # Version label
        version_label = Gtk.Label(label=_("homm3data v1.0"))
        version_label.add_css_class("dim-label")
        version_label.set_margin_bottom(8)
        sidebar.append(version_label)

        sidebar.set_hexpand(False)
        main_box.append(sidebar)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(sep)

        # Content stack
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)
        self.content_stack.set_transition_duration(200)
        self.content_stack.set_hexpand(True)
        self.content_stack.set_vexpand(True)

        # Create mode widgets
        self.archive_browser = ArchiveBrowser(self)
        self.def_editor = DefEditor(self)
        self.pcx_converter = PcxConverter(self)

        self.content_stack.add_named(self.archive_browser, "archive")
        self.content_stack.add_named(self.def_editor, "def")
        self.content_stack.add_named(self.pcx_converter, "pcx")

        main_box.append(self.content_stack)

        self.set_child(main_box)

        # Default mode
        btn_archive.set_active(True)
        self.content_stack.set_visible_child_name("archive")

    def _on_mode_changed(self, button, mode):
        if button.get_active():
            self.content_stack.set_visible_child_name(mode)


class H3DataApp(Gtk.Application):
    """Main GTK application."""

    def __init__(self):
        super().__init__(
            application_id="com.homm3data.editor",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

    def do_activate(self):
        win = MainWindow(self)
        win.present()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)


def main():
    try:
        import gi
        gi.require_version('Gtk', '4.0')
    except (ImportError, ValueError):
        print("Error: PyGObject (GTK4) not found.")
        print("Please install it with: pip install '.[gui]'")
        sys.exit(1)

    app = H3DataApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
