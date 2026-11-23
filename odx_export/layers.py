"""Layer documents: parent references, communication parameter references, protocol references."""
import os
import xml.etree.ElementTree as ET

from odx_export.elements import XSI_TYPE, format_value, sub
from odx_export.naming import layer_name

PARENT_REF_TYPES = {'.bv': 'BASE-VARIANT-REF', '.fg': 'FUNCTIONAL-GROUP-REF', '.pr': 'PROTOCOL-REF',
                    '.sd': 'ECU-SHARED-DATA-REF', '.ev': 'ECU-VARIANT-REF'}

# (layer data field, list element, entry element, reference element), in schema order.
_NOT_INHERITED = (
    ('not_inherited_diag_com_primitives', 'NOT-INHERITED-DIAG-COMMS', 'NOT-INHERITED-DIAG-COMM',
     'DIAG-COMM-SNREF'),
    ('not_inherited_dops', 'NOT-INHERITED-DOPS', 'NOT-INHERITED-DOP', 'DOP-BASE-SNREF'),
    ('not_inherited_tables', 'NOT-INHERITED-TABLES', 'NOT-INHERITED-TABLE', 'TABLE-SNREF'),
    ('not_inherited_global_negative_responses', 'NOT-INHERITED-GLOBAL-NEG-RESPONSES',
     'NOT-INHERITED-GLOBAL-NEG-RESPONSE', 'GLOBAL-NEG-RESPONSE-SNREF'),
)


def add_parent_refs(ctx, parent, layer_data, parent_layer):
    """Append PARENT-REFS in the order of 'parent_layers'; None when the layer has no parent.

    parent_layer(pool_id) returns {'layer_name', 'layer_id'} of the parent pool's layer or None."""
    pools = layer_data.get('parent_layers') or []
    for field, _, _, _ in _NOT_INHERITED:
        for entry in layer_data.get(field) or []:
            if entry.get('map_key') not in pools:
                ctx.report['not_inherited_without_parent'] += 1
    if not pools:
        return None
    refs = sub(ctx, parent, 'PARENT-REFS')
    for pool_id in pools:
        known = parent_layer(pool_id)
        if known:
            id_ref, docref = known['layer_id'], known['layer_name']
        else:
            id_ref = docref = layer_name(pool_id)
            ctx.report['unresolvable_references'] += 1
        ref_type = PARENT_REF_TYPES.get(os.path.splitext(pool_id)[1])
        if ref_type is None:
            ctx.report['unknown_parent_ref_type'] += 1
        attributes = {'ID-REF': id_ref, 'DOCREF': docref, 'DOCTYPE': 'LAYER', XSI_TYPE: ref_type}
        ref = sub(ctx, refs, 'PARENT-REF', attributes=attributes)
        for field, list_tag, entry_tag, ref_tag in _NOT_INHERITED:
            names = [name for entry in layer_data.get(field) or [] if entry.get('map_key') == pool_id
                     for name in entry.get('strings') or []]
            if not names:
                continue
            listing = ET.SubElement(ref, list_tag)
            for name in names:
                sub(ctx, ET.SubElement(listing, entry_tag), ref_tag, SHORT_NAME=name)
    return refs


def check_shared_data_parents(ctx, layer_data):
    """Report every shared-data parent pool that is not among the parents."""
    parents = set(layer_data.get('parent_layers') or [])
    for pool_id in layer_data.get('shared_data_parent_layers') or []:
        if pool_id not in parents:
            ctx.report['shared_data_parent_not_in_parents'] += 1


def _dop_pool(parameter):
    return (parameter.get('dop_base_reference') or {}).get('pool_id') or None


def _nested_dop_pools(parameters, pools):
    for parameter in parameters or []:
        if _dop_pool(parameter):
            pools.add(_dop_pool(parameter))
        _nested_dop_pools(parameter.get('parameters'), pools)
    return pools


def comparam_pool(entry):
    """The .cs pool of a communication parameter: its DOP pool, else the one pool its sub-parameters name.

    None when neither rule gives exactly one pool."""
    if _dop_pool(entry):
        return _dop_pool(entry)
    pools = _nested_dop_pools(entry.get('parameters'), set())
    return pools.pop() if len(pools) == 1 else None


def _add_value(ctx, parent, parameter):
    """Append SIMPLE-VALUE, or COMPLEX-VALUE with the sub-parameter values in list order."""
    if parameter.get('parameter_type') == 'eSTRUCTURE':
        complex_value = ET.SubElement(parent, 'COMPLEX-VALUE')
        for sub_parameter in parameter.get('parameters') or []:
            _add_value(ctx, complex_value, sub_parameter)
        return
    value = parameter.get('default_value') or {}
    text = format_value(value.get('value'), value.get('data_type'))
    if text is None:
        ctx.report['comparam_value_missing'] += 1
        return
    sub(ctx, parent, 'SIMPLE-VALUE', text)


def add_comparam_refs(ctx, parent, layer_data):
    """Append COMPARAM-REFS from 'layer_com_params'; None when no reference is written.

    The parameter has no object key in its .cs pool, so ID-REF is derived as <subset>.<short name>."""
    refs = None
    for entry in layer_data.get('layer_com_params') or []:
        pool_id = comparam_pool(entry)
        if pool_id is None:
            ctx.report['comparam_without_subset'] += 1
            continue
        if refs is None:
            refs = sub(ctx, parent, 'COMPARAM-REFS')
        subset = layer_name(pool_id)
        ref = sub(ctx, refs, 'COMPARAM-REF', ID_REF=subset + '.' + entry['short_name'], DOCREF=subset,
                  DOCTYPE='COMPARAM-SUBSET')
        _add_value(ctx, ref, entry)
        if entry.get('protocol_short_name'):
            sub(ctx, ref, 'PROTOCOL-SNREF', SHORT_NAME=entry['protocol_short_name'])
    return refs


def add_protocol_refs(ctx, parent, layer_data):
    """Append COMPARAM-SPEC-REF and PROT-STACK-SNREF of a protocol layer, each only when set.

    The comparam spec has no stored ID, so ID-REF is derived as the layer name of the .cp pool."""
    spec_pool = layer_data.get('com_param_spec_pool_id')
    if spec_pool:
        spec = layer_name(spec_pool)
        sub(ctx, parent, 'COMPARAM-SPEC-REF', ID_REF=spec, DOCREF=spec, DOCTYPE='COMPARAM-SPEC')
    if layer_data.get('protocol_stack_short_name'):
        sub(ctx, parent, 'PROT-STACK-SNREF', SHORT_NAME=layer_data['protocol_stack_short_name'])
