"""Protection tests for the current (VW) layouts of the project, vehicle and ECU loaders.

Every body is built exactly as the loader reads it today and the complete result is
asserted, in strict mode.  Branches in which the loaders raise today are not pinned.
Where a loader reads an object of any type, MCD_AUDIENCE stands in because its body is
the smallest; the loader does not look at the type.
The ECU loader follows the kernel for its three identifiers: unique_object_id,
long_name_id and description_id always appear as keys (None when empty) instead of the
first being required empty.
The functional class, vehicle information, physical vehicle link, vehicle connector and
connector pin loaders do the same for description_id, long_name_id and unique_object_id,
which stand before the description in their name block.
The vehicle information data loader follows the kernel: the second counter introduces the
collection base_var_prot_id_to_link_info_map instead of having to be 0.  The access key
loader accepts an empty or short last string (stored as layer_data_object_id) instead of
indexing into it.
The layer data loader follows the kernel: unk_string, unk_map1 and unk_map2 are named
unknown_1, not_inherited_tables_map and not_inherited_diag_comms_map, and the state chart,
sub component, additional audience, special data group and multiple ECU job references are
read as the keys ecu_state_chart_refs_map, sub_component_refs_map,
additional_audience_refs_map, special_data_group_refs (None without presence byte) and
multiple_ecu_job_refs_map instead of having to be empty.
"""
import importlib
import unittest

import object_loaders
from tests.support import (NAMED_REFS, ObjectBytes, attributed_ref, attributed_ref_body, audience,
                           audience_body, concat, diag_com_ref, diag_com_ref_body,
                           diag_com_refs, diag_com_refs_body, load, named_refs, named_refs_body,
                           object_type_code, ref_body, typed)

# ---------------------------------------------------------------------------
# Shared pieces
# ---------------------------------------------------------------------------


def strings_body(body, prefix, count):
    """ASCII string vector with a 16 bit count."""
    body.u16(count)
    for i in range(1, count + 1):
        body.ascii('%s%d' % (prefix, i))
    return body


def strings(prefix, count):
    return ['%s%d' % (prefix, i) for i in range(1, count + 1)]


def ref_map_body(body, prefix, count, vector=False):
    """String to reference map; with vector each reference carries two strings."""
    body.u16(count)
    for i in range(1, count + 1):
        body.ascii('%sK%d' % (prefix, i)).ascii('%sR%d' % (prefix, i)).ascii('%sP%d' % (prefix, i))
        if vector:
            body.u8(2).ascii('%sS%da' % (prefix, i)).ascii('%sS%db' % (prefix, i))
    return body


def ref_map(prefix, count, vector=False):
    result = []
    for i in range(1, count + 1):
        reference = {'object_id': '%sR%d' % (prefix, i), 'pool_id': '%sP%d' % (prefix, i)}
        if vector:
            reference['strings'] = ['%sS%da' % (prefix, i), '%sS%db' % (prefix, i)]
        result.append({'map_key': '%sK%d' % (prefix, i), 'reference': reference})
    return result


def vector_map_body(body, prefix, count):
    """String to string vector map; every vector holds two strings."""
    body.u16(count)
    for i in range(1, count + 1):
        body.ascii('%sK%d' % (prefix, i)).u16(2)
        body.ascii('%sV%da' % (prefix, i)).ascii('%sV%db' % (prefix, i))
    return body


def vector_map(prefix, count):
    return [{'map_key': '%sK%d' % (prefix, i),
             'strings': ['%sV%da' % (prefix, i), '%sV%db' % (prefix, i)]}
            for i in range(1, count + 1)]


def ref3_body(body, prefix):
    """DbObjectReference with the third string."""
    return body.ascii(prefix + 'R').ascii(prefix + 'P').ascii(prefix + 'R2')


def ref3(prefix):
    return {'object_id': prefix + 'R', 'pool_id': prefix + 'P', 'object_id2': prefix + 'R2'}


def object_map_body(body, prefix, full):
    """String to object map: one present object, one absent object."""
    if not full:
        return body.u16(0)
    body.u16(2).ascii(prefix + 'K1').nested('MCD_AUDIENCE', audience_body())
    return body.ascii(prefix + 'K2').absent()


def object_map(prefix, full):
    if not full:
        return []
    return [{'map_key': prefix + 'K1', 'object': audience()},
            {'map_key': prefix + 'K2', 'object': None}]


def described_body(body):
    """The three identifiers, then description, long name and short name."""
    body.ascii(None).ascii(None).ascii(None)
    return body.unicode('Description').unicode('Long name').ascii('Name')


def described():
    return {'description': 'Description', 'long_name': 'Long name', 'short_name': 'Name'}


def described_ids():
    """Expectation of the reversed name block with all three identifiers empty."""
    return {'description_id': None, 'long_name_id': None, 'unique_object_id': None,
            **described()}


# ---------------------------------------------------------------------------
# Access key and ECU
# ---------------------------------------------------------------------------

LOCATION_TYPES = [(0x0101, 'ECU_BASE_VARIANT'), (0x0102, 'ECU_VARIANT'),
                  (0x0103, 'FUNCTIONAL_GROUP'), (0x0104, 'MULTIPLE_ECU_JOB'), (0x0105, 'PROTOCOL')]
POOL_ID = 'A.B.C@VARIANT.vi'
ACCESS_KEY_STRING = '[Protocol]PROT.[FunctionalGroup]FG.[EcuBaseVariant]BV.[EcuVariant]EV'


