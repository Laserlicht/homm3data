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
