"""Porsche output of the table scripts: single-DID services with row references, on invented data."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import dumpMWB
from common_utils.layer_chain import load_layer_data
from tests.script_support import FakeObjectLoader, layer
from tests.table_fixtures import (POOL, base_variant_objects, diag_com, key_dop_decimal, ref, service_objects,
                                  sid_parameter, structure, table, table_key_parameter, table_row,
                                  table_struct_parameter, uint_dop, value_parameter)
from tests.test_vw_table_scripts import VW_MWB, vw_objects


def porsche_table_objects():
    """Decimal table 'TABLE P' with the rows Row_1 (key 257) and Row_2 (key 258)."""
    objects = {(POOL, 'DOP u8'): uint_dop(8), (POOL, 'DOP key P'): key_dop_decimal()}
    key_map = []
    for map_key, short_name in (('257', 'Row_1'), ('258', 'Row_2')):
        objects[(POOL, 'ROW ' + short_name)] = table_row(short_name, 'Row ' + short_name, map_key,
                                                          ref('STRUCT ' + short_name))
        objects[(POOL, 'STRUCT ' + short_name)] = structure('Struct_' + short_name,
                                                             [value_parameter('Field_1', 0, ref('DOP u8'))],
                                                             byte_length=1)
        key_map.append((map_key, ref('ROW ' + short_name)))
    objects[(POOL, 'TABLE P')] = table(ref('DOP key P'), key_map)
    return objects


def read_service(name, row_short_name):
    """Single-DID 0x22 service whose positive response references one row of the table."""
    return service_objects(name, [sid_parameter(0x22)],
                           [[sid_parameter(0x62), table_key_parameter(ref('TABLE P'), row_short_name=row_short_name),
                             table_struct_parameter(ref('TABLE P'))]])


class PorscheMwbScriptTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.out = os.path.join(holder.name, 'out')
        self.objects = base_variant_objects()
        self.objects.update(porsche_table_objects())
        self.objects.update(read_service('S_A', 'Row_1'))
        self.objects.update(read_service('S_C', 'Row_1'))
        self.objects.update(read_service('S_B', 'Row_2'))

    def dump_mwb(self, objects, service_names):
        ev_layer = layer(name='EV', parent_layers=['BV.bv'],
                         diag_com_primitive_references=[diag_com(name) for name in service_names])
        console = io.StringIO()
        with mock.patch.object(dumpMWB, 'get_ecu_variant_layer_data', return_value=ev_layer), \
                contextlib.redirect_stdout(console):
            dumpMWB.dump_mwbs_for_base_variant(FakeObjectLoader(objects), 'project', 'BV.bv.db', self.out)
        return console.getvalue()

    def mwb_path(self):
        return os.path.join(self.out, 'BV', 'MWB_EV.json')

    def read_mwb(self):
        with open(self.mwb_path(), encoding='utf-8') as file:
            return json.load(file)

    def test_porsche_mwb_file_lists_one_entry_per_row_with_services(self):
        self.dump_mwb(self.objects, ['S_A', 'S_C', 'S_B'])
        data = self.read_mwb()
        self.assertEqual([(e['did'], e['services']) for e in data],
                         [(0x0101, ['S_A', 'S_C']), (0x0102, ['S_B'])])

    def test_variant_without_measurement_services_has_no_file(self):
        console = self.dump_mwb(self.objects, [])
        self.assertIn('Has no MWBs', console)
        self.assertFalse(os.path.exists(self.mwb_path()))

    def test_vw_service_wins_and_output_has_no_services(self):
        objects = vw_objects()
        objects.update(porsche_table_objects())
        objects.update(read_service('S_A', 'Row_1'))
        self.dump_mwb(objects, [VW_MWB, 'S_A'])
        data = self.read_mwb()
        # the VW table lists its DIDs in key-scale order, not in key-map order
        self.assertEqual([e['did'] for e in data], [0x0102, 0x0101])
        self.assertTrue(all('services' not in e for e in data))
