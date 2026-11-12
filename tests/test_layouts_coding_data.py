"""Layout tests for the coding data loaders and their embedded objects.

Upstream has no loaders for these types; every body follows the kernel read order.
Where a loader reads an object of any type, MCD_AUDIENCE stands in.
"""
import unittest

from classes.DbStream import DbStream
from common_utils import common_loaders
from tests import support
from tests.support import (NAMED_REFS, ObjectBytes, attributed_ref_body, audience, audience_body,
                           concat, named_refs, named_refs_body, typed, uint, uint_value)
from tests.test_vw_layouts_services import parameter_body


def load(type_name, body):
    return support.load(type_name, body)


# MCD value of data type 255, loads as None
def no_value(body):
    return body.u8(255)


def odx_link_body(id_ref='ID1', doc_ref='DOC1', layer=False):
    return ObjectBytes().ascii(id_ref).ascii(doc_ref).flag(layer)


def odx_link(id_ref='ID1', doc_ref='DOC1', layer=False):
    return {'#OBJECT_TYPE': 'DB_ODX_LINK', 'id_ref': id_ref, 'doc_ref': doc_ref,
            'is_layer_doc_type': layer}


class OdxLinkTests(unittest.TestCase):
    def test_db_odx_link_minimal(self):
        self.assertEqual(load('DB_ODX_LINK', ObjectBytes().ascii(None).ascii(None).flag(False)),
                         {'#OBJECT_TYPE': 'DB_ODX_LINK', 'id_ref': None, 'doc_ref': None,
                          'is_layer_doc_type': False})

    def test_db_odx_link_all_branches(self):
        self.assertEqual(load('DB_ODX_LINK', odx_link_body(layer=True)), odx_link(layer=True))

    def test_db_odx_links_minimal(self):
        self.assertEqual(load('DB_ODX_LINKS', ObjectBytes().u32(0)), [])

    def test_db_odx_links_all_branches(self):
        body = ObjectBytes().u32(2).nested('DB_ODX_LINK', odx_link_body()).absent()
        self.assertEqual(load('DB_ODX_LINKS', body), [odx_link(), None])

    def test_mcd_db_parameter_dop_base_odx_link(self):
        body = parameter_body(reference=True, dop_base=odx_link_body(), dop_base_type='DB_ODX_LINK')
        self.assertEqual(load('MCD_DB_PARAMETER', body)['dop_base'], odx_link())


def item_base_body(sdgs=None, parameter=False, complex_=False):
    body = (ObjectBytes().ascii('DescId').ascii('LongId').ascii('UID')
            .unicode('Description').unicode('Long name').ascii('Item'))
    if sdgs is None:
        body.u8(0)
    else:
        body.u8(1).u16(len(sdgs))
        for object_id in sdgs:
            body.u32(object_id)
    if parameter:
        body.nested('MCD_AUDIENCE', audience_body())
    else:
        body.absent()
    return body.flag(complex_)


def item_base(sdgs=None, parameter=False, complex_=False):
    return {'description_id': 'DescId', 'long_name_id': 'LongId', 'unique_object_id': 'UID',
            'description': 'Description', 'long_name': 'Long name', 'short_name': 'Item',
            # kernel: an absent collection reads as an empty one
            'special_data_group_refs': [] if sdgs is None else [{'object_id': n} for n in sdgs],
            'parameter': audience() if parameter else None, 'is_complex': complex_}


