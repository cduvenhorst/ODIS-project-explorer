import io
import unittest
import xml.etree.ElementTree as ET

from flash_export.odx_flash import is_flash_document, read_flash_document, read_intern_data


def doc(blocks='', flash_datas='', sessions='', session_descs='', layer_refs=''):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ODX xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><FLASH>'
        '<ECU-MEMS><ECU-MEM><MEM>'
        f'<SESSIONS>{sessions}</SESSIONS><DATABLOCKS>{blocks}</DATABLOCKS><FLASHDATAS>{flash_datas}</FLASHDATAS>'
        '</MEM></ECU-MEM></ECU-MEMS>'
        '<ECU-MEM-CONNECTORS><ECU-MEM-CONNECTOR>'
        f'<SESSION-DESCS>{session_descs}</SESSION-DESCS><LAYER-REFS>{layer_refs}</LAYER-REFS>'
        '</ECU-MEM-CONNECTOR></ECU-MEM-CONNECTORS></FLASH></ODX>'
    ).encode()


def block(id_, name, type_=None, segments='', ref=None):
    type_attr = f' TYPE="{type_}"' if type_ else ''
    ref_xml = f'<FLASHDATA-REF ID-REF="{ref}"/>' if ref else ''
    return (f'<DATABLOCK ID="{id_}"{type_attr}><SHORT-NAME>{name}</SHORT-NAME>{ref_xml}'
            f'<SEGMENTS>{segments}</SEGMENTS></DATABLOCK>')


def segment(start, size):
    return (f'<SEGMENT><SOURCE-START-ADDRESS>{start}</SOURCE-START-ADDRESS>'
            f'<UNCOMPRESSED-SIZE>{size}</UNCOMPRESSED-SIZE></SEGMENT>')


def session(name, *refs):
    inner = ''.join(f'<DATABLOCK-REF ID-REF="{r}"/>' for r in refs)
    return f'<SESSION><SHORT-NAME>{name}</SHORT-NAME><DATABLOCK-REFS>{inner}</DATABLOCK-REFS></SESSION>'


def flash_data(id_, name, kind, body, method=None):
    m = f'<ENCRYPT-COMPRESS-METHOD>{method}</ENCRYPT-COMPRESS-METHOD>' if method else ''
    return (f'<FLASHDATA ID="{id_}" xsi:type="{kind}"><SHORT-NAME>{name}</SHORT-NAME>'
            f'<DATAFORMAT SELECTION="BINARY"/>{m}{body}</FLASHDATA>')


def read(data):
    return read_flash_document(io.BytesIO(data))


