"""STATE-CHARTS with STATE-CHART, STATE-TRANSITION and STATE."""
from odx_export.elements import add_names, identified, sub

_CHART = 'MCD_DB_ECU_STATE_CHART'


def _own_object_key(ctx, entry, type_name):
    """Key of the own object a named reference points to, or None after counting why it cannot be embedded."""
    reference = entry.get('reference') if isinstance(entry, dict) else None
    object_id = reference.get('object_id') if reference else None
    if not object_id:
        ctx.report['empty_references'] += 1
        return None
    # A state or transition is written inside its chart; one outside the own pool has no place here.
    if (reference.get('pool_id') != ctx.pool_id or ctx.types.get(object_id) != type_name
            or not ctx.owns(object_id)):
        ctx.report['unresolvable_references'] += 1
        return None
    return object_id


def _add_state_snref(ctx, parent, tag, reference):
    """SOURCE-SNREF or TARGET-SNREF with the last part of the state key."""
    object_id = reference.get('object_id') if reference else None
    if not object_id:
        ctx.report['empty_references'] += 1
        return None
    return sub(ctx, parent, tag, SHORT_NAME=object_id.split('.')[-1])


def _add_transition(ctx, parent, key):
    transition = ctx.take(key)
    element = identified(ctx, parent, 'STATE-TRANSITION', ctx.own_id(key), transition)
    add_names(ctx, element, transition)
    _add_state_snref(ctx, element, 'SOURCE-SNREF', transition.get('source_state'))
    _add_state_snref(ctx, element, 'TARGET-SNREF', transition.get('target_state'))
    return element


def _add_state(ctx, parent, key):
    state = ctx.take(key)
    element = identified(ctx, parent, 'STATE', ctx.own_id(key), state)
    add_names(ctx, element, state)
    return element


def _add_chart(ctx, parent, key):
    chart = ctx.take(key)
    element = identified(ctx, parent, 'STATE-CHART', ctx.own_id(key), chart)
    add_names(ctx, element, chart)
    if chart.get('semantic') is not None:
        sub(ctx, element, 'SEMANTIC', chart['semantic'])
    transition_keys = [_own_object_key(ctx, entry, 'MCD_DB_ECU_STATE_TRANSITION')
                       for entry in chart.get('ecu_state_transitions') or []]
    transition_keys = [transition_key for transition_key in transition_keys if transition_key]
    if transition_keys:
        transitions = sub(ctx, element, 'STATE-TRANSITIONS')
        for transition_key in transition_keys:
            _add_transition(ctx, transitions, transition_key)
    if chart.get('start_state') is not None:
        sub(ctx, element, 'START-STATE-SNREF', SHORT_NAME=chart['start_state'])
    state_keys = [_own_object_key(ctx, entry, 'MCD_DB_ECU_STATE') for entry in chart.get('ecu_states') or []]
    state_keys = [state_key for state_key in state_keys if state_key]
    if state_keys:
        states = sub(ctx, element, 'STATES')
        for state_key in state_keys:
            _add_state(ctx, states, state_key)
    return element


def add_state_charts(ctx, parent, layer_data):
    chart_keys = ctx.ordered(layer_data.get('ecu_state_chart_references'), ctx.keys('SC_', _CHART))
    if not chart_keys:
        return None
    element = sub(ctx, parent, 'STATE-CHARTS')
    for chart_key in chart_keys:
        _add_chart(ctx, element, chart_key)
    return element
