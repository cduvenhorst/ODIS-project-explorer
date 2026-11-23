"""Tests for the per-layer view of a pool and the target layer of references."""
import unittest
import xml.etree.ElementTree as ET

from odx_export import data_objects
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


if __name__ == '__main__':
    unittest.main()
