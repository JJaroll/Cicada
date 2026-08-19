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
  dispositivo.

**Hipótesis confirmada con hardware real (2026-08-19)**: en un iPod con residuo real de
iOpenPod que Music.app ya rechazaba, `clean-foreign` + borrado manual de los `.backup`
ajenos —sin tocar `mhbd`/SQLite, sin restaurar— bastó para que Music.app reconociera el
dispositivo completo de nuevo. Detalle y comparación byte a byte del `mhbd`/SQLite
(idénticos entre Cicada e iOpenPod salvo 4 IDs aleatorios esperados) en
`docs/IPOD_INTEGRATION.md` §0.3.

**`clean_foreign_authority()` extendida para cubrir también los `.backup` ajenos
(2026-08-19).** Ya no limpia solo `iOpenPodSysInfoAuthority` — también los 7 `.backup`
en sitio de los 7 archivos de base de datos (`FOREIGN_BACKUP_RELPATHS`: mecanismo
propio de `write_itunesdb`/`write_sqlite_databases` de iOpenPod, que el camino activo
de Cicada nunca invoca). **Cambio de firma explícito**: devuelve `list[str]` (rutas
relativas eliminadas) en vez de `bool` — así el CLI/futuro API pueden reportar
exactamente qué se borró, no solo si se borró algo.

**Garantía de seguridad, verificada por comportamiento, no por lectura de código**:
antes de borrar automáticamente esos 7 nombres hacía falta la certeza de que el camino
activo de escritura de Cicada (`build_itunescdb`/`build_sqlite_databases`, vía
`create_plan()`) nunca los produce — de lo contrario, `clean-foreign` podría borrar algo
propio. `test_create_plan_never_produces_foreign_backup_filenames`
(`tests/ipod/db/coordinator/test_plan.py`) corre `create_plan()` de verdad y revisa el
staging resultante, en vez de confiar en que un grep de hoy siga siendo cierto mañana.
Sanity check de mutación: se inyectó a mano un `.write_bytes` que generaba
`iTunesCDB.backup` en `create_plan()`, el test lo detectó, se revirtió.

**Decisión de nombre registrada, no un olvido**: la función se sigue llamando
`clean_foreign_authority` pese a que ya cubre más que solo el archivo de autoridad —
a propósito, porque es el nombre del comando público `cicada ipod clean-foreign` ya
conocido, y no hay urgencia de romperlo. Un rename a `clean_foreign_artifacts` (o
similar) sería apropiado si en el futuro algo más importa este nombre directamente.

Tests: `tests/ipod/device/test_authority.py` (18, incluye los `.backup` y el caso
combinado autoridad+backups) + 1 en `test_plan.py` (la garantía de arriba).

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

Tests: `tests/ipod/device/test_eject.py` (29), incl. parser contra la salida real.

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
—el dispositivo reproduce lo que escribe iOpenPod—; (2) en esta fase se creía que
**Music.app solo acepta la de Apple** y por eso pedía restaurar el iPod. El go/no-go de
Fase 2 fue que el dispositivo funcione → **la escritura HASHAB es VIABLE**.

**Corrección posterior (2026-08-19, ver §0.3 del spec): la firma nunca fue la causa del
rechazo de Music.app.** `mhbd`/SQLite de Cicada e iOpenPod son idénticos byte a byte
(salvo 4 IDs aleatorios esperados) — la causa real es `iOpenPodSysInfoAuthority` +
reescritura de `SysInfo`/`SysInfoExtended` + `.backup` residuales, todo fuera del
`iTunesCDB`, y todo evitado por diseño en Cicada desde `authority.py` (Paquete 2 más
arriba). Confirmado limpiando esos archivos en hardware real sin restaurar: Music.app
volvió a reconocer el dispositivo. El requisito de advertir antes de la primera
escritura se mantiene (la firma sigue sin ser la de Apple), pero ya no por el motivo
que se creía aquí.

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

- `consent.py` (propio): Gate de advertencia de divergencia de firma con Music.app de Apple. Persiste consentimiento off-device en `~/.cicada/consent/<sha256(guid)[:16]>.json` con escritura atómica. No re-pregunta si ya fue otorgado. **Se mantiene, no descartado** — la firma HASHAB de Cicada sigue sin ser la de Apple. **Nota pendiente (2026-08-19, no aplicada a propósito):** el texto del docstring de `consent.py` y del aviso en `cli.py`/`api.py` ("invalidará la compatibilidad con Music.app") quedó desactualizado tras confirmar en `docs/IPOD_INTEGRATION.md` §0.3 que Cicada, por sí sola, **no** rompe esa compatibilidad — el riesgo real es residuo de terceros (iOpenPod u otras herramientas) en el dispositivo, no la escritura de Cicada. Revisar el texto del mensaje cuando se decida tocar este gate; el mecanismo en sí no cambia.
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

### Paquete 7 — `artworkdb_writer/` → `cicada/ipod/db/artwork/` (Fase 4, por etapas)

Escritor de `ArtworkDB` + `.ithmb`. Origen: `src/iopenpod/artworkdb_writer/`,
`src/iopenpod/artworkdb_shared/` @ `ea72e3e` (4521 líneas en el original).

