"""TABLES with TABLE, TABLE-ROW and the precondition states inverted from the state chart data."""
from collections import defaultdict

from odx_export import special_data
from odx_export.elements import add_names, add_ref, identified, sub
from odx_export.naming import split_key

_TABLE = 'MCD_DB_TABLE'
_ROW = 'MCD_DB_TABLE_PARAMETER'
_CHART = 'MCD_DB_ECU_STATE_CHART'
_CHART_DATA = 'DB_STATE_CHART_DATA'
_CHART_DATA_PREFIX = 'DbStateChartData'
_STRUCTURE = 'MCD_DB_PARAMETER_STRUCTURE'


def _object_id(reference):
    return reference.get('object_id') if isinstance(reference, dict) else None


def _listed_own_rows(ctx, table):
    """Keys of the own rows a table lists, in the order of its key map."""
    for entry in table.get('table_key_map') or []:
        reference = entry.get('reference') if isinstance(entry, dict) else None
        if reference and reference.get('pool_id') == ctx.pool_id and reference.get('object_id'):
            yield reference['object_id']


def _referenced_own_keys(ctx):
    """Every own key that a reference anywhere in the loaded objects of the pool points to."""
    referenced = set()
    pending = list(ctx.objects.values())
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if value.get('pool_id') == ctx.pool_id and value.get('object_id'):
                referenced.add(value['object_id'])
            pending.extend(value.values())
        elif isinstance(value, (list, tuple)):
            pending.extend(value)
    return referenced


def row_owners(ctx, table_keys):
    """Own row key -> key of the table that embeds the row.

    The table whose ID is the part of the row ID before the last dot takes the row; without
    such a table, the first table (in the given order) that lists the row.
    """
    listing = defaultdict(list)
    for table_key in table_keys:
        for row_key in _listed_own_rows(ctx, ctx.objects[table_key]):
            if ctx.types.get(row_key) == _ROW and split_key(row_key, ctx.layer) is not None:
                if table_key not in listing[row_key]:
                    listing[row_key].append(table_key)
    owners = {}
    for row_key, tables_of_row in listing.items():
        row_id = split_key(row_key, ctx.layer)[1]
        named = 'TB_' + ctx.layer + '_' + row_id.rsplit('.', 1)[0] if '.' in row_id else None
        owners[row_key] = named if named in tables_of_row else tables_of_row[0]
    return owners


def precondition_states(ctx):
    """Row key -> ID-REFs '<chart ID>.<state>' of its precondition states, from DB_STATE_CHART_DATA."""
    charts = {}
    for chart_key in ctx.keys('SC_', _CHART):
        charts.setdefault(ctx.objects[chart_key].get('semantic'), ctx.own_id(chart_key))
    result = defaultdict(list)
    for data_key, type_name in ctx.types.items():
        if type_name != _CHART_DATA:
            continue
        data = ctx.take(data_key)
        semantic = data_key[len(_CHART_DATA_PREFIX):] if data_key.startswith(_CHART_DATA_PREFIX) else data_key
        for entry in data.get('state_precondition_definitions_map') or []:
            state = entry.get('map_key')
            for definition in entry.get('items') or []:
                if not isinstance(definition, dict):
                    continue
                row_key = _object_id(definition.get('table_parameter'))
                # The data holds no table parameter for this definition: an empty reference.
                if not row_key or state is None:
                    ctx.report['empty_references'] += 1
                    continue
                if semantic in charts:
                    state_id = charts[semantic] + '.' + state
                else:
                    state_id = semantic + '.' + state
                    ctx.report['unresolvable_references'] += 1
                result[row_key].append(state_id)
    return dict(result)


def _add_row(ctx, parent, row_key, preconditions):
    row = ctx.take(row_key)
    element = identified(ctx, parent, 'TABLE-ROW', ctx.own_id(row_key), row)
    add_names(ctx, element, row)
    if row.get('key') is not None:
        sub(ctx, element, 'KEY', row['key'])
    reference = row.get('dop_base_reference')
    # A DOP reference whose flag is not set is absent, not an empty reference.
    if reference is not None:
        # An unknown target type (for example in a pool missing from the project) is written as a DOP.
        tag = 'STRUCTURE-REF' if ctx.target_type(reference) == _STRUCTURE else 'DATA-OBJECT-PROP-REF'
        add_ref(ctx, element, tag, reference)
    special_data.sdgs(ctx, element, row)
    states = preconditions.get(row_key)
    if states:
        refs = sub(ctx, element, 'PRE-CONDITION-STATE-REFS')
        for state_id in states:
            sub(ctx, refs, 'PRE-CONDITION-STATE-REF', ID_REF=state_id)
    return element


def _add_table(ctx, parent, table_key, owners, preconditions):
    table = ctx.take(table_key)
    element = identified(ctx, parent, 'TABLE', ctx.own_id(table_key), table, SEMANTIC=table.get('semantic'))
    add_names(ctx, element, table)
    # A key DOP reference whose flag is not set is absent, not an empty reference.
    if table.get('dop_simple_reference') is not None:
        add_ref(ctx, element, 'KEY-DOP-REF', table['dop_simple_reference'])
    embedded = set()
    for entry in table.get('table_key_map') or []:
        reference = entry.get('reference') if isinstance(entry, dict) else None
        row_key = _object_id(reference)
        if (reference is not None and reference.get('pool_id') == ctx.pool_id and owners.get(row_key) == table_key
                and row_key not in embedded):
            embedded.add(row_key)
            _add_row(ctx, element, row_key, preconditions)
        else:
            add_ref(ctx, element, 'TABLE-ROW-REF', reference)
    special_data.sdgs(ctx, element, table)
    return element


def _mark_rows_without_place(ctx):
    """Own rows that no table lists and no object references have no place in ODX."""
    listed = set()
    for key, type_name in ctx.types.items():
        if type_name == _TABLE:
            listed.update(_listed_own_rows(ctx, ctx.objects[key]))
    unlisted = [key for key, type_name in ctx.types.items() if type_name == _ROW and key not in listed]
    if not unlisted:
        return
    referenced = _referenced_own_keys(ctx)
    for key in unlisted:
        if key not in referenced:
            ctx.mark_without_place(key)


def add_tables(ctx, parent, layer_data):
    _mark_rows_without_place(ctx)
    table_keys = ctx.ordered(layer_data.get('table_references'), ctx.keys('TB_', _TABLE))
    preconditions = precondition_states(ctx)
    if not table_keys:
        return None
    owners = row_owners(ctx, table_keys)
    element = sub(ctx, parent, 'TABLES')
    for table_key in table_keys:
        _add_table(ctx, element, table_key, owners, preconditions)
    return element
