"""Parts of variant layers: ECU-VARIANT-PATTERNS, SUB-COMPONENTS and the checks of patterns and group members."""
from odx_export.elements import add_desc, add_names, add_ref, identified, sub

_SUB_COMPONENT = 'MCD_DB_SUB_COMPONENT'


def _add_name_ref(ctx, parent, tag, name, attribute='SHORT_NAME'):
    """Append a reference by short name or short name path; one without a name is not written and is counted."""
    if name is None:
        ctx.report['snref_without_name'] += 1
        return None
    return sub(ctx, parent, tag, **{attribute: name})


def _add_matching_parameters(ctx, parent, pattern):
    """Append MATCHING-PARAMETERS of a matching pattern; a pattern without parameters is reported."""
    parameters = [parameter for parameter in (pattern or {}).get('matching_parameters') or [] if parameter]
    if not parameters:
        ctx.report['matching_pattern_empty'] += 1
        return None
    element = sub(ctx, parent, 'MATCHING-PARAMETERS')
    for parameter in parameters:
        matching = sub(ctx, element, 'MATCHING-PARAMETER')
        if parameter.get('expected_value_string') is not None:
            sub(ctx, matching, 'EXPECTED-VALUE', parameter['expected_value_string'])
        reference = parameter.get('diag_com_primitive_reference') or {}
        if reference.get('pool_id') is not None:
            # The pool names the service by short name; with a pool ID the name may be an object key.
            ctx.report['matching_parameter_pooled_reference'] += 1
        _add_name_ref(ctx, matching, 'DIAG-COMM-SNREF', reference.get('object_id'))
        if parameter.get('response_parameter_is_short_name_path'):
            _add_name_ref(ctx, matching, 'OUT-PARAM-IF-SNPATHREF', parameter.get('response_parameter_short_name_path'),
                          'SHORT_NAME_PATH')
        else:
            _add_name_ref(ctx, matching, 'OUT-PARAM-IF-SNREF', parameter.get('response_parameter_name'))
    return element


def _add_patterns(ctx, parent, list_tag, tag, patterns):
    """Append a list of matching patterns; the list is left out when no pattern has parameters."""
    if not patterns:
        return None
    element = sub(ctx, parent, list_tag)
    for pattern in patterns:
        entry = sub(ctx, element, tag)
        if _add_matching_parameters(ctx, entry, pattern) is None:
            element.remove(entry)
    if len(element) == 0:
        parent.remove(element)
        return None
    return element


def add_variant_patterns(ctx, parent, variant):
    """Append ECU-VARIANT-PATTERNS from 'variant_patterns' of a variant; None when it has none."""
    return _add_patterns(ctx, parent, 'ECU-VARIANT-PATTERNS', 'ECU-VARIANT-PATTERN', variant.get('variant_patterns'))


def check_base_variant_patterns(ctx, base_variant, variants):
    """Report every entry of the base variant's 'ecu_variant_patterns' that differs from its variant's patterns.

    variants maps the variant name (the 'map_key' of an entry) to the variant's layer data."""
    for entry in base_variant.get('ecu_variant_patterns') or []:
        variant = variants.get(entry.get('map_key'))
        if variant is None or (entry.get('ecu_variant_patterns') or []) != (variant.get('variant_patterns') or []):
            ctx.report['base_variant_pattern_mismatch'] += 1


def variants_by_name(base_variant, variants):
    """Variant name -> variant, from the base variant's 'ecu_variant_references'.

    variants maps the object key of a variant to the variant; a name whose reference points to no
    such variant is left out."""
    result = {}
    for entry in base_variant.get('ecu_variant_references') or []:
        reference = entry.get('reference') if isinstance(entry, dict) else None
        object_id = reference.get('object_id') if reference else None
        if object_id in variants:
            result.setdefault(entry.get('name'), variants[object_id])
    return result


def check_group_members(ctx, group, member_parents):
    """Report every member of a functional group whose pool does not list the group's pool as parent.

    member_parents(pool_id) returns the parent pool IDs of a member pool."""
    for entry in group.get('group_member_references') or []:
        pool_id = ((entry or {}).get('reference') or {}).get('pool_id')
        if not pool_id or ctx.pool_id not in member_parents(pool_id):
            ctx.report['group_member_without_parent_ref'] += 1


def _connector_entries(ctx, sub_component, field):
    entries = sub_component.get(field) or []
    present = [entry for entry in entries if entry]
    # The loader keeps an empty collection entry readable; there is nothing to write for it.
    ctx.report['sub_component_empty_entry'] += len(entries) - len(present)
    return present


def _add_connector_names(ctx, parent, connector):
    """Names of a connector; ODX form after the named elements of ODX 2.2 (no schema to compare)."""
    if connector.get('short_name'):
        sub(ctx, parent, 'SHORT-NAME', connector['short_name'])
    else:
        # No name is invented for a connector the pool stores without one.
        ctx.report['sub_component_connector_without_short_name'] += 1
    if connector.get('long_name') is not None:
        sub(ctx, parent, 'LONG-NAME', connector['long_name'], TI=connector.get('long_name_id') or None)
    if connector.get('description') is not None:
        add_desc(ctx, parent, connector['description'], connector.get('description_id'))
    if connector.get('unique_object_id'):
        # A named element has no OID attribute.
        ctx.report['sub_component_connector_oid_not_written'] += 1


