import unittest

from common_utils.coding_layout import apply_dop, flatten_coding_entry


def dop(bit_length=8, bit_mask=None, compu_category='IDENTICAL', compu_scales=None,
        diag_coded_type='STANDARD-LENGTH-TYPE'):
    result = {'type': 'DOP', 'diag_coded_type': diag_coded_type, 'bit_mask': bit_mask,
              'compu_category': compu_category}
    if diag_coded_type == 'STANDARD-LENGTH-TYPE':
        result['bit_length'] = bit_length
    if compu_scales is not None:
        result['compu_scales'] = compu_scales
    return result


def param(name, byte_position, bit_position=0, parameter_type='VALUE', dop_object=None, **extra):
    result = {'type': 'PARAMETER', 'parameter_type': parameter_type, 'long_name': name,
              'long_name_id': 'ID_' + name, 'byte_position': byte_position,
              'bit_position': bit_position,
              'dop': dop() if dop_object is None else dop_object}
    result.update(extra)
    return result


def structure(parameters, byte_size=None):
    return {'type': 'STRUCTURE', 'long_name': 'S_A', 'description': None,
            'byte_size': byte_size, 'parameters': parameters}


def entry(structure_object, byte_position=0):
    return {'did': 1, 'long_name': 'Row_1', 'long_name_id': 'ID_Row_1', 'description': None,
            'byte_position': byte_position, 'bit_position': 0, 'structure': structure_object}


