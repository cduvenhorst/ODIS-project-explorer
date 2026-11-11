# Not actually a class, but whatever


import contextlib
import struct

from common_utils import diagnostics
from common_utils import enum_converters
from classes.DbStream import DbStream
from classes.StringStorage import StringStorage

# This imports all loaders defined in the `__all__` list of the file "object_loaders/__init__.py"
# If a new object loader is to be implemented, it must be added there
from object_loaders import *


def load_object_from_stream(stream):
    # The first 2 bytes of an Object's data are an enum which represents the Object's type
    # It will be used for selecting a loader to parse the data
    object_type_enum = stream.loadEnumMediumRange()
    object_type = enum_converters.get_object_type_enum(object_type_enum)
    
    # All loaders were imported by the wildcard import, look for the appropriate loader in the global namespace
    module = globals().get(object_type)
    if module is None:
        raise RuntimeError('Unknown object ({} - {:04X}), cannot load (size {})'.format(object_type, object_type_enum, stream.get_length()))
    
    # Call the `load` method
    obj = module.load(stream)
    
    # An Object will often be loaded as a dictionary
    # If it has a "plural" type, it will be loaded as a list of dictionaries
    # Dictionaries get an "artificial" attribute, with key '#OBJECT_TYPE' (first key)
    ret = obj
    if type(obj) is dict:
        ret = {'#OBJECT_TYPE': object_type}
        ret.update(obj)
    return ret


def load_object_from_stream_if_exists(stream):
    # Load the flag
    object_exists = stream.loadOneByteType()
    
    # The flag is a byte, but it is only allowed to be 0 or 1
    # Other values mean the data was read incorrectly, and the current position didn't really represent such a flag
    if object_exists == 1:
        return load_object_from_stream(stream)
    elif object_exists != 0:
        raise RuntimeError('Invalid object existance flag value ({})'.format(object_exists))
    
    # Return None if the Object isn't present
    return None


def load_object(object_data, string_storage, strict=False):
    # Construct a DbStream instance from the binary data
    stream = DbStream(object_data, string_storage)
    
    if not strict:
        # Load and return the Object
        return load_object_from_stream(stream)
    
    # In strict mode leftover bytes are an error, so the destructor must not print them as well
    stream.report_unread_on_delete = False
    with diagnostics.strict_reading():
        obj = load_object_from_stream(stream)
        
        # Exactly the 3 end bytes must remain
        remaining = stream.get_length() - 3
        if remaining != 0:
            object_type = enum_converters.get_object_type_enum(stream.get_object_type_enum())
            raise diagnostics.UnreadBytesError(object_type, remaining)
    return obj


def load_object_from_parts(parts: list[bytearray], string_storage: StringStorage, strict: bool = False) -> dict | list:
    """Load an object from the parts of its record.

    One part is loaded like `load_object`. Several parts of a type whose loader offers
    `load_big_data` are loaded as a big data record; several parts of any other type are
    concatenated and loaded like one part. Raises `diagnostics.UnreadBytesError` in strict
    mode if the first part of a big data record holds more than the type code.
    The passed parts are consumed: the stream reads the first part in place.
    """
    if len(parts) > 1:
        # The kernel reads only the first part of a big data record as an object (type code,
        # no end marker) and fetches the other parts as raw content on demand
        object_type_enum = struct.unpack('<H', parts[0][:2])[0]
        object_type = enum_converters.get_object_type_enum(object_type_enum)
        module = globals().get(object_type)
        if module is not None and hasattr(module, 'load_big_data'):
            return _load_big_data_object(object_type, module, parts, string_storage, strict)
        return load_object(bytearray().join(parts), string_storage, strict)
    return load_object(parts[0], string_storage, strict)


def _load_big_data_object(object_type: str, module, parts: list[bytearray], string_storage: StringStorage,
                          strict: bool) -> dict:
    """Load a big data record: the first part as object, the others as content for `module.load_big_data`."""
    stream = DbStream(parts[0], string_storage)
    # Leftover bytes of the first part are reported below, not by the destructor
    stream.report_unread_on_delete = False
    with diagnostics.strict_reading() if strict else contextlib.nullcontext():
        stream.loadEnumMediumRange()
        obj = module.load_big_data(stream, parts[1:])
        if strict and stream.get_length() != 0:
            raise diagnostics.UnreadBytesError(object_type, stream.get_length())
        if not strict and stream.get_length() != 0:
            print('Object stream ({:04X}) not empty: '.format(stream.get_object_type_enum())
                  + DbStream.bytearray_to_string(stream.read(stream.get_length())))
    ret = {'#OBJECT_TYPE': object_type}
    ret.update(obj)
    return ret
