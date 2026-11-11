from common_utils import common_loaders


def load(stream):
    obj = common_loaders.loadStandardNameBlock(stream)
    
    obj['is_checksum_algorithm_available'] = bool(stream.loadOneByteType())
    obj['checksum_algorithm'] = stream.loadAsciiString()[0]
    obj['checksum_result'] = common_loaders.loadMCDValueFromObjectStream(stream)
    
    # The sizes and addresses are in the stream even when their flag is 0
    obj['is_compressed_size_available'] = bool(stream.loadOneByteType())
    obj['compressed_size'] = stream.loadNumericType(4)
    obj['uncompressed_size'] = stream.loadNumericType(4)
    
    obj['is_fill_byte_available'] = bool(stream.loadOneByteType())
    obj['fill_byte'] = common_loaders.loadBytefieldFromObjectStream(stream)
    
    obj['source_start_address'] = stream.loadNumericType(4)
    obj['source_end_address'] = stream.loadNumericType(4)
    
    return obj
