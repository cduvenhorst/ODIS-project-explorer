import contextlib
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

import dumpFreezeFrames
from common_utils.layer_chain import load_layer_data
from tests.script_support import FakeObjectLoader, layer

UDS_TYPE = 'ISO_15765_3_on_ISO_15765_2'


def fake_parse_dop(object_loader, layer_data_objects, project_folder_path, dop):
    if dop['#OBJECT_TYPE'] == 'MCD_DB_PARAMETER_STRUCTURE':
        return {'type': 'STRUCTURE', 'name': dop['long_name']}
    return {'type': 'PARAMETER', 'name': dop['long_name']}


def freeze_frame_project(base_variant_layer, ecu_variant_layers=None):
    """In-memory project: base variant BV.bv below PR.pr plus one ECU variant per entry of ecu_variant_layers."""
    ecu_variant_layers = ecu_variant_layers or {}
    references = [{'name': name, 'reference': {'pool_id': name + '.ev', 'object_id': name}}
                  for name in ecu_variant_layers]
    objects = {
        ('BV.bv', '#RtGen_DB_LAYER_DATA'): base_variant_layer,
        ('BV.bv', '#RtGen_DB_PROJECT_DATA'): {'ecu_variant_references': references,
                                              'base_variant_reference': {'object_id': 'BV'}},
        ('PR.pr', '#RtGen_DB_LAYER_DATA'): layer(name='PR', protocol_type=UDS_TYPE)}
    for name, ecu_variant_layer in ecu_variant_layers.items():
        objects[(name + '.ev', name)] = {'location_references': [
            {'reference': {'access_key': {'pool_id': 'LD_' + name}}}]}
        objects[(name + '.ev', 'LD_' + name)] = ecu_variant_layer
    # shared objects: switch key DOP, two case structures and the multiplexer
    objects[('BV.bv', 'SWITCH_A')] = {'#OBJECT_TYPE': 'MCD_DB_PARAMETER', 'long_name': 'SWITCH_A',
                                      'diag_coded_type': {'bit_length': 8}}
    objects[('BV.bv', 'S_A')] = {'#OBJECT_TYPE': 'MCD_DB_PARAMETER_STRUCTURE', 'long_name': 'S_A'}
    objects[('BV.bv', 'S_B')] = {'#OBJECT_TYPE': 'MCD_DB_PARAMETER_STRUCTURE', 'long_name': 'S_B'}
    objects[('BV.bv', 'MUX_A')] = mux()
    return FakeObjectLoader(objects)


def closed_limit(value):
    return {'limit_type': 'eLIMIT_CLOSED', 'limit': {'value': value}}


def mux_case(name, description, lower, upper, structure):
    return {'long_name': name, 'description': description,
            'lower_limit': closed_limit(lower), 'upper_limit': closed_limit(upper),
            'structure_dop_reference': {'pool_id': 'BV.bv', 'object_id': structure}}


def mux():
    return {'#OBJECT_TYPE': 'MCD_DB_PARAMETER_MULTIPLEXER', 'long_name': 'MUX_A', 'offset': 2,
            'switch_key': {'bit_position': 0, 'byte_position': 0,
                           'dop_base_reference': {'pool_id': 'BV.bv', 'object_id': 'SWITCH_A'}},
            'cases': [mux_case('CASE_A', 'First case', '1', '1', 'S_A'),
                      mux_case('CASE_B', 'Second case', '2', '3', 'S_B')]}


def mux_reference():
    return {'map_key': 'MUX_DTCExtenDataRecor', 'reference': {'pool_id': 'BV.bv', 'object_id': 'MUX_A'}}


# Captured from the output of the unmodified script
EXPECTED_BV_FILE = (
    "'CASE_A' {\n  description: 'First case'\n  lower_limit: 1\n  upper_limit: 1\n  data_offset: 2\n"
    "  obj {\n    type: 'STRUCTURE'\n    name: 'S_A'\n  }\n}\n\n"
    "'CASE_B' {\n  description: 'Second case'\n  lower_limit: 2\n  upper_limit: 3\n  data_offset: 2\n"
    "  obj {\n    type: 'STRUCTURE'\n    name: 'S_B'\n  }\n}\n\n")


