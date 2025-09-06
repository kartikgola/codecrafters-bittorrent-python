import unittest
from bencoder.decoder import Decoder

class TestDivideFunction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Called once before all tests in this class"""
        cls.decoder = Decoder()
    
    def test_decode_list(self):
        self.assertEqual(self.decoder.decode(b'l5:helloi52ee'), ["hello", 52])
        self.assertEqual(self.decoder.decode(b'l1:a1:b1:ci-123ee'), ["a", "b", "c", -123])
        self.assertEqual(self.decoder.decode(b'llleee'), [[[]]])
        self.assertEqual(self.decoder.decode(b'l1:al1:al1:aeee'), ["a", ["a", ["a"]]])

    def test_decode_dict(self):
        self.assertEqual(self.decoder.decode(b'd3:foo3:bar5:helloi52ee'), {"foo": "bar", "hello": 52})
        self.assertEqual(self.decoder.decode(b'd1:adee'), {"a": {}})
        self.assertEqual(self.decoder.decode(b'd1:ade2:abdee'), {"a": {}, "ab": {}})
        self.assertEqual(self.decoder.decode(b'd10:inner_dictd4:key16:value14:key2i42e8:list_keyl5:item15:item2i3eeee'), {"inner_dict":{"key1":"value1","key2":42,"list_key":["item1","item2",3]}})

if __name__ == '__main__':
    unittest.main()
