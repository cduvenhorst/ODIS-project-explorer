import struct
from classes.StringStorage import StringStorage


class DbStream:
    @staticmethod
    def bytearray_to_string(ba):
        return ''.join('{:02X} '.format(x) for x in ba)
    
    
    # Constructor
    ### data           = bytearray object with complete Object data, as read from the .db file and decompressed with zlib
    ### string_storage = instance of StringStorage class, loaded from the current Project
    def __init__(self, data, string_storage):
        # Parameter checking
        if type(data) is not bytearray:
            raise RuntimeError('DbStream needs bytearray, not {}'.format(type(data)))
        if type(string_storage) is not StringStorage:
            raise RuntimeError('DbStream needs StringStorage, not {}'.format(type(string_storage)))
        
        # Private variables
        self.__stream = data
        self.__string_storage = string_storage
        self.report_unread_on_delete = True
        
        # Store the Object's type enum (first 2 bytes)
        self.__stream_object_type = struct.unpack('<H', self.__stream[:2])[0]
    
    
    # Check whether the project's database version is at least the given one
    # * a project without a known database version counts as the newest layout
    def is_database_version_at_least(self, version: int) -> bool:
        database_version = self.__string_storage.database_version
        return database_version is None or database_version >= version
    
    
    # Destructor
    def __del__(self):
        # After an Object is fully loaded, its stream must be '#>\0' (3 characters)
        # If more than 3 bytes are present, some data was left unparsed, print this to the console
        if self.report_unread_on_delete and self.get_length() > 3:
            print('Object stream ({:04X}) not empty: {}'.format(self.__stream_object_type, DbStream.bytearray_to_string(self.__stream[:-3])))
    
    
    # Converter to string (returns current stream bytes as formatted string)
    def __str__(self):
        return DbStream.bytearray_to_string(self.__stream)
    
    
    # Getter for the Object's type enum (first 2 bytes of the data)
    def get_object_type_enum(self):
        return self.__stream_object_type
    
    
    # Getter for amount of bytes remaining in the stream
    def get_length(self):
        return len(self.__stream)
    
    
    # Read an arbitrary amount of bytes, returned as a bytearray
    def read(self, count):
        # Parameter checking
        if count > len(self.__stream):
            raise RuntimeError('Cannot read {} bytes, only have {}'.format(count, len(self.__stream)))
        
        # Read the requested amount of bytes and remove them from the stream
        # (slice deletion removes the bytes in one step instead of one by one)
        data = self.__stream[:count]
        del self.__stream[:count]
        return data
    
    
    # Load 2 bytes, usually used for enums
    def loadEnumMediumRange(self):
        return struct.unpack('<H', self.read(2))[0]
    
    
    # Load 1 byte, usually used for enums
    def loadEnumSmallRange(self):
        return struct.unpack('<B', self.read(1))[0]
    
    
    # Load 1 byte, usually used for flags and counters
    def loadOneByteType(self):
        return struct.unpack('<B', self.read(1))[0]
    
    
    # Load 1/2/4/8 bytes, interpreted as (un)signed integer
    def loadNumericType(self, size, signed = False):
        if size == 1:
            return struct.unpack('<B' if not signed else '<b', self.read(size))[0]
        elif size == 2:
            return struct.unpack('<H' if not signed else '<h', self.read(size))[0]
        elif size == 4:
            return struct.unpack('<I' if not signed else '<i', self.read(size))[0]
        elif size == 8:
            return struct.unpack('<Q' if not signed else '<q', self.read(size))[0]
        else:
            raise RuntimeError('Numeric type can only have size 1/2/4/8, not {}'.format(size))
    
    
    # Load 8 bytes, interpreted as double
    def loadDoubleType(self):
        return struct.unpack('<d', self.read(8))[0]
    
    
    # Load a string given by a 4-byte word: a string pool key, or the string itself
    # * the kernel treats a set top bit as the length of a string stored in the object itself;
    #   pool hashes are always below 0x80000000
    # * 0xFFFFFFFF marks an empty string reference in older databases; read as a length it would
    #   exceed any object, so it keeps the pool lookup
    # * returns (string, key); key is None for a string stored in the stream
    def __load_string(self, pool_lookup, bytes_per_unit, encoding):
        word = self.loadNumericType(4)
        if word & 0x80000000 and word != 0xFFFFFFFF:
            return self.read(bytes_per_unit * (word & 0x7FFFFFFF)).decode(encoding), None
        return pool_lookup(word), word
    
    
    # Load an ASCII string: string pool key (returned as (string, key)) or string stored in the stream (key None)
    def loadAsciiString(self):
        return self.__load_string(self.__string_storage.get_ascii_string, 1, 'cp1252')
    
    
    # Load a Unicode string: string pool key (returned as (string, key)) or string stored in the stream (key None)
    def loadUnicodeString(self):
        return self.__load_string(self.__string_storage.get_unicode_string, 2, 'utf-16-le')
    
    
    # Load a string stored in the object itself, introduced by a 4-byte word
    # * kernel: a set top bit makes the low 31 bits the length (in bytes per unit, see below) and the string follows;
    #   without the top bit the string is empty and nothing more is read, whatever the remaining bits are
    def __load_native_string(self, bytes_per_unit, encoding):
        word = self.loadNumericType(4)
        if word & 0x80000000:
            return self.read(bytes_per_unit * (word & 0x7FFFFFFF)).decode(encoding)
        return ''
    
    
    # Load a native ASCII string (length in bytes)
    def loadNativeAsciiString(self):
        return self.__load_native_string(1, 'cp1252')
    
    
    # Load a native Unicode string (length in UTF-16 code units); a leading byte order mark is kept
    def loadNativeUnicodeString(self):
        return self.__load_native_string(2, 'utf-16-le')
