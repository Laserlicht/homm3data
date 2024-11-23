import contextlib
import typing
from PIL import Image
import builtins
from enum import IntEnum
import struct
from collections import defaultdict
import warnings
import numpy as np
from io import BytesIO

@contextlib.contextmanager
def open(file: str | typing.BinaryIO):
    """
    Open a Heroes III DEF file. Avoid using DefFile class directly

    Args:
        file (str | BinaryIO): The file as filepath or file like object
    """
    if isinstance(file, str):
        file = builtins.open(file, "rb")
    obj = DefFile(file)
    try:
        yield obj
    finally:
        file.close()

class DefFile:
    """
    Class for DEF handling. Use open() and avoid using directly.
    """
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
            "has_shadow": self.__type not in [self.FileType.SPELL, self.FileType.TERRAIN, self.FileType.CURSOR, self.FileType.INTERFACE],
            "pixeldata": pixeldata
        }
    
    def __get_image(self, data: typing.ByteString, width: int, height: int, full_width: int, full_height: int, margin_left: int, margin_top: int, has_shadow: bool, how: str):
        img_p = Image.frombytes('P', (width, height), data)
        palette = [item for sub_list in self.__palette for item in sub_list] # flatten
        img_p.putpalette(palette)
        img_rgb = img_p.convert("RGBA")
        pix_rgb = np.array(img_rgb)
        pix_p = np.array(img_p)

        # replace special colors
        # 0 -> (0,0,0,0)    = full transparency
        # 1 -> (0,0,0,0x40) = shadow border
        # 2 -> Normal Pixeldata
        # 3 -> Normal Pixeldata
        # 4 -> (0,0,0,0x80) = shadow body
        # 5 -> (0,0,0,0)    = selection highlight, treat as full transparency
        # 6 -> (0,0,0,0x80) = shadow body below selection, treat as shadow body
        # 7 -> (0,0,0,0x40) = shadow border below selection, treat as shadow border
        # >7 -> Normal Pixeldata

        has_overlay = has_shadow and self.__palette[5] == (255, 255, 0) and (pix_p == 5).sum() > 0
        
        match how:
            case "combined":
                pix_rgb[pix_p == 0] = (0, 0, 0, 0)
                if has_shadow:
                    pix_rgb[pix_p == 1] = (0, 0, 0, 0x40)
                    pix_rgb[pix_p == 4] = (0, 0, 0, 0x80)
                    if has_overlay:
                        pix_rgb[pix_p == 5] = (0, 0, 0, 0)
                    pix_rgb[pix_p == 6] = (0, 0, 0, 0x80)
                    pix_rgb[pix_p == 7] = (0, 0, 0, 0x40)
            case "normal":
                pix_rgb[pix_p == 0] = (0, 0, 0, 0)
                if has_shadow:
                    pix_rgb[pix_p == 1] = (0, 0, 0, 0)
                    pix_rgb[pix_p == 4] = (0, 0, 0, 0)
                    if has_overlay:
                        pix_rgb[pix_p == 5] = (0, 0, 0, 0)
                    pix_rgb[pix_p == 6] = (0, 0, 0, 0)
                    pix_rgb[pix_p == 7] = (0, 0, 0, 0)
            case "shadow":
                if not has_shadow:
                    return None
                pix_rgb[pix_p == 0] = (0, 0, 0, 0)
                pix_rgb[pix_p == 1] = (0, 0, 0, 0x40)
                pix_rgb[pix_p == 2] = (0, 0, 0, 0)
                pix_rgb[pix_p == 3] = (0, 0, 0, 0)
                pix_rgb[pix_p == 4] = (0, 0, 0, 0x80)
                pix_rgb[pix_p == 5] = (0, 0, 0, 0)
                pix_rgb[pix_p == 6] = (0, 0, 0, 0x80)
                pix_rgb[pix_p == 7] = (0, 0, 0, 0x40)
                pix_rgb[pix_p > 7] = (0, 0, 0, 0)
            case "overlay":
                if not has_overlay:
                    return None
                pix_rgb[pix_p == 0] = (0, 0, 0, 0)
                pix_rgb[pix_p == 1] = (0, 0, 0, 0)
                pix_rgb[pix_p == 2] = (0, 0, 0, 0)
                pix_rgb[pix_p == 3] = (0, 0, 0, 0)
                pix_rgb[pix_p == 4] = (0, 0, 0, 0)
                pix_rgb[pix_p == 5] = (255, 255, 255, 255)
                pix_rgb[pix_p == 6] = (255, 255, 255, 255)
                pix_rgb[pix_p == 7] = (255, 255, 255, 255)
                pix_rgb[pix_p > 7] = (0, 0, 0, 0)
            case _:
                warnings.warn("Unknown how %s" % how)
                return None
        img_rgb = Image.fromarray(pix_rgb)
        img = Image.new('RGBA', (full_width, full_height), (0, 0, 0, 0))
        img.paste(img_rgb, (margin_left, margin_top))
        return img
    
    def __create_header(self) -> typing.ByteString:
        file = BytesIO()

        data = self.__raw_data

        file.write(struct.pack("<IIII", int(self.__type), self.__width, self.__height, self.__block_count))
        for i in range(256):
            file.write(struct.pack("<BBB", self.__palette[i][0], self.__palette[i][1], self.__palette[i][2]))

        data.sort(key=lambda k: (k["group_id"], k["image_id"]))
        group_id = None
        for i, d in enumerate(data):
            if d["group_id"] != group_id:
                image_count = max([x["image_id"] for x in data if x["group_id"] == d["group_id"]]) + 1
                file.write(struct.pack("<IIII", d["group_id"], image_count, 0, 0))

                for j in range(image_count):
                    name = data[i + j]["name"].encode()
                    while len(name) < 13:
                        name += b"\x00"
                    file.write(struct.pack("13s", name))
                for j in range(image_count):
                    file.write(struct.pack("<I", data[i + j]["offset"]))

                group_id = d["group_id"]
        
        file.seek(0)
        return file.read()

    def __recalculate_size_offset(self) -> list[dict[str, typing.Any]]:
        start = len(self.__create_header())
        data = self.__raw_data
        data.sort(key=lambda k: k["offset"])
        for d in data:
            length = len(d["image"]["pixeldata"])
            d["image"]["format"] = 0
            d["image"]["size"] = length
            d["offset"] = start
            start += length + 32
        return data

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

    def read_image(self, how: typing.Literal['combined', 'normal', 'shadow', 'overlay']="combined", group_id: int=None, image_id: int=None, name: str=None) -> Image.Image:
        """
        Read image as PIL image. Combination of parameters `group_id`, `image_id`, `name` has to be unique. If not required to make unique some of them can skipped.

        Args:
            how (str): Selection of desired layers: `combined` for all, `normal` only for unlayered, `shadow` for shadow and `overlay` for outlines. If desired layer not exists it returns None.
            group_id (str): The group id of the requested file
            image_id (str): The image id of the requested file
            name (str): The filename of the requested file

        Returns:
            Image: File as PIL image. None if file or layer not found.
        """
        found_data = [
            value for value in self.__raw_data if
            (group_id is None or value["group_id"] == group_id) and
            (image_id is None or value["image_id"] == image_id) and
            (name is None or value["name"] == name)
        ]

        if len(found_data) != 1:
            warnings.warn("Image read unsuccessful. Found %d images with filter criteria." % len(found_data))
            return None
        found_data = found_data[0]
        
        return self.__get_image(
            found_data["image"]["pixeldata"],
            found_data["image"]["width"],
            found_data["image"]["height"],
            found_data["image"]["full_width"],
            found_data["image"]["full_height"],
            found_data["image"]["margin_left"],
            found_data["image"]["margin_top"],
            found_data["image"]["has_shadow"],
            how
        )

    def save(self, file: str | typing.BinaryIO):
        """
        Write data from file (currently only for testing)

        Args:
            file (str | BinaryIO): The file as filepath or file like object
        """
        if isinstance(file, str):
            file = builtins.open(file, "wb")

        data = self.__recalculate_size_offset()
        file.write(self.__create_header())
        
        data.sort(key=lambda k: k["offset"])
        for d in data:
            file.write(struct.pack("<IIIIIIii", d["image"]["size"], d["image"]["format"], d["image"]["full_width"], d["image"]["full_height"], d["image"]["width"], d["image"]["height"], d["image"]["margin_left"], d["image"]["margin_top"]))
            file.write(d["image"]["pixeldata"])


    def get_size(self) -> tuple[int, int]:
        """
        Get image size (max img of def)

        Returns:
            tuple: Width and height as tuple.
        """
        return (self.__width, self.__height)
    
    def get_block_count(self) -> int:
        """
        Get amount of blocks

        Returns:
            int: block count
        """
        return self.__block_count
    
    def get_groups(self) -> list[int]:
        """
        Get list of aviable groups

        Returns:
            list[int]: list of groups
        """
        return list(dict.fromkeys([value["group_id"] for value in self.__raw_data]))
    
    def get_frame_count(self, group_id: int) -> int:
        """
        Get amount of frames in group (group id)

        Args:
            group_id (str): The group id for the frame count

        Returns:
            int: frame count
        """
        found_data = [
            value for value in self.__raw_data if value["group_id"] == group_id
        ]
        return len(found_data)
    
    def get_type(self) -> FileType:
        """
        Get Type of def

        Returns:
            FileType: Type of def
        """
        return self.__type
    
    def get_palette(self) -> list[tuple[int, int, int]]:
        """
        Get palette

        Returns:
            list[tuple[int, int, int]]: List of tuple with 3 elements (rgb)
        """
        return self.__palette
    
    def get_raw_data(self) -> dict:
        """
        Get internal structure of loaded def

        Returns:
            dict: Object with internal structure
        """
        return self.__raw_data
