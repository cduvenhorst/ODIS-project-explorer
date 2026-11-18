import contextlib
import io
import os
import tempfile
import unittest

from flash_export.output import Occurrence, export
from flash_export.project_sources import (FLASH_DATA_OBJECT_ID, pool_chain_occurrences, project_file_index,
                                          resolve_external_file)


def block(name, file_name=None, sub=None, inline=None, segments=(), method=None, idents=()):
    if inline is not None:
        ref = {'kind': 'big_data_object', 'pool_id': 'A.fl', 'object_id': inline}
        stored = 'DSA_INLINE_A.flDDDSSSBBB' + inline
    else:
        ref = {'kind': 'external_file', 'file_name': file_name}
        stored = file_name
    return {'short_name': name, 'data_block_type': 'CODE', 'own_idents': list(idents),
            'flash_data': {'data_file_name_or_inline_flash_data': stored, 'data_reference': ref,
                           'flash_file_sub_directory_name': sub, 'encryption_compression_method': method},
            'flash_segments': list(segments)}


class FakeLoader:
    def __init__(self):
        self.objects = {}
        self.inline = {}

    def load_object_by_id(self, folder, pool_id, object_id):
        return self.objects[(pool_id, object_id)]

    def load_object_by_reference(self, folder, reference):
        return self.load_object_by_id(folder, reference['pool_id'], reference['object_id'])

    def load_inline_flash_data_by_id(self, folder, pool_id, object_id):
        return self.inline[(pool_id, object_id)]

    def add_chain(self, pool, blocks, ecu_mem=None, session_extra=None, name='S1'):
        self.objects[(pool, FLASH_DATA_OBJECT_ID)] = {'ecu_mem_references': [
            {'map_key': 'E', 'reference': {'pool_id': pool, 'object_id': 'EM'}}]}
        self.objects[(pool, 'EM')] = ecu_mem or {
            'has_layers': True, 'layers': [{'id_reference': 'L1'}], 'base_variants': None, 'variants': None,
            'flash_sessions': []}
        sessions = self.objects[(pool, 'EM')]['flash_sessions']
        sessions.append({'name': name, 'reference': {'pool_id': pool, 'object_id': 'S_' + name}})
        session = {'short_name': name, 'data_blocks': blocks, 'expected_idents': []}
        session.update(session_extra or {})
        self.objects[(pool, 'S_' + name)] = session


class ProjectSourcesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        for name in ('A.fl.db', 'B.bv.db'):
            open(os.path.join(self.dir, name), 'wb').close()
        self.loader = FakeLoader()

    def collect(self, notes_for=None):
        index = project_file_index(self.dir)
        args = (self.loader, self.dir, 'P1', index)
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            result = pool_chain_occurrences(*args, notes_for) if notes_for else pool_chain_occurrences(*args)
        return result

    def test_inline_block_becomes_bin_in_pool_folder(self):
        self.loader.add_chain('A.fl', [block('Drv', inline='O1')])
        self.loader.inline[('A.fl', 'O1')] = b'\x01\x02'
        occurrences, reached, errors = self.collect()
        self.assertEqual(errors, 0)
        self.assertEqual(reached, set())
        (item,) = occurrences
        self.assertEqual(item.target, 'flash/P1/A.fl/Drv.bin')
        self.assertEqual(item.read(), b'\x01\x02')
        self.assertEqual(item.session, 'S1')
        self.assertEqual(item.ecu, 'L1')
        self.assertIn('no part number in pool', item.note)
        self.assertEqual(item.source, 'A.fl')
        self.assertEqual(item.detail, 'A.fl/S1/1')

    def test_external_file_is_resolved_case_insensitively(self):
        os.makedirs(os.path.join(self.dir, 'Dev', 'flash-data'))
        with open(os.path.join(self.dir, 'Dev', 'flash-data', 'X.SGM'), 'wb') as handle:
            handle.write(b'abc')
        self.loader.add_chain('A.fl', [block('B', file_name='flash-data/x.sgm', sub='dev')])
        occurrences, reached, _ = self.collect()
        (item,) = occurrences
        self.assertEqual(item.source, 'Dev/flash-data/X.SGM')
        self.assertEqual(item.target, 'flash/P1/Dev/flash-data/X.SGM')
        self.assertEqual(item.read(), b'abc')
        self.assertIn('Dev/flash-data/X.SGM', reached)

    def test_external_block_index_counts_references_to_a_file(self):
        with open(os.path.join(self.dir, 'F.bin'), 'wb') as handle:
            handle.write(b'x')
        self.loader.add_chain('A.fl', [block('B1', file_name='F.bin'), block('B2', file_name='f.BIN')])
        occurrences, _, _ = self.collect()
        self.assertEqual(sorted(item.block_index for item in occurrences), [1, 2])

    def test_missing_and_wildcard_files_have_no_target(self):
        self.loader.add_chain('A.fl', [block('B1', file_name='gone.bin', sub='s'), block('B2', file_name='*.bin')])
        occurrences, reached, _ = self.collect()
        notes = [item.note for item in occurrences]
        self.assertIn('no part number in pool; file not found in project', notes)
        self.assertIn('no part number in pool; file not found in project (wildcard name)', notes)
        for item in occurrences:
            self.assertIsNone(item.target)
            self.assertIsNone(item.read)
        self.assertEqual(reached, set())
        self.assertEqual(sorted(item.source for item in occurrences), ['*.bin', 's/gone.bin'])

    def test_notes_for_found_file_are_appended(self):
        with open(os.path.join(self.dir, 'F.bin'), 'wb') as handle:
            handle.write(b'x')
        self.loader.add_chain('A.fl', [block('B1', file_name='F.bin')])
        occurrences, _, _ = self.collect(lambda path: ['container: %s' % path])
        self.assertEqual(occurrences[0].note, 'no part number in pool; container: F.bin')

    def test_segments_give_start_and_uncompressed_size(self):
        segments = [{'source_start_address': 0x200, 'uncompressed_size': 3},
                    {'source_start_address': 0x100, 'uncompressed_size': 4}]
        self.loader.add_chain('A.fl', [block('B', inline='O1', segments=segments)])
        (item,), _, _ = self.collect()
        self.assertEqual(item.start_address, 0x100)
        self.assertEqual(item.uncompressed_size, 7)

    def test_no_segments_leave_start_and_size_empty(self):
        self.loader.add_chain('A.fl', [block('B', inline='O1')])
        (item,), _, _ = self.collect()
        self.assertIsNone(item.start_address)
        self.assertIsNone(item.uncompressed_size)

    def test_part_number_from_idents(self):
        ident = {'short_name': 'HW', 'ident_values': [{'value': 'X1'}]}
        own = {'short_name': 'SW', 'ident_values': [{'value': 'Y2'}]}
        self.loader.add_chain('A.fl', [block('B', inline='O1', idents=[own])],
                              session_extra={'expected_idents': [ident]})
        (item,), _, _ = self.collect()
        self.assertEqual(item.part_number, 'HW=X1; SW=Y2')
        self.assertNotIn('no part number', item.note)

    def test_ecu_from_variants_without_layers(self):
        mem = {'has_layers': False, 'layers': None, 'base_variants': [{'name': 'BV'}],
               'variants': [{'name': 'EV'}], 'flash_sessions': []}
        self.loader.add_chain('A.fl', [block('B', inline='O1')], ecu_mem=mem)
        (item,), _, _ = self.collect()
        self.assertEqual(item.ecu, 'BV; EV')

    def test_method_byte_from_bytefield(self):
        method = {'data_type': 'eA_BYTEFIELD', 'value': bytearray(b'\x00')}
        self.loader.add_chain('A.fl', [block('B', inline='O1', method=method),
                                       block('C', inline='O2', method={'data_type': 'eA_UINT32', 'value': 17}),
                                       block('D', inline='O3', method={'data_type': 'eA_BYTEFIELD',
                                                                        'value': bytearray(b'\x00\x01')})])
        occurrences, _, _ = self.collect()
        by_block = {item.block: item for item in occurrences}
        self.assertEqual(by_block['B'].method, 0)
        self.assertEqual(by_block['B'].method_source, 'encryption_compression_method')
        self.assertEqual(by_block['C'].method, 17)
        self.assertIsNone(by_block['D'].method)

    def test_inline_content_reads_from_name(self):
        item_block = block('B', file_name='x')
        item_block['flash_data']['data_reference'] = {'kind': 'inline_content', 'content_length': 4}
        item_block['flash_data']['data_file_name_or_inline_flash_data'] = 'DSA_INLINE_0aFF'
        self.loader.add_chain('A.fl', [item_block])
        (item,), _, _ = self.collect()
        self.assertEqual(item.read(), b'\x0a\xff')
        self.assertEqual(item.target, 'flash/P1/A.fl/B.bin')

    def test_pool_without_flash_data_object_is_skipped(self):
        occurrences, reached, errors = self.collect()
        self.assertEqual((occurrences, reached, errors), ([], set(), 0))

    def test_failing_session_is_counted_and_others_continue(self):
        self.loader.add_chain('A.fl', [block('Bad', inline='O1')], name='S1')
        self.loader.add_chain('A.fl', [block('Good', inline='O2')], name='S2',
                              ecu_mem=self.loader.objects[('A.fl', 'EM')])
        del self.loader.objects[('A.fl', 'S_S1')]
        occurrences, _, errors = self.collect()
        self.assertEqual(errors, 1)
        self.assertEqual([item.block for item in occurrences], ['Good'])

    def test_inline_read_error_reaches_export_as_error_row(self):
        self.loader.add_chain('A.fl', [block('B', inline='O1')])

        def fail(folder, pool_id, object_id):
            raise ValueError('bad hex')
        self.loader.load_inline_flash_data_by_id = fail
        occurrences, _, _ = self.collect()
        with tempfile.TemporaryDirectory() as target, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(export(occurrences, target), 1)
            with open(os.path.join(target, 'flash', 'flash_overview.csv'), encoding='utf-8') as handle:
                self.assertIn('error: ValueError', handle.read())

    def test_lambdas_bind_their_own_block(self):
        self.loader.add_chain('A.fl', [block('B1', inline='O1'), block('B2', inline='O2')])
        self.loader.inline[('A.fl', 'O1')] = b'one'
        self.loader.inline[('A.fl', 'O2')] = b'two'
        occurrences, _, _ = self.collect()
        self.assertEqual({item.block: item.read() for item in occurrences}, {'B1': b'one', 'B2': b'two'})

    def test_resolve_external_file(self):
        index = {'a/b.bin': 'A/B.bin', 'c.bin': 'C.bin'}
        self.assertEqual(resolve_external_file(index, 'a', 'b.bin'), 'A/B.bin')
        self.assertEqual(resolve_external_file(index, 'A\\', 'B.BIN'), 'A/B.bin')
        self.assertEqual(resolve_external_file(index, None, 'c.bin'), 'C.bin')
        self.assertEqual(resolve_external_file(index, '', 'c.bin'), 'C.bin')
        self.assertIsNone(resolve_external_file(index, 'a', 'x.bin'))

    def test_project_file_index_lists_every_file(self):
        os.makedirs(os.path.join(self.dir, 'Sub'))
        open(os.path.join(self.dir, 'Sub', 'File.X'), 'wb').close()
        index = project_file_index(self.dir)
        self.assertEqual(index['sub/file.x'], 'Sub/File.X')
        self.assertEqual(index['a.fl.db'], 'A.fl.db')


if __name__ == '__main__':
    unittest.main()
