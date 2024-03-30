import os

from src.logging import book

MODULE_PATHS = [
    os.path.join(dirpath, f).replace(os.sep, ".").strip(".")[:-3]  # noqa: PTH118
    for (dirpath, _, filenames) in os.walk(
        f".{os.sep}src{os.sep}types",
        onerror=lambda oserror: book.critical(oserror),
    )
    for f in filenames
    if f.endswith(".py") and not f.startswith("_")
]
