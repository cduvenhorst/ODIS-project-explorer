import unittest

from common_utils.layer_chain import load_layer_data
from common_utils.table_entries import (CODING_SERVICE_NAMES, KIND_ADAPTATION, KIND_CODING, KIND_MWB,
                                        VW_ADAPTATION_SERVICE_NAME, VW_MWB_SERVICE_NAME, SelectedService,
                                        TableEntryReader)
from tests.script_support import FakeObjectLoader, layer
from tests.table_fixtures import (POOL, diag_com, key_dop_decimal, key_dop_names, ref, service_objects,
                                  sid_parameter, structure, table, table_key_parameter, table_row,
                                  table_struct_parameter, uint_dop, value_parameter)


def key_and_struct(key_byte=1, struct_byte=3):
    return [table_key_parameter(ref('T'), byte_position=key_byte),
            table_struct_parameter(ref('T'), byte_position=struct_byte)]


def mwb_service(name, sid=0x22, key_byte=1, struct_byte=3, responses=1):
    return service_objects(name, [sid_parameter(sid)], [key_and_struct(key_byte, struct_byte)] * responses)


def write_service(name, sid=0x2E, key_byte=1, struct_byte=3):
    return service_objects(name, [sid_parameter(sid)] + key_and_struct(key_byte, struct_byte), [[]])


class SelectServicesTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()

    def select(self, kind, names, *service_object_dicts):
        objects = {}
        for service_objects_dict in service_object_dicts:
            objects.update(service_objects_dict)
        variant = layer(name='EV', diag_com_primitive_references=[diag_com(name) for name in names])
        reader = TableEntryReader(FakeObjectLoader(objects), 'project')
        return reader.select_services(variant, kind)

    def test_porsche_mwb_services_selected_by_structure(self):
        result = self.select(KIND_MWB, ['S_A', 'S_X', 'S_Y'], mwb_service('S_A'),
                             mwb_service('S_X', struct_byte=4), write_service('S_Y'))
        self.assertEqual([s.short_name for s in result], ['S_A'])
        self.assertIs(result[0].is_vw_table_service, False)

    def test_mwb_service_with_two_positive_responses_is_skipped(self):
        self.assertEqual(self.select(KIND_MWB, ['S_A'], mwb_service('S_A', responses=2)), [])

    def test_reference_to_non_service_object_is_skipped(self):
        job = {(POOL, 'service S_J'): {'#OBJECT_TYPE': 'MCD_DB_SINGLE_ECU_JOB'}}
        for kind in (KIND_MWB, KIND_ADAPTATION, KIND_CODING):
            with self.subTest(kind=kind):
                self.assertEqual(self.select(kind, ['S_J'], job), [])

    def test_vw_mwb_service_wins_over_structural_services(self):
        result = self.select(KIND_MWB, ['S_A', VW_MWB_SERVICE_NAME], mwb_service('S_A'),
                             mwb_service(VW_MWB_SERVICE_NAME))
        self.assertEqual([s.short_name for s in result], [VW_MWB_SERVICE_NAME])
        self.assertIs(result[0].is_vw_table_service, True)
        self.assertEqual(result[0].key_parameter['#OBJECT_TYPE'], 'MCD_DB_PARAMETER_TABLE_KEY')
        self.assertEqual(result[0].struct_parameter['#OBJECT_TYPE'], 'MCD_DB_PARAMETER_TABLESTRUCT')

    def test_vw_mwb_service_with_two_positive_responses_raises(self):
        with self.assertRaisesRegex(RuntimeError, 'RDBI service has multiple positive responses'):
            self.select(KIND_MWB, [VW_MWB_SERVICE_NAME], mwb_service(VW_MWB_SERVICE_NAME, responses=2))

    def test_porsche_adaptation_selection_excludes_coding_services(self):
        result = self.select(KIND_ADAPTATION, ['S_W', 'CodingValue_Write'], write_service('S_W'),
                             write_service('CodingValue_Write'))
        self.assertEqual([s.short_name for s in result], ['S_W'])
        self.assertIs(result[0].is_vw_table_service, False)

    def test_vw_adaptation_service_wins_over_structural_services(self):
        result = self.select(KIND_ADAPTATION, ['S_W', VW_ADAPTATION_SERVICE_NAME], write_service('S_W'),
                             write_service(VW_ADAPTATION_SERVICE_NAME, struct_byte=5))
        self.assertEqual([s.short_name for s in result], [VW_ADAPTATION_SERVICE_NAME])
        self.assertIs(result[0].is_vw_table_service, True)

    def test_coding_service_key_at_wrong_byte_raises(self):
        with self.assertRaisesRegex(RuntimeError, 'Expected BYTE-POSITION 1 and BIT-POSITION 0 for Coding table key'):
            self.select(KIND_CODING, ['CodingValue_Write'], write_service('CodingValue_Write', key_byte=2))

    def test_coding_service_struct_at_wrong_byte_raises(self):
        with self.assertRaisesRegex(RuntimeError, 'Expected BYTE-POSITION 3 and BIT-POSITION 0 for Coding table struct'):
            self.select(KIND_CODING, [CODING_SERVICE_NAMES[0]], write_service(CODING_SERVICE_NAMES[0], struct_byte=4))

    def test_coding_service_without_key_raises(self):
        objects = service_objects('CodingValue_Write', [sid_parameter(0x2E), table_struct_parameter(ref('T'))], [[]])
        with self.assertRaisesRegex(RuntimeError, 'Could not find table key request parameter'):
            self.select(KIND_CODING, ['CodingValue_Write'], objects)

    def test_coding_service_name_order_decides(self):
        result = self.select(KIND_CODING, ['CodingValue_Write', CODING_SERVICE_NAMES[0]],
                             write_service('CodingValue_Write'), write_service(CODING_SERVICE_NAMES[0]))
        self.assertEqual([s.short_name for s in result], [CODING_SERVICE_NAMES[0]])
        self.assertIs(result[0].is_vw_table_service, True)

    def test_porsche_coding_service_is_not_a_vw_table_service(self):
        result = self.select(KIND_CODING, ['CodingValue_Write'], write_service('CodingValue_Write'))
        self.assertIs(result[0].is_vw_table_service, False)

    def test_variant_without_matching_service_gives_empty_list(self):
        for kind in (KIND_MWB, KIND_ADAPTATION, KIND_CODING):
            with self.subTest(kind=kind):
                self.assertEqual(self.select(kind, [], {}), [])


