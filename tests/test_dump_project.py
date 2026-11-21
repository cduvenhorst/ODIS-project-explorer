import contextlib
import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import dumpAllProjects
import dumpProject
from classes.StringStorage import StringStorage
from tests import support
from tests.support import REPOSITORY_ROOT, unit_body, write_project, write_raw_pool


def dump(project_folder, overwrite=True):
    """Run app_dumpProject on a project folder; return (output folder files, stdout)."""
    storage = StringStorage(project_folder)
    with tempfile.TemporaryDirectory() as output_folder:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            dumpProject.app_dumpProject(storage, project_folder, output_folder, overwrite)
        files = {}
        for name in sorted(os.listdir(output_folder)):
            with open(os.path.join(output_folder, name), encoding='utf-8') as handle:
                files[name] = handle.read()
    return files, stdout.getvalue()


def dump_tree(project_folder, overwrite=True):
    """Like dump(), but also report folders: keys are relative paths with '/'.

    A folder without files is listed as 'name/' with the value ''.
    """
    storage = StringStorage(project_folder)
    with tempfile.TemporaryDirectory() as output_folder:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            dumpProject.app_dumpProject(storage, project_folder, output_folder, overwrite)
        tree = {}
        for directory, folders, names in os.walk(output_folder):
            relative = os.path.relpath(directory, output_folder)
            prefix = '' if relative == '.' else relative.replace(os.sep, '/') + '/'
            if not names and not folders and prefix:
                tree[prefix] = ''
            for name in names:
                with open(os.path.join(directory, name), encoding='utf-8') as handle:
                    tree[prefix + name] = handle.read()
    return dict(sorted(tree.items())), stdout.getvalue()


def unit_record():
    return unit_body().build('MCD_DB_UNIT')


def write_strings(folder, ascii_strings=(), unicode_strings=()):
    support._write_string_files(folder, list(ascii_strings), list(unicode_strings))


def hash_key(name):
    return struct.pack('<L', support.string_hash(name, 'A'))


# Text of the .c files produced by the code before multi-part and name key support
EXPECTED_A = "ECU Shared Data\n\n'UNIT_ONE' {\n  #OBJECT_TYPE: 'MCD_DB_UNIT'\n  short_name: 'U_km'\n  long_name: 'Kilometer'\n  description: None\n  unique_object_id: 'UID'\n  long_name_id: None\n  description_id: None\n  display_name: 'km'\n  factor_si_to_unit: 1000.0\n  offset_si_to_unit: 0.0\n  physical_dimension: None\n  unit_group_references (0) {\n  }\n}\n"
EXPECTED_B = "ECU Shared Data\n\n'UNIT_TWO' {\n  #OBJECT_TYPE: 'MCD_DB_UNIT'\n  short_name: 'U_km'\n  long_name: 'Kilometer'\n  description: None\n  unique_object_id: 'UID'\n  long_name_id: None\n  description_id: None\n  display_name: 'km'\n  factor_si_to_unit: 1000.0\n  offset_si_to_unit: 0.0\n  physical_dimension: None\n  unit_group_references (0) {\n  }\n}\n"


# Text of B.sd.c for a state without transitions and a ConfigData without SDG references
EXPECTED_STATE_AND_CONFIGURATION = "ECU Shared Data\n\n'CD_X' {\n  #OBJECT_TYPE: 'MCD_DB_CONFIGURATION_DATA'\n  description_id: None\n  long_name_id: None\n  unique_object_id: None\n  description: None\n  long_name: None\n  short_name: 'CD_X'\n  configuration_record_references (0) {\n  }\n  base_variant_to_case_map (0) {\n  }\n  special_data_group_references (0) {\n  }\n  major: 0x0\n  minor: 0x0\n  revision: 0x0\n  is_revision_label_available: False\n  additional_audiences (0) {\n  }\n  configuration_data_files (0) {\n  }\n}\n\n'ST_A' {\n  #OBJECT_TYPE: 'MCD_DB_ECU_STATE'\n  description: None\n  long_name: None\n  short_name: 'ST_A'\n  description_id: None\n  long_name_id: None\n  unique_object_id: None\n  ecu_state_transitions (0) {\n  }\n}\n"


