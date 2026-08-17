# Especificación Técnica de Endpoints y UI del Subsistema iPod — Cicada

Este documento define la arquitectura técnica, catálogo de endpoints REST, contratos de datos y ciclo de vida de la interfaz de usuario del iPod en Cicada.

---

## 1. Arquitectura General del Subsistema

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Frontend (Cicada UI)                          │
│   • Barra Superior: Metadatos, Almacenamiento, Acciones Rápidas        │
│   • Sub-Sidebar: 6 Categorías (Canciones, Playlists, Fotos, Videos,    │
│                  Podcasts, Audiolibros)                                │
│   • Toolbar: Búsqueda en tiempo real, Filtros (Género, Año, Artista,   │
│              Álbum), Modo Lista / Cuadros, Botón (+)                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / JSON REST APIs
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     FastAPI Router (`/api/ipod`)                       │
│  ├── Detección y Hardware: `discover_ipods()`, `shutil.disk_usage()`   │
│  ├── Parseo de Base de Datos: `load_ipod_library()` (CDB / itdb)       │
│  ├── Coordinador Dry-Run: `create_plan()` (Off-device staging)         │
│  ├── Transacción y Rollback: `apply()` con `write_guard`               │
│  └── Respaldos y Seguridad: `create_backup()`, `restore_backup()`      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Catálogo Detallado de Endpoints REST

### 2.1 Dispositivo, Estado y Almacenamiento

#### `GET /api/ipod/status`
Reporta el diagnóstico exhaustivo de todos los iPods conectados, sus capacidades, esquemas de firma, imagen de modelo/color y almacenamiento en disco.

- **Response (200 OK)**:
```json
{
  "state": "ready",
  "devices": [
    {
      "mount": "/Volumes/IPOD",
      "firewire_guid": "000a27002014abcd",
      "family": "iPod Nano",
      "generation": "7th Gen",
      "model_number": "MD477",
      "serial": "DCYJV000F4M4",
      "capacity": "16GB",
      "color": "Yellow",
      "checksum_scheme": "HASHAB",
      "guid_provenance": "disk",
      "guid_is_write_safe": true,
      "partial": false,
      "music_app_consent_granted": true,
      "image_url": "/static/ipod_images/iPod18-Yellow.png",
      "storage": {
        "total_bytes": 15833497600,
        "used_bytes": 4512399360,
        "free_bytes": 11321098240,
        "audio_bytes": 3810293760,
        "video_bytes": 420000000,
        "photos_bytes": 150000000,
        "podcasts_bytes": 0,
        "other_bytes": 132105600,
        "formatted_total": "14.7 GB",
        "formatted_used": "4.2 GB",
        "formatted_free": "10.5 GB"
      }
    }
  ],
  "volumes_without_control": []
}
```

#### `GET /api/ipod/scan`
Endpoint ligero utilizado por el frontend al inicializar la vista, cambiar a la pestaña de iPod o pulsar el botón **Escanear**.

- **Response (200 OK)**:
```json
{
  "state": "ready",
  "ipods": [
    {
      "mount": "/Volumes/IPOD",
      "ipod_name": "iPod Nano 7th Gen",
      "model_family": "iPod Nano",
      "generation": "7th Gen",
      "color": "Yellow",
      "capacity": "16GB",
      "firewire_guid": "000a27002014abcd",
      "checksum": "HASHAB",
      "serial": "DCYJV000F4M4",
      "image_url": "/static/ipod_images/iPod18-Yellow.png",
      "storage": { ... }
    }
  ],
  "volumes_without_control": []
}
```

#### `GET /api/ipod/storage`
Devuelve el desglose en tiempo real del uso de almacenamiento del iPod montado (`shutil.disk_usage` + escaneo de tipos de archivos).

- **Response (200 OK)**:
```json
{
  "total_bytes": 15833497600,
  "used_bytes": 4512399360,
  "free_bytes": 11321098240,
  "audio_bytes": 3810293760,
  "video_bytes": 420000000,
  "photos_bytes": 150000000,
  "podcasts_bytes": 0,
  "other_bytes": 132105600,
  "formatted_total": "14.7 GB",
  "formatted_used": "4.2 GB",
  "formatted_free": "10.5 GB"
}
```

