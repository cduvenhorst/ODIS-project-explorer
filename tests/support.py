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


def unit_body():
    """Body of a valid MCD_DB_UNIT."""
    return (ObjectBytes().ascii('U_km').unicode('Kilometer').unicode(None).ascii('UID')
            .ascii(None).ascii(None).unicode('km').double(1000.0).double(0.0)
            .absent().flag(False))


def concat(first, second):
    """New body with the bytes and strings of first followed by those of second."""
    body = ObjectBytes().raw(first._data).raw(second._data)
    body.ascii_strings = first.ascii_strings + second.ascii_strings
    body.unicode_strings = first.unicode_strings + second.unicode_strings
    return body


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


def version_file(folder: str, lines: list[str]) -> None:
    """Write `DatabaseVersionInfo.txt` with the given lines, CRLF-terminated."""
    with open(os.path.join(folder, 'DatabaseVersionInfo.txt'), 'wb') as handle:
        handle.write(''.join(line + '\r\n' for line in lines).encode('latin-1'))


def string_storage(ascii_strings, unicode_strings, database_version=None):
    with tempfile.TemporaryDirectory() as folder:
        _write_string_files(folder, ascii_strings, unicode_strings)
        if database_version is not None:
            version_file(folder, ['PRODIS_MCD_DatabaseVersionInfo="%s"' % database_version])
        return StringStorage(folder)


def load(type_name, body, strict=True, database_version=None):
    storage = string_storage(body.ascii_strings, body.unicode_strings, database_version)
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


def write_raw_pool(folder: str, pool: str, entries: list[tuple[bytes, list[bytes]]]) -> None:
    """Write `<pool>.key` and `<pool>.db` from (key bytes, parts) entries.

    Each part is passed uncompressed and stored as its own zlib stream, back to back.
    The record data holds 12 bytes for one part, else 12 + 8k bytes for 1 + k parts.
    """
    library = _open_pbl()
    key_path = os.path.join(folder, pool + '.key')
    key_file = library.pblKfCreate(key_path.encode('ascii'), None)
    if not key_file:
        raise RuntimeError('pblKfCreate failed for %s' % key_path)
    try:
        with open(os.path.join(folder, pool + '.db'), 'wb') as db_file:
            for key, parts in entries:
                record = struct.pack('<I', db_file.tell())
                for part in parts:
                    compressed = zlib.compress(bytes(part))
                    record += struct.pack('<II', len(compressed), len(part))
                    db_file.write(compressed)
                if library.pblKfInsert(key_file, key, len(key), record, len(record)) != 0:
                    raise RuntimeError('pblKfInsert failed for %r' % key)
    finally:
        library.pblKfClose(key_file)


# ---------------------------------------------------------------------------
# Shared builders for the layout protection tests
# ---------------------------------------------------------------------------


OPEN, CLOSED, INFINITE = 1, 2, 3


LIMIT_NAMES = {OPEN: 'eLIMIT_OPEN', CLOSED: 'eLIMIT_CLOSED', INFINITE: 'eLIMIT_INFINITE'}


def uint_value(body, number):
    return body.u8(11).u32(number)


def uint(number):
    return {'data_type': 'eA_UINT32', 'value': number}


def limit_body(number=5, kind=OPEN):
    return uint_value(ObjectBytes(), number).u8(kind)


def limit(number=5, kind=OPEN):
    return {'#OBJECT_TYPE': 'DB_LIMIT', 'mcd_value': uint(number), 'limit_type': LIMIT_NAMES[kind]}


def diag_coded_type_body():
    return ObjectBytes().u8(0).u32(8).u8(0).u8(3).flag(False).flag(False)


def diag_coded_type():
    return {'#OBJECT_TYPE': 'DB_DIAG_CODED_TYPE', 'type': 'eLEADING_LENGTH_INFO_TYPE',
            'bit_length': 8, 'base_data_type': 'eDB_INT32',
            'base_data_type_as_mcd_data_type': 'eA_INT32', 'encoding': 'e2C',
            'is_high_low_byte_order': False, 'is_condensed': False}


