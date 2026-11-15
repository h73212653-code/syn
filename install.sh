#!/usr/bin/env bash
# Instalador universal de SYN (Arch/Debian/Fedora).
# Instala dependencias, venv, y prepara los lanzadores.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "=========================================="
echo "   SYN - Instalador Universal"
echo "=========================================="

# 1. Detectar gestor de paquetes
if command -v pacman >/dev/null 2>&1; then
    echo "==> Detectado Arch/CachyOS (pacman)"
    sudo pacman -S --needed --noconfirm kitty python python-pip pipewire pipewire-pulse git base-devel
elif command -v apt-get >/dev/null 2>&1; then
    echo "==> Detectado Debian/Ubuntu (apt)"
    sudo apt-get update
    sudo apt-get install -y kitty python3 python3-pip python3-venv pipewire-audio-client-libraries git build-essential
else
    echo "!! No se detectó un gestor de paquetes conocido (pacman/apt)."
    echo "!! Asegúrate de tener instalados: kitty, python3, pip, y pipewire."
fi

# 2. Entorno virtual
echo "==> [2/6] Configurando entorno de Python..."
if [[ ! -d "$ROOT/.venv" ]]; then
    python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/python" -m pip install --upgrade pip --quiet
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"

# 3. Lanzadores
echo "==> [3/6] Creando lanzadores en ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
chmod +x "$ROOT/bin/syn" "$ROOT/bin/syn-kitty"
ln -sfn "$ROOT/bin/syn" "$HOME/.local/bin/syn"
ln -sfn "$ROOT/bin/syn-kitty" "$HOME/.local/bin/syn-kitty"

# 4. PATH
for rcfile in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [[ -f "$rcfile" ]] && ! grep -q "\.local/bin" "$rcfile"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rcfile"
    fi
done

# 5. Kitty
KITTY_CONF="$HOME/.config/kitty/kitty.conf"
mkdir -p "$(dirname "$KITTY_CONF")"
if ! grep -qE '^background_opacity' "$KITTY_CONF" 2>/dev/null; then
    echo -e "\n# SYN: transparencia\nbackground_opacity 0.7" >> "$KITTY_CONF"
fi

# 6. .desktop
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/syn.desktop" <<EOF
[Desktop Entry]
Name=SYN Reproductor
Exec=$HOME/.local/bin/syn-kitty
Icon=multimedia-audio-player
Terminal=false
Type=Application
Categories=Audio;Music;
EOF

echo "=========================================="
echo "   ✓ INSTALACIÓN FINALIZADA"
echo "=========================================="
echo "  Ejecuta: source ~/.bashrc (y luego 'syn')"
