# Instalar Arch con niri + DMS (archinstall)

Guía para este equipo: NVMe de 476 GB como sistema, HDD de 1 TB como datos.
El USB Ventoy tiene el ISO de Arch **y** el backup de SYN: **no lo formatees**.

## Antes de empezar

- Backup verificado en el USB (`syn-backup-2026-11-21`, `sha256sum -c`).
- Código en GitHub: `https://github.com/h73212653-code/syn`.
- El ISO es `archlinux-2026.11.01`, que trae **archinstall 4.5**. Esa versión ya
  incluye el perfil **Niri + DankMaterialShell**, justo tu escritorio.

## Arrancar el ISO

En el menú de Ventoy elige el ISO de Arch y arranca en modo UEFI.
Comprueba que estás en UEFI:

```bash
ls /sys/firmware/efi/efivars >/dev/null && echo UEFI
```

Conecta red (archinstall también puede configurarla, pero mejor comprobar):

```bash
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
| Profile → Type | Desktop |
| Profile → Desktop | **Niri (DankMaterialShell)** |
| Audio | PipeWire |
| Kernels | `linux` |
| Network | NetworkManager |
| Additional packages | `kitty git` |
| Timezone | tu zona |
| NTP | activado |

> **Ojo con el disco.** En la lista aparecen tres: `nvme0n1` (SSD, donde va
> Arch), `sda` (HDD con el Fedora viejo) y `sdb` (el USB con el backup).
> Solo se selecciona `nvme0n1`. Si dudas, cancela y comprueba con `lsblk`.

Al terminar: `Reboot`, quita el USB y arranca Arch.

## Primer arranque

Si el perfil no dejó el servicio de DMS activo:

```bash
systemctl --user add-wants niri.service dms
```

Entra en niri desde el gestor de sesión o, desde una TTY, con:

```bash
niri-session
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

## Comprobaciones finales

```bash
niri --version          # 26.04 o superior (blur)
niri validate
pactl info              # PipeWire vivo
syn-kitty               # abre SYN con carátula
```

## Si algo sale mal

- El HDD (`sda`) sigue teniendo el Fedora viejo: puedes arrancar de él desde
  el menú UEFI mientras no lo borres.
- El backup del USB es independiente del sistema: se puede leer desde el ISO
  en vivo con `sha256sum -c SHA256SUMS`.
- Para reinstalar: repite archinstall; el código y la música están a salvo.
