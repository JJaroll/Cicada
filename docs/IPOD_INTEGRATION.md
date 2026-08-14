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

### 0.3 Hashing — escritura VIABLE con una limitación conocida (Music.app)

> **Corrección (verificada contra hardware, Fase 1).** Nuestra firma HASHAB (vía el WASM
> de dstaley/hashab que usa iOpenPod) reproduce **byte a byte** las firmas escritas por
> **iOpenPod**, pero **NO** las de **iTunes/Apple** (contra una base real de iTunes,
> mismo GUID, `verify_hashab` falla; 120 variantes de SHA1 no la reproducen; el WASM
> tiene 25 posiciones de bytes invariantes y Apple viola 23 → otra clave del white-box,
> o algoritmo distinto).
>
> **Dos hechos distintos, verificados con hardware — no confundirlos:**
> 1. **El firmware del iPod ACEPTA AMBAS firmas.** Confirmado: el dispositivo reproduce
>    en pantalla y suena la música cuya base escribió iOpenPod. Si el firmware exigiera
>    la firma de Apple, mostraría biblioteca vacía.
> 2. **Music.app solo acepta la firma de Apple.** Al conectar un iPod cuya base fue
>    escrita por Cicada/iOpenPod, Music lo considera no reconocido y pide **restaurarlo**
>    (irreversible: borra la biblioteca).
>
> **Go/no-go de Fase 2 = ¿funciona el dispositivo? Sí → GO.** El criterio es que el iPod
> reproduzca lo que escribimos, no que Music lo apruebe. **La escritura HASHAB es viable**,
> con esta **limitación conocida: rompe la compatibilidad con Music.app de forma
> irreversible** (revertir requiere restaurar el iPod desde Music/Finder).
>
> **Requisito de Fase 2:** advertir al usuario **antes de la primera escritura**, de forma
> explícita: *"Cicada escribirá una firma que el dispositivo acepta pero Music.app no
> reconocerá. Revertirlo requiere restaurar el iPod."*
>
> **Investigación paralela (no bloqueante):** una segunda base escrita por iTunes en el
> mismo dispositivo con contenido distinto (otro SHA1) permitiría desambiguar "clave" vs
> "algoritmo" — y, si es clave, podría dar compatibilidad total con Apple más adelante.

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
- [ ] Endpoints `GET /ipod/device`, `/ipod/tracks`, `/ipod/playlists`.
- [ ] UI: biblioteca del iPod en la sección existente.

**Aceptación**: Cicada lista tus canciones y playlists reales, y `verify_hashab()`
devuelve `True` para el `iTunesCDB` original del dispositivo.

### Fase 2 — Escritura de música

- [x] Vendorizar paquetes 4–5, incluido el WASM (`calcHashAB.wasm`).
- [x] `dispatch.py` / `capabilities.py`: selección de esquema de hash por capacidad.
- [x] `write_guard.py`: bloquea si el fs no es escribible o falta alguna capacidad.
- [x] Escritura coordinada `iTunesCDB` (`build_itunescdb`) + `.itdb` + `.cbk` (`build_sqlite_databases`).
- [x] `plan.py` y `apply.py` con backup automático previo, gate de advertencia Music.app y rollback ante error.
- [ ] UI / API: endpoints FastAPI y dry-run obligatorio antes de aplicar.

**Aceptación**: añades una canción desde Cicada, expulsas, y se reproduce en el iPod con
metadata correcta.

### Fase 3 — Playlists y bidireccional

- [ ] Playlists estándar; smart playlists preservadas sin interpretar en v1
      (conserva los bytes crudos y reescríbelos idénticos).
- [ ] Lectura de contadores desde `Dynamic.itdb`, delta contra `playback_state`.
- [ ] Resolución de conflictos en la UI. Nunca silenciosa.

### Fase 4 — Artwork
### Fase 5 — Podcasts y audiolibros
### Fase 6 — Fotos y video

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