import unittest

from flash_export.data_kind import describe_data_kind, entropy


class DataKindTests(unittest.TestCase):
    def test_entropy_of_uniform_bytes_is_eight(self):
        self.assertAlmostEqual(entropy(bytes(range(256)) * 4), 8.0)

    def test_entropy_of_constant_bytes_is_zero(self):
        self.assertEqual(entropy(b'\x00' * 100), 0.0)

    def test_empty(self):
        self.assertEqual(describe_data_kind(b''), 'empty')

    def test_low_entropy_without_method(self):
        self.assertEqual(describe_data_kind(b'\x00' * 100),
                         'not compressed or encrypted as a whole (entropy 0.00)')

    def test_high_entropy(self):
        self.assertEqual(describe_data_kind(bytes(range(256)) * 4), 'compressed or encrypted (entropy 8.00)')

    def test_gzip_header_and_method_and_entropy_are_all_named(self):
        self.assertEqual(describe_data_kind(b'\x1f\x8b' + b'\x00' * 98, 0x11, 'DATENBLOCK-FORMAT'),
                         'gzip (header); compressed and encrypted (DATENBLOCK-FORMAT 0x11, ISO 14229 reading); '
                         'not compressed or encrypted as a whole (entropy 0.16)')

    def test_method_zero(self):
        self.assertIn('not compressed, not encrypted (encryption_compression_method 0x00, ISO 14229 reading)',
                      describe_data_kind(b'ab', 0, 'encryption_compression_method'))

    def test_method_upper_and_lower_half(self):
        self.assertIn('compressed (m 0x10,', describe_data_kind(b'ab', 0x10, 'm'))
        self.assertIn('encrypted (m 0x01,', describe_data_kind(b'ab', 0x01, 'm'))

    def test_xz_header(self):
        self.assertTrue(describe_data_kind(b'\xfd7zXZ\x00rest').startswith('xz (header); '))