**Alcance de esta fase: SOLO iPod Nano 7G (RGB565_LE, 4 formatos fijos).**
Esto es una decisión de **entrega incremental, no el objetivo final** — iOpenPod
soporta más modelos (otros formatos de píxel: RGB565_BE, RGB555, UYVY, JPEG; y
otras tablas de dimensiones), y Cicada debe soportarlos todos eventualmente.
Ver **Etapa 4f** más abajo para la generalización — no está descartada, está
diferida.

- **Etapa 4a — Fuente de imagen unificada. Estado: implementado y verificado.**
  Cicada ya embebe carátula al organizar la biblioteca (`audio_processor.py`,
  vía Shazam/AcoustID) y ya la vuelve a leer para la UI de Biblioteca
  (`core/routes/library.py::_extract_embedded_artwork`, endpoint
  `/api/library/artwork`). En vez de portar `art_extractor.py` de iOpenPod
  (un segundo sistema de extracción), esa función se movió a
  `cicada/shared/artwork.py::extract_embedded_artwork` — módulo neutral que
  tanto `cicada.core` como `cicada.ipod` pueden importar sin romper la regla
  de que `cicada.ipod` nunca importa de `cicada.core`. `art_extractor.py` de
  iOpenPod **no se porta** (redundante).
  Tests: `tests/shared/test_artwork.py` (5 tests, fixtures reales en
  `tests/fixtures/audio/` generadas con ffmpeg+mutagen: mp3/m4a/flac con y
  sin `APIC`/`covr`/picture).
- **Etapa 4b — Codec RGB565_LE + tipos. Estado: implementado y verificado.**
  `cicada/ipod/db/artwork/{rgb565,types}.py`. `convert_art_for_format()` acepta
  cualquier `ArtworkFormat` (no solo Nano 7G) pero **rechaza con
  `NotImplementedError`** cualquier `pixel_format` distinto de `RGB565_LE`
  en vez de producir bytes silenciosamente incorrectos — así que activar
  otros modelos en 4f es extender el codec, no revisar si esta etapa hizo
  una suposición oculta. `hpad` (padding de alineación de fila, p. ej. el
  formato 1016 del Nano 7G: 57px visibles con stride de 58) se deriva de
  `ArtworkFormat.row_bytes`, no de una tabla aparte. No se porta
  `ithmb_codecs.py` completo (RGB565_BE/RGB555/UYVY/JPEG, decode) en esta
  etapa — ver 4f. `EncodedFormatPayload` se simplificó frente al
  `artwork_types.py` original: sin `ExistingFormatRef`/`PassthroughFormatRef`
  (soportan preservación incremental, descartada en 4c).
  Tests: `tests/ipod/db/artwork/test_rgb565.py` (30 tests): decode
  JPEG/PNG/RGBA, resize a los 4 formatos Nano 7G, conversión RGB565 bit-exacta
  (rojo/verde/azul/blanco/negro puros), padding de stride, tamaños de salida
  para los 4 formatos, rechazo de formatos no-RGB565_LE (BE/RGB555/YUV).
- **Etapa 4c — Escritor binario ArtworkDB + `.ithmb`. Estado: implementado
  y verificado.** `cicada/ipod/db/artwork/{chunks,writer}.py`.
  Reescritura completa cada sync (~12s medido contra 954 tracks reales),
  **sin** dedup por hash ni preservación incremental — el ahorro del dedup
  (~30%, de 12.4s a 8.7s) no compensa la complejidad/riesgo frente al
  patrón "reescritura completa" ya usado en el resto de Cicada. Cada track
  recibe su propio `img_id` aunque comparta imagen con otro (sin tabla de
  reuso). `write_guard.py` no necesita cambios: `assert_within_ipod_control()`
  ya es genérico para cualquier subárbol de `iPod_Control/`, incluido
  `Artwork/` (la escritura a disco es responsabilidad del coordinador,
  Etapa 4d — `writer.py` aquí solo produce `bytes`, mismo patrón que
  `db/writer/build.py`: "aquí no se toca disco").
  `reference_mhfd` de iOpenPod (fusión de bytes con el ArtworkDB anterior,
  soporte de preservación) no se porta — no aplica sin preservación.
  `read_artworkdb()` es deliberadamente más simple que
  `read_existing_artwork()` de iOpenPod: sin el blindaje defensivo contra
  ArtworkDB de terceros corrupto, porque de momento solo relee lo que este
  mismo escritor acaba de producir (staging, no dispositivo real todavía).
  Se añadió `rgb565_le_to_rgb888()` a `rgb565.py` (4b) — inversa del
  encoder, solo para esta verificación, no forma parte del camino de
  escritura.
  **Verificación exigida antes de construir esto** (no solo "reparsea sin
  excepción"): con 3 imágenes de prueba conocidas (patrones de 4 cuadrantes,
  colores distintos por track) se comprobó (a) que el `.ithmb` releído y
  decodificado en el offset que indica el propio ArtworkDB reproduce los
  píxeles originales dentro del margen RGB565, (b) que esos offsets son
  exactos y no solapan entre tracks (chequeo anti-contaminación cruzada
  explícito, no solo tamaño total del archivo), y (c) que `song_id`/`img_id`
  en cada MHII corresponde al track correcto. Sanity check adicional: se
  inyectó a propósito un bug de offset (`offsets[fmt_id] = 0` en vez de
  `len(buf)`) y se confirmó que 13 de los 29 tests de
  `test_writer.py` lo detectan, antes de revertirlo — la suite no es solo
  happy-path.
  Tests: `tests/ipod/db/artwork/test_chunks.py` (7, round-trip binario
  sintético de cada chunk) y `test_writer.py` (29, verificación de extremo
  a extremo descrita arriba). Prueba en hardware real (que la carátula
  aparezca en pantalla) diferida a la Etapa 4d, cuando esté enganchado con
  `create_plan()`.
