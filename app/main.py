import json
import sys

from bencoder.decoder import Decoder
from client.bittorrent_client import BitTorrentClient
from client.torrent import Torrent

def main():
    command = sys.argv[1]
    if command == "decode":
        bencoded_value = sys.argv[2].encode()
        decoder = Decoder()

        # json.dumps() can't handle bytes, but bencoded "strings" need to be
        # bytestrings since they might contain non utf-8 characters.
        #
        # Let's convert them to strings for printing to the console.
        def bytes_to_str(data):
            if isinstance(data, bytes):
                return data.decode()
            raise TypeError(f"Type not serializable: {type(data)}")

        print(json.dumps(decoder.decode(bencoded_value), default=bytes_to_str))

    elif command == "info":
        torrent_file_path = sys.argv[2]
        t = Torrent(torrent_file_path)
        print(f"Tracker URL: {t.announce}")
        print(f"Length: {t.info['length']}")
        print(f"Info Hash: {t.info_hex_hash}")
        print(f"Piece Length: {t.info['piece length']}")
        print(f"Piece Hashes:")

        pieces = t.info['pieces']
        for i in range(0, len(pieces), 20):
            print(pieces[i: i+20].hex())

    elif command == "peers":
        torrent_file_path = sys.argv[2]
        t = Torrent(torrent_file_path)
        peers = BitTorrentClient().get_peers(t)
        for peer in peers:
            print(peer)
            
    elif command == "handshake":
        torrent_file_path = sys.argv[2]
        peer_info = sys.argv[3]
        peer_ip, peer_port = peer_info.split(":")
        t = Torrent(torrent_file_path)
        peer_id = BitTorrentClient().handshake(t, peer_ip, int(peer_port))
        print(f"Peer ID: {peer_id}")
    
    elif command == "download_piece":
        output_path = sys.argv[3]
        torrent_file_path = sys.argv[4]
        t = Torrent(torrent_file_path)
        piece_index = sys.argv[5]
        peer_id = BitTorrentClient().download_piece(t, output_path, int(piece_index))
    
    elif command == "download":
        output_path = sys.argv[3]
        torrent_file_path = sys.argv[4]
        t = Torrent(torrent_file_path)
        peer_id = BitTorrentClient().download(t, output_path)

if __name__ == "__main__":
    main()
