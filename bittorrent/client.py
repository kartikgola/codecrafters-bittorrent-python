import os
import sys
from typing import List

from bittorrent.peer import Peer
from bittorrent.peer_connection import PeerConnection
from bittorrent.torrent import Torrent, TorrentSummary
from bittorrent.tracker_client import TrackerClient

class BitTorrentClient:
    """
    High-level application layer "boring" class that exposes methods
    for outer world to interact with torrents.
    """
    def __init__(self):
        # generate a 20 bytes random client id on startup for the current BitTorrent client
        self._client_id = os.urandom(20)
        self._tracker_client = TrackerClient(self._client_id)

        # set of all loaded torrents
        self._torrents = set()
    
    def add_torrent(self, torrent: Torrent) -> None:
        self._torrents.add(torrent)

    def remove_torrent(self, torrent: Torrent) -> None:
        pass

    def start_torrent(self, torrent: Torrent) -> None:
        pass

    def stop_torrent(self, torrent: Torrent) -> None:
        pass

    def list_torrents(self) -> List[TorrentSummary]:
        pass

    def get_torrent(self, torrent: Torrent) -> TorrentSummary:
        pass

    def get_torrent_peer_address(self, torrent: Torrent) -> List[str]:
        peers = self._tracker_client.get_peers(torrent)
        return [f"{peer.ip}:{peer.port}" for peer in peers]

    def handshake(self, torrent: Torrent, peer_ip: str, peer_port: int, with_extensions: bool = False) -> str:
        connection = PeerConnection(self._client_id, Peer(None, peer_ip, peer_port), torrent, with_extensions)
        try:
            peer_id = connection.handshake()
            if with_extensions:
                connection.send_extension_handshake()
            return peer_id
        finally:
            connection.close()

    def download(self, torrent: Torrent, output_path: str, piece_index: int = None, quit_early: bool = False) -> None:
        if torrent.info is None and not quit_early:
            raise ValueError("magnet downloads require fetching metadata before downloading pieces")

        peers = self._tracker_client.get_peers(torrent)
        if not peers:
            raise ValueError("no peers found")

        target = f"piece {piece_index}" if piece_index is not None else "complete file"
        print(f"[client] downloading {target} to {output_path}", file=sys.stderr)
        last_error = None
        for peer in peers:
            connection = PeerConnection(self._client_id, peer, torrent, with_extensions=torrent.info is None)
            try:
                print(f"[client] trying peer {peer.ip}:{peer.port}", file=sys.stderr)
                data = connection.download(piece_index, quit_early)
                with open(output_path, 'wb') as output_file:
                    output_file.write(data)
                print(f"[client] wrote {len(data)} bytes to {output_path}", file=sys.stderr)
                return
            except Exception as error:
                print(f"[client] peer {peer.ip}:{peer.port} failed: {error}", file=sys.stderr)
                last_error = error
            finally:
                connection.close()

        raise ValueError(f"download failed for all peers: {last_error}")

    def start(self):
        pass

    def stop(self):
        pass
