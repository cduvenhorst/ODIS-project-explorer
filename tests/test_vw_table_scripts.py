"""Protection tests: the VW output of dumpCoding, dumpMWB, dumpAdaptations and parseMWB must not change.

The expected texts below are the output of the scripts before the table rewrite, on invented data that shows
the VW peculiarities:
- the key DOP lists the DIDs in another order than the table's key map (the output follows the key DOP),
- the table key parameter of the service has is_table_row_reference set, yet the whole table is read,
- the measurement table has a row 'Meas Value' for the key text 'Meas_Value' (underscore replacement),
- the adaptation table struct sits at byte 4, not at byte 3,
- every row is a structure with two fields, one of them a TEXTTABLE.
"""
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
import parseMWB
from common_utils.layer_chain import load_layer_data
from tests.script_support import FakeObjectLoader, layer
from tests.table_fixtures import (base_variant_objects, diag_com, key_dop_names, ref, service_objects,
                                  sid_parameter, structure, table, table_key_parameter, table_row,
                                  table_struct_parameter, texttable_dop, uint_dop, value_parameter)

VW_CODING = 'DiagnServi_WriteDataByIdentVariaCodinTextu'
VW_MWB = 'DiagnServi_ReadDataByIdentMeasuValue'
VW_ADAPTATION = 'DiagnServi_WriteDataByIdentCalibData'

STATES = [(0, 'Off'), (1, 'On'), (2, 'Error')]


def two_field_structure(name, field_bits=8, second_byte=1, second_bit=0):
    """Structure with a plain field and a TEXTTABLE field; the DOPs are stored as DOP u<n> and DOP state<n>."""
    return structure(name, [value_parameter('Field_1', 0, ref('DOP u{}'.format(field_bits))),
                            value_parameter('Field_2', second_byte, ref('DOP state{}'.format(field_bits)),
                                            bit_position=second_bit)],
                     byte_length=2 if field_bits == 8 else 1)


def table_objects(prefix, scales, rows, struct_objects):
    """Objects of one key DOP, one table with its rows and the row structures; rows is [(map key, short name)]."""
    objects = {('POOL', 'DOP key ' + prefix): key_dop_names(scales)}
    table_rows = []
    for map_key, short_name in rows:
        row_id = 'ROW {} {}'.format(prefix, short_name)
        struct_id = 'STRUCT {} {}'.format(prefix, short_name)
        objects[('POOL', row_id)] = table_row(short_name, map_key, map_key, ref(struct_id))
        objects[('POOL', struct_id)] = struct_objects[short_name]
        table_rows.append((map_key, ref(row_id)))
    objects[('POOL', 'TABLE ' + prefix)] = table(ref('DOP key ' + prefix), table_rows)
    return objects


def vw_objects():
    objects = base_variant_objects()
    objects[('POOL', 'DOP u8')] = uint_dop(8)
    objects[('POOL', 'DOP state8')] = texttable_dop(STATES, 8)
    objects[('POOL', 'DOP u4')] = uint_dop(4)
    objects[('POOL', 'DOP state4')] = texttable_dop(STATES, 4)
    plain = {'Row_A': two_field_structure('Struct_A'), 'Row_B': two_field_structure('Struct_B')}
    nibbles = {'Row_A': two_field_structure('Struct_A', 4, 0, 4), 'Row_B': two_field_structure('Struct_B', 4, 0, 4)}
    # the key DOPs list the DIDs in the opposite order of the key maps
    objects.update(table_objects('coding', [(0x0102, 'Coding_B'), (0x0101, 'Coding_A')],
                                 [('Coding_A', 'Row_A'), ('Coding_B', 'Row_B')], plain))
    objects.update(table_objects('adaptation', [(0x0302, 'Adapt_B'), (0x0301, 'Adapt_A')],
                                 [('Adapt_A', 'Row_A'), ('Adapt_B', 'Row_B')], plain))
    # the key text Meas_Value belongs to the row named 'Meas Value'
    objects.update(table_objects('mwb', [(0x0102, 'Meas_Plain'), (0x0101, 'Meas_Value')],
                                 [('Meas Value', 'Row_A'), ('Meas_Plain', 'Row_B')], nibbles))
    key = table_key_parameter(ref('TABLE coding'), row_short_name='Row_A')
    objects.update(service_objects(VW_CODING, [sid_parameter(0x2E), key,
                                               table_struct_parameter(ref('TABLE coding'))], []))
    key = table_key_parameter(ref('TABLE adaptation'), row_short_name='Row_A')
    objects.update(service_objects(VW_ADAPTATION, [sid_parameter(0x2E), key,
                                                   table_struct_parameter(ref('TABLE adaptation'),
                                                                          byte_position=4)], []))
    key = table_key_parameter(ref('TABLE mwb'), row_short_name='Row_A')
    objects.update(service_objects(VW_MWB, [], [[sid_parameter(0x62), key,
                                                 table_struct_parameter(ref('TABLE mwb'))]]))
    return objects


class VwTableScriptTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.out = os.path.join(holder.name, 'out')
        self.loader = FakeObjectLoader(vw_objects())
        self.ev_layer = layer(name='EV', parent_layers=['BV.bv'],
                              diag_com_primitive_references=[diag_com(VW_CODING), diag_com(VW_MWB),
                                                             diag_com(VW_ADAPTATION)])

    def run_dump(self, module, function):
        with mock.patch.object(module, 'get_ecu_variant_layer_data', return_value=self.ev_layer), \
                contextlib.redirect_stdout(io.StringIO()):
            function(self.loader, 'project', 'BV.bv.db', self.out)

    def dump_coding(self):
        self.run_dump(dumpCoding, dumpCoding.dump_codings_for_base_variant)

    def dump_mwb(self):
        self.run_dump(dumpMWB, dumpMWB.dump_mwbs_for_base_variant)

    def dump_adaptations(self):
        self.run_dump(dumpAdaptations, dumpAdaptations.dump_adaptations_for_base_variant)

    def read(self, name):
        with open(os.path.join(self.out, 'BV', name), encoding='utf-8') as file:
            return file.read()

    def parse_mwb(self, ecu_variant, did, response):
        translation = mock.Mock()
        translation.get_long_name_translation.side_effect = lambda long_name_id, long_name: long_name
        output = io.StringIO()
        with mock.patch.object(parseMWB, 'get_ecu_variant_layer_data', return_value=self.ev_layer), \
                mock.patch.object(parseMWB, 'long_name_translation', translation, create=True), \
                contextlib.redirect_stdout(output):
            parseMWB.app_parseMWB(self.loader, translation, 'project', 'BV.bv.db', ecu_variant, did, response)
        return output.getvalue()

    def test_vw_coding_file_is_unchanged(self):
        self.dump_coding()
        self.assertEqual(self.read('VRC_EV.c'), EXPECTED_VW_CODING_FILE)

    def test_vw_mwb_file_is_unchanged(self):
        self.dump_mwb()
        self.assertEqual(json.loads(self.read('MWB_EV.json')), EXPECTED_VW_MWB_LIST)

    def test_vw_mwb_row_with_default_is_dumped(self):
        self.loader.objects[('POOL', 'ROW mwb Row_A')]['default_value'] = {'data_type': 'eA_UINT32', 'value': 0}
        self.dump_mwb()
        self.assertEqual([e['did'] for e in json.loads(self.read('MWB_EV.json'))], [0x0102, 0x0101])

    def test_vw_adaptation_file_is_unchanged(self):
        self.dump_adaptations()
        self.assertEqual(self.read('ADP_EV.c'), EXPECTED_VW_ADAPTATION_FILE)

    def test_vw_parse_mwb_output_is_unchanged(self):
        self.assertEqual(self.parse_mwb('EV', '0101', '2A'), EXPECTED_VW_PARSE_MWB_OUTPUT)


