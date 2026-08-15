# Código vendorizado

Registro de todo el código de terceros incorporado a `cicada/ipod/`, con su
commit de origen, para poder auditar divergencias frente al upstream (ver
docs/IPOD_INTEGRATION.md §6, riesgo "el fork diverge").

## Fuente: iOpenPod

- **Repositorio**: https://github.com/TheRealSavi/iOpenPod
- **Licencia**: MIT — Copyright (c) 2025 John Gibbons
- **Redistribución en Cicada**: GPLv3 (MIT → GPLv3 es compatible; ver §0.4 del spec)
- **Clon local de referencia**: `../iPod-clon/iOpenPod`
- **Commit de origen**: `ea72e3e7786c5dd08be2680a6f5778c688db5259`
  (2026-08-04, "Forensic findings of iTunesDB")

Regla de vendorizado (spec §1): se copia un paquete, se escriben sus tests, se
verifica contra el iPod real, y solo entonces se pasa al siguiente.

### Paquete 1 — `itunesdb_shared/` → `cicada/ipod/db/shared/`

Origen: `src/iopenpod/itunesdb_shared/` @ `ea72e3e`
(clon: `../iPod-clon/iOpenPod`). Definiciones y constantes compartidas por parser
y writer; solo stdlib, sin dependencias de terceros. Copiado sin modificaciones
(imports relativos intactos). **Estado: copiado y verificado.**

| Archivo (destino `cicada/ipod/db/shared/`) | Origen (commit ea72e3e) |
|---|---|
| `__init__.py` | `src/iopenpod/itunesdb_shared/__init__.py` |
| `album_identity.py` | `src/iopenpod/itunesdb_shared/album_identity.py` |
| `constants.py` | `src/iopenpod/itunesdb_shared/constants.py` |
| `device_time.py` | `src/iopenpod/itunesdb_shared/device_time.py` |
| `extraction.py` | `src/iopenpod/itunesdb_shared/extraction.py` |
| `field_base.py` | `src/iopenpod/itunesdb_shared/field_base.py` |
| `mhbd_defs.py` | `src/iopenpod/itunesdb_shared/mhbd_defs.py` |
| `mhia_defs.py` | `src/iopenpod/itunesdb_shared/mhia_defs.py` |
| `mhii_defs.py` | `src/iopenpod/itunesdb_shared/mhii_defs.py` |
| `mhip_defs.py` | `src/iopenpod/itunesdb_shared/mhip_defs.py` |
| `mhit_defs.py` | `src/iopenpod/itunesdb_shared/mhit_defs.py` |
| `mhod_defs.py` | `src/iopenpod/itunesdb_shared/mhod_defs.py` |
| `mhsd_defs.py` | `src/iopenpod/itunesdb_shared/mhsd_defs.py` |
| `mhyp_defs.py` | `src/iopenpod/itunesdb_shared/mhyp_defs.py` |
| `playlist_lifecycle.py` | `src/iopenpod/itunesdb_shared/playlist_lifecycle.py` |
| `playlist_properties.py` | `src/iopenpod/itunesdb_shared/playlist_properties.py` |

Tests: `tests/ipod/db/shared/` — `device_time` (conversión mac↔unix, round-trip,
DST America/Santiago) y smoke (carga, `FIELD_REGISTRY` con 8 chunks, y
verificación contra el `iTunesCDB` real del fixture nano7g).

**Hallazgo de formato**: el `iTunesCDB` del Nano 7G es una cabecera `mhbd` en claro
(244 bytes, con la firma en `0xAB`) seguida del cuerpo **comprimido con zlib**
(payload que descomprime a ~51 KB). Solo `mhbd` es visible en texto; los demás
chunks (`mhsd`, `mhlt`, `mhit`, `mhod`…) viven dentro del payload zlib. Relevante
para el parser (paquete 3).

### Paquete 2 — `device/` → `cicada/ipod/device/` (por etapas)

