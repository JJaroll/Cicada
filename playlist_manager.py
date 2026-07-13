"""
Emparejador Difuso y Compilador de Playlists locales.

Conecta las playlists/álbumes resueltos desde Spotify con la biblioteca ya organizada localmente por Cicada,
sin necesidad de volver a descargar nada: si la canción ya existe en disco,
se reutiliza.

Módulo aislado a propósito (no depende de `main.py`, FastAPI ni websockets)
para poder probarlo unitariamente sin levantar el resto de la aplicación.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mutagen
from thefuzz import fuzz, process


class PlaylistManager:
    """
    Empareja tracks de Spotify contra archivos ya organizados por Cicada
    (`output_dir/Artist/Album/XX - Title.ext`) usando fuzzy matching, y
    compila los resultados en playlists .m3u8 locales.
    """

    SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".mp4", ".aac", ".flac", ".wav", ".aiff", ".aif", ".alac"}
    MATCH_THRESHOLD = 85
    VERSION_KEYWORDS = ("live", "en vivo", "remix", "acoustic", "acústico")
    VERSION_PENALTY = 25

    def index_local_library(self, output_dir: str) -> List[Dict[str, str]]:
        """
        Escanea recursivamente `output_dir` y construye un índice liviano de
        la biblioteca local ya organizada por Cicada.

        Intenta leer título/artista/álbum con `mutagen` (más preciso); si el
        archivo no trae tags legibles, deduce los tres campos de la estructura
        de carpetas `Artist/Album/XX - Title.ext` que produce
        `audio_processor.apply_metadata_and_move`.

        Args:
            output_dir: carpeta raíz de la biblioteca ya organizada.

        Returns:
            Lista de dicts: {"title": str, "artist": str, "album": str, "path": str}
            (`path` es siempre una ruta absoluta).
        """
        base = Path(output_dir)
        index: List[Dict[str, str]] = []

        if not base.is_dir():
            return index

        for file_path in base.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                continue

            title, artist, album = self._read_tags(file_path)
            fallback_title, fallback_artist, fallback_album = self._infer_from_path(file_path, base)

            index.append({
                "title": title or fallback_title,
                "artist": artist or fallback_artist,
                "album": album or fallback_album,
                "path": str(file_path.resolve()),
            })

        return index

    def scan_local_playlists(self, output_dir: str) -> List[Dict[str, Any]]:
        """
        Lee los archivos .m3u8 ya generados (por `generate_m3u8`) en la raíz
        de `output_dir`, para poder agrupar la biblioteca "por playlist" sin
        volver a consultar Spotify.

        Returns:
            Lista de dicts: {"name": str, "paths": List[str]} (rutas absolutas).
        """
        base = Path(output_dir)
        playlists: List[Dict[str, Any]] = []

        if not base.is_dir():
            return playlists

        for m3u8_file in sorted(base.glob("*.m3u8")):
            try:
                lines = m3u8_file.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue

            paths = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                candidate = Path(line)
                if not candidate.is_absolute():
                    candidate = (m3u8_file.parent / candidate).resolve()
                paths.append(str(candidate))

            playlists.append({"name": m3u8_file.stem, "paths": paths})

        return playlists

    def _read_tags(self, file_path: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Lectura ligera de título/artista/álbum vía la interfaz 'easy' de mutagen. Nunca lanza."""
        try:
            audio = mutagen.File(str(file_path), easy=True)
            if audio is None or not audio.tags:
                return None, None, None
            title = next(iter(audio.tags.get("title", [])), None)
            artist = next(iter(audio.tags.get("artist", [])), None)
            album = next(iter(audio.tags.get("album", [])), None)
            return (title or None), (artist or None), (album or None)
        except Exception:
            return None, None, None

    def _infer_from_path(self, file_path: Path, base: Path) -> Tuple[str, str, str]:
        """
        Deduce (titulo, artista, album) de la ruta cuando no hay tags legibles,
        asumiendo la estructura `Artist/Album/XX - Title.ext` que produce
        Cicada al organizar archivos.
        """
        try:
            parts = file_path.relative_to(base).parts
        except ValueError:
            parts = (file_path.name,)

        # Artist/Album/archivo.ext -> 3 partes; si el archivo cuelga directo
        # de output_dir no podemos inferir artista/álbum de la carpeta.
        artist = parts[0] if len(parts) >= 3 else "Unknown Artist"
        album = parts[1] if len(parts) >= 3 else "Unknown Album"

        # Quita el prefijo "XX - " (número de pista) que agrega Cicada al nombrar el archivo
        title = re.sub(r"^\d{1,3}\s*-\s*", "", file_path.stem).strip()

        return title or file_path.stem, artist, album

    def _has_version_keyword(self, text: str) -> bool:
        """True si el texto trae una marca de versión alternativa (Live, Remix, etc.)."""
        lowered = text.lower()
        return any(re.search(rf"\b{re.escape(kw)}\b", lowered) for kw in self.VERSION_KEYWORDS)

    @staticmethod
    def _comparable(artist: str, title: str) -> str:
        """Normaliza un par (artista, título) al formato "Artista - Título" usado para comparar."""
        artist = (artist or "").strip()
        title = (title or "").strip()
        if not artist and not title:
            return ""
        return f"{artist} - {title}".strip(" -")

    def match_track(self, spotify_track: Dict[str, str], local_index: List[Dict[str, str]]) -> Optional[str]:
        """
        Busca en el índice local la mejor coincidencia difusa para un track de Spotify.

        Usa `fuzz.token_set_ratio` sobre "Artista - Título" (tolerante a orden
        de palabras y texto extra) a través de `process.extractOne`, y
        penaliza coincidencias locales marcadas como "Live"/"Remix"/etc.
        cuando el track de Spotify no lo es, para no mezclar la versión
        equivocada.

        Args:
            spotify_track: dict con al menos 'title' y 'artist'.
            local_index: salida de `index_local_library`.

        Returns:
            Ruta absoluta del archivo local si la similitud supera
            `MATCH_THRESHOLD` (85%), o None si no hay coincidencia suficiente.
        """
        if not local_index:
            return None

        query = self._comparable(spotify_track.get("artist", ""), spotify_track.get("title", ""))
        if not query:
            return None

        query_is_alt_version = self._has_version_keyword(query)

        # Mapeamos índice numérico -> texto comparable. Usar el índice como key
        # (en vez del texto) evita colisiones cuando dos pistas locales
        # comparten el mismo "Artista - Título".
        choices: Dict[int, str] = {
            i: self._comparable(entry.get("artist", ""), entry.get("title", ""))
            for i, entry in enumerate(local_index)
        }

        def scorer(a: str, b: str, **_kwargs: Any) -> int:
            score = fuzz.token_set_ratio(a, b)
            if self._has_version_keyword(b) and not query_is_alt_version:
                score = max(0, score - self.VERSION_PENALTY)
            return score

        result = process.extractOne(query, choices, scorer=scorer, score_cutoff=self.MATCH_THRESHOLD)
        if result is None:
            return None

        _matched_text, _score, matched_index = result
        return local_index[matched_index]["path"]

    def generate_m3u8(self, playlist_name: str, matched_file_paths: List[str], output_dir: str) -> str:
        """
        Compila una lista de rutas de archivos locales en una playlist .m3u8
        estándar, guardada en la raíz de `output_dir`.

        Las rutas dentro del .m3u8 se guardan relativas a la carpeta donde
        vive el propio archivo .m3u8 (portable si se mueve toda la carpeta
        de música); si el cálculo de ruta relativa no es posible (p. ej. en
        Windows entre unidades distintas), cae de vuelta a la ruta absoluta.

        Args:
            playlist_name: nombre de la playlist (sin extensión).
            matched_file_paths: rutas de los archivos a incluir, en orden.
            output_dir: carpeta raíz donde se guarda el .m3u8 (y la biblioteca).

        Returns:
            Ruta absoluta del archivo .m3u8 generado.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        # Resolvemos symlinks para que coincida con las rutas ya resueltas
        # que entrega `index_local_library`; si no, relpath puede calcular
        # saltos de directorio incorrectos entre una ruta resuelta y otra que no lo está.
        output_path = output_path.resolve()

        safe_name = re.sub(r'[<>:"/\\|?*]', "_", playlist_name).strip() or "playlist"
        m3u8_path = output_path / f"{safe_name}.m3u8"

        lines = ["#EXTM3U"]
        for file_path in matched_file_paths:
            resolved_file = Path(file_path).resolve()
            try:
                line = os.path.relpath(resolved_file, start=output_path)
            except ValueError:
                # En Windows, relpath falla entre unidades distintas (ej. C:\ vs D:\)
                line = str(resolved_file)
            lines.append(line)

        m3u8_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return str(m3u8_path.resolve())
