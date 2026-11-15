#!/usr/bin/env bash
# Script simple para actualizar SYN
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Actualizando SYN desde GitHub..."
cd "$ROOT"
git pull

echo "==> Asegurando dependencias..."
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt" --quiet

echo "==> ¡Actualización completada!"
