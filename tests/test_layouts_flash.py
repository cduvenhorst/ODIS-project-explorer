"""Layout tests for the flash data loaders.

Upstream has no loaders for these types; every body follows the kernel read order.
"""
import shutil
import struct
import tempfile
import unittest

from classes import DbObject
from classes.ObjectLoader import ObjectLoader
from classes.PBL import default_library_path
from classes.PblRecordManager import PblRecordManager
from classes.StringStorage import StringStorage
from common_utils import diagnostics
from object_loaders import DB_INLINE_FLASH_DATA, MCD_DB_FLASH_DATA
from tests import support
from tests.support import REPOSITORY_ROOT, ObjectBytes, typed

LIBRARY = default_library_path(REPOSITORY_ROOT)


def type_code():
    return bytearray(struct.pack('<H', support.object_type_code('DB_INLINE_FLASH_DATA')))


class InlineFlashDataTests(unittest.TestCase):
    def test_db_inline_flash_data_minimal(self):
        result = support.load('DB_INLINE_FLASH_DATA', ObjectBytes().u32(0))
        self.assertEqual(result, {'#OBJECT_TYPE': 'DB_INLINE_FLASH_DATA', 'is_big_data': False,
                                  'inline_flash_data_length': 0})

    def test_db_inline_flash_data_all_branches(self):
        single = support.load('DB_INLINE_FLASH_DATA', ObjectBytes().native_ascii('0A1B'))
        self.assertEqual(single, {'#OBJECT_TYPE': 'DB_INLINE_FLASH_DATA', 'is_big_data': False,
                                  'inline_flash_data_length': 4})
        big = DbObject.load_object_from_parts(
            [type_code(), bytearray(b'0A1B'), bytearray(b'2C')], support.string_storage([], []), strict=True)
        self.assertEqual(big, {'#OBJECT_TYPE': 'DB_INLINE_FLASH_DATA', 'is_big_data': True,
                               'inline_flash_data_length': 6})

    def test_big_data_first_part_with_extra_bytes_is_unread(self):
        parts = [type_code() + b'\x00', bytearray(b'0A1B')]
        with self.assertRaises(diagnostics.UnreadBytesError) as context:
            DbObject.load_object_from_parts(parts, support.string_storage([], []), strict=True)
        self.assertEqual(context.exception.remaining, 1)

    def test_content_bytes_big_data(self):
        parts = [type_code(), bytearray(b'0A1B'), bytearray(b'2c')]
        self.assertEqual(DB_INLINE_FLASH_DATA.content_bytes(parts), b'\x0a\x1b\x2c')

    def test_content_bytes_single_part(self):
        data = ObjectBytes().native_ascii('FF00').build('DB_INLINE_FLASH_DATA')
        self.assertEqual(DB_INLINE_FLASH_DATA.content_bytes([data]), b'\xff\x00')

    def test_content_bytes_rejects_non_hex(self):
        for text in (b'0A1', b'0G'):
            with self.assertRaises(ValueError):
                DB_INLINE_FLASH_DATA.content_bytes([type_code(), bytearray(text)])

    def test_load_inline_flash_data_by_id(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        support.write_project(folder, {}, [], [])
        support.write_raw_pool(folder, 'P1', [(b'Content', [bytes(type_code()), b'0A1B'])])
        loader = ObjectLoader(PblRecordManager(LIBRARY), StringStorage(folder))
        self.assertEqual(loader.load_inline_flash_data_by_id(folder, 'P1', 'Content'), b'\x0a\x1b')
        result = loader.load_object_by_id(folder, 'P1', 'Content')
        self.assertTrue(result['is_big_data'])
        self.assertEqual(result['inline_flash_data_length'], 4)


def name_block_body(body, filled=False):
    """Standard name block in stream order: short name, long name, description, three ids."""
    if filled:
        return (body.ascii('Short').unicode('Long').unicode('Desc').ascii('UID')
                .ascii('LongId').ascii('DescId'))
    return body.ascii(None).unicode(None).unicode(None).ascii(None).ascii(None).ascii(None)


def name_block(filled=False):
    if filled:
        return {'short_name': 'Short', 'long_name': 'Long', 'description': 'Desc',
                'unique_object_id': 'UID', 'long_name_id': 'LongId', 'description_id': 'DescId'}
    return {key: None for key in ('short_name', 'long_name', 'description', 'unique_object_id',
                                  'long_name_id', 'description_id')}


def load(type_name, body):
    return support.load(type_name, body)


def collection_body():
    """Two elements: one present object, one absent."""
    return ObjectBytes().u32(2).nested('MCD_AUDIENCE', support.audience_body()).absent()


class EmbeddedFlashTests(unittest.TestCase):
    def test_mcd_db_flash_checksums_minimal(self):
        self.assertEqual(load('MCD_DB_FLASH_CHECKSUMS', ObjectBytes().u32(0)), [])

    def test_mcd_db_flash_checksums_all_branches(self):
        self.assertEqual(load('MCD_DB_FLASH_CHECKSUMS', collection_body()), [support.audience(), None])

    def test_mcd_db_flash_data_blocks_minimal(self):
        self.assertEqual(load('MCD_DB_FLASH_DATA_BLOCKS', ObjectBytes().u32(0)), [])

    def test_mcd_db_flash_data_blocks_all_branches(self):
        self.assertEqual(load('MCD_DB_FLASH_DATA_BLOCKS', collection_body()), [support.audience(), None])

    def test_mcd_db_flash_filters_minimal(self):
        self.assertEqual(load('MCD_DB_FLASH_FILTERS', ObjectBytes().u32(0)), [])

    def test_mcd_db_flash_filters_all_branches(self):
        self.assertEqual(load('MCD_DB_FLASH_FILTERS', collection_body()), [support.audience(), None])

    def test_mcd_db_flash_idents_minimal(self):
        self.assertEqual(load('MCD_DB_FLASH_IDENTS', ObjectBytes().u32(0)), [])

    def test_mcd_db_flash_idents_all_branches(self):
        self.assertEqual(load('MCD_DB_FLASH_IDENTS', collection_body()), [support.audience(), None])

    def test_mcd_db_flash_securities_minimal(self):
        self.assertEqual(load('MCD_DB_FLASH_SECURITIES', ObjectBytes().u32(0)), [])

    def test_mcd_db_flash_securities_all_branches(self):
        self.assertEqual(load('MCD_DB_FLASH_SECURITIES', collection_body()), [support.audience(), None])

    def test_mcd_db_flash_segments_minimal(self):
        self.assertEqual(load('MCD_DB_FLASH_SEGMENTS', ObjectBytes().u32(0)), [])

    def test_mcd_db_flash_segments_all_branches(self):
        self.assertEqual(load('MCD_DB_FLASH_SEGMENTS', collection_body()), [support.audience(), None])

    def test_mcd_db_flash_checksum_minimal(self):
        body = name_block_body(ObjectBytes())
        body.u8(0).ascii(None).u8(255).u8(0).u32(0).u32(0).u8(0).u8(0).u32(0).u32(0)
        self.assertEqual(load('MCD_DB_FLASH_CHECKSUM', body), typed('MCD_DB_FLASH_CHECKSUM', {
            **name_block(), 'is_checksum_algorithm_available': False, 'checksum_algorithm': None,
            'checksum_result': None, 'is_compressed_size_available': False, 'compressed_size': 0,
            'uncompressed_size': 0, 'is_fill_byte_available': False, 'fill_byte': bytearray(),
            'source_start_address': 0, 'source_end_address': 0}))

    def test_mcd_db_flash_checksum_all_branches(self):
        body = name_block_body(ObjectBytes(), True)
        body.u8(1).ascii('CRC')
        support.uint_value(body, 7)
        body.u8(1).u32(16).u32(32).u8(1).u8(1).u32(1).raw(b'\xff').u32(0x1000).u32(0x1FFF)
        self.assertEqual(load('MCD_DB_FLASH_CHECKSUM', body), typed('MCD_DB_FLASH_CHECKSUM', {
            **name_block(True), 'is_checksum_algorithm_available': True,
            'checksum_algorithm': 'CRC', 'checksum_result': support.uint(7),
            'is_compressed_size_available': True, 'compressed_size': 16, 'uncompressed_size': 32,
            'is_fill_byte_available': True, 'fill_byte': bytearray(b'\xff'),
            'source_start_address': 0x1000, 'source_end_address': 0x1FFF}))

    def test_mcd_db_flash_filter_minimal(self):
        body = name_block_body(ObjectBytes()).u32(0).u32(0).u32(0)
        self.assertEqual(load('MCD_DB_FLASH_FILTER', body), typed('MCD_DB_FLASH_FILTER', {
            **name_block(), 'filter_start': 0, 'filter_end': 0, 'filter_size': 0}))

    def test_mcd_db_flash_filter_all_branches(self):
        body = name_block_body(ObjectBytes(), True).u32(1).u32(2).u32(3)
        self.assertEqual(load('MCD_DB_FLASH_FILTER', body), typed('MCD_DB_FLASH_FILTER', {
            **name_block(True), 'filter_start': 1, 'filter_end': 2, 'filter_size': 3}))

    def test_mcd_db_flash_segment_minimal(self):
        body = name_block_body(ObjectBytes()).u8(0)
        body.u32(0).u32(0).u32(0).u32(0).u32(0).u8(0)
        self.assertEqual(load('MCD_DB_FLASH_SEGMENT', body), typed('MCD_DB_FLASH_SEGMENT', {
            **name_block(), 'is_compressed_size_available': False, 'compressed_size': 0,
            'uncompressed_size': 0, 'source_start_address': 0, 'source_end_address': 0,
            'binary_start_address': 0, 'has_filtered_ranges': False,
            'filtered_ranges_for_binary_data': None}))

    def test_mcd_db_flash_segment_all_branches(self):
        # The short name is stored in the stream itself.
        body = (ObjectBytes().embedded_ascii('SEG').unicode('Long').unicode('Desc').ascii('UID')
                .ascii('LongId').ascii('DescId'))
        body.u8(1).u32(10).u32(20).u32(30).u32(40).u32(50).u8(1)
        body.u16(2).u32(1).u32(2).u32(3).u32(4)
        self.assertEqual(load('MCD_DB_FLASH_SEGMENT', body), typed('MCD_DB_FLASH_SEGMENT', {
            **name_block(True), 'short_name': 'SEG', 'is_compressed_size_available': True,
            'compressed_size': 10, 'uncompressed_size': 20, 'source_start_address': 30,
            'source_end_address': 40, 'binary_start_address': 50, 'has_filtered_ranges': True,
            'filtered_ranges_for_binary_data': [[1, 2], [3, 4]]}))

    def test_mcd_db_flash_security_minimal(self):
        body = name_block_body(ObjectBytes()).u8(255).u8(255).u8(255).u8(255)
        self.assertEqual(load('MCD_DB_FLASH_SECURITY', body), typed('MCD_DB_FLASH_SECURITY', {
            **name_block(), 'security_method': None, 'flashware_signature': None,
            'flashware_checksum': None, 'validity': None}))

    def test_mcd_db_flash_security_all_branches(self):
        body = name_block_body(ObjectBytes(), True)
        body.u8(3).u8(1).u16(1).raw(b'\x01')
        body.u8(1).ascii('SUM')
        support.uint_value(body, 9)
        body.u8(255)
        self.assertEqual(load('MCD_DB_FLASH_SECURITY', body), typed('MCD_DB_FLASH_SECURITY', {
            **name_block(True),
            'security_method': {'data_type': 'eA_BYTEFIELD', 'value': bytearray(b'\x01')},
            'flashware_signature': {'data_type': 'eA_ASCIISTRING', 'value': 'SUM'},
            'flashware_checksum': support.uint(9), 'validity': None}))

    def test_mcd_db_ident_description_minimal(self):
        body = ObjectBytes().ascii(None).u8(0).ascii(None)
        self.assertEqual(load('MCD_DB_IDENT_DESCRIPTION', body), typed('MCD_DB_IDENT_DESCRIPTION', {
            'data_primitive_name': None, 'is_response_parameter_name': False,
            'response_parameter_name': None, 'response_parameter_short_name_path': None}))

    def test_mcd_db_ident_description_all_branches(self):
        body = ObjectBytes().ascii('DP').u8(1).ascii('RP')
        self.assertEqual(load('MCD_DB_IDENT_DESCRIPTION', body), typed('MCD_DB_IDENT_DESCRIPTION', {
            'data_primitive_name': 'DP', 'is_response_parameter_name': True,
            'response_parameter_name': 'RP', 'response_parameter_short_name_path': None}))
        body = ObjectBytes().ascii('DP').u8(0).ascii('A.B')
        self.assertEqual(load('MCD_DB_IDENT_DESCRIPTION', body), typed('MCD_DB_IDENT_DESCRIPTION', {
            'data_primitive_name': 'DP', 'is_response_parameter_name': False,
            'response_parameter_name': None, 'response_parameter_short_name_path': 'A.B'}))

    def test_mcd_db_flash_ident_minimal(self):
        body = name_block_body(ObjectBytes()).absent().absent()
        self.assertEqual(load('MCD_DB_FLASH_IDENT', body), typed('MCD_DB_FLASH_IDENT', {
            **name_block(), 'ident_values': None, 'read_ident_description': None}))

    def test_mcd_db_flash_ident_all_branches(self):
        body = name_block_body(ObjectBytes(), True)
        body.nested('MCD_VALUES', ObjectBytes().u16(1).u8(1).ascii('V1'))
        body.nested('MCD_DB_IDENT_DESCRIPTION', ObjectBytes().ascii('DP').u8(0).ascii('A.B'))
        self.assertEqual(load('MCD_DB_FLASH_IDENT', body), typed('MCD_DB_FLASH_IDENT', {
            **name_block(True),
            'ident_values': [{'data_type': 'eA_ASCIISTRING', 'value': 'V1'}],
            'read_ident_description': typed('MCD_DB_IDENT_DESCRIPTION', {
                'data_primitive_name': 'DP', 'is_response_parameter_name': False,
                'response_parameter_name': None, 'response_parameter_short_name_path': 'A.B'})}))


class FlashDataTests(unittest.TestCase):
    def test_mcd_db_flash_data_minimal(self):
        body = name_block_body(ObjectBytes()).ascii(None).u8(0).u16(0x6B01).u8(255).ascii(None)
        self.assertEqual(load('MCD_DB_FLASH_DATA', body), typed('MCD_DB_FLASH_DATA', {
            **name_block(), 'data_file_name_or_inline_flash_data': None,
            'data_reference': {'kind': 'external_file', 'file_name': None},
            'late_bound_or_is_inline': False, 'data_format': 0x6B01,
            'encryption_compression_method': None, 'flash_file_sub_dir_name': None}))

    def test_mcd_db_flash_data_all_branches(self):
        body = name_block_body(ObjectBytes(), True).ascii('DSA_INLINE_POOLDDDSSSBBBKEY').u8(1).u16(0x6B02)
        body.u8(3).u8(1).u16(1).raw(b'\x01')
        body.ascii('SUB')
        self.assertEqual(load('MCD_DB_FLASH_DATA', body), typed('MCD_DB_FLASH_DATA', {
            **name_block(True), 'data_file_name_or_inline_flash_data': 'DSA_INLINE_POOLDDDSSSBBBKEY',
            'data_reference': {'kind': 'big_data_object', 'pool_id': 'POOL', 'object_id': 'KEY'},
            'late_bound_or_is_inline': True, 'data_format': 0x6B02,
            'encryption_compression_method': {'data_type': 'eA_BYTEFIELD', 'value': bytearray(b'\x01')},
            'flash_file_sub_dir_name': 'SUB'}))

    def test_decode_data_reference(self):
        decode = MCD_DB_FLASH_DATA.decode_data_reference
        self.assertEqual(decode('file.bin'), {'kind': 'external_file', 'file_name': 'file.bin'})
        self.assertEqual(decode('DSA_INLINE_'), {'kind': 'external_file', 'file_name': 'DSA_INLINE_'})
        self.assertEqual(decode('DSA_INLINE_PDDDSSSAAAO'),
                         {'kind': 'object', 'pool_id': 'P', 'object_id': 'O'})
        self.assertEqual(decode('DSA_INLINE_0A1B'), {'kind': 'inline_content', 'content_length': 4})
        self.assertEqual(decode('DSA_INLINE_' + 'X' * 1000 + 'DDDSSSBBBK'),
                         {'kind': 'inline_content', 'content_length': 1010})

    def test_mcd_db_flash_data_block_minimal(self):
        body = name_block_body(ObjectBytes()).u64(0).ascii(None)
        for _ in range(5):
            body.absent()
        body.u8(0).u8(0).absent().u8(0).u8(0)
        self.assertEqual(load('MCD_DB_FLASH_DATA_BLOCK', body), typed('MCD_DB_FLASH_DATA_BLOCK', {
            **name_block(), 'address_offset': 0, 'data_block_type': None, 'flash_data': None,
            'flash_filters': None, 'flash_segments': None, 'own_idents': None, 'securities': None,
            'special_data_group_refs': None, 'has_logical_block_index': False,
            'logical_block_index': None, 'audience_state': None,
            'disabled_additional_audiences': None, 'enabled_additional_audiences': None}))

    def test_mcd_db_flash_data_block_all_branches(self):
        data = name_block_body(ObjectBytes()).ascii(None).u8(0).u16(0x6B01).u8(255).ascii(None)
        body = name_block_body(ObjectBytes(), True).u64(2**33).ascii('APPLICATION')
        body.nested('MCD_DB_FLASH_DATA', data)
        for name in ('MCD_DB_FLASH_FILTERS', 'MCD_DB_FLASH_SEGMENTS', 'MCD_DB_FLASH_IDENTS',
                     'MCD_DB_FLASH_SECURITIES'):
            body.nested(name, ObjectBytes().u32(0))
        body.u8(1).u16(1).u32(7)
        body.u8(1).u32(3)
        body.nested('MCD_AUDIENCE', support.audience_body())
        support.named_refs_body(body.u8(1), support.NAMED_REFS)
        support.named_refs_body(body.u8(1), support.NAMED_REFS)
        flash_data = typed('MCD_DB_FLASH_DATA', {
            **name_block(), 'data_file_name_or_inline_flash_data': None,
            'data_reference': {'kind': 'external_file', 'file_name': None},
            'late_bound_or_is_inline': False, 'data_format': 0x6B01,
            'encryption_compression_method': None, 'flash_file_sub_dir_name': None})
        self.assertEqual(load('MCD_DB_FLASH_DATA_BLOCK', body), typed('MCD_DB_FLASH_DATA_BLOCK', {
            **name_block(True), 'address_offset': 2**33, 'data_block_type': 'APPLICATION',
            'flash_data': flash_data, 'flash_filters': [], 'flash_segments': [], 'own_idents': [],
            'securities': [], 'special_data_group_refs': [{'object_id': 7}],
            'has_logical_block_index': True, 'logical_block_index': 3,
            'audience_state': support.audience(),
            'disabled_additional_audiences': support.named_refs(support.NAMED_REFS),
            'enabled_additional_audiences': support.named_refs(support.NAMED_REFS)}))


SESSION_KEYS = ('short_name', 'odx_session_short_name', 'long_name', 'description', 'unique_object_id',
                'long_name_id', 'description_id', 'flash_pool_id', 'checksums', 'data_blocks',
                'expected_idents', 'flash_job_name', 'has_flash_session_classes',
                'flash_session_classes', 'securities', 'flash_key', 'priority', 'is_download',
                'special_data_group_refs')


class FlashTopLevelTests(unittest.TestCase):
    def test_mcd_db_flash_session_minimal(self):
        body = ObjectBytes().ascii(None).ascii(None).unicode(None).unicode(None)
        body.ascii(None).ascii(None).ascii(None).ascii(None)
        body.absent().absent().absent().ascii(None).u8(0).absent().ascii(None).u32(0).u8(0).u8(0)
        expected = {key: None for key in SESSION_KEYS}
        expected.update({'has_flash_session_classes': False, 'flash_session_classes': [],
                         'priority': 0, 'is_download': False})
        self.assertEqual(load('MCD_DB_FLASH_SESSION', body), typed('MCD_DB_FLASH_SESSION', expected))

    def test_mcd_db_flash_session_all_branches(self):
        body = ObjectBytes().ascii('S_A').ascii('S_B').embedded_unicode('Lang').unicode('Desc')
        body.ascii('UID').ascii('LongId').ascii('DescId').ascii('POOL')
        body.nested('MCD_DB_FLASH_CHECKSUMS', ObjectBytes().u32(0))
        body.nested('MCD_DB_FLASH_DATA_BLOCKS', ObjectBytes().u32(0))
        body.nested('MCD_DB_FLASH_IDENTS', ObjectBytes().u32(0))
        body.ascii('JOB')
        support.named_refs_body(body.u8(1), support.NAMED_REFS)
        body.nested('MCD_DB_FLASH_SECURITIES', ObjectBytes().u32(0))
        body.ascii('K').u32(5).u8(1).u8(1).u16(1).u32(7)
        self.assertEqual(load('MCD_DB_FLASH_SESSION', body), typed('MCD_DB_FLASH_SESSION', {
            'short_name': 'S_A', 'odx_session_short_name': 'S_B', 'long_name': 'Lang',
            'description': 'Desc', 'unique_object_id': 'UID', 'long_name_id': 'LongId',
            'description_id': 'DescId', 'flash_pool_id': 'POOL', 'checksums': [], 'data_blocks': [],
            'expected_idents': [], 'flash_job_name': 'JOB', 'has_flash_session_classes': True,
            'flash_session_classes': support.named_refs(support.NAMED_REFS), 'securities': [],
            'flash_key': 'K', 'priority': 5, 'is_download': True,
            'special_data_group_refs': [{'object_id': 7}]}))

    def test_mcd_db_ecu_mem_minimal(self):
        body = name_block_body(ObjectBytes()).u8(0).u16(0).u16(0).u16(0).u8(0).u8(0).u8(0).u8(0)
        self.assertEqual(load('MCD_DB_ECU_MEM', body), typed('MCD_DB_ECU_MEM', {
            **name_block(), 'has_layers': False, 'base_variants': [], 'variants': [],
            'layers': None, 'all_variant_layers': None, 'flash_sessions': [],
            'additional_audiences': None, 'has_flash_session_classes': False,
            'flash_session_class_refs': None, 'has_physical_memory': False,
            'physical_memory_ref': None, 'special_data_group_refs': None}))

    def test_mcd_db_ecu_mem_all_branches(self):
        body = name_block_body(ObjectBytes(), True).u8(1)
        body.nested('DB_ODX_LINKS', ObjectBytes().u32(0)).absent()
        support.named_attributed_refs_body(body, support.NAMED_ATTRIBUTED_REFS)
        support.named_refs_body(body.u8(1), support.NAMED_REFS)
        support.named_refs_body(body.u8(1), support.NAMED_REFS)
        support.attributed_ref_body(body.u8(1), ('X',))
        body.u8(1).u16(1).u32(7)
        self.assertEqual(load('MCD_DB_ECU_MEM', body), typed('MCD_DB_ECU_MEM', {
            **name_block(True), 'has_layers': True, 'base_variants': None, 'variants': None,
            'layers': [], 'all_variant_layers': None,
            'flash_sessions': support.named_attributed_refs(support.NAMED_ATTRIBUTED_REFS),
            'additional_audiences': support.named_refs(support.NAMED_REFS),
            'has_flash_session_classes': True,
            'flash_session_class_refs': support.named_refs(support.NAMED_REFS),
            'has_physical_memory': True, 'physical_memory_ref': support.attributed_ref(('X',)),
            'special_data_group_refs': [{'object_id': 7}]}))

    def test_db_flash_data_minimal(self):
        self.assertEqual(load('DB_FLASH_DATA', ObjectBytes().u16(0)),
                         {'#OBJECT_TYPE': 'DB_FLASH_DATA', 'ecu_mem_refs': []})

    def test_db_flash_data_all_branches(self):
        body = ObjectBytes().u16(2)
        body.ascii('MEM').ascii('OBJ').ascii('POOL')
        body.embedded_ascii('EMB').ascii('OBJ').ascii('POOL')
        self.assertEqual(load('DB_FLASH_DATA', body), {
            '#OBJECT_TYPE': 'DB_FLASH_DATA',
            'ecu_mem_refs': [{'map_key': 'MEM', 'reference': support.ref()},
                             {'map_key': 'EMB', 'reference': support.ref()}]})


if __name__ == '__main__':
    unittest.main()
