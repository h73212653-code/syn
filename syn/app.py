"""Aplicación Textual de SYN."""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from rich.markup import escape
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Gradient
from textual.containers import Container, Horizontal
from textual.widgets import Input, Label, OptionList, ProgressBar, Static

from .artwork import create_placeholder, load_cover
from .config import Config
from .lyrics import LyricLine, Lyrics, fetch_lyrics_data
from .theme import ThemeManager
from .library import Section, Track, scan_sections
from .mpris import (
    NO_TRACK,
    MprisServer,
    cached_art_url,
    publish_artwork,
    save_placeholder,
    track_object_path,
)
from .player import PlaybackError, PlaybackState, Player
from .widgets import CoverStage, TrackList, build_logo

FOOTER = (
    "[b #67e8f9]Espacio[/] [#94a3b8]pausa[/]  "
    "[b #f0abfc]Enter[/] [#94a3b8]reproducir[/]  "
    "[b #67e8f9]n/p[/] [#94a3b8]pista[/]  "
    "[b #f0abfc]←/→[/] [#94a3b8]carpeta[/]\n"
    "[b #67e8f9]y/u[/] [#94a3b8]volumen[/]  "
    "[b #f0abfc]m[/] [#94a3b8]mudo[/]  "
    "[b #f0abfc]t[/] [#94a3b8]fondo[/]  "
    "[b #f0abfc]l[/] [#94a3b8]letras[/]  "
    "[b #67e8f9]/[/] [#94a3b8]buscar[/]  "
    "[b #67e8f9]q[/] [#94a3b8]salir[/]"
)

FOOTER_ON = FOOTER.replace(
    "[b #f0abfc]t[/] [#94a3b8]fondo[/]",
    "[b #67e8f9]t[/] [#67e8f9]fondo ON[/]",
).replace(
    "[b #f0abfc]l[/] [#94a3b8]letras[/]",
    "[b #67e8f9]l[/] [#67e8f9]letras ON[/]",
)


def format_time(seconds: float | None) -> str:
    """Formatea segundos como m:ss o h:mm:ss."""
    if seconds is None:
        return "--:--"
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _fold(text: str) -> str:
    """Minúsculas y sin acentos: «cancion» también encuentra «Canción».

    La normalización va antes y después de ``casefold`` para que también
    funcionen letras «decorativas» de YouTube (𝙋𝘼𝙎𝘼 → pasa) y la I turca.
    """
    decomposed = unicodedata.normalize("NFKD", text).casefold()
    decomposed = unicodedata.normalize("NFKD", decomposed)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _search_score(track: Track, folder: str, terms: list[str]) -> int | None:
    """Puntúa una pista para la búsqueda; ``None`` si no coincide.

    Cuanto menor es el número, más arriba sale: primero las que empiezan
    por lo escrito, luego las que lo contienen en el título, el artista o
    el álbum/carpeta.
    """
    title = _fold(track.title)
    artist = _fold(track.artist)
    album = _fold(track.album)
    haystack = f"{title} {artist} {album} {folder}"
    if not all(term in haystack for term in terms):
        return None

    phrase = " ".join(terms)
    if title.startswith(phrase):
        return 0
    if phrase in title:
        return 1
    if phrase in artist:
        return 2
    if phrase in album or phrase in folder:
        return 3
    return 4


