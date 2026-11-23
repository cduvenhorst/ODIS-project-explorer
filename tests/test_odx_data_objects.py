"""Tests for the ODX data object properties, coded and physical types, compu methods and units."""
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from odx_export import data_objects
from odx_export.elements import XSI_TYPE
from tests.odx_support import context, xml

OWN = '0.0.0@L.sd'


def reference(object_id, pool_id=OWN):
    return {'object_id': object_id, 'pool_id': pool_id}


def value(content, data_type='eA_UINT32'):
    return {'data_type': data_type, 'value': content}


def limit(content, limit_type='eLIMIT_CLOSED', data_type='eA_UINT32'):
    return {'limit': None if content is None else value(content, data_type), 'limit_type': limit_type}


def coded_type(**fields):
    result = {'coded_type': 'eSTANDARD_LENGTH_TYPE', 'bit_length': 8, 'bit_mask': bytearray(),
              'base_data_type': 'eDB_UINT32', 'encoding': 'eNONE', 'is_high_low_byte_order': True,
              'is_condensed_bit_mask': False, 'length_key_parameter': None}
    result.update(fields)
    return result


def min_max_type(max_length, min_length=1):
    return coded_type(coded_type='eMIN_MAX_LENGTH_TYPE', bit_length=None, max_length=max_length,
                      min_length=min_length, termination='eZERO', base_data_type='eDB_ASCIISTRING',
                      encoding='eISO_8859_1')


def scale(lower, upper, constant=None, inverse=None, coeffs=None, long_name_id=None, plain_coeffs=None):
    return {'long_name_id': long_name_id, 'compu_rational_coeffs': plain_coeffs,
            'compu_rational_coeffs_as_coded_values': coeffs, 'lower_limit': None, 'upper_limit': None,
            'compu_constant': constant, 'compu_inverse_value': inverse, 'compu_constant_as_coded_value': None,
            'lower_limit_as_coded_value': lower, 'upper_limit_as_coded_value': upper}


def compu_method(category, scales=None, default=None, default_id=None):
    internal_to_phys = {'compu_scales': scales, 'compu_default_value': default, 'compu_code_byte_stream': None,
                        'code_information': None, 'compu_inverse_value': None}
    return {'compu_category': category, 'compu_phys_to_internal': None,
            'compu_internal_to_phys': internal_to_phys, 'compu_inverse_value_id': None,
            'compu_default_value_id': default_id}


def physical_type(base='eDB_PHYS_UINT32', radix=10, precision=None):
    return {'base_data_type': base, 'is_precision_available': precision is not None,
            'precision': precision, 'display_radix': radix}


def interval(lower, upper, lower_type='eLIMIT_CLOSED', upper_type='eLIMIT_CLOSED'):
    return {'lower_limit': value(lower), 'upper_limit': value(upper),
            'lower_limit_interval_type': lower_type, 'upper_limit_interval_type': upper_type}


def constraint(lower=0, upper=255, scales=None, computed=False, **interval_types):
    return {'interval': interval(lower, upper, **interval_types), 'scale_constraints': scales or [],
            'is_computed': computed}


def scale_constraint(label, lower, upper, range_info='eVALUE_NOT_AVAILABLE', **interval_types):
    return {'interval': interval(lower, upper, **interval_types), 'range_info': range_info,
            'description': None, 'description_id': None, 'short_label': label,
            'short_label_id': label + '_TI', 'is_computed': False}


def dimension(unique_object_id, short_name, **exponents):
    result = {'short_name': short_name, 'long_name': None, 'description': None,
              'unique_object_id': unique_object_id, 'long_name_id': None, 'description_id': None}
    for field in ('length_exponent', 'mass_exponent', 'time_exponent', 'current_exponent',
                  'temperature_exponent', 'molar_amount_exponent', 'luminous_intensity'):
        result[field] = exponents.get(field, 0)
    return result


def unit(short_name, unique_object_id, physical_dimension=None):
    return {'short_name': short_name, 'long_name': None, 'description': None,
            'unique_object_id': unique_object_id, 'long_name_id': None, 'description_id': None,
            'display_name': short_name.lower(), 'factor_si_to_unit': 1000.0, 'offset_si_to_unit': 0.5,
            'physical_dimension': physical_dimension, 'unit_group_references': []}


def tags(element):
    return [child.tag for child in element]


