"""Builders for the table scripts' test data: services, tables, rows and structures.

Each function returns a raw object as the object loader delivers it (pool 'POOL'), with every field that
parse_dop and the scripts read. Everything here is invented data.
"""
from tests.script_support import layer

POOL = 'POOL'
UDS_TYPE = 'ISO_15765_3_on_ISO_15765_2'


def ref(object_id):
    return {'pool_id': POOL, 'object_id': object_id}


def coded_type(bit_length=8):
    return {'is_condensed_bit_mask': False, 'base_data_type_as_mcd_data_type': 'eA_UINT32',
            'coded_type': 'eSTANDARD_LENGTH_TYPE', 'bit_length': bit_length, 'bit_mask': bytearray(),
            'encoding': 'eNONE', 'is_high_low_byte_order': True}


def physical_type(base='eA_UINT32'):
    return {'base_data_type_as_mcd_data_type': base, 'display_radix': 10, 'is_precision_available': False}


def uint_dop(bit_length=8):
    """Simple DOP: A_UINT32 coded to A_UINT32 physical, IDENTICAL, standard length."""
    return {'#OBJECT_TYPE': 'DB_DOP_SIMPLE_BASE', 'diag_coded_type': coded_type(bit_length),
            'physical_type': physical_type(),
            'compu_method': {'compu_category': 'eIDENTICAL', 'compu_internal_to_phys': None,
                             'compu_phys_to_internal': None}}


def texttable_dop(scales, bit_length=8, physical='eA_UNICODE2STRING'):
    """Simple DOP with a TEXTTABLE; scales is a list of (coded value, text)."""
    compu_scales = []
    for coded, text in scales:
        limit = {'limit_type': 'eLIMIT_CLOSED', 'limit': {'data_type': 'eA_UINT32', 'value': coded}}
        compu_scales.append({'lower_limit_as_coded_value': limit, 'upper_limit_as_coded_value': dict(limit),
                             'compu_constant': {'data_type': physical, 'value': text},
                             'long_name_id': 'ID_' + str(text)})
    dop = uint_dop(bit_length)
    dop['physical_type'] = physical_type(physical)
    dop['compu_method'] = {'compu_category': 'eTEXTTAB',
                           'compu_internal_to_phys': {'compu_scales': compu_scales, 'compu_default_value': None},
                           'compu_phys_to_internal': None}
    return dop


def key_dop_names(scales):
    """Key DOP of the name family: the key values are texts, two bytes wide."""
    return texttable_dop(scales, bit_length=16)


def key_dop_decimal():
    """Key DOP of the decimal family: a plain two byte unsigned number."""
    return uint_dop(bit_length=16)


def value_parameter(long_name, byte_position, dop_reference, bit_position=0, default=None,
                    object_type='MCD_DB_PARAMETER', **fields):
    parameter = {'#OBJECT_TYPE': object_type, 'short_name': long_name, 'long_name': long_name,
                 'long_name_id': 'ID_' + long_name, 'description': None, 'description_id': None,
                 'is_byte_position_available': True, 'byte_position': byte_position,
                 'bit_position': bit_position, 'default_value': default, 'mcd_parameter_type': 'eVALUE',
                 'dop_base_reference': dop_reference}
    parameter.update(fields)
    return parameter


def structure(long_name, parameters, byte_length=0):
    return {'#OBJECT_TYPE': 'MCD_DB_PARAMETER_STRUCTURE', 'long_name': long_name, 'description': None,
            'byte_length': byte_length, 'parameters': parameters}


def table_row(short_name, long_name, key, structure_reference, default=None):
    row = value_parameter(long_name, 0, structure_reference, default=default,
                          object_type='MCD_DB_TABLE_PARAMETER', short_name=short_name)
    row['key'] = key
    return row


def table(key_dop_reference, rows):
    """Table; rows is a list of (map key, row reference) in table_key_map."""
    return {'#OBJECT_TYPE': 'MCD_DB_TABLE', 'dop_simple_reference': key_dop_reference,
            'table_key_map': [{'map_key': map_key, 'reference': row_reference}
                              for map_key, row_reference in rows]}


def table_key_parameter(table_reference, byte_position=1, row_short_name=None):
    return value_parameter('Key', byte_position, None, object_type='MCD_DB_PARAMETER_TABLE_KEY',
                           short_name='TK', table_reference=table_reference,
                           is_table_row_reference=row_short_name is not None,
                           row_reference_short_name=row_short_name)


def table_struct_parameter(table_reference, key_short_name='TK', byte_position=3):
    return value_parameter('Data', byte_position, None, object_type='MCD_DB_PARAMETER_TABLESTRUCT',
                           short_name='TS', table_reference=table_reference,
                           key_parameter_short_name=key_short_name)


def sid_parameter(sid):
    return value_parameter('SID', 0, None, object_type='MCD_DB_PARAMETER',
                           mcd_parameter_type='eCODED_CONST',
                           default={'data_type': 'eA_UINT32', 'value': sid},
                           diag_coded_type=coded_type())


def service_objects(name, request_parameters, response_parameters_list):
    """Objects of a service, its request and one positive response per entry of response_parameters_list."""
    service_id = 'service ' + name
    request_id = 'request ' + name
    response_ids = ['response {} {}'.format(name, index) for index in range(len(response_parameters_list))]
    objects = {
        (POOL, service_id): {'#OBJECT_TYPE': 'MCD_DB_SERVICE', 'request_reference': ref(request_id),
                             'positive_response_references': [{'map_key': response_id, 'reference': ref(response_id)}
                                                              for response_id in response_ids]},
        (POOL, request_id): {'request_parameters': request_parameters}}
    for response_id, parameters in zip(response_ids, response_parameters_list):
        objects[(POOL, response_id)] = {'response_parameters': parameters}
    return objects


def diag_com(name):
    return {'map_key': name, 'reference': ref('service ' + name)}


def base_variant_objects(ecu_variants=('EV',), base_variant_layer=None):
    """Project data and layer data of the base variant BV.bv with the UDS protocol layer PR.pr."""
    return {
        ('BV.bv', '#RtGen_DB_LAYER_DATA'): base_variant_layer or layer(name='BV', parent_layers=['PR.pr']),
        ('BV.bv', '#RtGen_DB_PROJECT_DATA'): {
            'ecu_variant_references': [{'name': name, 'reference': name + '-reference'} for name in ecu_variants],
            'base_variant_reference': {'object_id': 'BV'}},
        ('PR.pr', '#RtGen_DB_LAYER_DATA'): layer(name='PR', protocol_type=UDS_TYPE)}
