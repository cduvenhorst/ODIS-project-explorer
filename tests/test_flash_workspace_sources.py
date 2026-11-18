import contextlib
import csv
import io
import os
import tempfile
import unittest

from flash_export.output import export, overview_path
from flash_export.workspace_sources import (
    DocumentCache, loose_odx_occurrences, pcc_occurrences, pdx_occurrences, platforms_for_project,
    read_platform_mapping, workspace_occurrences, workspace_platforms)
from tests.flash_workspace_support import (
    DocBlock, flash_folder, odx_flash_document, sw_cnt_areas_xml, write_file, write_loose_odx, write_pcc,
    write_pdx, write_zip)


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


class PccTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = os.path.join(self._tmp.name, 'ws')
        self.out = os.path.join(self._tmp.name, 'out')
        os.makedirs(self.ws)

    def read_target(self, *parts):
        with open(os.path.join(self.out, *parts), 'rb') as handle:
            return handle.read()

    def test_dsdl_documents_get_a_folder_per_entry(self):
        write_pcc(self.ws, 'pa', 'P1.pcc', {
            'A.odx': odx_flash_document([DocBlock('b', flash_name='FD1', data=b'aaa')]),
            'B.odx': odx_flash_document([DocBlock('b', flash_name='FD1', data=b'bbb')])})
        occurrences, errors = pcc_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(0, errors)
        self.assertEqual(['flash/workspace/P1/A/FD1.bin', 'flash/workspace/P1/B/FD1.bin'],
                         [o.target for o in occurrences])
        first = occurrences[0]
        self.assertEqual(('pcc', 'pa', 3, 'pa/mcr-data/P1.pcc/A.odx', 'A.odx/1'),
                         (first.origin_kind, first.origin, first.source_rank, first.source, first.detail))
        self.assertEqual(0, export(occurrences, self.out))
        self.assertEqual(b'aaa', self.read_target('flash', 'workspace', 'P1', 'A', 'FD1.bin'))
        self.assertEqual(b'bbb', self.read_target('flash', 'workspace', 'P1', 'B', 'FD1.bin'))

    def test_sw_cnt_areas_are_decoded(self):
        write_pcc(self.ws, 'pa', 'sub/deeper/P1.PCC', {
            'S.xml': sw_cnt_areas_xml([('Area One', b'\x01\x02'), ('', b'\x03'), ('Bad', None)])})
        occurrences, errors = pcc_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(0, errors)
        self.assertEqual(['flash/workspace/P1/S/Area One.bin', 'flash/workspace/P1/S/bereich_2.bin', None],
                         [o.target for o in occurrences])
        first = occurrences[0]
        self.assertEqual('pa/mcr-data/sub/deeper/P1.PCC/S.xml', first.source)
        self.assertEqual(('S.xml/1', 1, 'Area One', 0xA000, 0x10, None, 'decoded from container (Base64)'),
                         (first.detail, first.block_index, first.block, first.start_address,
                          first.uncompressed_size, first.method, first.note))
        self.assertEqual('could not decode container block', occurrences[2].note)
        self.assertEqual(b'\x03', occurrences[1].read())
        self.assertEqual(0, export(occurrences, self.out))
        self.assertEqual(b'\x01\x02', self.read_target('flash', 'workspace', 'P1', 'S', 'Area One.bin'))

    def test_area_without_data_raises_on_read(self):
        write_pcc(self.ws, 'pa', 'P1.pcc', {'S.xml': sw_cnt_areas_xml([('A', b'x')])})
        (item,), _ = pcc_occurrences(self.ws, 'pa', DocumentCache())
        write_pcc(self.ws, 'pa', 'P1.pcc', {'S.xml': sw_cnt_areas_xml([('B', None)])})
        with self.assertRaises(ValueError):
            item.read()

    def test_other_entries_go_to_mcr_unchanged(self):
        entries = {'ConfigData_X.odx-e': b'enc', 'Z.xml': b'<ZDC/>', 'a.session': b'1', 'a.sig': b'2',
                   'a.kfh': b'3', 'index.xml': b'<index/>', 'bad.xml': b'<a><b></a>'}
        write_pcc(self.ws, 'pa', 'P1.pcc', entries)
        occurrences, errors = pcc_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(0, errors)
        self.assertEqual(sorted('mcr/P1/' + name for name in entries), [o.target for o in occurrences])
        for item in occurrences:
            self.assertEqual((0, 'package entry, unchanged'), (item.block_index, item.note))
        self.assertEqual(0, export(occurrences, self.out))
        for name, data in entries.items():
            self.assertEqual(data, self.read_target('mcr', 'P1', name))

    def test_odx_entry_without_flash_goes_to_mcr(self):
        write_pcc(self.ws, 'pa', 'P1.pcc', {'C.odx': b'<?xml version="1.0"?><ODX><COMPARAM-SPEC/></ODX>'})
        (item,), errors = pcc_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual((0, 'mcr/P1/C.odx'), (errors, item.target))

    def test_broken_entries_and_packages_are_error_rows(self):
        write_pcc(self.ws, 'pa', 'P1.pcc', {'bad.odx': b'<ODX><FLASH>', 'ok.sig': b'1'})
        write_file(os.path.join(self.ws, 'pa', 'mcr-data', 'P2.pcc'), b'not a zip')
        with contextlib.redirect_stderr(io.StringIO()):
            occurrences, errors = pcc_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(2, errors)
        self.assertEqual(['pa/mcr-data/P1.pcc/bad.odx', 'pa/mcr-data/P1.pcc/ok.sig', 'pa/mcr-data/P2.pcc'],
                         [o.source for o in occurrences])
        self.assertTrue(occurrences[0].note.startswith('error: ParseError'))
        self.assertIsNone(occurrences[0].target)
        self.assertEqual('mcr/P1/ok.sig', occurrences[1].target)
        self.assertTrue(occurrences[2].note.startswith('error: BadZipFile'))

    def test_same_entry_in_two_packages_is_written_once(self):
        write_pcc(self.ws, 'pa', 'P1.pcc', {'a.sig': b'same'})
        write_pcc(self.ws, 'pa', 'P2.pcc', {'a.sig': b'same'})
        occurrences, _ = pcc_occurrences(self.ws, 'pa', DocumentCache())
        self.assertEqual(0, export(occurrences, self.out))
        self.assertEqual(['no', 'yes'], [r['duplicate'] for r in overview(self.out)])
        self.assertFalse(os.path.exists(os.path.join(self.out, 'mcr', 'P2')))

    def test_workspace_occurrences_end_to_end(self):
        for platform in ('pb', 'pa'):
            write_pdx(self.ws, platform, 'K.pdx', [DocBlock('b', flash_name='FD', data=platform.encode())])
            write_loose_odx(self.ws, platform, 'L.odx', [DocBlock('b', flash_name='FD', data=platform.encode() * 2)])
            write_pcc(self.ws, platform, 'P.pcc', {'a.sig': platform.encode() * 3})
        seen = []
        occurrences, errors = workspace_occurrences(self.ws, ['pa', 'pb'], progress=seen.append)
        self.assertEqual((0, ['pa', 'pb']), (errors, seen))
        self.assertEqual([('pa', 1), ('pa', 2), ('pa', 3), ('pb', 1), ('pb', 2), ('pb', 3)],
                         [(o.origin, o.source_rank) for o in occurrences])
        self.assertEqual(0, export(occurrences, self.out))
        self.assertEqual(6, len(overview(self.out)))


if __name__ == '__main__':
    unittest.main()