def access_key_body(full=False, location=0x0101, last=''):
    """MCD_ACCESS_KEY; full sets every name and uses a pool identifier as last string."""
    body = ObjectBytes()
    for text in (['BV', 'BVID', 'EV', 'EVID', 'FG', 'MEJ', 'PROT'] if full else [None] * 7):
        body.ascii(text)
    if last == '':
        last = POOL_ID if full else 'LAYER-1'
    return body.u16(location).ascii(last)


def access_key_fields(full=False, location_type='ECU_BASE_VARIANT'):
    fields = {'ecu_base_variant': None, 'ecu_base_variant_id': None, 'ecu_variant': None,
              'ecu_variant_id': None, 'functional_group': None, 'multiple_ecu_job': None,
              'protocol': None, 'location_type': location_type, 'string': ''}
    if full:
        fields.update(ecu_base_variant='BV', ecu_base_variant_id='BVID', ecu_variant='EV',
                      ecu_variant_id='EVID', functional_group='FG', multiple_ecu_job='MEJ',
                      protocol='PROT', pool_id=POOL_ID, string=ACCESS_KEY_STRING)
    else:
        fields['layer_data_object_id'] = 'LAYER-1'
    return fields


def access_key(full=False, location_type='ECU_BASE_VARIANT'):
    return typed('MCD_ACCESS_KEY', access_key_fields(full, location_type))


ECU_LOCATIONS = [('L1', 'O1', 'P1', False), ('L2', 'O2', 'P2', True)]


def ecu_body(body, locations=(), unique_object_id=None):
    """MCD_DB_ECU body (also the tail of the variant and group loaders)."""
    body.ascii('Ecu').unicode('Ecu long').unicode('Ecu description').ascii(unique_object_id)
    body.ascii('LongId').ascii('DescId').u16(len(locations))
    for name, object_id, pool_id, with_key in locations:
        body.ascii(name).ascii(object_id).ascii(pool_id)
        if with_key:
            body.nested('MCD_ACCESS_KEY', access_key_body(True))
        else:
            body.absent()
    return body


def ecu_fields(locations=(), unique_object_id=None):
    return {'short_name': 'Ecu', 'long_name': 'Ecu long', 'description': 'Ecu description',
            'unique_object_id': unique_object_id, 'long_name_id': 'LongId', 'description_id': 'DescId',
            'location_refs': [{'name': name,
                               'reference': {'object_id': object_id, 'pool_id': pool_id,
                                             'access_key': access_key(True) if with_key else None}}
                              for name, object_id, pool_id, with_key in locations]}


def ecu_part(locations=()):
    """The ECU as the variant and group loaders embed it."""
    return typed('MCD_DB_ECU', ecu_fields(locations))


class AccessKeyTests(unittest.TestCase):
    def test_mcd_access_key_minimal(self):
        body = access_key_body()
        self.assertEqual(load('MCD_ACCESS_KEY', body), access_key())

    def test_mcd_access_key_all_branches(self):
        body = access_key_body(True)
        self.assertEqual(load('MCD_ACCESS_KEY', body), access_key(True))

    def test_mcd_access_key_location_types(self):
        for code, name in LOCATION_TYPES:
            with self.subTest(location=name):
                body = access_key_body(location=code)
                self.assertEqual(load('MCD_ACCESS_KEY', body), access_key(location_type=name))

    def test_mcd_access_key_empty_last_string(self):
        expected = access_key_fields()
        expected['layer_data_object_id'] = None
        self.assertEqual(load('MCD_ACCESS_KEY', access_key_body(last=None)),
                         typed('MCD_ACCESS_KEY', expected))

    def test_mcd_access_key_short_last_string(self):
        expected = access_key_fields()
        expected['layer_data_object_id'] = 'L1'
        self.assertEqual(load('MCD_ACCESS_KEY', access_key_body(last='L1')),
                         typed('MCD_ACCESS_KEY', expected))


class EcuTests(unittest.TestCase):
    def test_mcd_db_ecu_minimal(self):
        body = ecu_body(ObjectBytes())
        self.assertEqual(load('MCD_DB_ECU', body), typed('MCD_DB_ECU', ecu_fields()))

    def test_mcd_db_ecu_all_branches(self):
        body = ecu_body(ObjectBytes(), ECU_LOCATIONS)
        self.assertEqual(load('MCD_DB_ECU', body), typed('MCD_DB_ECU', ecu_fields(ECU_LOCATIONS)))

    def test_mcd_db_ecu_identifiers(self):
        body = ObjectBytes().ascii('Ecu').unicode('Ecu long').unicode('Ecu description')
        body.ascii('UOI').ascii('LNID').ascii('DID').u16(0)
        self.assertEqual(load('MCD_DB_ECU', body), {
            '#OBJECT_TYPE': 'MCD_DB_ECU', 'short_name': 'Ecu', 'long_name': 'Ecu long',
            'description': 'Ecu description', 'unique_object_id': 'UOI',
            'long_name_id': 'LNID', 'description_id': 'DID', 'location_refs': []})


# ---------------------------------------------------------------------------
# Variants and groups
# ---------------------------------------------------------------------------

def matching_patterns_body(body, full):
    """Two entries: one with a pattern collection, one without an object."""
    if not full:
        return body.u16(0)
    body.u16(2).ascii('MP1').nested('MCD_DB_MATCHING_PATTERNS', ObjectBytes().u32(0))
    return body.ascii('MP2').absent()


def matching_patterns(full):
    if not full:
        return []
    return [{'short_name': 'MP1', 'items': []}, {'short_name': 'MP2', 'items': None}]