class DiagCodedTypeTests(unittest.TestCase):
    def test_standard_length_coded_type(self):
        ctx = context({})
        element = data_objects.add_diag_coded_type(
            ctx, ET.Element('X'), coded_type(bit_length=32, bit_mask=bytearray(b'\x0f\xff')))
        self.assertEqual(element.get(XSI_TYPE), 'STANDARD-LENGTH-TYPE')
        self.assertEqual(element.get('BASE-DATA-TYPE'), 'A_UINT32')
        self.assertNotIn('BASE-TYPE-ENCODING', element.attrib)
        self.assertNotIn('IS-HIGHLOW-BYTE-ORDER', element.attrib)
        self.assertEqual(tags(element), ['BIT-LENGTH', 'BIT-MASK'])
        self.assertEqual(element.findtext('BIT-LENGTH'), '32')
        self.assertEqual(element.findtext('BIT-MASK'), '0FFF')

    def test_leading_length_info_type_writes_no_bit_mask(self):
        ctx = context({})
        element = data_objects.add_diag_coded_type(
            ctx, ET.Element('X'), coded_type(coded_type='eLEADING_LENGTH_INFO_TYPE', bit_length=8,
                                             bit_mask=bytearray(b'\x0f')))
        self.assertEqual(tags(element), ['BIT-LENGTH'])

    def test_length_key_owner_cache_is_created_by_the_context(self):
        self.assertTrue(hasattr(context({}), '_length_key_owners'))

    def test_low_high_byte_order_is_written(self):
        ctx = context({})
        element = data_objects.add_diag_coded_type(ctx, ET.Element('X'),
                                                   coded_type(is_high_low_byte_order=False))
        self.assertEqual(element.get('IS-HIGHLOW-BYTE-ORDER'), 'false')
        self.assertEqual(tags(element), ['BIT-LENGTH'])

    def test_coded_type_drops_converter_encodings(self):
        ctx = context({})
        parent = ET.Element('X')
        ascii_type = data_objects.add_diag_coded_type(
            ctx, parent, coded_type(base_data_type='eDB_ASCIISTRING', encoding='eISO_8859_1'))
        int_type = data_objects.add_diag_coded_type(
            ctx, parent, coded_type(base_data_type='eDB_INT32', encoding='e2C'))
        unicode_type = data_objects.add_diag_coded_type(
            ctx, parent, coded_type(base_data_type='eDB_UNICODE2STRING', encoding='eUCS_2'))
        self.assertEqual(ascii_type.get('BASE-DATA-TYPE'), 'A_ASCIISTRING')
        self.assertNotIn('BASE-TYPE-ENCODING', ascii_type.attrib)
        self.assertNotIn('BASE-TYPE-ENCODING', int_type.attrib)
        self.assertEqual(unicode_type.get('BASE-TYPE-ENCODING'), 'UCS-2')

    def test_ieee754_encoding_is_written(self):
        ctx = context({})
        element = data_objects.add_diag_coded_type(
            ctx, ET.Element('X'), coded_type(base_data_type='eDB_FLOAT32', encoding='eIEEE754'))
        self.assertEqual(element.get('BASE-TYPE-ENCODING'), 'IEEE754')
        self.assertEqual(ctx.report['unmapped_enumerations'], 0)

    def test_unmapped_encoding_is_not_written(self):
        ctx = context({})
        element = data_objects.add_diag_coded_type(
            ctx, ET.Element('X'), coded_type(base_data_type='eDB_FLOAT32', encoding=42))
        self.assertNotIn('BASE-TYPE-ENCODING', element.attrib)
        self.assertEqual(ctx.report['unmapped_enumerations'], 1)

    def test_min_max_length_omits_default_max(self):
        ctx = context({})
        parent = ET.Element('X')
        default_max = data_objects.add_diag_coded_type(ctx, parent, min_max_type(65535))
        short_max = data_objects.add_diag_coded_type(ctx, parent, min_max_type(20))
        self.assertEqual(default_max.get(XSI_TYPE), 'MIN-MAX-LENGTH-TYPE')
        self.assertEqual(default_max.get('TERMINATION'), 'ZERO')
        self.assertEqual(tags(default_max), ['MIN-LENGTH'])
        self.assertEqual(tags(short_max), ['MAX-LENGTH', 'MIN-LENGTH'])
        self.assertEqual(short_max.findtext('MAX-LENGTH'), '20')
        self.assertEqual(short_max.findtext('MIN-LENGTH'), '1')

    def test_terminations(self):
        ctx = context({})
        parent = ET.Element('X')
        for termination, text in (('eENDOFPDU', 'END-OF-PDU'), ('eHEX_FF', 'HEX-FF')):
            element = data_objects.add_diag_coded_type(ctx, parent, dict(min_max_type(20),
                                                                         termination=termination))
            self.assertEqual(element.get('TERMINATION'), text)

    def test_leading_length_info_type(self):
        ctx = context({})
        element = data_objects.add_diag_coded_type(
            ctx, ET.Element('X'), coded_type(coded_type='eLEADING_LENGTH_INFO_TYPE', bit_length=8,
                                             base_data_type='eDB_BYTEFIELD'))
        self.assertEqual(element.get(XSI_TYPE), 'LEADING-LENGTH-INFO-TYPE')
        self.assertEqual(element.get('BASE-DATA-TYPE'), 'A_BYTEFIELD')
        self.assertEqual(tags(element), ['BIT-LENGTH'])

    def test_param_length_info_type_refers_to_owner(self):
        length_key = {'short_name': 'LEN', 'unique_object_id': 'P-7'}
        structure = {'short_name': 'S1', 'parameters': [
            {'short_name': 'OTHER', 'unique_object_id': 'P-6'}, length_key]}
        ctx = context({'DOP_L_S1': ('MCD_DB_PARAMETER_STRUCTURE', structure)})
        self.assertEqual(data_objects.length_key_owners(ctx), {'P-6': 'DOP_L_S1', 'P-7': 'DOP_L_S1'})
        element = data_objects.add_diag_coded_type(
            ctx, ET.Element('X'), coded_type(coded_type='ePARAM_LENGTH_INFO_TYPE',
                                             bit_mask=None, length_key_parameter=length_key),
            owner_id='S9')
        self.assertEqual(element.get(XSI_TYPE), 'PARAM-LENGTH-INFO-TYPE')
        self.assertEqual(xml(element.find('LENGTH-KEY-REF')), '<LENGTH-KEY-REF ID-REF="S1.LEN" />')

    def test_length_key_owners_cover_request_and_response_parameters(self):
        ctx = context({'REQ_L_Q1': ('MCD_DB_REQUEST', {'request_parameters': [
                           {'short_name': 'A', 'unique_object_id': 'P-1'}, None]}),
                       'RSP_L_R1': ('MCD_DB_RESPONSE', {'response_parameters': [
                           {'short_name': 'B', 'unique_object_id': 'P-2'}]}),
                       'DOP_L_E1': ('MCD_DB_PARAMETER_ENV_DATA', {'parameters': None})})
        self.assertEqual(data_objects.length_key_owners(ctx), {'P-1': 'REQ_L_Q1', 'P-2': 'RSP_L_R1'})

    def test_param_length_info_type_owner_without_naming_rule_keeps_its_key(self):
        length_key = {'short_name': 'LEN', 'unique_object_id': 'P-3'}
        ctx = context({'XYZ': ('MCD_DB_PARAMETER_STRUCTURE', {'parameters': [length_key]})})
        element = data_objects.add_diag_coded_type(
            ctx, ET.Element('X'), coded_type(coded_type='ePARAM_LENGTH_INFO_TYPE', bit_mask=None,
                                             length_key_parameter=length_key), owner_id='S9')
        self.assertEqual(xml(element.find('LENGTH-KEY-REF')), '<LENGTH-KEY-REF ID-REF="XYZ.LEN" />')

    def test_param_length_info_type_falls_back_to_given_owner(self):
        ctx = context({})
        element = data_objects.add_diag_coded_type(
            ctx, ET.Element('X'), coded_type(coded_type='ePARAM_LENGTH_INFO_TYPE', bit_mask=None,
                                             length_key_parameter={'short_name': 'LEN',
                                                                   'unique_object_id': 'P-9'}),
            owner_id='S9')
        self.assertEqual(element.find('LENGTH-KEY-REF').get('ID-REF'), 'S9.LEN')

    def test_param_length_info_type_without_owner_is_unresolvable(self):
        ctx = context({})
        element = data_objects.add_diag_coded_type(
            ctx, ET.Element('X'), coded_type(coded_type='ePARAM_LENGTH_INFO_TYPE', bit_mask=None,
                                             length_key_parameter={'short_name': 'LEN',
                                                                   'unique_object_id': 'P-9'}))
        self.assertEqual(element.find('LENGTH-KEY-REF').get('ID-REF'), 'LEN')
        self.assertEqual(ctx.report['unresolvable_references'], 1)


