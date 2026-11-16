"""Obtención de letras desde LRCLIB.

Se usa solo la biblioteca estándar para no añadir dependencias al entorno
virtual de SYN (el lanzador `syn` corre con `.venv`, que no incluye httpx).
Cualquier fallo (sin red, 404, timeout, JSON inválido…) devuelve ``None`` en
silencio.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

API_URL = "https://lrclib.net/api/get"
TIMEOUT = 3.0
USER_AGENT = "syn-tui/1.2.0 (reproductor local)"


def fetch_lyrics(artist: str, track: str) -> str | None:
    """Devuelve la letra en texto plano de una canción, o ``None``."""
    artist = (artist or "").strip()
    track = (track or "").strip()
    if not artist or not track:
        return None

    query = urllib.parse.urlencode(
        {"artist_name": artist, "track_name": track}
    )
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                return None
            payload = response.read().decode("utf-8", errors="replace")
        data = json.loads(payload)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    lyrics = data.get("plainLyrics")
    if not isinstance(lyrics, str):
        return None

    lyrics = lyrics.strip()
    return lyrics or None