class EcuBaseVariantTests(unittest.TestCase):
    def test_mcd_db_ecu_base_variant_minimal(self):
        body = named_refs_body(ObjectBytes())
        matching_patterns_body(body, False)
        ecu_body(body)
        self.assertEqual(load('MCD_DB_ECU_BASE_VARIANT', body), typed('MCD_DB_ECU_BASE_VARIANT', {
            'ecu_variant_ref_collection': [], 'matching_patterns': [], 'ecu': ecu_part()}))

    def test_mcd_db_ecu_base_variant_all_branches(self):
        body = named_refs_body(ObjectBytes(), NAMED_REFS)
        matching_patterns_body(body, True)
        ecu_body(body, ECU_LOCATIONS)
        self.assertEqual(load('MCD_DB_ECU_BASE_VARIANT', body), typed('MCD_DB_ECU_BASE_VARIANT', {
            'ecu_variant_ref_collection': named_refs(NAMED_REFS),
            'matching_patterns': matching_patterns(True), 'ecu': ecu_part(ECU_LOCATIONS)}))


class EcuVariantTests(unittest.TestCase):
    def test_mcd_db_ecu_variant_minimal(self):
        body = ref_body(ObjectBytes(), 'BV', 'BVPOOL').absent()
        ecu_body(body)
        self.assertEqual(load('MCD_DB_ECU_VARIANT', body), typed('MCD_DB_ECU_VARIANT', {
            'ecu_base_variant_ref': {'object_id': 'BV', 'pool_id': 'BVPOOL'},
            'matching_patterns': None, 'ecu': ecu_part()}))

    def test_mcd_db_ecu_variant_all_branches(self):
        body = ref_body(ObjectBytes(), 'BV', 'BVPOOL')
        body.nested('MCD_DB_MATCHING_PATTERNS', ObjectBytes().u32(0))
        ecu_body(body, ECU_LOCATIONS)
        self.assertEqual(load('MCD_DB_ECU_VARIANT', body), typed('MCD_DB_ECU_VARIANT', {
            'ecu_base_variant_ref': {'object_id': 'BV', 'pool_id': 'BVPOOL'},
            'matching_patterns': [], 'ecu': ecu_part(ECU_LOCATIONS)}))


class FunctionalGroupTests(unittest.TestCase):
    def test_mcd_db_functional_group_minimal(self):
        body = ecu_body(named_refs_body(ObjectBytes()))
        self.assertEqual(load('MCD_DB_FUNCTIONAL_GROUP', body), typed('MCD_DB_FUNCTIONAL_GROUP', {
            'group_member_ref_collection': [], 'ecu': ecu_part()}))

    def test_mcd_db_functional_group_all_branches(self):
        body = ecu_body(named_refs_body(ObjectBytes(), NAMED_REFS), ECU_LOCATIONS)
        self.assertEqual(load('MCD_DB_FUNCTIONAL_GROUP', body), typed('MCD_DB_FUNCTIONAL_GROUP', {
            'group_member_ref_collection': named_refs(NAMED_REFS),
            'ecu': ecu_part(ECU_LOCATIONS)}))


class FunctionalClassTests(unittest.TestCase):
    def test_mcd_db_functional_class_minimal(self):
        body = ObjectBytes().ascii(None).ascii(None).ascii(None)
        body.unicode(None).unicode(None).ascii(None).u16(0)
        self.assertEqual(load('MCD_DB_FUNCTIONAL_CLASS', body), typed('MCD_DB_FUNCTIONAL_CLASS', {
            'description_id': None, 'long_name_id': None, 'unique_object_id': None,
            'description': None, 'long_name': None, 'short_name': None,
            'data_primitive_refs': []}))

    def test_mcd_db_functional_class_all_branches(self):
        body = ObjectBytes().ascii(None).ascii(None).ascii(None)
        body.unicode('Description').unicode('Long name').ascii('Name')
        diag_com_refs_body(body)
        self.assertEqual(load('MCD_DB_FUNCTIONAL_CLASS', body), typed('MCD_DB_FUNCTIONAL_CLASS', {
            **described_ids(), 'data_primitive_refs': diag_com_refs()}))


IDS = {'description_id': 'DID', 'long_name_id': 'LNID', 'unique_object_id': 'UOI'}


def reversed_names_body(body):
    """Reversed name block with filled identifiers and empty texts."""
    body.ascii('DID').ascii('LNID').ascii('UOI')
    return body.unicode(None).unicode(None).ascii(None)


EMPTY_NAMES = {'description': None, 'long_name': None, 'short_name': None}


class ReversedNameBlockIdentifierTests(unittest.TestCase):
    def test_mcd_db_functional_class_identifiers(self):
        body = reversed_names_body(ObjectBytes()).u16(0)
        self.assertEqual(load('MCD_DB_FUNCTIONAL_CLASS', body), typed(
            'MCD_DB_FUNCTIONAL_CLASS', {**IDS, **EMPTY_NAMES, 'data_primitive_refs': []}))

    def test_mcd_db_physical_vehicle_link_or_interface_identifiers(self):
        pin_part = reversed_names_body(ObjectBytes()).u16(1).u16(0x7400)
        pins = ObjectBytes().u16(1).nested('MCD_DB_VEHICLE_CONNECTOR_PIN', pin_part)
        body = reversed_names_body(ObjectBytes()).ascii(None)
        body.nested('MCD_DB_VEHICLE_CONNECTOR_PINS', pins)
        self.assertEqual(load('MCD_DB_PHYSICAL_VEHICLE_LINK_OR_INTERFACE', body), typed(
            'MCD_DB_PHYSICAL_VEHICLE_LINK_OR_INTERFACE', {
                **IDS, **EMPTY_NAMES, 'type': None,
                'vehicle_connector_pins': [typed('MCD_DB_VEHICLE_CONNECTOR_PIN', {
                    **IDS, **EMPTY_NAMES, 'pin_number': 1, 'pin_type': None})]}))

    def test_mcd_db_vehicle_information_identifiers(self):
        body = reversed_names_body(ObjectBytes()).u16(0).u16(0).absent()
        self.assertEqual(load('MCD_DB_VEHICLE_INFORMATION', body), typed(
            'MCD_DB_VEHICLE_INFORMATION', {
                **IDS, **EMPTY_NAMES, 'logical_links': [],
                'physical_vehicle_links_or_interfaces': [], 'vehicle_connectors': None}))

    def test_mcd_db_vehicle_connector_identifiers(self):
        body = reversed_names_body(ObjectBytes()).absent()
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTOR', body), typed(
            'MCD_DB_VEHICLE_CONNECTOR', {**IDS, **EMPTY_NAMES, 'connector_pins': None}))

    def test_mcd_db_vehicle_connector_pin_identifiers(self):
        body = reversed_names_body(ObjectBytes()).u16(3).u16(0x7400)
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTOR_PIN', body), typed(
            'MCD_DB_VEHICLE_CONNECTOR_PIN', {
                **IDS, **EMPTY_NAMES, 'pin_number': 3, 'pin_type': None}))


