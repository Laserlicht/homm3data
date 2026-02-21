#!/usr/bin/env python3
"""
H3 Data Editor — GTK3 GUI for Heroes of Might and Magic III data files.

Modes:
  - Archive Browser: Browse and manage LOD/PAK archives
  - DEF Editor: View and edit DEF animation frames
  - PCX Converter: Convert between H3 PCX/P32 and common image formats
"""
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, Gio

import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.archive_browser import ArchiveBrowser
from gui.def_editor import DefEditor
from gui.pcx_converter import PcxConverter
from gui.i18n import _


CSS = b"""
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
    background: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}

.mode-header {
    font-size: 11px;
    font-weight: bold;
    padding: 8px 16px 4px 16px;
    color: alpha(@theme_fg_color, 0.6);
}

.app-title {
    font-size: 14px;
    font-weight: bold;
    padding: 12px 16px;
}

.sidebar {
    background: shade(@theme_bg_color, 0.96);
    border-right: 1px solid alpha(@theme_fg_color, 0.1);
}
"""


class MainWindow(Gtk.ApplicationWindow):
    """Main application window with mode-switching sidebar."""

    def __init__(self, app):
        super().__init__(application=app, title="H3 Data Editor")
        self.set_default_size(1200, 750)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Apply CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
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
        sidebar.get_style_context().add_class("sidebar")

        # App title in sidebar
        title_label = Gtk.Label(label=_("H3 Data Editor"))
        title_label.get_style_context().add_class("app-title")
        title_label.set_xalign(0)
        sidebar.pack_start(title_label, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar.pack_start(sep, False, False, 0)

        # Mode header
        mode_label = Gtk.Label(label=_("MODES"))
        mode_label.get_style_context().add_class("mode-header")
        mode_label.set_xalign(0)
        sidebar.pack_start(mode_label, False, False, 0)

        # Mode buttons
        self.mode_buttons = []

        btn_archive = Gtk.RadioButton.new_with_label(None, "📁  " + _("Archive Browser"))
        btn_archive.set_mode(False)
        btn_archive.set_alignment(0, 0.5)
        btn_archive.get_style_context().add_class("sidebar-button")
        btn_archive.connect("toggled", self._on_mode_changed, "archive")
        sidebar.pack_start(btn_archive, False, False, 0)
        self.mode_buttons.append(btn_archive)

        btn_def = Gtk.RadioButton.new_with_label_from_widget(btn_archive, "🎬  " + _("DEF Editor"))
        btn_def.set_mode(False)
        btn_def.set_alignment(0, 0.5)
        btn_def.get_style_context().add_class("sidebar-button")
        btn_def.connect("toggled", self._on_mode_changed, "def")
        sidebar.pack_start(btn_def, False, False, 0)
        self.mode_buttons.append(btn_def)

        btn_pcx = Gtk.RadioButton.new_with_label_from_widget(btn_archive, "🖼  " + _("PCX Converter"))
        btn_pcx.set_mode(False)
        btn_pcx.set_alignment(0, 0.5)
        btn_pcx.get_style_context().add_class("sidebar-button")
        btn_pcx.connect("toggled", self._on_mode_changed, "pcx")
        sidebar.pack_start(btn_pcx, False, False, 0)
        self.mode_buttons.append(btn_pcx)

        # Spacer
        sidebar.pack_start(Gtk.Box(), True, True, 0)

        # Version label
        version_label = Gtk.Label(label=_("homm3data v1.0"))
        version_label.get_style_context().add_class("dim-label")
        version_label.set_margin_bottom(8)
        sidebar.pack_start(version_label, False, False, 0)

        main_box.pack_start(sidebar, False, False, 0)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        main_box.pack_start(sep, False, False, 0)

        # Content stack
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)
        self.content_stack.set_transition_duration(200)

        # Create mode widgets
        self.archive_browser = ArchiveBrowser(self)
        self.def_editor = DefEditor(self)
        self.pcx_converter = PcxConverter(self)

        self.content_stack.add_named(self.archive_browser, "archive")
        self.content_stack.add_named(self.def_editor, "def")
        self.content_stack.add_named(self.pcx_converter, "pcx")

        main_box.pack_start(self.content_stack, True, True, 0)

        self.add(main_box)
        self.show_all()

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
    app = H3DataApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
