"""Tests for the ODX structures, fields, multiplexers and environment data."""
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from odx_export import structures
from tests.odx_support import context, xml

OWN = '0.0.0@L.sd'


def reference(object_id, pool_id=OWN):
    return {'object_id': object_id, 'pool_id': pool_id}


def value(content, data_type='eA_UINT32'):
    return {'data_type': data_type, 'value': content}


def limit(content, limit_type='eLIMIT_CLOSED'):
    return {'limit': value(content), 'limit_type': limit_type}


def parameter(short_name, **fields):
    result = {'description': None, 'long_name': None, 'short_name': short_name, 'description_id': None,
              'long_name_id': None, 'unique_object_id': 'OID-' + short_name, 'bit_position': 0,
              'byte_position': 0, 'default_value': None, 'semantic': None, 'system_parameter': None,
              'mcd_parameter_type': 'eVALUE', 'diag_coded_type': None,
              'dop_base_reference': reference('DOP_L_D1'), 'is_byte_position_available': True,
              'special_data_group_references': [], 'nrc_constant_values': None}
    result.update(fields)
    return result


def structure(byte_length, parameters=None):
    return {'short_name': 'Structure', 'long_name': 'A structure', 'long_name_id': 'TI_S',
            'description': None, 'description_id': None, 'unique_object_id': 'OID-S',
            'byte_length': byte_length, 'parameters': parameters}


def field(structure_reference=None, env_data_desc_reference=None, **fields):
    result = {'dop_structure_reference': structure_reference,
              'dop_env_data_desc_reference': env_data_desc_reference}
    result.update(fields)
    return result


def case_base(short_name, structure_reference):
    return {'short_name': short_name, 'long_name': None, 'description': None,
            'unique_object_id': 'OID-' + short_name, 'long_name_id': None, 'description_id': None,
            'structure_dop_reference': structure_reference}


def pool(**extra):
    objects = {'DOP_L_D1': ('DB_DOP_SIMPLE_BASE', {}),
               'DOP_L_S1': ('MCD_DB_PARAMETER_STRUCTURE', structure(4)),
               'DOP_L_S2': ('MCD_DB_PARAMETER_STRUCTURE', structure(0)),
               'DOP_L_E1': ('MCD_DB_PARAMETER_ENV_DATA_DESC', {}),
               'DOP_L_V1': ('MCD_DB_PARAMETER_ENV_DATA', {})}
    objects.update(extra)
    return context(objects)


def tags(element):
    return [child.tag for child in element]


class StructureTests(unittest.TestCase):
    def test_structure(self):
        ctx = pool(DOP_L_S3=('MCD_DB_PARAMETER_STRUCTURE', structure(4, [parameter('A')])))
        element = structures.add_structure(ctx, ET.Element('X'), 'DOP_L_S3')
        self.assertEqual(element.attrib, {'ID': 'S3', 'OID': 'OID-S'})
        self.assertEqual(tags(element), ['SHORT-NAME', 'LONG-NAME', 'BYTE-SIZE', 'PARAMS'])
        self.assertEqual(element.findtext('BYTE-SIZE'), '4')
        self.assertIn('DOP_L_S3', ctx.used)

    def test_structure_byte_size_zero_omitted(self):
        ctx = pool()
        element = structures.add_structure(ctx, ET.Element('X'), 'DOP_L_S2')
        self.assertEqual(tags(element), ['SHORT-NAME', 'LONG-NAME'])

    def test_structure_length_key_param_id_uses_structure_id(self):
        ctx = pool(DOP_L_S3=('MCD_DB_PARAMETER_STRUCTURE', structure(
            0, [parameter('LEN', mcd_parameter_type='eLENGTH_KEY')])))
        element = structures.add_structure(ctx, ET.Element('X'), 'DOP_L_S3')
        self.assertEqual(element.find('PARAMS/PARAM').get('ID'), 'S3.LEN')


