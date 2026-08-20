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
- Añadida `clean_foreign_artifacts(ipod_path)` (vía `write_guard`), expuesta como
  `cicada ipod clean-foreign`: elimina el `iOpenPodSysInfoAuthority` ajeno del
  dispositivo.

**Hipótesis confirmada con hardware real (2026-08-19)**: en un iPod con residuo real de
iOpenPod que Music.app ya rechazaba, `clean-foreign` + borrado manual de los `.backup`
ajenos —sin tocar `mhbd`/SQLite, sin restaurar— bastó para que Music.app reconociera el
dispositivo completo de nuevo. Detalle y comparación byte a byte del `mhbd`/SQLite
(idénticos entre Cicada e iOpenPod salvo 4 IDs aleatorios esperados) en
`docs/IPOD_INTEGRATION.md` §0.3.

**`clean_foreign_artifacts()` extendida para cubrir también los `.backup` ajenos
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
`clean_foreign_artifacts` pese a que ya cubre más que solo el archivo de autoridad —
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

**Actualización (2026-08-20):** la función vendorizada-pero-nunca-llamada que
dependía de ese `try/except` (`write_itunesdb()`, el punto de entrada de
iOpenPod que combinaba build+firma+instalación en uno, superseded por
`build.py` desde esta misma etapa) se eliminó de `mhbd_writer.py`, junto con
sus helpers privados exclusivos y el bloque de import muerto — hallazgo
colateral de la investigación de Fotos (Etapa 6e), resuelto aparte. Detalle
en Paquete 9. `write_mhbd()` (el builder puro que sí usa `build.py`) sin
cambios.

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