def linear_key_dop():
    """Key DOP with a LINEAR COMPU-METHOD, which no table key family uses."""
    scale = {'lower_limit_as_coded_value': None, 'upper_limit_as_coded_value': None,
             'lower_limit': None, 'upper_limit': None,
             'compu_rational_coeffs_as_coded_values': {'numerator': [0, 2], 'denominator': []}}
    dop = uint_dop(bit_length=16)
    dop['compu_method'] = {'compu_category': 'eLINEAR', 'compu_phys_to_internal': None,
                           'compu_internal_to_phys': {'compu_scales': [scale]}}
    return dop


class GetEntriesTest(unittest.TestCase):
    # Fixtures are built fresh per test, since parse_dop changes some parameter objects in place
    def setUp(self):
        self.objects = {(POOL, 'DOP u8'): uint_dop(8)}

    def add_table(self, name, key_dop, rows):
        """Table 'TABLE <name>'; rows is a list of (map key, row short name, row long name)."""
        self.objects[(POOL, 'DOP key ' + name)] = key_dop
        key_map = []
        for map_key, short_name, long_name in rows:
            row_id = 'ROW {} {}'.format(name, short_name)
            struct_id = 'STRUCT {} {}'.format(name, short_name)
            row = table_row(short_name, long_name, map_key, ref(struct_id))
            row['long_name_id'] = 'ID_row_' + short_name
            self.objects[(POOL, row_id)] = row
            self.objects[(POOL, struct_id)] = structure('Struct_' + short_name,
                                                         [value_parameter('Field_1', 0, ref('DOP u8'))],
                                                         byte_length=1)
            key_map.append((map_key, ref(row_id)))
        self.objects[(POOL, 'TABLE ' + name)] = table(ref('DOP key ' + name), key_map)

    def row(self, table_name, short_name):
        return self.objects[(POOL, 'ROW {} {}'.format(table_name, short_name))]

    @staticmethod
    def service(name, table_name, row_short_name=None, is_vw=False):
        return SelectedService(name, table_key_parameter(ref('TABLE ' + table_name), row_short_name=row_short_name),
                               table_struct_parameter(ref('TABLE ' + table_name)), is_vw)

    def get_entries(self, services):
        reader = TableEntryReader(FakeObjectLoader(self.objects), 'project')
        return reader.get_entries([], services)

    def add_decimal_table(self):
        self.add_table('T', key_dop_decimal(), [('257', 'Row_1', 'Row one'), ('258', 'Row_2', 'Row two')])

    def test_vw_whole_table_matches_todays_order_and_names(self):
        self.add_table('T', key_dop_names([(0x0600, 'Coding_B'), (0x0100, 'Coding_A')]),
                       [('Coding_A', 'Row_A', 'Coding_A'), ('Coding_B', 'Row_B', 'Coding_B')])
        entries = self.get_entries([self.service(CODING_SERVICE_NAMES[0], 'T', 'Row_A', is_vw=True)])
        self.assertEqual([e['did'] for e in entries], [0x0600, 0x0100])
        self.assertEqual([e['long_name'] for e in entries], ['Coding_B', 'Coding_A'])
        self.assertEqual(entries[0]['long_name_id'], 'ID_Coding_B')
        self.assertEqual(list(entries[0]), ['did', 'long_name', 'long_name_id', 'description', 'byte_position',
                                            'bit_position', 'structure'])
        self.assertNotIn('services', entries[0])
        self.assertEqual(entries[0]['structure']['type'], 'STRUCTURE')

    def test_vw_whole_table_uses_underscore_workaround(self):
        self.add_table('T', key_dop_names([(0x0101, 'Meas_Value')]), [('Meas Value', 'Row_A', 'Meas Value')])
        entries = self.get_entries([self.service(VW_MWB_SERVICE_NAME, 'T', 'Row_A', is_vw=True)])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['long_name'], 'Meas_Value')
        self.assertEqual(entries[0]['did'], 0x0101)

    def test_vw_whole_table_without_matching_row_raises(self):
        self.add_table('T', key_dop_names([(0x0101, 'Meas_Other')]), [('Meas Value', 'Row_A', 'Meas Value')])
        with self.assertRaisesRegex(RuntimeError, 'Failed to find table row for Meas_Other'):
            self.get_entries([self.service(VW_MWB_SERVICE_NAME, 'T', 'Row_A', is_vw=True)])

    def test_row_reference_decimal_family(self):
        self.add_decimal_table()
        entries = self.get_entries([self.service('S_A', 'T', 'Row_2')])
        self.assertEqual([(e['did'], e['long_name'], e['services']) for e in entries], [(0x0102, 'Row two', ['S_A'])])
        self.assertEqual(entries[0]['long_name_id'], 'ID_row_Row_2')
        self.assertEqual(list(entries[0]), ['did', 'long_name', 'long_name_id', 'description', 'byte_position',
                                            'bit_position', 'structure', 'services'])

    def test_whole_table_decimal_family_follows_key_map(self):
        self.add_table('T', key_dop_decimal(), [('258', 'Row_2', 'Row two'), ('257', 'Row_1', 'Row one')])
        entries = self.get_entries([self.service(VW_ADAPTATION_SERVICE_NAME, 'T', is_vw=True)])
        self.assertEqual([(e['did'], e['long_name']) for e in entries], [(0x0102, 'Row two'), (0x0101, 'Row one')])

    def test_row_reference_name_family_takes_did_from_compu_scale(self):
        self.add_table('T', key_dop_names([(0x0201, 'Value_A')]), [('Value_A', 'Row_A', 'Value_A')])
        entries = self.get_entries([self.service('S_A', 'T', 'Row_A')])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['did'], 0x0201)
        self.assertEqual(entries[0]['long_name'], 'Value_A')
        self.assertEqual(entries[0]['long_name_id'], 'ID_Value_A')

    def test_same_row_from_two_services_appears_once(self):
        self.add_decimal_table()
        entries = self.get_entries([self.service('S_C', 'T', 'Row_1'), self.service('S_A', 'T', 'Row_1')])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['services'], ['S_A', 'S_C'])

    def test_duplicate_did_with_different_rows_sorted_by_service_name(self):
        self.add_decimal_table()
        self.add_table('U', key_dop_decimal(), [('258', 'Row_X', 'Row ex')])
        entries = self.get_entries([self.service('S_D', 'T', 'Row_2'), self.service('S_B', 'U', 'Row_X')])
        self.assertEqual([(e['did'], e['services']) for e in entries], [(0x0102, ['S_B']), (0x0102, ['S_D'])])
        self.assertEqual([e['long_name'] for e in entries], ['Row ex', 'Row two'])

    def test_porsche_entries_sorted_by_did(self):
        self.add_decimal_table()
        entries = self.get_entries([self.service('S_A', 'T', 'Row_2'), self.service('S_B', 'T', 'Row_1')])
        self.assertEqual([e['did'] for e in entries], [0x0101, 0x0102])

    def test_row_with_default_value_is_accepted(self):
        self.add_decimal_table()
        self.row('T', 'Row_1')['default_value'] = {'data_type': 'eA_UINT32', 'value': 0}
        entries = self.get_entries([self.service('S_A', 'T', 'Row_1')])
        self.assertEqual(len(entries), 1)

    def test_row_without_dop_gets_error_marker_structure(self):
        self.add_decimal_table()
        self.row('T', 'Row_1')['dop_base_reference'] = None
        entries = self.get_entries([self.service('S_A', 'T', 'Row_1')])
        self.assertEqual(entries[0]['structure'],
                         {'#error': 'Access to database element failed - DOP with name: None'})

    def test_row_of_other_parameter_type_raises(self):
        self.add_decimal_table()
        self.row('T', 'Row_1')['mcd_parameter_type'] = 'eSYSTEM'
        self.row('T', 'Row_1')['system_parameter'] = 'TIMESTAMP'
        with self.assertRaisesRegex(RuntimeError, 'Wrong parameter type for table row parameter'):
            self.get_entries([self.service('S_A', 'T', 'Row_1')])

    def test_row_dop_that_is_no_structure_raises(self):
        self.add_decimal_table()
        self.row('T', 'Row_1')['dop_base_reference'] = ref('DOP u8')
        with self.assertRaisesRegex(RuntimeError, 'Wrong data type for parameter structure: DOP'):
            self.get_entries([self.service('S_A', 'T', 'Row_1')])

    def test_missing_reference_row_raises(self):
        self.add_decimal_table()
        with self.assertRaisesRegex(RuntimeError, 'Table row Row_9 of service S_A not found'):
            self.get_entries([self.service('S_A', 'T', 'Row_9')])

    def test_name_family_key_without_compu_scale_raises(self):
        self.add_table('T', key_dop_names([(0x0201, 'Value_A')]),
                       [('Value_A', 'Row_A', 'Value_A'), ('Value_B', 'Row_B', 'Value_B')])
        with self.assertRaisesRegex(RuntimeError, 'Expected one DID for table key Value_B, found 0'):
            self.get_entries([self.service('S_A', 'T', 'Row_B')])

    def test_name_family_key_with_two_compu_scales_raises(self):
        self.add_table('T', key_dop_names([(0x0201, 'Value_A'), (0x0202, 'Value_A')]),
                       [('Value_A', 'Row_A', 'Value_A')])
        with self.assertRaisesRegex(RuntimeError, 'Expected one DID for table key Value_A, found 2'):
            self.get_entries([self.service('S_A', 'T', 'Row_A')])

    def test_unexpected_key_dop_raises(self):
        self.add_table('T', linear_key_dop(), [('257', 'Row_1', 'Row one')])
        with self.assertRaisesRegex(RuntimeError, 'Unexpected table key DOP: LINEAR A_UINT32 -> A_UINT32'):
            self.get_entries([self.service('S_A', 'T', 'Row_1')])