El `device/` de iOpenPod son 36 archivos (~17.800 líneas). Se copia por etapas
para controlar el riesgo. **`write_guard.py` y `backup.py` de este directorio son
de Cicada (Fase 0), no de iOpenPod: no se tocan.**

#### Etapa 2a — módulos limpios (datos/enums, cero escrituras, cero deps forward)

Origen: `src/iopenpod/device/` @ `ea72e3e` (clon: `../iPod-clon/iOpenPod`).
Copiados sin modificar. **Estado: copiado y verificado.**

| Archivo (destino `cicada/ipod/device/`) | Origen (commit ea72e3e) |
|---|---|
| `checksum.py` | `src/iopenpod/device/checksum.py` |
| `artwork_presets.py` | `src/iopenpod/device/artwork_presets.py` |
| `models.py` | `src/iopenpod/device/models.py` |
| `capabilities.py` | `src/iopenpod/device/capabilities.py` |

Deps internas: `capabilities` → `artwork_presets`, `checksum`, `models` (todos en
esta etapa). Solo stdlib; ninguna dep forward a paquetes 3/4.

Tests: `tests/ipod/device/test_{checksum,capabilities,models,artwork_presets}.py`.

**Hallazgo de resolución de esquema**: el HASHAB del Nano 7G **no** se resuelve
leyendo `mhbd[0x30]` (el `hashing_scheme`): en el iTunesCDB real ese campo vale
`3`, que no está en el mapa wire (HASHAB = wire `4`). HASHAB se determina por
**capacidad** (`checksum_type_for_family_gen("iPod Nano","7th Gen")`). Registrado
en los tests. Relevante para el dispatcher de hash (Fase 2).

#### Etapa 2b — en curso

Bloque pesado con adaptaciones.

**`authority.py` — reimplementado (NO vendorizado).** Es código propio de Cicada
que cumple la interfaz que espera `info.py` (`read_authority`,
`check_authority_coverage`, `update_sysinfo`, `cache_sysinfo_extended`,
`SOURCE_RANK`, `SYSINFO_FIELDS`) pero persiste **fuera del dispositivo**, en
`~/.cicada/sysinfo/<sha256(guid)[:16]>/`. Motivos y decisiones:
- iOpenPod escribe `iOpenPodSysInfoAuthority`/SysInfo en `iPod_Control/Device/`,
  lo que hace que Music.app pida restaurar el iPod. Cicada no toca el volumen.
- Indexado por **FireWireGUID**, no por punto de montaje (el mismo iPod puede
  montarse en rutas distintas; puede haber varios dispositivos).
- El nombre de carpeta es `sha256(guid)[:16]` (GUID no en claro en rutas/logs);
  el GUID real vive dentro del `authority.json`.
- Las tablas de ranking/procedencia (`_SOURCE_ORDER`, `SYSINFO_FIELDS`) y la
  semántica derivan de iOpenPod (MIT) — atribución en NOTICE.
- Añadida `clean_foreign_authority(ipod_path)` (vía `write_guard`), expuesta como
  `cicada ipod clean-foreign`: elimina el `iOpenPodSysInfoAuthority` ajeno del
  dispositivo. No automática — para verificar la hipótesis del rechazo de Music.app.

Tests: `tests/ipod/device/test_authority.py` (12).

**`sysinfo.py` — vendorizado sin modificar.** Origen: `src/iopenpod/device/sysinfo.py`
@ `ea72e3e`. **Estado: copiado y verificado.** Parseo puro de SysInfo/SysInfoExtended;
sin probing de hardware, sin `pyusb`, sin `import os`, cero escrituras. Única dep
interna: `.lookup.extract_model_number` (import perezoso y **guardado** con
`try/except` → degrada al string crudo si `lookup` no está; solo se usa cuando hay
`ModelNumStr`, ausente en el Nano 7G). Ahora `authority._normalise_sysinfo_extended`
usa este parser real.

