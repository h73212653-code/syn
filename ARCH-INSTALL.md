# Instalar Arch con niri + DMS (archinstall)

Guía para este equipo: NVMe de 476 GB como sistema, HDD de 1 TB como datos.
El USB Ventoy tiene el ISO de Arch **y** el backup de SYN: **no lo formatees**.

**Ruta recomendada:** instalar Arch **sin entorno gráfico** (perfil Minimal) y
después instalar niri + DMS a mano. Así solo entra lo que usas y se evitan los
errores del perfil de escritorio.

## Antes de empezar

- Backup verificado en el USB (`syn-backup-2026-11-21`, `sha256sum -c`).
- Código en GitHub: `https://github.com/h73212653-code/syn`.
- ISO `archlinux-2026.11.01` con **archinstall 4.5**.

## Arrancar el ISO

En el menú de Ventoy elige el ISO de Arch y arranca en modo UEFI:

```bash
ls /sys/firmware/efi/efivars >/dev/null && echo UEFI
ping -c1 archlinux.org
```

## archinstall: qué elegir

```bash
archinstall
```

| Menú | Qué poner |
| --- | --- |
| Language | Español |
| Keyboard | `es` (o `us`) |
| Mirrors | los de tu país |
| Locale | `es_ES.UTF-8` |
| Disk configuration | **Wipe disk → `nvme0n1`** (NO `sda`, NO `sdb`) |
| File system | btrfs (con subvolúmenes `@` y `@home`) |
| Bootloader | systemd-boot |
| Swap | zram |
| Hostname | `arch` (o el que quieras) |
| Root password | la que uses |
| User account | tu usuario, con sudo |
| Profile → Type | **Minimal** |
| Audio | PipeWire |
| Kernels | `linux` |
| Network | NetworkManager |
| Additional packages | `git kitty sudo` |
| Timezone | tu zona |
| NTP | activado |

> **Ojo con el disco.** En la lista aparecen tres: `nvme0n1` (SSD, donde va
> Arch), `sda` (HDD con el Fedora viejo) y `sdb` (el USB con el backup).
> Solo se selecciona `nvme0n1`. Si dudas, cancela y comprueba con `lsblk`.

Al terminar: `Reboot`, quita el USB y arranca Arch. Entrarás en una TTY sin
entorno gráfico; es lo esperado.

## Instalar niri + DMS

Es el comando que recomienda la wiki de niri para Arch. `dux-shell` (DMS) ya
está en el repo `extra`, no hace falta AUR.

```bash
sudo pacman -Syu
sudo pacman -S --needed \
  niri xwayland-satellite xdg-desktop-portal-gnome xdg-desktop-portal-gtk \
  kitty dux-shell matugen cava qt6-multimedia-ffmpeg polkit-gnome \
  ttf-jetbrains-mono-nerd noto-fonts noto-fonts-emoji
```

Activa DMS como servicio de usuario:

```bash
systemctl --user add-wants niri.service dms
```

## Arrancar niri

Desde la TTY:

```bash
niri-session
```

La primera vez niri crea una config por defecto y DMS genera sus `dms/*.kdl`.

Opcional, si quieres login gráfico en vez de TTY:

```bash
sudo pacman -S greetd greetd-tuigreet
sudo systemctl enable greetd
```

## Restaurar tu configuración

```bash
BK=/run/media/$USER/Ventoy/syn-backup-2026-11-21

mkdir -p ~/.config
cp -r "$BK/config/niri"  ~/.config/
cp -r "$BK/config/kitty" ~/.config/
cp -r "$BK/config/syn"   ~/.config/
cp -r "$BK/Musica"       ~/

niri validate
```

Si `niri validate` falla por los `dms/*.kdl`, arranca niri una vez para que DMS
los regenere y vuelve a validar.

## Instalar SYN

```bash
git clone https://github.com/h73212653-code/syn.git ~/syn
cd ~/syn
./install-cachyos.sh
./setup-niri.sh
```

Atajo en `~/.config/niri/syn.kdl`:

```kdl
binds {
    Mod+T { spawn "syn-kitty"; }
}
```

## Instalar SYNGET (descargador de música)

```bash
sudo pacman -S --needed ffmpeg
git clone https://github.com/h73212653-code/synget.git ~/synget
cd ~/synget
./install.sh
```

SYNGET baja audio de YouTube a `~/Musica` con etiquetas y carátula, listo para
que SYN lo reproduzca. Config opcional en `~/.config/synget/config.toml`
(plantilla en `config.example.toml`).

## Comprobaciones finales

```bash
niri --version          # 26.04 o superior (blur)
niri validate
pactl info              # PipeWire vivo
syn-kitty               # abre SYN con carátula
```

## Alternativa: perfil Niri + DMS

archinstall 4.4+ trae un perfil **Niri (DankMaterialShell)** que instala niri y
DMS de una vez. Funciona, pero mete paquetes que no usas (alacritty, greeter) y
es donde suelen salir los errores. Si lo pruebas: Profile → Desktop →
Niri (DankMaterialShell), y luego salta directo a "Restaurar tu configuración".

## Si algo sale mal

- El HDD (`sda`) sigue teniendo el Fedora viejo: puedes arrancar de él desde
  el menú UEFI mientras no lo borres.
- El backup del USB es independiente del sistema: se puede leer desde el ISO
  en vivo con `sha256sum -c SHA256SUMS`.
- Para reinstalar: repite archinstall; el código y la música están a salvo.
