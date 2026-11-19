# Changelog

## 1.4.1 — 2026-11-19

### Correcciones
- **Canciones sin letra aunque LRCLIB la tuviera**: la búsqueda descartaba las
  descargas de YouTube cuyo artista es el nombre del canal, las que llevan
  varios artistas en la etiqueta («Maroon 5, Wiz Khalifa») o las que traen el
  artista dentro del título («COQUETA - Fuerza Regida»). Ahora los artistas se
  separan bien, el título se prueba entero y por partes y, si hace falta, se
  deduce el artista del propio título. En una biblioteca de prueba se pasa de
  10 a 15 canciones con letra.
- Los títulos marcados como instrumentales muestran «Canción instrumental» en
  vez de «no hay letra disponible».
- Si LRCLIB limita las peticiones (HTTP 429), se reintenta una vez tras una
  espera corta en lugar de darse por vencido.

### Mejoras
- El volumen arranca al **100 %** (antes 82 %). Con `u` y `y` se baja o sube
  de 5 en 5, y `m` sigue silenciando.

## 1.4.0 — 2026-11-19

### Nuevas funciones
- **Letras sincronizadas**: si LRCLIB tiene la letra con tiempos, el panel
  resalta la línea que está sonando, deja las anteriores y las siguientes en
  tonos apagados y se desplaza solo. Si la duración de la versión de LRCLIB no
  coincide con la que suena (slowed, sped up, otra edición), se muestra la
  letra sin tiempos: mejor sin resaltar que desincronizada.
- **Búsqueda global** (tecla `/`): filtra toda la biblioteca por título,
  artista, álbum o carpeta, sin distinguir mayúsculas ni acentos. Los
  resultados se ordenan por coincidencia (primero las que empiezan por lo
  escrito) y `Esc` vuelve a la carpeta anterior.
- Al buscar, el logo se oculta para dejar más sitio a la lista y las pestañas
  de carpeta desaparecen, porque los resultados pueden venir de cualquiera.
- `Ctrl+F` abre la búsqueda igual que `/`, por si la distribución del teclado
  no envía la barra.

### Correcciones
- La tecla `/` no abría la búsqueda en teclados donde `/` se escribe con
  `Mayús+7` (español, alemán…) si la terminal usa el protocolo de teclado de
  Kitty: la pulsación llegaba como `shift+7` y el atajo no se reconocía. Ahora
  se aceptan todas las variantes y `Ctrl+F` funciona siempre como alternativa.

### Mejoras
- El pie de ayuda se reparte en dos líneas fijas, así no queda una palabra
  suelta ni se corta al añadir atajos.
- Reproducir una pista encontrada por la búsqueda ya avanza por **su** carpeta
  real (antes se habría quedado anclada a la carpeta visible).
- Las letras se guardan en caché y las búsquedas a LRCLIB fallan en silencio
  si no hay red, así que nunca bloquean la reproducción.

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
