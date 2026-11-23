"""Tests for the per-layer view of a pool and the target layer of references."""
import unittest
import xml.etree.ElementTree as ET

from odx_export import data_objects, layers
from odx_export.elements import add_ref
from odx_export.special_data import sdgs
from tests.odx_support import context, xml

OWN = '0.0.0@L.sd'
LAYER_POOL = '0.0.0@B.bv'
REQUEST = 'MCD_DB_REQUEST'


def reference(object_id, pool_id):
    return {'object_id': object_id, 'pool_id': pool_id}


def ref_xml(ctx, object_id, pool_id):
    return xml(add_ref(ctx, ET.Element('X'), 'REQUEST-REF', reference(object_id, pool_id)))


def layer_pool(objects, **kwargs):
    """Context of pool B with the base variant B and the variants V1 and V2."""
    return context(objects, pool_id=LAYER_POOL, pool_layers=['B', 'V1', 'V2'], **kwargs)


class PoolLayerTests(unittest.TestCase):
    def test_single_layer_pool_behaves_as_before(self):
        ctx = context({'REQ_L_R1': (REQUEST, {})},
                      object_type=lambda pool_id, key: REQUEST)
        self.assertEqual(ctx.pool_layers, ['L'])
        self.assertEqual(ref_xml(ctx, 'REQ_L_R1', OWN), '<REQUEST-REF ID-REF="R1" />')
        self.assertEqual(ref_xml(ctx, 'REQ_N_R2', '5.4.0@N.sd'),
                         '<REQUEST-REF ID-REF="R2" DOCREF="N" DOCTYPE="LAYER" />')
        self.assertEqual(ref_xml(ctx, 'REQ_X_R3', OWN), '<REQUEST-REF ID-REF="REQ_X_R3" />')
        self.assertEqual(ctx.report['unresolvable_references'], 1)

    def test_naming_layer_prefers_longest_name(self):
        ctx = context({}, pool_id=LAYER_POOL, pool_layers=['B', 'V1', 'V1X', 'V1_X'])
        self.assertEqual(ctx.naming_layer('DC_V1X_S1'), 'V1X')
        self.assertEqual(ctx.naming_layer('DC_V1_X_S1'), 'V1_X')
        self.assertEqual(ctx.naming_layer('DC_V1_S1'), 'V1')
        self.assertIsNone(ctx.naming_layer('DC_W_S1'))

    def test_reference_to_other_layer_of_same_pool_has_docref(self):
        ctx = layer_pool({'REQ_V1_R1': (REQUEST, {}), 'REQ_V2_R1': (REQUEST, {})}).for_layer('V1')
        self.assertEqual(ref_xml(ctx, 'REQ_V2_R1', LAYER_POOL),
                         '<REQUEST-REF ID-REF="R1" DOCREF="V2" DOCTYPE="LAYER" />')
        self.assertEqual(ref_xml(ctx, 'REQ_V1_R1', LAYER_POOL), '<REQUEST-REF ID-REF="R1" />')
        self.assertEqual(ctx.report['unresolvable_references'], 0)

    def test_same_id_part_in_two_layers(self):
        pool = layer_pool({'REQ_V1_R1': (REQUEST, {}), 'REQ_V2_R1': (REQUEST, {})})
        view = pool.for_layer('V1')
        self.assertEqual(view.keys('REQ_'), ['REQ_V1_R1'])
        self.assertEqual(pool.for_layer('V2').keys('REQ_'), ['REQ_V2_R1'])
        self.assertEqual(view.own_id('REQ_V1_R1'), 'R1')
        self.assertEqual(view.own_id('REQ_V2_R1'), 'R1')

    def test_keys_do_not_include_layers_with_a_longer_name(self):
        pool = context({'REQ_V1_R1': (REQUEST, {}), 'REQ_V1_X_R2': (REQUEST, {})},
                       pool_id=LAYER_POOL, pool_layers=['B', 'V1', 'V1_X'])
        self.assertEqual(pool.for_layer('V1').keys('REQ_'), ['REQ_V1_R1'])
        self.assertEqual(pool.for_layer('V1_X').keys('REQ_'), ['REQ_V1_X_R2'])

    def test_reference_into_foreign_multi_layer_pool(self):
        asked = []

        def foreign_layers(pool_id):
            asked.append(pool_id)
            return ['B', 'V2']

        ctx = context({}, object_type=lambda pool_id, key: 'MCD_DB_SERVICE', foreign_layers=foreign_layers)
        element = add_ref(ctx, ET.Element('X'), 'DIAG-COMM-REF', reference('DC_V2_S1', LAYER_POOL))
        self.assertEqual(xml(element), '<DIAG-COMM-REF ID-REF="S1" DOCREF="V2" DOCTYPE="LAYER" />')
        self.assertEqual(asked, [LAYER_POOL])
        # A key that follows no layer of the foreign pool falls back to the pool's layer name.
        element = add_ref(ctx, ET.Element('X'), 'DIAG-COMM-REF', reference('DC_W_S2', LAYER_POOL))
        self.assertEqual(xml(element), '<DIAG-COMM-REF ID-REF="DC_W_S2" DOCREF="B" DOCTYPE="LAYER" />')

    def test_target_layer(self):
        ctx = layer_pool({}, foreign_layers=lambda pool_id: ['N']).for_layer('V1')
        self.assertEqual(ctx.target_layer(LAYER_POOL, 'REQ_V2_R1'), 'V2')
        self.assertEqual(ctx.target_layer(LAYER_POOL, 'REQ_W_R1'), 'B')
        self.assertEqual(ctx.target_layer('5.4.0@N.sd', 'DOP_N_D1'), 'N')
        self.assertEqual(context({}).target_layer('0.0.0@G.fg', 'DC_G_S1'), 'G')

    def test_layer_view_shares_usage_and_report(self):
        pool = layer_pool({'REQ_V1_R1': (REQUEST, {'short_name': 'R'}), 'REQ_V2_R1': (REQUEST, {})})
        view = pool.for_layer('V1')
        self.assertEqual(view.layer, 'V1')
        self.assertEqual(pool.layer, 'B')
        self.assertEqual(view.take('REQ_V1_R1'), {'short_name': 'R'})
        view.report['unresolvable_references'] += 2
        view.mark_without_place('REQ_V2_R1')
        self.assertIn('REQ_V1_R1', pool.used)
        self.assertEqual(pool.report['unresolvable_references'], 2)
        self.assertEqual(pool.without_place, ['REQ_V2_R1'])
        self.assertEqual(pool.unused(), {})
        view.written_caption_ids.add('7')
        self.assertEqual(pool.written_caption_ids, set())
        self.assertEqual(pool.for_layer('V2').written_caption_ids, set())

    def test_layer_view_shares_length_key_owners(self):
        pool = layer_pool({'REQ_V1_R1': (REQUEST, {'request_parameters': [{'unique_object_id': 'P-1'}]}),
                           'REQ_V2_R1': (REQUEST, {'request_parameters': [{'unique_object_id': 'P-2'}]})})
        self.assertEqual(data_objects.length_key_owners(pool.for_layer('V1')), {'P-1': 'R1', 'P-2': 'R1'})
        view = pool.for_layer('V1')
        view._length_key_owners = {'P-1': 'R1'}
        self.assertEqual(pool.for_layer('V2')._length_key_owners, {'P-1': 'R1'})

    def test_caption_without_naming_rule_counts_as_used_and_reported(self):
        names = {7: 'CAPTION_X_G'}
        caption = {'short_name': 'CAP', 'long_name': None, 'description': None,
                   'long_name_id': '', 'description_id': '', 'unique_object_id': ''}
        ctx = context({'CAPTION_X_G': ('MCD_DB_SPECIAL_DATA_GROUP_CAPTION', caption)},
                      pool_id='0.0.0@G.fg', key_name=names.get)
        parent = ET.Element('P')
        sdgs(ctx, parent, {'special_data_groups': [
            {'items': [], 'semantic_information': '', 'caption': caption,
             'caption_reference': {'object_key': 7, 'pool_id': '0.0.0@G.fg'}}]})
        self.assertEqual(xml(parent), '<P><SDGS><SDG><SDG-CAPTION-REF ID-REF="CAPTION_X_G" /></SDG></SDGS></P>')
        self.assertEqual(ctx.report['unresolvable_references'], 1)
        self.assertIn('CAPTION_X_G', ctx.used)
        self.assertEqual(ctx.unused(), {})

    def test_caption_of_variant_is_split_with_its_naming_layer(self):
        names = {7: 'CAPTION_V1_7'}
        caption = {'short_name': 'CAP', 'long_name': None, 'description': None,
                   'long_name_id': '', 'description_id': '', 'unique_object_id': ''}
        ctx = layer_pool({'CAPTION_V1_7': ('MCD_DB_SPECIAL_DATA_GROUP_CAPTION', caption)},
                         key_name=names.get).for_layer('V1')
        parent = ET.Element('P')
        sdgs(ctx, parent, {'special_data_groups': [
            {'items': [], 'semantic_information': '', 'caption': caption,
             'caption_reference': {'object_key': 7, 'pool_id': LAYER_POOL}}]})
        self.assertEqual(xml(parent), '<P><SDGS><SDG><SDG-CAPTION ID="7"><SHORT-NAME>CAP</SHORT-NAME>'
                                      '</SDG-CAPTION></SDG></SDGS></P>')
        self.assertEqual(ctx.report['unresolvable_references'], 0)


