"""FUNCT-CLASSS, DIAG-COMMS (DIAG-SERVICE, SINGLE-ECU-JOB, DIAG-COMM-REF), REQUESTS and the three response lists."""
import os

from odx_export import special_data
from odx_export.elements import add_names, add_ref, format_value, identified, sub
from odx_export.parameters import add_params

_FUNCTIONAL_CLASS = 'MCD_DB_FUNCTIONAL_CLASS'
_REQUEST = 'MCD_DB_REQUEST'
_RESPONSE = 'MCD_DB_RESPONSE'
_SERVICE_TYPES = ('MCD_DB_SERVICE', 'MCD_DB_STARTCOMMUNICATION', 'MCD_DB_STOPCOMMUNICATION')
_JOB = 'MCD_DB_SINGLE_ECU_JOB'
_FLASH_JOB = 'MCD_DB_FLASH_JOB'
# Types written as DIAG-COMMS of a layer pool.
_DIAG_COMM_TYPES = _SERVICE_TYPES + (_JOB, _FLASH_JOB)

ADDRESSING = {'eFUNCTIONAL_OR_PHYSICAL': 'FUNCTIONAL-OR-PHYSICAL', 'eFUNCTIONAL': 'FUNCTIONAL',
              'ePHYSICAL': 'PHYSICAL'}
DIAGNOSTIC_CLASS = {1: 'STARTCOMM', 2: 'STOPCOMM', 3: 'VARIANTIDENTIFICATION'}
# Attribute of AUDIENCE -> flag of the loaded audience; ODX defaults each attribute to true.
_AUDIENCE = (('IS-SUPPLIER', 'supplier'), ('IS-DEVELOPMENT', 'development'), ('IS-MANUFACTURING', 'manufacturing'),
             ('IS-AFTERSALES', 'after_sales'), ('IS-AFTERMARKET', 'after_market'))
# Response type -> list tag and element tag, in the schema order of the diagnostic layer.
_RESPONSE_LISTS = (('ePOSITIVE_RESPONSE', 'POS-RESPONSES', 'POS-RESPONSE'),
                   ('eLOCAL_NEG_RESPONSE', 'NEG-RESPONSES', 'NEG-RESPONSE'),
                   ('eGLOBAL_NEG_RESPONSE', 'GLOBAL-NEG-RESPONSES', 'GLOBAL-NEG-RESPONSE'))
_PROG_CODE_FIELDS = (('CODE-FILE', 'code_file'), ('ENCRYPTION', 'encryption'), ('SYNTAX', 'syntax'),
                     ('REVISION', 'revision'), ('ENTRYPOINT', 'entry_point'))


def _own_keys(ctx, prefixes, type_name):
    """Own keys with one of the prefixes and of the given type, in pool order."""
    heads = tuple(prefix + ctx.layer + '_' for prefix in prefixes)
    # The prefix check is only a pre-filter; ctx.owns decides which keys belong to the layer.
    return [key for key in ctx.objects if key.startswith(heads) and ctx.types[key] == type_name and ctx.owns(key)]


def _reference(entry):
    """The reference of a named reference or map entry."""
    return entry.get('reference') if isinstance(entry, dict) else None


def _add_refs(ctx, parent, list_tag, tag, entries):
    """Append a list of references; the list is left out when no reference is written."""
    if not entries:
        return None
    element = sub(ctx, parent, list_tag)
    written = [add_ref(ctx, element, tag, _reference(entry)) for entry in entries]
    if not any(child is not None for child in written):
        parent.remove(element)
        return None
    return element


def _add_audience(ctx, parent, obj):
    flags = obj.get('audience_state')
    if flags is None:
        return None
    # Only the flags that differ from the ODX default true are written.
    return sub(ctx, parent, 'AUDIENCE',
               attributes={name: 'false' for name, field in _AUDIENCE if not flags.get(field, True)})


def _add_related(ctx, parent, obj):
    entries = obj.get('related_data_primitives')
    if not entries:
        return None
    element = sub(ctx, parent, 'RELATED-DIAG-COMM-REFS')
    for entry in entries:
        reference = _reference(entry)
        related = add_ref(ctx, element, 'RELATED-DIAG-COMM-REF', reference)
        attributes = reference.get('attributes') if related is not None else None
        if attributes:
            sub(ctx, related, 'RELATION-TYPE', attributes[0])
    if len(element) == 0:
        parent.remove(element)
        return None
    return element


