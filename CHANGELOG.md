# Historial de Cambios

Todos los cambios notables de este proyecto se documentarán en este archivo.

## [No publicado]
### Agregado
- **Soporte para iPod (Nano 7G):** nueva sección para detectar el dispositivo y leer su biblioteca (canciones y playlists), con información del modelo (imagen oficial por color, capacidad) y desglose de almacenamiento en tiempo real.
- **iPod — escritura segura:** botón "Escribir en el iPod" que reescribe la base de datos en el formato de Cicada mediante un flujo transaccional: plan *dry-run* fuera del dispositivo, **backup automático** previo, y **rollback** ante cualquier error. La primera escritura pide confirmación explícita (advertencia irreversible de incompatibilidad con Music.app).
- **iPod — respaldos y expulsión:** creación y restauración de backups `.tar.zst`, y expulsión segura del volumen.
- **iPod — sincronización de reproducciones:** lectura y persistencia local de contadores de reproducción (base para sincronización bidireccional).

### Nota
- Algunas funciones del iPod aún no están disponibles y responden "no implementado" (sin efecto en el dispositivo): crear/importar playlists y la gestión de fotos, videos, podcasts y audiolibros. Están planificadas para próximas fases.

## [1.1.2] - 2026-08-07
### Agregado
- **Playlists:** Nuevo botón de descarga individual (en tiempo real) para pistas no encontradas en la biblioteca local durante la replicación, inyectando metadatos de Spotify y organizando el archivo automáticamente.
- **Biblioteca:** Menú contextual en la vista de biblioteca con opciones para mostrar en el explorador, eliminar de forma segura y un nuevo editor avanzado de metadatos de las canciones (incluyendo manejo de carátulas).

### Cambiado
- **Playlists:** Animaciones de reordenamiento de canciones (Drag & Drop) más fluidas en la vista de réplica, brindando feedback visual inmediato.


## [1.1.1] - 2026-07-19
### Agregado
- Nuevas traducciones del `README` al inglés (`README_en.md`) y japonés (`README_ja.md`) con barra de navegación de idiomas.
- Nueva sección de Privacidad y Seguridad detallando el manejo local de datos.
- Enlaces a los Términos y Condiciones (`TERMS.md`) en la documentación y en el menú "Sobre Cicada" dentro de la aplicación.

## [1.1.0] - 2026-07-15
### Agregado
- Implementación de comprobaciones automáticas de actualizaciones, avisos de apoyo en Ko-fi y funcionalidad de búsqueda en la biblioteca.
- Nota de autorización de usuario para el modo de desarrollo.
- Revisión de la configuración de la clave API y adición de la sección de descargas.

### Cambiado
- Revisión de la sección de instalación en el README.md.
- Se ignoró `compile_intel.sh` en el control de versiones.
- Se eliminó la compilación para macOS 13 Intel del flujo de trabajo de lanzamientos.

## [1.0.1] - 2026-07-11
### Agregado
- Selección de archivos/carpetas multiplataforma, implementación del empaquetado macOS OneDir y estabilización del flujo de cierre de la aplicación.
- Adición de nombre de usuario de Ko-fi para apoyo financiero.

### Cambiado
- Migración de archivos de datos de aplicaciones persistentes a directorios específicos de la plataforma y actualización del flujo de trabajo de lanzamiento en macOS.

### Corregido
- Desactivación de la actualización automática de yt-dlp en entornos empaquetados y manejo de errores de inicio de sesión de Spotify mediante redireccionamientos.
- Archivos de compilación de instaladores corregidos.
- Ajustes generales para la versión v1.0.1.

## [1.0.0] - 2026-07-11
### Agregado
- Lanzamiento inicial: Cicada v1.0.0.
- Íconos de colores.
- Bug SVG.
- Icono contextual.
- Requerimientos.
- Cerebro de Cicada.
