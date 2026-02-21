"""
PCX converter mode for converting between H3 PCX format and common image formats.
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio
from PIL import Image
from io import BytesIO
import os

from homm3data import pcxfile
from gui.utils import pil_to_pixbuf, scale_pixbuf_fit
from gui.i18n import _


class PcxConverter(Gtk.Box):
    """
    Simple PCX converter widget.
    Converts between H3 PCX/P32 format and common image formats (PNG, BMP, etc.).
    """

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent_window = parent_window
        self.current_image = None
        self.current_path = None
        self.current_source_format = None
        self._build_ui()

    def _build_ui(self):
        # Toolbar (using Gtk.Box with Buttons)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        toolbar.add_css_class("primary-toolbar")

        btn_open_pcx = self._make_toolbar_button("document-open", _("Open PCX/P32"), self._on_open_pcx)
        toolbar.append(btn_open_pcx)

        btn_open_img = self._make_toolbar_button("insert-image", _("Open Image"), self._on_open_image)
        toolbar.append(btn_open_img)

        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        btn_save_pcx = self._make_toolbar_button("document-save-as", _("Save as PCX"), self._on_save_pcx)
        toolbar.append(btn_save_pcx)

        btn_save_p32 = self._make_toolbar_button("document-save-as", _("Save as P32"), self._on_save_p32)
        toolbar.append(btn_save_p32)

        btn_save_png = self._make_toolbar_button("document-save-as", _("Save as PNG"), self._on_save_png)
        toolbar.append(btn_save_png)

        btn_save_bmp = self._make_toolbar_button("document-save-as", _("Save as BMP"), self._on_save_bmp)
        toolbar.append(btn_save_bmp)

        self.append(toolbar)

        # Main area
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_vexpand(True)

        # Info panel
        info_frame = Gtk.Frame(label=_("Image Information"))
        info_grid = Gtk.Grid()
        info_grid.set_column_spacing(12)
        info_grid.set_row_spacing(4)
        info_grid.set_margin_start(8)
        info_grid.set_margin_end(8)
        info_grid.set_margin_top(4)
        info_grid.set_margin_bottom(8)

        self.info_file = Gtk.Label(label="—")
        self.info_file.set_xalign(0)
        self.info_file.set_selectable(True)
        info_grid.attach(Gtk.Label(label=_("File:")), 0, 0, 1, 1)
        info_grid.attach(self.info_file, 1, 0, 1, 1)

        self.info_size = Gtk.Label(label="—")
        self.info_size.set_xalign(0)
        info_grid.attach(Gtk.Label(label=_("Dimensions:")), 0, 1, 1, 1)
        info_grid.attach(self.info_size, 1, 1, 1, 1)

        self.info_mode = Gtk.Label(label="—")
        self.info_mode.set_xalign(0)
        info_grid.attach(Gtk.Label(label=_("Mode:")), 0, 2, 1, 1)
        info_grid.attach(self.info_mode, 1, 2, 1, 1)

        self.info_format = Gtk.Label(label="—")
        self.info_format.set_xalign(0)
        info_grid.attach(Gtk.Label(label=_("Format:")), 0, 3, 1, 1)
        info_grid.attach(self.info_format, 1, 3, 1, 1)

        info_frame.set_child(info_grid)
        main_box.append(info_frame)

        # PCX mode selection for save
        mode_frame = Gtk.Frame(label=_("PCX Save Mode"))
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        mode_box.set_margin_start(8)
        mode_box.set_margin_end(8)
        mode_box.set_margin_top(4)
        mode_box.set_margin_bottom(8)

        self.radio_rgb = Gtk.ToggleButton(label=_("24-bit RGB"))
        self.radio_rgb.set_active(True)
        mode_box.append(self.radio_rgb)

        self.radio_palette = Gtk.ToggleButton(label=_("8-bit Palette"))
        self.radio_palette.set_group(self.radio_rgb)
        mode_box.append(self.radio_palette)

        mode_frame.set_child(mode_box)
        main_box.append(mode_frame)

        # DnD area / preview
        drop_frame = Gtk.Frame()

        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Drop zone label
        self.drop_label = Gtk.Label(label=_("Drag image here\nor open via toolbar"))
        self.drop_label.set_justify(Gtk.Justification.CENTER)
        self.drop_label.add_css_class("dim-label")
        self.drop_label.set_margin_top(16)

        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        preview_scroll.set_vexpand(True)

        self.preview_image = Gtk.Image()
        preview_scroll.set_child(self.preview_image)

        preview_box.append(self.drop_label)
        preview_box.append(preview_scroll)

        drop_frame.set_child(preview_box)
        main_box.append(drop_frame)

        self.append(main_box)

        # Drag & drop
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.set_gtypes([Gio.File])
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

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

    def _on_drop(self, target, value, x, y):
        """Handle dropped files."""
        if isinstance(value, Gio.File):
            filepath = value.get_path()
            if filepath:
                ext = os.path.splitext(filepath)[1].lower()
                if ext in ('.pcx', '.p32'):
                    self._load_pcx(filepath)
                else:
                    self._load_image(filepath)
            return True
        return False

    def _load_pcx(self, filepath):
        """Load a PCX/P32 file."""
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            if not pcxfile.is_pcx(data):
                self._show_message(_("No valid H3 PCX/P32 file."))
                return

            self.current_image = pcxfile.read_pcx(data)
            self.current_path = filepath
            self.current_source_format = os.path.splitext(filepath)[1].lower()
            self._update_info()
            self._update_preview()
        except Exception as e:
            self._show_message(_("Error loading: ") + str(e))

    def _load_image(self, filepath):
        """Load a common image file."""
        try:
            self.current_image = Image.open(filepath)
            self.current_path = filepath
            self.current_source_format = os.path.splitext(filepath)[1].lower()
            self._update_info()
            self._update_preview()
        except Exception as e:
            self._show_message(_("Error loading: ") + str(e))

    def _update_info(self):
        """Update image info labels."""
        if self.current_image is None:
            self.info_file.set_text("—")
            self.info_size.set_text("—")
            self.info_mode.set_text("—")
            self.info_format.set_text("—")
            return

        self.info_file.set_text(self.current_path or _("In memory"))
        w, h = self.current_image.size
        self.info_size.set_text(f"{w} × {h} Pixel")
        self.info_mode.set_text(self.current_image.mode)
        self.info_format.set_text(self.current_source_format or _("Unknown"))

    def _update_preview(self):
        """Update the image preview."""
        if self.current_image is None:
            self.drop_label.set_text(_("Drag image here\nor open via toolbar"))
            self.preview_image.clear()
            return

        self.drop_label.set_text("")

        img = self.current_image
        if img.mode == 'P':
            img = img.convert('RGBA')
        elif img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA')

        pixbuf = pil_to_pixbuf(img)
        pixbuf = scale_pixbuf_fit(pixbuf, 600, 500)
        self.preview_image.set_from_pixbuf(pixbuf)

    def _on_open_pcx(self, button):
        """Open a PCX/P32 file."""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Open PCX/P32"))

        pcx_filter = Gtk.FileFilter()
        pcx_filter.set_name(_("H3 PCX/P32 Files"))
        pcx_filter.add_pattern("*.pcx")
        pcx_filter.add_pattern("*.PCX")
        pcx_filter.add_pattern("*.p32")
        pcx_filter.add_pattern("*.P32")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(pcx_filter)
        dialog.set_filters(filters)

        dialog.open(self.parent_window, None, self._on_open_pcx_finish)

    def _on_open_pcx_finish(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
            if gfile:
                filepath = gfile.get_path()
                self._load_pcx(filepath)
        except GLib.Error:
            pass

    def _on_open_image(self, button):
        """Open a common image file."""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Open Image"))

        img_filter = Gtk.FileFilter()
        img_filter.set_name(_("Image Files"))
        img_filter.add_pattern("*.png")
        img_filter.add_pattern("*.PNG")
        img_filter.add_pattern("*.bmp")
        img_filter.add_pattern("*.BMP")
        img_filter.add_pattern("*.jpg")
        img_filter.add_pattern("*.jpeg")
        img_filter.add_pattern("*.gif")
        img_filter.add_pattern("*.tiff")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(img_filter)
        dialog.set_filters(filters)

        dialog.open(self.parent_window, None, self._on_open_image_finish)

    def _on_open_image_finish(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
            if gfile:
                filepath = gfile.get_path()
                self._load_image(filepath)
        except GLib.Error:
            pass

    def _on_save_pcx(self, button):
        """Save as H3 PCX format."""
        if self.current_image is None:
            self._show_message(_("No image loaded"))
            return

        self._save_mode = "rgb" if self.radio_rgb.get_active() else "palette"

        dialog = Gtk.FileDialog()
        dialog.set_title(_("Save as PCX"))
        name = os.path.splitext(os.path.basename(self.current_path))[0] if self.current_path else "image"
        dialog.set_initial_name(f"{name}.pcx")
        dialog.save(self.parent_window, None, self._on_save_pcx_finish)

    def _on_save_pcx_finish(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
            if gfile:
                filepath = gfile.get_path()
                data = pcxfile.write_pcx(self.current_image, mode=self._save_mode)
                with open(filepath, "wb") as f:
                    f.write(data)
                self._show_message(_("Saved: ") + filepath, is_error=False)
        except GLib.Error:
            pass
        except Exception as e:
            self._show_message(_("Error: ") + str(e))

    def _on_save_p32(self, button):
        """Save as HotA P32 format."""
        if self.current_image is None:
            self._show_message(_("No image loaded"))
            return

        dialog = Gtk.FileDialog()
        dialog.set_title(_("Save as P32"))
        name = os.path.splitext(os.path.basename(self.current_path))[0] if self.current_path else "image"
        dialog.set_initial_name(f"{name}.p32")
        dialog.save(self.parent_window, None, self._on_save_p32_finish)

    def _on_save_p32_finish(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
            if gfile:
                filepath = gfile.get_path()
                data = pcxfile.write_p32(self.current_image)
                with open(filepath, "wb") as f:
                    f.write(data)
                self._show_message(_("Saved: ") + filepath, is_error=False)
        except GLib.Error:
            pass
        except Exception as e:
            self._show_message(_("Error: ") + str(e))

    def _on_save_png(self, button):
        """Save as PNG."""
        self._save_common("PNG", "png")

    def _on_save_bmp(self, button):
        """Save as BMP."""
        self._save_common("BMP", "bmp")

    def _save_common(self, fmt, ext):
        """Save to a common image format."""
        if self.current_image is None:
            self._show_message(_("No image loaded"))
            return

        self._save_fmt = fmt

        dialog = Gtk.FileDialog()
        dialog.set_title(f"Save as {fmt}")
        name = os.path.splitext(os.path.basename(self.current_path))[0] if self.current_path else "image"
        dialog.set_initial_name(f"{name}.{ext}")
        dialog.save(self.parent_window, None, self._on_save_common_finish)

    def _on_save_common_finish(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
            if gfile:
                filepath = gfile.get_path()
                fmt = self._save_fmt
                img = self.current_image
                if fmt == "BMP" and img.mode == "RGBA":
                    img = img.convert("RGB")
                if img.mode == "P" and fmt == "PNG":
                    img = img.convert("RGBA")
                img.save(filepath, format=fmt)
                self._show_message(_("Saved: ") + filepath, is_error=False)
        except GLib.Error:
            pass
        except Exception as e:
            self._show_message(_("Error: ") + str(e))

    def _show_message(self, text, is_error=True):
        alert = Gtk.AlertDialog()
        alert.set_message(text)
        alert.set_buttons(["OK"])
        alert.show(self.parent_window)