class CompuMethodTests(unittest.TestCase):
    def test_identical(self):
        ctx = context({})
        method = compu_method('eIDENTICAL')
        method['compu_internal_to_phys'] = None
        element = data_objects.add_compu_method(ctx, ET.Element('X'), method)
        self.assertEqual(xml(element), '<COMPU-METHOD><CATEGORY>IDENTICAL</CATEGORY></COMPU-METHOD>')

    def test_texttable_scale_omits_upper_equal_lower_and_uses_vt_by_physical_type(self):
        ctx = context({})
        scales = [scale(limit(1), limit(1), constant=value('On', 'eA_UNICODE2STRING'), long_name_id='TX1'),
                  scale(limit(2), limit(5), constant=value('Off', 'eA_UNICODE2STRING'))]
        text = data_objects.add_compu_method(ctx, ET.Element('X'), compu_method('eTEXTTAB', scales),
                                             'eDB_PHYS_UNICODE2STRING')
        self.assertEqual(text.findtext('CATEGORY'), 'TEXTTABLE')
        first, second = text.findall('COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE')
        self.assertEqual(xml(first), '<COMPU-SCALE><LOWER-LIMIT>1</LOWER-LIMIT>'
                                     '<COMPU-CONST><VT TI="TX1">On</VT></COMPU-CONST></COMPU-SCALE>')
        self.assertEqual(tags(second), ['LOWER-LIMIT', 'UPPER-LIMIT', 'COMPU-CONST'])
        self.assertEqual(second.findtext('UPPER-LIMIT'), '5')
        self.assertIsNone(second.find('COMPU-CONST/VT').get('TI'))
        numbers = data_objects.add_compu_method(
            ctx, ET.Element('X'),
            compu_method('eTEXTTAB', [scale(limit(1), limit(1), constant=value(7.0, 'eA_FLOAT64'))]),
            'eDB_PHYS_UINT32')
        self.assertEqual(numbers.findtext('COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE/COMPU-CONST/V'), '7')

    def test_compu_inverse_value_is_written_outside_tab_intp(self):
        ctx = context({})
        element = data_objects.add_compu_method(
            ctx, ET.Element('X'),
            compu_method('eTEXTTAB', [scale(limit(1), limit(1), constant=value('On', 'eA_UNICODE2STRING'),
                                            inverse=value(1))]),
            'eDB_PHYS_UNICODE2STRING')
        compu_scale = element.find('COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE')
        self.assertEqual(tags(compu_scale), ['LOWER-LIMIT', 'COMPU-INVERSE-VALUE', 'COMPU-CONST'])
        self.assertEqual(xml(compu_scale.find('COMPU-INVERSE-VALUE')),
                         '<COMPU-INVERSE-VALUE><V>1</V></COMPU-INVERSE-VALUE>')

    def test_tab_intp_drops_open_upper_and_inverse_value(self):
        ctx = context({})
        scales = [scale(limit(0), limit(10, 'eLIMIT_OPEN'), constant=value(0.0, 'eA_FLOAT64'), inverse=value(0)),
                  scale(limit(10), limit(20), constant=value(2.5, 'eA_FLOAT64'))]
        element = data_objects.add_compu_method(ctx, ET.Element('X'), compu_method('eTAB_INTP', scales),
                                                'eDB_PHYS_FLOAT64')
        self.assertEqual(element.findtext('CATEGORY'), 'TAB-INTP')
        first, second = element.findall('COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE')
        self.assertEqual(tags(first), ['LOWER-LIMIT', 'COMPU-CONST'])
        self.assertEqual(tags(second), ['LOWER-LIMIT', 'UPPER-LIMIT', 'COMPU-CONST'])
        self.assertEqual(second.findtext('COMPU-CONST/V'), '2.5')

    def test_tab_intp_scale_omits_upper_equal_lower(self):
        ctx = context({})
        scales = [scale(limit(0), limit(65535), constant=value(0.0, 'eA_FLOAT64')),
                  scale(limit(65535), limit(65535), constant=value(100.0, 'eA_FLOAT64'))]
        element = data_objects.add_compu_method(ctx, ET.Element('X'), compu_method('eTAB_INTP', scales),
                                                'eDB_PHYS_FLOAT64')
        first, last = element.findall('COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE')
        self.assertEqual(tags(first), ['LOWER-LIMIT', 'UPPER-LIMIT', 'COMPU-CONST'])
        self.assertEqual(tags(last), ['LOWER-LIMIT', 'COMPU-CONST'])
        self.assertEqual(last.findtext('LOWER-LIMIT'), '65535')

    def test_linear_drops_infinite_limits_and_writes_rational_coeffs_from_coded_values(self):
        ctx = context({})
        coeffs = {'numerator': [0.0, 0.5], 'denominator': [1.0]}
        scales = [scale(limit(None, 'eLIMIT_INFINITE'), limit(None, 'eLIMIT_INFINITE'), coeffs=coeffs,
                        plain_coeffs={'numerator': [9.0, 9.0], 'denominator': [9.0]})]
        element = data_objects.add_compu_method(ctx, ET.Element('X'), compu_method('eLINEAR', scales),
                                                'eDB_PHYS_FLOAT64')
        self.assertEqual(element.findtext('CATEGORY'), 'LINEAR')
        compu_scale = element.find('COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE')
        self.assertEqual(xml(compu_scale),
                         '<COMPU-SCALE><COMPU-RATIONAL-COEFFS>'
                         '<COMPU-NUMERATOR><V>0</V><V>0.5</V></COMPU-NUMERATOR>'
                         '<COMPU-DENOMINATOR><V>1</V></COMPU-DENOMINATOR>'
                         '</COMPU-RATIONAL-COEFFS></COMPU-SCALE>')

    def test_open_lower_limit_keeps_interval_type(self):
        ctx = context({})
        scales = [scale(limit(3, 'eLIMIT_OPEN'), limit(None, 'eLIMIT_INFINITE'),
                        coeffs={'numerator': [1.0], 'denominator': []})]
        element = data_objects.add_compu_method(ctx, ET.Element('X'), compu_method('eLINEAR', scales))
        compu_scale = element.find('COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE')
        self.assertEqual(xml(compu_scale.find('LOWER-LIMIT')), '<LOWER-LIMIT INTERVAL-TYPE="OPEN">3</LOWER-LIMIT>')
        self.assertEqual(tags(compu_scale.find('COMPU-RATIONAL-COEFFS')), ['COMPU-NUMERATOR'])

    def test_compu_default_value(self):
        ctx = context({})
        scales = [scale(limit(1), limit(1), constant=value('On', 'eA_UNICODE2STRING'))]
        element = data_objects.add_compu_method(
            ctx, ET.Element('X'),
            compu_method('eTEXTTAB', scales, default=value('n/a', 'eA_UNICODE2STRING'), default_id='TXD'),
            'eDB_PHYS_UNICODE2STRING')
        internal_to_phys = element.find('COMPU-INTERNAL-TO-PHYS')
        self.assertEqual(tags(internal_to_phys), ['COMPU-SCALES', 'COMPU-DEFAULT-VALUE'])
        self.assertEqual(xml(internal_to_phys.find('COMPU-DEFAULT-VALUE')),
                         '<COMPU-DEFAULT-VALUE><VT TI="TXD">n/a</VT></COMPU-DEFAULT-VALUE>')

    def test_unknown_category_is_not_written(self):
        ctx = context({})
        method = compu_method(17)
        method['compu_internal_to_phys'] = None
        element = data_objects.add_compu_method(ctx, ET.Element('X'), method)
        self.assertEqual(xml(element), '<COMPU-METHOD />')
        self.assertEqual(ctx.report['unmapped_enumerations'], 1)


    def test_string_values_use_vt_without_physical_base_type(self):
        ctx = context({})
        scales = [scale(limit(1), limit(1), constant=value('An', 'eA_ASCIISTRING'),
                        inverse=value('x', 'eA_ASCIISTRING')),
                  scale(limit(2), limit(2), constant=value('Aus', 'eA_UNICODE2STRING')),
                  scale(limit(3), limit(3), constant=value(3))]
        element = data_objects.add_compu_method(ctx, ET.Element('X'), compu_method('eTEXTTAB', scales))
        first, second, third = element.findall('COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE')
        self.assertEqual(first.findtext('COMPU-CONST/VT'), 'An')
        self.assertEqual(first.findtext('COMPU-INVERSE-VALUE/VT'), 'x')
        self.assertEqual(second.findtext('COMPU-CONST/VT'), 'Aus')
        self.assertEqual(third.findtext('COMPU-CONST/V'), '3')

    def test_inverse_value_tag_follows_its_data_type(self):
        # The inverse value is an internal value; the physical base type does not describe it.
        ctx = context({})
        scales = [scale(limit(1), limit(1), constant=value('On', 'eA_UNICODE2STRING'), inverse=value(1)),
                  scale(limit(2), limit(2), constant=value('Off', 'eA_UNICODE2STRING'),
                        inverse=value('y', 'eA_UNICODE2STRING'))]
        element = data_objects.add_compu_method(ctx, ET.Element('X'), compu_method('eTEXTTAB', scales),
                                                'eDB_PHYS_UNICODE2STRING')
        first, second = element.findall('COMPU-INTERNAL-TO-PHYS/COMPU-SCALES/COMPU-SCALE')
        self.assertEqual(first.findtext('COMPU-INVERSE-VALUE/V'), '1')
        self.assertEqual(second.findtext('COMPU-INVERSE-VALUE/VT'), 'y')


