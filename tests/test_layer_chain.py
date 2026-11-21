import os
import tempfile
import unittest

from common_utils.layer_chain import (
    get_inherited_diag_com_primitive_references, get_inherited_dtc_dop_names,
    get_inherited_env_data_descs, get_parent_layer_chain, get_protocol_layer_data_list,
    has_vw_uds_protocol, is_uds_base_variant, is_uds_protocol_type, load_layer_data)
from tests.script_support import FakeObjectLoader, layer, vector_map

UDS_TYPE = 'ISO_15765_3_on_ISO_15765_2'
KWP_TYPE = 'ISO_14230_3_on_ISO_15765_2'


def make_loader(layers):
    return FakeObjectLoader({(pool, '#RtGen_DB_LAYER_DATA'): data for pool, data in layers.items()})


def names(layer_data_list):
    return [ld['name'] for ld in layer_data_list]


def service(key, source):
    return {'map_key': key, 'reference': {'pool_id': source, 'object_id': key + '@' + source}}


def env_data_desc(key, source):
    return {'map_key': key, 'env_data_desc': {'source': source}}


class TempProjectCase(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = holder.name

    def touch(self, name):
        open(os.path.join(self.tmp, name), 'w').close()


class ChainTests(TempProjectCase):
    def test_chain_is_breadth_first_nearest_first_without_duplicates(self):
        loader = make_loader({
            'BV.bv': layer(parent_layers=['FG.fg', 'PR1.pr']),
            'FG.fg': layer(parent_layers=['PR1.pr', 'SD.sd']),
            'PR1.pr': layer(parent_layers=['BV.bv']),
            'SD.sd': layer()})
        self.assertEqual([p for p, _ in get_parent_layer_chain(loader, self.tmp, 'BV.bv')],
                         ['FG.fg', 'PR1.pr', 'SD.sd'])

    def test_chain_skips_missing_parent_pool(self):
        loader = make_loader({'BV.bv': layer(parent_layers=['GONE.pr', 'PR1.pr']), 'PR1.pr': layer()})
        self.assertEqual([p for p, _ in get_parent_layer_chain(loader, self.tmp, 'BV.bv')], ['PR1.pr'])

    def test_chain_skips_parent_pool_without_layer_data(self):
        loader = FakeObjectLoader({('BV.bv', '#RtGen_DB_LAYER_DATA'): layer(parent_layers=['X.pr', 'PR1.pr']),
                                   ('PR1.pr', '#RtGen_DB_LAYER_DATA'): layer(), ('X.pr', 'other'): {}})
        self.assertEqual([p for p, _ in get_parent_layer_chain(loader, self.tmp, 'BV.bv')], ['PR1.pr'])

    def test_chain_raises_when_layer_data_of_the_layer_itself_is_missing(self):
        loader = FakeObjectLoader({('BV.bv', 'other'): {}})
        with self.assertRaises(KeyError):
            get_parent_layer_chain(loader, self.tmp, 'BV.bv')
        with self.assertRaises(FileNotFoundError):
            get_parent_layer_chain(loader, self.tmp, 'GONE.bv')

    def test_layer_data_is_cached_per_loader_and_pool(self):
        loader = make_loader({'BV.bv': layer()})
        load_layer_data(loader, self.tmp, 'BV.bv')
        load_layer_data(loader, self.tmp, 'BV.bv')
        self.assertEqual(loader.load_calls, 1)
        other = make_loader({'BV.bv': layer()})
        load_layer_data(other, self.tmp, 'BV.bv')
        self.assertEqual(other.load_calls, 1)


class UdsTests(TempProjectCase):
    def test_uds_protocol_types(self):
        for t in ('ISO_15765_3_on_ISO_15765_2', 'ISO_14229_5_on_ISO_13400_2', 'ISO_14229_3_on_ISO_15765_2'):
            self.assertTrue(is_uds_protocol_type(t), t)
        for t in (None, '', 'ISO_14230_3_on_ISO_15765_2', 'ISO_15031_5_on_ISO_15765_4',
                  'VW2000_on_TP20', 'MSP_VW2000LP_on_TP16'):
            self.assertFalse(is_uds_protocol_type(t), t)

    def test_has_vw_uds_protocol(self):
        self.assertFalse(has_vw_uds_protocol(self.tmp))
        self.touch('0.0.0@PR_UDSOnCAN.pr.key')
        self.assertTrue(has_vw_uds_protocol(self.tmp))

    def test_base_variant_is_uds_by_protocol_type_in_chain(self):
        loader = make_loader({'BV.bv': layer(parent_layers=['FG.fg']),
                              'FG.fg': layer(parent_layers=['PR1.pr']),
                              'PR1.pr': layer(protocol_type=UDS_TYPE)})
        self.assertTrue(is_uds_base_variant(loader, self.tmp, 'BV.bv'))

    def test_base_variant_with_kwp_and_obd_only_is_not_uds(self):
        loader = make_loader({'BV.bv': layer(parent_layers=['PR1.pr', 'PR2.pr']),
                              'PR1.pr': layer(protocol_type=KWP_TYPE),
                              'PR2.pr': layer(protocol_type='ISO_OBD_on_ISO_15765_4')})
        self.assertFalse(is_uds_base_variant(loader, self.tmp, 'BV.bv'))

    def test_missing_layer_data_of_base_variant_raises_instead_of_not_uds(self):
        loader = FakeObjectLoader({('BV.bv', 'other'): {}, ('PR1.pr', '#RtGen_DB_LAYER_DATA'): layer()})
        with self.assertRaises(KeyError):
            is_uds_base_variant(loader, self.tmp, 'BV.bv')
        with self.assertRaises(KeyError):
            get_protocol_layer_data_list(loader, self.tmp, 'BV.bv')

    def test_base_variant_with_untyped_protocol_is_not_uds(self):
        loader = make_loader({'BV.bv': layer(parent_layers=['PR1.pr']), 'PR1.pr': layer(protocol_type=None)})
        self.assertFalse(is_uds_base_variant(loader, self.tmp, 'BV.bv'))

    def test_vw_project_with_pr_udsoncan_counts_every_base_variant_as_uds(self):
        self.touch('0.0.0@PR_UDSOnCAN.pr.key')
        loader = make_loader({'KWP.bv': layer(parent_layers=['PR1.pr']),
                              'PR1.pr': layer(protocol_type=KWP_TYPE)})
        self.assertTrue(is_uds_base_variant(loader, self.tmp, 'KWP.bv'))

    def vw_layers(self):
        return {'BV.bv': layer(name='BV.bv', parent_layers=['FG.fg', '0.0.0@PR_UDSOnCAN.pr']),
                'FG.fg': layer(name='FG.fg'),
                '0.0.0@PR_UDSOnCAN.pr': layer(name='PR_UDSOnCAN', parent_layers=['ES1.sd', 'ES2.sd']),
                '0.0.0@PR_OBDOnCAN.pr': layer(name='PR_OBDOnCAN'),
                'ES1.sd': layer(name='ES1.sd'), 'ES2.sd': layer(name='ES2.sd')}

    def test_protocol_list_vw_keeps_upstream_order_then_rest_of_chain(self):
        self.touch('0.0.0@PR_UDSOnCAN.pr.key')
        self.touch('0.0.0@PR_OBDOnCAN.pr.key')
        loader = make_loader(self.vw_layers())
        self.assertEqual(names(get_protocol_layer_data_list(loader, self.tmp, 'BV.bv')),
                         ['ES1.sd', 'ES2.sd', 'PR_UDSOnCAN', 'PR_OBDOnCAN', 'FG.fg'])

    def test_protocol_list_vw_without_obd_pool(self):
        self.touch('0.0.0@PR_UDSOnCAN.pr.key')
        layers = self.vw_layers()
        del layers['0.0.0@PR_OBDOnCAN.pr']
        loader = make_loader(layers)
        self.assertEqual(names(get_protocol_layer_data_list(loader, self.tmp, 'BV.bv')),
                         ['ES1.sd', 'ES2.sd', 'PR_UDSOnCAN', 'FG.fg'])

    def test_protocol_list_is_chain_order_without_vw_pool(self):
        loader = make_loader({'BV.bv': layer(parent_layers=['FG.fg', 'PR1.pr']),
                              'FG.fg': layer(name='FG.fg', parent_layers=['SD.sd']),
                              'PR1.pr': layer(name='PR1.pr', protocol_type=UDS_TYPE),
                              'SD.sd': layer(name='SD.sd')})
        expected = [ld for _, ld in get_parent_layer_chain(loader, self.tmp, 'BV.bv')]
        self.assertEqual(get_protocol_layer_data_list(loader, self.tmp, 'BV.bv'), expected)
        self.assertEqual(names(expected), ['FG.fg', 'PR1.pr', 'SD.sd'])

    def test_protocol_list_is_none_for_non_uds(self):
        loader = make_loader({'BV.bv': layer(parent_layers=['PR1.pr']),
                              'PR1.pr': layer(protocol_type=KWP_TYPE)})
        self.assertIsNone(get_protocol_layer_data_list(loader, self.tmp, 'BV.bv'))


class InheritanceTests(TempProjectCase):
    def keys(self, entries):
        return [e['map_key'] for e in entries]

    def test_inherited_services_own_first_then_parents_minus_not_inherited(self):
        loader = make_loader({
            'BV.bv': layer(diag_com_primitive_references=[service('B', 'BV'), service('C', 'BV'), service('A', 'BV')],
                           parent_layers=['FG.fg']),
            'FG.fg': layer(diag_com_primitive_references=[service('D', 'FG'), service('B', 'FG')])})
        ev = layer(diag_com_primitive_references=[service('A', 'EV')], parent_layers=['BV.bv'],
                   not_inherited_diag_com_primitives=vector_map({'BV.bv': ['C']}))
        result = get_inherited_diag_com_primitive_references(loader, self.tmp, ev)
        self.assertEqual(self.keys(result), ['A', 'B', 'D'])
        sources = {e['map_key']: e['reference']['pool_id'] for e in result}
        self.assertEqual(sources, {'A': 'EV', 'B': 'BV', 'D': 'FG'})

    def test_not_inherited_blocks_whole_branch_below_parent(self):
        loader = make_loader({
            'BV.bv': layer(diag_com_primitive_references=[service('B', 'BV')], parent_layers=['FG.fg']),
            'FG.fg': layer(diag_com_primitive_references=[service('D', 'FG')])})
        ev = layer(parent_layers=['BV.bv'], not_inherited_diag_com_primitives=vector_map({'BV.bv': ['D']}))
        self.assertEqual(self.keys(get_inherited_diag_com_primitive_references(loader, self.tmp, ev)), ['B'])

    def test_not_inherited_of_parent_applies_to_its_own_parents(self):
        loader = make_loader({
            'BV.bv': layer(parent_layers=['FG.fg'],
                           not_inherited_diag_com_primitives=vector_map({'FG.fg': ['D']})),
            'FG.fg': layer(diag_com_primitive_references=[service('D', 'FG'), service('E', 'FG')])})
        ev = layer(parent_layers=['BV.bv'])
        self.assertEqual(self.keys(get_inherited_diag_com_primitive_references(loader, self.tmp, ev)), ['E'])

    def test_branch_order_own_then_each_parent_with_its_inherited_set(self):
        # EV -> [P1, P2], P1 -> [G]; G and P2 both define X: P1's effective set (with G) precedes P2
        loader = make_loader({
            'P1.pr': layer(parent_layers=['G.pr']),
            'G.pr': layer(diag_com_primitive_references=[service('X', 'G')]),
            'P2.pr': layer(diag_com_primitive_references=[service('X', 'P2'), service('Y', 'P2')])})
        ev = layer(parent_layers=['P1.pr', 'P2.pr'])
        result = get_inherited_diag_com_primitive_references(loader, self.tmp, ev)
        self.assertEqual({e['map_key']: e['reference']['pool_id'] for e in result}, {'X': 'G', 'Y': 'P2'})
        self.assertEqual(self.keys(result), ['X', 'Y'])

    def test_inheritance_survives_cycles_and_missing_parents(self):
        loader = make_loader({
            'BV.bv': layer(diag_com_primitive_references=[service('B', 'BV')], parent_layers=['EV.ev']),
            'EV.ev': layer(parent_layers=['BV.bv'])})
        ev = layer(parent_layers=['GONE.bv', 'BV.bv'])
        self.assertEqual(self.keys(get_inherited_diag_com_primitive_references(loader, self.tmp, ev)), ['B'])

    def test_inherited_dtc_dop_names(self):
        loader = make_loader({
            'BV.bv': layer(dtc_dop_names=['B', 'C', 'A'], parent_layers=['FG.fg']),
            'FG.fg': layer(dtc_dop_names=['D', 'B'])})
        ev = layer(dtc_dop_names=['A'], parent_layers=['BV.bv'], not_inherited_dops=vector_map({'BV.bv': ['C']}))
        self.assertEqual(get_inherited_dtc_dop_names(loader, self.tmp, ev), ['A', 'B', 'D'])

    def test_inherited_env_data_descs_own_first_then_parents_minus_not_inherited(self):
        loader = make_loader({
            'BV.bv': layer(env_data_descs=[env_data_desc('EDD_B', 'BV'), env_data_desc('EDD_C', 'BV')],
                           parent_layers=['FG.fg']),
            'FG.fg': layer(env_data_descs=[env_data_desc('EDD_D', 'FG')])})
        ev = layer(env_data_descs=[env_data_desc('EDD_A', 'EV')], parent_layers=['BV.bv'],
                   not_inherited_dops=vector_map({'BV.bv': ['EDD_C']}))
        self.assertEqual(self.keys(get_inherited_env_data_descs(loader, self.tmp, ev)),
                         ['EDD_A', 'EDD_B', 'EDD_D'])

    def test_inherited_env_data_descs_own_entry_wins_over_parent_entry_of_same_name(self):
        own = env_data_desc('EDD_A', 'EV')
        loader = make_loader({
            'BV.bv': layer(env_data_descs=[env_data_desc('EDD_A', 'BV')])})
        ev = layer(env_data_descs=[own], parent_layers=['BV.bv'])
        result = get_inherited_env_data_descs(loader, self.tmp, ev)
        self.assertEqual(len(result), 1)
        self.assertIs(result[0]['env_data_desc'], own['env_data_desc'])


if __name__ == '__main__':
    unittest.main()
