"""Tests for DbStream: reading primitives and strings stored in the stream."""
import struct
import time
import unittest

from classes.DbStream import DbStream
from common_utils import common_loaders
from tests import support


def open_stream(body, trailer=b'', database_version=None):
    """Stream over the body's bytes (plus trailer), positioned after the type code."""
    storage = support.string_storage(body.ascii_strings, body.unicode_strings, database_version)
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

    def test_all_ones_word_is_an_embedded_length(self):
        # kernel: a set top bit is always the length of a string stored in the object
        for load, size in (('loadAsciiString', 2147483647), ('loadUnicodeString', 4294967294)):
            stream = open_stream(support.ObjectBytes().u32(0xFFFFFFFF), b'tail')
            with self.assertRaisesRegex(RuntimeError, 'Cannot read %d bytes' % size):
                getattr(stream, load)()

    def test_empty_three_string_reference_with_all_ones_word(self):
        stream = open_stream(support.ObjectBytes().u32(0).u32(0).u32(0xFFFFFFFF), database_version='0011')
        self.assertEqual(common_loaders.load_reference(stream),
                         {'object_id': None, 'pool_id': None, 'object_id2': 0xFFFFFFFF})

    def test_third_word_is_number_below_0012(self):
        for number in (0xFFFFFFFF, 7):
            body = support.ObjectBytes().ascii('O').ascii('P').u32(number)
            stream = open_stream(body, database_version='0011')
            self.assertEqual(common_loaders.load_reference(stream),
                             {'object_id': 'O', 'pool_id': 'P', 'object_id2': number})
            self.assertEqual(stream.get_length(), 0)

    def test_third_word_is_string_from_0012(self):
        for version in (None, '0012'):
            body = support.ObjectBytes().ascii('O').ascii('P').ascii('T')
            stream = open_stream(body, database_version=version)
            self.assertEqual(common_loaders.load_reference(stream),
                             {'object_id': 'O', 'pool_id': 'P', 'object_id2': 'T'})

    def test_embedded_string_inside_mcd_value(self):
        stream = open_stream(support.ObjectBytes().u8(1).embedded_ascii('V'))
        self.assertEqual(common_loaders.loadMCDValueFromObjectStream(stream),
                         {'data_type': 'eA_ASCIISTRING', 'value': 'V'})

    def test_mcd_value_all_kernel_types(self):
        # kernel: value types and sizes as read by the kernel
        cases = [
            (6, b'\xff\xff', 'eA_INT16', -1),
            (8, b'\xff' * 8, 'eA_INT64', -1),
            (9, b'\xff', 'eA_INT8', -1),
            (10, b'\xff\xff', 'eA_UINT16', 65535),
            (12, b'\xff' * 8, 'eA_UINT64', 18446744073709551615),
            (13, b'\xff', 'eA_UINT8', 255),
            (19, b'\x01', 'eA_BOOLEAN', True),
            (19, b'\x00', 'eA_BOOLEAN', False),
        ]
        for code, payload, name, value in cases:
            with self.subTest(code=code, value=value):
                stream = open_stream(support.ObjectBytes().u8(code).raw(payload), b'tail')
                self.assertEqual(common_loaders.loadMCDValueFromObjectStream(stream),
                                 {'data_type': name, 'value': value})
                self.assertEqual(stream.read(4), b'tail')

    def test_mcd_value_types_without_payload(self):
        for code in (0, 15, 16, 17, 18, 20, 255):
            with self.subTest(code=code):
                stream = open_stream(support.ObjectBytes().u8(code), b'tail')
                self.assertIsNone(common_loaders.loadMCDValueFromObjectStream(stream))
                self.assertEqual(stream.read(4), b'tail')

    def test_native_string_zero_word_is_empty(self):
        for load in ('loadNativeAsciiString', 'loadNativeUnicodeString'):
            stream = open_stream(support.ObjectBytes().u32(0))
            self.assertEqual(getattr(stream, load)(), '')
            self.assertEqual(stream.get_length(), 0)

    def test_native_string_word_without_top_bit_is_empty(self):
        for load in ('loadNativeAsciiString', 'loadNativeUnicodeString'):
            stream = open_stream(support.ObjectBytes().u32(0x1234), b'tail')
            self.assertEqual(getattr(stream, load)(), '')
            self.assertEqual(stream.read(4), b'tail')

    def test_native_unicode_keeps_leading_byte_order_mark(self):
        text = '\ufeffA'
        stream = open_stream(support.ObjectBytes().u32(0x80000002).raw(text.encode('utf-16-le')))
        self.assertEqual(stream.loadNativeUnicodeString(), text)

    def test_embedded_unicode_keeps_leading_byte_order_mark(self):
        text = '\ufeffA'
        stream = open_stream(support.ObjectBytes().embedded_unicode(text))
        self.assertEqual(stream.loadUnicodeString(), (text, None))

    def test_pool_unicode_keeps_leading_byte_order_mark(self):
        text = '\ufeffB'
        storage = support.string_storage([], [text])
        self.assertEqual(storage.get_unicode_string(support.string_hash(text, 'U')), text)

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


