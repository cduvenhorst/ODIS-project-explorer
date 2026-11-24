"""Tests for the enum converters in common_utils/enum_converters.py."""

import unittest

from common_utils import enum_converters


class EnumConverterTests(unittest.TestCase):
    def test_flash_data_format_names(self):
        for code, name in [(0x6B01, 'eBINARY'), (0x6B02, 'eINTEL_HEX'), (0x6B03, 'eMOTOROLA_S')]:
            with self.subTest(code=code):
                self.assertEqual(enum_converters.get_MCDFlashDataFormat(code), name)

    def test_flash_data_format_unknown_raises(self):
        with self.assertRaisesRegex(RuntimeError, r'Invalid enum value \(6B04\)'):
            enum_converters.get_MCDFlashDataFormat(0x6B04)

    def test_physical_to_db_data_type_unknown_maps_to_zero(self):
        # kernel: an unknown physical base data type maps to 0
        self.assertEqual(enum_converters.map_enum_EDbPhysicalDataType_to_EDbDataType(6), 0)

    def test_object_type_0x030b_is_named_like_0x030a(self):
        self.assertEqual(enum_converters.get_object_type_enum(0x030B),
                         enum_converters.get_object_type_enum(0x030A))

    def test_db_file_type_of_name_without_extension_is_unknown(self):
        self.assertEqual('Unknown (duvi)', enum_converters.get_db_file_type('duvi'))
        self.assertEqual('Base Variant', enum_converters.get_db_file_type('0.0.0@B.bv'))


if __name__ == '__main__':
    unittest.main()
