"""Tests for the ODX tables, their rows and the preconditions inverted from the state chart data."""
import unittest
import xml.etree.ElementTree as ET

from odx_export import tables
from tests.odx_support import context

OWN = '0.0.0@L.sd'
OTHER = '0.0.0@M.sd'


def reference(object_id, pool_id=OWN):
    return {'object_id': object_id, 'pool_id': pool_id}


def names(short_name, oid=None):
    return {'short_name': short_name, 'long_name': None, 'long_name_id': None, 'description': None,
            'description_id': None, 'unique_object_id': oid}


def row(short_name, key, dop_reference=None, oid=None):
    result = names(short_name, oid)
    result.update({'key': key, 'dop_base_reference': dop_reference if dop_reference is not None
                   else reference('DOP_L_D1'), 'special_data_group_references': [],
                   'pre_condition_state_references': None})
    return result


def table(short_name, row_references, semantic='SEM', oid=None, dop_reference=None):
    result = names(short_name, oid)
    result.update({'semantic': semantic, 'diag_com_primitive_references': [],
                   'dop_simple_reference': dop_reference if dop_reference is not None else reference('DOP_L_D1'),
                   'special_data_group_references': [],
                   'table_key_map': [{'map_key': row_reference['object_id'], 'reference': row_reference}
                                     for row_reference in row_references]})
    return result


def definition(table_parameter):
    return {'#OBJECT_TYPE': 'MCD_DB_PRECONDITION_DEFINITION', 'diag_com_primitive': None,
            'table_parameter': table_parameter}


def chart_data(entries):
    """DB_STATE_CHART_DATA from [(state short name, [table parameter reference, ...]), ...]."""
    return {'state_transition_transition_actions_map': [],
            'state_precondition_definitions_map': [
                {'map_key': state, 'items': [definition(item) for item in items]} for state, items in entries]}


def chart(semantic):
    result = names('Chart')
    result.update({'semantic': semantic, 'ecu_states': [], 'start_state': None, 'ecu_state_transitions': []})
    return result


def pool(objects, **kwargs):
    base = {'DOP_L_D1': ('DB_DOP_SIMPLE_BASE', {}),
            'DOP_L_S1': ('MCD_DB_PARAMETER_STRUCTURE', {})}
    base.update(objects)
    return context(base, **kwargs)


def tags(element):
    return [child.tag for child in element]


def written(ctx, layer_data=None):
    return tables.add_tables(ctx, ET.Element('DIAG-DATA-DICTIONARY-SPEC'), layer_data or {})


def table_element(tables_element, table_id):
    return next(element for element in tables_element if element.get('ID') == table_id)


