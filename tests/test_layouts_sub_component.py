"""Layout tests for the sub component loaders and their embedded objects.

Upstream has no loaders for these types; every body follows the kernel read order.
"""
import unittest

from tests import support
from tests.support import ObjectBytes, attributed_ref, attributed_ref_body, ref, ref_body, typed
from tests.test_layouts_coding_data import odx_link as odx_link_expected
from tests.test_layouts_coding_data import odx_link_body


def load(type_name, body):
    return support.load(type_name, body)


def name_block_body(body, short_name):
    """The six standard name fields in stream order."""
    return (body.ascii(short_name).unicode(short_name + ' long').unicode(short_name + ' desc')
            .ascii(short_name + '_UID').ascii(short_name + '_LID').ascii(short_name + '_DID'))


def name_block(short_name):
    return {'short_name': short_name, 'long_name': short_name + ' long',
            'description': short_name + ' desc', 'unique_object_id': short_name + '_UID',
            'long_name_id': short_name + '_LID', 'description_id': short_name + '_DID'}


def dtc_connector_body(odx_link=False):
    body = ObjectBytes()
    if odx_link:
        body.u8(1).nested('DB_ODX_LINK', odx_link_body())
    else:
        body.u8(0)
        ref_body(body, 'DOP1', 'POOL1')
    return name_block_body(body.ascii('DTC1'), 'C1')


def dtc_connector(odx_link=False):
    return typed('MCD_DB_DIAG_TROUBLE_CODE_CONNECTOR', {
        'dtc_dop_is_odx_link': odx_link,
        'dtc_dop_ref': None if odx_link else ref('DOP1', 'POOL1'),
        'dtc_dop_odx_link': odx_link_expected() if odx_link else None,
        'diag_trouble_code': 'DTC1', **name_block('C1')})


def env_connector_body(odx_link=False):
    body = ObjectBytes()
    if odx_link:
        body.u8(1).nested('DB_ODX_LINK', odx_link_body())
    else:
        body.u8(0)
        ref_body(body, 'DOP1', 'POOL1')
    return name_block_body(body.ascii('ENV1'), 'E1')


def env_connector(odx_link=False):
    return typed('MCD_DB_ENV_DATA_CONNECTOR', {
        'env_data_desc_dop_is_odx_link': odx_link,
        'env_data_desc_dop_ref': None if odx_link else ref('DOP1', 'POOL1'),
        'env_data_desc_dop_odx_link': odx_link_expected() if odx_link else None,
        'env_data': 'ENV1', **name_block('E1')})


def table_row_connector_body(odx_link=False, strings=()):
    body = ObjectBytes()
    if odx_link:
        body.u8(1).nested('DB_ODX_LINK', odx_link_body())
    else:
        body.u8(0)
        attributed_ref_body(body, strings)
    return name_block_body(body.ascii('TAB1'), 'T1')


def table_row_connector(odx_link=False, strings=()):
    return typed('MCD_DB_TABLE_ROW_CONNECTOR', {
        'table_is_odx_link': odx_link,
        'table_ref': None if odx_link else attributed_ref(strings),
        'table_odx_link': odx_link_expected() if odx_link else None,
        'table_row': 'TAB1', **name_block('T1')})


def param_connector_body(in_params=(('IN1', 0),), out_params=(('OUT1', 1), ('OUT2', 0))):
    body = ObjectBytes().ascii('DCP1')
    for params in (in_params, out_params):
        body.u16(len(params))
        for name, is_name in params:
            body.ascii(name).u8(is_name)
    return name_block_body(body, 'P1')


def param_connector(in_params=(('IN1', False),), out_params=(('OUT1', True), ('OUT2', False))):
    def entries(params):
        return [{'name': name, 'is_name': is_name} for name, is_name in params]
    return typed('MCD_DB_SUB_COMPONENT_PARAM_CONNECTOR', {
        'diag_com_primitive_name': 'DCP1', 'sub_component_in_param_names': entries(in_params),
        'sub_component_out_param_names': entries(out_params), **name_block('P1')})


