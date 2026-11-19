import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

try:
    import jpype  # noqa: F401
except ImportError:
    # dumpDTC imports LongNameTranslation, which needs jpype; these tests never translate names
    for stub_name in ('jpype', 'jpype.imports', 'jpype.types'):
        sys.modules[stub_name] = mock.MagicMock()

import dumpAdaptations
import dumpCoding
import dumpDTC
import dumpECUVariantPatterns
import dumpFreezeFrames
import dumpMWB
from common_utils.layer_chain import load_layer_data
from tests.script_support import FakeObjectLoader, layer

UDS_TYPE = 'ISO_15765_3_on_ISO_15765_2'
KWP_TYPE = 'ISO_14230_3_on_ISO_15765_2'
UDS_POOL = '0.0.0@PR_UDSOnCAN.pr'
OBD_POOL = '0.0.0@PR_OBDOnCAN.pr'


def make_loader(layers):
    return FakeObjectLoader({(pool, '#RtGen_DB_LAYER_DATA'): data for pool, data in layers.items()})


def names(layer_data_list):
    return [ld['name'] for ld in layer_data_list]


class VwProtocolListTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = holder.name
        for pool in (UDS_POOL, OBD_POOL):
            open(os.path.join(self.tmp, pool + '.key'), 'w').close()
        self.loader = make_loader({
            'BV.bv': layer(name='BV', parent_layers=['PRX.pr']),
            'PRX.pr': layer(name='PRX'),
            UDS_POOL: layer(name='PR_UDSOnCAN', parent_layers=['ES1.sd', 'ES2.sd']),
            OBD_POOL: layer(name='PR_OBDOnCAN'),
            'ES1.sd': layer(name='ES1.sd'),
            'ES2.sd': layer(name='ES2.sd')})

    def test_vw_protocol_list_matches_upstream(self):
        # PR_UDSOnCAN parents ['ES1.sd', 'ES2.sd']; expected order captured from the upstream function
        expected = ['ES1.sd', 'ES2.sd', 'PR_UDSOnCAN', 'PR_OBDOnCAN']
        self.assertEqual(names(upstream_list(self.loader, self.tmp))[:4], expected)


def upstream_list(loader, tmp):
    return dumpMWB.get_protocol_layer_data_list(loader, tmp, 'BV.bv')


PROJECT_DATA = {'ecu_variant_references': [], 'base_variant_reference': {'object_id': 'BV'}}

# (module, function, arguments before the project folder) of each dump function for one base variant
BASE_VARIANT_DUMPS = [
    (dumpMWB, 'dump_mwbs_for_base_variant', ()),
    (dumpCoding, 'dump_codings_for_base_variant', ()),
    (dumpAdaptations, 'dump_adaptations_for_base_variant', ()),
    (dumpFreezeFrames, 'dump_freezeframes_for_base_variant', ()),
    (dumpDTC, 'dump_dtcs_for_base_variant', (None,)),
    (dumpECUVariantPatterns, 'dump_patterns_for_base_variant', ())]


class BaseVariantProtocolTest(unittest.TestCase):
    def setUp(self):
        load_layer_data.cache_clear()
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = os.path.join(holder.name, 'project')
        self.out = os.path.join(holder.name, 'out')
        os.makedirs(self.tmp)
        open(os.path.join(self.tmp, 'BV.bv.db'), 'w').close()

    def loader(self, protocol_type):
        return FakeObjectLoader({
            ('BV.bv', '#RtGen_DB_LAYER_DATA'): layer(name='BV', parent_layers=['PR.pr']),
            ('BV.bv', '#RtGen_DB_PROJECT_DATA'): PROJECT_DATA,
            ('PR.pr', '#RtGen_DB_LAYER_DATA'): layer(name='PR', protocol_type=protocol_type)})

    def run_captured(self, function, *args):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            function(*args)
        return buffer.getvalue()

    def run_project_function(self, module, function_name, protocol_type, *extra):
        loader = self.loader(protocol_type)
        with mock.patch.object(module, 'ObjectLoader', return_value=loader), \
                mock.patch.object(module, 'StringStorage'):
            return self.run_captured(getattr(module, function_name), self.tmp, self.out, *extra)

    def test_dump_codings_skips_non_uds_base_variant(self):
        # KWP-only chain, no PR_UDSOnCAN pool -> stdout contains 'Not UDS', no output folder created
        output = self.run_captured(dumpCoding.dump_codings_for_base_variant,
                                   self.loader(KWP_TYPE), self.tmp, 'BV.bv.db', self.out)
        self.assertEqual(output, 'Not UDS\n')
        self.assertFalse(os.path.exists(self.out))

    def test_every_script_skips_non_uds_base_variant(self):
        for module, name, extra in BASE_VARIANT_DUMPS:
            with self.subTest(function=name):
                output = self.run_captured(getattr(module, name), self.loader(KWP_TYPE), *extra,
                                           self.tmp, 'BV.bv.db', self.out, False, 2)
                self.assertEqual(output, '    Not UDS\n')
                self.assertFalse(os.path.exists(self.out))

    def test_dump_codings_for_uds_base_variant_without_coding_service(self):
        # BV -> PR(ISO_15765_3_...), BV has no coding service -> 'Has no Coding', no 'Not UDS'
        output = self.run_captured(dumpCoding.dump_codings_for_base_variant,
                                   self.loader(UDS_TYPE), self.tmp, 'BV.bv.db', self.out)
        self.assertIn('Has no Coding', output)
        self.assertNotIn('Not UDS', output)

    def test_dump_mwbs_project_has_no_project_wide_uds_check(self):
        # project folder without PR_UDSOnCAN; dumpMWB_project prints no 'Not UDS project' and visits the UDS BV
        output = self.run_project_function(dumpMWB, 'dumpMWB_project', UDS_TYPE)
        self.assertNotIn('Not UDS project', output)
        self.assertIn('Dumping BV.bv', output)
        self.assertNotIn('Error', output)

    def test_project_functions_report_non_uds_per_base_variant(self):
        for module, name, extra in [(dumpMWB, 'dumpMWB_project', ()), (dumpCoding, 'dumpCoding_project', ()),
                                    (dumpAdaptations, 'dumpAdaptations_project', ()),
                                    (dumpFreezeFrames, 'dumpFreezeFrames_project', ()),
                                    (dumpDTC, 'dumpDTC_project', (None, None)),
                                    (dumpECUVariantPatterns, 'dumpECUVariantPatterns_project', ())]:
            with self.subTest(function=name):
                output = self.run_project_function(module, name, KWP_TYPE, *extra)
                self.assertIn('Dumping BV.bv', output)
                self.assertIn('Not UDS', output)
                self.assertNotIn('Not UDS project', output)

    def test_all_projects_function_visits_non_uds_projects(self):
        holder = os.path.dirname(self.tmp)
        loader = self.loader(KWP_TYPE)
        with mock.patch.object(dumpMWB, 'ObjectLoader', return_value=loader), \
                mock.patch.object(dumpMWB, 'StringStorage'):
            output = self.run_captured(dumpMWB.dump_mwbs_for_all_base_variants_in_all_projects, holder, self.out)
        self.assertNotIn('Not UDS project', output)
        self.assertIn('  Dumping BV.bv', output)
        self.assertIn('    Not UDS', output)


if __name__ == '__main__':
    unittest.main()