- **Etapa 4d — Enganche con `TrackInfo`/`create_plan()`/`apply()`. Estado:
  implementado y verificado.**
  `create_plan()` (`cicada/ipod/db/coordinator/plan.py`) construye artwork
  ANTES de `build_itunescdb()`/`build_sqlite_databases()`: resuelve la
  fuente de imagen por track (`source_path` si es una pista nueva, si no
  `mount/location` — el propio audio ya en el iPod, mismo patrón que
  `_heal_track_lengths` en `coordinator/media.py`), llama a
  `build_artwork_assets()`, y puebla `mhii_link`/`artwork_size`/`artwork_count`
  en el propio `TrackInfo` antes de que ambos builders los lean — consistencia
  por construcción, no por parche posterior. **Todo el subsistema (staging,
  artefactos, instalación, backup) es condicional**: se activa solo si al
  menos un track tiene una fuente de imagen resoluble
  (`Plan.artwork_touched`); si no, no se toca nada de `Artwork/` — evita
  tanto el coste de un ArtworkDB vacío en cada sync como el falso-positivo
  de "artefacto vacío" que dispararía la Fase A4 si se instalara siempre un
  `.ithmb` de 0 bytes.
  `apply()` extiende `_ORDERED_INSTALL_SEQUENCE` (ahora `_BASE_INSTALL_SEQUENCE`
  + `_ARTWORK_INSTALL_SEQUENCE` condicional) con los 4 `.ithmb` + `ArtworkDB`
  **antes** de la secuencia de 7 archivos, para que lo referenciado exista
  antes que quien lo referencia. `PreStateFingerprint` amplía sus rutas
  vigiladas a las 5 de Artwork siempre (barato, solo hash — un falso positivo
  de "plan obsoleto" solo fuerza regenerar el plan, no deja nada
  inconsistente). Fase E añade una verificación referencial: todo track con
  `mhii_link` en el iTunesCDB recién commiteado debe tener una entrada MHII
  correspondiente en el ArtworkDB recién commiteado — no confía en que
  "staging era consistente" implique "el commit físico lo es".

  **Bug real encontrado construyendo esto** (no solo en el diseño de papel):
  el backup `DB_ONLY` con `include_artwork=True` de la Fase B, tomado la
  PRIMERA vez que se escribe artwork, no tiene ningún miembro bajo
  `Artwork/` (esa carpeta aún no existía en el dispositivo) — así que si el
  commit fallaba a mitad DESPUÉS de instalar Artwork/ pero ANTES de terminar
  los 7 archivos base, `restore_backup()` revertía los 7 archivos pero
  dejaba el ArtworkDB/`.ithmb` recién instalados sin revertir (la
  reconciliación de `_prune_extras` solo poda raíces derivadas de los
  nombres de miembro del propio archivo). Fix: `restore_backup()` y
  `create_backup()` ahora comparten un parámetro explícito
  `include_artwork` (no inferido del contenido del archivo) — cuando es
  `True`, `restore_backup()` declara la raíz `Artwork/` aunque el backup no
  tenga miembros ahí, así la reconciliación la poda igual. Persistido en el
  marcador `inflight.json` (`set_inflight_marker`) para que
  `recover_inflight_commit()` (recuperación cross-sesión, sin `Plan`
  disponible) también lo aplique correctamente.

  **Verificación exigida antes de cerrar esta etapa** (paralela a la de 4c,
  pero contra la coordinación con Fase 2, no contra el formato binario):
  se forzó un escenario de dos syncs consecutivos en staging — sync 1 con
  un track nuevo (`source_path` → carátula real), sync 2 recargando SOLO
  ese mismo track sin `source_path` (como haría un round-trip real vía
  `load_ipod_library()`) — y se verificó, releyendo el ArtworkDB
  REALMENTE instalado tras el sync 2 (no el staging, no lo que el código
  "dice" que hizo), que el track del sync 1 conserva una entrada MHII
  válida. Sanity check: se deshabilitó a propósito el fallback a
  `location` (forzando el bug de regresión original) y se confirmó que
  este test específico falla con un mensaje claro; se revirtió después.
  Tests: `tests/ipod/db/coordinator/test_plan.py` (+5: construcción desde
  `source_path`, fallback a `location`, track sin arte junto a uno con
  arte, fingerprint cubre Artwork, skip completo sin fuente resoluble) y
  `test_apply.py` (+6: instalación+verificación E4, backup excluye Artwork
  cuando no se toca, backup SÍ cubre Artwork en un segundo sync, rollback
  byte-exacto revierte Artwork tras fallo en Fase D, E4 detecta una
  referencia colgante forzada, y el test de dos syncs consecutivos
  descrito arriba). Prueba de fuego en hardware real (Nano 7G): siguiente
  paso, fuera de esta etapa.

  **Prueba de fuego contra hardware real (Nano 7G), ejecutada dos veces
  (2026-08-18/19):** backup → sync → verificación independiente releyendo
  ArtworkDB/iTunesCDB ya instalados (no solo confiar en la respuesta) →
  eject limpio, ambas veces. Primera corrida por `curl` manual a
  `/api/ipod/media/sync`: artwork correcto, pero metadata (artista/álbum)
  vacía porque el payload a mano nunca incluyó esos campos — no fue un bug
  de Cicada, fue un payload incompleto (`MediaTrackInput`/`sync_media()`
  construyen `TrackInfo` solo de lo que el request trae, no leen tags del
  MP3). Segunda corrida repetida desde la UI real (búsqueda → selección →
  "Agregar a iPod" → carrito → sync), que sí arma el payload completo
  desde `libraryTracks`: artwork y metadata correctos, verificado
  releyendo el iTunesCDB instalado. Diagnóstico completo (TrackInfo
  antes/después de `build_artwork_assets()`, instrumentación temporal
  revertida) confirmó que el paso de artwork de 4d muta `TrackInfo`
  in-place y no toca ningún otro campo — no hay pérdida de metadata en el
  pipeline de escritura, nunca la hubo.

  **`cicada ipod plan`/`sync` (CLI): NO es una capacidad de artwork
  incompleta — tiene un contrato distinto, documentado aquí para que no
  se confunda con un bug (investigado y cerrado 2026-08-19).**
  `_load_tracks_from_file()` en `cli.py` nunca rellena `TrackInfo.source_path`
  porque `_cmd_plan()`/`_cmd_sync()` llaman a `create_plan()`/`apply()`
  **directamente**, y ese par **nunca copia audio** al dispositivo (el
  propio docstring de `plan.py` lo dice: "NUNCA escribe en el volumen del
  iPod"; `apply.py`'s `_BASE_INSTALL_SEQUENCE`/`_ARTWORK_INSTALL_SEQUENCE`
  solo listan artefactos de base de datos). La copia de audio vive
  exclusivamente en `copy_media()` dentro de `sync_media_to_ipod()`
  (`coordinator/media.py`), usada solo por `POST /api/ipod/media/sync`
  (la UI). Las claves que lee `_load_tracks_from_file()` (`Title`,
  `Artist`, `Album`, `Location`, con esa capitalización) coinciden
  exactamente con lo que emite `cicada ipod tracks --json` — el contrato
  real del CLI es **volcar → editar a mano → reaplicar** sobre tracks que
  **ya están en el iPod**, no agregar audio nuevo desde la PC. Para ese
  caso (round-trip de tracks existentes), el fallback a `location` de la
  Etapa 4d ya resuelve artwork sin ningún cambio — es el mismo mecanismo
  validado por el test de dos syncs consecutivos.
  Agregarle `source_path` al parser sin más habría sido un fix engañoso:
  `plan` mostraría `artwork_touched=True` (el paso de artwork solo
  necesita `source_path`), pero `sync`/`apply` fallaría después con
  `ValueError: track iPod location is empty` (reproducido de verdad
  durante el diagnóstico de metadata) o, peor, escribiría una referencia a
  un archivo que no existe en el dispositivo.
  **No se construye por ahora**: agregar audio nuevo por CLI (un futuro
  `cicada ipod add` envolviendo `sync_media_to_ipod()`, sin tocarla) sería
  una **capacidad nueva**, no un fix — decisión explícita de no construirla
  sin un caso de uso real pidiéndola (automatización, uso headless); ese
  caso, cuando aparezca, debe definir su propio diseño.

  **`Plan.artwork_touched`/`.artwork_tracks_count`/`.artwork_skipped_count`
  cableados a `ApplyResult`/`PlanResponse`/`ApplyResponse`/CLI, cerrando el
  punto 7 del diseño de 4d (2026-08-19).**
  `ApplyResult` (`db/coordinator/apply.py`) gana los 3 campos, poblados solo
  en el `return` de éxito desde `plan.*` — igual patrón que `tracks_written`;
  los dos `return` de rollback se quedan en 0/False, nada se instaló de
  verdad. `PlanResponse`/`ApplyResponse` en `api.py` los exponen en
  `POST /plan`, `POST /apply` y `POST /media/sync` (los tres comparten
  `ApplyResponse`; los demás endpoints que la reusan — `/restore`,
  `/playlist/*`, `/track/rate`, `/conflicts/resolve*` — no se tocaron,
  quedan en los defaults ya que no tocan artwork). CLI: `_cmd_plan`/`_cmd_sync`
  imprimen una línea de artwork cuando aplica.
  Tests con verificación fuerte, no solo presencia del campo: releen el
  ArtworkDB *realmente instalado* con `read_artworkdb()` y comparan su
  conteo de entradas contra el valor reportado en la respuesta —
  `tests/ipod/db/coordinator/test_apply.py` (+2), `tests/ipod/test_api.py`
  (+3, incluye el par `/plan`+`/apply` vía `location` y `/media/sync` vía
  `source_path`), `tests/ipod/test_cli.py` (+2). Sanity check de mutación:
  se forzó `artwork_touched=False` a mano en el handler de `/media/sync`,
  se confirmó que el test lo detecta, se revirtió. 467 tests tras esto.
