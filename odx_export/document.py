"""The ODX document of a pool: DIAG-LAYER-CONTAINER with its ECU-SHARED-DATA or its other layers."""
import os
import xml.etree.ElementTree as ET

from odx_export import (communication, data_objects, layers, special_data, state_charts, structures, tables,
                        trouble_codes, variants)
from odx_export.elements import add_desc, clean, identified, sub

LAYER_DATA_KEY = '#RtGen_DB_LAYER_DATA'
PROJECT_DATA_KEY = '#RtGen_DB_PROJECT_DATA'
_XSI_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
_ENV_DATA_DESC = 'MCD_DB_PARAMETER_ENV_DATA_DESC'
_ENV_DATA = 'MCD_DB_PARAMETER_ENV_DATA'
_HEADER = (' Reconstructed by ODIS-project-explorer from pool {}: '
           'equivalent in content, not identical to the original ODX document ')
_NOT_WRITTEN = ' Not written: {} {}: not referenced by any object, no place in ODX '
_SHARED_DATA_EXTENSION = '.sd'
# location_type -> (list element, layer element, layer data field of the layer object, its type)
_LAYER_KINDS = {
    'ePROTOCOL': ('PROTOCOLS', 'PROTOCOL', None, None),
    'eFUNCTIONAL_GROUP': ('FUNCTIONAL-GROUPS', 'FUNCTIONAL-GROUP', 'functional_group_reference',
                          'MCD_DB_FUNCTIONAL_GROUP'),
    'eECU_BASE_VARIANT': ('BASE-VARIANTS', 'BASE-VARIANT', 'base_variant_reference', 'MCD_DB_ECU_BASE_VARIANT'),
    'eECU_VARIANT': ('ECU-VARIANTS', 'ECU-VARIANT', 'ecu_variant_reference', 'MCD_DB_ECU_VARIANT'),
}
# Lists of a DIAG-LAYER-CONTAINER in the order of the ODX 2.2 schema; ECU-SHARED-DATAS is written by build_document.
_LAYER_LISTS = ('PROTOCOLS', 'FUNCTIONAL-GROUPS', 'BASE-VARIANTS', 'ECU-VARIANTS')


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
    _add_not_written(ctx, esd, ctx.without_place)
    return root


def _add_not_written(ctx, parent, keys):
    for key in keys:
        parent.append(ET.Comment(_comment_text(_NOT_WRITTEN.format(ctx.types[key], clean(ctx, key)))))


def _pool_layer(ctx, layer_lookup, pool_id):
    """Layer description of a pool's own layer (key #RtGen_DB_LAYER_DATA), or None."""
    try:
        descriptions = layer_lookup(pool_id) or []
    except Exception:
        # A broken layer object of another pool is an unknown parent, not an error of this pool.
        ctx.report['layers_of_other_pool_not_loadable'] += 1
        return None
    for description in descriptions:
        if description.get('key') == LAYER_DATA_KEY:
            return description
    return None


def _layer_object(ctx, layer_data, field, type_name):
    """The object that names the layer (base variant, variant, functional group), taken; None if missing."""
    reference = layer_data.get(field) or {}
    object_id = reference.get('object_id')
    # An empty pool word stands for the pool that holds the reference (as in the reference resolver).
    if (reference.get('pool_id') or ctx.pool_id) != ctx.pool_id or ctx.types.get(object_id) != type_name:
        ctx.report['layer_object_missing'] += 1
        return None
    return ctx.take(object_id)