Tests: `tests/ipod/device/test_sysinfo.py` (9), incl. el obligatorio contra el
fixture real (FireWireGUID, FamilyID=18, MaxTracks=65534, DBVersion=5).

**`lookup.py` — vendorizado sin modificar.** Origen: `src/iopenpod/device/lookup.py`
@ `ea72e3e`. **Estado: copiado y verificado.** Solo depende de `.capabilities` y
`.models` (2a) + `re`; sin escrituras/subprocess/pyusb. Degrada a `None` sin
ModelNumStr. Tests: `tests/ipod/device/test_lookup.py` (4). Nota: el mapeo
`FamilyID(int)→(familia,gen)` **no** está aquí — llega con scanner/info.

**`durability.py` — vendorizado con una adaptación mínima.** Origen:
`src/iopenpod/device/durability.py` @ `ea72e3e`. **Estado: copiado y verificado.**
Primitivas de flush/replace (`durable_replace`, `durable_unlink`,
`durable_publish_new`, `flush_filesystem`); **no** hace eject. `flush_filesystem`
ya devuelve `(bool, mensaje)` con `timeout`.
- **Adaptación (única):** el import perezoso `from .info import resolve_itdb_path`
  en `_committed_database_path` se envolvió en `try/except ImportError` con log
  explícito. `info` llega al final de 2b; hasta entonces `flush_filesystem` omite
  el flush del ancla de DB en vez de lanzar un `ImportError` confuso.

**`safe_write.py` — código propio de Cicada** (no vendorizado). Envuelve las
primitivas de `durability` validando el target con
`write_guard.assert_within_ipod_control` **antes** de delegar
(`guarded_durable_replace`/`_publish_new`/`_unlink`). Regla de integración: nadie
escribe en el volumen sin pasar por aquí. Tests: `tests/ipod/device/test_safe_write.py`
(5), incl. rechazo vía symlink que apunta fuera.

**`eject.py` — código propio de Cicada** (no vendorizado). iOpenPod expulsa pero
NO identifica al proceso que bloquea; esta reimplementación sí. `eject_ipod(mount,
*, force=False, timeout=30)` → `EjectResult(ejected, message, blockers, forced,
platform)`. Hace flush (vía `durability`), nunca fuerza por defecto, usa timeout, y
devuelve `Blocker(pid, name, path, ppid, parent, friendly_name)` al llamador.
`friendly_name` mapea binarios conocidos a nombres entendibles (AMPDevicesAgent→
"Música", mds→"Spotlight", fseventsd→"sistema de archivos de macOS", bird/cloudd→
"iCloud"). Expuesto como `cicada ipod eject [--force]`.
- **macOS**: implementado — parser del disidente de `diskutil` (validado contra la
  salida real de `AMPDevicesAgent`) + fallback `lsof`; seguridad (no expulsa discos
  no extraíbles).
- **Linux**: implementado — `umount` no forzado + bloqueadores vía `lsof`.
- **Windows**: **ESBOZADO, no implementado.** Devuelve un `EjectResult` honesto
  ("no se pueden identificar los procesos bloqueadores en Windows todavía").
  **PENDIENTE**: expulsión vía `DeviceIoControl` (FSCTL_LOCK_VOLUME/DISMOUNT +
  IOCTL_STORAGE_EJECT_MEDIA) e identificación del bloqueador vía **Restart Manager
  API** (`RmStartSession`/`RmGetList`, ctypes) — se dejó fuera por no poder
  probarlo en hardware Windows. Ausencia declarada, no ctypes sin verificar.

Tests: `tests/ipod/device/test_eject.py` (20), incl. parser contra la salida real.

#### Etapa 2c — Identidad desde el volumen (código propio, sin vendorizar)