- **Etapa 4e — API/CLI/UI.** Pendiente.
- **Etapa 4f — Generalización a otros modelos.**

  **Hallazgo de investigación (2026-08-19) que redujo el alcance real**:
  de los formatos de píxel que iOpenPod soporta (RGB565_LE, RGB565_BE,
  RGB555/REC_RGB555_LE, UYVY, I420_LE, JPEG), **las 24 device families que
  Cicada modela en `capabilities.py` usan RGB565_LE para `cover_art_formats`
  sin ninguna excepción** — verificado grepeando cada asignación
  `cover_art_formats=(...)` una por una. Los formatos no-LE (`RGB565_BE_90`,
  `RGB565_BE` en 1013/1019/1023, `UYVY`/`I420_LE`/`JPEG` en 1019/1067/1081)
  son de **fotos (slideshow) o salida de TV** (`role="photo_*"`/`"tv_out"`,
  subsistema `photo_formats`, Fase 6) — no ArtworkDB/cover art. Los
  restantes (`RGB565_BE` en 2002/2003 "iPod Mobile", `RGB555`/`REC_RGB555_LE`
  en 3001-3005 "iPod touch") no tienen ninguna entrada en
  `_FAMILY_GEN_CAPABILITIES` — Cicada no modela esos dispositivos en
  ninguna capacidad hoy, no solo artwork. Diferido con el mismo criterio
  que `cicada ipod add` (ver arriba): no se construye sin que exista
  primero soporte real de esa familia de dispositivo.
  `ithmb_codecs.py` de iOpenPod SÍ tiene encoders completos para todos esos
  formatos (`encode_image_for_format()`, línea 419-517) — si algún día
  hace falta, es portar, no escribir de cero. No portar
  `hydrate_track_artwork_refs` (`itunesdb_parser/artwork_links.py`)
  tampoco — solo relevante para reconciliar DBs legadas.

  **Esquema de verificación de tres niveles** (sin hardware de otros
  modelos disponible): (1) *verificado por construcción* — mismo código ya
  probado exhaustivamente en 4c/4d, solo parametrizado con otro
  `ArtworkFormat`; (2) *auditado contra la fuente, no contra runtime* — la
  tabla de dimensiones se transcribió de libgpod (`src/itdb_device.c`,
  citado en el docstring de `artwork_presets.py`), así que se audita por
  diff contra esa fuente, no se re-verifica en ejecución; (3) *marcado
  explícitamente como no verificado en hardware real*, por family, sin
  eufemismos. Se rechazó bit-exactitud contra los codecs de iOpenPod como
  sustituto — sería circular, ya sabemos que coinciden porque es la misma
  reimplementación ya verificada en 4b.

  - **Etapa 4f-1 — Activar RGB565_LE para las 23 device families restantes
    (además de Nano 7G). Estado: implementado y verificado.**
    `chunks.py`/`writer.py` (4c) ya eran agnósticos del formato de píxel
    (grep de `"RGB565"`/`"pixel_format"` sobre ambos: cero resultados) y
    `build_artwork_assets()` ya tomaba `formats` como parámetro con
    default de Nano 7G — la generalización no fue "escribir codecs", fue
    activar 3 puntos de hardcodeo localizados con precisión:
    `plan.py` (`ARTWORK_TARGET_RELPATHS` constante de módulo fija →
    función `artwork_target_relpaths(formats)`; `build_artwork_assets()`
    llamado sin `formats=` → ahora recibe `cover_art_formats` resuelto de
    `device_info.capabilities.cover_art_formats`) y `apply.py`
    (`_ARTWORK_INSTALL_SEQUENCE` fija → derivada de
    `plan.capabilities.cover_art_formats`, cero campos nuevos en `Plan`).
    Gate único: `cover_art_formats` vacío (dispositivo sin
    `supports_artwork` o con tabla vacía por omisión) salta el subsistema
    entero sin intentar extraer nada — ni siquiera se lee el audio.

    **Hallazgo encontrado en el diseño, antes de escribir código**: sin
    generalizar también `PreStateFingerprint`, un plan para cualquier
    family que no fuera Nano 7G fingerprintearía rutas `F1010_*` que nunca
    le pertenecen y **nunca detectaría deriva real en sus propios
    `.ithmb`** — un rollback que no dispara cuando debería, silencioso
    hasta que algo se corrompe de verdad. Corregido: `capture()` recibe
    `artwork_relpaths` (derivado de los formatos DEL DISPOSITIVO antes de
    capturar), y `matches()` se simplificó para re-hashear exactamente
    `self.files.keys()` en vez de tener que volver a recibir qué formatos
    importaban.
    Tests (Nano 7G suite completa sin cambios de comportamiento — pasa a
    ser "un caso más", no uno especial): `test_plan.py` (+3) — Classic
    construye artwork con SUS format_id (1055/1060/1061/1068, no los de
    Nano 7G); **gate por capacidad del dispositivo, no por disponibilidad
    de fuente** (Shuffle 1G con un track cuyo `source_path` SÍ tiene
    carátula real embebida — la misma fixture que en otros tests SÍ
    produce artwork — sigue en `artwork_touched=False`); fingerprint usa
    los formatos de Classic, no los de Nano 7G. `test_apply.py` (+1):
    round-trip completo de `apply()` para Nano 6G (mismo esquema
    HASHAB/CDB comprimida que Nano 7G, aísla la generalización de formatos
    del eje ortogonal de esquema de firma por family) — instala
    `F1073_1.ithmb`/`F1074_1.ithmb`/`F1085_1.ithmb`/`F1089_1.ithmb`
    reales, no los de Nano 7G. Dos sanity checks de mutación: (a)
    deshabilitar el gate `if cover_art_formats:` — el test de Shuffle 1G
    lo detecta; (b) hacer que `capture()` ignore `artwork_relpaths` (el
    bug real que este bloque encontró) — el test de fingerprint de Classic
    lo detecta. Ambas revertidas. 471 tests tras esto.
  - **Etapa 4f-2 — Auditoría de la tabla de dimensiones contra libgpod.
    Estado: completada para las 12 de 13 families con `supports_artwork`
    que tienen tabla en libgpod (2026-08-19).**
    Fuente: `src/itdb_device.c` de `gtkpod/libgpod` (rama `master`),
    descargado directo con `curl` — **no** vía el resumen de `WebFetch`,
    que en un primer intento fabricó un array `ipod_nano6g_cover_art_info`
    idéntico byte a byte al de Nano 4G (alucinación del modelo resumidor,
    detectada porque dos arrays distintos no deberían ser idénticos, y
    descartada) — grep directo sobre el archivo crudo confirmó que **ese
    array no existe en absoluto** en libgpod. Lección: para auditoría
    contra fuente, bajar el archivo y grepear, no confiar en el resumen.

    Resultado, comparado campo a campo (format_id, width, height,
    pixel_format) contra los arrays reales de libgpod:
    - **Classic (6G/6.5G/7G, comparten `CLASSIC_COVER_ART_FORMATS`)**:
      coincidencia exacta con `ipod_classic_1_cover_art_info` — 1061
      (56×56), 1055 (128×128), 1068 (128×128), 1060 (320×320), los 4 en
      RGB565_LE. libgpod trae su propia nota de incertidumbre sobre 1061
      ("officially 55x55 -- verify!") — no es un gap nuestro, es
      incertidumbre ya presente en la fuente que igual coincide con nuestro
      valor.
    - **Nano 3G**: coincidencia exacta — libgpod reutiliza literalmente el
      array de Classic para 3G Nano (comentario `/* also used for 3G Nano
      */` en la fuente), y así lo tiene ya `capabilities.py` (1061/1055/
      1068/1060), sin que nadie lo hubiera documentado como tal hasta ahora.
    - **Nano 1G/2G**: coincidencia exacta — 1031 (42×42), 1027 (100×100).
    - **Nano 4G**: coincidencia exacta — los 6 formatos (1055/1068/1071/
      1074/1078/1084) con las mismas dimensiones.
    - **Nano 5G**: coincidencia exacta — 1056 (128×128), 1078 (80×80), 1073
      (240×240), 1074 (50×50).
    - **iPod 4G photo/color** (`ipod_photo_cover_art_info`): coincidencia
      exacta — 1017 (56×56), 1016 (140×140).
    - **iPod Video / 5G / 5.5G** (`ipod_video_cover_art_info`): coincidencia
      exacta — 1028 (100×100), 1029 (200×200).
    - **iPod Mobile** (2002/2003, fuera de alcance — ningún device family de
      Cicada lo usa): coincidencia exacta igual, la tabla en sí es fiel
      aunque no esté cableada a ninguna family hoy.
    - **Nano 7G**: no está en libgpod en absoluto (nunca lo soportó) —
      pero es la family con MÁS verificación de todas, contra hardware
      real (4a-4d, fixtures HASHAB reales, prueba de fuego dos veces). No
      necesita auditoría de libgpod, ya tiene algo mejor.
    - **Nano 6G**: **sin poder auditar** — `1085`/`1089` no aparecen en
      libgpod en absoluto (grep sobre el archivo completo, cero
      resultados), y no existe ningún array `nano6g` real en esta fuente
      (confirmado también en el fork `fadingred/libgpod`, idéntico). La
      tabla de Cicada para Nano 6G viene de alguna de las otras fuentes
      citadas en el docstring de `artwork_presets.py` (Keith's photo
      database reader README / cyianor's ithmbrdr README / volcado propio
      de Nano 7G), no de libgpod. **Queda explícitamente en el nivel 3
      (no verificado contra fuente ni hardware)** — el resto de families
      con `supports_artwork` suben a nivel 2 (Classic/Nano1-5G/iPod
      Video/4G photo-color) o ya tenían nivel de hardware real (Nano 7G).
  - **Etapa 4f-3 — RGB565_BE/RGB555 para iPod touch/"Mobile". Diferida, no
    descartada.** No se construye sin que exista primero soporte real de
    Cicada para esa familia de dispositivo (hoy no existe en absoluto, en
    ninguna capacidad) — ese trabajo mayor debe definir su propio diseño,
    no colgar de "generalizar artwork".

