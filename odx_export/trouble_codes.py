"""DTC-DOP with its DTCs."""
from odx_export import special_data
from odx_export.data_objects import add_compu_method, add_diag_coded_type, add_physical_type
from odx_export.elements import add_names, add_ref, identified, sub


def _add_dtc(ctx, parent, key):
    dtc = ctx.take(key)
    element = identified(ctx, parent, 'DTC', ctx.own_id(key), dtc)
    sub(ctx, element, 'SHORT-NAME', dtc.get('short_name'))
    sub(ctx, element, 'TROUBLE-CODE', str(dtc['trouble_code']))
    if dtc.get('display_trouble_code') is not None:
        sub(ctx, element, 'DISPLAY-TROUBLE-CODE', dtc['display_trouble_code'])
    if dtc.get('dtc_text') is not None:
        sub(ctx, element, 'TEXT', dtc['dtc_text'], TI=dtc.get('diag_trouble_code_text_id') or None)
    sub(ctx, element, 'LEVEL', str(dtc['level']))
    special_data.sdgs(ctx, element, dtc)
    return element


def add_dtc_dop(ctx, parent, key, written_dtcs):
    """DTC-DOP; a DTC of the own pool is embedded the first time and referred to afterwards.

    written_dtcs holds the keys of the DTCs already embedded in the document and is updated.
    """
    dop = ctx.take(key)
    element = identified(ctx, parent, 'DTC-DOP', ctx.own_id(key), dop)
    add_names(ctx, element, dop)
    special_data.sdgs(ctx, element, dop)
    if dop.get('diag_coded_type') is not None:
        add_diag_coded_type(ctx, element, dop['diag_coded_type'])
    physical_type = dop.get('physical_type')
    if physical_type is not None:
        add_physical_type(ctx, element, physical_type)
    if dop.get('compu_method') is not None:
        add_compu_method(ctx, element, dop['compu_method'],
                         physical_type['base_data_type'] if physical_type else None)
    entries = dop.get('diag_trouble_code_references') or []
    if entries:
        dtcs = sub(ctx, element, 'DTCS')
        for entry in entries:
            reference = entry.get('reference', entry)
            dtc_key = reference.get('object_id') if reference else None
            if (dtc_key and reference.get('pool_id') == ctx.pool_id and dtc_key in ctx.objects
                    and dtc_key not in written_dtcs):
                _add_dtc(ctx, dtcs, dtc_key)
                written_dtcs.add(dtc_key)
            else:
                add_ref(ctx, dtcs, 'DTC-REF', reference)
        # Only empty references: DTCS without content is not written.
        if not len(dtcs):
            element.remove(dtcs)
    return element
