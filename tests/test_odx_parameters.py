"""Tests for the ODX PARAM writer."""
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from odx_export import parameters
from odx_export.elements import XSI_TYPE
from tests.odx_support import context, xml

OWN = '0.0.0@L.sd'


def reference(object_id, pool_id=OWN):
    return {'object_id': object_id, 'pool_id': pool_id}


def value(content, data_type='eA_UINT32'):
    return {'data_type': data_type, 'value': content}


def coded_type(bit_length=8):
    return {'coded_type': 'eSTANDARD_LENGTH_TYPE', 'bit_length': bit_length, 'bit_mask': bytearray(),
            'base_data_type': 'eDB_UINT32', 'encoding': 'eNONE', 'is_high_low_byte_order': True,
            'is_condensed_bit_mask': False, 'length_key_parameter': None}


def parameter(kind, short_name='P1', **fields):
    result = {'#OBJECT_TYPE': 'MCD_DB_PARAMETER_SIMPLE', 'description': None, 'long_name': None,
              'short_name': short_name, 'description_id': None, 'long_name_id': None,
              'unique_object_id': 'OID-' + short_name, 'bit_position': 0, 'byte_position': 2,
              'default_value': None, 'display_level': 0, 'semantic': None, 'system_parameter': None,
              'mcd_parameter_type': kind, 'parameter_type': None, 'diag_coded_type': None,
              'dop_base_reference': None, 'dop_base': None, 'is_byte_position_available': True,
              'special_data_group_references': [], 'is_protocol_parameter': False,
              'nrc_constant_values': None}
    result.update(fields)
    return result


def table_key(short_name='KEY', table_reference=None, is_table_row_reference=False):
    return parameter('eTABLE_KEY', short_name, table=None, table_reference=table_reference,
                     is_table_row_reference=is_table_row_reference, row_reference_short_name=None)


def tags(element):
    return [child.tag for child in element]


def target_context():
    return context({'DOP_L_D1': ('DB_DOP_SIMPLE_BASE', {}),
                    'TB_L_T1': ('MCD_DB_TABLE', {}),
                    'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', {})})


def write(ctx, *params):
    return parameters.add_params(ctx, ET.Element('X'), list(params), 'S1')


