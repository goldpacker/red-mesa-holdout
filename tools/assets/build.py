"""Blender entrypoint: build, bake, preview and export one asset.

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        -P tools/assets/build.py -- SupplyCrate [--no-preview] [--samples N]

Or use tools/assets/build.sh <Name>.
"""
import importlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        raise SystemExit("usage: build.py -- <AssetName> [--no-preview] [--samples N]")
    name = argv[0]
    kw = {}
    if "--no-preview" in argv:
        kw["preview"] = False
    if "--only" in argv:
        kw["only"] = argv[argv.index("--only") + 1].split(",")
    if "--samples" in argv:
        kw["samples"] = int(argv[argv.index("--samples") + 1])
    module = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    mod = importlib.import_module(f"models.{module}")
    mod.build(**kw)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
