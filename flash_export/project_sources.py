"""Flash data of a project, collected along the pool chain DbFlashData -> ECU_MEM -> session -> data block."""
import os
import posixpath
import sys
from typing import Callable

from classes import DbObject  # noqa: F401  (loads the object loaders first; they import each other circularly)
from common_utils.enum_converters import get_db_file_type
from flash_export.output import SOURCE_PROJECTS, Occurrence, sanitize_name
from object_loaders.MCD_DB_FLASH_DATA import INLINE_PREFIX

FLASH_DATA_OBJECT_ID = 'DbFlashData'
_METHOD_SOURCE = 'encryption_compression_method'


def project_file_index(project_dir: str) -> dict[str, str]:
    """Map the lower-case '/'-path of every file below ``project_dir`` to its actual '/'-path."""
    index: dict[str, str] = {}
    for folder, folders, files in os.walk(project_dir):
        folders.sort()
        for name in sorted(files):
            relative = os.path.relpath(os.path.join(folder, name), project_dir).replace(os.sep, '/')
            index.setdefault(relative.lower(), relative)
    return index


def resolve_external_file(index: dict[str, str], sub_directory: str | None, file_name: str | None) -> str | None:
    """Find a referenced flash file in the index, ignoring case; wildcards are not resolved."""
    name = (file_name or '').replace('\\', '/')
    sub = (sub_directory or '').replace('\\', '/')
    key = posixpath.normpath(sub + '/' + name if sub else name).lower()
    return index.get(key)


def _ecu(ecu_mem: dict) -> str:
    if ecu_mem.get('has_layers'):
        names = [layer.get('id_reference') for layer in ecu_mem.get('layers') or [] if layer]
    else:
        names = [item.get('name') for item in (ecu_mem.get('base_variants') or []) + (ecu_mem.get('variants') or [])]
    return '; '.join(str(name) for name in names if name)


def _value_text(value) -> str:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex().upper()
    return str(value)


def _part_number(*ident_lists) -> str:
    parts = []
    for idents in ident_lists:
        for ident in idents or []:
            for value in ident.get('ident_values') or []:
                parts.append('%s=%s' % (ident.get('short_name'), _value_text(value.get('value'))))
    return '; '.join(parts)


def _method(flash_data: dict) -> int | None:
    value = (flash_data.get('encryption_compression_method') or {}).get('value')
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, (bytes, bytearray)) and len(value) == 1:
        return value[0]
    return None


def _segments(block: dict) -> tuple[int | None, int | None]:
    segments = block.get('flash_segments') or []
    if not segments:
        return None, None
    return (min(segment['source_start_address'] for segment in segments),
            sum(segment['uncompressed_size'] for segment in segments))


def _read_file(path: str) -> Callable[[], bytes]:
    def read(path=path) -> bytes:
        with open(path, 'rb') as handle:
            return handle.read()
    return read


def _report(pool: str, what: str, error: Exception) -> None:
    print('error loading %s of pool %s: %s' % (what, pool, type(error).__name__), file=sys.stderr)


def pool_chain_occurrences(object_loader, project_dir: str, project_name: str, index: dict[str, str],
                           notes_for: Callable[[str], list[str]] = lambda path: []
                           ) -> tuple[list[Occurrence], set[str], int]:
    """Collect the flash blocks of all flash pools; return occurrences, reached paths and the error count."""
    occurrences: list[Occurrence] = []
    reached: set[str] = set()
    errors = 0
    file_counts: dict[str, int] = {}
    for file_name in sorted(os.listdir(project_dir)):
        if not file_name.endswith('.db'):
            continue
        pool = file_name[:-3]
        if '.' not in pool or get_db_file_type(pool) != 'Flash':
            continue
        try:
            flash_data_object = object_loader.load_object_by_id(project_dir, pool, FLASH_DATA_OBJECT_ID)
        except KeyError:
            continue
        except Exception as error:
            errors += 1
            _report(pool, FLASH_DATA_OBJECT_ID, error)
            continue
        pool_count = 0
        for mem_entry in flash_data_object['ecu_mem_references']:
            mem_reference = mem_entry['reference']
            try:
                ecu_mem = object_loader.load_object_by_id(project_dir, mem_reference['pool_id'],
                                                          mem_reference['object_id'])
                ecu = _ecu(ecu_mem)
                session_entries = ecu_mem['flash_sessions'] or []
            except Exception as error:
                errors += 1
                _report(pool, 'ECU_MEM ' + str(mem_reference.get('object_id')), error)
                continue
            for session_entry in session_entries:
                session_reference = session_entry['reference']
                try:
                    session = object_loader.load_object_by_id(project_dir, session_reference['pool_id'],
                                                              session_reference['object_id'])
                    blocks = session['data_blocks'] or []
                except Exception as error:
                    errors += 1
                    _report(pool, 'session ' + str(session_reference.get('object_id')), error)
                    continue
                for number, block in enumerate(blocks, 1):
                    flash_data = block['flash_data']
                    reference = flash_data['data_reference']
                    part_number = _part_number(session.get('expected_idents'), block.get('own_idents'))
                    notes = [] if part_number else ['no part number in pool']
                    start, size = _segments(block)
                    fields = dict(
                        source_rank=SOURCE_PROJECTS, origin_kind='project', origin=project_name,
                        detail='%s/%s/%d' % (pool, session['short_name'], number), ecu=ecu,
                        part_number=part_number, session=session['short_name'], block=block['short_name'],
                        block_type=block['data_block_type'], start_address=start, uncompressed_size=size,
                        method=_method(flash_data), method_source=_METHOD_SOURCE)
                    kind = reference['kind']
                    if kind == 'external_file':
                        name = reference.get('file_name')
                        sub = flash_data.get('flash_file_sub_directory_name')
                        found = resolve_external_file(index, sub, name)
                        if found is None:
                            wildcard = any(c in (name or '') for c in '*?')
                            notes.append('file not found in project' + (' (wildcard name)' if wildcard else ''))
                            source = '%s/%s' % (sub, name) if sub else str(name)
                            file_counts[source] = file_counts.get(source, 0) + 1
                            occurrences.append(Occurrence(source=source, block_index=file_counts[source],
                                                          target=None, read=None, note='; '.join(notes),
                                                          **fields))
                            continue
                        reached.add(found)
                        notes.extend(notes_for(found))
                        file_counts[found] = file_counts.get(found, 0) + 1
                        occurrences.append(Occurrence(
                            source=found, block_index=file_counts[found], target='flash/%s/%s' % (project_name, found),
                            read=_read_file(os.path.join(project_dir, *found.split('/'))),
                            note='; '.join(notes), **fields))
                        continue
                    pool_count += 1
                    target = 'flash/%s/%s/%s.bin' % (project_name, pool, sanitize_name(block['short_name']))
                    if kind in ('object', 'big_data_object'):
                        read = (lambda pool_id=reference['pool_id'], object_id=reference['object_id']:
                                object_loader.load_inline_flash_data_by_id(project_dir, pool_id, object_id))
                    else:
                        stored = flash_data['data_file_name_or_inline_flash_data']
                        read = lambda stored=stored: bytes.fromhex(stored[len(INLINE_PREFIX):])
                    occurrences.append(Occurrence(source=pool, block_index=pool_count, target=target, read=read,
                                                  note='; '.join(notes), **fields))
    return occurrences, reached, errors