class RowPlaceTests(unittest.TestCase):
    def test_row_is_embedded_in_table_named_by_row_id(self):
        rows = [reference('TBP_L_T1.R1'), reference('TBP_L_T2.R2')]
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', rows)),
                    'TB_L_T2': ('MCD_DB_TABLE', table('T2', rows)),
                    'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1')),
                    'TBP_L_T2.R2': ('MCD_DB_TABLE_PARAMETER', row('R2', '2'))})
        self.assertEqual(tables.row_owners(ctx, ['TB_L_T1', 'TB_L_T2']),
                         {'TBP_L_T1.R1': 'TB_L_T1', 'TBP_L_T2.R2': 'TB_L_T2'})
        element = written(ctx)
        first, second = table_element(element, 'T1'), table_element(element, 'T2')
        self.assertEqual(tags(first), ['SHORT-NAME', 'KEY-DOP-REF', 'TABLE-ROW', 'TABLE-ROW-REF'])
        self.assertEqual(first.find('TABLE-ROW').get('ID'), 'T1.R1')
        self.assertEqual(first.find('TABLE-ROW-REF').attrib, {'ID-REF': 'T2.R2'})
        self.assertEqual(tags(second), ['SHORT-NAME', 'KEY-DOP-REF', 'TABLE-ROW-REF', 'TABLE-ROW'])
        self.assertEqual(second.find('TABLE-ROW').get('ID'), 'T2.R2')
        self.assertEqual(second.find('TABLE-ROW-REF').attrib, {'ID-REF': 'T1.R1'})
        self.assertEqual(len(element.findall('.//TABLE-ROW')), 2)
        self.assertNotIn('MCD_DB_TABLE_PARAMETER', ctx.unused())
        self.assertNotIn('MCD_DB_TABLE', ctx.unused())

    def test_row_with_unrelated_id_is_embedded_in_its_only_table(self):
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', [reference('TBP_L_X.R1')])),
                    'TBP_L_X.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1'))})
        self.assertEqual(tables.row_owners(ctx, ['TB_L_T1']), {'TBP_L_X.R1': 'TB_L_T1'})
        element = written(ctx)
        self.assertEqual(table_element(element, 'T1').find('TABLE-ROW').get('ID'), 'X.R1')
        self.assertIn('TBP_L_X.R1', ctx.used)

    def test_row_with_unrelated_id_goes_to_the_first_listing_table(self):
        rows = [reference('TBP_L_X.R1')]
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', rows)),
                    'TB_L_T2': ('MCD_DB_TABLE', table('T2', rows)),
                    'TBP_L_X.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1'))})
        self.assertEqual(tables.row_owners(ctx, ['TB_L_T2', 'TB_L_T1']), {'TBP_L_X.R1': 'TB_L_T2'})

    def test_row_of_other_pool_is_row_ref(self):
        other_row = reference('TBP_M_T1.R1', OTHER)
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', [other_row]))},
                   object_type=lambda pool_id, key: 'MCD_DB_TABLE_PARAMETER')
        self.assertEqual(tables.row_owners(ctx, ['TB_L_T1']), {})
        element = table_element(written(ctx), 'T1')
        self.assertIsNone(element.find('TABLE-ROW'))
        self.assertEqual(element.find('TABLE-ROW-REF').attrib,
                         {'ID-REF': 'T1.R1', 'DOCREF': 'M', 'DOCTYPE': 'LAYER'})

    def test_row_listed_by_no_table_has_no_place(self):
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', [reference('TBP_L_T1.R1')])),
                    'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1')),
                    'TBP_L_Y.R9': ('MCD_DB_TABLE_PARAMETER', row('R9', '9'))})
        element = written(ctx)
        self.assertEqual(ctx.without_place, ['TBP_L_Y.R9'])
        self.assertNotIn('MCD_DB_TABLE_PARAMETER', ctx.unused())
        self.assertEqual([row_element.get('ID') for row_element in element.iter('TABLE-ROW')], ['T1.R1'])

    def test_row_listed_by_no_table_but_referenced_stays_unused(self):
        table_key = {'short_name': 'Key', 'mcd_parameter_type': 'eTABLE_KEY',
                     'table_reference': reference('TBP_L_Y.R9'), 'is_table_row_reference': True}
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', [reference('TBP_L_T1.R1')])),
                    'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1')),
                    'TBP_L_Y.R9': ('MCD_DB_TABLE_PARAMETER', row('R9', '9')),
                    'DOP_L_S2': ('MCD_DB_PARAMETER_STRUCTURE', {'parameters': [table_key]})})
        written(ctx)
        self.assertEqual(ctx.without_place, [])
        self.assertEqual(ctx.unused()['MCD_DB_TABLE_PARAMETER'], 1)
        self.assertNotIn('TBP_L_Y.R9', ctx.used)

    def test_rows_without_any_table_have_no_place(self):
        ctx = pool({'TBP_L_Y.R9': ('MCD_DB_TABLE_PARAMETER', row('R9', '9'))})
        self.assertIsNone(written(ctx))
        self.assertEqual(ctx.without_place, ['TBP_L_Y.R9'])

    def test_row_listed_twice_in_its_table_is_embedded_once(self):
        rows = [reference('TBP_L_T1.R1'), reference('TBP_L_T1.R1')]
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', rows)),
                    'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1'))})
        element = table_element(written(ctx), 'T1')
        self.assertEqual(tags(element), ['SHORT-NAME', 'KEY-DOP-REF', 'TABLE-ROW', 'TABLE-ROW-REF'])

    def test_row_key_outside_naming_rule_is_unresolvable_row_ref(self):
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', [reference('ROW_1')])),
                    'ROW_1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1'))})
        self.assertEqual(tables.row_owners(ctx, ['TB_L_T1']), {})
        element = table_element(written(ctx), 'T1')
        self.assertEqual(element.find('TABLE-ROW-REF').attrib, {'ID-REF': 'ROW_1'})
        self.assertEqual(ctx.report['unresolvable_references'], 1)


