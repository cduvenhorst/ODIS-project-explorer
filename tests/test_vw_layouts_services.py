"""Protection tests for the current (VW) layouts of the parameter, service, table and matching loaders.

Every body is built exactly as the loader reads it today and the complete result is
asserted, in strict mode.  Branches in which the loaders raise today are not pinned.
The helper loaders these loaders call (field base, diagnostic service, data primitive,
diagnostic communication primitive, job) are exercised through the tests below.
The ECU state collections of the communication primitive follow the kernel (attributed
references), not the former upstream layout.
The environment data description loader follows the kernel: description is read instead of
being required empty, and description_id, long_name_id and unique_object_id always appear
as keys (None when empty).
The identifiers follow the kernel names: the communication primitive reads description_id
(formerly id), the request unique_object_id (formerly id) and the parameter description_id
(formerly some_id); the parameter also always has dop_base (None without flag 1 << 4).
The table parameter reads its additional audience collections and its named streams A and B
like the kernel.  Deviation from the former behaviour: a present but empty named stream B
gives pre_condition_state_refs == [] instead of None (None only when B is absent).
"""
import unittest

from tests import support
from tests.support import (NAMED_ATTRIBUTED_REFS, NAMED_REFS, ObjectBytes, concat, attributed_ref, attributed_ref_body,
                           audience, audience_body, case, case_base_body, case_body, diag_coded_type,
                           diag_coded_type_body, diag_com_ref, diag_com_ref_body, diag_com_refs,
                           diag_com_refs_body, named_attributed_refs, named_attributed_refs_body,
                           named_refs, named_refs_body, ref, ref_body, typed,
                           uint, uint_value)


def load(type_name, body):
    return support.load(type_name, body)


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

PARAMETER_ALL = dict(value=True, semantic=True, layer=5, coded_type=True, reference=True,
                     byte_pos=True, protocol=True, sdgs=[11, 22])


def parameter_body(value=False, semantic=False, layer=None, coded_type=False, reference=False,
                   byte_pos=False, protocol=False, type_code=1, sdgs=None, nrc_values=None, dop_base=None):
    """MCD_DB_PARAMETER body; coded_type may also be 'absent' (flag set, object missing).

    sdgs sets flag 1 << 6 and writes the reference collection (u16 count, u32 each).
    dop_base is a body (embedded object after the reference), 'absent' (flag set, object
    missing) or None, which leaves flag 1 << 4 unset.
    nrc_values is only used with type_code 0x13: None writes nothing, 'absent' writes a missing
    object, a list of numbers writes an MCD_VALUES object.
    """
    flags = (int(value) | int(semantic) << 1 | int(bool(coded_type)) << 2 | int(reference) << 3
             | int(dop_base is not None) << 4 | int(byte_pos) << 5 | int(sdgs is not None) << 6 | int(protocol) << 7)
    body = ObjectBytes().unicode('Description').unicode('Long name').ascii('Name')
    body.ascii('SomeId').ascii('LongId').ascii('UID').u8(3).u32(12).u8(flags)
    if value:
        uint_value(body, 7)
    body.u32(2)
    if semantic:
        body.ascii('SEM')
    body.ascii('SYS').u8(type_code).u8(0xFF if layer is None else layer)
    if coded_type == 'absent':
        body.absent()
    elif coded_type:
        body.nested('DB_DIAG_CODED_TYPE', diag_coded_type_body())
    if reference:
        ref_body(body, 'REF')
    if dop_base == 'absent':
        body.absent()
    elif dop_base is not None:
        body.nested('MCD_AUDIENCE', dop_base)
    if sdgs is not None:
        body.u16(len(sdgs))
        for object_id in sdgs:
            body.u32(object_id)
    if nrc_values == 'absent':
        body.absent()
    elif nrc_values is not None:
        values = ObjectBytes().u16(len(nrc_values))
        for number in nrc_values:
            uint_value(values, number)
        body.nested('MCD_VALUES', values)
    return body


def parameter(**changes):
    fields = {'description': 'Description', 'long_name': 'Long name', 'short_name': 'Name',
              'description_id': 'SomeId', 'long_name_id': 'LongId', 'unique_object_id': 'UID',
              'bit_position': 3, 'byte_position': 12, 'default_mcd_value': None,
              'display_level': 2, 'semantic': None, 'sys_param': 'SYS',
              'mcd_parameter_type': 'eVALUE', 'layer_id': None, 'diag_coded_type': None,
              'db_object_ref': None, 'dop_base': None, 'is_byte_pos_available': False,
              'is_protocol_parameter': False,
              'special_data_group_refs': None, 'nrc_const_values': None}
    fields.update(changes)
    return fields


def parameter_all():
    return parameter(default_mcd_value=uint(7), semantic='SEM', layer_id=5,
                     diag_coded_type=diag_coded_type(), db_object_ref=ref('REF'),
                     is_byte_pos_available=True, is_protocol_parameter=True,
                     special_data_group_refs=[{'object_id': 11}, {'object_id': 22}])


def two_parameters_body():
    return (ObjectBytes().u16(2).nested('MCD_DB_PARAMETER', parameter_body())
            .nested('MCD_DB_PARAMETER_SIMPLE', parameter_body(type_code=2)))


def two_parameters():
    return [typed('MCD_DB_PARAMETER', parameter()),
            typed('MCD_DB_PARAMETER_SIMPLE', parameter(mcd_parameter_type='eRESERVED'))]


