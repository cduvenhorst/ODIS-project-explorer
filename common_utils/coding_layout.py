# Flat coding layout: absolute byte positions, ODX bit positions, value lists, defaults and notes,
# computed from an already parsed coding entry (see common_utils/table_entries.py) without any object loader.

LEAF_PARAMETER_TYPES = ('VALUE', 'RESERVED', 'CODED-CONST', 'PHYS-CONST')
NO_POSITION_NOTE = 'No BYTE-POSITION, position not computed'


def flatten_coding_entry(entry):
    structure = entry['structure']
    if structure.get('#error') is not None or structure.get('type') != 'STRUCTURE':
        return {'byte_length': None, 'note': 'Structure not available', 'fields': []}

    # kernel: a row parameter without position starts at the beginning of the coding data
    base = entry['byte_position'] if entry['byte_position'] is not None else 0
    fields = []
    _flatten_structure(structure, base, fields)

    byte_length = structure['byte_size']
    note = None
    if byte_length is None:
        byte_length = _computed_length(fields)
        if byte_length is None:
            note = 'Length is not fixed'
    # The helper key is only needed for the computed length; it is removed in every case
    for field in fields:
        del field['_standard_length']
    return {'byte_length': byte_length, 'note': note, 'fields': fields}


def _flatten_structure(structure, base, fields):
    for parameter in structure['parameters']:
        own_position = parameter['byte_position']
        dop = parameter.get('dop') or {}

        if dop.get('type') == 'STRUCTURE':
            inner_base = base + own_position if base is not None and own_position is not None else None
            _flatten_structure(dop, inner_base, fields)
            continue

        field = {
            'byte_position': None,
            'bit_position': parameter['bit_position'],
            'bit_length': None,
            'bit_mask': None,
            'long_name': parameter['long_name'],
            'long_name_id': parameter['long_name_id'],
            'parameter_type': parameter['parameter_type'],
            'values': [],
            'default': None,
            'note': None,
            '_standard_length': False,
        }
        if base is not None and own_position is not None:
            field['byte_position'] = base + own_position

        parameter_type = parameter['parameter_type']
        if parameter_type not in LEAF_PARAMETER_TYPES:
            field['note'] = 'Parameter type {} not expected in coding structure'.format(parameter_type)
        elif '#error' in dop:
            field['note'] = 'DOP not available'
        elif dop.get('type') != 'DOP':
            field['note'] = '{} not expanded'.format(dop.get('type'))
        else:
            field['bit_length'] = dop.get('bit_length')
            field['bit_mask'] = dop.get('bit_mask')
            field['_standard_length'] = dop.get('diag_coded_type') == 'STANDARD-LENGTH-TYPE'
            if dop.get('compu_category') == 'TEXTTABLE':
                field['values'] = [{'lower_limit': scale['lower_limit'],
                                    'upper_limit': scale['upper_limit'],
                                    'text': scale['long_name'],
                                    'text_id': scale['long_name_id']}
                                   for scale in dop['compu_scales']]
            if parameter_type in ('VALUE', 'RESERVED'):
                field['default'] = parameter.get('default_value')
            else:
                field['default'] = parameter.get('constant')
        if field['note'] is None and field['byte_position'] is None:
            field['note'] = NO_POSITION_NOTE
        fields.append(field)


def _computed_length(fields):
    length = 0
    for field in fields:
        if (not field['_standard_length'] or field['byte_position'] is None
                or field['note'] is not None or field['bit_length'] is None):
            length = None
            break
        end = field['byte_position'] + (field['bit_position'] + field['bit_length'] + 7) // 8
        length = max(length, end)
    return length
