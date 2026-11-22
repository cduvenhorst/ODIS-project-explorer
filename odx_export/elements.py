"""Helpers that write ODX elements with escaping, references and number formats."""
import re
import xml.etree.ElementTree as ET

from odx_export.naming import layer_name, split_key

XSI_TYPE = '{http://www.w3.org/2001/XMLSchema-instance}type'

# Characters XML 1.0 does not allow.
_INVALID = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]')


def clean(ctx, text):
    """Replace every character XML 1.0 forbids by U+FFFD and count the replacements."""
    cleaned, count = _INVALID.subn('�', text)
    if count:
        ctx.report['replaced_characters'] += count
    return cleaned


def sub(ctx, parent, tag, text=None, attributes=None, **named):
    """Append a child. 'attributes' holds finished names, 'named' maps '_' to '-'; None is omitted."""
    values = dict(attributes or {})
    values.update((name.replace('_', '-'), value) for name, value in named.items())
    element = ET.SubElement(parent, tag, {name: clean(ctx, str(value))
                                          for name, value in values.items() if value is not None})
    if text is not None:
        element.text = clean(ctx, text)
    return element


def identified(ctx, parent, tag, element_id, obj, **attributes):
    """Append an element with ID and, when the object has one, OID."""
    oid = obj.get('unique_object_id') if obj else None
    return sub(ctx, parent, tag, attributes={'ID': element_id, 'OID': oid or None}, **attributes)


def add_desc(ctx, parent, text, text_id):
    """Append DESC with XML content; text that is not well-formed XML is written as plain text."""
    text = clean(ctx, text)
    try:
        element = ET.fromstring('<DESC>' + text + '</DESC>')
    except ET.ParseError:
        ctx.report['malformed_descriptions'] += 1
        element = ET.Element('DESC')
        element.text = text
    if text_id:
        element.set('TI', clean(ctx, text_id))
    parent.append(element)


def add_names(ctx, parent, obj, short_name=None, long_name=True):
    """Append SHORT-NAME, LONG-NAME (with TI) and DESC (with TI) from a loaded object."""
    sub(ctx, parent, 'SHORT-NAME', short_name if short_name is not None else obj.get('short_name'))
    if long_name and obj.get('long_name') is not None:
        sub(ctx, parent, 'LONG-NAME', obj['long_name'], TI=obj.get('long_name_id') or None)
    if obj.get('description') is not None:
        add_desc(ctx, parent, obj['description'], obj.get('description_id'))


def format_value(value, data_type=None):
    """Text of a pool value: doubles without '.0', bytes as upper-case hex, booleans as true/false."""
    if value is None:
        return None
    if isinstance(value, dict) and 'value' in value:
        data_type = value.get('data_type') or data_type
        value = value['value']
    if isinstance(value, (bytes, bytearray)):
        if data_type in ('eA_BITFIELD', 'eA_UNICODE2STRING'):
            return bytes(value).decode('latin-1')
        return bytes(value).hex().upper()
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float):
        text = repr(value)
        return text[:-2] if text.endswith('.0') else text
    return str(value)


def add_ref(ctx, parent, tag, reference):
    """Append a reference element, or return None for an empty reference."""
    object_id = reference.get('object_id') if reference else None
    if not object_id:
        ctx.report['empty_references'] += 1
        return None
    pool_id = reference.get('pool_id')
    if pool_id is None:
        return sub(ctx, parent, tag[:-len('-REF')] + '-SNREF', SHORT_NAME=object_id)
    own = pool_id == ctx.pool_id
    layer = layer_name(pool_id)
    parts = split_key(object_id, layer)
    exists = ctx.target_type(reference) is not None
    if exists and parts is not None:
        id_ref = parts[1]
    else:
        id_ref = object_id
        ctx.report['unresolvable_references'] += 1
    return sub(ctx, parent, tag, ID_REF=id_ref,
               DOCREF=None if own else layer, DOCTYPE=None if own else 'LAYER')
