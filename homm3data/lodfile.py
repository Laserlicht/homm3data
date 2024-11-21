import contextlib
import typing
import builtins
import struct
import warnings
import zlib
import gzip

@contextlib.contextmanager
def open(file: str | typing.BinaryIO):
    if isinstance(file, str):
        file = builtins.open(file, "rb")
    obj = LodFile(file)
    try:
        yield obj
    finally:
        file.close()

class LodFile:
    def __init__(self, file: typing.BinaryIO):
        self.__file = file
        self.__parse()

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
        self.__file.seek(92)

        self.__files=[]
        for i in range(total):
            filename, = struct.unpack("16s", self.__file.read(16))
            filename = filename[:filename.index(b'\0')].decode().lower()
            offset, size, _, csize = struct.unpack("<IIII", self.__file.read(16))
            self.__files.append((filename, offset, size, csize))

    def get_filelist(self) -> list[str]:
        return [x[0] for x in self.__files]
    
    def get_file(self, selected_filename) -> bytes:
        selected_filename = selected_filename.lower()

        for filename, offset, size, csize in self.__files:
            if selected_filename != filename:
                continue

            self.__file.seek(offset)
            if csize != 0:
                data = zlib.decompress(self.__file.read(csize))
            else:
                data = self.__file.read(size)
            
            return data
        
        warnings.warn("file not found: %s" % selected_filename)
        return None