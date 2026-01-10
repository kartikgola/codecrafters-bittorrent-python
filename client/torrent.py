import hashlib
from bencoder.decoder import Decoder
from bencoder.encoder import Encoder

class Torrent:
    def __init__(self, file_path):
        with open(file_path, 'rb') as f:
            self.binary_content = f.read()
            self.decoded_content = Decoder().decode(self.binary_content)

    @property
    def info_hash(self) -> bytes:
        """
        returns 20 bytes of SHA1 digest of torrent's encoded info
        """
        encoded_info = Encoder().encode(self.decoded_content['info'])
        return hashlib.sha1(encoded_info).digest()
    
    @property
    def info_hex_hash(self) -> str:
        """
        returns string (40 bytes long) of SHA1 hexdigest of torrent's encoded info
        """
        encoded_info = Encoder().encode(self.decoded_content['info'])
        return hashlib.sha1(encoded_info).hexdigest()
    
    @property
    def info(self):
        return self.decoded_content['info']
    
    @property
    def announce(self):
        return self.decoded_content['announce']