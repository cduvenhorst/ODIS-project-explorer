import contextlib
import csv
import io
import os
import tempfile
import unittest
from unittest import mock

import dumpFlash
from tests import support
from tests.flash_workspace_support import DocBlock, write_file, write_loose_odx
from tests.test_flash_project_sources import container, put, sw_block

A_BYTES = bytes([0xC3, 0x5A, 0x91, 0x7E, 0x2D, 0xB4, 0x68, 0xF1])


def make_project(root, name, with_a=True):
    folder = os.path.join(root, name)
    os.makedirs(folder)
    support.write_project(folder, {}, [], [])
    if with_a:
        put(folder, 'Dev/flash-data/a.bin', A_BYTES)
    put(folder, 'Tools/k.dll', b'seed-key')
    put(folder, 'index.xml', b'<CATALOG/>')
    put(folder, 'Common/DVR/s.odx', b'<ODX/>')
    put(folder, 'Dev/flash-data/c.sgm', container(sw_block('B1', 'AQID')))
    return folder


class DumpFlashTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = os.path.realpath(self._temp.name)
        self.out = os.path.join(self.root, 'out')
        previous = os.getcwd()
        os.chdir(support.REPOSITORY_ROOT)
        self.addCleanup(os.chdir, previous)

    def run_main(self, command, source, output, *extra):
        # Takes the folders in command line order and passes them as named options
        source_option = '--projects' if command == 'projects' else '--project'
        argv = [command, source_option, source, '--output', output]
        for item in extra:
            argv.extend([item] if item.startswith('--') else ['--workspace', item])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            code = dumpFlash.main(argv)
        return code, stdout.getvalue()

    def overview_rows(self):
        with open(os.path.join(self.out, 'flash', 'flash_overview.csv'), newline='', encoding='utf-8') as handle:
            return list(csv.DictReader(handle))

    def test_project_writes_files_and_overview(self):
        folder = make_project(self.root, 'P1')
        code, text = self.run_main('project', folder, self.out)
        self.assertEqual(code, 0)
        base = os.path.join(self.out, 'flash', 'P1')
        with open(os.path.join(base, 'Dev', 'flash-data', 'a.bin'), 'rb') as handle:
            self.assertEqual(handle.read(), A_BYTES)
        self.assertTrue(os.path.isfile(os.path.join(base, 'Tools', 'k.dll')))
        self.assertTrue(os.path.isfile(os.path.join(base, 'Dev', 'flash-data', 'c', 'B1.bin')))
        self.assertEqual(len(self.overview_rows()), 4)
        self.assertIn('Collecting P1', text)
        self.assertIn('Overview: ', text)
        self.assertIn('Elapsed: ', text)

    def test_project_copies_other_project_files(self):
        folder = make_project(self.root, 'P1')
        code, _ = self.run_main('project', folder, self.out, '--hexdump')
        self.assertEqual(code, 0)
        for relative, content in (('index.xml', b'<CATALOG/>'), ('Common/DVR/s.odx', b'<ODX/>')):
            with open(os.path.join(self.out, 'P1', *relative.split('/')), 'rb') as handle:
                self.assertEqual(handle.read(), content)
        self.assertFalse(os.path.exists(os.path.join(self.out, 'P1', 'index.xml.hexdump.txt')))
        self.assertFalse(os.path.exists(os.path.join(self.out, 'P1', 'Tools', 'k.dll')))

    def test_projects_copies_other_files_of_each_valid_project(self):
        projects = os.path.join(self.root, 'all')
        for name in ('P1', 'P2'):
            make_project(projects, name)
        bad = os.path.join(projects, 'bad')
        os.makedirs(bad)
        put(bad, 'index.xml', b'<CATALOG/>')
        code, _ = self.run_main('projects', projects, self.out)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'P1', 'index.xml')))
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'P2', 'index.xml')))
        self.assertFalse(os.path.exists(os.path.join(self.out, 'bad')))

    def test_second_run_copies_the_same_project_files(self):
        folder = make_project(self.root, 'P1')

        def files():
            return sorted(os.path.relpath(os.path.join(base, name), os.path.join(self.out, 'P1'))
                          for base, _, names in os.walk(os.path.join(self.out, 'P1')) for name in names)

        self.assertEqual(self.run_main('project', folder, self.out)[0], 0)
        first = files()
        self.assertEqual(self.run_main('project', folder, self.out)[0], 0)
        self.assertEqual(files(), first)
        self.assertIn('index.xml', first)

    def test_second_run_gives_same_overview(self):
        folder = make_project(self.root, 'P1')
        self.assertEqual(self.run_main('project', folder, self.out)[0], 0)
        path = os.path.join(self.out, 'flash', 'flash_overview.csv')
        with open(path, 'rb') as handle:
            first = handle.read()
        self.assertEqual(self.run_main('project', folder, self.out)[0], 0)
        with open(path, 'rb') as handle:
            self.assertEqual(handle.read(), first)

    def test_hexdump_flag(self):
        folder = make_project(self.root, 'P1')
        self.assertEqual(self.run_main('project', folder, self.out, '--hexdump')[0], 0)
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'flash', 'P1', 'Dev', 'flash-data', 'a.bin.hexdump.txt')))

    def test_projects_skips_invalid_folder_and_dedups_across_projects(self):
        projects = os.path.join(self.root, 'all')
        os.makedirs(os.path.join(projects, 'Empty'))
        for name in ('P2', 'P1'):
            folder = os.path.join(projects, name)
            os.makedirs(folder)
            support.write_project(folder, {}, [], [])
            put(folder, 'Dev/flash-data/a.bin', A_BYTES)
        code, text = self.run_main('projects', projects, self.out)
        self.assertEqual(code, 0)
        self.assertIn('Invalid project', text)
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'flash', 'P1', 'Dev', 'flash-data', 'a.bin')))
        self.assertFalse(os.path.exists(os.path.join(self.out, 'flash', 'P2')))
        duplicates = {row['origin']: row['duplicate'] for row in self.overview_rows()}
        self.assertEqual(duplicates, {'P1': 'no', 'P2': 'yes'})

    def test_output_inside_source_is_refused(self):
        folder = make_project(self.root, 'P1')
        target = os.path.join(folder, 'out')
        with mock.patch('dumpFlash.PblRecordManager') as manager:
            code, text = self.run_main('project', folder, target)
        self.assertEqual(code, 1)
        self.assertIn('Output folder must not be inside the source folder', text)
        self.assertFalse(os.path.exists(target))
        manager.assert_not_called()

    def test_output_inside_source_with_other_case_spelling_is_refused(self):
        folder = make_project(self.root, 'Proj')
        swapped = os.path.join(self.root, 'pROJ')
        if not os.path.exists(swapped):
            self.skipTest('file system is case-sensitive')
        target = os.path.join(swapped, 'out')
        code, text = self.run_main('project', folder, target)
        self.assertEqual(code, 1)
        self.assertIn('Output folder must not be inside the source folder', text)
        self.assertFalse(os.path.exists(os.path.join(folder, 'out')))

    def snapshot(self, folder):
        result = {}
        for current, _, names in os.walk(folder):
            for name in names:
                path = os.path.join(current, name)
                with open(path, 'rb') as handle:
                    result[path] = handle.read()
        return result

    def test_project_output_mapping_onto_source_is_refused(self):
        folder = make_project(self.root, 'P1')
        before = self.snapshot(folder)
        with mock.patch('dumpFlash.PblRecordManager') as manager:
            code, text = self.run_main('project', folder, self.root)
        self.assertEqual(code, 1)
        self.assertIn('Output folder must not overlap the source folder', text)
        self.assertEqual(self.snapshot(folder), before)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'flash')))
        manager.assert_not_called()

    def test_projects_output_mapping_onto_a_project_is_refused(self):
        all_folder = os.path.join(self.root, 'All')
        os.makedirs(all_folder)
        folder = make_project(all_folder, 'All')
        before = self.snapshot(folder)
        with mock.patch('dumpFlash.PblRecordManager') as manager:
            code, text = self.run_main('projects', all_folder, self.root)
        self.assertEqual(code, 1)
        self.assertIn('Output folder must not overlap the source folder', text)
        self.assertEqual(self.snapshot(folder), before)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'flash')))
        manager.assert_not_called()

    def test_sibling_with_same_prefix_is_accepted(self):
        folder = make_project(self.root, 'proj')
        self.assertFalse(dumpFlash.is_inside(os.path.join(self.root, 'proj2'), folder))
        self.assertFalse(dumpFlash.is_inside(os.path.join(self.root, 'proj2', 'out'), folder))
        self.assertTrue(dumpFlash.is_inside(os.path.join(folder, 'a', 'b'), folder))

    def test_not_enough_space(self):
        folder = make_project(self.root, 'P1')
        with mock.patch('flash_export.output.free_space', return_value=0):
            code, text = self.run_main('project', folder, self.out)
        self.assertEqual(code, 1)
        self.assertIn('Not enough free space', text)
        self.assertFalse(os.path.exists(self.out))

    def test_console_shows_no_content(self):
        folder = make_project(self.root, 'P1')
        code, text = self.run_main('project', folder, self.out, '--hexdump')
        self.assertEqual(code, 0)
        self.assertNotIn(A_BYTES.hex(), text.lower())
        self.assertNotIn(A_BYTES.hex(' '), text.lower())
        self.assertNotIn(A_BYTES.decode('latin-1'), text)

    def test_dot_as_project_path_uses_real_folder_name(self):
        folder = make_project(self.root, 'P1')
        os.chdir(folder)
        with mock.patch('dumpFlash.PblRecordManager'):
            code, _ = self.run_main('project', '.', self.out)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'flash', 'P1', 'Dev', 'flash-data', 'a.bin')))
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, 'flash'))), ['P1', 'flash_overview.csv'])

    def test_dot_dot_as_project_path_uses_real_folder_name(self):
        folder = make_project(self.root, 'P1')
        os.makedirs(os.path.join(folder, 'sub'))
        os.chdir(os.path.join(folder, 'sub'))
        with mock.patch('dumpFlash.PblRecordManager'):
            code, _ = self.run_main('project', '..', self.out)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.out, 'flash', 'P1', 'Dev', 'flash-data', 'a.bin')))

    def test_unwritable_output_folder_is_reported_once(self):
        folder = make_project(self.root, 'P1')
        blocker = os.path.join(self.root, 'file')
        with open(blocker, 'wb'):
            pass
        code, text = self.run_main('project', folder, os.path.join(blocker, 'out'))
        self.assertEqual(code, 1)
        self.assertEqual(text.count('Cannot create output folder'), 1)
        self.assertIn(os.path.join(blocker, 'out', 'flash') + ': ', text)
        self.assertIn('NotADirectoryError', text)

    def make_workspace(self, mapping='pidt-vehicle-platform.pa=[Pp][Aa].*\n'):
        workspace = os.path.join(self.root, 'ws')
        for platform, payload in (('pa', b'\x11\x22\x33\x44'), ('pb', b'\x55\x66\x77\x88')):
            write_loose_odx(workspace, platform, 'x.odx', [DocBlock('blk', data=payload)])
        if mapping is not None:
            write_file(os.path.join(workspace, 'mapping.properties'), mapping.encode())
        return workspace

    def workspace_origins(self):
        return {row['origin'] for row in self.overview_rows() if row['origin_kind'] == 'workspace'}

    def test_project_with_workspace_reads_only_mapped_platform(self):
        folder = make_project(self.root, 'PA1')
        workspace = self.make_workspace()
        code, text = self.run_main('project', folder, self.out, workspace)
        self.assertEqual(code, 0)
        self.assertEqual(self.workspace_origins(), {'pa'})
        self.assertIn('Collecting workspace pa', text)
        self.assertNotIn('Collecting workspace pb', text)

    def test_projects_with_workspace_reads_all_platforms(self):
        projects = os.path.join(self.root, 'all')
        os.makedirs(projects)
        make_project(projects, 'PA1')
        workspace = self.make_workspace(mapping=None)
        code, text = self.run_main('projects', projects, self.out, workspace)
        self.assertEqual(code, 0)
        self.assertEqual(self.workspace_origins(), {'pa', 'pb'})
        self.assertIn('Collecting workspace pa', text)
        self.assertIn('Collecting workspace pb', text)

    def test_project_without_mapping_match_continues(self):
        folder = make_project(self.root, 'QX')
        workspace = self.make_workspace()
        code, text = self.run_main('project', folder, self.out, workspace)
        self.assertEqual(code, 0)
        self.assertIn('No vehicle platform in workspace for QX', text)
        self.assertEqual(self.workspace_origins(), set())
        self.assertEqual(len(self.overview_rows()), 4)

    def test_project_with_workspace_without_mapping_file(self):
        folder = make_project(self.root, 'PA1')
        workspace = self.make_workspace(mapping=None)
        code, text = self.run_main('project', folder, self.out, workspace)
        self.assertEqual(code, 1)
        self.assertIn('No mapping.properties in workspace', text)
        self.assertFalse(os.path.exists(self.out))

    def test_project_with_invalid_mapping_expression_writes_nothing(self):
        folder = make_project(self.root, 'PA1')
        workspace = self.make_workspace(mapping='pidt-vehicle-platform.pa=[\n')
        code, text = self.run_main('project', folder, self.out, workspace)
        self.assertEqual(code, 1)
        self.assertIn('invalid regular expression', text)
        self.assertFalse(os.path.exists(self.out))

    def test_output_inside_workspace_is_refused(self):
        folder = make_project(self.root, 'PA1')
        workspace = self.make_workspace()
        target = os.path.join(workspace, 'out')
        with mock.patch('dumpFlash.PblRecordManager') as manager:
            code, text = self.run_main('project', folder, target, workspace)
        self.assertEqual(code, 1)
        self.assertIn('Output folder must not be inside the workspace folder', text)
        self.assertFalse(os.path.exists(target))
        manager.assert_not_called()

    def test_workspace_must_be_folder(self):
        folder = make_project(self.root, 'PA1')
        with mock.patch('dumpFlash.PblRecordManager') as manager:
            code, text = self.run_main('project', folder, self.out, os.path.join(self.root, 'missing'))
        self.assertEqual(code, 1)
        self.assertIn('Workspace must be folder', text)
        self.assertFalse(os.path.exists(self.out))
        manager.assert_not_called()

    def test_projects_output_inside_workspace_is_refused(self):
        projects = os.path.join(self.root, 'all')
        os.makedirs(projects)
        make_project(projects, 'PA1')
        workspace = self.make_workspace(mapping=None)
        target = os.path.join(workspace, 'out')
        with mock.patch('dumpFlash.PblRecordManager') as manager:
            code, text = self.run_main('projects', projects, target, workspace)
        self.assertEqual(code, 1)
        self.assertIn('Output folder must not be inside the workspace folder', text)
        self.assertFalse(os.path.exists(target))
        manager.assert_not_called()

    def test_projects_workspace_must_be_folder(self):
        projects = os.path.join(self.root, 'all')
        os.makedirs(projects)
        make_project(projects, 'PA1')
        with mock.patch('dumpFlash.PblRecordManager') as manager:
            code, text = self.run_main('projects', projects, self.out, os.path.join(self.root, 'missing'))
        self.assertEqual(code, 1)
        self.assertIn('Workspace must be folder', text)
        self.assertFalse(os.path.exists(self.out))
        manager.assert_not_called()


if __name__ == '__main__':
    unittest.main()
