"""MPRIS2: publica lo que suena para que la isla y el escritorio lo detecten.

SYN expone el servicio D-Bus estándar ``org.mpris.MediaPlayer2.syn``. Cualquier
cliente MPRIS (la Dynamic Island de KDE, el applet de medios de Plasma, teclas
multimedia, etc.) puede leer el título, el artista, la carátula y el progreso,
además de enviar play/pausa/siguiente/anterior o cambiar el volumen.

Si no hay sesión D-Bus o falta ``jeepney``, el módulo se desactiva en silencio:
la reproducción sigue funcionando igual.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

try:  # jeepney es puro Python; si falta, MPRIS simplemente no se publica.
    from jeepney import (
        DBusAddress,
        HeaderFields,
        MessageType,
        new_error,
        new_method_return,
        new_signal,
    )
    from jeepney.bus_messages import message_bus
    from jeepney.io.blocking import open_dbus_connection
except Exception:  # pragma: no cover - entorno sin jeepney
    DBUS_AVAILABLE = False
else:
    DBUS_AVAILABLE = True

BUS_NAME = "org.mpris.MediaPlayer2.syn"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
IFACE_ROOT = "org.mpris.MediaPlayer2"
IFACE_PLAYER = "org.mpris.MediaPlayer2.Player"
IFACE_PROPS = "org.freedesktop.DBus.Properties"
IFACE_INTROSPECT = "org.freedesktop.DBus.Introspectable"

NO_TRACK = "/org/mpris/MediaPlayer2/TrackList/NoTrack"

_INTROSPECTION = f"""<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node>
  <interface name="{IFACE_ROOT}">
    <method name="Raise"/>
    <method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/>
    <property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/>
    <property name="Identity" type="s" access="read"/>
    <property name="DesktopEntry" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="{IFACE_PLAYER}">
    <method name="Next"/>
    <method name="Previous"/>
    <method name="Pause"/>
    <method name="PlayPause"/>
    <method name="Stop"/>
    <method name="Play"/>
    <method name="Seek"><arg direction="in" name="Offset" type="x"/></method>
    <method name="SetPosition">
      <arg direction="in" name="TrackId" type="o"/>
      <arg direction="in" name="Position" type="x"/>
    </method>
    <method name="OpenUri"><arg direction="in" name="Uri" type="s"/></method>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="LoopStatus" type="s" access="readwrite"/>
    <property name="Rate" type="d" access="readwrite"/>
    <property name="Shuffle" type="b" access="readwrite"/>
    <property name="Metadata" type="a{{sv}}" access="read"/>
    <property name="Volume" type="d" access="readwrite"/>
    <property name="Position" type="x" access="read"/>
    <property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
    <signal name="Seeked"><arg name="Position" type="x"/></signal>
  </interface>
  <interface name="{IFACE_PROPS}">
    <method name="Get">
      <arg direction="in" type="s"/><arg direction="in" type="s"/>
      <arg direction="out" type="v"/>
    </method>
    <method name="GetAll">
      <arg direction="in" type="s"/><arg direction="out" type="a{{sv}}"/>
    </method>
    <method name="Set">
      <arg direction="in" type="s"/><arg direction="in" type="s"/>
      <arg direction="in" type="v"/>
    </method>
    <signal name="PropertiesChanged">
      <arg type="s"/><arg type="a{{sv}}"/><arg type="as"/>
    </signal>
  </interface>
  <interface name="{IFACE_INTROSPECT}">
    <method name="Introspect"><arg direction="out" type="s"/></method>
  </interface>
