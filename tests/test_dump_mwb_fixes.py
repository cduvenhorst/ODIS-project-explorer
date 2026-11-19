import copy
import unittest

import dumpMWB
from tests.script_support import FakeObjectLoader

REFERENCE = {'pool_id': 'POOL', 'object_id': 'object'}


def uint(number):
    return {'data_type': 'eA_UINT32', 'value': number}


def coded_type(base='eA_UINT32'):
    return {'is_condensed_bit_mask': False, 'base_data_type_as_mcd_data_type': base,
            'coded_type': 'eSTANDARD_LENGTH_TYPE', 'bit_length': 8, 'bit_mask': bytearray(),
            'encoding': 'eNONE', 'is_high_low_byte_order': True}


def physical_type(base='eA_UINT32'):
    return {'base_data_type_as_mcd_data_type': base, 'display_radix': 10,
            'is_precision_available': False}


def identical():
    return {'compu_category': 'eIDENTICAL', 'compu_internal_to_phys': None,
            'compu_phys_to_internal': None}


def simple_dop(**fields):
    dop = {'#OBJECT_TYPE': 'DB_DOP_SIMPLE_BASE', 'diag_coded_type': coded_type(),
           'physical_type': physical_type(), 'compu_method': identical()}
    dop.update(fields)
    return dop


def interval(lower, upper):
    return {'lower_limit': lower, 'upper_limit': upper,
            'lower_limit_interval_type': 'eLIMIT_CLOSED',
            'upper_limit_interval_type': 'eLIMIT_CLOSED'}


def constraint(limits, scale_constraints=None):
    return {'is_computed': False, 'interval': limits,
            'scale_constraints': [] if scale_constraints is None else scale_constraints}


def parse(dop, objects=None):
    loader = FakeObjectLoader(objects or {})
    return dumpMWB.parse_dop(loader, [], 'project', copy.deepcopy(dop))


def parse_with_constraint(constraint_object):
    return parse(simple_dop(internal_constraint_reference=REFERENCE),
                 {('POOL', 'object'): constraint_object})


def parameter(**fields):
    dop = {'#OBJECT_TYPE': 'MCD_DB_PARAMETER', 'long_name': None, 'long_name_id': None,
           'description': None, 'is_byte_position_available': True, 'byte_position': 0,
           'bit_position': 0, 'mcd_parameter_type': 'eNRC_CONST', 'dop_base_reference': None,
           'diag_coded_type': coded_type(), 'nrc_constant_values': [uint(0x11), uint(0x31)]}
    dop.update(fields)
    return dop


def dtc_dop():
    dop = {'#OBJECT_TYPE': 'DB_DOP_DTC', 'diag_coded_type': coded_type(),
           'physical_type': physical_type(), 'compu_method': identical(),
           'short_name': 'DTC', 'long_name': None,
           'diag_trouble_code_references': [{'reference': REFERENCE, 'map_key': 1}]}
    dop['diag_coded_type']['bit_length'] = 24
    return dop


class CompuCategoryTest(unittest.TestCase):
    def test_texttable_has_no_calculation_type(self):
        text_scale = {'lower_limit_as_coded_value': {'limit_type': 'eLIMIT_CLOSED', 'limit': uint(1)},
                      'upper_limit_as_coded_value': {'limit_type': 'eLIMIT_CLOSED', 'limit': uint(1)},
                      'compu_constant': {'data_type': 'eA_UNICODE2STRING', 'value': 'on'},
                      'long_name_id': None}
        compu_method = {'compu_category': 'eTEXTTAB', 'compu_phys_to_internal': None,
                        'compu_internal_to_phys': {'compu_scales': [text_scale],
                                                   'compu_default_value': None}}
        result = parse(simple_dop(physical_type=physical_type('eA_UNICODE2STRING'),
                                  compu_method=compu_method))
        self.assertEqual(result['compu_category'], 'TEXTTABLE')
        self.assertIsNone(result['calculation_type'])

    def test_linear_compu_keeps_calculation_type_a_int32(self):
        scale = {'lower_limit_as_coded_value': None, 'upper_limit_as_coded_value': None,
                 'lower_limit': None, 'upper_limit': None,
                 'compu_rational_coeffs_as_coded_values': {'numerator': [0, 2], 'denominator': []}}
        compu_method = {'compu_category': 'eLINEAR', 'compu_phys_to_internal': None,
                        'compu_internal_to_phys': {'compu_scales': [scale]}}
        result = parse(simple_dop(physical_type=physical_type('eA_INT32'),
                                  compu_method=compu_method))
        self.assertEqual(result['compu_category'], 'LINEAR')
        self.assertEqual(result['calculation_type'], 'A_INT32')


