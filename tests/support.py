"""Synthetic object streams, string storage and projects for tests.

Everything here is invented data; the formats follow the readers in classes/.
"""
import ctypes
import gzip
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

    def u64(self, value):
        return self.raw(struct.pack('<Q', value))

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

    def embedded_ascii(self, text):
        """String stored in the stream itself; nothing is added to the string pool."""
        encoded = text.encode('cp1252')
        return self.u32(0x80000000 | len(encoded)).raw(encoded)

    def embedded_unicode(self, text):
        """Unicode string stored in the stream itself; nothing is added to the pool."""
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


def write_sdg_file(folder, pool_id, records):
    """Write SDG_<pool_id>.kix.gz / .dix.gz: records back to back, one 8-byte key entry each."""
    keys = bytearray()
    data = bytearray()
    for record in records:
        keys += struct.pack('<II', len(data), len(record))
        data += record
    with gzip.open(os.path.join(folder, 'SDG_%s.kix.gz' % pool_id), 'wb') as handle:
        handle.write(bytes(keys))
    with gzip.open(os.path.join(folder, 'SDG_%s.dix.gz' % pool_id), 'wb') as handle:
        handle.write(bytes(data))


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
    # kernel: the limit value is read with getLimit
    return {'#OBJECT_TYPE': 'DB_LIMIT', 'limit': uint(number), 'limit_type': LIMIT_NAMES[kind]}


def diag_coded_type_body():
    return ObjectBytes().u8(0).u32(8).u8(0).u8(3).flag(False).flag(False)


def diag_coded_type():
    # kernel: the type is read with getCodedType, the flag with isCondensedBitMask
    return {'#OBJECT_TYPE': 'DB_DIAG_CODED_TYPE', 'coded_type': 'eLEADING_LENGTH_INFO_TYPE',
            'bit_length': 8, 'base_data_type': 'eDB_INT32',
            'base_data_type_as_mcd_data_type': 'eA_INT32', 'encoding': 'e2C',
            'is_high_low_byte_order': False, 'is_condensed_bit_mask': False,
            # kernel: getLengthKeyParam reports 'not set' unless the type is a parameter length info type
            'length_key_parameter': None}


def case_base_body(structure_ref=False, ids=None):
    # ids: (unique_object_id, long_name_id, description_id); None writes word 0 three times
    body = ObjectBytes().ascii('Case').unicode('Case long').unicode(None)
    for identifier in ids or (None, None, None):
        body.ascii(identifier)
    if structure_ref:
        return body.flag(True).ascii('STRUCT').ascii('POOL')
    return body.flag(False)


def case_base(structure_ref=None, ids=None):
    unique_object_id, long_name_id, description_id = ids or (None, None, None)
    return {'short_name': 'Case', 'long_name': 'Case long', 'description': None,
            'unique_object_id': unique_object_id, 'long_name_id': long_name_id,
            'description_id': description_id, 'structure_dop_reference': structure_ref}


def case_body():
    return ObjectBytes().nested('DB_LIMIT', limit_body(1, CLOSED)).nested('DB_LIMIT', limit_body(9, OPEN))


def case_expected():
    return {'lower_limit': limit(1, CLOSED), 'upper_limit': limit(9, OPEN)}


def case(structure_ref=None, type_name='DB_CASE', ids=None):
    result = {'#OBJECT_TYPE': type_name}
    if type_name == 'DB_CASE':
        result.update(case_expected())
    result.update(case_base(structure_ref, ids))
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


def attributed_ref_body(body, strings=(), object_id='OBJ', pool_id='POOL'):
    body.ascii(object_id).ascii(pool_id).u8(len(strings))
    for text in strings:
        body.ascii(text)
    return body


def attributed_ref(strings=()):
    return {'object_id': 'OBJ', 'pool_id': 'POOL', 'attributes': list(strings)}


NAMED_ATTRIBUTED_REFS = [('S1', ('A1', 'A2')), ('S2', ())]


def named_attributed_refs_body(body, entries=()):
    body.u16(len(entries))
    for name, strings in entries:
        body.ascii(name)
        attributed_ref_body(body, strings)
    return body


def named_attributed_refs(entries=()):
    return [{'name': name, 'reference': attributed_ref(strings)} for name, strings in entries]


def diag_com_ref_body(body, with_strings, object_id='OBJ', pool_id='POOL'):
    """DbDiagComObjectReference, type eMCDAUDIENCE."""
    attributed_ref_body(body, ['A1'] if with_strings else [], object_id, pool_id)
    body.u8(3).u16(0x0DAC).u8(1 if with_strings else 0)
    if with_strings:
        body.u16(2).ascii('V1').ascii('V2')
    return body


def diag_com_ref(with_strings):
    return {'object_id': 'OBJ', 'pool_id': 'POOL', 'attributes': ['A1'] if with_strings else [],
            'audience_filter': 3, 'object_type': 'eMCDAUDIENCE',
            'protocol_short_name_references': ['V1', 'V2'] if with_strings else None}


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
    return typed('MCD_AUDIENCE', {'supplier': True, 'development': False,
                                  'manufacturing': True, 'after_sales': False,
                                  'after_market': True})


def request_part(body, short_name_path):
    """Value and request parameter part of a state transition action or precondition definition."""
    body.unicode('V').flag(short_name_path).ascii('P')
    return body


def name_block_body(body, filled=False, short_name=None):
    """Name block in the read order of MCD_DB_ENV_DATA_DESC; short_name fills only the short name."""
    if filled:
        return (body.unicode('Desc').unicode('Long').ascii('Short').ascii('DescId')
                .ascii('LongId').ascii('UID'))
    return body.unicode(None).unicode(None).ascii(short_name).ascii(None).ascii(None).ascii(None)


