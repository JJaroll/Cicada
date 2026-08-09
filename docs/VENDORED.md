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

Atribución completa en `cicada/ipod/NOTICE`.