def _add_diag_comm_head(ctx, element, obj):
    """Children every DIAG-COMM shares, from the names to the state transitions."""
    add_names(ctx, element, obj)
    special_data.sdgs(ctx, element, obj)
    _add_refs(ctx, element, 'FUNCT-CLASS-REFS', 'FUNCT-CLASS-REF', obj.get('functional_class_references'))
    _add_audience(ctx, element, obj)
    _add_related(ctx, element, obj)
    _add_refs(ctx, element, 'PRE-CONDITION-STATE-REFS', 'PRE-CONDITION-STATE-REF', obj.get('ecu_state_references'))
    _add_refs(ctx, element, 'STATE-TRANSITION-REFS', 'STATE-TRANSITION-REF',
              obj.get('ecu_state_transition_references'))


def _diagnostic_class(value):
    if not value:
        return None
    return DIAGNOSTIC_CLASS.get(value, str(value))


def _add_suppressable(ctx, parent, obj):
    if not obj.get('has_suppress_positive_response_capability'):
        return None
    element = sub(ctx, parent, 'POS-RESPONSE-SUPPRESSABLE')
    mask = obj.get('positive_response_suppress_bit_mask')
    if mask:
        sub(ctx, element, 'BIT-MASK', format_value(bytes(mask)))
    if obj.get('has_positive_response_suppress_parameter_short_name_path'):
        # ODX form from the standard; no original document to compare (survey)
        sub(ctx, element, 'VALUE-SNPATHREF',
            SHORT_NAME_PATH=obj.get('positive_response_suppress_parameter_short_name_path'))
    elif obj.get('positive_response_suppress_parameter_short_name') is not None:
        sub(ctx, element, 'VALUE-SNREF', SHORT_NAME=obj['positive_response_suppress_parameter_short_name'])
    return element


def _add_service(ctx, parent, key):
    obj = ctx.take(key)
    element = identified(ctx, parent, 'DIAG-SERVICE', ctx.own_id(key), obj, SEMANTIC=obj.get('semantic'),
                         DIAGNOSTIC_CLASS=_diagnostic_class(obj.get('diagnostic_class')),
                         # The communication primitives have no addressing mode, so no ADDRESSING.
                         ADDRESSING=ADDRESSING.get(obj.get('addressing_mode')))
    _add_diag_comm_head(ctx, element, obj)
    # A request reference whose flag is not set is absent, not an empty reference.
    if obj.get('request_reference') is not None:
        add_ref(ctx, element, 'REQUEST-REF', obj['request_reference'])
    _add_refs(ctx, element, 'POS-RESPONSE-REFS', 'POS-RESPONSE-REF', obj.get('positive_response_references'))
    _add_refs(ctx, element, 'NEG-RESPONSE-REFS', 'NEG-RESPONSE-REF', obj.get('negative_response_references'))
    _add_suppressable(ctx, element, obj)
    return element


def _add_prog_code(ctx, parent, code):
    element = sub(ctx, parent, 'PROG-CODE')
    for tag, field in _PROG_CODE_FIELDS:
        if code.get(field):
            sub(ctx, element, tag, code[field])
    _add_refs(ctx, element, 'LIBRARY-REFS', 'LIBRARY-REF', code.get('library_references'))
    return element


def _add_job(ctx, parent, key):
    # ODX form from the standard; no original document to compare (survey)
    obj = ctx.take(key)
    element = identified(ctx, parent, 'SINGLE-ECU-JOB', ctx.own_id(key), obj, SEMANTIC=obj.get('semantic'))
    _add_diag_comm_head(ctx, element, obj)
    codes = [code for code in obj.get('code_informations') or [] if code]
    if codes:
        codes_element = sub(ctx, element, 'PROG-CODES')
        for code in codes:
            _add_prog_code(ctx, codes_element, code)
    return element


def add_funct_classes(ctx, parent, layer_data):
    keys = ctx.ordered(layer_data.get('functional_class_references'), ctx.keys('FC_', _FUNCTIONAL_CLASS))
    if not keys:
        return None
    element = sub(ctx, parent, 'FUNCT-CLASSS')
    for key in keys:
        obj = ctx.take(key)
        add_names(ctx, identified(ctx, element, 'FUNCT-CLASS', ctx.own_id(key), obj), obj)
    return element


