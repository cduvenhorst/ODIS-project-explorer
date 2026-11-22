"""PARAMS and PARAM of structures, environment data, requests and responses."""
from odx_export import special_data
from odx_export.data_objects import add_diag_coded_type
from odx_export.elements import XSI_TYPE, add_names, add_ref, format_value, sub

PTYPE = {'eCODED_CONST': 'CODED-CONST', 'eVALUE': 'VALUE', 'ePHYS_CONST': 'PHYS-CONST', 'eRESERVED': 'RESERVED',
         'eLENGTH_KEY': 'LENGTH-KEY', 'eTABLE_KEY': 'TABLE-KEY', 'eTABLE_STRUCT': 'TABLE-STRUCT',
         'eMATCHING_REQUEST_PARAM': 'MATCHING-REQUEST-PARAM', 'eNRC_CONST': 'NRC-CONST', 'eSYSTEM': 'SYSTEM'}
# Only these kinds carry an ID; other parameters are never referenced by ID.
_IDENTIFIED_KINDS = ('TABLE-KEY', 'LENGTH-KEY')


def _kind(ctx, parameter_type):
    """xsi:type of a pool parameter type; an unknown one keeps its pool name without the 'e' and is counted."""
    if parameter_type in PTYPE:
        return PTYPE[parameter_type]
    ctx.report['unknown_parameter_types'] += 1
    text = str(parameter_type)
    return text[1:] if text.startswith('e') else text


def _add_dop_ref(ctx, element, parameter):
    # A DOP reference whose flag is not set is absent, not an empty reference.
    if parameter.get('dop_base_reference') is not None:
        add_ref(ctx, element, 'DOP-REF', parameter['dop_base_reference'])


def _add_value(ctx, element, tag, value):
    if value is not None:
        sub(ctx, element, tag, format_value(value))


def _add_coded_type(ctx, element, parameter, owner_id):
    if parameter.get('diag_coded_type') is not None:
        add_diag_coded_type(ctx, element, parameter['diag_coded_type'], owner_id)


def _add_table_key_ref(ctx, element, parameter):
    reference = parameter.get('table_reference')
    # The table reference is not set when the pool embeds the table object; ODX has no place for that.
    if reference is None:
        return
    object_id = reference.get('object_id') or ''
    if parameter.get('is_table_row_reference') or object_id.startswith('TBP_'):
        add_ref(ctx, element, 'TABLE-ROW-REF', reference)
    else:
        add_ref(ctx, element, 'TABLE-REF', reference)


def add_param(ctx, parent, parameter, owner_id):
    kind = _kind(ctx, parameter['mcd_parameter_type'])
    attributes = {XSI_TYPE: kind, 'SEMANTIC': parameter.get('semantic')}
    if kind in _IDENTIFIED_KINDS:
        attributes['ID'] = owner_id + '.' + parameter['short_name']
    # Every parameter keeps its object ID, also without ID: the original documents carry it on each PARAM.
    attributes['OID'] = parameter.get('unique_object_id') or None
    if kind == 'SYSTEM':
        # ODX form from the standard; no original document to compare (survey)
        attributes['SYSPARAM'] = parameter.get('system_parameter')
    element = sub(ctx, parent, 'PARAM', attributes=attributes)
    add_names(ctx, element, parameter)
    special_data.sdgs(ctx, element, parameter)
    if parameter.get('is_byte_position_available'):
        sub(ctx, element, 'BYTE-POSITION', str(parameter['byte_position']))
    if parameter.get('bit_position'):
        sub(ctx, element, 'BIT-POSITION', str(parameter['bit_position']))
    if kind == 'CODED-CONST':
        _add_value(ctx, element, 'CODED-VALUE', parameter.get('default_value'))
        _add_coded_type(ctx, element, parameter, owner_id)
    elif kind == 'NRC-CONST':
        # ODX form from the standard; no original document to compare (survey)
        values = [value for value in parameter.get('nrc_constant_values') or [] if value is not None]
        if values:
            values_element = sub(ctx, element, 'CODED-VALUES')
            for value in values:
                sub(ctx, values_element, 'CODED-VALUE', format_value(value))
        _add_coded_type(ctx, element, parameter, owner_id)
    elif kind == 'VALUE':
        _add_value(ctx, element, 'PHYSICAL-DEFAULT-VALUE', parameter.get('default_value'))
        _add_dop_ref(ctx, element, parameter)
    elif kind == 'PHYS-CONST':
        _add_value(ctx, element, 'PHYS-CONSTANT-VALUE', parameter.get('default_value'))
        _add_dop_ref(ctx, element, parameter)
    elif kind == 'RESERVED':
        if parameter.get('diag_coded_type') is not None:
            sub(ctx, element, 'BIT-LENGTH', str(parameter['diag_coded_type']['bit_length']))
    elif kind in ('LENGTH-KEY', 'SYSTEM'):
        _add_dop_ref(ctx, element, parameter)
    elif kind == 'MATCHING-REQUEST-PARAM':
        sub(ctx, element, 'REQUEST-BYTE-POS', str(parameter['request_byte_position']))
        sub(ctx, element, 'BYTE-LENGTH', str(parameter['byte_length']))
    elif kind == 'TABLE-KEY':
        _add_table_key_ref(ctx, element, parameter)
    elif kind == 'TABLE-STRUCT':
        sub(ctx, element, 'TABLE-KEY-REF', ID_REF=owner_id + '.' + parameter['key_parameter_short_name'])
    return element


def add_params(ctx, parent, parameters, owner_id):
    """Append PARAMS with one PARAM per parameter, or return None when there is none."""
    present = [parameter for parameter in parameters or [] if parameter]
    if not present:
        return None
    element = sub(ctx, parent, 'PARAMS')
    for parameter in present:
        add_param(ctx, element, parameter, owner_id)
    return element
