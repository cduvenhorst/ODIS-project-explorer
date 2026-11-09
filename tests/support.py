"""Synthetic object streams, string storage and projects for tests.

Everything here is invented data; the formats follow the readers in classes/.
"""
import ctypes
import os
import struct
import tempfile
import zlib
from ctypes import c_char_p, c_int, c_long, c_size_t, c_void_p

from classes import DbObject
from classes.PBL import default_library_path
from classes.StringStorage import StringStorage
from common_utils import enum_converters

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

END_MARKER = b'#>\x00'


def object_type_code(type_name):
    """Inverse of enum_converters.object_types."""
    for code, name in enum_converters.object_types.items():
        if name == type_name:
            return code
    raise KeyError(type_name)


def string_hash(text, kind):
    """Initial DJB2 hash as in StringStorage.__get_string_hash (kind 'A' or 'U')."""
    if kind == 'A':
        units = list(text.encode('cp1252'))
    else:
        raw = text.encode('utf-16-le')
        units = list(struct.unpack('<%dH' % (len(raw) // 2), raw))
    value = 5381
    for unit in units:
        value = (value << 5) + value + unit
    value &= 0x7FFFFFFF
    return value or 5


def _assign_hashes(strings, kind):
    """Map hash -> string for the given strings; a collision is an error."""
    table = {}
    for text in strings:
        value = string_hash(text, kind)
        if value in table and table[value] != text:
            raise ValueError('hash collision between %r and %r' % (table[value], text))
        table[value] = text
    return table


class ObjectBytes:
    """Builds the byte stream of one object; every writer returns self."""

    def __init__(self):
        self._data = bytearray()
        self.ascii_strings = []
        self.unicode_strings = []

    def raw(self, data):
        self._data += data
        return self

    def u8(self, value):
        return self.raw(struct.pack('<B', value))

    def u16(self, value):
        return self.raw(struct.pack('<H', value))

    def u32(self, value):
        return self.raw(struct.pack('<I', value))

    def i32(self, value):
        return self.raw(struct.pack('<i', value))

    def double(self, value):
        return self.raw(struct.pack('<d', value))

    def flag(self, value):
        return self.u8(1 if value else 0)

    def ascii(self, text):
        if text is None:
            return self.u32(0)
        self.ascii_strings.append(text)
        return self.u32(string_hash(text, 'A'))

    def unicode(self, text):
        if text is None:
            return self.u32(0)
        self.unicode_strings.append(text)
        return self.u32(string_hash(text, 'U'))

    def native_ascii(self, text):
        if text is None:
            return self.u32(0)
        encoded = text.encode('cp1252')
        return self.u32(0x80000000 | len(encoded)).raw(encoded)

    def native_unicode(self, text):
        if text is None:
            return self.u32(0)
        encoded = text.encode('utf-16-le')
        return self.u32(0x80000000 | (len(encoded) // 2)).raw(encoded)

    def nested(self, type_name, body):
        self.u8(1).u16(object_type_code(type_name)).raw(body._data)
        self.ascii_strings += body.ascii_strings
        self.unicode_strings += body.unicode_strings
        return self

    def absent(self):
        return self.u8(0)

    def build(self, type_name):
        return bytearray(struct.pack('<H', object_type_code(type_name))) + self._data + END_MARKER


def _write_string_files(folder, ascii_strings, unicode_strings):
    for prefix, kind, strings, encoding in (('A', 'A', ascii_strings, 'cp1252'),
                                            ('U', 'U', unicode_strings, 'utf-16-le')):
        data = bytearray()
        index = bytearray()
        table = _assign_hashes(strings, kind)
        index += struct.pack('<I', len(table))
        for value, text in table.items():
            encoded = text.encode(encoding)
            index += struct.pack('<II', len(data), value)
            data += struct.pack('<I', len(encoded) // (2 if kind == 'U' else 1))
            data += encoded
        for suffix, content in (('data', data), ('idx', index)):
            path = os.path.join(folder, '%sStringData.%s.gz' % (prefix, suffix))
            with open(path, 'wb') as handle:
                handle.write(zlib.compress(bytes(content), wbits=31, level=1))


def string_storage(ascii_strings, unicode_strings):
    with tempfile.TemporaryDirectory() as folder:
        _write_string_files(folder, ascii_strings, unicode_strings)
        return StringStorage(folder)


def load(type_name, body, strict=True):
    storage = string_storage(body.ascii_strings, body.unicode_strings)
    return DbObject.load_object(body.build(type_name), storage, strict=strict)


def _open_pbl():
    library = ctypes.CDLL(default_library_path(REPOSITORY_ROOT))
    library.pblKfCreate.argtypes = [c_char_p, c_void_p]
    library.pblKfCreate.restype = c_void_p
    library.pblKfInsert.argtypes = [c_void_p, c_void_p, c_size_t, c_void_p, c_long]
    library.pblKfInsert.restype = c_int
    library.pblKfClose.argtypes = [c_void_p]
    library.pblKfClose.restype = c_int
    return library


def write_project(folder, pools, ascii_strings, unicode_strings):
    """Write `<pool>.key` and `<pool>.db` per pool plus the four string files.

    pools maps pool name to {object name: object bytes as built by ObjectBytes.build}.
    Object names are added to the ASCII strings, since lookup hashes them there.
    """
    names = [name for objects in pools.values() for name in objects]
    ascii_all = list(dict.fromkeys(list(ascii_strings) + names))
    _write_string_files(folder, ascii_all, list(unicode_strings))
    library = _open_pbl()
    for pool, objects in pools.items():
        key_path = os.path.join(folder, pool + '.key')
        key_file = library.pblKfCreate(key_path.encode('ascii'), None)
        if not key_file:
            raise RuntimeError('pblKfCreate failed for %s' % key_path)
        try:
            with open(os.path.join(folder, pool + '.db'), 'wb') as db_file:
                for name, data in objects.items():
                    compressed = zlib.compress(bytes(data))
                    record = struct.pack('<III', db_file.tell(), len(compressed), len(data))
                    db_file.write(compressed)
                    key = struct.pack('<L', string_hash(name, 'A'))
                    if library.pblKfInsert(key_file, key, len(key), record, len(record)) != 0:
                        raise RuntimeError('pblKfInsert failed for %s' % name)
        finally:
            library.pblKfClose(key_file)
