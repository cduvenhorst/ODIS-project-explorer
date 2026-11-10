"""Protection tests for the current (VW) layouts of the computation, DOP and unit loaders.

Every body is built exactly as the loader reads it today and the complete result is
asserted, in strict mode.  Branches in which the loaders raise today are not pinned.
The three identifiers of the unit, unit group and physical dimension loaders follow the
kernel: they appear as the keys unique_object_id, long_name_id and description_id (None
when empty) instead of being required empty.
The parameter embedded in the length information type follows the kernel names: description_id
(formerly some_id) and the always present key dop_base (None without flag 1 << 4).
The DTC DOP loader follows the kernel: the second counter introduces the collection
linked_dtc_dops instead of having to be 0, and unique_object_identifier is named
unique_object_id.
"""
import unittest

from tests import support
from tests.support import (ObjectBytes, concat, CLOSED, INFINITE, OPEN, case, case_base_body,
                           case_body, diag_coded_type, diag_coded_type_body, limit, limit_body,
                           uint, uint_value)


def load(type_name, body):
    return support.load(type_name, body)


def no_value(body):
    """MCD value of type eNO_TYPE (loads as None)."""
    return body.u8(0xFF)


def coeffs_body():
    return ObjectBytes().u8(1).double(2.5).u8(1).double(4.0)


def coeffs():
    return {'#OBJECT_TYPE': 'DB_COMPU_RATIONAL_COEFFS', 'numerator': [2.5], 'denominator': [4.0]}


def scale_body():
    """Minimal DB_COMPU_SCALE: everything optional is off."""
    body = ObjectBytes().ascii(None).absent().absent().absent().absent()
    no_value(body)
    no_value(body)
    no_value(body)
    return body.absent().absent()


def scale():
    return {'#OBJECT_TYPE': 'DB_COMPU_SCALE', 'long_name_id': None,
            'compu_inverse_rational_coeffs': None, 'compu_rational_coeffs': None,
            'lower_limit': None, 'upper_limit': None, 'compu_const': None,
            'compu_inverse_value': None, 'compu_const_as_coded_value': None,
            'lower_limit_as_coded_value': None, 'upper_limit_as_coded_value': None}


def compu_base_body(default=None, inverse=None):
    body = ObjectBytes().absent()
    no_value(body) if default is None else uint_value(body, default)
    no_value(body)
    body.absent()
    no_value(body) if inverse is None else uint_value(body, inverse)
    return body


def compu_base(default=None, inverse=None):
    return {'#OBJECT_TYPE': 'DB_COMPU_BASE', 'compu_scales': None,
            'compu_default_value': None if default is None else uint(default),
            'compu_code_byte_stream': None, 'code_information': None,
            'compu_inverse_value': None if inverse is None else uint(inverse)}


def compu_method_body():
    return ObjectBytes().u8(0).absent().absent()


def compu_method():
    return {'#OBJECT_TYPE': 'DB_COMPU_METHOD', 'compu_category': 'eIDENTICAL',
            'compu_phys_to_internal': None, 'compu_internal_to_phys': None}


def physical_type_body():
    return ObjectBytes().u8(0).flag(False).u8(10)


def physical_type():
    return {'#OBJECT_TYPE': 'DB_PHYSICAL_TYPE', 'base_data_type': 'eDB_INT32',
            'base_data_type_as_mcd_data_type': 'eA_INT32', 'is_precision_available': False,
            'display_radix': 10}


def interval_body(lower=None, upper=None, flags=0):
    body = ObjectBytes()
    no_value(body) if lower is None else uint_value(body, lower)
    no_value(body) if upper is None else uint_value(body, upper)
    return body.u8(flags)


def interval(lower=None, upper=None, lower_type='eLIMIT_OPEN', upper_type='eLIMIT_OPEN'):
    return {'#OBJECT_TYPE': 'MCD_INTERVAL',
            'lower_limit': None if lower is None else uint(lower),
            'upper_limit': None if upper is None else uint(upper),
            'lower_limit_type': lower_type, 'upper_limit_type': upper_type}


def scale_constraint_body(range_info=2):
    return (ObjectBytes().absent().u8(range_info).unicode(None).ascii(None).ascii(None)
            .ascii(None).flag(False))


def scale_constraint(range_info='eVALUE_VALID'):
    return {'#OBJECT_TYPE': 'MCD_SCALE_CONSTRAINT', 'interval': None, 'range_info': range_info,
            'description': None, 'description_id': None, 'short_label': None,
            'short_label_id': None, 'is_computed': False}


def dimension_body():
    body = ObjectBytes().ascii('Length').unicode(None).unicode(None).ascii(None).ascii(None)
    return body.ascii(None).i32(1).i32(0).i32(0).i32(0).i32(0).i32(0).i32(0)


def dimension():
    return {'#OBJECT_TYPE': 'MCD_DB_PHYSICAL_DIMENSION', 'short_name': 'Length',
            'long_name': None, 'description': None, 'unique_object_id': None,
            'long_name_id': None, 'description_id': None, 'length_exponent': 1,
            'mass_exponent': 0,
            'time_exponent': 0, 'current_exponent': 0, 'temperature_exponent': 0,
            'molar_amount_exponent': 0, 'luminous_intensity_exponent': 0}


