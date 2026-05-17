import shutil
from pathlib import Path


def copy_tdata_tree(src: Path, dest: Path) -> None:
    """Копирует распакованный каталог tdata (корень с папкой tdata внутри)."""
    src = Path(src)
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
