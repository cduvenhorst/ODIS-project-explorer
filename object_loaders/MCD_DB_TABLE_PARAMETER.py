from object_loaders import MCD_DB_PARAMETER
from classes import DbObject
from classes.DbStream import DbStream


from common_utils import common_loaders

STREAM_BEGIN = bytes.fromhex('233E00')  # '#>' 0
STREAM_END = bytes.fromhex('233E01')  # '#>' 1
STREAM_SEPARATOR = bytes.fromhex('233C00')  # '#<' 0
MARKER_LENGTH = 3


def _expect_marker(stream: DbStream, marker: bytes) -> None:
    data = stream.read(MARKER_LENGTH)
    if data != marker:
        raise RuntimeError('Unexpected marker in named streams: {}'.format(DbStream.bytearray_to_string(data)))


def load_named_streams(stream: DbStream) -> dict[str, object]:
    # Named streams are read by name, as the kernel does: A = IsApiExecutable (1 byte),
    # B = PreConditionStates (named attributed references).
    # The length check assumes the table parameter is a standalone object: only the
    # object end marker (3 bytes, not consumed here) may remain after the last stream.
    streams: dict[str, object] = {}
    if stream.get_length() == MARKER_LENGTH:
        return streams
    _expect_marker(stream, STREAM_BEGIN)
    while True:
        name = chr(stream.read(1)[0])
        match name:
            case 'A':
                streams[name] = bool(stream.loadOneByteType())
            case 'B':
                streams[name] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(
                    stream, common_loaders.loadDbAttributedObjectReference)
            case _:
                raise RuntimeError('Unknown named stream: {}'.format(name))
        _expect_marker(stream, STREAM_END)
        if stream.get_length() == MARKER_LENGTH:
            return streams
        _expect_marker(stream, STREAM_SEPARATOR)


def load(stream):
    obj = {}
    
    obj['key'] = stream.loadUnicodeString()[0]
    
    obj['audience_state'] = DbObject.load_object_from_stream_if_exists(stream) # MCDAudienceImpl
    
    # DisabledAdditionalAudiences, EnabledAdditionalAudiences: presence byte, then named references
    obj['disabled_additional_audiences'] = None
    if stream.loadOneByteType():
        obj['disabled_additional_audiences'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_reference, False)
    
    obj['enabled_additional_audiences'] = None
    if stream.loadOneByteType():
        obj['enabled_additional_audiences'] = common_loaders.loadNamedObjectReferenceCollectionFromObjectStream(stream, common_loaders.load_reference, False)
    
    obj['parameter'] = {'#OBJECT_TYPE': 'MCD_DB_PARAMETER'}
    obj['parameter'].update(MCD_DB_PARAMETER.load(stream))
    
    streams = load_named_streams(stream)
    obj['is_api_executable'] = streams.get('A', True)
    obj['pre_condition_state_refs'] = streams.get('B')
    
    return obj
