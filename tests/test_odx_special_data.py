import unittest
import xml.etree.ElementTree as ET

from odx_export.special_data import sdgs
from tests.odx_support import context, xml

NAMES = {7: 'CAPTION_L_7', 8: 'CAPTION_L_8', 9: 'STRANGE_NAME'}


def make_ctx():
    return context({}, key_name=NAMES.get)


def caption(short_name='CAP', **fields):
    result = {'short_name': short_name, 'long_name': None, 'description': None,
              'long_name_id': '', 'description_id': '', 'unique_object_id': ''}
    result.update(fields)
    return result


def group(items, caption_obj=None, key=None, si='', **fields):
    result = {'items': items, 'semantic_information': si,
              'caption_reference': None if key is None else {'object_key': key, 'pool_id': '0.0.0@L.sd'},
              'caption': caption_obj}
    result.update(fields)
    return result


def element(content='x', si='', text_id=''):
    return {'content': content, 'semantic_information': si, 'text_id': text_id}


def run(ctx, groups):
    parent = ET.Element('P')
    sdgs(ctx, parent, {'special_data_groups': groups})
    return parent


class SpecialDataTest(unittest.TestCase):
    def test_sdg_with_elements_and_nested_group(self):
        ctx = make_ctx()
        inner = group([element('b', si='SIB', text_id='TB')], si='SII')
        outer = group([element('a', si='SIA', text_id='TA'), None, inner], si='SIO')
        parent = run(ctx, [outer])
        self.assertEqual(
            '<P><SDGS><SDG SI="SIO"><SD SI="SIA" TI="TA">a</SD>'
            '<SDG SI="SII"><SD SI="SIB" TI="TB">b</SD></SDG></SDG></SDGS></P>', xml(parent))

    def test_empty_texts_give_no_attributes(self):
        parent = run(make_ctx(), [group([element('a')])])
        self.assertEqual('<P><SDGS><SDG><SD>a</SD></SDG></SDGS></P>', xml(parent))

    def test_caption_first_time_then_ref(self):
        ctx = make_ctx()
        cap = caption(long_name='Long', long_name_id='LT', description='Desc',
                      description_id='DT', unique_object_id='OID-1')
        parent = run(ctx, [group([element('a')], cap, 7), group([element('b')], cap, 7)])
        root = ET.fromstring(xml(parent))
        first, second = root.findall('SDGS/SDG')
        self.assertEqual(
            '<SDG-CAPTION ID="7" OID="OID-1"><SHORT-NAME>CAP</SHORT-NAME>'
            '<LONG-NAME TI="LT">Long</LONG-NAME><DESC TI="DT">Desc</DESC></SDG-CAPTION>',
            ET.tostring(first[0], encoding='unicode'))
        self.assertEqual('SDG-CAPTION-REF', second[0].tag)
        self.assertEqual('7', second[0].get('ID-REF'))
        ids = [e.get('ID') for e in root.iter() if e.get('ID')]
        self.assertEqual(['7'], ids)
        self.assertEqual(0, ctx.report['unresolvable_references'])

    def test_caption_ids_are_per_document(self):
        cap = caption()
        first = run(make_ctx(), [group([], cap, 7)])
        second = run(make_ctx(), [group([], cap, 7)])
        self.assertEqual('SDG-CAPTION', first.find('SDGS/SDG')[0].tag)
        self.assertEqual('SDG-CAPTION', second.find('SDGS/SDG')[0].tag)

    def test_unresolvable_caption_and_group_are_counted(self):
        ctx = make_ctx()
        parent = run(ctx, [group([], 'not resolvable', 7),
                           'not resolvable',
                           group([], 'not resolvable', 9),
                           group([], 'not resolvable', 5),
                           group([], caption(), 9)])
        sdg = parent.findall('SDGS/SDG')
        self.assertEqual(4, len(sdg))
        self.assertEqual('CAPTION_L_7', sdg[0][0].get('ID-REF'))
        self.assertEqual('STRANGE_NAME', sdg[1][0].get('ID-REF'))
        self.assertEqual('hash 5', sdg[2][0].get('ID-REF'))
        self.assertEqual('STRANGE_NAME', sdg[3][0].get('ID-REF'))
        self.assertEqual({'SDG-CAPTION-REF'}, {s[0].tag for s in sdg})
        self.assertEqual(4, ctx.report['unresolvable_references'])
        self.assertEqual(1, ctx.report['unresolvable_sdgs'])

    def test_no_groups_gives_no_sdgs(self):
        for obj in ({}, {'special_data_groups': []}, {'special_data_groups': None}):
            parent = ET.Element('P')
            self.assertIsNone(sdgs(make_ctx(), parent, obj))
            self.assertEqual('<P />', xml(parent))

    def test_only_unresolvable_groups_give_no_sdgs(self):
        ctx = make_ctx()
        parent = run(ctx, ['not resolvable'])
        self.assertEqual('<P />', xml(parent))
        self.assertEqual(1, ctx.report['unresolvable_sdgs'])

    def test_unresolvable_group_as_special_data_groups_value(self):
        ctx = make_ctx()
        parent = ET.Element('P')
        sdgs(ctx, parent, {'special_data_groups': 'not resolvable'})
        self.assertEqual('<P />', xml(parent))
        self.assertEqual(1, ctx.report['unresolvable_sdgs'])


if __name__ == '__main__':
    unittest.main()
