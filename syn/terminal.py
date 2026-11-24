"""Sondeo temprano de la terminal que necesita textual-image.

``textual_image`` documenta que el sondeo (TGP, Sixel y tamaño de celda) tiene
que ejecutarse **antes** de que Textual tome el control de stdin. Si se hace
dentro de la aplicación, las respuestas de la terminal se pierden: la carátula
cae al renderizador de bloques y, si la terminal todavía no tiene tamaño, el
sondeo revienta con ``ZeroDivisionError``.

Este módulo se importa solo cuando las carátulas están activas, así que el
Gaming Mode sigue sin cargar nada de imágenes.
"""

from __future__ import annotations

import logging
import os
import sys
import time

# Tamaño de celda razonable si la terminal no responde (VT340).
_FALLBACK_CELL = (10, 20)


def _terminal_columns() -> int:
    """Columnas de la terminal, esperando un instante si aún no hay tamaño."""
    for _ in range(10):
        try:
            size = os.get_terminal_size(sys.__stdout__.fileno())
        except (OSError, ValueError, AttributeError):
            return 0
        if size.columns > 0 and size.lines > 0:
            return size.columns
        time.sleep(0.02)
    return 0


def _safe_capabilities(module):
    """Capacidades de reserva: dibujo por bloques, nunca por gráficos."""
    return module.TerminalCapabilities(
        cell_size=module.CellSize(*_FALLBACK_CELL),
        sixel=False,
        # En una ventana de Kitty el protocolo de gráficos existe aunque el
        # sondeo no haya podido confirmarlo.
        tgp=bool(os.environ.get("KITTY_WINDOW_ID")),
    )


def prime_terminal_probe() -> None:
    """Rellena la caché de textual-image antes de que arranque Textual."""
    try:
        from textual_image import _terminal
    except Exception:  # pragma: no cover - dependencia opcional
        return

    probe = _terminal.probe_terminal
    if hasattr(probe, "_result"):
        return

    if _terminal_columns() <= 0:
        # Ventana recién creada o pty sin tamaño: sembramos un resultado
        # seguro para que textual-image no divida por cero.
        probe._result = _safe_capabilities(_terminal)
        return

    # Si la terminal no responde, textual-image registra un aviso con traza
    # completa. Es inofensivo (cae a dibujo por bloques) pero ensucia la
    # pantalla justo antes de abrir SYN, así que lo silenciamos.
    logger = logging.getLogger("textual_image")
    previous_propagate = logger.propagate
    logger.propagate = False
    logger.addHandler(logging.NullHandler())
    try:
        probe()
    except Exception:  # pragma: no cover - terminal exótica
        probe._result = _safe_capabilities(_terminal)
    finally:
        logger.propagate = previous_propagate