class ParameterTests(unittest.TestCase):
    def test_mcd_db_parameter_minimal(self):
        self.assertEqual(load('MCD_DB_PARAMETER', parameter_body()),
                         typed('MCD_DB_PARAMETER', parameter()))

    def test_mcd_db_parameter_dop_base(self):
        self.assertEqual(
            load('MCD_DB_PARAMETER', parameter_body(reference=True, dop_base=audience_body())),
            typed('MCD_DB_PARAMETER', parameter(db_object_ref=ref('REF'), dop_base=audience())))

    def test_mcd_db_parameter_dop_base_flag_without_object(self):
        body = parameter_body(dop_base='absent')
        self.assertEqual(load('MCD_DB_PARAMETER', body),
                         typed('MCD_DB_PARAMETER', parameter(dop_base=None)))

    def test_mcd_db_parameter_all_branches(self):
        self.assertEqual(load('MCD_DB_PARAMETER', parameter_body(**PARAMETER_ALL)),
                         typed('MCD_DB_PARAMETER', parameter_all()))

    def test_mcd_db_parameter_coded_type_flag_without_object(self):
        self.assertEqual(load('MCD_DB_PARAMETER', parameter_body(coded_type='absent')),
                         typed('MCD_DB_PARAMETER', parameter()))

    def test_mcd_db_parameter_nrc_const(self):
        self.assertEqual(load('MCD_DB_PARAMETER', parameter_body(type_code=0x13, nrc_values=[1, 2])),
                         typed('MCD_DB_PARAMETER', parameter(
                             mcd_parameter_type='eNRC_CONST',
                             nrc_const_values=[uint(1), uint(2)])))

    def test_mcd_db_parameter_nrc_const_without_values(self):
        self.assertEqual(load('MCD_DB_PARAMETER',
                              parameter_body(type_code=0x13, nrc_values='absent')),
                         typed('MCD_DB_PARAMETER', parameter(mcd_parameter_type='eNRC_CONST')))

    def test_mcd_db_parameter_nrc_const_with_special_data_groups(self):
        self.assertEqual(load('MCD_DB_PARAMETER',
                              parameter_body(sdgs=[11], type_code=0x13, nrc_values=[1])),
                         typed('MCD_DB_PARAMETER', parameter(
                             mcd_parameter_type='eNRC_CONST',
                             special_data_group_refs=[{'object_id': 11}],
                             nrc_const_values=[uint(1)])))

    def test_mcd_db_parameter_types(self):
        names = {1: 'eVALUE', 2: 'eRESERVED', 3: 'eCODED_CONST', 4: 'ePHYS_CONST',
                 5: 'eLENGTH_KEY', 6: 'eMATCHING_REQUEST_PARAM', 7: 'eSYSTEM', 8: 'eDYNAMIC',
                 9: 'eTABLE_KEY', 0x10: 'eTABLE_STRUCT', 0x11: 'eTABLE_ENTRY',
                 0x12: 'eGENERATED'}
        for code, name in names.items():
            with self.subTest(parameter_type=name):
                self.assertEqual(load('MCD_DB_PARAMETER', parameter_body(type_code=code)),
                                 typed('MCD_DB_PARAMETER', parameter(mcd_parameter_type=name)))


class ValuesTests(unittest.TestCase):
    def test_mcd_values_minimal(self):
        self.assertEqual(load('MCD_VALUES', ObjectBytes().u16(0)), [])

    def test_mcd_values_all_branches(self):
        body = ObjectBytes().u16(2)
        uint_value(body, 7)
        uint_value(body, 9)
        self.assertEqual(load('MCD_VALUES', body), [uint(7), uint(9)])


class ParameterSimpleTests(unittest.TestCase):
    def test_mcd_db_parameter_simple_minimal(self):
        self.assertEqual(load('MCD_DB_PARAMETER_SIMPLE', parameter_body()),
                         typed('MCD_DB_PARAMETER_SIMPLE', parameter()))

    def test_mcd_db_parameter_simple_all_branches(self):
        self.assertEqual(load('MCD_DB_PARAMETER_SIMPLE', parameter_body(**PARAMETER_ALL)),
                         typed('MCD_DB_PARAMETER_SIMPLE', parameter_all()))


class ParametersTests(unittest.TestCase):
    def test_mcd_db_parameters_minimal(self):
        self.assertEqual(load('MCD_DB_PARAMETERS', ObjectBytes().u16(0)), [])

    def test_mcd_db_parameters_all_branches(self):
        self.assertEqual(load('MCD_DB_PARAMETERS', two_parameters_body()), two_parameters())

    def test_mcd_db_parameters_missing_entry(self):
        self.assertEqual(load('MCD_DB_PARAMETERS', ObjectBytes().u16(1).absent()), [None])


class RequestParametersTests(unittest.TestCase):
    def test_mcd_db_request_parameters_minimal(self):
        self.assertEqual(load('MCD_DB_REQUEST_PARAMETERS', ObjectBytes().u16(0)), [])

    def test_mcd_db_request_parameters_all_branches(self):
        self.assertEqual(load('MCD_DB_REQUEST_PARAMETERS', two_parameters_body()),
                         two_parameters())


class ResponseParametersTests(unittest.TestCase):
    def test_mcd_db_response_parameters_minimal(self):
        self.assertEqual(load('MCD_DB_RESPONSE_PARAMETERS', ObjectBytes().u16(0)), [])

    def test_mcd_db_response_parameters_all_branches(self):
        self.assertEqual(load('MCD_DB_RESPONSE_PARAMETERS', two_parameters_body()),
                         two_parameters())


# ---------------------------------------------------------------------------
# Parameter variants
# ---------------------------------------------------------------------------

def dop_field_body(environment=False):
    """DB_DOP_FIELD: structure reference, or environment data description reference."""
    body = ObjectBytes().u8(1 if environment else 0)
    return ref_body(body, 'ENV' if environment else 'STRUCT')


def dop_field(environment=False):
    if environment:
        return {'env_data_desc_ref': ref('ENV')}
    return {'structure_ref': ref('STRUCT')}


class StaticFieldTests(unittest.TestCase):
    def test_mcd_db_parameter_static_field_minimal(self):
        body = concat(dop_field_body(), ObjectBytes().u32(4).u32(2))
        self.assertEqual(load('MCD_DB_PARAMETER_STATIC_FIELD', body), typed(
            'MCD_DB_PARAMETER_STATIC_FIELD',
            {**dop_field(), 'fixed_number_of_items': 4, 'item_byte_size': 2}))

    def test_mcd_db_parameter_static_field_all_branches(self):
        body = concat(dop_field_body(True), ObjectBytes().u32(4).u32(2))
        self.assertEqual(load('MCD_DB_PARAMETER_STATIC_FIELD', body), typed(
            'MCD_DB_PARAMETER_STATIC_FIELD',
            {**dop_field(True), 'fixed_number_of_items': 4, 'item_byte_size': 2}))


class EndOfPduFieldTests(unittest.TestCase):
    def test_mcd_db_parameter_end_of_pdu_field_minimal(self):
        body = concat(dop_field_body(), ObjectBytes().u32(9).u32(1))
        self.assertEqual(load('MCD_DB_PARAMETER_END_OF_PDU_FIELD', body), typed(
            'MCD_DB_PARAMETER_END_OF_PDU_FIELD',
            {**dop_field(), 'max_number_of_items': 9, 'min_number_of_items': 1}))

    def test_mcd_db_parameter_end_of_pdu_field_all_branches(self):
        body = concat(dop_field_body(True), ObjectBytes().u32(9).u32(1))
        self.assertEqual(load('MCD_DB_PARAMETER_END_OF_PDU_FIELD', body), typed(
            'MCD_DB_PARAMETER_END_OF_PDU_FIELD',
            {**dop_field(True), 'max_number_of_items': 9, 'min_number_of_items': 1}))


