"""
Utility functions for the GTK4 GUI.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf
from PIL import Image
import io
import numpy as np


def pil_to_pixbuf(image: Image.Image) -> GdkPixbuf.Pixbuf:
    """Convert a PIL Image to a GdkPixbuf for display in GTK."""
    if image is None:
        return None

    if image.mode == 'P':
        image = image.convert('RGBA')
    elif image.mode == 'RGB':
        image = image.convert('RGBA')
    elif image.mode == 'L':
        image = image.convert('RGBA')
    elif image.mode != 'RGBA':
        image = image.convert('RGBA')

    arr = np.array(image)
    h, w, channels = arr.shape
    has_alpha = channels == 4

    data = arr.tobytes()
    pixbuf = GdkPixbuf.Pixbuf.new_from_data(
        data, GdkPixbuf.Colorspace.RGB,
        has_alpha, 8, w, h,
        w * channels
    )
    # Copy to ensure data lifetime
    return pixbuf.copy()


def scale_pixbuf_fit(pixbuf: GdkPixbuf.Pixbuf, max_width: int, max_height: int) -> GdkPixbuf.Pixbuf:
    """Scale pixbuf to fit within max dimensions while maintaining aspect ratio."""
    if pixbuf is None:
        return None
    w = pixbuf.get_width()
    h = pixbuf.get_height()
    if w <= max_width and h <= max_height:
        return pixbuf

    scale = min(max_width / w, max_height / h)
    new_w = max(int(w * scale), 1)
    new_h = max(int(h * scale), 1)
    return pixbuf.scale_simple(new_w, new_h, GdkPixbuf.InterpType.BILINEAR)


def get_checkerboard_pixbuf(width: int, height: int, cell_size: int = 8) -> GdkPixbuf.Pixbuf:
    """Create a checkerboard pattern pixbuf for transparency background."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            if ((x // cell_size) + (y // cell_size)) % 2 == 0:
                arr[y, x] = [200, 200, 200]
            else:
                arr[y, x] = [255, 255, 255]
    data = arr.tobytes()
    return GdkPixbuf.Pixbuf.new_from_data(
        data, GdkPixbuf.Colorspace.RGB,
        False, 8, width, height, width * 3
    ).copy()