</node>"""


def _debug(message: str) -> None:
    """Registro opcional para depurar; nunca escribe en la interfaz."""
    if not os.environ.get("SYN_MPRIS_DEBUG"):
        return
    try:
        with open("/tmp/syn-mpris.log", "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except OSError:
        pass


def track_object_path(track: Any) -> str:
    """Ruta D-Bus estable y válida para una pista."""
    raw = f"{getattr(track, 'path', '')}|{getattr(track, 'title', '')}"
    digest = hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]
    return f"{OBJECT_PATH}/Track/{digest}"


def _cover_cache_dir() -> Path:
    cache = Path(
        os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    ) / "syn" / "covers"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _cover_digest(track: Any) -> str:
    """Clave de caché que cambia si el archivo cambia."""
    path = Path(str(getattr(track, "path", "")))
    try:
        stat = path.stat()
        stamp = f"{int(stat.st_mtime)}-{stat.st_size}"
    except OSError:
        stamp = "0-0"
    raw = f"{path}|{stamp}"
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:20]


def _sniff_extension(data: bytes) -> str:
    """Extensión según el contenido real de la imagen."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"GIF8"):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    return "img"


def cached_art_url(track: Any) -> str:
    """URL de la carátula si ya está en caché. No procesa la imagen."""
    try:
        cache = _cover_cache_dir()
        for path in cache.glob(f"{_cover_digest(track)}.*"):
            if path.is_file():
                return path.as_uri()
    except Exception:
        pass
    return ""


def publish_artwork(track: Any) -> str:
    """Deja la carátula en caché y devuelve su URL lo antes posible.

    Usa los bytes incrustados tal cual (sin decodificar ni redimensionar), así
    que tarda unos milisegundos y puede ejecutarse antes de publicar la pista.
    """
    existing = cached_art_url(track)
    if existing:
        return existing
    try:
        from .artwork import extract_cover_bytes

        data = extract_cover_bytes(track)
        if not data:
            return ""
        path = _cover_cache_dir() / f"{_cover_digest(track)}.{_sniff_extension(data)}"
        path.write_bytes(data)
        return path.as_uri()
    except Exception:
        return ""


def save_placeholder(track: Any, image: Any) -> str:
    """Guarda la portada generada para pistas sin carátula incrustada."""
    try:
        path = _cover_cache_dir() / f"{_cover_digest(track)}.png"
        if not path.is_file():
            image.save(path, format="PNG")
        return path.as_uri()
    except Exception:
        return ""


