"""DATA-OBJECT-PROP with its coded type, compu method, physical type and constraints, and UNIT-SPEC."""
import xml.etree.ElementTree as ET

from odx_export import special_data
from odx_export.elements import XSI_TYPE, add_desc, add_names, add_ref, format_value, identified, sub
from odx_export.naming import split_key

ENC = {'eISO_8859_1': 'ISO-8859-1', 'e2C': '2C', 'eBCD_P': 'BCD-P', 'eBCD_UP': 'BCD-UP', 'eUTF_8': 'UTF-8',
       'eUCS_2': 'UCS-2', 'e1C': '1C', 'eSM': 'SM', 'eISO_8859_2': 'ISO-8859-2', 'eWINDOWS_1252': 'WINDOWS-1252',
       'eIEEE754': 'IEEE754'}
CT = {'eSTANDARD_LENGTH_TYPE': 'STANDARD-LENGTH-TYPE', 'eMIN_MAX_LENGTH_TYPE': 'MIN-MAX-LENGTH-TYPE',
      'eLEADING_LENGTH_INFO_TYPE': 'LEADING-LENGTH-INFO-TYPE', 'ePARAM_LENGTH_INFO_TYPE': 'PARAM-LENGTH-INFO-TYPE'}
CC = {'eIDENTICAL': 'IDENTICAL', 'eLINEAR': 'LINEAR', 'eTEXTTAB': 'TEXTTABLE', 'eTAB_INTP': 'TAB-INTP',
      'eSCALE_LINEAR': 'SCALE-LINEAR', 'eRAT_FUNC': 'RAT-FUNC', 'eSCALE_RAT_FUNC': 'SCALE-RAT-FUNC',
      'eCOMPUCODE': 'COMPUCODE'}
RADIX = {10: 'DEC', 16: 'HEX', 2: 'BIN', 8: 'OCT'}
VALID = {'eVALUE_NOT_AVAILABLE': 'NOT-AVAILABLE', 'eVALUE_NOT_DEFINED': 'NOT-DEFINED', 'eVALUE_NOT_VALID': 'NOT-VALID',
         'eVALUE_VALID': 'VALID'}
# A closed limit is the ODX default and is not written.
LIMT = {'eLIMIT_OPEN': 'OPEN', 'eLIMIT_INFINITE': 'INFINITE', 'eLIMIT_CLOSED': None}
UGCAT = {'eEQUIVALENT_UNITS': 'EQUIV-UNITS', 'eCOUNTRY': 'COUNTRY'}
TERMINATION = {'eENDOFPDU': 'END-OF-PDU', 'eZERO': 'ZERO', 'eHEX_FF': 'HEX-FF'}

# Encodings the converter adds to these base data types; the original documents do not carry them.
_CONVERTER_ENCODINGS = {('eDB_ASCIISTRING', 'eISO_8859_1'), ('eDB_INT32', 'e2C')}
_DEFAULT_MAX_LENGTH = 65535
# The converter adds these internal limits next to scale constraints.
_FULL_RANGE = ('0', '4294967295')
_DEC_RADIX_COMMENT = ' DISPLAY-RADIX not present: pool value DEC '
_PARAMETER_FIELDS = ('parameters', 'request_parameters', 'response_parameters')
_STRING_VALUE_TYPES = ('eA_UNICODE2STRING', 'eA_ASCIISTRING')
_EXPONENTS = (('LENGTH-EXP', 'length_exponent'), ('MASS-EXP', 'mass_exponent'), ('TIME-EXP', 'time_exponent'),
              ('CURRENT-EXP', 'current_exponent'), ('TEMPERATURE-EXP', 'temperature_exponent'),
              ('MOLAR-AMOUNT-EXP', 'molar_amount_exponent'), ('LUMINOUS-INTENSITY-EXP', 'luminous_intensity'))


def _mapped(ctx, table, key):
    """ODX text of a pool enumeration value; an unmapped value gives None and is counted."""
    if key in table:
        return table[key]
    ctx.report['unmapped_enumerations'] += 1
    return None


def _data_type(ctx, base_data_type, prefix):
    """'eDB_UINT32' -> 'A_UINT32'; a value kept as its number gives None and is counted."""
    if isinstance(base_data_type, str) and base_data_type.startswith(prefix):
        return 'A_' + base_data_type[len(prefix):]
    ctx.report['unmapped_enumerations'] += 1
    return None


def _add_limit(ctx, parent, tag, limit_value, limit_type):
    """Append LOWER-LIMIT or UPPER-LIMIT; an infinite limit without value is the converter's and is dropped."""
    if limit_type == 'eLIMIT_INFINITE' and limit_value is None:
        return None
    return sub(ctx, parent, tag, format_value(limit_value),
               INTERVAL_TYPE=_mapped(ctx, LIMT, limit_type))