class DynamicLengthFieldTests(unittest.TestCase):
    @staticmethod
    def tail():
        return ref_body(ObjectBytes().u32(6), 'DOP').u32(20).u8(5)

    @staticmethod
    def fields():
        return {'first_item_offset': 6, 'determine_number_of_items_dop_ref': ref('DOP'),
                'determine_number_of_items_byte_position': 20,
                'determine_number_of_items_bit_position': 5}

    def test_mcd_db_parameter_dynamic_length_field_minimal(self):
        self.assertEqual(
            load('MCD_DB_PARAMETER_DYNAMIC_LENGTH_FIELD', concat(dop_field_body(), self.tail())),
            typed('MCD_DB_PARAMETER_DYNAMIC_LENGTH_FIELD', {**dop_field(), **self.fields()}))

    def test_mcd_db_parameter_dynamic_length_field_all_branches(self):
        body = concat(dop_field_body(True), self.tail())
        self.assertEqual(
            load('MCD_DB_PARAMETER_DYNAMIC_LENGTH_FIELD', body),
            typed('MCD_DB_PARAMETER_DYNAMIC_LENGTH_FIELD', {**dop_field(True), **self.fields()}))


class DynamicEndmarkerFieldTests(unittest.TestCase):
    @staticmethod
    def tail():
        return ref_body(ObjectBytes().ascii('FF'), 'DOP')

    def test_mcd_db_parameter_dynamic_endmarker_field_minimal(self):
        self.assertEqual(
            load('MCD_DB_PARAMETER_DYNAMIC_ENDMARKER_FIELD',
                 concat(dop_field_body(), self.tail())),
            typed('MCD_DB_PARAMETER_DYNAMIC_ENDMARKER_FIELD',
                  {**dop_field(), 'termination_value': 'FF', 'dop_base_ref': ref('DOP')}))

    def test_mcd_db_parameter_dynamic_endmarker_field_all_branches(self):
        self.assertEqual(
            load('MCD_DB_PARAMETER_DYNAMIC_ENDMARKER_FIELD',
                 concat(dop_field_body(True), self.tail())),
            typed('MCD_DB_PARAMETER_DYNAMIC_ENDMARKER_FIELD',
                  {**dop_field(True), 'termination_value': 'FF', 'dop_base_ref': ref('DOP')}))


class ParameterEnvDataTests(unittest.TestCase):
    def test_mcd_db_parameter_env_data_minimal(self):
        self.assertEqual(load('MCD_DB_PARAMETER_ENV_DATA', ObjectBytes().u16(8).absent()),
                         typed('MCD_DB_PARAMETER_ENV_DATA', {'byte_length': 8, 'parameters': None}))

    def test_mcd_db_parameter_env_data_all_branches(self):
        body = ObjectBytes().u16(8).nested('MCD_DB_PARAMETERS', two_parameters_body())
        self.assertEqual(load('MCD_DB_PARAMETER_ENV_DATA', body), typed(
            'MCD_DB_PARAMETER_ENV_DATA', {'byte_length': 8, 'parameters': two_parameters()}))


def env_data_desc_body(full=False):
    """MCD_DB_ENV_DATA_DESC: the string slots that must be empty are written as 0."""
    body = ObjectBytes().unicode(None).unicode('Long').ascii('Desc')
    body.ascii(None).ascii(None).ascii(None)
    if not full:
        return body.u16(0).u8(0).u16(0)
    body.u16(2).u32(1).ascii('S1').u32(2).ascii(None)
    body.u8(1).nested('MCD_DB_PARAMETER', parameter_body())
    body.u16(2)
    body.ascii('E1').nested('MCD_DB_PARAMETER', parameter_body()).u32(2).u32(10).u32(20)
    body.ascii(None).absent().u32(0)
    return body


def env_data_desc(full=False):
    fields = {'description': None, 'long_name': 'Long', 'short_name': 'Desc',
              'description_id': None, 'long_name_id': None, 'unique_object_id': None,
              'env_data_param_map': [], 'env_data_params': []}
    if full:
        fields['env_data_param_map'] = [{'key': 1, 'string': 'S1'}, {'key': 2, 'string': None}]
        fields['all_value_db_env_data_param'] = typed('MCD_DB_PARAMETER', parameter())
        fields['env_data_params'] = [
            {'string': 'E1', 'param': typed('MCD_DB_PARAMETER', parameter()),
             'vector': [10, 20]},
            {'string': None, 'param': None, 'vector': []}]
    return fields


class EnvDataDescTests(unittest.TestCase):
    def test_mcd_db_env_data_desc_minimal(self):
        self.assertEqual(load('MCD_DB_ENV_DATA_DESC', env_data_desc_body()),
                         typed('MCD_DB_ENV_DATA_DESC', env_data_desc()))

    def test_mcd_db_env_data_desc_all_branches(self):
        self.assertEqual(load('MCD_DB_ENV_DATA_DESC', env_data_desc_body(True)),
                         typed('MCD_DB_ENV_DATA_DESC', env_data_desc(True)))

    def test_mcd_db_env_data_desc_all_value_flag_without_object(self):
        body = (ObjectBytes().unicode(None).unicode('Long').ascii('Desc').ascii(None)
                .ascii(None).ascii(None).u16(0).u8(1).absent().u16(0))
        self.assertEqual(load('MCD_DB_ENV_DATA_DESC', body), typed(
            'MCD_DB_ENV_DATA_DESC', {**env_data_desc(), 'all_value_db_env_data_param': None}))


class EnvDataDescIdentifierTests(unittest.TestCase):
    def test_mcd_db_env_data_desc_identifiers(self):
        body = ObjectBytes().unicode('Desc').unicode('Long').ascii('Name')
        body.ascii('DID').ascii('LNID').ascii('UOI').u16(0).u8(0).u16(0)
        self.assertEqual(load('MCD_DB_ENV_DATA_DESC', body), typed('MCD_DB_ENV_DATA_DESC', {
            'description': 'Desc', 'long_name': 'Long', 'short_name': 'Name',
            'description_id': 'DID', 'long_name_id': 'LNID', 'unique_object_id': 'UOI',
            'env_data_param_map': [], 'env_data_params': []}))


class ParameterEnvDataDescTests(unittest.TestCase):
    def test_mcd_db_parameter_env_data_desc_minimal(self):
        body = ObjectBytes().u8(0).ascii('PName')
        body.nested('MCD_DB_ENV_DATA_DESC', env_data_desc_body()).u16(4)
        self.assertEqual(load('MCD_DB_PARAMETER_ENV_DATA_DESC', body), typed(
            'MCD_DB_PARAMETER_ENV_DATA_DESC', {
                'is_parameter_short_name_path_available': 0, 'parameter_name': 'PName',
                'env_data_desc': typed('MCD_DB_ENV_DATA_DESC', env_data_desc()),
                'byte_length': 4}))

    def test_mcd_db_parameter_env_data_desc_all_branches(self):
        body = ObjectBytes().u8(1).ascii('PATH')
        body.nested('MCD_DB_ENV_DATA_DESC', env_data_desc_body(True)).u16(4)
        self.assertEqual(load('MCD_DB_PARAMETER_ENV_DATA_DESC', body), typed(
            'MCD_DB_PARAMETER_ENV_DATA_DESC', {
                'is_parameter_short_name_path_available': 1,
                'parameter_short_name_path': 'PATH',
                'env_data_desc': typed('MCD_DB_ENV_DATA_DESC', env_data_desc(True)),
                'byte_length': 4}))


