from common_utils import enum_converters


def add_field_to_string(key, field, value):
    if key != '':
        key += '.'
    key += '[{}]{}'.format(field, value)
    return key


def load(stream):
    obj = {}
    
    # Each name is kept with its word: a word of 0 is not set, an embedded string (word None) is set
    names = [stream.loadAsciiString() for _ in range(7)]
    (base_variant, base_variant_id, variant, variant_id,
     functional_group, multiple_ecu_job, protocol) = names
    obj['ecu_base_variant'] = base_variant[0]
    obj['ecu_base_variant_id'] = base_variant_id[0]
    obj['ecu_variant'] = variant[0]
    obj['ecu_variant_id'] = variant_id[0]
    obj['functional_group'] = functional_group[0]
    obj['multiple_ecu_job'] = multiple_ecu_job[0]
    obj['protocol'] = protocol[0]
    
    # kernel: MCDLocationType; an unknown location type is kept as its number
    obj['location_type'] = enum_converters.enum_name_or_number(enum_converters.get_MCDLocationType, stream.loadEnumMediumRange())
    
    # kernel: the last string is the access key's own pool ID (setDbPoolID)
    obj['pool_id'] = stream.loadAsciiString()[0]
    
    # derived, not stored by the kernel; composed as getStringNr does
    obj['string'] = compose_string(base_variant, variant, functional_group, multiple_ecu_job, protocol)
    
    return obj


def compose_string(base_variant, variant, functional_group, multiple_ecu_job, protocol):
    def is_set(loaded):
        return loaded[1] != 0
    
    if is_set(multiple_ecu_job):
        parts = [('MultipleEcuJob', multiple_ecu_job)]
    else:
        parts = [('Protocol', protocol)] if is_set(protocol) else []
        # kernel: the functional group is left out when a base variant is set
        if is_set(functional_group) and not is_set(base_variant):
            parts.append(('FunctionalGroup', functional_group))
        if is_set(base_variant):
            parts.append(('EcuBaseVariant', base_variant))
        if is_set(variant):
            parts.append(('EcuVariant', variant))
    
    # kernel: getString fails when a set name cannot be resolved
    if any(loaded[0] is None for _, loaded in parts):
        return None
    
    string = ''
    for field, loaded in parts:
        string = add_field_to_string(string, field, loaded[0])
    return string