def _value_tag(value, physical_base_type=None):
    """VT for text values, V otherwise; the physical base type decides when it is known."""
    if physical_base_type:
        return 'VT' if physical_base_type == 'eDB_PHYS_UNICODE2STRING' else 'V'
    return 'VT' if value.get('data_type') in _STRING_VALUE_TYPES else 'V'


def length_key_owners(ctx):
    """unique_object_id of every parameter of the pool -> ID of the object that holds it."""
    owners = {}
    for key, obj in ctx.objects.items():
        if not isinstance(obj, dict):
            continue
        parts = split_key(key, ctx.layer)
        owner_id = parts[1] if parts else key
        for field in _PARAMETER_FIELDS:
            for parameter in obj.get(field) or []:
                if parameter and parameter.get('unique_object_id'):
                    owners[parameter['unique_object_id']] = owner_id
    return owners


def _length_key_owner(ctx, unique_object_id):
    # Computed once per context; length_key_owners itself stays a pure function.
    owners = getattr(ctx, '_length_key_owners', None)
    if owners is None:
        owners = length_key_owners(ctx)
        ctx._length_key_owners = owners
    return owners.get(unique_object_id)


def add_diag_coded_type(ctx, parent, coded_type, owner_id=None):
    kind = coded_type['coded_type']
    base_data_type = coded_type['base_data_type']
    encoding = coded_type['encoding']
    if encoding == 'eNONE' or (base_data_type, encoding) in _CONVERTER_ENCODINGS:
        encoding_text = None
    else:
        encoding_text = _mapped(ctx, ENC, encoding)
    termination = coded_type.get('termination')
    element = sub(ctx, parent, 'DIAG-CODED-TYPE', attributes={
        XSI_TYPE: _mapped(ctx, CT, kind),
        'BASE-DATA-TYPE': _data_type(ctx, base_data_type, 'eDB_'),
        'BASE-TYPE-ENCODING': encoding_text,
        'IS-HIGHLOW-BYTE-ORDER': None if coded_type['is_high_low_byte_order'] else 'false',
        'TERMINATION': None if termination is None else _mapped(ctx, TERMINATION, termination)})
    if kind in ('eSTANDARD_LENGTH_TYPE', 'eLEADING_LENGTH_INFO_TYPE'):
        sub(ctx, element, 'BIT-LENGTH', str(coded_type['bit_length']))
        if coded_type.get('bit_mask'):
            sub(ctx, element, 'BIT-MASK', format_value(bytes(coded_type['bit_mask'])))
    elif kind == 'eMIN_MAX_LENGTH_TYPE':
        if coded_type['max_length'] != _DEFAULT_MAX_LENGTH:
            sub(ctx, element, 'MAX-LENGTH', str(coded_type['max_length']))
        sub(ctx, element, 'MIN-LENGTH', str(coded_type['min_length']))
    elif kind == 'ePARAM_LENGTH_INFO_TYPE':
        length_key = coded_type.get('length_key_parameter')
        if not length_key:
            ctx.report['empty_references'] += 1
            return element
        owner = _length_key_owner(ctx, length_key.get('unique_object_id')) or owner_id
        if owner is None:
            ctx.report['unresolvable_references'] += 1
            id_ref = length_key['short_name']
        else:
            id_ref = owner + '.' + length_key['short_name']
        sub(ctx, element, 'LENGTH-KEY-REF', ID_REF=id_ref)
    return element


def _add_compu_scale(ctx, parent, compu_scale, category, physical_base_type):
    element = sub(ctx, parent, 'COMPU-SCALE')
    lower = compu_scale.get('lower_limit_as_coded_value')
    upper = compu_scale.get('upper_limit_as_coded_value')
    if lower is not None:
        _add_limit(ctx, element, 'LOWER-LIMIT', lower.get('limit'), lower.get('limit_type'))
    # TEXTTABLE: an upper limit equal to the lower one is the ODX default.
    # TAB-INTP: open upper limits are added by the converter.
    if upper is not None and not (category == 'eTEXTTAB' and upper == lower) \
            and not (category == 'eTAB_INTP' and upper.get('limit_type') == 'eLIMIT_OPEN'):
        _add_limit(ctx, element, 'UPPER-LIMIT', upper.get('limit'), upper.get('limit_type'))
    inverse = compu_scale.get('compu_inverse_value')
    # TAB-INTP: the inverse values are added by the converter.
    if inverse is not None and category != 'eTAB_INTP':
        # The inverse value is an internal value; the physical base type does not describe it.
        sub(ctx, sub(ctx, element, 'COMPU-INVERSE-VALUE'), _value_tag(inverse), format_value(inverse))
    constant = compu_scale.get('compu_constant')
    coeffs = compu_scale.get('compu_rational_coeffs_as_coded_values')
    if constant is not None:
        sub(ctx, sub(ctx, element, 'COMPU-CONST'), _value_tag(constant, physical_base_type),
            format_value(constant), TI=compu_scale.get('long_name_id') or None)
    elif coeffs and (coeffs['numerator'] or coeffs['denominator']):
        coeffs_element = sub(ctx, element, 'COMPU-RATIONAL-COEFFS')
        for tag, field in (('COMPU-NUMERATOR', 'numerator'), ('COMPU-DENOMINATOR', 'denominator')):
            if coeffs[field]:
                part = sub(ctx, coeffs_element, tag)
                for coefficient in coeffs[field]:
                    sub(ctx, part, 'V', format_value(coefficient))
    return element


