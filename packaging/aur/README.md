# Paquetes AUR de SYN

Dos paquetes, porque `pyfiglet` no está empaquetado ni en Arch ni en AUR:

| Paquete | Qué es | Estado |
| --- | --- | --- |
| `python-pyfiglet` | Dependencia pura Python (MIT) | Listo |
| `syn-tui` | SYN 1.4.2 | Listo |

Dependencias de `syn-tui`:

| Dependencia | Dónde está |
| --- | --- |
| `python-textual` | `extra` |
| `python-mutagen` | `extra` |
| `python-pillow` | `extra` |
| `python-jeepney` | `extra` |
| `python-textual-image` | AUR |
| `python-pygame-ce` | AUR |
| `python-pyfiglet` | AUR (este repo) |
| `kitty` | `extra` |

Por eso, para instalar SYN desde AUR hace falta un helper (`yay`, `paru`) que
resuelva las dependencias de AUR.

## Probado

Construido en un contenedor Arch limpio (`archlinux:latest`) con
`makepkg --nodeps`, instalado y verificado:

```
$ python -m syn --version
SYN 1.4.2
```

## Publicar en AUR

1. Crea cuenta en <https://aur.archlinux.org> y añade tu clave SSH pública en
   *My Account → SSH Public Key*.
2. Publica primero `python-pyfiglet`:

```bash
git clone ssh://aur@aur.archlinux.org/python-pyfiglet.git
cp packaging/aur/python-pyfiglet/PKGBUILD packaging/aur/python-pyfiglet/.SRCINFO \
   python-pyfiglet/
cd python-pyfiglet
git add PKGBUILD .SRCINFO
git commit -m "Initial import: python-pyfiglet 1.0.4"
git push
```

3. Después `syn-tui`:

```bash
git clone ssh://aur@aur.archlinux.org/syn-tui.git
cp packaging/aur/syn-tui/PKGBUILD packaging/aur/syn-tui/.SRCINFO syn-tui/
cd syn-tui
git add PKGBUILD .SRCINFO
git commit -m "Initial import: syn-tui 1.4.2"
git push
```

4. Comprueba que aparece: <https://aur.archlinux.org/packages/syn-tui>

## Actualizar una versión

```bash
# 1. Sube el tag en GitHub (v1.4.3, etc.)
# 2. En packaging/aur/syn-tui/PKGBUILD:
#    pkgver=1.4.3
#    pkgrel=1
# 3. Regenera checksum y .SRCINFO:
updpkgsums
makepkg --printsrcinfo > .SRCINFO
# 4. Copia PKGBUILD y .SRCINFO al clon del AUR y haz push
```

## Notas

- `arch=('any')` porque todo es Python puro + datos.
- El paquete instala `/usr/bin/syn` (entry point del wheel) y
  `/usr/bin/syn-kitty` (abre kitty con `--class syn`).
- Iconos en `/usr/share/icons/hicolor/` y `.desktop` en
  `/usr/share/applications/`.
- `kitty` va como dependencia porque el lanzador del menú lo usa; el binario
  `syn` funciona en cualquier terminal, pero sin portadas.
- Si algún día `python-textual-image` o `python-pygame-ce` entran en `extra`,
  se pueden quitar del AUR sin tocar el PKGBUILD.
