"""Verificación de firma HASHAB (Nano 6G/7G) — Fase 1, solo verificar.

Comprueba que una firma HASHAB existente en el header `mhbd` (offset 0xAB)
coincide con la que produce nuestra implementación. Es el criterio de aceptación
que decide el paso a Fase 2: si reproducimos la firma que el dispositivo ya tiene,
el writer funcionará.

**Hallazgo clave (verificado contra el iPod real):** el SHA1 se computa sobre los
bytes del **iTunesCDB comprimido tal cual están en disco** (NO sobre el iTunesDB
descomprimido, como asumía el spec), con:
  - `hashing_scheme` (0x30) puesto a 4 (HASHAB),
  - los campos db_id/unk_0x32/hash58/hash72/hashab a cero,
  - el GUID en orden natural (`bytes.fromhex`, sin reversión).

Solo se verifica, no se genera. La generación (write_hashab) es Fase 2.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from cicada.ipod.db.shared.mhbd_defs import (
    MHBD_OFFSET_DB_ID,
    MHBD_OFFSET_HASH58,
    MHBD_OFFSET_HASH72,
    MHBD_OFFSET_HASHAB,
    MHBD_OFFSET_HASHING_SCHEME,
    MHBD_OFFSET_UNK_0x32,
)
from cicada.ipod.db.writer.hashab import HASHAB_SIZE, compute_hashab

__all__ = ["HashVerifyResult", "verify_hashab", "canonical_hashab_sha1"]

_ITDB_CHECKSUM_HASHAB = 4


@dataclass(frozen=True)
class HashVerifyResult:
    """Resultado de verificar una firma HASHAB, con ambos bytes para comparar."""
    valid: bool
    stored: bytes
    computed: bytes

    @property
    def stored_hex(self) -> str:
        return self.stored.hex()

    @property
    def computed_hex(self) -> str:
        return self.computed.hex()


def canonical_hashab_sha1(itunescdb: bytes | bytearray) -> bytes:
    """SHA1 canónico para HASHAB sobre el iTunesCDB **comprimido** en disco.

    Pone hashing_scheme=4 y pone a cero db_id, unk_0x32, hash58, hash72, hashab.
    """
    data = bytearray(itunescdb)
    data[MHBD_OFFSET_HASHING_SCHEME:MHBD_OFFSET_HASHING_SCHEME + 2] = \
        _ITDB_CHECKSUM_HASHAB.to_bytes(2, "little")
    data[MHBD_OFFSET_DB_ID:MHBD_OFFSET_DB_ID + 8] = b"\x00" * 8
    data[MHBD_OFFSET_UNK_0x32:MHBD_OFFSET_UNK_0x32 + 20] = b"\x00" * 20
    data[MHBD_OFFSET_HASH58:MHBD_OFFSET_HASH58 + 20] = b"\x00" * 20
    data[MHBD_OFFSET_HASH72:MHBD_OFFSET_HASH72 + 46] = b"\x00" * 46
    data[MHBD_OFFSET_HASHAB:MHBD_OFFSET_HASHAB + HASHAB_SIZE] = b"\x00" * HASHAB_SIZE
    return hashlib.sha1(bytes(data)).digest()


def verify_hashab(itunescdb: bytes | bytearray, firewire_guid: bytes) -> HashVerifyResult:
    """Verifica la firma HASHAB del ``itunescdb`` (bytes comprimidos en disco).

    :param itunescdb: bytes del iTunesCDB tal como están en disco (comprimido).
    :param firewire_guid: GUID de 8+ bytes (``bytes.fromhex`` del FireWireGUID).
    :returns: :class:`HashVerifyResult` con ``valid`` y ambas firmas.
    """
    data = bytes(itunescdb)
    stored = data[MHBD_OFFSET_HASHAB:MHBD_OFFSET_HASHAB + HASHAB_SIZE]
    computed = compute_hashab(canonical_hashab_sha1(data), firewire_guid)
    return HashVerifyResult(valid=stored == computed, stored=stored, computed=computed)
