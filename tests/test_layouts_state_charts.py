"""Layout tests for the state chart loaders and their embedded objects.

Upstream has no loaders for these types; every body follows the kernel read order.
"""
import unittest

from tests import support
from tests.support import NAMED_ATTRIBUTED_REFS, ObjectBytes, typed


def load(type_name, body, database_version=None):
    return support.load(type_name, body, database_version=database_version)


def request_part(body, short_name_path):
    body.unicode('V').flag(short_name_path).ascii('P')
    return body


def action_body(short_name_path=False, with_strings=False):
    return request_part(support.diag_com_ref_body(ObjectBytes(), with_strings), short_name_path)


def action(short_name_path=False, with_strings=False):
    return typed('MCD_DB_STATE_TRANSITION_ACTION', {
        'diag_com_primitive': support.diag_com_ref(with_strings),
        'value': 'V',
        'request_parameter_is_short_name_path': short_name_path,
        'request_parameter_short_name': None if short_name_path else 'P',
        'request_parameter_short_name_path': 'P' if short_name_path else None})


def precondition_body(diag_com=True, short_name_path=False, with_strings=False, old_layout=False):
    body = ObjectBytes()
    if not old_layout:
        body.flag(diag_com)
    if diag_com:
        support.diag_com_ref_body(body, with_strings)
    return request_part(body, short_name_path)


def precondition(diag_com=True, short_name_path=False, with_strings=False):
    result = action(short_name_path, with_strings)
    result['#OBJECT_TYPE'] = 'MCD_DB_PRECONDITION_DEFINITION'
    if not diag_com:
        result['diag_com_primitive'] = None
    result['table_parameter'] = None
    return result


def name_block_body(body, filled=False):
    """Name block in the read order of MCD_DB_ENV_DATA_DESC."""
    if filled:
        return (body.unicode('Desc').unicode('Long').ascii('Short').ascii('DescId')
                .ascii('LongId').ascii('UID'))
    return body.unicode(None).unicode(None).ascii(None).ascii(None).ascii(None).ascii(None)


def name_block(filled=False):
    if filled:
        return {'description': 'Desc', 'long_name': 'Long', 'short_name': 'Short',
                'description_id': 'DescId', 'long_name_id': 'LongId', 'unique_object_id': 'UID'}
    return {key: None for key in ('description', 'long_name', 'short_name', 'description_id',
                                  'long_name_id', 'unique_object_id')}


class EmbeddedStateChartTests(unittest.TestCase):
    def test_mcd_db_external_access_method_minimal(self):
        self.assertEqual(load('MCD_DB_EXTERNAL_ACCESS_METHOD',
                              ObjectBytes().ascii(None).unicode(None)),
                         typed('MCD_DB_EXTERNAL_ACCESS_METHOD',
                               {'unique_object_id': None, 'method': None}))

    def test_mcd_db_external_access_method_all_branches(self):
        self.assertEqual(load('MCD_DB_EXTERNAL_ACCESS_METHOD',
                              ObjectBytes().ascii('UID').unicode('Method')),
                         typed('MCD_DB_EXTERNAL_ACCESS_METHOD',
                               {'unique_object_id': 'UID', 'method': 'Method'}))

    def test_mcd_db_state_transition_action_minimal(self):
        body = support.diag_com_ref_body(ObjectBytes(), False)
        body.unicode(None).flag(False).ascii(None)
        result = load('MCD_DB_STATE_TRANSITION_ACTION', body)
        self.assertEqual(result, typed('MCD_DB_STATE_TRANSITION_ACTION', {
            'diag_com_primitive': support.diag_com_ref(False), 'value': None,
            'request_parameter_is_short_name_path': False,
            'request_parameter_short_name': None, 'request_parameter_short_name_path': None}))

    def test_mcd_db_state_transition_action_all_branches(self):
        result = load('MCD_DB_STATE_TRANSITION_ACTION', action_body(True, True))
        self.assertEqual(result['request_parameter_short_name_path'], 'P')
        self.assertIsNone(result['request_parameter_short_name'])
        self.assertEqual(result['diag_com_primitive'], support.diag_com_ref(True))
        self.assertEqual(result, action(True, True))

    def test_mcd_db_state_transition_action_short_name(self):
        self.assertEqual(load('MCD_DB_STATE_TRANSITION_ACTION', action_body()), action())

    def test_mcd_db_precondition_definition_minimal(self):
        body = ObjectBytes().flag(False).unicode(None).flag(False).ascii(None)
        self.assertEqual(load('MCD_DB_PRECONDITION_DEFINITION', body),
                         typed('MCD_DB_PRECONDITION_DEFINITION', {
                             'diag_com_primitive': None, 'value': None,
                             'request_parameter_is_short_name_path': False,
                             'request_parameter_short_name': None,
                             'request_parameter_short_name_path': None,
                             'table_parameter': None}))

    def test_mcd_db_precondition_definition_all_branches(self):
        self.assertEqual(load('MCD_DB_PRECONDITION_DEFINITION',
                              precondition_body(True, True, True)),
                         precondition(True, True, True))

    def test_mcd_db_precondition_definition_without_reference(self):
        self.assertEqual(load('MCD_DB_PRECONDITION_DEFINITION',
                              precondition_body(diag_com=False)),
                         precondition(diag_com=False))

    def test_mcd_db_precondition_definition_old_layout(self):
        old = load('MCD_DB_PRECONDITION_DEFINITION',
                   precondition_body(with_strings=True, old_layout=True), '0015')
        new = load('MCD_DB_PRECONDITION_DEFINITION',
                   precondition_body(with_strings=True), '0018')
        self.assertEqual(old, new)
        self.assertEqual(old, precondition(with_strings=True))

    def test_mcd_db_precondition_definition_version_boundary(self):
        self.assertEqual(load('MCD_DB_PRECONDITION_DEFINITION', precondition_body(), '0018'),
                         precondition())
        self.assertEqual(load('MCD_DB_PRECONDITION_DEFINITION',
                              precondition_body(old_layout=True), '0017'),
                         precondition())