class PhysicalTypeTests(unittest.TestCase):
    def test_physical_type_writes_dec_radix_for_uint32_only(self):
        ctx = context({})
        parent = ET.Element('X')
        decimal = data_objects.add_physical_type(ctx, parent, physical_type(radix=10))
        self.assertEqual(xml(decimal), '<PHYSICAL-TYPE BASE-DATA-TYPE="A_UINT32" DISPLAY-RADIX="DEC" />')
        self.assertEqual(len(decimal), 0)

    def test_physical_type_leaves_out_dec_radix_for_other_data_types(self):
        ctx = context({})
        parent = ET.Element('X')
        plain = data_objects.add_physical_type(ctx, parent, physical_type('eDB_PHYS_INT32', 10))
        self.assertNotIn('DISPLAY-RADIX', plain.attrib)
        self.assertEqual(len(plain), 0)
        precise = data_objects.add_physical_type(ctx, parent, physical_type('eDB_PHYS_INT32', 10, 2))
        self.assertNotIn('DISPLAY-RADIX', precise.attrib)
        self.assertEqual([child.tag for child in precise], ['PRECISION'])

    def test_physical_type_keeps_other_radixes_for_any_data_type(self):
        ctx = context({})
        hexadecimal = data_objects.add_physical_type(ctx, ET.Element('X'), physical_type('eDB_PHYS_FLOAT64', 16, 3))
        self.assertEqual(xml(hexadecimal), '<PHYSICAL-TYPE BASE-DATA-TYPE="A_FLOAT64" DISPLAY-RADIX="HEX">'
                                           '<PRECISION>3</PRECISION></PHYSICAL-TYPE>')


