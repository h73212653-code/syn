"""Obtención de letras desde LRCLIB.

Se usa solo la biblioteca estándar para no añadir dependencias al entorno
virtual de SYN (el lanzador `syn` corre con `.venv`, que no incluye httpx).
Cualquier fallo (sin red, 404, timeout, JSON inválido…) devuelve ``None`` en
silencio.

LRCLIB devuelve dos formas de la misma letra:

* ``plainLyrics``: texto sin tiempos.
* ``syncedLyrics``: formato LRC, con ``[mm:ss.xx]`` al principio de cada línea.

Cuando hay tiempos, SYN los usa para resaltar la línea que suena. Si la
versión que está sonando no dura lo mismo que la de LRCLIB (slowed, sped up,
edición distinta), se descartan los tiempos: mejor letra sin resaltar que
letra desincronizada.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

API_URL = "https://lrclib.net/api/get"
SEARCH_URL = "https://lrclib.net/api/search"
TIMEOUT = 3.0
USER_AGENT = "syn-tui/1.4.1 (reproductor local)"

# Diferencia de duración tolerada antes de desconfiar de los tiempos.
MAX_DURATION_DRIFT = 0.06
# Similitud mínima del título para aceptar un resultado de búsqueda.
MIN_TITLE_RATIO = 0.75
# Cuando el artista solo se deduce del propio título, se exige más parecido.
MIN_INFERRED_RATIO = 0.90

# [mm:ss], [mm:ss.xx], [mm:ss.xxx] y también [mm:ss:xx].
_TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
# [offset:+500] (milisegundos; positivo adelanta la letra).
_OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\s*\]", re.IGNORECASE)
# LRC mejorado: <mm:ss.xx> dentro de la línea (karaoke por palabra).
_WORD_TIME = re.compile(r"<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>")

# Ruido habitual en títulos descargados de YouTube.
_NOISE = re.compile(
    r"[\(\[\{][^\)\]\}]*(slowed|reverb|sped up|speed up|nightcore|remix|"
    r"tiktok|version|edit|lyrics|audio|video|official|hd|4k|extended)[^\)\]\}]*"
    r"[\)\]\}]",
    re.IGNORECASE,
)
_YOUTUBE_ID = re.compile(r"\[[A-Za-z0-9_-]{11}\]")
_FEAT = re.compile(
    r"\s*[-–—]?\s*\b(feat\.?|ft\.?|featuring)\b.*$", re.IGNORECASE
)
_INSTRUMENTAL = re.compile(r"\b(instrumental|karaoke|sin voz)\b", re.IGNORECASE)
# «Artista A, Artista B & Artista C feat. D» → varios nombres.
_ARTIST_SPLIT = re.compile(
    r"\s*[,&]\s*|\s+/\s+|\bfeat\.?\b|\bft\.?\b|\s+x\s+", re.IGNORECASE
)
# «Tema - Artista» o «Artista - Tema» (con guion, en dash o em dash).
_DASHES = re.compile(r"\s*[-–—]\s*")
# Etiquetas tipo «[Slowed]», «(Official Video)», «{Remix}».
_BRACKETS = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")


@dataclass(frozen=True, slots=True)
class LyricLine:
    """Una línea de letra con el segundo en el que empieza."""

    time: float
    text: str


@dataclass(frozen=True, slots=True)
class Lyrics:
    """Letra de una canción, con o sin tiempos."""

    plain: str | None = None
    synced: tuple[LyricLine, ...] = ()
    instrumental: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.plain and not self.synced and not self.instrumental


def parse_lrc(raw: str) -> tuple[LyricLine, ...]:
    """Convierte texto LRC en líneas ordenadas por tiempo.

    Acepta varias marcas de tiempo en la misma línea
    (``[00:10.00][01:20.00]estribillo``), el ``[offset:...]`` global y el
    formato por palabra. Las etiquetas de metadatos (``[ar:...]``) se ignoran.
    """
    if not raw:
        return ()

    offset = 0.0
    match = _OFFSET.search(raw)
    if match:
        offset = int(match.group(1)) / 1000.0

    lines: list[LyricLine] = []
    for row in raw.splitlines():
        stamps = list(_TIMESTAMP.finditer(row))
        if not stamps:
            continue
        text = _WORD_TIME.sub("", row[stamps[-1].end():]).strip()
        for stamp in stamps:
            minutes = int(stamp.group(1))
            seconds = int(stamp.group(2))
            fraction = (stamp.group(3) or "0").ljust(3, "0")[:3]
            moment = minutes * 60 + seconds + int(fraction) / 1000.0
            lines.append(LyricLine(max(moment - offset, 0.0), text))

    lines.sort(key=lambda line: line.time)
    return tuple(lines)


def fetch_lyrics_data(
    artist: str, track: str, duration: float = 0.0
) -> Lyrics | None:
    """Devuelve la letra de una canción (con tiempos si son fiables)."""
    artist = (artist or "").strip()
    track = (track or "").strip()
    if not artist or not track:
        return None

    data = _lookup(artist, track, duration)
    if not isinstance(data, dict):
        return None
    return _build_lyrics(data, duration)


def fetch_lyrics(artist: str, track: str) -> str | None:
    """Compatibilidad: devuelve solo el texto plano de la letra."""
    lyrics = fetch_lyrics_data(artist, track)
    return lyrics.plain if lyrics else None


# --------------------------------------------------------------- búsqueda
def _lookup(artist: str, track: str, duration: float) -> Any | None:
    """Busca por título exacto y, si falla, con el título limpio."""
    data = _get(artist, track)
    if data is not None:
        return data

    # En una canción instrumental, buscar la versión con voz daría letras que
    # no suenan en el archivo.
    if _INSTRUMENTAL.search(track):
        return {"instrumental": True}

    cleaned = clean_title(track)
    if cleaned and cleaned.casefold() != track.casefold():
        data = _get(artist, cleaned)
        if data is not None:
            return data

    return _search_best(track, artist, duration)


def clean_title(title: str) -> str:
    """Quita identificadores de YouTube y etiquetas tipo ``[Slowed]``."""
    title = _YOUTUBE_ID.sub(" ", title)
    title = _NOISE.sub(" ", title)
    title = _FEAT.sub("", title)
    return re.sub(r"\s+", " ", title).strip(" -–—")


def _normalise(text: str) -> str:
    """Minúsculas, sin acentos y solo letras/números para comparar."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _artist_tokens(artist: str) -> set[str]:
    # Se separa antes de normalizar: si no, las comas desaparecen y
    # «Maroon 5, Wiz Khalifa» quedaría como un único nombre imposible de casar.
    tokens = {_normalise(part) for part in _ARTIST_SPLIT.split(artist)}
    return {token for token in tokens if len(token) > 2}