EXPECTED_VW_CODING_FILE = (
    '0x0102: ID_Coding_B - Coding_B {\n'
    '  did: 258\n'
    "  long_name: 'Coding_B'\n"
    "  long_name_id: 'ID_Coding_B'\n"
    '  description: None\n'
    '  byte_position: 0\n'
    '  bit_position: 0\n'
    '  structure {\n'
    "    type: 'STRUCTURE'\n"
    "    long_name: 'Struct_B'\n"
    '    description: None\n'
    '    byte_size: 2\n'
    '    parameters (2) {\n'
    '      [0] {\n'
    "        type: 'PARAMETER'\n"
    "        long_name: 'Field_1'\n"
    "        long_name_id: 'ID_Field_1'\n"
    '        description: None\n'
    '        byte_position: 0\n'
    '        bit_position: 0\n'
    "        parameter_type: 'VALUE'\n"
    '        default_value: None\n'
    '        dop {\n'
    "          type: 'DOP'\n"
    "          coded_base_data_type: 'A_UINT32'\n"
    "          diag_coded_type: 'STANDARD-LENGTH-TYPE'\n"
    '          bit_length: 8\n'
    '          bit_mask: None\n'
    "          encoding: 'NONE'\n"
    "          endianness: 'big'\n"
    "          physical_base_data_type: 'A_UINT32'\n"
    '          display_radix: 10\n'
    '          precision: None\n'
    '          calculation_type: None\n'
    "          compu_category: 'IDENTICAL'\n"
    '        }\n'
    '      }\n'
    '      [1] {\n'
    "        type: 'PARAMETER'\n"
    "        long_name: 'Field_2'\n"
    "        long_name_id: 'ID_Field_2'\n"
    '        description: None\n'
    '        byte_position: 1\n'
    '        bit_position: 0\n'
    "        parameter_type: 'VALUE'\n"
    '        default_value: None\n'
    '        dop {\n'
    "          type: 'DOP'\n"
    "          coded_base_data_type: 'A_UINT32'\n"
    "          diag_coded_type: 'STANDARD-LENGTH-TYPE'\n"
    '          bit_length: 8\n'
    '          bit_mask: None\n'
    "          encoding: 'NONE'\n"
    "          endianness: 'big'\n"
    "          physical_base_data_type: 'A_UNICODE2STRING'\n"
    '          display_radix: None\n'
    '          precision: None\n'
    '          calculation_type: None\n'
    "          compu_category: 'TEXTTABLE'\n"
    '          compu_scales (3) {\n'
    '            [0] {\n'
    '              lower_limit: 0\n'
    '              upper_limit: 0\n'
    "              long_name: 'Off'\n"
    "              long_name_id: 'ID_Off'\n"
    '            }\n'
    '            [1] {\n'
    '              lower_limit: 1\n'
    '              upper_limit: 1\n'
    "              long_name: 'On'\n"
    "              long_name_id: 'ID_On'\n"
    '            }\n'
    '            [2] {\n'
    '              lower_limit: 2\n'
    '              upper_limit: 2\n'
    "              long_name: 'Error'\n"
    "              long_name_id: 'ID_Error'\n"
    '            }\n'
    '          }\n'
    '          compu_default_value: None\n'
    '        }\n'
    '      }\n'
    '    }\n'
    '  }\n'
    '}\n'
    '\n'
    '0x0101: ID_Coding_A - Coding_A {\n'
    '  did: 257\n'
    "  long_name: 'Coding_A'\n"
    "  long_name_id: 'ID_Coding_A'\n"
    '  description: None\n'
    '  byte_position: 0\n'
    '  bit_position: 0\n'
    '  structure {\n'
    "    type: 'STRUCTURE'\n"
    "    long_name: 'Struct_A'\n"
    '    description: None\n'
    '    byte_size: 2\n'
    '    parameters (2) {\n'
    '      [0] {\n'
    "        type: 'PARAMETER'\n"
    "        long_name: 'Field_1'\n"
    "        long_name_id: 'ID_Field_1'\n"
    '        description: None\n'
    '        byte_position: 0\n'
    '        bit_position: 0\n'
    "        parameter_type: 'VALUE'\n"
    '        default_value: None\n'
    '        dop {\n'
    "          type: 'DOP'\n"
    "          coded_base_data_type: 'A_UINT32'\n"
    "          diag_coded_type: 'STANDARD-LENGTH-TYPE'\n"
    '          bit_length: 8\n'
    '          bit_mask: None\n'
    "          encoding: 'NONE'\n"
    "          endianness: 'big'\n"
    "          physical_base_data_type: 'A_UINT32'\n"
    '          display_radix: 10\n'
    '          precision: None\n'
    '          calculation_type: None\n'
    "          compu_category: 'IDENTICAL'\n"
    '        }\n'
    '      }\n'
    '      [1] {\n'
    "        type: 'PARAMETER'\n"
    "        long_name: 'Field_2'\n"
    "        long_name_id: 'ID_Field_2'\n"
    '        description: None\n'
    '        byte_position: 1\n'
    '        bit_position: 0\n'
    "        parameter_type: 'VALUE'\n"
    '        default_value: None\n'
    '        dop {\n'
    "          type: 'DOP'\n"
    "          coded_base_data_type: 'A_UINT32'\n"
    "          diag_coded_type: 'STANDARD-LENGTH-TYPE'\n"
    '          bit_length: 8\n'
    '          bit_mask: None\n'
    "          encoding: 'NONE'\n"
    "          endianness: 'big'\n"
    "          physical_base_data_type: 'A_UNICODE2STRING'\n"
    '          display_radix: None\n'
    '          precision: None\n'
    '          calculation_type: None\n'
    "          compu_category: 'TEXTTABLE'\n"
    '          compu_scales (3) {\n'
    '            [0] {\n'
    '              lower_limit: 0\n'
    '              upper_limit: 0\n'
    "              long_name: 'Off'\n"
    "              long_name_id: 'ID_Off'\n"
    '            }\n'
    '            [1] {\n'
    '              lower_limit: 1\n'
    '              upper_limit: 1\n'
    "              long_name: 'On'\n"
    "              long_name_id: 'ID_On'\n"
    '            }\n'
    '            [2] {\n'
    '              lower_limit: 2\n'
    '              upper_limit: 2\n'
    "              long_name: 'Error'\n"
    "              long_name_id: 'ID_Error'\n"
    '            }\n'
    '          }\n'
    '          compu_default_value: None\n'
    '        }\n'
    '      }\n'
    '    }\n'
    '  }\n'
    '}\n'
    '\n')

