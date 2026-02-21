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


# ===== LOD Encoder tests =====

def test_lod_create_empty():
    """Test creating an empty LOD archive."""
    lod = lodfile.LodFile.create()
    assert lod.get_filelist() == []

def test_lod_add_file():
    """Test adding files to LOD archive."""
    lod = lodfile.LodFile.create()
    lod.add_file("test.txt", b"Hello, World!")
    lod.add_file("data.bin", b"\x00\x01\x02\x03")

    assert "test.txt" in lod.get_filelist()
    assert "data.bin" in lod.get_filelist()
    assert len(lod.get_filelist()) == 2

def test_lod_remove_file():
    """Test removing files from LOD archive."""
    lod = lodfile.LodFile.create()
    lod.add_file("test.txt", b"Hello")
    lod.add_file("other.txt", b"World")
    assert len(lod.get_filelist()) == 2

    lod.remove_file("test.txt")
    assert len(lod.get_filelist()) == 1
    assert "other.txt" in lod.get_filelist()

def test_lod_save_roundtrip():
    """Test saving and re-loading a LOD archive."""
    lod = lodfile.LodFile.create()
    test_data = {
        "file1.txt": b"Content of file 1",
        "file2.bin": bytes(range(256)),
        "file3.dat": b"A" * 10000,  # large enough to benefit from compression
    }

    for name, data in test_data.items():
        lod.add_file(name, data)

    # Save with compression
    mf = BytesIO()
    lod.save(mf, compress=True)
    mf.seek(0)

    # Re-load
    with lodfile.open(mf) as lod2:
        assert set(lod2.get_filelist()) == set(k.lower() for k in test_data.keys())
        for name, original_data in test_data.items():
            loaded = lod2.get_file(name.lower())
            assert loaded == original_data, f"Data mismatch for {name}"

def test_lod_save_no_compression():
    """Test saving without compression."""
    lod = lodfile.LodFile.create()
    lod.add_file("test.txt", b"Hello, World!")

    mf = BytesIO()
    lod.save(mf, compress=False)
    mf.seek(0)

    with lodfile.open(mf) as lod2:
        assert lod2.get_file("test.txt") == b"Hello, World!"

def test_lod_replace_file():
    """Test replacing an existing file."""
    lod = lodfile.LodFile.create()
    lod.add_file("test.txt", b"Original")
    lod.add_file("test.txt", b"Replaced")

    assert len(lod.get_filelist()) == 1

    mf = BytesIO()
    lod.save(mf, compress=False)
    mf.seek(0)

    with lodfile.open(mf) as lod2:
        assert lod2.get_file("test.txt") == b"Replaced"

def test_lod_roundtrip_from_existing():
    """Test reading an existing LOD and saving it back."""
    with lodfile.open("tests/files/h3sprite.lod") as lod:
        filelist = lod.get_filelist()
        assert len(filelist) > 0

        # Read a file
        first_file = filelist[0]
        original_data = lod.get_file(first_file)
        assert original_data is not None

        # Create new LOD with that file
        new_lod = lodfile.LodFile.create()
        new_lod.add_file(first_file, original_data)

        mf = BytesIO()
        new_lod.save(mf, compress=True)
        mf.seek(0)

        with lodfile.open(mf) as lod2:
            loaded = lod2.get_file(first_file)
            assert loaded == original_data

def test_lod_save_filepath():
    """Test saving LOD to a file path."""
    import tempfile, os
    lod = lodfile.LodFile.create()
    lod.add_file("test.txt", b"file path test")

    with tempfile.NamedTemporaryFile(suffix=".lod", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        lod.save(tmp_path)
        assert os.path.getsize(tmp_path) > 0
        with lodfile.open(tmp_path) as lod2:
            assert lod2.get_file("test.txt") == b"file path test"
    finally:
        os.unlink(tmp_path)
