import unittest

from common_utils.layer_chain import load_layer_data
from common_utils.odx_link import OdxLinkResolver
from tests.script_support import FakeObjectLoader, layer

DOP = {'name': 'DOP_L__L_16'}


def dop_entry(object_id, pool_id='L.bv'):
    return {'map_key': 'DOP_Short', 'reference': {'pool_id': pool_id, 'object_id': object_id}}


def make_link(id_reference='DOP__L_16', document_reference='DLC_L'):
    return {'#OBJECT_TYPE': 'DB_ODX_LINK', 'id_reference': id_reference,
            'document_reference': document_reference, 'is_layer_document_type': False}


class OdxLinkResolverTests(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        self.objects = {
            ('L.bv', '#RtGen_DB_LAYER_DATA'): layer(layer_name='L', dop_references=[dop_entry('DOP_L__L_16')]),
            ('L.bv', 'DOP_L__L_16'): DOP,
        }

    def resolver(self, pool_ids=('L.bv',)):
        return OdxLinkResolver(FakeObjectLoader(self.objects), 'project', list(pool_ids))

    def test_link_resolves_through_layer_dop_map(self):
        self.assertEqual(self.resolver().resolve(make_link()), (DOP, None))

    def test_document_without_dlc_prefix(self):
        self.assertEqual(self.resolver().resolve(make_link(document_reference='X_L')),
                         (None, 'ODX link document is not a layer: X_L'))

    def test_unknown_layer(self):
        self.assertEqual(self.resolver().resolve(make_link(document_reference='DLC_M')),
                         (None, 'ODX link layer not found: M'))

    def test_layer_in_two_pools(self):
        self.objects[('L2.pr', '#RtGen_DB_LAYER_DATA')] = layer(layer_name='L')
        self.assertEqual(self.resolver(['L.bv', 'L2.pr']).resolve(make_link()),
                         (None, 'ODX link layer in more than one pool: L'))

    def test_dop_missing_from_map(self):
        self.assertEqual(self.resolver().resolve(make_link(id_reference='DOP__L_99')),
                         (None, 'ODX link DOP not found: DOP_L__L_99'))

    def test_dop_listed_twice(self):
        self.objects[('L.bv', '#RtGen_DB_LAYER_DATA')]['dop_references'].append(dop_entry('DOP_L__L_16'))
        self.assertEqual(self.resolver().resolve(make_link()),
                         (None, 'ODX link DOP listed more than once: DOP_L__L_16'))

    def test_dop_listed_but_not_loadable(self):
        self.objects[('L.bv', '#RtGen_DB_LAYER_DATA')]['dop_references'] = [dop_entry('DOP_L__L_16', 'Z.bv')]
        self.assertEqual(self.resolver().resolve(make_link()),
                         (None, 'ODX link DOP could not be loaded: DOP_L__L_16'))

    def test_pools_without_layer_data_are_skipped(self):
        self.objects[('X.vi', 'other')] = {}
        self.assertEqual(self.resolver(['X.vi', 'Y.cs', 'L.bv']).resolve(make_link()), (DOP, None))

    def test_ecu_configuration_pools_are_not_loaded(self):
        self.objects[('E.ec', '#RtGen_DB_LAYER_DATA')] = layer(layer_name='L')
        self.assertEqual(self.resolver(['L.bv', 'E.ec']).resolve(make_link()), (DOP, None))


if __name__ == '__main__':
    unittest.main()
