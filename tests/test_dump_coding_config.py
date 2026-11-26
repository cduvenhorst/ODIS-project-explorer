import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import dumpCoding
from common_utils.config_records import ConfigRecordSource
from common_utils.layer_chain import load_layer_data
from tests.script_support import FakeObjectLoader, layer
from tests.table_fixtures import base_variant_objects
from tests.test_config_records import config_record, entry_config_data, entry_objects, link_option

NUMERIC_LINE = 'Configuration records skipped: database older than version 0012'


def config_info(*listed):
    return {'unknown_1': [], 'unknown_3': [], 'unknown_4': [],
            'unknown_2': [{'map_key': 'BV', 'items': [{'object_id': name, 'name': name} for name in listed]}]}


def project_objects(case_map_values=None, protocol_type='ISO_15765_3_on_ISO_15765_2'):
    # configuration data CD applies to the variants named in case_map_values; [] means the whole base variant
    objects = base_variant_objects()
    objects[('PR.pr', '#RtGen_DB_LAYER_DATA')] = layer(name='PR', layer_name='PR', protocol_type=protocol_type)
    objects[('BV.bv', '#RtGen_DB_LAYER_DATA')] = layer(name='BV', layer_name='BV', parent_layers=['PR.pr'])
    objects.update(entry_objects(config_record([link_option()])))
    objects[('E.ec', 'DbEcuConfigInfo')] = config_info('CD')
    objects[('E.ec', 'CD')] = dict(entry_config_data(), base_variant_to_case_map=[
        {'map_key': 'BV', 'values': [] if case_map_values is None else case_map_values}])
    return objects


