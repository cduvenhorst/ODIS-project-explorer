"""Tests for the ODX DTC-DOP writer."""
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from odx_export import trouble_codes
from tests.odx_support import context, xml

OWN = '0.0.0@L.sd'


def reference(object_id, pool_id=OWN):
    return {'object_id': object_id, 'pool_id': pool_id}


def coded_type():
    return {'coded_type': 'eSTANDARD_LENGTH_TYPE', 'bit_length': 24, 'bit_mask': bytearray(),
            'base_data_type': 'eDB_UINT32', 'encoding': 'eNONE', 'is_high_low_byte_order': True,
            'is_condensed_bit_mask': False, 'length_key_parameter': None}


def dtc_dop(short_name, *references, **fields):
    result = {'diag_trouble_code_references': [{'map_key': index, 'reference': entry}
                                               for index, entry in enumerate(references)],
              'linked_dtc_dops': [],
              'compu_method': {'compu_category': 'eIDENTICAL', 'compu_phys_to_internal': None,
                               'compu_internal_to_phys': None, 'compu_inverse_value_id': None,
                               'compu_default_value_id': None},
              'diag_coded_type': coded_type(),
              'physical_type': {'base_data_type': 'eDB_PHYS_UINT32', 'is_precision_available': False,
                                'precision': None, 'display_radix': 16},
              'short_name': short_name, 'long_name': None, 'description': None,
              'unique_object_id': 'OID-' + short_name, 'long_name_id': None, 'description_id': None}
    result.update(fields)
    return result


def dtc(short_name, **fields):
    result = {'unique_object_id': 'OID-' + short_name, 'short_name': short_name,
              'display_trouble_code': 'P0001', 'dtc_text': 'Fault', 'level': 2, 'trouble_code': 4097,
              'special_data_group_references': [], 'diag_trouble_code_text_id': 'TI_D'}
    result.update(fields)
    return result


def tags(element):
    return [child.tag for child in element]


