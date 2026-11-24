"""Logo ASCII de SYN.

Solo depende de pyfiglet y Rich. Se importa de forma perezosa para que el
Gaming Mode no renderice ni cargue fuentes decorativas.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from pyfiglet import Figlet
from rich.text import Text

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