- `consent.py` (propio): Gate de advertencia de divergencia de firma con Music.app de Apple. Persiste consentimiento off-device en `~/.cicada/consent/<sha256(guid)[:16]>.json` con escritura atómica. No re-pregunta si ya fue otorgado. **Se mantiene, no descartado** — la firma HASHAB de Cicada sigue sin ser la de Apple. **Nota resuelta (corregida el 2026-08-19):** el texto del docstring de `consent.py` y del aviso en `cli.py`/`i18n.js` ("invalidará la compatibilidad con Music.app") estaba desactualizado tras confirmar en `docs/IPOD_INTEGRATION.md` §0.3 que Cicada, por sí sola, **no** rompe esa compatibilidad — el riesgo real es residuo de terceros (iOpenPod u otras herramientas) en el dispositivo, no la escritura de Cicada. Corregido en los tres sitios (mecanismo del gate sin tocar, solo el mensaje). `clean_foreign_artifacts()` también se extendió ese mismo día para cubrir los `.backup` ajenos además del archivo de autoridad — ver Etapa 2c/`authority.py` y el detalle completo del hallazgo en la sección "HALLAZGO MAYOR" del historial de esta fase.
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

  **Esquema de verificación de cuatro niveles** (sin hardware de otros
  modelos disponible): (1) *verificado por construcción* — mismo código ya
  probado exhaustivamente en 4c/4d, solo parametrizado con otro
  `ArtworkFormat`; (2) *auditado contra la fuente, no contra runtime* — la
  tabla de dimensiones se transcribió de libgpod (`src/itdb_device.c`,
  citado en el docstring de `artwork_presets.py`), así que se audita por
  diff contra esa fuente, no se re-verifica en ejecución; (3)
  **`hardware_claimed`** — un tercero (iOpenPod) cita una fuente primaria
  de hardware real (no libgpod, no un documento) para un valor que Cicada
  adoptó, con corroboración interna consistente en el propio código del
  tercero, pero sin el dump/fixture original disponible para que Cicada lo
  re-verifique de forma independiente. Más fuerte que "sin fuente" — no es
  una adivinanza ni una copia sin respaldo — pero no equivalente a
  "auditado": no hay nada citable y re-chequeable por diff, solo la
  palabra corroborada de quien sí (afirma) tener el hardware. Nivel
  reutilizable para cualquier caso futuro con esta misma forma (Fotos,
  cuando se retome, es candidato — ver Paquete 9); (4) *marcado
  explícitamente como no verificado en absoluto*, por family, sin
  eufemismos. Se rechazó bit-exactitud contra los codecs de iOpenPod como
  sustituto del nivel 2 — sería circular, ya sabemos que coinciden porque
  es la misma reimplementación ya verificada en 4b.

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
    - **Nano 6G**: `1085`/`1089` no aparecen en libgpod en absoluto (grep
      sobre el archivo completo, cero resultados, confirmado también en el
      fork `fadingred/libgpod`, idéntico) — **descartado el nivel 2**. Los
      otros dos formatos de la misma tupla, `1073` y `1074`, sí están
      auditados: son reuso literal de Nano 5G/Nano 4G, ya confirmados
      arriba.

      **Investigación de la fuente real (2026-08-20)**, motivada por
      evitar repetir "adoptamos porque iOpenPod lo tiene" sin verificar qué
      tiene realmente iOpenPod: se clonó su repo completo (`git clone`, no
      `WebFetch`) y se buscó el commit que introdujo estos valores. Es
      `8348aa8` (`feat: full iTunesCDB support — artist list, compilation
      fix, Nano 6G`, 2026-03-03, antes de la reorganización a
      `device/artwork_presets.py`), con esta nota original junto al array
      `_ART_NANO_6G`:

      > *"Nano 6G uses different format IDs than Nano 5G. Dimensions
      > extracted from a real Nano 6G ArtworkDB (written by iTunes).
      > libgpod has no hardcoded table for Nano 6G and relies on
      > SysInfoExtended; these match the device."*

      No es una cita aislada: el resto de la base de iOpenPod tiene
      múltiples referencias independientes y específicas a hardware Nano
      6G real, en archivos sin relación con artwork —
      `sqlitedb_writer/library_writer.py` ("*Values from a real
      iTunes-synced Nano 6G database: major=1, minor=111,
      device_update_level=1104, platform=2*", "*match a real Nano 6G
      Library.itdb exactly*"), `sqlitedb_writer/locations_writer.py`
      ("*IDs from real iTunes-written databases on Nano 6G*"),
      `itunesdb_writer/mhbd_writer.py` ("*iTunes on Nano 6G writes only
      [4,8,1,3,5]*"). Son detalles numéricos demasiado específicos para
      ser adivinados, y el patrón es consistente entre archivos —
      distinto del incidente de fabricación de Nano 6G de `WebFetch`
      (Etapa 4f-2, arriba), donde la señal de alarma era un array
      *idéntico* a otro ya existente. Acá cada cita es distinta y aporta
      un dato nuevo.

      Lo que **no** se encontró: el dump/backup original. No hay ningún
      fixture de Nano 6G en `tests/fixtures/` de iOpenPod (búsqueda
      explícita, cero resultados) — la fuente vive solo como afirmación en
      comentarios de código, no como archivo verificable.

      **Nivel asignado: `hardware_claimed`.** Se adoptan `1085`/`1089` con
      ese nivel — no "auditado" (nadie, ni iOpenPod ni Cicada, tiene un
      documento fuente citable y re-chequeable por diff, a diferencia de
      libgpod) ni "sin fuente" (hay una afirmación de hardware real,
      corroborada internamente, no una adivinanza). **Sigue sin ser
      verificable de forma independiente por Cicada** hasta que alguien
      con un Nano 6G real pueda confirmarlo contra el dispositivo — el
      resto de families con `supports_artwork` suben a nivel 2
      (Classic/Nano1-5G/iPod Video/4G photo-color) o ya tenían nivel de
      hardware real propio (Nano 7G); Nano 6G queda en su nivel propio,
      por debajo de ambos.
  - **Etapa 4f-3 — RGB565_BE/RGB555 para iPod touch/"Mobile". Sin soporte,
    sin plan de extensión incremental.** No se construye sin que exista
    primero soporte real de Cicada para esa familia de dispositivo (hoy no
    existe en absoluto, en ninguna capacidad, ni parcial). No es un
    "próximamente" del roadmap de artwork: el iPod touch corre iOS y
    sincroniza por un protocolo de dispositivo distinto al de los iPods
    click-wheel/Nano que modela `cicada/ipod/device/` hoy — muy
    probablemente sin el par FireWireGUID/HASHAB del que depende toda la
    identificación y firma actual (`authority.py`, `checksum.py`,
    `device_info.py`). Soportarlo sería un proyecto de integración aparte
    con su propio diseño, no una generalización de artwork ni de ningún
    otro subsistema existente. Documentado también en `README.md` y
    `docs/IPOD_INTEGRATION.md` (§0, nota de alcance).

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

#### Etapa 5c — `GET /podcasts` y `GET /audiobooks` reales. **Estado: implementado y verificado.**

Reemplazados los stubs (`{"podcasts": [], "count": 0}` fijo) por lectura
real de la biblioteca on-device, agrupando por `Album` (con fallback a
`Artist`). `/podcasts` filtra `media_type == MEDIA_TYPE_PODCAST` en
exclusiva — `video_podcast` no se lista (mismo criterio de exclusión que
5a/Paquete 8, requiere el pipeline de Fase 6). Comportamiento alineado con
`/tracks`: sin dispositivo montado, `404 MOUNT_NOT_FOUND` en vez del `200`
vacío que tenía el placeholder (el placeholder nunca tocaba el
dispositivo; la implementación real sí). Helper compartido
`_load_current_library()` extraído de `get_ipod_tracks()` para no
duplicar la resolución `iTunesCDB`/`iTunesDB`.

**Hallazgo que cambió el diseño respecto al plan original (segunda vez en
este bloque — la primera fue el enganche kind-agnóstico de 5b):** el plan
asumía "un audiolibro = un grupo con lista de capítulos" sin más detalle.
Un audiolibro real en un iTunesDB existe de dos formas genuinamente
distintas, y la implementación debe cubrir ambas, no solo la que Cicada
mismo produce:
  - Un solo archivo con capítulos embebidos (MHOD 17 / `chapter_data`) —
    el único camino que Cicada puede escribir hoy (Fase 5b).
  - Varias pistas bajo el mismo `Album`, cada una una parte/capítulo —
    el formato que usan iTunes/iOpenPod para audiolibros multi-pista, y
    que puede existir en un dispositivo real de una sesión anterior
    (mismo espíritu que el round-trip de playlists/ratings: leer
    correctamente lo que ya hay, no solo lo que Cicada mismo escribe).

`get_audiobooks()` distingue por cantidad de pistas en el grupo: más de
una → cada pista es un capítulo (orden por `track_number`), y
`chapter_data` embebido se ignora en ese caso (no debería coexistir con
el split multi-pista real). Exactamente una pista → se expanden sus
capítulos embebidos si los tiene; si no, la pista entera es un único
capítulo (nunca queda un audiolibro con lista de capítulos vacía).

`chapter_data` solo trae `startpos` (posición de inicio), no duración —
`_chapter_durations_ms()` la calcula a partir de los `startpos`
consecutivos, con el último capítulo durando hasta el final de la pista
(`length` del track).

**Corrección de frontend necesaria (fuera del alcance original de 5c pero
inevitable: es la primera vez que estos endpoints devuelven datos
reales):** `ep.date` (string ya formateado, contrato de `ui-ipod.md`) se
cambió a `ep.date_added` (unix ts crudo, igual que el resto de
`TrackSchema`) — no había ninguna convención de fecha-como-string en el
resto de `api.py` que igualar, y mantener la inconsistencia habría sido
peor que corregirla ahora que se implementa por primera vez. Un solo punto
de formato nuevo: `_formatDateAdded()` en `render.js`
(`toLocaleDateString()`, respeta el idioma del navegador). Cache-busting
`render.js`/`ui.js` subido a `2.2.1`. `_mockAddPodcast()` (flujo de UI que
simula "suscribirse a un podcast por nombre" — el propio vestigio del
modelo de feeds que corrige Etapa 5d) ajustado al mismo campo para no
quedar visualmente roto; su corrección de fondo (si debe seguir
existiendo) queda para 5d.

Tests (`tests/ipod/test_api.py`, +8): agrupamiento de 2 episodios reales
del mismo programa (vía `/media/sync` real, no un dict armado a mano);
música normal no aparece en `/podcasts`; audiolibro de una pista con
capítulos Nero reales, verificando duración calculada por capítulo;
audiolibro multi-pista real, verificando orden por `track_number`; 404
sin dispositivo (antes 200 vacío) para ambos endpoints. 3 mutation sanity
checks confirmados (clave de agrupamiento, cómputo de duración de
capítulo, orden multi-pista). Suite completa: 491 tests verdes (487 + 4
netos — el placeholder compartido perdió 2 casos y ganó una prueba 404
dedicada de 2, más 6 pruebas sustantivas nuevas).

#### Etapa 5d — Corrección de documentación. **Estado: cerrado.**

`ui-ipod.md`: §1.1 (tabla de estado) actualizada — `/podcasts`/
`/audiobooks` pasan de placeholder a real, `/media/sync` documenta `kind`
y la extracción de capítulos. §2.5 reescrita: contrato real (sin
`feed_url`, `date` → `date_added` como unix ts crudo, `chapters` con
duración calculada, no una lista pasada tal cual), más un párrafo de
alcance explícito al inicio de la sección (no gestión de feeds/
suscripciones, por qué). §4 ("Guía de Conexión para Próximas Fases"),
ítem 2: corregido — no había ningún feed parser que conectar, los MHOD
15/16/17 ya estaban vendorizados desde antes de Fase 5.

De paso, ya con el contexto cargado: se corrigió también la nota stale de
la Etapa 2c más arriba en este documento (`consent.py`) que decía
"pendiente, no aplicada a propósito" sobre un texto que en realidad ya se
había corregido — drift de cierre de una sesión anterior, detectado al
investigar Fase 5, sin relación de código con esta fase.

**No tocado a propósito:** `_mockAddPodcast()` en `static/js/ipod/ui.js`
sigue con el texto "Nombre del Podcast a **suscribir**" — vestigio visible
del modelo de feeds que corrige esta etapa, pero cambiar su copy o su
comportamiento (p. ej. conectarlo a un flujo real de "agregar archivo con
kind=podcast") es una decisión de UI/UX que nadie pidió todavía; solo se
ajustó el campo `date`→`date_added` para que no quedara visualmente roto
tras el cambio de contrato de 5c. Ítems 1 y 3 de §4 (Fase 4 ya cerrada
figurando como "próxima fase"; versión de cache-busting de ejemplo
desactualizada) detectados de pasada, fuera de alcance de Fase 5, sin
tocar.

### Paquete 9 — Fase 6: Video (implementado) y Fotos (diferido)

**Investigación inicial (2026-08-19) — incompleta, corregida el mismo
día.** La primera pasada auditó `src/iopenpod/` buscando un paquete de
dominio nombrado `photodb_*` o con prefijo `photo`, y concluyó que
iOpenPod no implementa fotos. **Esa conclusión era falsa** — el hueco fue
metodológico: nunca se buscó *dentro* de `sync/` (ya vendorizado
parcialmente, Paquete 6) ni con raíces `album`/`thumb`/`image`. El usuario
aportó evidencia directa (captura de la GUI real de iOpenPod, con una
sección "Photos" completa) que forzó la re-investigación. No es el mismo
tipo de hueco que Nano 6G en 4f-2 (ahí `WebFetch` fabricó datos
inexistentes) — acá la búsqueda fue genuina pero insuficientemente amplia.
Mismo principio aplicado: no aceptar la primera conclusión negativa sin
descartar huecos de búsqueda, evidencia de un lado a otro.

**Lo que existe realmente: `src/iopenpod/sync/photos.py`, 2706 líneas,
implementación completa y probada (MIT).** Parser y escritor completos —
no un mockup de GUI. Tests reales: `tests/test_photo_path_safety.py` (285
líneas: rechazo de path traversal, symlink escape, "Photo Database"
corrupta falla cerrado), `tests/test_photo_encoding.py`,
`tests/test_photo_planning.py`. La GUI (`gui/widgets/photo{Browser,Tile,
Viewer}.py`, `pooledPhotoGrid.py`) es una capa Qt separada encima —
confirmado cero imports de Qt en `photos.py` mismo.

**Formato — no es un formato nuevo, es el que ya está vendorizado.**
"Photo Database" usa el mismo árbol de chunks
`mhfd→mhsd→{mhli,mhla,mhlf}→mhii→{mhod,mhni}` que ArtworkDB (Etapa 4c) —
tamaños de header idénticos byte a byte (`MHFD`=132, `MHSD`=96, `MHLI`=92,
`MHLA`=92, `MHLF`=92, `MHII`=152, `MHOD`=24, `MHNI`=76, confirmado contra
`chunks.py`). No es casualidad: `chunks.py` ya escribe `write_mhla()` y
`write_mhlf()` — vacíos porque ArtworkDB nunca necesitó álbumes reales,
pero el contenedor MHFD de ArtworkDB siempre incluyó esos tres datasets
(imagen/álbumes/archivos) desde 4c. Lo único que falta a nivel de chunk
son `mhba`/`mhia` (entrada de álbum + membresía) — no existen en
`chunks.py` hoy, pero son ~40 líneas en el original (`_write_mhba`/
`_write_mhia` en `photos.py`), no un formato nuevo.

**Pixel format — RGB565_LE confirmado para Nano 7G (1005/1007,
`artwork_presets.py`), mismo códec que cover art.** `photos.py` llama a
`ithmb_codecs.encode_image_for_format()`/`decode_pixels_for_format()`/
`expected_size_bytes()` — un módulo que **no se porta completo** en 4b
(`rgb565.py` es una reimplementación deliberadamente más angosta, solo
RGB565_LE, documentado en la Etapa 4b de este mismo archivo). Para Nano 7G
el códec actual alcanza — hace falta un adaptador delgado de firma de
función (`convert_art_for_format` vs `encode_image_for_format`), no un
codec nuevo. La nota de la Etapa 4f-2 más abajo en este documento ya
señalaba que los formatos no-LE son "de fotos (slideshow) o salida de TV,
subsistema photo_formats, Fase 6" — la investigación inicial de Fase 6 no
cruzó ese hallazgo propio al arrancar de cero.

**Infraestructura ya vendorizada, reutilizable directo:**
`device/durability.py`, `device/path_safety.py`,
`device/storage_safety.py` — los tres del Paquete 2, sin cambios.

**Punto de adaptación real para cuando se retome (no un bloqueador, un
diseño a resolver primero):** `_photo_mapping_path()` de iOpenPod escribe
`iPod_Control/iOpenPod/photo_sync.json` **en el dispositivo**, bajo
namespace ajeno — misma categoría de residuo que `SysInfoAuthority`
(Etapa 2c, mucho menos invasivo: un JSON namespaced, no reescritura de
SysInfo). Mismo tratamiento que `authority.py` ya aplica: ese estado debe
ir off-device, no al iPod.

`supports_photo`/`photo_formats`/`max_video_width/height/bitrate/fps`/
`h264_level` en `capabilities.py` siguen siendo metadata correcta pero
inerte hasta que se construya el escritor — nada las consume todavía
(confirmado por grep). No estaban mal, solo sin usar.

**Fotos — diferido, no descartado. Motivo real: dimensión del trabajo, no
falta de referencia.** Existe una referencia Python completa, probada,
MIT (`sync/photos.py`), que reutiliza infraestructura y formato ya
vendorizados. Lo que falta es ~2700 líneas de dominio nuevo por adaptar —
comparable en tamaño a toda la Fase 4 (4a-4f) junta. Investigación
profunda y troceado completo cerrados el 2026-08-20 (ver más abajo);
implementación en curso, etapa por etapa, con el mismo rigor que cada
fase anterior.

#### Investigación profunda de Fotos (2026-08-20)

Lectura completa de `sync/photos.py` (2706 líneas), comparada byte a byte
contra `chunks.py`/`rgb565.py` de Cicada.

**Chunks que faltan — layout exacto extraído del propio `photos.py`:**
`MHBA` (148 bytes: `album_id`@20, `album_type`@30, `playmusic`@31,
`repeat`@32, `random`@33, `show_titles`@34, `transition_direction`@35,
`slide_duration`@36 u32, `transition_duration`@40 u32, `song_id`@52 u64,
`prev_album_id`@60, más `MHOD` tipo 1 con el nombre e hijos `MHIA`) y
`MHIA` (40 bytes: solo `image_id`@16). `write_mhla()` de Cicada hoy es un
stub de 0 álbumes (cover art no los necesita); Fotos necesita álbumes
reales. **Matiz no visto antes**: el `MHII` de Fotos usa offsets 40/44/48
para `created_at`/`digitized_at`/`original_size`, mientras el `MHII` de
cover art usa offset 20 para `song_id`/`db_track_id` — mismo tamaño de
header (152 bytes), semántica de campos distinta. `write_mhii()` de
Cicada no es reusable tal cual para Fotos, hace falta una variante
paralela.

**Pixel format — corrección de lo asumido en la investigación anterior.**
No es un solo "adaptador delgado": `rgb888_to_rgb565_le()` (el
empaquetado de píxeles puro, en `rgb565.py`) sí es directamente reusable,
cero cambios — ya es agnóstico a width/height/stride. Pero
`resize_for_format()` (mismo archivo) **no sirve para Fotos**: hace
`resize` directo sin preservar aspect ratio ("la carátula es cuadrada por
convención, está bien estirarla"), comportamiento que Fotos nunca puede
usar. Fotos necesita la política de `_fit_photo_to_format()`/
`_should_rotate_tall_photo_for_format()` de `photos.py` — fit + padding
simétrico + rotación condicional de fotos verticales — que no existe en
Cicada hoy, y hay que portarla como lógica nueva.

**Residuo on-device confirmado**: `_PHOTO_MAPPING_RELATIVE =
"iPod_Control/iOpenPod/photo_sync.json"` — mismo patrón que
`iOpenPodSysInfoAuthority` (Etapa 2b). Rediseño off-device: Etapa 6e.

**Infraestructura adicional necesaria, no registrada en la investigación
inicial** — `photos.py` importa de tres módulos de iOpenPod que Cicada no
tenía: `path_safety.py` (140 líneas, `resolve_device_path()`/
`UnsafeDevicePathError`), `storage_safety.py` (104 líneas,
`require_file_size_supported()`) y `filesystem_profile.py` (**633
líneas**, detección de filesystem cross-platform). Decisión: portar
`path_safety.py` casi tal cual y una versión reducida de
`storage_safety.py` (solo `require_file_size_supported` + una tabla
estática de techos por tipo de filesystem), **sin** portar
`filesystem_profile.py` completo — para el único dato que hace falta
(techo de tamaño de archivo), alcanza con reusar la llamada a `diskutil
info -plist` que `volume_id.py` ya hace para `VolumeUUID`, leyendo
también su campo `FilesystemType` (verificado contra el Nano 7G real
conectado: `FilesystemType`=`"msdos"`, `FilesystemName`=`"MS-DOS
FAT32"`). 633 líneas de detección cross-platform para ese único chequeo
habría sido sobre-alcance.

**Dependencia diferida, no descartada: HEIC/HEIF.**
`PHOTO_EXTENSIONS` de iOpenPod incluye `.heic`/`.heif` (fotos de iPhone).
Pillow estándar no los decodifica sin el plugin `pillow-heif`, que Cicada
no tiene instalado. Caso real fuera de alcance hoy, no "innecesario" —
las imágenes de prueba disponibles (`Magallanes 120/*.jpg`) son JPEG, así
que no bloquea el troceado aprobado; si se retoma, requiere agregar
`pillow-heif` a `requirements.txt`.

**Coordinación con `create_plan()`/`apply()`: coordinador propio, no
extensión del `Plan`.** Verificado en `sync_executor.py` de iOpenPod:
fotos corre como un paso separado del pipeline, gateado por
`supports_photo`, con su propia base de datos, sin relación
`track_id`↔foto. Traducido a Cicada: un coordinador nuevo
(`cicada/ipod/db/coordinator/photos.py`, análogo a `media.py`), no una
extensión de `Plan`/`apply()` — Fotos no tiene nada que fusionar con el
iTunesDB/SQLite de música, así que no hace falta tocar
`PreStateFingerprint` ni el `Plan` dataclass.

**Recorte de alcance deliberado, el más grande disponible**: `photos.py`
implementa dos caminos de escritura — reescritura completa desde cero
(`_write_photo_db_snapshot`, ~150 líneas) e **incremental con
compactación in-place de los `.ithmb`**
(`_apply_photo_sync_plan_incremental` + `_compact_photo_thumb_payloads`,
~600 líneas). `chunks.py` (Fase 4c) ya declaró la filosofía de "reescribe
completo en cada sync, sin preservación" para ArtworkDB — la misma
filosofía aplicada a Fotos descarta esas ~600 líneas de complejidad de
compactación. Coherente con el resto de Cicada, no una concesión.

**Troceado aprobado (orden ajustado explícitamente: validar contra
hardware real antes de construir la capa de API, mismo patrón que Fase
2):**
- **6e** — Infra de soporte: `path_safety.py`, `storage_safety.py`
  reducido, mapa off-device de fotos (patrón `authority.py`).
- **6f** — Chunks nuevos en `chunks.py`: `write_mhba`/`write_mhia`,
  variante de `write_mhii` con semántica de Fotos, lectura.
- **6g** — Procesamiento de imagen: fit/pad/rotate portado, reusando
  `rgb888_to_rgb565_le` sin cambios.
- **6h** — Coordinador `sync_photos_to_ipod()`.
- **6j** — Prueba de fuego con las dos imágenes reales de Magallanes 120
  (antes de la API, no después).
- **6i** — API/CLI: `POST /photos/sync`, reemplazo del stub `GET
  /photos`, `DELETE /photos/{id}`.

#### Etapa 6e — Infra de soporte para Fotos (`path_safety.py`, `storage_safety.py`, mapa off-device). **Estado: implementado y verificado.**

**`cicada/ipod/device/path_safety.py`** (nuevo) — `resolve_device_path()`/
`UnsafeDevicePathError`, adaptado casi tal cual de iOpenPod. Solo se
portó lo que `photos.py` (futuro) necesita: se omitió
`resolve_host_path`/`UnsafeHostPathError` de iOpenPod (valida rutas de
host absolutas contra una raíz) por no tener caso de uso hoy en Cicada.
Doble capa contra symlinks: rechazo explícito por componente
(`_reject_link_or_reparse_components`, walk con `os.lstat`) más el
chequeo final basado en `Path.resolve()` — confirmado con un mutation
check que intentar romper solo la primera capa no hace fallar el
resultado agregado (la segunda lo sigue atrapando), así que el sanity
check de mutación se probó contra `_reject_link_or_reparse_components()`
en aislamiento, no contra el wrapper completo.

**`cicada/ipod/device/storage_safety.py`** (nuevo, reducido respecto a
iOpenPod) — `require_file_size_supported()` + `FileSizeLimitError`
(subclase de `WriteGuardError`, no de un `DeviceWriteSafetyError` que
Cicada no tiene) + `max_file_size_bytes_for_mount()` con la misma tabla
de techos por filesystem que iOpenPod (`msdos`/`fat32`/`vfat`→4GiB-1,
`fat`/`fat16`→2GiB-1).

**`cicada/ipod/device/volume_id.py`** (extendido) — nueva función
`filesystem_type(mount)`, que reusa la llamada existente a `diskutil info
-plist` de `volume_fingerprint()` (un campo más del mismo plist,
`FilesystemType`, no un segundo proceso). Verificado contra hardware
real, no una fixture: el Nano 7G conectado reporta `"msdos"`
(2026-08-20). Solo macOS, igual que el resto del módulo.

**`cicada/ipod/device/photo_mapping.py`** (nuevo) — reimplementación
off-device de `photo_sync.json`, mismo patrón que `authority.py` pero
usando el helper centralizado `cicada.ipod.paths.guid_hash()` (que
`authority.py` predata y no usa — no se tocó, fuera de alcance de esta
etapa) en vez de una duplicación local del hash. Persiste en
`~/.cicada/photos/<guid_hash>/mapping.json`, indexado por FireWireGUID,
reemplazo atómico simple (`tmp` + `os.replace`) — no la maquinaria
pesada de `durability.py` (fsync agresivo, pensada para escrituras al
propio volumen del iPod con riesgo de eject a mitad de escritura; este
mapa vive en el filesystem del host). Falla cerrado
(`PhotoMappingSafetyError`) ante JSON malformado o con forma inesperada,
mismo criterio que `_load_photo_mapping` de iOpenPod.

**Tests** (36 nuevos, 536 en total): `test_path_safety.py` (10, incluye
symlink-escape con mutation check en aislamiento), `test_storage_safety.py`
(9, incluye mutation check real por inyección de bug — comparación
`size < limit` en vez de `size <= limit`, confirmado que falla, revertido),
`test_photo_mapping.py` (12, round-trip real de entradas y de settings,
indexado por GUID no por montaje, atomicidad, fallo cerrado ante datos
corruptos — mutation check real por inyección de bug, quitando la
validación de forma de entrada, confirmado que falla, revertido), 5
nuevos en `test_vpd_2d.py` para `filesystem_type()` (incluye un test
`skipif` que corre contra el Nano 7G real cuando está montado, sin mock,
en vez de solo contra una fixture — round-trip real donde el dispositivo
puede verificar).

**Hallazgo colateral, resuelto aparte (2026-08-20, no como parte de 6e):**
`mhbd_writer.py` tenía un bloque de import con fallback (`try: from
iopenpod.device.path_safety import ... except ImportError: ... = None`)
que asumía que estos módulos algún día se importarían del paquete
`iopenpod` real — nunca ocurre en Cicada, así que siempre caía al
fallback `None`. La función que los usaba, `write_itunesdb()`, y sus
helpers privados (`_preflight_database_install`, `_database_filename_for_
capabilities`, `_resolve_existing_itdb_for_write`, `_copy_device_file_
durably`, `_run_before_mutation`, `_cleanup_device_temp`) **no tenían
ningún caller en el código activo de Cicada** (`build.py` reimplementó la
entrada de escritura por su cuenta) — confirmado por grep antes y después
del cambio. Eliminados junto con los imports que quedaban exclusivamente
a su servicio (`durability.py` completo, `hash58`/`hashab` de este
módulo, `MHBD_OFFSET_HASHING_SCHEME`, `Callable`/`Path`/`os`/`shutil`/
`stat` — cada uno verificado individualmente por grep de que su único
uso caía dentro del bloque muerto antes de tocarlo). `write_mhbd()` (el
builder puro que sí usa `build.py`) y el resto de `mhbd_writer.py`
intactos. Verificado con `pyflakes` (cero imports sin usar tras el
cambio) y suite completa (536 tests, mismo piso que antes). Detalle
completo de la vendorización original de `write_itunesdb`/`hash72` con
`try/except ImportError` deliberado: Paquete 4, Etapa 2a, arriba —
**esa función ya estaba documentada ahí como vendorizada-pero-nunca-
llamada desde el día uno** ("Cicada no llama esas vías"); esta entrada
registra que finalmente se eliminó, no que se descubrió.

#### Etapa 6f — Chunks `mhba`/`mhia` + variante de `mhii`/`mhni` con semántica de Fotos, en `chunks.py`. **Estado: implementado y verificado.**

Todo en `cicada/ipod/db/artwork/chunks.py` (mismo módulo que ArtworkDB,
no uno nuevo — comparten contenedor, ver docstring del módulo actualizado
en esta etapa) y `types.py` (nuevo `PhotoAlbumInput`, dataclass frozen
igual que `EncodedFormatPayload`).

**Nuevo, aditivo, cero cambio de comportamiento en cover art:**
- `write_mhia(image_id) -> bytes` — MHIA de 40 bytes, solo `image_id`@16.
- `write_mhba(album: PhotoAlbumInput) -> bytes` — MHBA de 148 bytes:
  nombre (MHOD tipo `ALBUM_NAME`, valor nuevo en `ArtworkMhodType`, no
  usado por cover art) + un `mhia` por miembro. Los 10 campos de
  slideshow/reproducción (`album_type`/`playmusic`/`repeat`/`random`/
  `show_titles`/`transition_direction`/`slide_duration`/
  `transition_duration`/`song_id`/`prev_album_id`) van todos, con default
  0 — son parte fija del layout binario, no una capacidad opcional.
- `write_mhni_photo`/`write_mhii_photo` — variantes de `write_mhni`/
  `write_mhii`, **funciones separadas, no una generalización de las
  existentes**. Motivo, verificado con test de offset crudo
  (`test_mhii_photo_offset_20_no_es_song_id`), no solo documentado: el
  `MHII` de Fotos deja el offset 20 (donde cover art guarda `song_id`/
  `db_track_id` como u64) sin usar, y guarda `created_at`/`digitized_at`/
  `original_size` en 40/44/48 — mismo tamaño de header (152 bytes),
  semántica incompatible. El `MHNI` de Fotos también difiere: la ruta del
  archivo hijo (`MHOD` tipo `FILE_NAME`) es una ruta relativa completa con
  convención HFS multi-segmento (`":Full Resolution:iOpenPod:foto.jpg"`,
  vía nuevas `photo_rel_path_to_db_string`/`photo_db_string_to_rel_path`),
  no un nombre de archivo plano como en cover art.
- `write_mhla()` extendida con un parámetro opcional `mhba_blobs` (default
  `None` → 0 álbumes, **byte a byte igual que antes** — verificado con
  test de regresión dedicado). `write_mhfd()` extendida con `unknown2`
  keyword-only, default `2` (cover art, sin cambio) — Fotos pasa `6`
  (valor empírico de `_DEFAULT_MHFD_UNKNOWN2` en `sync/photos.py`,
  "Empirical iTunes-written databases across Nano 2/6/7 all use 6").
- `build_photo_db()` — assembler nuevo, paralelo a `build_artworkdb()`
  (no lo reemplaza ni lo llama): mismo MHFD→3×MHSD, con álbumes reales en
  el dataset `PHOTO_ALBUM_LIST` (que `build_artworkdb` siempre deja
  vacío) y `unknown2=6`.
- Lectura: `_parse_mhia`/`_parse_mhba`/`_parse_mhni_photo`/
  `_parse_mhii_photo` + `read_photo_db(data) -> (images, albums)`,
  paralelo a `read_artworkdb` sin tocarlo — reusar el parser de cover art
  para Fotos leería `created_at` como parte de un `song_id` inexistente,
  en silencio.

**Rigor de test (mismo criterio que 4c, reforzado):** el hallazgo de la
investigación de Fotos fue exactamente "mismo tamaño de header, semántica
de campos incompatible" — un round-trip puramente interno (escribir con
esta función, leer con su propio parser) no detectaría un bug simétrico
en ambos lados. Por eso varios tests de
`tests/ipod/db/artwork/test_chunks_photo.py` (14 nuevos) desempaquetan
bytes crudos con `struct` directo contra los offsets documentados, en vez
de pasar solo por las funciones del módulo — en particular
`test_mhii_photo_offset_20_no_es_song_id` (offset 20 en cero, no
interpretable como song_id) y `test_mhba_layout_exacto_todos_los_campos`
(los 13 campos del MHBA, uno por uno, contra sus offsets exactos). Dos
mutation checks reales por inyección de bug en el archivo fuente,
confirmados y revertidos: (a) `created_at` escrito por error en offset 20
(el slot de cover art) en vez de 40 — detectado; (b) `album_type`/
`playmusic` con posiciones de byte intercambiadas en `write_mhba` —
detectado. Suite completa: 550 tests verdes (536 + 14).

#### Etapa 6g — Procesamiento de imagen: fit/pad/rotate de fotos, en `photo_fit.py` nuevo. **Estado: implementado y verificado.**

`cicada/ipod/db/artwork/photo_fit.py` (nuevo, colocado junto a
`rgb565.py` — comparten dominio de codificación, no orquestación).
Bloque deliberadamente aislado del coordinador (Etapa 6h, todavía sin
construir): esta es la lógica con superficie de error real (aspect
ratio, padding simétrico, rotación condicional), decisión explícita del
usuario de no mezclarla con el diseño del coordinador para poder aislar
causas si algo falla más adelante.

Portado de `_fit_dimensions`/`_fitted_area`/
`_should_rotate_tall_photo_for_format`/`_fit_photo_to_format` en
`sync/photos.py` de iOpenPod, prácticamente literal (mismos umbrales:
aspecto 1.15, ganancia de rotación 1.2). **Confirma, con código real
además de con la investigación previa, que `rgb888_to_rgb565_le` de
`rgb565.py` (Etapa 4b) es reusable sin cambios** — el nuevo
`encode_photo_for_format()` lo llama tal cual, ningún ajuste. Lo que
faltaba era la política de fit/pad/rotate, no el codec — exactamente como
se documentó en la investigación de Fotos.

A diferencia de `resize_for_format()` (cover art, Etapa 4b, estira sin
preservar aspecto porque una carátula tolera eso): `fit_photo_to_format()`
**nunca estira** — fit preservando aspecto + padding negro simétrico
(con ajuste de paridad para que el padding se pueda partir en mitades
enteras por lado), salvo para roles de miniatura (`photo_thumb`/
`photo_list`) sin `fit_thumbnails`, que usan zoom-and-crop-to-fill (igual
que iTunes). `should_rotate_tall_photo_for_format()` decide rotar 270°
una foto más alta que ancha solo cuando (a) el formato destino tiene un
rol rotable, (b) el aspect ratio supera 1.15, y (c) rotar realmente gana
al menos 20% más de área aprovechada — **no todo formato "vertical
fuente" conviene rotarlo**: contra el `FULL_FMT` real del Nano 7G
(480×864, vertical), rotar una foto alta la vuelve horizontal, que encaja
peor en un target vertical — verificado con test dedicado
(`test_formato_vertical_real_del_nano7g_no_gana_rotando`), no asumido.

**Rigor de test**: 26 tests nuevos
(`tests/ipod/db/artwork/test_photo_fit.py`), con los tres casos de aspect
ratio pedidos (foto más ancha, más alta, exactamente cuadrada) verificados
dimensión a dimensión (`fit_dimensions`/`fit_photo_to_format`) y píxel a
píxel (decodificando el RGB565 real de vuelta con
`rgb565_le_to_rgb888` y comprobando que las franjas de padding son negro
exacto y el contenido reproduce el color original dentro del margen de
cuantización RGB565 empírico — 7 en R/B de 5 bits, 3 en G de 6 bits,
medido, no asumido en ±4 como un primer intento demasiado ajustado que
falló). Dos mutation checks reales por inyección de bug en el archivo
fuente, confirmados y revertidos: (a) se quitó el ajuste de paridad del
padding — 4 tests lo detectaron; (b) se quitó el umbral de ganancia de
`should_rotate_tall_photo_for_format` (rotaba con cualquier mejora, no
solo ≥20%) — detectado. Suite completa: 576 tests verdes (550 + 26).

#### Etapa 6h — Coordinador `sync_photos_to_ipod()`, en `cicada/ipod/db/coordinator/photos.py` nuevo. **Estado: implementado y verificado.**

Análogo a `media.py` (Fase 3), NO extensión de `Plan`/`apply()` — Fotos
no tiene relación con tracks/playlists, así que tiene su propia secuencia
de backup/stage/commit/verificación-post-commit/rollback, calcada de la
disciplina de `apply.py` (Etapa 2c): precondiciones → backup verificado →
staging con fsync (`.cicada-new`) → commit por renames (full-res/thumbs
antes que la DB, mismo criterio que ArtworkDB-antes-que-iTunesCDB en
4d) → verificación post-commit releyendo lo instalado (no lo que el
código dice haber escrito) → rollback inmediato ante cualquier fallo
desde el backup en adelante. Sin gate de consentimiento de Music.app:
ese gate existe porque reescribir el iTunesCDB re-firma HASHAB (§0.3);
Fotos nunca toca el iTunesCDB, no hay riesgo análogo que gatear —
decisión de diseño explícita, no un descuido.

**Hallazgo arquitectónico real, encontrado por ejecución real, no
supuesto** (Fase 6h, 2026-08-20): `write_guard.py` confina TODO a
`<mount>/iPod_Control/` desde Fase 0 — pero `Photos/` vive a **nivel de
volumen**, fuera de `iPod_Control/` (confirmado contra `sync/photos.py`
de iOpenPod, `_PHOTO_DB_RELATIVE = Path("Photos")/"Photo Database"`, sin
prefijo `iPod_Control`, y reproducido en vivo:
`PathOutsideIpodControlError` real al intentar escribir el primer
archivo de prueba). Esto rompía tres módulos a la vez: `write_guard.py`
(`assert_within_ipod_control`), `safe_write.py` (sus wrappers `guarded_*`
llaman a ese mismo assert) y `backup.py` (`_scope_roots` anidaba
`Photos/` bajo `iPod_Control/`, que tampoco es donde vive en un
dispositivo real). Todo lo que Cicada había escrito hasta ahora — Music/,
iTunes/, Artwork/, Device/ — vive bajo `iPod_Control/`, así que este
supuesto nunca se había puesto a prueba; Fotos es lo primero que lo
rompe. Presentado al usuario con dos opciones (generalizar
`write_guard.py` con una segunda raíz segura explícita vs. una capa
paralela solo para Fotos reusando `path_safety.py`); **elegida la
primera** — una sola autoridad de "qué es seguro escribir" para todo el
proyecto, no dos.

**Extensión de `write_guard.py`** (mismo invariante central, no
reemplazado): `assert_within_ipod_control`/`assert_deletable`/
`safe_rmtree` ganan un parámetro `root: str = IPOD_CONTROL_DIRNAME`
keyword-only — default preserva el comportamiento exacto de antes de 6h
para **todo** el resto del proyecto (nadie más pasa `root=`), y
`root=PHOTOS_DIRNAME` (nueva constante exportada) confina a `Photos/`
explícitamente, nunca por default — ampliar la raíz segura es una
decisión consciente en cada call site. `Photos/` se agregó a
`_protected_dirs()`: nunca se puede `rmtree` completa, mismo trato que
`iPod_Control/`/`iPod_Control/iTunes/`. `safe_write.py` (`guarded_durable_
replace`/`guarded_durable_publish_new`/`guarded_durable_unlink`) recibió
el mismo parámetro, delegando sin más lógica propia.

**Corrección de `backup.py`** (el `include_photos` añadido en 6e estaba
mal — asumía `Photos/` anidada bajo `iPod_Control/`, corregido aquí
antes de que se usara en producción): `_scope_roots()` trata `Photos/`
como raíz de volumen independiente, no como subdirectorio de `control`.
`BackupMode.FULL` ahora también cubre `Photos/` siempre que exista (sin
necesitar `include_photos`, igual que ya cubre `Music/` sin flag
especial — FULL es "todo el dispositivo"). `restore_backup()` reescrita
para resolver la raíz de guardia correcta (`iPod_Control` o `Photos`)
por cada miembro del tar (`_guard_root_for_member()`), incluida la
poda de directorios sobrantes y el `safe_rmtree` de directorios no
vacíos — antes estos habrían fallado con `PathOutsideIpodControlError`
al intentar reconciliar cualquier cosa bajo `Photos/`.

**Resto del coordinador** (`photos.py`): `image_id` estable entre syncs
por hash visual, resuelto contra el mapa off-device (`photo_mapping.py`,
6e) — nunca contra el dispositivo. Álbum maestro "Photo Library" siempre
presente con todas las fotos; álbumes nombrados desde el nombre del
subdirectorio de origen (mismo criterio que `scan_pc_photos` de
iOpenPod). Optimización: si el diff (agregadas/removidas) es vacío
contra la última sync, no se crea backup ni se escribe nada — mismo
criterio que `artwork_touched=False` en `create_plan()`.

**No implementado en este bloque, gap documentado, no descubierto por
accidente**: sin equivalente de `PreStateFingerprint` (Etapa 2c/4f-1)
para Fotos — no se detecta si algo modificó `Photos/` por fuera de
Cicada entre dos syncs. Fuera del alcance pedido para 6h (backup +
verificación post-commit + rollback, no detección de deriva de
pre-estado); candidato para una etapa futura si se vuelve necesario.

**Tests** (30 nuevos, 604 en total): 6 en `test_write_guard.py` para
`root=` (incluye que el default no cambió para nadie más, que
`root=PHOTOS_DIRNAME` no es un bypass general — sigue rechazando
`iPod_Control/` —, y que `Photos/` está protegida de `rmtree` completo);
9 en `test_backup.py` (`include_photos` no anida bajo `iPod_Control/`,
`FULL` cubre `Photos/` sin flag, round-trip real de backup/restore sobre
`Photos/`, que restore de Fotos no toca `iPod_Control/` y viceversa, el
mismo bug de "backup tomado antes de que la carpeta existiera" que se
corrigió para Artwork/ en 4d, y que restore nunca hace `rmtree` de
`Photos/` completa — vía monkeypatch de `shutil.rmtree`, mismo patrón que
el test ya existente para `iPod_Control/`); 15 en
`tests/ipod/db/coordinator/test_photos.py` (dedup por hash visual real —
no por ruta —, álbumes desde subdirectorio, round-trip completo
releyendo `read_photo_db()` de lo instalado en disco, `image_id` estable
entre dos syncs reales, borrado de full-res al remover una foto, sync
sin cambios es no-op sin backup nuevo, rollback real ante fallo de
verificación post-commit con el estado del dispositivo verificado byte a
byte igual al previo, sin temporales `.cicada-new` huérfanos tras el
rollback). Cuatro mutation checks reales por inyección de bug en el
archivo fuente, confirmados y revertidos: (a) enrutamiento de raíz de
`backup.py` roto (siempre `iPod_Control`, ignora `Photos/`) — 3 tests lo
detectan; (b) optimización de no-op quitada — detectado; (c) estabilidad
de `image_id` deshabilitada — 2 tests lo detectan.

**Verificado con ejecución real, no solo con la suite**: se corrió
`sync_photos_to_ipod()` a mano contra un árbol de iPod simulado con
fotos sintéticas reales (PIL) antes de escribir los tests formales —
así se encontró el hallazgo arquitectónico de arriba, que ningún mock
habría revelado.

**Revisión del usuario (2026-08-20) antes de dar 6h por cerrada — mismo
escrutinio que el fingerprint de `PreStateFingerprint` en 4f-1, por
tratarse de un cambio a un mecanismo de seguridad central.** Encontró un
hueco real en la primera versión: `root: str` en `assert_within_ipod_control`/
`assert_deletable`/`safe_rmtree` no tenía whitelist — cualquier caller
podía pasar `root="lo-que-sea"` y la función confinaría a esa raíz
arbitraria sin objetar, degradando el confinador central de "dos raíces
conocidas y auditadas" a "cualquier nombre que alguien pase". Corregido
con `_ALLOWED_ROOTS = frozenset({IPOD_CONTROL_DIRNAME, PHOTOS_DIRNAME})`,
verificado en `_control_dir()` antes de tocar el filesystem — un tercer
valor lanza `ValueError` de inmediato. Confirmado con mutation check real
(quitar la whitelist, ver el test fallar, revertir) y con grep exhaustivo
de que ningún caller pre-6h (`plan.py`/`media.py`/`apply.py`/
`authority.py`) pasa `root=` — todos usan el default, byte a byte el
mismo valor que antes de esta etapa. 1 test nuevo
(`test_root_arbitrario_no_conocido_es_rechazado`). 605 tests verdes.

#### Etapa 6j — Prueba de fuego en hardware real (Nano 7G), con las dos imágenes reales de Magallanes 120. **Estado: verificado en el dispositivo.**

Antes de construir la API/CLI (6i), tal como quedó reordenado: mismo
protocolo que las pruebas de fuego anteriores (Fase 4, video en 6c).
`sync_photos_to_ipod()` invocado directo (sin API, todavía no existe)
contra el Nano 7G real conectado (`read_device_info()` real, sin mocks:
`iPod Nano 7th Gen`, GUID `000A27002484DDFB`, `guid_is_write_safe=True`),
con `img20260322_14485213.jpg` (69.8 MB, 11376×8480) e
`img20260322_15243486.jpg` (46.7 MB, 11392×8368) — las dos imágenes
exactas que el usuario indicó, aisladas en un directorio aparte (symlinks)
para no sincronizar sin querer el resto de la carpeta `Magallanes 120/`
(64 archivos).

**Resultado**: `success=True`, 2 fotos, 1 álbum ("Photo Library"), backup
verificado creado, ~14s de principio a fin. Verificado releyendo lo
REALMENTE instalado en el dispositivo, no solo el resultado del código:
`read_photo_db()` sobre el `Photo Database` real — 2 imágenes, tamaños
originales exactos, offsets de miniatura secuenciales sin solape
(`F1005_1.ithmb`: 12800/12800 bytes; `F1007_1.ithmb`: 829440/829440
bytes, ambos exactos para 80×80 y 480×864 en RGB565_LE sin padding de
stride). Los dos JPEG de "Full Resolution" reabiertos y verificados con
PIL (`Image.verify()`), dimensiones íntegras. Expulsión limpia
(`cicada ipod eject`) al final.

**Hallazgo real, no bloqueante**: ambas fotos (96.5MP y 95.3MP — cámara
profesional real, no una foto de teléfono) superan el límite por
default de PIL para el aviso de "decompression bomb"
(`Image.MAX_IMAGE_PIXELS`, ~89.5MP) — sale un `DecompressionBombWarning`
en el log, la imagen se decodifica igual, no bloquea el sync. Ningún test
sintético lo había ejercitado (las imágenes de prueba son chicas a
propósito). No se tocó `MAX_IMAGE_PIXELS` ni se agregó manejo especial —
es una advertencia, no un error, y el caso real (fotos de 60-100MP) es
minoritario; queda registrado por si en el futuro justifica ajustar el
límite explícitamente en vez de dejarlo en el default de Pillow.

Verificación visual del resultado en el propio dispositivo: **la app de
Fotos apareció vacía pese al Photo Database bien formado** — ver
diagnóstico y fix abajo.

#### Diagnóstico post-6j — Fotos vacía en el dispositivo pese a un Photo Database bien formado (2026-08-20)

Tres hipótesis planteadas por el usuario, en orden barato→caro,
diagnosticadas **sin escribir nada al dispositivo** (mismo backup de 6j
reutilizado para inspección offline):

1. **¿Archivo de índice/contador separado?** Extraídos `iTunesPrefs.plist`
   e `iPodSettings.xml` reales del backup de 6j. Ninguno tiene un conteo
   de fotos separado del propio Photo Database — `iTunesPrefs.plist` no
   tiene `EstimatedDeviceTotals` en absoluto en este dispositivo (ni para
   música/video, que sí funcionan sin que Cicada haya escrito nunca ese
   archivo — descarta que sea requisito de visibilidad); `iPodSettings.xml`
   solo tiene preferencias de slideshow (`Repeat`/`Shuffle`/`TimePerSlide`/
   `Music`/`Transitions`), no un conteo. Sí se rastreó dónde lo escribe
   iOpenPod (`sync_executor.py` → `apply_itunes_protections_from_tracks`
   → `itunes_prefs.py`, un archivo real que Cicada nunca toca para ningún
   tipo de medio) — descartado como causa principal, no como gap a
   registrar.
2. **¿Reinicio necesario?** Descartado por el usuario — probó reiniciar
   el iPod, la app de Fotos siguió vacía.
3. **¿Discrepancia de chunk?** **Confirmado — bug real.** Auditoría byte
   a byte de `write_mhfd()`/`write_mhsd()` contra los DOS escritores
   originales de iOpenPod (`artworkdb_writer/artworkdb_chunks.py` para
   cover art, `sync/photos.py` para Fotos):
   - **MHFD offset 48 (u32) = 2** — fijado de forma incondicional por
     AMBOS escritores originales. `write_mhfd()` de Cicada nunca lo
     escribía (quedaba en 0 desde el buffer inicializado en cero), para
     cover art **y** para Fotos. Nunca rompió cover art visiblemente en
     hardware (esa app tolera un 0 ahí) — mismo principio que
     `mhbd[0x30]`: un campo que "no importa" para un caso puede ser
     justo el que importa para el siguiente. Significado exacto
     desconocido (no documentado en iOpenPod ni en libgpod) — se replica
     el valor observado, no se inventa uno.
   - **MHSD offset 12 (`ds_type`)**: ancho de empaquetado distinto entre
     los dos escritores originales — ArtworkDB usa `<H` (u16), Fotos usa
     `<I` (u32). `write_mhsd()` de Cicada usa `<H` (como ArtworkDB). Con
     los valores reales de `ds_type` (1/2/3, caben en 16 bits) y el
     buffer siempre inicializado en cero, el resultado en bytes es
     **idéntico** entre ambos anchos — confirmado por análisis directo,
     no es un gap funcional. Registrado igual porque el usuario pidió la
     auditoría completa, no solo lo que "sí importa".
   - **MHFD offsets 32-48/60-68**: en `artworkdb_chunks.py`, se copian
     condicionalmente de un `reference_mhfd` (preservación incremental
     entre syncs) — feature que la versión de Fotos de iOpenPod ni
     siquiera tiene, y que Cicada tampoco implementa para ningún caso
     (decisión ya aprobada: reescritura completa). No es un gap: ni
     siquiera el escritor original de Fotos lo hace.
   - **MHLI/MHLA/MHLF**: estructura idéntica en ambos escritores
     originales, y ya coincidía exactamente con lo que Cicada tenía. Sin
     hallazgos.

   **Fix**: `write_mhfd()` ahora fija el offset 48 = 2 siempre
   (`_MHFD_OFFSET_48_CONSTANT`), para cover art y Fotos por igual —
   mismo builder compartido, un solo punto de corrección. 2 tests nuevos
   (uno en `test_chunks.py` verificando ambas variantes de `write_mhfd()`
   directamente, uno en `test_chunks_photo.py` verificando que
   `build_photo_db()` lo hereda) — offsets exactos vía `struct.unpack_from`,
   no solo "no lanza excepción". Mutation check real (quitar la escritura
   del offset, confirmar que ambos tests fallan, revertir) confirmado.

   **Verificado que el fix no rompe cover art**: suite completa (607
   tests) incluyendo los tests de `apply.py`/Fase 4d que ejercitan
   `build_artworkdb()` con HASHAB real de punta a punta — todos verdes,
   sin cambios de comportamiento. El campo es aditivo (antes 0, ahora 2)
   y ningún test ni código de lectura de Cicada (`read_artworkdb()`)
   depende del valor anterior.

   **Segundo intento en hardware ejecutado (2026-08-20): fix del offset
   48 confirmado byte a byte en el `Photo Database` real instalado
   (offset 48 = 2, offset 16 = 6), pero la app de Fotos siguió vacía.**
   Dos hipótesis descartadas con evidencia real: reinicio del dispositivo
   (probado por el usuario, sin cambios) y estructura de header
   MHFD/MHSD (auditada, corregida, verificada en hardware — no era la
   causa).

#### Comparación contra un Photo Database REAL escrito por Música/iTunes (2026-08-20)

Hasta acá toda comparación fue contra **reimplementaciones** (iOpenPod,
Cicada) — nunca contra la fuente primaria. El usuario sincronizó 61 fotos
reales al mismo Nano 7G usando Música (sucesor de iTunes en macOS actual,
vía selección de carpeta completa por Finder — no fotos sueltas desde la
librería de Fotos.app), produciendo el primer `Photo Database` genuino
del proyecto. Auditoría byte a byte completa contra ese archivo (copiado
off-device para análisis, dispositivo sin más escrituras hasta terminar):

- **Hallazgo principal — `created_at`/`digitized_at` usan época Mac de
  1904 (HFS+), no Unix.** Valor real observado: `3862860232`. Decodificado
  como Unix epoch da el año 2092 (absurdo). Decodificado como época 1904
  (offset 2082844800s) da 2026-05-29 — coincide exactamente con la
  carpeta real donde Apple guardó el archivo
  (`Full Resolution/2026/05/29/`). Cicada escribía `int(stat.st_mtime)`
  (Unix) directo, sin conversión. Mismo patrón de bug que ya mordió 3
  veces en el proyecto con fechas del iTunesCDB (época Cocoa/2001) — una
  cuarta vez, con una época distinta (1904), en el único subsistema de
  Fotos sin respaldo SQLite. Candidato de causa raíz más fuerte
  encontrado, con mecanismo claro: una fecha que decodifica a un año sin
  sentido es exactamente lo que una app de Fotos descartaría en
  silencio de su índice visible.
- **MHFD offset 48 = 1 en el archivo real, no 2.** El "fix" aplicado en
  la etapa anterior (copiado del valor incondicional que usan ambos
  escritores de iOpenPod) no coincide con lo que realmente escribe
  Apple. Además offset 52 = 2 (ninguna referencia lo esperaba) y 24
  bytes opacos sin patrón simple en 32-48/60-68. Todo apunta a un
  contador de generación/sesión o checksum, no una constante fija.
  **Revertido a 0** (ver Etapa 6h arriba) — escribir "1" en vez de "2"
  habría sido el mismo error de raíz, copiar un valor de una fuente que
  tampoco lo entendía. Queda pendiente de investigar aparte, aislado del
  fix de época para poder atribuir la causa con certeza.
- **Full-res MHNI tiene width/height reales** (10612×8086 en la muestra),
  no 0/0 como escriben tanto iOpenPod como Cicada. Registrado, no
  bloqueante por ahora (podría importar para cómo la app pre-calcula
  aspect ratio antes de decodificar el JPEG, pero es menos sospechoso
  que la época).
- **Un chunk completamente nuevo, en ninguna de las dos referencias**:
  cada MHII real tiene 4 hijos, no 3 — el cuarto es `MHOD` tipo 6
  envolviendo un chunk `mhaf` (60 bytes, contenido íntegramente en cero
  en la muestra real). Ni iOpenPod ni Cicada lo modelan. Registrado como
  hueco conocido, no bloqueante por estar vacío en esta muestra
  (probablemente un campo opcional/reservado — caras, GPS, algo que
  Apple soporta pero no pobló acá).
- **MHSD/MHLI/MHLA/MHBA/MHLF/MHIF**: tamaños de header y campos que
  Cicada sí modela coinciden exactamente con el archivo real
  (`MHSD`=96, `MHLI`=92, `MHBA`=148 con `offset12=1`, `MHLA`=92,
  `MHLF`=92, `MHIF`=124). `MIN_PHOTO_ID`=100 confirmado — el primer
  `image_id` real de Apple también es 100.
- **Hipótesis del archivo de índice separado — descartada de forma
  PREMATURA, corregido más abajo (Etapa 6j, cuarto intento).** Esta
  primera comprobación solo diffeó `iTunesPrefs.plist`/`iPodSettings.xml`
  (archivos que ya existían antes del sync real) — bloque `<Photos>`
  idéntico, sin claves de fotos nuevas. Pero un diff limitado a archivos
  preexistentes no puede detectar archivos **nuevos**. La comprobación
  completa del árbol (ver más abajo) sí encontró uno: `frpd`/
  `PhotosFolder*`.
- Cosmético, no funcional: Apple organiza `Full Resolution/` por fecha
  (`año/mes/día`), Cicada (e iOpenPod) usan una subcarpeta plana fija.

**Fix de época aplicado, aislado del offset 48/52 a propósito** (para
poder atribuir causa con certeza si el próximo intento en hardware
funciona): `_build_photo_db_contents()` ahora recibe
`time_context: DeviceTimeContext` (mismo mecanismo ya probado que usa
`build_itunescdb()` desde Etapa 2a — no una conversión nueva de un solo
uso) y convierte con `time_context.unix_to_mac(item.mtime)` antes de
pasarlo a `write_mhii_photo()`. `sync_photos_to_ipod()` obtiene el
contexto real del dispositivo con `read_device_time_context(mount)` (lee
`Device/Preferences`), mismo patrón que `ipod_library.py`/
`bidirectional.py`. Verificación estructural exacta, no solo "compila":
con un mtime de origen controlado, el valor instalado en el dispositivo
simulado coincide exactamente con
`DeviceTimeContext.utc().unix_to_mac(mtime_conocido)` calculado por
separado. Reproducido también contra el valor REAL observado en el
dispositivo: `unix_to_mac()` del mtime real del archivo fuente (bajo el
contexto UTC que `read_device_time_context()` resuelve para este
dispositivo) da `3864323252` — coincide exacto con el `digitized_at`
real leído del `Photo Database` de Apple para esa misma foto. 1 test
nuevo con verificación exacta + reproducción del valor real, mutation
check real confirmado (quitar la conversión, ver el test fallar,
revertir). Suite completa: 608 tests verdes.

**Tercer intento en hardware (2026-08-20): fix de época aplicado y
verificado, síntoma sin cambios.** `read_photo_db()` sobre el
dispositivo real sigue confirmando 2 imágenes estructuralmente
correctas; la app de Fotos del Nano sigue mostrándose vacía. El
candidato más fuerte hasta ese momento (una fecha que decodifica a un
año absurdo, motivo plausible para que una app descarte una entrada en
silencio) no era, solo, la causa.

#### Diff binario completo MHII real vs. Cicada — mismo archivo fuente (2026-08-20)

Tras el tercer intento fallido, en vez de seguir infiriendo campo por
campo, se construyó — con las mismas piezas que usa
`_build_photo_db_contents()` (`encode_photo_for_format()`,
`write_mhii_photo()`, `DeviceTimeContext`) pero invocadas directo, sin
pasar por el coordinador completo — el MHII que Cicada produciría para
la MISMA foto fuente que una entrada real del `Photo Database` de
Música (`img20260322_13455148.jpg`, `image_id=100`). Identidad del
archivo confirmada por partida doble: el `digitized_at` calculado por
Cicada coincide exacto con el real (`3864323252`), y las dimensiones
leídas por PIL (10612×8086) coinciden con las que Apple grabó. Diff
byte a byte de ambos MHII, más verificación de que cada patrón se
sostiene sin excepción en las 61 entradas reales (no solo en la
primera inspeccionada):

| # | Campo | Real (Apple) | Cicada (antes) | ¿Uniforme en las 61 entradas? |
|---|---|---|---|---|
| **A** | `child_count`/4º hijo `MHOD` tipo 6 (`mhaf`) | Presente, contenido estático (96 bytes idénticos) | Ausente (3 hijos) | Sí, 61/61 |
| **B** | Offset 20 del header MHII (u32) — **sin documentar hasta este diff** | `image_id + 2` | `0` | Sí, 61/61, `image_id` 100→160 consecutivos |
| **C** | width/height del MHNI full-res | Poblado (10612×8086) | `0`/`0` | Sí, 61/61 |
| **D** | Offset 48 del header MHII (`original_size`) | `0` | Tamaño del archivo fuente en la PC | Sí, 61/61 en cero |
| **E** | Orden de los MHOD de thumbnail | Formato grande primero (1007, luego 1005) | Ascendente por `format_id` (1005, luego 1007) | Sí |
| **F** | `created_at` vs `digitized_at` | Distintos (EXIF vs. fecha de import) | Iguales (mismo mtime para ambos) | — |

**Cuarto intento en hardware (2026-08-20): A + B aplicados juntos
(ambos cambios estructurales/de header, no de contenido de imagen —
combinables sin perder atribución si el intento funciona), C/D/E/F
deliberadamente sin tocar.**

- `ArtworkMhodType.UNKNOWN_MHAF = 6` agregado; `MHAF_STATIC_BLOB`
  (constante de 96 bytes, `bytes.fromhex(...)`, extraída directo del
  `Photo Database` real y verificada — con un script de comparación
  independiente, no contra sí misma — byte a byte idéntica en las 61
  entradas) se agrega como 4º hijo incondicional de
  `write_mhii_photo()`.
- Offset 20 del header MHII ahora escribe `image_id + 2` — patrón
  empírico, no ley entendida (ver advertencia de una sola sesión de
  sync, igual que offset 48 de MHFD).
- `ParsedPhotoImageEntry` ganó `persistent_id`/`has_mhaf_marker` para
  poder verificar ambos campos por round-trip, no solo por inspección
  manual de bytes.
- Mutation checks reales confirmados y revertidos para ambos campos
  (fórmula de offset 20 y contenido de `MHAF_STATIC_BLOB`, este último
  verificado contra la extracción cruda del archivo real, no contra la
  propia constante). Suite completa: 604 tests verdes.
- Verificado en el dispositivo real tras el sync: `persistent_id=102`/
  `103` y `has_mhaf_marker=True` en ambas fotos, backup previo
  (`include_photos=True`) completado y verificado, archivos de
  thumbnail/full-res presentes en disco con los tamaños esperados.

**Resultado: la app de Fotos del Nano sigue mostrándose vacía.** Dos
hipótesis mecánicamente más plausibles que cualquiera de las anteriores
(A: fallo de forma fija en un parser rígido; B: colisión de un id que
debería ser único), estructuralmente verificadas como correctas en el
propio dispositivo, y el síntoma no cambió. Esto baja de forma real la
confianza en que la causa esté en un campo individual del `Photo
Database` — cuatro rondas, cuatro fixes correctos y verificados, mismo
síntoma.

#### Hallazgo nuevo: `frpd`/`PhotosFolder*` — fuera del Photo Database por completo (2026-08-20)

Comparación de un backup COMPLETO (no solo `Photos/`) tomado
inmediatamente antes del sync real de Música contra otro tomado
inmediatamente después — la comprobación de "archivo de índice
separado" de más arriba se había limitado a diffear archivos
preexistentes; esta vez se listó el árbol completo. Música creó **5
archivos nuevos en `iPod_Control/iTunes/`** (fuera de `Photos/` del
todo), con un formato de chunk (`frpd`) que ni iOpenPod ni ninguna
referencia usada hasta ahora documenta:

- `PhotosFolderName` (512 B): string UTF-16LE `"Pictures"` — el nombre
  de la carpeta de origen en la Mac.
- `PhotosFolderAlbums` (3196 B): contiene el string `"Adobe
  Lightroom"` — parece un índice de álbumes/carpetas independiente del
  `mhba` que ya vive dentro del `Photo Database`.
- `PhotosFolderPrefs` (764 B): estructura compleja — un
  *security-scoped bookmark* de macOS (ruta `Users/jjaroll/Pictures`,
  volumen `Macintosh HD`, un UUID), más ~30 bytes que tienen la forma de
  un hash/checksum sin algoritmo identificable a simple vista.
- `PSAlbumAlbums`, `PSElementsAlbums` (100 B cada uno): casi vacíos,
  solo header `frpd` — el nombre sugiere integraciones legado con
  Photoshop Album/Elements (apps de importación de fotos que iTunes
  soportó en versiones antiguas), probablemente plantillas que iTunes
  escribe siempre, poblado o no.

Confirmado que Cicada nunca toca ni borra estos archivos (idénticos
byte a byte después de los intentos 2°, 3° y 4° — `write_guard.py`
funciona como debe), pero eso también significa que después del sync
real quedaron apuntando a la carpeta/álbum de Música (`Pictures`/`Adobe
Lightroom`), sin ninguna relación con lo que Cicada sincroniza.

**Confianza: sin determinar, honesta.** Dos lecturas igual de
plausibles con la evidencia disponible: (1) son índices que el
firmware SÍ lee en paralelo al `Photo Database` para navegar
álbumes/carpetas — mecanismo plausible para "datos estructuralmente
válidos pero la app no muestra nada", pero sin evidencia directa de que
el firmware los lea; (2) son bookkeeping exclusivo de Música/iTunes en
la PC (el *bookmark* de macOS en `PhotosFolderPrefs` solo tiene sentido
para que iTunes vuelva a localizar la carpeta en el próximo sync, no
para el propio iPod), caso en el cual es un hallazgo real pero
irrelevante para este bug. A diferencia de `mhaf` (bytes estáticos,
copiables sin entenderlos), este contenido depende de la
carpeta/álbumes de origen reales y no se puede copiar a ciegas —
`PhotosFolderPrefs` en particular tiene un campo que parece un checksum
sin algoritmo conocido.

**Decisión (2026-08-20): pausa deliberada de la Etapa 6j, no
diferimiento sin investigar.** Cuatro rondas de hardware (15-20+ min
cada una) con 6 discrepancias reales encontradas y corregidas o
registradas (época, offset 48 de MHFD, `mhaf`, offset 20/
`persistent_id`, más C/D/E/F pendientes) no resolvieron el síntoma, y
el hallazgo de `frpd` cambia la naturaleza del trabajo restante: dejó
de ser "encontrar el campo que falta" para pasar a ser reconstruir por
ingeniería inversa un formato binario legado sin especificación
pública, con al menos un campo (el posible checksum de
`PhotosFolderPrefs`) que no se puede derivar por prueba y error. Se
pausa explícitamente en vez de seguir insistiendo con más rondas de
hardware al final de una sesión larga — mismas condiciones bajo las
que ya se cometió el error del offset 48 de MHFD (copiar sin entender).

**Estado del código al pausar**: A y B (mhaf + persistent_id) quedan
aplicados en `chunks.py` — verificados correctos y necesarios en
principio (coinciden con lo que escribe Apple), aunque no demostrados
suficientes por sí solos. C/D/E/F quedan sin aplicar, documentados
arriba con su confianza relativa.

**Para retomar sin repetir el trabajo de hoy**, todo preservado en
`~/.cicada/photo_sync_forensics/` (fuera del repo — 2 GB, no apto para
git; fuera también de la rotación de `~/.cicada/backups/`, que ya
estaba en 20/20 y habría empezado a borrar estos backups en el próximo
sync de cualquier tipo):

- `before_musica_real_sync_20260820T220243Z.tar.zst` /
  `after_musica_real_sync_20260820T223432Z.tar.zst` — los dos backups
  completos (`Photos/` + `iPod_Control/`) que hacen posible cualquier
  comparación futura contra un sync real de Apple, incluida la que
  encontró `frpd`.
- `backup_extracted_before_after/{before,after}/` — ambos ya
  descomprimidos, listos para inspección sin repetir la extracción.
- `Photo_Database_real` — el `Photo Database` real de 61 fotos,
  extraído suelto.
- `real_mhii_photo1.bin` / `cicada_mhii_photo1.bin` /
  `build_cicada_mhii.py` — el par de MHII usados para el diff A-F y el
  script que los generó, reproducible contra cualquier otra foto de la
  muestra real.

Primer paso sugerido al retomar (barato, no necesita el dispositivo):
buscar si hay evidencia pública de que el firmware de un Nano 7G lee
`frpd`/`PhotosFolder*` (herramientas open source de sync de fotos más
allá de iOpenPod, foros, ingeniería inversa previa de terceros) antes
de invertir tiempo en diseccionar el checksum de `PhotosFolderPrefs`
a ciegas.

#### Etapa 6a — `kind` de video en `/media/sync`. **Estado: implementado y verificado.**

`MediaTrackInput.kind` extendido con `"movie"`, `"tv_show"`,
`"music_video"`, `"video_podcast"` (cierra el hueco que había quedado
abierto en 5a — `MEDIA_TYPE_VIDEO_PODCAST` estaba excluido "hasta que
existiera Fase 6"). Campos nuevos opcionales: `season_number`,
`episode_number`, `show_name`. `video_podcast` combina las flags de
podcast (5a) con `media_type` de video — sin caso especial nuevo, la unión
de dos derivaciones ya existentes.

**Hallazgo que simplificó el código respecto al plan (video resultó
todavía más simple de lo esperado):** la derivación inicial seteaba
`ti.movie_file_flag = 1` explícitamente para las cuatro variantes de
video, calcado del patrón `podcast_flag`/`remember_position` de 5a. El
mutation sanity check sobre esa línea (comentada para `video_podcast`) no
hizo fallar ningún test — confirmando que `write_mhit()`
(`_resolve_movie_flag()`, infraestructura genérica de Fase 2) **ya
deriva `movie_flag` de `media_type` automáticamente** cuando el campo
explícito queda en 0. Se quitaron las cuatro líneas redundantes; un
segundo mutation check sobre `media_type` en sí (constante equivocada)
sí falló como se esperaba, confirmando que el test seguía siendo
significativo tras la simplificación.

Tests (`tests/ipod/test_api.py`, +5): round-trip real parametrizado para
las 4 variantes (`movie`/`tv_show`/`music_video`/`video_podcast`),
verificando `media_type` y `movie_flag` parseados del iTunesCDB escrito
en disco; prueba dedicada de `tv_show` verificando `season_number`/
`episode_number`/`Show` (nombre del programa) round-trip. 2 mutation
sanity checks confirmados y revertidos. Suite completa: 496 tests verdes
(491 + 5 nuevos).

#### Etapa 6b — Verificación del pipeline de artwork sobre video. **Estado: verificado, cero cambios de código.**

Hipótesis del plan: `shared/artwork.py` (Fase 4a, ya diseñado para
compartirse entre `core` e `ipod`) debería extraer carátula embebida de un
`.m4v` igual que de un `.m4a`, sin tocar nada. Confirmado en dos pasos:

1. `extract_embedded_artwork()` detecta el contenedor con
   `isinstance(audio, MP4)` vía `mutagen.File()` (que **sniffea** el
   contenido real, no la extensión) — un `.m4v` con `covr` se lee
   idéntico a un `.m4a`. Probado directo con el fixture existente
   `tests/fixtures/audio/with_art.m4a` copiado a `.m4v`: extrae los
   mismos bytes.
2. `create_plan()` (línea ~247 en `plan.py`) resuelve fuente de artwork
   para **todos** los tracks sin filtrar por `media_type` — un video con
   `kind="movie"` entra exactamente por el mismo camino que música.

Cero código nuevo — la instrucción explícita para esta etapa era no
forzar una corrección si algo no encajaba, y no hizo falta: la hipótesis
se cumplió sin cambios. Test (`tests/ipod/test_api.py`, +1): round-trip
real vía `/media/sync` con `kind="movie"` y el fixture `.m4v` reusado,
verificando `artwork_touched`/`artwork_tracks_count` en la respuesta **y**
la entrada real en `ArtworkDB` (`read_artworkdb()`), mismo patrón de
verificación que Fase 4d/5a. Suite completa: 497 tests verdes (496 + 1).

#### Etapa 6c — `GET /videos` y `DELETE /videos/{id}` reales. **Estado: implementado y verificado.**

`GET /videos`: lista plana (sin agrupar — así la consume el frontend hoy,
a diferencia de podcasts/audiobooks) filtrada por
`media_type ∈ {VIDEO, MUSIC_VIDEO, TV_SHOW, TV_SHOW_ALT}`, reusando
`_load_current_library()`. Sin `resolution` ni `thumb` del contrato
original (`ui-ipod.md`): `resolution` no se puede derivar sin `ffprobe`
(sin esa dependencia, ver Paquete 9); `thumb` necesitaría un endpoint de
servido de ArtworkDB que tampoco existe para música todavía — ambos
quedan fuera, mismo criterio que 5c con el arte de podcasts.

**Cierre del hueco de `MEDIA_TYPE_VIDEO_PODCAST` (aprobado explícitamente
por el usuario, ya que 6a lo hizo trivial):** en vez de agregarlo a
`/videos`, se sumó a `/podcasts` (5c) junto con `MEDIA_TYPE_PODCAST` — un
video_podcast es un episodio de programa antes que un video suelto;
mostrarlo en ambas categorías habría duplicado la pista en la UI.
Decisión tomada en implementación, documentada aquí en vez de dejarla como
hueco silencioso.

**`DELETE /videos/{id}` no necesitó coordinador nuevo — hallazgo que
simplificó el trabajo:** `POST /track/remove` (Fase 3, `remove_track_from_ipod()`
en `media.py`) ya borraba cualquier pista por `db_track_id` sin importar
`media_type`. El endpoint nuevo es un wrapper delgado que traduce el `id`
de la URL; sin `consent_ack` en el body (el contrato original de
`ui-ipod.md` no lo tenía) — no hace falta: `apply()` solo exige
`consent_ack=True` cuando `plan.consent_needed` es `True`, y eso solo pasa
en la primera escritura de un dispositivo (confirmado leyendo
`plan.py`/`apply.py`); para poder borrar un video ya tuvo que haber una
escritura previa, así que el consentimiento ya está otorgado.

Tests (`tests/ipod/test_api.py`, +5): lista real con película + episodio
de serie (verificando `show_name`/`season_number`/`episode_number`);
`video_podcast` no aparece en `/videos` pero sí en `/podcasts`; delete
real de extremo a extremo (`POST /media/sync` → `GET /videos` para el id
real → `DELETE` → verificado que la pista y el archivo de audio
desaparecen del iTunesCDB real, no de un mock); 404 con id inexistente. 2
mutation sanity checks confirmados (filtro de `_VIDEO_MEDIA_TYPES`,
wiring del id en `delete_video`). Suite completa: 500 tests verdes.

**Corrección de frontend necesaria (mismo patrón que `date`→`date_added`
en 5c — primera vez que `/videos` devuelve datos reales):**
`ipodVideoCardHtml()` en `render.js` leía `vid.size` (contrato antiguo de
`ui-ipod.md`); el schema real usa `size_bytes` (consistente con
`TrackSchema`). Sin el fix, el fallback de tamaño mostraba "0 B" para todo
video sin `resolution`. Corregido y verificado en el navegador real
(`preview_start`, sin errores). Cache-busting `render.js` a `2.2.2`.
`_mockAddVideo()` no se tocó — sigue enviando `resolution` explícito, que
tiene prioridad sobre el fallback y no se ve afectado.

