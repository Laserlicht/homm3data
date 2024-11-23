# homm3data
Decoding of Heroes Might of Magic III files

## Installation

Library can be installed with PIP:
`pip install homm3data`

## Examples

Saving all frames from def file as png files:
```
from homm3data import deffile

with deffile.open('path/to/deffile.def') as d:
    for group in d.get_groups():
        for frame in range(d.get_frame_count(group)):
            img = d.read_image('combined', group, frame)
            img.save('path/to/image_group%d_frame%d.png' % (group, frame))
```

Extracting image from pcx inside lod file:
```
from homm3data import pcxfile, lodfile

with lodfile.open('path/to/h3bitmap.lod') as lod:
    data = lod.get_file("aishield.pcx")
    if pcxfile.is_pcx(data):
        pcxfile.read_pcx(data).save('path/to/image.png')
```

Extracting image from pak file (Heroes III HD):
```
from homm3data import pakfile

with pakfile.open("path/to/sprite_DXT_com_x3.pak") as pak:
    img = pak.get_image("AVWIMPX0", "AVWIMPX1")
    img.save('path/to/image.png')
```

## API
The API for the library is described [here](https://laserlicht.github.io/homm3data).

## License
Library is released under MIT license.

Some parts of code are based on [lodextract](https://gitlab.mister-muffin.de/josch/lodextract) from josch. Originally published under GPL. Josch kindly gave me permission (via e-mail) to use the code under MIT as well. Thanks a lot!