class TableContentTests(unittest.TestCase):
    def test_table(self):
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', [reference('TBP_L_T1.R1')], oid='OID-T')),
                    'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1', oid='OID-R'))})
        element = written(ctx)
        self.assertEqual(element.tag, 'TABLES')
        table_el = element.find('TABLE')
        self.assertEqual(table_el.attrib, {'ID': 'T1', 'OID': 'OID-T', 'SEMANTIC': 'SEM'})
        self.assertEqual(table_el.find('KEY-DOP-REF').attrib, {'ID-REF': 'D1'})
        row_el = table_el.find('TABLE-ROW')
        self.assertEqual(row_el.attrib, {'ID': 'T1.R1', 'OID': 'OID-R'})
        self.assertEqual(tags(row_el), ['SHORT-NAME', 'KEY', 'DATA-OBJECT-PROP-REF'])
        self.assertEqual(row_el.findtext('KEY'), '1')

    def test_tables_follow_layer_order(self):
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', [])),
                    'TB_L_T2': ('MCD_DB_TABLE', table('T2', []))})
        layer_data = {'table_references': [{'reference': reference('TB_L_T2')}]}
        self.assertEqual([element.get('ID') for element in written(ctx, layer_data)], ['T2', 'T1'])

    def test_unset_key_dop_reference_is_absent(self):
        table_object = table('T1', [])
        table_object['dop_simple_reference'] = None
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table_object)})
        self.assertEqual(tags(written(ctx).find('TABLE')), ['SHORT-NAME'])
        self.assertEqual(ctx.report['empty_references'], 0)

    def test_no_tables_writes_nothing(self):
        parent = ET.Element('DIAG-DATA-DICTIONARY-SPEC')
        self.assertIsNone(tables.add_tables(pool({}), parent, {}))
        self.assertEqual(len(parent), 0)

    def test_row_reference_type_follows_target_type(self):
        missing = reference('DOP_Z_D1', '0.0.0@Z.sd')
        rows = [reference('TBP_L_T1.R1'), reference('TBP_L_T1.R2'), reference('TBP_L_T1.R3')]
        ctx = pool({'TB_L_T1': ('MCD_DB_TABLE', table('T1', rows)),
                    'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1', reference('DOP_L_S1'))),
                    'TBP_L_T1.R2': ('MCD_DB_TABLE_PARAMETER', row('R2', '2', reference('DOP_L_D1'))),
                    'TBP_L_T1.R3': ('MCD_DB_TABLE_PARAMETER', row('R3', '3', missing))},
                   object_type=lambda pool_id, key: None)
        row_elements = list(written(ctx).iter('TABLE-ROW'))
        self.assertEqual(row_elements[0].find('STRUCTURE-REF').attrib, {'ID-REF': 'S1'})
        self.assertEqual(row_elements[1].find('DATA-OBJECT-PROP-REF').attrib, {'ID-REF': 'D1'})
        self.assertEqual(row_elements[2].find('DATA-OBJECT-PROP-REF').attrib,
                         {'ID-REF': 'DOP_Z_D1', 'DOCREF': 'Z', 'DOCTYPE': 'LAYER'})
        self.assertIsNone(row_elements[2].find('STRUCTURE-REF'))
        self.assertEqual(ctx.report['unresolvable_references'], 1)


