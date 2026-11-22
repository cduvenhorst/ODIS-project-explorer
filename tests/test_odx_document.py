"""Tests for the ODX document: skeleton, section order, objects without a place and the written file."""
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from odx_export.document import build_document, write_document
from tests import test_odx_communication as communication
from tests import test_odx_data_objects as data_objects
from tests import test_odx_state_charts as state_charts
from tests import test_odx_structures as structures
from tests import test_odx_tables as tables
from tests import test_odx_trouble_codes as trouble_codes
from tests.odx_support import context

OWN = '0.0.0@L.sd'
DDDS_ORDER = ['DTC-DOPS', 'ENV-DATA-DESCS', 'DATA-OBJECT-PROPS', 'STRUCTURES', 'STATIC-FIELDS',
              'DYNAMIC-LENGTH-FIELDS', 'END-OF-PDU-FIELDS', 'MUXS', 'ENV-DATAS', 'UNIT-SPEC', 'TABLES']
ESD_ORDER = ['SHORT-NAME', 'FUNCT-CLASSS', 'DIAG-DATA-DICTIONARY-SPEC', 'DIAG-COMMS', 'REQUESTS',
             'POS-RESPONSES', 'NEG-RESPONSES', 'GLOBAL-NEG-RESPONSES', 'STATE-CHARTS', 'SDGS']


def reference(object_id, pool_id=OWN):
    return {'object_id': object_id, 'pool_id': pool_id}


def layer_data(**fields):
    result = {'layer_id': 'ESD_L', 'layer_name': 'L', 'special_data_group_references': []}
    result.update(fields)
    return result


def head(layer=None):
    return {'#RtGen_DB_PROJECT_DATA': ('DB_PROJECT_DATA', {'container_short_name': 'CONTAINER'}),
            '#RtGen_DB_LAYER_DATA': ('DB_LAYER_DATA', layer if layer is not None else layer_data())}


def sdg_group(content):
    return {'items': [{'content': content, 'semantic_information': '', 'text_id': ''}],
            'semantic_information': '', 'caption_reference': None, 'caption': None}


def full_objects():
    """One object of every collection the document writes."""
    all_value = structures.parameter('ALL', dop_base_reference=reference('DOP_L_V1'))
    env_data_desc = {'is_parameter_short_name_path_available': False, 'parameter_short_name_path': None,
                     'parameter_name': 'DTC_NUMBER', 'byte_length': 0,
                     'env_data_desc': {'description': None, 'long_name': None, 'short_name': 'ENV',
                                       'description_id': None, 'long_name_id': None, 'unique_object_id': None,
                                       'env_data_parameter_map': [], 'all_value_env_data_parameter': all_value,
                                       'env_data_information_map': []}}
    dop = {'short_name': 'Speed', 'compu_method': data_objects.compu_method('eIDENTICAL'),
           'diag_coded_type': data_objects.coded_type(), 'physical_type': data_objects.physical_type(radix=16),
           'unit_reference': reference('UNIT_L_U1'), 'internal_constraint_reference': None,
           'physical_constraint_reference': None}
    mux = {'offset': 0, 'switch_key': None, 'default_case': None,
           'cases': [dict(structures.case_base('ONE', reference('DOP_L_S1')),
                          lower_limit=structures.limit(1), upper_limit=structures.limit(1))]}
    objects = head(layer_data(special_data_groups=[sdg_group('layer')]))
    objects.update({
        'FC_L_F1': ('MCD_DB_FUNCTIONAL_CLASS', communication.functional_class('F1')),
        'DOP_L_X1': ('DB_DOP_DTC', trouble_codes.dtc_dop('DOP1', reference('DTC_L_A'))),
        'DTC_L_A': ('MCD_DB_DIAG_TROUBLE_CODE', trouble_codes.dtc('A')),
        'DOP_L_E1': ('MCD_DB_PARAMETER_ENV_DATA_DESC', env_data_desc),
        'DOP_L_D1': ('DB_DOP_SIMPLE_BASE', dop),
        'DOP_L_S1': ('MCD_DB_PARAMETER_STRUCTURE', structures.structure(4)),
        'DOP_L_F1': ('MCD_DB_PARAMETER_STATIC_FIELD', structures.field(
            reference('DOP_L_S1'), fixed_number_of_items=3, item_byte_size=2)),
        'DOP_L_F2': ('MCD_DB_PARAMETER_DYNAMIC_LENGTH_FIELD', structures.field(
            reference('DOP_L_S1'), offset=1, dop_base_reference=reference('DOP_L_D1'),
            simple_byte_position=0, simple_bit_position=0)),
        'DOP_L_F3': ('MCD_DB_PARAMETER_END_OF_PDU_FIELD', structures.field(
            reference('DOP_L_S1'), max_number_of_items=0xFFFFFFFF, min_number_of_items=0)),
        'DOP_L_M1': ('MCD_DB_PARAMETER_MULTIPLEXER', mux),
        'DOP_L_V1': ('MCD_DB_PARAMETER_ENV_DATA', {'byte_length': 0, 'parameters': None}),
        'UNIT_L_U1': ('MCD_DB_UNIT', data_objects.unit('km', 'U-1')),
        'TB_L_T1': ('MCD_DB_TABLE', tables.table('T1', [reference('TBP_L_T1.R1')])),
        'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', tables.row('R1', 'K1')),
        'DC_L_S1': ('MCD_DB_SERVICE', communication.service('S1', request_reference=reference('REQ_L_Q1'))),
        'REQ_L_Q1': ('MCD_DB_REQUEST', communication.request('Q1')),
        'RSP_L_P1': ('MCD_DB_RESPONSE', communication.response('P1', 'ePOSITIVE_RESPONSE')),
        'RSP_L_N1': ('MCD_DB_RESPONSE', communication.response('N1', 'eLOCAL_NEG_RESPONSE')),
        'RSP_L_G1': ('MCD_DB_RESPONSE', communication.response('G1', 'eGLOBAL_NEG_RESPONSE')),
        'SC_L_C1': ('MCD_DB_ECU_STATE_CHART', state_charts.chart(['ST_L_C1.Default'], [])),
        'ST_L_C1.Default': ('MCD_DB_ECU_STATE', state_charts.state('Default')),
    })
    return objects


