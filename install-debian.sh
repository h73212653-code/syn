#!/usr/bin/env bash
# Instalador de SYN para Debian, Ubuntu y derivados (Linux Mint, Pop!_OS,
# Zorin, elementary, Kali, Raspberry Pi OS...). Usa apt.
#
#   ./install-debian.sh              instala todo (recomendado)
#   ./install-debian.sh --sin-kitty  no instala Kitty (ya usas otra terminal)
#   ./install-debian.sh --sin-apt    no toca paquetes del sistema
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CON_KITTY=1
CON_APT=1
for arg in "$@"; do
    case "$arg" in
        --sin-kitty) CON_KITTY=0 ;;
        --sin-apt)   CON_APT=0 ;;
        -h|--help)   sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Opción desconocida: $arg" >&2; exit 2 ;;
    esac
done

PYTHON_MIN="3.11"

msg()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m  ✗\033[0m %s\n' "$*" >&2; exit 1; }

echo "=========================================="
echo "   SYN - Instalador para Debian / Ubuntu"
echo "=========================================="
echo

# --------------------------------------------------------------- 0. Entorno
[[ "$(uname -s)" == "Linux" ]] || die "Este instalador es solo para Linux."

if [[ "$EUID" -eq 0 ]]; then
    SUDO=""
    warn "Ejecutando como root: los archivos quedarán a nombre de root."
    warn "Lo normal es ejecutarlo como tu usuario, sin sudo."
else
    command -v sudo >/dev/null 2>&1 || die "Falta 'sudo'. Instálalo o ejecuta como root."
    SUDO="sudo"
fi

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    msg "Sistema detectado: ${PRETTY_NAME:-desconocido}"
else
    warn "No se pudo leer /etc/os-release; continúo a ciegas."
fi

if [[ "$CON_APT" -eq 1 ]]; then
    command -v apt-get >/dev/null 2>&1 || die "No encuentro apt-get. ¿Seguro que es Debian/Ubuntu?"
fi

# ------------------------------------------------------ 1. Versión de Python
version_ok() {
    # Devuelve 0 si "$1" es >= PYTHON_MIN
    "$1" - "$PYTHON_MIN" <<'PY' 2>/dev/null
import sys
if sys.version_info < tuple(int(x) for x in sys.argv[1].split(".")):
    raise SystemExit(1)
PY
}

pick_python() {
    local candidate
    for candidate in python3.13 python3.12 python3.11 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && version_ok "$candidate"; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

msg "[1/6] Comprobando Python (mínimo $PYTHON_MIN)..."

if ! PY="$(pick_python)"; then
    ACTUAL="$(python3 -V 2>&1 || echo 'no instalado')"
    warn "Python encontrado: $ACTUAL (demasiado antiguo o ausente)."
    if [[ "$CON_APT" -eq 0 ]]; then
        die "Instala Python $PYTHON_MIN o superior y vuelve a ejecutar."
    fi
    msg "       Intentando instalar Python $PYTHON_MIN desde apt..."
    $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq || true
    for pkg in python3.13 python3.12 python3.11; do
        if $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$pkg" "$pkg-venv" 2>/dev/null; then
            break
        fi
    done
    PY="$(pick_python)" || {
        cat <<'AYUDA'

  Tu versión de Python es demasiado antigua para SYN.
  Opciones:
    · Ubuntu 22.04 y anteriores: añade el PPA de deadsnakes
        sudo add-apt-repository ppa:deadsnakes/ppa
        sudo apt update && sudo apt install python3.12 python3.12-venv
    · Debian 11 y anteriores: actualiza a Debian 12 o superior
    · O instala Python 3.11+ con pyenv

AYUDA
        die "No hay ningún Python $PYTHON_MIN disponible."
    }
fi
msg "       Usando $("$PY" -V 2>&1)  ($(command -v "$PY"))"

# ------------------------------------------------- 2. Paquetes del sistema
if [[ "$CON_APT" -eq 1 ]]; then
    msg "[2/6] Instalando paquetes del sistema..."

    # Imprescindibles: si falta uno, no seguimos.
    BASE=(python3-venv python3-pip git ca-certificates)
    [[ "$PY" != "python3" ]] && BASE+=("$PY" "$PY-venv")

    $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq
    if ! $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${BASE[@]}"; then
        die "No se pudieron instalar los paquetes base: ${BASE[*]}"
    fi

    # Opcionales: si un nombre no existe en esta versión, seguimos igual.
    opcional() {
        local pkg="$1"
        if $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$pkg" >/dev/null 2>&1; then
            echo "       ✔ $pkg"
            return 0
        fi
        warn "$pkg no está disponible en este sistema (se omite)."
        return 1
    }

    # Sonido. PipeWire es el estándar en Debian 12+ / Ubuntu 23.04+.
    if [[ "$CON_KITTY" -eq 1 ]]; then
        opcional kitty
    fi
    if command -v pactl >/dev/null 2>&1; then
        if pactl info 2>/dev/null | grep -qi "pipewire"; then
            opcional pipewire-audio-client-libraries
        fi
    else
        # Sin cliente de audio instalado: dejamos ALSA y PipeWire listos.
        opcional pipewire-audio-client-libraries
        opcional libasound2t64 || opcional libasound2 || true
    fi
else
    msg "[2/6] Omitiendo paquetes del sistema (--sin-apt)."
fi

# ------------------------------------------------ 3. Entorno virtual y SYN
msg "[3/6] Creando el entorno virtual e instalando SYN..."

if [[ -d "$ROOT/.venv" ]]; then
    VENV_PY="$ROOT/.venv/bin/python"
    if [[ -x "$VENV_PY" ]] && ! version_ok "$VENV_PY"; then
        warn "El .venv existente usa una versión vieja de Python; lo recreo."
        rm -rf "$ROOT/.venv"
    fi
fi

if [[ ! -d "$ROOT/.venv" ]]; then
    "$PY" -m venv "$ROOT/.venv" || die "No se pudo crear el entorno virtual (¿falta ${PY}-venv?)."
fi

VENV_PY="$ROOT/.venv/bin/python"
"$VENV_PY" -m pip install --upgrade pip --quiet

if ! "$VENV_PY" -m pip install -r "$ROOT/requirements.txt" --quiet; then
    warn "La instalación falló. Puede que falten bibliotecas para compilar."
    warn "Instalando dependencias de compilación y reintentando..."
    if [[ "$CON_APT" -eq 1 ]]; then
        $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            build-essential python3-dev libsdl2-dev libsdl2-image-dev \
            libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev \
            >/dev/null 2>&1 || true
        "$VENV_PY" -m pip install -r "$ROOT/requirements.txt" \
            || die "No se pudo instalar las dependencias de Python."
    else
        die "No se pudo instalar las dependencias de Python."
    fi
fi

# --------------------------------------------------------- 4. Lanzadores
msg "[4/6] Creando los comandos 'syn' y 'syn-kitty'..."
mkdir -p "$HOME/.local/bin"
chmod +x "$ROOT/bin/syn" "$ROOT/bin/syn-kitty"
ln -sfn "$ROOT/bin/syn" "$HOME/.local/bin/syn"
ln -sfn "$ROOT/bin/syn-kitty" "$HOME/.local/bin/syn-kitty"

case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *)
        for rcfile in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
            if [[ -f "$rcfile" ]] && ! grep -q '\.local/bin' "$rcfile"; then
                printf '\n# SYN\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rcfile"
                warn "Añadido ~/.local/bin al PATH en $(basename "$rcfile")."
            fi
        done
        warn "Abre una terminal nueva (o ejecuta: source ~/.bashrc)."
        ;;
esac

# ------------------------------------------------------------ 5. Kitty
msg "[5/6] Configurando Kitty..."
if [[ "$CON_KITTY" -eq 1 ]]; then
    KITTY_CONF="$HOME/.config/kitty/kitty.conf"
    mkdir -p "$(dirname "$KITTY_CONF")"
    if ! grep -qE '^[[:space:]]*background_opacity' "$KITTY_CONF" 2>/dev/null; then
        printf '\n# SYN: transparencia para el modo "t"\nbackground_opacity 0.7\n' >> "$KITTY_CONF"
        echo "       ✔ background_opacity 0.7 en kitty.conf"
    else
        echo "       ✔ Kitty ya tenía opacidad configurada"
    fi
    if ! command -v kitty >/dev/null 2>&1; then
        warn "Kitty no está instalado; 'syn-kitty' no funcionará hasta que lo instales."
    fi
else
    echo "       Omitido (--sin-kitty)."
fi

# -------------------------------------------------------- 6. Icono y acceso directo
msg "[6/6] Creando el acceso directo del menú..."
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
Type=Application
Name=SYN Reproductor
GenericName=Reproductor de música
Comment=Reproductor de música local en la terminal
Exec=$HOME/.local/bin/syn-kitty
Icon=syn
Terminal=false
Categories=AudioVideo;Audio;Music;Player;
Keywords=musica;music;reproductor;player;tui;
StartupWMClass=syn
EOF
command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
echo "       ✔ $DESKTOP_DIR/syn.desktop"

# ------------------------------------------------------------ Verificación
echo
msg "Verificando la instalación..."
OUTPUT="$("$ROOT/bin/syn" --version 2>&1 || true)"
VERSION_LINE=""
while IFS= read -r line; do
    case "$line" in
        SYN\ [0-9]*) VERSION_LINE="$line"; break ;;
    esac
done <<< "$OUTPUT"

if [[ -z "$VERSION_LINE" ]]; then
    printf '%s\n' "$OUTPUT" | sed 's/^/     /'
    die "SYN no arranca. Revisa los mensajes de arriba."
fi

echo
echo "=========================================="
echo "   ✓ INSTALACIÓN COMPLETADA"
echo "=========================================="
echo "   $VERSION_LINE"
echo
echo "   syn          → en la terminal actual"
echo "   syn-kitty    → en ventana propia con carátulas"
echo
if [[ ! -d "$HOME/Musica" && ! -d "$HOME/Música" && ! -d "$HOME/Music" ]]; then
    warn "No encontré ~/Musica. Créala y copia ahí tus canciones,"
    warn "o cambia 'music_dir' en $ROOT/config.toml"
fi
echo
