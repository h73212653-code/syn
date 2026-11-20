#!/usr/bin/env bash
# Integración de SYN con niri (Wayland) + transparencia con blur en Kitty.
# Es idempotente: puedes ejecutarlo tantas veces como quieras.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
NIRI_DIR="$HOME/.config/niri"
NIRI_CONF="$NIRI_DIR/config.kdl"
SYN_RULE="$NIRI_DIR/syn.kdl"
KITTY_CONF="$HOME/.config/kitty/kitty.conf"

echo "=========================================="
echo "   SYN - Integración con niri"
echo "=========================================="

# 1. Regla de ventana
mkdir -p "$NIRI_DIR"
install -m 0644 "$ROOT/niri/syn.kdl" "$SYN_RULE"
echo "==> Regla instalada en $SYN_RULE"

# 2. Incluirla desde config.kdl (solo si aún no está)
if [[ -f "$NIRI_CONF" ]]; then
    if grep -qE '^[[:space:]]*include[^#]*"syn\.kdl"' "$NIRI_CONF"; then
        echo "==> config.kdl ya incluye syn.kdl"
    else
        printf '\n// SYN\ninclude optional=true "syn.kdl"\n' >> "$NIRI_CONF"
        echo "==> Añadido include de syn.kdl a config.kdl"
    fi
else
    echo "!! No existe $NIRI_CONF; añade manualmente:"
    echo '   include optional=true "syn.kdl"'
fi

# 3. Opacidad de Kitty
mkdir -p "$(dirname "$KITTY_CONF")"
touch "$KITTY_CONF"
if grep -qE '^[[:space:]]*background_opacity' "$KITTY_CONF"; then
    # Si está a 1.0 (opaco), bájalo a 0.75.
    sed -i -E 's/^([[:space:]]*)background_opacity[[:space:]]+1(\.0+)?[[:space:]]*$/\1background_opacity 0.75/' "$KITTY_CONF"
    echo "==> background_opacity revisado en kitty.conf"
else
    printf '\n# SYN: transparencia (el blur lo pone niri)\nbackground_opacity 0.75\n' >> "$KITTY_CONF"
    echo "==> Añadido background_opacity 0.75 a kitty.conf"
fi

# 4. Validar
if command -v niri >/dev/null 2>&1; then
    if niri validate -c "$NIRI_CONF" >/dev/null 2>&1; then
        echo "==> Configuración de niri válida"
    else
        echo "!! niri validate ha fallado; revisa $NIRI_CONF"
        niri validate -c "$NIRI_CONF" || true
    fi
fi

cat <<'EOF'

Hecho. Para verlo:
  1. Cierra TODAS las ventanas de Kitty (la opacidad se lee al arrancar).
  2. niri recarga la config solo; si no, Mod+Shift+R o reinicia la sesión.
  3. Lanza: syn-kitty

Si no ves blur, comprueba que tu niri es >= 26.04 (`niri --version`),
que es cuando llegó window-rule background-effect.
EOF
