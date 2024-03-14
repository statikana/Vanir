import os

MODULE_PATHS = [
    os.path.join(dirpath, f).replace("\\", ".").strip(".")[:-3]
    for (dirpath, _, filenames) in os.walk(".\\src\\ext")
    for f in filenames
    if f.endswith(".py") and not f.startswith("__")
]
