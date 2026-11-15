"""Widgets propios de SYN."""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from PIL import Image as PILImage
from pyfiglet import Figlet
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual_image.widget import Image as TerminalImage

try:  # API interna, pero estable y necesaria para ajustar la proporción.
    from textual_image._terminal import get_cell_size
except ImportError:  # pragma: no cover - fallback defensivo
    def get_cell_size() -> tuple[int, int]:  # type: ignore[misc]
        return 10, 20

from .library import Track, UNKNOWN_ARTIST


class CoverStage(Container):
    """Zona donde la carátula se ajusta a un cuadrado real en píxeles.

    Los caracteres de terminal son más altos que anchos. Si dejáramos que
    ``textual-image`` usara todo el contenedor, la portada se deformaría.
    Calculamos celdas de ancho/alto para que el área de dibujo sea cuadrada.
    """

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self._cover = TerminalImage(None, id="cover-image")
        self._last_size: tuple[int, int] | None = None

    def compose(self) -> ComposeResult:
        yield self._cover

    def on_mount(self) -> None:
        self.call_after_refresh(self._fit_cover)

    def on_resize(self, event: events.Resize) -> None:
        self.call_after_refresh(self._fit_cover)

    def set_artwork(self, artwork: PILImage.Image) -> None:
        self._cover.image = artwork
        self.call_after_refresh(self._fit_cover)

    def clear_artwork(self) -> None:
        self._cover.image = None

    def _fit_cover(self) -> None:
        available_width, available_height = self.content_size
        if available_width <= 0 or available_height <= 0:
            return

        cell_width, cell_height = get_cell_size()
        if cell_width <= 0 or cell_height <= 0:
            return

        # Cuadrado en píxeles: w * cell_width == h * cell_height.
        height = min(
            available_height,
            max(1, int(available_width * cell_width / cell_height)),
        )
        width = max(1, int(height * cell_height / cell_width))
        if width > available_width:
            width = available_width
            height = max(1, int(width * cell_width / cell_height))

        new_size = (width, height)
        if new_size == self._last_size:
            return
        self._last_size = new_size
        self._cover.styles.width = width
        self._cover.styles.height = height


class TrackList(OptionList):
    """Lista de pistas con navegación por flechas, j/k y Enter."""

    BINDINGS = [
        Binding("j", "cursor_down", "Abajo", show=False),
        Binding("k", "cursor_up", "Arriba", show=False),
    ]

    def __init__(self, id: str | None = None) -> None:
        super().__init__(compact=True, id=id)
        self._tracks: list[Track] = []
        self._playing_index: int | None = None
        self._paused = False

    @property
    def tracks(self) -> Sequence[Track]:
        return tuple(self._tracks)

    def set_tracks(self, tracks: Sequence[Track]) -> None:
        self._tracks = list(tracks)
        self._playing_index = None
        options = [
            Option(self._prompt(index, track), id=f"track-{index}")
            for index, track in enumerate(self._tracks)
        ]
        self.set_options(options)
        self.highlighted = 0 if options else None

    def set_playback_state(self, index: int | None, paused: bool = False) -> None:
        old_index = self._playing_index
        self._playing_index = index
        self._paused = paused
        for changed_index in {old_index, index}:
            if changed_index is not None and 0 <= changed_index < len(self._tracks):
                self.replace_option_prompt_at_index(
                    changed_index,
                    self._prompt(changed_index, self._tracks[changed_index]),
                )

    def focus_index(self, index: int) -> None:
        if 0 <= index < len(self._tracks):
            self.highlighted = index
            self.scroll_to_highlight()

    def on_resize(self, event: events.Resize) -> None:
        if self._tracks:
            self.call_after_refresh(self._refresh_prompts)

    def _refresh_prompts(self) -> None:
        for index in range(min(len(self._tracks), self.option_count)):
            self.replace_option_prompt_at_index(
                index,
                self._prompt(index, self._tracks[index]),
            )

    def _available_prompt_width(self) -> int:
        width = self.scrollable_content_region.width or self.content_size.width
        # El componente option-list--option tiene 1 celda de padding a cada lado.
        return max(12, width - 2)

    def _prompt(self, index: int, track: Track) -> Text:
        playing = index == self._playing_index
        if playing:
            marker = "‖" if self._paused else "▶"
            marker_style = "bold #f0abfc" if self._paused else "bold #67e8f9"
        else:
            marker = " "
            marker_style = ""

        prompt = Text(
            no_wrap=True,
            overflow="ellipsis",
            end="…",
        )
        prompt.append(f"{marker} ", style=marker_style)
        prompt.append(f"{index + 1:02d}  ", style="#475569")
        prompt.append(
            track.title,
            style="bold #a5f3fc" if playing else "bold #e2e8f0",
        )
        if track.artist and track.artist != UNKNOWN_ARTIST:
            prompt.append("  ·  ", style="#334155")
            prompt.append(track.artist, style="#7f8da3")

        # Textual visualiza los prompts con wrapping. Truncamos aquí para que
        # cada canción ocupe exactamente una línea (y no coma filas vecinas).
        prompt.truncate(self._available_prompt_width(), overflow="ellipsis")
        return prompt


# De mayor a menor: se elige el primero que quepa en el panel derecho.
_LOGO_FONTS = (
    "blocks",
    "patorjk-hex",
    "electronic",
    "banner3-D",
    "ansi_shadow",
    "small",
)

_FALLBACK_LOGO = (
    "███████╗██╗   ██╗███╗   ██╗",
    "██╔════╝╚██╗ ██╔╝████╗  ██║",
    "███████╗ ╚████╔╝ ██╔██╗ ██║",
    "╚════██║  ╚██╔╝  ██║╚██╗██║",
    "███████║   ██║   ██║ ╚████║",
    "╚══════╝   ╚═╝   ╚═╝  ╚═══╝",
)


@lru_cache(maxsize=None)
def _render_logo(font: str) -> tuple[str, ...]:
    """Renderiza SYN con una fuente y quita filas vacías sobrantes."""
    try:
        rendered = Figlet(font=font).renderText("SYN")
    except Exception:
        return _FALLBACK_LOGO
    lines = [line.rstrip() for line in rendered.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return tuple(lines) or _FALLBACK_LOGO


def _logo_width(lines: Sequence[str]) -> int:
    return max((len(line) for line in lines), default=0)


def build_logo(
    max_width: int | None = None,
    max_height: int | None = None,
) -> Text:
    """Logo SYN grande, adaptado al espacio disponible del panel derecho.

    En una ventana de 80×24 usa una fuente de 39×10; en ventanas más
    grandes sube a 54×10 o 60×11 para que el logo no se vea pequeño.
    """
    variants = [_render_logo(font) for font in _LOGO_FONTS]
    lines = variants[2]  # electronic: tamaño seguro por defecto

    if max_width is not None or max_height is not None:
        for candidate in variants:
            too_wide = max_width is not None and _logo_width(candidate) > max_width
            too_tall = max_height is not None and len(candidate) > max_height
            if not too_wide and not too_tall:
                lines = candidate
                break

    colors = [
        "#67e8f9",
        "#7dd3fc",
        "#93c5fd",
        "#a5b4fc",
        "#a78bfa",
        "#c084fc",
        "#e879f9",
    ]
    logo = Text(justify="center")
    for index, line in enumerate(lines):
        logo.append(
            line,
            style=f"bold {colors[min(index, len(colors) - 1)]}",
        )
        if index < len(lines) - 1:
            logo.append("\n")
    return logo
