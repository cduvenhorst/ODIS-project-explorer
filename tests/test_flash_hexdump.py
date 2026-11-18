import os
import tempfile
import unittest

from flash_export.hexdump import hexdump_lines, hexdump_size, write_hexdump


class HexdumpTests(unittest.TestCase):
    def test_short_line_is_padded_before_ascii_column(self):
        self.assertEqual(list(hexdump_lines(b'Hello\n')), [
            '00000000  48 65 6c 6c 6f 0a                                 |Hello.|\n',
            '00000006\n'])

    def test_repeated_lines_collapse_to_star(self):
        self.assertEqual(list(hexdump_lines(bytes(range(16)) * 3 + b'ABC')), [
            '00000000  00 01 02 03 04 05 06 07  08 09 0a 0b 0c 0d 0e 0f  |................|\n',
            '*\n',
            '00000030  41 42 43                                          |ABC|\n',
            '00000033\n'])

    def test_repeat_up_to_the_end_keeps_final_offset(self):
        self.assertEqual(list(hexdump_lines(b'\x00' * 32)), [
            '00000000  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|\n',
            '*\n',
            '00000020\n'])

    def test_printable_range_is_shown_in_ascii_column(self):
        self.assertEqual(list(hexdump_lines(bytes(range(32, 48)))), [
            '00000000  20 21 22 23 24 25 26 27  28 29 2a 2b 2c 2d 2e 2f  | !"#$%&\'()*+,-./|\n',
            '00000010\n'])

    def test_empty_input_gives_no_lines(self):
        self.assertEqual(list(hexdump_lines(b'')), [])

    def test_size_matches_written_text(self):
        data = bytes(range(16)) * 3 + b'ABC'
        self.assertEqual(hexdump_size(data), len(''.join(hexdump_lines(data))))

    def test_write_hexdump_writes_lines(self):
        data = bytes(range(16)) * 3 + b'ABC'
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'dump.txt')
            write_hexdump(data, path)
            with open(path, encoding='ascii', newline='') as handle:
                self.assertEqual(handle.read(), ''.join(hexdump_lines(data)))
