"""Tests for the ODX state charts with their states and state transitions."""
import unittest
import xml.etree.ElementTree as ET

from odx_export import state_charts
from tests.odx_support import context

OWN = '0.0.0@L.sd'


def reference(object_id, pool_id=OWN):
    return {'object_id': object_id, 'pool_id': pool_id, 'attributes': []}


def named(object_id, pool_id=OWN):
    return {'name': object_id.rsplit('.', 1)[-1], 'reference': reference(object_id, pool_id)}


def names(short_name, oid=None, long_name=None):
    return {'short_name': short_name, 'long_name': long_name, 'long_name_id': None, 'description': None,
            'description_id': None, 'unique_object_id': oid}


def chart(states, transitions, start_state='Default', semantic='SESSION'):
    result = names('Session', 'OID-C', 'Sessions')
    result.update({'semantic': semantic, 'ecu_states': [named(key) for key in states],
                   'start_state': start_state, 'ecu_state_transitions': [named(key) for key in transitions]})
    return result


def state(short_name):
    result = names(short_name, 'OID-' + short_name)
    result['ecu_state_transitions'] = []
    return result


def transition(short_name, source, target):
    result = names(short_name, 'OID-' + short_name)
    result.update({'source_state': reference(source), 'target_state': reference(target),
                   'has_external_access_method': False, 'external_access_method': None})
    return result


def tags(element):
    return [child.tag for child in element]


class StateChartTests(unittest.TestCase):
    def test_state_chart(self):
        ctx = context({
            'SC_L_C1': ('MCD_DB_ECU_STATE_CHART', chart(['ST_L_C1.Default', 'ST_L_C1.Extended'],
                                                        ['STR_L_C1.DefaultToExtended'])),
            'ST_L_C1.Default': ('MCD_DB_ECU_STATE', state('Default')),
            'ST_L_C1.Extended': ('MCD_DB_ECU_STATE', state('Extended')),
            'STR_L_C1.DefaultToExtended': ('MCD_DB_ECU_STATE_TRANSITION',
                                           transition('DefaultToExtended', 'ST_L_C1.Default', 'ST_L_C1.Extended'))})
        parent = ET.Element('ECU-SHARED-DATA')
        charts = state_charts.add_state_charts(ctx, parent, {})
        self.assertEqual(charts.tag, 'STATE-CHARTS')
        self.assertEqual(tags(parent), ['STATE-CHARTS'])
        element = charts.find('STATE-CHART')
        self.assertEqual(element.attrib, {'ID': 'C1', 'OID': 'OID-C'})
        self.assertEqual(tags(element), ['SHORT-NAME', 'LONG-NAME', 'SEMANTIC', 'STATE-TRANSITIONS',
                                         'START-STATE-SNREF', 'STATES'])
        self.assertEqual(element.findtext('SEMANTIC'), 'SESSION')
        transition_el = element.find('STATE-TRANSITIONS/STATE-TRANSITION')
        self.assertEqual(transition_el.attrib, {'ID': 'C1.DefaultToExtended', 'OID': 'OID-DefaultToExtended'})
        self.assertEqual(tags(transition_el), ['SHORT-NAME', 'SOURCE-SNREF', 'TARGET-SNREF'])
        self.assertEqual(transition_el.find('SOURCE-SNREF').attrib, {'SHORT-NAME': 'Default'})
        self.assertEqual(transition_el.find('TARGET-SNREF').attrib, {'SHORT-NAME': 'Extended'})
        self.assertEqual(element.find('START-STATE-SNREF').attrib, {'SHORT-NAME': 'Default'})
        self.assertEqual([(state_el.get('ID'), state_el.findtext('SHORT-NAME'))
                          for state_el in element.find('STATES')],
                         [('C1.Default', 'Default'), ('C1.Extended', 'Extended')])
        self.assertEqual(ctx.unused(), {})

    def test_state_charts_follow_layer_order(self):
        ctx = context({'SC_L_C1': ('MCD_DB_ECU_STATE_CHART', chart([], [], start_state=None)),
                       'SC_L_C2': ('MCD_DB_ECU_STATE_CHART', chart([], [], start_state=None))})
        layer_data = {'ecu_state_chart_references': [{'reference': reference('SC_L_C2')}]}
        charts = state_charts.add_state_charts(ctx, ET.Element('X'), layer_data)
        self.assertEqual([element.get('ID') for element in charts], ['C2', 'C1'])
        self.assertEqual(tags(charts[0]), ['SHORT-NAME', 'LONG-NAME', 'SEMANTIC'])

    def test_state_or_transition_outside_the_pool_is_counted(self):
        ctx = context({'SC_L_C1': ('MCD_DB_ECU_STATE_CHART', chart(['ST_L_C1.Missing', 'ST_Z_C1.Other'],
                                                                   ['STR_L_C1.Missing']))})
        element = state_charts.add_state_charts(ctx, ET.Element('X'), {}).find('STATE-CHART')
        self.assertEqual(tags(element), ['SHORT-NAME', 'LONG-NAME', 'SEMANTIC', 'START-STATE-SNREF'])
        self.assertEqual(ctx.report['unresolvable_references'], 3)

    def test_no_state_charts_writes_nothing(self):
        parent = ET.Element('X')
        self.assertIsNone(state_charts.add_state_charts(context({}), parent, {}))
        self.assertEqual(len(parent), 0)


class LongerLayerNameTests(unittest.TestCase):
    def test_state_of_a_longer_layer_name_is_not_embedded(self):
        bv = '0.0.0@B.bv'
        result = chart([], [], start_state=None)
        result['ecu_states'] = [named('ST_B_C1.Default', bv), named('ST_B_V1_C1.Other', bv)]
        ctx = context({'SC_B_C1': ('MCD_DB_ECU_STATE_CHART', result),
                       'ST_B_C1.Default': ('MCD_DB_ECU_STATE', state('Default')),
                       'ST_B_V1_C1.Other': ('MCD_DB_ECU_STATE', state('Other'))},
                      pool_id=bv, pool_layers=['B', 'B_V1']).for_layer('B')
        element = state_charts.add_state_charts(ctx, ET.Element('X'), {}).find('STATE-CHART')
        self.assertEqual([state_el.get('ID') for state_el in element.find('STATES')], ['C1.Default'])
        self.assertEqual(ctx.report['unresolvable_references'], 1)
        self.assertNotIn('ST_B_V1_C1.Other', ctx.used)


if __name__ == '__main__':
    unittest.main()
