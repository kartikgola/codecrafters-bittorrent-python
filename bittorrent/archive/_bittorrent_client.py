from collections import defaultdict
import hashlib
from http import HTTPStatus
import math
import os
from pathlib import Path
import socket
from typing import Dict, List, Tuple
 
import requests

from bencoder import decoder
from client.torrent import Torrent
from models import *


class BitTorrentClient:
    def __init__(self):
        # generate a 20 bytes random client id on startup for the current BitTorrent client
        self._client_id = os.urandom(20)

        # map of torrent info hash (bytes) to torrent obj
        self._torrents: Dict[bytes, Torrent] = {}
    
    def load_torrent(self, file_path: str) -> Torrent:
        """
        load the torrent using the file_path string
        returns Torrent object
        """
        torrent = Torrent(file_path)
        self._torrents.setdefault(torrent.info_hash, torrent)
        return self._torrents[torrent.info_hash]
    
    def _send_message(self, request_message_id_type: MessageIdType, payload: bytes, s: socket.socket) -> None:
        """
        send a message to the peer (does not wait for response)
        """
        length_prefix = 1 + len(payload)
        message_bytes = (
            length_prefix.to_bytes(4) +
            request_message_id_type.to_bytes(1) + 
            payload
        )
        s.sendall(message_bytes)
    
    def _receive_message(self, s: socket.socket) -> Message:
        """
        receive a message from the peer and return the response message
        """
        len_prefix = int.from_bytes(self._receive_bytes(s, 4), byteorder='big')
        if len_prefix == 0:
            # keep-alive message
            return None
        response_message_id = int.from_bytes(self._receive_bytes(s, 1), byteorder='big')
        payload_length = len_prefix - 1  # subtract 1 for the message ID byte
        
        match response_message_id:
            case MessageIdType.PIECE:
                piece_index = int.from_bytes(self._receive_bytes(s, 4), byteorder='big')
                block_id = int.from_bytes(self._receive_bytes(s, 4), byteorder='big')
                block = self._receive_bytes(s, payload_length - 4 - 4)  # subtract piece_index and block_id
                return PieceMessage(piece_index, block_id, block)
            case _:
                # otherwise, consume the payload to keep the stream in sync
                payload = b''
                if payload_length > 0:
                    payload = self._receive_bytes(s, payload_length)
                return Message(response_message_id, payload)
    
    def _download_file(self, torrent: Torrent, s: socket.socket, output_path: str, piece_index: int = None):
        total_length = torrent.info['length']
        piece_length = torrent.info['piece length']
        pieces_hash_bytes = torrent.info['pieces']
        total_pieces = math.ceil(total_length / piece_length)
        downloaded_blocks = b''

        print(f"downloading {torrent}", total_length, piece_length, total_pieces)

        # ensure file doesn't exist already
        if os.path.exists(output_path):
            raise ValueError(f"file {output_path} already exists")

        download_single_piece = piece_index is not None
        if piece_index is None:
            piece_index = 0

        if piece_index >= total_pieces:
            raise ValueError(f"piece_index {piece_index} cannot be >= total_pieces {total_pieces}")

        # downloading pieces starting from begin_index
        for piece_id in range(piece_index, total_pieces):
            # Calculate actual piece size (last piece may be smaller)
            actual_piece_length = min(piece_length, total_length - (piece_id * piece_length))

            # download all blocks within a piece
            for block_id in range(0, actual_piece_length, DEFAULT_BLOCK_LENGTH):
                # calculate the size of last block (since it can be smaller)
                block_length = min(DEFAULT_BLOCK_LENGTH, actual_piece_length - block_id)
                payload = (
                    piece_id.to_bytes(4) + 
                    block_id.to_bytes(4) + 
                    block_length.to_bytes(4)
                )

                print("sending request", piece_id, block_id, block_length)
                self._send_message(MessageIdType.REQUEST, payload, s)

                # read messages until we get PIECE
                while True:
                    message = self._receive_message(s)
                    if message is None:
                        continue  # keep-alive, skip
                    if isinstance(message, PieceMessage):
                        # verify it's the piece we requested
                        if message.piece_index == piece_id and message.block_id == block_id:
                            print("received piece message")
                            downloaded_blocks += message.block
                            break
                        else:
                            # Wrong piece, continue waiting
                            continue
                    else:
                        # handle other message types
                        print(f"received message {message.id}, continuing to wait for PIECE")
                        continue
            
            expected_piece_hash = pieces_hash_bytes[piece_id * 20: piece_id * 20 + 20]
            actual_piece_hash = hashlib.sha1(downloaded_blocks).digest()

            if expected_piece_hash != actual_piece_hash:
                raise ValueError(f"piece hash doesn't match")
            
            with open(output_path, 'ab') as f:
                f.write(downloaded_blocks)
            
            downloaded_blocks = b''

            if download_single_piece:
                break
    
    def download(self, torrent: Torrent, output_path: str, piece_index: int = None):
        peers = self.get_torrent_peer_address(torrent)
        peer_ip, peer_port = peers[0].split(":")
        peer_port = int(peer_port)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((peer_ip, peer_port))
            self._do_handshake(torrent, s)

            # wait for bitfield message
            message = self._receive_message(s)
            if message.id != MessageIdType.BITFIELD:
                raise ValueError(f"expected BITFIELD message, got {message.id}")

            # send interested message
            self._send_message(MessageIdType.INTERESTED, b'', s)
            
            # wait for UNCHOKE message
            while True:
                message = self._receive_message(s)
                if message is None:
                    continue  # keep-alive
                if message.id == MessageIdType.UNCHOKE:
                    break
                print(f"received message {message.id}, waiting for UNCHOKE")
            
            return self._download_file(torrent, s, output_path, piece_index)