def multiplexer_body(full=False):
    body = ObjectBytes().u32(7)
    if not full:
        return body.absent().absent().absent()
    switch_key = ObjectBytes().u8(2).u32(3)
    ref_body(switch_key, 'DOP')
    cases = ObjectBytes().u32(1).nested('DB_CASE', concat(case_body(), case_base_body()))
    return (body.nested('DB_SWITCH_KEY', switch_key).nested('DB_CASES', cases)
            .nested('DB_DEFAULT_CASE', case_base_body()))


class MultiplexerTests(unittest.TestCase):
    def test_mcd_db_parameter_multiplexer_minimal(self):
        self.assertEqual(load('MCD_DB_PARAMETER_MULTIPLEXER', multiplexer_body()), typed(
            'MCD_DB_PARAMETER_MULTIPLEXER',
            {'byte_position': 7, 'switch_key': None, 'cases': None, 'default_case': None}))

    def test_mcd_db_parameter_multiplexer_all_branches(self):
        self.assertEqual(load('MCD_DB_PARAMETER_MULTIPLEXER', multiplexer_body(True)), typed(
            'MCD_DB_PARAMETER_MULTIPLEXER', {
                'byte_position': 7,
                'switch_key': typed('DB_SWITCH_KEY', {
                    'bit_position': 2, 'byte_position': 3, 'is_byte_pos_available': True,
                    'dop_base_ref': ref('DOP')}),
                'cases': [case()],
                'default_case': case(type_name='DB_DEFAULT_CASE')}))


def structure_body(parameters=False):
    body = ObjectBytes().ascii('Struct').unicode('Struct long').ascii('LongId')
    body.unicode('Struct description').ascii('DescId').ascii('UID').u16(6)
    if parameters:
        return body.nested('MCD_DB_PARAMETERS', two_parameters_body())
    return body.absent()


def structure(parameters=None):
    return {'short_name': 'Struct', 'long_name': 'Struct long', 'long_name_id': 'LongId',
            'description': 'Struct description', 'description_id': 'DescId',
            'unique_object_id': 'UID', 'byte_size': 6, 'parameters': parameters}


class StructureTests(unittest.TestCase):
    def test_mcd_db_parameter_structure_minimal(self):
        self.assertEqual(load('MCD_DB_PARAMETER_STRUCTURE', structure_body()),
                         typed('MCD_DB_PARAMETER_STRUCTURE', structure()))

    def test_mcd_db_parameter_structure_all_branches(self):
        self.assertEqual(load('MCD_DB_PARAMETER_STRUCTURE', structure_body(True)),
                         typed('MCD_DB_PARAMETER_STRUCTURE', structure(two_parameters())))


def protocol_tail(parameters=False):
    body = ObjectBytes().u16(0x0102).u16(0x0304)
    if parameters:
        body.nested('MCD_DB_PARAMETERS', two_parameters_body())
    else:
        body.absent()
    return body.ascii('STACK').ascii('PROTOCOL').u16(0x0506)


def protocol_fields(parameters=None):
    return {'protocol_parameter_class': 0x0102, 'protocol_parameter_type': 0x0304,
            'parameters': parameters, 'protocol_stack_short_name': 'STACK',
            'protocol_short_name': 'PROTOCOL', 'protocol_parameter_usage': 0x0506}


class ProtocolParameterTests(unittest.TestCase):
    def test_mcd_db_protocol_parameter_minimal(self):
        body = concat(parameter_body(), protocol_tail())
        self.assertEqual(load('MCD_DB_PROTOCOL_PARAMETER', body), typed(
            'MCD_DB_PROTOCOL_PARAMETER', {**parameter(), **protocol_fields()}))

    def test_mcd_db_protocol_parameter_all_branches(self):
        body = concat(parameter_body(**PARAMETER_ALL), protocol_tail(True))
        self.assertEqual(load('MCD_DB_PROTOCOL_PARAMETER', body), typed(
            'MCD_DB_PROTOCOL_PARAMETER',
            {**parameter_all(), **protocol_fields(two_parameters())}))


class StructFieldTests(unittest.TestCase):
    def test_mcd_db_parameter_struct_field_minimal(self):
        body = concat(parameter_body(), protocol_tail())
        self.assertEqual(load('MCD_DB_PARAMETER_STRUCT_FIELD', body), typed(
            'MCD_DB_PARAMETER_STRUCT_FIELD', {**parameter(), **protocol_fields()}))

    def test_mcd_db_parameter_struct_field_all_branches(self):
        body = concat(parameter_body(**PARAMETER_ALL), protocol_tail(True))
        self.assertEqual(load('MCD_DB_PARAMETER_STRUCT_FIELD', body), typed(
            'MCD_DB_PARAMETER_STRUCT_FIELD',
            {**parameter_all(), **protocol_fields(two_parameters())}))


class TableStructTests(unittest.TestCase):
    def test_mcd_db_parameter_tablestruct_minimal(self):
        body = concat(parameter_body(), attributed_ref_body(ObjectBytes().ascii('KEY')))
        self.assertEqual(load('MCD_DB_PARAMETER_TABLESTRUCT', body), typed(
            'MCD_DB_PARAMETER_TABLESTRUCT',
            {**parameter(), 'key_param_short_name': 'KEY', 'table_ref': attributed_ref()}))

    def test_mcd_db_parameter_tablestruct_all_branches(self):
        body = concat(parameter_body(**PARAMETER_ALL),
                      attributed_ref_body(ObjectBytes().ascii('KEY'), ['S1', 'S2']))
        self.assertEqual(load('MCD_DB_PARAMETER_TABLESTRUCT', body), typed(
            'MCD_DB_PARAMETER_TABLESTRUCT',
            {**parameter_all(), 'key_param_short_name': 'KEY',
             'table_ref': attributed_ref(['S1', 'S2'])}))


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def table_body(full=False):
    body = ObjectBytes().ascii(None).ascii('SomeId').ascii('OBJ').unicode('Description')
    body.unicode('Long name').ascii('Table')
    if not full:
        body.u32(0).ascii(None).u16(0).u8(0).u8(0)
        return body
    body.u32(2)
    body.unicode('K1').ascii('O1').ascii('P1').ascii('Short1')
    body.unicode('K2').ascii('O2').ascii(None).ascii('Short2')
    body.ascii('SEM')
    diag_com_refs_body(body)
    body.u8(1)
    ref_body(body, 'DOP')
    return body.u8(0)