class FieldTests(unittest.TestCase):
    def test_static_field(self):
        ctx = pool(DOP_L_F1=('MCD_DB_PARAMETER_STATIC_FIELD', field(
            reference('DOP_L_S1'), fixed_number_of_items=3, item_byte_size=2)))
        element = structures.add_static_field(ctx, ET.Element('X'), 'DOP_L_F1')
        self.assertEqual(element.tag, 'STATIC-FIELD')
        self.assertEqual(element.attrib, {'ID': 'F1'})
        self.assertEqual(tags(element), ['SHORT-NAME', 'BASIC-STRUCTURE-REF', 'FIXED-NUMBER-OF-ITEMS',
                                         'ITEM-BYTE-SIZE'])
        self.assertEqual(element.findtext('SHORT-NAME'), 'F1')
        self.assertEqual(xml(element.find('BASIC-STRUCTURE-REF')), '<BASIC-STRUCTURE-REF ID-REF="S1" />')
        self.assertEqual(element.findtext('FIXED-NUMBER-OF-ITEMS'), '3')
        self.assertEqual(element.findtext('ITEM-BYTE-SIZE'), '2')

    def test_dynamic_length_field(self):
        ctx = pool(DOP_L_F2=('MCD_DB_PARAMETER_DYNAMIC_LENGTH_FIELD', field(
            reference('DOP_L_S1'), offset=1, dop_base_reference=reference('DOP_L_D1'),
            simple_byte_position=0, simple_bit_position=0)),
                   DOP_L_F3=('MCD_DB_PARAMETER_DYNAMIC_LENGTH_FIELD', field(
            reference('DOP_L_S1'), offset=0, dop_base_reference=reference('DOP_L_D1'),
            simple_byte_position=2, simple_bit_position=4)))
        parent = ET.Element('X')
        element = structures.add_dynamic_length_field(ctx, parent, 'DOP_L_F2')
        self.assertEqual(element.tag, 'DYNAMIC-LENGTH-FIELD')
        self.assertEqual(tags(element), ['SHORT-NAME', 'BASIC-STRUCTURE-REF', 'OFFSET',
                                         'DETERMINE-NUMBER-OF-ITEMS'])
        self.assertEqual(element.findtext('OFFSET'), '1')
        determine = element.find('DETERMINE-NUMBER-OF-ITEMS')
        self.assertEqual(tags(determine), ['BYTE-POSITION', 'DATA-OBJECT-PROP-REF'])
        self.assertEqual(determine.findtext('BYTE-POSITION'), '0')
        self.assertEqual(determine.find('DATA-OBJECT-PROP-REF').get('ID-REF'), 'D1')
        other = structures.add_dynamic_length_field(ctx, parent, 'DOP_L_F3')
        self.assertEqual(tags(other.find('DETERMINE-NUMBER-OF-ITEMS')),
                         ['BYTE-POSITION', 'BIT-POSITION', 'DATA-OBJECT-PROP-REF'])
        self.assertEqual(other.findtext('DETERMINE-NUMBER-OF-ITEMS/BIT-POSITION'), '4')

    def test_end_of_pdu_field_writes_min_zero_and_omits_max_default(self):
        ctx = pool(DOP_L_F4=('MCD_DB_PARAMETER_END_OF_PDU_FIELD', field(
            reference('DOP_L_S1'), max_number_of_items=0xFFFFFFFF, min_number_of_items=0)),
                   DOP_L_F5=('MCD_DB_PARAMETER_END_OF_PDU_FIELD', field(
            reference('DOP_L_S1'), max_number_of_items=8, min_number_of_items=1)))
        parent = ET.Element('X')
        default = structures.add_end_of_pdu_field(ctx, parent, 'DOP_L_F4')
        self.assertEqual(default.tag, 'END-OF-PDU-FIELD')
        self.assertEqual(tags(default), ['SHORT-NAME', 'BASIC-STRUCTURE-REF', 'MIN-NUMBER-OF-ITEMS'])
        self.assertEqual(default.findtext('MIN-NUMBER-OF-ITEMS'), '0')
        limited = structures.add_end_of_pdu_field(ctx, parent, 'DOP_L_F5')
        self.assertEqual(tags(limited), ['SHORT-NAME', 'BASIC-STRUCTURE-REF', 'MAX-NUMBER-OF-ITEMS',
                                         'MIN-NUMBER-OF-ITEMS'])
        self.assertEqual(limited.findtext('MAX-NUMBER-OF-ITEMS'), '8')

    def test_field_with_env_data_desc_reference(self):
        ctx = pool(DOP_L_F6=('MCD_DB_PARAMETER_END_OF_PDU_FIELD', field(
            None, reference('DOP_L_E1'), max_number_of_items=0xFFFFFFFF, min_number_of_items=0)))
        element = structures.add_end_of_pdu_field(ctx, ET.Element('X'), 'DOP_L_F6')
        self.assertEqual(xml(element.find('ENV-DATA-DESC-REF')), '<ENV-DATA-DESC-REF ID-REF="E1" />')
        self.assertIsNone(element.find('BASIC-STRUCTURE-REF'))
        self.assertEqual(ctx.report['empty_references'], 0)