# ---------------------------------------------------------------------------
# Logical link, layer data, project data
# ---------------------------------------------------------------------------

GATEWAY_MODES = [(0x6E03, 'eNO_GATEWAY'), (0x6E01, 'eTRANSPARENT_GATEWAY'),
                 (0x6E02, 'eVISIBLE_GATEWAY')]


def logical_link_body(full=False, gateway=0x6E03):
    body = ObjectBytes().ascii('Link').unicode('Link long').unicode('Link description')
    body.ascii('UID').ascii('LongId').ascii('DescId').ascii('ProtoShort')
    body.ascii('BaseVariantId').ascii('FunctionalGroupId').ascii('ProtoType')
    body.u16(0)
    ref3_body(body, 'PVL')
    body.u16(gateway).flag(full)
    object_map_body(body, 'Param', full)
    return object_map_body(body, 'Complex', full)


def logical_link(full=False, gateway='eNO_GATEWAY'):
    return typed('MCD_DB_LOGICAL_LINK', {
        'short_name': 'Link', 'long_name': 'Link long', 'description': 'Link description',
        'unique_object_id': 'UID', 'long_name_id': 'LongId', 'description_id': 'DescId',
        'protocol_short_name': 'ProtoShort', 'base_variant_id': 'BaseVariantId',
        'functional_group_id': 'FunctionalGroupId', 'protocol_type': 'ProtoType',
        'physical_vehicle_link_or_interface_ref': ref3('PVL'), 'gateway_mode': gateway,
        'accessed_via_gateway': full, 'link_com_params_map': object_map('Param', full),
        'link_complex_com_params_map': object_map('Complex', full)})


class LogicalLinkTests(unittest.TestCase):
    def test_mcd_db_logical_link_minimal(self):
        self.assertEqual(load('MCD_DB_LOGICAL_LINK', logical_link_body()), logical_link())

    def test_mcd_db_logical_link_all_branches(self):
        body = logical_link_body(True, 0x6E01)
        self.assertEqual(load('MCD_DB_LOGICAL_LINK', body),
                         logical_link(True, 'eTRANSPARENT_GATEWAY'))

    def test_mcd_db_logical_link_gateway_modes(self):
        for code, name in GATEWAY_MODES:
            with self.subTest(gateway=name):
                body = logical_link_body(gateway=code)
                self.assertEqual(load('MCD_DB_LOGICAL_LINK', body), logical_link(gateway=name))


LAYER_LOCATION_REFS = {0x0101: 'ecu_base_variant_ref', 0x0102: 'ecu_variant_ref',
                       0x0103: 'functional_group_ref'}


def layer_data_body(full=False, location=0x0104, kernel_collections=False, byte=True):
    """DB_LAYER_DATA; full gives every collection two entries.

    kernel_collections fills the state chart, sub component, additional audience, special
    data group and multiple ECU job references.
    """
    n = 2 if full else 0
    body = ObjectBytes().ascii('Layer').ascii('Unknown').ascii('ProtoType').ascii('Stack')
    body.ascii('ComParamPool').u16(location)
    if location in LAYER_LOCATION_REFS:
        ref_body(body, 'LOC', 'LOCPOOL')
    if full:
        diag_com_refs_body(body)
    else:
        body.u16(0)
    strings_body(body, 'Dtc', n)
    ref_map_body(body, 'Dop', n)
    ref_map_body(body, 'Table', n, vector=True)
    ref_map_body(body, 'Request', n)
    ref_map_body(body, 'Negative', n)
    ref_map_body(body, 'Class', n)
    body.u16(n)
    for i in range(1, n + 1):
        body.ascii('Primitive%d' % i)
        diag_com_refs_body(body)
    if kernel_collections:
        body.u16(1).ascii('SC1')
        attributed_ref_body(body, ('A1',))
        body.u16(1).ascii('SUB1')
        attributed_ref_body(body)
        body.u16(1).ascii('AA1').ascii('AUD1').ascii('POOL')
    else:
        body.u16(0).u16(0).u16(0)
    body.u16(n)
    if full:
        body.ascii('Env1').nested('MCD_AUDIENCE', audience_body()).ascii('Env2').absent()
    strings_body(body, 'Parent', n)
    strings_body(body, 'Shared', n)
    for prefix in ('NotInherited', 'Unknown1', 'Unknown2', 'NotNegative'):
        vector_map_body(body, prefix, n)
    ref_map_body(body, 'UnitGroup', n)
    ref_map_body(body, 'Unit', n)
    body.u16(n)
    if full:
        body.nested('MCD_AUDIENCE', audience_body()).absent()
    if byte:
        body.u8(0)
    if kernel_collections:
        body.u8(1).u16(2).u32(7).u32(9)
        body.u16(1).ascii('J1')
        return diag_com_ref_body(body, True)
    return body.u8(0).u16(0)