class CompuRationalCoeffsTests(unittest.TestCase):
    def test_db_compu_rational_coeffs_minimal(self):
        result = load('DB_COMPU_RATIONAL_COEFFS', ObjectBytes().u8(0).u8(0))
        self.assertEqual(result, {'#OBJECT_TYPE': 'DB_COMPU_RATIONAL_COEFFS',
                                  'numerator': [], 'denominator': []})

    def test_db_compu_rational_coeffs_all_branches(self):
        body = ObjectBytes().u8(2).double(1.5).double(-2.0).u8(2).double(4.0).double(0.25)
        result = load('DB_COMPU_RATIONAL_COEFFS', body)
        self.assertEqual(result, {'#OBJECT_TYPE': 'DB_COMPU_RATIONAL_COEFFS',
                                  'numerator': [1.5, -2.0], 'denominator': [4.0, 0.25]})


class LimitTests(unittest.TestCase):
    def test_db_limit_minimal(self):
        result = load('DB_LIMIT', no_value(ObjectBytes()).u8(OPEN))
        self.assertEqual(result, {'#OBJECT_TYPE': 'DB_LIMIT', 'mcd_value': None,
                                  'limit_type': 'eLIMIT_OPEN'})

    def test_db_limit_all_branches(self):
        body = ObjectBytes().u8(7).i32(-3).u8(INFINITE)
        self.assertEqual(load('DB_LIMIT', body),
                         {'#OBJECT_TYPE': 'DB_LIMIT',
                          'mcd_value': {'data_type': 'eA_INT32', 'value': -3},
                          'limit_type': 'eLIMIT_INFINITE'})

    def test_db_limit_closed(self):
        self.assertEqual(load('DB_LIMIT', limit_body(5, CLOSED)), limit(5, CLOSED))

    def test_db_limit_mcd_value_types(self):
        cases = [
            (ObjectBytes().u8(1).ascii('text'), {'data_type': 'eA_ASCIISTRING', 'value': 'text'}),
            (ObjectBytes().u8(14).unicode('Größe'),
             {'data_type': 'eA_UNICODE2STRING', 'value': 'Größe'}),
            (ObjectBytes().u8(4).raw(b'\x00\x00\xc0\x3f'), {'data_type': 'eA_FLOAT32', 'value': 1.5}),
            (ObjectBytes().u8(5).double(2.25), {'data_type': 'eA_FLOAT64', 'value': 2.25}),
            (ObjectBytes().u8(7).i32(-1), {'data_type': 'eA_INT32', 'value': -1}),
            (ObjectBytes().u8(11).u32(4000000000), {'data_type': 'eA_UINT32', 'value': 4000000000}),
            (ObjectBytes().u8(2).u8(1).u16(2).raw(b'\x0f\xf0'),
             {'data_type': 'eA_BITFIELD', 'value': b'\x0f\xf0'}),
            (ObjectBytes().u8(3).u8(0), {'data_type': 'eA_BYTEFIELD', 'value': b''}),
        ]
        for value_bytes, expected in cases:
            with self.subTest(data_type=expected['data_type']):
                body = concat(value_bytes, ObjectBytes().u8(CLOSED))
                self.assertEqual(load('DB_LIMIT', body),
                                 {'#OBJECT_TYPE': 'DB_LIMIT', 'mcd_value': expected,
                                  'limit_type': 'eLIMIT_CLOSED'})


class CompuScaleTests(unittest.TestCase):
    def test_db_compu_scale_minimal(self):
        self.assertEqual(load('DB_COMPU_SCALE', scale_body()), scale())

    def test_db_compu_scale_all_branches(self):
        body = ObjectBytes().ascii('LN')
        body.nested('DB_COMPU_RATIONAL_COEFFS', coeffs_body())
        body.nested('DB_COMPU_RATIONAL_COEFFS', coeffs_body())
        body.nested('DB_LIMIT', limit_body(1, CLOSED)).nested('DB_LIMIT', limit_body(2, OPEN))
        body.u8(1).ascii('const')
        uint_value(body, 7)
        body.u8(5).double(0.5)
        body.nested('DB_LIMIT', limit_body(3, OPEN)).nested('DB_LIMIT', limit_body(4, CLOSED))
        self.assertEqual(load('DB_COMPU_SCALE', body), {
            '#OBJECT_TYPE': 'DB_COMPU_SCALE', 'long_name_id': 'LN',
            'compu_inverse_rational_coeffs': coeffs(), 'compu_rational_coeffs': coeffs(),
            'lower_limit': limit(1, CLOSED), 'upper_limit': limit(2, OPEN),
            'compu_const': {'data_type': 'eA_ASCIISTRING', 'value': 'const'},
            'compu_inverse_value': uint(7),
            'compu_const_as_coded_value': {'data_type': 'eA_FLOAT64', 'value': 0.5},
            'lower_limit_as_coded_value': limit(3, OPEN),
            'upper_limit_as_coded_value': limit(4, CLOSED)})


class CompuScalesTests(unittest.TestCase):
    def test_db_compu_scales_minimal(self):
        self.assertEqual(load('DB_COMPU_SCALES', ObjectBytes().u32(0)), [])

    def test_db_compu_scales_all_branches(self):
        body = ObjectBytes().u32(2)
        body.nested('DB_COMPU_SCALE', scale_body()).nested('DB_COMPU_SCALE', scale_body())
        self.assertEqual(load('DB_COMPU_SCALES', body), [scale(), scale()])


