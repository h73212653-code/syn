"""Widget de carátula: único punto que importa Pillow y textual-image.

Se importa de forma perezosa desde ``app.py`` para que el Gaming Mode y el
modo ``--no-covers`` no carguen estas dependencias.
"""

from __future__ import annotations

from PIL import Image as PILImage
from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual_image.widget import Image as TerminalImage

try:  # API interna, pero estable y necesaria para ajustar la proporción.
    from textual_image._terminal import get_cell_size
except ImportError:  # pragma: no cover - fallback defensivo
    def get_cell_size() -> tuple[int, int]:  # type: ignore[misc]
        return 10, 20


def _safe_cell_size() -> tuple[int, int]:
    """Tamaño de celda a prueba de terminales que no responden."""
    try:
        width, height = get_cell_size()
    except Exception:
        return 10, 20
    if width <= 0 or height <= 0:
        return 10, 20
    return width, height


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

        cell_width, cell_height = _safe_cell_size()
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
