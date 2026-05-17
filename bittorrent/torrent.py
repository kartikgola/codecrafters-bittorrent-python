from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
import hashlib
from pathlib import Path
from typing import Dict
from urllib.parse import parse_qs, urlparse

from bencoder.decoder import Decoder
from bencoder.encoder import Encoder


DEFAULT_BLOCK_LENGTH = 2 ** 14 # 16K


class TorrentStatus(IntEnum):
    STOPPED = 0
    DOWNLOADING = 1
    SEEDING = 2


@dataclass(frozen=True)
class TorrentSummary:
    id: int
    file_path: str
    created_at: datetime
    updated_at: datetime
    download_progress: int
    upload_progress: int # future use
    status: TorrentStatus


class Torrent:
    """
    Represents one torrent: its metadata, state, and progress; exposes intent, not mechanics
    Torrent does not talk to sockets, does not understand protocol messages, doesn't interact with peers.
    """
    def __init__(self):
        self._file_path = None
        self._binary_content = None
        self._decoded_content = None
        self._magnet_link = None
        
    def load_from_file(self, file_path: str):
        if not file_path:
            return ValueError(f"{file_path} is not valid")
        
        path = Path(file_path)
        if not path.exists():
            return FileNotFoundError(f"{file_path} not found")
        
        if not path.is_file():
            return FileNotFoundError(f"{file_path} is not a file")

        self._file_path = file_path
        with open(file_path, 'rb') as f:
            self._binary_content = f.read()
            self._decoded_content = Decoder().decode(self._binary_content)
        
    def load_from_magnet_link(self, magnet_link: str):
        if not magnet_link:
            return ValueError(f"{magnet_link} is not valid")
        
        self._magnet_link = magnet_link
        query = urlparse(magnet_link).query
        self._parsed_magnet_link = parse_qs(query)

    @property
    def info_hash(self) -> bytes:
        """
        returns 20 bytes of SHA1 digest of torrent's encoded info
        """
        if self._decoded_content is not None:
            encoded_info = Encoder().encode(self._decoded_content['info'])
            return hashlib.sha1(encoded_info).digest()
        
        if self._parsed_magnet_link is not None:
            xt = self._parsed_magnet_link["xt"][0]
            raw_hash = xt.split(":")[-1]

            # if len(raw_hash) == 40:
            return bytes.fromhex(raw_hash)
        
        raise ValueError("torrent content is not loaded, cannot compute info hash")
    
    @property
    def info_hex_hash(self) -> str:
        """
        returns string (40 bytes long) of SHA1 hexdigest of torrent's encoded info
        """
        if self._decoded_content is not None:
            encoded_info = Encoder().encode(self._decoded_content['info'])
            return hashlib.sha1(encoded_info).hexdigest()
        
        if self._parsed_magnet_link is not None:
            return self._parsed_magnet_link['xt'][0].split(':')[-1]
        
        raise ValueError("torrent content is not loaded, cannot compute info hash")
    
    @property
    def info(self) -> Dict:
        """
        returns info part of the torrent as JSON value
        """
        if self._decoded_content:
            return self._decoded_content["None"]
    
        return None
    
    @property
    def announce(self) -> str:
        """
        returns announce url of the torrent
        """
        if self._decoded_content is not None:
            return self._decoded_content['announce']
        
        if self._parsed_magnet_link is not None:
            return self._parsed_magnet_link['tr'][0]
        
        raise ValueError("torrent content is not loaded, cannot get announce url")

    def __repr__(self):
        return f"Torrent: {self._file_path or self._magnet_link}"
