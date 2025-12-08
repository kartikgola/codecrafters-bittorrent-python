import json
import random
import sys
from bencoder.decoder import Decoder
from bencoder.encoder import Encoder
import hashlib
import requests
import string

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
        try:
            with open(file_path, 'rb') as f:
                binary_content = f.read()
                decoder = Decoder()
                decoded_content = decoder.decode(binary_content)
                
                # Helper function to convert bytes to hex string for display
                def bytes_to_str(data):
                    if isinstance(data, bytes):
                        return data.hex()
                    raise TypeError(f"Type not serializable: {type(data)}")

                print(decoded_content)

                print(f"Tracker URL: {decoded_content.get('announce', '')}")
                print(f"Length: {decoded_content['info']['length']}")
                
                encoded_info = Encoder().encode(decoded_content['info'])
                print(f"Info Hash: {hashlib.sha1(encoded_info).hexdigest()}")
                print(f"Piece Length: {decoded_content['info']['piece length']}")
                print(f"Piece Hashes:")

                pieces = decoded_content['info']['pieces']
                for i in range(0, len(pieces), 20):
                    print(pieces[i: i+20].hex())
        except Exception as e:
            print(e, file=sys.stderr)
    elif command == "peers":
        file_path = sys.argv[2]
        try:
            with open(file_path, 'rb') as f:
                binary_content = f.read()
                decoder = Decoder()
                decoded_content = decoder.decode(binary_content)
                
                # Helper function to convert bytes to hex string for display
                def bytes_to_str(data):
                    if isinstance(data, bytes):
                        return data.hex()
                    raise TypeError(f"Type not serializable: {type(data)}")
                
                announce_url = decoded_content['announce']
                encoded_info = Encoder().encode(decoded_content['info'])

                response = requests.get(announce_url, params={
                    # info_hash: the info hash of the torrent
                    # 20 bytes long, will need to be URL encoded
                    # Note: this is NOT the hexadecimal representation, which is 40 bytes long
                    "info_hash": hashlib.sha1(encoded_info).digest(),
                    "peer_id": "".join(random.choices(string.ascii_letters, k=20)),
                    "port": 6881,
                    "uploaded": 0,
                    "downloaded": 0,
                    "left": decoded_content['info']['length'],
                    "compact": 1
                })

                if response.status_code == 200:
                    response_decoded = decoder.decode(response.content)
                    peers = []
                    peers_data = response_decoded['peers']

                    for i in range(0, len(peers_data), 6):
                        ip_bytes = peers_data[i: i+4]
                        port_bytes = peers_data[i+4: i+6]

                        ip = ".".join(str(b) for b in ip_bytes)
                        port = "".join(str(b) for b in port_bytes)

                        peers.append(ip + ":" + port)
                    
                    for peer in peers:
                        print(peer)
                else:
                    print(f"error: {response.status_code}")
        except Exception as e:
            print(e, file=sys.stderr)
    else:
        raise NotImplementedError(f"Unknown command {command}")


if __name__ == "__main__":
    main()
