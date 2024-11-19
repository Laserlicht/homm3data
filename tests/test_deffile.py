from homm3data import deffile

def test_file_handling():
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        assert len(d.get_raw_data()) > 0

    with open("tests/files/courtyard/CTrSalamand.def", "rb") as f:
        with deffile.open(f) as d:
            assert len(d.get_raw_data()) > 0

def test_type():
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        assert d.get_type() == deffile.DefFile.FileType.CREATURE

def test_read():
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        assert d.read(group_id=1, image_id=1).width > 0
