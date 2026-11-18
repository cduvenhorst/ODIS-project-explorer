import contextlib
import csv
import io
import os
import tempfile
import unittest
from unittest import mock

from flash_export.hexdump import hexdump_lines
from flash_export.output import (OVERVIEW_COLUMNS, InsufficientSpaceError, Occurrence, OutputFolderError, export, overview_path,
                                 sanitize_name)

BIG = lambda p: 10 ** 12


def occ(source, target, content, **kw):
    return Occurrence(source_rank=kw.pop('source_rank', 0), origin_kind='project', origin=kw.pop('origin', 'P1'),
                      source=source, block_index=kw.pop('block_index', 0), target=target,
                      read=(lambda: content) if content is not None else None, **kw)


def read_overview(target):
    with open(overview_path(target), encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


class FlashOutputTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = self._tmp.name

    def test_same_content_is_written_once_under_first_in_sort_order(self):
        errors = export([occ('b/x.bin', 'flash/P1/b/x.bin', b'same'), occ('a/y.bin', 'flash/P1/a/y.bin', b'same')],
                        self.target, free_space_of=BIG)
        self.assertEqual(errors, 0)
        self.assertTrue(os.path.exists(os.path.join(self.target, 'flash/P1/a/y.bin')))
        self.assertFalse(os.path.exists(os.path.join(self.target, 'flash/P1/b/x.bin')))
        rows = read_overview(self.target)
        self.assertEqual(len(rows), 2)
        row = [r for r in rows if r['source'] == 'b/x.bin'][0]
        self.assertEqual(row['written_file'], 'flash/P1/a/y.bin')
        self.assertEqual(row['duplicate'], 'yes')
        first = [r for r in rows if r['source'] == 'a/y.bin'][0]
        self.assertEqual(first['duplicate'], 'no')

    def test_overview_header_and_formats(self):
        export([occ('a.bin', 'flash/P1/a.bin', b'12345', start_address=0x10000, method=0)], self.target,
               free_space_of=BIG)
        with open(overview_path(self.target), encoding='utf-8', newline='') as handle:
            self.assertEqual(next(csv.reader(handle)), OVERVIEW_COLUMNS)
        row = read_overview(self.target)[0]
        self.assertEqual(row['start_address'], '0x00010000')
        self.assertEqual(row['method'], '0x00')
        self.assertEqual(row['size'], '5')

    def test_row_without_content_has_empty_size_and_duplicate(self):
        errors = export([occ('a.bin', None, None, note='file not found in project')], self.target,
                        free_space_of=BIG)
        self.assertEqual(errors, 0)
        row = read_overview(self.target)[0]
        self.assertEqual((row['size'], row['written_file'], row['duplicate']), ('', '', ''))
        self.assertEqual(row['note'], 'file not found in project')

    def test_case_insensitive_name_clash_gets_running_number(self):
        export([occ('1', 'flash/P1/p/Driver.bin', b'one'), occ('2', 'flash/P1/p/driver.bin', b'two')],
               self.target, free_space_of=BIG)
        rows = read_overview(self.target)
        self.assertEqual([r['written_file'] for r in rows], ['flash/P1/p/Driver.bin', 'flash/P1/p/driver_2.bin'])

    def test_sanitize_name(self):
        self.assertEqual(sanitize_name('a/b'), 'a_b')
        self.assertEqual(sanitize_name('..'), '_')
        self.assertEqual(sanitize_name('x:y*?'), 'x_y__')
        self.assertEqual(sanitize_name(''), '_')

    def test_insufficient_space_writes_nothing(self):
        with self.assertRaises(InsufficientSpaceError) as ctx:
            export([occ('a.bin', 'flash/P1/a.bin', b'0123456789')], self.target, free_space_of=lambda p: 1)
        self.assertGreater(ctx.exception.needed, 1)
        self.assertEqual(ctx.exception.free, 1)
        self.assertEqual(os.listdir(self.target), [])

    def test_hexdump_adds_text_file_and_counts_its_size(self):
        content = bytes(range(40))
        export([occ('a.bin', 'flash/P1/a.bin', content)], self.target, hexdump=True, free_space_of=BIG)
        with open(os.path.join(self.target, 'flash/P1/a.bin.hexdump.txt'), encoding='ascii', newline='') as handle:
            self.assertEqual(handle.read(), ''.join(hexdump_lines(content)))
        overview_len = os.path.getsize(overview_path(self.target))
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(InsufficientSpaceError):
                export([occ('a.bin', 'flash/P1/a.bin', content)], other, hexdump=True,
                       free_space_of=lambda p: len(content) + overview_len)

    def test_existing_file_of_same_size_is_not_counted(self):
        occurrences = lambda: [occ('a.bin', 'flash/P1/a.bin', b'0123456789')]
        export(occurrences(), self.target, free_space_of=BIG)
        with open(overview_path(self.target), 'rb') as handle:
            first = handle.read()
        export(occurrences(), self.target, free_space_of=lambda p: 0)
        with open(overview_path(self.target), 'rb') as handle:
            self.assertEqual(handle.read(), first)

    def test_read_error_is_reported_and_counted(self):
        def bad():
            raise ValueError('bad hex')
        bad_occ = occ('a.bin', 'flash/P1/a.bin', b'x')
        bad_occ.read = bad
        good = occ('b.bin', 'flash/P1/b.bin', b'good')
        errors = export([bad_occ, good], self.target, free_space_of=BIG)
        self.assertEqual(errors, 1)
        rows = read_overview(self.target)
        self.assertEqual(rows[0]['note'], 'error: ValueError: bad hex')
        self.assertTrue(os.path.exists(os.path.join(self.target, 'flash/P1/b.bin')))

    def _flaky(self, second):
        calls = []

        def read():
            calls.append(1)
            if len(calls) == 1:
                return b'first'
            return second()
        return read

    def test_second_read_error_leaves_no_file_and_marks_row(self):
        def fail():
            raise OSError('disk gone')
        item = occ('a.bin', 'flash/P1/a.bin', b'x', )
        item.read = self._flaky(fail)
        dup = occ('b.bin', 'flash/P1/b.bin', b'first')
        errors = export([item, dup], self.target, hexdump=True, free_space_of=BIG)
        self.assertEqual(errors, 1)
        self.assertFalse(os.path.exists(os.path.join(self.target, 'flash/P1/a.bin')))
        self.assertFalse(os.path.exists(os.path.join(self.target, 'flash/P1/a.bin.hexdump.txt')))
        first = read_overview(self.target)[0]
        self.assertEqual(first['note'], 'error: OSError: disk gone')
        self.assertEqual((first['written_file'], first['duplicate']), ('', 'no'))

    def test_duplicates_of_a_failed_first_occurrence_are_marked(self):
        def fail():
            raise OSError('disk gone')
        item = occ('a.bin', 'flash/P1/a.bin', b'x')
        item.read = self._flaky(fail)
        dup = occ('b.bin', 'flash/P1/b.bin', b'first')
        self.assertEqual(export([item, dup], self.target, free_space_of=BIG), 1)
        row = read_overview(self.target)[1]
        self.assertEqual((row['duplicate'], row['written_file']), ('yes', ''))
        self.assertEqual(row['note'], 'error: OSError: disk gone')

    def test_second_read_with_different_bytes_is_an_error(self):
        item = occ('a.bin', 'flash/P1/a.bin', b'x')
        item.read = self._flaky(lambda: b'other')
        errors = export([item], self.target, free_space_of=BIG)
        self.assertEqual(errors, 1)
        self.assertFalse(os.path.exists(os.path.join(self.target, 'flash/P1/a.bin')))
        self.assertEqual(read_overview(self.target)[0]['note'], 'error: ValueError: content changed between reads')

    def test_rows_sorted_by_rank_origin_source_block_detail(self):
        export([occ('s', 'flash/r1', b'1', source_rank=1, origin='A', block='r1'),
                occ('s', 'flash/b2', b'2', origin='B', block_index=2, block='b2'),
                occ('s', 'flash/b1', b'3', origin='B', block_index=1, block='b1'),
                occ('t', 'flash/at', b'4', origin='A', block='at')], self.target, free_space_of=BIG)
        self.assertEqual([r['block'] for r in read_overview(self.target)], ['at', 'b1', 'b2', 'r1'])

    def test_data_kind_column_uses_method_source(self):
        export([occ('a.bin', 'flash/P1/a.bin', b'abc', method=0x11, method_source='DATENBLOCK-FORMAT')],
               self.target, free_space_of=BIG)
        self.assertIn('DATENBLOCK-FORMAT 0x11', read_overview(self.target)[0]['data_kind'])

    def test_overview_uses_default_csv_line_terminator(self):
        export([occ('a.bin', 'flash/P1/a.bin', b'1')], self.target, free_space_of=BIG)
        with open(overview_path(self.target), 'rb') as handle:
            lines = handle.read().split(b'\r\n')
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[2], b'')
        self.assertNotIn(b'\n', b''.join(lines))

    def test_hexdump_size_is_computed_only_for_new_content(self):
        with mock.patch('flash_export.output.hexdump_size', return_value=1) as size:
            export([occ('a.bin', 'flash/P1/a.bin', b'same'), occ('b.bin', 'flash/P1/b.bin', b'same'),
                    occ('c.bin', 'flash/P1/c.bin', b'other')], self.target, hexdump=True, free_space_of=BIG)
        self.assertEqual(size.call_count, 2)

    def test_unsafe_targets_become_error_rows_and_write_nothing(self):
        unsafe = ['flash/P1/../x.bin', 'flash//x.bin', 'flash/./x.bin', '/abs/x.bin', 'flash\\x.bin',
                  '../x.bin', 'flash/P1/']
        occurrences = [occ('s%d' % number, target, b'data%d' % number, block_index=number)
                       for number, target in enumerate(unsafe)]
        occurrences.append(occ('z-good', 'flash/P1/good.bin', b'good', block_index=99))
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            errors = export(occurrences, self.target, free_space_of=BIG)
        self.assertEqual(errors, len(unsafe))
        rows = read_overview(self.target)
        self.assertEqual(len(rows), len(unsafe) + 1)
        for row in rows[:-1]:
            self.assertEqual(row['note'], 'error: ValueError: unsafe target path')
            self.assertEqual((row['size'], row['written_file'], row['duplicate']), ('', '', ''))
        self.assertIn('s0', stderr.getvalue())
        self.assertEqual(sorted(os.listdir(os.path.join(self.target, 'flash'))), ['P1', 'flash_overview.csv'])
        self.assertEqual(os.listdir(os.path.join(self.target, 'flash', 'P1')), ['good.bin'])
        self.assertFalse(os.path.exists(os.path.join(self.target, 'x.bin')))

    def test_unwritable_output_folder_aborts_once(self):
        blocker = os.path.join(self.target, 'file')
        with open(blocker, 'wb'):
            pass
        reads = []
        item = occ('a.bin', 'flash/P1/a.bin', b'x')
        item.read = lambda: reads.append(1) or b'x'
        with self.assertRaises(OutputFolderError) as ctx:
            export([item, occ('b.bin', 'flash/P1/b.bin', b'y')], os.path.join(blocker, 'out'), free_space_of=BIG)
        self.assertIsInstance(ctx.exception, OSError)
        self.assertEqual(ctx.exception.path, os.path.join(blocker, 'out', 'flash'))


if __name__ == '__main__':
    unittest.main()
