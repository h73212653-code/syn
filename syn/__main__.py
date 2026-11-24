"""Punto de entrada de SYN."""

from __future__ import annotations

import sys
from typing import Sequence

from .app import SynApp
from .config import load_config


def main(argv: Sequence[str] | None = None) -> None:
    config = load_config(argv)
    # textual-image debe sondear la terminal antes de que Textual tome stdin.
    # En Gaming Mode o con --no-covers ni siquiera se importa.
    if config.covers and not config.game_mode:
        from .terminal import prime_terminal_probe

        prime_terminal_probe()
    app = SynApp(config)
    try:
        app.run()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
