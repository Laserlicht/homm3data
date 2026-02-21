import struct
from PIL import Image
import typing
import io
import numpy as np

def is_pcx(file: str | bytes | typing.BinaryIO) -> bool:
    """
    Checks if file is Heroes III PCX file.

    Args:
        file (str | bytes | BinaryIO): The file as filepath, bytes or file like object

    Returns:
        bool: True if file is pcx, False otherwise.
    """
    if isinstance(file, io.IOBase):
        data = file.read()
    elif isinstance(file, str):
        with open(file, "rb") as f:
            data = f.read()
    else:
        data = file

    (magic,) = struct.unpack("<I", data[:4])
    if magic == 0x46323350: #p32 format from HotA
        return True

    size, width, height = struct.unpack("<III", data[:12])
    return size == width * height or size == width * height * 3

def read_pcx(file: str | bytes | typing.BinaryIO) -> Image.Image:
    """
    Reads in a Heroes III PCX file as PIL image.

    Args:
        file (str | bytes | BinaryIO): The file as filepath, bytes or file like object

    Returns:
        bool: Image as PIL image, None if failed.
    """
    if isinstance(file, io.IOBase):
        data = file.read()
    elif isinstance(file, str):
        with open(file, "rb") as f:
            data = f.read()
    else:
        data = file

    (magic,) = struct.unpack("<I", data[:4])
    if magic == 0x46323350: #p32 format from HotA
        (magic, unknown1, bits_per_pixel, size_raw, size_header, size_data, width, height, unknown8, unknown9) = struct.unpack('<10I', data[:40])
        assert magic == 0x46323350
        assert size_header == 40
        assert size_raw == size_header + size_data
        assert size_data == width * height * bits_per_pixel / 8
        assert bits_per_pixel == 32
        assert unknown1 == 0
        assert unknown8 == 8
        assert unknown9 == 0
        arr = np.frombuffer(data[40:], dtype=np.uint8).reshape((height, width, 4))
        arr = arr[:, :, [2, 1, 0, 3]] # Swap channels: BGRA -> RGBA
        im = Image.fromarray(arr, 'RGBA')
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
        return im

    size, width, height = struct.unpack("<III", data[:12])
    if size == width * height:
        im = Image.frombytes('P', (width, height), data[12:12 + width * height])
        palette = []
        for i in range(256):
            offset = 12 + width * height + i * 3
            r, g, b = struct.unpack("<BBB", data[offset:offset + 3])
            palette.extend((r, g, b))
        im.putpalette(palette)
        return im
    elif size == width * height * 3:
        im = Image.frombytes("RGB", (width, height), data[12:])
        b, g, r = im.split()
        im = Image.merge("RGB", (r, g, b))
        return im
    else:
        return None


def write_pcx(image: Image.Image, mode: str = "rgb") -> bytes:
    """
    Encode a PIL image as Heroes III PCX format.

    Args:
        image (Image.Image): PIL image to encode
        mode (str): "rgb" for 24-bit RGB, "palette" for 8-bit palettized

    Returns:
        bytes: PCX file data
    """
    if mode == "palette":
        return _write_pcx_palette(image)
    elif mode == "rgb":
        return _write_pcx_rgb(image)
    else:
        raise ValueError("mode must be 'rgb' or 'palette', got: %s" % mode)


def _write_pcx_rgb(image: Image.Image) -> bytes:
    """Encode as 24-bit RGB PCX."""
    if image.mode != "RGB":
        image = image.convert("RGB")

    width, height = image.size
    r, g, b = image.split()
    # H3 PCX stores as BGR
    im_bgr = Image.merge("RGB", (b, g, r))
    pixel_data = im_bgr.tobytes()

    size = width * height * 3
    header = struct.pack("<III", size, width, height)
    return header + pixel_data


def _write_pcx_palette(image: Image.Image) -> bytes:
    """Encode as 8-bit palettized PCX."""
    if image.mode == "P":
        img_p = image
    elif image.mode in ("RGB", "RGBA"):
        img_p = image.quantize(colors=256)
    else:
        img_p = image.convert("RGB").quantize(colors=256)

    width, height = img_p.size
    pixel_data = img_p.tobytes()
    size = width * height

    # Get palette (expand to 256 * 3 bytes)
    palette = img_p.getpalette()
    if palette is None:
        palette = [0] * 768
    while len(palette) < 768:
        palette.append(0)

    palette_bytes = b''
    for i in range(256):
        palette_bytes += struct.pack("<BBB", palette[i * 3], palette[i * 3 + 1], palette[i * 3 + 2])

    header = struct.pack("<III", size, width, height)
    return header + pixel_data + palette_bytes


def write_p32(image: Image.Image) -> bytes:
    """
    Encode a PIL image as HotA P32 format (32-bit BGRA).

    Args:
        image (Image.Image): PIL image to encode

    Returns:
        bytes: P32 file data
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    width, height = image.size
    # Flip vertically (P32 is bottom-up)
    image = image.transpose(Image.FLIP_TOP_BOTTOM)

    arr = np.array(image)
    # RGBA -> BGRA
    arr = arr[:, :, [2, 1, 0, 3]]
    pixel_data = arr.tobytes()

    size_data = width * height * 4
    size_header = 40
    size_raw = size_header + size_data
    bits_per_pixel = 32

    header = struct.pack('<10I',
        0x46323350,  # magic "P32F"
        0,           # unknown1
        bits_per_pixel,
        size_raw,
        size_header,
        size_data,
        width,
        height,
        8,           # unknown8
        0,           # unknown9
    )
    return header + pixel_data
