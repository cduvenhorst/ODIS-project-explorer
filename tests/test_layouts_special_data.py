"""Layout tests for the special data group and element loaders.

Upstream has no loaders for these types; every body follows the kernel read order.
"""
import unittest

from tests import support
from tests.support import ObjectBytes, sdg_element_body, sdg_group_body


class SpecialDataLayoutTests(unittest.TestCase):
    def test_special_data_element_reads_three_native_strings(self):
        result = support.load('MCD_DB_SPECIAL_DATA_ELEMENT',
                              sdg_element_body('TID', 'Content', 'SI'), strict=True)
        self.assertEqual(result, {'#OBJECT_TYPE': 'MCD_DB_SPECIAL_DATA_ELEMENT',
                                  'text_id': 'TID', 'content': 'Content',
                                  'semantic_information': 'SI'})

    def test_special_data_element_empty_strings(self):
        result = support.load('MCD_DB_SPECIAL_DATA_ELEMENT', sdg_element_body(), strict=True)
        self.assertEqual((result['text_id'], result['content'], result['semantic_information']),
                         ('', '', ''))

    def test_special_data_element_content_with_cp1252_undefined_byte(self):
        raw = b'a\x81b'
        body = ObjectBytes().u32(0).u32(0x80000000 | len(raw)).raw(raw).u32(0)
        result = support.load('MCD_DB_SPECIAL_DATA_ELEMENT', body, strict=True)
        self.assertEqual(result['content'], 'a\x81b')

    def test_special_data_group_with_caption_and_nested_group(self):
        nested = ('MCD_DB_SPECIAL_DATA_GROUP',
                  sdg_group_body(items=(('MCD_DB_SPECIAL_DATA_ELEMENT',
                                         sdg_element_body('T2', 'C2')),)))
        body = sdg_group_body(
            items=(('MCD_DB_SPECIAL_DATA_ELEMENT', sdg_element_body('T1', 'C1', 'S1')),
                   None, nested),
            caption=(4711, 'A.sd'), semantic_information='GSI')
        result = support.load('MCD_DB_SPECIAL_DATA_GROUP', body, strict=True)
        self.assertEqual(result['caption_reference'], {'object_key': 4711, 'pool_id': 'A.sd'})
        self.assertEqual(result['semantic_information'], 'GSI')
        self.assertEqual(result['items'][0]['text_id'], 'T1')
        self.assertIsNone(result['items'][1])
        self.assertEqual(result['items'][2]['#OBJECT_TYPE'], 'MCD_DB_SPECIAL_DATA_GROUP')
        self.assertEqual(result['items'][2]['items'][0]['content'], 'C2')
        self.assertIsNone(result['items'][2]['caption_reference'])

    def test_special_data_group_pool_word_without_string_gives_none(self):
        body = ObjectBytes().u32(0).u8(1).u32(7).u32(0).u32(0)
        result = support.load('MCD_DB_SPECIAL_DATA_GROUP', body, strict=True)
        self.assertEqual(result['caption_reference'], {'object_key': 7, 'pool_id': None})

    def test_special_data_group_unknown_caption_flag_raises(self):
        body = ObjectBytes().u32(0).u8(2).u32(0)
        with self.assertRaisesRegex(RuntimeError, 'Unknown caption flag: 2'):
            support.load('MCD_DB_SPECIAL_DATA_GROUP', body, strict=True)

    def test_mcd_db_special_data_element_minimal(self):
        result = support.load('MCD_DB_SPECIAL_DATA_ELEMENT', sdg_element_body(), strict=True)
        self.assertEqual(result, {'#OBJECT_TYPE': 'MCD_DB_SPECIAL_DATA_ELEMENT', 'text_id': '',
                                  'content': '', 'semantic_information': ''})

    def test_mcd_db_special_data_element_all_branches(self):
        self.test_special_data_element_reads_three_native_strings()

    def test_mcd_db_special_data_group_minimal(self):
        result = support.load('MCD_DB_SPECIAL_DATA_GROUP', sdg_group_body(), strict=True)
        self.assertEqual(result, {'#OBJECT_TYPE': 'MCD_DB_SPECIAL_DATA_GROUP', 'items': [],
                                  'caption_reference': None, 'semantic_information': ''})

    def test_mcd_db_special_data_group_all_branches(self):
        self.test_special_data_group_with_caption_and_nested_group()
        self.test_special_data_group_pool_word_without_string_gives_none()
        self.test_special_data_group_unknown_caption_flag_raises()


if __name__ == '__main__':
    unittest.main()
