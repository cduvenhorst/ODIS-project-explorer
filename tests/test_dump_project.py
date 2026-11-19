import contextlib
import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest

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


def unit_record():
    return unit_body().build('MCD_DB_UNIT')


def write_strings(folder, ascii_strings=(), unicode_strings=()):
    support._write_string_files(folder, list(ascii_strings), list(unicode_strings))


def hash_key(name):
    return struct.pack('<L', support.string_hash(name, 'A'))


# Text of the .c files produced by the code before multi-part and name key support
EXPECTED_A = "ECU Shared Data\n\n'UNIT_ONE' {\n  #OBJECT_TYPE: 'MCD_DB_UNIT'\n  short_name: 'U_km'\n  long_name: 'Kilometer'\n  description: None\n  unique_object_id: 'UID'\n  long_name_id: None\n  description_id: None\n  display_name: 'km'\n  factor_si_to_unit: 1000.0\n  offset_si_to_unit: 0.0\n  physical_dimension: None\n  unit_group_references (0) {\n  }\n}\n"
EXPECTED_B = "ECU Shared Data\n\n'UNIT_TWO' {\n  #OBJECT_TYPE: 'MCD_DB_UNIT'\n  short_name: 'U_km'\n  long_name: 'Kilometer'\n  description: None\n  unique_object_id: 'UID'\n  long_name_id: None\n  description_id: None\n  display_name: 'km'\n  factor_si_to_unit: 1000.0\n  offset_si_to_unit: 0.0\n  physical_dimension: None\n  unit_group_references (0) {\n  }\n}\n"


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

    def test_dump_all_projects_exits_zero_when_clean(self):
        result = self.run_script(truncate=False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('Elapsed: ', result.stdout)
