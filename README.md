# SYN

Reproductor de música local para terminal, hecho con **Textual** y pensado para
**Kitty**. La portada se dibuja con el protocolo gráfico nativo de Kitty
(Terminal Graphics Protocol), los metadatos y las carátulas se leen con
**Mutagen**, y la reproducción usa **pygame-ce** (el paquete se importa como
`pygame`).

```
┌───────────────────────────┬──────────────────────────────────────┐
│                           │   ███████╗██╗   ██╗███╗   ██╗     │
│         PORTADA           │   ██╔════╝╚██╗ ██╔╝████╗  ██║     │
│        alta resolución    │   ███████╗ ╚████╔╝ ██╔██╗ ██║     │
│                           │   ╚════██║  ╚██╔╝  ██║╚██╗██║     │
│                           │   ███████║   ██║   ██║ ╚████║     │
│                           │   ╚══════╝   ╚═╝   ╚═╝  ╚═══╝     │
│      Título               │   Música →           8 canciones  │
│      Artista              │   ▶ 01  Animals · Maroon 5         │
│      Álbum                │     02  BbY WOW · KAROL G…         │
│                           │     03  Centuries · Fall Out Boy   │
├───────────────────────────┴──────────────────────────────────────┤
│ ▶  1:23  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  3:51  Vol 82%│
│   Espacio pausa · Enter reproducir · y/u volumen · m mudo · t fondo · q salir   │
└──────────────────────────────────────────────────────────────────┘
```

El logo se adapta al tamaño de la ventana: usa una versión de 39×11 en
80×24 y crece hasta 60×11 en ventanas grandes. No necesita Nerd Font.

## Instalación en Fedora

Requisitos del sistema:

```bash
sudo dnf install kitty python3 python3-pip pipewire pipewire-pulseaudio
```

Instalación del proyecto:

```bash
cd ~/syn
python3 -m venv .venv
source .venv/bin/activate
pip install textual textual-image mutagen pygame-ce pyfiglet pillow
```

También puedes usar el instalador incluido, que crea el entorno virtual y el
comando `~/.local/bin/syn`:

```bash
cd ~/syn
./install.sh
```

O instalar desde `requirements.txt`:

```bash
pip install -r requirements.txt
```

> `pygame-ce` es la edición comunitaria de pygame, compatible como reemplazo
> directo (`import pygame`). Se usa porque publica ruedas para Python 3.15 en
> Fedora 45. Si prefieres el pygame clásico, cambia `pygame-ce` por `pygame`.

## Arrancar

El instalador crea el comando `syn`. Escríbelo en cualquier terminal:

```bash
syn
```

SYN se abre **en esa misma terminal**. Para abrir una ventana nueva de Kitty:

```bash
syn-kitty
```

También puedes ejecutarlo sin instalarlo:

```bash
./bin/syn
./bin/syn-kitty
```

## Consumo

Medido en Fedora 45 con Kitty, después del arranque:

| Estado | CPU | RAM |
| --- | ---: | ---: |
| Abierto en reposo | ~0.07% | ~81 MB |
| Reproduciendo MP3 (80×24) | ~1.4% | ~98 MB |
| Reproduciendo en ventana grande | ~2–4% | ~98 MB |
| En pausa | ~0.7% | ~98 MB |
| Cerrado | 0% | 0 MB |

La interfaz solo se repinta una vez por segundo mientras hay música sonando;
en reposo no hay actualizaciones de progreso ni repintados periódicos. Es
suficientemente ligero para dejarlo abierto mientras juegas, y si quieres cero
consumo puedes cerrarlo con `q`.

## Música

La carpeta configurada es:

```toml
music_dir = "~/Musica"
recursive = true
```

en `config.toml`. Se puede cambiar de varias formas, de mayor a menor prioridad:

```bash
syn --music-dir ~/Música --no-recursive
SYN_MUSIC_DIR=~/Música syn
# ~/.config/syn/config.toml
```

