import unittest
import xml.etree.ElementTree as ET

from flash_export.sw_cnt import SwCntBlock, decode_mime_base64, read_sw_cnt, read_sw_cnt_areas

DOC = ('<!DOCTYPE SW-CNT PUBLIC "-//Example//DTD Container//EN" "x.dtd">'
       '<SW-CNT><IDENT><CNT-IDENT-TEXT>M\xfcster</CNT-IDENT-TEXT></IDENT>'
       '<DATEN><DATENBLOECKE>{}</DATENBLOECKE></DATEN></SW-CNT>')


def block(name, data_text, fmt='0x00', start='0x00010000', size='0x3'):
    return ('<DATENBLOCK><DATENBLOCK-NAME>{}</DATENBLOCK-NAME><DATENBLOCK-FORMAT>{}</DATENBLOCK-FORMAT>'
            '<START-ADR>{}</START-ADR><GROESSE-DEKOMPRIMIERT>{}</GROESSE-DEKOMPRIMIERT>'
            '<DATENBLOCK-DATEN>{}</DATENBLOCK-DATEN></DATENBLOCK>').format(name, fmt, start, size, data_text)


def container(blocks_xml):
    return DOC.format(blocks_xml).encode('iso-8859-1')


MIME = ('\nMime-Version: 1.0\nContent-Type: application/octet-stream; name="a.bin"\n'
        'Content-Transfer-Encoding: base64\n\nAQID\n')


class SwCntTests(unittest.TestCase):
    def test_latin1_document_with_mime_block(self):
        blocks = read_sw_cnt(container(block('B1', MIME)))
        self.assertEqual(blocks, [SwCntBlock(1, 'B1', 0, 0x10000, 3, b'\x01\x02\x03')])

    def test_header_continuation_line_is_skipped(self):
        text = '\nContent-Type: application/octet-stream;\n\tname="a.bin"\n\nAQID\n'
        self.assertEqual(read_sw_cnt(container(block('B', text)))[0].data, b'\x01\x02\x03')

    def test_header_name_with_spaces_is_skipped(self):
        text = ('\nMIME-Version: 1.0\nContent-Type: application/octet-stream\n'
                'Content -Transfer - Encoding: base64\n\nAQID\n')
        self.assertEqual(read_sw_cnt(container(block('B', text)))[0].data, b'\x01\x02\x03')

    def test_missing_padding_is_added(self):
        self.assertEqual(read_sw_cnt(container(block('B', 'AQ')))[0].data, b'\x01')

    def test_base64_split_over_lines(self):
        self.assertEqual(read_sw_cnt(container(block('B', 'AQ\nID')))[0].data, b'\x01\x02\x03')

    def test_undecodable_block_has_no_data(self):
        blocks = read_sw_cnt(container(block('B', 'A*B')))
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(blocks[0].data)

    def test_two_blocks_keep_order_and_format(self):
        xml = block('B1', 'AQID') + block('B2', 'AQID', fmt='0x11')
        blocks = read_sw_cnt(container(xml))
        self.assertEqual([b.index for b in blocks], [1, 2])
        self.assertEqual([b.data_format for b in blocks], [0, 0x11])

    def test_other_xml_root_is_not_a_container(self):
        self.assertIsNone(read_sw_cnt(b'<ODX/>'))

    def test_malformed_xml_raises(self):
        with self.assertRaises(ET.ParseError):
            read_sw_cnt(b'<SW-CNT><DATEN>')

    def test_missing_number_fields_are_none(self):
        xml = block('B', 'AQID').replace('<START-ADR>0x00010000</START-ADR>', '')
        self.assertIsNone(read_sw_cnt(container(xml))[0].start_address)

    def test_decode_empty_text_gives_empty_bytes(self):
        self.assertEqual(decode_mime_base64(''), b'')

    def test_areas_of_container_with_xml_declaration(self):
        raw = (b'<?xml version="1.0" encoding="UTF-8"?><SW-CNT><DATENBEREICHE><DATENBEREICH>'
               b'<DATEN-NAME>D\xc3\xbc</DATEN-NAME><DATEN-FORMAT-NAME>DFN_BYTE</DATEN-FORMAT-NAME>'
               b'<START-ADR>1A</START-ADR><GROESSE-DEKOMPRIMIERT>3</GROESSE-DEKOMPRIMIERT>'
               b'<DATEN>AQID</DATEN></DATENBEREICH></DATENBEREICHE></SW-CNT>')
        self.assertEqual(read_sw_cnt_areas(raw),
                         [SwCntBlock(1, 'D\xfc', None, 0x1A, 3, b'\x01\x02\x03')])

    def test_areas_of_other_root_is_none(self):
        self.assertIsNone(read_sw_cnt_areas(b'<OTHER/>'))

    def test_document_without_areas_gives_empty_list(self):
        self.assertEqual(read_sw_cnt_areas(b'<SW-CNT><IDENT/></SW-CNT>'), [])

    def test_blocks_of_container_with_xml_declaration(self):
        raw = (b'<?xml version="1.0" encoding="UTF-8"?><SW-CNT><DATEN><DATENBLOECKE><DATENBLOCK>'
               b'<DATENBLOCK-NAME>B\xc3\xbc</DATENBLOCK-NAME><DATENBLOCK-DATEN>AQID</DATENBLOCK-DATEN>'
               b'</DATENBLOCK></DATENBLOECKE></DATEN></SW-CNT>')
        self.assertEqual(read_sw_cnt(raw)[0].name, 'B\xfc')


if __name__ == '__main__':
    unittest.main()