class CompuBaseTests(unittest.TestCase):
    def test_db_compu_base_minimal(self):
        self.assertEqual(load('DB_COMPU_BASE', compu_base_body()), compu_base())

    def test_db_compu_base_all_branches(self):
        scales = ObjectBytes().u32(2)
        scales.nested('DB_COMPU_SCALE', scale_body()).nested('DB_COMPU_SCALE', scale_body())
        code = ObjectBytes().unicode('code.bin').unicode(None).unicode('syntax')
        code.unicode(None).unicode('entry').u16(0)
        body = ObjectBytes().nested('DB_COMPU_SCALES', scales)
        uint_value(body, 1)
        body.u8(3).u8(1).u16(2).raw(b'\x01\x02')
        body.nested('MCD_DB_CODE_INFORMATION', code)
        uint_value(body, 2)
        self.assertEqual(load('DB_COMPU_BASE', body), {
            '#OBJECT_TYPE': 'DB_COMPU_BASE',
            'compu_scales': [scale(), scale()],
            'compu_default_value': uint(1),
            'compu_code_byte_stream': {'data_type': 'eA_BYTEFIELD', 'value': b'\x01\x02'},
            'code_information': {'#OBJECT_TYPE': 'MCD_DB_CODE_INFORMATION',
                                 'code_file': 'code.bin', 'encryption': None,
                                 'syntax': 'syntax', 'revision': None,
                                 'entry_point': 'entry', 'library_refs': []},
            'compu_inverse_value': uint(2)})


class CompuMethodTests(unittest.TestCase):
    def test_db_compu_method_minimal(self):
        self.assertEqual(load('DB_COMPU_METHOD', compu_method_body()), compu_method())

    def test_db_compu_method_all_branches(self):
        body = ObjectBytes().u8(3)
        body.nested('DB_COMPU_BASE', compu_base_body(inverse=5))
        body.nested('DB_COMPU_BASE', compu_base_body(default=6))
        body.ascii('INV').ascii('DEF')
        self.assertEqual(load('DB_COMPU_METHOD', body), {
            '#OBJECT_TYPE': 'DB_COMPU_METHOD', 'compu_category': 'eTEXTTAB',
            'compu_phys_to_internal': compu_base(inverse=5),
            'compu_internal_to_phys': compu_base(default=6),
            'compu_inverse_val_id': 'INV', 'compu_default_val_id': 'DEF'})

    def test_db_compu_method_etexttab_without_values(self):
        body = ObjectBytes().u8(3)
        body.nested('DB_COMPU_BASE', compu_base_body()).nested('DB_COMPU_BASE', compu_base_body())
        self.assertEqual(load('DB_COMPU_METHOD', body), {
            '#OBJECT_TYPE': 'DB_COMPU_METHOD', 'compu_category': 'eTEXTTAB',
            'compu_phys_to_internal': compu_base(), 'compu_internal_to_phys': compu_base()})

    def test_db_compu_method_etexttab_inverse_value_only(self):
        body = ObjectBytes().u8(3)
        body.nested('DB_COMPU_BASE', compu_base_body(inverse=5)).absent().ascii('INV')
        self.assertEqual(load('DB_COMPU_METHOD', body), {
            '#OBJECT_TYPE': 'DB_COMPU_METHOD', 'compu_category': 'eTEXTTAB',
            'compu_phys_to_internal': compu_base(inverse=5), 'compu_internal_to_phys': None,
            'compu_inverse_val_id': 'INV'})

    def test_db_compu_method_etexttab_default_value_only(self):
        body = ObjectBytes().u8(3)
        body.absent().nested('DB_COMPU_BASE', compu_base_body(default=6)).ascii('DEF')
        self.assertEqual(load('DB_COMPU_METHOD', body), {
            '#OBJECT_TYPE': 'DB_COMPU_METHOD', 'compu_category': 'eTEXTTAB',
            'compu_phys_to_internal': None, 'compu_internal_to_phys': compu_base(default=6),
            'compu_default_val_id': 'DEF'})

    def test_db_compu_method_categories(self):
        names = ['eIDENTICAL', 'eLINEAR', 'eSCALE_LINEAR', 'eTEXTTAB', 'eCOMPUCODE',
                 'eTAB_INTP', 'eRAT_FUNC', 'eSCALE_RAT_FUNC']
        for code, name in enumerate(names):
            with self.subTest(category=name):
                result = load('DB_COMPU_METHOD', ObjectBytes().u8(code).absent().absent())
                self.assertEqual(result, {'#OBJECT_TYPE': 'DB_COMPU_METHOD', 'compu_category': name,
                                          'compu_phys_to_internal': None,
                                          'compu_internal_to_phys': None})


class CaseTests(unittest.TestCase):
    def test_db_case_minimal(self):
        self.assertEqual(load('DB_CASE', concat(case_body(), case_base_body())), case())

    def test_db_case_all_branches(self):
        body = concat(case_body(), case_base_body(structure_ref=True))
        self.assertEqual(load('DB_CASE', body),
                         case({'object_id': 'STRUCT', 'pool_id': 'POOL'}))


class DefaultCaseTests(unittest.TestCase):
    def test_db_default_case_minimal(self):
        self.assertEqual(load('DB_DEFAULT_CASE', case_base_body()),
                         case(type_name='DB_DEFAULT_CASE'))

    def test_db_default_case_all_branches(self):
        self.assertEqual(load('DB_DEFAULT_CASE', case_base_body(structure_ref=True)),
                         case({'object_id': 'STRUCT', 'pool_id': 'POOL'}, 'DB_DEFAULT_CASE'))


class CasesTests(unittest.TestCase):
    def test_db_cases_minimal(self):
        self.assertEqual(load('DB_CASES', ObjectBytes().u32(0)), [])

    def test_db_cases_all_branches(self):
        def one():
            return concat(case_body(), case_base_body())
        body = ObjectBytes().u32(2).nested('DB_CASE', one()).nested('DB_CASE', one())
        self.assertEqual(load('DB_CASES', body), [case(), case()])


