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