La búsqueda es recursiva por defecto y acepta **MP3, FLAC, WAV y OGG**. La lista
se ordena por artista, álbum y título. Las carátulas se extraen de las etiquetas
del archivo (ID3/APIC, FLAC PICTURE, OGG METADATA_BLOCK_PICTURE). Si una pista
no tiene portada, SYN genera una portada abstracta con sus colores.

## Controles

| Tecla | Acción |
| --- | --- |
| `↑` / `↓` o `k` / `j` | Navegar por la lista |
| `Enter` | Reproducir la pista seleccionada |
| `Espacio` | Pausar / reanudar |
| `n` / `p` | Siguiente / anterior |
| `y` | Subir el volumen un 5% |
| `u` | Bajar el volumen un 5% |
| `m` | Silenciar / restaurar el sonido |
| `t` | Fondo transparente / sólido |
| `q` | Salir |

Al terminar una canción se reproduce automáticamente la siguiente. La lista
también responde al ratón. El volumen se muestra a la derecha de la barra de
progreso (`Vol 82%`, o `Mudo` cuando está silenciado).

## Modo transparente

Pulsa `t` para alternar entre el fondo sólido de SYN y el fondo por defecto del
terminal. En ese modo los paneles, la lista y la barra de progreso dejan de
pintar su propio fondo, así que se ve lo que haya detrás de la ventana. Vuelve a
pulsar `t` para recuperar el fondo oscuro. El pie muestra `t fondo ON` mientras
está activo.

En Kitty la transparencia se controla desde `~/.config/kitty/kitty.conf`:

```conf
background_opacity 0.5
background_blur 10
```

`background_blur` es opcional y suaviza el escritorio que se ve detrás. Si tu
terminal no tiene transparencia configurada, `t` seguirá funcionando, pero el
fondo se verá con el color por defecto de ese terminal. SYN usa el color
`ansi_default` de Textual para que la decisión de opacidad quede siempre en
manos del emulador.

## Estructura

```
syn/
├── bin/
│   ├── syn                 # lanzador dentro de la terminal actual
│   └── syn-kitty           # abre una ventana nueva de Kitty
├── syn/
│   ├── __init__.py
│   ├── __main__.py         # punto de entrada
│   ├── app.py              # App, layout, atajos y estado
│   ├── artwork.py          # carátulas + generación de portadas
│   ├── config.py           # TOML, entorno y CLI
│   ├── library.py          # escaneo y metadatos con mutagen
│   ├── player.py           # reproducción con pygame-ce
│   ├── widgets.py          # portada, lista y logo ASCII
│   └── styles.tcss         # estilos de Textual
├── config.toml
├── install.sh
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Notas sobre Kitty

`textual-image` detecta el protocolo gráfico al arrancar. Debe importarse antes
de que Textual tome el control de la entrada/salida; en este proyecto se importa
desde `widgets.py` antes de crear la aplicación. En Kitty se usa TGP; en otras
terminales con Sixel se usa Sixel, y si no hay soporte gráfico se cae a
semibloques Unicode.

La portada se recorta en cuadrado y se ajusta al tamaño real de celda de la
terminal, evitando que se deforme. La ventana está pensada para funcionar desde
80×24, aunque aprovecha más espacio si la amplías.

## Problemas frecuentes

- **No hay sonido:** comprueba que PipeWire/PulseAudio esté activo con
  `pactl info`. Prueba también `paplay /usr/share/sounds/...` o `mpv` con el
  mismo archivo.
- **La portada sale con caracteres de bloque:** estás fuera de Kitty o el
  protocolo gráfico no está disponible. Abre con `./bin/syn-kitty`.
- **No aparecen canciones:** revisa `music_dir` en `config.toml`, los permisos
  de la carpeta y que los archivos tengan extensión `.mp3`, `.flac`, `.wav` u
  `.ogg`.
- **Fuente rara en el logo:** SYN solo usa caracteres Unicode de bloque; no
  necesita una Nerd Font.