class ComParamSpecTests(unittest.TestCase):
    def test_db_com_param_spec_minimal(self):
        self.assertEqual(load('DB_COM_PARAM_SPEC', ObjectBytes().u16(0)),
                         {'#OBJECT_TYPE': 'DB_COM_PARAM_SPEC', 'protocol_stack_map': []})

    def test_db_com_param_spec_all_branches(self):
        body = ObjectBytes().u16(2)
        body.ascii('STACK1').u16(2).ascii('R1').ascii('P1').ascii('R2').ascii('P2')
        body.ascii('STACK2').u16(0)
        self.assertEqual(load('DB_COM_PARAM_SPEC', body), {
            '#OBJECT_TYPE': 'DB_COM_PARAM_SPEC',
            'protocol_stack_map': [
                {'string': 'STACK1', 'request_parameters_refs': [
                    {'object_id': 'R1', 'pool_id': 'P1'}, {'object_id': 'R2', 'pool_id': 'P2'}]},
                {'string': 'STACK2', 'request_parameters_refs': []}]})


class DiagCodedTypeTests(unittest.TestCase):
    def test_db_diag_coded_type_minimal(self):
        self.assertEqual(load('DB_DIAG_CODED_TYPE', diag_coded_type_body()), diag_coded_type())

    def test_db_diag_coded_type_all_branches(self):
        parameter = ObjectBytes().unicode(None).unicode(None).ascii('LEN').ascii(None)
        parameter.ascii(None).ascii(None).u8(0).u32(0).u8(0).u32(0).ascii(None).u8(1).u8(0xFF)
        body = ObjectBytes().u8(3).u32(16).u8(1).u8(11).flag(True).flag(True)
        body.nested('MCD_DB_PARAMETER_SIMPLE', parameter)
        self.assertEqual(load('DB_DIAG_CODED_TYPE', body), {
            '#OBJECT_TYPE': 'DB_DIAG_CODED_TYPE', 'type': 'ePARAM_LENGTH_INFO_TYPE',
            'bit_length': 16, 'base_data_type': 'eDB_UINT32',
            'base_data_type_as_mcd_data_type': 'eA_UINT32', 'encoding': 'eNONE',
            'is_high_low_byte_order': True, 'is_condensed': True,
            'length_key_parameter': {
                '#OBJECT_TYPE': 'MCD_DB_PARAMETER_SIMPLE', 'description': None,
                'long_name': None, 'short_name': 'LEN', 'description_id': None,
                'long_name_id': None, 'unique_object_id': None, 'bit_position': 0,
                'byte_position': 0, 'default_mcd_value': None, 'display_level': 0,
                'semantic': None, 'sys_param': None, 'mcd_parameter_type': 'eVALUE',
                'layer_id': None, 'diag_coded_type': None, 'db_object_ref': None,
                'dop_base': None,
                'is_byte_pos_available': False, 'is_protocol_parameter': False,
                'special_data_group_refs': None, 'nrc_const_values': None}})

    def test_db_diag_coded_type_emin_max_length_type(self):
        body = ObjectBytes().u8(1).u32(10).u32(2).u8(1).u8(0).u8(3).flag(True).flag(False)
        self.assertEqual(load('DB_DIAG_CODED_TYPE', body), {
            '#OBJECT_TYPE': 'DB_DIAG_CODED_TYPE', 'type': 'eMIN_MAX_LENGTH_TYPE',
            'max_length': 10, 'min_length': 2, 'termination': 'eZERO',
            'base_data_type': 'eDB_INT32', 'base_data_type_as_mcd_data_type': 'eA_INT32',
            'encoding': 'e2C', 'is_high_low_byte_order': True, 'is_condensed': False})

    def test_db_diag_coded_type_estandard_length_type(self):
        body = ObjectBytes().u8(2).u32(12).u8(1).u32(2).raw(b'\x0f\xff').u8(0).u8(3)
        body.flag(False).flag(False)
        expected = diag_coded_type()
        expected.update({'type': 'eSTANDARD_LENGTH_TYPE', 'bit_length': 12, 'bit_mask': b'\x0f\xff'})
        self.assertEqual(load('DB_DIAG_CODED_TYPE', body), expected)

    def test_db_diag_coded_type_estandard_length_type_without_mask(self):
        body = ObjectBytes().u8(2).u32(12).u8(0).u8(0).u8(3).flag(False).flag(False)
        expected = diag_coded_type()
        expected.update({'type': 'eSTANDARD_LENGTH_TYPE', 'bit_length': 12, 'bit_mask': b''})
        self.assertEqual(load('DB_DIAG_CODED_TYPE', body), expected)

    def test_db_diag_coded_type_eparam_length_info_type_without_parameter(self):
        body = ObjectBytes().u8(3).u32(8).u8(0).u8(3).flag(False).flag(False).absent()
        expected = diag_coded_type()
        expected.update({'type': 'ePARAM_LENGTH_INFO_TYPE', 'length_key_parameter': None})
        self.assertEqual(load('DB_DIAG_CODED_TYPE', body), expected)

    def test_db_diag_coded_type_terminations(self):
        for code, name in ((0, 'eENDOFPDU'), (1, 'eZERO'), (2, 'eHEX_FF')):
            with self.subTest(termination=name):
                body = ObjectBytes().u8(1).u32(4).u32(1).u8(code).u8(0).u8(3)
                body.flag(False).flag(False)
                expected = diag_coded_type()
                del expected['bit_length']
                expected.update({'type': 'eMIN_MAX_LENGTH_TYPE', 'max_length': 4,
                                 'min_length': 1, 'termination': name})
                self.assertEqual(load('DB_DIAG_CODED_TYPE', body), expected)

    def test_db_diag_coded_type_leading_length_info_type_data_types(self):
        # (EDbDataType code, name, MCD data type, EDbEncoding code, encoding name)
        cases = [
            (0, 'eDB_INT32', 'eA_INT32', 2, 'e1C'),
            (1, 'eDB_UINT32', 'eA_UINT32', 0, 'eBCD_P'),
            (2, 'eDB_FLOAT32', 'eA_FLOAT32', 7, 'eIEEE754'),
            (3, 'eDB_FLOAT64', 'eA_FLOAT64', 7, 'eIEEE754'),
            (4, 'eDB_ASCIISTRING', 'eA_ASCIISTRING', 10, 'eWINDOWS_1252'),
            (5, 'eDB_UTF8STRING', 'eA_UTF8STRING', 5, 'eUTF_8'),
            (6, 'eDB_UNICODE2STRING', 'eA_UNICODE2STRING', 6, 'eUCS_2'),
            (7, 'eDB_BYTEFIELD', 'eA_BYTEFIELD', 1, 'eBCD_UP'),
            (8, 'eDB_BITFIELD', 'eA_BITFIELD', 11, 'eNONE'),
        ]
        for data_code, name, mcd_name, encoding_code, encoding in cases:
            with self.subTest(base_data_type=name):
                body = ObjectBytes().u8(0).u32(8).u8(data_code).u8(encoding_code)
                body.flag(False).flag(False)
                expected = diag_coded_type()
                expected.update({'base_data_type': name,
                                 'base_data_type_as_mcd_data_type': mcd_name,
                                 'encoding': encoding})
                self.assertEqual(load('DB_DIAG_CODED_TYPE', body), expected)