Decisión: la orquestación de `scanner`/`info` de iOpenPod **se reimplementa, no se
vendoriza** — `vpd_libusb` escribe `SysInfo`/`SysInfoExtended` en
`iPod_Control/Device/` (lo que corrompe Music.app), `metadata_write` es la sesión
que escribe ahí, y `bootstrap` crea la DB en el dispositivo. Bajo la regla dura
(nada escribe en `Device/`), reimplementar es más seguro que quitar caminos de
escritura a mano en 5.000+ líneas.

- **`family_ids.py`** (propio) — tabla `FamilyID(int)→(familia,gen)` que **iOpenPod
  no tiene**. Estructura de datos pura, ampliable sin tocar lógica; cada entrada
  con procedencia y flag `verified`. **Solo el FamilyID 18 (Nano 7G), verificado
  contra hardware real** (confirmado de forma independiente por sufijo de serie
  MD476). No se siembran inferidos.
- **`device_info.py`** (propio) — `read_device_info(mount, *, use_usb=False)` lee la
  identidad **solo del volumen**, **nunca escribe**, USB opcional (no-op hasta 2d),
  y **degrada a DeviceInfo parcial** en vez de lanzar. Cascada: FamilyID → sufijo de
  serie → ModelNumStr → USB PID. Usa los módulos ya copiados (`sysinfo`,
  `capabilities`, `checksum`, `models`, `lookup`). Resuelve el Nano 7G del fixture:
  `iPod Nano 7th Gen, HASHAB, identified_by=family_id`.

Tests: `tests/ipod/device/test_device_info.py` (11), incl. **validación cruzada**
(family_id y sufijo de serie resuelven al mismo modelo) y no-escritura.

### Paquete 3 — `itunesdb_parser/` → `cicada/ipod/db/parser/`

#### Etapa 3a — Lectura (parseo + listado), read-only. **Estado: copiado y verificado.**

Origen: `src/iopenpod/itunesdb_parser/` @ `ea72e3e`. 16 archivos vendorizados:
`exceptions`, `_parsing`, `byte_walk`, `chunk_parser`, `parser`, `mh{bd,sd,it,yp,ip,od,ia,ii}_parser`,
`ipod_library`, `playcounts`, `otg`. Imports `iopenpod.itunesdb_shared` reescritos a
`cicada.ipod.db.shared`. Descompresión zlib transparente del iTunesCDB.

- **Excluidos**: `forensics` (escribe informe de diagnóstico), `artwork_links`
  (depende de `artworkdb_parser`, Fase 4). El uso perezoso de `artwork_links` en
  `ipod_library` se **guardó con try/except ImportError** (sin artwork se lista igual).
- **Adaptación (Cicada)**: `load_ipod_library(..., mount=None)` — parámetro opcional
  de mount explícito. La derivación `dirname³(itunesdb_path)` es frágil (resuelve mal
  en silencio para un iTunesCDB fuera del layout estándar, p. ej. de un backup); con
  `mount` dado se usa ese en vez de derivar.

Tests: `tests/ipod/db/parser/test_ipod_library.py` (9). Verificado contra el
iTunesCDB real: **25 tracks, 3 playlists** (master "iPod" con 25 items + 2 de usuario
con 11 y 13). Play Counts: 25 entradas, **sin datos reales** (todo a cero/centinela).

#### Etapa 3b — Verificación HASHAB. **Estado: copiado y verificado. GO/NO-GO: PASS.**

De paquete 4 (`itunesdb_writer`) @ `ea72e3e`, lo mínimo para verificar:
- `hashab.py` → `cicada/ipod/db/writer/hashab.py` (imports `itunesdb_shared` reescritos).
- `wasm/calcHashAB.wasm` → `cicada/ipod/db/writer/wasm/` (506 KB, dstaley/hashab, Unlicense).
- Dep `wasmtime` añadida a requirements.txt.
- **`verify.py` (propio)**: `verify_hashab(itunescdb, guid) -> HashVerifyResult(valid, stored,
  computed)`. Computa + compara, **sin escribir**.