class ConstraintTests(unittest.TestCase):
    def test_empty_constraint_reference_writes_nothing(self):
        ctx = context({})
        parent = ET.Element('X')
        self.assertIsNone(data_objects.add_constraint(ctx, parent, 'INTERNAL-CONSTR', None))
        self.assertEqual(len(parent), 0)
        self.assertEqual(ctx.report['empty_references'], 0)

    def test_constraint_reference_with_empty_object_id_is_counted(self):
        ctx = context({})
        parent = ET.Element('X')
        self.assertIsNone(data_objects.add_constraint(ctx, parent, 'INTERNAL-CONSTR', reference('')))
        self.assertEqual(len(parent), 0)
        self.assertEqual(ctx.report['empty_references'], 1)

    def test_constraint_in_foreign_pool_is_unresolvable(self):
        # A constraint is embedded; ODX has no reference form for it, so no DOCREF/DOCTYPE is written.
        ctx = context({}, object_type=lambda pool, key: 'MCD_CONSTRAINT')
        parent = ET.Element('X')
        self.assertIsNone(data_objects.add_constraint(ctx, parent, 'INTERNAL-CONSTR',
                                                      reference('IC_N_C1', '5.4.0@N.sd')))
        self.assertEqual(len(parent), 0)
        self.assertEqual(ctx.report['unresolvable_references'], 1)

    def test_computed_constraint_is_dropped(self):
        ctx = context({'PC_L_C1': ('MCD_CONSTRAINT', constraint(computed=True))})
        parent = ET.Element('X')
        self.assertIsNone(data_objects.add_constraint(ctx, parent, 'PHYS-CONSTR', reference('PC_L_C1')))
        self.assertEqual(len(parent), 0)
        self.assertIn('PC_L_C1', ctx.used)

    def test_internal_constraint_full_range_with_scales_omits_limits(self):
        ctx = context({'IC_L_C1': ('MCD_CONSTRAINT', constraint(0, 4294967295,
                                                                [scale_constraint('Inv', 255, 255)]))})
        element = data_objects.add_constraint(ctx, ET.Element('X'), 'INTERNAL-CONSTR', reference('IC_L_C1'))
        self.assertEqual(tags(element), ['SCALE-CONSTRS'])
        self.assertIn('IC_L_C1', ctx.used)

    def test_full_range_without_scales_keeps_limits(self):
        ctx = context({'IC_L_C1': ('MCD_CONSTRAINT', constraint(0, 4294967295))})
        element = data_objects.add_constraint(ctx, ET.Element('X'), 'INTERNAL-CONSTR', reference('IC_L_C1'))
        self.assertEqual(xml(element), '<INTERNAL-CONSTR><LOWER-LIMIT>0</LOWER-LIMIT>'
                                       '<UPPER-LIMIT>4294967295</UPPER-LIMIT></INTERNAL-CONSTR>')

    def test_scale_constraint_validity_label_and_limits(self):
        ctx = context({'IC_L_C1': ('MCD_CONSTRAINT', constraint(0, 254, [
            scale_constraint('Inv', 255, 300, 'eVALUE_NOT_VALID', upper_type='eLIMIT_OPEN')]))})
        element = data_objects.add_constraint(ctx, ET.Element('X'), 'INTERNAL-CONSTR', reference('IC_L_C1'))
        self.assertEqual(tags(element), ['LOWER-LIMIT', 'UPPER-LIMIT', 'SCALE-CONSTRS'])
        self.assertEqual(xml(element.find('SCALE-CONSTRS/SCALE-CONSTR')),
                         '<SCALE-CONSTR VALIDITY="NOT-VALID"><SHORT-LABEL TI="Inv_TI">Inv</SHORT-LABEL>'
                         '<LOWER-LIMIT>255</LOWER-LIMIT>'
                         '<UPPER-LIMIT INTERVAL-TYPE="OPEN">300</UPPER-LIMIT></SCALE-CONSTR>')

    def test_closed_interval_type_is_omitted(self):
        ctx = context({'IC_L_C1': ('MCD_CONSTRAINT', constraint(1, 9, lower_type='eLIMIT_CLOSED',
                                                                upper_type='eLIMIT_OPEN'))})
        element = data_objects.add_constraint(ctx, ET.Element('X'), 'INTERNAL-CONSTR', reference('IC_L_C1'))
        self.assertNotIn('INTERVAL-TYPE', element.find('LOWER-LIMIT').attrib)
        self.assertEqual(element.find('UPPER-LIMIT').get('INTERVAL-TYPE'), 'OPEN')

    def test_missing_constraint_is_unresolvable(self):
        ctx = context({})
        parent = ET.Element('X')
        self.assertIsNone(data_objects.add_constraint(ctx, parent, 'INTERNAL-CONSTR', reference('IC_L_C9')))
        self.assertEqual(len(parent), 0)
        self.assertEqual(ctx.report['unresolvable_references'], 1)


