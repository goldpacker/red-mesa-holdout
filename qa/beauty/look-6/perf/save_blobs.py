"""Copies Studio capture blobs taken since an epoch into a folder under
free-form names (beauty_save.py only accepts <tod>_<n>-<shot> names).
    tools/qa/py qa/beauty/look-6/perf/save_blobs.py <dir> <since> name1 name2 ...
"""
import shutil
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "qa"))
import beauty_save  # noqa: E402

out = Path(sys.argv[1])
since = float(sys.argv[2])
names = sys.argv[3:]
blobs = [b for b in beauty_save.find_blobs() if b[0] > since * 1000]
if len(blobs) != len(names):
    sys.exit(f"{len(blobs)} captures since {since}, {len(names)} names")
out.mkdir(parents=True, exist_ok=True)
for (t, path), name in zip(blobs, names):
    size = Image.open(path).size
    shutil.copyfile(path, out / f"{name}.jpg")  # byte copy, no re-encode
    print(f"{name}.jpg  {size[0]}x{size[1]}  <- {path.name}")
