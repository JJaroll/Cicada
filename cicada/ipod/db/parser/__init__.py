"""Parser del iTunesCDB/iTunesDB — vendorizado de iOpenPod (Etapa 3a).

Solo lectura. Descompresión zlib transparente del iTunesCDB. Ver docs/VENDORED.md.
"""
from .exceptions import CorruptHeaderError, InsufficientDataError
from .parser import decompress_itunescdb, parse_itunesdb
from .ipod_library import load_ipod_library
from .playcounts import PlayCountEntry, merge_playcounts, parse_playcounts