def add_compu_method(ctx, parent, compu_method, physical_base_type=None):
    element = sub(ctx, parent, 'COMPU-METHOD')
    category = compu_method['compu_category']
    category_text = _mapped(ctx, CC, category)
    if category_text is not None:
        sub(ctx, element, 'CATEGORY', category_text)
    internal_to_phys = compu_method.get('compu_internal_to_phys')
    if internal_to_phys is None:
        return element
    internal_element = sub(ctx, element, 'COMPU-INTERNAL-TO-PHYS')
    compu_scales = [compu_scale for compu_scale in internal_to_phys.get('compu_scales') or [] if compu_scale]
    if compu_scales:
        scales_element = sub(ctx, internal_element, 'COMPU-SCALES')
        for compu_scale in compu_scales:
            _add_compu_scale(ctx, scales_element, compu_scale, category, physical_base_type)
    default = internal_to_phys.get('compu_default_value')
    if default is not None:
        sub(ctx, sub(ctx, internal_element, 'COMPU-DEFAULT-VALUE'), _value_tag(default, physical_base_type),
            format_value(default), TI=compu_method.get('compu_default_value_id') or None)
    return element


def add_physical_type(ctx, parent, physical_type):
    radix = physical_type['display_radix']
    radix_text = None
    if radix != 10:
        radix_text = _mapped(ctx, RADIX, radix)
    element = sub(ctx, parent, 'PHYSICAL-TYPE',
                  BASE_DATA_TYPE=_data_type(ctx, physical_type['base_data_type'], 'eDB_PHYS_'),
                  DISPLAY_RADIX=radix_text)
    if radix == 10:
        # DEC is the ODX default; it is marked as not present instead of being dropped silently.
        element.append(ET.Comment(_DEC_RADIX_COMMENT))
        ctx.report['omitted_display_radix'] += 1
    if physical_type['is_precision_available']:
        sub(ctx, element, 'PRECISION', str(physical_type['precision']))
    return element


def _add_interval(ctx, parent, interval):
    _add_limit(ctx, parent, 'LOWER-LIMIT', interval['lower_limit'], interval['lower_limit_interval_type'])
    _add_limit(ctx, parent, 'UPPER-LIMIT', interval['upper_limit'], interval['upper_limit_interval_type'])


def add_constraint(ctx, parent, tag, reference):
    """Append INTERNAL-CONSTR or PHYS-CONSTR from the referenced constraint of this pool."""
    # A field whose flag is not set is absent, not an empty reference; only an empty object_id counts.
    if reference is None:
        return None
    key = reference.get('object_id')
    if not key:
        ctx.report['empty_references'] += 1
        return None
    if reference.get('pool_id') != ctx.pool_id or key not in ctx.objects:
        ctx.report['unresolvable_references'] += 1
        return None
    constraint = ctx.take(key)
    # Computed constraints are added by the converter.
    if constraint.get('is_computed'):
        return None
    element = sub(ctx, parent, tag)
    interval = constraint.get('interval')
    scale_constraints = [entry for entry in constraint.get('scale_constraints') or [] if entry]
    if interval is not None:
        limits = (format_value(interval['lower_limit']), format_value(interval['upper_limit']))
        if not (scale_constraints and limits == _FULL_RANGE):
            _add_interval(ctx, element, interval)
    if scale_constraints:
        scales_element = sub(ctx, element, 'SCALE-CONSTRS')
        for scale_constraint in scale_constraints:
            scale_element = sub(ctx, scales_element, 'SCALE-CONSTR',
                                VALIDITY=_mapped(ctx, VALID, scale_constraint['range_info']))
            if scale_constraint.get('short_label') is not None:
                sub(ctx, scale_element, 'SHORT-LABEL', scale_constraint['short_label'],
                    TI=scale_constraint.get('short_label_id') or None)
            if scale_constraint.get('description') is not None:
                add_desc(ctx, scale_element, scale_constraint['description'], scale_constraint.get('description_id'))
            if scale_constraint.get('interval') is not None:
                _add_interval(ctx, scale_element, scale_constraint['interval'])
    return element


