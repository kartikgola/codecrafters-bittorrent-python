import requests
import sys

from bencoder.decoder import Decoder
from bittorrent.peer import Peer
from bittorrent.torrent import Torrent


class TrackerClient:
    """
    Tracker client is responsible for communicating with the tracker, sending announce requests, and processing responses.
    It also maintains the state of the torrent (started, stopped, completed) and updates it based on the events.
    """
    def __init__(self, peer_id: bytes, port: int = 6881):
        self._peer_id = peer_id
        self._port = port

    def get_peers(self, torrent: Torrent) -> list[Peer]:
        """
        Perform the tracker GET request to get a list of peers.
        Return list of peers as Peer objects.
        """
        print(f"[tracker] announcing to {torrent.announce}", file=sys.stderr)
        response = requests.get(torrent.announce, params={
            # info_hash: the info hash of the torrent 20 bytes long, will need to be URL encoded
            # Note: this is NOT the hexadecimal representation, which is 40 bytes long
            "info_hash": torrent.info_hash,
            
            # 20 bytes long peer id
            "peer_id": self._peer_id,
            "port": self._port,

            # progress so far
            "uploaded": 0,
            "downloaded": 0,
            "left": torrent.info['length'] if torrent.info else 1,
            "compact": 1,

            # event: started, stopped, completed
            # "event": "started",
        })

        if response.status_code != 200:
            raise ValueError(f"tracker request failed with status code {response.status_code}")
        
        response_data = response.content
        decoded_response = Decoder().decode(response_data)

        if 'failure reason' in decoded_response:
            raise ValueError(f"tracker request failed with reason: {decoded_response['failure reason']}")
        
        print(decoded_response)
        peers_data = decoded_response['peers']
        peers = []
        for i in range(0, len(peers_data), 6):
            ip_bytes = peers_data[i: i+4]
            port_bytes = peers_data[i+4: i+6]

            ip = ".".join(str(b) for b in ip_bytes)
            port = int.from_bytes(port_bytes, byteorder='big')

            peers.append(Peer(None, ip, port))

        print(f"[tracker] received {len(peers)} peers", file=sys.stderr)
        return peers