**Resultado (revisado tras probar contra una base de iTunes/Apple): GO con advertencia.**
`verify_hashab` reproduce **byte a byte** las firmas de **iOpenPod** (mismo WASM), pero
**NO** las de **Apple/iTunes** (verify=False contra la base real de iTunes). Dos hechos
verificados con hardware, **distintos**: (1) el **firmware del iPod acepta AMBAS firmas**
—el dispositivo reproduce lo que escribe iOpenPod—; (2) **Music.app solo acepta la de
Apple** y pide restaurar el iPod. El go/no-go de Fase 2 es que el dispositivo funcione →
**la escritura HASHAB es VIABLE**, con la limitación conocida de que **rompe la
compatibilidad con Music.app de forma irreversible**. Fase 2 debe advertir al usuario
antes de la primera escritura. Ver §0.3 del spec.

**Hallazgo que corrige el spec (§0.3):** el SHA1 se computa sobre el **iTunesCDB
COMPRIMIDO** en disco (no el descomprimido), con `hashing_scheme`=4 y el zeroing estándar,
GUID sin reversión. Encontrado por barrido de variantes (120 combinaciones). Implicación
para el writer de Fase 2: **comprimir primero, luego firmar**.

Tests: `tests/ipod/db/writer/test_verify_hashab.py` (5), incl. integración con
`device_info` (el GUID sale de leer solo el volumen).

**Pendiente:**
#### Etapa 2d-a — Identidad por USB (macOS). **Estado: implementado (falta aceptación en hardware).**

Lee el `FireWireGUID` del hardware cuando no está en disco (iPod restaurado por
iTunes no tiene `SysInfoExtended`). En macOS corre **`vpd_iokit`** (IOKit
SCSITaskLib, ctypes) — el módulo más limpio del stack USB: **cero escrituras, sin
`metadata_write`, sin pyusb, sin root**.

- **`vpd_iokit.py`** — vendorizado sin modificar (autocontenido, solo ctypes).
- **`vpd.py`** (propio) — dispatcher por plataforma; `query_vpd() -> VpdResult(data,
  error, transport)`. **Fallo nunca silencioso**: error tipado (IOKit no disponible /
  rechazó el SCSITaskUserClient / dispositivo no encontrado / plataforma no soportada).
- **`volume_id.py`** (propio) — huella del volumen para el caché GUID off-device.
  **strong** = `diskutil VolumeUUID` (VSN, sin root: diskutil hace la lectura
  privilegiada); **weak** = `sha256(DeviceNode+VolumeName)`. Comprobado: leer el VSN
  del boot sector directamente **requiere root** (`dd /dev/diskNsM` → Permission
  denied), por eso se delega en diskutil.
- **`device_info`** — orden de resolución del GUID: **disco → caché fuerte → USB →
  caché débil**. Añadidos `usb_error` y `guid_provenance` (disk/cache_strong/usb/
  cache_weak). El puntero **débil** queda por debajo de USB y **no es write-safe**
  (`guid_is_write_safe`): la Fase 2 no firmará con un GUID de `cache_weak`.
- **`authority`** — puntero `huella_volumen → GUID` (`~/.cicada/sysinfo/index/`) +
  `store_sysinfo_extended_for_guid`. El resultado USB se cachea **off-device**, nunca
  en `Device/`.
- CLI: `cicada ipod identify [--usb]` (para la prueba de aceptación).

Restricciones cumplidas: **`vpd_libusb` y `metadata_write` NO entran**; cero escrituras
de SysInfo al volumen; pyusb opcional (macOS usa IOKit, no lo toca).

Tests: `tests/ipod/device/test_vpd_2d.py` (12), todo mockeado (sin hardware).

**Etapa 2d-b (pendiente)** — Linux/Windows por libusb: `usb_backend`
  + parsers `vpd_*` + `linux_identity`, y `vpd_libusb` **adaptado** para volcar a
  `authority` off-device, nunca a `Device/`. `metadata_write` NO se copia. pyusb opcional.