class ConfigurationItemTests(unittest.TestCase):
    def test_mcd_db_configuration_id_item_minimal(self):
        self.assertEqual(load('MCD_DB_CONFIGURATION_ID_ITEM', item_base_body()),
                         typed('MCD_DB_CONFIGURATION_ID_ITEM', item_base()))

    def test_mcd_db_configuration_id_item_all_branches(self):
        self.assertEqual(load('MCD_DB_CONFIGURATION_ID_ITEM', item_base_body([7, 9], True, True)),
                         typed('MCD_DB_CONFIGURATION_ID_ITEM', item_base([7, 9], True, True)))

    def test_mcd_db_data_id_item_minimal(self):
        self.assertEqual(load('MCD_DB_DATA_ID_ITEM', item_base_body()),
                         typed('MCD_DB_DATA_ID_ITEM', item_base()))

    def test_mcd_db_data_id_item_all_branches(self):
        self.assertEqual(load('MCD_DB_DATA_ID_ITEM', item_base_body([7, 9], True, True)),
                         typed('MCD_DB_DATA_ID_ITEM', item_base([7, 9], True, True)))

    def test_mcd_db_system_item_minimal(self):
        body = concat(item_base_body(), ObjectBytes().ascii(None))
        self.assertEqual(load('MCD_DB_SYSTEM_ITEM', body),
                         typed('MCD_DB_SYSTEM_ITEM', {**item_base(), 'system_parameter_name': None}))

    def test_mcd_db_system_item_all_branches(self):
        body = concat(item_base_body([7, 9], True, True), ObjectBytes().ascii('SYSPARAM'))
        self.assertEqual(load('MCD_DB_SYSTEM_ITEM', body),
                         typed('MCD_DB_SYSTEM_ITEM', {**item_base([7, 9], True, True),
                                                      'system_parameter_name': 'SYSPARAM'}))

    def test_mcd_db_system_items_minimal(self):
        self.assertEqual(load('MCD_DB_SYSTEM_ITEMS', ObjectBytes().u16(0)), [])

    def test_mcd_db_system_items_all_branches(self):
        body = ObjectBytes().u16(2).nested('MCD_DB_SYSTEM_ITEM',
                                           concat(item_base_body(), ObjectBytes().ascii('S'))).absent()
        self.assertEqual(load('MCD_DB_SYSTEM_ITEMS', body),
                         [typed('MCD_DB_SYSTEM_ITEM', {**item_base(), 'system_parameter_name': 'S'}),
                          None])


def item_value_body(full=False):
    body = ObjectBytes()
    if full:
        body.nested('MCD_AUDIENCE', audience_body()).u8(1).u16(1).u32(3)
        body.unicode('Desc').ascii('DescId').ascii('KEY').ascii('Meaning').ascii('MeaningId')
        body.unicode('Value').ascii('Rule').u8(1)
        named_refs_body(body, NAMED_REFS)
        return body.u8(1).u16(0)
    body.absent().u8(0).unicode(None).ascii(None).ascii(None).ascii(None).ascii(None)
    return body.unicode(None).ascii(None).u8(0).u8(0)


def item_value(full=False):
    if not full:
        return typed('MCD_DB_ITEM_VALUE', {
            # kernel: an absent collection reads as an empty one
            'audience_state': None, 'special_data_group_refs': [], 'description': None,
            'description_id': None, 'key': None, 'meaning': None, 'meaning_id': None,
            'physical_constant_value': None, 'rule': None,
            'disabled_additional_audiences': [], 'enabled_additional_audiences': []})
    return typed('MCD_DB_ITEM_VALUE', {
        'audience_state': audience(), 'special_data_group_refs': [{'object_id': 3}],
        'description': 'Desc', 'description_id': 'DescId', 'key': 'KEY', 'meaning': 'Meaning',
        'meaning_id': 'MeaningId', 'physical_constant_value': 'Value', 'rule': 'Rule',
        'disabled_additional_audiences': named_refs(NAMED_REFS),
        'enabled_additional_audiences': []})


def option_item_body(full=False):
    if not full:
        return concat(item_base_body(), ObjectBytes().absent().unicode('Default').absent().absent()
                      .u8(0).u8(0).u8(0).u8(0))
    body = concat(item_base_body([7, 9], True, True),
                  ObjectBytes().nested('MCD_DB_ITEM_VALUES',
                                       ObjectBytes().u16(1).nested('MCD_DB_ITEM_VALUE', item_value_body()))
                  .unicode('Default')
                  .nested('MCD_AUDIENCE', audience_body()).nested('MCD_AUDIENCE', audience_body()))
    audiences = ObjectBytes().u8(1)
    named_refs_body(audiences, NAMED_REFS)
    audiences.u8(0).u8(1).u16(0).u8(1)
    named_refs_body(audiences, NAMED_REFS)
    return concat(body, audiences)