class BuilderTest(unittest.TestCase):
    def test_ecu_state_body_loads(self):
        loaded = support.load('MCD_DB_ECU_STATE', support.ecu_state_body('ST_A', (('TR_AB', 'OBJ', 'B.sd'), ('TR_AC', 'OBJ2', None))), strict=True)
        self.assertEqual('ST_A', loaded['short_name'])
        self.assertEqual([{'name': 'TR_AB', 'reference': {'object_id': 'OBJ', 'pool_id': 'B.sd', 'attributes': []}},
                          {'name': 'TR_AC', 'reference': {'object_id': 'OBJ2', 'pool_id': None, 'attributes': []}}],
                         loaded['ecu_state_transitions'])
        self.assertEqual([], support.load('MCD_DB_ECU_STATE', support.ecu_state_body('ST_B'), strict=True)['ecu_state_transitions'])

    def test_configuration_data_body_loads(self):
        loaded = support.load('MCD_DB_CONFIGURATION_DATA', support.configuration_data_body('CD_X', (3, 7)), strict=True)
        self.assertEqual('CD_X', loaded['short_name'])
        self.assertEqual([{'object_id': 3}, {'object_id': 7}], loaded['special_data_group_references'])
        empty = support.load('MCD_DB_CONFIGURATION_DATA', support.configuration_data_body('CD_X'), strict=True)
        self.assertEqual([], empty['special_data_group_references'])
        self.assertEqual([], empty['base_variant_to_case_map'])


