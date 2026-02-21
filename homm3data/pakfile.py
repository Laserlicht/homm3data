import contextlib
import typing
import builtins
import io
import zlib
import warnings
from PIL import Image

@contextlib.contextmanager
def open(file: str | typing.BinaryIO):
    """
    Open a Heroes III HD PAK file. Avoid using PakFile class directly

    Args:
        file (str | BinaryIO): The file as filepath or file like object
    """
    if isinstance(file, str):
        file = builtins.open(file, "rb")
    obj = PakFile(file)
    try:
        yield obj
    finally:
        file.close()

class PakFile:
    """
    Class for PAK handling. Use open() and avoid using directly.
    """
    def __init__(self, file: typing.BinaryIO):
        self.__file = file
        self.__parse()

    def __parse(self):
        self.__data = {}

        self.__file.read(4) # dummy
        info_offset = int.from_bytes(self.__file.read(4), byteorder='little')
        self.__file.seek(info_offset)
        files = int.from_bytes(self.__file.read(4), byteorder='little')
        offset_name = self.__file.tell()
        for i in range(files):
            self.__file.seek(offset_name)
            name = self.__file.read(8).split(b'\0', 1)[0].decode()
            self.__file.read(12) # dummy
            offset = int.from_bytes(self.__file.read(4), byteorder='little')
            dummy_size = int.from_bytes(self.__file.read(4), byteorder='little')
            chunks = int.from_bytes(self.__file.read(4), byteorder='little')
            zsize = int.from_bytes(self.__file.read(4), byteorder='little')
            size = int.from_bytes(self.__file.read(4), byteorder='little')
            chunk_zsize_arr = []
            for j in range(chunks):
                chunk_zsize = int.from_bytes(self.__file.read(4), byteorder='little')
                chunk_zsize_arr.append(chunk_zsize)
            chunk_size_arr = []
            for j in range(chunks):
                chunk_size = int.from_bytes(self.__file.read(4), byteorder='little')
                chunk_size_arr.append(chunk_size)
            offset_name = self.__file.tell()

            self.__file.seek(offset)
            image_config = self.__file.read(dummy_size).decode()
            offset += dummy_size

            data = bytearray(b'')
            data_compressed = bytearray(b'')
            for j in range(chunks):
                self.__file.seek(offset)
                if chunk_zsize_arr[j] == chunk_size_arr[j]:
                    data += bytearray(self.__file.read(chunk_size))
                else:
                    data_compressed += bytearray(self.__file.read(zsize))
                offset += chunk_zsize
            if len(data_compressed) != 0:
                to_decompress = data_compressed
                data_compressed = []
                while len(to_decompress) > 0:
                    dec = zlib.decompressobj()
                    try:
                        data_compressed.append(dec.decompress(to_decompress))
                        to_decompress = dec.unused_data
                    except:
                        break
                pass
            if len(data) < len(data_compressed):
                data = data_compressed
            else:
                data = [data]
            
            self.__data[name] = (image_config, data)
    
    def get_sheets(self, name: str) -> list[Image.Image]:
        """
        Get all sheets for a specified sheet name as images

        Args:
            name (str): The requested sheet name

        Returns:
            list[Image.Image]: A list of PIL images with all sheets.
        """
        for k, v in self.__data.items():
            if k.upper() == name.upper():
                return [Image.open(io.BytesIO(x)) for x in v[1]]
            
        warnings.warn("file not found: %s" % name)
        return None
      
    def get_sheets_dds(self, name: str) -> list[bytes]:
        """
        Get all sheets for a specified sheet name as dds images

        Args:
            name (str): The requested sheet name

        Returns:
            list[bytes]: A list of bytes with all sheets as dds.
        """
        for k, v in self.__data.items():
            if k.upper() == name.upper():
                return [x for x in v[1]]
            
        warnings.warn("file not found: %s" % name)
        return None
    
    def get_sheet_config(self, name: str) -> dict:
        """
        Get config param of every sprite on a specified sheet name as object

        Args:
            name (str): The requested sheet name

        Returns:
            dict: A dict (with sprite name as key) with every parameter of the sprite
        """
        for k, v in self.__data.items():
            if k.upper() == name.upper():
                ret = {}
                for line in v[0].split('\r\n'):
                    tmp = line.split(' ')
                    if len(tmp) > 11:
                        ret[tmp[0]] = {
                            "name": tmp[0],
                            "no": int(tmp[1]),
                            "x_offset_sd_hd": int(tmp[2]), # x offset between hd and sd sprites
                            "unknown_1": int(tmp[3]), # unknown
                            "y_offset_sd_hd": int(tmp[4]), # y offset between hd and sd sprites
                            "unknown_2": int(tmp[5]), # unknown
                            "x": int(tmp[6]),
                            "y": int(tmp[7]),
                            "width": int(tmp[8]),
                            "height": int(tmp[9]),
                            "rotation": int(tmp[10]),
                            "has_shadow": int(tmp[11]),
                            "shadow_no": None if int(tmp[11]) == 0 else int(tmp[12]),
                            "shadow_x": None if int(tmp[11]) == 0 else int(tmp[13]),
                            "shadow_y": None if int(tmp[11]) == 0 else int(tmp[14]),
                            "shadow_width": None if int(tmp[11]) == 0 else int(tmp[15]),
                            "shadow_height": None if int(tmp[11]) == 0 else int(tmp[16]),
                            "shadow_rotation": None if int(tmp[11]) == 0 else int(tmp[17])
                        }
                return ret
            
        warnings.warn("file not found: %s" % name)
        return None
    
    def get_sheet_config_raw(self, name: str) -> str:
        """
        Get config param of every sprite on a specified sheet name as object as raw string

        Args:
            name (str): The requested sheet name

        Returns:
            str: The raw embedded string for sheet config
        """
        for k in self.__data.keys():
            if k.upper() == name.upper():
                return k[0]
            
        warnings.warn("file not found: %s" % name)
        return None
    
    def get_sheetnames(self) -> list[str]:
        """
        Get all sheet names

        Returns:
            list: A list with all sheet names embedded in pak
        """
        return list(self.__data.keys())
    
    def get_filenames_for_sheet(self, name: str) -> list[str]:
        """
        Get all sprite names from sheet

        Args:
            name (str): The requested sheet name

        Returns:
            list: A list with all sprite names for selected sheet
        """
        for k, v in self.__data.items():
            if k.upper() == name.upper():
                ret = []
                for line in v[0].split('\r\n'):
                    tmp = line.split(' ')
                    if len(tmp) > 11:
                        img_name = tmp[0]
                        ret.append(img_name)
                return ret
        warnings.warn("file not found: %s" % name)
        return None
    
    def get_image(self, sheetname: str, imagename: str) -> tuple[Image.Image]:
        """
        Get image as PIL image

        Args:
            sheetname (str): The requested sheet name
            imagename (str): The requested image name

        Returns:
            tuple[Image.Image]: A tuple of images. First element is normal rgb image, second element is shadow image (if existing, otherwise None)
        """
        cfg = self.get_sheet_config(sheetname)
        data = self.get_sheets(sheetname)

        if cfg is not None:
            for k, v in cfg.items():
                if k.upper() == imagename.upper():
                    img_crop = data[v["no"]]
                    img_crop = img_crop.crop((v["x"], v["y"], v["x"] + v["width"], v["y"] + v["height"]))
                    img_crop = img_crop.rotate(-90 * v["rotation"], expand=True)

                    img_shadow_crop = None
                    if v["has_shadow"] == 1:
                        img_shadow_crop = data[v["shadow_no"]]
                        img_shadow_crop = img_shadow_crop.crop((v["shadow_x"], v["shadow_y"], v["shadow_x"] + v["shadow_width"], v["shadow_y"] + v["shadow_height"]))
                        img_shadow_crop = img_shadow_crop.rotate(-90 * v["shadow_rotation"], expand=True)

                    return (img_crop, img_shadow_crop)
                    
        warnings.warn("file not found: %s - %s" % (sheetname, imagename))
        return None

    def add_sheet(self, name: str, config: str, image_data: list[bytes]):
        """
        Add or replace a sheet in the PAK archive.

        Args:
            name (str): Sheet name (max 8 characters)
            config (str): Config string describing sprites on the sheet
            image_data (list[bytes]): List of image data (DDS format bytes)
        """
        name = name[:8]
        self.__data[name] = (config, image_data)

    def add_sheet_from_images(self, name: str, config: str, images: list[Image.Image], fmt: str = "PNG"):
        """
        Add or replace a sheet from PIL images.

        Args:
            name (str): Sheet name (max 8 characters)
            config (str): Config string describing sprites on the sheet
            images (list[Image.Image]): List of PIL images
            fmt (str): Image format for encoding (PNG, BMP, etc.)
        """
        data_list = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format=fmt)
            data_list.append(buf.getvalue())
        self.add_sheet(name, config, data_list)

    def remove_sheet(self, name: str):
        """
        Remove a sheet from the PAK archive.

        Args:
            name (str): The sheet name to remove
        """
        to_remove = None
        for k in self.__data.keys():
            if k.upper() == name.upper():
                to_remove = k
                break
        if to_remove:
            del self.__data[to_remove]

    def save(self, file: str | typing.BinaryIO, use_compression: bool = True):
        """
        Encode and write a PAK file.

        Args:
            file (str | BinaryIO): Output file path or file-like object
            use_compression (bool): Whether to compress chunk data with zlib
        """
        import struct as st

        close_after = False
        if isinstance(file, str):
            file = builtins.open(file, "wb")
            close_after = True

        try:
            sheets = list(self.__data.items())
            num_files = len(sheets)

            # We need to calculate the info section first to know its size
            # Then place data before it and write the info offset in the header

            # Prepare data for each sheet
            sheet_entries = []
            for name, (config, data_chunks) in sheets:
                config_bytes = config.encode('utf-8') if isinstance(config, str) else config
                chunk_data = []
                for chunk in data_chunks:
                    if isinstance(chunk, (bytearray, memoryview)):
                        chunk = bytes(chunk)
                    raw = chunk
                    if use_compression:
                        compressed = zlib.compress(raw)
                        chunk_data.append((raw, compressed))
                    else:
                        chunk_data.append((raw, raw))
                sheet_entries.append((name, config_bytes, chunk_data))

            # Layout: [header 8 bytes] [data...] [info section]
            # Header: 4 dummy bytes + 4 bytes info_offset
            current_offset = 8

            # Calculate data offsets
            data_offsets = []
            for name, config_bytes, chunk_data in sheet_entries:
                data_offsets.append(current_offset)
                current_offset += len(config_bytes)  # config string
                for raw, compressed in chunk_data:
                    current_offset += len(compressed)

            info_offset = current_offset

            # Write header
            file.write(b'\x00' * 4)  # dummy
            file.write(st.pack('<I', info_offset))

            # Write data
            for i, (name, config_bytes, chunk_data) in enumerate(sheet_entries):
                file.write(config_bytes)
                for raw, compressed in chunk_data:
                    file.write(compressed)

            # Write info section
            file.write(st.pack('<I', num_files))

            for i, (name, config_bytes, chunk_data) in enumerate(sheet_entries):
                # Name (8 bytes padded)
                name_bytes = name.encode('ascii')[:8].ljust(8, b'\x00')
                file.write(name_bytes)
                file.write(b'\x00' * 12)  # dummy

                offset = data_offsets[i]
                dummy_size = len(config_bytes)
                chunks = len(chunk_data)
                zsize = sum(len(c) for _, c in chunk_data)
                size = sum(len(r) for r, _ in chunk_data)

                file.write(st.pack('<I', offset))
                file.write(st.pack('<I', dummy_size))
                file.write(st.pack('<I', chunks))
                file.write(st.pack('<I', zsize))
                file.write(st.pack('<I', size))

                # Chunk compressed sizes
                for raw, compressed in chunk_data:
                    file.write(st.pack('<I', len(compressed)))
                # Chunk raw sizes
                for raw, compressed in chunk_data:
                    file.write(st.pack('<I', len(raw)))
        finally:
            if close_after:
                file.close()

    @classmethod
    def create(cls) -> 'PakFile':
        """
        Create a new empty PAK archive in memory.

        Returns:
            PakFile: A new empty PakFile instance
        """
        obj = cls.__new__(cls)
        obj._PakFile__file = None
        obj._PakFile__data = {}
        return obj
