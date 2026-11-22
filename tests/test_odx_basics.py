"""Tests for the naming rule, the pool context and the XML helpers of odx_export."""
import unittest
import xml.etree.ElementTree as ET

from odx_export import elements
from odx_export.naming import layer_name, split_key
from tests.odx_support import context, xml

OWN = '0.0.0@L.sd'


def reference(object_id, pool_id=OWN):
    return {'object_id': object_id, 'pool_id': pool_id}


class NamingTests(unittest.TestCase):
    def test_layer_name_strips_version_and_extension(self):
        self.assertEqual(layer_name('0.0.0@L.sd'), 'L')
        self.assertEqual(layer_name('5.4.0@N.sd'), 'N')
        self.assertEqual(layer_name('0.0.0@P.cs'), 'P')

    def test_split_key(self):
        self.assertEqual(split_key('DOP_L_D1', 'L'), ('DOP_', 'D1'))
        self.assertEqual(split_key('TBP_L_T1.R1', 'L'), ('TBP_', 'T1.R1'))
        self.assertEqual(split_key('STR_L_A', 'L'), ('STR_', 'A'))
        self.assertEqual(split_key('CAPTION_L_7', 'L'), ('CAPTION_', '7'))
        self.assertIsNone(split_key('UNITGR_3', 'L'))
        self.assertIsNone(split_key('DOP_M_D1', 'L'))


class ReferenceTests(unittest.TestCase):
    def test_ref_in_own_pool(self):
        ctx = context({'DOP_L_D1': ('MCD_DB_DIAG_OBJECT_CONNECTOR', {})})
        element = elements.add_ref(ctx, ET.Element('X'), 'DOP-REF', reference('DOP_L_D1'))
        self.assertEqual(xml(element), '<DOP-REF ID-REF="D1" />')

    def test_ref_into_other_pool_of_other_version(self):
        ctx = context({}, object_type=lambda pool, key: 'MCD_DB_DATA_OBJECT_PROP'
                      if (pool, key) == ('5.4.0@N.sd', 'DOP_N_D2') else None)
        element = elements.add_ref(ctx, ET.Element('X'), 'DOP-REF',
                                   reference('DOP_N_D2', '5.4.0@N.sd'))
        self.assertEqual(xml(element), '<DOP-REF ID-REF="D2" DOCREF="N" DOCTYPE="LAYER" />')
        self.assertEqual(ctx.report['unresolvable_references'], 0)

    def test_ref_without_pool_is_snref(self):
        ctx = context({})
        element = elements.add_ref(ctx, ET.Element('X'), 'DOP-REF', reference('D3', None))
        self.assertEqual(xml(element), '<DOP-SNREF SHORT-NAME="D3" />')

    def test_empty_ref_is_omitted_and_counted(self):
        ctx = context({})
        parent = ET.Element('X')
        self.assertIsNone(elements.add_ref(ctx, parent, 'DOP-REF', None))
        self.assertIsNone(elements.add_ref(ctx, parent, 'DOP-REF', reference('', 'x')))
        self.assertEqual(len(parent), 0)
        self.assertEqual(ctx.report['empty_references'], 2)

    def test_unresolvable_ref_keeps_key(self):
        ctx = context({}, object_type=lambda pool, key: None)
        parent = ET.Element('X')
        missing = elements.add_ref(ctx, parent, 'DOP-REF', reference('DOP_N_D9', '5.4.0@N.sd'))
        no_rule = elements.add_ref(ctx, parent, 'DOP-REF', reference('ODD_KEY'))
        self.assertEqual(xml(missing),
                         '<DOP-REF ID-REF="DOP_N_D9" DOCREF="N" DOCTYPE="LAYER" />')
        self.assertEqual(xml(no_rule), '<DOP-REF ID-REF="ODD_KEY" />')
        self.assertEqual(ctx.report['unresolvable_references'], 2)

    def test_foreign_target_without_rule_keeps_key(self):
        ctx = context({}, object_type=lambda pool, key: 'MCD_DB_UNIT')
        element = elements.add_ref(ctx, ET.Element('X'), 'UNIT-REF',
                                   reference('UNITGR_3', '0.0.0@M.sd'))
        self.assertEqual(element.get('ID-REF'), 'UNITGR_3')
        self.assertEqual(ctx.report['unresolvable_references'], 1)


