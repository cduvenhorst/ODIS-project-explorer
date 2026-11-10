"""Layout tests for the coding data loaders and their embedded objects.

Upstream has no loaders for these types; every body follows the kernel read order.
Where a loader reads an object of any type, MCD_AUDIENCE stands in.
"""
import unittest

from tests import support
from tests.support import ObjectBytes, audience, audience_body, concat, typed
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
