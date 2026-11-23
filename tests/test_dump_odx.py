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
from collections import Counter

import dumpODX
from classes.StringStorage import StringStorage
from odx_export.elements import identified
from odx_export.pool_source import ProjectPools, resolve_unpooled_references
from tests import support
from tests.odx_support import context
from tests.support import REPOSITORY_ROOT, ObjectBytes, concat, unit_body, write_project, write_raw_pool
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


def named_layer_body(layer_id, name):
    """layer_data_body() with the given layer ID and layer name."""
    body = layer_data_body()
    named = ObjectBytes().ascii(layer_id).ascii(name)
    # The first eight bytes of layer_data_body() are the two string hashes replaced here.
    named = concat(named, ObjectBytes().raw(body._data[8:]))
    named.ascii_strings += body.ascii_strings[2:]
    named.unicode_strings += body.unicode_strings
    return named


def write_layer_project(folder):
    """Layer pools B (base variant B, variant V1, one broken unit) and D (D, V2, one unit), one pool each
    of E.ev, G.fg, P.pr, L.sd and C.cs, and a data file of an F.fg without key file."""
    layers = {name: named_layer_body('ID_' + name, name) for name in ('B', 'V1', 'D', 'V2', 'E', 'G', 'P', 'L', 'C')}
    bodies = unit_body()
    for body in layers.values():
        bodies = concat(bodies, body)

    def layer_pool(name, extra=None):
        objects = {'#RtGen_DB_LAYER_DATA': layers[name].build('DB_LAYER_DATA')}
        objects.update(extra or {})
        return objects

    broken = unit_body().build('MCD_DB_UNIT')[:6]
    write_project(folder, {
        '0.0.0@B.bv': layer_pool('B', {'LD_V1': layers['V1'].build('DB_LAYER_DATA'), 'UNIT_V1_U1': broken}),
        '0.0.0@D.bv': layer_pool('D', {'LD_V2': layers['V2'].build('DB_LAYER_DATA'),
                                       'UNIT_V2_U1': unit_body().build('MCD_DB_UNIT')}),
        '0.0.0@E.ev': layer_pool('E'), '0.0.0@G.fg': layer_pool('G'), '0.0.0@P.pr': layer_pool('P'),
        '0.0.0@L.sd': layer_pool('L'), '0.0.0@C.cs': layer_pool('C')},
        bodies.ascii_strings, bodies.unicode_strings)
    with open(os.path.join(folder, '0.0.0@F.fg.db'), 'wb'):
        pass


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
        self.assertIn('0.0.0@L.sd: unresolvable references 0, empty references 0, replaced characters 0', lines)
        skipped = [line for line in lines if line.startswith('0.0.0@B.sd: ')]
        self.assertEqual(len(skipped), 1, lines)
        self.assertTrue(skipped[0].startswith('0.0.0@B.sd: skipped, cannot be loaded: '), skipped[0])
        self.assertFalse([line for line in lines if line.startswith('0.0.0@L.sd: unused objects')], lines)
        self.assertFalse([line for line in lines if line.startswith('0.0.0@L.sd: objects without a place in ODX')],
                         lines)

    def test_skipped_pool_prints_traceback_to_stderr(self):
        storage = StringStorage(self.folder)
        with tempfile.TemporaryDirectory() as output_folder:
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                dumpODX.app_dumpODX(storage, self.folder, output_folder)
        skipped = [line for line in stdout.getvalue().splitlines() if line.startswith('0.0.0@B.sd: ')]
        self.assertEqual(len(skipped), 1, stdout.getvalue())
        self.assertIn('Traceback (most recent call last)', stderr.getvalue())

    def test_skipped_pool_removes_output_of_an_earlier_run(self):
        storage = StringStorage(self.folder)
        with tempfile.TemporaryDirectory() as output_folder:
            odx_folder = os.path.join(output_folder, 'odx')
            os.makedirs(odx_folder)
            stale = os.path.join(odx_folder, 'B.odx')
            with open(stale, 'w') as handle:
                handle.write('stale')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                dumpODX.app_dumpODX(storage, self.folder, output_folder)
            self.assertFalse(os.path.exists(stale))
            self.assertTrue(os.path.isfile(os.path.join(odx_folder, 'L.odx')))

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
            '0.0.0@L.sd: unresolvable references 2, empty references 0, replaced characters 1',
            '0.0.0@L.sd: unused objects DB_DOP_SIMPLE_BASE 1, MCD_DB_UNIT 1',
            '0.0.0@L.sd: objects without a place in ODX MCD_DB_TABLE_PARAMETER 2'])

    def test_reports_each_duplicate_id(self):
        ctx = context({}, pool_id='0.0.0@B.bv', pool_layers=['B', 'V1'])
        view = ctx.for_layer('V1')
        for tag in ('REQUEST', 'POS-RESPONSE'):
            identified(view, ET.Element('X'), tag, 'X', {})
        self.assertEqual(dumpODX.report_lines(ctx), [
            '0.0.0@B.bv: unresolvable references 0, empty references 0, replaced characters 0',
            '0.0.0@B.bv: other counters duplicate_ids 1',
            '0.0.0@B.bv: duplicate ID X in layer V1 (POS-RESPONSE)'])

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


