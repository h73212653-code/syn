"""Aplicación Textual de SYN."""

from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Gradient
from textual.containers import Container, Horizontal
from textual.widgets import Label, OptionList, ProgressBar, Static

from .artwork import create_placeholder, load_cover
from .config import Config
from .library import Track, scan_library
from .player import PlaybackError, PlaybackState, Player
from .widgets import CoverStage, TrackList, build_logo

FOOTER = (
    "[b #67e8f9]Espacio[/] [#94a3b8]pausa[/]  "
    "[b #f0abfc]Enter[/] [#94a3b8]reproducir[/]  "
    "[b #67e8f9]n/p[/] [#94a3b8]cambiar[/]  "
    "[b #f0abfc]y/u[/] [#94a3b8]volumen[/]  "
    "[b #67e8f9]m[/] [#94a3b8]mudo[/]  "
    "[b #f0abfc]t[/] [#94a3b8]fondo[/]  "
    "[b #67e8f9]q[/] [#94a3b8]salir[/]"
)

FOOTER_ON = FOOTER.replace(
    "[b #f0abfc]t[/] [#94a3b8]fondo[/]",
    "[b #67e8f9]t[/] [#67e8f9]fondo ON[/]",
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
        Binding("y", "volume_up", "Subir volumen", show=False),
        Binding("u", "volume_down", "Bajar volumen", show=False),
        Binding("plus", "volume_up", "Subir volumen", show=False),
        Binding("equals", "volume_up", "Subir volumen", show=False),
        Binding("minus", "volume_down", "Bajar volumen", show=False),
        Binding("underscore", "volume_down", "Bajar volumen", show=False),
        Binding("m", "toggle_mute", "Silenciar", show=False),
        Binding("t", "toggle_transparency", "Transparencia", show=False),
        Binding("q", "quit", "Salir", show=False),
    ]

    def __init__(self, config: Config) -> None:
        # ansi_default debe llegar al terminal como color «default»; de lo
        # contrario Textual lo convierte al fondo opaco de su tema y el modo
        # transparente no se vería.
        super().__init__(ansi_color=True)
        self.config = config
        self.tracks: list[Track] = []
        self.current_index: int | None = None
        self.player = Player()
        self._cover_token = 0
        self._closing = False
        self._transparent = False
        self._active_gradient = Gradient.from_colors(
            "#22d3ee", "#818cf8", "#e879f9"
        )
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
                yield TrackList(id="track-list")

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
        self.set_interval(1.0, self._tick)
        self.query_one("#track-list", TrackList).focus()
        self._update_volume_ui()
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

        # Reserva filas para el encabezado, «Música →» y la lista.
        max_height = max(4, height - 6)
        key = (width, max_height)
        if key == self._logo_key:
            return

        self._logo_key = key
        self.query_one("#logo", Static).update(
            build_logo(max_width=width, max_height=max_height)
        )

    def on_unmount(self) -> None:
        self._closing = True
        self.player.shutdown()

    def on_key(self, event: events.Key) -> None:
        if event.key == "q":
            self.exit()

    async def action_quit(self) -> None:
        # Debugging message - this will be shown in stderr if running in a terminal
        import sys
        print("Quit action triggered!", file=sys.stderr)
        self._closing = True
        self.player.shutdown()
        await super().action_quit()

    # ------------------------------------------------------------- library
    def _scan_library(self) -> None:
        root = self.config.music_dir
        recursive = self.config.recursive

        def worker() -> None:
            try:
                tracks = scan_library(root, recursive)
            except Exception as exc:  # error inesperado del sistema de archivos
                try:
                    self.call_from_thread(self._on_library_error, str(exc))
                except RuntimeError:
                    pass
                return
            try:
                self.call_from_thread(self._on_library_loaded, tracks)
            except RuntimeError:
                pass

        self.run_worker(
            worker,
            group="library",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _on_library_loaded(self, tracks: list[Track]) -> None:
        if self._closing:
            return

        self.tracks = tracks
        track_list = self.query_one("#track-list", TrackList)
        track_list.set_tracks(tracks)
        count_label = self.query_one("#track-count", Static)
        count_label.update(
            f"{len(tracks)} canción" if len(tracks) == 1 else f"{len(tracks)} canciones"
        )

        if not tracks:
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

        self._select_index(0, focus_list=True)
        track_list.focus()

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
        self.query_one("#meta-title", Label).update(title)
        self.query_one("#meta-artist", Label).update(artist)
        self.query_one("#meta-album", Label).update(album)
        self.query_one("#play-state", Label).update("■")
        self.query_one("#time-elapsed", Label).update("0:00")
        self.query_one("#time-total", Label).update("--:--")
        progress = self.query_one("#progress-bar", ProgressBar)
        progress.update(total=1, progress=0)
        progress.gradient = self._active_gradient
        self.sub_title = "Reproductor local"

    # ------------------------------------------------------------- playback
    def _select_index(self, index: int, *, focus_list: bool) -> None:
        if not (0 <= index < len(self.tracks)):
            return

        self.current_index = index
        track = self.tracks[index]

        self.query_one("#meta-title", Label).update(track.title)
        self.query_one("#meta-artist", Label).update(track.artist)
        self.query_one("#meta-album", Label).update(track.album)
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

        self._load_cover_async(track)

    def _play_index(self, index: int) -> None:
        if not (0 <= index < len(self.tracks)):
            return

        self._select_index(index, focus_list=True)
        track = self.tracks[index]

        try:
            self.player.play(track.path)
        except PlaybackError as exc:
            self._set_state_ui(PlaybackState.STOPPED)
            self.notify(str(exc), severity="error", timeout=7)
            return

        self.query_one("#time-elapsed", Label).update("0:00")
        self._set_state_ui(PlaybackState.PLAYING)

    def _set_state_ui(self, state: PlaybackState) -> None:
        state_label = self.query_one("#play-state", Label)
        progress = self.query_one("#progress-bar", ProgressBar)
        track_list = self.query_one("#track-list", TrackList)

        if state is PlaybackState.PLAYING:
            state_label.update("▶")
            progress.gradient = self._active_gradient
            track_list.set_playback_state(self.current_index, paused=False)
        elif state is PlaybackState.PAUSED:
            state_label.update("❚❚")
            progress.gradient = self._paused_gradient
            track_list.set_playback_state(self.current_index, paused=True)
        else:
            state_label.update("■")
            progress.gradient = self._active_gradient
            track_list.set_playback_state(None, paused=False)

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
        """Alterna entre fondo sólido y el fondo transparente del terminal."""
        self._transparent = not self._transparent
        if self._transparent:
            self.screen.add_class("transparent")
            self.query_one("#footer", Static).update(FOOTER_ON)
        else:
            self.screen.remove_class("transparent")
            self.query_one("#footer", Static).update(FOOTER)
        self.screen.refresh()

    def _update_volume_ui(self) -> None:
        label = self.query_one("#volume-label", Label)
        if self.player.muted:
            label.update("[#f0abfc]Mudo[/]")
        else:
            label.update(f"Vol {round(self.player.volume * 100)}%")

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        event.stop()
        self._play_index(event.option_index)

    def _tick(self) -> None:
        if self._closing or not self.tracks or self.current_index is None:
            return

        # En reposo o en pausa no hay nada que actualizar: evitamos repintar
        # la interfaz cada segundo (importante mientras se juega).
        if self.player.state is not PlaybackState.PLAYING:
            return

        track = self.tracks[self.current_index]

        if self.player.finished():
            self._play_index((self.current_index + 1) % len(self.tracks))
            return

        duration = track.duration
        position = self.player.position()
        if duration > 0:
            position = min(position, duration)
        else:
            position = 0.0

        # El total y su etiqueta ya se fijaron al seleccionar la pista; aquí
        # solo cambian el avance y el tiempo transcurrido.
        progress = self.query_one("#progress-bar", ProgressBar)
        progress.update(progress=position)
        self.query_one("#time-elapsed", Label).update(format_time(position))

    # -------------------------------------------------------------- artwork
    def _load_cover_async(self, track: Track) -> None:
        self._cover_token += 1
        token = self._cover_token

        def worker() -> None:
            try:
                artwork = load_cover(track)
            except Exception:
                artwork = create_placeholder(track)
            try:
                self.call_from_thread(self._apply_cover, token, artwork)
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
                self.call_from_thread(self._apply_cover, token, artwork)
            except RuntimeError:
                pass

        self.run_worker(
            worker,
            group="artwork",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _apply_cover(self, token: int, artwork: PILImage.Image) -> None:
        if self._closing or token != self._cover_token:
            return
        self.query_one("#cover-stage", CoverStage).set_artwork(artwork)