class FlattenCodingEntryTest(unittest.TestCase):
    def test_nested_structure_absolute_positions(self):
        inner = structure([
            param('C', 0, 0, dop_object=dop(8, bytearray(b'\x0f'))),
            param('B', 1, 3, dop_object=dop(2)),
        ])
        outer = structure([
            param('A', 0, 0),
            param('Inner', 2, 0, dop_object=inner),
        ])
        result = flatten_coding_entry(entry(outer))
        fields = result['fields']
        self.assertEqual([(f['long_name'], f['byte_position'], f['bit_position']) for f in fields],
                         [('A', 0, 0), ('C', 2, 0), ('B', 3, 3)])
        self.assertEqual(fields[1]['bit_mask'], bytearray(b'\x0f'))
        self.assertEqual(result['byte_length'], 4)
        self.assertIsNone(result['note'])

    def test_row_byte_position_is_added(self):
        result = flatten_coding_entry(entry(structure([param('A', 0)]), byte_position=1))
        self.assertEqual(result['fields'][0]['byte_position'], 1)

    def test_row_without_byte_position_counts_as_zero(self):
        result = flatten_coding_entry(entry(structure([param('A', 2)]), byte_position=None))
        self.assertEqual(result['fields'][0]['byte_position'], 2)

    def test_byte_size_wins(self):
        result = flatten_coding_entry(entry(structure([param('A', 0)], byte_size=6)))
        self.assertEqual(result['byte_length'], 6)

    def test_fields_have_only_the_documented_keys_with_byte_size(self):
        result = flatten_coding_entry(entry(structure([param('A', 0)], byte_size=6)))
        self.assertEqual(list(result['fields'][0]), ['byte_position', 'bit_position', 'bit_length', 'bit_mask',
                                                     'long_name', 'long_name_id', 'parameter_type', 'values',
                                                     'default', 'note'])

    def test_texttable_values_and_default(self):
        scales = [{'lower_limit': 0, 'upper_limit': 0, 'long_name': 'Off', 'long_name_id': 'ID_Off'},
                  {'lower_limit': 1, 'upper_limit': 3, 'long_name': 'On', 'long_name_id': 'ID_On'}]
        default = {'data_type': 'A_UINT32', 'value': 1}
        p = param('A', 0, dop_object=dop(compu_category='TEXTTABLE', compu_scales=scales),
                  default_value=default)
        field = flatten_coding_entry(entry(structure([p])))['fields'][0]
        self.assertEqual(field['values'], [
            {'lower_limit': 0, 'upper_limit': 0, 'text': 'Off', 'text_id': 'ID_Off'},
            {'lower_limit': 1, 'upper_limit': 3, 'text': 'On', 'text_id': 'ID_On'}])
        self.assertEqual(field['default'], default)
        self.assertEqual(field['parameter_type'], 'VALUE')
        self.assertEqual(field['long_name_id'], 'ID_A')

    def test_non_texttable_has_no_values(self):
        field = flatten_coding_entry(entry(structure([param('A', 0)])))['fields'][0]
        self.assertEqual(field['values'], [])
        self.assertIsNone(field['default'])

    def test_constant_is_default(self):
        constant = {'data_type': 'A_UINT32', 'value': 5}
        p = param('K', 0, parameter_type='CODED-CONST', constant=constant)
        field = flatten_coding_entry(entry(structure([p])))['fields'][0]
        self.assertEqual(field['default'], constant)

    def test_min_max_length_field_makes_length_not_fixed(self):
        p = param('A', 0, dop_object=dop(diag_coded_type='MIN-MAX-LENGTH-TYPE'))
        result = flatten_coding_entry(entry(structure([p])))
        self.assertIsNone(result['byte_length'])
        self.assertEqual(result['note'], 'Length is not fixed')

    def test_no_fields_gives_length_zero(self):
        result = flatten_coding_entry(entry(structure([])))
        self.assertEqual(result['byte_length'], 0)
        self.assertEqual(result['fields'], [])

    def test_field_without_byte_position_gets_note(self):
        result = flatten_coding_entry(entry(structure([param('A', None)])))
        field = result['fields'][0]
        self.assertIsNone(field['byte_position'])
        self.assertEqual(field['note'], 'No BYTE-POSITION, position not computed')
        self.assertIsNone(result['byte_length'])
        self.assertEqual(result['note'], 'Length is not fixed')

    def test_nested_structure_without_byte_position(self):
        inner = structure([param('C', 0)])
        outer = structure([param('Inner', None, dop_object=inner)])
        field = flatten_coding_entry(entry(outer))['fields'][0]
        self.assertEqual(field['long_name'], 'C')
        self.assertIsNone(field['byte_position'])
        self.assertEqual(field['note'], 'No BYTE-POSITION, position not computed')

    def test_mux_gets_note_instead_of_error(self):
        p = param('M', 2, dop_object={'type': 'MUX'})
        result = flatten_coding_entry(entry(structure([p])))
        field = result['fields'][0]
        self.assertEqual(field['note'], 'MUX not expanded')
        self.assertEqual(field['byte_position'], 2)
        self.assertEqual(field['long_name'], 'M')
        self.assertEqual(result['note'], 'Length is not fixed')

    def test_dop_error_marker_gets_note(self):
        p = param('E', 0, dop_object={'#error': 'boom'})
        field = flatten_coding_entry(entry(structure([p])))['fields'][0]
        self.assertEqual(field['note'], 'DOP not available')

    def test_unexpected_parameter_type_gets_note(self):
        p = param('Y', 0, parameter_type='SYSTEM')
        field = flatten_coding_entry(entry(structure([p])))['fields'][0]
        self.assertEqual(field['note'], 'Parameter type SYSTEM not expected in coding structure')

    def test_error_structure(self):
        result = flatten_coding_entry(entry({'#error': 'x'}))
        self.assertEqual(result, {'byte_length': None, 'note': 'Structure not available',
                                  'fields': []})


class ApplyDopTests(unittest.TestCase):
    @staticmethod
    def blank_field():
        return {'bit_length': None, 'bit_mask': None, 'values': [], 'note': None,
                '_standard_length': False}

    def test_texttable_dop_sets_values(self):
        field = self.blank_field()
        apply_dop(field, {'type': 'DOP', 'bit_length': 2, 'bit_mask': None,
                          'diag_coded_type': 'STANDARD-LENGTH-TYPE', 'compu_category': 'TEXTTABLE',
                          'compu_scales': [{'lower_limit': 0, 'upper_limit': 0,
                                            'long_name': 'off', 'long_name_id': 'ID_off'}]})
        self.assertEqual(field['bit_length'], 2)
        self.assertIs(field['_standard_length'], True)
        self.assertEqual(field['values'], [{'lower_limit': 0, 'upper_limit': 0,
                                            'text': 'off', 'text_id': 'ID_off'}])

    def test_error_dop_sets_note(self):
        field = self.blank_field()
        apply_dop(field, {'#error': 'x'})
        self.assertEqual(field['note'], 'DOP not available')
        self.assertIsNone(field['bit_length'])

    def test_structure_dop_is_not_expanded(self):
        field = self.blank_field()
        apply_dop(field, {'type': 'STRUCTURE'})
        self.assertEqual(field['note'], 'STRUCTURE not expanded')


if __name__ == '__main__':
    unittest.main()