def option_item(full=False):
    if not full:
        return typed('MCD_DB_OPTION_ITEM', {
            **item_base(), 'item_values': None, 'physical_default_value': 'Default',
            'read_audience_state': None, 'write_audience_state': None,
            # kernel: an absent collection reads as an empty one
            'disabled_read_additional_audiences': [], 'enabled_read_additional_audiences': [],
            'disabled_write_additional_audiences': [], 'enabled_write_additional_audiences': []})
    return typed('MCD_DB_OPTION_ITEM', {
        **item_base([7, 9], True, True), 'item_values': [item_value()],
        'physical_default_value': 'Default',
        'read_audience_state': audience(), 'write_audience_state': audience(),
        'disabled_read_additional_audiences': named_refs(NAMED_REFS),
        'enabled_read_additional_audiences': [],
        'disabled_write_additional_audiences': [],
        'enabled_write_additional_audiences': named_refs(NAMED_REFS)})


class OptionItemTests(unittest.TestCase):
    def test_mcd_db_item_value_minimal(self):
        self.assertEqual(load('MCD_DB_ITEM_VALUE', item_value_body()), item_value())

    def test_mcd_db_item_value_all_branches(self):
        self.assertEqual(load('MCD_DB_ITEM_VALUE', item_value_body(True)), item_value(True))

    def test_mcd_db_item_values_minimal(self):
        self.assertEqual(load('MCD_DB_ITEM_VALUES', ObjectBytes().u16(0)), [])

    def test_mcd_db_item_values_all_branches(self):
        body = ObjectBytes().u16(2).nested('MCD_DB_ITEM_VALUE', item_value_body()).absent()
        self.assertEqual(load('MCD_DB_ITEM_VALUES', body), [item_value(), None])

    def test_mcd_db_option_item_minimal(self):
        self.assertEqual(load('MCD_DB_OPTION_ITEM', option_item_body()), option_item())

    def test_mcd_db_option_item_all_branches(self):
        self.assertEqual(load('MCD_DB_OPTION_ITEM', option_item_body(True)), option_item(True))

    def test_mcd_db_option_items_minimal(self):
        self.assertEqual(load('MCD_DB_OPTION_ITEMS', ObjectBytes().u16(0)), [])

    def test_mcd_db_option_items_all_branches(self):
        body = ObjectBytes().u16(2).nested('MCD_DB_OPTION_ITEM', option_item_body()).absent()
        self.assertEqual(load('MCD_DB_OPTION_ITEMS', body), [option_item(), None])


def string_map_body(body, entries=()):
    body.u16(len(entries))
    for key, value in entries:
        body.ascii(key).unicode(value)
    return body


def string_map(entries=()):
    return [{'map_key': key, 'value': value} for key, value in entries]


def connector_body(full=False):
    body = ObjectBytes()
    if not full:
        body.flag(False).ascii(None).flag(False).ascii(None).u8(0).u8(0).u32(0).u32(0)
        for _ in range(4):
            body.u16(0)
        return body
    body.flag(True).ascii('W.PATH').flag(False).ascii('R').u8(1).nested('DB_ODX_LINK', odx_link_body(id_ref='R'))
    body.u8(1).nested('DB_ODX_LINK', odx_link_body(id_ref='W')).u32(0x1000).u32(0x8000)
    string_map_body(body, [('K1', 'V1')])
    string_map_body(body, [('K3', 'V4')])
    string_map_body(body, [('K2', 'V2'), ('K2', 'V3')])
    return string_map_body(body, [('K4', 'V5')])


def connector(full=False):
    if not full:
        return typed('DB_DIAG_COM_DATA_CONNECTOR', {
            'write_param_is_short_name_path': False, 'write_param_short_name': None,
            'write_param_short_name_path': None, 'read_param_is_short_name_path': False,
            'read_param_short_name': None, 'read_param_short_name_path': None,
            'read_diag_com_primitive': None, 'write_diag_com_primitive': None,
            'uncompressed_size': 0, 'start_address': 0, 'write_param_value_map': [],
            'write_param_value_sn_path_map': [], 'read_param_value_map': [],
            'read_param_value_sn_path_map': []})
    return typed('DB_DIAG_COM_DATA_CONNECTOR', {
        'write_param_is_short_name_path': True, 'write_param_short_name': None,
        'write_param_short_name_path': 'W.PATH', 'read_param_is_short_name_path': False,
        'read_param_short_name': 'R', 'read_param_short_name_path': None,
        'read_diag_com_primitive': odx_link(id_ref='R'),
        'write_diag_com_primitive': odx_link(id_ref='W'),
        'uncompressed_size': 0x1000, 'start_address': 0x8000,
        'write_param_value_map': string_map([('K1', 'V1')]),
        'write_param_value_sn_path_map': string_map([('K3', 'V4')]),
        'read_param_value_map': string_map([('K2', 'V2'), ('K2', 'V3')]),
        'read_param_value_sn_path_map': string_map([('K4', 'V5')])})