def table(full=False):
    fields = {'some_id': 'SomeId', 'object_id': 'OBJ', 'description': 'Description',
              'long_name': 'Long name', 'short_name': 'Table', 'table_key_map': [],
              'semantic': None, 'diag_com_primitives_refs': []}
    if full:
        fields['table_key_map'] = [
            {'map_key': 'K1', 'reference': {'object_id': 'O1', 'pool_id': 'P1',
                                            'short_name': 'Short1'}},
            {'map_key': 'K2', 'reference': {'object_id': 'O2', 'pool_id': None,
                                            'short_name': 'Short2'}}]
        fields['semantic'] = 'SEM'
        fields['diag_com_primitives_refs'] = diag_com_refs()
        fields['dop_simple_ref'] = ref('DOP')
    return fields


class TableTests(unittest.TestCase):
    def test_mcd_db_table_minimal(self):
        self.assertEqual(load('MCD_DB_TABLE', table_body()), typed('MCD_DB_TABLE', table()))

    def test_mcd_db_table_all_branches(self):
        self.assertEqual(load('MCD_DB_TABLE', table_body(True)),
                         typed('MCD_DB_TABLE', table(True)))


class TableKeyTests(unittest.TestCase):
    def test_mcd_db_parameter_table_key_minimal(self):
        body = concat(parameter_body(), attributed_ref_body(ObjectBytes().absent()))
        body.u8(0).ascii(None)
        self.assertEqual(load('MCD_DB_PARAMETER_TABLE_KEY', body), typed(
            'MCD_DB_PARAMETER_TABLE_KEY', {
                **parameter(), 'table': None, 'table_ref': attributed_ref(),
                'is_table_row_reference': False, 'string': None}))

    def test_mcd_db_parameter_table_key_all_branches(self):
        body = concat(parameter_body(**PARAMETER_ALL),
                      attributed_ref_body(ObjectBytes().absent(), ['S1', 'S2']))
        body.u8(1).ascii('Text')
        self.assertEqual(load('MCD_DB_PARAMETER_TABLE_KEY', body), typed(
            'MCD_DB_PARAMETER_TABLE_KEY', {
                **parameter_all(), 'table': None, 'table_ref': attributed_ref(['S1', 'S2']),
                'is_table_row_reference': True, 'string': 'Text'}))

    def test_mcd_db_parameter_table_key_with_table(self):
        body = concat(parameter_body(), ObjectBytes().nested('MCD_DB_TABLE', table_body(True)))
        body.u8(0).ascii(None)
        self.assertEqual(load('MCD_DB_PARAMETER_TABLE_KEY', body), typed(
            'MCD_DB_PARAMETER_TABLE_KEY', {
                **parameter(), 'table': typed('MCD_DB_TABLE', table(True)),
                'is_table_row_reference': False, 'string': None}))


NAMED_STREAMS_A = bytes.fromhex('233E00 4101 233E01')
NAMED_STREAMS_A_AND_B = bytes.fromhex('233E00 4101 233E01 233C00 420000 233E01')


def table_parameter_body(audience_object=False, both_streams=False, audiences=(None, None),
                         streams=None):
    """audiences: two ObjectBytes (or None for an absent collection); streams: ObjectBytes or bytes."""
    body = ObjectBytes().unicode('Key')
    if audience_object:
        body.nested('MCD_AUDIENCE', audience_body())
    else:
        body.absent()
    for collection in audiences:
        if collection is None:
            body.u8(0)
        else:
            body = concat(body.u8(1), collection)
    body = concat(body, parameter_body())
    if streams is None:
        streams = NAMED_STREAMS_A_AND_B if both_streams else NAMED_STREAMS_A
    if isinstance(streams, ObjectBytes):
        return concat(body, streams)
    return body.raw(streams)


def table_parameter(audience_state=None):
    return {'key': 'Key', 'audience_state': audience_state,
            'disabled_additional_audiences': None, 'enabled_additional_audiences': None,
            'parameter': typed('MCD_DB_PARAMETER', parameter()),
            'is_api_executable': True, 'pre_condition_state_refs': None}


class TableParameterTests(unittest.TestCase):
    def test_mcd_db_table_parameter_minimal(self):
        self.assertEqual(load('MCD_DB_TABLE_PARAMETER', table_parameter_body()),
                         typed('MCD_DB_TABLE_PARAMETER', table_parameter()))

    def test_mcd_db_table_parameter_all_branches(self):
        expected = {**table_parameter(audience()), 'pre_condition_state_refs': []}
        self.assertEqual(load('MCD_DB_TABLE_PARAMETER', table_parameter_body(True, True)),
                         typed('MCD_DB_TABLE_PARAMETER', expected))

    def test_mcd_db_table_parameter_precondition_states(self):
        streams = concat(ObjectBytes().raw(bytes.fromhex('233E00 4101 233E01 233C00 42')),
                         named_attributed_refs_body(ObjectBytes(), NAMED_ATTRIBUTED_REFS))
        streams.raw(bytes.fromhex('233E01'))
        expected = table_parameter()
        expected['pre_condition_state_refs'] = named_attributed_refs(NAMED_ATTRIBUTED_REFS)
        self.assertEqual(load('MCD_DB_TABLE_PARAMETER', table_parameter_body(streams=streams)),
                         typed('MCD_DB_TABLE_PARAMETER', expected))

    def test_mcd_db_table_parameter_api_not_executable(self):
        streams = bytes.fromhex('233E00 4100 233E01')
        expected = {**table_parameter(), 'is_api_executable': False}
        self.assertEqual(load('MCD_DB_TABLE_PARAMETER', table_parameter_body(streams=streams)),
                         typed('MCD_DB_TABLE_PARAMETER', expected))

    def test_mcd_db_table_parameter_without_named_streams(self):
        self.assertEqual(load('MCD_DB_TABLE_PARAMETER', table_parameter_body(streams=b'')),
                         typed('MCD_DB_TABLE_PARAMETER', table_parameter()))

    def test_mcd_db_table_parameter_unknown_named_stream(self):
        streams = bytes.fromhex('233E00 4301 233E01')
        with self.assertRaisesRegex(RuntimeError, 'Unknown named stream: C'):
            load('MCD_DB_TABLE_PARAMETER', table_parameter_body(streams=streams))

    def test_mcd_db_table_parameter_unexpected_marker(self):
        streams = bytes.fromhex('233E01 4101 233E01')
        with self.assertRaisesRegex(RuntimeError, '23 3E 01'):
            load('MCD_DB_TABLE_PARAMETER', table_parameter_body(streams=streams))

    def test_mcd_db_table_parameter_empty_additional_audiences(self):
        body = table_parameter_body(audiences=(ObjectBytes().u16(0), ObjectBytes().u16(0)))
        expected = {**table_parameter(), 'disabled_additional_audiences': [],
                    'enabled_additional_audiences': []}
        self.assertEqual(load('MCD_DB_TABLE_PARAMETER', body),
                         typed('MCD_DB_TABLE_PARAMETER', expected))

    def test_mcd_db_table_parameter_additional_audiences(self):
        disabled = named_refs_body(ObjectBytes(), [('AUD1', 'OBJ1', 'POOL')])
        body = table_parameter_body(audiences=(disabled, ObjectBytes().u16(0)))
        expected = {**table_parameter(),
                    'disabled_additional_audiences': named_refs([('AUD1', 'OBJ1', 'POOL')]),
                    'enabled_additional_audiences': []}
        self.assertEqual(load('MCD_DB_TABLE_PARAMETER', body),
                         typed('MCD_DB_TABLE_PARAMETER', expected))


