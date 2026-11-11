import contextlib
import io
import json
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock

from classes.PBL import default_library_path
from tests import support
from tests.support import ObjectBytes, REPOSITORY_ROOT, unit_body
from tools import inventory

LIBRARY = default_library_path(REPOSITORY_ROOT)


def sample_pool():
    return {
        'Good': unit_body().build('MCD_DB_UNIT'),
        'TooLong': unit_body().u8(7).build('MCD_DB_UNIT'),
        'NoLoader': ObjectBytes().build('MCD_DB_CONTROL_PRIMITIVES'),
    }


def write_sample_project(folder, pools=None):
    os.makedirs(folder, exist_ok=True)
    body = unit_body()
    support.write_project(folder, pools or {'P1': sample_pool()},
                          body.ascii_strings, body.unicode_strings)


def run_main(arguments):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = inventory.main(arguments)
    return code, out.getvalue(), err.getvalue()


class InventoryTests(unittest.TestCase):
    def make_folder(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        return folder

    def test_counts_ok_failed_unknown(self):
        project = self.make_folder()
        write_sample_project(project)
        result = inventory.inventory_project(project, LIBRARY)
        unit = result['types']['MCD_DB_UNIT']
        self.assertEqual(unit, {'code': support.object_type_code('MCD_DB_UNIT'),
                                'ok': 1, 'failed': 1, 'unknown': 0})
        self.assertEqual(result['types']['MCD_DB_CONTROL_PRIMITIVES']['unknown'], 1)
        self.assertIn('MCD_DB_UNIT | UnreadBytesError: 1 bytes', result['errors'])
        self.assertEqual(result['errors']['MCD_DB_UNIT | UnreadBytesError: 1 bytes'], 1)
        self.assertEqual(result['pools']['P1'], {'ok': 1, 'failed': 1, 'unknown': 1, 'pool_error': None})

    def test_pool_with_name_keys_is_read(self):
        project = self.make_folder()
        body = unit_body()
        support.write_project(project, {}, body.ascii_strings, body.unicode_strings)
        code = support.object_type_code('MCD_DB_CONTROL_PRIMITIVES')
        support.write_raw_pool(project, 'P1', [
            (b'UnitByName', [bytes(body.build('MCD_DB_UNIT'))]),
            (b'MultiPart', [code.to_bytes(2, 'little'), b'content'])])
        result = inventory.inventory_project(project, LIBRARY)
        self.assertIsNone(result['pools']['P1']['pool_error'])
        self.assertEqual(result['types']['MCD_DB_UNIT']['ok'], 1)
        self.assertEqual(result['types']['MCD_DB_CONTROL_PRIMITIVES']['unknown'], 1)

    def test_big_data_record_is_read_strictly(self):
        project = self.make_folder()
        body = unit_body()
        support.write_project(project, {}, body.ascii_strings, body.unicode_strings)
        code = struct.pack('<H', support.object_type_code('DB_INLINE_FLASH_DATA'))
        support.write_raw_pool(project, 'P1', [
            (b'Big', [code, b'0A1B']),
            (b'BigBad', [code + b'\x00', b'0A1B'])])
        result = inventory.inventory_project(project, LIBRARY)
        self.assertIsNone(result['pools']['P1']['pool_error'])
        entry = result['types']['DB_INLINE_FLASH_DATA']
        self.assertEqual((entry['ok'], entry['failed'], entry['unknown']), (1, 1, 0))
        self.assertIn('DB_INLINE_FLASH_DATA | UnreadBytesError: 1 bytes', result['errors'])

    def test_broken_pool_is_counted_and_run_continues(self):
        project = self.make_folder()
        write_sample_project(project, {'A1': sample_pool(), 'B2': sample_pool()})
        os.remove(os.path.join(project, 'B2.db'))
        result = inventory.inventory_project(project, LIBRARY)
        self.assertTrue(result['pools']['B2']['pool_error'])
        self.assertIsNone(result['pools']['A1']['pool_error'])
        self.assertEqual(result['pools']['A1']['ok'], 1)
        self.assertEqual(result['types']['MCD_DB_UNIT']['ok'], 1)

    def test_refuses_output_inside_repository(self):
        target = os.path.join(REPOSITORY_ROOT, 'out')
        code, _, err = run_main(['--output', target, self.make_folder()])
        self.assertEqual(code, 2)
        self.assertTrue(err)
        self.assertFalse(os.path.exists(target))

    def test_clone_root_is_resolved_relative_to_repository_not_cwd(self):
        outside = self.make_folder()
        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(outside)
        with mock.patch.object(inventory, 'git_output', side_effect=lambda *a: '.git' if 'rev-parse' in a and '--git-common-dir' in a else REPOSITORY_ROOT):
            roots = inventory.protected_roots()
            self.assertNotIn(os.path.realpath(outside), roots)
            project = self.make_folder()
            write_sample_project(project)
            accepted, _, _ = run_main(['--output', os.path.join(outside, 'result'), project])
            refused, _, err = run_main(['--output', os.path.join(REPOSITORY_ROOT, 'out'), project])
        self.assertEqual(accepted, 0)
        self.assertEqual(refused, 2)
        self.assertTrue(err)
        self.assertFalse(os.path.exists(os.path.join(REPOSITORY_ROOT, 'out')))

    def test_project_without_string_files_is_a_project_error_and_run_continues(self):
        root = self.make_folder()
        good = os.path.join(root, 'A', 'Projects-V', 'Good')
        bad = os.path.join(root, 'A', 'Projects-V', 'Bad')
        write_sample_project(good)
        os.makedirs(bad)
        output = os.path.join(root, 'result')
        code, _, _ = run_main(['--output', output, bad, good])
        self.assertEqual(code, 0)
        with open(os.path.join(output, 'A-Bad.json')) as handle:
            self.assertTrue(json.load(handle)['project_error'])
        with open(os.path.join(output, 'A-Good.json')) as handle:
            self.assertNotIn('project_error', json.load(handle))
        with open(os.path.join(output, 'summary.txt')) as handle:
            self.assertEqual(len(handle.read().splitlines()), 2)

    def test_bad_library_exits_2_before_writing(self):
        root = self.make_folder()
        project = os.path.join(root, 'P')
        write_sample_project(project)
        output = os.path.join(root, 'result')
        code, _, err = run_main(['--output', output, '--library', os.path.join(root, 'missing.dylib'), project])
        self.assertEqual(code, 2)
        self.assertIn('library', err)
        self.assertFalse(os.path.exists(output))

    def test_uncreatable_output_exits_2_without_traceback(self):
        root = self.make_folder()
        project = os.path.join(root, 'P')
        write_sample_project(project)
        blocker = os.path.join(root, 'file')
        with open(blocker, 'w') as handle:
            handle.write('x')
        for target in (blocker, os.path.join(blocker, 'sub')):
            code, _, err = run_main(['--output', target, project])
            self.assertEqual(code, 2)
            self.assertIn('Cannot create output folder', err)

    def test_refuses_output_inside_repository_via_dotdot_and_symlink(self):
        outside = self.make_folder()
        link = os.path.join(outside, 'link')
        os.symlink(REPOSITORY_ROOT, link)
        tricky = os.path.join(outside, '..', os.path.basename(outside), 'x', '..', 'link', 'tools', 'new')
        for target in (os.path.join(link, 'new'), tricky):
            code, _, _ = run_main(['--output', target, outside])
            self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(os.path.join(REPOSITORY_ROOT, 'new')))
        self.assertFalse(os.path.exists(os.path.join(REPOSITORY_ROOT, 'tools', 'new')))

    def test_refuses_output_in_clone_root_and_sibling_worktrees(self):
        common = subprocess.run(['git', 'rev-parse', '--git-common-dir'], cwd=REPOSITORY_ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        clone_root = os.path.dirname(os.path.realpath(os.path.join(REPOSITORY_ROOT, common)))
        for target in (os.path.join(clone_root, 'inventory-out'),
                       os.path.join(clone_root, '.worktrees', 'other', 'inventory-out')):
            existed = os.path.exists(os.path.dirname(target))
            code, _, err = run_main(['--output', target, self.make_folder()])
            self.assertEqual(code, 2)
            self.assertTrue(err)
            self.assertFalse(os.path.exists(target))
            self.assertEqual(os.path.exists(os.path.dirname(target)), existed)

    def test_refuses_inside_repository_root_when_git_fails(self):
        target = os.path.join(REPOSITORY_ROOT, 'out')
        with mock.patch.object(inventory.subprocess, 'run', side_effect=OSError('no git')):
            code, _, err = run_main(['--output', target, self.make_folder()])
        self.assertEqual(code, 2)
        self.assertIn('Warning: git is not available', err)
        self.assertFalse(os.path.exists(target))

    def test_refuses_output_spelled_with_different_case(self):
        swapped = REPOSITORY_ROOT.swapcase()
        if not os.path.exists(swapped):
            self.skipTest('file system is case-sensitive')
        target = os.path.join(swapped, 'out')
        code, _, _ = run_main(['--output', target, self.make_folder()])
        self.assertEqual(code, 2)
        self.assertFalse(os.path.exists(os.path.join(REPOSITORY_ROOT, 'out')))

    def test_same_project_name_in_two_installations(self):
        root = self.make_folder()
        for installation in ('A', 'B'):
            write_sample_project(os.path.join(root, installation, 'Projects-V', 'OBD'))
        output = os.path.join(root, 'result')
        projects = [os.path.join(root, name, 'Projects-V', 'OBD') for name in ('A', 'B')]
        code, _, _ = run_main(['--output', output] + projects)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(os.listdir(output)), ['A-OBD.json', 'B-OBD.json', 'summary.txt'])
        with open(os.path.join(output, 'A-OBD.json')) as handle:
            self.assertEqual(json.load(handle)['types']['MCD_DB_UNIT']['ok'], 1)
        with open(os.path.join(output, 'summary.txt')) as handle:
            self.assertIn('A-OBD', handle.read())

    def test_output_name_falls_back_to_parent_folder(self):
        self.assertEqual(inventory.output_name('/x/Inst/Projects-V/OBD'), 'Inst-OBD')
        self.assertEqual(inventory.output_name('/x/Other/OBD/'), 'Other-OBD')


if __name__ == '__main__':
    unittest.main()