class MuxTests(unittest.TestCase):
    def test_mux_with_default_case_and_cases(self):
        mux = {'offset': 1,
               'switch_key': {'bit_position': 0, 'byte_position': 0, 'is_byte_position_available': True,
                              'dop_base_reference': reference('DOP_L_D1')},
               'cases': [dict(case_base('ONE', reference('DOP_L_S1')),
                              lower_limit=limit(1), upper_limit=limit(1)),
                         dict(case_base('TWO', reference('DOP_L_S2')),
                              lower_limit=limit(2), upper_limit=limit(5, 'eLIMIT_OPEN'))],
               'default_case': case_base('OTHER', reference('DOP_L_S2'))}
        ctx = pool(DOP_L_M1=('MCD_DB_PARAMETER_MULTIPLEXER', mux))
        element = structures.add_mux(ctx, ET.Element('X'), 'DOP_L_M1')
        self.assertEqual(element.attrib, {'ID': 'M1'})
        self.assertEqual(tags(element), ['SHORT-NAME', 'BYTE-POSITION', 'SWITCH-KEY', 'DEFAULT-CASE', 'CASES'])
        self.assertEqual(element.findtext('SHORT-NAME'), 'M1')
        self.assertEqual(element.findtext('BYTE-POSITION'), '1')
        self.assertEqual(tags(element.find('SWITCH-KEY')), ['BYTE-POSITION', 'DATA-OBJECT-PROP-REF'])
        default = element.find('DEFAULT-CASE')
        self.assertEqual(tags(default), ['SHORT-NAME', 'STRUCTURE-REF'])
        self.assertEqual(default.find('STRUCTURE-REF').get('ID-REF'), 'S2')
        cases = element.findall('CASES/CASE')
        self.assertEqual(tags(cases[0]), ['SHORT-NAME', 'STRUCTURE-REF', 'LOWER-LIMIT', 'UPPER-LIMIT'])
        self.assertEqual(cases[0].findtext('LOWER-LIMIT'), '1')
        self.assertEqual(xml(cases[1].find('UPPER-LIMIT')), '<UPPER-LIMIT INTERVAL-TYPE="OPEN">5</UPPER-LIMIT>')

    def test_mux_without_default_case_and_case_without_structure(self):
        mux = {'offset': 0,
               'switch_key': {'bit_position': 3, 'byte_position': 2, 'is_byte_position_available': True,
                              'dop_base_reference': reference('DOP_L_D1')},
               'cases': [dict(case_base('ONE', None), lower_limit=limit(1), upper_limit=limit(1))],
               'default_case': None}
        ctx = pool(DOP_L_M2=('MCD_DB_PARAMETER_MULTIPLEXER', mux))
        element = structures.add_mux(ctx, ET.Element('X'), 'DOP_L_M2')
        self.assertEqual(tags(element), ['SHORT-NAME', 'BYTE-POSITION', 'SWITCH-KEY', 'CASES'])
        self.assertEqual(tags(element.find('SWITCH-KEY')), ['BYTE-POSITION', 'BIT-POSITION',
                                                            'DATA-OBJECT-PROP-REF'])
        self.assertEqual(tags(element.find('CASES/CASE')), ['SHORT-NAME', 'LOWER-LIMIT', 'UPPER-LIMIT'])
        self.assertEqual(ctx.report['empty_references'], 0)


