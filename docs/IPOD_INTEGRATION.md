# Cicada — Integración con iPod

Spec de implementación, basado en inspección del dispositivo real y del código de iOpenPod.

- **Proyecto**: Cicada (GPLv3, Python 3.12.3, FastAPI)
- **Origen del código**: [iOpenPod](https://github.com/TheRealSavi/iOpenPod) (MIT)
- **Dispositivo de desarrollo**: iPod nano 7G, FAT32, montado en `/Volumes/IPOD`
- **Alcance v1**: música y playlists, sync bidireccional, selección manual

---

## 0. Hallazgos que definen el diseño



### 0.1 El Nano 7G usa arquitectura dual

Confirmado en el dispositivo:

```
iPod_Control/iTunes/
├── iTunesCDB                      528 KB   ← lo lee iTunes/el host
└── iTunes Library.itlp/
    ├── Library.itdb              1.6 MB    ← SQLite, lo lee el dispositivo
    ├── Locations.itdb            126 KB
    ├── Locations.itdb.cbk        2.5 KB    ← checksum de Locations
    ├── Dynamic.itdb               72 KB    ← play counts, ratings, estado
    ├── Extras.itdb                16 KB
    └── Genius.itdb               852 KB
```

**Escribir solo el `iTunesCDB` no sirve**: el dispositivo lee las bases SQLite. Toda
escritura debe actualizar ambas capas de forma consistente, más el `.cbk`.

`Dynamic.itdb` es la clave del sync bidireccional en este modelo: ahí viven play counts
y ratings, no en un archivo `Play Counts` separado como en los iPod clásicos.

### 0.2 Identificación de modelo

`SysInfoExtended` de este dispositivo **no contiene `ModelNumStr`**. Las claves relevantes son:

| Clave | Uso |
|---|---|
| `FireWireGUID` | Insumo del hash de firma. 8 bytes, hexadecimal. Imprescindible. |
| `FamilyID` | Identificador de modelo en dispositivos nuevos. |
| `ECID` | Identificador único de chip. |
| `DBVersion` | Versión del formato de base de datos. |
| `MaxTracks` | Límite de pistas del dispositivo. |
| `MaxFileSizeInGB` | Límite por archivo. |
| `PlaylistFoldersSupported` | Capacidad. |
| `DistinguishedSmartPlaylistsSupported` | Capacidad. |
| `MoviesSupported`, `HomeVideosSupported`, `PhotoEventsSupported` | Capacidades. |
| `MaxThumbFileSize` | Relevante para artwork. |

**Consecuencia de diseño**: en vez de una tabla estática modelo→capacidades, **lee las
capacidades del propio dispositivo**. La tabla estática queda solo como fallback para
modelos antiguos cuyo `SysInfoExtended` sea pobre.

En modelos nuevos, `SysInfoExtended` se genera consultando el dispositivo por USB
(SCSI vía `pyusb`). iOpenPod cachea el resultado en `iPod_Control/Device/iOpenPodSysInfoAuthority`.

**Cicada NO cachea en el dispositivo.** iOpenPod escribe su `iOpenPodSysInfoAuthority`
dentro de `iPod_Control/Device/`, y eso hace que Music.app considere el iPod corrupto y
pida restaurarlo. Cicada no debe ensuciar el volumen: el caché va **fuera del dispositivo**,
en `~/.cicada/` (p. ej. `~/.cicada/sysinfo/<guid>.json`), indexado por GUID. El nombre
`CicadaSysInfoAuthority` se conserva solo como identificador lógico del caché, no como
archivo en el iPod.

**Esta era una hipótesis de diseño cuando se escribió; §0.3 la confirma con hardware
real** (2026-08-19): limpiar `iOpenPodSysInfoAuthority` + los `.backup` de iOpenPod, sin
tocar `mhbd` ni SQLite ni restaurar nada, basta para que Music.app vuelva a reconocer el
dispositivo — la arquitectura de este párrafo ya evitaba la causa real, no solo un síntoma.

### 0.3 Hashing — escritura VIABLE, y la incompatibilidad con Music.app NO viene de la firma

> **Corrección definitiva (verificada contra hardware real, 2026-08-19) — reemplaza la
> hipótesis anterior de esta sección, que quedaba registrada aquí por trazabilidad.**
>
> Se investigó a fondo un hallazgo que contradecía la primera versión de esta sección:
> con Cicada, Music.app **sigue reconociendo el iPod** tras escribir; con iOpenPod, se
> rompe — pese a que ambos comparten el mismo WASM HASHAB. La causa **no es la firma**:
>
> 1. **`mhbd` y las tablas SQLite (`Library.itdb` completo) son idénticos byte a byte**
>    entre Cicada e iOpenPod para el mismo input — comparación directa, no por hash:
>    de 7314 bytes del `mhbd`, solo 32 difieren, y esos 32 se explican exactamente por
>    las 4 únicas llamadas a `random.getrandbits(64)` del árbol de escritura (IDs
>    internos de álbum/artista/track/playlist, no determinísticos por diseño en ambos
>    codebases). Las 20 tablas de `Library.itdb`, fila por fila, campo por campo:
>    coincidencia total. **La firma HASHAB nunca fue la variable — nunca lo fue, ni
>    siquiera en la versión anterior de esta sección, que asumía que "misma firma →
>    mismo resultado con Music" sin haberlo aislado.**
> 2. **La causa real está fuera del `iTunesCDB`**: iOpenPod escribe
>    `iPod_Control/Device/iOpenPodSysInfoAuthority` (JSON de procedencia de la
>    identidad del dispositivo) y, como parte de esa reconciliación, **reescribe
>    `SysInfo`/`SysInfoExtended` en el dispositivo** — confirmado leyendo el archivo
>    real en un iPod con residuo de una sesión anterior de iOpenPod, con
>    `SysInfoExtended` reescrito en el mismo instante que el archivo de autoridad.
>    Además deja `.backup` de los 7 archivos de base de datos
>    (`iTunesCDB.backup`, `Library.itdb.backup`, etc. — mecanismo de backup-en-sitio
>    de `write_itunesdb`/`write_sqlite_databases`). Todo esto vive fuera de lo que
>    Apple espera encontrar en esos archivos, y es lo que hace que Music.app trate el
>    dispositivo como no reconocido.
> 3. **Prueba directa, sin restaurar el iPod**: sobre un dispositivo con este residuo
>    real de iOpenPod (que Music.app ya rechazaba), se ejecutó `cicada ipod
>    clean-foreign` (borra `iOpenPodSysInfoAuthority`) más el borrado manual de los 7
>    `.backup` — **sin tocar `mhbd` ni las tablas SQLite, sin restaurar nada** — y
>    Music.app volvió a reconocer el dispositivo completo, con toda la biblioteca.
>    Confirmación directa del mecanismo, no solo correlación.
>
> **El firmware del iPod acepta la firma HASHAB de Cicada/iOpenPod** (sigue siendo
> cierto, sin cambios: el dispositivo reproduce lo que escribimos). Lo que cambia es
> el motivo por el que Music.app a veces no lo acepta — nunca fue la firma.
>
> **Implicación para Cicada: no reproduce este problema, y no requirió ningún cambio de
> código para lograrlo.** `cicada/ipod/device/authority.py` ya existía con esta
> arquitectura desde una fase anterior del proyecto — su propio docstring ya documentaba
> la hipótesis ("iOpenPod... reescribe SysInfo/SysInfoExtended... Eso hace que Music.app
> considere el iPod corrupto") y ya la evitaba: la autoridad de Cicada vive enteramente
> en `~/.cicada/sysinfo/<hash(guid)>/`, **nunca escribe `SysInfo`/`SysInfoExtended` en el
> volumen**, y nunca genera `.backup` en sitio (el camino activo de escritura,
> `build_itunescdb`/`build_sqlite_databases`, no invoca en ningún punto las funciones
> vendorizadas-pero-no-usadas que sí lo harían). **Verificado en hardware real, no solo
> por inspección de código.**
>
> **Requisito de consentimiento — se mantiene, pero con el motivo corregido.** El gate
> de `consent.py` (`ConsentRequiredError`, aviso antes de la primera escritura) **no se
> elimina**: la firma HASHAB de Cicada sigue sin ser la de Apple, y eso en sí mismo sigue
> siendo una divergencia real del formato, aunque ya sabemos que no es lo que rompe
> Music.app. El valor del gate pasa de "advertir de una incompatibilidad garantizada"
> a "advertir de una divergencia de firma cuyo impacto real en Music.app depende de que
> el dispositivo no cargue además residuo de terceros" — más matizado, pero sigue
> siendo información que el usuario debe poder ver antes de escribir. Sin cambios de
> código pendientes aquí.
>
> **Advertencia inversa (nueva, más útil que la anterior) — el riesgo real está en
> terceros, no en Cicada.** Si el dispositivo tiene residuo de iOpenPod (o de cualquier
> otra herramienta que reescriba `SysInfo`/deje `.backup` en sitio) de una sesión previa,
> Music.app puede rechazarlo **aunque Cicada nunca haya escrito nada problemático** — el
> caso real de esta investigación. `cicada ipod clean-foreign` ahora cubre **ambas**
> categorías: `iOpenPodSysInfoAuthority` y los 7 `.backup` ajenos conocidos
> (`iTunesCDB.backup`, `{Library,Locations,Dynamic,Extras,Genius}.itdb.backup`,
> `Locations.itdb.cbk.backup`) — extendido el 2026-08-19, ya no requiere borrado manual.
> Cambio de firma explícito: devuelve la lista de rutas eliminadas, no un booleano.
> Seguro por diseño y por test: `create_plan()` real (no un grep) se verifica que nunca
> produce esos 7 nombres antes de confiar en que borrarlos automáticamente no toque algo
> propio. Detalle, sanity check de mutación y la nota de por qué el nombre de la función
> no cambió en `docs/VENDORED.md`, Paquete 2.

El firmware verifica una firma en el header `mhbd` del `iTunesCDB`. Sin ella, el iPod
muestra la biblioteca vacía aunque los archivos estén presentes.

Los tres esquemas son la misma operación conceptual sobre offsets distintos:

| Esquema | Tamaño | Offset en `mhbd` | Modelos |
|---|---|---|---|
| HASH58 | 20 bytes | `0x58` | Classic 6G, Nano 3G/4G |
| HASH72 | 46 bytes | `0x72` | Classic 2009, Nano 5G |
| HASHAB | 57 bytes | `0xAB` | **Nano 6G/7G** ← el dispositivo de desarrollo |

Los tres toman el `FireWireGUID` como insumo. Diseña un dispatcher único con selección
por capacidad del dispositivo, no tres rutas separadas.

**Corrección verificada contra el dispositivo real (Fase 1, Etapa 3b):** en el Nano 7G
el SHA1 que alimenta HASHAB se computa sobre los bytes del **iTunesCDB comprimido tal
cual están en disco**, NO sobre el iTunesDB descomprimido. Con `hashing_scheme`(0x30)=4,
los campos db_id/unk_0x32/hash58/hash72/hashab a cero, y el GUID en orden natural
(`bytes.fromhex`, sin reversión). `verify_hashab` reproduce la firma existente byte a
byte. **Implicación para el writer (Fase 2): comprimir primero, luego firmar sobre el
comprimido** — no firmar-y-comprimir.

**HASHAB y su licencia** — verificado, no hay obstáculo:

- iOpenPod lo implementa ejecutando `calcHashAB.wasm` mediante `wasmtime-py`.
- Ese WASM viene de [`dstaley/hashab`](https://github.com/dstaley/hashab), bajo
  **The Unlicense** (dominio público).
- Es una reimplementación **clean-room** del algoritmo de white-box AES de Apple, no
  código desensamblado.

Por tanto **se vendoriza sin reparos** y `wasmtime` es dependencia obligatoria, no opcional.
Ejecutar el algoritmo en WASM es además lo que da soporte a Apple Silicon sin compilar
binarios nativos, a diferencia del viejo `libhashab` que exigía x86 de 32 bits.

Fases internas del algoritmo, para referencia: compresión CBC-MAC del UUID con AES →
expansión de material de clave (44 → 190 bytes) → generación de buffer inicial
(190 → 16 bytes) → cifrado white-box AES-128.

### 0.4 Licencias

MIT → GPLv3 es válido en esa dirección. Vendoriza libremente conservando la atribución.
Como no se contribuirá upstream, no hace falta doble licencia: `cicada/ipod/` es GPLv3
como el resto del proyecto.

`cicada/ipod/NOTICE`:

```
Portions of this module are derived from iOpenPod
Copyright (c) John Gibbons — MIT License
https://github.com/TheRealSavi/iOpenPod

calcHashAB.wasm is from dstaley/hashab — The Unlicense (public domain)
https://github.com/dstaley/hashab
Clean-room reimplementation of Apple's white-box AES signing algorithm.

Incorporated into Cicada and redistributed under GPLv3.
```

### 0.5 Filesystem

Dispositivo montado como `msdos` (FAT32). Lectura y escritura nativas en macOS, Linux y
Windows sin drivers adicionales. El requisito de portabilidad no tiene obstáculo.

**Trampa de macOS sobre FAT32**: el sistema crea forks de recursos con prefijo `._`
(`._SysInfo`, `._SysInfoExtended`). Todo escaneo de directorios debe filtrarlos, o el
parser recibirá basura. Filtra también `.DS_Store`, `.Spotlight-V100`, `.fseventsd`,
`.Trashes`.

---

## 1. Qué vendorizar

El núcleo de iOpenPod está limpio de Qt salvo seis archivos, todos en la capa de
orquestación que Cicada reemplaza:

```
Contaminados con Qt (NO copiar, reimplementar sobre FastAPI):
  application/bootstrap.py
  application/controllers.py
  application/runtime.py
  application/jobs.py
  application/sync_session.py
  podcasts/models.py
```

**Orden de copia**, de menor a mayor dependencia:

| # | Paquete origen | Destino en Cicada | Notas |
|---|---|---|---|
| 1 | `itunesdb_shared/` | `cicada/ipod/db/shared/` | Constantes y definiciones. Sin dependencias. |
| 2 | `device/` | `cicada/ipod/device/` | `scanner`, `models`, `capabilities`, `checksum`, `write_guard`, `durability`, `info`, `artwork_presets`. |
| 3 | `itunesdb_parser/` | `cicada/ipod/db/parser/` | Lectura. Aquí termina la Fase 1. |
| 4 | `itunesdb_writer/` | `cicada/ipod/db/writer/` | Incluye `hash58.py`, `hash72.py`, `hashab.py` y `wasm/calcHashAB.wasm`. |
| 5 | `sqlitedb_writer/` | `cicada/ipod/db/sqlite/` | La capa que lee el dispositivo. Incluye `cbk_writer.py`. |
| 6 | `sync/` | `cicada/ipod/sync/` | `spl_evaluator`, `itunes_prefs`, `_db_io`. |
| — | `podcasts/` | — | Aplazado a Fase 5. |

**Regla**: copia un paquete, escribe sus tests, verifica contra el iPod real, y solo
entonces pasa al siguiente. Son ~84k líneas: copiarlas en bloque es garantía de terminar
con código que no puedes mantener.

Registra en `docs/VENDORED.md` el commit de origen de cada archivo.

---

## 2. Estructura de destino

```
cicada/
├── core/                      # código actual, migrado desde la raíz
├── ipod/
│   ├── NOTICE
│   ├── util/
│   │   └── fsfilter.py        # filtro de artefactos macOS/FAT32
│   ├── device/
│   │   ├── scanner.py         # detección de volúmenes
│   │   ├── sysinfo.py         # plist XML/binario + SCSI vía pyusb
│   │   ├── authority.py       # caché CicadaSysInfoAuthority (en ~/.cicada/, NO en el iPod)
│   │   ├── capabilities.py    # lee capacidades del dispositivo
│   │   ├── write_guard.py     # bloqueo por fs/modelo/capacidad
│   │   ├── durability.py      # flush y expulsión segura por SO
│   │   └── backup.py          # snapshot de iPod_Control
│   ├── db/
│   │   ├── shared/
│   │   ├── parser/
│   │   ├── writer/
│   │   │   ├── dispatch.py    # selecciona esquema por capacidad
│   │   │   ├── hash58.py
│   │   │   ├── hash72.py
│   │   │   ├── hashab.py
│   │   │   └── wasm/calcHashAB.wasm
│   │   └── sqlite/
│   │       └── cbk_writer.py
│   ├── media/
│   │   ├── compat.py
│   │   ├── transcode.py       # FFmpeg
│   │   └── layout.py          # F00–F49
│   ├── sync/
│   │   ├── state.py           # SQLite propio de Cicada
│   │   ├── plan.py
│   │   └── apply.py
│   └── api.py                 # APIRouter FastAPI
└── ui/
```

## 3. Dependencias nuevas

De las 14 de iOpenPod, Cicada necesita:

| Paquete | Motivo | ¿Ya en Cicada? |
|---|---|---|
| `mutagen` | Metadata | Sí |
| `pillow` | Artwork | Probablemente |
| `pyusb` | SCSI para SysInfoExtended | No |
| `pycryptodome` | Hashing | No |
| `wasmtime` | HASHAB — **obligatorio** para Nano 6G/7G | No |
| `numpy` | Procesamiento de artwork | Verificar |
| `python-dateutil`, `tzdata` | Timestamps del iPod | No |

No se necesitan: `pyqt6` (GUI), `feedparser` (podcasts, Fase 5), `tqdm`, `requests`,
`certifi`, `packaging`.

---

## 4. Estado persistente

Cicada no tiene DB. El módulo iPod requiere SQLite propio en `~/.cicada/ipod.db`:

```sql
CREATE TABLE devices (
    guid TEXT PRIMARY KEY, family_id TEXT, ecid TEXT,
    name TEXT, first_seen INTEGER, last_seen INTEGER
);

CREATE TABLE track_map (
    guid TEXT, ipod_dbid INTEGER,
    local_path TEXT NOT NULL, local_mtime REAL, local_size INTEGER,
    content_hash TEXT, ipod_relpath TEXT NOT NULL,
    transcoded INTEGER, source_codec TEXT, synced_at INTEGER,
    PRIMARY KEY (guid, ipod_dbid)
);
CREATE INDEX idx_track_map_local ON track_map(guid, local_path);

CREATE TABLE playback_state (
    guid TEXT, ipod_dbid INTEGER,
    known_play_count INTEGER, known_rating INTEGER, known_last_played INTEGER,
    PRIMARY KEY (guid, ipod_dbid)
);

CREATE TABLE transcode_cache (
    source_hash TEXT, target_codec TEXT, target_params TEXT,
    cached_path TEXT, created_at INTEGER,
    PRIMARY KEY (source_hash, target_codec, target_params)
);
```

El sync bidireccional en Nano 7G lee los contadores desde `Dynamic.itdb` y calcula el
delta contra `playback_state`.

---

## 5. Roadmap

### Fase 0 — Seguridad y fixtures

- [x] `util/fsfilter.py`: filtro de artefactos macOS/FAT32, con tests. Lo usará todo
      escaneo de directorios del módulo.
- [x] `device/write_guard.py`: **antes que cualquier código que toque el volumen**.
      `resolve_mount()` revalida el montaje en cada operación; `assert_within_ipod_control()`
      rechaza rutas fuera de `<mount>/iPod_Control/`; prohibición explícita de borrado
      recursivo de `iPod_Control/` y de `iPod_Control/iTunes/`.
- [x] `device/backup.py`: backup y restore, siempre a través de `write_guard`. Dos modos:
      `--db-only` (por defecto, solo `iTunes/` y `Device/`, ~4 MB) y `--full` (árbol
      completo con `Music/`). Salida `.tar.zst` en `~/.cicada/backups/ipod/<guid>/`,
      con verificación de integridad y rotación de los últimos 20.
- [x] CLI: `cicada ipod backup`, `cicada ipod restore <archivo>`, `cicada ipod list-backups`.
- [x] Fixture en `tests/fixtures/nano7g/`: copia del árbol con los `.itdb`, `iTunesCDB` y
      `SysInfoExtended` íntegros, y los audios truncados a 4 KB.
- [x] Migración del código actual de la raíz a `cicada/core/`.
- [x] cicada/ipod/device/write_guard.py debe existir DESDE EL PRIMER COMMIT.
      Ninguna operación destructiva sobre el volumen del iPod sin pasar por él.
      Incluye protección contra borrado accidental de iPod_Control.

**Aceptación**: haces backup, borras deliberadamente una playlist desde iOpenPod,
restauras, y el iPod vuelve a su estado anterior. Verificado en el dispositivo real.

### Fase 1 — Lectura

- [x] Vendorizar paquetes 1–3.
- [x] `scanner.py` / `device_info.py` funcionando en macOS, Linux y Windows. Distingue **tres
      estados** (`ready`, `no_ipod_control`, `no_device`).
- [x] `sysinfo.py` con cascada: plist XML → plist binario → SCSI/pyusb (y IOKit en macOS) → `SysInfo` plano.
- [x] Parseo de `iTunesCDB` y de `Library.itdb`.
- [x] Verificación del hash contra el `iTunesCDB` existente.
- [x] Endpoints de lectura: `GET /api/ipod/{status,scan,tracks,playlists,storage}` (`api.py`).
- [x] UI: sección iPod con info del dispositivo (imagen por modelo/color, capacidad),
      desglose de almacenamiento y biblioteca (canciones + playlists).

**Aceptación**: Cicada lista tus canciones y playlists reales, y `verify_hashab()`
devuelve `True` para el `iTunesCDB` original del dispositivo.

### Fase 2 — Escritura de música

- [x] Vendorizar paquetes 4–5, incluido el WASM (`calcHashAB.wasm`).
- [x] `dispatch.py` / `capabilities.py`: selección de esquema de hash por capacidad.
- [x] `write_guard.py`: bloquea si el fs no es escribible o falta alguna capacidad.
- [x] Escritura coordinada `iTunesCDB` (`build_itunescdb`) + `.itdb` + `.cbk` (`build_sqlite_databases`).
- [x] `plan.py` y `apply.py` con backup automático previo, gate de advertencia Music.app y rollback ante error.
- [x] UI / API: endpoints FastAPI (`api.py`) y comandos CLI (`cli.py`) con dry-run obligatorio antes de aplicar.
- [x] UI: botón "Escribir en el iPod" cableado al flujo plan → dry-run → consentimiento Music.app → apply
      (reescribe la base con las pistas actuales; no hay copia de audio — la base asume audios ya presentes).
- [ ] **Aceptación en hardware pendiente**: el código de escritura aún NO se ha validado contra el Nano 7G real.

**Aceptación**: añades una canción desde Cicada, expulsas, y se reproduce en el iPod con
metadata correcta. Verificar además el round-trip de fechas (reproducir una canción antes de
escribir para capturar la zona horaria real del dispositivo).

### Fase 3 — Playlists y bidireccional

- [x] Playlists estándar; smart playlists preservadas sin interpretar en v1
      (conserva los bytes crudos y reescríbelos idénticos vía `playlists.py`).
- [x] Lectura de contadores desde `Dynamic.itdb` / `iTunesCDB`, delta contra `playback_state` (`bidirectional.py`).
      Conectado a la app vía `sync_playback_stats()` — `POST /api/ipod/sync/playback`
      y `cicada ipod sync-playback`; corre en segundo plano tras cada escaneo.
- [x] Persistencia local en SQLite `~/.cicada/ipod.db` (`state.py`).
- [x] Resolución de conflictos interactiva en UI. Único campo genuinamente
      conflictivo: el rating (play_count/skip_count se suman, timestamps toman
      `max()`). Tercer punto de dato (`local_playback_state`) + diff de tres vías
      (`conflicts.py::scan_for_conflicts`) para distinguir "cambió solo en el
      dispositivo" de "cambió en ambos lados y difieren" — nunca se resuelve un
      conflicto real en silencio. `GET/POST /api/ipod/conflicts[/resolve[-all]]`,
      calificar desde Cicada vía `POST /api/ipod/track/rate`, menú contextual
      "Calificar" y vista "Conflictos" en la sub-sidebar del iPod.

### Fase 4 — Artwork

Escritor de `ArtworkDB` + `.ithmb` (`artworkdb_writer` de iOpenPod, Paquete 7
en `VENDORED.md`). **Objetivo final: todos los modelos que soporta iOpenPod**
(varios formatos de píxel — RGB565_BE, RGB555, UYVY, JPEG — y tablas de
dimensiones por familia/generación). La entrega se trocea así para reducir
riesgo, empezando por un único caso real verificable contra hardware:

- [x] **4a** — Fuente de imagen: reusa el pipeline de carátula ya existente
      (`audio_processor.py` embebe, ahora `cicada/shared/artwork.py` extrae —
      compartido entre `core` y `ipod`, sin segundo sistema de descarga).
- [x] **4b** — Codec RGB565_LE + tipos (`cicada/ipod/db/artwork/`). Acepta
      cualquier `ArtworkFormat` pero rechaza formatos no-RGB565_LE en vez
      de adivinar (falla explícito hasta 4f).
- [x] **4c** — Escritor binario ArtworkDB + `.ithmb` (`cicada/ipod/db/artwork/
      {chunks,writer}.py`). Reescritura completa en cada sync (sin dedup ni
      preservación incremental — medido contra una biblioteca real de 954
      tracks: ~12s de coste total, no compensa la complejidad del dedup por
      ~3s de ahorro). Verificado con imágenes de prueba conocidas: pixel
      round-trip vía offset leído del propio ArtworkDB (no contadores
      internos), offsets exactos sin solape entre tracks, song_id/img_id
      correctos — ver detalle y sanity check (bug inyectado a propósito y
      detectado) en `docs/VENDORED.md`, Paquete 7.
- [x] **4d** — Coordinación con Fase 2: artwork se construye dentro de
      `create_plan()` antes de iTunesCDB/sqlite (consistencia por
      construcción), todo condicional a `Plan.artwork_touched` (staging,
      instalación, backup — nunca toca `Artwork/` si ningún track tiene
      fuente de imagen resoluble), `apply()` extiende su secuencia de
      instalación e incluye una verificación referencial post-commit
      (Fase E). Bug real encontrado y corregido: el backup de la primera
      escritura de artwork no cubría esa carpeta para rollback (no existía
      aún al tomarlo) — ver detalle en `docs/VENDORED.md`, Paquete 7.
      Verificado con un escenario forzado de dos syncs consecutivos
      (regresión de artwork_id_ref cerrada, con sanity check de mutación).
- [ ] **4e** — API/CLI/UI.
- **4f** — Generalización a otros modelos. Hallazgo: las 24 device families
      que Cicada modela usan RGB565_LE sin excepción para cover art — los
      demás formatos de píxel de iOpenPod son de fotos/TV-out (subsistema
      aparte) o de dispositivos (iPod touch/"Mobile") que Cicada no modela
      en ninguna capacidad. Detalle y esquema de verificación de tres
      niveles en `docs/VENDORED.md`, Paquete 7.
      - [x] **4f-1** — RGB565_LE activado para las 23 families restantes
            (antes solo Nano 7G). `chunks.py`/`writer.py` ya eran
            agnósticos del formato; el hardcodeo estaba en 3 puntos de
            `plan.py`/`apply.py`, ahora device-aware vía
            `device_info.capabilities.cover_art_formats`. Bug real
            encontrado y corregido antes de escribir código:
            `PreStateFingerprint` fingerprinteaba rutas fijas de Nano 7G
            para cualquier family — nunca detectaba deriva real en los
            `.ithmb` propios de otro dispositivo.
      - [x] **4f-2** — Auditoría contra `itdb_device.c` de libgpod
            (descargado y grepeado directo, no vía resumen — un intento de
            WebFetch fabricó un array de Nano 6G inexistente, descartado).
            12 de 13 families con `supports_artwork` confirmadas exactas
            (Classic incl. el reuso para 3G Nano, Nano 1-5G, iPod Video,
            4G photo/color). Nano 7G no está en libgpod pero tiene algo
            mejor: hardware real. Nano 6G queda en nivel 3 (no auditable:
            sus format_id no existen en libgpod) — detalle en
            `docs/VENDORED.md`, Paquete 7.
      - **4f-3** — RGB565_BE/RGB555 para iPod touch/"Mobile". Diferido con
            el mismo criterio que `cicada ipod add`: no se construye sin
            soporte real de esa familia de dispositivo primero.

**Alcance de 4a-4e: RGB565_LE, ahora en las 24 device families que Cicada
modela (antes solo Nano 7G) desde 4f-1.**

### Fase 5 — Podcasts y audiolibros
### Fase 6 — Fotos y video

> La UI ya expone las categorías de estas fases, pero los endpoints son **honestos**: la
> lectura (`/photos`, `/videos`, `/podcasts`, `/audiobooks`) devuelve lista vacía, y las
> operaciones de escritura/borrado (incluido `POST /playlists/{create,import}`) responden
> `501 Not Implemented`. Contrato futuro documentado en `ui-ipod.md`.

---

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Corromper la biblioteca del iPod | Backup automático antes de toda escritura; Fase 0 primero |
| 84k líneas de código ajeno sin entender | Copia paquete por paquete, con tests, en el orden dado |
| iOpenPod evoluciona y el fork diverge | `docs/VENDORED.md` con commits de origen |
| macOS ensucia el FAT32 con `._*` | Filtro compartido desde Fase 0 |
| Escritura parcial deja el iPod inconsistente | `apply.py` transaccional con rollback |
| El dispositivo se desmonta durante el uso normal | `resolve_mount()` revalida antes de cada operación; `apply.py` aborta limpiamente si desaparece a mitad de escritura |