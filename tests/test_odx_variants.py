"""Tests for the variant patterns, sub components and the checks of base variants and functional groups."""
import unittest
import xml.etree.ElementTree as ET

from odx_export import variants
from tests.odx_support import context

LAYER_POOL = '0.0.0@B.bv'
GROUP_POOL = '0.0.0@G.fg'


def matching_parameter(service, value, name=None, path=None):
    return {'#OBJECT_TYPE': 'MCD_DB_MATCHING_PARAMETER',
            'diag_com_primitive_reference': {'object_id': service, 'pool_id': None, 'attributes': [],
                                             'audience_filter': 0, 'object_type': 'eMCDSERVICE',
                                             'protocol_short_name_references': None},
            'response_parameter_name': name, 'response_parameter_short_name_path': path,
            'response_parameter_is_short_name_path': path is not None, 'expected_value_string': value}


def pattern(*parameters):
    return {'#OBJECT_TYPE': 'MCD_DB_MATCHING_PATTERN', 'matching_parameters': list(parameters)}


def names(short_name, oid=None, **fields):
    result = {'short_name': short_name, 'long_name': None, 'long_name_id': None, 'description': None,
              'description_id': None, 'unique_object_id': oid}
    result.update(fields)
    return result


def sub_component(short_name, oid=None, **fields):
    result = names(short_name, oid)
    result.update({'diag_trouble_code_connectors': None, 'env_data_connectors': None,
                   'sub_component_param_connectors': None, 'sub_component_patterns': None,
                   'table_row_connectors': None, 'semantic': None, 'dtc_dop_names': [], 'dtc_names': []})
    result.update(fields)
    return result


def param_connector(service, inputs, outputs, short_name=None, **fields):
    result = {'diag_com_primitive_name': service,
              'sub_component_in_parameter_names': [{'name': name, 'is_name': is_name} for name, is_name in inputs],
              'sub_component_out_parameter_names': [{'name': name, 'is_name': is_name} for name, is_name in outputs]}
    result.update(names(short_name, **fields))
    return result


def table_row_connector(table_key, row, short_name=None, **fields):
    result = {'table_reference': {'object_id': table_key, 'pool_id': LAYER_POOL, 'attributes': []}, 'table': None,
              'table_row': row}
    result.update(names(short_name, **fields))
    return result


def dtc_connector(dop_key, dtc, short_name=None, **fields):
    result = {'dtc_dop_reference': {'object_id': dop_key, 'pool_id': LAYER_POOL}, 'dtc_dop': None,
              'diag_trouble_code': dtc}
    result.update(names(short_name, **fields))
    return result


def tags(element):
    return [child.tag for child in element]