class ConnectorTests(unittest.TestCase):
    def test_mcd_db_diag_trouble_code_connector_minimal(self):
        body = ObjectBytes().u8(0)
        ref_body(body, 'DOP1', 'POOL1').ascii('DTC1')
        name_block_body(body, 'C1')
        self.assertEqual(load('MCD_DB_DIAG_TROUBLE_CODE_CONNECTOR', body), dtc_connector())

    def test_mcd_db_diag_trouble_code_connector_all_branches(self):
        self.assertEqual(load('MCD_DB_DIAG_TROUBLE_CODE_CONNECTOR', dtc_connector_body(True)),
                         dtc_connector(True))

    def test_connector_odx_link_switch_two_reads_odx_link(self):
        body = ObjectBytes().u8(2).nested('DB_ODX_LINK', odx_link_body()).ascii('DTC1')
        name_block_body(body, 'C1')
        self.assertEqual(load('MCD_DB_DIAG_TROUBLE_CODE_CONNECTOR', body), dtc_connector(True))

    def test_connector_odx_link_switch_with_absent_link(self):
        body = ObjectBytes().u8(1).absent().ascii('DTC1')
        name_block_body(body, 'C1')
        expected = dtc_connector(True)
        expected['dtc_dop_odx_link'] = None
        self.assertEqual(load('MCD_DB_DIAG_TROUBLE_CODE_CONNECTOR', body), expected)

    def test_mcd_db_env_data_connector_minimal(self):
        self.assertEqual(load('MCD_DB_ENV_DATA_CONNECTOR', env_connector_body()), env_connector())

    def test_mcd_db_env_data_connector_all_branches(self):
        self.assertEqual(load('MCD_DB_ENV_DATA_CONNECTOR', env_connector_body(True)),
                         env_connector(True))

    def test_mcd_db_table_row_connector_minimal(self):
        self.assertEqual(load('MCD_DB_TABLE_ROW_CONNECTOR', table_row_connector_body()),
                         table_row_connector())

    def test_mcd_db_table_row_connector_all_branches(self):
        self.assertEqual(load('MCD_DB_TABLE_ROW_CONNECTOR', table_row_connector_body(True)),
                         table_row_connector(True))
        self.assertEqual(load('MCD_DB_TABLE_ROW_CONNECTOR',
                              table_row_connector_body(strings=('A1', 'A2'))),
                         table_row_connector(strings=('A1', 'A2')))

    def test_table_row_connector_unknown_pool_key_gives_none(self):
        # The pool id is a key that is not in the string pool.
        body = ObjectBytes().u8(0).ascii('OBJ').u32(0x12345678).u8(0).ascii('TAB1')
        name_block_body(body, 'T1')
        result = load('MCD_DB_TABLE_ROW_CONNECTOR', body)
        self.assertEqual(result['table_ref']['object_id'], 'OBJ')
        self.assertIsNone(result['table_ref']['pool_id'])
        self.assertEqual(result['table_row'], 'TAB1')

    def test_mcd_db_sub_component_param_connector_minimal(self):
        body = ObjectBytes().ascii('DCP1').u16(0).u16(0)
        name_block_body(body, 'P1')
        self.assertEqual(load('MCD_DB_SUB_COMPONENT_PARAM_CONNECTOR', body),
                         param_connector(in_params=(), out_params=()))

    def test_mcd_db_sub_component_param_connector_all_branches(self):
        self.assertEqual(load('MCD_DB_SUB_COMPONENT_PARAM_CONNECTOR', param_connector_body()),
                         param_connector())

    def test_param_connector_keeps_duplicate_names(self):
        body = param_connector_body(out_params=(('OUT1', 1), ('OUT1', 1)))
        self.assertEqual(load('MCD_DB_SUB_COMPONENT_PARAM_CONNECTOR', body),
                         param_connector(out_params=(('OUT1', True), ('OUT1', True))))


class ConnectorCollectionTests(unittest.TestCase):
    def test_mcd_db_diag_trouble_code_connectors_minimal(self):
        self.assertEqual(load('MCD_DB_DIAG_TROUBLE_CODE_CONNECTORS', ObjectBytes().u32(0)), [])

    def test_mcd_db_diag_trouble_code_connectors_all_branches(self):
        body = ObjectBytes().u32(2).nested('MCD_DB_DIAG_TROUBLE_CODE_CONNECTOR',
                                           dtc_connector_body()).absent()
        self.assertEqual(load('MCD_DB_DIAG_TROUBLE_CODE_CONNECTORS', body), [dtc_connector(), None])

    def test_mcd_db_env_data_connectors_minimal(self):
        self.assertEqual(load('MCD_DB_ENV_DATA_CONNECTORS', ObjectBytes().u32(0)), [])

    def test_mcd_db_env_data_connectors_all_branches(self):
        body = ObjectBytes().u32(2).nested('MCD_DB_ENV_DATA_CONNECTOR', env_connector_body()).absent()
        self.assertEqual(load('MCD_DB_ENV_DATA_CONNECTORS', body), [env_connector(), None])

    def test_mcd_db_table_row_connectors_minimal(self):
        self.assertEqual(load('MCD_DB_TABLE_ROW_CONNECTORS', ObjectBytes().u32(0)), [])

    def test_mcd_db_table_row_connectors_all_branches(self):
        body = ObjectBytes().u32(2).nested('MCD_DB_TABLE_ROW_CONNECTOR',
                                           table_row_connector_body()).absent()
        self.assertEqual(load('MCD_DB_TABLE_ROW_CONNECTORS', body), [table_row_connector(), None])

    def test_mcd_db_sub_component_param_connectors_minimal(self):
        self.assertEqual(load('MCD_DB_SUB_COMPONENT_PARAM_CONNECTORS', ObjectBytes().u32(0)), [])

    def test_mcd_db_sub_component_param_connectors_all_branches(self):
        body = ObjectBytes().u32(2).nested('MCD_DB_SUB_COMPONENT_PARAM_CONNECTOR',
                                           param_connector_body()).absent()
        self.assertEqual(load('MCD_DB_SUB_COMPONENT_PARAM_CONNECTORS', body),
                         [param_connector(), None])


