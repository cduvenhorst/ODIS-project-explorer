import io
import os
import shutil
import struct
import tempfile
import unittest
import zlib

from classes.ObjectLoader import ObjectLoader
from classes.PBL import default_library_path
from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from tests import support
from tests.support import REPOSITORY_ROOT, string_hash, unit_body

LIBRARY = default_library_path(REPOSITORY_ROOT)


class PblRecordTests(unittest.TestCase):
    def make_folder(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        support.write_project(folder, {}, [], [])
        return folder

    def test_name_keys_are_listed_as_strings(self):
        folder = self.make_folder()
        support.write_raw_pool(folder, 'P1', [
            (string_hash('Good', 'A').to_bytes(4, 'little'), [b'one']),
            (b'NamedObject', [b'two'])])
        records = PblRecordManager(LIBRARY).get_all_records(folder, 'P1')
        self.assertEqual(set(records), {string_hash('Good', 'A'), 'NamedObject'})

    def test_multi_part_record_is_concatenated(self):
        folder = self.make_folder()
        support.write_raw_pool(folder, 'P1', [(b'NamedObject', [b'\x1f\x03', b'payload'])])
        records = PblRecordManager(LIBRARY).get_all_records(folder, 'P1')
        with open(os.path.join(folder, 'P1.db'), 'rb') as db_file:
            data = ObjectLoader.get_object_data_from_opened_db_file(records['NamedObject'], db_file)
        self.assertEqual(data, b'\x1f\x03payload')

    def loader(self, folder):
        return ObjectLoader(PblRecordManager(LIBRARY), StringStorage(folder))

    def test_load_object_by_id_falls_back_to_name_key(self):
        folder = self.make_folder()
        body = unit_body()
        support.write_raw_pool(folder, 'P1', [(b'UnitByName', [bytes(body.build('MCD_DB_UNIT'))])])
        support.write_project(folder, {}, body.ascii_strings, body.unicode_strings)
        result = self.loader(folder).load_object_by_id(folder, 'P1', 'UnitByName')
        self.assertEqual(result['short_name'], 'U_km')

    def test_load_object_by_id_prefers_hash_key(self):
        folder = self.make_folder()
        by_hash = support.ObjectBytes().ascii('U_hash').unicode('Kilometer').unicode(None).ascii('UID')
        by_name = support.ObjectBytes().ascii('U_name').unicode('Kilometer').unicode(None).ascii('UID')
        for body in (by_hash, by_name):
            body.ascii(None).ascii(None).unicode('km').double(1000.0).double(0.0).absent().flag(False)
        support.write_raw_pool(folder, 'P1', [
            (string_hash('SameName', 'A').to_bytes(4, 'little'), [bytes(by_hash.build('MCD_DB_UNIT'))]),
            (b'SameName', [bytes(by_name.build('MCD_DB_UNIT'))])])
        support.write_project(folder, {}, by_hash.ascii_strings + by_name.ascii_strings + ['SameName'],
                              by_hash.unicode_strings)
        result = self.loader(folder).load_object_by_id(folder, 'P1', 'SameName')
        self.assertEqual(result['short_name'], 'U_hash')

    def test_load_object_by_id_finds_four_byte_name_key(self):
        folder = self.make_folder()
        body = support.ObjectBytes().ascii('U_four').unicode('Kilometer').unicode(None).ascii('UID')
        body.ascii(None).ascii(None).unicode('km').double(1000.0).double(0.0).absent().flag(False)
        support.write_raw_pool(folder, 'P1', [(b'ABCD', [bytes(body.build('MCD_DB_UNIT'))])])
        support.write_project(folder, {}, body.ascii_strings + ['ABCD'], body.unicode_strings)
        result = self.loader(folder).load_object_by_id(folder, 'P1', 'ABCD')
        self.assertEqual(result['short_name'], 'U_four')

    def test_load_object_by_id_reports_missing_name(self):
        folder = self.make_folder()
        support.write_raw_pool(folder, 'P1', [(b'Other', [b'x'])])
        with self.assertRaises(KeyError) as context:
            self.loader(folder).load_object_by_id(folder, 'P1', 'Missing')
        self.assertIn('Missing', str(context.exception))

    def test_invalid_record_data_length_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Invalid PBL data length: 16'):
            PblRecordManager.parse_pbl_parts(bytes(16))

    def test_parts_of_longer_record_data(self):
        data = struct.pack('<IIIII', 7, 3, 4, 5, 6)
        self.assertEqual(PblRecordManager.parse_pbl_parts(data[:12] + struct.pack('<II', 5, 6)),
                         (7, [(3, 4), (5, 6)]))

    def test_wrong_part_size_is_rejected(self):
        first, second = zlib.compress(b'abc'), zlib.compress(b'defg')
        record = struct.pack('<IIIII', 0, len(first), 3, len(second), 99)
        with self.assertRaisesRegex(RuntimeError, 'Wrong data length'):
            ObjectLoader.get_object_data_from_opened_db_file(record, io.BytesIO(first + second))


if __name__ == '__main__':
    unittest.main()
