import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import dumpCoding
import dumpDTC
from common_utils.layer_chain import load_layer_data
from common_utils.table_entries import (CODING_SERVICE_NAMES, KIND_ADAPTATION, KIND_CODING, KIND_MWB,
                                        TableEntryReader)
from tests.script_support import FakeObjectLoader, layer
from tests.table_fixtures import table_key_parameter, table_struct_parameter

VW_CODING = 'DiagnServi_WriteDataByIdentVariaCodinTextu'
PORSCHE_CODING = 'CodingValue_Write'
ADAPTATION = 'DiagnServi_WriteDataByIdentCalibData'
MWB = 'DiagnServi_ReadDataByIdentMeasuValue'
UDS_TYPE = 'ISO_15765_3_on_ISO_15765_2'


def ref(name):
    return {'pool_id': 'POOL', 'object_id': name}


def service(name):
    return {'map_key': name, 'reference': ref('service of ' + name)}


def blocked(parent, *names):
    return [{'map_key': parent, 'strings': list(names)}]


def service_objects(*names):
    """Services with a request and a positive response that fit every kind, keyed as TableEntryReader loads them."""
    key = table_key_parameter(ref('T'))
    struct = table_struct_parameter(ref('T'))
    objects = {}
    for name in names:
        objects[('POOL', 'service of ' + name)] = {
            '#OBJECT_TYPE': 'MCD_DB_SERVICE', 'request_reference': ref('request of ' + name),
            'positive_response_references': [{'map_key': 'r', 'reference': ref('response of ' + name)}]}
        objects[('POOL', 'request of ' + name)] = {'request_parameters': [key, struct]}
        objects[('POOL', 'response of ' + name)] = {'response_parameters': [key, struct]}
    return objects


def selected_names(kind, ecu_variant_layer_data, objects=None, *service_names):
    """short_name of every service select_services picks for the kind."""
    all_objects = dict(objects or {})
    all_objects.update(service_objects(*service_names))
    reader = TableEntryReader(FakeObjectLoader(all_objects), 'project')
    return [selected.short_name for selected in reader.select_services(ecu_variant_layer_data, kind)]


class ServiceLookupTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()

    def kinds(self):
        return [(KIND_CODING, VW_CODING), (KIND_ADAPTATION, ADAPTATION), (KIND_MWB, MWB)]

    def test_vw_service_owned_by_variant_is_used(self):
        for kind, name in self.kinds():
            with self.subTest(kind=kind):
                ev = layer(name='EV', diag_com_primitive_references=[service('Other'), service(name)])
                self.assertEqual(selected_names(kind, ev, None, 'Other', name), [name])

    def test_vw_variant_without_any_service_has_none(self):
        for kind, _ in self.kinds():
            with self.subTest(kind=kind):
                ev = layer(name='EV', diag_com_primitive_references=[])
                self.assertEqual(selected_names(kind, ev), [])

    def test_coding_service_names_lists_vw_name_first(self):
        self.assertEqual(CODING_SERVICE_NAMES, (VW_CODING, PORSCHE_CODING))
        self.assertEqual(dumpCoding.CODING_SERVICE_NAMES, CODING_SERVICE_NAMES)

    def test_coding_service_inherited_from_base_variant(self):
        objects = {('BV.bv', '#RtGen_DB_LAYER_DATA'):
                   layer(name='BV', diag_com_primitive_references=[service(PORSCHE_CODING)])}
        ev = layer(name='EV', parent_layers=['BV.bv'])
        self.assertEqual(selected_names(KIND_CODING, ev, objects, PORSCHE_CODING), [PORSCHE_CODING])

    def test_coding_service_not_inherited_when_excluded(self):
        objects = {('BV.bv', '#RtGen_DB_LAYER_DATA'):
                   layer(name='BV', diag_com_primitive_references=[service(PORSCHE_CODING)])}
        ev = layer(name='EV', parent_layers=['BV.bv'],
                   not_inherited_diag_com_primitives=blocked('BV.bv', PORSCHE_CODING))
        self.assertEqual(selected_names(KIND_CODING, ev, objects, PORSCHE_CODING), [])

    def test_vw_coding_name_wins_over_porsche_name(self):
        # the Porsche service comes first in the layer; the VW name still decides
        ev = layer(name='EV', diag_com_primitive_references=[service(PORSCHE_CODING), service(VW_CODING)])
        self.assertEqual(selected_names(KIND_CODING, ev, None, PORSCHE_CODING, VW_CODING), [VW_CODING])

    def test_mwb_and_adaptation_service_inherited_from_functional_group(self):
        fg = layer(name='FG', diag_com_primitive_references=[service(ADAPTATION), service(MWB)])
        for kind, name in [(KIND_ADAPTATION, ADAPTATION), (KIND_MWB, MWB)]:
            with self.subTest(kind=kind):
                load_layer_data.cache_clear()
                ev = layer(name='EV', parent_layers=['FG.fg'])
                self.assertEqual(selected_names(kind, ev, {('FG.fg', '#RtGen_DB_LAYER_DATA'): fg}, ADAPTATION, MWB),
                                 [name])