class VariantPatternTests(unittest.TestCase):
    def test_variant_pattern_form(self):
        ctx = context({}, pool_id=LAYER_POOL)
        variant = {'variant_patterns': [
            pattern(matching_parameter('S_Read', '1000', name='P'), matching_parameter('S_Id', 'A&B', name='Q')),
            pattern(matching_parameter('S_Read', '2000', name='P'))]}
        written = variants.add_variant_patterns(ctx, ET.Element('ECU-VARIANT'), variant)
        self.assertEqual(written.tag, 'ECU-VARIANT-PATTERNS')
        self.assertEqual(tags(written), ['ECU-VARIANT-PATTERN', 'ECU-VARIANT-PATTERN'])
        first = written[0].find('MATCHING-PARAMETERS')
        self.assertEqual(tags(written[0]), ['MATCHING-PARAMETERS'])
        self.assertEqual(tags(first), ['MATCHING-PARAMETER', 'MATCHING-PARAMETER'])
        self.assertEqual(tags(first[0]), ['EXPECTED-VALUE', 'DIAG-COMM-SNREF', 'OUT-PARAM-IF-SNREF'])
        self.assertEqual(first[0].findtext('EXPECTED-VALUE'), '1000')
        self.assertEqual(first[0].find('DIAG-COMM-SNREF').attrib, {'SHORT-NAME': 'S_Read'})
        self.assertEqual(first[0].find('OUT-PARAM-IF-SNREF').attrib, {'SHORT-NAME': 'P'})
        self.assertEqual(first[1].findtext('EXPECTED-VALUE'), 'A&B')
        self.assertEqual(written[1].findtext('MATCHING-PARAMETERS/MATCHING-PARAMETER/EXPECTED-VALUE'), '2000')

    def test_variant_pattern_short_name_path(self):
        ctx = context({}, pool_id=LAYER_POOL)
        written = variants.add_variant_patterns(ctx, ET.Element('ECU-VARIANT'), {'variant_patterns': [
            pattern(matching_parameter('S_Read', '7', path='Struct.P'))]})
        parameter = written.find('ECU-VARIANT-PATTERN/MATCHING-PARAMETERS/MATCHING-PARAMETER')
        self.assertEqual(tags(parameter), ['EXPECTED-VALUE', 'DIAG-COMM-SNREF', 'OUT-PARAM-IF-SNPATHREF'])
        self.assertEqual(parameter.find('OUT-PARAM-IF-SNPATHREF').attrib, {'SHORT-NAME-PATH': 'Struct.P'})

    def test_no_variant_patterns(self):
        ctx = context({}, pool_id=LAYER_POOL)
        parent = ET.Element('ECU-VARIANT')
        self.assertIsNone(variants.add_variant_patterns(ctx, parent, {'variant_patterns': []}))
        self.assertIsNone(variants.add_variant_patterns(ctx, parent, {}))
        self.assertEqual(len(parent), 0)

    def test_empty_pattern_and_pooled_service_reference_are_reported(self):
        ctx = context({}, pool_id=LAYER_POOL)
        pooled = matching_parameter('DC_V1_S1', '1', name='P')
        pooled['diag_com_primitive_reference']['pool_id'] = LAYER_POOL
        written = variants.add_variant_patterns(ctx, ET.Element('ECU-VARIANT'), {'variant_patterns': [
            None, pattern(), {'matching_parameters': None}, pattern(pooled)]})
        self.assertEqual(len(written), 1)
        self.assertEqual(written.find('ECU-VARIANT-PATTERN/MATCHING-PARAMETERS/MATCHING-PARAMETER/DIAG-COMM-SNREF')
                         .attrib, {'SHORT-NAME': 'DC_V1_S1'})
        self.assertEqual(ctx.report['matching_pattern_empty'], 3)
        self.assertEqual(ctx.report['matching_parameter_pooled_reference'], 1)


class BaseVariantPatternTests(unittest.TestCase):
    def base_variant(self, *entries):
        return {'ecu_variant_patterns': [{'map_key': name, 'ecu_variant_patterns': patterns}
                                         for name, patterns in entries]}

    def test_base_variant_patterns_equal_are_silent(self):
        ctx = context({}, pool_id=LAYER_POOL)
        patterns = [pattern(matching_parameter('S_Read', '1000', name='P'))]
        variants.check_base_variant_patterns(
            ctx, self.base_variant(('V1', patterns), ('V2', [])),
            {'V1': {'variant_patterns': [pattern(matching_parameter('S_Read', '1000', name='P'))]},
             'V2': {'variant_patterns': None}})
        self.assertEqual(ctx.report['base_variant_pattern_mismatch'], 0)

    def test_base_variant_pattern_mismatch_is_reported(self):
        ctx = context({}, pool_id=LAYER_POOL)
        variants.check_base_variant_patterns(
            ctx, self.base_variant(('V1', [pattern(matching_parameter('S_Read', '1000', name='P'))]),
                                   ('V9', [pattern(matching_parameter('S_Read', '9', name='P'))])),
            {'V1': {'variant_patterns': [pattern(matching_parameter('S_Read', '2000', name='P'))]}})
        self.assertEqual(ctx.report['base_variant_pattern_mismatch'], 2)

    def test_variants_by_name_follow_the_reference_list(self):
        found = {'variant_patterns': []}
        base_variant = {'ecu_variant_references': [
            {'name': 'V1', 'reference': {'object_id': 'EV_X1', 'pool_id': LAYER_POOL}},
            {'name': 'V2', 'reference': {'object_id': 'EV_X2', 'pool_id': LAYER_POOL}},
            {'name': 'V3', 'reference': None}]}
        self.assertEqual(variants.variants_by_name(base_variant, {'EV_X1': found, 'EV_X9': {}}), {'V1': found})
        self.assertEqual(variants.variants_by_name({}, {'EV_X1': found}), {})