class DataConnectorTests(unittest.TestCase):
    def test_db_diag_com_data_connector_minimal(self):
        self.assertEqual(load('DB_DIAG_COM_DATA_CONNECTOR', connector_body()), connector())

    def test_db_diag_com_data_connector_all_branches(self):
        self.assertEqual(load('DB_DIAG_COM_DATA_CONNECTOR', connector_body(True)), connector(True))

    def test_db_diag_com_data_connector_outer_flag_without_object(self):
        body = ObjectBytes().flag(False).ascii(None).flag(False).ascii(None).u8(1).absent().u8(0)
        body.u32(0).u32(0)
        for _ in range(4):
            body.u16(0)
        self.assertEqual(load('DB_DIAG_COM_DATA_CONNECTOR', body), connector())

    def test_db_diag_com_data_connectors_minimal(self):
        self.assertEqual(load('DB_DIAG_COM_DATA_CONNECTORS', ObjectBytes().u32(0)), [])

    def test_db_diag_com_data_connectors_all_branches(self):
        body = ObjectBytes().u32(2).nested('DB_DIAG_COM_DATA_CONNECTOR', connector_body(True)).absent()
        self.assertEqual(load('DB_DIAG_COM_DATA_CONNECTORS', body), [connector(True), None])


def value_attributed_ref_body(body, strings=(), value=None):
    attributed_ref_body(body, strings)
    return no_value(body) if value is None else uint_value(body, value)


def value_attributed_ref(strings=(), value=None):
    return {'object_id': 'OBJ', 'pool_id': 'POOL', 'strings': list(strings),
            'value': None if value is None else uint(value)}


def coding_data_body(full=False):
    body = ObjectBytes()
    if not full:
        body.ascii(None).unicode(None).unicode(None).ascii(None).ascii(None).ascii(None)
        return body.ascii(None).flag(False)
    body.ascii('Short').unicode('Long').unicode('Desc').ascii('UID').ascii('LongId').ascii('DescId')
    return body.ascii('coding.bin').flag(True)


def coding_data(full=False):
    if not full:
        return typed('MCD_DB_CODING_DATA', {
            'short_name': None, 'long_name': None, 'description': None, 'unique_object_id': None,
            'long_name_id': None, 'description_id': None, 'file_name': None, 'is_late_bound': False})
    return typed('MCD_DB_CODING_DATA', {
        'short_name': 'Short', 'long_name': 'Long', 'description': 'Desc', 'unique_object_id': 'UID',
        'long_name_id': 'LongId', 'description_id': 'DescId', 'file_name': 'coding.bin',
        'is_late_bound': True})


def data_record_body(full=False, has_coding_data=None, coding=None):
    body = ObjectBytes()
    if not full:
        body.ascii(None).ascii(None).ascii(None).unicode(None).unicode(None).ascii(None)
        body.absent().u8(0).u16(0)
        no_value(body).flag(False).absent().u8(0).ascii(None).ascii(None).u32(0).ascii(None)
        return body.u8(0).u8(0)
    body.ascii('DescId').ascii('LongId').ascii('UID').unicode('Desc').unicode('Long').ascii('Rec')
    body.nested('MCD_AUDIENCE', audience_body()).u8(1).u32(2).raw(b'\x01\x02').u16(0x6B01)
    uint_value(body, 42).flag(True if has_coding_data is None else has_coding_data)
    body.nested('MCD_DB_CODING_DATA', coding_data_body(True) if coding is None else coding)
    body.u8(1).u16(1).u32(5).ascii('KEY').ascii('RULE').u32(16).ascii('PARENT').u8(1)
    named_refs_body(body, NAMED_REFS)
    return body.u8(1).u16(0)


