# Restaurar SYN en Arch Linux + niri

Backup creado el **2026-11-21** desde Fedora 45.
Verificado con `SHA256SUMS` (245 MB en total).

## Contenido del backup

| Carpeta/archivo | Qué es |
| --- | --- |
| `syn/` | Código de SYN, sin `.venv` |
| `synget/` | Código de SYNGET (descargador), sin `.venv` |
| `syn.bundle` | Historial git completo (restaurar sin red) |
| `config/niri/` | Tu config de niri (incluye `dms/` y `syn.kdl`) |
| `config/kitty/` | `kitty.conf` con `background_opacity 0.75` |
| `config/syn/` | `config.toml` del usuario |
| `Musica/` | Biblioteca de música (182 MB) |
| `SHA256SUMS` | Checksums de todo lo anterior |

## 0. Verificar el backup antes de usarlo

```bash
cd /ruta/al/syn-backup-2026-11-21
sha256sum -c SHA256SUMS
```

Debe terminar todo en `OK`.

## 1. Paquetes en Arch

```bash
sudo pacman -S --needed git niri kitty xdg-desktop-portal-gtk \
  xwayland-satellite fuzzel mako swaybg
```

## 2. Código (elige una opción)

**a) Desde GitHub (recomendado, ya está todo subido):**

```bash
git clone https://github.com/h73212653-code/syn.git ~/syn
```

**b) Desde el backup, sin red:**

```bash
cp -r syn-backup-2026-11-21/syn ~/syn
# Si quieres conservar el historial git:
git clone syn-backup-2026-11-21/syn.bundle ~/syn
git -C ~/syn remote set-url origin https://github.com/h73212653-code/syn.git
```

## 3. Configuraciones

```bash
mkdir -p ~/.config
cp -r syn-backup-2026-11-21/config/niri  ~/.config/
cp -r syn-backup-2026-11-21/config/kitty ~/.config/
cp -r syn-backup-2026-11-21/config/syn   ~/.config/
```

## 4. Música

```bash
cp -r syn-backup-2026-11-21/Musica ~/
```

La config por defecto busca `~/Musica`, así que no hay que tocar nada.

## 5. Instalar SYN

```bash
cd ~/syn
./install-cachyos.sh   # crea .venv e instala dependencias
./setup-niri.sh        # regla syn.kdl, include y opacidad
niri validate          # debe salir sin errores
```

## 5b. Instalar SYNGET (descargador de música)

```bash
sudo pacman -S --needed ffmpeg
cp -r syn-backup-2026-11-21/synget ~/synget
cd ~/synget
./install.sh
```

Opcional, configuración propia en `~/.config/synget/config.toml` (hay una
plantilla en `config.example.toml` del repo).

## 6. Comprobar

```bash
syn-kitty
```

Atajo sugerido en `~/.config/niri/syn.kdl`:

```kdl
binds {
    Mod+T { spawn "syn-kitty"; }
}
```

## Notas importantes

- **No copies `.venv`**: los binarios de Python de Fedora no funcionan en Arch.
  `install-cachyos.sh` lo crea de cero.
- La opacidad de kitty se lee **al abrir la ventana**: cierra todas las de
  Kitty y vuelve a lanzar `syn-kitty`.
- El blur necesita **niri 26.04+** (`background-effect`). Arch ya lo trae.
- Si no quieres la barra DMS, los `include optional=true "dms/*.kdl"` se
  ignoran solos; niri arranca igual.
