"""Tests for dumpODX: one ODX document per shared data pool of a synthetic project."""
import contextlib
import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import dumpODX
from classes.StringStorage import StringStorage
from odx_export.pool_source import ProjectPools
from tests import support
from tests.odx_support import context
from tests.support import REPOSITORY_ROOT, concat, unit_body, write_project, write_raw_pool
from tests.test_vw_layouts_project import layer_data_body, project_data_body

L_POOL = '0.0.0@L.sd'
N_POOL = '5.4.0@N.sd'
B_POOL = '0.0.0@B.sd'


def pool_objects(unit_key):
    return {'#RtGen_DB_LAYER_DATA': layer_data_body().build('DB_LAYER_DATA'),
            '#RtGen_DB_PROJECT_DATA': project_data_body().build('DB_PROJECT_DATA'),
            unit_key: unit_body().build('MCD_DB_UNIT')}


def write_test_project(folder):
    """Pools L and N with layer data, project data and one unit each; pool B with a broken object."""
    bodies = concat(concat(layer_data_body(), project_data_body()), unit_body())
    write_project(folder, {L_POOL: pool_objects('UNIT_L_U1'), N_POOL: pool_objects('UNIT_N_U2')},
                  bodies.ascii_strings, bodies.unicode_strings)
    broken = unit_body().build('MCD_DB_UNIT')[:6]
    write_raw_pool(folder, B_POOL, [(struct.pack('<L', support.string_hash('UNIT_B_U3', 'A')), [broken])])


def run_dump(project_folder):
    """Run app_dumpODX; return ({relative path: text}, stdout)."""
    storage = StringStorage(project_folder)
    with tempfile.TemporaryDirectory() as output_folder:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            dumpODX.app_dumpODX(storage, project_folder, output_folder)
        files = {}
        for directory, _, names in os.walk(output_folder):
            for name in names:
                path = os.path.join(directory, name)
                with open(path, encoding='utf-8') as handle:
                    files[os.path.relpath(path, output_folder).replace(os.sep, '/')] = handle.read()
    return files, stdout.getvalue()


class DumpOdxTests(unittest.TestCase):
    def setUp(self):
        self.folder_handle = tempfile.TemporaryDirectory()
        self.folder = self.folder_handle.name
        self.addCleanup(self.folder_handle.cleanup)
        write_test_project(self.folder)

    def test_writes_one_document_per_shared_data_pool(self):
        files, _ = run_dump(self.folder)
        self.assertEqual(sorted(files), ['odx/L.odx', 'odx/N.odx'])
        for name, unit_id in (('odx/L.odx', 'U1'), ('odx/N.odx', 'U2')):
            root = ET.fromstring(files[name].encode('utf-8'))
            units = root.findall('.//UNIT-SPEC/UNITS/UNIT')
            self.assertEqual([unit.get('ID') for unit in units], [unit_id])

    def test_reports_per_pool(self):
        _, stdout = run_dump(self.folder)
        lines = stdout.splitlines()
        self.assertIn('0.0.0@L.sd: unresolvable references 0, empty references 0, replaced characters 0, '
                      'DISPLAY-RADIX DEC not present 0', lines)
        skipped = [line for line in lines if line.startswith('0.0.0@B.sd: ')]
        self.assertEqual(len(skipped), 1, lines)
        self.assertTrue(skipped[0].startswith('0.0.0@B.sd: skipped, cannot be loaded: '), skipped[0])
        self.assertFalse([line for line in lines if line.startswith('0.0.0@L.sd: unused objects')], lines)
        self.assertFalse([line for line in lines if line.startswith('0.0.0@L.sd: objects without a place in ODX')],
                         lines)

    def test_reports_objects_without_place_separately(self):
        ctx = context({'DOP_L_D1': ('DB_DOP_SIMPLE_BASE', {}),
                       'TBP_L_T1.R1': ('MCD_DB_TABLE_PARAMETER', {}),
                       'TBP_L_T1.R2': ('MCD_DB_TABLE_PARAMETER', {}),
                       'UNIT_L_U1': ('MCD_DB_UNIT', {})})
        ctx.mark_without_place('TBP_L_T1.R1')
        ctx.mark_without_place('TBP_L_T1.R2')
        ctx.report['unresolvable_references'] = 2
        ctx.report['replaced_characters'] = 1
        self.assertEqual(dumpODX.report_lines(ctx), [
            '0.0.0@L.sd: unresolvable references 2, empty references 0, replaced characters 1, '
            'DISPLAY-RADIX DEC not present 0',
            '0.0.0@L.sd: unused objects DB_DOP_SIMPLE_BASE 1, MCD_DB_UNIT 1',
            '0.0.0@L.sd: objects without a place in ODX MCD_DB_TABLE_PARAMETER 2'])

    def test_main_writes_into_project_folder(self):
        with tempfile.TemporaryDirectory() as root:
            project = os.path.join(root, 'P')
            os.mkdir(project)
            write_test_project(project)
            result = subprocess.run([sys.executable, '-B', 'dumpODX.py', project, os.path.join(root, 'out')],
                                    cwd=REPOSITORY_ROOT, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(root, 'out', 'P', 'odx', 'L.odx')))
            self.assertTrue(os.path.isfile(os.path.join(root, 'out', 'P', 'odx', 'N.odx')))


