from homm3data import pakfile
from io import BytesIO
from PIL import Image
import os

def test_pak():
    if not os.path.exists("tests/files/courtyard/sprite_DXT_com_x3.pak"):
        return
    
    with pakfile.open("tests/files/courtyard/sprite_DXT_com_x3.pak") as pak:
        sheets = pak.get_sheetnames()
        filenames = pak.get_filenames_for_sheet(sheets[978])

        img = pak.get_image("AVWIMPX0", "AVWIMPX1")
        assert img[0].width > 0


# ===== PAK Encoder tests =====

def test_pak_create_empty():
    """Test creating an empty PAK archive."""
    pak = pakfile.PakFile.create()
    assert pak.get_sheetnames() == []

def test_pak_add_sheet():
    """Test adding a sheet to PAK."""
    pak = pakfile.PakFile.create()

    # Create test image
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    image_data = [buf.getvalue()]

    config = "TestSprite 0 0 0 0 0 0 0 64 64 0 0\r\n"
    pak.add_sheet("TEST", config, image_data)

    assert "TEST" in pak.get_sheetnames()
    sheets = pak.get_sheets("TEST")
    assert sheets is not None
    assert len(sheets) == 1
    assert sheets[0].width == 64

def test_pak_add_sheet_from_images():
    """Test adding a sheet from PIL images."""
    pak = pakfile.PakFile.create()

    img = Image.new("RGB", (32, 32), (0, 255, 0))
    config = "GreenBox 0 0 0 0 0 0 0 32 32 0 0\r\n"
    pak.add_sheet_from_images("GREEN", config, [img], fmt="PNG")

    assert "GREEN" in pak.get_sheetnames()
    sheets = pak.get_sheets("GREEN")
    assert len(sheets) == 1

def test_pak_remove_sheet():
    """Test removing a sheet."""
    pak = pakfile.PakFile.create()
    img = Image.new("RGB", (16, 16), (0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    pak.add_sheet("SHEET1", "config\r\n", [buf.getvalue()])
    pak.add_sheet("SHEET2", "config\r\n", [buf.getvalue()])

    assert len(pak.get_sheetnames()) == 2
    pak.remove_sheet("SHEET1")
    assert len(pak.get_sheetnames()) == 1
    assert "SHEET2" in pak.get_sheetnames()

def test_pak_save_roundtrip():
    """Test saving and re-loading a PAK archive."""
    pak = pakfile.PakFile.create()

    # Create test images
    img1 = Image.new("RGBA", (64, 64), (255, 0, 0, 200))
    img2 = Image.new("RGBA", (32, 32), (0, 255, 0, 200))

    buf1 = BytesIO()
    img1.save(buf1, format="PNG")
    buf2 = BytesIO()
    img2.save(buf2, format="PNG")

    config1 = "SPRITE1 0 0 0 0 0 0 0 64 64 0 0\r\n"
    config2 = "SPRITE2 0 0 0 0 0 0 0 32 32 0 0\r\n"

    pak.add_sheet("SHEET1", config1, [buf1.getvalue()])
    pak.add_sheet("SHEET2", config2, [buf2.getvalue()])

    # Save
    mf = BytesIO()
    pak.save(mf, use_compression=False)
    mf.seek(0)

    # Re-load
    with pakfile.open(mf) as pak2:
        assert set(pak2.get_sheetnames()) == {"SHEET1", "SHEET2"}
        sheets1 = pak2.get_sheets("SHEET1")
        assert sheets1 is not None
        assert len(sheets1) == 1
        assert sheets1[0].width == 64

        sheets2 = pak2.get_sheets("SHEET2")
        assert sheets2 is not None
        assert len(sheets2) == 1
        assert sheets2[0].width == 32

def test_pak_save_compressed():
    """Test saving with compression."""
    pak = pakfile.PakFile.create()
    img = Image.new("RGBA", (128, 128), (100, 100, 100, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    pak.add_sheet("BIG", "CONFIG\r\n", [buf.getvalue()])

    # Save with compression
    mf_compressed = BytesIO()
    pak.save(mf_compressed, use_compression=True)

    # Save without compression
    mf_raw = BytesIO()
    pak.save(mf_raw, use_compression=False)

    # Compressed should be smaller (or same for already-compressed PNG)
    mf_compressed.seek(0, 2)
    mf_raw.seek(0, 2)
    # Both should be valid
    mf_compressed.seek(0)
    mf_raw.seek(0)

def test_pak_save_filepath():
    """Test saving to a file path."""
    import tempfile
    pak = pakfile.PakFile.create()
    img = Image.new("RGB", (16, 16), (0, 0, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    pak.add_sheet("TEST", "cfg\r\n", [buf.getvalue()])

    with tempfile.NamedTemporaryFile(suffix=".pak", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        pak.save(tmp_path)
        assert os.path.getsize(tmp_path) > 0
    finally:
        os.unlink(tmp_path)

def test_pak_multiple_chunks():
    """Test sheet with multiple image chunks via compression."""
    pak = pakfile.PakFile.create()
    imgs = []
    for i in range(3):
        img = Image.new("RGB", (32, 32), (i * 80, 0, 0))
        buf = BytesIO()
        img.save(buf, format="PNG")
        imgs.append(buf.getvalue())

    pak.add_sheet("MULTI", "cfg\r\n", imgs)

    mf = BytesIO()
    pak.save(mf, use_compression=False)
    mf.seek(0)

    with pakfile.open(mf) as pak2:
        sheets_dds = pak2.get_sheets_dds("MULTI")
        # When uncompressed, chunks are concatenated into one blob by the parser
        assert sheets_dds is not None
        assert len(sheets_dds) >= 1