def data_record(full=False, **changes):
    if not full:
        return typed('MCD_DB_DATA_RECORD', {
            'description_id': None, 'long_name_id': None, 'unique_object_id': None,
            'description': None, 'long_name': None, 'short_name': None, 'audience_state': None,
            'binary_data': bytearray(), 'data_format': 0, 'data_id': None,
            # kernel: an absent collection reads as an empty one
            'has_coding_data': False, 'coding_data': None, 'special_data_group_refs': [],
            'key': None, 'rule': None, 'configuration_record_value_size': 0,
            'parent_config_data_short_name': None, 'disabled_additional_audiences': [],
            'enabled_additional_audiences': []})
    return typed('MCD_DB_DATA_RECORD', {
        'description_id': 'DescId', 'long_name_id': 'LongId', 'unique_object_id': 'UID',
        'description': 'Desc', 'long_name': 'Long', 'short_name': 'Rec',
        'audience_state': audience(), 'binary_data': b'\x01\x02', 'data_format': 0x6B01,
        'data_id': uint(42), 'has_coding_data': True, 'coding_data': coding_data(True),
        'special_data_group_refs': [{'object_id': 5}], 'key': 'KEY', 'rule': 'RULE',
        'configuration_record_value_size': 16, 'parent_config_data_short_name': 'PARENT',
        'disabled_additional_audiences': named_refs(NAMED_REFS),
        'enabled_additional_audiences': [], **changes})


class DataRecordTests(unittest.TestCase):
    def test_value_attributed_reference_with_uint_value(self):
        body = value_attributed_ref_body(ObjectBytes(), ['A1'], 5)
        stream = DbStream(body.build('MCD_AUDIENCE'), support.string_storage(body.ascii_strings, []))
        stream.loadEnumMediumRange()  # skip the object type
        self.assertEqual(common_loaders.loadDbValueAttributedObjectReference(stream),
                         value_attributed_ref(['A1'], 5))

    def test_mcd_db_coding_data_minimal(self):
        self.assertEqual(load('MCD_DB_CODING_DATA', coding_data_body()), coding_data())

    def test_mcd_db_coding_data_all_branches(self):
        self.assertEqual(load('MCD_DB_CODING_DATA', coding_data_body(True)), coding_data(True))

    def test_mcd_db_data_record_minimal(self):
        self.assertEqual(load('MCD_DB_DATA_RECORD', data_record_body()), data_record())

    def test_mcd_db_data_record_all_branches(self):
        self.assertEqual(load('MCD_DB_DATA_RECORD', data_record_body(True)), data_record(True))

    def test_mcd_db_data_record_coding_data_without_has_flag(self):
        self.assertEqual(load('MCD_DB_DATA_RECORD', data_record_body(True, has_coding_data=False)),
                         data_record(True, has_coding_data=False))


def configuration_record_body(full=False):
    body = ObjectBytes()
    if not full:
        body.ascii(None).ascii(None).ascii(None).unicode(None).unicode(None).ascii(None)
        no_value(body.absent()).flag(False).absent().flag(False).absent().u16(0).u8(0)
        for _ in range(5):
            body.absent()
        body.u32(0).ascii(None).ascii(None)
        return body.u8(0).u8(0).u8(0)
    body.ascii('DescId').ascii('LongId').ascii('UID').unicode('Desc').unicode('Long').ascii('Rec')
    body.nested('MCD_AUDIENCE', audience_body())
    uint_value(body, 7)
    body.flag(True).nested('MCD_DB_CONFIGURATION_ID_ITEM', item_base_body())
    body.flag(True).nested('MCD_DB_DATA_ID_ITEM', item_base_body())
    body.u16(2).ascii('D1')
    value_attributed_ref_body(body, ('A1',), 3)
    body.ascii('D2')
    value_attributed_ref_body(body)
    body.u8(1)
    value_attributed_ref_body(body)
    body.nested('MCD_DB_OPTION_ITEMS',
                ObjectBytes().u16(1).nested('MCD_DB_OPTION_ITEM', option_item_body()))
    body.nested('MCD_DB_SYSTEM_ITEMS', ObjectBytes().u16(0))
    body.nested('DB_ODX_LINKS', ObjectBytes().u32(1).nested('DB_ODX_LINK', odx_link_body()))
    body.nested('DB_ODX_LINKS', ObjectBytes().u32(0))
    body.nested('DB_DIAG_COM_DATA_CONNECTORS',
                ObjectBytes().u32(1).nested('DB_DIAG_COM_DATA_CONNECTOR', connector_body()))
    body.u32(32).ascii('SUBDIR').ascii('PARENT').u8(1).u16(0).u8(1)
    named_refs_body(body, NAMED_REFS)
    return body.u8(1).u16(1).u32(11)


