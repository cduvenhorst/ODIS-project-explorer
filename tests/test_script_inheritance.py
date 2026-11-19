import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

import dumpAdaptations
import dumpCoding
import dumpDTC
import dumpMWB
from common_utils.layer_chain import load_layer_data
from tests.script_support import FakeObjectLoader, layer

VW_CODING = 'DiagnServi_WriteDataByIdentVariaCodinTextu'
PORSCHE_CODING = 'CodingValue_Write'
ADAPTATION = 'DiagnServi_WriteDataByIdentCalibData'
MWB = 'DiagnServi_ReadDataByIdentMeasuValue'
UDS_TYPE = 'ISO_15765_3_on_ISO_15765_2'


class ServiceLoaded(Exception):
    """Raised by the loader as soon as a service is loaded; carries the reference."""

    def __init__(self, reference):
        super().__init__(reference)
        self.reference = reference


class SentinelLoader(FakeObjectLoader):
    def load_object_by_reference(self, input_folder_path, reference):
        raise ServiceLoaded(reference)


def ref(name):
    return {'pool_id': 'POOL', 'object_id': name}


def service(name):
    return {'map_key': name, 'reference': ref('service of ' + name)}


def blocked(parent, *names):
    return [{'map_key': parent, 'strings': list(names)}]


def loaded_reference(function, ecu_variant_layer_data, objects=None):
    """Call a get_*_keys_and_table function; return the reference of the service it loads, or None."""
    loader = SentinelLoader(objects or {})
    try:
        result = function(loader, [], 'project', ecu_variant_layer_data)
    except ServiceLoaded as loaded:
        return loaded.reference
    assert result is None, result
    return None


class ServiceLookupTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()

    def lookups(self):
        return [(dumpCoding.get_coding_keys_and_table, VW_CODING),
                (dumpAdaptations.get_adaptation_keys_and_table, ADAPTATION),
                (dumpMWB.get_mwb_keys_and_table, MWB)]

    def test_vw_coding_service_owned_by_variant_is_used(self):
        for function, name in self.lookups():
            with self.subTest(function=function.__name__):
                ev = layer(name='EV', diag_com_primitive_references=[service('Other'), service(name)])
                self.assertEqual(loaded_reference(function, ev), ref('service of ' + name))

    def test_vw_variant_without_any_service_has_none(self):
        for function, _ in self.lookups():
            with self.subTest(function=function.__name__):
                ev = layer(name='EV', diag_com_primitive_references=[service('Other')])
                self.assertIsNone(loaded_reference(function, ev))

    def test_coding_service_names_lists_vw_name_first(self):
        self.assertEqual(dumpCoding.CODING_SERVICE_NAMES, (VW_CODING, PORSCHE_CODING))

    def test_coding_service_inherited_from_base_variant(self):
        loader_objects = {('BV.bv', '#RtGen_DB_LAYER_DATA'):
                          layer(name='BV', diag_com_primitive_references=[service(PORSCHE_CODING)])}
        ev = layer(name='EV', parent_layers=['BV.bv'])
        loader = SentinelLoader(loader_objects)
        with self.assertRaises(ServiceLoaded) as raised:
            dumpCoding.get_coding_keys_and_table(loader, [], 'project', ev)
        self.assertEqual(raised.exception.reference, ref('service of ' + PORSCHE_CODING))

    def test_coding_service_not_inherited_when_excluded(self):
        loader = SentinelLoader({('BV.bv', '#RtGen_DB_LAYER_DATA'):
                                 layer(name='BV', diag_com_primitive_references=[service(PORSCHE_CODING)])})
        ev = layer(name='EV', parent_layers=['BV.bv'],
                   not_inherited_diag_com_primitives=blocked('BV.bv', PORSCHE_CODING))
        self.assertIsNone(dumpCoding.get_coding_keys_and_table(loader, [], 'project', ev))

    def test_vw_coding_name_wins_over_porsche_name(self):
        # the Porsche service comes first in the layer; the VW name still decides
        ev = layer(name='EV', diag_com_primitive_references=[service(PORSCHE_CODING), service(VW_CODING)])
        self.assertEqual(loaded_reference(dumpCoding.get_coding_keys_and_table, ev), ref('service of ' + VW_CODING))

    def test_mwb_and_adaptation_service_inherited_from_functional_group(self):
        fg = layer(name='FG', diag_com_primitive_references=[service(ADAPTATION), service(MWB)])
        for function, name in [(dumpAdaptations.get_adaptation_keys_and_table, ADAPTATION),
                               (dumpMWB.get_mwb_keys_and_table, MWB)]:
            with self.subTest(function=function.__name__):
                load_layer_data.cache_clear()
                loader = SentinelLoader({('FG.fg', '#RtGen_DB_LAYER_DATA'): fg})
                ev = layer(name='EV', parent_layers=['FG.fg'])
                with self.assertRaises(ServiceLoaded) as raised:
                    function(loader, [], 'project', ev)
                self.assertEqual(raised.exception.reference, ref('service of ' + name))


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