class MuxLimitTests(unittest.TestCase):
    def test_case_without_limit_objects_writes_no_limit_elements(self):
        mux = {'offset': 0,
               'switch_key': {'bit_position': 0, 'byte_position': 0, 'is_byte_position_available': True,
                              'dop_base_reference': reference('DOP_L_D1')},
               'cases': [dict(case_base('ONE', None), lower_limit=None, upper_limit=limit(1))],
               'default_case': None}
        ctx = pool(DOP_L_M3=('MCD_DB_PARAMETER_MULTIPLEXER', mux))
        element = structures.add_mux(ctx, ET.Element('X'), 'DOP_L_M3')
        self.assertEqual(tags(element.find('CASES/CASE')), ['SHORT-NAME', 'UPPER-LIMIT'])


class EnvDataTests(unittest.TestCase):
    def test_env_data_desc_and_env_data_with_all_value(self):
        all_value = parameter('ALL', long_name='All values', mcd_parameter_type='eVALUE',
                              dop_base_reference=reference('DOP_L_V2'))
        desc = {'is_parameter_short_name_path_available': False, 'parameter_short_name_path': None,
                'parameter_name': 'DTC_NUMBER', 'byte_length': 0,
                'env_data_desc': {'description': None, 'long_name': 'Environment', 'short_name': 'ENV',
                                  'description_id': None, 'long_name_id': None, 'unique_object_id': 'OID-E',
                                  'env_data_parameter_map': [], 'all_value_env_data_parameter': all_value,
                                  'env_data_information_map': []}}
        env_data = {'byte_length': 4, 'parameters': [parameter('A')]}
        ctx = pool(DOP_L_E2=('MCD_DB_PARAMETER_ENV_DATA_DESC', desc),
                   DOP_L_V2=('MCD_DB_PARAMETER_ENV_DATA', env_data))
        parent = ET.Element('X')
        desc_element = structures.add_env_data_desc(ctx, parent, 'DOP_L_E2')
        self.assertEqual(desc_element.tag, 'ENV-DATA-DESC')
        self.assertEqual(desc_element.attrib, {'ID': 'E2', 'OID': 'OID-E'})
        self.assertEqual(tags(desc_element), ['SHORT-NAME', 'LONG-NAME', 'PARAM-SNREF', 'ENV-DATA-REFS'])
        self.assertEqual(desc_element.findtext('SHORT-NAME'), 'ENV')
        self.assertEqual(xml(desc_element.find('PARAM-SNREF')), '<PARAM-SNREF SHORT-NAME="DTC_NUMBER" />')
        self.assertEqual(xml(desc_element.find('ENV-DATA-REFS')),
                         '<ENV-DATA-REFS><ENV-DATA-REF ID-REF="V2" /></ENV-DATA-REFS>')
        data_element = structures.add_env_data(ctx, parent, 'DOP_L_V2', all_value)
        self.assertEqual(data_element.tag, 'ENV-DATA')
        self.assertEqual(data_element.attrib, {'ID': 'V2', 'OID': 'OID-ALL'})
        self.assertEqual(tags(data_element), ['SHORT-NAME', 'LONG-NAME', 'PARAMS', 'ALL-VALUE'])
        self.assertEqual(data_element.findtext('SHORT-NAME'), 'ALL')
        self.assertEqual(data_element.find('PARAMS/PARAM').findtext('SHORT-NAME'), 'A')
        self.assertTrue({'DOP_L_E2', 'DOP_L_V2'} <= ctx.used)

    def test_env_data_desc_with_short_name_path_and_env_data_without_all_value(self):
        desc = {'is_parameter_short_name_path_available': True, 'parameter_short_name_path': 'A.B',
                'parameter_name': None, 'byte_length': 0,
                'env_data_desc': {'description': None, 'long_name': None, 'short_name': 'ENV',
                                  'description_id': None, 'long_name_id': None, 'unique_object_id': None,
                                  'env_data_parameter_map': [], 'all_value_env_data_parameter': None,
                                  'env_data_information_map': []}}
        ctx = pool(DOP_L_E3=('MCD_DB_PARAMETER_ENV_DATA_DESC', desc),
                   DOP_L_V3=('MCD_DB_PARAMETER_ENV_DATA', {'byte_length': 0, 'parameters': None}))
        parent = ET.Element('X')
        desc_element = structures.add_env_data_desc(ctx, parent, 'DOP_L_E3')
        self.assertEqual(desc_element.attrib, {'ID': 'E3'})
        self.assertEqual(tags(desc_element), ['SHORT-NAME', 'PARAM-SNPATHREF'])
        self.assertEqual(desc_element.find('PARAM-SNPATHREF').get('SHORT-NAME-PATH'), 'A.B')
        data_element = structures.add_env_data(ctx, parent, 'DOP_L_V3', None)
        self.assertEqual(data_element.attrib, {'ID': 'V3'})
        self.assertEqual(tags(data_element), ['SHORT-NAME'])
        self.assertEqual(data_element.findtext('SHORT-NAME'), 'V3')