class DumpCase(unittest.TestCase):
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
        with contextlib.redirect_stdout(buffer), \
                mock.patch.object(dumpFreezeFrames, 'parse_dop', fake_parse_dop):
            dumpFreezeFrames.dump_freezeframes_for_base_variant(loader, self.tmp, 'BV.bv.db', self.out)
        return buffer.getvalue()

    def read(self, name):
        with open(os.path.join(self.out, 'BV', name), encoding='utf-8') as file:
            return file.read()


class VwFreezeFrameTest(DumpCase):
    def test_vw_freeze_frame_mux_output_is_unchanged(self):
        loader = freeze_frame_project(layer(name='BV', parent_layers=['PR.pr'],
                                            dop_references=[mux_reference()]))
        self.run_dump(loader)
        self.assertEqual(self.read('FF_BV.c'), EXPECTED_BV_FILE)

    def test_vw_freeze_frame_without_mux_reports_no_special_freeze_frames(self):
        loader = freeze_frame_project(layer(name='BV', parent_layers=['PR.pr']))
        output = self.run_dump(loader)
        self.assertIn('Has no special Freeze Frames', output)
        self.assertFalse(os.path.exists(self.out))

    def test_vw_freeze_frame_mux_in_ecu_variant(self):
        loader = freeze_frame_project(layer(name='BV', parent_layers=['PR.pr']),
                                      {'EV': layer(name='EV', dop_references=[mux_reference()])})
        self.run_dump(loader)
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'BV', 'FF_EV.c')))
        self.assertFalse(os.path.exists(os.path.join(self.out, 'BV', 'FF_BV.c')))


def env_data_parameter(short_name, dop_name):
    return {'#OBJECT_TYPE': 'MCD_DB_PARAMETER_SIMPLE', 'short_name': short_name,
            'long_name': 'Long ' + short_name, 'description': 'Description ' + short_name,
            'dop_base_reference': {'pool_id': None, 'object_id': dop_name}}


def env_data_dop(name, object_type='MCD_DB_PARAMETER_ENV_DATA'):
    return {'#OBJECT_TYPE': object_type, 'long_name': name, 'byte_length': 3,
            'parameters': [{'#OBJECT_TYPE': 'MCD_DB_PARAMETER', 'long_name': name + '_P1'},
                           {'#OBJECT_TYPE': 'MCD_DB_PARAMETER', 'long_name': name + '_P2'}]}


def env_data_desc_entry(short_name, all_value=None, entries=(), dtc_map=()):
    """Layer entry for an invented environment data description; entries are (short_name, dtc_values)."""
    return {'map_key': short_name, 'env_data_desc': {
        'short_name': short_name, 'long_name': 'Long ' + short_name, 'description': 'Description ' + short_name,
        'all_value_env_data_parameter': all_value,
        'env_data_information_map': [{'map_key': name, 'env_data_parameter': env_data_parameter(name, 'ED_DOP_' + name),
                                      'dtc_values': values} for name, values in entries],
        'env_data_parameter_map': [{'map_key': key, 'value': value} for key, value in dtc_map]}}


def env_data_dop_references(*names):
    return [{'map_key': 'ED_DOP_' + name, 'reference': {'pool_id': 'BV.bv', 'object_id': 'ED_DOP_' + name}}
            for name in names]


def add_env_data_dops(loader, *names):
    for name in names:
        loader.objects[('BV.bv', 'ED_DOP_' + name)] = env_data_dop(name)


EDD_A = env_data_desc_entry('EDD_A', all_value=env_data_parameter('AV', 'ED_DOP_AV'))