class OdxFlashTest(unittest.TestCase):
    def test_block_metadata(self):
        data = doc(
            blocks=block('B1', 'one', 'CODE', segment('0001A000', 10) + segment('00010000', 6), 'F1')
            + block('B2', 'two'),
            flash_datas=flash_data('F1', 'FD1', 'INTERN-FLASHDATA', '<DATA>00</DATA>', 'A0'))
        blocks = read(data).blocks
        self.assertEqual(2, len(blocks))
        first = blocks[0]
        self.assertEqual((1, 'one', 'CODE'), (first.index, first.name, first.block_type))
        self.assertEqual(0x10000, first.start_address)
        self.assertEqual(16, first.uncompressed_size)
        self.assertEqual(0xA0, first.method)
        self.assertEqual((2, 'two', ''), (blocks[1].index, blocks[1].name, blocks[1].block_type))

    def test_sessions_and_part_numbers(self):
        data = doc(
            blocks=block('B1', 'one') + block('B2', 'two'),
            sessions=session('S1', 'B1', 'B2') + session('S2', 'B2'),
            session_descs='<SESSION-DESC><SHORT-NAME>D2</SHORT-NAME><PARTNUMBER>P2</PARTNUMBER>'
                          '<SESSION-SNREF SHORT-NAME="S2"/></SESSION-DESC>')
        blocks = read(data).blocks
        self.assertEqual(('S1',), blocks[0].sessions)
        self.assertEqual((), blocks[0].part_numbers)
        self.assertEqual(('S1', 'S2'), blocks[1].sessions)
        self.assertEqual(('P2',), blocks[1].part_numbers)

    def test_extern_and_intern_flash_data(self):
        data = doc(
            blocks=block('B1', 'one', ref='F1') + block('B2', 'two', ref='F2'),
            flash_datas=flash_data('F1', 'FD1', 'EXTERN-FLASHDATA',
                                   '<DATAFILE LATEBOUND-DATAFILE="false">a b+.bin</DATAFILE>')
            + flash_data('F2', 'FD2', 'INTERN-FLASHDATA', '<DATA>0102FF</DATA>'))
        blocks = read(data).blocks
        self.assertEqual(('FD1', 'a b+.bin', False), (blocks[0].flash_data, blocks[0].data_file, blocks[0].has_data))
        self.assertEqual(('FD2', None, True), (blocks[1].flash_data, blocks[1].data_file, blocks[1].has_data))
        self.assertEqual({'FD2': b'\x01\x02\xff'}, read_intern_data(io.BytesIO(data)))

    def test_forward_reference_and_whitespace_in_data(self):
        data = doc(
            blocks=block('B1', 'one', ref='F1'),
            flash_datas=flash_data('F1', 'FD1', 'INTERN-FLASHDATA', '<DATA>01 02\n03</DATA>'))
        self.assertEqual({'FD1': b'\x01\x02\x03'}, read_intern_data(io.BytesIO(data)))
        self.assertEqual('FD1', read(data).blocks[0].flash_data)

    def test_ecus_from_layer_refs(self):
        data = doc(layer_refs='<LAYER-REF DOCREF="BV_X" DOCTYPE="LAYER"/><LAYER-REF DOCREF="EV_Y"/>')
        self.assertEqual(('BV_X', 'EV_Y'), read(data).ecus)

    def test_unresolved_flash_data_reference(self):
        data = doc(blocks=block('B1', 'one', ref='MISSING'))
        self.assertIsNone(read(data).blocks[0].flash_data)

    def test_method_with_more_than_two_digits_is_none(self):
        data = doc(
            blocks=block('B1', 'one', ref='F1'),
            flash_datas=flash_data('F1', 'FD1', 'INTERN-FLASHDATA', '<DATA>00</DATA>', '0102'))
        self.assertIsNone(read(data).blocks[0].method)

    def test_unreadable_numbers_are_none(self):
        data = doc(blocks=block('B1', 'one', segments=segment('xyz', 'abc')))
        result = read(data).blocks[0]
        self.assertIsNone(result.start_address)
        self.assertIsNone(result.uncompressed_size)

    def test_bad_hex_data_is_stored_per_entry(self):
        data = doc(flash_datas=(
            flash_data('F1', 'FD1', 'INTERN-FLASHDATA', '<DATA>0G</DATA>')
            + flash_data('F2', 'FD2', 'INTERN-FLASHDATA', '<DATA>0102</DATA>')
            + flash_data('F3', 'FD3', 'INTERN-FLASHDATA', '<DATA>012</DATA>')))
        result = read_intern_data(io.BytesIO(data))
        self.assertEqual(['FD1', 'FD2', 'FD3'], sorted(result))
        self.assertIsInstance(result['FD1'], ValueError)
        self.assertEqual(b'\x01\x02', result['FD2'])
        self.assertIsInstance(result['FD3'], ValueError)

    def test_is_flash_document(self):
        self.assertTrue(is_flash_document(io.BytesIO(doc())))
        self.assertFalse(is_flash_document(io.BytesIO(b'<ODX><DIAG-LAYER-CONTAINER/><FLASH/></ODX>')))
        self.assertFalse(is_flash_document(io.BytesIO(b'<OTHER><FLASH/></OTHER>')))
        self.assertFalse(is_flash_document(io.BytesIO(b'<ODX/>')))

    def test_is_flash_document_raises_on_malformed_start(self):
        with self.assertRaises(ET.ParseError):
            is_flash_document(io.BytesIO(b'<ODX><FLASH'))
        with self.assertRaises(ET.ParseError):
            is_flash_document(io.BytesIO(b'not xml at all'))

    def test_whitespace_kinds_in_data_are_removed(self):
        data = doc(flash_datas=flash_data('F1', 'FD1', 'INTERN-FLASHDATA', '<DATA>01\t02\r\n 03</DATA>'))
        self.assertEqual({'FD1': b'\x01\x02\x03'}, read_intern_data(io.BytesIO(data)))


if __name__ == '__main__':
    unittest.main()