def diag_com_map():
    """diag_com_refs() as a string to reference map."""
    return [{'map_key': entry['name'], 'reference': entry['reference']}
            for entry in diag_com_refs()]


def layer_data(full=False, location='eMULTIPLE_ECU_JOB', kernel_collections=False):
    n = 2 if full else 0
    fields = {'layer_id': 'Layer', 'unknown_1': 'Unknown', 'protocol_type': 'ProtoType',
              'protocol_stack_short_name': 'Stack', 'com_param_spec_pool_id': 'ComParamPool',
              'mcd_location_type': location,
              'diag_com_refs': diag_com_map() if full else [],
              'dtc_dops': strings('Dtc', n), 'dop_refs_map': ref_map('Dop', n),
              'table_refs_map': ref_map('Table', n, vector=True),
              'request_refs_map': ref_map('Request', n),
              'global_negative_response_refs_map': ref_map('Negative', n),
              'functional_class_refs_map': ref_map('Class', n),
              'functional_class_data_primitive_refs_map': [
                  {'string': 'Primitive%d' % i,
                   'map': diag_com_map()} for i in range(1, n + 1)],
              'env_data_descs_map': [{'map_key': 'Env1', 'env_data_desc': audience()},
                                     {'map_key': 'Env2', 'env_data_desc': None}] if full else [],
              'parent_layers_vector': strings('Parent', n),
              'shared_data_parent_layers_vector': strings('Shared', n),
              'not_inherited_dops_map': vector_map('NotInherited', n),
              'not_inherited_tables_map': vector_map('Unknown1', n),
              'not_inherited_diag_comms_map': vector_map('Unknown2', n),
              'not_inherited_glob_neg_responses_map': vector_map('NotNegative', n),
              'unit_group_refs_map': ref_map('UnitGroup', n),
              'unit_refs_map': ref_map('Unit', n),
              'protocol_parameters': [audience(), None] if full else [],
              'ecu_state_chart_refs_map': [], 'sub_component_refs_map': [],
              'additional_audience_refs_map': [], 'special_data_group_refs': None,
              'multiple_ecu_job_refs_map': []}
    if kernel_collections:
        fields['ecu_state_chart_refs_map'] = [
            {'map_key': 'SC1', 'reference': attributed_ref(('A1',))}]
        fields['sub_component_refs_map'] = [
            {'map_key': 'SUB1', 'reference': attributed_ref()}]
        fields['additional_audience_refs_map'] = [
            {'map_key': 'AA1', 'reference': {'object_id': 'AUD1', 'pool_id': 'POOL'}}]
        fields['special_data_group_refs'] = [{'object_id': 7}, {'object_id': 9}]
        fields['multiple_ecu_job_refs_map'] = [{'map_key': 'J1', 'reference': diag_com_ref(True)}]
    return typed('DB_LAYER_DATA', fields)


class LayerDataTests(unittest.TestCase):
    def test_db_layer_data_minimal(self):
        self.assertEqual(load('DB_LAYER_DATA', layer_data_body()),
                         layer_data())

    def test_db_layer_data_kernel_collections(self):
        self.assertEqual(load('DB_LAYER_DATA', layer_data_body(kernel_collections=True)),
                         layer_data(kernel_collections=True))

    def test_db_layer_data_all_branches(self):
        body = layer_data_body(True, 0x0101)
        expected = layer_data(True, 'eECU_BASE_VARIANT')
        expected['ecu_base_variant_ref'] = {'object_id': 'LOC', 'pool_id': 'LOCPOOL'}
        self.assertEqual(load('DB_LAYER_DATA', body), expected)

    def test_db_layer_data_location_types(self):
        cases = [(0x0101, 'eECU_BASE_VARIANT'), (0x0102, 'eECU_VARIANT'),
                 (0x0103, 'eFUNCTIONAL_GROUP'), (0x0104, 'eMULTIPLE_ECU_JOB'),
                 (0x0105, 'ePROTOCOL')]
        for code, name in cases:
            with self.subTest(location=name):
                expected = layer_data(location=name)
                if code in LAYER_LOCATION_REFS:
                    expected[LAYER_LOCATION_REFS[code]] = {'object_id': 'LOC',
                                                           'pool_id': 'LOCPOOL'}
                self.assertEqual(load('DB_LAYER_DATA', layer_data_body(location=code)), expected)

    def test_layer_data_skips_byte_only_outside_0015(self):
        # kernel: the byte after the protocol parameters is absent only in version 0015
        self.assertEqual(load('DB_LAYER_DATA', layer_data_body(byte=False),
                              database_version='0015'), layer_data())
        for version in (None, '0018'):
            with self.subTest(database_version=version):
                self.assertEqual(load('DB_LAYER_DATA', layer_data_body(),
                                      database_version=version), layer_data())


def location_refs_body(body, full):
    """MCD_DB_LOCATION_REFERENCES entries; the access keys carry no existence flag."""
    if not full:
        return body.u16(0)
    body.u16(2).ascii('LocO1').ascii('LocP1').u8(2)
    for key_full in (True, False):
        body = concat(body.u16(object_type_code('MCD_ACCESS_KEY')), access_key_body(key_full))
    return body.ascii('LocO2').ascii('LocP2').u8(0)