# ---------------------------------------------------------------------------
# Requests and responses
# ---------------------------------------------------------------------------

def sdg_bytes(body, sdgs):
    if sdgs is None:
        return body.u8(0)
    body.u8(1).u16(len(sdgs))
    for object_id in sdgs:
        body.u32(object_id)
    return body


def request_body(parameters=False, description_id=None, sdgs=None):
    body = ObjectBytes().ascii('Request').unicode('Request long').unicode('Request description')
    body.ascii('ID').ascii('LongId').ascii(description_id)
    if parameters:
        body.nested('MCD_DB_REQUEST_PARAMETERS', two_parameters_body())
    else:
        body.absent()
    return sdg_bytes(body, sdgs)


def request(parameters=None, description_id=None, sdgs=None):
    return {'short_name': 'Request', 'long_name': 'Request long',
            'description': 'Request description', 'unique_object_id': 'ID', 'long_name_id': 'LongId',
            'description_id': description_id, 'request_parameters': parameters,
            'special_data_group_refs':
                None if sdgs is None else [{'object_id': i} for i in sdgs]}


class RequestTests(unittest.TestCase):
    def test_mcd_db_request_minimal(self):
        self.assertEqual(load('MCD_DB_REQUEST', request_body()),
                         typed('MCD_DB_REQUEST', request()))

    def test_mcd_db_request_all_branches(self):
        self.assertEqual(load('MCD_DB_REQUEST', request_body(True, 'DescId', [11, 22])),
                         typed('MCD_DB_REQUEST',
                               request(two_parameters(), 'DescId', [11, 22])))

    def test_mcd_db_request_empty_special_data_groups(self):
        self.assertEqual(load('MCD_DB_REQUEST', request_body(sdgs=[])),
                         typed('MCD_DB_REQUEST', request(sdgs=[])))


def response_body(parameters=False, response_type=0x6F01, description_id=None, sdgs=None):
    body = ObjectBytes().ascii('Response').unicode('Response long')
    body.unicode('Response description').ascii('UID').ascii('LongId').ascii(description_id)
    if parameters:
        body.nested('MCD_DB_RESPONSE_PARAMETERS', two_parameters_body())
    else:
        body.absent()
    return sdg_bytes(body.u16(response_type), sdgs)


def response(parameters=None, response_type='ePOSITIVE_RESPONSE', description_id=None,
             sdgs=None):
    return {'short_name': 'Response', 'long_name': 'Response long',
            'description': 'Response description', 'unique_object_id': 'UID',
            'long_name_id': 'LongId', 'description_id': description_id,
            'response_parameters': parameters, 'response_type': response_type,
            'special_data_group_refs':
                None if sdgs is None else [{'object_id': i} for i in sdgs]}


class ResponseTests(unittest.TestCase):
    def test_mcd_db_response_minimal(self):
        self.assertEqual(load('MCD_DB_RESPONSE', response_body()),
                         typed('MCD_DB_RESPONSE', response()))

    def test_mcd_db_response_all_branches(self):
        self.assertEqual(load('MCD_DB_RESPONSE', response_body(True, description_id='DescId', sdgs=[11, 22])),
                         typed('MCD_DB_RESPONSE',
                               response(two_parameters(), description_id='DescId',
                                        sdgs=[11, 22])))

    def test_mcd_db_response_types(self):
        names = {0x6F01: 'ePOSITIVE_RESPONSE', 0x6F02: 'eLOCAL_NEG_RESPONSE',
                 0x6F03: 'eGLOBAL_NEG_RESPONSE'}
        for code, name in names.items():
            with self.subTest(response_type=name):
                self.assertEqual(load('MCD_DB_RESPONSE', response_body(response_type=code)),
                                 typed('MCD_DB_RESPONSE', response(response_type=name)))


# ---------------------------------------------------------------------------
# Diagnostic communication primitives, services, jobs
# ---------------------------------------------------------------------------

def primitive_body(full=False, transmission=0x6A01, suppression=None):
    """MCD_DB_DIAG_COM_PRIMITIVE.

    suppression selects the suppress-positive-response part: None (off; on when full),
    'path', 'name' (no short name path) or 'empty' (empty bytefield).
    """
    suppression = suppression or ('path' if full else None)
    body = ObjectBytes().ascii('ID').ascii('LongId').ascii('UID').unicode('Description')
    body.unicode('Long name').ascii('Primitive')
    if full:
        body.u8(1)
        ref_body(body, 'REQ')
        named_refs_body(body, NAMED_REFS)
        named_refs_body(body, NAMED_REFS)
        named_refs_body(body, NAMED_REFS)
    else:
        body.u8(0)
        named_refs_body(body)
        named_refs_body(body)
        named_refs_body(body)
    body.ascii(None).u16(transmission).u8(1).u8(0).u8(2)
    named_attributed_refs_body(body, NAMED_ATTRIBUTED_REFS if full else ())
    named_attributed_refs_body(body, NAMED_ATTRIBUTED_REFS if full else ())
    if suppression is None:
        return body.u8(0)
    body.u8(1)
    if suppression == 'empty':
        body.u8(0)
    else:
        body.u8(1).u32(2).raw(b'\x12\x34')
    if suppression == 'name':
        return body.u8(0).ascii('NAME')
    return body.u8(1).ascii('PATH')