### Paquete 8 — `podcasts/` → excluido (Fase 5, `cicada/ipod/db/media/chapters.py`)

**Investigación (2026-08-19):** `src/iopenpod/podcasts/` en el origen no está
vendorizado localmente — auditado bajando cada archivo con `curl` directo
contra GitHub (`raw.githubusercontent.com`), no con `WebFetch` (ver la
lección ya documentada en Etapa 4f-2 sobre resúmenes fabricados).

Son 9 archivos: `artwork.py`, `downloader.py`, `feed_parser.py`,
`itunes_search.py`, `models.py`, `network_errors.py`, `podcast_sync.py`,
`subscription_store.py`, `__init__.py`. **Todos son gestión de feeds RSS,
suscripciones, búsqueda en el directorio de iTunes y descarga HTTP de
episodios** — `feed_parser.py` usa `feedparser` (ya descartado en la §3 del
spec original). Ninguno tiene lógica de escritura de iTunesDB propia; todos
terminan produciendo datos que pasan por `itunesdb_writer`, ya vendorizado
sin depender de nada de este paquete.

**Decisión de alcance (confirmada explícitamente, no un vacío de
documentación):** Cicada no gestiona feeds ni suscripciones — es un gestor
de biblioteca que además escribe al iPod, no un cliente de podcasts. El
alcance de Fase 5 es "el usuario ya tiene el episodio/audiolibro como
archivo local, Cicada lo pone bien en el dispositivo", no "Cicada descarga
episodios nuevos de un feed". Esto corrige una suposición que había quedado
escrita en `ui-ipod.md` §2.5 (contrato de `/podcasts` con `feed_url`, nota
de "conectar con el feed parser de podcasts") — corregida en Etapa 5d.