- **Paquete 3** (`itunesdb_parser`) — lectura de `iTunesCDB`/`Library.itdb`.
- **Nunca entran**: `metadata_write`, `bootstrap`, y el camino de escritura de `vpd_libusb`.
- Toda escritura al volumen pasa por `write_guard`/`safe_write`.

Atribución completa en `cicada/ipod/NOTICE`.

### Paquete 4 — `itunesdb_writer/` → `cicada/ipod/db/writer/` (Fase 2, por etapas)

#### Etapa 2a — Escritura del iTunesCDB en staging. **Estado: implementado y verificado (sin hardware).**

Origen: `src/iopenpod/itunesdb_writer/` @ `ea72e3e`. Vendorizados los **builders**:
`mhbd_writer` (builder puro `write_mhbd -> bytes`), `mh{it,yp,ip,od,sd,lt,la,li,lp}_writer`,
`mhod_spl_writer`, `mhod52_writer`, `hash58`, `hash72` (hashab ya estaba). Del paquete 6:
`_track_conversion.py` (conversor dict↔TrackInfo). Imports `itunesdb_shared`→`db.shared`.

**Adaptaciones (clave):** el **stack de escritura-al-dispositivo** de iOpenPod
(`filesystem`, `path_safety`, `storage_safety`, `write_readiness`, su `write_guard`,
`metadata_write`) **NO se vendoriza** — se reemplaza el coordinador. Sus imports
top-level en `mhbd_writer`/`hash72` se envolvieron en `try/except ImportError` (degradan
a `None`); Cicada no llama esas vías. `ChecksumType`/`DeviceCapabilities` desde
`cicada.ipod.device`.

**`build.py` (propio)** — `build_itunescdb(tracks, *, firewire_id, checksum, time_context, …)
-> bytes`: reimplementa la entrada de escritura (que estaba enredada con el stack de
dispositivo). Hace `write_mhbd` (builder) → comprimir zlib → **firmar sobre el comprimido**
(§0.3). **Produce bytes; no escribe disco** (el install es del coordinador 2c vía safe_write).
Gate: `firewire_id` write-safe obligatorio.

**Hallazgo (cazado por la comparación campo por campo):** sin pasar el `time_context`
del dispositivo, `date_added`/`last_modified` se **desplazan por el offset de zona**
(mac-en-hora-local ↔ Unix). `build_itunescdb` exige el contexto (el mismo con que se
leyó) → round-trip exacto.

Tests: `tests/ipod/db/writer/test_build_2a.py` (5): 25→26 tracks, `verify_hashab` True,
**comparación campo por campo de los 25** (idénticos con contexto), regresión del fix de
fechas, y **cross-check con el iOpenPod prístino** (`../iPod-clon/iOpenPod/src` vía
subprocess) — no es independencia (nuestro writer ES el suyo), prueba que las adaptaciones
no rompieron el formato.

**Pendiente:** 2c (coordinador propio: dry-run, backup, install vía safe_write, verify,
rollback, advertencia Music.app).

### Paquete 5 — `sqlitedb_writer/` → `cicada/ipod/db/sqlite/`

#### Etapa 2b — Escritura de las bases SQLite (`iTunes Library.itlp/`) en staging. **Estado: implementado y verificado (sin hardware).**

Origen: `src/iopenpod/sqlitedb_writer/` @ `ea72e3e`. Vendorizados los **builders puros**:
`library_writer` (`write_library_itdb -> playlist_pids`), `locations_writer`,
`dynamic_writer`, `extras_writer`, `genius_writer`, `cbk_writer` (`write_locations_cbk`),
`_helpers`. Imports `itunesdb_shared`→`db.shared`, `itunesdb_writer`→`db.writer`,
`sqlitedb_writer`→`db.sqlite`.

