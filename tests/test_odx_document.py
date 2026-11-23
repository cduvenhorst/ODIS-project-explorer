"""Tests for the ODX document: skeleton, section order, objects without a place and the written file."""
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from odx_export.document import build_document, build_layer_document, write_document
from odx_export.elements import XSI_TYPE
from tests import test_odx_communication as communication
from tests import test_odx_layers as layer_tests
from tests import test_odx_variants as variants
from tests import test_odx_data_objects as data_objects
from tests import test_odx_state_charts as state_charts
from tests import test_odx_structures as structures
from tests import test_odx_tables as tables
from tests import test_odx_trouble_codes as trouble_codes
from tests.odx_support import context, xml

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
        # DISPLAY-RADIX DEC of an A_UINT32 survives indenting and writing.
        physical_type = parsed.find('.//DATA-OBJECT-PROP/PHYSICAL-TYPE')
        self.assertEqual(physical_type.get('DISPLAY-RADIX'), 'DEC')

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


BV_POOL = '0.0.0@B.bv'
SD_POOL = '0.0.0@S.sd'
PR_POOL = '0.0.0@P.pr'
FG_POOL = '0.0.0@G.fg'
EV_POOL = '0.0.0@E.ev'
LAYER = 'DB_LAYER_DATA'
FOREIGN_LAYERS = {
    SD_POOL: [{'key': '#RtGen_DB_LAYER_DATA', 'layer_name': 'S', 'layer_id': 'ESD_S',
               'location_type': 'eMULTIPLE_ECU_JOB', 'parent_layers': []}],
    PR_POOL: [{'key': '#RtGen_DB_LAYER_DATA', 'layer_name': 'P', 'layer_id': 'PROT_P',
               'location_type': 'ePROTOCOL', 'parent_layers': []}],
}


def layer(name, layer_id, location, **fields):
    result = {'layer_name': name, 'layer_id': layer_id, 'location_type': location, 'parent_layers': [],
              'special_data_group_references': []}
    result.update(fields)
    return result


def project(container='CONTAINER_X'):
    return {'#RtGen_DB_PROJECT_DATA': ('DB_PROJECT_DATA', {'container_short_name': container})}


def layer_context(objects, pool_id):
    """Context of a layer pool with the pool layers in the order of its layer objects."""
    pool_layers = [obj['layer_name'] for type_name, obj in objects.values() if type_name == LAYER]
    return context(objects, pool_id=pool_id, pool_layers=pool_layers)


def layer_lookup(ctx, extra=None):
    """Stand-in for ProjectPools.layers: the layers of the context's pool, of FOREIGN_LAYERS and of extra."""
    own = [{'key': key, 'layer_name': obj['layer_name'], 'layer_id': obj['layer_id'],
            'location_type': obj['location_type'], 'parent_layers': obj['parent_layers']}
           for key, obj in ctx.objects.items() if ctx.types[key] == LAYER]
    known = dict(FOREIGN_LAYERS, **(extra or {}))
    known[ctx.pool_id] = own
    return lambda pool_id: known.get(pool_id, [])


def base_variant_objects():
    """Pool B: base variant B with variants V1 and V2, each variant with a request Q1 of its own."""
    v1_pattern = variants.pattern(variants.matching_parameter('Identify', '0815', name='Part'))
    objects = project('CONTAINER_B')
    objects.update({
        '#RtGen_DB_LAYER_DATA': (LAYER, layer('B', 'BV_B', 'eECU_BASE_VARIANT',
                                              base_variant_reference=reference('B', BV_POOL),
                                              parent_layers=[SD_POOL])),
        'LD_V1': (LAYER, layer('V1', 'EV_V1_ID', 'eECU_VARIANT', ecu_variant_reference=reference('EV_V1', BV_POOL),
                               parent_layers=[BV_POOL], com_param_spec_pool_id='0.0.0@SPEC.cp')),
        'LD_V2': (LAYER, layer('V2', 'EV_V2_ID', 'eECU_VARIANT', ecu_variant_reference=reference('EV_V2', BV_POOL),
                               parent_layers=[BV_POOL])),
        'B': ('MCD_DB_ECU_BASE_VARIANT', variants.names(
            'B', 'OID-B', long_name='Base', long_name_id='TI-B', description='Base text',
            ecu_variant_patterns=[{'map_key': 'EV_V1', 'ecu_variant_patterns': [v1_pattern]}])),
        'EV_V1': ('MCD_DB_ECU_VARIANT', variants.names('V1', 'OID-V1', variant_patterns=[v1_pattern])),
        'EV_V2': ('MCD_DB_ECU_VARIANT', variants.names('V2', 'OID-V2', variant_patterns=[])),
        'REQ_V1_Q1': ('MCD_DB_REQUEST', communication.request('Q1')),
        'REQ_V2_Q1': ('MCD_DB_REQUEST', communication.request('Q1')),
    })
    return objects


