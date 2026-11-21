"""Tests for reading single records from the SDG key and data files."""
import os
import tempfile
import unittest

from classes import DbObject
from common_utils.sdg_files import SdgFile
from tests import support
from tests.support import sdg_element_body, sdg_group_body, write_sdg_file


class SdgFileTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = folder.name

    def test_record_numbers_start_at_one(self):
        write_sdg_file(self.folder, 'A.sd', [b'first', b'second!'])
        sdg = SdgFile.open(self.folder, 'A.sd')
        self.assertEqual(sdg.record_count, 2)
        self.assertEqual(sdg.record(1), bytearray(b'first'))
        self.assertEqual(sdg.record(2), bytearray(b'second!'))
        self.assertIsInstance(sdg.record(1), bytearray)

    def test_out_of_range_gives_none(self):
        write_sdg_file(self.folder, 'A.sd', [b'first', b'second!'])
        sdg = SdgFile.open(self.folder, 'A.sd')
        self.assertIsNone(sdg.record(0))
        self.assertIsNone(sdg.record(3))
        self.assertIsNone(sdg.record(-1))

    def test_missing_sdg_file_gives_none(self):
        self.assertIsNone(SdgFile.open(self.folder, 'A.sd'))

    def test_missing_key_file_raises(self):
        write_sdg_file(self.folder, 'A.sd', [b'x'])
        os.remove(os.path.join(self.folder, 'SDG_A.sd.kix.gz'))
        with self.assertRaises(FileNotFoundError):
            SdgFile.open(self.folder, 'A.sd')

    def test_record_loads_as_special_data_group(self):
        body = sdg_group_body(items=(('MCD_DB_SPECIAL_DATA_ELEMENT',
                                      sdg_element_body('T1', 'C1')),))
        write_sdg_file(self.folder, 'A.sd', [body.build('MCD_DB_SPECIAL_DATA_GROUP')])
        storage = support.string_storage(body.ascii_strings, body.unicode_strings)
        result = DbObject.load_object(SdgFile.open(self.folder, 'A.sd').record(1),
                                      storage, strict=True)
        self.assertEqual(result['#OBJECT_TYPE'], 'MCD_DB_SPECIAL_DATA_GROUP')
        self.assertEqual(result['items'][0]['text_id'], 'T1')