**Adaptaciones:** como en 2a, el stack de escritura-al-dispositivo (`path_safety`,
`write_guard`, `write_readiness`, `detect_checksum_type`/`get_firewire_id`) **no se
vendoriza**: en `sqlite_writer` sus imports top-level van en `try/except ImportError`
(degradan a `None` + shim `DeviceWriteSafetyError`); Cicada no llama la vía
`write_sqlite_databases`→install. `ChecksumType`/`DeviceCapabilities` desde
`cicada.ipod.device`.

**`build.py` (propio)** — `build_sqlite_databases(dest_itlp, tracks, *, firewire_id,
checksum, time_context, playlists, …) -> dict`: reimplementa la orquestación de
`write_sqlite_databases` (que estaba enredada con el install), produciendo los **6
archivos** (`Library/Locations/Dynamic/Extras/Genius.itdb` + `Locations.itdb.cbk`) en un
directorio **off-device**. El install es del coordinador 2c vía safe_write.

**El `.cbk` NO es un esquema opaco nuevo:** es `[57B firma HASHAB de final_sha1] +
[20B final_sha1=SHA1(∥ SHA1 de cada bloque 1024B)] + [N×20B SHA1 de cada bloque]` de
`Locations.itdb` (libgpod `mk_Locations_cbk`). SHA1 abierto + el HASHAB que ya teníamos.

**Hallazgo (época Cocoa, cazado por la comparación campo por campo — 3ª vez del formato
de fechas):** `Dynamic.item_stats.date_played` de las 25 pistas salía `-14400` (−4h) vs
`0` del fixture. Causa: el centinela "2001-01-01" (`last_played=978292800`) pasa por
`unix_to_coredata` (época Cocoa absoluta, sin zona) y expone el offset con que se leyó
(el fixture no preserva la zona real). Fix en `dynamic_writer`: una pista **nunca
reproducida/saltada** lleva `date_played=0` (convención iOpenPod/libgpod, y semántica
correcta). Regresión en el test.

Tests: `tests/ipod/db/sqlite/test_build_2b.py` (7): produce los 6 archivos (los `.itdb`
son SQLite reales), **comparación campo por campo** de `Library.item` y
`Dynamic.item_stats` (incluido `date_played`), **coherencia de dbids entre capas leídos
por separado** (parser del iTunesCDB sin signo ↔ sqlite3 con signo, normalizados U64) con
**test negativo** que prueba que la verificación FALLA si divergen, y regresión de la
época Cocoa (nunca-reproducida ⇒ 0; reproducida conserva su instante).

**Completado:** 2c (coordinador: instala iTunesCDB + itlp/ juntos vía safe_write).

### Coordinador Transaccional (Etapa 2c) — `cicada/ipod/db/coordinator/` (código propio de Cicada)

Orquestador propio de escritura transaccional con rollback para el iPod Nano 7G. **Estado: implementado y verificado.**

- `consent.py` (propio): Gate de advertencia de incompatibilidad con Music.app de Apple. Persiste consentimiento off-device en `~/.cicada/consent/<sha256(guid)[:16]>.json` con escritura atómica. No re-pregunta si ya fue otorgado.
- `plan.py` (propio): Generador de planes dry-run. Captura la huella `PreStateFingerprint` de los 7 archivos pre-existentes en el iPod, genera los 7 artefactos en staging off-device (`iTunesCDB` comprimido/firmado + 6 archivos `iTunes Library.itlp/`), y valida consistencia interna antes de congelar el plan.
- `apply.py` (propio): Ejecución en 5 fases rigurosas:
  - Fase A (Precondiciones): Revalida montaje, permisos, procedencia de GUID (`guid_is_write_safe`), gate de consentimiento y huella pre-estado.
  - Fase B (Backup verificado): Snapshot `DB_ONLY` con `create_backup` y verificación de integridad.
  - Fase C (Staging en device): Copia los 7 artefactos como `.cicada-new` con `fsync` individual.
  - Fase D (Commit por renames): Marcador `inflight.json` previo y reemplazo atómico `os.replace` en orden estricto (`Locations.itdb` → `.cbk` → resto `.itdb` → `iTunesCDB`).
  - Fase E (Verificación post-commit): Re-lectura con parser `load_ipod_library` y `sqlite3` (con `PRAGMA integrity_check`).
  - Rollback byte-exacto ante cualquier error en D o E restaurando el backup con `restore_backup`.
  - `recover_inflight_commit`: recuperación cross-sesión en caso de corte de energía o crash.
