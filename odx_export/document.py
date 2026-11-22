"""The ODX document of a shared data pool: DIAG-LAYER-CONTAINER with one ECU-SHARED-DATA."""
import os
import xml.etree.ElementTree as ET

from odx_export import communication, data_objects, special_data, state_charts, structures, tables, trouble_codes
from odx_export.elements import clean, sub

LAYER_DATA_KEY = '#RtGen_DB_LAYER_DATA'
PROJECT_DATA_KEY = '#RtGen_DB_PROJECT_DATA'
_XSI_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
_ENV_DATA_DESC = 'MCD_DB_PARAMETER_ENV_DATA_DESC'
_ENV_DATA = 'MCD_DB_PARAMETER_ENV_DATA'
_HEADER = (' Reconstructed by ODIS-project-explorer from pool {}: '
           'equivalent in content, not identical to the original ODX document ')
_NOT_WRITTEN = ' Not written: {} {}: not referenced by any object, no place in ODX '


def _add_dops(ctx, parent, tag, keys, writer):
    """Append a DOP collection; nothing is written for an empty list."""
    if not keys:
        return None
    element = sub(ctx, parent, tag)
    for key in keys:
        writer(ctx, element, key)
    return element


def _all_values(ctx, desc_keys):
    """Own ENV-DATA key -> all-value parameter of the first ENV-DATA-DESC that names it."""
    result = {}
    for key in desc_keys:
        desc = ctx.objects[key].get('env_data_desc') or {}
        all_value = desc.get('all_value_env_data_parameter')
        reference = all_value.get('dop_base_reference') if all_value else None
        if reference and reference.get('pool_id') == ctx.pool_id and reference.get('object_id'):
            result.setdefault(reference['object_id'], all_value)
    return result


def _add_diag_data_dictionary_spec(ctx, esd, layer_data):
    element = sub(ctx, esd, 'DIAG-DATA-DICTIONARY-SPEC')
    dop_keys = ctx.ordered(layer_data.get('dop_references'), ctx.keys('DOP_'))

    def of_type(type_name):
        return [key for key in dop_keys if ctx.types[key] == type_name]

    written_dtcs = set()
    _add_dops(ctx, element, 'DTC-DOPS', of_type('DB_DOP_DTC'),
              lambda ctx, parent, key: trouble_codes.add_dtc_dop(ctx, parent, key, written_dtcs))
    desc_keys = of_type(_ENV_DATA_DESC)
    _add_dops(ctx, element, 'ENV-DATA-DESCS', desc_keys, structures.add_env_data_desc)
    _add_dops(ctx, element, 'DATA-OBJECT-PROPS', of_type('DB_DOP_SIMPLE_BASE'), data_objects.add_data_object_prop)
    _add_dops(ctx, element, 'STRUCTURES', of_type('MCD_DB_PARAMETER_STRUCTURE'), structures.add_structure)
    _add_dops(ctx, element, 'STATIC-FIELDS', of_type('MCD_DB_PARAMETER_STATIC_FIELD'), structures.add_static_field)
    _add_dops(ctx, element, 'DYNAMIC-LENGTH-FIELDS', of_type('MCD_DB_PARAMETER_DYNAMIC_LENGTH_FIELD'),
              structures.add_dynamic_length_field)
    _add_dops(ctx, element, 'END-OF-PDU-FIELDS', of_type('MCD_DB_PARAMETER_END_OF_PDU_FIELD'),
              structures.add_end_of_pdu_field)
    _add_dops(ctx, element, 'MUXS', of_type('MCD_DB_PARAMETER_MULTIPLEXER'), structures.add_mux)
    all_values = _all_values(ctx, desc_keys)
    _add_dops(ctx, element, 'ENV-DATAS', of_type(_ENV_DATA),
              lambda ctx, parent, key: structures.add_env_data(ctx, parent, key, all_values.get(key)))
    data_objects.add_unit_spec(ctx, element, layer_data)
    # Called also without tables: it marks the table rows that have no place in ODX.
    tables.add_tables(ctx, element, layer_data)
    if not len(element):
        esd.remove(element)


def _comment_text(text):
    """XML does not allow '--' inside a comment."""
    while '--' in text:
        text = text.replace('--', '- -')
    return text


def build_document(ctx):
    """ODX root with the DIAG-LAYER-CONTAINER and ECU-SHARED-DATA of the pool."""
    layer_data = ctx.take(LAYER_DATA_KEY)
    project_data = ctx.take(PROJECT_DATA_KEY)
    root = ET.Element('ODX', {'MODEL-VERSION': '2.2.0'})
    container = sub(ctx, root, 'DIAG-LAYER-CONTAINER', ID=project_data['container_short_name'])
    sub(ctx, container, 'SHORT-NAME', project_data['container_short_name'])
    esds = sub(ctx, container, 'ECU-SHARED-DATAS')
    esd = sub(ctx, esds, 'ECU-SHARED-DATA', ID=layer_data['layer_id'])
    sub(ctx, esd, 'SHORT-NAME', layer_data['layer_name'])
    # Written in document order, so that the first SDG-CAPTION of a caption comes first.
    communication.add_funct_classes(ctx, esd, layer_data)
    _add_diag_data_dictionary_spec(ctx, esd, layer_data)
    communication.add_diag_comms(ctx, esd, layer_data)
    communication.add_requests(ctx, esd, layer_data)
    communication.add_responses(ctx, esd, layer_data)
    state_charts.add_state_charts(ctx, esd, layer_data)
    special_data.sdgs(ctx, esd, layer_data)
    for key in ctx.without_place:
        esd.append(ET.Comment(_comment_text(_NOT_WRITTEN.format(ctx.types[key], clean(ctx, key)))))
    return root


def _uses_xsi(root):
    prefix = '{' + _XSI_NAMESPACE + '}'
    return any(name.startswith(prefix) for element in root.iter() for name in element.attrib)


def write_document(root, path, pool_id):
    """Write declaration, the reconstruction comment and the indented document; no file is left on failure."""
    ET.indent(root, '  ')
    original = root.attrib
    # ElementTree declares the namespace itself when an xsi attribute is written; otherwise it is set here.
    if not _uses_xsi(root):
        root.attrib = {'xmlns:xsi': _XSI_NAMESPACE, **original}
    try:
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            handle.write('<!--' + _comment_text(_HEADER.format(pool_id)) + '-->\n')
            handle.write(ET.tostring(root, encoding='unicode'))
            handle.write('\n')
    except BaseException:
        if os.path.exists(path):
            os.remove(path)
        raise
    finally:
        root.attrib = original