BV_POOL = '0.0.0@B.bv'
FG_POOL = '0.0.0@G.fg'
PR_POOL = '0.0.0@P.pr'
LOCATIONS = {'base variant': 0x0101, 'variant': 0x0102, 'functional group': 0x0103, 'protocol': 0x0105}


def located_layer_body(layer_id, name, location, target=None, parents=(), spec_pool=None):
    """DB_LAYER_DATA with location type, layer object reference and parent pools; all lists empty otherwise."""
    body = ObjectBytes().ascii(layer_id).ascii(name).ascii(None).ascii('STACK_' + name).ascii(spec_pool)
    body.u16(LOCATIONS[location])
    if target is not None:
        body.ascii(target).ascii(None)
    # The rest of layer_data_body() after its 22 header bytes (five string hashes and the location type);
    # in it, the twelve 16 bit counts before the parent pools (24 bytes), then the parent pool count.
    rest = layer_data_body()._data[22:]
    body.raw(rest[:24]).u16(len(parents))
    for pool_id in parents:
        body.ascii(pool_id)
    return body.raw(rest[26:])


def ecu_tail_body(body, name):
    """The name block of MCD_DB_ECU: short name, no texts, an OID, no text IDs, no locations."""
    return body.ascii(name).unicode(None).unicode(None).ascii('OID-' + name).ascii(None).ascii(None).u16(0)


def write_layers_project(folder, with_layer_pools=True):
    """Pool L.sd; with layer pools also B.bv (base variant B, variants V1 and V2), P.pr, G.fg, C.cs and a
    K.bv with a broken unit."""
    pool_layer = '#RtGen_DB_LAYER_DATA'
    project = project_data_body()
    bodies = {
        '0.0.0@L.sd': {pool_layer: named_layer_body('ESD_L', 'L'), '#RtGen_DB_PROJECT_DATA': project},
    }
    if with_layer_pools:
        bodies[BV_POOL] = {
            pool_layer: located_layer_body('BV_B', 'B', 'base variant', 'B', parents=('0.0.0@L.sd', FG_POOL)),
            'LD_V1': located_layer_body('EV_V1_ID', 'V1', 'variant', 'EV_V1', parents=(BV_POOL,)),
            'LD_V2': located_layer_body('EV_V2_ID', 'V2', 'variant', 'EV_V2', parents=(BV_POOL,)),
            'B': ecu_tail_body(ObjectBytes().u16(0).u16(0), 'B'),
            'EV_V1': ecu_tail_body(ObjectBytes().ascii('B').ascii(BV_POOL).absent(), 'V1'),
            'EV_V2': ecu_tail_body(ObjectBytes().ascii('B').ascii(BV_POOL).absent(), 'V2'),
            '#RtGen_DB_PROJECT_DATA': project}
        bodies[PR_POOL] = {pool_layer: located_layer_body('PROT_P', 'P', 'protocol', spec_pool='0.0.0@SPEC.cp'),
                           '#RtGen_DB_PROJECT_DATA': project}
        bodies[FG_POOL] = {
            pool_layer: located_layer_body('FG_G', 'G', 'functional group', 'DLC_G', parents=(PR_POOL,)),
            'DLC_G': ecu_tail_body(ObjectBytes().u16(1).ascii('B').ascii('B').ascii(BV_POOL), 'G'),
            '#RtGen_DB_PROJECT_DATA': project}
        bodies['0.0.0@C.cs'] = {pool_layer: named_layer_body('CS_C', 'C'), '#RtGen_DB_PROJECT_DATA': project}
        bodies['0.0.0@K.bv'] = {pool_layer: located_layer_body('BV_K', 'K', 'base variant', 'K'),
                                '#RtGen_DB_PROJECT_DATA': project}
    types = {'B': 'MCD_DB_ECU_BASE_VARIANT', 'EV_V1': 'MCD_DB_ECU_VARIANT', 'EV_V2': 'MCD_DB_ECU_VARIANT',
             'DLC_G': 'MCD_DB_FUNCTIONAL_GROUP', '#RtGen_DB_PROJECT_DATA': 'DB_PROJECT_DATA'}
    strings = ObjectBytes()
    pools = {}
    for pool_id, objects in bodies.items():
        pools[pool_id] = {}
        for key, body in objects.items():
            strings = concat(strings, body)
            pools[pool_id][key] = body.build(types.get(key, 'DB_LAYER_DATA'))
    if with_layer_pools:
        pools['0.0.0@K.bv']['UNIT_K_U1'] = unit_body().build('MCD_DB_UNIT')[:6]
    write_project(folder, pools, strings.ascii_strings, strings.unicode_strings)


