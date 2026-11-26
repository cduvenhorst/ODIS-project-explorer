import os
import tempfile
import unittest

from common_utils.config_records import ConfigDataIndex, project_pool_ids
from tests.script_support import FakeObjectLoader


def config_data(short_name, *case_map):
    return {'short_name': short_name,
            'base_variant_to_case_map': [{'map_key': key, 'unknown_1': 4, 'values': values}
                                         for key, values in case_map]}


def config_info():
    return {'unknown_1': [],
            'unknown_2': [{'map_key': 'BV', 'items': [{'object_id': 'CD_B', 'name': 'CD_B'},
                                                      {'object_id': 'CD_A', 'name': 'CD_A'}]}],
            'unknown_3': [{'map_key': 'EV1', 'items': [{'object_id': 'CD_V', 'name': 'CD_V'},
                                                       {'object_id': 'CD_A', 'name': 'CD_A'}]}],
            'unknown_4': []}


def objects(extra=None):
    result = {('E.ec', 'DbEcuConfigInfo'): config_info(),
              ('E.ec', 'CD_B'): config_data('CD_B', ('BV', [])),
              ('E.ec', 'CD_A'): config_data('CD_A', ('BV', [])),
              ('E.ec', 'CD_V'): config_data('CD_V', ('BV', ['EV1']))}
    result.update(extra or {})
    return result


def short_names(config_data_objects):
    return [item['short_name'] for item in config_data_objects]


class ConfigDataIndexTests(unittest.TestCase):
    def index(self, extra=None, pool_ids=('E.ec',)):
        return ConfigDataIndex(FakeObjectLoader(objects(extra)), 'project', list(pool_ids))

    def test_variant_gets_base_level_then_own(self):
        self.assertEqual(['CD_A', 'CD_B', 'CD_V'], short_names(self.index().for_variant('BV', 'EV1')))

    def test_base_variant_gets_base_level_only(self):
        self.assertEqual(['CD_A', 'CD_B'], short_names(self.index().for_variant('BV', 'BV')))

    def test_other_variant_gets_base_level_only(self):
        self.assertEqual(['CD_A', 'CD_B'], short_names(self.index().for_variant('BV', 'EV2')))

    def test_other_base_variant_gets_nothing(self):
        self.assertEqual([], self.index().for_variant('BX', 'BX'))

    def test_numeric_case_map_is_skipped_and_flagged(self):
        info = config_info()
        info['unknown_1'] = [{'map_key': 'BV', 'items': [{'object_id': 'CD_N', 'name': 'CD_N'}]}]
        index = self.index({('E.ec', 'DbEcuConfigInfo'): info,
                            ('E.ec', 'CD_N'): config_data('CD_N', (7, []))})
        self.assertTrue(index.has_numeric_case_maps)
        for variant in ('BV', 'EV1', 'EV2'):
            self.assertNotIn('CD_N', short_names(index.for_variant('BV', variant)))
        self.assertFalse(self.index().has_numeric_case_maps)

    def test_pool_without_config_info_is_skipped(self):
        index = self.index({('F.ec', 'Other'): {}}, pool_ids=('E.ec', 'F.ec'))
        self.assertEqual(['CD_A', 'CD_B', 'CD_V'], short_names(index.for_variant('BV', 'EV1')))

    def test_duplicate_listing_loads_once(self):
        found = short_names(self.index().for_variant('BV', 'EV1'))
        self.assertEqual(1, found.count('CD_A'))

    def test_config_data_missing_from_unknown_4_is_listed(self):
        self.assertEqual([], config_info()['unknown_4'])
        self.assertEqual(3, len(self.index().for_variant('BV', 'EV1')))

    def test_project_pool_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('B.bv.key', 'A.ec.key', 'A.ec.db'):
                open(os.path.join(folder, name), 'w').close()
            self.assertEqual(['A.ec', 'B.bv'], project_pool_ids(folder))


if __name__ == '__main__':
    unittest.main()
