import os

MODULE_PATHS = [
    os.path.join(dirpath, f).replace(os.sep, ".").strip(".")[:-3]
    for (dirpath, _, filenames) in os.walk(f".{os.sep}src{os.sep}ext")
    for f in filenames
    if f.endswith(".py") and not f.startswith("__")
]