class DumpCodingConfigTests(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.holder = holder.name
        self.out = os.path.join(holder.name, 'out')
        self.ev_layer = layer(name='EV', parent_layers=['BV.bv'])

    def dump(self, objects, overwrite=False):
        loader = FakeObjectLoader(objects)
        source = ConfigRecordSource(loader, 'project', pool_ids=['E.ec', 'L.bv'])
        output = io.StringIO()
        with mock.patch.object(dumpCoding, 'get_ecu_variant_layer_data', return_value=self.ev_layer), \
                contextlib.redirect_stdout(output):
            dumpCoding.dump_codings_for_base_variant(loader, 'project', 'BV.bv.db', self.out, overwrite,
                                                     config_source=source)
        return output.getvalue()

    def dump_with(self, objects, source='built', desired=None, project='project', reader=None):
        loader = FakeObjectLoader(objects)
        if source == 'built':
            source = ConfigRecordSource(loader, 'project', pool_ids=['E.ec', 'L.bv'])
        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(dumpCoding, 'get_ecu_variant_layer_data',
                                                  return_value=self.ev_layer))
            stack.enter_context(contextlib.redirect_stdout(output))
            if reader is not None:
                stack.enter_context(mock.patch.object(dumpCoding, 'TableEntryReader', return_value=reader))
                stack.enter_context(mock.patch.object(dumpCoding, 'flatten_coding_entry', return_value=[]))
            dumpCoding.dump_codings_for_base_variant(loader, project, 'BV.bv.db', self.out, False,
                                                     desired_ecu_variant=desired, config_source=source)
        return output.getvalue()

    def coding_reader(self):
        reader = mock.Mock()
        reader.select_services.return_value = ['service']
        reader.get_entries.return_value = [{'did': 1, 'long_name_id': 'ID_X', 'long_name': 'X'}]
        return reader

    def project_folder(self):
        project = os.path.join(self.holder, 'project')
        os.makedirs(project)
        for name in ('BV.bv.db', 'BV.bv.key', 'E.ec.key', 'PR.pr.key'):
            open(os.path.join(project, name), 'w').close()
        return project

    def path(self, name):
        return os.path.join(self.out, 'BV', name)

    def test_config_file_for_variant(self):
        self.dump(project_objects())
        with open(self.path('CONFIG_EV.json'), encoding='utf-8') as file:
            entries = json.load(file)
        self.assertEqual(['CD'], [entry['short_name'] for entry in entries])
        self.assertTrue(os.path.isfile(self.path('CONFIG_BV.json')))

    def test_config_file_without_coding_service(self):
        output = self.dump(project_objects())
        self.assertTrue(os.path.isfile(self.path('CONFIG_EV.json')))
        self.assertFalse(os.path.exists(self.path('VRC_EV.json')))
        self.assertIn('Has no Coding', output)

    def test_no_config_file_without_config_data(self):
        self.dump(project_objects(['OTHER']))
        self.assertFalse(os.path.exists(self.path('CONFIG_EV.json')))
        self.assertFalse(os.path.exists(self.path('CONFIG_BV.json')))

    def test_non_uds_base_variant_writes_config_only(self):
        output = self.dump(project_objects(protocol_type=None))
        self.assertTrue(os.path.isfile(self.path('CONFIG_EV.json')))
        self.assertEqual([], [name for name in os.listdir(self.path('')) if name.startswith('VRC_')])
        self.assertIn('Not UDS', output)

    def test_existing_config_file_is_kept_without_overwrite(self):
        os.makedirs(self.path(''))
        with open(self.path('CONFIG_EV.json'), 'w', encoding='utf-8') as file:
            file.write('[]')
        output = self.dump(project_objects())
        with open(self.path('CONFIG_EV.json'), encoding='utf-8') as file:
            self.assertEqual('[]', file.read())
        self.assertIn('CONFIG already done, skipping', output)

    def test_existing_config_file_is_replaced_with_overwrite(self):
        os.makedirs(self.path(''))
        with open(self.path('CONFIG_EV.json'), 'w', encoding='utf-8') as file:
            file.write('[]')
        self.dump(project_objects(), overwrite=True)
        with open(self.path('CONFIG_EV.json'), encoding='utf-8') as file:
            self.assertEqual(1, len(json.load(file)))

    def test_numeric_case_maps_are_reported(self):
        objects = project_objects()
        objects[('E.ec', 'DbEcuConfigInfo')] = config_info('CD', 'CD_N')
        objects[('E.ec', 'CD_N')] = dict(entry_config_data('CD_N'), base_variant_to_case_map=[
            {'map_key': 7, 'values': []}])
        project = os.path.join(self.holder, 'project')
        os.makedirs(project)
        for name in ('BV.bv.db', 'BV.bv.key', 'E.ec.key', 'PR.pr.key'):
            open(os.path.join(project, name), 'w').close()
        loader = FakeObjectLoader(objects)
        output = io.StringIO()
        with mock.patch.object(dumpCoding, 'get_ecu_variant_layer_data', return_value=self.ev_layer), \
                contextlib.redirect_stdout(output):
            dumpCoding.dump_codings_for_all_base_variants_in_project(loader, project, self.out)
        self.assertEqual(1, output.getvalue().count(NUMERIC_LINE))
        self.assertTrue(os.path.isfile(self.path('CONFIG_EV.json')))

    def test_failing_config_entries_keep_the_coding_output(self):
        source = mock.Mock(has_numeric_case_maps=False)
        source.entries_for_variant.side_effect = RuntimeError('boom')
        output = self.dump_with(project_objects(), source=source, reader=self.coding_reader())
        self.assertIn('Configuration records failed: boom', output)
        self.assertTrue(os.path.isfile(self.path('VRC_EV.json')))
        self.assertTrue(os.path.isfile(self.path('VRC_BV.json')))
        self.assertFalse(os.path.exists(self.path('CONFIG_EV.json')))

    def test_failing_config_source_keeps_the_coding_output(self):
        with mock.patch.object(dumpCoding, 'ConfigRecordSource', side_effect=RuntimeError('no source')):
            output = self.dump_with(project_objects(), source=None, reader=self.coding_reader())
        self.assertIn('Configuration records failed: no source', output)
        self.assertTrue(os.path.isfile(self.path('VRC_EV.json')))
        self.assertFalse(os.path.exists(self.path('CONFIG_EV.json')))

    def test_non_uds_project_data_failure_does_not_abort(self):
        objects = project_objects(protocol_type=None)
        del objects[('BV.bv', '#RtGen_DB_PROJECT_DATA')]
        output = self.dump_with(objects)
        self.assertIn('Configuration records failed:', output)
        self.assertFalse(os.path.exists(self.path('')))

    def test_non_uds_skip_line_names_the_file(self):
        os.makedirs(self.path(''))
        with open(self.path('CONFIG_EV.json'), 'w', encoding='utf-8') as file:
            file.write('[]')
        output = self.dump(project_objects(protocol_type=None))
        self.assertIn('CONFIG already done, skipping: CONFIG_EV.json', output)

    def test_source_is_built_when_none_is_passed(self):
        objects = project_objects()
        objects[('E.ec', 'DbEcuConfigInfo')] = config_info('CD', 'CD_N')
        objects[('E.ec', 'CD_N')] = dict(entry_config_data('CD_N'), base_variant_to_case_map=[
            {'map_key': 7, 'values': []}])
        output = self.dump_with(objects, source=None, project=self.project_folder())
        self.assertEqual(1, output.count(NUMERIC_LINE))
        self.assertTrue(os.path.isfile(self.path('CONFIG_EV.json')))
        self.assertTrue(os.path.isfile(self.path('CONFIG_BV.json')))

    def test_failing_project_source_is_reported_once_and_keeps_the_coding_output(self):
        loader = FakeObjectLoader(project_objects())
        output = io.StringIO()
        with mock.patch.object(dumpCoding, 'ConfigRecordSource', side_effect=RuntimeError('no source')), \
                mock.patch.object(dumpCoding, 'get_ecu_variant_layer_data', return_value=self.ev_layer), \
                mock.patch.object(dumpCoding, 'TableEntryReader', return_value=self.coding_reader()), \
                mock.patch.object(dumpCoding, 'flatten_coding_entry', return_value=[]), \
                contextlib.redirect_stdout(output):
            dumpCoding.dump_codings_for_all_base_variants_in_project(loader, self.project_folder(), self.out)
        self.assertEqual(1, output.getvalue().count('Configuration records failed: no source'))
        self.assertTrue(os.path.isfile(self.path('VRC_EV.json')))
        self.assertFalse(os.path.exists(self.path('CONFIG_EV.json')))

    def test_requested_variant_writes_only_its_config_file(self):
        self.dump_with(project_objects(), desired='EV')
        self.assertTrue(os.path.isfile(self.path('CONFIG_EV.json')))
        self.assertFalse(os.path.exists(self.path('CONFIG_BV.json')))


if __name__ == '__main__':
    unittest.main()
