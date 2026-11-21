"""Random access to the records of a pool's SDG key and data files."""
import gzip
import os
import struct

KEY_ENTRY_SIZE = 8


class SdgFile:
    """Records of SDG_<pool>.dix.gz, addressed through SDG_<pool>.kix.gz."""

    def __init__(self, keys, data):
        self._keys = keys
        self._data = data
        self.record_count = len(keys) // KEY_ENTRY_SIZE

    @staticmethod
    def open(project_folder_path, pool_id):
        ### project_folder_path: folder holding the SDG files
        ### pool_id: pool name, e.g. "A.sd"
        ### returns None if the data file is missing; a missing key file raises FileNotFoundError
        base = os.path.join(project_folder_path, 'SDG_%s' % pool_id)
        data_path = base + '.dix.gz'
        if not os.path.isfile(data_path):
            return None
        with gzip.open(base + '.kix.gz', 'rb') as handle:
            keys = handle.read()
        with gzip.open(data_path, 'rb') as handle:
            data = handle.read()
        return SdgFile(keys, data)

    def record(self, number):
        ### number: record number, starting at 1
        ### returns the record bytes, or None outside 1..record_count
        if not 1 <= number <= self.record_count:
            return None
        start = (number - 1) * KEY_ENTRY_SIZE
        offset, length = struct.unpack_from('<II', self._keys, start)
        return bytearray(self._data[offset:offset + length])
