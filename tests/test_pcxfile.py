from homm3data import pcxfile, lodfile
from io import BytesIO
from PIL import Image
import numpy as np

def test_pcx():
    with lodfile.open("tests/files/h3bitmap.lod") as lod:
        data = lod.get_file("aishield.pcx")
        
        assert pcxfile.is_pcx(data)
        assert pcxfile.is_pcx(BytesIO(data))

        assert pcxfile.read_pcx(data).width == 144
        assert pcxfile.read_pcx(BytesIO(data)).width == 144

def test_p32():
    with open("tests/files/HotA/Data/hd_wrench.p32", "rb") as p32:
        assert pcxfile.read_pcx(p32.read()).width == 16


# ===== PCX Encoder tests =====

def test_write_pcx_rgb():
    """Test encoding an RGB image to PCX format."""
    img = Image.new("RGB", (64, 32), (255, 128, 0))
    data = pcxfile.write_pcx(img, mode="rgb")

    # Verify it can be read back
    assert pcxfile.is_pcx(data)
    img2 = pcxfile.read_pcx(data)
    assert img2 is not None
    assert img2.size == (64, 32)
    assert img2.mode == "RGB"

    # Check pixel values match
    px = img2.getpixel((0, 0))
    assert px == (255, 128, 0)

def test_write_pcx_palette():
    """Test encoding a palettized image to PCX format."""
    img = Image.new("RGB", (32, 32), (200, 100, 50))
    data = pcxfile.write_pcx(img, mode="palette")

    assert pcxfile.is_pcx(data)
    img2 = pcxfile.read_pcx(data)
    assert img2 is not None
    assert img2.size == (32, 32)
    assert img2.mode == "P"

def test_write_pcx_rgb_roundtrip():
    """Test RGB PCX encode/decode roundtrip preserves pixels."""
    # Create a gradient image
    arr = np.zeros((16, 16, 3), dtype=np.uint8)
    for y in range(16):
        for x in range(16):
            arr[y, x] = [x * 16, y * 16, 128]
    img = Image.fromarray(arr, 'RGB')

    data = pcxfile.write_pcx(img, mode="rgb")
    img2 = pcxfile.read_pcx(data)

    # Pixels should be identical
    arr2 = np.array(img2)
    assert np.array_equal(arr, arr2)

def test_write_pcx_rgba_input():
    """Test that RGBA images are handled properly."""
    img = Image.new("RGBA", (16, 16), (255, 0, 128, 255))
    data = pcxfile.write_pcx(img, mode="rgb")
    assert pcxfile.is_pcx(data)
    img2 = pcxfile.read_pcx(data)
    assert img2 is not None
    px = img2.getpixel((0, 0))
    assert px == (255, 0, 128)

def test_write_p32():
    """Test encoding a P32 format image."""
    img = Image.new("RGBA", (16, 16), (255, 128, 64, 200))
    data = pcxfile.write_p32(img)

    assert pcxfile.is_pcx(data)
    img2 = pcxfile.read_pcx(data)
    assert img2 is not None
    assert img2.size == (16, 16)
    assert img2.mode == "RGBA"
    px = img2.getpixel((0, 0))
    assert px == (255, 128, 64, 200)

def test_write_p32_roundtrip():
    """Test P32 encode/decode roundtrip preserves RGBA."""
    arr = np.zeros((8, 8, 4), dtype=np.uint8)
    for y in range(8):
        for x in range(8):
            arr[y, x] = [x * 30, y * 30, 128, 200]
    img = Image.fromarray(arr, 'RGBA')

    data = pcxfile.write_p32(img)
    img2 = pcxfile.read_pcx(data)
    arr2 = np.array(img2)
    assert np.array_equal(arr, arr2)

def test_pcx_from_lod_roundtrip():
    """Test reading a PCX from LOD and re-encoding it."""
    with lodfile.open("tests/files/h3bitmap.lod") as lod:
        original_data = lod.get_file("aishield.pcx")
        img = pcxfile.read_pcx(original_data)
        assert img is not None

        # Re-encode as RGB PCX
        new_data = pcxfile.write_pcx(img, mode="rgb")
        img2 = pcxfile.read_pcx(new_data)
        assert img2 is not None
        assert img2.size == img.size

def test_write_pcx_large_image():
    """Test encoding a larger image."""
    img = Image.new("RGB", (800, 600), (100, 200, 50))
    data = pcxfile.write_pcx(img, mode="rgb")
    assert pcxfile.is_pcx(data)
    img2 = pcxfile.read_pcx(data)
    assert img2.size == (800, 600)

def test_write_pcx_invalid_mode():
    """Test that invalid mode raises an error."""
    img = Image.new("RGB", (16, 16))
    try:
        pcxfile.write_pcx(img, mode="invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