# Text written by the dumpDTC of the upstream state for a DTC DOP owned by the variant
EXPECTED_DTC_FILE = (
    "(1) {\n  [0] {\n    trouble_code: 0x1\n    dtc: 'P1'\n    level: 0x1\n"
    "    raw_description: 'text 1'\n    translated_description: 'translated'\n  }\n}\n")


class DtcDopTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = os.path.join(holder.name, 'project')
        self.out = os.path.join(holder.name, 'out')
        os.makedirs(self.tmp)

    def dump(self, bv_layer, ev_layer):
        objects = {
            ('BV.bv', '#RtGen_DB_LAYER_DATA'): bv_layer,
            ('BV.bv', '#RtGen_DB_PROJECT_DATA'): {
                'ecu_variant_references': [{'name': 'EV', 'reference': 'EV-reference'}],
                'base_variant_reference': {'object_id': 'BV'}},
            ('PR.pr', '#RtGen_DB_LAYER_DATA'): layer(name='PR', protocol_type=UDS_TYPE),
            ('POOL', 'DOP_A'): {'diag_trouble_code_references': [{'map_key': 1, 'reference': ref('DTC_1')}]},
            ('POOL', 'DOP_B'): {'diag_trouble_code_references': [{'map_key': 2, 'reference': ref('DTC_2')}]},
            ('POOL', 'DTC_1'): self.dtc(1), ('POOL', 'DTC_2'): self.dtc(2)}
        loader = FakeObjectLoader(objects)
        translation = mock.Mock()
        translation.get_long_name_translation.return_value = 'translated'
        with mock.patch.object(dumpDTC, 'get_ecu_variant_layer_data', return_value=ev_layer), \
                contextlib.redirect_stdout(io.StringIO()):
            dumpDTC.dump_dtcs_for_base_variant(loader, translation, self.tmp, 'BV.bv.db', self.out)

    @staticmethod
    def dtc(code):
        return {'trouble_code': code, 'diag_trouble_code_text_id': 'P{}'.format(code), 'level': 1,
                'dtc_text': 'text {}'.format(code), 'display_trouble_code': 'display {}'.format(code)}

    def read(self, filename):
        with open(os.path.join(self.out, 'BV', filename), encoding='utf-8') as file:
            return file.read()

    def bv_layer(self, **fields):
        return layer(name='BV', parent_layers=['PR.pr'], **fields)

    def test_vw_dtc_file_for_own_dtc_dop(self):
        ev = layer(name='EV', dtc_dop_names=['DOP_A'], dop_references=[{'map_key': 'DOP_A', 'reference': ref('DOP_A')}])
        self.dump(self.bv_layer(), ev)
        self.assertEqual(self.read('DOP_A_EV.c'), EXPECTED_DTC_FILE)

    def test_dtc_dop_inherited_from_base_variant_is_dumped_for_variant(self):
        bv = self.bv_layer(dtc_dop_names=['DOP_B'], dop_references=[{'map_key': 'DOP_B', 'reference': ref('DOP_B')}])
        self.dump(bv, layer(name='EV', parent_layers=['BV.bv']))
        self.assertIn('trouble_code', self.read('DOP_B_EV.c'))

    def test_dtc_dop_hidden_by_not_inherited_is_not_dumped(self):
        bv = self.bv_layer(dtc_dop_names=['DOP_B'], dop_references=[{'map_key': 'DOP_B', 'reference': ref('DOP_B')}])
        ev = layer(name='EV', parent_layers=['BV.bv'], not_inherited_dops=blocked('BV.bv', 'DOP_B'))
        self.dump(bv, ev)
        self.assertFalse(os.path.exists(os.path.join(self.out, 'BV', 'DOP_B_EV.c')))


if __name__ == '__main__':
    unittest.main()
