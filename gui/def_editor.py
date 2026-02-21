"""
DEF editor mode for viewing and editing DEF animation frames.
"""
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
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
        # Toolbar
        toolbar = Gtk.Toolbar()
        toolbar.set_style(Gtk.ToolbarStyle.BOTH_HORIZ)
        toolbar.get_style_context().add_class("primary-toolbar")

        btn_open = Gtk.ToolButton()
        btn_open.set_icon_name("document-open")
        btn_open.set_label(_("Open"))
        btn_open.set_is_important(True)
        btn_open.connect("clicked", self._on_open)
        toolbar.add(btn_open)

        btn_save = Gtk.ToolButton()
        btn_save.set_icon_name("document-save")
        btn_save.set_label(_("Save"))
        btn_save.set_is_important(True)
        btn_save.connect("clicked", self._on_save)
        toolbar.add(btn_save)

        toolbar.add(Gtk.SeparatorToolItem())

        btn_import = Gtk.ToolButton()
        btn_import.set_icon_name("insert-image")
        btn_import.set_label(_("Import Frame"))
        btn_import.set_is_important(True)
        btn_import.connect("clicked", self._on_import_frame)
        toolbar.add(btn_import)

        btn_export = Gtk.ToolButton()
        btn_export.set_icon_name("document-save-as")
        btn_export.set_label(_("Export Frame"))
        btn_export.set_is_important(True)
        btn_export.connect("clicked", self._on_export_frame)
        toolbar.add(btn_export)

        btn_remove = Gtk.ToolButton()
        btn_remove.set_icon_name("list-remove")
        btn_remove.set_label(_("Remove"))
        btn_remove.set_is_important(True)
        btn_remove.connect("clicked", self._on_remove_frame)
        toolbar.add(btn_remove)

        toolbar.add(Gtk.SeparatorToolItem())

        btn_new = Gtk.ToolButton()
        btn_new.set_icon_name("document-new")
        btn_new.set_label(_("New DEF"))
        btn_new.set_is_important(True)
        btn_new.connect("clicked", self._on_new_def)
        toolbar.add(btn_new)

        self.pack_start(toolbar, False, False, 0)

        # Main layout
        main_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_paned.set_position(200)

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
        info_box.pack_start(self.info_type, False, False, 0)
        info_box.pack_start(self.info_size, False, False, 0)
        info_box.pack_start(self.info_groups, False, False, 0)
        info_frame.add(info_box)
        left_box.pack_start(info_frame, False, False, 4)

        # Group selector
        group_label = Gtk.Label(label=_("Group:"))
        group_label.set_xalign(0)
        left_box.pack_start(group_label, False, False, 2)

        self.group_combo = Gtk.ComboBoxText()
        self.group_combo.connect("changed", self._on_group_changed)
        left_box.pack_start(self.group_combo, False, False, 0)

        # Frame list
        frame_label = Gtk.Label(label=_("Frames:"))
        frame_label.set_xalign(0)
        left_box.pack_start(frame_label, False, False, 2)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

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

        scrolled.add(self.frame_tree)
        left_box.pack_start(scrolled, True, True, 0)

        main_paned.pack1(left_box, False, False)

        # Right panel: frame preview
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Layer selector
        layer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        layer_box.set_margin_start(8)
        layer_box.set_margin_top(4)

        layer_label = Gtk.Label(label=_("Layer:"))
        layer_box.pack_start(layer_label, False, False, 0)

        self.layer_combo = Gtk.ComboBoxText()
        self.layer_combo.append_text(_("Combined"))
        self.layer_combo.append_text(_("Normal"))
        self.layer_combo.append_text(_("Shadow"))
        self.layer_combo.append_text(_("Overlay"))
        self.layer_combo.set_active(0)
        self.layer_combo.connect("changed", self._on_layer_changed)
        layer_box.pack_start(self.layer_combo, False, False, 0)

        # Zoom controls
        zoom_label = Gtk.Label(label="  " + _("Zoom:"))
        layer_box.pack_start(zoom_label, False, False, 0)

        btn_zoom_out = Gtk.Button(label="−")
        btn_zoom_out.connect("clicked", self._on_zoom_out)
        layer_box.pack_start(btn_zoom_out, False, False, 0)

        self.zoom_label = Gtk.Label(label="100%")
        layer_box.pack_start(self.zoom_label, False, False, 0)

        btn_zoom_in = Gtk.Button(label="+")
        btn_zoom_in.connect("clicked", self._on_zoom_in)
        layer_box.pack_start(btn_zoom_in, False, False, 0)

        btn_zoom_fit = Gtk.Button(label=_("Fit"))
        btn_zoom_fit.connect("clicked", self._on_zoom_fit)
        layer_box.pack_start(btn_zoom_fit, False, False, 0)

        right_box.pack_start(layer_box, False, False, 0)

        # Animation controls
        anim_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        anim_box.set_margin_start(8)

        self.btn_play = Gtk.Button(label="▶ " + _("Play"))
        self.btn_play.connect("clicked", self._on_toggle_animation)
        anim_box.pack_start(self.btn_play, False, False, 0)

        fps_label = Gtk.Label(label=_("FPS:"))
        anim_box.pack_start(fps_label, False, False, 0)

        self.fps_spin = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.fps_spin.set_value(10)
        self.fps_spin.connect("value-changed", self._on_fps_changed)
        anim_box.pack_start(self.fps_spin, False, False, 0)

        right_box.pack_start(anim_box, False, False, 0)

        # Image preview with scrolling
        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # Drawing area for checkerboard + image
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.connect("draw", self._on_draw)
        preview_scroll.add(self.drawing_area)

        right_box.pack_start(preview_scroll, True, True, 0)

        # Frame info
        self.frame_info = Gtk.Label(label="")
        self.frame_info.set_xalign(0)
        self.frame_info.set_margin_start(8)
        self.frame_info.set_margin_bottom(4)
        right_box.pack_start(self.frame_info, False, False, 0)

        main_paned.pack2(right_box, True, False)
        self.pack_start(main_paned, True, True, 0)

        self._current_pixbuf = None

    def _on_draw(self, widget, cr):
        """Draw checkerboard background and image."""
        alloc = widget.get_allocation()

        if self._current_pixbuf is None:
            return

        pw = self._current_pixbuf.get_width()
        ph = self._current_pixbuf.get_height()

        # Set minimum size for drawing area
        widget.set_size_request(max(pw, alloc.width), max(ph, alloc.height))

        # Center the image
        x = max(0, (alloc.width - pw) // 2)
        y = max(0, (alloc.height - ph) // 2)

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
        dialog = Gtk.FileChooserDialog(
            title=_("Open DEF File"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        filter_def = Gtk.FileFilter()
        filter_def.set_name(_("DEF Files"))
        filter_def.add_pattern("*.def")
        filter_def.add_pattern("*.DEF")
        filter_def.add_pattern("*.d32")
        filter_def.add_pattern("*.D32")
        dialog.add_filter(filter_def)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            self._load_def(filepath)
            self.parent_window.set_title(f"H3 Data Editor — {os.path.basename(filepath)}")
        else:
            dialog.destroy()

    def _on_save(self, button):
        """Save the DEF file."""
        if self.def_file is None:
            return

        if self.def_path:
            try:
                self.def_file.save(self.def_path)
                self._show_message(_("Saved: ") + self.def_path, Gtk.MessageType.INFO)
            except Exception as e:
                self._show_message(_("Error saving: ") + str(e))
        else:
            self._on_save_as()

    def _on_save_as(self):
        """Save as dialog."""
        dialog = Gtk.FileChooserDialog(
            title=_("Save DEF As"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialog.set_do_overwrite_confirmation(True)
        dialog.set_current_name("sprite.def")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            try:
                self.def_file.save(filepath)
                self.def_path = filepath
            except Exception as e:
                self._show_message(f"Fehler: {str(e)}")
        else:
            dialog.destroy()

    def _on_new_def(self, button):
        """Create a new empty DEF."""
        dialog = Gtk.Dialog(
            title=_("Create New DEF"),
            parent=self.parent_window,
            flags=0,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )

        content = dialog.get_content_area()
        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(4)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        grid.set_margin_top(8)
        grid.set_margin_bottom(8)

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

        content.add(grid)
        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            type_idx = type_combo.get_active()
            w = int(width_spin.get_value())
            h = int(height_spin.get_value())
            file_type = list(deffile.DefFile.FileType)[type_idx]
            dialog.destroy()

            self.def_file = deffile.DefFile.create(file_type=file_type, width=w, height=h)
            self.def_path = None
            self.parent_window.set_title("H3 Data Editor — Neues DEF")
            self._refresh_ui()
        else:
            dialog.destroy()

    def _on_import_frame(self, button):
        """Import an image as a new frame."""
        if self.def_file is None:
            self._show_message(_("Please load or create a DEF first."))
            return

        dialog = Gtk.FileChooserDialog(
            title=_("Import Frame"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            "Import", Gtk.ResponseType.OK,
        )
        dialog.set_select_multiple(True)

        img_filter = Gtk.FileFilter()
        img_filter.set_name(_("Image Files"))
        img_filter.add_pattern("*.png")
        img_filter.add_pattern("*.bmp")
        img_filter.add_pattern("*.jpg")
        img_filter.add_pattern("*.jpeg")
        img_filter.add_pattern("*.gif")
        img_filter.add_pattern("*.tiff")
        dialog.add_filter(img_filter)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filenames = dialog.get_filenames()
            dialog.destroy()

            group = self.current_group if self.current_group is not None else 0
            start_id = self.def_file.get_frame_count(group) if group in self.def_file.get_groups() else 0

            for i, filepath in enumerate(filenames):
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
        else:
            dialog.destroy()

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

        dialog = Gtk.FileChooserDialog(
            title=_("Export Frame"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialog.set_do_overwrite_confirmation(True)

        name = self.def_file.get_image_name(self.current_group, self.current_frame) or "frame"
        dialog.set_current_name(f"{name}.png")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            try:
                img.save(filepath)
            except Exception as e:
                self._show_message(f"Fehler: {str(e)}")
        else:
            dialog.destroy()

    def _on_remove_frame(self, button):
        """Remove the selected frame."""
        if self.def_file is None or self.current_group is None or self.current_frame is None:
            return

        self.def_file.remove_frame(self.current_group, self.current_frame)
        self._refresh_ui()
        groups = self.def_file.get_groups()
        if self.current_group in groups:
            self.group_combo.set_active(groups.index(self.current_group))

    def _show_message(self, text, msg_type=Gtk.MessageType.ERROR):
        dialog = Gtk.MessageDialog(
            transient_for=self.parent_window,
            flags=0,
            message_type=msg_type,
            buttons=Gtk.ButtonsType.OK,
            text=text,
        )
        dialog.run()
        dialog.destroy()
