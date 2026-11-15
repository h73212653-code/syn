#!/usr/bin/env bash
# Instalador de SYN para CachyOS (y cualquier distro con pacman).
# Instala dependencias del sistema, crea el venv y deja los comandos
# `syn` y `syn-kitty` listos para usar.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> Instalador de SYN para CachyOS"

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
echo "==> Instalando paquetes del sistema con pacman..."
sudo pacman -S --needed --noconfirm \
    kitty \
    python \
    python-pip \
    pipewire \
    pipewire-pulseaudio

# ------------------------------------------------------------------ 2. Entorno virtual
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    echo "==> Creando entorno virtual en .venv"
    python -m venv "$ROOT/.venv"
fi

echo "==> Actualizando pip"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip --quiet

echo "==> Instalando dependencias de Python"
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt" --quiet

# ------------------------------------------------------------------ 3. Comandos syn / syn-kitty
mkdir -p "$HOME/.local/bin"
ln -sfn "$ROOT/bin/syn" "$HOME/.local/bin/syn"
ln -sfn "$ROOT/bin/syn-kitty" "$HOME/.local/bin/syn-kitty"

# ------------------------------------------------------------------ 4. PATH
if ! grep -q "$HOME/.local/bin" "$HOME/.bashrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo "==> Añadido ~/.local/bin al PATH en ~/.bashrc"
fi

# ------------------------------------------------------------------ 5. Kitty: transparencia (opcional pero recomendada)
KITTY_CONF="$HOME/.config/kitty/kitty.conf"
mkdir -p "$(dirname "$KITTY_CONF")"

if ! grep -qE '^background_opacity' "$KITTY_CONF" 2>/dev/null; then
    {
        echo ""
        echo "# SYN: fondo transparente para ver el escritorio detrás del reproductor"
        echo "background_opacity 0.5"
        echo "background_blur 10"
    } >> "$KITTY_CONF"
    echo "==> Configurada transparencia en kitty.conf"
else
    echo "==> kitty.conf ya tiene background_opacity (déjalo así para el modo transparente)"
fi

# ------------------------------------------------------------------ 6. .desktop para menú de aplicaciones (opcional)
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/syn.desktop" <<EOF
[Desktop Entry]
Name=SYN Reproductor de Música
Comment=Reproductor de música local para terminal (Kitty)
Exec=kitty --class syn --title SYN --directory $ROOT $ROOT/bin/syn
Icon=media-player-audio
Terminal=true
Type=Application
Categories=Audio;AudioVideo;Player;
EOF

echo ""
echo "✓ SYN instalado."
echo ""
echo "  Comando:      syn          (abre en la terminal actual)"
echo "  Kitty nueva:  syn-kitty    (abre una ventana de Kitty dedicada)"
echo "  Música:       edita $ROOT/config.toml si tu carpeta no es ~/Musica"
echo ""
echo "  Para el modo transparente pulsa la tecla 't' dentro de la app."
echo ""
echo "  Si ~/.local/bin no está en tu PATH, cierra y abre la terminal o ejecuta:"
echo "    source ~/.bashrc"
