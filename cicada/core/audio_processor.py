import re
import shutil
import httpx
from pathlib import Path
from typing import Dict, Any

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TRCK, APIC, TCON, TSRC, TDOR, TCOM, TBPM
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
        """
        Inyecta metadatos extendidos provenientes de la API de Spotify (ISRC,
        fecha de lanzamiento original, compositor, BPM) en un objeto de tags
        ID3. Cada campo se omite silenciosamente si no está presente en `metadata`.
        """
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

    async def apply_metadata_and_move(self, source_path: str, output_base_dir: str, metadata: Dict[str, Any]) -> str:
        path = Path(source_path)
        ext = path.suffix.lower()

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

        if metadata.get('title'):
            tags.add(TIT2(encoding=3, text=metadata['title']))
        if metadata.get('artist'):
            tags.add(TPE1(encoding=3, text=metadata['artist']))
        if metadata.get('album'):
            tags.add(TALB(encoding=3, text=metadata['album']))
        if metadata.get('album_artist'):
            tags.add(TPE2(encoding=3, text=metadata['album_artist']))
        
        track_num = str(metadata.get('track_number', '1'))
        track_count = str(metadata.get('track_count', ''))
        if track_count:
            tags.add(TRCK(encoding=3, text=f"{track_num}/{track_count}"))
        else:
            tags.add(TRCK(encoding=3, text=track_num))
            
        if metadata.get('genre'):
            tags.add(TCON(encoding=3, text=metadata['genre']))

        self._apply_extended_id3_tags(tags, metadata)

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
        
        if metadata.get('title'): tags.add(TIT2(encoding=3, text=metadata['title']))
        if metadata.get('artist'): tags.add(TPE1(encoding=3, text=metadata['artist']))
        if metadata.get('album'): tags.add(TALB(encoding=3, text=metadata['album']))
        if metadata.get('album_artist'): tags.add(TPE2(encoding=3, text=metadata['album_artist']))
        
        track_num = str(metadata.get('track_number', '1'))
        track_count = str(metadata.get('track_count', ''))
        tags.add(TRCK(encoding=3, text=f"{track_num}/{track_count}" if track_count else track_num))
            
        if metadata.get('genre'): tags.add(TCON(encoding=3, text=metadata['genre']))
        self._apply_extended_id3_tags(tags, metadata)
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
        
        if metadata.get('title'): tags.add(TIT2(encoding=3, text=metadata['title']))
        if metadata.get('artist'): tags.add(TPE1(encoding=3, text=metadata['artist']))
        if metadata.get('album'): tags.add(TALB(encoding=3, text=metadata['album']))
        if metadata.get('album_artist'): tags.add(TPE2(encoding=3, text=metadata['album_artist']))
        
        track_num = str(metadata.get('track_number', '1'))
        track_count = str(metadata.get('track_count', ''))
        tags.add(TRCK(encoding=3, text=f"{track_num}/{track_count}" if track_count else track_num))
            
        if metadata.get('genre'): tags.add(TCON(encoding=3, text=metadata['genre']))
        self._apply_extended_id3_tags(tags, metadata)
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
            
        if metadata.get('genre'):
            audio['\xa9gen'] = metadata['genre']

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
            
        if metadata.get('genre'):
            audio['genre'] = metadata['genre']

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