def primitive(full=False, transmission_mode='eNO_TRANSMISSION', suppression=None):
    suppression = suppression or ('path' if full else None)
    refs = named_refs(NAMED_REFS) if full else []
    state_refs = named_attributed_refs(NAMED_ATTRIBUTED_REFS) if full else []
    fields = {'description_id': 'ID', 'long_name_id': 'LongId', 'unique_object_id': 'UID',
              'description': 'Description', 'long_name': 'Long name', 'short_name': 'Primitive'}
    if full:
        fields['request_ref'] = ref('REQ')
    fields.update({
        'positive_response_ref_collection': refs, 'negative_response_ref_collection': refs,
        'functional_class_ref_collection': refs, 'semantic': None,
        'transmission_mode': transmission_mode, 'is_api_executable': True,
        'is_no_operataion': False, 'diagnostic_class': 2,
        'ecu_state_transition_ref_collection': state_refs, 'ecu_state_ref_collection': state_refs,
        'has_suppress_positive_response_capability': suppression is not None})
    if suppression is not None:
        by_path = suppression != 'name'
        fields['bytefield'] = b'' if suppression == 'empty' else b'\x12\x34'
        fields['has_positive_response_suppression_parameter_short_name_path'] = by_path
        fields['positive_response_suppression_parameter_short_name_path' if by_path
               else 'positive_response_suppression_parameter_short_name'] = (
            'PATH' if by_path else 'NAME')
    return fields


def data_primitive_body(full=False):
    """MCD_DB_DATA_PRIMITIVE followed by its MCD_DB_DIAG_COM_PRIMITIVE."""
    body = ObjectBytes().absent()
    if not full:
        body.absent().u8(1)
        named_refs_body(body)
        body.u8(0)
        return concat(body, primitive_body())
    body.nested('MCD_AUDIENCE', audience_body()).u8(2)
    diag_com_refs_body(body)
    body.u8(7)
    named_refs_body(body, NAMED_REFS)
    named_refs_body(body, NAMED_REFS)
    body.u16(2).u32(11).u32(22)
    return concat(body, primitive_body(True))


def data_primitive(full=False):
    fields = {'access_level': None, 'audience_state': audience() if full else None,
              'repetition_mode': 'eREPEATED' if full else 'eSINGLE',
              'related_data_primitives': diag_com_refs() if full else [],
              'disabled_additional_audiences': named_refs(NAMED_REFS) if full else None,
              'enabled_additional_audiences': named_refs(NAMED_REFS) if full else None}
    if full:
        fields['special_data_group_refs'] = [{'object_id': 11}, {'object_id': 22}]
    fields['diag_com_primitive'] = typed('MCD_DB_DIAG_COM_PRIMITIVE', primitive(full))
    return typed('MCD_DB_DATA_PRIMITIVE', fields)


class StartCommunicationTests(unittest.TestCase):
    def test_mcd_db_startcommunication_minimal(self):
        body = concat(primitive_body(), ObjectBytes().u16(0))
        self.assertEqual(load('MCD_DB_STARTCOMMUNICATION', body), typed(
            'MCD_DB_STARTCOMMUNICATION', {**primitive(), 'service_protocol_parameters': []}))

    def test_mcd_db_startcommunication_all_branches(self):
        body = concat(primitive_body(True), ObjectBytes().u16(2).ascii('P1').ascii('P2'))
        self.assertEqual(load('MCD_DB_STARTCOMMUNICATION', body), typed(
            'MCD_DB_STARTCOMMUNICATION',
            {**primitive(True), 'service_protocol_parameters': ['P1', 'P2']}))

    def test_mcd_db_startcommunication_suppression_without_path(self):
        body = concat(primitive_body(True, suppression='name'), ObjectBytes().u16(0))
        self.assertEqual(load('MCD_DB_STARTCOMMUNICATION', body), typed(
            'MCD_DB_STARTCOMMUNICATION',
            {**primitive(True, suppression='name'), 'service_protocol_parameters': []}))

    def test_mcd_db_startcommunication_empty_bytefield(self):
        body = concat(primitive_body(True, suppression='empty'), ObjectBytes().u16(0))
        self.assertEqual(load('MCD_DB_STARTCOMMUNICATION', body), typed(
            'MCD_DB_STARTCOMMUNICATION',
            {**primitive(True, suppression='empty'), 'service_protocol_parameters': []}))

    def test_mcd_db_startcommunication_transmission_modes(self):
        names = {0x6A01: 'eNO_TRANSMISSION', 0x6A02: 'eRECEIVE', 0x6A03: 'eSEND',
                 0x6A04: 'eSEND_AND_RECEIVE', 0x6A05: 'eSEND_OR_RECEIVE'}
        for code, name in names.items():
            with self.subTest(transmission_mode=name):
                body = concat(primitive_body(transmission=code), ObjectBytes().u16(0))
                self.assertEqual(load('MCD_DB_STARTCOMMUNICATION', body), typed(
                    'MCD_DB_STARTCOMMUNICATION',
                    {**primitive(transmission_mode=name), 'service_protocol_parameters': []}))


class StopCommunicationTests(unittest.TestCase):
    def test_mcd_db_stopcommunication_minimal(self):
        body = concat(primitive_body(), ObjectBytes().u16(0))
        self.assertEqual(load('MCD_DB_STOPCOMMUNICATION', body), typed(
            'MCD_DB_STOPCOMMUNICATION', {**primitive(), 'service_protocol_parameters': []}))

    def test_mcd_db_stopcommunication_all_branches(self):
        body = concat(primitive_body(True), ObjectBytes().u16(2).ascii('P1').ascii('P2'))
        self.assertEqual(load('MCD_DB_STOPCOMMUNICATION', body), typed(
            'MCD_DB_STOPCOMMUNICATION',
            {**primitive(True), 'service_protocol_parameters': ['P1', 'P2']}))


def service_body(full=False, addressing=2, runtime=0x6901):
    body = ObjectBytes().u8(addressing)
    if full:
        body.u16(2)
        body.ascii('Item1').nested('MCD_DB_REQUEST_PARAMETERS', two_parameters_body())
        body.ascii('Item2').absent()
    else:
        body.u16(0)
    body.u16(runtime).u8(1 if full else 0)
    return concat(body, data_primitive_body(full))


def service(full=False, addressing='ePHYSICAL', runtime='eNONCYCLIC'):
    items = []
    if full:
        items = [{'string': 'Item1', 'service_protocol_parameters': two_parameters()},
                 {'string': 'Item2', 'service_protocol_parameters': None}]
    return {'repetition_mode': addressing, 'items': items, 'runtime_mode': runtime,
            'is_multiple': full, 'data_primitive': data_primitive(full)}