def location_refs(full):
    if not full:
        return []
    return [{'object_id': 'LocO1', 'pool_id': 'LocP1',
             'access_keys': [access_key(True), access_key(False)]},
            {'object_id': 'LocO2', 'pool_id': 'LocP2', 'access_keys': []}]


def minimal_variant_body():
    return ecu_body(ref_body(ObjectBytes(), 'BV', 'BVPOOL').absent())


def project_data_body(full=False):
    body = location_refs_body(ObjectBytes(), full)
    ref3_body(body, 'FG')
    ref3_body(body, 'BV')
    named_refs_body(body, NAMED_REFS if full else ())
    ref3_body(body, 'EV')
    body.ascii('String1').ascii('String2').ascii('String3')
    strings_body(body, 'Group', 2 if full else 0)
    if not full:
        return body.u16(0)
    body.u16(2).nested('MCD_DB_ECU_VARIANT', minimal_variant_body())
    return body.absent()


def project_data(full=False):
    return typed('DB_PROJECT_DATA', {
        'location_refs': location_refs(full), 'functional_group_ref': ref3('FG'),
        'ecu_base_variant_ref': ref3('BV'),
        'ecu_variant_ref_collection': named_refs(NAMED_REFS if full else ()),
        'ecu_variant_ref': ref3('EV'), 'string1': 'String1', 'string2': 'String2',
        'string3': 'String3', 'functional_groups': strings('Group', 2 if full else 0),
        'ecu_variants': [typed('MCD_DB_ECU_VARIANT', {
            'ecu_base_variant_ref': {'object_id': 'BV', 'pool_id': 'BVPOOL'},
            'matching_patterns': None, 'ecu': ecu_part()}), None] if full else []})


class ProjectDataTests(unittest.TestCase):
    def test_db_project_data_minimal(self):
        self.assertEqual(load('DB_PROJECT_DATA', project_data_body()), project_data())

    def test_db_project_data_all_branches(self):
        self.assertEqual(load('DB_PROJECT_DATA', project_data_body(True)), project_data(True))


class VehicleInfoDataTests(unittest.TestCase):
    def test_db_vehicle_info_data_minimal(self):
        body = ref_map_body(ObjectBytes(), 'Info', 0).u16(0)
        self.assertEqual(load('DB_VEHICLE_INFO_DATA', body), typed('DB_VEHICLE_INFO_DATA', {
            'vehicle_information_refs': [], 'base_var_prot_id_to_link_info_map': []}))

    def test_db_vehicle_info_data_all_branches(self):
        body = ref_map_body(ObjectBytes(), 'Info', 2).u16(0)
        self.assertEqual(load('DB_VEHICLE_INFO_DATA', body), typed('DB_VEHICLE_INFO_DATA', {
            'vehicle_information_refs': ref_map('Info', 2),
            'base_var_prot_id_to_link_info_map': []}))

    def test_db_vehicle_info_data_link_info_map(self):
        body = ref_map_body(ObjectBytes(), 'Info', 0).u16(2)
        body.ascii('K1').ascii('V1').ascii('K2').ascii(None)
        self.assertEqual(load('DB_VEHICLE_INFO_DATA', body), typed('DB_VEHICLE_INFO_DATA', {
            'vehicle_information_refs': [], 'base_var_prot_id_to_link_info_map': [
                {'map_key': 'K1', 'value': 'V1'}, {'map_key': 'K2', 'value': None}]}))


# ---------------------------------------------------------------------------
# Vehicle connectors, links and information
# ---------------------------------------------------------------------------

# enum_converters.get_MCDConnectorPinType accepts these nine codes but has no return
# statement, so the loaded pin type is None for every one of them today.
PIN_TYPE_CODES = [(0x7400, 'eHI'), (0x7401, 'eLOW'), (0x7402, 'eK'), (0x7403, 'eL'),
                  (0x7404, 'eTX'), (0x7405, 'eRX'), (0x7406, 'ePLUS'), (0x7407, 'eMINUS'),
                  (0x7408, 'eSINGLEWIRE')]


def pin_body(number=1, code=0x7400):
    return described_body(ObjectBytes()).u16(number).u16(code)


def pin(number=1):
    return typed('MCD_DB_VEHICLE_CONNECTOR_PIN', {**described_ids(), 'pin_number': number,
                                                  'pin_type': None})


def pins_body(count=0):
    """Collection with `count` objects; the second of three is absent."""
    body = ObjectBytes().u16(count)
    for i in range(count):
        if i == 1:
            body.absent()
        else:
            body.nested('MCD_DB_VEHICLE_CONNECTOR_PIN', pin_body(i + 1, 0x7400 + i))
    return body


def pins(count=0):
    return [None if i == 1 else pin(i + 1) for i in range(count)]


class VehicleConnectorPinTests(unittest.TestCase):
    def test_mcd_db_vehicle_connector_pin_minimal(self):
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTOR_PIN', pin_body(0)), pin(0))

    def test_mcd_db_vehicle_connector_pin_all_branches(self):
        body = pin_body(12, 0x7408)
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTOR_PIN', body), pin(12))

    def test_mcd_db_vehicle_connector_pin_types(self):
        for code, name in PIN_TYPE_CODES:
            with self.subTest(pin_type=name):
                self.assertEqual(load('MCD_DB_VEHICLE_CONNECTOR_PIN', pin_body(5, code)), pin(5))


class VehicleConnectorPinsTests(unittest.TestCase):
    def test_mcd_db_vehicle_connector_pins_minimal(self):
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTOR_PINS', pins_body()), [])

    def test_mcd_db_vehicle_connector_pins_all_branches(self):
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTOR_PINS', pins_body(3)), pins(3))