def map_body(body, entries):
    """One map of DB_STATE_CHART_DATA; entries is a list of (key, [element body or None])."""
    body.u16(len(entries))
    for key, elements in entries:
        body.ascii(key).u16(len(elements))
        for element in elements:
            if element is None:
                body.absent()
            else:
                body.nested(element[0], element[1])
    return body


def ecu_state_body(short_name, transitions=()):
    """Body of an MCD_DB_ECU_STATE; transitions are (name, object id, pool id)."""
    body = name_block_body(ObjectBytes(), short_name=short_name)
    body.u16(len(transitions))
    for name, object_id, pool_id in transitions:
        body.ascii(name).ascii(object_id).ascii(pool_id).u8(0)
    return body


def state_transition_body(short_name, source=None, target=None):
    """Body of an MCD_DB_ECU_STATE_TRANSITION; source and target are (object id, pool id) or None."""
    body = name_block_body(ObjectBytes(), short_name=short_name)
    for state in (source, target):
        object_id, pool_id = state or (None, None)
        body.ascii(object_id).ascii(pool_id).u8(0)
    return body.u8(0)


def state_chart_body(short_name, semantic, transitions=()):
    """Body of an MCD_DB_ECU_STATE_CHART without states; transitions are (name, object id, pool id)."""
    body = name_block_body(ObjectBytes(), short_name=short_name).ascii(semantic).u16(0).ascii(None)
    body.u16(len(transitions))
    for name, object_id, pool_id in transitions:
        body.ascii(name).ascii(object_id).ascii(pool_id).u8(0)
    return body


def state_transition_action_body(service_id=None, pool_id=None):
    """Body of an MCD_DB_STATE_TRANSITION_ACTION; without service_id the DiagCom reference is empty."""
    return request_part(diag_com_ref_body(ObjectBytes(), False, service_id, pool_id), False)


def state_chart_data_body(actions=()):
    """Body of a DB_STATE_CHART_DATA; actions are (transition short name, [action bodies])."""
    entries = [(transition, [('MCD_DB_STATE_TRANSITION_ACTION', action_body) for action_body in action_bodies])
               for transition, action_bodies in actions]
    return map_body(map_body(ObjectBytes(), entries), [])


def table_row_body(short_name, key):
    """Body of an MCD_DB_TABLE_PARAMETER (a table row) with the given key."""
    body = ObjectBytes().unicode(key).absent().u8(0).u8(0)
    body.unicode(None).unicode(None).ascii(short_name).ascii(None).ascii(None).ascii(None)
    return body.u8(0).u32(0).u8(0).u32(0).ascii(None).u8(1).u8(0xFF)


def table_body(short_name, rows=()):
    """Body of an MCD_DB_TABLE; rows are (map key, object id, pool id)."""
    body = (ObjectBytes().ascii(None).ascii(None).ascii(None).unicode(None).unicode(None)
            .ascii(short_name).u32(len(rows)))
    for map_key, object_id, pool_id in rows:
        body.unicode(map_key).ascii(object_id).ascii(pool_id).ascii(None)
    return body.ascii(None).u16(0).u8(0).u8(0)


def configuration_data_body(short_name, sdg_numbers=()):
    """Body of an MCD_DB_CONFIGURATION_DATA with empty collections (newest layout)."""
    body = (ObjectBytes().ascii(None).ascii(None).ascii(None).unicode(None).unicode(None)
            .ascii(short_name))
    body.u16(0).u32(0)
    if sdg_numbers:
        body.u8(1).u16(len(sdg_numbers))
        for number in sdg_numbers:
            body.u32(number)
    else:
        body.u8(0)
    return body.u32(0).u32(0).u32(0).flag(False).u8(0)


def data_record_body(short_name: str, parent: str | None, file_name: str | None) -> ObjectBytes:
    """Body of an MCD_DB_DATA_RECORD with coding data when file_name is not None."""
    body = (ObjectBytes().ascii(None).ascii(None).ascii(None).unicode(None).unicode(None)
            .ascii(short_name))
    body.absent().u8(0).u16(0).u8(0)
    if file_name is None:
        body.flag(False).absent()
    else:
        coding = (ObjectBytes().ascii(None).unicode(None).unicode(None).ascii(None).ascii(None).ascii(None)
                  .ascii(file_name).flag(False))
        body.flag(True).nested('MCD_DB_CODING_DATA', coding)
    body.u8(0).ascii(None).ascii(None).u32(0).ascii(parent)
    return body.u8(0).u8(0)


def sdg_element_body(text_id='', content='', semantic_information=''):
    """Body of a valid MCD_DB_SPECIAL_DATA_ELEMENT; an empty text is a word without the top bit."""
    body = ObjectBytes()
    for text in (text_id, content, semantic_information):
        if text:
            body.native_ascii(text)
        else:
            body.u32(0)
    return body


def sdg_group_body(items=(), caption=None, semantic_information=''):
    """Body of a valid MCD_DB_SPECIAL_DATA_GROUP; items are (type name, body) or None."""
    body = ObjectBytes().u32(len(items))
    for item in items:
        if item is None:
            body.absent()
        else:
            body.nested(*item)
    if caption is None:
        body.u8(0)
    else:
        object_key, pool_name = caption
        body.u8(1).u32(object_key).ascii(pool_name)
    if semantic_information:
        body.native_ascii(semantic_information)
    else:
        body.u32(0)
    return body
