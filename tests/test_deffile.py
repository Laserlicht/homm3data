from homm3data import deffile

def test_file_handling():
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        img = d.read(0, 0)
    assert img.width > 0

    with open("tests/files/courtyard/CTrSalamand.def", "rb") as f:
        with deffile.open(f) as d:
            img = d.read(0, 0)
    assert img.width > 0

def test_type():
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        assert d.get_type() == deffile.DefFile.FileType.CREATURE
