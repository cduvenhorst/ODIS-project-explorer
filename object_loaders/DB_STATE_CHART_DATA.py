from classes import DbObject
from common_utils import common_loaders


# Field names are the kernel setter names; per the getters, the keys are short names of a
# state transition (actions map) and of a state (precondition definitions map)
def load_map(stream):
    entries = []
    for _ in range(stream.loadNumericType(2)):
        entry = {'map_key': stream.loadAsciiString()[0]}
        entry['items'] = [DbObject.load_object_from_stream_if_exists(stream) for _ in range(stream.loadNumericType(2))]
        entries.append(entry)
    return entries


def load(stream):
    obj = {}
    
    obj['state_trans_trans_actions_map'] = load_map(stream)
    obj['state_precondition_defs_map'] = load_map(stream)
    
    # Precondition definitions without a DiagCom reference take their table parameter from
    # named stream C, one reference each in reading order
    pending = [definition for entry in obj['state_precondition_defs_map'] for definition in entry['items']
               if definition is not None and definition['diag_com_primitive'] is None]
    readers = {}
    if pending:
        readers['C'] = lambda s: [common_loaders.load_reference(s, True) for _ in range(len(pending))]
    streams = common_loaders.loadNamedStreams(stream, readers)
    if pending:
        if 'C' not in streams:
            raise RuntimeError('Named stream C missing for {} precondition definitions'.format(len(pending)))
        for definition, reference in zip(pending, streams['C']):
            definition['table_parameter'] = reference
    
    return obj
