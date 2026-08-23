# Especificación Técnica de Endpoints y UI del Subsistema iPod — Cicada

Este documento define la arquitectura técnica, catálogo de endpoints REST, contratos de datos y ciclo de vida de la interfaz de usuario del iPod en Cicada.

---

## 1. Arquitectura General del Subsistema

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Frontend (Cicada UI)                          │
│   • Barra Superior: Metadatos, Almacenamiento, Acciones Rápidas        │
│   • Sub-Sidebar: 5 Categorías (Canciones, Playlists, Videos,           │
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

## 1.1 Estado de implementación (a 2026-08-19)

Este documento describe el **diseño objetivo**. El estado real del backend hoy:

| Endpoint | Estado |
|---|---|
| `GET /status`, `GET /scan` | ✅ Real — incluyen `image_url` + `storage` |
| `GET /storage` | ✅ Real — con caché de 60 s (no recorre el FS en cada llamada) |
| `GET /tracks`, `GET /playlists` | ✅ Real — lectura de la base |
| `GET /podcasts`, `GET /audiobooks` | ✅ Real (Fase 5c/6c) — lectura y agrupamiento de lo que ya hay en el dispositivo; incluye episodios de video-podcast; **no** gestión de feeds/suscripciones (ver §2.5) |
| `GET /videos` | ✅ Real (Fase 6c) — lista plana, sin `resolution` ni `thumb` (ver §2.4) |
| `DELETE /videos/{id}` | ✅ Real (Fase 6c) — mismo mecanismo genérico que `POST /track/remove` (Fase 3) |
| `POST /media/sync` | ✅ Real — `kind: "music"\|"podcast"\|"audiobook"\|"movie"\|"tv_show"\|"music_video"\|"video_podcast"` (Fase 5a/6a), extracción automática de capítulos embebidos (Fase 5b) |
| `POST /plan`, `POST /apply` | ✅ Real — coordinador transaccional (dry-run, backup, rollback) |
| `POST /backup`, `POST /restore`, `POST /eject` | ✅ Real |
| `GET/POST/DELETE /consent/{guid}` | ✅ Real |
| `POST /playlists/create`, `POST /playlists/import` | 🔴 **501 Not Implemented** — se harán vía `plan`/`apply` |

Fotos (`GET /photos`, `DELETE /photos/{id}`) **excluida del proyecto**, no
diferida — ver §2.4 y `docs/VENDORED.md` Paquete 9.

**Regla de honestidad:** ningún endpoint devuelve éxito falso. Lo no implementado responde **`501`** con `{"detail": {"code": "NOT_IMPLEMENTED"}}`; los placeholders de lectura devuelven `[]`. Los ejemplos de respuesta de más abajo para `/videos` son el **contrato futuro**, no lo que responden hoy — `/podcasts`/`/audiobooks` ya no son placeholder, ver §2.5 para el contrato real (distinto del que tenía este documento).

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

### 2.4 Multimedia: Videos

**Alcance (igual que §2.5):** "ya tengo el video, ponlo en el iPod" — sin
transcodificación (el archivo ya debe ser H.264 compatible) ni servido de
miniaturas por HTTP (`GET /artwork/{track_id}` tampoco existe todavía para
música — queda fuera del alcance de esta fase, mismo criterio que con el
arte de podcasts en 5c).

**Fotos — excluida del proyecto v1, no diferida.** El iPod Nano 7G sí
tiene app de Fotos (confirmado por hardware), y llegó a implementarse
completa (Etapas 6e-6j) y verificarse byte a byte contra un Photo
Database real de Apple/Música — pero la app del dispositivo nunca llegó
a mostrar el contenido, pese a 5 intentos de hardware y 7 líneas de
investigación distintas agotadas sin causa identificable (contenido del
Photo Database, formato `frpd` hermano, contadores de `iTunesPrefs.plist`,
coordinación de escritura con `iTunesCDB`, metadata de filesystem,
mecanismo de expulsión, contenido de píxeles de miniaturas — ninguna
resultó ser la causa). Se decidió remover el código en vez de dejarlo
diferido. Detalle completo de la investigación en `docs/VENDORED.md`
Paquete 9 (marcado como excluido, preservado como registro histórico).

#### `GET /api/ipod/videos`
✅ Real (Fase 6c). Lista **plana** (sin agrupar por película/serie) de
todo lo que ya está en el dispositivo con `media_type` de video
(`movie`/`tv_show`/`music_video`) — `video_podcast` no aparece aquí, ver
`GET /podcasts` en §2.5. Sin `resolution` (no hay forma de derivarla sin
`ffprobe`, dependencia que Cicada no tiene) ni `thumb` (necesitaría un
endpoint de servido de ArtworkDB inexistente hoy).

- **Response (200 OK)**:
```json
{
  "videos": [
    {
      "id": "8043271996812345678",
      "title": "Piloto",
      "kind": "tv_show",
      "duration_ms": 1500000,
      "size_bytes": 85000000,
      "show_name": "Mi Serie",
      "season_number": 1,
      "episode_number": 1
    }
  ],
  "count": 1
}
```
`id` es el `db_track_id` (64 bits) como string — mismo motivo que en
`GET /tracks`: como `Number` de JS pierde precisión en la mayoría de los
valores.

#### `DELETE /api/ipod/videos/{video_id}`
✅ Real (Fase 6c). Borra la pista de la base y su archivo de audio —
mismo mecanismo genérico que `POST /track/remove` (Fase 3), sin importar
`media_type`; este endpoint solo traduce el `id` de la URL.

- **Response (200 OK)**: forma de `ApplyResponse` (igual que el resto de
  operaciones transaccionales, no un `{"success", "id"}` reducido):
```json
{
  "success": true,
  "backup_path": "/Users/.../Backups/...",
  "restored_from_backup": false,
  "first_write_committed": false,
  "tracks_written": 3,
  "error": null
}
```

---

### 2.5 Spoken Word: Podcasts y Audiolibros

**Alcance (Fase 5, corregido 2026-08-19):** Cicada no gestiona feeds RSS ni
suscripciones — es un gestor de biblioteca que además escribe al iPod, no
un cliente de podcasts. Estos endpoints leen lo que **ya está en el
dispositivo** (agrupado por programa/título) tras haberse añadido vía
`POST /media/sync` con `kind: "podcast"`/`"audiobook"`, o por haber
llegado con el dispositivo desde otra herramienta (iTunes/iOpenPod). No
hay concepto de suscripción, `feed_url`, ni descarga de episodios nuevos
— si el usuario quiere un episodio nuevo, lo agrega como cualquier otro
archivo de su biblioteca. Ver `docs/VENDORED.md` Paquete 8 para el
detalle de qué se excluyó de iOpenPod y por qué.

#### `GET /api/ipod/podcasts`
Lista los podcasts ya presentes en el dispositivo, agrupados por programa
(`Album`, con fallback a `Artist`). Incluye episodios `video_podcast`
(cerrado en Fase 6a) junto con los de audio — son episodios del mismo
programa; un video-podcast no aparece en `GET /videos` (§2.4) para no
duplicar la pista en dos categorías del frontend.

- **Response (200 OK)**:
```json
{
  "podcasts": [
    {
      "id": "radio-ambulante",
      "name": "Radio Ambulante",
      "episodes": [
        {
          "title": "El rescate",
          "date_added": 1786406400,
          "duration_ms": 2400000,
          "file_size": 28000000
        }
      ]
    }
  ],
  "count": 1
}
```
`date_added` es un timestamp Unix crudo (igual que el resto de campos de
fecha en `TrackSchema`) — el frontend lo formatea con
`toLocaleDateString()`, no hay un formato de fecha fijo en el backend.

#### `GET /api/ipod/audiobooks`
Lista los audiolibros ya presentes en el dispositivo, agrupados por título
(`Album`, con fallback a `Artist`). Un audiolibro real puede existir de
dos formas en un iTunesDB, y ambas se soportan:
- **Un solo archivo con capítulos embebidos** (MHOD 17 — lo que produce
  Cicada al añadir un `.m4b`/`.mp3` con capítulos, Fase 5b): los
  capítulos se expanden a partir de `chapter_data`, con la duración de
  cada uno calculada por diferencia entre `startpos` consecutivos (el
  formato del iTunesDB solo guarda la posición de inicio).
- **Varias pistas bajo el mismo álbum** (formato multi-pista de
  iTunes/iOpenPod): cada pista es un capítulo, ordenadas por
  `track_number`.

- **Response (200 OK)**:
```json
{
  "audiobooks": [
    {
      "id": "cien-anos-de-soledad",
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
2. **Podcasts y Audiolibros (Fase 5) — hecho, 2026-08-19.** No hubo feed parser que conectar: Cicada no gestiona feeds RSS (decisión de alcance explícita, ver §2.5 y `docs/VENDORED.md` Paquete 8). Se implementó `kind`/`category` en `POST /media/sync` (5a), extracción de capítulos embebidos de archivos ya locales (5b), y lectura real agrupada en `GET /podcasts`/`/audiobooks` (5c) — los tipos MHOD 15/16/17 (`cicada/ipod/db/writer/mhod_writer.py`) ya estaban vendorizados desde antes de Fase 5 y no necesitaron cambios.
3. **Video (Fase 6a-6c) — hecho, 2026-08-19; confirmado en hardware real, 2026-08-20.** Sin transcodificador: Cicada no transcodifica nada, ni audio ni video (el `transcoder.py` que sugería el código muerto de Fase 5 no existe en el repo) — el archivo ya debe ser H.264 compatible, misma filosofía que audio. `kind` extendido a `movie`/`tv_show`/`music_video`/`video_podcast` en `POST /media/sync` (6a); el arte embebido de video reutiliza el pipeline de artwork de Fase 4a-4d sin cambios (6b, verificado, no construido); `GET /videos`/`DELETE /videos/{id}` reales (6c). Prueba de fuego con archivo real, round-trip verificado en ambas capas del dispositivo (iTunesCDB + SQLite `Library.itdb`) y reproducción confirmada por el usuario en el iPod. **Fotos excluida del proyecto v1** (2026-08-22) tras 5 intentos de hardware y 7 líneas de investigación agotadas sin causa identificable — no diferida, removida: código exclusivo borrado, ver `docs/VENDORED.md` Paquete 9 y `docs/IPOD_INTEGRATION.md`.
4. **Cache-Busting Frontend**: Todos los archivos de script y estilos en `cicada/core/main.py` emplean el parámetro de versión `?v=2.0.0` para garantizar recargas instantáneas sin retención de caché obsoleta en el cliente.