def _add_layer(ctx, parent, tag, layer_data, obj, parent_layer):
    """One layer element; the children in the order of the ODX 2.2 schema."""
    element = identified(ctx, parent, tag, layer_data['layer_id'], obj)
    # SHORT-NAME is the layer name, which every DOCREF to the layer names.
    sub(ctx, element, 'SHORT-NAME', layer_data['layer_name'])
    if obj is not None:
        if obj.get('short_name') != layer_data['layer_name']:
            ctx.report['layer_short_name_differs'] += 1
        if obj.get('long_name') is not None:
            sub(ctx, element, 'LONG-NAME', obj['long_name'], TI=obj.get('long_name_id') or None)
        if obj.get('description') is not None:
            add_desc(ctx, element, obj['description'], obj.get('description_id'))
    communication.add_funct_classes(ctx, element, layer_data)
    _add_diag_data_dictionary_spec(ctx, element, layer_data)
    communication.add_diag_comms(ctx, element, layer_data)
    communication.add_requests(ctx, element, layer_data)
    communication.add_responses(ctx, element, layer_data)
    state_charts.add_state_charts(ctx, element, layer_data)
    variants.add_sub_components(ctx, element, layer_data)
    special_data.sdgs(ctx, element, layer_data)
    layers.add_comparam_refs(ctx, element, layer_data)
    if tag == 'ECU-VARIANT' and obj is not None:
        variants.add_variant_patterns(ctx, element, obj)
    if tag == 'PROTOCOL':
        layers.add_protocol_refs(ctx, element, layer_data)
    layers.add_parent_refs(ctx, element, layer_data, parent_layer)
    layers.check_shared_data_parents(ctx, layer_data)
    return element


def build_layer_document(ctx, layer_lookup):
    """ODX root with the DIAG-LAYER-CONTAINER of a layer pool and one element per layer, in pool order.

    layer_lookup(pool_id) returns the layer descriptions of a pool (ProjectPools.layers). A shared data
    pool gets the document of build_document."""
    if ctx.pool_id.endswith(_SHARED_DATA_EXTENSION):
        return build_document(ctx)
    project_data = ctx.take(PROJECT_DATA_KEY)
    root = ET.Element('ODX', {'MODEL-VERSION': '2.2.0'})
    container = sub(ctx, root, 'DIAG-LAYER-CONTAINER', ID=project_data['container_short_name'])
    sub(ctx, container, 'SHORT-NAME', project_data['container_short_name'])
    lists = {tag: sub(ctx, container, tag) for tag in _LAYER_LISTS}

    def parent_layer(pool_id):
        return _pool_layer(ctx, layer_lookup, pool_id)

    def member_parents(pool_id):
        return (parent_layer(pool_id) or {}).get('parent_layers') or []

    base_variant = None
    ecu_variants = {}
    elements = {}  # layer name -> written layer element
    for description in layer_lookup(ctx.pool_id) or []:
        key = description['key']
        layer_data = ctx.take(key)
        kind = _LAYER_KINDS.get(layer_data.get('location_type'))
        if kind is None:
            # A layer of another kind (a multiple ECU job, say) has no element in these documents.
            ctx.mark_without_place(key)
            continue
        list_tag, tag, field, type_name = kind
        view = ctx.for_layer(layer_data['layer_name'])
        obj = _layer_object(view, layer_data, field, type_name) if field else None
        elements[layer_data['layer_name']] = _add_layer(view, lists[list_tag], tag, layer_data, obj, parent_layer)
        if obj is None:
            continue
        if tag == 'BASE-VARIANT' and base_variant is None:
            base_variant = obj
        elif tag == 'BASE-VARIANT':
            ctx.report['second_base_variant'] += 1
        elif tag == 'ECU-VARIANT':
            ecu_variants[layer_data[field]['object_id']] = obj
        elif tag == 'FUNCTIONAL-GROUP':
            variants.check_group_members(ctx, obj, member_parents)
    if base_variant is not None:
        # The map key of a pattern entry is the variant name, not the object key of the variant.
        variants.check_base_variant_patterns(ctx, base_variant, variants.variants_by_name(base_variant, ecu_variants))
    for tag in _LAYER_LISTS:
        if not len(lists[tag]):
            container.remove(lists[tag])
    # Some marks are made for the whole pool, so each comment goes to the layer the key names; the others
    # (a layer of another kind among them) go to the end of the container.
    for key in ctx.without_place:
        _add_not_written(ctx, elements.get(ctx.naming_layer(key), container), [key])
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
            ET.ElementTree(root).write(handle, encoding='unicode')
            handle.write('\n')
    except BaseException:
        if os.path.exists(path):
            os.remove(path)
        raise
    finally:
        root.attrib = original