EXPECTED_VW_MWB_LIST = [{'did': 258,
  'long_name': 'Meas_Plain',
  'long_name_id': 'ID_Meas_Plain',
  'description': None,
  'byte_position': 0,
  'bit_position': 0,
  'structure': {'type': 'STRUCTURE',
                'long_name': 'Struct_B',
                'description': None,
                'byte_size': 1,
                'parameters': [{'type': 'PARAMETER',
                                'long_name': 'Field_1',
                                'long_name_id': 'ID_Field_1',
                                'description': None,
                                'byte_position': 0,
                                'bit_position': 0,
                                'parameter_type': 'VALUE',
                                'default_value': None,
                                'dop': {'type': 'DOP',
                                        'coded_base_data_type': 'A_UINT32',
                                        'diag_coded_type': 'STANDARD-LENGTH-TYPE',
                                        'bit_length': 4,
                                        'bit_mask': None,
                                        'encoding': 'NONE',
                                        'endianness': 'big',
                                        'physical_base_data_type': 'A_UINT32',
                                        'display_radix': 10,
                                        'precision': None,
                                        'calculation_type': None,
                                        'compu_category': 'IDENTICAL'}},
                               {'type': 'PARAMETER',
                                'long_name': 'Field_2',
                                'long_name_id': 'ID_Field_2',
                                'description': None,
                                'byte_position': 0,
                                'bit_position': 4,
                                'parameter_type': 'VALUE',
                                'default_value': None,
                                'dop': {'type': 'DOP',
                                        'coded_base_data_type': 'A_UINT32',
                                        'diag_coded_type': 'STANDARD-LENGTH-TYPE',
                                        'bit_length': 4,
                                        'bit_mask': None,
                                        'encoding': 'NONE',
                                        'endianness': 'big',
                                        'physical_base_data_type': 'A_UNICODE2STRING',
                                        'display_radix': None,
                                        'precision': None,
                                        'calculation_type': None,
                                        'compu_category': 'TEXTTABLE',
                                        'compu_scales': [{'lower_limit': 0,
                                                          'upper_limit': 0,
                                                          'long_name': 'Off',
                                                          'long_name_id': 'ID_Off'},
                                                         {'lower_limit': 1,
                                                          'upper_limit': 1,
                                                          'long_name': 'On',
                                                          'long_name_id': 'ID_On'},
                                                         {'lower_limit': 2,
                                                          'upper_limit': 2,
                                                          'long_name': 'Error',
                                                          'long_name_id': 'ID_Error'}],
                                        'compu_default_value': None}}]}},
 {'did': 257,
  'long_name': 'Meas_Value',
  'long_name_id': 'ID_Meas_Value',
  'description': None,
  'byte_position': 0,
  'bit_position': 0,
  'structure': {'type': 'STRUCTURE',
                'long_name': 'Struct_A',
                'description': None,
                'byte_size': 1,
                'parameters': [{'type': 'PARAMETER',
                                'long_name': 'Field_1',
                                'long_name_id': 'ID_Field_1',
                                'description': None,
                                'byte_position': 0,
                                'bit_position': 0,
                                'parameter_type': 'VALUE',
                                'default_value': None,
                                'dop': {'type': 'DOP',
                                        'coded_base_data_type': 'A_UINT32',
                                        'diag_coded_type': 'STANDARD-LENGTH-TYPE',
                                        'bit_length': 4,
                                        'bit_mask': None,
                                        'encoding': 'NONE',
                                        'endianness': 'big',
                                        'physical_base_data_type': 'A_UINT32',
                                        'display_radix': 10,
                                        'precision': None,
                                        'calculation_type': None,
                                        'compu_category': 'IDENTICAL'}},
                               {'type': 'PARAMETER',
                                'long_name': 'Field_2',
                                'long_name_id': 'ID_Field_2',
                                'description': None,
                                'byte_position': 0,
                                'bit_position': 4,
                                'parameter_type': 'VALUE',
                                'default_value': None,
                                'dop': {'type': 'DOP',
                                        'coded_base_data_type': 'A_UINT32',
                                        'diag_coded_type': 'STANDARD-LENGTH-TYPE',
                                        'bit_length': 4,
                                        'bit_mask': None,
                                        'encoding': 'NONE',
                                        'endianness': 'big',
                                        'physical_base_data_type': 'A_UNICODE2STRING',
                                        'display_radix': None,
                                        'precision': None,
                                        'calculation_type': None,
                                        'compu_category': 'TEXTTABLE',
                                        'compu_scales': [{'lower_limit': 0,
                                                          'upper_limit': 0,
                                                          'long_name': 'Off',
                                                          'long_name_id': 'ID_Off'},
                                                         {'lower_limit': 1,
                                                          'upper_limit': 1,
                                                          'long_name': 'On',
                                                          'long_name_id': 'ID_On'},
                                                         {'lower_limit': 2,
                                                          'upper_limit': 2,
                                                          'long_name': 'Error',
                                                          'long_name_id': 'ID_Error'}],
                                        'compu_default_value': None}}]}}]