**Excluido en bloque, sin caso de uso:** `feed_parser.py`, `downloader.py`
(descarga HTTP), `itunes_search.py`, `subscription_store.py`,
`podcast_sync.py` (matching episodio↔track, modos de gestión "newest"/
"next", borrado de episodios viejos — todo asume suscripción activa),
`artwork.py`/`network_errors.py` (soporte del pipeline de descarga).

**Vendorizado parcialmente:** `downloader.py:extract_chapters()` es la
única pieza desacoplada de feeds — toma un `file_path` local y devuelve
capítulos. De sus tres rutas internas se vendorizaron dos, sin dependencias
nuevas (mutagen, ya presente en `requirements.txt`, cubre ambas):
- `_read_nero_chapters` (átomo MP4 `chpl`, bytes crudos)
- `_chapters_from_mp3` (frames ID3v2 `CHAP`)

**Excluido explícitamente:** el fallback `_read_ffprobe_chapters` (pista de
capítulos QuickTime sin átomo Nero) — depende de un binario `ffprobe` que
Cicada no tiene como dependencia hoy (confirmado: no hay ninguna llamada a
`ffmpeg`/`ffprobe` en el código de Cicada). Sin caso de uso: los audiolibros
M4B reales usan casi siempre `chpl`. Diferido, no implementado.

