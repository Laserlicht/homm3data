"""
Archive browser mode for LOD and PAK files.
Provides a file browser-like UI with add/remove, sidebar preview,
and drag & drop support.
"""
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio
from PIL import Image
from io import BytesIO
import os
import tempfile

from homm3data import lodfile, pakfile, deffile, pcxfile
from gui.utils import pil_to_pixbuf, scale_pixbuf_fit
from gui.i18n import _


class ArchiveBrowser(Gtk.Box):
    """
    File browser widget for LOD and PAK archives.
    Shows file list with sidebar preview for DEF, PCX, and TXT files.
    Supports drag & drop and button-based file management.
    """

    def __init__(self, parent_window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.parent_window = parent_window
        self.archive = None
        self.archive_path = None
        self.archive_type = None  # 'lod' or 'pak'
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

        btn_save_as = Gtk.ToolButton()
        btn_save_as.set_icon_name("document-save-as")
        btn_save_as.set_label(_("Save As"))
        btn_save_as.set_is_important(True)
        btn_save_as.connect("clicked", self._on_save_as)
        toolbar.add(btn_save_as)

        toolbar.add(Gtk.SeparatorToolItem())

        btn_add = Gtk.ToolButton()
        btn_add.set_icon_name("list-add")
        btn_add.set_label(_("Add"))
        btn_add.set_is_important(True)
        btn_add.connect("clicked", self._on_add_files)
        toolbar.add(btn_add)

        btn_remove = Gtk.ToolButton()
        btn_remove.set_icon_name("list-remove")
        btn_remove.set_label(_("Remove"))
        btn_remove.set_is_important(True)
        btn_remove.connect("clicked", self._on_remove_files)
        toolbar.add(btn_remove)

        btn_extract = Gtk.ToolButton()
        btn_extract.set_icon_name("document-save")
        btn_extract.set_label(_("Export"))
        btn_extract.set_is_important(True)
        btn_extract.connect("clicked", self._on_extract_files)
        toolbar.add(btn_extract)

        toolbar.add(Gtk.SeparatorToolItem())

        btn_new_lod = Gtk.ToolButton()
        btn_new_lod.set_icon_name("document-new")
        btn_new_lod.set_label(_("New LOD"))
        btn_new_lod.set_is_important(True)
        btn_new_lod.connect("clicked", self._on_new_lod)
        toolbar.add(btn_new_lod)

        self.pack_start(toolbar, False, False, 0)

        # Main paned area
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(400)

        # Left: file list
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search..."))
        self.search_entry.connect("search-changed", self._on_search_changed)
        left_box.pack_start(self.search_entry, False, False, 4)

        # File list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.file_store = Gtk.ListStore(str, str, str)  # filename, size, type
        self.file_filter = self.file_store.filter_new()
        self.file_filter.set_visible_func(self._filter_func)
        self.file_sort = Gtk.TreeModelSort(model=self.file_filter)
        self.file_sort.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        self.file_tree = Gtk.TreeView(model=self.file_sort)
        self.file_tree.set_headers_visible(True)
        self.file_tree.set_enable_search(True)
        self.file_tree.set_rubber_banding(True)
        self.file_tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.file_tree.get_selection().connect("changed", self._on_selection_changed)
        self.file_tree.connect("row-activated", self._on_file_double_click)
        self.file_tree.connect("button-press-event", self._on_file_button_press)

        col_name = Gtk.TreeViewColumn(_("Filename"), Gtk.CellRendererText(), text=0)
        col_name.set_sort_column_id(0)
        col_name.set_resizable(True)
        col_name.set_expand(True)
        self.file_tree.append_column(col_name)

        col_size = Gtk.TreeViewColumn(_("Size"), Gtk.CellRendererText(), text=1)
        col_size.set_sort_column_id(1)
        col_size.set_resizable(True)
        self.file_tree.append_column(col_size)

        col_type = Gtk.TreeViewColumn(_("Type"), Gtk.CellRendererText(), text=2)
        col_type.set_sort_column_id(2)
        col_type.set_resizable(True)
        self.file_tree.append_column(col_type)

        scrolled.add(self.file_tree)
        left_box.pack_start(scrolled, True, True, 0)

        # Status bar
        self.status_label = Gtk.Label(label=_("No archive loaded"))
        self.status_label.set_xalign(0)
        left_box.pack_start(self.status_label, False, False, 4)

        paned.pack1(left_box, True, False)

        # Right: preview
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right_box.set_margin_start(4)

        preview_label = Gtk.Label(label=_("Preview"))
        preview_label.set_xalign(0)
        preview_label.get_style_context().add_class("dim-label")
        right_box.pack_start(preview_label, False, False, 4)

        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.preview_stack = Gtk.Stack()
        self.preview_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Image preview
        self.preview_image = Gtk.Image()
        self.preview_stack.add_named(self.preview_image, "image")

        # Text preview
        text_scroll = Gtk.ScrolledWindow()
        text_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.preview_text = Gtk.TextView()
        self.preview_text.set_editable(False)
        self.preview_text.set_monospace(True)
        self.preview_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_scroll.add(self.preview_text)
        self.preview_stack.add_named(text_scroll, "text")

        # Empty preview
        empty_label = Gtk.Label(label=_("Select a file\nfor preview"))
        empty_label.set_justify(Gtk.Justification.CENTER)
        empty_label.get_style_context().add_class("dim-label")
        self.preview_stack.add_named(empty_label, "empty")

        self.preview_stack.set_visible_child_name("empty")
        preview_scroll.add(self.preview_stack)
        right_box.pack_start(preview_scroll, True, True, 0)

        paned.pack2(right_box, True, False)
        self.pack_start(paned, True, True, 0)

        # Set up drag & drop
        self._setup_dnd()

    def _setup_dnd(self):
        """Set up drag & drop support."""
        target_entry = Gtk.TargetEntry.new("text/uri-list", 0, 0)
        self.file_tree.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [target_entry],
            Gdk.DragAction.COPY
        )
        self.file_tree.connect("drag-data-received", self._on_drag_data_received)

    def _on_drag_data_received(self, widget, context, x, y, data, info, time):
        """Handle files dropped onto the file list."""
        if self.archive is None:
            self._show_message(_("Please open or create an archive first."))
            return

        uris = data.get_uris()
        for uri in uris:
            filepath = Gio.File.new_for_uri(uri).get_path()
            if filepath and os.path.isfile(filepath):
                filename = os.path.basename(filepath)
                with open(filepath, "rb") as f:
                    file_data = f.read()
                if self.archive_type == 'lod':
                    self.archive.add_file(filename, file_data)
                self._refresh_file_list()

    def _filter_func(self, model, iter, data=None):
        """Filter function for the search."""
        search_text = self.search_entry.get_text().lower()
        if not search_text:
            return True
        filename = model[iter][0]
        return search_text in filename.lower() if filename else True

    def _on_search_changed(self, entry):
        self.file_filter.refilter()

    def _get_file_type(self, filename):
        """Determine file type from extension."""
        ext = os.path.splitext(filename)[1].lower()
        type_map = {
            '.def': 'DEF', '.d32': 'D32', '.pcx': 'PCX', '.p32': 'P32',
            '.txt': 'Text', '.msk': 'Maske', '.msg': 'Nachricht',
            '.fnt': 'Schrift', '.pal': 'Palette', '.bmp': 'Bitmap',
            '.wav': 'Audio', '.mp3': 'Audio', '.xmi': 'Musik',
            '.h3m': 'Karte', '.h3c': 'Kampagne', '.json': 'JSON',
        }
        return type_map.get(ext, ext.upper().lstrip('.') if ext else 'Datei')

    def _format_size(self, size):
        """Format byte size to human-readable string."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    def _refresh_file_list(self):
        """Refresh the file list from the current archive."""
        self.file_store.clear()
        if self.archive is None:
            self.status_label.set_text(_("No archive loaded"))
            return

        if self.archive_type == 'lod':
            files = self.archive.get_filelist()
            for filename in files:
                data = self.archive.get_file(filename)
                size_str = self._format_size(len(data)) if data else "?"
                file_type = self._get_file_type(filename)
                self.file_store.append([filename, size_str, file_type])
            self.status_label.set_text(f"{len(files)}" + _(" files in archive"))
        elif self.archive_type == 'pak':
            sheets = self.archive.get_sheetnames()
            for name in sheets:
                sprites = self.archive.get_filenames_for_sheet(name)
                count = len(sprites) if sprites else 0
                self.file_store.append([name, f"{count} Sprites", "PAK Sheet"])
            self.status_label.set_text(f"{len(sheets)}" + _(" sheets in archive"))

    def _on_selection_changed(self, selection):
        """Update preview when selection changes."""
        model, paths = selection.get_selected_rows()
        if not paths:
            self.preview_stack.set_visible_child_name("empty")
            return

        # Get filename from first selected item
        iter_ = model.get_iter(paths[0])
        filename = model.get_value(iter_, 0)
        self._update_preview(filename)

    def _on_file_double_click(self, tree_view, path, column):
        """Handle double-click on a file."""
        model = tree_view.get_model()
        iter_ = model.get_iter(path)
        if iter_ is None:
            return
        filename = model.get_value(iter_, 0)
        self._open_file_in_editor(filename)

    def _on_file_button_press(self, widget, event):
        """Handle right-click on a file for context menu."""
        if event.button == 3:
            # Get the path at the click position
            result = self.file_tree.get_path_at_pos(int(event.x), int(event.y))
            if result is None:
                return False
            
            path, column, cell_x, cell_y = result
            
            # Select the row if not already selected
            selection = self.file_tree.get_selection()
            if not selection.path_is_selected(path):
                selection.unselect_all()
                selection.select_path(path)
            
            model, paths = selection.get_selected_rows()
            if not paths:
                return False
            iter_ = model.get_iter(paths[0])
            if iter_ is None:
                return False
            filename = model.get_value(iter_, 0)
            ext = os.path.splitext(filename)[1].lower()
            
            menu = Gtk.Menu()
            
            if ext in ('.def', '.d32'):
                item = Gtk.MenuItem(label=_("Open in DEF Editor"))
                item.connect("activate", lambda *_: self._open_file_in_editor(filename))
                menu.append(item)
            elif ext in ('.pcx', '.p32'):
                item = Gtk.MenuItem(label=_("Open in PCX Converter"))
                item.connect("activate", lambda *_: self._open_file_in_editor(filename))
                menu.append(item)
            
            if len(menu.get_children()) > 0:
                menu.show_all()
                menu.attach_to_widget(widget, None)
                menu.popup_at_pointer(event)
            return True
        return False

    def _open_file_in_editor(self, filename):
        """Open the selected file in the appropriate editor."""
        if self.archive is None or self.archive_type != 'lod':
            return
        
        ext = os.path.splitext(filename)[1].lower()
        data = self.archive.get_file(filename)
        
        if data is None:
            return
        
        if ext in ('.def', '.d32'):
            self.parent_window.content_stack.set_visible_child_name("def")
            self.parent_window.def_editor._load_def(data)
            # Update mode buttons
            self.parent_window.mode_buttons[1].set_active(True)
        elif ext in ('.pcx', '.p32'):
            self.parent_window.content_stack.set_visible_child_name("pcx")
            try:
                img = pcxfile.read_pcx(data)
                self.parent_window.pcx_converter.current_image = img
                self.parent_window.pcx_converter.current_path = filename
                self.parent_window.pcx_converter.current_source_format = ext
                self.parent_window.pcx_converter._update_info()
                self.parent_window.pcx_converter._update_preview()
            except Exception as e:
                self._show_message(_("Error loading: ") + str(e))
            # Update mode buttons
            self.parent_window.mode_buttons[2].set_active(True)

    def _update_preview(self, filename):
        """Update the preview panel for the selected file."""
        if self.archive is None:
            return

        try:
            if self.archive_type == 'lod':
                data = self.archive.get_file(filename)
                if data is None:
                    self.preview_stack.set_visible_child_name("empty")
                    return
                self._preview_lod_file(filename, data)
            elif self.archive_type == 'pak':
                self._preview_pak_sheet(filename)
        except Exception as e:
            self.preview_text.get_buffer().set_text(_("Error loading: ") + str(e))
            self.preview_stack.set_visible_child_name("text")

    def _preview_lod_file(self, filename, data):
        """Preview a file from a LOD archive."""
        ext = os.path.splitext(filename)[1].lower()

        if ext in ('.def', '.d32'):
            try:
                with deffile.open(BytesIO(data)) as d:
                    img = d.read_image(group_id=d.get_groups()[0], image_id=0)
                    if img:
                        pixbuf = pil_to_pixbuf(img)
                        pixbuf = scale_pixbuf_fit(pixbuf, 400, 400)
                        self.preview_image.set_from_pixbuf(pixbuf)
                        self.preview_stack.set_visible_child_name("image")
                        return
            except Exception:
                pass

        if ext in ('.pcx', '.p32'):
            try:
                if pcxfile.is_pcx(data):
                    img = pcxfile.read_pcx(data)
                    if img:
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        pixbuf = pil_to_pixbuf(img)
                        pixbuf = scale_pixbuf_fit(pixbuf, 400, 400)
                        self.preview_image.set_from_pixbuf(pixbuf)
                        self.preview_stack.set_visible_child_name("image")
                        return
            except Exception:
                pass

        if ext in ('.txt', '.json', '.msg', '.xml', '.cfg', '.csv'):
            try:
                text = data.decode('utf-8', errors='replace')
                buf = self.preview_text.get_buffer()
                buf.set_text(text[:50000])  # Limit preview
                self.preview_stack.set_visible_child_name("text")
                return
            except Exception:
                pass

        # Binary info
        info = f"File: {filename}\nSize: {self._format_size(len(data))}\nType: {self._get_file_type(filename)}\n\nNo preview available"
        self.preview_text.get_buffer().set_text(info)
        self.preview_stack.set_visible_child_name("text")

    def _preview_pak_sheet(self, sheetname):
        """Preview a PAK sheet."""
        try:
            sheets = self.archive.get_sheets(sheetname)
            if sheets and len(sheets) > 0:
                img = sheets[0]
                if img:
                    pixbuf = pil_to_pixbuf(img.convert('RGBA') if img.mode != 'RGBA' else img)
                    pixbuf = scale_pixbuf_fit(pixbuf, 400, 400)
                    self.preview_image.set_from_pixbuf(pixbuf)
                    self.preview_stack.set_visible_child_name("image")
                    return
        except Exception:
            pass

        self.preview_stack.set_visible_child_name("empty")

    def _on_open(self, button):
        """Open a LOD or PAK file."""
        dialog = Gtk.FileChooserDialog(
            title=_("Open Archive"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("H3 Archives (LOD, PAK)"))
        filter_all.add_pattern("*.lod")
        filter_all.add_pattern("*.LOD")
        filter_all.add_pattern("*.pak")
        filter_all.add_pattern("*.PAK")
        dialog.add_filter(filter_all)

        filter_lod = Gtk.FileFilter()
        filter_lod.set_name(_("LOD Files"))
        filter_lod.add_pattern("*.lod")
        filter_lod.add_pattern("*.LOD")
        dialog.add_filter(filter_lod)

        filter_pak = Gtk.FileFilter()
        filter_pak.set_name(_("PAK Files"))
        filter_pak.add_pattern("*.pak")
        filter_pak.add_pattern("*.PAK")
        dialog.add_filter(filter_pak)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            self._load_archive(filepath)
        else:
            dialog.destroy()

    def _load_archive(self, filepath):
        """Load a LOD or PAK archive."""
        ext = os.path.splitext(filepath)[1].lower()
        try:
            if ext == '.lod':
                f = open(filepath, "rb")
                self.archive = lodfile.LodFile(f)
                self.archive_type = 'lod'
            elif ext == '.pak':
                f = open(filepath, "rb")
                self.archive = pakfile.PakFile(f)
                self.archive_type = 'pak'
            else:
                self._show_message(_("Unknown file format: ") + ext)
                return

            self.archive_path = filepath
            self.parent_window.set_title(f"H3 Data Editor — {os.path.basename(filepath)}")
            self._refresh_file_list()
        except Exception as e:
            self._show_message(_("Error opening: ") + str(e))

    def _on_save(self, button):
        """Save the current archive."""
        if self.archive is None:
            self._show_message(_("No archive loaded"))
            return
        if self.archive_path:
            try:
                self.archive.save(self.archive_path)
                self._show_message(_("Saved: ") + self.archive_path, Gtk.MessageType.INFO)
            except Exception as e:
                self._show_message(_("Error saving: ") + str(e))
        else:
            self._on_save_as(button)

    def _on_save_as(self, button):
        """Save the archive to a new file."""
        if self.archive is None:
            self._show_message(_("No archive loaded"))
            return

        dialog = Gtk.FileChooserDialog(
            title=_("Save Archive"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK,
        )
        dialog.set_do_overwrite_confirmation(True)

        if self.archive_type == 'lod':
            dialog.set_current_name("archive.lod")
        else:
            dialog.set_current_name("archive.pak")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filepath = dialog.get_filename()
            dialog.destroy()
            try:
                self.archive.save(filepath)
                self.archive_path = filepath
                self.parent_window.set_title(f"H3 Data Editor — {os.path.basename(filepath)}")
                self._show_message(_("Saved: ") + filepath, Gtk.MessageType.INFO)
            except Exception as e:
                self._show_message(_("Error saving: ") + str(e))
        else:
            dialog.destroy()

    def _on_new_lod(self, button):
        """Create a new empty LOD archive."""
        self.archive = lodfile.LodFile.create()
        self.archive_type = 'lod'
        self.archive_path = None
        self.parent_window.set_title("H3 Data Editor — New LOD Archive")
        self._refresh_file_list()

    def _on_add_files(self, button):
        """Add files to the archive."""
        if self.archive is None:
            self._show_message(_("Please open or create an archive first."))
            return

        dialog = Gtk.FileChooserDialog(
            title=_("Add Files"),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_ADD, Gtk.ResponseType.OK,
        )
        dialog.set_select_multiple(True)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filenames = dialog.get_filenames()
            dialog.destroy()
            added = 0
            for filepath in filenames:
                try:
                    filename = os.path.basename(filepath)
                    with open(filepath, "rb") as f:
                        data = f.read()
                    if self.archive_type == 'lod':
                        self.archive.add_file(filename, data)
                        added += 1
                except Exception as e:
                    self._show_message(_("Error adding ") + filepath + ": " + str(e))
            self._refresh_file_list()
            if added > 0:
                self.status_label.set_text(f"{added}" + _(" file(s) added"))
        else:
            dialog.destroy()

    def _on_remove_files(self, button):
        """Remove selected files from the archive."""
        if self.archive is None:
            return

        selection = self.file_tree.get_selection()
        model, paths = selection.get_selected_rows()
        if not paths:
            return

        filenames = []
        for path in paths:
            iter_ = model.get_iter(path)
            filenames.append(model.get_value(iter_, 0))

        # Confirm deletion
        dialog = Gtk.MessageDialog(
            transient_for=self.parent_window,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"{len(filenames)}" + " " + _("Remove files?"),
        )
        dialog.format_secondary_text(_("This action cannot be undone."))
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            for filename in filenames:
                if self.archive_type == 'lod':
                    self.archive.remove_file(filename)
                elif self.archive_type == 'pak':
                    self.archive.remove_sheet(filename)
            self._refresh_file_list()

    def _on_extract_files(self, button):
        """Extract selected files from the archive."""
        if self.archive is None:
            return

        selection = self.file_tree.get_selection()
        model, paths = selection.get_selected_rows()
        if not paths:
            self._show_message(_("No files selected."))
            return

        dialog = Gtk.FileChooserDialog(
            title=_("Export to..."),
            parent=self.parent_window,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            "Export", Gtk.ResponseType.OK,
        )

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            output_dir = dialog.get_filename()
            dialog.destroy()
            exported = 0
            for path in paths:
                iter_ = model.get_iter(path)
                filename = model.get_value(iter_, 0)
                try:
                    if self.archive_type == 'lod':
                        data = self.archive.get_file(filename)
                        if data:
                            outpath = os.path.join(output_dir, filename)
                            with open(outpath, "wb") as f:
                                f.write(data)
                            exported += 1
                except Exception as e:
                    self._show_message(_("Error exporting ") + filename + ": " + str(e))
            self.status_label.set_text(f"{exported}" + _(" file(s) exported"))
        else:
            dialog.destroy()

    def _show_message(self, text, msg_type=Gtk.MessageType.ERROR):
        """Show a message dialog."""
        dialog = Gtk.MessageDialog(
            transient_for=self.parent_window,
            flags=0,
            message_type=msg_type,
            buttons=Gtk.ButtonsType.OK,
            text=text,
        )
        dialog.run()
        dialog.destroy()
