"""SDGS of an ODX element from the special data groups of a loaded object."""
import xml.etree.ElementTree as ET

from odx_export.elements import add_desc, identified, sub
from odx_export.naming import split_key

NOT_RESOLVABLE = 'not resolvable'


def sdgs(ctx, parent, obj):
    """Append SDGS for the object's resolved groups; return it, or None if there is nothing to write."""
    groups = obj.get('special_data_groups')
    if groups == NOT_RESOLVABLE:
        ctx.report['unresolvable_sdgs'] += 1
        return None
    # Built detached so that an object with only unresolvable groups gets no empty SDGS
    holder = ET.Element('SDGS')
    for group in groups or []:
        _write_group(ctx, holder, group)
    if len(holder) == 0:
        return None
    parent.append(holder)
    return holder


def _write_group(ctx, parent, group):
    if group == NOT_RESOLVABLE:
        ctx.report['unresolvable_sdgs'] += 1
        return
    element = sub(ctx, parent, 'SDG', SI=group.get('semantic_information') or None)
    _write_caption(ctx, element, group)
    for item in group.get('items') or []:
        if item is None:
            continue
        if 'items' in item:
            _write_group(ctx, element, item)
        else:
            sub(ctx, element, 'SD', item.get('content'),
                SI=item.get('semantic_information') or None, TI=item.get('text_id') or None)


def _write_caption(ctx, parent, group):
    reference = group.get('caption_reference')
    caption = group.get('caption')
    if not reference or caption is None:
        return
    object_key = reference['object_key']
    name = ctx.key_name(object_key) if ctx.key_name else None
    parts = split_key(name, ctx.layer) if name is not None else None
    if caption == NOT_RESOLVABLE or parts is None:
        # ODX form from the standard; no original document to compare (survey)
        ctx.report['unresolvable_references'] += 1
        sub(ctx, parent, 'SDG-CAPTION-REF',
            ID_REF=name if name is not None else 'hash %d' % object_key)
        return
    caption_id = parts[1]
    if name in ctx.types:
        # The caption object of this pool is written, either here or by an earlier SDG-CAPTION.
        ctx.used.add(name)
    if caption_id in ctx.written_caption_ids:
        # ODX form from the standard; no original document to compare (survey)
        sub(ctx, parent, 'SDG-CAPTION-REF', ID_REF=caption_id)
        return
    ctx.written_caption_ids.add(caption_id)
    # ODX form from the standard; no original document to compare (survey)
    element = identified(ctx, parent, 'SDG-CAPTION', caption_id, caption)
    sub(ctx, element, 'SHORT-NAME', caption.get('short_name'))
    if caption.get('long_name') is not None:
        sub(ctx, element, 'LONG-NAME', caption['long_name'], TI=caption.get('long_name_id') or None)
    if caption.get('description') is not None:
        add_desc(ctx, element, caption['description'], caption.get('description_id'))
