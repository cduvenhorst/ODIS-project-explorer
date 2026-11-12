import contextlib
import io
import unittest

from classes import DbObject
from classes.DbStream import DbStream
from common_utils import diagnostics
from tests import support
from tests.support import ObjectBytes, unit_body


def logical_link_body(refs_counter):
    body = ObjectBytes().ascii('LL').unicode('Link').unicode(None)
    body.ascii('UID').ascii(None).ascii(None)
    body.ascii('PROTO').ascii('BV').ascii('FG').ascii('TYPE')
    body.u16(refs_counter)
    body.ascii('REF').ascii('POOL').ascii(None)
    body.u16(0x6E03).flag(False)
    return body.u16(0).u16(0)


class StrictReadingTests(unittest.TestCase):
    def test_strict_rejects_unread_bytes(self):
        with self.assertRaises(diagnostics.UnreadBytesError) as caught:
            support.load('MCD_DB_UNIT', unit_body().u8(7), strict=True)
        self.assertEqual(caught.exception.remaining, 1)
        self.assertEqual(caught.exception.object_type, 'MCD_DB_UNIT')

    def test_default_mode_still_loads_with_unread_bytes(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = support.load('MCD_DB_UNIT', unit_body().u8(7), strict=False)
        self.assertEqual(result['short_name'], 'U_km')
        self.assertIn('not empty', output.getvalue())

    def test_logical_link_refs_are_unread_content_in_strict_mode(self):
        with self.assertRaises(diagnostics.UnreadContentError):
            support.load('MCD_DB_LOGICAL_LINK', logical_link_body(1), strict=True)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            support.load('MCD_DB_LOGICAL_LINK', logical_link_body(1), strict=False)
        self.assertIn('logical link refs not 0', output.getvalue())

    def test_strict_mode_is_reset_after_error(self):
        with self.assertRaises(diagnostics.UnreadBytesError):
            support.load('MCD_DB_UNIT', unit_body().u8(7), strict=True)
        self.assertFalse(diagnostics.is_strict())

    def test_strict_load_of_clean_object_succeeds(self):
        support.load('MCD_DB_UNIT', unit_body(), strict=True)
        self.assertFalse(diagnostics.is_strict())


def stream_of(body):
    """DbStream over the raw bytes of body, with the strings it registered."""
    storage = support.string_storage(body.ascii_strings, body.unicode_strings)
    return DbStream(bytearray(body._data), storage)


def unit_object(presence):
    unit = unit_body()
    body = ObjectBytes().u8(presence).u16(support.object_type_code('MCD_DB_UNIT')).raw(unit._data)
    body.ascii_strings = unit.ascii_strings
    body.unicode_strings = unit.unicode_strings
    return body


class EmbeddedObjectTests(unittest.TestCase):
    def test_presence_byte_above_one_loads_object(self):
        expected = DbObject.load_object_from_stream_if_exists(stream_of(unit_object(1)))
        self.assertEqual(expected['#OBJECT_TYPE'], 'MCD_DB_UNIT')
        for presence in (2, 0x7F, 0xFF):
            result = DbObject.load_object_from_stream_if_exists(stream_of(unit_object(presence)))
            self.assertEqual(result, expected)

    def test_type_code_zero_gives_none(self):
        stream = stream_of(ObjectBytes().u8(1).u16(0).raw(b'tail'))
        self.assertIsNone(DbObject.load_object_from_stream_if_exists(stream))
        self.assertEqual(bytes(stream.read(4)), b'tail')

    def test_load_object_from_stream_type_code_zero_consumes_two_bytes(self):
        stream = stream_of(ObjectBytes().u16(0).raw(b'tail'))
        self.assertIsNone(DbObject.load_object_from_stream(stream))
        self.assertEqual(bytes(stream.read(4)), b'tail')

    def test_type_code_zero_inside_collection(self):
        unit = unit_object(1)
        body = ObjectBytes().u8(1).u16(0).raw(unit._data)
        body.ascii_strings = unit.ascii_strings
        body.unicode_strings = unit.unicode_strings
        stream = stream_of(body)
        first = DbObject.load_object_from_stream_if_exists(stream)
        second = DbObject.load_object_from_stream_if_exists(stream)
        self.assertIsNone(first)
        self.assertEqual(second['#OBJECT_TYPE'], 'MCD_DB_UNIT')
