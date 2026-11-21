import os
import shutil
import tempfile
import unittest

from classes.PBL import default_library_path
from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from common_utils.reference_resolver import NOT_RESOLVABLE, ReferenceResolver, insert_after
from tests import support
from tests.support import REPOSITORY_ROOT, string_hash, unit_body

LIBRARY = default_library_path(REPOSITORY_ROOT)
CAPTION_KEY = string_hash('CAP_A', 'A')


def caption_record(short_name='CAP_A'):
    body = (support.ObjectBytes().native_ascii(None).native_ascii(None).native_ascii(None)
            .native_unicode(None).native_unicode(None).native_ascii(short_name))
    return body.build('MCD_DB_SPECIAL_DATA_GROUP_CAPTION')


def group_record(caption=None, items=None):
    element = support.sdg_element_body('TXT', 'Content')
    if items is None:
        items = [('MCD_DB_SPECIAL_DATA_ELEMENT', element)]
    return support.sdg_group_body(items, caption).build('MCD_DB_SPECIAL_DATA_GROUP')


class ReferenceResolverTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def make_project(self, pool_objects=None, sdg_records=None, extra_pools=None, ascii_strings=()):
        pools = {'A.sd': {'CAP_A': caption_record(), 'UNIT_ONE': unit_body().build('MCD_DB_UNIT')}}
        if pool_objects is not None:
            pools['A.sd'] = pool_objects
        pools.update(extra_pools or {})
        support.write_project(self.folder, pools, list(ascii_strings), [])
        if sdg_records is not None:
            support.write_sdg_file(self.folder, 'A.sd', sdg_records)
        return ReferenceResolver(self.folder, StringStorage(self.folder), PblRecordManager(LIBRARY))

    def resolve(self, resolver, obj):
        resolver.resolve_object(obj, 'A.sd')
        return obj

    def test_insert_after_keeps_order(self):
        obj = {'a': 1, 'b': 2, 'c': 3}
        insert_after(obj, 'a', 'new', 9)
        self.assertEqual(['a', 'new', 'b', 'c'], list(obj))
        self.assertEqual(9, obj['new'])

    def test_sdg_reference_resolves_to_group_with_caption(self):
        resolver = self.make_project(sdg_records=[group_record((CAPTION_KEY, None))])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})
        self.assertEqual(['special_data_group_references', 'special_data_groups'], list(obj))
        group = obj['special_data_groups'][0]
        self.assertEqual('Content', group['items'][0]['content'])
        self.assertEqual('CAP_A', group['caption']['short_name'])
        self.assertEqual(['items', 'caption_reference', 'caption', 'semantic_information'],
                         [key for key in group if key != '#OBJECT_TYPE'])

    def test_group_without_caption_reference_has_no_caption(self):
        resolver = self.make_project(sdg_records=[group_record()])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})
        self.assertIsNone(obj['special_data_groups'][0]['caption'])

    def test_nested_group_gets_its_caption(self):
        inner = ('MCD_DB_SPECIAL_DATA_GROUP', support.sdg_group_body((), (CAPTION_KEY, '')))
        resolver = self.make_project(sdg_records=[group_record(items=[inner])])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})
        self.assertEqual('CAP_A', obj['special_data_groups'][0]['items'][0]['caption']['short_name'])

    def test_sdg_reference_in_nested_parameter_is_resolved(self):
        resolver = self.make_project(sdg_records=[group_record()])
        obj = self.resolve(resolver, {'parameters': [{'special_data_group_references': [{'object_id': 1}]}]})
        self.assertEqual('Content', obj['parameters'][0]['special_data_groups'][0]['items'][0]['content'])

    def test_sdg_reference_without_file_is_not_resolvable(self):
        resolver = self.make_project()
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}, {'object_id': 2}]})
        self.assertEqual([NOT_RESOLVABLE, NOT_RESOLVABLE], obj['special_data_groups'])

    def test_sdg_reference_out_of_range_is_not_resolvable(self):
        resolver = self.make_project(sdg_records=[group_record()])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 0}, {'object_id': 1}, {'object_id': 2}]})
        groups = obj['special_data_groups']
        self.assertEqual([NOT_RESOLVABLE, NOT_RESOLVABLE], [groups[0], groups[2]])
        self.assertIsInstance(groups[1], dict)

    def test_undecodable_record_raises(self):
        resolver = self.make_project(sdg_records=[bytearray(b'\x00')])
        with self.assertRaises(Exception):
            self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})

    def test_caption_key_missing_or_other_type_is_not_resolvable(self):
        missing = (string_hash('MISSING', 'A'), None)
        other_type = (string_hash('UNIT_ONE', 'A'), None)
        resolver = self.make_project(sdg_records=[group_record(missing), group_record(other_type)])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}, {'object_id': 2}]})
        self.assertEqual([NOT_RESOLVABLE, NOT_RESOLVABLE], [group['caption'] for group in obj['special_data_groups']])

    def test_caption_is_looked_up_in_own_pool_whatever_pool_id_says(self):
        resolver = self.make_project(sdg_records=[group_record((CAPTION_KEY, 'B.sd'))],
                                     ascii_strings=['B.sd'],
                                     extra_pools={'B.sd': {'UNIT_ONE': unit_body().build('MCD_DB_UNIT')}})
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})
        group = obj['special_data_groups'][0]
        self.assertEqual('CAP_A', group['caption']['short_name'])
        self.assertEqual('B.sd', group['caption_reference']['pool_id'])

    def test_caption_key_of_type_without_loader_is_not_resolvable(self):
        pool = {'CAP_A': support.ObjectBytes().build('DB_DOP_STRUCT'), 'UNIT_ONE': unit_body().build('MCD_DB_UNIT')}
        resolver = self.make_project(pool_objects=pool, sdg_records=[group_record((CAPTION_KEY, None))])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})
        self.assertEqual(NOT_RESOLVABLE, obj['special_data_groups'][0]['caption'])

    def test_caption_reference_outside_special_data_group_is_left_alone(self):
        resolver = self.make_project()
        other = {'#OBJECT_TYPE': 'MCD_DB_UNIT', 'caption_reference': {'object_key': CAPTION_KEY, 'pool_id': None}}
        self.assertEqual(['#OBJECT_TYPE', 'caption_reference'], list(self.resolve(resolver, other)))

    def test_empty_sdg_references_add_nothing(self):
        resolver = self.make_project(sdg_records=[group_record()])
        obj = self.resolve(resolver, {'special_data_group_references': [], 'other': [1, {'x': 2}]})
        self.assertEqual({'special_data_group_references': [], 'other': [1, {'x': 2}]}, obj)

    def test_load_object_by_name_hash_and_missing(self):
        resolver = self.make_project()
        by_name = resolver.load_object('', 'CAP_A', 'A.sd')
        self.assertEqual('CAP_A', by_name['short_name'])
        self.assertEqual(by_name, resolver.load_object(None, CAPTION_KEY, 'A.sd'))
        self.assertIsNone(resolver.load_object('A.sd', 'NOPE', 'A.sd'))
        self.assertIsNone(resolver.load_object('Z.sd', 'CAP_A', 'A.sd'))


class StateAndTableTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)
        self.pools = {}
        self.ascii_strings = []
        self.unicode_strings = []
        self._resolver = None

    def add(self, pool, name, type_name, body):
        self.pools.setdefault(pool, {})[name] = body.build(type_name)
        self.ascii_strings += body.ascii_strings + [name, pool]
        self.unicode_strings += body.unicode_strings

    def add_state(self, name, pool='A.sd', object_name=None):
        self.add(pool, object_name or name, 'MCD_DB_ECU_STATE', support.ecu_state_body(name))

    def add_service(self, name, pool='A.sd'):
        # any object with a short name serves as a service here
        self.add(pool, name, 'MCD_DB_ECU_STATE', support.ecu_state_body(name))

    def add_transition(self, name, source, target, pool='A.sd'):
        self.add(pool, name, 'MCD_DB_ECU_STATE_TRANSITION', support.state_transition_body(name, source, target))

    def resolver(self):
        # The project is written on first use, so objects are added before the first resolve
        if self._resolver is None:
            support.write_project(self.folder, self.pools, self.ascii_strings, self.unicode_strings)
            self._resolver = ReferenceResolver(self.folder, StringStorage(self.folder), PblRecordManager(LIBRARY))
        return self._resolver

    def resolve(self, obj, pool='A.sd'):
        self.resolver().resolve_object(obj, pool)
        return obj

    def transition_object(self, **fields):
        obj = {'#OBJECT_TYPE': 'MCD_DB_ECU_STATE_TRANSITION', 'short_name': 'TR_AB',
               'source_state': {'object_id': 'ST_A', 'pool_id': 'A.sd', 'attributes': []},
               'target_state': {'object_id': 'ST_B', 'pool_id': 'A.sd', 'attributes': []}}
        obj.update(fields)
        return obj

    def test_transition_gets_state_short_names(self):
        self.add_state('ST_A')
        self.add_state('ST_B', pool='B.sd')
        obj = self.transition_object()
        obj['target_state']['pool_id'] = 'B.sd'
        self.resolve(obj)
        self.assertEqual(['#OBJECT_TYPE', 'short_name', 'source_state', 'source_state_short_name',
                          'target_state', 'target_state_short_name'], list(obj))
        self.assertEqual('ST_A', obj['source_state_short_name'])
        self.assertEqual('ST_B', obj['target_state_short_name'])

    def test_transition_with_empty_pool_id_resolves_in_own_pool(self):
        self.add_state('ST_A')
        self.add_state('ST_B')
        obj = self.transition_object()
        obj['source_state']['pool_id'] = ''
        obj['target_state']['pool_id'] = None
        self.resolve(obj)
        self.assertEqual(['ST_A', 'ST_B'], [obj['source_state_short_name'], obj['target_state_short_name']])

    def test_transition_with_missing_state_is_not_resolvable(self):
        self.add_state('ST_A')
        obj = self.transition_object()
        obj['target_state']['pool_id'] = 'Z.sd'
        self.resolve(obj)
        self.assertEqual('ST_A', obj['source_state_short_name'])
        self.assertEqual(NOT_RESOLVABLE, obj['target_state_short_name'])

    def test_action_gets_service_short_name(self):
        self.add_service('SVC_X')
        self.add_service('SVC_Y', pool='B.sd')
        obj = [{'#OBJECT_TYPE': 'MCD_DB_STATE_TRANSITION_ACTION', 'diag_com_primitive': {'object_id': 'SVC_X', 'pool_id': ''}},
               {'#OBJECT_TYPE': 'MCD_DB_STATE_TRANSITION_ACTION', 'diag_com_primitive': {'object_id': 'SVC_Y', 'pool_id': 'B.sd'}},
               {'#OBJECT_TYPE': 'MCD_DB_STATE_TRANSITION_ACTION', 'diag_com_primitive': {'object_id': 'NOPE', 'pool_id': 'B.sd'}}]
        self.resolve(obj)
        self.assertEqual(['SVC_X', 'SVC_Y', NOT_RESOLVABLE], [action['diag_com_primitive_short_name'] for action in obj])
        self.assertEqual(['#OBJECT_TYPE', 'diag_com_primitive', 'diag_com_primitive_short_name'], list(obj[0]))

    def test_action_without_service_gets_nothing(self):
        obj = self.resolve({'#OBJECT_TYPE': 'MCD_DB_STATE_TRANSITION_ACTION', 'diag_com_primitive': None})
        self.assertEqual(['#OBJECT_TYPE', 'diag_com_primitive'], list(obj))

    def chart_object(self, semantic='SEM'):
        return {'#OBJECT_TYPE': 'MCD_DB_ECU_STATE_CHART', 'semantic': semantic, 'ecu_state_transitions': [
            {'name': 'TR_AB', 'reference': {'object_id': 'TR_AB', 'pool_id': 'A.sd', 'attributes': []}},
            {'name': 'TR_BA', 'reference': {'object_id': 'TR_BA', 'pool_id': '', 'attributes': []}}]}

    def add_chart_parts(self):
        self.add_state('ST_A')
        self.add_state('ST_B')
        self.add_transition('TR_AB', ('ST_A', 'A.sd'), ('ST_B', ''))
        self.add_transition('TR_BA', ('ST_B', ''), ('ST_A', None))
        self.add_service('SVC_X')
        self.add_service('SVC_Y')

    def test_chart_lists_transitions_with_services(self):
        self.add_chart_parts()
        actions = [('TR_AB', [support.state_transition_action_body('SVC_X', 'A.sd'),
                              support.state_transition_action_body('SVC_Y', None)])]
        self.add('A.sd', 'DbStateChartDataSEM', 'DB_STATE_CHART_DATA', support.state_chart_data_body(actions))
        chart = self.resolve(self.chart_object())
        self.assertEqual(['#OBJECT_TYPE', 'semantic', 'ecu_state_transitions', 'transitions'], list(chart))
        self.assertEqual([
            {'transition': 'TR_AB', 'source_state': 'ST_A', 'target_state': 'ST_B', 'services': ['SVC_X', 'SVC_Y']},
            {'transition': 'TR_BA', 'source_state': 'ST_B', 'target_state': 'ST_A', 'services': []}],
            chart['transitions'])
        self.assertEqual(['transition', 'source_state', 'target_state', 'services'], list(chart['transitions'][0]))

    def test_chart_without_chart_data_has_empty_services(self):
        self.add_chart_parts()
        for semantic in ('SEM', ''):
            chart = self.resolve(self.chart_object(semantic))
            self.assertEqual([[], []], [entry['services'] for entry in chart['transitions']])
            self.assertEqual('TR_AB', chart['transitions'][0]['transition'])

    def test_chart_with_missing_transition_is_not_resolvable(self):
        self.add_chart_parts()
        chart = self.chart_object()
        chart['ecu_state_transitions'][1]['reference']['object_id'] = 'NOPE'
        self.resolve(chart)
        self.assertEqual({'transition': NOT_RESOLVABLE, 'source_state': NOT_RESOLVABLE,
                          'target_state': NOT_RESOLVABLE, 'services': []}, chart['transitions'][1])

    def connector_object(self, table_row='ROW_1', table_pool='A.sd'):
        return {'#OBJECT_TYPE': 'MCD_DB_TABLE_ROW_CONNECTOR', 'table_row': 'ROW_1' if table_row is None else table_row,
                'table_reference': {'object_id': 'TAB_A', 'pool_id': table_pool, 'attributes': []}, 'table': None}

    def add_table(self, rows=(('ROW_1', 'F190'), ('ROW_2', 'F191')), pool='A.sd', row_pool=''):
        entries = []
        for name, key in rows:
            self.add(pool, name, 'MCD_DB_TABLE_PARAMETER', support.table_row_body(name, key))
            entries.append((name, name, row_pool))
        self.add(pool, 'TAB_A', 'MCD_DB_TABLE', support.table_body('TAB_A', entries))

    def test_row_connector_gets_table_short_name_and_row_key(self):
        self.add_table()
        for row, key in (('ROW_1', 'F190'), ('ROW_2', 'F191')):
            obj = self.resolve(self.connector_object(row))
            self.assertEqual('TAB_A', obj['table_short_name'])
            self.assertEqual(key, obj['table_row_key'])
        self.assertEqual(['#OBJECT_TYPE', 'table_row', 'table_short_name', 'table_row_key', 'table_reference', 'table'],
                         list(obj))

    def test_row_connector_with_empty_row_pool_ids_resolves_rows_in_pool_of_table(self):
        self.add_table(pool='B.sd')
        obj = self.resolve(self.connector_object(table_pool='B.sd'), pool='A.sd')
        self.assertEqual(('TAB_A', 'F190'), (obj['table_short_name'], obj['table_row_key']))

    def test_row_connector_with_empty_table_pool_id_resolves_table_in_own_pool(self):
        self.add_table()
        for empty in ('', None):
            obj = self.resolve(self.connector_object(table_pool=empty))
            self.assertEqual(('TAB_A', 'F190'), (obj['table_short_name'], obj['table_row_key']))

    def test_row_connector_with_missing_row_is_not_resolvable(self):
        self.add_table()
        obj = self.resolve(self.connector_object('ROW_9'))
        self.assertEqual(('TAB_A', NOT_RESOLVABLE), (obj['table_short_name'], obj['table_row_key']))

    def test_row_connector_without_row_name_does_not_match_unloadable_row(self):
        self.add('A.sd', 'TAB_A', 'MCD_DB_TABLE', support.table_body('TAB_A', [('GONE', 'GONE', '')]))
        obj = self.connector_object()
        obj['table_row'] = None
        obj = self.resolve(obj)
        self.assertEqual(('TAB_A', NOT_RESOLVABLE), (obj['table_short_name'], obj['table_row_key']))

    def test_row_connector_with_missing_table_is_not_resolvable(self):
        self.add_table()
        obj = self.resolve(self.connector_object(table_pool='Z.sd'))
        self.assertEqual((NOT_RESOLVABLE, NOT_RESOLVABLE), (obj['table_short_name'], obj['table_row_key']))

    def test_odx_link_row_connector_is_unchanged(self):
        self.add_table()
        obj = {'#OBJECT_TYPE': 'MCD_DB_TABLE_ROW_CONNECTOR', 'table_row': 'ROW_1', 'table_reference': None, 'table': {'x': 1}}
        self.assertEqual(['#OBJECT_TYPE', 'table_row', 'table_reference', 'table'], list(self.resolve(obj)))


if __name__ == '__main__':
    unittest.main()