class StateChartObjectTests(unittest.TestCase):
    def test_mcd_db_ecu_state_transition_minimal(self):
        body = name_block_body(ObjectBytes())
        support.attributed_ref_body(body)
        support.attributed_ref_body(body)
        body.flag(False)
        self.assertEqual(load('MCD_DB_ECU_STATE_TRANSITION', body),
                         typed('MCD_DB_ECU_STATE_TRANSITION', {
                             **name_block(), 'source_state': support.attributed_ref(),
                             'target_state': support.attributed_ref(),
                             'has_external_access_method': False,
                             'external_access_method': None}))

    def test_mcd_db_ecu_state_transition_all_branches(self):
        body = name_block_body(ObjectBytes(), True)
        support.attributed_ref_body(body, ('A1',))
        support.attributed_ref_body(body, ('A1',))
        body.flag(True).nested('MCD_DB_EXTERNAL_ACCESS_METHOD',
                               ObjectBytes().ascii('UID2').unicode('Method'))
        self.assertEqual(load('MCD_DB_ECU_STATE_TRANSITION', body),
                         typed('MCD_DB_ECU_STATE_TRANSITION', {
                             **name_block(True), 'source_state': support.attributed_ref(('A1',)),
                             'target_state': support.attributed_ref(('A1',)),
                             'has_external_access_method': True,
                             'external_access_method': typed('MCD_DB_EXTERNAL_ACCESS_METHOD', {
                                 'unique_object_id': 'UID2', 'method': 'Method'})}))

    def test_mcd_db_ecu_state_transition_flag_without_object(self):
        body = name_block_body(ObjectBytes())
        support.attributed_ref_body(body)
        support.attributed_ref_body(body)
        body.flag(True).absent()
        result = load('MCD_DB_ECU_STATE_TRANSITION', body)
        self.assertIs(result['has_external_access_method'], True)
        self.assertIsNone(result['external_access_method'])

    def test_mcd_db_ecu_state_minimal(self):
        body = support.named_attributed_refs_body(name_block_body(ObjectBytes()))
        self.assertEqual(load('MCD_DB_ECU_STATE', body),
                         typed('MCD_DB_ECU_STATE', {**name_block(), 'ecu_state_transitions': []}))

    def test_mcd_db_ecu_state_all_branches(self):
        body = support.named_attributed_refs_body(name_block_body(ObjectBytes(), True),
                                                  NAMED_ATTRIBUTED_REFS)
        self.assertEqual(load('MCD_DB_ECU_STATE', body),
                         typed('MCD_DB_ECU_STATE', {
                             **name_block(True),
                             'ecu_state_transitions':
                                 support.named_attributed_refs(NAMED_ATTRIBUTED_REFS)}))

    def test_mcd_db_ecu_state_chart_minimal(self):
        body = name_block_body(ObjectBytes()).ascii(None)
        support.named_attributed_refs_body(body)
        body.ascii(None)
        support.named_attributed_refs_body(body)
        self.assertEqual(load('MCD_DB_ECU_STATE_CHART', body),
                         typed('MCD_DB_ECU_STATE_CHART', {
                             **name_block(), 'semantic': None, 'ecu_states': [],
                             'start_state': None, 'ecu_state_transitions': []}))

    def test_mcd_db_ecu_state_chart_all_branches(self):
        body = name_block_body(ObjectBytes(), True).ascii('SESSION')
        support.named_attributed_refs_body(body, NAMED_ATTRIBUTED_REFS)
        body.ascii('S1')
        support.named_attributed_refs_body(body, NAMED_ATTRIBUTED_REFS)
        refs = support.named_attributed_refs(NAMED_ATTRIBUTED_REFS)
        self.assertEqual(load('MCD_DB_ECU_STATE_CHART', body),
                         typed('MCD_DB_ECU_STATE_CHART', {
                             **name_block(True), 'semantic': 'SESSION', 'ecu_states': refs,
                             'start_state': 'S1', 'ecu_state_transitions': refs}))