class NamedReferenceTests(unittest.TestCase):
    def test_named_collection_rejects_zero_name(self):
        body = support.ObjectBytes().u16(1).u32(0).ascii('O').ascii('P')
        stream = open_stream(body)
        with self.assertRaisesRegex(RuntimeError, 'Named reference without name'):
            common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream)

    def test_named_collection_accepts_embedded_empty_name(self):
        # the check is on the raw name word, not on the resulting string
        body = support.ObjectBytes().u16(1).u32(0x80000000).ascii('O').ascii('P')
        stream = open_stream(body)
        self.assertEqual(
            common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream),
            [{'name': '', 'reference': {'object_id': 'O', 'pool_id': 'P'}}])

    def test_string_to_reference_map_accepts_zero_key(self):
        body = support.ObjectBytes().u16(1).u32(0).ascii('O').ascii('P')
        stream = open_stream(body)
        self.assertEqual(
            common_loaders.loadStringToReferenceMap(stream),
            [{'map_key': None, 'reference': {'object_id': 'O', 'pool_id': 'P'}}])


class UnknownNamedStreamTests(unittest.TestCase):
    READERS = {'A': lambda s: s.loadAsciiString()[0], 'B': lambda s: s.loadAsciiString()[0]}
    END_MARKER = b'#<\x00'

    def load(self, body):
        stream = open_stream(body, self.END_MARKER)
        result = common_loaders.loadNamedStreams(stream, self.READERS)
        self.assertEqual(stream.get_length(), 3)
        return result

    def test_unknown_named_stream_is_skipped(self):
        body = (support.ObjectBytes().raw(b'#>\x00A').ascii('X').raw(b'#>\x01#<\x00')
                .raw(b'D\x01\x02\x03#>\x01#<\x00')
                .raw(b'B').ascii('Y').raw(b'#>\x01'))
        self.assertEqual(self.load(body), {'A': 'X', 'B': 'Y'})

    def test_unknown_last_named_stream_is_skipped(self):
        body = (support.ObjectBytes().raw(b'#>\x00A').ascii('X').raw(b'#>\x01#<\x00')
                .raw(b'D\x01\x02\x03#>\x01'))
        self.assertEqual(self.load(body), {'A': 'X'})

    def test_only_unknown_named_stream_is_skipped(self):
        body = support.ObjectBytes().raw(b'#>\x00D\x01#>\x01')
        self.assertEqual(self.load(body), {})

    def test_truncated_unknown_named_stream_is_rejected(self):
        # after the name of the unknown stream fewer bytes remain than an end marker needs
        body = support.ObjectBytes().raw(b'#>\x00D\x01#>\x01#<\x00#>\x00')
        stream = open_stream(body)
        with self.assertRaisesRegex(RuntimeError, 'runs past the object end'):
            common_loaders.loadNamedStreams(stream, self.READERS)


if __name__ == '__main__':
    unittest.main()
