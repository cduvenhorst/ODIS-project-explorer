import contextlib
import io
import os
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


class VwFreezeFrameTest(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
