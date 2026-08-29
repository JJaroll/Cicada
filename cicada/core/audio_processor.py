"""Procesamiento y etiquetado de metadatos en archivos de audio."""
import re
import shutil
import httpx
from pathlib import Path
from typing import Dict, Any

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TRCK, APIC, TCON, TSRC, TDOR, TCOM, TBPM, TPOS, TCMP, TIT1, COMM
import mutagen.id3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen.wave import WAVE
from mutagen.aiff import AIFF
import mutagen

class AudioProcessor:
    def __init__(self):
        pass

    async def _download_cover(self, url: str) -> bytes:
        if not url:
            return b""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
            except Exception:
                return b""

    def sanitize_filename(self, name: str) -> str:
        # Limpia caracteres no válidos para nombres de archivo.
        return re.sub(r'[<>:"/\\|?*]', '_', str(name))

    @staticmethod
    def _extract_isrc(metadata: dict) -> str:
        external_ids = metadata.get('external_ids')
        if not isinstance(external_ids, dict):
            return ''
        return external_ids.get('isrc') or ''

    @staticmethod
    def _extract_original_release_date(metadata: dict) -> str:
        release_date = metadata.get('original_release_date')
        return release_date if isinstance(release_date, str) else ''

    def _apply_extended_id3_tags(self, tags, metadata: dict) -> None:
        isrc = self._extract_isrc(metadata)
        if isrc:
            tags.add(TSRC(encoding=3, text=isrc))

        original_release_date = self._extract_original_release_date(metadata)
        if original_release_date:
            tags.add(TDOR(encoding=3, text=original_release_date))

        if metadata.get('composer'):
            tags.add(TCOM(encoding=3, text=metadata['composer']))

        if metadata.get('bpm'):
            tags.add(TBPM(encoding=3, text=str(metadata['bpm'])))

    def _parse_id3_tags(self, tags: ID3, meta: dict):
        if "TIT2" in tags: meta["title"] = str(tags["TIT2"].text[0])
        if "TPE1" in tags: meta["artist"] = str(tags["TPE1"].text[0])
        if "TALB" in tags: meta["album"] = str(tags["TALB"].text[0])
        if "TPE2" in tags: meta["album_artist"] = str(tags["TPE2"].text[0])
        if "TCOM" in tags: meta["composer"] = str(tags["TCOM"].text[0])
        if "TCON" in tags: meta["genre"] = str(tags["TCON"].text[0])
        if "TDOR" in tags: meta["year"] = str(tags["TDOR"].text[0])
        elif "TDRC" in tags: meta["year"] = str(tags["TDRC"].text[0])
        if "TBPM" in tags: meta["bpm"] = str(tags["TBPM"].text[0])
        if "TIT1" in tags: meta["grouping"] = str(tags["TIT1"].text[0])

        if "TCMP" in tags:
            val = str(tags["TCMP"].text[0])
            meta["compilation"] = (val == "1")

        for key in tags.keys():
            if key.startswith("COMM"):
                meta["comments"] = str(tags[key].text[0])
                break

        if "TRCK" in tags:
            trck = str(tags["TRCK"].text[0]).split("/")
            meta["track_number"] = trck[0]
            if len(trck) > 1: meta["track_count"] = trck[1]

        if "TPOS" in tags:
            tpos = str(tags["TPOS"].text[0]).split("/")
            meta["disc_number"] = tpos[0]
            if len(tpos) > 1: meta["disc_count"] = tpos[1]

    def read_full_metadata(self, file_path: str) -> Dict[str, Any]:
        # Lee los metadatos completos de un archivo de audio.
        path = Path(file_path)
        if not path.exists():
            return {}

        try:
            audio = mutagen.File(str(path))
            if audio is None:
                return {}
        except Exception:
            return {}

        meta = {
            "title": "", "artist": "", "album": "", "album_artist": "",
            "composer": "", "genre": "", "year": "", "track_number": "",
            "track_count": "", "disc_number": "", "disc_count": "",
            "compilation": False, "grouping": "", "comments": "", "bpm": ""
        }

        if isinstance(audio, MP3) or (hasattr(audio, 'tags') and isinstance(audio.tags, ID3)):
            if audio.tags:
                self._parse_id3_tags(audio.tags, meta)
        elif isinstance(audio, MP4):
            tags = audio
            if "\xa9nam" in tags: meta["title"] = str(tags["\xa9nam"][0])
            if "\xa9ART" in tags: meta["artist"] = str(tags["\xa9ART"][0])
            if "\xa9alb" in tags: meta["album"] = str(tags["\xa9alb"][0])
            if "aART" in tags: meta["album_artist"] = str(tags["aART"][0])
            if "\xa9wrt" in tags: meta["composer"] = str(tags["\xa9wrt"][0])
            if "\xa9gen" in tags: meta["genre"] = str(tags["\xa9gen"][0])
            if "\xa9day" in tags: meta["year"] = str(tags["\xa9day"][0])
            if "tmpo" in tags: meta["bpm"] = str(tags["tmpo"][0])
            if "\xa9grp" in tags: meta["grouping"] = str(tags["\xa9grp"][0])
            if "\xa9cmt" in tags: meta["comments"] = str(tags["\xa9cmt"][0])
            if "cpil" in tags: meta["compilation"] = bool(tags["cpil"][0])

            if "trkn" in tags and tags["trkn"]:
                meta["track_number"] = str(tags["trkn"][0][0])
                if tags["trkn"][0][1] > 0:
                    meta["track_count"] = str(tags["trkn"][0][1])
            if "disk" in tags and tags["disk"]:
                meta["disc_number"] = str(tags["disk"][0][0])
                if tags["disk"][0][1] > 0:
                    meta["disc_count"] = str(tags["disk"][0][1])

        else:
            tags = getattr(audio, 'tags', audio)
            if tags:
                if "title" in tags: meta["title"] = tags["title"][0]
                if "artist" in tags: meta["artist"] = tags["artist"][0]
                if "album" in tags: meta["album"] = tags["album"][0]
                if "albumartist" in tags: meta["album_artist"] = tags["albumartist"][0]
                if "composer" in tags: meta["composer"] = tags["composer"][0]
                if "genre" in tags: meta["genre"] = tags["genre"][0]
                if "date" in tags: meta["year"] = tags["date"][0]
                elif "originaldate" in tags: meta["year"] = tags["originaldate"][0]
                if "bpm" in tags: meta["bpm"] = tags["bpm"][0]
                if "grouping" in tags: meta["grouping"] = tags["grouping"][0]

                if "comment" in tags: meta["comments"] = tags["comment"][0]
                elif "description" in tags: meta["comments"] = tags["description"][0]

                if "compilation" in tags: meta["compilation"] = (str(tags["compilation"][0]) == "1")

                if "tracknumber" in tags: meta["track_number"] = tags["tracknumber"][0]
                if "tracktotal" in tags: meta["track_count"] = tags["tracktotal"][0]
                if "discnumber" in tags: meta["disc_number"] = tags["discnumber"][0]
                if "disctotal" in tags: meta["disc_count"] = tags["disctotal"][0]

        for k, v in meta.items():
            if v == "0" and k in ["track_number", "track_count", "disc_number", "disc_count"]:
                meta[k] = ""
            if v == "None":
                meta[k] = ""

        return meta

    async def apply_metadata_and_move(self, source_path: str, output_base_dir: str, metadata: Dict[str, Any]) -> str:
        # Aplica metadatos al audio y lo organiza en disco.
        path = Path(source_path)
        ext = path.suffix.lower()

        if 'artwork_base64' in metadata and metadata['artwork_base64']:
            import base64
            b64_str = metadata['artwork_base64']
            if "," in b64_str:
                b64_str = b64_str.split(",")[1]
            cover_data = base64.b64decode(b64_str)
        else:
            cover_data = await self._download_cover(metadata.get('artwork_url', ''))

        try:
            audio = mutagen.File(str(path))
            if audio is not None:
                from mutagen.mp3 import MP3
                from mutagen.mp4 import MP4
                from mutagen.flac import FLAC
                from mutagen.wave import WAVE
                from mutagen.aiff import AIFF

                if isinstance(audio, MP3):
                    self._tag_mp3(str(path), metadata, cover_data)
                elif isinstance(audio, MP4):
                    self._tag_mp4(str(path), metadata, cover_data)
                elif isinstance(audio, FLAC):
                    self._tag_flac(str(path), metadata, cover_data)
                elif isinstance(audio, WAVE):
                    self._tag_wav(str(path), metadata, cover_data)
                elif isinstance(audio, AIFF):
                    self._tag_aiff(str(path), metadata, cover_data)
        except Exception as e:
            raise e

        artist = self.sanitize_filename(metadata.get('artist', 'Unknown Artist'))
        album = self.sanitize_filename(metadata.get('album', 'Unknown Album'))

        track_number_str = str(metadata.get('track_number', '00')).zfill(2)
        title = self.sanitize_filename(metadata.get('title', path.stem))

        new_filename = f"{track_number_str} - {title}{ext}"

        target_dir = Path(output_base_dir) / artist / album
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / new_filename

        shutil.move(str(source_path), str(target_path))
        return str(target_path)

    def _tag_mp3(self, path: str, metadata: dict, cover_data: bytes):
        try:
            audio = MP3(path, ID3=ID3)
        except mutagen.id3.ID3NoHeaderError:
            audio = mutagen.File(path, easy=True)
            audio.add_tags()
            audio.save()
            audio = MP3(path, ID3=ID3)

        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags
        tags.clear()

    def _apply_common_id3_tags(self, tags, metadata: dict):
        if metadata.get('title'): tags.add(TIT2(encoding=3, text=metadata['title']))
        if metadata.get('artist'): tags.add(TPE1(encoding=3, text=metadata['artist']))
        if metadata.get('album'): tags.add(TALB(encoding=3, text=metadata['album']))
        if metadata.get('album_artist'): tags.add(TPE2(encoding=3, text=metadata['album_artist']))

        track_num = str(metadata.get('track_number', '1'))
        track_count = str(metadata.get('track_count', ''))
        tags.add(TRCK(encoding=3, text=f"{track_num}/{track_count}" if track_count else track_num))

        if metadata.get('genre'): tags.add(TCON(encoding=3, text=metadata['genre']))
        if metadata.get('grouping'): tags.add(TIT1(encoding=3, text=metadata['grouping']))
        if metadata.get('comments'): tags.add(COMM(encoding=3, lang='eng', desc='', text=metadata['comments']))

        disc_num = str(metadata.get('disc_number', ''))
        disc_count = str(metadata.get('disc_count', ''))
        if disc_num:
            tags.add(TPOS(encoding=3, text=f"{disc_num}/{disc_count}" if disc_count else disc_num))

        if metadata.get('compilation'):
            tags.add(TCMP(encoding=3, text="1"))

        self._apply_extended_id3_tags(tags, metadata)

    def _tag_mp3(self, path: str, metadata: dict, cover_data: bytes):
        try:
            audio = MP3(path, ID3=ID3)
        except mutagen.id3.ID3NoHeaderError:
            audio = mutagen.File(path, easy=True)
            audio.add_tags()
            audio.save()
            audio = MP3(path, ID3=ID3)

        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags
        tags.clear()

        self._apply_common_id3_tags(tags, metadata)

        if cover_data:
            tags.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=cover_data
            ))

        audio.save(v2_version=3)

    def _tag_wav(self, path: str, metadata: dict, cover_data: bytes):
        try:
            audio = WAVE(path)
        except Exception:
            return

        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags
        tags.clear()

        self._apply_common_id3_tags(tags, metadata)
        if cover_data: tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_data))

        audio.save()

    def _tag_aiff(self, path: str, metadata: dict, cover_data: bytes):
        try:
            audio = AIFF(path)
        except Exception:
            return

        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags
        tags.clear()

        self._apply_common_id3_tags(tags, metadata)
        if cover_data: tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_data))

        audio.save()

    def _tag_mp4(self, path: str, metadata: dict, cover_data: bytes):
        audio = MP4(path)
        audio.delete()
        if audio.tags is None:
            audio.add_tags()

        if metadata.get('title'):
            audio['\xa9nam'] = metadata['title']
        if metadata.get('artist'):
            audio['\xa9ART'] = metadata['artist']
        if metadata.get('album'):
            audio['\xa9alb'] = metadata['album']
        if metadata.get('album_artist'):
            audio['aART'] = metadata['album_artist']

        track_num = metadata.get('track_number', 0)
        track_count = metadata.get('track_count', 0)
        if track_num:
            try:
                audio['trkn'] = [(int(track_num), int(track_count) if track_count else 0)]
            except ValueError:
                pass

        disc_num = metadata.get('disc_number', 0)
        disc_count = metadata.get('disc_count', 0)
        if disc_num:
            try:
                audio['disk'] = [(int(disc_num), int(disc_count) if disc_count else 0)]
            except ValueError:
                pass

        if metadata.get('genre'):
            audio['\xa9gen'] = metadata['genre']

        if metadata.get('grouping'):
            audio['\xa9grp'] = metadata['grouping']

        if metadata.get('comments'):
            audio['\xa9cmt'] = metadata['comments']

        if metadata.get('compilation'):
            audio['cpil'] = True

        isrc = self._extract_isrc(metadata)
        if isrc:
            audio['isrc'] = isrc

        original_release_date = self._extract_original_release_date(metadata)
        if original_release_date:
            audio['\xa9day'] = original_release_date

        if metadata.get('composer'):
            audio['\xa9wrt'] = metadata['composer']

        if metadata.get('bpm'):
            try:
                audio['tmpo'] = [int(metadata['bpm'])]
            except (TypeError, ValueError):
                pass

        if cover_data:
            audio['covr'] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]

        audio.save()

    def _tag_flac(self, path: str, metadata: dict, cover_data: bytes):
        audio = FLAC(path)
        audio.clear_pictures()
        audio.delete()
        if audio.tags is None:
            audio.add_tags()

        if metadata.get('title'):
            audio['title'] = metadata['title']
        if metadata.get('artist'):
            audio['artist'] = metadata['artist']
        if metadata.get('album'):
            audio['album'] = metadata['album']
        if metadata.get('album_artist'):
            audio['albumartist'] = metadata['album_artist']

        if metadata.get('track_number'):
            audio['tracknumber'] = str(metadata['track_number'])
        if metadata.get('track_count'):
            audio['tracktotal'] = str(metadata['track_count'])

        if metadata.get('disc_number'):
            audio['discnumber'] = str(metadata['disc_number'])
        if metadata.get('disc_count'):
            audio['disctotal'] = str(metadata['disc_count'])

        if metadata.get('genre'):
            audio['genre'] = metadata['genre']

        if metadata.get('grouping'):
            audio['grouping'] = metadata['grouping']

        if metadata.get('comments'):
            audio['comment'] = metadata['comments']

        if metadata.get('compilation'):
            audio['compilation'] = "1"

        isrc = self._extract_isrc(metadata)
        if isrc:
            audio['isrc'] = isrc

        original_release_date = self._extract_original_release_date(metadata)
        if original_release_date:
            audio['originaldate'] = original_release_date

        if metadata.get('composer'):
            audio['composer'] = metadata['composer']

        if metadata.get('bpm'):
            audio['bpm'] = str(metadata['bpm'])

        if cover_data:
            pic = Picture()
            pic.type = 3
            pic.mime = "image/jpeg"
            pic.desc = "Front Cover"
            pic.data = cover_data
            audio.add_picture(pic)

        audio.save()
