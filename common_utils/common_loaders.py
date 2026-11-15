import struct
from collections.abc import Callable
from classes.DbStream import DbStream
from classes import DbObject
from common_utils import enum_converters


# Third word of a named object reference
def loadNamedReferenceThirdWord(stream: DbStream) -> str | int | None:
    """Read the third word of a named object reference: a string from database version 0012, else a number."""
    # kernel: below database version 0012 the third word is a number; 0xFFFFFFFF means no number
    if stream.is_database_version_at_least(12):
        return stream.loadAsciiString()[0]
    return stream.loadNumericType(4)


# "Standard" loader for DbObjectReference
def load_reference(stream, third_string = True):
    obj = {}
    
    obj['object_id'] = stream.loadAsciiString()[0]
    obj['pool_id'] = stream.loadAsciiString()[0]
    if third_string:
        obj['object_id2'] = loadNamedReferenceThirdWord(stream)
    
    return obj


# Custom loader for DbDiagComObjectReference
def load_DbDiagComObjectReference(stream, dummy = 0):
    # kernel: DbDiagComObjectReference extends the attributed reference; the base part is stored in the same object
    item = loadDbAttributedObjectReference(stream)
    
    # kernel: setAudienceFilter
    item['audience_filter'] = stream.loadNumericType(1)
    # kernel: the object type is stored without a check
    item['object_type'] = enum_converters.enum_name_or_number(enum_converters.get_MCDObjectType, stream.loadEnumMediumRange())
    
    # kernel: isProtocolSnRefsAvailable, getProtocolSnRefs
    item['protocol_short_name_references'] = loadAsciiStringVectorFromObjectStream(stream) if stream.loadOneByteType() else None
    
    return item


# Named reference
def _loadNamedObjectReferenceWithNameWord(stream, reference_loader, reference_loader_argument):
    """Read a named reference; returns it together with the raw name word (0 = no name)."""
    obj = {}
    
    obj['name'], name_word = stream.loadAsciiString()
    obj['reference'] = reference_loader(stream, reference_loader_argument)
    
    return obj, name_word


def loadNamedObjectReferenceFromObjectStream(stream, reference_loader = load_reference, reference_loader_argument = False):
    return _loadNamedObjectReferenceWithNameWord(stream, reference_loader, reference_loader_argument)[0]


# Collection of named references
def loadNamedObjectReferenceCollectionFromObjectStream(stream, reference_loader = load_reference, reference_loader_argument = False):
    obj = []
    
    collection_items = stream.loadNumericType(2)
    for i in range(collection_items):
        item, name_word = _loadNamedObjectReferenceWithNameWord(stream, reference_loader, reference_loader_argument)
        # kernel: a named reference collection rejects an entry without name; the string-to-reference map does not check
        if name_word == 0:
            raise RuntimeError('Named reference without name')
        obj.append(item)
    
    return obj


# Kernel map and set helpers
def put_map_entry(entries: list[dict], positions: dict[object, int], kernel_key: object, entry: dict) -> None:
    """Add an entry to a map kept as a list in read order; a later entry with a known key replaces the earlier one in its place."""
    if kernel_key in positions:
        entries[positions[kernel_key]] = entry
    else:
        positions[kernel_key] = len(entries)
        entries.append(entry)


def add_set_value(values: list, seen: set, kernel_key: object, value: object) -> None:
    """Add a value to a set kept as a list in read order; a value with a known key is dropped."""
    if kernel_key not in seen:
        seen.add(kernel_key)
        values.append(value)


def kernel_string_key(loaded: tuple[str | None, int | None]) -> object:
    """Return the kernel's comparison key of a loaded string: its word, or its text when it is stored in the object."""
    text, word = loaded
    return text if word is None else word


# ASCII string vector
def loadAsciiStringVectorFromObjectStream(stream):
    obj = []
    
    vector_items = stream.loadNumericType(2)
    for i in range(vector_items):
        obj.append(stream.loadAsciiString()[0])
    
    return obj


# ASCII string vector map (key + string vector)
def loadStringVectorMapFromObjectStream(stream):
    obj = []
    positions = {}
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        
        key = stream.loadAsciiString()
        item['map_key'] = key[0]
        item['strings'] = loadAsciiStringVectorFromObjectStream(stream)
        
        put_map_entry(obj, positions, kernel_string_key(key), item)
    
    return obj


