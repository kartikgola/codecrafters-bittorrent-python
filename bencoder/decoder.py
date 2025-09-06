class BencoderException(ValueError):
    pass

class Decoder:
    def __init__(self):
        self.encoded = ''
        self.i = -1

    def decode(self, encoded):
        """
        decodes a given byte string
        """
        self.encoded = encoded
        self.i = 0
        return self._parse()
    
    def _seek(self, val):
        """
        moves self.i until it reaches val
        val should be of str type
        returns when encoded[self.i] == val
        """


        # NOTE: slicing a byte string produces a value of type 'int'
        # ex, if x = b'abc', type(x) would be bytes but type(x[0]) would be int

        if chr(self.encoded[self.i]) == val:
            return
        while self.i+1 < len(self.encoded):
            self.i += 1
            if chr(self.encoded[self.i]) == val:
                return

    def _parse_int(self):
        """
        i will be at b'i'
        parses int of the type b'i52e', b'i-52e', b'i0e', etc
        """
        self.i += 1 # move past i
        start = self.i # inside int
        self._seek('e') # now self.i is at the next e
        
        slice = self.encoded[start: self.i] # from start till e (exclusive)
        val = int(slice)
        self.i += 1
        return val

    def _parse_dict(self):
        """
        parses a dict like d3:foo3:bar5:helloi52ee into {"foo": "bar", "hello": 52}
        value of a key may itself be a dictionary
        """
        dct = {}
        self.i += 1 # move past d
        while True:
            if self.encoded[self.i] == ord('e'):
                self.i += 1
                return dct
            key = self._parse()
            val = self._parse()
            dct[key] = val

    def _parse_list(self):
        """
        parses a list of the form b'l5:helloi52ee' (= ["hello", 52])
        can also be a nested list like l l l e e e
        """
        lst = []
        self.i += 1 # move past l
        while True:
            if self.encoded[self.i] == ord('e'):
                self.i += 1
                return lst
            lst.append(self._parse())

    def _parse_str(self):
        """
        i will be at a digit like b'5...'
        parses str of the type b'1:a' or b'10:abcdeabcde'
        """
        start = self.i
        self._seek(':') # now self.i is at :
        size = int(self.encoded[start: self.i])

        self.i += 1 # move to first char of str
        start = self.i
        val = "".join([chr(int_val) for int_val in self.encoded[start: start + size]])
        self.i += size
        return val

    def _parse(self):
        ch = self.encoded[self.i]
        if ch == ord('i'):
            return self._parse_int()
        elif ch == ord('l'):
            return self._parse_list()
        elif ch == ord('d'):
            return self._parse_dict()
        elif ch in b'0123456789':
            return self._parse_str()
        else:
            raise BencoderException("unknown character")