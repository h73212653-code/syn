"""Escaneo de la biblioteca local y lectura de metadatos."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mutagen import File as MutagenFile

AUDIO_EXTENSIONS = frozenset({".mp3", ".flac", ".wav", ".ogg"})
UNKNOWN_ARTIST = "Artista desconocido"
UNKNOWN_ALBUM = "Álbum desconocido"


@dataclass(frozen=True, slots=True)
class Track:
    """Una pista de audio con los datos que necesita la interfaz."""

    path: Path
    title: str
    artist: str
    album: str
    duration: float
    format: str

    @property
    def sort_key(self) -> tuple[str, str, str, str]:
        return (
            self.artist.casefold(),
            self.album.casefold(),
            self.title.casefold(),
            self.path.name.casefold(),
        )


@dataclass(frozen=True, slots=True)
class Section:
    """Grupo de pistas: normalmente una subcarpeta de la carpeta de música."""

    name: str
    tracks: list[Track]


def _first_tag(value: object) -> str:
    """Normaliza los valores que mutagen devuelve como listas o strings."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        for item in value:
            text = str(item).strip()
            if text:
                return text
        return ""
    return str(value).strip()


def _read_track(path: Path) -> Track:
    title = path.stem
    artist = UNKNOWN_ARTIST
    album = UNKNOWN_ALBUM
    duration = 0.0

    try:
        audio = MutagenFile(path, easy=True)
    except Exception:
        audio = None

    if audio is not None:
        tags = audio.tags or {}
        try:
            title = _first_tag(tags.get("title")) or title
            artist = _first_tag(
                tags.get("artist")
                or tags.get("albumartist")
                or tags.get("performer")
            ) or artist
            album = _first_tag(tags.get("album")) or album
        except Exception:
            # Una etiqueta corrupta no debe impedir mostrar la pista.
            pass

        try:
            if audio.info is not None:
                duration = max(0.0, float(audio.info.length))
        except Exception:
            duration = 0.0

    return Track(
        path=path,
        title=title,
        artist=artist,
        album=album,
        duration=duration,
        format=path.suffix.lstrip(".").upper(),
    )


def _iter_audio_paths(root: Path, recursive: bool) -> Iterable[Path]:
    """Recorre la carpeta omitiendo archivos y directorios ocultos."""
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = sorted(
                name for name in dirnames if not name.startswith(".")
            )
            for filename in sorted(filenames):
                if filename.startswith("."):
                    continue
                path = Path(dirpath) / filename
                if path.suffix.lower() in AUDIO_EXTENSIONS:
                    yield path
    else:
        try:
            entries = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            return
        for path in entries:
            if (
                path.is_file()
                and not path.name.startswith(".")
                and path.suffix.lower() in AUDIO_EXTENSIONS
            ):
                yield path


def scan_library(root: Path, recursive: bool = True) -> list[Track]:
    """Devuelve las pistas encontradas, ordenadas por artista/álbum/título."""
    root = root.expanduser()
    if not root.is_dir():
        return []

    tracks: list[Track] = []
    seen: set[Path] = set()

    for path in _iter_audio_paths(root, recursive):
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            tracks.append(_read_track(path))
        except OSError:
            # Archivo desaparecido o sin permisos entre el escaneo y la lectura.
            continue

    tracks.sort(key=lambda track: track.sort_key)
    return tracks


def _collect_tracks(root: Path, recursive: bool) -> list[Track]:
    """Lee y ordena las pistas de una carpeta concreta."""
    tracks: list[Track] = []
    seen: set[Path] = set()

    for path in _iter_audio_paths(root, recursive):
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            tracks.append(_read_track(path))
        except OSError:
            continue

    tracks.sort(key=lambda track: track.sort_key)
    return tracks


def _direct_files(root: Path) -> list[Track]:
    """Pistas que están sueltas en ``root``, sin entrar en subcarpetas."""
    tracks: list[Track] = []
    try:
        entries = sorted(root.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return tracks

    for path in entries:
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower() in AUDIO_EXTENSIONS
        ):
            try:
                tracks.append(_read_track(path))
            except OSError:
                continue

    tracks.sort(key=lambda track: track.sort_key)
    return tracks


def scan_sections(root: Path, recursive: bool = True) -> list[Section]:
    """Agrupa la música por subcarpeta de primer nivel.

    Cada subcarpeta visible de ``root`` se convierte en una sección. Las
    pistas sueltas directamente en ``root`` van en una sección con el nombre
    de la propia carpeta. Las secciones vacías se omiten.
    """
    root = root.expanduser()
    if not root.is_dir():
        return []

    try:
        folders = sorted(
            (
                item
                for item in root.iterdir()
                if item.is_dir() and not item.name.startswith(".")
            ),
            key=lambda item: item.name.casefold(),
        )
    except OSError:
        folders = []

    sections: list[Section] = []
    for folder in folders:
        tracks = _collect_tracks(folder, recursive)
        if tracks:
            sections.append(Section(folder.name, tracks))

    root_tracks = _direct_files(root)
    if root_tracks:
        sections.insert(0, Section(root.name, root_tracks))

    return sections
