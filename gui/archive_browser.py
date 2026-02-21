"""
Archive browser mode for LOD and PAK files.
Provides a file browser-like UI with add/remove, sidebar preview,
and drag & drop support.
"""
import gi
gi.require_version('Gtk', '4.0')
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
        # Toolbar (using Gtk.Box with Buttons)
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        toolbar.add_css_class("primary-toolbar")

        btn_open = self._make_toolbar_button("document-open", _("Open"), self._on_open)
        toolbar.append(btn_open)

        btn_save = self._make_toolbar_button("document-save", _("Save"), self._on_save)
        toolbar.append(btn_save)

        btn_save_as = self._make_toolbar_button("document-save-as", _("Save As"), self._on_save_as)
        toolbar.append(btn_save_as)

        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        btn_add = self._make_toolbar_button("list-add", _("Add"), self._on_add_files)
        toolbar.append(btn_add)

        btn_remove = self._make_toolbar_button("list-remove", _("Remove"), self._on_remove_files)
        toolbar.append(btn_remove)

        btn_extract = self._make_toolbar_button("document-save", _("Export"), self._on_extract_files)
        toolbar.append(btn_extract)

        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        btn_new_lod = self._make_toolbar_button("document-new", _("New LOD"), self._on_new_lod)
        toolbar.append(btn_new_lod)

        self.append(toolbar)

        # Main paned area
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(400)
        paned.set_vexpand(True)

        # Left: file list
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search..."))
        self.search_entry.connect("search-changed", self._on_search_changed)
        left_box.append(self.search_entry)

        # File list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

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

        scrolled.set_child(self.file_tree)
        left_box.append(scrolled)

        # Context menu via GestureClick
        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self._on_file_right_click)
        self.file_tree.add_controller(gesture)

        # Status bar
        self.status_label = Gtk.Label(label=_("No archive loaded"))
        self.status_label.set_xalign(0)
        self.status_label.set_margin_start(4)
        self.status_label.set_margin_bottom(4)
        left_box.append(self.status_label)

        paned.set_start_child(left_box)
        paned.set_resize_start_child(True)
        paned.set_shrink_start_child(False)

        # Right: preview
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right_box.set_margin_start(4)

        preview_label = Gtk.Label(label=_("Preview"))
        preview_label.set_xalign(0)
        preview_label.add_css_class("dim-label")
        preview_label.set_margin_start(4)
        preview_label.set_margin_top(4)
        right_box.append(preview_label)

        preview_scroll = Gtk.ScrolledWindow()
        preview_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        preview_scroll.set_vexpand(True)

        self.preview_stack = Gtk.Stack()
        self.preview_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Image preview
        self.preview_image = Gtk.Picture()
        self.preview_image.set_halign(Gtk.Align.CENTER)
        self.preview_image.set_valign(Gtk.Align.CENTER)
        self.preview_image.set_hexpand(False)
        self.preview_image.set_vexpand(False)
        self.preview_image.set_can_shrink(False)
        self.preview_stack.add_named(self.preview_image, "image")

        # Text preview
        text_scroll = Gtk.ScrolledWindow()
        text_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.preview_text = Gtk.TextView()
        self.preview_text.set_editable(False)
        self.preview_text.set_monospace(True)
        self.preview_text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_scroll.set_child(self.preview_text)
        self.preview_stack.add_named(text_scroll, "text")

        # Empty preview
        empty_label = Gtk.Label(label=_("Select a file\nfor preview"))
        empty_label.set_justify(Gtk.Justification.CENTER)
        empty_label.add_css_class("dim-label")
        self.preview_stack.add_named(empty_label, "empty")

        self.preview_stack.set_visible_child_name("empty")
        preview_scroll.set_child(self.preview_stack)
        right_box.append(preview_scroll)

        paned.set_end_child(right_box)
        paned.set_resize_end_child(True)
        paned.set_shrink_end_child(False)

        self.append(paned)

        # Set up drag & drop
        self._setup_dnd()

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

    def _setup_dnd(self):
        """Set up drag & drop support."""
        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.set_gtypes([Gio.File])
        drop_target.connect("drop", self._on_drop)
        self.file_tree.add_controller(drop_target)

    def _on_drop(self, target, value, x, y):
        """Handle files dropped onto the file list."""
        if self.archive is None:
            self._show_message(_("Please open or create an archive first."))
            return False

        if isinstance(value, Gio.File):
            filepath = value.get_path()
            if filepath and os.path.isfile(filepath):
                filename = os.path.basename(filepath)
                with open(filepath, "rb") as f:
                    file_data = f.read()
                if self.archive_type == 'lod':
                    self.archive.add_file(filename, file_data)
                self._refresh_file_list()
            return True
        return False

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

    def _on_file_right_click(self, gesture, n_press, x, y):
        """Handle right-click on a file for context menu."""
        result = self.file_tree.get_path_at_pos(int(x), int(y))
        if result is None:
            return

        path, column, cell_x, cell_y = result

        # Select the row if not already selected
        selection = self.file_tree.get_selection()
        if not selection.path_is_selected(path):
            selection.unselect_all()
            selection.select_path(path)

        model, paths = selection.get_selected_rows()
        if not paths:
            return
        iter_ = model.get_iter(paths[0])
        if iter_ is None:
            return
        filename = model.get_value(iter_, 0)
        ext = os.path.splitext(filename)[1].lower()

        # Build a Gio.Menu for the popover
        menu_model = Gio.Menu()
        has_items = False

        if ext in ('.def', '.d32'):
            menu_model.append(_("Open in DEF Editor"), "ctx.open-def")
            has_items = True
        elif ext in ('.pcx', '.p32'):
            menu_model.append(_("Open in PCX Converter"), "ctx.open-pcx")
            has_items = True

        if not has_items:
            return

        # Create action group
        action_group = Gio.SimpleActionGroup()

        action_def = Gio.SimpleAction.new("open-def", None)
        action_def.connect("activate", lambda *_: self._open_file_in_editor(filename))
        action_group.add_action(action_def)

        action_pcx = Gio.SimpleAction.new("open-pcx", None)
        action_pcx.connect("activate", lambda *_: self._open_file_in_editor(filename))
        action_group.add_action(action_pcx)

        self.file_tree.insert_action_group("ctx", action_group)

        popover = Gtk.PopoverMenu.new_from_model(menu_model)
        popover.set_parent(self.file_tree)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.popup()

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
                        self.preview_image.set_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
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
                        self.preview_image.set_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
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
                    self.preview_image.set_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
                    self.preview_stack.set_visible_child_name("image")
                    return
        except Exception:
            pass

        self.preview_stack.set_visible_child_name("empty")

    def _on_open(self, button):
        """Open a LOD or PAK file."""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Open Archive"))

        filter_all = Gtk.FileFilter()
        filter_all.set_name(_("H3 Archives (LOD, PAK)"))
        filter_all.add_pattern("*.lod")
        filter_all.add_pattern("*.LOD")
        filter_all.add_pattern("*.pak")
        filter_all.add_pattern("*.PAK")

        filter_lod = Gtk.FileFilter()
        filter_lod.set_name(_("LOD Files"))
        filter_lod.add_pattern("*.lod")
        filter_lod.add_pattern("*.LOD")

        filter_pak = Gtk.FileFilter()
        filter_pak.set_name(_("PAK Files"))
        filter_pak.add_pattern("*.pak")
        filter_pak.add_pattern("*.PAK")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_all)
        filters.append(filter_lod)
        filters.append(filter_pak)
        dialog.set_filters(filters)

        dialog.open(self.parent_window, None, self._on_open_finish)

    def _on_open_finish(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
            if gfile:
                filepath = gfile.get_path()
                self._load_archive(filepath)
        except GLib.Error:
            pass

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
                self._show_message(_("Saved: ") + self.archive_path, is_error=False)
            except Exception as e:
                self._show_message(_("Error saving: ") + str(e))
        else:
            self._on_save_as(button)

    def _on_save_as(self, button):
        """Save the archive to a new file."""
        if self.archive is None:
            self._show_message(_("No archive loaded"))
            return

        dialog = Gtk.FileDialog()
        dialog.set_title(_("Save Archive"))

        if self.archive_type == 'lod':
            dialog.set_initial_name("archive.lod")
        else:
            dialog.set_initial_name("archive.pak")

        dialog.save(self.parent_window, None, self._on_save_as_finish)

    def _on_save_as_finish(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
            if gfile:
                filepath = gfile.get_path()
                self.archive.save(filepath)
                self.archive_path = filepath
                self.parent_window.set_title(f"H3 Data Editor — {os.path.basename(filepath)}")
                self._show_message(_("Saved: ") + filepath, is_error=False)
        except GLib.Error:
            pass
        except Exception as e:
            self._show_message(_("Error saving: ") + str(e))

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

        dialog = Gtk.FileDialog()
        dialog.set_title(_("Add Files"))
        dialog.open_multiple(self.parent_window, None, self._on_add_files_finish)

    def _on_add_files_finish(self, dialog, result):
        try:
            gfiles = dialog.open_multiple_finish(result)
            if gfiles is None:
                return
            added = 0
            for i in range(gfiles.get_n_items()):
                gfile = gfiles.get_item(i)
                filepath = gfile.get_path()
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
        except GLib.Error:
            pass

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

        # Confirm deletion with AlertDialog
        alert = Gtk.AlertDialog()
        alert.set_message(f"{len(filenames)} " + _("Remove files?"))
        alert.set_detail(_("This action cannot be undone."))
        alert.set_buttons([_("Cancel"), _("Remove")])
        alert.set_cancel_button(0)
        alert.set_default_button(1)
        alert.choose(self.parent_window, None, self._on_remove_confirm, filenames)

    def _on_remove_confirm(self, alert, result, filenames):
        try:
            choice = alert.choose_finish(result)
            if choice == 1:  # "Remove" button
                for filename in filenames:
                    if self.archive_type == 'lod':
                        self.archive.remove_file(filename)
                    elif self.archive_type == 'pak':
                        self.archive.remove_sheet(filename)
                self._refresh_file_list()
        except GLib.Error:
            pass

    def _on_extract_files(self, button):
        """Extract selected files from the archive."""
        if self.archive is None:
            return

        selection = self.file_tree.get_selection()
        model, paths = selection.get_selected_rows()
        if not paths:
            self._show_message(_("No files selected."))
            return

        dialog = Gtk.FileDialog()
        dialog.set_title(_("Export to..."))
        dialog.select_folder(self.parent_window, None, self._on_extract_folder_selected, model, paths)

    def _on_extract_folder_selected(self, dialog, result, model, paths):
        try:
            gfile = dialog.select_folder_finish(result)
            if gfile is None:
                return
            output_dir = gfile.get_path()
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
        except GLib.Error:
            pass

    def _show_message(self, text, is_error=True):
        """Show a message dialog."""
        alert = Gtk.AlertDialog()
        alert.set_message(text)
        alert.set_buttons(["OK"])
        alert.show(self.parent_window)