PARENTS = {
    '0.0.0@B.bv': {'layer_name': 'Base', 'layer_id': 'BASE_ID'},
    '0.0.0@L.sd': {'layer_name': 'Shared', 'layer_id': 'SHARED_ID'},
    '0.0.0@P.pr': {'layer_name': 'Proto', 'layer_id': 'PROTO_ID'},
    '0.0.0@F.fg': {'layer_name': 'Func', 'layer_id': 'FUNC_ID'},
    '0.0.0@E.ev': {'layer_name': 'Variant', 'layer_id': 'VARIANT_ID'},
}


def entries(**by_pool):
    return [{'map_key': pool, 'strings': names} for pool, names in by_pool.items()]


def parent_refs(layer_data, ctx=None, lookup=PARENTS.get):
    ctx = ctx or context({}, pool_id='0.0.0@C.ev')
    holder = ET.Element('X')
    result = layers.add_parent_refs(ctx, holder, layer_data, lookup)
    return ctx, holder, result


class ParentRefTests(unittest.TestCase):
    def test_parent_ref_types_by_pool_extension(self):
        _, _, result = parent_refs({'parent_layers': list(PARENTS)})
        types = [ref.get(layers.XSI_TYPE) for ref in result]
        self.assertEqual(types, ['BASE-VARIANT-REF', 'ECU-SHARED-DATA-REF', 'PROTOCOL-REF',
                                 'FUNCTIONAL-GROUP-REF', 'ECU-VARIANT-REF'])

    def test_parent_ref_id_is_parent_layer_id(self):
        ctx, holder, result = parent_refs({'parent_layers': ['0.0.0@B.bv']})
        self.assertEqual(result.tag, 'PARENT-REFS')
        self.assertEqual(list(holder), [result])
        ref, = result
        self.assertEqual((ref.tag, ref.get('ID-REF'), ref.get('DOCREF'), ref.get('DOCTYPE')),
                         ('PARENT-REF', 'BASE_ID', 'Base', 'LAYER'))
        self.assertEqual(ctx.report['unresolvable_references'], 0)

    def test_not_inherited_lists_in_schema_order_only_when_non_empty(self):
        data = {'parent_layers': ['0.0.0@B.bv', '0.0.0@L.sd'],
                'not_inherited_global_negative_responses': entries(**{'0.0.0@B.bv': ['G1']}),
                'not_inherited_tables': entries(**{'0.0.0@B.bv': ['T1', 'T2']}),
                'not_inherited_dops': entries(**{'0.0.0@B.bv': [], '0.0.0@L.sd': ['D1']}),
                'not_inherited_diag_com_primitives': entries(**{'0.0.0@L.sd': ['S1'], '0.0.0@B.bv': ['S2']})}
        _, _, result = parent_refs(data)
        base, shared = result
        self.assertEqual(xml(base),
                         '<PARENT-REF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                         'ID-REF="BASE_ID" DOCREF="Base" DOCTYPE="LAYER" xsi:type="BASE-VARIANT-REF">'
                         '<NOT-INHERITED-DIAG-COMMS><NOT-INHERITED-DIAG-COMM>'
                         '<DIAG-COMM-SNREF SHORT-NAME="S2" /></NOT-INHERITED-DIAG-COMM>'
                         '</NOT-INHERITED-DIAG-COMMS>'
                         '<NOT-INHERITED-TABLES><NOT-INHERITED-TABLE><TABLE-SNREF SHORT-NAME="T1" />'
                         '</NOT-INHERITED-TABLE><NOT-INHERITED-TABLE><TABLE-SNREF SHORT-NAME="T2" />'
                         '</NOT-INHERITED-TABLE></NOT-INHERITED-TABLES>'
                         '<NOT-INHERITED-GLOBAL-NEG-RESPONSES><NOT-INHERITED-GLOBAL-NEG-RESPONSE>'
                         '<GLOBAL-NEG-RESPONSE-SNREF SHORT-NAME="G1" /></NOT-INHERITED-GLOBAL-NEG-RESPONSE>'
                         '</NOT-INHERITED-GLOBAL-NEG-RESPONSES></PARENT-REF>')
        self.assertEqual([child.tag for child in shared],
                         ['NOT-INHERITED-DIAG-COMMS', 'NOT-INHERITED-DOPS'])
        self.assertEqual(shared.find('NOT-INHERITED-DOPS/NOT-INHERITED-DOP/DOP-BASE-SNREF').get('SHORT-NAME'), 'D1')

    def test_parent_in_same_document_has_docref(self):
        ctx = context({}, pool_id='0.0.0@B.bv')
        _, _, result = parent_refs({'parent_layers': ['0.0.0@B.bv']}, ctx)
        self.assertEqual(result[0].get('DOCREF'), 'Base')
        self.assertEqual(result[0].get('DOCTYPE'), 'LAYER')

    def test_unknown_parent_pool_is_reported(self):
        ctx, _, result = parent_refs({'parent_layers': ['0.0.0@Q.bv']})
        self.assertEqual(result[0].get('ID-REF'), 'Q')
        self.assertEqual(result[0].get('DOCREF'), 'Q')
        self.assertEqual(ctx.report['unresolvable_references'], 1)

    def test_shared_data_parent_not_in_parents_is_reported(self):
        ctx = context({})
        layers.check_shared_data_parents(ctx, {'parent_layers': ['0.0.0@B.bv'],
                                               'shared_data_parent_layers': ['0.0.0@B.bv', '0.0.0@L.sd']})
        self.assertEqual(ctx.report['shared_data_parent_not_in_parents'], 1)
        layers.check_shared_data_parents(ctx, {'parent_layers': ['0.0.0@B.bv']})
        self.assertEqual(ctx.report['shared_data_parent_not_in_parents'], 1)

    def test_no_parents_writes_nothing(self):
        for data in ({}, {'parent_layers': []}):
            _, holder, result = parent_refs(data)
            self.assertIsNone(result)
            self.assertEqual(len(holder), 0)

    def test_parent_pool_with_unknown_extension_is_reported(self):
        ctx, _, result = parent_refs({'parent_layers': ['0.0.0@B.bv', '0.0.0@X.xx']},
                                     lookup={'0.0.0@X.xx': {'layer_name': 'X', 'layer_id': 'X_ID'},
                                             **PARENTS}.get)
        self.assertEqual([ref.get(layers.XSI_TYPE) for ref in result], ['BASE-VARIANT-REF', None])
        self.assertEqual(ctx.report['unknown_parent_ref_type'], 1)

    def test_not_inherited_entry_without_parent_is_reported(self):
        data = {'parent_layers': ['0.0.0@B.bv'],
                'not_inherited_dops': entries(**{'0.0.0@B.bv': ['D1'], '0.0.0@L.sd': ['D2', 'D3']}),
                'not_inherited_tables': entries(**{'0.0.0@F.fg': ['T1']})}
        ctx, _, result = parent_refs(data)
        self.assertEqual([element.get('SHORT-NAME') for element in result.iter('DOP-BASE-SNREF')], ['D1'])
        self.assertEqual(ctx.report['not_inherited_without_parent'], 2)
        ctx, _, result = parent_refs({'not_inherited_dops': entries(**{'0.0.0@B.bv': ['D1']})})
        self.assertIsNone(result)
        self.assertEqual(ctx.report['not_inherited_without_parent'], 1)


