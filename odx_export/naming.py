"""The naming rule: object keys read <prefix><layer>_<ID>, pools <version>@<layer>.<extension>."""

# Longer prefixes come before the shorter ones they start with (TBP_ before TB_, STR_ before ST_).
PREFIXES = ('DOP_', 'TBP_', 'TB_', 'IC_', 'PC_', 'UNIT_', 'DC_', 'REQ_', 'RSP_', 'FC_',
            'DTC_', 'SC_', 'STR_', 'ST_', 'CAPTION_')


def layer_name(pool_id):
    """Pool name without the '<version>@' part and without the last extension."""
    name = pool_id.split('@', 1)[-1]
    return name.rsplit('.', 1)[0] if '.' in name else name


def split_key(object_key, layer):
    """Return (prefix, ID) of an object key of the given layer, or None if no rule matches."""
    for prefix in PREFIXES:
        head = prefix + layer + '_'
        if object_key.startswith(head):
            return prefix, object_key[len(head):]
    return None