class DumpLayerPoolTests(unittest.TestCase):
    def setUp(self):
        self.folder_handle = tempfile.TemporaryDirectory()
        self.folder = self.folder_handle.name
        self.addCleanup(self.folder_handle.cleanup)
        write_layers_project(self.folder)

    def test_writes_documents_for_layer_pools(self):
        files, stdout = run_dump(self.folder)
        self.assertEqual(sorted(files), ['odx/B.odx', 'odx/G.odx', 'odx/L.odx', 'odx/P.odx'])
        self.assertTrue(files['odx/B.odx'].startswith(
            '<?xml version="1.0" encoding="UTF-8"?>\n<!-- Reconstructed by ODIS-project-explorer from pool '
            '0.0.0@B.bv: '), files['odx/B.odx'][:200])
        container = ET.fromstring(files['odx/B.odx'].encode('utf-8')).find('DIAG-LAYER-CONTAINER')
        self.assertEqual([child.tag for child in container], ['SHORT-NAME', 'BASE-VARIANTS', 'ECU-VARIANTS'])
        base, = container.find('BASE-VARIANTS')
        self.assertEqual(base.attrib, {'ID': 'BV_B', 'OID': 'OID-B'})
        self.assertEqual([(ref.get('ID-REF'), ref.get('DOCREF')) for ref in base.findall('PARENT-REFS/PARENT-REF')],
                         [('ESD_L', 'L'), ('FG_G', 'G')])
        variants = container.find('ECU-VARIANTS')
        self.assertEqual([variant.get('ID') for variant in variants], ['EV_V1_ID', 'EV_V2_ID'])
        for variant in variants:
            ref, = variant.findall('PARENT-REFS/PARENT-REF')
            self.assertEqual((ref.get('ID-REF'), ref.get('DOCREF')), ('BV_B', 'B'))
        protocol = ET.fromstring(files['odx/P.odx'].encode('utf-8')).find('DIAG-LAYER-CONTAINER/PROTOCOLS/PROTOCOL')
        self.assertEqual([child.tag for child in protocol], ['SHORT-NAME', 'COMPARAM-SPEC-REF', 'PROT-STACK-SNREF'])
        group = ET.fromstring(files['odx/G.odx'].encode('utf-8')).find(
            'DIAG-LAYER-CONTAINER/FUNCTIONAL-GROUPS/FUNCTIONAL-GROUP')
        self.assertEqual(group.attrib, {'ID': 'FG_G', 'OID': 'OID-G'})
        lines = stdout.splitlines()
        for pool_id in (BV_POOL, FG_POOL, PR_POOL):
            self.assertIn(pool_id + ': unresolvable references 0, empty references 0, replaced characters 0', lines)
            self.assertFalse([line for line in lines if line.startswith(pool_id + ': ')
                              and not line.startswith(pool_id + ': unresolvable')], lines)
        # Shared data pools come first, then the layer pools.
        self.assertLess(lines.index('0.0.0@L.sd: unresolvable references 0, empty references 0, '
                                    'replaced characters 0'),
                        lines.index(BV_POOL + ': unresolvable references 0, empty references 0, '
                                              'replaced characters 0'))

    def test_broken_layer_pool_is_skipped_others_written(self):
        storage = StringStorage(self.folder)
        with tempfile.TemporaryDirectory() as output_folder:
            odx_folder = os.path.join(output_folder, 'odx')
            os.makedirs(odx_folder)
            stale = os.path.join(odx_folder, 'K.odx')
            with open(stale, 'w') as handle:
                handle.write('stale')
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                dumpODX.app_dumpODX(storage, self.folder, output_folder)
            self.assertFalse(os.path.exists(stale))
            self.assertEqual(sorted(os.listdir(odx_folder)), ['B.odx', 'G.odx', 'L.odx', 'P.odx'])
        skipped = [line for line in stdout.getvalue().splitlines() if line.startswith('0.0.0@K.bv: ')]
        self.assertEqual(len(skipped), 1, stdout.getvalue())
        self.assertTrue(skipped[0].startswith('0.0.0@K.bv: skipped, cannot be loaded: '), skipped[0])

    def test_shared_data_output_is_unchanged_by_layer_pools(self):
        files, stdout = run_dump(self.folder)
        with tempfile.TemporaryDirectory() as alone:
            write_layers_project(alone, with_layer_pools=False)
            alone_files, alone_stdout = run_dump(alone)
        self.assertEqual(sorted(alone_files), ['odx/L.odx'])
        self.assertEqual(files['odx/L.odx'], alone_files['odx/L.odx'])
        sd_lines = [line for line in stdout.splitlines() if line.startswith('0.0.0@L.sd: ')]
        self.assertEqual(sd_lines, alone_stdout.splitlines())

    def test_other_counters_are_reported_in_one_line(self):
        ctx = context({'UNIT_L_U1': ('MCD_DB_UNIT', {})})
        ctx.report['unresolvable_references'] = 1
        ctx.report['layer_object_missing'] = 2
        ctx.report['comparam_without_subset'] = 1
        ctx.report['base_variant_pattern_mismatch'] = 0
        ctx.mark_without_place('UNIT_L_U1')
        self.assertEqual(dumpODX.report_lines(ctx), [
            '0.0.0@L.sd: unresolvable references 1, empty references 0, replaced characters 0',
            '0.0.0@L.sd: other counters comparam_without_subset 1, layer_object_missing 2',
            '0.0.0@L.sd: objects without a place in ODX MCD_DB_UNIT 1'])


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

    def layer_pools(self):
        folder_handle = tempfile.TemporaryDirectory()
        self.addCleanup(folder_handle.cleanup)
        write_layer_project(folder_handle.name)
        return ProjectPools(folder_handle.name, StringStorage(folder_handle.name), dumpODX.pbl_record_manager)

    def test_layer_pools_sorted_by_extension_set(self):
        self.assertEqual(self.layer_pools().layer_pools(),
                         ['0.0.0@B.bv', '0.0.0@D.bv', '0.0.0@E.ev', '0.0.0@G.fg', '0.0.0@P.pr'])
        self.assertEqual(self.pools.layer_pools(), [])

    def test_layers_lists_layer_data_without_loading_other_objects(self):
        pools = self.layer_pools()
        # Pool B holds a broken unit, so loading all of its objects fails.
        with self.assertRaises(Exception):
            pools.context('0.0.0@B.bv')
        layers = pools.layers('0.0.0@B.bv')
        self.assertEqual(sorted(layers, key=lambda layer: layer['key']), [
            {'key': '#RtGen_DB_LAYER_DATA', 'layer_name': 'B', 'layer_id': 'ID_B',
             'location_type': 'eMULTIPLE_ECU_JOB', 'parent_layers': []},
            {'key': 'LD_V1', 'layer_name': 'V1', 'layer_id': 'ID_V1',
             'location_type': 'eMULTIPLE_ECU_JOB', 'parent_layers': []}])
        self.assertIs(pools.layers('0.0.0@B.bv'), layers)
        self.assertEqual(pools.layers('0.0.0@X.bv'), [])
        self.assertEqual(pools.layers('0.0.0@F.fg'), [])

    def test_broken_layer_object_of_another_pool_falls_back_to_pool_layer_name(self):
        folder_handle = tempfile.TemporaryDirectory()
        self.addCleanup(folder_handle.cleanup)
        write_layer_project(folder_handle.name)
        broken = named_layer_body('ID_K', 'K').build('DB_LAYER_DATA')[:6]
        write_raw_pool(folder_handle.name, '0.0.0@K.bv',
                       [(struct.pack('<L', support.string_hash('#RtGen_DB_LAYER_DATA', 'A')), [broken])])
        pools = ProjectPools(folder_handle.name, StringStorage(folder_handle.name), dumpODX.pbl_record_manager)
        with self.assertRaises(Exception):
            pools.layers('0.0.0@K.bv')
        ctx = pools.context('0.0.0@D.bv')
        self.assertEqual(ctx.foreign_layers('0.0.0@K.bv'), ['K'])

    def test_context_sets_pool_layers(self):
        pools = self.layer_pools()
        # Read from the type map before the context loads the whole pool
        layers = list(pools.layers('0.0.0@D.bv'))
        ctx = pools.context('0.0.0@D.bv')
        self.assertEqual(sorted(ctx.pool_layers), ['D', 'V2'])
        # Pool order: the order in which the context holds the layer objects.
        self.assertEqual([layer['key'] for layer in layers],
                         [key for key, type_name in ctx.types.items() if type_name == 'DB_LAYER_DATA'])
        self.assertEqual(ctx.pool_layers, [layer['layer_name'] for layer in layers])
        self.assertEqual(pools.layers('0.0.0@D.bv'), layers)
        self.assertEqual(ctx.layer, 'D')
        self.assertEqual(sorted(ctx.foreign_layers('0.0.0@B.bv')), ['B', 'V1'])
        self.assertEqual(ctx.foreign_layers('0.0.0@L.sd'), ['L'])
        self.assertEqual(ctx.foreign_layers('0.0.0@X.sd'), ['X'])
        self.assertEqual(ctx.target_layer('0.0.0@B.bv', 'UNIT_V1_U1'), 'V1')

    def test_strict_loading_raises(self):
        with self.assertRaises(Exception):
            self.pools.context(B_POOL)


