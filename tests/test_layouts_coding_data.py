"""Layout tests for the coding data loaders and their embedded objects.

Upstream has no loaders for these types; every body follows the kernel read order.
Where a loader reads an object of any type, MCD_AUDIENCE stands in.
"""
import unittest

from tests import support
from tests.support import (NAMED_REFS, ObjectBytes, audience, audience_body, concat, named_refs,
                           named_refs_body, typed)
from tests.test_vw_layouts_services import parameter_body


def load(type_name, body):
    return support.load(type_name, body)


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
            'special_data_group_refs': None if sdgs is None else [{'object_id': n} for n in sdgs],
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
            'audience_state': None, 'special_data_group_refs': None, 'description': None,
            'description_id': None, 'key': None, 'meaning': None, 'meaning_id': None,
            'physical_constant_value': None, 'rule': None,
            'disabled_additional_audiences': None, 'enabled_additional_audiences': None})
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
            'disabled_read_additional_audiences': None, 'enabled_read_additional_audiences': None,
            'disabled_write_additional_audiences': None, 'enabled_write_additional_audiences': None})
    return typed('MCD_DB_OPTION_ITEM', {
        **item_base([7, 9], True, True), 'item_values': [item_value()],
        'physical_default_value': 'Default',
        'read_audience_state': audience(), 'write_audience_state': audience(),
        'disabled_read_additional_audiences': named_refs(NAMED_REFS),
        'enabled_read_additional_audiences': None,
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
    body.flag(True).ascii('W.PATH').flag(False).ascii('R').u8(1).nested('DB_ODX_LINK', odx_link_body())
    body.u8(1).nested('DB_ODX_LINK', odx_link_body()).u32(0x1000).u32(0x8000)
    string_map_body(body, [('K1', 'V1')])
    string_map_body(body)
    string_map_body(body, [('K2', 'V2'), ('K2', 'V3')])
    return string_map_body(body)


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
        'read_diag_com_primitive': odx_link(), 'write_diag_com_primitive': odx_link(),
        'uncompressed_size': 0x1000, 'start_address': 0x8000,
        'write_param_value_map': string_map([('K1', 'V1')]), 'write_param_value_sn_path_map': [],
        'read_param_value_map': string_map([('K2', 'V2'), ('K2', 'V3')]),
        'read_param_value_sn_path_map': []})


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
