from homm3data import deffile, lodfile
from io import BytesIO

def test_read_def_hota18():
    #read hota18 lod
    with lodfile.open("tests/files/HotA18/Data/HotA.lod") as lod:
        files = lod.get_filelist()
        with deffile.open(BytesIO(lod.get_file(files[0]))) as d:
            for group in d.get_groups():
                for index in range(d.get_frame_count(group)):
                    d.read_image(group_id=group, image_id=index)
