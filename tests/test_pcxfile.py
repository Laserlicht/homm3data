from homm3data import pcxfile, lodfile
from io import BytesIO

def test_pcx():
    with lodfile.open("tests/files/h3bitmap.lod") as lod:
        data = lod.get_file("aishield.pcx")
        
        assert pcxfile.is_pcx(data)
        assert pcxfile.is_pcx(BytesIO(data))

        assert pcxfile.read_pcx(data).width == 144
        assert pcxfile.read_pcx(BytesIO(data)).width == 144