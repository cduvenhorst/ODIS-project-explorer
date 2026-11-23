import gzip
import os
import struct
import tempfile
import unittest

from classes.StringStorage import StringStorage
from tests import support

FILE_NAMES = ('AStringData.data', 'AStringData.idx', 'UStringData.data', 'UStringData.idx')

# Two invented strings with the same initial DJB2 hash. DJB2 computes h * 33 + c, so for two-character
# strings (a, b) and (a + 1, b - 33) give the same value: 'A' + 'z' (65, 122) and 'B' + 'Y' (66, 89).
# support.string_hash confirms the equality for both the ASCII and the Unicode reading.
COLLIDING_FIRST = 'Az'
COLLIDING_SECOND = 'BY'


def _build_files(table, kind):
    """Return (data, index) bytes for a {hash: text} table, in index order."""
    encoding = 'cp1252' if kind == 'A' else 'utf-16-le'
    unit = 1 if kind == 'A' else 2
    data = bytearray()
    index = bytearray(struct.pack('<I', len(table)))
    for value, text in table.items():
        encoded = text.encode(encoding)
        index += struct.pack('<II', len(data), value)
        data += struct.pack('<I', len(encoded) // unit)
        data += encoded
    return bytes(data), bytes(index)


def _write_tables(folder, ascii_table, unicode_table, packed=True):
    """Write the four string files from explicit {hash: text} tables, gz-packed or plain."""
    for kind, table in (('A', ascii_table), ('U', unicode_table)):
        data, index = _build_files(table, kind)
        for suffix, content in (('data', data), ('idx', index)):
            name = '%sStringData.%s' % (kind, suffix)
            if packed:
                with open(os.path.join(folder, name + '.gz'), 'wb') as handle:
                    handle.write(gzip.compress(content))
            else:
                with open(os.path.join(folder, name), 'wb') as handle:
                    handle.write(content)


def _hashed(strings, kind):
    return {support.string_hash(text, kind): text for text in strings}


def _read_plain(folder, name):
    """Content of a string file whether it is stored plain or gz-packed."""
    plain = os.path.join(folder, name)
    if os.path.isfile(plain):
        with open(plain, 'rb') as handle:
            return handle.read()
    with gzip.open(plain + '.gz', 'rb') as handle:
        return handle.read()


class StringStorageTests(unittest.TestCase):
    def _folder(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return folder.name

    def _storage(self, ascii_table, unicode_table, packed=True):
        folder = self._folder()
        _write_tables(folder, ascii_table, unicode_table, packed)
        return StringStorage(folder)

    def test_get_strings_by_hash(self):
        ascii_strings = ['Alpha', 'Beta Gamma']
        unicode_strings = ['Grüße', '日本']
        for packed in (True, False):
            with self.subTest(packed=packed):
                storage = self._storage(_hashed(ascii_strings, 'A'), _hashed(unicode_strings, 'U'), packed)
                for text in ascii_strings:
                    value = support.string_hash(text, 'A')
                    self.assertEqual(storage.get_ascii_string(value), text)
                    self.assertEqual(storage.get_ascii_string(str(value)), text)
                    self.assertEqual(storage.get_string(value), text)
                    self.assertEqual(storage.get_string(str(value)), text)
                for text in unicode_strings:
                    value = support.string_hash(text, 'U')
                    self.assertEqual(storage.get_unicode_string(value), text)
                    self.assertEqual(storage.get_unicode_string(str(value)), text)
                    self.assertEqual(storage.get_string(value), text)

    def test_get_string_prefers_ascii_over_unicode(self):
        table_a = {77: 'ascii text'}
        table_u = {77: 'unicode text', 78: 'only unicode'}
        storage = self._storage(table_a, table_u)
        self.assertEqual(storage.get_string(77), 'ascii text')
        self.assertEqual(storage.get_unicode_string(77), 'unicode text')
        self.assertEqual(storage.get_string(78), 'only unicode')

    def test_unknown_hash_gives_none(self):
        storage = self._storage({5: 'a'}, {6: 'b'})
        self.assertIsNone(storage.get_ascii_string(999))
        self.assertIsNone(storage.get_unicode_string('999'))
        self.assertIsNone(storage.get_string(999))
        self.assertIsNone(storage.get_ascii_string(6))
        self.assertIsNone(storage.get_unicode_string(5))

    def test_non_numeric_hash_raises_value_error(self):
        storage = self._storage({5: 'a'}, {6: 'b'})
        for method in (storage.get_ascii_string, storage.get_unicode_string, storage.get_string):
            with self.subTest(method=method.__name__):
                with self.assertRaises(ValueError):
                    method('not a number')

    def test_get_hash_with_collision_chain(self):
        for kind in ('A', 'U'):
            with self.subTest(kind=kind):
                initial = support.string_hash(COLLIDING_FIRST, kind)
                self.assertEqual(initial, support.string_hash(COLLIDING_SECOND, kind))
                # the second string was stored one step (+11) behind the first
                table = {initial: COLLIDING_FIRST, initial + 11: COLLIDING_SECOND}
                if kind == 'A':
                    storage = self._storage(table, {})
                    get_hash = storage.get_ascii_hash
                else:
                    storage = self._storage({}, table)
                    get_hash = storage.get_unicode_hash
                self.assertEqual(get_hash(COLLIDING_FIRST), initial)
                self.assertEqual(get_hash(COLLIDING_SECOND), initial + 11)

    def test_get_hash_of_unknown_string_is_initial_hash(self):
        storage = self._storage({}, {})
        self.assertEqual(storage.get_ascii_hash('Alpha'), support.string_hash('Alpha', 'A'))
        self.assertEqual(storage.get_unicode_hash('日'), support.string_hash('日', 'U'))

    def test_unicode_byte_order_mark_is_kept(self):
        text = '\ufeffMarked'
        storage = self._storage({}, {11: text})
        self.assertEqual(storage.get_unicode_string(11), text)
        self.assertEqual(len(storage.get_unicode_string(11)), len('Marked') + 1)

    def test_empty_string(self):
        storage = self._storage({21: ''}, {22: ''})
        self.assertEqual(storage.get_ascii_string(21), '')
        self.assertEqual(storage.get_unicode_string(22), '')
        self.assertEqual(storage.get_string(21), '')

    def test_duplicate_hash_in_index_raises_runtime_error(self):
        folder = self._folder()
        _write_tables(folder, {5: 'first'}, {}, packed=False)
        # append a second index record that repeats hash 5 and points at the same data
        path = os.path.join(folder, 'AStringData.idx')
        with open(path, 'rb') as handle:
            index = bytearray(handle.read())
        index[:4] = struct.pack('<I', 2)
        index += struct.pack('<II', 0, 5)
        with open(path, 'wb') as handle:
            handle.write(index)
        with self.assertRaises(RuntimeError) as context:
            StringStorage(folder)
        self.assertEqual(str(context.exception), 'Duplicate key (5) while loading A strings ("first")')

    def test_add_string_then_get_and_hash(self):
        storage = self._storage({}, {})
        storage.add_string_ascii('Alpha')
        storage.add_string_unicode('日本')
        value_a = storage.get_ascii_hash('Alpha')
        value_u = storage.get_unicode_hash('日本')
        self.assertEqual(value_a, support.string_hash('Alpha', 'A'))
        self.assertEqual(storage.get_ascii_string(value_a), 'Alpha')
        self.assertEqual(storage.get_unicode_string(value_u), '日本')

    def test_add_colliding_string_moves_by_eleven(self):
        storage = self._storage({}, {})
        storage.add_string_ascii(COLLIDING_FIRST)
        storage.add_string_ascii(COLLIDING_SECOND)
        initial = support.string_hash(COLLIDING_FIRST, 'A')
        self.assertEqual(storage.get_ascii_hash(COLLIDING_FIRST), initial)
        self.assertEqual(storage.get_ascii_hash(COLLIDING_SECOND), initial + 11)
        self.assertEqual(storage.get_ascii_string(initial + 11), COLLIDING_SECOND)

    def test_write_round_trip_is_byte_identical(self):
        ascii_table = {5: 'Alpha', 9: 'Beta', 3: '', 7: 'café'}
        unicode_table = {8: 'Grüße', 4: '日本', 6: '\ufeffMarked'}
        for packed in (True, False):
            with self.subTest(packed=packed):
                source = self._folder()
                target = self._folder()
                _write_tables(source, ascii_table, unicode_table, packed)
                StringStorage(source).write(target)
                for name in FILE_NAMES:
                    self.assertEqual(_read_plain(target, name), _read_plain(source, name), name)

    def test_write_after_add_appends_new_text_behind_old_ones(self):
        source = self._folder()
        target = self._folder()
        _write_tables(source, {5: 'Alpha', 9: 'Beta'}, {8: 'Gamma'})
        storage = StringStorage(source)
        storage.add_string_ascii('Delta')
        storage.add_string_unicode('Epsilon')
        storage.write(target)
        expected_a = {5: 'Alpha', 9: 'Beta', support.string_hash('Delta', 'A'): 'Delta'}
        expected_u = {8: 'Gamma', support.string_hash('Epsilon', 'U'): 'Epsilon'}
        for kind, table in (('A', expected_a), ('U', expected_u)):
            data, index = _build_files(table, kind)
            self.assertEqual(_read_plain(target, '%sStringData.data' % kind), data)
            self.assertEqual(_read_plain(target, '%sStringData.idx' % kind), index)
        reloaded = StringStorage(target)
        self.assertEqual(reloaded.get_ascii_string(support.string_hash('Delta', 'A')), 'Delta')
        self.assertEqual(reloaded.get_unicode_string(support.string_hash('Epsilon', 'U')), 'Epsilon')

    def test_strings_are_not_held_as_python_objects(self):
        ascii_strings = ['Alpha', 'Beta Gamma', 'café', '']
        unicode_strings = ['Grüße', '日本', '\ufeffMarked']
        storage = self._storage(_hashed(ascii_strings, 'A'), _hashed(unicode_strings, 'U'))
        storage.add_string_ascii('Delta')
        storage.add_string_unicode('Epsilon')
        added_count = 2
        for name, value in vars(storage).items():
            if isinstance(value, dict):
                self.assertLessEqual(len(value), added_count, name)
        for text in ascii_strings + ['Delta']:
            self.assertEqual(storage.get_ascii_string(support.string_hash(text, 'A')), text)
        for text in unicode_strings + ['Epsilon']:
            self.assertEqual(storage.get_unicode_string(support.string_hash(text, 'U')), text)

    def test_str_counts(self):
        storage = self._storage({1: 'a', 2: 'b', 3: 'c'}, {4: 'd'})
        self.assertEqual(str(storage), 'A: 3, U: 1')
        storage.add_string_ascii('new')
        self.assertEqual(str(storage), 'A: 4, U: 1')
        self.assertEqual(str(self._storage({}, {})), 'A: 0, U: 0')

    def test_database_version(self):
        folder = self._folder()
        _write_tables(folder, {}, {})
        self.assertIsNone(StringStorage(folder).database_version)
        support.version_file(folder, ['Other="x"', 'PRODIS_MCD_DatabaseVersionInfo="0018"'])
        self.assertEqual(StringStorage(folder).database_version, 18)
        support.version_file(folder, ['VWMCD_DatabaseVersionInfo="12ab"'])
        self.assertIsNone(StringStorage(folder).database_version)


if __name__ == '__main__':
    unittest.main()
