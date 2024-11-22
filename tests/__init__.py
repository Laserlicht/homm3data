import os
import urllib.request
import tarfile
from io import BytesIO

if not os.path.isfile(os.path.join(os.path.dirname(__file__), "files/h3bitmap.lod")):
    url = "https://web.archive.org/web/20150506062114if_/http://updates.lokigames.com/loki_demos/heroes3-demo.run"
    contents = urllib.request.urlopen(url).read()
    data = contents.split(b"END_OF_STUB\n", 1)[1]
    with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as f:
        open(os.path.join(os.path.dirname(__file__), "files/h3bitmap.lod"), "wb").write(f.extractfile("data/demos/heroes3_demo/data/h3bitmap.lod").read())
        open(os.path.join(os.path.dirname(__file__), "files/h3sprite.lod"), "wb").write(f.extractfile("data/demos/heroes3_demo/data/h3sprite.lod").read())
        open(os.path.join(os.path.dirname(__file__), "files/heroes3.snd"), "wb").write(f.extractfile("data/demos/heroes3_demo/data/heroes3.snd").read())
        