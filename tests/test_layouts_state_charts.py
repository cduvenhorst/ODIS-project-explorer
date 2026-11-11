"""Layout tests for the state chart loaders and their embedded objects.

Upstream has no loaders for these types; every body follows the kernel read order.
"""
import unittest

from tests import support
from tests.support import ObjectBytes, typed


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
                   precondition_body(with_strings=True, old_layout=True), '0011')
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
