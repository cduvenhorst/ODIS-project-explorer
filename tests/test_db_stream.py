"""Tests for DbStream: reading primitives and strings stored in the stream."""
import struct
import time
import unittest

from classes.DbStream import DbStream
from common_utils import common_loaders
from tests import support


def open_stream(body, trailer=b''):
    """Stream over the body's bytes (plus trailer), positioned after the type code."""
    storage = support.string_storage(body.ascii_strings, body.unicode_strings)
    stream = DbStream(bytearray(b'\x00\x00') + body._data + trailer, storage)
    stream.report_unread_on_delete = False
    stream.loadEnumMediumRange()
    return stream


class DbStreamTests(unittest.TestCase):
    def test_pool_ascii_string_is_unchanged(self):
        stream = open_stream(support.ObjectBytes().ascii('Name'))
        self.assertEqual(stream.loadAsciiString(), ('Name', support.string_hash('Name', 'A')))

    def test_pool_unicode_string_is_unchanged(self):
        stream = open_stream(support.ObjectBytes().unicode('Name'))
        self.assertEqual(stream.loadUnicodeString(), ('Name', support.string_hash('Name', 'U')))

    def test_zero_key_is_unchanged(self):
        stream = open_stream(support.ObjectBytes().u32(0).u32(0))
        self.assertEqual(stream.loadAsciiString(), (None, 0))
        self.assertEqual(stream.loadUnicodeString(), (None, 0))

    def test_read_returns_requested_bytes_in_order(self):
        stream = open_stream(support.ObjectBytes().raw(b'abcdef'))
        self.assertEqual(stream.read(2), b'ab')
        self.assertEqual(stream.read(0), b'')
        self.assertEqual(stream.read(3), b'cde')
        self.assertEqual(stream.get_length(), 1)
        with self.assertRaisesRegex(RuntimeError, 'Cannot read 2 bytes, only have 1'):
            stream.read(2)

    def test_embedded_ascii_string(self):
        stream = open_stream(support.ObjectBytes().embedded_ascii('Äb'), b'tail')
        self.assertEqual(stream.loadAsciiString(), ('Äb', None))
        self.assertEqual(stream.get_length(), 4)

    def test_embedded_unicode_string(self):
        stream = open_stream(support.ObjectBytes().embedded_unicode('Ωx'), b'tail')
        self.assertEqual(stream.loadUnicodeString(), ('Ωx', None))
        self.assertEqual(stream.get_length(), 4)

    def test_embedded_empty_string(self):
        for load in ('loadAsciiString', 'loadUnicodeString'):
            stream = open_stream(support.ObjectBytes().u32(0x80000000), b'tail')
            self.assertEqual(getattr(stream, load)(), ('', None))
            self.assertEqual(stream.get_length(), 4)

    def test_all_ones_word_is_a_pool_key(self):
        for load in ('loadAsciiString', 'loadUnicodeString'):
            stream = open_stream(support.ObjectBytes().u32(0xFFFFFFFF), b'tail')
            self.assertEqual(getattr(stream, load)(), (None, 0xFFFFFFFF))
            self.assertEqual(stream.get_length(), 4)

    def test_empty_three_string_reference_with_all_ones_word(self):
        stream = open_stream(support.ObjectBytes().u32(0xFFFFFFFF).u32(0).u32(0))
        self.assertEqual(common_loaders.load_reference(stream),
                         {'object_id': None, 'pool_id': None, 'object_id2': None})

    def test_embedded_string_inside_mcd_value(self):
        stream = open_stream(support.ObjectBytes().u8(1).embedded_ascii('V'))
        self.assertEqual(common_loaders.loadMCDValueFromObjectStream(stream),
                         {'data_type': 'eA_ASCIISTRING', 'value': 'V'})

    def test_eight_byte_numbers(self):
        stream = open_stream(support.ObjectBytes().u64(2**40 + 5).raw(struct.pack('<q', -2))
                             .raw(b'abc'))
        self.assertEqual(stream.loadNumericType(8), 2**40 + 5)
        self.assertEqual(stream.loadNumericType(8, True), -2)
        with self.assertRaisesRegex(RuntimeError, '1/2/4/8'):
            stream.loadNumericType(3)

    def test_large_read_is_linear(self):
        # Guards against removing bytes one by one from the front of the stream.
        size = 4 * 1024 * 1024
        stream = open_stream(support.ObjectBytes().raw(bytes(size)))
        started = time.perf_counter()
        while stream.get_length() > 0:
            stream.read(64)
        self.assertLess(time.perf_counter() - started, 5)


if __name__ == '__main__':
    unittest.main()