class SdgsPositionTests(unittest.TestCase):
    def test_sdgs_come_after_the_names(self):
        def fake_sdgs(ctx, parent, obj):
            return ET.SubElement(parent, 'SDGS')

        desc = {'is_parameter_short_name_path_available': False, 'parameter_short_name_path': None,
                'parameter_name': 'DTC_NUMBER', 'byte_length': 0,
                'env_data_desc': {'description': None, 'long_name': None, 'short_name': 'ENV',
                                  'description_id': None, 'long_name_id': None, 'unique_object_id': None,
                                  'env_data_parameter_map': [], 'all_value_env_data_parameter': None,
                                  'env_data_information_map': []}}
        ctx = pool(DOP_L_F1=('MCD_DB_PARAMETER_STATIC_FIELD', field(
                       reference('DOP_L_S1'), fixed_number_of_items=3, item_byte_size=2)),
                   DOP_L_M1=('MCD_DB_PARAMETER_MULTIPLEXER', {
                       'offset': 0, 'switch_key': None, 'cases': [], 'default_case': None}),
                   DOP_L_E4=('MCD_DB_PARAMETER_ENV_DATA_DESC', desc),
                   DOP_L_V4=('MCD_DB_PARAMETER_ENV_DATA', {'byte_length': 0, 'parameters': [parameter('A')]}))
        parent = ET.Element('X')
        with mock.patch('odx_export.special_data.sdgs', fake_sdgs):
            structure_element = structures.add_structure(ctx, parent, 'DOP_L_S1')
            field_element = structures.add_static_field(ctx, parent, 'DOP_L_F1')
            mux_element = structures.add_mux(ctx, parent, 'DOP_L_M1')
            desc_element = structures.add_env_data_desc(ctx, parent, 'DOP_L_E4')
            env_data_element = structures.add_env_data(ctx, parent, 'DOP_L_V4', None)
        self.assertEqual(tags(structure_element)[:3], ['SHORT-NAME', 'LONG-NAME', 'SDGS'])
        self.assertEqual(tags(field_element)[:3], ['SHORT-NAME', 'SDGS', 'BASIC-STRUCTURE-REF'])
        self.assertEqual(tags(mux_element), ['SHORT-NAME', 'SDGS', 'BYTE-POSITION'])
        self.assertEqual(tags(desc_element), ['SHORT-NAME', 'SDGS', 'PARAM-SNREF'])
        # The parameters of the environment data carry their own SDGS.
        self.assertEqual(tags(env_data_element), ['SHORT-NAME', 'SDGS', 'PARAMS'])


if __name__ == '__main__':
    unittest.main()