class ProjectPoolsTests(unittest.TestCase):
    def setUp(self):
        self.folder_handle = tempfile.TemporaryDirectory()
        self.folder = self.folder_handle.name
        self.addCleanup(self.folder_handle.cleanup)
        write_test_project(self.folder)
        # A pool with another extension and a data file without key file are not shared data pools.
        write_raw_pool(self.folder, '0.0.0@P.cs', [(struct.pack('<L', support.string_hash('UNIT_P_U4', 'A')),
                                                    [unit_body().build('MCD_DB_UNIT')])])
        with open(os.path.join(self.folder, '0.0.0@Q.sd.db'), 'wb'):
            pass
        self.pools = ProjectPools(self.folder, StringStorage(self.folder), dumpODX.pbl_record_manager)

    def test_shared_data_pools_are_sorted_and_complete(self):
        self.assertEqual(self.pools.shared_data_pools(), [B_POOL, L_POOL, N_POOL])

    def test_context_loads_and_names_objects(self):
        ctx = self.pools.context(L_POOL)
        self.assertEqual(ctx.pool_id, L_POOL)
        self.assertEqual(set(ctx.types), {'#RtGen_DB_LAYER_DATA', '#RtGen_DB_PROJECT_DATA', 'UNIT_L_U1'})
        self.assertEqual(ctx.types['UNIT_L_U1'], 'MCD_DB_UNIT')
        self.assertEqual(ctx.objects['UNIT_L_U1']['short_name'], 'U_km')
        self.assertEqual(ctx.object_type(N_POOL, 'UNIT_N_U2'), 'MCD_DB_UNIT')

    def test_context_names_unknown_hashes_like_dump_project(self):
        unit = unit_body()
        write_raw_pool(self.folder, '0.0.0@M.sd', [(struct.pack('<L', 12345), [unit.build('MCD_DB_UNIT')])])
        ctx = self.pools.context('0.0.0@M.sd')
        self.assertEqual(list(ctx.types), ['hash 12345'])

    def test_object_type_of_missing_pool_or_object_is_none(self):
        self.assertIsNone(self.pools.object_type('0.0.0@X.sd', 'UNIT_X_U1'))
        self.assertIsNone(self.pools.object_type(N_POOL, 'UNIT_N_MISSING'))

    def test_key_name(self):
        self.assertEqual(self.pools.key_name(support.string_hash('UNIT_L_U1', 'A')), 'UNIT_L_U1')
        self.assertIsNone(self.pools.key_name(7))

    def test_strict_loading_raises(self):
        with self.assertRaises(Exception):
            self.pools.context(B_POOL)


if __name__ == '__main__':
    unittest.main()
