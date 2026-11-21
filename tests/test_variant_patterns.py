import contextlib
import io
import os
import tempfile
import unittest

import dumpECUVariantPatterns
from common_utils.layer_chain import load_layer_data
from tests.script_support import FakeObjectLoader, layer

UDS_TYPE = 'ISO_15765_3_on_ISO_15765_2'
FILE_IDENT = 'DiagnServi_ReadDataByIdentASAMODXFileIdent'
FILE_VERSION = 'DiagnServi_ReadDataByIdentASAMODXFileVersi'
PART_NUMBER = 'DS_ReadDataByIdentSubsySpeciDiagnSpeciPartNumbe'


def matching_parameter(service, value, name='P', path=None):
    """Matching parameter in the form of the MCD_DB_MATCHING_PARAMETER loader."""
    return {'diag_com_primitive_reference': {'pool_id': None, 'object_id': service},
            'response_parameter_name': None if path else name,
            'response_parameter_short_name_path': path,
            'response_parameter_is_short_name_path': path is not None,
            'expected_value_string': value}


def pattern_project(ecu_variants):
    """In-memory project: base variant BV.bv below PR.pr, ecu_variants = {name: [pattern, ...]}."""
    references = [{'name': name, 'reference': {'pool_id': name + '.ev', 'object_id': name}}
                  for name in ecu_variants]
    objects = {
        ('BV.bv', '#RtGen_DB_LAYER_DATA'): layer(name='BV', parent_layers=['PR.pr']),
        ('BV.bv', '#RtGen_DB_PROJECT_DATA'): {'ecu_variant_references': references,
                                              'base_variant_reference': {'object_id': 'BV'}},
        ('PR.pr', '#RtGen_DB_LAYER_DATA'): layer(name='PR', protocol_type=UDS_TYPE)}
    for name, patterns in ecu_variants.items():
        objects[(name + '.ev', name)] = {
            'long_name': 'Long ' + name, 'short_name': name, 'description': 'Description of ' + name,
            'variant_patterns': [{'matching_parameters': parameters} for parameters in patterns]}
    return FakeObjectLoader(objects)


# Captured from the output of the unmodified script
EXPECTED_EV_A_FILE = (
    "'EV_A' {\n  name: 'Long EV_A'\n  description: 'Description of EV_A'\n  matching_patterns (2) {\n"
    "    [0] {\n      odx_file_identifier: 'EV_A'\n      odx_file_version: '001'\n"
    "      subsystem_part_number: None\n"
    "      matching_parameters (2) {\n"
    "        [0] {\n          service: 'DiagnServi_ReadDataByIdentASAMODXFileIdent'\n"
    "          response_parameter: 'P'\n          expected_value: 'EV_A'\n        }\n"
    "        [1] {\n          service: 'DiagnServi_ReadDataByIdentASAMODXFileVersi'\n"
    "          response_parameter: 'P'\n          expected_value: '001'\n        }\n"
    "      }\n    }\n"
    "    [1] {\n      odx_file_identifier: None\n      odx_file_version: None\n"
    "      subsystem_part_number: '1K0907'\n"
    "      matching_parameters (1) {\n"
    "        [0] {\n          service: 'DS_ReadDataByIdentSubsySpeciDiagnSpeciPartNumbe'\n"
    "          response_parameter: 'P'\n          expected_value: '1K0907'\n        }\n"
    "      }\n    }\n  }\n}\n\n")


class VwVariantPatternTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = os.path.join(holder.name, 'project')
        self.out = os.path.join(holder.name, 'out')
        os.makedirs(self.tmp)
        open(os.path.join(self.tmp, 'BV.bv.db'), 'w').close()

    def run_dump(self, loader):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            dumpECUVariantPatterns.dump_patterns_for_base_variant(loader, self.tmp, 'BV.bv.db', self.out)
        return buffer.getvalue()

    def test_vw_pattern_output_is_unchanged(self):
        loader = pattern_project({'EV_A': [
            [matching_parameter(FILE_IDENT, 'EV_A'), matching_parameter(FILE_VERSION, '001')],
            [matching_parameter(PART_NUMBER, '1K0907')]]})
        self.run_dump(loader)
        with open(os.path.join(self.out, 'BV', 'PAT_EV_A.c'), encoding='utf-8') as file:
            self.assertEqual(file.read(), EXPECTED_EV_A_FILE)

    def test_kwp_pattern_reports_not_for_uds(self):
        loader = pattern_project({'EV_A': [[matching_parameter('MB_Identification_Read', 'X')]]})
        output = self.run_dump(loader)
        self.assertIn('Not for UDS', output)
        self.assertFalse(os.path.exists(os.path.join(self.out, 'BV', 'PAT_EV_A.c')))

    def test_matching_parameters_list_every_parameter_in_order(self):
        pattern = dumpECUVariantPatterns.get_matching_pattern(
            [matching_parameter('S_A', 'X', name='P_1'), matching_parameter('S_B', 'Y', path='P.Q')])
        self.assertEqual(pattern['matching_parameters'], [
            {'service': 'S_A', 'response_parameter': 'P_1', 'expected_value': 'X'},
            {'service': 'S_B', 'response_parameter': 'P.Q', 'expected_value': 'Y'}])
        self.assertEqual(list(pattern), ['odx_file_identifier', 'odx_file_version',
                                         'subsystem_part_number', 'matching_parameters'])
        self.assertIsNone(pattern['odx_file_identifier'])
        self.assertIsNone(pattern['odx_file_version'])
        self.assertIsNone(pattern['subsystem_part_number'])

    def test_unknown_service_raises_no_error(self):
        self.run_dump(pattern_project({'EV_A': [[matching_parameter('S_A', 'X')]]}))
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'BV', 'PAT_EV_A.c')))

    def test_repeated_service_is_kept_and_last_value_fills_old_field(self):
        pattern = dumpECUVariantPatterns.get_matching_pattern(
            [matching_parameter(FILE_IDENT, 'EV_A'), matching_parameter(FILE_IDENT, 'EV_B')])
        self.assertEqual(len(pattern['matching_parameters']), 2)
        self.assertEqual(pattern['odx_file_identifier'], 'EV_B')

    def test_kwp_pattern_skips_only_this_variant(self):
        loader = pattern_project({'EV_A': [[matching_parameter('MB_Identification_Read', 'X')]],
                                  'EV_B': [[matching_parameter(FILE_IDENT, 'EV_B')]]})
        output = self.run_dump(loader)
        self.assertIn('Not for UDS', output)
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'BV', 'PAT_EV_B.c')))
        self.assertFalse(os.path.exists(os.path.join(self.out, 'BV', 'PAT_EV_A.c')))


if __name__ == '__main__':
    unittest.main()