class EnvDataDescTest(DumpCase):
    def base_layer(self, **fields):
        return layer(name='BV', parent_layers=['PR.pr'],
                     dop_references=env_data_dop_references('AV', 'ED_1', 'ED_2') + fields.pop('dop_references', []),
                     **fields)

    def project(self, base_layer, ecu_variant_layers=None):
        loader = freeze_frame_project(base_layer, ecu_variant_layers)
        add_env_data_dops(loader, 'AV', 'ED_1', 'ED_2')
        return loader

    def test_env_data_desc_without_mux_writes_block(self):
        output = self.run_dump(self.project(self.base_layer(env_data_descs=[EDD_A])))
        text = self.read('FF_BV.c')
        for expected in ('EDD_A', 'all_value_env_data', 'AV_P1', 'AV_P2'):
            self.assertIn(expected, text)
        self.assertNotIn('Has no special Freeze Frames', output)

    def test_dtc_specific_env_data_lists_dtc_values_and_map(self):
        loader = self.project(self.base_layer())
        desc = env_data_desc_entry('EDD_B', entries=[('ED_1', [4660, 4661]), ('ED_2', [4662])],
                                   dtc_map=[(4660, 'ED_1'), (4662, 'ED_2')])['env_data_desc']
        with mock.patch.object(dumpFreezeFrames, 'parse_dop', fake_parse_dop):
            out = dumpFreezeFrames.get_env_data_desc_output(loader, [self.base_layer()], self.tmp, desc)
        self.assertEqual([e['short_name'] for e in out['env_data']], ['ED_1', 'ED_2'])
        self.assertEqual(out['env_data'][0]['dtc_values'], [4660, 4661])
        self.assertEqual(out['dtc_env_data'], [{'dtc': 4660, 'env_data': 'ED_1'}, {'dtc': 4662, 'env_data': 'ED_2'}])
        self.assertIsNone(out['all_value_env_data'])

    def test_ecu_variant_inherits_env_data_desc_of_base_variant(self):
        loader = self.project(self.base_layer(env_data_descs=[EDD_A]),
                              {'EV': layer(name='EV', parent_layers=['BV.bv'])})
        self.run_dump(loader)
        with open(os.path.join(self.out, 'BV', 'FF_EV.c'), encoding='utf-8') as file:
            self.assertIn('EDD_A', file.read())

    def test_not_inherited_env_data_desc_is_left_out(self):
        loader = self.project(self.base_layer(env_data_descs=[EDD_A]),
                              {'EV': layer(name='EV', parent_layers=['BV.bv'],
                                           not_inherited_dops=[{'map_key': 'BV.bv', 'strings': ['EDD_A']}])})
        output = self.run_dump(loader)
        self.assertIn('Has no special Freeze Frames', output)
        self.assertFalse(os.path.exists(os.path.join(self.out, 'BV', 'FF_EV.c')))

    def test_mux_cases_come_before_env_data_blocks(self):
        self.run_dump(self.project(self.base_layer(dop_references=[mux_reference()])))
        without = self.read('FF_BV.c')
        load_layer_data.cache_clear()
        shutil.rmtree(self.out)
        self.run_dump(self.project(self.base_layer(dop_references=[mux_reference()], env_data_descs=[EDD_A])))
        text = self.read('FF_BV.c')
        self.assertLess(text.index('CASE_B'), text.index('EDD_A'))
        self.assertTrue(text.startswith(without))

    def test_env_data_dop_of_wrong_type_raises(self):
        loader = self.project(self.base_layer(env_data_descs=[EDD_A]))
        loader.objects[('BV.bv', 'ED_DOP_AV')] = env_data_dop('AV', 'MCD_DB_PARAMETER_STRUCTURE')
        with self.assertRaisesRegex(RuntimeError, 'must be MCD_DB_PARAMETER_ENV_DATA, not MCD_DB_PARAMETER_STRUCTURE'):
            self.run_dump(loader)


if __name__ == '__main__':
    unittest.main()