class TextTests(unittest.TestCase):
    def test_invalid_xml_characters_are_replaced_in_text_and_attributes(self):
        ctx = context({})
        parent = ET.Element('X')
        elements.sub(ctx, parent, 'SHORT-NAME', 'a\x1eb')
        elements.add_ref(ctx, parent, 'DOP-REF', reference('c\x1cd', None))
        self.assertEqual(parent[0].text, 'a�b')
        self.assertEqual(parent[1].get('SHORT-NAME'), 'c�d')
        self.assertEqual(ctx.report['replaced_characters'], 2)
        ET.fromstring(xml(parent))

    def test_desc_keeps_markup_and_text_id(self):
        ctx = context({})
        parent = ET.Element('X')
        elements.add_desc(ctx, parent, '<p>x</p>', 'T1')
        self.assertEqual(xml(parent[0]), '<DESC TI="T1"><p>x</p></DESC>')

    def test_malformed_desc_is_written_as_text(self):
        ctx = context({})
        parent = ET.Element('X')
        elements.add_desc(ctx, parent, 'a < b & c', None)
        self.assertEqual(parent[0].text, 'a < b & c')
        self.assertEqual(len(parent[0]), 0)
        self.assertEqual(ctx.report['malformed_descriptions'], 1)

    def test_format_value(self):
        self.assertEqual(elements.format_value(1.0), '1')
        self.assertEqual(elements.format_value(0.25), '0.25')
        self.assertEqual(elements.format_value(b'\x0a\xff'), '0AFF')
        self.assertEqual(elements.format_value(True), 'true')
        self.assertEqual(elements.format_value({'value': 5, 'data_type': 'eA_UINT32'}), '5')
        self.assertIsNone(elements.format_value(None))

    def test_sub_omits_none_attributes_and_maps_named(self):
        ctx = context({})
        element = elements.sub(ctx, ET.Element('X'), 'A', 'v',
                               {elements.XSI_TYPE: 'T', 'GONE': None}, MAX_LENGTH='5', SKIP=None)
        self.assertEqual(element.attrib, {elements.XSI_TYPE: 'T', 'MAX-LENGTH': '5'})

    def test_add_names(self):
        ctx = context({})
        parent = ET.Element('X')
        elements.add_names(ctx, parent, {'short_name': 'S', 'long_name': 'L', 'long_name_id': 'T9',
                                         'description': '<p>d</p>', 'description_id': None})
        self.assertEqual(xml(parent), '<X><SHORT-NAME>S</SHORT-NAME><LONG-NAME TI="T9">L</LONG-NAME>'
                                      '<DESC><p>d</p></DESC></X>')

    def test_identified_writes_oid_only_when_set(self):
        ctx = context({})
        with_oid = elements.identified(ctx, ET.Element('X'), 'A', 'I1', {'unique_object_id': 'U1'})
        without = elements.identified(ctx, ET.Element('X'), 'A', 'I1', {'unique_object_id': None})
        self.assertEqual(xml(with_oid), '<A ID="I1" OID="U1" />')
        self.assertEqual(xml(without), '<A ID="I1" />')


class PoolContextTests(unittest.TestCase):
    def test_keys_ordered_and_take(self):
        ctx = context({'DOP_L_B': ('T', 1), 'DOP_M_X': ('T', 2), 'DOP_L_A': ('T', 3),
                       'TB_L_C': ('U', 4)})
        self.assertEqual(ctx.keys('DOP_'), ['DOP_L_B', 'DOP_L_A'])
        self.assertEqual(ctx.keys('TB_', 'U'), ['TB_L_C'])
        self.assertEqual(ctx.keys('TB_', 'T'), [])
        self.assertEqual(ctx.own_id('DOP_L_A'), 'A')
        self.assertEqual(ctx.take('DOP_L_A'), 3)
        self.assertIn('DOP_L_A', ctx.used)
        self.assertEqual(ctx.ordered([{'reference': reference('DOP_L_A')}, reference('DOP_L_Z')],
                                     ctx.keys('DOP_')), ['DOP_L_A', 'DOP_L_B'])
        self.assertEqual(ctx.ordered(None, ctx.keys('DOP_')), ['DOP_L_B', 'DOP_L_A'])

    def test_target_type(self):
        ctx = context({'DOP_L_A': ('T', 1)},
                      object_type=lambda pool, key: 'F' if pool == '5.4.0@N.sd' else None)
        self.assertEqual(ctx.target_type(reference('DOP_L_A')), 'T')
        self.assertIsNone(ctx.target_type(reference('DOP_L_Q')))
        self.assertEqual(ctx.target_type(reference('DOP_N_A', '5.4.0@N.sd')), 'F')
        self.assertIsNone(ctx.target_type(reference('DOP_M_A', '0.0.0@M.sd')))

    def test_unused_ignores_project_data_and_key_vector(self):
        ctx = context({'DOP_L_A': ('MCD_DB_DATA_OBJECT_PROP', 1), 'DOP_L_B': ('MCD_DB_DATA_OBJECT_PROP', 2),
                       'PROJ': ('DB_PROJECT_DATA', 3), 'KV': ('DB_KEY_VECTOR', 4),
                       'UNIT_L_U': ('MCD_DB_UNIT', 5)})
        ctx.take('DOP_L_A')
        self.assertEqual(dict(ctx.unused()), {'MCD_DB_DATA_OBJECT_PROP': 1, 'MCD_DB_UNIT': 1})

    def test_objects_without_place_are_not_unused(self):
        ctx = context({'TBP_L_X': ('MCD_DB_TABLE_ROW', 1)})
        ctx.mark_without_place('TBP_L_X')
        ctx.mark_without_place('TBP_L_X')
        self.assertEqual(ctx.without_place, ['TBP_L_X'])
        self.assertEqual(dict(ctx.unused()), {})


if __name__ == '__main__':
    unittest.main()
