import os
import pathlib
import sys


def resource_path(relative_path: str) -> str:
    base_path = getattr(
        sys, "_MEIPASS", str(pathlib.Path(os.path.abspath(__file__)).parent.parent)
    )
    return os.path.join(base_path, relative_path)


version = "2.1.12"
git_hash = pathlib.Path(resource_path("git_hash.txt")).read_text().strip()
license_text = (
    f"{pathlib.Path(resource_path('LICENSE')).read_text().strip()}\n\n"
    "https://github.com/Drapersniper/Qbitrr/blob/master/LICENSE"
)
patched_version = f"{version}-{git_hash}"