EXPECTED_VW_ADAPTATION_FILE = (
    '0x0302: ID_Adapt_B - Adapt_B {\n'
    '  did: 770\n'
    "  long_name: 'Adapt_B'\n"
    "  long_name_id: 'ID_Adapt_B'\n"
    '  description: None\n'
    '  byte_position: 0\n'
    '  bit_position: 0\n'
    '  structure {\n'
    "    type: 'STRUCTURE'\n"
    "    long_name: 'Struct_B'\n"
    '    description: None\n'
    '    byte_size: 2\n'
    '    parameters (2) {\n'
    '      [0] {\n'
    "        type: 'PARAMETER'\n"
    "        long_name: 'Field_1'\n"
    "        long_name_id: 'ID_Field_1'\n"
    '        description: None\n'
    '        byte_position: 0\n'
    '        bit_position: 0\n'
    "        parameter_type: 'VALUE'\n"
    '        default_value: None\n'
    '        dop {\n'
    "          type: 'DOP'\n"
    "          coded_base_data_type: 'A_UINT32'\n"
    "          diag_coded_type: 'STANDARD-LENGTH-TYPE'\n"
    '          bit_length: 8\n'
    '          bit_mask: None\n'
    "          encoding: 'NONE'\n"
    "          endianness: 'big'\n"
    "          physical_base_data_type: 'A_UINT32'\n"
    '          display_radix: 10\n'
    '          precision: None\n'
    '          calculation_type: None\n'
    "          compu_category: 'IDENTICAL'\n"
    '        }\n'
    '      }\n'
    '      [1] {\n'
    "        type: 'PARAMETER'\n"
    "        long_name: 'Field_2'\n"
    "        long_name_id: 'ID_Field_2'\n"
    '        description: None\n'
    '        byte_position: 1\n'
    '        bit_position: 0\n'
    "        parameter_type: 'VALUE'\n"
    '        default_value: None\n'
    '        dop {\n'
    "          type: 'DOP'\n"
    "          coded_base_data_type: 'A_UINT32'\n"
    "          diag_coded_type: 'STANDARD-LENGTH-TYPE'\n"
    '          bit_length: 8\n'
    '          bit_mask: None\n'
    "          encoding: 'NONE'\n"
    "          endianness: 'big'\n"
    "          physical_base_data_type: 'A_UNICODE2STRING'\n"
    '          display_radix: None\n'
    '          precision: None\n'
    '          calculation_type: None\n'
    "          compu_category: 'TEXTTABLE'\n"
    '          compu_scales (3) {\n'
    '            [0] {\n'
    '              lower_limit: 0\n'
    '              upper_limit: 0\n'
    "              long_name: 'Off'\n"
    "              long_name_id: 'ID_Off'\n"
    '            }\n'
    '            [1] {\n'
    '              lower_limit: 1\n'
    '              upper_limit: 1\n'
    "              long_name: 'On'\n"
    "              long_name_id: 'ID_On'\n"
    '            }\n'
    '            [2] {\n'
    '              lower_limit: 2\n'
    '              upper_limit: 2\n'
    "              long_name: 'Error'\n"
    "              long_name_id: 'ID_Error'\n"
    '            }\n'
    '          }\n'
    '          compu_default_value: None\n'
    '        }\n'
    '      }\n'
    '    }\n'
    '  }\n'
    '}\n'
    '\n'
    '0x0301: ID_Adapt_A - Adapt_A {\n'
    '  did: 769\n'
    "  long_name: 'Adapt_A'\n"
    "  long_name_id: 'ID_Adapt_A'\n"
    '  description: None\n'
    '  byte_position: 0\n'
    '  bit_position: 0\n'
    '  structure {\n'
    "    type: 'STRUCTURE'\n"
    "    long_name: 'Struct_A'\n"
    '    description: None\n'
    '    byte_size: 2\n'
    '    parameters (2) {\n'
    '      [0] {\n'
    "        type: 'PARAMETER'\n"
    "        long_name: 'Field_1'\n"
    "        long_name_id: 'ID_Field_1'\n"
    '        description: None\n'
    '        byte_position: 0\n'
    '        bit_position: 0\n'
    "        parameter_type: 'VALUE'\n"
    '        default_value: None\n'
    '        dop {\n'
    "          type: 'DOP'\n"
    "          coded_base_data_type: 'A_UINT32'\n"
    "          diag_coded_type: 'STANDARD-LENGTH-TYPE'\n"
    '          bit_length: 8\n'
    '          bit_mask: None\n'
    "          encoding: 'NONE'\n"
    "          endianness: 'big'\n"
    "          physical_base_data_type: 'A_UINT32'\n"
    '          display_radix: 10\n'
    '          precision: None\n'
    '          calculation_type: None\n'
    "          compu_category: 'IDENTICAL'\n"
    '        }\n'
    '      }\n'
    '      [1] {\n'
    "        type: 'PARAMETER'\n"
    "        long_name: 'Field_2'\n"
    "        long_name_id: 'ID_Field_2'\n"
    '        description: None\n'
    '        byte_position: 1\n'
    '        bit_position: 0\n'
    "        parameter_type: 'VALUE'\n"
    '        default_value: None\n'
    '        dop {\n'
    "          type: 'DOP'\n"
    "          coded_base_data_type: 'A_UINT32'\n"
    "          diag_coded_type: 'STANDARD-LENGTH-TYPE'\n"
    '          bit_length: 8\n'
    '          bit_mask: None\n'
    "          encoding: 'NONE'\n"
    "          endianness: 'big'\n"
    "          physical_base_data_type: 'A_UNICODE2STRING'\n"
    '          display_radix: None\n'
    '          precision: None\n'
    '          calculation_type: None\n'
    "          compu_category: 'TEXTTABLE'\n"
    '          compu_scales (3) {\n'
    '            [0] {\n'
    '              lower_limit: 0\n'
    '              upper_limit: 0\n'
    "              long_name: 'Off'\n"
    "              long_name_id: 'ID_Off'\n"
    '            }\n'
    '            [1] {\n'
    '              lower_limit: 1\n'
    '              upper_limit: 1\n'
    "              long_name: 'On'\n"
    "              long_name_id: 'ID_On'\n"
    '            }\n'
    '            [2] {\n'
    '              lower_limit: 2\n'
    '              upper_limit: 2\n'
    "              long_name: 'Error'\n"
    "              long_name_id: 'ID_Error'\n"
    '            }\n'
    '          }\n'
    '          compu_default_value: None\n'
    '        }\n'
    '      }\n'
    '    }\n'
    '  }\n'
    '}\n'
    '\n')

EXPECTED_VW_PARSE_MWB_OUTPUT = (
    '[S] Meas_Value - 2\n'
    '  [P] Field_1 - 10\n'
    '  [P] Field_2 - Error\n')