def coding_table_objects(name, key_dop, rows):
    """Objects of table 'TABLE <name>' with its rows; rows is a list of (map key, row short name)."""
    objects = {(POOL, 'DOP u8'): uint_dop(8), (POOL, 'DOP key ' + name): key_dop}
    key_map = []
    for map_key, short_name in rows:
        row_id = 'ROW {} {}'.format(name, short_name)
        struct_id = 'STRUCT {} {}'.format(name, short_name)
        objects[(POOL, row_id)] = table_row(short_name, map_key, map_key, ref(struct_id))
        objects[(POOL, struct_id)] = structure('Struct_' + short_name,
                                               [value_parameter('Field_1', 0, ref('DOP u8'))], byte_length=1)
        key_map.append((map_key, ref(row_id)))
    objects[(POOL, 'TABLE ' + name)] = table(ref('DOP key ' + name), key_map)
    return objects


def row_write_service(name, table_name, row_short_name):
    """0x2E service whose request addresses one row of a table (or the whole table without row)."""
    return service_objects(name, [sid_parameter(0x2E),
                                  table_key_parameter(ref('TABLE ' + table_name), row_short_name=row_short_name),
                                  table_struct_parameter(ref('TABLE ' + table_name))], [[]])


def row_read_service(name, table_name, row_short_name):
    """0x22 service whose positive response addresses one row of a table."""
    return service_objects(name, [sid_parameter(0x22)],
                           [[sid_parameter(0x62),
                             table_key_parameter(ref('TABLE ' + table_name), row_short_name=row_short_name),
                             table_struct_parameter(ref('TABLE ' + table_name))]])


class RelatedCodingEntriesTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()

    @staticmethod
    def porsche_objects():
        objects = coding_table_objects('C', key_dop_decimal(), [('257', 'Row_1'), ('258', 'Row_2'), ('259', 'Row_3')])
        objects.update(coding_table_objects('U', key_dop_decimal(), [('260', 'Row_X')]))
        objects.update(row_write_service('CodingValue_Write', 'C', 'Row_1'))
        return objects

    @staticmethod
    def related(objects, names):
        variant = layer(name='EV', diag_com_primitive_references=[diag_com(name) for name in names])
        reader = TableEntryReader(FakeObjectLoader(objects), 'project')
        return reader.get_related_coding_entries([], variant)

    def test_rows_addressed_by_other_services_are_added(self):
        objects = self.porsche_objects()
        objects.update(row_read_service('S_M', 'C', 'Row_2'))
        entries = self.related(objects, ['CodingValue_Write', 'S_M'])
        self.assertEqual([(e['did'], e['services']) for e in entries],
                         [(0x0101, ['CodingValue_Write']), (0x0102, ['S_M'])])

    def test_adaptation_services_on_the_coding_table_are_added(self):
        objects = self.porsche_objects()
        objects.update(row_write_service('S_W', 'C', 'Row_3'))
        entries = self.related(objects, ['CodingValue_Write', 'S_W'])
        self.assertEqual([(e['did'], e['services']) for e in entries],
                         [(0x0101, ['CodingValue_Write']), (0x0103, ['S_W'])])

    def test_services_on_other_tables_are_ignored(self):
        objects = self.porsche_objects()
        objects.update(row_read_service('S_M', 'U', 'Row_X'))
        objects.update(row_write_service('S_W', 'U', 'Row_X'))
        entries = self.related(objects, ['CodingValue_Write', 'S_M', 'S_W'])
        self.assertEqual([(e['did'], e['services']) for e in entries], [(0x0101, ['CodingValue_Write'])])

    def test_coding_service_without_row_reference_reads_whole_table_only(self):
        objects = self.porsche_objects()
        objects.update(row_write_service('CodingValue_Write', 'C', None))
        objects.update(row_read_service('S_M', 'C', 'Row_2'))
        entries = self.related(objects, ['CodingValue_Write', 'S_M'])
        self.assertEqual([(e['did'], e['services']) for e in entries],
                         [(0x0101, ['CodingValue_Write']), (0x0102, ['CodingValue_Write']),
                          (0x0103, ['CodingValue_Write'])])

    def test_variant_without_coding_service_gives_none(self):
        objects = self.porsche_objects()
        objects.update(row_read_service('S_M', 'C', 'Row_2'))
        self.assertIsNone(self.related(objects, ['S_M']))

    @staticmethod
    def vw_objects():
        objects = coding_table_objects('N', key_dop_names([(0x0102, 'Coding_B'), (0x0101, 'Coding_A')]),
                                       [('Coding_A', 'Row_A'), ('Coding_B', 'Row_B')])
        objects.update(row_write_service(CODING_SERVICE_NAMES[0], 'N', 'Row_A'))
        objects.update(row_read_service('S_M', 'N', 'Row_B'))
        return objects

    def test_vw_coding_service_reads_whole_table_only(self):
        entries = self.related(self.vw_objects(), [CODING_SERVICE_NAMES[0], 'S_M'])
        # parse_dop changes some parameter objects in place, so the comparison reads fresh objects
        reference_objects = self.vw_objects()
        request = reference_objects[(POOL, 'request ' + CODING_SERVICE_NAMES[0])]
        vw_service = SelectedService(CODING_SERVICE_NAMES[0], request['request_parameters'][1],
                                     request['request_parameters'][2], True)
        expected = TableEntryReader(FakeObjectLoader(reference_objects), 'project').get_entries([], [vw_service])
        self.assertEqual(entries, expected)
        self.assertEqual([e['did'] for e in entries], [0x0102, 0x0101])
        self.assertTrue(all('services' not in e for e in entries))
