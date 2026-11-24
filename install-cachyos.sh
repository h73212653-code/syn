#!/usr/bin/env bash
# Instalador de SYN para CachyOS (y cualquier distro con pacman).
# Instala dependencias del sistema, crea el venv y deja los comandos
# `syn` y `syn-kitty` listos para usar.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "=========================================="
echo "   SYN - Instalador para CachyOS/Arch"
echo "=========================================="

# ------------------------------------------------------------------ 0. Requisitos
if ! command -v pacman >/dev/null 2>&1; then
    echo "Error: este script requiere pacman (CachyOS / Arch)." >&2
    exit 1
fi

if [[ "$EUID" -eq 0 ]]; then
    echo "Error: no ejecutes este script como root. Usa tu usuario normal." >&2
    exit 1
fi

# ------------------------------------------------------------------ 1. Paquetes del sistema
echo "==> [1/6] Instalando paquetes del sistema..."
sudo pacman -S --needed --noconfirm \
    kitty \
    python \
    python-pip \
    pipewire \
    pipewire-pulse \
    git \
    libpulse \
    ffmpeg \
    base-devel

# ------------------------------------------------------------------ 2. Entorno virtual
echo "==> [2/6] Configurando entorno de Python..."
if [[ ! -d "$ROOT/.venv" ]]; then
    echo "    Creando .venv..."
    python -m venv "$ROOT/.venv"
fi

echo "    Actualizando pip e instalando dependencias..."
"$ROOT/.venv/bin/python" -m pip install --upgrade pip --quiet
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"

# ------------------------------------------------------------------ 3. Comandos syn / syn-kitty
echo "==> [3/6] Creando lanzadores en ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
# Aseguramos que los scripts en bin/ sean ejecutables
chmod +x "$ROOT/bin/syn" "$ROOT/bin/syn-kitty"
ln -sfn "$ROOT/bin/syn" "$HOME/.local/bin/syn"
ln -sfn "$ROOT/bin/syn-kitty" "$HOME/.local/bin/syn-kitty"

# ------------------------------------------------------------------ 4. PATH (Bash y Zsh)
echo "==> [4/6] Verificando PATH..."
added_to_path=0
for rcfile in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [[ -f "$rcfile" ]]; then
        if ! grep -q "\.local/bin" "$rcfile"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rcfile"
            echo "    Añadido PATH a $rcfile"
            added_to_path=1
        fi
    fi
done

# ------------------------------------------------------------------ 5. Kitty: transparencia
echo "==> [5/6] Configurando Kitty..."
KITTY_CONF="$HOME/.config/kitty/kitty.conf"
mkdir -p "$(dirname "$KITTY_CONF")"
if [[ ! -f "$KITTY_CONF" ]]; then
    touch "$KITTY_CONF"
fi

if ! grep -qE '^background_opacity' "$KITTY_CONF"; then
    echo "" >> "$KITTY_CONF"
    echo "# SYN: fondo transparente" >> "$KITTY_CONF"
    echo "background_opacity 0.7" >> "$KITTY_CONF"
    echo "background_blur 10" >> "$KITTY_CONF"
    echo "    Transparencia activada en kitty.conf"
fi

# ------------------------------------------------------------------ 6. Icono y .desktop
echo "==> [6/6] Creando acceso directo en el menú..."
ICON_DIR="$HOME/.local/share/icons/hicolor"
mkdir -p "$ICON_DIR/scalable/apps"
cp "$ROOT/assets/icon-syn.svg" "$ICON_DIR/scalable/apps/syn.svg"
for size in 16 24 32 48 64 128 256 512; do
    mkdir -p "$ICON_DIR/${size}x${size}/apps"
    cp "$ROOT/assets/icons/hicolor/${size}x${size}/apps/syn.png" \
       "$ICON_DIR/${size}x${size}/apps/syn.png"
done
command -v gtk-update-icon-cache >/dev/null 2>&1 \
    && gtk-update-icon-cache -f -t "$ICON_DIR" >/dev/null 2>&1 || true

DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/syn.desktop" <<EOF
[Desktop Entry]
Name=SYN Reproductor
Comment=Reproductor local TUI
Exec=$HOME/.local/bin/syn-kitty
Icon=syn
Terminal=false
Type=Application
Categories=Audio;Music;Player;
StartupWMClass=syn
EOF

echo "=========================================="
echo "   ✓ INSTALACIÓN COMPLETADA"
echo "=========================================="
echo ""
echo "  1. Recarga tu terminal:  source ~/.bashrc  (o abre una nueva)"
echo "  2. Lanza el reproductor: syn"
echo "     o en ventana nueva:   syn-kitty"
echo ""
if (( added_to_path )); then
    echo "  ¡IMPORTANTE!: Se ha actualizado tu PATH. Reinicia la terminal."
fi
echo "=========================================="
