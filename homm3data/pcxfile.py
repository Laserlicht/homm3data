import struct
from PIL import Image
import typing
import io

def is_pcx(file: str | bytes | typing.BinaryIO):
    if isinstance(file, io.IOBase):
        data = file.read()
    elif isinstance(file, str):
        with open(file, "rb") as f:
            data = f.read()
    else:
        data = file

    size, width, height = struct.unpack("<III", data[:12])
    return size == width * height or size == width * height * 3

def read_pcx(file: str | bytes | typing.BinaryIO):
    if isinstance(file, io.IOBase):
        data = file.read()
    elif isinstance(file, str):
        with open(file, "rb") as f:
            data = f.read()
    else:
        data = file
        
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