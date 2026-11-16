"""Extracción de carátulas y generación de portadas de reserva."""

from __future__ import annotations

import base64
import colorsys
import hashlib
from io import BytesIO
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import Picture
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .library import Track

_MAX_COVER_SIZE = 1400
_PLACEHOLDER_SIZE = 1000


def _extract_embedded_cover(path: Path) -> bytes | None:
    """Busca una carátula incrustada en MP3, FLAC, OGG/Opus o WAV."""
    try:
        audio = MutagenFile(path)
    except Exception:
        return None

    if audio is None:
        return None

    # FLAC: bloque PICTURE.
    pictures = getattr(audio, "pictures", None)
    if pictures:
        try:
            return bytes(pictures[0].data)
        except (AttributeError, IndexError, TypeError):
            pass

    tags = getattr(audio, "tags", None)
    if tags is None:
        return None

    # MP3 / WAV / AIFF: marcos ID3 APIC. Preferimos portada frontal.
    try:
        apic_frames = tags.getall("APIC")
    except (AttributeError, TypeError):
        apic_frames = []

    if apic_frames:
        def rank(frame: object) -> int:
            try:
                return 0 if int(getattr(frame, "type", 0)) == 3 else 1
            except (TypeError, ValueError):
                return 1

        try:
            frame = sorted(apic_frames, key=rank)[0]
            return bytes(frame.data)
        except (AttributeError, TypeError):
            pass

    # Ogg Vorbis / Opus: METADATA_BLOCK_PICTURE en base64.
    try:
        raw_picture = tags.get("metadata_block_picture")
    except (AttributeError, TypeError):
        raw_picture = None

    if raw_picture:
        if isinstance(raw_picture, (list, tuple)):
            raw_picture = raw_picture[0] if raw_picture else None
        try:
            if isinstance(raw_picture, str):
                raw_picture = base64.b64decode(raw_picture)
            if isinstance(raw_picture, bytes):
                return bytes(Picture(raw_picture).data)
        except Exception:
            pass

    # MP4/M4A, por si en el futuro se amplían las extensiones.
    try:
        covers = tags.get("covr")
    except (AttributeError, TypeError):
        covers = None
    if covers:
        try:
            return bytes(covers[0])
        except (AttributeError, IndexError, TypeError):
            pass

    return None


def _normalize_cover(image: Image.Image) -> Image.Image:
    """Orienta, aplana transparencia, recorta en cuadrado y limita el tamaño."""
    image = ImageOps.exif_transpose(image)

    if (
        image.mode in {"RGBA", "LA"}
        or "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (8, 10, 16, 255))
        background.alpha_composite(rgba)
        image = background.convert("RGB")
    else:
        image = image.convert("RGB")

    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side))

    if side > _MAX_COVER_SIZE:
        image = image.resize(
            (_MAX_COVER_SIZE, _MAX_COVER_SIZE),
            Image.Resampling.LANCZOS,
        )

    return image


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("/usr/share/fonts/google-noto/NotoSans-Bold.ttf"),
        Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    )
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _seed(track: Track | None) -> tuple[float, float]:
    raw = (
        f"{track.title}|{track.artist}|{track.album}"
        if track is not None
        else "SYN|LOCAL|MUSIC"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    offset = int.from_bytes(digest[4:8], "big") / 0xFFFFFFFF
    return hue, offset


def create_placeholder(track: Track | None = None) -> Image.Image:
    """Genera una portada abstracta cuando el archivo no trae carátula."""
    size = _PLACEHOLDER_SIZE
    hue, offset = _seed(track)

    top_rgb = colorsys.hls_to_rgb(hue, 0.30, 0.55)
    bottom_rgb = colorsys.hls_to_rgb((hue + 0.16 + offset * 0.15) % 1.0, 0.10, 0.55)
    accent_rgb = colorsys.hls_to_rgb((hue + 0.45) % 1.0, 0.68, 0.68)

    gradient = Image.new("RGB", (1, 2))
    gradient.putpixel((0, 0), tuple(int(c * 255) for c in top_rgb))
    gradient.putpixel((0, 1), tuple(int(c * 255) for c in bottom_rgb))
    image = gradient.resize((size, size), Image.Resampling.BICUBIC)

    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Halo de color y disco de vinilo abstracto.
    accent = tuple(int(c * 255) for c in accent_rgb)
    draw.ellipse(
        (410, 120, 1180, 890),
        fill=(*accent, 52),
    )
    draw.ellipse(
        (485, 195, 1105, 815),
        fill=(8, 10, 16, 214),
        outline=(255, 255, 255, 26),
        width=3,
    )
    for radius in range(225, 90, -22):
        box = (
            795 - radius,
            505 - radius,
            795 + radius,
            505 + radius,
        )
        draw.ellipse(box, outline=(255, 255, 255, 18), width=1)

    label_rgb = colorsys.hls_to_rgb((hue + 0.06) % 1.0, 0.55, 0.65)
    label = tuple(int(c * 255) for c in label_rgb)
    draw.ellipse((745, 455, 845, 555), fill=(*label, 240))
    draw.ellipse((788, 498, 802, 512), fill=(8, 10, 16, 255))

    # Líneas diagonales sutiles, tipo artwork editorial.
    for index in range(6):
        x = 60 + index * 150
        draw.line((x, 0, x + 310, size), fill=(255, 255, 255, 10), width=1)

    # Título de la portada.
    title_font = _font(188)
    small_font = _font(30)
    micro_font = _font(23)
    draw.text((58, 745), "SYN", font=title_font, fill=(255, 255, 255, 242))
    draw.text(
        (66, 942),
        "SIN PORTADA",
        font=small_font,
        fill=(255, 255, 255, 178),
    )
    artist = (track.artist if track is not None else "REPRODUCTOR LOCAL").upper()
    if len(artist) > 34:
        artist = artist[:31].rstrip() + "..."
    draw.text(
        (size - 62, 56),
        artist,
        font=micro_font,
        fill=(255, 255, 255, 150),
        anchor="ra",
    )

    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    return image


def load_cover(track: Track) -> Image.Image:
    """Carga la carátula incrustada o devuelve una portada generada."""
    data = _extract_embedded_cover(track.path)
    if data:
        try:
            with Image.open(BytesIO(data)) as image:
                image.load()
                return _normalize_cover(image.copy())
        except (OSError, ValueError, Image.DecompressionBombError):
            pass
    return create_placeholder(track)


def extract_cover_bytes(track: Track) -> bytes | None:
    """Bytes de la carátula incrustada, sin decodificar la imagen."""
    return _extract_embedded_cover(track.path)