def configuration_record(full=False):
    if not full:
        return typed('MCD_DB_CONFIGURATION_RECORD', {
            'description_id': None, 'long_name_id': None, 'unique_object_id': None,
            'description': None, 'long_name': None, 'short_name': None, 'audience_state': None,
            'configuration_id': None, 'has_configuration_id_item': False,
            'configuration_id_item': None, 'has_data_id_item': False, 'data_id_item': None,
            'data_record_refs': [], 'default_data_record_ref': None, 'option_items': None,
            'system_items': None, 'read_diag_com_primitives': None,
            'write_diag_com_primitives': None, 'diag_com_data_connectors': None,
            'configuration_record_value_size': 0, 'ecu_config_file_sub_dir_name': None,
            # kernel: an absent collection reads as an empty one
            'parent_config_data_short_name': None, 'disabled_additional_audiences': [],
            'enabled_additional_audiences': [], 'special_data_group_refs': []})
    return typed('MCD_DB_CONFIGURATION_RECORD', {
        'description_id': 'DescId', 'long_name_id': 'LongId', 'unique_object_id': 'UID',
        'description': 'Desc', 'long_name': 'Long', 'short_name': 'Rec',
        'audience_state': audience(), 'configuration_id': uint(7),
        'has_configuration_id_item': True,
        'configuration_id_item': typed('MCD_DB_CONFIGURATION_ID_ITEM', item_base()),
        'has_data_id_item': True, 'data_id_item': typed('MCD_DB_DATA_ID_ITEM', item_base()),
        'data_record_refs': [{'name': 'D1', 'reference': value_attributed_ref(('A1',), 3)},
                             {'name': 'D2', 'reference': value_attributed_ref()}],
        'default_data_record_ref': value_attributed_ref(), 'option_items': [option_item()],
        'system_items': [], 'read_diag_com_primitives': [odx_link()],
        'write_diag_com_primitives': [], 'diag_com_data_connectors': [connector()],
        'configuration_record_value_size': 32, 'ecu_config_file_sub_dir_name': 'SUBDIR',
        'parent_config_data_short_name': 'PARENT', 'disabled_additional_audiences': [],
        'enabled_additional_audiences': named_refs(NAMED_REFS),
        'special_data_group_refs': [{'object_id': 11}]})


class ConfigurationRecordTests(unittest.TestCase):
    def test_mcd_db_configuration_record_minimal(self):
        self.assertEqual(load('MCD_DB_CONFIGURATION_RECORD', configuration_record_body()),
                         configuration_record())

    def test_mcd_db_configuration_record_all_branches(self):
        self.assertEqual(load('MCD_DB_CONFIGURATION_RECORD', configuration_record_body(True)),
                         configuration_record(True))


def configuration_data_body(full=False):
    body = ObjectBytes()
    if not full:
        body.ascii(None).ascii(None).ascii(None).unicode(None).unicode(None).ascii(None)
        body.u16(0).u32(0).u8(0)
        return body.u32(0).u32(0).u32(0).flag(False).u8(0)
    body.ascii('DescId').ascii('LongId').ascii('UID').unicode('Desc').unicode('Long').ascii('Data')
    body.u16(1).ascii('R1')
    value_attributed_ref_body(body, ('A1',), 3)
    body.u32(2).ascii('BV1').u8(2).u32(2).ascii('C1').ascii('C2')
    body.ascii('BV2').u8(4).u32(0)
    body.u8(1).u16(1).u32(1)
    body.u32(1).u32(2).u32(3).flag(True)
    return named_refs_body(body.u8(1), NAMED_REFS)


def configuration_data(full=False):
    if not full:
        return typed('MCD_DB_CONFIGURATION_DATA', {
            'description_id': None, 'long_name_id': None, 'unique_object_id': None,
            'description': None, 'long_name': None, 'short_name': None,
            'configuration_record_refs': [], 'base_var_to_case_map': [],
            # kernel: an absent collection reads as an empty one
            'special_data_group_refs': [], 'major': 0, 'minor': 0, 'revision': 0,
            'is_revision_label_available': False, 'additional_audience_refs': []})
    return typed('MCD_DB_CONFIGURATION_DATA', {
        'description_id': 'DescId', 'long_name_id': 'LongId', 'unique_object_id': 'UID',
        'description': 'Desc', 'long_name': 'Long', 'short_name': 'Data',
        'configuration_record_refs': [{'name': 'R1', 'reference': value_attributed_ref(('A1',), 3)}],
        'base_var_to_case_map': [{'map_key': 'BV1', 'unknown_1': 2, 'values': ['C1', 'C2']},
                                 {'map_key': 'BV2', 'unknown_1': 4, 'values': []}],
        'special_data_group_refs': [{'object_id': 1}], 'major': 1, 'minor': 2, 'revision': 3,
        'is_revision_label_available': True,
        'additional_audience_refs': named_refs(NAMED_REFS)})


