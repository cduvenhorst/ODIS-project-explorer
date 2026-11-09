import contextlib
import io
import unittest

from common_utils import diagnostics
from tests import support
from tests.support import ObjectBytes
from tests.test_support import unit_body


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
