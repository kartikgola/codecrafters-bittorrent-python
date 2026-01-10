from enum import IntEnum
import hashlib
import math
from multiprocessing import Value
import os
import random
from secrets import token_bytes
import socket
import string
import struct
from typing import List
import requests
from bencoder import decoder
from client.torrent import Torrent

class MessageType(IntEnum):
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    NOT_INTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    PIECE = 7

class BitTorrentClient:
    def __init__(self):
        pass

    def get_peers(self, torrent: Torrent) -> List[str]:
        """
        perform the tracker GET request to get a list of peers
        return list of peers as strings values of IP:PORT
        """
        response = requests.get(torrent.announce, params={
            # info_hash: the info hash of the torrent
            # 20 bytes long, will need to be URL encoded
            # Note: this is NOT the hexadecimal representation, which is 40 bytes long
            "info_hash": torrent.info_hash,
            "peer_id": "".join(random.choices(string.ascii_letters, k=20)),
            "port": 6881,
            "uploaded": 0,
            "downloaded": 0,
            "left": torrent.info['length'],
            "compact": 1
        })

        peers = []
        if response.status_code == 200:
            response_decoded = decoder.Decoder().decode(response.content)
            peers_data = response_decoded['peers']

            for i in range(0, len(peers_data), 6):
                ip_bytes = peers_data[i: i+4]
                port_bytes = peers_data[i+4: i+6]

                ip = ".".join(str(b) for b in ip_bytes)
                port = int.from_bytes(port_bytes, byteorder='big')

                peers.append(ip + ":" + str(port))
        return peers
    
    def _receive_exact(self, sock, n):
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed by peer")
            data += chunk
        return data

    def handshake(self, torrent: Torrent, peer_ip: str, peer_port: int) -> str:
        """
        performs a handshake with the peer and returns peer_id of the peer
        """
        pstr = b"BitTorrent protocol" # 19 bytes
        pstr_len = len(pstr) # 1 byte
        reserved = b"\x00" * 8 # 8 bytes
        peer_id = os.urandom(20) # 20 bytes

        handshake = (
            struct.pack("!B", pstr_len) + 
            pstr + 
            reserved + 
            torrent.info_hash + 
            peer_id
        )

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((peer_ip, peer_port))
            s.sendall(handshake)
            response = self._receive_exact(s, 68)

            pstrlen = response[0]
            pstr = response[1:1+pstrlen]
            reserved = response[1+pstrlen : 1+pstrlen+8]
            info_hash = response[1+pstrlen+8 : 1+pstrlen+8+20]
            peer_id = response[1+pstrlen+8+20 : 68]
            return peer_id.hex()
    
    def _prepare_message(self, message_type: MessageType, payload: bytes) -> bytes:
        length_prefix = 1 + len(payload)
        return (
            length_prefix.to_bytes(4, byteorder='big') +
            message_type.to_bytes(1, byteorder='big') + 
            payload
        )
    
    def _download_file(self, torrent: Torrent, s, output_path: str, begin_index: int):
        total_length = torrent.info['length']
        piece_length = torrent.info['piece length']
        pieces_hash_bytes = torrent.info['pieces']
        total_pieces = math.ceil(total_length / piece_length)
        downloaded_blocks = b''

        print(f"downloading", total_length, piece_length, total_pieces)

        if begin_index >= total_pieces:
            raise ValueError(f"begin_index {begin_index} cannot be >= total_pieces {total_pieces}")

        # downloading pieces starting from begin_index
        for index in range(begin_index, total_pieces):
            # Calculate actual piece size (last piece may be smaller)
            actual_piece_length = min(piece_length, total_length - (index * piece_length))

            # download all blocks within a piece
            for begin in range(0, actual_piece_length, 2 ** 14):
                # calculate the size of last block (since it can be smaller)
                block_length = min(2 ** 14, actual_piece_length - begin)
                payload = (
                    index.to_bytes(4, byteorder='big') + 
                    begin.to_bytes(4, byteorder='big') + 
                    block_length.to_bytes(4, byteorder='big')
                )

                print("sending request", index, begin, block_length)
                s.sendall(self._prepare_message(MessageType.REQUEST, payload))

                print("waiting for piece")
                self._receive_exact(s, 4)
                message_id = int.from_bytes(self._receive_exact(s, 1), byteorder='big')
                
                if message_id == MessageType.PIECE:
                    print("received piece message")
                    index = int.from_bytes(self._receive_exact(s, 4))
                    begin = int.from_bytes(self._receive_exact(s, 4))
                    block = self._receive_exact(s, block_length)
                    # print(index, begin, block)
                    downloaded_blocks += block
            
            expected_piece_hash = pieces_hash_bytes[index * 20: index * 20 + 20]
            actual_piece_hash = hashlib.sha1(downloaded_blocks).digest()

            if expected_piece_hash != actual_piece_hash:
                raise ValueError(f"piece hash doesn't match")
            
            with open(output_path, 'wb') as f:
                f.write(downloaded_blocks)

            break
            

    def download_piece(self, torrent: Torrent, output_path: str, piece_index: int):
        peers = self.get_peers(torrent)
        peer_ip, peer_port = peers[0].split(":")
        print(torrent.info)
        
        pstr = b"BitTorrent protocol" # 19 bytes
        pstr_len = len(pstr) # 1 byte
        reserved = b"\x00" * 8 # 8 bytes
        peer_id = os.urandom(20) # 20 bytes

        handshake = (
            struct.pack("!B", pstr_len) + 
            pstr + 
            reserved + 
            torrent.info_hash + 
            peer_id
        )

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # establish TCP connection
            s.connect((peer_ip, int(peer_port)))
            
            # send handshake
            s.sendall(handshake)
            
            # receive response
            response = self._receive_exact(s, 68)
            pstrlen = response[0]
            pstr = response[1:1+pstrlen]
            reserved = response[1+pstrlen : 1+pstrlen+8]
            info_hash = response[1+pstrlen+8 : 1+pstrlen+8+20]
            peer_id = response[1+pstrlen+8+20 : 68]
            print("received peer id", peer_id.hex())
            
            # wait for bitfield message from peer
            print("waiting for bitfield")
            prefix = self._receive_exact(s, 4)
            message_id_bytes = self._receive_exact(s, 1)
            message_len = int.from_bytes(prefix, byteorder='big')
            message_id = int.from_bytes(message_id_bytes, byteorder='big')
            _ = self._receive_exact(s, message_len - 1)

            if message_id == MessageType.BITFIELD:
                # send interested message
                message_id = 2
                payload = b''
                prefix_len = 1 + 0
                message = (
                    prefix_len.to_bytes(4, byteorder='big') +
                    message_id.to_bytes(1, byteorder='big') + 
                    payload
                )
                print("sending interested")
                s.sendall(message)

                print("waiting for unchoke")
                prefix = self._receive_exact(s, 4)
                message_id_bytes = self._receive_exact(s, 1)
                message_len = int.from_bytes(prefix, byteorder='big')
                message_id = int.from_bytes(message_id_bytes, byteorder='big')
                _ = self._receive_exact(s, message_len - 1)
                print(f"message_id in response {message_id}")

                if message_id == MessageType.UNCHOKE:
                    self._download_file(torrent, s, output_path, piece_index)