class ParamKindTests(unittest.TestCase):
    def test_param_kinds(self):
        ctx = target_context()
        written = write(
            ctx,
            parameter('eCODED_CONST', 'C', default_value=value(0x22), diag_coded_type=coded_type()),
            parameter('eVALUE', 'V', default_value=value(7), dop_base_reference=reference('DOP_L_D1')),
            parameter('ePHYS_CONST', 'PC', default_value=value(1.5, 'eA_FLOAT64'),
                      dop_base_reference=reference('DOP_L_D1')),
            parameter('eRESERVED', 'R', diag_coded_type=coded_type(4)),
            parameter('eLENGTH_KEY', 'LK', dop_base_reference=reference('DOP_L_D1')),
            dict(parameter('eMATCHING_REQUEST_PARAM', 'M'), request_byte_position=1, byte_length=2),
            table_key('TK', reference('TB_L_T1')),
            dict(parameter('eTABLE_STRUCT', 'TS'), key_parameter_short_name='TK',
                 table_reference=reference('TB_L_T1')))
        self.assertEqual(written.tag, 'PARAMS')
        kinds = [param.get(XSI_TYPE) for param in written]
        self.assertEqual(kinds, ['CODED-CONST', 'VALUE', 'PHYS-CONST', 'RESERVED', 'LENGTH-KEY',
                                 'MATCHING-REQUEST-PARAM', 'TABLE-KEY', 'TABLE-STRUCT'])
        coded, value_param, phys, reserved, length_key, matching, key, table_struct = list(written)
        self.assertEqual(tags(coded), ['SHORT-NAME', 'BYTE-POSITION', 'CODED-VALUE', 'DIAG-CODED-TYPE'])
        self.assertEqual(coded.findtext('CODED-VALUE'), '34')
        self.assertEqual(tags(value_param), ['SHORT-NAME', 'BYTE-POSITION', 'PHYSICAL-DEFAULT-VALUE', 'DOP-REF'])
        self.assertEqual(value_param.findtext('PHYSICAL-DEFAULT-VALUE'), '7')
        self.assertEqual(xml(value_param.find('DOP-REF')), '<DOP-REF ID-REF="D1" />')
        self.assertEqual(tags(phys), ['SHORT-NAME', 'BYTE-POSITION', 'PHYS-CONSTANT-VALUE', 'DOP-REF'])
        self.assertEqual(phys.findtext('PHYS-CONSTANT-VALUE'), '1.5')
        self.assertEqual(tags(reserved), ['SHORT-NAME', 'BYTE-POSITION', 'BIT-LENGTH'])
        self.assertEqual(reserved.findtext('BIT-LENGTH'), '4')
        self.assertEqual(tags(length_key), ['SHORT-NAME', 'BYTE-POSITION', 'DOP-REF'])
        self.assertEqual(tags(matching), ['SHORT-NAME', 'BYTE-POSITION', 'REQUEST-BYTE-POS', 'BYTE-LENGTH'])
        self.assertEqual(matching.findtext('REQUEST-BYTE-POS'), '1')
        self.assertEqual(matching.findtext('BYTE-LENGTH'), '2')
        self.assertEqual(xml(key.find('TABLE-REF')), '<TABLE-REF ID-REF="T1" />')
        self.assertEqual(xml(table_struct.find('TABLE-KEY-REF')), '<TABLE-KEY-REF ID-REF="S1.TK" />')
        self.assertEqual(ctx.report['unknown_parameter_types'], 0)

    def test_value_param_without_default_or_dop(self):
        ctx = target_context()
        written = write(ctx, parameter('eVALUE', 'V'))
        self.assertEqual(tags(written[0]), ['SHORT-NAME', 'BYTE-POSITION'])
        self.assertEqual(ctx.report['empty_references'], 0)

    def test_semantic_and_names(self):
        ctx = target_context()
        written = write(ctx, parameter('eVALUE', 'V', semantic='DATA', long_name='Value', long_name_id='TI_1',
                                       description='<p>Text</p>', description_id='TI_2'))
        self.assertEqual(written[0].get('SEMANTIC'), 'DATA')
        self.assertEqual(tags(written[0]), ['SHORT-NAME', 'LONG-NAME', 'DESC', 'BYTE-POSITION'])

    def test_nrc_const_param(self):
        ctx = target_context()
        written = write(ctx, parameter('eNRC_CONST', 'NRC', diag_coded_type=coded_type(),
                                       nrc_constant_values=[value(0x11), value(0x12)]))
        param = written[0]
        self.assertEqual(param.get(XSI_TYPE), 'NRC-CONST')
        self.assertEqual(tags(param), ['SHORT-NAME', 'BYTE-POSITION', 'CODED-VALUES', 'DIAG-CODED-TYPE'])
        self.assertEqual([entry.text for entry in param.find('CODED-VALUES')], ['17', '18'])
        self.assertEqual(tags(param.find('CODED-VALUES')), ['CODED-VALUE', 'CODED-VALUE'])

    def test_system_param(self):
        ctx = target_context()
        written = write(ctx, parameter('eSYSTEM', 'SYS', system_parameter='TIMESTAMP',
                                       dop_base_reference=reference('DOP_L_D1')))
        param = written[0]
        self.assertEqual(param.get(XSI_TYPE), 'SYSTEM')
        self.assertEqual(param.get('SYSPARAM'), 'TIMESTAMP')
        self.assertEqual(tags(param), ['SHORT-NAME', 'BYTE-POSITION', 'DOP-REF'])

    def test_unknown_param_type_is_counted(self):
        ctx = target_context()
        written = write(ctx, parameter('eDYNAMIC', 'DYN'), parameter(0x7055, 'NUM'))
        self.assertEqual([param.get(XSI_TYPE) for param in written], ['DYNAMIC', '28757'])
        self.assertEqual(tags(written[0]), ['SHORT-NAME', 'BYTE-POSITION'])
        self.assertEqual(ctx.report['unknown_parameter_types'], 2)


