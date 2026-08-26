import contextlib
import typing
import builtins
import struct
import warnings
import zlib
import gzip
import lzma

@contextlib.contextmanager
def open(file: str | typing.BinaryIO):
    """
    Open a Heroes III LOD file. Avoid using LodFile class directly

    Args:
        file (str | BinaryIO): The file as filepath or file like object
    """
    if isinstance(file, str):
        file = builtins.open(file, "rb")
    obj = LodFile(file)
    try:
        yield obj
    finally:
        file.close()

class LodFile:
    """
    Class for LOD handling. Use open() and avoid using directly.
    """
    def __init__(self, file: typing.BinaryIO):
        self.__file = file
        self.__parse()

    def __xor_decrypt(self, data, key):
        key_len = len(key)
        decrypted_data = bytes(
            data[i] ^ key[i % key_len]
            for i in range(len(data))
        )
        return decrypted_data

    def __extract_first_lzma_stream(self, data: bytes) -> bytes:
        """
        Extracts the first raw LZMA stream found at offset 1
        using parameters reported by binwalk.

        Returns decompressed bytes.
        """

        offset = 1  # from binwalk

        filters = [{
            "id": lzma.FILTER_LZMA1,
            "dict_size": 262144,  # 256 KiB
            "lc": 3,
            "lp": 0,
            "pb": 2,
        }]

        decompressor = lzma.LZMADecompressor(
            format=lzma.FORMAT_RAW,
            filters=filters
        )

        return decompressor.decompress(data[offset:])

def __looks_like_hota_18(self, total, key):
    current = self.__file.tell()

    try:
        self.__file.seek(80)

        for _ in range(min(total, 8)):
            file_id = self.__file.read(16)
            encr = self.__file.read(16)

            if len(file_id) != 16 or len(encr) != 16:
                return False

            decr = self.__xor_decrypt(encr, key)
            offset, size, csize = struct.unpack("<III", decr[:12])

            # HotA compression flag is saved in encr[12]
            method = encr[12]

            if method not in (0, 2, 3):
                return False

            if offset <= 0 or size < 0 or csize < 0:
                return False

        return True
    finally:
        self.__file.seek(current)

    def __parse(self):
        header = self.__file.read(4)
        if header != b'LOD\0':
            self.__file.seek(0)
            self.__file = gzip.GzipFile(fileobj=self.__file, mode='rb') # linux files are gzipped
            header = self.__file.read(4)
            if header != b'LOD\0':
                warnings.warn("not LOD file: %s" % header)
                return None

        self.__file.seek(8)
        total, = struct.unpack("<I", self.__file.read(4))

        self.__file.seek(0x0C)
        key = self.__file.read(4)

        self.__files=[]
        self.__is_hota_18 = self.__looks_like_hota_18(total, key)
        if self.__is_hota_18: # HotA 1.8 format
            self.__file.seek(80)
            for i in range(total):
                filename, = struct.unpack("16s", self.__file.read(16))
                filename = filename.hex() # no filenames in hota 1.8 def, only unique ids
                encr = self.__file.read(16)
                decr = self.__xor_decrypt(encr, key)
                offset, size, csize = struct.unpack("<III", decr[:12])
                compression_method = encr[12]
                unknown = encr[13:16]
                self.__files.append((filename, offset, size, csize, compression_method, unknown))
        else:
            self.__file.seek(92)
            for i in range(total):
                filename, = struct.unpack("16s", self.__file.read(16))
                filename = filename[:filename.index(b'\0')].decode().lower()
                offset, size, unknown, csize = struct.unpack("<IIII", self.__file.read(16))
                self.__files.append((filename, offset, size, csize, None, unknown))

    def get_filelist(self) -> list[str]:
        """
        Get list of all files inside LOD archive

        Returns:
            list[str]: All filenames inside LOD archive.
        """
        return [x[0] for x in self.__files]
    
    def get_file(self, selected_filename) -> bytes:
        """
        Get file from LOD archive

        Args:
            selected_filename (str): The filename of the requested file

        Returns:
            bytes: File content as bytes.
        """
        selected_filename = selected_filename.lower()

        for filename, offset, size, csize, compression_method, unknown in self.__files:
            if selected_filename != filename:
                continue

            self.__file.seek(offset)
            if csize != 0:
                if self.__is_hota_18 and compression_method == 2:
                    #HotA 1.8 LOD compression methods
                    #Flag    Meaning
                    #0x00    Stored (no compression)
                    #0x03    zlib / deflate
                    #0x02    custom wrapper + LZMA-family
                    data = self.__extract_first_lzma_stream(self.__file.read(csize))
                else:
                    data = zlib.decompress(self.__file.read(csize))
            else:
                data = self.__file.read(size)
            
            return data
        
        warnings.warn("file not found: %s" % selected_filename)
        return None