class PhysicalTypeTests(unittest.TestCase):
    def test_db_physical_type_minimal(self):
        self.assertEqual(load('DB_PHYSICAL_TYPE', physical_type_body()), physical_type())

    def test_db_physical_type_all_branches(self):
        body = ObjectBytes().u8(3).flag(True).u16(2).u8(16)
        self.assertEqual(load('DB_PHYSICAL_TYPE', body), {
            '#OBJECT_TYPE': 'DB_PHYSICAL_TYPE', 'base_data_type': 'eDB_FLOAT64',
            'base_data_type_as_mcd_data_type': 'eA_FLOAT64', 'is_precision_available': True,
            'precision': 2, 'display_radix': 16})

    def test_db_physical_type_data_types(self):
        cases = [(0, 'eDB_INT32', 'eA_INT32'), (1, 'eDB_UINT32', 'eA_UINT32'),
                 (2, 'eDB_FLOAT32', 'eA_FLOAT32'), (3, 'eDB_FLOAT64', 'eA_FLOAT64'),
                 (4, 'eDB_UNICODE2STRING', 'eA_UNICODE2STRING'),
                 (5, 'eDB_BYTEFIELD', 'eA_BYTEFIELD')]
        for code, name, mcd_name in cases:
            with self.subTest(base_data_type=name):
                expected = physical_type()
                expected.update({'base_data_type': name,
                                 'base_data_type_as_mcd_data_type': mcd_name})
                self.assertEqual(
                    load('DB_PHYSICAL_TYPE', ObjectBytes().u8(code).flag(False).u8(10)), expected)


class DopDtcTests(unittest.TestCase):
    @staticmethod
    def strings(body):
        return body.ascii('DTC_DOP').unicode('Long').unicode(None).ascii('UID').ascii(None).ascii('DID')

    @staticmethod
    def expected(**changes):
        result = {'#OBJECT_TYPE': 'DB_DOP_DTC', 'diag_trouble_codes_ref_map': [],
                  'compu_method': None, 'diag_coded_type': None, 'physical_type': None,
                  'short_name': 'DTC_DOP', 'long_name': 'Long', 'description': None,
                  'unique_object_id': 'UID', 'long_name_id': None,
                  'description_id': 'DID', 'linked_dtc_dops': []}
        result.update(changes)
        return result

    def test_db_dop_dtc_minimal(self):
        body = ObjectBytes().u16(0).u16(0).absent().absent().absent()
        self.assertEqual(load('DB_DOP_DTC', self.strings(body)), self.expected())

    def test_db_dop_dtc_all_branches(self):
        body = ObjectBytes().u16(2)
        body.u32(0x10).ascii('DTC1').ascii('POOL').u32(0x20).ascii('DTC2').ascii('POOL')
        body.u16(0)
        body.nested('DB_COMPU_METHOD', compu_method_body())
        body.nested('DB_DIAG_CODED_TYPE', diag_coded_type_body())
        body.nested('DB_PHYSICAL_TYPE', physical_type_body())
        self.assertEqual(load('DB_DOP_DTC', self.strings(body)), self.expected(
            diag_trouble_codes_ref_map=[
                {'map_key': 0x10, 'reference': {'object_id': 'DTC1', 'pool_id': 'POOL'}},
                {'map_key': 0x20, 'reference': {'object_id': 'DTC2', 'pool_id': 'POOL'}}],
            compu_method=compu_method(), diag_coded_type=diag_coded_type(),
            physical_type=physical_type()))

    def test_db_dop_dtc_linked_dtc_dops(self):
        body = ObjectBytes().u16(0).u16(2)
        body.u16(2).ascii('V1').ascii('V2').ascii('DOP1').ascii('POOL')
        body.u16(0).ascii('DOP2').ascii(None)
        body.absent().absent().absent()
        self.assertEqual(load('DB_DOP_DTC', self.strings(body)), self.expected(linked_dtc_dops=[
            {'strings': ['V1', 'V2'], 'reference': {'object_id': 'DOP1', 'pool_id': 'POOL'}},
            {'strings': [], 'reference': {'object_id': 'DOP2', 'pool_id': None}}]))