**También excluidos explícitamente, sin caso de uso:**
- `mpeg_audio_type=41` (Audible/AAX): DRM cifrado, Cicada no maneja DRM.
- `MEDIA_TYPE_VIDEO_PODCAST`: requiere el pipeline de video de Fase 6
  (`movie_file_flag`), que no existe todavía.

**Hallazgo de la investigación — nada de esto necesitaba paquete nuevo:**
el soporte de podcasts/audiolibros a nivel de `itunesdb_parser`/
`itunesdb_writer` (Paquetes 3 y 4) **ya estaba completo desde fases
anteriores**, como infraestructura MHOD/MHIT genérica nunca activada:
`write_mhod_podcast_url()`, `write_mhod_chapter_data()` (el
`build_chapter_blob` de la Etapa 2/Community 17), y los campos
`bookmark_time`/`remember_position`/`podcast_flag`/`category` en
`TrackInfo`/`mhit_defs.py`. Confirmado con grep exhaustivo: `create_plan()`/
`apply()` no tienen ninguna lógica condicionada a `media_type` — todo fluye
por el mismo camino genérico que música. Fase 5a-c es enteramente trabajo
de entrada (qué llena `TrackInfo`) y salida (qué lee `/podcasts` y
`/audiobooks`), no de coordinador ni de formato binario nuevo.

**`pc_track_to_info()` (`cicada/ipod/db/writer/_track_conversion.py:159`) —
referencia de diseño no usada, mismo tratamiento que otras piezas
descartadas de iOpenPod.** Ya implementaba la derivación
`media_type→podcast_flag/skip_when_shuffling/remember_position` que
necesitaba 5a, pero recibe un objeto `pc_track` (atributos `.is_podcast`,
`.is_audiobook`, `.video_kind`, `.chapters`) que **no corresponde a ningún
tipo real en Cicada** — es un residuo del propio modelo de biblioteca local
de iOpenPod, nunca instanciado ni llamado desde ningún sitio del código.
**Decisión (2026-08-19):** no se adaptó — envolver una interfaz ajena que no
existe habría sido inventar una capa de traducción innecesaria. La
derivación real (Etapa 5a) se escribió directa en `cicada/ipod/api.py`,
más simple que la función original porque no necesita distinguir video ni
preservar `existing_media_type` (ese caso es para UPDATE, fuera de alcance
de "añadir track nuevo").