class ConstraintLimitTest(unittest.TestCase):
    def test_internal_constraint_with_mismatching_upper_limit_type_raises(self):
        limits = interval(uint(1), {'data_type': 'eA_INT32', 'value': 2})
        with self.assertRaisesRegex(RuntimeError, 'IC limit data types'):
            parse_with_constraint(constraint(limits))

    def test_scale_constraint_with_mismatching_upper_limit_type_raises(self):
        scale_constraint = {'interval': interval(uint(1), {'data_type': 'eA_INT32', 'value': 2})}
        with self.assertRaisesRegex(RuntimeError, 'IC SCALE-CONSTR limit data types'):
            parse_with_constraint(constraint(interval(uint(1), uint(2)), [scale_constraint]))


class BaseDataTypeTest(unittest.TestCase):
    def test_unknown_base_data_type_raises_runtime_error(self):
        with self.assertRaisesRegex(RuntimeError, 'Strange BASE-DATA-TYPE: None'):
            parse(simple_dop(diag_coded_type=coded_type(base=None)))

    def test_unknown_physical_base_data_type_raises_runtime_error(self):
        with self.assertRaisesRegex(RuntimeError, 'Strange PHYSICAL-TYPE BASE-DATA-TYPE: None'):
            parse(simple_dop(physical_type=physical_type(base=None)))


class NrcConstTest(unittest.TestCase):
    def test_nrc_const_parameter(self):
        result = parse(parameter())
        self.assertEqual(result['parameter_type'], 'NRC-CONST')
        self.assertEqual(result['constants'], [{'data_type': 'A_UINT32', 'value': 0x11},
                                               {'data_type': 'A_UINT32', 'value': 0x31}])
        self.assertEqual(result['dop']['type'], 'DOP')
        self.assertEqual(result['dop']['coded_base_data_type'], 'A_UINT32')

    def test_nrc_const_without_values_has_no_constants(self):
        self.assertEqual(parse(parameter(nrc_constant_values=None))['constants'], [])

    def test_nrc_const_referencing_dop_raises(self):
        with self.assertRaisesRegex(RuntimeError, 'NRC-CONST references DOP'):
            parse(parameter(dop_base_reference=REFERENCE))


class DtcDopTest(unittest.TestCase):
    def test_dtc_coded_type_error_message(self):
        dop = dtc_dop()
        dop['diag_coded_type']['coded_type'] = 'eMIN_MAX_LENGTH_TYPE'
        with self.assertRaisesRegex(RuntimeError, 'DTC DIAG-CODED-TYPE must be STANDARD-LENGTH-TYPE, not eMIN_MAX_LENGTH_TYPE'):
            parse(dop)

    def test_trouble_code_mismatch_raises_runtime_error(self):
        dtc = {'#OBJECT_TYPE': 'MCD_DB_DIAG_TROUBLE_CODE', 'trouble_code': 2}
        with self.assertRaisesRegex(RuntimeError, 'Trouble code 2 does not match map key 1'):
            parse(dtc_dop(), {('POOL', 'object'): dtc})


if __name__ == '__main__':
    unittest.main()