def sub_component_names_body(body):
    """The six name fields in the reversed stream order, each with a distinct value."""
    return (body.ascii('SC_DID').ascii('SC_LID').ascii('SC_UID')
            .unicode('SC desc').unicode('SC long').ascii('SC1'))


SUB_COMPONENT_NAMES = {
    'description_id': 'SC_DID', 'long_name_id': 'SC_LID', 'unique_object_id': 'SC_UID',
    'description': 'SC desc', 'long_name': 'SC long', 'short_name': 'SC1'}


class SubComponentTests(unittest.TestCase):
    def test_mcd_db_sub_component_minimal(self):
        body = ObjectBytes().ascii(None).ascii(None).ascii(None).unicode(None).unicode(None).ascii('SC1')
        for type_name in ('MCD_DB_DIAG_TROUBLE_CODE_CONNECTORS', 'MCD_DB_ENV_DATA_CONNECTORS',
                          'MCD_DB_SUB_COMPONENT_PARAM_CONNECTORS', 'MCD_DB_MATCHING_PATTERNS',
                          'MCD_DB_TABLE_ROW_CONNECTORS'):
            body.nested(type_name, ObjectBytes().u32(0))
        body.ascii('SEM1').u16(0).u16(0)
        self.assertEqual(load('MCD_DB_SUB_COMPONENT', body), typed('MCD_DB_SUB_COMPONENT', {
            'description_id': None, 'long_name_id': None, 'unique_object_id': None,
            'description': None, 'long_name': None, 'short_name': 'SC1',
            'diag_trouble_code_connectors': [], 'env_data_connectors': [],
            'sub_component_param_connectors': [], 'sub_component_patterns': [],
            'table_row_connectors': [], 'semantic': 'SEM1', 'dtc_dop_names': [],
            'dtc_names': []}))

    def test_mcd_db_sub_component_all_branches(self):
        body = sub_component_names_body(ObjectBytes())
        body.nested('MCD_DB_DIAG_TROUBLE_CODE_CONNECTORS',
                    ObjectBytes().u32(1).nested('MCD_DB_DIAG_TROUBLE_CODE_CONNECTOR',
                                                dtc_connector_body()))
        body.nested('MCD_DB_ENV_DATA_CONNECTORS',
                    ObjectBytes().u32(1).nested('MCD_DB_ENV_DATA_CONNECTOR', env_connector_body()))
        body.nested('MCD_DB_SUB_COMPONENT_PARAM_CONNECTORS',
                    ObjectBytes().u32(1).nested('MCD_DB_SUB_COMPONENT_PARAM_CONNECTOR',
                                                param_connector_body()))
        body.nested('MCD_DB_MATCHING_PATTERNS',
                    ObjectBytes().u32(1).nested('MCD_DB_MATCHING_PATTERN', ObjectBytes().absent()))
        body.nested('MCD_DB_TABLE_ROW_CONNECTORS',
                    ObjectBytes().u32(1).nested('MCD_DB_TABLE_ROW_CONNECTOR',
                                                table_row_connector_body()))
        body.ascii('SEM2').u16(1).ascii('DOP1').u16(2).ascii('DTC1').ascii('DTC2')
        self.assertEqual(load('MCD_DB_SUB_COMPONENT', body), typed('MCD_DB_SUB_COMPONENT', {
            **SUB_COMPONENT_NAMES,
            'diag_trouble_code_connectors': [dtc_connector()],
            'env_data_connectors': [env_connector()],
            'sub_component_param_connectors': [param_connector()],
            'sub_component_patterns': [typed('MCD_DB_MATCHING_PATTERN',
                                             {'matching_parameters': None})],
            'table_row_connectors': [table_row_connector()],
            'semantic': 'SEM2', 'dtc_dop_names': ['DOP1'], 'dtc_names': ['DTC1', 'DTC2']}))

    def test_sub_component_with_absent_optional_objects(self):
        body = sub_component_names_body(ObjectBytes())
        for _ in range(5):
            body.absent()
        body.ascii('SEM1').u16(0).u16(1).ascii('DTC1')
        self.assertEqual(load('MCD_DB_SUB_COMPONENT', body), typed('MCD_DB_SUB_COMPONENT', {
            **SUB_COMPONENT_NAMES,
            'diag_trouble_code_connectors': None, 'env_data_connectors': None,
            'sub_component_param_connectors': None, 'sub_component_patterns': None,
            'table_row_connectors': None, 'semantic': 'SEM1', 'dtc_dop_names': [],
            'dtc_names': ['DTC1']}))


if __name__ == '__main__':
    unittest.main()