- `_helpers.py` (modificado): Añadida constante `SQLITE_INT_MASK = 0xFFFFFFFFFFFFFFFF` y función documentada `u64(val: int) -> int` para normalizar dbids con signo de SQLite a sin signo de iTunesCDB.

Tests añadidos en Etapa 2c (25 tests):
- `tests/ipod/db/sqlite/test_helpers.py` (5 tests): normalización `u64`, `s64`, simetría round-trip y valores de borde.
- `tests/ipod/db/coordinator/test_consent.py` (8 tests): persistencia off-device, tolerancia a formatos, aislamiento por GUID y JSON corrupto.
- `tests/ipod/db/coordinator/test_plan.py` (6 tests): staging off-device, `PreStateFingerprint` drift, rechazo de `cache_weak`, verificación de artefactos.
- `tests/ipod/db/coordinator/test_apply.py` (6 tests): commit end-to-end, aborto por falta de consentimiento, aborto por plan obsoleto, simulación de fallo en commit con rollback byte-exacto, simulación de fallo en verify con rollback, y recuperación con `inflight.json`.

**Total suite iPod tras 2c:** 247 tests pasando.

### Paquete 6 — `cicada/ipod/sync/` (código propio de Cicada — Fase 3)

Motor de persistencia local, cálculo de deltas bidireccionales y gestión de playlists. **Estado: implementado y verificado.**

- `state.py` (propio): Capa de persistencia en SQLite (`~/.cicada/ipod.db` / `$CICADA_HOME/ipod.db`) con 4 tablas (`devices`, `track_map`, `playback_state`, `playlists_map`), context manager `_connection()` con cierre garantizado, transacciones explícitas `transaction()` y normalización uint64 (`u64()`).
- `bidirectional.py` (propio): Lector de contadores desde `Dynamic.itdb` (Nano 6G/7G) y `iTunesCDB`/`iTunesDB` con normalización de épocas (Core Data 2001 y Mac 1904 a Unix 1970). Cálculo de deltas (`delta_play_count`, `delta_skip_count`, `rating_changed`, escala 0-5 estrellas) y protección contra reseteo de contadores.
- `playlists.py` (propio): Conversión de `LocalPlaylist` a `PlaylistInfo` con IDs de 64 bits y resolución de rutas contra `track_map`. Preservación byte-exacta de smart playlists v1 (`smart_prefs`, `smart_rules`, blobs `mhod50`/`51`/`55`/`100`/`102`).
- `_helpers.py` (modificado): Añadida función `coredata_to_unix()` para convertir timestamps de Core Data a Unix epoch.

Tests añadidos en Fase 3 (20 tests):
- `tests/ipod/sync/test_state.py` (7 tests): Inicialización de esquema, CRUD de dispositivos, normalización uint64, estrellas, transacciones con rollback y borrado en cascada.
- `tests/ipod/sync/test_bidirectional.py` (7 tests): Conversión de épocas, lectura de `Dynamic.itdb`, deltas incrementales, cambios de rating, skips, counter reset y persistencia de baseline.
- `tests/ipod/sync/test_playlists.py` (6 tests): Resolución de listas estándar, pistas no resueltas, extracción de smart playlists, preparación unificada, persistencia y round-trip end-to-end con `create_plan()` y `apply()`.

**Total suite iPod tras Fase 3:** 280 tests pasando.