class PreconditionTests(unittest.TestCase):
    def test_preconditions_are_inverted_from_state_chart_data(self):
        ctx = pool({'SC_L_C1': ('MCD_DB_ECU_STATE_CHART', chart('SESSION')),
                    'DbStateChartDataSESSION': ('DB_STATE_CHART_DATA', chart_data(
                        [('Default', [reference('TBP_L_T1.R1')]),
                         ('Extended', [reference('TBP_L_T1.R1'), reference('TBP_L_T1.R2')])])),
                    'TB_L_T1': ('MCD_DB_TABLE', table('T1', [reference('TBP_L_T1.R1')])),
                    'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1'))})
        self.assertEqual(tables.precondition_states(ctx),
                         {'TBP_L_T1.R1': ['C1.Default', 'C1.Extended'], 'TBP_L_T1.R2': ['C1.Extended']})
        self.assertIn('DbStateChartDataSESSION', ctx.used)
        row_el = written(pool({'SC_L_C1': ('MCD_DB_ECU_STATE_CHART', chart('SESSION')),
                               'DbStateChartDataSESSION': ('DB_STATE_CHART_DATA', chart_data(
                                   [('Default', [reference('TBP_L_T1.R1')])])),
                               'TB_L_T1': ('MCD_DB_TABLE', table('T1', [reference('TBP_L_T1.R1')])),
                               'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', row('R1', '1'))})).find('.//TABLE-ROW')
        self.assertEqual(tags(row_el), ['SHORT-NAME', 'KEY', 'DATA-OBJECT-PROP-REF', 'PRE-CONDITION-STATE-REFS'])
        self.assertEqual([element.attrib for element in row_el.find('PRE-CONDITION-STATE-REFS')],
                         [{'ID-REF': 'C1.Default'}])

    def test_empty_table_parameter_in_state_chart_data_is_skipped(self):
        ctx = pool({'SC_L_C1': ('MCD_DB_ECU_STATE_CHART', chart('SESSION')),
                    'DbStateChartDataSESSION': ('DB_STATE_CHART_DATA', chart_data(
                        [('Default', [None, reference(''), reference('TBP_L_T1.R1')])]))})
        self.assertEqual(tables.precondition_states(ctx), {'TBP_L_T1.R1': ['C1.Default']})
        self.assertEqual(ctx.report['empty_references'], 2)

    def test_service_precondition_in_state_chart_data_is_skipped_without_counting(self):
        data = chart_data([('Default', [None, reference('TBP_L_T1.R1')])])
        data['state_precondition_definitions_map'][0]['items'][0]['diag_com_primitive'] = reference('DC_L_S1')
        ctx = pool({'SC_L_C1': ('MCD_DB_ECU_STATE_CHART', chart('SESSION')),
                    'DbStateChartDataSESSION': ('DB_STATE_CHART_DATA', data)})
        self.assertEqual(tables.precondition_states(ctx), {'TBP_L_T1.R1': ['C1.Default']})
        self.assertEqual(ctx.report['empty_references'], 0)

    def test_precondition_without_matching_chart_is_counted(self):
        ctx = pool({'SC_L_C1': ('MCD_DB_ECU_STATE_CHART', chart('OTHER')),
                    'DbStateChartDataSESSION': ('DB_STATE_CHART_DATA', chart_data(
                        [('Default', [reference('TBP_L_T1.R1')])]))})
        self.assertEqual(tables.precondition_states(ctx), {'TBP_L_T1.R1': ['SESSION.Default']})
        self.assertEqual(ctx.report['unresolvable_references'], 1)


if __name__ == '__main__':
    unittest.main()
