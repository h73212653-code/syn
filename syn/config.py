"""Configuración de SYN."""

from __future__ import annotations

import argparse
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

APP_VERSION = "1.4.1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_CONFIG = PROJECT_ROOT / "config.toml"


def _user_config_path() -> Path:
    """Ruta del archivo de configuración del usuario."""
    override = os.environ.get("SYN_CONFIG")
    if override:
        return Path(override).expanduser()

    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", "~/.config")
    ).expanduser()
    return config_home / "syn" / "config.toml"


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _default_music_dir() -> Path:
    """Devuelve ~/Música, con un fallback amable a ~/Musica.

    En muchos sistemas en español la carpeta se llama ``Música``, pero en
    otros se crea sin tilde. Se prefiere la primera si contiene audio.
    """
    candidates = [Path.home() / "Música", Path.home() / "Musica"]
    extensions = {".mp3", ".flac", ".wav", ".ogg"}
    first_existing: Path | None = None

    for candidate in candidates:
        if not candidate.is_dir():
            continue
        if first_existing is None:
            first_existing = candidate
        try:
            if any(
                item.is_file() and item.suffix.lower() in extensions
                for item in candidate.rglob("*")
            ):
                return candidate
        except OSError:
            continue

    return first_existing or candidates[0]


@dataclass(frozen=True, slots=True)
class Config:
    """Configuración efectiva del reproductor."""

    music_dir: Path
    recursive: bool = True
    theme_index: int = 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="syn",
        description="SYN · reproductor de música local para terminal (Kitty).",
    )
    parser.add_argument(
        "--music-dir",
        metavar="RUTA",
        type=Path,
        help="Carpeta de música (por defecto: ~/Música).",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="No buscar dentro de las subcarpetas.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"SYN {APP_VERSION}",
    )
    return parser


def load_config(argv: Sequence[str] | None = None) -> Config:
    """Carga y combina configuración, entorno y argumentos CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Primero los valores del proyecto y después los del usuario: el usuario
    # siempre puede sobrescribir los valores incluidos con el proyecto.
    values: dict[str, Any] = {}
    values.update(_read_toml(PROJECT_CONFIG))
    values.update(_read_toml(_user_config_path()))

    raw_dir: Any = os.environ.get("SYN_MUSIC_DIR") or values.get("music_dir")
    if args.music_dir is not None:
        music_dir = args.music_dir
    elif raw_dir:
        music_dir = Path(str(raw_dir)).expanduser()
    else:
        music_dir = _default_music_dir()

    recursive = bool(values.get("recursive", True))
    theme_index = int(values.get("theme_index", 0))
    if args.no_recursive:
        recursive = False

    return Config(music_dir=music_dir, recursive=recursive, theme_index=theme_index)