def add_data_object_prop(ctx, parent, key):
    dop = ctx.take(key)
    element = identified(ctx, parent, 'DATA-OBJECT-PROP', ctx.own_id(key), dop)
    add_names(ctx, element, dop)
    special_data.sdgs(ctx, element, dop)
    physical_type = dop.get('physical_type')
    if dop.get('compu_method') is not None:
        add_compu_method(ctx, element, dop['compu_method'],
                         physical_type['base_data_type'] if physical_type else None)
    if dop.get('diag_coded_type') is not None:
        add_diag_coded_type(ctx, element, dop['diag_coded_type'])
    if physical_type is not None:
        add_physical_type(ctx, element, physical_type)
    add_constraint(ctx, element, 'INTERNAL-CONSTR', dop.get('internal_constraint_reference'))
    # A unit reference whose flag is not set is absent, not an empty reference.
    if dop.get('unit_reference') is not None:
        add_ref(ctx, element, 'UNIT-REF', dop['unit_reference'])
    add_constraint(ctx, element, 'PHYS-CONSTR', dop.get('physical_constraint_reference'))
    return element


def _add_unit_group(ctx, parent, reference):
    key = reference.get('object_id') if reference else None
    if not key:
        ctx.report['empty_references'] += 1
        return None
    if reference.get('pool_id') != ctx.pool_id or key not in ctx.objects:
        ctx.report['unresolvable_references'] += 1
        return None
    group = ctx.take(key)
    # UNIT-GROUP has no ID and is never referenced.
    element = sub(ctx, parent, 'UNIT-GROUP', OID=group.get('unique_object_id') or None)
    add_names(ctx, element, group)
    category = _mapped(ctx, UGCAT, group['category'])
    if category is not None:
        sub(ctx, element, 'CATEGORY', category)
    if group.get('unit_references'):
        refs = sub(ctx, element, 'UNIT-REFS')
        for entry in group['unit_references']:
            add_ref(ctx, refs, 'UNIT-REF', entry.get('reference', entry))
    return element


def add_unit_spec(ctx, parent, layer_data):
    group_entries = layer_data.get('unit_group_references') or []
    unit_keys = ctx.ordered(layer_data.get('unit_references'), ctx.keys('UNIT_', 'MCD_DB_UNIT'))
    if not group_entries and not unit_keys:
        return None
    element = sub(ctx, parent, 'UNIT-SPEC')
    # UNIT-GROUPS needs at least one UNIT-GROUP; it is appended only when one was written.
    groups = ET.Element('UNIT-GROUPS')
    for entry in group_entries:
        _add_unit_group(ctx, groups, entry.get('reference', entry))
    if len(groups):
        element.append(groups)
    dimensions = {}
    if unit_keys:
        units = sub(ctx, element, 'UNITS')
        for key in unit_keys:
            unit = ctx.take(key)
            unit_element = identified(ctx, units, 'UNIT', ctx.own_id(key), unit)
            add_names(ctx, unit_element, unit)
            for tag, field in (('DISPLAY-NAME', 'display_name'), ('FACTOR-SI-TO-UNIT', 'factor_si_to_unit'),
                               ('OFFSET-SI-TO-UNIT', 'offset_si_to_unit')):
                if unit.get(field) is not None:
                    sub(ctx, unit_element, tag, format_value(unit[field]))
            dimension = unit.get('physical_dimension')
            if dimension:
                # Each unit carries its own copy of the dimension; the dimension's ID is its short name.
                sub(ctx, unit_element, 'PHYSICAL-DIMENSION-REF', ID_REF=dimension['short_name'])
                dimensions.setdefault(dimension.get('unique_object_id') or dimension['short_name'], dimension)
    if dimensions:
        dimensions_element = sub(ctx, element, 'PHYSICAL-DIMENSIONS')
        for dimension in dimensions.values():
            dimension_element = identified(ctx, dimensions_element, 'PHYSICAL-DIMENSION',
                                           dimension['short_name'], dimension)
            add_names(ctx, dimension_element, dimension)
            for tag, field in _EXPONENTS:
                if dimension.get(field):
                    sub(ctx, dimension_element, tag, str(dimension[field]))
    if not len(element):
        parent.remove(element)
        return None
    return element
