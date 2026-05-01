from enum import IntEnum
import hashlib
from http import HTTPStatus
from multiprocessing import Value
import os
from pathlib import Path
import socket
from typing import Dict, List, Tuple

import requests
from bencoder import decoder
from bencoder.decoder import Decoder
from bencoder.encoder import Encoder
from client.models import Peer

HANDSHAKE_LENGTH = 68
DEFAULT_BLOCK_LENGTH = 2 ** 14 # 16K


class TorrentStatus(IntEnum):
    NOT_STARTED = 0
    STARTED = 1
    FAILED = 2
    COMPLETED = 3


class Torrent:
    def __init__(self, file_path):
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

        self._connections: Dict[Peer, socket.socket] = {}
        self._status: TorrentStatus = TorrentStatus.NOT_STARTED

    @property
    def info_hash(self) -> bytes:
        """
        returns 20 bytes of SHA1 digest of torrent's encoded info
        """
        encoded_info = Encoder().encode(self._decoded_content['info'])
        return hashlib.sha1(encoded_info).digest()
    
    @property
    def info_hex_hash(self) -> str:
        """
        returns string (40 bytes long) of SHA1 hexdigest of torrent's encoded info
        """
        encoded_info = Encoder().encode(self._decoded_content['info'])
        return hashlib.sha1(encoded_info).hexdigest()
    
    @property
    def info(self):
        """
        returns info part of the torrent as JSON value
        """
        return self._decoded_content['info']
    
    @property
    def announce(self):
        """
        returns announce url of the torrent
        """
        return self._decoded_content['announce']

    def _receive_bytes(self, sock: socket.socket, n: int):
        """
        receive exactly n bytes from the socket
        """
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed by peer")
            data += chunk
        return data
    
    def get_peer_addresses(self) -> List[Tuple[str, int]]:
        """
        perform the tracker GET request to get a list of peers
        return list of peers as strings of IP:PORT values
        """
        # request new peer info
        response = requests.get(self.announce, params={
            # info_hash: the info hash of the torrent 20 bytes long, will need to be URL encoded
            # Note: this is NOT the hexadecimal representation, which is 40 bytes long
            "info_hash": self.info_hash,
            
            # 20 bytes long random peer id
            "peer_id": os.urandom(20),
            "port": 6881,

            # progress so far
            "uploaded": 0,
            "downloaded": 0,
            "left": self.info['length'],
            "compact": 1
        })

        peer_addresses: List[Tuple[str, int]] = []
        if response.status_code == HTTPStatus.OK:
            response_decoded = decoder.Decoder().decode(response.content)
            print(f"got response ", response_decoded)
            peers_data = response_decoded['peers']

            for i in range(0, len(peers_data), 6):
                ip_bytes = peers_data[i: i+4]
                port_bytes = peers_data[i+4: i+6]

                ip = ".".join(str(b) for b in ip_bytes)
                port = int.from_bytes(port_bytes)

                peer_addresses.append((ip, port))
        else:
            print(f"GET announce request returned non-200 code")
        
        return peer_addresses
    
    def handshake(self, peer_address: Tuple[str, int]) -> Peer:
        """
        performs handshake with the given IP:PORT of the peer 
        and returns peer object; also stores socket connection 
        established with the peer.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(peer_address)

        pstr = b"BitTorrent protocol" # 19 bytes
        pstr_len = len(pstr)          # 1 byte
        reserved = b"\x00" * 8        # 8 bytes
        peer_id = self._client_id     # 20 bytes

        payload = (
            pstr_len.to_bytes() + 
            pstr + 
            reserved + 
            self.info_hash + 
            peer_id
        )

        s.sendall(payload)
        response = self._receive_bytes(s, HANDSHAKE_LENGTH)
        peer_id = response[-20:]
        
        # create a Peer object
        peer = Peer(peer_id, peer_address[0], peer_address[1])

        # maintain 1 connection per torrent per peer
        if peer in self._connections and not self._connections[peer].is_closed():
            # no-op
            return 

        self._connections[peer] = s
        return peer

    def download(self, output_path: str, piece_index: int = None):
        """
        downloads the whole file or a particular piece of the torrent
        """
        if self._status != TorrentStatus.NOT_STARTED:
            raise ValueError("torrent status must be NOT_STARTED")
        
        self._status = TorrentStatus.STARTED
        peers = self.get_peer_addresses()
        
        if not peers:
            raise ValueError("no peers found!")
        
        peer_ip, peer_port = peers[0].split(":")

        # handshake with the peer
        self.handshake((peer_ip, peer_port))

    
    def __repr__(self):
        return f"Torrent: {self._file_path}"