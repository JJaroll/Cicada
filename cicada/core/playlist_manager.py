"""Emparejador difuso y compilador de listas de reproducción locales."""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mutagen
from thefuzz import fuzz, process


class PlaylistManager:
    SUPPORTED_EXTENSIONS = {".mp3", ".m4a", ".mp4", ".aac", ".flac", ".wav", ".aiff", ".aif", ".alac"}
    MATCH_THRESHOLD = 85
    VERSION_KEYWORDS = ("live", "en vivo", "remix", "acoustic", "acústico")
    VERSION_PENALTY = 25

    def index_local_library(self, output_dir: str) -> List[Dict[str, str]]:
        # Indexa los archivos de audio de la biblioteca local.
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
        # Escanea playlists .m3u8 generadas en la biblioteca local.
        playlists: List[Dict[str, Any]] = []
        base = Path(output_dir)
        if not base.is_dir():
            return playlists

        existing_files: Dict[str, Path] = {}
        existing_stems: Dict[str, Path] = {}
        for f in base.rglob("*"):
            if f.is_file() and f.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                existing_files[f.name.lower()] = f
                existing_stems[f.stem.lower()] = f

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
                if not candidate.is_file():
                    fname_key = candidate.name.lower()
                    fstem_key = candidate.stem.lower()
                    if fname_key in existing_files:
                        candidate = existing_files[fname_key]
                    elif fstem_key in existing_stems:
                        candidate = existing_stems[fstem_key]
                    else:
                        for k, fpath in existing_stems.items():
                            if fstem_key in k or k in fstem_key:
                                candidate = fpath
                                break
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

        artist = parts[0] if len(parts) >= 3 else "Unknown Artist"
        album = parts[1] if len(parts) >= 3 else "Unknown Album"

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
        # Busca coincidencias difusas para la pista en la biblioteca.
        if not local_index:
            return None

        query = self._comparable(spotify_track.get("artist", ""), spotify_track.get("title", ""))
        if not query:
            return None

        query_is_alt_version = self._has_version_keyword(query)

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
        # Genera una lista de reproducción .m3u8 con rutas relativas.
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        output_path = output_path.resolve()

        safe_name = re.sub(r'[<>:"/\\|?*]', "_", playlist_name).strip() or "playlist"
        m3u8_path = output_path / f"{safe_name}.m3u8"

        lines = ["#EXTM3U"]
        for file_path in matched_file_paths:
            resolved_file = Path(file_path).resolve()
            try:
                line = os.path.relpath(resolved_file, start=output_path)
            except ValueError:
                line = str(resolved_file)
            lines.append(line)

        m3u8_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return str(m3u8_path.resolve())