EV_POOL = '0.0.0@E.ev'


def variant_reference_body(object_id, pool_id=None, name='V'):
    """MCD_DB_ECU_VARIANT whose base variant reference is (object_id, pool_id)."""
    return ecu_tail_body(ObjectBytes().ascii(object_id).ascii(pool_id).absent(), name)


def write_variant_pool_project(folder):
    """Variant pool E.ev with parent B.bv, whose base variant has the parent P.pr, and a shared data pool L.sd.

    Each ECU variant object holds one reference; the units are the targets."""
    pool_layer = '#RtGen_DB_LAYER_DATA'
    bodies = {
        PR_POOL: {pool_layer: located_layer_body('PROT_P', 'P', 'protocol'),
                  'UNIT_P_U1': unit_body(), 'UNIT_P_U2': unit_body()},
        BV_POOL: {pool_layer: located_layer_body('BV_B', 'B', 'base variant', 'B', parents=(PR_POOL,)),
                  'UNIT_B_U1': unit_body(), 'UNIT_P_U2': unit_body(), 'UNIT_E_U1': unit_body(),
                  'EV_KEEP': variant_reference_body('UNIT_B_U1')},
        EV_POOL: {pool_layer: located_layer_body('EV_E_ID', 'E', 'variant', 'EV_E', parents=(BV_POOL,)),
                  'UNIT_E_U1': unit_body(), 'EV_E': variant_reference_body('B', BV_POOL, 'E'),
                  'EV_OWN': variant_reference_body('UNIT_E_U1'),
                  'EV_PARENT': variant_reference_body('UNIT_B_U1'),
                  'EV_GRANDPARENT': variant_reference_body('UNIT_P_U1'),
                  'EV_NEAREST': variant_reference_body('UNIT_P_U2'),
                  'EV_SHORT_NAME': variant_reference_body('SomeShortName'),
                  'EV_POOLED': variant_reference_body('UNIT_P_U1', PR_POOL)},
        L_POOL: {pool_layer: named_layer_body('ESD_L', 'L'), 'UNIT_L_U1': unit_body(),
                 'EV_SHARED': variant_reference_body('UNIT_L_U1')},
    }
    strings = ObjectBytes()
    pools = {}
    for pool_id, objects in bodies.items():
        pools[pool_id] = {}
        for key, body in objects.items():
            strings = concat(strings, body)
            type_name = ('MCD_DB_UNIT' if key.startswith('UNIT_') else 'MCD_DB_ECU_VARIANT'
                         if key.startswith('EV_') else 'DB_LAYER_DATA')
            pools[pool_id][key] = body.build(type_name)
    write_project(folder, pools, strings.ascii_strings, strings.unicode_strings)


