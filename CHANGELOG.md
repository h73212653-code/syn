# Changelog

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
