from homm3data import deffile, lodfile
from io import BytesIO

def test_file_handling():
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        assert len(d.get_raw_data()) > 0

    with open("tests/files/courtyard/CTrSalamand.def", "rb") as f:
        with deffile.open(f) as d:
            assert len(d.get_raw_data()) > 0

def test_type():
    with lodfile.open("tests/files/h3sprite.lod") as lod:
        with deffile.open(BytesIO(lod.get_file("avwangl.def"))) as d:
            assert d.get_type() == deffile.DefFile.FileType.MAP

def test_read_image():
    with lodfile.open("tests/files/h3sprite.lod") as lod:
        with deffile.open(BytesIO(lod.get_file("avwangl.def"))) as d:
            assert d.get_frame_count(0) == 30
            assert d.read_image(group_id=0, image_id=0).width > 0

def test_read_image_d32():
    with lodfile.open("tests/files/HotA/Data/HotA.lod") as lod:
        with deffile.open(BytesIO(lod.get_file("i_ok67.d32"))) as d:
            assert d.get_frame_count(0) == 3
            assert d.read_image(group_id=0, image_id=0).width == 67
    with lodfile.open("tests/files/HotA/Data/HotA.lod") as lod:
        with deffile.open(BytesIO(lod.get_file("COUATL.def"))) as d:
            assert d.get_frame_count(0) == 8
            assert d.read_image(group_id=0, image_id=0).width == 205
    
    #read all images
    with lodfile.open("tests/files/HotA/Data/HotA.lod") as lod:
        with deffile.open(BytesIO(lod.get_file("COUATL.def"))) as d:
            for group in d.get_groups():
                for index in range(d.get_frame_count(group)):
                    d.read_image(group_id=group, image_id=index)

def test_save():
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        mf = BytesIO()
        d.save(mf)
        mf.seek(0)
        assert len(mf.read()) > len(open("tests/files/courtyard/CTrSalamand.def", "rb").read()) # saving is currently uncompressed