class ServiceTests(unittest.TestCase):
    def test_mcd_db_service_minimal(self):
        self.assertEqual(load('MCD_DB_SERVICE', service_body()),
                         typed('MCD_DB_SERVICE', service()))

    def test_mcd_db_service_all_branches(self):
        self.assertEqual(load('MCD_DB_SERVICE', service_body(True)),
                         typed('MCD_DB_SERVICE', service(True)))

    def test_mcd_db_service_addressing_modes(self):
        names = {1: 'eUNDEFINED', 2: 'ePHYSICAL', 3: 'eFUNCTIONAL', 4: 'eFUNCTIONAL_OR_PHYSICAL'}
        for code, name in names.items():
            with self.subTest(addressing_mode=name):
                self.assertEqual(load('MCD_DB_SERVICE', service_body(addressing=code)),
                                 typed('MCD_DB_SERVICE', service(addressing=name)))

    def test_mcd_db_service_runtime_modes(self):
        names = {0x6901: 'eNONCYCLIC', 0x6902: 'eCYCLIC'}
        for code, name in names.items():
            with self.subTest(runtime_mode=name):
                self.assertEqual(load('MCD_DB_SERVICE', service_body(runtime=code)),
                                 typed('MCD_DB_SERVICE', service(runtime=name)))


def job_body(full=False):
    body = ObjectBytes().u32(1).u32(2).u32(3)
    if full:
        body.nested('MCD_DB_CODE_INFORMATIONS', ObjectBytes().u32(0))
    else:
        body.absent()
    return concat(body.u8(1 if full else 0), data_primitive_body(full))


def job(full=False):
    return {'major': 1, 'minor': 2, 'revision': 3,
            'db_code_informations': [] if full else None,
            'is_reduced_result_enabled': full, 'data_primitive': data_primitive(full)}


class SingleEcuJobTests(unittest.TestCase):
    def test_mcd_db_single_ecu_job_minimal(self):
        self.assertEqual(load('MCD_DB_SINGLE_ECU_JOB', job_body()),
                         typed('MCD_DB_SINGLE_ECU_JOB', job()))

    def test_mcd_db_single_ecu_job_all_branches(self):
        self.assertEqual(load('MCD_DB_SINGLE_ECU_JOB', job_body(True)),
                         typed('MCD_DB_SINGLE_ECU_JOB', job(True)))


class FlashJobTests(unittest.TestCase):
    def test_mcd_db_flash_job_minimal(self):
        self.assertEqual(load('MCD_DB_FLASH_JOB', job_body()),
                         typed('MCD_DB_FLASH_JOB', job()))

    def test_mcd_db_flash_job_all_branches(self):
        self.assertEqual(load('MCD_DB_FLASH_JOB', job_body(True)),
                         typed('MCD_DB_FLASH_JOB', job(True)))


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def matching_parameter_body(by_path=False):
    body = diag_com_ref_body(ObjectBytes(), by_path)
    body.u8(1 if by_path else 0).ascii('RESP').unicode('Expected')
    return body


def matching_parameter(by_path=False):
    fields = {'diag_com_primitive_ref': diag_com_ref(by_path)}
    fields['response_parameter_short_name_path' if by_path else 'response_parameter_name'] = 'RESP'
    fields['expected_value_string'] = 'Expected'
    return typed('MCD_DB_MATCHING_PARAMETER', fields)


class MatchingParameterTests(unittest.TestCase):
    def test_mcd_db_matching_parameter_minimal(self):
        self.assertEqual(load('MCD_DB_MATCHING_PARAMETER', matching_parameter_body()),
                         matching_parameter())

    def test_mcd_db_matching_parameter_all_branches(self):
        self.assertEqual(load('MCD_DB_MATCHING_PARAMETER', matching_parameter_body(True)),
                         matching_parameter(True))


def matching_parameters_body():
    return (ObjectBytes().u32(2).nested('MCD_DB_MATCHING_PARAMETER', matching_parameter_body())
            .nested('MCD_DB_MATCHING_PARAMETER', matching_parameter_body(True)))


def matching_parameters():
    return [matching_parameter(), matching_parameter(True)]


class MatchingParametersTests(unittest.TestCase):
    def test_mcd_db_matching_parameters_minimal(self):
        self.assertEqual(load('MCD_DB_MATCHING_PARAMETERS', ObjectBytes().u32(0)), [])

    def test_mcd_db_matching_parameters_all_branches(self):
        self.assertEqual(load('MCD_DB_MATCHING_PARAMETERS', matching_parameters_body()),
                         matching_parameters())


class MatchingPatternTests(unittest.TestCase):
    def test_mcd_db_matching_pattern_minimal(self):
        self.assertEqual(load('MCD_DB_MATCHING_PATTERN', ObjectBytes().absent()),
                         typed('MCD_DB_MATCHING_PATTERN', {'matching_parameters': None}))

    def test_mcd_db_matching_pattern_all_branches(self):
        body = ObjectBytes().nested('MCD_DB_MATCHING_PARAMETERS', matching_parameters_body())
        self.assertEqual(load('MCD_DB_MATCHING_PATTERN', body), typed(
            'MCD_DB_MATCHING_PATTERN', {'matching_parameters': matching_parameters()}))


class MatchingPatternsTests(unittest.TestCase):
    def test_mcd_db_matching_patterns_minimal(self):
        self.assertEqual(load('MCD_DB_MATCHING_PATTERNS', ObjectBytes().u32(0)), [])

    def test_mcd_db_matching_patterns_all_branches(self):
        body = (ObjectBytes().u32(2).nested('MCD_DB_MATCHING_PATTERN', ObjectBytes().absent())
                .nested('MCD_DB_MATCHING_PATTERN', ObjectBytes().nested(
                    'MCD_DB_MATCHING_PARAMETERS', matching_parameters_body())))
        self.assertEqual(load('MCD_DB_MATCHING_PATTERNS', body), [
            typed('MCD_DB_MATCHING_PATTERN', {'matching_parameters': None}),
            typed('MCD_DB_MATCHING_PATTERN', {'matching_parameters': matching_parameters()})])


class MatchingRequestParameterTests(unittest.TestCase):
    def test_mcd_db_matching_request_parameter_minimal(self):
        body = concat(parameter_body(), ObjectBytes().u32(2).u32(3))
        self.assertEqual(load('MCD_DB_MATCHING_REQUEST_PARAMETER', body), typed(
            'MCD_DB_MATCHING_REQUEST_PARAMETER',
            {**parameter(), 'request_byte_position': 2, 'byte_length': 3}))

    def test_mcd_db_matching_request_parameter_all_branches(self):
        body = concat(parameter_body(**PARAMETER_ALL), ObjectBytes().u32(2).u32(3))
        self.assertEqual(load('MCD_DB_MATCHING_REQUEST_PARAMETER', body), typed(
            'MCD_DB_MATCHING_REQUEST_PARAMETER',
            {**parameter_all(), 'request_byte_position': 2, 'byte_length': 3}))


if __name__ == '__main__':
    unittest.main()
