import os
import tempfile
import unittest

from common_utils.coding_layout import NO_POSITION_NOTE
from common_utils.config_records import ConfigDataIndex, ConfigRecordSource, build_config_entries, project_pool_ids
from common_utils.layer_chain import load_layer_data
from common_utils.odx_link import OdxLinkResolver
from tests.script_support import FakeObjectLoader, layer
from tests.table_fixtures import texttable_dop, uint_dop


def config_data(short_name, *case_map):
    return {'short_name': short_name,
            'base_variant_to_case_map': [{'map_key': key, 'unknown_1': 4, 'values': values}
                                         for key, values in case_map]}


def config_info():
    return {'unknown_1': [],
            'unknown_2': [{'map_key': 'BV', 'items': [{'object_id': 'CD_B', 'name': 'CD_B'},
                                                      {'object_id': 'CD_A', 'name': 'CD_A'}]}],
            'unknown_3': [{'map_key': 'EV1', 'items': [{'object_id': 'CD_V', 'name': 'CD_V'},
                                                       {'object_id': 'CD_A', 'name': 'CD_A'}]}],
            'unknown_4': []}


def objects(extra=None):
    result = {('E.ec', 'DbEcuConfigInfo'): config_info(),
              ('E.ec', 'CD_B'): config_data('CD_B', ('BV', [])),
              ('E.ec', 'CD_A'): config_data('CD_A', ('BV', [])),
              ('E.ec', 'CD_V'): config_data('CD_V', ('BV', ['EV1']))}
    result.update(extra or {})
    return result


def short_names(config_data_objects):
    return [item['short_name'] for item in config_data_objects]


class ConfigDataIndexTests(unittest.TestCase):
    def index(self, extra=None, pool_ids=('E.ec',)):
        return ConfigDataIndex(FakeObjectLoader(objects(extra)), 'project', list(pool_ids))

    def test_variant_gets_base_level_then_own(self):
        self.assertEqual(['CD_A', 'CD_B', 'CD_V'], short_names(self.index().for_variant('BV', 'EV1')))

    def test_base_variant_gets_base_level_only(self):
        self.assertEqual(['CD_A', 'CD_B'], short_names(self.index().for_variant('BV', 'BV')))

    def test_other_variant_gets_base_level_only(self):
        self.assertEqual(['CD_A', 'CD_B'], short_names(self.index().for_variant('BV', 'EV2')))

    def test_other_base_variant_gets_nothing(self):
        self.assertEqual([], self.index().for_variant('BX', 'BX'))

    def test_numeric_case_map_is_skipped_and_flagged(self):
        info = config_info()
        info['unknown_1'] = [{'map_key': 'BV', 'items': [{'object_id': 'CD_N', 'name': 'CD_N'}]}]
        index = self.index({('E.ec', 'DbEcuConfigInfo'): info,
                            ('E.ec', 'CD_N'): config_data('CD_N', (7, []))})
        self.assertTrue(index.has_numeric_case_maps)
        for variant in ('BV', 'EV1', 'EV2'):
            self.assertNotIn('CD_N', short_names(index.for_variant('BV', variant)))
        self.assertFalse(self.index().has_numeric_case_maps)

    def test_pool_without_config_info_is_skipped(self):
        index = self.index({('F.ec', 'Other'): {}}, pool_ids=('E.ec', 'F.ec'))
        self.assertEqual(['CD_A', 'CD_B', 'CD_V'], short_names(index.for_variant('BV', 'EV1')))

    def test_duplicate_listing_loads_once(self):
        found = short_names(self.index().for_variant('BV', 'EV1'))
        self.assertEqual(1, found.count('CD_A'))

    def test_config_data_missing_from_unknown_4_is_listed(self):
        self.assertEqual([], config_info()['unknown_4'])
        self.assertEqual(3, len(self.index().for_variant('BV', 'EV1')))

    def test_config_data_only_in_unknown_4_is_not_listed(self):
        info = config_info()
        info['unknown_4'] = [{'map_key': 'BV', 'items': [{'object_id': 'CD_X', 'name': 'CD_X'}]}]
        index = self.index({('E.ec', 'DbEcuConfigInfo'): info, ('E.ec', 'CD_X'): config_data('CD_X', ('BV', []))})
        self.assertNotIn('CD_X', short_names(index.for_variant('BV', 'EV1')))
        self.assertEqual(['CD_A', 'CD_B', 'CD_V'], short_names(index.for_variant('BV', 'EV1')))

    def test_project_pool_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('B.bv.key', 'A.ec.key', 'A.ec.db'):
                open(os.path.join(folder, name), 'w').close()
            self.assertEqual(['A.ec', 'B.bv'], project_pool_ids(folder))

    def test_project_pool_ids_of_missing_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual([], project_pool_ids(os.path.join(folder, 'missing')))


