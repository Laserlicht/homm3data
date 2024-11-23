# homm3data
Decoding and encoding of Heroes Might of Magic III files

## Installation

Library can be installed with PIP:
`pip install homm3data`

## Example
Saving all frames from def file as png files:
```
from homm3data import deffile

with deffile.open('path/to/deffile.def') as d:
    for group in range(d.get_block_count()):
        for frame in range(d.get_frame_count(group)):
            img = d.read_image('combined', group, frame)
            img.save('path/to/image_group%d_frame%d.png' % (group, frame))
```

## API
The API for the library is described [here](https://laserlicht.github.io/homm3data).

## License
Library is released under MIT license.

Some parts of code are based on [lodextract](https://github.com/josch/lodextract) from josch. Originally published under GPL. Josch kindly gave me permission (via mail) to use the code under MIT as well. Thanks a lot!