def esd_of(root):
    return root.find('DIAG-LAYER-CONTAINER/ECU-SHARED-DATAS/ECU-SHARED-DATA')


def tags(element):
    return [child.tag for child in element]


class DocumentTests(unittest.TestCase):
    def test_document_skeleton_and_order(self):
        ctx = context(full_objects())
        root = build_document(ctx)
        self.assertEqual(root.tag, 'ODX')
        self.assertEqual(root.get('MODEL-VERSION'), '2.2.0')
        self.assertEqual(tags(root), ['DIAG-LAYER-CONTAINER'])
        container = root.find('DIAG-LAYER-CONTAINER')
        self.assertEqual(container.attrib, {'ID': 'CONTAINER'})
        self.assertEqual(tags(container), ['SHORT-NAME', 'ECU-SHARED-DATAS'])
        self.assertEqual(container.findtext('SHORT-NAME'), 'CONTAINER')
        esd = esd_of(root)
        self.assertEqual(esd.attrib, {'ID': 'ESD_L'})
        self.assertEqual(esd.findtext('SHORT-NAME'), 'L')
        self.assertEqual(tags(esd), ESD_ORDER)
        self.assertEqual(tags(esd.find('DIAG-DATA-DICTIONARY-SPEC')), DDDS_ORDER)
        # The all-value parameter of the description names the environment data.
        self.assertEqual(esd.findtext('DIAG-DATA-DICTIONARY-SPEC/ENV-DATAS/ENV-DATA/SHORT-NAME'), 'ALL')
        self.assertEqual(sum(ctx.unused().values()), 0, ctx.unused())

    def test_dop_keys_follow_the_layer_list_and_are_split_by_type(self):
        objects = full_objects()
        objects['DOP_L_D2'] = ('DB_DOP_SIMPLE_BASE', dict(objects['DOP_L_D1'][1], short_name='Second'))
        layer = objects['#RtGen_DB_LAYER_DATA'][1]
        layer['dop_references'] = [{'map_key': 'D2', 'reference': reference('DOP_L_D2')}]
        esd = esd_of(build_document(context(objects)))
        props = esd.findall('DIAG-DATA-DICTIONARY-SPEC/DATA-OBJECT-PROPS/DATA-OBJECT-PROP')
        self.assertEqual([prop.get('ID') for prop in props], ['D2', 'D1'])

    def test_empty_collections_are_not_written(self):
        ctx = context(head())
        esd = esd_of(build_document(ctx))
        self.assertEqual(tags(esd), ['SHORT-NAME'])

    def test_layer_sdgs_come_last(self):
        objects = head(layer_data(special_data_groups=[sdg_group('layer')]))
        objects['FC_L_F1'] = ('MCD_DB_FUNCTIONAL_CLASS', communication.functional_class('F1'))
        esd = esd_of(build_document(context(objects)))
        self.assertEqual(tags(esd), ['SHORT-NAME', 'FUNCT-CLASSS', 'SDGS'])
        self.assertEqual(esd.findtext('SDGS/SDG/SD'), 'layer')

    def test_objects_without_place_are_commented_at_the_end(self):
        objects = head(layer_data(special_data_groups=[sdg_group('layer')]))
        objects['TBP_L_T9.R1'] = ('MCD_DB_TABLE_PARAMETER', tables.row('R1', 'K1'))
        objects['TBP_L_A--B'] = ('MCD_DB_TABLE_PARAMETER', tables.row('R2', 'K2'))
        objects['TBP_L_C---D'] = ('MCD_DB_TABLE_PARAMETER', tables.row('R3', 'K3'))
        ctx = context(objects)
        root = build_document(ctx)
        esd = esd_of(root)
        comments = [child for child in esd if child.tag is ET.Comment]
        self.assertIs(esd[-1], comments[-1])
        self.assertEqual(esd[-4].tag, 'SDGS')
        self.assertEqual([comment.text for comment in comments], [
            ' Not written: MCD_DB_TABLE_PARAMETER TBP_L_T9.R1: not referenced by any object, no place in ODX ',
            ' Not written: MCD_DB_TABLE_PARAMETER TBP_L_A- -B: not referenced by any object, no place in ODX ',
            ' Not written: MCD_DB_TABLE_PARAMETER TBP_L_C- - -D: not referenced by any object, no place in ODX '])
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'L.odx')
            write_document(root, path, OWN)
            parsed = ET.parse(path, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
        parsed_esd = esd_of(parsed.getroot())
        self.assertEqual(parsed_esd[-1].text, comments[-1].text)

    def test_written_file_has_declaration_comment_and_parses(self):
        objects = full_objects()
        objects['DOP_L_D1'][1]['physical_type'] = data_objects.physical_type(radix=10)
        root = build_document(context(objects))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'L.odx')
            write_document(root, path, OWN)
            with open(path, encoding='utf-8') as handle:
                text = handle.read()
            parsed = ET.parse(path, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
        lines = text.split('\n')
        self.assertEqual(lines[0], '<?xml version="1.0" encoding="UTF-8"?>')
        self.assertEqual(lines[1], '<!-- Reconstructed by ODIS-project-explorer from pool 0.0.0@L.sd: '
                                   'equivalent in content, not identical to the original ODX document -->')
        self.assertTrue(lines[2].startswith('<ODX '), lines[2])
        self.assertIn('xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"', lines[2])
        self.assertEqual(lines[3], '  <DIAG-LAYER-CONTAINER ID="CONTAINER">')
        self.assertEqual(parsed.getroot().get('MODEL-VERSION'), '2.2.0')
        # The DISPLAY-RADIX comment survives indenting and writing.
        physical_type = parsed.find('.//DATA-OBJECT-PROP/PHYSICAL-TYPE')
        self.assertIs(physical_type[0].tag, ET.Comment)
        self.assertEqual(physical_type[0].text, ' DISPLAY-RADIX not present: pool value DEC ')

    def test_xsi_namespace_is_declared_once_when_used(self):
        objects = full_objects()
        objects['DOP_L_S1'] = ('MCD_DB_PARAMETER_STRUCTURE', structures.structure(4, [structures.parameter('A')]))
        root = build_document(context(objects))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'L.odx')
            write_document(root, path, OWN)
            with open(path, encoding='utf-8') as handle:
                text = handle.read()
            ET.parse(path)
        self.assertIn('xsi:type=', text)
        self.assertEqual(text.count('xmlns:xsi='), 1)

    def test_failed_write_leaves_no_file(self):
        root = ET.Element('ODX')
        root.append(ET.Element('BROKEN', {'A': object()}))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'L.odx')
            with self.assertRaises(TypeError):
                write_document(root, path, OWN)
            self.assertFalse(os.path.exists(path))


if __name__ == '__main__':
    unittest.main()
