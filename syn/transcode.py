"""Decodificación de formatos que pygame/SDL_mixer no reproduce directamente.

Opus se reproduce de forma nativa en las builds actuales de pygame-ce, pero
M4A/AAC (MP4, Apple Music, iTunes…) no está soportado por SDL_mixer. Para esos
archivos se decodifica una vez a FLAC con ``ffmpeg`` y se guarda en caché; así
la primera reproducción tarda un poco y las siguientes son instantáneas.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

# Contenedores/códecs que SDL_mixer no sabe abrir y hay que convertir.
TRANSCODE_EXTENSIONS = frozenset({".m4a", ".m4b", ".mp4", ".aac"})

# Opus debería sonar directamente, pero algunas builds de SDL_mixer antiguas
# no lo incluyen: si falla la carga, se intenta convertir como último recurso.
FALLBACK_EXTENSIONS = frozenset({".opus"})

_FFMPEG_TIMEOUT = 300  # segundos; una pista larga en un equipo lento
_MAX_CACHE_FILES = 32
_MAX_CACHE_BYTES = 1 << 30  # 1 GiB


class TranscodeError(RuntimeError):
    """No se pudo convertir el archivo a un formato reproducible."""


def needs_transcode(path: Path) -> bool:
    return path.suffix.lower() in TRANSCODE_EXTENSIONS


def ffmpeg_binary() -> str | None:
    """Ruta de ffmpeg, permitiendo forzarla con ``SYN_FFMPEG``."""
    override = os.environ.get("SYN_FFMPEG")
    if override:
        return override
    return shutil.which("ffmpeg")


def cache_directory() -> Path:
    """Carpeta de caché de las conversiones (respeta ``XDG_CACHE_HOME``)."""
    override = os.environ.get("SYN_TRANSCODE_DIR")
    if override:
        return Path(override).expanduser()
    base = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser()
    return base / "syn" / "transcode"


def _cache_key(path: Path) -> str:
    """Identifica el archivo por ruta, tamaño y fecha de modificación."""
    try:
        stat = path.stat()
        fingerprint = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        fingerprint = str(path)
    digest = hashlib.sha1(fingerprint.encode("utf-8", "surrogatepass"))
    return digest.hexdigest()


def _prune_cache(directory: Path) -> None:
    """Elimina las conversiones más antiguas si la caché crece demasiado."""
    try:
        entries = [
            item for item in directory.glob("*.flac") if item.is_file()
        ]
        entries.sort(key=lambda item: item.stat().st_mtime)
    except OSError:
        return

    total = 0
    sizes: dict[Path, int] = {}
    for item in entries:
        try:
            size = item.stat().st_size
        except OSError:
            size = 0
        sizes[item] = size
        total += size

    while entries and (
        len(entries) > _MAX_CACHE_FILES or total > _MAX_CACHE_BYTES
    ):
        oldest = entries.pop(0)
        total -= sizes.get(oldest, 0)
        try:
            oldest.unlink()
        except OSError:
            pass


def transcode_to_flac(path: Path) -> Path:
    """Devuelve una versión FLAC reproducible de ``path``, usando caché.

    Lanza :class:`TranscodeError` con un mensaje apto para el usuario si falta
    ffmpeg o la conversión falla.
    """
    binary = ffmpeg_binary()
    directory = cache_directory()
    destination = directory / f"{_cache_key(path)}.flac"
    try:
        if destination.is_file() and destination.stat().st_size > 0:
            return destination
    except OSError:
        pass

    if binary is None:
        raise TranscodeError(
            f"«{path.name}» está en un formato que necesita ffmpeg. "
            "Instálalo (pacman -S ffmpeg / apt install ffmpeg / "
            "dnf install ffmpeg) y vuelve a intentarlo."
        )

    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TranscodeError(
            f"No se pudo crear la caché de conversión en {directory}: {exc}"
        ) from exc

    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.part"
    )
    command = [
        binary,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
        "-dn",
        "-c:a",
        "flac",
        "-f",
        "flac",
        "-y",
        str(temporary),
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=_FFMPEG_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        temporary.unlink(missing_ok=True)
        raise TranscodeError(
            f"La conversión de «{path.name}» tardó demasiado."
        ) from exc
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise TranscodeError(
            f"No se pudo ejecutar ffmpeg para «{path.name}»: {exc}"
        ) from exc

    if result.returncode != 0 or not temporary.is_file():
        temporary.unlink(missing_ok=True)
        detail = result.stderr.decode("utf-8", "replace").strip()
        if detail:
            detail = detail.splitlines()[-1]
            message = f"No se pudo convertir «{path.name}»: {detail}"
        else:
            message = f"No se pudo convertir «{path.name}» a FLAC."
        raise TranscodeError(message)

    try:
        os.replace(temporary, destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise TranscodeError(
            f"No se pudo guardar la conversión de «{path.name}»: {exc}"
        ) from exc

    _prune_cache(directory)
    return destination