def odx_link(id_reference='DOP__L_16', document_reference='DLC_L'):
    return {'#OBJECT_TYPE': 'DB_ODX_LINK', 'id_reference': id_reference,
            'document_reference': document_reference, 'is_layer_document_type': False}


def simple_parameter(dop_base=None, dop_base_reference=None, byte_position=0, bit_position=0,
                     is_byte_position_available=True, mcd_parameter_type='eVALUE'):
    return {'#OBJECT_TYPE': 'MCD_DB_PARAMETER', 'short_name': 'P', 'long_name': 'P', 'long_name_id': 'ID_P',
            'description': None, 'description_id': None, 'default_value': None,
            'is_byte_position_available': is_byte_position_available, 'byte_position': byte_position,
            'bit_position': bit_position, 'mcd_parameter_type': mcd_parameter_type,
            'dop_base_reference': dop_base_reference, 'dop_base': dop_base}


def pool_parameter(**fields):
    return simple_parameter(dop_base_reference={'pool_id': 'E.ec', 'object_id': 'DOP u8'}, **fields)


def item(long_name, parameter, **fields):
    result = {'short_name': long_name, 'long_name': long_name, 'long_name_id': 'ID_' + long_name,
              'parameter': parameter}
    result.update(fields)
    return result


def option_item(long_name, parameter, default='on', item_values=()):
    return item(long_name, parameter, physical_default_value=default, item_values=list(item_values))


def item_value(physical='0'):
    return {'physical_constant_value': physical, 'key': None, 'meaning': None, 'meaning_id': None}


def link_option(long_name='Switch'):
    return option_item(long_name, simple_parameter(dop_base=odx_link()), item_values=[item_value()])


def pool_option(long_name='Level'):
    return option_item(long_name, pool_parameter(), default='7')


def connector():
    return {'read_diag_com_primitive': None, 'write_diag_com_primitive': odx_link('GenericWriteId'),
            'uncompressed_size': 4, 'read_parameter_value_map': [],
            'write_parameter_value_map': [{'map_key': 'RecordDataIdentifier', 'value': '256'}]}


def config_record(option_items=(), **fields):
    result = {'short_name': 'CR', 'long_name': 'Record', 'long_name_id': 'ID_CR',
              'configuration_id_item': None, 'data_id_item': None,
              'option_items': list(option_items) if option_items is not None else None, 'system_items': [],
              'read_diag_com_primitives': [odx_link('GenericRead')],
              'write_diag_com_primitives': [odx_link('GenericWrite')],
              'diag_com_data_connectors': [connector()],
              'configuration_record_value_size': 4, 'data_record_references': []}
    result.update(fields)
    return result


def entry_objects(record):
    return {('L.bv', '#RtGen_DB_LAYER_DATA'): layer(layer_name='L', dop_references=[
                {'map_key': 'DOP_Short', 'reference': {'pool_id': 'L.bv', 'object_id': 'DOP_L__L_16'}}]),
            ('L.bv', 'DOP_L__L_16'): texttable_dop([(0, 'off'), (1, 'on')], 1),
            ('E.ec', 'DOP u8'): uint_dop(8),
            ('E.ec', 'CR'): record}


def entry_config_data(short_name='CD'):
    return {'short_name': short_name, 'long_name': 'Data', 'long_name_id': 'ID_CD',
            'configuration_record_references': [
                {'map_key': 'CR', 'reference': {'pool_id': 'E.ec', 'object_id': 'CR'}}]}