class DtcDopTests(unittest.TestCase):
    def test_dtc_dop_writes_types_and_embedded_dtc(self):
        ctx = context({'DOP_L_X1': ('DB_DOP_DTC', dtc_dop('DOP1', reference('DTC_L_A'))),
                       'DTC_L_A': ('MCD_DB_DIAG_TROUBLE_CODE', dtc('A'))})
        element = trouble_codes.add_dtc_dop(ctx, ET.Element('X'), 'DOP_L_X1', set())
        self.assertEqual(element.tag, 'DTC-DOP')
        self.assertEqual(element.attrib, {'ID': 'X1', 'OID': 'OID-DOP1'})
        self.assertEqual(tags(element), ['SHORT-NAME', 'DIAG-CODED-TYPE', 'PHYSICAL-TYPE', 'COMPU-METHOD', 'DTCS'])
        embedded = element.find('DTCS/DTC')
        self.assertEqual(embedded.attrib, {'ID': 'A', 'OID': 'OID-A'})
        self.assertEqual(tags(embedded), ['SHORT-NAME', 'TROUBLE-CODE', 'DISPLAY-TROUBLE-CODE', 'TEXT', 'LEVEL'])
        self.assertEqual(embedded.findtext('TROUBLE-CODE'), '4097')
        self.assertEqual(embedded.findtext('DISPLAY-TROUBLE-CODE'), 'P0001')
        self.assertEqual(xml(embedded.find('TEXT')), '<TEXT TI="TI_D">Fault</TEXT>')
        self.assertEqual(embedded.findtext('LEVEL'), '2')
        self.assertTrue({'DOP_L_X1', 'DTC_L_A'} <= ctx.used)

    def test_dtc_without_display_code_and_text_id(self):
        ctx = context({'DOP_L_X1': ('DB_DOP_DTC', dtc_dop('DOP1', reference('DTC_L_A'))),
                       'DTC_L_A': ('MCD_DB_DIAG_TROUBLE_CODE', dtc('A', display_trouble_code=None,
                                                                   diag_trouble_code_text_id=None))})
        element = trouble_codes.add_dtc_dop(ctx, ET.Element('X'), 'DOP_L_X1', set())
        embedded = element.find('DTCS/DTC')
        self.assertEqual(tags(embedded), ['SHORT-NAME', 'TROUBLE-CODE', 'TEXT', 'LEVEL'])
        self.assertEqual(xml(embedded.find('TEXT')), '<TEXT>Fault</TEXT>')

    def test_dtc_dop_embeds_own_dtc_once(self):
        ctx = context({'DOP_L_X1': ('DB_DOP_DTC', dtc_dop('DOP1', reference('DTC_L_A'))),
                       'DOP_L_X2': ('DB_DOP_DTC', dtc_dop('DOP2', reference('DTC_L_A'))),
                       'DTC_L_A': ('MCD_DB_DIAG_TROUBLE_CODE', dtc('A'))})
        root = ET.Element('X')
        written = set()
        first = trouble_codes.add_dtc_dop(ctx, root, 'DOP_L_X1', written)
        second = trouble_codes.add_dtc_dop(ctx, root, 'DOP_L_X2', written)
        self.assertEqual(tags(first.find('DTCS')), ['DTC'])
        self.assertEqual(xml(second.find('DTCS')), '<DTCS><DTC-REF ID-REF="A" /></DTCS>')
        self.assertEqual(written, {'DTC_L_A'})
        ids = [element.get('ID') for element in root.iter() if element.get('ID') is not None]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ctx.report['unresolvable_references'], 0)

    def test_dtc_dop_refers_to_dtc_of_other_pool(self):
        ctx = context({'DOP_L_X1': ('DB_DOP_DTC', dtc_dop('DOP1', reference('DTC_M_X', '0.0.0@M.sd')))},
                      object_type=lambda pool, key: 'MCD_DB_DIAG_TROUBLE_CODE' if pool == '0.0.0@M.sd' else None)
        element = trouble_codes.add_dtc_dop(ctx, ET.Element('X'), 'DOP_L_X1', set())
        self.assertEqual(xml(element.find('DTCS')),
                         '<DTCS><DTC-REF ID-REF="X" DOCREF="M" DOCTYPE="LAYER" /></DTCS>')

    def test_missing_own_dtc_is_unresolvable(self):
        ctx = context({'DOP_L_X1': ('DB_DOP_DTC', dtc_dop('DOP1', reference('DTC_L_GONE')))})
        element = trouble_codes.add_dtc_dop(ctx, ET.Element('X'), 'DOP_L_X1', set())
        self.assertEqual(xml(element.find('DTCS')), '<DTCS><DTC-REF ID-REF="DTC_L_GONE" /></DTCS>')
        self.assertEqual(ctx.report['unresolvable_references'], 1)

    def test_dtc_dop_without_dtcs_and_types(self):
        ctx = context({'DOP_L_X1': ('DB_DOP_DTC', dtc_dop('DOP1', compu_method=None, diag_coded_type=None,
                                                          physical_type=None))})
        element = trouble_codes.add_dtc_dop(ctx, ET.Element('X'), 'DOP_L_X1', set())
        self.assertEqual(tags(element), ['SHORT-NAME'])

    def test_dtc_dop_with_only_empty_references_has_no_dtcs(self):
        ctx = context({'DOP_L_X1': ('DB_DOP_DTC', dtc_dop('DOP1', reference('')))})
        element = trouble_codes.add_dtc_dop(ctx, ET.Element('X'), 'DOP_L_X1', set())
        self.assertIsNone(element.find('DTCS'))
        self.assertEqual(ctx.report['empty_references'], 1)

    def test_sdgs_positions(self):
        def fake_sdgs(ctx, parent, obj):
            return ET.SubElement(parent, 'SDGS')

        ctx = context({'DOP_L_X1': ('DB_DOP_DTC', dtc_dop('DOP1', reference('DTC_L_A'))),
                       'DTC_L_A': ('MCD_DB_DIAG_TROUBLE_CODE', dtc('A'))})
        with mock.patch('odx_export.special_data.sdgs', fake_sdgs):
            element = trouble_codes.add_dtc_dop(ctx, ET.Element('X'), 'DOP_L_X1', set())
        self.assertEqual(tags(element), ['SHORT-NAME', 'SDGS', 'DIAG-CODED-TYPE', 'PHYSICAL-TYPE',
                                         'COMPU-METHOD', 'DTCS'])
        self.assertEqual(tags(element.find('DTCS/DTC')), ['SHORT-NAME', 'TROUBLE-CODE', 'DISPLAY-TROUBLE-CODE',
                                                          'TEXT', 'LEVEL', 'SDGS'])


if __name__ == '__main__':
    unittest.main()
