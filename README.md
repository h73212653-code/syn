# SYN 🎵

<p align="center">
  <img src="assets/icon-syn.png" alt="Icono de SYN" width="110">
</p>

<p align="center">
  <img src="assets/SYN.png" alt="SYN Reproductor TUI" width="420">
  <img src="assets/syn2.png" alt="SYN Reproductor TUI" width="420">
</p>

### 🔗 Repositorio
[https://github.com/h73212653-code/syn](https://github.com/h73212653-code/syn)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Textual-TUI-purple.svg" alt="Textual">
  <img src="https://img.shields.io/badge/Kitty-Terminal-green.svg" alt="Kitty">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

Reproductor de música local ultraligero y elegante para la terminal, construido con **Textual** y diseñado para **Kitty**. 

- 🖼️ **Protocolo Gráfico Nativo (TGP):** Carátulas en alta resolución directamente en tu terminal.
- 🎵 **Soporte Universal:** MP3, FLAC, WAV, OGG, Opus y M4A con extracción de metadatos mediante **Mutagen**.
- 🔎 **Búsqueda global:** pulsa `/` y filtra por título, artista, álbum o carpeta sin importar dónde esté la canción.
- 🎤 **Letras sincronizadas:** con `l` se resalta la línea que suena y el panel se desplaza solo (si la versión coincide).
- ⚡ **Alto Rendimiento:** Consumo mínimo de CPU y RAM, con repintado inteligente bajo demanda.
- 🎨 **Modo Transparente:** Integración perfecta con fondos translúcidos y difuminados de Kitty.

---

## 🚀 Instalación Rápida

### 1. Arch Linux / CachyOS / Manjaro
```bash
git clone https://github.com/h73212653-code/syn.git ~/syn
cd ~/syn
./install-cachyos.sh
```

### 2. Debian / Ubuntu / Linux Mint / Pop!_OS
```bash
git clone https://github.com/h73212653-code/syn.git ~/syn
cd ~/syn
./install-debian.sh
```
Necesitas **Debian 12+** o **Ubuntu 24.04+** (Python 3.11 o superior).
El instalador detecta tu versión, instala lo que falte con `apt`, crea el
entorno virtual y comprueba al final que SYN arranca.

### 3. Fedora / Nobara (Universal)
```bash
git clone https://github.com/h73212653-code/syn.git ~/syn
cd ~/syn
./install.sh
```

---

## 📥 Descarga música integrada con `synget`

SYN incluye soporte para descargar música directamente desde YouTube en alta calidad (**Opus / M4A**) utilizando **`synget`**:

```bash
# Descarga rápida de un enlace o búsqueda directamente a ~/Musica
synget "https://www.youtube.com/watch?v=..."
synget "tu artista o canción favorita"

# O abre la TUI interactiva de synget
synget
```

---

## 📋 Guía Detallada de Instalación por Distro

### Instalación en Debian / Ubuntu
El instalador hace todo, pero si prefieres ver los requisitos:
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip kitty git ffmpeg
```
Luego:
```bash
cd ~/syn
./install-debian.sh
```

Opciones útiles:
```bash
./install-debian.sh --sin-kitty   # si ya usas otra terminal
./install-debian.sh --sin-apt     # si gestionas los paquetes tú
```

| Distro | Python | Estado |
| :--- | :--- | :--- |
| Debian 13 (trixie) | 3.13 | ✅ Probado |
| Debian 12 (bookworm) | 3.11 | ✅ Probado |
| Ubuntu 24.04 LTS | 3.12 | ✅ Probado |
| Ubuntu 22.04 LTS | 3.11 | ✅ Probado (desde `universe`) |
| Linux Mint 22 / Pop!_OS 24.04 | 3.12 | ✅ Compatible |
| Debian 11 / Ubuntu 20.04 | 3.9 / 3.8 | ❌ Python antiguo (ver abajo) |

> En Python 3.11 se instala `textual-image` 0.12, la última versión compatible
> con esa versión de Python. Las carátulas funcionan igual; en 3.12+ se usa 0.14.

Si tu Python es más antiguo que 3.11, el instalador te avisa y no rompe nada.
Para arreglarlo en Ubuntu 22.04 o Debian 12 con un Python más nuevo:
```bash
sudo add-apt-repository ppa:deadsnakes/ppa   # solo Ubuntu
sudo apt update && sudo apt install python3.12 python3.12-venv
./install-debian.sh
```

### Instalación en Fedora / Nobara
Requisitos del sistema:
```bash
sudo dnf install kitty python3 python3-pip pipewire pipewire-pulseaudio git @development-tools ffmpeg
```

### Instalación en CachyOS / Arch Linux
CachyOS usa `pacman`:
```bash
sudo pacman -S --needed --noconfirm kitty python python-pip pipewire pipewire-pulse git libpulse base-devel ffmpeg
```

---

## 🕹️ Arrancar

El instalador crea el comando global `syn`. Escríbelo en cualquier terminal:

```bash
syn
```

Para abrir SYN en una ventana dedicada de Kitty con soporte gráfico completo:
```bash
syn-kitty
```

También puedes ejecutarlo sin instalarlo:
```bash
./bin/syn
./bin/syn-kitty
```

---

## 📊 Consumo

Medido con `tools/benchmark.py` en Arch Linux (Intel i7-10510U, 8 hilos),
ventana de 120×40, biblioteca de 120 pistas y ventanas de muestreo de 10 s:

| Estado | SYN 1.4.2 | Normal | Gaming Mode |
| --- | ---: | ---: | ---: |
| Abierto en reposo | 80,1 MB · ~0,1 % | 79,6 MB · ~0,1 % | **58,5 MB** · ~0,1 % |
| Reproduciendo | 98,0 MB · ~0,8 % | 97,7 MB · ~0,8 % | **60,9 MB** · ~0,8 % |

El Gaming Mode arrancado con `syn --game-mode` ahorra un **27 % de RAM en
reposo** y un **38 % reproduciendo**, porque no carga Pillow, textual-image ni
pyfiglet. Pulsar `g` en caliente libera unos 22 MB, pero los módulos ya
importados siguen en memoria; para el consumo mínimo hay que arrancar
directamente en modo ligero.

### Medir tu propio equipo

```bash
.venv/bin/python tools/benchmark.py --label "mi equipo"
.venv/bin/python tools/benchmark.py --music-dir ~/Música --gaming
.venv/bin/python tools/benchmark.py --start-in-gaming --json /tmp/syn-gaming.json
```

La prueba arranca SYN real en un pseudo-terminal, reproduce una pista y
muestrea CPU y RSS desde `/proc`. Usa el driver `dummy` de SDL para no hacer
ruido y que el resultado no dependa del servidor de sonido. Compara siempre
mediciones hechas en la misma máquina y con la misma biblioteca.

---

## 🎮 Gaming Mode

Pensado para jugar sin que el reproductor compita por CPU, RAM o disco:

```bash
syn --game-mode      # arranca ligero
syn --no-covers      # interfaz normal, pero sin carátulas
```

| | Interfaz normal | Gaming Mode |
| :--- | :---: | :---: |
| Carátulas y portadas generadas | ✅ | ❌ |
| Logo y preparación de carátulas | ✅ | ❌ |
| Letras sincronizadas | ✅ | ❌ |
| Lista, búsqueda, progreso y volumen | ✅ | ✅ |
| MPRIS y teclas multimedia | ✅ | ✅ |

Dentro de SYN, `g` alterna entre ambos modos sin reiniciar. Al volver al modo
normal se recarga solo la carátula de la pista actual. El Gaming Mode mantiene
la reproducción, el control de volumen, la búsqueda y los controles MPRIS.

---

## 🎵 Música

La carpeta configurada por defecto es:
```toml
music_dir = "~/Musica"
recursive = true
game_mode = false
covers = true
```

Se puede cambiar de varias formas:
```bash
syn --music-dir ~/Música --no-recursive
SYN_MUSIC_DIR=~/Música syn
```

La búsqueda acepta **MP3, FLAC, WAV, OGG, Opus y M4A**. Las carátulas se extraen de las etiquetas del archivo.

> **M4A/AAC** se decodifica a FLAC con `ffmpeg`, porque SDL_mixer no lo
> reproduce directamente. La primera reproducción tarda un segundo extra y la
> conversión queda en `~/.cache/syn/transcode`; después es instantánea.
> Si no tienes `ffmpeg`: `sudo pacman -S ffmpeg`, `sudo apt install ffmpeg`
> o `sudo dnf install ffmpeg`.

---

## 📥 Guía: Cómo descargar música de YouTube

Para descargar música y tenerla en tu biblioteca, la mejor herramienta es `yt-dlp`.

### 📦 Paso 1: Instalar paquetes base
**Arch Linux:**
```bash
sudo pacman -S --needed yt-dlp ffmpeg
```
**Fedora:**
```bash
sudo dnf install yt-dlp ffmpeg
```
**Debian/Ubuntu:**
```bash
sudo apt update && sudo apt install yt-dlp ffmpeg
```

### ⚙️ Paso 2: Instalar Deno (Obligatorio)
YouTube bloquea las descargas si no detecta un entorno de JS.
```bash
curl -fsSL https://deno.land/install.sh | sh
source ~/.bashrc
```

### 📁 Paso 3: Descarga
```bash
mkdir -p ~/Musica
yt-dlp -x --audio-format mp3 --audio-quality 0 --embed-thumbnail --embed-metadata -P ~/Musica "URL_DEL_VIDEO"
```

---

## ⌨️ Controles

| Tecla | Acción |
| :--- | :--- |
| `↑` / `↓` o `k` / `j` | Navegar por la lista |
| `/` | Buscar en toda la música (título, artista, álbum o carpeta) |
| `Ctrl+F` | Abrir la búsqueda (alternativa a `/`, útil según el teclado) |
| `Esc` | Cerrar la búsqueda y volver a la carpeta |
| `Enter` | Reproducir la pista seleccionada |
| `Espacio` | Pausar / reanudar |
| `n` / `p` | Siguiente / anterior |
| `←` / `→` | Cambiar de carpeta (pestañas automáticas) |
| `l` | Mostrar / ocultar la letra de la canción |
| `g` | Alternar Gaming Mode (sin carátulas, logo ni letras) |
| `y` / `u` | Subir / bajar el volumen (5%) |
| `m` | Silenciar / restaurar sonido |
| `t` | Activar / desactivar fondo transparente |
| `q` | Salir |

### 🔎 Búsqueda

Pulsa `/` en cualquier momento y escribe. SYN busca a la vez en **todas las
carpetas** y muestra los resultados según coincidan con el título, el artista,
el álbum o el nombre de la carpeta:

- No importan los acentos: `cancion` encuentra «Canción».
- Varias palabras funcionan como filtros: `daft discovery` acota a ese álbum.
- `Enter` salta de la barra a los resultados para moverte con `↑`/`↓` y
  reproducir con `Enter`.
- `Esc` cierra la búsqueda y te devuelve a la carpeta donde estabas.
- Mientras escribes, el logo deja su sitio para que quepan más resultados.
- Si tu teclado escribe `/` con `Mayús+7` y no responde, usa `Ctrl+F`.

---

## 🪟 Integración con el escritorio (MPRIS)

SYN publica lo que suena por MPRIS2 con el nombre `org.mpris.MediaPlayer2.syn`,
así que cualquier cliente compatible lo detecta solo, sin configuración:

- **Dynamic Island** de KDE Plasma: título, artista, carátula y progreso.
- Applet de medios de Plasma, widgets de escritorio y teclas multimedia.
- `playerctl` y cualquier otro cliente MPRIS.

Los controles de la isla funcionan de verdad: reproducir/pausar, siguiente,
anterior, parar y volumen. Si el escritorio no tiene D-Bus, SYN sigue igual.

---

## 🌊 niri + DMS (transparencia y blur)

SYN se ve translúcido y con el fondo desenfocado en niri 26.04 o superior.
Todo se configura con un comando:

```bash
./setup-niri.sh
```

El script hace tres cosas y puedes repetirlo sin miedo:

1. Copia `niri/syn.kdl` a `~/.config/niri/syn.kdl` y lo incluye desde tu
   `config.kdl`.
2. Pone `background_opacity 0.75` en `~/.config/kitty/kitty.conf` si estaba a
   `1.0` (opaco).
3. Valida la configuración con `niri validate`.

La regla de niri usa `background-effect { blur true }`, que es el blur real del
compositor, y `draw-border-with-background false`, sin el cual niri pinta un
rectángulo opaco detrás de la ventana y la transparencia no se ve.

Después cierra **todas** las ventanas de Kitty y vuelve a abrir con `syn-kitty`:
la opacidad se lee al arrancar cada ventana.

Si usas una versión de niri anterior a 26.04, borra el bloque
`background-effect` de `~/.config/niri/syn.kdl`; la transparencia seguirá
funcionando, solo que sin desenfoque.

---

## 🔄 Actualizaciones

Para mantener SYN al día, ejecuta:
```bash
cd ~/syn
./update.sh
```

---

## 🛠️ Problemas frecuentes

- **No hay sonido:** comprueba que PipeWire/PulseAudio esté activo con `pactl info`.
- **En Ubuntu 22.04 el instalador dice que Python es antiguo:** esa versión trae
  Python 3.10 y SYN necesita 3.11+. Instala uno más nuevo:
  ```bash
  sudo add-apt-repository ppa:deadsnakes/ppa
  sudo apt update && sudo apt install python3.12 python3.12-venv
  ./install-debian.sh
  ```
- **`error: externally-managed-environment` al usar pip:** es la protección de
  Debian/Ubuntu. No instales con `pip` del sistema; usa `./install-debian.sh`,
  que crea un entorno virtual propio en `.venv`.
- **`syn-kitty` dice que Kitty no está instalado:** `sudo apt install kitty`
  (o `sudo dnf install kitty`).
- **La portada sale mal:** abre con `syn-kitty`.
- **No aparecen canciones:** revisa `music_dir` en `config.toml`.
- **La isla o el applet no muestra SYN:** comprueba que solo hay una instancia
  abierta y que `busctl --user list | grep mpris` muestra
  `org.mpris.MediaPlayer2.syn`.
- **Fuente rara en el logo:** SYN usa caracteres Unicode de bloque; no necesita una Nerd Font.
