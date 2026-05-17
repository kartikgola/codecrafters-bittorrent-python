
from dataclasses import dataclass
from enum import IntEnum
import hashlib
import math
import socket
import sys
from typing import Optional

from bencoder.decoder import Decoder
from bencoder.encoder import Encoder
from bittorrent.peer import Peer
from bittorrent.torrent import DEFAULT_BLOCK_LENGTH, Torrent


class MessageIdType(IntEnum):
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    NOT_INTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    PIECE = 7
    EXTENSION = 20


class ProtocolType(IntEnum):
    HANDSHAKE = 0
    MESSAGE = 1


@dataclass(frozen=True)
class Message:
    id: MessageIdType
    payload: bytes


@dataclass(frozen=True)
class PieceMessage(Message):
    piece_index: int
    block_offset: int
    block: bytes


class PeerConnectionStatus(IntEnum):
    NOT_CONNECTED = 0
    CONNECTED = 1
    HANDSHAKED = 2
    CLOSED = 3


class PeerConnection:
    """
    Represents a connection to a peer.
    """

    # number of bytes in the handshake message
    PEER_HANDSHAKE_BYTE_LENGTH = 68
    UT_METADATA_EXTENSION_ID = 1

    def __init__(self, client_id: bytes, peer: Peer, torrent: Torrent, with_extensions: bool = False):
        self._socket = None
        self._peer = peer
        self._torrent = torrent
        self._client_id = client_id
        self._status = PeerConnectionStatus.NOT_CONNECTED
        self._with_extensions = with_extensions

    def handshake(self) -> Peer:
        """
        performs handshake with the peer and updates connection status
        returns peer_id of the peer if handshake is successful, else raises an error
        """
        if self._status != PeerConnectionStatus.NOT_CONNECTED:
            raise ValueError("handshake can only be performed in NOT_CONNECTED status")

        pstr = b"BitTorrent protocol" # 19 bytes
        pstr_len = len(pstr)          # 1 byte
        reserved = b"\x00" * 8        # 8 bytes

        if self._with_extensions:
            reserved = b"\x00" * 5 + b"\x10" + 2 * b"\x00"

        payload = (
            pstr_len.to_bytes(1, byteorder='big') + 
            pstr + 
            reserved + 
            self._torrent.info_hash + 
            self._client_id
        )

        print(f"[peer] connecting to {self._peer.ip}:{self._peer.port}", file=sys.stderr)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self._peer.ip, self._peer.port))
        self._socket.sendall(payload)
        response = self._receive_bytes(self.PEER_HANDSHAKE_BYTE_LENGTH)

        # parse the response to extract peer_id and update connection status
        pstrlen = response[0]
        pstr = response[1:1+pstrlen]
        reserved = response[1+pstrlen: 1+pstrlen+8]
        info_hash = response[1+pstrlen+8 : 1+pstrlen+8+20]
        if pstr != b"BitTorrent protocol" or info_hash != self._torrent.info_hash:
            self.close()
            raise ValueError("invalid peer handshake response")

        peer_id = response[1 + pstrlen + 8 + 20 : self.PEER_HANDSHAKE_BYTE_LENGTH]
        self._status = PeerConnectionStatus.HANDSHAKED
        self._peer = Peer(peer_id, self._peer.ip, self._peer.port, supports_extensions=bool(reserved[5] & 0x10))
        print(f"[peer] handshake complete with {self._peer.ip}:{self._peer.port}", file=sys.stderr)
        return self._peer

    def send_extension_handshake(self) -> Peer:
        if self._status != PeerConnectionStatus.HANDSHAKED:
            raise ValueError("extension handshake requires a handshaked peer connection")

        if not self._peer.supports_extensions:
            raise ValueError("peer does not support extension protocol")

        request_payload = b"\x00" + Encoder().encode({"m": {
            "ut_metadata": self.UT_METADATA_EXTENSION_ID,
            }})
        self.send_message(MessageIdType.EXTENSION, request_payload)

        # wait for extension handshake response
        msg = self._wait_for_message(MessageIdType.EXTENSION)
        response_payload = Decoder().decode(msg.payload[1:])
        self._peer.extension_metadata = response_payload
        return self._peer

    def request_metadata(self) -> None:
        if self._status != PeerConnectionStatus.HANDSHAKED:
            raise ValueError("metadata request requires a handshaked peer connection")

        if self._peer.extension_metadata is None:
            self.send_extension_handshake()

        metadata_extension_id = self._peer.extension_metadata['m']['ut_metadata']
        # send metadata request message
        request_payload = metadata_extension_id.to_bytes(1, byteorder='big') + Encoder().encode({
            "msg_type": 0, # request
            "piece": 0,
        })
        self.send_message(MessageIdType.EXTENSION, request_payload)
        
        # wait for data piece response
        response_message = self._wait_for_message()
        decoder = Decoder()
        # parse the first dict 
        meta_dict = decoder.decode(response_message.payload[1:])
        # parse the 2nd dict
        info_dict = Decoder().decode(response_message.payload[decoder.i + 1:])
        self._torrent._decoded_content = {"info": info_dict}
        # print(info_dict)
        # print(hashlib.sha1(Encoder().encode(info_dict)).hexdigest())

    def _receive_bytes(self, n: int):
        """
        receive exactly n bytes from the socket
        """
        if self._socket is None:
            raise ValueError("connection is not open")

        data = b""
        while len(data) < n:
            chunk = self._socket.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed by peer")
            data += chunk
        return data

    def _prepare_message(self, message_id_type: MessageIdType, payload: bytes) -> bytes:
        length_prefix = 1 + len(payload)
        return (
            length_prefix.to_bytes(4, byteorder='big') +
            message_id_type.to_bytes(1, byteorder='big') + 
            payload
        )

    def download(self, piece_index: Optional[int] = None, quit_early: bool = False) -> bytes:
        """
        Download the complete file, or a single piece when piece_index is provided.
        Returns the downloaded bytes.
        """
        if self._status == PeerConnectionStatus.NOT_CONNECTED:
            self.handshake()
        elif self._status != PeerConnectionStatus.HANDSHAKED:
            raise ValueError("download requires a handshaked peer connection")

        print("[peer] waiting for bitfield", file=sys.stderr)
        self._wait_for_message(MessageIdType.BITFIELD)

        if self._with_extensions:
            if self._torrent.info is None:
                self.request_metadata()
            else:
                self.send_extension_handshake()
        
        if quit_early:
            return b''

        print("[peer] received bitfield; sending interested", file=sys.stderr)
        self.send_message(MessageIdType.INTERESTED, b'')

        print("[peer] waiting for unchoke", file=sys.stderr)
        self._wait_for_message(MessageIdType.UNCHOKE)

        print("[peer] unchoked; starting download", file=sys.stderr)
        
        total_length = self._torrent.info['length']
        piece_length = self._torrent.info['piece length']
        total_pieces = math.ceil(total_length / piece_length)

        if piece_index is not None and (piece_index < 0 or piece_index >= total_pieces):
            raise ValueError(f"piece_index {piece_index} must be between 0 and {total_pieces - 1}")

        start_piece = piece_index if piece_index is not None else 0
        end_piece = start_piece + 1 if piece_index is not None else total_pieces
        downloaded = bytearray()
        print(f"[download] pieces {start_piece}..{end_piece - 1} of {total_pieces}", file=sys.stderr)

        for current_piece in range(start_piece, end_piece):
            piece_data = self._download_piece(current_piece, total_length, piece_length)
            self._verify_piece(current_piece, piece_data)
            downloaded.extend(piece_data)

        return bytes(downloaded)

    def send_message(self, message_id_type: MessageIdType, payload: bytes = b''):
        if self._status == PeerConnectionStatus.CLOSED or self._socket is None:
            raise ValueError("cannot send message on a closed connection")
        self._socket.sendall(self._prepare_message(message_id_type, payload))

    def receive_message(self, message_id_type: Optional[MessageIdType] = None) -> Optional[Message]:
        length_prefix = int.from_bytes(self._receive_bytes(4), byteorder='big')
        if length_prefix == 0:
            return None

        message_id = MessageIdType(int.from_bytes(self._receive_bytes(1), byteorder='big'))
        payload_length = length_prefix - 1
        payload = self._receive_bytes(payload_length) if payload_length > 0 else b''

        if message_id_type is not None and message_id != message_id_type:
            return Message(message_id, payload)

        if message_id == MessageIdType.PIECE:
            piece_index = int.from_bytes(payload[0:4], byteorder='big')
            block_offset = int.from_bytes(payload[4:8], byteorder='big')
            block = payload[8:]
            return PieceMessage(message_id, payload, piece_index, block_offset, block)

        return Message(message_id, payload)

    def _wait_for_message(self, message_id_type: Optional[MessageIdType] = None) -> Message:
        while True:
            message = self.receive_message()
            if message is not None and (message_id_type is None or message.id == message_id_type):
                return message

    def _download_piece(self, piece_index: int, total_length: int, piece_length: int) -> bytes:
        actual_piece_length = min(piece_length, total_length - (piece_index * piece_length))
        piece_data = bytearray()
        print(f"[download] piece {piece_index}: {actual_piece_length} bytes", file=sys.stderr)

        for block_offset in range(0, actual_piece_length, DEFAULT_BLOCK_LENGTH):
            block_length = min(DEFAULT_BLOCK_LENGTH, actual_piece_length - block_offset)
            payload = (
                piece_index.to_bytes(4, byteorder='big') +
                block_offset.to_bytes(4, byteorder='big') +
                block_length.to_bytes(4, byteorder='big')
            )
            print(
                f"[download] requesting piece={piece_index} offset={block_offset} length={block_length}",
                file=sys.stderr,
            )
            self.send_message(MessageIdType.REQUEST, payload)

            while True:
                message = self.receive_message()
                if message is None:
                    continue
                if (
                    isinstance(message, PieceMessage) and
                    message.piece_index == piece_index and
                    message.block_offset == block_offset
                ):
                    piece_data.extend(message.block)
                    break

        return bytes(piece_data)

    def _verify_piece(self, piece_index: int, piece_data: bytes) -> None:
        pieces_hash_bytes = self._torrent.info['pieces']
        expected_piece_hash = pieces_hash_bytes[piece_index * 20: piece_index * 20 + 20]
        actual_piece_hash = hashlib.sha1(piece_data).digest()

        if expected_piece_hash != actual_piece_hash:
            raise ValueError(f"piece {piece_index} hash does not match")
        print(f"[download] verified piece {piece_index}", file=sys.stderr)

    def close(self):
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._status = PeerConnectionStatus.CLOSED

    @property
    def status(self):
        return self._status