class SubComponentTests(unittest.TestCase):
    def test_sub_component_basic_form_and_usage(self):
        ctx = context({
            'SC_V1_A': ('MCD_DB_SUB_COMPONENT', sub_component(
                'A', oid='OID-A', semantic='FUNCTION', long_name='Component', long_name_id='TI_A',
                sub_component_patterns=[pattern(matching_parameter('S_Read', '1', name='P'))],
                sub_component_param_connectors=[param_connector(
                    'S_Read', [('In1', True), ('Struct.In2', False)], [('Out1', True)], short_name='PC')],
                table_row_connectors=[table_row_connector('TB_V1_T', 'ROW1', short_name='TC',
                                                          long_name='Row', description='<p>D</p>')],
                diag_trouble_code_connectors=[dtc_connector('DOP_V1_D', 'DTC1', short_name='DC')])),
            'SC_V1_B': ('MCD_DB_SUB_COMPONENT', sub_component('B', semantic='SLAVE')),
            'SC_V1_Chart': ('MCD_DB_STATE_CHART', {}),
            'SC_V2_C': ('MCD_DB_SUB_COMPONENT', sub_component('C')),
            'TB_V1_T': ('MCD_DB_TABLE', {}),
            'DOP_V1_D': ('MCD_DB_DOP_DTC', {}),
        }, pool_id=LAYER_POOL, pool_layers=['B', 'V1', 'V2']).for_layer('V1')
        written = variants.add_sub_components(ctx, ET.Element('ECU-VARIANT'), {'sub_component_references': [
            {'name': 'B', 'reference': {'object_id': 'SC_V1_B', 'pool_id': LAYER_POOL}}]})
        self.assertEqual(written.tag, 'SUB-COMPONENTS')
        self.assertEqual([dict(element.attrib) for element in written],
                         [{'ID': 'B', 'SEMANTIC': 'SLAVE'}, {'ID': 'A', 'OID': 'OID-A', 'SEMANTIC': 'FUNCTION'}])
        self.assertEqual(tags(written[0]), ['SHORT-NAME'])
        component = written[1]
        self.assertEqual(tags(component), ['SHORT-NAME', 'LONG-NAME', 'SUB-COMPONENT-PATTERNS',
                                           'SUB-COMPONENT-PARAM-CONNECTORS', 'TABLE-ROW-CONNECTORS',
                                           'DTC-CONNECTORS'])
        self.assertEqual(component.find('LONG-NAME').get('TI'), 'TI_A')
        parameter = component.find('SUB-COMPONENT-PATTERNS/SUB-COMPONENT-PATTERN/MATCHING-PARAMETERS/'
                                   'MATCHING-PARAMETER')
        self.assertEqual(tags(parameter), ['EXPECTED-VALUE', 'DIAG-COMM-SNREF', 'OUT-PARAM-IF-SNREF'])
        connector = component.find('SUB-COMPONENT-PARAM-CONNECTORS/SUB-COMPONENT-PARAM-CONNECTOR')
        self.assertEqual(tags(connector), ['SHORT-NAME', 'DIAG-COMM-SNREF', 'OUT-PARAM-IF-REFS', 'IN-PARAM-IF-REFS'])
        self.assertEqual(connector.find('DIAG-COMM-SNREF').attrib, {'SHORT-NAME': 'S_Read'})
        self.assertEqual([(ref.tag, dict(ref.attrib)) for ref in connector.find('OUT-PARAM-IF-REFS')],
                         [('OUT-PARAM-IF-SNREF', {'SHORT-NAME': 'Out1'})])
        self.assertEqual([(ref.tag, dict(ref.attrib)) for ref in connector.find('IN-PARAM-IF-REFS')],
                         [('IN-PARAM-IF-SNREF', {'SHORT-NAME': 'In1'}),
                          ('IN-PARAM-IF-SNPATHREF', {'SHORT-NAME-PATH': 'Struct.In2'})])
        row = component.find('TABLE-ROW-CONNECTORS/TABLE-ROW-CONNECTOR')
        self.assertEqual(tags(row), ['SHORT-NAME', 'LONG-NAME', 'DESC', 'TABLE-REF', 'TABLE-ROW-SNREF'])
        self.assertEqual(row.find('TABLE-REF').attrib, {'ID-REF': 'T'})
        self.assertEqual(row.find('TABLE-ROW-SNREF').attrib, {'SHORT-NAME': 'ROW1'})
        dtc = component.find('DTC-CONNECTORS/DTC-CONNECTOR')
        self.assertEqual(tags(dtc), ['SHORT-NAME', 'DTC-DOP-REF', 'DTC-SNREF'])
        self.assertEqual(dtc.find('DTC-DOP-REF').attrib, {'ID-REF': 'D'})
        self.assertEqual(dtc.find('DTC-SNREF').attrib, {'SHORT-NAME': 'DTC1'})
        self.assertEqual(ctx.used, {'SC_V1_A', 'SC_V1_B'})
        self.assertEqual(ctx.report['unresolvable_references'], 0)
        self.assertEqual(sum(ctx.report.values()), 0)

    def test_sub_component_reports_what_has_no_place(self):
        ctx = context({'SC_V1_A': ('MCD_DB_SUB_COMPONENT', sub_component(
            'A', env_data_connectors=[{'short_name': 'E'}], dtc_dop_names=['DOP1'], dtc_names=['DTC1', 'DTC2'],
            sub_component_param_connectors=[param_connector('S_Read', [], [('Out1', True)], unique_object_id='O1'),
                                            None],
            table_row_connectors=[{'table_reference': None, 'table': {'#OBJECT_TYPE': 'DB_ODX_LINK'},
                                   'table_row': 'ROW1', **names('TC')}],
            diag_trouble_code_connectors=[{'dtc_dop_reference': None, 'dtc_dop': {'#OBJECT_TYPE': 'DB_ODX_LINK'},
                                           'diag_trouble_code': 'DTC1', **names(None)}]))},
            pool_id=LAYER_POOL, pool_layers=['B', 'V1', 'V2']).for_layer('V1')
        component = variants.add_sub_components(ctx, ET.Element('ECU-VARIANT'), {})[0]
        self.assertEqual(tags(component), ['SHORT-NAME', 'SUB-COMPONENT-PARAM-CONNECTORS', 'TABLE-ROW-CONNECTORS',
                                           'DTC-CONNECTORS'])
        self.assertEqual(tags(component.find('SUB-COMPONENT-PARAM-CONNECTORS/SUB-COMPONENT-PARAM-CONNECTOR')),
                         ['DIAG-COMM-SNREF', 'OUT-PARAM-IF-REFS'])
        self.assertEqual(tags(component.find('TABLE-ROW-CONNECTORS/TABLE-ROW-CONNECTOR')),
                         ['SHORT-NAME', 'TABLE-ROW-SNREF'])
        self.assertEqual(tags(component.find('DTC-CONNECTORS/DTC-CONNECTOR')), ['DTC-SNREF'])
        self.assertEqual(ctx.report['sub_component_connector_without_short_name'], 2)
        self.assertEqual(ctx.report['sub_component_connector_oid_not_written'], 1)
        self.assertEqual(ctx.report['sub_component_empty_entry'], 1)
        self.assertEqual(ctx.report['sub_component_odx_link_not_written'], 2)
        self.assertEqual(ctx.report['sub_component_env_data_connectors_not_written'], 1)
        self.assertEqual(ctx.report['sub_component_dtc_names_not_written'], 1)

    def test_no_sub_components(self):
        ctx = context({'SC_L_Chart': ('MCD_DB_STATE_CHART', {})})
        parent = ET.Element('ECU-SHARED-DATA')
        self.assertIsNone(variants.add_sub_components(ctx, parent, {}))
        self.assertEqual(len(parent), 0)


class GroupMemberTests(unittest.TestCase):
    def group(self, *pools):
        return {'group_member_references': [
            {'name': 'BV_' + pool, 'reference': {'object_id': 'BV_' + pool, 'pool_id': '0.0.0@%s.bv' % pool}}
            for pool in pools]}

    def test_group_member_with_parent_ref_is_silent(self):
        ctx = context({}, pool_id=GROUP_POOL)
        variants.check_group_members(ctx, self.group('X', 'Y'), lambda pool_id: ['0.0.0@P.pr', GROUP_POOL])
        self.assertEqual(ctx.report['group_member_without_parent_ref'], 0)

    def test_group_member_without_parent_ref_is_reported(self):
        ctx = context({}, pool_id=GROUP_POOL)
        parents = {'0.0.0@X.bv': [GROUP_POOL], '0.0.0@Y.bv': ['0.0.0@H.fg']}
        group = self.group('X', 'Y', 'Z')
        group['group_member_references'].append({'name': 'N', 'reference': {'object_id': 'N', 'pool_id': None}})
        variants.check_group_members(ctx, group, lambda pool_id: parents.get(pool_id, []))
        self.assertEqual(ctx.report['group_member_without_parent_ref'], 3)


if __name__ == '__main__':
    unittest.main()