#### `POST /api/ipod/eject`
Desmonta y expulsa de forma segura el volumen del iPod para evitar corrupción de la tabla de asignación de archivos o SQLite.

- **Request Body (opcional)**:
```json
{
  "force": false
}
```
- **Response (200 OK)**:
```json
{
  "ejected": true,
  "message": "Volumen /Volumes/IPOD desmontado exitosamente."
}
```

---

### 2.2 Música y Canciones

#### `GET /api/ipod/tracks`
Lee y retorna todas las canciones catalogadas en el archivo `iTunesCDB` y la base de datos `Library.itdb`.

- **Response (200 OK)**:
```json
{
  "guid": "000a27002014abcd",
  "tracks_count": 25,
  "tracks": [
    {
      "title": "Midnight City",
      "artist": "M83",
      "album": "Hurry Up, We're Dreaming",
      "album_artist": "M83",
      "genre": "Synthpop",
      "composer": "Anthony Gonzalez",
      "year": 2011,
      "track_number": 2,
      "disc_number": 1,
      "bitrate": 320,
      "length_ms": 243000,
      "size_bytes": 9720000,
      "filetype": "mp3",
      "play_count": 14,
      "rating": 80,
      "location": ":iPod_Control:Music:F01:ABCD.mp3",
      "db_track_id": 1024
    }
  ]
}
```

---

### 2.3 Playlists

#### `GET /api/ipod/playlists`
Retorna las listas de reproducción existentes en el dispositivo.

- **Response (200 OK)**:
```json
{
  "playlists": [
    {
      "title": "iPod",
      "is_master": true,
      "count": 25
    },
    {
      "title": "Running Mix",
      "is_master": false,
      "count": 12
    }
  ],
  "count": 2
}
```

#### `POST /api/ipod/playlists/create`
Crea una nueva playlist vacía en la base de datos del iPod.

- **Request Body**:
```json
{
  "name": "Gym 2026"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "name": "Gym 2026",
  "message": "Playlist 'Gym 2026' creada."
}
```

#### `POST /api/ipod/playlists/import`
Importa una playlist desde la biblioteca local de Cicada o Spotify.

- **Request Body**:
```json
{
  "source_name": "Descargas Recientes",
  "tracks": [ ... ]
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "name": "Descargas Recientes",
  "tracks_count": 10,
  "message": "Playlist 'Descargas Recientes' importada."
}
```

---

### 2.4 Multimedia: Fotos y Videos

#### `GET /api/ipod/photos`
Lista los álbumes y fotografías sincronizadas en el iPod.

- **Response (200 OK)**:
```json
{
  "photos": [
    {
      "id": "photo_1",
      "title": "Vacaciones 2025",
      "date": "15/07/2025",
      "size": 2400000,
      "url": "/api/ipod/photos/photo_1/thumb"
    }
  ],
  "count": 1
}
```

#### `DELETE /api/ipod/photos/{photo_id}`
Elimina una foto de la base de datos y del almacenamiento del iPod.

- **Response (200 OK)**:
```json
{
  "success": true,
  "id": "photo_1"
}
```

#### `GET /api/ipod/videos`
Lista los videos (películas, videos musicales) presentes en el iPod.

- **Response (200 OK)**:
```json
{
  "videos": [
    {
      "id": "video_1",
      "title": "Concierto en Vivo",
      "resolution": "720x480",
      "duration_ms": 360000,
      "size": 85000000,
      "thumb": "/api/ipod/videos/video_1/thumb"
    }
  ],
  "count": 1
}
```

#### `DELETE /api/ipod/videos/{video_id}`
Elimina un video del dispositivo.

- **Response (200 OK)**:
```json
{
  "success": true,
  "id": "video_1"
}
```

---

### 2.5 Spoken Word: Podcasts y Audiolibros

#### `GET /api/ipod/podcasts`
Lista los podcasts suscritos y sus episodios asociados.

- **Response (200 OK)**:
```json
{
  "podcasts": [
    {
      "id": "pod_1",
      "name": "Radio Ambulante",
      "feed_url": "https://feeds.example.com/radioambulante",
      "episodes": [
        {
          "title": "El rescate",
          "date": "10/08/2026",
          "duration_ms": 2400000,
          "file_size": 28000000
        }
      ]
    }
  ],
  "count": 1
}
```

