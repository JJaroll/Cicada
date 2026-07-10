"""
Plan B de identificación de audio: fingerprinting acústico vía AcoustID/MusicBrainz.
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import acoustid
import requests
from dotenv import load_dotenv

load_dotenv()

ACOUSTID_API_KEY: Optional[str] = os.environ.get("ACOUSTID_API_KEY")

EXTENSIONES_SOPORTADAS = {".mp3", ".m4a"}
META_ACOUSTID = ["recordings", "releasegroups"]


def _extraer_artista(recording: Dict[str, Any]) -> Optional[str]:
    artists = recording.get("artists")
    if not artists:
        return None
    return "".join(a["name"] + a.get("joinphrase", "") for a in artists)


def _extraer_album(recording: Dict[str, Any]) -> Optional[str]:
    releasegroups = recording.get("releasegroups")
    if not releasegroups:
        return None
    return releasegroups[0].get("title")


def _fingerprint_y_lookup(ruta_archivo: str) -> Dict[str, Any]:
    duration, fingerprint = acoustid.fingerprint_file(ruta_archivo)
    return acoustid.lookup(ACOUSTID_API_KEY, fingerprint, duration, meta=META_ACOUSTID)


def _parsear_respuesta_acoustid(respuesta: Dict[str, Any]) -> Dict[str, Any]:
    if respuesta.get("status") != "ok":
        return {"status": "error", "message": f"AcoustID devolvió status='{respuesta.get('status')}'"}

    resultados = respuesta.get("results", [])
    if not resultados:
        return {"status": "error", "message": "NOT_FOUND_ACOUSTID"}

    mejor = max(resultados, key=lambda r: r.get("score", 0))
    recordings = mejor.get("recordings")
    if not recordings:
        return {"status": "error", "message": "NOT_FOUND_ACOUSTID"}

    recording = recordings[0]
    titulo = recording.get("title")
    artista = _extraer_artista(recording)

    if not titulo or not artista:
        return {"status": "error", "message": "AcoustID encontró una coincidencia pero sin título/artista suficientes."}

    return {
        "status": "success",
        "title": titulo,
        "artist": artista,
        "album": _extraer_album(recording) or "Unknown Album",
        "score": round(mejor.get("score", 0.0), 2),
    }


async def identificar_con_acoustid(ruta_archivo: str) -> Dict[str, Any]:
    if not ACOUSTID_API_KEY:
        return {
            "status": "error",
            "message": "ACOUSTID_API_KEY no configurada. Define esta variable en tu archivo .env",
        }

    path = Path(ruta_archivo)
    if not path.is_file():
        return {"status": "error", "message": f"Archivo no encontrado: {ruta_archivo}"}

    if path.suffix.lower() not in EXTENSIONES_SOPORTADAS:
        return {"status": "error", "message": f"Extensión no soportada por este fallback: {path.suffix}"}

    try:
        respuesta = await asyncio.to_thread(_fingerprint_y_lookup, str(path))

    except acoustid.NoBackendError:
        return {
            "status": "error",
            "message": "No se encontró 'fpcalc' (Chromaprint) en el sistema. Instálalo con: brew install chromaprint",
        }
    except acoustid.FingerprintGenerationError:
        return {
            "status": "error",
            "message": f"No se pudo generar la huella acústica de '{path.name}' (archivo corrupto o formato inválido).",
        }
    except acoustid.WebServiceError as e:
        return {"status": "error", "message": f"Fallo el servicio AcoustID/MusicBrainz: {e}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Error de red al contactar AcoustID: {e}"}
    except acoustid.AcoustidError as e:
        return {"status": "error", "message": f"Error de AcoustID: {e}"}
    except OSError as e:
        return {"status": "error", "message": f"Error de E/S leyendo '{path.name}': {e}"}
    except Exception as e:  # último resorte: nunca dejar que un archivo tumbe el batch
        return {"status": "error", "message": f"Error inesperado procesando '{path.name}': {e}"}

    try:
        return _parsear_respuesta_acoustid(respuesta)
    except Exception as e:
        return {"status": "error", "message": f"Respuesta de AcoustID con formato inesperado: {e}"}


async def procesar_archivos_huerfanos(
    rutas_archivos: List[str],
    max_concurrencia: int = 3,
) -> List[Dict[str, Any]]:
    semaforo = asyncio.Semaphore(max_concurrencia)

    async def _procesar_uno(ruta: str) -> Dict[str, Any]:
        async with semaforo:
            resultado = await identificar_con_acoustid(ruta)
            resultado["file"] = ruta
            return resultado

    return await asyncio.gather(*(_procesar_uno(ruta) for ruta in rutas_archivos))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python acoustid_fallback.py <ruta_al_archivo>")
        raise SystemExit(1)

    resultado = asyncio.run(identificar_con_acoustid(sys.argv[1]))
    print(resultado)