def parent_ref(element):
    ref, = element.findall('PARENT-REFS/PARENT-REF')
    return ref.get('ID-REF'), ref.get('DOCREF'), ref.get('DOCTYPE'), ref.get(XSI_TYPE)


class LayerDocumentTests(unittest.TestCase):
    def test_base_variant_document_with_two_variants(self):
        ctx = layer_context(base_variant_objects(), BV_POOL)
        root = build_layer_document(ctx, layer_lookup(ctx))
        self.assertEqual(root.attrib, {'MODEL-VERSION': '2.2.0'})
        container = root.find('DIAG-LAYER-CONTAINER')
        self.assertEqual(container.attrib, {'ID': 'CONTAINER_B'})
        self.assertEqual(tags(container), ['SHORT-NAME', 'BASE-VARIANTS', 'ECU-VARIANTS'])
        self.assertEqual(container.findtext('SHORT-NAME'), 'CONTAINER_B')
        base, = container.find('BASE-VARIANTS')
        self.assertEqual(base.attrib, {'ID': 'BV_B', 'OID': 'OID-B'})
        self.assertEqual(tags(base), ['SHORT-NAME', 'LONG-NAME', 'DESC', 'PARENT-REFS'])
        self.assertEqual(xml(base.find('LONG-NAME')), '<LONG-NAME TI="TI-B">Base</LONG-NAME>')
        self.assertEqual(base.findtext('DESC'), 'Base text')
        self.assertEqual(parent_ref(base), ('ESD_S', 'S', 'LAYER', 'ECU-SHARED-DATA-REF'))
        first, second = container.find('ECU-VARIANTS')
        self.assertEqual(first.attrib, {'ID': 'EV_V1_ID', 'OID': 'OID-V1'})
        self.assertEqual(first.findtext('SHORT-NAME'), 'V1')
        # A variant layer writes no COMPARAM-SPEC-REF; only a protocol has one.
        self.assertEqual(tags(first), ['SHORT-NAME', 'REQUESTS', 'ECU-VARIANT-PATTERNS', 'PARENT-REFS'])
        self.assertEqual(first.findtext('ECU-VARIANT-PATTERNS/ECU-VARIANT-PATTERN/MATCHING-PARAMETERS/'
                                        'MATCHING-PARAMETER/EXPECTED-VALUE'), '0815')
        self.assertEqual(second.attrib, {'ID': 'EV_V2_ID', 'OID': 'OID-V2'})
        self.assertEqual(tags(second), ['SHORT-NAME', 'REQUESTS', 'PARENT-REFS'])
        for variant in (first, second):
            self.assertEqual(parent_ref(variant), ('BV_B', 'B', 'LAYER', 'BASE-VARIANT-REF'))
        self.assertEqual(ctx.report['base_variant_pattern_mismatch'], 0)
        self.assertEqual(ctx.unused(), {})

    def test_same_id_part_in_two_variants_written_in_each(self):
        ctx = layer_context(base_variant_objects(), BV_POOL)
        container = build_layer_document(ctx, layer_lookup(ctx)).find('DIAG-LAYER-CONTAINER')
        for variant in container.find('ECU-VARIANTS'):
            requests = variant.findall('REQUESTS/REQUEST')
            self.assertEqual([request.get('ID') for request in requests], ['Q1'])
        self.assertEqual(sum(ctx.report.values()), 0, ctx.report)

    def test_base_variant_patterns_and_shared_data_parents_are_checked(self):
        objects = base_variant_objects()
        objects['B'][1]['ecu_variant_patterns'].append({'map_key': 'EV_V2', 'ecu_variant_patterns': [
            variants.pattern(variants.matching_parameter('Identify', '4711', name='Part'))]})
        objects['LD_V2'][1]['shared_data_parent_layers'] = ['0.0.0@T.sd']
        ctx = layer_context(objects, BV_POOL)
        build_layer_document(ctx, layer_lookup(ctx))
        self.assertEqual(ctx.report['base_variant_pattern_mismatch'], 1)
        self.assertEqual(ctx.report['shared_data_parent_not_in_parents'], 1)

    def test_protocol_document_with_comparams_and_spec_ref(self):
        objects = project('CONTAINER_P')
        objects['#RtGen_DB_LAYER_DATA'] = (LAYER, layer(
            'P', 'PROT_P', 'ePROTOCOL', layer_com_params=[layer_tests.simple('CP_Baud', 500000)],
            com_param_spec_pool_id='0.0.0@SPEC.cp', protocol_stack_short_name='STACK', protocol_type='UDS'))
        ctx = layer_context(objects, PR_POOL)
        container = build_layer_document(ctx, layer_lookup(ctx)).find('DIAG-LAYER-CONTAINER')
        self.assertEqual(tags(container), ['SHORT-NAME', 'PROTOCOLS'])
        protocol, = container.find('PROTOCOLS')
        self.assertEqual(protocol.attrib, {'ID': 'PROT_P'})
        self.assertEqual(tags(protocol), ['SHORT-NAME', 'COMPARAM-REFS', 'COMPARAM-SPEC-REF', 'PROT-STACK-SNREF'])
        self.assertEqual(protocol.findtext('SHORT-NAME'), 'P')
        self.assertEqual(protocol.find('COMPARAM-REFS/COMPARAM-REF').get('ID-REF'), 'SUB_A.CP_Baud')
        self.assertEqual(xml(protocol.find('COMPARAM-SPEC-REF')),
                         '<COMPARAM-SPEC-REF ID-REF="SPEC" DOCREF="SPEC" DOCTYPE="COMPARAM-SPEC" />')
        self.assertEqual(xml(protocol.find('PROT-STACK-SNREF')), '<PROT-STACK-SNREF SHORT-NAME="STACK" />')
        self.assertEqual(ctx.unused(), {})

    def test_functional_group_document(self):
        objects = project('CONTAINER_G')
        objects['#RtGen_DB_LAYER_DATA'] = (LAYER, layer(
            'G', 'FG_G', 'eFUNCTIONAL_GROUP', functional_group_reference=reference('DLC_G', FG_POOL),
            parent_layers=[PR_POOL]))
        objects['DLC_G'] = ('MCD_DB_FUNCTIONAL_GROUP', variants.names('G', 'OID-G', long_name='Group',
                                                                      group_member_references=[
            {'name': 'B', 'reference': reference('B', BV_POOL)},
            {'name': 'X', 'reference': reference('X', '0.0.0@X.bv')}]))
        ctx = layer_context(objects, FG_POOL)
        members = {BV_POOL: [{'key': '#RtGen_DB_LAYER_DATA', 'layer_name': 'B', 'layer_id': 'BV_B',
                              'location_type': 'eECU_BASE_VARIANT', 'parent_layers': [FG_POOL]},
                             {'key': 'LD_V1', 'layer_name': 'V1', 'layer_id': 'EV_V1_ID',
                              'location_type': 'eECU_VARIANT', 'parent_layers': [BV_POOL]}]}
        container = build_layer_document(ctx, layer_lookup(ctx, members)).find('DIAG-LAYER-CONTAINER')
        self.assertEqual(tags(container), ['SHORT-NAME', 'FUNCTIONAL-GROUPS'])
        group, = container.find('FUNCTIONAL-GROUPS')
        self.assertEqual(group.attrib, {'ID': 'FG_G', 'OID': 'OID-G'})
        self.assertEqual(tags(group), ['SHORT-NAME', 'LONG-NAME', 'PARENT-REFS'])
        self.assertEqual(parent_ref(group), ('PROT_P', 'P', 'LAYER', 'PROTOCOL-REF'))
        # Pool X is unknown, so its member has no parent reference to the group.
        self.assertEqual(ctx.report['group_member_without_parent_ref'], 1)
        self.assertEqual(ctx.unused(), {})

    def test_ev_document(self):
        objects = project('CONTAINER_E')
        objects['#RtGen_DB_LAYER_DATA'] = (LAYER, layer(
            'E', 'EV_E_ID', 'eECU_VARIANT', ecu_variant_reference=reference('EV_E', None), parent_layers=[SD_POOL]))
        objects['EV_E'] = ('MCD_DB_ECU_VARIANT', variants.names('E', 'OID-E', variant_patterns=None))
        objects['REQ_E_Q1'] = ('MCD_DB_REQUEST', communication.request('Q1'))
        ctx = layer_context(objects, EV_POOL)
        container = build_layer_document(ctx, layer_lookup(ctx)).find('DIAG-LAYER-CONTAINER')
        self.assertEqual(tags(container), ['SHORT-NAME', 'ECU-VARIANTS'])
        variant, = container.find('ECU-VARIANTS')
        self.assertEqual(variant.attrib, {'ID': 'EV_E_ID', 'OID': 'OID-E'})
        self.assertEqual(tags(variant), ['SHORT-NAME', 'REQUESTS', 'PARENT-REFS'])
        self.assertEqual(parent_ref(variant), ('ESD_S', 'S', 'LAYER', 'ECU-SHARED-DATA-REF'))
        self.assertEqual(sum(ctx.report.values()), 0, ctx.report)
        self.assertEqual(ctx.unused(), {})

    def test_layer_objects_count_as_used(self):
        objects = base_variant_objects()
        objects['EV_V9'] = ('MCD_DB_ECU_VARIANT', variants.names('V9'))
        ctx = layer_context(objects, BV_POOL)
        build_layer_document(ctx, layer_lookup(ctx))
        for key in ('#RtGen_DB_PROJECT_DATA', '#RtGen_DB_LAYER_DATA', 'LD_V1', 'LD_V2', 'B', 'EV_V1', 'EV_V2'):
            self.assertIn(key, ctx.used)
        # A variant object that no layer names stays unused.
        self.assertEqual(ctx.unused(), {'MCD_DB_ECU_VARIANT': 1})

    def test_layer_without_its_object_or_with_other_short_name_is_reported(self):
        objects = base_variant_objects()
        del objects['EV_V2']
        objects['EV_V1'][1]['short_name'] = 'Other'
        ctx = layer_context(objects, BV_POOL)
        container = build_layer_document(ctx, layer_lookup(ctx)).find('DIAG-LAYER-CONTAINER')
        first, second = container.find('ECU-VARIANTS')
        # SHORT-NAME is the layer name, which every DOCREF to the layer names.
        self.assertEqual(first.findtext('SHORT-NAME'), 'V1')
        self.assertEqual(second.attrib, {'ID': 'EV_V2_ID'})
        self.assertEqual(second.findtext('SHORT-NAME'), 'V2')
        self.assertEqual(ctx.report['layer_short_name_differs'], 1)
        self.assertEqual(ctx.report['layer_object_missing'], 1)

    def test_layer_of_other_location_type_is_not_written(self):
        objects = base_variant_objects()
        objects['LD_J'] = (LAYER, layer('J', 'MEJ_J', 'eMULTIPLE_ECU_JOB'))
        ctx = layer_context(objects, BV_POOL)
        container = build_layer_document(ctx, layer_lookup(ctx)).find('DIAG-LAYER-CONTAINER')
        self.assertEqual(len(container.find('ECU-VARIANTS')), 2)
        self.assertEqual(ctx.without_place, ['LD_J'])
        self.assertEqual(container[-1].tag, ET.Comment)
        self.assertEqual(container[-1].text,
                         ' Not written: DB_LAYER_DATA LD_J: not referenced by any object, no place in ODX ')

    def test_objects_without_place_are_commented_in_their_layer(self):
        objects = base_variant_objects()
        objects['TBP_V2_T9.R1'] = ('MCD_DB_TABLE_PARAMETER', tables.row('R1', 'K1'))
        ctx = layer_context(objects, BV_POOL)
        container = build_layer_document(ctx, layer_lookup(ctx)).find('DIAG-LAYER-CONTAINER')
        first, second = container.find('ECU-VARIANTS')
        self.assertFalse([child for child in first if child.tag is ET.Comment])
        self.assertIs(second[-1].tag, ET.Comment)
        self.assertEqual(second[-1].text, ' Not written: MCD_DB_TABLE_PARAMETER TBP_V2_T9.R1: '
                                          'not referenced by any object, no place in ODX ')

    def test_shared_data_document_unchanged(self):
        expected = xml(build_document(context(full_objects())))
        ctx = context(full_objects())
        self.assertEqual(xml(build_layer_document(ctx, lambda pool_id: [])), expected)
        self.assertEqual(sum(ctx.unused().values()), 0, ctx.unused())

    def test_written_layer_document_parses(self):
        ctx = layer_context(base_variant_objects(), BV_POOL)
        root = build_layer_document(ctx, layer_lookup(ctx))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'B.odx')
            write_document(root, path, BV_POOL)
            parsed = ET.parse(path)
        self.assertEqual(parsed.getroot().find('DIAG-LAYER-CONTAINER/BASE-VARIANTS/BASE-VARIANT').get('ID'), 'BV_B')


if __name__ == '__main__':
    unittest.main()