def connector_body(with_pins):
    body = described_body(ObjectBytes())
    if with_pins:
        return body.nested('MCD_DB_VEHICLE_CONNECTOR_PINS', pins_body(3))
    return body.absent()


def connector(with_pins):
    return typed('MCD_DB_VEHICLE_CONNECTOR', {**described_ids(),
                                              'connector_pins': pins(3) if with_pins else None})


class VehicleConnectorTests(unittest.TestCase):
    def test_mcd_db_vehicle_connector_minimal(self):
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTOR', connector_body(False)),
                         connector(False))

    def test_mcd_db_vehicle_connector_all_branches(self):
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTOR', connector_body(True)), connector(True))


class VehicleConnectorsTests(unittest.TestCase):
    def test_mcd_db_vehicle_connectors_minimal(self):
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTORS', ObjectBytes().u16(0)), [])

    def test_mcd_db_vehicle_connectors_all_branches(self):
        body = ObjectBytes().u16(3)
        body.nested('MCD_DB_VEHICLE_CONNECTOR', connector_body(True)).absent()
        body.nested('MCD_DB_VEHICLE_CONNECTOR', connector_body(False))
        self.assertEqual(load('MCD_DB_VEHICLE_CONNECTORS', body),
                         [connector(True), None, connector(False)])


class PhysicalVehicleLinkTests(unittest.TestCase):
    def test_mcd_db_physical_vehicle_link_or_interface_minimal(self):
        body = described_body(ObjectBytes()).ascii(None).absent()
        self.assertEqual(
            load('MCD_DB_PHYSICAL_VEHICLE_LINK_OR_INTERFACE', body),
            typed('MCD_DB_PHYSICAL_VEHICLE_LINK_OR_INTERFACE', {
                **described_ids(), 'type': None, 'vehicle_connector_pins': None}))

    def test_mcd_db_physical_vehicle_link_or_interface_all_branches(self):
        body = described_body(ObjectBytes()).ascii('Type')
        body.nested('MCD_DB_VEHICLE_CONNECTOR_PINS', pins_body(3))
        self.assertEqual(
            load('MCD_DB_PHYSICAL_VEHICLE_LINK_OR_INTERFACE', body),
            typed('MCD_DB_PHYSICAL_VEHICLE_LINK_OR_INTERFACE', {
                **described_ids(), 'type': 'Type', 'vehicle_connector_pins': pins(3)}))


def vehicle_information_body(full):
    body = described_body(ObjectBytes())
    if not full:
        return body.u16(0).u16(0).absent()
    body.u16(2).ascii('Link1')
    attributed_ref_body(body, ['S1', 'S2'])
    body.ascii('Link2')
    attributed_ref_body(body)
    body.u16(2)
    for i in (1, 2):
        body.ascii('Phys%d' % i)
        ref3_body(body, 'Phys%d' % i)
    return body.nested('MCD_DB_VEHICLE_CONNECTORS',
                       ObjectBytes().u16(1).nested('MCD_DB_VEHICLE_CONNECTOR',
                                                   connector_body(False)))


def vehicle_information(full):
    return typed('MCD_DB_VEHICLE_INFORMATION', {
        **described_ids(),
        'logical_links': [{'name': 'Link1', 'reference': attributed_ref(['S1', 'S2'])},
                          {'name': 'Link2', 'reference': attributed_ref()}] if full else [],
        'physical_vehicle_links_or_interfaces': [
            {'name': 'Phys%d' % i, 'reference': ref3('Phys%d' % i)} for i in (1, 2)
        ] if full else [],
        'vehicle_connectors': [connector(False)] if full else None})


class VehicleInformationTests(unittest.TestCase):
    def test_mcd_db_vehicle_information_minimal(self):
        self.assertEqual(load('MCD_DB_VEHICLE_INFORMATION', vehicle_information_body(False)),
                         vehicle_information(False))

    def test_mcd_db_vehicle_information_all_branches(self):
        self.assertEqual(load('MCD_DB_VEHICLE_INFORMATION', vehicle_information_body(True)),
                         vehicle_information(True))


# ---------------------------------------------------------------------------
# Caption, code information, trouble code, audience
# ---------------------------------------------------------------------------

class SpecialDataGroupCaptionTests(unittest.TestCase):
    def test_mcd_db_special_data_group_caption_minimal(self):
        body = ObjectBytes().native_ascii(None).native_ascii(None).native_ascii(None)
        body.native_unicode(None).native_unicode(None).native_ascii(None)
        # kernel: a native string without length is empty
        self.assertEqual(load('MCD_DB_SPECIAL_DATA_GROUP_CAPTION', body),
                         typed('MCD_DB_SPECIAL_DATA_GROUP_CAPTION', {
                             'description_id': '', 'long_name_id': '',
                             'unique_object_id': '', 'description': '',
                             'long_name': '', 'short_name': ''}))

    def test_mcd_db_special_data_group_caption_all_branches(self):
        body = ObjectBytes().native_ascii('DescId').native_ascii('LongId').native_ascii('UID')
        body.native_unicode('Description').native_unicode('Long name').native_ascii('Name')
        self.assertEqual(load('MCD_DB_SPECIAL_DATA_GROUP_CAPTION', body),
                         typed('MCD_DB_SPECIAL_DATA_GROUP_CAPTION', {
                             'description_id': 'DescId', 'long_name_id': 'LongId',
                             'unique_object_id': 'UID', **described()}))

    def test_mcd_db_special_data_group_caption_non_ascii_text(self):
        body = ObjectBytes().native_ascii('Größe').native_ascii(None).native_ascii(None)
        body.native_unicode('Überschrift').native_unicode('Länge').native_ascii('Maß')
        self.assertEqual(load('MCD_DB_SPECIAL_DATA_GROUP_CAPTION', body),
                         typed('MCD_DB_SPECIAL_DATA_GROUP_CAPTION', {
                             # kernel: a native string without length is empty
                             'description_id': 'Größe', 'long_name_id': '',
                             'unique_object_id': '', 'description': 'Überschrift',
                             'long_name': 'Länge', 'short_name': 'Maß'}))