def table_ref_body(body, number):
    return body.ascii('ROW%d' % number).ascii('POOL').ascii('Row%d' % number)


def table_ref(number):
    return {'object_id': 'ROW%d' % number, 'pool_id': 'POOL', 'object_id2': 'Row%d' % number}


def map_body(body, entries):
    """One map of DB_STATE_CHART_DATA; entries is a list of (key, [element body or None])."""
    body.u16(len(entries))
    for key, elements in entries:
        body.ascii(key).u16(len(elements))
        for element in elements:
            if element is None:
                body.absent()
            else:
                body.nested(element[0], element[1])
    return body


ACTION = 'MCD_DB_STATE_TRANSITION_ACTION'
PRECONDITION = 'MCD_DB_PRECONDITION_DEFINITION'


class StateChartDataTests(unittest.TestCase):
    def test_db_state_chart_data_minimal(self):
        self.assertEqual(load('DB_STATE_CHART_DATA', ObjectBytes().u16(0).u16(0)),
                         typed('DB_STATE_CHART_DATA', {
                             'state_trans_trans_actions_map': [],
                             'state_precondition_defs_map': []}))

    def test_db_state_chart_data_all_branches(self):
        body = map_body(ObjectBytes(), [('T1', [(ACTION, action_body()), None])])
        map_body(body, [
            ('S1', [(PRECONDITION, precondition_body(diag_com=False)),
                    (PRECONDITION, precondition_body())]),
            ('S2', [(PRECONDITION, precondition_body(diag_com=False))])])
        body.raw(b'#>\x00C')
        table_ref_body(body, 1)
        table_ref_body(body, 2)
        body.raw(b'#>\x01')
        result = load('DB_STATE_CHART_DATA', body)
        self.assertEqual(result, typed('DB_STATE_CHART_DATA', {
            'state_trans_trans_actions_map': [{'map_key': 'T1', 'items': [action(), None]}],
            'state_precondition_defs_map': [
                {'map_key': 'S1', 'items': [
                    {**precondition(diag_com=False), 'table_parameter': table_ref(1)},
                    precondition()]},
                {'map_key': 'S2', 'items': [
                    {**precondition(diag_com=False), 'table_parameter': table_ref(2)}]}]}))

    def test_db_state_chart_data_missing_named_stream(self):
        body = map_body(ObjectBytes(), [])
        map_body(body, [('S1', [(PRECONDITION, precondition_body(diag_com=False))])])
        with self.assertRaisesRegex(RuntimeError, 'Named stream C missing'):
            load('DB_STATE_CHART_DATA', body)

    def test_db_state_chart_data_skips_unused_named_stream_c(self):
        # kernel: stream C is only read when a definition needs it, otherwise it is ignored
        body = map_body(ObjectBytes(), [])
        map_body(body, [('S1', [(PRECONDITION, precondition_body())])])
        body.raw(b'#>\x00C')
        table_ref_body(body, 1)
        body.raw(b'#>\x01')
        result = load('DB_STATE_CHART_DATA', body)
        self.assertEqual(result['state_precondition_defs_map'],
                         [{'map_key': 'S1', 'items': [precondition()]}])

    def test_db_state_chart_data_too_few_references(self):
        body = map_body(ObjectBytes(), [])
        map_body(body, [('S1', [(PRECONDITION, precondition_body(diag_com=False)),
                                (PRECONDITION, precondition_body(diag_com=False))])])
        body.raw(b'#>\x00C')
        table_ref_body(body, 1)
        body.raw(b'#>\x01')
        with self.assertRaisesRegex(RuntimeError, 'Cannot read'):
            load('DB_STATE_CHART_DATA', body)

    def test_db_state_chart_data_too_many_references(self):
        body = map_body(ObjectBytes(), [])
        map_body(body, [('S1', [(PRECONDITION, precondition_body(diag_com=False))])])
        body.raw(b'#>\x00C')
        table_ref_body(body, 1)
        table_ref_body(body, 2)
        body.raw(b'#>\x01')
        with self.assertRaisesRegex(RuntimeError, 'Unexpected marker'):
            load('DB_STATE_CHART_DATA', body)

    def test_db_state_chart_data_old_layout(self):
        body = map_body(ObjectBytes(), [])
        map_body(body, [('S1', [(PRECONDITION, precondition_body(old_layout=True))])])
        result = load('DB_STATE_CHART_DATA', body, '0015')
        self.assertEqual(result['state_precondition_defs_map'],
                         [{'map_key': 'S1', 'items': [precondition()]}])
