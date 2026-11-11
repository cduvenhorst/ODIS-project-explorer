from common_utils import common_loaders


def load(stream):
    obj = common_loaders.loadStandardNameBlock(stream)
    
    obj['is_compressed_size_available'] = bool(stream.loadOneByteType())
    obj['compressed_size'] = stream.loadNumericType(4)
    obj['uncompressed_size'] = stream.loadNumericType(4)
    obj['source_start_address'] = stream.loadNumericType(4)
    obj['source_end_address'] = stream.loadNumericType(4)
    obj['binary_start_address'] = stream.loadNumericType(4)
    
    # No setter; name chosen for the flag, not taken from the kernel
    obj['has_filtered_ranges'] = bool(stream.loadOneByteType())
    obj['filtered_ranges_for_binary_data'] = None
    if obj['has_filtered_ranges']:
        # The meaning of the two numbers is not named by the kernel
        obj['filtered_ranges_for_binary_data'] = []
        for i in range(stream.loadNumericType(2)):
            first = stream.loadNumericType(4)
            second = stream.loadNumericType(4)
            obj['filtered_ranges_for_binary_data'].append([first, second])
    
    return obj