class ParamIdTests(unittest.TestCase):
    def test_param_ids_only_for_table_key_and_length_key(self):
        ctx = target_context()
        written = write(ctx,
                        parameter('eLENGTH_KEY', 'LK', dop_base_reference=reference('DOP_L_D1')),
                        table_key('TK', reference('TB_L_T1')),
                        parameter('eVALUE', 'V', dop_base_reference=reference('DOP_L_D1')),
                        parameter('eCODED_CONST', 'C', default_value=value(1), diag_coded_type=coded_type()))
        self.assertEqual([param.get('ID') for param in written], ['S1.LK', 'S1.TK', None, None])
        self.assertEqual([param.get('OID') for param in written], ['OID-LK', 'OID-TK', 'OID-V', 'OID-C'])

    def test_every_param_with_object_id_gets_oid(self):
        ctx = target_context()
        written = write(ctx, parameter('eVALUE', 'V'), parameter('eVALUE', 'W', unique_object_id=''),
                        parameter('eVALUE', 'N', unique_object_id=None))
        self.assertEqual(written[0].attrib, {XSI_TYPE: 'VALUE', 'OID': 'OID-V'})
        self.assertNotIn('OID', written[1].attrib)
        self.assertNotIn('OID', written[2].attrib)

    def test_table_key_uses_row_ref_by_flag_or_prefix(self):
        ctx = target_context()
        written = write(ctx,
                        table_key('A', reference('TBP_L_T1.R1')),
                        table_key('B', reference('TB_L_T1'), is_table_row_reference=True),
                        table_key('C', reference('TB_L_T1')))
        self.assertEqual(xml(written[0].find('TABLE-ROW-REF')), '<TABLE-ROW-REF ID-REF="T1.R1" />')
        self.assertEqual(xml(written[1].find('TABLE-ROW-REF')), '<TABLE-ROW-REF ID-REF="T1" />')
        self.assertIsNone(written[2].find('TABLE-ROW-REF'))
        self.assertEqual(xml(written[2].find('TABLE-REF')), '<TABLE-REF ID-REF="T1" />')

    def test_table_key_with_embedded_table_writes_no_reference(self):
        ctx = target_context()
        written = write(ctx, dict(table_key('TK'), table={'short_name': 'T9'}))
        self.assertEqual(tags(written[0]), ['SHORT-NAME', 'BYTE-POSITION'])


class ParamPositionTests(unittest.TestCase):
    def test_param_bit_position_zero_omitted(self):
        ctx = target_context()
        written = write(ctx, parameter('eVALUE', 'A'), parameter('eVALUE', 'B', bit_position=3))
        self.assertIsNone(written[0].find('BIT-POSITION'))
        self.assertEqual(tags(written[1]), ['SHORT-NAME', 'BYTE-POSITION', 'BIT-POSITION'])
        self.assertEqual(written[1].findtext('BIT-POSITION'), '3')

    def test_param_without_byte_position(self):
        ctx = target_context()
        written = write(ctx, parameter('eVALUE', 'A', is_byte_position_available=False))
        self.assertEqual(tags(written[0]), ['SHORT-NAME'])


class ParamsTests(unittest.TestCase):
    def test_no_parameters_no_params(self):
        ctx = target_context()
        parent = ET.Element('X')
        self.assertIsNone(parameters.add_params(ctx, parent, None, 'S1'))
        self.assertIsNone(parameters.add_params(ctx, parent, [None], 'S1'))
        self.assertEqual(len(parent), 0)

    def test_coded_const_length_key_ref_uses_owner(self):
        ctx = target_context()
        length_coded_type = dict(coded_type(), coded_type='ePARAM_LENGTH_INFO_TYPE',
                                 length_key_parameter={'short_name': 'LEN', 'unique_object_id': 'X-1'})
        written = write(ctx, parameter('eCODED_CONST', 'C', default_value=value(1),
                                       diag_coded_type=length_coded_type))
        self.assertEqual(written[0].find('DIAG-CODED-TYPE/LENGTH-KEY-REF').get('ID-REF'), 'S1.LEN')

    def test_sdgs_come_after_the_names(self):
        def fake_sdgs(ctx, parent, obj):
            return ET.SubElement(parent, 'SDGS')

        ctx = target_context()
        with mock.patch('odx_export.special_data.sdgs', fake_sdgs):
            written = write(ctx, parameter('eVALUE', 'V', bit_position=1, long_name='Value'))
        self.assertEqual(tags(written[0]), ['SHORT-NAME', 'LONG-NAME', 'SDGS', 'BYTE-POSITION', 'BIT-POSITION'])


if __name__ == '__main__':
    unittest.main()
