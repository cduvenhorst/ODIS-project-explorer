import unittest

from common_utils.layer_chain import load_layer_data
from common_utils.table_entries import (CODING_SERVICE_NAMES, KIND_ADAPTATION, KIND_CODING, KIND_MWB,
                                        VW_ADAPTATION_SERVICE_NAME, VW_MWB_SERVICE_NAME, TableEntryReader)
from tests.script_support import FakeObjectLoader, layer
from tests.table_fixtures import (POOL, diag_com, ref, service_objects, sid_parameter, table_key_parameter,
                                  table_struct_parameter)


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