class DopSimpleBaseTests(unittest.TestCase):
    def test_db_dop_simple_base_minimal(self):
        body = ObjectBytes().ascii('DOP').absent().absent().absent().u16(0).u16(0)
        body.flag(False).flag(False).flag(False)
        self.assertEqual(load('DB_DOP_SIMPLE_BASE', body), {
            '#OBJECT_TYPE': 'DB_DOP_SIMPLE_BASE', 'short_name': 'DOP', 'compu_method': None,
            'diag_coded_type': None, 'physical_type': None, 'phys_to_coded_index_map': [],
            'coded_to_phys_index_map': [], 'units_ref': None, 'internal_constraint_ref': None,
            'physical_constraint_ref': None})

    def test_db_dop_simple_base_all_branches(self):
        body = ObjectBytes().ascii('DOP')
        body.nested('DB_COMPU_METHOD', compu_method_body())
        body.nested('DB_DIAG_CODED_TYPE', diag_coded_type_body())
        body.nested('DB_PHYSICAL_TYPE', physical_type_body())
        body.u16(2).u32(1).u16(10).u32(2).u16(20)
        body.u16(2).u32(3).u16(30).u32(4).u16(40)
        body.flag(True).ascii('UNIT').ascii('POOL')
        body.flag(True).ascii('INT').ascii('POOL')
        body.flag(True).ascii('PHYS').ascii('POOL')
        self.assertEqual(load('DB_DOP_SIMPLE_BASE', body), {
            '#OBJECT_TYPE': 'DB_DOP_SIMPLE_BASE', 'short_name': 'DOP',
            'compu_method': compu_method(), 'diag_coded_type': diag_coded_type(),
            'physical_type': physical_type(),
            'phys_to_coded_index_map': [{'map_key': 1, 'item': 10}, {'map_key': 2, 'item': 20}],
            'coded_to_phys_index_map': [{'map_key': 3, 'item': 30}, {'map_key': 4, 'item': 40}],
            'units_ref': {'object_id': 'UNIT', 'pool_id': 'POOL'},
            'internal_constraint_ref': {'object_id': 'INT', 'pool_id': 'POOL'},
            'physical_constraint_ref': {'object_id': 'PHYS', 'pool_id': 'POOL'}})


class KeyVectorTests(unittest.TestCase):
    def test_db_key_vector_minimal(self):
        self.assertEqual(load('DB_KEY_VECTOR', ObjectBytes().u16(0)),
                         {'#OBJECT_TYPE': 'DB_KEY_VECTOR', 'keys': []})

    def test_db_key_vector_all_branches(self):
        body = ObjectBytes().u16(2).ascii('K1').ascii('K2')
        self.assertEqual(load('DB_KEY_VECTOR', body),
                         {'#OBJECT_TYPE': 'DB_KEY_VECTOR', 'keys': ['K1', 'K2']})


class SwitchKeyTests(unittest.TestCase):
    def test_db_switch_key_minimal(self):
        body = ObjectBytes().u8(0).u32(0).ascii('DOP').ascii('POOL')
        self.assertEqual(load('DB_SWITCH_KEY', body), {
            '#OBJECT_TYPE': 'DB_SWITCH_KEY', 'bit_position': 0, 'byte_position': 0,
            'is_byte_pos_available': True, 'dop_base_ref': {'object_id': 'DOP', 'pool_id': 'POOL'}})

    def test_db_switch_key_all_branches(self):
        body = ObjectBytes().u8(7).u32(300).ascii('DOP').ascii(None)
        self.assertEqual(load('DB_SWITCH_KEY', body), {
            '#OBJECT_TYPE': 'DB_SWITCH_KEY', 'bit_position': 7, 'byte_position': 300,
            'is_byte_pos_available': True, 'dop_base_ref': {'object_id': 'DOP', 'pool_id': None}})


class IntervalTests(unittest.TestCase):
    def test_mcd_interval_minimal(self):
        self.assertEqual(load('MCD_INTERVAL', interval_body()), interval())

    def test_mcd_interval_all_branches(self):
        self.assertEqual(load('MCD_INTERVAL', interval_body(1, 9, 0x11)),
                         interval(1, 9, 'eLIMIT_CLOSED', 'eLIMIT_CLOSED'))

    def test_mcd_interval_infinite_limits(self):
        self.assertEqual(load('MCD_INTERVAL', interval_body(flags=0x22)),
                         interval(lower_type='eLIMIT_INFINITE', upper_type='eLIMIT_INFINITE'))

    def test_mcd_interval_infinite_wins_over_closed(self):
        self.assertEqual(load('MCD_INTERVAL', interval_body(flags=0x33)),
                         interval(lower_type='eLIMIT_INFINITE', upper_type='eLIMIT_INFINITE'))

    def test_mcd_interval_lower_closed_upper_open(self):
        self.assertEqual(load('MCD_INTERVAL', interval_body(flags=0x01)),
                         interval(lower_type='eLIMIT_CLOSED', upper_type='eLIMIT_OPEN'))

    def test_mcd_interval_lower_open_upper_closed(self):
        self.assertEqual(load('MCD_INTERVAL', interval_body(flags=0x10)),
                         interval(lower_type='eLIMIT_OPEN', upper_type='eLIMIT_CLOSED'))


