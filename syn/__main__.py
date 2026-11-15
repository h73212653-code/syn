"""Punto de entrada de SYN."""

from __future__ import annotations

import sys
from typing import Sequence

from .app import SynApp
from .config import load_config


def main(argv: Sequence[str] | None = None) -> None:
    config = load_config(argv)
    app = SynApp(config)
    try:
        app.run()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