def code_information_body(count=0):
    body = ObjectBytes().unicode('code.bin').unicode('Encryption').unicode('Syntax')
    body.unicode('Revision').unicode('EntryPoint').u16(count)
    for i in range(1, count + 1):
        body.ascii('Lib%dKey' % i).ascii('Lib%dR' % i)
        body.ascii('Lib%dP' % i).ascii('Lib%dThird' % i)
    return body


def code_information(count=0):
    return typed('MCD_DB_CODE_INFORMATION', {
        'code_file': 'code.bin', 'encryption': 'Encryption', 'syntax': 'Syntax',
        'revision': 'Revision', 'entry_point': 'EntryPoint',
        # kernel: map key, then a named object reference (object id, pool id, third word)
        'library_refs': [{'map_key': 'Lib%dKey' % i,
                          'reference': {'object_id': 'Lib%dR' % i,
                                        'pool_id': 'Lib%dP' % i,
                                        'object_id2': 'Lib%dThird' % i}}
                         for i in range(1, count + 1)]})


class CodeInformationTests(unittest.TestCase):
    def test_mcd_db_code_information_minimal(self):
        self.assertEqual(load('MCD_DB_CODE_INFORMATION', code_information_body()),
                         code_information())

    def test_mcd_db_code_information_all_branches(self):
        self.assertEqual(load('MCD_DB_CODE_INFORMATION', code_information_body(2)),
                         code_information(2))


class CodeInformationsTests(unittest.TestCase):
    def test_mcd_db_code_informations_minimal(self):
        self.assertEqual(load('MCD_DB_CODE_INFORMATIONS', ObjectBytes().u32(0)), [])

    def test_mcd_db_code_informations_all_branches(self):
        body = ObjectBytes().u32(3)
        body.nested('MCD_DB_CODE_INFORMATION', code_information_body(2)).absent()
        body.nested('MCD_DB_CODE_INFORMATION', code_information_body())
        self.assertEqual(load('MCD_DB_CODE_INFORMATIONS', body),
                         [code_information(2), None, code_information()])


def trouble_code_body(groups=None):
    """MCD_DB_DIAG_TROUBLE_CODE; groups is None (flag off) or a list of object numbers."""
    body = ObjectBytes().ascii('Label').ascii('DtcName').ascii('DtcLong')
    body.unicode('Description').u32(3).u32(0x123456)
    body.flag(groups is not None)
    if groups is not None:
        body.u16(len(groups))
        for number in groups:
            body.u32(number)
    return body.ascii('Text')


def trouble_code(groups=None):
    fields = {'label': 'Label', 'short_name': 'DtcName', 'long_name': 'DtcLong',
              'description': 'Description', 'level': 3, 'trouble_code': 0x123456,
              'trouble_code_text': 'Text'}
    if groups is not None:
        fields['special_data_group_refs'] = [{'object_id': number} for number in groups]
    return typed('MCD_DB_DIAG_TROUBLE_CODE', fields)


class DiagTroubleCodeTests(unittest.TestCase):
    def test_mcd_db_diag_trouble_code_minimal(self):
        self.assertEqual(load('MCD_DB_DIAG_TROUBLE_CODE', trouble_code_body()), trouble_code())

    def test_mcd_db_diag_trouble_code_all_branches(self):
        self.assertEqual(load('MCD_DB_DIAG_TROUBLE_CODE', trouble_code_body([7, 70000])),
                         trouble_code([7, 70000]))


class AudienceTests(unittest.TestCase):
    def test_mcd_audience_minimal(self):
        body = ObjectBytes().u8(0).u8(0).u8(0).u8(0).u8(0)
        self.assertEqual(load('MCD_AUDIENCE', body), typed('MCD_AUDIENCE', {
            'supplier': 0, 'development': 0, 'manufacturing': 0, 'after_sales': 0,
            'after_market': 0}))

    def test_mcd_audience_all_branches(self):
        self.assertEqual(load('MCD_AUDIENCE', audience_body()), audience())


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------

LAYOUT_TEST_MODULES = ['tests.test_vw_layouts_compu', 'tests.test_vw_layouts_services',
                       'tests.test_vw_layouts_project', 'tests.test_layouts_coding_data',
                       'tests.test_layouts_state_charts',
                       'tests.test_layouts_flash', 'tests.test_layouts_sub_component']


def layout_test_names():
    """Names of all test methods in the layout test modules."""
    names = set()
    for module_name in LAYOUT_TEST_MODULES:
        module = importlib.import_module(module_name)
        for value in vars(module).values():
            if (isinstance(value, type) and issubclass(value, unittest.TestCase)
                    and value.__module__ == module_name):
                names.update(unittest.defaultTestLoader.getTestCaseNames(value))
    return names


class CompletenessTests(unittest.TestCase):
    def test_every_registered_loader_is_pinned(self):
        names = layout_test_names()
        missing = ['test_%s_%s' % (loader.lower(), suffix)
                   for loader in object_loaders.__all__ for suffix in ('minimal', 'all_branches')
                   if 'test_%s_%s' % (loader.lower(), suffix) not in names]
        self.assertFalse(missing, 'Loaders without layout tests: ' + ', '.join(missing))