class DataObjectPropTests(unittest.TestCase):
    def test_data_object_prop_order(self):
        dop = {'short_name': 'Speed', 'compu_method': compu_method('eIDENTICAL'),
               'diag_coded_type': coded_type(), 'physical_type': physical_type(radix=16),
               'physical_to_coded_index_map': [], 'coded_to_physical_index_map': [],
               'unit_reference': reference('UNIT_L_U1'),
               'internal_constraint_reference': reference('IC_L_C1'),
               'physical_constraint_reference': reference('PC_L_C2')}
        ctx = context({'DOP_L_D1': ('DB_DOP_SIMPLE_BASE', dop),
                       'IC_L_C1': ('MCD_CONSTRAINT', constraint()),
                       'PC_L_C2': ('MCD_CONSTRAINT', constraint(computed=True)),
                       'UNIT_L_U1': ('MCD_DB_UNIT', unit('km', 'U-1'))})
        element = data_objects.add_data_object_prop(ctx, ET.Element('X'), 'DOP_L_D1')
        self.assertEqual(element.tag, 'DATA-OBJECT-PROP')
        self.assertEqual(element.attrib, {'ID': 'D1'})
        self.assertEqual(tags(element), ['SHORT-NAME', 'COMPU-METHOD', 'DIAG-CODED-TYPE', 'PHYSICAL-TYPE',
                                         'INTERNAL-CONSTR', 'UNIT-REF'])
        self.assertEqual(element.findtext('SHORT-NAME'), 'Speed')
        self.assertEqual(xml(element.find('UNIT-REF')), '<UNIT-REF ID-REF="U1" />')
        self.assertEqual(ctx.used, {'DOP_L_D1', 'IC_L_C1', 'PC_L_C2'})

    def test_data_object_prop_keeps_coded_type_range_next_to_scale_constraints(self):
        # The original documents mostly carry the full range of the coded type next to scale constraints.
        dop = {'short_name': 'Speed', 'compu_method': compu_method('eIDENTICAL'),
               'diag_coded_type': coded_type(bit_length=16), 'physical_type': physical_type(radix=16),
               'physical_to_coded_index_map': [], 'coded_to_physical_index_map': [],
               'unit_reference': None, 'internal_constraint_reference': reference('IC_L_C1'),
               'physical_constraint_reference': None}
        ctx = context({'DOP_L_D1': ('DB_DOP_SIMPLE_BASE', dop),
                       'IC_L_C1': ('MCD_CONSTRAINT', constraint(0, 65535, [scale_constraint('Inv', 255, 255)]))})
        element = data_objects.add_data_object_prop(ctx, ET.Element('X'), 'DOP_L_D1')
        self.assertEqual(tags(element.find('INTERNAL-CONSTR')), ['LOWER-LIMIT', 'UPPER-LIMIT', 'SCALE-CONSTRS'])
        self.assertEqual(element.findtext('INTERNAL-CONSTR/UPPER-LIMIT'), '65535')

    def test_data_object_prop_with_physical_constraint(self):
        dop = {'short_name': 'Temp', 'compu_method': compu_method('eIDENTICAL'),
               'diag_coded_type': coded_type(), 'physical_type': physical_type(radix=16),
               'unit_reference': None, 'internal_constraint_reference': None,
               'physical_constraint_reference': reference('PC_L_C2')}
        ctx = context({'DOP_L_D2': ('DB_DOP_SIMPLE_BASE', dop),
                       'PC_L_C2': ('MCD_CONSTRAINT', constraint(1, 9))})
        element = data_objects.add_data_object_prop(ctx, ET.Element('X'), 'DOP_L_D2')
        self.assertEqual(tags(element), ['SHORT-NAME', 'COMPU-METHOD', 'DIAG-CODED-TYPE', 'PHYSICAL-TYPE',
                                         'PHYS-CONSTR'])
        self.assertEqual(ctx.report['empty_references'], 0)

    def test_data_object_prop_sdgs_come_before_the_compu_method(self):
        def fake_sdgs(ctx, parent, obj):
            return ET.SubElement(parent, 'SDGS')

        dop = {'short_name': 'Temp', 'compu_method': compu_method('eIDENTICAL'),
               'diag_coded_type': coded_type(), 'physical_type': physical_type(radix=16),
               'unit_reference': None, 'internal_constraint_reference': None,
               'physical_constraint_reference': None}
        ctx = context({'DOP_L_D3': ('DB_DOP_SIMPLE_BASE', dop)})
        with mock.patch('odx_export.special_data.sdgs', fake_sdgs):
            element = data_objects.add_data_object_prop(ctx, ET.Element('X'), 'DOP_L_D3')
        self.assertEqual(tags(element), ['SHORT-NAME', 'SDGS', 'COMPU-METHOD', 'DIAG-CODED-TYPE',
                                         'PHYSICAL-TYPE'])