class ScaleConstraintTests(unittest.TestCase):
    def test_mcd_scale_constraint_minimal(self):
        self.assertEqual(load('MCD_SCALE_CONSTRAINT', scale_constraint_body()), scale_constraint())

    def test_mcd_scale_constraint_all_branches(self):
        body = ObjectBytes().nested('MCD_INTERVAL', interval_body(1, 2, 0x11)).u8(4)
        body.unicode('Description').ascii('DESC_ID').ascii('Label').ascii('LABEL_ID').flag(True)
        self.assertEqual(load('MCD_SCALE_CONSTRAINT', body), {
            '#OBJECT_TYPE': 'MCD_SCALE_CONSTRAINT',
            'interval': interval(1, 2, 'eLIMIT_CLOSED', 'eLIMIT_CLOSED'),
            'range_info': 'eVALUE_NOT_AVAILABLE', 'description': 'Description',
            'description_id': 'DESC_ID', 'short_label': 'Label',
            'short_label_id': 'LABEL_ID', 'is_computed': True})

    def test_mcd_scale_constraint_range_infos(self):
        names = {2: 'eVALUE_VALID', 3: 'eVALUE_NOT_DEFINED', 4: 'eVALUE_NOT_AVAILABLE',
                 5: 'eVALUE_NOT_VALID', 6: 'eVALUE_NOT_INITIALIZED',
                 7: 'eVALUE_CODED_TO_PHYSICAL_FAILED'}
        for code, name in names.items():
            with self.subTest(range_info=name):
                self.assertEqual(load('MCD_SCALE_CONSTRAINT', scale_constraint_body(code)),
                                 scale_constraint(name))


class ScaleConstraintsTests(unittest.TestCase):
    def test_mcd_scale_constraints_minimal(self):
        self.assertEqual(load('MCD_SCALE_CONSTRAINTS', ObjectBytes().u32(0)), [])

    def test_mcd_scale_constraints_all_branches(self):
        body = ObjectBytes().u32(2)
        body.nested('MCD_SCALE_CONSTRAINT', scale_constraint_body())
        body.nested('MCD_SCALE_CONSTRAINT', scale_constraint_body(3))
        self.assertEqual(load('MCD_SCALE_CONSTRAINTS', body),
                         [scale_constraint(), scale_constraint('eVALUE_NOT_DEFINED')])


class ConstraintTests(unittest.TestCase):
    def test_mcd_constraint_minimal(self):
        self.assertEqual(load('MCD_CONSTRAINT', ObjectBytes().absent().absent().flag(False)),
                         {'#OBJECT_TYPE': 'MCD_CONSTRAINT', 'interval': None,
                          'scale_constraints': None, 'is_computed': False})

    def test_mcd_constraint_all_branches(self):
        constraints = ObjectBytes().u32(1).nested('MCD_SCALE_CONSTRAINT', scale_constraint_body())
        body = ObjectBytes().nested('MCD_INTERVAL', interval_body(1, 2, 0x11))
        body.nested('MCD_SCALE_CONSTRAINTS', constraints).flag(True)
        self.assertEqual(load('MCD_CONSTRAINT', body), {
            '#OBJECT_TYPE': 'MCD_CONSTRAINT',
            'interval': interval(1, 2, 'eLIMIT_CLOSED', 'eLIMIT_CLOSED'),
            'scale_constraints': [scale_constraint()], 'is_computed': True})


class UnitTests(unittest.TestCase):
    @staticmethod
    def head():
        return ObjectBytes().ascii('U_km').unicode('Kilometer').unicode(None).ascii('UID').ascii(None).ascii(None)

    def test_mcd_db_unit_minimal(self):
        body = self.head().unicode(None).double(1000.0).double(0.0).absent().flag(False)
        self.assertEqual(load('MCD_DB_UNIT', body), {
            '#OBJECT_TYPE': 'MCD_DB_UNIT', 'short_name': 'U_km', 'long_name': 'Kilometer',
            'description': None, 'unique_object_id': 'UID', 'long_name_id': None,
            'description_id': None, 'display_name': None, 'factor_si_to_unit': 1000.0, 'offset_si_to_unit': 0.0,
            'physical_dimension': None, 'unit_group_refs': None})

    def test_mcd_db_unit_all_branches(self):
        body = self.head().unicode('km').double(0.001).double(-273.15)
        body.nested('MCD_DB_PHYSICAL_DIMENSION', dimension_body())
        body.flag(True).u16(2).ascii('G1').ascii('GRP1').ascii('POOL')
        body.ascii('G2').ascii('GRP2').ascii('POOL')
        self.assertEqual(load('MCD_DB_UNIT', body), {
            '#OBJECT_TYPE': 'MCD_DB_UNIT', 'short_name': 'U_km', 'long_name': 'Kilometer',
            'description': None, 'unique_object_id': 'UID', 'long_name_id': None,
            'description_id': None, 'display_name': 'km', 'factor_si_to_unit': 0.001, 'offset_si_to_unit': -273.15,
            'physical_dimension': dimension(),
            'unit_group_refs': [
                {'name': 'G1', 'reference': {'object_id': 'GRP1', 'pool_id': 'POOL'}},
                {'name': 'G2', 'reference': {'object_id': 'GRP2', 'pool_id': 'POOL'}}]})

    def test_mcd_db_unit_empty_group_collection(self):
        body = self.head().unicode(None).double(1.0).double(0.0).absent().flag(True).u16(0)
        self.assertEqual(load('MCD_DB_UNIT', body), {
            '#OBJECT_TYPE': 'MCD_DB_UNIT', 'short_name': 'U_km', 'long_name': 'Kilometer',
            'description': None, 'unique_object_id': 'UID', 'long_name_id': None,
            'description_id': None, 'display_name': None, 'factor_si_to_unit': 1.0, 'offset_si_to_unit': 0.0,
            'physical_dimension': None, 'unit_group_refs': []})

    def test_mcd_db_unit_identifiers(self):
        body = (ObjectBytes().ascii('U_km').unicode('Kilometer').unicode(None)
                .ascii('UOI').ascii('LNID').ascii('DID'))
        body.unicode(None).double(1000.0).double(0.0).absent().flag(False)
        self.assertEqual(load('MCD_DB_UNIT', body), {
            '#OBJECT_TYPE': 'MCD_DB_UNIT', 'short_name': 'U_km', 'long_name': 'Kilometer',
            'description': None, 'unique_object_id': 'UOI', 'long_name_id': 'LNID',
            'description_id': 'DID', 'display_name': None, 'factor_si_to_unit': 1000.0,
            'offset_si_to_unit': 0.0, 'physical_dimension': None, 'unit_group_refs': None})


