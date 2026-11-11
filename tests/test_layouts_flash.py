"""Layout tests for the flash data loaders.

Upstream has no loaders for these types; every body follows the kernel read order.
"""
import shutil
import struct
import tempfile
import unittest

from classes import DbObject
from classes.ObjectLoader import ObjectLoader
from classes.PBL import default_library_path
from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from common_utils import diagnostics
from object_loaders import DB_INLINE_FLASH_DATA
from tests import support
from tests.support import REPOSITORY_ROOT, ObjectBytes

LIBRARY = default_library_path(REPOSITORY_ROOT)


def type_code():
    return bytearray(struct.pack('<H', support.object_type_code('DB_INLINE_FLASH_DATA')))


class InlineFlashDataTests(unittest.TestCase):
    def test_db_inline_flash_data_minimal(self):
        result = support.load('DB_INLINE_FLASH_DATA', ObjectBytes().u32(0))
        self.assertEqual(result, {'#OBJECT_TYPE': 'DB_INLINE_FLASH_DATA', 'is_big_data': False,
                                  'inline_flash_data_length': 0})

    def test_db_inline_flash_data_all_branches(self):
        single = support.load('DB_INLINE_FLASH_DATA', ObjectBytes().native_ascii('0A1B'))
        self.assertEqual(single, {'#OBJECT_TYPE': 'DB_INLINE_FLASH_DATA', 'is_big_data': False,
                                  'inline_flash_data_length': 4})
        big = DbObject.load_object_from_parts(
            [type_code(), bytearray(b'0A1B'), bytearray(b'2C')], support.string_storage([], []), strict=True)
        self.assertEqual(big, {'#OBJECT_TYPE': 'DB_INLINE_FLASH_DATA', 'is_big_data': True,
                               'inline_flash_data_length': 6})

    def test_big_data_first_part_with_extra_bytes_is_unread(self):
        parts = [type_code() + b'\x00', bytearray(b'0A1B')]
        with self.assertRaises(diagnostics.UnreadBytesError) as context:
            DbObject.load_object_from_parts(parts, support.string_storage([], []), strict=True)
        self.assertEqual(context.exception.remaining, 1)

    def test_content_bytes_big_data(self):
        parts = [type_code(), bytearray(b'0A1B'), bytearray(b'2c')]
        self.assertEqual(DB_INLINE_FLASH_DATA.content_bytes(parts), b'\x0a\x1b\x2c')

    def test_content_bytes_single_part(self):
        data = ObjectBytes().native_ascii('FF00').build('DB_INLINE_FLASH_DATA')
        self.assertEqual(DB_INLINE_FLASH_DATA.content_bytes([data]), b'\xff\x00')

    def test_content_bytes_rejects_non_hex(self):
        for text in (b'0A1', b'0G'):
            with self.assertRaises(ValueError):
                DB_INLINE_FLASH_DATA.content_bytes([type_code(), bytearray(text)])

    def test_load_inline_flash_data_by_id(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        support.write_project(folder, {}, [], [])
        support.write_raw_pool(folder, 'P1', [(b'Content', [bytes(type_code()), b'0A1B'])])
        loader = ObjectLoader(PblRecordManager(LIBRARY), StringStorage(folder))
        self.assertEqual(loader.load_inline_flash_data_by_id(folder, 'P1', 'Content'), b'\x0a\x1b')
        result = loader.load_object_by_id(folder, 'P1', 'Content')
        self.assertTrue(result['is_big_data'])
        self.assertEqual(result['inline_flash_data_length'], 4)


if __name__ == '__main__':
    unittest.main()
