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
        self.__is_hota_18 = key[0] == 135
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

    def add_file(self, filename: str, data: bytes):
        """
        Add or replace a file in the LOD archive.

        Args:
            filename (str): The filename to add
            data (bytes): The file content
        """
        filename_lower = filename.lower()
        # Replace existing
        for i, (fname, offset, size, csize, compression_method, unknown) in enumerate(self.__files):
            if fname == filename_lower:
                self.__files[i] = (filename_lower, 0, len(data), 0, None, 0)
                self.__file_data[filename_lower] = data
                return
        # Add new
        self.__files.append((filename_lower, 0, len(data), 0, None, 0))
        if not hasattr(self, '_LodFile__file_data'):
            self.__file_data = {}
        self.__file_data[filename_lower] = data

    def remove_file(self, filename: str):
        """
        Remove a file from the LOD archive.

        Args:
            filename (str): The filename to remove
        """
        filename_lower = filename.lower()
        self.__files = [f for f in self.__files if f[0] != filename_lower]
        if hasattr(self, '_LodFile__file_data') and filename_lower in self.__file_data:
            del self.__file_data[filename_lower]

    def save(self, file: str | typing.BinaryIO, compress: bool = True):
        """
        Encode and write a LOD file. Only supports standard LOD format (not HotA 1.8).

        Args:
            file (str | BinaryIO): Output file path or file-like object
            compress (bool): Whether to zlib-compress file contents
        """
        close_after = False
        if isinstance(file, str):
            file = builtins.open(file, "wb")
            close_after = True

        try:
            total = len(self.__files)

            # Header: "LOD\0" + version(4 bytes) + file count (4 bytes) + padding to 92 bytes
            file.write(b'LOD\x00')
            file.write(struct.pack("<I", 200))  # version
            file.write(struct.pack("<I", total))
            file.write(b'\x00' * 80)  # padding to offset 92

            # Calculate data start position (after file table)
            file_table_size = total * 32  # 16 name + 16 metadata per file
            data_start = 92 + file_table_size

            # First pass: collect all file data and compute offsets
            entries = []
            current_offset = data_start
            for filename, orig_offset, orig_size, orig_csize, compression_method, unknown in self.__files:
                # Get actual data
                if hasattr(self, '_LodFile__file_data') and filename in self.__file_data:
                    raw_data = self.__file_data[filename]
                else:
                    raw_data = self.get_file(filename)

                if raw_data is None:
                    continue

                if compress and len(raw_data) > 0:
                    compressed = zlib.compress(raw_data)
                    if len(compressed) < len(raw_data):
                        entries.append((filename, current_offset, len(raw_data), len(compressed), compressed))
                        current_offset += len(compressed)
                    else:
                        entries.append((filename, current_offset, len(raw_data), 0, raw_data))
                        current_offset += len(raw_data)
                else:
                    entries.append((filename, current_offset, len(raw_data), 0, raw_data))
                    current_offset += len(raw_data)

            # Write file table
            for filename, offset, size, csize, data_bytes in entries:
                name_bytes = filename.encode('ascii')[:16].ljust(16, b'\x00')
                file.write(name_bytes)
                file.write(struct.pack("<IIII", offset, size, 0, csize))

            # Write file data
            for filename, offset, size, csize, data_bytes in entries:
                file.write(data_bytes)
        finally:
            if close_after:
                file.close()

    @classmethod
    def create(cls) -> 'LodFile':
        """
        Create a new empty LOD archive in memory.

        Returns:
            LodFile: A new empty LodFile instance
        """
        obj = cls.__new__(cls)
        obj._LodFile__file = None
        obj._LodFile__files = []
        obj._LodFile__is_hota_18 = False
        obj._LodFile__file_data = {}
        return obj
