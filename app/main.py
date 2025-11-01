import json
import sys
from bencoder.decoder import Decoder

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
                print(f"Tracker URL: {decoded_content["announce"]}")
                print(f"Length: {decoded_content["info"]["length"]}")
        except Exception as e:
            print("error {e}")
    else:
        raise NotImplementedError(f"Unknown command {command}")


if __name__ == "__main__":
    main()