class SynApp(App[None]):
    """Reproductor local SYN."""

    TITLE = "SYN"
    SUB_TITLE = "Reproductor local"
    CSS_PATH = Path(__file__).with_name("styles.tcss")

    BINDINGS = [
        Binding("space", "toggle_playback", "Pausar/Reanudar", show=False),
        Binding("enter", "play_selected", "Reproducir", show=False),
        Binding("n", "next_track", "Siguiente", show=False),
        Binding("p", "previous_track", "Anterior", show=False),
        Binding("left", "previous_section", "Carpeta anterior", show=False),
        Binding("right", "next_section", "Carpeta siguiente", show=False),
        Binding("y", "volume_up", "Subir volumen", show=False),
        Binding("u", "volume_down", "Bajar volumen", show=False),
        Binding("plus", "volume_up", "Subir volumen", show=False),
        Binding("equals", "volume_up", "Subir volumen", show=False),
        Binding("minus", "volume_down", "Bajar volumen", show=False),
        Binding("underscore", "volume_down", "Bajar volumen", show=False),
        Binding("m", "toggle_mute", "Silenciar", show=False),
        Binding("t", "toggle_transparency", "Transparencia", show=False),
        Binding("l", "toggle_lyrics", "Letras", show=True),
        Binding("slash", "search", "Buscar", show=True),
        Binding("ctrl+f", "search", "Buscar", show=False),
        Binding("escape", "close_search", "Cerrar búsqueda", show=False),
        Binding("q", "quit", "Salir", show=False),
    ]

    def __init__(self, config: Config) -> None:
        # ansi_default debe llegar al terminal como color «default»; de lo
        # contrario Textual lo convierte al fondo opaco de su tema y el modo
        # transparente no se vería.
        super().__init__(ansi_color=True)
        self.config = config
        self.tracks: list[Track] = []
        self.sections: list[Section] = []
        self.section_index = 0
        self.current_index: int | None = None
        self.playing_track: Track | None = None
        self.playing_section: int | None = None
        self.player = Player()
        self.mpris = MprisServer(self._on_mpris_action)
        self._cover_token = 0
        self._cover_art_url = ""
        self._closing = False
        self._transparent = False
        self._lyrics_visible = False
        self._lyrics_token = 0
        self._lyrics_plain = ""
        self._lyrics_synced: tuple[LyricLine, ...] = ()
        self._lyrics_times: list[float] = []
        self._lyrics_index = -2  # -2 = aún sin pintar
        self._lyrics_instrumental = False
        self._lyrics_track_path: Path | None = None
        self._lyrics_cache: dict[tuple[str, str], Lyrics | None] = {}
        self._search_active = False
        self._search_section = 0
        self._track_sections: dict[int, int] = {}
        self._primary_color = "#a78bfa"
        self.theme_manager = ThemeManager(config.theme_index)
        self._active_gradient = Gradient.from_colors(*self.theme_manager.get_current().gradient)
        self._paused_gradient = Gradient.from_colors("#334155", "#64748b")
        self._logo_key: tuple[int, int] | None = None

    # ------------------------------------------------------------------ UI
    def compose(self) -> ComposeResult:
        with Horizontal(id="top"):
            with Container(id="now-playing"):
                yield CoverStage(id="cover-stage")
                with Container(id="cover-meta"):
                    yield Label(
                        "Cargando…",
                        id="meta-title",
                        classes="meta-label",
                    )
                    yield Label(
                        "Buscando tu música",
                        id="meta-artist",
                        classes="meta-label",
                    )
                    yield Label(
                        str(self.config.music_dir),
                        id="meta-album",
                        classes="meta-label",
                    )
            with Container(id="library-panel"):
                yield Static(
                    "[#f0abfc]♛[/]  [#67e8f9]S[/][#7dd3fc]Y[/]"
                    "[#a78bfa]N[/]  [#475569]·[/]  "
                    "[#94a3b8]Reproductor local[/]",
                    id="logo-title",
                )
                yield Static(build_logo(), id="logo")
                with Horizontal(id="library-heading"):
                    yield Static("Música →", id="music-heading")
                    yield Static("Buscando…", id="track-count")
                yield Input(
                    placeholder="Buscar título, artista o carpeta…",
                    id="search-input",
                    classes="hidden",
                )
                yield Static("", id="folder-tabs", classes="hidden")
                yield TrackList(id="track-list")
                yield Static("", id="lyrics-panel", classes="hidden")

        with Container(id="bottom"):
            with Horizontal(id="progress-row"):
                yield Label("■", id="play-state")
                yield Label("0:00", id="time-elapsed")
                yield ProgressBar(
                    total=1,
                    show_percentage=False,
                    show_eta=False,
                    id="progress-bar",
                    gradient=self._active_gradient,
                )
                yield Label("--:--", id="time-total")
                yield Label("Vol 82%", id="volume-label")
            yield Static(FOOTER, id="footer")

    def on_mount(self) -> None:
        self.mpris.start()
        self.set_interval(1.0, self._tick)
        self.query_one("#track-list", TrackList).focus()
        self._update_volume_ui()
        self._apply_theme()
        self.call_after_refresh(self._update_logo)

        if not self.config.music_dir.is_dir():
            self._show_empty_state(
                title="Sin música",
                artist="No se encontró la carpeta",
                album=str(self.config.music_dir),
            )
            self.notify(
                f"No existe la carpeta de música:\n{self.config.music_dir}",
                severity="warning",
                timeout=7,
            )
            self._load_placeholder_async()
            return

        self._scan_library()

    def on_resize(self, event: events.Resize) -> None:
        self.call_after_refresh(self._update_logo)
        self.call_after_refresh(self._refresh_lyrics)

    def _update_logo(self) -> None:
        """Elige el logo más grande que quepa en el panel derecho."""
        try:
            panel = self.query_one("#library-panel", Container)
        except Exception:
            return

        width = panel.content_size.width
        height = panel.content_size.height
        if width <= 0 or height <= 0:
            return

        # Reserva filas para el encabezado, las pestañas, «Música →» y la lista.
        max_height = max(4, height - 7)
        key = (width, max_height)
        if key == self._logo_key:
            return

        self._logo_key = key
        self.query_one("#logo", Static).update(
            build_logo(max_width=width, max_height=max_height)
        )

    def on_unmount(self) -> None:
        self._closing = True
        self.mpris.stop()
        self.player.shutdown()

    # Con el protocolo de teclado de Kitty, en un teclado español «/» es
    # Mayús+7 y llega como «shift+7» sin carácter: el binding «slash» no se
    # dispara. Se aceptan todas las formas en que puede llegar la tecla.
    SEARCH_KEYS = frozenset({"slash", "shift+7", "divide", "kp_divide"})

    def on_key(self, event: events.Key) -> None:
        # Mientras se escribe en el buscador, «q» es una letra más.
        if isinstance(self.focused, Input):
            return
        if event.key == "q":
            self.exit()
            return
        if event.key in self.SEARCH_KEYS or event.character == "/":
            event.stop()
            self.action_search()

    def check_action(
        self, action: str, parameters: tuple[object, ...]
    ) -> bool | None:
        """Desactiva los atajos de una tecla mientras se escribe la búsqueda."""
        if isinstance(self.focused, Input):
            return action in {"search", "close_search", "quit"}
        return True

    async def action_quit(self) -> None:
        self._closing = True
        self.mpris.stop()
        self.player.shutdown()
        await super().action_quit()

    # ------------------------------------------------------------- library
    def _scan_library(self) -> None:
        root = self.config.music_dir
        recursive = self.config.recursive

        def worker() -> None:
            try:
                sections = scan_sections(root, recursive)
            except Exception as exc:  # error inesperado del sistema de archivos
                try:
                    self.call_from_thread(self._on_library_error, str(exc))
                except RuntimeError:
                    pass
                return
            try:
                self.call_from_thread(self._on_library_loaded, sections)
            except RuntimeError:
                pass

        self.run_worker(
            worker,
            group="library",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _on_library_loaded(self, sections: list[Section]) -> None:
        if self._closing:
            return

        self.sections = sections
        self._track_sections = {
            id(track): index
            for index, section in enumerate(sections)
            for track in section.tracks
        }
        self.section_index = 0
        self._render_tabs()

        if not sections:
            self.tracks = []
            self.current_index = None
            self.query_one("#track-list", TrackList).set_tracks([])
            self.query_one("#track-count", Static).update("0 canciones")
            self._show_empty_state(
                title="Sin pistas",
                artist="Añade archivos MP3, FLAC, WAV u OGG",
                album=str(self.config.music_dir),
            )
            self._load_placeholder_async()
            self.notify(
                "No se encontraron archivos de audio en "
                f"{self.config.music_dir}",
                severity="warning",
                timeout=7,
            )
            return

        self._select_section(0, focus_list=True)

    def _render_tabs(self) -> None:
        """Dibuja las pestañas de carpetas con la sección activa resaltada."""
        tabs = self.query_one("#folder-tabs", Static)
        if len(self.sections) <= 1:
            tabs.update("")
            tabs.set_class(True, "hidden")
            return

        tabs.set_class(False, "hidden")
        text = Text(no_wrap=True, overflow="ellipsis")
        for index, section in enumerate(self.sections):
            if index:
                text.append(" ")
            active = index == self.section_index
            style = (
                "bold #05070b on #67e8f9"
                if active
                else "#94a3b8 on #101725"
            )
            text.append(f" {section.name} ", style=style)
        tabs.update(text)

    def _select_section(self, index: int, *, focus_list: bool) -> None:
        """Muestra la carpeta indicada y selecciona su primera pista."""
        if not (0 <= index < len(self.sections)):
            return

        self.section_index = index
        section = self.sections[index]
        self.tracks = section.tracks
        self.current_index = None

        track_list = self.query_one("#track-list", TrackList)
        track_list.set_tracks(self.tracks)
        self.query_one("#track-count", Static).update(
            f"{len(self.tracks)} canción"
            if len(self.tracks) == 1
            else f"{len(self.tracks)} canciones"
        )
        self._render_tabs()
        self._prewarm_covers(section)

        if self.tracks:
            self._select_index(0, focus_list=focus_list)
            self._refresh_playback_marker()
            if focus_list:
                track_list.focus()
        else:
            self._show_empty_state(
                title=section.name,
                artist="Carpeta vacía",
                album=str(self.config.music_dir / section.name),
            )
            if self._lyrics_visible:
                self.query_one("#lyrics-panel", Static).update(
                    "Esta carpeta no tiene canciones."
                )

    def action_previous_section(self) -> None:
        self._change_section(-1)

    def action_next_section(self) -> None:
        self._change_section(1)

    def _change_section(self, delta: int) -> None:
        if len(self.sections) < 2:
            return
        if self._search_active:
            self._close_search()
        index = (self.section_index + delta) % len(self.sections)
        self._select_section(index, focus_list=False)
        self.query_one("#track-list", TrackList).focus()

    def _on_library_error(self, message: str) -> None:
        if self._closing:
            return
        self._show_empty_state(
            title="Error al leer la música",
            artist="Revisa los permisos de la carpeta",
            album=str(self.config.music_dir),
        )
        self._load_placeholder_async()
        self.notify(message, severity="error", timeout=8)

    def _show_empty_state(self, title: str, artist: str, album: str) -> None:
        self.current_index = None
        self.query_one("#meta-title", Label).update(Text(title))
        self.query_one("#meta-artist", Label).update(Text(artist))
        self.query_one("#meta-album", Label).update(Text(album))
        self.query_one("#play-state", Label).update("■")
        self.query_one("#time-elapsed", Label).update("0:00")
        self.query_one("#time-total", Label).update("--:--")
        progress = self.query_one("#progress-bar", ProgressBar)
        progress.update(total=1, progress=0)
        progress.gradient = self._active_gradient
        self.sub_title = "Reproductor local"

    # -------------------------------------------------------------- búsqueda
    def action_search(self) -> None:
        """Abre la barra de búsqueda global (tecla ``/``)."""
        if not self.sections:
            self.notify("La biblioteca aún se está cargando", timeout=3)
            return

        search = self.query_one("#search-input", Input)
        if not self._search_active:
            self._search_active = True
            self._search_section = self.section_index
            self.query_one("#library-panel", Container).add_class("searching")
            search.remove_class("hidden")
        search.focus()
        search.cursor_position = len(search.value)

    def action_close_search(self) -> None:
        self._close_search()

    def _close_search(self) -> None:
        """Cierra el buscador y vuelve a la carpeta en la que estabas."""
        if not self._search_active:
            return
        self._search_active = False
        search = self.query_one("#search-input", Input)
        search.value = ""
        search.add_class("hidden")
        self.query_one("#library-panel", Container).remove_class("searching")
        self._select_section(self._search_section, focus_list=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._filter_tracks(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "search-input":
            return
        event.stop()
        self.query_one("#track-list", TrackList).focus()

    def _filter_tracks(self, query: str) -> None:
        """Muestra todas las pistas de la biblioteca que coinciden."""
        if not self._search_active:
            return  # el valor se limpia al cerrar; no pisar la carpeta

        terms = _fold(query).split()
        track_list = self.query_one("#track-list", TrackList)
        count = self.query_one("#track-count", Static)

        if not terms:
            self.tracks = []
            self.current_index = None
            track_list.set_tracks([])
            count.update("Escribe para buscar")
            self._refresh_playback_marker()
            return

        scored: list[tuple[int, tuple[str, str, str, str], Track]] = []
        for section in self.sections:
            folder = _fold(section.name)
            for track in section.tracks:
                score = _search_score(track, folder, terms)
                if score is not None:
                    scored.append((score, track.sort_key, track))
        scored.sort(key=lambda item: (item[0], item[1]))

        self.tracks = [item[2] for item in scored]
        self.current_index = None
        track_list.set_tracks(self.tracks)
        count.update(
            "1 resultado"
            if len(self.tracks) == 1
            else f"{len(self.tracks)} resultados"
        )
        self._refresh_playback_marker()

        if self.tracks:
            self._select_index(0, focus_list=False)
            self._prewarm_tracks(self.tracks[:12])

    # ------------------------------------------------------------- playback
    def _select_index(self, index: int, *, focus_list: bool) -> None:
        if not (0 <= index < len(self.tracks)):
            return

        self.current_index = index
        track = self.tracks[index]

        self.query_one("#meta-title", Label).update(Text(track.title))
        self.query_one("#meta-artist", Label).update(Text(track.artist))
        self.query_one("#meta-album", Label).update(Text(track.album))
        self.sub_title = f"{track.title} — {track.artist}"

        progress = self.query_one("#progress-bar", ProgressBar)
        total = track.duration if track.duration > 0 else 1
        progress.update(total=total, progress=0)
        self.query_one("#time-elapsed", Label).update("0:00")
        self.query_one("#time-total", Label).update(
            format_time(track.duration) if track.duration > 0 else "--:--"
        )

        track_list = self.query_one("#track-list", TrackList)
        if focus_list:
            track_list.focus_index(index)

        # La carátula queda lista antes de publicar la pista por MPRIS: así la
        # isla no arranca su búsqueda en iTunes (1 s) ni muestra otra portada.
        self._cover_art_url = publish_artwork(track)
        self._load_cover_async(track)

        if self._lyrics_visible:
            self._load_lyrics_async(track)

        self._update_mpris()

    def _play_index(self, index: int) -> None:
        if not (0 <= index < len(self.tracks)):
            return

        track = self.tracks[index]
        self._select_index(index, focus_list=True)
        self._start_playback(track, self._section_of(track))

    def _start_playback(self, track: Track, section_index: int) -> None:
        try:
            self.player.play(track.path)
        except PlaybackError as exc:
            self.playing_track = None
            self.playing_section = None
            self._set_state_ui(PlaybackState.STOPPED)
            self.notify(str(exc), severity="error", timeout=7)
            return

        self.playing_track = track
        self.playing_section = section_index
        self.query_one("#time-elapsed", Label).update("0:00")
        self._set_state_ui(PlaybackState.PLAYING)

    def _playing_index_in_visible(self) -> int | None:
        """Índice de la pista sonando dentro de la lista visible, si está."""
        if self.playing_track is None:
            return None
        for index, track in enumerate(self.tracks):
            if track is self.playing_track:
                return index
        return None

    def _section_of(self, track: Track) -> int:
        """Carpeta a la que pertenece una pista (también desde la búsqueda)."""
        index = self._track_sections.get(id(track))
        if index is not None:
            return index
        for index, section in enumerate(self.sections):
            if any(item is track for item in section.tracks):
                return index
        return self.section_index

    def _sync_visible_selection(self) -> None:
        """Selecciona en la lista la pista que acaba de empezar a sonar."""
        index = self._playing_index_in_visible()
        if index is not None and index != self.current_index:
            self._select_index(index, focus_list=False)

    def _refresh_playback_marker(self) -> None:
        """Vuelve a marcar la pista en reproducción tras cambiar de carpeta."""
        track_list = self.query_one("#track-list", TrackList)
        paused = self.player.state is PlaybackState.PAUSED
        track_list.set_playback_state(
            self._playing_index_in_visible(), paused=paused
        )

    def _set_state_ui(self, state: PlaybackState) -> None:
        state_label = self.query_one("#play-state", Label)
        progress = self.query_one("#progress-bar", ProgressBar)
        track_list = self.query_one("#track-list", TrackList)
        index = self._playing_index_in_visible()

        if state is PlaybackState.PLAYING:
            state_label.update("▶")
            progress.gradient = self._active_gradient
            track_list.set_playback_state(index, paused=False)
        elif state is PlaybackState.PAUSED:
            state_label.update("❚❚")
            progress.gradient = self._paused_gradient
            track_list.set_playback_state(index, paused=True)
        else:
            state_label.update("■")
            progress.gradient = self._active_gradient
            track_list.set_playback_state(None, paused=False)

        self._update_mpris()

    # ---------------------------------------------------------------- MPRIS
    def _update_mpris(self) -> None:
        """Publica el estado actual para la isla y el escritorio."""
        if self._closing:
            return

        track = self.playing_track
        if track is None and self.current_index is not None and self.tracks:
            track = self.tracks[self.current_index]

        state = self.player.state
        status = {
            PlaybackState.PLAYING: "Playing",
            PlaybackState.PAUSED: "Paused",
        }.get(state, "Stopped")

        if track is None:
            self.mpris.update(
                title="",
                artist="",
                album="",
                length=0.0,
                track_id=NO_TRACK,
                has_track=False,
                status=status,
                volume=self.player.effective_volume,
                position=0.0,
                can_next=False,
                can_previous=False,
                art_url="",
            )
            return

        position = (
            self.player.position()
            if state is not PlaybackState.STOPPED
            else 0.0
        )
        self.mpris.update(
            title=track.title,
            artist=track.artist,
            album=track.album,
            length=track.duration,
            track_id=track_object_path(track),
            status=status,
            volume=self.player.effective_volume,
            position=position,
            has_track=True,
            can_next=True,
            can_previous=True,
            art_url=self._cover_art_url,
        )

    def _on_mpris_action(self, action: str, value: Any = None) -> None:
        """Llega desde el hilo de D-Bus; se reenvía al de la interfaz."""
        if self._closing:
            return
        try:
            self.call_from_thread(self._apply_mpris_action, action, value)
        except RuntimeError:
            pass

    def _apply_mpris_action(self, action: str, value: Any = None) -> None:
        if self._closing:
            return

        if action == "playpause":
            self.action_toggle_playback()
        elif action == "play":
            if self.player.state is PlaybackState.PAUSED:
                self.action_toggle_playback()
            elif self.player.state is PlaybackState.STOPPED:
                self.action_play_selected()
        elif action == "pause":
            if self.player.state is PlaybackState.PLAYING:
                self.action_toggle_playback()
        elif action == "stop":
            self._stop_playback()
        elif action == "next":
            self._skip_playback(1)
        elif action == "previous":
            self._skip_playback(-1)
        elif action == "volume" and value is not None:
            self.player.set_volume(float(value))
            self._update_volume_ui()

        self._update_mpris()

    def _skip_playback(self, delta: int) -> None:
        """Siguiente/anterior dentro de la carpeta que está sonando."""
        if self.playing_track is None or self.playing_section is None:
            if self.tracks:
                self._play_index(0)
            return
        if not (0 <= self.playing_section < len(self.sections)):
            return

        tracks = self.sections[self.playing_section].tracks
        if not tracks:
            return

        try:
            index = next(
                i for i, item in enumerate(tracks)
                if item is self.playing_track
            )
        except StopIteration:
            index = -1

        next_index = (index + delta) % len(tracks)
        self._start_playback(tracks[next_index], self.playing_section)
        self._sync_visible_selection()

    def _stop_playback(self) -> None:
        self.player.stop()
        self.playing_track = None
        self.playing_section = None
        self.query_one("#time-elapsed", Label).update("0:00")
        self.query_one("#progress-bar", ProgressBar).update(progress=0)
        self._set_state_ui(PlaybackState.STOPPED)

    def _selected_or_current_index(self) -> int | None:
        track_list = self.query_one("#track-list", TrackList)
        if track_list.highlighted is not None and track_list.tracks:
            return track_list.highlighted
        return self.current_index

    def action_play_selected(self) -> None:
        if not self.tracks:
            return
        index = self._selected_or_current_index()
        if index is not None:
            self._play_index(index)

    def action_toggle_playback(self) -> None:
        if not self.tracks:
            return

        if self.player.state is PlaybackState.PLAYING:
            self.player.toggle_pause()
            self._set_state_ui(PlaybackState.PAUSED)
        elif self.player.state is PlaybackState.PAUSED:
            self.player.toggle_pause()
            self._set_state_ui(PlaybackState.PLAYING)
        else:
            index = self.current_index
            if index is None:
                index = self._selected_or_current_index()
            if index is not None:
                self._play_index(index)

    def action_next_track(self) -> None:
        if not self.tracks:
            return
        if self.current_index is None:
            self._play_index(0)
        else:
            self._play_index((self.current_index + 1) % len(self.tracks))

    def action_previous_track(self) -> None:
        if not self.tracks:
            return
        if self.current_index is None:
            self._play_index(0)
        else:
            self._play_index((self.current_index - 1) % len(self.tracks))

    def action_volume_up(self) -> None:
        self.player.change_volume(0.05)
        self._update_volume_ui()

    def action_volume_down(self) -> None:
        self.player.change_volume(-0.05)
        self._update_volume_ui()

    def action_toggle_mute(self) -> None:
        self.player.toggle_mute()
        self._update_volume_ui()

    def action_toggle_transparency(self) -> None:
        """Alterna el modo transparente."""
        self._transparent = not self._transparent
        if self._transparent:
            self.add_class("transparent")
            self.notify("Transparencia ACTIVADA")
        else:
            self.remove_class("transparent")
            self.notify("Transparencia DESACTIVADA")

    def action_toggle_lyrics(self) -> None:
        """Muestra u oculta el panel de letras."""
        self._lyrics_visible = not self._lyrics_visible
        lyrics_panel = self.query_one("#lyrics-panel", Static)

        if not self._lyrics_visible:
            self._lyrics_token += 1  # descarta respuestas pendientes
            self.query_one("#footer", Static).update(FOOTER)
            lyrics_panel.add_class("hidden")
            return

        self.query_one("#footer", Static).update(FOOTER_ON)
        lyrics_panel.remove_class("hidden")
        self.call_after_refresh(self._refresh_lyrics)

        if self.current_index is None or not self.tracks:
            lyrics_panel.update("Selecciona una canción para ver su letra.")
            return

        track = self.tracks[self.current_index]
        self._load_lyrics_async(track)

    def _load_lyrics_async(self, track: Track) -> None:
        """Busca la letra en segundo plano para no bloquear la interfaz."""
        self._lyrics_token += 1
        token = self._lyrics_token

        cache_key = (track.artist.casefold(), track.title.casefold())
        if cache_key in self._lyrics_cache:
            self._apply_lyrics(token, track, self._lyrics_cache[cache_key])
            return

        if self._lyrics_visible:
            self.query_one("#lyrics-panel", Static).update(
                f"Buscando letra de\n{escape(track.title)}…"
            )

        def worker() -> None:
            try:
                lyrics = fetch_lyrics_data(
                    track.artist, track.title, track.duration
                )
            except Exception:
                lyrics = None
            try:
                self.call_from_thread(
                    self._store_lyrics, token, cache_key, track, lyrics
                )
            except RuntimeError:
                pass

        self.run_worker(
            worker,
            group="lyrics",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _store_lyrics(
        self,
        token: int,
        cache_key: tuple[str, str],
        track: Track,
        lyrics: Lyrics | None,
    ) -> None:
        # Cache pequeña y acotada: LRCLIB es gratuito y no conviene abusar.
        if len(self._lyrics_cache) >= 64:
            self._lyrics_cache.clear()
        self._lyrics_cache[cache_key] = lyrics
        self._apply_lyrics(token, track, lyrics)

    def _apply_lyrics(
        self, token: int, track: Track, lyrics: Lyrics | None
    ) -> None:
        if self._closing or token != self._lyrics_token:
            return
        if not self._lyrics_visible:
            return

        panel = self.query_one("#lyrics-panel", Static)

        self._lyrics_plain = (lyrics.plain if lyrics else None) or ""
        self._lyrics_synced = lyrics.synced if lyrics else ()
        self._lyrics_instrumental = bool(lyrics and lyrics.instrumental)
        self._lyrics_times = [line.time for line in self._lyrics_synced]
        self._lyrics_index = -2
        self._lyrics_track_path = track.path

        if self._lyrics_synced:
            position = (
                self._current_position() if self._lyrics_match_playing() else 0.0
            )
            self._render_synced_lyrics(position)
            return

        if self._lyrics_plain:
            # Text() evita que Rich interprete corchetes de la propia letra.
            panel.update(Text(self._lyrics_plain))
            return

        if self._lyrics_instrumental:
            panel.update(
                "[#64748b]Canción instrumental[/]\n"
                f"[b]{escape(track.title)}[/]\n"
                f"[#94a3b8]{escape(track.artist)}[/]"
            )
            return

        panel.update(
            "[#64748b]No hay letra disponible para[/]\n"
            f"[b]{escape(track.title)}[/]\n"
            f"[#94a3b8]{escape(track.artist)}[/]"
        )

    # --------------------------------------------------------------- letras
    def _current_position(self) -> float:
        """Posición actual del reproductor, nunca negativa."""
        try:
            return max(0.0, self.player.position())
        except Exception:
            return 0.0

    def _lyrics_match_playing(self) -> bool:
        """¿La letra cargada es la de la canción que suena?"""
        return (
            self.playing_track is not None
            and self._lyrics_track_path is not None
            and self._lyrics_track_path == self.playing_track.path
        )

    def _lyrics_window_size(self, panel: Static) -> int:
        """Cuántas líneas caben en el panel, con margen para líneas largas."""
        try:
            height = panel.content_size.height
        except Exception:
            height = 0
        if height <= 0:
            height = 12
        return max(3, min(17, height - 2))

    def _refresh_lyrics(self) -> None:
        """Repinta la ventana de letra (al mostrarla o al cambiar el tamaño)."""
        if not self._lyrics_visible or not self._lyrics_synced:
            return
        self._lyrics_index = -2
        position = self._current_position() if self._lyrics_match_playing() else 0.0
        self._render_synced_lyrics(position)

    def _render_synced_lyrics(self, position: float) -> None:
        """Pinta una ventana de líneas centrada en la que está sonando."""
        lines = self._lyrics_synced
        if not lines:
            return

        index = bisect_right(self._lyrics_times, position) - 1
        # En los silencios LRC suele haber líneas vacías: mantener resaltada
        # la última línea con texto se lee mejor que resaltar un hueco.
        while index >= 0 and not lines[index].text:
            index -= 1
        if index == self._lyrics_index:
            return  # misma línea: no hay nada que repintar
        self._lyrics_index = index

        panel = self.query_one("#lyrics-panel", Static)
        visible = self._lyrics_window_size(panel)
        half = visible // 2
        start = min(max(0, index - half), max(0, len(lines) - visible))
        end = min(len(lines), start + visible)

        text = Text()
        for i in range(start, end):
            line = lines[i]
            if i == index:
                style = f"bold {self._primary_color}"
            elif i < index:
                style = "#475569"
            else:
                style = "#94a3b8"
            # Una línea vacía conserva el ritmo vertical de la canción.
            text.append(line.text or " ", style=style)
            if i != end - 1:
                text.append("\n")
        panel.update(text)

    def _apply_theme(self) -> None:
        """Aplica el tema actual a los elementos de la interfaz."""
        theme = self.theme_manager.get_current()
        self._active_gradient = Gradient.from_colors(*theme.gradient)
        
        # Aplicar colores a elementos específicos
        # Gradiente barra de progreso
        progress = self.query_one("#progress-bar", ProgressBar)
        progress.gradient = self._active_gradient
        
        # Colores de elementos basados en el tema
        primary_color = theme.gradient[0]
        secondary_color = theme.gradient[1]
        self._primary_color = primary_color
        
        self.query_one("#meta-artist", Label).styles.color = primary_color
        self.query_one("#play-state", Label).styles.color = primary_color
        self.query_one("#logo", Static).styles.color = primary_color
        
        # Actualizar track-list highlights si fuera posible, 
        # aunque el CSS es estático, podemos forzar el refresh
        self.refresh()

    def _save_theme_preference(self) -> None:
        """Guarda el índice del tema actual en el archivo de configuración del usuario."""
        from .config import _user_config_path
        
        path = _user_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Leer el contenido existente o crear nuevo diccionario
        config_data = {}
        if path.is_file():
            import tomllib
            with path.open("rb") as f:
                config_data = tomllib.load(f)
        
        config_data["theme_index"] = self.theme_manager.index
        
        # Guardar (usamos formato básico ya que no tenemos dependencias de escritura TOML)
        with path.open("w") as f:
            for key, value in config_data.items():
                f.write(f"{key} = {repr(value)}\n")

    def _update_volume_ui(self) -> None:
        label = self.query_one("#volume-label", Label)
        if self.player.muted:
            label.update("[#f0abfc]Mudo[/]")
        else:
            label.update(f"Vol {round(self.player.volume * 100)}%")
        self.mpris.update(volume=self.player.effective_volume)

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        event.stop()
        self._play_index(event.option_index)

    def _tick(self) -> None:
        if self._closing or self.player.state is not PlaybackState.PLAYING:
            return

        track = self.playing_track
        if track is None:
            return

        if self.player.finished():
            self._advance_playback()
            return

        duration = track.duration
        position = self.player.position()
        if duration > 0:
            position = min(position, duration)
        else:
            position = 0.0

        progress = self.query_one("#progress-bar", ProgressBar)
        progress.update(total=max(duration, 1), progress=position)
        self.query_one("#time-elapsed", Label).update(format_time(position))
        self.query_one("#time-total", Label).update(
            format_time(duration) if duration > 0 else "--:--"
        )
        self.mpris.update(position=position)

        if (
            self._lyrics_visible
            and self._lyrics_synced
            and self._lyrics_match_playing()
        ):
            self._render_synced_lyrics(position)

    def _advance_playback(self) -> None:
        """Pasa a la siguiente pista de la carpeta que está sonando."""
        if self.playing_track is None or self.playing_section is None:
            return
        if not (0 <= self.playing_section < len(self.sections)):
            return

        tracks = self.sections[self.playing_section].tracks
        if not tracks:
            return

        try:
            index = next(
                i for i, item in enumerate(tracks)
                if item is self.playing_track
            )
        except StopIteration:
            index = -1

        next_index = (index + 1) % len(tracks)
        self._start_playback(tracks[next_index], self.playing_section)
        self._sync_visible_selection()

    # -------------------------------------------------------------- artwork
    def _prewarm_covers(self, section: Section) -> None:
        """Prepara las carátulas de la carpeta visible en segundo plano."""
        self._prewarm_tracks(section.tracks)

    def _prewarm_tracks(self, tracks: list[Track]) -> None:
        """Prepara carátulas de una lista corta (carpeta o resultados)."""
        pending = list(tracks)

        def worker() -> None:
            for item in pending:
                try:
                    publish_artwork(item)
                except Exception:
                    continue

        self.run_worker(
            worker,
            group="covers",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _load_cover_async(self, track: Track) -> None:
        self._cover_token += 1
        token = self._cover_token

        def worker() -> None:
            try:
                artwork = load_cover(track)
            except Exception:
                artwork = create_placeholder(track)
            url = cached_art_url(track) or save_placeholder(track, artwork)
            try:
                self.call_from_thread(self._apply_cover, token, artwork, url)
            except RuntimeError:
                pass

        self.run_worker(
            worker,
            group="artwork",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _load_placeholder_async(self) -> None:
        self._cover_token += 1
        token = self._cover_token

        def worker() -> None:
            try:
                artwork = create_placeholder(None)
            except Exception:
                return
            try:
                self.call_from_thread(self._apply_cover, token, artwork, "")
            except RuntimeError:
                pass

        self.run_worker(
            worker,
            group="artwork",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _apply_cover(
        self, token: int, artwork: PILImage.Image, art_url: str = ""
    ) -> None:
        if self._closing or token != self._cover_token:
            return
        self.query_one("#cover-stage", CoverStage).set_artwork(artwork)
        self._cover_art_url = art_url
        self._update_mpris()
