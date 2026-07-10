import re
import asyncio
import httpx
from pathlib import Path
from typing import Dict, Any
from shazamio import Shazam

from acoustid_fallback import identificar_con_acoustid

class MetadataManager:
    """
    Identifica metadatos de una pista de audio encadenando varias fuentes,
    de la más precisa a la más especulativa:

      Plan A: Shazam (huella acústica, más preciso)
      Plan B: AcoustID/MusicBrainz (fallback cuando Shazam no reconoce)
      Plan C: heurística sobre el nombre de archivo (opcional, menos fiable)
      Plan D: enriquecimiento con iTunes (álbum, portada, número de pista)

    Cada plan solo se activa si el anterior falla, y Plan D corre siempre
    al final para completar datos que Shazam/AcoustID no traen.
    """

    def __init__(self):
        self.shazam = Shazam()
        self.semaphore = asyncio.Semaphore(5)
        self.itunes_url = "https://itunes.apple.com/search"

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        patterns = [
            r"\s*-\s*Remastered\s*\d*",
            r"\s*\(Deluxe Edition\)",
            r"\s*\[Anniversary[^\]]*\]",
            r"\s*-\s*EP",
            r"\s*\(Remastered\)",
            r"\s*\(Deluxe\)"
        ]
        for p in patterns:
            text = re.sub(p, "", text, flags=re.IGNORECASE)
        return text.strip()

    async def identify_audio(self, file_path: str) -> Dict[str, Any]:
        async with self.semaphore:
            # Demora artificial para no disparar el rate limit no documentado de Shazam
            await asyncio.sleep(0.5)
            try:
                out = await self.shazam.recognize(file_path)
                if 'track' not in out:
                    return {"success": False, "error": "NOT_FOUND_SHAZAM"}

                track = out['track']
                title = self.clean_text(track.get('title', ''))
                artist = self.clean_text(track.get('subtitle', ''))

                return {
                    "success": True,
                    "title": title,
                    "artist": artist
                }
            except Exception as e:
                return {"success": False, "error": f"SHAZAM_ERROR: {str(e)}"}

    async def extract_from_filename(self, file_path: str) -> tuple[str, str]:
        """
        Plan C: deduce título y artista a partir del nombre del archivo cuando
        ni Shazam ni AcoustID lograron identificar la pista.
        """
        try:
            stem = Path(file_path).stem

            # Descarta anotaciones típicas de descargas/rips: "(Official Video)", "[HD]", "www.site.com"
            junk_patterns = [
                r"\[[^\]]{0,60}\]",
                r"\((?:official\s*)?(?:video|audio|lyrics?|music\s*video|visualizer|hd|hq|4k)\)",
                r"(?:www\.)?[\w-]+\.(?:com|net|org|mx|es)\b",
            ]
            for p in junk_patterns:
                stem = re.sub(p, "", stem, flags=re.IGNORECASE)

            stem = re.sub(r"[_.]+", " ", stem)
            stem = re.sub(r"\s{2,}", " ", stem).strip()

            # Separa por guiones: "Artista - Título" o "Track - Artista - Título"
            parts = [p.strip() for p in re.split(r"\s+-\s+", stem) if p.strip()]

            # Descarta un posible número de pista inicial ("01", "Track 03", etc.)
            if parts and re.fullmatch(r"(?:track\s*)?\d{1,3}", parts[0], flags=re.IGNORECASE):
                parts = parts[1:]

            if len(parts) >= 2:
                artista_raw, titulo_raw = parts[0], " - ".join(parts[1:])
            else:
                artista_raw, titulo_raw = "", (parts[0] if parts else stem)

            titulo = self.clean_text(titulo_raw)
            artista = self.clean_text(artista_raw)

            if not artista:
                titulo = self.clean_text(stem)
                artista = "Unknown Artist"

            if not titulo:
                titulo = "Unknown Title"

            titulo = titulo[:120].strip() or "Unknown Title"
            artista = artista[:120].strip() or "Unknown Artist"

            return titulo, artista
        except Exception:
            # Nunca dejar que un nombre de archivo raro tumbe el pipeline
            nombre_limpio = self.clean_text(Path(file_path).stem)[:120] if file_path else ""
            return (nombre_limpio or "Unknown Title"), "Unknown Artist"

    async def fetch_itunes_metadata(self, title: str, artist: str) -> Dict[str, Any]:
        async with self.semaphore:
            await asyncio.sleep(1.0)  # Respeta el límite no oficial de iTunes (~20 req/min según IP)
            term = f"{title} {artist}"

            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(self.itunes_url, params={
                        "term": term,
                        "media": "music",
                        "entity": "song",
                        "limit": 1
                    })
                    response.raise_for_status()
                    data = response.json()

                    if data.get('resultCount', 0) == 0:
                        return {"success": False, "error": "NOT_FOUND_ITUNES"}

                    track_data = data['results'][0]

                    # iTunes expone portada en alta resolución cambiando el tamaño en la URL
                    artwork_url = track_data.get('artworkUrl100', '')
                    if artwork_url:
                        artwork_url = artwork_url.replace('100x100bb', '600x600bb')

                    return {
                        "success": True,
                        "title": self.clean_text(track_data.get('trackName', title)),
                        "artist": self.clean_text(track_data.get('artistName', artist)),
                        "album": self.clean_text(track_data.get('collectionName', '')),
                        "album_artist": self.clean_text(track_data.get('collectionArtistName', track_data.get('artistName', ''))),
                        "track_number": track_data.get('trackNumber'),
                        "track_count": track_data.get('trackCount'),
                        "genre": track_data.get('primaryGenreName'),
                        "release_date": track_data.get('releaseDate'),
                        # Misma fecha bajo la clave que espera AudioProcessor._extract_original_release_date
                        "original_release_date": track_data.get('releaseDate'),
                        "artwork_url": artwork_url
                    }
                except Exception as e:
                    return {"success": False, "error": f"ITUNES_ERROR: {str(e)}"}

    async def process_file_metadata(self, file_path: str, logger_callback=None, plan_c_enabled: bool = False) -> Dict[str, Any]:
        """
        Corre el pipeline completo (Plan A -> B -> C -> D) sobre un archivo.

        plan_c_enabled: si Shazam y AcoustID fallan, controla si se recurre al
        Plan C (deducir título/artista del nombre de archivo). Apagado por
        defecto porque suele ser poco preciso; con él apagado, esos archivos
        se reportan como error en vez de adivinar.
        """
        if logger_callback: await logger_callback("⚗️ Extrayendo huella acústica con Shazam...")
        shazam_res = await self.identify_audio(file_path)

        if shazam_res['success']:
            title = shazam_res['title']
            artist = shazam_res['artist']
        else:
            if logger_callback:
                await logger_callback("⚠️ Shazam falló. Activando Plan B (AcoustID)...")
            acoustid_res = await identificar_con_acoustid(file_path)

            if acoustid_res['status'] == 'success':
                title = self.clean_text(acoustid_res['title'])
                artist = self.clean_text(acoustid_res['artist'])
                if logger_callback:
                    await logger_callback(f"✅ Plan B exitoso: identificado como {title} - {artist} vía AcoustID.")
            elif not plan_c_enabled:
                return {
                    "success": False,
                    "status": "failed",
                    "error": f"Shazam: {shazam_res['error']}. AcoustID: {acoustid_res['message']}"
                }
            else:
                if logger_callback:
                    await logger_callback("⚠️ Huellas acústicas fallaron. Activando Plan C: Extrayendo del nombre del archivo...")
                title, artist = await self.extract_from_filename(file_path)
                if logger_callback:
                    await logger_callback(f"📄 Plan C: usando '{title} - {artist}' extraído del nombre de archivo.")

        # Plan D: sin importar el origen del título/artista, se busca portada y datos de álbum en iTunes
        if logger_callback: await logger_callback(f"🔍 Identificado como: {title} - {artist}. Buscando arte de alta calidad en iTunes...")
        itunes_res = await self.fetch_itunes_metadata(title, artist)

        incomplete = []
        if not itunes_res['success']:
            incomplete.append(f"iTunes fallback failed: {itunes_res['error']}")
            metadata = {
                "title": title,
                "artist": artist,
                "album": "Unknown Album"
            }
        else:
            metadata = itunes_res
            required_keys = ['title', 'artist', 'album', 'track_number']
            for k in required_keys:
                if not metadata.get(k):
                    incomplete.append(f"Missing {k}")

            # iTunes normalmente entrega album_artist por release; si no vino, usamos el artist de la pista
            if not metadata.get('album_artist'):
                metadata['album_artist'] = metadata['artist']

        return {
            "success": True,
            "status": "success" if not incomplete else "incomplete",
            "metadata": metadata,
            "incomplete_fields": incomplete
        }