def _add_param_refs(ctx, parent, list_tag, tag, parameters):
    if not parameters:
        return
    element = sub(ctx, parent, list_tag)
    for parameter in parameters:
        if parameter.get('is_name'):
            _add_name_ref(ctx, element, tag + '-SNREF', parameter.get('name'))
        else:
            # The kernel looks the parameter up by short name path when the name flag is zero.
            _add_name_ref(ctx, element, tag + '-SNPATHREF', parameter.get('name'), 'SHORT_NAME_PATH')
    if len(element) == 0:
        parent.remove(element)


def _add_param_connectors(ctx, parent, sub_component):
    connectors = _connector_entries(ctx, sub_component, 'sub_component_param_connectors')
    if not connectors:
        return
    element = sub(ctx, parent, 'SUB-COMPONENT-PARAM-CONNECTORS')
    for connector in connectors:
        entry = sub(ctx, element, 'SUB-COMPONENT-PARAM-CONNECTOR')
        _add_connector_names(ctx, entry, connector)
        _add_name_ref(ctx, entry, 'DIAG-COMM-SNREF', connector.get('diag_com_primitive_name'))
        _add_param_refs(ctx, entry, 'OUT-PARAM-IF-REFS', 'OUT-PARAM-IF',
                        connector.get('sub_component_out_parameter_names'))
        _add_param_refs(ctx, entry, 'IN-PARAM-IF-REFS', 'IN-PARAM-IF',
                        connector.get('sub_component_in_parameter_names'))


def _add_linked_ref(ctx, parent, tag, connector, reference_field, link_field):
    """Append the reference of a connector; one stored as an ODX link has no writer and is reported."""
    if connector.get(reference_field) is None and connector.get(link_field) is not None:
        ctx.report['sub_component_odx_link_not_written'] += 1
        return None
    return add_ref(ctx, parent, tag, connector.get(reference_field))


def _add_table_row_connectors(ctx, parent, sub_component):
    connectors = _connector_entries(ctx, sub_component, 'table_row_connectors')
    if not connectors:
        return
    element = sub(ctx, parent, 'TABLE-ROW-CONNECTORS')
    for connector in connectors:
        entry = sub(ctx, element, 'TABLE-ROW-CONNECTOR')
        _add_connector_names(ctx, entry, connector)
        _add_linked_ref(ctx, entry, 'TABLE-REF', connector, 'table_reference', 'table')
        _add_name_ref(ctx, entry, 'TABLE-ROW-SNREF', connector.get('table_row'))


def _add_dtc_connectors(ctx, parent, sub_component):
    connectors = _connector_entries(ctx, sub_component, 'diag_trouble_code_connectors')
    if not connectors:
        return
    element = sub(ctx, parent, 'DTC-CONNECTORS')
    for connector in connectors:
        entry = sub(ctx, element, 'DTC-CONNECTOR')
        _add_connector_names(ctx, entry, connector)
        _add_linked_ref(ctx, entry, 'DTC-DOP-REF', connector, 'dtc_dop_reference', 'dtc_dop')
        _add_name_ref(ctx, entry, 'DTC-SNREF', connector.get('diag_trouble_code'))


def _add_sub_component(ctx, parent, key):
    # ODX 2.2 form as far as known; no schema or original document to compare.
    obj = ctx.take(key)
    element = identified(ctx, parent, 'SUB-COMPONENT', ctx.own_id(key), obj, SEMANTIC=obj.get('semantic'))
    add_names(ctx, element, obj)
    _add_patterns(ctx, element, 'SUB-COMPONENT-PATTERNS', 'SUB-COMPONENT-PATTERN',
                  _connector_entries(ctx, obj, 'sub_component_patterns'))
    _add_param_connectors(ctx, element, obj)
    _add_table_row_connectors(ctx, element, obj)
    if obj.get('env_data_connectors'):
        # The pools hold no environment data connector; there is no writer for one.
        ctx.report['sub_component_env_data_connectors_not_written'] += 1
    _add_dtc_connectors(ctx, element, obj)
    if obj.get('dtc_dop_names') or obj.get('dtc_names'):
        # Plain name lists without a place in the SUB-COMPONENT.
        ctx.report['sub_component_dtc_names_not_written'] += 1
    return element


def add_sub_components(ctx, parent, layer_data):
    """Append SUB-COMPONENTS in the order of 'sub_component_references'; None when the layer has none."""
    # State charts share the SC_ prefix, so only the sub component type counts.
    keys = ctx.ordered(layer_data.get('sub_component_references'), ctx.keys('SC_', _SUB_COMPONENT))
    if not keys:
        return None
    element = sub(ctx, parent, 'SUB-COMPONENTS')
    for key in keys:
        _add_sub_component(ctx, element, key)
    return element