def config_info_map_body(body, entries, with_value=False):
    body.u32(len(entries))
    for key, items in entries:
        body.ascii(key).u32(len(items))
        for item in items:
            body.ascii(item[0]).ascii(item[1])
            if with_value:
                if item[2] is None:
                    no_value(body)
                else:
                    uint_value(body, item[2])
    return body


def config_info_map(entries, with_value=False):
    result = []
    for key, items in entries:
        elements = []
        for item in items:
            element = {'object_id': item[0], 'unknown_1': item[1]}
            if with_value:
                element['value'] = None if item[2] is None else uint(item[2])
            elements.append(element)
        result.append({'map_key': key, 'items': elements})
    return result


FULL_CONFIG_INFO = (
    [('BASE', [('CD1', 'N1')])], [], [('VAR', [])],
    [('CD1', [('CR1', 'N2', 9), ('CR2', None, None)])])


def config_info_body(maps=None):
    body = ObjectBytes()
    for index in range(4):
        config_info_map_body(body, maps[index] if maps else [], index == 3)
    return body


def config_info(maps=None):
    fields = {}
    for index in range(4):
        fields[f'unknown_{index + 1}'] = config_info_map(maps[index] if maps else [], index == 3)
    return typed('DB_ECU_CONFIG_INFO', fields)


class ConfigurationDataTests(unittest.TestCase):
    def test_mcd_db_configuration_data_minimal(self):
        self.assertEqual(load('MCD_DB_CONFIGURATION_DATA', configuration_data_body()),
                         configuration_data())

    def test_mcd_db_configuration_data_all_branches(self):
        self.assertEqual(load('MCD_DB_CONFIGURATION_DATA', configuration_data_body(True)),
                         configuration_data(True))

    def test_mcd_db_configuration_data_case_map_is_numeric_below_0012(self):
        body = ObjectBytes().ascii(None).ascii(None).ascii(None).unicode(None).unicode(None).ascii(None)
        body.u16(0).u32(1).u32(5).u8(2).u32(2).u32(6).u32(7)
        body.u8(0).u32(0).u32(0).u32(0).flag(False).u8(0)
        loaded = support.load('MCD_DB_CONFIGURATION_DATA', body, database_version='0011')
        self.assertEqual(loaded['base_var_to_case_map'],
                         [{'map_key': 5, 'unknown_1': 2, 'values': [6, 7]}])

    def test_mcd_db_configuration_data_case_map_is_string_from_0012(self):
        body = ObjectBytes().ascii(None).ascii(None).ascii(None).unicode(None).unicode(None).ascii(None)
        body.u16(0).u32(1).ascii('K').u8(2).u32(1).ascii('V')
        body.u8(0).u32(0).u32(0).u32(0).flag(False).u8(0)
        for version in (None, '0012'):
            loaded = support.load('MCD_DB_CONFIGURATION_DATA', body, database_version=version)
            self.assertEqual(loaded['base_var_to_case_map'],
                             [{'map_key': 'K', 'unknown_1': 2, 'values': ['V']}])

    def test_db_ecu_config_info_minimal(self):
        self.assertEqual(load('DB_ECU_CONFIG_INFO', config_info_body()), config_info())

    def test_db_ecu_config_info_all_branches(self):
        self.assertEqual(load('DB_ECU_CONFIG_INFO', config_info_body(FULL_CONFIG_INFO)),
                         config_info(FULL_CONFIG_INFO))

    def test_db_ecu_config_info_duplicate_keys_are_kept(self):
        maps = ([], [], [('VAR', [('X1', 'A')]), ('VAR', [('X2', 'B')])], [])
        loaded = load('DB_ECU_CONFIG_INFO', config_info_body(maps))
        self.assertEqual(loaded, config_info(maps))
        self.assertEqual([entry['items'][0]['object_id'] for entry in loaded['unknown_3']],
                         ['X1', 'X2'])