class VariantPoolReferenceTests(unittest.TestCase):
    def setUp(self):
        folder_handle = tempfile.TemporaryDirectory()
        self.addCleanup(folder_handle.cleanup)
        write_variant_pool_project(folder_handle.name)
        self.pools = ProjectPools(folder_handle.name, StringStorage(folder_handle.name), dumpODX.pbl_record_manager)

    def reference(self, ctx, key):
        reference = ctx.objects[key]['ecu_base_variant_reference']
        return reference['object_id'], reference['pool_id']

    def test_ev_unpooled_reference_to_own_object_gets_own_pool(self):
        ctx = self.pools.context(EV_POOL)
        # The own pool comes before the parent B.bv, which has an object of the same name.
        self.assertEqual(self.reference(ctx, 'EV_OWN'), ('UNIT_E_U1', EV_POOL))

    def test_ev_unpooled_reference_to_parent_object_gets_parent_pool(self):
        ctx = self.pools.context(EV_POOL)
        self.assertEqual(self.reference(ctx, 'EV_PARENT'), ('UNIT_B_U1', BV_POOL))
        self.assertEqual(self.reference(ctx, 'EV_GRANDPARENT'), ('UNIT_P_U1', PR_POOL))
        # Breadth first: the parent B.bv comes before its own parent P.pr.
        self.assertEqual(self.reference(ctx, 'EV_NEAREST'), ('UNIT_P_U2', BV_POOL))
        self.assertEqual(self.reference(ctx, 'EV_POOLED'), ('UNIT_P_U1', PR_POOL))
        self.assertEqual(ctx.report['unpooled_references_resolved_to_parent'], 3)

    def test_ev_unpooled_short_name_stays_unpooled(self):
        ctx = self.pools.context(EV_POOL)
        self.assertEqual(self.reference(ctx, 'EV_SHORT_NAME'), ('SomeShortName', None))
        self.assertEqual(ctx.report['unpooled_references_unresolved'], 1)

    def test_broken_parent_layer_object_ends_the_chain(self):
        folder_handle = tempfile.TemporaryDirectory()
        self.addCleanup(folder_handle.cleanup)
        write_variant_pool_project(folder_handle.name)
        broken = named_layer_body('BV_B', 'B').build('DB_LAYER_DATA')[:6]
        for extension in ('.key', '.db'):
            os.remove(os.path.join(folder_handle.name, BV_POOL + extension))
        write_raw_pool(folder_handle.name, BV_POOL,
                       [(struct.pack('<L', support.string_hash('#RtGen_DB_LAYER_DATA', 'A')), [broken])])
        pools = ProjectPools(folder_handle.name, StringStorage(folder_handle.name), dumpODX.pbl_record_manager)
        ctx = pools.context(EV_POOL)
        self.assertEqual(self.reference(ctx, 'EV_OWN'), ('UNIT_E_U1', EV_POOL))
        self.assertEqual(self.reference(ctx, 'EV_GRANDPARENT'), ('UNIT_P_U1', None))

    def test_other_pools_keep_unpooled_references(self):
        base = self.pools.context(BV_POOL)
        self.assertEqual(self.reference(base, 'EV_KEEP'), ('UNIT_B_U1', None))
        shared = self.pools.context(L_POOL)
        self.assertEqual(self.reference(shared, 'EV_SHARED'), ('UNIT_L_U1', None))
        for ctx in (base, shared):
            self.assertEqual(ctx.report['unpooled_references_resolved_to_parent'], 0)
            self.assertEqual(ctx.report['unpooled_references_unresolved'], 0)


