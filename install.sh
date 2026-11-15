#!/usr/bin/env bash
# Instala SYN en un entorno virtual local y crea el comando ~/.local/bin/syn.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: no encuentro python3." >&2
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    echo "Error: SYN necesita Python 3.11 o superior." >&2
    python3 --version >&2
    exit 1
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    echo "→ Creando entorno virtual en .venv"
    python3 -m venv "$ROOT/.venv"
fi

echo "→ Actualizando pip"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip

echo "→ Instalando dependencias"
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"

mkdir -p "$HOME/.local/bin"
ln -sfn "$ROOT/bin/syn" "$HOME/.local/bin/syn"
ln -sfn "$ROOT/bin/syn-kitty" "$HOME/.local/bin/syn-kitty"

echo
echo "✓ SYN instalado."
echo "  Comando:  syn"
echo "  En Kitty: syn-kitty   (abre una ventana nueva)"
echo "  Música:   $ROOT/config.toml"
echo
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo "Aviso: añade ~/.local/bin a tu PATH para usar «syn»." ;;
esac