def case_base_body(structure_ref=False):
    body = ObjectBytes().ascii('Case').unicode('Case long').unicode(None)
    body.ascii(None).ascii(None).ascii(None)
    if structure_ref:
        return body.flag(True).ascii('STRUCT').ascii('POOL')
    return body.flag(False)


def case_base(structure_ref=None):
    return {'short_name': 'Case', 'long_name': 'Case long', 'description': None,
            'structure_dop_ref': structure_ref}


def case_body():
    return ObjectBytes().nested('DB_LIMIT', limit_body(1, CLOSED)).nested('DB_LIMIT', limit_body(9, OPEN))


def case_expected():
    return {'lower_limit': limit(1, CLOSED), 'upper_limit': limit(9, OPEN)}


def case(structure_ref=None, type_name='DB_CASE'):
    result = {'#OBJECT_TYPE': type_name}
    if type_name == 'DB_CASE':
        result.update(case_expected())
    result.update(case_base(structure_ref))
    return result


def typed(type_name, fields):
    return {'#OBJECT_TYPE': type_name, **fields}


def ref_body(body, object_id='OBJ', pool_id='POOL'):
    """DbObjectReference without the third string."""
    return body.ascii(object_id).ascii(pool_id)


def ref(object_id='OBJ', pool_id='POOL'):
    return {'object_id': object_id, 'pool_id': pool_id}


NAMED_REFS = [('N1', 'R1', 'P1'), ('N2', 'R2', None)]


def named_refs_body(body, entries=()):
    body.u16(len(entries))
    for name, object_id, pool_id in entries:
        body.ascii(name).ascii(object_id).ascii(pool_id)
    return body


def named_refs(entries=()):
    return [{'name': name, 'reference': ref(object_id, pool_id)}
            for name, object_id, pool_id in entries]


def attributed_ref_body(body, strings=()):
    body.ascii('OBJ').ascii('POOL').u8(len(strings))
    for text in strings:
        body.ascii(text)
    return body


def attributed_ref(strings=()):
    return {'object_id': 'OBJ', 'pool_id': 'POOL', 'strings': list(strings)}


NAMED_ATTRIBUTED_REFS = [('S1', ('A1', 'A2')), ('S2', ())]


def named_attributed_refs_body(body, entries=()):
    body.u16(len(entries))
    for name, strings in entries:
        body.ascii(name)
        attributed_ref_body(body, strings)
    return body


def named_attributed_refs(entries=()):
    return [{'name': name, 'reference': attributed_ref(strings)} for name, strings in entries]


def diag_com_ref_body(body, with_strings):
    """DbDiagComObjectReference, type eMCDAUDIENCE."""
    attributed_ref_body(body, ['A1'] if with_strings else [])
    body.u8(3).u16(0x0DAC).u8(1 if with_strings else 0)
    if with_strings:
        body.u16(2).ascii('V1').ascii('V2')
    return body


def diag_com_ref(with_strings):
    result = {'attrib_obj_ref': attributed_ref(['A1'] if with_strings else []),
              'number': 3, 'mcd_object_type': 'eMCDAUDIENCE'}
    if with_strings:
        result['strings'] = ['V1', 'V2']
    return result


def diag_com_refs_body(body):
    """Named collection of two DbDiagComObjectReference, loaded with and without strings."""
    body.u16(2).ascii('D1')
    diag_com_ref_body(body, True)
    body.ascii('D2')
    return diag_com_ref_body(body, False)


def diag_com_refs():
    return [{'name': 'D1', 'reference': diag_com_ref(True)},
            {'name': 'D2', 'reference': diag_com_ref(False)}]


def audience_body():
    return ObjectBytes().u8(1).u8(0).u8(1).u8(0).u8(1)


def audience():
    return typed('MCD_AUDIENCE', {'supplier': 1, 'development': 0, 'manufacturing': 1,
                                  'after_sales': 0, 'after_market': 1})
