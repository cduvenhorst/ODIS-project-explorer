import os
import shutil
import tempfile
import unittest

from classes.PBL import default_library_path
from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from common_utils.reference_resolver import NOT_RESOLVABLE, ReferenceResolver, insert_after
from tests import support
from tests.support import REPOSITORY_ROOT, string_hash, unit_body

LIBRARY = default_library_path(REPOSITORY_ROOT)
CAPTION_KEY = string_hash('CAP_A', 'A')


def caption_record(short_name='CAP_A'):
    body = (support.ObjectBytes().native_ascii(None).native_ascii(None).native_ascii(None)
            .native_unicode(None).native_unicode(None).native_ascii(short_name))
    return body.build('MCD_DB_SPECIAL_DATA_GROUP_CAPTION')


def group_record(caption=None, items=None):
    element = support.sdg_element_body('TXT', 'Content')
    if items is None:
        items = [('MCD_DB_SPECIAL_DATA_ELEMENT', element)]
    return support.sdg_group_body(items, caption).build('MCD_DB_SPECIAL_DATA_GROUP')


class ReferenceResolverTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def make_project(self, pool_objects=None, sdg_records=None, extra_pools=None, ascii_strings=()):
        pools = {'A.sd': {'CAP_A': caption_record(), 'UNIT_ONE': unit_body().build('MCD_DB_UNIT')}}
        if pool_objects is not None:
            pools['A.sd'] = pool_objects
        pools.update(extra_pools or {})
        support.write_project(self.folder, pools, list(ascii_strings), [])
        if sdg_records is not None:
            support.write_sdg_file(self.folder, 'A.sd', sdg_records)
        return ReferenceResolver(self.folder, StringStorage(self.folder), PblRecordManager(LIBRARY))

    def resolve(self, resolver, obj):
        resolver.resolve_object(obj, 'A.sd')
        return obj

    def test_insert_after_keeps_order(self):
        obj = {'a': 1, 'b': 2, 'c': 3}
        insert_after(obj, 'a', 'new', 9)
        self.assertEqual(['a', 'new', 'b', 'c'], list(obj))
        self.assertEqual(9, obj['new'])

    def test_sdg_reference_resolves_to_group_with_caption(self):
        resolver = self.make_project(sdg_records=[group_record((CAPTION_KEY, None))])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})
        self.assertEqual(['special_data_group_references', 'special_data_groups'], list(obj))
        group = obj['special_data_groups'][0]
        self.assertEqual('Content', group['items'][0]['content'])
        self.assertEqual('CAP_A', group['caption']['short_name'])
        self.assertEqual(['items', 'caption_reference', 'caption', 'semantic_information'],
                         [key for key in group if key != '#OBJECT_TYPE'])

    def test_group_without_caption_reference_has_no_caption(self):
        resolver = self.make_project(sdg_records=[group_record()])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})
        self.assertIsNone(obj['special_data_groups'][0]['caption'])

    def test_nested_group_gets_its_caption(self):
        inner = ('MCD_DB_SPECIAL_DATA_GROUP', support.sdg_group_body((), (CAPTION_KEY, '')))
        resolver = self.make_project(sdg_records=[group_record(items=[inner])])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})
        self.assertEqual('CAP_A', obj['special_data_groups'][0]['items'][0]['caption']['short_name'])

    def test_sdg_reference_in_nested_parameter_is_resolved(self):
        resolver = self.make_project(sdg_records=[group_record()])
        obj = self.resolve(resolver, {'parameters': [{'special_data_group_references': [{'object_id': 1}]}]})
        self.assertEqual('Content', obj['parameters'][0]['special_data_groups'][0]['items'][0]['content'])

    def test_sdg_reference_without_file_is_not_resolvable(self):
        resolver = self.make_project()
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}, {'object_id': 2}]})
        self.assertEqual([NOT_RESOLVABLE, NOT_RESOLVABLE], obj['special_data_groups'])

    def test_sdg_reference_out_of_range_is_not_resolvable(self):
        resolver = self.make_project(sdg_records=[group_record()])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 0}, {'object_id': 1}, {'object_id': 2}]})
        groups = obj['special_data_groups']
        self.assertEqual([NOT_RESOLVABLE, NOT_RESOLVABLE], [groups[0], groups[2]])
        self.assertIsInstance(groups[1], dict)

    def test_undecodable_record_raises(self):
        resolver = self.make_project(sdg_records=[bytearray(b'\x00')])
        with self.assertRaises(Exception):
            self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})

    def test_caption_key_missing_or_other_type_is_not_resolvable(self):
        missing = (string_hash('MISSING', 'A'), None)
        other_type = (string_hash('UNIT_ONE', 'A'), None)
        resolver = self.make_project(sdg_records=[group_record(missing), group_record(other_type)])
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}, {'object_id': 2}]})
        self.assertEqual([NOT_RESOLVABLE, NOT_RESOLVABLE], [group['caption'] for group in obj['special_data_groups']])

    def test_caption_is_looked_up_in_own_pool_whatever_pool_id_says(self):
        resolver = self.make_project(sdg_records=[group_record((CAPTION_KEY, 'B.sd'))],
                                     ascii_strings=['B.sd'],
                                     extra_pools={'B.sd': {'UNIT_ONE': unit_body().build('MCD_DB_UNIT')}})
        obj = self.resolve(resolver, {'special_data_group_references': [{'object_id': 1}]})
        group = obj['special_data_groups'][0]
        self.assertEqual('CAP_A', group['caption']['short_name'])
        self.assertEqual('B.sd', group['caption_reference']['pool_id'])

    def test_empty_sdg_references_add_nothing(self):
        resolver = self.make_project(sdg_records=[group_record()])
        obj = self.resolve(resolver, {'special_data_group_references': [], 'other': [1, {'x': 2}]})
        self.assertEqual({'special_data_group_references': [], 'other': [1, {'x': 2}]}, obj)

    def test_load_object_by_name_hash_and_missing(self):
        resolver = self.make_project()
        by_name = resolver.load_object('', 'CAP_A', 'A.sd')
        self.assertEqual('CAP_A', by_name['short_name'])
        self.assertEqual(by_name, resolver.load_object(None, CAPTION_KEY, 'A.sd'))
        self.assertIsNone(resolver.load_object('A.sd', 'NOPE', 'A.sd'))
        self.assertIsNone(resolver.load_object('Z.sd', 'CAP_A', 'A.sd'))


if __name__ == '__main__':
    unittest.main()
