import contextlib
import typing
from PIL import Image
import builtins
from enum import IntEnum
import struct
from collections import defaultdict

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
            block_id, image_count, _, _ = struct.unpack("<IIII", self.__file.read(16))
    
            for j in range(image_count):
                name, = struct.unpack("13s", self.__file.read(13))
                self.__file_names[block_id].append(name.split(b'\x00', 1)[0].decode())
            for j in range(image_count):
                offset, = struct.unpack("<I", self.__file.read(4))
                self.__offsets[block_id].append(offset)

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

    def read(self, group: int, number: int) -> Image.Image:
        return Image.new(mode="RGB", size=(200, 200))
    
    def get_size(self) -> tuple[int, int]:
        return (self.__width, self.__height)
    
    def get_block_count(self) -> int:
        return self.__blocks
    
    def get_type(self) -> FileType:
        return self.__type
    
    def get_palette(self) -> list[tuple[int, int, int]]:
        return self.__palette
