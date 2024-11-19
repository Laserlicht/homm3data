import contextlib
import typing
from PIL import Image
import builtins
from enum import IntEnum
import struct
from collections import defaultdict
import warnings

@contextlib.contextmanager
def open(file: str | typing.BinaryIO, write: bool = False):
    if isinstance(file, str):
        file = builtins.open(file, ("w" if write else "r") + "b")
    obj = DefFile(file)
    try:
        yield obj
    finally:
        file.close()

class DefFile:
    def __init__(self, file: typing.BinaryIO):
        self.__file = file
        self.__parse()

    def __parse(self):
        self.__type, self.__width, self.__height, self.__block_count = struct.unpack("<IIII", self.__file.read(16))
        self.__type = self.FileType(self.__type)

        self.__palette = []
        for i in range(256):
            r, g, b = struct.unpack("<BBB", self.__file.read(3))
            self.__palette.append((r, g, b))
        
        self.__offsets = defaultdict(list)
        self.__file_names = defaultdict(list)
        for i in range(self.__block_count):
            group_id, image_count, _, _ = struct.unpack("<IIII", self.__file.read(16))
    
            for j in range(image_count):
                name, = struct.unpack("13s", self.__file.read(13))
                self.__file_names[group_id].append(name.split(b'\x00', 1)[0].decode())
            for j in range(image_count):
                offset, = struct.unpack("<I", self.__file.read(4))
                self.__offsets[group_id].append(offset)
        
        self.__raw_data = [
                {
                    "group_id": group_id,
                    "image_id": image_id,
                    "offset": offset,
                    "name": self.__file_names[group_id][image_id],
                }
                for group_id, image_ids in self.__offsets.items() for image_id, offset in enumerate(image_ids)
        ]

        for data in self.__raw_data:
            data["image"] = self.__get_image_data(data["offset"], data["name"])
    
    def __get_image_data(self, offset: int, name: str):
        self.__file.seek(offset)
        # width must be multiple of 16
        size, format, full_width, full_height, width, height, margin_left, margin_top = struct.unpack("<IIIIIIii", self.__file.read(32))
        pixeldata = b""

        if margin_left > full_width or margin_top > full_height:
            warnings.warn("Image %s - margins exceed dimensions" % name)
            return None
        
        # SGTWMTA.def and SGTWMTB.def fail here
        # they have inconsistent left and top margins
        # they seem to be unused
        if width == 0 or height == 0:
            warnings.warn("Image %s - no image size" % name)
            return None

        match format:
            case 0:
                pixeldata = self.__file.read(width * height)
            case 1:
                line_offsets = struct.unpack("<" + "I" * height, self.__file.read(4 * height))
                for line_offset in line_offsets:
                    self.__file.seek(offset + 32 + line_offset)
                    total_length = 0
                    while total_length < width:
                        code, length = struct.unpack("<BB", self.__file.read(2))
                        length += 1
                        if code == 0xff: # contains raw data
                            pixeldata += self.__file.read(length)
                        else: # contains rle
                            pixeldata += str.encode(length * chr(code))
                        total_length += length
            case 2:
                line_offsets = struct.unpack("<%dH" % height, self.__file.read(2 * height))
                struct.unpack("<BB", self.__file.read(2)) # not known
                for line_offset in line_offsets:
                    if self.__file.tell() != offset + 32 + line_offset:
                        warnings.warn("Image %s - not expected offset: %d should be %d" % (name, self.__file.tell(), offset + 32 + line_offset))
                        self.__file.seek(offset + 32 + line_offset)
                    total_length = 0
                    while total_length < width:
                        segment, = struct.unpack("<B", self.__file.read(1))
                        code = segment >> 5
                        length = (segment & 0x1f) + 1
                        if code == 7: # contains raw data
                            pixeldata += self.__file.read(length)
                        else: # contains rle data
                            pixeldata += str.encode(length * chr(code))
                        total_length += length
            case 3:
                # each row is split into 32 byte long blocks which are individually encoded
                # two bytes store the offset for each block per line 
                line_offsets = [struct.unpack("<" + "H" * int(width / 32), self.__file.read(int(width / 16))) for i in range(height)]
                for line_offset in line_offsets:
                    for i in line_offset:
                        if self.__file.tell() != offset + 32 + i:
                            warnings.warn("Image %s - not expected offset: %d should be %d" % (name, self.__file.tell(), offset + 32 + i))
                            self.__file.seek(offset + 32 + i)
                        total_length = 0
                        while total_length < 32:
                            segment, = struct.unpack("<B", self.__file.read(1))
                            code = segment >> 5
                            length = (segment & 0x1f) + 1
                            if code == 7: # contains raw data
                                pixeldata += self.__file.read(length)
                            else: # contains rle data
                                pixeldata += str.encode(length * chr(code))
                            total_length += length
            case _:
                warnings.warn("Image %s - unknown format %d" % (name, format))
                return None

        return {
            "size": size,
            "format": format,
            "full_width": full_width,
            "full_height": full_height,
            "width": width,
            "height": height,
            "margin_left": margin_left,
            "margin_top": margin_top,
            "pixeldata": pixeldata
        }

    class FileType(IntEnum):
        SPELL = 0x40,
        SPRITE = 0x41,
        CREATURE = 0x42,
        MAP = 0x43,
        MAP_HERO = 0x44,
        TERRAIN = 0x45,
        CURSOR = 0x46,
        INTERFACE = 0x47,
        SPRITE_FRAME = 0x48,
        BATTLE_HERO = 0x49

    def read(self, group_id: int=None, image_id: int=None, name: str=None) -> Image.Image:
        # TODO: name/group/image handling
        return Image.new(mode="RGB", size=(200, 200))
    
    def get_size(self) -> tuple[int, int]:
        return (self.__width, self.__height)
    
    def get_block_count(self) -> int:
        return self.__block_count
    
    def get_type(self) -> FileType:
        return self.__type
    
    def get_palette(self) -> list[tuple[int, int, int]]:
        return self.__palette
    
    def get_raw_data(self) -> dict:
        return self.__raw_data
