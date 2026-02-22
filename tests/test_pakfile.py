from homm3data import pakfile
import os

def test_pak():
    if not os.path.exists("tests/files/courtyard/sprite_DXT_com_x3.pak"):
        return
    
    with pakfile.open("tests/files/courtyard/sprite_DXT_com_x3.pak") as pak:
        sheets = pak.get_sheetnames()
        filenames = pak.get_filenames_for_sheet(sheets[978])

        img = pak.get_image("AVWIMPX0", "AVWIMPX1")
        assert img[0].width > 0
