"""Подготовка изображений под требования BotFather."""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

DESCRIPTION_PICTURE_WIDTH = 640
DESCRIPTION_PICTURE_HEIGHT = 360
DESCRIPTION_PICTURE_SIZE = (DESCRIPTION_PICTURE_WIDTH, DESCRIPTION_PICTURE_HEIGHT)
DESCRIPTION_PICTURE_ASPECT = DESCRIPTION_PICTURE_WIDTH / DESCRIPTION_PICTURE_HEIGHT


def _cover_crop_to_aspect(img: Image.Image, target_aspect: float) -> Image.Image:
    w, h = img.size
    if w <= 0 or h <= 0:
        raise ValueError("Некорректный размер изображения")
    current = w / h
    if abs(current - target_aspect) < 0.001:
        return img
    if current > target_aspect:
        new_w = int(h * target_aspect)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    new_h = int(w / target_aspect)
    top = (h - new_h) // 2
    return img.crop((0, top, w, top + new_h))


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        return background
    if img.mode == "P":
        return _to_rgb(img.convert("RGBA"))
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def normalize_description_picture(data: bytes) -> bytes:
    """
    Приводит картинку плаката к 640×360 (cover crop 16:9, JPEG).
    BotFather отклоняет произвольные размеры.
    """
    if not data:
        raise ValueError("Пустой файл изображения")

    with Image.open(BytesIO(data)) as src:
        img = ImageOps.exif_transpose(src)
        if getattr(img, "is_animated", False):
            img.seek(0)
        img = _to_rgb(img)
        img = _cover_crop_to_aspect(img, DESCRIPTION_PICTURE_ASPECT)
        img = img.resize(DESCRIPTION_PICTURE_SIZE, Image.Resampling.LANCZOS)

        out = BytesIO()
        img.save(out, format="JPEG", quality=88, optimize=True)
        return out.getvalue()


def normalize_description_picture_file(path: Path) -> None:
    """Перезаписывает файл нормализованным JPEG 640×360."""
    raw = path.read_bytes()
    path.write_bytes(normalize_description_picture(raw))
