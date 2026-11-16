# Changelog

## 1.3.0 — 2026-11-16

### Nuevas funciones
- **Instalador para Debian y Ubuntu** (`install-debian.sh`): detecta la versión
  de la distro, comprueba que Python sea 3.11 o superior, instala lo que falte
  con `apt`, crea el entorno virtual y verifica al final que SYN arranca.
  Probado en Debian 13, Debian 12, Ubuntu 24.04 y Ubuntu 22.04.
- Opciones `--sin-kitty` (si ya usas otra terminal) y `--sin-apt` (si gestionas
  los paquetes a mano).
- Si falta un paquete opcional en tu versión de la distro, avisa y continúa en
  vez de abortar.

### Correcciones
- `textual-image` se pedía en `>=0.14`, que exige Python 3.12; en Debian 12 y
  Ubuntu 22.04 (Python 3.11) la instalación fallaba. Ahora el rango es
  `>=0.12,<1` y pip elige la versión adecuada para cada Python.
- `install.sh` delega en el instalador de Debian/Ubuntu cuando detecta `apt`,
  para no mantener dos rutas distintas.

### Mejoras
- El acceso directo `.desktop` incluye `StartupWMClass=syn`, así el dock y la
  Dynamic Island asocian la ventana con la aplicación.
- README: sección de Debian/Ubuntu con tabla de versiones probadas.

## 1.2.0 — 2026-11-16

### Nuevas funciones
- **MPRIS2**: SYN publica su estado en D-Bus como
  `org.mpris.MediaPlayer2.syn`. La Dynamic Island de KDE, el applet de medios de
  Plasma, las teclas multimedia y `playerctl` detectan la canción, el artista,
  la carátula y el progreso.
- Los controles externos funcionan: reproducir/pausar, siguiente, anterior,
  parar y cambiar el volumen desde la isla o el escritorio.

### Mejoras
- La posición se interpola con el reloj para que la barra de progreso de la isla
  avance suave aunque SYN solo la actualice una vez por segundo.
- La carátula se guarda en caché (`~/.cache/syn/covers`) y se publica como
  `mpris:artUrl`.
- La carátula está disponible desde el primer instante: se extrae en milisegundos
  y las carpetas se precalientan en segundo plano, así la isla no espera su
  búsqueda en iTunes (1 s) ni muestra una portada distinta.
- Si no hay sesión D-Bus o falta `jeepney`, MPRIS se desactiva en silencio.

## 1.1.0 — 2026-11-16

### Nuevas funciones
- **Letras de canciones** con la tecla `l`: se obtienen de LRCLIB y se muestran
  centradas en un panel con scroll. Si no hay conexión o no existe la letra, se
  indica sin interrumpir la reproducción.
- **Pestañas por carpeta**: cada subcarpeta de `~/Musica` aparece como una
  pestaña independiente. Se cambia con `←` / `→` y cada pestaña muestra solo sus
  pistas y su contador.
- **Transparencia** mejorada con la tecla `t`: ahora afecta también al panel de
  letras, manteniendo el fondo del terminal.

### Mejoras
- La reproducción continúa en su carpeta original al cambiar de pestaña y el
  avance automático sigue dentro de esa carpeta.
- La búsqueda de letras se hace en segundo plano, sin bloquear la interfaz.
- Los títulos con corchetes ya no se interpretan como estilos de Rich.
- Documentación de controles actualizada en el README.

## 1.0.0

- Primera versión publicada.