def add_diag_comms(ctx, parent, layer_data):
    if os.path.splitext(ctx.pool_id)[1] != '.sd':
        return _add_layer_diag_comms(ctx, parent, layer_data)
    # Requests and responses under DC_ belong to the jobs and are written with the other requests and responses;
    # any other type under DC_ has no writer here and stays unused.
    keys = [key for key in ctx.keys('DC_') if ctx.types[key] in _SERVICE_TYPES or ctx.types[key] == _JOB]
    keys = ctx.ordered(layer_data.get('diag_com_primitive_references'), keys)
    if not keys:
        return None
    element = sub(ctx, parent, 'DIAG-COMMS')
    for key in keys:
        if ctx.types[key] == _JOB:
            _add_job(ctx, element, key)
        else:
            _add_service(ctx, element, key)
    return element


def _add_own_diag_comm(ctx, parent, key):
    # A flash job has the fields of a single ECU job and is written as one.
    if ctx.types[key] in (_JOB, _FLASH_JOB):
        _add_job(ctx, parent, key)
    else:
        _add_service(ctx, parent, key)


def _add_layer_diag_comms(ctx, parent, layer_data):
    """DIAG-COMMS of a layer pool in the order of its reference list, then its unlisted own objects.

    An own object is written in full; an object of another layer or pool becomes a DIAG-COMM-REF to the
    layer that writes it."""
    own = [key for key in ctx.keys('DC_') if ctx.types[key] in _DIAG_COMM_TYPES]
    own_set = set(own)
    element = sub(ctx, parent, 'DIAG-COMMS')
    written = set()
    referenced = set()
    for entry in layer_data.get('diag_com_primitive_references') or []:
        reference = entry.get('reference', entry) if isinstance(entry, dict) else None
        if not reference or not reference.get('object_id'):
            ctx.report['empty_references'] += 1
            continue
        pool_id, object_id = reference.get('pool_id'), reference['object_id']
        if pool_id == ctx.pool_id and object_id in own_set:
            if object_id not in written:
                written.add(object_id)
                _add_own_diag_comm(ctx, element, object_id)
            continue
        if pool_id is None:
            ctx.report['diag_comm_reference_not_written'] += 1
            continue
        if pool_id == ctx.pool_id and (ctx.target_layer(pool_id, object_id) == ctx.layer
                                       or ctx.types.get(object_id) not in _DIAG_COMM_TYPES):
            # An object of this pool that is no DIAG-COMM written in its layer (a request, say) gets no reference.
            ctx.report['diag_comm_reference_not_written'] += 1
            continue
        target_type = ctx.target_type(reference)
        if pool_id != ctx.pool_id and target_type is not None and target_type not in _DIAG_COMM_TYPES:
            # The same rule for another pool; a target of unknown type is left to add_ref, which counts it.
            ctx.report['diag_comm_reference_not_written'] += 1
            continue
        if (pool_id, object_id) not in referenced:
            referenced.add((pool_id, object_id))
            add_ref(ctx, element, 'DIAG-COMM-REF', reference)
    for key in own:
        if key not in written:
            _add_own_diag_comm(ctx, element, key)
    if len(element) == 0:
        parent.remove(element)
        return None
    return element


def _add_message(ctx, parent, tag, key, parameters_field):
    obj = ctx.take(key)
    message_id = ctx.own_id(key)
    element = identified(ctx, parent, tag, message_id, obj)
    add_names(ctx, element, obj)
    special_data.sdgs(ctx, element, obj)
    add_params(ctx, element, obj.get(parameters_field), message_id)
    return element


def add_requests(ctx, parent, layer_data):
    keys = ctx.ordered(layer_data.get('request_references'), _own_keys(ctx, ('REQ_', 'DC_'), _REQUEST))
    if not keys:
        return None
    element = sub(ctx, parent, 'REQUESTS')
    for key in keys:
        _add_message(ctx, element, 'REQUEST', key, 'request_parameters')
    return element


def add_responses(ctx, esd, layer_data):
    keys = _own_keys(ctx, ('RSP_', 'DC_'), _RESPONSE)
    for response_type, list_tag, tag in _RESPONSE_LISTS:
        typed = [key for key in keys if ctx.objects[key].get('response_type') == response_type]
        # Only the global negative responses have a reference list in the layer data.
        if response_type == 'eGLOBAL_NEG_RESPONSE':
            typed = ctx.ordered(layer_data.get('global_negative_response_references'), typed)
        if not typed:
            continue
        element = sub(ctx, esd, list_tag)
        for key in typed:
            _add_message(ctx, element, tag, key, 'response_parameters')
