import struct
from collections.abc import Callable
from classes.DbStream import DbStream
from common_utils import enum_converters


# "Standard" loader for DbObjectReference
def load_reference(stream, third_string = True, string_vector = False):
    obj = {}
    
    obj['object_id'] = stream.loadAsciiString()[0]
    obj['pool_id'] = stream.loadAsciiString()[0]
    if third_string:
        obj['object_id2'] = stream.loadAsciiString()[0]
    
    if string_vector:
        obj['strings'] = []
        counter = stream.loadOneByteType()
        for i in range(counter):
            obj['strings'].append(stream.loadAsciiString()[0])
    
    return obj


# Custom loader for DbDiagComObjectReference
def load_DbDiagComObjectReference(stream, dummy = 0):
    item = {}
    
    item['attrib_obj_ref'] = loadDbAttributedObjectReference(stream)
    
    item['number'] = stream.loadNumericType(1)
    item['mcd_object_type'] = enum_converters.get_MCDObjectType(stream.loadEnumMediumRange())
    
    if stream.loadOneByteType():
        item['strings'] = loadAsciiStringVectorFromObjectStream(stream)
    
    return item


# Named reference
def loadNamedObjectReferenceFromObjectStream(stream, reference_loader = load_reference, reference_loader_argument = False):
    obj = {}
    
    obj['name'] = stream.loadAsciiString()[0]
    obj['reference'] = reference_loader(stream, reference_loader_argument)
    
    return obj


# Collection of named references
def loadNamedObjectReferenceCollectionFromObjectStream(stream, reference_loader = load_reference, reference_loader_argument = False):
    obj = []
    
    collection_items = stream.loadNumericType(2)
    for i in range(collection_items):
        obj.append(loadNamedObjectReferenceFromObjectStream(stream, reference_loader, reference_loader_argument))
    
    return obj


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
    
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        
        item['map_key'] = stream.loadAsciiString()[0]
        item['strings'] = loadAsciiStringVectorFromObjectStream(stream)
        
        obj.append(item)
    
    return obj


# String-to-reference map (key + reference)
def loadStringToReferenceMap(stream, string_vector_in_reference = False, is_DbDiagComObjectReference = False, is_NamedObjectReference = False):
    obj = []
    
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        
        item['map_key'] = stream.loadAsciiString()[0]
        
        if is_DbDiagComObjectReference:
            item['reference'] = load_DbDiagComObjectReference(stream)
        elif is_NamedObjectReference:
            item['reference'] = loadNamedObjectReferenceFromObjectStream(stream)
        else:
            item['reference'] = load_reference(stream, False, string_vector_in_reference)
        
        obj.append(item)
    
    return obj


# Attributed reference (reference + strings)
def loadDbAttributedObjectReference(stream, dummy = 0):
    obj = {}
    
    obj['object_id'] = stream.loadAsciiString()[0]
    obj['pool_id'] = stream.loadAsciiString()[0]
    
    obj['strings'] = []
    counter = stream.loadOneByteType()
    for i in range(counter):
        obj['strings'].append(stream.loadAsciiString()[0])
    
    return obj


# DbValueAttributedObjectReference
def loadDbValueAttributedObjectReference(stream: DbStream, dummy: int = 0) -> dict[str, object]:
    """Read an attributed object reference followed by an MCD value."""
    obj = loadDbAttributedObjectReference(stream)
    obj['value'] = loadMCDValueFromObjectStream(stream)
    
    return obj


# MCDValue (data type + value)
def loadMCDValueFromObjectStream(stream):
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
        case 'eNO_TYPE':
            return None
        case _:
            raise RuntimeError('Unknown how to retrieve MCD value with type {}'.format(obj['data_type']))
    
    return obj


# Standard name block: short name, long name, description, then the three ids
def loadStandardNameBlock(stream: DbStream) -> dict[str, str | None]:
    """Read the six standard name fields in stream order; raises like the string readers on a bad key."""
    obj = {}
    
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
    
    map_items = stream.loadNumericType(2)
    for i in range(map_items):
        item = {}
        
        item['map_key'] = stream.loadAsciiString()[0]
        item['value'] = stream.loadUnicodeString()[0]
        
        obj.append(item)
    
    return obj


# Presence byte, then a named reference collection (DisabledAdditionalAudiences, EnabledAdditionalAudiences, ...)
def loadAdditionalAudiencesFromObjectStream(stream: DbStream) -> list[dict[str, object]] | None:
    """Read a presence byte and, when it is set, a named object reference collection."""
    if stream.loadOneByteType():
        return loadNamedObjectReferenceCollectionFromObjectStream(stream, load_reference, False)
    return None


STREAM_BEGIN = bytes.fromhex('233E00')  # '#>' 0
STREAM_END = bytes.fromhex('233E01')  # '#>' 1
STREAM_SEPARATOR = bytes.fromhex('233C00')  # '#<' 0
MARKER_LENGTH = 3


def _expect_marker(stream: DbStream, marker: bytes) -> None:
    data = stream.read(MARKER_LENGTH)
    if data != marker:
        raise RuntimeError('Unexpected marker in named streams: {}'.format(DbStream.bytearray_to_string(data)))


def loadNamedStreams(stream: DbStream, readers: dict[str, Callable[[DbStream], object]]) -> dict[str, object]:
    """Read the named streams that follow the fixed fields of an object, as the kernel does.

    Each stream is a one-character name followed by the data of its reader.
    The length check assumes the object is standalone: only the object end marker
    (3 bytes, not consumed here) may remain after the last stream.
    """
    streams: dict[str, object] = {}
    if stream.get_length() == MARKER_LENGTH:
        return streams
    _expect_marker(stream, STREAM_BEGIN)
    while True:
        name = chr(stream.read(1)[0])
        if name not in readers:
            raise RuntimeError('Unknown named stream: {}'.format(name))
        streams[name] = readers[name](stream)
        _expect_marker(stream, STREAM_END)
        if stream.get_length() == MARKER_LENGTH:
            return streams
        _expect_marker(stream, STREAM_SEPARATOR)