# String-to-reference map (key + reference)
def loadStringToReferenceMap(stream, is_DbDiagComObjectReference = False, is_three_word_reference = False, is_attributed_reference = False):
    obj = []
    positions = {}
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        
        key = stream.loadAsciiString()
        item['map_key'] = key[0]
        
        if is_DbDiagComObjectReference:
            item['reference'] = load_DbDiagComObjectReference(stream)
        elif is_three_word_reference:
            item['reference'] = load_reference(stream, True)
        elif is_attributed_reference:
            item['reference'] = loadDbAttributedObjectReference(stream)
        else:
            item['reference'] = load_reference(stream, False)
        
        put_map_entry(obj, positions, kernel_string_key(key), item)
    
    return obj


# Attributed reference (reference + attributes)
def loadDbAttributedObjectReference(stream, dummy = 0):
    obj = {}
    
    obj['object_id'] = stream.loadAsciiString()[0]
    obj['pool_id'] = stream.loadAsciiString()[0]
    
    # kernel: getAttributeCount and getSemantic read this vector
    obj['attributes'] = []
    counter = stream.loadOneByteType()
    for i in range(counter):
        obj['attributes'].append(stream.loadAsciiString()[0])
    
    return obj


# DbValueAttributedObjectReference
def loadDbValueAttributedObjectReference(stream: DbStream, dummy: int = 0) -> dict[str, object]:
    """Read an attributed object reference followed by an MCD value."""
    obj = loadDbAttributedObjectReference(stream)
    obj['value'] = loadMCDValueFromObjectStream(stream)
    
    return obj


# MCDValue (data type + value)
def loadMCDValueFromObjectStream(stream):
    # kernel: value types and sizes as read by the kernel
    obj = {}
    
    obj['data_type'] = enum_converters.get_mcd_value_data_type_enum(stream.loadNumericType(1))
    
    match obj['data_type']:
        case 'eA_ASCIISTRING':
            obj['value'] = stream.loadAsciiString()[0]
        case 'eA_UNICODE2STRING':
            obj['value'] = stream.loadUnicodeString()[0]
        case 'eA_FLOAT32':
            obj['value'] = struct.unpack('<f', stream.read(4))[0]
        case 'eA_FLOAT64':
            obj['value'] = struct.unpack('<d', stream.read(8))[0]
        case 'eA_INT32':
            obj['value'] = stream.loadNumericType(4, True)
        case 'eA_UINT32':
            obj['value'] = stream.loadNumericType(4)
        case 'eA_BITFIELD'| 'eA_BYTEFIELD':
            obj['value'] = bytearray()
            if stream.loadOneByteType() != 0:
                size = stream.loadNumericType(2)
                obj['value'] = stream.read(size)
        case 'eA_INT16':
            obj['value'] = stream.loadNumericType(2, True)
        case 'eA_INT64':
            obj['value'] = stream.loadNumericType(8, True)
        case 'eA_INT8':
            obj['value'] = stream.loadNumericType(1, True)
        case 'eA_UINT16':
            obj['value'] = stream.loadNumericType(2)
        case 'eA_UINT64':
            obj['value'] = stream.loadNumericType(8)
        case 'eA_UINT8':
            obj['value'] = stream.loadNumericType(1)
        case 'eA_BOOLEAN':
            obj['value'] = stream.loadNumericType(1) != 0
        case 'eNO_TYPE':
            return None
        case _:
            raise RuntimeError('Unknown how to retrieve MCD value with type {}'.format(obj['data_type']))
    
    return obj


def loadStandardNameBlock(stream: DbStream) -> dict[str, str | None]:
    """Read the six standard name fields in stream order (unknown pool keys give None); raises RuntimeError if the stream ends early."""
    obj: dict[str, str | None] = {}
    
    obj['short_name'] = stream.loadAsciiString()[0]
    obj['long_name'] = stream.loadUnicodeString()[0]
    obj['description'] = stream.loadUnicodeString()[0]
    
    obj['unique_object_id'] = stream.loadAsciiString()[0]
    obj['long_name_id'] = stream.loadAsciiString()[0]
    obj['description_id'] = stream.loadAsciiString()[0]
    
    return obj


# Bytefield
def loadBytefieldFromObjectStream(stream):
    obj = bytearray()
    
    if stream.loadOneByteType() != 0:
        size = stream.loadNumericType(4)
        obj = stream.read(size)
    
    return obj