class ResolveUnpooledReferencesTests(unittest.TestCase):
    def test_references_at_any_depth_are_resolved(self):
        obj = {'reference': {'object_id': 'A', 'pool_id': None},
               'entries': [{'name': 'N', 'reference': {'object_id': 'B', 'pool_id': None}},
                           [{'object_id': 'C', 'pool_id': None, 'attributes': []}]],
               'empty': {'object_id': '', 'pool_id': None},
               'pooled': {'object_id': 'A', 'pool_id': 'X.bv'}}
        pools = {'A': 'own.ev', 'B': 'parent.bv'}
        counts = resolve_unpooled_references(obj, pools.get)
        self.assertEqual(obj['reference'], {'object_id': 'A', 'pool_id': 'own.ev'})
        self.assertEqual(obj['entries'][0]['reference'], {'object_id': 'B', 'pool_id': 'parent.bv'})
        self.assertEqual(obj['entries'][1][0], {'object_id': 'C', 'pool_id': None, 'attributes': []})
        self.assertEqual(obj['empty'], {'object_id': '', 'pool_id': None})
        self.assertEqual(obj['pooled'], {'object_id': 'A', 'pool_id': 'X.bv'})
        # Per pool the number of references resolved into it; None counts the unresolved ones.
        self.assertEqual(counts, Counter({'own.ev': 1, 'parent.bv': 1, None: 1}))


if __name__ == '__main__':
    unittest.main()
