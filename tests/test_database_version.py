import os
import tempfile
import unittest

from classes.DbStream import DbStream
from classes.StringStorage import StringStorage
from tests import support


class DatabaseVersionTests(unittest.TestCase):
    def _storage(self, lines=None, raw=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        support._write_string_files(folder.name, [], [])
        if lines is not None:
            support.version_file(folder.name, lines)
        if raw is not None:
            with open(os.path.join(folder.name, 'DatabaseVersionInfo.txt'), 'wb') as handle:
                handle.write(raw)
        return StringStorage(folder.name)

    def test_missing_file_gives_none(self):
        storage = self._storage()
        self.assertIsNone(storage.database_version)
        stream = DbStream(bytearray(b'\x00\x00#>\x00'), storage)
        stream.report_unread_on_delete = False
        self.assertIs(stream.is_database_version_at_least(18), True)

    def test_porsche_key_with_other_lines(self):
        storage = self._storage(['First="1"',
                                 'PRODIS_MCD_DatabaseVersionInfo="0015"',
                                 'Other="1"'])
        self.assertEqual(storage.database_version, 15)
        stream = DbStream(bytearray(b'\x00\x00#>\x00'), storage)
        stream.report_unread_on_delete = False
        self.assertIs(stream.is_database_version_at_least(18), False)
        self.assertIs(stream.is_database_version_at_least(15), True)

    def test_vw_key(self):
        self.assertEqual(self._storage(['VWMCD_DatabaseVersionInfo="0018"']).database_version, 18)

    def test_lf_line_endings(self):
        storage = self._storage(raw=b'First="1"\nVWMCD_DatabaseVersionInfo="0018"\nOther="1"\n')
        self.assertEqual(storage.database_version, 18)

    def test_version_with_trailing_text(self):
        self.assertEqual(self._storage(['PRODIS_MCD_DatabaseVersionInfo="0016" build']).database_version, 16)

    def test_version_with_trailing_quote_text(self):
        self.assertEqual(self._storage(['VWMCD_DatabaseVersionInfo="0018"x']).database_version, 18)

    def test_is_database_version(self):
        stream = DbStream(bytearray(b'\x00\x00#>\x00'), self._storage(['PRODIS_MCD_DatabaseVersionInfo="0015"']))
        stream.report_unread_on_delete = False
        self.assertIs(stream.is_database_version(15), True)
        self.assertIs(stream.is_database_version(18), False)
        none_stream = DbStream(bytearray(b'\x00\x00#>\x00'), self._storage())
        none_stream.report_unread_on_delete = False
        self.assertIs(none_stream.is_database_version(15), False)

    def test_invalid_value_gives_none(self):
        self.assertIsNone(self._storage(['PRODIS_MCD_DatabaseVersionInfo="abc"']).database_version)

    def test_missing_entry_gives_none(self):
        self.assertIsNone(self._storage(['First="1"']).database_version)

    def test_support_load_passes_version(self):
        self.assertEqual(support.string_storage([], [], database_version='0017').database_version, 17)


if __name__ == '__main__':
    unittest.main()