#### Etapa 5a — Derivar `media_type`/flags/`category` en la entrada de `/media/sync`. **Estado: implementado y verificado.**

`MediaTrackInput` (api.py) gana `kind: "music" | "podcast" | "audiobook"`
(default `"music"`, validado por Pydantic `Literal`) y `category:
str | None`. En `sync_media()`, `kind="podcast"` setea
`media_type=MEDIA_TYPE_PODCAST`, `podcast_flag=1`,
`skip_when_shuffling=True`, `remember_position=True`; `kind="audiobook"`
setea `media_type=MEDIA_TYPE_AUDIOBOOK` y las mismas dos flags de
reproducción (sin `podcast_flag`, que es específico de podcast).
`kind="music"` (o ausente) no cambia nada del comportamiento previo.

Tests (`tests/ipod/test_api.py`): round-trip real — `POST /media/sync` con
`kind="podcast"`/`"audiobook"`, luego `load_ipod_library()` parseando el
`iTunesCDB` **escrito en disco**, no la respuesta HTTP de otro endpoint de
Cicada ni valores hardcodeados. Mismo patrón de rigor que el round-trip de
Fase 2/4 que ya atrapó dos bugs reales antes. Verificado con mutation
sanity check: se comentó la línea `remember_position=True` del caso
audiobook, el test correspondiente falló exactamente como se esperaba, se
revirtió. Suite completa: 478 tests verdes (475 + 3 nuevos).

#### Etapa 5b — Extracción de capítulos embebidos. **Estado: implementado y verificado.**

`cicada/ipod/db/writer/chapter_extraction.py` (nuevo, vendorizado desde
`downloader.py` @ `c66a4bdb`): `extract_chapters(file_path)` lee el átomo
Nero `chpl` (MP4/M4A/M4B/M4V/MOV) o frames ID3v2 `CHAP` (MP3), devolviendo
`[{"startpos", "title"}, ...]` crudo — la normalización/validación final
(orden, límite, títulos sospechosos) ya la hace
`mhod_writer._normalized_chapters_for_track()`, vendorizada desde Fase 2,
así que no se duplicó.

**Enganche:** decidido en implementación, no en el plan original —
`_prepare_new_tracks()` en `cicada/ipod/db/coordinator/media.py`, junto a
`_read_audio_info()` (que ya probaba length/bitrate/sample_rate del archivo
real para toda pista nueva). Es el mismo mecanismo, agnóstico de `kind`: no
se gateó por `kind="podcast"/"audiobook"` en `api.py` como sugería el plan,
porque no hay motivo real para negarle capítulos a un archivo de música que
los traiga embebidos — la extracción es puramente aditiva (no cambia
`media_type` ni ninguna otra flag) y barata (no-op si el archivo no tiene
capítulos). Efecto colateral correcto: cualquier llamador de
`sync_media_to_ipod`/`_prepare_new_tracks` los recibe gratis, no solo
`POST /media/sync` (también `set_ipod_playlist` con tracks nuevas).

**Hallazgo real durante la verificación (no hipotético — atrapado por el
propio test antes de dar la función por buena):** el código de origen lee
`frame.sub_frames` como lista (`for sub in frame.sub_frames`), pero mutagen
1.47.0 (el pinneado en `requirements.txt`) lo expone como un `ID3Tags`
dict-like (`{"TIT2": TIT2(...)}`, ni siquiera `isinstance(x, dict)` da
`True`) — iterarlo directo da las claves-string, `hasattr(sub, "text")` es
siempre `False`, y el título de cada capítulo caía en silencio al genérico
`"Chapter N"`. El test de capítulos MP3 falló al primer intento con el
código vendorizado tal cual; fix: detectar `hasattr(sub_frames, "values")`
en vez de `isinstance(..., dict)` y desenvolver antes de iterar. Confirmado
con mutation sanity check explícito (revertido el fix, el test volvió a
fallar exactamente igual, se restauró).

Tests: `tests/ipod/db/writer/test_chapter_extraction.py` (7, unitarios —
fixtures de M4B/MP3 construidas byte a byte en el propio test, sin audio
con copyright: átomo `chpl` armado a mano, frames `CHAP` vía mutagen sobre
la fixture MP3 real ya existente; casos negativos: sin capítulos, archivo
inexistente, extensión no soportada, atom `chpl` truncado no debe lanzar).
`tests/ipod/db/coordinator/test_media_sync.py` (+2): round-trip real de
extremo a extremo — `sync_media_to_ipod()` con un `.m4b` con capítulos
Nero, luego `load_ipod_library()` sobre el iTunesCDB escrito en disco
(MHOD 17 real, no el dict de entrada) **y** lectura directa por `sqlite3`
de la tabla `chapter` en `Extras.itdb` (mismo mecanismo que ya usan las
lyrics). Regresión: track sin capítulos no debe dejar `chapter_data` en el
track parseado ni fila en `Extras.itdb`. Mutation sanity check adicional
sobre el enganche en `media.py` (deshabilitado con `if False`, el test de
round-trip falló como se esperaba, se revirtió). Suite completa: 487 tests
verdes (478 + 9 nuevos).