class UnitGroupTests(unittest.TestCase):
    @staticmethod
    def head():
        return (ObjectBytes().ascii('Group').unicode('Group long').unicode(None)
                .ascii(None).ascii(None).ascii(None))

    @staticmethod
    def expected(category, refs):
        return {'#OBJECT_TYPE': 'MCD_DB_UNIT_GROUP', 'short_name': 'Group',
                'long_name': 'Group long', 'description': None, 'unique_object_id': None,
                'long_name_id': None, 'description_id': None, 'category': category,
                'ref_collection': refs}

    def test_mcd_db_unit_group_minimal(self):
        body = self.head().u16(0x0F00).u16(0)
        self.assertEqual(load('MCD_DB_UNIT_GROUP', body), self.expected('eCOUNTRY', []))

    def test_mcd_db_unit_group_all_branches(self):
        body = self.head().u16(0x0F01).u16(2)
        body.ascii('N1').ascii('R1').ascii('POOL').ascii('N2').ascii('R2').ascii(None)
        self.assertEqual(load('MCD_DB_UNIT_GROUP', body), self.expected('eEQUIVALENT_UNITS', [
            {'name': 'N1', 'reference': {'object_id': 'R1', 'pool_id': 'POOL'}},
            {'name': 'N2', 'reference': {'object_id': 'R2', 'pool_id': None}}]))

    def test_mcd_db_unit_group_ecountry(self):
        body = self.head().u16(0x0F00).u16(1).ascii('N1').ascii('R1').ascii('POOL')
        self.assertEqual(load('MCD_DB_UNIT_GROUP', body), self.expected('eCOUNTRY', [
            {'name': 'N1', 'reference': {'object_id': 'R1', 'pool_id': 'POOL'}}]))

    def test_mcd_db_unit_group_identifiers(self):
        body = (ObjectBytes().ascii('Group').unicode('Group long').unicode(None)
                .ascii('UOI').ascii('LNID').ascii('DID').u16(0x0F00).u16(0))
        expected = self.expected('eCOUNTRY', [])
        expected.update(unique_object_id='UOI', long_name_id='LNID', description_id='DID')
        self.assertEqual(load('MCD_DB_UNIT_GROUP', body), expected)


class PhysicalDimensionTests(unittest.TestCase):
    def test_mcd_db_physical_dimension_minimal(self):
        self.assertEqual(load('MCD_DB_PHYSICAL_DIMENSION', dimension_body()), dimension())

    def test_mcd_db_physical_dimension_all_branches(self):
        body = ObjectBytes().ascii('Speed').unicode('Speed long').unicode('Description')
        body.ascii('UID').ascii('LID').ascii(None)
        body.i32(1).i32(-1).i32(2).i32(-2).i32(3).i32(-3).i32(2147483647)
        self.assertEqual(load('MCD_DB_PHYSICAL_DIMENSION', body), {
            '#OBJECT_TYPE': 'MCD_DB_PHYSICAL_DIMENSION', 'short_name': 'Speed',
            'long_name': 'Speed long', 'description': 'Description', 'unique_object_id': 'UID',
            'long_name_id': 'LID', 'description_id': None, 'length_exponent': 1,
            'mass_exponent': -1,
            'time_exponent': 2, 'current_exponent': -2, 'temperature_exponent': 3,
            'molar_amount_exponent': -3, 'luminous_intensity_exponent': 2147483647})

    def test_mcd_db_physical_dimension_identifiers(self):
        body = (ObjectBytes().ascii('Length').unicode(None).unicode(None)
                .ascii('UOI').ascii('LNID').ascii('DID'))
        body.i32(1).i32(0).i32(0).i32(0).i32(0).i32(0).i32(0)
        expected = dimension()
        expected.update(unique_object_id='UOI', long_name_id='LNID', description_id='DID')
        self.assertEqual(load('MCD_DB_PHYSICAL_DIMENSION', body), expected)


if __name__ == '__main__':
    unittest.main()
