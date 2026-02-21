"""
DEF editor mode for viewing and editing DEF animation frames.
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio
from PIL import Image
from io import BytesIO
import os

from homm3data import deffile
from gui.utils import pil_to_pixbuf, scale_pixbuf_fit
from gui.i18n import _


class DefEditor(Gtk.Box):
    """
    DEF file editor widget.
    Shows animation groups and frames, allows viewing and editing.
    """

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent_window = parent_window
        self.def_file = None
        self.def_path = None
        self.current_group = None
        self.current_frame = None
        self.zoom_level = 1.0
        self._animation_running = False
        self._animation_timeout_id = None
        self._animation_fps = 10
        self._build_ui()

    def _build_ui(self):
        # Toolbar (using Gtk.Box with Buttons)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        toolbar.add_css_class("primary-toolbar")

        btn_open = self._make_toolbar_button("document-open", _("Open"), self._on_open)
        toolbar.append(btn_open)

        btn_save = self._make_toolbar_button("document-save", _("Save"), self._on_save)
        toolbar.append(btn_save)

        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        btn_import = self._make_toolbar_button("insert-image", _("Import Frame"), self._on_import_frame)
        toolbar.append(btn_import)

        btn_export = self._make_toolbar_button("document-save-as", _("Export Frame"), self._on_export_frame)
        toolbar.append(btn_export)

        btn_remove = self._make_toolbar_button("list-remove", _("Remove"), self._on_remove_frame)
        toolbar.append(btn_remove)

        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        btn_new = self._make_toolbar_button("document-new", _("New DEF"), self._on_new_def)
        toolbar.append(btn_new)

        self.append(toolbar)

        # Main layout
        main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_paned.set_position(200)
        main_paned.set_vexpand(True)

        # Left panel: groups + frames list
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Info section
        info_frame = Gtk.Frame(label=_("Info"))
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_margin_start(8)
        info_box.set_margin_end(8)
        info_box.set_margin_top(4)
        info_box.set_margin_bottom(4)
        self.info_type = Gtk.Label(label=_("Type:") + " —")
        self.info_type.set_xalign(0)
        self.info_size = Gtk.Label(label=_("Size:") + " —")
        self.info_size.set_xalign(0)
        self.info_groups = Gtk.Label(label=_("Groups:") + " —")
        self.info_groups.set_xalign(0)
        info_box.append(self.info_type)
        info_box.append(self.info_size)
        info_box.append(self.info_groups)
        info_frame.set_child(info_box)
        left_box.append(info_frame)

        # Group selector
        group_label = Gtk.Label(label=_("Group:"))
        group_label.set_xalign(0)
        left_box.append(group_label)

        self.group_combo = Gtk.ComboBoxText()
        self.group_combo.connect("changed", self._on_group_changed)
        left_box.append(self.group_combo)

        # Frame list
        frame_label = Gtk.Label(label=_("Frames:"))
        frame_label.set_xalign(0)
        left_box.append(frame_label)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        self.frame_store = Gtk.ListStore(int, str, str)  # id, name, size
        self.frame_tree = Gtk.TreeView(model=self.frame_store)
        self.frame_tree.get_selection().connect("changed", self._on_frame_selected)

        col_id = Gtk.TreeViewColumn(_("Nr"), Gtk.CellRendererText(), text=0)
        col_id.set_sort_column_id(0)
        self.frame_tree.append_column(col_id)

        col_name = Gtk.TreeViewColumn(_("Name"), Gtk.CellRendererText(), text=1)
        col_name.set_sort_column_id(1)
        col_name.set_expand(True)
        self.frame_tree.append_column(col_name)

        col_size = Gtk.TreeViewColumn(_("Size"), Gtk.CellRendererText(), text=2)
        self.frame_tree.append_column(col_size)

        scrolled.set_child(self.frame_tree)
        left_box.append(scrolled)

        main_paned.set_start_child(left_box)
        main_paned.set_resize_start_child(False)
        main_paned.set_shrink_start_child(False)

        # Right panel: frame preview
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Layer selector
        layer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        layer_box.set_margin_start(8)
        layer_box.set_margin_top(4)

        layer_label = Gtk.Label(label=_("Layer:"))
        layer_box.append(layer_label)

        self.layer_combo = Gtk.ComboBoxText()
        self.layer_combo.append_text(_("Combined"))
        self.layer_combo.append_text(_("Normal"))
        self.layer_combo.append_text(_("Shadow"))
        self.layer_combo.append_text(_("Overlay"))
        self.layer_combo.set_active(0)
        self.layer_combo.connect("changed", self._on_layer_changed)
        layer_box.append(self.layer_combo)

        # Zoom controls
        zoom_label = Gtk.Label(label="  " + _("Zoom:"))
        layer_box.append(zoom_label)

        btn_zoom_out = Gtk.Button(label="−")
        btn_zoom_out.connect("clicked", self._on_zoom_out)
        layer_box.append(btn_zoom_out)

        self.zoom_label = Gtk.Label(label="100%")
        layer_box.append(self.zoom_label)

        btn_zoom_in = Gtk.Button(label="+")
        btn_zoom_in.connect("clicked", self._on_zoom_in)
        layer_box.append(btn_zoom_in)

        btn_zoom_fit = Gtk.Button(label=_("Fit"))
        btn_zoom_fit.connect("clicked", self._on_zoom_fit)
        layer_box.append(btn_zoom_fit)

        right_box.append(layer_box)

        # Animation controls
        anim_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        anim_box.set_margin_start(8)

        self.btn_play = Gtk.Button(label="▶ " + _("Play"))
        self.btn_play.connect("clicked", self._on_toggle_animation)
        anim_box.append(self.btn_play)

        fps_label = Gtk.Label(label=_("FPS:"))
        anim_box.append(fps_label)

        self.fps_spin = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.fps_spin.set_value(10)
        self.fps_spin.connect("value-changed", self._on_fps_changed)
        anim_box.append(self.fps_spin)

        right_box.append(anim_box)

        # Image preview with scrolling
        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        preview_scroll.set_vexpand(True)

        # Drawing area for checkerboard + image
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_draw_func(self._on_draw)
        preview_scroll.set_child(self.drawing_area)

        right_box.append(preview_scroll)

        # Frame info
        self.frame_info = Gtk.Label(label="")
        self.frame_info.set_xalign(0)
        self.frame_info.set_margin_start(8)
        self.frame_info.set_margin_bottom(4)
        right_box.append(self.frame_info)

        main_paned.set_end_child(right_box)
        main_paned.set_resize_end_child(True)
        main_paned.set_shrink_end_child(False)

        self.append(main_paned)

        self._current_pixbuf = None

    def _make_toolbar_button(self, icon_name, label, callback):
        """Create a toolbar-style button with icon and label."""
        btn = Gtk.Button()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        box.append(icon)
        lbl = Gtk.Label(label=label)
        box.append(lbl)
        btn.set_child(box)
        btn.connect("clicked", callback)
        return btn

    def _on_draw(self, area, cr, width, height):
        """Draw checkerboard background and image."""
        if self._current_pixbuf is None:
            return

        pw = self._current_pixbuf.get_width()
        ph = self._current_pixbuf.get_height()

        # Set minimum size for drawing area
        area.set_size_request(max(pw, width), max(ph, height))

        # Center the image
        x = max(0, (width - pw) // 2)
        y = max(0, (height - ph) // 2)

        # Draw checkerboard behind image
        cell = 8
        for cy in range(y, y + ph, cell):
            for cx in range(x, x + pw, cell):
                if ((cx // cell) + (cy // cell)) % 2 == 0:
                    cr.set_source_rgb(0.78, 0.78, 0.78)
                else:
                    cr.set_source_rgb(1.0, 1.0, 1.0)
                cr.rectangle(cx, cy, min(cell, x + pw - cx), min(cell, y + ph - cy))
                cr.fill()

        # Draw the image
        Gdk.cairo_set_source_pixbuf(cr, self._current_pixbuf, x, y)
        cr.paint()

    def _load_def(self, filepath_or_data):
        """Load a DEF file from path or bytes."""
        try:
            if isinstance(filepath_or_data, str):
                self.def_path = filepath_or_data
                f = open(filepath_or_data, "rb")
                self.def_file = deffile.DefFile(f)
            elif isinstance(filepath_or_data, bytes):
                self.def_file = deffile.DefFile(BytesIO(filepath_or_data))
                self.def_path = None
            else:
                self.def_file = deffile.DefFile(filepath_or_data)
                self.def_path = None

            self._refresh_ui()
        except Exception as e:
            self._show_message(f"Fehler beim Laden: {str(e)}")

    def _refresh_ui(self):
        """Refresh UI from current DEF file."""
        if self.def_file is None:
            return

        # Update info
        try:
            type_name = self.def_file.get_type().name
        except (AttributeError, ValueError):
            type_name = "Unbekannt"

        w, h = self.def_file.get_size()
        groups = self.def_file.get_groups()

        self.info_type.set_text(f"Typ: {type_name}")
        self.info_size.set_text(f"Größe: {w}×{h}")
        self.info_groups.set_text(f"Gruppen: {len(groups)}")

        # Update group combo
        self.group_combo.remove_all()
        for g in groups:
            fc = self.def_file.get_frame_count(g)
            self.group_combo.append_text(f"Gruppe {g} ({fc} Frames)")

        if groups:
            self.group_combo.set_active(0)

    def _on_group_changed(self, combo):
        """Handle group selection change."""
        idx = combo.get_active()
        if idx < 0 or self.def_file is None:
            return

        groups = self.def_file.get_groups()
        if idx < len(groups):
            self.current_group = groups[idx]
            self._refresh_frame_list()

    def _refresh_frame_list(self):
        """Refresh frame list for current group."""
        self.frame_store.clear()
        if self.def_file is None or self.current_group is None:
            return

        count = self.def_file.get_frame_count(self.current_group)
        for i in range(count):
            name = self.def_file.get_image_name(self.current_group, i) or f"frame_{i}"
            raw = self.def_file.get_raw_data()
            size_str = ""
            for d in raw:
                if d["group_id"] == self.current_group and d["image_id"] == i:
                    w = d["image"].get("width", "?")
                    h = d["image"].get("height", "?")
                    size_str = f"{w}×{h}"
                    break
            self.frame_store.append([i, name, size_str])

        # Select first frame
        if count > 0:
            self.frame_tree.get_selection().select_path(Gtk.TreePath(0))

    def _on_frame_selected(self, selection):
        """Handle frame selection."""
        model, iter_ = selection.get_selected()
        if iter_ is None:
            return

        frame_id = model.get_value(iter_, 0)
        self.current_frame = frame_id
        self._update_preview()

    def _get_layer_name(self):
        """Get the current layer mode string."""
        idx = self.layer_combo.get_active()
        return ["combined", "normal", "shadow", "overlay"][idx]

    def _update_preview(self):
        """Update the frame preview."""
        if self.def_file is None or self.current_group is None or self.current_frame is None:
            self._current_pixbuf = None
            self.drawing_area.queue_draw()
            return

        try:
            layer = self._get_layer_name()
            img = self.def_file.read_image(
                how=layer,
                group_id=self.current_group,
                image_id=self.current_frame
            )

            if img is None:
                self.frame_info.set_text("Keine Daten für diese Ebene")
                self._current_pixbuf = None
            else:
                pixbuf = pil_to_pixbuf(img)
                if self.zoom_level != 1.0:
                    w = max(int(pixbuf.get_width() * self.zoom_level), 1)
                    h = max(int(pixbuf.get_height() * self.zoom_level), 1)
                    pixbuf = pixbuf.scale_simple(w, h, GdkPixbuf.InterpType.NEAREST)
                self._current_pixbuf = pixbuf
                self.frame_info.set_text(
                    f"Frame {self.current_frame} | {img.width}×{img.height} | "
                    f"Zoom: {int(self.zoom_level * 100)}%"
                )

            self.drawing_area.queue_draw()
        except Exception as e:
            self.frame_info.set_text(f"Fehler: {str(e)}")

    def _on_layer_changed(self, combo):
        self._update_preview()

    def _on_zoom_in(self, button):
        self.zoom_level = min(self.zoom_level * 1.5, 16.0)
        self.zoom_label.set_text(f"{int(self.zoom_level * 100)}%")
        self._update_preview()

    def _on_zoom_out(self, button):
        self.zoom_level = max(self.zoom_level / 1.5, 0.1)
        self.zoom_label.set_text(f"{int(self.zoom_level * 100)}%")
        self._update_preview()

    def _on_zoom_fit(self, button):
        self.zoom_level = 1.0
        self.zoom_label.set_text("100%")
        self._update_preview()

    def _on_fps_changed(self, spin):
        self._animation_fps = int(spin.get_value())
        if self._animation_running:
            self._stop_animation()
            self._start_animation()

    def _on_toggle_animation(self, button):
        if self._animation_running:
            self._stop_animation()
        else:
            self._start_animation()

    def _start_animation(self):
        if self.def_file is None or self.current_group is None:
            return
        self._animation_running = True
        self.btn_play.set_label("⏹ " + _("Stop"))
        interval = max(int(1000 / self._animation_fps), 16)
        self._animation_timeout_id = GLib.timeout_add(interval, self._animation_tick)

    def _stop_animation(self):
        self._animation_running = False
        self.btn_play.set_label("▶ " + _("Play"))
        if self._animation_timeout_id:
            GLib.source_remove(self._animation_timeout_id)
            self._animation_timeout_id = None

    def _animation_tick(self):
        if not self._animation_running or self.def_file is None:
            return False

        count = self.def_file.get_frame_count(self.current_group)
        if count == 0:
            return False

        next_frame = ((self.current_frame or 0) + 1) % count
        self.frame_tree.get_selection().select_path(Gtk.TreePath(next_frame))
        return True

    def _on_open(self, button):
        """Open a DEF file."""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Open DEF File"))

        filter_def = Gtk.FileFilter()
        filter_def.set_name(_("DEF Files"))
        filter_def.add_pattern("*.def")
        filter_def.add_pattern("*.DEF")
        filter_def.add_pattern("*.d32")
        filter_def.add_pattern("*.D32")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_def)
        dialog.set_filters(filters)

        dialog.open(self.parent_window, None, self._on_open_finish)

    def _on_open_finish(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
            if gfile:
                filepath = gfile.get_path()
                self._load_def(filepath)
                self.parent_window.set_title(f"H3 Data Editor — {os.path.basename(filepath)}")
        except GLib.Error:
            pass

    def _on_save(self, button):
        """Save the DEF file."""
        if self.def_file is None:
            return

        if self.def_path:
            try:
                self.def_file.save(self.def_path)
                self._show_message(_("Saved: ") + self.def_path, is_error=False)
            except Exception as e:
                self._show_message(_("Error saving: ") + str(e))
        else:
            self._on_save_as()

    def _on_save_as(self):
        """Save as dialog."""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Save DEF As"))
        dialog.set_initial_name("sprite.def")
        dialog.save(self.parent_window, None, self._on_save_as_finish)

    def _on_save_as_finish(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
            if gfile:
                filepath = gfile.get_path()
                self.def_file.save(filepath)
                self.def_path = filepath
        except GLib.Error:
            pass
        except Exception as e:
            self._show_message(f"Fehler: {str(e)}")

    def _on_new_def(self, button):
        """Create a new empty DEF — using a custom dialog window."""
        dialog = Gtk.Window(title=_("Create New DEF"))
        dialog.set_transient_for(self.parent_window)
        dialog.set_modal(True)
        dialog.set_default_size(300, 200)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(8)
        content.set_margin_bottom(8)

        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(4)

        grid.attach(Gtk.Label(label=_("Type:")), 0, 0, 1, 1)
        type_combo = Gtk.ComboBoxText()
        for t in deffile.DefFile.FileType:
            type_combo.append_text(t.name)
        type_combo.set_active(1)  # SPRITE
        grid.attach(type_combo, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Width:")), 0, 1, 1, 1)
        width_spin = Gtk.SpinButton.new_with_range(1, 4096, 1)
        width_spin.set_value(32)
        grid.attach(width_spin, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("Height:")), 0, 2, 1, 1)
        height_spin = Gtk.SpinButton.new_with_range(1, 4096, 1)
        height_spin.set_value(32)
        grid.attach(height_spin, 1, 2, 1, 1)

        content.append(grid)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        btn_cancel = Gtk.Button(label=_("Cancel"))
        btn_cancel.connect("clicked", lambda *_: dialog.close())
        btn_box.append(btn_cancel)

        btn_ok = Gtk.Button(label=_("OK"))
        btn_ok.add_css_class("suggested-action")

        def on_ok(*_):
            type_idx = type_combo.get_active()
            w = int(width_spin.get_value())
            h = int(height_spin.get_value())
            file_type = list(deffile.DefFile.FileType)[type_idx]
            dialog.close()

            self.def_file = deffile.DefFile.create(file_type=file_type, width=w, height=h)
            self.def_path = None
            self.parent_window.set_title("H3 Data Editor — Neues DEF")
            self._refresh_ui()

        btn_ok.connect("clicked", on_ok)
        btn_box.append(btn_ok)

        content.append(btn_box)
        dialog.set_child(content)
        dialog.present()

    def _on_import_frame(self, button):
        """Import an image as a new frame."""
        if self.def_file is None:
            self._show_message(_("Please load or create a DEF first."))
            return

        dialog = Gtk.FileDialog()
        dialog.set_title(_("Import Frame"))

        img_filter = Gtk.FileFilter()
        img_filter.set_name(_("Image Files"))
        img_filter.add_pattern("*.png")
        img_filter.add_pattern("*.bmp")
        img_filter.add_pattern("*.jpg")
        img_filter.add_pattern("*.jpeg")
        img_filter.add_pattern("*.gif")
        img_filter.add_pattern("*.tiff")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(img_filter)
        dialog.set_filters(filters)

        dialog.open_multiple(self.parent_window, None, self._on_import_finish)

    def _on_import_finish(self, dialog, result):
        try:
            gfiles = dialog.open_multiple_finish(result)
            if gfiles is None:
                return

            group = self.current_group if self.current_group is not None else 0
            start_id = self.def_file.get_frame_count(group) if group in self.def_file.get_groups() else 0

            for i in range(gfiles.get_n_items()):
                gfile = gfiles.get_item(i)
                filepath = gfile.get_path()
                try:
                    img = Image.open(filepath)
                    name = os.path.splitext(os.path.basename(filepath))[0][:12]
                    self.def_file.set_image(group, start_id + i, img, name=name)
                except Exception as e:
                    self._show_message(_("Error importing ") + filepath + ": " + str(e))

            self._refresh_ui()
            # Re-select current group
            groups = self.def_file.get_groups()
            if group in groups:
                self.group_combo.set_active(groups.index(group))
        except GLib.Error:
            pass

    def _on_export_frame(self, button):
        """Export current frame as PNG."""
        if self.def_file is None or self.current_group is None or self.current_frame is None:
            return

        img = self.def_file.read_image(
            how=self._get_layer_name(),
            group_id=self.current_group,
            image_id=self.current_frame
        )
        if img is None:
            self._show_message(_("No image to export"))
            return

        dialog = Gtk.FileDialog()
        dialog.set_title(_("Export Frame"))
        name = self.def_file.get_image_name(self.current_group, self.current_frame) or "frame"
        dialog.set_initial_name(f"{name}.png")

        # Store image for callback
        self._export_img = img
        dialog.save(self.parent_window, None, self._on_export_finish)

    def _on_export_finish(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
            if gfile and self._export_img:
                filepath = gfile.get_path()
                self._export_img.save(filepath)
                self._export_img = None
        except GLib.Error:
            pass
        except Exception as e:
            self._show_message(f"Fehler: {str(e)}")

    def _on_remove_frame(self, button):
        """Remove the selected frame."""
        if self.def_file is None or self.current_group is None or self.current_frame is None:
            return

        self.def_file.remove_frame(self.current_group, self.current_frame)
        self._refresh_ui()
        groups = self.def_file.get_groups()
        if self.current_group in groups:
            self.group_combo.set_active(groups.index(self.current_group))

    def _show_message(self, text, is_error=True):
        alert = Gtk.AlertDialog()
        alert.set_message(text)
        alert.set_buttons(["OK"])
        alert.show(self.parent_window)
