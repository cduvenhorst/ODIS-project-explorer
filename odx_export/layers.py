"""Layer documents: parent references with their not-inherited lists."""
import os
import xml.etree.ElementTree as ET

from odx_export.elements import XSI_TYPE, sub
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
        attributes = {'ID-REF': id_ref, 'DOCREF': docref, 'DOCTYPE': 'LAYER',
                      XSI_TYPE: PARENT_REF_TYPES.get(os.path.splitext(pool_id)[1])}
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
