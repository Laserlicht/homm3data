"""
PCX converter mode for converting between H3 PCX format and common image formats.
"""
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Gio
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
        # Toolbar
        toolbar = Gtk.Toolbar()
        toolbar.set_style(Gtk.ToolbarStyle.BOTH_HORIZ)
        toolbar.get_style_context().add_class("primary-toolbar")

        btn_open_pcx = Gtk.ToolButton()
        btn_open_pcx.set_icon_name("document-open")
        btn_open_pcx.set_label(_("Open PCX/P32"))
        btn_open_pcx.set_is_important(True)
        btn_open_pcx.connect("clicked", self._on_open_pcx)
        toolbar.add(btn_open_pcx)

        btn_open_img = Gtk.ToolButton()
        btn_open_img.set_icon_name("insert-image")
        btn_open_img.set_label(_("Open Image"))
        btn_open_img.set_is_important(True)
        btn_open_img.connect("clicked", self._on_open_image)
        toolbar.add(btn_open_img)

        toolbar.add(Gtk.SeparatorToolItem())

        btn_save_pcx = Gtk.ToolButton()
        btn_save_pcx.set_icon_name("document-save-as")
        btn_save_pcx.set_label(_("Save as PCX"))
        btn_save_pcx.set_is_important(True)
        btn_save_pcx.connect("clicked", self._on_save_pcx)
        toolbar.add(btn_save_pcx)

        btn_save_p32 = Gtk.ToolButton()
        btn_save_p32.set_icon_name("document-save-as")
        btn_save_p32.set_label(_("Save as P32"))
        btn_save_p32.set_is_important(True)
        btn_save_p32.connect("clicked", self._on_save_p32)
        toolbar.add(btn_save_p32)

        btn_save_png = Gtk.ToolButton()
        btn_save_png.set_icon_name("document-save-as")
        btn_save_png.set_label(_("Save as PNG"))
        btn_save_png.set_is_important(True)
        btn_save_png.connect("clicked", self._on_save_png)
        toolbar.add(btn_save_png)

        btn_save_bmp = Gtk.ToolButton()
        btn_save_bmp.set_icon_name("document-save-as")
        btn_save_bmp.set_label(_("Save as BMP"))
        btn_save_bmp.set_is_important(True)
        btn_save_bmp.connect("clicked", self._on_save_bmp)
        toolbar.add(btn_save_bmp)

        self.pack_start(toolbar, False, False, 0)

        # Main area
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)

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

        info_frame.add(info_grid)
        main_box.pack_start(info_frame, False, False, 0)

        # PCX mode selection for save
        mode_frame = Gtk.Frame(label=_("PCX Save Mode"))
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        mode_box.set_margin_start(8)
        mode_box.set_margin_end(8)
        mode_box.set_margin_top(4)
        mode_box.set_margin_bottom(8)

        self.radio_rgb = Gtk.RadioButton.new_with_label_from_widget(None, _("24-bit RGB"))
        mode_box.pack_start(self.radio_rgb, False, False, 0)

        self.radio_palette = Gtk.RadioButton.new_with_label_from_widget(self.radio_rgb, _("8-bit Palette"))
        mode_box.pack_start(self.radio_palette, False, False, 0)

        mode_frame.add(mode_box)
        main_box.pack_start(mode_frame, False, False, 0)

        # DnD area / preview
        drop_frame = Gtk.Frame()

        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Drop zone label
        self.drop_label = Gtk.Label(label=_("Drag image here\nor open via toolbar"))
        self.drop_label.set_justify(Gtk.Justification.CENTER)
        self.drop_label.get_style_context().add_class("dim-label")
        self.drop_label.set_margin_top(16)

        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.preview_image = Gtk.Image()
        preview_scroll.add(self.preview_image)

        preview_box.pack_start(self.drop_label, False, False, 0)
        preview_box.pack_start(preview_scroll, True, True, 0)

        drop_frame.add(preview_box)
        main_box.pack_start(drop_frame, True, True, 0)

        self.pack_start(main_box, True, True, 0)

        # Drag & drop
        target_entry = Gtk.TargetEntry.new("text/uri-list", 0, 0)
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [target_entry],
            Gdk.DragAction.COPY
        )
        self.connect("drag-data-received", self._on_drag_data_received)

    def _on_drag_data_received(self, widget, context, x, y, data, info, time):
        """Handle dropped files."""
        uris = data.get_uris()
        if uris:
            filepath = Gio.File.new_for_uri(uris[0]).get_path()
            if filepath:
                ext = os.path.splitext(filepath)[1].lower()
                if ext in ('.pcx', '.p32'):
                    self._load_pcx(filepath)
                else:
                    self._load_image(filepath)

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
        dialog = Gtk.FileChooserDialog(
            title=_("Open PCX/P32"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        pcx_filter = Gtk.FileFilter()
        pcx_filter.set_name(_("H3 PCX/P32 Files"))
        pcx_filter.add_pattern("*.pcx")
        pcx_filter.add_pattern("*.PCX")
        pcx_filter.add_pattern("*.p32")
        pcx_filter.add_pattern("*.P32")
        dialog.add_filter(pcx_filter)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            self._load_pcx(filepath)
        else:
            dialog.destroy()

    def _on_open_image(self, button):
        """Open a common image file."""
        dialog = Gtk.FileChooserDialog(
            title=_("Open Image"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

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
        dialog.add_filter(img_filter)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            self._load_image(filepath)
        else:
            dialog.destroy()

    def _on_save_pcx(self, button):
        """Save as H3 PCX format."""
        if self.current_image is None:
            self._show_message(_("No image loaded"))
            return

        mode = "rgb" if self.radio_rgb.get_active() else "palette"
        dialog = Gtk.FileChooserDialog(
            title=_("Save as PCX"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialog.set_do_overwrite_confirmation(True)
        name = os.path.splitext(os.path.basename(self.current_path))[0] if self.current_path else "image"
        dialog.set_current_name(f"{name}.pcx")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            try:
                data = pcxfile.write_pcx(self.current_image, mode=mode)
                with open(filepath, "wb") as f:
                    f.write(data)
                self._show_message(_("Saved: ") + filepath, Gtk.MessageType.INFO)
            except Exception as e:
                self._show_message(_("Error: ") + str(e))
        else:
            dialog.destroy()

    def _on_save_p32(self, button):
        """Save as HotA P32 format."""
        if self.current_image is None:
            self._show_message(_("No image loaded"))
            return

        dialog = Gtk.FileChooserDialog(
            title=_("Save as P32"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialog.set_do_overwrite_confirmation(True)
        name = os.path.splitext(os.path.basename(self.current_path))[0] if self.current_path else "image"
        dialog.set_current_name(f"{name}.p32")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            try:
                data = pcxfile.write_p32(self.current_image)
                with open(filepath, "wb") as f:
                    f.write(data)
                self._show_message(_("Saved: ") + filepath, Gtk.MessageType.INFO)
            except Exception as e:
                self._show_message(_("Error: ") + str(e))
        else:
            dialog.destroy()

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

        dialog = Gtk.FileChooserDialog(
            title=f"Save as {fmt}",
            parent=self.parent_window,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialog.set_do_overwrite_confirmation(True)
        name = os.path.splitext(os.path.basename(self.current_path))[0] if self.current_path else "image"
        dialog.set_current_name(f"{name}.{ext}")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            try:
                img = self.current_image
                if fmt == "BMP" and img.mode == "RGBA":
                    img = img.convert("RGB")
                if img.mode == "P" and fmt == "PNG":
                    img = img.convert("RGBA")
                img.save(filepath, format=fmt)
                self._show_message(_("Saved: ") + filepath, Gtk.MessageType.INFO)
            except Exception as e:
                self._show_message(_("Error: ") + str(e))
        else:
            dialog.destroy()

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