SUBSET = '0.0.0@SUB_A.cs'


def dop(pool_id, name='DOP_SUB_A_SUB_A.DOP_X'):
    return {'object_id': name, 'pool_id': pool_id}


def simple(short_name, value, data_type='eA_UINT32', pool_id=SUBSET, protocol=None):
    return {'short_name': short_name, 'parameter_type': data_type, 'protocol_short_name': protocol,
            'default_value': {'data_type': data_type, 'value': value},
            'dop_base_reference': dop(pool_id) if pool_id else None, 'parameters': []}


def complex_param(short_name, parameters, protocol=None):
    return {'short_name': short_name, 'parameter_type': 'eSTRUCTURE', 'protocol_short_name': protocol,
            'default_value': None, 'dop_base_reference': None, 'parameters': parameters}


def comparam_refs(params, ctx=None):
    ctx = ctx or context({}, pool_id='0.0.0@B.bv')
    holder = ET.Element('X')
    result = layers.add_comparam_refs(ctx, holder, {'layer_com_params': params})
    return ctx, holder, result


class ComparamRefTests(unittest.TestCase):
    def test_simple_comparam_ref_from_dop_pool(self):
        ctx, holder, result = comparam_refs([simple('CP_Speed', 125000), simple('CP_Mode', 2)])
        self.assertEqual(list(holder), [result])
        self.assertEqual(xml(result),
                         '<COMPARAM-REFS>'
                         '<COMPARAM-REF ID-REF="SUB_A.CP_Speed" DOCREF="SUB_A" DOCTYPE="COMPARAM-SUBSET">'
                         '<SIMPLE-VALUE>125000</SIMPLE-VALUE></COMPARAM-REF>'
                         '<COMPARAM-REF ID-REF="SUB_A.CP_Mode" DOCREF="SUB_A" DOCTYPE="COMPARAM-SUBSET">'
                         '<SIMPLE-VALUE>2</SIMPLE-VALUE></COMPARAM-REF></COMPARAM-REFS>')
        self.assertEqual(layers.comparam_pool(simple('CP_Speed', 1)), SUBSET)
        self.assertEqual(sum(ctx.report.values()), 0)

    def test_bytefield_value_is_hex(self):
        _, _, result = comparam_refs([simple('CP_Bytes', bytearray(b'>\x00\xab'), 'eA_BYTEFIELD')])
        self.assertEqual(result.find('COMPARAM-REF/SIMPLE-VALUE').text, '3E00AB')

    def test_complex_comparam_pool_from_sub_parameters(self):
        entry = complex_param('CP_Table', [
            complex_param('CP_Row', [simple('CP_Cell1', 1), simple('CP_Cell2', 2)]),
            simple('CP_Last', 3, pool_id=None)])
        self.assertEqual(layers.comparam_pool(entry), SUBSET)
        _, _, result = comparam_refs([entry])
        ref, = result
        self.assertEqual((ref.get('ID-REF'), ref.get('DOCREF'), ref.get('DOCTYPE')),
                         ('SUB_A.CP_Table', 'SUB_A', 'COMPARAM-SUBSET'))

    def test_complex_value_nested_in_list_order(self):
        entry = complex_param('CP_Table', [
            simple('CP_First', 1),
            complex_param('CP_Row', [simple('CP_Cell1', bytearray(b'\x01'), 'eA_BYTEFIELD'),
                                     simple('CP_Cell2', 'Text', 'eA_ASCIISTRING')]),
            {**simple('CP_Empty', None), 'default_value': None},
            simple('CP_Last', 4)])
        ctx, _, result = comparam_refs([entry])
        self.assertEqual(xml(result[0]),
                         '<COMPARAM-REF ID-REF="SUB_A.CP_Table" DOCREF="SUB_A" DOCTYPE="COMPARAM-SUBSET">'
                         '<COMPLEX-VALUE><SIMPLE-VALUE>1</SIMPLE-VALUE>'
                         '<COMPLEX-VALUE><SIMPLE-VALUE>01</SIMPLE-VALUE><SIMPLE-VALUE>Text</SIMPLE-VALUE>'
                         '</COMPLEX-VALUE><SIMPLE-VALUE>4</SIMPLE-VALUE></COMPLEX-VALUE></COMPARAM-REF>')
        self.assertEqual(ctx.report['comparam_value_missing'], 1)

    def test_comparam_without_unique_subset_is_reported(self):
        no_pool = complex_param('CP_None', [simple('CP_Cell', 1, pool_id=None)])
        two_pools = complex_param('CP_Two', [simple('CP_Cell1', 1),
                                             complex_param('CP_Row', [simple('CP_Cell2', 2,
                                                                             pool_id='0.0.0@SUB_B.cs')])])
        empty_reference = {**simple('CP_Empty', 1), 'dop_base_reference': {}}
        for entry in (no_pool, two_pools, empty_reference):
            self.assertIsNone(layers.comparam_pool(entry))
        ctx, holder, result = comparam_refs([no_pool, simple('CP_Speed', 1), two_pools, empty_reference])
        self.assertEqual([ref.get('ID-REF') for ref in result], ['SUB_A.CP_Speed'])
        self.assertEqual(ctx.report['comparam_without_subset'], 3)
        ctx, holder, result = comparam_refs([no_pool])
        self.assertIsNone(result)
        self.assertEqual(len(holder), 0)
        self.assertEqual(ctx.report['comparam_without_subset'], 1)

    def test_protocol_snref_only_when_set(self):
        _, _, result = comparam_refs([simple('CP_A', 1, protocol='PROTO_X'), simple('CP_B', 2, protocol=''),
                                      simple('CP_C', 3),
                                      complex_param('CP_D', [simple('CP_Cell', 4)], protocol='PROTO_Y')])
        self.assertEqual([[child.tag for child in ref] for ref in result],
                         [['SIMPLE-VALUE', 'PROTOCOL-SNREF'], ['SIMPLE-VALUE'], ['SIMPLE-VALUE'],
                          ['COMPLEX-VALUE', 'PROTOCOL-SNREF']])
        self.assertEqual(result[0].find('PROTOCOL-SNREF').get('SHORT-NAME'), 'PROTO_X')
        self.assertEqual(result[3].find('PROTOCOL-SNREF').get('SHORT-NAME'), 'PROTO_Y')

    def test_simple_comparam_without_value_is_reported(self):
        ctx, _, result = comparam_refs([{**simple('CP_A', 1), 'default_value': None}])
        self.assertEqual(xml(result[0]),
                         '<COMPARAM-REF ID-REF="SUB_A.CP_A" DOCREF="SUB_A" DOCTYPE="COMPARAM-SUBSET" />')
        self.assertEqual(ctx.report['comparam_value_missing'], 1)

    def test_no_comparams_writes_nothing(self):
        for data in ({}, {'layer_com_params': []}):
            holder = ET.Element('X')
            self.assertIsNone(layers.add_comparam_refs(context({}), holder, data))
            self.assertEqual(len(holder), 0)

    def test_protocol_spec_ref_and_stack_snref(self):
        ctx = context({}, pool_id='0.0.0@P.pr')
        holder = ET.Element('PROTOCOL')
        layers.add_protocol_refs(ctx, holder, {'com_param_spec_pool_id': '0.0.0@SPEC_A.cp',
                                               'protocol_stack_short_name': 'PS_STACK_A',
                                               'protocol_type': 'TYPE_A'})
        self.assertEqual(xml(holder),
                         '<PROTOCOL><COMPARAM-SPEC-REF ID-REF="SPEC_A" DOCREF="SPEC_A" DOCTYPE="COMPARAM-SPEC" />'
                         '<PROT-STACK-SNREF SHORT-NAME="PS_STACK_A" /></PROTOCOL>')
        for data, tags in (({}, []), ({'com_param_spec_pool_id': '', 'protocol_stack_short_name': None}, []),
                           ({'protocol_stack_short_name': 'PS_STACK_A'}, ['PROT-STACK-SNREF']),
                           ({'com_param_spec_pool_id': '0.0.0@SPEC_A.cp'}, ['COMPARAM-SPEC-REF'])):
            holder = ET.Element('PROTOCOL')
            layers.add_protocol_refs(ctx, holder, data)
            self.assertEqual([child.tag for child in holder], tags)


if __name__ == '__main__':
    unittest.main()