def _title_variants(title: str) -> list[str]:
    """Formas de buscar un título descargado de YouTube.

    «COQUETA - Fuerza Regida» se prueba entero y por partes, y las etiquetas
    entre corchetes se ignoran. Así se encuentra la canción aunque el nombre
    del canal esté mezclado con el del artista o con «[Slowed + Reverb]».
    """
    base = clean_title(title)
    candidates = [base, _BRACKETS.sub(" ", base)]
    for text in list(candidates):
        candidates.extend(_DASHES.split(text))

    variants: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip(" -–—")
        key = _normalise(candidate)
        if len(key) < 3 or key in seen:
            continue
        seen.add(key)
        variants.append(candidate)
    return variants[:6]


def _get(artist: str, track: str) -> Any | None:
    query = urllib.parse.urlencode(
        {"artist_name": artist, "track_name": track}
    )
    data = _request_json(f"{API_URL}?{query}")
    return data if isinstance(data, dict) else None


def _search(query: str) -> list[dict[str, Any]]:
    data = _request_json(f"{SEARCH_URL}?{urllib.parse.urlencode({'q': query})}")
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _search_best(title: str, artist: str, duration: float) -> dict[str, Any] | None:
    """Elige un resultado solo si título y artista se parecen de verdad.

    El título puede traer el artista mezclado (nombre del canal de YouTube,
    «Tema - Artista»), así que se compara contra el título completo y contra
    sus partes. Cuanta menos evidencia hay del artista, más alto se exige el
    parecido del título para no enseñar la letra de otra canción.
    """
    variants = _title_variants(title)
    if not variants:
        return None

    wanted = [_normalise(variant) for variant in variants]
    own = _artist_tokens(artist)
    inferred: set[str] = set()
    for variant in variants[1:]:
        if len(variant.split()) >= 2:
            inferred |= _artist_tokens(variant)

    queries: list[str] = []
    for query in [f"{variants[0]} {artist}", *variants]:
        if query and query not in queries:
            queries.append(query)

    results: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for query in queries:
        for item in _search(query):
            key = (
                item.get("id"),
                item.get("trackName"),
                item.get("artistName"),
                item.get("duration"),
            )
            if key in seen:
                continue
            seen.add(key)
            results.append(item)

    best: dict[str, Any] | None = None
    best_score = 0.0

    for item in results:
        their_title = _normalise(str(item.get("trackName") or ""))
        ratio = max(
            (
                SequenceMatcher(None, wanted_title, their_title).ratio()
                for wanted_title in wanted
            ),
            default=0.0,
        )
        theirs = _artist_tokens(str(item.get("artistName") or ""))

        if own & theirs:
            needed = MIN_TITLE_RATIO
        elif inferred & theirs:
            needed = MIN_INFERRED_RATIO
        else:
            # Sin ninguna pista del artista no se arriesga: mejor no enseñar
            # letra que enseñar la de otra canción con el mismo título.
            continue
        if ratio < needed:
            continue

        score = ratio
        their_duration = item.get("duration")
        if duration > 0 and isinstance(their_duration, (int, float)):
            drift = abs(their_duration - duration) / duration
            score += max(0.0, 0.3 - drift)
        if item.get("syncedLyrics"):
            score += 0.05
        if score > best_score:
            best, best_score = item, score

    return best


def _request_json(url: str) -> Any | None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                if response.status != 200:
                    return None
                payload = response.read().decode("utf-8", errors="replace")
            return json.loads(payload)
        except urllib.error.HTTPError as exc:
            # LRCLIB limita las peticiones seguidas: una espera corta y reintento.
            if exc.code == 429 and attempt == 0:
                time.sleep(0.8)
                continue
            return None
        except Exception:
            return None
    return None


def _build_lyrics(data: dict[str, Any], duration: float) -> Lyrics | None:
    plain = data.get("plainLyrics")
    plain = plain.strip() if isinstance(plain, str) else ""

    raw_synced = data.get("syncedLyrics")
    synced = parse_lrc(raw_synced) if isinstance(raw_synced, str) else ()

    # Si solo vienen tiempos, se reconstruye el texto plano a partir de ellos.
    if not plain and synced:
        plain = "\n".join(line.text for line in synced if line.text).strip()

    if synced and duration > 0:
        their_duration = data.get("duration")
        if isinstance(their_duration, (int, float)) and their_duration > 0:
            drift = abs(their_duration - duration) / max(duration, 1.0)
            if drift > MAX_DURATION_DRIFT:
                synced = ()  # otra versión: los tiempos no sirven

    lyrics = Lyrics(
        plain=plain or None,
        synced=synced,
        instrumental=bool(data.get("instrumental")),
    )
    return None if lyrics.is_empty else lyrics
