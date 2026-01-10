import json
import random
import sys
from bencoder.decoder import Decoder
from bencoder.encoder import Encoder
import hashlib
import requests
import string
import socket
import struct
import os

from client.bittorrent_client import BitTorrentClient
from client.torrent import Torrent

# import bencodepy
# import requests

def main():
    command = sys.argv[1]

    # # You can use print statements as follows for debugging, they'll be visible when running tests.
    # print("Logs from your program will appear here!", file=sys.stderr)

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

        # Uncomment this block to pass the first stage
        print(json.dumps(decoder.decode(bencoded_value), default=bytes_to_str))

    elif command == "info":
        file_path = sys.argv[2]
        t = Torrent(file_path)
        print(f"Tracker URL: {t.announce}")
        print(f"Length: {t.info['length']}")
        print(f"Info Hash: {t.info_hex_hash}")
        print(f"Piece Length: {t.info['piece length']}")
        print(f"Piece Hashes:")

        pieces = t.info['pieces']
        for i in range(0, len(pieces), 20):
            print(pieces[i: i+20].hex())

    elif command == "peers":
        file_path = sys.argv[2]
        t = Torrent(file_path)
        peers = BitTorrentClient().get_peers(t)
        for peer in peers:
            print(peer)
            
    elif command == "handshake":
        file_path = sys.argv[2]
        peer_info = sys.argv[3]
        peer_ip, peer_port = peer_info.split(":")
        t = Torrent(file_path)
        peer_id = BitTorrentClient().handshake(t, peer_ip, int(peer_port))
        print(f"Peer ID: {peer_id}")
    
    elif command == "download_piece":
        output_path = sys.argv[3]
        file_path = sys.argv[4]
        t = Torrent(file_path)
        piece_index = sys.argv[5]
        peer_id = BitTorrentClient().download_piece(t, output_path, int(piece_index))

# Helper function to convert bytes to hex string for display
def bytes_to_str(data):
    if isinstance(data, bytes):
        return data.hex()
    raise TypeError(f"Type not serializable: {type(data)}")

def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed by peer")
        data += chunk
    return data

if __name__ == "__main__":
    main()
