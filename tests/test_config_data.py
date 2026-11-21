import os
import shutil
import tempfile
import unittest

from classes.PBL import default_library_path
from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from common_utils import config_data
from common_utils.reference_resolver import NOT_RESOLVABLE, ReferenceResolver
from tests import support
from tests.support import REPOSITORY_ROOT

LIBRARY = default_library_path(REPOSITORY_ROOT)


def write_file(folder, relative_path, content=b'x'):
    path = os.path.join(folder, *relative_path.split('/'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as handle:
        handle.write(content)


class ConfigDataFilesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def test_list_files_sorted_with_sizes_and_subfolders(self):
        write_file(self.folder, 'ConfigData_CD_X/b.bin', b'12')
        write_file(self.folder, 'ConfigData_CD_X/a.bin', b'1')
        write_file(self.folder, 'ConfigData_CD_X/sub/c.bin', b'123')
        self.assertEqual([{'name': 'a.bin', 'size': 1}, {'name': 'b.bin', 'size': 2},
                          {'name': 'sub/c.bin', 'size': 3}],
                         config_data.list_config_data_files(self.folder, 'ConfigData_CD_X'))

    def test_missing_folder_lists_nothing(self):
        self.assertEqual([], config_data.list_config_data_files(self.folder, 'ConfigData_CD_X'))

    def test_folders_are_sorted_and_filtered_by_prefix(self):
        os.mkdir(os.path.join(self.folder, 'ConfigData_B'))
        os.mkdir(os.path.join(self.folder, 'ConfigData_A'))
        os.mkdir(os.path.join(self.folder, 'Other'))
        write_file(self.folder, 'ConfigData_file', b'x')
        self.assertEqual(['ConfigData_A', 'ConfigData_B'], config_data.config_data_folders(self.folder))

    def test_matching_is_case_sensitive_wildcard(self):
        files = [{'name': 'a.bin', 'size': 1}, {'name': 'b.BIN', 'size': 1}, {'name': 'c.xml', 'size': 1}]
        self.assertEqual([{'name': 'a.bin', 'size': 1}], config_data.matching_config_data_files(files, '*.bin'))

    def test_copy_without_overwrite_copies_missing_target_and_keeps_existing(self):
        output = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, output)
        write_file(self.folder, 'ConfigData_CD_X/a.bin', b'new')
        write_file(self.folder, 'ConfigData_CD_X/b.bin', b'new')
        write_file(output, 'ConfigData_CD_X/a.bin', b'old')
        config_data.copy_config_data(self.folder, output, False)
        with open(os.path.join(output, 'ConfigData_CD_X', 'a.bin'), 'rb') as handle:
            self.assertEqual(b'old', handle.read())
        with open(os.path.join(output, 'ConfigData_CD_X', 'b.bin'), 'rb') as handle:
            self.assertEqual(b'new', handle.read())

    def test_copy_with_overwrite_replaces_existing_target(self):
        output = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, output)
        write_file(self.folder, 'ConfigData_CD_X/a.bin', b'new')
        write_file(output, 'ConfigData_CD_X/a.bin', b'old')
        config_data.copy_config_data(self.folder, output, True)
        with open(os.path.join(output, 'ConfigData_CD_X', 'a.bin'), 'rb') as handle:
            self.assertEqual(b'new', handle.read())


class ConfigDataResolverTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)
        write_file(self.folder, 'ConfigData_CD_X/a.bin', b'1')
        write_file(self.folder, 'ConfigData_CD_X/b.xml', b'12')
        support.write_project(self.folder, {'A.sd': {}}, [], [])
        self.resolver = ReferenceResolver(self.folder, StringStorage(self.folder), PblRecordManager(LIBRARY))

    def resolve(self, name, parent, file_name):
        data = support.data_record_body(name, parent, file_name)
        obj = support.load('MCD_DB_DATA_RECORD', data)
        self.resolver.resolve_object(obj, 'A.sd')
        return obj

    def test_configuration_data_lists_all_files(self):
        obj = {'#OBJECT_TYPE': 'MCD_DB_CONFIGURATION_DATA', 'short_name': 'CD_X', 'other': 1}
        self.resolver.resolve_object(obj, 'A.sd')
        self.assertEqual('configuration_data_files', list(obj)[-1])
        self.assertEqual([{'name': 'a.bin', 'size': 1}, {'name': 'b.xml', 'size': 2}],
                         obj['configuration_data_files'])
        self.assertEqual({'CD_X'}, self.resolver.configuration_data_short_names)

    def test_configuration_data_without_short_name_is_not_resolvable(self):
        for short_name in (None, ''):
            with self.subTest(short_name=short_name):
                obj = {'#OBJECT_TYPE': 'MCD_DB_CONFIGURATION_DATA', 'short_name': short_name}
                self.resolver.resolve_object(obj, 'A.sd')
                self.assertEqual(NOT_RESOLVABLE, obj['configuration_data_files'])
                self.assertEqual('configuration_data_files', list(obj)[-1])
                self.assertEqual(set(), self.resolver.configuration_data_short_names)

    def test_data_record_lists_only_matching_files(self):
        obj = self.resolve('REC', 'CD_X', '*.bin')
        self.assertEqual('configuration_data_files', list(obj)[-1])
        self.assertEqual([{'name': 'a.bin', 'size': 1}], obj['configuration_data_files'])

    def test_data_record_pattern_without_match_gives_empty_list(self):
        self.assertEqual([], self.resolve('REC', 'CD_X', '*.none')['configuration_data_files'])

    def test_data_record_without_parent_or_coding_data_is_not_resolvable(self):
        for parent, file_name in ((None, '*.bin'), ('CD_X', None), (None, None)):
            with self.subTest(parent=parent, file_name=file_name):
                self.assertEqual(NOT_RESOLVABLE, self.resolve('REC', parent, file_name)['configuration_data_files'])


if __name__ == '__main__':
    unittest.main()
