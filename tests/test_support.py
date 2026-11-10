import os
import shutil
import tempfile
import unittest

from classes.ObjectLoader import ObjectLoader
from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from tests import support
from tests.support import ObjectBytes, REPOSITORY_ROOT, unit_body

EXPECTED_UNIT = {
    '#OBJECT_TYPE': 'MCD_DB_UNIT',
    'short_name': 'U_km',
    'long_name': 'Kilometer',
    'description': None,
    'unique_object_id': 'UID',
    'long_name_id': None,
    'description_id': None,
    'display_name': 'km',
    'factor_si_to_unit': 1000.0,
    'offset_si_to_unit': 0.0,
    'physical_dimension': None,
    'unit_group_refs': None,
}


class SupportTests(unittest.TestCase):
    def test_string_storage_round_trip(self):
        storage = support.string_storage(['ABC'], ['Größe'])
        self.assertEqual(storage.get_ascii_string(storage.get_ascii_hash('ABC')), 'ABC')
        self.assertEqual(storage.get_unicode_string(storage.get_unicode_hash('Größe')), 'Größe')

    def test_object_type_code_inverts_the_enum_table(self):
        self.assertEqual(support.object_type_code('MCD_DB_UNIT'), 0x0102)

    def test_build_prefixes_type_code_and_appends_end_marker(self):
        data = ObjectBytes().u8(7).build('MCD_DB_UNIT')
        self.assertEqual(data, bytearray(b'\x02\x01\x07#>\x00'))

    def test_primitive_encodings(self):
        body = ObjectBytes().u16(0x0102).u32(1).i32(-1).flag(True).raw(b'\xAA')
        self.assertEqual(bytes(body.build('DB_UNKNOWN')),
                         b'\x00\x00' + b'\x02\x01' + b'\x01\x00\x00\x00' + b'\xff\xff\xff\xff' + b'\x01\xaa' + b'#>\x00')

    def test_none_string_writes_hash_zero_and_collects_nothing(self):
        body = ObjectBytes().ascii(None).unicode(None)
        self.assertEqual(bytes(body.build('DB_UNKNOWN'))[2:10], bytes(8))
        self.assertEqual(body.ascii_strings, [])
        self.assertEqual(body.unicode_strings, [])

    def test_strings_are_collected_in_order(self):
        body = ObjectBytes().ascii('a').unicode('b').ascii('c')
        self.assertEqual(body.ascii_strings, ['a', 'c'])
        self.assertEqual(body.unicode_strings, ['b'])

    def test_native_strings_round_trip_through_a_loader_shaped_read(self):
        data = ObjectBytes().native_ascii('Ab').native_unicode('Hé').native_ascii(None).native_unicode(None)
        self.assertEqual(bytes(data.build('DB_UNKNOWN')[2:-3]),
                         b'\x02\x00\x00\x80Ab' + b'\x02\x00\x00\x80H\x00\xe9\x00' + bytes(8))

    def test_nested_writes_existence_flag_type_code_and_body(self):
        data = ObjectBytes().nested('MCD_DB_UNIT', ObjectBytes().u8(9)).absent()
        self.assertEqual(bytes(data.build('DB_UNKNOWN')[2:-3]), b'\x01\x02\x01\x09\x00')

    def test_nested_merges_strings_of_the_body(self):
        data = ObjectBytes().nested('MCD_DB_UNIT', ObjectBytes().ascii('x'))
        self.assertEqual(data.ascii_strings, ['x'])

    def test_loads_unit_from_synthetic_bytes(self):
        self.assertEqual(support.load('MCD_DB_UNIT', unit_body()), EXPECTED_UNIT)

    def test_write_project_round_trip(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        body = unit_body()
        support.write_project(folder, {'P1': {'U_km': body.build('MCD_DB_UNIT')}},
                              body.ascii_strings, body.unicode_strings)
        for name in ('P1.key', 'P1.db', 'AStringData.data.gz', 'AStringData.idx.gz',
                     'UStringData.data.gz', 'UStringData.idx.gz'):
            self.assertTrue(os.path.isfile(os.path.join(folder, name)), name)
        loader = ObjectLoader(PblRecordManager(os.path.join(REPOSITORY_ROOT, 'bin', 'pbl.dll')),
                              StringStorage(folder))
        self.assertEqual(loader.load_object_by_id(folder, 'P1', 'U_km'), EXPECTED_UNIT)

    def test_write_project_holds_several_objects_in_one_pool(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        objects = {'First': unit_body().build('MCD_DB_UNIT'), 'Second': unit_body().build('MCD_DB_UNIT')}
        support.write_project(folder, {'P1': objects}, unit_body().ascii_strings, unit_body().unicode_strings)
        loader = ObjectLoader(PblRecordManager(os.path.join(REPOSITORY_ROOT, 'bin', 'pbl.dll')),
                              StringStorage(folder))
        self.assertEqual(loader.load_object_by_id(folder, 'P1', 'Second'), EXPECTED_UNIT)
        self.assertEqual(loader.load_object_by_id(folder, 'P1', 'First'), EXPECTED_UNIT)


if __name__ == '__main__':
    unittest.main()