# Collection of references (for SDGs, uncommon)
def loadObjectReferenceCollectionFromObjectStream_MCDDbSpecialDataGroupImplRef(stream):
    obj = []
    
    collection_items = stream.loadNumericType(2)
    for i in range(collection_items):
        item = {}
        item['object_id'] = stream.loadNumericType(4) # asam::database::base::IDbPersistentObject::setDbObjectID
        obj.append(item)
    
    return obj


# ASCII-to-Unicode string map (key + value)
def loadAsciiToUnicodeStringMap(stream: DbStream) -> list[dict[str, str | None]]:
    """Read a u16-counted map of ASCII keys to Unicode values, in stream order."""
    obj = []
    positions = {}
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        
        key = stream.loadAsciiString()
        item['map_key'] = key[0]
        item['value'] = stream.loadUnicodeString()[0]
        
        put_map_entry(obj, positions, kernel_string_key(key), item)
    
    return obj


# Service protocol parameters map (key + optional MCDDbRequestParametersImpl)
def loadServiceProtocolParametersMap(stream: DbStream) -> list[dict[str, object]]:
    """Read a u16-counted map of ASCII keys to optional request parameters objects, in stream order."""
    obj = []
    positions = {}
    
    # kernel: std::map ordered by the string number of the key; a later duplicate key replaces the earlier entry; kept in read order
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        
        key = stream.loadAsciiString()
        item['map_key'] = key[0]
        # kernel: fails when an entry has no parameters object; kept readable for VW projects
        item['service_protocol_parameters'] = DbObject.load_object_from_stream_if_exists(stream)
        
        put_map_entry(obj, positions, kernel_string_key(key), item)
    
    return obj


# Presence byte, then a named reference collection (DisabledAdditionalAudiences, EnabledAdditionalAudiences, ...)
def loadAdditionalAudiencesFromObjectStream(stream: DbStream) -> list[dict[str, object]]:
    """Read a presence byte and, when it is set, a named object reference collection."""
    if stream.loadOneByteType():
        return loadNamedObjectReferenceCollectionFromObjectStream(stream, load_reference, False)
    # kernel: an absent collection reads as an empty one
    return []


STREAM_BEGIN = bytes.fromhex('233E00')  # '#>' 0
STREAM_SEPARATOR = bytes.fromhex('233C00')  # '#<' 0
MARKER_LENGTH = 3


def _expect_marker(stream: DbStream, marker: bytes) -> None:
    data = stream.read(MARKER_LENGTH)
    if data != marker:
        raise RuntimeError('Unexpected marker in named streams: {}'.format(DbStream.bytearray_to_string(data)))


def _skip_to_next_named_stream(stream: DbStream) -> bool:
    """Skip the rest of the current named stream; False means no further named stream follows.

    Reads up to and including the next separator and returns True. Without a following separator
    (or when the next separator is the object end marker) it reads up to the object end marker
    and returns False.
    """
    if stream.get_length() < MARKER_LENGTH:
        return False
    end = stream.find(STREAM_SEPARATOR)
    if end < 0 or end == stream.get_length() - MARKER_LENGTH:
        stream.read(stream.get_length() - MARKER_LENGTH)
        return False
    stream.read(end)
    _expect_marker(stream, STREAM_SEPARATOR)
    return True


def loadNamedStreams(stream: DbStream, readers: dict[str, Callable[[DbStream], object]]) -> dict[str, object]:
    """Read the named streams that follow the fixed fields of an object, as the kernel does.

    Each stream is a one-character name followed by the data of its reader.
    The length check assumes the object is standalone: only the object end marker
    (3 bytes, not consumed here) may remain after the last stream.
    """
    streams: dict[str, object] = {}
    if stream.get_length() == MARKER_LENGTH:
        return streams
    # kernel: an object without the start marker has no named streams; kept as an error for VW projects
    _expect_marker(stream, STREAM_BEGIN)
    while True:
        name = chr(stream.read(1)[0])
        if name in readers:
            # kernel: does not register a named stream without a following separator; kept readable for VW projects
            streams[name] = readers[name](stream)
        # kernel: unknown named streams are ignored, and so are bytes a reader leaves in a named stream
        # kernel: a part without a following separator ends the split without error
        if not _skip_to_next_named_stream(stream):
            return streams
