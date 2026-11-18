import contextlib
import csv
import io
import os
import tempfile
import unittest

from flash_export.output import export, overview_path
from flash_export.workspace_sources import (
    DocumentCache, loose_odx_occurrences, pdx_occurrences, platforms_for_project, read_platform_mapping,
    workspace_platforms)
from tests.flash_workspace_support import (
    DocBlock, flash_folder, odx_flash_document, write_file, write_loose_odx, write_pdx, write_zip)


def overview(target):
    with open(overview_path(target), encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


class WorkspaceSourcesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = os.path.join(self._tmp.name, 'ws')
        self.out = os.path.join(self._tmp.name, 'out')
        os.makedirs(self.ws)

    def mixed_pdx(self, platform='pa', name='K1.pdx'):
        return write_pdx(self.ws, platform, name, [
            DocBlock('ext', flash_name='FD1', datafile='a b+.bin', method='A0'),
            DocBlock('emb', flash_name='FD2', data=b'\x01\x02\x03')],
            payloads={'a b+.bin': b'EXTERNAL'}, document_entry='k1.odx')

    def test_workspace_platforms_need_flash_data_or_mcr_data(self):
        os.makedirs(os.path.join(self.ws, 'pa', 'flash-data', 'flash-data'))
        os.makedirs(os.path.join(self.ws, 'pb', 'mcr-data'))
        write_file(os.path.join(self.ws, 'pc', 'x.jpg'), b'x')
        write_file(os.path.join(self.ws, 'loose.txt'), b'x')
        self.assertEqual(['pa', 'pb'], workspace_platforms(self.ws))

    def test_mapping_matches_whole_project_name(self):
        write_file(os.path.join(self.ws, 'mapping.properties'),
                   b'# comment\n\npidt-vehicle-platform.pa=[Pp][Aa].*\npidt-vehicle-platform.pz=Z.*\n')
        mapping = read_platform_mapping(self.ws)
        self.assertEqual([('pa', '[Pp][Aa].*'), ('pz', 'Z.*')], mapping)
        self.assertEqual(['pa'], platforms_for_project(mapping, 'PA1', ['pa', 'pb']))
        self.assertEqual([], platforms_for_project(mapping, 'XPA', ['pa', 'pb']))
        self.assertEqual([], platforms_for_project(mapping, 'Z1', ['pa', 'pb']))

    def test_invalid_mapping_expression_raises(self):
        with self.assertRaises(ValueError) as caught:
            platforms_for_project([('pa', '[Pp')], 'PA1', ['pa'])
        self.assertIn('invalid regular expression for pa in mapping.properties', str(caught.exception))

    def test_mapping_file_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_platform_mapping(self.ws)

    def test_pdx_extern_and_intern_blocks(self):
        self.mixed_pdx()
        occurrences, errors = pdx_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(0, errors)
        self.assertEqual(2, len(occurrences))
        ext, emb = occurrences
        self.assertEqual('flash/workspace/K1/a b+.bin', ext.target)
        self.assertEqual('flash/workspace/K1/FD2.bin', emb.target)
        for item in occurrences:
            self.assertEqual('pa/flash-data/flash-data/K1.pdx/k1.odx', item.source)
            self.assertEqual(('workspace', 'pa', 1), (item.origin_kind, item.origin, item.source_rank))
            self.assertEqual('ENCRYPT-COMPRESS-METHOD', item.method_source)
        self.assertEqual(('k1.odx/1', 'ecu-a', 'PN-1', 'S1', 'ext', 'CODE', 0x1000, 16, 0xA0, ''),
                         (ext.detail, ext.ecu, ext.part_number, ext.session, ext.block, ext.block_type,
                          ext.start_address, ext.uncompressed_size, ext.method, ext.note))
        self.assertEqual(b'EXTERNAL', ext.read())
        self.assertEqual(b'\x01\x02\x03', emb.read())

    def test_external_file_missing_in_package(self):
        write_pdx(self.ws, 'pa', 'K1.pdx', [DocBlock('ext', datafile='gone.bin')])
        (item,), errors = pdx_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(0, errors)
        self.assertIsNone(item.target)
        self.assertIn('file not found in package', item.note)

    def test_same_pdx_in_two_platforms_is_written_once(self):
        self.mixed_pdx('pa')
        self.mixed_pdx('pb')
        cache = DocumentCache()
        occurrences = pdx_occurrences(self.ws, 'pa', cache)[0] + pdx_occurrences(self.ws, 'pb', cache)[0]
        self.assertEqual(0, export(occurrences, self.out))
        with open(os.path.join(self.out, 'flash', 'workspace', 'K1', 'a b+.bin'), 'rb') as handle:
            self.assertEqual(b'EXTERNAL', handle.read())
        self.assertEqual(['K1'], os.listdir(os.path.join(self.out, 'flash', 'workspace')))
        self.assertEqual(['FD2.bin', 'a b+.bin'], sorted(os.listdir(os.path.join(self.out, 'flash', 'workspace', 'K1'))))
        rows = overview(self.out)
        self.assertEqual({('pa', 'no'), ('pb', 'yes')}, {(r['origin'], r['duplicate']) for r in rows})

    def test_loose_odx_is_decoded_once_across_both_passes(self):
        write_loose_odx(self.ws, 'pa', 'L1.odx', [
            DocBlock('b1', flash_name='X1', data=b'one'), DocBlock('b2', flash_name='X2', data=b'two'),
            DocBlock('b3', flash_name='X3', data=b'three')])
        cache = DocumentCache()
        occurrences, errors = loose_odx_occurrences(self.ws, 'pa', cache)
        self.assertEqual(0, errors)
        self.assertEqual('pa/flash-data/flash-data/L1.odx', occurrences[0].source)
        self.assertEqual(0, export(occurrences, self.out))
        self.assertEqual(['X1.bin', 'X2.bin', 'X3.bin'],
                         sorted(os.listdir(os.path.join(self.out, 'flash', 'workspace', 'L1'))))
        # the decoded document stays cached across both export passes, so it is decoded exactly once
        self.assertEqual(1, cache.reads())

    def test_cache_keeps_only_the_latest_document(self):
        cache = DocumentCache()
        cache.get(('a',), lambda: {'x': b'1'})
        cache.get(('b',), lambda: {'x': b'2'})
        cache.get(('a',), lambda: {'x': b'1'})
        self.assertEqual(3, cache.reads())

    def test_block_without_flash_data_has_note(self):
        write_loose_odx(self.ws, 'pa', 'L1.odx', [DocBlock('b1')])
        (item,), _ = loose_odx_occurrences(self.ws, 'pa', DocumentCache())
        self.assertIsNone(item.target)
        self.assertIn('no flash data in document', item.note)

    def test_missing_part_number_note(self):
        write_loose_odx(self.ws, 'pa', 'L1.odx', [DocBlock('b1', data=b'x', part_number=None)])
        (item,), _ = loose_odx_occurrences(self.ws, 'pa', DocumentCache())
        self.assertIn('no part number in document', item.note)
        self.assertEqual('', item.part_number)

    def test_broken_pdx_is_an_error_row(self):
        write_file(os.path.join(flash_folder(self.ws, 'pa'), 'Bad.pdx'), b'not a zip')
        self.mixed_pdx()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            occurrences, errors = pdx_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(1, errors)
        bad = [o for o in occurrences if o.detail == 'Bad.pdx']
        self.assertEqual(1, len(bad))
        self.assertEqual(0, bad[0].block_index)
        self.assertIsNone(bad[0].target)
        self.assertTrue(bad[0].note.startswith('error: BadZipFile: '))
        self.assertEqual(3, len(occurrences))
        self.assertIn('Bad.pdx', stderr.getvalue())

    def test_pdx_without_flash_document_is_an_error_row(self):
        write_zip(os.path.join(flash_folder(self.ws, 'pa'), 'Empty.pdx'), {'index.xml': b'<index/>'})
        with contextlib.redirect_stderr(io.StringIO()):
            (item,), errors = pdx_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(1, errors)
        self.assertEqual('Empty.pdx', item.detail)
        self.assertTrue(item.note.startswith('error: '))

    def test_malformed_document_is_an_error_row(self):
        write_zip(os.path.join(flash_folder(self.ws, 'pa'), 'Bad.pdx'), {'d.odx': b'<ODX><FLASH></ODX>'})
        write_file(os.path.join(flash_folder(self.ws, 'pa'), 'Bad2.odx'), b'<ODX><FLASH>')
        with contextlib.redirect_stderr(io.StringIO()):
            pdx, e1 = pdx_occurrences(self.ws, 'pa', DocumentCache())
            loose, e2 = loose_odx_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual((1, 1), (e1, e2))
        self.assertTrue(pdx[0].note.startswith('error: ParseError'))
        self.assertTrue(loose[0].note.startswith('error: ParseError'))

    def test_extensions_and_folders_ignore_case(self):
        path = os.path.join(self.ws, 'pa', 'Flash-Data', 'FLASH-DATA')
        write_file(os.path.join(path, 'L1.ODX'), odx_flash_document([DocBlock('b1', data=b'x')]))
        self.assertEqual(['pa'], workspace_platforms(self.ws))
        (item,), errors = loose_odx_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(0, errors)
        self.assertEqual('pa/Flash-Data/FLASH-DATA/L1.ODX', item.source)
        self.assertEqual('flash/workspace/L1/b1.bin', item.target)


if __name__ == '__main__':
    unittest.main()
