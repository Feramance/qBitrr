import os
import pathlib
import sys


def get_git_hash() -> str:
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path is not None:
        return pathlib.Path(os.path.join(base_path, "git_hash.txt")).read_text().strip()  # FIXME
    return "Non-Binary"


version = "2.1.14"
git_hash = get_git_hash()

license_text = (
    "Licence can be found on:\n\nhttps://github.com/Drapersniper/Qbitrr/blob/master/LICENSE"
)
patched_version = f"{version}-{git_hash}"