class MprisServer:
    """Servidor MPRIS2 mínimo, en un hilo aparte."""

    def __init__(self, on_action: Callable[[str, Any], None]) -> None:
        self._on_action = on_action
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._conn: Any = None

        # Estado publicado. La posición se extrapola con el reloj para que la
        # barra de la isla avance suave aunque solo la actualicemos cada segundo.
        self._title = ""
        self._artist = ""
        self._album = ""
        self._length = 0.0
        self._art_url = ""
        self._track_id = NO_TRACK
        self._status = "Stopped"
        self._volume = 1.0
        self._position = 0.0
        self._position_at = time.monotonic()
        self._has_track = False
        self._can_next = False
        self._can_previous = False

    # ------------------------------------------------------------- estado
    def update(
        self,
        *,
        title: str | None = None,
        artist: str | None = None,
        album: str | None = None,
        length: float | None = None,
        art_url: str | None = None,
        track_id: str | None = None,
        status: str | None = None,
        volume: float | None = None,
        position: float | None = None,
        has_track: bool | None = None,
        can_next: bool | None = None,
        can_previous: bool | None = None,
    ) -> None:
        """Actualiza el estado publicado. Seguro desde el hilo de la UI."""
        with self._lock:
            if title is not None:
                self._title = title
            if artist is not None:
                self._artist = artist
            if album is not None:
                self._album = album
            if length is not None:
                self._length = max(0.0, length)
            if art_url is not None:
                self._art_url = art_url
            if track_id is not None:
                self._track_id = track_id
            if status is not None:
                self._status = status
                self._position_at = time.monotonic()
            if volume is not None:
                self._volume = max(0.0, min(1.0, volume))
            if position is not None:
                self._position = max(0.0, position)
                self._position_at = time.monotonic()
            if has_track is not None:
                self._has_track = has_track
            if can_next is not None:
                self._can_next = can_next
            if can_previous is not None:
                self._can_previous = can_previous

    def _current_position(self) -> float:
        with self._lock:
            position = self._position
            if self._status == "Playing":
                position += time.monotonic() - self._position_at
            length = self._length
        if length > 0:
            position = min(position, length)
        return max(0.0, position)

    # ------------------------------------------------------------ arranque
    def start(self) -> bool:
        """Arranca el servicio. Devuelve False si no es posible."""
        if not DBUS_AVAILABLE or self._thread is not None:
            return False
        thread = threading.Thread(
            target=self._serve, name="syn-mpris", daemon=True
        )
        thread.start()
        self._thread = thread
        return True

    def stop(self) -> None:
        self._stopping.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            # El bucle atiende con un tiempo máximo de espera de 300 ms, así
            # que debería salir solo; cerramos la conexión si se atasca.
            thread.join(timeout=1.0)
            if thread.is_alive():
                conn = self._conn
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
                thread.join(timeout=0.5)
        self._thread = None

    # --------------------------------------------------------------- bucle
    def _serve(self) -> None:
        try:
            conn = open_dbus_connection(bus="SESSION")
        except Exception as exc:
            _debug(f"sin sesión D-Bus: {exc}")
            return

        try:
            reply = conn.send_and_get_reply(message_bus.RequestName(BUS_NAME, 0))
            result = reply.body[0] if reply.body else 0
        except Exception as exc:
            _debug(f"RequestName falló: {exc}")
            try:
                conn.close()
            except Exception:
                pass
            return

        if result != 1:
            # Ya hay otra instancia de SYN publicando MPRIS.
            _debug(f"nombre ocupado (resultado {result})")
            try:
                conn.close()
            except Exception:
                pass
            return

        self._conn = conn
        _debug("servicio MPRIS listo")
        last_props: dict[str, Any] | None = None

        while not self._stopping.is_set():
            try:
                message = conn.receive(timeout=0.3)
            except TimeoutError:
                props = self._public_props(include_position=False)
                if last_props is None:
                    last_props = props
                elif props != last_props:
                    changed = {
                        key: value
                        for key, value in props.items()
                        if last_props.get(key) != value
                    }
                    last_props = props
                    self._emit_changed(conn, changed)
                continue
            except Exception as exc:
                _debug(f"conexión terminada: {exc}")
                break

            if message.header.message_type != MessageType.method_call:
                continue
            try:
                self._handle(conn, message)
            except Exception as exc:
                _debug(f"error atendiendo llamada: {exc}")

        try:
            conn.send(message_bus.ReleaseName(BUS_NAME))
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        _debug("servicio detenido")

    def _emit_changed(self, conn: Any, changed: dict[str, Any]) -> None:
        if not changed:
            return
        address = DBusAddress(OBJECT_PATH, bus_name=BUS_NAME, interface=IFACE_PROPS)
        try:
            conn.send(
                new_signal(
                    address,
                    "PropertiesChanged",
                    "sa{sv}as",
                    (IFACE_PLAYER, changed, []),
                )
            )
            _debug(f"emitido PropertiesChanged {sorted(changed)}")
        except Exception as exc:
            _debug(f"no se pudo emitir PropertiesChanged: {exc}")

    # ---------------------------------------------------------- propiedades
    def _metadata(self) -> dict[str, Any]:
        with self._lock:
            title = self._title
            artist = self._artist
            album = self._album
            length = self._length
            art_url = self._art_url
            track_id = self._track_id if self._has_track else NO_TRACK

        metadata: dict[str, Any] = {
            "mpris:trackid": ("o", track_id),
            "xesam:title": ("s", title or "SYN"),
        }
        if artist:
            metadata["xesam:artist"] = ("as", [artist])
        if album:
            metadata["xesam:album"] = ("s", album)
        if length > 0:
            metadata["mpris:length"] = ("x", int(length * 1_000_000))
        if art_url:
            metadata["mpris:artUrl"] = ("s", art_url)
        return metadata

    def _public_props(self, *, include_position: bool = True) -> dict[str, Any]:
        with self._lock:
            status = self._status
            volume = self._volume
            can_next = self._can_next
            can_previous = self._can_previous
            has_track = self._has_track

        props: dict[str, Any] = {
            "PlaybackStatus": ("s", status),
            "LoopStatus": ("s", "None"),
            "Rate": ("d", 1.0),
            "Shuffle": ("b", False),
            "Metadata": ("a{sv}", self._metadata()),
            "Volume": ("d", volume),
            "MinimumRate": ("d", 1.0),
            "MaximumRate": ("d", 1.0),
            "CanGoNext": ("b", can_next),
            "CanGoPrevious": ("b", can_previous),
            "CanPlay": ("b", has_track),
            "CanPause": ("b", status != "Stopped"),
            "CanSeek": ("b", False),
            "CanControl": ("b", True),
        }
        if include_position:
            props["Position"] = ("x", int(self._current_position() * 1_000_000))
        return props

    def _root_props(self) -> dict[str, Any]:
        return {
            "CanQuit": ("b", False),
            "CanRaise": ("b", False),
            "HasTrackList": ("b", False),
            "Identity": ("s", "SYN"),
            "DesktopEntry": ("s", "syn"),
            "SupportedUriSchemes": ("as", ["file"]),
            "SupportedMimeTypes": ("as", [
                "audio/mpeg",
                "audio/flac",
                "audio/ogg",
                "audio/wav",
            ]),
        }

    # ------------------------------------------------------------- llamadas
    def _handle(self, conn: Any, message: Any) -> None:
        fields = message.header.fields
        member = fields.get(HeaderFields.member)
        interface = fields.get(HeaderFields.interface)
        _debug(f"llamada {interface}.{member} {message.body!r}")

        if member == "Introspect":
            conn.send(new_method_return(message, "s", (_INTROSPECTION,)))
            return

        if member == "Get":
            target, prop = message.body
            props = (
                self._root_props()
                if target == IFACE_ROOT
                else self._public_props()
            )
            if prop in props:
                conn.send(new_method_return(message, "v", (props[prop],)))
            else:
                conn.send(
                    new_error(
                        message,
                        "org.freedesktop.DBus.Error.InvalidArgs",
                        f"Propiedad desconocida: {prop}",
                    )
                )
            return

        if member == "GetAll":
            (target,) = message.body
            props = (
                self._root_props()
                if target == IFACE_ROOT
                else self._public_props()
            )
            conn.send(new_method_return(message, "a{sv}", (props,)))
            return

        if member == "Set":
            target, prop, value = message.body
            self._set_property(target, prop, value)
            conn.send(new_method_return(message, "", ()))
            return

        # Métodos del reproductor.
        if member in {"Play", "Pause", "PlayPause", "Stop", "Next", "Previous"}:
            conn.send(new_method_return(message, "", ()))
            self._dispatch(member.lower())
            return

        if member in {"Raise", "Quit"}:
            conn.send(new_method_return(message, "", ()))
            return

        if member in {"Seek", "SetPosition", "OpenUri"}:
            # Sin soporte de búsqueda: se acepta y se ignora.
            conn.send(new_method_return(message, "", ()))
            return

        conn.send(
            new_error(
                message,
                "org.freedesktop.DBus.Error.UnknownMethod",
                f"Método no soportado: {member}",
            )
        )

    def _set_property(self, target: str, prop: str, value: Any) -> None:
        signature, raw = value
        if prop == "Volume" and signature == "d":
            self._dispatch("volume", float(raw))
        # LoopStatus, Shuffle y Rate se aceptan pero no se aplican.

    def _dispatch(self, action: str, value: Any = None) -> None:
        try:
            self._on_action(action, value)
        except Exception as exc:  # pragma: no cover - nunca debe tumbar el hilo
            _debug(f"acción {action} falló: {exc}")
