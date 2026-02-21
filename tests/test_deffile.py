from homm3data import deffile, lodfile
from io import BytesIO
from PIL import Image
import struct

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


# ===== Encoder tests =====

def test_save_roundtrip():
    """Test that saving and re-loading a DEF produces equivalent data."""
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        original_groups = d.get_groups()
        original_type = d.get_type()
        original_palette = d.get_palette()
        original_size = d.get_size()
        original_frame_counts = {g: d.get_frame_count(g) for g in original_groups}

        # Save to memory
        mf = BytesIO()
        d.save(mf)
        mf.seek(0)

    # Re-load saved DEF
    with deffile.open(mf) as d2:
        assert d2.get_type() == original_type
        assert d2.get_palette() == original_palette
        assert d2.get_size() == original_size
        assert d2.get_groups() == original_groups
        for g in original_groups:
            assert d2.get_frame_count(g) == original_frame_counts[g]
        # All frames should be readable
        for g in d2.get_groups():
            for i in range(d2.get_frame_count(g)):
                img = d2.read_image(group_id=g, image_id=i)
                assert img is not None
                assert img.width > 0

def test_create_def_from_scratch():
    """Test creating a DEF file from scratch with images."""
    d = deffile.DefFile.create(
        file_type=deffile.DefFile.FileType.SPRITE,
        width=32, height=32
    )

    # Create a test image
    img = Image.new('RGBA', (32, 32), (255, 0, 0, 255))
    d.set_image(0, 0, img, name="test_frame")

    assert d.get_groups() == [0]
    assert d.get_frame_count(0) == 1
    assert d.get_type() == deffile.DefFile.FileType.SPRITE

    # Save and re-load
    mf = BytesIO()
    d.save(mf)
    mf.seek(0)

    with deffile.open(mf) as d2:
        assert d2.get_type() == deffile.DefFile.FileType.SPRITE
        assert d2.get_groups() == [0]
        assert d2.get_frame_count(0) == 1
        img2 = d2.read_image(group_id=0, image_id=0)
        assert img2 is not None
        assert img2.width == 32
        assert img2.height == 32

def test_create_def_multiple_groups():
    """Test DEF with multiple groups and frames."""
    d = deffile.DefFile.create(
        file_type=deffile.DefFile.FileType.CREATURE,
        width=64, height=64
    )

    # Group 0: 2 frames
    img1 = Image.new('RGBA', (64, 64), (255, 0, 0, 255))
    img2 = Image.new('RGBA', (64, 64), (0, 255, 0, 255))
    d.set_image(0, 0, img1, name="walk_0")
    d.set_image(0, 1, img2, name="walk_1")

    # Group 1: 1 frame
    img3 = Image.new('RGBA', (64, 64), (0, 0, 255, 255))
    d.set_image(1, 0, img3, name="attack_0")

    assert len(d.get_groups()) == 2
    assert d.get_frame_count(0) == 2
    assert d.get_frame_count(1) == 1

    # Save and reload
    mf = BytesIO()
    d.save(mf)
    mf.seek(0)

    with deffile.open(mf) as d2:
        assert d2.get_frame_count(0) == 2
        assert d2.get_frame_count(1) == 1
        assert d2.read_image(group_id=0, image_id=0).width == 64
        assert d2.read_image(group_id=1, image_id=0).width == 64

def test_set_image_replace():
    """Test replacing an existing frame."""
    d = deffile.DefFile.create(width=32, height=32)

    img1 = Image.new('RGBA', (32, 32), (255, 0, 0, 255))
    d.set_image(0, 0, img1, name="frame0")
    assert d.get_frame_count(0) == 1

    # Replace with different size
    img2 = Image.new('RGBA', (16, 16), (0, 255, 0, 255))
    d.set_image(0, 0, img2, name="frame0")
    assert d.get_frame_count(0) == 1  # Still 1 frame

    mf = BytesIO()
    d.save(mf)
    mf.seek(0)

    with deffile.open(mf) as d2:
        raw = d2.get_raw_data()
        assert raw[0]["image"]["width"] == 16
        assert raw[0]["image"]["height"] == 16

def test_remove_frame():
    """Test removing a frame."""
    d = deffile.DefFile.create(width=32, height=32)
    img = Image.new('RGBA', (32, 32), (255, 0, 0, 255))
    d.set_image(0, 0, img, name="frame0")
    d.set_image(0, 1, img, name="frame1")
    assert d.get_frame_count(0) == 2

    d.remove_frame(0, 0)
    assert d.get_frame_count(0) == 1

def test_set_palette():
    """Test setting a custom palette."""
    d = deffile.DefFile.create(width=32, height=32)
    custom_palette = [(i, i, i) for i in range(256)]
    d.set_palette(custom_palette)
    assert d.get_palette() == custom_palette

def test_special_colors_detection():
    """Test that special palette indices are detected correctly."""
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        palette = d.get_palette()
        # Standard H3 DEF files should have special colors at indices 0-7
        # Index 0 should be close to (0, 255, 255) - cyan
        assert abs(palette[0][0] - 0) < 8
        assert abs(palette[0][1] - 255) < 8
        assert abs(palette[0][2] - 255) < 8

def test_read_all_layers():
    """Test reading combined, normal, shadow, overlay layers."""
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        img_combined = d.read_image(how="combined", group_id=0, image_id=0)
        img_normal = d.read_image(how="normal", group_id=0, image_id=0)
        assert img_combined is not None
        assert img_normal is not None
        assert img_combined.mode == "RGBA"
        # Shadow may or may not exist depending on type
        img_shadow = d.read_image(how="shadow", group_id=0, image_id=0)
        # Overlay may or may not exist
        img_overlay = d.read_image(how="overlay", group_id=0, image_id=0)

def test_save_with_filepath():
    """Test saving to a file path string."""
    import tempfile, os
    with deffile.open("tests/files/courtyard/CTrSalamand.def") as d:
        with tempfile.NamedTemporaryFile(suffix=".def", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            d.save(tmp_path)
            assert os.path.getsize(tmp_path) > 0
            with deffile.open(tmp_path) as d2:
                assert len(d2.get_groups()) > 0
        finally:
            os.unlink(tmp_path)

def test_encode_from_lod_image():
    """Test encoding an image loaded from LOD back to DEF."""
    with lodfile.open("tests/files/h3sprite.lod") as lod:
        with deffile.open(BytesIO(lod.get_file("avwangl.def"))) as d:
            original_palette = d.get_palette()
            original_type = d.get_type()

            # Read an image
            img = d.read_image(group_id=0, image_id=0)
            assert img is not None

            # Create new DEF with same palette and type
            new_d = deffile.DefFile.create(
                file_type=original_type,
                width=img.width, height=img.height,
                palette=original_palette
            )
            new_d.set_image(0, 0, img, name="test")

            mf = BytesIO()
            new_d.save(mf)
            mf.seek(0)

            # Re-read
            with deffile.open(mf) as d2:
                img2 = d2.read_image(group_id=0, image_id=0)
                assert img2 is not None
                assert img2.size == img.size
