"""Porsche output of the table scripts: single-DID services with row references, on invented data."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import dumpAdaptations
import dumpCoding
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


def write_service(name, table_name, row_short_name):
    """Single-DID 0x2E service whose request references one row of the table."""
    return service_objects(name, [sid_parameter(0x2E),
                                  table_key_parameter(ref(table_name), row_short_name=row_short_name),
                                  table_struct_parameter(ref(table_name))], [[]])


def second_table_objects():
    """Decimal table 'TABLE Q' with one row Row_2 that has the same key 258 as Row_2 of 'TABLE P'."""
    return {(POOL, 'DOP key Q'): key_dop_decimal(),
            (POOL, 'ROW Q Row_2'): table_row('Row_2', 'Other Row_2', '258', ref('STRUCT Q Row_2')),
            (POOL, 'STRUCT Q Row_2'): structure('Struct_Q_Row_2', [value_parameter('Field_1', 0, ref('DOP u8'))],
                                                byte_length=1),
            (POOL, 'TABLE Q'): table(ref('DOP key Q'), [('258', ref('ROW Q Row_2'))])}


class PorscheAdaptationScriptTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.out = os.path.join(holder.name, 'out')
        self.objects = base_variant_objects()
        self.objects.update(porsche_table_objects())
        self.objects.update(second_table_objects())
        self.objects.update(write_service('S_W', 'TABLE P', 'Row_2'))
        self.objects.update(write_service('S_X', 'TABLE Q', 'Row_2'))

    def dump_adaptations(self, service_names):
        ev_layer = layer(name='EV', parent_layers=['BV.bv'],
                         diag_com_primitive_references=[diag_com(name) for name in service_names])
        console = io.StringIO()
        with mock.patch.object(dumpAdaptations, 'get_ecu_variant_layer_data', return_value=ev_layer), \
                contextlib.redirect_stdout(console):
            dumpAdaptations.dump_adaptations_for_base_variant(FakeObjectLoader(self.objects), 'project',
                                                              'BV.bv.db', self.out)
        return console.getvalue()

    def adaptation_path(self):
        return os.path.join(self.out, 'BV', 'ADP_EV.c')

    def read_adaptations(self):
        with open(self.adaptation_path(), encoding='utf-8') as file:
            return file.read()

    def test_porsche_adaptation_file_has_entry_with_services(self):
        self.dump_adaptations(['S_W'])
        text = self.read_adaptations()
        self.assertIn('0x0102: ', text)
        self.assertIn("  services (1) {\n    [0]: 'S_W'\n  }\n}\n", text)

    def test_duplicate_adaptation_did_gives_two_entries(self):
        self.dump_adaptations(['S_W', 'S_X'])
        titles = [line for line in self.read_adaptations().splitlines() if line.startswith('0x0102: ')]
        self.assertEqual(len(titles), 2)

    def test_variant_without_adaptation_services_has_no_file(self):
        console = self.dump_adaptations([])
        self.assertIn('Has no Adaptations', console)
        self.assertFalse(os.path.exists(self.adaptation_path()))


class PorscheCodingScriptTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.out = os.path.join(holder.name, 'out')
        self.service_names = ['CodingValue_Write', 'S_M']
        self.objects = base_variant_objects(
            ecu_variants=('EV1', 'EV2'),
            base_variant_layer=layer(name='BV', parent_layers=['PR.pr'],
                                     diag_com_primitive_references=[diag_com(n) for n in self.service_names]))
        self.objects.update(porsche_table_objects())
        # the coding service addresses Row_1, the measurement service Row_2 of the same table
        self.objects.update(write_service('CodingValue_Write', 'TABLE P', 'Row_1'))
        self.objects.update(read_service('S_M', 'Row_2'))

    def dump_coding(self, desired_ecu_variant=None):
        layers = {name + '-reference': layer(name=name, parent_layers=['BV.bv'],
                                             diag_com_primitive_references=[diag_com(n) for n in self.service_names])
                  for name in ('EV1', 'EV2')}
        console = io.StringIO()
        with mock.patch.object(dumpCoding, 'get_ecu_variant_layer_data',
                               side_effect=lambda loader, path, reference: layers[reference]), \
                contextlib.redirect_stdout(console):
            dumpCoding.dump_codings_for_base_variant(FakeObjectLoader(self.objects), 'project', 'BV.bv.db',
                                                     self.out, desired_ecu_variant=desired_ecu_variant)
        return console.getvalue()

    def path(self, name):
        return os.path.join(self.out, 'BV', name)

    def read(self, name):
        with open(self.path(name), encoding='utf-8') as file:
            return file.read()

    @staticmethod
    def titles(text):
        return [line for line in text.splitlines() if line.startswith('0x')]

    def test_without_variant_only_coding_service_entry(self):
        self.dump_coding()
        text = self.read('VRC_EV1.c')
        self.assertEqual(self.titles(text), ['0x0101: ID_Row Row_1 - Row Row_1 {'])
        self.assertIn("  services (1) {\n    [0]: 'CodingValue_Write'\n  }\n  flat_layout {\n", text)
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, 'BV'))),
                         ['VRC_BV.c', 'VRC_BV.json', 'VRC_EV1.c', 'VRC_EV1.json', 'VRC_EV2.c', 'VRC_EV2.json'])

    def test_with_variant_adds_related_rows_and_only_that_variant(self):
        console = self.dump_coding('EV1')
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, 'BV'))), ['VRC_EV1.c', 'VRC_EV1.json'])
        self.assertEqual([title.split(':')[0] for title in self.titles(self.read('VRC_EV1.c'))],
                         ['0x0101', '0x0102'])
        with open(self.path('VRC_EV1.json'), encoding='utf-8') as file:
            data = json.load(file)
        self.assertEqual([(e['did'], e['services']) for e in data],
                         [(0x0101, ['CodingValue_Write']), (0x0102, ['S_M'])])
        self.assertEqual(console, 'ECU-VARIANT EV1\n')

    def test_base_variant_name_can_be_given(self):
        self.dump_coding('BV')
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, 'BV'))), ['VRC_BV.c', 'VRC_BV.json'])
        self.assertEqual(len(self.titles(self.read('VRC_BV.c'))), 2)

    def test_unknown_variant_lists_variants_and_raises(self):
        console = io.StringIO()
        with contextlib.redirect_stdout(console), \
                self.assertRaisesRegex(RuntimeError, '^Could not find ECU-VARIANT NOPE$'):
            dumpCoding.dump_codings_for_base_variant(FakeObjectLoader(self.objects), 'project', 'BV.bv.db',
                                                     self.out, desired_ecu_variant='NOPE')
        self.assertEqual(console.getvalue(), 'Available ECU-VARIANTs:\n  BV\n  EV1\n  EV2\n\n')
        self.assertFalse(os.path.exists(self.out))

    def test_json_file_has_flat_layout(self):
        self.dump_coding()
        with open(self.path('VRC_EV1.json'), encoding='utf-8') as file:
            data = json.load(file)
        self.assertEqual(list(data[0]), ['did', 'long_name', 'long_name_id', 'services', 'flat_layout'])
        self.assertEqual(data[0]['flat_layout']['fields'][0]['byte_position'], 0)
        self.assertEqual(data[0]['flat_layout']['byte_length'], 1)