class UnitSpecTests(unittest.TestCase):
    def test_unit_spec_groups_units_dimensions(self):
        voltage = dimension('PD-1', 'Voltage', length_exponent=2, mass_exponent=1, time_exponent=-3,
                            current_exponent=-1)
        group = {'short_name': 'Metric', 'long_name': None, 'description': None,
                 'unique_object_id': 'G-1', 'long_name_id': None, 'description_id': None,
                 'category': 'eCOUNTRY', 'unit_references': [{'name': 'mV', 'reference': reference('UNIT_L_U1')}]}
        ctx = context({'UNIT_L_U1': ('MCD_DB_UNIT', unit('mV', 'U-1', voltage)),
                       'UNIT_L_U2': ('MCD_DB_UNIT', unit('V', 'U-2', dict(voltage))),
                       'UNITGR_1': ('MCD_DB_UNIT_GROUP', group)})
        layer_data = {'unit_group_references': [{'map_key': 'Metric', 'reference': reference('UNITGR_1')}],
                      'unit_references': [{'map_key': 'V', 'reference': reference('UNIT_L_U2')}]}
        element = data_objects.add_unit_spec(ctx, ET.Element('X'), layer_data)
        self.assertEqual(tags(element), ['UNIT-GROUPS', 'UNITS', 'PHYSICAL-DIMENSIONS'])
        self.assertEqual(xml(element.find('UNIT-GROUPS')),
                         '<UNIT-GROUPS><UNIT-GROUP OID="G-1"><SHORT-NAME>Metric</SHORT-NAME>'
                         '<CATEGORY>COUNTRY</CATEGORY><UNIT-REFS><UNIT-REF ID-REF="U1" /></UNIT-REFS>'
                         '</UNIT-GROUP></UNIT-GROUPS>')
        first, second = element.findall('UNITS/UNIT')
        self.assertEqual(xml(first),
                         '<UNIT ID="U2" OID="U-2"><SHORT-NAME>V</SHORT-NAME><DISPLAY-NAME>v</DISPLAY-NAME>'
                         '<FACTOR-SI-TO-UNIT>1000</FACTOR-SI-TO-UNIT><OFFSET-SI-TO-UNIT>0.5</OFFSET-SI-TO-UNIT>'
                         '<PHYSICAL-DIMENSION-REF ID-REF="Voltage" /></UNIT>')
        self.assertEqual(second.get('ID'), 'U1')
        self.assertEqual(xml(element.find('PHYSICAL-DIMENSIONS')),
                         '<PHYSICAL-DIMENSIONS><PHYSICAL-DIMENSION ID="Voltage" OID="PD-1">'
                         '<SHORT-NAME>Voltage</SHORT-NAME><LENGTH-EXP>2</LENGTH-EXP><MASS-EXP>1</MASS-EXP>'
                         '<TIME-EXP>-3</TIME-EXP><CURRENT-EXP>-1</CURRENT-EXP>'
                         '</PHYSICAL-DIMENSION></PHYSICAL-DIMENSIONS>')
        self.assertEqual(ctx.used, {'UNIT_L_U1', 'UNIT_L_U2', 'UNITGR_1'})

    def test_unit_without_dimension(self):
        ctx = context({'UNIT_L_U1': ('MCD_DB_UNIT', unit('rpm', 'U-1'))})
        element = data_objects.add_unit_spec(ctx, ET.Element('X'), {'unit_group_references': [],
                                                                    'unit_references': []})
        self.assertEqual(tags(element), ['UNITS'])
        self.assertIsNone(element.find('UNITS/UNIT/PHYSICAL-DIMENSION-REF'))

    def test_unit_groups_need_a_written_group(self):
        ctx = context({'UNIT_L_U1': ('MCD_DB_UNIT', unit('rpm', 'U-1'))})
        layer_data = {'unit_group_references': [{'map_key': 'A', 'reference': reference('')},
                                                {'map_key': 'B', 'reference': reference('UNITGR_9')}],
                      'unit_references': []}
        element = data_objects.add_unit_spec(ctx, ET.Element('X'), layer_data)
        self.assertEqual(tags(element), ['UNITS'])
        self.assertEqual(ctx.report['empty_references'], 1)
        self.assertEqual(ctx.report['unresolvable_references'], 1)

    def test_no_written_group_and_no_units_no_unit_spec(self):
        ctx = context({})
        parent = ET.Element('X')
        self.assertIsNone(data_objects.add_unit_spec(
            ctx, parent, {'unit_group_references': [{'map_key': 'B', 'reference': reference('UNITGR_9')}]}))
        self.assertEqual(len(parent), 0)

    def test_no_units_no_unit_spec(self):
        ctx = context({})
        parent = ET.Element('X')
        self.assertIsNone(data_objects.add_unit_spec(ctx, parent, {}))
        self.assertEqual(len(parent), 0)


if __name__ == '__main__':
    unittest.main()