class DumpProjectTest(unittest.TestCase):
    def setUp(self):
        self.folder_handle = tempfile.TemporaryDirectory()
        self.folder = self.folder_handle.name
        self.addCleanup(self.folder_handle.cleanup)

    def test_project_with_hash_keys_dumps_same_text(self):
        unit = unit_body()
        write_project(self.folder, {'A.sd': {'UNIT_ONE': unit_record()}, 'B.sd': {'UNIT_TWO': unit_record()}},
                      unit.ascii_strings, unit.unicode_strings)
        files, stdout = dump(self.folder)
        self.assertEqual({'A.sd.c': EXPECTED_A, 'B.sd.c': EXPECTED_B}, files)
        self.assertEqual('', stdout)

    def test_objects_without_references_dump_as_before(self):
        unit = unit_body()
        state = support.ecu_state_body('ST_A')
        data = support.configuration_data_body('CD_X')
        ascii_strings = unit.ascii_strings + state.ascii_strings + data.ascii_strings
        write_project(self.folder,
                      {'A.sd': {'UNIT_ONE': unit_record()},
                       'B.sd': {'ST_A': state.build('MCD_DB_ECU_STATE'),
                                'CD_X': data.build('MCD_DB_CONFIGURATION_DATA')}},
                      ascii_strings, unit.unicode_strings)
        os.mkdir(os.path.join(self.folder, 'ConfigData_CD_Y'))
        tree, stdout = dump_tree(self.folder)
        self.assertEqual({'A.sd.c', 'B.sd.c'}, set(tree))
        self.assertEqual(EXPECTED_A, tree['A.sd.c'])
        self.assertEqual(EXPECTED_STATE_AND_CONFIGURATION, tree['B.sd.c'])
        self.assertEqual('', stdout)

    def test_dump_shows_special_data_groups_beside_references(self):
        data = support.configuration_data_body('CD_X', sdg_numbers=(1,))
        element = support.sdg_element_body('TXT', 'Content')
        group = support.sdg_group_body([('MCD_DB_SPECIAL_DATA_ELEMENT', element)]).build('MCD_DB_SPECIAL_DATA_GROUP')
        write_project(self.folder, {'B.sd': {'CD_X': data.build('MCD_DB_CONFIGURATION_DATA')}},
                      data.ascii_strings, data.unicode_strings)
        support.write_sdg_file(self.folder, 'B.sd', [group])
        files, _ = dump(self.folder)
        text = files['B.sd.c']
        references = "  special_data_group_references (1) {\n    [0] {\n      object_id: 0x1\n    }\n  }\n"
        self.assertIn(references + "  special_data_groups (1) {\n", text)
        self.assertIn("content: 'Content'", text)

    def config_data_project(self):
        data = support.configuration_data_body('CD_X')
        write_project(self.folder, {'B.sd': {'CD_X': data.build('MCD_DB_CONFIGURATION_DATA')}},
                      data.ascii_strings, data.unicode_strings)

    def write_config_file(self, relative_path, content=b'x'):
        path = os.path.join(self.folder, *relative_path.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as handle:
            handle.write(content)

    def test_dump_copies_config_data_and_skips_empty_folders(self):
        self.config_data_project()
        self.write_config_file('ConfigData_CD_X/a.bin', b'1')
        self.write_config_file('ConfigData_CD_X/sub/b.bin', b'22')
        os.mkdir(os.path.join(self.folder, 'ConfigData_CD_EMPTY'))
        tree, stdout = dump_tree(self.folder)
        self.assertEqual(['B.sd.c', 'ConfigData_CD_X/a.bin', 'ConfigData_CD_X/sub/b.bin'], list(tree))
        self.assertEqual('1', tree['ConfigData_CD_X/a.bin'])
        self.assertEqual('22', tree['ConfigData_CD_X/sub/b.bin'])
        self.assertIn("    name: 'a.bin'\n", tree['B.sd.c'])
        self.assertEqual('', stdout)

    def test_unreferenced_folder_with_files_is_reported(self):
        self.config_data_project()
        self.write_config_file('ConfigData_CD_X/a.bin')
        self.write_config_file('ConfigData_CD_Y/a.bin')
        _, stdout = dump_tree(self.folder)
        self.assertEqual('ConfigData folder ConfigData_CD_Y is not referenced by any object\n', stdout)

    def test_rerun_without_overwrite_reports_nothing_and_keeps_copies(self):
        self.config_data_project()
        self.write_config_file('ConfigData_CD_X/a.bin', b'old')
        self.write_config_file('ConfigData_CD_Y/a.bin')
        storage = StringStorage(self.folder)
        with tempfile.TemporaryDirectory() as output_folder:
            with contextlib.redirect_stdout(io.StringIO()):
                dumpProject.app_dumpProject(storage, self.folder, output_folder, True)
            self.write_config_file('ConfigData_CD_X/a.bin', b'new')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                dumpProject.app_dumpProject(storage, self.folder, output_folder, False)
            with open(os.path.join(output_folder, 'ConfigData_CD_X', 'a.bin'), 'rb') as handle:
                self.assertEqual(b'old', handle.read())
        self.assertEqual('', stdout.getvalue())

    def raw_project(self, entries, pool='A.sd', ascii_strings=()):
        write_strings(self.folder, ascii_strings)
        write_raw_pool(self.folder, pool, entries)

    def test_name_key_is_dumped_under_its_name(self):
        self.raw_project([(b'DbFlashName_X', [unit_record()])])
        files, _ = dump(self.folder)
        self.assertIn("\n'DbFlashName_X' {\n  #OBJECT_TYPE: 'MCD_DB_UNIT'\n", files['A.sd.c'])

    def test_four_byte_name_key_without_string_uses_hash_label(self):
        # kernel: a 4-byte key is read as a hash; without a string it has no name
        self.raw_project([(b'ABCD', [unit_record()])])
        files, _ = dump(self.folder)
        self.assertIn("\n'hash {}' {{\n".format(struct.unpack('<L', b'ABCD')[0]), files['A.sd.c'])

    def test_hash_key_without_string_is_dumped_with_hash_label(self):
        self.raw_project([(struct.pack('<L', 4711), [unit_record()])])
        files, _ = dump(self.folder)
        self.assertIn("\n'hash 4711' {\n  #OBJECT_TYPE: 'MCD_DB_UNIT'\n", files['A.sd.c'])

    def test_hash_key_with_string_is_dumped_under_the_string(self):
        self.raw_project([(hash_key('UNIT_ONE'), [unit_record()])], ascii_strings=['UNIT_ONE'])
        files, _ = dump(self.folder)
        self.assertIn("\n'UNIT_ONE' {\n", files['A.sd.c'])

    def test_two_part_inline_flash_record_shows_length_only(self):
        content = b'0102' * 8
        type_code = struct.pack('<H', support.object_type_code('DB_INLINE_FLASH_DATA'))
        self.raw_project([(b'InlineFlash_X', [type_code, content])])
        files, stdout = dump(self.folder)
        self.assertIn('inline_flash_data_length: 0x20', files['A.sd.c'])
        self.assertNotIn(content.decode('ascii'), files['A.sd.c'])
        self.assertNotIn(content.decode('ascii'), stdout)
        self.assertNotIn('not empty', stdout)

    def test_unlisted_pool_is_reported(self):
        unit = unit_body()
        write_project(self.folder, {'A.sd': {'UNIT_ONE': unit_record()}, 'B.sd': {'UNIT_TWO': unit_record()}},
                      unit.ascii_strings, unit.unicode_strings)
        with open(os.path.join(self.folder, 'rt_index.xml'), 'w', encoding='utf-8') as handle:
            handle.write('<INDEX><SECTION><FILE>sub\\A.sd.db</FILE><FILE>A.sd.key</FILE></SECTION></INDEX>')
        files, stdout = dump(self.folder)
        self.assertEqual({'B.sd'}, dumpProject.pools_not_in_rt_index(self.folder))
        self.assertEqual('Pool B.sd is not listed in rt_index.xml\n', stdout)
        self.assertEqual('ECU Shared Data\nNot listed in rt_index.xml\n', files['B.sd.c'][:43])
        self.assertEqual(EXPECTED_A, files['A.sd.c'])

    def test_missing_or_broken_rt_index_gives_no_note(self):
        unit = unit_body()
        write_project(self.folder, {'A.sd': {'UNIT_ONE': unit_record()}}, unit.ascii_strings, unit.unicode_strings)
        self.assertIsNone(dumpProject.pools_not_in_rt_index(self.folder))
        files, stdout = dump(self.folder)
        self.assertEqual({'A.sd.c': EXPECTED_A}, files)
        self.assertEqual('', stdout)
        with open(os.path.join(self.folder, 'rt_index.xml'), 'w', encoding='utf-8') as handle:
            handle.write('<INDEX><FILE>A.sd.db')
        self.assertIsNone(dumpProject.pools_not_in_rt_index(self.folder))
        files, stdout = dump(self.folder)
        self.assertEqual({'A.sd.c': EXPECTED_A}, files)
        self.assertEqual('', stdout)

    def test_unreadable_rt_index_gives_no_note(self):
        unit = unit_body()
        write_project(self.folder, {'A.sd': {'UNIT_ONE': unit_record()}}, unit.ascii_strings, unit.unicode_strings)
        with open(os.path.join(self.folder, 'rt_index.xml'), 'w', encoding='utf-8') as handle:
            handle.write('<INDEX/>')
        with mock.patch.object(dumpProject.ET, 'parse', side_effect=PermissionError('denied')):
            self.assertIsNone(dumpProject.pools_not_in_rt_index(self.folder))
        # a directory in place of the file counts as missing
        os.remove(os.path.join(self.folder, 'rt_index.xml'))
        os.mkdir(os.path.join(self.folder, 'rt_index.xml'))
        self.assertIsNone(dumpProject.pools_not_in_rt_index(self.folder))

    def test_failing_pool_leaves_no_half_written_file(self):
        unit = unit_body()
        write_project(self.folder, {'A.sd': {'UNIT_ONE': unit_record()}}, unit.ascii_strings, unit.unicode_strings)
        with open(os.path.join(self.folder, 'A.sd.db'), 'r+b') as handle:
            handle.truncate(4)
        storage = StringStorage(self.folder)
        with tempfile.TemporaryDirectory() as output_folder:
            with self.assertRaises(Exception), contextlib.redirect_stdout(io.StringIO()):
                dumpProject.app_dumpProject(storage, self.folder, output_folder, False)
            self.assertEqual([], os.listdir(output_folder))


class DumpAllProjectsTest(unittest.TestCase):
    def run_script(self, truncate):
        with tempfile.TemporaryDirectory() as root:
            projects = os.path.join(root, 'projects')
            project = os.path.join(projects, 'P')
            os.makedirs(project)
            unit = unit_body()
            write_project(project, {'A.sd': {'UNIT_ONE': unit_record()}}, unit.ascii_strings, unit.unicode_strings)
            if truncate:
                with open(os.path.join(project, 'A.sd.db'), 'r+b') as handle:
                    handle.truncate(4)
            return subprocess.run([sys.executable, '-B', 'dumpAllProjects.py', projects, os.path.join(root, 'out')],
                                  cwd=REPOSITORY_ROOT, capture_output=True, text=True)

    def test_dump_all_projects_exits_nonzero_on_error(self):
        result = self.run_script(truncate=True)
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn('Elapsed: ', result.stdout)
        self.assertIn('Error', result.stdout)

    def test_rerun_after_failure_still_fails(self):
        with tempfile.TemporaryDirectory() as root:
            projects = os.path.join(root, 'projects')
            project = os.path.join(projects, 'P')
            os.makedirs(project)
            unit = unit_body()
            write_project(project, {'A.sd': {'UNIT_ONE': unit_record()}}, unit.ascii_strings, unit.unicode_strings)
            with open(os.path.join(project, 'A.sd.db'), 'r+b') as handle:
                handle.truncate(4)
            command = [sys.executable, '-B', 'dumpAllProjects.py', projects, os.path.join(root, 'out')]
            for run in (1, 2):
                result = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True)
                self.assertEqual(1, result.returncode, 'run {}: {}'.format(run, result.stderr))
            self.assertFalse(os.path.exists(os.path.join(root, 'out', 'P', 'A.sd.c')))

    def test_dump_all_projects_exits_zero_when_clean(self):
        result = self.run_script(truncate=False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('Elapsed: ', result.stdout)
