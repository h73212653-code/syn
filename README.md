# SYN 🎵

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
- 🎵 **Soporte Universal:** MP3, FLAC, WAV y OGG con extracción de metadatos mediante **Mutagen**.
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

## 📋 Guía Detallada de Instalación por Distro

### Instalación en Debian / Ubuntu
El instalador hace todo, pero si prefieres ver los requisitos:
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip kitty git
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
sudo dnf install kitty python3 python3-pip pipewire pipewire-pulseaudio git @development-tools
```

### Instalación en CachyOS / Arch Linux
CachyOS usa `pacman`:
```bash
sudo pacman -S --needed --noconfirm kitty python python-pip pipewire pipewire-pulse git libpulse base-devel
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

Medido en Fedora/CachyOS con Kitty, después del arranque:

| Estado | CPU | RAM |
| --- | ---: | ---: |
| Abierto en reposo | ~0.07% | ~81 MB |
| Reproduciendo MP3 (80×24) | ~1.4% | ~98 MB |
| Reproduciendo en ventana grande | ~2–4% | ~98 MB |
| En pausa | ~0.7% | ~98 MB |
| Cerrado | 0% | 0 MB |

---

## 🎵 Música

La carpeta configurada por defecto es:
```toml
music_dir = "~/Musica"
recursive = true
```

Se puede cambiar de varias formas:
```bash
syn --music-dir ~/Música --no-recursive
SYN_MUSIC_DIR=~/Música syn
```

La búsqueda acepta **MP3, FLAC, WAV y OGG**. Las carátulas se extraen de las etiquetas del archivo.

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
