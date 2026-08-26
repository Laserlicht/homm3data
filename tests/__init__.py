import os
import shutil
import urllib.request
import tarfile
import subprocess
from io import BytesIO

if not os.path.isfile(os.path.join(os.path.dirname(__file__), "files/h3bitmap.lod")):
    url = "https://web.archive.org/web/20150506062114if_/http://updates.lokigames.com/loki_demos/heroes3-demo.run"
    contents = urllib.request.urlopen(url).read()
    data = contents.split(b"END_OF_STUB\n", 1)[1]
    with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as f:
        open(os.path.join(os.path.dirname(__file__), "files/h3bitmap.lod"), "wb").write(f.extractfile("data/demos/heroes3_demo/data/h3bitmap.lod").read())
        open(os.path.join(os.path.dirname(__file__), "files/h3sprite.lod"), "wb").write(f.extractfile("data/demos/heroes3_demo/data/h3sprite.lod").read())
        open(os.path.join(os.path.dirname(__file__), "files/heroes3.snd"), "wb").write(f.extractfile("data/demos/heroes3_demo/data/heroes3.snd").read())

if not os.path.isfile(os.path.join(os.path.dirname(__file__), "files/HotA/Data/HotA.lod")):
    url = "https://web.archive.org/web/20250609102045if_/https://www.vault.acidcave.net/download/HotA_1.7.3_setup.exe"
    os.makedirs(os.path.join(os.path.dirname(__file__), "files/HotA"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "files/HotA/tmp"), exist_ok=True)
    urllib.request.urlretrieve(url, os.path.join(os.path.dirname(__file__), "files/HotA/tmp/hota.exe"))
    subprocess.run(
        ['innoextract', '--extract', '--output-dir', os.path.join(os.path.dirname(__file__), "files/HotA/tmp"), os.path.join(os.path.dirname(__file__), "files/HotA/tmp/hota.exe")],
        check=True
    )
    shutil.move(os.path.join(os.path.dirname(__file__), "files/HotA/tmp/app/Data"), os.path.join(os.path.dirname(__file__), "files/HotA"))
    shutil.rmtree(os.path.join(os.path.dirname(__file__), "files/HotA/tmp"))

if not os.path.isfile(os.path.join(os.path.dirname(__file__), "files/HotA18/Data/HotA.lod")):
    url = "https://web.archive.org/web/20251231221901if_/https://www.vault.acidcave.net/download/HotA_1.8.0_setup.exe"
    os.makedirs(os.path.join(os.path.dirname(__file__), "files/HotA18"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "files/HotA18/tmp"), exist_ok=True)
    urllib.request.urlretrieve(url, os.path.join(os.path.dirname(__file__), "files/HotA18/tmp/hota.exe"))
    subprocess.run(
        ['innoextract', '--extract', '--output-dir', os.path.join(os.path.dirname(__file__), "files/HotA18/tmp"), os.path.join(os.path.dirname(__file__), "files/HotA18/tmp/hota.exe")],
        check=True
    )
    shutil.move(os.path.join(os.path.dirname(__file__), "files/HotA18/tmp/app/Data"), os.path.join(os.path.dirname(__file__), "files/HotA18"))
    shutil.rmtree(os.path.join(os.path.dirname(__file__), "files/HotA18/tmp"))

if not os.path.isfile(os.path.join(os.path.dirname(__file__), "files/HotA181/Data/HotA.lod")):
    url = "https://www.vault.acidcave.net/download/HotA_1.8.1_setup.exe"
    os.makedirs(os.path.join(os.path.dirname(__file__), "files/HotA181"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "files/HotA181/tmp"), exist_ok=True)
    urllib.request.urlretrieve(url, os.path.join(os.path.dirname(__file__), "files/HotA181/tmp/hota.exe"))
    subprocess.run(
        ['innoextract', '--extract', '--output-dir', os.path.join(os.path.dirname(__file__), "files/HotA181/tmp"), os.path.join(os.path.dirname(__file__), "files/HotA181/tmp/hota.exe")],
        check=True
    )
    shutil.move(os.path.join(os.path.dirname(__file__), "files/HotA181/tmp/app/Data"), os.path.join(os.path.dirname(__file__), "files/HotA181"))
    shutil.rmtree(os.path.join(os.path.dirname(__file__), "files/HotA181/tmp"))
