class Encoder:
    def __init__(self):
        pass

    def encode(self, data) -> bytes:
        """
            Encodes data to bencode format and returns bytes
            The program always does byte manipulation internally.
        """
        if isinstance(data, dict):
            result = b'd'
            for key in sorted(data.keys()):
                result += self.encode(key)
                result += self.encode(data[key])
            return result + b'e'
        elif isinstance(data, bytes):
            return str(len(data)).encode() + b':' + data
        elif isinstance(data, str):
            encoded = data.encode('utf-8')
            return str(len(encoded)).encode() + b':' + encoded
        elif isinstance(data, int):
            return b'i' + str(int(data)).encode() + b'e'
        elif isinstance(data, list):
            result = b'l'
            for item in data:
                result += self.encode(item)
            return result + b'e'
        else:
            print("error")
            raise TypeError(f"Type not serializable: {type(data)}")