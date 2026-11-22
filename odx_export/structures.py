"""STRUCTURE, the fields, MUX, ENV-DATA-DESC and ENV-DATA."""
import xml.etree.ElementTree as ET

from odx_export import special_data
from odx_export.data_objects import add_limit
from odx_export.elements import add_names, add_ref, identified, sub
from odx_export.parameters import add_params

_DEFAULT_MAX_NUMBER_OF_ITEMS = 0xFFFFFFFF


def add_structure(ctx, parent, key):
    structure = ctx.take(key)
    structure_id = ctx.own_id(key)
    element = identified(ctx, parent, 'STRUCTURE', structure_id, structure)
    add_names(ctx, element, structure)
    special_data.sdgs(ctx, element, structure)
    if structure.get('byte_length'):
        sub(ctx, element, 'BYTE-SIZE', str(structure['byte_length']))
    add_params(ctx, element, structure.get('parameters'), structure_id)
    return element


def _add_field(ctx, parent, tag, key):
    """Field head: ID, SHORT-NAME from the ID part of the key, SDGS and the structure reference."""
    field = ctx.take(key)
    field_id = ctx.own_id(key)
    element = identified(ctx, parent, tag, field_id, field)
    sub(ctx, element, 'SHORT-NAME', field_id)
    special_data.sdgs(ctx, element, field)
    # The pool sets exactly one of the two references; the other one is absent.
    if field.get('dop_structure_reference') is not None:
        add_ref(ctx, element, 'BASIC-STRUCTURE-REF', field['dop_structure_reference'])
    elif field.get('dop_env_data_desc_reference') is not None:
        add_ref(ctx, element, 'ENV-DATA-DESC-REF', field['dop_env_data_desc_reference'])
    return field, element


def add_static_field(ctx, parent, key):
    # ODX form from the standard; no original document to compare (survey)
    field, element = _add_field(ctx, parent, 'STATIC-FIELD', key)
    sub(ctx, element, 'FIXED-NUMBER-OF-ITEMS', str(field['fixed_number_of_items']))
    sub(ctx, element, 'ITEM-BYTE-SIZE', str(field['item_byte_size']))
    return element


def add_dynamic_length_field(ctx, parent, key):
    field, element = _add_field(ctx, parent, 'DYNAMIC-LENGTH-FIELD', key)
    sub(ctx, element, 'OFFSET', str(field['offset']))
    determine = sub(ctx, element, 'DETERMINE-NUMBER-OF-ITEMS')
    sub(ctx, determine, 'BYTE-POSITION', str(field['simple_byte_position']))
    if field.get('simple_bit_position'):
        sub(ctx, determine, 'BIT-POSITION', str(field['simple_bit_position']))
    add_ref(ctx, determine, 'DATA-OBJECT-PROP-REF', field.get('dop_base_reference'))
    return element


def add_end_of_pdu_field(ctx, parent, key):
    field, element = _add_field(ctx, parent, 'END-OF-PDU-FIELD', key)
    if field['max_number_of_items'] != _DEFAULT_MAX_NUMBER_OF_ITEMS:
        sub(ctx, element, 'MAX-NUMBER-OF-ITEMS', str(field['max_number_of_items']))
    # Written also when it is 0: the original documents mostly carry it.
    sub(ctx, element, 'MIN-NUMBER-OF-ITEMS', str(field['min_number_of_items']))
    return element


def _add_case(ctx, parent, tag, case):
    element = sub(ctx, parent, tag)
    add_names(ctx, element, case)
    # A structure reference whose flag is not set is absent, not an empty reference.
    if case.get('structure_dop_reference') is not None:
        add_ref(ctx, element, 'STRUCTURE-REF', case['structure_dop_reference'])
    return element


def add_mux(ctx, parent, key):
    mux = ctx.take(key)
    mux_id = ctx.own_id(key)
    element = identified(ctx, parent, 'MUX', mux_id, mux)
    sub(ctx, element, 'SHORT-NAME', mux_id)
    special_data.sdgs(ctx, element, mux)
    sub(ctx, element, 'BYTE-POSITION', str(mux['offset']))
    switch_key = mux.get('switch_key')
    if switch_key is not None:
        switch_element = sub(ctx, element, 'SWITCH-KEY')
        sub(ctx, switch_element, 'BYTE-POSITION', str(switch_key['byte_position']))
        if switch_key.get('bit_position'):
            sub(ctx, switch_element, 'BIT-POSITION', str(switch_key['bit_position']))
        add_ref(ctx, switch_element, 'DATA-OBJECT-PROP-REF', switch_key.get('dop_base_reference'))
    if mux.get('default_case') is not None:
        _add_case(ctx, element, 'DEFAULT-CASE', mux['default_case'])
    cases = [case for case in mux.get('cases') or [] if case]
    if cases:
        cases_element = sub(ctx, element, 'CASES')
        for case in cases:
            case_element = _add_case(ctx, cases_element, 'CASE', case)
            for tag, field in (('LOWER-LIMIT', 'lower_limit'), ('UPPER-LIMIT', 'upper_limit')):
                if case[field] is not None:
                    add_limit(ctx, case_element, tag, case[field].get('limit'), case[field].get('limit_type'))
    return element


def add_env_data_desc(ctx, parent, key):
    outer = ctx.take(key)
    desc = outer['env_data_desc']
    element = identified(ctx, parent, 'ENV-DATA-DESC', ctx.own_id(key), desc)
    add_names(ctx, element, desc)
    special_data.sdgs(ctx, element, desc)
    if outer.get('is_parameter_short_name_path_available'):
        sub(ctx, element, 'PARAM-SNPATHREF', SHORT_NAME_PATH=outer['parameter_short_name_path'])
    else:
        sub(ctx, element, 'PARAM-SNREF', SHORT_NAME=outer['parameter_name'])
    # ENV-DATA-REFS needs at least one ENV-DATA-REF; it is appended only when one was written.
    refs = ET.Element('ENV-DATA-REFS')
    all_value = desc.get('all_value_env_data_parameter')
    if all_value and all_value.get('dop_base_reference') is not None:
        add_ref(ctx, refs, 'ENV-DATA-REF', all_value['dop_base_reference'])
    if len(refs):
        element.append(refs)
    return element


def add_env_data(ctx, parent, key, all_value):
    """ENV-DATA; with the all-value parameter of its description it takes that parameter's names."""
    env_data = ctx.take(key)
    env_data_id = ctx.own_id(key)
    named = all_value if all_value else env_data
    element = identified(ctx, parent, 'ENV-DATA', env_data_id, named)
    if all_value:
        add_names(ctx, element, all_value)
    else:
        sub(ctx, element, 'SHORT-NAME', env_data_id)
    special_data.sdgs(ctx, element, named)
    add_params(ctx, element, env_data.get('parameters'), env_data_id)
    if all_value:
        sub(ctx, element, 'ALL-VALUE')
    return element