#### `GET /api/ipod/audiobooks`
Lista los audiolibros organizados con sus capítulos.

- **Response (200 OK)**:
```json
{
  "audiobooks": [
    {
      "id": "ab_1",
      "title": "Cien Años de Soledad",
      "author": "Gabriel García Márquez",
      "chapters": [
        {
          "title": "Capítulo 1",
          "duration_ms": 1800000
        }
      ]
    }
  ],
  "count": 1
}
```

---

### 2.6 Sincronización Transaccional y Seguridad

#### `POST /api/ipod/plan`
Genera un plan dry-run en una carpeta de staging temporal fuera del dispositivo (`~/.cicada/staging/`), verificando artefactos, firmas y consistencia de tablas SQLite.

- **Request Body**:
```json
{
  "tracks": [ ... ],
  "master_playlist_name": "iPod"
}
```
- **Response (200 OK)**:
```json
{
  "guid": "000a27002014abcd",
  "tracks_count": 25,
  "consent_needed": false,
  "write_safe": true,
  "created_at": "2026-08-16T21:40:00Z",
  "plan_id": "c1f76d90-0982-411a-a12b-31d24c45a709",
  "artifacts_summary": {
    "iTunesCDB": 540672,
    "iTunes Library.itlp/Library.itdb": 1646592,
    "iTunes Library.itlp/Locations.itdb": 126976
  }
}
```

#### `POST /api/ipod/apply`
Aplica el plan dry-run sobre el iPod mediante la siguiente secuencia protegida:
1. Verificación de `write_guard`.
2. Creación automática de backup `.tar.zst` del estado previo.
3. Copia atómica de archivos de base de datos a `iPod_Control/iTunes/`.
4. Verificación post-commit de checksums y cabeceras.
5. En caso de cualquier error, **restauración automática (rollback)**.

- **Request Body**:
```json
{
  "plan_id": "c1f76d90-0982-411a-a12b-31d24c45a709",
  "consent_ack": true
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "backup_path": "~/.cicada/backups/ipod/000a27002014abcd/20260816_214000.tar.zst",
  "restored_from_backup": false,
  "first_write_committed": true,
  "tracks_written": 25,
  "error": null
}
```

#### `POST /api/ipod/backup` & `POST /api/ipod/restore`
- `POST /api/ipod/backup`: genera un snapshot manual de las bases (`full: false`) o del árbol completo (`full: true`).
- `POST /api/ipod/restore`: restaura un archivo `.tar.zst` sobre el iPod montado.

---

## 3. Matriz de Estados de la UI

| Estado del Dispositivo | Elementos Visibles en la UI | Acciones Habilitadas |
|---|---|---|
| `no_device` | Mensaje "No se ha detectado ningún iPod", botón Escanear permanente en cabecera | Solo `Escanear` |
| `no_ipod_control` | Mensaje de advertencia (Volumen sin estructura `iPod_Control`) | Solo `Escanear` |
| `ready` | Barra de almacenamiento completa, Imagen oficial del modelo y color, Sub-sidebar de 6 categorías, Toolbar de filtros y contenido | `Escanear`, `Eyectar`, `Sync`, `Backup`, Búsqueda, Filtros, Agregar, Eliminar |

---

## 4. Guía de Conexión para Próximas Fases

1. **Artwork (Fase 4)**: Vincular el endpoint `/api/ipod/artwork/{track_id}` con la generación de bloques `mhni`/`mhii` en `iPod_Control/Artwork/ArtworkDB`.
2. **Podcasts y Audiolibros (Fase 5)**: Conectar los módulos `cicada/ipod/db/writer/mhod_writer.py` (tipos MHOD 15 y 16) con el feed parser de podcasts.
3. **Fotos y Videos (Fase 6)**: Implementar el transcodificador y generador de thumbnails `Photo Database` para visualización en pantalla color del iPod.
4. **Cache-Busting Frontend**: Todos los archivos de script y estilos en `cicada/core/main.py` emplean el parámetro de versión `?v=2.0.0` para garantizar recargas instantáneas sin retención de caché obsoleta en el cliente.