class ConfigEntriesTests(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()

    def build(self, record, dop_u8=None):
        objects_by_key = entry_objects(record)
        if dop_u8 is not None:
            objects_by_key[('E.ec', 'DOP u8')] = dop_u8
        loader = FakeObjectLoader(objects_by_key)
        resolver = OdxLinkResolver(loader, 'project', ['E.ec', 'L.bv'])
        return build_config_entries(loader, 'project', resolver, [entry_config_data()])

    def fields(self, *option_items):
        return self.build(config_record(option_items))[0]['records'][0]['fields']

    def test_option_item_with_odx_link(self):
        field = self.fields(link_option(), pool_option())[0]
        self.assertEqual([0, 1], [value['lower_limit'] for value in field['values']])
        self.assertEqual(['off', 'on'], [value['text'] for value in field['values']])
        self.assertEqual('on', field['default'])
        self.assertEqual('option', field['item_kind'])
        self.assertIsNone(field['note'])
        self.assertEqual(1, field['bit_length'])
        self.assertEqual('VALUE', field['parameter_type'])
        self.assertEqual([{'physical_value': '0', 'key': None, 'meaning': None, 'meaning_id': None}],
                         field['item_values'])
        self.assertNotIn('_standard_length', field)

    def test_option_item_with_pool_reference(self):
        field = self.fields(link_option(), pool_option())[1]
        self.assertEqual(8, field['bit_length'])
        self.assertEqual([], field['values'])
        self.assertIsNone(field['note'])

    def test_record_header(self):
        header = self.build(config_record())[0]
        self.assertEqual(['CD', 'Data', 'ID_CD'], [header[key] for key in ('short_name', 'long_name', 'long_name_id')])
        record = header['records'][0]
        self.assertEqual(4, record['byte_length'])
        self.assertEqual(['GenericRead'], record['read_services'])
        self.assertEqual(['GenericWrite'], record['write_services'])
        self.assertEqual({'RecordDataIdentifier': '256'}, record['connectors'][0]['write_parameter_values'])
        self.assertEqual({}, record['connectors'][0]['read_parameter_values'])
        self.assertIsNone(record['connectors'][0]['read_service'])
        self.assertEqual('GenericWriteId', record['connectors'][0]['write_service'])
        self.assertEqual(4, record['connectors'][0]['size'])
        self.assertEqual([], record['data_records'])

    def test_unresolved_link_becomes_note(self):
        parameter = simple_parameter(dop_base=odx_link(document_reference='DLC_M'))
        field = self.fields(option_item('X', parameter))[0]
        self.assertEqual('ODX link layer not found: M', field['note'])
        self.assertEqual([], field['values'])

    def test_reference_without_pool_becomes_note(self):
        parameter = simple_parameter(dop_base_reference={'pool_id': None, 'object_id': 'DOP u8'})
        self.assertEqual('DOP reference without pool: DOP u8', self.fields(option_item('X', parameter))[0]['note'])

    def test_missing_reference_becomes_note(self):
        parameter = simple_parameter(dop_base_reference={'pool_id': 'E.ec', 'object_id': 'Missing'})
        self.assertEqual('DOP reference not found: E.ec/Missing', self.fields(option_item('X', parameter))[0]['note'])

    def test_parameter_without_dop_becomes_note(self):
        self.assertEqual('Parameter has no DOP', self.fields(option_item('X', simple_parameter()))[0]['note'])

    def test_item_without_parameter_becomes_note(self):
        field = self.fields(option_item('X', None))[0]
        self.assertEqual('Item has no parameter', field['note'])
        self.assertIsNone(field['byte_position'])
        self.assertIsNone(field['bit_position'])

    def test_dop_parse_error_becomes_note(self):
        dop = uint_dop(8)
        dop['diag_coded_type']['coded_type'] = 'eBOGUS'
        field = self.build(config_record([pool_option()]), dop_u8=dop)[0]['records'][0]['fields'][0]
        self.assertEqual('DOP could not be parsed: Unknown DIAG-CODED-TYPE type: eBOGUS', field['note'])

    def test_system_and_identifier_items(self):
        record = config_record(configuration_id_item=item('Cfg', pool_parameter()),
                               data_id_item=item('Dat', pool_parameter()),
                               system_items=[item('Sys', pool_parameter(), system_parameter_name='DATE')])
        fields = self.build(record)[0]['records'][0]['fields']
        self.assertEqual(['configuration_id', 'data_id', 'system'], [field['item_kind'] for field in fields])
        self.assertEqual([None, None, 'DATE'], [field['system_parameter_name'] for field in fields])
        self.assertEqual([None, None, None], [field['default'] for field in fields])

    def test_data_record_names(self):
        record = config_record(data_record_references=[{'name': 'LateBound', 'reference': {'pool_id': None}}])
        entry = self.build(record)[0]['records'][0]
        self.assertEqual([], entry['fields'])
        self.assertEqual(['LateBound'], entry['data_records'])

    def test_item_without_byte_position(self):
        field = self.fields(option_item('X', pool_parameter(is_byte_position_available=False)))[0]
        self.assertIsNone(field['byte_position'])
        self.assertEqual(NO_POSITION_NOTE, field['note'])

    def test_none_collections_read_as_empty(self):
        record = config_record(option_items=None, system_items=None, read_diag_com_primitives=None,
                               write_diag_com_primitives=None, diag_com_data_connectors=None)
        entry = self.build(record)[0]['records'][0]
        self.assertEqual([[], [], [], []], [entry['fields'], entry['read_services'], entry['write_services'],
                                            entry['connectors']])

    def test_none_elements_of_collections_are_skipped(self):
        record = config_record([None, link_option(), None], system_items=[None],
                               read_diag_com_primitives=[None, odx_link('GenericRead')],
                               write_diag_com_primitives=[None],
                               diag_com_data_connectors=[None, connector()],
                               data_record_references=[None, {'name': 'Named', 'reference': {'pool_id': None}}])
        record['configuration_id_item'] = None
        entry = self.build(record)[0]['records'][0]
        self.assertEqual(['Switch'], [field['long_name'] for field in entry['fields']])
        self.assertEqual(['GenericRead'], entry['read_services'])
        self.assertEqual([], entry['write_services'])
        self.assertEqual(1, len(entry['connectors']))
        self.assertEqual(['Named'], entry['data_records'])

    def test_none_option_item_values_are_skipped(self):
        field = self.fields(option_item('X', pool_parameter(), item_values=[None, item_value()]))[0]
        self.assertEqual(1, len(field['item_values']))

    def test_none_record_reference_is_skipped(self):
        loader = FakeObjectLoader(entry_objects(config_record([link_option()])))
        resolver = OdxLinkResolver(loader, 'project', ['E.ec', 'L.bv'])
        data = entry_config_data()
        data['configuration_record_references'].insert(0, None)
        entries = build_config_entries(loader, 'project', resolver, [data])
        self.assertEqual(1, len(entries[0]['records']))

    def test_integer_parameter_type_passes_through(self):
        field = self.fields(option_item('X', pool_parameter(mcd_parameter_type=3)))[0]
        self.assertEqual(3, field['parameter_type'])

    def source(self):
        objects_by_key = entry_objects(config_record([link_option()]))
        objects_by_key[('E.ec', 'DbEcuConfigInfo')] = {
            'unknown_1': [], 'unknown_3': [], 'unknown_4': [],
            'unknown_2': [{'map_key': 'BV', 'items': [{'object_id': 'CD', 'name': 'CD'}]}]}
        objects_by_key[('E.ec', 'CD')] = dict(entry_config_data(),
                                              base_variant_to_case_map=[{'map_key': 'BV', 'values': []}])
        loader = FakeObjectLoader(objects_by_key)
        return loader, ConfigRecordSource(loader, 'project', pool_ids=['E.ec', 'L.bv'])

    def test_base_level_entry_is_built_once_across_variants(self):
        loader, source = self.source()
        first = source.entries_for_variant('BV', 'EV1')
        calls = loader.load_calls
        second = source.entries_for_variant('BV', 'EV2')
        self.assertEqual(calls, loader.load_calls)
        self.assertEqual(first, second)

    def test_source_builds_entries_for_variant(self):
        _, source = self.source()
        entries = source.entries_for_variant('BV', 'EV1')
        self.assertEqual(['CD'], [entry['short_name'] for entry in entries])
        self.assertEqual('Switch', entries[0]['records'][0]['fields'][0]['long_name'])
        self.assertFalse(source.has_numeric_case_maps)


if __name__ == '__main__':
    unittest.main()
