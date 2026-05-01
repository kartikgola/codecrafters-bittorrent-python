
from typing import Set

from bittorrent.peer_connection import PeerConnection
from bittorrent.torrent import Torrent


class ConnectionManager:
    """
    Manages all peer connections for a torrent.
    """
    def __init__(self, torrent: Torrent):
        self.torrent = torrent
        self.peer_connections: Set[PeerConnection] = set()
    
    def add_peer_connection(self, peer_connection: PeerConnection) -> None:
        self.peer_connections.add(peer_connection)