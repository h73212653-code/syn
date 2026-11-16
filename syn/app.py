"""Aplicación Textual de SYN."""

from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from rich.markup import escape
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Gradient
from textual.containers import Container, Horizontal
from textual.widgets import Label, OptionList, ProgressBar, Static

from .artwork import create_placeholder, load_cover
from .config import Config
from .theme import ThemeManager
from .library import Section, Track, scan_sections
from .player import PlaybackError, PlaybackState, Player
from .widgets import CoverStage, TrackList, build_logo

FOOTER = (
    "[b #67e8f9]Espacio[/] [#94a3b8]pausa[/]  "
    "[b #f0abfc]Enter[/] [#94a3b8]reproducir[/]  "
    "[b #67e8f9]n/p[/] [#94a3b8]cambiar[/]  "
    "[b #f0abfc]←/→[/] [#94a3b8]carpeta[/]  "
    "[b #67e8f9]y/u[/] [#94a3b8]volumen[/]  "
    "[b #f0abfc]m[/] [#94a3b8]mudo[/]  "
    "[b #f0abfc]t[/] [#94a3b8]fondo[/]  "
    "[b #f0abfc]l[/] [#94a3b8]letras[/]  "
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
        self._cover_token = 0
        self._closing = False
        self._transparent = False
        self._lyrics_visible = False
        self._lyrics_token = 0
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
        self.player.shutdown()

    def on_key(self, event: events.Key) -> None:
        if event.key == "q":
            self.exit()

    async def action_quit(self) -> None:
        self._closing = True
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

        self._load_cover_async(track)

        if self._lyrics_visible:
            self._load_lyrics_async(track)

    def _play_index(self, index: int) -> None:
        if not (0 <= index < len(self.tracks)):
            return

        self._select_index(index, focus_list=True)
        self._start_playback(self.tracks[index], self.section_index)

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
        """Índice de la pista sonando dentro de la carpeta visible, si está."""
        if self.playing_track is None or self.playing_section != self.section_index:
            return None
        for index, track in enumerate(self.tracks):
            if track is self.playing_track:
                return index
        return None

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

        if self.current_index is None or not self.tracks:
            lyrics_panel.update("Selecciona una canción para ver su letra.")
            return

        track = self.tracks[self.current_index]
        self._load_lyrics_async(track)

    def _load_lyrics_async(self, track: Track) -> None:
        """Busca la letra en segundo plano para no bloquear la interfaz."""
        self._lyrics_token += 1
        token = self._lyrics_token

        if self._lyrics_visible:
            self.query_one("#lyrics-panel", Static).update(
                f"Buscando letra de\n{escape(track.title)}…"
            )

        def worker() -> None:
            from .lyrics import fetch_lyrics

            try:
                lyrics = fetch_lyrics(track.artist, track.title)
            except Exception:
                lyrics = None
            try:
                self.call_from_thread(self._apply_lyrics, token, track, lyrics)
            except RuntimeError:
                pass

        self.run_worker(
            worker,
            group="lyrics",
            exclusive=True,
            thread=True,
            exit_on_error=False,
        )

    def _apply_lyrics(
        self, token: int, track: Track, lyrics: str | None
    ) -> None:
        if self._closing or token != self._lyrics_token:
            return
        if not self._lyrics_visible:
            return

        panel = self.query_one("#lyrics-panel", Static)
        if lyrics:
            # Text() evita que Rich interprete corchetes de la propia letra.
            panel.update(Text(lyrics))
        else:
            panel.update(
                "[#64748b]No hay letra disponible para[/]\n"
                f"[b]{escape(track.title)}[/]\n"
                f"[#94a3b8]{escape(track.artist)}[/]"
            )

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
        if self.playing_section == self.section_index:
            self._select_index(next_index, focus_list=False)
        self._start_playback(tracks[next_index], self.playing_section)

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
